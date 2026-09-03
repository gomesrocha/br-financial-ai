import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

NEWS_PROVIDER_YAHOO = "yahoo"


@dataclass(frozen=True, slots=True)
class NewsArticleRecord:
    yahoo_symbol: str
    title: str
    summary: str | None
    publisher: str | None
    published_at: datetime
    url: str
    provider_article_id: str | None = None


def news_content_hash(
    *,
    title: str,
    publisher: str | None,
    published_at: datetime,
    canonical_url: str,
) -> str:
    timestamp = published_at

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    payload = "\n".join(
        [
            title.strip(),
            (publisher or "").strip(),
            timestamp.astimezone(UTC).isoformat(),
            canonical_url.strip(),
        ]
    )

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
