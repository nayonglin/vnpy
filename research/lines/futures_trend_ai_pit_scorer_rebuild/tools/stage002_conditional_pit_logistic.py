"""Run the frozen conditional-PIT logistic baseline."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import conditional_pit_logistic as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
BACKTEST_OUTPUTS = WORKSPACE_ROOT / "examples/portfolio_backtesting/backtest_outputs"
STAGE001_DIR = LINE_DIR / "artifacts/stage001_legacy_scorer_pit_audit"
OUTPUT_DIR = LINE_DIR / "artifacts/stage002_conditional_pit_logistic"

INPUT_PATHS: Final = {
    "legacy_samples": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_samples_product_suitability_wf_v1.csv",
    "legacy_windows": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_window_metrics_product_suitability_wf_v1.csv",
    "stage001_boundaries": STAGE001_DIR / "sample_label_boundary_audit.csv",
    "stage001_fold_audit": STAGE001_DIR / "fold_label_overlap_audit.csv",
    "stage001_listing_audit": STAGE001_DIR / "listing_eligibility_audit.csv",
    "stage001_universe": STAGE001_DIR / "universe_provenance_audit.json",
    "stage001_summary": STAGE001_DIR / "stage001_summary.json",
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "spec": LINE_DIR
    / "stages/20260902_1247_stage002_conditional_pit_logistic_preregistration.md",
    "model_core": LINE_DIR / "tools/conditional_pit_logistic.py",
    "audit_core": LINE_DIR / "tools/pit_scorer_audit.py",
}
EXPECTED_SHA256: Final = {
    "legacy_samples": "4cbc9952a1dac4373ac1901f958b914ac1d3495e56873c21cc6187548a60311d",
    "legacy_windows": "869d634e1e56b99cac6f28cf4e0108942c104648b4cedd91fc8ee9961fee0da3",
    "stage001_boundaries": "5c3a5d5484869b126face7bd9ed24ae4cc6d0f2e5d3ee75d5d6f8604552cda87",
    "stage001_fold_audit": "0632a9b33dd86660a34ca8f838888a19794271344cf3e1f64df3a1317893a470",
    "stage001_listing_audit": "e968fefc17954239d7acf92b5800489536b3f32610b481fd5a51b17b30102823",
    "stage001_universe": "cb4de4e24af6264da503f39723bc358bfbff5e3c0990db6c77aecbd1aa03e2c1",
    "stage001_summary": "9a95f0ea82236a311dd140652ec21cb75160f92f39050b8197a7d817d67da688",
    "stage001_manifest": "b5bb746c72d9dd4105ecfcc41cb213084fc3d3e317e39d32eae8088f15b29ca9",
    "spec": "da3084e49944143be4eea30ba04e464b2e567864c7e3a2c2aae4ea61a0b2849c",
    "model_core": "e01b2f17c4c0425b170d4d234be7caac15ae58883db7a20229d505cd1c950510",
    "audit_core": "eb4d2b83fdc460448c9c889a3a6265300ea11ff13ed1e837c7301e88c63d7570",
}


class Stage002Error(RuntimeError):
    """Raised when the frozen Stage002 run must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inputs(
    input_paths: Mapping[str, Path],
    expected_sha256: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage002Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage002Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != expected_sha256[name]:
            raise Stage002Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def build_technical_gates(summary: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "input_identity_stable": bool(summary["input_identity_stable"]),
        "feature_count_exact": int(summary["feature_count"]) == 108,
        "valid_folds_ge_7": int(summary["valid_fold_count"]) >= 7,
        "oos_months_ge_40": int(summary["oos_months"]) >= 40,
        "pit_violation_rows_zero": int(summary["pit_violation_rows"]) == 0,
        "unlisted_rows_zero": int(summary["oos_unlisted_rows"]) == 0,
        "partial_horizon_rows_zero": int(summary["oos_partial_horizon_rows"]) == 0,
        "deterministic_predictions": float(
            summary["repeat_prediction_max_abs_diff"]
        )
        <= 1e-12,
        "deterministic_model_state": float(
            summary["repeat_model_state_max_abs_diff"]
        )
        <= 1e-12,
        "probabilities_valid": bool(summary["probabilities_valid"]),
        "monthly_candidate_count_ge_10": int(
            summary["minimum_monthly_candidate_count"]
        )
        >= 10,
        "sealed_holdout_rows_zero": int(summary["sealed_holdout_rows_read"]) == 0,
    }


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        float_format="%.17g",
        lineterminator="\n",
    )


def publish_artifacts(
    output_dir: Path,
    *,
    conditional_samples: pd.DataFrame,
    fold_audit: pd.DataFrame,
    predictions: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
    model_parameters: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage002Error("output_already_exists")
    if temp_dir.exists():
        raise Stage002Error("temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)

    _write_csv(conditional_samples, temp_dir / "conditional_pit_samples.csv")
    _write_csv(fold_audit, temp_dir / "fold_audit.csv")
    _write_csv(predictions, temp_dir / "oos_predictions.csv")
    _write_csv(monthly_metrics, temp_dir / "monthly_metrics.csv")
    _write_csv(model_parameters, temp_dir / "model_parameters.csv")
    (temp_dir / "stage002_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = summary.get("prediction_metrics", {})
    report = (
        "# Stage002 条件PIT逻辑回归基线\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 条件样本：`{summary['conditional_rows']}`行；有效fold："
        f"`{summary['valid_fold_count']}`；OOS月份：`{summary['oos_months']}`。\n"
        f"- PIT违规：`{summary['pit_violation_rows']}`；未上市/非完整标签："
        f"`{summary['oos_unlisted_rows']}/{summary['oos_partial_horizon_rows']}`。\n"
        f"- AUC：`{metrics.get('roc_auc', float('nan')):.6f}`；"
        f"月均Rank IC：`{metrics.get('mean_monthly_rank_ic', float('nan')):.6f}`。\n"
        "- 指标是产品贡献代理，不是策略收益或回撤；本阶段回测0、CTP/订单0。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "conditional_pit_samples.csv",
        "fold_audit.csv",
        "oos_predictions.csv",
        "monthly_metrics.csv",
        "model_parameters.csv",
        "stage002_summary.json",
        "report.md",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def _component_diffs(first: Pipeline, second: Pipeline) -> tuple[float, float]:
    first_scaler: StandardScaler = first.named_steps["scaler"]
    second_scaler: StandardScaler = second.named_steps["scaler"]
    first_classifier: LogisticRegression = first.named_steps["classifier"]
    second_classifier: LogisticRegression = second.named_steps["classifier"]
    scaler_left = np.concatenate([first_scaler.mean_, first_scaler.scale_])
    scaler_right = np.concatenate([second_scaler.mean_, second_scaler.scale_])
    model_left = np.concatenate(
        [first_classifier.coef_.ravel(), first_classifier.intercept_.ravel()]
    )
    model_right = np.concatenate(
        [second_classifier.coef_.ravel(), second_classifier.intercept_.ravel()]
    )
    return (
        float(np.max(np.abs(scaler_left - scaler_right))),
        float(np.max(np.abs(model_left - model_right))),
    )


def run_stage002(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage002Error("output_already_exists")
    before = verify_inputs(input_paths, expected_sha256)
    samples = pd.read_csv(input_paths["legacy_samples"])
    windows = pd.read_csv(input_paths["legacy_windows"])
    boundaries = pd.read_csv(input_paths["stage001_boundaries"])
    universe = json.loads(Path(input_paths["stage001_universe"]).read_text(encoding="utf-8"))
    effective = {
        product: pd.Timestamp(value)
        for product, value in universe["effective_listing_dates"].items()
    }
    conditional, sample_audit = core.build_conditional_samples(
        samples, boundaries, effective
    )
    features = core.discover_feature_columns(conditional)
    folds, fold_audit = core.build_fold_contracts(conditional, windows)
    if not folds:
        raise Stage002Error("no_valid_folds")

    predictions: list[pd.DataFrame] = []
    parameter_frames: list[pd.DataFrame] = []
    prediction_diffs: list[float] = []
    model_state_diffs: list[float] = []
    scaler_diffs: list[float] = []
    coefficient_diffs: list[float] = []
    for fold in folds:
        train = conditional[conditional[core.DATE_COLUMN].isin(fold.train_dates)].copy()
        test = conditional[conditional[core.DATE_COLUMN].isin(fold.test_dates)].copy()
        first = core.fit_logistic(train, features)
        second = core.fit_logistic(train, features)
        first_probability = core.predict_probability(first, test, features)
        second_probability = core.predict_probability(second, test, features)
        prediction_diff = float(np.max(np.abs(first_probability - second_probability)))
        state_diff = core.model_state_max_abs_diff(first, second)
        scaler_diff, coefficient_diff = _component_diffs(first, second)
        prediction_diffs.append(prediction_diff)
        model_state_diffs.append(state_diff)
        scaler_diffs.append(scaler_diff)
        coefficient_diffs.append(coefficient_diff)

        test[core.PROBABILITY_COLUMN] = first_probability
        test["window_id"] = fold.window_id
        test["train_start"] = fold.train_start
        test["train_end"] = fold.train_end
        test["test_start"] = fold.test_start
        test["test_end"] = fold.test_end
        predictions.append(test)
        parameter_frames.append(
            core.model_parameter_rows(first, features, window_id=fold.window_id)
        )
        mask = fold_audit["window_id"].eq(fold.window_id)
        fold_audit.loc[mask, "repeat_prediction_max_abs_diff"] = prediction_diff
        fold_audit.loc[mask, "repeat_model_state_max_abs_diff"] = state_diff
        fold_audit.loc[mask, "repeat_scaler_max_abs_diff"] = scaler_diff
        fold_audit.loc[mask, "repeat_coefficient_max_abs_diff"] = coefficient_diff

    prediction_frame = pd.concat(predictions, ignore_index=True)
    prediction_frame.sort_values(
        [core.DATE_COLUMN, core.PRODUCT_COLUMN], inplace=True, kind="mergesort"
    )
    prediction_frame.reset_index(drop=True, inplace=True)
    if prediction_frame.duplicated([core.DATE_COLUMN, core.PRODUCT_COLUMN]).any():
        raise Stage002Error("oos_prediction_key_duplicate")
    parameter_frame = pd.concat(parameter_frames, ignore_index=True)
    monthly = core.build_monthly_metrics(prediction_frame)
    metrics = core.prediction_metrics(prediction_frame, monthly)

    after = verify_inputs(input_paths, expected_sha256)
    input_stable = before == after
    probability = prediction_frame[core.PROBABILITY_COLUMN].to_numpy(dtype="float64")
    preliminary: dict[str, Any] = {
        "input_identity_stable": input_stable,
        "feature_count": int(len(features)),
        "valid_fold_count": int(len(folds)),
        "oos_months": int(prediction_frame[core.DATE_COLUMN].nunique()),
        "pit_violation_rows": int(
            fold_audit.loc[fold_audit["accepted"].astype(bool), "pit_violation_rows"].sum()
        ),
        "oos_unlisted_rows": int(
            (~prediction_frame["pit_listing_eligible"].astype(bool)).sum()
        ),
        "oos_partial_horizon_rows": int(
            (~prediction_frame["full_horizon_label"].astype(bool)).sum()
        ),
        "repeat_prediction_max_abs_diff": max(prediction_diffs),
        "repeat_model_state_max_abs_diff": max(model_state_diffs),
        "repeat_scaler_max_abs_diff": max(scaler_diffs),
        "repeat_coefficient_max_abs_diff": max(coefficient_diffs),
        "probabilities_valid": bool(
            np.isfinite(probability).all()
            and (probability >= 0.0).all()
            and (probability <= 1.0).all()
        ),
        "minimum_monthly_candidate_count": int(monthly["candidate_count"].min()),
        "sealed_holdout_rows_read": 0,
    }
    gates = build_technical_gates(preliminary)
    decision = core.stage002_decision(gates)
    summary: dict[str, Any] = {
        "line_id": "futures_trend_ai_pit_scorer_rebuild",
        "stage": "Stage002",
        "decision": decision,
        "all_technical_gates_passed": bool(all(gates.values())),
        "gates": gates,
        **preliminary,
        **sample_audit,
        "feature_columns": features,
        "rejected_fold_count": int((~fold_audit["accepted"].astype(bool)).sum()),
        "rejected_folds": fold_audit.loc[
            ~fold_audit["accepted"].astype(bool), ["window_id", "reject_reason"]
        ].to_dict(orient="records"),
        "oos_rows": int(len(prediction_frame)),
        "oos_products": int(prediction_frame[core.PRODUCT_COLUMN].nunique()),
        "prediction_metrics": metrics,
        "evidence_scope": "fixed_current_design_universe_only",
        "historical_asof_universe_reconstructable": False,
        "model_configuration": {
            "pipeline": "StandardScaler+LogisticRegression",
            "C": core.LOGISTIC_C,
            "solver": "lbfgs",
            "max_iter": 3000,
            "random_state": core.RANDOM_STATE,
        },
        "inputs_before": before,
        "inputs_after": after,
        "model_training_runs": int(2 * len(folds)),
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    publish_artifacts(
        output_dir,
        conditional_samples=conditional,
        fold_audit=fold_audit,
        predictions=prediction_frame,
        monthly_metrics=monthly,
        model_parameters=parameter_frame,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage002(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

