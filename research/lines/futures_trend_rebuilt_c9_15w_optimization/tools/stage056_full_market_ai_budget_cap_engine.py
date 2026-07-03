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
import stage038_candidate_pit_feature_matrix_audit as s038
import stage055_new_entry_signal_budget_audit as s055
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage056"
MODEL_TAG = "stage056_full_market_ai_budget_cap_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage056_full_market_ai_budget_cap_engine"
PROFILE_NAME = "stage056_full_market_ai_budget_cap_engine"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0
MAX_NON_TOP8_VOLUME = 1

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage056_full_market_ai_budget_cap_engine"
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
CANDIDATE_VARIANT = "stage056_full_market_ai_budget_cap"

EXTERNAL_RESEARCH_JUDGMENT = (
    "Position-sizing and trend-following references support separating signal quality from risk budget: preserve "
    "broad trend-following participation, but release larger new-entry risk only when a predeclared, point-in-time "
    "cross-sectional quality signal is strong. Stage056 freezes one such rule using full-market AI top8 and avoids "
    "product, direction, date, or threshold rescue."
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
    if value is None or pd.isna(value):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(float(value) != 0.0)
    return str(value).strip().lower() in {"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"}


def _product_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _build_stage056_full_market_lookup(monthly: pd.DataFrame) -> dict[str, pd.DataFrame]:
    required = {"eval_date", "product_vt_symbol"}
    if monthly.empty or not required.issubset(monthly.columns):
        return {}
    frame = monthly.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    frame["product_key"] = frame["product_vt_symbol"].map(_product_key)
    frame = frame.dropna(subset=["eval_date"])
    if "stage021_ai_top8" not in frame.columns:
        frame["stage021_ai_top8"] = False
    if "ai_rank_desc" not in frame.columns:
        frame["ai_rank_desc"] = np.nan
    if "predicted_product_suitability_probability" not in frame.columns:
        frame["predicted_product_suitability_probability"] = np.nan

    lookup: dict[str, pd.DataFrame] = {}
    keep = [
        "eval_date",
        "product_key",
        "stage021_ai_top8",
        "ai_rank_desc",
        "predicted_product_suitability_probability",
    ]
    for key, group in frame[keep].sort_values(["product_key", "eval_date"]).groupby("product_key", sort=True):
        lookup[str(key)] = group.reset_index(drop=True)
    return lookup


def _stage056_lookup_full_market_ai_state(
    lookup: dict[str, pd.DataFrame],
    product_vt_symbol: Any,
    entry_date: Any,
) -> dict[str, Any]:
    key = _product_key(product_vt_symbol)
    group = lookup.get(key)
    if group is None or group.empty:
        return {
            "full_market_ai_top8": False,
            "full_market_eval_date": "",
            "full_market_ai_rank_desc": np.nan,
            "full_market_probability": np.nan,
            "full_market_lookup_missing": 1,
        }
    date = pd.Timestamp(entry_date).normalize()
    eval_dates = group["eval_date"].to_numpy(dtype="datetime64[ns]")
    idx = int(np.searchsorted(eval_dates, np.datetime64(date.to_datetime64(), "ns"), side="right")) - 1
    if idx < 0:
        return {
            "full_market_ai_top8": False,
            "full_market_eval_date": "",
            "full_market_ai_rank_desc": np.nan,
            "full_market_probability": np.nan,
            "full_market_lookup_missing": 1,
        }
    row = group.iloc[idx]
    return {
        "full_market_ai_top8": _to_bool(row.get("stage021_ai_top8", False)),
        "full_market_eval_date": _date_text(row["eval_date"]),
        "full_market_ai_rank_desc": pd.to_numeric(pd.Series([row.get("ai_rank_desc")]), errors="coerce").iloc[0],
        "full_market_probability": pd.to_numeric(
            pd.Series([row.get("predicted_product_suitability_probability")]), errors="coerce"
        ).iloc[0],
        "full_market_lookup_missing": 0,
    }


def _stage056_apply_full_market_ai_budget_cap(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    full_market_state: dict[str, Any] | None,
    min_position_size: int,
    enabled: bool,
    max_non_top8_volume: int = MAX_NON_TOP8_VOLUME,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    state = dict(full_market_state or {})
    top8 = _to_bool(state.get("full_market_ai_top8", False))
    min_size = max(0, int(min_position_size or 0))
    cap_volume = max(0, int(max_non_top8_volume or 0))
    selected_after = selected_before
    applied = 0

    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif top8:
        reason = "full_market_ai_top8_release_allowed"
    else:
        target = min(selected_before, max(min_size, cap_volume))
        if 0 < target < min_size:
            target = 0
        selected_after = target
        applied = int(selected_after != selected_before)
        reason = "stage056_non_full_market_ai_top8_cap" if applied else "already_at_stage056_cap"

    fields = {
        "stage056_budget_cap_enabled": int(bool(enabled)),
        "stage056_budget_cap_applied": applied,
        "stage056_budget_cap_reason": reason,
        "stage056_budget_cap_selected_volume_before": selected_before,
        "stage056_budget_cap_selected_volume_after": selected_after,
        "stage056_budget_cap_reduced_volume": selected_before - selected_after,
        "stage056_budget_cap_max_non_top8_volume": cap_volume,
        "stage056_budget_cap_min_position_size": min_size,
        "stage056_full_market_ai_top8": int(top8),
        "stage056_full_market_eval_date": str(state.get("full_market_eval_date") or ""),
        "stage056_full_market_ai_rank_desc": state.get("full_market_ai_rank_desc", np.nan),
        "stage056_full_market_probability": state.get("full_market_probability", np.nan),
        "stage056_full_market_lookup_missing": int(state.get("full_market_lookup_missing", 0) or 0),
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage056FullMarketAiBudgetCap(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage056_full_market_ai_budget_cap: bool = False
    stage056_full_market_predictions_path: str = str(s038.FULL_MARKET_PREDICTIONS_PATH)
    stage056_max_non_top8_volume: int = MAX_NON_TOP8_VOLUME

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage056_full_market_ai_budget_cap",
        "stage056_full_market_predictions_path",
        "stage056_max_non_top8_volume",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage056_budget_cap_count",
        "stage056_budget_cap_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage056_budget_cap_events: list[dict[str, Any]] = []
        self.stage056_budget_cap_count: int = 0
        self.stage056_budget_cap_reduced_volume: int = 0
        path = Path(str(getattr(self, "stage056_full_market_predictions_path", "") or ""))
        monthly = pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()
        self.stage056_full_market_lookup = _build_stage056_full_market_lookup(monthly)

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage056_full_market_ai_budget_cap:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            bar = plan.get("target_bar")
            bar_datetime = getattr(bar, "datetime", None)
            entry_date = pd.Timestamp(bar_datetime).normalize() if bar_datetime is not None else pd.NaT
            sizing = dict(plan.get("sizing") or {})
            state = _stage056_lookup_full_market_ai_state(
                self.stage056_full_market_lookup,
                product_vt_symbol,
                entry_date,
            )
            selected_after, fields = _stage056_apply_full_market_ai_budget_cap(
                sizing=sizing,
                entry_context="flat_entry",
                full_market_state=state,
                min_position_size=int(getattr(self, "min_position_size", 1) or 1),
                enabled=bool(self.enable_stage056_full_market_ai_budget_cap),
                max_non_top8_volume=int(self.stage056_max_non_top8_volume),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage056_budget_cap_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage056_full_market_ai_budget_cap_zero"

            event = self._stage056_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage056_budget_cap_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage056_budget_cap_count += 1
            self.stage056_budget_cap_reduced_volume += int(fields["stage056_budget_cap_reduced_volume"])
        return plans

    def _stage056_event_from_plan(
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
            "reason": "stage056_full_market_ai_budget_cap",
            "volume": int(fields["stage056_budget_cap_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage056_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage056 full-market AI budget cap",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage056 isolated research candidate. Stage013 account pilot remains active; "
            "new flat-entry budget above one contract is released only for point-in-time full-market AI top8 products."
        ),
    )
    overrides = {
        **spec.overrides,
        **build_official_live_strategy_overrides(),
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": s013.PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": s013.PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": s013.PILOT_MIN_VOLUME,
        "enable_stage056_full_market_ai_budget_cap": True,
        "stage056_full_market_predictions_path": str(s038.FULL_MARKET_PREDICTIONS_PATH),
        "stage056_max_non_top8_volume": MAX_NON_TOP8_VOLUME,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage056FullMarketAiBudgetCap
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage056(
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
        profile = _stage056_profile(metadata)
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
    starts["stage056_pressure_rank"] = np.arange(1, len(starts) + 1)
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
        raise RuntimeError("Stage056 pressure starts are empty; run Stage054/055 first.")

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for index, row in enumerate(starts.itertuples(index=False), start=1):
        start = pd.Timestamp(row.requested_start).normalize()
        print(f"[stage056] A Stage013 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        base_combined, base_frames, _base_spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _curve_for_variant(base_combined, start=start, variant_label=BASE_VARIANT)
        curve_frames.append(base_curve)
        summary_rows.append(_summarize_curve(base_curve, start=start, variant_label=BASE_VARIANT))
        _append_frame(candidate_frames, base_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_frames, base_frames.get("trades", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(entry_risk_frames, base_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)
        _append_frame(trade_event_frames, base_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=BASE_VARIANT)

        print(f"[stage056] C Stage056 {index}/{len(starts)} start={_date_text(start)}", flush=True)
        cap_combined, cap_frames, _cap_spec = _run_live_stage056(metadata, start, REQUESTED_END)
        cap_curve = _curve_for_variant(cap_combined, start=start, variant_label=CANDIDATE_VARIANT)
        curve_frames.append(cap_curve)
        summary_rows.append(_summarize_curve(cap_curve, start=start, variant_label=CANDIDATE_VARIANT))
        _append_frame(candidate_frames, cap_frames.get("entry_candidates", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(trade_frames, cap_frames.get("trades", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(entry_risk_frames, cap_frames.get("entry_risk", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)
        _append_frame(trade_event_frames, cap_frames.get("trade_events", pd.DataFrame()), start=start, variant_label=CANDIDATE_VARIANT)

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    budget_cap_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage056_full_market_ai_budget_cap")].copy()
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
    wide["stage056_vs_stage013_return_ratio"] = (
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
            CANDIDATE_VARIANT: "stage056_total_return_pct",
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
                budget_cap_events.get("stage056_budget_cap_reduced_volume", pd.Series(dtype=float)),
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
        "stage056_positive_start_count": int(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").gt(0).sum()),
        "stage013_min_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").min()),
        "stage056_min_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").min()),
        "stage013_median_total_return_pct": float(pd.to_numeric(base_summary["total_return_pct"], errors="coerce").median()),
        "stage056_median_total_return_pct": float(pd.to_numeric(candidate_summary["total_return_pct"], errors="coerce").median()),
        "stage013_worst_max_dd_pct": float(pd.to_numeric(base_summary["max_dd_pct"], errors="coerce").min()),
        "stage056_worst_max_dd_pct": float(pd.to_numeric(candidate_summary["max_dd_pct"], errors="coerce").min()),
        "stage013_median_sharpe": float(pd.to_numeric(base_summary["sharpe"], errors="coerce").median()),
        "stage056_median_sharpe": float(pd.to_numeric(candidate_summary["sharpe"], errors="coerce").median()),
        "stage013_strict_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "negative_count", 0.0)),
        "stage056_strict_negative_window_count": int(
            _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "negative_count", 0.0)
        ),
        "stage013_strict_window_count": int(_variant_metric(aggregate, BASE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage056_strict_window_count": int(_variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "window_count", 0.0)),
        "stage013_strict_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, strict_scope, "min_return_pct"),
        "stage056_strict_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, strict_scope, "min_return_pct"),
        "stage013_to_final_negative_window_count": int(_variant_metric(aggregate, BASE_VARIANT, final_scope, "negative_count", 0.0)),
        "stage056_to_final_negative_window_count": int(
            _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "negative_count", 0.0)
        ),
        "stage013_to_final_min_return_pct": _variant_metric(aggregate, BASE_VARIANT, final_scope, "min_return_pct"),
        "stage056_to_final_min_return_pct": _variant_metric(aggregate, CANDIDATE_VARIANT, final_scope, "min_return_pct"),
        "retention_pass_count": int(retention["passes_80pct_retention"].sum()) if not retention.empty else 0,
        "retention_rows": int(len(retention)),
        "budget_cap_event_count": int(len(budget_cap_events)),
        "budget_cap_reduced_volume": reduced_volume,
    }


def _plot_performance(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    color_map = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#2563eb"}
    for (variant, start), group in curves.groupby(["variant", "requested_start_month"], sort=True):
        group = group.sort_values("date")
        label = f"{variant} {start}"
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.72, color=color_map.get(variant), label=label)
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.72, color=color_map.get(variant), label=label)
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage056 Pressure Starts Absolute Account Equity")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage056 Pressure Starts Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=6, ncol=3, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_goal_audit(aggregate: pd.DataFrame, worst: pd.DataFrame, fixed: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    colors = {BASE_VARIANT: "#64748b", CANDIDATE_VARIANT: "#2563eb"}
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
        ax.scatter(
            np.arange(len(plot)),
            plot["return_pct"],
            s=12,
            c=[colors.get(v, "#94a3b8") for v in plot["variant"]],
        )
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
    report = f"""# Stage056 full-market AI Top8 新开仓预算 cap 真引擎压力验证

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：独立研究 profile 真实引擎 A/C 压力起点验证；不改 C9 官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- 趋势跟随与 position sizing 资料支持把信号质量和风险预算拆开：弱质量信号仍可小风险参与，强质量信号才释放更大新开仓预算。
- GitHub/开源资料更多是通用 risk budget/backtest 框架，没有可直接复制的商品池规则。
- Stage056 因此只冻结 `full_market_ai_top8` 一个 PIT 横截面质量信号；不按品种、方向、年份、日期或最差窗口定制。

## A/C 口径

- A：`{BASE_VARIANT}`，Stage013 账户状态小风险试探母本。
- C：`{CANDIDATE_VARIANT}`，Stage013 + 新 `flat_entry` 若不是 PIT full-market AI Top8，则 `selected_volume` 最高 `{MAX_NON_TOP8_VOLUME}` 手。
- 样本：Stage054/055 去重后的 `{decision['pressure_start_count']}` 个左尾压力日级起点，结束日统一 `2026-06-30`。
- 动作边界：不强平、不暂停、不改 AI 池、不影响换月、加仓、反手、开仓日实时止损重试。

## 核心结果

- Stage013 正收益起点：`{decision['stage013_positive_start_count']}/{decision['pressure_start_count']}`；Stage056：`{decision['stage056_positive_start_count']}/{decision['pressure_start_count']}`
- 期末收益最小：Stage013 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage056 `{decision['stage056_min_total_return_pct']:.4f}%`
- 最差最大回撤：Stage013 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage056 `{decision['stage056_worst_max_dd_pct']:.4f}%`
- 严格任意结束日 `>1` 年负窗口：Stage013 `{decision['stage013_strict_negative_window_count']}` / `{decision['stage013_strict_window_count']}`；Stage056 `{decision['stage056_strict_negative_window_count']}` / `{decision['stage056_strict_window_count']}`
- 严格最差收益：Stage013 `{decision['stage013_strict_min_return_pct']:.4f}%`；Stage056 `{decision['stage056_strict_min_return_pct']:.4f}%`
- 到 `2026-06-30` 负窗口：Stage013 `{decision['stage013_to_final_negative_window_count']}`；Stage056 `{decision['stage056_to_final_negative_window_count']}`
- 80% 收益保留：`{decision['retention_pass_count']}/{decision['retention_rows']}`
- Stage056 cap 事件：`{decision['budget_cap_event_count']}`；减少手数：`{decision['budget_cap_reduced_volume']}`

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
    record_path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage056_full_market_ai_budget_cap_engine.md"
    content = f"""# Stage056 - full-market AI Top8 新开仓预算 cap 真引擎压力验证

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选 A/C 压力验证，不改官方实盘配置。
- 是否重要突破：`{'是' if decision['decision'].endswith('expand_validation') else '否'}`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：trend-following position sizing、Rob Carver risk budget、系统化趋势跟随综述、PySystemTrade/PyTrendFollow 等开源实现。
- 我的判断：有第一性价值的是“质量信号决定风险预算释放”，不是按最差品种/方向/月份做黑名单；因此本阶段只冻结 full-market AI Top8 一条规则。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage056_full_market_ai_budget_cap_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage056_full_market_ai_budget_cap.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`MAX_NON_TOP8_VOLUME={MAX_NON_TOP8_VOLUME}`、`selector=full_market_ai_top8`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`{BASE_VARIANT}`，Stage013。
- C：`{CANDIDATE_VARIANT}`，Stage013 + 非 full-market AI Top8 新 flat_entry 最多 `{MAX_NON_TOP8_VOLUME}` 手。
- 样本：Stage054/055 去重左尾压力日级起点 `{decision['pressure_start_count']}` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前重建 C9/15w 与 Stage013 真实引擎口径。
- 样本过滤：不按品种/方向/日期/source 过滤。
- 策略/归因口径：真实引擎；不连接 CTP、不调用订单 API。

## 结果

- 期末权益：见 summary 输出。
- 总收益：Stage013 最小 `{decision['stage013_min_total_return_pct']:.4f}%`；Stage056 最小 `{decision['stage056_min_total_return_pct']:.4f}%`
- 最大回撤：Stage013 最差 `{decision['stage013_worst_max_dd_pct']:.4f}%`；Stage056 最差 `{decision['stage056_worst_max_dd_pct']:.4f}%`
- Sharpe：Stage013 中位 `{decision['stage013_median_sharpe']:.4f}`；Stage056 中位 `{decision['stage056_median_sharpe']:.4f}`
- 总滑点：见 summary 输出。
- 总交易次数：见 summary 输出。
- 胜率：见 summary 输出。
- 其他关键指标：Stage013 严格负窗口 `{decision['stage013_strict_negative_window_count']}`，Stage056 严格负窗口 `{decision['stage056_strict_negative_window_count']}`，80% 收益保留 `{decision['retention_pass_count']}/{decision['retention_rows']}`，cap 事件 `{decision['budget_cap_event_count']}`，减少手数 `{decision['budget_cap_reduced_volume']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- daily：`{CURVES_PATH}`
- quality：`{BUDGET_CAP_EVENTS_PATH}`
- goal_aggregate：`{GOAL_AGGREGATE_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：只有压力集相对 Stage013 改善且收益保留过关，才扩到更密日级/多周期；否则停止该形状，不扫 TopN 或手数。
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前判断：有风险但可控。规则来自最差窗口归因，必须小心；但它是固定横截面质量预算原则，不是品种/日期/方向补丁。
- 运行后判断：{decision['overfit_reflection_after']}
- 原因：本阶段没有根据结果调整 TopN、手数或产品。

## 继续价值反思

- 运行前判断：有。Stage055 已显示 `selected_volume>1 且非 full-market AI top8` 与左尾亏损高度重合，值得做真实引擎验真。
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
    improves_left_tail = (
        metrics["stage056_strict_negative_window_count"] < metrics["stage013_strict_negative_window_count"]
        and metrics["stage056_strict_min_return_pct"] > metrics["stage013_strict_min_return_pct"]
    )
    retention_ok = metrics["retention_rows"] > 0 and metrics["retention_pass_count"] == metrics["retention_rows"]
    pressure_goal_pass = metrics["stage056_strict_negative_window_count"] == 0 and retention_ok
    if pressure_goal_pass:
        decision_text = "stage056_pressure_goal_pass_expand_validation"
        next_step = "扩到全量日级/逐半年多周期，并做交易明细和 AI 月度应用审计。"
        overfit_after = "否，但仍需外推验证。压力集通过只能说明候选值得扩样本，不能直接上线。"
        continue_after = "有。压力左尾清零且收益保留通过，值得进入全量验证。"
    elif improves_left_tail and retention_ok:
        decision_text = "stage056_pressure_improves_left_tail_expand_validation"
        next_step = "先扩到 32 个 Stage053 压力起点，再决定是否做全量日级密集回测。"
        overfit_after = "暂不判定过拟合。规则未改参且压力集改善，但还没有跨样本证明。"
        continue_after = "有。压力左尾改善且收益保留过关，值得扩样本验证。"
    else:
        decision_text = "stage056_pressure_not_enough_stop_no_param_rescue"
        next_step = "停止扫 TopN/手数/品种；回到 Stage056 失败归因，寻找更稳定的预算信号。"
        overfit_after = "否。本阶段没有救参；如果继续调 Top8/Top6/2手就是过拟合。"
        continue_after = "有限。若压力集都不改善或右尾损失过大，该形状不应继续交易化。"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "stage013_vs_stage056_full_market_ai_top8_budget_cap_pressure_true_engine",
        "decision": decision_text,
        "next_step": next_step,
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
        "selector": "full_market_ai_top8",
        "max_non_top8_volume": MAX_NON_TOP8_VOLUME,
        **metrics,
        "improves_left_tail": bool(improves_left_tail),
        "retention_ok": bool(retention_ok),
        "pressure_goal_pass": bool(pressure_goal_pass),
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": (
            "有风险但可控。规则来自最差窗口归因，但冻结为横截面质量预算原则，不扫品种、方向、日期或阈值。"
        ),
        "continue_value_before": (
            "有。Stage055 显示非 full-market AI top8 的大手数新开仓是左尾主要候选，需要真实引擎验真。"
        ),
        "overfit_reflection_after": overfit_after,
        "continue_value_after": continue_after,
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
