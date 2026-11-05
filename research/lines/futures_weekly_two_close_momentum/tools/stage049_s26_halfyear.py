"""Replay Stage048 S26 in the established 24 independent half-year windows."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage040_s19_without_gold as base
from stage041_complete_halfyear import START as JULY_2015
from stage042_s19_fixed_two import ENGINE_SHA, STAGE041, STAGE041_SHA, control_path
from stage048_s26_full import ADDED, TAIL_AUDIT, TAIL_AUDIT_SHA, add_tail

FULL = base.LINE / "outputs/stage048_s26_full_20261104"
FULL_SHA = "9499cb34c0b0494f0df22f1057109a59311b4341d0658aac8c13b9baf345464f"
FULL_AUDIT = base.LINE / "reviews/stage048_s26_full_audit.json"
FULL_AUDIT_SHA = "de862797f57e4f55f13eee3a6d65e4fc11685920ec2720dd6f9fa29590b0f936"
TAIL = base.LINE / "outputs/stage048_s26_tail/attempt002"
DESIGN = base.LINE / "stages/20261104_2046_stage049_s26_halfyear_design.md"
STARTS = (base.WINDOWS[0], JULY_2015, *base.STARTS)


def read_json(path):
    return json.loads(path.read_text())


def funding_metrics(folder, daily, opening, summary):
    nonpositive = set(daily.loc[daily.equity.le(0), "date"]) | set(
        opening.loc[opening.equity.le(0), "date"]
    )
    return dict(
        **base.metrics(folder, daily, opening, summary),
        nonpositive_equity_days=len(nonpositive),
        minimum_equity=min(daily.equity.min(), opening.equity.min()),
    )


def replay(folder, start, market, full_inputs):
    with patch.object(base.portfolio, "INITIAL", base.CAPITAL), patch.object(
        base.portfolio, "START", start
    ), redirect_stdout(StringIO()):
        base.portfolio.run(folder, week_body_filter=True, reverse_after_stop=True,
                           block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    if read_json(folder / "inputs.json") != {**full_inputs, "start": start}:
        raise ValueError(f"configuration drift: {start}")
    control = control_path(start)
    daily = pd.read_csv(folder / "daily.csv")
    control_daily = pd.read_csv(control / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    signals = pd.read_csv(folder / "signals.csv")
    first = daily.date.iat[0]
    if (daily.date.tolist() != [day for day in market[1] if day >= start]
            or not daily.date.equals(control_daily.date) or daily.date.iat[-1] != base.TARGET
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or not fills.volume.eq(1).all() or fills.date.le(first).any()
            or fills.signal_day.lt(first).any() or signals.date.lt(first).any()):
        raise ValueError(f"invalid cold start or trading calendar: {start}")

    s19_fills = pd.read_csv(control / "fills.csv").drop(columns="cycle")
    common_fills = fills.loc[fills["product"].isin(set(market[0]) - set(ADDED))]
    pd.testing.assert_frame_equal(
        common_fills.drop(columns="cycle").reset_index(drop=True), s19_fills,
        obj=f"original S19 fills {start}",
    )
    terminal = read_json(folder / "terminal.json")
    if (any((base.TARGET, pos["epoch"]) not in market[5] for pos in terminal["positions"].values())
            or pd.read_csv(folder / "gaps.csv").date.eq(base.TARGET).any()):
        raise ValueError(f"missing final-day coverage: {start}")

    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    summary_path = folder / "summary.json"
    summary = read_json(summary_path)
    s26 = funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = s26["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    s19 = funding_metrics(control, control_daily, pd.read_csv(control / "opening_funding.csv"),
                          read_json(control / "summary.json"))
    cycles = pd.read_csv(folder / "cycles.csv")
    added = cycles.loc[cycles["product"].isin(ADDED)].groupby("product").net_pnl.sum()
    difference = s26["net_pnl"] - s19["net_pnl"]
    if abs(difference - added.sum()) > 1e-6:
        raise ValueError(f"new product PnL does not reconcile: {start}")
    if start == STARTS[0]:
        for name in ("daily", "fills", "signals", "cycles", "opening_funding"):
            if (folder / f"{name}.csv").read_bytes() != (FULL / f"{name}.csv").read_bytes():
                raise ValueError(f"Stage048 reference drift: {name}")
    return dict(
        calendar_start=start, first_session=first, last_session=base.TARGET, days=len(daily),
        **{f"s19_{key}": value for key, value in s19.items()},
        **{f"s26_{key}": value for key, value in s26.items()},
        pnl_difference=difference,
        return_difference_pp=s26["return_pct"] - s19["return_pct"],
        drawdown_difference_pp=s26["max_dd_pct"] - s19["max_dd_pct"],
    )


def run(output):
    manifests = {FULL: FULL_SHA, base.PARENT: base.PARENT_SHA,
                 base.HALFYEAR: base.HALFYEAR_SHA, STAGE041: STAGE041_SHA}
    for path, digest in manifests.items():
        base.verify_manifest(path, digest)
    if (base.portfolio.sha(FULL_AUDIT) != FULL_AUDIT_SHA
            or base.portfolio.sha(TAIL_AUDIT) != TAIL_AUDIT_SHA
            or base.portfolio.sha(Path(base.portfolio.__file__)) != ENGINE_SHA):
        raise ValueError("frozen strategy or audit changed")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    reference = read_json(FULL / "receipt.json")
    market = add_tail((reference["products"], *expanded[1:]), original, TAIL)
    market_hashes = {str(path): digest for path, digest in market[-1].items()}
    if (market_hashes != reference["market_sha256"] or len(market[0]) != 26
            or set(market[0]) - set(original[0]) != set(ADDED)):
        raise ValueError("Stage048 frozen market or product list changed")

    full_inputs = read_json(FULL / "inputs.json")
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market, full_inputs) for start in STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        manifests_sha256={path.name: digest for path, digest in manifests.items()},
        full_audit_sha256=FULL_AUDIT_SHA, tail_admission_sha256=TAIL_AUDIT_SHA,
        engine_sha256=ENGINE_SHA, design_sha256=base.portfolio.sha(DESIGN),
        entrypoint_sha256=base.portfolio.sha(Path(__file__)), cutoff=base.TARGET,
        capital=base.CAPITAL, products=market[0], market_sha256=market_hashes,
        starts=STARTS, attempted_runs=len(STARTS), completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
