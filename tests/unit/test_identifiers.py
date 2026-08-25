from br_financial_ai.utils.identifiers import (
    normalize_cnpj,
    normalize_cvm_code,
)


def test_normalize_formatted_cnpj() -> None:
    result = normalize_cnpj("33.000.167/0001-01")

    assert result == "33000167000101"


def test_normalize_unformatted_cnpj() -> None:
    result = normalize_cnpj("33000167000101")

    assert result == "33000167000101"


def test_normalize_cvm_code() -> None:
    result = normalize_cvm_code(" 9512 ")

    assert result == "9512"


def test_normalize_padded_cvm_code() -> None:
    assert normalize_cvm_code("009512") == "9512"


def test_normalize_cvm_code_without_padding() -> None:
    assert normalize_cvm_code("9512") == "9512"
