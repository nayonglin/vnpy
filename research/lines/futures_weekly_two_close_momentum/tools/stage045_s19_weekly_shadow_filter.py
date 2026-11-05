"""Apply the requested two-candle shadow filter to the frozen S19 replay."""
import argparse
from contextlib import redirect_stdout
from inspect import getsource
from io import StringIO
import json
from math import isfinite
from pathlib import Path

import pandas as pd

import stage042_s19_fixed_two as grid
from stage040_s19_without_gold import (
    CAPITAL, GOLD, LINE, MARKET, PARENT, PARENT_SHA, HALFYEAR, HALFYEAR_SHA,
    TAIL, TARGET, extend, load, metrics, portfolio, reconstruct_opening, verify_manifest,
    write_checksums,
)

DESIGN = LINE / "stages/20261104_2003_stage045_s19_weekly_shadow_filter_design.md"
FILTER_CONFIG = {"body_to_total_shadow_lt": "1/3", "required_bars": 2}
BLOCK_COLUMNS = (
    "date", "product", "epoch", "action", "kind",
    "current_body", "current_shadow", "prior_body", "prior_shadow",
)


def body_and_shadow(bar):
    body = abs(bar.close - bar.open)
    return body, bar.high - bar.low - body


def wick_filter_engine():
    source_path = Path(portfolio.__file__)
    source = getsource(portfolio.run)
    anchor = '                if is_add:\n                    action = action.replace'
    if portfolio.sha(source_path) != grid.ENGINE_SHA or source.count(anchor) != 1:
        raise ValueError("unexpected frozen engine or entry hook")
    hook = """                if not is_add and action in ("open_long", "open_short"):
                    kind = "reversal" if orders is pending_reversals else "entry"
                    if shadow_blocks(day, product, bar.contract_epoch_id, action, kind, current, last):
                        continue
"""
    namespace = vars(portfolio).copy()
    exec(compile(source.replace(anchor, hook + anchor), str(source_path), "exec"), namespace)
    return namespace


def replay(output, start, market, engine):
    blocked = []

    def shadow_blocks(day, product, epoch, action, kind, current, prior):
        body, shadow = body_and_shadow(current)
        prior_body, prior_shadow = body_and_shadow(prior)
        if 3 * body < shadow and 3 * prior_body < prior_shadow:
            blocked.append((day, product, epoch, action, kind, body, shadow, prior_body, prior_shadow))
            return True
        return False

    control = grid.control_path(start)
    engine.update(START=start, INITIAL=CAPITAL, shadow_blocks=shadow_blocks)
    with redirect_stdout(StringIO()):
        engine["run"](output, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs_path = output / "inputs.json"
    config = json.loads(inputs_path.read_text())
    if config != json.loads((control / "inputs.json").read_text()):
        raise ValueError(f"unexpected strategy configuration: {start}")
    inputs_path.write_text(json.dumps({**config, "entry_shadow_filter": FILTER_CONFIG}, indent=2) + "\n")
    pd.DataFrame(blocked, columns=BLOCK_COLUMNS).to_csv(output / "shadow_blocks.csv", index=False)

    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    reference = pd.read_csv(control / "daily.csv")
    if (not daily.date.equals(reference.date) or daily.date.iat[-1] != TARGET
            or daily.cash.iat[0] != CAPITAL or daily.positions.iat[0] != 0
            or fills.date.min() <= daily.date.iat[0] or fills.signal_day.min() < daily.date.iat[0]
            or not fills.volume.eq(1).all()):
        raise ValueError(f"unexpected calendar, cold start or sizing: {start}")

    opening = reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text())
    for key in ("sharpe", "peak_margin_ratio_pct"):
        if not isfinite(summary[key]):
            summary[key] = None
    candidate = metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = candidate["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    base = metrics(control, reference, pd.read_csv(control / "opening_funding.csv"),
                   json.loads((control / "summary.json").read_text()))
    nonpositive = set(daily.loc[daily.equity.le(0), "date"]) | set(opening.loc[opening.equity.le(0), "date"])
    return dict(
        calendar_start=start, first_session=daily.date.iat[0], last_session=daily.date.iat[-1],
        days=len(daily), blocks=len(blocked),
        reversal_blocks=sum(event[4] == "reversal" for event in blocked),
        candidate_nonpositive_days=len(nonpositive),
        **{f"base_{key}": value for key, value in base.items()},
        **{f"candidate_{key}": value for key, value in candidate.items()},
    )


def run(output):
    for parent, digest in ((grid.STAGE041, grid.STAGE041_SHA),
                           (PARENT, PARENT_SHA), (HALFYEAR, HALFYEAR_SHA)):
        verify_manifest(parent, digest)
    config = json.loads((PARENT / "inputs.json").read_text())
    for name, digest in (config["inputs_sha256"] | config["source_sha256"]).items():
        if portfolio.sha(Path(name)) != digest:
            raise ValueError(f"frozen source changed: {name}")
    starts = json.loads((grid.STAGE041 / "receipt.json").read_text())["starts"]
    market = extend(load(MARKET, control=True), TAIL)
    if (list(market[0]) != config["products"] or len(market[0]) != 19 or GOLD not in market[0]
            or {str(path): digest for path, digest in market[-1].items()} != config["inputs_sha256"]):
        raise ValueError("unexpected frozen market")
    engine = wick_filter_engine()
    output.mkdir(parents=True)
    results = [replay(output / start, start, market, engine) for start in starts]
    pd.DataFrame(results).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage041_manifest_sha256=grid.STAGE041_SHA, design_sha256=portfolio.sha(DESIGN),
        entrypoint_sha256=portfolio.sha(Path(__file__)), cutoff=TARGET, capital=CAPITAL,
        entry_shadow_filter=FILTER_CONFIG, starts=starts, attempted=len(starts),
        completed=len(results), unknown=0, market_sha256=config["inputs_sha256"],
        source_sha256=config["source_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
