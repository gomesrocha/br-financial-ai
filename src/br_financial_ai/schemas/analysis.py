from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

from br_financial_ai.domain.recommendation import (
    ANALYSIS_DISCLAIMER,
    RecommendationStance,
)


class AnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    news_limit: int = Field(default=10, ge=0, le=20)


class EvidenceRead(BaseModel):
    source: str
    kind: str
    reference: str


class RecommendationViewsRead(BaseModel):
    fundamentals: str
    valuation: str
    market: str
    news: str


class RecommendationRead(BaseModel):
    ticker: str
    stance: RecommendationStance
    confidence: Decimal
    summary: str
    views: RecommendationViewsRead
    positives: list[str]
    risks: list[str]
    limitations: list[str]
    evidence: list[EvidenceRead]
    as_of: datetime
    disclaimer: str = ANALYSIS_DISCLAIMER

    @field_serializer("confidence")
    def serialize_confidence(self, value: Decimal) -> str:
        return format(value, "f")


class UnavailableSectionRead(BaseModel):
    section: str
    source: str
    reason: str
    reference: str | None = None


class AnnualFinancialsRead(BaseModel):
    ticker: str
    year: int
    document_type: str
    revenue: Decimal | None
    gross_profit: Decimal | None
    operating_result: Decimal | None
    net_income: Decimal | None
    currency: str


class ValuationMetricsRead(BaseModel):
    ticker: str
    reference_year: int
    revenue: Decimal | None
    gross_profit: Decimal | None
    operating_result: Decimal | None
    net_income: Decimal | None
    gross_margin: Decimal | None
    operating_margin: Decimal | None
    net_margin: Decimal | None
    market_cap: Decimal | None
    price_to_sales: Decimal | None
    price_to_earnings: Decimal | None


class MarketQuoteRead(BaseModel):
    ticker: str
    symbol: str
    price: Decimal
    previous_close: Decimal | None
    currency: str
    timestamp: datetime
    market_cap: Decimal | None = None


class PriceChangeRead(BaseModel):
    absolute: Decimal | None
    percentage: Decimal | None


class PriceBarRead(BaseModel):
    ticker: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None = None


class MarketPeriodMetricsRead(BaseModel):
    period: str
    period_return: Decimal
    volatility: Decimal
    max_drawdown: Decimal


class NewsItemRead(BaseModel):
    article_id: int | None
    title: str
    publisher: str | None
    published_at: datetime
    url: str
    canonical_url: str
    summary: str | None = None


class NewsSignalRead(BaseModel):
    article_id: int | None
    relevance: str
    materiality: str
    sentiment: str
    company_specific: bool
    categories: list[str]
    confidence: Decimal
    rationale: str


class RecommendationContextRead(BaseModel):
    ticker: str
    company_name: str
    financial_profile: str
    as_of: datetime
    financials: AnnualFinancialsRead
    valuation: ValuationMetricsRead
    market_quote: MarketQuoteRead
    price_change: PriceChangeRead
    market_metrics: list[MarketPeriodMetricsRead]
    recent_news: list[NewsItemRead]
    news_signals: list[NewsSignalRead]
    evidence: list[EvidenceRead]
    unavailable: list[UnavailableSectionRead]
    disclaimer: str = ANALYSIS_DISCLAIMER
