from datetime import date
from decimal import Decimal

from br_financial_ai.parsers.cvm_financial import (
    CvmFinancialStatementParser,
)


def create_dre_csv() -> bytes:
    content = (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;"
        "GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
        "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;"
        "VL_CONTA;ST_CONTA_FIXA\n"
        "33.000.167/0001-01;2025-12-31;1;"
        "PETRÓLEO BRASILEIRO S.A. PETROBRAS;009512;"
        "DF Consolidado - Demonstração do Resultado;"
        "REAL;MIL;ÚLTIMO;2025-01-01;2025-12-31;"
        "3.01;Receita de Venda de Bens e/ou Serviços;"
        "490829000.0000000000;S\n"
        "60.746.948/0001-12;2025-12-31;1;"
        "BANCO BRADESCO S.A.;000906;"
        "DF Consolidado - Demonstração do Resultado;"
        "REAL;MIL;ÚLTIMO;2025-01-01;2025-12-31;"
        "3.01;Receitas da Intermediação Financeira;"
        "100000.0000000000;S\n"
    )

    return content.encode("latin-1")


def test_parse_petrobras_dre() -> None:
    parser = CvmFinancialStatementParser()

    records = parser.parse(
        create_dre_csv(),
        document_type="DFP",
        statement_type="DRE",
        scope="CONSOLIDATED",
        cvm_code="9512",
    )

    assert len(records) == 1

    record = records[0]

    assert record.document_type == "DFP"
    assert record.statement_type == "DRE"
    assert record.scope == "CONSOLIDATED"

    assert record.cvm_code == "9512"
    assert record.cnpj == "33000167000101"

    assert record.reference_date == date(2025, 12, 31)
    assert record.version == 1

    assert record.currency == "REAL"
    assert record.currency_scale == "MIL"
    assert record.exercise_order == "ÚLTIMO"

    assert record.period_start == date(2025, 1, 1)
    assert record.period_end == date(2025, 12, 31)

    assert record.account_code == "3.01"

    assert record.value == Decimal("490829000.0000000000")

    assert record.fixed_account_status == "S"


def test_parse_all_companies() -> None:
    parser = CvmFinancialStatementParser()

    records = parser.parse(
        create_dre_csv(),
        document_type="DFP",
        statement_type="DRE",
        scope="CONSOLIDATED",
    )

    assert len(records) == 2

    assert {record.cvm_code for record in records} == {
        "9512",
        "906",
    }
