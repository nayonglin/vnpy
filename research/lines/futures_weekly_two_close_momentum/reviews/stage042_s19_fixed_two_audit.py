"""Reconstruct Stage042's two-lot books from physical open/close bars and execution tape."""
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import (
    ADMITTED, CAPITAL, DAY_COLUMNS, FULL, HALF, HISTORY, LINE, OPEN_COLUMNS, OUT, TARGET,
    cents, check_manifest, load_json, near, physical_prices, read_csv, sha,
)

CURRENT = LINE / "outputs/stage042_s19_fixed_two_20261104"
COMPLETED_GRID = LINE / "outputs/stage041_complete_halfyear_20261104"
STARTS = [f"{year}-{month}-01" for year in range(2015, 2027) for month in ("01", "07")]
ADDED = "2015-07-01"
LOTS = 2
STAGE041_AUDIT_SHA = "7b13eba47e0ab69f11409295f142a240863c6791e961afaa1de9e6235319f96c"


def baseline_folder(start):
    if start == STARTS[0]:
        return FULL
    if start == ADDED:
        return COMPLETED_GRID / start / "s19"
    return HALF / start


def reconcile(folder, start, calendar, prices, settings):
    fills = read_csv(folder, "fills")
    daily = read_csv(folder, "daily")
    opening = read_csv(folder, "opening_funding")
    cycles = read_csv(folder, "cycles")
    assert daily.date.tolist() == [day for day in calendar if day >= start]
    assert fills.date.min() > daily.date.iat[0]
    assert fills.signal_day.min() >= daily.date.iat[0]
    assert (daily.iloc[0][DAY_COLUMNS] == [CAPITAL, CAPITAL, 0, 0, 0, 0, 0]).all()
    by_day = {day: list(frame.itertuples(index=False)) for day, frame in fills.groupby("date", sort=False)}
    margin_rates = {key: int(Decimal(str(value)) * 10_000) for key, value in settings["margin_ratios"].items()}
    cash = CAPITAL * 100
    slippage = commission = 0
    holdings = {}
    flows = defaultdict(int)
    entries, exits = {}, {}
    day_marks, opening_marks = [], []

    def mark_positions(day, index):
        position_value = margin_units = 0
        for entry, last_mark in holdings.values():
            physical = prices.get((day, entry.epoch))
            mark = physical[index] if physical is not None else last_mark
            notional = mark * entry.size * entry.volume
            position_value += notional * entry.side
            margin_units += notional * margin_rates[entry.contract]
        return position_value, margin_units

    def snapshot(day, sequence, product="", reason="before_fills"):
        value, units = mark_positions(day, 0)
        equity, margin = (cash + value) / 100, units / 1_000_000
        opening_marks.append((day, sequence, product, reason, equity, margin, equity - margin, len(holdings)))

    for day in daily.date:
        snapshot(day, 0)
        prev_fill = None
        for sequence, fill in enumerate(by_day.get(day, ()), 1):
            physical_open, _, symbol, one_price = prices[day, fill.epoch]
            assert (fill.contract, cents(fill.price), fill.one_price) == (symbol, physical_open, one_price)
            assert (fill.volume, fill.size) == (LOTS, settings["sizes"][symbol]) and fill.side in (-1, 1)
            amount = physical_open * fill.size * LOTS
            trade_slip = cents(settings["slippages"][symbol] * fill.size * LOTS)
            trade_commission = cents(fill.price * fill.size * LOTS * settings["rates"][symbol])
            assert (cents(fill.slippage), cents(fill.commission)) == (trade_slip, trade_commission)
            flow = -fill.side * amount - trade_slip - trade_commission
            cash += flow
            flows[fill.cycle] += flow
            slippage += trade_slip
            commission += trade_commission

            if fill.reason in ("entry", "roll_open"):
                assert fill.product not in holdings
                if fill.reason == "entry":
                    assert fill.cycle not in entries
                    entries[fill.cycle] = fill
                else:
                    assert prev_fill is not None
                    assert (prev_fill.reason, prev_fill.product, prev_fill.cycle, prev_fill.side) == (
                        "roll_close", fill.product, fill.cycle, -fill.side)
                holdings[fill.product] = fill, physical_open
            else:
                assert fill.reason in ("roll_close", "delivery_guard_exit", "weekly_stop")
                previous, _ = holdings.pop(fill.product)
                assert (previous.epoch, previous.side, previous.cycle, previous.volume) == (
                    fill.epoch, -fill.side, fill.cycle, LOTS)
                if fill.reason != "roll_close":
                    assert fill.cycle not in exits
                    exits[fill.cycle] = day
            snapshot(day, sequence, fill.product, fill.reason)
            prev_fill = fill
        value, units = mark_positions(day, 1)
        day_marks.append(((cash + value) / 100, cash / 100, value / 100, units / 1_000_000,
                          len(holdings), slippage / 100, commission / 100))
        for product, (entry, last_mark) in holdings.items():
            physical = prices.get((day, entry.epoch))
            holdings[product] = entry, physical[1] if physical is not None else last_mark

    daily_marks = pd.DataFrame(day_marks, columns=DAY_COLUMNS)
    open_marks = pd.DataFrame(opening_marks, columns=OPEN_COLUMNS)
    near(daily[DAY_COLUMNS], daily_marks)
    pd.testing.assert_frame_equal(opening.iloc[:, :4], open_marks.iloc[:, :4])
    near(opening.iloc[:, 4:], open_marks.iloc[:, 4:])
    assert len(opening) == len(daily) + len(fills)

    terminal = load_json(folder / "terminal.json")
    assert not terminal["pending"] and not terminal["pending_reversals"]
    assert set(terminal["positions"]) == set(holdings)
    final_marks = {}
    for product, (entry, price) in holdings.items():
        observed = terminal["positions"][product]
        assert (observed["epoch"], observed["symbol"], observed["cycle"], observed["side"],
                cents(observed["mark"])) == (entry.epoch, entry.contract, entry.cycle, entry.side, price)
        assert prices[TARGET, entry.epoch][1] == price
        final_marks[entry.cycle] = entry.side * price * entry.size * LOTS
    assert set(cycles.cycle) == set(entries) and len(cycles) == len(entries)
    assert set(cycles.loc[cycles.exit_day.ne(""), "cycle"]) == set(exits)
    for cycle in cycles.itertuples(index=False):
        entry = entries[cycle.cycle]
        assert (cycle.product, cycle.direction, cycle.entry_day, cycle.exit_day) == (
            entry.product, entry.side, entry.date, exits.get(cycle.cycle, ""))
        flow = flows[cycle.cycle]
        mark = final_marks.get(cycle.cycle, 0)
        assert (cents(cycle.cash_flow), cents(cycle.terminal_mark), cents(cycle.net_pnl)) == (flow, mark, flow + mark)

    equity = daily_marks.equity
    prev_equity = np.r_[CAPITAL, equity.iloc[:-1]]
    net_pnl = equity.iat[-1] - CAPITAL
    drawdown = equity / np.maximum.accumulate(np.r_[CAPITAL, equity])[1:] - 1
    returns = equity / prev_equity - 1
    near(net_pnl, cycles.net_pnl.sum())
    near(equity - prev_equity, daily.net_pnl)
    near(drawdown, daily.drawdown)
    near(daily_marks.margin / equity, daily.margin_ratio, atol=1e-10)
    annual = pd.Series(equity - prev_equity).groupby(daily.date.str[:4]).sum()
    annual_csv = read_csv(folder, "annual")
    assert annual.index.tolist() == annual_csv.date.astype(str).tolist()
    near(annual, annual_csv.net_pnl)

    close_free = (equity - daily_marks.margin).round(8)
    open_free = open_marks.free_equity.round(8)
    close_gap = set(daily.loc[close_free.lt(0), "date"])
    open_gap = set(open_marks.loc[open_free.lt(0), "date"])
    gap = close_gap | open_gap
    nonpositive = set(daily.loc[equity.le(0), "date"]) | set(open_marks.loc[open_marks.equity.le(0), "date"])
    closed = cycles[cycles.exit_day.ne("")]
    wins, losses = closed.net_pnl.gt(0).sum(), closed.net_pnl.lt(0).sum()
    performance = dict(
        equity=equity.iat[-1], net_pnl=net_pnl, return_pct=100 * net_pnl / CAPITAL, max_dd_pct=100 * drawdown.min(),
        sharpe=returns.mean() / returns.std(ddof=1) * np.sqrt(252), closed_cycles=len(closed), wins=wins,
        losses=losses, win_rate_pct=100 * wins / len(closed), fills=len(fills), slippage=slippage / 100,
        commission=commission / 100,
    )
    summary = load_json(folder / "summary.json")
    summary_values = dict(
        **performance, initial=CAPITAL, days=len(daily), days_margin_above_equity=len(close_gap),
        peak_margin=daily_marks.margin.max(), open_positions=len(holdings), pending_signals=0,
        net_pnl_double_slippage_same_path=net_pnl - slippage / 100,
        one_price_exits=int(fills.one_price.sum()), rolls=int(fills.reason.eq("roll_open").sum()),
        long_pnl=cycles.loc[cycles.direction.eq(1), "net_pnl"].sum(),
        short_pnl=cycles.loc[cycles.direction.eq(-1), "net_pnl"].sum(),
        terminal_open_net_pnl=cycles.loc[cycles.exit_day.eq(""), "net_pnl"].sum(),
    )
    assert (summary["start"], summary["end"]) == (daily.date.iat[0], TARGET)
    assert summary["gaps"] == dict(Counter(read_csv(folder, "gaps").reason))
    for key, value in summary_values.items():
        near(summary[key], value)
    max_positions = int(daily_marks.positions.max())
    metrics = dict(
        first_session=daily.date.iat[0], last_session=TARGET, days=len(daily), **performance,
        opening_deficit_days=len(open_gap), close_deficit_days=len(close_gap), deficit_days=len(gap),
        first_deficit=min(gap, default=""), max_shortfall=max(0.0, -min(open_free.min(), close_free.min())),
        peak_opening_margin=open_marks.margin.max(), peak_close_margin=daily_marks.margin.max(),
        nonpositive_equity_days=len(nonpositive), minimum_equity=min(equity.min(), open_marks.equity.min()),
        max_positions=max_positions, max_lots=LOTS * max_positions,
    )
    counts = dict(daily=len(daily), opening=len(opening), fills=len(fills), cycles=len(cycles),
                  signals=len(read_csv(folder, "signals")), terminal_positions=len(holdings))
    return metrics, counts


def compare_frozen_one_lot(original, new):
    for name in ("signals.csv", "gaps.csv", "entry_filter.csv", "week_body_filter.csv", "four_up_blocks.csv",
                 "terminal.json"):
        assert (original / name).read_bytes() == (new / name).read_bytes(), (new, name)
    before, after = (read_csv(folder, "fills") for folder in (original, new))
    assert before.volume.eq(1).all() and after.volume.eq(LOTS).all()
    for field in ("volume", "slippage", "commission"):
        before[field] *= LOTS
    pd.testing.assert_frame_equal(before, after, rtol=0, atol=1e-7)
    before, after = (read_csv(folder, "cycles") for folder in (original, new))
    for field in ("cash_flow", "terminal_mark", "net_pnl"):
        before[field] *= LOTS
    pd.testing.assert_frame_equal(before, after, rtol=0, atol=1e-7)
    before, after = (read_csv(folder, "daily") for folder in (original, new))
    assert before.date.equals(after.date) and before.positions.equals(after.positions)
    for field in ("equity", "cash", "position_value", "margin", "net_pnl", "cumulative_slippage",
                  "cumulative_commission"):
        anchor = CAPITAL if field in ("cash", "equity") else 0
        near(after[field], anchor + LOTS * (before[field] - anchor))


def audit():
    parents = [FULL, HALF, OUT, COMPLETED_GRID]
    parent_entries = {parent.name: check_manifest(parent) for parent in parents}
    file_count = check_manifest(CURRENT)
    receipt = load_json(CURRENT / "receipt.json")
    assert receipt["stage041_manifest_sha256"] == sha(COMPLETED_GRID / "SHA256SUMS")
    prev_audit = LINE / "reviews/stage041_complete_halfyear_audit.json"
    assert sha(prev_audit) == STAGE041_AUDIT_SHA
    assert load_json(prev_audit)["current_manifest_sha256"] == receipt["stage041_manifest_sha256"]
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_1925_stage042_s19_fixed_two_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage042_s19_fixed_two.py")
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["cutoff"], receipt["capital"], receipt["fixed_entry_lots"], receipt["starts"]) == (
        TARGET, CAPITAL, LOTS, STARTS)
    assert (receipt["attempted"], receipt["completed"], receipt["unknown"]) == (24, 24, 0)
    assert {path.name for path in CURRENT.iterdir() if path.is_dir()} == set(STARTS)
    config = load_json(FULL / "inputs.json")
    assert receipt["products"] == config["products"] and len(receipt["products"]) == 19
    assert receipt["products"].count("au.SHFE") == 1
    assert receipt["market_sha256"] == config["inputs_sha256"]
    pins = config["source_sha256"] | config["inputs_sha256"]
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    prices = physical_prices()
    calendar = sorted(set(pd.read_csv(ADMITTED / "mapping.csv", usecols=["date"]).date)) + [TARGET]
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    combined = read_csv(CURRENT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == STARTS
    totals = Counter()
    windows = []
    for start in STARTS:
        original, new = baseline_folder(start), CURRENT / start
        config_for_window = {**config, "start": start}
        assert load_json(original / "inputs.json") == config_for_window
        assert load_json(new / "inputs.json") == {**config_for_window, "fixed_entry_lots": LOTS}
        compare_frozen_one_lot(original, new)
        metrics, counts = reconcile(new, start, calendar, prices, settings)
        row = combined.loc[start]
        assert set(row.index) == set(metrics)
        for key, value in metrics.items():
            if isinstance(value, str):
                assert row[key] == value, (start, key)
            else:
                near(row[key], value)
        totals.update(counts)
        windows.append(dict(
            start=start, deficit_days=int(metrics["deficit_days"]),
            nonpositive_equity_days=int(metrics["nonpositive_equity_days"]),
            max_shortfall=float(metrics["max_shortfall"]), minimum_equity=float(metrics["minimum_equity"]),
        ))
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_sha256=sha(CURRENT / "SHA256SUMS"), manifest_entries=file_count,
        parent_manifest_entries=parent_entries, pinned_inputs=len(pins), checked_rows=dict(totals),
        deficit_windows=sum(row["deficit_days"] > 0 for row in windows),
        nonpositive_windows=sum(row["nonpositive_equity_days"] > 0 for row in windows), windows=windows,
        limitations=["Frozen static margin and positive-volume open print proxies, with zero commission",
                     "Signals and theoretical fills continue through cash shortfalls and nonpositive equity",
                     "Drawdown below -100% marks nonpositive equity, where percentage returns and Sharpe lose economic meaning",
                     "Baseline terminal JSON omits a volume field; terminal lots are derived from matched execution tape",
                     "Overlapping historical windows"],
    )
    with Path(__file__).with_suffix(".json").open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print({key: value for key, value in report.items() if key != "windows"})


if __name__ == "__main__":
    audit()
