from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage075"
MODEL_TAG = "stage075_staggered_sleeve_deployment_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage075_staggered_sleeve_deployment_proxy"

CAPITAL = 150000.0
BASE_VARIANT = "stage013_engine"
TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
STAGGERED_SUFFIX = "_staggered_sleeve"
SLEEVE_OFFSETS = (0, 63, 126, 189)
EPS = 1e-9

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
WORST_PER_START = 3
WORST_OUTPUT_ROWS = 1000

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / "stage075_staggered_sleeve_deployment_proxy"
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
VARIANT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ABSOLUTE_EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
TARGET_FOCUS_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_absolute_equity_focus_chart_{MODEL_TAG}.png"


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


def _normalize_offsets(sleeve_offsets: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    offsets = tuple(max(0, int(item)) for item in sleeve_offsets)
    if not offsets:
        raise ValueError("sleeve_offsets must not be empty")
    return offsets


def compute_staggered_sleeve_multiplier(
    length: int,
    *,
    sleeve_offsets: tuple[int, ...] | list[int] = SLEEVE_OFFSETS,
) -> pd.Series:
    if length <= 0:
        return pd.Series(dtype="float64")
    offsets = _normalize_offsets(sleeve_offsets)
    index = np.arange(length, dtype=int)
    active = np.zeros(length, dtype=float)
    for offset in offsets:
        active += (index >= offset).astype(float)
    return pd.Series(active / float(len(offsets)), dtype="float64")


def apply_staggered_sleeve_deployment_to_equity(
    equity: pd.Series,
    *,
    sleeve_offsets: tuple[int, ...] | list[int] = SLEEVE_OFFSETS,
) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().astype(float).reset_index(drop=True)
    if values.empty:
        return values
    multiplier = compute_staggered_sleeve_multiplier(len(values), sleeve_offsets=sleeve_offsets)
    pnl = values.diff().fillna(0.0)
    adjusted = values.iloc[0] + (pnl * multiplier).cumsum()
    return adjusted.astype(float)


def _simulate_returns_from_start(
    equity: np.ndarray,
    start_index: int,
    end_indices: np.ndarray,
    *,
    sleeve_offsets: tuple[int, ...],
    apply_staggered: bool,
) -> tuple[np.ndarray, np.ndarray]:
    start_equity = float(equity[start_index])
    if not apply_staggered:
        end_equity = equity[end_indices]
        return (end_equity / start_equity - 1.0) * 100.0, end_equity
    segment = pd.Series(equity[start_index : end_indices[-1] + 1])
    adjusted_segment = apply_staggered_sleeve_deployment_to_equity(
        segment,
        sleeve_offsets=sleeve_offsets,
    ).to_numpy(dtype=float)
    local_end_indices = end_indices - start_index
    end_equity = adjusted_segment[local_end_indices]
    return (end_equity / start_equity - 1.0) * 100.0, end_equity


def _audit_one_group(
    *,
    variant: str,
    source_start: str,
    group: pd.DataFrame,
    apply_staggered: bool,
    sleeve_offsets: tuple[int, ...],
    objective_start_min: pd.Timestamp,
    objective_start_max: pd.Timestamp,
    min_period_calendar_days: int,
    worst_per_start: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    date_series = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    dates = date_series.to_numpy(dtype="datetime64[ns]")
    equity = pd.to_numeric(data["equity"], errors="coerce").to_numpy(dtype=float)
    start_mask = (date_series >= objective_start_min) & (date_series <= objective_start_max)
    start_indices = np.flatnonzero(start_mask.to_numpy())

    audit_variant = f"{variant}{STAGGERED_SUFFIX}" if apply_staggered else variant
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
            sleeve_offsets=sleeve_offsets,
            apply_staggered=apply_staggered,
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
        for local_position in np.argpartition(returns, k - 1)[:k]:
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
            sleeve_offsets=sleeve_offsets,
            apply_staggered=apply_staggered,
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
            "is_staggered_sleeve_proxy": int(apply_staggered),
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
            "is_staggered_sleeve_proxy": int(apply_staggered),
        },
    ]
    return rows, worst_rows


def run_dense_staggered_goal_audit(
    curves: pd.DataFrame,
    *,
    target_variants: list[str],
    sleeve_offsets: tuple[int, ...] | list[int] = SLEEVE_OFFSETS,
    objective_start_min: pd.Timestamp = OBJECTIVE_START_MIN,
    objective_start_max: pd.Timestamp = OBJECTIVE_START_MAX,
    min_period_calendar_days: int = MIN_PERIOD_CALENDAR_DAYS,
    worst_per_start: int = WORST_PER_START,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    offsets = _normalize_offsets(sleeve_offsets)
    frame = curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[frame["variant"].isin(target_variants)].dropna(subset=["date", "equity"]).copy()
    aggregate_rows: list[dict[str, Any]] = []
    worst_rows: list[dict[str, Any]] = []
    for (variant, source_start), group in frame.groupby(["variant", "requested_start_month"], sort=True):
        for apply_staggered in (False, True):
            rows, worst = _audit_one_group(
                variant=str(variant),
                source_start=str(source_start),
                group=group,
                apply_staggered=apply_staggered,
                sleeve_offsets=offsets,
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


def build_original_start_staggered_panel(
    panel_curves: pd.DataFrame,
    *,
    target_variants: list[str],
    sleeve_offsets: tuple[int, ...] | list[int] = SLEEVE_OFFSETS,
) -> pd.DataFrame:
    offsets = _normalize_offsets(sleeve_offsets)
    frame = panel_curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[frame["variant"].isin(target_variants)].dropna(subset=["date", "equity"]).copy()
    parts = [frame[["variant", "requested_start_month", "date", "equity"]]]
    staged_frames: list[pd.DataFrame] = []
    for (variant, source), group in frame.groupby(["variant", "requested_start_month"], sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        staged = group[["requested_start_month", "date"]].copy()
        staged["variant"] = f"{variant}{STAGGERED_SUFFIX}"
        staged["equity"] = apply_staggered_sleeve_deployment_to_equity(
            group["equity"],
            sleeve_offsets=offsets,
        )
        staged["stage075_sleeve_offsets"] = ",".join(str(item) for item in offsets)
        staged["stage075_sleeve_count"] = len(offsets)
        staged["stage075_sleeve_multiplier"] = compute_staggered_sleeve_multiplier(
            len(group),
            sleeve_offsets=offsets,
        )
        staged["requested_start_month"] = str(source)
        staged_frames.append(staged)
    if staged_frames:
        parts.append(pd.concat(staged_frames, ignore_index=True, sort=False))
    return pd.concat(parts, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True)


def _source_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in panel.groupby(["variant", "requested_start_month"], sort=True):
        g = group.sort_values("date").copy()
        equity = pd.to_numeric(g["equity"], errors="coerce")
        multiplier = pd.to_numeric(g.get("stage075_sleeve_multiplier"), errors="coerce")
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
                "mean_sleeve_multiplier": float(multiplier.mean()) if not multiplier.isna().all() else 1.0,
                "min_sleeve_multiplier": float(multiplier.min()) if not multiplier.isna().all() else 1.0,
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
    target_c = f"{TARGET_VARIANT}{STAGGERED_SUFFIX}"
    target_rows = variant_summary[variant_summary["variant"].eq(target_c)]
    target = target_rows.iloc[0].to_dict() if not target_rows.empty else {}
    negative_count = int(target.get("all_gt1y_negative_count", 0)) if target else 0
    retention_pass = int(target.get("retention_vs_base_stage006_pass_count", 0)) if target else 0
    retention_rows = int(target.get("retention_rows", 0)) if target else 0
    if target and negative_count == 0 and retention_pass == retention_rows and retention_rows > 0:
        decision = "stage075_staggered_sleeve_proxy_passes_goal_needs_true_deployment_review"
        next_stage = "进入真实部署层/日级冷启动更宽验证，严查收益保留、成本和保证金，不直接上线"
    else:
        decision = "stage075_staggered_sleeve_proxy_not_goal_no_param_rescue"
        next_stage = "停止 sleeve_count/offset 救参；若继续账户外层，需要不同结构或新 PIT 信息源"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "arms": {
            "A": BASE_VARIANT,
            "B": f"{BASE_VARIANT}{STAGGERED_SUFFIX}",
            "C0": TARGET_VARIANT,
            "C": target_c,
        },
        "sleeve_offsets": list(SLEEVE_OFFSETS),
        "sleeve_count": len(SLEEVE_OFFSETS),
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
            "Managed futures and pysystemtrade references support portfolio-level allocation, risk targeting, "
            "and capital correction, but warn that overlay choices can damage trend-following right tails; "
            "this stage freezes quarterly staged sleeves instead of tuning signal/product/date filters."
        ),
        "overfit_reflection_before": (
            "否。候选是账户部署结构，固定 4 个等权袖和 0/63/126/189 交易日投入，不按坏窗口调参。"
        ),
        "overfit_reflection_after": (
            "待运行后填写；若失败后继续扫袖数、offset 或按 2022 窗口定制，就是过拟合。"
        ),
        "continue_value_before": "有。任意起点目标本质包含冷启动路径依赖，分批部署直接针对该结构问题。",
        "continue_value_after": "待运行后填写。",
        "outputs": {
            "panel_curves": str(PANEL_CURVES_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "retention": str(RETENTION_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
            "target_absolute_equity_focus_chart": str(TARGET_FOCUS_CHART_PATH),
        },
    }


def _write_absolute_equity_charts(panel: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    frame = panel.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["date", "equity"])
    variants = [
        BASE_VARIANT,
        f"{BASE_VARIANT}{STAGGERED_SUFFIX}",
        TARGET_VARIANT,
        f"{TARGET_VARIANT}{STAGGERED_SUFFIX}",
    ]
    titles = {
        BASE_VARIANT: "A: Stage013 engine",
        f"{BASE_VARIANT}{STAGGERED_SUFFIX}": "B: Stage013 + staggered sleeves",
        TARGET_VARIANT: "C0: AI top8 + active<3",
        f"{TARGET_VARIANT}{STAGGERED_SUFFIX}": "C: C0 + staggered sleeves",
    }
    starts = sorted(frame["requested_start_month"].astype(str).unique())
    colors = plt.cm.viridis([i / max(1, len(starts) - 1) for i in range(len(starts))])
    color_by_start = dict(zip(starts, colors))

    def money_fmt(value: float, _pos: int) -> str:
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"{value / 1_000:.0f}k"
        return f"{value:.0f}"

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex=True)
    axes = axes.flatten()
    for ax, variant in zip(axes, variants):
        part = frame[frame["variant"].eq(variant)]
        for start in starts:
            line = part[part["requested_start_month"].astype(str).eq(start)]
            if line.empty:
                continue
            ax.plot(
                line["date"],
                line["equity"],
                color=color_by_start[start],
                lw=1.45 if start.endswith("-01") else 0.95,
                alpha=0.72 if start.endswith("-01") else 0.38,
            )
        ax.axhline(CAPITAL, color="#6b7280", lw=0.9, ls="--", alpha=0.75)
        ax.set_title(titles.get(variant, variant), fontsize=12, loc="left")
        ax.yaxis.set_major_formatter(FuncFormatter(money_fmt))
        ax.set_ylabel("Absolute equity (CNY)")
        ax.margins(x=0.01)
    handles = []
    labels = []
    for start in starts:
        if start.endswith("-01"):
            handle, = axes[-1].plot([], [], color=color_by_start[start], lw=2, label=start)
            handles.append(handle)
            labels.append(start)
    fig.suptitle("Stage075 absolute equity curves by requested start month", fontsize=16, y=0.98)
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=min(9, len(labels)),
        frameon=False,
        title="January starts shown in legend; July starts are lighter lines",
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.95])
    fig.savefig(ABSOLUTE_EQUITY_CHART_PATH, dpi=180)
    plt.close(fig)

    focus_starts = ["2020-01", "2021-07", "2022-07", "2025-01"]
    focus_variants = [TARGET_VARIANT, f"{TARGET_VARIANT}{STAGGERED_SUFFIX}"]
    styles = {
        TARGET_VARIANT: dict(color="#0f766e", lw=2.0, ls="-", label="C0 AI top8 active<3"),
        f"{TARGET_VARIANT}{STAGGERED_SUFFIX}": dict(color="#b91c1c", lw=2.0, ls="--", label="C staggered sleeves"),
    }
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    axes = axes.flatten()
    for ax, start in zip(axes, focus_starts):
        for variant in focus_variants:
            line = frame[frame["variant"].eq(variant) & frame["requested_start_month"].astype(str).eq(start)]
            if line.empty:
                continue
            ax.plot(line["date"], line["equity"], **styles[variant])
            ax.scatter(line["date"].iloc[-1], line["equity"].iloc[-1], s=22, color=styles[variant]["color"])
        ax.axhline(CAPITAL, color="#6b7280", lw=0.9, ls="--", alpha=0.75)
        ax.set_title(f"Requested start {start}", fontsize=12, loc="left")
        ax.yaxis.set_major_formatter(FuncFormatter(money_fmt))
        ax.set_ylabel("Absolute equity (CNY)")
        ax.margins(x=0.01)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:2], labels[:2], loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Stage075 target absolute equity focus", fontsize=16, y=0.98)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    fig.savefig(TARGET_FOCUS_CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    variant_summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
) -> str:
    lines = [
        "# Stage075 staggered sleeve deployment proxy",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：{decision['next_stage']}",
        f"- A/B/C：A=`{decision['arms']['A']}`，B=`{decision['arms']['B']}`，C0=`{decision['arms']['C0']}`，C=`{decision['arms']['C']}`",
        f"- 固定参数：`sleeve_offsets={decision['sleeve_offsets']}`，`sleeve_count={decision['sleeve_count']}`。",
        "",
        "## 外部调研判断",
        "",
        "- Managed futures/pysystemtrade 资料支持组合层 allocation、risk target 与 capital correction；但趋势右尾脆弱，失败后不能扫袖数、offset 或坏窗口。",
        "- 本阶段只验证一个固定账户部署结构，不改信号、不改 AI 池、不改品种、不按坏窗口调参数。",
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
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage075_staggered_sleeve_deployment_proxy.md"
    lines = [
        "# Stage075 分批多袖账户部署 proxy",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：否",
        "- 新增参数：`stage075_sleeve_offsets=(0,63,126,189)`、`stage075_sleeve_count=4`。",
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
    staged_panel = build_original_start_staggered_panel(panel, target_variants=target_variants)
    source_summary = _source_summary(staged_panel)
    retention = _retention(source_summary)
    aggregate, worst = run_dense_staggered_goal_audit(panel, target_variants=target_variants)
    variant_summary = _variant_goal_summary(aggregate, source_summary, retention)
    decision = _decision(variant_summary)

    target_c = decision["arms"]["C"]
    target_row = variant_summary[variant_summary["variant"].eq(target_c)]
    if not target_row.empty and int(target_row.iloc[0]["all_gt1y_negative_count"]) == 0:
        decision["overfit_reflection_after"] = "否。本阶段没有调袖数或 offset；若进入下一步也必须做真部署层验证。"
        decision["continue_value_after"] = "有，但必须验证真实部署、成本和保证金，不能直接上线。"
    else:
        decision["overfit_reflection_after"] = "否。本阶段没有根据结果调整袖数或 offset；若失败后继续扫这些参数就是过拟合。"
        decision["continue_value_after"] = "该固定分袖形状若不达标就无救参价值；应转新 PIT 信息源或不同账户外层结构。"

    _write_absolute_equity_charts(staged_panel)
    report = _write_report(decision, variant_summary, aggregate, worst)
    stage_record = _write_stage_record(report, decision)
    decision["outputs"]["stage_record"] = str(stage_record)

    staged_panel.to_csv(PANEL_CURVES_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(report, encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
