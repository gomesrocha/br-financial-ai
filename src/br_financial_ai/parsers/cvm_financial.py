import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO

from br_financial_ai.utils.identifiers import (
    normalize_cnpj,
    normalize_cvm_code,
)


@dataclass(frozen=True, slots=True)
class FinancialStatementRecord:
    document_type: str
    statement_type: str
    scope: str

    cvm_code: str
    cnpj: str
    company_name: str

    reference_date: date
    version: int

    currency: str
    currency_scale: str
    exercise_order: str

    period_start: date | None
    period_end: date

    account_code: str
    account_name: str
    value: Decimal

    fixed_account_status: str
    source_group: str


def decode_cvm_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Unable to decode CVM CSV.")


def parse_optional_date(value: str) -> date | None:
    normalized = value.strip()

    if not normalized:
        return None

    return date.fromisoformat(normalized)


class CvmFinancialStatementParser:
    def parse(
        self,
        content: bytes,
        *,
        document_type: str,
        statement_type: str,
        scope: str,
        cvm_code: str | None = None,
    ) -> list[FinancialStatementRecord]:
        text = decode_cvm_csv(content)

        reader = csv.DictReader(
            StringIO(text),
            delimiter=";",
        )

        normalized_cvm_code = (
            normalize_cvm_code(cvm_code) if cvm_code is not None else None
        )

        records: list[FinancialStatementRecord] = []

        for row in reader:
            row_cvm_code = normalize_cvm_code(row["CD_CVM"])

            if normalized_cvm_code is not None and row_cvm_code != normalized_cvm_code:
                continue

            records.append(
                FinancialStatementRecord(
                    document_type=document_type.strip().upper(),
                    statement_type=statement_type.strip().upper(),
                    scope=scope.strip().upper(),
                    cvm_code=row_cvm_code,
                    cnpj=normalize_cnpj(row["CNPJ_CIA"]),
                    company_name=row["DENOM_CIA"].strip(),
                    reference_date=date.fromisoformat(row["DT_REFER"].strip()),
                    version=int(row["VERSAO"]),
                    currency=row["MOEDA"].strip(),
                    currency_scale=row["ESCALA_MOEDA"].strip(),
                    exercise_order=row["ORDEM_EXERC"].strip(),
                    period_start=parse_optional_date(row["DT_INI_EXERC"]),
                    period_end=date.fromisoformat(row["DT_FIM_EXERC"].strip()),
                    account_code=row["CD_CONTA"].strip(),
                    account_name=row["DS_CONTA"].strip(),
                    value=Decimal(row["VL_CONTA"].strip()),
                    fixed_account_status=row["ST_CONTA_FIXA"].strip(),
                    source_group=row["GRUPO_DFP"].strip(),
                )
            )

        return records
