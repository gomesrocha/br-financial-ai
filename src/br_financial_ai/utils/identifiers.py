import re

NON_DIGIT_PATTERN = re.compile(r"\D+")


def normalize_cnpj(value: str) -> str:
    return NON_DIGIT_PATTERN.sub("", value)


def normalize_cvm_code(value: str) -> str:
    normalized = value.strip().lstrip("0")

    return normalized or "0"
