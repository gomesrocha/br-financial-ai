from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

NEWS_CATEGORIES = frozenset(
    {
        "earnings",
        "revenue",
        "profit",
        "production",
        "capex",
        "debt",
        "dividends",
        "management",
        "regulation",
        "legal",
        "governance",
        "merger_acquisition",
        "commodity_price",
        "oil_price",
        "interest_rates",
        "currency",
        "geopolitics",
        "macro",
        "operations",
        "accident",
        "environment",
    }
)


class NewsRelevance(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NewsMateriality(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NewsSentiment(StrEnum):
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"
    MIXED = "MIXED"


@dataclass(frozen=True, slots=True)
class NewsClassificationRequest:
    article_id: int | None
    ticker: str
    company_name: str
    title: str
    summary: str | None
    publisher: str | None


@dataclass(frozen=True, slots=True)
class NewsClassifierIdentity:
    model_provider: str
    model_name: str
    classifier_version: int
    prompt_version: str


@dataclass(frozen=True, slots=True)
class NewsSignal:
    article_id: int | None
    relevance: NewsRelevance
    materiality: NewsMateriality
    sentiment: NewsSentiment
    company_specific: bool
    categories: tuple[str, ...]
    confidence: Decimal
    rationale: str
