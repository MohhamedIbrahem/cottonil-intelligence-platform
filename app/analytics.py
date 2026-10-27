"""Reusable analytics models for the Feature 003 dashboards.

Three deliberately small, auditable models live here:

- ``forecast_demand``: Holt-Winters (additive damped trend + multiplicative
  seasonality) with a rolling-origin backtest and an empirical planning band.
- ``price_elasticity``: two-way within (SKU and month fixed effects) regression
  of log units on log price and discount rate, with SKU-clustered standard errors.
- ``churn_holdout``: temporal-holdout logistic regression used to *test* whether
  churn is predictable, not to pretend that it is.

The functions are pure pandas/numpy/statsmodels: pages pass real curated-view
rows in and get result frames/dicts back, so the models are unit-testable and
the dashboards never query raw facts.
"""

from __future__ import annotations

import calendar
import math
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import ExponentialSmoothing

MIN_FORECAST_MONTHS = 48
FORECAST_HORIZON = 6

FORECAST_MODEL = (
    "Holt-Winters: additive damped trend + multiplicative seasonality"
)


# --------------------------------------------------------------------------- #
# Demand forecast
# --------------------------------------------------------------------------- #
def _fit_holt_winters(series: pd.Series):
    """Fit the documented model; return (result, warning messages)."""
    seasonal = "mul" if bool((series > 0).all()) else "add"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        result = ExponentialSmoothing(
            series,
            trend="add",
            damped_trend=True,
            seasonal=seasonal,
            seasonal_periods=12,
            initialization_method="estimated",
        ).fit(optimized=True, use_brute=True)
    return result, [str(item.message) for item in caught]


def _month_end(values: pd.Series) -> pd.DatetimeIndex:
    return pd.PeriodIndex(values.astype(str), freq="M").to_timestamp("M")


def forecast_demand(
    frame: pd.DataFrame,
    *,
    value_col: str = "units",
    horizon: int = FORECAST_HORIZON,
    backtest_windows: int = 3,
) -> dict:
    """Forecast a monthly demand series and backtest it on rolling origins.

    ``frame`` needs ``ym`` (YYYY-MM) and ``value_col``. If ``is_complete_month``
    is present, only complete months are used. The last ``backtest_windows``
    12-month holdouts are scored before the final model is fitted on all data.
    """
    if not {"ym", value_col}.issubset(frame.columns):
        raise ValueError(f"forecast_demand needs columns 'ym' and '{value_col}'.")

    data = frame.copy()
    if "is_complete_month" in data.columns:
        data = data[data["is_complete_month"].astype(bool)]
    data["ym"] = data["ym"].astype(str)
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=["ym", value_col])
    data = data[data[value_col] >= 0]

    series = data.groupby("ym", as_index=True)[value_col].sum().sort_index()
    if len(series) < MIN_FORECAST_MONTHS:
        raise ValueError(
            f"Need at least {MIN_FORECAST_MONTHS} complete months; got {len(series)}."
        )
    series.index = _month_end(series.index)

    backtest_rows: list[dict] = []
    abs_pct_errors: list[float] = []
    for offset in range(backtest_windows):
        test_end = series.index[-1] - pd.DateOffset(months=12 * offset)
        test_start = test_end - pd.DateOffset(months=11)
        train = series[series.index < test_start]
        actual = series[(series.index >= test_start) & (series.index <= test_end)]
        if len(train) < MIN_FORECAST_MONTHS or len(actual) != 12:
            continue
        try:
            model, _ = _fit_holt_winters(train)
            predicted = np.asarray(model.forecast(12), dtype=float)
        except (ValueError, TypeError, np.linalg.LinAlgError):
            # A window that cannot be fitted is skipped, never fabricated.
            predicted = None
        if predicted is None:
            continue
        actual_values = actual.to_numpy(dtype=float)
        errors = predicted - actual_values
        denom = float(np.sum(np.abs(actual_values)))
        wape = float(np.sum(np.abs(errors)) / denom) if denom else float("nan")
        backtest_rows.append(
            {
                "test_start": test_start.strftime("%Y-%m"),
                "test_end": test_end.strftime("%Y-%m"),
                "train_months": len(train),
                "wape": wape,
                "mae": float(np.mean(np.abs(errors))),
                "bias": float(np.sum(errors) / denom) if denom else float("nan"),
            }
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = np.abs(errors) / np.abs(actual_values)
        abs_pct_errors.extend(pct[np.isfinite(pct)].tolist())

    model, fit_warnings = _fit_holt_winters(series)
    forecast_values = np.asarray(model.forecast(horizon), dtype=float)
    future_index = pd.period_range(
        pd.Period(series.index[-1], freq="M") + 1, periods=horizon, freq="M"
    ).to_timestamp("M")

    band_pct = float(np.percentile(abs_pct_errors, 80)) if abs_pct_errors else float("nan")
    lower = np.maximum(forecast_values * (1 - band_pct), 0) if np.isfinite(band_pct) else forecast_values
    upper = forecast_values * (1 + band_pct) if np.isfinite(band_pct) else forecast_values

    forecast = pd.DataFrame(
        {
            "ym": future_index.strftime("%Y-%m"),
            "forecast": forecast_values,
            "lo": lower,
            "hi": upper,
        }
    )

    fitted = pd.Series(np.asarray(model.fittedvalues, dtype=float), index=series.index)
    history = pd.DataFrame(
        {
            "ym": series.index.strftime("%Y-%m"),
            "actual": series.to_numpy(dtype=float),
            "fitted": fitted.to_numpy(dtype=float),
        }
    )

    # Multiplicative seasonal shape from a centred 12-month moving average.
    ratio = series / series.rolling(12, center=True).mean()
    by_month = ratio.groupby(ratio.index.month).mean()
    by_month = by_month / by_month.mean()
    seasonal_index = pd.DataFrame(
        {
            "month": by_month.index.astype(int),
            "month_name": [calendar.month_abbr[m] for m in by_month.index.astype(int)],
            "index": by_month.to_numpy(dtype=float),
        }
    )

    backtest = pd.DataFrame(backtest_rows)
    metrics = {
        "model": FORECAST_MODEL,
        "train_months": len(series),
        "horizon": int(horizon),
        "backtest_windows": len(backtest),
        "wape_mean": float(backtest["wape"].mean()) if len(backtest) else float("nan"),
        "wape_latest": float(backtest.iloc[0]["wape"]) if len(backtest) else float("nan"),
        "mae_latest": float(backtest.iloc[0]["mae"]) if len(backtest) else float("nan"),
        "bias_latest": float(backtest.iloc[0]["bias"]) if len(backtest) else float("nan"),
        "band_pct": band_pct,
        "residual_std": float(np.nanstd(np.asarray(model.resid, dtype=float), ddof=1)),
        "converged": not any("converge" in message.lower() for message in fit_warnings),
        "warnings": fit_warnings,
    }
    return {
        "history": history,
        "forecast": forecast,
        "backtest": backtest,
        "seasonal_index": seasonal_index,
        "metrics": metrics,
    }


# --------------------------------------------------------------------------- #
# Price elasticity
# --------------------------------------------------------------------------- #
def _two_way_demean(values: np.ndarray, sku: np.ndarray, month: np.ndarray) -> np.ndarray:
    """Alternating projections for SKU + month fixed effects."""
    out = values.astype(float).copy()
    for _ in range(50):
        previous = out.copy()
        out -= pd.Series(out).groupby(sku).transform("mean").to_numpy()
        out -= pd.Series(out).groupby(month).transform("mean").to_numpy()
        if float(np.max(np.abs(out - previous))) < 1e-10:
            break
    return out


def _elasticity_one(
    frame: pd.DataFrame, *, min_obs: int, min_skus: int, price_col: str
) -> dict | None:
    required = ["sku_id", "ym", "units", price_col, "discount_rate"]
    data = frame[required].rename(columns={price_col: "avg_price"}).copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    data = data[
        (data["units"] > 0) & (data["avg_price"] > 0) & (data["discount_rate"] >= 0)
    ]
    if (
        len(data) < min_obs
        or data["sku_id"].nunique() < min_skus
        or data["ym"].nunique() < 2
    ):
        return None

    sku = data["sku_id"].to_numpy()
    month = data["ym"].astype(str).to_numpy()
    y = _two_way_demean(np.log(data["units"].to_numpy(dtype=float)), sku, month)
    price = _two_way_demean(np.log(data["avg_price"].to_numpy(dtype=float)), sku, month)
    discount = _two_way_demean(data["discount_rate"].to_numpy(dtype=float), sku, month)
    if float(np.std(price)) < 1e-12:
        return None

    design = np.column_stack([price, discount])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ beta
    sst = float(y @ y)
    r2 = 1.0 - float(residual @ residual) / sst if sst > 0 else float("nan")

    xtx_inv = np.linalg.inv(design.T @ design)
    meat = np.zeros((2, 2))
    for positions in data.groupby("sku_id").indices.values():
        score = design[positions].T @ residual[positions]
        meat += np.outer(score, score)
    n_obs = len(data)
    n_skus = int(data["sku_id"].nunique())
    correction = (
        (n_skus / (n_skus - 1)) * ((n_obs - 1) / (n_obs - 2))
        if n_skus > 1 and n_obs > 2
        else 1.0
    )
    covariance = correction * xtx_inv @ meat @ xtx_inv
    standard_errors = np.sqrt(np.diag(covariance))
    t_values = beta / np.where(standard_errors > 0, standard_errors, np.nan)
    p_values = [math.erfc(abs(t) / math.sqrt(2)) if np.isfinite(t) else np.nan for t in t_values]

    ordered = data.sort_values(["sku_id", "ym"])
    price_moves = (
        ordered.groupby("sku_id")["avg_price"].pct_change().abs().replace([np.inf], np.nan)
    )
    return {
        "n_obs": n_obs,
        "n_skus": n_skus,
        "n_months": int(data["ym"].nunique()),
        "beta_price": float(beta[0]),
        "se_price": float(standard_errors[0]),
        "t_price": float(t_values[0]),
        "p_price": float(p_values[0]),
        "beta_discount": float(beta[1]),
        "se_discount": float(standard_errors[1]),
        "t_discount": float(t_values[1]),
        "p_discount": float(p_values[1]),
        "r2_within": r2,
        "mean_discount": float(data["discount_rate"].mean()),
        "mean_abs_price_change": float(price_moves.mean(skipna=True)),
        "discounted_share": float((data["discount_rate"] > 0).mean()),
    }


def price_elasticity(
    frame: pd.DataFrame,
    *,
    group_col: str | None = None,
    price_col: str = "avg_unit_price",
    min_obs: int = 100,
    min_skus: int = 2,
) -> pd.DataFrame:
    """Estimate the within-SKU/month price response, optionally by group.

    Returns one row per group (or a single 'All' row). A null result is a real
    result: the current data show no usable price elasticity (see audit A11).
    """
    groups: list[tuple[str, pd.DataFrame]] = [("All", frame)]
    if group_col:
        if group_col not in frame.columns:
            raise ValueError(f"price_elasticity needs column '{group_col}'.")
        groups.extend((str(name), part) for name, part in frame.groupby(group_col))
    rows: list[dict] = []
    for name, part in groups:
        result = _elasticity_one(
            part, min_obs=min_obs, min_skus=min_skus, price_col=price_col
        )
        if result is None:
            continue
        result["group"] = name
        rows.append(result)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Churn holdout
# --------------------------------------------------------------------------- #
def _auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Rank-based ROC AUC (no sklearn dependency)."""
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    return float(
        (ranks[labels == 1].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def _churn_matrix(frame: pd.DataFrame, label_col: str, min_tenure: int):
    data = frame[frame["tenure"] >= min_tenure].copy()
    needed = ["recency", "orders", "monetary", "tenure", "aov", "customer_segment", label_col]
    data = data.dropna(subset=needed)
    design = pd.DataFrame(
        {
            "recency": data["recency"].astype(float),
            "log_orders": np.log1p(data["orders"].astype(float)),
            "log_monetary": np.log1p(data["monetary"].astype(float)),
            "log_tenure": np.log1p(data["tenure"].astype(float)),
            "log_aov": np.log1p(data["aov"].astype(float)),
            "b2b": (data["customer_segment"] == "B2B reseller").astype(int),
        }
    )
    return sm.add_constant(design), data[label_col].astype(int), data


def churn_holdout(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    label_col: str = "bought_next",
    min_tenure: int = 365,
) -> dict:
    """Fit a logistic repurchase model and score a temporal holdout.

    ``train`` and ``test`` must carry recency/orders/monetary/tenure/aov,
    customer_segment, and the binary ``label_col`` (1 = purchased in the next
    12 months). Customers below ``min_tenure`` are excluded from both sides.
    """
    x_train, y_train, _ = _churn_matrix(train, label_col, min_tenure)
    x_test, y_test, test_rows = _churn_matrix(test, label_col, min_tenure)
    if len(x_train) < 100 or len(x_test) < 100:
        raise ValueError("Not enough eligible customers for a churn holdout.")

    model = sm.Logit(y_train, x_train).fit(disp=0, maxiter=200)
    probability = np.asarray(model.predict(x_test), dtype=float)
    predicted_churn = 1.0 - probability
    actual_churn = 1 - y_test.to_numpy(dtype=int)

    deciles = pd.DataFrame(
        {"predicted_churn": predicted_churn, "actual_churn": actual_churn}
    )
    deciles["decile"] = (
        pd.qcut(deciles["predicted_churn"].rank(method="first"), 10, labels=False) + 1
    )
    decile_table = (
        deciles.groupby("decile")
        .agg(
            customers=("actual_churn", "size"),
            actual_churn=("actual_churn", "mean"),
            predicted_churn=("predicted_churn", "mean"),
        )
        .reset_index()
    )

    coefficients = pd.DataFrame(
        {
            "term": x_train.columns,
            "coef": np.asarray(model.params),
            "se": np.asarray(model.bse),
            "z": np.asarray(model.tvalues),
            "p": np.asarray(model.pvalues),
        }
    )
    accuracy = float(((probability >= 0.5).astype(int) == y_test.to_numpy(dtype=int)).mean())
    auc = _auc(y_test.to_numpy(dtype=int), probability)
    return {
        "auc": auc,
        "accuracy": accuracy,
        "base_churn": float(actual_churn.mean()),
        "predicted_churn": float(predicted_churn.mean()),
        "n_train": len(x_train),
        "n_test": len(x_test),
        "cutoff_rows": test_rows,
        "coefficients": coefficients,
        "deciles": decile_table,
        "model": model,
    }


def discrimination_note(auc: float) -> str:
    """Plain-language reading of the holdout AUC, used by the dashboard."""
    if not np.isfinite(auc):
        return "Holdout AUC could not be computed."
    if auc < 0.55:
        return (
            "No usable discrimination: the 12-month holdout AUC is "
            f"{auc:.3f} (0.50 = coin flip). Do not use this model to rank customers."
        )
    if auc < 0.65:
        return f"Weak discrimination (holdout AUC {auc:.3f}); directional at best."
    return f"Useful discrimination (holdout AUC {auc:.3f})."
