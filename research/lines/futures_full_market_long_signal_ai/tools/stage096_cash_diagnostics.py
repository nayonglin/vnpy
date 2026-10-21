"""Independent saved-cash diagnostics for frozen092 ORDER versus BAG.

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

ARMS = ("ORDER", "BAG")
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
    costs = fills.assign(year=fills.date.str[:4]).groupby(["family_id", "year"]).agg(
        slippage=("slippage", "sum"), fill_count=("qty", "size"), filled_qty=("qty", "sum"))
    costs = costs.reindex(grid, fill_value=0.).sort_index()
    for col in ("slippage", "fill_count", "filled_qty"):
        compare(actual_family[col], costs[col], "family/year " + col)
        expected_family[col] = costs[col]
    return daily, log, dict(daily_rows=len(daily), family_year_rows=len(expected_family), active_families=len(active),
                            stale_days=int((daily.stale_positions > 0).sum()), terminal_open_episodes=len(opened),
                            terminal_stale_episodes=int(opened.state.eq("stale_open_unresolved").sum())), expected_family.reset_index()


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


def _bound(binding):
    data = Path(binding["path"]).read_bytes()
    _require(len(data) == binding["bytes"] and hashlib.sha256(data).hexdigest() == binding["sha256"], "frozen artifact binding differs")
    return data


def _nested(actual, expected, label):
    """Allow float roundoff only; preserve structure, nulls and decision signs."""
    if isinstance(expected, dict):
        _require(isinstance(actual, dict) and set(actual) == set(expected), label + ": keys differ")
        for key in expected:
            _nested(actual[key], expected[key], label + "." + str(key))
    elif isinstance(expected, (list, tuple)):
        _require(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label + ": sequence differs")
        for index, (a, b) in enumerate(zip(actual, expected)):
            _nested(a, b, label + "." + str(index))
    elif actual is None or expected is None:
        _require(actual is None and expected is None, label + ": null differs")
    elif isinstance(actual, (bool, np.bool_)) or isinstance(expected, (bool, np.bool_)):
        _require(isinstance(actual, (bool, np.bool_)) and isinstance(expected, (bool, np.bool_)) and actual == expected, label + ": boolean differs")
    elif isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        numeric = (int, float, np.integer, np.floating)
        _require(isinstance(actual, numeric) and isinstance(expected, numeric), label + ": numeric type differs")
        _require(np.isfinite(actual) and np.isfinite(expected) and np.sign(actual) == np.sign(expected), label + ": finite value/sign differs")
        compare(actual, expected, label)
    else:
        _require(type(actual) is type(expected) and actual == expected, label + ": exact value differs")


def _gate(points, held, any_stale, main_unknown):
    """Separate cash identification from main/held label identification."""
    _require(set(held.get("groups", {})) == {"holdout_0", "holdout_1"}, "both independently reviewed held groups")
    values = list(points.values())
    returns = all(p["return_percentage_point_difference"] > 0 if w == "primary_2020" else p["return_percentage_point_difference"] >= 0 for (w, _), p in points.items())
    dds = [p["drawdown_percentage_point_difference"] for p in values]
    dd_known = all(v is not None and np.isfinite(v) for v in dds)
    dd = all(v >= 0 for v in dds if v is not None and np.isfinite(v))
    low = points[("primary_2020", "stress")]["ci95_low"]
    ci = low is not None and np.isfinite(low) and low > 0
    own = all(p["active_total_return_pct"] > 0 and np.isfinite(p["active_total_return_pct"]) for p in values)
    cash_nominal = bool(returns and dd_known and dd and ci and own)
    groups = list(held["groups"].values())
    held_nominal = all(g.get("nominal_pass") is True for g in groups)
    held_unknown = any(g.get("unknown_differential_selected_events", 0) > 0 or g.get("status") == "unknown" for g in groups)
    if all(p["identification"] == "all_empty_unidentified" for p in values):
        status = "all_empty_unidentified"
    elif not (returns and dd and ci and held_nominal and own):
        status = "unsupported"
    elif not dd_known:
        status = "unknown_empty_reference_DD"
    elif any_stale:
        status = "unknown_historical_stale"
    elif held_unknown:
        status = "unknown_differential_held_outcome"
    else:
        status = "supported_research_model_only"
    return dict(status=status, cash_nominal_pass=cash_nominal, held_known_nominal_pass=bool(held_nominal),
                ORDER_own_returns_positive_in_all_four=bool(own),
                nominal_pass=bool(cash_nominal and held_nominal), financial_unknown=bool(any_stale or not dd_known),
                signal_unknown_main=bool(main_unknown), held_signal_unknown=bool(held_unknown),
                signal_label_uncertainty_is_not_cash_exposure=True, goal_complete=False, production_qualified=False,
                increased_betting_qualified=False, independent_actual_review_required=True, no_automatic_promotion=True)


def _signal(cash_dir, held, signal_report, signal_states):
    _require(signal_report is not None and signal_states is not None, "independently reviewed main signal report and states required")
    saved = json.loads((cash_dir / "signal_identification.json").read_text())
    _require(saved["main"] == signal_report, "independent main signal report differs")
    _nested(saved["held_groups"], held["groups"], "independent held groups")
    _nested(json.loads(_bound(saved["held_binding"])), held, "held bound independent input")
    _fields(saved, dict(label_unknown_not_a_cash_gate=True), "signal cash separation")
    _fields(signal_report, dict(main_prediction_rows_per_arm=161014, full_mother_rows=399252,
                               unfilled_signal_label_uncertainty_is_not_cash_exposure=True), "main signal scope")
    _require(sum(signal_report["full_mother_label_states"].values()) == 399252, "full mother label state count")
    _require(0 <= signal_report["unknown_differential_selected_events"] <= 161014, "unknown main count")
    actual = _read(cash_dir, "main_signal_states")
    expected = pd.DataFrame(signal_states).copy()
    _require(set(actual.columns) == set(expected.columns), "signal state columns")
    for frame in (actual, expected):
        frame["year"] = frame.year.astype(str)
        _require(not frame.duplicated(["year", "label_state"]).any(), "duplicate signal state identity")
    actual = actual.sort_values(["year", "label_state"]).reset_index(drop=True)
    expected = expected.sort_values(["year", "label_state"]).reset_index(drop=True)
    _require(actual[["year", "label_state"]].fillna("").values.tolist() == expected[["year", "label_state"]].fillna("").values.tolist(), "signal state identity")
    for col in set(actual.columns) - {"year", "label_state"}:
        compare(actual[col], expected[col], "independent main states " + col)
    compare(actual.rows.sum(), 161014, "main state total")
    return signal_report["unknown_differential_selected_events"] > 0


def review_cash_diagnostics(cash_dir, summaries, protocol, held, *, signal_report=None, signal_states=None):
    """Read saved8 cash only; parent supplies independently reviewed held/main.

    summaries keys: NARROW_{CONTROL|OI}_{primary_2020|cold_2023}_{base|stress}.
    signal_report and signal_states are required keyword inputs from the parent
    model checker. No author imports, labels/predictions, SQL, fit or cash replay.
    """
    cash_dir = Path(cash_dir)
    _fields(protocol, dict(schema="stage092_crossday_order_bag_protocol_v1"), "084 scope")
    finance = protocol["finance"]
    _fields(finance, dict(initial=1000000, new_cash_accounts=8, allocation="accepted070_original; no080/noOI"), "084 finance")
    _fields(finance["bootstrap"], dict(repetitions=2000, block_length=252, seed=20261018), "084 bootstrap")
    _require(finance["arms"] == list(ARMS) and finance["costs"] == list(COSTS), "fixed two arms/costs")
    _require([w["id"] for w in finance["windows"]] == list(WINDOWS), "fixed two windows")
    keys = [(a, w, c) for a in ARMS for w in WINDOWS for c in COSTS]
    name = lambda a, w, c: f"NARROW_{a}_{w}_{c}"
    names = {name(*k) for k in keys}
    _require(set(summaries) == names, "exact8 independent summaries")
    reports = json.loads((cash_dir / "diagnostics.json").read_text())
    _require(set(reports) == names, "exact8 diagnostics")
    family = _read(cash_dir, "family_year_including_zero")
    families = sorted(family.family_id.unique())
    _require(len(families) == 95 and set(zip(family.arm, family.window, family.cost)) == set(keys), "8 x all95 family universe")
    annual = _read(cash_dir, "annual_slices")
    _require(set(annual.account) == names and not annual.duplicated(["account", "year"]).any(), "unique8 account annual tables")
    summary_table = _read(cash_dir, "account_summaries")
    _require(len(summary_table) == 8 and set(zip(summary_table.arm, summary_table.window, summary_table.cost)) == set(keys), "eight summary identities")
    daily, logs, counts, family_expected = {}, {}, {}, []
    for key in keys:
        account = name(*key)
        selected = family.loc[family.arm.eq(key[0]) & family.window.eq(key[1]) & family.cost.eq(key[2])]
        daily[key], logs[key], counts[account], fy = _account(cash_dir / account, summaries[account], reports[account], selected, families)
        family_expected.append(fy.assign(arm=key[0], window=key[1], cost=key[2]))
        _daily_summary(daily[key], summaries[account], finance["initial"])
        rows = annual.loc[annual.account.eq(account)].sort_values("year")
        _require(len(rows) == len(reports[account]["annual_slices"]), "annual row count")
        for actual, expected in zip(rows.to_dict("records"), reports[account]["annual_slices"]):
            _fields(actual, expected, "saved annual table")
        row = summary_table.loc[summary_table.arm.eq(key[0]) & summary_table.window.eq(key[1]) & summary_table.cost.eq(key[2])].iloc[0].to_dict()
        for field, value in summaries[account].items():
            if not isinstance(value, (dict, list)):
                _require(field in row, "summary table missing " + field)
                compare(row[field], value, "account summary " + field)
    totals = _read(cash_dir, "family_total_including_zero")
    group_cols = ["arm", "window", "cost", "family_id"]
    measures = ["net_equity_contribution", "fee", "slippage", "fill_count", "filled_qty"]
    expected = pd.concat(family_expected).groupby(group_cols)[measures].sum().sort_index()
    _require(not totals.duplicated(group_cols).any(), "duplicate family total")
    actual = totals.set_index(group_cols).sort_index()
    _require(actual.index.tolist() == expected.index.tolist(), "8 x all95 family total grid")
    for col in measures:
        compare(actual[col], expected[col], "independent family total " + col)
    comparisons = _read(cash_dir, "comparisons")
    distributions = _read(cash_dir, "bootstrap_distributions")
    expected_columns = {w + "_" + c + "_ORDER_minus_BAG" for w in WINDOWS for c in COSTS}
    _require(len(comparisons) == 4 and not comparisons.duplicated(["window", "cost"]).any(), "four unique comparisons")
    _require(set(comparisons.contrast) == {"ORDER_minus_BAG"}, "single frozen contrast")
    _require(len(distributions) == 2000 and set(distributions.columns) == expected_columns, "2000 x 4 distributions")
    _require(set(protocol["bootstrap_indices"]) == set(WINDOWS), "two prebound old indices")
    points = {}
    for window in WINDOWS:
        dates = daily[("ORDER", window, "stress")].date.tolist()
        _require(all(daily[k].date.tolist() == dates for k in keys if k[1] == window), "common source calendar")
        schedule = next(w for w in finance["windows"] if w["id"] == window)
        _require(dates[0] >= schedule["start"] and dates[-1] == schedule["end"], "calendar window bounds")
        index = np.load(io.BytesIO(_bound(protocol["bootstrap_indices"][window])), allow_pickle=False)
        _require(index.shape == (2000, len(dates)) and index.dtype.kind in "iu" and index.min() >= 0 and index.max() < len(dates), "bound index shape/type/range")
        for cost in COSTS:
            a, b = ("ORDER", window, cost), ("BAG", window, cost)
            active, control = summaries[name(*a)], summaries[name(*b)]
            empty = control["fills"] == 0
            point = dict(active_total_return_pct=active["total_return_pct"], reference_total_return_pct=control["total_return_pct"],
                         return_percentage_point_difference=active["total_return_pct"] - control["total_return_pct"],
                         drawdown_percentage_point_difference=None if empty else active["max_drawdown_pct"] - control["max_drawdown_pct"],
                         dd_comparison_state="NA_empty_reference" if empty else "active_reference",
                         identification="all_empty_unidentified" if active["fills"] == control["fills"] == 0 else "observed_cash_comparison")
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
            row = comparisons.loc[comparisons.window.eq(window) & comparisons.cost.eq(cost)]
            _require(len(row) == 1, "expected comparison")
            _fields(row.iloc[0].to_dict(), point, window + "." + cost)
            compare(distributions[window + "_" + cost + "_ORDER_minus_BAG"], values, "paired bootstrap", atol=1e-12)
            points[(window, cost)] = point
    main_unknown = _signal(cash_dir, held, signal_report, signal_states)
    any_stale = any(r["stale_days"] > 0 for r in counts.values())
    gate = _gate(points, held, any_stale, main_unknown)
    _fields(json.loads((cash_dir / "continuation_gate.json").read_text()), dict(gate, any_historical_stale=any_stale), "continuation gate")
    disclosure = json.loads((cash_dir / "budget_and_tick_disclosure.json").read_text())
    _fields(disclosure, dict(policy="NARROW", continuous_boundary_not_necessarily_tick_order=True, no_gap_loss_cap=True,
                            normal_open_close_mark_is_frozen_research_valuation=True, zero_price_scenarios_are_not_universal_loss_bounds=True,
                            bootstrap_indices_regenerated=False, normal_open_not_automatically_financial_unknown=True), "financial disclosures")
    _require(disclosure["bootstrap_indices"] == protocol["bootstrap_indices"], "disclosed old indices identity")
    _require(0 <= disclosure["stop_distance_below_tick"] <= disclosure["known_tick_rows"] <= disclosure["ready_rows"], "tick counts range")
    return dict(accounts_checked=8, all_families=95, comparisons_checked=4, repetitions=2000, block_length=252,
                seed=20261018, bootstrap_indices_regenerated=False, account_diagnostics=counts, continuation_gate=gate,
                independently_supplied_main_signal_checked=True, independently_supplied_held_checked=True,
                unknown_payoff_bound_established=False, tick_counts_independently_rederived=False)
