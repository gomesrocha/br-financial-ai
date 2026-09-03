import argparse
import asyncio
from pathlib import Path

import httpx
import yaml

from br_financial_ai.clients.b3 import B3Client
from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.clients.cvm_financial import (
    CvmFinancialClient,
)
from br_financial_ai.clients.yahoo_news import (
    YahooNewsClient,
    YahooNewsProviderError,
)
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.eval.profile import EvalProfile
from br_financial_ai.eval.runner import export_eval_history, run_eval
from br_financial_ai.services.company_sync import (
    CompanySyncService,
)
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    CvmCompanyNotFoundError,
)
from br_financial_ai.services.financial_ingestion import (
    FinancialIngestionService,
)
from br_financial_ai.services.news_ingestion import (
    NewsIngestionService,
)
from br_financial_ai.services.security_sync import (
    SecuritySyncService,
)
from br_financial_ai.services.tracked_company import TrackedCompanyService


def load_bootstrap_config(config_path: str) -> dict:
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def bootstrap(
    config_path: str,
) -> int:
    try:
        config = load_bootstrap_config(config_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    companies = config.get("companies", [])
    financial_data = config.get(
        "financial_data",
        [],
    )

    if not companies:
        print("Error: no monitored companies configured.")
        return 1

    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
        "Referer": ("https://sistemaswebb3-listados.b3.com.br/"),
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True,
        headers=headers,
    ) as http_client:
        cvm_client = CvmClient(http_client)
        b3_client = B3Client(http_client)
        cvm_financial_client = CvmFinancialClient(http_client)

        async with async_session_factory() as session:
            company_sync_service = CompanySyncService(
                session=session,
                cvm_client=cvm_client,
            )

            security_sync_service = SecuritySyncService(
                session=session,
                b3_client=b3_client,
            )

            financial_ingestion_service = FinancialIngestionService(
                session=session,
                client=cvm_financial_client,
            )
            tracked_company_service = TrackedCompanyService(session)

            for item in companies:
                cvm_code = str(item["cvm_code"]).strip()
                preferred_ticker = (
                    str(
                        item.get("preferred_ticker") or "",
                    )
                    .strip()
                    .upper()
                    or None
                )

                print(f"Synchronizing CVM company {cvm_code}...")

                try:
                    company = await company_sync_service.sync_by_cvm_code(cvm_code)

                    securities = await security_sync_service.sync_by_cvm_code(cvm_code)

                    print(
                        f"  {company.trade_name}: "
                        f"{len(securities)} securities "
                        f"synchronized"
                    )

                    if preferred_ticker:
                        preferred = next(
                            (
                                security
                                for security in securities
                                if security.ticker == preferred_ticker
                            ),
                            None,
                        )
                        if preferred is None or company.id is None:
                            print(
                                f"  Warning: preferred ticker "
                                f"{preferred_ticker} was not found."
                            )
                        else:
                            tracked = await tracked_company_service.track_company(
                                company_id=company.id,
                                preferred_security=preferred,
                            )
                            print(f"  Tracked {preferred.ticker} (id={tracked.id})")

                    for financial_item in financial_data:
                        document_type = (
                            str(financial_item["document_type"]).strip().upper()
                        )

                        year = int(financial_item["year"])

                        print(f"  Synchronizing {document_type} {year}...")

                        result = await financial_ingestion_service.sync(
                            cvm_code=cvm_code,
                            document_type=(document_type),
                            year=year,
                        )

                        print(
                            f"    "
                            f"{result.items_created} "
                            f"items created, "
                            f"{result.items_skipped} "
                            f"skipped"
                        )

                except CvmCompanyNotFoundError as exc:
                    print(f"Error: {exc}")
                    return 2

                except CompanyNotFoundError as exc:
                    print(f"Error: {exc}")
                    return 2

                except httpx.HTTPError as exc:
                    print(f"Error accessing external source: {exc}")
                    return 3

                except ValueError as exc:
                    print(f"Error: {exc}")
                    return 4

    print("Bootstrap completed successfully.")

    return 0


async def sync_news(ticker: str, limit: int) -> int:
    async with async_session_factory() as session:
        service = NewsIngestionService(
            session,
            YahooNewsClient(),
        )

        try:
            result = await service.sync_company_news(
                ticker,
                limit=limit,
            )
        except CompanyNotFoundError as exc:
            print(f"Error: {exc}")
            return 1
        except ValueError as exc:
            print(f"Error: {exc}")
            return 2
        except YahooNewsProviderError as exc:
            print(f"Error fetching company news: {exc}")
            return 3

    print("Company news synchronized successfully:")
    print(f"  Ticker: {result.ticker}")
    print(f"  Fetched: {result.fetched}")
    print(f"  Created: {result.created}")
    print(f"  Skipped: {result.skipped}")

    return 0


async def sync_company(
    cvm_code: str,
) -> int:
    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True,
    ) as http_client:
        cvm_client = CvmClient(http_client)

        async with async_session_factory() as session:
            service = CompanySyncService(
                session=session,
                cvm_client=cvm_client,
            )

            try:
                company = await service.sync_by_cvm_code(cvm_code)
            except CvmCompanyNotFoundError as exc:
                print(f"Error: {exc}")
                return 1
            except httpx.HTTPError as exc:
                print(f"Error accessing CVM: {exc}")
                return 2

    print("Company synchronized successfully:")
    print(f"  ID: {company.id}")
    print(f"  CVM code: {company.cvm_code}")
    print(f"  CNPJ: {company.cnpj}")
    print(f"  Legal name: {company.legal_name}")
    print(f"  Trade name: {company.trade_name}")
    print(f"  Activity: {company.setor_ativ}")
    print(f"  Active: {company.active}")

    return 0


async def sync_securities(
    cvm_code: str,
) -> int:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
        "Referer": ("https://sistemaswebb3-listados.b3.com.br/"),
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    ) as http_client:
        b3_client = B3Client(http_client)

        async with async_session_factory() as session:
            service = SecuritySyncService(
                session=session,
                b3_client=b3_client,
            )

            try:
                securities = await service.sync_by_cvm_code(cvm_code)
            except CompanyNotFoundError as exc:
                print(f"Error: {exc}")
                return 1
            except httpx.HTTPError as exc:
                print(f"Error accessing B3: {exc}")
                return 2

    print("Securities synchronized successfully:")

    for security in securities:
        print(f"  {security.ticker} | {security.isin} | {security.security_type}")

    return 0


async def sync_financials(
    cvm_code: str,
    document_type: str,
    year: int,
) -> int:
    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True,
    ) as http_client:
        client = CvmFinancialClient(http_client)

        async with async_session_factory() as session:
            service = FinancialIngestionService(
                session=session,
                client=client,
            )

            try:
                result = await service.sync(
                    cvm_code=cvm_code,
                    document_type=document_type,
                    year=year,
                )

            except CompanyNotFoundError as exc:
                print(f"Error: {exc}")
                return 1

            except ValueError as exc:
                print(f"Error: {exc}")
                return 2

            except httpx.HTTPError as exc:
                print(f"Error accessing CVM financial data: {exc}")
                return 3

    print("Financial statements synchronized successfully:")
    print(f"  CVM code: {result.cvm_code}")
    print(f"  Document type: {result.document_type}")
    print(f"  Year: {result.year}")
    print(f"  Files processed: {result.files_processed}")
    print(f"  Filings created: {result.filings_created}")
    print(f"  Filings skipped: {result.filings_skipped}")
    print(f"  Items created: {result.items_created}")
    print(f"  Items skipped: {result.items_skipped}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="br-financial-ai",
        description=("BR Financial AI command line interface."),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sync_company_parser = subparsers.add_parser(
        "sync-company",
        help=("Synchronize a company using its CVM code."),
    )

    sync_company_parser.add_argument(
        "cvm_code",
        help="CVM company code.",
    )

    sync_securities_parser = subparsers.add_parser(
        "sync-securities",
        help=("Synchronize company securities from B3."),
    )

    sync_securities_parser.add_argument(
        "cvm_code",
        help="CVM company code.",
    )

    sync_financials_parser = subparsers.add_parser(
        "sync-financials",
        help=("Synchronize financial statements from CVM."),
    )

    sync_financials_parser.add_argument(
        "cvm_code",
        help="CVM company code.",
    )

    sync_financials_parser.add_argument(
        "--type",
        dest="document_type",
        choices=("DFP", "ITR"),
        default="DFP",
        help="Financial document type.",
    )

    sync_financials_parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Source year to synchronize.",
    )

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help=("Synchronize all monitored companies, securities and financial data."),
    )

    bootstrap_parser.add_argument(
        "--config",
        default=("config/monitored_companies.yaml"),
        help=("Path to monitored companies configuration."),
    )

    sync_news_parser = subparsers.add_parser(
        "sync-news",
        help=("Synchronize persisted Yahoo news for a ticker."),
    )
    sync_news_parser.add_argument(
        "ticker",
        help="B3 ticker, for example PETR4.",
    )
    sync_news_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of articles to fetch.",
    )

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run FAST or FULL model/provider evaluation.",
    )
    eval_parser.add_argument(
        "--profile",
        choices=(EvalProfile.FAST.value, EvalProfile.FULL.value),
        required=True,
        help="FAST is a representative subset. FULL is the complete eval suite.",
    )
    eval_parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when quality gates fail.",
    )
    eval_parser.add_argument(
        "--no-export",
        action="store_true",
        help="Do not copy reports into the frontend public/ folder.",
    )

    subparsers.add_parser(
        "eval-export",
        help="Copy eval reports into the frontend public/evals/ folder.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sync-company":
        exit_code = asyncio.run(
            sync_company(args.cvm_code),
        )
        raise SystemExit(exit_code)

    if args.command == "sync-securities":
        exit_code = asyncio.run(
            sync_securities(args.cvm_code),
        )
        raise SystemExit(exit_code)

    if args.command == "sync-financials":
        exit_code = asyncio.run(
            sync_financials(
                args.cvm_code,
                args.document_type,
                args.year,
            ),
        )
        raise SystemExit(exit_code)

    if args.command == "bootstrap":
        exit_code = asyncio.run(
            bootstrap(args.config),
        )
        raise SystemExit(exit_code)

    if args.command == "sync-news":
        exit_code = asyncio.run(
            sync_news(args.ticker, args.limit),
        )
        raise SystemExit(exit_code)

    if args.command == "eval":
        raise SystemExit(
            run_eval(
                args.profile,
                fail_on_regression=args.fail_on_regression,
                export=not args.no_export,
            )
        )

    if args.command == "eval-export":
        raise SystemExit(export_eval_history())


if __name__ == "__main__":
    main()
