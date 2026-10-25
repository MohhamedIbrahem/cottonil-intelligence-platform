# Feature Specification: Cottonil AI Business Assistant — Core Release

**Feature Branch**: `001-core-platform`

**Created**: 2026-10-24

**Status**: Draft

**Input**: Build a web app from the HVIA Task 3 concept deck (23 images) + COTTONIL dataset (25 CSVs): data foundation, Core 5 dashboards (Executive, Sales, Branch, Inventory, Customers), and an AI business assistant that answers business questions from the data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Data foundation I can trust (Priority: P1)

A developer runs `uv run python -m pipeline.build` on a clean checkout and gets a typed, tested DuckDB database with curated analytical views from the 25 CSVs. Dashboard pages and the assistant consume only those views.

**Why this priority**: Nothing else can be built or trusted without it; every number on every screen depends on it.

**Independent Test**: Run the pipeline on a fresh clone, then run `uv run pytest tests/` — all data-quality tests pass in under 5 minutes total.

**Acceptance Scenarios**:

1. **Given** a fresh checkout, **When** the pipeline runs, **Then** a DuckDB file exists containing all 25 source tables plus ≥10 curated analytical views.
2. **Given** the built database, **When** reconciliation checks run, **Then** gross − discount = net before tax for 100% of orders, and order→item, order→customer, order→branch, item→SKU, item→product joins have 0 foreign-key orphans (excluding documented null customer_id "guest orders" ≈19%).
3. **Given** a source CSV is malformed or missing, **When** the pipeline runs, **Then** it fails loudly with a table-level error, not silently.
4. **Given** the pipeline, **When** re-run twice, **Then** output is deterministic (same row counts, same totals).

---

### User Story 2 - Executive overview (Priority: P2)

A shop-owner opens the Executive Overview page and sees Total Sales, Gross Profit, Orders, Customers, Return Rate plus monthly trend, top branches, category mix, and channel mix — all computed from the dataset, with a period filter (Last 12 months default) and YoY change badges like the PDF mockup style.

**Why this priority**: The single screen that proves the concept and is the landing page of the app.

**Independent Test**: Open the app → Executive page renders in <3 seconds with period filter functional.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** Executive page opens, **Then** KPI cards show Net Sales, Gross Profit, Orders, Active Customers, Return Rate for the selected period with YoY deltas.
2. **Given** period filter "Jan 2024 – Dec 2024", **When** selected, **Then** all KPIs and charts update to that period only.
3. **Given** any period, **When** KPI is clicked, **Then** a definition tooltip shows the metric definition (Principle IV).

---

### User Story 3 - Sales Performance page (Priority: P3)

A category manager sees revenue trend by month, top products (units & EGP), category revenue share, basket size (AOV, items per order), and sales by governorate/branch — like PDF page 3 but computed from real data.

**Why this priority**: Highest-frequency question set for merchandising decisions.

**Independent Test**: Navigate to Sales page; trend, top products table, and category donut render with period + category filters.

**Acceptance Scenarios**:

1. **Given** Sales page, **When** a category filter is applied, **Then** trend and top products recompute for that category only.
2. **Given** Sales page, **When** period = Last 12 months, **Then** monthly trend shows 12 points (Oct 2025–Oct 2026 partial) with YoY comparison line where prior-year data exists.

---

### User Story 4 - Branch Performance page (Priority: P3)

An area manager compares the 80 branches by revenue, growth %, basket size, and orders, with a ranked table + map-like bar breakdown by governorate; top/bottom performers highlighted.

**Why this priority**: The PDF's most detailed concept (page 4) and directly supported data (80 branches, clean join).

**Independent Test**: Branch page renders ranked table sorted by revenue with growth column; filter by governorate works.

**Acceptance Scenarios**:

1. **Given** Branch page, **When** sorted by growth %, **Then** top-5 and bottom-5 highlight as in PDF page 4's "Top performing branches" pattern.
2. **Given** Branch page, **When** a governorate filter is applied, **Then** only branches in that governorate are listed; total revenue recomputes.

---

### User Story 5 - Inventory & Warehouse page (Priority: P3)

An inventory planner sees total stock value/units by month (from monthly_stock), in-stock vs overstock vs low-stock buckets, category breakdown, stockout-risk alerts, and warehouse vs branch stock split.

**Why this priority**: Directly supported (97 months × 92 locations × 16 categories) and a pillar of the concept deck.

**Independent Test**: Inventory page renders status buckets and stock risk alerts from monthly_stock views.

**Acceptance Scenarios**:

1. **Given** Inventory page, **When** it opens, **Then** KPIs show latest-month stock units, stock value, % locations at high stockout risk.
2. **Given** Inventory page, **When** category filter applied, **Then** buckets and trend recompute for that category.

---

### User Story 6 - Customer Intelligence page (Priority: P3)

A CRM manager sees customer base by segment (Retail vs B2B), age bands, governorates, join trend, repeat-purchase rate, RFM-derived segments (Champions/Loyal/At Risk/etc.), and top customers by lifetime value.

**Why this priority**: Data fully supports RFM/CLV derivation; unblocks the assistant's customer questions.

**Independent Test**: Customer page renders segment/age distributions and an RFM segment table; a customer search shows their purchase history.

**Acceptance Scenarios**:

1. **Given** Customer page, **When** it opens, **Then** segment mix, age band mix, and repeat-rate KPIs render from real customer + order data.
2. **Given** a customer_id in search, **When** submitted, **Then** their order history, lifetime spend, and RFM tier display.

---

### User Story 7 - AI business assistant (Priority: P2)

A manager types "What were the top selling products last month?" into the chat and gets: (1) a correct answer computed from the data, (2) the SQL that produced it, (3) the source view, and optional follow-ups ("check inventory", "store performance", "customer insights", "supplier information" per PDF page 23).

**Why this priority**: The product vision on PDF page 23; P2 because it depends on US1 views but can ship alongside/after dashboards.

**Independent Test**: Ask the 20-question gold set; ≥80% produce correct, valid answers.

**Acceptance Scenarios**:

1. **Given** the assistant page, **When** "top 5 selling products last month" is asked, **Then** the answer lists 5 products with units/EGP for the correct latest month and shows the SQL used.
2. **Given** the assistant, **When** asked an out-of-scope question ("order me 500 t-shirts"), **Then** it declines write actions and suggests data questions instead (Principle V).
3. **Given** the assistant, **When** a question maps to an existing dashboard, **Then** a button deep-links to it ("View on Branch Performance →").
4. **Given** the assistant, **When** asked in Arabic, **Then** it answers in Arabic (both languages present in data/UI context).

---

### User Story 8 - Get insights, reports & supplier info shortcuts (Priority: P4)

Assistant sidebar per PDF page 23: Get Insights (top movers/losers digest), View Reports (period report generator returning markdown + table), Check Inventory, Store Performance, Customer Insights, Supplier Information — each a guided prompt template producing an assistant answer from US1 views.

**Why this priority**: Nice-to-have guided UX; requires US7 underlying engine only.

**Independent Test**: Each shortcut button produces a valid answer card.

**Acceptance Scenarios**:

1. **Given** "Check Inventory" clicked for a product search term, **Then** latest stock position + stockout risk returned.
2. **Given** "Supplier Information" clicked, **Then** supplier list with PO volume, on-time %, lead time returned.

---

### Edge Cases

- **Guest orders**: 19% of orders have null customer_id → treated as "Anonymous/Guest" segment; customer-level metrics exclude-or-attribute them by documented policy.
- **Data ends 2026-10-18**: "last month" resolves to last complete month (Sep 2026) with a note; partial-current-month label shown where relevant.
- **Area with no sales in period**: charts render zero-lines without breaking.
- **Assistant hallucination guard**: unanswerable questions (e.g., ESG, planogram — no data) return "not available in the dataset" rather than inventing numbers.
- **LLM offline**: with Ollama down and no API key, assistant shows a clear configuration error and dashboards keep working.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Pipeline MUST load all 25 source CSVs into typed DuckDB tables with documented quality checks run after load.
- **FR-002**: Pipeline MUST create curated analytical views for: daily/mthly sales sales, sales-line enriched dims (product/category/audience/branch/gov/segment), returns, customer RFM, branch aggregates, monthly stock, shipments, transfers, POs, suppliers, payroll/opex, marketing campaigns.
- **FR-003**: UI MUST expose period filter (≥ Last 12 months; Jan–Dec of a year; All-time), persistent across pages.
- **FR-004**: Executive page MUST show KPI cards + monthly trend + top-5 branches + category mix + channel mix (per PDF p2 layout).
- **FR-005**: Sales page MUST show monthly trend, top products, category share, AOV/basket, governorate breakdown (per PDF p3).
- **FR-006**: Branch page MUST show ranked branch table with revenue/growth/AOV + governorate totals (per PDF p4).
- **FR-007**: Inventory page MUST show stock status buckets, category mix, warehouse/branch split, stockout-risk alerts (per PDF p5).
- **FR-008**: Customer page MUST show segment/age/gov distributions, repeat rate, RFM segments, customer lookup (per PDF p6).
- **FR-009**: Assistant MUST answer natural-language business questions by generating validated SELECT-only DuckDB SQL against allowlisted views, executing it, and composing an answer with the SQL visible.
- **FR-010**: Assistant MUST show source attribution (view + SQL) and offer dashboard deep-links when the question matches a page.
- **FR-011**: Assistant MUST support Arabic and English input; metrics stay EGP.
- **FR-012**: Each page MUST show a "Data notes" expander listing known limitations from the scope matrix (e.g., marketing attribution not reconciled).
- **FR-013**: The app MUST run with `uv run streamlit run app/Home.py` on a clean machine after `uv sync`.

### Key Entities *(include if feature involves data)*

- **sales_orders / sales_order_items**: transactional spine (540K orders / 1.14M lines, 2018-10→2026-10), channel, payment, status.
- **customers**: 85K, segments Retail/B2B reseller, age band, governorate.
- **branches**: 80 across 21 governorates (retail vs POS/reseller).
- **products / sku_variants**: 139 products, 695 SKUs, 16 categories.
- **monthly_stock**: 97 months × 92 locations × 16 categories, incl. stockout_risk_score.
- **sales_returns**: 28.5K returns with reason and refund.
- **suppliers / purchase_orders(+items)**: procurement; scale anomaly documented.
- **marketing_campaigns**: 2,200 campaigns, spend/impressions/clicks; attribution anomaly documented.
- **delivery_shipments / inventory_transfers**: fulfillment + replenishment flows.
- **payroll / employees / operating_expenses**: labor & opex (used in later features).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All data-quality tests pass; foreign-key orphans = 0 (except documented guests); gross/net/tax reconciliation exact.
- **SC-002**: All 5 dashboard pages render with real data in <3 s per page query on the target machine.
- **SC-003**: Assistant passes ≥80% of a 20-question gold set (correct metric + correct filter + valid SQL).
- **SC-004**: 100% of shipped KPIs have stored definitions; mockup-vs-data naming map documented in the scope matrix.
- **SC-005**: Clean-machine onboarding script reproduces the demo: `uv sync && pipeline build && streamlit run`.

## Assumptions

- Development machine has Python 3.12 (present), uv (present), Ollama (present); cloud LLM keys optional.
- Single user, read-only; no auth needed for Phase 1.
- Bench/streamlit packages from the existing Anaconda install are NOT reused; project uses its own uv venv (Anaconda has broken numpy/numexpr combos).
- Mockup visual language (navy cards, KPI tiles, delta badges) is the design target; exact numbers are not.
- US7 provider-agnostic LLM: default local Ollama; OpenAI-compatible endpoints via env var.
