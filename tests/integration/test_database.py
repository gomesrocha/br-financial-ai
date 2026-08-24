import pytest
from sqlalchemy import text

from br_financial_ai.db.engine import engine


@pytest.mark.asyncio
async def test_database_connection() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_database_name() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT current_database()"))

    assert result.scalar_one() == "br_financial_ai"


@pytest.mark.asyncio
async def test_pgvector_extension_is_available() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
        )

    assert result.scalar_one() == "0.8.6"
