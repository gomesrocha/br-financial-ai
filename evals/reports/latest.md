# BR Financial AI evaluation summary

Run `2026-09-03T021334Z` (full) at `2026-09-03T02:13:34Z`.

Model `ollama / llama3.1`. Status `PASS`.

## Tool Selection

- **cases**: `12`
- **tool_name_accuracy**: `1.0000`
- **argument_accuracy**: `1.0000`
- **exact_call_accuracy**: `1.0000`
- **case_ids**: `["petr4_revenue_long_pt", "petr4_revenue_2t26", "petr4_revenue_petrobras_faturamento", "petr4_revenue_q2_en", "petr4_net_income_2q", "petr4_gross_profit_q1", "petr4_operating_result_q3", "vale3_revenue_q2", "vale3_net_income_q2", "bbdc4_revenue_q1", "bbdc4_net_income_q2", "petr4_wrong_quarter_must_not_match_q2"]`

## News Classification

- **cases**: `8`
- **relevance_accuracy**: `1.0000`
- **materiality_accuracy**: `0.8750`
- **company_specific_accuracy**: `1.0000`
- **sentiment_agreement**: `0.8750`
- **category_agreement**: `1.0000`
- **case_ids**: `["company_specific_positive", "company_specific_adverse", "sector_event", "macro_event", "geopolitical_event", "weak_mention", "irrelevant_mention", "mixed_impact"]`

## Recommendation

- **cases**: `9`
- **stance_accuracy**: `1.0000`
- **factual_consistency**: `1.0000`
- **evidence_grounding**: `1.0000`
- **hallucination_count**: `0`
- **true_hallucination_count**: `0`
- **evaluator_false_positive_count**: `0`
- **case_ids**: `["strong_favorable", "weak_favorable", "mixed", "weak_unfavorable", "strong_unfavorable", "insufficient_data", "conflicting_market_vs_fundamentals", "negative_news_vs_strong_fundamentals", "positive_news_vs_poor_fundamentals"]`
- **flagged_cases**: `[]`

## Stability

- **runs**: `5`
- **stance_distribution**: `{"NEUTRAL": 5}`
- **dominant_stance**: `NEUTRAL`
- **stance_stability_ratio**: `1.0000`
- **confidence_mean**: `0.7800`
- **confidence_range**: `0.1`

## Performance

- **total_analysis_latency**: `140.8959`
- **yahoo_quote_latency**: `0.5782`
- **yahoo_history_latency**: `0.5665`
- **context_build_latency**: `1.1596`
- **recommendation_latency**: `139.7363`

## Llm Usage

- **e2e_recommendation**: `{"input_tokens": 3846, "output_tokens": 740, "total_tokens": 4586, "estimated_cost": null, "currency": null, "model": "llama3.1", "provider": "ollama", "available": true}`
- **news_classification**: `{"input_tokens": 3436, "output_tokens": 670, "total_tokens": 4106, "estimated_cost": null, "currency": null, "model": "llama3.1", "provider": "ollama", "available": true, "calls": 8}`
- **recommendation**: `{"input_tokens": 7592, "output_tokens": 2847, "total_tokens": 10439, "estimated_cost": null, "currency": null, "model": "llama3.1", "provider": "ollama", "available": true, "calls": 9}`
- **recommendation_prompt_characters**: `1785`
- **tool_selection**: `{"input_tokens": 4555, "output_tokens": 517, "total_tokens": 5072, "estimated_cost": null, "currency": null, "model": "llama3.1", "provider": "ollama", "available": true, "calls": 12}`

## E2E

- **ticker**: `PETR4`
- **stance**: `NEUTRAL`
- **confidence**: `0.8`
- **limitations**: `["P/B not supported", "EV/EBITDA not supported"]`
- **evidence_count**: `10`
- **total_latency_seconds**: `92.6243`
- **context_http_latency_seconds**: `2.0296`
- **analysis_http_latency_seconds**: `90.5947`
- **instrumented**: `{"stance": "NEUTRAL", "confidence": "0.7", "factual_consistency": "1.0000", "evidence_grounding": "1.0000", "hallucination_count": 0, "fabricated_evidence_count": 0, "news_articles": 5, "recommendation_prompt_characters": 5781}`

## Eval Performance

- **grounding_eval_seconds**: `0.0038`
- **news_eval_seconds**: `102.5963`
- **news_llm_calls**: `8`
- **recommendation_eval_seconds**: `434.9011`
- **recommendation_llm_calls**: `9`
- **tool_selection_eval_seconds**: `76.2433`
- **tool_selection_llm_calls**: `12`
- **report_generation_seconds**: `0.0057`

## Gates

- **passed**: `["exact tool-call accuracy 1.0 >= 0.95", "news relevance accuracy 1.0 >= 0.9", "company-specific accuracy 1.0 >= 0.9", "stance accuracy 1.0 >= 0.8", "factual consistency 1.0 >= 0.95", "evidence grounding 1.0 >= 1.0", "true hallucinations 0.0 == 0.0"]`
- **failed**: `[]`
- **unmeasured**: `[]`

## Warnings

None.

## Comparison

- **previous_run_id**: `2026-09-03T011616Z`
- **metrics**: `{"tool_name_accuracy": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "argument_accuracy": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "exact_tool_call_accuracy": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "news_relevance_accuracy": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "news_materiality_accuracy": {"previous": 0.875, "current": 0.875, "delta": 0.0}, "company_specific_accuracy": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "sentiment_agreement": {"previous": 0.875, "current": 0.875, "delta": 0.0}, "stance_accuracy": {"previous": 0.8889, "current": 1.0, "delta": 0.1111}, "factual_consistency": {"previous": 0.9921, "current": 1.0, "delta": 0.0079}, "evidence_grounding": {"previous": 1.0, "current": 1.0, "delta": 0.0}, "true_hallucination_count": {"previous": 1.0, "current": 0.0, "delta": -1.0}, "news_classification_latency": {"previous": null, "current": null, "delta": null}, "recommendation_latency": {"previous": 116.0061, "current": 139.7363, "delta": 23.7302}, "total_analysis_latency_seconds": {"previous": 117.1362, "current": 140.8959, "delta": 23.7597}, "tool_selection_input_tokens": {"previous": 4555.0, "current": 4555.0, "delta": 0.0}, "tool_selection_output_tokens": {"previous": 517.0, "current": 517.0, "delta": 0.0}, "news_classification_input_tokens": {"previous": 3436.0, "current": 3436.0, "delta": 0.0}, "news_classification_output_tokens": {"previous": 670.0, "current": 670.0, "delta": 0.0}, "recommendation_input_tokens": {"previous": 6535.0, "current": 7592.0, "delta": 1057.0}, "recommendation_output_tokens": {"previous": 2438.0, "current": 2847.0, "delta": 409.0}, "fast_eval_total_seconds": {"previous": null, "current": null, "delta": null}, "tool_selection_eval_seconds": {"previous": 76.3547, "current": 76.2433, "delta": -0.1114}, "news_eval_seconds": {"previous": 127.6368, "current": 102.5963, "delta": -25.0405}, "recommendation_eval_seconds": {"previous": 379.9852, "current": 434.9011, "delta": 54.9159}, "input_tokens": {"previous": 14526.0, "current": 15583.0, "delta": 1057.0}, "output_tokens": {"previous": 3625.0, "current": 4034.0, "delta": 409.0}, "total_tokens": {"previous": 18151.0, "current": 19617.0, "delta": 1466.0}}`
