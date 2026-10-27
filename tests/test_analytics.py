"""Analytics model gate: synthetic mechanics + real-data regression checks.

The synthetic tests fix the *mechanics* (recover a known elasticity, forecast a
clean seasonal series, discriminate a known churn signal). The real-data tests
pin the results the Feature 003 pages disclose, so a data or dependency change
that breaks the documented numbers fails loudly instead of drifting silently.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app import analytics
from pipeline import config


# --------------------------------------------------------------------------
# Forecast
# --------------------------------------------------------------------------
def _synthetic_demand(months: int = 84) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    periods = pd.period_range("2019-10", periods=months, freq="M")
    season = np.array(
        [0.82, 0.86, 0.96, 1.02, 1.06, 1.12, 1.16, 1.10, 1.04, 0.98, 0.90, 0.88]
    )
    trend = 9000 + 60 * np.arange(months)
    values = trend * season[np.arange(months) % 12] * (1 + rng.normal(0, 0.01, months))
    return pd.DataFrame(
        {
            "ym": periods.strftime("%Y-%m"),
            "value": values,
            "is_complete_month": True,
        }
    )


def test_forecast_recovers_a_clean_seasonal_series():
    frame = _synthetic_demand()
    result = analytics.forecast_demand(
        frame, value_col="value", horizon=6, backtest_windows=2
    )
    metrics = result["metrics"]
    history = result["history"]
    forecast = result["forecast"]
    backtest = result["backtest"]

    assert metrics["train_months"] == len(frame)
    assert metrics["backtest_windows"] == 2
    assert metrics["wape_mean"] < 0.10
    assert np.isfinite(metrics["band_pct"])

    assert len(history) == len(frame)
    assert len(forecast) == 6
    assert np.isfinite(forecast["forecast"]).all()
    assert (forecast["forecast"] > 0).all()
    assert (forecast["lo"] <= forecast["forecast"]).all()
    assert (forecast["forecast"] <= forecast["hi"]).all()
    assert len(backtest) == 2

    seasonal = result["seasonal_index"]
    assert len(seasonal) == 12
    assert seasonal["index"].mean() == pytest.approx(1.0, abs=1e-9)


def test_forecast_excludes_partial_months():
    frame = _synthetic_demand()
    partial = pd.DataFrame(
        [{"ym": "2026-10", "value": 1e9, "is_complete_month": False}]
    )
    result = analytics.forecast_demand(
        pd.concat([frame, partial], ignore_index=True),
        value_col="value",
        backtest_windows=0,
    )
    assert len(result["history"]) == len(frame)
    assert result["history"]["ym"].max() == "2026-09"


def test_forecast_requires_enough_history():
    frame = _synthetic_demand(months=36)
    with pytest.raises(ValueError, match="at least 48"):
        analytics.forecast_demand(frame, value_col="value")


# --------------------------------------------------------------------------
# Price elasticity
# --------------------------------------------------------------------------
def _synthetic_sku_panel(*, true_beta: float = -1.5) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    months = [f"2024-{m:02d}" for m in range(1, 13)] + [
        f"2025-{m:02d}" for m in range(1, 13)
    ]
    rows: list[dict] = []
    for index in range(40):
        sku = f"S{index:02d}"
        base_price = 50.0 + index
        intercept = 9.5 + 0.01 * index
        category = "A" if index % 2 == 0 else "B"
        for month_index, ym in enumerate(months):
            price = base_price * (1 + rng.normal(0, 0.08))
            month_effect = 0.15 * np.sin(2 * np.pi * month_index / 12)
            log_units = (
                intercept + month_effect + true_beta * np.log(price)
                + rng.normal(0, 0.04)
            )
            rows.append(
                {
                    "sku_id": sku,
                    "ym": ym,
                    "units": max(1.0, float(np.exp(log_units))),
                    "avg_unit_price": float(price),
                    "discount_rate": float(rng.uniform(0.0, 0.20)),
                    "category_en": category,
                }
            )
    return pd.DataFrame(rows)


def test_price_elasticity_recovers_a_known_negative_response():
    frame = _synthetic_sku_panel(true_beta=-1.5)
    result = analytics.price_elasticity(frame)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["n_obs"] == len(frame)
    assert row["n_skus"] == 40
    assert row["n_months"] == 24
    assert -1.65 < row["beta_price"] < -1.35
    assert row["p_price"] < 0.001
    assert row["r2_within"] > 0.80


def test_price_elasticity_groups_return_all_plus_each_group():
    frame = _synthetic_sku_panel()
    result = analytics.price_elasticity(frame, group_col="category_en")
    assert set(result["group"]) == {"All", "A", "B"}
    grouped = result[result["group"] != "All"]
    assert (grouped["n_obs"] == len(frame) // 2).all()
    assert (grouped["beta_price"] < -1.0).all()


# --------------------------------------------------------------------------
# Churn holdout
# --------------------------------------------------------------------------
def _synthetic_churn(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    recency = rng.integers(0, 700, rows)
    orders = rng.integers(1, 7, rows)
    tenure = rng.integers(365, 2000, rows)
    monetary = orders * rng.uniform(200.0, 1000.0, rows)
    logit = 2.0 - recency / 120.0 + 0.25 * orders
    probability = 1.0 / (1.0 + np.exp(-logit))
    return pd.DataFrame(
        {
            "recency": recency,
            "orders": orders,
            "monetary": monetary,
            "tenure": tenure,
            "aov": monetary / orders,
            "customer_segment": np.where(
                rng.random(rows) < 0.05, "B2B reseller", "Retail"
            ),
            "bought_next": rng.binomial(1, probability),
        }
    )


def test_churn_holdout_discriminates_a_known_signal():
    train = _synthetic_churn(2_000, seed=3)
    test = _synthetic_churn(2_000, seed=5)
    result = analytics.churn_holdout(train, test)
    assert result["n_train"] == len(train)
    assert result["n_test"] == len(test)
    assert result["auc"] > 0.70
    assert result["accuracy"] > 0.60
    assert 0.0 < result["base_churn"] < 1.0
    assert len(result["deciles"]) == 10
    assert set(result["coefficients"]["term"]) == {
        "const", "recency", "log_orders", "log_monetary", "log_tenure", "log_aov", "b2b",
    }


def test_churn_holdout_excludes_short_tenure_customers():
    train = _synthetic_churn(1_000, seed=7)
    test = _synthetic_churn(1_000, seed=9)
    short = test.head(100).copy()
    short["tenure"] = 100
    result = analytics.churn_holdout(train, pd.concat([test, short], ignore_index=True))
    assert result["n_test"] == len(test)


def test_discrimination_note_is_honest_about_a_coin_flip():
    assert "No usable discrimination" in analytics.discrimination_note(0.4995)
    assert "Do not use this model" in analytics.discrimination_note(0.4995)
    assert "Weak discrimination" in analytics.discrimination_note(0.60)
    assert "Useful discrimination" in analytics.discrimination_note(0.80)


# --------------------------------------------------------------------------
# Real-data checks (skipped when the database has not been built)
# --------------------------------------------------------------------------
requires_db = pytest.mark.skipif(
    not config.DB_PATH.exists(), reason="data/cottonil.duckdb not built"
)


def _read(sql: str) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


@requires_db
def test_real_units_forecast_matches_the_documented_accuracy():
    frame = _read(
        "SELECT ym, units AS value, is_complete_month "
        "FROM views.demand_monthly ORDER BY ym"
    )
    result = analytics.forecast_demand(
        frame, value_col="value", backtest_windows=1
    )
    assert result["metrics"]["train_months"] == 96
    assert result["metrics"]["wape_latest"] == pytest.approx(0.0303, abs=0.01)
    assert result["forecast"]["forecast"].notna().all()


@requires_db
def test_real_price_elasticity_reproduces_the_failed_signal():
    frame = _read(
        "SELECT sku_id, ym, units, avg_unit_price, discount_rate "
        "FROM views.sku_monthly"
    )
    result = analytics.price_elasticity(frame).iloc[0]
    assert result["n_obs"] == 66_627
    assert result["n_skus"] == 695
    assert result["n_months"] == 97
    assert result["beta_price"] == pytest.approx(0.2292, abs=0.02)
    assert result["r2_within"] < 0.01
    assert result["p_price"] > 0.01


@requires_db
def test_real_customer_clv_is_consistent_with_the_audit():
    status = _read(
        "SELECT churn_status, COUNT(*) AS customers "
        "FROM views.customer_clv GROUP BY 1"
    ).set_index("churn_status")["customers"]
    assert int(status.sum()) == 85_000
    assert int(status["Active"]) == 47_680
    assert int(status["Churned"]) == 23_138
    assert int(status["Insufficient history"]) == 3_842
    assert int(status["Never purchased"]) == 10_340
    eligible = int(status["Active"] + status["Churned"])
    assert eligible == 70_818
    assert status["Churned"] / eligible == pytest.approx(0.32672, abs=0.001)
