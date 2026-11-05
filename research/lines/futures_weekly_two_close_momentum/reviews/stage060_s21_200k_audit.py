"""Independently audit the fixed-one-lot S21 capital change to 200,000 yuan."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from types import FunctionType
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from stage055_all_touch_audit import (
    STARTS, TAIL_CERT, check_manifest, completed_weeks, extend_raw_market,
    financial_metrics, load_json, reconcile, sha, table, verify_risk_table,
)
from stage056_random10_audit import PARENT, audit_window, attribution_rows, check_metrics_row

LINE = Path(__file__).resolve().parents[1]
RESULT = LINE / "outputs/stage060_s21_200k_touch_halfyear_20261104"
DESIGN = LINE / "stages/20261105_1322_stage060_s21_200k_design.md"
CAPITAL = 200000


def capital_clone(function):
    namespace = {**function.__globals__, "CAPITAL": CAPITAL}
    copied = FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
    copied.__kwdefaults__ = function.__kwdefaults__
    assert function.__globals__["CAPITAL"] == 150000
    assert copied.__globals__["CAPITAL"] == CAPITAL
    return copied


def audit_200k_window(folder, start, market, weeks):
    configuration = load_json(folder / "inputs.json")
    baseline = load_json(PARENT / start / "inputs.json")
    assert configuration == {**baseline, "initial": CAPITAL}
    independent_reconcile = capital_clone(reconcile)
    independent_financial_metrics = capital_clone(financial_metrics)
    assert "CAPITAL" not in verify_risk_table.__code__.co_names
    data = independent_reconcile(folder, start, configuration, *market, *weeks)
    (
        marks, opening, cycles, pending, reversals, branches, delayed, risk,
        touch, locks, locked, carry, unavailable, waiting,
    ) = data
    assert not pending and not reversals and not locked
    performance, counts, zero_close = independent_financial_metrics(folder, marks, opening, pending)
    decisions, equalities = verify_risk_table(folder, risk, opening)
    assert all(request["requested_lots"] == 1 for request in risk)
    fills = table(folder, "fills")
    assert set(fills["product"]) <= set(configuration["products"])
    assert not fills.reason.eq("weekly_stop").any()
    assert (marks.iloc[0][["equity", "cash", "positions", "margin"]] == [CAPITAL, CAPITAL, 0, 0]).all()
    assert opening.iloc[0].equity == CAPITAL and opening.iloc[0].free_equity == CAPITAL
    observed_stops = table(folder, "touch_stops")
    pd.testing.assert_frame_equal(
        pd.DataFrame(touch, columns=observed_stops.columns), observed_stops,
        check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
    )
    assert not observed_stops.one_price.any()
    assert observed_stops.trigger_day.lt(observed_stops.date).equals(observed_stops.reason.eq("touch_after_one_price"))
    assert (observed_stops.anchor_day.lt(observed_stops.trigger_day) & observed_stops.trigger_day.le(observed_stops.date)).all()
    for trigger in locks:
        matches = [event for event in touch if (event["cycle"], event["epoch"], event["trigger_day"])
                   == (trigger["cycle"], trigger["epoch"], trigger["trigger_day"])]
        assert len(matches) == 1 and matches[0]["date"] > trigger["trigger_day"]
    reasons = Counter(observed_stops.reason)
    stats = {
        "stop_count": len(touch), "open_gap_count": reasons["touch_open_gap"],
        "intraday_count": reasons["touch_intraday"], "delayed_count": reasons["touch_after_one_price"],
        "locked_count": len(locks), "missing_bars": len(unavailable),
        "blocked_total": sum(count for (status, _), count in decisions.items() if status != "filled"),
        "nonpositive_equity_days": counts["nonpositive_days"],
        "minimum_equity": min(marks.equity.min(), opening.equity.min()),
    }
    assert reconcile.__globals__["CAPITAL"] == financial_metrics.__globals__["CAPITAL"] == 150000
    return {
        "metrics": performance | stats, "ledger_counts": counts,
        "funding": decisions, "branches": branches, "touch_reasons": reasons,
        "anchor_carry_days": len(carry), "waiting_days": len(waiting), "zero_close_days": zero_close,
    }


def check_capital_path(start):
    before, after = PARENT / start, RESULT / "S21_20w" / start
    same = (before / "fills.csv").read_bytes() == (after / "fills.csv").read_bytes()
    parent_risk, child_risk = table(before, "risk_sizing"), table(after, "risk_sizing")
    both_without_rejection = parent_risk.executed_lots.eq(1).all() and child_risk.executed_lots.eq(1).all()
    assert same or not both_without_rejection, start
    parent_summary, child_summary = load_json(before / "summary.json"), load_json(after / "summary.json")
    if same:
        for name in ("signals", "cycles", "gaps", "entry_filter", "week_body_filter", "four_up_blocks", "touch_stops", "annual"):
            assert (before / f"{name}.csv").read_bytes() == (after / f"{name}.csv").read_bytes(), (start, name)
        assert load_json(before / "terminal.json") == load_json(after / "terminal.json")
        old, new = table(before, "daily"), table(after, "daily")
        assert old.date.equals(new.date)
        np.testing.assert_allclose(new.equity - old.equity, 50000, rtol=0, atol=1e-6)
        np.testing.assert_allclose(new.cash - old.cash, 50000, rtol=0, atol=1e-6)
        stable = ["position_value", "margin", "positions", "cumulative_slippage", "cumulative_commission", "net_pnl"]
        np.testing.assert_allclose(new[stable], old[stable], rtol=0, atol=1e-6)
        old_open, new_open = table(before, "opening_funding"), table(after, "opening_funding")
        pd.testing.assert_frame_equal(
            old_open[["date", "fill_sequence", "product", "reason", "positions"]],
            new_open[["date", "fill_sequence", "product", "reason", "positions"]],
            check_dtype=False, check_exact=True,
        )
        np.testing.assert_allclose(new_open[["equity", "free_equity"]] - old_open[["equity", "free_equity"]],
                                   50000, rtol=0, atol=1e-6)
        np.testing.assert_allclose(new_open.margin, old_open.margin, rtol=0, atol=1e-6)
        assert abs(child_summary["net_pnl"] - parent_summary["net_pnl"]) < 1e-7
        assert abs(child_summary["return_pct"] - parent_summary["return_pct"] * 0.75) < 1e-9
    return {
        "same_trade_path": same, "both_without_funding_rejection": bool(both_without_rejection),
        "baseline_denied": int(parent_risk.executed_lots.eq(0).sum()),
        "candidate_denied": int(child_risk.executed_lots.eq(0).sum()),
        "net_pnl_delta": child_summary["net_pnl"] - parent_summary["net_pnl"],
    }


def check_analysis(metrics, products, paths):
    expected_attribution, expected_concentration, expected_summary = [], [], []
    for row in metrics.itertuples(index=False):
        folder = PARENT / row.calendar_start if row.group == "S21" else RESULT / "S21_20w" / row.calendar_start
        values = attribution_rows(folder, products)
        assert abs(sum(item["net_pnl"] for item in values) - row.net_pnl) < 1e-7
        expected_attribution.extend(dict(group=row.group, calendar_start=row.calendar_start, **value) for value in values)
        profits = sorted((item["net_pnl"] for item in values if item["net_pnl"] > 0), reverse=True)
        total_profit = sum(profits)
        best = max(values, key=lambda item: item["net_pnl"])
        expected_concentration.append({
            "group": row.group, "calendar_start": row.calendar_start,
            "largest_product": best["product"], "largest_product_pnl": best["net_pnl"],
            "positive_product_pnl": total_profit,
            "top1_positive_share_pct": sum(profits[:1]) * 100 / total_profit if total_profit else "",
            "top3_positive_share_pct": sum(profits[:3]) * 100 / total_profit if total_profit else "",
            "profitable_products": sum(item["net_pnl"] > 0 for item in values),
            "traded_products": sum(item["fills"] > 0 for item in values),
        })
    for group, windows in metrics.groupby("group", sort=False):
        first = windows.loc[windows.calendar_start.eq(STARTS[0])].iloc[0]
        expected_summary.append({
            "group": group, "positive_windows": int(windows.return_pct.gt(0).sum()), "windows": len(windows),
            "minimum_return_pct": windows.return_pct.min(), "maximum_return_pct": windows.return_pct.max(),
            "median_return_pct": windows.return_pct.median(), "worst_max_dd_pct": windows.max_dd_pct.min(),
            "median_max_dd_pct": windows.max_dd_pct.median(),
            "deficit_windows": int(windows.deficit_days.gt(0).sum()),
            "nonpositive_equity_windows": int(windows.nonpositive_equity_days.gt(0).sum()),
            "full_equity": first.equity, "full_return_pct": first.return_pct,
            "full_max_dd_pct": first.max_dd_pct, "full_sharpe": first.sharpe,
            "full_closed_cycles": first.closed_cycles, "full_fills": first.fills,
            "full_win_rate_pct": first.win_rate_pct, "full_slippage": first.slippage,
        })
    for name, rows, count in (
        ("product_attribution", expected_attribution, 1008),
        ("concentration", expected_concentration, 48),
        ("group_summary", expected_summary, 2),
    ):
        observed = table(RESULT, name)
        pd.testing.assert_frame_equal(
            pd.DataFrame(rows, columns=observed.columns), observed,
            check_dtype=False, check_exact=False, rtol=0, atol=1e-8, obj=name,
        )
        assert len(observed) == count
    paired = pd.read_csv(RESULT / "paired_comparison.csv", header=[0, 1], index_col=0)
    assert paired.index.tolist() == STARTS
    assert set(paired.columns) == {
        (metric, group) for metric in ("net_pnl", "return_pct", "max_dd_pct", "closed_cycles", "deficit_days")
        for group in ("S21", "S21_20w")
    }
    indexed = metrics.set_index(["group", "calendar_start"], verify_integrity=True)
    for start in STARTS:
        for metric, group in paired.columns:
            assert abs(paired.at[start, (metric, group)] - indexed.at[(group, start), metric]) < 1e-8
    expected_paths = []
    for start in STARTS:
        before, after = indexed.loc[("S21", start)], indexed.loc[("S21_20w", start)]
        expected_paths.append({
            "calendar_start": start, "same_fills": paths[start]["same_trade_path"],
            **{f"{name}_delta": after[name] - before[name] for name in ("net_pnl", "equity", "return_pct", "max_dd_pct")},
        })
    observed_paths = table(RESULT, "path_comparison")
    pd.testing.assert_frame_equal(
        pd.DataFrame(expected_paths, columns=observed_paths.columns), observed_paths,
        check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
    )
    return {"window_metrics": len(metrics), "product_attribution": 1008, "concentration": 48,
            "group_summary": 2, "paired_comparison_rows": len(paired), "path_comparison_rows": len(observed_paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()
    manifests = {folder.name: check_manifest(folder) for folder in (RESULT, PARENT)}
    receipt, parent = load_json(RESULT / "receipt.json"), load_json(PARENT / "receipt.json")
    assert receipt["schema"] == "stage060_s21_200k_halfyear_v1"
    assert receipt["stage055_manifest_sha256"] == sha(PARENT / "SHA256SUMS")
    assert receipt["stage056_entrypoint_sha256"] == sha(LINE / "tools/stage056_random10_touch.py")
    assert receipt["design_sha256"] == sha(DESIGN)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage060_s21_200k_halfyear.py")
    assert receipt["stage055_entrypoint_sha256"] == parent["entrypoint_sha256"] == sha(LINE / "tools/stage055_s21_all_touch_halfyear.py")
    for name in ("stage054_entrypoint_sha256", "stage052_entrypoint_sha256", "engine_sha256",
                 "market_sha256", "gate", "all_products_stop_rule", "starts", "cutoff", "products"):
        assert receipt[name] == parent[name], name
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    for stage, suffix in ((52, "s21_margin_gate"), (54, "s21_gold_touch_halfyear")):
        assert receipt[f"stage{stage:03d}_entrypoint_sha256"] == sha(LINE / f"tools/stage{stage:03d}_{suffix}.py")
    assert (receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"], receipt["control_validation_runs"]) == (24, 24, 0, 1)
    assert receipt["starts"] == STARTS and receipt["cutoff"] == "2026-11-04"
    assert receipt["capital"] == CAPITAL and receipt["baseline_capital"] == parent["capital"] == 150000
    products = receipt["products"]
    assert len(products) == len(set(products)) == 21
    pins = receipt["market_sha256"] | load_json(PARENT / STARTS[0] / "inputs.json")["source_sha256"]
    assert len(pins) == 42 and all(sha(Path(path)) == digest for path, digest in pins.items())
    assert {p.name for p in RESULT.iterdir() if p.is_dir()} == {"validation_s21", "S21_20w"}
    assert {p.name for p in (RESULT / "S21_20w").iterdir()} == set(STARTS)
    for path in (PARENT / STARTS[0]).iterdir():
        assert path.read_bytes() == (RESULT / "validation_s21" / path.name).read_bytes(), path.name
    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    calendar = market[0]
    control = audit_window(RESULT / "validation_s21", STARTS[0], products, market, weeks)
    metrics = table(RESULT, "window_metrics")
    assert list(zip(metrics["group"], metrics.calendar_start)) == [
        (group, start) for group in ("S21", "S21_20w") for start in STARTS
    ]
    parent_metrics = table(PARENT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    for start in STARTS:
        expected = {
            "group": "S21", "calendar_start": start,
            **{name: parent_metrics.at[start, name] for name in ("first_session", "last_session", "days")},
            **{name.removeprefix("all_touch_"): value for name, value in parent_metrics.loc[start].items()
               if name.startswith("all_touch_")},
        }
        row = metrics.loc[metrics["group"].eq("S21") & metrics.calendar_start.eq(start)].iloc[0]
        check_metrics_row(row, expected, ("S21", start))
    counts, funding, reasons, branches = Counter(), Counter(), Counter(), Counter()
    windows, paths = {}, {}
    for start in STARTS:
        folder = RESULT / "S21_20w" / start
        result = audit_200k_window(folder, start, market, weeks)
        expected = {
            "group": "S21_20w", "calendar_start": start,
            "first_session": next(day for day in calendar if day >= start),
            "last_session": receipt["cutoff"], "days": result["ledger_counts"]["days"],
            **result["metrics"],
        }
        row = metrics.loc[metrics["group"].eq("S21_20w") & metrics.calendar_start.eq(start)].iloc[0]
        check_metrics_row(row, expected, ("S21_20w", start))
        counts.update(result["ledger_counts"])
        funding.update(result["funding"])
        reasons.update(result["touch_reasons"])
        branches.update(result["branches"])
        paths[start] = check_capital_path(start)
        windows[start] = {
            **result["metrics"], "anchor_carry_days": result["anchor_carry_days"],
            "waiting_days": result["waiting_days"], **paths[start],
        }
        print(start, row.equity, row.return_pct, row.max_dd_pct, row.blocked_total,
              "same_path", paths[start]["same_trade_path"], "pnl_delta", paths[start]["net_pnl_delta"], flush=True)
    aggregate_counts = check_analysis(metrics, products, paths)
    candidate = metrics.loc[metrics["group"].eq("S21_20w")]
    audit = {
        "schema": "stage060_independent_s21_200k_audit_v1", "verdict": "PASS_WITH_LIMITATIONS",
        "audited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "audit_script_sha256": sha(Path(__file__)),
        "independent_150k_auditor_sha256": sha(LINE / "reviews/stage056_random10_audit.py"),
        "independent_state_machine_sha256": sha(LINE / "reviews/stage055_all_touch_audit.py"),
        "independent_financial_metrics_sha256": sha(LINE / "reviews/stage044_s19_daily_halfyear_audit.py"),
        "result_manifest_sha256": sha(RESULT / "SHA256SUMS"), "checked_manifests": manifests,
        "market_and_strategy_input_hashes": len(pins),
        "windows": {"fixed_attempted": 24, "completed_verified": 24, "unknown": 0},
        "capital": CAPITAL, "baseline_capital": 150000,
        "additional_control_replays": 1, "control_ledger_rows": control["ledger_counts"],
        "products": products, "ledger_rows": dict(counts), "touch_exits": dict(reasons),
        "funding": {
            "decisions": sum(funding.values()),
            "approved": sum(value for (status, _), value in funding.items() if status == "filled"),
            "denied": sum(value for (status, _), value in funding.items() if status != "filled"),
            "by_status_and_role": {f"{status}:{role}": value for (status, role), value in funding.items()},
        },
        "branch_counts": dict(branches), "aggregate_rows": aggregate_counts,
        "capital_paths": {
            "unchanged_trade_path_windows": sum(item["same_trade_path"] for item in paths.values()),
            "changed_trade_path_windows": sum(not item["same_trade_path"] for item in paths.values()),
            "nominal_pnl_lower_windows": sum(item["net_pnl_delta"] < 0 for item in paths.values()),
            "nominal_pnl_higher_windows": sum(item["net_pnl_delta"] > 0 for item in paths.values()),
            "nominal_pnl_unchanged_windows": sum(item["net_pnl_delta"] == 0 for item in paths.values()),
            "funding_deficit_windows": int(candidate.deficit_days.gt(0).sum()),
            "funding_deficit_window_days": int(candidate.deficit_days.sum()),
        },
        "by_window": windows,
        "confidence": {
            "offline_accounting_and_frozen_rule_consistency": "high",
            "real_execution_or_future_profitability": "not established",
        },
        "limitations": [
            "Only initial capital changed; fixed one lot did not become equal-risk or dynamic sizing.",
            "The 24 expanding windows overlap and are not 24 independent economic samples.",
            "Higher starting capital changes margin admission and later trades; nominal PnL is not monotonic in capital.",
            "Percentage return and drawdown change with capital even on identical nominal trade paths.",
            "Frozen pool and strategy retain their historical selection bias; these are not PIT/OOS results.",
            "Daily OHLC touches, first non-one-price daily exit proxies and zero commissions limit execution confidence.",
            "Opening margin admission does not model broker liquidation or intraday margin requirements.",
        ],
    }
    print("TOTALS", counts, "FUNDING", funding, "REASONS", reasons, "BRANCHES", branches, flush=True)
    print("CAPITAL_PATHS", audit["capital_paths"], flush=True)
    if args.certificate:
        with args.certificate.open("x") as file:
            json.dump(audit, file, ensure_ascii=False, indent=2, default=lambda item: item.item())
            file.write("\n")


if __name__ == "__main__":
    main()
