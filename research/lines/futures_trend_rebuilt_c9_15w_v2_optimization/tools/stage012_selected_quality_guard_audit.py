from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage012"
MODEL_TAG = "stage012_selected_quality_guard_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage012_selected_quality_guard_audit"
ADD_RISK_FRACTION = 0.25

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_meta_label_entry_quality_audit as s009


LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage012_selected_quality_guard_audit"

STAGE010_OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_quality_add_risk_proxy"
STAGE010_PREFIX = "rebuilt_c9_v2_stage010_quality_add_risk_proxy"
STAGE010_TAG = "stage010_quality_add_risk_proxy_v1"
STAGE010_LOT_DELTAS_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_lot_deltas_{STAGE010_TAG}.csv.gz"

STAGE011_OUTPUT_DIR = LINE_DIR / "outputs" / "stage011_stage010_remaining_left_tail_attribution"
STAGE011_PREFIX = "rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution"
STAGE011_TAG = "stage011_stage010_remaining_left_tail_attribution_v1"
STAGE011_FOCUS_WINDOWS_PATH = STAGE011_OUTPUT_DIR / f"{STAGE011_PREFIX}_focus_windows_{STAGE011_TAG}.csv"

TAGGED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tagged_lots_{MODEL_TAG}.csv.gz"
GUARD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_guard_summary_{MODEL_TAG}.csv"
GUARD_YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_guard_year_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_guard_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0445_stage012_selected_quality_guard_audit.md"

DEFAULT_MIN_RETAINED_COUNT = 500
DEFAULT_MIN_YEAR_COUNT = 5
DEFAULT_MIN_RETAINED_TOTAL_PNL_SHARE_PCT = 80.0
DEFAULT_MIN_FOCUS_PROXY_IMPROVEMENT = 1.0


def _json_safe(value: Any) -> Any:
    return s009._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009._md_table(frame, max_rows=max_rows or 20)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _pctize(series: pd.Series) -> pd.Series:
    return s009._pctize(series)


def _directional_rsi_follow(lots: pd.DataFrame) -> pd.Series:
    direction = lots.get("direction", pd.Series("", index=lots.index)).astype(str).str.lower()
    rsi = _numeric(lots, "rsi_value")
    return (direction.eq("long") & rsi.ge(60)) | (direction.eq("short") & rsi.le(40))


def _directional_rsi_extreme(lots: pd.DataFrame) -> pd.Series:
    direction = lots.get("direction", pd.Series("", index=lots.index)).astype(str).str.lower()
    rsi = _numeric(lots, "rsi_value")
    return (direction.eq("long") & rsi.ge(75)) | (direction.eq("short") & rsi.le(25))


def _trend_aligned(lots: pd.DataFrame) -> pd.Series:
    direction = lots.get("direction", pd.Series("", index=lots.index)).astype(str).str.lower()
    bullish = _numeric(lots, "bullish_alignment").fillna(0.0)
    bearish = _numeric(lots, "bearish_alignment").fillna(0.0)
    return (direction.eq("long") & bullish.eq(1.0)) | (direction.eq("short") & bearish.eq(1.0))


def _corr_present(lots: pd.DataFrame) -> pd.Series:
    active = _numeric(lots, "same_direction_correlation_active_count").fillna(0.0)
    max_corr = _numeric(lots, "same_direction_correlation_max_corr").fillna(0.0)
    return active.gt(0.0) | max_corr.gt(0.0)


def _prepare_lots(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["requested_start_month"] = data.get("requested_start_month", "").astype(str)
    data["entry_date"] = pd.to_datetime(data.get("entry_date"), errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data.get("exit_date"), errors="coerce").dt.normalize()
    data["realized_pnl"] = _numeric(data, "realized_pnl", 0.0).fillna(0.0)
    if "entry_year" not in data.columns:
        data["entry_year"] = data["entry_date"].dt.year
    data["entry_year"] = pd.to_numeric(data["entry_year"], errors="coerce")
    if "portfolio_drawdown_abs_pct" not in data.columns and "portfolio_drawdown_pct" in data.columns:
        data["portfolio_drawdown_abs_pct"] = _pctize(data["portfolio_drawdown_pct"]).abs()
    if "entry_risk_distance_pct_abs" not in data.columns and "entry_risk_distance_pct" in data.columns:
        data["entry_risk_distance_pct_abs"] = _pctize(data["entry_risk_distance_pct"]).abs()
    if "stage010_proxy_delta_pnl" not in data.columns:
        data["stage010_proxy_delta_pnl"] = data["realized_pnl"] * ADD_RISK_FRACTION
    data["stage010_proxy_delta_pnl"] = _numeric(data, "stage010_proxy_delta_pnl", 0.0).fillna(0.0)
    if "bad_path" not in data.columns:
        data["bad_path"] = data["realized_pnl"].lt(0).astype(int)
    data["bad_path"] = _numeric(data, "bad_path", 0.0).fillna(0.0)
    if "big_winner" not in data.columns:
        data["big_winner"] = 0
    data["big_winner"] = _numeric(data, "big_winner", 0.0).fillna(0.0)
    return data.reset_index(drop=True)


def mark_focus_membership(lots: pd.DataFrame, focus_windows: pd.DataFrame) -> pd.DataFrame:
    data = _prepare_lots(lots)
    focus = focus_windows.copy()
    if focus.empty:
        data["stage011_focus_window_hit"] = 0
        data["stage011_focus_window_hit_count"] = 0
        return data
    focus["source_start_month"] = focus["source_start_month"].astype(str)
    focus["start_date"] = pd.to_datetime(focus["start_date"], errors="coerce").dt.normalize()
    focus["end_date"] = pd.to_datetime(focus["end_date"], errors="coerce").dt.normalize()
    hit_count = pd.Series(0, index=data.index, dtype="int64")
    for _, window in focus.dropna(subset=["start_date", "end_date"]).iterrows():
        in_window = (
            data["requested_start_month"].eq(str(window["source_start_month"]))
            & data["exit_date"].gt(window["start_date"])
            & data["exit_date"].le(window["end_date"])
        )
        hit_count = hit_count + in_window.astype("int64")
    data["stage011_focus_window_hit_count"] = hit_count.astype("int64")
    data["stage011_focus_window_hit"] = hit_count.gt(0).astype("int64")
    return data


def _guard_masks(lots: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    active = _numeric(lots, "active_positions_before")
    loss_streak = _numeric(lots, "loss_streak")
    risk_multiplier = _numeric(lots, "risk_multiplier")
    drawdown = _numeric(lots, "portfolio_drawdown_abs_pct")
    entry_risk = _numeric(lots, "entry_risk_distance_pct_abs")
    breakout = _numeric(lots, "breakout")
    corr = _corr_present(lots)
    rsi_follow = _directional_rsi_follow(lots)
    rsi_extreme = _directional_rsi_extreme(lots)
    trend_aligned = _trend_aligned(lots)
    return [
        ("exclude_active_positions_ge3", "排除入场前活跃持仓 >=3", active.ge(3)),
        ("exclude_account_drawdown_ge20", "排除账户回撤绝对值 >=20%", drawdown.ge(20)),
        ("exclude_same_direction_corr_present", "排除存在同向相关持仓", corr),
        ("exclude_loss_streak_gt0", "排除 loss_streak >0", loss_streak.gt(0)),
        ("exclude_risk_multiplier_ge2", "排除 risk_multiplier >=2", risk_multiplier.ge(2)),
        ("exclude_rsi_extreme_follow", "排除 RSI 极端顺势", rsi_extreme),
        ("exclude_rsi_not_directional_follow", "排除 RSI 非顺势", ~rsi_follow),
        ("exclude_entry_risk_distance_gt2pct", "排除入场止损距离 >2%", entry_risk.gt(2)),
        ("exclude_breakout_false", "排除非 breakout 入场", ~breakout.eq(1)),
        ("exclude_trend_not_aligned", "排除入场方向与中长期均线不一致", ~trend_aligned),
        (
            "exclude_active_ge3_and_corr_present",
            "排除活跃持仓 >=3 且存在同向相关持仓",
            active.ge(3) & corr,
        ),
        (
            "exclude_active_ge2_and_rsi_extreme",
            "排除活跃持仓 >=2 且 RSI 极端顺势",
            active.ge(2) & rsi_extreme,
        ),
        (
            "exclude_high_entry_risk_and_corr",
            "排除止损距离 >2% 且存在同向相关持仓",
            entry_risk.gt(2) & corr,
        ),
    ]


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def _year_rows(guard_name: str, retained: pd.DataFrame, excluded: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, frame in [("retained", retained), ("excluded", excluded)]:
        if frame.empty:
            continue
        grouped = frame.groupby("entry_year", dropna=False)
        for year, group in grouped:
            rows.append(
                {
                    "guard_name": guard_name,
                    "bucket": bucket,
                    "entry_year": int(year) if pd.notna(year) else np.nan,
                    "event_count": int(len(group)),
                    "total_pnl": float(_numeric(group, "realized_pnl", 0.0).sum()),
                    "mean_pnl": float(_numeric(group, "realized_pnl", 0.0).mean()),
                    "bad_path_rate_pct": float(_numeric(group, "bad_path", 0.0).mean() * 100.0),
                    "focus_proxy_delta_pnl": _focus_proxy_delta(group),
                }
            )
    return rows


def _focus_proxy_delta(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    hit_count = _numeric(frame, "stage011_focus_window_hit_count", 0.0).fillna(0.0)
    return float((_numeric(frame, "stage010_proxy_delta_pnl", 0.0).fillna(0.0) * hit_count).sum())


def _summarize_guard(
    lots: pd.DataFrame,
    guard_name: str,
    description: str,
    exclude_mask: pd.Series,
    *,
    min_retained_count: int,
    min_year_count: int,
    min_retained_total_pnl_share_pct: float,
    min_focus_proxy_improvement: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exclude_mask = exclude_mask.reindex(lots.index).fillna(False).astype(bool)
    excluded = lots.loc[exclude_mask].copy()
    retained = lots.loc[~exclude_mask].copy()
    total_pnl = float(_numeric(lots, "realized_pnl", 0.0).sum())
    base_bad_rate = float(_numeric(lots, "bad_path", 0.0).mean() * 100.0) if len(lots) else np.nan
    retained_pnl = float(_numeric(retained, "realized_pnl", 0.0).sum()) if len(retained) else 0.0
    excluded_pnl = float(_numeric(excluded, "realized_pnl", 0.0).sum()) if len(excluded) else 0.0
    focus_before = _focus_proxy_delta(lots)
    focus_after = _focus_proxy_delta(retained)
    retained_year = (
        retained.groupby("entry_year", as_index=False)["realized_pnl"].sum()
        if len(retained)
        else pd.DataFrame(columns=["entry_year", "realized_pnl"])
    )
    positive_year_count = int(pd.to_numeric(retained_year["realized_pnl"], errors="coerce").gt(0.0).sum())
    year_count = int(retained_year["entry_year"].nunique()) if len(retained_year) else 0
    retained_bad_rate = float(_numeric(retained, "bad_path", 0.0).mean() * 100.0) if len(retained) else np.nan
    excluded_bad_rate = float(_numeric(excluded, "bad_path", 0.0).mean() * 100.0) if len(excluded) else np.nan
    retained_share = _safe_div(retained_pnl, total_pnl) * 100.0 if np.isfinite(_safe_div(retained_pnl, total_pnl)) else np.nan
    focus_improvement = focus_after - focus_before
    candidate = (
        len(retained) >= int(min_retained_count)
        and year_count >= int(min_year_count)
        and positive_year_count >= int(min_year_count)
        and retained_pnl > 0.0
        and np.isfinite(retained_share)
        and retained_share >= float(min_retained_total_pnl_share_pct)
        and excluded_pnl <= 0.0
        and np.isfinite(focus_improvement)
        and focus_improvement >= float(min_focus_proxy_improvement)
        and (not np.isfinite(retained_bad_rate) or not np.isfinite(base_bad_rate) or retained_bad_rate <= base_bad_rate)
    )
    row = {
        "guard_name": guard_name,
        "description": description,
        "excluded_count": int(len(excluded)),
        "excluded_share_pct": float(len(excluded) / len(lots) * 100.0) if len(lots) else 0.0,
        "excluded_total_pnl": excluded_pnl,
        "excluded_mean_pnl": float(_numeric(excluded, "realized_pnl", 0.0).mean()) if len(excluded) else np.nan,
        "excluded_bad_path_rate_pct": excluded_bad_rate,
        "retained_count": int(len(retained)),
        "retained_share_pct": float(len(retained) / len(lots) * 100.0) if len(lots) else 0.0,
        "retained_total_pnl": retained_pnl,
        "retained_total_pnl_share_pct": retained_share,
        "retained_mean_pnl": float(_numeric(retained, "realized_pnl", 0.0).mean()) if len(retained) else np.nan,
        "retained_year_count": year_count,
        "retained_positive_year_count": positive_year_count,
        "retained_min_year_pnl": float(pd.to_numeric(retained_year["realized_pnl"], errors="coerce").min())
        if len(retained_year)
        else np.nan,
        "retained_bad_path_rate_pct": retained_bad_rate,
        "baseline_bad_path_rate_pct": base_bad_rate,
        "focus_proxy_delta_before_guard": focus_before,
        "focus_proxy_delta_after_guard": focus_after,
        "focus_proxy_delta_improvement": focus_improvement,
        "focus_excluded_proxy_delta_pnl": focus_before - focus_after,
        "candidate_for_true_engine_audit": bool(candidate),
    }
    return row, _year_rows(guard_name, retained, excluded)


def build_guard_summary(
    selected_lots: pd.DataFrame,
    focus_windows: pd.DataFrame,
    *,
    min_retained_count: int = DEFAULT_MIN_RETAINED_COUNT,
    min_year_count: int = DEFAULT_MIN_YEAR_COUNT,
    min_retained_total_pnl_share_pct: float = DEFAULT_MIN_RETAINED_TOTAL_PNL_SHARE_PCT,
    min_focus_proxy_improvement: float = DEFAULT_MIN_FOCUS_PROXY_IMPROVEMENT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    tagged = mark_focus_membership(selected_lots, focus_windows)
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for guard_name, description, mask in _guard_masks(tagged):
        row, guard_year_rows = _summarize_guard(
            tagged,
            guard_name,
            description,
            mask,
            min_retained_count=min_retained_count,
            min_year_count=min_year_count,
            min_retained_total_pnl_share_pct=min_retained_total_pnl_share_pct,
            min_focus_proxy_improvement=min_focus_proxy_improvement,
        )
        rows.append(row)
        year_rows.extend(guard_year_rows)
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["candidate_for_true_engine_audit", "focus_proxy_delta_improvement", "retained_total_pnl_share_pct"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
    return summary, pd.DataFrame(year_rows)


def make_decision(tagged_lots: pd.DataFrame, guard_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = (
        guard_summary[guard_summary["candidate_for_true_engine_audit"].astype(bool)].copy()
        if not guard_summary.empty
        else pd.DataFrame()
    )
    focus_proxy_delta = _focus_proxy_delta(tagged_lots)
    if tagged_lots.empty:
        decision = "stage012_no_selected_quality_lots_stop"
        reason = "Stage010 selected quality lots 为空，无法做 guard 审计。"
    elif candidates.empty:
        decision = "stage012_no_stable_generic_guard_candidate_keep_readonly"
        reason = "没有通用 PIT guard 同时满足保留收益、跨年正贡献、focus proxy 改善和非正 excluded PnL。"
    else:
        decision = "stage012_has_generic_guard_candidates_need_path_proxy_ab"
        reason = "存在通用 PIT guard 候选，但本阶段仍是 closed-lot 只读审计；下一步只能冻结一个候选做路径 proxy 或真实引擎 A/B。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_paths": {
            "stage010_lot_deltas": str(STAGE010_LOT_DELTAS_PATH.relative_to(PROJECT_DIR)),
            "stage011_focus_windows": str(STAGE011_FOCUS_WINDOWS_PATH.relative_to(PROJECT_DIR)),
        },
        "output_paths": {
            "tagged_lots": str(TAGGED_LOTS_PATH.relative_to(PROJECT_DIR)),
            "guard_summary": str(GUARD_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "guard_year_summary": str(GUARD_YEAR_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "chart": str(CHART_PATH.relative_to(PROJECT_DIR)),
            "decision": str(DECISION_PATH.relative_to(PROJECT_DIR)),
            "report": str(REPORT_PATH.relative_to(PROJECT_DIR)),
            "stage_record": str(STAGE_RECORD_PATH.relative_to(PROJECT_DIR)),
        },
        "thresholds": {
            "min_retained_count": DEFAULT_MIN_RETAINED_COUNT,
            "min_year_count": DEFAULT_MIN_YEAR_COUNT,
            "min_retained_total_pnl_share_pct": DEFAULT_MIN_RETAINED_TOTAL_PNL_SHARE_PCT,
            "min_focus_proxy_improvement": DEFAULT_MIN_FOCUS_PROXY_IMPROVEMENT,
            "add_risk_fraction": ADD_RISK_FRACTION,
        },
        "analysis_scope": {
            "selected_lot_count": int(len(tagged_lots)),
            "focus_selected_lot_count": int(tagged_lots["stage011_focus_window_hit"].sum()) if not tagged_lots.empty else 0,
            "selected_total_pnl": float(_numeric(tagged_lots, "realized_pnl", 0.0).sum()) if not tagged_lots.empty else 0.0,
            "focus_proxy_delta_pnl": focus_proxy_delta,
            "year_count": int(tagged_lots["entry_year"].nunique()) if not tagged_lots.empty else 0,
        },
        "candidate_count": int(len(candidates)),
        "candidate_guards": candidates["guard_name"].head(10).tolist() if not candidates.empty else [],
        "top_candidates": _json_safe(candidates.head(10).to_dict("records")) if not candidates.empty else [],
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Meta-labeling supports a secondary filter or sizing layer only when features are point-in-time and the "
            "primary signal still owns direction. This audit therefore tests generic guard families before any true engine."
        ),
        "overfit_reflection_before": (
            "否。本阶段固定 Stage010 质量候选，guard 只使用预声明 PIT 状态字段，不使用产品、方向、日期或单个窗口。"
        ),
        "continue_value_before": (
            "有价值。Stage010 已证明高质量信号加风险有信息量，Stage011 又证明其中混入负拖累簇；需要先找通用过滤结构。"
        ),
        "overfit_reflection_after": (
            "待本次结果判断；若直接把任何 guard 上线或继续调阈值/产品/日期，就是过拟合。"
        ),
        "continue_value_after": (
            "待本次结果判断；只有 guard 能保留大部分收益并改善 focus 左尾，才值得进入路径 proxy 或真实引擎。"
        ),
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _plot_guard_summary(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    shown = summary.head(12).copy()
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    labels = shown["guard_name"].astype(str).tolist()
    y = np.arange(len(shown))
    colors = np.where(shown["candidate_for_true_engine_audit"].astype(bool), "#15803d", "#64748b")
    axes[0].barh(y, shown["focus_proxy_delta_improvement"], color=colors)
    axes[0].axvline(0.0, color="#111827", linestyle="--", linewidth=0.8)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].invert_yaxis()
    axes[0].set_title("Focus Proxy Delta Improvement")
    axes[0].grid(True, axis="x", alpha=0.25)
    axes[1].barh(y, shown["retained_total_pnl_share_pct"], color=colors)
    axes[1].axvline(80.0, color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=8)
    axes[1].invert_yaxis()
    axes[1].set_title("Retained Total PnL Share %")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame) -> None:
    cols = [
        "guard_name",
        "excluded_count",
        "excluded_total_pnl",
        "retained_total_pnl",
        "retained_total_pnl_share_pct",
        "retained_positive_year_count",
        "focus_proxy_delta_before_guard",
        "focus_proxy_delta_after_guard",
        "focus_proxy_delta_improvement",
        "candidate_for_true_engine_audit",
    ]
    candidates = summary[summary["candidate_for_true_engine_audit"].astype(bool)].copy() if not summary.empty else pd.DataFrame()
    text = f"""# Stage012 Selected Quality Guard Audit

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 输入：Stage010 selected quality lots + Stage011 focus windows
- 决策：`{decision["decision"]}`

## 外部调研与判断

Meta-labeling 的二级层只适合过滤假阳性或做加风险置信度，不能替代趋势主策略。趋势跟随的长期收益依赖右尾，因此 guard 必须先证明保留大部分 Stage010 选中收益，再看是否减少 focus 左尾负拖累。

## 样本概况

```json
{json.dumps(_json_safe(decision["analysis_scope"]), ensure_ascii=False, indent=2)}
```

## 候选 guard

{_md_table(candidates[cols] if not candidates.empty else candidates)}

## guard 总表

{_md_table(summary[cols] if not summary.empty else summary, max_rows=20)}

## 结论

- {decision["decision_reason"]}
- 本阶段不产生新资金曲线、期末权益、最大回撤、Sharpe、滑点、交易次数或胜率。
- 即使出现候选，也只能进入下一阶段路径 proxy 或真实引擎 A/B；不能直接上线。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> None:
    cols = [
        "guard_name",
        "excluded_count",
        "excluded_total_pnl",
        "retained_total_pnl",
        "retained_total_pnl_share_pct",
        "retained_positive_year_count",
        "focus_proxy_delta_before_guard",
        "focus_proxy_delta_after_guard",
        "focus_proxy_delta_improvement",
        "candidate_for_true_engine_audit",
    ]
    candidates = summary[summary["candidate_for_true_engine_audit"].astype(bool)].copy() if not summary.empty else pd.DataFrame()
    text = f"""# Stage012 Selected Quality Guard Audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：只读 guard 审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只决定是否值得进入路径 proxy/真实引擎

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：Stage010 的高质量加风险方向值得继续，但 guard 必须只用入场前可见状态，且不能产品/方向/日期黑名单化。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage012_selected_quality_guard_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage012_selected_quality_guard_audit.py`
- 新增参数：`MIN_RETAINED_COUNT={DEFAULT_MIN_RETAINED_COUNT}`、`MIN_YEAR_COUNT={DEFAULT_MIN_YEAR_COUNT}`、`MIN_RETAINED_TOTAL_PNL_SHARE_PCT={DEFAULT_MIN_RETAINED_TOTAL_PNL_SHARE_PCT}`、`MIN_FOCUS_PROXY_IMPROVEMENT={DEFAULT_MIN_FOCUS_PROXY_IMPROVEMENT}`
- 修改参数：无
- 删除参数：无

## 结果

- Stage010 selected lots：`{decision["analysis_scope"]["selected_lot_count"]}`
- focus selected lots：`{decision["analysis_scope"]["focus_selected_lot_count"]}`
- selected total PnL：`{decision["analysis_scope"]["selected_total_pnl"]:.2f}`
- focus proxy delta：`{decision["analysis_scope"]["focus_proxy_delta_pnl"]:.2f}`
- candidate guard 数：`{decision["candidate_count"]}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 候选 guard

{_md_table(candidates[cols] if not candidates.empty else candidates)}

## guard 总表

{_md_table(summary[cols] if not summary.empty else summary, max_rows=20)}

## 过拟合反思

- 运行前判断：否。本阶段固定 Stage010 候选，只用预声明 PIT 状态字段，不用产品/方向/日期/坏窗口黑名单。
- 运行后判断：待结果解释；如果把任何 guard 直接上线或继续调阈值救参，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage011 已经证明 Stage010 候选里存在负拖累簇，必须先确认是否有通用状态能过滤。
- 运行后判断：待结果解释；若没有候选，应转向新 PIT 信息源或真实持仓路径，不继续扫这些 guard。

## 输出文件

- tagged_lots: `{TAGGED_LOTS_PATH}`
- guard_summary: `{GUARD_SUMMARY_PATH}`
- guard_year_summary: `{GUARD_YEAR_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _read_csv(STAGE010_LOT_DELTAS_PATH)
    focus = _read_csv(STAGE011_FOCUS_WINDOWS_PATH)
    tagged = mark_focus_membership(lots, focus)
    summary, year_summary = build_guard_summary(tagged, focus)
    decision = make_decision(tagged, summary)
    if decision["candidate_count"]:
        decision["overfit_reflection_after"] = (
            "否，但只限审计层面。候选来自预声明 PIT guard，仍必须进入路径 proxy/真实引擎后才能判断是否过拟合。"
        )
        decision["continue_value_after"] = (
            "有价值。出现候选 guard，下一步应冻结最少自由度候选做资金曲线 proxy，而不是继续扫阈值。"
        )
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段没有继续调阈值或按产品/日期救参；当前 guard 家族未提供足够稳健候选。"
        )
        decision["continue_value_after"] = (
            "有限。若无候选，应转向新 PIT 信息源或持仓路径，而不是继续扩展同类 guard。"
        )
    tagged.to_csv(TAGGED_LOTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    summary.to_csv(GUARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(GUARD_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot_guard_summary(summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary)
    _write_stage_record(decision, summary)
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
