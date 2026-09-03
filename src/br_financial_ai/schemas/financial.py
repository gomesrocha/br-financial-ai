from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel


class FinancialAccountRead(SQLModel):
    ticker: str
    year: int
    quarter: int

    statement_type: str
    scope: str

    account_code: str
    account_name: str

    period_start: date | None
    period_end: date

    value: Decimal

    currency: str
    currency_scale: str
