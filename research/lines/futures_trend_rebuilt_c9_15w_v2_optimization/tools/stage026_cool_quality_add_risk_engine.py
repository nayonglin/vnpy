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
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage026"
MODEL_TAG = "stage026_cool_quality_add_risk_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage026_cool_quality_add_risk_engine"
PROFILE_NAME = "stage026_cool_quality_add_risk_engine"

V2_LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
UPSTREAM_TOOLS_DIR = UPSTREAM_LINE_DIR / "tools"
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(UPSTREAM_TOOLS_DIR), str(PORTFOLIO_DIR)):
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


REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")

STAGE026_AI_RANK_MIN = 1
STAGE026_AI_RANK_MAX = 4
STAGE026_LONG_RSI_EXHAUSTION_MIN = 75.0
STAGE026_SHORT_RSI_EXHAUSTION_MAX = 25.0
STAGE026_MAX_RISK_MULTIPLIER = 2.0
STAGE026_ADD_RISK_FRACTION = 0.25

OUTPUT_DIR = V2_LINE_DIR / "outputs" / "stage026_cool_quality_add_risk_engine"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
STAGE026_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cool_quality_add_risk_events_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_stage013_{MODEL_TAG}.csv"
AB_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ab_summary_vs_stage013_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
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


def _to_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_int(value: Any, default: int = 0) -> int:
    number = _to_float(value, np.nan)
    if not np.isfinite(number):
        return default
    return int(number)


def _stage026_is_rsi_exhaustion(direction: str, rsi_value: float) -> bool:
    side = str(direction or "").strip().lower()
    if not np.isfinite(rsi_value):
        return False
    if side == "long":
        return rsi_value >= STAGE026_LONG_RSI_EXHAUSTION_MIN
    if side == "short":
        return rsi_value <= STAGE026_SHORT_RSI_EXHAUSTION_MAX
    return False


def _stage026_sizing_with_signal_fields(plan: dict[str, Any]) -> dict[str, Any]:
    sizing = dict(plan.get("sizing") or {})
    signal_data = dict(plan.get("signal_data") or {})
    for key in ["rsi_value", "bullish_alignment", "bearish_alignment", "breakout"]:
        if key not in sizing or pd.isna(sizing.get(key)):
            sizing[key] = signal_data.get(key)
    for key in ["selected_volume", "ai_product_pool_rank", "ai_product_pool_score", "risk_multiplier"]:
        if key not in sizing or pd.isna(sizing.get(key)):
            sizing[key] = plan.get(key)
    return sizing


def _stage026_apply_cool_quality_add_risk(
    *,
    sizing: dict[str, Any],
    direction: str,
    entry_context: str,
    enabled: bool,
    add_risk_fraction: float = STAGE026_ADD_RISK_FRACTION,
    ai_rank_min: int = STAGE026_AI_RANK_MIN,
    ai_rank_max: int = STAGE026_AI_RANK_MAX,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, _to_int(sizing.get("selected_volume"), 0))
    ai_rank = _to_float(sizing.get("ai_product_pool_rank"), np.nan)
    rsi_value = _to_float(sizing.get("rsi_value"), np.nan)
    risk_multiplier = _to_float(sizing.get("risk_multiplier"), np.nan)
    ai_rank_hit = bool(np.isfinite(ai_rank) and ai_rank_min <= ai_rank <= ai_rank_max)
    rsi_exhaustion_hit = _stage026_is_rsi_exhaustion(direction, rsi_value)
    risk_hit = bool(np.isfinite(risk_multiplier) and risk_multiplier < STAGE026_MAX_RISK_MULTIPLIER)
    selected_volume_hit = selected_before > 1
    selected_after_candidate = int(np.floor(float(selected_before) * (1.0 + float(add_risk_fraction))))
    added_volume = max(0, selected_after_candidate - selected_before)

    selected_after = selected_before
    applied = 0
    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif not selected_volume_hit:
        reason = "selected_volume_not_above_one"
    elif not ai_rank_hit:
        reason = "ai_rank_outside_stage026_top_band"
    elif not risk_hit:
        reason = "risk_multiplier_not_below_stage026_floor"
    elif rsi_exhaustion_hit:
        reason = "rsi_in_stage026_exhaustion_zone"
    elif added_volume <= 0:
        reason = "floor25_no_integer_increment"
    else:
        selected_after = selected_after_candidate
        applied = 1
        reason = "stage026_cool_quality_floor25_add_risk"

    fields = {
        "stage026_cool_quality_add_risk_enabled": int(bool(enabled)),
        "stage026_cool_quality_add_risk_applied": applied,
        "stage026_cool_quality_add_risk_reason": reason,
        "stage026_cool_quality_selected_volume_before": selected_before,
        "stage026_cool_quality_selected_volume_after": selected_after,
        "stage026_cool_quality_add_risk_added_volume": selected_after - selected_before,
        "stage026_cool_quality_candidate_added_volume": added_volume,
        "stage026_cool_quality_ai_rank": ai_rank,
        "stage026_cool_quality_ai_rank_min": int(ai_rank_min),
        "stage026_cool_quality_ai_rank_max": int(ai_rank_max),
        "stage026_cool_quality_ai_rank_hit": int(ai_rank_hit),
        "stage026_cool_quality_rsi_value": rsi_value,
        "stage026_cool_quality_long_rsi_exhaustion_min": STAGE026_LONG_RSI_EXHAUSTION_MIN,
        "stage026_cool_quality_short_rsi_exhaustion_max": STAGE026_SHORT_RSI_EXHAUSTION_MAX,
        "stage026_cool_quality_rsi_exhaustion_hit": int(rsi_exhaustion_hit),
        "stage026_cool_quality_risk_multiplier": risk_multiplier,
        "stage026_cool_quality_risk_multiplier_max_exclusive": STAGE026_MAX_RISK_MULTIPLIER,
        "stage026_cool_quality_risk_multiplier_hit": int(risk_hit),
        "stage026_cool_quality_selected_volume_hit": int(selected_volume_hit),
        "stage026_cool_quality_add_risk_fraction": float(add_risk_fraction),
        "stage026_cool_quality_direction": str(direction or ""),
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage026CoolQualityAddRisk(
    s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate
):
    enable_stage026_cool_quality_add_risk: bool = False
    stage026_ai_rank_min: int = STAGE026_AI_RANK_MIN
    stage026_ai_rank_max: int = STAGE026_AI_RANK_MAX
    stage026_add_risk_fraction: float = STAGE026_ADD_RISK_FRACTION

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage026_cool_quality_add_risk",
        "stage026_ai_rank_min",
        "stage026_ai_rank_max",
        "stage026_add_risk_fraction",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage026_cool_quality_add_risk_count",
        "stage026_cool_quality_add_risk_added_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage026_cool_quality_add_risk_events: list[dict[str, Any]] = []
        self.stage026_cool_quality_add_risk_count: int = 0
        self.stage026_cool_quality_add_risk_added_volume: int = 0

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage026_cool_quality_add_risk:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = _stage026_sizing_with_signal_fields(plan)
            selected_after, fields = _stage026_apply_cool_quality_add_risk(
                sizing=sizing,
                direction=str(plan.get("direction") or ""),
                entry_context="flat_entry",
                enabled=bool(self.enable_stage026_cool_quality_add_risk),
                add_risk_fraction=float(self.stage026_add_risk_fraction),
                ai_rank_min=int(self.stage026_ai_rank_min),
                ai_rank_max=int(self.stage026_ai_rank_max),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage026_cool_quality_add_risk_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            event = self._stage026_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage026_cool_quality_add_risk_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage026_cool_quality_add_risk_count += 1
            self.stage026_cool_quality_add_risk_added_volume += int(
                fields["stage026_cool_quality_add_risk_added_volume"]
            )
        return plans

    def _stage026_event_from_plan(
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
            "reason": "stage026_cool_quality_add_risk",
            "volume": int(fields["stage026_cool_quality_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage026_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage026 cool quality add-risk engine",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage026 isolated research candidate. "
            "Keep Stage013 account-state pilot and C9 stop-retry unchanged; when a new flat-entry has "
            "top AI rank, risk multiplier below 2 and no RSI exhaustion, increase integer size by floor 25%."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage026_cool_quality_add_risk": True,
        "stage026_ai_rank_min": STAGE026_AI_RANK_MIN,
        "stage026_ai_rank_max": STAGE026_AI_RANK_MAX,
        "stage026_add_risk_fraction": STAGE026_ADD_RISK_FRACTION,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage026CoolQualityAddRisk
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage026(
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
        profile = _stage026_profile(metadata)
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


def _build_start_dates() -> list[pd.Timestamp]:
    return [pd.Timestamp(value).normalize() for value in s167._build_start_dates()]


def _run_multistart() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = _build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage026] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage026(metadata, start, REQUESTED_END)

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
    stage026_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage026_cool_quality_add_risk")].copy()
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
        "stage026_events": stage026_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s013.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_stage013", "_stage026"),
    )
    merged["stage026_vs_stage013_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage026"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage026"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _ab_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s013.SUMMARY_PATH, encoding="utf-8-sig")
    cols = [
        "requested_start_month",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_stage013_A", "_stage026_C"),
    )
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]:
        merged[f"{metric}_delta_C_minus_A"] = (
            pd.to_numeric(merged[f"{metric}_stage026_C"], errors="coerce")
            - pd.to_numeric(merged[f"{metric}_stage013_A"], errors="coerce")
        )
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage026_engine"
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
    axes[0].set_title("Stage026 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage026 Drawdown By Cold Start")
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
        plot = worst.head(160).copy()
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


def _baseline_goal_metrics() -> dict[str, Any]:
    if not s013.GOAL_AGGREGATE_PATH.exists():
        return {}
    aggregate = pd.read_csv(s013.GOAL_AGGREGATE_PATH, encoding="utf-8-sig")
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    return {
        "stage013_all_gt1y_negative_count": int(all_scope["negative_count"].sum()) if not all_scope.empty else 0,
        "stage013_all_gt1y_window_count": int(all_scope["window_count"].sum()) if not all_scope.empty else 0,
        "stage013_all_gt1y_min_return_pct": float(all_scope["min_return_pct"].min()) if not all_scope.empty else np.nan,
        "stage013_to_final_negative_count": int(final_scope["negative_count"].sum()) if not final_scope.empty else 0,
        "stage013_to_final_window_count": int(final_scope["window_count"].sum()) if not final_scope.empty else 0,
        "stage013_to_final_min_return_pct": float(final_scope["min_return_pct"].min()) if not final_scope.empty else np.nan,
    }


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    stage026_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
    ab_summary: pd.DataFrame,
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
    metrics = {
        "sample_count": int(len(summary)),
        "positive_count": int((returns > 0.0).sum()),
        "min_end_equity": float(pd.to_numeric(summary["end_equity"], errors="coerce").min()) if len(summary) else np.nan,
        "median_end_equity": float(pd.to_numeric(summary["end_equity"], errors="coerce").median()) if len(summary) else np.nan,
        "max_end_equity": float(pd.to_numeric(summary["end_equity"], errors="coerce").max()) if len(summary) else np.nan,
        "min_return_pct": float(returns.min()) if len(returns) else np.nan,
        "median_return_pct": float(returns.median()) if len(returns) else np.nan,
        "max_return_pct": float(returns.max()) if len(returns) else np.nan,
        "worst_max_dd_pct": float(dds.min()) if len(dds) else np.nan,
        "median_max_dd_pct": float(dds.median()) if len(dds) else np.nan,
        "min_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").min()) if len(summary) else np.nan,
        "median_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").median()) if len(summary) else np.nan,
        "total_slippage": float(pd.to_numeric(summary["total_slippage"], errors="coerce").sum()) if len(summary) else 0.0,
        "total_trade_count": float(pd.to_numeric(summary["total_trade_count"], errors="coerce").sum()) if len(summary) else 0.0,
        "median_win_rate_pct": float(pd.to_numeric(summary["nonzero_daily_win_rate_pct"], errors="coerce").median())
        if len(summary)
        else np.nan,
        "retention_80pct_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "stage026_event_count": int(len(stage026_events)),
        "stage026_added_volume_sum": (
            int(
                pd.to_numeric(
                    stage026_events.get("stage026_cool_quality_add_risk_added_volume", pd.Series(dtype=float)),
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
            if not stage026_events.empty
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
        "return_win_count_vs_stage013": int((ab_summary["total_return_pct_delta_C_minus_A"] > 0).sum())
        if "total_return_pct_delta_C_minus_A" in ab_summary.columns
        else 0,
        "return_compare_rows": int(len(ab_summary)),
        "median_return_delta_vs_stage013": float(
            pd.to_numeric(ab_summary.get("total_return_pct_delta_C_minus_A"), errors="coerce").median()
        )
        if len(ab_summary)
        else np.nan,
        "median_dd_delta_vs_stage013": float(
            pd.to_numeric(ab_summary.get("max_dd_pct_delta_C_minus_A"), errors="coerce").median()
        )
        if len(ab_summary)
        else np.nan,
    }
    metrics.update(_baseline_goal_metrics())
    return metrics


def _make_decision(metrics: dict[str, Any]) -> str:
    strict_goal_pass = (
        metrics["all_gt1y_negative_count"] == 0
        and metrics["to_final_negative_count"] == 0
        and metrics["retention_80pct_pass_count"] == metrics["retention_rows"]
        and metrics["ai_post_first_fail_count"] == 0
    )
    if strict_goal_pass:
        return "stage026_strict_goal_pass_needs_independent_review"
    base_neg = metrics.get("stage013_all_gt1y_negative_count")
    if (
        base_neg is not None
        and metrics["all_gt1y_negative_count"] < int(base_neg)
        and metrics["retention_80pct_pass_count"] == metrics["retention_rows"]
        and metrics["return_win_count_vs_stage013"] >= max(1, metrics["return_compare_rows"] // 2)
    ):
        return "stage026_directionally_positive_needs_full_ab_review"
    return "stage026_not_promoted_keep_for_attribution"


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
    ab_summary: pd.DataFrame,
    stage026_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    report = f"""# Stage026 冷静高质量加风险真实引擎 A/B

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- A：Stage013 account-state pilot gate。
- C：Stage013 + Stage026 cool quality add-risk engine。
- 线上母本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`
- 回测区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`；起点为每年 `01-01/07-01`
- 阶段性质：独立研究 profile 真实引擎；不改官方 live config、不连接 CTP、不调用下单

## 外部调研判断

- Rob Carver / pysystemtrade 框架强调 forecast、position sizing、组合风险和成本要拆开验证；本阶段只改高质量入场的风险投入，不改 AI 月池和信号。
- 金融机器学习回测资料强调 point-in-time 和 purged/样本外验证，不能从已知亏损窗口直接写品种/日期黑名单；本阶段只使用入场前可见字段。
- 趋势跟随资料提示仓位放大必须服务于已经存在的结构优势；因此 C 只在 top AI、risk<2 且非 RSI 极端顺势时做 floor 25% 整数加风险，不做 ceil 或最小加 1 手。

## 固定规则

- 只作用于 opened `flat_entry`。
- 条件：`AI rank 1-4`、`selected_volume>1`、`risk_multiplier<2` 且不处于 `long RSI>=75 / short RSI<=25` 的极端顺势区。
- 动作：该次新开仓按 `floor(selected_volume * 1.25)` 增加整数手数；若 floor 后没有整数增量，则不强行加仓。已有仓位、换月、加仓、反手、开仓日实时止损重试、AI 月池、保证金和成本逻辑保持 C9/Stage013 原样。

## 核心结果

- 正收益起点：`{metrics['positive_count']}/{metrics['sample_count']}`
- 期末权益 最小/中位/最大：`{metrics['min_end_equity']:,.2f}` / `{metrics['median_end_equity']:,.2f}` / `{metrics['max_end_equity']:,.2f}`
- 总收益 最小/中位/最大：`{metrics['min_return_pct']:.4f}%` / `{metrics['median_return_pct']:.4f}%` / `{metrics['max_return_pct']:.4f}%`
- 最大回撤 最差/中位：`{metrics['worst_max_dd_pct']:.4f}%` / `{metrics['median_max_dd_pct']:.4f}%`
- Sharpe 最小/中位：`{metrics['min_sharpe']:.4f}` / `{metrics['median_sharpe']:.4f}`
- 总滑点：`{metrics['total_slippage']:,.2f}`
- 总交易次数：`{metrics['total_trade_count']:,.0f}`
- 胜率中位：`{metrics['median_win_rate_pct']:.4f}%`
- 80% 收益保留：`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`
- 严格任意结束日 `>1` 年负窗口：`{metrics['all_gt1y_negative_count']}` / `{metrics['all_gt1y_window_count']}`；最差 `{metrics['all_gt1y_min_return_pct']:.4f}%`
- Stage013 A 对应负窗口：`{metrics.get('stage013_all_gt1y_negative_count', 'NA')}` / `{metrics.get('stage013_all_gt1y_window_count', 'NA')}`；最差 `{metrics.get('stage013_all_gt1y_min_return_pct', np.nan):.4f}%`
- 到 `{REQUESTED_END.date()}` 负窗口：`{metrics['to_final_negative_count']}` / `{metrics['to_final_window_count']}`；最差 `{metrics['to_final_min_return_pct']:.4f}%`
- AI 月度审计 FAIL：`{metrics['ai_post_first_fail_count']}`
- Stage026 触发事件：`{metrics['stage026_event_count']}`；增加手数：`{metrics['stage026_added_volume_sum']}`
- A/B 收益胜出：`{metrics['return_win_count_vs_stage013']}/{metrics['return_compare_rows']}`；收益差中位 `{metrics['median_return_delta_vs_stage013']:.4f}pp`
- 决策：`{decision['decision']}`

## A/B 摘要

{_md_table(ab_summary, max_rows=30)}

## C 多起点摘要

{_md_table(summary, max_rows=30)}

## 目标审计摘要

{_md_table(aggregate.head(40), max_rows=40)}

## 收益保留

{_md_table(retention, max_rows=30)}

## AI 月度审计

{_md_table(ai_month_audit['status'].value_counts().rename_axis('status').reset_index(name='count'), max_rows=10) if 'status' in ai_month_audit.columns else '_无数据_'}

## Stage026 事件样本

{_md_table(stage026_events.head(40), max_rows=40)}

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
- stage026_events: `{STAGE026_EVENTS_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- ab_summary: `{AB_SUMMARY_PATH}`
- performance_chart: `{PERFORMANCE_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> Path:
    stage_dir = V2_LINE_DIR / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    record_path = stage_dir / "20260702_0649_stage026_cool_quality_add_risk_engine.md"
    metrics = decision["metrics"]
    lines = [
        "# Stage026 冷静高质量加风险真实引擎 A/B",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        f"- 工作区/分支：`{PROJECT_DIR}`",
        "- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：是；A=Stage013，C=Stage013+Stage026",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：pysystemtrade/Rob Carver systematic trading、金融机器学习 point-in-time/backtest overfitting、趋势跟随 RSI/whipsaw 资料。",
        "- 我的判断：Stage025 说明质量加风险桶也参与剩余左尾，因此真实引擎只能做 top AI 且不过热状态的冻结质量拆分；必须保持 AI 月池、止损重试、保证金、整数手和成本逻辑不变。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        f"- 新增参数：`stage026_ai_rank_min={STAGE026_AI_RANK_MIN}`、`stage026_ai_rank_max={STAGE026_AI_RANK_MAX}`、"
        f"`stage026_long_rsi_exhaustion_min={STAGE026_LONG_RSI_EXHAUSTION_MIN}`、"
        f"`stage026_short_rsi_exhaustion_max={STAGE026_SHORT_RSI_EXHAUSTION_MAX}`、"
        f"`stage026_max_risk_multiplier={STAGE026_MAX_RISK_MULTIPLIER}`、"
        f"`stage026_add_risk_fraction={STAGE026_ADD_RISK_FRACTION}`",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        f"- 数据区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`",
        f"- 账户规模：`{OFFICIAL_LIVE_CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。",
        "- 样本过滤：每半年独立冷启动。",
        "- 策略/归因口径：C 只对 opened flat_entry 中 `AI rank 1-4 + selected_volume>1 + risk_multiplier<2 + 非 RSI 极端顺势` 按 floor 25% 增加整数手数。",
        "",
        "## 结果",
        "",
        f"- 期末权益：最小 `{metrics['min_end_equity']:,.2f}`；中位 `{metrics['median_end_equity']:,.2f}`；最大 `{metrics['max_end_equity']:,.2f}`",
        f"- 总收益：最小 `{metrics['min_return_pct']:.4f}%`；中位 `{metrics['median_return_pct']:.4f}%`；最大 `{metrics['max_return_pct']:.4f}%`",
        f"- 最大回撤：最差 `{metrics['worst_max_dd_pct']:.4f}%`；中位 `{metrics['median_max_dd_pct']:.4f}%`",
        f"- Sharpe：最小 `{metrics['min_sharpe']:.4f}`；中位 `{metrics['median_sharpe']:.4f}`",
        f"- 总滑点：`{metrics['total_slippage']:,.2f}`",
        f"- 总交易次数：`{metrics['total_trade_count']:,.0f}`",
        f"- 胜率：中位 `{metrics['median_win_rate_pct']:.4f}%`",
        f"- 80% 收益保留：`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`",
        f"- 严格任意结束日 >1 年负窗口：`{metrics['all_gt1y_negative_count']}/{metrics['all_gt1y_window_count']}`，最差 `{metrics['all_gt1y_min_return_pct']:.4f}%`",
        f"- 到终点负窗口：`{metrics['to_final_negative_count']}/{metrics['to_final_window_count']}`，最差 `{metrics['to_final_min_return_pct']:.4f}%`",
        f"- Stage026 触发事件：`{metrics['stage026_event_count']}`；增加手数 `{metrics['stage026_added_volume_sum']}`",
        f"- A/B 收益胜出：`{metrics['return_win_count_vs_stage013']}/{metrics['return_compare_rows']}`；收益差中位 `{metrics['median_return_delta_vs_stage013']:.4f}pp`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 本阶段结论：`{decision['decision']}`",
            "- 是否进入下一步：仅当 C 明显改善目标且收益保留过线时才继续；否则保留为只读归因。",
            "- 下一步：根据结果决定是否拆分 top AI cool-quality 的真实贡献，不能追加品种/日期黑名单或改成 ceil/min+1 救参。",
            "",
            "## 过拟合反思",
            "",
            f"- 运行前判断：{decision['overfit_reflection_before']}",
            f"- 运行后判断：{decision['overfit_reflection_after']}",
            "- 原因：本阶段只有一个预声明规则，但标签来自 Stage025 剩余左尾归因，若继续叠条件救结果会过拟合。",
            "",
            "## 继续价值反思",
            "",
            f"- 运行前判断：{decision['continue_value_before']}",
            f"- 运行后判断：{decision['continue_value_after']}",
            "- 原因：真实引擎结果能判断 Stage025 的质量拆分是否只是归因幻觉。",
            "",
            "## 合入建议",
            "",
            "- 是否更新本线 `LINE.md`：是。",
            "- 是否更新 `research/registry.md`：是。",
            "- 是否追加根目录 `memory.md/back_log.md`：否，除非结果成为正式候选或重要路线废弃。",
        ]
    )
    record_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return record_path


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    candidates = frames["entry_candidates"]
    stage026_events = frames["stage026_events"]

    ai_month_audit, ai_pool_audit, ai_pool_meta = _ai_audit(candidates, summary)
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    ab_summary = _ab_summary(summary)

    _plot_performance(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    stage026_events.to_csv(STAGE026_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_pool_audit.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    ab_summary.to_csv(AB_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, stage026_events, ai_month_audit, ab_summary)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_A": "stage013_account_state_pilot_gate_engine",
        "candidate_C": PROFILE_NAME,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "stage026_parameters": {
            "ai_rank_min": STAGE026_AI_RANK_MIN,
            "ai_rank_max": STAGE026_AI_RANK_MAX,
            "long_rsi_exhaustion_min": STAGE026_LONG_RSI_EXHAUSTION_MIN,
            "short_rsi_exhaustion_max": STAGE026_SHORT_RSI_EXHAUSTION_MAX,
            "max_risk_multiplier_exclusive": STAGE026_MAX_RISK_MULTIPLIER,
            "add_risk_fraction": STAGE026_ADD_RISK_FRACTION,
        },
        "ai_pool_audit": ai_pool_meta,
        "metrics": metrics,
        "decision": _make_decision(metrics),
        "strategy_changed": True,
        "official_live_strategy_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "External systematic-trading references support testing PIT sizing/add-risk overlays, "
            "but not product/date blacklists or post-hoc labels. Stage026 freezes one low-degree true-engine rule."
        ),
        "overfit_reflection_before": (
            "有风险。Stage026 的条件来自 Stage025 对剩余左尾的反向约束；通过只使用 PIT 字段、固定 top rank/risk/RSI 结构和 floor 25% 整数加风险来控制。"
        ),
        "continue_value_before": (
            "有价值。它直接检验 Stage010/013 的质量加风险能否在真实组合引擎里保留右尾并减少一年以上左尾，而不是继续做代理曲线。"
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "stage026_events": str(STAGE026_EVENTS_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "ai_pool_audit": str(AI_POOL_AUDIT_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "ab_summary": str(AB_SUMMARY_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    if decision["decision"] == "stage026_strict_goal_pass_needs_independent_review":
        decision["overfit_reflection_after"] = (
            "仍需谨慎。虽然达到当前硬目标，但规则来自 residual attribution，必须独立复核和成本压力测试后才能讨论正式化。"
        )
        decision["continue_value_after"] = "有价值，应进入独立 agent/code review 和更密集起点压力测试。"
    elif decision["decision"] == "stage026_directionally_positive_needs_full_ab_review":
        decision["overfit_reflection_after"] = (
            "有过拟合风险但未失控。C 改善了部分目标且收益保留过线，下一步只能做预声明拆解，不能追加救参条件。"
        )
        decision["continue_value_after"] = "有价值，作为低自由度候选继续审计。"
    else:
        decision["overfit_reflection_after"] = (
            "有过拟合风险且真实引擎证据不足。不能因为归因 lift 高就继续叠条件救结果。"
        )
        decision["continue_value_after"] = "有限。若结果没有改善负窗口，应停止该组合规则，回到更外生的信号或账户层结构。"

    _write_report(decision, summary, aggregate, worst, retention, ab_summary, stage026_events, ai_month_audit)
    decision["outputs"]["stage_record"] = str(_write_stage_record(decision, summary))
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
