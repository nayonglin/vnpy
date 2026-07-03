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
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage009_dense_start_goal_audit as s009
import stage013_account_state_pilot_gate_engine as s013
import stage042_expanded_daily_cold_start_probe as s042
import stage066_breakeven_after_1r_true_engine as s066


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage067"
MODEL_TAG = "stage067_breakeven_expanded_daily_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage067_breakeven_expanded_daily_probe"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0

BASE_VARIANT = "stage013_expanded_baseline"
CANDIDATE_VARIANT = "stage067_breakeven_after_1r"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage067_breakeven_expanded_daily_probe"
STAGE_RECORD_DIR = LINE_DIR / "stages"

STARTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_starts_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
BREAKEVEN_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_breakeven_events_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EXTERNAL_RESEARCH_SOURCES = [
    "Backtrader stop order docs: https://www.backtrader.com/docu/order/",
    "NautilusTrader backtesting event cycle: https://nautilustrader.io/docs/latest/concepts/backtesting/",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
    "Rob Carver dynamic trend following: https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "Stage067 does not tune the breakeven threshold. It only expands Stage066's conservative event-ordering true "
    "engine to the Stage042/053-style daily pressure starts, because stop and breakeven rules can easily damage trend "
    "following right tails if judged only from closed-lot hindsight."
)


def _json_safe(value: Any) -> Any:
    return s066._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s066._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _stage067_starts_from_stage042_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "stage067_probe_rank",
                "requested_start",
                "requested_end",
                "probe_bucket",
                "source_stage042_probe_rank",
            ]
        )
    data = frame.copy()
    data["requested_start"] = pd.to_datetime(data["requested_start"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["requested_start"]).sort_values("requested_start").drop_duplicates("requested_start", keep="first")
    data = data.reset_index(drop=True)
    result = pd.DataFrame(
        {
            "stage067_probe_rank": np.arange(1, len(data) + 1, dtype=int),
            "requested_start": data["requested_start"].dt.date.astype(str),
            "requested_end": _date_text(REQUESTED_END),
            "probe_bucket": data.get("probe_bucket", pd.Series(["unknown"] * len(data))).astype(str).to_numpy(),
            "source_stage042_probe_rank": pd.to_numeric(data.get("probe_rank", np.nan), errors="coerce"),
        }
    )
    for column in [
        "source_window_class",
        "source_stage039_return_pct",
        "source_stage013_return_pct",
        "source_stage039_absolute_end_ge_stage013",
    ]:
        if column in data.columns:
            result[column] = data[column].to_numpy()
    return result


def _load_expanded_starts() -> pd.DataFrame:
    if s042.PROBE_STARTS_PATH.exists():
        frame = pd.read_csv(s042.PROBE_STARTS_PATH, encoding="utf-8-sig")
    else:
        top_windows = pd.read_csv(s042.STAGE040_TOP_WINDOWS_PATH, encoding="utf-8-sig")
        frame = s042._select_expanded_probe_start_dates(top_windows)
    starts = _stage067_starts_from_stage042_frame(frame)
    if starts.empty:
        raise RuntimeError("Stage067 expanded starts are empty; run Stage042 first.")
    return starts


def _frame_with_run_columns(frame: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = s066.OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = s066.OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _date_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    result["ab_variant"] = variant_label
    return result


def _append_frame(target: list[pd.DataFrame], frame: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> None:
    framed = _frame_with_run_columns(frame, start=start, variant_label=variant_label)
    if not framed.empty:
        target.append(framed)


def _curve_for_variant(combined: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> pd.DataFrame:
    curve = combined.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["official_live_version"] = s066.OFFICIAL_LIVE_VERSION
    curve["official_live_alias"] = s066.OFFICIAL_LIVE_ALIAS
    curve["requested_start"] = _date_text(start)
    curve["requested_start_month"] = _date_text(start)
    curve["requested_end"] = _date_text(REQUESTED_END)
    curve["variant"] = variant_label
    curve["ab_variant"] = variant_label
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
    curve["drawdown_pct"] = s066.s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
    curve["days_since_start"] = np.arange(len(curve), dtype=int)
    return curve


def _summarize_curve(curve: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> dict[str, Any]:
    row = s066.s167._summarize_curve(curve, start)
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start": _date_text(start),
            "requested_start_month": _date_text(start),
            "requested_end": _date_text(REQUESTED_END),
            "variant": variant_label,
            "ab_variant": variant_label,
            "official_live_profile_name": s066.PROFILE_NAME if variant_label == CANDIDATE_VARIANT else s013.PROFILE_NAME,
        }
    )
    return row


def _run_expanded_ab() -> dict[str, pd.DataFrame]:
    metadata = s066.s901.s513._metadata()
    starts = _load_expanded_starts()

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for index, row in enumerate(starts.itertuples(index=False), start=1):
        start = pd.Timestamp(row.requested_start).normalize()
        print(f"[stage067] A Stage013 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        base_combined, base_frames, _base_spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _curve_for_variant(base_combined, start=start, variant_label=BASE_VARIANT)
        curve_frames.append(base_curve)
        summary_rows.append(_summarize_curve(base_curve, start=start, variant_label=BASE_VARIANT))
        _append_frame(candidate_frames, base_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_frames, base_frames.get("trades", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(entry_risk_frames, base_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_event_frames, base_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)

        print(f"[stage067] C Stage067 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        candidate_combined, candidate_frames_map, _candidate_spec = s066._run_live_stage066(metadata, start, REQUESTED_END)
        candidate_curve = _curve_for_variant(candidate_combined, start=start, variant_label=CANDIDATE_VARIANT)
        curve_frames.append(candidate_curve)
        summary_rows.append(_summarize_curve(candidate_curve, start=start, variant_label=CANDIDATE_VARIANT))
        _append_frame(
            candidate_frames,
            candidate_frames_map.get("entry_candidates", pd.DataFrame()),
            start=start,
            variant_label=CANDIDATE_VARIANT,
        )
        _append_frame(trade_frames, candidate_frames_map.get("trades", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(
            entry_risk_frames,
            candidate_frames_map.get("entry_risk", pd.DataFrame()),
            start=start,
            variant_label=CANDIDATE_VARIANT,
        )
        _append_frame(
            trade_event_frames,
            candidate_frames_map.get("trade_events", pd.DataFrame()),
            start=start,
            variant_label=CANDIDATE_VARIANT,
        )

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    breakeven_events = (
        trade_events[trade_events["reason"].astype(str).str.startswith("stage066_", na=False)].copy()
        if not trade_events.empty and "reason" in trade_events.columns
        else pd.DataFrame()
    )
    return {
        "starts": starts,
        "summary": pd.DataFrame(summary_rows).sort_values(["requested_start", "variant"]).reset_index(drop=True),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "entry_risk": pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        "trade_events": trade_events,
        "breakeven_events": breakeven_events,
    }


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "variant", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"])
    return s009._run_audit(audit_curves)


def _retention_summary(summary: pd.DataFrame) -> pd.DataFrame:
    wide = summary.pivot(index="requested_start_month", columns="variant", values="total_return_pct").reset_index()
    if BASE_VARIANT not in wide.columns or CANDIDATE_VARIANT not in wide.columns:
        return pd.DataFrame()
    wide["stage067_vs_baseline_return_ratio"] = (
        pd.to_numeric(wide[CANDIDATE_VARIANT], errors="coerce")
        / pd.to_numeric(wide[BASE_VARIANT], errors="coerce").replace(0.0, np.nan)
    )
    wide["passes_80pct_retention"] = (
        pd.to_numeric(wide[CANDIDATE_VARIANT], errors="coerce")
        >= pd.to_numeric(wide[BASE_VARIANT], errors="coerce") * 0.8
    ).astype("int64")
    return wide.rename(
        columns={
            BASE_VARIANT: "baseline_total_return_pct",
            CANDIDATE_VARIANT: "candidate_total_return_pct",
        }
    )


def _variant_metric(aggregate: pd.DataFrame, variant: str, scope: str, column: str, default: float = np.nan) -> float:
    rows = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq(scope)]
    if rows.empty or column not in rows.columns:
        return default
    values = pd.to_numeric(rows[column], errors="coerce")
    if column in {"negative_count", "window_count", "positive_count"}:
        return float(values.fillna(0.0).sum())
    if column == "min_return_pct":
        return float(values.min())
    return float(values.mean())


def _ai_audit(entry_candidates: pd.DataFrame) -> pd.DataFrame:
    if entry_candidates.empty:
        return pd.DataFrame()
    frame = entry_candidates.copy()
    frame["date"] = pd.to_datetime(frame.get("date"), errors="coerce")
    frame["month"] = frame["date"].dt.to_period("M").astype(str)
    frame["ai_enabled_num"] = pd.to_numeric(frame.get("ai_product_pool_enabled", 0), errors="coerce").fillna(0)
    frame["ai_allowed_num"] = pd.to_numeric(frame.get("ai_product_pool_allowed", 0), errors="coerce").fillna(0)
    frame["selected_volume_num"] = pd.to_numeric(frame.get("selected_volume", 0), errors="coerce").fillna(0)
    rows: list[dict[str, Any]] = []
    for variant, group in frame.groupby("ab_variant", sort=True):
        by_month = group.groupby("month", dropna=True)["ai_enabled_num"].sum()
        rows.append(
            {
                "variant": variant,
                "row_count": int(len(group)),
                "month_count": int(group["month"].nunique()),
                "month_min": str(group["month"].min()),
                "month_max": str(group["month"].max()),
                "ai_enabled_rows": int(group["ai_enabled_num"].gt(0).sum()),
                "ai_allowed_rows": int(group["ai_allowed_num"].gt(0).sum()),
                "selected_rows": int(group["selected_volume_num"].gt(0).sum()),
                "months_without_ai_enabled": int(by_month.eq(0).sum()),
                "strategy_values": "|".join(sorted(group.get("ai_product_pool_strategy", pd.Series(dtype=str)).dropna().astype(str).unique())),
            }
        )
    return pd.DataFrame(rows)


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    breakeven_events: pd.DataFrame,
    ai_audit: pd.DataFrame,
) -> dict[str, Any]:
    candidate_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)]
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)]
    strict_scope = "all_trading_end_dates_gt_1y"
    final_scope = "start_to_2026_06_30_only"
    return {
        "expanded_start_count": int(candidate_summary["requested_start_month"].nunique()),
        "baseline_positive_start_count": int(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "candidate_positive_start_count": int(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "baseline_min_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").min()),
        "candidate_min_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").min()),
        "baseline_median_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").median()),
        "candidate_median_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").median()),
        "baseline_worst_max_dd_pct": float(pd.to_numeric(base_summary["max_dd_pct"], errors="coerce").min()),
        "candidate_worst_max_dd_pct": float(pd.to_numeric(candidate_summary["max_dd_pct"], errors="coerce").min()),
        "baseline_median_sharpe": float(pd.to_numeric(base_summary["sharpe"], errors="coerce").median()),
        "candidate_median_sharpe": float(pd.to_numeric(candidate_summary["sharpe"], errors="coerce").median()),
        "baseline_strict_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "negative_count", 0.0)),
        "candidate_strict_negative_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "negative_count", 0.0)),
        "baseline_strict_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "window_count", 0.0)),
        "candidate_strict_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "window_count", 0.0)),
        "baseline_strict_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, strict_scope, "min_return_pct"),
        "candidate_strict_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "min_return_pct"),
        "baseline_to_final_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, final_scope, "negative_count", 0.0)),
        "candidate_to_final_negative_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "negative_count", 0.0)),
        "baseline_to_final_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, final_scope, "min_return_pct"),
        "candidate_to_final_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "min_return_pct"),
        "retention_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "breakeven_event_count": int(len(breakeven_events)),
        "breakeven_applied_event_count": int(pd.to_numeric(breakeven_events.get("stage066_apply_now", 0), errors="coerce").fillna(0).sum())
        if not breakeven_events.empty
        else 0,
        "breakeven_pending_event_count": int(
            pd.to_numeric(breakeven_events.get("stage066_pending_apply", 0), errors="coerce").fillna(0).sum()
        )
        if not breakeven_events.empty
        else 0,
        "candidate_ai_months_without_enabled": int(
            ai_audit[ai_audit["variant"].eq(CANDIDATE_VARIANT)]["months_without_ai_enabled"].sum()
        )
        if not ai_audit.empty and "months_without_ai_enabled" in ai_audit.columns
        else -1,
    }


def _stage067_decision_from_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    retention_rows = int(metrics.get("retention_rows", 0) or 0)
    retention_ok = retention_rows > 0 and int(metrics.get("retention_pass_count", 0) or 0) == retention_rows
    baseline_negative = int(metrics.get("baseline_strict_negative_window_count", 0) or 0)
    candidate_negative = int(metrics.get("candidate_strict_negative_window_count", 0) or 0)
    baseline_min = float(metrics.get("baseline_strict_min_return_pct", np.nan))
    candidate_min = float(metrics.get("candidate_strict_min_return_pct", np.nan))
    improves_left_tail = candidate_negative < baseline_negative and candidate_min > baseline_min
    goal_pass = candidate_negative == 0 and retention_ok
    if goal_pass:
        return {
            "decision": "stage067_expanded_goal_pass_candidate",
            "goal_pass": True,
            "improves_left_tail": True,
            "retention_ok": True,
            "next_step": "进入更宽日级网格与逐半年多周期验证，并审计 AI 月更、鸡蛋池和成本压力。",
            "overfit_reflection_after": "暂不判定过拟合，但必须继续全量 OOS 与成本压力验证。",
            "continue_value_after": "有。扩展压力起点已清零负窗口，值得进入全量目标验证。",
        }
    if improves_left_tail and retention_ok:
        return {
            "decision": "stage067_expanded_improves_left_tail_not_goal",
            "goal_pass": False,
            "improves_left_tail": True,
            "retention_ok": True,
            "next_step": "保留 Stage067 为候选证据，但不要上线；继续找 early/late adverse 的强 PIT 信息源或账户外层。",
            "overfit_reflection_after": "暂不判定过拟合。未调参且扩样本仍改善，但不能因为改善就宣布达标。",
            "continue_value_after": "有。左尾改善有机制价值，但目标未达成，下一步需要补缺口而不是救参。",
        }
    return {
        "decision": "stage067_expanded_not_enough_stop_no_param_rescue",
        "goal_pass": False,
        "improves_left_tail": False,
        "retention_ok": bool(retention_ok),
        "next_step": "停止保本 stop 路线参数化救援；转更强 PIT 信息源、账户外层或高质量信号识别。",
        "overfit_reflection_after": "否。本阶段没有救参；若继续改保本阈值或筛样本就是过拟合。",
        "continue_value_after": "有限。若扩样本无法保持左尾改善，该保本形状不应继续交易化。",
    }


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    color_map = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#dc2626"}
    for (variant, start), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.75, alpha=0.55, color=color_map.get(variant), label=f"{variant} {start}")
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.75, alpha=0.55, color=color_map.get(variant), label=f"{variant} {start}")
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage067 Expanded Starts Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage067 Expanded Starts Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=5, ncol=4, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal_audit(aggregate: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), constrained_layout=True)
    colors = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#dc2626"}
    scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    scope["label"] = scope["variant"].astype(str) + "\n" + scope["source_start_month"].astype(str)
    x = np.arange(len(scope))
    axes[0].bar(x, scope["negative_rate_pct"], color=[colors.get(v, "#94a3b8") for v in scope["variant"]])
    axes[0].set_xticks(x[::4])
    axes[0].set_xticklabels(scope["label"].iloc[::4], rotation=60, ha="right", fontsize=6)
    axes[0].set_title("Negative Rate: All Trading End Dates > 1Y")
    axes[0].set_ylabel("negative rate %")
    axes[0].grid(True, axis="y", alpha=0.25)

    if not fixed.empty:
        fixed_summary = (
            fixed.groupby(["variant", "horizon_days"], as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values(["horizon_days", "variant"])
        )
        for variant, group in fixed_summary.groupby("variant"):
            axes[1].plot(group["horizon_days"], group["negative_rate_pct"], marker="o", label=str(variant), color=colors.get(variant))
    axes[1].set_title("Fixed Horizon Negative Rate")
    axes[1].set_xlabel("calendar days")
    axes[1].set_ylabel("negative rate %")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame, ai_audit: pd.DataFrame) -> None:
    report = f"""# Stage067 保本退出扩展日级压力起点验证

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：Stage066 保本真引擎扩样本验证；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 参考：{'; '.join(EXTERNAL_RESEARCH_SOURCES)}
- 我的判断：保本退出必须显式处理事件顺序，扩样本只验证 Stage066 形状，不调 R 倍数。

## A/C 口径

- A：`{BASE_VARIANT}`，Stage013。
- C：`{CANDIDATE_VARIANT}`，Stage013 + Stage066 `+1R` 后保本 stop。
- 样本：Stage042 扩展日级压力起点 `{decision['expanded_start_count']}` 个，结束日统一 `2026-06-30`。

## 核心结果

- A 正收益起点：`{decision['baseline_positive_start_count']}/{decision['expanded_start_count']}`；C：`{decision['candidate_positive_start_count']}/{decision['expanded_start_count']}`
- 期末收益最小：A `{decision['baseline_min_total_return_pct']:.4f}%`；C `{decision['candidate_min_total_return_pct']:.4f}%`
- 最差最大回撤：A `{decision['baseline_worst_max_dd_pct']:.4f}%`；C `{decision['candidate_worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：A `{decision['baseline_strict_negative_window_count']}`；C `{decision['candidate_strict_negative_window_count']}`
- 严格最差收益：A `{decision['baseline_strict_min_return_pct']:.4f}%`；C `{decision['candidate_strict_min_return_pct']:.4f}%`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- AI 未启用月份：`{decision['candidate_ai_months_without_enabled']}`

## 多起点摘要

{_md_table(summary)}

## 目标审计摘要

{_md_table(aggregate.head(80))}

## 收益保留

{_md_table(retention)}

## AI 审计

{_md_table(ai_audit)}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage067_breakeven_expanded_daily_probe.md"
    content = f"""# Stage067 - 保本退出扩展日级压力起点验证

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage066 保本真引擎扩样本验证，不改官方实盘配置。
- 是否重要突破：`{'是' if decision['goal_pass'] else '否'}`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：Backtrader stop order、NautilusTrader event cycle、pysystemtrade、Rob Carver dynamic trend following。
- 我的判断：保本退出必须显式事件顺序；本阶段只扩样本，不扫 `1R/2R/4R` 或锁盈档位。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage067_breakeven_expanded_daily_probe.py`
- 新增测试：`tests/test_rebuilt_c9_stage067_expanded_breakeven_probe.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无新交易参数，复用 Stage066 `stage066_breakeven_trigger_r=1.0`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`{BASE_VARIANT}`。
- C：`{CANDIDATE_VARIANT}`。
- 样本：Stage042 扩展日级压力起点 `{decision['expanded_start_count']}` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。

## 结果

- 总收益：A 最小 `{decision['baseline_min_total_return_pct']:.4f}%`；C 最小 `{decision['candidate_min_total_return_pct']:.4f}%`
- 最大回撤：A 最差 `{decision['baseline_worst_max_dd_pct']:.4f}%`；C 最差 `{decision['candidate_worst_max_dd_pct']:.4f}%`
- Sharpe：A 中位 `{decision['baseline_median_sharpe']:.4f}`；C 中位 `{decision['candidate_median_sharpe']:.4f}`
- 严格负窗口：A `{decision['baseline_strict_negative_window_count']}`；C `{decision['candidate_strict_negative_window_count']}`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- AI 未启用月份：`{decision['candidate_ai_months_without_enabled']}`
- 总滑点、总交易次数、胜率：见 summary 输出。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- curves：`{CURVES_PATH}`
- ai_audit：`{AI_AUDIT_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前判断：有风险但可控。Stage066 已有压力集改善，本阶段只扩样本，不调参。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。必须确认 Stage066 改善能否穿越更多日级压力起点。
- 运行后判断：{decision['continue_value_after']}
"""
    record_path.write_text(content, encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    frames = _run_expanded_ab()
    starts = frames["starts"]
    summary = frames["summary"]
    curves = frames["curves"]
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    ai_audit = _ai_audit(frames["entry_candidates"])
    breakeven_events = frames["breakeven_events"]
    _plot_performance(curves)
    _plot_goal_audit(aggregate, fixed)

    starts.to_csv(STARTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    breakeven_events.to_csv(BREAKEVEN_EVENTS_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    ai_audit.to_csv(AI_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, breakeven_events, ai_audit)
    decision_fields = _stage067_decision_from_metrics(metrics)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage013_vs_stage067_breakeven_after_1r_expanded_daily_probe",
        "strategy_changed": True,
        "official_live_config_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "ab_arms": {"A": BASE_VARIANT, "C": CANDIDATE_VARIANT},
        "breakeven_trigger_r": s066.BREAKEVEN_TRIGGER_R,
        **metrics,
        **decision_fields,
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "有风险但可控。Stage066 已改善压力集，本阶段只扩样本，不调参。",
        "continue_value_before": "有。必须确认 Stage066 改善能否穿越更多日级压力起点。",
        "outputs": {
            "starts": str(STARTS_PATH),
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "breakeven_events": str(BREAKEVEN_EVENTS_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "ai_audit": str(AI_AUDIT_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention, ai_audit)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
