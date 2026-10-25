"""SQL safety gate (T091): the assistant may only read, and only from the app's
curated single source of truth.

Guarantees:
- exactly one statement, no statement terminator tricks
- read verbs only (SELECT / WITH ... SELECT); any write/DDL/PRAGMA keyword fails
- fully-qualified tables only, restricted to views.* plus whitelisted raw *dimensions*
  (raw facts are deliberately excluded so answers come from the curated views -
  Constitution III single source of truth)
- results row-capped: deadline_wrap enforces LIMIT 201 (page flags truncation)

The underlying DuckDB handle is opened read-only as a second line of defense
(Constitution V).
"""

from __future__ import annotations

import re

from assistant import env

MAX_ROWS_PLUS = env.MAX_ROWS + 1

ALLOWED_RAW_DIMS = frozenset({
    "branches", "warehouses", "products_catalog", "sku_variants", "customers",
    "suppliers", "import_partners", "factories", "employees",
})
ALLOWED_VIEW_NAMES = frozenset({
    "sales_enriched", "monthly_sales", "branch_daily", "branch_summary",
    "product_overview", "top_products", "stock_monthly", "stock_status",
    "stock_latest", "returns_enriched", "supplier_pos", "customer_rfm",
    "customer_profile", "campaigns_clean",
})


class GuardError(ValueError):
    """Raised when a candidate SQL violates the assistant SQL contract."""


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|export|import|"
    r"merge|grant|revoke|pragma|call|checkpoint|vacuum|install|load|set|reset|use)\b",
    re.IGNORECASE,
)


def _without_literals(sql: str) -> str:
    """Remove line comments, block comments, and quoted string/identifier content
    so keyword and separator scans cannot be fooled by text inside quotes."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'[^']*'", "''", sql)
    sql = re.sub(r'"[^"]*"', '""', sql)
    return sql


def validate(sql: str) -> str:
    """Validate candidate SQL and return the (semicolon-stripped) statement."""
    candidate = (sql or "").strip()
    if not candidate:
        raise GuardError("Empty SQL.")

    scanned = _without_literals(candidate)

    if ";" in scanned.strip().rstrip(";") and re.search(r";\s*\S", scanned):
        raise GuardError("Exactly one statement is allowed.")

    if _FORBIDDEN.search(scanned):
        raise GuardError(
            "Only read-only SELECT queries are allowed "
            "(no writes, DDL, PRAGMA, or meta commands)."
        )

    statement = scanned.strip().lstrip("(").rstrip(";")
    first_word = re.match(r"[A-Za-z]+", statement or "").group(0).lower() if statement else ""
    if first_word not in {"select", "with"}:
        raise GuardError("The query must start with SELECT or WITH ... SELECT.")

    tables = [
        f"{m.group(1).lower()}.{m.group(2).lower()}"
        for m in re.finditer(
            r"\b(?:from|join)\s+([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)",
            scanned,
            re.IGNORECASE,
        )
    ]
    if not tables:
        raise GuardError("Query every table with a schema, e.g. views.sales_enriched.")

    schema_map = {"views": ALLOWED_VIEW_NAMES, "raw": ALLOWED_RAW_DIMS}
    for full_name in tables:
        schema, _, name = full_name.partition(".")
        if schema not in schema_map:
            raise GuardError(f"Schema '{schema}.' is not allowed.")
        if name not in schema_map[schema]:
            raise GuardError(
                f"Table '{full_name}' is not in the allow-list. "
                "Use the curated views (see the provided catalog) "
                "or raw dimensions (branches, warehouses, products_catalog, sku_variants, "
                "customers, suppliers, import_partners, factories, employees)."
            )

    return candidate.rstrip(";").strip()


def deadline_wrap(sql: str) -> str:
    """Row-cap any validated statement for execution/wrapping order safety."""
    return f"SELECT * FROM ({sql})\nLIMIT {MAX_ROWS_PLUS}"


def referenced_tables(sql: str) -> list[str]:
    """Qualified table names referenced (for source footers and deep links)."""
    scanned = _without_literals(sql)
    return [
        f"{m.group(1).lower()}.{m.group(2).lower()}"
        for m in re.finditer(r"\b(?:from|join)\s+([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)", scanned, re.IGNORECASE)
    ]
