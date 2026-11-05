"""Replay the frozen 15w S19 windows with gold excluded from the product loop."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import run_weekly_portfolio as portfolio
from run_stage021_multicycle import write_checksums
from stage033_s19_annual_starts import LINE, MARKET, TARGET, extend, load
from stage035_s19_half_pct import TAIL
from stage036_s19_paired_mc import verify_manifest
from stage037_s19_fixed_one_150k import CAPITAL, reconstruct_opening
from stage038_s19_fixed_one_150k_halfyear import PARENT, PARENT_SHA, STARTS

GOLD = "au.SHFE"
HALFYEAR = LINE / "outputs/stage038_s19_fixed_one_150k_halfyear_20261104"
HALFYEAR_SHA = "0e3f8aaaba64eac4bfb21284e66944fd2099091182c1e8dcc0c7cf3db3fbf5a8"
DESIGN = LINE / "stages/20261104_1808_stage040_s19_without_gold_design.md"
WINDOWS = ("2015-01-01", *STARTS)
METRICS = ("equity", "net_pnl", "return_pct", "max_dd_pct", "sharpe", "closed_cycles",
           "wins", "losses", "win_rate_pct", "fills", "slippage", "commission")


def metrics(root, daily, opening, summary):
    free = (daily.equity - daily.margin).round(8)
    close_gaps = set(daily.loc[free.lt(0), "date"])
    open_gaps = set(opening.loc[opening.free_equity.lt(0), "date"])
    all_gaps = close_gaps | open_gaps
    cycles = pd.read_csv(root / "cycles.csv")
    return dict(
        **{key: summary[key] for key in METRICS},
        gold_net_pnl=round(cycles.loc[cycles["product"].eq(GOLD), "net_pnl"].sum(), 8),
        peak_close_margin=round(daily.margin.max(), 8),
        peak_open_margin=opening.margin.max(),
        min_close_free_equity=free.min(),
        min_open_free_equity=opening.free_equity.min(),
        close_deficit_days=len(close_gaps),
        opening_deficit_days=len(open_gaps),
        deficit_days=len(all_gaps),
        first_deficit=min(all_gaps, default=""),
        max_shortfall=max(0, -min(free.min(), opening.free_equity.min())),
        minimum_close_equity=daily.equity.min(),
        max_close_positions=int(daily.positions.max()),
    )


def replay(output, start, market, reference):
    with patch.object(portfolio, "INITIAL", CAPITAL), patch.object(portfolio, "START", start):
        with redirect_stdout(StringIO()):
            portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                          block_four_up=True, delivery_guard=True, market_loader=lambda: market)

    baseline_inputs = json.loads((reference / "inputs.json").read_text())
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs != {**baseline_inputs, "products": market[0]}:
        raise ValueError(f"configuration drift beyond gold removal: {start}")

    daily = pd.read_csv(output / "daily.csv")
    baseline_daily = pd.read_csv(reference / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    if (not daily.date.equals(baseline_daily.date) or daily.date.iat[-1] != TARGET
            or daily.cash.iat[0] != CAPITAL or daily.positions.iat[0] != 0
            or fills.date.min() <= daily.date.iat[0] or fills.signal_day.min() < daily.date.iat[0]):
        raise ValueError(f"bad cold start or trading calendar: {start}")

    opening = reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text())
    no_gold = metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = no_gold["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    baseline = metrics(reference, baseline_daily, pd.read_csv(reference / "opening_funding.csv"),
                       json.loads((reference / "summary.json").read_text()))
    if abs(no_gold["net_pnl"] - baseline["net_pnl"] + baseline["gold_net_pnl"]) > 1e-6:
        raise ValueError(f"net PnL does not reconcile to deleted gold: {start}")
    return dict(
        calendar_start=start, first_session=daily.date.iat[0], last_session=TARGET, days=len(daily),
        **{f"s19_{key}": value for key, value in baseline.items()},
        **{f"no_gold_{key}": value for key, value in no_gold.items()},
    )


def run(output):
    verify_manifest(PARENT, PARENT_SHA)
    verify_manifest(HALFYEAR, HALFYEAR_SHA)
    market = extend(load(MARKET, control=True), TAIL)
    products = [product for product in market[0] if product != GOLD]
    baseline = json.loads((PARENT / "inputs.json").read_text())
    if (len(products) != 18 or list(market[0]) != baseline["products"]
            or {str(path): digest for path, digest in market[-1].items()} != baseline["inputs_sha256"]):
        raise ValueError("frozen market or product list drift")
    no_gold_market = (products, *market[1:])
    output.mkdir(parents=True)
    results = [replay(output / start, start, no_gold_market,
                      PARENT if start == WINDOWS[0] else HALFYEAR / start) for start in WINDOWS]
    pd.DataFrame(results).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        stage037_manifest_sha256=PARENT_SHA, stage038_manifest_sha256=HALFYEAR_SHA,
        design_sha256=portfolio.sha(DESIGN), entrypoint_sha256=portfolio.sha(Path(__file__)),
        cutoff=TARGET, capital=CAPITAL, excluded_product=GOLD, products=products,
        starts=WINDOWS, attempted_runs=len(WINDOWS), completed_runs=len(results), unknown_runs=0,
        market_sha256=baseline["inputs_sha256"], source_sha256=baseline["source_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
