from functools import lru_cache

from pydantic import model_validator
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
    volcengine_api_key: str = ""
    volcengine_base_url: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    volcengine_model: str = "doubao-seed-2.1-turbo"
    default_site_id: str = "MLM"
    allow_live_publish: bool = False
    token_encryption_key: str = "local-dev-token-key-change-me"
    job_stale_after_seconds: int = 900
    job_execution_timeout_seconds: int = 840
    listing_type_cache_ttl_seconds: int = 900
    amazon_domain_min_interval_seconds: int = 8
    amazon_challenge_backoff_base_seconds: int = 300
    amazon_challenge_backoff_max_seconds: int = 21600

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def validate_runtime_safety(self):
        if self.allow_live_publish and not self.database_url.lower().startswith(
            ("postgresql://", "postgresql+")
        ):
            raise ValueError("Live publishing requires PostgreSQL task locking.")
        if self.job_execution_timeout_seconds >= self.job_stale_after_seconds:
            raise ValueError("Job execution timeout must be shorter than the stale-job threshold.")
        if self.amazon_domain_min_interval_seconds < 1:
            raise ValueError("Amazon domain interval must be at least one second.")
        if self.amazon_challenge_backoff_base_seconds < 1:
            raise ValueError("Amazon challenge backoff must be at least one second.")
        if (
            self.amazon_challenge_backoff_max_seconds
            < self.amazon_challenge_backoff_base_seconds
        ):
            raise ValueError("Amazon challenge maximum backoff must not be shorter than its base.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
