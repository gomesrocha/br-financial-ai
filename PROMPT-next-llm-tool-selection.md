# Cursor task — first LLM tool-selection checkpoint

Use the `implement-llm-tool-selection` skill and obey all project Rules in `.cursor/rules`.

## Context

The project already has a deterministic quarterly financial metric path:

`QuarterFinancialMetricInput`
→ LangChain `StructuredTool`
→ `get_quarter_financial_metric`
→ `FinancialQueryService`
→ PostgreSQL

The direct `StructuredTool.ainvoke()` path is already implemented and tested.

The current baseline is green with 80 tests passing. Existing pytest-bdd compatibility warnings are known and must not be hidden by unrelated changes.

## Objective

Connect ONE LLM to the existing `get_quarter_financial_metric` tool using LangChain `bind_tools()` and prove ONLY that the model selects the correct tool and produces the correct arguments.

Target question:

> Qual foi a receita da PETR4 no segundo trimestre de 2026?

Expected tool call:

```json
{
  "name": "get_quarter_financial_metric",
  "args": {
    "ticker": "PETR4",
    "metric": "revenue",
    "year": 2026,
    "quarter": 2
  }
}
```

## Constraints

Do NOT implement yet:

- agent executor;
- autonomous agent loop;
- memory;
- RAG;
- vector retrieval;
- multiple tools;
- tool execution orchestration;
- final natural-language answer generation;
- UI/API endpoint for the LLM flow.

Do not duplicate business logic in the AI layer.

Do not expose SQL, repositories, CVM account codes, or `AsyncSession` to the LLM.

Do not hardcode provider API keys.

Before selecting or adding an LLM provider dependency, inspect `pyproject.toml` and the existing settings/configuration. Reuse what is already available when appropriate.

## Testing strategy

Separate deterministic software tests from model-dependent evals.

- Unit-test deterministic helper/provider-binding code where possible.
- If proving actual model tool selection requires a remote LLM call, put that check under `evals/`.
- Do not make the normal `pytest` suite depend on network/API availability.
- Preserve current LangSmith integration if present, but do not make LangSmith mandatory for ordinary tests.

## Required sequence

1. Inspect existing AI/tool code, settings, and `pyproject.toml`.
2. Propose the smallest file changes required.
3. Implement a small provider/model construction boundary if one does not exist.
4. Bind only `get_quarter_financial_metric`.
5. Add the minimum deterministic tests.
6. Add one focused model-dependent eval for the target question if a real LLM call is required.
7. Run focused tests.
8. Run Ruff.
9. Run the full deterministic test suite.

## Required final evidence

Report:

- files created/changed;
- model/provider selected and why;
- exact bound tool name;
- exact tool-call arguments produced;
- focused test/eval results;
- `uv run ruff check .` result;
- `uv run ruff format --check .` result;
- `uv run pytest -q` result.

## Stop condition

STOP after proving tool selection and correct argument extraction.

Do not continue to tool execution or final answer generation.
