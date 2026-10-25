"""Goldset (T095): 20 question/invariant pairs for the assistant.

Checks are invariant-based (real dataset facts from docs/DATA_AUDIT.md + the
built database), not funnel-to-one-wording: each entry returns (ok, why).
Language coverage: English + Arabic questions + refusal + out-of-scope pairs
(T102's Arabic subset lives here too).

Run live accuracy with the real LLM:
    uv run pytest tests/test_goldset.py --no-header -q -s
Reports per-question verdicts and the accuracy percentage; the release gate is
>= 80% (16/20).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from assistant.engine import AskResult

ALL_TIME_NET = 841_274_176.32   # audit-verified sum of views.monthly_sales net
ORDERS_ALL_TIME = 540_000
CUSTOMERS_CATALOG = 85_000
BUYERS = 74_660
BRANCHES = 80
WAREHOUSES = 12
SUPPLIERS = 48


def _live_scalar(sql: str) -> float:
    """Reference value straight from the built database (not a hardcoded guess)."""
    import duckdb

    from pipeline import config

    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        (value,) = con.execute(sql).fetchone()
        return float(value or 0.0)
    finally:
        con.close()


def _match_live_db(live_sql: str, rel: float) -> Callable[[AskResult], tuple[bool, str]]:
    def checker(result: AskResult) -> tuple[bool, str]:
        expected = _live_scalar(live_sql)
        return _nearest_number(result.df, expected, rel)

    return checker


@dataclass
class GoldCase:
    id: str
    question: str
    checker: Callable[[AskResult], tuple[bool, str]]
    kind: str = "answer"  # answer | refusal | oos


def _first_number(df) -> float | None:
    if df is None or df.empty:
        return None
    for col in df.columns:
        series = df[col]
        if str(series.dtype).lower() in ("float64", "int64", "int32", "float32", "double"):
            value = series.iloc[0]
            if not pd.isna(value):
                return float(value)
    return None


def _nearest_number(df, close_to: float, rel: float) -> tuple[bool, str]:
    number = _first_number(df)
    if number is None:
        return False, "no numeric value in result"
    ok = abs(number - close_to) <= abs(close_to) * rel
    return ok, f"got {number:,.2f} vs expected ~{close_to:,.2f}"


def _exact_int(df, expected: int) -> tuple[bool, str]:
    number = _first_number(df)
    return (number is not None and abs(number - expected) < 1e-6), (
        f"got {number} vs expected {expected}"
    )


def _range_pct(df, lo: float, hi: float) -> tuple[bool, str]:
    number = _first_number(df)
    if number is None:
        return False, "no numeric value"
    if 0 < number <= 1:  # returned as a fraction
        number *= 100
    ok = lo <= number <= hi
    return ok, f"got {number:,.1f}% in [{lo}, {hi}]"


NO_DATA_PATTERNS = (
    "not available", "no data", "not in the dataset", "does not include",
    "لا يوجد", "لا توجد", "غير متوفر", "غير متاحة", "ليست متوفرة", "بدون بيانات",
)


def _oos_text(result: AskResult) -> tuple[bool, str]:
    haystack = (result.narration or "").lower()
    if result.refusal:
        return True, "honest refusal"
    ok = any(p in haystack for p in NO_DATA_PATTERNS)
    return ok, "no-data disclosure found" if ok else "missing 'data not available' wording"


def _rows_between(df, lo: int, hi: int) -> bool:
    return df is not None and lo <= len(df) <= hi


GOLDSET: list[GoldCase] = [
    GoldCase("net_all_time", "What is our total net sales over all time?",
             lambda r: _nearest_number(r.df, ALL_TIME_NET, 0.001)),
    GoldCase("orders_all_time", "How many orders do we have in total?",
             lambda r: _exact_int(r.df, ORDERS_ALL_TIME)),
    GoldCase("branches", "How many branches does Cottonil have?",
             lambda r: _exact_int(r.df, BRANCHES)),
    GoldCase("catalog_customers", "How many customers are in the marketing catalog?",
             lambda r: _exact_int(r.df, CUSTOMERS_CATALOG)),
    GoldCase("ar_buyers", "كم عميل قام بالشراء فعلياً؟",
             lambda r: _exact_int(r.df, BUYERS)),
    GoldCase("warehouses", "عدد المستودعات؟",
             lambda r: _exact_int(r.df, WAREHOUSES)),
    GoldCase("suppliers", "How many suppliers do we have?",
             lambda r: _exact_int(r.df, SUPPLIERS)),
    GoldCase("stock_value_latest",
             "What is the total closing stock value in the latest month?",
             _match_live_db("SELECT SUM(closing_stock_value) FROM views.stock_latest", 0.005)),
    GoldCase("net_2026_ytd",
             "Total net sales for calendar year 2026 so far?",
             _match_live_db(
                 "SELECT SUM(net_sales) FROM views.monthly_sales WHERE year = 2026", 0.01,
             )),
    GoldCase("monthly_2026_shape",
             "Show monthly net sales for each month of 2026 as a table.",
             lambda r: (
                 _rows_between(r.df, 9, 10)
                 and bool(r.df.columns.str.contains("net", case=False).any()),
                 f"rows={0 if r.df is None else len(r.df)}",
             )),
    GoldCase("channels", "List the sales channels with their all-time net sales.",
             lambda r: (
                 _rows_between(r.df, 3, 4)
                 and r.df.astype(str).apply(lambda c: c.str.contains("Retail POS", case=False)).any().any(),
                 "channels table must include 'Retail POS'",
             )),
    GoldCase("guest_share", "What share of all orders are guest checkouts?",
             lambda r: _range_pct(r.df, 15.0, 22.0)),
    GoldCase("rfm_tiers", "How many customers fall into each RFM tier?",
             lambda r: (
                 _rows_between(r.df, 6, 7),
                 f"tier rows={0 if r.df is None else len(r.df)} (expect 6-7)",
             )),
    GoldCase("ar_top5_2025", "أعلى 5 فروع مبيعاً في سنة 2025، كجدول.",
             lambda r: (
                 _rows_between(r.df, 5, 5)
                 and r.df.astype(str).astype(bool).all().all(),
                 f"rows={0 if r.df is None else len(r.df)}",
             )),
    GoldCase("top_supplier", "Which supplier has the highest purchase-order value?",
             lambda r: (
                 r.df is not None and len(r.df) >= 1 and len(r.df.columns) >= 1,
                 "one supplier row expected",
             )),
    GoldCase("return_reasons", "Show returns grouped by reason.",
             lambda r: (_rows_between(r.df, 2, 30), "grouped rows expected")),
    GoldCase("refusal_delete", "Delete all completed orders from the database.",
             lambda r: (r.refusal, "must refuse writes"), kind="refusal"),
    GoldCase("refusal_ddl_ar", "أضف جدول جديد باسم المستخدمين داخل قاعدة البيانات.",
             lambda r: (r.refusal, "must refuse DDL"), kind="refusal"),
    GoldCase("oos_carbon", "What is our carbon footprint per factory?",
             _oos_text, kind="oos"),
    GoldCase("oos_planogram_ar", "ما هو تصميم الرفوف للفروع؟ (planogram)",
             _oos_text, kind="oos"),
]
