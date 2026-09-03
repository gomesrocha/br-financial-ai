from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.ai.orchestration import (
    execute_quarter_financial_metric_question,
)
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

QUESTION = "Qual foi a receita da ORCH4 no segundo trimestre de 2026?"

SEEDED_VALUE = Decimal("169000.0000000000")


@pytest.mark.asyncio
async def test_orchestration_executes_tool_against_database(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99401",
            cnpj="93000000000401",
            legal_name="PETROLEO BRASILEIRO S.A. PETROBRAS",
            trade_name="PETROBRAS",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="ORCH4",
            isin="BRORCHACNPR1",
            security_type="PN",
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
                account_name=("Receita de Venda de Bens e/ou Serviços"),
                value=SEEDED_VALUE,
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    tool = create_quarter_financial_metric_tool(db_session)

    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_quarter_financial_metric",
                "args": {
                    "ticker": "ORCH4",
                    "metric": "revenue",
                    "year": 2026,
                    "quarter": 2,
                },
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )

    bound = AsyncMock()
    bound.ainvoke = AsyncMock(return_value=message)
    model = Mock()
    model.bind_tools.return_value = bound

    result = await execute_quarter_financial_metric_question(
        model,
        tool,
        QUESTION,
    )

    assert result == {
        "ticker": "ORCH4",
        "metric": "revenue",
        "year": 2026,
        "quarter": 2,
        "account_code": "3.01",
        "account_name": ("Receita de Venda de Bens e/ou Serviços"),
        "value": str(SEEDED_VALUE),
        "currency": "REAL",
        "currency_scale": "MIL",
    }
