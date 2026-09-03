from br_financial_ai.domain.financial_profile import (
    FinancialProfile,
    financial_profile_from_setor_ativ,
)


def test_non_financial_activity_resolves_non_financial_profile() -> None:
    assert (
        financial_profile_from_setor_ativ("Petróleo e Gás")
        is FinancialProfile.NON_FINANCIAL
    )
    assert (
        financial_profile_from_setor_ativ("Extração Mineral")
        is FinancialProfile.NON_FINANCIAL
    )


def test_bancos_activity_resolves_financial_institution_profile() -> None:
    assert (
        financial_profile_from_setor_ativ("Bancos")
        is FinancialProfile.FINANCIAL_INSTITUTION
    )
    assert (
        financial_profile_from_setor_ativ("bancos")
        is FinancialProfile.FINANCIAL_INSTITUTION
    )


def test_profile_does_not_depend_on_ticker_strings() -> None:
    assert "ITUB" not in FinancialProfile._value2member_map_
    assert "BBDC" not in FinancialProfile._value2member_map_
    assert financial_profile_from_setor_ativ.__code__.co_argcount == 1


def test_unknown_and_missing_activity_default_to_non_financial() -> None:
    assert financial_profile_from_setor_ativ(None) is FinancialProfile.NON_FINANCIAL
    assert (
        financial_profile_from_setor_ativ("Seguros") is FinancialProfile.NON_FINANCIAL
    )
    assert financial_profile_from_setor_ativ("") is FinancialProfile.NON_FINANCIAL
