from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class FinancialStatementItem(SQLModel, table=True):
    __tablename__ = "financial_statement_items"

    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "statement_type",
            "scope",
            "exercise_order",
            "period_start",
            "period_end",
            "statement_column",
            "account_code",
            name="uq_financial_statement_items_identity",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    filing_id: int = Field(
        foreign_key="financial_filings.id",
        index=True,
    )

    statement_type: str = Field(
        max_length=20,
        index=True,
    )

    scope: str = Field(
        max_length=20,
    )

    exercise_order: str = Field(
        max_length=20,
    )

    period_start: date | None = None

    period_end: date

    statement_column: str | None = Field(
        default=None,
        max_length=255,
    )

    account_code: str = Field(
        max_length=50,
    )

    account_name: str = Field(
        max_length=500,
    )

    value: Decimal = Field(
        sa_type=Numeric(
            precision=30,
            scale=10,
        ),
    )

    currency: str = Field(
        max_length=20,
    )

    currency_scale: str = Field(
        max_length=20,
    )

    fixed_account_status: str = Field(
        max_length=5,
    )

    source_group: str = Field(
        max_length=255,
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
        },
    )
