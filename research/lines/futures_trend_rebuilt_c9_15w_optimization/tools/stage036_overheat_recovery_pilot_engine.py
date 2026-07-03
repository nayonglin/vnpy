from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
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
import stage018_regime_pilot_gate_engine as s018
import stage034_stage033_remaining_negative_precursor as s034
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage036"
MODEL_TAG = "stage036_overheat_recovery_pilot_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage036_overheat_recovery_pilot_engine"
PROFILE_NAME = "stage036_overheat_recovery_pilot_engine"

TARGET_REGIME = "high_vol_high_eff"
OVERHEAT_RETURN_63D_PCT = 20.0
RECOVERY_DRAWDOWN_PROTECT_PCT = 0.30
RECOVERY_RETURN_63D_PROTECT_PCT = -20.0
CONSENSUS_MIN = 1
CONSENSUS_MAX = 3
PILOT_MIN_VOLUME = 1
RETURN_LOOKBACK_DAYS = 63
REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage036_overheat_recovery_pilot_engine"
STAGE_RECORD_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
OVERHEAT_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overheat_events_{MODEL_TAG}.csv"
AI_MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_monthly_state_{MODEL_TAG}.csv"
REGIME_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_causal_regime_table_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


EXTERNAL_RESEARCH_JUDGMENT = (
    "Trend-following references favor preserving right-tail convexity and using risk budgets instead of broad "
    "winner-cutting filters. Stage036 therefore caps only a frozen overheat state to a one-contract pilot and "
    "explicitly exempts deep-drawdown or 63-day-loss recovery states."
)


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _normalize_drawdown_ratio(value: Any) -> float:
    return s013._normalize_drawdown_ratio(value)


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _stage036_apply_overheat_recovery_gate(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    regime_info: dict[str, Any] | None,
    account_state: dict[str, Any] | None,
    ai_state: dict[str, Any] | None,
    min_position_size: int,
    enabled: bool,
    target_regime: str = TARGET_REGIME,
    overheat_return_63d_pct: float = OVERHEAT_RETURN_63D_PCT,
    recovery_drawdown_pct: float = RECOVERY_DRAWDOWN_PROTECT_PCT,
    recovery_return_63d_pct: float = RECOVERY_RETURN_63D_PROTECT_PCT,
    consensus_min: int = CONSENSUS_MIN,
    consensus_max: int = CONSENSUS_MAX,
    pilot_min_volume: int = PILOT_MIN_VOLUME,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    min_size = max(0, int(min_position_size or 0))
    pilot_volume = max(0, int(pilot_min_volume or 0))
    info = dict(regime_info or {})
    account = dict(account_state or {})
    ai = dict(ai_state or {})

    regime = str(info.get("stage018_joint_regime") or "missing")
    return_63d_pct = _safe_float(account.get("portfolio_return_63d_pct"))
    drawdown_ratio = _normalize_drawdown_ratio(account.get("portfolio_drawdown_pct", 0.0))
    consensus_count = _safe_float(ai.get("consensus_top8_count"))
    consensus_count_int = int(consensus_count) if math.isfinite(consensus_count) else -1

    selected_after = selected_before
    applied = 0
    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif regime != str(target_regime):
        reason = "regime_not_target"
    elif not math.isfinite(consensus_count):
        reason = "ai_consensus_missing"
    elif not (int(consensus_min) <= consensus_count_int <= int(consensus_max)):
        reason = "consensus_not_narrow"
    elif drawdown_ratio >= _normalize_drawdown_ratio(recovery_drawdown_pct):
        reason = "recovery_drawdown_protected"
    elif math.isfinite(return_63d_pct) and return_63d_pct <= float(recovery_return_63d_pct):
        reason = "recovery_63d_loss_protected"
    elif not math.isfinite(return_63d_pct):
        reason = "insufficient_63d_account_history"
    elif return_63d_pct <= float(overheat_return_63d_pct):
        reason = "account_not_overheated_63d"
    else:
        selected_after = min(selected_before, max(min_size, pilot_volume))
        if 0 < selected_after < min_size:
            selected_after = 0
        applied = int(selected_after != selected_before)
        reason = "stage036_overheat_high_vol_narrow_consensus_pilot" if applied else "already_at_stage036_pilot_size"

    fields = {
        "stage036_overheat_gate_enabled": int(bool(enabled)),
        "stage036_overheat_gate_applied": applied,
        "stage036_overheat_gate_reason": reason,
        "stage036_overheat_gate_target_regime": str(target_regime),
        "stage036_overheat_gate_joint_regime": regime,
        "stage036_overheat_gate_source_date": str(info.get("stage018_regime_source_date") or ""),
        "stage036_overheat_gate_vol60_bucket": str(info.get("stage018_vol60_bucket") or "missing"),
        "stage036_overheat_gate_eff60_bucket": str(info.get("stage018_eff60_bucket") or "missing"),
        "stage036_overheat_gate_return_63d_pct": return_63d_pct,
        "stage036_overheat_gate_return_63d_trigger_pct": float(overheat_return_63d_pct),
        "stage036_overheat_gate_drawdown_pct": drawdown_ratio,
        "stage036_overheat_gate_recovery_drawdown_protect_pct": _normalize_drawdown_ratio(recovery_drawdown_pct),
        "stage036_overheat_gate_recovery_return_63d_protect_pct": float(recovery_return_63d_pct),
        "stage036_overheat_gate_consensus_top8_count": consensus_count,
        "stage036_overheat_gate_consensus_min": int(consensus_min),
        "stage036_overheat_gate_consensus_max": int(consensus_max),
        "stage036_overheat_gate_selected_volume_before": selected_before,
        "stage036_overheat_gate_selected_volume_after": selected_after,
        "stage036_overheat_gate_reduced_volume": selected_before - selected_after,
        "stage036_overheat_gate_pilot_min_volume": pilot_volume,
    }
    return selected_after, fields


def _stage036_ai_monthly_summary() -> pd.DataFrame:
    monthly = s034._ai_monthly_summary().copy()
    monthly["eval_date"] = pd.to_datetime(monthly["eval_date"], errors="coerce").dt.normalize()
    monthly = monthly.dropna(subset=["eval_date"]).sort_values("eval_date").reset_index(drop=True)
    return monthly


class QmtRollPortfolioStrategyStage036OverheatRecoveryPilot(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage036_overheat_recovery_gate: bool = False
    stage036_market_daily_path: str = str(s018.MARKET_DAILY_PATH)
    stage036_pilot_min_volume: int = PILOT_MIN_VOLUME

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage036_overheat_recovery_gate",
        "stage036_market_daily_path",
        "stage036_pilot_min_volume",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage036_overheat_gate_count",
        "stage036_overheat_gate_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage036_overheat_gate_events: list[dict[str, Any]] = []
        self.stage036_overheat_gate_count: int = 0
        self.stage036_overheat_gate_reduced_volume: int = 0
        self.stage036_equity_history: list[float] = []
        self.stage036_regime_by_date = s018._stage018_load_regime_map(
            str(getattr(self, "stage036_market_daily_path", str(s018.MARKET_DAILY_PATH)) or s018.MARKET_DAILY_PATH)
        )
        self.stage036_ai_monthly = _stage036_ai_monthly_summary()

    def on_bars(self, bars: dict[Any, Any]) -> None:
        super().on_bars(bars)
        equity = _safe_float(getattr(self, "estimated_equity", self.base_capital), float(self.base_capital))
        if math.isfinite(equity) and equity > 0:
            self.stage036_equity_history.append(equity)

    def _stage036_account_state(self) -> dict[str, Any]:
        history = np.array(self.stage036_equity_history, dtype="float64")
        history = history[np.isfinite(history)]
        return_63d = float("nan")
        if len(history) > RETURN_LOOKBACK_DAYS and history[-(RETURN_LOOKBACK_DAYS + 1)] > 0:
            return_63d = float(history[-1] / history[-(RETURN_LOOKBACK_DAYS + 1)] - 1.0) * 100.0
        return {
            "portfolio_return_63d_pct": return_63d,
            "portfolio_drawdown_pct": float(getattr(self, "portfolio_drawdown_pct", 0.0) or 0.0),
            "stage036_equity_history_count": int(len(history)),
        }

    def _stage036_ai_state(self, date_key: str) -> dict[str, Any]:
        if self.stage036_ai_monthly.empty:
            return {"consensus_top8_count": float("nan"), "eval_date": ""}
        date = pd.Timestamp(date_key).normalize()
        eval_dates = self.stage036_ai_monthly["eval_date"].to_numpy(dtype="datetime64[ns]")
        idx = int(np.searchsorted(eval_dates, np.datetime64(date.to_datetime64(), "ns"), side="right")) - 1
        if idx < 0:
            return {"consensus_top8_count": float("nan"), "eval_date": ""}
        row = self.stage036_ai_monthly.iloc[idx]
        return {
            "consensus_top8_count": float(row.get("consensus_top8_count", np.nan)),
            "consensus_prob_mean": float(row.get("consensus_prob_mean", np.nan)),
            "eval_date": pd.Timestamp(row["eval_date"]).date().isoformat(),
        }

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage036_overheat_recovery_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            bar = plan.get("target_bar")
            bar_datetime = getattr(bar, "datetime", None)
            date_key = pd.Timestamp(bar_datetime).date().isoformat() if bar_datetime is not None else ""
            sizing = dict(plan.get("sizing") or {})
            account_state = self._stage036_account_state()
            selected_after, fields = _stage036_apply_overheat_recovery_gate(
                sizing=sizing,
                entry_context="flat_entry",
                regime_info=self.stage036_regime_by_date.get(date_key),
                account_state=account_state,
                ai_state=self._stage036_ai_state(date_key),
                min_position_size=int(getattr(self, "min_position_size", 1) or 1),
                enabled=bool(self.enable_stage036_overheat_recovery_gate),
                pilot_min_volume=int(self.stage036_pilot_min_volume),
            )
            fields["stage036_overheat_gate_ai_eval_date"] = str(self._stage036_ai_state(date_key).get("eval_date") or "")
            fields["stage036_overheat_gate_equity_history_count"] = int(
                account_state.get("stage036_equity_history_count", 0) or 0
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage036_overheat_gate_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage036_overheat_recovery_pilot_zero"

            event = self._stage036_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage036_overheat_gate_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage036_overheat_gate_count += 1
            self.stage036_overheat_gate_reduced_volume += int(fields["stage036_overheat_gate_reduced_volume"])
        return plans

    def _stage036_event_from_plan(
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
            "reason": "stage036_overheat_recovery_pilot_gate",
            "volume": int(fields["stage036_overheat_gate_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage036_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage036 overheat recovery pilot",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage036 isolated research candidate. "
            "Stage013 account pilot remains active; high-vol/high-efficiency, overheated, narrow-consensus flat "
            "entries are capped to a single-contract pilot, while deep-drawdown recovery states are protected."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": s013.PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": s013.PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": s013.PILOT_MIN_VOLUME,
        "enable_stage036_overheat_recovery_gate": True,
        "stage036_market_daily_path": str(s018.MARKET_DAILY_PATH),
        "stage036_pilot_min_volume": PILOT_MIN_VOLUME,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage036OverheatRecoveryPilot
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage036(
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
        profile = _stage036_profile(metadata)
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
        print(f"[stage036] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage036(metadata, start, REQUESTED_END)

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
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
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
    overheat_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage036_overheat_recovery_pilot_gate")].copy()
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
        "overheat_events": overheat_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s006.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_base_stage006", "_stage036"),
    )
    merged["stage036_vs_base_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage036"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage036"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage036_engine"
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"])
    return s009._run_audit(audit_curves)


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.74, label=str(start))
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.74, label=str(start))
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage036 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage036 Drawdown By Cold Start")
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
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    overheat_events: pd.DataFrame,
) -> dict[str, Any]:
    all_scope = aggregate[aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
    final_scope = aggregate[aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
    total_negative = int(pd.to_numeric(all_scope["negative_count"], errors="coerce").fillna(0).sum())
    min_strict = float(pd.to_numeric(all_scope["min_return_pct"], errors="coerce").min())
    final_negative = int(pd.to_numeric(final_scope["negative_count"], errors="coerce").fillna(0).sum())
    final_min = float(pd.to_numeric(final_scope["min_return_pct"], errors="coerce").min())
    retention_pass = int(pd.to_numeric(retention["passes_80pct_retention"], errors="coerce").fillna(0).sum())
    event_count = int(len(overheat_events))
    reduced_volume = (
        int(
            pd.to_numeric(
                overheat_events.get("stage036_overheat_gate_reduced_volume", pd.Series(dtype=float)),
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )
        if not overheat_events.empty
        else 0
    )
    return {
        "sample_count": int(summary["requested_start_month"].nunique()),
        "positive_start_count": int(pd.to_numeric(summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "min_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").min()),
        "median_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").median()),
        "max_total_return_pct": float(pd.to_numeric(summary["total_return_pct"], errors="coerce").max()),
        "worst_max_dd_pct": float(pd.to_numeric(summary["max_dd_pct"], errors="coerce").min()),
        "median_max_dd_pct": float(pd.to_numeric(summary["max_dd_pct"], errors="coerce").median()),
        "min_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").min()),
        "median_sharpe": float(pd.to_numeric(summary["sharpe"], errors="coerce").median()),
        "strict_negative_window_count": total_negative,
        "strict_min_return_pct": min_strict,
        "to_final_negative_window_count": final_negative,
        "to_final_min_return_pct": final_min,
        "retention_pass_count": retention_pass,
        "retention_rows": int(len(retention)),
        "overheat_event_count": event_count,
        "overheat_reduced_volume": reduced_volume,
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    overheat_events: pd.DataFrame,
) -> None:
    report = f"""# Stage036 过热抑制 + 恢复右尾保护真实引擎候选

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：独立研究 profile 真实引擎回测；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 趋势跟随资料强调保留右尾凸性和多市场/风险预算纪律，不支持粗暴切掉恢复期交易。
- GitHub/开源材料更多提供通用 backtest、position sizing、risk controls，没有可直接搬入本仓库的商品组合规则。
- Stage036 因此只做一个低自由度冻结规则：过热时 cap 到 `1` 手，深回撤或 63 日亏损的恢复右尾不处理。

## 固定规则

- 母本：Stage013 账户状态小风险试探真实引擎。
- 额外触发：`joint_regime={TARGET_REGIME}`、账户 `63d` 收益 `>{OVERHEAT_RETURN_63D_PCT}%`、AI consensus top8 count 在 `{CONSENSUS_MIN}-{CONSENSUS_MAX}`。
- 恢复保护：组合回撤 `>={RECOVERY_DRAWDOWN_PROTECT_PCT:.0%}` 或账户 `63d` 收益 `<= {RECOVERY_RETURN_63D_PROTECT_PCT}%` 时不触发。
- 动作：只把新的 `flat_entry` cap 到 `1` 手；不强平、不影响 rollover/add/reverse、不改 AI 池。

## 核心结果

- 正收益起点：`{decision['positive_start_count']}/{decision['sample_count']}`
- 期末收益 最小/中位/最大：`{decision['min_total_return_pct']:.4f}% / {decision['median_total_return_pct']:.4f}% / {decision['max_total_return_pct']:.4f}%`
- 最差最大回撤：`{decision['worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：`{decision['strict_negative_window_count']}`
- 严格最差收益：`{decision['strict_min_return_pct']:.4f}%`
- 到 `2026-06-30` 负窗口：`{decision['to_final_negative_window_count']}`；最差 `{decision['to_final_min_return_pct']:.4f}%`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- Stage036 过热事件：`{decision['overheat_event_count']}`；减少手数：`{decision['overheat_reduced_volume']}`

## 多起点摘要

{_md_table(summary)}

## 目标审计摘要

{_md_table(aggregate.head(40))}

## 收益保留

{_md_table(retention)}

## 过热事件样本

{_md_table(overheat_events.head(30))}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- summary: `{SUMMARY_PATH}`
- curves: `{CURVES_PATH}`
- overheat_events: `{OVERHEAT_EVENTS_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- performance_chart: `{PERFORMANCE_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage036_overheat_recovery_pilot_engine.md"
    content = f"""# Stage036 - 过热抑制 + 恢复右尾保护真实引擎候选

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Man Group trend-following market mix、Man AHL trend following drawdown/convexity 资料、Hurst/Ooi/Pedersen 长期趋势跟随证据、GitHub 上通用 systematic trading/risk-control 代码索引。
- 我的判断：趋势跟随的核心是右尾凸性，Stage036 不能重复 Stage024 hard gate；更合理的是过热时小风险试探，恢复右尾显式豁免。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage036_overheat_recovery_pilot_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage036_overheat_recovery_gate.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`OVERHEAT_RETURN_63D_PCT={OVERHEAT_RETURN_63D_PCT}`、`RECOVERY_DRAWDOWN_PROTECT_PCT={RECOVERY_DRAWDOWN_PROTECT_PCT}`、`RECOVERY_RETURN_63D_PROTECT_PCT={RECOVERY_RETURN_63D_PROTECT_PCT}`、`CONSENSUS_MIN={CONSENSUS_MIN}`、`CONSENSUS_MAX={CONSENSUS_MAX}`、`PILOT_MIN_VOLUME={PILOT_MIN_VOLUME}`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 起每半年冷启动，统一结束 `2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前重建 C9/15w 与 Stage013 真实引擎口径。
- 样本过滤：不按品种/方向/日期/source 过滤。
- 策略/归因口径：Stage013 母本 + Stage036 过热 cap 到 1 手；不连接 CTP、不调用订单 API。

## 结果

- 期末权益：见 summary 输出。
- 总收益：最小/中位/最大 `{decision['min_total_return_pct']:.4f}% / {decision['median_total_return_pct']:.4f}% / {decision['max_total_return_pct']:.4f}%`
- 最大回撤：最差 `{decision['worst_max_dd_pct']:.4f}%`
- Sharpe：最小/中位 `{decision['min_sharpe']:.4f} / {decision['median_sharpe']:.4f}`
- 总滑点：见 summary 输出。
- 总交易次数：见 summary 输出。
- 胜率：见 summary 输出。
- 其他关键指标：严格任意 `>1` 年负窗口 `{decision['strict_negative_window_count']}`，严格最差 `{decision['strict_min_return_pct']:.4f}%`，80% 收益保留 `{decision['retention_pass_count']}/{decision['retention_rows']}`，Stage036 事件 `{decision['overheat_event_count']}`，减少手数 `{decision['overheat_reduced_volume']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- orders：不适用。
- daily：`{CURVES_PATH}`
- quality：`{OVERHEAT_EVENTS_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：按决策与指标决定；若未达标，不允许扫相邻阈值救参。
- 下一步：若有改善但未达标，优先做失败归因；若收益保留失败，则停止该形状。

## 过拟合反思

- 运行前判断：否。规则来自 Stage035 的机制拆分，并做成低自由度单点；没有按品种、方向、月份、source 定制。
- 运行后判断：{decision['overfit_reflection_after']}
- 原因：本阶段没有根据结果调整阈值；后续如果改 `20%/30%/1-3/1手` 周边就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage035 已拆出过热回吐和恢复右尾，值得做一次真实引擎验真。
- 运行后判断：{decision['continue_value_after']}
- 原因：见核心指标和目标审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`。
"""
    record_path.write_text(content, encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    overheat_events = frames["overheat_events"]
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    regime_table = s018._stage018_build_causal_regime_table()
    ai_monthly = _stage036_ai_monthly_summary()
    _plot_performance(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    overheat_events.to_csv(OVERHEAT_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_monthly.to_csv(AI_MONTHLY_PATH, index=False, encoding="utf-8-sig")
    regime_table.to_csv(REGIME_TABLE_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, overheat_events)
    goal_pass = metrics["strict_negative_window_count"] == 0 and metrics["retention_pass_count"] == metrics["retention_rows"]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "audit_type": "stage013_plus_overheat_recovery_pilot_true_engine",
        "decision": "stage036_goal_pass_needs_review" if goal_pass else "stage036_goal_not_met_not_promoted",
        "strategy_changed": True,
        "official_live_config_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "target_regime": TARGET_REGIME,
        "overheat_return_63d_pct": OVERHEAT_RETURN_63D_PCT,
        "recovery_drawdown_protect_pct": RECOVERY_DRAWDOWN_PROTECT_PCT,
        "recovery_return_63d_protect_pct": RECOVERY_RETURN_63D_PROTECT_PCT,
        "consensus_min": CONSENSUS_MIN,
        "consensus_max": CONSENSUS_MAX,
        "pilot_min_volume": PILOT_MIN_VOLUME,
        **metrics,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": (
            "否。Stage036 是 Stage035 机制拆分后的冻结单点，不按品种/方向/月份/source 定制。"
        ),
        "continue_value_before": (
            "有。Stage035 已证明 high_vol_high_eff 内部有过热与恢复两类机制，必须用真实引擎验真。"
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
            "overheat_events": str(OVERHEAT_EVENTS_PATH),
            "ai_monthly": str(AI_MONTHLY_PATH),
            "causal_regime_table": str(REGIME_TABLE_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    if goal_pass:
        decision["overfit_reflection_after"] = "否，但仍需独立复核、成本敏感和右尾错杀审计，不能直接上线。"
        decision["continue_value_after"] = "有。目标口径通过时，下一步是独立复核和实盘 SOP 前置检查。"
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段没有根据结果改阈值；若继续扫 20%/30%/consensus/手数周边就是过拟合。"
        )
        decision["continue_value_after"] = (
            "有限。若未达标，应先做失败归因，而不是直接救参；若收益保留失败则停止该形状。"
        )

    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention, overheat_events)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
