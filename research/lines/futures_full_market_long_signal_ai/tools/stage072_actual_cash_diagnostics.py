"""Independent, read-only review of Stage070 saved cash diagnostics.

No author module is imported. Calling review_cash_diagnostics reads completed
saved artifacts only; importing this helper performs no data I/O or execution.
The caller must first independently reconcile the supplied account summaries.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

POLICIES = ("WIDE", "NARROW")
ARMS = ("COMMON", "SETTLEMENT", "OHLC_PROXY")
WINDOWS = ("primary_2020", "cold_2023")
COSTS = ("base", "stress")


def _require(condition, label):
    if not condition:
        raise AssertionError(label)


def _missing(value):
    return value is None or (np.isscalar(value) and bool(pd.isna(value)))


def compare(actual, expected, label="value", atol=1e-6, rtol=1e-10):
    """Compare numeric arrays/scalars, strings, booleans and null values."""
    if np.isscalar(actual) or actual is None:
        if _missing(actual) or _missing(expected):
            _require(_missing(actual) and _missing(expected), label + ": null differs")
        elif isinstance(expected, (str, bool, np.bool_)):
            _require(actual == expected, label + ": value differs")
        else:
            _require(bool(np.isclose(actual, expected, atol=atol, rtol=rtol)), label + ": numeric differs")
        return
    a, b = np.asarray(actual), np.asarray(expected)
    _require(a.shape == b.shape, label + ": shape differs")
    _require(bool(np.allclose(a.astype(float), b.astype(float), atol=atol, rtol=rtol, equal_nan=True)), label + ": array differs")


def _fields(actual, expected, label):
    for key, value in expected.items():
        _require(key in actual, label + ": missing " + key)
        compare(actual[key], value, label + "." + key)


def _read(directory, name):
    frame = pd.read_csv(directory / (name + ".csv.gz"), dtype={"date": str, "year": str, "family_id": str})
    # Explicit numeric dtypes also cover legitimate zero-trade tables.
    for col in ("qty", "multiplier", "fill_price", "fee", "realized_gross", "net_pnl", "unrealized", "notional"):
        if col in frame:
            frame[col] = pd.to_numeric(frame[col], errors="raise")
    return frame


def _booleans(values):
    lowered = values.astype(str).str.lower()
    _require(lowered.isin(["true", "false", "0", "1"]).all(), "invalid saved boolean")
    return lowered.isin(["true", "1"]).to_numpy()


def _log(daily, initial):
    path = np.r_[initial, daily.equity.to_numpy(float)]
    insolvent = _booleans(daily.ever_insolvent).any() if "ever_insolvent" in daily else False
    if insolvent or not np.isfinite(path).all() or (path <= 0).any():
        return None
    return np.log(path[1:] / path[:-1])


def _account(directory, summary, diag, saved_family, all_families):
    daily, fills, positions, closed, opened = [_read(directory, n) for n in ("daily", "fills", "positions", "closed", "open")]
    _require(len(daily) > 0 and daily.date.is_unique and daily.date.is_monotonic_increasing, "daily calendar")
    initial = float(summary["initial_capital"])
    years = sorted(daily.date.str[:4].unique())
    previous, annual = initial, []
    for year in years:
        rows = daily.loc[daily.date.str.startswith(year)]
        path = np.r_[previous, rows.equity.to_numpy(float)]
        with np.errstate(divide="ignore", invalid="ignore"):
            drawdown = float(np.min(path / np.maximum.accumulate(path) - 1) * 100)
        annual.append(dict(year=year, partial=year == "2026", source_days=len(rows), starting_equity=previous,
                           ending_equity=float(path[-1]), cash_growth=float(path[-1] - previous),
                           return_pct=(path[-1] / previous - 1) * 100 if previous > 0 else None,
                           max_drawdown_pct=drawdown if np.isfinite(drawdown) else None,
                           continuous_account_slice=True, independent_cold_start=False))
        previous = float(path[-1])
    _require(len(diag["annual_slices"]) == len(annual), "annual slice count")
    for actual, expected in zip(diag["annual_slices"], annual):
        _fields(actual, expected, directory.name + ".annual")
    dates = pd.Index(daily.date)
    active = sorted(set(fills.family_id) | set(positions.family_id))
    _require(set(active).issubset(all_families), "unknown saved family")
    records, by_day = [], np.zeros(len(daily))
    for family in active:
        f = fills.loc[fills.family_id.eq(family)].groupby("date")[["realized_gross", "fee"]].sum().reindex(dates, fill_value=0.)
        u = positions.loc[positions.family_id.eq(family)].groupby("date").unrealized.sum().reindex(dates, fill_value=0.)
        contribution = f.realized_gross.to_numpy(float) - f.fee.to_numpy(float) + np.diff(np.r_[0., u.to_numpy(float)])
        by_day += contribution
        frame = pd.DataFrame(dict(year=daily.date.str[:4], net_equity_contribution=contribution, fee=f.fee.to_numpy(float)))
        for year, row in frame.groupby("year")[["net_equity_contribution", "fee"]].sum().iterrows():
            records.append(dict(family_id=family, year=year, net_equity_contribution=row.net_equity_contribution, fee=row.fee))
    residual = float(np.max(np.abs(by_day - np.diff(np.r_[initial, daily.equity.to_numpy(float)])))) if active else abs(previous - initial)
    _require(residual <= 1e-5, "independent family/day reconciliation")
    compare(diag["attribution_max_abs_error"], residual, "attribution residual", atol=1e-5)
    columns = ["family_id", "year", "net_equity_contribution", "fee"]
    active_year = pd.DataFrame(records, columns=columns)
    grid = pd.MultiIndex.from_product([all_families, years], names=["family_id", "year"])
    expected_family = active_year.set_index(["family_id", "year"]).reindex(grid, fill_value=0.).sort_index()
    _require(not saved_family.duplicated(["family_id", "year"]).any(), "duplicate family/year")
    actual_family = saved_family.set_index(["family_id", "year"]).sort_index()
    _require(actual_family.index.tolist() == expected_family.index.tolist(), "all95 family/year grid")
    for col in columns[2:]:
        compare(actual_family[col], expected_family[col], "family/year " + col)
    compare(expected_family.net_equity_contribution.sum(), previous - initial, "family attribution ending equity")
    concentration = diag["family_year_concentration"]
    _require([r["year"] for r in concentration] == (years if active else []), "concentration years")
    for record in concentration:
        values = expected_family.xs(record["year"], level="year").net_equity_contribution
        wins, losses = values[values > 0].sort_values(ascending=False), values[values < 0].sort_values()
        wp, lp = float(wins.sum()), float(-losses.sum())
        _fields(record, dict(gross_positive_contributions=wp, gross_negative_contributions=lp,
                            largest_winner_share=None if not wp else wins.iloc[0] / wp,
                            top5_winner_share=None if not wp else wins.head(5).sum() / wp,
                            largest_loser_share=None if not lp else -losses.iloc[0] / lp), "concentration")
        for key, series in (("largest_winning_family", wins), ("largest_losing_family", losses)):
            if series.empty:
                compare(record[key], None, key)
            else:
                _require(record[key] in series.index, key + ": absent family")
                compare(series.loc[record[key]], series.iloc[0], key + ": not extremum")
    log = _log(daily, initial)
    _fields(diag, dict(log_status="valid" if log is not None else "survival_failure_no_log_repair",
                       cumulative_log_growth=None if log is None else float(log.sum()),
                       stale_days=int((daily.stale_positions > 0).sum()), max_stale_notional=float(daily.stale_notional.max()),
                       minimum_stale_zero_equity=float(daily.stale_zero_equity.min()),
                       minimum_all_open_zero_equity=float(daily.unresolved_zero_equity.min()),
                       unresolved_zero_is_scenario_not_universal_bound=True), "unknown/stale diagnostics")
    stale = positions.loc[positions.mark_state.eq("stale")]
    stale_count = stale.groupby("date").size().reindex(dates, fill_value=0)
    stale_value = stale.groupby("date").notional.sum().reindex(dates, fill_value=0.)
    open_value = positions.groupby("date").notional.sum().reindex(dates, fill_value=0.)
    compare(daily.stale_positions, stale_count, "saved stale position count")
    compare(daily.stale_notional, stale_value, "saved stale notional")
    compare(daily.stale_zero_equity, daily.equity.to_numpy() - stale_value.to_numpy(), "stale zero scenario")
    compare(daily.unresolved_zero_equity, daily.equity.to_numpy() - open_value.to_numpy(), "all open zero scenario")
    _fields(summary, dict(fills=len(fills), max_open_notional=float(daily.open_notional.max()),
                          max_buffered_margin=float(daily.buffered_margin.max()), max_frozen_initial_risk=float(daily.initial_risk.max()),
                          total_filled_qty=int(fills.qty.sum()), turnover_notional=float((fills.qty * fills.multiplier * fills.fill_price).sum()),
                          closed_top5_positive_net_CNY=float(closed.loc[closed.net_pnl.gt(0), "net_pnl"].nlargest(5).sum()),
                          closed_positive_net_CNY=float(closed.loc[closed.net_pnl.gt(0), "net_pnl"].sum())), "summary diagnostics")
    return daily, log, dict(daily_rows=len(daily), family_year_rows=len(expected_family), active_families=len(active),
                            stale_days=int((daily.stale_positions > 0).sum()), terminal_open_episodes=len(opened),
                            terminal_stale_episodes=int(opened.state.eq("stale_open_unresolved").sum()))


def _indices(n):
    _require(n > 0, "empty bootstrap calendar")
    starts = np.random.default_rng(20261018).integers(0, n, size=(2000, (n + 251) // 252), dtype=np.int64)
    return ((starts[..., None] + np.arange(252)) % n).reshape(2000, -1)[:, :n].astype(np.int32)


def review_cash_diagnostics(cash_dir, summaries):
    """Recompute saved annual/family/unknown diagnostics, 20 contrasts and 3 gates.

    summaries is {account_directory_name: independently_reconciled_070_summary}.
    Returns JSON-safe counts and nominal gates; raises AssertionError on mismatch.
    This verifies published research gates, without certifying unknown payoffs.
    """
    cash_dir = Path(cash_dir)
    name = lambda p, a, w, c: f"{p}_{a}_{w}_{c}"
    keys = [(p, a, w, c) for p in POLICIES for a in ARMS for w in WINDOWS for c in COSTS]
    names = {name(*k) for k in keys}
    _require(set(summaries) == names, "exact 24 supplied summaries")
    diagnostics = json.loads((cash_dir / "diagnostics.json").read_text())
    _require(set(diagnostics) == names, "exact 24 diagnostics")
    family = _read(cash_dir, "family_year_including_zero")
    families = sorted(family.family_id.unique())
    _require(len(families) == 95, "all95 family universe")
    _require(set(zip(family.policy, family.arm, family.window, family.cost)) == set(keys), "24 family grids")
    daily, logs, counts = {}, {}, {}
    for key in keys:
        account = name(*key)
        selected = family.loc[family.policy.eq(key[0]) & family.arm.eq(key[1]) & family.window.eq(key[2]) & family.cost.eq(key[3])]
        daily[key], logs[key], counts[account] = _account(cash_dir / account, summaries[account], diagnostics[account], selected, families)
    comparisons = _read(cash_dir, "comparisons")
    distributions = _read(cash_dir, "bootstrap_distributions")
    _require(len(comparisons) == 20 and not comparisons.duplicated(["window", "cost", "contrast"]).any(), "20 unique comparisons")
    _require(len(distributions) == 2000 and len(distributions.columns) == 20, "2000 x 20 saved distributions")
    points, distribution_names = {}, set()
    for window in WINDOWS:
        reference_dates = daily[("NARROW", "SETTLEMENT", window, "stress")].date.tolist()
        _require(all(daily[k].date.tolist() == reference_dates for k in keys if k[2] == window), "common window calendar")
        index = _indices(len(reference_dates))
        saved_index = np.load(cash_dir / (window + "_bootstrap_indices.npy"), allow_pickle=False)
        _require(saved_index.dtype == np.int32 and np.array_equal(saved_index, index), "common circular252 indices seed20261018")
        for cost in COSTS:
            contrasts = [((p, "SETTLEMENT", window, cost), (p, r, window, cost), f"{p}_SETTLEMENT_minus_{r}") for p in POLICIES for r in ("COMMON", "OHLC_PROXY")]
            contrasts.append((("NARROW", "SETTLEMENT", window, cost), ("WIDE", "SETTLEMENT", window, cost), "NARROW_minus_WIDE_SETTLEMENT"))
            for a, b, contrast in contrasts:
                sa, sb = summaries[name(*a)], summaries[name(*b)]
                both_empty, reference_empty = sa["fills"] == sb["fills"] == 0, sb["fills"] == 0
                point = dict(return_percentage_point_difference=sa["total_return_pct"] - sb["total_return_pct"],
                             drawdown_percentage_point_difference=None if reference_empty else sa["max_drawdown_pct"] - sb["max_drawdown_pct"],
                             dd_comparison_state="NA_empty_reference" if reference_empty else "active_reference",
                             identification="all_empty_unidentified" if both_empty else "observed_cash_comparison")
                if logs[a] is None or logs[b] is None:
                    values = np.full(2000, np.nan)
                    point.update(status="survival_failure_no_log_repair", ci95_low=None, ci95_high=None,
                                 mean_daily_log_difference=None, cumulative_log_difference=None)
                else:
                    difference = logs[a] - logs[b]
                    values = difference[index].mean(axis=1)
                    low, high = np.quantile(values, [.025, .975])
                    point.update(status="valid", ci95_low=float(low), ci95_high=float(high),
                                 mean_daily_log_difference=float(difference.mean()), cumulative_log_difference=float(difference.sum()))
                row = comparisons.loc[comparisons.window.eq(window) & comparisons.cost.eq(cost) & comparisons.contrast.eq(contrast)]
                _require(len(row) == 1, "missing expected contrast")
                _fields(row.iloc[0].to_dict(), point, window + "." + cost + "." + contrast)
                ident = window + "_" + cost + "_" + contrast
                _require(ident in distributions, "missing bootstrap distribution")
                compare(distributions[ident], values, ident + ".distribution", atol=1e-12)
                distribution_names.add(ident)
                points[(window, cost, contrast)] = point
    _require(set(distributions.columns) == distribution_names, "bootstrap contrast column identities")
    any_stale = any(c["stale_days"] > 0 for c in counts.values())
    gates = []
    for policy in POLICIES:
        primary = [points[("primary_2020", "stress", f"{policy}_SETTLEMENT_minus_{r}")] for r in ("COMMON", "OHLC_PROXY")]
        cold = [points[("cold_2023", c, f"{policy}_SETTLEMENT_minus_{r}")] for c in COSTS for r in ("COMMON", "OHLC_PROXY")]
        nominal = summaries[name(policy, "SETTLEMENT", "primary_2020", "stress")]["total_return_pct"] > 0
        nominal &= all(p["ci95_low"] is not None and p["ci95_low"] > 0 for p in primary)
        nominal &= all(summaries[name(policy, "SETTLEMENT", "cold_2023", c)]["total_return_pct"] > 0 for c in COSTS)
        nominal &= all(p["return_percentage_point_difference"] >= 0 for p in cold)
        empty = all(summaries[name(policy, a, w, c)]["fills"] == 0 for a in ARMS for w in WINDOWS for c in COSTS)
        state = "all_empty_unidentified" if empty else "unknown_historical_stale" if nominal and any_stale else "supported_research_model_only" if nominal else "unsupported"
        gates.append(dict(policy=policy, nominal_pass=bool(nominal), status=state, kind="information", empty_reference_dd_not_a_gate=True))
    relevant = [points[(w, c, "NARROW_minus_WIDE_SETTLEMENT")] for w in WINDOWS for c in COSTS]
    gains = all(points[(w, c, "NARROW_minus_WIDE_SETTLEMENT")]["return_percentage_point_difference"] > 0 if w == "primary_2020" else points[(w, c, "NARROW_minus_WIDE_SETTLEMENT")]["return_percentage_point_difference"] >= 0 for w in WINDOWS for c in COSTS)
    identified = all(p["drawdown_percentage_point_difference"] is not None for p in relevant)
    no_worse = all(p["drawdown_percentage_point_difference"] >= 0 for p in relevant if p["drawdown_percentage_point_difference"] is not None)
    empty = all(p["identification"] == "all_empty_unidentified" for p in relevant)
    state = "all_empty_unidentified" if empty else "unknown_empty_reference_DD" if gains and no_worse and not identified else "unknown_historical_stale" if gains and no_worse and any_stale else "supported_research_model_only" if gains and no_worse else "unsupported"
    gates.append(dict(kind="policy_package", nominal_pass=bool(gains and no_worse and identified), status=state, pure_stop_causal_claim=False))
    saved = json.loads((cash_dir / "continuation_gates.json").read_text())
    _require(len(saved["gates"]) == 3, "three saved gates")
    for actual, expected in zip(saved["gates"], gates):
        _fields(actual, expected, "continuation gate")
    _fields(saved, dict(any_historical_stale=any_stale, goal_complete=False, independent_actual_review_required=True, no_automatic_promotion=True), "gate disclosures")
    disclosure = json.loads((cash_dir / "budget_and_tick_disclosure.json").read_text())
    _fields(disclosure, dict(continuous_boundary_not_necessarily_tick_order=True, no_gap_loss_cap=True), "tick/budget disclosure")
    _require({r["policy"] for r in disclosure["policy_tick"]} == set(POLICIES) and len(disclosure["policy_tick"]) == 2, "two tick disclosures")
    for row in disclosure["policy_tick"]:
        _require(0 <= row["stop_distance_below_tick"] <= row["known_tick_rows"] <= row["ready_rows"], "tick disclosure counts")
    return dict(accounts_checked=24, all_families=95, comparisons_checked=20, repetitions=2000, block_length=252,
                seed=20261018, any_historical_stale=any_stale, account_diagnostics=counts, nominal_gates=gates,
                tick_counts_independently_rederived=False, unknown_payoff_bound_established=False)
