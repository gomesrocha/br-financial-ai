from fastapi import APIRouter, HTTPException, status

from br_financial_ai.api.dependencies import YahooMarketClientDep
from br_financial_ai.clients.yahoo_market import (
    MarketDataNotFoundError,
    YahooMarketProviderError,
)
from br_financial_ai.domain.market import quote_price_change
from br_financial_ai.schemas.tracked import MarketQuoteSnapshotRead

router = APIRouter(
    prefix="/api/v1/market",
    tags=["market"],
)


@router.get(
    "/quote/{ticker}",
    response_model=MarketQuoteSnapshotRead,
)
async def get_market_quote(
    ticker: str,
    market_client: YahooMarketClientDep,
) -> MarketQuoteSnapshotRead:
    try:
        quote = await market_client.get_quote(ticker)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticker is invalid.",
        ) from exc
    except (YahooMarketProviderError, MarketDataNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data provider is unavailable.",
        ) from exc

    change = quote_price_change(quote)
    return MarketQuoteSnapshotRead(
        ticker=quote.ticker,
        symbol=quote.symbol,
        price=quote.price,
        previous_close=quote.previous_close,
        absolute_change=change.absolute,
        percentage_change=change.percentage,
        currency=quote.currency,
        timestamp=quote.timestamp,
    )
