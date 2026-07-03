from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage038"
MODEL_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE_SLUG = "stage038_candidate_pit_feature_matrix_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"

OBJECTIVE_ENTRY_START = pd.Timestamp("2020-01-01")
OBJECTIVE_ENTRY_END = pd.Timestamp("2026-06-30")
EMBARGO_DAYS = 20
N_SPLITS = 4
MIN_CONDITION_COUNT = 60
MIN_OOS_TEST_FOLDS = 3
MIN_SOURCE_COUNT = 5
MIN_YEAR_COUNT = 3
MAX_CANDIDATE_SIGNAL_LAG_DAYS = 7

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
QUALITY_FEATURES_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_quality_features_{STAGE006_TAG}.csv"
ENTRY_CANDIDATES_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_entry_candidates_{STAGE006_TAG}.csv"

STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"
FULL_MARKET_PREDICTIONS_PATH = (
    STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_full_market_predictions_ranked_{STAGE021_TAG}.csv"
)

FEATURE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FOLD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fold_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class TimeSplit:
    split_id: str
    train_mask: pd.Series
    test_mask: pd.Series
    train_start: pd.Timestamp | pd.NaT
    train_end: pd.Timestamp | pd.NaT
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    embargo_days: int


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    description: str
    feature_family: str
    eligible: bool
    mask: pd.Series


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _pctize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    sample = values.replace([np.inf, -np.inf], np.nan).dropna().abs()
    if not sample.empty and sample.quantile(0.99) <= 1.5:
        values = values * 100.0
    return values


def _product_key(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def attach_pit_monthly_features(entries: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Attach latest product-month feature with eval_date <= entry_date."""
    result = entries.copy()
    if result.empty:
        return result
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    result["product_key"] = _product_key(result["product_vt_symbol"])
    result["full_market_eval_date"] = pd.NaT
    result["full_market_ai_rank_desc"] = np.nan
    result["full_market_simple_rank_desc"] = np.nan
    result["full_market_ai_top8"] = False
    result["full_market_simple_top8"] = False
    result["full_market_consensus_top8"] = False
    result["full_market_probability"] = np.nan
    result["full_market_simple_score"] = np.nan

    required = {"eval_date", "product_vt_symbol"}
    if monthly.empty or not required.issubset(monthly.columns):
        return result

    feature_columns = [
        "eval_date",
        "product_vt_symbol",
        "ai_rank_desc",
        "simple_rank_desc",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
    ]
    feature_columns = [column for column in feature_columns if column in monthly.columns]
    features = monthly[feature_columns].copy()
    features["eval_date"] = pd.to_datetime(features["eval_date"], errors="coerce").dt.normalize()
    features["product_key"] = _product_key(features["product_vt_symbol"])
    features = features.dropna(subset=["eval_date"])

    for key, group_index in result.groupby("product_key").groups.items():
        feature_group = features[features["product_key"].eq(key)].sort_values("eval_date")
        if feature_group.empty:
            continue
        entry_group = result.loc[group_index].sort_values("entry_date").copy()
        attached = pd.merge_asof(
            entry_group[["entry_date"]].reset_index(),
            feature_group.sort_values("eval_date"),
            left_on="entry_date",
            right_on="eval_date",
            direction="backward",
        ).set_index("index")
        result.loc[attached.index, "full_market_eval_date"] = attached["eval_date"]
        result.loc[attached.index, "full_market_ai_rank_desc"] = pd.to_numeric(
            attached.get("ai_rank_desc"), errors="coerce"
        )
        result.loc[attached.index, "full_market_simple_rank_desc"] = pd.to_numeric(
            attached.get("simple_rank_desc"), errors="coerce"
        )
        result.loc[attached.index, "full_market_ai_top8"] = _to_bool(
            attached.get("stage021_ai_top8", False), index=attached.index
        )
        result.loc[attached.index, "full_market_simple_top8"] = _to_bool(
            attached.get("stage021_simple_top8", False), index=attached.index
        )
        result.loc[attached.index, "full_market_consensus_top8"] = _to_bool(
            attached.get("stage021_consensus_top8", False), index=attached.index
        )
        result.loc[attached.index, "full_market_probability"] = pd.to_numeric(
            attached.get("predicted_product_suitability_probability"), errors="coerce"
        )
        result.loc[attached.index, "full_market_simple_score"] = pd.to_numeric(
            attached.get("simple_trend_suitability_score"), errors="coerce"
        )
    return result


def build_purged_time_splits(
    frame: pd.DataFrame,
    *,
    date_column: str,
    n_splits: int = N_SPLITS,
    embargo_days: int = EMBARGO_DAYS,
) -> list[TimeSplit]:
    dates = pd.to_datetime(frame[date_column], errors="coerce").dt.normalize()
    unique_dates = pd.Series(dates.dropna().unique()).sort_values().reset_index(drop=True)
    if unique_dates.empty:
        return []
    chunk = max(1, int(math.floor(len(unique_dates) / (n_splits + 1))))
    splits: list[TimeSplit] = []
    for idx in range(n_splits):
        test_start_pos = min((idx + 1) * chunk, len(unique_dates) - 1)
        test_end_pos = len(unique_dates) - 1 if idx == n_splits - 1 else min((idx + 2) * chunk - 1, len(unique_dates) - 1)
        if test_end_pos < test_start_pos:
            continue
        test_start = pd.Timestamp(unique_dates.iloc[test_start_pos])
        test_end = pd.Timestamp(unique_dates.iloc[test_end_pos])
        train_cutoff = test_start - pd.Timedelta(days=embargo_days)
        train_mask = dates < train_cutoff
        test_mask = dates.ge(test_start) & dates.le(test_end)
        if not test_mask.any() or not train_mask.any():
            continue
        train_dates = dates[train_mask]
        splits.append(
            TimeSplit(
                split_id=f"fold_{idx + 1:02d}",
                train_mask=train_mask.fillna(False),
                test_mask=test_mask.fillna(False),
                train_start=pd.Timestamp(train_dates.min()),
                train_end=pd.Timestamp(train_dates.max()),
                test_start=test_start,
                test_end=test_end,
                embargo_days=embargo_days,
            )
        )
    return splits


def _aggregate_open_trades(quality: pd.DataFrame) -> pd.DataFrame:
    frame = quality.copy()
    frame = frame[frame.get("entry_context", "").astype(str).eq("flat_entry")].copy()
    frame = frame[frame.get("layer_kind", "").fillna("base").astype(str).eq("base")].copy()
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    frame["exit_date"] = pd.to_datetime(frame["exit_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["requested_start_month", "open_trade_id", "entry_date"])
    frame = frame.loc[frame["entry_date"].between(OBJECTIVE_ENTRY_START, OBJECTIVE_ENTRY_END)].copy()

    numeric_columns = [
        "realized_pnl",
        "risk_amount",
        "volume",
        "selected_volume",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "target_risk_amount",
        "r_multiple",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    bool_columns = [
        "ai_product_pool_allowed",
        "oi_price_confirm_passed",
        "recovery_sleeve_applied",
        "streak_entry_structure_risk_recovery_applied",
        "post_entry_quality_add_passed",
    ]
    for column in bool_columns:
        if column in frame.columns:
            frame[column] = _to_bool(frame[column]).astype("int64")

    first_columns = [
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "entry_context",
        "layer_kind",
        "risk_mode",
        "signal",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_allowed",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "target_risk_amount",
        "selected_volume",
        "oi_price_confirm_passed",
        "recovery_sleeve_applied",
        "streak_entry_structure_risk_recovery_applied",
        "post_entry_quality_add_passed",
        "requested_start",
        "requested_end",
    ]
    aggregations: dict[str, tuple[str, str]] = {
        "exit_date": ("exit_date", "max"),
        "realized_pnl": ("realized_pnl", "sum"),
        "risk_amount": ("risk_amount", "sum"),
        "volume": ("volume", "sum"),
        "lot_count": ("lot_id", "count"),
    }
    for column in first_columns:
        if column in frame.columns:
            aggregations[column] = (column, "first")

    grouped = (
        frame.sort_values(["requested_start_month", "open_trade_id", "entry_date", "exit_date"])
        .groupby(["requested_start_month", "open_trade_id"], dropna=False)
        .agg(**aggregations)
        .reset_index()
    )
    grouped["r_multiple_agg"] = grouped["realized_pnl"] / grouped["risk_amount"].replace(0.0, np.nan)
    grouped["winner"] = grouped["realized_pnl"] > 0
    grouped["big_winner"] = grouped["r_multiple_agg"] >= 2.0
    grouped["entry_year"] = pd.to_datetime(grouped["entry_date"], errors="coerce").dt.year
    grouped["holding_calendar_days"] = (
        pd.to_datetime(grouped["exit_date"], errors="coerce") - pd.to_datetime(grouped["entry_date"], errors="coerce")
    ).dt.days
    if "product" in grouped.columns:
        grouped["product_vt_symbol"] = grouped["product"].astype(str)
    else:
        grouped["product_vt_symbol"] = grouped["vt_symbol"].astype(str).str.extract(r"([A-Za-z]+)")[0].str.lower()
    return grouped


def _entry_candidate_feature_frame(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    frame = candidates.copy()
    required = {"requested_start_month", "date", "product_vt_symbol", "direction"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()
    frame["candidate_signal_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["direction"] = frame["direction"].astype(str)
    if "entry_context" in frame.columns:
        frame = frame[frame["entry_context"].astype(str).eq("flat_entry")].copy()
    if "is_opened" in frame.columns:
        frame = frame[_to_bool(frame["is_opened"])].copy()
    elif "candidate_status" in frame.columns:
        frame = frame[frame["candidate_status"].astype(str).str.lower().eq("opened")].copy()
    frame = frame.dropna(subset=["candidate_signal_date"])
    if frame.empty:
        return pd.DataFrame()

    for column in [
        "oi_price_confirm_passed",
        "selection_pairwise_rank",
        "selection_pairwise_score",
        "selection_pairwise_volume_tilt_applied",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    aggregations: dict[str, tuple[str, str]] = {
        "entry_candidate_count": ("product_vt_symbol", "count"),
    }
    if "oi_price_confirm_passed" in frame.columns:
        aggregations["entry_candidate_oi_confirmed"] = ("oi_price_confirm_passed", "max")
    if "selection_pairwise_rank" in frame.columns:
        aggregations["entry_candidate_pairwise_rank_min"] = ("selection_pairwise_rank", "min")
    if "selection_pairwise_score" in frame.columns:
        aggregations["entry_candidate_pairwise_score_max"] = ("selection_pairwise_score", "max")
    if "selection_pairwise_volume_tilt_applied" in frame.columns:
        aggregations["entry_candidate_pairwise_volume_tilt_applied"] = (
            "selection_pairwise_volume_tilt_applied",
            "max",
        )

    keys = ["requested_start_month", "candidate_signal_date", "product_vt_symbol", "direction"]
    return frame.groupby(keys, dropna=False).agg(**aggregations).reset_index()


def _attach_entry_candidate_features(matrix: pd.DataFrame, candidates: pd.DataFrame | None) -> pd.DataFrame:
    result = matrix.copy()
    if candidates is None or candidates.empty:
        return result
    features = _entry_candidate_feature_frame(candidates)
    if features.empty:
        return result
    for frame in [result, features]:
        frame["requested_start_month"] = frame["requested_start_month"].astype(str)
        frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
        frame["direction"] = frame["direction"].astype(str)
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    features["candidate_signal_date"] = pd.to_datetime(features["candidate_signal_date"], errors="coerce").dt.normalize()

    value_columns = [
        column
        for column in features.columns
        if column not in {"requested_start_month", "candidate_signal_date", "product_vt_symbol", "direction"}
    ]
    if "entry_candidate_signal_date" not in result.columns:
        result["entry_candidate_signal_date"] = pd.NaT
    if "entry_candidate_signal_lag_days" not in result.columns:
        result["entry_candidate_signal_lag_days"] = np.nan
    for column in value_columns:
        if column not in result.columns:
            result[column] = np.nan

    group_keys = ["requested_start_month", "product_vt_symbol", "direction"]
    for key, row_index in result.groupby(group_keys, dropna=False).groups.items():
        source, product, direction = key
        feature_group = features[
            features["requested_start_month"].eq(source)
            & features["product_vt_symbol"].eq(product)
            & features["direction"].eq(direction)
        ].sort_values("candidate_signal_date")
        if feature_group.empty:
            continue
        entry_group = result.loc[row_index].sort_values("entry_date")
        attached = pd.merge_asof(
            entry_group[["entry_date"]].reset_index(),
            feature_group,
            left_on="entry_date",
            right_on="candidate_signal_date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_CANDIDATE_SIGNAL_LAG_DAYS),
        ).set_index("index")
        matched = attached["candidate_signal_date"].notna()
        if not matched.any():
            continue
        matched_index = attached.index[matched]
        result.loc[matched_index, "entry_candidate_signal_date"] = attached.loc[matched, "candidate_signal_date"]
        result.loc[matched_index, "entry_candidate_signal_lag_days"] = (
            attached.loc[matched, "entry_date"] - attached.loc[matched, "candidate_signal_date"]
        ).dt.days
        for column in value_columns:
            result.loc[matched_index, column] = attached.loc[matched, column]
    return result


def build_feature_matrix(
    quality: pd.DataFrame,
    monthly: pd.DataFrame,
    *,
    entry_candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    matrix = _aggregate_open_trades(quality)
    if matrix.empty:
        return matrix
    matrix = _attach_entry_candidate_features(matrix, entry_candidates)
    matrix["ai_rank"] = _num(matrix, "ai_product_pool_rank")
    matrix["ai_score"] = _num(matrix, "ai_product_pool_score")
    matrix["ai_enabled"] = matrix["ai_rank"].gt(0)
    matrix["ai_rank_1_3"] = matrix["ai_rank"].between(1, 3, inclusive="both")
    matrix["ai_rank_1_6"] = matrix["ai_rank"].between(1, 6, inclusive="both")
    matrix["ai_rank_1_9"] = matrix["ai_rank"].between(1, 9, inclusive="both")
    matrix["ai_rank_gt9"] = matrix["ai_rank"].gt(9)
    quality_oi = _to_bool(matrix.get("oi_price_confirm_passed", False), index=matrix.index)
    candidate_oi = _to_bool(matrix.get("entry_candidate_oi_confirmed", False), index=matrix.index)
    matrix["oi_confirmed"] = quality_oi | candidate_oi
    matrix["drawdown_abs_pct"] = _pctize(_num(matrix, "portfolio_drawdown_pct")).abs()
    matrix["loss_streak"] = _num(matrix, "loss_streak").fillna(0)
    matrix["loss_streak_0"] = matrix["loss_streak"].eq(0)
    matrix["loss_streak_ge2"] = matrix["loss_streak"].ge(2)
    matrix["loss_streak_ge3"] = matrix["loss_streak"].ge(3)
    matrix["account_clean"] = matrix["drawdown_abs_pct"].lt(10) & matrix["loss_streak"].le(1)
    matrix["account_injured"] = matrix["drawdown_abs_pct"].ge(20) | matrix["loss_streak"].ge(3)
    matrix["selected_volume_gt1"] = _num(matrix, "selected_volume").gt(1)
    matrix["active_positions_ge3"] = _num(matrix, "active_positions_before").ge(3)
    matrix["ai_rank_1_9_and_oi_confirm"] = matrix["ai_rank_1_9"] & matrix["oi_confirmed"]
    matrix["ai_rank_1_9_and_account_clean"] = matrix["ai_rank_1_9"] & matrix["account_clean"]
    matrix["ai_rank_1_9_oi_confirm_account_clean"] = (
        matrix["ai_rank_1_9"] & matrix["oi_confirmed"] & matrix["account_clean"]
    )
    matrix = attach_pit_monthly_features(matrix, monthly)
    matrix["full_market_ai_top8"] = _to_bool(matrix["full_market_ai_top8"])
    matrix["full_market_simple_top8"] = _to_bool(matrix["full_market_simple_top8"])
    matrix["full_market_consensus_top8"] = _to_bool(matrix["full_market_consensus_top8"])
    matrix["ai_rank_1_9_and_full_market_consensus"] = matrix["ai_rank_1_9"] & matrix["full_market_consensus_top8"]
    matrix["ai_oi_account_and_full_market_consensus"] = (
        matrix["ai_rank_1_9"] & matrix["oi_confirmed"] & matrix["account_clean"] & matrix["full_market_consensus_top8"]
    )
    return matrix.sort_values(["entry_date", "requested_start_month", "open_trade_id"]).reset_index(drop=True)


def _base_stats(frame: pd.DataFrame) -> dict[str, float]:
    pnl = _num(frame, "realized_pnl", default=0.0).fillna(0.0)
    r_multiple = _num(frame, "r_multiple_agg")
    return {
        "count": float(len(frame)),
        "total_pnl": float(pnl.sum()),
        "mean_pnl": float(pnl.mean()) if len(frame) else 0.0,
        "median_r": float(r_multiple.median()) if r_multiple.notna().any() else np.nan,
        "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(frame) else 0.0,
        "big_win_rate_pct": float(_to_bool(frame.get("big_winner", False), index=frame.index).mean() * 100.0)
        if len(frame)
        else 0.0,
    }


def _condition_specs(matrix: pd.DataFrame) -> list[ConditionSpec]:
    return [
        ConditionSpec("all_open_trades", "全部 2020+ opened flat-entry；只作基准", "baseline", False, pd.Series(True, index=matrix.index)),
        ConditionSpec("ai_rank_1_3", "Stage182 AI rank 1-3", "ai_rank", True, matrix["ai_rank_1_3"]),
        ConditionSpec("ai_rank_1_6", "Stage182 AI rank 1-6", "ai_rank", True, matrix["ai_rank_1_6"]),
        ConditionSpec("ai_rank_1_9", "Stage182 AI rank 1-9", "ai_rank", True, matrix["ai_rank_1_9"]),
        ConditionSpec("oi_confirmed", "OI 与价格方向确认", "oi_confirm", True, matrix["oi_confirmed"]),
        ConditionSpec("account_clean", "入场前账户回撤<10% 且 loss_streak<=1", "account_state", True, matrix["account_clean"]),
        ConditionSpec("loss_streak_0", "入场前 loss_streak=0", "account_state", True, matrix["loss_streak_0"]),
        ConditionSpec("account_injured", "入场前回撤>=20% 或 loss_streak>=3", "account_state", True, matrix["account_injured"]),
        ConditionSpec("ai_rank_1_9_and_oi_confirm", "AI rank 1-9 且 OI确认", "ai_oi", True, matrix["ai_rank_1_9_and_oi_confirm"]),
        ConditionSpec(
            "ai_rank_1_9_and_account_clean",
            "AI rank 1-9 且账户状态干净",
            "ai_account",
            True,
            matrix["ai_rank_1_9_and_account_clean"],
        ),
        ConditionSpec(
            "ai_rank_1_9_oi_confirm_account_clean",
            "AI rank 1-9 + OI确认 + 账户状态干净",
            "ai_oi_account",
            True,
            matrix["ai_rank_1_9_oi_confirm_account_clean"],
        ),
        ConditionSpec("full_market_ai_top8", "full-market AI top8", "full_market", True, matrix["full_market_ai_top8"]),
        ConditionSpec("full_market_simple_top8", "simple trend top8", "full_market", True, matrix["full_market_simple_top8"]),
        ConditionSpec(
            "full_market_consensus_top8",
            "full-market AI top8 且 simple top8 共识",
            "full_market",
            True,
            matrix["full_market_consensus_top8"],
        ),
        ConditionSpec(
            "ai_rank_1_9_and_full_market_consensus",
            "Stage182 AI rank 1-9 且 full-market 共识 top8",
            "ai_full_market",
            True,
            matrix["ai_rank_1_9_and_full_market_consensus"],
        ),
        ConditionSpec(
            "ai_oi_account_and_full_market_consensus",
            "AI rank 1-9 + OI确认 + 账户干净 + full-market 共识",
            "ai_oi_account_full_market",
            True,
            matrix["ai_oi_account_and_full_market_consensus"],
        ),
        ConditionSpec(
            "post_entry_quality_add_passed",
            "开仓后质量确认字段；本阶段显式排除",
            "post_entry",
            False,
            _to_bool(matrix.get("post_entry_quality_add_passed", False), index=matrix.index),
        ),
    ]


def summarize_condition_oos(
    matrix: pd.DataFrame,
    splits: list[TimeSplit],
    conditions: list[ConditionSpec],
    *,
    min_count: int = MIN_CONDITION_COUNT,
    min_test_folds: int = MIN_OOS_TEST_FOLDS,
) -> pd.DataFrame:
    base = _base_stats(matrix)
    rows: list[dict[str, Any]] = []
    pnl_all = pd.to_numeric(matrix.get("realized_pnl"), errors="coerce").fillna(0.0)
    for condition in conditions:
        mask = condition.mask.reindex(matrix.index).fillna(False).astype(bool)
        subset = matrix.loc[mask].copy()
        pnl = _num(subset, "realized_pnl", default=0.0).fillna(0.0)
        r_multiple = _num(subset, "r_multiple_agg")
        fold_pnls: list[float] = []
        fold_counts: list[int] = []
        for split in splits:
            test_mask = split.test_mask.reindex(matrix.index).fillna(False).astype(bool) & mask
            test_pnl = float(pnl_all.loc[test_mask].sum())
            test_count = int(test_mask.sum())
            if test_count > 0:
                fold_pnls.append(test_pnl)
                fold_counts.append(test_count)
        positive_folds = sum(1 for value in fold_pnls if value > 0)
        oos_test_fold_count = len(fold_pnls)
        source_count = int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0
        year_count = int(subset["entry_year"].nunique()) if "entry_year" in subset.columns else 0
        mean_pnl = float(pnl.mean()) if len(subset) else 0.0
        stable = (
            condition.eligible
            and len(subset) >= min_count
            and source_count >= MIN_SOURCE_COUNT
            and year_count >= MIN_YEAR_COUNT
            and oos_test_fold_count >= min_test_folds
            and positive_folds == oos_test_fold_count
            and bool(fold_pnls)
            and min(fold_pnls) > 0
            and float(pnl.sum()) > 0
            and mean_pnl > base["mean_pnl"]
        )
        rows.append(
            {
                "condition": condition.name,
                "description": condition.description,
                "feature_family": condition.feature_family,
                "candidate_eligible": bool(condition.eligible),
                "count": int(len(subset)),
                "coverage_pct": float(len(subset) / len(matrix) * 100.0) if len(matrix) else 0.0,
                "source_count": source_count,
                "year_count": year_count,
                "product_count": int(subset["product_vt_symbol"].nunique()) if "product_vt_symbol" in subset.columns else 0,
                "total_pnl": float(pnl.sum()) if len(subset) else 0.0,
                "pnl_share_pct": float(pnl.sum() / base["total_pnl"] * 100.0) if base["total_pnl"] else np.nan,
                "mean_pnl": mean_pnl,
                "mean_pnl_lift_vs_base": float(mean_pnl / base["mean_pnl"]) if base["mean_pnl"] else np.nan,
                "median_r": float(r_multiple.median()) if r_multiple.notna().any() else np.nan,
                "median_r_lift_vs_base": float(r_multiple.median() / base["median_r"])
                if r_multiple.notna().any() and base["median_r"] not in {0.0, np.nan}
                else np.nan,
                "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(subset) else 0.0,
                "win_rate_lift_pp": float((pnl > 0).mean() * 100.0 - base["win_rate_pct"]) if len(subset) else np.nan,
                "big_win_rate_pct": float(_to_bool(subset.get("big_winner", False), index=subset.index).mean() * 100.0)
                if len(subset)
                else 0.0,
                "big_win_rate_lift_pp": (
                    float(_to_bool(subset.get("big_winner", False), index=subset.index).mean() * 100.0 - base["big_win_rate_pct"])
                    if len(subset)
                    else np.nan
                ),
                "oos_test_fold_count": int(oos_test_fold_count),
                "oos_positive_fold_count": int(positive_folds),
                "oos_min_fold_pnl": float(min(fold_pnls)) if fold_pnls else np.nan,
                "oos_total_test_pnl": float(sum(fold_pnls)) if fold_pnls else 0.0,
                "oos_min_fold_count": int(min(fold_counts)) if fold_counts else 0,
                "stable_oos_candidate": bool(stable),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["stable_oos_candidate", "candidate_eligible", "mean_pnl_lift_vs_base", "oos_min_fold_pnl", "count"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def _fold_summary(matrix: pd.DataFrame, splits: list[TimeSplit]) -> pd.DataFrame:
    rows = []
    for split in splits:
        train = matrix.loc[split.train_mask.reindex(matrix.index).fillna(False).astype(bool)]
        test = matrix.loc[split.test_mask.reindex(matrix.index).fillna(False).astype(bool)]
        rows.append(
            {
                "split_id": split.split_id,
                "train_start": split.train_start.date().isoformat() if pd.notna(split.train_start) else "",
                "train_end": split.train_end.date().isoformat() if pd.notna(split.train_end) else "",
                "test_start": split.test_start.date().isoformat(),
                "test_end": split.test_end.date().isoformat(),
                "embargo_days": split.embargo_days,
                "train_count": int(len(train)),
                "test_count": int(len(test)),
                "train_pnl": float(pd.to_numeric(train.get("realized_pnl"), errors="coerce").fillna(0.0).sum()),
                "test_pnl": float(pd.to_numeric(test.get("realized_pnl"), errors="coerce").fillna(0.0).sum()),
                "test_win_rate_pct": float((pd.to_numeric(test.get("realized_pnl"), errors="coerce").fillna(0.0) > 0).mean() * 100.0)
                if len(test)
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _feature_coverage(matrix: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "ai_rank",
        "ai_score",
        "oi_confirmed",
        "drawdown_abs_pct",
        "loss_streak",
        "account_clean",
        "full_market_eval_date",
        "full_market_ai_rank_desc",
        "full_market_simple_rank_desc",
        "full_market_consensus_top8",
        "post_entry_quality_add_passed",
    ]
    rows = []
    for column in columns:
        if column not in matrix.columns:
            rows.append({"feature": column, "present": False, "non_null_count": 0, "coverage_pct": 0.0})
            continue
        values = matrix[column]
        if pd.api.types.is_bool_dtype(values):
            non_null = int(values.notna().sum())
            active = int(values.fillna(False).sum())
        else:
            non_null = int(values.notna().sum())
            active = int(values.notna().sum())
        rows.append(
            {
                "feature": column,
                "present": True,
                "non_null_count": non_null,
                "active_count": active,
                "coverage_pct": float(non_null / len(matrix) * 100.0) if len(matrix) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _decision(
    matrix: pd.DataFrame,
    condition_summary: pd.DataFrame,
    fold_summary: pd.DataFrame,
    feature_coverage: pd.DataFrame,
) -> dict[str, Any]:
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    top = stable.head(10)
    base = _base_stats(matrix)
    full_market_coverage = feature_coverage.set_index("feature").get("coverage_pct", pd.Series(dtype=float)).get(
        "full_market_eval_date", 0.0
    )
    if stable.empty:
        decision = "stage038_no_stable_preentry_quality_candidate_keep_readonly"
        next_stage = "stage039_try_low_degree_proxy_only_if_candidate_emerges"
    else:
        decision = "stage038_has_preentry_oos_quality_candidates_needs_proxy_engine"
        next_stage = "stage039_freeze_one_low_degree_proxy_from_stage038_not_parameter_sweep"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "quality_features_path": str(QUALITY_FEATURES_PATH),
        "entry_candidates_path": str(ENTRY_CANDIDATES_PATH),
        "full_market_predictions_path": str(FULL_MARKET_PREDICTIONS_PATH),
        "entry_scope": {
            "entry_start": OBJECTIVE_ENTRY_START.date().isoformat(),
            "entry_end": OBJECTIVE_ENTRY_END.date().isoformat(),
            "unit": "opened_flat_entry_open_trade_aggregated",
        },
        "matrix_rows": int(len(matrix)),
        "entry_date_min": matrix["entry_date"].min().date().isoformat() if len(matrix) else "",
        "entry_date_max": matrix["entry_date"].max().date().isoformat() if len(matrix) else "",
        "base_total_pnl": base["total_pnl"],
        "base_mean_pnl": base["mean_pnl"],
        "base_win_rate_pct": base["win_rate_pct"],
        "base_big_win_rate_pct": base["big_win_rate_pct"],
        "split_count": int(len(fold_summary)),
        "embargo_days": EMBARGO_DAYS,
        "stable_condition_count": int(len(stable)),
        "stable_conditions": top["condition"].tolist() if not top.empty else [],
        "best_stable_condition": top.iloc[0].to_dict() if not top.empty else {},
        "full_market_eval_coverage_pct": float(full_market_coverage) if pd.notna(full_market_coverage) else 0.0,
        "post_entry_excluded": True,
        "official_live_config_changed": False,
        "ctp_connected": False,
        "order_api_calls": 0,
        "external_research_judgment": (
            "CFA commodity ML and futures momentum literature support theory-grounded signals, "
            "but Lopez de Prado style purging/embargo and backtest-overfitting warnings require this stage to remain "
            "a point-in-time, OOS stability audit rather than a trading rule or parameter sweep."
        ),
        "overfit_reflection_before": (
            "否。Stage038 不按收益调参，不写交易规则，只把 Stage037 认定可用的入场前字段做点时矩阵和 OOS 分桶审计。"
        ),
        "continue_value_before": (
            "有。用户目标需要 AI 选品识别超高质量信号；在加风险前必须先证明信号不靠未来标签、单年或单 source。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只报告固定条件的 OOS 表现；如果下一步按本表继续扫 rank/topN/阈值/年份，就是过拟合。"
        ),
        "continue_value_after": (
            "有条件。有稳定候选时只能冻结一个低自由度 proxy 进入 Stage039；没有稳定候选时应回到新信息源或账户外层，而不是继续调参。"
        ),
        "outputs": {
            "feature_matrix": str(FEATURE_MATRIX_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "fold_summary": str(FOLD_SUMMARY_PATH),
            "feature_coverage": str(FEATURE_COVERAGE_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    fold_summary: pd.DataFrame,
    feature_coverage: pd.DataFrame,
) -> None:
    lines = [
        "# Stage038 - 候选级 PIT 特征矩阵与 OOS 预测力审计",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision['next_stage']}`",
        "- 本阶段只读：不改正式 C9/15w 配置，不连接 CTP，不调用订单 API。",
        "",
        "## 样本口径",
        "",
        f"- 输入：`{QUALITY_FEATURES_PATH}`",
        f"- OI/候选补充输入：`{ENTRY_CANDIDATES_PATH}`",
        f"- 月度 full-market 输入：`{FULL_MARKET_PREDICTIONS_PATH}`",
        f"- 样本：`{decision['matrix_rows']}` 个 2020+ opened flat-entry open-trade 聚合样本。",
        f"- 日期：`{decision['entry_date_min']}` -> `{decision['entry_date_max']}`",
        f"- full-market as-of 覆盖：`{decision['full_market_eval_coverage_pct']:.4f}%`",
        "",
        "## 调研和判断结论",
        "",
        "- CFA commodity ML 资料支持商品期货中使用有理论约束、可解释的 ML 信号；CME/OI 类资料支持把持仓量确认作为商品趋势确认信息。",
        "- Lopez de Prado/purged CV 与 backtest-overfitting 资料提示，金融时间序列不能用随机 KFold 或事后挑最优阈值；本阶段采用固定条件、时间顺序、embargo 的 OOS 稳定性审计。",
        "- GitHub 上通用 walk-forward/ML trading 代码可参考工程形状，但不能替代本仓当前 C9 点时数据与执行约束。",
        "",
        "## OOS fold",
        "",
        _md_table(fold_summary),
        "",
        "## 特征覆盖",
        "",
        _md_table(feature_coverage),
        "",
        "## 条件 OOS 汇总",
        "",
        _md_table(
            condition_summary[
                [
                    "condition",
                    "candidate_eligible",
                    "count",
                    "coverage_pct",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "big_win_rate_lift_pp",
                    "oos_test_fold_count",
                    "oos_positive_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    stage_path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage038_candidate_pit_feature_matrix_audit.md"
    stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    lines = [
        "# Stage038 - 候选级 PIT 特征矩阵与 OOS 预测力审计",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage038_candidate_pit_feature_matrix_audit.py`",
        "- 新增参数：`EMBARGO_DAYS=20`、`N_SPLITS=4`、`MIN_CONDITION_COUNT=60`、`MIN_OOS_TEST_FOLDS=3`。",
        "- 修改参数：无，Stage006/Stage167 母本和官方 C9/15w 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：无，本阶段不是收益回测，只做只读特征审计。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        "- CFA commodity ML / futures momentum / OI 资料支持 theory-grounded 商品特征；Lopez de Prado/purged CV 和 backtest-overfitting 资料要求做点时、embargo、OOS 稳定性审计。",
        "- 因此 Stage038 不训练模型、不扫阈值、不写交易规则，只判断现有入场前字段是否具备稳定识别超高质量信号的资格。",
        "",
        "## 审计结果",
        "",
        f"- matrix rows：`{decision['matrix_rows']}`。",
        f"- entry date：`{decision['entry_date_min']}` -> `{decision['entry_date_max']}`。",
        f"- base total pnl：`{decision['base_total_pnl']:,.2f}`。",
        f"- base mean pnl：`{decision['base_mean_pnl']:,.4f}`。",
        f"- base win rate：`{decision['base_win_rate_pct']:.4f}%`。",
        f"- full-market as-of 覆盖：`{decision['full_market_eval_coverage_pct']:.4f}%`。",
        f"- stable OOS condition count：`{decision['stable_condition_count']}`。",
        f"- stable conditions：`{', '.join(decision['stable_conditions']) if decision['stable_conditions'] else '无'}`。",
        "",
        "## 条件摘要",
        "",
        _md_table(
            condition_summary[
                [
                    "condition",
                    "candidate_eligible",
                    "count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 输出",
        "",
        f"- feature_matrix：`{FEATURE_MATRIX_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- fold_summary：`{FOLD_SUMMARY_PATH}`",
        f"- feature_coverage：`{FEATURE_COVERAGE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        f"- 下一步：`{decision['next_stage']}`。",
        "- 若 stable condition 非空，只允许冻结一个低自由度 Stage039 proxy，不允许扫 rank/topN/阈值。",
        "- 若 stable condition 为空，停止在当前 AI/OI/account 字段上救参，转新外生信息源或账户外层方案。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    quality = _read_csv(QUALITY_FEATURES_PATH)
    entry_candidates = _read_csv(ENTRY_CANDIDATES_PATH) if ENTRY_CANDIDATES_PATH.exists() else pd.DataFrame()
    monthly = _read_csv(FULL_MARKET_PREDICTIONS_PATH) if FULL_MARKET_PREDICTIONS_PATH.exists() else pd.DataFrame()
    matrix = build_feature_matrix(quality, monthly, entry_candidates=entry_candidates)
    splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    condition_summary = summarize_condition_oos(matrix, splits, _condition_specs(matrix))
    fold_summary = _fold_summary(matrix, splits)
    feature_coverage = _feature_coverage(matrix)
    decision = _decision(matrix, condition_summary, fold_summary, feature_coverage)

    matrix.to_csv(FEATURE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    fold_summary.to_csv(FOLD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_coverage.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, condition_summary, fold_summary, feature_coverage)
    stage_record = _write_stage_record(decision, condition_summary)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
