"""Replay Stage043's daily signal model from the full Stage041 start grid."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage042_s19_fixed_two as grid
import stage043_s19_daily_one as daily_arm

baseline = daily_arm.baseline
LINE = daily_arm.LINE
STAGE043 = LINE / "outputs/stage043_s19_daily_one_20261104"
STAGE043_SHA = "c6211380a47d0ee0f7fad2990d74547e41944b4dc511ecabe07b5826e35c39bf"
DESIGN = LINE / "stages/20261104_1942_stage044_s19_daily_halfyear_design.md"
REPRODUCTION_FILES = (
    "annual.csv", "cycles.csv", "daily.csv", "entry_filter.csv", "fills.csv", "four_up_blocks.csv",
    "gaps.csv", "inputs.json", "opening_funding.csv", "signals.csv", "summary.json",
    "terminal.json", "week_body_filter.csv",
)


def replay(output, start, market):
    control = grid.control_path(start)
    config = json.loads((control / "inputs.json").read_text())
    with patch.object(baseline.portfolio, "INITIAL", baseline.CAPITAL), patch.object(
        baseline.portfolio, "START", start
    ), redirect_stdout(StringIO()):
        baseline.portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                               block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = output / "inputs.json"
    if json.loads(inputs.read_text()) != config:
        raise ValueError(f"strategy configuration drift: {start}")
    inputs.write_text(json.dumps({**config, "signal_bar": "1d", "fixed_entry_lots": 1}, indent=2) + "\n")

    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    reference = pd.read_csv(control / "daily.csv")
    if (not daily.date.equals(reference.date) or daily.date.iat[-1] != baseline.TARGET
            or daily.cash.iat[0] != baseline.CAPITAL or daily.positions.iat[0] != 0
            or fills.date.min() <= daily.date.iat[0] or fills.signal_day.min() < daily.date.iat[0]
            or not fills.volume.eq(1).all()):
        raise ValueError(f"unexpected calendar, cold start or sizing: {start}")
    opening = baseline.reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    summary_file = output / "summary.json"
    summary = json.loads(summary_file.read_text())
    for key in ("sharpe", "peak_margin_ratio_pct"):
        if not isfinite(summary[key]):
            summary[key] = None
    daily_metrics = baseline.metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = daily_metrics["close_deficit_days"]
    summary_file.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    if start == daily_arm.START:
        for name in REPRODUCTION_FILES:
            if (output / name).read_bytes() != (STAGE043 / name).read_bytes():
                raise ValueError(f"Stage043 reproduction changed: {name}")

    weekly_metrics = baseline.metrics(control, reference, pd.read_csv(control / "opening_funding.csv"),
                                     json.loads((control / "summary.json").read_text()))
    nonpositive = set(daily.loc[daily.equity.le(0), "date"]) | set(opening.loc[opening.equity.le(0), "date"])
    return dict(
        calendar_start=start, first_session=daily.date.iat[0], last_session=daily.date.iat[-1],
        days=len(daily), daily_nonpositive_equity_days=len(nonpositive),
        **{f"weekly_{key}": value for key, value in weekly_metrics.items()},
        **{f"daily_{key}": value for key, value in daily_metrics.items()},
    )


def run(output):
    for parent, digest in ((grid.STAGE041, grid.STAGE041_SHA), (STAGE043, STAGE043_SHA),
                           (baseline.PARENT, baseline.PARENT_SHA), (baseline.HALFYEAR, baseline.HALFYEAR_SHA)):
        baseline.verify_manifest(parent, digest)
    reference = json.loads((STAGE043 / "receipt.json").read_text())
    for name, digest in (reference["market_sha256"] | reference["source_sha256"]).items():
        if baseline.portfolio.sha(Path(name)) != digest:
            raise ValueError(f"frozen source changed: {name}")
    if baseline.portfolio.sha(Path(daily_arm.__file__)) != reference["entrypoint_sha256"]:
        raise ValueError("Stage043 entry point changed")
    grid_receipt = json.loads((grid.STAGE041 / "receipt.json").read_text())
    starts = grid_receipt["starts"]
    if starts != [f"{year}-{month}-01" for year in range(2015, 2027) for month in ("01", "07")]:
        raise ValueError("unexpected half-year grid")
    market = baseline.extend(baseline.load(baseline.MARKET, control=True), baseline.TAIL)
    if {str(path): digest for path, digest in market[-1].items()} != reference["market_sha256"]:
        raise ValueError("loaded market differs from Stage043")
    market = daily_arm.daily_signal_market(market)
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market) for start in starts]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage041_manifest_sha256=grid.STAGE041_SHA, stage043_manifest_sha256=STAGE043_SHA,
        design_sha256=baseline.portfolio.sha(DESIGN),
        entrypoint_sha256=baseline.portfolio.sha(Path(__file__)),
        cutoff=baseline.TARGET, capital=baseline.CAPITAL, signal_bar="1d", fixed_entry_lots=1,
        starts=starts, attempted=len(starts), completed=len(rows), unknown=0,
        stage043_identical_ledgers=list(REPRODUCTION_FILES),
        market_sha256=reference["market_sha256"], source_sha256=reference["source_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    baseline.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
