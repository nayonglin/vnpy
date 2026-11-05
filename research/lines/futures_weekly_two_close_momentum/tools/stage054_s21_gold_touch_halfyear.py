"""Gold-only price-touch stop on the frozen margin-gated S21 engine."""
import argparse
from contextlib import redirect_stdout
from inspect import getsource
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage053_s21_silver_halfyear as silver

parent, base, prior, LINE = silver.parent, silver.base, silver.prior, silver.LINE
GOLD = silver.GOLD
DESIGN = LINE / "stages/20261105_1202_stage054_gold_touch_design.md"
PRODUCT = "au.SHFE"
RULE = "previous_completed_physical_week_touch_daily_ohlc_proxy"
OPEN_GAP, INTRADAY = "gold_touch_open_gap", "gold_touch_intraday"
STOP_COLUMNS = ("date", "product", "contract", "epoch", "cycle", "side",
                "anchor_day", "stop", "open", "high", "low", "price", "reason", "one_price")


def touch_price(side, stop, bar, *, opening_only=False):
    if side * (bar.open - stop) <= 0:
        return bar.open
    extreme = bar.low if side == 1 else bar.high
    return stop if not opening_only and side * (extreme - stop) <= 0 else None


STOP_HELPER = '''
    gold_stop_anchors = {}
    gold_stop_events = []

    def check_gold_stop(day, index, *, opening_only):
        pos = positions.get(GOLD_PRODUCT)
        if pos is None:
            return
        bar = by_epoch.get((day, pos.epoch))
        reference = weekly(pos.epoch, index - 1)
        key = pos.cycle, pos.epoch
        if reference:
            stop = reference.low if pos.side == 1 else reference.high
            gold_stop_anchors[key] = (reference.week_end.isoformat(), float(stop))
        anchor = gold_stop_anchors.get(key)
        if anchor is None:
            raise ValueError(f"missing first gold stop anchor: {day}/{pos.epoch}")
        if bar is None:
            if not opening_only:
                gaps.append((day, GOLD_PRODUCT, pos.symbol, "gold_stop_day_unavailable"))
            return
        anchor_day, stop = anchor
        price = gold_touch_price(pos.side, stop, bar, opening_only=opening_only)
        if price is None:
            return
        reason = GOLD_OPEN_GAP if opening_only else GOLD_INTRADAY
        trade(day, GOLD_PRODUCT, bar._replace(open=price), -pos.side, pos, reason, anchor_day, stop)
        cycles[pos.cycle]["exit_day"] = day
        positions.pop(GOLD_PRODUCT)
        pending.pop(GOLD_PRODUCT, None)
        pending_reversals.pop(GOLD_PRODUCT, None)
        gold_stop_events.append(dict(
            date=day, product=GOLD_PRODUCT, contract=bar.vt_symbol, epoch=pos.epoch,
            cycle=pos.cycle, side=pos.side, anchor_day=anchor_day, stop=stop,
            open=bar.open, high=bar.high, low=bar.low, price=price,
            reason=reason, one_price=bar.high == bar.low,
        ))
'''


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"frozen source anchor changed: {old[:80]}")
    return source.replace(old, new)


def touch_source(source):
    edits = (
        ("    previous_day = None\n    for day in days:", STOP_HELPER + "\n    previous_day = None\n    for day in days:"),
        ("            before = len(fills)\n            position = positions.get(product)",
         "            before = len(fills)\n"
         "            if product == GOLD_PRODUCT:\n"
         "                check_gold_stop(day, index, opening_only=True)\n"
         "            position = positions.get(product)"),
        ("            if track_open_funding and len(fills) != before:\n"
         "                record_open(day, product)\n"
         "            if position:",
         "            if track_open_funding and len(fills) != before:\n"
         "                record_open(day, product)\n\n"
         "        check_gold_stop(day, index, opening_only=False)\n"
         "        for product in products:\n"
         "            position = positions.get(product)\n"
         "            if position:"),
        ("            is_add = False\n            orders = pending",
         "            if product == GOLD_PRODUCT and position:\n"
         "                decision = None\n"
         "            is_add = False\n            orders = pending"),
        ('    d.to_csv(out / "daily.csv", index=False)',
         '    pd.DataFrame(gold_stop_events, columns=GOLD_STOP_COLUMNS).to_csv(out / "gold_touch_stops.csv", index=False)\n'
         '    d.to_csv(out / "daily.csv", index=False)'),
    )
    for old, new in edits:
        source = replace_once(source, old, new)
    return source


def touch_engine():
    with patch.object(parent, "getsource", side_effect=lambda fn: touch_source(getsource(fn))):
        engine = parent.gated_engine()
    engine.update(GOLD_PRODUCT=PRODUCT, GOLD_OPEN_GAP=OPEN_GAP, GOLD_INTRADAY=INTRADAY,
                  GOLD_STOP_COLUMNS=STOP_COLUMNS, gold_touch_price=touch_price)
    return engine


def opening_reconstructor():
    original = base.reconstruct_opening
    source = replace_once(
        getsource(original),
        "fill.volume != 1 or fill.price != bar.open or",
        "fill.volume != 1 or (fill.reason != GOLD_INTRADAY and fill.price != bar.open) or",
    )
    source = replace_once(
        source, "            snapshot(day, index, fill.product, fill.reason)",
        "            if fill.reason != GOLD_INTRADAY:\n"
        "                snapshot(day, index, fill.product, fill.reason)",
    )
    namespace = {**original.__globals__, "GOLD_INTRADAY": INTRADAY}
    exec(compile(source, original.__code__.co_filename, "exec"), namespace)
    return namespace["reconstruct_opening"]


def replay(folder, start, market, engine, reconstruct, reference):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    path = folder / "inputs.json"
    inputs = prior.read_json(path)
    inputs["fixed_one_margin_gate"] = parent.GATE
    if inputs != prior.read_json(GOLD / start / "inputs.json"):
        raise ValueError(f"configuration drift: {start}")
    inputs["gold_stop_rule"] = RULE
    path.write_text(json.dumps(inputs, indent=2) + "\n")

    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    stops = pd.read_csv(folder / "gold_touch_stops.csv")
    stop_fills = fills.loc[fills.reason.isin((OPEN_GAP, INTRADAY))]
    cols = ["date", "product", "contract", "epoch", "cycle", "price", "stop", "reason", "one_price"]
    pd.testing.assert_frame_equal(stops[cols], stop_fills[cols].reset_index(drop=True),
                                  check_dtype=False, rtol=0, atol=1e-8)
    opening = reconstruct(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    if (not daily.date.equals(pd.read_csv(GOLD / start / "daily.csv").date)
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or parent.opening_checks(fills, opening) != (0, 0)
            or fills.loc[fills["product"].eq(PRODUCT), "reason"].eq("weekly_stop").any()
            or not stops.anchor_day.lt(stops.date).all()):
        raise ValueError(f"calendar, funding or gold rule drift: {start}")
    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    expected = sizing.free_cash.ge((sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8))
    if not admitted.equals(expected) or not sizing.requested_lots.eq(1).all():
        raise ValueError(f"incorrect opening funding decision: {start}")
    path = folder / "summary.json"
    summary = prior.read_json(path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return dict(calendar_start=start, **reference, **{f"touch_{k}": v for k, v in metrics.items()},
                touch_stop_count=len(stops), touch_open_gap_count=int(stops.reason.eq(OPEN_GAP).sum()),
                touch_intraday_count=int(stops.reason.eq(INTRADAY).sum()),
                touch_one_price_count=int(stops.one_price.sum()), touch_blocked_total=int((~admitted).sum()))


def run(output):
    base.verify_manifest(GOLD, silver.GOLD_SHA)
    frozen = prior.read_json(GOLD / "receipt.json")
    if (base.portfolio.sha(silver.AUDIT) != silver.AUDIT_SHA
            or base.portfolio.sha(Path(parent.__file__)) != frozen["entrypoint_sha256"]):
        raise ValueError("Stage052 engine or audit changed")
    ref = prior.read_json(parent.baseline.parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full = prior.add_tail((ref["products"], *expanded[1:]), original, prior.TAIL)
    hashes = {str(path): digest for path, digest in full[-1].items()}
    if hashes != frozen["market_sha256"] or tuple(frozen["starts"]) != prior.STARTS:
        raise ValueError("frozen market or calendar changed")
    market = (frozen["products"], *full[1:])
    control = pd.read_csv(GOLD / "window_metrics.csv", keep_default_na=False).set_index("calendar_start")
    keys = [key for key in control if key.startswith("gated_")]
    control = control[["first_session", "last_session", "days", "blocked_total", *keys]].rename(
        columns={**{k: k.replace("gated_", "weekly_", 1) for k in keys}, "blocked_total": "weekly_blocked_total"})
    output.mkdir(parents=True)
    engine, reconstruct = touch_engine(), opening_reconstructor()
    rows = [replay(output / start, start, market, engine, reconstruct, control.loc[start].to_dict())
            for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage052_manifest_sha256=silver.GOLD_SHA, stage052_audit_sha256=silver.AUDIT_SHA,
        stage052_entrypoint_sha256=frozen["entrypoint_sha256"], engine_sha256=prior.ENGINE_SHA,
        design_sha256=base.portfolio.sha(DESIGN), entrypoint_sha256=base.portfolio.sha(Path(__file__)),
        market_sha256=hashes, cutoff=base.TARGET, capital=base.CAPITAL, products=market[0],
        starts=prior.STARTS, gate=parent.GATE, gold_stop_rule=RULE,
        attempted_runs=len(prior.STARTS), completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
