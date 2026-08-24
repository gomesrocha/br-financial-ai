from fastapi import APIRouter, HTTPException, status

from br_financial_ai.api.dependencies import CompanyQueryServiceDep
from br_financial_ai.schemas.company import CompanyRead

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


@router.get(
    "/by-ticker/{ticker}",
    response_model=CompanyRead,
)
async def get_company_by_ticker(
    ticker: str,
    service: CompanyQueryServiceDep,
) -> CompanyRead:
    company = await service.find_by_ticker(ticker)

    if company is None or company.id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    return CompanyRead(
        id=company.id,
        cvm_code=company.cvm_code,
        cnpj=company.cnpj,
        legal_name=company.legal_name,
        trade_name=company.trade_name,
        active=company.active,
    )
