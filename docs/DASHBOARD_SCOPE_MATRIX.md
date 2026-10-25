# DASHBOARD SCOPE MATRIX — Deck (23 pages) → Dataset Reality

**Owner decision reference** · Created 2026-10-24 · Companion to `docs/PROJECT_PLAN.md`.

Legend: **Ready** = directly computable · **Derived** = buildable via modeling/statistics · **Partial** = some fields exist, some don't (documented carve-outs) · **Missing** = no source columns (needs synthesized demo data or out-of-scope) · **Ship-when**: planned feature.

| # | Deck page | Dashboard concept | Data support | Ship-when | Notes / carve-outs |
|---|---|---|---|---|---|
| — | p1 | Cover (branding) | — | — | theme only |
| 1 | p2 | Executive Overview | **Ready** | **001** | full support (sales, profit, branches, mix) |
| 2 | p3 | Sales Performance Intelligence | **Ready** | **001** | top products, seasonality, branch split |
| 3 | p4 | Branch Performance Optimization | **Ready** | **001** | 80 branches × 21 gov.; ranked + growth |
| 4 | p5 | Inventory & Warehouse Intelligence | **Ready** | **001** | monthly_stock 97mo × 92 loc × 16 cat |
| 6 | p6 | Customer Segmentation & Loyalty | **Derived** | **001** | RFM built from orders; age/gov real; join trend real |
| 7 | p7 | Demand Forecasting & Product Planning | **Derived** | 003 | seasonal decompose + Holt-Winters; no ML infra |
| 8 | p8 | Supply Chain & Logistics Visibility | **Partial** | 002 | shipments + transfers real; no supplier→shipment link, no "in transit" queue beyond status |
| 9 | p9 | Procurement & Supplier Analytics | **Partial** | 002 | volumes/lead-times real; **spend unusable vs COGS (A1)** |
| 10 | p10 | Returns & Quality Control | **Partial** | 002 | returns + reasons real; no defect funnel stages / claims table |
| 15 | p15 | Marketing ROI & Campaign Performance | **Partial** | 002 | spend/impressions/clicks real; attribution rebuilt (A2) |
| 21 | p22 | Wholesale & Distributor Performance | **Ready** | 002 | B2B segment + wholesale channel; **no distributor accounts table** → accounts = aggregated B2B customers |
| 14 | p14 | Omnichannel Commerce & Digital Analytics | **Partial** | 003 | 3 channels (POS/E-com/Wholesale) vs deck's 6; no app/social/marketplace data |
| 19 | p19 | Customer Lifetime Value & Churn | **Derived** | 003 | CLV, RFM tiers, churn from order recency |
| 16 | p16 | Product Profitability & Margin Intelligence | **Derived** | 003 | line margin exists; ranking/alerts to build |
| 18 | p18 | Smart Replenishment & Auto Allocation | **Derived** | 003 | stockout risk + transfers + sales velocity → reorder suggestions (rules, not ML) |
| 13 | p13 | Price Optimization & Promotion Intelligence | **Derived** | 003 | discount depth real; elasticity estimated with regression (approximation, labeled) |
| 17 | p17 | Workforce Productivity & Store Ops | **Partial** | 004 | payroll/labour cost real; **service scores, checkout time, task completion not in data** → labor analytics only |
| 12 | p12 | New Store Expansion & Site Selection | **Missing** | out / 004 | no demographics/competition/health data; possible branch-gap proxy view |
| 11 | p11 | Sustainability & ESG Analytics | **Missing** | **out** | no energy/water/waste/sourcing metrics |
| 20 | p20 | Visual Merchandising & Planogram | **Missing** | **out** | no audit/diswhere/space data |
| 22 | p21 | Loss Prevention & Shrinkage | **Missing** | out | no incident/variance audit trail; receipts↔stock variance not reconstructable |
| — | p23 | **AI-Powered Business Assistant** | **Derived** | **001 (core), Ext in 002/003** | chat + shortcuts (Get Insights / Reports / Inventory / Store Performance / Customer Insights / Supplier Info) |

## Build phases

- **001 Core (now)**: data foundation + Exec/Sales/Branch/Inventory/Customers + assistant with shortcuts → all `Ready`/`Derived` items above marked 001.
- **002 Supply & Marketing edge**: p8, p9, p10, p15, p22.
- **003 Advanced analytics**: p7, p13, p14-lite, p16, p18, p19.
- **004 Optional / stripped**: p12-lite (branch-gap), p17-lite (labor cost), others = explicit **out-of-scope** until owner provides synthesized demo data (Constitution II: never fake silently).

## Deck page → feature mapping (page 23 assistant rail)

| Assistant rail item (deck p23) | Backing views |
|---|---|
| Ask Questions | text→SQL over view allowlist |
| Get Insights | period digest: movers/losers, returns spike, stockout alerts |
| View Reports | period report (markdown + KPI table) |
| Check Inventory | `050_stock_monthly` + product search |
| Store Performance | `025_branch_summary` (+ deep-link Branch page) |
| Customer Insights | `085_customer_profile` (RFM) |
| Supplier Information | `070_supplier_pos` (volumes, lead time, on-time) |
