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
import stage055_new_entry_signal_budget_audit as s055
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage066"
MODEL_TAG = "stage066_breakeven_after_1r_true_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage066_breakeven_after_1r_true_engine"
PROFILE_NAME = "stage066_breakeven_after_1r_true_engine"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0
BREAKEVEN_TRIGGER_R = 1.0

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage066_breakeven_after_1r_true_engine"
STAGE_RECORD_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
BREAKEVEN_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_breakeven_events_{MODEL_TAG}.csv"
PRESSURE_STARTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_starts_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

BASE_VARIANT = "stage013_pressure_baseline"
CANDIDATE_VARIANT = "stage066_breakeven_after_1r"

EXTERNAL_RESEARCH_SOURCES = [
    "Backtrader stop order docs: https://www.backtrader.com/docu/order/",
    "Backtrader stop-loss examples: https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
    "NautilusTrader backtesting event cycle: https://nautilustrader.io/docs/latest/concepts/backtesting/",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "Stop and breakeven exits must be modeled with explicit event ordering. Stage066 therefore converts the Stage065 "
    "closed-lot upper bound into a conservative daily true-engine stop update: after a layer reaches +1R, move that "
    "layer stop to breakeven; if the same daily bar both reaches +1R and retraces to entry, defer the stop to the next "
    "bar instead of assuming favorable intrabar order."
)


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _is_stop_at_or_beyond_breakeven(*, direction: str, entry_price: float, current_stop_price: float) -> bool:
    if direction == "long":
        return current_stop_price >= entry_price
    if direction == "short":
        return current_stop_price <= entry_price
    return False


def _stage066_evaluate_breakeven_update(
    *,
    direction: str,
    entry_price: float,
    original_stop_price: float,
    current_stop_price: float,
    high_price: float,
    low_price: float,
    trigger_r: float,
    already_armed: bool,
    pending_apply: bool,
) -> dict[str, Any]:
    direction = str(direction or "").lower()
    values = [entry_price, original_stop_price, current_stop_price, high_price, low_price, trigger_r]
    if direction not in {"long", "short"} or any(not np.isfinite(float(value)) for value in values):
        return {
            "armed": bool(already_armed),
            "apply_now": False,
            "pending_apply": bool(pending_apply),
            "new_stop_price": current_stop_price,
            "reason": "invalid_input",
        }

    entry = float(entry_price)
    original_stop = float(original_stop_price)
    current_stop = float(current_stop_price)
    risk = abs(entry - original_stop)
    if risk <= 0.0 or float(trigger_r) <= 0.0:
        return {
            "armed": bool(already_armed),
            "apply_now": False,
            "pending_apply": bool(pending_apply),
            "new_stop_price": current_stop,
            "reason": "invalid_risk",
        }

    if _is_stop_at_or_beyond_breakeven(direction=direction, entry_price=entry, current_stop_price=current_stop):
        return {
            "armed": bool(already_armed),
            "apply_now": False,
            "pending_apply": False,
            "new_stop_price": current_stop,
            "reason": "stop_already_at_or_beyond_breakeven",
        }

    if pending_apply:
        return {
            "armed": True,
            "apply_now": True,
            "pending_apply": False,
            "new_stop_price": entry,
            "reason": "stage066_pending_breakeven_applied",
        }

    if already_armed:
        return {
            "armed": True,
            "apply_now": False,
            "pending_apply": False,
            "new_stop_price": current_stop,
            "reason": "already_armed",
        }

    if direction == "long":
        activation_price = entry + float(trigger_r) * risk
        activation_hit = float(high_price) >= activation_price
        same_bar_retrace = float(low_price) <= entry
    else:
        activation_price = entry - float(trigger_r) * risk
        activation_hit = float(low_price) <= activation_price
        same_bar_retrace = float(high_price) >= entry

    if not activation_hit:
        return {
            "armed": False,
            "apply_now": False,
            "pending_apply": False,
            "new_stop_price": current_stop,
            "reason": "activation_not_reached",
        }

    if same_bar_retrace:
        return {
            "armed": True,
            "apply_now": False,
            "pending_apply": True,
            "new_stop_price": current_stop,
            "reason": "stage066_same_bar_activation_retrace_deferred",
        }

    return {
        "armed": True,
        "apply_now": True,
        "pending_apply": False,
        "new_stop_price": entry,
        "reason": "stage066_breakeven_armed_and_applied",
    }


class QmtRollPortfolioStrategyStage066BreakevenAfter1R(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage066_breakeven_after_1r: bool = False
    stage066_breakeven_trigger_r: float = BREAKEVEN_TRIGGER_R

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage066_breakeven_after_1r",
        "stage066_breakeven_trigger_r",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage066_breakeven_stop_update_count",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage066_breakeven_events: list[dict[str, Any]] = []
        self.stage066_breakeven_stop_update_count: int = 0

    def _update_dynamic_stops(self, state: Any, bar: Any, history: pd.DataFrame) -> None:
        if self.enable_stage066_breakeven_after_1r:
            for layer in state.layers:
                if not hasattr(layer, "stage066_original_stop_price"):
                    setattr(layer, "stage066_original_stop_price", float(layer.stop_price))
                    setattr(layer, "stage066_breakeven_armed", False)
                    setattr(layer, "stage066_breakeven_pending_apply", False)
        super()._update_dynamic_stops(state, bar, history)
        if self.enable_stage066_breakeven_after_1r:
            self._stage066_apply_breakeven_updates(state, bar)

    def _stage066_apply_breakeven_updates(self, state: Any, bar: Any) -> None:
        for index, layer in enumerate(list(state.layers)):
            original_stop = float(getattr(layer, "stage066_original_stop_price", layer.stop_price))
            already_armed = bool(getattr(layer, "stage066_breakeven_armed", False))
            pending_apply = bool(getattr(layer, "stage066_breakeven_pending_apply", False))
            result = _stage066_evaluate_breakeven_update(
                direction=str(layer.direction),
                entry_price=float(layer.entry_price),
                original_stop_price=original_stop,
                current_stop_price=float(layer.stop_price),
                high_price=float(bar.high_price),
                low_price=float(bar.low_price),
                trigger_r=float(self.stage066_breakeven_trigger_r),
                already_armed=already_armed,
                pending_apply=pending_apply,
            )
            setattr(layer, "stage066_breakeven_armed", bool(result["armed"]))
            setattr(layer, "stage066_breakeven_pending_apply", bool(result["pending_apply"]))
            previous_stop = float(layer.stop_price)
            if bool(result["apply_now"]):
                layer.stop_price = float(result["new_stop_price"])
                self.stage066_breakeven_stop_update_count += 1
            if str(result["reason"]).startswith("stage066_"):
                event = self._stage066_event_from_layer(state, bar, layer, index, result, original_stop, previous_stop)
                self.stage066_breakeven_events.append(event)
                self.trade_event_diagnostics.append(event)

    def _stage066_event_from_layer(
        self,
        state: Any,
        bar: Any,
        layer: Any,
        layer_index: int,
        result: dict[str, Any],
        original_stop: float,
        previous_stop: float,
    ) -> dict[str, Any]:
        return {
            "datetime": getattr(bar, "datetime", None),
            "date": pd.Timestamp(getattr(bar, "datetime", None)).date() if getattr(bar, "datetime", None) else "",
            "vt_symbol": str(state.contract_vt_symbol or ""),
            "contract_vt_symbol": str(state.contract_vt_symbol or ""),
            "product_vt_symbol": str(state.product_vt_symbol or ""),
            "position_direction": str(layer.direction),
            "direction": str(layer.direction),
            "offset": "StopUpdate",
            "reason": str(result["reason"]),
            "volume": int(layer.volume),
            "price": float(result["new_stop_price"]),
            "entry_context": str(layer.kind),
            "signal": str(layer.signal),
            "stage066_layer_index": int(layer_index),
            "stage066_entry_price": float(layer.entry_price),
            "stage066_original_stop_price": float(original_stop),
            "stage066_previous_stop_price": float(previous_stop),
            "stage066_new_stop_price": float(result["new_stop_price"]),
            "stage066_trigger_r": float(self.stage066_breakeven_trigger_r),
            "stage066_apply_now": int(bool(result["apply_now"])),
            "stage066_pending_apply": int(bool(result["pending_apply"])),
            "stage066_armed": int(bool(result["armed"])),
            "stage066_high_price": float(bar.high_price),
            "stage066_low_price": float(bar.low_price),
        }


def _stage066_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage066 breakeven after 1R",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage066 isolated research candidate. Stage013 account pilot remains active; "
            "after a layer reaches +1R, its stop is raised to breakeven with same-bar activation/retrace deferred."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": s013.PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": s013.PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": s013.PILOT_MIN_VOLUME,
        "enable_stage066_breakeven_after_1r": True,
        "stage066_breakeven_trigger_r": BREAKEVEN_TRIGGER_R,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage066BreakevenAfter1R
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage066(
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
        profile = _stage066_profile(metadata)
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


def _load_pressure_starts() -> pd.DataFrame:
    if s055.SELECTED_WINDOWS_PATH.exists():
        windows = pd.read_csv(s055.SELECTED_WINDOWS_PATH, encoding="utf-8-sig")
    else:
        selected = pd.read_csv(s055.STAGE054_SELECTED_WINDOWS_PATH, encoding="utf-8-sig")
        windows = s055.unique_stage054_windows(selected)
    starts = windows[["requested_start"]].copy()
    starts["requested_start"] = pd.to_datetime(starts["requested_start"], errors="coerce").dt.normalize()
    starts = starts.dropna(subset=["requested_start"]).drop_duplicates().sort_values("requested_start")
    starts["requested_end"] = REQUESTED_END
    starts["run_scope"] = "stage054_unique_left_tail_pressure_starts"
    starts["stage066_pressure_rank"] = np.arange(1, len(starts) + 1)
    return starts.reset_index(drop=True)


def _frame_with_run_columns(frame: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
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
    curve["official_live_version"] = OFFICIAL_LIVE_VERSION
    curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    curve["requested_start"] = _date_text(start)
    curve["requested_start_month"] = _date_text(start)
    curve["requested_end"] = _date_text(REQUESTED_END)
    curve["variant"] = variant_label
    curve["ab_variant"] = variant_label
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
    curve["drawdown_pct"] = s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
    curve["days_since_start"] = np.arange(len(curve), dtype=int)
    return curve


def _summarize_curve(curve: pd.DataFrame, *, start: pd.Timestamp, variant_label: str) -> dict[str, Any]:
    row = s167._summarize_curve(curve, start)
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
            "official_live_profile_name": PROFILE_NAME if variant_label == CANDIDATE_VARIANT else s013.PROFILE_NAME,
        }
    )
    return row


def _run_pressure_ab() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = _load_pressure_starts()
    if starts.empty:
        raise RuntimeError("Stage066 pressure starts are empty; run Stage054/055 first.")

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for index, row in enumerate(starts.itertuples(index=False), start=1):
        start = pd.Timestamp(row.requested_start).normalize()
        print(f"[stage066] A Stage013 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        base_combined, base_frames, _base_spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _curve_for_variant(base_combined, start=start, variant_label=BASE_VARIANT)
        curve_frames.append(base_curve)
        summary_rows.append(_summarize_curve(base_curve, start=start, variant_label=BASE_VARIANT))
        _append_frame(candidate_frames, base_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_frames, base_frames.get("trades", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(entry_risk_frames, base_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_event_frames, base_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)

        print(f"[stage066] C Stage066 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        candidate_combined, candidate_frames_map, _candidate_spec = _run_live_stage066(metadata, start, REQUESTED_END)
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
        "pressure_starts": starts,
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
    wide["stage066_vs_stage013_return_ratio"] = (
        pd.to_numeric(wide[CANDIDATE_VARIANT], errors="coerce")
        / pd.to_numeric(wide[BASE_VARIANT], errors="coerce").replace(0.0, np.nan)
    )
    wide["passes_80pct_retention"] = (
        pd.to_numeric(wide[CANDIDATE_VARIANT], errors="coerce")
        >= pd.to_numeric(wide[BASE_VARIANT], errors="coerce") * 0.8
    ).astype("int64")
    return wide.rename(
        columns={
            BASE_VARIANT: "stage013_total_return_pct",
            CANDIDATE_VARIANT: "stage066_total_return_pct",
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


def _metrics(summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame, breakeven_events: pd.DataFrame) -> dict[str, Any]:
    candidate_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)]
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)]
    strict_scope = "all_trading_end_dates_gt_1y"
    final_scope = "start_to_2026_06_30_only"
    return {
        "pressure_start_count": int(candidate_summary["requested_start_month"].nunique()),
        "stage013_positive_start_count": int(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "stage066_positive_start_count": int(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "stage013_min_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").min()),
        "stage066_min_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").min()),
        "stage013_median_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").median()),
        "stage066_median_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").median()),
        "stage013_worst_max_dd_pct": float(pd.to_numeric(base_summary["max_dd_pct"], errors="coerce").min()),
        "stage066_worst_max_dd_pct": float(pd.to_numeric(candidate_summary["max_dd_pct"], errors="coerce").min()),
        "stage013_median_sharpe": float(pd.to_numeric(base_summary["sharpe"], errors="coerce").median()),
        "stage066_median_sharpe": float(pd.to_numeric(candidate_summary["sharpe"], errors="coerce").median()),
        "stage013_strict_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "negative_count", 0.0)),
        "stage066_strict_negative_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "negative_count", 0.0)),
        "stage013_strict_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage066_strict_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage013_strict_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, strict_scope, "min_return_pct"),
        "stage066_strict_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "min_return_pct"),
        "stage013_to_final_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, final_scope, "negative_count", 0.0)),
        "stage066_to_final_negative_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "negative_count", 0.0)),
        "stage013_to_final_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, final_scope, "min_return_pct"),
        "stage066_to_final_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "min_return_pct"),
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
    }


def _stage066_decision_from_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    improves_left_tail = (
        int(metrics.get("stage066_strict_negative_window_count", 0))
        < int(metrics.get("stage013_strict_negative_window_count", 0))
        and float(metrics.get("stage066_strict_min_return_pct", np.nan))
        > float(metrics.get("stage013_strict_min_return_pct", np.nan))
    )
    retention_rows = int(metrics.get("retention_rows", 0) or 0)
    retention_ok = retention_rows > 0 and int(metrics.get("retention_pass_count", 0) or 0) == retention_rows
    pressure_goal_pass = int(metrics.get("stage066_strict_negative_window_count", 0) or 0) == 0 and retention_ok
    if pressure_goal_pass:
        return {
            "decision": "stage066_pressure_goal_pass_expand_validation",
            "next_step": "扩到更密日级/逐半年多周期，并做交易明细、AI 月度应用和成本压力审计。",
            "improves_left_tail": True,
            "retention_ok": bool(retention_ok),
            "pressure_goal_pass": True,
            "overfit_reflection_after": "否，但仍需外推验证。压力集通过只能说明候选值得扩样本，不能直接上线。",
            "continue_value_after": "有。压力左尾清零且收益保留通过，值得进入全量验证。",
        }
    if improves_left_tail and retention_ok:
        return {
            "decision": "stage066_pressure_improves_left_tail_expand_validation",
            "next_step": "扩到 Stage042/053 级别更多压力起点，再决定是否做全量日级密集回测。",
            "improves_left_tail": True,
            "retention_ok": bool(retention_ok),
            "pressure_goal_pass": False,
            "overfit_reflection_after": "暂不判定过拟合。规则未改参且压力集改善，但还没有跨样本证明。",
            "continue_value_after": "有。压力左尾改善且收益保留过关，值得扩样本验证。",
        }
    return {
        "decision": "stage066_pressure_not_enough_stop_no_param_rescue",
        "next_step": "停止扫保本/锁盈阈值；回到失败归因，或转更强 PIT 信息源和账户外层。",
        "improves_left_tail": False,
        "retention_ok": bool(retention_ok),
        "pressure_goal_pass": False,
        "overfit_reflection_after": "否。本阶段没有救参；如果继续调 R 倍数、锁盈档位、品种或年份就是过拟合。",
        "continue_value_after": "有限。若压力集不改善或右尾损失过大，该保本形状不应继续交易化。",
    }


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    color_map = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#dc2626"}
    for (variant, start), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        group = group.sort_values("date")
        label = f"{variant} {start}"
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.72, color=color_map.get(variant), label=label)
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.72, color=color_map.get(variant), label=label)
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage066 Pressure Starts Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage066 Pressure Starts Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=6, ncol=3, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal_audit(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    colors = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#dc2626"}
    for ax, scope_name, title in [
        (axes[0, 0], "all_trading_end_dates_gt_1y", "Negative Rate: All Trading End Dates > 1Y"),
        (axes[0, 1], "start_to_2026_06_30_only", "Negative Rate: Start To 2026-06-30"),
    ]:
        scope = aggregate[aggregate["audit_scope"].eq(scope_name)].copy()
        scope["label"] = scope["variant"].astype(str) + "\n" + scope["source_start_month"].astype(str)
        x = np.arange(len(scope))
        ax.bar(x, scope["negative_rate_pct"], color=[colors.get(v, "#94a3b8") for v in scope["variant"]])
        ax.set_xticks(x[::2])
        ax.set_xticklabels(scope["label"].iloc[::2], rotation=55, ha="right", fontsize=7)
        ax.set_title(title)
        ax.set_ylabel("negative rate %")
        ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not worst.empty:
        plot = worst.head(120).copy()
        ax.scatter(np.arange(len(plot)), plot["return_pct"], s=12, c=[colors.get(v, "#94a3b8") for v in plot["variant"]])
    ax.axhline(0, color="#111827", linewidth=0.9, linestyle="--")
    ax.set_title("Worst Negative Windows")
    ax.set_ylabel("return %")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    if not fixed.empty:
        fixed_summary = (
            fixed.groupby(["variant", "horizon_days"], as_index=False)
            .agg(negative_rate_pct=("positive_return", lambda s: float((1.0 - s.mean()) * 100.0)))
            .sort_values(["horizon_days", "variant"])
        )
        for variant, group in fixed_summary.groupby("variant"):
            ax.plot(group["horizon_days"], group["negative_rate_pct"], marker="o", label=str(variant), color=colors.get(variant))
    ax.set_title("Fixed Horizon Negative Rate")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("negative rate %")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    breakeven_events: pd.DataFrame,
) -> None:
    report = f"""# Stage066 保本退出真引擎压力验证

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：独立研究 profile 真实引擎 A/C 压力起点验证；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 参考：{'; '.join(EXTERNAL_RESEARCH_SOURCES)}
- 我的判断：保本退出必须显式处理事件顺序；Stage066 用保守日级语义验真 Stage065 的 closed-lot 上界。

## A/C 口径

- A：`{BASE_VARIANT}`，Stage013 账户状态小风险试探母本。
- C：`{CANDIDATE_VARIANT}`，Stage013 + layer 到达 `+{BREAKEVEN_TRIGGER_R:g}R` 后 stop 抬到入场价；同日同时触发 `+1R` 与回踩入场价则延迟到下一根日 K。
- 样本：Stage054/055 去重后的 `{decision['pressure_start_count']}` 个左尾压力日级起点，结束日统一 `2026-06-30`。

## 核心结果

- Stage013 正收益起点：`{decision['stage013_positive_start_count']}/{decision['pressure_start_count']}`；Stage066：`{decision['stage066_positive_start_count']}/{decision['pressure_start_count']}`
- 期末收益最小：Stage013 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage066 `{decision['stage066_min_total_return_pct']:.4f}%`
- 最差最大回撤：Stage013 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage066 `{decision['stage066_worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：Stage013 `{decision['stage013_strict_negative_window_count']}` / `{decision['stage013_strict_window_count']}`；Stage066 `{decision['stage066_strict_negative_window_count']}` / `{decision['stage066_strict_window_count']}`
- 严格最差收益：Stage013 `{decision['stage013_strict_min_return_pct']:.4f}%`；Stage066 `{decision['stage066_strict_min_return_pct']:.4f}%`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- Stage066 breakeven events：`{decision['breakeven_event_count']}`；apply events：`{decision['breakeven_applied_event_count']}`；pending events：`{decision['breakeven_pending_event_count']}`

## 多起点摘要

{_md_table(summary)}

## 目标审计摘要

{_md_table(aggregate.head(60))}

## 收益保留

{_md_table(retention)}

## 保本事件样本

{_md_table(breakeven_events.head(60))}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage066_breakeven_after_1r_true_engine.md"
    content = f"""# Stage066 - 保本退出真引擎压力验证

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选 A/C 压力验证，不改官方实盘配置。
- 是否重要突破：`{'是' if decision['decision'].endswith('expand_validation') else '否'}`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：Backtrader stop order/stop-loss examples、NautilusTrader event cycle、pysystemtrade。
- 我的判断：保本退出必须显式事件顺序；本阶段只验真 Stage065 `optimistic_breakeven_after_1r`，不扫 R 倍数或锁盈档位。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage066_breakeven_after_1r_true_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage066_breakeven_engine.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`BREAKEVEN_TRIGGER_R={BREAKEVEN_TRIGGER_R}`、`enable_stage066_breakeven_after_1r=True`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`{BASE_VARIANT}`，Stage013。
- C：`{CANDIDATE_VARIANT}`，Stage013 + `+1R` 后保本 stop。
- 样本：Stage054/055 去重左尾压力日级起点 `{decision['pressure_start_count']}` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。
- 事件顺序：同日同时触发 `+1R` 与回踩入场价时，不假设有利先后，保本 stop 延迟到下一根日 K。

## 结果

- 总收益：Stage013 最小 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage066 最小 `{decision['stage066_min_total_return_pct']:.4f}%`
- 最大回撤：Stage013 最差 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage066 最差 `{decision['stage066_worst_max_dd_pct']:.4f}%`
- Sharpe：Stage013 中位 `{decision['stage013_median_sharpe']:.4f}`；Stage066 中位 `{decision['stage066_median_sharpe']:.4f}`
- 严格负窗口：Stage013 `{decision['stage013_strict_negative_window_count']}`；Stage066 `{decision['stage066_strict_negative_window_count']}`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- 保本事件：`{decision['breakeven_event_count']}`；实际应用 `{decision['breakeven_applied_event_count']}`；同日歧义延迟 `{decision['breakeven_pending_event_count']}`。
- 总滑点、总交易次数、胜率：见 summary 输出。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- curves：`{CURVES_PATH}`
- breakeven_events：`{BREAKEVEN_EVENTS_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前判断：有风险但可控。保本规则来自 Stage065 proxy，但冻结为一个低自由度结构，不按品种/日期/方向救参。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage065 closed-lot 上界通过，需要真引擎验真。
- 运行后判断：{decision['continue_value_after']}
"""
    record_path.write_text(content, encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    frames = _run_pressure_ab()
    pressure_starts = frames["pressure_starts"]
    summary = frames["summary"]
    curves = frames["curves"]
    breakeven_events = frames["breakeven_events"]
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    _plot_performance(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    pressure_starts.to_csv(PRESSURE_STARTS_PATH, index=False, encoding="utf-8-sig")
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

    metrics = _metrics(summary, aggregate, retention, breakeven_events)
    decision_fields = _stage066_decision_from_metrics(metrics)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage013_vs_stage066_breakeven_after_1r_pressure_true_engine",
        "strategy_changed": True,
        "official_live_config_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "ab_arms": {"A": BASE_VARIANT, "C": CANDIDATE_VARIANT},
        "breakeven_trigger_r": BREAKEVEN_TRIGGER_R,
        **metrics,
        **decision_fields,
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": (
            "有风险但可控。规则来自 Stage065 proxy，但冻结为 +1R 后保本，不扫品种、方向、日期或阈值。"
        ),
        "continue_value_before": "有。Stage065 closed-lot 上界通过，必须真实引擎验真。",
        "outputs": {
            "pressure_starts": str(PRESSURE_STARTS_PATH),
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
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, aggregate, retention, breakeven_events)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
