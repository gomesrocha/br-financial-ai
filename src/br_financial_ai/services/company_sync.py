from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.db.models import Company
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.schemas.company import CompanyCreate
from br_financial_ai.services.company import CompanyService
from br_financial_ai.services.exceptions import CvmCompanyNotFoundError


class CompanySyncService:
    def __init__(
        self,
        session: AsyncSession,
        cvm_client: CvmClient,
    ) -> None:
        self.company_repository = CompanyRepository(session)
        self.company_service = CompanyService(session)
        self.cvm_client = cvm_client

    async def sync_by_cvm_code(
        self,
        cvm_code: str,
    ) -> Company:
        existing_company = await self.company_repository.get_by_cvm_code(
            cvm_code.strip(),
        )

        if existing_company is not None:
            return existing_company

        cvm_company = await self.cvm_client.get_company_by_cvm_code(
            cvm_code,
        )

        if cvm_company is None:
            raise CvmCompanyNotFoundError(
                f"Company with CVM code {cvm_code} was not found."
            )

        company_data = CompanyCreate(
            cvm_code=cvm_company.cvm_code,
            cnpj=cvm_company.cnpj,
            legal_name=cvm_company.legal_name,
            trade_name=cvm_company.trade_name,
            active=cvm_company.status.upper() == "ATIVO",
        )

        return await self.company_service.create_company(
            company_data,
        )
