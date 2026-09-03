"""add company news articles

Revision ID: 8ee102a9d576
Revises: 8c7b655c6a0e
Create Date: 2026-09-01 18:21:52.949873

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8ee102a9d576"
down_revision: str | Sequence[str] | None = "8c7b655c6a0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column(
            "provider_article_id",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "title",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sqlmodel.sql.sqltypes.AutoString(length=4000),
            nullable=True,
        ),
        sa.Column(
            "publisher",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column(
            "url",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=False,
        ),
        sa.Column(
            "canonical_url",
            sqlmodel.sql.sqltypes.AutoString(length=2048),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "content_hash",
            name="uq_news_articles_content_hash",
        ),
        sa.UniqueConstraint(
            "company_id",
            "provider",
            "canonical_url",
            name="uq_news_articles_provider_canonical_url",
        ),
    )
    op.create_index(
        op.f("ix_news_articles_company_id"),
        "news_articles",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_news_articles_company_published_at",
        "news_articles",
        ["company_id", "published_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_articles_provider"),
        "news_articles",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "uq_news_articles_provider_article_id",
        "news_articles",
        ["company_id", "provider", "provider_article_id"],
        unique=True,
        postgresql_where=sa.text("provider_article_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_news_articles_provider_article_id",
        table_name="news_articles",
        postgresql_where=sa.text("provider_article_id IS NOT NULL"),
    )
    op.drop_index(
        op.f("ix_news_articles_provider"),
        table_name="news_articles",
    )
    op.drop_index(
        "ix_news_articles_company_published_at",
        table_name="news_articles",
    )
    op.drop_index(
        op.f("ix_news_articles_company_id"),
        table_name="news_articles",
    )
    op.drop_table("news_articles")
