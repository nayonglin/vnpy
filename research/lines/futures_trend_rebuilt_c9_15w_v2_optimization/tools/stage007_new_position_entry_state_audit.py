from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage007"
MODEL_TAG = "stage007_new_position_entry_state_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage007_new_position_entry_state_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_new_position_entry_state_audit"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_stage013_base_holding_position_attribution"
STAGE006_PREFIX = "rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution"
STAGE006_TAG = "stage006_stage013_base_holding_position_attribution_v1"
STAGE006_WINDOW_DETAIL_PATH = (
    STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_window_position_detail_{STAGE006_TAG}.csv.gz"
)

STAGE019_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE019_CLOSED_LOTS_PATH = (
    STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
)

ENTRY_EXPOSURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exposures_{MODEL_TAG}.csv.gz"
BACKGROUND_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_background_lots_{MODEL_TAG}.csv.gz"
UNMATCHED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unmatched_window_rows_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
NUMERIC_FEATURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_feature_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_lift_chart_{MODEL_TAG}.png"

DEFAULT_MIN_POPULATION_COUNT = 50
DEFAULT_MIN_SOURCE_COUNT = 3
DEFAULT_MIN_LOSS_SHARE_PCT = 5.0
DEFAULT_MIN_LIFT = 1.25

PIT_NUMERIC_FEATURES = [
    "ai_product_pool_rank",
    "ai_product_pool_score",
    "active_positions_before",
    "loss_streak",
    "risk_multiplier",
    "selected_volume",
    "target_risk_amount",
    "contracts_by_risk",
    "contracts_by_margin",
    "stop_distance",
    "entry_risk_distance_pct",
    "entry_risk_distance_pct_abs",
    "rsi_value",
    "breakout",
    "bullish_alignment",
    "bearish_alignment",
    "portfolio_drawdown_abs_pct",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "recovery_sleeve_applied",
    "streak_entry_structure_risk_recovery_applied",
]

POST_ENTRY_LABEL_FEATURES = [
    "realized_pnl",
    "r_multiple",
    "mfe_r",
    "mae_r",
    "exit_efficiency",
    "holding_calendar_days",
    "days_to_mfe",
    "days_to_mae",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
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
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    text = frame[column].astype(str).str.strip().str.lower()
    return text.isin(["1", "1.0", "true", "yes", "y", "pass", "passed", "opened"])


def _pctize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    sample = values.replace([np.inf, -np.inf], np.nan).dropna().abs()
    if not sample.empty and sample.quantile(0.99) <= 1.5:
        values = values * 100.0
    return values


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def prepare_window_loss_rows(window_detail: pd.DataFrame) -> pd.DataFrame:
    data = window_detail.copy()
    data["source_start_month"] = data["source_start_month"].astype(str)
    data["window_start_date"] = pd.to_datetime(data["window_start_date"], errors="coerce").dt.normalize()
    data["window_end_date"] = pd.to_datetime(data["window_end_date"], errors="coerce").dt.normalize()
    for column in [
        "stage074_scaled_holding_pnl",
        "stage074_scaled_net_pnl",
        "stage074_scaled_trading_pnl",
        "stage074_scaled_cost",
        "active_days",
        "contract_count",
        "trade_count",
        "max_abs_end_pos",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["product"] = data["product"].astype(str)
    data["direction"] = data["direction"].astype(str).str.lower()
    scoped = data[
        data["source_bucket"].astype(str).eq("opened_or_traded_after_window_start")
        & data["direction"].isin(["long", "short"])
        & data["window_start_date"].notna()
        & data["window_end_date"].notna()
        & _numeric(data, "stage074_scaled_holding_pnl", 0.0).lt(0.0)
    ].copy()
    scoped["window_row_id"] = np.arange(len(scoped), dtype=int)
    scoped["window_holding_loss_abs"] = scoped["stage074_scaled_holding_pnl"].clip(upper=0.0).abs()
    scoped["window_net_loss_abs"] = scoped["stage074_scaled_net_pnl"].clip(upper=0.0).abs()
    return scoped.sort_values(
        ["source_start_month", "window_start_date", "window_end_date", "product", "direction"]
    ).reset_index(drop=True)


def prepare_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    data = closed_lots.copy()
    if "lot_id" not in data.columns:
        data["lot_id"] = np.arange(len(data), dtype=int)
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["product"] = data["product"].astype(str)
    data["direction"] = data["direction"].astype(str).str.lower()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    if "exit_date" in data.columns:
        data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in [*PIT_NUMERIC_FEATURES, *POST_ENTRY_LABEL_FEATURES, "volume", "size", "risk_amount"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    if "portfolio_drawdown_pct" in data.columns:
        data["portfolio_drawdown_abs_pct"] = _pctize(data["portfolio_drawdown_pct"]).abs()
    if "entry_risk_distance_pct" in data.columns:
        data["entry_risk_distance_pct_abs"] = _pctize(data["entry_risk_distance_pct"]).abs()
    data["lot_key"] = data["requested_start_month"].astype(str) + "|" + data["lot_id"].astype(str)
    return data.dropna(subset=["requested_start_month", "product", "direction", "entry_date"]).reset_index(drop=True)


def match_entry_exposures(window_rows: pd.DataFrame, closed_lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    exposure_frames: list[pd.DataFrame] = []
    unmatched_rows: list[dict[str, Any]] = []
    lot_groups = {
        (str(source), str(product), str(direction)): group.reset_index(drop=True)
        for (source, product, direction), group in closed_lots.groupby(
            ["requested_start_month", "product", "direction"], dropna=False
        )
    }
    for _, row in window_rows.iterrows():
        key = (str(row["source_start_month"]), str(row["product"]), str(row["direction"]))
        candidates = lot_groups.get(key, closed_lots.iloc[0:0])
        matched = candidates[
            candidates["entry_date"].gt(row["window_start_date"])
            & candidates["entry_date"].le(row["window_end_date"])
        ].copy()
        if matched.empty:
            payload = row.to_dict()
            payload["matched_lot_count"] = 0
            unmatched_rows.append(payload)
            continue
        count = len(matched)
        matched["matched_window_row_id"] = int(row["window_row_id"])
        matched["window_id"] = row["window_id"]
        matched["window_source_start_month"] = row["source_start_month"]
        matched["window_start_date"] = row["window_start_date"]
        matched["window_end_date"] = row["window_end_date"]
        matched["window_product"] = row["product"]
        matched["window_direction"] = row["direction"]
        matched["window_stage074_scaled_holding_pnl"] = float(row["stage074_scaled_holding_pnl"])
        matched["window_stage074_scaled_net_pnl"] = float(row.get("stage074_scaled_net_pnl", np.nan))
        matched["window_holding_loss_abs"] = float(row["window_holding_loss_abs"])
        matched["window_net_loss_abs"] = float(row.get("window_net_loss_abs", np.nan))
        matched["matched_lot_count"] = int(count)
        matched["allocated_window_holding_loss_abs"] = float(row["window_holding_loss_abs"]) / count
        matched["allocated_window_net_loss_abs"] = float(row.get("window_net_loss_abs", np.nan)) / count
        exposure_frames.append(matched)
    exposures = pd.concat(exposure_frames, ignore_index=True, sort=False) if exposure_frames else pd.DataFrame()
    unmatched = pd.DataFrame(unmatched_rows)
    return exposures, unmatched


def build_background_lots(closed_lots: pd.DataFrame, window_rows: pd.DataFrame) -> pd.DataFrame:
    if window_rows.empty:
        return closed_lots.iloc[0:0].copy()
    horizons = (
        window_rows.groupby("source_start_month", dropna=False)
        .agg(first_window_start=("window_start_date", "min"), last_window_end=("window_end_date", "max"))
        .reset_index()
    )
    frames: list[pd.DataFrame] = []
    for _, horizon in horizons.iterrows():
        source = str(horizon["source_start_month"])
        source_lots = closed_lots[closed_lots["requested_start_month"].astype(str).eq(source)].copy()
        mask = source_lots["entry_date"].gt(horizon["first_window_start"]) & source_lots["entry_date"].le(
            horizon["last_window_end"]
        )
        frames.append(source_lots.loc[mask])
    if not frames:
        return closed_lots.iloc[0:0].copy()
    scoped = pd.concat(frames, ignore_index=True, sort=False)
    return scoped[scoped["direction"].isin(["long", "short"])].reset_index(drop=True)


def attach_exposure_weights(background_lots: pd.DataFrame, entry_exposures: pd.DataFrame) -> pd.DataFrame:
    background = background_lots.copy()
    if entry_exposures.empty:
        background["residual_exposure_count"] = 0
        background["allocated_window_holding_loss_abs"] = 0.0
        background["allocated_window_net_loss_abs"] = 0.0
        background["residual_exposed"] = False
        return background
    exposures = entry_exposures.copy()
    if "matched_window_row_id" not in exposures.columns:
        exposures["matched_window_row_id"] = np.arange(len(exposures), dtype=int)
    if "allocated_window_net_loss_abs" not in exposures.columns:
        exposures["allocated_window_net_loss_abs"] = 0.0
    if "window_start_date" not in exposures.columns:
        exposures["window_start_date"] = pd.NaT
    if "window_end_date" not in exposures.columns:
        exposures["window_end_date"] = pd.NaT
    exposure_summary = (
        exposures.groupby("lot_key", dropna=False)
        .agg(
            residual_exposure_count=("matched_window_row_id", "count"),
            allocated_window_holding_loss_abs=("allocated_window_holding_loss_abs", "sum"),
            allocated_window_net_loss_abs=("allocated_window_net_loss_abs", "sum"),
            earliest_residual_window_start=("window_start_date", "min"),
            latest_residual_window_end=("window_end_date", "max"),
        )
        .reset_index()
    )
    result = background.merge(exposure_summary, on="lot_key", how="left")
    result["residual_exposure_count"] = pd.to_numeric(result["residual_exposure_count"], errors="coerce").fillna(0).astype(int)
    for column in ["allocated_window_holding_loss_abs", "allocated_window_net_loss_abs"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["residual_exposed"] = result["residual_exposure_count"].gt(0)
    return result


def _condition_masks(lots: pd.DataFrame) -> list[tuple[str, str, pd.Series, bool]]:
    index = lots.index

    def num(column: str) -> pd.Series:
        return _numeric(lots, column)

    direction = lots["direction"].astype(str).str.lower() if "direction" in lots.columns else pd.Series("", index=index)
    ai_rank = num("ai_product_pool_rank")
    ai_score = num("ai_product_pool_score")
    active = num("active_positions_before")
    loss_streak = num("loss_streak")
    drawdown = num("portfolio_drawdown_abs_pct")
    corr_max = num("same_direction_correlation_max_corr")
    corr_active = num("same_direction_correlation_active_count")
    risk_multiplier = num("risk_multiplier")
    selected_volume = num("selected_volume")
    rsi = num("rsi_value")
    breakout = num("breakout")
    bullish = num("bullish_alignment")
    bearish = num("bearish_alignment")
    entry_risk_pct = num("entry_risk_distance_pct_abs")
    mae_r = num("mae_r")
    mfe_r = num("mfe_r")
    r_multiple = num("r_multiple")

    aligned = (direction.eq("long") & bullish.eq(1)) | (direction.eq("short") & bearish.eq(1))
    not_aligned = direction.isin(["long", "short"]) & ~aligned
    rsi_exhaustion = (direction.eq("long") & rsi.ge(75)) | (direction.eq("short") & rsi.le(25))
    rsi_counter = (direction.eq("long") & rsi.le(45)) | (direction.eq("short") & rsi.ge(55))

    return [
        ("all_background_lots", "同 source/horizon 内全部 closed lots；只作基准", pd.Series(True, index=index), False),
        ("ai_rank_missing", "AI rank 缺失", ai_rank.isna(), True),
        ("ai_rank_gt8_or_missing", "AI rank >8 或缺失", ai_rank.gt(8) | ai_rank.isna(), True),
        ("ai_rank_le4", "AI rank <=4", ai_rank.le(4), True),
        ("ai_rank_5_to_8", "AI rank 5-8", ai_rank.ge(5) & ai_rank.le(8), True),
        ("ai_score_le0", "AI score <=0", ai_score.le(0), True),
        ("active_positions_ge3", "入场前活跃持仓 >=3", active.ge(3), True),
        ("active_positions_ge4", "入场前活跃持仓 >=4", active.ge(4), True),
        ("loss_streak_ge2", "入场前 loss_streak >=2", loss_streak.ge(2), True),
        ("loss_streak_ge3", "入场前 loss_streak >=3", loss_streak.ge(3), True),
        ("drawdown_abs_ge10", "入场前账户回撤绝对值 >=10%", drawdown.ge(10), True),
        ("drawdown_abs_ge20", "入场前账户回撤绝对值 >=20%", drawdown.ge(20), True),
        ("drawdown_ge10_active_ge3", "回撤 >=10% 且活跃持仓 >=3", drawdown.ge(10) & active.ge(3), True),
        ("same_direction_active_ge1", "同向相关 active count >=1", corr_active.ge(1), True),
        ("same_direction_max_corr_ge050", "同向最大相关性 >=0.50", corr_max.ge(0.50), True),
        ("risk_multiplier_ge2", "风险 multiplier >=2", risk_multiplier.ge(2), True),
        ("selected_volume_gt1", "selected_volume >1", selected_volume.gt(1), True),
        ("recovery_sleeve_applied", "recovery_sleeve_applied 为真", _bool_column(lots, "recovery_sleeve_applied"), True),
        (
            "streak_structure_recovery_applied",
            "streak_entry_structure_risk_recovery_applied 为真",
            _bool_column(lots, "streak_entry_structure_risk_recovery_applied"),
            True,
        ),
        ("not_directionally_aligned", "入场方向与均线方向未对齐", not_aligned, True),
        ("breakout_false", "breakout 为假", breakout.fillna(0).le(0), True),
        ("rsi_exhaustion_zone", "RSI 极端顺势区：long>=75 或 short<=25", rsi_exhaustion, True),
        ("rsi_counter_zone", "RSI 逆势区：long<=45 或 short>=55", rsi_counter, True),
        ("entry_risk_distance_ge5pct", "入场止损距离 >=5%", entry_risk_pct.ge(5), True),
        ("entry_risk_distance_ge8pct", "入场止损距离 >=8%", entry_risk_pct.ge(8), True),
        ("post_mae_le_minus1r", "事后 MAE <= -1R；只作路径标签，不可交易化", mae_r.le(-1), False),
        ("post_mfe_lt1r", "事后 MFE < 1R；只作路径标签，不可交易化", mfe_r.lt(1), False),
        ("post_closed_loser", "事后 R multiple <0；只作标签，不可交易化", r_multiple.lt(0), False),
    ]


def summarize_condition_table(
    background_lots: pd.DataFrame,
    *,
    min_population_count: int = DEFAULT_MIN_POPULATION_COUNT,
    min_source_count: int = DEFAULT_MIN_SOURCE_COUNT,
    min_loss_share_pct: float = DEFAULT_MIN_LOSS_SHARE_PCT,
    min_lift: float = DEFAULT_MIN_LIFT,
) -> pd.DataFrame:
    if background_lots.empty:
        return pd.DataFrame()
    total_count = len(background_lots)
    total_loss = float(pd.to_numeric(background_lots["allocated_window_holding_loss_abs"], errors="coerce").sum())
    rows: list[dict[str, Any]] = []
    for name, description, mask, candidate_eligible in _condition_masks(background_lots):
        mask = mask.fillna(False).astype(bool)
        subset = background_lots.loc[mask]
        population_count = int(len(subset))
        population_share = population_count / total_count * 100.0 if total_count else 0.0
        allocated_loss = float(pd.to_numeric(subset.get("allocated_window_holding_loss_abs"), errors="coerce").sum())
        loss_share = allocated_loss / total_loss * 100.0 if total_loss > 0 else 0.0
        lift = loss_share / population_share if population_share > 0 else np.nan
        exposed = subset.get("residual_exposed", pd.Series(False, index=subset.index)).astype(bool)
        loss_positive = pd.to_numeric(subset.get("allocated_window_holding_loss_abs"), errors="coerce").fillna(0.0).gt(0)
        source_count = int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0
        loss_source_count = (
            int(subset.loc[loss_positive, "requested_start_month"].nunique())
            if "requested_start_month" in subset.columns
            else 0
        )
        stable = (
            candidate_eligible
            and population_count >= min_population_count
            and source_count >= min_source_count
            and loss_source_count >= min_source_count
            and loss_share >= min_loss_share_pct
            and np.isfinite(lift)
            and lift >= min_lift
        )
        rows.append(
            {
                "condition": name,
                "description": description,
                "candidate_eligible": bool(candidate_eligible),
                "population_count": population_count,
                "population_share_pct": population_share,
                "source_count": source_count,
                "loss_source_count": loss_source_count,
                "date_count": int(subset["entry_date"].nunique()) if "entry_date" in subset.columns else 0,
                "loss_date_count": int(subset.loc[loss_positive, "entry_date"].nunique()) if "entry_date" in subset.columns else 0,
                "residual_exposed_lot_count": int(exposed.sum()),
                "residual_exposed_lot_rate_pct": float(exposed.mean() * 100.0) if population_count else 0.0,
                "residual_exposure_count_sum": int(
                    pd.to_numeric(subset.get("residual_exposure_count"), errors="coerce").fillna(0).sum()
                ),
                "allocated_holding_loss_abs": allocated_loss,
                "allocated_loss_share_pct": loss_share,
                "loss_lift_vs_population": float(lift) if np.isfinite(lift) else np.nan,
                "median_ai_rank": float(_numeric(subset, "ai_product_pool_rank").median()),
                "median_active_positions_before": float(_numeric(subset, "active_positions_before").median()),
                "median_drawdown_abs_pct": float(_numeric(subset, "portfolio_drawdown_abs_pct").median()),
                "median_same_direction_corr": float(_numeric(subset, "same_direction_correlation_max_corr").median()),
                "median_rsi": float(_numeric(subset, "rsi_value").median()),
                "stable_candidate": bool(stable),
            }
        )
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["stable_candidate", "loss_lift_vs_population", "allocated_loss_share_pct", "population_count"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def _weighted_mean(frame: pd.DataFrame, value_column: str, weight_column: str) -> float:
    if value_column not in frame.columns or weight_column not in frame.columns:
        return np.nan
    values = pd.to_numeric(frame[value_column], errors="coerce")
    weights = pd.to_numeric(frame[weight_column], errors="coerce")
    mask = values.notna() & weights.notna() & weights.gt(0)
    if not mask.any():
        return np.nan
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def summarize_numeric_features(background_lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    exposed = background_lots.get("residual_exposed", pd.Series(False, index=background_lots.index)).astype(bool)
    for column in [*PIT_NUMERIC_FEATURES, *POST_ENTRY_LABEL_FEATURES]:
        if column not in background_lots.columns:
            continue
        values = pd.to_numeric(background_lots[column], errors="coerce")
        if values.notna().sum() < 20:
            continue
        exposed_values = values[exposed].dropna()
        non_exposed_values = values[~exposed].dropna()
        population_mean = float(values.mean())
        exposed_mean = float(exposed_values.mean()) if len(exposed_values) else np.nan
        non_exposed_mean = float(non_exposed_values.mean()) if len(non_exposed_values) else np.nan
        loss_weighted_mean = _weighted_mean(background_lots, column, "allocated_window_holding_loss_abs")
        rows.append(
            {
                "feature": column,
                "is_entry_visible": column in PIT_NUMERIC_FEATURES,
                "population_non_null_count": int(values.notna().sum()),
                "exposed_non_null_count": int(exposed_values.notna().sum()),
                "population_mean": population_mean,
                "exposed_mean": exposed_mean,
                "non_exposed_mean": non_exposed_mean,
                "loss_weighted_mean": loss_weighted_mean,
                "loss_weighted_minus_population": loss_weighted_mean - population_mean
                if np.isfinite(loss_weighted_mean) and np.isfinite(population_mean)
                else np.nan,
                "population_median": float(values.median()),
                "exposed_median": float(exposed_values.median()) if len(exposed_values) else np.nan,
                "loss_weighted_vs_population_abs": abs(loss_weighted_mean - population_mean)
                if np.isfinite(loss_weighted_mean) and np.isfinite(population_mean)
                else np.nan,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["is_entry_visible", "loss_weighted_vs_population_abs"],
        ascending=[False, False],
    ).reset_index(drop=True)


def summarize_product_direction(entry_exposures: pd.DataFrame) -> pd.DataFrame:
    if entry_exposures.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    total_loss = float(pd.to_numeric(entry_exposures["allocated_window_holding_loss_abs"], errors="coerce").sum())
    for (product, direction), group in entry_exposures.groupby(["product", "direction"], dropna=False):
        loss = float(pd.to_numeric(group["allocated_window_holding_loss_abs"], errors="coerce").sum())
        rows.append(
            {
                "product": product,
                "direction": direction,
                "entry_exposure_rows": int(len(group)),
                "unique_lot_count": int(group["lot_key"].nunique()),
                "source_count": int(group["requested_start_month"].nunique()),
                "entry_date_count": int(group["entry_date"].nunique()),
                "allocated_holding_loss_abs": loss,
                "allocated_loss_share_pct": loss / total_loss * 100.0 if total_loss > 0 else 0.0,
                "loss_weighted_ai_rank": _weighted_mean(group, "ai_product_pool_rank", "allocated_window_holding_loss_abs"),
                "loss_weighted_active_positions_before": _weighted_mean(
                    group, "active_positions_before", "allocated_window_holding_loss_abs"
                ),
                "loss_weighted_drawdown_abs_pct": _weighted_mean(
                    group, "portfolio_drawdown_abs_pct", "allocated_window_holding_loss_abs"
                ),
                "loss_weighted_rsi": _weighted_mean(group, "rsi_value", "allocated_window_holding_loss_abs"),
                "loss_weighted_mae_r": _weighted_mean(group, "mae_r", "allocated_window_holding_loss_abs"),
            }
        )
    return pd.DataFrame(rows).sort_values("allocated_holding_loss_abs", ascending=False).reset_index(drop=True)


def make_decision(
    window_rows: pd.DataFrame,
    entry_exposures: pd.DataFrame,
    unmatched_windows: pd.DataFrame,
    background_lots: pd.DataFrame,
    condition_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
) -> dict[str, Any]:
    matched_loss = float(pd.to_numeric(entry_exposures.get("allocated_window_holding_loss_abs"), errors="coerce").sum())
    unmatched_loss = (
        float(pd.to_numeric(unmatched_windows.get("window_holding_loss_abs"), errors="coerce").sum())
        if not unmatched_windows.empty
        else 0.0
    )
    total_window_loss = matched_loss + unmatched_loss
    matched_loss_share = matched_loss / total_window_loss * 100.0 if total_window_loss > 0 else 0.0
    stable = (
        condition_summary[
            condition_summary.get("stable_candidate", pd.Series(False, index=condition_summary.index)).astype(bool)
            & condition_summary.get("candidate_eligible", pd.Series(False, index=condition_summary.index)).astype(bool)
        ].copy()
        if not condition_summary.empty
        else pd.DataFrame()
    )
    if total_window_loss <= 0 or entry_exposures.empty:
        decision = "stage007_no_entry_exposure_match_do_not_trade"
        reason = "Stage006 新开/交易仓亏损行没有映射到 Stage019 closed lots，不能据此做入场状态判断。"
    elif matched_loss_share < 95.0:
        decision = "stage007_entry_exposure_mapping_incomplete_readonly"
        reason = "Stage006 持仓亏损与 Stage019 入场批次映射覆盖不足，当前只能作部分样本审计。"
    elif not stable.empty:
        decision = "stage007_has_pit_entry_state_candidates_need_true_engine_ab"
        reason = "存在满足样本、跨 source、亏损占比和 lift 门槛的入场前状态条件；下一步只能进真实引擎 A/B，不能直接改正式版。"
    else:
        decision = "stage007_no_stable_pit_entry_state_candidate_stop_window_mining"
        reason = "没有稳定的非品种黑名单、入场前可见低质量条件；继续在同一批亏损窗口挖规则会偏过拟合。"

    top_conditions = stable["condition"].head(10).tolist() if not stable.empty else []
    worst_product_direction = product_direction_summary.head(10).to_dict("records") if not product_direction_summary.empty else []
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_paths": {
            "stage006_window_detail": str(STAGE006_WINDOW_DETAIL_PATH.relative_to(PROJECT_DIR)),
            "stage019_closed_lots": str(STAGE019_CLOSED_LOTS_PATH.relative_to(PROJECT_DIR)),
        },
        "output_paths": {
            "entry_exposures": str(ENTRY_EXPOSURES_PATH.relative_to(PROJECT_DIR)),
            "background_lots": str(BACKGROUND_LOTS_PATH.relative_to(PROJECT_DIR)),
            "unmatched_windows": str(UNMATCHED_WINDOWS_PATH.relative_to(PROJECT_DIR)),
            "condition_summary": str(CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "numeric_feature_summary": str(NUMERIC_FEATURE_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "chart": str(CHART_PATH.relative_to(PROJECT_DIR)),
            "report": str(REPORT_PATH.relative_to(PROJECT_DIR)),
            "decision": str(DECISION_PATH.relative_to(PROJECT_DIR)),
        },
        "analysis_scope": {
            "window_loss_rows": int(len(window_rows)),
            "window_count": int(window_rows["window_id"].nunique()) if not window_rows.empty else 0,
            "source_count": int(window_rows["source_start_month"].nunique()) if not window_rows.empty else 0,
            "entry_exposure_rows": int(len(entry_exposures)),
            "unique_exposed_lots": int(entry_exposures["lot_key"].nunique()) if not entry_exposures.empty else 0,
            "background_lots": int(len(background_lots)),
            "background_exposed_lots": int(background_lots["residual_exposed"].sum()) if not background_lots.empty else 0,
            "matched_holding_loss_abs": matched_loss,
            "unmatched_holding_loss_abs": unmatched_loss,
            "matched_holding_loss_share_pct": matched_loss_share,
        },
        "candidate_thresholds": {
            "min_population_count": DEFAULT_MIN_POPULATION_COUNT,
            "min_source_count": DEFAULT_MIN_SOURCE_COUNT,
            "min_loss_share_pct": DEFAULT_MIN_LOSS_SHARE_PCT,
            "min_lift": DEFAULT_MIN_LIFT,
        },
        "stable_candidate_conditions": top_conditions,
        "worst_product_direction_readonly": _json_safe(worst_product_direction),
        "decision": decision,
        "decision_reason": reason,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _write_chart(condition_summary: pd.DataFrame) -> None:
    if condition_summary.empty:
        return
    shown = condition_summary[
        condition_summary["candidate_eligible"].astype(bool) & condition_summary["population_count"].ge(20)
    ].copy()
    if shown.empty:
        return
    shown = shown.sort_values("loss_lift_vs_population", ascending=False).head(16).sort_values("loss_lift_vs_population")
    colors = np.where(shown["stable_candidate"].astype(bool), "#c0392b", "#4c78a8")
    plt.figure(figsize=(12, 7))
    plt.barh(shown["condition"], shown["loss_lift_vs_population"], color=colors)
    plt.axvline(1.0, color="#555555", linewidth=1)
    plt.axvline(DEFAULT_MIN_LIFT, color="#c0392b", linestyle="--", linewidth=1)
    plt.xlabel("Allocated holding-loss share / population share")
    plt.ylabel("Entry-visible condition")
    plt.title("Stage007 PIT Entry-State Loss Lift")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=180)
    plt.close()


def _write_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    numeric_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
) -> None:
    scope = decision["analysis_scope"]
    stable = condition_summary.loc[condition_summary["stable_candidate"].astype(bool)] if not condition_summary.empty else pd.DataFrame()
    eligible_top = (
        condition_summary.loc[condition_summary["candidate_eligible"].astype(bool)].head(18)
        if not condition_summary.empty
        else pd.DataFrame()
    )
    text = f"""# Stage007 新增/交易仓入场状态审计

- line_id：`{LINE_ID}`
- 阶段：`{STAGE}`
- 生成时间：`{decision['generated_at']}`
- 性质：只读归因；不改策略、不改实盘配置、不连接 CTP、不调用下单。

## 外部调研与判断

- pysystemtrade / Rob Carver 系统化交易框架强调 futures 策略要把 forecast、position sizing、组合风险和成本拆开看；本阶段采用这个拆分，不把产品方向归因直接变成交易黑名单。
- Machine Learning for Trading 的研究流程强调时间序列回测要避免 look-ahead contamination；本阶段只把 `AI rank/score、账户状态、相关性、RSI/突破/均线对齐` 等入场日前可见字段列为候选条件。
- Trend-following 资料普遍提示 whipsaw/drawdown 是趋势策略的结构性成本；本阶段把 MAE/MFE/R multiple 只作事后路径标签，不纳入可交易候选。
- 我的判断：Stage006 已显示残余主要来自窗口后新增/交易仓，本阶段要回答“这些新仓在入场时是否已经有可预声明的低质量状态”，而不是继续扫 Stage074 ramp 或 AI topN 参数。

## 口径

- 输入：Stage006 `window_position_detail` 中 `opened_or_traded_after_window_start` 且 holding pnl 为负的 product/direction/window 行；Stage019 `stage013_rebuilt_closed_lots` 的入场批次特征。
- 映射：同 `requested_start_month/source_start_month`、同 `product`、同 `direction`，且 `entry_date > window_start_date`、`entry_date <= window_end_date`。
- 权重：一个 Stage006 window/product/direction 的 holding loss 按匹配到的 closed lots 等权分摊；这是“窗口-入场暴露”审计，不是逐笔 PnL 复盘。
- 背景样本：同 source 的 first residual window start 到 last residual window end 之间全部 closed lots，用来计算条件 population share。
- 严格限制：product/direction 只作解释表，不作为候选条件；事后 MAE/MFE/R multiple 只作标签，不作为交易条件。

## 总览

- window loss rows：`{scope['window_loss_rows']}`
- window 数：`{scope['window_count']}`
- source 数：`{scope['source_count']}`
- entry exposure rows：`{scope['entry_exposure_rows']}`
- unique exposed lots：`{scope['unique_exposed_lots']}`
- background lots：`{scope['background_lots']}`
- matched holding loss：`{scope['matched_holding_loss_abs']:,.4f}`
- unmatched holding loss：`{scope['unmatched_holding_loss_abs']:,.4f}`
- matched holding loss share：`{scope['matched_holding_loss_share_pct']:.4f}%`
- 决策：`{decision['decision']}`
- 理由：{decision['decision_reason']}

## 满足晋级门槛的入场前条件

{_md_table(stable, max_rows=20)}

## 入场前条件 lift

{_md_table(eligible_top, max_rows=18)}

## 数值特征差异

{_md_table(numeric_summary.head(18), max_rows=18)}

## 产品方向归因（只读解释，不能黑名单）

{_md_table(product_direction_summary.head(20), max_rows=20)}

## 结论

- 如果 stable candidate 非空，下一步只能写冻结真实引擎 A/B：保持 AI 月池、止损重试、保证金、整数手和交易成本逻辑不变，只验证这个入场前条件是否改善全路径目标。
- 如果 stable candidate 为空，应停止继续从同一批亏损窗口挖规则，转向更外生的数据源或账户层生存机制。
- 本阶段没有改变任何线上/实盘逻辑。

## 过拟合反思

- 运行前判断：有过拟合风险，因为标签来自已知残余亏损窗口。
- 运行后判断：`{decision['decision']}`。
- 原因：本阶段设置了跨 source、样本数、亏损占比和 lift 门槛，并排除了 product/direction 黑名单和事后路径字段；但只要要交易化，仍必须通过真实引擎多起点验证。

## 继续价值反思

- 运行前判断：有价值，因为 Stage006 已把问题定位到窗口后新增/交易仓。
- 运行后判断：{decision['decision_reason']}
- 下一步：按上述决策进入真实引擎候选验证，或停止本窗口挖掘路线。

## 输出文件

- entry exposures：`{ENTRY_EXPOSURES_PATH.relative_to(PROJECT_DIR)}`
- background lots：`{BACKGROUND_LOTS_PATH.relative_to(PROJECT_DIR)}`
- condition summary：`{CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- numeric feature summary：`{NUMERIC_FEATURE_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- product direction summary：`{PRODUCT_DIRECTION_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- chart：`{CHART_PATH.relative_to(PROJECT_DIR)}`
- decision：`{DECISION_PATH.relative_to(PROJECT_DIR)}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    window_detail = _read_csv(STAGE006_WINDOW_DETAIL_PATH)
    closed_lots_raw = _read_csv(STAGE019_CLOSED_LOTS_PATH)
    window_rows = prepare_window_loss_rows(window_detail)
    closed_lots = prepare_closed_lots(closed_lots_raw)
    entry_exposures, unmatched_windows = match_entry_exposures(window_rows, closed_lots)
    background_scope = build_background_lots(closed_lots, window_rows)
    background_lots = attach_exposure_weights(background_scope, entry_exposures)

    condition_summary = summarize_condition_table(background_lots)
    numeric_summary = summarize_numeric_features(background_lots)
    product_direction_summary = summarize_product_direction(entry_exposures)
    decision = make_decision(
        window_rows,
        entry_exposures,
        unmatched_windows,
        background_lots,
        condition_summary,
        product_direction_summary,
    )

    entry_exposures.to_csv(ENTRY_EXPOSURES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    background_lots.to_csv(BACKGROUND_LOTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    unmatched_windows.to_csv(UNMATCHED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    numeric_summary.to_csv(NUMERIC_FEATURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_direction_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_chart(condition_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, condition_summary, numeric_summary, product_direction_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
