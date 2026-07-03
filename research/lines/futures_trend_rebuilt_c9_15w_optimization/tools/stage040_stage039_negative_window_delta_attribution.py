from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage040"
MODEL_TAG = "stage040_stage039_negative_window_delta_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage040_stage039_negative_window_delta_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage040_stage039_negative_window_delta_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE039_OUTPUT_DIR = LINE_DIR / "outputs" / "stage039_full_market_ai_top8_proxy"
STAGE039_PREFIX = "rebuilt_c9_stage039_full_market_ai_top8_proxy"
STAGE039_TAG = "stage039_full_market_ai_top8_proxy_v1"

CURVES_PATH = STAGE039_OUTPUT_DIR / f"{STAGE039_PREFIX}_curves_{STAGE039_TAG}.csv"
LOT_DELTAS_PATH = STAGE039_OUTPUT_DIR / f"{STAGE039_PREFIX}_lot_deltas_{STAGE039_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
BY_SOURCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_source_{MODEL_TAG}.csv"
TOP_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_windows_{MODEL_TAG}.csv"
LOT_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_window_lot_attribution_{MODEL_TAG}.csv"
PRODUCT_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_window_product_attribution_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
WORST_PER_START_PER_CLASS = 3
TOP_WINDOW_ROWS = 1000
TOP_ATTRIBUTION_WINDOWS = 80


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
        return None if np.isnan(number) or np.isinf(number) else number
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


def _ret_pct(start_equity: float, end_equity: float) -> float:
    if abs(float(start_equity)) <= 1e-12:
        return np.nan
    return float((float(end_equity) / float(start_equity) - 1.0) * 100.0)


def _classify_window_effect(
    *,
    source_start_month: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    stage013_start_equity: float,
    stage013_end_equity: float,
    stage039_start_equity: float,
    stage039_end_equity: float,
) -> dict[str, Any]:
    stage013_return = _ret_pct(stage013_start_equity, stage013_end_equity)
    stage039_return = _ret_pct(stage039_start_equity, stage039_end_equity)
    stage013_negative = bool(pd.notna(stage013_return) and stage013_return < 0.0)
    stage039_negative = bool(pd.notna(stage039_return) and stage039_return < 0.0)
    if stage013_negative and stage039_negative:
        window_class = "both_negative"
    elif stage013_negative and not stage039_negative:
        window_class = "fixed_by_stage039"
    elif not stage013_negative and stage039_negative:
        window_class = "added_negative_by_stage039"
    else:
        window_class = "both_non_negative"
    start_delta = float(stage039_start_equity - stage013_start_equity)
    end_delta = float(stage039_end_equity - stage013_end_equity)
    in_window_delta = float(end_delta - start_delta)
    absolute_end_ge = int(stage039_end_equity >= stage013_end_equity)
    denominator_effect = int(window_class == "added_negative_by_stage039" and absolute_end_ge == 1)
    return {
        "source_start_month": str(source_start_month),
        "start_date": pd.Timestamp(start_date).date().isoformat(),
        "end_date": pd.Timestamp(end_date).date().isoformat(),
        "period_calendar_days": int((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days),
        "stage013_return_pct": stage013_return,
        "stage039_return_pct": stage039_return,
        "return_delta_pp_stage039_vs_stage013": float(stage039_return - stage013_return)
        if pd.notna(stage013_return) and pd.notna(stage039_return)
        else np.nan,
        "window_class": window_class,
        "stage013_start_equity": float(stage013_start_equity),
        "stage013_end_equity": float(stage013_end_equity),
        "stage039_start_equity": float(stage039_start_equity),
        "stage039_end_equity": float(stage039_end_equity),
        "stage039_start_delta_vs_stage013": start_delta,
        "stage039_end_delta_vs_stage013": end_delta,
        "stage039_in_window_delta": in_window_delta,
        "stage039_absolute_end_ge_stage013": absolute_end_ge,
        "stage039_added_negative_denominator_effect": denominator_effect,
    }


def _load_curves() -> pd.DataFrame:
    curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig", parse_dates=["date"])
    required = ["requested_start_month", "date", "account_equity", "stage039_account_equity"]
    missing = [column for column in required if column not in curves.columns]
    if missing:
        raise ValueError(f"missing curve columns: {missing}")
    curves = curves[required].copy()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    curves["stage039_account_equity"] = pd.to_numeric(curves["stage039_account_equity"], errors="coerce")
    return curves.dropna(subset=["date", "account_equity", "stage039_account_equity"]).sort_values(
        ["requested_start_month", "date"]
    )


def _top_indices(mask: np.ndarray, scores: np.ndarray, limit: int) -> np.ndarray:
    positions = np.flatnonzero(mask)
    if len(positions) == 0:
        return positions
    selected = positions[np.argsort(scores[positions])[:limit]]
    return selected


def _select_top_windows(windows: pd.DataFrame, per_class_limit: int) -> pd.DataFrame:
    if windows.empty:
        return windows.copy()
    frames: list[pd.DataFrame] = []
    order = {
        "both_negative": ("stage039_return_pct", True),
        "added_negative_by_stage039": ("stage039_return_pct", True),
        "fixed_by_stage039": ("stage013_return_pct", True),
    }
    for window_class, (sort_column, ascending) in order.items():
        subset = windows[windows["window_class"].eq(window_class)].copy()
        if subset.empty:
            continue
        frames.append(subset.sort_values(sort_column, ascending=ascending).head(per_class_limit))
    if not frames:
        return windows.head(0).copy()
    return pd.concat(frames, ignore_index=True, sort=False)


def _analyze_source(source_start_month: str, group: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = data["date"].to_numpy(dtype="datetime64[ns]")
    base = data["account_equity"].to_numpy(dtype=float)
    proxy = data["stage039_account_equity"].to_numpy(dtype=float)
    objective_mask = (data["date"] >= OBJECTIVE_START_MIN) & (data["date"] <= OBJECTIVE_START_MAX)
    start_indices = np.flatnonzero(objective_mask.to_numpy())

    stats = {
        "source_start_month": source_start_month,
        "window_count": 0,
        "stage013_negative_count": 0,
        "stage039_negative_count": 0,
        "both_negative_count": 0,
        "fixed_by_stage039_count": 0,
        "added_negative_by_stage039_count": 0,
        "both_non_negative_count": 0,
        "added_negative_absolute_end_ge_stage013_count": 0,
        "added_negative_absolute_end_lt_stage013_count": 0,
        "added_negative_denominator_effect_count": 0,
        "stage013_min_return_pct": np.nan,
        "stage039_min_return_pct": np.nan,
        "stage039_min_in_window_delta": np.nan,
        "stage039_sum_in_window_delta_on_added_negatives": 0.0,
    }
    top_rows: list[dict[str, Any]] = []
    min_stage013 = np.inf
    min_stage039 = np.inf
    min_in_window_delta = np.inf

    for start_idx in start_indices:
        start_date = pd.Timestamp(dates[start_idx])
        min_end_date = start_date + pd.Timedelta(days=MIN_PERIOD_CALENDAR_DAYS)
        min_end_idx = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_idx >= len(dates):
            continue
        end_indices = np.arange(min_end_idx, len(dates), dtype=int)
        stage013_start = float(base[start_idx])
        stage039_start = float(proxy[start_idx])
        if abs(stage013_start) <= 1e-12 or abs(stage039_start) <= 1e-12:
            continue
        stage013_returns = (base[end_indices] / stage013_start - 1.0) * 100.0
        stage039_returns = (proxy[end_indices] / stage039_start - 1.0) * 100.0
        valid = np.isfinite(stage013_returns) & np.isfinite(stage039_returns)
        if not valid.any():
            continue
        end_indices = end_indices[valid]
        stage013_returns = stage013_returns[valid]
        stage039_returns = stage039_returns[valid]
        stage013_negative = stage013_returns < 0.0
        stage039_negative = stage039_returns < 0.0
        both_negative = stage013_negative & stage039_negative
        fixed = stage013_negative & ~stage039_negative
        added = ~stage013_negative & stage039_negative
        both_non_negative = ~stage013_negative & ~stage039_negative
        start_delta = stage039_start - stage013_start
        end_delta = proxy[end_indices] - base[end_indices]
        in_window_delta = end_delta - start_delta

        stats["window_count"] += int(len(end_indices))
        stats["stage013_negative_count"] += int(stage013_negative.sum())
        stats["stage039_negative_count"] += int(stage039_negative.sum())
        stats["both_negative_count"] += int(both_negative.sum())
        stats["fixed_by_stage039_count"] += int(fixed.sum())
        stats["added_negative_by_stage039_count"] += int(added.sum())
        stats["both_non_negative_count"] += int(both_non_negative.sum())
        stats["added_negative_absolute_end_ge_stage013_count"] += int((added & (end_delta >= 0.0)).sum())
        stats["added_negative_absolute_end_lt_stage013_count"] += int((added & (end_delta < 0.0)).sum())
        stats["added_negative_denominator_effect_count"] += int((added & (end_delta >= 0.0)).sum())
        stats["stage039_sum_in_window_delta_on_added_negatives"] += float(in_window_delta[added].sum()) if added.any() else 0.0
        min_stage013 = min(min_stage013, float(stage013_returns.min()))
        min_stage039 = min(min_stage039, float(stage039_returns.min()))
        min_in_window_delta = min(min_in_window_delta, float(in_window_delta.min()))

        candidate_positions = []
        candidate_positions.extend(_top_indices(added, stage039_returns, WORST_PER_START_PER_CLASS).tolist())
        candidate_positions.extend(_top_indices(both_negative, stage039_returns, WORST_PER_START_PER_CLASS).tolist())
        candidate_positions.extend(_top_indices(fixed, stage013_returns, WORST_PER_START_PER_CLASS).tolist())
        for local_pos in sorted(set(candidate_positions)):
            end_idx = int(end_indices[local_pos])
            top_rows.append(
                _classify_window_effect(
                    source_start_month=source_start_month,
                    start_date=start_date,
                    end_date=pd.Timestamp(dates[end_idx]),
                    stage013_start_equity=stage013_start,
                    stage013_end_equity=float(base[end_idx]),
                    stage039_start_equity=stage039_start,
                    stage039_end_equity=float(proxy[end_idx]),
                )
            )

    stats["stage013_min_return_pct"] = float(min_stage013) if np.isfinite(min_stage013) else np.nan
    stats["stage039_min_return_pct"] = float(min_stage039) if np.isfinite(min_stage039) else np.nan
    stats["stage039_min_in_window_delta"] = float(min_in_window_delta) if np.isfinite(min_in_window_delta) else np.nan
    return stats, top_rows


def _transition_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    by_source_rows: list[dict[str, Any]] = []
    top_rows: list[dict[str, Any]] = []
    for source, group in curves.groupby("requested_start_month", sort=True):
        stats, rows = _analyze_source(str(source), group)
        by_source_rows.append(stats)
        top_rows.extend(rows)
    by_source = pd.DataFrame(by_source_rows)
    numeric_columns = [column for column in by_source.columns if column != "source_start_month"]
    summary = by_source[numeric_columns].sum(numeric_only=True).to_frame().T
    summary.insert(0, "scope", "all_sources")
    if not by_source.empty:
        summary["stage013_min_return_pct"] = float(by_source["stage013_min_return_pct"].min())
        summary["stage039_min_return_pct"] = float(by_source["stage039_min_return_pct"].min())
        summary["stage039_min_in_window_delta"] = float(by_source["stage039_min_in_window_delta"].min())
    summary["net_negative_window_change_stage039_minus_stage013"] = (
        summary["stage039_negative_count"] - summary["stage013_negative_count"]
    )
    summary["added_minus_fixed_negative_count"] = (
        summary["added_negative_by_stage039_count"] - summary["fixed_by_stage039_count"]
    )
    summary["added_negative_denominator_effect_rate_pct"] = np.where(
        summary["added_negative_by_stage039_count"].gt(0),
        summary["added_negative_denominator_effect_count"] / summary["added_negative_by_stage039_count"] * 100.0,
        np.nan,
    )
    top = pd.DataFrame(top_rows)
    if not top.empty:
        top = _select_top_windows(top, TOP_WINDOW_ROWS).reset_index(drop=True)
    return summary, by_source, top


def _lot_attribution(top_windows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if top_windows.empty or not LOT_DELTAS_PATH.exists():
        return pd.DataFrame(), pd.DataFrame()
    lots = pd.read_csv(LOT_DELTAS_PATH, encoding="utf-8-sig", parse_dates=["entry_date", "exit_date"])
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["stage039_proxy_delta_pnl"] = pd.to_numeric(lots["stage039_proxy_delta_pnl"], errors="coerce").fillna(0.0)
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    selected_windows = top_windows.head(TOP_ATTRIBUTION_WINDOWS).copy()
    rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    for window_id, row in selected_windows.reset_index(drop=True).iterrows():
        source = str(row["source_start_month"])
        start = pd.Timestamp(row["start_date"]).normalize()
        end = pd.Timestamp(row["end_date"]).normalize()
        subset = lots[
            lots["requested_start_month"].eq(source) & lots["exit_date"].gt(start) & lots["exit_date"].le(end)
        ].copy()
        rows.append(
            {
                "window_id": int(window_id),
                "source_start_month": source,
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "window_class": row["window_class"],
                "stage039_in_window_delta_from_curve": float(row["stage039_in_window_delta"]),
                "selected_lot_count": int(len(subset)),
                "selected_lot_delta_sum": float(subset["stage039_proxy_delta_pnl"].sum()) if not subset.empty else 0.0,
                "selected_lot_realized_pnl_sum": float(subset["realized_pnl"].sum()) if not subset.empty else 0.0,
                "selected_lot_positive_count": int(subset["stage039_proxy_delta_pnl"].gt(0).sum()) if not subset.empty else 0,
                "selected_lot_negative_count": int(subset["stage039_proxy_delta_pnl"].lt(0).sum()) if not subset.empty else 0,
            }
        )
        if not subset.empty:
            grouped = (
                subset.groupby(["product", "direction"], dropna=False)
                .agg(
                    selected_lot_count=("lot_id", "count"),
                    selected_lot_delta_sum=("stage039_proxy_delta_pnl", "sum"),
                    selected_lot_realized_pnl_sum=("realized_pnl", "sum"),
                )
                .reset_index()
                .sort_values("selected_lot_delta_sum")
            )
            for _, item in grouped.iterrows():
                product_rows.append(
                    {
                        "window_id": int(window_id),
                        "source_start_month": source,
                        "start_date": start.date().isoformat(),
                        "end_date": end.date().isoformat(),
                        "window_class": row["window_class"],
                        "product": item.get("product"),
                        "direction": item.get("direction"),
                        "selected_lot_count": int(item["selected_lot_count"]),
                        "selected_lot_delta_sum": float(item["selected_lot_delta_sum"]),
                        "selected_lot_realized_pnl_sum": float(item["selected_lot_realized_pnl_sum"]),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(product_rows)


def _decision(summary: pd.DataFrame, by_source: pd.DataFrame, top_windows: pd.DataFrame) -> dict[str, Any]:
    row = summary.iloc[0].to_dict() if not summary.empty else {}
    added = int(row.get("added_negative_by_stage039_count", 0))
    fixed = int(row.get("fixed_by_stage039_count", 0))
    absolute_worse_added = int(row.get("added_negative_absolute_end_lt_stage013_count", 0))
    denominator_added = int(row.get("added_negative_denominator_effect_count", 0))
    if added > fixed and absolute_worse_added > denominator_added:
        decision = "stage040_stage039_left_tail_worsening_is_real_window_delta_not_denominator"
        next_step = (
            "Stage039 新增负窗口主要是窗口内 delta 变差，不是纯分母效应；后续不要救 full_market_top8，"
            "应转向账户外层或新外生源。"
        )
    elif added > fixed:
        decision = "stage040_stage039_added_negatives_mixed_with_denominator_effect"
        next_step = "Stage039 新增负窗口含显著分母效应；后续需要分别看绝对权益和收益率目标。"
    else:
        decision = "stage040_stage039_negative_window_migration_not_primary_failure"
        next_step = "Stage039 负窗口迁移不是主失败，后续回到剩余 common-negative 左尾。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "stage013_vs_stage039_exhaustive_negative_window_transition_attribution",
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "window_count": int(row.get("window_count", 0)),
        "stage013_negative_count": int(row.get("stage013_negative_count", 0)),
        "stage039_negative_count": int(row.get("stage039_negative_count", 0)),
        "net_negative_window_change_stage039_minus_stage013": int(
            row.get("net_negative_window_change_stage039_minus_stage013", 0)
        ),
        "both_negative_count": int(row.get("both_negative_count", 0)),
        "fixed_by_stage039_count": fixed,
        "added_negative_by_stage039_count": added,
        "added_negative_absolute_end_ge_stage013_count": int(row.get("added_negative_absolute_end_ge_stage013_count", 0)),
        "added_negative_absolute_end_lt_stage013_count": absolute_worse_added,
        "added_negative_denominator_effect_count": denominator_added,
        "added_negative_denominator_effect_rate_pct": float(row.get("added_negative_denominator_effect_rate_pct", np.nan)),
        "stage013_min_return_pct": float(row.get("stage013_min_return_pct", np.nan)),
        "stage039_min_return_pct": float(row.get("stage039_min_return_pct", np.nan)),
        "top_window_rows": int(len(top_windows)),
        "external_research_judgment": (
            "趋势跟随文献和 managed futures 实务更强调风险预算、波动目标和回撤承受域；"
            "Stage040 只做左尾窗口迁移诊断，不把 single signal bet sizing 当成目标解。"
        ),
        "overfit_reflection_before": (
            "否。本阶段不新增交易规则、不扫参数，只解释 Stage039 为什么右尾增强但严格目标失败。"
        ),
        "overfit_reflection_after": (
            "否。输出是窗口迁移和 delta 归因；若据此反推日期/品种/方向过滤才会过拟合。"
        ),
        "continue_value_before": "有。必须先确认失败来自真实窗口内亏损还是收益率分母效应，才能决定下一条路线。",
        "continue_value_after": next_step,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "by_source": str(BY_SOURCE_PATH),
            "top_windows": str(TOP_WINDOWS_PATH),
            "lot_attribution": str(LOT_ATTRIBUTION_PATH),
            "product_attribution": str(PRODUCT_ATTRIBUTION_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    by_source: pd.DataFrame,
    top_windows: pd.DataFrame,
    lot_attribution: pd.DataFrame,
    product_attribution: pd.DataFrame,
) -> None:
    added = top_windows[top_windows["window_class"].eq("added_negative_by_stage039")] if not top_windows.empty else pd.DataFrame()
    both = top_windows[top_windows["window_class"].eq("both_negative")] if not top_windows.empty else pd.DataFrame()
    lines = [
        "# Stage040 - Stage039 负窗口迁移与 delta 归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读诊断；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 核心结论",
        "",
        f"- Stage013 负窗口：`{decision['stage013_negative_count']}`；Stage039 负窗口：`{decision['stage039_negative_count']}`；净变化：`{decision['net_negative_window_change_stage039_minus_stage013']}`。",
        f"- Stage039 修复 Stage013 负窗口：`{decision['fixed_by_stage039_count']}`；新增负窗口：`{decision['added_negative_by_stage039_count']}`。",
        f"- 新增负窗口中，Stage039 绝对期末权益仍不低于 Stage013 的分母效应窗口：`{decision['added_negative_denominator_effect_count']}`；绝对期末权益更低的真实 delta 变差窗口：`{decision['added_negative_absolute_end_lt_stage013_count']}`。",
        f"- Stage013 最差收益：`{decision['stage013_min_return_pct']:.4f}%`；Stage039 最差收益：`{decision['stage039_min_return_pct']:.4f}%`。",
        "",
        "## 汇总",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## 分 source",
        "",
        _md_table(
            by_source[
                [
                    "source_start_month",
                    "stage013_negative_count",
                    "stage039_negative_count",
                    "fixed_by_stage039_count",
                    "added_negative_by_stage039_count",
                    "added_negative_absolute_end_lt_stage013_count",
                    "stage013_min_return_pct",
                    "stage039_min_return_pct",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 新增负窗口样例",
        "",
        _md_table(
            added[
                [
                    "source_start_month",
                    "start_date",
                    "end_date",
                    "stage013_return_pct",
                    "stage039_return_pct",
                    "stage039_in_window_delta",
                    "stage039_added_negative_denominator_effect",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 双负窗口样例",
        "",
        _md_table(
            both[
                [
                    "source_start_month",
                    "start_date",
                    "end_date",
                    "stage013_return_pct",
                    "stage039_return_pct",
                    "stage039_in_window_delta",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Top 窗口 lot delta 归因",
        "",
        _md_table(lot_attribution, max_rows=20),
        "",
        "## Top 窗口产品方向归因",
        "",
        _md_table(product_attribution, max_rows=30),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame, by_source: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage040_stage039_negative_window_delta_attribution.md"
    lines = [
        "# Stage040 - Stage039 负窗口迁移与 delta 归因",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage040_stage039_negative_window_delta_attribution.py`",
        "- 新增参数：无交易参数；诊断常量 `MIN_PERIOD_CALENDAR_DAYS=366`、`OBJECTIVE_START_MIN=2020-01-01`、`OBJECTIVE_START_MAX=2025-06-30`。",
        "- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：Stage013 vs Stage039 严格窗口迁移与 lot delta 归因；不是真实组合引擎。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- Stage013 负窗口：`{decision['stage013_negative_count']}`。",
        f"- Stage039 负窗口：`{decision['stage039_negative_count']}`。",
        f"- 净变化：`{decision['net_negative_window_change_stage039_minus_stage013']}`。",
        f"- 修复负窗口：`{decision['fixed_by_stage039_count']}`。",
        f"- 新增负窗口：`{decision['added_negative_by_stage039_count']}`。",
        f"- 新增负窗口里分母效应：`{decision['added_negative_denominator_effect_count']}`。",
        f"- 新增负窗口里绝对期末权益更低：`{decision['added_negative_absolute_end_lt_stage013_count']}`。",
        f"- Stage013 最差收益：`{decision['stage013_min_return_pct']:.4f}%`。",
        f"- Stage039 最差收益：`{decision['stage039_min_return_pct']:.4f}%`。",
        "",
        "## 分 source 摘要",
        "",
        _md_table(
            by_source[
                [
                    "source_start_month",
                    "stage013_negative_count",
                    "stage039_negative_count",
                    "fixed_by_stage039_count",
                    "added_negative_by_stage039_count",
                    "added_negative_absolute_end_lt_stage013_count",
                    "stage013_min_return_pct",
                    "stage039_min_return_pct",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 输出",
        "",
        f"- summary：`{SUMMARY_PATH}`",
        f"- by_source：`{BY_SOURCE_PATH}`",
        f"- top_windows：`{TOP_WINDOWS_PATH}`",
        f"- lot_attribution：`{LOT_ATTRIBUTION_PATH}`",
        f"- product_attribution：`{PRODUCT_ATTRIBUTION_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    curves = _load_curves()
    summary, by_source, top_windows = _transition_audit(curves)
    lot_attr, product_attr = _lot_attribution(top_windows)
    decision = _decision(summary, by_source, top_windows)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_source.to_csv(BY_SOURCE_PATH, index=False, encoding="utf-8-sig")
    top_windows.to_csv(TOP_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    lot_attr.to_csv(LOT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, summary, by_source, top_windows, lot_attr, product_attr)
    stage_record = _write_stage_record(decision, summary, by_source)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
