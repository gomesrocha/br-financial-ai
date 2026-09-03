from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
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


@pytest.mark.asyncio
async def test_financial_filing_repository(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="FIN001",
            cnpj="88000000000101",
            legal_name="EMPRESA FINANCEIRA TESTE S.A.",
            trade_name="FIN TESTE",
        )
    )

    assert company.id is not None

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

    found = await filing_repository.get_by_identity(
        company_id=company.id,
        document_type="dfp",
        reference_date=date(2025, 12, 31),
        version=1,
    )

    assert found is not None
    assert found.id == filing.id
    assert found.document_type == "DFP"


@pytest.mark.asyncio
async def test_financial_statement_item_repository(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="FIN002",
            cnpj="88000000000102",
            legal_name="EMPRESA FINANCEIRA ITEM S.A.",
            trade_name="FIN ITEM",
        )
    )

    assert company.id is not None

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

    items = [
        FinancialStatementItem(
            filing_id=filing.id,
            statement_type="DRE",
            scope="CONSOLIDATED",
            exercise_order="ÚLTIMO",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            statement_column=None,
            account_code="3.01",
            account_name="Receita",
            value=Decimal("100000.0000000000"),
            currency="REAL",
            currency_scale="MIL",
            fixed_account_status="S",
            source_group=("DF Consolidado - Demonstração do Resultado"),
        ),
        FinancialStatementItem(
            filing_id=filing.id,
            statement_type="DRE",
            scope="CONSOLIDATED",
            exercise_order="ÚLTIMO",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            statement_column=None,
            account_code="3.02",
            account_name="Custos",
            value=Decimal("-50000.0000000000"),
            currency="REAL",
            currency_scale="MIL",
            fixed_account_status="S",
            source_group=("DF Consolidado - Demonstração do Resultado"),
        ),
    ]

    await item_repository.add_all(items)

    saved = await item_repository.list_by_filing_id(filing.id)

    assert len(saved) == 2

    assert {item.account_code for item in saved} == {
        "3.01",
        "3.02",
    }
