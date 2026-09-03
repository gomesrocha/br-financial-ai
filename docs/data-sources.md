# Data sources

## CVM

The study ingests public CVM company metadata and financial statements.

| Input | Role |
| --- | --- |
| Company metadata | CVM code, CNPJ, legal name, trade name, `SETOR_ATIV`, active flag |
| DFP | Annual financial statements |
| ITR | Quarterly financial statements |
| Filing versions | Latest accepted version for a document type and period is stored |
| Accounting periods | Exact period end dates, not calendar approximations |
| Currency scale | `MIL` and `UNIDADE` |

`parsers.cvm_financial` reads CVM rows including `ESCALA_MOEDA`.
`cvm_amount_to_brl` multiplies `MIL` values by 1,000 so they are
comparable to Yahoo market capitalization in BRL units.

CLI:

```bash
uv run br-financial-ai sync-company 9512
uv run br-financial-ai sync-securities 9512
uv run br-financial-ai sync-financials 9512 --type DFP --year 2025
uv run br-financial-ai sync-financials 9512 --type ITR --year 2026
uv run br-financial-ai bootstrap
```

`bootstrap` uses `config/monitored_companies.yaml` by default (CVM codes
`9512`, `906`, `4170`; DFP 2025; ITR 2026).

## B3

`B3Client` synchronizes listed securities for a CVM code so tickers such
as `PETR4` can be resolved to a company. Yahoo symbols are derived from
those B3 tickers.

Ticker onboarding (`POST /api/v1/companies/onboard`) resolves a ticker through
`CompositeTickerDiscovery`:

1. Local `Security` / `Company` rows (primary cache).
2. B3 ListedCompanies (`sistemaswebb3-listados.b3.com.br` search + detail).
3. Official B3 **InstrumentsConsolidated** public file from
   `https://arquivos.b3.com.br/api/download/requestname?fileName=InstrumentsConsolidated`
   plus the CVM registry `cad_cia_aberta.csv`.

The InstrumentsConsolidated CSV (latin-1, `;`) exposes `TckrSymb`, `Asst`,
`SgmtNm`, `SctyCtgyNm`, `ISIN`, `CFICd`, and `CrpnNm`. Cash/share rows with a
12-character ISIN are kept. Sibling equities share `Asst` (ITUB3 + ITUB4).
`CrpnNm` is matched to exactly one **ATIVO** CVM legal or trade name after
deterministic normalization (case, accents, punctuation, `S.A.` spacing).
Ambiguous or inactive-only matches do not onboard.

Yahoo is not used for CVM identity. ListedCompanies uses a 3s connect / 8s
read timeout so an unreachable host fails fast and the official file fallback
can run. Company and Security rows remain the identity cache; no extra table.

Discovery errors stay distinct: `DISCOVERY_UNAVAILABLE`, `TICKER_NOT_FOUND`,
`DISCOVERY_AMBIGUOUS`.

## Yahoo Finance / yfinance

Market quote, historical prices, and company news go through provider
adapters:

* `YahooMarketClient` — quote, OHLC history, period metrics inputs
* `YahooNewsClient` — company news ingested into PostgreSQL.
  Structured AI labels for those articles are stored separately as
  `NewsArticleSignal` rows and are filled in only by explicit analysis,
  not by dashboard context.

`clients.yahoo.to_yahoo_symbol` normalizes a B3 ticker to the Yahoo
suffix `.SA` (`PETR4` → `PETR4.SA`). Incoming `.SA` symbols are stripped
and re-validated against the B3 equity ticker pattern.

Yahoo is isolated behind those adapters and is replaceable. The rest of
the domain speaks `MarketQuote`, `PriceBar`, and persisted `NewsArticle`
rows, not yfinance types.

The frontend never calls Yahoo. Sync news with:

```bash
uv run br-financial-ai sync-news PETR4 --limit 10
```

### Usage and licensing

This repository uses Yahoo Finance data through the community `yfinance`
library for a local study. That is not an official Yahoo licensed
production feed for this application. Review Yahoo’s terms and
`yfinance` guidance before any broader use. Do not assume redistribution
rights.

CVM and B3 data are public regulatory / exchange sources used here for
research. Redistribution and commercial use remain the caller’s
responsibility.

## Financial metric semantics

Account mappings live in `domain.financial_metrics` and depend on
`FinancialProfile`. The profile is resolved from persisted CVM
`SETOR_ATIV`, not from ticker names.

Industrial DRE codes (Petrobras, Vale) remain the `NON_FINANCIAL`
catalogue: revenue `3.01`, gross profit `3.03`, operating result `3.05`,
profit before tax `3.07`, net income `3.11`.

Inspected bank DRE trees (Itaú, Bradesco) share intermediation accounts
at `3.01`/`3.03` and profit before tax at `3.05`. Consolidated net income
is `3.11` when that slot exists (Bradesco) and `3.09` when the issuer
names that slot as lucro consolidado do período (Itaú). Those candidates
are profile-level, not ticker-specific. Industrial `revenue` is not
silently mapped to bank intermediation revenue.

`Company.setor_ativ` stores the official CVM activity string. `Bancos`
selects `FINANCIAL_INSTITUTION`. Unknown or missing activity stays
`NON_FINANCIAL` until a statement structure is inspected.

