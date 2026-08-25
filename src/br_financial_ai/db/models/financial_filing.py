from datetime import UTC, date, datetime

from sqlalchemy import DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class FinancialFiling(SQLModel, table=True):
    __tablename__ = "financial_filings"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "document_type",
            "reference_date",
            "version",
            name="uq_financial_filings_identity",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    company_id: int = Field(
        foreign_key="companies.id",
        index=True,
    )

    document_type: str = Field(
        max_length=10,
    )

    reference_date: date

    version: int

    source_year: int

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
        },
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
        },
    )
