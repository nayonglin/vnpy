"""Stage268's frozen outcome and statistical definitions, without engine replay.

All features and labels must be computed on the actual source calendar before
bootstrap.  No function below reconstructs an equity/price path from resampled
returns.  Missing rows remain in the bootstrap population and are masked only
after whole rows have been drawn.  These are historical conditional-association
estimates, not causal estimates or unseen out-of-sample validation.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


REGIMES = ("low", "mid", "high")
REGIME_ALIASES = {"低": "low", "中": "mid", "高": "high", "middle": "mid", "medium": "mid"}


def _dates(values) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(values, errors="raise")).normalize()
    if dates.hasnans:
        raise ValueError("source calendar/date contains NaT")
    if dates.has_duplicates:
        raise ValueError("source calendar/date must contain one row per day")
    return dates


def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
    return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)


def build_outcomes(daily: pd.DataFrame, calendar=None, initial_capital: float = 150000.0) -> pd.DataFrame:
    """Create complete future u+1..u+20 labels and as-of-u past60 measures.

    ``calendar`` is the explicit actual source trading-day calendar, not a
    weekday calendar.  All of its rows are preserved.  With ``None``, the
    supplied daily dates are assumed to be the complete source calendar; an
    absent trading date cannot be inferred from prices alone.  Pass an explicit
    calendar whenever that completeness has not already been established.

    Equity return is E[u+20]/E[u]-1; cash is the sum of the same twenty future
    net_pnl values.  Both require every source row and finite positive equity
    throughout the twenty-day interval.  Zero returns remain valid labels and
    are not profitable.  Tail labels remain missing.  The as-of-u 60-day sample
    volatility uses simple daily equity returns (ddof=1); normalization divides
    Y20 by sigma60*sqrt(20), with no positive floor for zero volatility.

    Extra-slippage columns subtract exactly one additional original slippage
    from the frozen original path; they do not describe an engine rerun.
    """
    required = {"date", "account_equity", "net_pnl"}
    if not required.issubset(daily.columns):
        raise ValueError(f"daily is missing columns: {sorted(required - set(daily.columns))}")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be finite and positive")
    source = daily.copy()
    source["date"] = _dates(source["date"])
    source = source.sort_values("date").set_index("date")
    dates = source.index if calendar is None else _dates(calendar).sort_values()
    if not source.index.isin(dates).all():
        raise ValueError("daily contains a source date outside the supplied calendar")
    result = source.reindex(dates).copy()
    result.index.name = "date"
    result["source_present"] = dates.isin(source.index)
    result = result.reset_index()
    n = len(result)
    equity = _numeric(result, "account_equity")
    cash = _numeric(result, "net_pnl")
    present = result["source_present"].to_numpy(dtype=bool)
    equity_valid = np.isfinite(equity) & (equity > 0)
    cash_valid = np.isfinite(cash)
    daily_return = np.full(n, np.nan)
    if n:
        # Initial capital is immediately before the first real daily source
        # row, not before missing calendar rows supplied as earlier history.
        first_source = np.flatnonzero(present)
        if len(first_source) and first_source[0] == 0 and equity_valid[0]:
            daily_return[0] = equity[0] / initial_capital - 1
        for u in range(1, n):
            if present[u - 1:u + 1].all() and equity_valid[u - 1:u + 1].all():
                daily_return[u] = equity[u] / equity[u - 1] - 1
    result["daily_return"] = daily_return
    result["label_end"] = pd.NaT
    result["label_status"] = "immature_tail"
    for col in ("future20_return", "future20_cash", "future20_profit", "past60_return", "past60_vol", "normalized_future20_return"):
        result[col] = np.nan
    has_slippage = "slippage" in result
    if has_slippage:
        slippage = _numeric(result, "slippage")
        for col in ("future20_slippage", "future20_cash_extra_slippage", "future20_return_extra_slippage"):
            result[col] = np.nan
    for u in range(n):
        if u >= 59:
            returns = daily_return[u - 59:u + 1]
            if np.isfinite(returns).all():
                base = initial_capital if u == 59 else equity[u - 60]
                result.at[u, "past60_return"] = equity[u] / base - 1
                volatility = float(np.std(returns, ddof=1))
                # A mathematically constant compounded return can acquire
                # division roundoff around 1e-16.  Treat machine-resolution
                # noise as zero, never as a tiny denominator generating an
                # enormous normalized label.  This is not an economic vol
                # floor: genuinely small, resolved volatility stays unchanged.
                roundoff = np.finfo(float).eps * max(1.0, float(np.max(np.abs(returns))))
                result.at[u, "past60_vol"] = 0.0 if volatility <= roundoff else volatility
        if u + 20 >= n:
            continue
        result.at[u, "label_end"] = dates[u + 20]
        span = slice(u, u + 21)
        future = slice(u + 1, u + 21)
        if not present[span].all():
            result.at[u, "label_status"] = "missing_source_day"
            continue
        if not equity_valid[span].all() or not cash_valid[future].all():
            result.at[u, "label_status"] = "invalid_label_source"
            continue
        outcome = equity[u + 20] / equity[u] - 1
        future_cash = float(cash[future].sum())
        result.at[u, "future20_return"] = outcome
        result.at[u, "future20_cash"] = future_cash
        result.at[u, "future20_profit"] = float(outcome > 0)
        result.at[u, "label_status"] = "complete"
        if has_slippage and np.isfinite(slippage[future]).all() and (slippage[future] >= 0).all():
            extra = float(slippage[future].sum())
            result.at[u, "future20_slippage"] = extra
            result.at[u, "future20_cash_extra_slippage"] = future_cash - extra
            result.at[u, "future20_return_extra_slippage"] = outcome - extra / equity[u]
    volatility = result["past60_vol"].to_numpy(dtype=float)
    usable_vol = np.isfinite(volatility) & (volatility > 0)
    result.loc[usable_vol, "normalized_future20_return"] = (
        result.loc[usable_vol, "future20_return"] / (volatility[usable_vol] * np.sqrt(20))
    )
    result["label_mature"] = result["label_status"].eq("complete")
    result.attrs["calendar_assumption"] = "explicit_actual_source_calendar" if calendar is not None else "daily_dates_assumed_complete"
    result.attrs["normalization"] = "future20_return / (asof_u_daily_simple_return_sample_std60 * sqrt(20)); zero vol -> missing"
    result.attrs["extra_slippage_scope"] = "fixed original path accounting sensitivity; not a two-cost engine replay"
    return result


def split_period(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    """Return period anchors only when the full future label ends in-period.

    This is for split descriptive tables.  For block inference, preserve the
    full underlying calendar and mask these labels, rather than compressing
    gaps by joining filtered periods (for example in a leave-one-year table).
    """
    dates = pd.to_datetime(frame["date"])
    label_end = pd.to_datetime(frame["label_end"])
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start > end:
        raise ValueError("period start must be no later than end")
    mask = dates.between(start, end) & label_end.between(start, end)
    return frame.loc[mask].copy()


def _regime(frame: pd.DataFrame) -> np.ndarray:
    return frame["regime"].replace(REGIME_ALIASES).to_numpy(dtype=object)


def _joint_arrays(frame: pd.DataFrame, outcome: str):
    y = _numeric(frame, outcome)
    original = _numeric(frame, "future20_return")
    regime = _regime(frame)
    valid = np.isfinite(y) & np.isfinite(original) & np.isin(regime, REGIMES)
    # Same original twenty-day label for both endpoints, including zero.
    probability = (original > 0).astype(float)
    return y, probability, regime, valid


def group_stats(frame: pd.DataFrame, outcome: str = "future20_return") -> pd.DataFrame:
    """Show all three groups, retaining zeros and the actual unbalanced counts."""
    y, profit, regime, valid = _joint_arrays(frame, outcome)
    rows = []
    for group in REGIMES:
        mask = valid & (regime == group)
        n = int(mask.sum())
        row = {"regime": group, "n_rows": int((regime == group).sum()), "n": n,
               "mean": float(y[mask].mean()) if n else np.nan,
               "median": float(np.median(y[mask])) if n else np.nan,
               "profit_probability": float(profit[mask].mean()) if n else np.nan}
        rows.append(row)
    return pd.DataFrame(rows)


def stationary_indexes(n: int, block: float, repeats: int = 2000, seed: int = 42) -> np.ndarray:
    """Circular stationary bootstrap indices; geometric mean block length.

    Draw one common index sequence per repetition for all columns/products.
    An independent uniform restart occurs with probability 1/block per step.
    Calendar gaps are ordinary population rows, never dropped by this function.
    """
    if int(n) != n or n <= 0 or int(repeats) != repeats or repeats <= 0:
        raise ValueError("n and repeats must be positive integers")
    if not np.isfinite(block) or block < 1:
        raise ValueError("block must be finite and at least one")
    n, repeats = int(n), int(repeats)
    rng = np.random.default_rng(seed)
    indexes = np.empty((repeats, n), dtype=np.int64)
    indexes[:, 0] = rng.integers(n, size=repeats)
    for j in range(1, n):
        restart = rng.random(repeats) < 1 / block
        new_starts = rng.integers(n, size=repeats)
        indexes[:, j] = np.where(restart, new_starts, (indexes[:, j - 1] + 1) % n)
    return indexes


def effect_summary(frame: pd.DataFrame, outcome: str = "future20_return") -> dict:
    """Quick point estimates for annual and leave-one-year descriptions."""
    table = group_stats(frame, outcome)
    groups = table.set_index("regime")
    _, _, _, valid = _joint_arrays(frame, outcome)
    summary = {
        "outcome": outcome, "n_calendar": len(frame), "n_labeled": int(valid.sum()),
        "n_low": int(groups.at["low", "n"]), "n_mid": int(groups.at["mid", "n"]), "n_high": int(groups.at["high", "n"]),
        "return_difference": float(groups.at["high", "mean"] - groups.at["low", "mean"]),
        "profit_probability_difference": float(groups.at["high", "profit_probability"] - groups.at["low", "profit_probability"]),
        "groups": table.to_dict(orient="records"),
        "approx_60day_blocks": len(frame) / 60, "approx_120day_blocks": len(frame) / 120,
        # Fixed anchors in the original calendar, rather than adjacent nonmissing rows.
        "nonoverlap20_n": int(valid[::20].sum()),
    }
    return summary


def _ci_and_p(draws: np.ndarray, estimate: float) -> tuple[list[float], float, int]:
    draws = draws[np.isfinite(draws)]
    if not len(draws) or not np.isfinite(estimate):
        return [np.nan, np.nan], np.nan, len(draws)
    interval = np.quantile(draws, [.025, .975]).astype(float).tolist()
    # Empirical bootstrap error distribution centered under H0: theta=0.
    # Not a count of positive resampled effects (which is not a null p-value).
    p = (1 + np.count_nonzero(np.abs(draws - estimate) >= abs(estimate))) / (len(draws) + 1)
    return interval, float(p), len(draws)


def effect_with_bootstrap(frame: pd.DataFrame, block: float = 60, repeats: int = 2000,
                          seed: int = 42, outcome: str = "future20_return") -> dict:
    """High-minus-low effect with percentile 95% stationary bootstrap CI.

    ``frame`` must contain all actual source calendar rows, including rows with
    unavailable features/labels.  Draw calendar indices first, then apply the
    common complete-label mask for both endpoints.  Missing one comparison
    group in a repetition makes that repetition undefined; counts are exposed.

    p-values are approximate two-sided null-centered bootstrap-error tail
    proportions (plus-one correction).  CIs and cross-period direction are the
    main evidence; the p-values are not exact tests and add no market cycles.
    """
    result = effect_summary(frame, outcome)
    y, profit, regimes, valid = _joint_arrays(frame, outcome)
    y_draws = np.full(repeats, np.nan)
    p_draws = np.full(repeats, np.nan)
    group_means = {g: np.full(repeats, np.nan) for g in REGIMES}
    group_probabilities = {g: np.full(repeats, np.nan) for g in REGIMES}
    if len(frame):
        indexes = stationary_indexes(len(frame), block, repeats, seed)
        for b, idx in enumerate(indexes):
            draw_valid, draw_group = valid[idx], regimes[idx]
            for group in REGIMES:
                take = draw_valid & (draw_group == group)
                if take.any():
                    group_means[group][b] = y[idx][take].mean()
                    group_probabilities[group][b] = profit[idx][take].mean()
            y_draws[b] = group_means["high"][b] - group_means["low"][b]
            p_draws[b] = group_probabilities["high"][b] - group_probabilities["low"][b]
    return_ci, return_p, valid_repeats = _ci_and_p(y_draws, result["return_difference"])
    probability_ci, probability_p, _ = _ci_and_p(p_draws, result["profit_probability_difference"])
    result.update({
        "return_ci": return_ci, "return_p_null_centered": return_p,
        "profit_probability_ci": probability_ci, "profit_probability_p_null_centered": probability_p,
        "holm_pvalues": holm_adjust([return_p, probability_p]),
        "block": block, "repeats": repeats, "seed": seed,
        "bootstrap_valid_repeats": valid_repeats,
        "bootstrap_invalid_repeats": repeats - valid_repeats,
        "ci_method": "95% percentile stationary block bootstrap; fixed calendar rows, joint sample",
        "p_value_method": "approximate two-sided null-centered bootstrap error tail; (1+count(abs(theta_star-theta_hat)>=abs(theta_hat)))/(B_valid+1)",
        "missing_calendar_policy": "all calendar rows sampled jointly before complete-label masking; no compressed dropna calendar",
    })
    for row in result["groups"]:
        group = row["regime"]
        row["mean_ci"] = _ci_and_p(group_means[group], row["mean"])[0]
        row["profit_probability_ci"] = _ci_and_p(group_probabilities[group], row["profit_probability"])[0]
    return result


def holm_adjust(pvals: Sequence[float]) -> list[float]:
    """Holm-adjust predeclared family; unavailable tests retain family size."""
    values = np.asarray(pvals, dtype=float)
    if values.ndim != 1:
        raise ValueError("pvals must be one dimensional")
    finite = np.isfinite(values)
    if ((values[finite] < 0) | (values[finite] > 1)).any():
        raise ValueError("p-values must be between zero and one")
    adjusted = np.full(len(values), np.nan)
    order = np.flatnonzero(finite)[np.argsort(values[finite], kind="stable")]
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def ols_incremental(frame: pd.DataFrame, x: str = "er60_expanding_pct",
                    controls: Sequence[str] | None = None, year_fe: bool = True,
                    outcome: str = "future20_return") -> dict:
    """Fixed low-dimensional OLS association, using only a joint finite sample.

    Numeric features are standardized for the solve, then coefficients are
    converted back to original units.  ``beta`` is outcome change for a +1.0
    change in original x (for an expanding percentile on [0,1], the entire
    percentile range); ``beta_per_sd`` is the sample-one-SD change.  Controls
    must have been made as-of-u by the caller.  No future exposure may be used.
    There is no iid standard error or CI: a minimum-norm coefficient from a
    rank-deficient model is not reported as an identified incremental effect.
    """
    controls = list(controls or [])
    if x in controls or len(controls) != len(set(controls)):
        raise ValueError("controls must be unique and must not duplicate x")
    names = [x, *controls]
    values = np.column_stack([_numeric(frame, name) for name in names])
    y = _numeric(frame, outcome)
    valid = np.isfinite(y) & np.isfinite(values).all(axis=1)
    years = None
    if year_fe:
        dates = pd.to_datetime(frame["date"], errors="coerce")
        valid &= dates.notna().to_numpy()
        years = dates.dt.year.to_numpy()[valid]
    numeric, target = values[valid], y[valid]
    n = len(target)
    result = {
        "x": x, "outcome": outcome, "controls": controls, "year_fe": year_fe,
        "n": n, "n_calendar": len(frame), "n_missing_joint": len(frame) - n,
        "beta": np.nan, "beta_per_sd": np.nan, "rank": 0,
        "coefficients": {}, "dropped_constant_controls": [],
        "beta_units": "outcome per +1.0 original x unit; x percentile uses [0,1] units",
        "ci_method": "not computed; no iid standard errors used for overlapping outcomes",
        "status": "insufficient_sample",
    }
    if n < 2:
        return result
    means, scales = numeric.mean(axis=0), numeric.std(axis=0, ddof=0)
    if scales[0] == 0:
        result["status"] = "constant_x"
        return result
    keep = scales > 0
    result["dropped_constant_controls"] = [name for name, good in zip(names, keep) if not good]
    kept_names = [name for name, good in zip(names, keep) if good]
    standardized = (numeric[:, keep] - means[keep]) / scales[keep]
    design = np.column_stack([np.ones(n), standardized])
    dummy_names = []
    if year_fe:
        unique_years = sorted(np.unique(years))
        dummy_names = [f"year_{int(year)}" for year in unique_years[1:]]
        for year in unique_years[1:]:
            design = np.column_stack([design, (years == year).astype(float)])
        result["reference_year"] = int(unique_years[0])
    result["n_parameters"] = design.shape[1]
    beta_scaled, _, rank, singular = np.linalg.lstsq(design, target, rcond=None)
    result["rank"] = int(rank)
    result["condition_number_standardized"] = float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 0 else np.inf
    if rank < design.shape[1]:
        result["status"] = "rank_deficient"
        return result
    if n <= design.shape[1]:
        return result
    numeric_coeff = beta_scaled[1:1 + len(kept_names)] / scales[keep]
    coeff = dict(zip(kept_names, map(float, numeric_coeff)))
    coeff["intercept"] = float(beta_scaled[0] - np.dot(numeric_coeff, means[keep]))
    coeff.update(dict(zip(dummy_names, map(float, beta_scaled[1 + len(kept_names):]))))
    residual = target - design @ beta_scaled
    tss = float(np.sum((target - target.mean()) ** 2))
    result.update({"beta": coeff[x], "beta_per_sd": float(beta_scaled[1]),
                   "coefficients": coeff, "status": "ok", "r_squared": 1 - float(residual @ residual) / tss if tss > 0 else np.nan})
    return result
