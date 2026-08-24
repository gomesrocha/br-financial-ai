from dataclasses import dataclass

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from br_financial_ai.api.dependencies import get_company_query_service
from br_financial_ai.main import app

scenarios("features/monitored_companies.feature")


@dataclass
class FakeCompany:
    id: int
    cvm_code: str
    cnpj: str
    legal_name: str
    trade_name: str
    active: bool = True


class FakeCompanyQueryService:
    COMPANIES_BY_TICKER = {
        "PETR3": FakeCompany(
            id=1,
            cvm_code="9512",
            cnpj="33000167000101",
            legal_name="PETRÓLEO BRASILEIRO S.A. - PETROBRAS",
            trade_name="PETROBRAS",
        ),
        "PETR4": FakeCompany(
            id=1,
            cvm_code="9512",
            cnpj="33000167000101",
            legal_name="PETRÓLEO BRASILEIRO S.A. - PETROBRAS",
            trade_name="PETROBRAS",
        ),
        "BBDC3": FakeCompany(
            id=2,
            cvm_code="906",
            cnpj="60746948000112",
            legal_name="BANCO BRADESCO S.A.",
            trade_name="BANCO BRADESCO S.A.",
        ),
        "BBDC4": FakeCompany(
            id=2,
            cvm_code="906",
            cnpj="60746948000112",
            legal_name="BANCO BRADESCO S.A.",
            trade_name="BANCO BRADESCO S.A.",
        ),
        "VALE3": FakeCompany(
            id=3,
            cvm_code="4170",
            cnpj="33592510000154",
            legal_name="VALE S.A.",
            trade_name="VALE",
        ),
    }

    async def find_by_ticker(
        self,
        ticker: str,
    ) -> FakeCompany | None:
        return self.COMPANIES_BY_TICKER.get(ticker.strip().upper())


@given(
    "que existe um universo inicial de companhias monitoradas",
    target_fixture="client",
)
def monitored_companies_client() -> TestClient:
    service = FakeCompanyQueryService()

    app.dependency_overrides[get_company_query_service] = lambda: service

    return TestClient(app)


@when(
    parsers.parse('eu consulto o ticker "{ticker}"'),
    target_fixture="response",
)
def resolve_company(
    ticker: str,
    client: TestClient,
):
    return client.get(f"/companies/by-ticker/{ticker}")


@then(parsers.parse('a companhia identificada deve possuir o código CVM "{cvm_code}"'))
def company_should_match(
    response,
    cvm_code: str,
) -> None:
    assert response.status_code == 200
    assert response.json()["cvm_code"] == cvm_code
