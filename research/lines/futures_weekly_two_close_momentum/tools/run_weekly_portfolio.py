"""Offline portfolio replay of the frozen two-close weekly rule."""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from math import sqrt
from pathlib import Path
import sys

import pandas as pd

from weekly_two_close_momentum import MA_PERIODS, WeeklyBar, blocks_entry, weekly_action, weekly_ma_slopes

LINE = Path(__file__).resolve().parents[1]
FROZEN = LINE.parent / "futures_weekly19_stop_reversal" / "outputs"
DATA = FROZEN / "stage002_data/data_approved"
REFERENCE = FROZEN / "stage003_D_20261103_attempt01"
START, END, INITIAL = "2015-01-01", "2026-11-03", 300_000
CASH_RISK_2PCT = Decimal("0.02")
CASH_RISK_1PCT = Decimal("0.01")
CASH_RISK_HALF_PCT = Decimal("0.005")
MAX_ACTIVE_PRODUCTS = 5
MA40_WEEKS = 40


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_market():
    inputs = json.loads((REFERENCE / "inputs.json").read_text())["inputs_sha256"]
    audit = json.loads((FROZEN / "stage003_independent_review.json").read_text())
    paths = [DATA / name for name in ("receipt.json", "source_manifest.json", "physical_epoch_daily.csv",
                                      "mapping.csv", "forward_calendar.csv")]
    specs_path = REFERENCE / "contract_settings.json"
    expected = {path: inputs[str(path)] for path in paths}
    expected[specs_path] = audit["D"]["hashes"][specs_path.name]
    if any(sha(path) != digest for path, digest in expected.items()):
        raise ValueError("frozen market input hash mismatch")
    receipt = json.loads((DATA / "receipt.json").read_text())
    if receipt["date_end"] != END or not receipt["data_ready_for_bounded_replay"]:
        raise ValueError("data receipt cutoff or scope mismatch")
    mapping = pd.read_csv(DATA / "mapping.csv", dtype=str, keep_default_na=False)
    mapping = mapping.loc[mapping.date.between("2014-01-01", END)]
    products = sorted(mapping.continuous_symbol_vt.unique())
    days = sorted(mapping.date.unique())
    if len(products) != 19 or days[-1] != END:
        raise ValueError("universe or cutoff mismatch")
    grouped = defaultdict(list)
    for day in sorted(set(days).union(pd.read_csv(DATA / "forward_calendar.csv").date)):
        grouped[date.fromisoformat(day).isocalendar()[:2]].append(day)
    weeks = list(grouped.values())
    week_index = {day: i for i, week in enumerate(weeks) for day in week}

    frame = pd.read_csv(DATA / "physical_epoch_daily.csv", usecols=[
        "date", "vt_symbol", "contract_epoch_id", "contract_yyyymm", "open", "high", "low", "close", "volume",
    ], dtype={"contract_yyyymm": str})
    if frame.duplicated(["date", "vt_symbol"]).any() or frame.volume.le(0).any():
        raise ValueError("duplicate or non-positive-volume admitted daily bar")
    rows = {(r.date, r.vt_symbol): r for r in frame.itertuples(index=False)}
    epoch_rows = {(r.date, r.contract_epoch_id): r for r in rows.values()}
    mains = {(r.date, r.continuous_symbol_vt): r.main_contract_vt for r in mapping.itertuples(index=False)}
    if any((END, mains.get((END, product))) not in rows
           for product in products):
        raise ValueError("latest main data incomplete")
    return products, days, weeks, week_index, rows, epoch_rows, mains, json.loads(specs_path.read_text()), expected


@dataclass
class Position:
    side: int
    cycle: int
    symbol: str
    epoch: str
    expiry_month: str
    mark: float
    entry_day: str
    volume: int = 1


def entry_risk_lots(free, side, price, stop, size, fraction=CASH_RISK_2PCT):
    budget = max(Decimal(0), Decimal(str(free))) * fraction
    risk = side * (Decimal(str(price)) - Decimal(str(stop))) * size
    return budget, risk, int(budget // risk) if risk > 0 else 0


def affordable_lots(free, margin, cost):
    return int(max(Decimal(0), Decimal(str(free))) // (margin + cost))


def aligned_week_bodies(action, current, previous):
    if action == "open_long":
        return current.close > current.open and previous.close > previous.open
    return current.close < current.open and previous.close < previous.open


def blocks_week_range_overlap(current, previous):
    shorter_range = min(current.high - current.low, previous.high - previous.low)
    overlap = min(current.high, previous.high) - max(current.low, previous.low)
    return shorter_range > 0 and overlap * 2 >= shorter_range


def weekly_shape_status(action, current, previous, prior_weeks):
    span = current.high - current.low
    previous_span = previous.high - previous.low
    close_tail = current.high - current.close if action == "open_long" else current.close - current.low
    if span <= 0 or previous_span <= 0 or span < 2 * previous_span:
        return "no_range_expansion"
    if 4 * close_tail > span:
        return "close_outside_quartile"
    if prior_weeks is not None:
        if any(week is None for week in prior_weeks):
            return "missing_breakout_history"
        if action == "open_long" and current.close <= max(week.high for week in prior_weeks):
            return "no_breakout"
        if action == "open_short" and current.close >= min(week.low for week in prior_weeks):
            return "no_breakout"
    return "allowed"


def delivery_guard_start(calendar, delivery_month):
    """First of the five known trading days before the delivery month."""
    boundary = f"{delivery_month[:4]}-{delivery_month[4:]}-01"
    index = bisect_left(calendar, boundary)
    return calendar[index - 5] if 5 <= index < len(calendar) else boundary


def run(
    out, *, ma_filter=True, cash_risk=False, risk_fraction=CASH_RISK_2PCT,
    week_body_filter=False, max_five_products=False, max_fixed_adds=0, fresh_add_sequence=False,
    ma40_filter=False, reverse_after_stop=False, two_close_entry=False, block_four_up=False,
    ma10_20_only=False, market_loader=None, delivery_guard=False, long_only=False,
    block_week_range_overlap=False, weekly_shape_entry=None, monthly_entry_products=None,
):
    if weekly_shape_entry not in (None, "expansion", "expansion_break3"):
        raise ValueError("unknown weekly entry shape")
    if ma10_20_only and not ma_filter:
        raise ValueError("MA10/20 mode requires the slope filter")
    slope_periods = (10, 20) if ma10_20_only else MA_PERIODS
    if max_fixed_adds not in (0, 1, 2, 3):
        raise ValueError("supported fixed addition limits are 0 through 3")
    if max_fixed_adds and cash_risk:
        raise ValueError("fixed-lot additions require fixed entry sizing")
    if monthly_entry_products is not None and max_fixed_adds:
        raise ValueError("monthly entry selection requires no fixed additions")
    if fresh_add_sequence and not (max_fixed_adds and week_body_filter):
        raise ValueError("fresh addition sequences require fixed adds and the weekly body filter")
    max_fixed_lots = 1 + max_fixed_adds
    track_open_funding = cash_risk or max_fixed_adds > 0
    load = load_market if market_loader is None else market_loader
    products, days, weeks, week_index, rows, by_epoch, mains, specs, hashes = load()
    guard_starts = {}
    if delivery_guard:
        calendar = sorted({day for week in weeks for day in week})
        guard_starts = {
            month: delivery_guard_start(calendar, month)
            for month in {bar.contract_yyyymm for bar in by_epoch.values()}
        }
    out.mkdir(parents=True)
    source = [
        Path(__file__), Path(__file__).with_name("weekly_two_close_momentum.py"),
        next((LINE / "stages").glob("*_stage002_full_history.md")),
        next((LINE / "stages").glob("*_stage003_weekly_ma_slope_filter.md")),
    ]
    if cash_risk:
        source.append(next((LINE / "stages").glob("*_stage004_cash_risk_sizing.md")))
        if risk_fraction == CASH_RISK_HALF_PCT:
            source.append(next((LINE / "stages").glob("*_stage005_cash_risk_half_pct.md")))
        if risk_fraction == CASH_RISK_1PCT:
            source.append(next((LINE / "stages").glob("*_stage008_weekly_body_cash_risk_one_pct.md")))
    if week_body_filter:
        source.append(next((LINE / "stages").glob("*_stage006_weekly_body_filter.md")))
    if max_five_products:
        source.append(next((LINE / "stages").glob("*_stage009_weekly_body_one_pct_max_five.md")))
    if max_fixed_adds:
        source.append(next((LINE / "stages").glob("*_stage010_weekly_fixed_one_two_adds.md")))
    if max_fixed_adds == 3:
        source.append(next((LINE / "stages").glob("*_stage011_weekly_fixed_one_three_adds.md")))
    if fresh_add_sequence:
        source.append(next((LINE / "stages").glob("*_stage012_weekly_fixed_one_fresh_add_sequence.md")))
        if max_fixed_adds == 1:
            source.append(next((LINE / "stages").glob("*_stage013_weekly_fixed_one_fresh_single_add.md")))
    if ma40_filter:
        source.append(next((LINE / "stages").glob("*_stage014_weekly_ma40_filter.md")))
    if reverse_after_stop:
        source.append(next((LINE / "stages").glob("*_stage016_weekly_reverse_after_stop.md")))
    if two_close_entry:
        source.append(next((LINE / "stages").glob("*_stage019_weekly_two_close_correction.md")))
    if block_four_up:
        source.append(next((LINE / "stages").glob("*_stage022_block_four_up.md")))
    if ma10_20_only:
        source.append(next((LINE / "stages").glob("*_stage023_ma10_20_only.md")))
    if long_only:
        source.append(next((LINE / "stages").glob("*_stage026_s_s44_long_only.md")))
    if block_week_range_overlap:
        source.append(Path(__file__).with_name("stage028_week_range_overlap.py"))
    if weekly_shape_entry:
        source.append(Path(__file__).with_name("stage030_weekly_shape_replay.py"))
    if monthly_entry_products is not None:
        source.append(Path(__file__).with_name("stage032_s19_monthly_volume_top10.py"))
    (out / "inputs.json").write_text(json.dumps({
        "start": START, "end": days[-1], "initial": INITIAL, "products": products, "ma_slope_filter": ma_filter,
        "cash_risk_fraction": float(risk_fraction) if cash_risk else None,
        **({"week_body_filter": True} if week_body_filter else {}),
        **({"max_active_products": MAX_ACTIVE_PRODUCTS} if max_five_products else {}),
        **({"max_fixed_adds": max_fixed_adds} if max_fixed_adds else {}),
        **({"fresh_add_sequence": True} if fresh_add_sequence else {}),
        **({"ma40_filter": "raw_main_weekly_close"} if ma40_filter else {}),
        **({"reverse_after_stop": True} if reverse_after_stop else {}),
        **({"two_close_entry": True} if two_close_entry else {}),
        **({"block_four_up": True} if block_four_up else {}),
        **({"ma_slope_periods": list(slope_periods)} if ma10_20_only else {}),
        **({"delivery_guard_trading_days": 5} if delivery_guard else {}),
        **({"long_only": True} if long_only else {}),
        **({"block_week_range_overlap_pct": 50} if block_week_range_overlap else {}),
        **({"weekly_shape_entry": weekly_shape_entry} if weekly_shape_entry else {}),
        **({"monthly_entry_products": {month: sorted(pool) for month, pool in monthly_entry_products.items()}}
           if monthly_entry_products is not None else {}),
        "inputs_sha256": {str(path): digest for path, digest in hashes.items()},
        "source_sha256": {str(path): sha(path) for path in source},
        "python": sys.version,
    }, indent=2) + "\n")

    cache, positions, pending, cycles = {}, {}, {}, {}
    pending_reversals = {}
    fills, daily, gaps, signals = [], [], [], []
    filter_events = []
    body_events = []
    ma40_events = []
    four_up_blocks = []
    week_range_blocks = []
    shape_checks = []
    monthly_entry_blocks = []
    main_weekly_closes = {}
    if ma40_filter:
        for product in products:
            closes = []
            for week in weeks:
                week_end = week[-1]
                bar = rows.get((week_end, mains.get((week_end, product))))
                closes.append(Decimal(str(bar.close)) if bar is not None else None)
            main_weekly_closes[product] = closes
    add_breaks, add_sequences = {}, []
    sizing, opening_marks = [], []
    cash = INITIAL
    total_slippage = total_commission = 0.0

    def weekly(epoch, index):
        if index < 0:
            return None
        key = epoch, index
        if key not in cache:
            dates = weeks[index]
            bars = [by_epoch.get((day, epoch)) for day in dates]
            cache[key] = None if None in bars else WeeklyBar(
                bars[0].vt_symbol, date.fromisoformat(dates[0]), date.fromisoformat(dates[-1]),
                *map(lambda value: Decimal(str(value)),
                     (bars[0].open, max(bar.high for bar in bars), min(bar.low for bar in bars), bars[-1].close)),
            )
        return cache[key]

    def trade(day, product, bar, side, position, reason, signal_day, stop, *, volume=None):
        nonlocal cash, total_slippage, total_commission
        symbol = bar.vt_symbol
        size = specs["sizes"][symbol]
        volume = position.volume if volume is None else volume
        slippage = size * specs["slippages"][symbol] * volume
        commission = size * bar.open * specs["rates"][symbol] * volume
        flow = -side * size * bar.open * volume - slippage - commission
        cash += flow
        total_slippage += slippage
        total_commission += commission
        cycles[position.cycle]["cash_flow"] += flow
        fills.append(dict(date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                          cycle=position.cycle, side=side, volume=volume, price=bar.open, size=size,
                          slippage=slippage, commission=commission, reason=reason,
                          signal_day=signal_day, stop=stop, one_price=bar.high == bar.low))

    def available(bar):
        return bar is not None and bar.high > bar.low

    def open_funding(day):
        value = margin = 0
        for pos in positions.values():
            bar = by_epoch.get((day, pos.epoch))
            # A missing bar leaves the previous valid mark untouched.
            price = bar.open if bar is not None else pos.mark
            notional = price * specs["sizes"][pos.symbol] * pos.volume
            value += pos.side * notional
            margin += notional * specs["margin_ratios"][pos.symbol]
        equity = cash + value
        return round(equity, 8), round(margin, 8), round(equity - margin, 8)

    def funding_order(day, product, bar, kind, signal_day, side, stop, carry=None):
        equity, margin, free = open_funding(day)
        symbol = bar.vt_symbol
        size = specs["sizes"][symbol]
        notional = Decimal(str(bar.open)) * size
        unit_margin = notional * Decimal(str(specs["margin_ratios"][symbol]))
        cost = size * Decimal(str(specs["slippages"][symbol]))
        cost += notional * Decimal(str(specs["rates"][symbol]))
        affordable = affordable_lots(free, unit_margin, cost)
        budget = risk = None
        requested = carry
        if kind == "entry":
            budget, risk, requested = entry_risk_lots(free, side, bar.open, stop, size, risk_fraction)
        volume = min(affordable, requested)
        if risk is not None and risk <= 0:
            status = "at_or_through_stop"
        elif kind == "entry" and not requested:
            status = "risk_below_one_lot"
        elif not volume:
            status = "margin_below_one_lot"
        elif volume < requested:
            status = "margin_capped"
        else:
            status = "filled"
        sizing.append(dict(date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                           kind=kind, signal_day=signal_day, side=side, price=bar.open, stop=stop,
                           equity=equity, margin=margin, free_cash=free, risk_budget=budget,
                           risk_per_lot=risk, margin_per_lot=unit_margin, entry_cost_per_lot=cost,
                           requested_lots=requested, affordable_lots=affordable,
                           executed_lots=volume, status=status))
        return volume

    def record_open(day, product):
        equity, margin, free = open_funding(day)
        opening_marks.append(dict(date=day, after_product=product, equity=equity,
                                  margin=margin, free_cash=free, positions=len(positions),
                                  lots=sum(pos.volume for pos in positions.values())))

    def queue_signal(orders, day, product, bar, action, stop, current, last, older):
        orders[product] = action, day, bar.vt_symbol, bar.contract_epoch_id, stop
        signals.append(dict(date=day, product=product, contract=bar.vt_symbol, epoch=bar.contract_epoch_id,
                            action=action, stop=stop, close=current.close, prior_close=last.close,
                            older_close=older.close if older else None))

    previous_day = None
    for day in days:
        if day < START:
            previous_day = day
            continue
        index = week_index[day]
        if track_open_funding:
            record_open(day, "")
        for product in products:
            before = len(fills)
            position = positions.get(product)
            order = pending.get(product)
            entry_kind = "entry"
            guard_active = position and delivery_guard and day >= guard_starts[position.expiry_month]
            if guard_active and not (order and order[0].startswith("close_")):
                bar = by_epoch.get((day, position.epoch))
                if bar is not None:
                    trade(day, product, bar, -position.side, position, "delivery_guard_exit",
                          guard_starts[position.expiry_month], None)
                    cycles[position.cycle]["exit_day"] = day
                    add_breaks.pop(position.cycle, None)
                    positions.pop(product)
                    pending.pop(product, None)
                    pending_reversals.pop(product, None)
                    position = order = None
                else:
                    gaps.append((day, product, position.symbol, "delivery_guard_exit_open_unavailable"))
            if order and order[0].startswith("add_"):
                action, signal_day, symbol, epoch, stop = pending.pop(product)
                side = 1 if action == "add_long" else -1
                if (position is None or position.side != side or position.epoch != epoch
                        or position.volume >= max_fixed_lots):
                    raise ValueError(f"invalid pending addition: {day} {product}")
                bar = by_epoch.get((day, epoch))
                if available(bar):
                    trade(day, product, bar, side, position, "add", signal_day, stop, volume=1)
                    position.volume += 1
                else:
                    gaps.append((day, product, symbol, "add_open_unavailable"))
                order = None
            if order and order[0].startswith("close_"):
                _, signal_day, symbol, epoch, stop = order
                bar = by_epoch.get((day, epoch))
                reversal = pending_reversals.pop(product, None)
                order = None
                if bar is not None:
                    trade(day, product, bar, -position.side, position, "weekly_stop", signal_day, stop)
                    cycles[position.cycle]["exit_day"] = day
                    add_breaks.pop(position.cycle, None)
                    positions.pop(product)
                    pending.pop(product)
                    position = None
                    if reversal:
                        pending[product] = order = reversal
                        entry_kind = "reversal"
                else:
                    gaps.append((day, product, symbol, "exit_open_unavailable"))
            if order:
                action, signal_day, symbol, epoch, stop = order
                bar = by_epoch.get((day, epoch))
                pending.pop(product)
                if monthly_entry_products is not None and product not in monthly_entry_products[day[:7]]:
                    monthly_entry_blocks.append(dict(date=day, product=product, contract=symbol, epoch=epoch,
                                                     action=action, kind=entry_kind, signal_day=signal_day))
                    gaps.append((day, product, symbol, "entry_outside_monthly_pool"))
                elif delivery_guard and day >= guard_starts[epoch.rsplit(".", 1)[-1]]:
                    gaps.append((day, product, symbol, "entry_delivery_guard"))
                elif not available(bar) or position is not None:
                    gaps.append((day, product, symbol, "entry_open_unavailable"))
                elif max_five_products and len(positions) >= MAX_ACTIVE_PRODUCTS:
                    gaps.append((day, product, symbol, "entry_max_active_products"))
                else:
                    side = 1 if action == "open_long" else -1
                    volume = funding_order(day, product, bar, "entry", signal_day, side, stop) if cash_risk else 1
                    if volume:
                        cycle = len(cycles) + 1
                        position = Position(side, cycle, symbol, epoch, bar.contract_yyyymm, bar.open, day, volume)
                        cycles[cycle] = dict(cycle=cycle, product=product, direction=side, entry_day=day,
                                             exit_day="", cash_flow=0.0)
                        positions[product] = position
                        trade(day, product, bar, side, position, "entry", signal_day, stop)
            elif position and product not in pending and not guard_active:
                target = mains.get((previous_day, product))
                if target and target != position.symbol:
                    old = by_epoch.get((day, position.epoch))
                    new = rows.get((day, target))
                    # Identify the physical target from information available at
                    # the previous close. The opening print must match it.
                    known = rows.get((previous_day, target))
                    protection = weekly(known.contract_epoch_id, index - 1) if known else None
                    if new is not None and delivery_guard and day >= guard_starts[new.contract_yyyymm]:
                        gaps.append((day, product, target, "roll_target_delivery_guard"))
                    elif old is not None and available(new) and protection and known.contract_epoch_id == new.contract_epoch_id:
                        trade(day, product, old, -position.side, position, "roll_close", previous_day, None)
                        stop = protection.low if position.side == 1 else protection.high
                        volume = position.volume
                        if cash_risk:
                            positions.pop(product)
                            volume = funding_order(day, product, new, "roll", previous_day, position.side, stop, volume)
                        if volume:
                            position.volume = volume
                            trade(day, product, new, position.side, position, "roll_open", previous_day, stop)
                            position.symbol, position.epoch = target, new.contract_epoch_id
                            position.expiry_month, position.mark = new.contract_yyyymm, new.open
                            positions[product] = position
                        else:
                            fills[-1]["reason"] = "roll_funding_exit"
                            cycles[position.cycle]["exit_day"] = day
                            position = None
                    else:
                        gaps.append((day, product, position.symbol, "roll_open_pair_or_history_unavailable"))

            if track_open_funding and len(fills) != before:
                record_open(day, product)
            if position:
                bar = by_epoch.get((day, position.epoch))
                if day[:7].replace("-", "") > position.expiry_month:
                    raise ValueError(f"expired contract retained: {day} {position.symbol}")
                if bar:
                    position.mark = bar.close
                else:
                    gaps.append((day, product, position.symbol, "held_close_stale"))

            if day != weeks[index][-1] or product in pending:
                continue
            symbol = position.symbol if position else mains.get((day, product))
            if not symbol:
                continue
            bar = by_epoch.get((day, position.epoch)) if position else rows.get((day, symbol))
            current = weekly(bar.contract_epoch_id, index) if bar else None
            last = weekly(bar.contract_epoch_id, index - 1) if bar else None
            older = weekly(bar.contract_epoch_id, index - 2) if bar and not position and not two_close_entry else None
            if not current or not last or (not position and not two_close_entry and older is None):
                gaps.append((day, product, symbol, "weekly_history_incomplete"))
                continue
            decision = weekly_action(
                position.side if position else 0, current, last, older, two_close_entry=two_close_entry,
            )
            is_add = False
            orders = pending
            if position and decision:
                action, stop = decision
                queue_signal(pending, day, product, bar, action, stop, current, last, older)
                if not reverse_after_stop:
                    continue
                symbol = mains.get((day, product))
                bar = rows.get((day, symbol))
                if bar is None:
                    continue
                current = weekly(bar.contract_epoch_id, index)
                last = weekly(bar.contract_epoch_id, index - 1)
                older = weekly(bar.contract_epoch_id, index - 2) if not two_close_entry else None
                if current is None or last is None or (not two_close_entry and older is None):
                    continue
                decision = weekly_action(0, current, last, older, two_close_entry=two_close_entry)
                opposite = "open_short" if position.side == 1 else "open_long"
                if decision is None or decision[0] != opposite:
                    continue
                orders = pending_reversals
            elif decision is None and max_fixed_adds and position and position.volume < max_fixed_lots:
                if fresh_add_sequence:
                    if (position.side * (current.close - last.close) <= 0
                            or position.side * (current.close - current.open) <= 0):
                        add_breaks[position.cycle] = index
                    break_week = add_breaks.get(position.cycle)
                    if break_week is None or index - break_week < 2:
                        continue
                older = weekly(bar.contract_epoch_id, index - 2) if not two_close_entry else None
                entry = weekly_action(0, current, last, older, two_close_entry=two_close_entry)
                expected_action = "open_long" if position.side == 1 else "open_short"
                if entry and entry[0] == expected_action:
                    decision = entry
                    is_add = True
            if decision:
                action, stop = decision
                if week_body_filter:
                    aligned = aligned_week_bodies(action, current, last)
                    body_events.append(dict(
                        date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                        action=action, status="allowed" if aligned else "blocked",
                        signal_week_open=current.open, signal_week_close=current.close,
                        prior_week_open=last.open, prior_week_close=last.close,
                    ))
                    if not aligned:
                        continue
                if ma_filter:
                    history = [
                        weekly(bar.contract_epoch_id, week_id)
                        for week_id in range(index - max(slope_periods), index + 1)
                    ]
                    slopes = weekly_ma_slopes(history, slope_periods)
                    blocked = blocks_entry(action, slopes)
                    slope_values = slopes if slopes is not None else (None,) * len(slope_periods)
                    filter_events.append(dict(
                        date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                        action=action, status="blocked" if blocked else ("incomplete" if slopes is None else "allowed"),
                        **{f"ma{period}_slope": slope for period, slope in zip(slope_periods, slope_values)},
                    ))
                    if blocked:
                        continue
                if ma40_filter:
                    window = main_weekly_closes[product][max(0, index - MA40_WEEKS + 1):index + 1]
                    if len(window) != MA40_WEEKS or None in window:
                        ma40, status = None, "missing_history"
                    else:
                        ma40 = sum(window) / MA40_WEEKS
                        side = 1 if action == "open_long" else -1
                        status = "allowed" if side * (window[-1] - ma40) > 0 else "blocked_price"
                    ma40_events.append(dict(
                        date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                        action=action, kind="add" if is_add else "entry", status=status,
                        main_contract=mains.get((day, product)), main_close=window[-1], ma40=ma40,
                    ))
                    if status != "allowed":
                        continue
                if long_only and action == "open_short":
                    reason = "reversal_short_disabled" if orders is pending_reversals else "entry_short_disabled"
                    gaps.append((day, product, symbol, reason))
                    continue
                if block_four_up and action == "open_long" and not is_add:
                    window = [weekly(bar.contract_epoch_id, week_id) for week_id in range(index - 4, index + 1)]
                    if all(window):
                        closes = [week.close for week in window]
                        if all(a < b for a, b in zip(closes, closes[1:])):
                            four_up_blocks.append(dict(
                                date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                                kind="reversal" if orders is pending_reversals else "entry",
                                **{f"close_t{offset}": close for offset, close in zip((4, 3, 2, 1, 0), closes)},
                            ))
                            continue
                if block_week_range_overlap and not is_add and blocks_week_range_overlap(current, last):
                    week_range_blocks.append(dict(
                        date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id, action=action,
                        kind="reversal" if orders is pending_reversals else "entry",
                        current_high=current.high, current_low=current.low,
                        previous_high=last.high, previous_low=last.low,
                    ))
                    continue
                if weekly_shape_entry and not is_add:
                    prior_weeks = None
                    if weekly_shape_entry == "expansion_break3":
                        prior_weeks = [weekly(bar.contract_epoch_id, j) for j in range(index - 3, index)]
                    status = weekly_shape_status(action, current, last, prior_weeks)
                    shape_checks.append(dict(date=day, product=product, contract=symbol, epoch=bar.contract_epoch_id,
                                             action=action, kind="reversal" if orders is pending_reversals else "entry",
                                             status=status))
                    if status != "allowed":
                        continue
                if is_add:
                    action = action.replace("open_", "add_", 1)
                    if fresh_add_sequence:
                        break_week = add_breaks.pop(position.cycle)
                        add_sequences.append(dict(
                            cycle=position.cycle, product=product, contract=symbol, action=action,
                            break_day=weeks[break_week][-1], first_confirm_day=weeks[index - 1][-1],
                            signal_day=day,
                        ))
                queue_signal(orders, day, product, bar, action, stop, current, last, older)

        mark = sum(p.side * p.mark * specs["sizes"][p.symbol] * p.volume for p in positions.values())
        margin = sum(p.mark * specs["sizes"][p.symbol] * specs["margin_ratios"][p.symbol] * p.volume
                     for p in positions.values())
        daily.append(dict(date=day, equity=cash + mark, cash=cash, position_value=mark, margin=margin,
                          positions=len(positions), cumulative_slippage=total_slippage,
                          cumulative_commission=total_commission))
        if track_open_funding:
            daily[-1]["lots"] = sum(p.volume for p in positions.values())
        previous_day = day

    for pos in positions.values():
        cycles[pos.cycle]["terminal_mark"] = pos.side * pos.mark * specs["sizes"][pos.symbol] * pos.volume
    c = pd.DataFrame(cycles.values()).fillna({"terminal_mark": 0})
    if "terminal_mark" not in c.columns:
        c["terminal_mark"] = 0.0
    c["net_pnl"] = (c.cash_flow + c.terminal_mark).round(8)
    d = pd.DataFrame(daily)
    d["net_pnl"] = d.equity.diff().fillna(d.equity - INITIAL)
    d["drawdown"] = d.equity / d.equity.cummax().clip(lower=INITIAL) - 1
    d["margin_ratio"] = d.margin / d.equity
    closed = c.loc[c.exit_day.ne("")]
    wins = closed.loc[closed.net_pnl.gt(0), "net_pnl"]
    losses = -closed.loc[closed.net_pnl.lt(0), "net_pnl"]
    returns = d.equity.pct_change().fillna(d.equity / INITIAL - 1)
    pnl = float(d.equity.iloc[-1] - INITIAL)
    if abs(pnl - c.net_pnl.sum()) > 1e-6:
        raise ValueError("cycle net PnL does not reconcile to daily equity")
    stats = dict(
        start=d.date.iloc[0], end=d.date.iloc[-1], days=len(d), initial=INITIAL,
        equity=d.equity.iloc[-1], net_pnl=pnl, return_pct=100*pnl/INITIAL,
        max_dd_pct=100*d.drawdown.min(), sharpe=returns.mean()/returns.std()*sqrt(252),
        fills=len(fills), one_price_exits=sum(fill["one_price"] for fill in fills), rolls=sum(fill["reason"] == "roll_open" for fill in fills),
        closed_cycles=len(closed), wins=len(wins), losses=len(losses),
        win_rate_pct=100*len(wins)/len(closed), payoff=wins.mean()/losses.mean(),
        profit_factor=wins.sum()/losses.sum(), slippage=total_slippage, commission=total_commission,
        net_pnl_double_slippage_same_path=pnl-total_slippage,
        peak_margin=d.margin.max(), peak_margin_ratio_pct=100*d.margin_ratio.max(),
        days_margin_above_equity=int(d.margin_ratio.gt(1).sum()),
        open_positions=len(positions), pending_signals=len(pending),
        long_pnl=c.loc[c.direction.eq(1), "net_pnl"].sum(), short_pnl=c.loc[c.direction.eq(-1), "net_pnl"].sum(),
        terminal_open_net_pnl=c.loc[c.exit_day.eq(""), "net_pnl"].sum(),
        gaps=dict(Counter(item[-1] for item in gaps)),
    )
    d.to_csv(out / "daily.csv", index=False)
    c.to_csv(out / "cycles.csv", index=False)
    pd.DataFrame(fills).to_csv(out / "fills.csv", index=False)
    pd.DataFrame(signals).to_csv(out / "signals.csv", index=False)
    pd.DataFrame(gaps, columns=["date", "product", "contract", "reason"]).to_csv(out / "gaps.csv", index=False)
    if ma_filter:
        pd.DataFrame(filter_events).to_csv(out / "entry_filter.csv", index=False)
    if week_body_filter:
        pd.DataFrame(body_events).to_csv(out / "week_body_filter.csv", index=False)
    if ma40_filter:
        pd.DataFrame(ma40_events).to_csv(out / "ma40_filter.csv", index=False)
    if block_four_up:
        pd.DataFrame(four_up_blocks, columns=[
            "date", "product", "contract", "epoch", "kind",
            "close_t4", "close_t3", "close_t2", "close_t1", "close_t0",
        ]).to_csv(out / "four_up_blocks.csv", index=False)
    if block_week_range_overlap:
        pd.DataFrame(week_range_blocks, columns=[
            "date", "product", "contract", "epoch", "action", "kind",
            "current_high", "current_low", "previous_high", "previous_low",
        ]).to_csv(out / "week_range_blocks.csv", index=False)
    if weekly_shape_entry:
        pd.DataFrame(shape_checks, columns=[
            "date", "product", "contract", "epoch", "action", "kind", "status",
        ]).to_csv(out / "weekly_shape_checks.csv", index=False)
    if monthly_entry_products is not None:
        pd.DataFrame(monthly_entry_blocks, columns=[
            "date", "product", "contract", "epoch", "action", "kind", "signal_day",
        ]).to_csv(out / "monthly_entry_blocks.csv", index=False)
    if fresh_add_sequence:
        pd.DataFrame(add_sequences, columns=[
            "cycle", "product", "contract", "action", "break_day", "first_confirm_day", "signal_day",
        ]).to_csv(out / "add_sequences.csv", index=False)
    if cash_risk:
        pd.DataFrame(sizing).to_csv(out / "risk_sizing.csv", index=False)
    if track_open_funding:
        pd.DataFrame(opening_marks).to_csv(out / "opening_marks.csv", index=False)
    d.groupby(d.date.str[:4]).net_pnl.sum().to_csv(out / "annual.csv")
    terminal = {product: vars(pos).copy() for product, pos in positions.items()}
    if not track_open_funding:
        for pos in terminal.values():
            pos.pop("volume")
    (out / "terminal.json").write_text(json.dumps({
        "positions": terminal, "pending": pending,
        **({"pending_reversals": pending_reversals} if reverse_after_stop else {}),
    }, default=str, indent=2) + "\n")
    report = json.dumps(stats, default=lambda value: value.item(), indent=2)
    (out / "summary.json").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-ma-slope-filter", action="store_true")
    parser.add_argument("--ma10-20-only", action="store_true", help="use only MA10 and MA20 in the slope filter")
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument("--cash-risk-2pct", dest="risk_fraction", action="store_const", const=CASH_RISK_2PCT)
    sizing.add_argument("--cash-risk-1pct", dest="risk_fraction", action="store_const", const=CASH_RISK_1PCT)
    sizing.add_argument("--cash-risk-0-5pct", dest="risk_fraction", action="store_const", const=CASH_RISK_HALF_PCT)
    parser.add_argument("--week-body-filter", action="store_true")
    parser.add_argument("--max-five-products", action="store_true")
    parser.add_argument("--fresh-add-sequence", action="store_true")
    parser.add_argument("--ma40-filter", action="store_true")
    parser.add_argument("--reverse-after-stop", action="store_true")
    parser.add_argument("--two-close-entry", action="store_true")
    parser.add_argument("--block-four-up", action="store_true", help="skip new longs after four rising weekly closes")
    sizing.add_argument("--one-fixed-add", dest="max_fixed_adds", action="store_const", const=1)
    sizing.add_argument("--two-fixed-adds", dest="max_fixed_adds", action="store_const", const=2)
    sizing.add_argument("--three-fixed-adds", dest="max_fixed_adds", action="store_const", const=3)
    parser.set_defaults(max_fixed_adds=0)
    args = parser.parse_args()
    run(args.output, ma_filter=not args.no_ma_slope_filter, cash_risk=args.risk_fraction is not None,
        risk_fraction=args.risk_fraction, week_body_filter=args.week_body_filter,
        max_five_products=args.max_five_products, max_fixed_adds=args.max_fixed_adds,
        fresh_add_sequence=args.fresh_add_sequence, ma40_filter=args.ma40_filter,
        reverse_after_stop=args.reverse_after_stop, two_close_entry=args.two_close_entry,
        block_four_up=args.block_four_up, ma10_20_only=args.ma10_20_only)
