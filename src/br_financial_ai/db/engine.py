from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from br_financial_ai.core.settings import get_settings

settings = get_settings()


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)
