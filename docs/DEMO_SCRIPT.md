# Two-Minute Demo Script (feature 001)

Audience: HVIA Task 3 reviewers. Screen: `uv run streamlit run app/Home.py` at fullscreen.
Pre-roll (before recording): `uv run build` + `uv run checks`, Ollama running (`ollama serve`, model pulled), `uv run pytest -q` passed.

| # | Seconds | Action | Say |
|---|---------|--------|-----|
| 1 | 0:00–0:15 | Land on **Home**. Point at the 4 KPI tiles, then open *About this app — data & policies*. | "Everything you'll see is computed live from 25 raw CSVs into one DuckDB. Real data only — the deck's numbers were illustrative: we actually have 540K orders, 80 branches, 85K customers through 2026-10-18, in EGP." |
| 2 | 0:15–0:45 | Exec Overview page: flick the period selector **Calendar year → 2025**, then back to **Last 12 months**. | "Fifty KPI cards? No — five honest ones. Every delta compares the same calendar window a year earlier, never a cherry-picked slice. The trend line reads monthly net and profit straight from the curated spine." |
| 3 | 0:45–1:05 | **Sales Performance**: pick a category, show the trend + top products table snap to it; then **Branch page**: hover the quadrant scatter, red dots below the median. | "The category picker scopes the whole page. On branches, dot size is orders; growth-colored tables flag 'n/a' for branches with no prior window instead of printing a fake zero." |
| 4 | 1:05–1:20 | **Inventory**: read snapshot tiles (2026-10: 1.8M units, EGP 346.0M) + open the risk-alerts table. | "Stock is tracked monthly per location × category. The at-risk filter uses the deck's ≥0.70 alert line; the low-stock bucket threshold is disclosed separately." |
| 5 | 1:20–1:50 | **Assistant**: click ▶ *Get insights*; then ask two questions — "أعلى 5 فروع مبيعاً في 2025" and "Show returns by reason". Expand *SQL used* on the second. | "Ask in Arabic or English. Every answer is a guarded read-only SELECT — writes are refused by contract — and each message shows the exact SQL and lets you jump to the dashboard that matches. The assistant knows the data quirks: it won't compare purchase-order totals to revenue (audit A1) and it flags guest checkouts honestly." |
| 6 | 1:50–2:00 | Terminal: `uv run pytest -q` scroll of greens + goldset line. | "Underneath: 45 tests — data, pages, assistant safety, a 20-question goldset — same gates run on every commit." |

## Screenshot checklist
- [ ] Home hero + four all-time KPI tiles
- [ ] Executive with Last-12-months KPI strip + monthly trend
- [ ] Sales page with a single category selected
- [ ] Branch quadrant scatter (growth colors)
- [ ] Inventory risk alerts table
- [ ] Assistant: Arabic question answered + SQL expander open
- [ ] Terminal: full pytest run green

## Known-demo facts (say these confidently)
- Net sales all-time **EGP 841,274,176** excl. 14% VAT · orders **540,000** · buyers **74,660/85,000**.
- Last-12-months net EGP 293.2M, +36.3% vs the same window before.
- Latest stock month 2026-10: **1.8M units / EGP 346.0M**; at-risk cells (≥0.70): **2.2%**.
