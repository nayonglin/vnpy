"""Replace gold with silver in Stage052 and replay the frozen half-year grid."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path

import pandas as pd

import stage052_s21_margin_gate as parent

base, prior, LINE = parent.base, parent.prior, parent.LINE
GOLD = LINE / "outputs/stage052_s21_margin_gate_20261104"
GOLD_SHA = "40fc03ceb24a07d65be55c5aefe993fcc16c6cd7ccb51c55f3ae359974520051"
AUDIT = LINE / "reviews/stage052_s21_margin_gate_audit.json"
AUDIT_SHA = "d9c741e9979559ec52c1eac46cf7318cab2beb436e30136f56ef07e586fcc2e4"
DESIGN = LINE / "stages/20261104_2122_stage053_s21_silver_halfyear_design.md"
REMOVED, ADDED = "au.SHFE", "ag.SHFE"


def replay(folder, start, market, engine, reference):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    path = folder / "inputs.json"
    inputs = prior.read_json(path)
    inputs["fixed_one_margin_gate"] = parent.GATE
    gold = GOLD / start
    if inputs != {**prior.read_json(gold / "inputs.json"), "products": market[0]}:
        raise ValueError(f"configuration drift: {start}")
    path.write_text(json.dumps(inputs, indent=2) + "\n")

    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    if (not daily.date.equals(pd.read_csv(gold / "daily.csv").date)
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or not fills["product"].isin(market[0]).all()
            or parent.opening_checks(fills, opening) != (0, 0)):
        raise ValueError(f"calendar, universe or funding drift: {start}")

    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    expected = sizing.free_cash.ge((sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8))
    if (not admitted.equals(expected) or not sizing.requested_lots.eq(1).all()
            or not sizing.status.eq(admitted.map({True: "filled", False: "margin_below_one_lot"})).all()):
        raise ValueError(f"incorrect funding decision: {start}")
    cols = ["date", "product", "contract", "epoch", "signal_day", "side", "price"]
    pd.testing.assert_frame_equal(
        sizing.loc[admitted, cols].reset_index(drop=True),
        fills.loc[fills.reason.isin(parent.OPEN_REASONS), cols].reset_index(drop=True),
        check_dtype=False, rtol=0, atol=1e-8, obj=f"admitted opening fills: {start}",
    )
    blocked = sizing.loc[~admitted]
    if blocked.kind.eq("roll").sum() != fills.reason.eq("roll_funding_exit").sum():
        raise ValueError(f"roll close accounting mismatch: {start}")
    terminal = prior.read_json(folder / "terminal.json")
    if any((base.TARGET, pos["epoch"]) not in market[5] for pos in terminal["positions"].values()):
        raise ValueError(f"missing final-day valuation: {start}")
    summary_path = folder / "summary.json"
    summary = prior.read_json(summary_path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    cycles = pd.read_csv(folder / "cycles.csv")
    return dict(calendar_start=start, **reference,
                **{f"silver_{key}": value for key, value in metrics.items()},
                silver_metal_net_pnl=cycles.loc[cycles["product"].eq(ADDED), "net_pnl"].sum(),
                silver_blocked_total=len(blocked), silver_blocked_entry=int(blocked.kind.eq("fixed_entry").sum()),
                silver_blocked_reversal=int(blocked.kind.eq("reversal").sum()),
                silver_blocked_roll=int(blocked.kind.eq("roll").sum()))


def run(output):
    base.verify_manifest(GOLD, GOLD_SHA)
    frozen = prior.read_json(GOLD / "receipt.json")
    if (base.portfolio.sha(AUDIT) != AUDIT_SHA
            or base.portfolio.sha(Path(parent.__file__)) != frozen["entrypoint_sha256"]
            or frozen["gate"] != parent.GATE):
        raise ValueError("frozen Stage052 engine or review changed")
    reference = prior.read_json(parent.baseline.parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full = prior.add_tail((reference["products"], *expanded[1:]), original, prior.TAIL)
    hashes = {str(path): digest for path, digest in full[-1].items()}
    control_products = frozen["products"]
    products = [ADDED if product == REMOVED else product for product in control_products]
    if (hashes != frozen["market_sha256"] or control_products.count(REMOVED) != 1
            or ADDED in control_products or ADDED not in full[0] or len(set(products)) != 21):
        raise ValueError("unexpected frozen market or replacement universe")
    market = (products, *full[1:])

    data = pd.read_csv(GOLD / "window_metrics.csv", keep_default_na=False).set_index("calendar_start")
    if tuple(data.index) != prior.STARTS or tuple(frozen["starts"]) != prior.STARTS:
        raise ValueError("frozen start grid changed")
    keys = [key for key in data if key.startswith("gated_")]
    controls = data[["first_session", "last_session", "days", "blocked_total", *keys]].rename(
        columns={**{key: key.replace("gated_", "gold_", 1) for key in keys},
                 "blocked_total": "gold_blocked_total"})
    output.mkdir(parents=True)
    engine = parent.gated_engine()
    rows = [replay(output / start, start, market, engine, controls.loc[start].to_dict())
            for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage052_manifest_sha256=GOLD_SHA, stage052_audit_sha256=AUDIT_SHA,
        stage052_entrypoint_sha256=frozen["entrypoint_sha256"], engine_sha256=prior.ENGINE_SHA,
        design_sha256=base.portfolio.sha(DESIGN), entrypoint_sha256=base.portfolio.sha(Path(__file__)),
        market_sha256=hashes, cutoff=base.TARGET, capital=base.CAPITAL, products=products,
        removed=REMOVED, added=ADDED, gate=parent.GATE, starts=prior.STARTS,
        attempted_runs=len(prior.STARTS), completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
