"""Rerun the conditional-PIT logistic baseline with a raw-only feature contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import numpy as np
import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import conditional_pit_logistic as core  # noqa: E402
import stage002_conditional_pit_logistic as stage002  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
BACKTEST_OUTPUTS = WORKSPACE_ROOT / "examples/portfolio_backtesting/backtest_outputs"
STAGE001_DIR = LINE_DIR / "artifacts/stage001_legacy_scorer_pit_audit"
STAGE002_DIR = LINE_DIR / "artifacts/stage002_conditional_pit_logistic"
OUTPUT_DIR = LINE_DIR / "artifacts/stage003_feature_contract_fix"

INPUT_PATHS: Final = {
    "legacy_samples": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_samples_product_suitability_wf_v1.csv",
    "legacy_windows": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_window_metrics_product_suitability_wf_v1.csv",
    "stage001_boundaries": STAGE001_DIR / "sample_label_boundary_audit.csv",
    "stage001_universe": STAGE001_DIR / "universe_provenance_audit.json",
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "stage002_failed_summary": STAGE002_DIR / "stage002_summary.json",
    "stage002_failed_manifest": STAGE002_DIR / "artifact_manifest.json",
    "spec": LINE_DIR
    / "stages/20260902_1254_stage003_feature_contract_fix_preregistration.md",
    "model_core": LINE_DIR / "tools/conditional_pit_logistic.py",
    "audit_core": LINE_DIR / "tools/pit_scorer_audit.py",
}
EXPECTED_SHA256: Final = {
    "legacy_samples": "4cbc9952a1dac4373ac1901f958b914ac1d3495e56873c21cc6187548a60311d",
    "legacy_windows": "869d634e1e56b99cac6f28cf4e0108942c104648b4cedd91fc8ee9961fee0da3",
    "stage001_boundaries": "5c3a5d5484869b126face7bd9ed24ae4cc6d0f2e5d3ee75d5d6f8604552cda87",
    "stage001_universe": "cb4de4e24af6264da503f39723bc358bfbff5e3c0990db6c77aecbd1aa03e2c1",
    "stage001_manifest": "b5bb746c72d9dd4105ecfcc41cb213084fc3d3e317e39d32eae8088f15b29ca9",
    "stage002_failed_summary": "2be847d9b0df073d5492656d2a134ac8a03e3828f7f0478d262bc901151b3411",
    "stage002_failed_manifest": "20ccebe644f955015326faefa1fa572fcefa8bdded039a2ad983d29e8aa50589",
    "spec": "71749515f326804a4d0b10e51556039b0c53420eafec9af285ec5e270a3ba833",
    "model_core": "ccccf8254655bf76b837d14db1af63a33b1d0a9fbc08261b1b677a2d1c8b510d",
    "audit_core": "eb4d2b83fdc460448c9c889a3a6265300ea11ff13ed1e837c7301e88c63d7570",
}

PASS_DECISION = "stage003_feature_contract_fix_pass_allow_frozen_xgboost_design"
FAIL_DECISION = "stage003_feature_contract_fix_fail_stop_no_xgboost"
FORBIDDEN_PREFIXES = (
    "future_",
    "target_",
    "sample_weight_",
    "pit_future_",
    "pit_target_",
)


class Stage003Error(RuntimeError):
    """Raised when the frozen Stage003 rerun must fail closed."""


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
        raise Stage003Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage003Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != expected_sha256[name]:
            raise Stage003Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def freeze_raw_feature_contract(
    raw_samples: pd.DataFrame,
    conditional_samples: pd.DataFrame,
    *,
    expected_count: int = 108,
) -> list[str]:
    features = core.discover_feature_columns(raw_samples)
    if len(features) != expected_count:
        raise Stage003Error(f"raw_feature_count:{len(features)}")
    missing = sorted(set(features) - set(conditional_samples.columns))
    if missing:
        raise Stage003Error(f"conditional_feature_missing:{','.join(missing)}")
    forbidden = [column for column in features if column.startswith(FORBIDDEN_PREFIXES)]
    if forbidden:
        raise Stage003Error(f"forbidden_features:{','.join(forbidden)}")
    return features


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
        raise Stage003Error("output_already_exists")
    if temp_dir.exists():
        raise Stage003Error("temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(conditional_samples, temp_dir / "conditional_pit_samples.csv")
    _write_csv(fold_audit, temp_dir / "fold_audit.csv")
    _write_csv(predictions, temp_dir / "oos_predictions.csv")
    _write_csv(monthly_metrics, temp_dir / "monthly_metrics.csv")
    _write_csv(model_parameters, temp_dir / "model_parameters.csv")
    (temp_dir / "stage003_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = summary["prediction_metrics"]
    report = (
        "# Stage003 条件PIT逻辑回归特征合同修复\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 原始冻结特征：`{summary['feature_count']}`；非法标签特征："
        f"`{summary['forbidden_feature_count']}`。\n"
        f"- 有效fold/OOS月：`{summary['valid_fold_count']}/{summary['oos_months']}`；"
        f"PIT违规：`{summary['pit_violation_rows']}`。\n"
        f"- AUC：`{metrics['roc_auc']:.6f}`；月均Rank IC："
        f"`{metrics['mean_monthly_rank_ic']:.6f}`。\n"
        "- 以上是产品贡献代理，不是策略收益或回撤；回测0、CTP/订单0。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "conditional_pit_samples.csv",
        "fold_audit.csv",
        "oos_predictions.csv",
        "monthly_metrics.csv",
        "model_parameters.csv",
        "stage003_summary.json",
        "report.md",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage003(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage003Error("output_already_exists")
    before = verify_inputs(input_paths, expected_sha256)
    raw_samples = pd.read_csv(input_paths["legacy_samples"])
    windows = pd.read_csv(input_paths["legacy_windows"])
    boundaries = pd.read_csv(input_paths["stage001_boundaries"])
    universe = json.loads(Path(input_paths["stage001_universe"]).read_text(encoding="utf-8"))
    effective = {
        product: pd.Timestamp(value)
        for product, value in universe["effective_listing_dates"].items()
    }
    conditional, sample_audit = core.build_conditional_samples(
        raw_samples, boundaries, effective
    )
    features = freeze_raw_feature_contract(raw_samples, conditional)
    folds, fold_audit = core.build_fold_contracts(conditional, windows)
    if not folds:
        raise Stage003Error("no_valid_folds")

    predictions: list[pd.DataFrame] = []
    parameters: list[pd.DataFrame] = []
    prediction_diffs: list[float] = []
    state_diffs: list[float] = []
    scaler_diffs: list[float] = []
    coefficient_diffs: list[float] = []
    for fold in folds:
        train = conditional[conditional[core.DATE_COLUMN].isin(fold.train_dates)].copy()
        test = conditional[conditional[core.DATE_COLUMN].isin(fold.test_dates)].copy()
        first = core.fit_logistic(train, features)
        second = core.fit_logistic(train, features)
        p1 = core.predict_probability(first, test, features)
        p2 = core.predict_probability(second, test, features)
        prediction_diff = float(np.max(np.abs(p1 - p2)))
        state_diff = core.model_state_max_abs_diff(first, second)
        scaler_diff, coefficient_diff = stage002._component_diffs(first, second)
        prediction_diffs.append(prediction_diff)
        state_diffs.append(state_diff)
        scaler_diffs.append(scaler_diff)
        coefficient_diffs.append(coefficient_diff)
        test[core.PROBABILITY_COLUMN] = p1
        test["window_id"] = fold.window_id
        test["train_start"] = fold.train_start
        test["train_end"] = fold.train_end
        test["test_start"] = fold.test_start
        test["test_end"] = fold.test_end
        predictions.append(test)
        parameters.append(
            core.model_parameter_rows(first, features, window_id=fold.window_id)
        )
        mask = fold_audit["window_id"].eq(fold.window_id)
        fold_audit.loc[mask, "repeat_prediction_max_abs_diff"] = prediction_diff
        fold_audit.loc[mask, "repeat_model_state_max_abs_diff"] = state_diff
        fold_audit.loc[mask, "repeat_scaler_max_abs_diff"] = scaler_diff
        fold_audit.loc[mask, "repeat_coefficient_max_abs_diff"] = coefficient_diff

    prediction_frame = pd.concat(predictions, ignore_index=True).sort_values(
        [core.DATE_COLUMN, core.PRODUCT_COLUMN], kind="mergesort"
    ).reset_index(drop=True)
    if prediction_frame.duplicated([core.DATE_COLUMN, core.PRODUCT_COLUMN]).any():
        raise Stage003Error("oos_prediction_key_duplicate")
    parameter_frame = pd.concat(parameters, ignore_index=True)
    monthly = core.build_monthly_metrics(prediction_frame)
    metrics = core.prediction_metrics(prediction_frame, monthly)
    after = verify_inputs(input_paths, expected_sha256)

    probability = prediction_frame[core.PROBABILITY_COLUMN].to_numpy(dtype="float64")
    forbidden = [column for column in features if column.startswith(FORBIDDEN_PREFIXES)]
    preliminary: dict[str, Any] = {
        "input_identity_stable": before == after,
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
        "repeat_model_state_max_abs_diff": max(state_diffs),
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
    gates = stage002.build_technical_gates(preliminary)
    gates["raw_feature_contract_exact"] = len(features) == 108
    gates["forbidden_feature_count_zero"] = len(forbidden) == 0
    decision = PASS_DECISION if all(gates.values()) else FAIL_DECISION
    summary: dict[str, Any] = {
        "line_id": "futures_trend_ai_pit_scorer_rebuild",
        "stage": "Stage003",
        "decision": decision,
        "all_technical_gates_passed": bool(all(gates.values())),
        "gates": gates,
        **preliminary,
        **sample_audit,
        "feature_columns": features,
        "forbidden_features": forbidden,
        "forbidden_feature_count": int(len(forbidden)),
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
    print(json.dumps(run_stage003(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

