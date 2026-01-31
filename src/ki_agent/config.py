from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "openai"  # openai | azure

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-01-preview"

    # Vector database / embeddings (optional)
    # - vector_provider: "none" | "chroma" (local persistent)
    # - embedding_provider: defaults to llm_provider if not set
    vector_provider: str = "none"
    vector_collection: str = "kb"
    vector_dir: Path = Path("data/vectorstore")

    embedding_provider: str | None = None  # openai | azure | None

    # OpenAI-compatible embeddings
    openai_base_url: str = "https://api.openai.com"
    openai_embedding_model: str = "text-embedding-3-small"

    # Azure OpenAI embeddings (deployment name)
    azure_openai_embedding_deployment: str | None = None

    kb_raw_dir: Path = Path("knowledge_base/raw")
    kb_html_dir: Path = Path("knowledge_base/html")
    data_dir: Path = Path("data")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def normalized_dir(self) -> Path:
        return self.data_dir / "normalized"

    @property
    def suggestions_dir(self) -> Path:
        return self.data_dir / "suggestions"

    @property
    def reviews_dir(self) -> Path:
        return self.data_dir / "reviews"

    @property
    def effective_embedding_provider(self) -> str:
        return self.embedding_provider or self.llm_provider


def get_settings() -> Settings:
    return Settings()
