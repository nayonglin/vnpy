"""Independently reconstruct both frozen Stage040 portfolios from physical prices and fills."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
FULL = LINE / "outputs/stage037_s19_fixed_one_150k_20261104"
HALF = LINE / "outputs/stage038_s19_fixed_one_150k_halfyear_20261104"
OUT = LINE / "outputs/stage040_s19_without_gold_20261104"
HISTORY = LINE.parent / "futures_weekly19_stop_reversal/outputs"
ADMITTED = HISTORY / "stage002_data/data_approved"
TAIL = LINE / "outputs/stage033_s19_data/attempt002/provider/raw_daily.csv"
TARGET = "2026-11-04"
GOLD = "au.SHFE"
CAPITAL = 150_000
STARTS = ["2015-01-01", *(f"{year}-{month}-01" for year in range(2016, 2027) for month in ("01", "07"))]
DAY_COLUMNS = ["equity", "cash", "position_value", "margin", "positions", "cumulative_slippage",
               "cumulative_commission"]
OPEN_COLUMNS = ["date", "fill_sequence", "product", "reason", "equity", "margin", "free_equity", "positions"]


def load_json(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_manifest(directory):
    expected = {}
    for record in (directory / "SHA256SUMS").read_text().splitlines():
        digest, file_name = record.split(maxsplit=1)
        assert file_name not in expected and digest == sha(directory / file_name), (directory, file_name)
        expected[file_name] = digest
    present = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()}
    assert present == {*expected, "SHA256SUMS"}, directory
    return len(expected)


def cents(value):
    return int(round(value * 100))


def near(actual, expected, atol=1e-6):
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=0)


def read_csv(root, name):
    return pd.read_csv(root / (name + ".csv"), keep_default_na=False)


def physical_prices():
    columns = ["date", "contract_epoch_id", "vt_symbol", "open", "high", "low", "close"]
    history = pd.read_csv(ADMITTED / "physical_epoch_daily.csv", usecols=columns)
    epochs = pd.read_csv(ADMITTED / "physical_epochs.csv", dtype=str)
    active_epochs = epochs[epochs.contract_yyyymm.ge("202611")].set_index("vt_symbol", verify_integrity=True)
    tail = pd.read_csv(TAIL)
    tail = tail[tail.date.eq(TARGET) & tail.volume.gt(0)].copy()
    tail["contract_epoch_id"] = tail.vt_symbol.map(active_epochs.contract_epoch_id)
    data = pd.concat([history, tail[columns]], ignore_index=True)
    prices = {}
    for row in data.itertuples(index=False):
        key = (row.date, row.contract_epoch_id)
        assert key not in prices
        prices[key] = (cents(row.open), cents(row.close), row.vt_symbol, row.high == row.low)
    return prices


def audit_book(root, start, calendar, prices, settings):
    fills = read_csv(root, "fills")
    by_day = {day: list(frame.itertuples(index=False)) for day, frame in fills.groupby("date", sort=False)}
    cycles = read_csv(root, "cycles")
    daily = read_csv(root, "daily")
    opening = read_csv(root, "opening_funding")
    assert daily.date.tolist() == [day for day in calendar if day >= start]
    assert (daily.iloc[0][DAY_COLUMNS] == [CAPITAL, CAPITAL, 0, 0, 0, 0, 0]).all()
    assert fills.date.min() > daily.date.iat[0] and fills.signal_day.min() >= daily.date.iat[0]
    assert read_csv(root, "signals").date.min() >= daily.date.iat[0]
    cash = CAPITAL * 100
    gold_cash = 0
    slippage = commission = 0
    holdings, entries, exits = {}, {}, {}
    flows = defaultdict(int)
    day_marks, opening_marks, gold_marks = [], [], []
    margins = {symbol: int(Decimal(str(ratio)) * 10_000) for symbol, ratio in settings["margin_ratios"].items()}
    size = settings["sizes"]

    def value(day, mark_column):
        marked = {}
        position_value = margin_units = 0
        for product, (entry, previous_mark) in holdings.items():
            bar = prices.get((day, entry.epoch))
            mark = bar[mark_column] if bar is not None else previous_mark
            marked[product] = mark
            notional = mark * entry.size
            position_value += notional * entry.side
            margin_units += notional * margins[entry.contract]
        return position_value, margin_units, marked

    def snapshot(day, sequence, product="", reason="before_fills"):
        marked_value, units, _ = value(day, 0)
        equity = (cash + marked_value) / 100
        margin = units / 1_000_000
        opening_marks.append((day, sequence, product, reason, equity, margin, equity - margin, len(holdings)))

    for day in daily.date:
        snapshot(day, 0)
        for sequence, fill in enumerate(by_day.get(day, ()), 1):
            p, _, symbol, locked = prices[day, fill.epoch]
            assert (fill.contract, cents(fill.price), fill.volume, fill.size, fill.one_price) == (
                symbol, p, 1, size[symbol], locked)
            cost = cents(settings["slippages"][symbol] * fill.size)
            fee = cents(fill.price * fill.size * settings["rates"][symbol])
            assert (cents(fill.slippage), cents(fill.commission)) == (cost, fee)
            flow = -fill.side * p * fill.size - cost - fee
            cash += flow
            if fill.product == GOLD:
                gold_cash += flow
            slippage += cost
            commission += fee
            flows[fill.cycle] += flow
            if fill.reason in ("entry", "roll_open"):
                assert fill.product not in holdings
                holdings[fill.product] = fill, p
                if fill.reason == "entry":
                    assert fill.cycle not in entries
                    entries[fill.cycle] = fill
            else:
                previous, _ = holdings.pop(fill.product)
                assert (fill.cycle, fill.epoch, fill.side) == (previous.cycle, previous.epoch, -previous.side)
                if fill.reason != "roll_close":
                    assert fill.cycle not in exits
                    exits[fill.cycle] = day
            snapshot(day, sequence, fill.product, fill.reason)
        marked_value, units, marks = value(day, 1)
        day_marks.append(((cash + marked_value) / 100, cash / 100, marked_value / 100,
                          units / 1_000_000, len(holdings), slippage / 100, commission / 100))
        for product, (entry, _) in holdings.items():
            holdings[product] = entry, marks[product]
        if GOLD in holdings:
            gold_fill, gold_price = holdings[GOLD]
            gold_notional = gold_price * gold_fill.size
            gold_marks.append(((gold_cash + gold_notional * gold_fill.side) / 100,
                               gold_notional * margins[gold_fill.contract] / 1_000_000))
        else:
            gold_marks.append((gold_cash / 100, 0.0))

    rebuilt = pd.DataFrame(day_marks, columns=DAY_COLUMNS)
    reconstructed_open = pd.DataFrame(opening_marks, columns=OPEN_COLUMNS)
    near(daily[DAY_COLUMNS], rebuilt)
    pd.testing.assert_frame_equal(reconstructed_open.iloc[:, :4], opening.iloc[:, :4])
    near(reconstructed_open.iloc[:, 4:], opening.iloc[:, 4:])
    assert len(opening) == len(daily) + len(fills)
    terminal = load_json(root / "terminal.json")
    assert set(terminal["positions"]) == set(holdings)
    assert not terminal["pending"] and not terminal["pending_reversals"]
    final_value = {}
    for product, (entry, mark) in holdings.items():
        holding = terminal["positions"][product]
        assert (holding["cycle"], holding["epoch"], holding["side"], cents(holding["mark"])) == (
            entry.cycle, entry.epoch, entry.side, mark)
        assert mark == prices[TARGET, entry.epoch][1]
        final_value[entry.cycle] = entry.side * mark * entry.size
    assert set(cycles.cycle) == set(entries) and len(cycles) == len(entries)
    assert set(cycles.loc[cycles.exit_day.ne(""), "cycle"]) == set(exits)
    for cycle in cycles.itertuples(index=False):
        entry = entries[cycle.cycle]
        assert (cycle.product, cycle.direction, cycle.entry_day, cycle.exit_day) == (
            entry.product, entry.side, entry.date, exits.get(cycle.cycle, ""))
        flow = flows[cycle.cycle]
        mark = final_value.get(cycle.cycle, 0)
        assert (cents(cycle.cash_flow), cents(cycle.terminal_mark), cents(cycle.net_pnl)) == (flow, mark, flow + mark)

    equity = rebuilt.equity
    prev = np.r_[CAPITAL, equity.iloc[:-1]]
    drawdown = equity / np.maximum.accumulate(np.r_[CAPITAL, equity])[1:] - 1
    returns = equity / prev - 1
    net_pnl = equity.iat[-1] - CAPITAL
    near(net_pnl, cycles.net_pnl.sum())
    near(drawdown, daily.drawdown)
    near(equity - prev, daily.net_pnl)
    near(rebuilt.margin / equity, daily.margin_ratio)
    annual = pd.Series(equity - prev).groupby(daily.date.str[:4]).sum()
    assert annual.index.tolist() == read_csv(root, "annual").date.astype(str).tolist()
    near(annual, read_csv(root, "annual").net_pnl)
    free_close = (equity - rebuilt.margin).round(8)
    free_open = reconstructed_open.free_equity.round(8)
    closing = set(daily.loc[free_close.lt(0), "date"])
    op = set(reconstructed_open.loc[free_open.lt(0), "date"])
    nonpositive = set(daily.loc[equity.le(0), "date"]) | set(
        reconstructed_open.loc[reconstructed_open.equity.le(0), "date"])
    closed = cycles[cycles.exit_day.ne("")]
    wins, losses = closed.net_pnl.gt(0).sum(), closed.net_pnl.lt(0).sum()
    result = dict(
        equity=equity.iat[-1], net_pnl=net_pnl, return_pct=100 * net_pnl / CAPITAL,
        max_dd_pct=100 * drawdown.min(), sharpe=returns.mean() / returns.std(ddof=1) * np.sqrt(252),
        closed_cycles=len(closed), wins=wins, losses=losses, win_rate_pct=100 * wins / len(closed),
        fills=len(fills), slippage=slippage / 100, commission=commission / 100,
        gold_net_pnl=cycles.loc[cycles["product"].eq(GOLD), "net_pnl"].sum(),
        peak_close_margin=rebuilt.margin.max(), peak_open_margin=reconstructed_open.margin.max(),
        min_close_free_equity=free_close.min(), min_open_free_equity=free_open.min(),
        close_deficit_days=len(closing), opening_deficit_days=len(op), deficit_days=len(closing | op),
        first_deficit=min(closing | op, default=""), max_shortfall=max(0, -min(free_close.min(), free_open.min())),
        minimum_close_equity=equity.min(), max_close_positions=int(rebuilt.positions.max()),
    )
    summary = load_json(root / "summary.json")
    summary_checks = {key: result[key] for key in (
        "equity", "net_pnl", "return_pct", "max_dd_pct", "sharpe", "closed_cycles", "wins",
        "losses", "win_rate_pct", "fills", "slippage", "commission")}
    summary_checks.update(
        start=daily.date.iat[0], end=TARGET, days=len(daily), initial=CAPITAL,
        days_margin_above_equity=len(closing), peak_margin=rebuilt.margin.max(),
        open_positions=len(holdings), pending_signals=0,
    )
    assert summary["gaps"] == dict(Counter(read_csv(root, "gaps").reason))
    for key, expected in summary_checks.items():
        if isinstance(expected, str):
            assert summary[key] == expected
        else:
            near(summary[key], expected)
    counts = dict(days=len(daily), fills=len(fills), cycles=len(cycles), opening=len(opening),
                  signals=len(read_csv(root, "signals")), nonpositive_days=len(nonpositive))
    return result, counts, rebuilt, np.asarray(gold_marks)


def compare_other_products(control, candidate):
    control_cycles = read_csv(control, "cycles")
    remaining = control_cycles[control_cycles["product"].ne(GOLD)]
    cycle_map = dict(zip(remaining.cycle, range(1, len(remaining) + 1), strict=True))
    counts = {}
    for name in ("fills", "cycles", "signals", "gaps", "entry_filter", "week_body_filter", "four_up_blocks"):
        before = read_csv(control, name)
        before = before[before["product"].ne(GOLD)].reset_index(drop=True)
        after = read_csv(candidate, name)
        if "cycle" in before:
            before["cycle"] = before.cycle.map(cycle_map)
        pd.testing.assert_frame_equal(before, after)
        counts[name] = len(after)
    terminals = [load_json(folder / "terminal.json") for folder in (control, candidate)]
    for section in ("positions", "pending", "pending_reversals"):
        terminals[0][section].pop(GOLD, None)
    for value in terminals[0]["positions"].values():
        value["cycle"] = cycle_map[value["cycle"]]
    assert terminals[0] == terminals[1]
    return counts


def audit():
    sizes = {folder.name: check_manifest(folder) for folder in (FULL, HALF, OUT)}
    receipt = load_json(OUT / "receipt.json")
    assert receipt["stage037_manifest_sha256"] == sha(FULL / "SHA256SUMS")
    assert receipt["stage038_manifest_sha256"] == sha(HALF / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_1808_stage040_s19_without_gold_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage040_s19_without_gold.py")
    assert receipt["capital"] == CAPITAL and receipt["cutoff"] == TARGET
    assert (receipt["excluded_product"], receipt["starts"], receipt["attempted_runs"],
            receipt["completed_runs"], receipt["unknown_runs"]) == (GOLD, STARTS, 23, 23, 0)
    config = load_json(FULL / "inputs.json")
    assert len(config["products"]) == 19 and config["products"].count(GOLD) == 1
    assert receipt["products"] == [product for product in config["products"] if product != GOLD]
    assert config["inputs_sha256"] == receipt["market_sha256"]
    assert config["source_sha256"] == receipt["source_sha256"]
    pins = {**receipt["market_sha256"], **receipt["source_sha256"]}
    assert all(sha(Path(path)) == digest for path, digest in pins.items())
    assert {p.name for p in OUT.iterdir() if p.is_dir()} == set(STARTS)
    window = read_csv(OUT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert window.index.tolist() == STARTS
    calendar = sorted(set(pd.read_csv(ADMITTED / "mapping.csv", usecols=["date"]).date)) + [TARGET]
    prices = physical_prices()
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    totals = Counter()
    comparisons = Counter()
    audited = []
    for start in STARTS:
        control, candidate = (FULL if start == STARTS[0] else HALF / start), OUT / start
        assert load_json(control / "inputs.json") == {**config, "start": start}
        assert load_json(candidate / "inputs.json") == {**config, "start": start, "products": receipt["products"]}
        comparisons.update(compare_other_products(control, candidate))
        baseline, before_counts, before_day, gold = audit_book(control, start, calendar, prices, settings)
        without, after_counts, after_day, absent = audit_book(candidate, start, calendar, prices, settings)
        near(absent, 0)
        near(before_day.equity - after_day.equity, gold[:, 0])
        near(before_day.margin - after_day.margin, gold[:, 1])
        near(baseline["gold_net_pnl"], gold[-1, 0])
        row = window.loc[start]
        assert (row.first_session, row.last_session, row.days) == (
            next(day for day in calendar if day >= start), TARGET, len(before_day))
        for prefix, values, counts in (("s19", baseline, before_counts), ("no_gold", without, after_counts)):
            totals.update({f"{prefix}_{key}": value for key, value in counts.items()})
            for key, expected in values.items():
                observed = row[f"{prefix}_{key}"]
                if isinstance(expected, str):
                    assert expected == observed, (start, prefix, key)
                else:
                    near(observed, expected)
        audited.append(dict(start=start, s19_deficit_days=baseline["deficit_days"],
                            no_gold_deficit_days=without["deficit_days"],
                            s19_nonpositive_days=before_counts["nonpositive_days"],
                            no_gold_nonpositive_days=after_counts["nonpositive_days"]))
    result = dict(
        verdict="PASS_WITH_LIMITATIONS", windows=len(audited), unknown=0, manifest_entries=sizes,
        manifest_sha256=sha(OUT / "SHA256SUMS"), pinned_inputs=len(pins), checked_rows=dict(totals),
        unchanged_non_gold_rows=dict(comparisons), windows_funding=audited,
        limitations=["Overlapping historical windows and retrospective exclusion of gold",
                     "Static margin and simulated opening prints with zero commission",
                     "Theoretical fills continue after shortages and nonpositive equity",
                     "Sharpe is mechanically reproducible but not economically interpretable after crossing zero"],
    )
    destination = Path(__file__).with_suffix(".json")
    with destination.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print({key: value for key, value in result.items() if key != "windows_funding"})


if __name__ == "__main__":
    audit()
