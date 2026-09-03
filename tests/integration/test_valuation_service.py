from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    Security,
)
from br_financial_ai.domain.market import MarketQuote
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.valuation import ValuationService

QUOTE = MarketQuote(
    ticker="FVAL3",
    symbol="FVAL3.SA",
    price=Decimal("10"),
    previous_close=Decimal("9"),
    currency="BRL",
    timestamp=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
    market_cap=Decimal("200000"),
)


async def _seed_annual_dre(
    session: AsyncSession,
    *,
    ticker: str,
    cvm_code: str,
    cnpj: str,
    values: dict[str, str],
    setor_ativ: str | None = None,
    accounts: dict[str, tuple[str, str]] | None = None,
) -> Company:
    company_repository = CompanyRepository(session)
    security_repository = SecurityRepository(session)
    filing_repository = FinancialFilingRepository(session)
    item_repository = FinancialStatementItemRepository(session)

    company = await company_repository.add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name="EMPRESA VALUATION S.A.",
            trade_name="VALUATION",
            setor_ativ=setor_ativ,
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker=ticker,
            isin=f"BR{ticker[:4]}ACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )

    assert filing.id is not None

    accounts = accounts or {
        "3.01": ("Receita", values.get("3.01")),
        "3.03": ("Resultado Bruto", values.get("3.03")),
        "3.05": ("Resultado operacional", values.get("3.05")),
        "3.11": ("Lucro", values.get("3.11")),
    }

    items = [
        FinancialStatementItem(
            filing_id=filing.id,
            statement_type="DRE",
            scope="CONSOLIDATED",
            exercise_order="ÚLTIMO",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            statement_column=None,
            account_code=code,
            account_name=name,
            value=Decimal(value),
            currency="REAL",
            currency_scale="MIL",
            fixed_account_status="S",
            source_group="DF Consolidado - DRE",
        )
        for code, (name, value) in accounts.items()
        if value is not None
    ]

    if items:
        await item_repository.add_all(items)

    return company


@pytest.mark.asyncio
async def test_valuation_normalizes_cvm_mil_before_ratios(
    db_session: AsyncSession,
) -> None:
    await _seed_annual_dre(
        db_session,
        ticker="FVAL3",
        cvm_code="99201",
        cnpj="92000000000201",
        values={
            "3.01": "100.0000000000",
            "3.03": "40.0000000000",
            "3.05": "20.0000000000",
            "3.11": "10.0000000000",
        },
    )

    service = ValuationService(db_session)
    metrics = await service.get_metrics("FVAL3", 2025, quote=QUOTE)

    assert metrics.revenue == Decimal("100000.0000000000")
    assert metrics.gross_profit == Decimal("40000.0000000000")
    assert metrics.operating_result == Decimal("20000.0000000000")
    assert metrics.net_income == Decimal("10000.0000000000")
    assert metrics.gross_margin == Decimal("0.4")
    assert metrics.operating_margin == Decimal("0.2")
    assert metrics.net_margin == Decimal("0.1")
    assert metrics.market_cap == Decimal("200000")
    assert metrics.price_to_sales == Decimal("2")
    assert metrics.price_to_earnings == Decimal("20")


@pytest.mark.asyncio
async def test_valuation_skips_negative_pe_from_persisted_loss(
    db_session: AsyncSession,
) -> None:
    await _seed_annual_dre(
        db_session,
        ticker="FVAL4",
        cvm_code="99202",
        cnpj="92000000000202",
        values={
            "3.01": "100.0000000000",
            "3.11": "-10.0000000000",
        },
    )

    quote = MarketQuote(
        ticker="FVAL4",
        symbol="FVAL4.SA",
        price=Decimal("10"),
        previous_close=Decimal("9"),
        currency="BRL",
        timestamp=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
        market_cap=Decimal("200000"),
    )
    service = ValuationService(db_session)
    metrics = await service.get_metrics("FVAL4", 2025, quote=quote)

    assert metrics.net_income == Decimal("-10000.0000000000")
    assert metrics.net_margin == Decimal("-0.1")
    assert metrics.price_to_earnings is None


@pytest.mark.asyncio
async def test_bank_pe_uses_positive_net_income(
    db_session: AsyncSession,
) -> None:
    await _seed_annual_dre(
        db_session,
        ticker="VITB4",
        cvm_code="99210",
        cnpj="92000000000210",
        values={},
        setor_ativ="Bancos",
        accounts={
            "3.09": (
                "Lucro/Prejuízo Consolidado do Período",
                "10.0000000000",
            ),
        },
    )

    quote = MarketQuote(
        ticker="VITB4",
        symbol="VITB4.SA",
        price=Decimal("10"),
        previous_close=Decimal("9"),
        currency="BRL",
        timestamp=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
        market_cap=Decimal("200000"),
    )
    metrics = await ValuationService(db_session).get_metrics(
        "VITB4",
        2025,
        quote=quote,
    )

    assert metrics.net_income == Decimal("10000.0000000000")
    assert metrics.revenue is None
    assert metrics.gross_profit is None
    assert metrics.gross_margin is None
    assert metrics.price_to_sales is None
    assert metrics.price_to_earnings == Decimal("20")


@pytest.mark.asyncio
async def test_bank_pe_skipped_when_net_income_non_positive(
    db_session: AsyncSession,
) -> None:
    await _seed_annual_dre(
        db_session,
        ticker="VBBD4",
        cvm_code="99211",
        cnpj="92000000000211",
        values={},
        setor_ativ="Bancos",
        accounts={
            "3.11": (
                "Lucro ou Prejuízo Líquido Consolidado do Período",
                "-10.0000000000",
            ),
        },
    )

    quote = MarketQuote(
        ticker="VBBD4",
        symbol="VBBD4.SA",
        price=Decimal("10"),
        previous_close=Decimal("9"),
        currency="BRL",
        timestamp=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
        market_cap=Decimal("200000"),
    )
    metrics = await ValuationService(db_session).get_metrics(
        "VBBD4",
        2025,
        quote=quote,
    )

    assert metrics.net_income == Decimal("-10000.0000000000")
    assert metrics.price_to_earnings is None
    assert metrics.gross_margin is None
