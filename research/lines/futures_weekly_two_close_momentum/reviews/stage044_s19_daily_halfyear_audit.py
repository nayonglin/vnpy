"""Independently re-create each Stage044 signal, execution, and cash ledger."""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import (
    CAPITAL, DAY_COLUMNS, FULL, HALF, HISTORY, LINE, OPEN_COLUMNS, TARGET,
    cents, check_manifest, load_json, near, read_csv, sha,
)
from stage043_s19_daily_one_audit import Holding, Signal, source_data

RESULT = LINE / "outputs/stage044_s19_daily_halfyear_20261104"
STAGE043 = LINE / "outputs/stage043_s19_daily_one_20261104"
STAGE041 = LINE / "outputs/stage041_complete_halfyear_20261104"
STARTS = [f"{year}-{month}-01" for year in range(2015, 2027) for month in ("01", "07")]


def reconcile(folder, start, config, calendar, guard_calendar, mains, symbols, by_epoch, settings):
    products = config["products"]
    dates = [day for day in calendar if day >= start]
    assert dates[0] >= start and dates[-1] == TARGET
    positions, orders, reversals = {}, {}, {}
    fills, signals, bodies, ma, four_up, gaps, opening, daily_marks = [], [], [], [], [], [], [], []
    cycles, open_sizes = {}, Counter()
    branches = Counter()
    delayed = []
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

    for index in range(bisect_left(calendar, start), len(calendar)):
        day, yesterday = calendar[index], calendar[index - 1]
        snapshot(day, 0)
        for product in products:
            held = positions.get(product)
            order = orders.pop(product, None)
            conditional = reversals.pop(product, None)
            old_bar = by_epoch.get((day, held.bar.epoch)) if held else None
            guard_active = held and day >= guard(held.bar)
            if held and order and order.action.startswith("close_"):
                if old_bar is None:
                    gaps.append((day, product, held.bar.symbol, "exit_open_unavailable"))
                    orders[product] = order
                    branches["exit_missing_open"] += 1
                    if conditional:
                        branches["conditional_reverse_expired_after_missing_exit"] += 1
                    order = None
                else:
                    if order.day != yesterday:
                        assert all((calendar[prior], order.bar.epoch) not in by_epoch
                                   for prior in range(bisect_left(calendar, order.day) + 1, index))
                        delayed.append(dict(start=start, product=product, symbol=old_bar.symbol,
                                            signal=order.day, next_session=calendar[bisect_left(calendar, order.day) + 1],
                                            execution=day, open=old_bar.op / 100))
                    close_position(day, product, old_bar, "weekly_stop", order.day, order.stop)
                    held, order = None, conditional
            elif guard_active:
                if old_bar is None:
                    gaps.append((day, product, held.bar.symbol, "delivery_guard_exit_open_unavailable"))
                    branches["guard_exit_missing_open"] += 1
                else:
                    close_position(day, product, old_bar, "delivery_guard_exit", guard(held.bar))
                    held = order = None

            if order:
                assert held is None and order.day == yesterday
                current = by_epoch.get((day, order.bar.epoch))
                if day >= guard(order.bar):
                    gaps.append((day, product, order.bar.symbol, "entry_delivery_guard"))
                elif current is None or current.high == current.low:
                    gaps.append((day, product, order.bar.symbol, "entry_open_unavailable"))
                    branches["entry_missing_open" if current is None else "entry_one_price_open"] += 1
                else:
                    side = 1 if order.action == "open_long" else -1
                    number = len(cycles) + 1
                    cycles[number] = dict(product=product, direction=side, entry=day, exit="", flow=0)
                    positions[product] = Holding(current, side, number, day, current.op)
                    fill(day, product, current, side, number, "entry", order.day, order.stop)
            elif held and product not in orders and not guard_active:
                main = mains.get((yesterday, product))
                if main and main != held.bar.symbol:
                    current, old_main = symbols.get((day, main)), symbols.get((yesterday, main))
                    if current and day >= guard(current):
                        gaps.append((day, product, main, "roll_target_delivery_guard"))
                    elif old_bar and current and old_main and current.epoch == old_main.epoch and current.high > current.low:
                        side, number, entered = held.side, held.number, held.entered
                        close_position(day, product, old_bar, "roll_close", yesterday)
                        positions[product] = Holding(current, side, number, entered, current.op)
                        fill(day, product, current, side, number, "roll_open", yesterday,
                             old_main.low if side == 1 else old_main.high)
                    else:
                        gaps.append((day, product, held.bar.symbol, "roll_open_pair_or_history_unavailable"))
                        branches["roll_pair_unavailable"] += 1

            held = positions.get(product)
            current = None
            if held:
                assert day[:7].replace("-", "") <= held.bar.epoch.rsplit(".", 1)[1]
                current = by_epoch.get((day, held.bar.epoch))
                if current:
                    held.mark = current.close
                else:
                    gaps.append((day, product, held.bar.symbol, "held_close_stale"))
            if product in orders:
                continue
            reversing = None
            if held:
                prev = by_epoch.get((yesterday, held.bar.epoch))
                if current is None or prev is None:
                    gaps.append((day, product, held.bar.symbol, "weekly_history_incomplete"))
                    continue
                bound = prev.low if held.side == 1 else prev.high
                if held.side * (current.close - bound) > 0:
                    continue
                add_signal(day, product, "close_long" if held.side == 1 else "close_short",
                           current, prev, None, bound, orders)
                reversing = -held.side

            main = mains.get((day, product))
            if main is None:
                continue
            current = symbols.get((day, main))
            bars = [by_epoch.get((calendar[index - offset], current.epoch))
                    for offset in range(21)] if current else [None] * 21
            _, prev, older = bars[:3]
            if current is None or prev is None or older is None:
                if reversing is None:
                    gaps.append((day, product, main, "weekly_history_incomplete"))
                continue
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
        actual = read_csv(folder, name)
        generated = pd.DataFrame(expected, columns=actual.columns)
        nullable = {"stop", "older_close", "ma5_slope", "ma10_slope", "ma20_slope"}
        for field in nullable.intersection(actual.columns):
            actual[field] = pd.to_numeric(actual[field].mask(actual[field].eq("")))
            generated[field] = pd.to_numeric(generated[field].mask(generated[field].eq("")))
        pd.testing.assert_frame_equal(generated, actual, check_dtype=False, check_exact=False, rtol=0, atol=1e-8,
                                      obj=name)
    marks = pd.DataFrame(daily_marks, columns=DAY_COLUMNS)
    observed = read_csv(folder, "daily")
    assert observed.date.tolist() == dates
    near(observed[DAY_COLUMNS], marks)

    terminal = load_json(folder / "terminal.json")
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
    cycle_csv = read_csv(folder, "cycles")
    assert len(cycle_csv) == len(cycles)
    for row in cycle_csv.itertuples(index=False):
        cycle = cycles[row.cycle]
        mark = terminal_value.get(row.cycle, 0)
        assert (row.product, row.direction, row.entry_day, row.exit_day, cents(row.cash_flow),
                cents(row.terminal_mark), cents(row.net_pnl)) == (
            cycle["product"], cycle["direction"], cycle["entry"], cycle["exit"], cycle["flow"],
            mark, cycle["flow"] + mark)
    return marks, pd.DataFrame(opening, columns=OPEN_COLUMNS), cycles, len(orders), len(reversals), branches, delayed


def financial_metrics(folder, marks, opening, pending):
    daily = read_csv(folder, "daily")
    fills = read_csv(folder, "fills")
    cycles = read_csv(folder, "cycles")
    equity = marks.equity
    prior_equity = np.r_[CAPITAL, equity.iloc[:-1]]
    net = equity.iat[-1] - CAPITAL
    near(net, cycles.net_pnl.sum())
    near(equity - prior_equity, daily.net_pnl)
    drawdown = equity / np.maximum.accumulate(np.r_[CAPITAL, equity])[1:] - 1
    near(drawdown, daily.drawdown)
    with np.errstate(divide="ignore", invalid="ignore"):
        margin_ratio = marks.margin / equity
        sharpe = None if (prior_equity == 0).any() else float(
            (equity / prior_equity - 1).mean() / (equity / prior_equity - 1).std(ddof=1) * np.sqrt(252))
    near(margin_ratio, daily.margin_ratio)
    annual = pd.Series(equity - prior_equity).groupby(daily.date.str[:4]).sum()
    annual_csv = read_csv(folder, "annual")
    assert annual.index.tolist() == annual_csv.date.astype(str).tolist()
    near(annual, annual_csv.net_pnl)

    close_free = (equity - marks.margin).round(8)
    open_free = opening.free_equity.round(8)
    op_gap = set(opening.loc[open_free.lt(0), "date"])
    close_gap = set(daily.loc[close_free.lt(0), "date"])
    nonpositive = set(daily.loc[equity.le(0), "date"]) | set(opening.loc[opening.equity.le(0), "date"])
    closed = cycles[cycles.exit_day.ne("")]
    wins = closed.loc[closed.net_pnl.gt(0), "net_pnl"]
    losses = -closed.loc[closed.net_pnl.lt(0), "net_pnl"]
    performance = dict(
        equity=equity.iat[-1], net_pnl=net, return_pct=100 * net / CAPITAL, max_dd_pct=100 * drawdown.min(),
        sharpe=sharpe, closed_cycles=len(closed), wins=len(wins), losses=len(losses),
        win_rate_pct=100 * len(wins) / len(closed), fills=len(fills),
        slippage=marks.cumulative_slippage.iat[-1], commission=marks.cumulative_commission.iat[-1],
    )
    result = dict(
        **performance,
        gold_net_pnl=cycles.loc[cycles["product"].eq("au.SHFE"), "net_pnl"].sum(),
        peak_close_margin=marks.margin.max(), peak_open_margin=opening.margin.max(),
        min_close_free_equity=close_free.min(), min_open_free_equity=open_free.min(),
        close_deficit_days=len(close_gap), opening_deficit_days=len(op_gap), deficit_days=len(op_gap | close_gap),
        first_deficit=min(op_gap | close_gap, default=""), max_shortfall=max(0, -min(close_free.min(), open_free.min())),
        minimum_close_equity=equity.min(), max_close_positions=marks.positions.max(),
    )
    def strict_constant(value):
        raise ValueError(f"non-JSON number in {folder.name}/summary.json: {value}")

    summary = json.loads((folder / "summary.json").read_text(), parse_constant=strict_constant)
    assert (summary["start"], summary["end"], summary["days"], summary["initial"]) == (
        daily.date.iat[0], TARGET, len(marks), CAPITAL)
    assert summary["gaps"] == dict(Counter(read_csv(folder, "gaps").reason))
    expected = dict(
        **performance, pending_signals=pending, days_margin_above_equity=len(close_gap),
        peak_margin=marks.margin.max(),
        peak_margin_ratio_pct=100 * margin_ratio.max() if np.isfinite(margin_ratio.max()) else None,
        open_positions=int(marks.positions.iat[-1]),
        one_price_exits=int(fills.one_price.sum()), rolls=int(fills.reason.eq("roll_open").sum()),
        payoff=wins.mean() / losses.mean(), profit_factor=wins.sum() / losses.sum(),
        net_pnl_double_slippage_same_path=net - performance["slippage"],
        long_pnl=cycles.loc[cycles.direction.eq(1), "net_pnl"].sum(),
        short_pnl=cycles.loc[cycles.direction.eq(-1), "net_pnl"].sum(),
        terminal_open_net_pnl=cycles.loc[cycles.exit_day.eq(""), "net_pnl"].sum(),
    )
    for key, value in expected.items():
        if value is None:
            assert summary[key] is None, (folder, key, summary[key])
        else:
            near(summary[key], value)

    counters = dict(
        days=len(daily), fills=len(fills), cycles=len(cycles), opening_snapshots=len(opening),
        signals=len(read_csv(folder, "signals")), one_price_exits=int(fills.one_price.sum()),
        nonpositive_days=len(nonpositive), entries=int(fills.reason.eq("entry").sum()),
        stops=int(fills.reason.eq("weekly_stop").sum()),
        rolls=int(fills.reason.eq("roll_open").sum()),
        guard_exits=int(fills.reason.eq("delivery_guard_exit").sum()),
    )
    zero_close = daily.loc[equity.eq(0), "date"].tolist()
    return result, counters, zero_close


def control_path(start):
    if start == STARTS[0]:
        return FULL
    if start == "2015-07-01":
        return STAGE041 / start / "s19"
    return HALF / start


def audit():
    parents = {folder.name: check_manifest(folder) for folder in (FULL, HALF, STAGE041, STAGE043)}
    count = check_manifest(RESULT)
    receipt = load_json(RESULT / "receipt.json")
    prev = load_json(STAGE043 / "receipt.json")
    assert receipt["stage041_manifest_sha256"] == sha(STAGE041 / "SHA256SUMS")
    assert receipt["stage043_manifest_sha256"] == sha(STAGE043 / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_1942_stage044_s19_daily_halfyear_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage044_s19_daily_halfyear.py")
    assert prev["entrypoint_sha256"] == sha(LINE / "tools/stage043_s19_daily_one.py")
    assert (receipt["signal_bar"], receipt["fixed_entry_lots"], receipt["starts"],
            receipt["attempted"], receipt["completed"], receipt["unknown"], receipt["cutoff"], receipt["capital"]) == (
        "1d", 1, STARTS, 24, 24, 0, TARGET, CAPITAL)
    assert (receipt["market_sha256"], receipt["source_sha256"]) == (prev["market_sha256"], prev["source_sha256"])
    pins = receipt["market_sha256"] | receipt["source_sha256"]
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)
    reproduction = RESULT / "2026-01-01"
    files = {path.name for path in reproduction.iterdir()}
    assert files == set(receipt["stage043_identical_ledgers"])
    assert all((reproduction / name).read_bytes() == (STAGE043 / name).read_bytes() for name in files)
    controls = read_csv(STAGE041, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = read_csv(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == controls.index.tolist() == STARTS
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    source = source_data()
    totals, branches, gap_reasons = Counter(), Counter(), Counter()
    delayed = []
    windows = []
    for start in STARTS:
        folder = RESULT / start
        config = load_json(control_path(start) / "inputs.json")
        assert config["start"] == start and config["end"] == TARGET and config["initial"] == CAPITAL
        assert len(config["products"]) == 19 and config["products"].count("au.SHFE") == 1
        assert (config["inputs_sha256"], config["source_sha256"]) == (receipt["market_sha256"], receipt["source_sha256"])
        assert load_json(folder / "inputs.json") == {**config, "signal_bar": "1d", "fixed_entry_lots": 1}
        marks, opening, cycles, pending, conditional, affected, delayed_stops = reconcile(
            folder, start, config, *source, settings)
        metrics, checked, zero_close = financial_metrics(folder, marks, opening, pending)
        row = combined.loc[start]
        assert row.first_session == controls.at[start, "first_session"]
        assert row.last_session == controls.at[start, "last_session"] == TARGET
        assert row.days == controls.at[start, "days"] == checked["days"]
        assert row.daily_nonpositive_equity_days == checked["nonpositive_days"]
        for key, value in metrics.items():
            actual = row[f"daily_{key}"]
            if value is None:
                assert actual == "", (start, key, actual)
            elif isinstance(value, str):
                assert actual == value
            elif isinstance(actual, str):
                near(float(actual), value)
            else:
                near(actual, value)
            expected = controls.at[start, f"s19_{key}"]
            observed = row[f"weekly_{key}"]
            if isinstance(expected, str):
                assert observed == expected
            else:
                near(observed, expected)
        totals.update(checked)
        branches.update(affected)
        delayed.extend(delayed_stops)
        gap_reasons.update(read_csv(folder, "gaps").reason)
        windows.append(dict(start=start, deficit_days=metrics["deficit_days"],
                            nonpositive_days=checked["nonpositive_days"], zero_equity_close_dates=zero_close,
                            terminal_pending=pending, terminal_conditional_reversals=conditional,
                            final_equity=float(metrics["equity"])))
        print(start, checked, dict(affected), flush=True)
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", completed=len(windows), unknown=0,
        manifest_entries=count, manifest_sha256=sha(RESULT / "SHA256SUMS"), parent_manifest_entries=parents,
        stage043_byte_identical_files=len(files), pinned_inputs=len(pins), checked_rows=dict(totals),
        gap_reasons=dict(gap_reasons), execution_branches=dict(branches), delayed_stop_rows=delayed,
        windows_with_deficit=sum(row["deficit_days"] > 0 for row in windows),
        windows_with_nonpositive_equity=sum(row["nonpositive_days"] > 0 for row in windows),
        windows=windows,
        limitations=[
            "Positive-volume, non-one-price execution-day bars qualify opening entry proxies. "
            "The opening queue is not observed, and positive-volume one-price exits use the opening print as a proxy.",
            "Frozen main-contract mapping is not certified as revision-free point-in-time vendor data.",
            "Cash shortfalls and nonpositive equity do not halt theoretical trading.",
            "Percentage Sharpe is not economically interpretable after nonpositive equity; an exact-zero close "
            "can produce an infinite raw margin ratio and undefined next-session percentage return.",
            "Overlapping start windows repeat historical events. Zero commission.",
        ],
    )
    with Path(__file__).with_suffix(".json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print({key: value for key, value in report.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
