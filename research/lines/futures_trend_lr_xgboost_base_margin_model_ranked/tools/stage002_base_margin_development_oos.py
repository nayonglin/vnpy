"""Frozen development OOS test for LR-initialized XGBoost residual correction."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import xgboost
from sklearn.metrics import log_loss
from xgboost import XGBClassifier


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage001_model_ranked_contract as stage001


LINE_DIR = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = (
    LINE_DIR
    / "stages/20260904_1554_stage002_base_margin_development_oos_preregistration.md"
)
TEST_PATH = (
    LINE_DIR / "tests/test_stage002_base_margin_development_oos.py"
)
AUTHORIZATION_PATH = (
    LINE_DIR / "stages/20260904_stage002_execution_authorization.json"
)
STAGE001_DIR = LINE_DIR / "artifacts/stage001_model_ranked_contract"
STAGE001_SUMMARY_PATH = STAGE001_DIR / "summary.json"
STAGE001_MANIFEST_PATH = STAGE001_DIR / "artifact_manifest.json"
STAGE001_FOLD_PLAN_PATH = STAGE001_DIR / "fold_plan.csv"
FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage002_base_margin_development_oos"

PASS_DECISION = (
    "stage002_base_margin_residual_development_oos_pass_"
    "require_independent_review_before_true_engine"
)
FAIL_DECISION = "stage002_base_margin_residual_development_oos_fail_close_no_true_engine"

TOP_N = 10
HORIZON = 60
XGBOOST_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "n_estimators": 32,
    "max_depth": 1,
    "learning_rate": 0.03,
    "min_child_weight": 20,
    "gamma": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 20.0,
    "max_delta_step": 1.0,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 1,
}


class Stage002Error(RuntimeError):
    pass


@dataclass(frozen=True)
class ResidualFitResult:
    probability: np.ndarray
    raw_correction: np.ndarray
    repeat_max_abs_error: float
    split_nodes: int


def _sha256(path: Path) -> tuple[int, int, str]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise Stage002Error(f"file_changed_while_hashing:{source}")
    return int(after.st_size), int(after.st_mtime_ns), digest.hexdigest()


def _logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probability, dtype="float64"), 1e-12, 1.0 - 1e-12)
    return np.log(clipped / (1.0 - clipped))


def _new_xgboost_model() -> XGBClassifier:
    return XGBClassifier(**XGBOOST_PARAMS)


def fit_base_margin_residual(
    *,
    x_train: Any,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    train_margin: np.ndarray,
    x_test: Any,
    test_margin: np.ndarray,
) -> ResidualFitResult:
    """Fit two identical residual models and return the first prediction plus audit data."""

    model = _new_xgboost_model()
    model.fit(
        x_train,
        y_train,
        sample_weight=sample_weight,
        base_margin=train_margin,
        verbose=False,
    )
    probability = np.asarray(
        model.predict_proba(x_test, base_margin=test_margin)[:, 1],
        dtype="float64",
    )

    repeated = _new_xgboost_model()
    repeated.fit(
        x_train,
        y_train,
        sample_weight=sample_weight,
        base_margin=train_margin,
        verbose=False,
    )
    repeated_probability = np.asarray(
        repeated.predict_proba(x_test, base_margin=test_margin)[:, 1],
        dtype="float64",
    )
    repeat_error = float(np.max(np.abs(probability - repeated_probability)))
    tree_frame = model.get_booster().trees_to_dataframe()
    split_nodes = int(tree_frame["Feature"].ne("Leaf").sum())
    raw_correction = _logit(probability) - np.asarray(test_margin, dtype="float64")
    return ResidualFitResult(
        probability=probability,
        raw_correction=raw_correction,
        repeat_max_abs_error=repeat_error,
        split_nodes=split_nodes,
    )


def build_future_path_table(
    daily: pd.DataFrame,
    eval_dates: Iterable[pd.Timestamp],
    *,
    horizon: int = HORIZON,
) -> pd.DataFrame:
    required = {"date", "product_vt_symbol", "net_pnl"}
    missing = sorted(required - set(daily.columns))
    if missing:
        raise ValueError(f"future_path_columns_missing:{','.join(missing)}")
    if horizon <= 0:
        raise ValueError("future_path_horizon_must_be_positive")
    tests = pd.DatetimeIndex(pd.to_datetime(list(eval_dates))).normalize().unique().sort_values()
    rows: list[pd.DataFrame] = []
    for product, raw_group in daily.groupby("product_vt_symbol", sort=True):
        group = raw_group[["date", "net_pnl"]].copy()
        group["date"] = pd.to_datetime(group["date"]).dt.normalize()
        group.sort_values("date", inplace=True)
        group.reset_index(drop=True, inplace=True)
        positions = {pd.Timestamp(date): index for index, date in enumerate(group["date"])}
        for eval_date in tests:
            if eval_date not in positions:
                raise ValueError(
                    f"future_path_eval_date_missing:{product}:{eval_date.date().isoformat()}"
                )
            start = positions[eval_date] + 1
            path = group.iloc[start : start + int(horizon)].copy()
            if len(path) != int(horizon):
                raise ValueError(
                    f"future_path_incomplete:{product}:{eval_date.date().isoformat()}:{len(path)}"
                )
            path.insert(0, "eval_date", pd.Timestamp(eval_date))
            path.insert(1, "product_vt_symbol", str(product))
            path.insert(2, "path_step", np.arange(1, int(horizon) + 1))
            rows.append(path)
    result = pd.concat(rows, ignore_index=True)
    result.sort_values(
        ["eval_date", "product_vt_symbol", "path_step"],
        inplace=True,
    )
    result.reset_index(drop=True, inplace=True)
    return result


def path_metrics(net_pnl: np.ndarray) -> dict[str, float]:
    values = np.asarray(net_pnl, dtype="float64")
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("path_values_invalid")
    equity = np.concatenate(([0.0], np.cumsum(values)))
    drawdown = equity - np.maximum.accumulate(equity)
    return {
        "total_net_pnl": float(values.sum()),
        "max_drawdown": float(drawdown.min()),
    }


def stable_top_n(
    frame: pd.DataFrame,
    *,
    score_column: str,
    top_n: int = TOP_N,
) -> list[str]:
    ranked = frame.sort_values(
        [score_column, "product_vt_symbol"],
        ascending=[False, True],
        kind="mergesort",
    )
    return ranked.head(int(top_n))["product_vt_symbol"].astype(str).tolist()


def _selected_path_metrics(
    paths: pd.DataFrame,
    products: list[str],
) -> dict[str, float]:
    selected = paths[paths["product_vt_symbol"].isin(products)].copy()
    if selected["product_vt_symbol"].nunique() != len(products):
        raise ValueError("selected_path_product_missing")
    expected_steps = int(selected["path_step"].max())
    counts = selected.groupby("product_vt_symbol")["path_step"].nunique()
    if not counts.eq(expected_steps).all():
        raise ValueError("selected_path_step_incomplete")
    aggregate = (
        selected.groupby("path_step", sort=True)["net_pnl"]
        .sum()
        .reindex(range(1, expected_steps + 1))
    )
    if aggregate.isna().any():
        raise ValueError("selected_path_step_gap")
    return path_metrics(aggregate.to_numpy(dtype="float64"))


def build_monthly_effects(
    predictions: pd.DataFrame,
    future_paths: pd.DataFrame,
    *,
    top_n: int = TOP_N,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    effect_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    frame = predictions.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
    paths = future_paths.copy()
    paths["eval_date"] = pd.to_datetime(paths["eval_date"]).dt.normalize()
    for eval_date, month in frame.groupby("eval_date", sort=True):
        selected_a = stable_top_n(month, score_column="score_a", top_n=top_n)
        selected_b = stable_top_n(month, score_column="score_b", top_n=top_n)
        month_paths = paths[paths["eval_date"].eq(eval_date)]
        metrics_a = _selected_path_metrics(month_paths, selected_a)
        metrics_b = _selected_path_metrics(month_paths, selected_b)
        for arm, products in (("A", selected_a), ("B", selected_b)):
            for rank, product in enumerate(products, start=1):
                selection_rows.append(
                    {
                        "eval_date": pd.Timestamp(eval_date),
                        "arm": arm,
                        "selection_rank": rank,
                        "product_vt_symbol": product,
                    }
                )
        return_delta = metrics_b["total_net_pnl"] - metrics_a["total_net_pnl"]
        drawdown_improvement = metrics_b["max_drawdown"] - metrics_a["max_drawdown"]
        effect_rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "selected_a": ",".join(selected_a),
                "selected_b": ",".join(selected_b),
                "changed": set(selected_a) != set(selected_b),
                "a_future_net_pnl_60d": metrics_a["total_net_pnl"],
                "b_future_net_pnl_60d": metrics_b["total_net_pnl"],
                "a_future_max_drawdown_60d": metrics_a["max_drawdown"],
                "b_future_max_drawdown_60d": metrics_b["max_drawdown"],
                "return_delta": return_delta,
                "drawdown_improvement": drawdown_improvement,
                "joint_positive": return_delta > 0.0 and drawdown_improvement > 0.0,
            }
        )
    return pd.DataFrame(effect_rows), pd.DataFrame(selection_rows)


def summarize_effects(
    monthly_effects: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    effects = monthly_effects.copy()
    effects["eval_date"] = pd.to_datetime(effects["eval_date"]).dt.normalize()
    changed = effects[effects["changed"].astype(bool)].copy()
    if changed.empty:
        yearly = pd.DataFrame(
            columns=["year", "changed_months", "return_delta", "drawdown_improvement"]
        )
        return {
            "changed_months": 0,
            "changed_years": 0,
            "sum_return_delta": 0.0,
            "sum_drawdown_improvement": 0.0,
            "leave_best_return_delta": 0.0,
            "leave_best_drawdown_improvement": 0.0,
            "joint_positive_ratio": 0.0,
            "minimum_year_return_delta": 0.0,
            "minimum_year_drawdown_improvement": 0.0,
        }, yearly
    changed["joint_positive"] = (
        changed["return_delta"].gt(0.0)
        & changed["drawdown_improvement"].gt(0.0)
    )
    changed["year"] = changed["eval_date"].dt.year
    yearly = (
        changed.groupby("year", as_index=False)
        .agg(
            changed_months=("eval_date", "size"),
            return_delta=("return_delta", "sum"),
            drawdown_improvement=("drawdown_improvement", "sum"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )
    return_sum = float(changed["return_delta"].sum())
    drawdown_sum = float(changed["drawdown_improvement"].sum())
    summary = {
        "changed_months": int(len(changed)),
        "changed_years": int(changed["year"].nunique()),
        "sum_return_delta": return_sum,
        "sum_drawdown_improvement": drawdown_sum,
        "leave_best_return_delta": float(return_sum - changed["return_delta"].max()),
        "leave_best_drawdown_improvement": float(
            drawdown_sum - changed["drawdown_improvement"].max()
        ),
        "joint_positive_ratio": float(changed["joint_positive"].mean()),
        "minimum_year_return_delta": float(yearly["return_delta"].min()),
        "minimum_year_drawdown_improvement": float(
            yearly["drawdown_improvement"].min()
        ),
    }
    return summary, yearly


def summarize_model_metrics(predictions: pd.DataFrame) -> dict[str, float]:
    target = predictions["target"].to_numpy(dtype="int64")
    weight = predictions["sample_weight"].to_numpy(dtype="float64")
    score_a = np.clip(predictions["score_a"].to_numpy(dtype="float64"), 1e-12, 1 - 1e-12)
    score_b = np.clip(predictions["score_b"].to_numpy(dtype="float64"), 1e-12, 1 - 1e-12)
    rank_ics = (
        predictions.groupby("eval_date", sort=True)
        .apply(
            lambda group: pd.Series(
                {
                    "a": group["score_a"].corr(group["future_rank"], method="spearman"),
                    "b": group["score_b"].corr(group["future_rank"], method="spearman"),
                }
            ),
            include_groups=False,
        )
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    return {
        "weighted_logloss_a": float(
            log_loss(target, score_a, sample_weight=weight, labels=[0, 1])
        ),
        "weighted_logloss_b": float(
            log_loss(target, score_b, sample_weight=weight, labels=[0, 1])
        ),
        "mean_monthly_rank_ic_a": float(rank_ics["a"].mean()),
        "mean_monthly_rank_ic_b": float(rank_ics["b"].mean()),
    }


def assess_gates(metrics: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if not (
        int(metrics.get("input_identity_mismatch_count", -1)) == 0
        and bool(metrics.get("authorization_valid", False))
        and bool(metrics.get("stage001_manifest_valid", False))
    ):
        failures.append("identity_authorization")
    if not (
        int(metrics.get("fold_count", -1)) == 50
        and int(metrics.get("prediction_rows", -1)) == 900
        and int(metrics.get("minimum_products_per_test_month", -1)) == 18
        and int(metrics.get("maximum_products_per_test_month", -1)) == 18
        and int(metrics.get("feature_count", -1)) == 108
        and int(metrics.get("logistic_fit_count", -1)) == 50
        and int(metrics.get("scaler_fit_count", -1)) == 50
        and int(metrics.get("xgboost_fit_count", -1)) == 100
    ):
        failures.append("fold_and_fit_contract")
    if not (
        int(metrics.get("pit_violation_rows", -1)) == 0
        and int(metrics.get("pit_violation_folds", -1)) == 0
        and int(metrics.get("sealed_holdout_rows", -1)) == 0
        and int(metrics.get("fixed_fu_model_rows", -1)) == 0
    ):
        failures.append("pit_and_scope_integrity")
    if not (
        int(metrics.get("nonfinite_output_cells", -1)) == 0
        and int(metrics.get("nonpositive_score_std_months_a", -1)) == 0
        and int(metrics.get("nonpositive_score_std_months_b", -1)) == 0
    ):
        failures.append("finite_nonconstant_predictions")
    if float(metrics.get("repeat_prediction_max_abs_error", float("inf"))) != 0.0:
        failures.append("deterministic_repeat")
    if not (
        int(metrics.get("xgboost_split_nodes", 0)) > 0
        and int(metrics.get("xgboost_folds_with_splits", -1)) == 50
    ):
        failures.append("xgboost_non_degenerate")
    median_correction = float(metrics.get("median_abs_correction", float("inf")))
    max_correction = float(metrics.get("max_abs_correction", float("inf")))
    if not (1e-6 < median_correction <= 0.5 and max_correction <= 2.0):
        failures.append("bounded_residual_correction")
    if not (
        float(metrics.get("weighted_logloss_b", float("inf")))
        < float(metrics.get("weighted_logloss_a", -float("inf")))
        and float(metrics.get("mean_monthly_rank_ic_b", -float("inf")))
        > float(metrics.get("mean_monthly_rank_ic_a", float("inf")))
    ):
        failures.append("model_quality_increment")
    if not (
        int(metrics.get("changed_months", -1)) >= 8
        and int(metrics.get("changed_years", -1)) >= 3
    ):
        failures.append("minimum_action_coverage")
    if not (
        float(metrics.get("sum_return_delta", -float("inf"))) > 0.0
        and float(metrics.get("sum_drawdown_improvement", -float("inf"))) > 0.0
    ):
        failures.append("joint_return_drawdown_effect")
    if not (
        float(metrics.get("leave_best_return_delta", -float("inf"))) > 0.0
        and float(metrics.get("leave_best_drawdown_improvement", -float("inf"))) > 0.0
    ):
        failures.append("leave_best_robustness")
    if float(metrics.get("joint_positive_ratio", -float("inf"))) < 0.55:
        failures.append("joint_positive_rate")
    if not (
        float(metrics.get("minimum_year_return_delta", -float("inf"))) > 0.0
        and float(metrics.get("minimum_year_drawdown_improvement", -float("inf"))) > 0.0
    ):
        failures.append("yearly_robustness")
    side_effect_fields = (
        "true_engine_run_count",
        "ctp_connection_count",
        "order_api_call_count",
        "production_write_count",
    )
    if any(int(metrics.get(field, -1)) != 0 for field in side_effect_fields):
        failures.append("forbidden_side_effect")
    failures = list(dict.fromkeys(failures))
    passed = not failures
    return {
        "all_gates_passed": passed,
        "failures": failures,
        "decision": PASS_DECISION if passed else FAIL_DECISION,
    }


def validate_authorization_receipt(receipt_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"valid": False, "errors": ["authorization_receipt_unreadable"]}
    if receipt.get("authorized") is not True:
        errors.append("authorization_not_granted")
    if receipt.get("authorization_scope") != "single_stage002_development_oos":
        errors.append("authorization_scope_invalid")
    if int(receipt.get("allowed_run_count", -1)) != 1:
        errors.append("authorization_run_count_invalid")
    bindings = receipt.get("bindings", {})
    if not isinstance(bindings, dict) or not bindings:
        errors.append("authorization_bindings_missing")
    else:
        for name, binding in bindings.items():
            try:
                path = Path(str(binding["path"]))
                _, _, actual = _sha256(path)
            except (KeyError, OSError, Stage002Error):
                errors.append(f"binding_unreadable:{name}")
                continue
            if actual != str(binding.get("sha256", "")):
                errors.append(f"binding_sha256_mismatch:{name}")
    return {"valid": not errors, "errors": errors, "receipt": receipt}


def _read_stage001_fold_plan() -> pd.DataFrame:
    frame = pd.read_csv(STAGE001_FOLD_PLAN_PATH)
    for column in (
        "test_eval_date",
        "test_label_end",
        "train_start",
        "train_end",
        "train_label_end_max",
    ):
        frame[column] = pd.to_datetime(frame[column]).dt.normalize()
    return frame


def _parse_train_dates(value: object) -> pd.DatetimeIndex:
    raw = [item for item in str(value).split(",") if item]
    return pd.DatetimeIndex(pd.to_datetime(raw)).normalize()


def _input_identities(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, binding in receipt.get("bindings", {}).items():
        path = Path(str(binding["path"]))
        size, mtime_ns, digest = _sha256(path)
        result[name] = {
            "path": str(path.resolve()),
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": digest,
            "expected_sha256": str(binding["sha256"]),
            "matches_expected": digest == str(binding["sha256"]),
        }
    return result


def _pit_audit(
    fold_plan: pd.DataFrame,
    label_calendar: pd.DataFrame,
) -> tuple[int, int]:
    label_end_by_date = label_calendar.set_index("eval_date")["label_end"]
    violation_rows = 0
    violation_folds = 0
    for row in fold_plan.itertuples(index=False):
        train_dates = _parse_train_dates(row.train_eval_dates)
        invalid = label_end_by_date.loc[train_dates] > pd.Timestamp(row.test_eval_date)
        count = int(invalid.sum())
        violation_rows += count
        violation_folds += int(count > 0)
    return violation_rows, violation_folds


def _atomic_publish(
    *,
    summary: dict[str, Any],
    identities: dict[str, Any],
    predictions: pd.DataFrame,
    fold_diagnostics: pd.DataFrame,
    monthly_effects: pd.DataFrame,
    yearly_effects: pd.DataFrame,
    selections: pd.DataFrame,
    authorization: dict[str, Any],
) -> None:
    final = FINAL_OUTPUT_DIR.resolve()
    if final.exists():
        raise Stage002Error(f"final_output_exists:{final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.tmp.{os.getpid()}"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        stage001.base._write_json(temporary / "summary.json", summary)
        stage001.base._write_json(temporary / "input_identities.json", identities)
        stage001.base._write_json(
            temporary / "model_params.json",
            {
                "logistic": {
                    "C": 0.20,
                    "solver": "lbfgs",
                    "max_iter": 3000,
                    "random_state": 42,
                },
                "xgboost": XGBOOST_PARAMS,
                "xgboost_version": xgboost.__version__,
                "top_n": TOP_N,
                "future_horizon_trading_days": HORIZON,
            },
        )
        stage001.base._write_json(
            temporary / "authorization_receipt.json",
            authorization,
        )
        predictions.to_csv(temporary / "oos_predictions.csv", index=False)
        fold_diagnostics.to_csv(temporary / "fold_diagnostics.csv", index=False)
        monthly_effects.to_csv(temporary / "monthly_effects.csv", index=False)
        yearly_effects.to_csv(temporary / "yearly_effects.csv", index=False)
        selections.to_csv(temporary / "top10_selections.csv", index=False)
        (temporary / "report.md").write_text(
            "\n".join(
                [
                    "# Stage002 base-margin residual development OOS",
                    "",
                    f"- Decision: `{summary['decision']}`",
                    f"- Folds/predictions: `{summary['fold_count']}/{summary['prediction_rows']}`",
                    f"- Changed months: `{summary['changed_months']}`",
                    f"- Return delta: `{summary['sum_return_delta']}`",
                    f"- Drawdown improvement: `{summary['sum_drawdown_improvement']}`",
                    f"- Failures: `{','.join(summary['failures']) or 'none'}`",
                    "- This is a product-contribution proxy, not a true portfolio backtest.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        names = [
            "summary.json",
            "input_identities.json",
            "model_params.json",
            "authorization_receipt.json",
            "oos_predictions.csv",
            "fold_diagnostics.csv",
            "monthly_effects.csv",
            "yearly_effects.csv",
            "top10_selections.csv",
            "report.md",
        ]
        manifest = {
            "schema_version": 1,
            "files": stage001.base._file_manifest(temporary, names),
        }
        stage001.base._write_json(temporary / "artifact_manifest.json", manifest)
        verification = verify_output_bundle(temporary)
        if not verification["valid"]:
            raise Stage002Error(
                f"temporary_manifest_invalid:{','.join(verification['errors'])}"
            )
        os.replace(temporary, final)
        verification = verify_output_bundle(final)
        if not verification["valid"]:
            raise Stage002Error(
                f"published_manifest_invalid:{','.join(verification['errors'])}"
            )
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_output_bundle(directory: Path = FINAL_OUTPUT_DIR) -> dict[str, Any]:
    return stage001.base.verify_evidence_bundle(directory)


def preflight() -> dict[str, Any]:
    if FINAL_OUTPUT_DIR.exists():
        raise Stage002Error(f"final_output_exists:{FINAL_OUTPUT_DIR}")
    authorization = validate_authorization_receipt(AUTHORIZATION_PATH)
    stage001_manifest = stage001.base.verify_evidence_bundle(STAGE001_DIR)
    stage001_summary = json.loads(STAGE001_SUMMARY_PATH.read_text(encoding="utf-8"))
    valid = bool(
        authorization["valid"]
        and stage001_manifest["valid"]
        and stage001_summary.get("decision") == stage001.PASS_DECISION
        and xgboost.__version__ == "3.2.0"
    )
    return {
        "valid": valid,
        "authorization": {
            "valid": authorization["valid"],
            "errors": authorization["errors"],
        },
        "stage001_manifest": stage001_manifest,
        "stage001_decision": stage001_summary.get("decision"),
        "xgboost_version": xgboost.__version__,
        "label_value_read_count": 0,
        "model_fit_count": 0,
        "output_write_count": 0,
    }


def run_stage002() -> dict[str, Any]:
    preflight_result = preflight()
    if not preflight_result["valid"]:
        raise Stage002Error("stage002_preflight_failed")
    authorization_result = validate_authorization_receipt(AUTHORIZATION_PATH)
    receipt = authorization_result["receipt"]
    identities_before = _input_identities(receipt)

    current, manifest, stage182 = stage001.base._load_current_identity()
    formal = stage001.base._load_formal_model_module()
    daily = formal.build_product_daily()
    featured = formal.add_rolling_features(daily)
    samples, feature_columns = formal.build_monthly_samples(featured)
    cutoff = pd.Timestamp(stage182["training_label_cutoff"]).normalize()
    panel = samples[pd.to_datetime(samples["eval_date"]).dt.normalize() <= cutoff].copy()
    panel["eval_date"] = pd.to_datetime(panel["eval_date"]).dt.normalize()
    panel.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    if len(panel) != 1386 or panel["eval_date"].nunique() != 77 or len(feature_columns) != 108:
        raise Stage002Error("formal_labeled_panel_contract_failed")

    fold_plan = _read_stage001_fold_plan()
    label_calendar = stage001.causal.build_label_end_calendar(
        daily["date"],
        panel["eval_date"],
        horizon=HORIZON,
    )
    pit_rows, pit_folds = _pit_audit(fold_plan, label_calendar)

    prediction_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    repeat_errors: list[float] = []
    total_split_nodes = 0
    folds_with_splits = 0
    for fold in fold_plan.itertuples(index=False):
        train_dates = _parse_train_dates(fold.train_eval_dates)
        test_date = pd.Timestamp(fold.test_eval_date)
        train = panel[panel["eval_date"].isin(train_dates)].copy()
        test = panel[panel["eval_date"].eq(test_date)].copy()
        if len(train) != len(train_dates) * 18 or len(test) != 18:
            raise Stage002Error(f"fold_row_contract_failed:{fold.fold_id}")
        logistic = formal.train_model(train, feature_columns)
        x_train = formal.prepare_x(train, feature_columns)
        x_test = formal.prepare_x(test, feature_columns)
        train_margin = np.asarray(
            logistic.decision_function(x_train),
            dtype="float64",
        )
        test_margin = np.asarray(
            logistic.decision_function(x_test),
            dtype="float64",
        )
        score_a = np.asarray(logistic.predict_proba(x_test)[:, 1], dtype="float64")
        residual = fit_base_margin_residual(
            x_train=x_train,
            y_train=train[formal.TARGET_COLUMN].to_numpy(dtype="int64"),
            sample_weight=train[formal.WEIGHT_COLUMN].to_numpy(dtype="float64"),
            train_margin=train_margin,
            x_test=x_test,
            test_margin=test_margin,
        )
        repeat_errors.append(residual.repeat_max_abs_error)
        total_split_nodes += residual.split_nodes
        folds_with_splits += int(residual.split_nodes > 0)
        scored = test[
            [
                "eval_date",
                "product_vt_symbol",
                formal.TARGET_COLUMN,
                formal.WEIGHT_COLUMN,
                "future_rank_centered_60d",
                "future_net_pnl_60d",
            ]
        ].copy()
        scored.rename(
            columns={
                formal.TARGET_COLUMN: "target",
                formal.WEIGHT_COLUMN: "sample_weight",
                "future_rank_centered_60d": "future_rank",
                "future_net_pnl_60d": "future_net_pnl_60d",
            },
            inplace=True,
        )
        scored["fold_id"] = str(fold.fold_id)
        scored["train_months"] = int(fold.train_months)
        scored["train_label_end_max"] = pd.Timestamp(fold.train_label_end_max)
        scored["score_a"] = score_a
        scored["score_b"] = residual.probability
        scored["raw_margin_a"] = test_margin
        scored["raw_correction"] = residual.raw_correction
        prediction_frames.append(scored)
        fold_rows.append(
            {
                "fold_id": str(fold.fold_id),
                "test_eval_date": test_date,
                "train_months": int(fold.train_months),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "train_label_end_max": pd.Timestamp(fold.train_label_end_max),
                "repeat_prediction_max_abs_error": residual.repeat_max_abs_error,
                "split_nodes": residual.split_nodes,
                "median_abs_correction": float(np.median(np.abs(residual.raw_correction))),
                "max_abs_correction": float(np.max(np.abs(residual.raw_correction))),
            }
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    predictions.reset_index(drop=True, inplace=True)
    fold_diagnostics = pd.DataFrame(fold_rows)
    future_paths = build_future_path_table(
        daily[["date", "product_vt_symbol", "net_pnl"]],
        predictions["eval_date"].unique(),
        horizon=HORIZON,
    )
    monthly_effects, selections = build_monthly_effects(
        predictions,
        future_paths,
        top_n=TOP_N,
    )
    effect_summary, yearly_effects = summarize_effects(monthly_effects)
    model_summary = summarize_model_metrics(predictions)

    output_numeric_columns = [
        "score_a",
        "score_b",
        "raw_margin_a",
        "raw_correction",
        "future_rank",
        "future_net_pnl_60d",
    ]
    nonfinite_output_cells = int(
        (~np.isfinite(predictions[output_numeric_columns].to_numpy(dtype="float64"))).sum()
    )
    score_stds = predictions.groupby("eval_date")[["score_a", "score_b"]].std()
    products_per_test = predictions.groupby("eval_date")["product_vt_symbol"].nunique()
    abs_correction = predictions["raw_correction"].abs()

    identities_after = _input_identities(receipt)
    mismatch_count = sum(
        not bool(identity["matches_expected"])
        for identity in identities_before.values()
    ) + sum(
        identities_before[name]["sha256"] != identities_after[name]["sha256"]
        for name in identities_before
    )
    metrics: dict[str, Any] = {
        "current_release_id": current.get("release_id"),
        "current_strategy_id": current.get("strategy_version"),
        "xgboost_version": xgboost.__version__,
        "input_identity_mismatch_count": int(mismatch_count),
        "authorization_valid": True,
        "stage001_manifest_valid": True,
        "fold_count": int(len(fold_plan)),
        "prediction_rows": int(len(predictions)),
        "minimum_products_per_test_month": int(products_per_test.min()),
        "maximum_products_per_test_month": int(products_per_test.max()),
        "feature_count": int(len(feature_columns)),
        "logistic_fit_count": int(len(fold_plan)),
        "scaler_fit_count": int(len(fold_plan)),
        "xgboost_fit_count": int(len(fold_plan) * 2),
        "pit_violation_rows": int(pit_rows),
        "pit_violation_folds": int(pit_folds),
        "sealed_holdout_rows": 0,
        "fixed_fu_model_rows": int(
            predictions["product_vt_symbol"].astype(str).eq("fu.SHFE").sum()
        ),
        "nonfinite_output_cells": nonfinite_output_cells,
        "nonpositive_score_std_months_a": int(score_stds["score_a"].le(0).sum()),
        "nonpositive_score_std_months_b": int(score_stds["score_b"].le(0).sum()),
        "repeat_prediction_max_abs_error": float(max(repeat_errors)),
        "xgboost_split_nodes": int(total_split_nodes),
        "xgboost_folds_with_splits": int(folds_with_splits),
        "median_abs_correction": float(abs_correction.median()),
        "max_abs_correction": float(abs_correction.max()),
        **model_summary,
        **effect_summary,
        "true_engine_run_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "label_value_rows_read": int(len(panel)),
        "development_oos_label_rows_used": int(len(predictions)),
    }
    gate_result = assess_gates(metrics)
    summary = {**metrics, **gate_result}
    identities = {"before": identities_before, "after": identities_after}
    _atomic_publish(
        summary=summary,
        identities=identities,
        predictions=predictions,
        fold_diagnostics=fold_diagnostics,
        monthly_effects=monthly_effects,
        yearly_effects=yearly_effects,
        selections=selections,
        authorization=receipt,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--authorized-development-oos", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight()
        if not result["valid"]:
            raise Stage002Error("stage002_preflight_failed")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.verify_only:
        result = verify_output_bundle()
        if not result["valid"]:
            raise Stage002Error(f"verification_failed:{','.join(result['errors'])}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    summary = run_stage002()
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=stage001.base._json_default,
        )
    )


if __name__ == "__main__":
    main()
