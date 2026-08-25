from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from br_financial_ai.db.models import (
    FinancialFiling,
    FinancialStatementItem,
)


def test_financial_filing_model() -> None:
    filing = FinancialFiling(
        company_id=1,
        document_type="DFP",
        reference_date=date(2025, 12, 31),
        version=1,
        source_year=2025,
    )

    assert filing.document_type == "DFP"
    assert filing.version == 1


def test_financial_statement_item_model() -> None:
    item = FinancialStatementItem(
        filing_id=1,
        statement_type="DRE",
        scope="CONSOLIDATED",
        exercise_order="ÚLTIMO",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        account_code="3.01",
        account_name="Receita de Venda de Bens e/ou Serviços",
        value=Decimal("497549000.0000000000"),
        currency="REAL",
        currency_scale="MIL",
        fixed_account_status="S",
        source_group="DF Consolidado - Demonstração do Resultado",
        statement_column=None,
    )

    assert item.account_code == "3.01"

    assert item.value == Decimal("497549000.0000000000")
    assert item.statement_column is None


def test_financial_tables_registered() -> None:
    assert "financial_filings" in SQLModel.metadata.tables

    assert "financial_statement_items" in SQLModel.metadata.tables
