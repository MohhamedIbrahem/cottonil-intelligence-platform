# Cottonil — Data, AI & Business Intelligence Project

> Implementation of **HVIA Task 3** using the Cottonil dataset: data foundation, core dashboards, and an AI-powered business assistant — per the concept deck (`COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf`, 23 pages).

## Quickstart (Features 001–004 verified)

```powershell
uv sync                 # create venv + install deps (python 3.12)
uv run build            # load COTTONIL_Data CSVs -> data/cottonil.duckdb (25 tables + 26 views)
uv run checks           # data-quality gate: 34 integrity/reconciliation checks
uv run pytest           # pipeline + analytics + pages + assistant tests (DB required; ~3-4 min)
uv run streamlit run app/Home.py   # the dashboard app (needs the build first)
```

- View definitions live in `pipeline/views/` (numbered, applied in order); the auto-generated contract doc is [`pipeline/VIEW_CATALOG.md`](pipeline/VIEW_CATALOG.md).
- Metric definitions + anomaly policies: [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md).

## Runbook

**App pages** (`streamlit run app/Home.py`, multipage):
1. **Executive Overview** — period KPIs with same-window YoY, monthly trend, top-5 branches, governorate share, category/channel mix.
2. **Sales Performance** — category-filterable trend, top-15 products, AOV/items-per-order cards.
3. **Branch & Governorate** — growth-colored ranking, quadrant scatter, governorate growth bar.
4. **Inventory & Stock** — latest-month snapshot vs period trend, status buckets, risk alerts.
5. **Customers** — RFM tier table, top-LTV, profile mixes, customer lookup.
6. **Assistant** — bilingual chat (EN/AR), every answer shows its SQL + sources, deep-link buttons.
7. **Supply Chain & Logistics** — shipment status/delayed rate, carrier comparison, destination governorates, transfer pipeline.
8. **Procurement & Suppliers** — supplier scorecard, lead times, on-time proxy, material mix (PO value is absolute-only, A1).
9. **Returns & Quality** — return-rate trend, reason mix, capped refunds, category and governorate analysis (A3).
10. **Marketing ROI** — spend, CTR, ROAS, CPA, budget utilization, channel comparison (rebuilt attribution, A2).
11. **Wholesale & Distributors** — wholesale channel trend, B2B account value, recency and concentration (no sell-out data).
12. **Demand Forecast** — category demand, 6-month Holt-Winters forecast, rolling-origin WAPE and empirical planning band; units default (A15).
13. **Price & Promotion** — discount depth, margin link, within-SKU price-response test reported as a failed signal (A11).
14. **Omnichannel (Lite)** — three real channels, mix, AOV, margin, returns and observed cross-channel customers; no sessions/carts/app users.
15. **Product Profitability** — SKU-month margin distribution, low-margin review alerts, top products by gross profit (A13).
16. **Smart Replenishment** — latest-snapshot 45-day cover rule, reorder priorities, overstock review (rules, not an optimiser; A14).
17. **CLV & Churn** — historical gross-profit CLV, concentration, churn status, temporal churn holdout reported as unpredictable (A12).
18. **Workforce Productivity (Lite)** — payroll-covered headcount, labor cost ratio, branch payroll detail; reference year 2023; no hours/FTE/service data (A16).
19. **Store Expansion (Gap Proxy)** — governorate coverage intensity, resident demand vs branch POS; no demographics/competitors/rent/catchment (A17).

**Assistant LLM** (cloud provider chain — no local server needed):

- **Primary:** Google **Gemini** — `GEMINI_API_KEY` + `GEMINI_MODEL` in `.env`
- **Fallback:** **Groq** — `GROQ_API_KEY` + `GROQ_MODEL` in `.env`; used automatically when Gemini fails (quota exhausted, rate limit, outage)

```powershell
uv run streamlit run app/Home.py    # keys are read from .env on startup
```

Optional `.env` overrides (see `.env.example`): `COTTONIL_LLM_BASE_URL/_MODEL/_API_KEY` (primary) and `COTTONIL_LLM_FALLBACK_*` (fallback), plus `COTTONIL_LLM_TIMEOUT`, `COTTONIL_SQL_TIMEOUT`.

**Quality gates**

| Command | Gate |
|---|---|
| `uv run checks` | 34 DQ gates (27 FK/orphan + 7 financial reconciliations) |
| `uv run pytest tests/test_pipeline.py` | exact rowcounts + view integrity + anomaly caps |
| `uv run pytest tests/test_analytics.py` | forecast/elasticity/churn mechanics on synthetic data + real-data checks |
| `uv run pytest tests/test_pages_smoke.py` | every page × 3 period modes renders clean |
| `uv run pytest tests/test_pages_perf.py` | every page < 3 s render |
| `uv run pytest tests/test_assistant.py -q -s` | SQL guard, refusal tests, goldset mechanics + live 20-question goldset (release gate ≥ 80% — runs against Gemini/Groq when the chain is up) |

**Troubleshooting**
- `data/cottonil.duckdb not found` → run `uv run build` first (requires the CSVs under `COTTONIL/COTTONIL_Data/`).
- Assistant banner "LLM is not reachable" → check the provider table on the banner, verify `GEMINI_API_KEY` / `GROQ_API_KEY` in `.env`, reload the page; engine is read-only regardless. Quota-exhausted primary → the chain falls back to Groq automatically (answers are captioned "via Groq (fallback)").
- Rebuilding while the app is open on Windows may hit a file lock → stop the streamlit process, rebuild, restart.

## What this repo is

| Area | Where |
|---|---|
| Master project plan (phases, scope, timeline) | [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) |
| Dataset audit + metric dictionary + anomaly policies | [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md) |
| All 21 dashboards from the deck × data availability → build order | [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) |
| Current feature (Core 5 dashboards + AI assistant): spec/plan/tasks | [`specs/001-core-platform/`](specs/001-core-platform/) |
| Feature 002 scope (supply, procurement, returns, marketing, wholesale) | [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) |
| Feature 003 scope (forecast, pricing, omnichannel, profitability, replenishment, CLV) | [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) |
| Feature 004 scope (workforce-lite, store-expansion gap proxy) | [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) |
| Spec-kit process (constitution) | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |

## Source of truth

- Concept deck: `COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf` — design language only (see Principle II in the constitution: numbers in the deck are illustrative; the real dataset differs: 80 branches, 85K customers, 540K orders to 2026-10-18).
- Dataset: `COTTONIL/COTTONIL_Data/` (25 CSVs). Kept out of git (large); place it at that path.
