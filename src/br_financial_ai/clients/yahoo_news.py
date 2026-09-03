import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from br_financial_ai.clients.yahoo import to_yahoo_symbol
from br_financial_ai.domain.news import NewsArticleRecord

NewsFetcher = Callable[[str, int], Sequence[object]]


class YahooNewsProviderError(Exception):
    pass


def fetch_yahoo_news(symbol: str, count: int) -> Sequence[object]:
    from yfinance import Ticker

    return Ticker(symbol).get_news(count=count)


def parse_news_article(
    yahoo_symbol: str,
    article: object,
) -> NewsArticleRecord | None:
    """Return a normalized article, or None if it is skipped.

    An article is skipped when it is not a mapping, or when title,
    URL, or publication timestamp cannot be extracted.
    """
    if not isinstance(article, Mapping):
        return None

    content = article.get("content")
    if not isinstance(content, Mapping):
        content = {}

    title = _optional_text(content.get("title")) or _optional_text(article.get("title"))
    url = _extract_url(content, article)
    published_at = _extract_published_at(content, article)

    if title is None or url is None or published_at is None:
        return None

    summary = _optional_text(content.get("summary")) or _optional_text(
        article.get("summary")
    )
    publisher = _extract_publisher(content, article)
    provider_article_id = _optional_text(article.get("id")) or _optional_text(
        content.get("id")
    )

    return NewsArticleRecord(
        yahoo_symbol=yahoo_symbol,
        title=title,
        summary=summary,
        publisher=publisher,
        published_at=published_at,
        url=url,
        provider_article_id=provider_article_id,
    )


class YahooNewsClient:
    def __init__(
        self,
        fetch_news: NewsFetcher | None = None,
    ) -> None:
        self._fetch_news = fetch_news or fetch_yahoo_news

    async def get_company_news(
        self,
        ticker: str,
        *,
        limit: int = 10,
    ) -> list[NewsArticleRecord]:
        if limit < 1:
            raise ValueError("News limit must be at least 1.")

        symbol = to_yahoo_symbol(ticker)

        try:
            raw_items = await asyncio.to_thread(
                self._fetch_news,
                symbol,
                limit,
            )
        except YahooNewsProviderError:
            raise
        except Exception as exc:
            raise YahooNewsProviderError(
                f"Failed to fetch Yahoo news for {symbol}."
            ) from exc

        if raw_items is None:
            return []

        if not isinstance(raw_items, list | tuple):
            raise YahooNewsProviderError(f"Unexpected Yahoo news payload for {symbol}.")

        articles: list[NewsArticleRecord] = []

        for item in raw_items:
            record = parse_news_article(symbol, item)

            if record is not None:
                articles.append(record)

        return articles


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()

    return text or None


def _extract_publisher(
    content: Mapping[str, object],
    article: Mapping[str, object],
) -> str | None:
    provider = content.get("provider")

    if isinstance(provider, Mapping):
        publisher = _optional_text(provider.get("displayName"))

        if publisher is not None:
            return publisher

    return _optional_text(article.get("publisher"))


def _extract_url(
    content: Mapping[str, object],
    article: Mapping[str, object],
) -> str | None:
    for candidate in (
        content.get("canonicalUrl"),
        content.get("clickThroughUrl"),
        article.get("link"),
        article.get("url"),
    ):
        if isinstance(candidate, Mapping):
            url = _optional_text(candidate.get("url"))

            if url is not None:
                return url

        url = _optional_text(candidate)

        if url is not None:
            return url

    return None


def _extract_published_at(
    content: Mapping[str, object],
    article: Mapping[str, object],
) -> datetime | None:
    for candidate in (
        content.get("pubDate"),
        article.get("pubDate"),
        article.get("providerPublishTime"),
    ):
        parsed = _parse_datetime(candidate)

        if parsed is not None:
            return parsed

    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value

    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed
