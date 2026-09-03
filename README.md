# BR Financial AI

AI Engineering study for Brazilian financial-market analysis.

The system combines CVM structured financial data, deterministic
financial calculations, Yahoo Finance market data, Yahoo company news,
structured LLM tool use, news classification, grounded recommendation
context, explainable recommendation, deterministic validation, AI
evaluation, observability, FastAPI, and a Next.js frontend.

It does **not** predict future stock prices. Recommendation stance is
`FAVORABLE`, `NEUTRAL`, or `UNFAVORABLE` — an analytical outlook, not
BUY / HOLD / SELL, and not a trading instruction.

This is a local research laboratory. Output is informational and is not
personalized financial advice.

Version **0.1.0**. Licensed under the [Apache License 2.0](LICENSE).
The Git tag `v0.1.0` is the authoritative release identifier.

## Overview

Given a B3 ticker such as PETR4, the study can:

1. Load CVM annual and quarterly statements from PostgreSQL.
2. Fetch a Yahoo quote and price history at request time.
3. Attach persisted company news with structured LLM classifications.
4. Build a `RecommendationContext` with explicit evidence identifiers.
5. Optionally ask a local LLM to interpret that context as an explainable
   recommendation.
6. Serve the result from FastAPI to a Next.js dashboard.

Numbers come from filings, Yahoo adapters, and Python. The LLM selects
tools, classifies news, and writes the narrative.

## Why this project exists

The goal is to practice AI Engineering on a realistic Brazilian-market
pipeline: provider adapters, deterministic domain logic, structured
model I/O, grounding, evaluation, and a thin UI. It is feature-complete
as a study, not a brokerage product.

## Architecture

```text
Ticker
 ↓
Local Security
 ↓ fallback if needed
B3 ListedCompanies
 ↓
B3 Instruments + CVM fallback
 ↓
Company / Securities
 ↓
DFP / ITR
 ↓
TrackedCompany
```

```text
CVM / B3 / Yahoo
      ↓
clients / adapters
      ↓
normalization
      ↓
PostgreSQL / deterministic services
      ↓
framework-independent tools
      ↓
AI adapters
      ↓
RecommendationContext
      ↓
RecommendationEngine
      ↓
FastAPI
      ↓
Next.js
```

See [docs/architecture.md](docs/architecture.md) for Mermaid diagrams of
the system, the deterministic-versus-AI boundary, the recommendation
pipeline, and the evaluation loop.

## Core principles

* LLM is not the source of truth for financial numbers.
* Domain objects are model-independent.
* Evidence must be identifiable and validatable.
* Stance is analytical, never a trade order.
* Default tests stay deterministic; model evals are explicit and slow.

## Features

* CVM DFP / ITR ingestion and exact-period queries
* `FinancialProfile` from official CVM `SETOR_ATIV` (`NON_FINANCIAL` vs
  `FINANCIAL_INSTITUTION`)
* Deterministic metrics: industrial P&L, bank intermediation, margins,
  P/S, P/E (no P/B, ROE, or ROA)
* Yahoo quote, OHLC history, period return, volatility, max drawdown
* Persisted news plus cached `NewsArticleSignal` classification
* Structured tool selection for quarterly metric questions
* Grounded recommendation with limitations and evidence
* FastAPI + Next.js research UI with tracked-company home cards
* Ticker-based company onboarding (B3 discovery, no LLM)
* FAST/FULL evaluation, quality gates, and `/quality`

## Data sources

CVM (company metadata, DFP, ITR, `MIL` scale), B3 securities, and Yahoo
Finance via `yfinance` adapters. Yahoo is not an official licensed
production feed for this application. Details:
[docs/data-sources.md](docs/data-sources.md).

## AI engineering design

Deterministic code owns accounting values, period resolution, ratios,
and market statistics. The LLM owns tool selection, news labels, and
recommendation wording. See
[docs/ai-engineering.md](docs/ai-engineering.md).

## Recommendation pipeline

```text
Dashboard GET /api/v1/analysis/context/{ticker}
→ deterministic CVM + Yahoo + cached NewsArticleSignal
→ no LLM

Generate AI analysis POST /api/v1/analysis
→ classify only missing NewsSignals
→ persist successful rows
→ RecommendationEngine
```

`GET` never invokes Ollama. `POST` is the explicit AI path.

## Evaluation results

FAST and FULL write timestamped history, `latest.json`, quality gates,
and a comparison to the previous run of the **same** profile.
`/quality` only displays exported JSON.

```text
FAST/FULL eval
 → historical report
 → quality gates
 → /quality
```

Current numbers live in `evals/reports/latest.json`. Tables:
[docs/evaluation.md](docs/evaluation.md).

## Performance

Instrumented analysis path in the same report (local `llama3.1`):

```text
news classification: 66.9141 s
recommendation: 103.8926 s
total analysis: 171.892 s
```

HTTP E2E for PETR4 was 227.7242 s. These times are local-inference
latency, not an SLA.

## Backend setup

Python 3.13+ and `uv`. Full commands:
[docs/local-development.md](docs/local-development.md).

```bash
uv sync
```

## Database setup

```bash
docker compose up -d
uv run alembic upgrade head
```

Compose publishes PostgreSQL on host port **5438** by default. Align
`DATABASE_URL` with that port (see `.env.example`).

## Data bootstrap

```bash
uv run br-financial-ai bootstrap
uv run br-financial-ai sync-news PETR4 --limit 10
```

## Ollama setup

Default model: `llama3.1` (`LLM_MODEL`). `ollama pull llama3.1` then
`ollama list` (or `curl http://127.0.0.1:11434/api/tags`).

## Running the API

```bash
uv run uvicorn br_financial_ai.main:app --reload
```

Health: `GET /health`. Override the port with `--port` if 8000 is taken,
and set the frontend `NEXT_PUBLIC_API_BASE_URL` to the same origin.

Home-page APIs (no LLM): `GET /api/v1/companies/tracked`,
`GET /api/v1/market/quote/{ticker}`, `POST /api/v1/companies/onboard`,
`GET /api/v1/companies/onboarding/{job_id}`. Onboarding continues in an
in-process background task and is not durable across process crashes.

## Running evals

```bash
uv run br-financial-ai eval --profile fast --fail-on-regression
uv run br-financial-ai eval --profile full --fail-on-regression
uv run br-financial-ai eval-export
```

FAST is a representative subset. FULL is the complete external suite.
Default `uv run pytest -q` stays deterministic. Evals write timestamped
history under `evals/reports/history/`, update `latest.json`, and copy
artifacts to the frontend `public/evals/` folder when present.

See [docs/evaluation.md](docs/evaluation.md) for quality gates, cadence,
and `/quality` versus LangSmith.

## Frontend

Sibling repo `../br-financial-ai-web`. Routes: `/` (tracked-company
cards), `/companies/[ticker]`, `/quality`. The home page uses
`GET /api/v1/companies/tracked` and optional live quotes. It does not
build analysis context or call Ollama. The company dashboard loads
context immediately; AI recommendation is user-triggered.

## Observability / LangSmith

LangSmith is optional individual AI trace debugging (prompt, model,
tokens, tool calls). Tracing is off unless environment variables are
set (`LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` and API keys). Local
tests and everyday runs leave them unset.

`/quality` is historical system-quality observability (accuracy,
grounding, hallucination, latency, tokens, regression). It reads
exported JSON only and does not run evals.

`NEWS_CLASSIFICATION_CONCURRENCY` defaults to 3.

## Project structure

```text
src/br_financial_ai/
├── ai/              LLM adapters: tools, news classifier, recommendation
├── api/             FastAPI routers and dependencies
├── clients/         CVM, B3, Yahoo adapters
├── core/            Settings
├── db/              Engine, session, SQLModel tables
├── domain/          Model-independent financial, market, news, recommendation types
├── eval/            Metrics, grounding, FAST/FULL reports, history
├── observability/   Timing, tracing config, token usage
├── parsers/         CVM financial row parsing
├── repositories/    PostgreSQL access
├── schemas/         API Pydantic models
├── services/        Ingestion, query, valuation, context assembly
└── tools/           Framework-independent financial tools
```

Also: `config/` (monitored companies), `migrations/`, `evals/`, `docs/`,
`tests/`.

## Known limitations

* Local Ollama first-run (cold model) can take many minutes
* Recommendation inference is slow on local `llama3.1` (often ~45–100 s
  per call; instrumented FULL analysis was ~172 s)
* FAST eval is a real-model suite (~4–5 minutes when warm)
* News and market data depend on Yahoo / `yfinance`
* Company discovery and filings depend on B3 and CVM network availability
* In-process onboarding after HTTP 202 is not crash-durable
* No P/B, EV/EBITDA, DCF, target price, ROE, ROA, or Basel metrics
* Bank statements do not expose industrial revenue, gross profit, or
  gross/operating/net margin; those cards are not applicable
* No personalized advice, portfolio optimization, or brokerage integration
* LangSmith tracing is optional; live traces require credentials
* Stance is analytical, not a trading instruction

## Post-v0.1.0 roadmap

Possible future work (not implemented):

```text
company comparison
recommendation history
scheduled analyses
watchlists
multi-model evaluation
multi-provider market/news
additional FinancialProfiles
advanced banking metrics
portfolio analytics
```

## Disclaimer

Informational research software only. Not investment advice. Not a
prediction of future prices. Not a substitute for a licensed analyst or
advisor.

Further reading: [CHANGELOG.md](CHANGELOG.md),
[docs/architecture.md](docs/architecture.md),
[docs/ai-engineering.md](docs/ai-engineering.md),
[docs/evaluation.md](docs/evaluation.md),
[docs/data-sources.md](docs/data-sources.md),
[docs/local-development.md](docs/local-development.md).
