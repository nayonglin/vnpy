"""Replay S19 fixed-one sizing from every requested semiannual start."""
import argparse
import csv
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import run_weekly_portfolio as portfolio
from run_stage021_multicycle import write_checksums
from stage033_s19_annual_starts import LINE, MARKET, TARGET, extend, load
from stage034_s19_monte_carlo import BASE as JANUARY_REFERENCE, BASE_SHA as JANUARY_SHA
from stage035_s19_half_pct import TAIL
from stage036_s19_paired_mc import verify_manifest
from stage037_s19_fixed_one_150k import CAPITAL, reconstruct_opening

PARENT = LINE / "outputs/stage037_s19_fixed_one_150k_20261104"
PARENT_SHA = "7761f0f90ef0eb9d727ec4ec42541b19757f7a7905cad2dd9be654ca7ac73128"
PARENT_AUDIT = LINE / "reviews/stage037_s19_fixed_one_150k_audit.json"
PARENT_AUDIT_SHA = "2cbf6a9469608660b5b9b2a53c13f9a8daaa3be6aec16d8d4027996410b2ada3"
DESIGN = LINE / "stages/20261104_1751_stage038_s19_fixed_one_150k_halfyear_design.md"
STARTS = tuple(f"{year}-{month}-01" for year in range(2016, 2027) for month in ("01", "07"))


def replay(output, start, market, parent_inputs):
    with patch.object(portfolio, "INITIAL", CAPITAL), patch.object(portfolio, "START", start):
        with redirect_stdout(StringIO()):
            portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                          block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = json.loads((output / "inputs.json").read_text())
    inputs.pop("source_sha256")
    if inputs != {**parent_inputs, "start": start}:
        raise ValueError(f"unexpected configuration drift for {start}")
    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    signals = pd.read_csv(output / "signals.csv")
    dates = [day for day in market[1] if day >= start]
    if (daily.date.tolist() != dates or daily.iloc[0].cash != CAPITAL
            or daily.iloc[0].positions != 0 or fills.date.min() <= dates[0]
            or fills.signal_day.min() < dates[0] or signals.date.min() < dates[0]):
        raise ValueError(f"invalid cold start for {start}")
    terminal = json.loads((output / "terminal.json").read_text())
    gaps = pd.read_csv(output / "gaps.csv")
    if (any((TARGET, position["epoch"]) not in market[5] for position in terminal["positions"].values())
            or gaps.date.eq(TARGET).any()):
        raise ValueError(f"missing final-day coverage for {start}")
    if start[5:7] == "01":
        reference = JANUARY_REFERENCE / start[:4]
        for name in ("fills.csv", "signals.csv", "cycles.csv", "terminal.json"):
            if (reference / name).read_bytes() != (output / name).read_bytes():
                raise ValueError(f"unexpected January trade path drift for {start}/{name}")
    opening = reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    closing_free = (daily.equity - daily.margin).round(8)
    opening_deficit = set(opening.loc[opening.free_equity.lt(0), "date"])
    closing_deficit = set(daily.loc[closing_free.lt(0), "date"])
    deficit_dates = sorted(opening_deficit | closing_deficit)
    min_free = min(opening.free_equity.min(), closing_free.min())
    first_deficit = deficit_dates[0] if deficit_dates else ""
    nonpositive_days = set(opening.loc[opening.equity.le(0), "date"]) | set(daily.loc[daily.equity.le(0), "date"])
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text())
    # An equity ratio misses margin deficits when equity is nonpositive.
    summary["days_margin_above_equity"] = len(closing_deficit)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    keys = ("start", "end", "days", "initial", "equity", "net_pnl", "return_pct",
            "max_dd_pct", "sharpe", "closed_cycles", "fills", "slippage")
    return dict(
        calendar_start=start, **{key: summary[key] for key in keys},
        minimum_close_equity=daily.equity.min(),
        max_close_margin_pct=100 * (daily.margin / daily.equity.where(daily.equity.gt(0))).max(),
        close_deficit_days=len(closing_deficit), opening_deficit_days=len(opening_deficit),
        deficit_days=len(deficit_dates), first_deficit=first_deficit,
        max_shortfall=max(0, -min_free), min_free_equity=min_free,
        nonpositive_equity_days=len(nonpositive_days),
        opening_snapshots=len(opening), max_opening_positions=int(opening.positions.max()),
        max_close_positions=int(daily.positions.max()),
    )


def run(output):
    verify_manifest(PARENT, PARENT_SHA)
    verify_manifest(JANUARY_REFERENCE, JANUARY_SHA)
    if portfolio.sha(PARENT_AUDIT) != PARENT_AUDIT_SHA:
        raise ValueError("unexpected Stage037 audit")
    market = extend(load(MARKET, control=True), TAIL)
    parent_inputs = json.loads((PARENT / "inputs.json").read_text())
    parent_inputs.pop("source_sha256")
    if {str(path): digest for path, digest in market[-1].items()} != parent_inputs["inputs_sha256"]:
        raise ValueError("market data differ from Stage037")
    output.mkdir(parents=True)
    results = [replay(output / start, start, market, parent_inputs) for start in STARTS]
    with (output / "window_metrics.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    receipt = dict(
        parent_manifest_sha256=PARENT_SHA, parent_audit_sha256=PARENT_AUDIT_SHA,
        january_reference_manifest_sha256=JANUARY_SHA, design_sha256=portfolio.sha(DESIGN),
        entrypoint_sha256=portfolio.sha(Path(__file__)), cutoff=TARGET, capital=CAPITAL,
        starts=STARTS, completed_runs=len(results), unknown_runs=0,
        market_sha256=parent_inputs["inputs_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
