"""Replay the 24 frozen S19 starts at two lots per entry."""
import argparse
from contextlib import redirect_stdout
from inspect import getsource
from io import StringIO
import json
from pathlib import Path

import numpy as np
import pandas as pd

import stage040_s19_without_gold as baseline
import stage041_complete_halfyear as halfyear

LINE = baseline.LINE
ENGINE_SHA = "5da2f122fa8ff2dc1df9f4667a15b300c23a457a5cc875ce50b14ed88faec507"
STAGE041 = LINE / "outputs/stage041_complete_halfyear_20261104"
STAGE041_SHA = "c71b2b77b59084f278d9a16b6eaa266d7159aebb830f5643be89aaa7493070a4"
DESIGN = LINE / "stages/20261104_1925_stage042_s19_fixed_two_design.md"
LOTS = 2


def fixed_two_engine():
    engine = baseline.portfolio
    source_path = Path(engine.__file__)
    source = getsource(engine.run)
    fixed_entry = 'funding_order(day, product, bar, "entry", signal_day, side, stop) if cash_risk else 1'
    if engine.sha(source_path) != ENGINE_SHA or source.count(fixed_entry) != 1:
        raise ValueError("frozen fixed-entry engine differs")
    source = source.replace(fixed_entry, fixed_entry[:-1] + str(LOTS))
    namespace = vars(engine).copy()
    exec(compile(source, str(source_path), "exec"), namespace)
    return namespace


def control_path(start):
    if start == "2015-01-01":
        return baseline.PARENT
    if start == halfyear.START:
        return STAGE041 / start / "s19"
    return baseline.HALFYEAR / start


def scaled_opening(control):
    marks = pd.read_csv(control / "opening_funding.csv")
    marks["equity"] = baseline.CAPITAL + LOTS * (marks.equity - baseline.CAPITAL)
    marks["margin"] = LOTS * marks.margin
    marks["free_equity"] = (marks.equity - marks.margin).round(8)
    return marks


def replay(output, start, market, engine):
    control = control_path(start)
    engine["START"] = start
    engine["INITIAL"] = baseline.CAPITAL
    with redirect_stdout(StringIO()):
        engine["run"](output, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)

    inputs_path = output / "inputs.json"
    inputs = json.loads(inputs_path.read_text())
    if inputs != json.loads((control / "inputs.json").read_text()):
        raise ValueError(f"configuration drift for {start}")
    inputs["fixed_entry_lots"] = LOTS
    inputs_path.write_text(json.dumps(inputs, indent=2) + "\n")

    fills = pd.read_csv(output / "fills.csv")
    expected = pd.read_csv(control / "fills.csv")
    expected[["volume", "slippage", "commission"]] *= LOTS
    pd.testing.assert_frame_equal(fills, expected, rtol=0, atol=1e-7)
    for name in ("signals.csv", "gaps.csv", "entry_filter.csv", "week_body_filter.csv",
                 "four_up_blocks.csv", "terminal.json"):
        if (output / name).read_bytes() != (control / name).read_bytes():
            raise ValueError(f"unexpected {name} drift for {start}")

    daily = pd.read_csv(output / "daily.csv")
    one = pd.read_csv(control / "daily.csv")
    pd.testing.assert_frame_equal(daily[["date", "positions"]], one[["date", "positions"]])
    for field in ("equity", "cash", "position_value", "margin", "net_pnl",
                  "cumulative_slippage", "cumulative_commission"):
        anchor = baseline.CAPITAL if field in ("equity", "cash") else 0
        np.testing.assert_allclose(daily[field], anchor + LOTS * (one[field] - anchor), atol=1e-6, rtol=0)

    opening = scaled_opening(control)
    opening.to_csv(output / "opening_funding.csv", index=False)
    free = (daily.equity - daily.margin).round(8)
    close_gaps = set(daily.loc[free.lt(0), "date"])
    open_gaps = set(opening.loc[opening.free_equity.lt(0), "date"])
    gaps = close_gaps | open_gaps
    nonpositive = set(daily.loc[daily.equity.le(0), "date"]) | set(opening.loc[opening.equity.le(0), "date"])
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["days_margin_above_equity"] = len(close_gaps)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return dict(
        calendar_start=start, first_session=daily.date.iat[0], last_session=daily.date.iat[-1],
        days=len(daily), **{key: summary[key] for key in baseline.METRICS},
        opening_deficit_days=len(open_gaps), close_deficit_days=len(close_gaps),
        deficit_days=len(gaps), first_deficit=min(gaps, default=""),
        max_shortfall=max(0, -min(opening.free_equity.min(), free.min())),
        peak_opening_margin=opening.margin.max(), peak_close_margin=round(daily.margin.max(), 8),
        nonpositive_equity_days=len(nonpositive), minimum_equity=min(daily.equity.min(), opening.equity.min()),
        max_positions=int(daily.positions.max()), max_lots=LOTS * int(daily.positions.max()),
    )


def run(output):
    for parent, digest in ((STAGE041, STAGE041_SHA), (halfyear.PRIOR, halfyear.PRIOR_SHA),
                           (baseline.PARENT, baseline.PARENT_SHA), (baseline.HALFYEAR, baseline.HALFYEAR_SHA)):
        baseline.verify_manifest(parent, digest)
    prior = json.loads((STAGE041 / "receipt.json").read_text())
    market = baseline.extend(baseline.load(baseline.MARKET, control=True), baseline.TAIL)
    config = json.loads((baseline.PARENT / "inputs.json").read_text())
    if (list(market[0]) != config["products"] or len(market[0]) != 19 or baseline.GOLD not in market[0]
            or market[1][-1] != prior["cutoff"]
            or {str(path): digest for path, digest in market[-1].items()} != config["inputs_sha256"]):
        raise ValueError("unexpected frozen market")
    engine = fixed_two_engine()
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market, engine) for start in prior["starts"]]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage041_manifest_sha256=STAGE041_SHA, engine_sha256=ENGINE_SHA,
        design_sha256=baseline.portfolio.sha(DESIGN),
        entrypoint_sha256=baseline.portfolio.sha(Path(__file__)),
        cutoff=prior["cutoff"], capital=baseline.CAPITAL, fixed_entry_lots=LOTS,
        starts=prior["starts"], attempted=len(prior["starts"]), completed=len(rows), unknown=0,
        products=config["products"], market_sha256=config["inputs_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    baseline.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
