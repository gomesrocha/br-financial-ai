from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.ai.tools.financial import (
    create_quarter_financial_metric_tool,
)
from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    Security,
)
from br_financial_ai.repositories.company import (
    CompanyRepository,
)
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.security import (
    SecurityRepository,
)
from br_financial_ai.tools.financial import (
    get_quarter_financial_metric,
)


@pytest.mark.asyncio
async def test_get_quarter_financial_metric(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99201",
            cnpj="93000000000101",
            legal_name="EMPRESA FINANCIAL TOOL S.A.",
            trade_name="FINANCIAL TOOL",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FTOO3",
            isin="BRFTOOACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("169.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    result = await get_quarter_financial_metric(
        db_session,
        ticker="FTOO3",
        metric="revenue",
        year=2026,
        quarter=2,
    )

    assert result is not None

    assert result.ticker == "FTOO3"
    assert result.metric == "revenue"

    assert result.year == 2026
    assert result.quarter == 2

    assert result.account_code == "3.01"
    assert result.account_name == "Receita"

    assert result.value == Decimal("169.0000000000")

    assert result.currency == "REAL"
    assert result.currency_scale == "MIL"


@pytest.mark.asyncio
async def test_financial_metric_tool_normalizes_inputs(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99202",
            cnpj="93000000000102",
            legal_name="EMPRESA NORMALIZATION TOOL S.A.",
            trade_name="NORMALIZATION TOOL",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FNOR3",
            isin="BRFNORACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("250.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    result = await get_quarter_financial_metric(
        db_session,
        ticker="  fnor3  ",
        metric="  REVENUE  ",
        year=2026,
        quarter=2,
    )

    assert result is not None

    assert result.ticker == "FNOR3"
    assert result.metric == "revenue"

    assert result.account_code == "3.01"

    assert result.value == Decimal("250.0000000000")


@pytest.mark.asyncio
async def test_financial_metric_tool_returns_none_when_value_not_found(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99203",
            cnpj="93000000000103",
            legal_name="EMPRESA EMPTY TOOL S.A.",
            trade_name="EMPTY TOOL",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FEMP3",
            isin="BRFEMPACNOR1",
            security_type="ON",
        )
    )

    result = await get_quarter_financial_metric(
        db_session,
        ticker="FEMP3",
        metric="revenue",
        year=2026,
        quarter=2,
    )

    assert result is None


@pytest.mark.asyncio
async def test_financial_metric_tool_rejects_unknown_metric(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(
        ValueError,
        match="Unknown financial metric",
    ):
        await get_quarter_financial_metric(
            db_session,
            ticker="ANY3",
            metric="unknown_metric",
            year=2026,
            quarter=2,
        )


@pytest.mark.asyncio
async def test_financial_metric_tool_rejects_invalid_quarter(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99204",
            cnpj="93000000000104",
            legal_name="EMPRESA QUARTER TOOL S.A.",
            trade_name="QUARTER TOOL",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FQTR3",
            isin="BRFQTRACNOR1",
            security_type="ON",
        )
    )

    with pytest.raises(
        ValueError,
        match="Quarter must be between 1 and 4",
    ):
        await get_quarter_financial_metric(
            db_session,
            ticker="FQTR3",
            metric="revenue",
            year=2026,
            quarter=5,
        )


@pytest.mark.asyncio
async def test_langchain_financial_tool_ainvoke(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99205",
            cnpj="93000000000105",
            legal_name="EMPRESA LANGCHAIN TOOL S.A.",
            trade_name="LANGCHAIN TOOL",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FLNG3",
            isin="BRFLNGACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("321.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    tool = create_quarter_financial_metric_tool(db_session)

    result = await tool.ainvoke(
        {
            "ticker": "FLNG3",
            "metric": "revenue",
            "year": 2026,
            "quarter": 2,
        }
    )

    assert result is not None

    assert result["ticker"] == "FLNG3"
    assert result["metric"] == "revenue"

    assert result["year"] == 2026
    assert result["quarter"] == 2

    assert result["account_code"] == "3.01"
    assert result["account_name"] == "Receita"

    assert result["value"] == "321.0000000000"

    assert result["currency"] == "REAL"
    assert result["currency_scale"] == "MIL"
