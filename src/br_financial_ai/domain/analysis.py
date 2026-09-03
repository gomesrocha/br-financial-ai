from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from br_financial_ai.domain.market import (
    MarketPeriodMetrics,
    MarketQuote,
    PriceChange,
)
from br_financial_ai.domain.news_signals import NewsSignal
from br_financial_ai.domain.valuation import ValuationMetrics

CONTEXT_MARKET_PERIODS = ("1mo", "3mo", "1y")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    source: str
    kind: str
    reference: str


@dataclass(frozen=True, slots=True)
class UnavailableSection:
    section: str
    source: str
    reason: str
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class AnnualFinancials:
    """Annual DFP values in BRL units after CVM scale conversion."""

    ticker: str
    year: int
    document_type: str
    revenue: Decimal | None
    gross_profit: Decimal | None
    operating_result: Decimal | None
    net_income: Decimal | None
    currency: str


@dataclass(frozen=True, slots=True)
class NewsContextItem:
    article_id: int | None
    title: str
    publisher: str | None
    published_at: datetime
    url: str
    canonical_url: str
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class RecommendationContext:
    ticker: str
    company_name: str
    financial_profile: str
    as_of: datetime
    financials: AnnualFinancials
    valuation: ValuationMetrics
    market_quote: MarketQuote
    price_change: PriceChange
    market_metrics: tuple[MarketPeriodMetrics, ...]
    recent_news: tuple[NewsContextItem, ...]
    news_signals: tuple[NewsSignal, ...]
    evidence: tuple[EvidenceReference, ...]
    unavailable: tuple[UnavailableSection, ...]
