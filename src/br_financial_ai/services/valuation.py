from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import FinancialStatementItem
from br_financial_ai.domain.financial_metrics import (
    supports_metric,
)
from br_financial_ai.domain.market import MarketQuote
from br_financial_ai.domain.valuation import (
    VALUATION_METRIC_KEYS,
    AnnualAmounts,
    ValuationMetrics,
    compute_valuation_metrics,
    cvm_amount_to_brl,
)
from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)


def statement_item_to_brl(
    item: FinancialStatementItem | None,
) -> Decimal | None:
    if item is None:
        return None

    return cvm_amount_to_brl(item.value, item.currency_scale)


class ValuationService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.financial_query_service = FinancialQueryService(session)

    async def get_annual_amounts(
        self,
        ticker: str,
        year: int,
    ) -> AnnualAmounts:
        profile = await self.financial_query_service.resolve_financial_profile(
            ticker,
        )
        amounts: dict[str, Decimal | None] = {}

        for key in VALUATION_METRIC_KEYS:
            if not supports_metric(profile, key):
                amounts[key] = None
                continue

            item = await self.financial_query_service.get_annual_metric(
                ticker,
                year,
                key,
            )
            amounts[key] = statement_item_to_brl(item)

        return AnnualAmounts(
            revenue=amounts["revenue"],
            gross_profit=amounts["gross_profit"],
            operating_result=amounts["operating_result"],
            net_income=amounts["net_income"],
        )

    async def get_metrics(
        self,
        ticker: str,
        year: int,
        *,
        quote: MarketQuote,
    ) -> ValuationMetrics:
        amounts = await self.get_annual_amounts(ticker, year)

        return compute_valuation_metrics(
            ticker=ticker,
            reference_year=year,
            amounts=amounts,
            market_cap=quote.market_cap,
            quote_currency=quote.currency,
        )
