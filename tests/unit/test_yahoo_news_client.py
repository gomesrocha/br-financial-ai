from datetime import UTC, datetime

import pytest

from br_financial_ai.clients.yahoo_news import (
    YahooNewsClient,
    YahooNewsProviderError,
    parse_news_article,
    to_yahoo_symbol,
)
from br_financial_ai.domain.news import NewsArticleRecord

NESTED_ARTICLE = {
    "id": "article-1",
    "content": {
        "title": "Petrobras anuncia resultado trimestral",
        "summary": "Receita permanece resiliente no segundo trimestre.",
        "provider": {"displayName": "Reuters"},
        "pubDate": "2026-08-15T12:00:00Z",
        "canonicalUrl": {
            "url": "https://example.com/petr4-resultado",
        },
    },
}

FLAT_ARTICLE = {
    "title": "Petrobras paga dividendos",
    "summary": "Distribuicao anunciada ao mercado.",
    "publisher": "Valor Economico",
    "link": "https://example.com/petr4-dividendos",
    "providerPublishTime": 1755259200,
}


def test_to_yahoo_symbol_appends_sa_suffix() -> None:
    assert to_yahoo_symbol("PETR4") == "PETR4.SA"
    assert to_yahoo_symbol("PETR3") == "PETR3.SA"
    assert to_yahoo_symbol("VALE3") == "VALE3.SA"
    assert to_yahoo_symbol("BBDC4") == "BBDC4.SA"


def test_to_yahoo_symbol_normalizes_case_and_whitespace() -> None:
    assert to_yahoo_symbol("  petr4  ") == "PETR4.SA"


def test_to_yahoo_symbol_keeps_existing_yahoo_symbol() -> None:
    assert to_yahoo_symbol("PETR4.SA") == "PETR4.SA"
    assert to_yahoo_symbol(" petr4.sa ") == "PETR4.SA"


def test_to_yahoo_symbol_rejects_invalid_ticker() -> None:
    with pytest.raises(ValueError, match="Unsupported ticker"):
        to_yahoo_symbol("AAPL")

    with pytest.raises(ValueError, match="Unsupported ticker"):
        to_yahoo_symbol("PETR-DEB62")

    with pytest.raises(ValueError, match="Unsupported ticker"):
        to_yahoo_symbol("   ")


def test_parse_nested_yahoo_article() -> None:
    record = parse_news_article("PETR4.SA", NESTED_ARTICLE)

    assert record == NewsArticleRecord(
        yahoo_symbol="PETR4.SA",
        title="Petrobras anuncia resultado trimestral",
        summary="Receita permanece resiliente no segundo trimestre.",
        publisher="Reuters",
        published_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        url="https://example.com/petr4-resultado",
        provider_article_id="article-1",
    )


def test_parse_nested_article_extracts_publisher() -> None:
    record = parse_news_article("PETR4.SA", NESTED_ARTICLE)

    assert record is not None
    assert record.publisher == "Reuters"


def test_parse_nested_article_timestamp_is_timezone_aware() -> None:
    record = parse_news_article("PETR4.SA", NESTED_ARTICLE)

    assert record is not None
    assert record.published_at.tzinfo is not None
    assert record.published_at.utcoffset() is not None


def test_parse_nested_article_extracts_url() -> None:
    record = parse_news_article("PETR4.SA", NESTED_ARTICLE)

    assert record is not None
    assert record.url == "https://example.com/petr4-resultado"


def test_parse_flat_yahoo_article() -> None:
    record = parse_news_article("PETR4.SA", FLAT_ARTICLE)

    assert record is not None
    assert record.title == "Petrobras paga dividendos"
    assert record.publisher == "Valor Economico"
    assert record.url == "https://example.com/petr4-dividendos"
    assert record.published_at.tzinfo is not None


def test_parse_malformed_article_returns_none() -> None:
    assert parse_news_article("PETR4.SA", {"content": {"title": "Sem URL"}}) is None
    assert parse_news_article("PETR4.SA", "not-a-mapping") is None
    assert (
        parse_news_article(
            "PETR4.SA",
            {
                "content": {
                    "title": "Sem data",
                    "canonicalUrl": {"url": "https://example.com/x"},
                }
            },
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_company_news_returns_multiple_articles() -> None:
    second_article = {
        "id": "article-2",
        "content": {
            "title": "Analistas revisam Petrobras",
            "summary": None,
            "provider": {"displayName": "Bloomberg"},
            "pubDate": "2026-08-16T09:30:00Z",
            "canonicalUrl": {
                "url": "https://example.com/petr4-analistas",
            },
        },
    }

    def fetch_news(symbol: str, count: int) -> list[object]:
        assert symbol == "PETR4.SA"
        assert count == 10
        return [NESTED_ARTICLE, second_article]

    client = YahooNewsClient(fetch_news=fetch_news)

    articles = await client.get_company_news("PETR4")

    assert [article.title for article in articles] == [
        "Petrobras anuncia resultado trimestral",
        "Analistas revisam Petrobras",
    ]
    assert articles[1].publisher == "Bloomberg"


@pytest.mark.asyncio
async def test_get_company_news_skips_malformed_article() -> None:
    def fetch_news(symbol: str, count: int) -> list[object]:
        return [
            NESTED_ARTICLE,
            {"content": {"title": "Artigo incompleto"}},
            {"not": "enough"},
        ]

    client = YahooNewsClient(fetch_news=fetch_news)

    articles = await client.get_company_news("PETR4")

    assert len(articles) == 1
    assert articles[0].title == "Petrobras anuncia resultado trimestral"


@pytest.mark.asyncio
async def test_get_company_news_returns_empty_list() -> None:
    def fetch_news(symbol: str, count: int) -> list[object]:
        return []

    client = YahooNewsClient(fetch_news=fetch_news)

    articles = await client.get_company_news("PETR4")

    assert articles == []


@pytest.mark.asyncio
async def test_get_company_news_wraps_provider_failure() -> None:
    def fetch_news(symbol: str, count: int) -> list[object]:
        raise RuntimeError("yahoo unavailable")

    client = YahooNewsClient(fetch_news=fetch_news)

    with pytest.raises(
        YahooNewsProviderError,
        match="Failed to fetch Yahoo news for PETR4.SA",
    ):
        await client.get_company_news("  petr4  ")
