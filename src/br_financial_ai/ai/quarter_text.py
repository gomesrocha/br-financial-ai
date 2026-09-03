import re

from br_financial_ai.domain.financial_metrics import normalize_metric_key

_COMPACT_BR = re.compile(
    r"(?<![A-Za-z0-9])([1-4])\s*T\s*(20\d{2}|\d{2})(?!\d)",
    re.IGNORECASE,
)
_COMPACT_Q = re.compile(
    r"(?<![A-Za-z0-9])Q\s*([1-4])(?:\s*[/\-]\s*|\s+)(20\d{2}|\d{2})(?!\d)",
    re.IGNORECASE,
)
_PT_TRIMESTRE = re.compile(
    r"(primeiro|segundo|terceiro|quarto|1[oº°]?|2[oº°]?|3[oº°]?|4[oº°]?)"
    r"\s+trimestre(?:\s+de)?\s+(20\d{2}|\d{2})",
    re.IGNORECASE,
)
_PT_ORDINAL = {
    "primeiro": 1,
    "segundo": 2,
    "terceiro": 3,
    "quarto": 4,
    "1": 1,
    "1o": 1,
    "1º": 1,
    "1°": 1,
    "2": 2,
    "2o": 2,
    "2º": 2,
    "2°": 2,
    "3": 3,
    "3o": 3,
    "3º": 3,
    "3°": 3,
    "4": 4,
    "4o": 4,
    "4º": 4,
    "4°": 4,
}


def expand_two_digit_year(year: int) -> int:
    if 0 <= year <= 99:
        return 2000 + year
    return year


def parse_compact_year(token: str) -> int:
    return expand_two_digit_year(int(token))


def expand_quarter_expressions(question: str) -> str:
    """Rewrite common quarterly date forms without general-purpose NLP."""

    def replace_numeric(match: re.Match[str]) -> str:
        quarter = match.group(1)
        year = parse_compact_year(match.group(2))
        return f"quarter {quarter} of {year}"

    def replace_portuguese(match: re.Match[str]) -> str:
        ordinal = re.sub(r"[º°]", "o", match.group(1).strip().lower())
        quarter = _PT_ORDINAL.get(ordinal)
        if quarter is None:
            return match.group(0)
        year = parse_compact_year(match.group(2))
        return f"quarter {quarter} of {year}"

    expanded = _COMPACT_BR.sub(replace_numeric, question)
    expanded = _COMPACT_Q.sub(replace_numeric, expanded)
    return _PT_TRIMESTRE.sub(replace_portuguese, expanded)


def normalize_quarter_tool_args(args: dict[str, object]) -> dict[str, object]:
    normalized = dict(args)
    year = normalized.get("year")
    if isinstance(year, int):
        normalized["year"] = expand_two_digit_year(year)
    metric = normalized.get("metric")
    if isinstance(metric, str):
        normalized["metric"] = normalize_metric_key(metric)
    return normalized
