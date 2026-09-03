# Evaluation

This document describes how quality is measured, how reports are stored
over time, and what the **current accepted baseline** reports. Numeric
values below are taken from `evals/reports/latest.json`. If that file is
regenerated, trust the file, not a stale copy of this page.

## Deterministic tests versus model/provider evals

| Suite | Command | Needs |
| --- | --- | --- |
| Backend unit/integration | `uv run pytest -q` | PostgreSQL for integration tests; no Yahoo/Ollama |
| Frontend | `npm test` | Mocked `fetch`; no backend |
| FAST eval | `uv run br-financial-ai eval --profile fast` | Ollama; representative subset |
| FULL eval | `uv run br-financial-ai eval --profile full` | Local data, Yahoo, Ollama; complete suite |

`pyproject.toml` sets `testpaths = ["tests"]`, so default pytest never
runs `evals/`. Markers: `eval`, `slow`, `external`, `ollama`, `yahoo`.

FAST and FULL are the supported profile commands. They reuse the same
aggregation and report writer. Equivalent pytest forms:

```bash
EVAL_PROFILE=fast uv run pytest evals -q
EVAL_PROFILE=full uv run pytest evals -q
```

`EVAL_PROFILE=fast` skips eval files that are not in the FAST allowlist.
Ordinary `uv run pytest -q` is unchanged and still excludes
external/model-dependent evals.

Optional quality-gate failure:

```bash
uv run br-financial-ai eval --profile fast --fail-on-regression
```

That fails only when required quality thresholds are violated
(`status=FAIL`). Latency movement is not a hard failure.

## Profiles

### FAST

Frequent quality-regression check. It still calls production
`bind_tools`, `NewsClassifier`, and `RecommendationEngine`. Mocks stay
in deterministic unit tests.

FAST fixtures and the regression each one guards:

Tool (5):

* `petr4_revenue_long_pt` — canonical Portuguese phrasing
* `petr4_revenue_2t26` — compact quarter form (`2T26`)
* `petr4_net_income_2q` — metric alias (`lucro líquido` → net income)
* `petr4_gross_profit_q1` — different metric and Q1
* `vale3_revenue_q2` — different company

News (4):

* `company_specific_positive` — company-specific constructive article
* `company_specific_adverse` — company-specific accident/adverse article
* `sector_event` — sector/oil move, not company-specific
* `macro_event` — macro/rates, different issuer

`weak_mention` / `irrelevant_mention` remain FULL-only. Adding them to
FAST would add Ollama calls without a distinct production boundary
beyond LOW relevance, which sector/macro already exercise as
non-company-specific.

Recommendation (3):

* `strong_favorable` — favorable stance
* `mixed` — mixed/neutral evidence
* `strong_unfavorable` — unfavorable stance

Stance, factual, grounding, and hallucination checks reuse **one**
generated recommendation per fixture. Grounding in `test_grounding.py`
is deterministic and does not call Ollama.

Independent fixtures can run with bounded concurrency
(`EVAL_LLM_CONCURRENCY`, default 1, max 8). On local Ollama, 2 did not
reduce wall time (requests serialized). Raise only if the runtime
actually overlaps work (`OLLAMA_NUM_PARALLEL`). Results stay aligned to
fixture ids in dataset order.

Suite timings are stored under `eval_performance` and must not be
confused with production `performance.total_analysis_latency`:

* `fast_eval_total_seconds`
* `tool_selection_eval_seconds`
* `news_eval_seconds`
* `recommendation_eval_seconds`
* `report_generation_seconds`

Excludes stability, Yahoo E2E, extra case files, and frontend smoke.

### FULL

The complete current external/model evaluation suite:

* full tool-selection, news-classification, and recommendation datasets
* grounding, hallucination, stability
* Yahoo/provider checks where applicable
* real E2E where applicable
* latency and token/usage capture

FULL coverage is not reduced to create profiles. FAST vs FULL numbers
are **not** directly comparable: the datasets differ.

## Report identity and history

Every completed run writes an `EvalRun` object:

```json
{
  "id": "2026-09-02T174658Z",
  "timestamp": "2026-09-02T17:46:58Z",
  "profile": "full",
  "model_provider": "ollama",
  "model_name": "llama3.1",
  "git_commit": null,
  "git_branch": null
}
```

* timestamps are UTC and timezone-aware
* run IDs are filesystem-safe (`YYYY-MM-DDTHHMMSSZ`)
* model/provider come from application settings, not a hardcoded model
  name in the writer
* git metadata is optional; missing git does not fail report generation

Layout:

```text
evals/reports/
├── latest.json
├── latest.md
└── history/
    ├── index.json
    ├── 2026-09-02T174658Z.json
    └── ...
```

Flow:

```text
FAST/FULL eval
     ↓
EvalReport
     ↓
history/
     ↓
index.json
     ↓
frontend export
     ↓
/quality
```

`history/index.json` is newest-first and stores compact summaries only.
It does not duplicate the full report. Malformed history files are
skipped.

Regression comparison uses the previous run with the **same** profile
(FAST vs previous FAST, FULL vs previous FULL). FAST-vs-FULL deltas are
never labeled as regressions.

## Quality gates

Central thresholds live in `br_financial_ai.eval.thresholds`. They are
set from the accepted FULL baseline with headroom, not to make evals
permanently unpassable.

| Gate | Operator | Limit |
| --- | --- | --- |
| exact_tool_call_accuracy | >= | 0.95 |
| news_relevance_accuracy | >= | 0.90 |
| company_specific_accuracy | >= | 0.90 |
| stance_accuracy | >= | 0.80 |
| factual_consistency | >= | 0.95 |
| evidence_grounding | >= | 1.00 |
| true_hallucination_count | == | 0 |

News materiality (baseline 0.875) and sentiment agreement (0.875) are
reported but not hard gates. Unmeasured gates become warnings
(`PASS_WITH_WARNINGS`). Failed measured gates set `FAIL`. Missing token
counts stay `null`; they are never filled with zeros.

Overall status is `PASS`, `PASS_WITH_WARNINGS`, or `FAIL`. It is not
defined as “pytest exited zero”.

## Frontend export

```bash
uv run br-financial-ai eval-export
```

Eval runs export automatically unless `--no-export` or `EVAL_EXPORT=0`.
The command copies:

```text
br-financial-ai-web/public/evals/latest.json
br-financial-ai-web/public/evals/index.json
br-financial-ai-web/public/evals/history/*.json
br-financial-ai-web/public/evaluation-summary.json
```

The frontend never reads files outside its project directory and never
executes evals.

## `/quality` versus LangSmith

| Surface | Purpose |
| --- | --- |
| LangSmith | Individual AI trace debugging (prompt, model, latency, tokens, tool calls, structured output) |
| `/quality` | System quality over time (accuracy, grounding, hallucination, stability, latency trends, token trends, regression) |

Do not inspect traces in `/quality`. Do not treat `/quality` as a
LangSmith replacement.

## Suggested cadence

There is no in-app scheduler. External automation should call the CLI:

```bash
uv run br-financial-ai eval --profile fast --fail-on-regression
uv run br-financial-ai eval --profile full --fail-on-regression
```

Exit codes: `0` on success, non-zero when pytest failed or
`--fail-on-regression` saw `status=FAIL`. Suitable for cron, GitHub
Actions, or any other external scheduler. Do not add an application
scheduler.

* **FAST:** after important AI/prompt/tool changes, and before merging
  or releasing meaningful changes. Typical local/CI hook.
* **FULL:** periodically, before release, and after model/provider
  changes. A weekly FULL run is reasonable.

Optional `EVAL_LLM_CONCURRENCY=1` (default) bounds parallel Ollama
calls. `2` was slower on local Ollama because inference did not
overlap. Raise only if the local runtime actually overlaps work
(`OLLAMA_NUM_PARALLEL`).

## How reports are generated

`evals/conftest.py` persists `eval.runtime.RESULTS` through
`write_evaluation_summary`. That function:

1. archives the previous `latest.json` into `history/` if needed
2. writes an immutable timestamped JSON
3. updates `latest.json` and `latest.md`
4. rebuilds `history/index.json`
5. exports frontend artifacts when enabled

`latest.json` / `latest.md` plus tracked history files and
`history/index.json` are the accepted artifacts. Other history JSON
files remain generated scratch output.

## Historical runs in this repository

Newest-first `evals/reports/history/index.json` currently contains:

| Run | Profile | Status | Notes |
| --- | --- | --- | --- |
| `2026-09-03T001742Z` | FULL | FAIL | Release FULL attempt. `true_hallucination_count=1`. Immutable. |
| `2026-09-02T234957Z` | FAST | PASS | Release FAST. 5/4/3 cases. Compared to `2026-09-02T225152Z`. |
| `2026-09-02T225152Z` | FAST | PASS | Phase 17.1 concurrency measurement (not a git-tracked baseline). |
| `2026-09-02T220819Z` | FAST | PASS | First tracked FAST baseline. Immutable. |
| `2026-09-02T174658Z` | FULL | PASS | First tracked FULL baseline. Immutable. |

FAST and FULL datasets differ. Do not treat metric movement between
these two runs as a regression.

## Metrics in the accepted FULL baseline

Values below reflect `evals/reports/history/2026-09-02T174658Z.json`,
generated at `2026-09-02T17:46:58.809441+00:00`. The newest
`latest.json` may be a later FAST run.

### Tool selection (12 cases)

| Metric | Value |
| --- | --- |
| tool_name_accuracy | 1.0000 |
| argument_accuracy | 1.0000 |
| exact_call_accuracy | 1.0000 |

### News classification (8 cases)

| Metric | Value |
| --- | --- |
| relevance_accuracy | 1.0000 |
| materiality_accuracy | 0.8750 |
| company_specific_accuracy | 1.0000 |
| sentiment_agreement | 0.8750 |
| category_agreement | 1.0000 |

### Recommendation (9 cases)

| Metric | Value |
| --- | --- |
| stance_accuracy | 0.8889 |
| factual_consistency | 1.0000 |
| evidence_grounding | 1.0000 |
| hallucination_count | 0 |
| true_hallucination_count | 0 |
| evaluator_false_positive_count | 1 |

### Stability (5 PETR4 runs)

| Metric | Value |
| --- | --- |
| dominant_stance | NEUTRAL |
| stance_distribution | NEUTRAL 5 |
| stance_stability_ratio | 1.0000 |
| confidence_mean | 0.8000 |
| confidence_range | 0.0 |

### Latency (seconds, instrumented analysis path)

| Step | Seconds |
| --- | --- |
| yahoo_quote_latency | 0.5487 |
| yahoo_history_latency | 0.5217 |
| news_classification_latency | 66.9141 |
| context_build_latency | 67.9994 |
| recommendation_latency | 103.8926 |
| total_analysis_latency | 171.892 |

HTTP E2E for PETR4 in the same report: 227.7242 s total
(context 71.7088 s, analysis 156.0154 s), stance NEUTRAL, confidence 0.8.

### Token usage (from application settings / provider metadata)

Local inference has `estimated_cost: null`. The UI shows
“Cost not available for local provider”, never `$0.00`.

| Call | input | output | total |
| --- | --- | --- | --- |
| tool_selection | 336 | 43 | 379 |
| news_classification | 432 | 83 | 515 |
| recommendation (dataset) | 736 | 260 | 996 |
| e2e_recommendation | 1744 | 417 | 2161 |

Dataset recommendation prompt characters: 1406. Instrumented E2E prompt
characters: 5353.

## Restore local data before live E2E

```bash
uv run alembic upgrade head
uv run br-financial-ai bootstrap
uv run br-financial-ai sync-news PETR4 --limit 10
```

## Phase 13 hardening (historical comparison)

The table below is the accepted before/after snapshot from the Phase 13
hardening run. **After** matches the FULL baseline in
`evals/reports/history/2026-09-02T174658Z.json`. **Before** is the
pre-hardening measurement from that same study cycle.

| Metric | Before Phase 13 | After (`latest.json`) |
| --- | --- | --- |
| exact tool-call accuracy | 0.8333 | 1.0000 |
| factual consistency (dataset) | 0.9444 | 1.0000 |
| PETR4 factual consistency | 0.6667 | 1.0000 |
| true hallucinations | 1* | 0 |
| news classification latency | ~122.89 s | 66.9141 s |
| recommendation latency | ~151.14 s | 103.8926 s |
| total analysis latency | ~275.48 s | 171.892 s |

\*The pre-hardening hallucination flag was later classified as an
evaluator false positive (`evaluator_false_positive_count` is 1 in the
current report). True hallucinations in the accepted baseline are 0.

Hardening that produced this baseline included metric-alias fixes for
tool selection, display-form factual matching, bounded news
classification concurrency, and a compact recommendation prompt. Domain
`RecommendationContext` was not reduced.
