"""Replay the requested S26 portfolio in one shared 2022 account."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import stage046_s44_individual_2022 as solo
from stage040_s19_without_gold import HALFYEAR, HALFYEAR_SHA, PARENT, verify_manifest

LINE = solo.LINE
SOLO = LINE / "outputs/stage046_s44_individual_2022"
SOLO_SHA = "632f823b1589c51969055203dfd63d69cb0ee57477721e1562cf5a5fe09889be"
DESIGN = LINE / "stages/20261104_2032_stage047_s26_2022_design.md"
ADDED = ("p.DCE", "ss.SHFE", "zn.SHFE", "ni.SHFE", "ag.SHFE", "jd.DCE", "TA.CZCE")


def period_metrics(daily, opening, fills, cycles):
    close_free = (daily.equity - daily.margin).round(8)
    deficit = set(daily.loc[close_free.lt(0), "date"]) | set(opening.loc[opening.free_equity.lt(0), "date"])
    closed = cycles.loc[cycles.exit_day.ne("") & cycles.exit_day.le(solo.END)]
    returns = daily.equity.pct_change().fillna(0)
    equity = daily.equity.iat[-1]
    return dict(
        equity=equity, net_pnl=equity - solo.CAPITAL, return_pct=100*(equity-solo.CAPITAL)/solo.CAPITAL,
        max_dd_pct=100*daily.drawdown.min(), sharpe=returns.mean()/returns.std()*np.sqrt(252),
        closed_cycles=len(closed), fills=len(fills), win_rate_pct=100*closed.net_pnl.gt(0).mean(),
        slippage=fills.slippage.sum(), commission=fills.commission.sum(),
        deficit_days=len(deficit), first_deficit=min(deficit, default=""),
        max_shortfall=max(0, -min(close_free.min(), opening.free_equity.min())),
        peak_close_margin=round(daily.margin.max(), 8), peak_open_margin=opening.margin.max(),
        max_close_positions=int(daily.positions.max()),
    )


def ledgers(root):
    def read(name):
        return pd.read_csv(root / f"{name}.csv", keep_default_na=False)
    return tuple(read(name).query("date <= @solo.END").reset_index(drop=True)
                 for name in ("daily", "opening_funding", "fills")) + (read("cycles"),)


def run(output):
    verify_manifest(SOLO, SOLO_SHA)
    verify_manifest(HALFYEAR, HALFYEAR_SHA)
    if solo.portfolio.sha(Path(solo.portfolio.__file__)) != solo.ENGINE_SHA:
        raise ValueError("frozen engine changed")
    base_products = json.loads((PARENT / "inputs.json").read_text())["products"]
    standalone = pd.read_csv(SOLO / "product_metrics.csv").set_index("product")
    if set(standalone.head(15).index) - set(base_products) != set(ADDED):
        raise ValueError("added pool does not match frozen selection")
    products = sorted(set(base_products) | set(ADDED))
    available, days, *rest = solo.load(solo.MARKET, control=False)
    pins = {str(path): digest for path, digest in rest[-1].items()}
    if len(products) != 26 or not set(products) <= set(available):
        raise ValueError("invalid S26 pool")
    if pins != json.loads((SOLO / "receipt.json").read_text())["market_sha256"]:
        raise ValueError("market differs from Stage046")
    market = (products, [day for day in days if day <= solo.END], *rest)

    with patch.object(solo.portfolio, "INITIAL", solo.CAPITAL), patch.object(
        solo.portfolio, "START", solo.START
    ), redirect_stdout(StringIO()):
        solo.portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                           block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    opening = solo.reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)

    control = HALFYEAR / solo.START
    base_daily, base_opening, base_fills, base_cycles = ledgers(control)
    if (not daily.date.equals(base_daily.date) or daily.date.iat[-1] != solo.END
            or daily.positions.iat[0] != 0 or daily.cash.iat[0] != solo.CAPITAL
            or not fills.volume.eq(1).all() or not fills["product"].isin(products).all()
            or fills.signal_day.min() < daily.date.iat[0]):
        raise ValueError("unexpected calendar, sizing, scope or initial position")
    for product in products:
        solo_fills = pd.read_csv(SOLO / product / "fills.csv")
        expected = fills[fills["product"].eq(product)].reset_index(drop=True)
        pd.testing.assert_frame_equal(expected.drop(columns="cycle"), solo_fills.drop(columns="cycle"),
                                      check_dtype=False, rtol=0, atol=1e-7)
    cycles = pd.read_csv(output / "cycles.csv", keep_default_na=False)
    comparison = dict(
        start=daily.date.iat[0], end=solo.END, days=len(daily), initial=solo.CAPITAL,
        s19=period_metrics(base_daily, base_opening, base_fills, base_cycles),
        s26=period_metrics(daily, opening, fills, cycles),
        added_pnl={p: float(cycles.loc[cycles["product"].eq(p), "net_pnl"].sum()) for p in ADDED},
    )
    if abs(comparison["s26"]["net_pnl"] - comparison["s19"]["net_pnl"]
           - sum(comparison["added_pnl"].values())) > 1e-6:
        raise ValueError("portfolio change fails PnL reconciliation")
    (output / "comparison.json").write_text(json.dumps(comparison, indent=2, allow_nan=False) + "\n")
    receipt = dict(
        stage046_manifest_sha256=SOLO_SHA, stage038_manifest_sha256=HALFYEAR_SHA,
        engine_sha256=solo.ENGINE_SHA, design_sha256=solo.portfolio.sha(DESIGN),
        entrypoint_sha256=solo.portfolio.sha(Path(__file__)), products=products, added=list(ADDED),
        start=solo.START, end=solo.END, capital=solo.CAPITAL, market_sha256=pins,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    solo.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
