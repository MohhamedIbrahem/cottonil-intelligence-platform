"""Global cross-filters (App Shell v3): governorate / channel / branch.

One set of selections, stored in session state by the filter bar and read
by the pages that support them, so a choice made on one dashboard carries
to the next (the cross-filtering behaviour of mature BI tools).

Design rules:
- Empty selection = "All" — the SQL fragment is empty and every number is
  exactly what the page showed before this module existed.
- Fragments are parametrized (`IN (?, ?, ...)`) and built ONLY by
  `build_where()` from the column map below; values are never interpolated.
- Each page declares the filters it supports; unsupported filters are
  neither rendered nor applied on that page.
"""

from __future__ import annotations

import streamlit as st

from app import data

KEYS = {
    "governorate": "gf_governorates",
    "channel": "gf_channels",
    "branch": "gf_branches",
}

# Filter name -> column on views.sales_enriched-shaped queries.
_COLUMNS = {
    "governorate": "branch_governorate_ar",
    "channel": "sales_channel",
    "branch": "branch_name_ar",
}

_LABELS = {
    "governorate": "Governorate",
    "channel": "Channel",
    "branch": "Branch",
}

_OPTION_QUERIES = {
    "governorate": "SELECT DISTINCT branch_governorate_ar FROM views.sales_enriched "
                   "WHERE branch_governorate_ar IS NOT NULL ORDER BY 1",
    "channel": "SELECT DISTINCT sales_channel FROM views.sales_enriched "
               "WHERE sales_channel IS NOT NULL ORDER BY 1",
    "branch": "SELECT DISTINCT branch_name_ar FROM views.sales_enriched "
              "WHERE branch_name_ar IS NOT NULL ORDER BY 1",
}

ALL_FILTERS = frozenset(KEYS)


def build_where(
    selections: dict[str, list],
    supported: set[str] | frozenset[str],
    *,
    alias: str = "",
) -> tuple[str, tuple]:
    """Pure SQL-fragment builder (unit-tested in tests/test_global_filters.py).

    Returns (" AND <alias>col IN (?, ...)", params) per active supported
    filter, or ("", ()) when every supported filter is on All.
    """
    prefix = f"{alias}." if alias else ""
    parts: list[str] = []
    params: list = []
    for name in ("governorate", "channel", "branch"):
        if name not in supported:
            continue
        values = [v for v in (selections.get(name) or []) if v is not None]
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        parts.append(f" AND {prefix}{_COLUMNS[name]} IN ({placeholders})")
        params.extend(values)
    return "".join(parts), tuple(params)


def selections() -> dict[str, list]:
    """Current selections from session state (empty list = All)."""
    return {name: list(st.session_state.get(key, [])) for name, key in KEYS.items()}


def sales_where(
    supported: set[str] | frozenset[str] = ALL_FILTERS,
    *,
    alias: str = "",
) -> tuple[str, tuple]:
    """Fragment + params for the current selections on a sales query."""
    return build_where(selections(), supported, alias=alias)


def _options(name: str) -> list[str]:
    frame = data.q(_OPTION_QUERIES[name])
    return [str(v) for v in frame.iloc[:, 0].tolist()]


def _reset() -> None:
    for key in KEYS.values():
        st.session_state[key] = []


def render_filter_bar(supported: set[str] | frozenset[str]) -> None:
    """Pill row of the supported global filters + reset, for a page top."""
    active = [name for name in ("governorate", "channel", "branch") if name in supported]
    if not active:
        return
    with st.container(border=True):
        cols = st.columns([*([2] * len(active)), 1])
        for col, name in zip(cols, active, strict=False):
            with col:
                st.multiselect(
                    _LABELS[name],
                    _options(name),
                    key=KEYS[name],
                    placeholder="All",
                )
        with cols[-1]:
            st.button("Reset filters", on_click=_reset, key="gf_reset")
