import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import Company, Security, TrackedCompany
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.repositories.tracked_company import TrackedCompanyRepository
from br_financial_ai.services.exceptions import PreferredSecurityMismatchError
from br_financial_ai.services.tracked_company import TrackedCompanyService


async def _company_with_securities(
    session: AsyncSession,
    *,
    cvm_code: str,
    cnpj: str,
    tickers: tuple[str, str],
) -> tuple[Company, Security, Security]:
    company = await CompanyRepository(session).add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name=f"{cvm_code} LEGAL",
            trade_name=f"{cvm_code} TRADE",
        )
    )
    assert company.id is not None
    repository = SecurityRepository(session)
    first = await repository.add(
        Security(
            company_id=company.id,
            ticker=tickers[0],
            isin=f"BR{tickers[0]}0001",
            security_type="ON",
        )
    )
    second = await repository.add(
        Security(
            company_id=company.id,
            ticker=tickers[1],
            isin=f"BR{tickers[1]}0001",
            security_type="PN",
        )
    )
    await session.flush()
    return company, first, second


@pytest.mark.asyncio
async def test_persist_tracked_company(db_session: AsyncSession) -> None:
    company, _on, preferred = await _company_with_securities(
        db_session,
        cvm_code="TRK001",
        cnpj="11000000000101",
        tickers=("TRKA3", "TRKA4"),
    )
    service = TrackedCompanyService(db_session)
    tracked = await service.track_company(
        company_id=company.id or 0,
        preferred_security=preferred,
    )

    assert tracked.id is not None
    assert tracked.company_id == company.id
    assert tracked.preferred_security_id == preferred.id
    assert tracked.active is True


@pytest.mark.asyncio
async def test_tracked_company_is_unique_per_company(
    db_session: AsyncSession,
) -> None:
    company, _on, preferred = await _company_with_securities(
        db_session,
        cvm_code="TRK002",
        cnpj="11000000000102",
        tickers=("TRKB3", "TRKB4"),
    )
    service = TrackedCompanyService(db_session)
    first = await service.track_company(
        company_id=company.id or 0,
        preferred_security=preferred,
    )
    second = await service.track_company(
        company_id=company.id or 0,
        preferred_security=preferred,
    )

    assert first.id == second.id

    repository = TrackedCompanyRepository(db_session)
    with pytest.raises(IntegrityError):
        await repository.add(
            TrackedCompany(
                company_id=company.id or 0,
                preferred_security_id=preferred.id or 0,
                active=True,
            )
        )


@pytest.mark.asyncio
async def test_preferred_security_must_belong_to_company(
    db_session: AsyncSession,
) -> None:
    company_a, _on_a, preferred_a = await _company_with_securities(
        db_session,
        cvm_code="TRK003",
        cnpj="11000000000103",
        tickers=("TRKC3", "TRKC4"),
    )
    _company_b, _on_b, preferred_b = await _company_with_securities(
        db_session,
        cvm_code="TRK004",
        cnpj="11000000000104",
        tickers=("TRKD3", "TRKD4"),
    )
    service = TrackedCompanyService(db_session)

    with pytest.raises(PreferredSecurityMismatchError):
        await service.track_company(
            company_id=company_a.id or 0,
            preferred_security=preferred_b,
        )

    tracked = await service.track_company(
        company_id=company_a.id or 0,
        preferred_security=preferred_a,
    )
    assert tracked.preferred_security_id == preferred_a.id


@pytest.mark.asyncio
async def test_list_active_tracked_companies(
    db_session: AsyncSession,
) -> None:
    company, _on, preferred = await _company_with_securities(
        db_session,
        cvm_code="TRK005",
        cnpj="11000000000105",
        tickers=("TRKE3", "TRKE4"),
    )
    service = TrackedCompanyService(db_session)
    await service.track_company(
        company_id=company.id or 0,
        preferred_security=preferred,
    )

    records = await service.list_active()
    created = [item for item in records if item.security.ticker == "TRKE4"]
    assert len(created) == 1
    assert created[0].company.trade_name == "TRK005 TRADE"
