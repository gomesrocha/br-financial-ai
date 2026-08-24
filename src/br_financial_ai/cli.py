import argparse
import asyncio
from pathlib import Path

import httpx
import yaml

from br_financial_ai.clients.b3 import B3Client
from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.services.company_sync import CompanySyncService
from br_financial_ai.services.exceptions import (
    CompanyNotFoundError,
    CvmCompanyNotFoundError,
)
from br_financial_ai.services.security_sync import SecuritySyncService


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

    if not companies:
        print("Error: no monitored companies configured.")
        return 1

    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://sistemaswebb3-listados.b3.com.br/",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    ) as http_client:
        cvm_client = CvmClient(http_client)
        b3_client = B3Client(http_client)

        async with async_session_factory() as session:
            company_sync_service = CompanySyncService(
                session=session,
                cvm_client=cvm_client,
            )

            security_sync_service = SecuritySyncService(
                session=session,
                b3_client=b3_client,
            )

            for item in companies:
                cvm_code = str(item["cvm_code"]).strip()

                print(f"Synchronizing CVM company {cvm_code}...")

                try:
                    company = await company_sync_service.sync_by_cvm_code(cvm_code)

                    securities = await security_sync_service.sync_by_cvm_code(cvm_code)

                except CvmCompanyNotFoundError as exc:
                    print(f"Error: {exc}")
                    return 2

                except httpx.HTTPError as exc:
                    print(f"Error accessing external source: {exc}")
                    return 3

                print(
                    f"  {company.trade_name}: {len(securities)} securities synchronized"
                )

    print("Bootstrap completed successfully.")

    return 0


async def sync_company(cvm_code: str) -> int:
    async with httpx.AsyncClient(
        timeout=30.0,
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
    print(f"  Active: {company.active}")

    return 0


async def sync_securities(cvm_code: str) -> int:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://sistemaswebb3-listados.b3.com.br/",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="br-financial-ai",
        description="BR Financial AI command line interface.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sync_company_parser = subparsers.add_parser(
        "sync-company",
        help="Synchronize a company using its CVM code.",
    )

    sync_company_parser.add_argument(
        "cvm_code",
        help="CVM company code.",
    )

    sync_securities_parser = subparsers.add_parser(
        "sync-securities",
        help="Synchronize company securities from B3.",
    )

    sync_securities_parser.add_argument(
        "cvm_code",
        help="CVM company code.",
    )
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Synchronize all monitored companies and securities.",
    )

    bootstrap_parser.add_argument(
        "--config",
        default="config/monitored_companies.yaml",
        help="Path to monitored companies configuration.",
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
    if args.command == "bootstrap":
        exit_code = asyncio.run(
            bootstrap(args.config),
        )
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
