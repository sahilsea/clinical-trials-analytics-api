"""Application settings, loaded from environment variables or a `.env` file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Clinical Trials Analytics API"
    database_url: str = "sqlite:///./clinical_trials.db"
    api_key: str = "change-me"
    default_page_size: int = 20
    max_page_size: int = 100
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
