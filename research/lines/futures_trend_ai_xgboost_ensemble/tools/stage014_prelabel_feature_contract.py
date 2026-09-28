"""Freeze a low-dimensional XGBoost feature contract before reading labels."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
FORMAL_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases"
    / FORMAL_RELEASE_ID
)
FORMAL_SUMMARY = FORMAL_RELEASE / "payload/ai/stage182/summary.json"
MODEL_CODE = (
    FORMAL_RELEASE
    / "payload/examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py"
)
PARITY_PANEL = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_ai_score_attribution/artifacts/"
    "stage001_20260731/training_samples.csv"
)
FULL_RANKING = LINE / "artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
LABEL_PLAN = LINE / "artifacts/stage013_label_grid_coverage/full_grid_label_plan.csv"
PREREGISTRATION = LINE / "stages/20260901_1820_stage014_prelabel_feature_contract.md"
OUT = LINE / "artifacts/stage014_prelabel_feature_contract"
HOLDOUT_MONTHS = 12

STRUCTURAL_SOURCE_COLUMNS = [
    "net_pnl_sum_120d",
    "net_pnl_sum_60d",
    "net_pnl_sharpe_like_60d",
    "pnl_positive_day_mean_60d",
    "opened_count_sum_60d",
    "slippage_sum_60d",
    "net_pnl_drawdown_60d",
]
STRUCTURAL_OUTPUT_NAMES = [
    "pnl120_z_delta_vs_rank10",
    "pnl60_z_delta_vs_rank10",
    "sharpe60_z_delta_vs_rank10",
    "positive_day60_z_delta_vs_rank10",
    "opened60_z_delta_vs_rank10",
    "slippage60_z_delta_vs_rank10",
    "drawdown60_z_delta_vs_rank10",
]
MODEL_FEATURE_COLUMNS = [
    "formal_probability_delta_vs_rank10",
    "formal_rank_distance",
    *STRUCTURAL_OUTPUT_NAMES,
]
XGBREGRESSOR_PARAMS = {
    "objective": "reg:squarederror",
    "eval_metric": "rmse",
    "n_estimators": 64,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 12.0,
    "gamma": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 10.0,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 1,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cross_section_zscore(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="raise").astype(float)
    grouped = values.groupby(frame["eval_date"])
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0.0, np.nan)
    return ((values - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_pairwise_feature_panel(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "score_rank",
        "score",
        "score_type",
        *STRUCTURAL_SOURCE_COLUMNS,
    }
    if missing := sorted(required - set(frame.columns)):
        raise RuntimeError(f"feature_input_columns_missing:{missing}")
    result = frame.loc[:, list(required)].copy()
    result["eval_date"] = pd.to_datetime(
        result["eval_date"], errors="raise"
    ).dt.date.astype(str)
    result["score_rank"] = pd.to_numeric(
        result["score_rank"], errors="raise"
    ).astype(int)
    if result.duplicated(["eval_date", "score_rank"]).any():
        raise RuntimeError("feature_month_rank_duplicate")
    baseline_count = result[result["score_rank"].eq(10)].groupby("eval_date").size()
    if not baseline_count.eq(1).all() or len(baseline_count) != result["eval_date"].nunique():
        raise RuntimeError("feature_rank10_baseline_shape")

    probability = pd.to_numeric(result["score"], errors="raise").astype(float)
    probability_mode = result["score_type"].astype(str).eq(
        "ai_probability_top19_plus_fixed_fu"
    )
    probability = probability.where(probability_mode, np.nan)
    baseline_probability = pd.Series(
        probability[result["score_rank"].eq(10)].to_numpy(),
        index=result.loc[result["score_rank"].eq(10), "eval_date"],
    )
    result["formal_probability_delta_vs_rank10"] = probability - result[
        "eval_date"
    ].map(baseline_probability)
    result["formal_rank_distance"] = result["score_rank"].astype(float) - 10.0

    for source, output in zip(STRUCTURAL_SOURCE_COLUMNS, STRUCTURAL_OUTPUT_NAMES):
        z_column = f"__z__{source}"
        result[z_column] = _cross_section_zscore(result, source)
        baseline = result[result["score_rank"].eq(10)].set_index("eval_date")[z_column]
        result[output] = result[z_column] - result["eval_date"].map(baseline)

    columns = [
        "eval_date",
        "product_vt_symbol",
        "score_rank",
        "score_type",
        *MODEL_FEATURE_COLUMNS,
    ]
    result = result.loc[:, columns].sort_values(
        ["eval_date", "score_rank"], kind="mergesort"
    )
    result.reset_index(drop=True, inplace=True)
    return result


def build_month_split(
    dates: Any,
    *,
    holdout_months: int = HOLDOUT_MONTHS,
) -> pd.DataFrame:
    normalized = pd.DatetimeIndex(pd.to_datetime(list(dates), errors="raise")).normalize()
    normalized = pd.DatetimeIndex(sorted(normalized.unique()))
    if len(normalized) <= holdout_months:
        raise RuntimeError("insufficient_months_for_sealed_holdout")
    cutoff = len(normalized) - holdout_months
    return pd.DataFrame(
        {
            "eval_date": normalized.date.astype(str),
            "split": [
                "development" if index < cutoff else "sealed_holdout"
                for index in range(len(normalized))
            ],
            "label_values_read_allowed": [index < cutoff for index in range(len(normalized))],
        }
    )


def _load_model_code(products: list[str]):
    universe = ModuleType("qmt_universe")
    universe.VT_SYMBOLS = list(products)
    previous = sys.modules.get("qmt_universe")
    sys.modules["qmt_universe"] = universe
    spec = importlib.util.spec_from_file_location(
        "stage014_m0005_frozen_model_code", MODEL_CODE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_formal_model_code:{MODEL_CODE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("qmt_universe", None)
        else:
            sys.modules["qmt_universe"] = previous
    return module


def _verify_source_identities(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    verified: dict[str, dict[str, Any]] = {}
    for key in ("position_changes", "entry_candidate_snapshots"):
        path = Path(summary["source_paths"][key])
        actual = {"path": str(path), "size": path.stat().st_size, "sha256": _sha256(path)}
        expected = summary["source_identities"][key]
        if actual["size"] != int(expected["size"]) or actual["sha256"] != expected["sha256"]:
            raise RuntimeError(f"m0005_source_identity_drift:{key}")
        verified[key] = actual
    return verified


def _feature_parity(
    samples: pd.DataFrame,
    feature_columns: list[str],
    parity: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["eval_date", "product_vt_symbol"]
    left = samples.loc[:, [*keys, *feature_columns]].copy()
    right = parity.loc[:, [*keys, *feature_columns]].copy()
    left["eval_date"] = pd.to_datetime(left["eval_date"]).dt.normalize()
    right["eval_date"] = pd.to_datetime(right["eval_date"]).dt.normalize()
    merged = left.merge(right, on=keys, suffixes=("_new", "_old"), validate="one_to_one")
    if len(merged) != len(right):
        raise RuntimeError(f"legacy_feature_parity_rows:{len(merged)}:{len(right)}")
    errors = []
    for column in feature_columns:
        a = pd.to_numeric(merged[f"{column}_new"], errors="raise").to_numpy(float)
        b = pd.to_numeric(merged[f"{column}_old"], errors="raise").to_numpy(float)
        errors.append(float(np.max(np.abs(a - b))))
    max_error = max(errors, default=0.0)
    if not np.isfinite(max_error) or max_error > 1e-9:
        raise RuntimeError(f"legacy_feature_parity_failed:{max_error}")
    return {"rows": int(len(merged)), "features": len(feature_columns), "max_abs_error": max_error}


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"stage014_output_already_exists:{OUT}")
    formal_summary = json.loads(FORMAL_SUMMARY.read_text(encoding="utf-8"))
    if formal_summary.get("model_tag") != "stage182_ai_product_pool_live_inference_v1":
        raise RuntimeError("formal_model_tag_drift")
    sources = _verify_source_identities(formal_summary)
    parity = pd.read_csv(PARITY_PANEL)
    products = sorted(parity["product_vt_symbol"].astype(str).unique())
    if len(products) != 18:
        raise RuntimeError(f"formal_product_count:{len(products)}")
    model_code = _load_model_code(products)
    model_code.POSITION_CHANGES_PATH = Path(sources["position_changes"]["path"])
    model_code.ENTRY_SNAPSHOTS_PATH = Path(
        sources["entry_candidate_snapshots"]["path"]
    )
    daily = model_code.build_product_daily()
    featured = model_code.add_rolling_features(daily)
    samples, all_feature_columns = model_code.build_monthly_samples(featured)
    if len(all_feature_columns) != 108:
        raise RuntimeError(f"formal_feature_count:{len(all_feature_columns)}")
    parity_result = _feature_parity(samples, all_feature_columns, parity)

    plan = pd.read_csv(LABEL_PLAN)
    plan_keys = plan.loc[
        :, ["eval_date", "next_eval_date", "product_vt_symbol", "score_rank"]
    ].copy()
    plan_keys["eval_date"] = pd.to_datetime(plan_keys["eval_date"]).dt.date.astype(str)
    eval_dates = set(plan_keys["eval_date"])
    raw = featured.copy()
    raw["eval_date"] = pd.to_datetime(raw["date"]).dt.date.astype(str)
    raw = raw[raw["eval_date"].isin(eval_dates)].copy()
    if len(raw) != 51 * 18 or raw["eval_date"].nunique() != 51:
        raise RuntimeError(f"raw_feature_grid_shape:{len(raw)}:{raw['eval_date'].nunique()}")
    if not raw.groupby("eval_date").size().eq(18).all():
        raise RuntimeError("raw_feature_month_product_shape")

    ranking = pd.read_csv(FULL_RANKING)
    ranking["eval_date"] = pd.to_datetime(ranking["eval_date"]).dt.date.astype(str)
    ranking = ranking[
        ranking["eval_date"].isin(eval_dates)
    ].loc[:, ["eval_date", "product_vt_symbol", "score", "score_rank", "score_type"]]
    feature_input = ranking.merge(
        raw.loc[:, ["eval_date", "product_vt_symbol", *STRUCTURAL_SOURCE_COLUMNS]],
        on=["eval_date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
    )
    if feature_input[STRUCTURAL_SOURCE_COLUMNS].isna().any().any():
        raise RuntimeError("raw_structural_feature_missing")
    pairwise = build_pairwise_feature_panel(feature_input)
    panel = plan_keys.merge(
        pairwise,
        on=["eval_date", "product_vt_symbol", "score_rank"],
        how="left",
        validate="one_to_one",
    )
    if len(panel) != 459 or panel["eval_date"].nunique() != 51:
        raise RuntimeError(f"model_feature_panel_shape:{len(panel)}:{panel['eval_date'].nunique()}")
    if not panel.groupby("eval_date")["score_rank"].apply(list).map(
        lambda values: values == list(range(10, 19))
    ).all():
        raise RuntimeError("model_feature_month_rank_shape")
    non_probability = panel["score_type"].eq("membership_locked_top19_plus_fixed_fu")
    expected_missing = int(non_probability.sum())
    observed_missing = int(panel["formal_probability_delta_vs_rank10"].isna().sum())
    if observed_missing != expected_missing or expected_missing != 27:
        raise RuntimeError(
            f"formal_probability_missing_contract:{observed_missing}:{expected_missing}"
        )
    other_features = [
        column
        for column in MODEL_FEATURE_COLUMNS
        if column != "formal_probability_delta_vs_rank10"
    ]
    if not np.isfinite(panel[other_features].to_numpy(float)).all():
        raise RuntimeError("model_feature_nonfinite")

    split = build_month_split(panel["eval_date"].unique())
    panel = panel.merge(split, on="eval_date", how="left", validate="many_to_one")
    split_counts = split["split"].value_counts().to_dict()
    if split_counts != {"development": 39, "sealed_holdout": 12}:
        raise RuntimeError(f"month_split_shape:{split_counts}")
    holdout_start = split[split["split"].eq("sealed_holdout")]["eval_date"].min()
    holdout_end = split[split["split"].eq("sealed_holdout")]["eval_date"].max()

    contract = {
        "line_id": "futures_trend_ai_xgboost_ensemble",
        "stage": "Stage014",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": "stage014_nine_feature_prelabel_contract_frozen",
        "formal_release_id": FORMAL_RELEASE_ID,
        "model_features": MODEL_FEATURE_COLUMNS,
        "feature_count": len(MODEL_FEATURE_COLUMNS),
        "structural_source_columns": STRUCTURAL_SOURCE_COLUMNS,
        "feature_semantics": (
            "month_cross_section_zscore_candidate_minus_formal_rank10; formal probability "
            "is missing for membership-locked months"
        ),
        "panel": {
            "rows": int(len(panel)),
            "months": int(panel["eval_date"].nunique()),
            "ranks_per_month": 9,
            "probability_missing_rows": observed_missing,
        },
        "split": {
            "development_months": 39,
            "sealed_holdout_months": 12,
            "sealed_holdout_start": holdout_start,
            "sealed_holdout_end": holdout_end,
            "holdout_label_values_read_allowed_before_model_freeze": False,
        },
        "planned_models": {
            "return_delta_model": "XGBRegressor",
            "drawdown_improvement_model": "XGBRegressor",
            "parameters": XGBREGRESSOR_PARAMS,
            "parameter_scan_allowed": False,
            "label_based_feature_selection_allowed": False,
        },
        "arms": {
            "A": "formal_logistic_rank10",
            "B": "xgboost_dual_head_direct_selector_rank10_to18",
            "C": (
                "formal_top9_plus_xgboost_challenger_only_when_predicted_return_delta_gt0_"
                "and_predicted_drawdown_improvement_gt0_else_formal_rank10"
            ),
        },
        "parity": parity_result,
        "source_identities": sources,
        "input_identities": {
            "formal_summary": {"path": str(FORMAL_SUMMARY), "sha256": _sha256(FORMAL_SUMMARY)},
            "formal_model_code": {"path": str(MODEL_CODE), "sha256": _sha256(MODEL_CODE)},
            "legacy_parity_panel": {"path": str(PARITY_PANEL), "sha256": _sha256(PARITY_PANEL)},
            "formal_full_ranking": {"path": str(FULL_RANKING), "sha256": _sha256(FULL_RANKING)},
            "stage013_label_plan_keys_only": {"path": str(LABEL_PLAN), "sha256": _sha256(LABEL_PLAN)},
            "preregistration": {"path": str(PREREGISTRATION), "sha256": _sha256(PREREGISTRATION)},
        },
        "stage013_columns_consumed": [
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "score_rank",
        ],
        "account_label_files_read": [],
        "account_label_values_read": False,
        "runs_backtest": False,
        "trains_model": False,
        "order_api_called_count": 0,
        "ctp_connected": False,
    }
    OUT.mkdir(parents=True, exist_ok=False)
    panel.to_csv(OUT / "prelabel_feature_panel.csv", index=False, encoding="utf-8-sig")
    split.to_csv(OUT / "month_split.csv", index=False, encoding="utf-8-sig")
    (OUT / "feature_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = (
        "# Stage014 账户边际XGBoost标签前特征合同\n\n"
        f"- 决策：`{contract['decision']}`。\n"
        f"- 特征：{len(MODEL_FEATURE_COLUMNS)}项；面板：{len(panel)}行/51个月。\n"
        f"- 旧108特征重合{parity_result['rows']}行最大误差："
        f"`{parity_result['max_abs_error']:.3e}`。\n"
        f"- development：39个月；sealed holdout：12个月（{holdout_start}至{holdout_end}）。\n"
        "- 未读取账户标签，未训练模型，未回测，未连接CTP，未调用订单API。\n"
    )
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(contract, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
