"""
Centralized app configuration.

Every value here is read from environment variables (see .env.example).
Nothing is hard-coded so the app never needs a code change to point at a
different Hindsight instance, LLM provider, or environment.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Hindsight
    hindsight_base_url: str = "https://api.hindsight.vectorize.io"
    hindsight_api_key: str | None = None
    hindsight_bank_id: str = "secops-memory-org1"

    # Groq / LLM
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"

    # App
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — env is only read once per process."""
    return Settings()
