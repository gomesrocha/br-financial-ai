from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "BR Financial AI"
    app_environment: str = "local"

    database_url: str = (
        "postgresql+psycopg://"
        "br_financial_ai:br_financial_ai"
        "@localhost:5432/br_financial_ai"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
