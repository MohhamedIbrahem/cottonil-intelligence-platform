# Tasks: Cottonil AI Business Assistant — Core Release

**Input**: Design documents from `specs/001-core-platform/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)
**Organization**: Tasks grouped by user story; `[P]` = parallelizable.

## Phase 0: Setup

- [x] T001 Create `pyproject.toml` (uv project; python 3.12; deps: pandas, duckdb, streamlit, plotly, openai client, pytest, ruff; scripts: build, checks)
- [x] T002 Create `.env.example` (LLM base URL/model/key placeholders) and add to `.gitignore`. ( parallel with T001 different files)
- [x] T003 [P] Update `.gitignore`: exclude `.venv/`, `*.duckdb`, `.env`
- [x] T004 Run `uv sync`; commit lockfile
- [x] T005 README skeleton with 3-step quickstart

**Checkpoint**: clean machine can `uv sync` without error

## Phase 1: Foundational — Data Pipeline (US1, P1)

**⚠️ CRITICAL**: No user-story work until this passes DQ tests.

- [x] T010 `pipeline/__init__.py`, `pipeline/config.py` (paths, dataset constants incl. dataset end date 2026-10-18, encoding utf-8-sig)
- [x] T011 `pipeline/build_db.py` — load all 25 CSVs into `raw` schema with explicit types; deterministic table order; transaction per table; fail on missing file
- [x] T012 [P] `pipeline/checks.py` — DQ SQL: FK orphans (items→orders/sku/product, orders→branch/customer(allow guest-null), payments→orders, returns→orders/lines, transfer_items→transfers/sku, po_items→po/sku) with expected-zero counts and guest-null exception
- [x] T013 [P] `pipeline/checks.py` — reconciliation: `gross−discount=net_before_tax`, tax≈14%, `paid=net+tax`; flag anomalies (PO scale, attribution) as warnings not failures
- [x] T014 View 01: `pipeline/views/010_sales_enriched.sql` — sales_order_items × orders (+ year, month, channel), × product (category_en, audience), × branch (governorate), × customer (segment, age_band)
- [x] T015 [P] View 02: `020_branch_daily.sql`, 03: `025_branch_summary.sql`
- [x] T016 [P] View 04: `030_product_hierarchy.sql`, 05: `040_top_products.sql`
- [x] T017 [P] View 06: `050_stock_monthly.sql`, 07: `055_stock_status.sql`
- [x] T018 [P] View 08: `060_returns_enriched.sql` (refund capped per policy), 09: `070_supplier_pos.sql` (documented scale caveat)
- [x] T019 [P] View 10: `080_customer_rfm.sql` (recency/frequency/monetary + named RFM tier), 11: `085_customer_profile.sql`
- [x] T020 [P] View 12: `090_campaigns_clean.sql` (spend, impressions, clicks, CTR; conversion recomputed from orders in window; `orders_attributed` excluded from revenue math)
- [x] T021 View loader: read numbered view SQLs in order, materialize as DuckDB views; write `pipeline/VIEW_CATALOG.md` (name, grain, columns, joins) — source for `schema_docs.py` later
- [x] T022 `tests/test_pipeline.py` — run build on tmp copy, assert view row counts >0, run `pipeline/checks.py` expecting exit 0
- [x] T023 Wire `build`/`checks` scripts to uv project scripts; verify `uv run build && uv run checks`

**Checkpoint**: US1 done — pipeline builds, DQ tests green ✅ (2026-10-25: build EXIT 0, 34/34 gates PASS, 11/11 tests pass in ~20 s; A9 catalog-namespace finding added to DATA_AUDIT)

## Phase 2: App Shell (shared UI)

- [x] T030 `app/theme.py` — navy palette constants + `kpi_card(title, value, delta, help_text)` component + chart style
- [x] T031 [P] `app/filters.py` — period selector state (Last 12 months / calendar-year / all), `where_period(df)` helper, dataset-last-date aware labels + `st.session_state`
- [x] T032 [P] `app/data.py` — DuckDB connection singleton + `q(view)` convenience returning pandas df
- [x] T033 `app/Home.py` — app title, nav, landing = Executive Overview placeholder; shared filter render
- [x] T034 `streamlit.config.toml` theme config; verify dark navy look

**Checkpoint**: shell runs, shared filter works ✅ (2026-10-25: headless server health/main 200, AppTest 0 exceptions, 34/34 DQ + ruff clean; home KPIs read real views)

## Phase 3: US2 Executive Overview (P2) 🎯 demo-able core

- [ ] T040 Executive page KPI cards: Net Sales, Gross Profit (sum margin_EGP), Orders, Active Customers, Return Rate % with YoY deltas; metric-definition tooltips from AUDIT doc
- [ ] T041 Monthly sales & profit trend line (period-aware)
- [ ] T042 [P] Top-5 branches bar + governorate totals
- [ ] T043 [P] Category mix donut + channel mix donut
- [ ] T044 Data-note expander content per page (FR-012)

**Checkpoint**: deck p2 exists with real data

## Phase 4: US3 Sales Performance (P3)

- [ ] T050 Monthly sales performance line (net + profit), category filter
- [ ] T051 [P] Top-selling products table (units + EGP) per period
- [ ] T052 [P] Category revenue share donut + average basket (AOV, items/order)
- [ ] T053 [P] Governorate breakdown bar
- [ ] T054 Data notes expander

**Checkpoint**: US3 done independently

## Phase 5: US4 Branch Performance (P3)

- [ ] T060 Branch ranked table: revenue, growth %, orders, AOV; top/bottom highlighting
- [ ] T061 [P] Governorate-level bar (revenue + growth)
- [ ] T062 [P] Growth % vs revenue scatter/star-ish charts (deck p4 style imitation, no map)
- [ ] T063 Data notes expander

**Checkpoint**: US4 done

## Phase 6: US5 Inventory & Warehouse (P3)

- [ ] T070 KPIs: latest-month units, stock value EGP, % locations at risk (stockout_risk_score ≥0.7)
- [ ] T071 [P] Monthly stock value/units trend + warehouse/branch split
- [ ] T072 [P] Category mix + status buckets (in-stock/overstock/low-stock via quantile policy)
- [ ] T073 [P] Risk alerts table (top 10 locations×category)
- [ ] T074 Data notes expander

**Checkpoint**: US5 done

## Phase 7: US6 Customer Intelligence (P3)

- [ ] T080 Segment/age/gov mix donuts + join trend
- [ ] T081 [P] RFM segment table from `085_customer_profile` view (Champions, Loyal, At Risk…)
- [ ] T082 [P] Repeat rate KPI + top customers by LTV
- [ ] T083 [P] Customer lookup (search by name/id → order history)
- [ ] T084 Data notes expander

**Checkpoint**: Core 5 complete

## Phase 8: US7 AI Assistant (P2, depends on Phase 1 + any one dashboard)

- [ ] T090 `assistant/schema_docs.py` — embed view catalog (from T021 artefact) with allowed views list
- [ ] T091 [P] `assistant/sql_guard.py` — SELECT-only, single statement, allowlist enforcement, LIMIT 200, read-only connection
- [ ] T092 [P] `assistant/llm.py` — OpenAI-compatible client (default Ollama env), retry on invalid SQL (max 2)
- [ ] T093 `assistant/prompts.py` — system prompt: Cottonil context, metric dictionary summary, EN/AR answer rule, refusal policy, output format (markdown + numbered sources)
- [ ] T094 Chat page `6_Assistant.py`: chat UI, SQL collapsible per message, deep-link button logic
- [ ] T095 [P] `assistant/goldset.py` + `tests/test_goldset.py` — 20 question/expected-invariant pairs; pytest runs engine locally (no UI), reports accuracy %
- [ ] T096 Refusal tests: write-action denial & out-of-scope (ESG/planogram) returns explicit "not in dataset" message
- [ ] T097 Connection: DuckDB read-only view execution guard; time cap; error surfacing to chat (no raw tracebacks in UI)

**Checkpoint**: US7 done; goldset ≥80%

## Phase 9: US8 Shortcut Rail (P4)

- [ ] T100 Shortcuts list rendering with lambdas: Get Insights (period digest), View Reports (period report summary markdown), Check Inventory (product search term), Store Performance (branch chooser), Customer Insights (customer chooser), Supplier Information (supplier table + on-time/lead time from `070_supplier_pos`)
- [ ] T101 [P] Session-scoped conversation memory; reset button; export answer to clipboard
- [ ] T102 [P] Arabic test prompts in goldset (≥3) verified

**Checkpoint**: US8 done; PDF p23 feature set fully mapped

## Phase 10: Polish

- [ ] T110 Docs: update DATA_AUDIT + SCOPE matrix statuses; add runbook in README
- [ ] T111 [P] Ruff clean; consistent naming
- [ ] T112 [P] Perf: verify each page <3s (time in `st.cache_data` if needed)
- [ ] T113 Record 2-min demo script (chat transcript + screenshots)

**Checkpoint**: Release 001 candidate

---

## Dependencies & Execution Order

- Setup → Foundational(pipeline) → App Shell → (US2..US6 sequential in UI though QA-able independently) → US7 → US8 → Polish.
- US7 can start once Phase 1 + any one page exist; but recommended after Phase 8's views are stable.
- Each US checkpoint is demo-able.

## Implementation Strategy

- MVP = Phase 1 + shell + US2 only; stop-and-validate each checkpoint.
- Parallel-friendly where marked due to file isolation; sequential where schema/views shared.
