# Cottonil Dataset — Data Audit & Metric Dictionary

**Audited**: 2026-10-24 · Source: `COTTONIL/COTTONIL_Data/` (25 CSVs) · Tooling: pandas profiling session (reproducible: audit script saved in worktree history).

This is the runtime guidance referenced by Constitution Principle IV ("Trust & Traceability"). Any shipped KPI must have a definition here or in a view SQL file.

## 1. Dataset inventory (all loads verified clean)

| Table | Rows | Grain / purpose | Key integrity |
|---|---:|---|---|
| branches | 80 | Store/POS network, 21 governorates, opened 2018-11→2020-08 | ID unique |
| customers | 85,000 | Retail 83,334 / B2B 1,666; age bands ≈ uniform; joined 2018-10→2026-10 | ID unique |
| sales_orders | 540,000 | Order header 2018-10-19→2026-10-18; channels: POS 49.5% / Wholesale 38.0% / E-com 12.5% | FK→branch/customer ✓ (19% guest-null) |
| sales_order_items | 1,138,536 | Order lines; price, discount, net, unit cost, margin per line | FK→orders/SKU/product ✓ 100% |
| sales_payments | 540,000 | 1 payment per order, all `Paid` | FK→orders ✓ |
| sales_returns | 28,500 | 5.28% of orders; reasons: Size issue / Defect claim / Wrong item / Exchange / Other | FK→order+line ✓ |
| products_catalog | 139 | Product level, 16 categories (e.g., Socks 76, Men tops 9…) | ID unique |
| sku_variants | 695 | Size/color variants (multiplier 0.95–1.05) | FK→product ✓ |
| monthly_stock | 142,784 | 97 months × 92 locations (80 branches + 12 warehouses) × 16 categories | FK→locations ✓ |
| inventory_transfers(_items) | 36,500 / 109,614 | WH→branch replenishment, costs 28.9M EGP | FK ✓ |
| purchase_orders(_items) | 41,500 / 103,334 | Supplier POs receiving into 11 warehouses | FK ✓ (see anomaly A1) |
| delivery_shipments | 97,660 | E-com/delivery shipments; 3.03% `Delayed` | FK→orders ✓ |
| import_partners/ _shipments | 16 / 4,200 | Import containers, customs/freight in USD | FK ✓ |
| suppliers | 48 | 10 material types | ID unique |
| employees | 640 | 5 store positions across 80 branches | FK→branch ✓ |
| payroll | 13,210 | Monthly, net paid total 59.5M EGP | FK→employee ✓ |
| operating_expenses | 47,000 | 10 expense categories, 135.6M EGP | FK→branch/WH ✓ |
| marketing_campaigns | 2,200 | 6 channels, spend 219.5M EGP | internal (see anomaly A2) |
| factories / import_partners / warehouses | 6 / 16 / 12 | Small static dims | ✓ |
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
| Labor Cost % | payroll net + overtime / net sales, per branch (employees→branch) |
| OPEX | operating_expenses by category/branch |

**Monetary unit**: always EGP. Import/customs data is USD — convert with a documented static rate table only when used (import feature is out of v1 scope). The deck's wholesale page in `$M` is ignored → EGP.

## 3. Known anomalies & handling policies (Constitution III/IV)

### A1 — Purchase orders scale mismatch ⚠️
PO line totals sum to **29.15B EGP over 8 years vs 841M EGP of sales (34.7×)**; median unit cost ≈54 EGP across every material type (flat synthetic artifact). **Policy: procurement dashboards report PO volumes, lead times, supplier on-time % as absolute metrics; never reconcile PO spend against COGS or revenue; do not derive product cost from PO data.** Flagged with a permanent note wherever shown.

### A2 — Marketing attribution inflation ⚠️
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
`scope_matrix` marks ESG (p11), Planogram (p20), Loss Prevention (p21), Store Expansion (p12) as **not derivable** — no source columns exist (energy, waste, audits, demographics, incidents). They are excluded from v1 and marked IF the deck's owner wants synthesized demo data (explicitly labeled synthetic, Constitution II).

### A9 — Public reference catalog uses a second ID namespace
`01_CATALOG/PRODUCT_CATALOG_PUBLIC_REFERENCE.csv` has 238 rows: the 139 canonical sales products (`PRxxxx`, all covered — DQ-gated) plus 99 supplementary `PUBxxxx` rows for website-only products that never appear in sales. **Policy: `PUBxxxx` rows are enrichment-only metadata; never joins/sales consumption; not valid product dimension members.**

### A10 — Pipeline float-summation drift
One-cent tolerance applies to *aggregate* SUM comparisons (accumulation order of float adds); row-level reconciliation remains exact (DQ gate enforces 0 offending rows).

## 4. Deck-vs-data number reconciliation (for stakeholders)

| Deck (illustrative) | Actual dataset | Note |
|---|---|---|
| 1.24M customers, 186 branches, EGP 512.8M sales | 85K customers, 80 branches, EGP 148.8M (2024) | Build with actuals; deck numbers are marketing fiction |
| 85 branches (p21) / Cairo 38% share (p4) | 80 branches; Cairo-branched share computable | close |
| 4.8% return rate (p10) | 5.28% of orders | same ballpark |
| $12.4M wholesale (p22) | EGP ~89M (2025 wholesale channel) | EGP normalization per metric dictionary |
| 12.4M impressions 804K clicks (p15) | 4.9M avg/campaign impressions | platform-reported fields retained |
