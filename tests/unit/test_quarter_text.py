from br_financial_ai.ai.quarter_text import (
    expand_quarter_expressions,
    expand_two_digit_year,
    normalize_quarter_tool_args,
)


def test_expand_compact_brazilian_and_english_quarters() -> None:
    assert "quarter 2 of 2026" in expand_quarter_expressions(
        "Qual a receita da PETR4 no 2T26?"
    )
    assert "quarter 2 of 2026" in expand_quarter_expressions("Receita PETR4 2T 2026")
    assert "quarter 2 of 2026" in expand_quarter_expressions("Receita PETR4 Q2 2026")
    assert "quarter 2 of 2026" in expand_quarter_expressions(
        "Qual foi a receita da PETR4 no segundo trimestre de 2026?"
    )
    assert "quarter 4 of 2026" in expand_quarter_expressions(
        "Receita da PETR4 no quarto trimestre de 2026"
    )
    assert "quarter 3 of 2026" in expand_quarter_expressions(
        "Resultado operacional PETR4 3T26"
    )


def test_two_digit_years_expand_to_2000s() -> None:
    assert expand_two_digit_year(26) == 2026
    assert expand_two_digit_year(2026) == 2026
    assert normalize_quarter_tool_args(
        {"year": 26, "quarter": 2, "metric": "gross_income"}
    ) == {
        "year": 2026,
        "quarter": 2,
        "metric": "gross_profit",
    }
