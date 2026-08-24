from pytest_bdd import given, parsers, scenarios, then, when

from br_financial_ai.domain.companies import (
    MONITORED_COMPANIES,
    MonitoredCompany,
    find_company_by_ticker,
)

scenarios("features/monitored_companies.feature")


@given(
    "que existe um universo inicial de companhias monitoradas",
    target_fixture="monitored_companies",
)
def monitored_companies() -> tuple[MonitoredCompany, ...]:
    return MONITORED_COMPANIES


@when(
    parsers.parse('eu consulto o ticker "{ticker}"'),
    target_fixture="resolved_company",
)
def resolve_company(
    ticker: str,
    monitored_companies: tuple[MonitoredCompany, ...],
) -> MonitoredCompany | None:
    assert monitored_companies

    return find_company_by_ticker(ticker)


@then(parsers.parse('a companhia identificada deve ser "{company}"'))
def company_should_match(
    resolved_company: MonitoredCompany | None,
    company: str,
) -> None:
    assert resolved_company is not None
    assert resolved_company.name == company
