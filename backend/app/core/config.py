from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Amazon Mercado Libre Publisher"
    database_url: str = "sqlite:///./dev.db"
    meli_client_id: str = ""
    meli_client_secret: str = ""
    meli_redirect_uri: str = "http://localhost:8000/api/stores/meli/callback"
    frontend_url: str = "http://localhost:5173"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.1-70b-instruct"
    default_site_id: str = "MLM"
    allow_live_publish: bool = False
    token_encryption_key: str = "local-dev-token-key-change-me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
