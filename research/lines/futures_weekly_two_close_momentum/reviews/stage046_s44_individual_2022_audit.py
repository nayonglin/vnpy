"""Independently audit each of the 44 separate S44 accounts over 2022."""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import (
    ADMITTED, CAPITAL, DAY_COLUMNS, HALF, HISTORY, LINE, OPEN_COLUMNS,
    cents, check_manifest, load_json, near, read_csv, sha,
)
from stage043_s19_daily_one_audit import Bar, Holding, Signal
from stage045_s19_weekly_shadow_filter_audit import completed_weeks

RESULT = LINE / "outputs/stage046_s44_individual_2022"
MARKET = LINE / "outputs/stage024_market/approved_v1"
START, END = "2022-01-01", "2022-12-30"
PREWARM = "2021-01-01"
BAR_COLUMNS = ["date", "vt_symbol", "contract_epoch_id", "open", "high", "low", "close", "volume"]
MAPPING_COLUMNS = ["date", "continuous_symbol_vt", "main_contract_vt"]


def table(folder, name):
    try:
        return read_csv(folder, name)
    except pd.errors.EmptyDataError:
        assert (folder / (name + ".csv")).read_text().strip() == ""
        return pd.DataFrame()


def raw_market():
    original_mapping = pd.read_csv(ADMITTED / "mapping.csv", usecols=MAPPING_COLUMNS, keep_default_na=False)
    extra_mapping = pd.read_csv(MARKET / "added_mapping.csv", usecols=MAPPING_COLUMNS, keep_default_na=False)
    all_mapping = pd.concat([original_mapping, extra_mapping], ignore_index=True)
    assert not all_mapping.duplicated(["date", "continuous_symbol_vt"]).any()
    nonempty = all_mapping.loc[all_mapping.main_contract_vt.ne("")]
    first_listed = nonempty.groupby("continuous_symbol_vt").date.min().to_dict()
    mains = {(row.date, row.continuous_symbol_vt): row.main_contract_vt
             for row in nonempty.loc[nonempty.date.between(PREWARM, END), MAPPING_COLUMNS].itertuples(index=False)}
    calendar = sorted(set(original_mapping.date))
    forward = set(pd.read_csv(ADMITTED / "forward_calendar.csv").date)
    guard_calendar = sorted(set(calendar) | forward)
    original_bars = pd.read_csv(ADMITTED / "physical_epoch_daily.csv", usecols=BAR_COLUMNS)
    extra_bars = pd.read_csv(MARKET / "added_bars.csv", usecols=BAR_COLUMNS)
    records = pd.concat([frame.loc[frame.date.between(PREWARM, END), BAR_COLUMNS]
                         for frame in (original_bars, extra_bars)], ignore_index=True)
    assert records.volume.gt(0).all()
    symbols, by_epoch = {}, {}
    for row in records.itertuples(index=False):
        bar = Bar(row.vt_symbol, row.contract_epoch_id, *map(cents, (row.open, row.high, row.low, row.close)))
        assert (row.date, bar.epoch) not in by_epoch and (row.date, bar.symbol) not in symbols
        symbols[row.date, bar.symbol] = by_epoch[row.date, bar.epoch] = bar

    specs = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    for key, fields in load_json(MARKET / "added_specs.json").items():
        assert not specs[key].keys() & fields.keys()
        specs[key].update(fields)
    assert not any(specs["rates"].values())
    return [day for day in calendar if day <= END], guard_calendar, mains, symbols, by_epoch, specs, first_listed


def reconcile(folder, start, config, calendar, guard_calendar, mains, symbols, by_epoch, settings, weeks, week_index, weekly_bar):
    products = config["products"]
    dates = [day for day in calendar if day >= start]
    assert dates[0] >= start and dates[-1] == END
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
        this_week = week_index[day]
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
                    protection = weekly_bar(old_main.epoch, this_week - 1) if old_main else None
                    if current and day >= guard(current):
                        gaps.append((day, product, main, "roll_target_delivery_guard"))
                    elif (old_bar and current and protection and current.epoch == old_main.epoch
                          and current.high > current.low):
                        side, number, entered = held.side, held.number, held.entered
                        close_position(day, product, old_bar, "roll_close", yesterday)
                        positions[product] = Holding(current, side, number, entered, current.op)
                        fill(day, product, current, side, number, "roll_open", yesterday,
                             protection.low if side == 1 else protection.high)
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
            if product in orders or day != weeks[this_week][-1]:
                continue
            reversing = None
            if held:
                current = weekly_bar(held.bar.epoch, this_week) if current else None
                prev = weekly_bar(held.bar.epoch, this_week - 1)
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
            bars = [weekly_bar(current.epoch, this_week - offset) for offset in range(21)] if current else [None] * 21
            current, prev, older = bars[:3]
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
        actual = table(folder, name)
        if actual.empty:
            assert not expected, (folder, name)
            continue
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
        assert by_epoch[END, holding.bar.epoch].close == holding.mark
        terminal_value[holding.number] = holding.side * holding.mark * settings["sizes"][holding.bar.symbol]
    for section, expected in (("pending", orders), ("pending_reversals", reversals)):
        normalized = {product: (*order[:4], cents(float(order[4]))) for product, order in terminal[section].items()}
        assert normalized == {product: (order.action, END, order.bar.symbol, order.bar.epoch, order.stop)
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




def metrics(folder, marks, opening, pending):
    daily, fills, cycles = (table(folder, name) for name in ("daily", "fills", "cycles"))
    equity = marks.equity
    prior = np.r_[CAPITAL, equity.iloc[:-1]]
    net = equity.iat[-1] - CAPITAL
    near(net, float(cycles.net_pnl.sum()))
    near(equity - prior, daily.net_pnl)
    drawdown = equity / np.maximum.accumulate(np.r_[CAPITAL, equity])[1:] - 1
    near(drawdown, daily.drawdown)
    returns = equity / prior - 1
    sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(252) if returns.std(ddof=1) else None
    margin_ratio = marks.margin / equity
    near(margin_ratio, daily.margin_ratio)
    annual = table(folder, "annual")
    assert annual.date.tolist() == [2022]
    near(annual.net_pnl, [net])
    close_free = (equity - marks.margin).round(8)
    open_free = opening.free_equity.round(8)
    open_gap = set(opening.loc[open_free.lt(0), "date"])
    close_gap = set(daily.loc[close_free.lt(0), "date"])
    closed = cycles[cycles.exit_day.ne("")]
    wins = closed.loc[closed.net_pnl.gt(0), "net_pnl"]
    losses = -closed.loc[closed.net_pnl.lt(0), "net_pnl"]
    performance = dict(
        equity=equity.iat[-1], net_pnl=net, return_pct=100 * net / CAPITAL, max_dd_pct=100 * drawdown.min(),
        sharpe=sharpe, closed_cycles=len(closed), wins=len(wins), losses=len(losses),
        win_rate_pct=100 * len(wins) / len(closed) if len(closed) else None,
        fills=len(fills), slippage=marks.cumulative_slippage.iat[-1], commission=marks.cumulative_commission.iat[-1],
    )
    result = dict(
        **performance,
        gold_net_pnl=float(cycles.loc[cycles["product"].eq("au.SHFE"), "net_pnl"].sum()),
        peak_close_margin=marks.margin.max(), peak_open_margin=opening.margin.max(),
        min_close_free_equity=close_free.min(), min_open_free_equity=open_free.min(),
        close_deficit_days=len(close_gap), opening_deficit_days=len(open_gap), deficit_days=len(open_gap | close_gap),
        first_deficit=min(open_gap | close_gap, default=""), max_shortfall=max(0, -min(close_free.min(), open_free.min())),
        minimum_close_equity=equity.min(), max_close_positions=int(marks.positions.max()),
        open_positions=int(marks.positions.iat[-1]),
    )
    def strict_constant(value):
        raise ValueError(f"non-JSON number in {folder.name}/summary.json: {value}")

    summary = json.loads((folder / "summary.json").read_text(), parse_constant=strict_constant)
    assert (summary["start"], summary["end"], summary["days"], summary["initial"]) == (
        daily.date.iat[0], END, len(daily), CAPITAL)
    assert summary["gaps"] == dict(Counter(table(folder, "gaps").reason))
    expected = dict(
        **performance, pending_signals=pending, days_margin_above_equity=len(close_gap),
        peak_margin=marks.margin.max(), peak_margin_ratio_pct=100 * margin_ratio.max(),
        open_positions=result["open_positions"], one_price_exits=int(fills.one_price.sum()),
        rolls=int(fills.reason.eq("roll_open").sum()), payoff=wins.mean() / losses.mean() if len(wins) and len(losses) else None,
        profit_factor=wins.sum() / losses.sum() if len(losses) else None,
        net_pnl_double_slippage_same_path=net - performance["slippage"],
        long_pnl=float(cycles.loc[cycles.direction.eq(1), "net_pnl"].sum()),
        short_pnl=float(cycles.loc[cycles.direction.eq(-1), "net_pnl"].sum()),
        terminal_open_net_pnl=float(cycles.loc[cycles.exit_day.eq(""), "net_pnl"].sum()),
    )
    for key, value in expected.items():
        if value is None:
            assert summary[key] is None, (folder, key, summary[key])
        else:
            near(summary[key], value)
    totals = dict(
        days=len(daily), fills=len(fills), cycles=len(cycles), closed_cycles=len(closed), opening_snapshots=len(opening),
        signals=len(table(folder, "signals")), one_price_exits=int(fills.one_price.sum()),
        entries=int(fills.reason.eq("entry").sum()), stops=int(fills.reason.eq("weekly_stop").sum()),
        rolls=int(fills.reason.eq("roll_open").sum()), guard_exits=int(fills.reason.eq("delivery_guard_exit").sum()),
        open_positions=result["open_positions"], pending_signals=pending,
    )
    return result, totals


def verify_shared_book(start_2022, shared, marks):
    checks = Counter()
    for name in ("fills", "signals", "entry_filter", "week_body_filter", "gaps", "four_up_blocks"):
        reference = read_csv(start_2022, name)
        reference = reference.loc[reference.date.le(END)]
        for product in shared:
            before = reference.loc[reference["product"].eq(product)].drop(columns="cycle", errors="ignore")
            after = table(RESULT / product, name).drop(columns="cycle", errors="ignore")
            if before.empty:
                assert after.empty
            else:
                before, after = before.reset_index(drop=True), after.reset_index(drop=True)
                nullable = {"stop", "older_close", "ma5_slope", "ma10_slope", "ma20_slope"}
                for frame in (before, after):
                    for field in nullable.intersection(frame.columns):
                        frame[field] = pd.to_numeric(frame[field].mask(frame[field].eq("")))
                pd.testing.assert_frame_equal(before, after, check_dtype=False, check_exact=False, rtol=0, atol=1e-9)
            checks[name] += len(after)
    total = sum(marks[product] for product in shared)
    reference = read_csv(start_2022, "daily").loc[lambda frame: frame.date.le(END), DAY_COLUMNS].copy()
    assert len(reference) == len(total) == 242
    total[["equity", "cash"]] -= CAPITAL * (len(shared) - 1)
    near(total, reference)
    return dict(checks, shared_products=len(shared), daily=242)


def audit():
    count = check_manifest(RESULT)
    check_manifest(HALF)
    receipt = load_json(RESULT / "receipt.json")
    approved = load_json(MARKET / "receipt.json")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_2020_stage046_s44_individual_2022_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage046_s44_individual_2022.py")
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    products = receipt["products"]
    assert products == approved["products"] and len(set(products)) == 44
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(products)
    assert (receipt["attempted"], receipt["completed"], receipt["unknown"], receipt["start"],
            receipt["end"], receipt["capital"]) == (44, 44, 0, START, END, CAPITAL)
    pins = receipt["market_sha256"]
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    universe = pd.read_csv(next(Path(path) for path in pins if path.endswith("stage020_universe.csv")))
    assert set(universe.product_vt_symbol) == set(products) and universe.eligible.eq(1).all()
    reference = HALF / START
    known = load_json(reference / "inputs.json")
    assert all(sha(Path(path)) == digest for path, digest in known["source_sha256"].items())
    comparison = table(RESULT, "product_metrics").set_index("product", verify_integrity=True)
    assert set(comparison.index) == set(products)
    market = raw_market()
    calendar, guard_calendar, mains, symbols, by_epoch, settings, first_listed = market
    weeks = completed_weeks(guard_calendar, by_epoch)
    sessions = [day for day in calendar if day >= START]
    assert len(sessions) == 242 and sessions[0] == "2022-01-04"
    totals, gaps, branches = Counter(), Counter(), Counter()
    delayed, rows, marks, absent = [], [], {}, []
    for product in products:
        folder = RESULT / product
        config = load_json(folder / "inputs.json")
        assert config == {**known, "products": [product], "end": END, "inputs_sha256": pins}
        valuations, opening, cycles, pending, conditional, affected, delayed_stops = reconcile(
            folder, START, config, *market[:-1], *weeks)
        performance, counts = metrics(folder, valuations, opening, pending)
        assert int(valuations.positions.max()) <= 1
        mapped = [day for day in sessions if (day, product) in mains]
        missing = [day for day in mapped if (day, mains[day, product]) not in symbols]
        for day in missing:
            absent.append(dict(day=day, product=product, main=mains[day, product]))
        status = "traded" if counts["fills"] else "no_fills" if mapped else "not_listed"
        if status == "not_listed":
            assert first_listed[product] > END
        result = dict(product=product, status=status, start=sessions[0], end=END, mapped_days=len(mapped),
                      main_bars_missing=len(missing), **performance)
        observed = comparison.loc[product]
        assert set(observed.index) == set(result) - {"product"}
        for key, value in result.items():
            if key == "product":
                continue
            if value is None:
                assert observed[key] == ""
            elif isinstance(value, str):
                assert observed[key] == value, (product, key)
            elif isinstance(observed[key], str):
                near(float(observed[key]), value)
            else:
                near(observed[key], value)
        rows.append(result)
        marks[product] = valuations
        totals.update(counts)
        gaps.update(table(folder, "gaps").reason)
        branches.update(affected)
        delayed.extend(delayed_stops)
        print(product, status, performance["net_pnl"], counts["fills"], flush=True)
    ranking = sorted(rows, key=lambda row: (-row["net_pnl"], row["product"]))
    assert comparison.index.tolist() == [row["product"] for row in ranking]
    shared = verify_shared_book(reference, known["products"], marks)
    no_trade = {row["product"]: dict(status=row["status"], first_mapped=first_listed[row["product"]],
                                    mapped_days=row["mapped_days"]) for row in rows if row["status"] != "traded"}
    result = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=44, completed=len(rows), unknown=0,
        manifest_entries=count, manifest_sha256=sha(RESULT / "SHA256SUMS"),
        pinned_market_inputs=len(pins), pinned_strategy_inputs=len(known["source_sha256"]),
        checked_rows=dict(totals), shared_S19_ledger_crosscheck=shared,
        status_counts=dict(Counter(row["status"] for row in rows)), no_trade_products=no_trade,
        missing_mapped_bars=absent, gap_reasons=dict(gaps), execution_branches=dict(branches),
        delayed_stop_rows=delayed, positive=int(sum(row["net_pnl"] > 0 for row in rows)),
        negative=int(sum(row["net_pnl"] < 0 for row in rows)),
        flat=int(sum(row["net_pnl"] == 0 for row in rows)),
        funding_deficit_accounts=sum(row["deficit_days"] > 0 for row in rows),
        top_five=[dict(product=row["product"], net_pnl=float(row["net_pnl"])) for row in ranking[:5]],
        bottom_five=[dict(product=row["product"], net_pnl=float(row["net_pnl"])) for row in ranking[-5:]],
        limitations=[
            "44 fixed retrospective pool, with no in-sample tuning; 2022 results describe that one period.",
            "Standalone accounts use independent capital and physical close marks. Summed values do not model a shared account.",
            "Static margin, zero commissions, and theoretical open prints; no exchange queue simulation.",
            "Unavailable physical bars remain gaps; no prices imputed.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(result, flush=True)


if __name__ == "__main__":
    audit()
