# DASHBOARD SCOPE MATRIX — Deck (23 pages) → Dataset Reality

**Owner decision reference** · Created 2026-10-24 · Companion to `docs/PROJECT_PLAN.md`.

Legend: **Ready** = directly computable · **Derived** = buildable via modeling/statistics · **Partial** = some fields exist, some don't (documented carve-outs) · **Missing** = no source columns (needs synthesized demo data or out-of-scope) · **Ship-when**: planned feature.

## Feature 001 shipping status (2026-10-25)

Code as tasks mark shipped for **001 Core**: p1 cover/theme, p2 Executive (`pages/1`), p3 Sales (`pages/2`), p4 Branch (`pages/3`), p5+6-row-4 Inventory (`pages/4`), p6 Customers/RFM (`pages/5`), p23 Assistant chat + shortcut rail (`pages/6`). Unshown deck rows below stay at their planned feature (002/003/004/out) with no code today.

## Feature 002 shipping status (2026-10-26)

Code as tasks mark shipped for **002 Supply & Marketing edge**: p8 Supply Chain (`pages/7`), p9 Procurement (`pages/8`), p10 Returns & Quality (`pages/9`), p15 Marketing ROI (`pages/10`), p22 Wholesale (`pages/11`). New curated views: `delivery_ops`, `transfer_ops`, `procurement_monthly`, `wholesale_accounts`; existing `returns_enriched`, `supplier_pos`, `campaigns_clean` and `sales_enriched` are reused. The data carve-outs below remain in force.

## Feature 003 shipping status (2026-10-26)

Code as tasks mark shipped for **003 Advanced analytics**: p7 Demand Forecast (`pages/12`), p13 Price & Promotion (`pages/13`), p14 Omnichannel Lite (`pages/14`), p16 Product Profitability (`pages/15`), p18 Smart Replenishment (`pages/16`), p19 CLV & Churn (`pages/17`). New curated views: `demand_monthly`, `product_monthly`, `sku_monthly`, `channel_monthly`, `replenishment_signals`, `customer_clv`. Reusable model logic lives in `app/analytics.py`. Failed or weak model signals are disclosed on the pages: price elasticity has no usable signal (A11) and the churn holdout has no discrimination (A12).

## Feature 004 shipping status (2026-10-26)

Code as tasks mark shipped for **004 Optional lites**: p17 Workforce Productivity (`pages/18`) and p12 Store Expansion as a gap proxy (`pages/19`). New curated views: `workforce_monthly`, `expansion_gap`. Both are deliberately narrow, descriptive proxies: payroll-covered labour only (no hours/FTE/service data, A16) and governorate coverage intensity only (no demographics/competitors/rent/catchment, A17). Neither page uses the sidebar reporting period: p18 is fixed to reference year 2023 (broadest full-year payroll coverage), p19 is an all-time profile.

| # | Deck page | Dashboard concept | Data support | Ship-when | Notes / carve-outs |
|---|---|---|---|---|---|
| — | p1 | Cover (branding) | — | — | theme only |
| 1 | p2 | Executive Overview | **Ready** | **001** | full support (sales, profit, branches, mix) |
| 2 | p3 | Sales Performance Intelligence | **Ready** | **001** | top products, seasonality, branch split |
| 3 | p4 | Branch Performance Optimization | **Ready** | **001** | 80 branches × 21 gov.; ranked + growth |
| 4 | p5 | Inventory & Warehouse Intelligence | **Ready** | **001** | monthly_stock 97mo × 92 loc × 16 cat |
| 6 | p6 | Customer Segmentation & Loyalty | **Derived** | **001** | RFM built from orders; age/gov real; join trend real |
| 7 | p7 | Demand Forecasting & Product Planning | **Derived** | **003 shipped** | Holt-Winters + rolling-origin backtest; units WAPE 3.0–3.3%, net sales 7.3–9.2% (A15) |
| 8 | p8 | Supply Chain & Logistics Visibility | **Partial** | 002 | shipments + transfers real; no supplier→shipment link, no "in transit" queue beyond status |
| 9 | p9 | Procurement & Supplier Analytics | **Partial** | 002 | volumes/lead-times real; **spend unusable vs COGS (A1)** |
| 10 | p10 | Returns & Quality Control | **Partial** | 002 | returns + reasons real; no defect funnel stages / claims table |
| 15 | p15 | Marketing ROI & Campaign Performance | **Partial** | 002 | spend/impressions/clicks real; attribution rebuilt (A2) |
| 21 | p22 | Wholesale & Distributor Performance | **Ready** | 002 | B2B segment + wholesale channel; **no distributor accounts table** → accounts = aggregated B2B customers |
| 14 | p14 | Omnichannel Commerce & Digital Analytics | **Partial** | **003 shipped** | 3 channels (POS/E-com/Wholesale) vs deck's 6; no app/social/marketplace data; observed cross-channel customers only |
| 19 | p19 | Customer Lifetime Value & Churn | **Derived** | **003 shipped** | historical gross-profit CLV + 365-day churn status; churn holdout AUC 0.50 = no usable discrimination (A12) |
| 16 | p16 | Product Profitability & Margin Intelligence | **Derived** | **003 shipped** | SKU-month margin variation + top-profit products; 30% low-margin flag is a display policy (A13) |
| 18 | p18 | Smart Replenishment & Auto Allocation | **Derived** | **003 shipped** | 45-day cover rule on the latest stock snapshot; branches use sales velocity, warehouses transfers; no lead-time/MOQ (A14) |
| 13 | p13 | Price Optimization & Promotion Intelligence | **Derived** | **003 shipped** | discount depth real; within-SKU/month regression shows no usable elasticity → diagnostic only (A11) |
| 17 | p17 | Workforce Productivity & Store Ops | **Partial** | **004 shipped** | payroll-covered headcount + labor cost ratio; **no hours, FTE, service scores, checkout time or task completion** (A16); reference year 2023 |
| 12 | p12 | New Store Expansion & Site Selection | **Missing** | **004 shipped (proxy)** | site selection unavailable (no demographics/competition/rent/catchment); shipped only as a governorate coverage-intensity proxy (A17) |
| 11 | p11 | Sustainability & ESG Analytics | **Missing** | **out** | no energy/water/waste/sourcing metrics |
| 20 | p20 | Visual Merchandising & Planogram | **Missing** | **out** | no audit/diswhere/space data |
| 22 | p21 | Loss Prevention & Shrinkage | **Missing** | out | no incident/variance audit trail; receipts↔stock variance not reconstructable |
| — | p23 | **AI-Powered Business Assistant** | **Derived** | **001 (core), Ext in 002/003** | chat + shortcuts (Get Insights / Reports / Inventory / Store Performance / Customer Insights / Supplier Info) |

## Build phases

- **001 Core (shipped 2026-10-25)**: data foundation + Exec/Sales/Branch/Inventory/Customers + assistant with shortcuts → all `Ready`/`Derived` items above marked 001.
- **002 Supply & Marketing edge (shipped 2026-10-26)**: p8, p9, p10, p15, p22.
- **003 Advanced analytics (shipped 2026-10-26)**: p7, p13, p14-lite, p16, p18, p19.
- **004 Optional lites (shipped 2026-10-26)**: p17-lite (payroll-covered labor, `pages/18`), p12-lite (governorate coverage gap, `pages/19`). ESG, Planogram and Loss Prevention remain explicit **out-of-scope** until the owner provides synthesized demo data (Constitution II: never fake silently).

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

Feature 004 adds `workforce_monthly` and `expansion_gap` to the assistant allow-list, with deep links to pages 18–19. Neither is part of the deck's p23 shortcut rail; they are answer sources only.
