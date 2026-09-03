# AI Engineering

This study treats the LLM as an interpreter sitting on top of
deterministic financial machinery. The model may choose a tool, label a
news article, or write an outlook. It must not invent CVM numbers, market
prices, or evidence identifiers.

## LLM != source of truth for financial numbers

CVM filings and Yahoo market snapshots enter PostgreSQL and domain
objects before any prompt is built. Ratios, margins, returns, volatility,
and drawdown are calculated in Python. The recommendation prompt receives
those values as given and is instructed not to recalculate them.

If the model disagrees with a supplied figure, validation and evaluation
treat the deterministic value as correct.

## Deterministic responsibilities

| Concern | Where it lives |
| --- | --- |
| CVM accounting values | parsers, financial repositories, `FinancialQueryService` |
| Annual / quarterly period resolution | `FinancialQueryService`, `ai.quarter_text` |
| Metric mappings | `domain.financial_metrics` (profile-aware catalogue) |
| Financial profile | `domain.financial_profile` from CVM `SETOR_ATIV` |
| Margins, P/S, P/E | `domain.valuation`, `ValuationService` |
| Market returns, volatility, drawdown | `domain.market` |
| Evidence identity | `domain.recommendation.evidence_identity` |

`MIL` CVM amounts are multiplied by 1,000 before they are compared with
Yahoo market capitalization, which is already in BRL units.

Quarter phrasing such as `2T26`, `Q2 2026`, or `segundo trimestre de 2026`
is normalized before tool arguments are executed. Canonical metric keys
depend on `FinancialProfile`. Non-financial companies use `revenue`,
`gross_profit`, `operating_result`, and `net_income`. Financial
institutions use `net_income` plus bank-specific intermediation metrics.
Industrial `revenue` is unsupported for banks rather than remapped.


## LLM responsibilities

* **Financial-question tool selection.** `select_quarter_financial_metric_tool`
  binds `get_quarter_financial_metric` and expects exactly one tool call.
* **Structured news classification.** `NewsClassifier` labels relevance,
  materiality, company-specific, sentiment, and category for persisted
  articles during `POST /api/v1/analysis`. Results are stored as
  `NewsArticleSignal` rows keyed by classifier identity
  (`provider`, `model`, `classifier_version`, `prompt_version`).
  `GET /api/v1/analysis/context/{ticker}` never classifies; it only
  returns cached signals when the identity matches.
* **Recommendation interpretation.** `RecommendationEngine` writes stance,
  confidence, summary, positives, risks, and four views from
  `RecommendationContext`.

Stance is `FAVORABLE`, `NEUTRAL`, or `UNFAVORABLE`. Those labels are an
analytical outlook, not BUY / HOLD / SELL, and not a price forecast.

## StructuredTool and bind_tools

Framework-independent retrieval lives in `br_financial_ai.tools.financial`.
The LangChain adapter in `br_financial_ai.ai.tools.financial` wraps that
function as a `StructuredTool` with a Pydantic `args_schema`.

`bind_quarter_financial_metric_tool` calls `model.bind_tools([tool])`.
Selected arguments are validated with `QuarterFinancialMetricInput` and
then normalized. The tool itself queries PostgreSQL; the model does not
compute the metric.

## Structured output

News classification and recommendation both use
`with_structured_output` against Pydantic models. Malformed payloads
raise `NewsClassificationError` or `RecommendationGenerationError`.

Recommendation parsing also checks:

* ticker matches the context;
* stance is one of the three allowed values;
* confidence is in `[0, 1]`;
* summary and the four views are non-empty;
* any model-supplied evidence identity exists in the context.

The stored `RecommendationResult.evidence` is the context evidence, not
the model’s copy.

## Provider boundary

`create_chat_model` calls LangChain `init_chat_model` with
`LLM_PROVIDER`, `LLM_MODEL`, and `LLM_TEMPERATURE` from settings. The
default local stack is Ollama + `llama3.1` at temperature `0`.

Domain objects (`RecommendationContext`, `NewsSignal`,
`ValuationMetrics`, `FinancialMetricResult`) do not import the provider.
Swapping the chat model should not require changing those dataclasses.

Yahoo market and news access is isolated behind `YahooMarketClient` and
`YahooNewsClient`. The frontend never calls Yahoo.

## Hallucination guards

* Prompts forbid inventing numbers, URLs, or sources.
* Tool execution returns database values, not model arithmetic.
* Evidence identities must match `source`, `kind`, and `reference`.
* Evaluation scores factual consistency, evidence grounding, and
  hallucination counts against the supplied context.
* Stance vocabulary is constrained so BUY / SELL / HOLD cannot pass as
  the stored stance.

See [evaluation.md](evaluation.md) for the measured baseline.
