"""Independent Stage001 evidence audit; never imports or runs a strategy engine.

Weekly validation uses scalar EMA recursion instead of the implementation's
pandas ewm. Account validation is enabled only for an explicitly supplied,
completed offline replay directory. Output belongs to this independent reviewer.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUT = LINE / "outputs/stage001_independent_review"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def weekly_audit():
    folder = LINE / "outputs/stage001_weekly_features"
    summary = json.loads((folder / "summary.json").read_text())
    source = Path(summary["source_path"])
    calendar = Path(summary["calendar_path"])
    output = folder / "weekly_daily.csv"
    fingerprints = {
        "source": digest(source) == summary["source_sha256"],
        "calendar": digest(calendar) == summary["calendar_sha256"],
        "weekly_csv": digest(output) == summary["output_sha256"],
        "module": digest(LINE / "tools/stage001_weekly_features.py") == summary["module_sha256"],
        "tests": digest(LINE / "tools/test_stage001_weekly_features.py") == summary["tests_sha256"],
    }
    assert all(fingerprints.values()), fingerprints
    source_rows = pd.read_csv(source, usecols=["date", "product_id", "r"])
    products = summary["products"]
    source_rows = source_rows.loc[source_rows.product_id.isin(products)].copy()
    source_rows["date"] = pd.to_datetime(source_rows.date)
    assert not source_rows.duplicated(["date", "product_id"]).any()
    raw = np.load(calendar, allow_pickle=False)
    dates = list(pd.to_datetime(raw.astype(str), format="%Y%m%d"))
    lo, hi = source_rows.date.min(), source_rows.date.max()
    first_monday = lo - pd.Timedelta(days=lo.dayofweek)
    last_sunday = hi + pd.Timedelta(days=6 - hi.dayofweek)
    weeks = {}
    for date in dates:
        if first_monday <= date <= last_sunday:
            weeks.setdefault(tuple(date.isocalendar()[:2]), []).append(date)
    week_keys = list(weeks)
    day_to_prev_key = {}
    for i, key in enumerate(week_keys):
        for day in weeks[key]:
            if lo <= day <= hi:
                day_to_prev_key[day] = week_keys[i - 1] if i else None

    states = {}
    for product in products:
        values = source_rows.loc[source_rows.product_id.eq(product)].set_index("date").r.to_dict()
        entirely_missing = not any(math.isfinite(v) for v in values.values())
        count = 0
        cumulative_log = 0.0
        fast = slow = signal = prior_hist = None
        for key in week_keys:
            week_days = weeks[key]
            returns = [float(values.get(day, math.nan)) for day in week_days]
            complete = all(math.isfinite(v) for v in returns)
            hist = None
            previous_hist = prior_hist
            if not complete:
                count, cumulative_log = 0, 0.0
                fast = slow = signal = prior_hist = previous_hist = None
            else:
                count += 1
                cumulative_log += math.fsum(returns)
                price = 100.0 * math.exp(cumulative_log)
                fast = price if fast is None else fast + (price - fast) * (2.0 / 13.0)
                slow = price if slow is None else slow + (price - slow) * (2.0 / 27.0)
                if count >= 26:
                    macd = fast - slow
                    signal = macd if signal is None else signal + (macd - signal) * 0.2
                    if count >= 34:
                        hist = macd - signal
                prior_hist = hist
            ready = complete and count >= 35 and hist is not None and previous_hist is not None
            slope = hist - previous_hist if ready else 0.0
            direction = int(slope > 0) - int(slope < 0)
            states[(product, key)] = dict(ready=ready, direction=direction, hist=hist,
                hist_prev=previous_hist, count=count, asof=week_days[-1], complete=complete,
                entirely_missing=entirely_missing)

    observed = pd.read_csv(output, parse_dates=["date", "weekly_asof"])
    assert not observed.duplicated(["date", "product_id"]).any()
    expected_rows = len(day_to_prev_key) * len(products)
    assert len(observed) == expected_rows
    errors = []
    numerical_errors = []
    for row in observed.itertuples(index=False):
        key = day_to_prev_key[row.date]
        state = states.get((row.product_id, key))
        ready = state["ready"] if state else False
        direction = state["direction"] if state else 0
        count = state["count"] if state else 0
        if state and state["entirely_missing"]:
            reason = "missing_product_returns"
        elif state is None:
            reason = "no_completed_week"
        elif not state["complete"]:
            reason = "missing_previous_week_returns"
        elif not ready:
            reason = "warming_up" if count < 35 else "nonfinite_weekly_indicator"
        else:
            reason = "flat_weekly_histogram" if direction == 0 else "ready"
        comparisons = dict(ready=bool(row.weekly_ready) == ready,
            direction=int(row.weekly_direction) == direction,
            count=int(row.weekly_complete_weeks) == count, reason=row.reason == reason,
            asof=pd.isna(row.weekly_asof) if state is None else row.weekly_asof == state["asof"])
        if ready:
            for name in ("hist", "hist_prev"):
                delta = abs(float(getattr(row, "weekly_" + name)) - state[name])
                numerical_errors.append(delta)
                comparisons[name] = math.isclose(float(getattr(row, "weekly_" + name)),
                    state[name], rel_tol=1e-10, abs_tol=1e-8)
        if not all(comparisons.values()):
            errors.append(dict(date=str(row.date.date()), product=row.product_id,
                failed=[k for k, good in comparisons.items() if not good]))
    report = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        scope="independent_scalar_recursion_on_frozen_19_product_cache_not_financial_replay",
        source_fingerprints_match=fingerprints, weekly_rows=len(observed),
        independently_checked_rows=expected_rows, mismatched_rows=len(errors),
        first_mismatches=errors[:20], max_hist_absolute_difference=max(numerical_errors, default=0),
        ready_2020_plus=int(observed.loc[observed.date.ge("2020-01-01"), "weekly_ready"].sum()),
        PnL_accessed=False, production_qualified=False, account_results_reviewed=False,
        conclusion="weekly_cache_arithmetic_and_previous_completed_week_pass" if not errors else "blocked")
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "weekly_independent_checks.json", report)
    assert not errors, report
    return report


def account_audit(source):
    """Rebuild cash/marks and retry-parent episodes from exported fill evidence."""
    source = Path(source).resolve()
    assert source.parent == (LINE / "outputs/stage001_first_screen").resolve()
    identity = re.fullmatch(r"(A0|C0)(?:_attempt[0-9]+)?", source.name)
    assert identity is not None
    arm = identity.group(1)
    names = ["daily.csv", "trades.csv", "positions.csv", "execution_proxy_usage.csv",
        "execution_clock.csv", "internal_equity_daily.csv", "entry_candidates.csv",
        "weekly_gate_audit.csv", "effective_parameters.json", "actual_strategy_settings.json",
        "run_provenance.json", "metrics.json", "minute_scan_requests.csv", "rollover_shape_same_volume.csv"]
    hashes = {name: digest(source / name) for name in names}
    provenance = json.loads((source / "run_provenance.json").read_text())
    assert provenance["arm"] == arm
    assert provenance["status"] == "completed_pending_independent_review"
    assert provenance["production_qualified"] is False
    assert provenance["strict_minutes"] is True and provenance["captured_bar_failure_count"] == 0
    assert provenance["all_consumed_inputs_unchanged_during_run"] is True
    assert provenance["actual_settings_equal_accepted_A"] is True
    assert provenance["parameters_equal_accepted_A"] is True
    assert provenance["minute_input_sha256"] == "5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189"
    old = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3"
    old_provenance = json.loads((old / "run_provenance.json").read_text())
    assert provenance["correctness_code_sha256"] == old_provenance["correctness_code_sha256"]
    assert all(digest(ROOT / name) == value for name, value in provenance["correctness_code_sha256"].items())
    parameters = json.loads((source / "effective_parameters.json").read_text())
    d = pd.read_csv(source / "daily.csv").sort_values("date").reset_index(drop=True)
    t = pd.read_csv(source / "trades.csv").fillna("")
    u = pd.read_csv(source / "execution_proxy_usage.csv").fillna("")
    c = pd.read_csv(source / "execution_clock.csv").fillna("")
    p = pd.read_csv(source / "positions.csv", usecols=["date", "vt_symbol", "start_pos", "end_pos", "close_price", "net_pnl"])
    e = pd.read_csv(source / "internal_equity_daily.csv")
    candidates = pd.read_csv(source / "entry_candidates.csv").fillna("")
    g = pd.read_csv(source / "weekly_gate_audit.csv").fillna("")
    rollover = pd.read_csv(source / "rollover_shape_same_volume.csv").fillna("")
    m = json.loads((source / "metrics.json").read_text())
    assert d.date.is_unique
    assert all(x.trade_id.is_unique for x in (t, u, c))
    assert set(t.trade_id) == set(u.trade_id) == set(c.trade_id)
    assert t.date.tolist() == t.trading_date.tolist()
    tc = t.merge(c, on="trade_id", suffixes=("", "_clock"), validate="one_to_one")
    assert tc.trading_date.eq(tc.trading_date_clock).all()
    assert tc.vt_symbol.eq(tc.vt_symbol_clock).all()
    assert np.allclose(tc.price, tc.price_clock, atol=0, rtol=0)
    assert np.allclose(tc.volume, tc.volume_clock, atol=0, rtol=0)
    assert tc.direction.eq(tc.direction_clock).all() and tc.offset.eq(tc.offset_clock).all()
    t = t.merge(u[["trade_id", "signal_date", "price_source", "execution_datetime"]], on="trade_id", validate="one_to_one")
    t["fill_number"] = t.trade_id.str.rsplit(".", n=1).str[-1].astype(int)
    t = t.sort_values("fill_number").reset_index(drop=True)
    assert t.fill_number.tolist() == list(range(1, len(t) + 1))
    sizes = t.vt_symbol.map(parameters["contract_sizes"]).astype(float)
    slips = t.vt_symbol.map(parameters["slippages"]).astype(float)
    rates = t.vt_symbol.map(parameters["rates"]).astype(float)
    assert not sizes.isna().any()
    t["independent_slippage"] = t.volume * sizes * slips
    t["independent_commission"] = t.volume * sizes * t.price * rates
    t["independent_cash"] = -t.signed_volume * sizes * t.price - t.independent_slippage - t.independent_commission
    capital = float(d.account_capital.iloc[0])
    assert capital == 150000.0
    fill_cash = t.groupby("date").independent_cash.sum().reindex(d.date, fill_value=0).cumsum().to_numpy()
    p["independent_mark"] = p.end_pos * p.close_price * p.vt_symbol.map(parameters["contract_sizes"])
    marks = p.groupby("date").independent_mark.sum().reindex(d.date, fill_value=0).to_numpy()
    independent_equity = capital + fill_cash + marks
    cash_residual = float(np.max(np.abs(independent_equity - d.account_equity.to_numpy())))
    internal = d.merge(e, on="date", validate="one_to_one")
    assert len(internal) == len(d)
    internal_residual = float((internal.account_equity - internal.estimated_equity).abs().max())
    cumsum_residual = float((capital + d.net_pnl.cumsum() - d.account_equity).abs().max())
    position_pnl = p.groupby("date").net_pnl.sum().reindex(d.date, fill_value=0).to_numpy()
    position_residual = float(np.max(np.abs(position_pnl - d.net_pnl)))
    slip_residual = abs(float(t.independent_slippage.sum() - d.slippage.sum()))
    commission_residual = abs(float(t.independent_commission.sum() - d.commission.sum()))
    assert max(cash_residual, internal_residual, cumsum_residual, position_residual, slip_residual, commission_residual) < 1e-6
    equity = d.account_equity.to_numpy(dtype=float)
    changes = np.zeros(len(equity))
    changes[1:] = equity[1:] / equity[:-1] - 1.0
    std = changes.std(ddof=1)
    reconstructed = dict(end_equity=float(equity[-1]), total_return_pct=float((equity[-1] / capital - 1) * 100),
        max_dd_pct=float((equity / np.maximum.accumulate(equity) - 1).min() * 100),
        sharpe=float(changes.mean() / std * math.sqrt(252)) if std > 0 else 0.0,
        total_slippage=float(t.independent_slippage.sum()), total_trade_count=len(t),
        max_broker10_margin_to_equity_pct=float((d.broker10_total_margin_exact / d.account_equity * 100).max()),
        days_over_100pct=int((d.broker10_total_margin_exact / d.account_equity > 1 + 1e-11).sum()),
        days_over_90pct=int((d.broker10_total_margin_exact / d.account_equity > 0.9 + 1e-11).sum()),
        days_equity_below_zero=int((equity <= 0).sum()))
    for key, value in reconstructed.items():
        assert math.isclose(float(m[key]), value, abs_tol=1e-7, rel_tol=1e-11), (key, m[key], value)

    # Scalar cash ledger cycles. A retry inherits the actual ordinary parent
    # order; rollover starts a different contract cycle unless lineage is proven.
    active, root_by_order, closed, retry_rows, rollover_rows = {}, {}, [], [], []
    opened_candidates = candidates.loc[candidates.candidate_status.eq("opened")]
    for row in t.to_dict("records"):
        symbol, opening = row["vt_symbol"], row["offset"] == "开"
        if symbol not in active:
            assert opening, (symbol, row["trade_id"], "close_without_position")
            retry = row["price_source"] == "stage847_intraday_reentry_at_original_entry"
            if retry:
                parent = row["order_id"].split(".intraday.")[0]
                assert parent in root_by_order and parent != row["order_id"]
                original = t.loc[t.order_id.eq(parent) & t.offset.eq("开")]
                assert len(original) == 1 and original.iloc[0].vt_symbol == symbol
                assert original.iloc[0].date == row["date"]
                root, entry_context = root_by_order[parent]
                retry_rows.append(dict(root=root, retry_fill=row["trade_id"], parent_order=parent))
            else:
                root = row["trade_id"]
                direction = "long" if row["signed_volume"] > 0 else "short"
                matches = opened_candidates.loc[opened_candidates.date.eq(row["signal_date"]) &
                    opened_candidates.contract_vt_symbol.eq(symbol) & opened_candidates.direction.eq(direction)]
                if len(matches) == 1:
                    entry_context = str(matches.iloc[0].entry_context)
                else:
                    assert len(matches) == 0, (symbol, row["trade_id"], "mother_candidate_not_unique", len(matches))
                    continuation = rollover.loc[rollover.date.eq(row["signal_date"]) &
                        rollover.target_contract_vt_symbol.eq(symbol) & rollover.direction.eq(direction) &
                        rollover.status.eq("targeted") & pd.to_numeric(rollover.final_volume).ge(row["volume"])]
                    assert len(continuation) == 1, (symbol, row["trade_id"], "unproven_rollover_open")
                    entry_context = "rollover_reopen"
                    rollover_rows.append(dict(fill=row["trade_id"], signal_date=row["signal_date"],
                        source_contract=continuation.iloc[0].old_contract_vt_symbol, target_contract=symbol,
                        diagnostic_index=int(continuation.iloc[0].diagnostic_index), volume=row["volume"]))
            root_by_order[row["order_id"]] = (root, entry_context)
            active[symbol] = dict(root=root, entry_context=entry_context, first_fill=row["trade_id"],
                entry_date=row["date"], symbol=symbol, quantity=0.0, net_cash=0.0,
                costs=0.0, retry=retry)
        cycle = active[symbol]
        if opening:
            assert cycle["quantity"] == 0 or cycle["quantity"] * row["signed_volume"] > 0
        else:
            assert cycle["quantity"] * row["signed_volume"] < 0
            assert abs(cycle["quantity"]) + 1e-9 >= row["volume"]
        cycle["quantity"] += row["signed_volume"]
        cycle["net_cash"] += row["independent_cash"]
        cycle["costs"] += row["independent_slippage"] + row["independent_commission"]
        if abs(cycle["quantity"]) < 1e-9:
            cycle.update(last_fill=row["trade_id"], exit_date=row["date"])
            closed.append(cycle)
            del active[symbol]
    closed_frame = pd.DataFrame(closed)
    still_open_roots = {x["root"] for x in active.values()}
    episodes = closed_frame.loc[~closed_frame.root.isin(still_open_roots)].groupby("root", as_index=False).agg(
        net_pnl=("net_cash", "sum"), costs=("costs", "sum"), cycles=("root", "size"), entry_context=("entry_context", "first"))
    final_marks = p.loc[p.date.eq(d.date.iloc[-1])].set_index("vt_symbol")
    open_net = sum(v["net_cash"] + v["quantity"] * float(final_marks.loc[sym, "close_price"]) * parameters["contract_sizes"][sym]
        for sym, v in active.items())
    cycle_residual = abs(float(closed_frame.net_cash.sum() + open_net - d.net_pnl.sum()))
    assert cycle_residual < 1e-6

    # The gate audit must refer to the exact frozen cache with canonical keys.
    weekly = pd.read_csv(LINE / "outputs/stage001_weekly_features/weekly_daily.csv").fillna("")
    weekly["product_id"] = weekly.product_id.str.upper()
    g["canonical_product"] = g.product_id.str.upper()
    wg = g.merge(weekly, left_on=["date", "canonical_product"], right_on=["date", "product_id"],
        suffixes=("", "_source"), how="left", validate="many_to_one", indicator=True)
    assert wg._merge.eq("both").all()
    assert wg.weekly_ready.eq(wg.weekly_ready_source).all()
    assert wg.weekly_direction.eq(wg.weekly_direction_source).all()
    assert wg.weekly_asof.eq(wg.weekly_asof_source).all()
    signs = wg.direction.map({"long": 1, "short": -1})
    expected_block = (arm == "C0") & wg.native_openable_before & wg.weekly_ready & wg.weekly_direction.ne(signs)
    assert expected_block.eq(wg.gate_blocked).all()
    assert wg.native_openable_after.eq(wg.native_openable_before & ~expected_block).all()
    flat = candidates.loc[candidates.entry_context.eq("flat_entry")]
    joined_gate = flat.merge(g, left_on=["date", "contract_vt_symbol", "direction", "signal"],
        right_on=["date", "target_contract", "direction", "signal"], suffixes=("_candidate", "_audit"),
        how="left", validate="one_to_one", indicator=True)
    assert joined_gate._merge.eq("both").all()
    blocked = joined_gate.loc[joined_gate.gate_blocked]
    assert blocked.candidate_status.eq("skipped").all()
    assert blocked.skip_reason_candidate.str.startswith("weekly_first_screen_").all()
    actual_flat = joined_gate.loc[joined_gate.candidate_status.eq("opened")]
    if arm == "C0":
        assert (~actual_flat.weekly_ready | actual_flat.weekly_direction.eq(actual_flat.direction.map({"long": 1, "short": -1}))).all()
    minutes = pd.read_csv(source / "minute_scan_requests.csv")
    assert minutes.missing_bar_count.eq(0).all()
    assert minutes.coverage_status.eq("complete").all()
    audit_files = OUT / source.name
    audit_files.mkdir(parents=True, exist_ok=True)
    closed_frame.to_csv(audit_files / "independent_cycles.csv", index=False)
    episodes.to_csv(audit_files / "independent_mother_order_episodes.csv", index=False)
    pd.DataFrame(retry_rows).to_csv(audit_files / "independent_retry_links.csv", index=False)
    pd.DataFrame(rollover_rows).to_csv(audit_files / "independent_rollover_open_links.csv", index=False)
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec="seconds"), arm=arm,
        source=str(source), source_hashes=hashes, production_qualified=False,
        review_scope="exported_fill_cashflow_marks_gate_and_retry_identity_no_new_engine_run",
        reconstructed_metrics=reconstructed,
        residuals=dict(cashflow_equity=cash_residual, internal_equity=internal_residual,
            daily_net_pnl_cumsum=cumsum_residual, positions_daily_pnl=position_residual,
            slippage=slip_residual, commission=commission_residual, cycles_and_open_mtm=cycle_residual),
        closed_contract_cycles=len(closed), complete_mother_order_episodes=len(episodes),
        mother_order_episode_wins=int(episodes.net_pnl.gt(1e-6).sum()),
        mother_order_episode_win_rate_pct=float(episodes.net_pnl.gt(1e-6).mean() * 100),
        episode_definition="ordinary opening parent order plus its same-day synthetic retry; rollover contract reopening is a distinct order episode",
        confirmed_retry_parent_links=len(retry_rows), end_open_contracts=len(active), end_open_net_mtm=float(open_net),
        confirmed_rollover_reopen_links=len(rollover_rows),
        observed_flat_entry_plans=len(g), recorded_flat_entry_candidates=len(flat),
        actual_opened_flat_candidates=len(actual_flat), blocked_recorded_flat_candidates=len(blocked),
        native_ready_plans=int((g.native_openable_before & g.weekly_ready).sum()),
        native_unknown_fallback_plans=int((g.native_openable_before & ~g.weekly_ready).sum()),
        coverage_denominator="native flat-entry plans and recorded candidates are separately reported; all-calendar coverage is not trade coverage",
        minute_scan_rows=len(minutes), missing_scan_rows=0,
        source_revalidation_scope="four accepted repair source hashes rechecked against A_final3; consumed input integrity follows frozen receipts, no bulk raw-market/minute re-cleaning",
        confidence_limit="single full historical account path with prior research selection; no new strict OOS, fresh-start or cost-pressure claim",
        status="independent_exported_arithmetic_and_gate_checks_passed")
    assert all(digest(source / name) == sha for name, sha in hashes.items())
    write_json(audit_files / "account_checks.json", result)
    return result


def baseline_audit(source):
    """Compare an already independently audited A0 with accepted A_final3."""
    source = Path(source).resolve()
    account = json.loads((OUT / source.name / "account_checks.json").read_text())
    assert account["arm"] == "A0" and account["status"] == "independent_exported_arithmetic_and_gate_checks_passed"
    old = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3"
    numeric = ["trade_count", "turnover", "commission", "slippage", "trading_pnl", "holding_pnl",
        "net_pnl", "account_equity", "broker10_total_margin_exact", "c3_active_contracts", "c3_active_products"]
    daily_new = pd.read_csv(source / "daily.csv")
    daily_old = pd.read_csv(old / "daily.csv")
    assert daily_new.date.tolist() == daily_old.date.tolist()
    differences = {key: float(np.max(np.abs(daily_new[key].to_numpy() - daily_old[key].to_numpy()))) for key in numeric}
    trades_new = pd.read_csv(source / "trades.csv").fillna("")
    trades_old = pd.read_csv(old / "trades.csv").fillna("")
    keys = ["trade_id", "order_id", "vt_symbol", "date", "datetime", "direction", "offset", "price", "volume", "signed_volume"]
    fills_equal = {key: trades_new[key].tolist() == trades_old[key].tolist() for key in keys}
    new_actual = json.loads((source / "actual_strategy_settings.json").read_text())[0]["actual"]
    old_actual = json.loads((old / "actual_strategy_settings.json").read_text())[0]["actual"]
    def normalize(value, directory):
        if isinstance(value, dict):
            return {key: normalize(item, directory) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item, directory) for item in value]
        return value.replace(directory, "{accepted_empty_signal_directory}") if isinstance(value, str) else value
    new_dir = str(Path(new_actual["supply_demand_signal_path"]).parent)
    old_dir = str(Path(old_actual["supply_demand_signal_path"]).parent)
    actual_equal = normalize(new_actual, new_dir) == normalize(old_actual, old_dir)
    new_parameters = json.loads((source / "effective_parameters.json").read_text())
    old_parameters = json.loads((old / "effective_parameters.json").read_text())
    parameters_equal = normalize(new_parameters, new_dir) == normalize(old_parameters, old_dir)
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        scope="independent_existing_A0_vs_accepted_A_final3_sentinel_not_new_engine",
        source=str(source), accepted_reference=str(old), daily_rows=len(daily_new), fills=len(trades_new),
        daily_max_abs_differences=differences, fill_fields_exact_equal=fills_equal,
        actual_strategy_attributes_equal_after_empty_signal_path_normalization=actual_equal,
        effective_parameters_equal_after_empty_signal_path_normalization=parameters_equal,
        production_qualified=False, unresolved_economic_drift=False)
    passed = all(v == 0 for v in differences.values()) and all(fills_equal.values()) and actual_equal and parameters_equal
    result["status"] = "independent_A0_baseline_sentinel_pass" if passed else "blocked_unexplained_baseline_drift"
    write_json(OUT / source.name / "baseline_sentinel_checks.json", result)
    assert passed, result
    return result


def overlay_audit(folder):
    """Audit append-only local data and A0 read sets, without replaying A0."""
    folder = Path(folder).resolve()
    assert folder.is_relative_to((LINE / "outputs").resolve())
    summary = json.loads((folder / "summary.json").read_text())
    manifest = json.loads((folder / "source_manifest.json").read_text())
    assert summary["status"] == "completed_local_overlay_pending_independent_review"
    assert summary["production_qualified"] is False and summary["financial_replays"] == 0
    assert summary["downloads"] == 0 and summary["all_inputs_unchanged"] is True
    hashes = {name: digest(folder / name) for name in
        ["overlay.csv", "source_manifest.json", "session_manifest.csv", "quarantine.csv", "a0_path_equivalence.json", "summary.json"]}
    for name, key in [("overlay.csv", "overlay_sha256"), ("session_manifest.csv", "session_manifest_sha256"),
        ("source_manifest.json", "source_manifest_sha256")]:
        assert hashes[name] == summary[key]
    old = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3"
    accepted = json.loads((old / "input_manifest.json").read_text())
    actual_digests = {}
    def once(path):
        path = str(Path(path).resolve())
        if path not in actual_digests:
            actual_digests[path] = digest(path)
        return actual_digests[path]
    sources = {row["source_id"]: row for row in manifest["sources"]}
    assert len(sources) == 134
    for row in sources.values():
        path = Path(row["path"])
        assert accepted[str(path.relative_to(ROOT))] == row["sha256"] == once(path)
        assert path.name.endswith("_completed_minute_backtest.csv")
        assert "tqsdk_stage491_covered_key_full_session_backfill" in str(path)
    for row in manifest["daily_sources"]:
        path = Path(row["path"])
        assert accepted[str(path.relative_to(ROOT))] == row["sha256"] == once(path)
    protocol_amended = False
    for path, sha in manifest["input_sha256"].items():
        if once(path) != sha and Path(path).name == "20261017_2250_stage002_local_minute_coverage_protocol.md":
            amendment = json.loads((folder / "protocol_amendment_receipt.json").read_text())
            assert amendment["amendment_after_build"] is True and amendment["financial_replays"] == 0
            assert amendment["original_protocol_sha256"] == sha == summary["protocol_sha256"]
            assert once(folder / "protocol_used.md") == sha
            assert once(path) == amendment["amended_protocol_sha256"]
            protocol_amended = True
        else:
            assert once(path) == sha, path
    base_path = next(Path(path) for path in manifest["input_sha256"] if "full_minute_bars_stage861" in path)
    base_sha = once(base_path)
    assert base_sha == "5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189"
    mapping_path = next(Path(path) for path in manifest["input_sha256"] if "main_contract_mapping" in path)
    assert once(mapping_path) == accepted[str(mapping_path.relative_to(ROOT))]
    calendar = pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(mapping_path, usecols=["date"]).date.unique())))
    date_positions = {day: i for i, day in enumerate(calendar)}

    # Independent scalar session construction, applying the already frozen
    # product hours and 2020 night suspension. No implementation import.
    def grid(symbol, trade_day):
        day = pd.Timestamp(trade_day).normalize()
        i = date_positions[day]
        product = re.match(r"[A-Za-z]+", symbol).group()
        parts = [pd.date_range(day + pd.Timedelta(minutes=start), periods=count, freq="min")
            for start, count in [(540, 75), (630, 60), (810, 90)]]
        day_only = product in {"AP", "SM", "si", "lc", "lh"}
        if not day_only:
            assert i > 0
            prior = calendar[i - 1]
            gap = (day - prior).days
            active = gap == 1 or (prior.weekday() == 4 and day.weekday() == 0 and gap == 3)
            active = active and not (pd.Timestamp("2020-02-03") <= prior < pd.Timestamp("2020-05-06"))
            if active:
                count = 330 if product == "au" else 240 if product == "cu" else 120
                parts.insert(0, pd.date_range(prior + pd.Timedelta(hours=21), periods=count, freq="min"))
        return pd.DatetimeIndex(np.concatenate([p.values for p in parts])).sort_values()

    values = ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    base = pd.read_csv(base_path, usecols=["vt_symbol", "bar_datetime", *values], parse_dates=["bar_datetime"])
    overlay = pd.read_csv(folder / "overlay.csv", parse_dates=["bar_datetime"])
    sessions = pd.read_csv(folder / "session_manifest.csv").fillna("")
    quarantine = pd.read_csv(folder / "quarantine.csv").fillna("")
    assert not base.duplicated(["vt_symbol", "bar_datetime"]).any()
    assert not overlay.duplicated(["vt_symbol", "bar_datetime"]).any()
    base_keys = set(zip(base.vt_symbol, base.bar_datetime))
    added_keys = set(zip(overlay.vt_symbol, overlay.bar_datetime))
    assert not added_keys.intersection(base_keys)
    assert len(overlay) > 0 and len(overlay) == summary["added_minutes"]
    nums = overlay[values].to_numpy(dtype=float)
    assert np.isfinite(nums).all() and (overlay[["open", "high", "low", "close"]] > 0).all().all()
    assert (overlay[["volume", "open_oi", "close_oi"]] >= 0).all().all()
    assert overlay.low.le(overlay[["open", "close"]].min(axis=1)).all()
    assert overlay.high.ge(overlay[["open", "close"]].max(axis=1)).all()
    assert not sessions.duplicated(["vt_symbol", "trading_date"]).any()
    overlay_session_keys = set(zip(overlay.vt_symbol, overlay.trading_date))
    rejected_session_keys = set(zip(quarantine.vt_symbol, quarantine.trading_date))
    assert not overlay_session_keys.intersection(rejected_session_keys)
    accepted_sessions = sessions.loc[sessions.status.eq("accepted")]
    new_sessions = accepted_sessions.loc[pd.to_numeric(accepted_sessions.new_minutes).gt(0)]
    assert len(accepted_sessions) == summary["accepted_sessions"]
    assert len(quarantine) == summary["quarantined_sessions"]
    assert overlay_session_keys.issubset(set(zip(accepted_sessions.vt_symbol, accepted_sessions.trading_date)))

    source_bound_rows = 0
    complete_new_sessions = 0
    overlap_minutes = 0
    checked_open_oi = 0
    unknown_open_oi = 0
    max_daily_difference = 0.0
    sentinel = None
    daily_kinds = {}
    for source_id, source_sessions in new_sessions.groupby("source_id", sort=False):
        info = sources[source_id]
        raw = pd.read_csv(info["path"], parse_dates=["bar_datetime"])
        added = overlay.loc[overlay.source_id.eq(source_id)]
        if len(added):
            row_indices = added.source_row_number.to_numpy(dtype=int) - 2
            assert (row_indices >= 0).all() and (row_indices < len(raw)).all()
            original = raw.iloc[row_indices]
            assert original.vt_symbol.to_numpy().tolist() == added.vt_symbol.to_numpy().tolist()
            assert original.bar_datetime.to_numpy().tolist() == added.bar_datetime.to_numpy().tolist()
            assert np.allclose(original[values].to_numpy(float), added[values].to_numpy(float), rtol=1e-12, atol=1e-8)
            assert added.source_sha256.eq(info["sha256"]).all()
            source_bound_rows += len(added)
        daily_paths = set(source_sessions.daily_source_path)
        assert len(daily_paths) == 1
        symbol = str(source_sessions.iloc[0].vt_symbol)
        daily_path = Path(next(iter(daily_paths)))
        kinds = set(source_sessions.daily_source_kind)
        assert len(kinds) == 1
        kind = next(iter(kinds))
        daily_kinds[kind] = daily_kinds.get(kind, 0) + 1
        native, exchange = symbol.rsplit(".", 1)
        expected_csv = ROOT / "examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04" / exchange / (native + ".csv")
        if daily_path.suffix == ".db":
            assert kind == "accepted_exact_symbol_database_daily_open_oi_unknown"
            assert not expected_csv.exists(), "SQLite is allowed only when the exact legacy CSV is absent"
            assert daily_path.resolve() == (ROOT / ".vntrader/database.db").resolve()
            with sqlite3.connect(daily_path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
                connection.execute("PRAGMA query_only=ON")
                daily = pd.read_sql_query("SELECT substr(datetime,1,10) AS trade_date, open_price AS open, "
                    "high_price AS high, low_price AS low, close_price AS close, volume, open_interest AS close_oi "
                    "FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' "
                    "AND datetime>=? AND datetime<? ORDER BY datetime", connection,
                    params=[native, exchange, "2020-01-01", "2026-10-15"])
            daily["open_oi"] = np.nan
        else:
            assert kind == "accepted_exact_symbol_daily_csv"
            assert daily_path.resolve() == expected_csv.resolve()
            daily = pd.read_csv(daily_path)
        daily["trade_date"] = pd.to_datetime(daily.trade_date).dt.strftime("%Y-%m-%d")
        base_symbol = base.loc[base.vt_symbol.eq(symbol)]
        for session in source_sessions.itertuples(index=False):
            expected = grid(symbol, session.trading_date)
            assert len(expected) == session.expected_minutes
            original = raw.loc[raw.bar_datetime.isin(expected)].sort_values("bar_datetime")
            assert not original.bar_datetime.duplicated().any()
            assert original.bar_datetime.tolist() == expected.tolist()
            base_part = base_symbol.loc[base_symbol.bar_datetime.isin(expected)]
            added_part = added.loc[added.trading_date.eq(session.trading_date)]
            assert len(base_part) == session.base_overlap_minutes
            assert len(added_part) == session.new_minutes
            merged = pd.concat([base_part, added_part], ignore_index=True).sort_values("bar_datetime")
            assert merged.bar_datetime.tolist() == expected.tolist()
            assert np.allclose(merged[values].to_numpy(float), original[values].to_numpy(float), rtol=1e-12, atol=1e-8)
            target_daily = daily.loc[daily.trade_date.eq(session.trading_date)]
            assert len(target_daily) == 1
            target_daily = target_daily.iloc[0]
            aggregate = dict(open=float(merged.open.iloc[0]), high=float(merged.high.max()),
                low=float(merged.low.min()), close=float(merged.close.iloc[-1]), volume=float(merged.volume.sum()),
                close_oi=float(merged.close_oi.iloc[-1]), open_oi=float(merged.open_oi.iloc[0]))
            fields = ["open", "high", "low", "close", "volume", "close_oi"]
            if "open_oi" in target_daily and math.isfinite(float(target_daily.open_oi)):
                fields.append("open_oi")
                checked_open_oi += 1
                assert session.daily_open_oi_check == "checked"
            else:
                unknown_open_oi += 1
                assert session.daily_open_oi_check == "unknown"
            for key in fields:
                max_daily_difference = max(max_daily_difference, abs(aggregate[key] - float(target_daily[key])))
                assert math.isclose(aggregate[key], float(target_daily[key]), rel_tol=1e-12, abs_tol=1e-8)
            complete_new_sessions += int(len(added_part) > 0)
            overlap_minutes += len(base_part)
            if symbol == "rb2010.SHFE" and session.trading_date == "2020-05-18":
                sentinel = dict(minutes=len(expected), first=str(expected[0]), last=str(expected[-1]),
                    base_minutes=len(base_part), added_minutes=len(added_part), daily_fields_checked=fields,
                    aggregate=aggregate)
    assert source_bound_rows == len(overlay)
    assert sentinel and sentinel["minutes"] == 345 and sentinel["base_minutes"] == 0 and sentinel["added_minutes"] == 345
    a0 = LINE / "outputs/stage001_first_screen/A0_attempt2"
    anchors = pd.read_csv(a0 / "execution_anchor_requests.csv")
    scans = pd.read_csv(a0 / "minute_scan_requests.csv")
    assert len(anchors) == 535 and len(scans) == 501
    anchor_keys = {(str(row.vt_symbol), pd.Timestamp(row.expected_start)) for row in anchors.itertuples(index=False)}
    scanned_keys = set()
    for row in scans.itertuples(index=False):
        minutes = grid(str(row.vt_symbol), row.trading_date)
        suffix = minutes[minutes >= pd.Timestamp(row.requested_start)]
        assert len(suffix) == row.expected_bar_count == row.actual_bar_count and row.missing_bar_count == 0
        scanned_keys.update((str(row.vt_symbol), stamp) for stamp in suffix)
    reads = anchor_keys | scanned_keys
    assert not (added_keys & reads)
    assert reads.issubset(base_keys)
    equality = json.loads((folder / "a0_path_equivalence.json").read_text())
    assert equality["path_equivalent"] is True and equality["intersection_count"] == 0
    assert equality["distinct_actual_read_keys"] == len(reads)
    assert digest(base_path) == base_sha
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        status="independent_overlay_and_A0_path_equivalence_pass", source=str(folder), source_hashes=hashes,
        production_qualified=False, financial_engine_runs=0, A0_financial_replays=0, weekly_recalculations=0,
        source_files=134, source_bytes=sum(row["bytes"] for row in sources.values()),
        source_and_daily_SHA_match_accepted_A=True, mapping_SHA_match_accepted_A=True,
        protocol_amendment_after_build_explicit=protocol_amended,
        original_base_SHA_unchanged=base_sha, base_rows=len(base), overlay_rows=len(overlay),
        overlay_rows_bound_to_exact_source_row=source_bound_rows,
        new_key_overlap_with_base=0, accepted_sessions=len(accepted_sessions), sessions_adding_rows=complete_new_sessions,
        quarantined_sessions=len(quarantine), quarantined_reason_counts=quarantine.reason.value_counts().to_dict(),
        quarantined_session_overlay_intersection=0, accepted_base_overlap_minutes=overlap_minutes,
        daily_aggregate_scope="only accepted sessions contributing new overlay keys; unchanged old-only sessions not revalidated",
        daily_max_absolute_difference=max_daily_difference, daily_open_oi_checked_sessions=checked_open_oi,
        daily_open_oi_unknown_sessions=unknown_open_oi, target_rb2010_20200518=sentinel,
        daily_source_contract_counts=daily_kinds,
        a0_anchor_requests=len(anchors), a0_scan_requests=len(scans), a0_distinct_read_keys=len(reads),
        added_anchor_intersection=len(added_keys & anchor_keys), added_scan_intersection=len(added_keys & scanned_keys),
        original_read_keys_missing_from_base=0, A0_path_equivalent=True,
        equivalence_scope="all recorded canonical anchor and requested session suffix keys preserved; no A0 economic rerun, based on deterministic existing consumers",
        limit="certifies local accepted sessions and A0 invariance only; no guarantee that every new C0 or future strategy session is covered")
    destination = LINE / "outputs/stage002_independent_review"
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "overlay_independent_checks.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly-only", action="store_true")
    parser.add_argument("--account", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    if sum(bool(x) for x in (args.weekly_only, args.account, args.baseline, args.overlay)) != 1:
        parser.error("choose exactly one of --weekly-only, --account, --baseline or --overlay")
    result = weekly_audit() if args.weekly_only else account_audit(args.account) if args.account else baseline_audit(args.baseline) if args.baseline else overlay_audit(args.overlay)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
