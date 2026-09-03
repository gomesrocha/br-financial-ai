from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, UniqueConstraint, func, text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class NewsArticle(SQLModel, table=True):
    __tablename__ = "news_articles"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "provider",
            "canonical_url",
            name="uq_news_articles_provider_canonical_url",
        ),
        UniqueConstraint(
            "company_id",
            "content_hash",
            name="uq_news_articles_content_hash",
        ),
        Index(
            "uq_news_articles_provider_article_id",
            "company_id",
            "provider",
            "provider_article_id",
            unique=True,
            postgresql_where=text("provider_article_id IS NOT NULL"),
        ),
        Index(
            "ix_news_articles_company_published_at",
            "company_id",
            "published_at",
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

    provider: str = Field(
        max_length=50,
        index=True,
    )

    provider_article_id: str | None = Field(
        default=None,
        max_length=255,
    )

    title: str = Field(
        max_length=500,
    )

    summary: str | None = Field(
        default=None,
        max_length=4000,
    )

    publisher: str | None = Field(
        default=None,
        max_length=255,
    )

    url: str = Field(
        max_length=2048,
    )

    canonical_url: str = Field(
        max_length=2048,
    )

    published_at: datetime = Field(
        sa_type=DateTime(timezone=True),
    )

    fetched_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
        },
    )

    content_hash: str = Field(
        max_length=64,
    )
