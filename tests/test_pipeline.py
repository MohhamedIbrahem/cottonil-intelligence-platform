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


def test_feature_003_view_rowcounts(db_con):
    expected = {
        "demand_monthly": 1_552,
        "product_monthly": 13_483,
        "sku_monthly": 66_627,
        "channel_monthly": 291,
        "replenishment_signals": 1_472,
        "customer_clv": 85_000,
    }
    for view_name, rows in expected.items():
        (actual,) = db_con.execute(
            f"SELECT COUNT(*) FROM {config.VIEW_SCHEMA}.{view_name}"
        ).fetchone()
        assert actual == rows, f"views.{view_name}: {actual:,} != {rows:,}"


def test_demand_monthly_flags_only_october_2026_as_partial(db_con):
    complete, partial = db_con.execute(
        "SELECT COUNT(DISTINCT ym) FILTER (WHERE is_complete_month), "
        "       COUNT(DISTINCT ym) FILTER (WHERE NOT is_complete_month) "
        "FROM views.demand_monthly"
    ).fetchone()
    assert (complete, partial) == (96, 1)
    (partial_month,) = db_con.execute(
        "SELECT DISTINCT ym FROM views.demand_monthly WHERE NOT is_complete_month"
    ).fetchone()
    assert partial_month == "2026-10"
    (last_complete,) = db_con.execute(
        "SELECT MAX(ym) FROM views.demand_monthly WHERE is_complete_month"
    ).fetchone()
    assert last_complete == "2026-09"

    demand_net, demand_units, monthly_net, monthly_units = db_con.execute(
        "SELECT (SELECT SUM(net_sales) FROM views.demand_monthly), "
        "       (SELECT SUM(units) FROM views.demand_monthly), "
        "       (SELECT SUM(net_sales) FROM views.monthly_sales), "
        "       (SELECT SUM(units) FROM views.monthly_sales)"
    ).fetchone()
    assert demand_net == pytest.approx(monthly_net, abs=0.01)
    assert demand_units == monthly_units


def test_product_and_sku_monthly_reconcile_to_the_sales_spine(db_con):
    pm_net, pm_profit, pm_units, sku_net, sku_profit, sku_units, line_net, line_profit = (
        db_con.execute(
            "SELECT (SELECT SUM(net_sales) FROM views.product_monthly), "
            "       (SELECT SUM(gross_profit) FROM views.product_monthly), "
            "       (SELECT SUM(units) FROM views.product_monthly), "
            "       (SELECT SUM(net_sales) FROM views.sku_monthly), "
            "       (SELECT SUM(gross_profit) FROM views.sku_monthly), "
            "       (SELECT SUM(units) FROM views.sku_monthly), "
            "       (SELECT SUM(net_sales) FROM views.sales_enriched), "
            "       (SELECT SUM(gross_profit) FROM views.sales_enriched)"
        ).fetchone()
    )
    for actual, expected in (
        (pm_net, line_net),
        (pm_profit, line_profit),
        (pm_units, sku_units),
        (sku_net, line_net),
        (sku_profit, line_profit),
    ):
        assert actual == pytest.approx(expected, abs=0.01)
    (null_size,) = db_con.execute(
        "SELECT COUNT(*) FROM views.sku_monthly WHERE size IS NULL"
    ).fetchone()
    assert null_size == 0


def test_channel_monthly_reconciles_to_monthly_sales(db_con):
    channel_net, channel_orders, monthly_net, monthly_orders = db_con.execute(
        "SELECT (SELECT SUM(net_sales) FROM views.channel_monthly), "
        "       (SELECT SUM(orders) FROM views.channel_monthly), "
        "       (SELECT SUM(net_sales) FROM views.monthly_sales), "
        "       (SELECT SUM(orders) FROM views.monthly_sales)"
    ).fetchone()
    assert channel_net == pytest.approx(monthly_net, abs=0.01)
    assert channel_orders == monthly_orders == 540_000
    channels = {name for (name,) in db_con.execute(
        "SELECT DISTINCT sales_channel FROM views.channel_monthly"
    ).fetchall()}
    assert channels == {"Retail POS", "E-commerce", "Wholesale / reseller"}


def test_replenishment_signal_rule_is_consistent(db_con):
    expected_counts = {
        "Overstock (>180d)": 931,
        "Adequate (45-180d)": 405,
        "Below target (30-45d)": 52,
        "Low (14-30d)": 49,
        "Critical (<14d)": 23,
        "No demand signal": 12,
    }
    counts = dict(db_con.execute(
        "SELECT signal, COUNT(*) FROM views.replenishment_signals GROUP BY 1"
    ).fetchall())
    assert counts == expected_counts

    bad_signal = db_con.execute("""
        SELECT COUNT(*) FROM views.replenishment_signals
        WHERE (cover_days IS NULL AND signal <> 'No demand signal')
           OR (cover_days < 14 AND signal <> 'Critical (<14d)')
           OR (cover_days >= 14 AND cover_days < 30 AND signal <> 'Low (14-30d)')
           OR (cover_days >= 30 AND cover_days < 45 AND signal <> 'Below target (30-45d)')
           OR (cover_days >= 45 AND cover_days <= 180 AND signal <> 'Adequate (45-180d)')
           OR (cover_days > 180 AND signal <> 'Overstock (>180d)')
    """).fetchone()
    assert bad_signal[0] == 0

    bad_reorder = db_con.execute("""
        SELECT COUNT(*) FROM views.replenishment_signals
        WHERE (cover_days IS NULL AND reorder_units <> 0)
           OR (cover_days < 45 AND reorder_units <= 0)
           OR (cover_days >= 45 AND reorder_units <> 0)
           OR target_cover_days <> 45
    """).fetchone()
    assert bad_reorder[0] == 0

    by_type = dict(db_con.execute(
        "SELECT stock_location_type, COUNT(*) FROM views.replenishment_signals "
        "GROUP BY 1"
    ).fetchall())
    assert by_type == {"Branch": 1_280, "Warehouse": 192}


def test_customer_clv_status_domain_and_reconciliation(db_con):
    status = dict(db_con.execute(
        "SELECT churn_status, COUNT(*) FROM views.customer_clv GROUP BY 1"
    ).fetchall())
    assert status == {
        "Active": 47_680,
        "Churned": 23_138,
        "Insufficient history": 3_842,
        "Never purchased": 10_340,
    }

    clv_net, spine_net, eligible = db_con.execute(
        "SELECT (SELECT SUM(net_sales_lifetime) FROM views.customer_clv), "
        "       (SELECT SUM(net_sales) FROM views.sales_enriched "
        "        WHERE customer_id IS NOT NULL), "
        "       (SELECT COUNT(*) FROM views.customer_clv WHERE is_churn_eligible)"
    ).fetchone()
    assert clv_net == pytest.approx(spine_net, abs=0.01)
    assert eligible == 70_818

    bad_flag = db_con.execute("""
        SELECT COUNT(*) FROM views.customer_clv
        WHERE is_churn_eligible <> (has_purchased AND tenure_days >= 365)
    """).fetchone()
    assert bad_flag[0] == 0


def test_feature_004_view_rowcounts(db_con):
    expected = {"workforce_monthly": 5_644, "expansion_gap": 21}
    for view_name, rows in expected.items():
        (actual,) = db_con.execute(
            f"SELECT COUNT(*) FROM {config.VIEW_SCHEMA}.{view_name}"
        ).fetchone()
        assert actual == rows, f"views.{view_name}: {actual:,} != {rows:,}"


def test_workforce_monthly_payroll_identity_and_coverage(db_con):
    rows, bad_identity, bad_headcount = db_con.execute("""
        SELECT COUNT(*),
               COUNT(*) FILTER (
                   WHERE ABS(net_paid - (gross_payroll - deductions)) > 0.01
                      OR ABS(gross_payroll - (base_salary + overtime + bonus)) > 0.01
               ),
               COUNT(*) FILTER (
                   WHERE paid_employees < 1 OR paid_employees > employees_ever_attached
               )
        FROM views.workforce_monthly
    """).fetchone()
    assert rows == 5_644
    assert bad_identity == 0
    assert bad_headcount == 0

    view_paid, source_paid = db_con.execute("""
        SELECT (SELECT SUM(net_paid) FROM views.workforce_monthly),
               (SELECT SUM(net_paid_EGP) FROM raw.payroll)
    """).fetchone()
    assert view_paid == pytest.approx(source_paid, abs=0.01)

    branch_months, branches, full_year, labor_ratio = db_con.execute("""
        WITH per_branch AS (
            SELECT branch_id, COUNT(*) AS months
            FROM views.workforce_monthly
            WHERE LEFT(ym, 4) = '2023'
            GROUP BY 1
        )
        SELECT (SELECT COUNT(*) FROM views.workforce_monthly WHERE LEFT(ym, 4) = '2023'),
               COUNT(*),
               COUNT(*) FILTER (WHERE months = 12),
               (SELECT SUM(net_paid) / NULLIF(SUM(net_sales), 0)
                FROM views.workforce_monthly WHERE LEFT(ym, 4) = '2023')
        FROM per_branch
    """).fetchone()
    assert branch_months == 922          # 2023 is the best-covered payroll year
    assert branches == 80
    assert full_year == 72
    assert labor_ratio == pytest.approx(0.1359, abs=0.0001)


def test_expansion_gap_reconciles_to_the_sales_spine(db_con):
    govs, branches, customers, buyers, min_branches = db_con.execute("""
        SELECT COUNT(*), SUM(branches), SUM(customers), SUM(resident_buyers),
               MIN(branches)
        FROM views.expansion_gap
    """).fetchone()
    assert (govs, branches, customers, buyers, min_branches) == (21, 80, 85_000, 74_660, 1)

    resident_net, branch_net, pos_net, spine_net, spine_pos = db_con.execute("""
        SELECT (SELECT SUM(resident_net_sales) FROM views.expansion_gap),
               (SELECT SUM(branch_net_sales) FROM views.expansion_gap),
               (SELECT SUM(pos_net_sales) FROM views.expansion_gap),
               (SELECT SUM(net_sales) FROM views.sales_enriched
                WHERE customer_id IS NOT NULL),
               (SELECT SUM(net_sales) FROM views.sales_enriched
                WHERE sales_channel = 'Retail POS')
    """).fetchone()
    assert resident_net == pytest.approx(spine_net, abs=0.01)
    assert branch_net == pytest.approx(841_274_176.32, abs=0.01)
    assert pos_net == pytest.approx(spine_pos, abs=0.01)

    network_share, buyer_share, gap_sum = db_con.execute("""
        SELECT SUM(network_share), SUM(buyer_share),
               SUM(network_minus_buyer_share_pp)
        FROM views.expansion_gap
    """).fetchone()
    assert network_share == pytest.approx(1.0)
    assert buyer_share == pytest.approx(1.0)
    assert gap_sum == pytest.approx(0.0, abs=1e-9)

    bad = db_con.execute("""
        SELECT COUNT(*) FROM views.expansion_gap
        WHERE resident_buyers > customers OR branches <> retail_branches + reseller_pos_branches
    """).fetchone()
    assert bad[0] == 0


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
