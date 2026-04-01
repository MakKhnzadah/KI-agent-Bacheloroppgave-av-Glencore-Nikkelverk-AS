from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.vector_store.chroma_store import ChromaVectorStore
from app.vector_store.config import load_vector_store_config
from app.vector_store.kb_indexer import index_kb
from app.vector_store.ollama_embeddings import OllamaEmbeddingClient


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
