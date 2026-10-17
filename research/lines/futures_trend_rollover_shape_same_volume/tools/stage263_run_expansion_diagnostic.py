"""One fixed, paired training-history comparison on a single expanded source."""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning

import stage262_ai_sample_contract as contract
import stage262_run_model_diagnostic as diagnostic

original = diagnostic.original
LINE = Path(__file__).resolve().parents[1]


def remove_undefined_rank_months(samples: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """A constant future cross-section has no ordering, regardless of model skill."""
    valid = samples.groupby("eval_date")[contract.FUTURE].transform("nunique") > 1
    removed = samples.loc[~valid]
    return samples.loc[valid].copy(), {
        "removed_rows": len(removed), "removed_months": removed.eval_date.nunique(),
        "removed_dates": [str(pd.Timestamp(date).date()) for date in sorted(removed.eval_date.unique())]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=LINE / "outputs/stage263_ai_data_expansion")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if (output / "expansion_summary.json").exists():
        raise SystemExit("Result exists; do not repeat completed fits.")
    start = time.perf_counter()
    inputs = {name: diagnostic.identity(output / name) for name in [
        "source_position_changes.csv", "source_entry_candidate_snapshots.csv", "source_summary.json",
        "market_daily_coverage.csv", "daily_coverage.json"]}
    original.POSITION_CHANGES_PATH = output / "source_position_changes.csv"
    original.ENTRY_SNAPSHOTS_PATH = output / "source_entry_candidate_snapshots.csv"
    source_summary = json.loads((output / "source_summary.json").read_text())
    daily = original.build_product_daily()
    featured = original.add_rolling_features(daily)
    legacy, features = original.build_monthly_samples(featured)
    if len(features) != 108:
        raise RuntimeError("Feature set changed")
    position = pd.read_csv(original.POSITION_CHANGES_PATH, usecols=["date", "vt_symbol"])
    position["date"] = pd.to_datetime(position.date)
    position["product_vt_symbol"] = position.vt_symbol.map(original.product_from_contract)
    observed = position[["date", "product_vt_symbol"]].drop_duplicates().assign(observed=True)
    market = pd.read_csv(output / "market_daily_coverage.csv", parse_dates=["date"])
    if "product_vt_symbol" not in market:
        market = market.rename(columns={"product": "product_vt_symbol"})
    if market.duplicated(["date", "product_vt_symbol"]).any():
        raise RuntimeError("Duplicate daily market coverage")
    if not pd.api.types.is_bool_dtype(market.coverage_ok):
        raise RuntimeError("market coverage must be explicit booleans")
    mapped = market[["date", "product_vt_symbol", "coverage_ok"]].rename(columns={"coverage_ok": "mapped"})
    coverage = (daily[["date", "product_vt_symbol"]].merge(observed, how="left")
                .merge(mapped, how="left"))
    # Source position artifacts can carry unchanged closes on missing days. Market
    # coverage is therefore independently required, not inferred from those rows.
    coverage["observed"] = coverage.observed.eq(True)
    coverage["mapped"] = coverage.mapped.eq(True)
    metadata = contract.build_window_metadata(daily, coverage)
    samples = legacy.merge(metadata, on=["eval_date", "product_vt_symbol"], validate="one_to_one")
    clean = contract.rerank_eligible(samples)
    clean = clean.loc[clean.cross_section_count >= 8].copy()
    clean, undefined_rank_audit = remove_undefined_rank_months(clean)
    clean["source_start"] = "2015-01-01"
    clean["position_source_sha"] = inputs["source_position_changes.csv"]["sha256"]
    clean["candidate_source_sha"] = inputs["source_entry_candidate_snapshots.csv"]["sha256"]
    arms = {"E0_train_2020_plus": clean.loc[clean.eval_date >= "2020-01-01"].copy(),
            "E1_train_2015_plus": clean.copy()}
    if not arms["E0_train_2020_plus"].equals(arms["E1_train_2015_plus"].loc[clean.eval_date >= "2020-01-01"]):
        raise RuntimeError("Common features/labels/weights changed across arms")
    samples.to_csv(output / "all_sample_contract.csv", index=False)
    clean.to_csv(output / "eligible_samples.csv", index=False)
    dates = sorted(clean.loc[clean.eval_date.between("2022-01-01", "2026-06-30"), "eval_date"].unique())
    warnings.simplefilter("error", ConvergenceWarning)
    results, predictions, skips = [], [], []
    fits = 0
    for date in dates:
        date = pd.Timestamp(date)
        test = clean.loc[clean.eval_date == date].copy()
        trains = {arm: contract.mature_training(data, date) for arm, data in arms.items()}
        if any(data.eval_date.nunique() < 12 or data[contract.TARGET].nunique() < 2 for data in trains.values()):
            skips.append(str(date.date()))
            continue
        for arm, train in trains.items():
            model = original.train_model(train, features)
            fits += 1
            scored = test[["eval_date", "product_vt_symbol", contract.FUTURE, contract.TARGET]].copy()
            scored["score"] = original.score_model(model, test, features)
            scored["arm"] = arm
            predictions.append(scored)
            results.append({"arm": arm, "eval_date": date, **contract.month_metrics(scored),
                            "train_rows": len(train), "train_months": train.eval_date.nunique(),
                            "early_train_rows": int((train.eval_date < "2020-01-01").sum()),
                            "early_train_months": train.loc[train.eval_date < "2020-01-01", "eval_date"].nunique(),
                            "max_train_label_end": train.label_end.max()})
        if date.month in (6, 12):
            print(f"completed {date.date()}, fits={fits}", flush=True)
    metrics = pd.DataFrame(results)
    metrics.to_csv(output / "expansion_monthly_metrics.csv", index=False)
    pd.concat(predictions, ignore_index=True).to_csv(output / "expansion_monthly_predictions.csv", index=False)
    aggregates = diagnostic.aggregate(metrics)
    metrics["year"] = metrics.eval_date.dt.year
    annual = metrics.groupby(["year", "arm"]).agg(
        months=("eval_date", "nunique"), mean_rank_ic=("rank_ic", "mean"),
        mean_top_rank_lift=("top_rank_lift", "mean"), mean_auc=("auc", "mean")).reset_index()
    annual.to_csv(output / "expansion_annual_metrics.csv", index=False)
    pivot = metrics.pivot(index="eval_date", columns="arm", values="rank_ic")
    interval = contract.paired_block_interval((pivot.E1_train_2015_plus - pivot.E0_train_2020_plus).to_numpy())
    values = aggregates.set_index("arm")
    ic_delta = float(values.loc["E1_train_2015_plus", "mean_rank_ic"] - values.loc["E0_train_2020_plus", "mean_rank_ic"])
    lift_delta = float(values.loc["E1_train_2015_plus", "mean_top_rank_lift"] - values.loc["E0_train_2020_plus", "mean_top_rank_lift"])
    passed = ic_delta > 0 and lift_delta > 0 and interval["ci95_low"] > 0
    asof = pd.Timestamp("2026-09-30")
    train_counts = {arm: {"rows": len(contract.mature_training(data, asof)),
                          "months": contract.mature_training(data, asof).eval_date.nunique()}
                    for arm, data in arms.items()}
    scripts = [Path(__file__), Path(contract.__file__), Path(original.__file__),
               LINE / "stages/20261017_1702_stage263_ai_expansion_protocol.md"]
    target_diagnostics = clean.assign(pre2020=clean.eval_date < "2020-01-01").groupby("pre2020").agg(
        rows=("eval_date", "size"), months=("eval_date", "nunique"),
        zero_future_rows=(contract.FUTURE, lambda values: int(values.eq(0).sum())),
        positive_class_fraction=(contract.TARGET, "mean")).reset_index()
    summary = {"kind": "OFFLINE_SINGLE_SOURCE_TRAINING_HISTORY_EXPANSION",
               "generated_at": datetime.now().astimezone().isoformat(), "inputs": inputs,
               "scripts": [diagnostic.identity(path) for path in scripts],
               "feature_count": len(features), "feature_columns": features,
               "source_engine_summary": str(output / "source_summary.json"),
               "source_runtime": source_summary.get("runtime"),
               "model_runtime": {"python": platform.python_version(), "numpy": np.__version__,
                                 "pandas": pd.__version__, "sklearn": sklearn.__version__},
               "test_months": metrics.eval_date.nunique(), "first_test": str(metrics.eval_date.min().date()),
               "last_test": str(metrics.eval_date.max().date()), "actual_model_fits": fits,
               "skipped_months": skips, "common_feature_label_weight_values_identical": True,
               "eligible_rows": len(clean), "eligible_months": clean.eval_date.nunique(),
               "undefined_rank_months_excluded": undefined_rank_audit,
               "target_diagnostics": target_diagnostics.to_dict("records"),
               "extra_pre2020_rows": int((clean.eval_date < "2020-01-01").sum()),
               "extra_pre2020_months": clean.loc[clean.eval_date < "2020-01-01", "eval_date"].nunique(),
               "training_asof_2026_09_30": train_counts, "aggregates": aggregates.to_dict("records"),
               "paired_rank_ic_difference": interval, "ic_delta": ic_delta, "top_rank_lift_delta": lift_delta,
               "predeclared_model_evidence_gate_passed": bool(passed),
               "decision": "additional_account_test_requires_source_and_annual_review" if passed else "stop_no_account_backtest_no_parameter_search",
               "elapsed_seconds": round(time.perf_counter()-start, 3),
               "limits": ["Conditional on fixed ex-post pairwise/strategy specifications; not historical PIT proof",
                          "Not a C9 account backtest or evidence of deployable profitability",
                          "2025-2026 repeatedly inspected; only retrospective diagnostics",
                          "Missing daily bars can alter simulated source account path; affected feature/label windows excluded",
                          "No 2014 preload; source begins cold in 2015; complete 120-day history required",
                          "Only future forward observation after freeze is genuinely unseen"]}
    (output / "expansion_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["test_months", "actual_model_fits", "extra_pre2020_rows",
                       "extra_pre2020_months", "training_asof_2026_09_30", "aggregates",
                       "paired_rank_ic_difference", "decision", "elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
