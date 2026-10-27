"""Unit tests for the App Shell v3 global cross-filters SQL builder.

The builder is pure: given the same selections it must produce an empty
fragment on "All" (so existing pages keep byte-identical results) and a
parametrized IN(...) fragment per active, supported filter otherwise.
"""

from app.global_filters import build_where


def test_all_empty_is_noop():
    sql, params = build_where({}, {"governorate", "channel", "branch"})
    assert sql == "" and params == ()


def test_single_filter():
    sql, params = build_where({"governorate": ["Cairo"]}, {"governorate"})
    assert sql == " AND branch_governorate_ar IN (?)"
    assert params == ("Cairo",)


def test_multiple_values_and_filters_keep_order():
    sql, params = build_where(
        {"channel": ["Retail", "Online"], "governorate": ["Giza"]},
        {"governorate", "channel", "branch"},
    )
    assert sql == (
        " AND branch_governorate_ar IN (?)"
        " AND sales_channel IN (?, ?)"
    )
    assert params == ("Giza", "Retail", "Online")


def test_unsupported_filter_is_ignored():
    sql, params = build_where({"governorate": ["Cairo"]}, {"channel"})
    assert sql == "" and params == ()


def test_alias_prefix_for_joined_queries():
    sql, params = build_where({"branch": ["A", "B"]}, {"branch"}, alias="le")
    assert sql == " AND le.branch_name_ar IN (?, ?)"
    assert params == ("A", "B")
