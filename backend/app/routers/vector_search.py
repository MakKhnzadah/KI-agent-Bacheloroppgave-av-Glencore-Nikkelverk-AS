from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.vector_store.chroma_store import ChromaVectorStore
from app.vector_store.config import load_vector_store_config
from app.vector_store.kb_indexer import index_kb
from app.vector_store.ollama_embeddings import OllamaEmbeddingClient


router = APIRouter(prefix="/vector", tags=["vector"])


@router.post("/index/kb")
def index_knowledge_base() -> dict:
    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
    embedder = OllamaEmbeddingClient(base_url=cfg.ollama_base_url, model=cfg.ollama_embed_model)

    try:
        stats = index_kb(store=store, embedder=embedder)
        return {"status": "ok", "indexed": stats, "persist_dir": str(cfg.persist_dir)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search")
def search(q: str, k: int = 5) -> dict:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' cannot be empty")

    cfg = load_vector_store_config()
    store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
    embedder = OllamaEmbeddingClient(base_url=cfg.ollama_base_url, model=cfg.ollama_embed_model)

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
