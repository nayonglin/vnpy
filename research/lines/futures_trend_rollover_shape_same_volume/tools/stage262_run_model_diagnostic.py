"""Frozen legacy-source, model-only cleanup diagnostic. Never generates orders/pools."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
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

ROOT = Path(__file__).resolve().parents[4]
LINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/portfolio_backtesting"))
import analyze_qmt_roll_ai_product_suitability_walkforward as original

EXPECTED = {
    "position_changes": "28040df656218a5eafd23200d7a4e24bc475c92743351d10a79bb23ea59be687",
    "entry_candidate_snapshots": "f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0",
    "mapping": "55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325",
}


def identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def observed_coverage(position: Path, mapping: Path, daily: pd.DataFrame) -> pd.DataFrame:
    observed = pd.read_csv(position, usecols=["date", "vt_symbol"])
    observed["date"] = pd.to_datetime(observed.date)
    observed["product_vt_symbol"] = observed.vt_symbol.map(original.product_from_contract)
    observed = observed[["date", "product_vt_symbol"]].drop_duplicates().assign(observed=True)
    mapped = pd.read_csv(mapping, usecols=["date", "main_contract_vt"])
    mapped = mapped.loc[mapped.main_contract_vt.fillna("").str.match(r"^[A-Za-z]+[0-9]{3,4}\.[A-Z]+$")].copy()
    mapped["date"] = pd.to_datetime(mapped.date)
    mapped["product_vt_symbol"] = mapped.main_contract_vt.map(original.product_from_contract)
    mapped = mapped[["date", "product_vt_symbol"]].drop_duplicates().assign(mapped=True)
    return (daily[["date", "product_vt_symbol"]].merge(observed, how="left")
            .merge(mapped, how="left").fillna({"observed": False, "mapped": False}))


def aggregate(metrics: pd.DataFrame) -> pd.DataFrame:
    return metrics.groupby("arm", sort=True).agg(
        months=("eval_date", "nunique"), mean_rank_ic=("rank_ic", "mean"),
        mean_top_rank_lift=("top_rank_lift", "mean"),
        mean_top_half_hit_rate=("top_half_hit_rate", "mean"), mean_auc=("auc", "mean"),
        min_train_rows=("train_rows", "min"), max_train_rows=("train_rows", "max"),
        min_train_months=("train_months", "min"), max_train_months=("train_months", "max")
    ).reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=LINE / "outputs/stage262_ai_sample_contract")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if (output / "model_summary.json").exists():
        raise SystemExit("Result already exists; inspect it instead of repeating the fits.")
    start = time.perf_counter()
    paths = {name: args.source_dir / f"qmt_roll_stage183_ai_source_floor35_{name}_2020_2026_04.csv"
             for name in ("position_changes", "entry_candidate_snapshots")}
    paths["mapping"] = ROOT / "examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
    inputs = {name: identity(path) for name, path in paths.items()}
    for name, value in inputs.items():
        if value["sha256"] != EXPECTED[name]:
            raise RuntimeError(f"Frozen input SHA mismatch: {name}")
    original.POSITION_CHANGES_PATH = paths["position_changes"]
    original.ENTRY_SNAPSHOTS_PATH = paths["entry_candidate_snapshots"]
    daily = original.build_product_daily()
    featured = original.add_rolling_features(daily)
    legacy, features = original.build_monthly_samples(featured)
    if len(features) != 108:
        raise RuntimeError(f"Expected unchanged 108 features, got {len(features)}")
    coverage = observed_coverage(paths["position_changes"], paths["mapping"], daily)
    metadata = contract.build_window_metadata(daily, coverage)
    samples = legacy.merge(metadata, on=["eval_date", "product_vt_symbol"], validate="one_to_one")
    # Full labels only, including the L0 legacy-eligibility reference.
    l0 = samples.loc[samples.label_complete].copy()
    l1 = l0.loc[l0.eligible].copy()
    l2 = contract.rerank_eligible(l0)
    l2 = l2.loc[l2.cross_section_count >= 8].copy()
    if not l1.set_index(["eval_date", "product_vt_symbol"])[features].equals(
            l2.set_index(["eval_date", "product_vt_symbol"])[features]):
        raise RuntimeError("Common feature values changed during label cleanup")
    arms = {"L0_legacy_purged": l0, "L1_eligible_original_rank": l1,
            "L2_eligible_valid_rank": l2}
    prediction_dates = sorted(l2.loc[l2.eval_date.between("2022-01-01", "2026-06-30"), "eval_date"].unique())
    output.mkdir(parents=True, exist_ok=True)
    provenance = {"source_engine": "legacy_floor35_20w_risk045_frozen_m0008_source",
                  "source_start": str(daily.date.min().date()),
                  "source_commit": "unknown_not_inferred_from_current_checkout",
                  "position_source_sha": inputs["position_changes"]["sha256"],
                  "candidate_source_sha": inputs["entry_candidate_snapshots"]["sha256"]}
    for key, value in provenance.items():
        samples[key] = value
    samples.to_csv(output / "sample_contract.csv", index=False)
    l2.to_csv(output / "eligible_rank_samples.csv", index=False)
    results, predictions, skips = [], [], []
    warnings.simplefilter("error", ConvergenceWarning)
    fits = 0
    for prediction_date in prediction_dates:
        prediction_date = pd.Timestamp(prediction_date)
        test = l2.loc[l2.eval_date == prediction_date].copy()
        trains = {name: contract.mature_training(frame, prediction_date) for name, frame in arms.items()}
        if any(frame.eval_date.nunique() < 12 or frame[contract.TARGET].nunique() < 2 for frame in trains.values()):
            skips.append(str(prediction_date.date()))
            continue
        for name, train in trains.items():
            if not (train.label_end <= prediction_date).all():
                raise RuntimeError("Future training label leaked")
            model = original.train_model(train, features)
            fits += 1
            scored = test[["eval_date", "product_vt_symbol", contract.FUTURE, contract.TARGET]].copy()
            scored["score"] = original.score_model(model, test, features)
            scored["arm"] = name
            predictions.append(scored)
            results.append({"arm": name, "eval_date": prediction_date,
                            **contract.month_metrics(scored), "train_rows": len(train),
                            "train_months": train.eval_date.nunique(),
                            "max_train_label_end": train.label_end.max()})
        if prediction_date.month in (6, 12):
            print(f"completed through {prediction_date.date()}, fits={fits}", flush=True)
    metrics = pd.DataFrame(results)
    metrics.to_csv(output / "monthly_metrics.csv", index=False)
    pd.concat(predictions, ignore_index=True).to_csv(output / "monthly_predictions.csv", index=False)
    aggregates = aggregate(metrics)
    metrics["year"] = metrics.eval_date.dt.year
    yearly = metrics.groupby(["year", "arm"]).agg(
        months=("eval_date", "nunique"), mean_rank_ic=("rank_ic", "mean"),
        mean_top_rank_lift=("top_rank_lift", "mean"), mean_auc=("auc", "mean")).reset_index()
    yearly.to_csv(output / "annual_metrics.csv", index=False)
    pivot = metrics.pivot(index="eval_date", columns="arm", values="rank_ic")
    intervals = {name: contract.paired_block_interval((pivot[name] - pivot["L0_legacy_purged"]).to_numpy())
                 for name in arms if name != "L0_legacy_purged"}
    asof = pd.Timestamp("2026-09-30")
    train_counts = {name: {"rows": len(contract.mature_training(frame, asof)),
                           "months": contract.mature_training(frame, asof).eval_date.nunique()}
                    for name, frame in arms.items()}
    scripts = [Path(__file__), Path(contract.__file__), Path(original.__file__),
               LINE / "stages/20261017_1710_stage262_ai_sample_contract_plan.md"]
    summary = {"generated_at": datetime.now().astimezone().isoformat(), "kind": "OFFLINE_LEGACY_SOURCE_MODEL_DIAGNOSTIC",
               "inputs": inputs, "scripts": [identity(path) for path in scripts],
               "study_git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                           "pandas": pd.__version__, "sklearn": sklearn.__version__},
               "source_provenance": provenance, "feature_columns": features, "feature_count": len(features),
               "fixed_model": {"C": .20, "solver": "lbfgs", "max_iter": 3000, "random_state": 42},
               "first_test": str(metrics.eval_date.min().date()), "last_test": str(metrics.eval_date.max().date()),
               "test_months": metrics.eval_date.nunique(), "actual_model_fits": fits, "skipped_months": skips,
               "nominal_legacy_rows": len(samples), "full_label_rows": len(l0), "eligible_rows": len(l1),
               "incomplete_tail_rows": int((~samples.label_complete).sum()),
               "coverage_or_warmup_removed": len(l0)-len(l1), "training_asof_2026_09_30": train_counts,
               "aggregates": aggregates.to_dict("records"), "paired_rank_ic_difference": intervals,
               "elapsed_seconds": round(time.perf_counter()-start, 3),
               "limits": ["Old account-dependent source; not current master/C9 labels or financial backtest",
                          "After-close label_end <= prediction_date; 60-source-day labels overlap",
                          "2025-2026 already inspected; retrospective diagnostics, no pristine holdout",
                          "Local mapping+source coverage is not exchange-certified historical listing/liquidity",
                          "No model/feature/threshold sweep; no pool publication, orders, or promotion"]}
    (output / "model_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "fits": fits, "test_months": summary["test_months"],
                      "aggregates": summary["aggregates"], "intervals": intervals,
                      "training_asof_2026_09_30": train_counts, "elapsed_seconds": summary["elapsed_seconds"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
