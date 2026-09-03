from decimal import Decimal

import pytest

from br_financial_ai.clients.yahoo_market import YahooMarketClient
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.services.analysis_context import (
    AnalysisContextService,
)
from br_financial_ai.services.exceptions import CompanyNotFoundError

pytestmark = [
    pytest.mark.eval,
    pytest.mark.external,
    pytest.mark.ollama,
    pytest.mark.yahoo,
    pytest.mark.slow,
]


@pytest.mark.asyncio
async def test_live_recommendation_context_spike_for_petr4() -> None:
    async with async_session_factory() as session:
        service = AnalysisContextService(
            session,
            YahooMarketClient(),
        )

        try:
            context = await service.build_recommendation_context(
                "PETR4",
                news_limit=5,
            )
        except CompanyNotFoundError:
            pytest.skip("PETR4 is not present in the local database.")

        assert context.ticker == "PETR4"
        assert context.market_quote.price > Decimal("0")
        assert context.as_of.tzinfo is not None
        assert context.financials.currency == "BRL"
        assert context.valuation.ticker == "PETR4"
        print(context.company_name)
        print(context.valuation)
        print(context.market_metrics)
        print(context.news_signals)
        print(context.unavailable)
