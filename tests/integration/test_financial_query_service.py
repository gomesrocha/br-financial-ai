from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)


@pytest.mark.asyncio
async def test_get_second_quarter_uses_isolated_period(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99123",
            cnpj="91000000000101",
            legal_name="EMPRESA QUERY S.A.",
            trade_name="EMPRESA QUERY",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FQRY3",
            isin="BRFQRYACNOR1",
            security_type="ON",
        )
    )

    first_quarter_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 3, 31),
            version=1,
            source_year=2026,
        )
    )

    second_quarter_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert first_quarter_filing.id is not None
    assert second_quarter_filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=first_quarter_filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("123.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            ),
            FinancialStatementItem(
                filing_id=second_quarter_filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("292.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            ),
            FinancialStatementItem(
                filing_id=second_quarter_filing.id,
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
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_quarter_account(
        ticker="fqry3",
        year=2026,
        quarter=2,
        account_code="3.01",
    )

    assert result is not None

    assert result.period_start == date(2026, 4, 1)
    assert result.period_end == date(2026, 6, 30)

    assert result.value == Decimal("169.0000000000")


@pytest.mark.asyncio
async def test_get_quarter_account_uses_latest_version(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99124",
            cnpj="91000000000102",
            legal_name="EMPRESA VERSIONADA S.A.",
            trade_name="EMPRESA VERSIONADA",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FVRS3",
            isin="BRFVRSACNOR1",
            security_type="ON",
        )
    )

    filing_v1 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    filing_v2 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=2,
            source_year=2026,
        )
    )

    assert filing_v1.id is not None
    assert filing_v2.id is not None

    common = {
        "statement_type": "DRE",
        "scope": "CONSOLIDATED",
        "exercise_order": "ÚLTIMO",
        "period_start": date(2026, 4, 1),
        "period_end": date(2026, 6, 30),
        "statement_column": None,
        "account_code": "3.01",
        "account_name": "Receita",
        "currency": "REAL",
        "currency_scale": "MIL",
        "fixed_account_status": "S",
        "source_group": "DF Consolidado - DRE",
    }

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing_v1.id,
                value=Decimal("160.0000000000"),
                **common,
            ),
            FinancialStatementItem(
                filing_id=filing_v2.id,
                value=Decimal("169.0000000000"),
                **common,
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_quarter_account(
        ticker="FVRS3",
        year=2026,
        quarter=2,
        account_code="3.01",
    )

    assert result is not None
    assert result.filing_id == filing_v2.id

    assert result.value == Decimal("169.0000000000")
