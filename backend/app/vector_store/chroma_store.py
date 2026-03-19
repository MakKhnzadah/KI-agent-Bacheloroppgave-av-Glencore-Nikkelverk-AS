from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb


@dataclass
class ChromaVectorStore:
    persist_dir: Path
    collection_name: str

    def __post_init__(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(name=self.collection_name)

    def reset_collection(self) -> None:
        """Delete and recreate the collection.

        Useful for a full rebuild when the underlying KB documents change and
        old embeddings must be removed.
        """

        try:
            self._client.delete_collection(name=self.collection_name)
        except Exception:
            # Collection may not exist yet; ignore.
            pass
        self._collection = self._client.get_or_create_collection(name=self.collection_name)

    def upsert(
        self,
        *,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if metadatas is None:
            metadatas = [{} for _ in ids]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        *,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
