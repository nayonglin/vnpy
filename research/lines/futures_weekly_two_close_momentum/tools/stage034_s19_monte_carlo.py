"""S19 joint daily PnL and end-of-day margin moving-block resampling."""
import argparse
import csv
import json
from math import ceil, sqrt
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from run_stage021_multicycle import write_checksums
from run_weekly_portfolio import sha

LINE = Path(__file__).resolve().parents[1]
DESIGN = LINE / "stages/20261104_1704_stage034_s19_monte_carlo_design.md"
BASE = LINE / "outputs/stage033_s19_annual_starts_20261104"
BASE_SHA = "db8dc6230079ae1972e5011fed9c1607e5597cdcf4bedf0a61275611766f8fba"
AUDIT = LINE / "reviews/stage033_s19_annual_starts_audit.json"
AUDIT_SHA = "81971ec62626e096c816a9533320436b893124ac96f7122875abeed1788b99c6"
YEARS = np.arange(2015, 2027)
SEED = 20261104034
PATHS, PREFIX, INITIAL_CENTS = 20_000, 63, 30_000_000
BLOCKS, HORIZONS = (63, 21), (252, 756, 1260)
QUANTILES = (.01, .05, .25, .50, .75, .95, .99)
EVENTS = ("terminal_loss", "margin_breach", "equity_nonpositive", "dd30", "dd40", "dd50")


def cents(values):
    scaled = np.asarray(values, dtype=np.float64) * 100
    rounded = np.rint(scaled)
    if not np.isfinite(scaled).all() or not np.allclose(scaled, rounded, rtol=0, atol=1e-4):
        raise ValueError("non-finite amount or unsupported sub-cent rounding")
    return rounded.astype(np.int64)


def load_source():
    manifest = BASE / "SHA256SUMS"
    if sha(manifest) != BASE_SHA or sha(AUDIT) != AUDIT_SHA:
        raise ValueError("unexpected Stage033 parent or audit")
    for line in manifest.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        if sha(BASE / name) != digest:
            raise ValueError(f"Stage033 source mismatch: {name}")
    prefixes = []
    continuing = None
    source_files = {}
    for year in YEARS:
        path = BASE / str(year) / "daily.csv"
        source_files[str(year)] = sha(path)
        frame = pd.read_csv(path)
        equity, cash, value, pnl, margin = (
            cents(frame[name]) for name in ("equity", "cash", "position_value", "net_pnl", "margin")
        )
        if (not frame.date.is_monotonic_increasing or not frame.date.is_unique
                or frame.date.iloc[0][:4] != str(year) or frame.date.iloc[-1] != "2026-11-04"
                or len(frame) < PREFIX or equity[0] != INITIAL_CENTS or margin[0] != 0
                or frame.positions.iloc[0] != 0 or (margin < 0).any()
                or not np.array_equal(equity, cash + value)
                or not np.array_equal(pnl, np.diff(equity, prepend=INITIAL_CENTS))):
            raise ValueError(f"invalid cold start source {year}")
        pairs = np.stack((pnl, margin), axis=-1)
        prefixes.append(pairs[:PREFIX])
        if year == YEARS[0]:
            continuing = pairs[PREFIX:]
    return np.stack(prefixes), continuing, source_files


def wilson(count, total):
    z = 1.959963984540054
    p = count / total
    scale = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / scale
    radius = z * sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / scale
    return max(0, center - radius), min(1, center + radius)


def summarize(frame, block, horizon):
    event_rows = []
    for name in EVENTS:
        count = int(frame[name].sum())
        lo, hi = wilson(count, len(frame))
        event_rows.append(dict(block_days=block, horizon_days=horizon, event=name, count=count,
                               valid=len(frame), attempted=PATHS, unknown=PATHS-len(frame),
                               frequency=count/len(frame), wilson_lo=lo, wilson_hi=hi))
    measure_rows = []
    metrics = {
        "terminal_equity": frame.terminal_equity,
        "max_drawdown_pct": frame.max_drawdown_pct,
        "initial_capital_required": frame.initial_capital_required,
        "max_margin_shortfall_given_breach": frame.loc[frame.margin_breach, "max_margin_shortfall"],
        "first_breach_day_given_breach": frame.loc[frame.margin_breach, "first_breach_day"],
    }
    for name, values in metrics.items():
        if len(values):
            qs = np.quantile(values, QUANTILES, method="linear")
            measure_rows.append(dict(block_days=block, horizon_days=horizon, measure=name, n=len(values),
                                     **{f"p{round(p*100):02}": q for p, q in zip(QUANTILES, qs)}))
    return event_rows, measure_rows


def simulate(prefixes, continuing, prefix_ids, block):
    horizon = HORIZONS[-1]
    nblocks = ceil((horizon - PREFIX) / block)
    rng = np.random.default_rng(np.random.SeedSequence([SEED, block]))
    starts = rng.integers(0, len(continuing) - block + 1, size=(PATHS, nblocks), dtype=np.int32)
    snapshots = np.arange(0, horizon + 1, 21)
    fan = np.empty((PATHS, len(snapshots)), dtype=np.int64)
    rows = []
    for first in range(0, PATHS, 500):
        batch = slice(first, min(first + 500, PATHS))
        positions = (starts[batch, :, None] + np.arange(block)).reshape(-1, nblocks * block)
        sampled = np.concatenate((prefixes[prefix_ids[batch]], continuing[positions]), axis=1)[:, :horizon]
        accumulated = sampled[:, :, 0].cumsum(axis=1)
        equity = INITIAL_CENTS + accumulated
        margin = sampled[:, :, 1]
        high = np.maximum.accumulate(np.maximum(equity, INITIAL_CENTS), axis=1)
        decline = high - equity
        shortfall = margin - equity
        breach = shortfall > 0
        fan[batch, 0] = INITIAL_CENTS
        fan[batch, 1:] = equity[:, snapshots[1:] - 1]
        for length in HORIZONS:
            segment = slice(0, length)
            at_end = equity[:, length - 1]
            excess = shortfall[:, segment].max(axis=1)
            deficits = breach[:, segment]
            has_deficit = deficits.any(axis=1)
            drawdown = decline[:, segment]
            peaks = high[:, segment]
            frame = pd.DataFrame(dict(
                block_days=block, horizon_days=length, path_id=np.arange(batch.start, batch.stop) + 1,
                prefix_year=YEARS[prefix_ids[batch]], terminal_equity=at_end/100,
                max_drawdown_pct=100 * (drawdown / peaks).max(axis=1),
                initial_capital_required=np.maximum(0, INITIAL_CENTS + excess)/100,
                max_margin_shortfall=np.maximum(excess, 0)/100,
                first_breach_day=np.where(has_deficit, deficits.argmax(axis=1) + 1, 0),
                margin_breach_days=deficits.sum(axis=1),
                terminal_loss=at_end < INITIAL_CENTS, margin_breach=has_deficit,
                equity_nonpositive=(equity[:, segment] <= 0).any(axis=1),
                dd30=(drawdown * 100 >= peaks * 30).any(axis=1),
                dd40=(drawdown * 100 >= peaks * 40).any(axis=1),
                dd50=(drawdown * 100 >= peaks * 50).any(axis=1),
            ))
            rows.append(frame)
    stats = pd.concat(rows, ignore_index=True).sort_values(["horizon_days", "path_id"])
    fan_q = np.quantile(fan, QUANTILES, axis=0, method="linear") / 100
    fan_frame = pd.DataFrame(dict(block_days=block, trading_days=snapshots,
                                  **{f"p{round(p*100):02}": q for p, q in zip(QUANTILES, fan_q)}))
    return starts, stats, fan_frame


def write_rows(path, rows):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(output):
    prefixes, continuing, source_files = load_source()
    prefix_ids = np.random.default_rng(SEED).integers(0, len(prefixes), size=PATHS, dtype=np.int32)
    output.mkdir(parents=True)
    events, measures, fans = [], [], []
    schedule = {"prefix_index": prefix_ids}
    for block in BLOCKS:
        starts, stats, fan = simulate(prefixes, continuing, prefix_ids, block)
        schedule[f"block_{block}_start"] = starts
        stats.to_csv(output / f"paths_b{block}.csv", index=False)
        fans.append(fan)
        for horizon, group in stats.groupby("horizon_days", sort=True):
            if group.path_id.tolist() != list(range(1, PATHS + 1)) or group.isna().any().any():
                raise ValueError(f"incomplete group {block}/{horizon}")
            event_rows, measure_rows = summarize(group, block, horizon)
            events.extend(event_rows)
            measures.extend(measure_rows)
    np.savez_compressed(output / "sampling_plan.npz", **schedule)
    pd.concat(fans, ignore_index=True).to_csv(output / "equity_fan.csv", index=False)
    write_rows(output / "event_frequencies.csv", events)
    write_rows(output / "quantiles.csv", measures)
    receipt = dict(parent_sha256=BASE_SHA, parent_audit_sha256=AUDIT_SHA, source_daily_sha256=source_files,
                   design_sha256=sha(DESIGN), source_sha256=sha(Path(__file__)), cutoff="2026-11-04",
                   seed=SEED, prefix_days=PREFIX, prefix_years=YEARS.tolist(), mature_days=len(continuing),
                   block_days=BLOCKS, horizons=HORIZONS, initial_cents=INITIAL_CENTS, paths_per_block=PATHS,
                   attempted_paths=PATHS*len(BLOCKS), unknown_paths=0, python=sys.version,
                   numpy=np.__version__, pandas=pd.__version__)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.iterdir() if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
