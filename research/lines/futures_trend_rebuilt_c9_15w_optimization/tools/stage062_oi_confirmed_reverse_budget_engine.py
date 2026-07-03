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
STAGE = "Stage062"
MODEL_TAG = "stage062_oi_confirmed_reverse_budget_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage062_oi_confirmed_reverse_budget_engine"
PROFILE_NAME = "stage062_oi_confirmed_reverse_budget_engine"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0
MAX_OI_CONFIRMED_VOLUME = 1

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage062_oi_confirmed_reverse_budget_engine"
STAGE_RECORD_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
BUDGET_CAP_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_budget_cap_events_{MODEL_TAG}.csv"
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
CANDIDATE_VARIANT = "stage062_oi_confirmed_reverse_budget_cap"

EXTERNAL_RESEARCH_SOURCES = [
    "CME Open Interest: https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest",
    "CME Position/Risk Management: https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management",
    "QuantConnect futures trend/carry risk regimes: https://www.quantconnect.com/research/15989/futures-trend-following-and-carry-in-different-risk-regimes/",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "Open interest is a participation/context signal, not a standalone alpha. Stage062 therefore tests a frozen "
    "reverse-risk-budget rule from Stage060/061: when OI confirms a new flat entry and the engine wants more than "
    "one contract, keep only a one-contract probe until true-engine evidence says the large budget is justified."
)


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _to_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None:
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return bool(np.isfinite(number) and number != 0.0)
    try:
        if bool(pd.isna(value)):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"}


def _stage062_extract_oi_confirmed_state(sizing: dict[str, Any], plan: dict[str, Any] | None = None) -> bool:
    plan = dict(plan or {})
    candidate = plan.get("candidate")
    values: list[Any] = [
        sizing.get("oi_price_confirm_passed"),
        sizing.get("oi_confirmed"),
        sizing.get("entry_candidate_oi_confirmed"),
        plan.get("oi_price_confirm_passed"),
        plan.get("oi_confirmed"),
        plan.get("entry_candidate_oi_confirmed"),
    ]
    if isinstance(candidate, dict):
        values.extend(
            [
                candidate.get("oi_price_confirm_passed"),
                candidate.get("oi_confirmed"),
                candidate.get("entry_candidate_oi_confirmed"),
            ]
        )
    elif candidate is not None:
        values.extend(
            [
                getattr(candidate, "oi_price_confirm_passed", None),
                getattr(candidate, "oi_confirmed", None),
                getattr(candidate, "entry_candidate_oi_confirmed", None),
            ]
        )
    return any(_to_bool(value) for value in values)


def _stage062_apply_oi_confirmed_reverse_budget_cap(
    *,
    sizing: dict[str, Any],
    plan: dict[str, Any] | None,
    entry_context: str,
    min_position_size: int,
    enabled: bool,
    max_oi_confirmed_volume: int = MAX_OI_CONFIRMED_VOLUME,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    min_size = max(0, int(min_position_size or 0))
    cap_volume = max(0, int(max_oi_confirmed_volume or 0))
    oi_confirmed = _stage062_extract_oi_confirmed_state(sizing, plan)
    selected_after = selected_before
    applied = 0

    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif not oi_confirmed:
        reason = "oi_not_confirmed"
    else:
        target = min(selected_before, max(min_size, cap_volume))
        if 0 < target < min_size:
            target = 0
        selected_after = target
        applied = int(selected_after != selected_before)
        reason = "stage062_oi_confirmed_cap_to_one" if applied else "already_at_stage062_cap"

    fields = {
        "stage062_oi_reverse_budget_enabled": int(bool(enabled)),
        "stage062_oi_reverse_budget_applied": applied,
        "stage062_oi_reverse_budget_reason": reason,
        "stage062_oi_reverse_budget_selected_volume_before": selected_before,
        "stage062_oi_reverse_budget_selected_volume_after": selected_after,
        "stage062_oi_reverse_budget_reduced_volume": selected_before - selected_after,
        "stage062_oi_reverse_budget_max_oi_confirmed_volume": cap_volume,
        "stage062_oi_reverse_budget_min_position_size": min_size,
        "stage062_oi_confirmed": int(oi_confirmed),
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage062OiConfirmedReverseBudget(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage062_oi_confirmed_reverse_budget_cap: bool = False
    stage062_max_oi_confirmed_volume: int = MAX_OI_CONFIRMED_VOLUME

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage062_oi_confirmed_reverse_budget_cap",
        "stage062_max_oi_confirmed_volume",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage062_oi_reverse_budget_count",
        "stage062_oi_reverse_budget_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage062_oi_reverse_budget_events: list[dict[str, Any]] = []
        self.stage062_oi_reverse_budget_count: int = 0
        self.stage062_oi_reverse_budget_reduced_volume: int = 0

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage062_oi_confirmed_reverse_budget_cap:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = dict(plan.get("sizing") or {})
            selected_after, fields = _stage062_apply_oi_confirmed_reverse_budget_cap(
                sizing=sizing,
                plan=plan,
                entry_context="flat_entry",
                min_position_size=int(getattr(self, "min_position_size", 1) or 1),
                enabled=bool(self.enable_stage062_oi_confirmed_reverse_budget_cap),
                max_oi_confirmed_volume=int(self.stage062_max_oi_confirmed_volume),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage062_oi_reverse_budget_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage062_oi_confirmed_reverse_budget_zero"

            event = self._stage062_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage062_oi_reverse_budget_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage062_oi_reverse_budget_count += 1
            self.stage062_oi_reverse_budget_reduced_volume += int(fields["stage062_oi_reverse_budget_reduced_volume"])
        return plans

    def _stage062_event_from_plan(
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
            "reason": "stage062_oi_confirmed_reverse_budget_cap",
            "volume": int(fields["stage062_oi_reverse_budget_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage062_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage062 OI confirmed reverse budget",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage062 isolated research candidate. Stage013 account pilot remains active; "
            "new OI-confirmed flat-entry budget above one contract is capped to a probe size."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": s013.PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": s013.PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": s013.PILOT_MIN_VOLUME,
        "enable_stage062_oi_confirmed_reverse_budget_cap": True,
        "stage062_max_oi_confirmed_volume": MAX_OI_CONFIRMED_VOLUME,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage062OiConfirmedReverseBudget
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage062(
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
        profile = _stage062_profile(metadata)
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
    starts["stage062_pressure_rank"] = np.arange(1, len(starts) + 1)
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


def _curve_for_variant(
    combined: pd.DataFrame,
    *,
    start: pd.Timestamp,
    variant_label: str,
) -> pd.DataFrame:
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
        raise RuntimeError("Stage062 pressure starts are empty; run Stage054/055 first.")

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for index, row in enumerate(starts.itertuples(index=False), start=1):
        start = pd.Timestamp(row.requested_start).normalize()
        print(f"[stage062] A Stage013 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        base_combined, base_frames, _base_spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _curve_for_variant(base_combined, start=start, variant_label=BASE_VARIANT)
        curve_frames.append(base_curve)
        summary_rows.append(_summarize_curve(base_curve, start=start, variant_label=BASE_VARIANT))
        _append_frame(candidate_frames, base_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_frames, base_frames.get("trades", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(entry_risk_frames, base_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_event_frames, base_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)

        print(f"[stage062] C Stage062 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        cap_combined, cap_frames, _cap_spec = _run_live_stage062(metadata, start, REQUESTED_END)
        cap_curve = _curve_for_variant(cap_combined, start=start, variant_label=CANDIDATE_VARIANT)
        curve_frames.append(cap_curve)
        summary_rows.append(_summarize_curve(cap_curve, start=start, variant_label=CANDIDATE_VARIANT))
        _append_frame(candidate_frames, cap_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(trade_frames, cap_frames.get("trades", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(entry_risk_frames, cap_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(trade_event_frames, cap_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    budget_cap_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage062_oi_confirmed_reverse_budget_cap")].copy()
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
        "budget_cap_events": budget_cap_events,
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
    wide["stage062_vs_stage013_return_ratio"] = (
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
            CANDIDATE_VARIANT: "stage062_total_return_pct",
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


def _metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    budget_cap_events: pd.DataFrame,
) -> dict[str, Any]:
    candidate_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)]
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)]
    strict_scope = "all_trading_end_dates_gt_1y"
    final_scope = "start_to_2026_06_30_only"
    reduced_volume = (
        int(
            pd.to_numeric(
                budget_cap_events.get("stage062_oi_reverse_budget_reduced_volume", pd.Series(dtype=float)),
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )
        if not budget_cap_events.empty
        else 0
    )
    return {
        "pressure_start_count": int(candidate_summary["requested_start_month"].nunique()),
        "stage013_positive_start_count": int(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "stage062_positive_start_count": int(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "stage013_min_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").min()),
        "stage062_min_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").min()),
        "stage013_median_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").median()),
        "stage062_median_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").median()),
        "stage013_worst_max_dd_pct": float(pd.to_numeric(base_summary["max_dd_pct"], errors="coerce").min()),
        "stage062_worst_max_dd_pct": float(pd.to_numeric(candidate_summary["max_dd_pct"], errors="coerce").min()),
        "stage013_median_sharpe": float(pd.to_numeric(base_summary["sharpe"], errors="coerce").median()),
        "stage062_median_sharpe": float(pd.to_numeric(candidate_summary["sharpe"], errors="coerce").median()),
        "stage013_strict_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "negative_count", 0.0)),
        "stage062_strict_negative_window_count": int(
            _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "negative_count", 0.0)
        ),
        "stage013_strict_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage062_strict_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage013_strict_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, strict_scope, "min_return_pct"),
        "stage062_strict_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "min_return_pct"),
        "stage013_to_final_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, final_scope, "negative_count", 0.0)),
        "stage062_to_final_negative_window_count": int(
            _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "negative_count", 0.0)
        ),
        "stage013_to_final_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, final_scope, "min_return_pct"),
        "stage062_to_final_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "min_return_pct"),
        "retention_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "budget_cap_event_count": int(len(budget_cap_events)),
        "budget_cap_reduced_volume": reduced_volume,
    }


def _stage062_decision_from_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    improves_left_tail = (
        int(metrics.get("stage062_strict_negative_window_count", 0))
        < int(metrics.get("stage013_strict_negative_window_count", 0))
        and float(metrics.get("stage062_strict_min_return_pct", np.nan))
        > float(metrics.get("stage013_strict_min_return_pct", np.nan))
    )
    retention_rows = int(metrics.get("retention_rows", 0) or 0)
    retention_ok = retention_rows > 0 and int(metrics.get("retention_pass_count", 0) or 0) == retention_rows
    pressure_goal_pass = int(metrics.get("stage062_strict_negative_window_count", 0) or 0) == 0 and retention_ok
    if pressure_goal_pass:
        decision_text = "stage062_pressure_goal_pass_expand_validation"
        next_step = "扩到更密日级/逐半年多周期，并做交易明细和 AI 月度应用审计。"
        overfit_after = "否，但仍需外推验证。压力集通过只能说明候选值得扩样本，不能直接上线。"
        continue_after = "有。压力左尾清零且收益保留通过，值得进入全量验证。"
    elif improves_left_tail and retention_ok:
        decision_text = "stage062_pressure_improves_left_tail_expand_validation"
        next_step = "先扩到 Stage053 级别更多压力起点，再决定是否做全量日级密集回测。"
        overfit_after = "暂不判定过拟合。规则未改参且压力集改善，但还没有跨样本证明。"
        continue_after = "有。压力左尾改善且收益保留过关，值得扩样本验证。"
    else:
        decision_text = "stage062_pressure_not_enough_stop_no_param_rescue"
        next_step = "停止扫 OI 阈值/手数/品种；回到失败归因，寻找更稳定的预算信号。"
        overfit_after = "否。本阶段没有救参；如果继续调 OI 阈值或按产品特殊处理就是过拟合。"
        continue_after = "有限。若压力集不改善或右尾损失过大，该形状不应继续交易化。"
    return {
        "decision": decision_text,
        "next_step": next_step,
        "improves_left_tail": bool(improves_left_tail),
        "retention_ok": bool(retention_ok),
        "pressure_goal_pass": bool(pressure_goal_pass),
        "overfit_reflection_after": overfit_after,
        "continue_value_after": continue_after,
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
    axes[0].set_title("Stage062 Pressure Starts Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage062 Pressure Starts Drawdown")
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
    budget_cap_events: pd.DataFrame,
) -> None:
    report = f"""# Stage062 OI 确认反向预算 cap 真引擎压力验证

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：独立研究 profile 真实引擎 A/C 压力起点验证；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 参考：{'; '.join(EXTERNAL_RESEARCH_SOURCES)}
- 我的判断：OI 只代表参与度/趋势确认背景，不是独立 alpha。Stage062 只验证 Stage060/061 发现的反向风险预算形状，不把 OI 当作加仓信号。

## A/C 口径

- A：`{BASE_VARIANT}`，Stage013 账户状态小风险试探母本。
- C：`{CANDIDATE_VARIANT}`，Stage013 + 新 `flat_entry` 若 `oi_price_confirm_passed/oi_confirmed` 为真且 `selected_volume > 1`，则最高 `{MAX_OI_CONFIRMED_VOLUME}` 手。
- 样本：Stage054/055 去重后的 `{decision['pressure_start_count']}` 个左尾压力日级起点，结束日统一 `2026-06-30`。
- 动作边界：不强平、不暂停、不改 AI 池、不影响换月、加仓、反手、开仓日实时止损重试。

## 核心结果

- Stage013 正收益起点：`{decision['stage013_positive_start_count']}/{decision['pressure_start_count']}`；Stage062：`{decision['stage062_positive_start_count']}/{decision['pressure_start_count']}`
- 期末收益最小：Stage013 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage062 `{decision['stage062_min_total_return_pct']:.4f}%`
- 最差最大回撤：Stage013 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage062 `{decision['stage062_worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：Stage013 `{decision['stage013_strict_negative_window_count']}` / `{decision['stage013_strict_window_count']}`；Stage062 `{decision['stage062_strict_negative_window_count']}` / `{decision['stage062_strict_window_count']}`
- 严格最差收益：Stage013 `{decision['stage013_strict_min_return_pct']:.4f}%`；Stage062 `{decision['stage062_strict_min_return_pct']:.4f}%`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- Stage062 cap 事件：`{decision['budget_cap_event_count']}`；减少手数：`{decision['budget_cap_reduced_volume']}`

## 多起点摘要

{_md_table(summary)}

## 目标审计摘要

{_md_table(aggregate.head(60))}

## 收益保留

{_md_table(retention)}

## 预算 cap 事件样本

{_md_table(budget_cap_events.head(40))}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- summary: `{SUMMARY_PATH}`
- curves: `{CURVES_PATH}`
- budget_cap_events: `{BUDGET_CAP_EVENTS_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- performance_chart: `{PERFORMANCE_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage062_oi_confirmed_reverse_budget_engine.md"
    content = f"""# Stage062 - OI 确认反向预算 cap 真引擎压力验证

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选 A/C 压力验证，不改官方实盘配置。
- 是否重要突破：`{'是' if decision['decision'].endswith('expand_validation') else '否'}`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：CME Open Interest、CME position/risk management、QuantConnect futures trend/carry risk regimes、pysystemtrade。
- 我的判断：OI 是参与度/趋势确认背景，不是独立 alpha；本阶段只做 Stage060/061 反向预算形状的真引擎验真。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage062_oi_confirmed_reverse_budget_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage062_oi_confirmed_reverse_budget_engine.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`MAX_OI_CONFIRMED_VOLUME={MAX_OI_CONFIRMED_VOLUME}`、`selector=oi_price_confirm_passed/oi_confirmed`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`{BASE_VARIANT}`，Stage013。
- C：`{CANDIDATE_VARIANT}`，Stage013 + OI 确认新 flat_entry 最多 `{MAX_OI_CONFIRMED_VOLUME}` 手。
- 样本：Stage054/055 去重左尾压力日级起点 `{decision['pressure_start_count']}` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前重建 C9/15w 与 Stage013 真实引擎口径。
- 样本过滤：不按品种/方向/日期/source 过滤。
- 策略/归因口径：真实引擎；不连接 CTP、不调用订单 API。

## 结果

- 期末权益：见 summary 输出。
- 总收益：Stage013 最小 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage062 最小 `{decision['stage062_min_total_return_pct']:.4f}%`
- 最大回撤：Stage013 最差 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage062 最差 `{decision['stage062_worst_max_dd_pct']:.4f}%`
- Sharpe：Stage013 中位 `{decision['stage013_median_sharpe']:.4f}`；Stage062 中位 `{decision['stage062_median_sharpe']:.4f}`
- 总滑点：见 summary 输出。
- 总交易次数：见 summary 输出。
- 胜率：见 summary 输出。
- 其他关键指标：Stage013 严格负窗口 `{decision['stage013_strict_negative_window_count']}`，Stage062 严格负窗口 `{decision['stage062_strict_negative_window_count']}`，80% 收益保留 `{decision['retention_pass_count']}/{decision['retention_rows']}`，cap 事件 `{decision['budget_cap_event_count']}`，减少手数 `{decision['budget_cap_reduced_volume']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- daily：`{CURVES_PATH}`
- quality：`{BUDGET_CAP_EVENTS_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：只有压力集相对 Stage013 改善且收益保留过关，才扩到更密日级/多周期；否则停止该形状，不扫 OI 阈值或手数。
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前判断：有风险但可控。规则来自最差窗口归因，必须小心；但它是固定预算原则，不是品种/日期/方向补丁。
- 运行后判断：{decision['overfit_reflection_after']}
- 原因：本阶段没有根据结果调整 OI 阈值、手数或产品。

## 继续价值反思

- 运行前判断：有。Stage061 闭合成交代理显示该形状值得真实引擎验真。
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

    frames = _run_pressure_ab()
    pressure_starts = frames["pressure_starts"]
    summary = frames["summary"]
    curves = frames["curves"]
    budget_cap_events = frames["budget_cap_events"]
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
    budget_cap_events.to_csv(BUDGET_CAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, budget_cap_events)
    decision_fields = _stage062_decision_from_metrics(metrics)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage013_vs_stage062_oi_confirmed_reverse_budget_pressure_true_engine",
        "strategy_changed": True,
        "official_live_config_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "ab_arms": {
            "A": BASE_VARIANT,
            "C": CANDIDATE_VARIANT,
        },
        "selector": "oi_price_confirm_passed_or_alias",
        "max_oi_confirmed_volume": MAX_OI_CONFIRMED_VOLUME,
        **metrics,
        **decision_fields,
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": (
            "有风险但可控。规则来自最差窗口归因，但冻结为 OI 确认大手数反向预算原则，不扫品种、方向、日期或阈值。"
        ),
        "continue_value_before": "有。Stage061 闭合成交代理显示该形状值得真实引擎验真。",
        "outputs": {
            "pressure_starts": str(PRESSURE_STARTS_PATH),
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "budget_cap_events": str(BUDGET_CAP_EVENTS_PATH),
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
    _write_report(decision, summary, aggregate, retention, budget_cap_events)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
