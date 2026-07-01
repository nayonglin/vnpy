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
STAGE = "Stage013"
MODEL_TAG = "stage013_account_state_pilot_gate_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
PROFILE_NAME = "stage013_account_state_pilot_gate_engine"

PILOT_DRAWDOWN_TRIGGER_PCT = 0.30
PILOT_ACTIVE_POSITIONS_MAX = 1
PILOT_MIN_VOLUME = 1

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
PILOT_GATE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pilot_gate_events_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_cycle_retention_{MODEL_TAG}.csv"
ABSOLUTE_EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
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


def _normalize_drawdown_ratio(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(number):
        return 0.0
    number = abs(number)
    return number / 100.0 if number > 1.5 else number


def _stage013_apply_account_state_pilot_gate(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    active_positions_before: int,
    min_position_size: int,
    enabled: bool,
    drawdown_trigger_pct: float = PILOT_DRAWDOWN_TRIGGER_PCT,
    active_positions_max: int = PILOT_ACTIVE_POSITIONS_MAX,
    pilot_min_volume: int = PILOT_MIN_VOLUME,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    drawdown_ratio = _normalize_drawdown_ratio(sizing.get("portfolio_drawdown_pct", 0.0))
    trigger_ratio = _normalize_drawdown_ratio(drawdown_trigger_pct)
    active_before = max(0, int(active_positions_before or 0))
    min_size = max(0, int(min_position_size or 0))
    pilot_volume = max(0, int(pilot_min_volume or 0))

    reason = "not_evaluated"
    selected_after = selected_before
    applied = 0

    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif drawdown_ratio < trigger_ratio:
        reason = "drawdown_below_stage013_trigger"
    elif active_before > max(0, int(active_positions_max or 0)):
        reason = "active_positions_above_stage013_trigger"
    else:
        selected_after = min(selected_before, max(min_size, pilot_volume))
        if 0 < selected_after < min_size:
            selected_after = 0
        applied = int(selected_after != selected_before)
        reason = "stage013_deep_drawdown_low_active_flat_entry_pilot" if applied else "already_at_stage013_pilot_size"

    fields = {
        "stage013_pilot_gate_enabled": int(bool(enabled)),
        "stage013_pilot_gate_applied": applied,
        "stage013_pilot_gate_reason": reason,
        "stage013_pilot_gate_selected_volume_before": selected_before,
        "stage013_pilot_gate_selected_volume_after": selected_after,
        "stage013_pilot_gate_reduced_volume": selected_before - selected_after,
        "stage013_pilot_gate_drawdown_pct": drawdown_ratio,
        "stage013_pilot_gate_drawdown_trigger_pct": trigger_ratio,
        "stage013_pilot_gate_active_positions_before": active_before,
        "stage013_pilot_gate_active_positions_max": max(0, int(active_positions_max or 0)),
        "stage013_pilot_gate_pilot_min_volume": pilot_volume,
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage013AccountStatePilotGate(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage013_account_state_pilot_gate: bool = False
    stage013_pilot_drawdown_trigger_pct: float = PILOT_DRAWDOWN_TRIGGER_PCT
    stage013_pilot_active_positions_max: int = PILOT_ACTIVE_POSITIONS_MAX
    stage013_pilot_min_volume: int = PILOT_MIN_VOLUME

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage013_account_state_pilot_gate",
        "stage013_pilot_drawdown_trigger_pct",
        "stage013_pilot_active_positions_max",
        "stage013_pilot_min_volume",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage013_pilot_gate_count",
        "stage013_pilot_gate_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage013_pilot_gate_events: list[dict[str, Any]] = []
        self.stage013_pilot_gate_count: int = 0
        self.stage013_pilot_gate_reduced_volume: int = 0

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage013_account_state_pilot_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = dict(plan.get("sizing") or {})
            selected_after, fields = _stage013_apply_account_state_pilot_gate(
                sizing=sizing,
                entry_context="flat_entry",
                active_positions_before=int(plan.get("active_positions_before") or 0),
                min_position_size=int(getattr(self, "min_position_size", 1) or 1),
                enabled=bool(self.enable_stage013_account_state_pilot_gate),
                drawdown_trigger_pct=float(self.stage013_pilot_drawdown_trigger_pct),
                active_positions_max=int(self.stage013_pilot_active_positions_max),
                pilot_min_volume=int(self.stage013_pilot_min_volume),
            )
            sizing.update(fields)
            if int(fields["stage013_pilot_gate_applied"]) != 1:
                plan["sizing"] = sizing
                continue

            sizing["selected_volume"] = selected_after
            plan["sizing"] = sizing
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage013_account_state_pilot_gate_zero"

            event = self._stage013_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage013_pilot_gate_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage013_pilot_gate_count += 1
            self.stage013_pilot_gate_reduced_volume += int(fields["stage013_pilot_gate_reduced_volume"])
        return plans

    def _stage013_event_from_plan(
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
            "reason": "stage013_account_state_pilot_gate",
            "volume": int(fields["stage013_pilot_gate_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage013_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage013 account-state pilot gate",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage013 isolated research candidate. "
            "When account drawdown is deep and active positions are low, flat-entry sizing is reduced to a "
            "single-contract pilot; no product/date/direction blacklist and no official live config mutation."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": PILOT_MIN_VOLUME,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage013AccountStatePilotGate
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s847.s827.s778.s653.s517.START_DT
    original_end = s847.s827.s778.s653.s517.END_DT
    original_preload = s847.s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s847.s827.s778.s653.s517.START_DT = s847.START.to_pydatetime()
        s847.s827.s778.s653.s517.END_DT = s847.END.to_pydatetime()
        s847.s827.s778.s653.s517.PRELOAD_START_DT = s847.s827.s772._preload_for_start(
            s847.START
        ).to_pydatetime()

        s847.s827.s778.s653.s517.assert_stage196_database_sentinels()
        s847.s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s847.s827.s778.s653.s517.PRELOAD_START_DT,
            s847.s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s847.s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s847.Stage847StopRetryEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s847.s827.Interval.DAILY,
            start=preload_start,
            end=s847.s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s847.s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s847.s513._c3_overrides(s847.START.to_pydatetime())),
            start=s847.START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            daily_df = pd.DataFrame(
                [
                    {
                        "net_pnl": 0.0,
                        "trade_count": 0.0,
                        "slippage": 0.0,
                        "commission": 0.0,
                        "turnover": 0.0,
                    }
                ],
                index=pd.Index([s847.END.date()], name="date"),
            )

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= s847.START.date()) & (daily.index <= s847.END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s847.s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s847.s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=[
                    "variant",
                    "combo_variant",
                    "date",
                    "c3_margin_exact",
                    "c3_active_contracts",
                    "c3_active_products",
                ]
            )
        combined = s847.s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        pilot_gate_events = pd.DataFrame(getattr(strategy, "stage013_pilot_gate_events", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s847.s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s847.s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s847.s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "pilot_gate_events": pilot_gate_events,
            "pending_orders": s847._active_limit_orders_frame(engine),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = s847.START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s847.s827.s778.s653.s517.START_DT = original_start
        s847.s827.s778.s653.s517.END_DT = original_end
        s847.s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _run_live_stage013(
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
        profile = _stage013_profile(metadata)
        combined, frames = _run_profile(profile, metadata)
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


def _append_frame(target: list[pd.DataFrame], frame: pd.DataFrame, start: pd.Timestamp) -> None:
    frame = _frame_with_run_columns(frame, start)
    if not frame.empty:
        target.append(frame)


def _run_multistart() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = s167._build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    intraday_event_frames: list[pd.DataFrame] = []
    pilot_gate_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage013] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage013(metadata, start, REQUESTED_END)

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
        _append_frame(intraday_event_frames, frames.get("intraday_events", pd.DataFrame()), start)
        _append_frame(pilot_gate_event_frames, frames.get("pilot_gate_events", pd.DataFrame()), start)

    summary = pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True)
    return {
        "summary": summary,
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "entry_risk": pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        "trade_events": pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame(),
        "intraday_events": (
            pd.concat(intraday_event_frames, ignore_index=True, sort=False) if intraday_event_frames else pd.DataFrame()
        ),
        "pilot_gate_events": (
            pd.concat(pilot_gate_event_frames, ignore_index=True, sort=False)
            if pilot_gate_event_frames
            else pd.DataFrame()
        ),
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s006.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_base_stage006", "_stage013"),
    )
    merged["stage013_vs_base_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage013_engine"
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
    axes[0].set_title("Stage013 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage013 Drawdown By Cold Start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    fig.savefig(ABSOLUTE_EQUITY_CHART_PATH, dpi=160)
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


def _stage013_metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    pilot_events: pd.DataFrame,
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
        "retention_80pct_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "pilot_gate_event_count": int(len(pilot_events)),
        "pilot_gate_reduced_volume_sum": (
            int(pd.to_numeric(pilot_events.get("stage013_pilot_gate_reduced_volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
            if not pilot_events.empty
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
    pilot_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 账户状态小风险试探真实引擎候选",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 候选 profile：`{PROFILE_NAME}`",
        f"- 线上母本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 回测区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`；起点为每年 `01-01/07-01`。",
        "- 阶段性质：独立研究线真实引擎候选；不连接 CTP、不调用下单 API、不修改官方 live config。",
        "",
        "## 外部调研判断",
        "",
        "- CFM/PBO 资料提示：本阶段只冻结一个账户状态规则，不扫阈值、不按结果回填品种/日期，降低样本内过拟合风险。",
        "- CTA/趋势跟随仓位资料提示：仓位控制可以依赖波动和账户状态，但必须避免切断右尾；所以本候选只在深回撤且低活跃的新开仓上降到试探手数。",
        "- 采纳：账户状态低自由度风控；否决：按 `SM`、`2022-07`、方向或单起点黑名单化。",
        "",
        "## 参数",
        "",
        f"- `stage013_pilot_drawdown_trigger_pct`: `{PILOT_DRAWDOWN_TRIGGER_PCT}`",
        f"- `stage013_pilot_active_positions_max`: `{PILOT_ACTIVE_POSITIONS_MAX}`",
        f"- `stage013_pilot_min_volume`: `{PILOT_MIN_VOLUME}`",
        "",
        "## 多起点摘要",
        "",
        _md_table(
            summary[
                [
                    "requested_start_month",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "total_trade_count",
                    "max_broker10_margin_to_equity_pct",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 密集目标审计",
        "",
        _md_table(aggregate, max_rows=40),
        "",
        "## 全周期收益保留",
        "",
        _md_table(retention, max_rows=30),
        "",
        "## AI 月度审计",
        "",
        _md_table(ai_month_audit["status"].value_counts().rename_axis("status").reset_index(name="count"), max_rows=10)
        if "status" in ai_month_audit.columns
        else "",
        "",
        "## Stage013 触发事件",
        "",
        _md_table(
            pilot_events[
                [
                    "requested_start_month",
                    "date",
                    "product_vt_symbol",
                    "direction",
                    "stage013_pilot_gate_selected_volume_before",
                    "stage013_pilot_gate_selected_volume_after",
                    "stage013_pilot_gate_drawdown_pct",
                    "stage013_pilot_gate_active_positions_before",
                ]
            ].head(40)
            if not pilot_events.empty
            else pilot_events,
            max_rows=40,
        ),
        "",
        "## 最差窗口",
        "",
        _md_table(worst.head(40), max_rows=40),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> Path:
    stage_dir = LINE_DIR / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    record_path = stage_dir / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage013_account_state_pilot_gate_engine.md"
    metrics = decision["metrics"]
    lines = [
        "# Stage013 账户状态小风险试探真实引擎候选",
        "",
        f"- 记录时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        "- 新增参数：`enable_stage013_account_state_pilot_gate=True`、"
        f"`stage013_pilot_drawdown_trigger_pct={PILOT_DRAWDOWN_TRIGGER_PCT}`、"
        f"`stage013_pilot_active_positions_max={PILOT_ACTIVE_POSITIONS_MAX}`、"
        f"`stage013_pilot_min_volume={PILOT_MIN_VOLUME}`。",
        "- 修改参数：无，官方线上 C9/15w 配置未改；本阶段只在独立研究 profile 内覆盖。",
        "- 删除参数：无。",
        "- 规则：深回撤且有效空仓/低活跃状态下，`flat_entry` 新开仓先降到 1 手试探；不按品种、日期、方向黑名单。",
        "",
        "## 回测参数",
        "",
        f"- 起点：`2018-01-01` 起每半年一个独立冷启动，共 `{metrics['sample_count']}` 个。",
        f"- 终点：`{REQUESTED_END.date()}`。",
        f"- 资金：`{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        "",
        "## 回测结果",
        "",
        f"- 正收益起点：`{metrics['positive_count']}/{metrics['sample_count']}`。",
        f"- 期末权益最小/中位/最大：`{summary['end_equity'].min():,.2f}` / "
        f"`{summary['end_equity'].median():,.2f}` / `{summary['end_equity'].max():,.2f}`。",
        f"- 总收益最小/中位/最大：`{metrics['min_return_pct']:.4f}%` / "
        f"`{metrics['median_return_pct']:.4f}%` / `{metrics['max_return_pct']:.4f}%`。",
        f"- 最大回撤最差/中位：`{metrics['worst_max_dd_pct']:.4f}%` / `{metrics['median_max_dd_pct']:.4f}%`。",
        f"- Sharpe 最小/中位/最大：`{summary['sharpe'].min():.4f}` / "
        f"`{summary['sharpe'].median():.4f}` / `{summary['sharpe'].max():.4f}`。",
        f"- 总滑点：`{summary['total_slippage'].sum():,.2f}`。",
        f"- 总交易次数：`{summary['total_trade_count'].sum():,.0f}`。",
        f"- 胜率中位：`{summary['nonzero_daily_win_rate_pct'].median():.4f}%`。",
        f"- Stage013 触发次数：`{metrics['pilot_gate_event_count']}`；累计减少手数："
        f"`{metrics['pilot_gate_reduced_volume_sum']}`。",
        f"- 密集任意结束日 `>1` 年负窗口：`{metrics['all_gt1y_negative_count']}` / "
        f"`{metrics['all_gt1y_window_count']}`，最差 `{metrics['all_gt1y_min_return_pct']:.4f}%`。",
        f"- 到 `{REQUESTED_END.date()}` 负窗口：`{metrics['to_final_negative_count']}` / "
        f"`{metrics['to_final_window_count']}`，最差 `{metrics['to_final_min_return_pct']:.4f}%`。",
        f"- 全周期 `80%` 收益保留：`{metrics['retention_80pct_pass_count']}/{metrics['retention_rows']}`。",
        f"- AI 月度审计 FAIL：`{metrics['ai_post_first_fail_count']}`。",
        "",
        "## 文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    lines.extend(
        [
            "",
            "## 后续规划和 TODO",
            "",
            "- 若仍未满足严格任意结束日目标，停止把深回撤小风险试探当作已解决方案；继续归因它实际触发在哪些账户状态和是否错过右尾。",
            "- 鸡蛋仍需单独补 full-universe monthly AI 分数或非挤占候选，不能直接塞入共享 AI topN。",
            "- 后续若写确认后风险释放，必须继续用真实引擎验证，不用代理曲线替代。",
            "",
            "## 反思",
            "",
            f"- 过拟合反思：{decision['overfit_reflection_after']}",
            f"- 继续价值反思：{decision['continue_value_after']}",
            "",
        ]
    )
    record_path.write_text("\n".join(lines), encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    candidates = frames["entry_candidates"]
    pilot_events = frames["pilot_gate_events"]

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
    frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pilot_events.to_csv(PILOT_GATE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_pool_audit.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _stage013_metrics(summary, aggregate, retention, pilot_events, ai_month_audit)
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
        "stage013_parameters": {
            "drawdown_trigger_pct": PILOT_DRAWDOWN_TRIGGER_PCT,
            "active_positions_max": PILOT_ACTIVE_POSITIONS_MAX,
            "pilot_min_volume": PILOT_MIN_VOLUME,
        },
        "ai_pool_audit": ai_pool_meta,
        "metrics": metrics,
        "decision": (
            "stage013_strict_goal_pass_research_candidate_needs_review"
            if strict_goal_pass
            else "stage013_goal_not_met_keep_research_candidate_for_attribution"
        ),
        "strategy_changed": True,
        "official_live_strategy_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "CFM/PBO and CTA sizing references support low-degree account-state sizing controls, "
            "but not parameter sweeps or product/date blacklists. Stage013 freezes one rule for true-engine testing."
        ),
        "overfit_reflection_before": (
            "否。本阶段预先冻结账户状态闸门，不按 Stage009 最差具体日期、品种或方向做黑名单，也不扫触发阈值。"
        ),
        "continue_value_before": (
            "是。Stage012 显示坏窗口高质量标签也失效，必须把账户状态纳入真实引擎验证。"
        ),
        "overfit_reflection_after": (
            "否，但风险上升。本阶段仍是单规则冻结验证；如果继续把阈值、品种或日期调到刚好修复 2022-07 窗口，就会过拟合。"
        ),
        "continue_value_after": (
            "是。无论是否达标，真实引擎触发事件和密集窗口审计可以判断账户状态风控是否有方向价值；但不能直接上线。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "pilot_gate_events": str(PILOT_GATE_EVENTS_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "ai_pool_audit": str(AI_POOL_AUDIT_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    _write_report(decision, summary, aggregate, worst, retention, pilot_events, ai_month_audit)
    decision["outputs"]["stage_record"] = str(_write_stage_record(decision, summary))
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(
        summary[
            [
                "requested_start_month",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "total_trade_count",
            ]
        ].to_string(index=False)
    )
    print("goal_aggregate")
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
