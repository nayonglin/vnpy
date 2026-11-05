"""Replay S19 plus the top three of the seven Stage047 additions."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage049_s26_halfyear as prior
from stage047_s26_2022 import SOLO, SOLO_SHA

base = prior.base
LINE = base.LINE
S26 = LINE / "outputs/stage049_s26_halfyear_20261104"
S26_SHA = "3dd745103129525d81cd58a1b69de810173e7d5279c5fb7d3e02d8afd990dd8a"
S26_AUDIT = LINE / "reviews/stage049_s26_halfyear_audit.json"
S26_AUDIT_SHA = "7955f08b99783ff54b0a05e235f66365e77057814a30d2fe4bb18f7780be2229"
DESIGN = LINE / "stages/20261104_2053_stage050_s22_halfyear_design.md"
ADDED = ("p.DCE", "ss.SHFE", "zn.SHFE")


def replay(folder, start, market, inputs, references):
    with patch.object(base.portfolio, "INITIAL", base.CAPITAL), patch.object(
        base.portfolio, "START", start
    ), redirect_stdout(StringIO()):
        base.portfolio.run(folder, week_body_filter=True, reverse_after_stop=True,
                           block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    if prior.read_json(folder / "inputs.json") != {**inputs, "start": start, "products": market[0]}:
        raise ValueError(f"configuration drift: {start}")
    daily = pd.read_csv(folder / "daily.csv")
    fills = pd.read_csv(folder / "fills.csv")
    signals = pd.read_csv(folder / "signals.csv")
    first = daily.date.iat[0]
    if (daily.date.tolist() != [day for day in market[1] if day >= start]
            or (first, daily.date.iat[-1], len(daily)) != (
                references["first_session"], references["last_session"], references["days"])
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0
            or not fills.volume.eq(1).all() or fills.date.le(first).any()
            or fills.signal_day.lt(first).any() or signals.date.lt(first).any()):
        raise ValueError(f"invalid calendar or cold start: {start}")

    terminal = prior.read_json(folder / "terminal.json")
    if (any((base.TARGET, pos["epoch"]) not in market[5] for pos in terminal["positions"].values())
            or pd.read_csv(folder / "gaps.csv").date.eq(base.TARGET).any()):
        raise ValueError(f"missing final-day coverage: {start}")
    for name in ("fills", "signals"):
        original = pd.read_csv(S26 / start / f"{name}.csv")
        selected = original.loc[original["product"].isin(market[0])]
        actual = fills if name == "fills" else signals
        pd.testing.assert_frame_equal(actual.drop(columns="cycle", errors="ignore"),
                                      selected.drop(columns="cycle", errors="ignore").reset_index(drop=True),
                                      obj=f"retained {name}: {start}")

    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    path = folder / "summary.json"
    summary = prior.read_json(path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    cycles = pd.read_csv(folder / "cycles.csv")
    added = cycles.loc[cycles["product"].isin(ADDED)].groupby("product").net_pnl.sum()
    if abs(metrics["net_pnl"] - references["s19_net_pnl"] - added.sum()) > 1e-6:
        raise ValueError(f"added PnL does not reconcile: {start}")
    return dict(calendar_start=start, **references,
                **{f"s22_{key}": value for key, value in metrics.items()},
                **{f"s22_added_pnl_{key}": added[key] for key in ADDED})


def run(output):
    manifests = {SOLO: SOLO_SHA, S26: S26_SHA, prior.FULL: prior.FULL_SHA}
    for path, digest in manifests.items():
        base.verify_manifest(path, digest)
    if (base.portfolio.sha(S26_AUDIT) != S26_AUDIT_SHA
            or base.portfolio.sha(Path(base.portfolio.__file__)) != prior.ENGINE_SHA):
        raise ValueError("frozen engine or independent review changed")
    ranking = pd.read_csv(SOLO / "product_metrics.csv").set_index("product").net_pnl
    if tuple(ranking.loc[list(prior.ADDED)].nlargest(3).index) != ADDED:
        raise ValueError("selected products differ from frozen ranking")

    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    reference = prior.read_json(S26 / "receipt.json")
    full_market = prior.add_tail((reference["products"], *expanded[1:]), original, prior.TAIL)
    market_hashes = {str(path): digest for path, digest in full_market[-1].items()}
    products = [p for p in full_market[0] if p in set(original[0]) | set(ADDED)]
    if market_hashes != reference["market_sha256"] or len(products) != 22:
        raise ValueError("unexpected market or product universe")
    market = (products, *full_market[1:])
    controls = pd.read_csv(S26 / "window_metrics.csv", keep_default_na=False).set_index("calendar_start")
    if tuple(controls.index) != prior.STARTS:
        raise ValueError("unexpected reference starts")
    controls = controls.drop(columns=["pnl_difference", "return_difference_pp", "drawdown_difference_pp"])
    inputs = prior.read_json(prior.FULL / "inputs.json")
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market, inputs, controls.loc[start].to_dict())
            for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    receipt = dict(
        manifests_sha256={path.name: digest for path, digest in manifests.items()},
        stage049_audit_sha256=S26_AUDIT_SHA, engine_sha256=prior.ENGINE_SHA,
        design_sha256=base.portfolio.sha(DESIGN), entrypoint_sha256=base.portfolio.sha(Path(__file__)),
        market_sha256=market_hashes, cutoff=base.TARGET, capital=base.CAPITAL, products=products,
        added=ADDED, starts=prior.STARTS, attempted_runs=len(prior.STARTS), completed_runs=len(rows),
        unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
