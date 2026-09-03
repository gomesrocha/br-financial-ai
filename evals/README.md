# Evals

External, non-deterministic checks. They are not part of
`uv run pytest -q`.

See [docs/evaluation.md](../docs/evaluation.md) for metrics, quality
gates, history, and the accepted baseline.

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

## Commands

```bash
uv run br-financial-ai eval --profile fast
uv run br-financial-ai eval --profile full
uv run br-financial-ai eval --profile fast --fail-on-regression
uv run br-financial-ai eval-export
```

Equivalent pytest:

```bash
EVAL_PROFILE=fast uv run pytest evals -q
EVAL_PROFILE=full uv run pytest evals -q
```

FAST runs `test_tool_selection_dataset.py`,
`test_news_classification_dataset.py`,
`test_recommendation_dataset.py`, and `test_grounding.py` with the
`fast: true` dataset subset. Independent cases use bounded concurrency
(`EVAL_LLM_CONCURRENCY`, default 1). One generated recommendation is
reused for stance, factual, grounding, and hallucination checks.

External automation:

```bash
uv run br-financial-ai eval --profile fast --fail-on-regression
uv run br-financial-ai eval --profile full --fail-on-regression
```

Exit code 0 means tests and quality gates passed. Non-zero is safe for
cron, GitHub Actions, or another external scheduler. There is no
in-app scheduler.

FULL runs the complete `evals/` suite, including stability, Yahoo,
E2E, and extra case files.

Markers: `eval`, `slow`, `external`, `ollama`, `yahoo`.

Reports:

* `evals/reports/latest.json` / `latest.md`
* immutable `evals/reports/history/<run-id>.json`
* compact newest-first `evals/reports/history/index.json`

If the sibling frontend exists, artifacts are copied to
`br-financial-ai-web/public/evals/` (and `evaluation-summary.json` for
compatibility). `/quality` only displays those files.

Restore local data before live E2E:

```bash
uv run alembic upgrade head
uv run br-financial-ai bootstrap
uv run br-financial-ai sync-news PETR4 --limit 10
```

LangSmith is optional individual-trace debugging. Leave tracing
environment variables unset for local tests. `/quality` is historical
system-quality observability, not a trace viewer.
