from datetime import UTC, datetime

from br_financial_ai.domain.news import news_content_hash
from br_financial_ai.utils.urls import canonicalize_url

TRACKED_URL = "https://www.barrons.com/articles/oil-stocks?siteid=yhoof2&yptr=yahoo"


def test_canonicalize_url_removes_yahoo_tracking_params() -> None:
    assert canonicalize_url(TRACKED_URL) == (
        "https://www.barrons.com/articles/oil-stocks"
    )


def test_canonicalize_url_removes_fragment() -> None:
    assert (
        canonicalize_url("https://example.com/article#section")
        == "https://example.com/article"
    )


def test_canonicalize_url_equivalent_tracked_urls() -> None:
    first = canonicalize_url("https://example.com/article?siteid=yhoof2&yptr=yahoo")
    second = canonicalize_url("HTTPS://EXAMPLE.COM/article?yptr=yahoo&siteid=other")

    assert first == second
    assert first == "https://example.com/article"


def test_canonicalize_url_preserves_meaningful_query_params() -> None:
    assert (
        canonicalize_url("https://example.com/article?page=2&siteid=yhoof2")
        == "https://example.com/article?page=2"
    )


def test_news_content_hash_is_stable() -> None:
    published_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    first = news_content_hash(
        title="Petrobras anuncia resultado",
        publisher="Reuters",
        published_at=published_at,
        canonical_url="https://example.com/article",
    )
    second = news_content_hash(
        title="Petrobras anuncia resultado",
        publisher="Reuters",
        published_at=published_at,
        canonical_url="https://example.com/article",
    )

    assert first == second
    assert len(first) == 64


def test_news_content_hash_uses_canonical_url() -> None:
    published_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    first = news_content_hash(
        title="Petrobras anuncia resultado",
        publisher="Reuters",
        published_at=published_at,
        canonical_url=canonicalize_url(TRACKED_URL),
    )
    second = news_content_hash(
        title="Petrobras anuncia resultado",
        publisher="Reuters",
        published_at=published_at,
        canonical_url="https://www.barrons.com/articles/oil-stocks",
    )

    assert first == second
