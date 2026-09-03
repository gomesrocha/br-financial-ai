import unicodedata
from dataclasses import dataclass

from br_financial_ai.domain.financial_profile import (
    FinancialProfile,
)


@dataclass(frozen=True, slots=True)
class AccountSelector:
    statement_type: str
    account_code: str
    scope: str = "CONSOLIDATED"
    name_contains: tuple[str, ...] = ()
    name_excludes: tuple[str, ...] = ()

    def matches_account_name(self, account_name: str) -> bool:
        folded = fold_account_text(account_name)

        for token in self.name_contains:
            if fold_account_text(token) not in folded:
                return False

        for token in self.name_excludes:
            if fold_account_text(token) in folded:
                return False

        return True


@dataclass(frozen=True, slots=True)
class FinancialMetric:
    key: str
    label: str
    selectors: tuple[AccountSelector, ...]

    @property
    def statement_type(self) -> str:
        return self.selectors[0].statement_type

    @property
    def account_code(self) -> str:
        return self.selectors[0].account_code

    @property
    def scope(self) -> str:
        return self.selectors[0].scope


def fold_account_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in without_marks)
    return " ".join(cleaned.split())


def _dre(
    code: str,
    *,
    name_contains: tuple[str, ...] = (),
    name_excludes: tuple[str, ...] = (),
) -> AccountSelector:
    return AccountSelector(
        statement_type="DRE",
        account_code=code,
        name_contains=name_contains,
        name_excludes=name_excludes,
    )


def _metric(
    key: str,
    label: str,
    *selectors: AccountSelector,
) -> FinancialMetric:
    return FinancialMetric(
        key=key,
        label=label,
        selectors=selectors,
    )


NON_FINANCIAL_METRICS = {
    "revenue": _metric(
        "revenue",
        "Receita de venda de bens e/ou serviços",
        _dre("3.01"),
    ),
    "gross_profit": _metric(
        "gross_profit",
        "Resultado bruto",
        _dre("3.03"),
    ),
    "operating_result": _metric(
        "operating_result",
        "Resultado antes do resultado financeiro e tributos",
        _dre("3.05"),
    ),
    "profit_before_tax": _metric(
        "profit_before_tax",
        "Resultado antes dos tributos sobre o lucro",
        _dre("3.07"),
    ),
    "net_income": _metric(
        "net_income",
        "Lucro/Prejuízo consolidado do período",
        _dre("3.11"),
    ),
}

# Bank DRE codes 3.01/3.03 are intermediation, not industrial revenue or
# gross profit. 3.05 is profit before tax, not operating result. Net
# income is 3.11 when present (Bradesco) or 3.09 when the issuer
# collapses the chart and names that slot as consolidated period profit
# (Itaú). Prefer 3.11, then 3.09, and reject "antes das participações".
FINANCIAL_INSTITUTION_METRICS = {
    "net_income": _metric(
        "net_income",
        "Lucro/Prejuízo líquido consolidado do período",
        _dre(
            "3.11",
            name_contains=("consolidado", "periodo"),
            name_excludes=("participacoes",),
        ),
        _dre(
            "3.09",
            name_contains=("consolidado", "periodo"),
            name_excludes=("participacoes",),
        ),
    ),
    "profit_before_tax": _metric(
        "profit_before_tax",
        "Resultado antes dos tributos sobre o lucro",
        _dre("3.05", name_contains=("tributos",)),
    ),
    "financial_intermediation_revenue": _metric(
        "financial_intermediation_revenue",
        "Receitas de intermediação financeira",
        _dre("3.01", name_contains=("intermediacao",)),
    ),
    "financial_intermediation_result": _metric(
        "financial_intermediation_result",
        "Resultado bruto de intermediação financeira",
        _dre("3.03", name_contains=("intermediacao",)),
    ),
}

PROFILE_METRICS: dict[FinancialProfile, dict[str, FinancialMetric]] = {
    FinancialProfile.NON_FINANCIAL: NON_FINANCIAL_METRICS,
    FinancialProfile.FINANCIAL_INSTITUTION: FINANCIAL_INSTITUTION_METRICS,
}

ALL_METRIC_KEYS = frozenset(
    key for catalogue in PROFILE_METRICS.values() for key in catalogue
)

METRIC_ALIASES = {
    "gross_income": "gross_profit",
    "gross_result": "gross_profit",
    "lucro_bruto": "gross_profit",
    "resultado_bruto": "gross_profit",
    "operational_result": "operating_result",
    "operating_income": "operating_result",
    "operating_profit": "operating_result",
    "resultado_operacional": "operating_result",
    "net_profit": "net_income",
    "lucro_liquido": "net_income",
    "sales": "revenue",
    "receita": "revenue",
    "faturamento": "revenue",
}

CONTEXT_METRIC_KEYS = (
    "revenue",
    "gross_profit",
    "operating_result",
    "net_income",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "price_to_sales",
    "price_to_earnings",
)

_CONTEXT_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "gross_margin": ("revenue", "gross_profit"),
    "operating_margin": ("revenue", "operating_result"),
    "net_margin": ("revenue", "net_income"),
    "price_to_sales": ("revenue",),
    "price_to_earnings": ("net_income",),
}


def coerce_financial_profile(
    financial_profile: FinancialProfile | str,
) -> FinancialProfile:
    if isinstance(financial_profile, FinancialProfile):
        return financial_profile

    return FinancialProfile(financial_profile.strip().upper())


def normalize_metric_key(key: str) -> str:
    normalized = key.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in ALL_METRIC_KEYS:
        return normalized
    return METRIC_ALIASES.get(normalized, normalized)


def get_financial_metric(
    key: str,
    financial_profile: FinancialProfile | str = FinancialProfile.NON_FINANCIAL,
) -> FinancialMetric | None:
    profile = coerce_financial_profile(financial_profile)
    return PROFILE_METRICS[profile].get(normalize_metric_key(key))


def supports_metric(
    financial_profile: FinancialProfile | str,
    metric_key: str,
) -> bool:
    return get_financial_metric(metric_key, financial_profile) is not None


def list_supported_metrics(
    financial_profile: FinancialProfile | str,
) -> tuple[str, ...]:
    profile = coerce_financial_profile(financial_profile)
    return tuple(PROFILE_METRICS[profile])


def is_known_metric_key(key: str) -> bool:
    return normalize_metric_key(key) in ALL_METRIC_KEYS


def is_context_metric_supported(
    financial_profile: FinancialProfile | str,
    metric_key: str,
) -> bool:
    normalized = normalize_metric_key(metric_key)
    required = _CONTEXT_DEPENDENCIES.get(normalized)

    if required is None:
        return supports_metric(financial_profile, normalized)

    return all(supports_metric(financial_profile, item) for item in required)


def list_unsupported_context_metrics(
    financial_profile: FinancialProfile | str,
) -> tuple[str, ...]:
    return tuple(
        key
        for key in CONTEXT_METRIC_KEYS
        if not is_context_metric_supported(financial_profile, key)
    )
