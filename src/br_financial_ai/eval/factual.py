import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from br_financial_ai.domain.analysis import RecommendationContext
from br_financial_ai.domain.recommendation import RecommendationResult

_CLAIM = re.compile(
    r"(?:R\$\s*)?(?<![A-Za-z])"
    r"([-+]?(?:"
    r"\d{1,3}(?:\.\d{3})+,\d+"
    r"|\d{1,3}(?:,\d{3})+\.\d+"
    r"|\d{1,3}(?:\.\d{3}){2,}"
    r"|\d{1,3}(?:,\d{3}){2,}"
    r"|\d+[.,]\d+"
    r"|\d+"
    r"))"
    r"(?:\s*%|\s*x)?",
    re.IGNORECASE,
)
_ISO_DATETIME = re.compile(
    r"\b\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b",
    re.IGNORECASE,
)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?|janeiro|fevereiro|mar[cç]o|abril|maio|"
    r"junho|julho|agosto|setembro|outubro|novembro|dezembro)"
)
_HUMAN_DATE = re.compile(
    rf"\b(?:\d{{1,2}}\s+(?:de\s+)?{_MONTH}\s+(?:de\s+)?\d{{4}}"
    rf"|{_MONTH}\s+\d{{1,2}},?\s+\d{{4}})\b",
    re.IGNORECASE,
)
_SLASH_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_CLOCK_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?\b")
_UNSUPPORTED_METRIC_VALUE = re.compile(
    r"\b(?:P\s*/\s*B|price[ -]?to[ -]?book|EV\s*/\s*EBITDA)"
    r"\s*(?:=|is|of|:)\s*[-+]?\d",
    re.IGNORECASE,
)
_UNSUPPORTED_METRIC_NAME = re.compile(
    r"\b(?:P\s*/\s*B|price[ -]?to[ -]?book|EV\s*/\s*EBITDA)\b",
    re.IGNORECASE,
)
_UNAVAILABLE_HINT = re.compile(
    r"(?:not supported|unsupported|unavailable|not available|omitted|"
    r"lack of support|not provided|not disclosed|absent from|"
    r"not in (?:the |this )?(?:supplied |provided )?context)",
    re.IGNORECASE,
)
_TWO_DP = Decimal("0.01")
_FOUR_DP = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class FactualConsistencyResult:
    checked_claims: int
    consistent_claims: int
    inconsistent_claims: tuple[str, ...]
    score: Decimal


def evaluate_factual_consistency(
    context: RecommendationContext,
    result: RecommendationResult,
) -> FactualConsistencyResult:
    authorized = _authorized_numbers(context)
    ignorable = _ignorable_values(result)
    inconsistent: list[str] = []
    consistent = 0

    for raw, value, is_percent in _extract_numeric_claims(
        "\n".join(_result_texts(result))
    ):
        candidates = _claim_candidates(value, is_percent=is_percent)
        if any(
            _is_ignorable(item) or _matches_values(item, ignorable)
            for item in candidates
        ):
            continue

        if any(_matches_authorized(item, authorized) for item in candidates):
            consistent += 1
        else:
            inconsistent.append(raw)

    checked = consistent + len(inconsistent)
    score = Decimal("1") if checked == 0 else (Decimal(consistent) / Decimal(checked))

    return FactualConsistencyResult(
        checked_claims=checked,
        consistent_claims=consistent,
        inconsistent_claims=tuple(inconsistent),
        score=score.quantize(Decimal("0.0001")) if checked else Decimal("1"),
    )


def _authorized_numbers(context: RecommendationContext) -> tuple[Decimal, ...]:
    values: list[Decimal | None] = [
        context.financials.revenue,
        context.financials.gross_profit,
        context.financials.operating_result,
        context.financials.net_income,
        context.valuation.gross_margin,
        context.valuation.operating_margin,
        context.valuation.net_margin,
        context.valuation.market_cap,
        context.valuation.price_to_sales,
        context.valuation.price_to_earnings,
        context.market_quote.price,
        context.market_quote.previous_close,
        context.market_quote.market_cap,
        context.price_change.absolute,
        context.price_change.percentage,
    ]

    for item in context.market_metrics:
        values.extend([item.period_return, item.volatility, item.max_drawdown])

    authorized: list[Decimal] = []

    for value in values:
        if value is None:
            continue
        authorized.extend(_authorized_variants(value))

    return tuple(authorized)


def _authorized_variants(value: Decimal) -> tuple[Decimal, ...]:
    variants = [
        value,
        abs(value),
        value * Decimal("100"),
        abs(value) * Decimal("100"),
        _quantize(value, _TWO_DP),
        _quantize(abs(value), _TWO_DP),
        _quantize(value, _FOUR_DP),
        _quantize(abs(value), _FOUR_DP),
    ]

    if abs(value) <= Decimal("2"):
        percent = abs(value) * Decimal("100")
        variants.append(_quantize(percent, Decimal("1")))
        variants.append(_quantize(percent, _TWO_DP))

    if abs(value) >= Decimal("1000000"):
        variants.extend(
            [
                value / Decimal("1000000"),
                value / Decimal("1000000000"),
                value / Decimal("1000000000000"),
                abs(value) / Decimal("1000000"),
                abs(value) / Decimal("1000000000"),
                abs(value) / Decimal("1000000000000"),
            ]
        )

    return tuple(variants)


def _ignorable_values(result: RecommendationResult) -> tuple[Decimal, ...]:
    return (
        result.confidence,
        result.confidence * Decimal("100"),
        _quantize(result.confidence, _TWO_DP),
        _quantize(result.confidence * Decimal("100"), _TWO_DP),
    )


def _result_texts(result: RecommendationResult) -> tuple[str, ...]:
    return (
        result.summary,
        result.fundamentals_view,
        result.valuation_view,
        result.market_view,
        result.news_view,
        *result.positives,
        *result.risks,
    )


def _mask_temporal_literals(text: str) -> str:
    """Remove dates and clock times so they are not parsed as financial claims.

    Recommendation text often echoes context `as_of` / `published_at` ISO
    timestamps or calendar dates. Those values are metadata, not P&L numbers.
    """

    masked = _ISO_DATETIME.sub(" ", text)
    masked = _HUMAN_DATE.sub(" ", masked)
    masked = _SLASH_DATE.sub(" ", masked)
    return _CLOCK_TIME.sub(" ", masked)


def _extract_numeric_claims(text: str) -> list[tuple[str, Decimal, bool]]:
    claims: list[tuple[str, Decimal, bool]] = []

    for match in _CLAIM.finditer(_mask_temporal_literals(text)):
        raw = match.group(0)
        parsed = _parse_number(match.group(1))
        if parsed is None:
            continue
        is_percent = "%" in raw
        claims.append((raw.strip(), parsed, is_percent))

    return claims


def _parse_number(raw: str) -> Decimal | None:
    normalized = raw.replace("+", "")

    if normalized.count(".") > 1 and "," not in normalized:
        normalized = normalized.replace(".", "")
    elif normalized.count(",") > 1 and "." not in normalized:
        normalized = normalized.replace(",", "")
    elif "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        decimal_digits = len(normalized.rsplit(",", 1)[1])
        if decimal_digits in {1, 2}:
            normalized = normalized.replace(".", "").replace(",", ".")
        elif decimal_digits == 3 and normalized.count(",") >= 1:
            normalized = normalized.replace(".", "").replace(",", "")
        else:
            normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _claim_candidates(value: Decimal, *, is_percent: bool) -> tuple[Decimal, ...]:
    candidates = [
        value,
        abs(value),
        _quantize(value, _TWO_DP),
        _quantize(abs(value), _TWO_DP),
    ]
    if is_percent:
        ratio = value / Decimal("100")
        candidates.extend([ratio, abs(ratio), _quantize(ratio, _FOUR_DP)])
    return tuple(candidates)


def _is_ignorable(value: Decimal) -> bool:
    if value.copy_abs() in {Decimal("0"), Decimal("1")}:
        return True

    as_int = int(value)
    if value == as_int and 1900 <= as_int <= 2100:
        return True

    if value == as_int and 0 <= as_int <= 4:
        return True

    return False


def _matches_values(value: Decimal, authorized: tuple[Decimal, ...]) -> bool:
    return _matches_authorized(value, authorized)


def _matches_authorized(value: Decimal, authorized: tuple[Decimal, ...]) -> bool:
    for candidate in authorized:
        if candidate == 0:
            if value == 0:
                return True
            continue

        difference = abs(value - candidate)
        relative = difference / abs(candidate)
        if relative <= Decimal("0.005"):
            return True

        if abs(candidate) >= Decimal("1") and (
            difference <= Decimal("0.05")
            or _quantize(value, _TWO_DP) == _quantize(candidate, _TWO_DP)
        ):
            return True

    return False


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def mentions_unsupported_valuation(text: str) -> tuple[str, ...]:
    found: set[str] = set()
    for match in _UNSUPPORTED_METRIC_VALUE.finditer(text):
        found.add(match.group(0))
    for match in _UNSUPPORTED_METRIC_NAME.finditer(text):
        if _UNAVAILABLE_HINT.search(_sentence_at(text, match.start())):
            continue
        found.add(match.group(0))
    return tuple(sorted(found))


def _sentence_at(text: str, index: int) -> str:
    start = index
    while start > 0 and text[start - 1] not in ".\n!?":
        start -= 1
    end = index
    while end < len(text) and text[end] not in ".\n!?":
        end += 1
    return text[start:end]
