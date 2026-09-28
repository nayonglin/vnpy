"""Run the frozen Stage003 historical-OOS stacked XGBoost ranker qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import numpy as np
import pandas as pd
import xgboost


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import stacked_xgboost_ranker as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
STAGE001_DIR = LINE_DIR / "artifacts/stage001_market_context_coverage"
STAGE002_DIR = LINE_DIR / "artifacts/stage002_market_context_features"
SCORER_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_ai_pit_scorer_rebuild"
RETURN_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_contract_returns"
OUTPUT_DIR = LINE_DIR / "artifacts/stage003_stacked_xgboost_ranker"
INPUT_PATHS: Final = {
    "feature_panel": STAGE002_DIR / "market_context_feature_panel.csv",
    "stage002_manifest": STAGE002_DIR / "artifact_manifest.json",
    "ranked_a_panel": STAGE001_DIR / "ranked_a_panel.csv",
    "conditional_samples": (
        SCORER_LINE / "artifacts/stage003_feature_contract_fix/conditional_pit_samples.csv"
    ),
    "product_returns": (
        RETURN_LINE / "artifacts/stage001_pit_contract_return_coverage/product_daily_returns.csv.gz"
    ),
    "return_manifest": (
        RETURN_LINE / "artifacts/stage001_pit_contract_return_coverage/artifact_manifest.json"
    ),
    "spec": LINE_DIR / "stages/20260902_1335_stage003_stacked_xgboost_ranker_preregistration.md",
    "ranker_core": LINE_DIR / "tools/stacked_xgboost_ranker.py",
}
EXPECTED_SHA256: Final = {
    "feature_panel": "3d77c8d1d4d9f95612ca4d9c4e0db1df5bc88a58eb8b0a5968a1eaf6bc7fcaf0",
    "stage002_manifest": "ef60982092f42e127533bc82cf462f68ec1aa0cefd7ed294381c899a850656a5",
    "ranked_a_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "conditional_samples": "22fc20b184f1f0e283d0bc2041a37d9bc778646c6fcaad662235c87f2e216cfc",
    "product_returns": "ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa",
    "return_manifest": "32ead9d84ff97d6722a4491e389912c40d9c6558f5f4c6afbfdaa11a64c0c9b5",
    "spec": "b2385a3f296a9a298cf06c2e475c72c37cb6a9588976301f099f397a8ae772e9",
    "ranker_core": "588b7c1c8b893597c18fe2cf87d5d2a813173bb62b79e3eb2321d4d37dc5146e",
}
FEATURE_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "window_id",
    "a_rank",
    "role",
    "pit_logistic_probability",
    *core.FEATURE_COLUMNS,
]
RANKED_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "window_id",
    "a_rank",
    "role",
    "pit_logistic_probability",
]
LABEL_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "future_net_pnl_60d",
    "future_label_end_date",
    "full_horizon_label",
]
RETURN_COLUMNS: Final = [
    "product_vt_symbol",
    "selection_date",
    "return_date",
    "selected_contract_vt",
    "product_return",
    "status",
    "fallback_used",
    "cross_contract_price_used",
]


class Stage003Error(RuntimeError):
    """Raised when the frozen Stage003 runner must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    input_paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage003Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage003Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage003Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _read_inputs(
    input_paths: Mapping[str, Path], *, expected_fold_count: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(Path(input_paths["feature_panel"]), usecols=FEATURE_COLUMNS)
    ranked = pd.read_csv(Path(input_paths["ranked_a_panel"]), usecols=RANKED_COLUMNS)
    labels = pd.read_csv(Path(input_paths["conditional_samples"]), usecols=LABEL_COLUMNS)
    returns = pd.read_csv(Path(input_paths["product_returns"]), usecols=RETURN_COLUMNS)
    fold_ids = sorted(features["window_id"].astype(str).unique())
    if len(fold_ids) != expected_fold_count:
        raise Stage003Error(f"feature_fold_count:{len(fold_ids)}")
    return features, ranked, labels, returns


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
        float_format="%.17g",
    )


def _publish(
    output_dir: Path,
    *,
    predictions: pd.DataFrame,
    monthly: pd.DataFrame,
    model_audit: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage003Error("stage003_output_already_exists")
    if temp_dir.exists():
        raise Stage003Error("stage003_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(predictions, temp_dir / "oos_predictions.csv")
    _write_csv(monthly, temp_dir / "monthly_proxy_metrics.csv")
    _write_csv(model_audit, temp_dir / "model_audit.csv")
    (temp_dir / "stage003_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage003 历史OOS堆叠月分组XGBoost Ranker\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 技术门：`{sum(summary['technical_gates'].values())}/"
        f"{len(summary['technical_gates'])}`；效果门："
        f"`{sum(summary['effect_gates'].values())}/{len(summary['effect_gates'])}`。\n"
        f"- 测试/替换月：`{summary['test_months']}` / `{summary['replacement_months']}`。\n"
        f"- A/C月均未来策略利润代理：`{summary['a_mean_future_pnl']:.2f}` / "
        f"`{summary['c_mean_future_pnl']:.2f}`。\n"
        f"- A/C月均未来市场路径回撤：`{summary['a_mean_market_drawdown']:.6f}` / "
        f"`{summary['c_mean_market_drawdown']:.6f}`。\n"
        "- 本阶段不是策略回测，不产生账户收益率、最大回撤或Sharpe。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "model_audit.csv",
        "monthly_proxy_metrics.csv",
        "oos_predictions.csv",
        "report.md",
        "stage003_summary.json",
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
    top_rank_count: int = 9,
    minimum_train_months: int = 18,
    minimum_train_rows: int = 120,
    expected_feature_rows: int = 328,
    expected_feature_months: int = 43,
    expected_min_test_months: int = 18,
    minimum_test_months_by_year: Mapping[int, int] = {2024: 6, 2025: 6},
    minimum_replacement_months: int = 4,
    future_market_horizon: int = 60,
    expected_fold_count: int = 8,
    model_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage003Error("stage003_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    features, ranked, labels, returns = _read_inputs(
        input_paths, expected_fold_count=expected_fold_count
    )
    labelled = core.attach_relevance_labels(features, labels)
    folds = core.build_stacked_walk_forward_folds(
        labelled,
        minimum_train_months=minimum_train_months,
        minimum_train_rows=minimum_train_rows,
    )
    if not folds:
        raise Stage003Error("no_eligible_walk_forward_tests")

    prediction_frames: list[pd.DataFrame] = []
    model_rows: list[dict[str, Any]] = []
    prediction_diffs: list[float] = []
    dump_matches: list[bool] = []
    split_counts: list[int] = []
    score_unique_counts: list[int] = []
    for index, fold in enumerate(folds, start=1):
        train = labelled[labelled["eval_date"].isin(fold.train_dates)].copy()
        test = labelled[labelled["eval_date"].eq(fold.test_date)].copy().sort_values(
            ["a_rank", "product_vt_symbol"], kind="mergesort"
        )
        first = core.fit_ranker(train, params=model_params)
        second = core.fit_ranker(train, params=model_params)
        first_prediction = core.predict_ranker(first, test)
        second_prediction = core.predict_ranker(second, test)
        prediction_diff = float(np.max(np.abs(first_prediction - second_prediction)))
        first_sha = core.booster_dump_sha256(first)
        second_sha = core.booster_dump_sha256(second)
        dump_match = first_sha == second_sha
        splits = core.split_node_count(first)
        unique_scores = int(np.unique(first_prediction).size)
        test[core.RANKER_SCORE_COLUMN] = first_prediction
        test["ranker_test_id"] = f"stacked_{index:02d}"
        prediction_frames.append(test)
        prediction_diffs.append(prediction_diff)
        dump_matches.append(dump_match)
        split_counts.append(splits)
        score_unique_counts.append(unique_scores)
        model_rows.append(
            {
                "ranker_test_id": f"stacked_{index:02d}",
                "test_date": fold.test_date,
                "train_start": min(fold.train_dates),
                "train_end": max(fold.train_dates),
                "train_label_end_max": fold.train_label_end_max,
                "train_months": int(len(fold.train_dates)),
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "train_label_overlap_rows": int(
                    (train["future_label_end_date"] >= fold.test_date).sum()
                ),
                "repeat_prediction_max_abs_diff": prediction_diff,
                "first_dump_sha256": first_sha,
                "second_dump_sha256": second_sha,
                "dump_sha_match": dump_match,
                "split_node_count": splits,
                "test_score_unique_count": unique_scores,
            }
        )
    predictions = pd.concat(prediction_frames, ignore_index=True).sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    monthly = core.build_monthly_proxy_metrics(
        predictions,
        ranked,
        labels,
        returns,
        top_rank_count=top_rank_count,
        future_market_horizon=future_market_horizon,
    )
    effects = core.summarize_proxy_effects(monthly)
    effect_gates = core.evaluate_effect_gates(
        effects,
        minimum_replacement_months=minimum_replacement_months,
        required_years=tuple(minimum_test_months_by_year),
    )
    model_audit = pd.DataFrame(model_rows)
    test_months_by_year = {
        str(year): int(pd.to_datetime(predictions["eval_date"]).dt.year.eq(int(year)).groupby(
            predictions["eval_date"]
        ).max().sum())
        for year in sorted(minimum_test_months_by_year)
    }
    returns_normalised = core._normalise_returns(returns)
    technical_gates = {
        "input_identity_stable": True,
        "feature_row_count_exact": len(labelled) == expected_feature_rows,
        "feature_month_count_exact": labelled["eval_date"].nunique() == expected_feature_months,
        "full_horizon_labels_all": bool(labelled["full_horizon_label"].all()),
        "label_values_finite": bool(np.isfinite(labelled["future_net_pnl_60d"].to_numpy(float)).all()),
        "test_months_minimum": predictions["eval_date"].nunique() >= expected_min_test_months,
        "test_months_each_year_minimum": all(
            test_months_by_year[str(year)] >= int(minimum)
            for year, minimum in minimum_test_months_by_year.items()
        ),
        "train_months_minimum": bool(model_audit["train_months"].ge(minimum_train_months).all()),
        "train_rows_minimum": bool(model_audit["train_rows"].ge(minimum_train_rows).all()),
        "train_label_overlap_zero": int(model_audit["train_label_overlap_rows"].sum()) == 0,
        "query_group_size_range": bool(model_audit["test_rows"].between(6 if top_rank_count == 9 else 3, 9 if top_rank_count == 9 else 3).all()),
        "repeat_prediction_exact": max(prediction_diffs) == 0.0,
        "repeat_dump_sha_match": bool(all(dump_matches)),
        "split_nodes_positive_every_model": min(split_counts) > 0,
        "test_scores_nonconstant_every_month": min(score_unique_counts) >= 2,
        "future_market_metrics_finite": bool(
            np.isfinite(
                monthly[
                    ["a_future_market_drawdown_60d", "c_future_market_drawdown_60d"]
                ].to_numpy(float)
            ).all()
        ),
        "return_source_pit_violation_zero": int(
            (returns_normalised["selection_date"] >= returns_normalised["return_date"]).sum()
        )
        == 0,
        "return_source_fallback_zero": int(returns_normalised["fallback_used"].sum()) == 0,
        "return_source_cross_contract_zero": int(
            returns_normalised["cross_contract_price_used"].sum()
        )
        == 0,
    }
    after = _verify_inputs(input_paths, expected_sha256)
    technical_gates["input_identity_stable"] = before == after
    passed = all(technical_gates.values()) and all(effect_gates.values())
    decision = core.PASS_DECISION if passed else core.FAIL_DECISION
    summary: dict[str, Any] = {
        "line_id": "futures_trend_xgboost_pit_market_context_after_listing",
        "stage": "Stage003",
        "decision": decision,
        "all_gates_passed": bool(passed),
        "technical_gates": technical_gates,
        "effect_gates": effect_gates,
        **effects,
        "feature_rows": int(len(labelled)),
        "feature_months": int(labelled["eval_date"].nunique()),
        "test_rows": int(len(predictions)),
        "test_months": int(predictions["eval_date"].nunique()),
        "test_months_by_year": test_months_by_year,
        "minimum_train_months_observed": int(model_audit["train_months"].min()),
        "minimum_train_rows_observed": int(model_audit["train_rows"].min()),
        "repeat_prediction_max_abs_diff": float(max(prediction_diffs)),
        "repeat_dump_sha_match": bool(all(dump_matches)),
        "minimum_split_nodes": int(min(split_counts)),
        "minimum_test_score_unique_count": int(min(score_unique_counts)),
        "ranker_params": core.RANKER_PARAMS if model_params is None else model_params,
        "xgboost_version": xgboost.__version__,
        "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
        "evidence_scope": "observed_development_historical_oos_stacking_only",
        "future_market_drawdown_is_account_drawdown": False,
        "input_identities_before": before,
        "input_identities_after": after,
        "input_identity_stable": before == after,
        "feature_columns_read": list(FEATURE_COLUMNS),
        "ranked_columns_read": list(RANKED_COLUMNS),
        "label_columns_read": list(LABEL_COLUMNS),
        "return_columns_read": list(RETURN_COLUMNS),
        "sealed_holdout_files_read": [],
        "xgboost_training_runs": int(2 * len(folds)),
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    prediction_columns = [
        "eval_date",
        "product_vt_symbol",
        "window_id",
        "ranker_test_id",
        "a_rank",
        "role",
        "pit_logistic_probability",
        "future_net_pnl_60d",
        "future_label_end_date",
        "rank_relevance",
        core.RANKER_SCORE_COLUMN,
    ]
    _publish(
        Path(output_dir),
        predictions=predictions[prediction_columns],
        monthly=monthly,
        model_audit=model_audit,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage003(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
