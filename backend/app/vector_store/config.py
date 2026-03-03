from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VectorStoreConfig:
    ollama_base_url: str
    ollama_embed_model: str
    chroma_collection: str
    persist_dir: Path


def _repo_root_from_here() -> Path:
    # backend/app/vector_store/config.py -> repo root is 3 parents up
    return Path(__file__).resolve().parents[3]


def load_vector_store_config() -> VectorStoreConfig:
    repo_root = _repo_root_from_here()
    persist_default = repo_root / "databases" / "vector_store" / "chroma"

    return VectorStoreConfig(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "kb_chunks"),
        persist_dir=Path(os.getenv("VECTOR_STORE_DIR", str(persist_default))),
    )
