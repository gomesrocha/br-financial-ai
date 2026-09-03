from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


class TrackedCompanyRead(BaseModel):
    company_id: int
    legal_name: str
    trade_name: str
    ticker: str
    active: bool


class OnboardCompanyRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


class OnboardingWarningRead(BaseModel):
    code: str
    message: str


class OnboardingJobRead(BaseModel):
    job_id: int | None
    ticker: str
    status: str
    step: str
    already_tracked: bool = False
    company_id: int | None = None
    tracked_company_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[OnboardingWarningRead] = Field(default_factory=list)


class MarketQuoteSnapshotRead(BaseModel):
    ticker: str
    symbol: str
    price: Decimal
    previous_close: Decimal | None
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    currency: str
    timestamp: datetime

    @field_serializer(
        "price",
        "previous_close",
        "absolute_change",
        "percentage_change",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")
