from sqlmodel import SQLModel


class SecurityCreate(SQLModel):
    ticker: str
    security_type: str


class CompanyCreate(SQLModel):
    cvm_code: str
    cnpj: str
    legal_name: str
    trade_name: str
    securities: list[SecurityCreate] = []