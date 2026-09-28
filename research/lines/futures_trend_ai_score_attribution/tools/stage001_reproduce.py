"""Reproduce the frozen July 2026 AI scores without updating any live material."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.special import expit


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage001_20260731"
PRODUCTION = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
CODE = PRODUCTION / "examples/portfolio_backtesting"
MATERIALS = PRODUCTION / "official_strategy_materials"
FORMAL = MATERIALS / "ai_top10_plus_fu_official_live_v1/releases/m0004_20260831T112631+0800_2485073e9594"
ORIGINAL = MATERIALS / "official_live_stage847_c9_15w_stage819_05r_stop_retry_once/releases/m0015_20260825T205121+0800_c097d7836dd4"
PROB = "predicted_product_suitability_probability"
TOL = 1e-10


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def identity(path: Path) -> dict:
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return {"path": str(path), "size": after.st_size, "sha256": h.hexdigest()}


def save_json(name: str, value: dict) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    current_path = MATERIALS / "CURRENT.json"
    current = read_json(current_path)
    assert current["release_id"] == FORMAL.name, "active material changed; do not silently move the target"
    summary_path = ORIGINAL / "payload/ai/stage182/summary.json"
    metadata = read_json(summary_path)
    official_path = FORMAL / "payload/ai/stage182/latest_pool.csv"
    original_pool_path = ORIGINAL / "payload/ai/stage182/latest_pool.csv"
    paths = [current_path, summary_path, official_path, original_pool_path]
    paths += [Path(metadata["source_paths"][key]) for key in ("position_changes", "entry_candidate_snapshots")]
    names = ["analyze_qmt_roll_ai_product_suitability_walkforward.py", "qmt_universe.py"]
    paths += [CODE / name for name in names]
    paths += [CODE / "build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py", Path(__file__).resolve()]
    before = {str(path): identity(path) for path in paths}
    for key in ("position_changes", "entry_candidate_snapshots"):
        path = metadata["source_paths"][key]
        assert before[path]["sha256"] == metadata["source_identities"][key]["sha256"], key
        assert before[path]["size"] == metadata["source_identities"][key]["size"], key
    for name in names:
        frozen = ORIGINAL / "payload/examples/portfolio_backtesting" / name
        if frozen.exists():
            assert identity(frozen)["sha256"] == before[str(CODE / name)]["sha256"], name
        else:
            old_code = subprocess.check_output(
                ["git", "show", f"c097d7836dd4:examples/portfolio_backtesting/{name}"], cwd=PRODUCTION
            )
            assert hashlib.sha256(old_code).hexdigest() == before[str(CODE / name)]["sha256"], name

    sys.path[:0] = [str(CODE), str(PRODUCTION)]
    import analyze_qmt_roll_ai_product_suitability_walkforward as model_code
    import build_qmt_roll_stage182_ai_product_pool_live_inference_runner as runner

    model_code.POSITION_CHANGES_PATH = Path(metadata["source_paths"]["position_changes"])
    model_code.ENTRY_SNAPSHOTS_PATH = Path(metadata["source_paths"]["entry_candidate_snapshots"])
    print("Input and code identities match; building the original features.", flush=True)
    daily = model_code.build_product_daily()
    assert pd.Timestamp(daily.date.max()).date().isoformat() == metadata["source_max_date"]
    featured = model_code.add_rolling_features(daily)
    samples, features = model_code.build_monthly_samples(featured)
    eval_date = pd.Timestamp(metadata["eval_date"])
    cutoff = runner._training_label_cutoff(daily.date, eval_date)
    assert cutoff.date().isoformat() == metadata["training_label_cutoff"]
    train = samples[pd.to_datetime(samples.eval_date).dt.normalize() <= cutoff].copy()
    assert len(train) == metadata["train_rows"]
    assert train.eval_date.nunique() == metadata["train_months"]
    assert len(features) == metadata["feature_count"]
    live = runner._build_live_feature_rows(featured, eval_date)
    print(f"Fitting original parameters: {len(train)} samples, {len(features)} features, {len(live)} products.", flush=True)
    model = model_code.train_model(train, features)
    live[PROB] = model_code.score_model(model, live, features)
    live = live.sort_values([PROB, model_code.SIMPLE_SCORE_COLUMN, "product_vt_symbol"], ascending=[False, False, True])
    live["model_rank"] = np.arange(1, len(live) + 1)
    reference = pd.read_csv(original_pool_path, float_precision="round_trip")
    official = pd.read_csv(official_path, float_precision="round_trip")
    assert live.product_vt_symbol.is_unique and reference.product_vt_symbol.is_unique
    assert set(live.product_vt_symbol) == set(reference.product_vt_symbol)
    comparison = live[["product_vt_symbol", "model_rank", PROB]].merge(
        reference[["product_vt_symbol", "ai_rank", PROB]], on="product_vt_symbol", validate="one_to_one", suffixes=("_reproduced", "_original")
    )
    comparison["abs_probability_error"] = (comparison[PROB + "_reproduced"] - comparison[PROB + "_original"]).abs()
    original_error = float(comparison.abs_probability_error.max())
    assert original_error <= TOL, f"original probability error: {original_error}"
    assert (comparison.model_rank == comparison.ai_rank).all(), "original rank mismatch"
    non_fixed = official[official.selection_role.eq("model_ranked")].sort_values("ai_rank")
    selected = live[~live.product_vt_symbol.eq("fu.SHFE")].head(10)
    assert selected.product_vt_symbol.tolist() == non_fixed.product_vt_symbol.tolist(), "formal Top10 mismatch"
    formal_error = float(np.max(np.abs(selected[PROB].to_numpy() - non_fixed[PROB].to_numpy())))
    assert formal_error <= TOL, f"formal probability error: {formal_error}"
    feature_parity = live.set_index("product_vt_symbol")[features] - reference.set_index("product_vt_symbol")[features]
    assert np.max(np.abs(feature_parity.to_numpy())) <= TOL, "saved feature row mismatch"
    fixed = official[official.selection_role.eq("fixed_fu")]
    assert fixed.product_vt_symbol.tolist() == ["fu.SHFE"]
    assert abs(float(fixed[PROB].iloc[0]) - (float(non_fixed[PROB].min()) - 1e-6)) <= TOL

    scaler = model.named_steps["scaler"]
    classifier = model.named_steps["classifier"]
    x = model_code.prepare_x(live, features)
    z = scaler.transform(x)
    coefficients = classifier.coef_[0]
    intercept = float(classifier.intercept_[0])
    contributions = z * coefficients
    logits = intercept + contributions.sum(axis=1)
    logits_error = float(np.max(np.abs(logits - model.decision_function(x))))
    reconstructed_error = float(np.max(np.abs(expit(logits) - live[PROB].to_numpy())))
    assert logits_error <= 1e-12 and reconstructed_error <= 1e-12
    assert np.isfinite(contributions).all()
    feature_frame = pd.DataFrame({
        "feature": features, "coefficient": coefficients,
        "training_mean": scaler.mean_, "training_scale": scaler.scale_,
        "training_variance": scaler.var_,
        "current_mean_abs_contribution": np.abs(contributions).mean(axis=0),
        "current_cross_product_std_contribution": contributions.std(axis=0),
    })
    records = []
    official_ranks = dict(zip(official.product_vt_symbol, official.ai_rank))
    for i, row in enumerate(live.itertuples(index=False)):
        for j, feature in enumerate(features):
            records.append({
                "product_vt_symbol": row.product_vt_symbol,
                "model_rank": int(row.model_rank),
                "official_rank": official_ranks.get(row.product_vt_symbol),
                "feature": feature,
                "raw_value": float(x.iloc[i, j]),
                "training_mean": float(scaler.mean_[j]),
                "training_scale": float(scaler.scale_[j]),
                "standardized_value": float(z[i, j]),
                "coefficient": float(coefficients[j]),
                "contribution_log_odds": float(contributions[i, j]),
            })
    detail = pd.DataFrame(records)
    live["official_rank"] = live.product_vt_symbol.map(official_ranks)
    live["intercept_log_odds"] = intercept
    live["contribution_sum_log_odds"] = contributions.sum(axis=1)
    live["decision_log_odds"] = logits
    live["positive_contribution_sum"] = np.maximum(contributions, 0).sum(axis=1)
    live["negative_contribution_sum"] = np.minimum(contributions, 0).sum(axis=1)
    before_after_match = all(identity(path) == before[str(path)] for path in paths)
    assert before_after_match, "source or active release changed during reproduction"
    comparison.to_csv(OUT / "score_parity.csv", index=False)
    feature_frame.to_csv(OUT / "model_coefficients.csv", index=False)
    detail.to_csv(OUT / "feature_contributions.csv", index=False)
    live.to_csv(OUT / "product_scores_and_features.csv", index=False)
    train[["eval_date", "product_vt_symbol", model_code.TARGET_COLUMN, model_code.WEIGHT_COLUMN] + features].to_csv(OUT / "training_samples.csv", index=False)
    official.to_csv(OUT / "formal_pool_snapshot.csv", index=False)
    save_json("model_snapshot.json", {
        "features": features, "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "coefficients": coefficients.tolist(), "intercept": intercept, "classes": classifier.classes_.tolist(),
        "parameters": classifier.get_params(), "iterations": classifier.n_iter_.tolist(),
        "baseline_probability_at_training_mean": float(expit(intercept)),
    })
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": "exact_current_score_reproduction_pass",
        "eval_date": metadata["eval_date"], "source_max_date": metadata["source_max_date"],
        "training_label_cutoff": metadata["training_label_cutoff"],
        "training_start": str(train.eval_date.min().date()), "training_end": str(train.eval_date.max().date()),
        "train_rows": len(train), "train_months": int(train.eval_date.nunique()), "feature_count": len(features),
        "model_product_count": len(live), "formal_non_fixed_count": len(non_fixed),
        "source_identities": before, "source_unchanged": before_after_match,
        "production_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCTION, text=True).strip(),
        "formal_release_id": current["release_id"],
        "original_metadata": metadata,
        "versions": {"python": sys.version, "sklearn": sklearn.__version__, "numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__},
        "checks": {"original_max_probability_error": original_error, "formal_max_probability_error": formal_error,
                   "logit_max_error": logits_error, "reconstructed_probability_max_error": reconstructed_error,
                   "feature_max_abs_error": float(np.max(np.abs(feature_parity.to_numpy()))),
                   "all_18_ranks_match": True, "formal_top10_order_matches": True,
                   "fu_placeholder_not_model_probability": True},
        "attribution": {"baseline": "unweighted training feature means used by StandardScaler",
                        "formula": "coefficient * ((feature - training_mean) / training_scale)",
                        "units": "log_odds", "causal": False, "probability_contributions_additive": False},
        "safety": {"runs_backtest": False, "order_api_called_count": 0, "ctp_connected": False, "production_files_written": False, "original_parameters_changed": False},
        "references": ["https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html",
                       "https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_logistic.py"],
    }
    save_json("reproduction_summary.json", manifest)
    print(json.dumps({key: manifest[key] for key in ("decision", "feature_count", "train_rows", "train_months", "checks")}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
