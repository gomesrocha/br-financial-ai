from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from br_financial_ai.db.models import (
    Company,
    FinancialFiling,
    FinancialStatementItem,
    Security,
)
from br_financial_ai.repositories.company import (
    CompanyRepository,
)
from br_financial_ai.repositories.financial_filing import (
    FinancialFilingRepository,
)
from br_financial_ai.repositories.financial_statement_item import (
    FinancialStatementItemRepository,
)
from br_financial_ai.repositories.security import (
    SecurityRepository,
)
from br_financial_ai.services.financial_query import (
    FinancialQueryService,
)


@pytest.mark.asyncio
async def test_get_second_quarter_uses_isolated_period(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99123",
            cnpj="91000000000101",
            legal_name="EMPRESA QUERY S.A.",
            trade_name="EMPRESA QUERY",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FQRY3",
            isin="BRFQRYACNOR1",
            security_type="ON",
        )
    )

    first_quarter_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 3, 31),
            version=1,
            source_year=2026,
        )
    )

    second_quarter_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert first_quarter_filing.id is not None
    assert second_quarter_filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=first_quarter_filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("123.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            ),
            FinancialStatementItem(
                filing_id=second_quarter_filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("292.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            ),
            FinancialStatementItem(
                filing_id=second_quarter_filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("169.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_quarter_account(
        ticker="fqry3",
        year=2026,
        quarter=2,
        account_code="3.01",
    )

    assert result is not None

    assert result.period_start == date(2026, 4, 1)
    assert result.period_end == date(2026, 6, 30)

    assert result.value == Decimal("169.0000000000")


@pytest.mark.asyncio
async def test_get_quarter_account_uses_latest_version(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99124",
            cnpj="91000000000102",
            legal_name="EMPRESA VERSIONADA S.A.",
            trade_name="EMPRESA VERSIONADA",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FVRS3",
            isin="BRFVRSACNOR1",
            security_type="ON",
        )
    )

    filing_v1 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    filing_v2 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=2,
            source_year=2026,
        )
    )

    assert filing_v1.id is not None
    assert filing_v2.id is not None

    common = {
        "statement_type": "DRE",
        "scope": "CONSOLIDATED",
        "exercise_order": "ÚLTIMO",
        "period_start": date(2026, 4, 1),
        "period_end": date(2026, 6, 30),
        "statement_column": None,
        "account_code": "3.01",
        "account_name": "Receita",
        "currency": "REAL",
        "currency_scale": "MIL",
        "fixed_account_status": "S",
        "source_group": "DF Consolidado - DRE",
    }

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing_v1.id,
                value=Decimal("160.0000000000"),
                **common,
            ),
            FinancialStatementItem(
                filing_id=filing_v2.id,
                value=Decimal("169.0000000000"),
                **common,
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_quarter_account(
        ticker="FVRS3",
        year=2026,
        quarter=2,
        account_code="3.01",
    )

    assert result is not None
    assert result.filing_id == filing_v2.id

    assert result.value == Decimal("169.0000000000")


@pytest.mark.asyncio
async def test_get_quarter_metric_resolves_revenue(
    db_session: AsyncSession,
) -> None:
    company_repository = CompanyRepository(db_session)
    security_repository = SecurityRepository(db_session)
    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    company = await company_repository.add(
        Company(
            cvm_code="99125",
            cnpj="91000000000103",
            legal_name="EMPRESA METRIC S.A.",
            trade_name="EMPRESA METRIC",
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker="FMET3",
            isin="BRFMETACNOR1",
            security_type="ON",
        )
    )

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            FinancialStatementItem(
                filing_id=filing.id,
                statement_type="DRE",
                scope="CONSOLIDATED",
                exercise_order="ÚLTIMO",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                statement_column=None,
                account_code="3.01",
                account_name="Receita",
                value=Decimal("169.0000000000"),
                currency="REAL",
                currency_scale="MIL",
                fixed_account_status="S",
                source_group="DF Consolidado - DRE",
            )
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_quarter_metric(
        ticker="FMET3",
        year=2026,
        quarter=2,
        metric_key="revenue",
    )

    assert result is not None
    assert result.account_code == "3.01"
    assert result.value == Decimal("169.0000000000")


@pytest.mark.asyncio
async def test_unknown_metric_raises_value_error(
    db_session: AsyncSession,
) -> None:
    service = FinancialQueryService(db_session)

    with pytest.raises(
        ValueError,
        match="Unknown financial metric",
    ):
        await service.get_quarter_metric(
            ticker="ANY3",
            year=2026,
            quarter=2,
            metric_key="does_not_exist",
        )


async def _seed_listed_company(
    session: AsyncSession,
    *,
    cvm_code: str,
    cnpj: str,
    ticker: str,
    isin: str,
) -> Company:
    company_repository = CompanyRepository(session)
    security_repository = SecurityRepository(session)

    company = await company_repository.add(
        Company(
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name=f"{ticker} S.A.",
            trade_name=ticker,
        )
    )

    assert company.id is not None

    await security_repository.add(
        Security(
            company_id=company.id,
            ticker=ticker,
            isin=isin,
            security_type="ON",
        )
    )

    return company


def _dre_item(
    filing_id: int,
    *,
    account_code: str,
    account_name: str,
    value: str,
    period_start: date,
    period_end: date,
) -> FinancialStatementItem:
    return FinancialStatementItem(
        filing_id=filing_id,
        statement_type="DRE",
        scope="CONSOLIDATED",
        exercise_order="ÚLTIMO",
        period_start=period_start,
        period_end=period_end,
        statement_column=None,
        account_code=account_code,
        account_name=account_name,
        value=Decimal(value),
        currency="REAL",
        currency_scale="MIL",
        fixed_account_status="S",
        source_group="DF Consolidado - DRE",
    )


@pytest.mark.asyncio
async def test_get_annual_metric_uses_dfp_period(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99130",
        cnpj="91000000000110",
        ticker="FDFP3",
        isin="BRFDFPACNOR1",
    )

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    itr_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )
    dfp_filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )

    assert itr_filing.id is not None
    assert dfp_filing.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                itr_filing.id,
                account_code="3.01",
                account_name="Receita",
                value="10.0000000000",
                period_start=date(2025, 10, 1),
                period_end=date(2025, 12, 31),
            ),
            _dre_item(
                dfp_filing.id,
                account_code="3.01",
                account_name="Receita",
                value="490.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_annual_metric(
        "FDFP3",
        2025,
        "revenue",
    )

    assert result is not None
    assert result.filing_id == dfp_filing.id
    assert result.account_code == "3.01"
    assert result.period_start == date(2025, 1, 1)
    assert result.period_end == date(2025, 12, 31)
    assert result.value == Decimal("490.0000000000")


@pytest.mark.asyncio
async def test_get_annual_account_uses_latest_filing_version(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99131",
        cnpj="91000000000111",
        ticker="FDFP4",
        isin="BRFDFPACNPR8",
    )

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    filing_v1 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )
    filing_v2 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=2,
            source_year=2025,
        )
    )

    assert filing_v1.id is not None
    assert filing_v2.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                filing_v1.id,
                account_code="3.01",
                account_name="Receita",
                value="100.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
            _dre_item(
                filing_v2.id,
                account_code="3.01",
                account_name="Receita",
                value="120.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_annual_account(
        ticker="FDFP4",
        year=2025,
        account_code="3.01",
    )

    assert result is not None
    assert result.filing_id == filing_v2.id
    assert result.value == Decimal("120.0000000000")


@pytest.mark.asyncio
async def test_get_annual_metric_resolves_net_income(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99132",
        cnpj="91000000000112",
        ticker="FDFP5",
        isin="BRFDFPACNOR5",
    )

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)

    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                filing.id,
                account_code="3.11",
                account_name="Lucro",
                value="55.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            )
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_annual_metric(
        "FDFP5",
        2025,
        "net_income",
    )

    assert result is not None
    assert result.account_code == "3.11"
    assert result.value == Decimal("55.0000000000")


@pytest.mark.asyncio
async def test_bank_annual_net_income_uses_consolidated_period_profit(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99140",
        cnpj="91000000000140",
        ticker="QITB4",
        isin="BRQITBACNPR1",
    )
    company.setor_ativ = "Bancos"
    await db_session.flush()

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)
    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=2,
            source_year=2025,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                filing.id,
                account_code="3.09",
                account_name="Lucro/Prejuízo Consolidado do Período",
                value="45849.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
            _dre_item(
                filing.id,
                account_code="3.01",
                account_name="Receitas da Intermediação Financeira",
                value="387118.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
        ]
    )

    service = FinancialQueryService(db_session)

    result = await service.get_annual_metric("QITB4", 2025, "net_income")

    assert result is not None
    assert result.account_code == "3.09"
    assert result.account_name == "Lucro/Prejuízo Consolidado do Período"
    assert result.value == Decimal("45849.0000000000")

    with pytest.raises(
        ValueError,
        match="unsupported for profile FINANCIAL_INSTITUTION",
    ):
        await service.get_annual_metric("QITB4", 2025, "revenue")


@pytest.mark.asyncio
async def test_bank_annual_net_income_prefers_latest_dfp_and_code_3_11(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99141",
        cnpj="91000000000141",
        ticker="QBBD4",
        isin="BRQBBDACNPR1",
    )
    company.setor_ativ = "Bancos"
    await db_session.flush()

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)
    filing_v1 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=1,
            source_year=2025,
        )
    )
    filing_v2 = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="DFP",
            reference_date=date(2025, 12, 31),
            version=2,
            source_year=2025,
        )
    )

    assert filing_v1.id is not None
    assert filing_v2.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                filing_v1.id,
                account_code="3.11",
                account_name="Lucro ou Prejuízo Líquido Consolidado do Período",
                value="100.0000000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
            _dre_item(
                filing_v2.id,
                account_code="3.09",
                account_name=(
                    "Lucro ou Prejuízo antes das Participações "
                    "e Contribuições Estatutárias"
                ),
                value="23924.6360000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
            _dre_item(
                filing_v2.id,
                account_code="3.11",
                account_name="Lucro ou Prejuízo Líquido Consolidado do Período",
                value="23924.6360000000",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
            ),
        ]
    )

    service = FinancialQueryService(db_session)
    result = await service.get_annual_metric("QBBD4", 2025, "net_income")

    assert result is not None
    assert result.filing_id == filing_v2.id
    assert result.account_code == "3.11"
    assert result.value == Decimal("23924.6360000000")


@pytest.mark.asyncio
async def test_bank_quarterly_net_income_uses_isolated_period(
    db_session: AsyncSession,
) -> None:
    company = await _seed_listed_company(
        db_session,
        cvm_code="99142",
        cnpj="91000000000142",
        ticker="QITB3",
        isin="BRQITBACNOR0",
    )
    company.setor_ativ = "Bancos"
    await db_session.flush()

    filing_repository = FinancialFilingRepository(db_session)
    item_repository = FinancialStatementItemRepository(db_session)
    filing = await filing_repository.add(
        FinancialFiling(
            company_id=company.id,
            document_type="ITR",
            reference_date=date(2026, 6, 30),
            version=1,
            source_year=2026,
        )
    )

    assert filing.id is not None

    await item_repository.add_all(
        [
            _dre_item(
                filing.id,
                account_code="3.09",
                account_name="Lucro/Prejuízo Consolidado do Período",
                value="24199.0000000000",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 6, 30),
            ),
            _dre_item(
                filing.id,
                account_code="3.09",
                account_name="Lucro/Prejuízo Consolidado do Período",
                value="12324.0000000000",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
            ),
        ]
    )

    service = FinancialQueryService(db_session)
    result = await service.get_quarter_metric(
        ticker="QITB3",
        year=2026,
        quarter=2,
        metric_key="net_income",
    )

    assert result is not None
    assert result.account_code == "3.09"
    assert result.period_start == date(2026, 4, 1)
    assert result.period_end == date(2026, 6, 30)
    assert result.value == Decimal("12324.0000000000")
