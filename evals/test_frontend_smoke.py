import os

import httpx
import pytest

pytestmark = [pytest.mark.eval, pytest.mark.external]


def test_frontend_pages_are_reachable() -> None:
    base_url = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:3000")

    try:
        home = httpx.get(f"{base_url}/", timeout=5.0)
        company = httpx.get(f"{base_url}/companies/PETR4", timeout=10.0)
    except httpx.HTTPError:
        pytest.skip(f"Frontend is not running at {base_url}.")

    assert home.status_code == 200
    assert "BR Financial AI" in home.text
    assert "Tracked companies" in home.text
    assert "Add company" in home.text
    assert company.status_code == 200
    assert "PETR4" in company.text
