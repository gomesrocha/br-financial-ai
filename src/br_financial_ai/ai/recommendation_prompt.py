import json
from dataclasses import dataclass
from decimal import Decimal

from br_financial_ai.domain.analysis import RecommendationContext
from br_financial_ai.domain.recommendation import limitations_from_context


@dataclass(frozen=True, slots=True)
class RecommendationPromptContext:
    payload: dict[str, object]
    serialized: str

    @property
    def character_count(self) -> int:
        return len(self.serialized)


def build_recommendation_prompt_context(
    context: RecommendationContext,
) -> RecommendationPromptContext:
    signals = {item.article_id: item for item in context.news_signals}
    news: list[dict[str, object]] = []

    for item in context.recent_news:
        entry: dict[str, object] = {
            "id": item.article_id,
            "title": item.title,
            "publisher": item.publisher,
            "published_at": item.published_at.isoformat(),
        }
        if item.summary and item.summary != item.title:
            entry["summary"] = item.summary
        signal = signals.get(item.article_id)
        if signal is not None:
            entry["relevance"] = signal.relevance.value
            entry["materiality"] = signal.materiality.value
            entry["sentiment"] = signal.sentiment.value
            entry["company_specific"] = signal.company_specific
            entry["categories"] = list(signal.categories)
            if signal.rationale and signal.rationale != item.title:
                entry["rationale"] = signal.rationale
        news.append(entry)

    payload: dict[str, object] = {
        "ticker": context.ticker,
        "company_name": context.company_name,
        "financial_profile": context.financial_profile,
        "as_of": context.as_of.isoformat(),
        "financials": {
            "year": context.financials.year,
            "document_type": context.financials.document_type,
            "currency": context.financials.currency,
            "revenue": _decimal(context.financials.revenue),
            "gross_profit": _decimal(context.financials.gross_profit),
            "operating_result": _decimal(context.financials.operating_result),
            "net_income": _decimal(context.financials.net_income),
            "amount_scales": {
                "revenue": _amount_scales(context.financials.revenue),
                "gross_profit": _amount_scales(context.financials.gross_profit),
                "operating_result": _amount_scales(context.financials.operating_result),
                "net_income": _amount_scales(context.financials.net_income),
            },
        },
        "valuation": {
            "reference_year": context.valuation.reference_year,
            "gross_margin": _decimal(context.valuation.gross_margin),
            "operating_margin": _decimal(context.valuation.operating_margin),
            "net_margin": _decimal(context.valuation.net_margin),
            "price_to_sales": _decimal(context.valuation.price_to_sales),
            "price_to_earnings": _decimal(context.valuation.price_to_earnings),
        },
        "market_quote": {
            "symbol": context.market_quote.symbol,
            "price": _decimal(context.market_quote.price),
            "previous_close": _decimal(context.market_quote.previous_close),
            "currency": context.market_quote.currency,
            "market_cap": _decimal(context.market_quote.market_cap),
        },
        "price_change": {
            "absolute": _decimal(context.price_change.absolute),
            "percentage": _decimal(context.price_change.percentage),
        },
        "market_metrics": [
            {
                "period": item.period,
                "period_return": _decimal(item.period_return),
                "volatility": _decimal(item.volatility),
                "max_drawdown": _decimal(item.max_drawdown),
            }
            for item in context.market_metrics
        ],
        "news": news,
        "evidence": [
            {
                "source": item.source,
                "kind": item.kind,
                "reference": item.reference,
            }
            for item in context.evidence
        ],
        "unavailable": [
            {
                "section": item.section,
                "source": item.source,
                "reason": item.reason,
                "reference": item.reference,
            }
            for item in context.unavailable
        ],
        "limitations": list(limitations_from_context(context)),
    }
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return RecommendationPromptContext(payload=payload, serialized=serialized)


def prompt_from_context(context: RecommendationContext) -> str:
    compact = build_recommendation_prompt_context(context)
    return (
        "RecommendationContext JSON follows. Use these values as given.\n"
        f"{compact.serialized}"
    )


def _decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None

    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _amount_scales(value: Decimal | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {
        "million": _decimal(value / Decimal("1000000")),
        "billion": _decimal(value / Decimal("1000000000")),
    }
