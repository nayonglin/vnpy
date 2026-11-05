"""Independently reproduce the approved D10 half-year-start strategy study."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from stage040_s19_without_gold_audit import cents
from stage056_random10_audit import (
    STARTS, TAIL_CERT, PARENT, attribution_rows, audit_window, check_manifest,
    check_metrics_row, completed_weeks, extend_raw_market, load_json, sha, table,
)

LINE = Path(__file__).resolve().parents[1]
RESULT = LINE / "outputs/stage059_diverse10_touch_halfyear_20261104"
SELECTION = LINE / "outputs/stage058_diverse10_20261103"
DESIGN = LINE / "stages/20261105_1315_stage059_diverse10_halfyear_design.md"


def check_analysis(metrics, selected):
    expected_attribution, expected_concentration, expected_summary = [], [], []
    parent_products = load_json(PARENT / "receipt.json")["products"]
    for row in metrics.itertuples(index=False):
        products = parent_products if row.group == "S21" else selected
        folder = PARENT / row.calendar_start if row.group == "S21" else RESULT / "D10" / row.calendar_start
        values = attribution_rows(folder, products)
        assert abs(sum(item["net_pnl"] for item in values) - row.net_pnl) < 1e-7
        expected_attribution.extend(
            dict(group=row.group, calendar_start=row.calendar_start, **value) for value in values
        )
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
        ("product_attribution", expected_attribution, 744),
        ("concentration", expected_concentration, 48),
        ("group_summary", expected_summary, 2),
    ):
        observed = table(RESULT, name)
        expected = pd.DataFrame(rows, columns=observed.columns)
        pd.testing.assert_frame_equal(
            expected, observed, check_dtype=False, check_exact=False, rtol=0, atol=1e-8, obj=name,
        )
        assert len(observed) == count
    paired = pd.read_csv(RESULT / "paired_comparison.csv", header=[0, 1], index_col=0)
    assert paired.index.tolist() == STARTS
    assert set(paired.columns) == {
        (metric, group) for metric in ("return_pct", "max_dd_pct", "closed_cycles") for group in ("S21", "D10")
    }
    indexed = metrics.set_index(["group", "calendar_start"], verify_integrity=True)
    for start in STARTS:
        for metric, group in paired.columns:
            assert abs(paired.at[start, (metric, group)] - indexed.at[(group, start), metric]) < 1e-8
    return {"window_metrics": len(metrics), "product_attribution": 744, "concentration": 48, "group_summary": 2,
            "paired_comparison_rows": len(paired)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    args = parser.parse_args()
    manifests = {folder.name: check_manifest(folder) for folder in (RESULT, PARENT, SELECTION)}
    receipt = load_json(RESULT / "receipt.json")
    parent = load_json(PARENT / "receipt.json")
    selection = load_json(SELECTION / "selection.json")
    assert receipt["stage058_manifest_sha256"] == sha(SELECTION / "SHA256SUMS")
    assert receipt["stage058_audit_sha256"] == sha(LINE / "reviews/stage058_diverse10_audit.json")
    assert receipt["stage056_entrypoint_sha256"] == sha(LINE / "tools/stage056_random10_touch.py")
    assert receipt["stage055_manifest_sha256"] == sha(PARENT / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(DESIGN)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage059_diverse10_halfyear.py")
    assert receipt["stage055_entrypoint_sha256"] == parent["entrypoint_sha256"] == sha(LINE / "tools/stage055_s21_all_touch_halfyear.py")
    for name in ("stage054_entrypoint_sha256", "stage052_entrypoint_sha256", "engine_sha256",
                 "market_sha256", "gate", "all_products_stop_rule", "starts", "capital", "cutoff"):
        assert receipt[name] == parent[name], name
    assert receipt["selected"] == selection["selected"] == sorted(selection["selected"])
    selected = receipt["selected"]
    assert len(selected) == len(set(selected)) == 10 and "ni.SHFE" in selected
    assert (receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"], receipt["control_validation_runs"]) == (24, 24, 0, 1)
    assert receipt["starts"] == STARTS and receipt["cutoff"] == "2026-11-04" and receipt["capital"] == 150000
    pins = receipt["market_sha256"] | load_json(PARENT / STARTS[0] / "inputs.json")["source_sha256"]
    assert len(pins) == 42 and all(sha(Path(path)) == digest for path, digest in pins.items())
    assert {p.name for p in RESULT.iterdir() if p.is_dir()} == {"validation_s21", "D10"}
    assert {p.name for p in (RESULT / "D10").iterdir()} == set(STARTS)
    for path in (PARENT / STARTS[0]).iterdir():
        assert path.read_bytes() == (RESULT / "validation_s21" / path.name).read_bytes(), path.name
    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    calendar, _, mains, symbols, epochs, settings = market
    nickel = [(day, bar) for (day, epoch), bar in epochs.items() if epoch.startswith("SHFE.NI.")]
    first_nickel_day = min(day for day, _ in nickel)
    assert first_nickel_day == "2015-03-27"
    assert mains["2026-11-04", "ni.SHFE"] == "ni2612.SHFE"
    latest = symbols["2026-11-04", "ni2612.SHFE"]
    tail_certificate = load_json(TAIL_CERT)
    admitted = next(
        item for item in tail_certificate["admitted"]
        if item["symbol"] == "ni2612.SHFE" and item["date"] == "2026-11-04"
    )
    assert tuple(cents(admitted[field]) for field in ("open", "high", "low", "close")) == (
        latest.op, latest.high, latest.low, latest.close,
    )
    assert admitted["volume"] == 154081 and latest.close == 11690000
    control = audit_window(RESULT / "validation_s21", STARTS[0], parent["products"], market, weeks)
    metrics = table(RESULT, "window_metrics")
    assert list(zip(metrics["group"], metrics.calendar_start)) == [
        (group, start) for group in ("S21", "D10") for start in STARTS
    ]
    parent_metrics = table(PARENT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    for start in STARTS:
        expected = {
            "group": "S21", "calendar_start": start,
            **{name: parent_metrics.at[start, name] for name in ("first_session", "last_session", "days")},
            **{
                name.removeprefix("all_touch_"): value
                for name, value in parent_metrics.loc[start].items() if name.startswith("all_touch_")
            },
        }
        row = metrics.loc[metrics["group"].eq("S21") & metrics.calendar_start.eq(start)].iloc[0]
        check_metrics_row(row, expected, ("S21", start))
    counts, funding, reasons, branches = Counter(), Counter(), Counter(), Counter()
    nickel_stop_cases, windows = {}, {}
    first_nickel_fill = None
    for start in STARTS:
        folder = RESULT / "D10" / start
        result = audit_window(folder, start, selected, market, weeks)
        expected = {
            "group": "D10", "calendar_start": start,
            "first_session": next(day for day in calendar if day >= start),
            "last_session": receipt["cutoff"], "days": result["ledger_counts"]["days"],
            **result["metrics"],
        }
        row = metrics.loc[metrics["group"].eq("D10") & metrics.calendar_start.eq(start)].iloc[0]
        check_metrics_row(row, expected, ("D10", start))
        counts.update(result["ledger_counts"])
        funding.update(result["funding_decisions"])
        reasons.update(result["touch_reasons"])
        branches.update(result["branches"])
        fills = table(folder, "fills")
        ni_fills = fills.loc[fills["product"].eq("ni.SHFE")]
        assert ni_fills.date.ge(first_nickel_day).all()
        if not ni_fills.empty:
            day = ni_fills.date.min()
            first_nickel_fill = min(first_nickel_fill or day, day)
        stops = table(folder, "touch_stops")
        ni_stops = stops.loc[stops["product"].eq("ni.SHFE") & stops.trigger_day.between("2022-01-01", "2022-12-31")]
        for stop in ni_stops.to_dict("records"):
            key = (stop["epoch"], stop["trigger_day"], stop["date"], stop["side"], stop["stop"], stop["price"])
            record = nickel_stop_cases.setdefault(key, {**stop, "windows": []})
            record["windows"].append(start)
        windows[start] = {
            **{name: float(value) if isinstance(value, (int, float)) else value for name, value in result["metrics"].items()},
            "nickel_net_pnl": float(result["product_pnl"].get("ni.SHFE", 0)),
            "gold_net_pnl": float(result["product_pnl"].get("au.SHFE", 0)),
            "anchor_carry_days": result["anchor_carry_days"], "waiting_days": result["waiting_days"],
            "pending_at_cutoff": result["pending_at_cutoff"],
        }
        print(start, row.equity, row.return_pct, row.max_dd_pct, row.blocked_total,
              "Ni", windows[start]["nickel_net_pnl"], flush=True)
    aggregate_counts = check_analysis(metrics, selected)
    audit = {
        "schema": "stage059_independent_approved_diverse10_audit_v1", "verdict": "PASS_WITH_LIMITATIONS",
        "audited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "audit_script_sha256": sha(Path(__file__)),
        "independent_window_auditor_sha256": sha(LINE / "reviews/stage056_random10_audit.py"),
        "independent_state_machine_sha256": sha(LINE / "reviews/stage055_all_touch_audit.py"),
        "result_manifest_sha256": sha(RESULT / "SHA256SUMS"), "checked_manifests": manifests,
        "market_and_strategy_input_hashes": len(pins),
        "windows": {"fixed_attempted": 24, "completed_verified": 24, "unknown": 0},
        "additional_control_replays": 1, "control_ledger_rows": control["ledger_counts"],
        "selected": selected, "ledger_rows": dict(counts), "touch_exits": dict(reasons),
        "funding": {
            "decisions": sum(funding.values()),
            "approved": sum(value for (status, _), value in funding.items() if status == "filled"),
            "denied": sum(value for (status, _), value in funding.items() if status != "filled"),
            "by_status_and_role": {f"{status}:{role}": value for (status, role), value in funding.items()},
        },
        "branch_counts": dict(branches), "aggregate_rows": aggregate_counts,
        "nickel": {
            "first_admitted_physical_day": first_nickel_day, "first_fill_across_windows": first_nickel_fill,
            "latest_main": latest.symbol, "latest_epoch": latest.epoch, "latest_open": latest.op / 100,
            "latest_close": latest.close / 100, "latest_volume": admitted["volume"],
            "2022_stop_cases": list(nickel_stop_cases.values()),
        },
        "by_window": windows,
        "limitations": [
            "The fixed D10 pool was selected with correlations known on November 3, 2026, and is not historical PIT/OOS evidence.",
            "The 24 expanding windows overlap and are not 24 independent economic samples.",
            "Fixed one lot has unequal risk and margin, and pool changes alter subsequent funding paths.",
            "Daily OHLC touch prices, first non-one-price daily exit proxies and zero commissions limit execution confidence.",
            "Opening margin admission does not model broker liquidation or intraday margin requirements.",
        ],
    }
    print("TOTALS", counts, "FUNDING", funding, "REASONS", reasons, "BRANCHES", branches, flush=True)
    if args.certificate:
        with args.certificate.open("x") as file:
            json.dump(audit, file, ensure_ascii=False, indent=2, default=lambda item: item.item())
            file.write("\n")


if __name__ == "__main__":
    main()
