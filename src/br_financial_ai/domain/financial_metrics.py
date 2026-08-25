from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    key: str
    label: str
    statement_type: str
    account_code: str
    scope: str = "CONSOLIDATED"


FINANCIAL_METRICS = {
    "revenue": FinancialMetric(
        key="revenue",
        label="Receita",
        statement_type="DRE",
        account_code="3.01",
    ),
    "gross_profit": FinancialMetric(
        key="gross_profit",
        label="Resultado Bruto",
        statement_type="DRE",
        account_code="3.03",
    ),
    "operating_result": FinancialMetric(
        key="operating_result",
        label="Resultado antes do resultado financeiro e tributos",
        statement_type="DRE",
        account_code="3.05",
    ),
    "profit_before_tax": FinancialMetric(
        key="profit_before_tax",
        label="Resultado antes dos tributos sobre o lucro",
        statement_type="DRE",
        account_code="3.07",
    ),
    "net_income": FinancialMetric(
        key="net_income",
        label="Lucro/Prejuízo consolidado do período",
        statement_type="DRE",
        account_code="3.11",
    ),
}


def get_financial_metric(
    key: str,
) -> FinancialMetric | None:
    return FINANCIAL_METRICS.get(key.strip().lower())
