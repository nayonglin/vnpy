"""Independently audit the bounded Stage058 nonferrous-alternative selection."""
import argparse
from datetime import datetime
from itertools import combinations, product
import json
from math import fsum
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from stage040_s19_without_gold_audit import cents
from stage043_s19_daily_one_audit import Bar
from stage057_diverse10_audit import (
    CATEGORIES as ORIGINAL_CATEGORIES, LIMIT, WINDOWS, TAIL_CERT,
    check_manifest, load_json, sha, extend_raw_market, compare_frame,
    independent_returns, independent_pairs,
)

LINE = Path(__file__).resolve().parents[1]
RESULT = LINE / "outputs/stage058_diverse10_20261103"
PRIOR = LINE / "outputs/stage057_diverse10_20261104"
APPROVED = LINE / "outputs/stage024_market/approved_v1"
CATEGORIES = {**ORIGINAL_CATEGORIES, "有色金属": ["cu.SHFE", "al.SHFE", "ni.SHFE"]}
CUTOFF = "2026-11-03"


def independent_market():
    calendar, guard, mains, symbols, by_epoch, settings = extend_raw_market(load_json(TAIL_CERT))
    calendar = [day for day in calendar if day <= CUTOFF]
    bars = pd.read_csv(APPROVED / "added_bars.csv")
    normalized = bars.vt_symbol.str.replace(r"\d+(?=\.)", "", regex=True)
    bars = bars.loc[normalized.isin(["al.SHFE", "ni.SHFE"]) & bars.date.le(CUTOFF)]
    assert bars.volume.gt(0).all() and not bars.duplicated(["date", "contract_epoch_id"]).any()
    for row in bars.itertuples(index=False):
        bar = Bar(row.vt_symbol, row.contract_epoch_id, *map(cents, (row.open, row.high, row.low, row.close)))
        assert bar.close > 0
        key, symbol_key = (row.date, bar.epoch), (row.date, bar.symbol)
        if key in by_epoch:
            assert by_epoch[key] == bar and symbols[symbol_key] == bar
        else:
            assert symbol_key not in symbols
            by_epoch[key] = symbols[symbol_key] = bar
    mapping = pd.read_csv(APPROVED / "added_mapping.csv", keep_default_na=False)
    mapping = mapping.loc[mapping.continuous_symbol_vt.isin(["al.SHFE", "ni.SHFE"]) & mapping.date.le(CUTOFF)]
    for row in mapping.itertuples(index=False):
        key = row.date, row.continuous_symbol_vt
        if not row.main_contract_vt:
            continue
        if key in mains:
            assert mains[key] == row.main_contract_vt
        else:
            mains[key] = row.main_contract_vt
    return calendar, guard, mains, symbols, by_epoch, settings


def independent_choices(pairs):
    lookup = {tuple(sorted((row.left, row.right))): row for row in pairs.itertuples(index=False)}
    choices = []
    for chosen in product(*CATEGORIES.values()):
        links = [lookup[tuple(sorted(pair))] for pair in combinations(chosen, 2)]
        assert len(links) == 45
        choices.append({
            "products": json.dumps(sorted(chosen)), "allowed": all(link.allowed for link in links),
            "max_correlation": max(link.score for link in links),
            "mean_pair_score": fsum(link.score for link in links) / 45,
            "violating_pairs": sum(not link.allowed for link in links),
        })
    return pd.DataFrame(choices).sort_values(
        ["max_correlation", "mean_pair_score", "products"], kind="stable",
    ).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path)
    arguments = parser.parse_args()
    manifest_counts = {path.name: check_manifest(path) for path in (RESULT, PRIOR)}
    receipt = load_json(RESULT / "selection.json")
    prior = load_json(PRIOR / "selection.json")
    assert prior["status"] == "NO_FEASIBLE_SELECTION" and prior["eligible_combinations"] == 0
    assert receipt["original_infeasible_manifest_sha256"] == sha(PRIOR / "SHA256SUMS")
    assert receipt["core_entrypoint_sha256"] == prior["entrypoint_sha256"] == sha(LINE / "tools/stage057_diverse10.py")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261105_1307_stage058_nonferrous_extension_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage058_diverse10_nonferrous.py")
    assert receipt["loader_sha256"] == sha(LINE / "tools/stage025_delivery_guard.py")
    assert receipt["cutoff"] == CUTOFF and receipt["categories"] == CATEGORIES
    assert receipt["windows"] == prior["windows"] == {name: list(value) for name, value in WINDOWS.items()}
    assert receipt["correlation_limit"] == prior["correlation_limit"] == LIMIT
    assert receipt["selection_rule"] == prior["selection_rule"]
    assert all(sha(Path(path)) == digest for path, digest in receipt["market_sha256"].items())
    approved_receipt = load_json(APPROVED / "receipt.json")
    assert set(approved_receipt["inputs_sha256"].items()) <= set(receipt["market_sha256"].items())
    assert receipt["market_sha256"][str(APPROVED.resolve() / "receipt.json")] == sha(APPROVED / "receipt.json")
    products = sorted(product_name for category in CATEGORIES.values() for product_name in category)
    assert len(products) == len(set(products)) == 23 and "zn.SHFE" not in products
    assert set(products) - set(product_name for category in ORIGINAL_CATEGORIES.values() for product_name in category) == {"al.SHFE", "ni.SHFE"}
    assert set(products) <= set(approved_receipt["products"])
    market = independent_market()
    daily, weekly, evidence, switch_days = independent_returns(products, market)
    for name, expected in (("daily_log_returns.csv", daily), ("weekly_log_returns.csv", weekly)):
        compare_frame(expected, pd.read_csv(RESULT / name, index_col="date"), name)
    compare_frame(evidence, pd.read_csv(RESULT / "return_evidence.csv"), "all same-epoch returns")
    original_daily = pd.read_csv(PRIOR / "daily_log_returns.csv", index_col="date")
    original_weekly = pd.read_csv(PRIOR / "weekly_log_returns.csv", index_col="date")
    original_products = original_daily.columns.tolist()
    compare_frame(
        daily[original_products], original_daily.loc[original_daily.index <= CUTOFF],
        "original 21 daily returns before the shared cutoff",
    )
    compare_frame(weekly[original_products], original_weekly, "unchanged original 21 completed-week returns")
    pairs = independent_pairs(daily, weekly)
    compare_frame(pairs, pd.read_csv(RESULT / "pairwise.csv"), "all 253 pair statistics", tolerance=1e-10)
    assert len(pairs) == 253
    candidates = independent_choices(pairs)
    compare_frame(candidates, pd.read_csv(RESULT / "candidates.csv"), "all 360 candidates")
    assert len(candidates) == len(set(candidates.products)) == receipt["attempted_combinations"] == 360
    valid = candidates.loc[candidates.allowed]
    assert len(valid) == receipt["eligible_combinations"]
    selected = json.loads(valid.iloc[0].products) if not valid.empty else []
    assert receipt["selected"] == selected and receipt["status"] == ("SELECTED_FOR_RESEARCH" if selected else "NO_FEASIBLE_SELECTION")
    assert receipt["selected_by_category"] == {
        name: next((item for item in values if item in selected), None) for name, values in CATEGORIES.items()
    }
    selected_pairs = pairs.loc[pairs.left.isin(selected) & pairs.right.isin(selected)]
    compare_frame(
        selected_pairs.reset_index(drop=True), pd.read_csv(RESULT / "selected_pairs.csv"),
        "all selected 45 pairs", tolerance=1e-10,
    )
    assert len(selected) == 10 and len(selected_pairs) == 45 and selected_pairs.allowed.all()
    assert abs(receipt["maximum_pair_score"] - valid.iloc[0].max_correlation) < 1e-12
    assert abs(receipt["mean_pair_score"] - valid.iloc[0].mean_pair_score) < 1e-12
    for name, (length, _) in WINDOWS.items():
        sample = weekly.iloc[-length:] if name.startswith("weekly") else daily.iloc[-length:]
        assert receipt["data_windows"][name] == {
            "first": sample.index[0], "last": sample.index[-1], "observations": len(sample),
        }
    historical_high = selected_pairs.loc[selected_pairs.rolling52_abs_max.ge(LIMIT)]
    certificate = {
        "schema": "stage058_independent_nonferrous_selection_audit_v1", "verdict": "PASS_WITH_LIMITATIONS",
        "selection_status": receipt["status"],
        "audited_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "audit_script_sha256": sha(Path(__file__)),
        "independent_statistic_source_sha256": sha(LINE / "reviews/stage057_diverse10_audit.py"),
        "result_manifest_sha256": sha(RESULT / "SHA256SUMS"),
        "original_infeasible_manifest_sha256": sha(PRIOR / "SHA256SUMS"),
        "checked_manifests": manifest_counts, "market_input_hashes": len(receipt["market_sha256"]),
        "financial_replays": 0, "cutoff": CUTOFF,
        "matrix_products": len(products),
        "return_rows": {"daily_matrix": len(daily), "weekly_matrix": len(weekly), "daily_evidence": len(evidence)},
        "same_epoch_returns_on_main_switch_days": switch_days,
        "pair_statistics": len(pairs), "candidate_combinations": len(candidates),
        "eligible_combinations": len(valid), "selected": selected,
        "selected_pairs": len(selected_pairs), "all_selected_pairs_pass": bool(selected_pairs.allowed.all()),
        "maximum_pair_score": float(valid.iloc[0].max_correlation),
        "mean_pair_score": float(valid.iloc[0].mean_pair_score),
        "data_windows": receipt["data_windows"],
        "historical_52_week_pairs_over_060": historical_high.to_dict("records"),
        "limitations": [
            "Aluminium and nickel were added adaptively after the original gold/copper mandatory-category infeasibility.",
            "The 23-candidate category-constrained search is restricted to the inherited pool and the documented two alternatives.",
            "The common cutoff is one session earlier than Stage057 because the two alternatives lack admitted November 4 data.",
            "The author-defined categories do not span all futures sub-industries or missing grain and crude-oil markets.",
            "The 0.60 threshold and windows are research judgments; selected historical rolling correlations have exceeded the threshold.",
            "A current-correlation selection does not have historical point-in-time or out-of-sample qualification.",
            "Fixed one lot has unequal risk and margin; descriptive price correlations do not establish strategy PnL or funding diversification.",
        ],
    }
    print(json.dumps(certificate, ensure_ascii=False, indent=2), flush=True)
    if arguments.certificate:
        with arguments.certificate.open("x") as file:
            json.dump(certificate, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")


if __name__ == "__main__":
    main()
