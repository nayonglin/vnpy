from __future__ import annotations

from dataclasses import replace
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

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import stage006_current_quality_feature_binder as s006
import stage009_dense_start_goal_audit as s009
import stage013_account_state_pilot_gate_engine as s013
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage029"
MODEL_TAG = "stage029_account_injury_flat_entry_pause_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage029_account_injury_flat_entry_pause_engine"
PROFILE_NAME = "stage029_account_injury_flat_entry_pause_engine"

INJURY_DRAWDOWN_TRIGGER_PCT = 0.20
INJURY_LOSS_STREAK_TRIGGER = 3
REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage029_account_injury_flat_entry_pause_engine"
STAGE_RECORD_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INJURY_PAUSE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_injury_pause_events_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _normalize_ratio(value: Any) -> float:
    return s013._normalize_drawdown_ratio(value)


def _stage029_apply_account_injury_pause_gate(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    loss_streak: int,
    enabled: bool,
    drawdown_trigger_pct: float = INJURY_DRAWDOWN_TRIGGER_PCT,
    loss_streak_trigger: int = INJURY_LOSS_STREAK_TRIGGER,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    drawdown_ratio = _normalize_ratio(sizing.get("portfolio_drawdown_pct", 0.0))
    trigger_ratio = _normalize_ratio(drawdown_trigger_pct)
    streak = max(0, int(loss_streak or 0))
    streak_trigger = max(0, int(loss_streak_trigger or 0))
    drawdown_hit = drawdown_ratio >= trigger_ratio
    streak_hit = streak >= streak_trigger

    selected_after = selected_before
    applied = 0
    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif not (drawdown_hit or streak_hit):
        reason = "account_state_not_injured"
    else:
        selected_after = 0
        applied = int(selected_after != selected_before)
        reason = "stage029_account_injury_flat_entry_pause" if applied else "already_zero"

    fields = {
        "stage029_injury_pause_gate_enabled": int(bool(enabled)),
        "stage029_injury_pause_gate_applied": applied,
        "stage029_injury_pause_gate_reason": reason,
        "stage029_injury_pause_selected_volume_before": selected_before,
        "stage029_injury_pause_selected_volume_after": selected_after,
        "stage029_injury_pause_reduced_volume": selected_before - selected_after,
        "stage029_injury_pause_drawdown_pct": drawdown_ratio,
        "stage029_injury_pause_drawdown_trigger_pct": trigger_ratio,
        "stage029_injury_pause_loss_streak": streak,
        "stage029_injury_pause_loss_streak_trigger": streak_trigger,
        "stage029_injury_pause_drawdown_hit": int(drawdown_hit),
        "stage029_injury_pause_loss_streak_hit": int(streak_hit),
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage029AccountInjuryPause(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage029_account_injury_pause_gate: bool = False
    stage029_injury_drawdown_trigger_pct: float = INJURY_DRAWDOWN_TRIGGER_PCT
    stage029_injury_loss_streak_trigger: int = INJURY_LOSS_STREAK_TRIGGER

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage029_account_injury_pause_gate",
        "stage029_injury_drawdown_trigger_pct",
        "stage029_injury_loss_streak_trigger",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage029_injury_pause_gate_count",
        "stage029_injury_pause_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage029_injury_pause_events: list[dict[str, Any]] = []
        self.stage029_injury_pause_gate_count: int = 0
        self.stage029_injury_pause_reduced_volume: int = 0

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage029_account_injury_pause_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = dict(plan.get("sizing") or {})
            selected_after, fields = _stage029_apply_account_injury_pause_gate(
                sizing=sizing,
                entry_context="flat_entry",
                loss_streak=int(getattr(self, "loss_streak", 0) or 0),
                enabled=bool(self.enable_stage029_account_injury_pause_gate),
                drawdown_trigger_pct=float(self.stage029_injury_drawdown_trigger_pct),
                loss_streak_trigger=int(self.stage029_injury_loss_streak_trigger),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage029_injury_pause_gate_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            plan["candidate_status"] = "skipped"
            plan["skip_reason"] = "stage029_account_injury_pause"

            event = self._stage029_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage029_injury_pause_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage029_injury_pause_gate_count += 1
            self.stage029_injury_pause_reduced_volume += int(fields["stage029_injury_pause_reduced_volume"])
        return plans

    def _stage029_event_from_plan(
        self,
        product_vt_symbol: str,
        plan: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        bar = plan.get("target_bar")
        bar_datetime = getattr(bar, "datetime", None)
        close_price = float(getattr(bar, "close_price", 0.0) or 0.0)
        direction = str(plan.get("direction") or "")
        return {
            "datetime": bar_datetime,
            "date": pd.Timestamp(bar_datetime).date() if bar_datetime is not None else "",
            "vt_symbol": str(plan.get("target_contract") or ""),
            "contract_vt_symbol": str(plan.get("target_contract") or ""),
            "product_vt_symbol": product_vt_symbol,
            "position_direction": direction,
            "direction": direction,
            "offset": "Sizing",
            "reason": "stage029_account_injury_pause_gate",
            "volume": int(fields["stage029_injury_pause_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage029_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage029 account-injury flat-entry pause",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage029 isolated research candidate. "
            "When account drawdown is already deep or loss_streak is severe, new flat entries are paused; "
            "existing positions, rollovers, adds, stop/retry, AI pool, and official live config are untouched."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage029_account_injury_pause_gate": True,
        "stage029_injury_drawdown_trigger_pct": INJURY_DRAWDOWN_TRIGGER_PCT,
        "stage029_injury_loss_streak_trigger": INJURY_LOSS_STREAK_TRIGGER,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage029AccountInjuryPause
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage029(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = _stage029_profile(metadata)
        combined, frames = s013._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    combined["account_capital"] = spec.capital.account_capital
    combined["c3_capital"] = spec.capital.c3_capital
    combined["profile"] = spec.profile
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = spec.capital.account_capital
        frame["c3_capital"] = spec.capital.c3_capital
        frame["profile"] = spec.profile
    return combined, frames, spec


def _frame_with_run_columns(frame: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    return result


def _append_frame(target: list[pd.DataFrame], frame: pd.DataFrame, start: pd.Timestamp) -> None:
    frame = _frame_with_run_columns(frame, start)
    if not frame.empty:
        target.append(frame)


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    row = s167._summarize_curve(curve, requested_start)
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "official_live_profile_name": PROFILE_NAME,
            "requested_end": REQUESTED_END.date().isoformat(),
        }
    )
    return row


def _run_multistart() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = s167._build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage029] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage029(metadata, start, REQUESTED_END)

        curve = combined.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["official_live_version"] = OFFICIAL_LIVE_VERSION
        curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
        curve["requested_start"] = _date_text(start)
        curve["requested_start_month"] = _start_month_text(start)
        curve["requested_end"] = _date_text(REQUESTED_END)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
        curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
        curve["drawdown_pct"] = s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start))

        _append_frame(candidate_frames, frames.get("entry_candidates", pd.DataFrame()), start)
        _append_frame(trade_frames, frames.get("trades", pd.DataFrame()), start)
        _append_frame(entry_risk_frames, frames.get("entry_risk", pd.DataFrame()), start)
        _append_frame(trade_event_frames, frames.get("trade_events", pd.DataFrame()), start)

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    injury_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage029_account_injury_pause_gate")].copy()
        if not trade_events.empty and "reason" in trade_events.columns
        else pd.DataFrame()
    )
    return {
        "summary": pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "entry_risk": pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        "trade_events": trade_events,
        "injury_pause_events": injury_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s006.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_base_stage006", "_stage029"),
    )
    merged["stage029_vs_base_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage029"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage029"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage029_engine"
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"])
    return s009._run_audit(audit_curves)


def _ai_audit(candidates: pd.DataFrame, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    pool, pool_audit = s167._load_ai_pool()
    month_audit = s167._ai_month_audit(candidates, summary, pool)
    pool_frame = s167._pool_audit_frame(pool)
    return month_audit, pool_frame, pool_audit


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.76, label=str(start))
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.76, label=str(start))
    axes[0].axhline(OFFICIAL_LIVE_CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage029 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage029 Drawdown By Cold Start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal_audit(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")].copy()
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")].copy()
    for ax, frame, title in [
        (axes[0, 0], all_scope, "Negative Rate: All Trading End Dates > 1Y"),
        (axes[0, 1], final_scope, "Negative Rate: Start To 2026-06-30"),
    ]:
        labels = frame["source_start_month"].astype(str).tolist()
        x = np.arange(len(frame))
        ax.bar(x, frame["negative_rate_pct"], color="#2563eb")
        ax.set_xticks(x[::2])
        ax.set_xticklabels(labels[::2], rotation=45, ha="right", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel("negative rate %")
        ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not worst.empty:
        plot = worst.head(120).copy()
        ax.scatter(np.arange(len(plot)), plot["return_pct"], s=12, color="#dc2626")
    ax.axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    ax.set_title("Worst Negative Windows")
    ax.set_ylabel("return %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    if not fixed.empty:
        fixed_summary = (
            fixed.groupby("horizon_days", as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values("horizon_days")
        )
        ax.plot(fixed_summary["horizon_days"], fixed_summary["negative_rate_pct"], marker="o", color="#16a34a")
    ax.set_title("Fixed Horizon Negative Rate")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("negative rate %")
    ax.grid(True, alpha=0.25)
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    injury_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> dict[str, Any]:
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    dds = pd.to_numeric(summary["max_dd_pct"], errors="coerce")
    status_counts = (
        ai_month_audit["status"].fillna("").astype(str).value_counts().to_dict()
        if "status" in ai_month_audit.columns
        else {}
    )
    return {
        "sample_count": int(len(summary)),
        "positive_count": int((returns > 0.0).sum()),
        "min_return_pct": float(returns.min()) if len(returns) else np.nan,
        "median_return_pct": float(returns.median()) if len(returns) else np.nan,
        "max_return_pct": float(returns.max()) if len(returns) else np.nan,
        "worst_max_dd_pct": float(dds.min()) if len(dds) else np.nan,
        "median_max_dd_pct": float(dds.median()) if len(dds) else np.nan,
        "min_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").min()) if len(summary) else np.nan,
        "median_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").median()) if len(summary) else np.nan,
        "retention_80pct_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "injury_pause_event_count": int(len(injury_events)),
        "injury_pause_reduced_volume_sum": (
            int(pd.to_numeric(injury_events.get("stage029_injury_pause_reduced_volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
            if not injury_events.empty
            else 0
        ),
        "injury_pause_drawdown_hit_count": (
            int(pd.to_numeric(injury_events.get("stage029_injury_pause_drawdown_hit", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
            if not injury_events.empty
            else 0
        ),
        "injury_pause_loss_streak_hit_count": (
            int(pd.to_numeric(injury_events.get("stage029_injury_pause_loss_streak_hit", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
            if not injury_events.empty
            else 0
        ),
        "all_gt1y_window_count": int(all_scope["window_count"].sum()) if not all_scope.empty else 0,
        "all_gt1y_negative_count": int(all_scope["negative_count"].sum()) if not all_scope.empty else 0,
        "all_gt1y_min_return_pct": float(all_scope["min_return_pct"].min()) if not all_scope.empty else np.nan,
        "to_final_window_count": int(final_scope["window_count"].sum()) if not final_scope.empty else 0,
        "to_final_negative_count": int(final_scope["negative_count"].sum()) if not final_scope.empty else 0,
        "to_final_min_return_pct": float(final_scope["min_return_pct"].min()) if not final_scope.empty else np.nan,
        "ai_month_status_counts": status_counts,
        "ai_post_first_fail_count": int(status_counts.get("FAIL", 0)),
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
    injury_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    report = f"""# Stage029 账户受伤状态暂停新 flat_entry 真实引擎候选

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 候选 profile：`{PROFILE_NAME}`
- 线上母本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`
- 回测区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`；起点为每年 `01-01/07-01`
- 阶段性质：独立研究 profile 真实引擎；不改官方 live config、不连接 CTP、不调用下单

## 外部调研判断

- 资料支持组合风险预算、仓位控制和 drawdown/tail-risk sizing；但趋势跟随的正偏右尾很脆弱，机械降风险容易错失恢复段。
- 本阶段采纳：只在账户已经受伤时暂停新的 `flat_entry`，不强平已有仓位，不影响 roll/retry/add，不改 AI 池。
- 本阶段否决：全局半风险、品种/方向黑名单、AI rank 阈值、pairwise rank 阈值、回测后再调 `20%/3`。

## 固定规则

- 若 opened `flat_entry` 入场前 `portfolio_drawdown_pct >= {INJURY_DRAWDOWN_TRIGGER_PCT}` 或 `loss_streak >= {INJURY_LOSS_STREAK_TRIGGER}`，则本次新开仓手数降为 `0` 并跳过。
- 只作用于新的 `flat_entry`；已有仓位、换月、加仓、反手、开仓日实时止损重试逻辑保持 C9 原样。

## 核心结果

- 正收益起点：`{metrics['positive_count']}/{metrics['sample_count']}`
- 期末收益 最小/中位/最大：`{metrics['min_return_pct']:.4f}% / {metrics['median_return_pct']:.4f}% / {metrics['max_return_pct']:.4f}%`
- 最差最大回撤：`{metrics['worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：`{metrics['all_gt1y_negative_count']}` / `{metrics['all_gt1y_window_count']}`
- 严格最差收益：`{metrics['all_gt1y_min_return_pct']:.4f}%`
- 到 `{REQUESTED_END.date()}` 负窗口：`{metrics['to_final_negative_count']}` / `{metrics['to_final_window_count']}`；最差 `{metrics['to_final_min_return_pct']:.4f}%`
- 80% 收益保留：`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`
- AI 月度审计 FAIL：`{metrics['ai_post_first_fail_count']}`
- 暂停事件：`{metrics['injury_pause_event_count']}`；减少手数：`{metrics['injury_pause_reduced_volume_sum']}`
- drawdown hit 次数：`{metrics['injury_pause_drawdown_hit_count']}`；loss_streak hit 次数：`{metrics['injury_pause_loss_streak_hit_count']}`

## 多起点摘要

{_md_table(summary, max_rows=30)}

## 目标审计摘要

{_md_table(aggregate.head(40), max_rows=40)}

## 收益保留

{_md_table(retention, max_rows=30)}

## AI 月度审计

{_md_table(ai_month_audit['status'].value_counts().rename_axis('status').reset_index(name='count'), max_rows=10) if 'status' in ai_month_audit.columns else '_无数据_'}

## 暂停事件样本

{_md_table(injury_events.head(40), max_rows=40)}

## 最差窗口

{_md_table(worst.head(40), max_rows=40)}

## 判断

- 决策：`{decision['decision']}`
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- summary: `{SUMMARY_PATH}`
- curves: `{CURVES_PATH}`
- entry_candidates: `{ENTRY_CANDIDATES_PATH}`
- trades: `{TRADES_PATH}`
- entry_risk: `{ENTRY_RISK_PATH}`
- trade_events: `{TRADE_EVENTS_PATH}`
- injury_pause_events: `{INJURY_PAUSE_EVENTS_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- performance_chart: `{PERFORMANCE_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage029_account_injury_flat_entry_pause_engine.md"
    metrics = decision["metrics"]
    content = f"""# Stage029 账户受伤状态暂停新 flat_entry 真实引擎候选

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}
- 工作区/分支：`{PROJECT_DIR}`
- 阶段性质：A/C 冻结真实引擎验证；A 为当前重建 C9/15w，C 为 Stage029
- 是否重要突破：否
- 是否触发A/B：是，触发 A vs C 真实引擎验证，但不晋级正式

## 外部调研与判断

- 参考资料：Concretum position sizing、Diva CTA position sizing、pysystemtrade、CFA/managed futures trend-following 资料。
- 我的判断：账户风险预算有第一性价值，但机械 drawdown gate 容易破坏趋势右尾；本阶段只验证一个冻结的新开仓暂停规则，不扫参数。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage029_account_injury_flat_entry_pause_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`enable_stage029_account_injury_pause_gate=True`、`stage029_injury_drawdown_trigger_pct={INJURY_DRAWDOWN_TRIGGER_PCT}`、`stage029_injury_loss_streak_trigger={INJURY_LOSS_STREAK_TRIGGER}`
- 修改参数：无，官方线上 C9/15w 配置未改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `{REQUESTED_END.date()}`
- 账户规模：`{OFFICIAL_LIVE_CAPITAL:,.0f}`
- 成本口径：沿用 C9/15w 真实引擎成本、滑点和合约乘数
- 样本过滤：每半年冷启动起点 `17` 个；目标审计覆盖 `2020-01-01` 到 `2025-06-30` 任意起点、周期大于一年
- 策略口径：仅当 opened `flat_entry` 入场前 `portfolio_drawdown_pct >= 20%` 或 `loss_streak >= 3` 时跳过该新开仓；不影响已有仓位、换月、加仓、反手、AI 池和开仓日实时止损重试

## 结果

- 期末权益最小/中位/最大：`{summary['end_equity'].min():,.2f}` / `{summary['end_equity'].median():,.2f}` / `{summary['end_equity'].max():,.2f}`
- 总收益最小/中位/最大：`{metrics['min_return_pct']:.4f}%` / `{metrics['median_return_pct']:.4f}%` / `{metrics['max_return_pct']:.4f}%`
- 最大回撤最差/中位：`{metrics['worst_max_dd_pct']:.4f}%` / `{metrics['median_max_dd_pct']:.4f}%`
- Sharpe 最小/中位/最大：`{summary['sharpe'].min():.4f}` / `{summary['sharpe'].median():.4f}` / `{summary['sharpe'].max():.4f}`
- 总滑点：`{summary['total_slippage'].sum():,.2f}`
- 总交易次数：`{summary['total_trade_count'].sum():,.0f}`
- 胜率中位：`{summary['nonzero_daily_win_rate_pct'].median():.4f}%`
- 暂停事件：`{metrics['injury_pause_event_count']}`；累计减少手数：`{metrics['injury_pause_reduced_volume_sum']}`
- 密集任意结束日 `>1` 年负窗口：`{metrics['all_gt1y_negative_count']}` / `{metrics['all_gt1y_window_count']}`，最差 `{metrics['all_gt1y_min_return_pct']:.4f}%`
- 到 `{REQUESTED_END.date()}` 负窗口：`{metrics['to_final_negative_count']}` / `{metrics['to_final_window_count']}`，最差 `{metrics['to_final_min_return_pct']:.4f}%`
- 全周期 `80%` 收益保留：`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`
- AI 月度审计 FAIL：`{metrics['ai_post_first_fail_count']}`

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- daily/curves：`{CURVES_PATH}`
- injury pause events：`{INJURY_PAUSE_EVENTS_PATH}`
- decision：`{DECISION_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`
- 是否进入下一步：不自动晋级；按结果决定是否需要失败归因或换方向。
- 下一步：若目标未达标，先做 Stage029 vs Stage006/013 的失败归因，不扫 `20%/25%/30%`、`loss_streak 2/3/4`、品种、方向或日期。

## 过拟合反思

- 运行前判断：有风险但可控；触发条件来自 Stage028，但冻结且只用入场前账户状态。
- 运行后判断：{decision['overfit_reflection_after']}
- 原因：若失败后继续微调阈值或按坏窗口筛品种，就是过拟合。

## 继续价值反思

- 运行前判断：有价值；它检验 Stage028 账户受伤状态是否能真实减少左尾。
- 运行后判断：{decision['continue_value_after']}
- 原因：真实引擎结果能决定账户受伤暂停是否值得进一步归因。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要 A/C 记录；`memory.md` 仅在结论改变长期策略时再追加
"""
    record_path.write_text(content, encoding="utf-8")
    return record_path


def _append_back_log(decision: dict[str, Any], summary: pd.DataFrame) -> None:
    metrics = decision["metrics"]
    path = PROJECT_DIR / "back_log.md"
    line = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage029 完成当前重建 C9/15w 的 "
        f"`DD>=20% OR loss_streak>=3 暂停新 flat_entry` 冻结 A/C 真实引擎验证，决策 "
        f"`{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage029_account_injury_flat_entry_pause_engine.py`；"
        f"不改正式配置、不连接 CTP、不调用订单 API。A 为 Stage006/Stage167 当前重建 C9/15w；C 为同一 C9 信号，"
        f"仅在 opened flat_entry 入场前 `portfolio_drawdown_pct>=20%` 或 `loss_streak>=3` 时跳过该新开仓，"
        f"不影响已有仓位、换月、加仓、反手、AI 池和开仓日实时止损重试。"
        f"C 多起点正收益 `{metrics['positive_count']}/{metrics['sample_count']}`，期末权益最小/中位/最大 "
        f"`{summary['end_equity'].min():,.2f}/{summary['end_equity'].median():,.2f}/{summary['end_equity'].max():,.2f}`，"
        f"总收益最小/中位/最大 `{metrics['min_return_pct']:.4f}%/{metrics['median_return_pct']:.4f}%/{metrics['max_return_pct']:.4f}%`，"
        f"最差最大回撤 `{metrics['worst_max_dd_pct']:.4f}%`，Sharpe 中位 `{metrics['median_sharpe']:.4f}`，"
        f"总滑点 `{summary['total_slippage'].sum():,.2f}`，总交易次数 `{summary['total_trade_count'].sum():,.0f}`，"
        f"胜率中位 `{summary['nonzero_daily_win_rate_pct'].median():.4f}%`，暂停事件 `{metrics['injury_pause_event_count']}`，"
        f"减少手数 `{metrics['injury_pause_reduced_volume_sum']}`，严格任意结束日 `>1` 年负窗口 "
        f"`{metrics['all_gt1y_negative_count']}/{metrics['all_gt1y_window_count']}`，最差 "
        f"`{metrics['all_gt1y_min_return_pct']:.4f}%`，到 `{REQUESTED_END.date()}` 负窗口 "
        f"`{metrics['to_final_negative_count']}/{metrics['to_final_window_count']}`，80% 收益保留 "
        f"`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`，AI FAIL `{metrics['ai_post_first_fail_count']}`。"
        f"运行前过拟合反思：有风险但可控，规则来自 Stage028 但冻结且不按品种/日期/source。"
        f"运行后过拟合反思：{decision['overfit_reflection_after']}。"
        f"运行前继续价值反思：有价值，检验账户受伤状态是否能真实减少左尾。"
        f"运行后继续价值反思：{decision['continue_value_after']}。"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    candidates = frames["entry_candidates"]
    injury_events = frames["injury_pause_events"]

    ai_month_audit, ai_pool_audit, ai_pool_meta = _ai_audit(candidates, summary)
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    _plot_performance(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    injury_events.to_csv(INJURY_PAUSE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_pool_audit.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, injury_events, ai_month_audit)
    strict_goal_pass = (
        metrics["all_gt1y_negative_count"] == 0
        and metrics["to_final_negative_count"] == 0
        and metrics["retention_80pct_pass_count"] == metrics["retention_rows"]
        and metrics["ai_post_first_fail_count"] == 0
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "candidate_profile_name": PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "stage029_parameters": {
            "drawdown_trigger_pct": INJURY_DRAWDOWN_TRIGGER_PCT,
            "loss_streak_trigger": INJURY_LOSS_STREAK_TRIGGER,
        },
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "ai_pool_audit": ai_pool_meta,
        "metrics": metrics,
        "decision": (
            "stage029_strict_goal_pass_research_candidate_needs_review"
            if strict_goal_pass
            else "stage029_goal_not_met_not_promoted"
        ),
        "strategy_changed": True,
        "official_live_strategy_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Position sizing and trend-following references support account-state risk governance, "
            "but right-tail preservation is the hard gate. Stage029 freezes one account-injury flat-entry pause."
        ),
        "overfit_reflection_before": (
            "有风险但可控。触发条件来自 Stage028，但冻结为 DD>=20% 或 loss_streak>=3，"
            "不按品种、方向、日期、source 或 AI rank 调参。"
        ),
        "continue_value_before": (
            "有。Stage028 指向账户受伤后的新开仓风险释放，必须用真实引擎验证。"
        ),
        "overfit_reflection_after": (
            "待运行结果解释；如果失败，不继续扫 20/25/30、loss_streak 2/3/4、品种、方向或日期。"
        ),
        "continue_value_after": "待运行结果解释。",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "injury_pause_events": str(INJURY_PAUSE_EVENTS_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "retention": str(RETENTION_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    if strict_goal_pass:
        decision["overfit_reflection_after"] = "否，但仍需独立复核和成本敏感验证；本阶段没有调参。"
        decision["continue_value_after"] = "有。进入下一轮复核，但不能直接上线。"
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段没有根据结果微调阈值；若继续救该形状的小阈值或局部窗口，就是过拟合。"
        )
        decision["continue_value_after"] = (
            "有限。若目标未达标，应先做失败归因；不要直接继续扫账户回撤或 loss_streak 阈值。"
        )

    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, worst, retention, injury_events, ai_month_audit)
    stage_record = _write_stage_record(decision, summary)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _append_back_log(decision, summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
