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
STAGE = "Stage025"
MODEL_TAG = "stage025_stage024_opened_entry_state_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage025_stage024_opened_entry_state_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage025_stage024_opened_entry_state_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE024_OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_stage022_base_position_attribution"
STAGE024_PREFIX = "rebuilt_c9_v2_stage024_stage022_base_position_attribution"
STAGE024_TAG = "stage024_stage022_base_position_attribution_v1"
STAGE024_WINDOW_DETAIL_PATH = (
    STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_window_position_detail_{STAGE024_TAG}.csv.gz"
)

STAGE019_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE019_CLOSED_LOTS_PATH = (
    STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
)

STAGE022_OUTPUT_DIR = LINE_DIR / "outputs" / "stage022_xsmom_entry_confirmation_proxy"
STAGE022_PREFIX = "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy"
STAGE022_TAG = "stage022_xsmom_entry_confirmation_proxy_v1"
STAGE022_TAGGED_EVENTS_PATH = STAGE022_OUTPUT_DIR / f"{STAGE022_PREFIX}_tagged_events_{STAGE022_TAG}.csv.gz"

ENTRY_EXPOSURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exposures_{MODEL_TAG}.csv.gz"
BACKGROUND_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_background_lots_{MODEL_TAG}.csv.gz"
UNMATCHED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unmatched_window_rows_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
NUMERIC_FEATURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_feature_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
TAG_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage022_tag_coverage_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_loss_lift_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0639_stage025_stage024_opened_entry_state_audit.md"

DEFAULT_MIN_POPULATION_COUNT = 20
DEFAULT_MIN_SOURCE_COUNT = 2
DEFAULT_MIN_NET_LOSS_SHARE_PCT = 10.0
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
    "xsmom12_active",
    "xsmom12_covered",
    "xsmom12_aligned",
    "xsmom12_opposed",
    "xsmom12_not_opposed",
    "xsmom6_active",
    "xsmom6_covered",
    "xsmom6_aligned",
    "xsmom6_opposed",
    "xsmom6_not_opposed",
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
    data["product"] = data["product"].astype(str)
    data["direction"] = data["direction"].astype(str).str.lower()
    for column in [
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "cost",
        "net_pnl",
        "active_days",
        "contract_count",
        "trade_count",
        "max_abs_end_pos",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    scoped = data[
        data["source_bucket"].astype(str).eq("opened_or_traded_after_window_start")
        & data["direction"].isin(["long", "short"])
        & data["window_start_date"].notna()
        & data["window_end_date"].notna()
        & _numeric(data, "net_pnl", 0.0).lt(0.0)
    ].copy()
    scoped = scoped.sort_values(
        ["source_start_month", "window_start_date", "window_end_date", "product", "direction"]
    ).reset_index(drop=True)
    scoped["window_row_id"] = np.arange(len(scoped), dtype=int)
    scoped["window_net_loss_abs"] = scoped["net_pnl"].clip(upper=0.0).abs()
    scoped["window_holding_loss_abs"] = scoped["holding_pnl"].clip(upper=0.0).abs()
    return scoped


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


def attach_stage022_tags(closed_lots: pd.DataFrame, tagged_events: pd.DataFrame) -> pd.DataFrame:
    tagged = prepare_closed_lots(tagged_events)
    tag_columns = [
        column
        for column in tagged.columns
        if column == "lot_key" or column.startswith("xsmom12_") or column.startswith("xsmom6_")
    ]
    if len(tag_columns) <= 1:
        return closed_lots.copy()
    tags = tagged[tag_columns].drop_duplicates("lot_key")
    result = closed_lots.merge(tags, on="lot_key", how="left", suffixes=("", "_stage022"))
    for column in [item for item in tag_columns if item != "lot_key"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


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
        key = (str(row["source_start_month"]), str(row["product"]), str(row["direction"]).lower())
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
        matched["window_holding_pnl"] = float(row.get("holding_pnl", np.nan))
        matched["window_trading_pnl"] = float(row.get("trading_pnl", np.nan))
        matched["window_net_pnl"] = float(row.get("net_pnl", np.nan))
        matched["window_holding_loss_abs"] = float(row["window_holding_loss_abs"])
        matched["window_net_loss_abs"] = float(row["window_net_loss_abs"])
        matched["matched_lot_count"] = int(count)
        matched["allocated_window_holding_loss_abs"] = float(row["window_holding_loss_abs"]) / count
        matched["allocated_window_net_loss_abs"] = float(row["window_net_loss_abs"]) / count
        exposure_frames.append(matched)
    exposures = pd.concat(exposure_frames, ignore_index=True, sort=False) if exposure_frames else pd.DataFrame()
    unmatched = pd.DataFrame(unmatched_rows)
    return exposures, unmatched


def build_background_lots(closed_lots: pd.DataFrame, window_rows: pd.DataFrame) -> pd.DataFrame:
    if window_rows.empty:
        return closed_lots.iloc[0:0].copy()
    frames: list[pd.DataFrame] = []
    for _, row in window_rows.iterrows():
        mask = (
            closed_lots["requested_start_month"].astype(str).eq(str(row["source_start_month"]))
            & closed_lots["entry_date"].gt(row["window_start_date"])
            & closed_lots["entry_date"].le(row["window_end_date"])
        )
        frames.append(closed_lots.loc[mask])
    if not frames:
        return closed_lots.iloc[0:0].copy()
    scoped = pd.concat(frames, ignore_index=True, sort=False)
    scoped = scoped.drop_duplicates("lot_key").reset_index(drop=True)
    return scoped[scoped["direction"].isin(["long", "short"])].reset_index(drop=True)


def attach_exposure_weights(background_lots: pd.DataFrame, entry_exposures: pd.DataFrame) -> pd.DataFrame:
    background = background_lots.copy()
    if entry_exposures.empty:
        background["residual_exposure_count"] = 0
        background["allocated_window_holding_loss_abs"] = 0.0
        background["allocated_window_net_loss_abs"] = 0.0
        background["residual_exposed"] = False
        return background
    exposure_summary = (
        entry_exposures.groupby("lot_key", dropna=False)
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
    x12_active = num("xsmom12_active").eq(1)
    x12_aligned = num("xsmom12_aligned").eq(1)
    x12_opposed = num("xsmom12_opposed").eq(1)
    x12_not_opposed = num("xsmom12_not_opposed").eq(1)
    x6_aligned = num("xsmom6_aligned").eq(1)
    x6_opposed = num("xsmom6_opposed").eq(1)
    x6_not_opposed = num("xsmom6_not_opposed").eq(1)

    aligned_ma = (direction.eq("long") & bullish.eq(1)) | (direction.eq("short") & bearish.eq(1))
    not_aligned_ma = direction.isin(["long", "short"]) & ~aligned_ma
    rsi_exhaustion = (direction.eq("long") & rsi.ge(75)) | (direction.eq("short") & rsi.le(25))
    rsi_counter = (direction.eq("long") & rsi.le(45)) | (direction.eq("short") & rsi.ge(55))
    quality = ai_rank.ge(1) & ai_rank.le(8) & selected_volume.gt(1)
    guarded = quality & risk_multiplier.lt(2)

    return [
        ("all_background_lots", "同 source/window horizon 内全部 closed lots；只作基准", pd.Series(True, index=index), False),
        ("ai_rank_1_8", "AI rank 1-8", ai_rank.ge(1) & ai_rank.le(8), True),
        ("ai_rank_1_4", "AI rank 1-4", ai_rank.ge(1) & ai_rank.le(4), True),
        ("ai_rank_5_8", "AI rank 5-8", ai_rank.ge(5) & ai_rank.le(8), True),
        ("selected_volume_gt1", "selected_volume >1", selected_volume.gt(1), True),
        ("ai_rank_1_8_and_selected_volume_gt1", "AI rank 1-8 且 selected_volume>1", quality, True),
        ("guarded_quality_risk_lt2", "AI rank 1-8、selected_volume>1 且 risk_multiplier<2", guarded, True),
        ("risk_multiplier_ge2", "risk_multiplier >=2", risk_multiplier.ge(2), True),
        ("risk_multiplier_lt2", "risk_multiplier <2", risk_multiplier.lt(2), True),
        ("active_positions_ge3", "入场前活跃持仓 >=3", active.ge(3), True),
        ("active_positions_ge4", "入场前活跃持仓 >=4", active.ge(4), True),
        ("loss_streak_ge2", "入场前 loss_streak >=2", loss_streak.ge(2), True),
        ("drawdown_abs_ge10", "入场前账户回撤绝对值 >=10%", drawdown.ge(10), True),
        ("same_direction_active_ge1", "同向相关 active count >=1", corr_active.ge(1), True),
        ("same_direction_max_corr_ge050", "同向最大相关性 >=0.50", corr_max.ge(0.50), True),
        ("not_ma_directionally_aligned", "入场方向与均线方向未对齐", not_aligned_ma, True),
        ("breakout_false", "breakout 为假", breakout.fillna(0).le(0), True),
        ("rsi_exhaustion_zone", "RSI 极端顺势区：long>=75 或 short<=25", rsi_exhaustion, True),
        ("rsi_counter_zone", "RSI 逆势区：long<=45 或 short>=55", rsi_counter, True),
        ("xsmom12_active", "前一交易日 12-1m xsmom 有可用横截面", x12_active, False),
        ("xsmom12_aligned", "前一交易日 12-1m xsmom 与入场方向一致", x12_aligned, True),
        ("xsmom12_not_opposed", "前一交易日 12-1m xsmom 未反向", x12_not_opposed, True),
        ("xsmom12_opposed", "前一交易日 12-1m xsmom 反向", x12_opposed, True),
        ("xsmom6_aligned", "前一交易日 6-1m xsmom 与入场方向一致", x6_aligned, True),
        ("xsmom6_not_opposed", "前一交易日 6-1m xsmom 未反向", x6_not_opposed, True),
        ("xsmom6_opposed", "前一交易日 6-1m xsmom 反向", x6_opposed, True),
        (
            "guarded_quality_xsmom12_not_opposed",
            "guarded quality 且 12-1m xsmom 未反向",
            guarded & x12_not_opposed,
            True,
        ),
        (
            "guarded_quality_xsmom12_aligned",
            "guarded quality 且 12-1m xsmom 一致",
            guarded & x12_aligned,
            True,
        ),
        (
            "guarded_quality_xsmom6_not_opposed",
            "guarded quality 且 6-1m xsmom 未反向",
            guarded & x6_not_opposed,
            True,
        ),
    ]


def summarize_condition_table(
    background_lots: pd.DataFrame,
    *,
    min_population_count: int = DEFAULT_MIN_POPULATION_COUNT,
    min_source_count: int = DEFAULT_MIN_SOURCE_COUNT,
    min_loss_share_pct: float = DEFAULT_MIN_NET_LOSS_SHARE_PCT,
    min_lift: float = DEFAULT_MIN_LIFT,
) -> pd.DataFrame:
    if background_lots.empty:
        return pd.DataFrame()
    total_count = len(background_lots)
    total_net_loss = float(pd.to_numeric(background_lots["allocated_window_net_loss_abs"], errors="coerce").sum())
    total_holding_loss = float(pd.to_numeric(background_lots["allocated_window_holding_loss_abs"], errors="coerce").sum())
    rows: list[dict[str, Any]] = []
    for name, description, mask, candidate_eligible in _condition_masks(background_lots):
        mask = mask.reindex(background_lots.index).fillna(False).astype(bool)
        subset = background_lots.loc[mask]
        population_count = int(len(subset))
        population_share = population_count / total_count * 100.0 if total_count else 0.0
        net_loss = float(pd.to_numeric(subset.get("allocated_window_net_loss_abs"), errors="coerce").sum())
        holding_loss = float(pd.to_numeric(subset.get("allocated_window_holding_loss_abs"), errors="coerce").sum())
        net_loss_share = net_loss / total_net_loss * 100.0 if total_net_loss > 0 else 0.0
        holding_loss_share = holding_loss / total_holding_loss * 100.0 if total_holding_loss > 0 else 0.0
        lift = net_loss_share / population_share if population_share > 0 else np.nan
        source_count = int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0
        net_loss_positive = pd.to_numeric(subset.get("allocated_window_net_loss_abs"), errors="coerce").fillna(0.0).gt(0)
        loss_source_count = (
            int(subset.loc[net_loss_positive, "requested_start_month"].nunique())
            if "requested_start_month" in subset.columns
            else 0
        )
        exposed = subset.get("residual_exposed", pd.Series(False, index=subset.index)).astype(bool)
        stable = (
            candidate_eligible
            and population_count >= min_population_count
            and source_count >= min_source_count
            and loss_source_count >= min_source_count
            and net_loss_share >= min_loss_share_pct
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
                "residual_exposed_lot_count": int(exposed.sum()),
                "residual_exposed_lot_rate_pct": float(exposed.mean() * 100.0) if population_count else 0.0,
                "residual_exposure_count_sum": int(
                    pd.to_numeric(subset.get("residual_exposure_count"), errors="coerce").fillna(0).sum()
                ),
                "allocated_net_loss_abs": net_loss,
                "allocated_net_loss_share_pct": net_loss_share,
                "allocated_holding_loss_abs": holding_loss,
                "allocated_holding_loss_share_pct": holding_loss_share,
                "net_loss_lift_vs_population": float(lift) if np.isfinite(lift) else np.nan,
                "realized_pnl_sum": float(pd.to_numeric(subset.get("realized_pnl"), errors="coerce").sum()),
                "realized_pnl_mean": float(pd.to_numeric(subset.get("realized_pnl"), errors="coerce").mean()),
                "median_ai_rank": float(_numeric(subset, "ai_product_pool_rank").median()),
                "median_selected_volume": float(_numeric(subset, "selected_volume").median()),
                "median_risk_multiplier": float(_numeric(subset, "risk_multiplier").median()),
                "median_active_positions_before": float(_numeric(subset, "active_positions_before").median()),
                "median_drawdown_abs_pct": float(_numeric(subset, "portfolio_drawdown_abs_pct").median()),
                "median_rsi": float(_numeric(subset, "rsi_value").median()),
                "stable_candidate": bool(stable),
            }
        )
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["stable_candidate", "net_loss_lift_vs_population", "allocated_net_loss_share_pct", "population_count"],
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
        if values.notna().sum() < 10:
            continue
        exposed_values = values[exposed].dropna()
        non_exposed_values = values[~exposed].dropna()
        population_mean = float(values.mean())
        exposed_mean = float(exposed_values.mean()) if len(exposed_values) else np.nan
        non_exposed_mean = float(non_exposed_values.mean()) if len(non_exposed_values) else np.nan
        net_loss_weighted_mean = _weighted_mean(background_lots, column, "allocated_window_net_loss_abs")
        rows.append(
            {
                "feature": column,
                "is_entry_visible": column in PIT_NUMERIC_FEATURES,
                "population_non_null_count": int(values.notna().sum()),
                "exposed_non_null_count": int(exposed_values.notna().sum()),
                "population_mean": population_mean,
                "exposed_mean": exposed_mean,
                "non_exposed_mean": non_exposed_mean,
                "net_loss_weighted_mean": net_loss_weighted_mean,
                "net_loss_weighted_minus_population": net_loss_weighted_mean - population_mean
                if np.isfinite(net_loss_weighted_mean) and np.isfinite(population_mean)
                else np.nan,
                "population_median": float(values.median()),
                "exposed_median": float(exposed_values.median()) if len(exposed_values) else np.nan,
                "net_loss_weighted_vs_population_abs": abs(net_loss_weighted_mean - population_mean)
                if np.isfinite(net_loss_weighted_mean) and np.isfinite(population_mean)
                else np.nan,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["is_entry_visible", "net_loss_weighted_vs_population_abs"],
        ascending=[False, False],
    ).reset_index(drop=True)


def summarize_product_direction(entry_exposures: pd.DataFrame) -> pd.DataFrame:
    if entry_exposures.empty:
        return pd.DataFrame()
    total_net_loss = float(pd.to_numeric(entry_exposures["allocated_window_net_loss_abs"], errors="coerce").sum())
    rows: list[dict[str, Any]] = []
    for (product, direction), group in entry_exposures.groupby(["product", "direction"], dropna=False):
        net_loss = float(pd.to_numeric(group["allocated_window_net_loss_abs"], errors="coerce").sum())
        holding_loss = float(pd.to_numeric(group["allocated_window_holding_loss_abs"], errors="coerce").sum())
        rows.append(
            {
                "product": product,
                "direction": direction,
                "entry_exposure_rows": int(len(group)),
                "unique_lot_count": int(group["lot_key"].nunique()),
                "source_count": int(group["requested_start_month"].nunique()),
                "entry_date_count": int(group["entry_date"].nunique()),
                "allocated_net_loss_abs": net_loss,
                "allocated_net_loss_share_pct": net_loss / total_net_loss * 100.0 if total_net_loss > 0 else 0.0,
                "allocated_holding_loss_abs": holding_loss,
                "realized_pnl_sum": float(pd.to_numeric(group.get("realized_pnl"), errors="coerce").sum()),
                "net_loss_weighted_ai_rank": _weighted_mean(group, "ai_product_pool_rank", "allocated_window_net_loss_abs"),
                "net_loss_weighted_selected_volume": _weighted_mean(group, "selected_volume", "allocated_window_net_loss_abs"),
                "net_loss_weighted_risk_multiplier": _weighted_mean(group, "risk_multiplier", "allocated_window_net_loss_abs"),
                "net_loss_weighted_rsi": _weighted_mean(group, "rsi_value", "allocated_window_net_loss_abs"),
            }
        )
    return pd.DataFrame(rows).sort_values("allocated_net_loss_abs", ascending=False).reset_index(drop=True)


def build_tag_coverage(background_lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = len(background_lots)
    for column in ["xsmom12_covered", "xsmom12_active", "xsmom6_covered", "xsmom6_active"]:
        if column not in background_lots.columns:
            rows.append({"tag": column, "non_null_count": 0, "true_count": 0, "true_rate_pct": 0.0})
            continue
        values = pd.to_numeric(background_lots[column], errors="coerce")
        rows.append(
            {
                "tag": column,
                "non_null_count": int(values.notna().sum()),
                "true_count": int(values.fillna(0).eq(1).sum()),
                "true_rate_pct": float(values.fillna(0).eq(1).mean() * 100.0) if total else 0.0,
            }
        )
    return pd.DataFrame(rows)


def make_decision(
    window_rows: pd.DataFrame,
    entry_exposures: pd.DataFrame,
    unmatched_windows: pd.DataFrame,
    background_lots: pd.DataFrame,
    condition_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
    tag_coverage: pd.DataFrame,
) -> dict[str, Any]:
    matched_net_loss = float(pd.to_numeric(entry_exposures.get("allocated_window_net_loss_abs"), errors="coerce").sum())
    unmatched_net_loss = (
        float(pd.to_numeric(unmatched_windows.get("window_net_loss_abs"), errors="coerce").sum())
        if not unmatched_windows.empty
        else 0.0
    )
    total_net_loss = matched_net_loss + unmatched_net_loss
    matched_net_loss_share = matched_net_loss / total_net_loss * 100.0 if total_net_loss > 0 else 0.0
    stable = (
        condition_summary[
            condition_summary.get("stable_candidate", pd.Series(False, index=condition_summary.index)).astype(bool)
            & condition_summary.get("candidate_eligible", pd.Series(False, index=condition_summary.index)).astype(bool)
        ].copy()
        if not condition_summary.empty
        else pd.DataFrame()
    )
    if total_net_loss <= 0 or entry_exposures.empty:
        decision = "stage025_no_entry_exposure_match_do_not_trade"
        reason = "Stage024 opened/traded 负净损失行没有映射到 closed lots，不能据此做入场状态判断。"
    elif matched_net_loss_share < 95.0:
        decision = "stage025_entry_exposure_mapping_incomplete_readonly"
        reason = "Stage024 opened/traded 负净损失与 closed lots 映射覆盖不足，当前只能作部分样本审计。"
    elif not stable.empty:
        decision = "stage025_opened_entry_states_have_loss_concentration_candidates_need_true_guard_or_quality_split"
        reason = "存在跨 source、入场前可见条件，其 lot 占比低于净亏损占比且 lift 达标；只能作为下一步真实 guard/质量拆分假设，不能直接上线。"
    else:
        decision = "stage025_no_stable_pit_entry_loss_state_candidate_stop_window_mining"
        reason = "没有稳定、入场前可见、非黑名单式的损失集中条件；继续在这些窗口挖规则会偏过拟合。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_paths": {
            "stage024_window_detail": str(STAGE024_WINDOW_DETAIL_PATH.relative_to(PROJECT_DIR)),
            "stage019_closed_lots": str(STAGE019_CLOSED_LOTS_PATH.relative_to(PROJECT_DIR)),
            "stage022_tagged_events": str(STAGE022_TAGGED_EVENTS_PATH.relative_to(PROJECT_DIR)),
        },
        "output_paths": {
            "entry_exposures": str(ENTRY_EXPOSURES_PATH.relative_to(PROJECT_DIR)),
            "background_lots": str(BACKGROUND_LOTS_PATH.relative_to(PROJECT_DIR)),
            "unmatched_windows": str(UNMATCHED_WINDOWS_PATH.relative_to(PROJECT_DIR)),
            "condition_summary": str(CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "numeric_feature_summary": str(NUMERIC_FEATURE_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "tag_coverage": str(TAG_COVERAGE_PATH.relative_to(PROJECT_DIR)),
            "chart": str(CHART_PATH.relative_to(PROJECT_DIR)),
            "report": str(REPORT_PATH.relative_to(PROJECT_DIR)),
            "stage_record": str(STAGE_RECORD_PATH.relative_to(PROJECT_DIR)),
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
            "matched_net_loss_abs": matched_net_loss,
            "unmatched_net_loss_abs": unmatched_net_loss,
            "matched_net_loss_share_pct": matched_net_loss_share,
            "matched_holding_loss_abs": float(
                pd.to_numeric(entry_exposures.get("allocated_window_holding_loss_abs"), errors="coerce").sum()
            ),
        },
        "candidate_thresholds": {
            "min_population_count": DEFAULT_MIN_POPULATION_COUNT,
            "min_source_count": DEFAULT_MIN_SOURCE_COUNT,
            "min_net_loss_share_pct": DEFAULT_MIN_NET_LOSS_SHARE_PCT,
            "min_lift": DEFAULT_MIN_LIFT,
        },
        "stable_candidate_conditions": stable["condition"].head(10).tolist() if not stable.empty else [],
        "top_loss_condition_readonly": _json_safe(condition_summary.head(10).to_dict("records"))
        if not condition_summary.empty
        else [],
        "worst_product_direction_readonly": _json_safe(product_direction_summary.head(10).to_dict("records"))
        if not product_direction_summary.empty
        else [],
        "tag_coverage": _json_safe(tag_coverage.to_dict("records")) if not tag_coverage.empty else [],
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


def write_condition_chart(condition_summary: pd.DataFrame) -> None:
    if condition_summary.empty:
        return
    shown = condition_summary[
        condition_summary["condition"].ne("all_background_lots")
        & condition_summary["candidate_eligible"].astype(bool)
        & condition_summary["population_count"].gt(0)
    ].head(12)
    if shown.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ["#b91c1c" if bool(value) else "#2563eb" for value in shown["stable_candidate"]]
    ax.barh(shown["condition"], shown["net_loss_lift_vs_population"], color=colors)
    ax.axvline(DEFAULT_MIN_LIFT, color="#111827", linestyle="--", linewidth=1, label=f"lift floor {DEFAULT_MIN_LIFT}")
    ax.set_xlabel("Net loss lift vs population share")
    ax.set_title("Stage025 PIT entry-state loss concentration")
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def build_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
    numeric_feature_summary: pd.DataFrame,
    tag_coverage: pd.DataFrame,
) -> str:
    scope = decision["analysis_scope"]
    return f"""# Stage025 Stage024 opened/traded 入场状态审计

## 结论

- 决策：`{decision["decision"]}`。
- 原因：{decision["decision_reason"]}
- 本阶段只读，不改策略、不改实盘配置、不连接 CTP、不调用订单 API。

## 调研和判断

- 外部调研判断：meta-labeling 更适合做“已有趋势信号的质量/仓位过滤”，不应该替代主趋势方向；drawdown/positions 分解要把亏损映射回当时可见的入场状态，而不是按事后品种黑名单修补。
- 当前判断：Stage024 已说明剩余 base 亏损主要来自 opened/traded bucket；Stage025 只检查这些 lot 在入场前是否存在可解释的损失集中状态。

## 范围

- Stage024 opened/traded 负净损失行：`{scope["window_loss_rows"]}`。
- focus window 数：`{scope["window_count"]}`，source 数：`{scope["source_count"]}`。
- entry exposure rows：`{scope["entry_exposure_rows"]}`，unique exposed lots：`{scope["unique_exposed_lots"]}`。
- background lots：`{scope["background_lots"]}`，background exposed lots：`{scope["background_exposed_lots"]}`。
- matched net loss：`{scope["matched_net_loss_abs"]:.4f}`，unmatched net loss：`{scope["unmatched_net_loss_abs"]:.4f}`，matched share：`{scope["matched_net_loss_share_pct"]:.4f}%`。
- matched holding loss：`{scope["matched_holding_loss_abs"]:.4f}`。

## 条件摘要

{_md_table(condition_summary.head(15))}

## 产品方向只读归因

{_md_table(product_direction_summary.head(15))}

## 数值特征摘要

{_md_table(numeric_feature_summary.head(15))}

## Stage022 标签覆盖

{_md_table(tag_coverage)}

## 反过拟合和价值判断

- 是否过拟合：否。本阶段没有改参数、没有上线规则，也没有按具体品种/日期做黑名单；它只是把 Stage024 的剩余亏损映射回入场前可见状态。
- 是否值得继续：是，但只能把稳定条件转成下一阶段“预声明真实引擎 guard/质量拆分”的假设；不能直接把本阶段条件当策略。

## 后续规划

- 若稳定条件存在：下一阶段只允许做一个或两个冻结 guard/quality split 的真实引擎 A/B，验证是否保留趋势右尾。
- 若稳定条件不存在：停止继续在 Stage024 focus 窗口挖规则，转向账户状态或外生确认源。
"""


def build_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame) -> str:
    scope = decision["analysis_scope"]
    stable = decision["stable_candidate_conditions"]
    return f"""# Stage025 - Stage024 opened/traded 入场状态审计

- 记录时间：2026-07-02 06:39 CST
- 所属研究线：`{LINE_ID}`
- 是否重要突破版本：否，当前是只读法证审计，不是正式策略候选。

## 本次版本改动

- 新增：`tools/stage025_stage024_opened_entry_state_audit.py`
- 新增：Stage024 opened/traded 负净损失行到 Stage019 closed lots 的 entry exposure 映射。
- 新增：Stage022 xsmom 标签 join，用于只读检查 `xsmom12/xsmom6` 入场确认状态。
- 修改参数：无。
- 删除参数：无。

## 回测结果

- 本阶段未新增正式回测。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 审计结果

- Stage024 opened/traded 负净损失行：`{scope["window_loss_rows"]}`。
- entry exposure rows：`{scope["entry_exposure_rows"]}`，unique exposed lots：`{scope["unique_exposed_lots"]}`。
- matched net loss：`{scope["matched_net_loss_abs"]:.4f}`，matched share：`{scope["matched_net_loss_share_pct"]:.4f}%`。
- stable candidate conditions：`{stable}`。
- 决策：`{decision["decision"]}`。
- 理由：{decision["decision_reason"]}

## 条件 Top 10

{_md_table(condition_summary.head(10))}

## 反思

- 是否过拟合：否。没有根据单一日期、品种、方向做黑名单，也没有扫小参数；只是验证亏损 lot 的 PIT 状态。
- 是否还有价值继续：是。如果稳定条件能转成真实引擎 A/B 并保留右尾，才有继续价值；否则停止这条 focus-window 挖掘。

## TODO

- 下一步先 review Stage025 稳定条件是否具备第一性原理解释。
- 若具备，再做冻结条件的真实引擎 A/B；若不具备，转账户状态或外生确认源。
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    window_detail = _read_csv(STAGE024_WINDOW_DETAIL_PATH)
    closed_lots_raw = _read_csv(STAGE019_CLOSED_LOTS_PATH)
    tagged_events_raw = _read_csv(STAGE022_TAGGED_EVENTS_PATH)

    window_rows = prepare_window_loss_rows(window_detail)
    closed_lots = prepare_closed_lots(closed_lots_raw)
    closed_lots = attach_stage022_tags(closed_lots, tagged_events_raw)
    entry_exposures, unmatched_windows = match_entry_exposures(window_rows, closed_lots)
    background_lots = build_background_lots(closed_lots, window_rows)
    background_lots = attach_exposure_weights(background_lots, entry_exposures)
    condition_summary = summarize_condition_table(background_lots)
    numeric_feature_summary = summarize_numeric_features(background_lots)
    product_direction_summary = summarize_product_direction(entry_exposures)
    tag_coverage = build_tag_coverage(background_lots)
    decision = make_decision(
        window_rows,
        entry_exposures,
        unmatched_windows,
        background_lots,
        condition_summary,
        product_direction_summary,
        tag_coverage,
    )

    entry_exposures.to_csv(ENTRY_EXPOSURES_PATH, index=False, encoding="utf-8-sig")
    background_lots.to_csv(BACKGROUND_LOTS_PATH, index=False, encoding="utf-8-sig")
    unmatched_windows.to_csv(UNMATCHED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    numeric_feature_summary.to_csv(NUMERIC_FEATURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_direction_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    tag_coverage.to_csv(TAG_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    write_condition_chart(condition_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        build_report(decision, condition_summary, product_direction_summary, numeric_feature_summary, tag_coverage),
        encoding="utf-8",
    )
    STAGE_RECORD_PATH.write_text(build_stage_record(decision, condition_summary), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
