"""Application settings loaded from the project-root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    # Free-tier quotas are per minute; 0 disables client-side spacing (paid tiers).
    gemini_max_rpm: int = 0
    openrouter_max_rpm: int = 0

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    database_url: str = ""
    llm_cache_dir: Path = ROOT / ".cache" / "llm"

    # Retrieval gate: top-1 cosine similarity below this declines the question.
    # Placeholder until tuned on the off-material slice (eval.run_rag_eval --tune-gate).
    coverage_threshold: float = 0.6
    # Cosine similarity at or above which two questions count as duplicates.
    dedup_threshold: float = 0.88
    whisper_model: str = "small"

    data_dir: Path = ROOT / "data"
    prompts_dir: Path = ROOT / "prompts"

    # Comma-separated browser origins allowed to call the API.
    cors_origins: str = "http://localhost:3000"
    # Ingestion endpoints are disabled unless this is set; clients send it as X-Admin-Token.
    admin_token: str = ""
    # Per-IP requests per minute on endpoints that spend LLM budget.
    rate_limit_per_minute: int = 30
    # Total LLM-spending requests accepted per day across all clients (cost ceiling).
    daily_request_cap: int = 3000
    # Reverse proxies in front of the API (Render = 1). 0 = use the socket peer address.
    trusted_proxy_hops: int = 1
    max_upload_mb: int = 50

    @property
    def derived_dir(self) -> Path:
        return self.data_dir / "derived"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
