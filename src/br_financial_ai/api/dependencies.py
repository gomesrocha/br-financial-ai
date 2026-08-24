from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.session import get_session
from br_financial_ai.services.company_query import CompanyQueryService

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_company_query_service(
    session: SessionDep,
) -> CompanyQueryService:
    return CompanyQueryService(session)


CompanyQueryServiceDep = Annotated[
    CompanyQueryService,
    Depends(get_company_query_service),
]
