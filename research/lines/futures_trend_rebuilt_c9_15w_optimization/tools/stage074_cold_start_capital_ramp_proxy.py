from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import stage009_dense_start_goal_audit as s009
import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage074"
MODEL_TAG = "stage074_cold_start_capital_ramp_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage074_cold_start_capital_ramp_proxy"

CAPITAL = 150000.0
BASE_VARIANT = "stage013_engine"
TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
RAMP_FLOOR = 0.35
RAMP_TRADING_DAYS = 252
RAMP_SUFFIX = "_cold_start_ramp"
EPS = 1e-9

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
WORST_PER_START = 3
WORST_OUTPUT_ROWS = 1000

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / "stage074_cold_start_capital_ramp_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE070_OUTPUT_DIR = LINE_DIR / "outputs" / "stage070_super_quality_sibling_panel"
STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE070_PREFIX = "rebuilt_c9_stage070_super_quality_sibling_panel"
STAGE070_TAG = "stage070_super_quality_sibling_panel_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE070_PANEL_CURVES_PATH = STAGE070_OUTPUT_DIR / f"{STAGE070_PREFIX}_panel_curves_{STAGE070_TAG}.csv.gz"

PANEL_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_panel_curves_{MODEL_TAG}.csv.gz"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
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
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def compute_age_ramp_multiplier(
    length: int,
    *,
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> pd.Series:
    if length <= 0:
        return pd.Series(dtype="float64")
    days = max(1, int(ramp_trading_days))
    floor_value = max(0.0, min(1.0, float(floor)))
    age_for_pnl = np.maximum(np.arange(length, dtype=float) - 1.0, 0.0)
    if days <= 1:
        values = np.ones(length, dtype=float)
        values[0] = floor_value
        return pd.Series(values, dtype="float64")
    ramp = floor_value + (1.0 - floor_value) * np.minimum(age_for_pnl, days - 1.0) / (days - 1.0)
    return pd.Series(np.clip(ramp, floor_value, 1.0), dtype="float64")


def apply_start_reset_ramp_to_equity(
    equity: pd.Series,
    *,
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().astype(float).reset_index(drop=True)
    if values.empty:
        return values
    multiplier = compute_age_ramp_multiplier(len(values), floor=floor, ramp_trading_days=ramp_trading_days)
    pnl = values.diff().fillna(0.0)
    adjusted = values.iloc[0] + (pnl * multiplier).cumsum()
    return adjusted.astype(float)


def _ret_pct(start_equity: float, end_equity: float) -> float:
    return float((end_equity / start_equity - 1.0) * 100.0) if abs(start_equity) > EPS else np.nan


def _simulate_returns_from_start(
    equity: np.ndarray,
    start_index: int,
    end_indices: np.ndarray,
    *,
    floor: float,
    ramp_trading_days: int,
    apply_ramp: bool,
) -> tuple[np.ndarray, np.ndarray]:
    start_equity = float(equity[start_index])
    if not apply_ramp:
        end_equity = equity[end_indices]
        return (end_equity / start_equity - 1.0) * 100.0, end_equity
    segment = pd.Series(equity[start_index : end_indices[-1] + 1])
    adjusted_segment = apply_start_reset_ramp_to_equity(
        segment,
        floor=floor,
        ramp_trading_days=ramp_trading_days,
    ).to_numpy(dtype=float)
    local_end_indices = end_indices - start_index
    end_equity = adjusted_segment[local_end_indices]
    return (end_equity / start_equity - 1.0) * 100.0, end_equity


def _audit_one_group(
    *,
    variant: str,
    source_start: str,
    group: pd.DataFrame,
    apply_ramp: bool,
    floor: float,
    ramp_trading_days: int,
    objective_start_min: pd.Timestamp,
    objective_start_max: pd.Timestamp,
    min_period_calendar_days: int,
    worst_per_start: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = pd.to_datetime(data["date"], errors="coerce").dt.normalize().to_numpy(dtype="datetime64[ns]")
    equity = pd.to_numeric(data["equity"], errors="coerce").to_numpy(dtype=float)
    start_mask = (
        (pd.to_datetime(data["date"], errors="coerce").dt.normalize() >= objective_start_min)
        & (pd.to_datetime(data["date"], errors="coerce").dt.normalize() <= objective_start_max)
    )
    start_indices = np.flatnonzero(start_mask.to_numpy())

    audit_variant = f"{variant}{RAMP_SUFFIX}" if apply_ramp else variant
    all_count = 0
    all_negative = 0
    all_positive = 0
    all_sum = 0.0
    all_min = np.inf
    final_count = 0
    final_negative = 0
    final_sum = 0.0
    final_min = np.inf
    worst_rows: list[dict[str, Any]] = []

    for start_index in start_indices:
        start_date = pd.Timestamp(dates[start_index])
        start_equity = float(equity[start_index])
        min_end_date = start_date + pd.Timedelta(days=int(min_period_calendar_days))
        min_end_index = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_index >= len(dates) or abs(start_equity) <= EPS:
            continue
        end_indices = np.arange(min_end_index, len(dates), dtype=int)
        returns, end_equities = _simulate_returns_from_start(
            equity,
            start_index,
            end_indices,
            floor=floor,
            ramp_trading_days=ramp_trading_days,
            apply_ramp=apply_ramp,
        )
        valid = np.isfinite(returns)
        returns = returns[valid]
        end_equities = end_equities[valid]
        valid_end_indices = end_indices[valid]
        if len(returns) == 0:
            continue
        all_count += int(len(returns))
        all_negative += int((returns < 0.0).sum())
        all_positive += int((returns > 0.0).sum())
        all_sum += float(returns.sum())
        all_min = min(all_min, float(returns.min()))

        k = min(int(worst_per_start), len(returns))
        candidate_positions = np.argpartition(returns, k - 1)[:k]
        for local_position in candidate_positions:
            ret = float(returns[local_position])
            if ret >= 0.0:
                continue
            end_index = int(valid_end_indices[local_position])
            worst_rows.append(
                {
                    "variant": audit_variant,
                    "source_start_month": source_start,
                    "window_type": "all_gt_1y",
                    "start_date": start_date.date().isoformat(),
                    "end_date": pd.Timestamp(dates[end_index]).date().isoformat(),
                    "period_calendar_days": int((pd.Timestamp(dates[end_index]) - start_date).days),
                    "period_trading_days": int(end_index - start_index + 1),
                    "return_pct": ret,
                    "start_equity": start_equity,
                    "end_equity": float(end_equities[local_position]),
                }
            )

        final_returns, _final_equities = _simulate_returns_from_start(
            equity,
            start_index,
            np.array([len(equity) - 1], dtype=int),
            floor=floor,
            ramp_trading_days=ramp_trading_days,
            apply_ramp=apply_ramp,
        )
        final_ret = float(final_returns[0])
        final_count += 1
        final_negative += int(final_ret < 0.0)
        final_sum += final_ret
        final_min = min(final_min, final_ret)

    rows = [
        {
            "variant": audit_variant,
            "source_start_month": source_start,
            "audit_scope": "all_trading_end_dates_gt_1y",
            "window_count": all_count,
            "positive_count": all_positive,
            "negative_count": all_negative,
            "negative_rate_pct": float(all_negative / all_count * 100.0) if all_count else np.nan,
            "min_return_pct": float(all_min) if np.isfinite(all_min) else np.nan,
            "mean_return_pct": float(all_sum / all_count) if all_count else np.nan,
            "is_independent_daily_cold_start": 0,
            "is_start_reset_ramp_proxy": int(apply_ramp),
        },
        {
            "variant": audit_variant,
            "source_start_month": source_start,
            "audit_scope": "start_to_2026_06_30_only",
            "window_count": final_count,
            "positive_count": int(final_count - final_negative),
            "negative_count": final_negative,
            "negative_rate_pct": float(final_negative / final_count * 100.0) if final_count else np.nan,
            "min_return_pct": float(final_min) if np.isfinite(final_min) else np.nan,
            "mean_return_pct": float(final_sum / final_count) if final_count else np.nan,
            "is_independent_daily_cold_start": 0,
            "is_start_reset_ramp_proxy": int(apply_ramp),
        },
    ]
    return rows, worst_rows


def run_dense_ramp_goal_audit(
    curves: pd.DataFrame,
    *,
    target_variants: list[str],
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
    objective_start_min: pd.Timestamp = OBJECTIVE_START_MIN,
    objective_start_max: pd.Timestamp = OBJECTIVE_START_MAX,
    min_period_calendar_days: int = MIN_PERIOD_CALENDAR_DAYS,
    worst_per_start: int = WORST_PER_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[frame["variant"].isin(target_variants)].dropna(subset=["date", "equity"]).copy()
    aggregate_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []
    for (variant, source_start), group in frame.groupby(["variant", "requested_start_month"], sort=True):
        for apply_ramp in (False, True):
            rows, worst = _audit_one_group(
                variant=str(variant),
                source_start=str(source_start),
                group=group,
                apply_ramp=apply_ramp,
                floor=floor,
                ramp_trading_days=ramp_trading_days,
                objective_start_min=objective_start_min,
                objective_start_max=objective_start_max,
                min_period_calendar_days=min_period_calendar_days,
                worst_per_start=worst_per_start,
            )
            aggregate_rows.extend(rows)
            worst_rows.extend(worst)
    aggregate = pd.DataFrame(aggregate_rows)
    worst = pd.DataFrame(worst_rows)
    if not worst.empty:
        worst = worst.sort_values("return_pct").head(WORST_OUTPUT_ROWS).reset_index(drop=True)
    return aggregate, worst


def build_original_start_ramp_panel(
    panel_curves: pd.DataFrame,
    *,
    target_variants: list[str],
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> pd.DataFrame:
    frame = panel_curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[frame["variant"].isin(target_variants)].dropna(subset=["date", "equity"]).copy()
    parts = [frame[["variant", "requested_start_month", "date", "equity"]]]
    ramp_frames: list[pd.DataFrame] = []
    for (variant, source), group in frame.groupby(["variant", "requested_start_month"], sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        ramped = group[["requested_start_month", "date"]].copy()
        ramped["variant"] = f"{variant}{RAMP_SUFFIX}"
        ramped["equity"] = apply_start_reset_ramp_to_equity(
            group["equity"],
            floor=floor,
            ramp_trading_days=ramp_trading_days,
        )
        ramped["stage074_ramp_floor"] = float(floor)
        ramped["stage074_ramp_trading_days"] = int(ramp_trading_days)
        ramped["stage074_ramp_multiplier"] = compute_age_ramp_multiplier(
            len(group),
            floor=floor,
            ramp_trading_days=ramp_trading_days,
        )
        ramped["requested_start_month"] = str(source)
        ramp_frames.append(ramped)
    if ramp_frames:
        parts.append(pd.concat(ramp_frames, ignore_index=True, sort=False))
    return pd.concat(parts, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True)


def _source_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in panel.groupby(["variant", "requested_start_month"], sort=True):
        g = group.sort_values("date").copy()
        equity = pd.to_numeric(g["equity"], errors="coerce")
        rows.append(
            {
                "variant": str(g["variant"].iloc[0]),
                "requested_start_month": str(g["requested_start_month"].iloc[0]),
                "actual_start": pd.Timestamp(g["date"].iloc[0]).date().isoformat(),
                "actual_end": pd.Timestamp(g["date"].iloc[-1]).date().isoformat(),
                "trading_days": int(len(g)),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(s039._drawdown_pct(equity).min()),
                "sharpe": s039._sharpe_from_equity(equity),
                "ramp_mean_multiplier": float(
                    pd.to_numeric(g.get("stage074_ramp_multiplier"), errors="coerce").mean()
                )
                if "stage074_ramp_multiplier" in g
                else 1.0,
                "ramp_min_multiplier": float(
                    pd.to_numeric(g.get("stage074_ramp_multiplier"), errors="coerce").min()
                )
                if "stage074_ramp_multiplier" in g
                else 1.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _retention(source_summary: pd.DataFrame) -> pd.DataFrame:
    base_stage006 = _read_csv(BASE_STAGE006_SUMMARY_PATH)
    base_stage006 = base_stage006[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    stage013 = source_summary[source_summary["variant"].eq(BASE_VARIANT)][
        ["requested_start_month", "total_return_pct"]
    ].rename(columns={"total_return_pct": "total_return_pct_stage013"})
    rows: list[pd.DataFrame] = []
    for variant in sorted(set(source_summary["variant"]) - {BASE_VARIANT, TARGET_VARIANT}):
        candidate = source_summary[source_summary["variant"].eq(variant)][
            ["requested_start_month", "total_return_pct"]
        ].rename(columns={"total_return_pct": "candidate_total_return_pct"})
        merged = base_stage006.merge(stage013, on="requested_start_month", how="inner").merge(
            candidate,
            on="requested_start_month",
            how="inner",
        )
        merged["variant"] = variant
        merged["vs_base_stage006_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
        )
        merged["vs_stage013_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
        )
        merged["passes_80pct_retention_vs_base_stage006"] = merged["vs_base_stage006_return_ratio"].ge(0.8).astype(
            "int64"
        )
        merged["passes_80pct_retention_vs_stage013"] = merged["vs_stage013_return_ratio"].ge(0.8).astype("int64")
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _variant_goal_summary(aggregate: pd.DataFrame, source_summary: pd.DataFrame, retention: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, group in source_summary.groupby("variant", sort=True):
        all_scope = aggregate[
            aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
        ]
        final_scope = aggregate[
            aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")
        ]
        ret = retention[retention["variant"].eq(variant)] if not retention.empty else pd.DataFrame()
        rows.append(
            {
                "variant": variant,
                "min_return_pct": float(group["total_return_pct"].min()),
                "median_return_pct": float(group["total_return_pct"].median()),
                "worst_max_dd_pct": float(group["max_dd_pct"].min()),
                "median_sharpe": float(group["sharpe"].median()),
                "all_gt1y_window_count": int(all_scope["window_count"].sum()) if not all_scope.empty else 0,
                "all_gt1y_negative_count": int(all_scope["negative_count"].sum()) if not all_scope.empty else 0,
                "all_gt1y_min_return_pct": float(all_scope["min_return_pct"].min()) if not all_scope.empty else np.nan,
                "to_final_negative_count": int(final_scope["negative_count"].sum()) if not final_scope.empty else 0,
                "to_final_min_return_pct": float(final_scope["min_return_pct"].min()) if not final_scope.empty else np.nan,
                "retention_vs_base_stage006_pass_count": int(ret["passes_80pct_retention_vs_base_stage006"].sum())
                if not ret.empty
                else np.nan,
                "retention_vs_stage013_pass_count": int(ret["passes_80pct_retention_vs_stage013"].sum())
                if not ret.empty
                else np.nan,
                "retention_rows": int(len(ret)) if not ret.empty else 0,
            }
        )
    return pd.DataFrame(rows).sort_values("variant").reset_index(drop=True)


def _decision(variant_summary: pd.DataFrame) -> dict[str, Any]:
    target_c = f"{TARGET_VARIANT}{RAMP_SUFFIX}"
    target_rows = variant_summary[variant_summary["variant"].eq(target_c)]
    target = target_rows.iloc[0].to_dict() if not target_rows.empty else {}
    negative_count = int(target.get("all_gt1y_negative_count", 0)) if target else 0
    retention_pass = int(target.get("retention_vs_base_stage006_pass_count", 0)) if target else 0
    retention_rows = int(target.get("retention_rows", 0)) if target else 0
    if target and negative_count == 0 and retention_pass == retention_rows and retention_rows > 0:
        decision = "stage074_cold_start_ramp_proxy_passes_goal_needs_true_deployment_review"
        next_stage = "进入真实部署层/日级冷启动更宽验证，严查收益保留和成本，不直接上线"
    else:
        decision = "stage074_cold_start_ramp_proxy_not_goal_no_param_rescue"
        next_stage = "停止 floor/ramp_days 救参；若继续账户外层，应换结构而不是调 0.35/252"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "arms": {
            "A": BASE_VARIANT,
            "B": f"{BASE_VARIANT}{RAMP_SUFFIX}",
            "C0": TARGET_VARIANT,
            "C": target_c,
        },
        "ramp_floor": RAMP_FLOOR,
        "ramp_trading_days": RAMP_TRADING_DAYS,
        "target_metrics": target,
        "variant_summary": variant_summary.to_dict(orient="records"),
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "proxy_overlay": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Managed futures references support risk targeting and account capital correction as broad portfolio-level "
            "controls; this stage freezes a cold-start ramp instead of tuning signal/product/date filters."
        ),
        "overfit_reflection_before": (
            "否。候选是账户启动风险部署层，固定 252 个交易日和 0.35 floor，不按具体坏窗口调参。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有根据结果调整 floor 或 ramp_days；若失败后继续调这些数就是过拟合。"
        ),
        "continue_value_before": "有。目标本质包含任意起点冷启动路径，账户部署层直接针对这个结构问题。",
        "continue_value_after": (
            "若 proxy 不达标，则该线性 ramp 形状无继续救参价值；若达标，也必须做真实部署层验证。"
        ),
        "outputs": {
            "panel_curves": str(PANEL_CURVES_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "retention": str(RETENTION_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], variant_summary: pd.DataFrame, aggregate: pd.DataFrame, worst: pd.DataFrame) -> str:
    lines = [
        "# Stage074 cold-start capital ramp proxy",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：{decision['next_stage']}",
        f"- A/B/C：A=`{decision['arms']['A']}`，B=`{decision['arms']['B']}`，C0=`{decision['arms']['C0']}`，C=`{decision['arms']['C']}`",
        f"- 固定参数：floor `{decision['ramp_floor']}`，ramp `{decision['ramp_trading_days']}` 个交易日。",
        "",
        "## 外部调研判断",
        "",
        "- Managed futures/trend-following 资料支持组合层风险目标、drawdown/risk overlay 和 capital correction，但也警告过度调参会削弱趋势右尾。",
        "- 本阶段只验证一个冷启动部署层，不改信号、不改品种、不按坏窗口调参数。",
        "",
        "## 过拟合与继续价值反思",
        "",
        f"- 开始是否过拟合：{decision['overfit_reflection_before']}",
        f"- 结束是否过拟合：{decision['overfit_reflection_after']}",
        f"- 开始是否值得继续：{decision['continue_value_before']}",
        f"- 结束是否值得继续：{decision['continue_value_after']}",
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary),
        "",
        "## Goal Aggregate",
        "",
        _md_table(aggregate.head(40)),
        "",
        "## Worst Windows",
        "",
        _md_table(worst.head(40)),
        "",
        "## 输出",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    return "\n".join(lines) + "\n"


def _write_stage_record(report: str, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage074_cold_start_capital_ramp_proxy.md"
    lines = [
        "# Stage074 冷启动资本 ramp proxy",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：否",
        "- 新增参数：`stage074_cold_start_ramp_floor=0.35`、`stage074_cold_start_ramp_trading_days=252`。",
        "- 修改参数：无正式策略参数修改；本阶段是账户外层 proxy。",
        "- 删除参数：无。",
        "",
        report,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    panel = _read_csv(STAGE070_PANEL_CURVES_PATH)
    target_variants = [BASE_VARIANT, TARGET_VARIANT]
    panel = panel[panel["variant"].isin(target_variants)].copy()
    ramp_panel = build_original_start_ramp_panel(panel, target_variants=target_variants)
    source_summary = _source_summary(ramp_panel)
    retention = _retention(source_summary)
    aggregate, worst = run_dense_ramp_goal_audit(panel, target_variants=target_variants)
    variant_summary = _variant_goal_summary(aggregate, source_summary, retention)
    decision = _decision(variant_summary)
    report = _write_report(decision, variant_summary, aggregate, worst)
    stage_record = _write_stage_record(report, decision)
    decision["outputs"]["stage_record"] = str(stage_record)

    ramp_panel.to_csv(PANEL_CURVES_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(report, encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
