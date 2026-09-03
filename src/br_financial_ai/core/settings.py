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
        "@localhost:5438/br_financial_ai"
    )

    llm_provider: str = "ollama"
    llm_model: str = "llama3.1"
    llm_temperature: float = 0

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    news_classification_concurrency: int = 3


def cors_origin_list(settings: Settings) -> list[str]:
    return [
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
