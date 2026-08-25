from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.cvm_financial import (
    CvmFinancialClient,
)
from br_financial_ai.db.models import (
    FinancialFiling,
    FinancialStatementItem,
)
from br_financial_ai.parsers.cvm_financial import (
    CvmFinancialStatementParser,
    FinancialStatementRecord,
)
from br_financial_ai.repositories.company import (
    CompanyRepository,
)
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
)
from br_financial_ai.utils.identifiers import (
    normalize_cvm_code,
)

STATEMENT_TYPES = (
    "BPA",
    "BPP",
    "DFC_MD",
    "DFC_MI",
    "DMPL",
    "DRA",
    "DRE",
    "DVA",
)

STATEMENT_SCOPES = (
    ("con", "CONSOLIDATED"),
    ("ind", "INDIVIDUAL"),
)


@dataclass(frozen=True, slots=True)
class FinancialIngestionResult:
    cvm_code: str
    document_type: str
    year: int
    files_processed: int
    filings_created: int
    filings_skipped: int
    items_created: int
    items_skipped: int


class FinancialIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        client: CvmFinancialClient,
    ) -> None:
        self.session = session
        self.client = client

        self.company_repository = CompanyRepository(session)
        self.filing_repository = FinancialFilingRepository(session)
        self.item_repository = FinancialStatementItemRepository(session)

        self.parser = CvmFinancialStatementParser()

    async def sync(
        self,
        *,
        cvm_code: str,
        document_type: str,
        year: int,
    ) -> FinancialIngestionResult:
        normalized_cvm_code = normalize_cvm_code(cvm_code)
        normalized_document_type = document_type.strip().upper()

        company = await self.company_repository.get_by_cvm_code(normalized_cvm_code)

        if company is None or company.id is None:
            raise CompanyNotFoundError(
                f"Company with CVM code {normalized_cvm_code} not found."
            )

        archive = await self.client.download_archive(
            normalized_document_type,
            year,
        )

        available_files = set(archive.file_names())

        records: list[FinancialStatementRecord] = []
        files_processed = 0

        for statement_type in STATEMENT_TYPES:
            for scope_code, scope in STATEMENT_SCOPES:
                file_name = (
                    f"{normalized_document_type.lower()}"
                    f"_cia_aberta_{statement_type}_"
                    f"{scope_code}_{year}.csv"
                )

                if file_name not in available_files:
                    continue

                content = archive.read_file(file_name)

                parsed = self.parser.parse(
                    content,
                    document_type=normalized_document_type,
                    statement_type=statement_type,
                    scope=scope,
                    cvm_code=normalized_cvm_code,
                )

                records.extend(parsed)
                files_processed += 1

        grouped_records: dict[
            tuple[object, int],
            list[FinancialStatementRecord],
        ] = defaultdict(list)

        for record in records:
            key = (
                record.reference_date,
                record.version,
            )

            grouped_records[key].append(record)

        filings_created = 0
        filings_skipped = 0
        items_created = 0
        items_skipped = 0

        try:
            for (
                reference_date,
                version,
            ), filing_records in grouped_records.items():
                existing = await self.filing_repository.get_by_identity(
                    company_id=company.id,
                    document_type=normalized_document_type,
                    reference_date=reference_date,
                    version=version,
                )

                if existing is not None:
                    filings_skipped += 1
                    items_skipped += len(filing_records)
                    continue

                filing = await self.filing_repository.add(
                    FinancialFiling(
                        company_id=company.id,
                        document_type=normalized_document_type,
                        reference_date=reference_date,
                        version=version,
                        source_year=year,
                    )
                )

                assert filing.id is not None

                items = [
                    FinancialStatementItem(
                        filing_id=filing.id,
                        statement_type=record.statement_type,
                        scope=record.scope,
                        exercise_order=record.exercise_order,
                        period_start=record.period_start,
                        period_end=record.period_end,
                        statement_column=(record.statement_column),
                        account_code=record.account_code,
                        account_name=record.account_name,
                        value=record.value,
                        currency=record.currency,
                        currency_scale=record.currency_scale,
                        fixed_account_status=(record.fixed_account_status),
                        source_group=record.source_group,
                    )
                    for record in filing_records
                ]

                await self.item_repository.add_all(items)

                filings_created += 1
                items_created += len(items)

            await self.session.commit()

        except Exception:
            await self.session.rollback()
            raise

        return FinancialIngestionResult(
            cvm_code=normalized_cvm_code,
            document_type=normalized_document_type,
            year=year,
            files_processed=files_processed,
            filings_created=filings_created,
            filings_skipped=filings_skipped,
            items_created=items_created,
            items_skipped=items_skipped,
        )
