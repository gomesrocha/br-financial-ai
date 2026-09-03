"""add tracked companies and onboarding jobs

Revision ID: c3a91f4b2e10
Revises: 8ee102a9d576
Create Date: 2026-09-02 15:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3a91f4b2e10"
down_revision: str | Sequence[str] | None = "8ee102a9d576"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracked_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("preferred_security_id", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["preferred_security_id"],
            ["securities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            name="uq_tracked_companies_company_id",
        ),
    )
    op.create_index(
        op.f("ix_tracked_companies_company_id"),
        "tracked_companies",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_companies_preferred_security_id"),
        "tracked_companies",
        ["preferred_security_id"],
        unique=False,
    )

    op.create_table(
        "company_onboarding_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "requested_ticker",
            sqlmodel.sql.sqltypes.AutoString(length=12),
            nullable=False,
        ),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column(
            "step",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("tracked_company_id", sa.Integer(), nullable=True),
        sa.Column(
            "error_code",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'READY', "
            "'READY_WITH_WARNINGS', 'FAILED')",
            name="ck_onboarding_jobs_status",
        ),
        sa.CheckConstraint(
            "step IN ('RESOLVING_TICKER', 'SYNCING_COMPANY', "
            "'SYNCING_SECURITIES', 'SYNCING_FINANCIALS', "
            "'SYNCING_NEWS', 'TRACKING_COMPANY', 'COMPLETED')",
            name="ck_onboarding_jobs_step",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tracked_company_id"],
            ["tracked_companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_onboarding_jobs_requested_ticker"),
        "company_onboarding_jobs",
        ["requested_ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_onboarding_jobs_company_id"),
        "company_onboarding_jobs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_onboarding_jobs_tracked_company_id"),
        "company_onboarding_jobs",
        ["tracked_company_id"],
        unique=False,
    )
    op.create_index(
        "ix_onboarding_jobs_status",
        "company_onboarding_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "uq_onboarding_jobs_active_ticker",
        "company_onboarding_jobs",
        ["requested_ticker"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_onboarding_jobs_active_ticker",
        table_name="company_onboarding_jobs",
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )
    op.drop_index(
        "ix_onboarding_jobs_status",
        table_name="company_onboarding_jobs",
    )
    op.drop_index(
        op.f("ix_company_onboarding_jobs_tracked_company_id"),
        table_name="company_onboarding_jobs",
    )
    op.drop_index(
        op.f("ix_company_onboarding_jobs_company_id"),
        table_name="company_onboarding_jobs",
    )
    op.drop_index(
        op.f("ix_company_onboarding_jobs_requested_ticker"),
        table_name="company_onboarding_jobs",
    )
    op.drop_table("company_onboarding_jobs")
    op.drop_index(
        op.f("ix_tracked_companies_preferred_security_id"),
        table_name="tracked_companies",
    )
    op.drop_index(
        op.f("ix_tracked_companies_company_id"),
        table_name="tracked_companies",
    )
    op.drop_table("tracked_companies")
