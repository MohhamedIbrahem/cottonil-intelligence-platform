# Cottonil Intelligence Platform

> **HVIA Task 3** — An enterprise-grade data foundation, 16 domain dashboards across 6 navigation groups, econometric analytics, and a bilingual Business AI Assistant built on the Cottonil retail dataset (25 CSVs → DuckDB → Streamlit).

---

## 🎬 Demo Video

[`docs/demo_final.mp4`](docs/demo_final.mp4) — a scripted walkthrough of the real running app: a title card, all **16 dashboards** (each with live sidebar navigation, render settle, and a smooth scroll-through), and the **Business AI Assistant** answering two real questions — one in English, one in Arabic — with SQL-grounded responses, sources, and result tables.

*1920×1080 · 30 fps · H.264 + AAC · 2 min 49 s*

---

## Architecture & What We Built

```
                          ┌────────────────────────┐
                          │   25 Raw CSV Tables    │
                          │   (~80 Branches, 85K   │
                          │   Customers, 540K Tx)  │
                          └───────────┬────────────┘
                                      │ uv run build (pipeline.build_db)
                                      ▼
                          ┌────────────────────────┐
                          │  Embedded DuckDB Store │
                          │ (data/cottonil.duckdb) │
                          └───────────┬────────────┘
                                      │ Materialize Views
                                      ▼
                          ┌────────────────────────┐
                          │  26 Curated SQL Views  │
                          │   (pipeline/views/)    │
                          └───────────┬────────────┘
                                      │ uv run checks (34 DQ Gates)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       Cottonil Intelligence Shell (Home.py)      │
             │   - Shared Period Filter (Same-Window YoY)       │
             │   - Professional Design System (app/theme.py)    │
             │   - Grouped Navigation (app/navigation.py)       │
             └─────────────┬──────────────────────┬─────────────┘
                           │                      │
                           ▼                      ▼
        ┌────────────────────────────┐  ┌───────────────────────────────────┐
        │  16 Domain Dashboards      │  │    Business AI Assistant          │
        │  Across 6 Business Groups  │  │  - Floating Docked Bubble (FAB)   │
        │  - Overview                │  │  - NL → SQL Pipeline (Read-Only)  │
        │  - Sales & Channels        │  │  - Gemini + Groq Provider Chain   │
        │  - Products & Pricing      │  │  - EN/AR Language Matching        │
        │  - Supply & Operations     │  │  - Idempotent Event Queueing      │
        │  - Customers               │  │  - Matched Dashboard Deep Links   │
        │  - Organization & Growth   │  └───────────────────────────────────┘
        └─────────────┬──────────────┘
                      ▼
        ┌────────────────────────────┐
        │ Econometric Models         │
        │ (app/analytics.py)         │
        │ - Holt-Winters Forecast    │
        │ - 2-Way Fixed Elasticity   │
        │ - Temporal Churn Holdout   │
        └────────────────────────────┘
```

---

## Key Platform Capabilities

### 1. 🏗️ Data Foundation & Automated Pipeline
- **25 Relational Tables** loaded into an embedded, high-performance **DuckDB** database (`data/cottonil.duckdb`) with strict typed schemas (Dates, BigInt IDs, Double monetary metrics).
- **26 Curated Analytical Views** (`pipeline/views/`) materialized in dependency order, isolating raw ingestion from UI presentation.
- **34 Data Quality Gates** (`uv run checks`):
  - **27 Foreign Key & Orphan Checks**: Verifies zero orphaned orders, payments, shipments, inventory transfers, and items.
  - **7 Financial Reconciliation Checks**: Verifies strict balance across gross sales, discounts, net sales, returns, and payments.
- **Automated Data Contracts**: Full column-level definitions documented in [`pipeline/VIEW_CATALOG.md`](pipeline/VIEW_CATALOG.md).

### 2. 📊 16 Enterprise Dashboards (6 Navigation Groups)
Registered in [`app/navigation.py`](app/navigation.py) with unified date-window filtering, same-window YoY comparison, and export capabilities:

| Group | Dashboard | File | Key Features |
|---|---|---|---|
| **Overview** | **Executive Overview** | `1_Executive_Overview.py` | Macro KPI strip (Revenue, Gross Margin, AOV, Volume) with YoY deltas, monthly trajectory, top-5 branch share, governorate breakdown, channel distribution. |
| **Sales & Channels** | **Sales Performance** | `2_Sales_Performance.py` | Category-filterable sales trends, top-15 volume products, items-per-order, order value metrics. |
| | **Branch Performance** | `3_Branch_Performance.py` | Branch performance ranking, revenue vs. growth scatter quadrant, governorate expansion analysis. |
| | **Wholesale & Distributors** | `11_Wholesale.py` | B2B distributor volume, channel trends, client account recency and customer concentration metrics. |
| | **Omnichannel (Lite)** | `14_Omnichannel.py` | Performance across retail branches, e-commerce, and wholesale; cross-channel customer overlaps. |
| | **Marketing ROI** | `10_Marketing_ROI.py` | Channel attribution, ad spend efficiency, CAC, ROAS, CPA, and campaign budget utilization. |
| **Products & Pricing** | **Product Profitability** | `15_Product_Profitability.py` | SKU-level gross margins, margin distribution curves, low-margin outlier warnings, top revenue drivers. |
| | **Price & Promotion** | `13_Price_Promotion.py` | Discount depth analysis, margin interaction, promotional lift, and price elasticity estimates. |
| | **Demand Forecast** | `12_Demand_Forecast.py` | Category-level unit demand, 6-month predictive horizon, rolling-origin WAPE error tracking, empirical risk bounds. |
| **Supply & Operations**| **Inventory & Stock** | `4_Inventory_Stock.py` | Current stock coverage days, warehouse-to-store distribution, stock-out risk buckets, **Smart Replenishment tab** (45-day cover rule, priority reorder). |
| | **Supply Chain & Logistics** | `7_Supply_Chain.py` | Delivery on-time rates, transit delays, logistics partner performance, warehouse transfer pipeline. |
| | **Procurement & Suppliers**| `8_Procurement.py` | Supplier lead-time distribution, on-time delivery scorecards, purchase order execution rates. |
| | **Returns & Quality** | `9_Returns_Quality.py` | Return rate trends, return reasons breakdown, category-specific defect/return concentrations. |
| **Customers** | **Customer Intelligence** | `5_Customer_Intelligence.py` | RFM customer segmentation, top-tier VIP accounts, geographic distribution, **CLV & Churn tab** (historical LTV, churn risk holdout). |
| **Organization** | **Workforce Productivity** | `18_Workforce_Productivity.py` | Branch headcount, payroll-to-revenue ratios, labor efficiency trends (2023 reference period). |
| | **Store Expansion** | `19_Expansion_Gap.py` | Branch density vs. governorate population and customer demand, expansion opportunity scoring. |

### 3. 🤖 Business AI Assistant
Built into a floating widget docked on every dashboard page (`app/assistant_widget.py`) with backend intelligence in `assistant/`:

- **Natural Language to SQL**: Translates English and Arabic questions into strict read-only SQL queries executed directly against the curated views.
- **Provider Fallback Chain**:
  - **Primary**: Google **Gemini** (`gemini-2.0-flash` or `gemini-2.5-flash`)
  - **Fallback**: **Groq** (`llama-3.3-70b-versatile`), activated automatically upon quota exhaustion or timeouts.
- **Enterprise Guard-Rails**:
  - AST-based SQL validation ensuring single-statement `SELECT`/`WITH` statements only.
  - Whitelist enforcement restricting access exclusively to analytical views (`views.*`).
  - Strict timeout bounds and query cancellation (`con.interrupt()`).
- **Prompt Injection Defense & Refusal Handling**: Classifies and cleanly refuses out-of-domain or malicious queries in both English and Arabic.
- **Submission Idempotency**: Event-driven form handling preventing duplicate submission reruns.
- **Language Detection & Matching**: Explicitly detects question language to prevent cross-language responses when viewing Arabic schema names.
- **Modern User Experience**:
  - Modern gradient Floating Action Button (FAB) docked on every dashboard.
  - Live provider status indicator (`● Online · ask about sales, stock & customers`).
  - Scrollable fixed-height conversation history with full EN/AR rendering.
  - Collapsible result table viewer (`st.dataframe`).
  - 1-click deep-link navigation directly to relevant dashboards.
  - One-click copy/export to Markdown.

### 4. 📈 Statistical & Econometric Models (`app/analytics.py`)
- **Holt-Winters Exponential Smoothing**: Additive damped trend with multiplicative seasonality for multi-month demand forecasting (`statsmodels.tsa.holtwinters`).
- **Two-Way Fixed Effects Price Elasticity**: Panel regression controlling for SKU and monthly fixed effects with clustered standard errors.
- **Temporal-Holdout Churn Classifier**: Out-of-time evaluation verifying customer reorder behavior and churn predictability.

### 5. 🎨 Design System (`app/theme.py`)
- Light theme engineered for high contrast (WCAG AA compliant: 15.9:1 text contrast).
- Corporate Cottonil brand navy identity (`#17365D`) paired with coordinated categorical chart colors (blue, teal, violet, amber, rose, green, red).
- Custom global Plotly template unifying all interactive charts.
- Standardized KPI cards with color-coded sentiment tone strips.

---

## Test Suite & Quality Gates

The codebase includes 6 comprehensive automated test suites:

```powershell
uv run pytest -v
```

| Suite | File | Focus Area |
|---|---|---|
| **Pipeline & Views** | `tests/test_pipeline.py` | Exact table row counts, view materialization, 0 foreign-key orphans, reconciliation math. |
| **Econometric Models** | `tests/test_analytics.py` | Synthetic & real data verification of Holt-Winters, elasticity regression, and churn holdout. |
| **Page Smoke Suite** | `tests/test_pages_smoke.py` | Headless render of all 16 dashboards across 3 period modes; navigation integrity. |
| **Performance Gate** | `tests/test_pages_perf.py` | Enforces sub-3-second render budget for every single dashboard page. |
| **Assistant Mechanics** | `tests/test_assistant.py` | SQL injection defense, schema constraints, refusal logic, and 20-question accuracy goldset. |
| **Idempotency Gate** | `tests/test_assistant_idempotency.py` | Guarantees single-request queueing across simulated Streamlit reruns and provider outage resilience. |

---

## Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Runtime** | Python 3.12+ | Core programming environment |
| **Package Manager** | `uv` | High-speed dependency resolver and task runner |
| **Database Engine** | DuckDB (>=1.1.0) | Embedded in-process columnar SQL OLAP database |
| **Web UI** | Streamlit (>=1.37.0) | Interactive dashboard framework |
| **Data Processing** | Pandas & PyArrow | High-throughput data frames and memory management |
| **Visualizations** | Plotly (>=5.22.0) | Interactive charts with custom Cottonil theme |
| **Econometrics** | Statsmodels & SciPy | Time-series forecasting and panel regression |
| **LLM Orchestration**| OpenAI SDK | Universal client for Gemini and Groq API endpoints |
| **Code Quality** | Ruff & Pytest | Strict linting, formatting, and automated testing |

---

## Project Structure

```
Cottonil/
├── app/                          # Streamlit application layer
│   ├── Home.py                   # App entrypoint, shell configuration, and nav mounting
│   ├── assistant_widget.py       # Floating Business AI Assistant widget & CSS
│   ├── navigation.py             # 16-page registry & 6 business navigation groups
│   ├── theme.py                  # 1,116-line design system (tokens, CSS, Plotly template)
│   ├── filters.py                # Global period selector & YoY period math
│   ├── analytics.py              # Statistical forecasting, elasticity, and churn models
│   ├── data.py                   # Cached DuckDB query interface
│   ├── pages/                    # 16 registered dashboard pages
│   │   ├── 1_Executive_Overview.py
│   │   ├── 2_Sales_Performance.py
│   │   ├── 3_Branch_Performance.py
│   │   ├── 4_Inventory_Stock.py
│   │   ├── 5_Customer_Intelligence.py
│   │   ├── 7_Supply_Chain.py
│   │   ├── 8_Procurement.py
│   │   ├── 9_Returns_Quality.py
│   │   ├── 10_Marketing_ROI.py
│   │   ├── 11_Wholesale.py
│   │   ├── 12_Demand_Forecast.py
│   │   ├── 13_Price_Promotion.py
│   │   ├── 14_Omnichannel.py
│   │   ├── 15_Product_Profitability.py
│   │   ├── 18_Workforce_Productivity.py
│   │   └── 19_Expansion_Gap.py
├── assistant/                    # Business AI Assistant core
│   ├── engine.py                 # Multi-step ask() pipeline (prompt -> SQL -> exec -> narrate)
│   ├── sql_guard.py              # AST SQL parsing, read-only validation, table whitelisting
│   ├── prompts.py                # System instructions, schema formatting, language detection
│   ├── llm.py                    # Dual-provider client with automatic fallback
│   ├── env.py                    # Provider configuration and timeout settings
│   ├── schema_docs.py            # Automated view documentation injected into prompts
│   └── goldset.py                # Benchmark question set for assistant evaluation
├── pipeline/                     # ETL and analytical data pipeline
│   ├── build_db.py               # Ingests 25 CSVs into DuckDB with typed schemas
│   ├── checks.py                 # 34 automated data quality and reconciliation gates
│   ├── views_loader.py           # Applies SQL views in sequence
│   ├── config.py                 # File paths, table definitions, and constants
│   ├── VIEW_CATALOG.md           # Catalog of materialized views and schema contracts
│   └── views/                    # 26 SQL view migration files
├── tests/                        # 6 Automated pytest suites
├── docs/                         # Architecture docs, audits, project plans, demo video
│   ├── demo_final.mp4            # Product demo walkthrough (1920×1080, H.264/AAC)
│   ├── PROJECT_PLAN.md           # Master roadmap and feature scope
│   ├── DATA_AUDIT.md             # Dataset anomalies, policies, and metric dictionary
│   └── DASHBOARD_SCOPE_MATRIX.md # Mapping of concept deck to build order
├── COTTONIL/                     # Source CSV dataset (gitignored)
├── data/                         # Built DuckDB database files (gitignored)
├── .streamlit/config.toml        # Streamlit server and light theme config
├── pyproject.toml                # Project metadata, dependencies, and build scripts
└── README.md                     # Project overview and runbook
```

---

## Quickstart Guide

### 1. Prerequisites & Installation
Ensure Python 3.12+ and `uv` are installed:

```powershell
# Clone the repository
git clone https://github.com/MohhamedIbrahem/Cottonil.git
cd Cottonil

# Synchronize virtual environment and dependencies
uv sync
```

### 2. Build the Data Layer
Ingest the 25 CSV tables and compile the 26 analytical views into DuckDB:

```powershell
# Build DuckDB database
uv run build

# Run 34 data quality & financial reconciliation checks
uv run checks
```

### 3. Run Test Suite
Verify that pipeline math, econometric models, and pages pass all gates:

```powershell
uv run pytest
```

### 4. Configure AI Assistant
Create a `.env` file in the project root:

```env
# Primary LLM Provider (Google Gemini)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# Fallback LLM Provider (Groq)
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

### 5. Launch the Platform
Start the multi-page Streamlit application:

```powershell
uv run streamlit run app/Home.py
```

---

## Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `data/cottonil.duckdb not found` | The database has not been built yet. | Run `uv run build` to ingest CSVs and generate views. |
| Assistant displays "LLM is not reachable" | Missing or invalid API key in `.env`. | Add valid `GEMINI_API_KEY` or `GROQ_API_KEY` to `.env` and reopen the panel. |
| Primary quota limit hit (429) | Gemini API rate limit or quota exceeded. | The assistant automatically falls back to Groq without manual intervention. |
| Database file lock on Windows | Rebuilding while Streamlit app is actively running. | Stop the Streamlit server process, run `uv run build`, and restart Streamlit. |

---

## Project Documentation Links

- **[Master Project Plan](docs/PROJECT_PLAN.md)**: Delivery phases, feature scope, and roadmap.
- **[Data Audit & Metric Dictionary](docs/DATA_AUDIT.md)**: Dataset structure, reconciliation policies, and anomaly handling.
- **[Dashboard Scope Matrix](docs/DASHBOARD_SCOPE_MATRIX.md)**: Complete mapping of the 23-page concept deck to implementation.
- **[Curated View Catalog](pipeline/VIEW_CATALOG.md)**: Data schemas and column contracts for all 26 views.
- **[Concept Deck Source]**: `COTTONIL/HVIA_TASK_3_COTTONIL_ALL_23_IMAGES.pdf` (design inspiration).
