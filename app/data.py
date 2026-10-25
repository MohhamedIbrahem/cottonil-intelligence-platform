"""Streamlit-facing data access: read-only DuckDB over the curated views.

Pages call `q(sql, params)` and get back a pandas DataFrame. The connection is
opened once per process (read-only, Constitution V) and query results are
cached keyed on sql+params; the Phase-1 dataset is immutable, so no invalidation
beyond the 10-minute TTL is needed.
"""

from __future__ import annotations

import duckdb
import streamlit as st
from pandas import DataFrame

from pipeline import config


@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    if not config.DB_PATH.exists():
        raise FileNotFoundError(
            "DuckDB database not found. Run the pipeline first:\n\n"
            "```\nuv run build\n```"
        )
    return duckdb.connect(str(config.DB_PATH), read_only=True)


@st.cache_data(ttl=600, show_spinner="running query…")
def q(sql: str, params: tuple = ()) -> DataFrame:
    """Run a read-only query against the built database (cached by sql+params)."""
    con = _connection()
    if params:
        return con.execute(sql, list(params)).df()
    return con.execute(sql).df()


def scalar(sql: str, params: tuple = ()):
    """First value of the first row, or None."""
    frame = q(sql, params)
    return frame.iloc[0, 0] if len(frame) else None
