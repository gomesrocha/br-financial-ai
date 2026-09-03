# Changelog

All notable changes to this study are documented here.

## [0.1.0] - 2026-09-02

First complete study snapshot: CVM ingestion through grounded
recommendation, FastAPI, Next.js dashboard, evaluation, and quality
hardening.

### Added

* CVM company metadata, DFP, and ITR ingestion with filing versions and
  `MIL` normalization
* Deterministic financial metrics, margins, P/S, and P/E
* Yahoo Finance market quote, historical prices, returns, volatility,
  and drawdown behind replaceable adapters
* Persisted Yahoo company news and structured LLM news classification
* Framework-independent financial tools with LangChain `StructuredTool`
  adapters and `bind_tools` selection
* `RecommendationContext` assembly and explainable
  `FAVORABLE` / `NEUTRAL` / `UNFAVORABLE` recommendation
* FastAPI health, company, financials, and analysis routes
* Next.js research dashboard with tracked-company home, on-demand AI
  analysis, and `/quality`
* Evaluation datasets, metrics, stability, latency, token reporting,
  timestamped history, FAST/FULL profiles, and `/quality` trends
* Ticker-based company onboarding with persisted jobs and B3 discovery
* Lightweight `GET /api/v1/market/quote/{ticker}` for home cards

### Changed

* Quality hardening: quarter/metric tool-selection aliases, factual
  evaluator display matching, concurrent news classification, compact
  recommendation prompts with BRL amount scales, and one generation
  retry when numeric claims are ungrounded or evidence is not in context
* Factual evaluator ignores ISO/calendar dates and treats unsupported
  P/B or EV/EBITDA mentions as grounded when described as unavailable
  or lacking support, while still rejecting numeric assertions
* Ticker discovery falls back from B3 ListedCompanies to the official
  InstrumentsConsolidated public file plus CVM `cad_cia_aberta.csv`
  when the listed-company host is unavailable, without using Yahoo for
  issuer identity
* Dashboard `GET /api/v1/analysis/context/{ticker}` is deterministic and
  does not invoke an LLM. News classifications are cached as
  `NewsArticleSignal` rows and filled in only by `POST /api/v1/analysis`
* `/quality` reads exported eval history (latest, index, timestamped
  runs) and does not execute models
* Financial metrics are selected by `FinancialProfile` from official CVM
  `SETOR_ATIV`. Banks use a distinct net-income mapping; industrial
  revenue is not applied to financial institutions

### Notes

* Output is informational. It is not personalized investment advice and
  does not predict future prices.
