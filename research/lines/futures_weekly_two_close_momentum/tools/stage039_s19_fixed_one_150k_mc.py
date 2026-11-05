"""Compare 150k against the sealed 300k S19 draw plan and vary cold-start dates."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import stage034_s19_monte_carlo as mc
from run_stage021_multicycle import write_checksums
from run_weekly_portfolio import sha
from stage036_s19_paired_mc import PRIOR_MC, PRIOR_MC_SHA, verify_manifest
from stage037_s19_fixed_one_150k import CAPITAL
from stage038_s19_fixed_one_150k_halfyear import PARENT, PARENT_SHA, STARTS

SEMIANNUAL = mc.LINE / "outputs/stage038_s19_fixed_one_150k_halfyear_20261104"
SEMIANNUAL_SHA = "0e3f8aaaba64eac4bfb21284e66944fd2099091182c1e8dcc0c7cf3db3fbf5a8"
DESIGN = mc.LINE / "stages/20261104_1759_stage039_s19_fixed_one_150k_mc_design.md"


def read_ledger(path):
    frame = pd.read_csv(path)
    equity = mc.cents(frame.equity)
    pnl = mc.cents(frame.net_pnl)
    margin = mc.cents(frame.margin)
    initial = CAPITAL * 100
    if (not frame.date.is_unique or not frame.date.is_monotonic_increasing
            or len(frame) < mc.PREFIX or frame.date.iloc[-1] != "2026-11-04"
            or equity[0] != initial or frame.positions.iloc[0] != 0 or margin[0] != 0
            or (margin < 0).any() or not np.array_equal(pnl, np.diff(equity, prepend=initial))
            or not np.array_equal(equity, mc.cents(frame.cash) + mc.cents(frame.position_value))):
        raise ValueError(f"invalid 150k historical ledger {path}")
    return frame.date, np.stack((pnl, margin), axis=-1)


def assert_paired(cash150, cash300):
    if not cash150[["horizon_days", "path_id", "prefix_year"]].equals(
        cash300[["horizon_days", "path_id", "prefix_year"]]
    ):
        raise ValueError("30w and 15w path keys differ")
    initial_difference = mc.INITIAL_CENTS // 100 - CAPITAL
    if (not np.array_equal(mc.cents(cash300.terminal_equity - cash150.terminal_equity),
                           np.full(len(cash150), initial_difference * 100))
            or not np.array_equal(mc.cents(cash150.initial_capital_required),
                                  mc.cents(cash300.initial_capital_required))
            or not cash150.terminal_loss.equals(cash300.terminal_loss)
            or (cash300.margin_breach & ~cash150.margin_breach).any()
            or (cash300.equity_nonpositive & ~cash150.equity_nonpositive).any()):
        raise ValueError("capital-only paired identities failed")


def run(output):
    verify_manifest(PRIOR_MC, PRIOR_MC_SHA)
    verify_manifest(PARENT, PARENT_SHA)
    verify_manifest(SEMIANNUAL, SEMIANNUAL_SHA)
    old_prefixes, continuing, _ = mc.load_source()
    dates, full = read_ledger(PARENT / "daily.csv")
    dates300 = pd.read_csv(mc.BASE / "2015/daily.csv", usecols=["date"]).date
    if (not dates.equals(dates300) or not np.array_equal(full[:mc.PREFIX], old_prefixes[0])
            or not np.array_equal(full[mc.PREFIX:], continuing)):
        raise ValueError("2015 absolute PnL/margin path drift")
    new_prefixes = []
    sources = {}
    for start in STARTS:
        path = SEMIANNUAL / start / "daily.csv"
        cold_dates, pairs = read_ledger(path)
        if not cold_dates.equals(dates.loc[dates.ge(start)].reset_index(drop=True)):
            raise ValueError(f"unpaired cold-start calendar {start}")
        new_prefixes.append(pairs[:mc.PREFIX])
        sources[start] = sha(path)
    new_prefixes = np.stack(new_prefixes)
    january = new_prefixes[::2]
    if not np.array_equal(january, old_prefixes[1:]):
        raise ValueError("January absolute PnL/margin path drift")

    output.mkdir(parents=True)
    events, quantiles, fans = [], [], []
    new_ids = np.random.default_rng(mc.SEED).integers(
        0, len(new_prefixes), size=mc.PATHS, dtype=np.int32
    )
    np.save(output / "semiannual_prefix_indices.npy", new_ids, allow_pickle=False)
    with np.load(PRIOR_MC / "sampling_plan.npz", allow_pickle=False) as plan:
        for block in mc.BLOCKS:
            paired300 = pd.read_csv(PRIOR_MC / f"paths_b{block}.csv")
            configurations = (
                ("paired_january", old_prefixes, plan["prefix_index"], mc.YEARS),
                ("semiannual", new_prefixes, new_ids, np.array(STARTS)),
            )
            for name, prefixes, ids, labels in configurations:
                with patch.object(mc, "INITIAL_CENTS", CAPITAL * 100), patch.object(mc, "YEARS", labels):
                    starts, paths, fan = mc.simulate(prefixes, continuing, ids, block)
                if not np.array_equal(starts, plan[f"block_{block}_start"]):
                    raise ValueError(f"draw drift for {name}/{block}")
                if name == "paired_january":
                    assert_paired(paths.reset_index(drop=True), paired300)
                paths.rename(columns={"prefix_year": "prefix_start"}).to_csv(
                    output / f"{name}_paths_b{block}.csv", index=False
                )
                fans.append(fan.assign(cohort=name))
                for horizon, frame in paths.groupby("horizon_days", sort=True):
                    if (frame.path_id.tolist() != list(range(1, mc.PATHS + 1))
                            or frame.isna().any().any()):
                        raise ValueError(f"incomplete group {name}/{block}/{horizon}")
                    frequencies, measures = mc.summarize(frame, block, horizon)
                    events.extend(dict(cohort=name, **row) for row in frequencies)
                    quantiles.extend(dict(cohort=name, **row) for row in measures)
    mc.write_rows(output / "event_frequencies.csv", events)
    mc.write_rows(output / "quantiles.csv", quantiles)
    pd.concat(fans, ignore_index=True).to_csv(output / "equity_fan.csv", index=False)
    receipt = dict(
        design_sha256=sha(DESIGN), entrypoint_sha256=sha(Path(__file__)),
        sampling_source_sha256=sha(Path(mc.__file__)), parent_mc_manifest_sha256=PRIOR_MC_SHA,
        parent_150k_manifest_sha256=PARENT_SHA, semiannual_manifest_sha256=SEMIANNUAL_SHA,
        paired_sampling_plan_sha256=sha(PRIOR_MC / "sampling_plan.npz"), semiannual_daily_sha256=sources,
        cutoff="2026-11-04", initial_capital=CAPITAL, block_days=mc.BLOCKS, horizons=mc.HORIZONS,
        paths_per_group=mc.PATHS, completed_paths=4*mc.PATHS, unknown_paths=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.iterdir() if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
