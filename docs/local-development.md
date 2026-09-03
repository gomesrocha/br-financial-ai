# Local development

Reproducible setup for the backend study and the sibling Next.js app.

## Prerequisites

* Python 3.13+
* [uv](https://docs.astral.sh/uv/)
* Docker Compose
* [Ollama](https://ollama.com/) with the configured model
* Node.js 20+ for the frontend

## Backend

```bash
uv sync
docker compose up -d
```

`compose.yaml` starts PostgreSQL (`pgvector/pgvector`) and publishes it
on host port **5438** by default (`POSTGRES_PORT`, container port 5432).

Copy `.env.example` to `.env` and keep `DATABASE_URL` on the same host
port as Compose:

```text
DATABASE_URL=postgresql+psycopg://br_financial_ai:br_financial_ai@localhost:5438/br_financial_ai
```

Then:

```bash
uv run alembic upgrade head
uv run br-financial-ai bootstrap
```

After migration `a1c4e7f092b3`, existing `companies` rows have
`setor_ativ` NULL until the next `sync-company` (or onboarding of a new
issuer). That official CVM activity field selects `FinancialProfile`.
Re-run `sync-company` for already ingested CVM codes so banks such as
Itaú and Bradesco resolve as `FINANCIAL_INSTITUTION`. Metadata refresh
is committed by `CompanySyncService`.


`bootstrap` reads `config/monitored_companies.yaml` unless
`--config PATH` is passed. It syncs companies, B3 securities, DFP, and
ITR for the configured CVM codes, then upserts `TrackedCompany` rows
from each `preferred_ticker`. Repeated bootstrap does not duplicate
tracked rows.

Add a company later from the UI (`POST /api/v1/companies/onboard`) or
keep using CLI `sync-*` commands. Onboarding runs in-process after HTTP
202 and is not durable across API process crashes.

Persist Yahoo news after bootstrap (required for the PETR4 dashboard
news section and live evals):

```bash
uv run br-financial-ai sync-news PETR4 --limit 10
```

Other CLI commands that exist:

```bash
uv run br-financial-ai sync-company 9512
uv run br-financial-ai sync-securities 9512
uv run br-financial-ai sync-financials 9512 --type DFP --year 2025
uv run br-financial-ai --help
```

## Ollama

Settings default to:

```text
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_TEMPERATURE=0
```

Pull and verify:

```bash
ollama pull llama3.1
ollama list
```

A running daemon typically listens on `127.0.0.1:11434`.
`curl http://127.0.0.1:11434/api/tags` should list `llama3.1`.

## Running the API

Uvicorn’s default bind is port 8000:

```bash
uv run uvicorn br_financial_ai.main:app --reload
```

If 8000 is already in use, choose another port:

```bash
uv run uvicorn br_financial_ai.main:app --reload --host 127.0.0.1 --port 8001
```

Health check (no `/api` prefix):

```bash
curl http://127.0.0.1:8000/health
# or, if you overrode the port:
curl http://127.0.0.1:8001/health
```

Expected body includes `"status": "ok"`.

Context smoke (deterministic; does not invoke Ollama):

```bash
curl http://127.0.0.1:8000/api/v1/analysis/context/PETR4
```

`POST /api/v1/analysis` is the explicit AI path: it classifies only
uncached news, persists `NewsArticleSignal` rows, then runs the
recommendation engine.

Point the frontend at the same origin you actually bound. CORS defaults
allow `http://localhost:3000` and `http://127.0.0.1:3000` via
`CORS_ORIGINS`.

## Frontend

Sibling repository:

```text
../br-financial-ai-web
```

```bash
cp .env.example .env.local
```

`NEXT_PUBLIC_API_BASE_URL` must match the API origin, including a
non-default port:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
```

If the variable is unset, the UI falls back to `http://localhost:8000`.

```bash
npm install
npm run dev
```

The Next.js dev server defaults to port 3000. Open `/`,
`/companies/PETR4`, and `/quality`.

## Deterministic tests

Backend (no Yahoo, Ollama, or LangSmith):

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Frontend:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Model and provider evals are separate. FAST and FULL commands,
history, and `/quality` are documented in [evaluation.md](evaluation.md).
