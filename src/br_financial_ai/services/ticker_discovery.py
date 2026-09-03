from inspect import isawaitable
from typing import Protocol

import httpx

from br_financial_ai.clients.b3 import B3Client
from br_financial_ai.clients.b3_instruments import B3InstrumentsClient
from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.domain.ticker_discovery import (
    DiscoveredSecurity,
    TickerDiscoveryAmbiguousError,
    TickerDiscoveryNotFoundError,
    TickerDiscoveryResult,
    TickerDiscoverySource,
    TickerDiscoveryUnavailableError,
    cash_share_security,
    result_from_instrument_match,
)
from br_financial_ai.repositories.company import CompanyRepository
from br_financial_ai.repositories.security import SecurityRepository
from br_financial_ai.utils.identifiers import normalize_cvm_code


class TickerDiscoveryProvider(Protocol):
    async def discover(self, ticker: str) -> TickerDiscoveryResult: ...


class LocalSecurityDiscovery:
    cache_miss_only = True

    def __init__(
        self,
        companies: CompanyRepository,
        securities: SecurityRepository,
    ) -> None:
        self.companies = companies
        self.securities = securities

    async def discover(self, ticker: str) -> TickerDiscoveryResult:
        security = await self.securities.get_by_ticker(ticker)
        if security is None:
            raise TickerDiscoveryNotFoundError(ticker)

        company = await self.companies.get_by_id(security.company_id)
        if company is None:
            raise TickerDiscoveryNotFoundError(ticker)

        rows = await self.securities.list_by_company_id(security.company_id)
        discovered: list[DiscoveredSecurity] = []
        for item in rows:
            parsed = cash_share_security(item.ticker, item.isin)
            if parsed is not None:
                discovered.append(parsed)

        if not any(item.ticker == security.ticker for item in discovered):
            raise TickerDiscoveryNotFoundError(ticker)

        return TickerDiscoveryResult(
            requested_ticker=security.ticker,
            cvm_code=normalize_cvm_code(company.cvm_code),
            company_name=company.legal_name,
            securities=tuple(discovered),
            source=TickerDiscoverySource.LOCAL.value,
        )


class B3ListedCompaniesDiscovery:
    def __init__(self, b3_client: B3Client) -> None:
        self.b3_client = b3_client

    async def discover(self, ticker: str) -> TickerDiscoveryResult:
        try:
            issuer = await self.b3_client.discover_ticker_issuer(ticker)
        except httpx.HTTPError as exc:
            raise TickerDiscoveryUnavailableError(ticker) from exc

        if issuer is None:
            raise TickerDiscoveryNotFoundError(ticker)

        securities: list[DiscoveredSecurity] = []
        getter = getattr(self.b3_client, "get_company_securities", None)
        records: list = []
        if getter is not None:
            try:
                fetched = getter(issuer.cvm_code)
                if isawaitable(fetched):
                    fetched = await fetched
                if isinstance(fetched, list):
                    records = fetched
            except (httpx.HTTPError, TypeError):
                records = []

        for item in records:
            parsed = cash_share_security(item.ticker, item.isin)
            if parsed is not None:
                securities.append(parsed)

        return TickerDiscoveryResult(
            requested_ticker=ticker.strip().upper(),
            cvm_code=normalize_cvm_code(issuer.cvm_code),
            company_name=issuer.company_name,
            securities=tuple(securities),
            source=TickerDiscoverySource.B3_LISTED_COMPANIES.value,
        )


class B3InstrumentsCvmDiscovery:
    def __init__(
        self,
        instruments_client: B3InstrumentsClient,
        cvm_client: CvmClient,
    ) -> None:
        self.instruments_client = instruments_client
        self.cvm_client = cvm_client

    async def discover(self, ticker: str) -> TickerDiscoveryResult:
        try:
            records = await self.instruments_client.get_equity_records()
            companies = await self.cvm_client.get_companies()
        except httpx.HTTPError as exc:
            raise TickerDiscoveryUnavailableError(ticker) from exc

        return result_from_instrument_match(ticker, records, companies)


class CompositeTickerDiscovery:
    def __init__(self, providers: tuple[TickerDiscoveryProvider, ...]) -> None:
        self.providers = providers

    async def discover(self, ticker: str) -> TickerDiscoveryResult:
        remote_unavailable = 0
        remote_not_found = 0

        for provider in self.providers:
            try:
                return await provider.discover(ticker)
            except TickerDiscoveryAmbiguousError:
                raise
            except TickerDiscoveryUnavailableError:
                if getattr(provider, "cache_miss_only", False):
                    raise
                remote_unavailable += 1
            except TickerDiscoveryNotFoundError:
                if getattr(provider, "cache_miss_only", False):
                    continue
                remote_not_found += 1

        if remote_not_found:
            raise TickerDiscoveryNotFoundError(ticker)
        if remote_unavailable:
            raise TickerDiscoveryUnavailableError(ticker)
        raise TickerDiscoveryNotFoundError(ticker)
