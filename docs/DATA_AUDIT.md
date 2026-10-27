# Cottonil Dataset — Data Audit & Metric Dictionary

**Audited**: 2026-10-24 · Source: `COTTONIL/COTTONIL_Data/` (25 CSVs) · Tooling: pandas profiling session (reproducible: audit script saved in worktree history). Feature 003 model extensions audited 2026-10-26 (A11–A15); Feature 004 workforce/expansion proxies audited 2026-10-26 (A16–A17).

This is the runtime guidance referenced by Constitution Principle IV ("Trust & Traceability"). Any shipped KPI must have a definition here or in a view SQL file.

## 1. Dataset inventory (all loads verified clean)

| Table | Rows | Grain / purpose | Key integrity |
|---|---:|---|---|
| branches | 80 | Store/POS network, 21 governorates, opened 2018-11→2020-08 | ID unique |
| customers | 85,000 | Retail 83,334 / B2B 1,666; age bands ≈ uniform; joined 2018-10→2026-10 | ID unique |
| sales_orders | 540,000 | Order header 2018-10-19→2026-10-18; channels: POS 49.5% / Wholesale 38.0% / E-com 12.5% | FK→branch/customer OK (19% guest-null) |
| sales_order_items | 1,138,536 | Order lines; price, discount, net, unit cost, margin per line | FK→orders/SKU/product OK 100% |
| sales_payments | 540,000 | 1 payment per order, all `Paid` | FK→orders OK |
| sales_returns | 28,500 | 5.28% of orders; reasons: Size issue / Defect claim / Wrong item / Exchange / Other | FK→order+line OK |
| products_catalog | 139 | Product level, 16 categories (e.g., Socks 76, Men tops 9…) | ID unique |
| sku_variants | 695 | Size/color variants (multiplier 0.95–1.05) | FK→product OK |
| monthly_stock | 142,784 | 97 months × 92 locations (80 branches + 12 warehouses) × 16 categories | FK→locations OK |
| inventory_transfers(_items) | 36,500 / 109,614 | WH→branch replenishment, costs 28.9M EGP | FK OK |
| purchase_orders(_items) | 41,500 / 103,334 | Supplier POs receiving into 11 warehouses | FK OK (see anomaly A1) |
| delivery_shipments | 97,660 | E-com/delivery shipments; 3.03% `Delayed` | FK→orders OK |
| import_partners/ _shipments | 16 / 4,200 | Import containers, customs/freight in USD | FK OK |
| suppliers | 48 | 10 material types | ID unique |
| employees | 640 | 5 store positions across 80 branches | FK→branch OK |
| payroll | 13,210 | Monthly, net paid total 59.5M EGP | FK→employee OK |
| operating_expenses | 47,000 | 10 expense categories, 135.6M EGP | FK→branch/WH OK |
| marketing_campaigns | 2,200 | 6 channels, spend 219.5M EGP | internal (see anomaly A2) |
| factories / import_partners / warehouses | 6 / 16 / 12 | Small static dims | OK |
| data_dictionary | 169 | Field descriptions | Advisory only |
| catalog_reference | 238 | Public website reference: 139 rows in the canonical `PRxxxx` id space + 99 supplementary `PUBxxxx` rows (website-only products) | see A9 |

Note: `data_dictionary` describes a `loyalty_tier` column on customers.csv that the actual file does not contain — treat the dictionary as advisory, never authoritative.

Financial mechanics are exact (zero tolerance checks):
`gross_EGP − discount_EGP = net_before_tax_EGP` (100% match) · `tax = 14% ±0.0004` · `paid_total = net + tax` (100%) · `line sums = order totals` (exact) · `items_count = line count` (100%).

## 2. Metric dictionary (v1 core)

| Metric | Definition (from views) |
|---|---|
| Net Sales | Σ `net_line_EGP` (excl. 14% VAT) over period |
| Gross Sales | Σ `gross_line_EGP` |
| Discount Rate | discount / gross per line/period |
| Gross Profit | Σ `margin_EGP` (line margin field) |
| Margin % | margin / net_line |
| AOV / Basket | net_before_tax / order count; items/order = Σ qty / orders |
| Return Rate | returned orders / orders in period (line-level variant: qty returned / qty sold) |
| Net Revenue after Returns | net sales − capped refunds (A3) |
| Active Customers | distinct non-null customer_id with ≥1 order in period |
| Repeat Rate | customers with ≥2 orders / active customers (period) |
| RFM Segments | recency (days from last order vs dataset end), frequency, monetary → Champions / Loyal / Potential Loyalist / Need Attention / At Risk / Churned (deck p19 naming) |
| Stock | `monthly_stock.closing_units/value` by month, location type, category |
| Stockout Risk | avg/≥0.7 share of `stockout_risk_score` |
| On-time Delivery | `delivered` / shipments (delivery_shipments) |
| Fill Rate | transfer lines received qty / requested qty proxy (transfers × status) |
| Sell-through | sold units / (sold + closing stock) per category-month |
| Wholesale Net | net sales where `sales_channel='Wholesale / reseller'` (B2B customers 1,666) |
| Labor Cost Ratio | `views.workforce_monthly`: `net_paid` / branch-attributed net sales in the same branch-month; `net_paid = base + overtime + bonus − deductions` (A16) |
| Paid Employees | distinct employees with a payroll record in a branch-month; payroll-covered headcount, not active headcount or FTE (A16) |
| Workforce Coverage | branch-months with a payroll record / (branches × months); 2023 = 922/960 (96.0%) (A16) |
| OPEX | operating_expenses by category/branch |
| Demand Forecast | Holt-Winters (additive damped trend, multiplicative seasonality) on complete months; 6-month horizon; WAPE = Σ\|forecast−actual\| / Σ\|actual\| over 12-month rolling origins; band = P80 absolute % error (A15) |
| Price Elasticity | within-SKU and within-month log units on log net price + discount rate; SKU-clustered SE; within-R² (A11) |
| Channel Mix | `views.channel_monthly` net sales / orders / customers by order channel (Retail POS, E-commerce, Wholesale); guests count in revenue only (A4) |
| Historical CLV | Σ `gross_profit_lifetime` per identified buyer; descriptive gross profit, not a forecast (A12) |
| Churn Rate | customers with no order for 365+ days / customers with 365+ days tenure; never-purchased and insufficient-history customers excluded (A12) |
| Replenishment Cover | closing units / 90-day daily velocity; reorder = max(0, ceil(velocity × 45 − closing units)) (A14) |
| SKU-Month Margin | gross profit / net sales at SKU × month; low-margin flag = margin < 30% (display policy) (A13) |
| Expansion Coverage Gap | governorate branch-network share − resident-buyer share (pp); descriptive coverage intensity, not market potential (A17) |

**Monetary unit**: always EGP. Import/customs data is USD — convert with a documented static rate table only when used (import feature is out of v1 scope). The deck's wholesale page in `$M` is ignored → EGP.

## 3. Known anomalies & handling policies (Constitution III/IV)

### A1 — Purchase orders scale mismatch
PO line totals sum to **29.15B EGP over 8 years vs 841M EGP of sales (34.7×)**; median unit cost ≈54 EGP across every material type (flat synthetic artifact). **Policy: procurement dashboards report PO volumes, lead times, supplier on-time % as absolute metrics; never reconcile PO spend against COGS or revenue; do not derive product cost from PO data.** Flagged with a permanent note wherever shown.

### A2 — Marketing attribution inflation
`orders_attributed` sums to **24.1M vs 540K real orders** (values look random, CTR ~4.4%). **Policy: never use `orders_attributed` for revenue or conversion math. Conversions = re-attributed real sales orders overlapping campaign window × governorate × audience; impressions/clicks/spend used as platform-reported absolutes only.** Marketing ROI becomes directional (spend vs. organic baseline uplift), with the method documented.

### A3 — Refunds exceed line value
`refund_amount_EGP / net_line_EGP` reaches 124.9% (median 92%). **Policy: refund analytics cap refunds at line net value; raw value kept in raw table.**

### A4 — Guest orders
19.07% of orders have `customer_id` null. **Policy: treated as "Guest / Anonymous" flow (equals deck's "New customers"); customer-level metrics exclude them and state so; they still count fully in revenue/branch metrics.**

### A5 — "Last month" boundary
Data ends **2026-10-18**. Default "Last 12 months" = Oct 2025→Oct 2026 (partial Oct). "Last month" = **September 2026 (last complete month)**, labeled in UI.

### A6 — Price semantics
Sales `unit_price_EGP` runs well below `listed_price_EGP` (median 0.406×; catalog prices look like multi-pack list prices). **Policy: pricing analytics use actual line prices only; no pack/listed comparisons shipped without a note.**

### A7 — Stock-to-sales scale
Monthly closing stock value ≈ 346M EGP (Oct 2026) against ~239M EGP of 2026-to-date net sales; internally consistent for a stock-holding retailer; no adjustment.

### A8 — Distribution columns unused/out-of-syllabus
`scope_matrix` marks ESG (p11), Planogram (p20) and Loss Prevention (p21) as **not derivable** — no source columns exist (energy, waste, audits, incidents). They remain excluded from v1 and would be marked IF the deck's owner wants synthesized demo data (explicitly labeled synthetic, Constitution II). Store Expansion (p12) has no demographics/competitor/rent/catchment inputs either, so Feature 004 ships only the governorate coverage-intensity proxy documented in A17 — not a site-selection model.

### A9 — Public reference catalog uses a second ID namespace
`01_CATALOG/PRODUCT_CATALOG_PUBLIC_REFERENCE.csv` has 238 rows: the 139 canonical sales products (`PRxxxx`, all covered — DQ-gated) plus 99 supplementary `PUBxxxx` rows for website-only products that never appear in sales. **Policy: `PUBxxxx` rows are enrichment-only metadata; never joins/sales consumption; not valid product dimension members.**

### A10 — Pipeline float-summation drift
One-cent tolerance applies to *aggregate* SUM comparisons (accumulation order of float adds); row-level reconciliation remains exact (DQ gate enforces 0 offending rows).

### A11 — Price/demand independence (no usable elasticity)
Within the 66,627 selling SKU-months (695 SKUs × 97 months), the two-way within (SKU + month fixed effects) log-log regression gives a price coefficient of **+0.2292** (SKU-clustered SE 0.1123, p 0.0413) — the wrong sign for demand — with within-R² **0.000227**. The discount coefficient is +0.0161 (p 0.925). Discounts average **4.32%**, **96.0%** of SKU-months carry one, and the mean absolute within-SKU monthly price move is **6.42%**, leaving little independent price variation. **Policy: the estimate is a diagnostic, not a pricing tool. Never use it to set prices, forecast promotion lift or claim promotion ROI; say the data show no usable price response.**

### A12 — Churn is not predictable from the available features
Churn is defined as no purchase for 365+ days among customers with 365+ days of tenure: **47,680 Active**, **23,138 Churned**, **3,842 Insufficient history**, **10,340 Never purchased** → 70,818 eligible buyers, churn rate **32.7%**. A temporal holdout (train cutoff 2024-10-18, test cutoff 2025-10-18; features strictly pre-cutoff, label = purchase in the next 365 days) scores **AUC 0.4995**, accuracy **64.19%**, base churn **35.81%**, predicted churn **34.43%**; holdout deciles are flat at roughly 35–36%. Twelve-month repurchase is **64.1%** overall and essentially flat across recency buckets (0–30 through 365+ days). **Policy: churn status is descriptive only. Do not rank customers, target retention spend or claim predictive CLV from the model score; report the failed holdout rather than hiding it.**

### A13 — SKU-month margin dispersion vs product-level uniformity
All-time product margins cluster tightly at **37.57–39.39%** across 139 products, so product-level margin ranking is uninformative. SKU-month margins range **7.53–55.89%** (median **38.38%**); **4.38%** of SKU-months sit below 30%, representing **0.83%** of net sales. **Policy: analyse margin at SKU × month. The 30% low-margin flag is a display/review threshold chosen after profiling, not a company policy or loss claim; margin uses recorded unit cost and excludes operating expenses, post-sale markdowns, shrinkage and freight.**

### A14 — Replenishment is a transparent heuristic, not an optimiser
`views.replenishment_signals` covers the latest stock snapshot (2026-10): **1,472** location × category cells. Branches use 90-day sales velocity; warehouses use 90-day outgoing-transfer velocity (warehouses do not sell). Rule: 45-day target cover, reorder = `max(0, ceil(velocity × 45 − closing units))`. Signal distribution: **931 Overstock (>180d)**, **405 Adequate (45–180d)**, **52 Below target (30–45d)**, **49 Low (14–30d)**, **23 Critical (<14d)**, **12 No demand signal**. Branches: 119 below target; warehouses: 5 below target plus 12 with no recent transfers. **Policy: the output is a category-level signal, not a purchase order. There is no lead time, MOQ, shelf life, seasonality, budget constraint, supplier capacity or open-PO netting; a buyer must translate it into SKUs.**

### A15 — Demand forecast caveats
The forecast uses **96 complete months** (2018-11 → 2026-09); the partial month 2026-10 (dataset ends 2026-10-18) is excluded from fitting and backtests. Model: Holt-Winters with additive damped trend and multiplicative seasonality, 6-month horizon, three rolling 12-month origins. Latest holdout / mean WAPE: **units 3.03% / 3.29%**; **net sales 7.27% / 9.16%**. The planning band is the **80th percentile of absolute percentage errors**, not a statistical confidence interval, and it does not widen with horizon. **Policy: this is a baseline, not a commitment. No causal drivers (price, promotion, stockouts, weather, competitors, distribution) and no SKU-level forecasts; always show the backtest error with the forecast.**

### A16 — Workforce data are payroll-covered only
`views.workforce_monthly` has **5,644 branch-months** (80 branches × 97 months, 2018-10 to 2026-10) built from **13,210 payroll rows** for **640 employees** (exactly 8 per branch, 3 positions per branch). Each employee has a continuous payroll window of **9–34 months** (median **20**); there is no termination date, so a month without a record cannot be classified as termination, leave or a data gap. The payroll identity holds exactly: **net paid = base + overtime + bonus − deductions** on all 13,210 rows (net paid **EGP 59.52M**; overtime **4.07M**; bonus **5.90M**; deductions **1.21M**). Paid headcount peaks at **225 in 2023-03** and falls to **10 in 2026-10**. **Policy: `paid_employees` means payroll-covered headcount, not active headcount or FTE; the decline is coverage/tenure behaviour, not evidence of layoffs. There are no hours, attendance, FTE conversion, checkout times, tasks, service scores, recruiting cost, benefits or employer tax fields. Branch sales include e-commerce and wholesale orders carrying a `branch_id`, so sales per paid employee is not store footfall or hourly productivity.** Reference year 2023 is used for the broadest full-year coverage: **72 of 80 branches have 12 payroll months** (**922/960 branch-months, 96.0%**; 2024 has slightly more branch-months at 926 but only 69 full-year branches). Net payroll **EGP 10.99M** against **EGP 80.88M** of sales in the same covered branch-months, labor cost ratio **13.59%**, payroll **EGP 4,261** and sales **EGP 31,351** per employee-month. Eight partial-coverage branches are excluded from the branch table because missing payroll would understate their ratios.

### A17 — Store expansion is a governorate coverage proxy, not site selection
`views.expansion_gap` has one row per governorate (**21**), covering **80 branches** (52 retail + 28 POS/reseller) and **85,000 cataloged customers**. Every governorate already has at least one branch, so there is no greenfield whitespace. Identified demand: **74,660 resident buyers** (3,469–3,648 per governorate), buyer penetration **87.1–88.6%**, resident net sales **EGP 680.3M** (EGP 31.2M–34.0M per governorate). Branch side: all-channel net sales **EGP 841.3M** (EGP 9.84M–11.43M per branch); Retail POS net sales **EGP 416.2M** (EGP 5.06M–5.28M per branch). The coverage gap is branch-network share minus resident-buyer share: Cairo **+21.51 pp**, Alexandria **+7.66**, Giza **+2.78**, and about **−3.45 to −3.48** for one-branch governorates; buyers per branch range from **168** (Cairo) to **3,530** (Red Sea). **Policy: this is a descriptive coverage-intensity proxy, not market potential or an investment case. `branch_id` is not geographic: 95.2% of identified order lines have `customer_governorate_ar != branch_governorate_ar`, so residence-based and branch-attributed lenses are separate and cannot be reconciled as catchment or leakage. Resident customers and branch POS per branch are near-uniform, making the ranking mostly a branch-count ranking (correlation buyers/branch vs POS/branch **−0.24**). There are no demographics, income, competitor, rent, footfall, catchment, cannibalisation, store-health, lease or capital-cost inputs, and no composite site-selection score or ranked expansion list.**

## 4. Deck-vs-data number reconciliation (for stakeholders)

| Deck (illustrative) | Actual dataset | Note |
|---|---|---|
| 1.24M customers, 186 branches, EGP 512.8M sales | 85K customers, 80 branches, EGP 148.8M (2024) | Build with actuals; deck numbers are marketing fiction |
| 85 branches (p21) / Cairo 38% share (p4) | 80 branches; Cairo-branched share computable | close |
| 4.8% return rate (p10) | 5.28% of orders | same ballpark |
| $12.4M wholesale (p22) | EGP ~89M (2025 wholesale channel) | EGP normalization per metric dictionary |
| 12.4M impressions 804K clicks (p15) | 4.9M avg/campaign impressions | platform-reported fields retained |
