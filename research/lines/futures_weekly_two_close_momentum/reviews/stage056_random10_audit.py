"""Independently validate Stage056 sampling and reproduce its frozen trade ledgers."""
import argparse
from collections import Counter
from datetime import datetime
from itertools import combinations
import json
from pathlib import Path
import random
from zoneinfo import ZoneInfo

import pandas as pd

from stage055_all_touch_audit import (
    STARTS, TAIL_CERT, check_manifest, completed_weeks, extend_raw_market,
    financial_metrics, load_json, reconcile, sha, table, verify_risk_table, check_values,
)

LINE = Path(__file__).resolve().parents[1]
FROZEN_GROUPS = LINE / "inputs/stage056_random10_groups.json"
DESIGN = LINE / "stages/20261105_1253_stage056_random10_design.md"
PARENT = LINE / "outputs/stage055_s21_all_touch_halfyear_20261104"
RESULT = LINE / "outputs/stage056_random10_touch_halfyear_20261104"


def check_groups():
    frozen = load_json(FROZEN_GROUPS)
    parent = load_json(PARENT / "receipt.json")
    products = parent["products"]
    assert len(products) == 21 and frozen["parent_products"] == products
    assert frozen["seed"] == 20261105
    rng = random.Random(frozen["seed"])
    expected = {}
    for index in range(1, 5):
        sample = set(rng.sample(sorted(products), 10))
        expected[f"G{index}"] = [product for product in products if product in sample]
    assert frozen["groups"] == expected
    assert frozen["stage055_manifest_sha256"] == sha(PARENT / "SHA256SUMS")
    assert frozen["stage055_audit_sha256"] == sha(LINE / "reviews/stage055_all_touch_audit.json")
    assert frozen["stage055_entrypoint_sha256"] == sha(LINE / "tools/stage055_s21_all_touch_halfyear.py")
    assert frozen["design_sha256"] == sha(DESIGN)
    assert frozen["starts"] == parent["starts"] == STARTS
    assert frozen["cutoff"] == parent["cutoff"] == "2026-11-04"
    assert frozen["capital"] == parent["capital"] == 150000
    assert frozen["attempted_runs"] == 96
    sets = [set(group) for group in expected.values()]
    coverage = {
        "covered_products": sorted(set.union(*sets)),
        "uncovered_products": sorted(set(products) - set.union(*sets)),
        "common_to_all_groups": sorted(set.intersection(*sets)),
        "pairwise_overlap": {
            f"{a}-{b}": len(set(expected[a]) & set(expected[b]))
            for a, b in combinations(expected, 2)
        },
        "product_group_counts": dict(Counter(product for group in expected.values() for product in group)),
    }
    assert len(coverage["covered_products"]) == 19
    assert coverage["uncovered_products"] == ["cu.SHFE", "hc.SHFE"]
    assert coverage["common_to_all_groups"] == ["p.DCE", "ru.SHFE", "ss.SHFE"]
    return frozen, parent, coverage


def audit_window(folder, start, products, market, weeks):
    configuration = load_json(folder / "inputs.json")
    parent_configuration = load_json(PARENT / start / "inputs.json")
    assert configuration == {**parent_configuration, "products": products}
    data = reconcile(folder, start, configuration, *market, *weeks)
    (
        marks, opening, cycles, pending, reversals, branches, delayed, risk,
        touch, locks, locked, carried, unavailable, waiting,
    ) = data
    assert not pending and not reversals and not locked
    performance, counts, zero_close = financial_metrics(folder, marks, opening, pending)
    decisions, equality = verify_risk_table(folder, risk, opening)
    fills = table(folder, "fills")
    assert set(fills["product"]) <= set(products)
    assert not fills.reason.eq("weekly_stop").any()
    observed = table(folder, "touch_stops")
    pd.testing.assert_frame_equal(
        pd.DataFrame(touch, columns=observed.columns), observed,
        check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
    )
    assert not observed.one_price.any()
    assert (observed.anchor_day.lt(observed.trigger_day) & observed.trigger_day.le(observed.date)).all()
    assert observed.trigger_day.lt(observed.date).equals(observed.reason.eq("touch_after_one_price"))
    for trigger in locks:
        matches = [
            event for event in touch
            if (event["cycle"], event["epoch"], event["trigger_day"])
            == (trigger["cycle"], trigger["epoch"], trigger["trigger_day"])
        ]
        assert len(matches) == 1 and matches[0]["date"] > trigger["trigger_day"]
    reasons = Counter(observed.reason)
    stats = {
        "stop_count": len(touch),
        "open_gap_count": reasons["touch_open_gap"],
        "intraday_count": reasons["touch_intraday"],
        "delayed_count": reasons["touch_after_one_price"],
        "locked_count": len(locks),
        "missing_bars": len(unavailable),
        "blocked_total": sum(value for (status, _), value in decisions.items() if status != "filled"),
        "nonpositive_equity_days": counts["nonpositive_days"],
        "minimum_equity": min(marks.equity.min(), opening.equity.min()),
    }
    cycle_rows = table(folder, "cycles")
    product_pnl = cycle_rows.groupby("product").net_pnl.sum().reindex(products, fill_value=0)
    assert abs(product_pnl.sum() - performance["net_pnl"]) < 1e-8
    return {
        "metrics": performance | stats,
        "ledger_counts": counts,
        "funding_decisions": decisions,
        "branches": branches,
        "touch_reasons": reasons,
        "product_pnl": product_pnl.to_dict(),
        "anchor_carry_days": len(carried),
        "waiting_days": len(waiting),
        "pending_at_cutoff": len(locked),
        "zero_close_days": zero_close,
    }


def check_metrics_row(observed, expected, label):
    assert set(observed.index) == set(expected), label
    for name, value in expected.items():
        check_values(observed[name], value, (label, name))


def attribution_rows(folder, products):
    cycles = table(folder, "cycles")
    fills = table(folder, "fills")
    rows = []
    for product in products:
        selected = cycles.loc[cycles["product"].eq(product)]
        closed = selected.loc[selected.exit_day.ne("")]
        rows.append({
            "product": product,
            "net_pnl": selected.net_pnl.sum(),
            "closed_pnl": closed.net_pnl.sum(),
            "terminal_pnl": selected.loc[selected.exit_day.eq(""), "net_pnl"].sum(),
            "closed_cycles": len(closed),
            "wins": int(closed.net_pnl.gt(0).sum()),
            "fills": int(fills["product"].eq(product).sum()),
        })
    return rows


def check_analysis(metrics):
    attribution = table(RESULT, "product_attribution")
    concentration = table(RESULT, "concentration")
    summary = table(RESULT, "group_summary")
    expected_attribution, expected_concentration = [], []
    frozen = load_json(FROZEN_GROUPS)
    for item in metrics.itertuples(index=False):
        group, start = item.group, item.calendar_start
        products = frozen["parent_products"] if group == "S21" else frozen["groups"][group]
        folder = PARENT / start if group == "S21" else RESULT / group / start
        values = attribution_rows(folder, products)
        check_values(sum(value["net_pnl"] for value in values), item.net_pnl, (group, start, "product sum"))
        expected_attribution.extend(dict(group=group, calendar_start=start, **value) for value in values)
        profits = sorted((value["net_pnl"] for value in values if value["net_pnl"] > 0), reverse=True)
        best = max(values, key=lambda value: value["net_pnl"])
        positive_total = sum(profits)
        expected_concentration.append({
            "group": group, "calendar_start": start,
            "largest_product": best["product"], "largest_product_pnl": best["net_pnl"],
            "positive_product_pnl": positive_total,
            "top1_positive_share_pct": 100 * sum(profits[:1]) / positive_total if positive_total else "",
            "top3_positive_share_pct": 100 * sum(profits[:3]) / positive_total if positive_total else "",
            "profitable_products": sum(value["net_pnl"] > 0 for value in values),
            "traded_products": sum(value["fills"] > 0 for value in values),
        })
    for actual, rows, name in (
        (attribution, expected_attribution, "attribution"),
        (concentration, expected_concentration, "concentration"),
    ):
        expected = pd.DataFrame(rows, columns=actual.columns)
        pd.testing.assert_frame_equal(
            expected, actual, check_dtype=False, check_exact=False, rtol=0, atol=1e-8, obj=name,
        )
    expected_summary = []
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
    pd.testing.assert_frame_equal(
        pd.DataFrame(expected_summary, columns=summary.columns), summary,
        check_dtype=False, check_exact=False, rtol=0, atol=1e-8, obj="group summary",
    )
    assert (len(attribution), len(concentration), len(summary)) == (1464, 120, 5)
    return {"product_attribution": len(attribution), "concentration": len(concentration), "group_summary": len(summary)}


def check_full_history_projection(groups):
    start = STARTS[0]
    baseline = PARENT / start
    assert table(baseline, "risk_sizing").executed_lots.eq(1).all()
    counts = {}
    for group, products in groups.items():
        folder = RESULT / group / start
        assert table(folder, "risk_sizing").executed_lots.eq(1).all()
        group_counts = {}
        for name in ("fills", "signals", "cycles", "gaps", "entry_filter", "week_body_filter", "four_up_blocks", "touch_stops"):
            expected = table(baseline, name)
            expected = expected.loc[expected["product"].isin(products)].drop(columns="cycle", errors="ignore")
            observed = table(folder, name).drop(columns="cycle", errors="ignore")
            pd.testing.assert_frame_equal(
                expected.reset_index(drop=True), observed.reset_index(drop=True),
                check_dtype=False, check_exact=True, obj=(group, name),
            )
            group_counts[name] = len(observed)
        parent_terminal = load_json(baseline / "terminal.json")
        child_terminal = load_json(folder / "terminal.json")
        expected_positions = {
            product: {key: value for key, value in position.items() if key != "cycle"}
            for product, position in parent_terminal["positions"].items() if product in products
        }
        actual_positions = {
            product: {key: value for key, value in position.items() if key != "cycle"}
            for product, position in child_terminal["positions"].items()
        }
        assert actual_positions == expected_positions
        for name in ("pending", "pending_reversals"):
            assert child_terminal[name] == {
                product: value for product, value in parent_terminal[name].items() if product in products
            }
        counts[group] = group_counts
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--certificate", type=Path)
    arguments = parser.parse_args()
    frozen, parent, coverage = check_groups()
    if arguments.freeze_only:
        print(json.dumps(coverage, indent=2))
        return
    manifests = {path.name: check_manifest(path) for path in (RESULT, PARENT)}
    receipt = load_json(RESULT / "receipt.json")
    for name in (
        "stage055_manifest_sha256", "stage055_audit_sha256", "stage055_entrypoint_sha256", "design_sha256",
    ):
        assert receipt[name] == frozen[name]
    assert receipt["group_design_sha256"] == sha(FROZEN_GROUPS)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage056_random10_touch.py")
    for name in (
        "stage054_entrypoint_sha256", "stage052_entrypoint_sha256", "engine_sha256", "market_sha256",
        "gate", "all_products_stop_rule",
    ):
        assert receipt[name] == parent[name], name
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    for stage in (52, 54):
        filename = f"stage{stage:03d}_" + ("s21_margin_gate.py" if stage == 52 else "s21_gold_touch_halfyear.py")
        assert receipt[f"stage{stage:03d}_entrypoint_sha256"] == sha(LINE / "tools" / filename)
    assert receipt["groups"] == frozen["groups"] and receipt["starts"] == STARTS
    assert (receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (96, 96, 0)
    assert receipt["control_validation_runs"] == 1
    assert receipt["capital"] == frozen["capital"] and receipt["cutoff"] == frozen["cutoff"]
    pins = receipt["market_sha256"] | load_json(PARENT / STARTS[0] / "inputs.json")["source_sha256"]
    assert len(pins) == 42 and all(sha(Path(path)) == digest for path, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == {*frozen["groups"], "validation_s21"}
    for group in frozen["groups"]:
        assert {path.name for path in (RESULT / group).iterdir()} == set(STARTS)
    for path in (PARENT / STARTS[0]).iterdir():
        assert path.read_bytes() == (RESULT / "validation_s21" / path.name).read_bytes(), path.name
    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    control = audit_window(RESULT / "validation_s21", STARTS[0], frozen["parent_products"], market, weeks)
    metrics = table(RESULT, "window_metrics")
    expected_keys = [(group, start) for group in ["S21", *frozen["groups"]] for start in STARTS]
    assert list(zip(metrics["group"], metrics.calendar_start)) == expected_keys
    metric_index = metrics.set_index(["group", "calendar_start"], verify_integrity=True)
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
        check_metrics_row(metrics.loc[(metrics["group"] == "S21") & metrics.calendar_start.eq(start)].iloc[0],
                          expected, ("S21", start))
    ledger_totals, funding_totals, touch_totals = Counter(), Counter(), Counter()
    per_group = {}
    initial_availability = {}
    dates, _, mains, symbols, _, _ = market
    first_date = next(day for day in dates if day >= STARTS[0])
    for group, products in frozen["groups"].items():
        initial_availability[group] = [
            product for product in products if symbols.get((first_date, mains.get((first_date, product))))
        ]
        group_totals, group_funding = Counter(), Counter()
        for start in STARTS:
            result = audit_window(RESULT / group / start, start, products, market, weeks)
            expected = {
                "group": group, "calendar_start": start,
                "first_session": next(day for day in dates if day >= start),
                "last_session": frozen["cutoff"], "days": result["ledger_counts"]["days"],
                **result["metrics"],
            }
            observed = metrics.loc[metrics["group"].eq(group) & metrics.calendar_start.eq(start)].iloc[0]
            check_metrics_row(observed, expected, (group, start))
            ledger_totals.update(result["ledger_counts"])
            group_totals.update(result["ledger_counts"])
            funding_totals.update(result["funding_decisions"])
            group_funding.update(result["funding_decisions"])
            touch_totals.update(result["touch_reasons"])
            print(group, start, result["metrics"]["equity"], result["metrics"]["return_pct"],
                  result["metrics"]["blocked_total"], flush=True)
        per_group[group] = {
            "ledger_rows": dict(group_totals),
            "funding_by_status_and_role": {f"{status}:{role}": count for (status, role), count in group_funding.items()},
        }
    aggregates = check_analysis(metrics)
    projection = check_full_history_projection(frozen["groups"])
    certificate = {
        "schema": "stage056_independent_random10_audit_v1", "verdict": "PASS_WITH_LIMITATIONS",
        "audited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "audit_method": "Replay all 96 subsets plus the S21 control using the Stage055 independent integer-cent state machine.",
        "audit_script_sha256": sha(Path(__file__)),
        "independent_state_machine_sha256": sha(LINE / "reviews/stage055_all_touch_audit.py"),
        "result_manifest_sha256": sha(RESULT / "SHA256SUMS"),
        "frozen_group_design_sha256": sha(FROZEN_GROUPS),
        "checked_manifests": manifests, "input_hashes": len(pins),
        "windows": {"fixed_attempted": 96, "completed_verified": 96, "unknown": 0},
        "additional_control_replays": 1, "control_ledger_rows": control["ledger_counts"],
        "sampling": coverage, "positive_main_products_on_20150105": initial_availability,
        "ledger_rows": dict(ledger_totals), "touch_exits": dict(touch_totals),
        "funding": {
            "decisions": sum(funding_totals.values()),
            "approved": sum(count for (status, _), count in funding_totals.items() if status == "filled"),
            "denied": sum(count for (status, _), count in funding_totals.items() if status != "filled"),
            "by_status_and_role": {f"{status}:{role}": count for (status, role), count in funding_totals.items()},
        },
        "aggregate_rows": {"window_metrics": len(metrics), **aggregates}, "by_group": per_group,
        "full_history_parent_projection": projection,
        "limitations": [
            "Four random groups overlap by 4 to 7 products. Their union covers 19 of the 21 parent products.",
            "All groups share p, ru and ss. No group contains cu or hc.",
            "Fixed one lot has different capital and risk exposure across products and differs from the 21-product total exposure.",
            "Early history has fewer than ten available group products because of actual listing and admitted market coverage.",
            "Funding rejections make portfolio state paths dependent on the chosen group.",
            "The 24 expanding windows overlap and four groups are insufficient for independent-sample confidence intervals.",
            "Daily OHLC stop execution, zero commissions and first non-one-price daily exit proxies remain bounded assumptions.",
            "The frozen parent universe and strategy were selected with historical knowledge.",
        ],
    }
    print("TOTALS", ledger_totals, "FUNDING", funding_totals, "TOUCH", touch_totals, flush=True)
    if arguments.certificate:
        with arguments.certificate.open("x") as file:
            json.dump(certificate, file, ensure_ascii=False, indent=2)
            file.write("\n")


if __name__ == "__main__":
    main()
