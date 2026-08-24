from sqlmodel import Field, SQLModel


class SecurityCreate(SQLModel):
    ticker: str
    security_type: str


class CompanyCreate(SQLModel):
    cvm_code: str
    cnpj: str
    legal_name: str
    trade_name: str
    active: bool = True

    securities: list[SecurityCreate] = Field(
        default_factory=list,
    )
