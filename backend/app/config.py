from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    anthropic_api_key: str
    cohere_api_key: str
    browserbase_api_key: str
    browserbase_project_id: str
    nhtsa_api_base: str = "https://vpic.nhtsa.dot.gov/api/vehicles"
    sqlite_fts_path: str = "fts_index.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
