from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Company(SQLModel, table=True):
    __tablename__ = "companies"

    __table_args__ = (
        UniqueConstraint(
            "cvm_code",
            name="uq_companies_cvm_code",
        ),
        UniqueConstraint(
            "cnpj",
            name="uq_companies_cnpj",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    cvm_code: str = Field(
        max_length=20,
        index=True,
    )

    cnpj: str = Field(
        max_length=14,
        index=True,
    )

    legal_name: str = Field(
        max_length=255,
    )

    trade_name: str = Field(
        max_length=255,
    )

    active: bool = Field(
        default=True,
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
