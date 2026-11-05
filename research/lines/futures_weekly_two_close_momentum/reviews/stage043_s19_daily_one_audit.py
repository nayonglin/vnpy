"""Independent signal, execution, and accounting replay for Stage043's daily signal bars."""
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import (
    ADMITTED, CAPITAL, DAY_COLUMNS, HALF, HISTORY, LINE, OPEN_COLUMNS, TAIL, TARGET,
    audit_book, cents, check_manifest, load_json, near, physical_prices, read_csv, sha,
)

RESULT = LINE / "outputs/stage043_s19_daily_one_20261104"
START = "2026-01-01"


@dataclass(frozen=True)
class Bar:
    symbol: str
    epoch: str
    op: int
    high: int
    low: int
    close: int


@dataclass(frozen=True)
class Signal:
    action: str
    day: str
    bar: Bar
    stop: int


@dataclass
class Holding:
    bar: Bar
    side: int
    number: int
    entered: str
    mark: int


def source_data():
    mapping = pd.read_csv(ADMITTED / "mapping.csv", usecols=["date", "continuous_symbol_vt", "main_contract_vt"])
    calendar = sorted(set(mapping.date)) + [TARGET]
    guard_calendar = sorted(set(calendar) | set(pd.read_csv(ADMITTED / "forward_calendar.csv").date))
    mains = {(row.date, row.continuous_symbol_vt): row.main_contract_vt
             for row in mapping.dropna().itertuples(index=False)}
    tail_request = load_json(TAIL.parents[1] / "request.json")
    continuous_table = load_json(TAIL.parents[1] / "continuous_table.raw.json")
    for product, symbol in tail_request["mains"].items():
        code, exchange = product.split(".")
        for day in calendar[-2:]:
            _, vendor_symbol = max(row for row in continuous_table[f"{exchange}.{code}"]
                                   if row[0] <= day.replace("-", ""))
            vendor_exchange, contract = vendor_symbol.split(".")
            assert f"{contract}.{vendor_exchange}" == (symbol if day == TARGET else mains[day, product])
        mains[TARGET, product] = symbol

    columns = ["date", "vt_symbol", "contract_epoch_id", "open", "high", "low", "close", "volume"]
    history = pd.read_csv(ADMITTED / "physical_epoch_daily.csv", usecols=columns)
    epochs = pd.read_csv(ADMITTED / "physical_epochs.csv", dtype=str)
    current = epochs[epochs.contract_yyyymm.ge("202611")].set_index("vt_symbol", verify_integrity=True)
    tail = pd.read_csv(TAIL)
    tail = tail[tail.date.eq(TARGET) & tail.volume.gt(0)].copy()
    tail["contract_epoch_id"] = tail.vt_symbol.map(current.contract_epoch_id)
    records = pd.concat([history, tail[columns]], ignore_index=True)
    assert records.volume.gt(0).all()
    symbols, by_epoch = {}, {}
    for row in records.itertuples(index=False):
        bar = Bar(row.vt_symbol, row.contract_epoch_id, *map(cents, (row.open, row.high, row.low, row.close)))
        assert (row.date, bar.epoch) not in by_epoch
        symbols[row.date, bar.symbol] = by_epoch[row.date, bar.epoch] = bar
    return calendar, guard_calendar, mains, symbols, by_epoch


def reconcile(config, calendar, guard_calendar, mains, symbols, by_epoch, settings):
    products = config["products"]
    dates = [day for day in calendar if day >= START]
    assert dates[0] == "2026-01-05" and dates[-1] == TARGET
    positions, orders, reversals = {}, {}, {}
    fills, signals, bodies, ma, four_up, gaps, opening, daily_marks = [], [], [], [], [], [], [], []
    cycles, open_sizes = {}, Counter()
    cash, slip_total, fee_total = CAPITAL * 100, 0, 0
    rates = {symbol: int(Decimal(str(value)) * 10_000) for symbol, value in settings["margin_ratios"].items()}

    def guard(bar):
        month = bar.epoch.rsplit(".", 1)[1]
        boundary = f"{month[:4]}-{month[4:]}-01"
        index = bisect_left(guard_calendar, boundary)
        return guard_calendar[index - 5] if 5 <= index < len(guard_calendar) else boundary

    def valuation(day, opening):
        value = margin = 0
        for position in positions.values():
            bar = by_epoch.get((day, position.bar.epoch))
            mark = position.mark if bar is None else bar.op if opening else bar.close
            notional = mark * settings["sizes"][position.bar.symbol]
            value += position.side * notional
            margin += notional * rates[position.bar.symbol]
        return value, margin

    def snapshot(day, sequence, product="", reason="before_fills"):
        value, margin = valuation(day, True)
        equity, margin = (cash + value) / 100, margin / 1_000_000
        opening.append((day, sequence, product, reason, equity, margin, equity - margin, len(positions)))

    def fill(day, product, bar, side, number, reason, decision, stop):
        nonlocal cash, slip_total, fee_total
        size = settings["sizes"][bar.symbol]
        slip = cents(size * settings["slippages"][bar.symbol])
        fee = cents(size * (bar.op / 100) * settings["rates"][bar.symbol])
        flow = -side * size * bar.op - slip - fee
        cash += flow
        slip_total += slip
        fee_total += fee
        cycles[number]["flow"] += flow
        fills.append((day, product, bar.symbol, bar.epoch, number, side, 1, bar.op / 100, size, slip / 100,
                      fee / 100, reason, decision, stop / 100 if stop is not None else "", bar.high == bar.low))
        open_sizes[day] += 1
        snapshot(day, open_sizes[day], product, reason)

    def close_position(day, product, bar, reason, decision, stop=None):
        held = positions.pop(product)
        fill(day, product, bar, -held.side, held.number, reason, decision, stop)
        if reason != "roll_close":
            cycles[held.number]["exit"] = day

    def add_signal(day, product, key, current, prev, older, stop, destination):
        order = Signal(key, day, current, stop)
        destination[product] = order
        signals.append((day, product, current.symbol, current.epoch, key, stop / 100, current.close / 100,
                        prev.close / 100, older.close / 100 if older else ""))

    for index in range(bisect_left(calendar, START), len(calendar)):
        day, yesterday = calendar[index], calendar[index - 1]
        snapshot(day, 0)
        for product in products:
            held = positions.get(product)
            order = orders.pop(product, None)
            conditional = reversals.pop(product, None)
            old_bar = by_epoch.get((day, held.bar.epoch)) if held else None
            if held and order and order.action.startswith("close_"):
                assert old_bar is not None
                close_position(day, product, old_bar, "weekly_stop", order.day, order.stop)
                held, order = None, conditional
            elif held and day >= guard(held.bar):
                assert old_bar is not None
                close_position(day, product, old_bar, "delivery_guard_exit", guard(held.bar))
                held = order = None

            if order:
                assert held is None and order.day == yesterday
                current = by_epoch.get((day, order.bar.epoch))
                if day >= guard(order.bar):
                    gaps.append((day, product, order.bar.symbol, "entry_delivery_guard"))
                else:
                    assert current and current.high > current.low, ("entry open proxy affects result", day, product)
                    side = 1 if order.action == "open_long" else -1
                    number = len(cycles) + 1
                    cycles[number] = dict(product=product, direction=side, entry=day, exit="", flow=0)
                    positions[product] = Holding(current, side, number, day, current.op)
                    fill(day, product, current, side, number, "entry", order.day, order.stop)
            elif held:
                main = mains.get((yesterday, product))
                if main and main != held.bar.symbol:
                    current, old_main = symbols.get((day, main)), symbols.get((yesterday, main))
                    if current and day >= guard(current):
                        gaps.append((day, product, main, "roll_target_delivery_guard"))
                    else:
                        assert old_bar and current and old_main and current.epoch == old_main.epoch
                        assert current.high > current.low, ("roll open proxy affects result", day, product)
                        side, number, entered = held.side, held.number, held.entered
                        close_position(day, product, old_bar, "roll_close", yesterday)
                        positions[product] = Holding(current, side, number, entered, current.op)
                        fill(day, product, current, side, number, "roll_open", yesterday,
                             old_main.low if side == 1 else old_main.high)

            held = positions.get(product)
            reversing = None
            if held:
                current = by_epoch.get((day, held.bar.epoch))
                prev = by_epoch.get((yesterday, held.bar.epoch))
                assert current and prev
                held.mark = current.close
                bound = prev.low if held.side == 1 else prev.high
                if held.side * (current.close - bound) > 0:
                    continue
                add_signal(day, product, "close_long" if held.side == 1 else "close_short",
                           current, prev, None, bound, orders)
                reversing = -held.side

            main = mains.get((day, product))
            current = symbols.get((day, main))
            assert current
            bars = [by_epoch.get((calendar[index - offset], current.epoch)) for offset in range(21)]
            _, prev, older = bars[:3]
            assert prev and older
            if current.close > prev.close > older.close:
                side, action = 1, "open_long"
            elif current.close < prev.close < older.close:
                side, action = -1, "open_short"
            else:
                continue
            if reversing and reversing != side:
                continue
            prefix = (day, product, current.symbol, current.epoch, action)
            same_body = all(side * (bar.close - bar.op) > 0 for bar in (current, prev))
            bodies.append((*prefix, "allowed" if same_body else "blocked",
                           current.op / 100, current.close / 100, prev.op / 100, prev.close / 100))
            if not same_body:
                continue
            slopes = [(current.close - bars[p].close) / (100 * p) for p in (5, 10, 20)] if all(bars) else None
            ma_block = slopes is not None and all(side * slope < 0 for slope in slopes)
            ma.append((*prefix, "blocked" if ma_block else "incomplete" if slopes is None else "allowed",
                       *(slopes if slopes is not None else ("", "", ""))))
            if ma_block:
                continue
            if side == 1 and all(bars[:5]) and all(x.close > y.close for x, y in zip(bars[:4], bars[1:5])):
                four_up.append((*prefix[:4], "reversal" if reversing else "entry",
                                *(bar.close / 100 for bar in reversed(bars[:5]))))
                continue
            add_signal(day, product, action, current, prev, older, current.low if side == 1 else current.high,
                       reversals if reversing else orders)

        value, margin = valuation(day, False)
        daily_marks.append(((cash + value) / 100, cash / 100, value / 100, margin / 1_000_000,
                            len(positions), slip_total / 100, fee_total / 100))

    for name, expected in (("fills", fills), ("signals", signals), ("gaps", gaps), ("entry_filter", ma),
                           ("week_body_filter", bodies), ("four_up_blocks", four_up), ("opening_funding", opening)):
        actual = read_csv(RESULT, name)
        generated = pd.DataFrame(expected, columns=actual.columns)
        nullable = {"stop", "older_close", "ma5_slope", "ma10_slope", "ma20_slope"}
        for field in nullable.intersection(actual.columns):
            actual[field] = pd.to_numeric(actual[field].replace("", np.nan))
            generated[field] = pd.to_numeric(generated[field].replace("", np.nan))
        pd.testing.assert_frame_equal(generated, actual, check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
                                      obj=name)
    marks = pd.DataFrame(daily_marks, columns=DAY_COLUMNS)
    observed = read_csv(RESULT, "daily")
    assert observed.date.tolist() == dates
    near(observed[DAY_COLUMNS], marks)

    terminal = load_json(RESULT / "terminal.json")
    assert set(terminal["positions"]) == set(positions)
    terminal_value = {}
    for product, holding in positions.items():
        position = terminal["positions"][product]
        assert (position["symbol"], position["epoch"], position["side"], position["cycle"],
                position["entry_day"], cents(position["mark"])) == (
            holding.bar.symbol, holding.bar.epoch, holding.side, holding.number, holding.entered, holding.mark)
        assert by_epoch[TARGET, holding.bar.epoch].close == holding.mark
        terminal_value[holding.number] = holding.side * holding.mark * settings["sizes"][holding.bar.symbol]
    for section, expected in (("pending", orders), ("pending_reversals", reversals)):
        normalized = {product: (*order[:4], cents(float(order[4]))) for product, order in terminal[section].items()}
        assert normalized == {product: (order.action, TARGET, order.bar.symbol, order.bar.epoch, order.stop)
                              for product, order in expected.items()}
    cycle_csv = read_csv(RESULT, "cycles")
    assert len(cycle_csv) == len(cycles)
    for row in cycle_csv.itertuples(index=False):
        cycle = cycles[row.cycle]
        mark = terminal_value.get(row.cycle, 0)
        assert (row.product, row.direction, row.entry_day, row.exit_day, cents(row.cash_flow),
                cents(row.terminal_mark), cents(row.net_pnl)) == (
            cycle["product"], cycle["direction"], cycle["entry"], cycle["exit"], cycle["flow"],
            mark, cycle["flow"] + mark)
    return marks, pd.DataFrame(opening, columns=OPEN_COLUMNS), cycles, len(orders), len(reversals)


def audit():
    previous = HALF / START
    result_count, previous_count = check_manifest(RESULT), check_manifest(HALF)
    receipt = load_json(RESULT / "receipt.json")
    assert receipt["weekly_reference_manifest_sha256"] == sha(HALF / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_1936_stage043_s19_daily_one_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage043_s19_daily_one.py")
    assert (receipt["signal_bar"], receipt["fixed_entry_lots"], receipt["attempted"],
            receipt["completed"], receipt["unknown"]) == ("1d", 1, 1, 1, 0)
    config = load_json(previous / "inputs.json")
    assert config["start"] == START and config["end"] == TARGET and config["initial"] == CAPITAL
    assert len(config["products"]) == 19 and config["products"].count("au.SHFE") == 1
    assert load_json(RESULT / "inputs.json") == {**config, "signal_bar": "1d", "fixed_entry_lots": 1}
    assert (receipt["market_sha256"], receipt["source_sha256"]) == (config["inputs_sha256"], config["source_sha256"])
    pins = receipt["market_sha256"] | receipt["source_sha256"]
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    calendar, guard_calendar, mains, symbols, by_epoch = source_data()
    marks, opening, cycles, pending, conditional = reconcile(
        config, calendar, guard_calendar, mains, symbols, by_epoch, settings)

    daily = read_csv(RESULT, "daily")
    fills = read_csv(RESULT, "fills")
    cycle_csv = read_csv(RESULT, "cycles")
    equity = marks.equity
    prev = np.r_[CAPITAL, equity.iloc[:-1]]
    net = equity.iat[-1] - CAPITAL
    near(net, cycle_csv.net_pnl.sum())
    near(equity - prev, daily.net_pnl)
    drawdown = equity / np.maximum.accumulate(np.r_[CAPITAL, equity])[1:] - 1
    near(drawdown, daily.drawdown)
    near(marks.margin / equity, daily.margin_ratio)
    near(pd.Series(equity - prev).groupby(daily.date.str[:4]).sum(), read_csv(RESULT, "annual").net_pnl)
    returns = equity / prev - 1
    close_free = (equity - marks.margin).round(8)
    open_free = opening.free_equity.round(8)
    op_gap = set(opening.loc[open_free.lt(0), "date"])
    close_gap = set(daily.loc[close_free.lt(0), "date"])
    nonpositive = set(daily.loc[equity.le(0), "date"]) | set(opening.loc[opening.equity.le(0), "date"])
    closed = cycle_csv[cycle_csv.exit_day.ne("")]
    wins, losses = closed.net_pnl.gt(0).sum(), closed.net_pnl.lt(0).sum()
    metrics = dict(
        equity=equity.iat[-1], net_pnl=net, return_pct=100 * net / CAPITAL, max_dd_pct=100 * drawdown.min(),
        sharpe=returns.mean() / returns.std(ddof=1) * np.sqrt(252), closed_cycles=len(closed),
        wins=wins, losses=losses, win_rate_pct=100 * wins / len(closed), fills=len(fills),
        slippage=marks.cumulative_slippage.iat[-1], commission=marks.cumulative_commission.iat[-1],
        gold_net_pnl=cycle_csv.loc[cycle_csv["product"].eq("au.SHFE"), "net_pnl"].sum(),
        peak_close_margin=marks.margin.max(), peak_open_margin=opening.margin.max(),
        min_close_free_equity=close_free.min(), min_open_free_equity=open_free.min(),
        close_deficit_days=len(close_gap), opening_deficit_days=len(op_gap), deficit_days=len(op_gap | close_gap),
        first_deficit=min(op_gap | close_gap), max_shortfall=-min(close_free.min(), open_free.min()),
        minimum_close_equity=equity.min(), max_close_positions=marks.positions.max(),
    )
    summary = load_json(RESULT / "summary.json")
    assert (summary["start"], summary["end"], summary["days"], summary["initial"]) == (
        daily.date.iat[0], TARGET, len(marks), CAPITAL)
    assert summary["pending_signals"] == pending and summary["days_margin_above_equity"] == len(close_gap)
    assert summary["gaps"] == dict(Counter(read_csv(RESULT, "gaps").reason))
    for key in metrics.keys() & summary.keys():
        near(metrics[key], summary[key])
    control, control_counts, *_ = audit_book(previous, START, calendar, physical_prices(), settings)
    comparison = load_json(RESULT / "comparison.json")
    assert set(comparison["daily"]) == set(metrics)
    for label, values in (("daily", metrics), ("weekly", control)):
        for key, value in values.items():
            if isinstance(value, str):
                assert comparison[label][key] == value
            else:
                near(comparison[label][key], value)
    reasons = dict(Counter(fills.reason))
    assert comparison["daily_fill_reasons"] == reasons
    assert comparison["daily_nonpositive_equity_days"] == len(nonpositive)
    worst = opening.loc[open_free.idxmin()].to_dict()
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", manifest_sha256=sha(RESULT / "SHA256SUMS"),
        manifest_entries=result_count, parent_manifest_entries=previous_count, pinned_inputs=len(pins),
        dates=[daily.date.iat[0], TARGET], days=len(daily), signals=len(read_csv(RESULT, "signals")),
        fills=len(fills), opening_snapshots=len(opening), cycles=len(cycles), fill_reasons=reasons,
        checked_event_rows={name: len(read_csv(RESULT, name)) for name in (
            "entry_filter", "week_body_filter", "four_up_blocks", "gaps")},
        pending_at_cutoff=pending, conditional_reversals_at_cutoff=conditional,
        funding_deficit_days=len(op_gap | close_gap), worst_open_snapshot=worst,
        nonpositive_equity_days=len(nonpositive), weekly_comparison_book_counts=control_counts,
        limitations=[
            "Full execution-day high/low and positive volume qualify a daily opening proxy in the inherited engine. "
            "No candidate in this window was blocked by the high/low or daily-volume proxy. "
            "No session-open depth or as-of intraday volume is available.",
            "Main-contract vendor mapping is frozen but revision-free point-in-time availability is not established.",
            "Theoretical fills continue through static margin shortfalls. No broker funding checks or forced liquidation.",
            "Zero commissions. The legacy weekly_stop and week_body_filter labels refer to daily decisions in this run.",
        ],
    )
    with Path(__file__).with_suffix(".json").open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(report)


if __name__ == "__main__":
    audit()
