"""add news article signals

Revision ID: d4f8a1c2b390
Revises: c3a91f4b2e10
Create Date: 2026-09-02 16:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4f8a1c2b390"
down_revision: str | Sequence[str] | None = "c3a91f4b2e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_article_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("news_article_id", sa.Integer(), nullable=False),
        sa.Column(
            "model_provider",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column(
            "model_name",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=False,
        ),
        sa.Column("classifier_version", sa.Integer(), nullable=False),
        sa.Column(
            "prompt_version",
            sqlmodel.sql.sqltypes.AutoString(length=32),
            nullable=False,
        ),
        sa.Column(
            "relevance",
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
        ),
        sa.Column(
            "materiality",
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
        ),
        sa.Column(
            "sentiment",
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
        ),
        sa.Column("company_specific", sa.Boolean(), nullable=False),
        sa.Column(
            "categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint(
            "relevance IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_news_article_signals_relevance",
        ),
        sa.CheckConstraint(
            "materiality IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_news_article_signals_materiality",
        ),
        sa.CheckConstraint(
            "sentiment IN ('NEGATIVE', 'NEUTRAL', 'POSITIVE', 'MIXED')",
            name="ck_news_article_signals_sentiment",
        ),
        sa.ForeignKeyConstraint(
            ["news_article_id"],
            ["news_articles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "news_article_id",
            "model_provider",
            "model_name",
            "classifier_version",
            "prompt_version",
            name="uq_news_article_signals_article_classifier",
        ),
    )
    op.create_index(
        op.f("ix_news_article_signals_news_article_id"),
        "news_article_signals",
        ["news_article_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_news_article_signals_news_article_id"),
        table_name="news_article_signals",
    )
    op.drop_table("news_article_signals")
