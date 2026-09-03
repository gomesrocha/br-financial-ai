from dataclasses import dataclass
from io import BytesIO
from zipfile import ZipFile

import httpx

CVM_FINANCIAL_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"


@dataclass(frozen=True, slots=True)
class CvmFinancialArchive:
    document_type: str
    year: int
    content: bytes

    def file_names(self) -> list[str]:
        with ZipFile(BytesIO(self.content)) as archive:
            return sorted(archive.namelist())

    def read_file(
        self,
        file_name: str,
    ) -> bytes:
        with ZipFile(BytesIO(self.content)) as archive:
            return archive.read(file_name)


class CvmFinancialClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.http_client = http_client

    async def download_archive(
        self,
        document_type: str,
        year: int,
    ) -> CvmFinancialArchive:
        normalized_type = document_type.strip().upper()

        if normalized_type not in {"DFP", "ITR"}:
            raise ValueError(f"Unsupported document type: {document_type}")

        file_name = f"{normalized_type.lower()}_cia_aberta_{year}.zip"

        url = f"{CVM_FINANCIAL_BASE_URL}/{normalized_type}/DADOS/{file_name}"

        response = await self.http_client.get(url)
        response.raise_for_status()

        return CvmFinancialArchive(
            document_type=normalized_type,
            year=year,
            content=response.content,
        )
