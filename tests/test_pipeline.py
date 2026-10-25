"""Pipeline + DQ + curated-view tests (tasks T022 / spec US1 / SC-001).

These tests build the full database ONCE per session into a temp directory
(~1-3 min on the target machine) and assert the audit-verified invariants:

- exact row counts for every source table
- every DQ gate passes (FK orphans = 0, reconciliations exact)
- every curated view materializes with rows
- examples of gross/net/tax arithmetic at the aggregate level
"""

from __future__ import annotations

import duckdb
import pytest

from pipeline import build_db, checks, config, views_loader

# Audit-verified row counts (2026-10-24 profile; update if the dataset changes)
EXPECTED_ROWS: dict[str, int] = {
    "warehouses": 12,
    "factories": 6,
    "suppliers": 48,
    "import_partners": 16,
    "branches": 80,
    "customers": 85_000,
    "products_catalog": 139,
    "sku_variants": 695,
    "sales_orders": 540_000,
    "sales_order_items": 1_138_536,
    "sales_payments": 540_000,
    "sales_returns": 28_500,
    "delivery_shipments": 97_660,
    "inventory_transfers": 36_500,
    "inventory_transfer_items": 109_614,
    "monthly_stock": 142_784,
    "purchase_orders": 41_500,
    "purchase_order_items": 103_334,
    "import_shipments": 4_200,
    "marketing_campaigns": 2_200,
    "operating_expenses": 47_000,
    "payroll": 13_210,
    "employees": 640,
}
GUEST_ORDERS = 102_961  # sales_orders without customer_id (audit A4)


@pytest.fixture(scope="session")
def db_con(tmp_path_factory) -> duckdb.DuckDBPyConnection:
    db_path = tmp_path_factory.mktemp("db") / "cottonil_test.duckdb"
    con = build_db.build_database(str(db_path), apply_curated_views=True)
    yield con
    con.close()


def test_all_tables_loaded_with_expected_row_counts(db_con):
    installed = {name for (name,) in db_con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
    ).fetchall()}
    for table_name, filename, source in build_db.TABLE_ORDER:
        assert table_name in installed, f"raw.{table_name} missing from database"
        (rows,) = db_con.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()
        expected = EXPECTED_ROWS.get(table_name)
        if expected is not None:
            assert rows == expected, f"raw.{table_name}: {rows:,} != {expected:,}"
        else:
            # data_dictionary / catalog_reference - audited as non-empty only
            assert rows > 0, f"raw.{table_name} unexpectedly empty"


def test_every_curated_view_in_catalog_materializes(db_con):
    installed = set(views_loader.installed_views(db_con))
    assert installed == set(views_loader.VIEWS_META), (
        f"catalog mismatch: files-vs-views {installed ^ set(views_loader.VIEWS_META)}"
    )
    for view_name in views_loader.VIEWS_META:
        (rows,) = db_con.execute(
            f"SELECT COUNT(*) FROM {config.VIEW_SCHEMA}.{view_name}"
        ).fetchone()
        assert rows > 0, f"views.{view_name} materialized with 0 rows"


def test_sales_totals_reconcile_across_raw_and_views(db_con):
    (header_total,) = db_con.execute(
        "SELECT SUM(net_before_tax_EGP) FROM raw.sales_orders"
    ).fetchone()
    (items_total,) = db_con.execute(
        "SELECT SUM(net_line_EGP) FROM raw.sales_order_items"
    ).fetchone()
    (view_total,) = db_con.execute("SELECT SUM(net_sales) FROM views.sales_enriched").fetchone()
    # Row-level reconciliation is exact (DQ gate); aggregate SUMs use float
    # accumulation whose order can drift by sub-piaster amounts -> 1-cent tolerance.
    assert header_total == pytest.approx(items_total, abs=0.01)
    assert header_total == pytest.approx(view_total, abs=0.01)


def test_guest_orders_match_audit(db_con):
    (guests,) = db_con.execute(
        "SELECT COUNT(*) FROM raw.sales_orders WHERE customer_id IS NULL"
    ).fetchone()
    assert guests == GUEST_ORDERS


def test_monthly_sales_month_count_matches_orders(db_con):
    (distinct_months_orders,) = db_con.execute(
        "SELECT COUNT(DISTINCT strftime(CAST(order_date AS DATE), '%Y-%m')) "
        "FROM raw.sales_orders"
    ).fetchone()
    (view_rows,) = db_con.execute("SELECT COUNT(*) FROM views.monthly_sales").fetchone()
    assert view_rows == distinct_months_orders


def test_rfm_tiers_are_from_the_documented_set(db_con):
    tiers = {t for (t,) in db_con.execute(
        "SELECT DISTINCT rfm_tier FROM views.customer_rfm"
    ).fetchall()}
    assert tiers <= {
        "Champions", "Loyal", "Potential Loyalist", "Need Attention", "At Risk", "Churned",
    }
    profile_tiers = {t for (t,) in db_con.execute(
        "SELECT DISTINCT rfm_tier FROM views.customer_profile"
    ).fetchall()}
    assert "No purchase" in profile_tiers
    assert profile_tiers <= tiers | {"No purchase"}


def test_stock_latest_only_contains_the_last_month(db_con):
    (max_month,) = db_con.execute("SELECT MAX(year_month) FROM views.stock_status").fetchone()
    bad = db_con.execute(
        f"SELECT COUNT(*) FROM {config.VIEW_SCHEMA}.stock_latest WHERE year_month <> ?",
        [max_month],
    ).fetchone()
    assert bad[0] == 0


def test_refund_cap_is_enforced_in_view(db_con):
    rows = db_con.execute("""
        SELECT COUNT(*) FROM views.returns_enriched
        WHERE refund_capped > refunded_line_net + 0.005
    """).fetchone()
    assert rows[0] == 0


def test_campaign_attribution_stays_within_window_orders(db_con):
    """Rebuilt attribution is capped by real orders inside each campaign window."""
    rows = db_con.execute("""
        WITH daily AS (
            SELECT CAST(order_date AS DATE) AS d, COUNT(DISTINCT sales_order_id) AS orders
            FROM raw.sales_orders GROUP BY 1
        ),
        win AS (
            SELECT m.campaign_id, COALESCE(SUM(dd.orders), 0) AS window_orders
            FROM raw.marketing_campaigns m
            LEFT JOIN daily dd
              ON dd.d >= CAST(m.start_date AS DATE)
             AND dd.d <= CAST(m.end_date AS DATE)
            GROUP BY m.campaign_id
        )
        SELECT COUNT(*)
        FROM views.campaigns_clean v
        JOIN win w USING (campaign_id)
        WHERE v.attributed_orders_real > w.window_orders
    """).fetchone()
    assert rows[0] == 0


def test_dq_gates_all_pass(db_con):
    failures, warnings = checks.run_checks(db_con)
    assert failures == [], f"DQ failures: {failures}"
    assert warnings, "documented anomaly warnings should always be produced"


def test_missing_source_csv_fails_loudly(monkeypatch, tmp_path):
    from pipeline.build_db import _load_frame

    monkeypatch.setattr(build_db.config, "TABLES_DIR", tmp_path / "does_not_exist")
    with pytest.raises(FileNotFoundError, match="sales_orders"):
        _load_frame("sales_orders", "02_TABLES", "sales_orders.csv")
