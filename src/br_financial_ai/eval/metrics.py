from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import fmean


def ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("1")

    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))


def mean_ratio(flags: Sequence[bool]) -> Decimal:
    if not flags:
        return Decimal("0")

    return ratio(sum(1 for flag in flags if flag), len(flags))


def mean_or_none(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None

    return Decimal(str(fmean(values))).quantize(Decimal("0.0001"))


@dataclass(frozen=True, slots=True)
class ToolSelectionScores:
    tool_name_accuracy: Decimal
    argument_accuracy: Decimal
    exact_call_accuracy: Decimal
    cases: int


def tool_selection_scores(
    *,
    tool_name_matches: Sequence[bool],
    argument_matches: Sequence[bool],
    exact_matches: Sequence[bool],
) -> ToolSelectionScores:
    return ToolSelectionScores(
        tool_name_accuracy=mean_ratio(tool_name_matches),
        argument_accuracy=mean_ratio(argument_matches),
        exact_call_accuracy=mean_ratio(exact_matches),
        cases=len(exact_matches),
    )
