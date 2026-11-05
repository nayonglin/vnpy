"""Compare fixed and cash-risk sizing using the Stage034 paired block schedule."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import run_weekly_portfolio as portfolio
import stage034_s19_monte_carlo as mc
from run_stage021_multicycle import write_checksums
from stage033_s19_annual_starts import MARKET, extend, load
from stage035_s19_half_pct import TAIL

PRIOR_MC = mc.LINE / "outputs/stage034_s19_monte_carlo_v1"
PRIOR_MC_SHA = "74f6bdf35c25d50b61e77208204fd06f288453ba0367b013bef724f8d6925b51"
SIZING = mc.LINE / "outputs/stage035_s19_half_pct_20261104"
SIZING_SHA = "b1225ec06ebd2fe1b3f58b9fc352ab7a2dfd9e3826beacca535b020d065747c1"
DESIGN = mc.LINE / "stages/20261104_1724_stage036_s19_paired_mc_design.md"


def verify_manifest(root, digest):
    manifest = root / "SHA256SUMS"
    if portfolio.sha(manifest) != digest:
        raise ValueError(f"unexpected manifest {root.name}")
    for line in manifest.read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        if portfolio.sha(root / name) != expected:
            raise ValueError(f"changed parent artifact {root.name}/{name}")


def dynamic_source(output):
    market = extend(load(MARKET, control=True), TAIL)
    full = SIZING / "cash_risk_0_5pct"
    baseline = json.loads((full / "inputs.json").read_text())
    baseline.pop("source_sha256")
    if {str(path): digest for path, digest in market[-1].items()} != baseline["inputs_sha256"]:
        raise ValueError("market data differ from Stage035")
    prefixes, sources = [], {}
    for year in mc.YEARS:
        start = f"{year}-01-01"
        dates = [day for day in market[1] if day >= start][:mc.PREFIX]
        if len(dates) != mc.PREFIX:
            raise ValueError(f"incomplete prefix calendar for {year}")
        destination = full
        if year != mc.YEARS[0]:
            destination = output / "cold_starts" / str(year)
            bounded = (market[0], [day for day in market[1] if day <= dates[-1]], *market[2:])
            with patch.object(portfolio, "START", start), redirect_stdout(StringIO()):
                portfolio.run(destination, week_body_filter=True, reverse_after_stop=True,
                              block_four_up=True, delivery_guard=True, market_loader=lambda: bounded,
                              cash_risk=True, risk_fraction=portfolio.CASH_RISK_HALF_PCT)
            inputs = json.loads((destination / "inputs.json").read_text())
            inputs.pop("source_sha256")
            if inputs != {**baseline, "start": start, "end": dates[-1]}:
                raise ValueError(f"dynamic prefix configuration drift for {year}")
            gaps = pd.read_csv(destination / "gaps.csv")
            if gaps.reason.eq("held_close_stale").any():
                raise ValueError(f"stale held close in cold start {year}")
        path = destination / "daily.csv"
        sources[str(year)] = portfolio.sha(path)
        daily = pd.read_csv(path)
        expected = pd.read_csv(mc.BASE / str(year) / "daily.csv", usecols=["date"]).date
        if not daily.date.equals(expected.iloc[:len(daily)]):
            raise ValueError(f"unpaired calendar for {year}")
        equity, pnl, margin, cash, value = (
            mc.cents(daily[name]) for name in ("equity", "net_pnl", "margin", "cash", "position_value")
        )
        if (daily.date.iloc[:mc.PREFIX].tolist() != dates
                or equity[0] != mc.INITIAL_CENTS or margin[0] != 0 or daily.positions.iloc[0] != 0
                or (margin < 0).any() or not np.array_equal(equity, cash + value)
                or not np.array_equal(pnl, np.diff(equity, prepend=mc.INITIAL_CENTS))):
            raise ValueError(f"invalid cash-risk ledger for {year}")
        pairs = np.stack((pnl, margin), axis=-1)
        prefixes.append(pairs[:mc.PREFIX])
        if year == mc.YEARS[0]:
            continuing = pairs[mc.PREFIX:]
    return np.stack(prefixes), continuing, sources


def compare(fixed, cash, block, horizon):
    if not fixed[["path_id", "prefix_year"]].equals(cash[["path_id", "prefix_year"]]):
        raise ValueError("mismatched paired scenarios")
    equity = fixed.terminal_equity - cash.terminal_equity
    drawdown = cash.max_drawdown_pct - fixed.max_drawdown_pct
    tied = np.isclose(drawdown, 0, rtol=0, atol=1e-10)
    drawdown = drawdown.mask(tied, 0)
    f_margin, c_margin = fixed.margin_breach, cash.margin_breach
    stats = {
        "fixed_higher_equity": equity.gt(0),
        "cash_higher_equity": equity.lt(0),
        "equity_tie": equity.eq(0),
        "fixed_lower_drawdown": drawdown.gt(0),
        "cash_lower_drawdown": drawdown.lt(0),
        "drawdown_tie": drawdown.eq(0),
        "fixed_higher_equity_and_lower_drawdown": equity.gt(0) & drawdown.gt(0),
        "cash_higher_equity_and_lower_drawdown": equity.lt(0) & drawdown.lt(0),
        "fixed_only_margin_breach": f_margin & ~c_margin,
        "cash_only_margin_breach": c_margin & ~f_margin,
        "both_margin_breach": f_margin & c_margin,
        "neither_margin_breach": ~f_margin & ~c_margin,
    }
    rows = []
    for name, flags in stats.items():
        count = int(flags.sum())
        lo, hi = mc.wilson(count, mc.PATHS)
        rows.append(dict(block_days=block, horizon_days=horizon, measure=name,
                         count=count, pairs=mc.PATHS, frequency=count / mc.PATHS,
                         wilson_lo=lo, wilson_hi=hi))
    return rows


def run(output):
    verify_manifest(PRIOR_MC, PRIOR_MC_SHA)
    verify_manifest(SIZING, SIZING_SHA)
    mc.load_source()
    output.mkdir(parents=True)
    prefixes, continuing, sources = dynamic_source(output)
    event_rows, quantile_rows, paired_rows, fans = [], [], [], []
    with np.load(PRIOR_MC / "sampling_plan.npz", allow_pickle=False) as plan:
        prefix_ids = plan["prefix_index"]
        for block in mc.BLOCKS:
            starts, cash, fan = mc.simulate(prefixes, continuing, prefix_ids, block)
            if not np.array_equal(starts, plan[f"block_{block}_start"]):
                raise ValueError(f"draw drift for {block}-day blocks")
            cash.to_csv(output / f"cash_paths_b{block}.csv", index=False)
            fans.append(fan)
            fixed = pd.read_csv(PRIOR_MC / f"paths_b{block}.csv")
            for horizon in mc.HORIZONS:
                arms = {"fixed_one": fixed[fixed.horizon_days.eq(horizon)].reset_index(drop=True),
                        "cash_risk_0_5pct": cash[cash.horizon_days.eq(horizon)].reset_index(drop=True)}
                for name, frame in arms.items():
                    if frame.path_id.tolist() != list(range(1, mc.PATHS + 1)) or frame.isna().any().any():
                        raise ValueError(f"incomplete simulation {name}/{block}/{horizon}")
                    events, quantiles = mc.summarize(frame, block, horizon)
                    event_rows.extend(dict(arm=name, **row) for row in events)
                    quantile_rows.extend(dict(arm=name, **row) for row in quantiles)
                paired_rows.extend(compare(*arms.values(), block, horizon))
    mc.write_rows(output / "event_frequencies.csv", event_rows)
    mc.write_rows(output / "quantiles.csv", quantile_rows)
    mc.write_rows(output / "paired_frequencies.csv", paired_rows)
    fixed_fan = pd.read_csv(PRIOR_MC / "equity_fan.csv").assign(arm="fixed_one")
    cash_fan = pd.concat(fans, ignore_index=True).assign(arm="cash_risk_0_5pct")
    pd.concat([fixed_fan, cash_fan], ignore_index=True).to_csv(output / "equity_fan.csv", index=False)
    receipt = dict(parent_mc_manifest_sha256=PRIOR_MC_SHA, parent_sizing_manifest_sha256=SIZING_SHA,
                   design_sha256=portfolio.sha(DESIGN), entrypoint_sha256=portfolio.sha(Path(__file__)),
                   sampling_source_sha256=portfolio.sha(Path(mc.__file__)),
                   paired_sampling_plan_sha256=portfolio.sha(PRIOR_MC / "sampling_plan.npz"),
                   dynamic_daily_sha256=sources, block_days=mc.BLOCKS, horizons=mc.HORIZONS,
                   cutoff="2026-11-04", paths_per_block=mc.PATHS,
                   attempted_pairs=mc.PATHS*len(mc.BLOCKS), unknown_pairs=0)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
