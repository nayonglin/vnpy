"""Four predeclared random ten-product subsets of the frozen Stage055 strategy."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import random

import pandas as pd

import stage055_s21_all_touch_halfyear as parent

base, prior, LINE = parent.base, parent.prior, parent.LINE
BASELINE = LINE / "outputs/stage055_s21_all_touch_halfyear_20261104"
FROZEN = LINE / "inputs/stage056_random10_groups.json"
FROZEN_SHA = "5a305423f1c2f9d5a8612210956d2a408551ed6203aca5bf218566d53e5f3202"
DESIGN = LINE / "stages/20261105_1253_stage056_random10_design.md"


def frozen_market():
    if base.portfolio.sha(FROZEN) != FROZEN_SHA:
        raise ValueError("predeclared grouping changed")
    design = prior.read_json(FROZEN)
    base.verify_manifest(BASELINE, design["stage055_manifest_sha256"])
    receipt = prior.read_json(BASELINE / "receipt.json")
    if (base.portfolio.sha(LINE / "reviews/stage055_all_touch_audit.json") != design["stage055_audit_sha256"]
            or base.portfolio.sha(Path(parent.__file__)) != design["stage055_entrypoint_sha256"]
            or base.portfolio.sha(DESIGN) != design["design_sha256"]
            or receipt["products"] != design["parent_products"]
            or receipt["starts"] != design["starts"]):
        raise ValueError("frozen parent or design changed")
    rng = random.Random(design["seed"])
    for products in design["groups"].values():
        selected = set(rng.sample(sorted(receipt["products"]), 10))
        if products != [product for product in receipt["products"] if product in selected]:
            raise ValueError("group not equal to the predeclared random draw")

    reference = prior.read_json(parent.gold.parent.baseline.parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full = prior.add_tail((reference["products"], *expanded[1:]), original, prior.TAIL)
    hashes = {str(path): digest for path, digest in full[-1].items()}
    if (hashes != receipt["market_sha256"] or tuple(receipt["starts"]) != prior.STARTS
            or receipt["cutoff"] != base.TARGET or receipt["capital"] != base.CAPITAL):
        raise ValueError("market, starts, cutoff or capital changed")
    return design, receipt, (receipt["products"], *full[1:])


def replay(folder, start, market, engine, reconstruct):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = prior.read_json(folder / "inputs.json")
    inputs["fixed_one_margin_gate"] = parent.gold.parent.GATE
    inputs["all_products_stop_rule"] = parent.RULE
    expected = {**prior.read_json(BASELINE / start / "inputs.json"), "products": market[0]}
    if inputs != expected:
        raise ValueError(f"configuration changed beyond product selection: {folder}")
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")

    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    stops = pd.read_csv(folder / "touch_stops.csv")
    opening = reconstruct(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    if (daily.date.tolist() != [day for day in market[1] if day >= start]
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or daily.date.iat[-1] != base.TARGET or not fills.volume.eq(1).all()
            or not fills["product"].isin(market[0]).all()
            or parent.gold.parent.opening_checks(fills, opening) != (0, 0)
            or fills.reason.eq("weekly_stop").any() or stops.one_price.any()
            or not (stops.anchor_day.lt(stops.trigger_day) & stops.trigger_day.le(stops.date)).all()
            or not stops.trigger_day.lt(stops.date).equals(stops.reason.eq(parent.DELAYED))):
        raise ValueError(f"invalid calendar, cold start, product, sizing or stop: {folder}")
    columns = ["date", "product", "contract", "epoch", "cycle", "price", "stop", "reason", "one_price"]
    stop_fills = fills.loc[fills.reason.isin((parent.OPEN_GAP, parent.INTRADAY, parent.DELAYED))]
    pd.testing.assert_frame_equal(stops[columns], stop_fills[columns].reset_index(drop=True),
                                  check_dtype=False, rtol=0, atol=1e-8)
    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    required = (sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8)
    if (not admitted.equals(sizing.free_cash.ge(required))
            or not sizing.requested_lots.eq(1).all()
            or not sizing["product"].isin(market[0]).all()):
        raise ValueError(f"invalid opening funding decision: {folder}")
    summary = prior.read_json(folder / "summary.json")
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    gaps = pd.read_csv(folder / "gaps.csv")
    return dict(
        first_session=daily.date.iat[0], last_session=daily.date.iat[-1], days=len(daily), **metrics,
        stop_count=len(stops), open_gap_count=int(stops.reason.eq(parent.OPEN_GAP).sum()),
        intraday_count=int(stops.reason.eq(parent.INTRADAY).sum()),
        delayed_count=int(stops.reason.eq(parent.DELAYED).sum()),
        locked_count=int(gaps.reason.eq("touch_trigger_one_price").sum()),
        missing_bars=int(gaps.reason.eq("touch_stop_day_unavailable").sum()),
        blocked_total=int((~admitted).sum()),
    )


def product_metrics(folder, products):
    cycles = pd.read_csv(folder / "cycles.csv", keep_default_na=False)
    fills = pd.read_csv(folder / "fills.csv")
    result = []
    for product in products:
        selected = cycles.loc[cycles["product"].eq(product)]
        closed = selected.loc[selected.exit_day.ne("")]
        result.append(dict(
            product=product, net_pnl=selected.net_pnl.sum(), closed_pnl=closed.net_pnl.sum(),
            terminal_pnl=selected.loc[selected.exit_day.eq(""), "net_pnl"].sum(),
            closed_cycles=len(closed), wins=int(closed.net_pnl.gt(0).sum()),
            fills=int(fills["product"].eq(product).sum()),
        ))
    return result


def write_analysis(output, design, rows):
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output / "window_metrics.csv", index=False)
    attribution, concentrations = [], []
    for row in rows:
        arm, start = row["group"], row["calendar_start"]
        products = design["parent_products"] if arm == "S21" else design["groups"][arm]
        folder = BASELINE / start if arm == "S21" else output / arm / start
        values = product_metrics(folder, products)
        if abs(sum(value["net_pnl"] for value in values) - row["net_pnl"]) > 1e-7:
            raise ValueError(f"product PnL not conserved: {arm}/{start}")
        attribution.extend(dict(group=arm, calendar_start=start, **value) for value in values)
        positive = sorted((v["net_pnl"] for v in values if v["net_pnl"] > 0), reverse=True)
        total_positive = sum(positive)
        best = max(values, key=lambda value: value["net_pnl"])
        concentrations.append(dict(
            group=arm, calendar_start=start, largest_product=best["product"],
            largest_product_pnl=best["net_pnl"], positive_product_pnl=total_positive,
            top1_positive_share_pct=100 * sum(positive[:1]) / total_positive if total_positive else None,
            top3_positive_share_pct=100 * sum(positive[:3]) / total_positive if total_positive else None,
            profitable_products=sum(value["net_pnl"] > 0 for value in values),
            traded_products=sum(value["fills"] > 0 for value in values),
        ))
    pd.DataFrame(attribution).to_csv(output / "product_attribution.csv", index=False)
    pd.DataFrame(concentrations).to_csv(output / "concentration.csv", index=False)
    summary = []
    for arm, windows in metrics.groupby("group", sort=False):
        full = windows.loc[windows.calendar_start.eq(design["starts"][0])].iloc[0]
        summary.append(dict(
            group=arm, positive_windows=int(windows.return_pct.gt(0).sum()), windows=len(windows),
            minimum_return_pct=windows.return_pct.min(), maximum_return_pct=windows.return_pct.max(),
            median_return_pct=windows.return_pct.median(), worst_max_dd_pct=windows.max_dd_pct.min(),
            median_max_dd_pct=windows.max_dd_pct.median(), deficit_windows=int(windows.deficit_days.gt(0).sum()),
            nonpositive_equity_windows=int(windows.nonpositive_equity_days.gt(0).sum()),
            full_equity=full.equity, full_return_pct=full.return_pct, full_max_dd_pct=full.max_dd_pct,
            full_sharpe=full.sharpe, full_closed_cycles=full.closed_cycles, full_fills=full.fills,
            full_win_rate_pct=full.win_rate_pct, full_slippage=full.slippage,
        ))
    pd.DataFrame(summary).to_csv(output / "group_summary.csv", index=False)


def run(output):
    design, frozen, market = frozen_market()
    output.mkdir(parents=True)
    engine, reconstruct = parent.build_engine()
    start = design["starts"][0]
    replay(output / "validation_s21", start, market, engine, reconstruct)
    for name in ("daily.csv", "fills.csv", "cycles.csv", "signals.csv", "terminal.json", "touch_stops.csv",
                 "risk_sizing.csv", "opening_funding.csv", "inputs.json", "summary.json"):
        if (output / "validation_s21" / name).read_bytes() != (BASELINE / start / name).read_bytes():
            raise ValueError(f"21-product control replay changed: {name}")
    print("21-product control byte-for-byte PASS", flush=True)

    reference = pd.read_csv(BASELINE / "window_metrics.csv", keep_default_na=False)
    rows = []
    for row in reference.to_dict("records"):
        stats = {key.removeprefix("all_touch_"): value for key, value in row.items() if key.startswith("all_touch_")}
        rows.append(dict(group="S21", calendar_start=row["calendar_start"],
                         **{key: row[key] for key in ("first_session", "last_session", "days")}, **stats))
    for arm, products in design["groups"].items():
        subset = (products, *market[1:])
        for start in design["starts"]:
            stats = replay(output / arm / start, start, subset, engine, reconstruct)
            rows.append(dict(group=arm, calendar_start=start, **stats))
            print(arm, start, stats["equity"], stats["return_pct"], stats["closed_cycles"], flush=True)
    write_analysis(output, design, rows)
    receipt = dict(
        schema="stage056_random10_touch_v1", groups=design["groups"], starts=design["starts"],
        capital=base.CAPITAL, cutoff=base.TARGET, attempted_runs=design["attempted_runs"],
        completed_runs=len(rows) - len(design["starts"]), unknown_runs=0, control_validation_runs=1,
        group_design_sha256=FROZEN_SHA, design_sha256=design["design_sha256"],
        stage055_manifest_sha256=design["stage055_manifest_sha256"],
        stage055_audit_sha256=design["stage055_audit_sha256"],
        stage055_entrypoint_sha256=design["stage055_entrypoint_sha256"],
        stage054_entrypoint_sha256=frozen["stage054_entrypoint_sha256"],
        stage052_entrypoint_sha256=frozen["stage052_entrypoint_sha256"], engine_sha256=frozen["engine_sha256"],
        market_sha256=frozen["market_sha256"], gate=frozen["gate"],
        all_products_stop_rule=frozen["all_products_stop_rule"],
        entrypoint_sha256=base.portfolio.sha(Path(__file__)),
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
