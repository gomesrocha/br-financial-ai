from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, Security
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.schemas.company import CompanyCreate
from br_financial_ai.services.exceptions import (
    CompanyAlreadyExistsError,
    SecurityAlreadyExistsError,
)


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.company_repository = CompanyRepository(session)
        self.security_repository = SecurityRepository(session)

    async def create_company(
        self,
        data: CompanyCreate,
    ) -> Company:
        existing_by_cvm_code = await self.company_repository.get_by_cvm_code(
            data.cvm_code,
        )

        if existing_by_cvm_code is not None:
            raise CompanyAlreadyExistsError(
                f"Company with CVM code {data.cvm_code} already exists."
            )

        existing_by_cnpj = await self.company_repository.get_by_cnpj(
            data.cnpj,
        )

        if existing_by_cnpj is not None:
            raise CompanyAlreadyExistsError(
                f"Company with CNPJ {data.cnpj} already exists."
            )

        for security_data in data.securities:
            existing_security = await self.security_repository.get_by_ticker(
                security_data.ticker,
            )

            if existing_security is not None:
                raise SecurityAlreadyExistsError(
                    f"Security {security_data.ticker} already exists."
                )

        company = Company(
            cvm_code=data.cvm_code.strip(),
            cnpj=data.cnpj.strip(),
            legal_name=data.legal_name.strip(),
            trade_name=data.trade_name.strip(),
        )

        company = await self.company_repository.add(company)

        if company.id is None:
            raise RuntimeError("Company ID was not generated.")

        for security_data in data.securities:
            security = Security(
                company_id=company.id,
                ticker=security_data.ticker.strip().upper(),
                security_type=security_data.security_type.strip().upper(),
            )

            await self.security_repository.add(security)

        await self.session.commit()

        return company
