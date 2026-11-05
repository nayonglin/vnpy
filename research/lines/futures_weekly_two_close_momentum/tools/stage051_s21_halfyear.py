"""Replay Stage050 without zinc over its frozen half-year grid."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage050_s22_halfyear as parent

prior, base, LINE = parent.prior, parent.base, parent.LINE
S22 = LINE / "outputs/stage050_s22_halfyear_20261104"
S22_SHA = "24a1b662eef7570a450ecf10d9462eb40b30df700b9e58fa0a5e5121bdf91545"
AUDIT = LINE / "reviews/stage050_s22_halfyear_audit.json"
AUDIT_SHA = "4f7a1487a911d41a499e7f065e73bf255d783cc0c7f33edefb0a4198465d9ae6"
DESIGN = LINE / "stages/20261104_2057_stage051_s21_halfyear_design.md"
EXCLUDED = "zn.SHFE"
ADDED = ("p.DCE", "ss.SHFE")


def replay(folder, start, market, reference):
    baseline = S22 / start
    with patch.object(base.portfolio, "INITIAL", base.CAPITAL), patch.object(
        base.portfolio, "START", start
    ), redirect_stdout(StringIO()):
        base.portfolio.run(folder, week_body_filter=True, reverse_after_stop=True,
                           block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    expected_inputs = {**prior.read_json(baseline / "inputs.json"), "products": market[0]}
    if prior.read_json(folder / "inputs.json") != expected_inputs:
        raise ValueError(f"strategy inputs changed: {start}")
    daily = pd.read_csv(folder / "daily.csv")
    if (not daily.date.equals(pd.read_csv(baseline / "daily.csv").date)
            or daily.date.iat[-1] != base.TARGET or daily.cash.iat[0] != base.CAPITAL
            or daily.positions.iat[0] != 0):
        raise ValueError(f"cold start or calendar changed: {start}")
    for name in ("fills", "signals"):
        original = pd.read_csv(baseline / f"{name}.csv")
        expected = original.loc[original["product"].ne(EXCLUDED)].reset_index(drop=True)
        actual = pd.read_csv(folder / f"{name}.csv")
        pd.testing.assert_frame_equal(actual.drop(columns="cycle", errors="ignore"),
                                      expected.drop(columns="cycle", errors="ignore"),
                                      obj=f"retained {name}: {start}")
    fills = pd.read_csv(folder / "fills.csv")
    if not fills.volume.eq(1).all() or fills.date.le(daily.date.iat[0]).any():
        raise ValueError(f"invalid fills: {start}")

    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(folder / "opening_funding.csv", index=False)
    path = folder / "summary.json"
    summary = prior.read_json(path)
    metrics = prior.funding_metrics(folder, daily, opening, summary)
    summary["days_margin_above_equity"] = metrics["close_deficit_days"]
    path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    cycles = pd.read_csv(folder / "cycles.csv")
    added = cycles.loc[cycles["product"].isin(ADDED)].groupby("product").net_pnl.sum()
    if (abs(metrics["net_pnl"] - reference["s19_net_pnl"] - added.sum()) > 1e-6
            or abs(metrics["net_pnl"] - reference["s22_net_pnl"]
                   + reference[f"s22_added_pnl_{EXCLUDED}"]) > 1e-6):
        raise ValueError(f"removal PnL does not reconcile: {start}")
    return dict(calendar_start=start, **reference,
                **{f"s21_{key}": value for key, value in metrics.items()},
                **{f"s21_added_pnl_{key}": added.get(key, 0) for key in ADDED})


def run(output):
    base.verify_manifest(S22, S22_SHA)
    if (base.portfolio.sha(AUDIT) != AUDIT_SHA
            or base.portfolio.sha(Path(base.portfolio.__file__)) != prior.ENGINE_SHA):
        raise ValueError("frozen audit or engine changed")
    receipt = prior.read_json(S22 / "receipt.json")
    reference = prior.read_json(parent.S26 / "receipt.json")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    expanded = base.load(base.MARKET, control=False)
    full_market = prior.add_tail((reference["products"], *expanded[1:]), original, prior.TAIL)
    market_hashes = {str(path): digest for path, digest in full_market[-1].items()}
    products = [p for p in receipt["products"] if p != EXCLUDED]
    if (market_hashes != receipt["market_sha256"] or len(products) != 21
            or set(products) != set(original[0]) | set(ADDED)):
        raise ValueError("unexpected frozen market or product list")
    market = (products, *full_market[1:])
    controls = pd.read_csv(S22 / "window_metrics.csv", keep_default_na=False).set_index("calendar_start")
    if tuple(controls.index) != prior.STARTS:
        raise ValueError("unexpected reference starts")
    output.mkdir(parents=True)
    rows = [replay(output / start, start, market, controls.loc[start].to_dict()) for start in prior.STARTS]
    pd.DataFrame(rows).to_csv(output / "window_metrics.csv", index=False)
    result_receipt = dict(
        manifests_sha256={S22.name: S22_SHA}, stage050_audit_sha256=AUDIT_SHA,
        engine_sha256=prior.ENGINE_SHA, design_sha256=base.portfolio.sha(DESIGN),
        entrypoint_sha256=base.portfolio.sha(Path(__file__)), market_sha256=market_hashes,
        cutoff=base.TARGET, capital=base.CAPITAL, products=products, excluded=EXCLUDED,
        added=ADDED, starts=prior.STARTS, attempted_runs=len(prior.STARTS),
        completed_runs=len(rows), unknown_runs=0,
    )
    (output / "receipt.json").write_text(json.dumps(result_receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
