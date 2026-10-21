"""Independent, read-only saved diagnostics for fixed Stage079/080 four cash accounts.

No author module is imported. Calling review_cash_diagnostics reads completed
saved artifacts only; importing this helper performs no data I/O or execution.
The caller must first independently reconcile the supplied account summaries.
"""
from pathlib import Path
import json
import hashlib
import io

import numpy as np
import pandas as pd

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
    for col in ("qty", "multiplier", "fill_price", "fee", "slippage", "realized_gross", "net_pnl", "unrealized", "notional"):
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
                          total_filled_qty=int(fills.qty.sum()), total_fees=float(fills.fee.sum()), total_slippage=float(fills.slippage.sum()), turnover_notional=float((fills.qty * fills.multiplier * fills.fill_price).sum()),
                          closed_top5_positive_net_CNY=float(closed.loc[closed.net_pnl.gt(0), "net_pnl"].nlargest(5).sum()),
                          closed_positive_net_CNY=float(closed.loc[closed.net_pnl.gt(0), "net_pnl"].sum())), "summary diagnostics")
    return daily, log, dict(daily_rows=len(daily), family_year_rows=len(expected_family), active_families=len(active),
                            stale_days=int((daily.stale_positions > 0).sum()), terminal_open_episodes=len(opened),
                            terminal_stale_episodes=int(opened.state.eq("stale_open_unresolved").sum()))


def _indices(n):
    _require(n > 0, "empty bootstrap calendar")
    starts = np.random.default_rng(20261018).integers(0, n, size=(2000, (n + 251) // 252), dtype=np.int64)
    return ((starts[..., None] + np.arange(252)) % n).reshape(2000, -1)[:, :n].astype(np.int32)


def _bound(binding, basename):
    path = Path(binding["path"])
    _require(path.name == basename, "unexpected baseline artifact kind")
    data = path.read_bytes()
    _require(len(data) == binding["bytes"] and hashlib.sha256(data).hexdigest() == binding["sha256"], "frozen baseline binding differs")
    return data


def _daily_summary(daily, summary, initial):
    """Reconcile only facts identifiable in a saved daily curve, no old fills."""
    _require(len(daily) > 0 and daily.date.is_unique and daily.date.is_monotonic_increasing, "baseline daily calendar")
    path = np.r_[initial, daily.equity.to_numpy(float)]
    insolvent = bool(_booleans(daily.ever_insolvent).any())
    returns = path[1:] / path[:-1] - 1 if not insolvent and (path > 0).all() else None
    sharpe = None
    if returns is not None and len(returns) > 1 and returns.std(ddof=1) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(252))
    last = daily.iloc[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown = float(np.min(path / np.maximum.accumulate(path) - 1) * 100)
    expected = dict(initial_capital=initial, ending_equity=float(path[-1]), total_return_pct=(path[-1] / initial - 1) * 100,
                    max_drawdown_pct=drawdown if np.isfinite(drawdown) else None, sharpe=sharpe, ever_insolvent=insolvent,
                    total_fees=float(last.cumulative_fees), total_slippage=float(last.cumulative_slippage),
                    cumulative_realized_gross=float(last.cumulative_realized_gross), unrealized=float(last.unrealized),
                    open_positions=int(last.open_positions), stale_positions=int(last.stale_positions),
                    open_notional=float(last.open_notional), stale_zero_equity=float(last.stale_zero_equity),
                    all_open_long_zero_scenario_equity=float(last.unresolved_zero_equity),
                    max_open_notional=float(daily.open_notional.max()), max_buffered_margin=float(daily.buffered_margin.max()),
                    max_frozen_initial_risk=float(daily.initial_risk.max()),
                    valuation_stress_not_universal_lower_bound=True, production_qualified=False)
    _fields(summary, expected, "saved daily/summary")
    compare(daily.equity, initial + daily.cumulative_realized_gross - daily.cumulative_fees + daily.unrealized, "saved daily equity identity")


def _annual_rows(daily, initial):
    previous, rows = float(initial), []
    for year, group in daily.groupby(daily.date.str[:4], sort=True):
        path = np.r_[previous, group.equity.to_numpy(float)]
        with np.errstate(divide="ignore", invalid="ignore"):
            drawdown = float(np.min(path / np.maximum.accumulate(path) - 1) * 100)
        rows.append(dict(year=year, source_days=len(group), starting_equity=previous, ending_equity=float(path[-1]),
                         return_pct=(path[-1] / previous - 1) * 100 if previous > 0 else None,
                         max_drawdown_pct=drawdown if np.isfinite(drawdown) else None,
                         continuous_account_slice=True, independent_cold_start=False))
        previous = float(path[-1])
    return rows


def _gate(points):
    """The sole frozen079 continuation condition, independently expressed."""
    primary = points[("primary_2020", "stress")]
    directions = primary["return_percentage_point_difference"] > 0
    directions &= points[("primary_2020", "base")]["return_percentage_point_difference"] > 0
    directions &= all(points[("cold_2023", c)]["return_percentage_point_difference"] >= 0 for c in COSTS)
    values = list(points.values())
    identified = all(p["drawdown_percentage_point_difference"] is not None for p in values)
    dd = all(p["drawdown_percentage_point_difference"] >= 0 for p in values if p["drawdown_percentage_point_difference"] is not None)
    ci = primary["ci95_low"] is not None and primary["ci95_low"] > 0
    nominal = bool(directions and identified and dd and ci)
    empty = all(p["identification"] == "all_empty_unidentified" for p in values)
    unknown = any(p["differential_historical_stale"] or p["zero_scenario_reverses_positive_return_delta"] for p in values)
    if empty:
        status = "all_empty_unidentified"
    elif directions and dd and ci and not identified:
        status = "unknown_empty_reference_DD"
    elif nominal:
        status = "unknown_differential_unidentified" if unknown else "supported_research_model_only"
    else:
        status = "unsupported"
    return dict(nominal_pass=nominal, status=status, qualification="unknown_differential_unidentified" if unknown else "research_model_only",
                primary_return_higher=bool(primary["return_percentage_point_difference"] > 0), drawdown_not_deeper=bool(dd),
                primary_paired_CI_low_positive=bool(ci), base_and_cold_consistent=bool(directions),
                goal_complete=False, no_automatic_promotion=True, independent_full_actual_review_required=True)


def review_cash_diagnostics(cash_dir, summaries, protocol):
    """Review saved Stage080 artifacts after the caller reconciles 4 new ledgers.

    summaries: name -> new070-style summary, names NARROW_COMMON_{window}_{cost}.
    protocol: parsed frozen079 dict. Reads new saved diagnostics/tables and only
    bound accepted070 daily.csv.gz, summary.json, and the two saved .npy indices.
    No imports of author code, old reservations, market data, SQL, fits or replay.
    """
    cash_dir = Path(cash_dir)
    _fields(protocol, dict(schema="stage079_one_lot_prefilter_protocol_v1", policy="NARROW", arm="COMMON"), "079 scope")
    finance = protocol["finance"]
    _fields(finance, dict(initial=1000000, new_cash_accounts=4), "079 finite finance")
    _fields(finance["bootstrap"], dict(repetitions=2000, block_length=252, seed=20261018), "079 bootstrap")
    _require(finance["costs"] == list(COSTS) and [w["id"] for w in finance["windows"]] == list(WINDOWS), "079 windows/costs")
    keys = [(w, c) for w in WINDOWS for c in COSTS]
    name = lambda w, c: f"NARROW_COMMON_{w}_{c}"
    names = {name(*k) for k in keys}
    _require(set(summaries) == names and set(protocol["baselines"]) == names, "exact4 new and baseline accounts")
    _require(set(protocol["bootstrap_indices"]) == set(WINDOWS), "two frozen old indices")
    diagnostics = json.loads((cash_dir / "diagnostics.json").read_text())
    _require(set(diagnostics) == names, "exact4 diagnostics")
    family = _read(cash_dir, "family_year_including_zero")
    families = sorted(family.family_id.unique())
    _require(len(families) == 95 and set(family.variant) == {"ONE_LOT_PREFILTER"}, "all95 new family universe")
    _require(set(zip(family.window, family.cost)) == set(keys), "four family grids")
    annual = _read(cash_dir, "annual_slices")
    # 080 writes new report rows without a variant field; only imported old
    # rows carry ACCEPTED070. This is the concrete 080 table schema.
    annual["variant"] = annual["variant"].fillna("ONE_LOT_PREFILTER")
    summary_table = _read(cash_dir, "new_and_accepted_summary")
    variants = ("ONE_LOT_PREFILTER", "ACCEPTED070")
    _require(len(summary_table) == 8 and not summary_table.duplicated(["window", "cost", "variant"]).any(), "eight unique summaries")
    _require(set(zip(summary_table.window, summary_table.cost, summary_table.variant)) == {(w, c, v) for w, c in keys for v in variants}, "summary identities")
    _require(set(zip(annual.account, annual.variant)) == {(n, v) for n in names for v in variants}, "annual variant identities")
    indices, daily, old_daily, old_summary, logs, old_logs, counts = {}, {}, {}, {}, {}, {}, {}
    for window in WINDOWS:
        binding = protocol["bootstrap_indices"][window]
        indices[window] = np.load(io.BytesIO(_bound(binding, window + "_bootstrap_indices.npy")), allow_pickle=False)
    for key in keys:
        account = name(*key)
        selected = family.loc[family.window.eq(key[0]) & family.cost.eq(key[1])]
        daily[key], logs[key], counts[account] = _account(cash_dir / account, summaries[account], diagnostics[account], selected, families)
        _fields(diagnostics[account], dict(baseline_daily_and_summary_only=True), "baseline scope disclosure")
        _daily_summary(daily[key], summaries[account], finance["initial"])
        binding = protocol["baselines"][account]
        old_daily[key] = pd.read_csv(io.BytesIO(_bound(binding["daily"], "daily.csv.gz")), compression="gzip", dtype={"date": str})
        old_summary[key] = json.loads(_bound(binding["summary"], "summary.json"))
        _daily_summary(old_daily[key], old_summary[key], finance["initial"])
        _require(daily[key].date.tolist() == old_daily[key].date.tolist(), "new/old paired dates")
        old_logs[key] = _log(old_daily[key], finance["initial"])
        for variant, frame, summary in ((variants[0], daily[key], summaries[account]), (variants[1], old_daily[key], old_summary[key])):
            rows = annual.loc[annual.account.eq(account) & annual.variant.eq(variant)].sort_values("year")
            expected = _annual_rows(frame, finance["initial"])
            _require(len(rows) == len(expected), "annual saved row count")
            for actual, expected_row in zip(rows.to_dict("records"), expected):
                _fields(actual, expected_row, "saved annual table")
            row = summary_table.loc[summary_table.window.eq(key[0]) & summary_table.cost.eq(key[1]) & summary_table.variant.eq(variant)].iloc[0].to_dict()
            for field, value in summary.items():
                if not isinstance(value, (dict, list)):
                    _require(field in row, "summary table missing " + field)
                    compare(row[field], value, "summary table " + field)
    comparisons = _read(cash_dir, "comparisons")
    distributions = _read(cash_dir, "bootstrap_distributions")
    _require(len(comparisons) == 4 and not comparisons.duplicated(["window", "cost"]).any(), "four unique comparisons")
    _require(len(distributions) == 2000 and set(distributions.columns) == names, "2000x4 saved distributions")
    points = {}
    for window in WINDOWS:
        dates = daily[(window, "base")].date.tolist()
        _require(daily[(window, "stress")].date.tolist() == dates, "common new base/stress dates")
        index = indices[window]
        _require(index.dtype == np.int32 and np.array_equal(index, _indices(len(dates))), "fixed old circular252/2000/seed20261018 indices")
        schedule = next(w for w in finance["windows"] if w["id"] == window)
        _require(dates[0] >= schedule["start"] and dates[-1] == schedule["end"], "window calendar bounds")
        for cost in COSTS:
            key, account = (window, cost), name(window, cost)
            new, old = summaries[account], old_summary[key]
            reference_empty = old["fills"] == 0
            zero_delta = float(daily[key].unresolved_zero_equity.iloc[-1] - old_daily[key].unresolved_zero_equity.iloc[-1])
            delta = new["total_return_pct"] - old["total_return_pct"]
            point = dict(return_percentage_point_difference=delta,
                         drawdown_percentage_point_difference=None if reference_empty else new["max_drawdown_pct"] - old["max_drawdown_pct"],
                         dd_comparison_state="NA_empty_reference" if reference_empty else "active_reference",
                         identification="all_empty_unidentified" if new["fills"] == old["fills"] == 0 else "observed_cash_comparison",
                         differential_historical_stale=bool(not np.array_equal(daily[key].stale_notional.to_numpy(), old_daily[key].stale_notional.to_numpy())),
                         all_open_zero_ending_equity_difference=zero_delta,
                         zero_scenario_reverses_positive_return_delta=bool(delta > 0 and zero_delta <= 0),
                         actual_total_filled_qty_difference=new["total_filled_qty"] - old["total_filled_qty"])
            if logs[key] is None or old_logs[key] is None:
                values = np.full(2000, np.nan)
                point.update(status="survival_failure_no_log_repair", ci95_low=None, ci95_high=None,
                             mean_daily_log_difference=None, cumulative_log_difference=None)
            else:
                difference = logs[key] - old_logs[key]
                values = difference[index].mean(axis=1)
                low, high = np.quantile(values, [.025, .975])
                point.update(status="valid", ci95_low=float(low), ci95_high=float(high),
                             mean_daily_log_difference=float(difference.mean()), cumulative_log_difference=float(difference.sum()))
            row = comparisons.loc[comparisons.window.eq(window) & comparisons.cost.eq(cost)]
            _require(len(row) == 1, "expected paired comparison")
            _fields(row.iloc[0].to_dict(), point, account + ".comparison")
            compare(distributions[account], values, account + ".bootstrap", atol=1e-12)
            points[key] = point
    gate = _gate(points)
    saved_gate = json.loads((cash_dir / "continuation_gate.json").read_text())
    _fields(saved_gate, gate, "continuation gate")
    return dict(new_accounts_checked=4, old_saved_daily_summary_checked=4, all_families=95, comparisons_checked=4,
                repetitions=2000, block_length=252, seed=20261018, account_diagnostics=counts, continuation_gate=gate,
                old_fills_or_reservations_read=False, old_total_filled_qty_rederived=False,
                unknown_payoff_bound_established=False)
