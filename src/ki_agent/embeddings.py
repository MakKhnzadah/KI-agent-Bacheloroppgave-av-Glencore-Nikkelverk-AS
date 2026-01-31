from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class EmbeddingsError(RuntimeError):
    pass


def _require(value: str | None, name: str) -> str:
    if value is None or not str(value).strip():
        raise EmbeddingsError(f"Missing required setting: {name}")
    return value


def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Supports:
    - OpenAI-compatible endpoint: POST {OPENAI_BASE_URL}/v1/embeddings
    - Azure OpenAI embeddings endpoint

    Note: This is synchronous for simplicity (MVP).
    """

    if not texts:
        return []

    provider = settings.effective_embedding_provider.lower()
    if provider == "openai":
        return _embed_openai_compatible(settings, texts)
    if provider == "azure":
        return _embed_azure_openai(settings, texts)

    raise EmbeddingsError(
        f"Unsupported embedding provider: {provider!r}. Expected 'openai' or 'azure'."
    )


def _embed_openai_compatible(settings: Settings, texts: list[str]) -> list[list[float]]:
    api_key = _require(settings.openai_api_key, "OPENAI_API_KEY")
    base_url = (settings.openai_base_url or "").rstrip("/")
    if not base_url:
        raise EmbeddingsError("Missing required setting: OPENAI_BASE_URL")

    url = f"{base_url}/v1/embeddings"
    payload: dict[str, Any] = {
        "model": settings.openai_embedding_model,
        "input": texts,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload, headers=headers)

    if resp.status_code >= 400:
        raise EmbeddingsError(f"Embeddings request failed: {resp.status_code} {resp.text}")

    data = resp.json()
    items = data.get("data")
    if not isinstance(items, list):
        raise EmbeddingsError("Unexpected embeddings response format (missing 'data')")

    vectors: list[list[float]] = []
    for item in items:
        vec = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vec, list):
            raise EmbeddingsError("Unexpected embeddings response format (missing 'embedding')")
        vectors.append([float(x) for x in vec])

    if len(vectors) != len(texts):
        raise EmbeddingsError("Embeddings response length mismatch")

    return vectors


def _embed_azure_openai(settings: Settings, texts: list[str]) -> list[list[float]]:
    endpoint = _require(settings.azure_openai_endpoint, "AZURE_OPENAI_ENDPOINT")
    api_key = _require(settings.azure_openai_api_key, "AZURE_OPENAI_API_KEY")
    deployment = _require(settings.azure_openai_embedding_deployment, "AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    endpoint = endpoint.rstrip("/")
    api_version = settings.azure_openai_api_version

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings"
    params = {"api-version": api_version}

    payload: dict[str, Any] = {"input": texts}
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, params=params, json=payload, headers=headers)

    if resp.status_code >= 400:
        raise EmbeddingsError(f"Embeddings request failed: {resp.status_code} {resp.text}")

    data = resp.json()
    items = data.get("data")
    if not isinstance(items, list):
        raise EmbeddingsError("Unexpected embeddings response format (missing 'data')")

    vectors: list[list[float]] = []
    for item in items:
        vec = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vec, list):
            raise EmbeddingsError("Unexpected embeddings response format (missing 'embedding')")
        vectors.append([float(x) for x in vec])

    if len(vectors) != len(texts):
        raise EmbeddingsError("Embeddings response length mismatch")

    return vectors
