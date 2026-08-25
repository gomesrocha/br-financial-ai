from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest

from br_financial_ai.clients.cvm_financial import (
    CvmFinancialClient,
)


def create_financial_zip() -> bytes:
    buffer = BytesIO()

    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "dfp_cia_aberta_DRE_con_2025.csv",
            "CD_CVM;CD_CONTA;VL_CONTA\n9512;3.11;1000\n",
        )

        archive.writestr(
            "dfp_cia_aberta_BPA_con_2025.csv",
            "CD_CVM;CD_CONTA;VL_CONTA\n9512;1;5000\n",
        )

    return buffer.getvalue()


@pytest.mark.asyncio
async def test_download_dfp_archive() -> None:
    zip_content = create_financial_zip()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/DFP/DADOS/dfp_cia_aberta_2025.zip")

        return httpx.Response(
            200,
            content=zip_content,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as http_client:
        client = CvmFinancialClient(http_client)

        archive = await client.download_archive(
            "DFP",
            2025,
        )

    assert archive.document_type == "DFP"
    assert archive.year == 2025

    assert archive.file_names() == [
        "dfp_cia_aberta_BPA_con_2025.csv",
        "dfp_cia_aberta_DRE_con_2025.csv",
    ]


@pytest.mark.asyncio
async def test_reject_unsupported_document_type() -> None:
    async with httpx.AsyncClient() as http_client:
        client = CvmFinancialClient(http_client)

        with pytest.raises(ValueError):
            await client.download_archive(
                "INVALID",
                2025,
            )


def test_read_file_from_archive() -> None:
    zip_content = create_financial_zip()

    from br_financial_ai.clients.cvm_financial import (
        CvmFinancialArchive,
    )

    archive = CvmFinancialArchive(
        document_type="DFP",
        year=2025,
        content=zip_content,
    )

    content = archive.read_file("dfp_cia_aberta_DRE_con_2025.csv")

    assert content.decode() == ("CD_CVM;CD_CONTA;VL_CONTA\n9512;3.11;1000\n")
