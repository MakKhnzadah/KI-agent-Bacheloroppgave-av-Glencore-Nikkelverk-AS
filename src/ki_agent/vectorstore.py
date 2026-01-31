from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .storage import ensure_dir


class VectorStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class VectorChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float | None


class VectorStore:
    def upsert(self, *, chunks: list[VectorChunk], embeddings: list[list[float]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def query(
        self, *, embedding: list[float], n_results: int = 5
    ) -> list[VectorSearchResult]:  # pragma: no cover
        raise NotImplementedError


def make_chunk_id(source: str, chunk_index: int) -> str:
    ns = uuid.UUID("f2a86e07-5f3f-4b06-bb31-78f5f7cc5a63")
    return str(uuid.uuid5(ns, f"{source}::chunk::{chunk_index}"))


def get_vectorstore(settings: Settings) -> VectorStore:
    provider = (settings.vector_provider or "none").lower()
    if provider in {"none", "disabled"}:
        raise VectorStoreError(
            "Vector store is disabled (VECTOR_PROVIDER=none). Set VECTOR_PROVIDER=chroma and install extras: "
            "pip install -e .[vector]"
        )

    if provider == "chroma":
        return ChromaVectorStore(
            persist_dir=settings.vector_dir,
            collection_name=settings.vector_collection,
        )

    raise VectorStoreError(f"Unknown VECTOR_PROVIDER: {settings.vector_provider!r}")


class ChromaVectorStore(VectorStore):
    def __init__(self, *, persist_dir: Path, collection_name: str):
        try:
            import chromadb  # type: ignore
        except Exception as e:  # pragma: no cover
            raise VectorStoreError(
                "Chroma backend requires optional dependency. Install with: pip install -e .[vector]"
            ) from e

        ensure_dir(persist_dir)

        self._persist_dir = persist_dir
        self._collection_name = collection_name

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, *, chunks: list[VectorChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("chunks and embeddings length mismatch")
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [c.metadata for c in chunks]

        self._collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    def query(self, *, embedding: list[float], n_results: int = 5) -> list[VectorSearchResult]:
        res = self._collection.query(query_embeddings=[embedding], n_results=n_results)

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0] if res.get("distances") is not None else [None] * len(ids)

        out: list[VectorSearchResult] = []
        for i in range(len(ids)):
            dist_val = dists[i] if dists and i < len(dists) else None
            dist: float | None
            if dist_val is None:
                dist = None
            else:
                try:
                    dist = float(dist_val)  # type: ignore[arg-type]
                except Exception:
                    dist = None
            out.append(
                VectorSearchResult(
                    chunk_id=str(ids[i]),
                    text=str(docs[i]) if docs and docs[i] is not None else "",
                    metadata=metas[i] if isinstance(metas[i], dict) else {},
                    distance=dist,
                )
            )
        return out
