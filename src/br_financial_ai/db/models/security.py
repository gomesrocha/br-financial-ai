from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Security(SQLModel, table=True):
    __tablename__ = "securities"

    __table_args__ = (
        UniqueConstraint(
            "ticker",
            name="uq_securities_ticker",
        ),
        CheckConstraint(
            "security_type IN ('ON', 'PN', 'UNIT', 'OTHER')",
            name="ck_securities_security_type",
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

    ticker: str = Field(
        max_length=12,
        index=True,
    )

    security_type: str = Field(
        max_length=20,
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
