# Cottonil Intelligence Platform

> **HVIA Task 3** — A full-stack data foundation, 19 interactive dashboards, and a bilingual AI business assistant built on the Cottonil retail dataset (25 CSVs → DuckDB → Streamlit).

---

## What We Built

### 🏗️ Data Foundation (Phase 1)

- **25 raw CSV tables** ingested into a local **DuckDB** database (`data/cottonil.duckdb`) via a reproducible build pipeline.
- **26 curated SQL views** (`pipeline/views/`) — numbered and applied in order — that transform raw data into analytics-ready datasets covering sales, branches, inventory, customers, supply chain, procurement, marketing, wholesale, demand, pricing, profitability, replenishment, CLV/churn, workforce, and store expansion.
- **34 data-quality gates** (`uv run checks`): 27 FK/orphan integrity checks + 7 financial reconciliation checks that run before any dashboard renders.
- Auto-generated **view contract catalog** ([`pipeline/VIEW_CATALOG.md`](pipeline/VIEW_CATALOG.md)) documenting every column, type, and source.

### 📊 19 Interactive Dashboards (Phases 2–5)

Every dashboard is a Streamlit page registered under **6 navigation groups**, with a shared global reporting-period filter (same-window YoY comparison) and a unified design system (1,097 lines in [`app/theme.py`](app/theme.py)).

| # | Dashboard | Key Features |
|---|---|---|
| 1 | **Executive Overview** | Period KPIs with YoY, monthly trend, top-5 branches, governorate share, category/channel mix |
| 2 | **Sales Performance** | Category-filterable trend, top-15 products, AOV/items-per-order cards |
| 3 | **Branch & Governorate** | Growth-colored ranking, quadrant scatter, governorate growth bar |
| 4 | **Inventory & Stock** | Latest-month snapshot vs period trend, status buckets, risk alerts |
| 5 | **Customer Intelligence** | RFM tier table, top-LTV customers, profile mixes, customer lookup |
| 6 | **Supply Chain & Logistics** | Shipment status/delayed rate, carrier comparison, destination governorates, transfer pipeline |
| 7 | **Procurement & Suppliers** | Supplier scorecard, lead times, on-time proxy, material mix |
| 8 | **Returns & Quality** | Return-rate trend, reason mix, capped refunds, category and governorate analysis |
| 9 | **Marketing ROI** | Spend, CTR, ROAS, CPA, budget utilization, channel comparison (rebuilt attribution) |
| 10 | **Wholesale & Distributors** | Wholesale channel trend, B2B account value, recency and concentration |
| 11 | **Demand Forecast** | Category demand, 6-month Holt-Winters forecast, rolling-origin WAPE, empirical planning band |
| 12 | **Price & Promotion** | Discount depth, margin link, within-SKU price-response test |
| 13 | **Omnichannel (Lite)** | Three real channels, mix, AOV, margin, returns, cross-channel customers |
| 14 | **Product Profitability** | SKU-month margin distribution, low-margin review alerts, top products by gross profit |
| 15 | **Smart Replenishment** | Latest-snapshot 45-day cover rule, reorder priorities, overstock review |
| 16 | **CLV & Churn** | Historical gross-profit CLV, concentration, churn status, temporal churn holdout |
| 17 | **Workforce Productivity (Lite)** | Payroll-covered headcount, labor cost ratio, branch payroll detail |
| 18 | **Store Expansion (Gap Proxy)** | Governorate coverage intensity, resident demand vs branch POS |
| 19 | **Data Explorer** | Ad-hoc view browser for all 26 curated views |

### 🤖 AI Business Assistant (Phase 3)

A **floating chat widget** (bottom-right FAB, available on every dashboard page) that answers business questions in **English and Arabic** using natural-language-to-SQL:

- **Pipeline**: User question → schema-aware SQL generation → read-only execution on curated views → business narration
- **Provider chain**: Google **Gemini** (primary) with automatic fallback to **Groq** on quota/rate-limit/outage
- **Safety**: SQL guard-rails (read-only, view-only), prompt-injection defence, refusal classification for out-of-scope questions
- **UX**: Conversation memory (last 4 exchanges), deep-link buttons to related dashboards, result tables, copy/export, truncation notices
- **Submission idempotency**: One click/Enter → exactly one engine call, no duplicate answers on Streamlit reruns (regression-tested)
- **Language matching**: Detects the user's language and responds in the same language, even when the underlying schema has Arabic column names

### 🎨 Design System

- **Brand navy palette** (`#17365D`) with a coordinated chart color family (blue, teal, violet, amber, rose, green, red)
- **Plotly template** applied to all charts for consistent styling
- **KPI cards** with tone strips (positive/negative/warning), status chips, page headers
- **Sidebar branding** with Cottonil identity mark
- **Responsive** mobile layout for the assistant panel

### 🧪 Test Suite (6 test files)

| Command | What it tests |
|---|---|
| `uv run pytest tests/test_pipeline.py` | Exact rowcounts, view integrity, anomaly caps, DQ gates |
| `uv run pytest tests/test_analytics.py` | Forecast (Holt-Winters), price-elasticity, churn, RFM on synthetic + real data |
| `uv run pytest tests/test_pages_smoke.py` | Every page × 3 period modes renders clean; navigation registry; assistant defaults |
| `uv run pytest tests/test_pages_perf.py` | Every page < 3 s render time |
| `uv run pytest tests/test_assistant.py` | SQL guard-rails, refusal tests, prompt injection, goldset mechanics + live 20-question evaluation (≥ 80% gate) |
| `uv run pytest tests/test_assistant_idempotency.py` | One submission → one `engine.ask()` call; provider storms produce exactly one error bubble |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Database | DuckDB (embedded, zero-config) |
| Web framework | Streamlit (multipage app) |
| Charting | Plotly |
| AI / LLM | OpenAI-compatible API (Gemini + Groq) |
| Forecasting | SciPy (Holt-Winters exponential smoothing) |
| Package manager | uv |
| Testing | pytest |
| Linting | Ruff |

---

## Project Structure

```
Cottonil/
├── app/                          # Streamlit application
│   ├── Home.py                   # App shell: navigation, filters, assistant mount
│   ├── assistant_widget.py       # Floating AI assistant chat panel
│   ├── charts.py                 # Plotly chart helpers using theme tokens
│   ├── filters.py                # Global period filter with YoY
│   ├── kpi.py                    # KPI card rendering
│   ├── navigation.py             # Page registry, nav groups, deep-link mapping
│   ├── theme.py                  # Design system (1,097 lines)
│   └── pages/                    # 19 dashboard pages
│       ├── 1_Executive_Overview.py
│       ├── 2_Sales_Performance.py
│       ├── ...
│       └── 19_Data_Explorer.py
├── assistant/                    # AI assistant engine
│   ├── engine.py                 # ask() → AskResult pipeline
│   ├── env.py                    # Provider config from .env
│   ├── llm.py                    # LLM client with fallback chain
│   ├── prompts.py                # System prompts (SQL generation + narration)
│   └── sql_exec.py               # Read-only SQL execution
├── pipeline/                     # Data pipeline
│   ├── build.py                  # CSV → DuckDB loader + view applicator
│   ├── checks.py                 # 34 data-quality gates
│   ├── connection.py             # DuckDB connection helper
│   ├── VIEW_CATALOG.md           # Auto-generated view contract docs
│   └── views/                    # 26 numbered SQL view definitions
├── tests/                        # 6 test files
├── docs/                         # PROJECT_PLAN, DATA_AUDIT, DASHBOARD_SCOPE_MATRIX
├── specs/                        # Feature specifications (001-core-platform)
├── data/                         # cottonil.duckdb (built, gitignored)
├── COTTONIL/                     # Raw dataset (25 CSVs, gitignored)
├── .streamlit/config.toml        # Streamlit theme configuration
├── .env                          # API keys (gitignored)
└── pyproject.toml                # Project config + dependencies
```

---

## Quickstart

```powershell
# 1. Install dependencies
uv sync

# 2. Build the database (loads 25 CSVs → DuckDB + applies 26 views)
uv run build

# 3. Run data quality checks
uv run checks

# 4. Run the full test suite
uv run pytest

# 5. Launch the dashboard
uv run streamlit run app/Home.py
```

### AI Assistant Setup

Add your API keys to `.env` (gitignored):

```env
# Primary provider (Google Gemini)
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash

# Fallback provider (Groq)
GROQ_API_KEY=your-key-here
GROQ_MODEL=llama-3.3-70b-versatile
```

The assistant auto-detects provider availability. If Gemini hits a rate limit or is unavailable, it falls back to Groq automatically (answers are captioned "via Groq (fallback)").

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `data/cottonil.duckdb not found` | Run `uv run build` first (requires CSVs under `COTTONIL/COTTONIL_Data/`) |
| Assistant says "LLM is not reachable" | Verify `GEMINI_API_KEY` / `GROQ_API_KEY` in `.env`, reload the page |
| Quota exhausted on Gemini | The chain falls back to Groq automatically |
| File lock on rebuild (Windows) | Stop the Streamlit process, rebuild, restart |

---

## Documentation

| Document | Description |
|---|---|
| [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) | Master project plan (phases, scope, timeline) |
| [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md) | Dataset audit, metric dictionary, anomaly policies |
| [`docs/DASHBOARD_SCOPE_MATRIX.md`](docs/DASHBOARD_SCOPE_MATRIX.md) | All 21 deck pages × data availability → build order |
| [`pipeline/VIEW_CATALOG.md`](pipeline/VIEW_CATALOG.md) | Auto-generated view definitions and column contracts |
| [`specs/001-core-platform/`](specs/001-core-platform/) | Feature spec, implementation plan, and task tracker |

---

## Source of Truth

- **Concept deck**: `COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf` (23 pages) — design language only. Numbers in the deck are illustrative; the real dataset differs.
- **Dataset**: `COTTONIL/COTTONIL_Data/` (25 CSVs, ~80 branches, ~85K customers, ~540K orders). Kept out of git (large); place it at that path before building.
