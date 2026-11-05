"""Independently replay both Stage053 metal variants and reconcile shared-funding effects."""
from collections import Counter
import json
from pathlib import Path

from stage040_s19_without_gold_audit import CAPITAL, LINE, TARGET, check_manifest, load_json, near, sha
from stage044_s19_daily_halfyear_audit import STARTS, financial_metrics
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import table
from stage048_s26_full_audit import TAIL_CERT, extend_raw_market
from stage049_s26_halfyear_audit import check_values
from stage052_s21_margin_gate_audit import GATE, RESULT as GOLD_CONTROL, reconcile, verify_risk_table

RESULT = LINE / "outputs/stage053_s21_silver_halfyear_20261104"
GOLD_CERT = LINE / "reviews/stage052_s21_margin_gate_audit.json"
GOLD = "au.SHFE"
SILVER = "ag.SHFE"
KINDS = ("fixed_entry", "reversal", "roll")


def replay_arm(folder, start, config, market, weeks):
    marks, opening, cycles, pending, conditional, branches, delayed, risk = reconcile(
        folder, start, config, *market, *weeks)
    performance, counts, zero_close = financial_metrics(folder, marks, opening, pending)
    statuses, equal = verify_risk_table(folder, risk, opening)
    day = table(folder, "daily")
    assert day.date.iat[-1] == TARGET and day.date.iat[0] >= start
    assert (day.iloc[0][["equity", "cash", "positions", "margin"]] == [CAPITAL, CAPITAL, 0, 0]).all()
    assert not pending and not conditional
    assert not table(folder, "gaps").date.eq(TARGET).any()
    fills = table(folder, "fills")
    assert fills.volume.eq(1).all() and fills.date.min() > day.date.iat[0] and fills.signal_day.min() >= day.date.iat[0]
    assert set(fills["product"]) <= set(config["products"])
    position_products = load_json(folder / "terminal.json")["positions"].keys()
    assert set(position_products) <= set(config["products"])
    close_free = (marks.equity - marks.margin).round(8)
    open_free = opening.free_equity.round(8)
    worst_open = opening.loc[open_free.idxmin()].to_dict()
    worst_close = day.loc[close_free.idxmin(), ["date", "equity", "margin", "positions"]].to_dict()
    worst_open["free_equity"] = float(open_free.min())
    worst_close.update(free_equity=float(close_free.min()), reason="close_mark")
    worst = min((worst_open, worst_close), key=lambda item: item["free_equity"])
    for key in ("equity", "margin"):
        worst[key] = round(float(worst[key]), 8)
    performance.update(
        nonpositive_equity_days=counts["nonpositive_days"], minimum_equity=min(marks.equity.min(), opening.equity.min())
    )
    by_product = table(folder, "cycles").groupby("product").net_pnl.sum().to_dict()
    assert set(by_product) <= set(config["products"])
    denied = {role: statuses["margin_below_one_lot", role] for role in KINDS}
    return performance, counts, statuses, equal, denied, worst, by_product, zero_close, day.date


def check_row(row, start, dates, gold, silver, gold_denied, silver_denied, silver_pnl):
    values = dict(first_session=dates.iat[0], last_session=TARGET, days=len(dates))
    values.update({f"gold_{key}": value for key, value in gold.items()})
    values.update({f"silver_{key}": value for key, value in silver.items()})
    values.update(
        gold_blocked_total=sum(gold_denied.values()), silver_blocked_total=sum(silver_denied.values()),
        silver_blocked_entry=silver_denied["fixed_entry"], silver_blocked_reversal=silver_denied["reversal"],
        silver_blocked_roll=silver_denied["roll"], silver_metal_net_pnl=silver_pnl,
    )
    for arm in ("gold", "silver"):
        assert {f"{arm}_{key}" for key in ("equity", "net_pnl", "return_pct", "max_dd_pct", "deficit_days",
                                            "nonpositive_equity_days", "max_shortfall", "fills",
                                            "closed_cycles", "blocked_total")} <= set(row.index)
    for field, actual in row.items():
        assert field in values, (start, field, "unexpected summary field")
        check_values(actual, values[field], (start, field))


def audit():
    manifests = {folder.name: check_manifest(folder) for folder in (RESULT, GOLD_CONTROL)}
    receipt = load_json(RESULT / "receipt.json")
    control_receipt = load_json(GOLD_CONTROL / "receipt.json")
    control_cert = load_json(GOLD_CERT)
    assert control_cert["verdict"] == "PASS_WITH_LIMITATIONS"
    assert control_cert["manifest_sha256"] == sha(GOLD_CONTROL / "SHA256SUMS")
    assert receipt["stage052_manifest_sha256"] == sha(GOLD_CONTROL / "SHA256SUMS")
    assert receipt["stage052_audit_sha256"] == sha(GOLD_CERT)
    assert receipt["stage052_entrypoint_sha256"] == sha(LINE / "tools/stage052_s21_margin_gate.py")
    assert receipt["removed"] == GOLD and receipt["added"] == SILVER
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage053_s21_silver_halfyear.py")
    design = list((LINE / "stages").glob("*_stage053_*design.md"))
    assert len(design) == 1 and receipt["design_sha256"] == sha(design[0])
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["starts"], receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (STARTS, 24, 24, 0)
    assert (receipt["cutoff"], receipt["capital"], receipt["gate"]) == (TARGET, CAPITAL, GATE)
    assert receipt["market_sha256"] == control_receipt["market_sha256"]
    original_products = control_receipt["products"]
    products = [SILVER if product == GOLD else product for product in original_products]
    assert receipt["products"] == products and len(products) == 21
    assert set(original_products) - set(products) == {GOLD} and set(products) - set(original_products) == {SILVER}
    assert [product for product in original_products if product != GOLD] == [
        product for product in products if product != SILVER]
    prior_config = load_json(GOLD_CONTROL / STARTS[0] / "inputs.json")
    assert prior_config["fixed_one_margin_gate"] == GATE
    assert prior_config["inputs_sha256"] == receipt["market_sha256"]
    pins = prior_config["inputs_sha256"] | prior_config["source_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)
    gold_table = table(GOLD_CONTROL, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = table(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == gold_table.index.tolist() == STARTS

    tail = load_json(TAIL_CERT)
    assert tail["verdict"] == "PASS_TAIL_INPUT_ADMISSION"
    assert tail["target"] == TARGET and SILVER in tail["verified_mains"]
    assert all(sha(Path(name)) == digest for name, digest in tail["sha256"].items())
    market = extend_raw_market(tail)
    weeks = completed_weeks(market[1], market[4])
    all_counts = {arm: Counter() for arm in ("gold", "silver")}
    all_statuses = {arm: Counter() for arm in ("gold", "silver")}
    all_equalities = {arm: Counter() for arm in ("gold", "silver")}
    proof = {row["start"]: row for row in control_cert["windows"]}
    windows = []
    for start in STARTS:
        gold_dir, silver_dir = GOLD_CONTROL / start, RESULT / start
        gold_config = load_json(gold_dir / "inputs.json")
        silver_config = load_json(silver_dir / "inputs.json")
        assert gold_config == {**prior_config, "start": start}
        assert silver_config == {**gold_config, "products": products}
        ledgers = {
            "gold": replay_arm(gold_dir, start, gold_config, market, weeks),
            "silver": replay_arm(silver_dir, start, silver_config, market, weeks),
        }
        for arm, (_, counts, statuses, equal, *_rest) in ledgers.items():
            all_counts[arm].update(counts)
            all_statuses[arm].update(statuses)
            all_equalities[arm].update(equal)

        gold, _, _, _, gold_denied, gold_worst, gold_pnl, gold_zero, gold_dates = ledgers["gold"]
        silver, _, _, _, silver_denied, silver_worst, silver_pnl, silver_zero, silver_dates = ledgers["silver"]
        assert silver_dates.equals(gold_dates)
        assert GOLD not in silver_pnl and SILVER not in gold_pnl
        near(gold["gold_net_pnl"], gold_pnl.get(GOLD, 0))
        near(silver["gold_net_pnl"], 0)
        gold_metal = float(gold_pnl.get(GOLD, 0))
        silver_metal = float(silver_pnl.get(SILVER, 0))
        common = set(original_products) & set(products)
        other_changes = {product: float(silver_pnl.get(product, 0) - gold_pnl.get(product, 0))
                         for product in sorted(common)}
        shared = sum(other_changes.values())
        near(silver["net_pnl"] - gold["net_pnl"], silver_metal - gold_metal + shared)
        check_row(combined.loc[start], start, silver_dates, gold, silver, gold_denied, silver_denied, silver_metal)
        baseline = gold_table.loc[start]
        for key, value in gold.items():
            check_values(baseline[f"gated_{key}"], value, (start, "gold source", key))
        assert int(baseline.blocked_total) == sum(gold_denied.values()) == sum(proof[start]["denied"].values())
        near(proof[start]["gated_worst"]["free_equity"], gold_worst["free_equity"])
        record = dict(
            start=start, gold_equity=float(gold["equity"]), silver_equity=float(silver["equity"]),
            gold_metal_net_pnl=gold_metal, silver_metal_net_pnl=silver_metal,
            direct_metal_pnl_difference=silver_metal-gold_metal, shared_product_pnl_difference=shared,
            shared_product_pnl_differences=other_changes, gold_denied=gold_denied, silver_denied=silver_denied,
            gold_deficit_days=gold["deficit_days"], silver_deficit_days=silver["deficit_days"],
            gold_nonpositive_days=gold["nonpositive_equity_days"], silver_nonpositive_days=silver["nonpositive_equity_days"],
            gold_zero_equity_closes=gold_zero, silver_zero_equity_closes=silver_zero,
            gold_worst=gold_worst, silver_worst=silver_worst,
            gold_drawdown=float(gold["max_dd_pct"]), silver_drawdown=float(silver["max_dd_pct"]),
        )
        windows.append(record)
        print(start, "equity", gold["equity"], silver["equity"], "gaps", gold["deficit_days"], silver["deficit_days"],
              "denied", sum(gold_denied.values()), sum(silver_denied.values()), flush=True)

    report = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_sha256=sha(RESULT / "SHA256SUMS"), manifest_entries=manifests, pinned_inputs=len(pins),
        removed=GOLD, added=SILVER, checked_rows={arm: dict(counts) for arm, counts in all_counts.items()},
        checked_gate_decisions={arm: {
            status: {kind: counters[status, kind] for kind in KINDS} for status in ("filled", "margin_below_one_lot")
        } for arm, counters in all_statuses.items()},
        exact_funding_equalities={arm: dict(counters) for arm, counters in all_equalities.items()},
        funding_deficit_windows={arm: sum(row[f"{arm}_deficit_days"] > 0 for row in windows) for arm in ledgers},
        nonpositive_equity_windows={arm: sum(row[f"{arm}_nonpositive_days"] > 0 for row in windows) for arm in ledgers},
        higher_silver_final_equity=sum(row["silver_equity"] > row["gold_equity"] for row in windows),
        lower_silver_final_equity=sum(row["silver_equity"] < row["gold_equity"] for row in windows),
        better_silver_drawdown=sum(row["silver_drawdown"] > row["gold_drawdown"] for row in windows),
        windows=windows,
        limitations=[
            "Margin gate applies to new and replacement opening legs. Existing positions can produce shortfalls.",
            "Changing the metal changes shared buying power and can change trades in unchanged products.",
            "One-lot static margin, daily opening proxies, no forced liquidation or queue model, and zero commission.",
            "Half-year windows overlap; gold and silver are compared within the same retrospective histories.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in report.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
