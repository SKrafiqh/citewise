"""Application settings loaded from the project-root .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    database_url: str = ""
    llm_cache_dir: Path = ROOT / ".cache" / "llm"


@lru_cache
def get_settings() -> Settings:
    return Settings()
