# Cottonil — Data, AI & Business Intelligence Project

> Implementation of **HVIA Task 3** using the Cottonil dataset: data foundation, core dashboards, and an AI-powered business assistant — per the concept deck (`COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf`, 23 pages).

## Quickstart (feature 001 verified ✅)

```powershell
uv sync                 # create venv + install deps (python 3.12)
uv run build            # load COTTONIL_Data CSVs -> data/cottonil.duckdb (25 tables + 14 views)
uv run checks           # data-quality gate: 34 integrity/reconciliation checks
uv run pytest           # pipeline + pages + assistant tests (DB required; ~40 s)
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
| Spec-kit process (constitution) | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |

## Source of truth

- Concept deck: `COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf` — design language only (see Principle II in the constitution: numbers in the deck are illustrative; the real dataset differs: 80 branches, 85K customers, 540K orders to 2026-10-18).
- Dataset: `COTTONIL/COTTONIL_Data/` (25 CSVs). Kept out of git (large); place it at that path.
