from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from br_financial_ai.clients.yahoo import to_b3_ticker

ONBOARDING_NEWS_LIMIT = 10

ACTIVE_ONBOARDING_STATUSES = frozenset({"PENDING", "RUNNING"})
SUCCESS_ONBOARDING_STATUSES = frozenset({"READY", "READY_WITH_WARNINGS"})


class OnboardingStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    FAILED = "FAILED"


class OnboardingStep(StrEnum):
    RESOLVING_TICKER = "RESOLVING_TICKER"
    SYNCING_COMPANY = "SYNCING_COMPANY"
    SYNCING_SECURITIES = "SYNCING_SECURITIES"
    SYNCING_FINANCIALS = "SYNCING_FINANCIALS"
    SYNCING_NEWS = "SYNCING_NEWS"
    TRACKING_COMPANY = "TRACKING_COMPANY"
    COMPLETED = "COMPLETED"


class OnboardingWarningCode(StrEnum):
    DFP_UNAVAILABLE = "DFP_UNAVAILABLE"
    ITR_UNAVAILABLE = "ITR_UNAVAILABLE"
    NEWS_UNAVAILABLE = "NEWS_UNAVAILABLE"
    NEWS_EMPTY = "NEWS_EMPTY"


@dataclass(frozen=True, slots=True)
class OnboardingWarning:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    document_type: str
    year: int


def normalize_requested_ticker(value: str) -> str:
    return to_b3_ticker(value)


def financial_periods_for_onboarding(as_of: date) -> tuple[FinancialPeriod, ...]:
    return (
        FinancialPeriod(document_type="DFP", year=as_of.year - 1),
        FinancialPeriod(document_type="ITR", year=as_of.year),
    )
