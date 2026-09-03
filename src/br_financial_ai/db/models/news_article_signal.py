from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class NewsArticleSignal(SQLModel, table=True):
    __tablename__ = "news_article_signals"

    __table_args__ = (
        UniqueConstraint(
            "news_article_id",
            "model_provider",
            "model_name",
            "classifier_version",
            "prompt_version",
            name="uq_news_article_signals_article_classifier",
        ),
        CheckConstraint(
            "relevance IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_news_article_signals_relevance",
        ),
        CheckConstraint(
            "materiality IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_news_article_signals_materiality",
        ),
        CheckConstraint(
            "sentiment IN ('NEGATIVE', 'NEUTRAL', 'POSITIVE', 'MIXED')",
            name="ck_news_article_signals_sentiment",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    news_article_id: int = Field(
        foreign_key="news_articles.id",
        index=True,
    )

    model_provider: str = Field(
        max_length=50,
    )

    model_name: str = Field(
        max_length=100,
    )

    classifier_version: int = Field(
        sa_column=Column(Integer, nullable=False),
    )

    prompt_version: str = Field(
        max_length=32,
    )

    relevance: str = Field(
        max_length=16,
    )

    materiality: str = Field(
        max_length=16,
    )

    sentiment: str = Field(
        max_length=16,
    )

    company_specific: bool = Field(
        default=False,
    )

    categories: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )

    confidence: Decimal = Field(
        sa_type=Numeric(
            precision=10,
            scale=8,
        ),
    )

    rationale: str = Field(
        sa_column=Column(Text, nullable=False),
    )

    classified_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
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

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
