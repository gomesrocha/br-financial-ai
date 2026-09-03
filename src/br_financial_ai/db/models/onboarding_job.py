from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class CompanyOnboardingJob(SQLModel, table=True):
    __tablename__ = "company_onboarding_jobs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'READY', "
            "'READY_WITH_WARNINGS', 'FAILED')",
            name="ck_onboarding_jobs_status",
        ),
        CheckConstraint(
            "step IN ('RESOLVING_TICKER', 'SYNCING_COMPANY', "
            "'SYNCING_SECURITIES', 'SYNCING_FINANCIALS', "
            "'SYNCING_NEWS', 'TRACKING_COMPANY', 'COMPLETED')",
            name="ck_onboarding_jobs_step",
        ),
        Index(
            "uq_onboarding_jobs_active_ticker",
            "requested_ticker",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
        Index(
            "ix_onboarding_jobs_status",
            "status",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    requested_ticker: str = Field(
        max_length=12,
        index=True,
    )

    status: str = Field(
        max_length=32,
    )

    step: str = Field(
        max_length=32,
    )

    company_id: int | None = Field(
        default=None,
        foreign_key="companies.id",
        index=True,
    )

    tracked_company_id: int | None = Field(
        default=None,
        foreign_key="tracked_companies.id",
        index=True,
    )

    error_code: str | None = Field(
        default=None,
        max_length=64,
    )

    error_message: str | None = Field(
        default=None,
        max_length=500,
    )

    warnings: list[dict[str, str]] = Field(
        default_factory=list,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )

    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
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
