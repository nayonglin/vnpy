"""Run the frozen conditional-PIT XGBoost and LR rank-fusion qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import numpy as np
import pandas as pd
import sklearn
import xgboost


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import conditional_pit_logistic as logistic_core  # noqa: E402
import frozen_xgboost_fusion as fusion_core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
BACKTEST_OUTPUTS = WORKSPACE_ROOT / "examples/portfolio_backtesting/backtest_outputs"
STAGE003_DIR = LINE_DIR / "artifacts/stage003_feature_contract_fix"
OUTPUT_DIR = LINE_DIR / "artifacts/stage004_frozen_xgboost_fusion"

INPUT_PATHS: Final = {
    "conditional_samples": STAGE003_DIR / "conditional_pit_samples.csv",
    "fold_audit": STAGE003_DIR / "fold_audit.csv",
    "lr_oos_predictions": STAGE003_DIR / "oos_predictions.csv",
    "stage003_summary": STAGE003_DIR / "stage003_summary.json",
    "stage003_manifest": STAGE003_DIR / "artifact_manifest.json",
    "legacy_daily": BACKTEST_OUTPUTS
    / "qmt_roll_ai_product_suitability_walkforward_daily_product_suitability_wf_v1.csv",
    "spec": LINE_DIR
    / "stages/20260902_1259_stage004_frozen_xgboost_fusion_preregistration.md",
    "fusion_core": LINE_DIR / "tools/frozen_xgboost_fusion.py",
    "logistic_core": LINE_DIR / "tools/conditional_pit_logistic.py",
}
EXPECTED_SHA256: Final = {
    "conditional_samples": "22fc20b184f1f0e283d0bc2041a37d9bc778646c6fcaad662235c87f2e216cfc",
    "fold_audit": "92082f0791376e3b1df337e4b07a4bc7cb1ef0e0fd3c1672141e809e3e773c69",
    "lr_oos_predictions": "9ec713fd03d9f1131b22b5378a4b8feb9b1065660052cbeb427ab327b51ccce3",
    "stage003_summary": "ea9766e9a2fa1856d1e178754350f7a805825dfb94ccb4c5758cced91d8cef83",
    "stage003_manifest": "30ab79bd2373d0ad9c9e15ea1b0d013f657cd38b3474299146bb4b4140e40c59",
    "legacy_daily": "9af514a3a5ab7ca4d982a31bd758522c32c4dec792f1b1819abb5462a391efcd",
    "spec": "766bcbe5da09f654a3d6cfebf8bb29e16786cf95708af365eceed8e877a7d920",
    "fusion_core": "94961cb8caf8e8b979ed5d8599d970fbcc1586e242f9b43d337a9a47afd3320c",
    "logistic_core": "ccccf8254655bf76b837d14db1af63a33b1d0a9fbc08261b1b677a2d1c8b510d",
}

PASS_DECISION = (
    "stage004_xgboost_fusion_prediction_pass_allow_candidate_ranking_design"
)
FAIL_DECISION = "stage004_xgboost_fusion_prediction_fail_stop_feature_label_family"


class Stage004Error(RuntimeError):
    """Raised when the frozen Stage004 qualification must fail closed."""


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
        raise Stage004Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage004Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != expected_sha256[name]:
            raise Stage004Error(f"input_sha256_drift:{name}")
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
        "valid_fold_count_exact": int(summary["valid_fold_count"]) == 8,
        "oos_month_count_exact": int(summary["oos_months"]) == 47,
        "pit_violation_rows_zero": int(summary["pit_violation_rows"]) == 0,
        "stage003_a_prediction_exact": float(summary["a_prediction_max_abs_diff"])
        <= 1e-12,
        "xgb_repeat_prediction_exact": float(
            summary["xgb_repeat_prediction_max_abs_diff"]
        )
        <= 1e-12,
        "xgb_repeat_dump_sha_match": bool(summary["xgb_repeat_dump_sha_match"]),
        "xgb_probabilities_valid": bool(summary["xgb_probabilities_valid"]),
        "monthly_arm_rows_exact": int(summary["monthly_arm_rows"])
        == int(summary["oos_months"]) * 3,
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
    predictions: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
    fold_audit: pd.DataFrame,
    model_dump_audit: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage004Error("output_already_exists")
    if temp_dir.exists():
        raise Stage004Error("temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(predictions, temp_dir / "oos_predictions.csv")
    _write_csv(monthly_metrics, temp_dir / "monthly_arm_metrics.csv")
    _write_csv(fold_audit, temp_dir / "fold_audit.csv")
    _write_csv(model_dump_audit, temp_dir / "model_dump_audit.csv")
    (temp_dir / "stage004_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    arms = summary.get("arms", {})
    a = arms.get("A_logistic", {})
    c = arms.get("C_fusion", {})
    report = (
        "# Stage004 条件PIT冻结XGBoost融合\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 技术门：`{sum(summary['technical_gates'].values())}/"
        f"{len(summary['technical_gates'])}`；C效果门："
        f"`{sum(summary['effect_gates'].values())}/{len(summary['effect_gates'])}`。\n"
        f"- A/C月均未来净利润代理：`{a.get('top10_mean_future_pnl', float('nan')):.2f}/"
        f"{c.get('top10_mean_future_pnl', float('nan')):.2f}`。\n"
        f"- A/C月均路径回撤代理：`{a.get('mean_path_drawdown', float('nan')):.2f}/"
        f"{c.get('mean_path_drawdown', float('nan')):.2f}`。\n"
        "- 本阶段不是策略回测，不产生期末权益、组合收益率或真实最大回撤。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "oos_predictions.csv",
        "monthly_arm_metrics.csv",
        "fold_audit.csv",
        "model_dump_audit.csv",
        "stage004_summary.json",
        "report.md",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage004(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise Stage004Error("output_already_exists")
    before = verify_inputs(input_paths, expected_sha256)
    panel = pd.read_csv(input_paths["conditional_samples"])
    windows = pd.read_csv(input_paths["fold_audit"])
    frozen_a = pd.read_csv(
        input_paths["lr_oos_predictions"],
        usecols=[
            logistic_core.DATE_COLUMN,
            logistic_core.PRODUCT_COLUMN,
            logistic_core.PROBABILITY_COLUMN,
        ],
    )
    stage003_summary = json.loads(
        Path(input_paths["stage003_summary"]).read_text(encoding="utf-8")
    )
    daily = pd.read_csv(
        input_paths["legacy_daily"],
        usecols=["date", logistic_core.PRODUCT_COLUMN, "net_pnl"],
    )
    panel[logistic_core.DATE_COLUMN] = pd.to_datetime(
        panel[logistic_core.DATE_COLUMN], errors="raise"
    ).dt.normalize()
    frozen_a[logistic_core.DATE_COLUMN] = pd.to_datetime(
        frozen_a[logistic_core.DATE_COLUMN], errors="raise"
    ).dt.normalize()
    daily["date"] = pd.to_datetime(daily["date"], errors="raise").dt.normalize()
    features = [str(value) for value in stage003_summary["feature_columns"]]
    folds, fold_audit = logistic_core.build_fold_contracts(panel, windows)

    prediction_frames: list[pd.DataFrame] = []
    model_rows: list[dict[str, Any]] = []
    a_diffs: list[float] = []
    xgb_diffs: list[float] = []
    dump_matches: list[bool] = []
    for fold in folds:
        train = panel[panel[logistic_core.DATE_COLUMN].isin(fold.train_dates)].copy()
        test = panel[panel[logistic_core.DATE_COLUMN].isin(fold.test_dates)].copy()
        recomputed_a_model = logistic_core.fit_logistic(train, features)
        recomputed_a = logistic_core.predict_probability(
            recomputed_a_model, test, features
        )
        frozen_fold = frozen_a[
            frozen_a[logistic_core.DATE_COLUMN].isin(fold.test_dates)
        ].copy()
        joined = test.merge(
            frozen_fold,
            on=[logistic_core.DATE_COLUMN, logistic_core.PRODUCT_COLUMN],
            how="left",
            validate="one_to_one",
        )
        if joined[logistic_core.PROBABILITY_COLUMN].isna().any() or len(joined) != len(test):
            raise Stage004Error(f"stage003_a_join_failed:{fold.window_id}")
        a_diff = float(
            np.max(
                np.abs(
                    recomputed_a
                    - joined[logistic_core.PROBABILITY_COLUMN].to_numpy(dtype="float64")
                )
            )
        )
        first = fusion_core.fit_xgboost(train, features)
        second = fusion_core.fit_xgboost(train, features)
        p1 = fusion_core.predict_xgboost(first, test, features)
        p2 = fusion_core.predict_xgboost(second, test, features)
        xgb_diff = float(np.max(np.abs(p1 - p2)))
        first_sha = fusion_core.booster_dump_sha256(first)
        second_sha = fusion_core.booster_dump_sha256(second)
        dump_match = first_sha == second_sha
        joined[fusion_core.XGB_SCORE_COLUMN] = p1
        joined["window_id"] = fold.window_id
        prediction_frames.append(joined)
        a_diffs.append(a_diff)
        xgb_diffs.append(xgb_diff)
        dump_matches.append(dump_match)
        model_rows.append(
            {
                "window_id": fold.window_id,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "a_prediction_max_abs_diff": a_diff,
                "xgb_repeat_prediction_max_abs_diff": xgb_diff,
                "xgb_first_dump_sha256": first_sha,
                "xgb_second_dump_sha256": second_sha,
                "xgb_dump_sha_match": dump_match,
                "xgb_tree_count": len(first.get_booster().get_dump()),
            }
        )
        mask = fold_audit["window_id"].eq(fold.window_id)
        fold_audit.loc[mask, "a_prediction_max_abs_diff"] = a_diff
        fold_audit.loc[mask, "xgb_repeat_prediction_max_abs_diff"] = xgb_diff
        fold_audit.loc[mask, "xgb_dump_sha_match"] = dump_match

    predictions = pd.concat(prediction_frames, ignore_index=True).sort_values(
        [logistic_core.DATE_COLUMN, logistic_core.PRODUCT_COLUMN], kind="mergesort"
    ).reset_index(drop=True)
    if predictions.duplicated(
        [logistic_core.DATE_COLUMN, logistic_core.PRODUCT_COLUMN]
    ).any():
        raise Stage004Error("prediction_key_duplicate")
    predictions = fusion_core.add_fixed_rank_fusion(predictions)
    score_columns = {
        "A_logistic": fusion_core.LR_SCORE_COLUMN,
        "B_xgboost": fusion_core.XGB_SCORE_COLUMN,
        "C_fusion": fusion_core.FUSION_SCORE_COLUMN,
    }
    monthly, selections = fusion_core.build_arm_monthly_metrics(
        predictions, daily, score_columns
    )
    arms = {
        arm: fusion_core.summarize_arm(monthly, selections, arm)
        for arm in score_columns
    }
    effect_summary = fusion_core.build_effect_summary(monthly, arms)
    effect_gates = fusion_core.evaluate_c_effect_gates(effect_summary)
    after = verify_inputs(input_paths, expected_sha256)
    xgb_probability = predictions[fusion_core.XGB_SCORE_COLUMN].to_numpy(
        dtype="float64"
    )
    preliminary: dict[str, Any] = {
        "input_identity_stable": before == after,
        "feature_count": int(len(features)),
        "valid_fold_count": int(len(folds)),
        "oos_months": int(predictions[logistic_core.DATE_COLUMN].nunique()),
        "pit_violation_rows": int(
            fold_audit.loc[fold_audit["accepted"].astype(bool), "pit_violation_rows"].sum()
        ),
        "a_prediction_max_abs_diff": max(a_diffs),
        "xgb_repeat_prediction_max_abs_diff": max(xgb_diffs),
        "xgb_repeat_dump_sha_match": bool(all(dump_matches)),
        "xgb_probabilities_valid": bool(
            np.isfinite(xgb_probability).all()
            and (xgb_probability >= 0.0).all()
            and (xgb_probability <= 1.0).all()
        ),
        "monthly_arm_rows": int(len(monthly)),
        "sealed_holdout_rows_read": 0,
    }
    technical_gates = build_technical_gates(preliminary)
    passed = all(technical_gates.values()) and all(effect_gates.values())
    decision = PASS_DECISION if passed else FAIL_DECISION
    summary: dict[str, Any] = {
        "line_id": "futures_trend_ai_pit_scorer_rebuild",
        "stage": "Stage004",
        "decision": decision,
        "all_gates_passed": bool(passed),
        "technical_gates": technical_gates,
        "effect_gates": effect_gates,
        **preliminary,
        **effect_summary,
        "arms": arms,
        "xgboost_params": fusion_core.XGBOOST_PARAMS,
        "xgboost_version": xgboost.__version__,
        "sklearn_version": sklearn.__version__,
        "evidence_scope": "fixed_current_design_universe_only",
        "future_path_drawdown_is_account_drawdown": False,
        "inputs_before": before,
        "inputs_after": after,
        "lr_reproduction_training_runs": int(len(folds)),
        "xgboost_training_runs": int(2 * len(folds)),
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    output_columns = [
        logistic_core.DATE_COLUMN,
        logistic_core.PRODUCT_COLUMN,
        logistic_core.FUTURE_PNL_COLUMN,
        logistic_core.FUTURE_RANK_COLUMN,
        logistic_core.TARGET_COLUMN,
        logistic_core.PROBABILITY_COLUMN,
        fusion_core.XGB_SCORE_COLUMN,
        "score_a_percentile",
        "score_b_percentile",
        fusion_core.FUSION_SCORE_COLUMN,
        "window_id",
    ]
    publish_artifacts(
        output_dir,
        predictions=predictions[output_columns],
        monthly_metrics=monthly,
        fold_audit=fold_audit,
        model_dump_audit=pd.DataFrame(model_rows),
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage004(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

