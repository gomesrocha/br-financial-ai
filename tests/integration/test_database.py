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


from br_financial_ai.db.models import Company, Security


def test_company_model() -> None:
    company = Company(
        cvm_code="TEST001",
        cnpj="12345678000199",
        legal_name="Empresa Teste S.A.",
        trade_name="Empresa Teste",
    )

    assert company.id is None
    assert company.cvm_code == "TEST001"
    assert company.cnpj == "12345678000199"
    assert company.active is True


def test_security_model() -> None:
    security = Security(
        company_id=1,
        ticker="TEST3",
        security_type="ON",
    )

    assert security.id is None
    assert security.company_id == 1
    assert security.ticker == "TEST3"
    assert security.security_type == "ON"
    assert security.active is True
