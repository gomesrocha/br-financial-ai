from sqlmodel import SQLModel

from br_financial_ai.db.models import (
    Company,
    CompanyOnboardingJob,  # noqa: F401
    NewsArticleSignal,  # noqa: F401
    Security,
    TrackedCompany,  # noqa: F401
)


def test_company_model() -> None:
    company = Company(
        cvm_code="TEST001",
        cnpj="12345678000199",
        legal_name="Empresa Teste S.A.",
        trade_name="Empresa Teste",
    )

    assert company.id is None
    assert company.cvm_code == "TEST001"
    assert company.cnpj == "12345678000199"
    assert company.active is True
    assert company.setor_ativ is None


def test_security_model() -> None:
    security = Security(
        company_id=1,
        ticker="TEST3",
        isin="BRTESTACNOR1",
        security_type="ON",
    )

    assert security.isin == "BRTESTACNOR1"
    assert security.id is None
    assert security.company_id == 1
    assert security.ticker == "TEST3"
    assert security.security_type == "ON"
    assert security.active is True


def test_company_and_security_tables_are_registered() -> None:
    assert "companies" in SQLModel.metadata.tables
    assert "securities" in SQLModel.metadata.tables
    assert "tracked_companies" in SQLModel.metadata.tables
    assert "company_onboarding_jobs" in SQLModel.metadata.tables
    assert "news_article_signals" in SQLModel.metadata.tables
