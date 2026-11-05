"""Apply the Stage054 touch stop to every S21 product."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage054_s21_gold_touch_halfyear as gold

base, prior, LINE = gold.base, gold.prior, gold.LINE
BASELINE = LINE / "outputs/stage054_s21_gold_touch_halfyear_20261104"
BASELINE_SHA = "2ff506be26280e4861dcda2d11b3b9f3baa6687845bf55017488e29cb7d13b20"
AUDIT = LINE / "reviews/stage054_gold_touch_audit.json"
AUDIT_SHA = "3a68924629ec7e8767c111603ecad5107ec19db659ddf1c1a2eb24f7acc76dc4"
DESIGN = LINE / "stages/20261105_1237_stage055_all_touch_design.md"
OPEN_GAP, INTRADAY, DELAYED = "touch_open_gap", "touch_intraday", "touch_after_one_price"
RULE = "all_products_previous_week_touch_daily_ohlc_with_one_price_delay"
STOP_COLUMNS = (*gold.STOP_COLUMNS, "trigger_day")

STOP_HELPER = '''
    stop_anchors = {}
    locked_stops = {}
    gold_stop_events = []

    def check_touch_stop(day, index, product, *, opening_only):
        pos = positions.get(product)
        if pos is None:
            return False
        key = pos.cycle, pos.epoch
        bar = by_epoch.get((day, pos.epoch))
        locked = locked_stops.get(key)
        if locked is not None:
            if not opening_only or bar is None or bar.high == bar.low:
                if opening_only:
                    gaps.append((day, product, pos.symbol, "touch_exit_waiting_for_liquidity"))
                return True
            anchor_day, stop, trigger_day = locked
            price, reason = bar.open, TOUCH_DELAYED
            locked_stops.pop(key)
        else:
            reference = weekly(pos.epoch, index - 1)
            if reference is not None:
                stop = reference.low if pos.side == 1 else reference.high
                stop_anchors[key] = (reference.week_end.isoformat(), float(stop))
            anchor = stop_anchors.get(key)
            if anchor is None:
                raise ValueError(f"missing first stop anchor: {day}/{pos.epoch}")
            if bar is None:
                if not opening_only:
                    gaps.append((day, product, pos.symbol, "touch_stop_day_unavailable"))
                return False
            anchor_day, stop = anchor
            price = gold_touch_price(pos.side, stop, bar, opening_only=opening_only)
            if price is None:
                return False
            trigger_day = day
            if bar.high == bar.low:
                locked_stops[key] = anchor_day, stop, trigger_day
                gaps.append((day, product, pos.symbol, "touch_trigger_one_price"))
                return True
            reason = GOLD_OPEN_GAP if opening_only else GOLD_INTRADAY

        trade(day, product, bar._replace(open=price), -pos.side, pos, reason, anchor_day, stop)
        cycles[pos.cycle]["exit_day"] = day
        positions.pop(product)
        pending.pop(product, None)
        pending_reversals.pop(product, None)
        gold_stop_events.append(dict(
            date=day, product=product, contract=bar.vt_symbol, epoch=pos.epoch,
            cycle=pos.cycle, side=pos.side, anchor_day=anchor_day, stop=stop,
            open=bar.open, high=bar.high, low=bar.low, price=price,
            reason=reason, one_price=False, trigger_day=trigger_day,
        ))
        return False
'''


def all_touch_source(source, original_touch_source):
    with patch.object(gold, "STOP_HELPER", STOP_HELPER):
        source = original_touch_source(source)
    edits = (
        ("            if product == GOLD_PRODUCT:\n                check_gold_stop(day, index, opening_only=True)",
         "            if check_touch_stop(day, index, product, opening_only=True):\n                continue"),
        ("        check_gold_stop(day, index, opening_only=False)",
         "        for product in products:\n            check_touch_stop(day, index, product, opening_only=False)"),
        ("            if product == GOLD_PRODUCT and position:", "            if position:"),
        ('out / "gold_touch_stops.csv"', 'out / "touch_stops.csv"'),
    )
    for old, new in edits:
        source = gold.replace_once(source, old, new)
    return source


def build_engine():
    original_touch_source = gold.touch_source
    def overlay(source):
        return all_touch_source(source, original_touch_source)
    with (patch.object(gold, "touch_source", overlay), patch.object(gold, "OPEN_GAP", OPEN_GAP),
          patch.object(gold, "INTRADAY", INTRADAY), patch.object(gold, "STOP_COLUMNS", STOP_COLUMNS)):
        engine = gold.touch_engine()
        reconstruct = gold.opening_reconstructor()
    engine["TOUCH_DELAYED"] = DELAYED
    return engine, reconstruct


def replay(folder, start, market, engine, reconstruct, reference):
    engine["START"] = start
    with redirect_stdout(StringIO()):
        engine["run"](folder, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    path = folder / "inputs.json"
    inputs = gold.prior.read_json(path)
    inputs["fixed_one_margin_gate"] = gold.parent.GATE
    inputs["gold_stop_rule"] = gold.RULE
    if inputs != prior.read_json(BASELINE / start / "inputs.json"):
        raise ValueError(f"configuration drift: {start}")
    del inputs["gold_stop_rule"]
    inputs["all_products_stop_rule"] = RULE
    path.write_text(json.dumps(inputs, indent=2) + "\n")

    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    stops = pd.read_csv(folder / "touch_stops.csv")
    stop_fills = fills.loc[fills.reason.isin((OPEN_GAP, INTRADAY, DELAYED))]
    cols = ["date", "product", "contract", "epoch", "cycle", "price", "stop", "reason", "one_price"]
    pd.testing.assert_frame_equal(stops[cols], stop_fills[cols].reset_index(drop=True),
                                  check_dtype=False, rtol=0, atol=1e-8)
    opening = reconstruct(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    if (not daily.date.equals(pd.read_csv(BASELINE / start / "daily.csv").date)
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or gold.parent.opening_checks(fills, opening) != (0, 0)
            or fills.reason.eq("weekly_stop").any() or stops.one_price.any()
            or not (stops.anchor_day.lt(stops.trigger_day) & stops.trigger_day.le(stops.date)).all()
            or not stops.trigger_day.lt(stops.date).eq(stops.reason.eq(DELAYED)).all()):
        raise ValueError(f"calendar, funding or stop rule drift: {start}")
    sizing = pd.read_csv(folder / "risk_sizing.csv")
    admitted = sizing.executed_lots.eq(1)
    expected = sizing.free_cash.ge((sizing.margin_per_lot + sizing.entry_cost_per_lot).round(8))
    if not admitted.equals(expected) or not sizing.requested_lots.eq(1).all():
        raise ValueError(f"incorrect opening funding decision: {start}")
    summary_path = folder / "summary.json"
    summary = prior.read_json(summary_path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    gaps = pd.read_csv(folder / "gaps.csv")
    return dict(calendar_start=start, **reference, **{f"all_touch_{k}": v for k, v in metrics.items()},
                all_touch_stop_count=len(stops), all_touch_open_gap_count=int(stops.reason.eq(OPEN_GAP).sum()),
                all_touch_intraday_count=int(stops.reason.eq(INTRADAY).sum()),
                all_touch_delayed_count=int(stops.reason.eq(DELAYED).sum()),
                all_touch_locked_count=int(gaps.reason.eq("touch_trigger_one_price").sum()),
                all_touch_missing_bars=int(gaps.reason.eq("touch_stop_day_unavailable").sum()),
                all_touch_blocked_total=int((~admitted).sum()))


def run(output):
    base.verify_manifest(BASELINE, BASELINE_SHA)
    frozen = prior.read_json(BASELINE / "receipt.json")
    if (base.portfolio.sha(AUDIT) != AUDIT_SHA
            or base.portfolio.sha(Path(gold.__file__)) != frozen["entrypoint_sha256"]
            or base.portfolio.sha(Path(gold.parent.__file__)) != frozen["stage052_entrypoint_sha256"]):
        raise ValueError("Stage054 engine or audit changed")
    ref = prior.read_json(gold.parent.baseline.parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full = prior.add_tail((ref["products"], *expanded[1:]), original, prior.TAIL)
    hashes = {str(path): digest for path, digest in full[-1].items()}
    if hashes != frozen["market_sha256"] or tuple(frozen["starts"]) != prior.STARTS:
        raise ValueError("frozen market or calendar changed")
    market = (frozen["products"], *full[1:])
    control = pd.read_csv(BASELINE / "window_metrics.csv", keep_default_na=False).set_index("calendar_start")
    control = control.rename(columns={k: k.replace("touch_", "gold_touch_", 1)
                                      for k in control if k.startswith("touch_")})
    output.mkdir(parents=True)
    engine, reconstruct = build_engine()
    rows = [replay(output / start, start, market, engine, reconstruct, control.loc[start].to_dict())
            for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage054_manifest_sha256=BASELINE_SHA, stage054_audit_sha256=AUDIT_SHA,
        stage054_entrypoint_sha256=frozen["entrypoint_sha256"],
        stage052_entrypoint_sha256=frozen["stage052_entrypoint_sha256"], engine_sha256=prior.ENGINE_SHA,
        design_sha256=base.portfolio.sha(DESIGN), entrypoint_sha256=base.portfolio.sha(Path(__file__)),
        market_sha256=hashes, cutoff=base.TARGET, capital=base.CAPITAL, products=market[0],
        starts=prior.STARTS, gate=gold.parent.GATE, all_products_stop_rule=RULE,
        attempted_runs=len(prior.STARTS), completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
