"""Replay Stage051 with a fixed one-lot opening margin check."""
import argparse
from contextlib import redirect_stdout
from inspect import getsource
from io import StringIO
import json
from pathlib import Path

import pandas as pd

import stage051_s21_halfyear as baseline

base, prior, LINE = baseline.base, baseline.prior, baseline.LINE
S21 = LINE / "outputs/stage051_s21_halfyear_20261104"
S21_SHA = "05398bb32a68fed4710fcaf3919752fd421006ecf85cf29d46f05433c1f262e1"
AUDIT = LINE / "reviews/stage051_s21_halfyear_audit.json"
AUDIT_SHA = "f0c60a3317320764ea5b311c2ceae23bc539b3c2b87c9ca4e46e9d42aeb3f1ee"
DESIGN = LINE / "stages/20261104_2101_stage052_s21_margin_gate_design.md"
GATE = "available_equity_ge_one_lot_margin_and_entry_cost"
OPEN_REASONS = ("entry", "roll_open")


def gated_engine():
    # Keep the pinned research engine and previously frozen entry points intact.
    engine = base.portfolio
    path = Path(engine.__file__)
    if engine.sha(path) != prior.ENGINE_SHA:
        raise ValueError("frozen strategy changed")
    source = getsource(engine.run)
    replacements = (
        ('volume = funding_order(day, product, bar, "entry", signal_day, side, stop) if cash_risk else 1',
         'kind = "reversal" if entry_kind == "reversal" else "fixed_entry"\n'
         '                    volume = funding_order(day, product, bar, kind, signal_day, side, stop, 1)'),
        ('def open_funding(day):\n        value = margin = 0\n        for pos in positions.values():',
         'def open_funding(day, closed_product=None):\n        value = margin = 0\n'
         '        for product, pos in positions.items():\n'
         '            if product == closed_product:\n                continue'),
        ('        equity, margin, free = open_funding(day)\n        symbol = bar.vt_symbol',
         '        equity, margin, free = open_funding(day, product if kind == "roll" else None)\n'
         '        symbol = bar.vt_symbol'),
        ('                        if cash_risk:\n                            positions.pop(product)\n'
         '                            volume = funding_order(day, product, new, "roll", previous_day, position.side, stop, volume)',
         '                        volume = funding_order(day, product, new, "roll", previous_day, position.side, stop, volume)'),
        ('                            fills[-1]["reason"] = "roll_funding_exit"',
         '                            positions.pop(product)\n'
         '                            fills[-1]["reason"] = "roll_funding_exit"'),
        ('    if cash_risk:\n        pd.DataFrame(sizing).to_csv(out / "risk_sizing.csv", index=False)',
         '    pd.DataFrame(sizing).to_csv(out / "risk_sizing.csv", index=False)'),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError("margin gate source anchor changed")
        source = source.replace(old, new)
    namespace = {**vars(engine), "INITIAL": base.CAPITAL}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def opening_checks(fills, opening):
    before = opening.groupby("date").free_equity.shift()
    entries = opening.reason.isin(OPEN_REASONS)
    if entries.sum() != fills.reason.isin(OPEN_REASONS).sum() or before[entries].isna().any():
        raise ValueError("opening ledger did not match fills")
    return int((entries & before.lt(0)).sum()), int((entries & opening.free_equity.lt(0)).sum())


def replay(folder, start, market, engine, reference):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    control = S21 / start
    input_path = folder / "inputs.json"
    inputs = prior.read_json(input_path)
    if inputs != prior.read_json(control / "inputs.json"):
        raise ValueError(f"configuration drift: {start}")
    inputs["fixed_one_margin_gate"] = GATE
    input_path.write_text(json.dumps(inputs, indent=2) + "\n")
    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    old_fills = pd.read_csv(control / "fills.csv")
    old_opening = pd.read_csv(control / "opening_funding.csv")
    old_already_negative, old_unaffordable = opening_checks(old_fills, old_opening)
    if (not daily.date.equals(pd.read_csv(control / "daily.csv").date)
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or opening_checks(fills, opening) != (0, 0)):
        raise ValueError(f"cash or calendar reconciliation failed: {start}")

    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    expected = sizing.free_cash.ge((sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8))
    if (not admitted.equals(expected) or not sizing.requested_lots.eq(1).all()
            or not sizing.status.eq(admitted.map({True: "filled", False: "margin_below_one_lot"})).all()):
        raise ValueError(f"incorrect funding decision: {start}")
    cols = ["date", "product", "contract", "epoch", "signal_day", "side", "price"]
    pd.testing.assert_frame_equal(
        sizing.loc[admitted, cols].reset_index(drop=True),
        fills.loc[fills.reason.isin(OPEN_REASONS), cols].reset_index(drop=True),
        check_dtype=False, rtol=0, atol=1e-8, obj=f"admitted opening fills: {start}",
    )
    blocked = sizing.loc[~admitted]
    if blocked.kind.eq("roll").sum() != fills.reason.eq("roll_funding_exit").sum():
        raise ValueError(f"roll close accounting mismatch: {start}")
    if blocked.empty:
        for name in ("daily.csv", "fills.csv", "cycles.csv", "signals.csv", "terminal.json"):
            if (folder / name).read_bytes() != (control / name).read_bytes():
                raise ValueError(f"path changed without a margin rejection: {start}/{name}")

    path = folder / "summary.json"
    summary = prior.read_json(path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return dict(calendar_start=start, **reference,
                **{f"gated_{key}": value for key, value in metrics.items()},
                old_open_fills_with_negative_free_before=old_already_negative,
                old_open_fills_with_negative_free_after=old_unaffordable,
                blocked_total=len(blocked), blocked_entry=int(blocked.kind.eq("fixed_entry").sum()),
                blocked_reversal=int(blocked.kind.eq("reversal").sum()),
                blocked_roll=int(blocked.kind.eq("roll").sum()))


def run(output):
    base.verify_manifest(S21, S21_SHA)
    if base.portfolio.sha(AUDIT) != AUDIT_SHA:
        raise ValueError("parent audit changed")
    source = prior.read_json(S21 / "receipt.json")
    s26 = prior.read_json(baseline.parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full = prior.add_tail((s26["products"], *expanded[1:]), original, prior.TAIL)
    market_hashes = {str(path): digest for path, digest in full[-1].items()}
    if (market_hashes != source["market_sha256"]
            or set(source["products"]) != set(original[0]) | set(baseline.ADDED)):
        raise ValueError("frozen market or S21 universe changed")
    market = (source["products"], *full[1:])
    data = pd.read_csv(S21 / "window_metrics.csv", keep_default_na=False)
    keys = [key for key in data if key.startswith("s21_")]
    controls = data[["calendar_start", "first_session", "last_session", "days", *keys]].set_index("calendar_start")
    if tuple(controls.index) != prior.STARTS:
        raise ValueError("frozen starts changed")
    engine = gated_engine()
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market, engine, controls.loc[start].to_dict())
            for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage051_manifest_sha256=S21_SHA, stage051_audit_sha256=AUDIT_SHA,
        engine_sha256=prior.ENGINE_SHA, design_sha256=base.portfolio.sha(DESIGN),
        entrypoint_sha256=base.portfolio.sha(Path(__file__)), market_sha256=market_hashes,
        cutoff=base.TARGET, capital=base.CAPITAL, products=market[0], gate=GATE,
        starts=prior.STARTS, attempted_runs=len(prior.STARTS), completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
