"""Central navigation registry — the single source of truth for the app shell.

`build_navigation()` returns the grouped page mapping for `st.navigation`
(six groups, 16 dashboard pages) and `get_page(key)` hands out the registered
`st.Page` objects so assistant deep links always point at a real page.
The Assistant is not a navigation page: it is a floating widget
(`app.assistant_widget`) available on every dashboard.
"""

from __future__ import annotations

import streamlit as st

_PAGE_DIR = "pages"  # relative to app/Home.py (the st.Page path base)

# Key -> (page file, nav title, icon). Keys are stable identifiers shared
# with the assistant deep-link map (§7.8) and the tests.
_PAGES: dict[str, dict[str, str]] = {
    "executive_overview": {
        "file": "1_Executive_Overview.py", "title": "Executive Overview",
        "icon": ":material/analytics:",
    },
    "sales_performance": {
        "file": "2_Sales_Performance.py", "title": "Sales Performance",
        "icon": ":material/trending_up:",
    },
    "branch_performance": {
        "file": "3_Branch_Performance.py", "title": "Branch Performance",
        "icon": ":material/storefront:",
    },
    "wholesale": {
        "file": "11_Wholesale.py", "title": "Wholesale & Distributors",
        "icon": ":material/handshake:",
    },
    "omnichannel": {
        "file": "14_Omnichannel.py", "title": "Omnichannel (Lite)",
        "icon": ":material/compare:",
    },
    "marketing_roi": {
        "file": "10_Marketing_ROI.py", "title": "Marketing ROI",
        "icon": ":material/campaign:",
    },
    "product_profitability": {
        "file": "15_Product_Profitability.py", "title": "Product Profitability",
        "icon": ":material/payments:",
    },
    "price_promotion": {
        "file": "13_Price_Promotion.py", "title": "Price & Promotion",
        "icon": ":material/sell:",
    },
    "demand_forecast": {
        "file": "12_Demand_Forecast.py", "title": "Demand Forecast",
        "icon": ":material/query_stats:",
    },
    "inventory_stock": {
        "file": "4_Inventory_Stock.py", "title": "Inventory & Stock",
        "icon": ":material/inventory_2:",
    },
    "supply_chain": {
        "file": "7_Supply_Chain.py", "title": "Supply Chain & Logistics",
        "icon": ":material/local_shipping:",
    },
    "procurement": {
        "file": "8_Procurement.py", "title": "Procurement & Suppliers",
        "icon": ":material/factory:",
    },
    "returns_quality": {
        "file": "9_Returns_Quality.py", "title": "Returns & Quality",
        "icon": ":material/autorenew:",
    },
    "customer_intelligence": {
        "file": "5_Customer_Intelligence.py", "title": "Customer Intelligence",
        "icon": ":material/groups:",
    },
    "workforce": {
        "file": "18_Workforce_Productivity.py", "title": "Workforce Productivity (Lite)",
        "icon": ":material/work:",
    },
    "expansion": {
        "file": "19_Expansion_Gap.py", "title": "Store Expansion (Gap Proxy)",
        "icon": ":material/rocket_launch:",
    },
}

# Exactly six navigation groups; Executive Overview is the default page.
NAV_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Overview", ("executive_overview",)),
    ("Sales & Channels", (
        "sales_performance", "branch_performance", "wholesale",
        "omnichannel", "marketing_roi",
    )),
    ("Products & Pricing", (
        "product_profitability", "price_promotion", "demand_forecast",
    )),
    ("Supply & Operations", (
        "inventory_stock", "supply_chain", "procurement", "returns_quality",
    )),
    ("Customers", ("customer_intelligence",)),
    ("Organization & Growth", ("workforce", "expansion")),
)


def pages() -> dict[str, st.Page]:
    """Build every registered page exactly once."""
    return {
        key: st.Page(
            f"{_PAGE_DIR}/{spec['file']}",
            title=spec["title"],
            icon=spec["icon"],
            default=(key == "executive_overview"),
        )
        for key, spec in _PAGES.items()
    }


def build_navigation() -> dict[str, list[st.Page]]:
    """Grouped mapping for st.navigation: {group: [st.Page, ...]}."""
    registered = pages()
    return {
        group: [registered[key] for key in keys]
        for group, keys in NAV_GROUPS
    }


def get_page(key: str) -> st.Page:
    """One registered page by key — safe target for st.switch_page."""
    return pages()[key]


def page_names() -> list[str]:
    """Keys in registration order (16 + Home-folded = 16 dashboards)."""
    return list(_PAGES)


def page_files() -> list[str]:
    """File names under app/pages/ for the registered dashboards, in order."""
    return [spec["file"] for spec in _PAGES.values()]


# ------------------------------------------------- assistant deep links (7.8) --
# Curated-view name -> page key. Kept from the old chat page's map; views that
# lived on deleted pages now land on the merged tabs:
#   replenishment_signals -> the Replenishment tab of Inventory & Stock,
#   customer_clv          -> the CLV & Churn tab of Customer Intelligence.
# The widget resolves keys with `get_page()`, so a link can never point at a
# deleted page file.
VIEW_PAGE_MAP: dict[str, str] = {
    "sales_enriched": "executive_overview",
    "monthly_sales": "executive_overview",
    "top_products": "sales_performance",
    "product_overview": "sales_performance",
    "branch_daily": "branch_performance",
    "branch_summary": "branch_performance",
    "stock_monthly": "inventory_stock",
    "stock_status": "inventory_stock",
    "stock_latest": "inventory_stock",
    "customer_rfm": "customer_intelligence",
    "customer_profile": "customer_intelligence",
    "delivery_ops": "supply_chain",
    "transfer_ops": "supply_chain",
    "supplier_pos": "procurement",
    "procurement_monthly": "procurement",
    "returns_enriched": "returns_quality",
    "campaigns_clean": "marketing_roi",
    "wholesale_accounts": "wholesale",
    "demand_monthly": "demand_forecast",
    "channel_monthly": "omnichannel",
    "product_monthly": "product_profitability",
    "sku_monthly": "product_profitability",
    "replenishment_signals": "inventory_stock",
    "customer_clv": "customer_intelligence",
    "workforce_monthly": "workforce",
    "expansion_gap": "expansion",
}
