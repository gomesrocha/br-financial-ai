from br_financial_ai.ai.recommendation_prompt import (
    build_recommendation_prompt_context,
)
from br_financial_ai.domain.recommendation import evidence_identity
from br_financial_ai.eval.contexts import context_from_case
from br_financial_ai.eval.datasets import dataset_cases


def test_prompt_context_keeps_required_recommendation_fields() -> None:
    context = context_from_case(dataset_cases("recommendation.json")[0])
    prompt = build_recommendation_prompt_context(context)
    payload = prompt.payload

    assert payload["ticker"] == context.ticker
    assert payload["company_name"] == context.company_name
    assert payload["financial_profile"] == "NON_FINANCIAL"
    financials = payload["financials"]
    assert financials["revenue"] == "490829000000"
    assert financials["net_income"] == "80000000000"
    scales = financials["amount_scales"]
    assert scales["net_income"]["million"] == "80000"
    assert scales["net_income"]["billion"] == "80"
    assert scales["revenue"]["million"] == "490829"
    assert scales["revenue"]["billion"] == "490.829"
    valuation = payload["valuation"]
    assert valuation["price_to_sales"] == "0.81"
    assert valuation["price_to_earnings"] == "5"
    assert "market_cap" not in valuation
    assert payload["market_quote"]["price"] == "46.87"
    assert payload["market_quote"]["market_cap"] == "400000000000"
    news = payload["news"]
    assert news[0]["title"] == context.recent_news[0].title
    assert news[0]["sentiment"] == "POSITIVE"
    assert "canonical_url" not in news[0]
    assert "recent_news" not in payload
    assert "news_signals" not in payload
    evidence = {
        (item["source"], item["kind"], item["reference"])
        for item in payload["evidence"]
    }
    assert evidence == {evidence_identity(item) for item in context.evidence}
    assert prompt.character_count < 4000
