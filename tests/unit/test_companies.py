from br_financial_ai.domain.companies import find_company_by_ticker


def test_find_petrobras_by_ticker() -> None:
    company = find_company_by_ticker("PETR4")

    assert company is not None
    assert company.name == "Petrobras"


def test_find_company_is_case_insensitive() -> None:
    company = find_company_by_ticker("vale3")

    assert company is not None
    assert company.name == "Vale"


def test_unknown_ticker_returns_none() -> None:
    company = find_company_by_ticker("INVALID")

    assert company is None
