from __future__ import annotations

from dataclasses import dataclass
from typing import List

import requests


@dataclass(frozen=True)
class OllamaEmbeddingClient:
    base_url: str
    model: str
    timeout_s: float = 60.0

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Ollama embeddings endpoint
        # https://github.com/ollama/ollama/blob/main/docs/api.md
        url = self.base_url.rstrip("/") + "/api/embeddings"
        resp = requests.post(
            url,
            json={"model": self.model, "prompt": text},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        payload = resp.json()

        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise RuntimeError(f"Unexpected Ollama embeddings response: {payload}")

        return embedding
