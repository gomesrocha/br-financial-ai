from datetime import date
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.clients.cvm_financial import (
    CvmFinancialClient,
)
from br_financial_ai.db.models import Company
from br_financial_ai.repositories.company import (
    CompanyRepository,
)
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.services.financial_ingestion import (
    FinancialIngestionService,
)


def create_financial_archive(
    cvm_code: str = "099999",
    cnpj: str = "89.000.000/0001-01",
) -> bytes:
    buffer = BytesIO()

    dre = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;"
        "GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
        "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;"
        "DS_CONTA;VL_CONTA;ST_CONTA_FIXA\n"
        f"{cnpj};2025-12-31;1;"
        f"EMPRESA TESTE S.A.;{cvm_code};"
        "DF Consolidado - Demonstração do Resultado;"
        "REAL;MIL;ÚLTIMO;2025-01-01;2025-12-31;"
        "3.01;Receita;"
        "100000.0000000000;S\n"
    )

    bpa = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;"
        "GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
        "DT_FIM_EXERC;CD_CONTA;DS_CONTA;"
        "VL_CONTA;ST_CONTA_FIXA\n"
        f"{cnpj};2025-12-31;1;"
        f"EMPRESA TESTE S.A.;{cvm_code};"
        "DF Consolidado - Balanço Patrimonial Ativo;"
        "REAL;MIL;ÚLTIMO;2025-12-31;"
        "1;Ativo Total;"
        "500000.0000000000;S\n"
    )

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "dfp_cia_aberta_DRE_con_2025.csv",
            dre.encode("latin-1"),
        )

        archive.writestr(
            "dfp_cia_aberta_BPA_con_2025.csv",
            bpa.encode("latin-1"),
        )

    return buffer.getvalue()


@pytest.mark.asyncio
async def test_sync_financial_statements(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99999",
            cnpj="89000000000101",
            legal_name="EMPRESA TESTE S.A.",
            trade_name="EMPRESA TESTE",
        )
    )

    assert company.id is not None

    archive_content = create_financial_archive(
        cvm_code="099999",
        cnpj="89.000.000/0001-01",
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=archive_content,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = CvmFinancialClient(http_client)

        service = FinancialIngestionService(
            db_session,
            client,
        )

        result = await service.sync(
            cvm_code="99999",
            document_type="DFP",
            year=2025,
        )

    assert result.files_processed == 2
    assert result.filings_created == 1
    assert result.filings_skipped == 0
    assert result.items_created == 2
    assert result.items_skipped == 0

    filing_repository = FinancialFilingRepository(db_session)

    filing = await filing_repository.get_by_identity(
        company_id=company.id,
        document_type="DFP",
        reference_date=date(2025, 12, 31),
        version=1,
    )

    assert filing is not None
    assert filing.id is not None

    item_repository = FinancialStatementItemRepository(db_session)

    items = await item_repository.list_by_filing_id(filing.id)

    assert len(items) == 2

    assert {item.statement_type for item in items} == {
        "BPA",
        "DRE",
    }


@pytest.mark.asyncio
async def test_sync_financial_statements_is_idempotent(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)

    await company_repository.add(
        Company(
            cvm_code="99998",
            cnpj="89000000000102",
            legal_name="EMPRESA IDEMPOTENTE S.A.",
            trade_name="EMPRESA IDEMPOTENTE",
        )
    )

    archive_content = create_financial_archive(
        cvm_code="099998",
        cnpj="89.000.000/0001-02",
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=archive_content,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = CvmFinancialClient(http_client)

        service = FinancialIngestionService(
            db_session,
            client,
        )

        first = await service.sync(
            cvm_code="99998",
            document_type="DFP",
            year=2025,
        )

        second = await service.sync(
            cvm_code="99998",
            document_type="DFP",
            year=2025,
        )

    assert first.filings_created == 1
    assert first.items_created == 2

    assert second.filings_created == 0
    assert second.filings_skipped == 1
    assert second.items_created == 0
    assert second.items_skipped == 2
