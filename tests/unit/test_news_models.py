from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import SQLModel

from br_financial_ai.db.models import NewsArticle, NewsArticleSignal
from br_financial_ai.domain.news import NEWS_PROVIDER_YAHOO


def test_news_article_model() -> None:
    article = NewsArticle(
        company_id=1,
        provider=NEWS_PROVIDER_YAHOO,
        provider_article_id="yahoo-1",
        title="Petrobras anuncia resultado",
        summary="Resumo",
        publisher="Reuters",
        url="https://example.com/article?siteid=yhoof2",
        canonical_url="https://example.com/article",
        published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        content_hash="a" * 64,
    )

    assert article.id is None
    assert article.company_id == 1
    assert article.provider == "yahoo"
    assert article.published_at.tzinfo is not None


def test_news_article_signal_model() -> None:
    signal = NewsArticleSignal(
        news_article_id=17,
        model_provider="ollama",
        model_name="llama3.1",
        classifier_version=1,
        prompt_version="news-v1",
        relevance="HIGH",
        materiality="MEDIUM",
        sentiment="POSITIVE",
        company_specific=True,
        categories=["production"],
        confidence=Decimal("0.86"),
        rationale="Company production guidance.",
    )

    assert signal.id is None
    assert signal.news_article_id == 17
    assert signal.prompt_version == "news-v1"


def test_news_articles_table_registered() -> None:
    assert "news_articles" in SQLModel.metadata.tables
    assert "news_article_signals" in SQLModel.metadata.tables
