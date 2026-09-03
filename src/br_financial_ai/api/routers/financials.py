from fastapi import APIRouter, HTTPException, status

from br_financial_ai.api.dependencies import (
    FinancialQueryServiceDep,
)
from br_financial_ai.schemas.financial import (
    FinancialAccountRead,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    MetricUnsupportedForProfileError,
)

router = APIRouter(
    prefix="/financials",
    tags=["financials"],
)


@router.get(
    "/by-ticker/{ticker}/quarterly/{year}/{quarter}/accounts/{account_code}",
    response_model=FinancialAccountRead,
)
async def get_quarter_account(
    ticker: str,
    year: int,
    quarter: int,
    account_code: str,
    service: FinancialQueryServiceDep,
) -> FinancialAccountRead:
    try:
        item = await service.get_quarter_account(
            ticker=ticker,
            year=year,
            quarter=quarter,
            account_code=account_code,
        )

    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found.",
        )

    return FinancialAccountRead(
        ticker=ticker.strip().upper(),
        year=year,
        quarter=quarter,
        statement_type=item.statement_type,
        scope=item.scope,
        account_code=item.account_code,
        account_name=item.account_name,
        period_start=item.period_start,
        period_end=item.period_end,
        value=item.value,
        currency=item.currency,
        currency_scale=item.currency_scale,
    )


@router.get(
    "/by-ticker/{ticker}/quarterly/{year}/{quarter}/metrics/{metric_key}",
    response_model=FinancialAccountRead,
)
async def get_quarter_metric(
    ticker: str,
    year: int,
    quarter: int,
    metric_key: str,
    service: FinancialQueryServiceDep,
) -> FinancialAccountRead:
    try:
        item = await service.get_quarter_metric(
            ticker=ticker,
            year=year,
            quarter=quarter,
            metric_key=metric_key,
        )

    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except MetricUnsupportedForProfileError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial metric not found.",
        )

    return FinancialAccountRead(
        ticker=ticker.strip().upper(),
        year=year,
        quarter=quarter,
        statement_type=item.statement_type,
        scope=item.scope,
        account_code=item.account_code,
        account_name=item.account_name,
        period_start=item.period_start,
        period_end=item.period_end,
        value=item.value,
        currency=item.currency,
        currency_scale=item.currency_scale,
    )
