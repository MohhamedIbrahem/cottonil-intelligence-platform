# Implementation Plan: Cottonil AI Business Assistant — Core Release

**Branch**: `001-core-platform` | **Spec**: `specs/001-core-platform/spec.md` | **Created**: 2026-10-24

## Summary

Build a local-first analytics web app: the 25 Cottonil CSVs are loaded into a typed DuckDB database and surfaced as curated analytical views; a Streamlit multipage app provides the Executive, Sales, Branch, Inventory and Customer dashboards from the PDF deck (pages 2–6); an LLM-powered assistant answers business questions in EN/AR by generating validated read-only SQL against those views. All numbers come from the real dataset; the PDF is the design language only.

**Runtime note**: Dataset static (ends 2026-10-18) → pipeline is manual-run, not scheduled; no CI required for demo path.

## Technical Context

| Aspect | Decision |
|---|---|
| Language/runtime | Python 3.12 (uv-managed venv; NOT the broken Anaconda base) |
| Storage/analytics | DuckDB single-file DB, prebuilt views, Parquet-friendly |
| Ingestion | Python stdlib pandas + DuckDB COPY, typed explicitly |
| UI | Streamlit multipage + Plotly (dark navy theme per deck) |
| Assistant LLM | Generic OpenAI-compatible client; default endpoint = local Ollama (`http://localhost:11434/v1`), cloud model optional via env |
| NL→SQL guard | SQL parser validation (SELECT-only, allowlisted views), LIMIT enforced, schema row-limits |
| Testing | pytest (pipeline + gold question set) |
| Deployment | `uv sync` → build → `streamlit run` local; Docker optional later |
| Git | main + feature branch; commit per task (initialized 2026-10) |

## Repository Structure

```
Cottonil/
├── COTTONIL/                      # source deck (PDF) + COTTONIL_Data/ (read-only inputs)
│   └── COTTONIL_Data/
│       ├── 01_CATALOG/            # product catalog public reference
│       └── 02_TABLES/             # 25 CSVs (_the_ source of truth)
├── specs/001-core-platform/       # this feature's spec/plan/tasks
├── docs/                          # PROJECT_PLAN, DATA_AUDIT, DASHBOARD_SCOPE_MATRIX
├── app/                           # Streamlit multipage app
│   ├── Home.py                    # landing (Executive Overview = US2)
│   ├── pages/                     # 1_Sales.py … 5_Assistant.py
│   ├── theme.py                   # navy palette, KPI card component
│   └── filters.py                 # shared period/global filter logic
├── pipeline/
│   ├── build_db.py                # load CSVs → duckdb (CLI entry)
│   ├── checks.py                  # DQ SQL checks (reconciliation, orphans)
│   └── views/*.sql                # curated view definitions (numbered)
├── assistant/
│   ├── schema_docs.py             # allowlisted views + descriptions for prompt
│   ├── sql_guard.py               # SELECT-only validator & limits
│   ├── llm.py                     # OpenAI-compatible client (Ollama default)
│   ├── goldset.py                 # 20 question/answer pairs + evaluator
│   └── prompts.py                 # system prompt, EN/AR, decline rules
├── tests/                         # pytest: pipeline DQ, view smoke tests, goldset
├── pyproject.toml                 # uv project (deps, scripts)
├── README.md
└── .specify/                      # Spec Kit (constitution, templates, commands)
```

## Phase 0 — Repository & Environment (foundational)

- pyproject.toml + `uv sync` venv (python 3.12); dev deps: pytest, ruff.
- `.gitignore` additions: `.duckdb/`, `*.parquet`, `.venv/`, `.env`.
- Commit baseline: data folder is large (200+ MB) — keep `COTTONIL_Data/` OUT of git initially; document where it lives (PDF deck too big as well). Decide: `git lfs` or just local path relative — **decision: keep out of git, README documents placement**.

## Phase 1 — Data Pipeline (US1)

1. `pipeline/build_db.py`:
   - register table loaders per CSV: dtypes (date parsing, EGP floats, unit ints, enum fields as-is).
   - load → DuckDB in one transaction per table; deterministic order (branches, customers, products, skus, … orders, items, returns, …).
2. `pipeline/checks.py` (SQL):
   - FK orphan checks: items→orders, items→sku/product, orders→branch, payments→orders, returns→orders/lines, PO items→PO, transfers→sku/warehouse.
   - reconciliation: `gross − discount = net_before_tax`; `net_before_tax × ~0.14 ≈ tax`; `paid_total = net + tax`.
   - documented anomalies (not blockers): PO total 29.15B EGP vs 841M sales (procurement values may not reconcile with COGS — policy: procurement dashboards absolute-only), marketing `orders_attributed` sums 24M (unusable → recompute attribution by date/governorate/audience overlap instead), refunds > line net (cap in refund analytics), items↔lines count ok.
3. `pipeline/views/`: numbered SQL files producing `sales_enriched`, `sales_daily`, `sales_monthly`, `product_hierarchy`, `branch_daily`, `branch_summary`, `stock_monthly`, `stock_status`, `returns_enriched`, `customer_rfm`, `supplier_pos`, `campaigns_clean`, …
4. `tests/test_pipeline.py` with row-count expectations + reconciliation + orphan checks.

Question → which story: builds US1 only; every later story depends on it.

## Phase 2 — App Shell & Design System

- `app/theme.py` navy palette (deck-style: dark indigo cards, blue accents, green/red delta badges), `kpi_card()` component, `filters.py` shared period state (`st.session_state`).
- `app/Home.py` = Executive Overview (US2) if Phase 3 not finished, otherwise shell + nav.
- Data notes expander per page (FR-012).

## Phase 3 — Core 5 Dashboards (US2..US6)

Bottom-queries-per-page; each page default period = last 12 months (ends at dataset max date = 2026-10-18; label "Sep 2026 last complete month").

| Page (deck page) | Queries/views | Charts |
|---|---|---|
| Executive (p2) | exec KPIs, monthly trend, top branches, cat mix, channel mix | KPI cards, line, bar×2, donut |
| Sales (p3) | monthly sales, top products (units & EGP), AOV, cat share, gov breakdown | line, bar×2, donut, table |
| Branch (p4) | branch_summary ranked, governorate totals, growth deltas | table+rank, bar, scatter growth vs revenue |
| Inventory (p5) | stock_status buckets, monthly stock trend, category, top-risk locations | KPI, stacked bar, donut, alert table |
| Customers (p6) | segment/age/gov mix, join trend, RFM segments table, lookup | donuts×2, bar, table, search box |

## Phase 4 — AI Assistant (US7..US8)

- `assistant/schema_docs.py`: embedded catalog — per view: name, grain, key columns, joins, sample values; tight "known-good question patterns".
- `assistant/llm.py`: OpenAI-compatible; provider config via env (`COTTONIL_LLM_BASE_URL`, `_MODEL`, optional `_API_KEY`); default Ollama local.
- `assistant/sql_guard.py`: tokenize → reject non-SELECT/multi-statement/DML; enforce `LIMIT 200`; strip markdown fences; exec on DuckDB read-only connection; row cap; elapsed-time guard (no table scans of raw 100MB+ CSVs — views only).
- `assistant/prompts.py`: system prompt: Cottonil context, metric dictionary summary, "you only have these views", Arabic/English reply rule, refusal policy for write actions or out-of-scope data (ESG, planogram, etc.), answer format with bold numbers and source SQL.
- `assistant/goldset.py`: 20 questions with expected invariants (e.g., top product last month = product X metric Y ≈ number range); evaluator runs pipeline SQL alternative manually precomputed.
- Streamlit `pages/6_Assistant.py`: chat UI, SQL toggle per answer, deep-link buttons, preset shortcuts (US8): Get Insights, View Reports, Check Inventory, Store Performance, Customer Insights, Supplier Information.
- Cost/latency guard: single short context (views catalog <4KB), max ~40 SQLs/session logged.

**Wireframe mapping to deck page 23** (chat panel + shortcuts + example answer layout):
left rail: shortcuts; main column: chat; each answer as markdown + collapsible SQL + optional small table/chart.

## Phase 5 — QA & Docs

- pytest suites all pass; README quickstart validated on clean venv.
- Update `docs/DASHBOARD_SCOPE_MATRIX.md` statuses; update `docs/DATA_AUDIT.md` with final policies.
- Recording: 2-min walkthrough script for demo/handover.

## Data Handling Decisions (Principle IV)

See `docs/DATA_AUDIT.md` for full list; key policies:
1. Procurement metrics absolute-only; COGS not derived from PO values due to scale anomaly.
2. Marketing attribution: recompute conversions from sales_orders in campaign window; keep platform-reported clicks/impressions as-is; do NOT use `orders_attributed` for revenue math.
3. Wholesale USD→EGP normalization; B2B segment = `customer_segment='B2B reseller'` + `sales_channel='Wholesale / reseller'`.
4. "Last month" logic: last complete month in data (Sep 2026), clearly labeled.
5. Products' unit prices below listed are pack-vs-unit semantics; AOV etc. computed from actual prices, no forced packaging assumptions.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Anaconda env broken for pandas-numexpr | blocks dev | uv venv from python 3.12; do not reuse Anaconda site-packages |
| LLM local model weak at SQL | assistant quality poor | tight views + few-shot patterns + validator retry (max 2), goldset threshold gates release |
| DuckDB file locked while app runs | dev friction | single shared connection module; same-process; avoid second builder while app open |
| 200MB+ data folder in git | repo bloat | keep COTTONIL_Data out of git; document path |
| Arabic encoding on Windows console | garbled names | force UTF-8 in pipeline (utf-8-sig read), UI renders correct |
| Mockup numbers mislead stakeholders | scope creep | Principle II + scope matrix prominently linked from every page |

## Validation Checklist

- [ ] `uv sync` works; pytest green
- [ ] `python -m pipeline.build_db && python -m pipeline.checks` exits 0, prints DQ summary
- [ ] `streamlit run app/Home.py`: 5 pages render with real data
- [ ] Assistant answers ≥80% gold set correctly; refuses out-of-scope
- [ ] Scope matrix updated; docs/DATA_AUDIT.md matches shipped views
