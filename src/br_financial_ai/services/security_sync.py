from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.b3 import B3Client
from br_financial_ai.db.models import Security
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.services.exceptions import CompanyNotFoundError


class SecuritySyncService:
    def __init__(
        self,
        session: AsyncSession,
        b3_client: B3Client,
    ) -> None:
        self.session = session
        self.b3_client = b3_client

        self.company_repository = CompanyRepository(session)
        self.security_repository = SecurityRepository(session)

    async def sync_by_cvm_code(
        self,
        cvm_code: str,
    ) -> list[Security]:
        company = await self.company_repository.get_by_cvm_code(
            cvm_code.strip(),
        )

        if company is None or company.id is None:
            raise CompanyNotFoundError(
                f"Company with CVM code {cvm_code} was not found."
            )

        b3_securities = await self.b3_client.get_company_securities(
            company.cvm_code,
        )

        synchronized: list[Security] = []

        for item in b3_securities:
            existing = await self.security_repository.get_by_ticker(
                item.ticker,
            )

            if existing is not None:
                synchronized.append(existing)
                continue

            security = Security(
                company_id=company.id,
                ticker=item.ticker,
                isin=item.isin,
                security_type=item.security_type,
            )

            security = await self.security_repository.add(security)

            synchronized.append(security)

        await self.session.commit()

        return synchronized
