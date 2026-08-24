import csv
from dataclasses import dataclass
from io import StringIO

import httpx

from br_financial_ai.utils.identifiers import (
    normalize_cnpj,
    normalize_cvm_code,
)

CVM_COMPANIES_URL = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
)


@dataclass(frozen=True, slots=True)
class CvmCompanyRecord:
    cvm_code: str
    cnpj: str
    legal_name: str
    trade_name: str
    status: str


class CvmClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.http_client = http_client

    async def get_companies(self) -> list[CvmCompanyRecord]:
        response = await self.http_client.get(CVM_COMPANIES_URL)
        response.raise_for_status()

        return parse_companies_csv(response.content)

    async def get_company_by_cvm_code(
        self,
        cvm_code: str,
    ) -> CvmCompanyRecord | None:
        normalized_code = normalize_cvm_code(cvm_code)

        companies = await self.get_companies()

        return next(
            (company for company in companies if company.cvm_code == normalized_code),
            None,
        )


def parse_companies_csv(content: bytes) -> list[CvmCompanyRecord]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = content.decode("latin-1")

    reader = csv.DictReader(
        StringIO(decoded),
        delimiter=";",
    )

    return [
        CvmCompanyRecord(
            cvm_code=normalize_cvm_code(row["CD_CVM"]),
            cnpj=normalize_cnpj(row["CNPJ_CIA"]),
            legal_name=row["DENOM_SOCIAL"].strip(),
            trade_name=row["DENOM_COMERC"].strip(),
            status=row["SIT"].strip(),
        )
        for row in reader
    ]
