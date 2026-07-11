#!/usr/bin/env python3
"""Stage010: parameter-free drawdown recovery-progress risk ramp."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
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


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage006_stage013_reconciled_equity_engine as s6  # noqa: E402
import stage007_stage006_reconciled_equity_halfyear as s7  # noqa: E402
import stage009_gate_opportunity_cost_attribution as s9  # noqa: E402


TRIGGER_DRAWDOWN = 0.30
ACTIVE_POSITIONS_MAX = 1
MIN_VOLUME = 1

LINE_ID = s6.LINE_ID
STAGE_ID = "stage010_drawdown_recovery_progress_ramp"
STAGE_LABEL = "Stage010"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"
A_VERSION = s6.A_VERSION
C_VERSION = "c_current_ai_stage010_recovery_progress_ramp"
VERSIONS = (A_VERSION, C_VERSION)
A_STRATEGY = s6.A_STRATEGY
C_STRATEGY = "stage010_anchor_c_recovery_progress_ramp"
ANCHOR_STARTS = (
    pd.Timestamp("2020-01-01"),
    pd.Timestamp("2021-01-01"),
    pd.Timestamp("2022-01-01"),
)
REQUESTED_END = s7.REQUESTED_END
RETURN_RETENTION_MIN = 0.70
FULL_DD_IMPROVEMENT_MIN_PP = 3.0
RAMP_REASON = "stage010_drawdown_recovery_progress_ramp_evaluation"
EPISODE_DAILY_REASON = "stage010_drawdown_episode_daily"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_gates_{MODEL_TAG}.csv"
WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_2022_drawdown_windows_{MODEL_TAG}.csv"
REPRODUCTION_PATH = OUT / f"{OUTPUT_PREFIX}_a_reproduction_{MODEL_TAG}.csv"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_reconciliation_{MODEL_TAG}.csv"
RAMP_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ramp_audit_{MODEL_TAG}.csv"
EPISODE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_episode_daily_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_equity_drawdown_{MODEL_TAG}.png"

SAVE_FRAME_NAMES = (
    "entry_candidates",
    "trades",
    "trade_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
    "stage010_ramp_events",
    "stage010_episode_daily",
    "stop_retry_events",
)


def _update_episode_state(
    *,
    episode_active: bool,
    episode_peak_drawdown: float,
    current_drawdown: float,
    trigger_drawdown: float = TRIGGER_DRAWDOWN,
) -> dict[str, Any]:
    current = max(0.0, float(current_drawdown))
    trigger = max(0.0, float(trigger_drawdown))
    if current < trigger:
        return {"episode_active": False, "episode_peak_drawdown": 0.0}
    peak = current if not episode_active else max(float(episode_peak_drawdown), current)
    return {"episode_active": True, "episode_peak_drawdown": peak}


def _recovery_progress(
    *, current_drawdown: float, episode_peak_drawdown: float, trigger_drawdown: float
) -> float:
    current = float(current_drawdown)
    trigger = float(trigger_drawdown)
    peak = max(float(episode_peak_drawdown), current, trigger)
    denominator = peak - trigger
    if denominator <= 1e-15:
        return 0.0
    return float(np.clip((peak - current) / denominator, 0.0, 1.0))


def _evaluate_recovery_ramp(
    *,
    selected_volume_before: int,
    entry_context: str,
    active_positions_before: int,
    current_drawdown: float,
    episode_peak_drawdown: float,
    enabled: bool = True,
    trigger_drawdown: float = TRIGGER_DRAWDOWN,
    active_positions_max: int = ACTIVE_POSITIONS_MAX,
    min_volume: int = MIN_VOLUME,
) -> dict[str, Any]:
    before = max(0, int(selected_volume_before or 0))
    active = max(0, int(active_positions_before or 0))
    trigger = max(0.0, float(trigger_drawdown))
    current = max(0.0, float(current_drawdown))
    peak = max(float(episode_peak_drawdown), current, trigger)
    minimum = max(0, int(min_volume or 0))
    eligible = bool(
        enabled
        and before > 0
        and str(entry_context or "") == "flat_entry"
        and active <= max(0, int(active_positions_max or 0))
        and current >= trigger
    )
    progress = (
        _recovery_progress(
            current_drawdown=current,
            episode_peak_drawdown=peak,
            trigger_drawdown=trigger,
        )
        if eligible
        else 0.0
    )
    expected = before
    if eligible:
        floor_volume = minimum + math.floor(max(0, before - minimum) * progress)
        expected = min(before, max(minimum, floor_volume))
    after = expected
    applied = int(eligible and after != before)
    if not enabled:
        reason = "disabled"
    elif before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif active > max(0, int(active_positions_max or 0)):
        reason = "active_positions_above_stage010_limit"
    elif current < trigger:
        reason = "drawdown_below_stage010_trigger"
    elif applied:
        reason = "stage010_drawdown_recovery_progress_ramp"
    else:
        reason = "stage010_ramp_already_at_allowed_volume"
    return {
        "eligible": int(eligible),
        "applied": applied,
        "reason": reason,
        "selected_volume_before": before,
        "selected_volume_after": after,
        "expected_volume_after": expected,
        "reduced_volume": before - after,
        "recovery_progress": progress,
        "current_drawdown": current,
        "episode_peak_drawdown": peak,
        "trigger_drawdown": trigger,
        "active_positions_before": active,
        "active_positions_max": max(0, int(active_positions_max or 0)),
        "min_volume": minimum,
    }


def _ramp_audit(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            [
                {
                    "requested_start_month": "all",
                    "rows": 0,
                    "eligible_count": 0,
                    "applied_count": 0,
                    "formula_violation_count": 0,
                    "drawdown_below_trigger_count": 0,
                    "episode_peak_below_current_count": 0,
                    "progress_out_of_range_count": 0,
                    "active_positions_violation_count": 0,
                    "volume_bounds_violation_count": 0,
                }
            ]
        )
    data = frame.copy()
    numeric_columns = [
        column
        for column in data.columns
        if column.startswith("stage010_ramp_")
        and column not in {"stage010_ramp_reason"}
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    groups = (
        data.groupby("requested_start_month", dropna=False)
        if "requested_start_month" in data.columns
        else [("all", data)]
    )
    rows = []
    for start, part in groups:
        eligible = part["stage010_ramp_eligible"].eq(1)
        applied = part["stage010_ramp_applied"].eq(1)
        before = part["stage010_ramp_selected_volume_before"]
        after = part["stage010_ramp_selected_volume_after"]
        expected = part["stage010_ramp_expected_volume_after"]
        progress = part["stage010_ramp_recovery_progress"]
        current = part["stage010_ramp_current_drawdown"]
        peak = part["stage010_ramp_episode_peak_drawdown"]
        trigger = part["stage010_ramp_trigger_drawdown"]
        active = part["stage010_ramp_active_positions_before"]
        active_max = part["stage010_ramp_active_positions_max"]
        rows.append(
            {
                "requested_start_month": str(start),
                "rows": int(len(part)),
                "eligible_count": int(eligible.sum()),
                "applied_count": int(applied.sum()),
                "formula_violation_count": int((eligible & after.ne(expected)).sum()),
                "drawdown_below_trigger_count": int((eligible & current.lt(trigger - 1e-12)).sum()),
                "episode_peak_below_current_count": int((eligible & peak.lt(current - 1e-12)).sum()),
                "progress_out_of_range_count": int((eligible & ~progress.between(0.0, 1.0)).sum()),
                "active_positions_violation_count": int((eligible & active.gt(active_max)).sum()),
                "volume_bounds_violation_count": int((eligible & ((after.lt(1)) | after.gt(before))).sum()),
            }
        )
    return pd.DataFrame(rows)


def _ramp_semantics_pass(frame: pd.DataFrame) -> bool:
    violations = [column for column in frame.columns if column.endswith("_violation_count")]
    return bool(
        not frame.empty
        and pd.to_numeric(frame["eligible_count"], errors="coerce").fillna(0).sum() > 0
        and pd.to_numeric(frame["applied_count"], errors="coerce").fillna(0).sum() > 0
        and all(
            pd.to_numeric(frame[column], errors="coerce").fillna(1).eq(0).all()
            for column in violations
        )
    )


def _anchor_gate_row(
    *,
    requested_start_month: str,
    a: dict[str, Any],
    c: dict[str, Any],
    a_2022_account_history_drawdown: float,
    c_2022_account_history_drawdown: float,
) -> dict[str, Any]:
    a_return = float(a["total_return_pct"])
    c_return = float(c["total_return_pct"])
    retention = c_return / a_return if a_return > 0.0 else np.nan
    full_dd_improvement = float(c["max_drawdown_pct"]) - float(a["max_drawdown_pct"])
    year_dd_improvement = float(c_2022_account_history_drawdown) - float(
        a_2022_account_history_drawdown
    )
    broker_delta = float(c["max_broker10_margin_to_equity_pct"]) - float(
        a["max_broker10_margin_to_equity_pct"]
    )
    gates = {
        "c_positive_pass": c_return > 0.0,
        "return_retention_pass": bool(
            np.isfinite(retention) and retention >= RETURN_RETENTION_MIN
        ),
        "full_drawdown_pass": full_dd_improvement >= FULL_DD_IMPROVEMENT_MIN_PP,
        "account_history_2022_drawdown_pass": year_dd_improvement > 0.0,
        "broker10_pass": broker_delta <= 1e-9,
    }
    return {
        "requested_start_month": requested_start_month,
        "a_total_return_pct": a_return,
        "c_total_return_pct": c_return,
        "return_retention_ratio": retention,
        "a_max_drawdown_pct": float(a["max_drawdown_pct"]),
        "c_max_drawdown_pct": float(c["max_drawdown_pct"]),
        "full_drawdown_improvement_pp": full_dd_improvement,
        "a_account_history_2022_drawdown_pct": float(
            a_2022_account_history_drawdown
        ),
        "c_account_history_2022_drawdown_pct": float(
            c_2022_account_history_drawdown
        ),
        "account_history_2022_dd_improvement_pp": year_dd_improvement,
        "a_broker10_peak_pct": float(a["max_broker10_margin_to_equity_pct"]),
        "c_broker10_peak_pct": float(c["max_broker10_margin_to_equity_pct"]),
        "broker10_delta_pp": broker_delta,
        **gates,
        "anchor_performance_pass": bool(all(gates.values())),
    }


def _anchor_performance_pass(frame: pd.DataFrame) -> bool:
    return bool(
        len(frame) == len(ANCHOR_STARTS)
        and set(frame["requested_start_month"].astype(str))
        == {start.strftime("%Y-%m") for start in ANCHOR_STARTS}
        and frame["anchor_performance_pass"].astype(bool).all()
    )


class QmtRollPortfolioStrategyStage010RecoveryProgressRamp(
    s6.QmtRollPortfolioStrategyStage006ReconciledEquity
):
    enable_stage010_recovery_progress_ramp: bool = False
    stage010_trigger_drawdown: float = TRIGGER_DRAWDOWN
    stage010_active_positions_max: int = ACTIVE_POSITIONS_MAX
    stage010_min_volume: int = MIN_VOLUME

    parameters = s6.QmtRollPortfolioStrategyStage006ReconciledEquity.parameters + [
        "enable_stage010_recovery_progress_ramp",
        "stage010_trigger_drawdown",
        "stage010_active_positions_max",
        "stage010_min_volume",
    ]
    variables = s6.QmtRollPortfolioStrategyStage006ReconciledEquity.variables + [
        "stage010_episode_active",
        "stage010_episode_peak_drawdown",
        "stage010_ramp_evaluation_count",
        "stage010_ramp_applied_count",
    ]

    def __init__(
        self,
        strategy_engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict[str, Any],
    ) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage010_episode_active = False
        self.stage010_episode_peak_drawdown = 0.0
        self.stage010_ramp_evaluation_count = 0
        self.stage010_ramp_applied_count = 0

    def _stage010_refresh_episode(self) -> None:
        state = _update_episode_state(
            episode_active=bool(self.stage010_episode_active),
            episode_peak_drawdown=float(self.stage010_episode_peak_drawdown),
            current_drawdown=float(self.stage006_authoritative_drawdown_pct),
            trigger_drawdown=float(self.stage010_trigger_drawdown),
        )
        self.stage010_episode_active = bool(state["episode_active"])
        self.stage010_episode_peak_drawdown = float(
            state["episode_peak_drawdown"]
        )
        engine_datetime = getattr(self.strategy_engine, "datetime", None)
        self.trade_event_diagnostics.append(
            {
                "datetime": engine_datetime,
                "date": (
                    self._normalized_date(engine_datetime).date()
                    if engine_datetime is not None
                    else ""
                ),
                "vt_symbol": "",
                "product_vt_symbol": "",
                "direction": "",
                "offset": "Audit",
                "reason": EPISODE_DAILY_REASON,
                "volume": 0,
                "price": 0.0,
                "stage010_episode_active": int(self.stage010_episode_active),
                "stage010_episode_peak_drawdown": float(
                    self.stage010_episode_peak_drawdown
                ),
                "stage010_episode_current_drawdown": float(
                    self.stage006_authoritative_drawdown_pct
                ),
                "stage010_episode_trigger_drawdown": float(
                    self.stage010_trigger_drawdown
                ),
                "stage010_episode_authoritative_equity": float(
                    self.stage006_authoritative_equity
                ),
                "stage010_episode_authoritative_high_water": float(
                    self.stage006_authoritative_high_water
                ),
            }
        )

    def _stage010_event_from_plan(
        self,
        product_vt_symbol: str,
        plan: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        bar = plan.get("target_bar")
        bar_datetime = getattr(bar, "datetime", None)
        return {
            "datetime": bar_datetime,
            "date": (
                self._normalized_date(bar_datetime).date()
                if bar_datetime is not None
                else ""
            ),
            "vt_symbol": str(plan.get("target_contract") or ""),
            "contract_vt_symbol": str(plan.get("target_contract") or ""),
            "product_vt_symbol": product_vt_symbol,
            "direction": str(plan.get("direction") or ""),
            "position_direction": str(plan.get("direction") or ""),
            "offset": "Sizing",
            "reason": RAMP_REASON,
            "volume": int(fields["stage010_ramp_selected_volume_after"]),
            "price": float(getattr(bar, "close_price", 0.0) or 0.0),
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }

    def _plan_flat_entry_candidates(
        self, day_contexts: list[Any]
    ) -> dict[str, dict[str, Any]]:
        self._stage010_refresh_episode()
        base_class = (
            s6.stage001.stage013.s847.QmtRollPortfolioStrategyStage847C9StopRetry
        )
        plans = base_class._plan_flat_entry_candidates(self, day_contexts)
        if not self.enable_stage010_recovery_progress_ramp:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = dict(plan.get("sizing") or {})
            result = _evaluate_recovery_ramp(
                selected_volume_before=int(sizing.get("selected_volume") or 0),
                entry_context="flat_entry",
                active_positions_before=int(
                    plan.get("active_positions_before") or 0
                ),
                current_drawdown=float(
                    self.stage006_authoritative_drawdown_pct
                ),
                episode_peak_drawdown=float(
                    self.stage010_episode_peak_drawdown
                ),
                enabled=bool(self.enable_stage010_recovery_progress_ramp),
                trigger_drawdown=float(self.stage010_trigger_drawdown),
                active_positions_max=int(self.stage010_active_positions_max),
                min_volume=int(self.stage010_min_volume),
            )
            fields = {
                f"stage010_ramp_{key}": value for key, value in result.items()
            }
            fields.update(
                {
                    "stage006_authoritative_equity": float(
                        self.stage006_authoritative_equity
                    ),
                    "stage006_authoritative_high_water": float(
                        self.stage006_authoritative_high_water
                    ),
                    "stage006_authoritative_drawdown_pct": float(
                        self.stage006_authoritative_drawdown_pct
                    ),
                    "stage006_legacy_equity": float(
                        self.stage006_legacy_equity_at_close
                    ),
                    "stage006_cumulative_duplicate_pnl": float(
                        self.stage006_cumulative_duplicate_pnl
                    ),
                }
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(result["eligible"]) != 1:
                continue

            selected_after = int(result["selected_volume_after"])
            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            event = self._stage010_event_from_plan(
                str(product_vt_symbol), plan, fields
            )
            self.trade_event_diagnostics.append(event)
            self.stage010_ramp_evaluation_count += 1
            self.stage010_ramp_applied_count += int(result["applied"])
        return plans


def _eligibility(
    strategy_name: str, score_type: str, version: str
) -> tuple[pd.DataFrame, Path]:
    frame = s6.stage001.source.s006._official_eligibility_for_strategy(
        strategy_name, score_type
    )
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _candidate_profile(
    metadata: dict[str, Any], eligibility_path: Path
) -> dict[str, Any]:
    profile = s6._candidate_profile(metadata, eligibility_path)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=C_VERSION,
        label="C current AI Stage010 drawdown recovery-progress ramp",
        note=(
            f"{spec.capital.note} | Stage010 isolated research candidate. "
            "Deep-drawdown flat entries use a parameter-free recovery-progress ramp; "
            "no product/date/direction/AI-quality exception."
        ),
    )
    overrides = {
        **spec.overrides,
        "ai_product_pool_strategy": C_STRATEGY,
        "enable_stage013_account_state_pilot_gate": False,
        "enable_stage010_recovery_progress_ramp": True,
        "stage010_trigger_drawdown": TRIGGER_DRAWDOWN,
        "stage010_active_positions_max": ACTIVE_POSITIONS_MAX,
        "stage010_min_volume": MIN_VOLUME,
    }
    result = dict(profile)
    result["profile"] = C_VERSION
    result["strategy_cls"] = QmtRollPortfolioStrategyStage010RecoveryProgressRamp
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides=overrides,
        profile=C_VERSION,
    )
    return result


def _tag(frame: pd.DataFrame, start: pd.Timestamp, version: str) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        return result
    result["start_month"] = start.strftime("%Y-%m")
    result["requested_start_month"] = start.strftime("%Y-%m")
    result["requested_end"] = REQUESTED_END.date().isoformat()
    result["version"] = version
    result["stage"] = STAGE_LABEL
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    return result


def _run_arm(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    with s7._requested_window(start):
        daily, frames = s6.stage001._run(metadata, profile, version)
    daily = _tag(daily, start, version)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    reason = trade_events.get("reason", pd.Series(dtype=str)).astype(str)
    if version == C_VERSION and not trade_events.empty:
        frames["stage006_equity_daily"] = trade_events[
            reason.eq(s6.DAILY_REASON)
        ].copy()
        frames["stage006_trade_corrections"] = trade_events[
            reason.eq(s6.CORRECTION_REASON)
        ].copy()
        frames["stage010_ramp_events"] = trade_events[
            reason.eq(RAMP_REASON)
        ].copy()
        frames["stage010_episode_daily"] = trade_events[
            reason.eq(EPISODE_DAILY_REASON)
        ].copy()
    else:
        frames["stage006_equity_daily"] = pd.DataFrame()
        frames["stage006_trade_corrections"] = pd.DataFrame()
        frames["stage010_ramp_events"] = pd.DataFrame()
        frames["stage010_episode_daily"] = pd.DataFrame()
    return daily, {
        name: _tag(frame, start, version) for name, frame in frames.items()
    }


def _summary_arm(
    metadata: dict[str, Any],
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    version: str,
    start: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    row, curve, closed = s6._summary_row(version, daily, frames, metadata)
    row.update(
        {
            "version": version,
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start_month": start.strftime("%Y-%m"),
            "requested_end": REQUESTED_END.date().isoformat(),
        }
    )
    return row, _tag(curve, start, version), _tag(closed, start, version)


def _save_arm(
    start: pd.Timestamp,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{start.strftime('%Y-%m')}_{version}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    if not closed.empty:
        closed.to_csv(
            OUT / f"{prefix}_closed_lots_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )
    for name in SAVE_FRAME_NAMES:
        frame = frames.get(name, pd.DataFrame())
        if frame.empty:
            continue
        frame.to_csv(
            OUT / f"{prefix}_{name}_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )


CORE_DAILY_COLUMNS = (
    "date",
    "trade_count",
    "turnover",
    "commission",
    "slippage",
    "trading_pnl",
    "holding_pnl",
    "total_pnl",
    "net_pnl",
    "total_net_pnl",
    "total_slippage",
    "account_equity",
    "total_margin_exact",
    "broker10_total_margin_exact",
    "broker10_margin_to_equity_pct",
)


def _a_reproduction(start: pd.Timestamp, current: pd.DataFrame) -> dict[str, Any]:
    start_month = start.strftime("%Y-%m")
    reference_path = s7.OUT / (
        f"{s7.OUTPUT_PREFIX}_{start_month}_{A_VERSION}_daily_{s7.MODEL_TAG}.csv.gz"
    )
    reference = pd.read_csv(reference_path, encoding="utf-8-sig")
    columns = [
        column
        for column in CORE_DAILY_COLUMNS
        if column in reference.columns and column in current.columns
    ]
    missing_columns = sorted(set(CORE_DAILY_COLUMNS) - set(columns))
    date_equal = bool(
        len(reference) == len(current)
        and reference["date"].astype(str).reset_index(drop=True).equals(
            current["date"].astype(str).reset_index(drop=True)
        )
    )
    numeric = [column for column in columns if column != "date"]
    if len(reference) == len(current) and numeric:
        max_difference = float(
            (
                reference[numeric].apply(pd.to_numeric, errors="coerce")
                - current[numeric]
                .reset_index(drop=True)
                .apply(pd.to_numeric, errors="coerce")
            )
            .abs()
            .max()
            .max()
        )
    else:
        max_difference = float("inf")
    return {
        "requested_start_month": start_month,
        "reference_path": str(reference_path),
        "reference_rows": int(len(reference)),
        "current_rows": int(len(current)),
        "date_equal": date_equal,
        "missing_core_column_count": int(len(missing_columns)),
        "missing_core_columns": "|".join(missing_columns),
        "max_core_daily_abs_difference": max_difference,
        "reproduction_pass": bool(
            date_equal and not missing_columns and max_difference <= 1e-9
        ),
    }


def _episode_daily_audit(
    daily: pd.DataFrame, frames: dict[str, pd.DataFrame], start: pd.Timestamp
) -> dict[str, Any]:
    official_dates = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    official_dates = official_dates.dropna().drop_duplicates().sort_values()
    events = frames.get("stage010_episode_daily", pd.DataFrame()).copy()
    start_month = start.strftime("%Y-%m")
    if events.empty:
        return {
            "requested_start_month": start_month,
            "official_rows": int(len(official_dates)),
            "raw_episode_rows": 0,
            "episode_daily_pass": False,
        }
    events["_date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events = events.dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)
    raw_rows = int(len(events))
    duplicate_count = int(events["_date"].duplicated(keep=False).sum())
    official_set = set(official_dates)
    official_start = pd.Timestamp(official_dates.min())
    official_end = pd.Timestamp(official_dates.max())
    in_range = events[events["_date"].isin(official_set)].copy()
    missing_count = int(len(official_set - set(in_range["_date"])))
    in_range_extra_count = int(
        len(
            events[
                events["_date"].between(official_start, official_end)
                & ~events["_date"].isin(official_set)
            ]
        )
    )
    post_end_count = int((events["_date"] > official_end).sum())
    pre_start = events[events["_date"] < official_start]
    pre_start_invalid_count = int(
        (
            pd.to_numeric(
                pre_start["stage010_episode_current_drawdown"], errors="coerce"
            ).abs()
            > 1e-12
        ).sum()
        + (
            pd.to_numeric(
                pre_start["stage010_episode_peak_drawdown"], errors="coerce"
            ).abs()
            > 1e-12
        ).sum()
        + pd.to_numeric(
            pre_start["stage010_episode_active"], errors="coerce"
        ).fillna(1).ne(0).sum()
    )
    expected_active = False
    expected_peak = 0.0
    state_violation_count = 0
    for row in events.itertuples(index=False):
        current = float(row.stage010_episode_current_drawdown)
        trigger = float(row.stage010_episode_trigger_drawdown)
        expected = _update_episode_state(
            episode_active=expected_active,
            episode_peak_drawdown=expected_peak,
            current_drawdown=current,
            trigger_drawdown=trigger,
        )
        expected_active = bool(expected["episode_active"])
        expected_peak = float(expected["episode_peak_drawdown"])
        if int(row.stage010_episode_active) != int(expected_active):
            state_violation_count += 1
        if abs(float(row.stage010_episode_peak_drawdown) - expected_peak) > 1e-12:
            state_violation_count += 1
    pass_value = bool(
        len(in_range) == len(official_dates)
        and duplicate_count == 0
        and missing_count == 0
        and in_range_extra_count == 0
        and post_end_count == 0
        and pre_start_invalid_count == 0
        and state_violation_count == 0
    )
    return {
        "requested_start_month": start_month,
        "official_rows": int(len(official_dates)),
        "raw_episode_rows": raw_rows,
        "in_range_episode_rows": int(len(in_range)),
        "pre_start_episode_rows": int(len(pre_start)),
        "pre_start_invalid_count": pre_start_invalid_count,
        "duplicate_date_count": duplicate_count,
        "missing_date_count": missing_count,
        "in_range_extra_count": in_range_extra_count,
        "post_end_count": post_end_count,
        "state_violation_count": state_violation_count,
        "episode_daily_pass": pass_value,
    }


def _candidate_event_coverage(
    candidates: pd.DataFrame,
    episode_daily: pd.DataFrame,
    events: pd.DataFrame,
) -> dict[str, int]:
    candidate_data = candidates.copy()
    episode_data = episode_daily.copy()
    event_data = events.copy()
    if candidate_data.empty or episode_data.empty:
        return {
            "candidate_eligible_count": 0,
            "event_count": int(len(event_data)),
            "candidate_event_mismatch_count": int(len(event_data)),
        }
    candidate_data["_date"] = pd.to_datetime(
        candidate_data["date"], errors="coerce"
    ).dt.normalize()
    episode_data["_date"] = pd.to_datetime(
        episode_data["date"], errors="coerce"
    ).dt.normalize()
    state = episode_data[
        ["_date", "stage010_episode_current_drawdown"]
    ].drop_duplicates("_date", keep="last")
    candidate_data = candidate_data.merge(state, on="_date", how="left")
    eligible = candidate_data[
        candidate_data["candidate_status"].astype(str).eq("opened")
        & candidate_data["entry_context"].astype(str).eq("flat_entry")
        & pd.to_numeric(
            candidate_data["active_positions_before"], errors="coerce"
        )
        .fillna(ACTIVE_POSITIONS_MAX + 1)
        .le(ACTIVE_POSITIONS_MAX)
        & pd.to_numeric(candidate_data["selected_volume"], errors="coerce")
        .fillna(0)
        .gt(0)
        & pd.to_numeric(
            candidate_data["stage010_episode_current_drawdown"], errors="coerce"
        )
        .fillna(-1.0)
        .ge(TRIGGER_DRAWDOWN - 1e-12)
    ].copy()
    eligible["_symbol"] = eligible["contract_vt_symbol"].astype(str)
    eligible["_direction"] = eligible["direction"].astype(str).str.lower()
    eligible["_signal"] = eligible["signal"].fillna("").astype(str)
    eligible["_after"] = pd.to_numeric(
        eligible["selected_volume"], errors="coerce"
    )

    if event_data.empty:
        mismatch = int(len(eligible))
    else:
        event_data["_date"] = pd.to_datetime(
            event_data["date"], errors="coerce"
        ).dt.normalize()
        event_data["_symbol"] = event_data["vt_symbol"].astype(str)
        event_data["_direction"] = event_data["direction"].astype(str).str.lower()
        event_data["_signal"] = event_data["signal"].fillna("").astype(str)
        event_data["_after"] = pd.to_numeric(
            event_data["stage010_ramp_selected_volume_after"], errors="coerce"
        )
        keys = ["_date", "_symbol", "_direction", "_signal", "_after"]
        candidate_counts = eligible.groupby(keys, dropna=False).size().rename("candidate")
        event_counts = event_data.groupby(keys, dropna=False).size().rename("event")
        compared = pd.concat([candidate_counts, event_counts], axis=1).fillna(0)
        mismatch = int((compared["candidate"] - compared["event"]).abs().sum())
    return {
        "candidate_eligible_count": int(len(eligible)),
        "event_count": int(len(event_data)),
        "candidate_event_mismatch_count": mismatch,
    }


def _ramp_audit_for_start(
    frames: dict[str, pd.DataFrame], start: pd.Timestamp
) -> pd.DataFrame:
    events = frames.get("stage010_ramp_events", pd.DataFrame()).copy()
    audit = _ramp_audit(events)
    audit["requested_start_month"] = start.strftime("%Y-%m")
    candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    coverage = _candidate_event_coverage(
        candidates,
        frames.get("stage010_episode_daily", pd.DataFrame()),
        events,
    )
    audit["candidate_eligible_count"] = coverage["candidate_eligible_count"]
    audit["event_count"] = coverage["event_count"]
    audit["candidate_event_count_mismatch_violation_count"] = coverage[
        "candidate_event_mismatch_count"
    ]
    if events.empty:
        audit["event_authoritative_dd_mismatch_violation_count"] = 0
    else:
        audit["event_authoritative_dd_mismatch_violation_count"] = int(
            (
                pd.to_numeric(
                    events["stage010_ramp_current_drawdown"], errors="coerce"
                )
                - pd.to_numeric(
                    events["stage006_authoritative_drawdown_pct"], errors="coerce"
                )
            )
            .abs()
            .gt(1e-12)
            .sum()
        )
    return audit


def _all_reconciliations_pass(frame: pd.DataFrame) -> bool:
    zero_columns = (
        "missing_date_count",
        "duplicate_date_count",
        "pre_start_invalid_count",
        "in_range_extra_audit_count",
        "post_end_audit_count",
        "future_trade_violation_count",
    )
    return bool(
        len(frame) == len(ANCHOR_STARTS)
        and frame["reconciliation_pass"].astype(bool).all()
        and all(
            pd.to_numeric(frame[column], errors="coerce").fillna(1).eq(0).all()
            for column in zero_columns
        )
    )


def _all_episode_audits_pass(frame: pd.DataFrame) -> bool:
    return bool(
        len(frame) == len(ANCHOR_STARTS)
        and frame["episode_daily_pass"].astype(bool).all()
    )


def _window_rows(
    daily_by_key: dict[tuple[str, str], pd.DataFrame]
) -> pd.DataFrame:
    rows = []
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        for version in VERSIONS:
            metrics = s9._window_drawdown_metrics(
                daily_by_key[(start_month, version)],
                start=s9.YEAR_2022_START,
                end=s9.YEAR_2022_END,
            )
            rows.append(
                {
                    "requested_start_month": start_month,
                    "version": version,
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def _anchor_pairs(summary: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fixed = pd.read_csv(s7.PAIR_PATH, encoding="utf-8-sig")
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        group = summary[summary["requested_start_month"].eq(start_month)]
        a = group[group["version"].eq(A_VERSION)].iloc[0].to_dict()
        c = group[group["version"].eq(C_VERSION)].iloc[0].to_dict()
        window = windows[windows["requested_start_month"].eq(start_month)]
        aw = window[window["version"].eq(A_VERSION)].iloc[0]
        cw = window[window["version"].eq(C_VERSION)].iloc[0]
        row = _anchor_gate_row(
            requested_start_month=start_month,
            a=a,
            c=c,
            a_2022_account_history_drawdown=float(
                aw["account_history_max_drawdown_pct"]
            ),
            c_2022_account_history_drawdown=float(
                cw["account_history_max_drawdown_pct"]
            ),
        )
        row.update(
            {
                "a_local_reset_2022_drawdown_pct": float(
                    aw["local_window_reset_max_drawdown_pct"]
                ),
                "c_local_reset_2022_drawdown_pct": float(
                    cw["local_window_reset_max_drawdown_pct"]
                ),
                "local_reset_2022_dd_improvement_pp": float(
                    cw["local_window_reset_max_drawdown_pct"]
                    - aw["local_window_reset_max_drawdown_pct"]
                ),
            }
        )
        fixed_row = fixed[
            fixed["requested_start_month"].eq(start_month)
        ].iloc[0]
        row.update(
            {
                "fixed1_c_total_return_pct": float(
                    fixed_row["c_total_return_pct"]
                ),
                "fixed1_return_retention_ratio": float(
                    fixed_row["return_retention_ratio"]
                ),
                "fixed1_c_max_drawdown_pct": float(
                    fixed_row["c_max_drawdown_pct"]
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _ai_parity(
    eligibility: dict[str, pd.DataFrame], paths: dict[str, Path]
) -> pd.DataFrame:
    rows = []
    for version in VERSIONS:
        frame = eligibility[version]
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "eval_date_count": int(frame["eval_date"].nunique()),
                "normalized_sha256": s6.stage001.source._normalized_ai_hash(frame),
                "eligibility_sha256": s9._sha256(paths[version]),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(
        result["normalized_sha256"].nunique() == 1
    )
    return result


def _ai_usage_pass(frame: pd.DataFrame) -> bool:
    usage = pd.to_numeric(frame["ai_usage_rows"], errors="coerce").fillna(0)
    enabled = pd.to_numeric(frame["ai_enabled_rows"], errors="coerce").fillna(0)
    missing = pd.to_numeric(
        frame["missing_signal_date_rows"], errors="coerce"
    ).fillna(1)
    return bool(
        len(frame) == len(ANCHOR_STARTS) * len(VERSIONS)
        and usage.eq(enabled).all()
        and missing.eq(0).all()
    )


def _plot(curves: pd.DataFrame, pairs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, len(ANCHOR_STARTS), figsize=(18, 9))
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    labels = {A_VERSION: "A current C9", C_VERSION: "C recovery ramp"}
    for column, start in enumerate(ANCHOR_STARTS):
        start_month = start.strftime("%Y-%m")
        subset = curves[curves["requested_start_month"].eq(start_month)]
        for version in VERSIONS:
            group = subset[subset["version"].eq(version)].sort_values("date")
            dates = pd.to_datetime(group["date"], errors="coerce")
            equity_column = (
                "account_equity_for_metrics"
                if "account_equity_for_metrics" in group.columns
                else "account_equity"
            )
            equity = pd.to_numeric(group[equity_column], errors="coerce").ffill()
            axes[0, column].plot(
                dates,
                equity / float(s7.CAPITAL),
                color=colors[version],
                label=labels[version],
                linewidth=1.0,
            )
            axes[1, column].plot(
                dates,
                s6.stage001.source.s006.base._drawdown_pct(equity),
                color=colors[version],
                label=labels[version],
                linewidth=0.9,
            )
        pair = pairs[pairs["requested_start_month"].eq(start_month)].iloc[0]
        axes[0, column].set_title(
            f"{start_month}: ret A {pair['a_total_return_pct']:.1f}% / C {pair['c_total_return_pct']:.1f}%\n"
            f"retention {pair['return_retention_ratio'] * 100.0:.1f}%"
        )
        axes[1, column].set_title(
            f"DD A {pair['a_max_drawdown_pct']:.1f}% / C {pair['c_max_drawdown_pct']:.1f}%\n"
            f"2022 history-HWM improve {pair['account_history_2022_dd_improvement_pp']:.2f}pp"
        )
        axes[0, column].axhline(1.0, color="#94a3b8", linestyle=":", linewidth=0.7)
        axes[1, column].axhline(0.0, color="#94a3b8", linestyle=":", linewidth=0.7)
        axes[0, column].grid(alpha=0.22)
        axes[1, column].grid(alpha=0.22)
        axes[0, column].legend(fontsize=8)
        axes[1, column].legend(fontsize=8)
    axes[0, 0].set_ylabel("normalized account equity")
    axes[1, 0].set_ylabel("drawdown %")
    fig.suptitle("Stage010 drawdown recovery-progress ramp anchor A/C")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path != MANIFEST_PATH:
            rows.append(
                {
                    "file": path.name,
                    "bytes": int(path.stat().st_size),
                    "sha256": s9._sha256(path),
                }
            )
    return pd.DataFrame(rows)


def _lineage(
    metadata: dict[str, Any], source_manifest_audit: dict[str, Any]
) -> dict[str, Any]:
    paths = {
        "stage010_tool": Path(__file__).resolve(),
        "stage010_test": TOOLS_DIR / "test_stage010_drawdown_recovery_progress_ramp.py",
        "stage009_tool": Path(s9.__file__).resolve(),
        "stage007_tool": Path(s7.__file__).resolve(),
        "stage006_tool": Path(s6.__file__).resolve(),
        "stage007_manifest": s7.MANIFEST_PATH,
        "official_ai": s6.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    }
    metadata_hashes = {}
    for key in (
        "vt_symbols",
        "rates",
        "slippages",
        "sizes",
        "priceticks",
        "margin_ratios",
    ):
        payload = json.dumps(
            metadata.get(key, {}),
            default=str,
            sort_keys=True,
            ensure_ascii=True,
        )
        metadata_hashes[key] = {
            "rows": int(len(metadata.get(key, {}))),
            "sha256": hashlib.sha256(payload.encode("ascii")).hexdigest(),
        }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "inputs": {
            name: {
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": s9._sha256(path),
            }
            for name, path in paths.items()
        },
        "source_stage007_manifest_audit": source_manifest_audit,
        "metadata_hashes": metadata_hashes,
        "history_database_snapshot_complete": False,
    }


def _write_report(
    summary: pd.DataFrame,
    pairs: pd.DataFrame,
    windows: pd.DataFrame,
    reproduction: pd.DataFrame,
    reconciliation: pd.DataFrame,
    ramp_audit: pd.DataFrame,
    episode_audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage010 低水位恢复进度连续释放锚点 A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 绩效门：`{decision['performance_ok']}`
- 语义门：`{decision['semantics_ok']}`
- 公式：`after=min(before, 1+floor((before-1)*progress))`，其中 `progress=(episode_peak_dd-current_dd)/(episode_peak_dd-30%)`。
- 回撤主口径：账户从独立起点开始的历史高水位；local-reset 仅作对照。
- 独立 review：待完成。

## 锚点硬门

{pairs.to_markdown(index=False)}

## 分臂汇总

{summary.to_markdown(index=False)}

## 2022 双口径

{windows.to_markdown(index=False)}

## A 复现

{reproduction.to_markdown(index=False)}

## 权威权益 reconciliation

{reconciliation.to_markdown(index=False)}

## Ramp 语义

{ramp_audit.to_markdown(index=False)}

## Episode 每日状态

{episode_audit.to_markdown(index=False)}

## AI parity

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    source_manifest_audit = s9._verify_manifest(s7.OUT, s7.MANIFEST_PATH)
    if not source_manifest_audit["pass"]:
        raise RuntimeError(
            f"Stage007 source manifest verification failed: {source_manifest_audit}"
        )

    metadata = s6.stage001.source._metadata()
    a_eligibility, a_path = _eligibility(A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(C_STRATEGY, C_VERSION, C_VERSION)
    profiles = {
        A_VERSION: s6.stage001._a_profile(metadata, a_path),
        C_VERSION: _candidate_profile(metadata, c_path),
    }
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    eligibility_paths = {A_VERSION: a_path, C_VERSION: c_path}

    daily_by_key: dict[tuple[str, str], pd.DataFrame] = {}
    frames_by_key: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}
    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    reproduction_rows = []
    reconciliation_parts = []
    ramp_parts = []
    episode_rows = []
    ai_usage_rows = []
    stage013_event_count = 0

    run_count = len(ANCHOR_STARTS) * len(VERSIONS)
    run_index = 0
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        for version in VERSIONS:
            run_index += 1
            print(
                f"[stage010] run {run_index}/{run_count} start={start_month} version={version}",
                flush=True,
            )
            daily, frames = _run_arm(
                metadata, profiles[version], version, start
            )
            row, curve, closed = _summary_arm(
                metadata, daily, frames, version, start
            )
            _save_arm(start, version, daily, frames, closed)
            daily_by_key[(start_month, version)] = daily
            frames_by_key[(start_month, version)] = frames
            summary_rows.append(row)
            curves.append(curve)
            ai_usage_rows.append(s7._ai_usage_row(frames, version, start))

            if version == A_VERSION:
                reproduction_rows.append(_a_reproduction(start, daily))
            else:
                reconciliation = s6._equity_reconciliation(daily, frames)
                reconciliation["requested_start_month"] = start_month
                reconciliation_parts.append(reconciliation)
                ramp_parts.append(_ramp_audit_for_start(frames, start))
                episode_rows.append(_episode_daily_audit(daily, frames, start))
                trade_events = frames.get("trade_events", pd.DataFrame())
                if not trade_events.empty:
                    stage013_event_count += int(
                        trade_events["reason"]
                        .astype(str)
                        .eq("stage013_account_state_pilot_gate")
                        .sum()
                    )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    reproduction = pd.DataFrame(reproduction_rows).sort_values(
        "requested_start_month"
    )
    reconciliation = pd.concat(
        reconciliation_parts, ignore_index=True, sort=False
    )
    ramp_audit = pd.concat(ramp_parts, ignore_index=True, sort=False)
    episode_audit = pd.DataFrame(episode_rows).sort_values(
        "requested_start_month"
    )
    ai_usage = pd.DataFrame(ai_usage_rows).sort_values(
        ["requested_start_month", "version"]
    )
    ai_parity = _ai_parity(eligibility, eligibility_paths)
    windows = _window_rows(daily_by_key)
    pairs = _anchor_pairs(summary, windows)

    reproduction_ok = bool(
        len(reproduction) == len(ANCHOR_STARTS)
        and reproduction["reproduction_pass"].astype(bool).all()
    )
    reconciliation_ok = _all_reconciliations_pass(reconciliation)
    ramp_ok = bool(
        len(ramp_audit) == len(ANCHOR_STARTS)
        and _ramp_semantics_pass(ramp_audit)
    )
    episode_ok = _all_episode_audits_pass(episode_audit)
    ai_parity_ok = bool(ai_parity["all_normalized_equal"].eq(1).all())
    ai_usage_ok = _ai_usage_pass(ai_usage)
    stage013_disabled_ok = stage013_event_count == 0
    semantics_ok = bool(
        reproduction_ok
        and reconciliation_ok
        and ramp_ok
        and episode_ok
        and ai_parity_ok
        and ai_usage_ok
        and stage013_disabled_ok
        and source_manifest_audit["pass"]
    )
    performance_ok = _anchor_performance_pass(pairs)
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "anchor_starts": [start.strftime("%Y-%m") for start in ANCHOR_STARTS],
        "requested_end": REQUESTED_END.date().isoformat(),
        "formula": "after=min(before,1+floor((before-1)*clip((episode_peak_dd-current_dd)/(episode_peak_dd-0.30),0,1)))",
        "source_stage007_manifest_pass": bool(source_manifest_audit["pass"]),
        "a_reproduction_ok": reproduction_ok,
        "all_reconciliations_ok": reconciliation_ok,
        "ramp_semantics_ok": ramp_ok,
        "episode_daily_state_ok": episode_ok,
        "ai_parity_ok": ai_parity_ok,
        "ai_usage_ok": ai_usage_ok,
        "stage013_fixed1_disabled_ok": stage013_disabled_ok,
        "stage013_event_count": int(stage013_event_count),
        "semantics_ok": semantics_ok,
        "performance_ok": performance_ok,
        "anchor_gates": pairs.to_dict("records"),
        "final_goal_complete": False,
        "final_goal_residual": (
            "anchor pass still requires 13-start and cost validation"
            if semantics_ok and performance_ok
            else "Stage010 anchor hard gate failed; formula must close without parameter rescue"
        ),
        "decision": (
            "stage010_anchor_pass_allow_halfyear"
            if semantics_ok and performance_ok
            else "stage010_anchor_fail_close_formula_no_parameter_rescue"
        ),
        "overfit_before": "low-to-medium: one parameter-free account-state formula after attribution",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: break fixed-one-contract recovery deadlock",
        "continue_value_after": "pending_independent_review",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    reproduction.to_csv(REPRODUCTION_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    ramp_audit.to_csv(RAMP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    episode_audit.to_csv(EPISODE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(s9._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    LINEAGE_PATH.write_text(
        json.dumps(
            s9._json_safe(_lineage(metadata, source_manifest_audit)),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame, pairs)
    _write_report(
        summary,
        pairs,
        windows,
        reproduction,
        reconciliation,
        ramp_audit,
        episode_audit,
        ai_parity,
        decision,
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "pairs": pairs,
        "windows": windows,
        "reproduction": reproduction,
        "reconciliation": reconciliation,
        "ramp_audit": ramp_audit,
        "episode_audit": episode_audit,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["pairs"].to_string(index=False))
    print(result["reconciliation"].to_string(index=False))
    print(result["ramp_audit"].to_string(index=False))
    print(result["episode_audit"].to_string(index=False))
    print(
        json.dumps(
            s9._json_safe(result["decision"]),
            ensure_ascii=False,
            indent=2,
        )
    )
