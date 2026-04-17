from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.vector_store.config import load_vector_store_config


router = APIRouter(prefix="/vector", tags=["vector"])


def _load_vector_deps():
    """Load optional vector-search dependencies.

    This keeps the API runnable without chromadb installed.
    """

    try:
        from app.vector_store.chroma_store import ChromaVectorStore
        from app.vector_store.kb_indexer import index_kb
        from app.vector_store.ollama_embeddings import OllamaEmbeddingClient
    except ModuleNotFoundError as exc:
        # Most common on Windows when running minimal requirements.
        raise HTTPException(
            status_code=503,
            detail="Vector search is disabled (missing optional dependency 'chromadb').",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Vector search is disabled (optional dependencies failed to load: {exc}).",
        ) from exc

    return ChromaVectorStore, index_kb, OllamaEmbeddingClient


def _repo_root() -> Path:
    from app.vector_store.config import _repo_root_from_here

    return Path(_repo_root_from_here())


def _kb_raw_root() -> Path:
    return _repo_root() / "databases" / "knowledge_base" / "raw"


def _to_kb_rel_path_from_meta(meta: dict) -> str | None:
    raw_path = str((meta or {}).get("path") or "").strip()
    if not raw_path:
        return None

    repo_root = _repo_root().resolve()
    kb_root = _kb_raw_root().resolve()

    try:
        full = Path(raw_path)
        if not full.is_absolute():
            full = (repo_root / full).resolve()
        else:
            full = full.resolve()
        return full.relative_to(kb_root).as_posix()
    except Exception:
        return None


@router.get("/db/documents")
def list_vector_db_documents(limit: int = 200, offset: int = 0) -> dict:
    """List unique KB documents currently stored in the Chroma vector DB.

    We group by `metadata.path` (one document => many chunks).
    """

    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    ChromaVectorStore, _index_kb, _OllamaEmbeddingClient = _load_vector_deps()
    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)

    # Iterate metadatas in batches to avoid loading full documents.
    batch_size = 5000
    cursor = 0
    by_path: dict[str, dict] = {}

    try:
        while True:
            res = store.get(limit=batch_size, offset=cursor, include=["metadatas"])
            ids = res.get("ids") or []
            metas = res.get("metadatas") or []
            if not ids:
                break

            for meta in metas:
                if not isinstance(meta, dict):
                    continue
                path = str(meta.get("path") or "").strip()
                if not path:
                    continue

                rec = by_path.get(path)
                if rec is None:
                    kb_path = _to_kb_rel_path_from_meta(meta)
                    rec = {
                        "path": path,
                        "kb_path": kb_path,
                        "title": str(meta.get("title") or "").strip() or (kb_path or Path(path).stem),
                        "doc_id": str(meta.get("doc_id") or "").strip(),
                        "doc_hash": str(meta.get("doc_hash") or "").strip() or None,
                        "chunk_count": 0,
                    }
                    by_path[path] = rec

                rec["chunk_count"] = int(rec.get("chunk_count") or 0) + 1

            cursor += len(ids)
            if len(ids) < batch_size:
                break

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    docs = list(by_path.values())
    docs.sort(key=lambda d: ((d.get("title") or "").lower(), (d.get("kb_path") or d.get("path") or "").lower()))

    total = len(docs)
    sliced = docs[offset : offset + limit]

    return {
        "total_documents": total,
        "returned": len(sliced),
        "offset": offset,
        "limit": limit,
        "documents": sliced,
        "persist_dir": str(cfg.persist_dir),
        "collection": cfg.chroma_collection,
    }


@router.delete("/db/documents")
def delete_vector_db_document(kb_path: str) -> dict:
    """Delete a KB document from the vector DB.

    This removes all chunks whose metadata.path matches the KB markdown file.
    """

    if not (kb_path or "").strip():
        raise HTTPException(status_code=400, detail="Query param 'kb_path' is required")

    ChromaVectorStore, _index_kb, _OllamaEmbeddingClient = _load_vector_deps()
    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)

    # Validate & normalize kb_path without requiring the file to exist.
    try:
        from app.kb.kb_reader import resolve_kb_path

        full = resolve_kb_path(kb_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    meta_path = str(full.resolve().as_posix())

    try:
        store.delete(where={"path": meta_path})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "deleted_kb_path": kb_path}


@router.post("/index/kb")
def index_knowledge_base() -> dict:
    ChromaVectorStore, index_kb, OllamaEmbeddingClient = _load_vector_deps()
    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
    embedder = OllamaEmbeddingClient(
        base_url=cfg.ollama_base_url,
        model=cfg.ollama_embed_model,
        timeout_s=cfg.ollama_embed_timeout_s,
    )

    try:
        stats = index_kb(store=store, embedder=embedder)
        return {"status": "ok", "indexed": stats, "persist_dir": str(cfg.persist_dir)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search")
def search(q: str, k: int = 5) -> dict:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' cannot be empty")

    ChromaVectorStore, _index_kb, OllamaEmbeddingClient = _load_vector_deps()
    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
    embedder = OllamaEmbeddingClient(
        base_url=cfg.ollama_base_url,
        model=cfg.ollama_embed_model,
        timeout_s=cfg.ollama_embed_timeout_s,
    )

    try:
        query_embedding = embedder.embed_text(q)
        res = store.query(query_embedding=query_embedding, n_results=max(1, min(k, 20)))
        # Chroma returns lists per query; we sent one query.
        return {
            "query": q,
            "k": k,
            "results": [
                {
                    "distance": res.get("distances", [[None]])[0][i],
                    "metadata": res.get("metadatas", [[{}]])[0][i],
                    "text": res.get("documents", [[""]])[0][i],
                }
                for i in range(len(res.get("documents", [[]])[0]))
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
