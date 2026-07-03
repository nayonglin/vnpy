from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage071"
MODEL_TAG = "stage071_stage070_remaining_left_tail_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage071_stage070_remaining_left_tail_attribution"

TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
TOP_N_WORST_WINDOWS = 32
MIN_COVERAGE_SHARE_FOR_ADD_RISK_MAIN_SOLUTION = 10.0

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage071_stage070_remaining_left_tail_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE070_OUTPUT_DIR = LINE_DIR / "outputs" / "stage070_super_quality_sibling_panel"

STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE070_PREFIX = "rebuilt_c9_stage070_super_quality_sibling_panel"
STAGE070_TAG = "stage070_super_quality_sibling_panel_v1"

STAGE013_CLOSED_LOTS_PATH = (
    STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
)
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"
STAGE070_WORST_WINDOWS_PATH = STAGE070_OUTPUT_DIR / f"{STAGE070_PREFIX}_goal_worst_windows_{STAGE070_TAG}.csv"
STAGE070_LOT_DELTAS_PATH = STAGE070_OUTPUT_DIR / f"{STAGE070_PREFIX}_lot_deltas_{STAGE070_TAG}.csv"

TARGET_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_worst_windows_{MODEL_TAG}.csv"
WINDOW_ENTRIES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_entries_{MODEL_TAG}.csv"
DELTA_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_coverage_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _date_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def select_target_worst_windows(
    worst_windows: pd.DataFrame,
    *,
    target_variant: str = TARGET_VARIANT,
    top_n: int = TOP_N_WORST_WINDOWS,
) -> pd.DataFrame:
    frame = worst_windows.copy()
    frame = frame[frame["variant"].astype(str).eq(target_variant)].copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "stage071_window_rank",
                "variant",
                "source_start_month",
                "window_start_date",
                "window_end_date",
                "return_pct",
            ]
        )
    frame["source_start_month"] = frame["source_start_month"].astype(str)
    frame["window_start_date"] = pd.to_datetime(frame["start_date"], errors="coerce").dt.normalize()
    frame["window_end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.normalize()
    frame["return_pct"] = pd.to_numeric(frame["return_pct"], errors="coerce")
    frame = frame.dropna(subset=["window_start_date", "window_end_date", "return_pct"])
    frame = (
        frame.sort_values(["return_pct", "source_start_month", "window_start_date", "window_end_date"])
        .drop_duplicates(["source_start_month", "window_start_date", "window_end_date"], keep="first")
        .head(int(top_n))
        .reset_index(drop=True)
    )
    frame.insert(0, "stage071_window_rank", np.arange(1, len(frame) + 1))
    keep = [
        "stage071_window_rank",
        "variant",
        "source_start_month",
        "window_type",
        "window_start_date",
        "window_end_date",
        "period_calendar_days",
        "period_trading_days",
        "return_pct",
        "start_equity",
        "end_equity",
    ]
    return frame[[column for column in keep if column in frame.columns]].reset_index(drop=True)


def _feature_columns(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features
    data = features.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["open_trade_id"] = data["open_trade_id"].astype(str)
    keep = [
        "requested_start_month",
        "open_trade_id",
        "ai_rank",
        "ai_score",
        "ai_rank_1_6",
        "ai_rank_1_9",
        "full_market_ai_top8",
        "full_market_simple_top8",
        "full_market_consensus_top8",
        "full_market_probability",
        "account_clean",
        "account_injured",
        "drawdown_abs_pct",
        "loss_streak",
        "active_positions_ge3",
        "active_positions_before",
        "selected_volume_gt1",
        "oi_confirmed",
        "r_multiple_agg",
    ]
    result = data[[column for column in keep if column in data.columns]].copy()
    return result.sort_values(["requested_start_month", "open_trade_id"]).drop_duplicates(
        ["requested_start_month", "open_trade_id"], keep="last"
    )


def attach_stage038_features(closed_lots: pd.DataFrame, feature_matrix: pd.DataFrame) -> pd.DataFrame:
    closed = closed_lots.copy()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["open_trade_id"] = closed["open_trade_id"].astype(str)
    features = _feature_columns(feature_matrix)
    if features.empty:
        return closed
    feature_add = [column for column in features.columns if column not in {"requested_start_month", "open_trade_id"}]
    overlapping = [column for column in feature_add if column in closed.columns]
    rename = {column: f"stage038_{column}" for column in overlapping}
    features = features.rename(columns=rename)
    return closed.merge(features, on=["requested_start_month", "open_trade_id"], how="left")


def attach_stage070_deltas_to_window_entries(
    closed_lots: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    windows: pd.DataFrame,
    *,
    target_variant: str = TARGET_VARIANT,
) -> pd.DataFrame:
    if windows.empty or closed_lots.empty:
        return pd.DataFrame()

    closed = closed_lots.copy()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["lot_key"] = closed["lot_id"].astype(str)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)
    closed = closed.dropna(subset=["entry_date", "exit_date"])

    deltas = lot_deltas.copy()
    deltas = deltas[deltas["candidate_variant"].astype(str).eq(target_variant)].copy()
    if deltas.empty:
        delta_by_lot = pd.DataFrame(
            columns=["requested_start_month", "lot_key", "stage071_stage070_selected", "stage071_stage070_delta_pnl"]
        )
    else:
        deltas["requested_start_month"] = deltas["requested_start_month"].astype(str)
        deltas["lot_key"] = deltas["lot_id"].astype(str)
        deltas["stage070_proxy_delta_pnl"] = pd.to_numeric(
            deltas["stage070_proxy_delta_pnl"], errors="coerce"
        ).fillna(0.0)
        delta_by_lot = (
            deltas.groupby(["requested_start_month", "lot_key"], dropna=False)["stage070_proxy_delta_pnl"]
            .sum()
            .reset_index()
            .rename(columns={"stage070_proxy_delta_pnl": "stage071_stage070_delta_pnl"})
        )
        delta_by_lot["stage071_stage070_selected"] = True

    frames: list[pd.DataFrame] = []
    for row in windows.itertuples(index=False):
        source = str(row.source_start_month)
        start = pd.Timestamp(row.window_start_date).normalize()
        end = pd.Timestamp(row.window_end_date).normalize()
        mask = closed["requested_start_month"].eq(source) & closed["entry_date"].gt(start) & closed["exit_date"].le(end)
        selected = closed.loc[mask].copy()
        if selected.empty:
            continue
        selected["stage071_window_rank"] = int(row.stage071_window_rank)
        selected["stage071_variant"] = target_variant
        selected["stage071_window_start_date"] = start
        selected["stage071_window_end_date"] = end
        selected["stage071_window_return_pct"] = float(getattr(row, "return_pct", np.nan))
        frames.append(selected)

    if not frames:
        return pd.DataFrame()

    entries = pd.concat(frames, ignore_index=True, sort=False)
    entries = entries.merge(delta_by_lot, on=["requested_start_month", "lot_key"], how="left")
    entries["stage071_stage070_selected"] = entries["stage071_stage070_selected"].eq(True)
    entries["stage071_stage070_delta_pnl"] = pd.to_numeric(
        entries["stage071_stage070_delta_pnl"], errors="coerce"
    ).fillna(0.0)
    entries["stage071_base_realized_pnl"] = pd.to_numeric(entries["realized_pnl"], errors="coerce").fillna(0.0)
    entries["stage071_candidate_realized_pnl"] = (
        entries["stage071_base_realized_pnl"] + entries["stage071_stage070_delta_pnl"]
    )
    entries["stage071_base_loss_abs"] = entries["stage071_base_realized_pnl"].clip(upper=0.0).abs()
    entries["stage071_candidate_loss_abs"] = entries["stage071_candidate_realized_pnl"].clip(upper=0.0).abs()
    return entries.sort_values(["stage071_window_rank", "entry_date", "lot_id"]).reset_index(drop=True)


def summarize_delta_coverage(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows = []
    for rank, group in entries.groupby("stage071_window_rank", dropna=False):
        base_pnl = pd.to_numeric(group["stage071_base_realized_pnl"], errors="coerce").fillna(0.0)
        candidate_pnl = pd.to_numeric(group["stage071_candidate_realized_pnl"], errors="coerce").fillna(0.0)
        delta = pd.to_numeric(group["stage071_stage070_delta_pnl"], errors="coerce").fillna(0.0)
        selected = group["stage071_stage070_selected"].astype(bool)
        selected_base_loss = float(base_pnl[selected].clip(upper=0.0).abs().sum())
        unselected_base_loss = float(base_pnl[~selected].clip(upper=0.0).abs().sum())
        base_loss = selected_base_loss + unselected_base_loss
        rows.append(
            {
                "stage071_window_rank": int(rank),
                "requested_start_month": str(group["requested_start_month"].iloc[0])
                if "requested_start_month" in group.columns
                else "",
                "window_start_date": _date_key(group["stage071_window_start_date"].iloc[0])
                if "stage071_window_start_date" in group.columns
                else "",
                "window_end_date": _date_key(group["stage071_window_end_date"].iloc[0])
                if "stage071_window_end_date" in group.columns
                else "",
                "stage070_window_return_pct": float(group["stage071_window_return_pct"].iloc[0])
                if "stage071_window_return_pct" in group.columns
                else np.nan,
                "entry_count": int(len(group)),
                "stage070_selected_entry_count": int(selected.sum()),
                "stage070_unselected_entry_count": int((~selected).sum()),
                "base_total_pnl": float(base_pnl.sum()),
                "candidate_total_pnl": float(candidate_pnl.sum()),
                "selected_base_total_pnl": float(base_pnl[selected].sum()),
                "unselected_base_total_pnl": float(base_pnl[~selected].sum()),
                "selected_delta_pnl": float(delta.sum()),
                "base_loss_abs": base_loss,
                "selected_loss_abs": selected_base_loss,
                "unselected_loss_abs": unselected_base_loss,
                "selected_loss_abs_share_pct": selected_base_loss / base_loss * 100.0 if base_loss else 0.0,
                "unselected_loss_abs_share_pct": unselected_base_loss / base_loss * 100.0 if base_loss else 0.0,
                "abs_delta_share_of_base_loss_pct": abs(float(delta.sum())) / base_loss * 100.0 if base_loss else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("stage071_window_rank").reset_index(drop=True)


def _condition_masks(entries: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    index = entries.index
    selected = _to_bool(entries.get("stage071_stage070_selected", False), index=index)
    full_market_ai_top8 = _to_bool(entries.get("full_market_ai_top8", False), index=index)
    ai_rank_1_6 = _to_bool(entries.get("ai_rank_1_6", False), index=index)
    account_injured = _to_bool(entries.get("account_injured", False), index=index)
    active_positions_ge3 = _to_bool(entries.get("active_positions_ge3", False), index=index)
    selected_volume = _num(entries, "selected_volume", 0.0).fillna(0.0)
    oi_confirmed = _to_bool(entries.get("oi_confirmed", False), index=index)
    loss_streak = _num(entries, "loss_streak", 0.0).fillna(0.0)
    drawdown = _num(entries, "drawdown_abs_pct", 0.0).fillna(0.0)
    return [
        ("all_remaining_window_entries", "Stage070 最差窗口内全部已退出 entry", pd.Series(True, index=index)),
        ("stage070_selected", "被 Stage070 最佳 variant 加风险选中的 entry", selected),
        ("not_stage070_selected", "未被 Stage070 最佳 variant 选中的 entry", ~selected),
        ("full_market_ai_top8", "full-market AI top8", full_market_ai_top8),
        ("not_full_market_ai_top8", "非 full-market AI top8", ~full_market_ai_top8),
        ("ai_rank_1_6", "Stage182 AI rank 1-6", ai_rank_1_6),
        ("account_injured", "入场前账户受伤", account_injured),
        ("active_positions_lt3", "入场前活跃持仓 <3", ~active_positions_ge3),
        ("selected_volume_gt1", "释放到 1 手以上", selected_volume.gt(1)),
        ("oi_confirmed", "OI 与价格方向确认", oi_confirmed),
        ("loss_streak_ge3", "loss_streak >=3", loss_streak.ge(3)),
        ("drawdown_abs_ge20", "入场前回撤绝对值 >=20%", drawdown.ge(20)),
    ]


def summarize_conditions(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    base_pnl_all = pd.to_numeric(entries["stage071_base_realized_pnl"], errors="coerce").fillna(0.0)
    total_loss_abs = float(base_pnl_all.clip(upper=0.0).abs().sum())
    for condition, description, mask in _condition_masks(entries):
        mask = mask.reindex(entries.index).fillna(False).astype(bool)
        subset = entries.loc[mask]
        base_pnl = pd.to_numeric(subset.get("stage071_base_realized_pnl"), errors="coerce").fillna(0.0)
        candidate_pnl = pd.to_numeric(subset.get("stage071_candidate_realized_pnl"), errors="coerce").fillna(0.0)
        delta = pd.to_numeric(subset.get("stage071_stage070_delta_pnl"), errors="coerce").fillna(0.0)
        loss_abs = float(base_pnl.clip(upper=0.0).abs().sum())
        rows.append(
            {
                "condition": condition,
                "description": description,
                "count": int(len(subset)),
                "source_count": int(subset["requested_start_month"].nunique()) if len(subset) else 0,
                "product_count": int(subset["product"].nunique()) if len(subset) and "product" in subset.columns else 0,
                "base_total_pnl": float(base_pnl.sum()) if len(subset) else 0.0,
                "candidate_total_pnl": float(candidate_pnl.sum()) if len(subset) else 0.0,
                "stage070_delta_pnl": float(delta.sum()) if len(subset) else 0.0,
                "base_loss_abs": loss_abs,
                "base_loss_abs_share_pct": loss_abs / total_loss_abs * 100.0 if total_loss_abs else 0.0,
                "loss_rate_pct": float((base_pnl < 0).mean() * 100.0) if len(subset) else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["base_loss_abs_share_pct", "base_total_pnl"], ascending=[False, True])


def summarize_sources(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows = []
    for source, group in entries.groupby("requested_start_month", dropna=False):
        base_pnl = pd.to_numeric(group["stage071_base_realized_pnl"], errors="coerce").fillna(0.0)
        delta = pd.to_numeric(group["stage071_stage070_delta_pnl"], errors="coerce").fillna(0.0)
        selected = group["stage071_stage070_selected"].astype(bool)
        rows.append(
            {
                "requested_start_month": str(source),
                "window_count": int(group["stage071_window_rank"].nunique()),
                "entry_count": int(len(group)),
                "stage070_selected_entry_count": int(selected.sum()),
                "base_total_pnl": float(base_pnl.sum()),
                "stage070_delta_pnl": float(delta.sum()),
                "candidate_total_pnl": float((base_pnl + delta).sum()),
                "base_loss_abs": float(base_pnl.clip(upper=0.0).abs().sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("base_total_pnl").reset_index(drop=True)


def _decision(
    windows: pd.DataFrame,
    entries: pd.DataFrame,
    coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
) -> dict[str, Any]:
    base_loss_abs = float(pd.to_numeric(coverage.get("base_loss_abs"), errors="coerce").fillna(0.0).sum())
    selected_delta_pnl = float(pd.to_numeric(coverage.get("selected_delta_pnl"), errors="coerce").fillna(0.0).sum())
    selected_loss_abs = float(pd.to_numeric(coverage.get("selected_loss_abs"), errors="coerce").fillna(0.0).sum())
    unselected_loss_abs = float(pd.to_numeric(coverage.get("unselected_loss_abs"), errors="coerce").fillna(0.0).sum())
    selected_delta_abs_share = abs(selected_delta_pnl) / base_loss_abs * 100.0 if base_loss_abs else 0.0
    selected_loss_share = selected_loss_abs / base_loss_abs * 100.0 if base_loss_abs else 0.0
    if selected_delta_abs_share < MIN_COVERAGE_SHARE_FOR_ADD_RISK_MAIN_SOLUTION:
        decision = "stage071_stage070_add_risk_low_coverage_remaining_tail_requires_defensive_or_new_pit"
        next_stage = "do_not_tune_stage070_add_risk_turn_to_account_outer_layer_or_defensive_pit_budget"
    elif selected_delta_pnl < 0:
        decision = "stage071_stage070_selected_delta_worsens_remaining_tail_stop_add_risk_shape"
        next_stage = "turn_to_account_outer_layer_or_new_pit_information"
    else:
        decision = "stage071_stage070_partial_left_tail_coverage_requires_true_account_layer"
        next_stage = "test_low_degree_account_outer_layer_before_any_trade_rule"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_variant": TARGET_VARIANT,
        "top_n_worst_windows": TOP_N_WORST_WINDOWS,
        "decision": decision,
        "next_stage": next_stage,
        "audit_type": "read_only_remaining_left_tail_attribution_after_stage070_best_add_risk_proxy",
        "worst_window_count": int(len(windows)),
        "window_entry_rows": int(len(entries)),
        "base_loss_abs": base_loss_abs,
        "selected_loss_abs": selected_loss_abs,
        "unselected_loss_abs": unselected_loss_abs,
        "selected_loss_abs_share_pct": selected_loss_share,
        "unselected_loss_abs_share_pct": unselected_loss_abs / base_loss_abs * 100.0 if base_loss_abs else 0.0,
        "selected_delta_pnl": selected_delta_pnl,
        "selected_delta_abs_share_of_base_loss_pct": selected_delta_abs_share,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "triggered_ab_experiment": False,
        "external_research_judgment": (
            "外部资料支持趋势策略可使用风险 overlay/波动率目标来治理尾部，但 Rob Carver/pysystemtrade 也提醒风险 overlay "
            "容易降低趋势策略正偏度，不能为修一个历史窗口而调参。Stage071 因此只做 Stage070 后剩余左尾归因，"
            "不新增交易参数。参考：https://github.com/pst-group/pysystemtrade ; "
            "https://qoppac.blogspot.com/2020/05/ ; https://alphaarchitect.com/conditional-volatility-targeting/"
        ),
        "overfit_reflection_before": (
            "否。Stage071 固定使用 Stage070 最佳 variant 与其最差窗口，只做覆盖归因，不扫阈值、品种、方向或日期。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有把任何结果写成交易规则；如果继续改 Stage070 composite、TopN 或单窗口过滤，就是过拟合。"
        ),
        "continue_value_before": "有。Stage070 已证明加风险有收益信息但不能解决左尾，必须知道剩余尾部是否被该形状覆盖。",
        "continue_value_after": (
            "有，但方向应转账户外层/防守型 PIT 预算或新信息源；继续救 Stage070 高质量加风险形状价值低。"
        ),
        "top_conditions": condition_summary.head(8).to_dict("records") if not condition_summary.empty else [],
        "outputs": {
            "target_worst_windows": str(TARGET_WORST_WINDOWS_PATH),
            "window_entries": str(WINDOW_ENTRIES_PATH),
            "delta_coverage": str(DELTA_COVERAGE_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    windows: pd.DataFrame,
    coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Stage071 - Stage070 剩余左尾归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision['next_stage']}`",
        f"- 目标 variant：`{TARGET_VARIANT}`",
        "- 阶段性质：只读归因；复用 Stage070 closed-lot proxy 产物，不改策略、不连接 CTP、不调用下单。",
        "",
        "## 核心结论",
        "",
        f"- 最差窗口数：`{decision['worst_window_count']}`",
        f"- 窗口 entry 行数：`{decision['window_entry_rows']}`",
        f"- base loss_abs：`{decision['base_loss_abs']:,.2f}`",
        f"- Stage070 selected loss_abs 占比：`{decision['selected_loss_abs_share_pct']:.4f}%`",
        f"- Stage070 unselected loss_abs 占比：`{decision['unselected_loss_abs_share_pct']:.4f}%`",
        f"- Stage070 selected delta：`{decision['selected_delta_pnl']:,.2f}`",
        f"- selected delta / base loss_abs：`{decision['selected_delta_abs_share_of_base_loss_pct']:.4f}%`",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## Stage070 目标最差窗口",
        "",
        _md_table(windows, max_rows=40),
        "",
        "## Delta 覆盖",
        "",
        _md_table(coverage, max_rows=40),
        "",
        "## 条件汇总",
        "",
        _md_table(condition_summary, max_rows=40),
        "",
        "## Source 汇总",
        "",
        _md_table(source_summary, max_rows=40),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage071_stage070_remaining_left_tail_attribution.md"
    report = REPORT_PATH.read_text(encoding="utf-8")
    header = f"""# Stage071 - Stage070 剩余左尾归因

- 记录时间：`{timestamp.isoformat(timespec='minutes')}`
- line_id：`{LINE_ID}`
- 当前模式：`day`
- model_tag：`{MODEL_TAG}`
- 是否重要突破版本：`否`
- 是否触发A/B：`否，只读归因`
- 决策：`{decision['decision']}`

## 本次版本变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage071_stage070_remaining_left_tail_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_stage071_stage070_remaining_left_tail_attribution.py`
- 新增参数：`TARGET_VARIANT={TARGET_VARIANT}`、`TOP_N_WORST_WINDOWS={TOP_N_WORST_WINDOWS}`。
- 修改参数：无，Stage013/Stage070/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：无真实回测；本阶段是 Stage070 closed-lot proxy 剩余左尾归因。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

"""
    path.write_text(header + report, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    worst = _read_csv(STAGE070_WORST_WINDOWS_PATH)
    closed = _read_csv(STAGE013_CLOSED_LOTS_PATH, parse_dates=["entry_date", "exit_date"])
    features = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    deltas = _read_csv(STAGE070_LOT_DELTAS_PATH, parse_dates=["entry_date", "exit_date"])

    windows = select_target_worst_windows(worst)
    enriched_closed = attach_stage038_features(closed, features)
    entries = attach_stage070_deltas_to_window_entries(enriched_closed, deltas, windows)
    coverage = summarize_delta_coverage(entries)
    condition_summary = summarize_conditions(entries)
    source_summary = summarize_sources(entries)
    decision = _decision(windows, entries, coverage, condition_summary)

    windows.to_csv(TARGET_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    entries.to_csv(WINDOW_ENTRIES_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(DELTA_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, windows, coverage, condition_summary, source_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
