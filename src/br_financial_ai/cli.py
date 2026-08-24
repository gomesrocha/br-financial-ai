import argparse
import asyncio

import httpx

from br_financial_ai.clients.cvm import CvmClient
from br_financial_ai.db.session import async_session_factory
from br_financial_ai.services.company_sync import CompanySyncService
from br_financial_ai.services.exceptions import CvmCompanyNotFoundError


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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sync-company":
        exit_code = asyncio.run(
            sync_company(args.cvm_code),
        )
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
