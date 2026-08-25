from br_financial_ai.cli import (
    build_parser,
    load_bootstrap_config,
)


def test_parse_sync_financials_command() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "sync-financials",
            "9512",
            "--type",
            "DFP",
            "--year",
            "2025",
        ]
    )

    assert args.command == "sync-financials"
    assert args.cvm_code == "9512"
    assert args.document_type == "DFP"
    assert args.year == 2025


def test_sync_financials_defaults_to_dfp() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "sync-financials",
            "9512",
            "--year",
            "2025",
        ]
    )

    assert args.document_type == "DFP"


def test_load_bootstrap_config_with_financial_data(
    tmp_path,
) -> None:
    config_file = tmp_path / "companies.yaml"

    config_file.write_text(
        (
            "companies:\n"
            '  - cvm_code: "9512"\n'
            "financial_data:\n"
            '  - document_type: "DFP"\n'
            "    year: 2025\n"
        ),
        encoding="utf-8",
    )

    config = load_bootstrap_config(str(config_file))

    assert config["companies"] == [
        {
            "cvm_code": "9512",
        }
    ]

    assert config["financial_data"] == [
        {
            "document_type": "DFP",
            "year": 2025,
        }
    ]
