"""Re-run the fixed one-lot S19 account with RMB 150,000 and check funding."""
import argparse
from collections import defaultdict
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import run_weekly_portfolio as portfolio
from stage034_s19_monte_carlo import cents
from run_stage021_multicycle import write_checksums
from stage033_s19_annual_starts import LINE, MARKET, TARGET, extend, load
from stage035_s19_half_pct import TAIL
from stage036_s19_paired_mc import SIZING, SIZING_SHA, verify_manifest

CAPITAL = 150_000
DESIGN = LINE / "stages/20261104_1743_stage037_s19_fixed_one_150k_design.md"
AUDIT = LINE / "reviews/stage035_s19_half_pct_audit.json"
AUDIT_SHA = "6b80c05b2535a44df0479c4d0bb37a97d79f080324a5602752a1eb90a00d64e8"


def reconstruct_opening(daily, fills, market):
    by_epoch, specs = market[5], market[7]
    orders = defaultdict(list)
    for fill in fills.itertuples(index=False):
        orders[fill.date].append(fill)
    positions, snapshots = {}, []
    cash = CAPITAL

    def mark(day, at_open):
        value = margin = 0.0
        for fill, previous_mark in positions.values():
            bar = by_epoch.get((day, fill.epoch))
            price = (bar.open if at_open else bar.close) if bar is not None else previous_mark
            notional = price * fill.size
            value += fill.side * notional
            margin += notional * specs["margin_ratios"][fill.contract]
        return value, margin

    def snapshot(day, index, product="", reason="before_fills"):
        value, margin = mark(day, at_open=True)
        equity = cash + value
        snapshots.append(dict(date=day, fill_sequence=index, product=product, reason=reason,
                              equity=round(equity, 8), margin=round(margin, 8),
                              free_equity=round(equity - margin, 8), positions=len(positions)))

    for record in daily.itertuples(index=False):
        day = record.date
        snapshot(day, 0)
        for index, fill in enumerate(orders[day], 1):
            bar = by_epoch[day, fill.epoch]
            if fill.volume != 1 or fill.price != bar.open or fill.size != specs["sizes"][fill.contract]:
                raise ValueError(f"invalid physical fill {day}/{index}")
            cash -= fill.side * fill.size * fill.price + fill.slippage + fill.commission
            if fill.reason in ("entry", "roll_open"):
                if fill.product in positions:
                    raise ValueError(f"duplicate holding {day}/{index}")
                positions[fill.product] = fill, fill.price
            else:
                old, _ = positions.pop(fill.product)
                if (fill.side, fill.epoch, fill.cycle) != (-old.side, old.epoch, old.cycle):
                    raise ValueError(f"invalid close leg {day}/{index}")
            snapshot(day, index, fill.product, fill.reason)
        value, margin = mark(day, at_open=False)
        if (len(positions) != record.positions
                or not np.allclose([cash, value, margin, cash + value],
                                   [record.cash, record.position_value, record.margin, record.equity],
                                   atol=1e-6, rtol=0)):
            raise ValueError(f"daily reconciliation failed {day}")
        for product, (fill, previous_mark) in positions.items():
            bar = by_epoch.get((day, fill.epoch))
            positions[product] = fill, bar.close if bar is not None else previous_mark
    return pd.DataFrame(snapshots)


def run(output):
    verify_manifest(SIZING, SIZING_SHA)
    if portfolio.sha(AUDIT) != AUDIT_SHA:
        raise ValueError("unexpected Stage035 independent audit")
    market = extend(load(MARKET, control=True), TAIL)
    control = SIZING / "fixed_one"
    fixed_inputs = json.loads((control / "inputs.json").read_text())
    fixed_inputs.pop("source_sha256")
    if {str(path): digest for path, digest in market[-1].items()} != fixed_inputs["inputs_sha256"]:
        raise ValueError("market data differ from Stage035")
    with patch.object(portfolio, "INITIAL", CAPITAL), redirect_stdout(StringIO()):
        portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = json.loads((output / "inputs.json").read_text())
    inputs.pop("source_sha256")
    if inputs != {**fixed_inputs, "initial": CAPITAL}:
        raise ValueError("configuration changes beyond initial capital")
    for name in ("fills.csv", "signals.csv", "cycles.csv", "gaps.csv", "terminal.json",
                 "entry_filter.csv", "four_up_blocks.csv"):
        if (control / name).read_bytes() != (output / name).read_bytes():
            raise ValueError(f"unexpected trade path change in {name}")
    daily = pd.read_csv(output / "daily.csv")
    baseline = pd.read_csv(control / "daily.csv")
    same = ["date", "positions", "margin", "cumulative_slippage", "cumulative_commission"]
    if (not daily[same].equals(baseline[same])
            or not np.array_equal(cents(daily.net_pnl), cents(baseline.net_pnl))
            or not np.allclose(baseline.equity - daily.equity, fixed_inputs["initial"] - CAPITAL,
                               atol=1e-6, rtol=0)):
        raise ValueError("unexpected daily path change")
    opening = reconstruct_opening(daily, pd.read_csv(output / "fills.csv"), market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    free = daily.equity - daily.margin
    risk = dict(
        max_positions=int(daily.positions.max()),
        close_margin_deficit_days=int(free.lt(0).sum()),
        close_min_free_equity=float(round(free.min(), 8)),
        close_min_free_equity_date=daily.loc[free.idxmin(), "date"],
        opening_snapshots=len(opening),
        opening_margin_deficit_days=int(opening.loc[opening.free_equity.lt(0), "date"].nunique()),
        opening_min_free_equity=opening.free_equity.min(),
        opening_min_free_equity_date=opening.loc[opening.free_equity.idxmin(), "date"],
        opening_peak_margin_ratio_pct=100 * (opening.margin / opening.equity).max(),
        peak_drawdown_date=daily.loc[daily.drawdown.idxmin(), "date"],
        minimum_equity=daily.equity.min(),
        minimum_equity_date=daily.loc[daily.equity.idxmin(), "date"],
    )
    (output / "funding_summary.json").write_text(json.dumps(risk, indent=2) + "\n")
    receipt = dict(parent_manifest_sha256=SIZING_SHA, parent_audit_sha256=AUDIT_SHA,
                   design_sha256=portfolio.sha(DESIGN), entrypoint_sha256=portfolio.sha(Path(__file__)),
                   cutoff=TARGET, only_initial_capital_changed=True, trade_path_matched=True,
                   market_sha256=inputs["inputs_sha256"])
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.iterdir() if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
