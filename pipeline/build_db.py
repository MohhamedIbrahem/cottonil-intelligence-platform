"""Load the 25 Cottonil CSVs into a typed DuckDB database and chart the curated views.

Usage:
    uv run build            # -> data/cottonil.duckdb
    uv run python -m pipeline.build_db [optional-output-path]
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

from pipeline import config
from pipeline.views_loader import apply_views

# Deterministic load order: static dimensions first, then the transactional spine.
TABLE_ORDER: list[tuple[str, str, str]] = [
    # (table_name, subfolder, filename)
    ("warehouses", "02_TABLES", "warehouses.csv"),
    ("factories", "02_TABLES", "factories.csv"),
    ("suppliers", "02_TABLES", "suppliers.csv"),
    ("import_partners", "02_TABLES", "import_partners.csv"),
    ("branches", "02_TABLES", "branches.csv"),
    ("customers", "02_TABLES", "customers.csv"),
    ("products_catalog", "02_TABLES", "products_catalog.csv"),
    ("sku_variants", "02_TABLES", "sku_variants.csv"),
    ("sales_orders", "02_TABLES", "sales_orders.csv"),
    ("sales_order_items", "02_TABLES", "sales_order_items.csv"),
    ("sales_payments", "02_TABLES", "sales_payments.csv"),
    ("sales_returns", "02_TABLES", "sales_returns.csv"),
    ("delivery_shipments", "02_TABLES", "delivery_shipments.csv"),
    ("inventory_transfers", "02_TABLES", "inventory_transfers.csv"),
    ("inventory_transfer_items", "02_TABLES", "inventory_transfer_items.csv"),
    ("monthly_stock", "02_TABLES", "monthly_stock.csv"),
    ("purchase_orders", "02_TABLES", "purchase_orders.csv"),
    ("purchase_order_items", "02_TABLES", "purchase_order_items.csv"),
    ("import_shipments", "02_TABLES", "import_shipments.csv"),
    ("marketing_campaigns", "02_TABLES", "marketing_campaigns.csv"),
    ("operating_expenses", "02_TABLES", "operating_expenses.csv"),
    ("payroll", "02_TABLES", "payroll.csv"),
    ("employees", "02_TABLES", "employees.csv"),
    ("data_dictionary", "02_TABLES", "data_dictionary.csv"),
    ("catalog_reference", "01_CATALOG", "PRODUCT_CATALOG_PUBLIC_REFERENCE.csv"),
]

_INT_COLS = {
    "items_count", "quantity", "quantity_units", "return_quantity", "closing_units",
    "capacity_units", "impressions", "clicks", "orders_attributed", "payment_terms_days",
}


def _col_kind(name: str) -> str:
    """Column-name-based typing rules (audit-verified, config.ENCODING aware)."""
    lower = name.lower()
    if name.endswith("_date"):
        return "DATE"
    if name in {"year_month", "pay_month"}:  # keep month keys as sortable 'YYYY-MM' strings
        return "VARCHAR"
    if name in _INT_COLS:
        return "BIGINT"
    if "egp" in lower or "usd" in lower:
        return "DOUBLE"
    if name == "stockout_risk_score" or name == "price_multiplier":
        return "DOUBLE"
    return "VARCHAR"


def _load_frame(table_name: str, source: str, filename: str) -> pd.DataFrame:
    folder = config.CATALOG_DIR if source == "01_CATALOG" else config.TABLES_DIR
    path = folder / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Source CSV missing for table '{table_name}': {path}\n"
            "Place the dataset at COTTONIL/COTTONIL_Data/ (see README)."
        )
    df = pd.read_csv(path, encoding=config.ENCODING)
    for name in df.columns:
        if _col_kind(name) == "DATE":
            df[name] = pd.to_datetime(df[name], format="mixed", errors="raise")
    return df


def build_database(db_path: str | None = None, apply_curated_views: bool = True) -> duckdb.DuckDBPyConnection:
    """Build (destructively rebuild) the DuckDB database from source CSVs."""
    path_str = str(db_path or config.DB_PATH)
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(path_str)
    con.execute("DROP SCHEMA IF EXISTS raw CASCADE")
    con.execute(f"CREATE SCHEMA {config.RAW_SCHEMA}")

    con.execute(f"CREATE SCHEMA IF NOT EXISTS {config.VIEW_SCHEMA}")
    for table_name, source, filename in TABLE_ORDER:
        df = _load_frame(table_name, source, filename)
        con.register("_incoming", df)
        cast_cols = []
        for name in df.columns:
            kind = _col_kind(name)
            if kind == "VARCHAR":
                cast_cols.append(f'"{name}"')
            else:
                cast_cols.append(f'CAST("{name}" AS {kind}) AS "{name}"')
        cols_sql = ", ".join(cast_cols)
        con.execute(
            f"CREATE OR REPLACE TABLE {config.RAW_SCHEMA}.{table_name} AS "
            f"SELECT {cols_sql} FROM _incoming"
        )
        con.unregister("_incoming")
        print(f"  loaded raw.{table_name:<24} rows={len(df):>9,} from {filename}")

    if apply_curated_views:
        apply_views(con)

    return con


def main(argv: list[str] | None = None) -> int:  # console entrypoint: uv run build
    argv = list(sys.argv[1:] if argv is None else argv)
    db_path = argv[0] if argv else str(config.DB_PATH)
    print(f"Building DuckDB database -> {db_path}")
    con = build_database(db_path)
    counts = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'views' ORDER BY 1"
    ).fetchall()
    print(f"  curated views created: {len(counts)}")
    con.close()
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
