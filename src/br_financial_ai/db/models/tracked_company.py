from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class TrackedCompany(SQLModel, table=True):
    __tablename__ = "tracked_companies"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            name="uq_tracked_companies_company_id",
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

    preferred_security_id: int = Field(
        foreign_key="securities.id",
        index=True,
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
