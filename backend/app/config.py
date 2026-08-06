from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    anthropic_api_key: str
    cohere_api_key: str
    # Only used by ingestion/scraper.py — optional so the API server can boot without them
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""
    nhtsa_api_base: str = "https://vpic.nhtsa.dot.gov/api/vehicles"
    sqlite_fts_path: str = "fts_index.db"
    # Comma-separated allowed origins; "*" allows all (dev only — set the frontend URL in prod)
    cors_origins: str = "*"
    # If set, every non-/health request must send a matching X-API-Key header
    api_key: str | None = None
    # Per-IP limit on POST requests per minute; 0 disables
    rate_limit_per_minute: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
