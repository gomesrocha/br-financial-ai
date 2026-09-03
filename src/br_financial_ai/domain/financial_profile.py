import unicodedata
from enum import StrEnum

METRIC_UNSUPPORTED_FOR_PROFILE = "METRIC_UNSUPPORTED_FOR_PROFILE"

# Official CVM cad_cia_aberta SETOR_ATIV values whose inspected DRE
# uses financial-institution (COSIF-style) semantics. This is not a
# market-sector taxonomy.
FINANCIAL_INSTITUTION_ACTIVITIES = frozenset(
    {
        "BANCOS",
    }
)


class FinancialProfile(StrEnum):
    NON_FINANCIAL = "NON_FINANCIAL"
    FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION"


def financial_profile_from_setor_ativ(
    setor_ativ: str | None,
) -> FinancialProfile:
    """Resolve accounting semantics from official CVM SETOR_ATIV.

    Unknown, missing, or currently uninspected activities map to
    NON_FINANCIAL. Tickers are not used.
    """

    if setor_ativ is None:
        return FinancialProfile.NON_FINANCIAL

    normalized = _normalize_activity(setor_ativ)
    if normalized in FINANCIAL_INSTITUTION_ACTIVITIES:
        return FinancialProfile.FINANCIAL_INSTITUTION

    return FinancialProfile.NON_FINANCIAL


def _normalize_activity(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(without_marks.upper().split())
