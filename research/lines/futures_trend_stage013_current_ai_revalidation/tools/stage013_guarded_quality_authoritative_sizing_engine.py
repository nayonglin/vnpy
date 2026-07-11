#!/usr/bin/env python3
"""Stage013: guarded quality add-risk on the authoritative-equity engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
ROOT = Path(__file__).resolve().parents[4]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_gate_opportunity_cost_attribution as s9  # noqa: E402
import stage010_drawdown_recovery_progress_ramp as s10  # noqa: E402
import stage011_2021_anchor_path_feedback_attribution as s11  # noqa: E402
import stage012_global_authoritative_equity_sizing_engine as s12  # noqa: E402


STAGE_LABEL = "Stage013"
STAGE_ID = "stage013_guarded_quality_authoritative_sizing_engine"
MODEL_TAG = f"{STAGE_ID}_v1"
LINE_ID = "futures_trend_stage013_current_ai_revalidation"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = s12.A_VERSION
B_VERSION = s12.C_VERSION
C_VERSION = "c_current_ai_stage013_authoritative_guarded_quality25"
VERSIONS = (A_VERSION, B_VERSION, C_VERSION)
C_STRATEGY = "stage013_authoritative_guarded_quality25"
ANCHOR_STARTS = s12.ANCHOR_STARTS
REQUESTED_END = s12.REQUESTED_END

QUALITY_REASON = "stage013_authoritative_guarded_quality25_floor"
QUALITY_ADD_FRACTION = 0.25
QUALITY_AI_RANK_MIN = 1
QUALITY_AI_RANK_MAX = 8
QUALITY_RISK_MULTIPLIER_MAX_EXCLUSIVE = 2.0

UPSTREAM_LINE = ROOT / "research/lines/futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_GUARD_TOOL = UPSTREAM_LINE / "tools/stage013_guarded_quality_add_risk_proxy.py"
UPSTREAM_GUARD_TEST = ROOT / "tests/test_rebuilt_c9_v2_stage013_guarded_quality_proxy.py"

OUT = LINE_DIR / "outputs" / STAGE_ID
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_gates_{MODEL_TAG}.csv"
WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_2022_drawdown_windows_{MODEL_TAG}.csv"
QUALITY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_quality_events_{MODEL_TAG}.csv.gz"
QUALITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_quality_audit_{MODEL_TAG}.csv"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_reconciliation_{MODEL_TAG}.csv"
IMMEDIATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_immediate_correction_audit_{MODEL_TAG}.csv"
SIZING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_sizing_alignment_audit_{MODEL_TAG}.csv.gz"
SIZING_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_sizing_alignment_summary_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_equity_drawdown_{MODEL_TAG}.png"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
TEST_PATH = TOOLS_DIR / "test_stage013_guarded_quality_authoritative_sizing_engine.py"

SAVE_FRAME_NAMES = (
    "entry_candidates",
    "trades",
    "trade_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
    "stage012_immediate_corrections",
    "stage013_quality_events",
    "stop_retry_events",
)


def _to_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_int(value: Any, default: int = 0) -> int:
    number = _to_float(value)
    return int(number) if np.isfinite(number) else default


def _guarded_quality_floor25(
    *, sizing: dict[str, Any], entry_context: str, enabled: bool
) -> tuple[int, dict[str, Any]]:
    before = max(0, _to_int(sizing.get("selected_volume"), 0))
    ai_rank = _to_float(sizing.get("ai_product_pool_rank"))
    risk_multiplier = _to_float(sizing.get("risk_multiplier"))
    after_candidate = int(np.floor(float(before) * (1.0 + QUALITY_ADD_FRACTION)))
    added_candidate = max(0, after_candidate - before)
    rank_hit = bool(
        np.isfinite(ai_rank)
        and QUALITY_AI_RANK_MIN <= ai_rank <= QUALITY_AI_RANK_MAX
    )
    risk_hit = bool(
        np.isfinite(risk_multiplier)
        and risk_multiplier < QUALITY_RISK_MULTIPLIER_MAX_EXCLUSIVE
    )

    after = before
    applied = 0
    if not enabled:
        reason = "disabled"
    elif before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif before <= 1:
        reason = "selected_volume_not_above_one"
    elif not rank_hit:
        reason = "ai_rank_outside_1_8"
    elif not risk_hit:
        reason = "risk_multiplier_not_below_2"
    elif added_candidate <= 0:
        reason = "floor25_no_integer_increment"
    else:
        after = after_candidate
        applied = 1
        reason = "guarded_quality_floor25"

    return after, {
        "stage013_quality_enabled": int(bool(enabled)),
        "stage013_quality_applied": applied,
        "stage013_quality_reason": reason,
        "stage013_quality_selected_before": before,
        "stage013_quality_selected_after": after,
        "stage013_quality_added_volume": after - before,
        "stage013_quality_candidate_added_volume": added_candidate,
        "stage013_quality_ai_rank": ai_rank,
        "stage013_quality_ai_rank_min": QUALITY_AI_RANK_MIN,
        "stage013_quality_ai_rank_max": QUALITY_AI_RANK_MAX,
        "stage013_quality_ai_rank_hit": int(rank_hit),
        "stage013_quality_risk_multiplier": risk_multiplier,
        "stage013_quality_risk_multiplier_max_exclusive": (
            QUALITY_RISK_MULTIPLIER_MAX_EXCLUSIVE
        ),
        "stage013_quality_risk_multiplier_hit": int(risk_hit),
        "stage013_quality_add_fraction": QUALITY_ADD_FRACTION,
    }


def _guarded_quality_before_final_risk_gates(
    *, sizing: dict[str, Any], entry_context: str, enabled: bool
) -> tuple[int, dict[str, Any]]:
    requested_after, fields = _guarded_quality_floor25(
        sizing=sizing,
        entry_context=entry_context,
        enabled=enabled,
    )
    before = int(fields["stage013_quality_selected_before"])
    cap_enabled = bool(_to_int(sizing.get("stage830_broker10_margin_cap_enabled"), 0))
    max_affordable = max(
        0,
        _to_int(
            sizing.get("stage830_margin_cap_max_affordable_volume"),
            before,
        ),
    )
    selected_after = requested_after
    if int(fields["stage013_quality_applied"]) and cap_enabled:
        selected_after = max(before, min(requested_after, max_affordable))

    equity = _to_float(sizing.get("sizing_equity"), 0.0)
    reserved_margin = _to_float(sizing.get("reserved_margin_before"), 0.0)
    margin_per_contract = _to_float(sizing.get("margin_per_contract"), 0.0)
    broker_multiplier = _to_float(
        sizing.get("stage830_broker_margin_multiplier"), 0.0
    )
    cap_ratio = _to_float(sizing.get("stage830_margin_cap_ratio"), np.inf)
    projected_after = (
        (reserved_margin + margin_per_contract * selected_after)
        * broker_multiplier
        / equity
        if equity > 0.0 and broker_multiplier > 0.0
        else np.nan
    )

    fields.update(
        {
            "stage013_quality_requested": int(
                fields["stage013_quality_applied"]
            ),
            "stage013_quality_requested_after": requested_after,
            "stage013_quality_pre_incremental_gate_after": selected_after,
            "stage013_quality_broker10_cap_enabled": int(cap_enabled),
            "stage013_quality_broker10_max_affordable_volume": max_affordable,
            "stage013_quality_broker10_clamped": int(
                selected_after < requested_after
            ),
            "stage013_quality_projected_broker10_after": projected_after,
            "stage013_quality_broker10_cap_ratio": cap_ratio,
        }
    )
    fields["stage013_quality_applied"] = int(selected_after > before)
    fields["stage013_quality_selected_after"] = selected_after
    fields["stage013_quality_added_volume"] = selected_after - before
    if int(fields["stage013_quality_requested"]) and selected_after <= before:
        fields["stage013_quality_reason"] = "broker10_cap_no_increment"
    return selected_after, fields


def _finalize_guarded_quality_after_final_risk_gates(
    *, sizing: dict[str, Any], candidate_status: str
) -> dict[str, Any]:
    fields = {
        key: value
        for key, value in sizing.items()
        if str(key).startswith("stage013_quality_")
    }
    if not fields:
        return fields

    before = max(0, _to_int(fields.get("stage013_quality_selected_before"), 0))
    final_selected = max(0, _to_int(sizing.get("selected_volume"), 0))
    requested = bool(_to_int(fields.get("stage013_quality_requested"), 0))
    survived = bool(
        requested
        and str(candidate_status or "") == "opened"
        and final_selected > before
    )
    fields["stage013_quality_applied"] = int(survived)
    fields["stage013_quality_selected_after"] = final_selected
    fields["stage013_quality_added_volume"] = (
        final_selected - before if survived else 0
    )
    if requested and str(candidate_status or "") != "opened":
        fields["stage013_quality_reason"] = "final_risk_gate_candidate_not_opened"
    elif requested and final_selected <= before:
        fields["stage013_quality_reason"] = "final_risk_gate_no_increment"
    elif survived:
        fields["stage013_quality_reason"] = "guarded_quality_floor25_after_risk_gates"

    equity = _to_float(sizing.get("sizing_equity"), 0.0)
    reserved_margin = _to_float(sizing.get("reserved_margin_before"), 0.0)
    margin_per_contract = _to_float(sizing.get("margin_per_contract"), 0.0)
    broker_multiplier = _to_float(
        sizing.get("stage830_broker_margin_multiplier"), 0.0
    )
    fields["stage013_quality_projected_broker10_after"] = (
        (reserved_margin + margin_per_contract * final_selected)
        * broker_multiplier
        / equity
        if equity > 0.0 and broker_multiplier > 0.0
        else np.nan
    )
    return fields


def _sizing_with_plan_fields(plan: dict[str, Any]) -> dict[str, Any]:
    sizing = dict(plan.get("sizing") or {})
    for key in ("selected_volume", "ai_product_pool_rank", "risk_multiplier"):
        if key not in sizing or pd.isna(sizing.get(key)):
            sizing[key] = plan.get(key)
    return sizing


def _quality_event_audit_pass(
    frame: pd.DataFrame, *, expected_starts: set[str]
) -> bool:
    if frame.empty or set(frame["requested_start_month"].astype(str)) != set(
        expected_starts
    ):
        return False
    before = pd.to_numeric(frame["stage013_quality_selected_before"], errors="coerce")
    requested_after = pd.to_numeric(
        frame["stage013_quality_requested_after"], errors="coerce"
    )
    pre_incremental_after = pd.to_numeric(
        frame["stage013_quality_pre_incremental_gate_after"], errors="coerce"
    )
    after = pd.to_numeric(frame["stage013_quality_selected_after"], errors="coerce")
    added = pd.to_numeric(frame["stage013_quality_added_volume"], errors="coerce")
    rank = pd.to_numeric(frame["stage013_quality_ai_rank"], errors="coerce")
    risk = pd.to_numeric(
        frame["stage013_quality_risk_multiplier"], errors="coerce"
    )
    expected_requested_after = np.floor(
        before * (1.0 + QUALITY_ADD_FRACTION)
    )
    broker_cap_enabled = pd.to_numeric(
        frame["stage013_quality_broker10_cap_enabled"], errors="coerce"
    ).eq(1)
    projected_broker10 = pd.to_numeric(
        frame["stage013_quality_projected_broker10_after"], errors="coerce"
    )
    broker_cap_ratio = pd.to_numeric(
        frame["stage013_quality_broker10_cap_ratio"], errors="coerce"
    )
    broker_cap_ok = bool(
        (
            ~broker_cap_enabled
            | (
                projected_broker10.notna()
                & broker_cap_ratio.notna()
                & projected_broker10.le(broker_cap_ratio + 1e-12)
            )
        ).all()
    )
    return bool(
        pd.to_numeric(frame["stage013_quality_enabled"], errors="coerce")
        .eq(1)
        .all()
        and pd.to_numeric(frame["stage013_quality_applied"], errors="coerce")
        .eq(1)
        .all()
        and before.gt(1).all()
        and requested_after.eq(expected_requested_after).all()
        and pre_incremental_after.gt(before).all()
        and pre_incremental_after.le(requested_after).all()
        and after.gt(before).all()
        and after.le(pre_incremental_after).all()
        and added.eq(after - before).all()
        and added.gt(0).all()
        and rank.between(QUALITY_AI_RANK_MIN, QUALITY_AI_RANK_MAX).all()
        and risk.lt(QUALITY_RISK_MULTIPLIER_MAX_EXCLUSIVE).all()
        and frame["entry_context"].astype(str).eq("flat_entry").all()
        and frame["candidate_status_after"].astype(str).eq("opened").all()
        and broker_cap_ok
    )


class QmtRollPortfolioStrategyStage013GuardedQualityAuthoritativeSizing(
    s12.QmtRollPortfolioStrategyStage012GlobalAuthoritativeEquitySizing
):
    enable_stage013_guarded_quality_authoritative_sizing: bool = False

    parameters = (
        s12.QmtRollPortfolioStrategyStage012GlobalAuthoritativeEquitySizing.parameters
        + ["enable_stage013_guarded_quality_authoritative_sizing"]
    )
    variables = (
        s12.QmtRollPortfolioStrategyStage012GlobalAuthoritativeEquitySizing.variables
        + ["stage013_quality_event_count", "stage013_quality_added_volume"]
    )

    def __init__(
        self,
        strategy_engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict[str, Any],
    ) -> None:
        self.stage013_quality_event_count = 0
        self.stage013_quality_added_volume = 0
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

    def _apply_selection_pairwise_volume_tilt(
        self, opened_plans: list[dict[str, Any]]
    ) -> None:
        super()._apply_selection_pairwise_volume_tilt(opened_plans)
        if not self.enable_stage013_guarded_quality_authoritative_sizing:
            return

        for plan in opened_plans:
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = _sizing_with_plan_fields(plan)
            sizing.setdefault(
                "stage830_margin_cap_ratio",
                float(
                    getattr(
                        self,
                        "stage830_projected_broker10_margin_to_equity_cap",
                        np.inf,
                    )
                ),
            )
            selected_after, fields = _guarded_quality_before_final_risk_gates(
                sizing=sizing,
                entry_context="flat_entry",
                enabled=True,
            )
            sizing.update(fields)
            sizing["selected_volume"] = selected_after
            plan["sizing"] = sizing
            plan["volume"] = selected_after

    def _plan_flat_entry_candidates(
        self, day_contexts: list[Any]
    ) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage013_guarded_quality_authoritative_sizing:
            return plans

        for product_vt_symbol, plan in plans.items():
            sizing = _sizing_with_plan_fields(plan)
            fields = _finalize_guarded_quality_after_final_risk_gates(
                sizing=sizing,
                candidate_status=str(plan.get("candidate_status") or ""),
            )
            if not fields:
                continue
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage013_quality_applied"]) != 1:
                continue

            event = self._quality_event_from_plan(
                str(product_vt_symbol), plan, fields
            )
            self.trade_event_diagnostics.append(event)
            self.stage013_quality_event_count += 1
            self.stage013_quality_added_volume += int(
                fields["stage013_quality_added_volume"]
            )
        return plans

    @staticmethod
    def _quality_event_from_plan(
        product_vt_symbol: str,
        plan: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        bar = plan.get("target_bar")
        sizing = dict(plan.get("sizing") or {})
        bar_datetime = getattr(bar, "datetime", None)
        return {
            "datetime": bar_datetime,
            "date": (
                pd.Timestamp(bar_datetime).date() if bar_datetime is not None else ""
            ),
            "vt_symbol": str(plan.get("target_contract") or ""),
            "contract_vt_symbol": str(plan.get("target_contract") or ""),
            "product_vt_symbol": product_vt_symbol,
            "direction": str(plan.get("direction") or ""),
            "offset": "Sizing",
            "reason": QUALITY_REASON,
            "volume": int(fields["stage013_quality_selected_after"]),
            "price": float(getattr(bar, "close_price", 0.0) or 0.0),
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "ai_product_pool_signal_date": str(
                sizing.get("ai_product_pool_signal_date") or ""
            ),
            "ai_product_pool_entry_effective_date": str(
                sizing.get("ai_product_pool_entry_effective_date") or ""
            ),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            **fields,
        }


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


def _source_arm_path(start: pd.Timestamp, version: str, kind: str) -> Path:
    prefix = f"{s12.OUTPUT_PREFIX}_{start.strftime('%Y-%m')}_{version}"
    return s12.OUT / f"{prefix}_{kind}_{s12.MODEL_TAG}.csv.gz"


def _source_eligibility_path(version: str) -> Path:
    return s12.OUT / (
        f"{s12.OUTPUT_PREFIX}_{version}_eligibility_{s12.MODEL_TAG}.csv"
    )


def _load_source_arm(
    start: pd.Timestamp, version: str
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    daily = pd.read_csv(_source_arm_path(start, version, "daily"))
    closed = pd.read_csv(_source_arm_path(start, version, "closed_lots"))
    frames: dict[str, pd.DataFrame] = {}
    for name in ("entry_candidates", "trades", "trade_events", "stop_retry_events"):
        path = _source_arm_path(start, version, name)
        frames[name] = pd.read_csv(path) if path.exists() else pd.DataFrame()
    return (
        _tag(daily, start, version),
        {name: _tag(frame, start, version) for name, frame in frames.items()},
        _tag(closed, start, version),
    )


def _candidate_eligibility() -> tuple[pd.DataFrame, Path]:
    frame = s12.s6.stage001.source.s006._official_eligibility_for_strategy(
        C_STRATEGY, C_VERSION
    )
    path = OUT / f"{OUTPUT_PREFIX}_{C_VERSION}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _candidate_profile(
    metadata: dict[str, Any], eligibility_path: Path
) -> dict[str, Any]:
    profile = s12._candidate_profile(metadata, eligibility_path)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=C_VERSION,
        label="C authoritative sizing plus guarded quality 25% floor",
        note=(
            f"{spec.capital.note} | Stage013 isolated frozen guarded-quality leg. "
            "AI rank 1-8, selected volume above one and risk multiplier below two "
            "receive floor 25% integer risk on the corrected account ledger."
        ),
    )
    overrides = {
        **spec.overrides,
        "ai_product_pool_strategy": C_STRATEGY,
        "enable_stage013_account_state_pilot_gate": False,
        "enable_stage012_global_authoritative_equity_sizing": True,
        "enable_stage013_guarded_quality_authoritative_sizing": True,
    }
    result = dict(profile)
    result["profile"] = C_VERSION
    result["strategy_cls"] = (
        QmtRollPortfolioStrategyStage013GuardedQualityAuthoritativeSizing
    )
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides=overrides,
        profile=C_VERSION,
    )
    return result


def _run_c(
    metadata: dict[str, Any], profile: dict[str, Any], start: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    with s12.s7._requested_window(start):
        daily, frames = s12.s6.stage001._run(metadata, profile, C_VERSION)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    reason = trade_events.get("reason", pd.Series(dtype=str)).astype(str)
    frames["stage006_equity_daily"] = trade_events[
        reason.eq(s12.s6.DAILY_REASON)
    ].copy()
    frames["stage006_trade_corrections"] = trade_events[
        reason.eq(s12.s6.CORRECTION_REASON)
    ].copy()
    frames["stage012_immediate_corrections"] = trade_events[
        reason.eq(s12.IMMEDIATE_REASON)
    ].copy()
    frames["stage013_quality_events"] = trade_events[
        reason.eq(QUALITY_REASON)
    ].copy()
    closed = s12.s6.stage001.source._closed_lots(frames, metadata)
    return (
        _tag(daily, start, C_VERSION),
        {name: _tag(frame, start, C_VERSION) for name, frame in frames.items()},
        _tag(closed, start, C_VERSION),
    )


def _summary(
    daily: pd.DataFrame,
    closed: pd.DataFrame,
    version: str,
    start: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame]:
    curve = s12.s6.stage001.source.s006.base._curve_for_metrics(daily, version)
    row = s12.s6.stage001.source.s006._summarize_curve(curve)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "version": version,
            "requested_start_month": start.strftime("%Y-%m"),
            "requested_end": REQUESTED_END.date().isoformat(),
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    return row, _tag(curve, start, version)


def _save_c(
    start: pd.Timestamp,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{start.strftime('%Y-%m')}_{C_VERSION}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
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


def _quality_audit(
    events: pd.DataFrame, candidates: pd.DataFrame, start: pd.Timestamp
) -> dict[str, Any]:
    start_month = start.strftime("%Y-%m")
    expected = {start_month}
    event_pass = _quality_event_audit_pass(events, expected_starts=expected)
    keys = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "ai_product_pool_signal_date",
    ]
    event_data = events.copy()
    candidate_data = candidates.copy()
    for frame in (event_data, candidate_data):
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date.astype(str)
        signal_dates = frame.get(
            "ai_product_pool_signal_date",
            pd.Series("", index=frame.index, dtype=str),
        )
        frame["ai_product_pool_signal_date"] = (
            pd.to_datetime(signal_dates, errors="coerce").dt.date.astype(str)
        )
        for key in keys[1:]:
            frame[key] = frame.get(key, "").astype(str)
    candidate_data = candidate_data[
        candidate_data.get("candidate_status", pd.Series(dtype=str))
        .astype(str)
        .eq("opened")
    ].copy()
    candidate_counts = (
        candidate_data.groupby(keys, dropna=False).size().rename("candidate_match_count")
    )
    candidate_volume = (
        candidate_data.groupby(keys, dropna=False)["selected_volume"]
        .first()
        .rename("candidate_selected_volume")
    )
    mapped = event_data.merge(
        pd.concat([candidate_counts, candidate_volume], axis=1).reset_index(),
        on=keys,
        how="left",
    )
    match_count = pd.to_numeric(
        mapped.get("candidate_match_count", pd.Series(dtype=float)), errors="coerce"
    ).fillna(0)
    mapped_volume = pd.to_numeric(
        mapped.get("candidate_selected_volume", pd.Series(dtype=float)), errors="coerce"
    )
    event_after = pd.to_numeric(
        mapped.get("stage013_quality_selected_after", pd.Series(dtype=float)),
        errors="coerce",
    )
    mapping_missing = int(match_count.ne(1).sum())
    volume_mismatch = int((mapped_volume - event_after).abs().gt(1e-12).sum())
    duplicate_event_keys = int(event_data.duplicated(keys, keep=False).sum())
    before = pd.to_numeric(
        event_data.get("stage013_quality_selected_before", pd.Series(dtype=float)),
        errors="coerce",
    )
    after = pd.to_numeric(
        event_data.get("stage013_quality_selected_after", pd.Series(dtype=float)),
        errors="coerce",
    )
    requested_after = pd.to_numeric(
        event_data.get("stage013_quality_requested_after", pd.Series(dtype=float)),
        errors="coerce",
    )
    formula_error = (
        float((requested_after - np.floor(before * 1.25)).abs().max())
        if len(event_data)
        else np.nan
    )
    return {
        "requested_start_month": start_month,
        "quality_event_count": int(len(event_data)),
        "quality_total_added_volume": int(
            pd.to_numeric(
                event_data.get(
                    "stage013_quality_added_volume", pd.Series(dtype=float)
                ),
                errors="coerce",
            ).sum()
        ),
        "quality_formula_max_abs_error": formula_error,
        "quality_duplicate_event_key_count": duplicate_event_keys,
        "quality_candidate_mapping_missing_or_ambiguous_count": mapping_missing,
        "quality_candidate_selected_volume_mismatch_count": volume_mismatch,
        "quality_event_formula_pass": event_pass,
        "quality_mapping_pass": bool(
            len(event_data) > 0
            and duplicate_event_keys == 0
            and mapping_missing == 0
            and volume_mismatch == 0
        ),
        "quality_audit_pass": bool(
            event_pass
            and len(event_data) > 0
            and duplicate_event_keys == 0
            and mapping_missing == 0
            and volume_mismatch == 0
        ),
    }


def _sizing_summary(audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start, part in audit.groupby("requested_start_month"):
        error = pd.to_numeric(
            part["legacy_minus_official_same_day"], errors="coerce"
        )
        identity = pd.to_numeric(
            part["official_daily_identity_error"], errors="coerce"
        )
        rows.append(
            {
                "requested_start_month": str(start),
                "candidate_day_count": int(len(part)),
                "max_sizing_equity_abs_error": float(error.abs().max()),
                "max_official_daily_identity_abs_error": float(
                    identity.abs().max()
                ),
                "all_candidate_days_aligned": bool(
                    error.notna().all()
                    and identity.notna().all()
                    and error.abs().le(1e-8).all()
                    and identity.abs().le(1e-8).all()
                ),
            }
        )
    return pd.DataFrame(rows)


def _windows(
    daily_by_key: dict[tuple[str, str], pd.DataFrame]
) -> pd.DataFrame:
    rows = []
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        for version in VERSIONS:
            rows.append(
                {
                    "requested_start_month": start_month,
                    "version": version,
                    **s9._window_drawdown_metrics(
                        daily_by_key[(start_month, version)],
                        start=s9.YEAR_2022_START,
                        end=s9.YEAR_2022_END,
                    ),
                }
            )
    return pd.DataFrame(rows)


def _pairs(summary: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        group = summary[summary["requested_start_month"].eq(start_month)]
        a = group[group["version"].eq(A_VERSION)].iloc[0].to_dict()
        b = group[group["version"].eq(B_VERSION)].iloc[0].to_dict()
        c = group[group["version"].eq(C_VERSION)].iloc[0].to_dict()
        window = windows[windows["requested_start_month"].eq(start_month)]
        aw = window[window["version"].eq(A_VERSION)].iloc[0]
        cw = window[window["version"].eq(C_VERSION)].iloc[0]
        row = s10._anchor_gate_row(
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
                "b_total_return_pct": float(b["total_return_pct"]),
                "b_max_drawdown_pct": float(b["max_drawdown_pct"]),
                "c_vs_b_return_delta_pp": float(c["total_return_pct"])
                - float(b["total_return_pct"]),
                "c_vs_b_return_improved_pass": bool(
                    float(c["total_return_pct"]) > float(b["total_return_pct"])
                ),
                "b_broker10_peak_pct": float(
                    b["max_broker10_margin_to_equity_pct"]
                ),
            }
        )
        row["anchor_performance_pass"] = bool(
            row["anchor_performance_pass"]
            and row["c_vs_b_return_improved_pass"]
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
                "normalized_sha256": s12.s6.stage001.source._normalized_ai_hash(
                    frame
                ),
                "eligibility_sha256": s9._sha256(paths[version]),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(
        result["normalized_sha256"].nunique() == 1
    )
    return result


def _ai_future_signal_violation_count(candidates: pd.DataFrame) -> int:
    if candidates.empty:
        return 0
    candidate_dates = pd.to_datetime(
        candidates.get("date", pd.Series(index=candidates.index, dtype=str)),
        errors="coerce",
    )
    signal_dates = pd.to_datetime(
        candidates.get(
            "ai_product_pool_signal_date",
            pd.Series(index=candidates.index, dtype=str),
        ),
        errors="coerce",
    )
    return int((signal_dates.notna() & candidate_dates.notna() & signal_dates.gt(candidate_dates)).sum())


def _plot(curves: pd.DataFrame, pairs: pd.DataFrame) -> None:
    colors = {A_VERSION: "#111827", B_VERSION: "#0f766e", C_VERSION: "#c2410c"}
    labels = {A_VERSION: "A legacy C9", B_VERSION: "B correct ledger", C_VERSION: "C + quality25"}
    fig, axes = plt.subplots(2, len(ANCHOR_STARTS), figsize=(18, 9))
    for column, start in enumerate(ANCHOR_STARTS):
        start_month = start.strftime("%Y-%m")
        subset = curves[curves["requested_start_month"].eq(start_month)]
        for version in VERSIONS:
            part = subset[subset["version"].eq(version)].sort_values("date")
            dates = pd.to_datetime(part["date"], errors="coerce")
            equity = pd.to_numeric(part["account_equity"], errors="coerce")
            axes[0, column].plot(
                dates,
                equity,
                color=colors[version],
                label=labels[version],
                linewidth=1.05,
            )
            axes[1, column].plot(
                dates,
                (equity / equity.cummax() - 1.0) * 100.0,
                color=colors[version],
                linewidth=1.05,
            )
        pair = pairs[pairs["requested_start_month"].eq(start_month)].iloc[0]
        axes[0, column].set_title(
            f"{start_month} C/A retention={pair['return_retention_ratio']:.1%}"
        )
        axes[1, column].set_title(
            f"C-A DD improve={pair['full_drawdown_improvement_pp']:.2f}pp"
        )
        axes[0, column].grid(alpha=0.25)
        axes[1, column].grid(alpha=0.25)
    axes[0, 0].legend(fontsize=7)
    axes[0, 0].set_ylabel("account equity")
    axes[1, 0].set_ylabel("drawdown %")
    fig.suptitle("Stage013 authoritative ledger + guarded quality 25% anchors")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    pairs: pd.DataFrame,
    reconciliation: pd.DataFrame,
    immediate: pd.DataFrame,
    sizing_summary: pd.DataFrame,
    quality_audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage013 正确账本 + guarded quality 25% 三锚点 A/B/C

- 生成时间：`{decision['generated_at']}`。
- 决策：`{decision['decision']}`。
- A：旧 current C9 目标参照；B：Stage012 正确账本；C：B + guarded quality 25% floor。
- C 只对 `AI rank 1-8 + selected_volume>1 + risk_multiplier<2` 的 opened flat-entry 增加整数手；不含 OI/xsmom/RSI/ceil/Stage013 gate/ramp。

## 锚点硬门

{pairs.to_markdown(index=False)}

## 分臂汇总

{summary.to_markdown(index=False)}

## Quality事件审计

{quality_audit.to_markdown(index=False)}

## 权威权益 reconciliation

{reconciliation.to_markdown(index=False)}

## 即时成交修正

{immediate.to_markdown(index=False)}

## 候选日 sizing 对齐

{sizing_summary.to_markdown(index=False)}

## AI parity

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    source_stage012 = s9._verify_manifest(s12.OUT, s12.MANIFEST_PATH)
    if not source_stage012["pass"]:
        raise RuntimeError(f"source Stage012 manifest failed: {source_stage012}")
    for source in (UPSTREAM_GUARD_TOOL, UPSTREAM_GUARD_TEST, TEST_PATH):
        if not source.exists():
            raise FileNotFoundError(source)

    metadata = s12.s6.stage001.source._metadata()
    a_path = _source_eligibility_path(A_VERSION)
    b_path = _source_eligibility_path(B_VERSION)
    a_eligibility = pd.read_csv(a_path)
    b_eligibility = pd.read_csv(b_path)
    c_eligibility, c_path = _candidate_eligibility()
    eligibility = {
        A_VERSION: a_eligibility,
        B_VERSION: b_eligibility,
        C_VERSION: c_eligibility,
    }
    eligibility_paths = {A_VERSION: a_path, B_VERSION: b_path, C_VERSION: c_path}
    profile = _candidate_profile(metadata, c_path)

    daily_by_key: dict[tuple[str, str], pd.DataFrame] = {}
    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    reconciliation_parts: list[pd.DataFrame] = []
    immediate_rows: list[dict[str, Any]] = []
    sizing_parts: list[pd.DataFrame] = []
    quality_events_parts: list[pd.DataFrame] = []
    quality_audit_rows: list[dict[str, Any]] = []
    ai_usage_rows: list[dict[str, Any]] = []
    forbidden_event_count = 0

    for index, start in enumerate(ANCHOR_STARTS, 1):
        start_month = start.strftime("%Y-%m")
        print(
            f"[stage013] anchor {index}/{len(ANCHOR_STARTS)} start={start_month}",
            flush=True,
        )
        for version in (A_VERSION, B_VERSION):
            daily, frames, closed = _load_source_arm(start, version)
            row, curve = _summary(daily, closed, version, start)
            daily_by_key[(start_month, version)] = daily
            summary_rows.append(row)
            curves.append(curve)
            ai_usage_row = s12.s7._ai_usage_row(frames, version, start)
            ai_usage_row["future_signal_date_rows"] = (
                _ai_future_signal_violation_count(frames["entry_candidates"])
            )
            ai_usage_rows.append(ai_usage_row)

        c_daily, c_frames, c_closed = _run_c(metadata, profile, start)
        _save_c(start, c_daily, c_frames, c_closed)
        c_row, c_curve = _summary(c_daily, c_closed, C_VERSION, start)
        daily_by_key[(start_month, C_VERSION)] = c_daily
        summary_rows.append(c_row)
        curves.append(c_curve)
        ai_usage_row = s12.s7._ai_usage_row(c_frames, C_VERSION, start)
        ai_usage_row["future_signal_date_rows"] = (
            _ai_future_signal_violation_count(c_frames["entry_candidates"])
        )
        ai_usage_rows.append(ai_usage_row)

        reconciliation = s12.s6._equity_reconciliation(c_daily, c_frames)
        reconciliation["requested_start_month"] = start_month
        reconciliation_parts.append(reconciliation)
        immediate_rows.append(s12._immediate_audit(c_frames, start))
        sizing = s11._pretrade_equity_audit(
            c_frames["entry_candidates"], c_daily
        )
        sizing["requested_start_month"] = start_month
        sizing_parts.append(sizing)
        events = c_frames["stage013_quality_events"]
        quality_events_parts.append(events)
        quality_audit_rows.append(
            _quality_audit(events, c_frames["entry_candidates"], start)
        )

        reason = c_frames.get("trade_events", pd.DataFrame()).get(
            "reason", pd.Series(dtype=str)
        ).astype(str)
        forbidden_event_count += int(
            reason.isin(
                [
                    "stage013_account_state_pilot_gate",
                    s10.RAMP_REASON,
                    "stage058_quality_oi_cap50_add_risk",
                    "stage026_cool_quality_add_risk",
                ]
            ).sum()
        )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    reconciliation = pd.concat(reconciliation_parts, ignore_index=True, sort=False)
    immediate = pd.DataFrame(immediate_rows).sort_values("requested_start_month")
    sizing_audit = pd.concat(sizing_parts, ignore_index=True, sort=False)
    sizing_summary = _sizing_summary(sizing_audit)
    quality_events = pd.concat(quality_events_parts, ignore_index=True, sort=False)
    quality_audit = pd.DataFrame(quality_audit_rows).sort_values(
        "requested_start_month"
    )
    ai_usage = pd.DataFrame(ai_usage_rows).sort_values(
        ["requested_start_month", "version"]
    )
    ai_parity = _ai_parity(eligibility, eligibility_paths)
    windows = _windows(daily_by_key)
    pairs = _pairs(summary, windows)

    expected_starts = {start.strftime("%Y-%m") for start in ANCHOR_STARTS}
    reconciliation_ok = bool(
        len(reconciliation) >= len(ANCHOR_STARTS)
        and reconciliation["reconciliation_pass"].astype(bool).all()
    )
    immediate_ok = bool(
        len(immediate) == len(ANCHOR_STARTS)
        and immediate["immediate_correction_pass"].astype(bool).all()
    )
    sizing_ok = s12._sizing_alignment_pass(
        sizing_audit, expected_starts=expected_starts
    )
    quality_ok = bool(
        len(quality_audit) == len(ANCHOR_STARTS)
        and quality_audit["quality_audit_pass"].astype(bool).all()
        and _quality_event_audit_pass(
            quality_events, expected_starts=expected_starts
        )
    )
    ai_parity_ok = bool(
        ai_parity["all_normalized_equal"].eq(1).all()
        and pd.to_numeric(ai_parity["rows"], errors="coerce").eq(504).all()
        and pd.to_numeric(ai_parity["eval_date_count"], errors="coerce")
        .eq(55)
        .all()
    )
    usage = pd.to_numeric(ai_usage["ai_usage_rows"], errors="coerce").fillna(0)
    enabled = pd.to_numeric(ai_usage["ai_enabled_rows"], errors="coerce").fillna(0)
    missing = pd.to_numeric(
        ai_usage["missing_signal_date_rows"], errors="coerce"
    ).fillna(1)
    future = pd.to_numeric(
        ai_usage["future_signal_date_rows"], errors="coerce"
    ).fillna(1)
    ai_usage_ok = bool(
        len(ai_usage) == len(ANCHOR_STARTS) * len(VERSIONS)
        and usage.eq(enabled).all()
        and missing.eq(0).all()
        and future.eq(0).all()
    )
    semantics_ok = bool(
        source_stage012["pass"]
        and reconciliation_ok
        and immediate_ok
        and sizing_ok
        and quality_ok
        and ai_parity_ok
        and ai_usage_ok
        and forbidden_event_count == 0
    )
    performance_ok = bool(
        s10._anchor_performance_pass(pairs)
        and pairs["c_vs_b_return_improved_pass"].astype(bool).all()
    )
    if not semantics_ok:
        decision_name = "stage013_semantic_fail_close_no_result_claim"
    elif performance_ok:
        decision_name = "stage013_anchor_pass_allow_halfyear"
    else:
        decision_name = "stage013_anchor_fail_close_no_parameter_rescue"
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "anchor_starts": [start.strftime("%Y-%m") for start in ANCHOR_STARTS],
        "requested_end": REQUESTED_END.date().isoformat(),
        "a_legacy_reference_reused": True,
        "b_stage012_reference_reused": True,
        "c_true_engine_run_count": len(ANCHOR_STARTS),
        "source_stage012_manifest_pass": bool(source_stage012["pass"]),
        "all_reconciliations_ok": reconciliation_ok,
        "all_immediate_corrections_ok": immediate_ok,
        "all_candidate_day_sizing_aligned": sizing_ok,
        "all_quality_events_and_mappings_ok": quality_ok,
        "quality_event_count": int(len(quality_events)),
        "quality_total_added_volume": int(
            pd.to_numeric(
                quality_events["stage013_quality_added_volume"], errors="coerce"
            ).sum()
        ),
        "ai_parity_ok": ai_parity_ok,
        "ai_usage_ok": ai_usage_ok,
        "forbidden_stage013_ramp_oi_or_cool_quality_event_count": int(
            forbidden_event_count
        ),
        "semantics_ok": semantics_ok,
        "performance_ok": performance_ok,
        "anchor_gates": pairs.to_dict("records"),
        "final_goal_complete": False,
        "decision": decision_name,
        "overfit_before": "low-to-medium: frozen upstream guarded-quality selector",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: only untested single-leg right-tail restoration structure on corrected ledger",
        "continue_value_after": "pending_independent_review",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    quality_events.to_csv(QUALITY_EVENTS_PATH, index=False, compression="gzip")
    quality_audit.to_csv(QUALITY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    immediate.to_csv(IMMEDIATE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    sizing_audit.to_csv(SIZING_AUDIT_PATH, index=False, compression="gzip")
    sizing_summary.to_csv(SIZING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, compression="gzip")
    DECISION_PATH.write_text(
        json.dumps(s9._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lineage = {
        "stage": STAGE_LABEL,
        "source_stage012_manifest": {
            "path": str(s12.MANIFEST_PATH),
            "sha256": s9._sha256(s12.MANIFEST_PATH),
        },
        "source_stage012_manifest_audit": source_stage012,
        "upstream_guard_tool": {
            "path": str(UPSTREAM_GUARD_TOOL),
            "sha256": s9._sha256(UPSTREAM_GUARD_TOOL),
        },
        "upstream_guard_test": {
            "path": str(UPSTREAM_GUARD_TEST),
            "sha256": s9._sha256(UPSTREAM_GUARD_TEST),
        },
        "stage013_tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": s9._sha256(Path(__file__).resolve()),
        },
        "stage013_test": {
            "path": str(TEST_PATH),
            "sha256": s9._sha256(TEST_PATH),
        },
        "source_reference_files": {
            f"{start.strftime('%Y-%m')}_{version}_{kind}": str(
                _source_arm_path(start, version, kind)
            )
            for start in ANCHOR_STARTS
            for version in (A_VERSION, B_VERSION)
            for kind in (
                "daily",
                "entry_candidates",
                "trades",
                "trade_events",
                "closed_lots",
                "stop_retry_events",
            )
        },
        "history_database_snapshot_complete": False,
    }
    LINEAGE_PATH.write_text(
        json.dumps(s9._json_safe(lineage), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame, pairs)
    _write_report(
        summary,
        pairs,
        reconciliation,
        immediate,
        sizing_summary,
        quality_audit,
        ai_parity,
        decision,
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "pairs": pairs,
        "quality_audit": quality_audit,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["pairs"].to_string(index=False))
    print(result["quality_audit"].to_string(index=False))
    print(json.dumps(s9._json_safe(result["decision"]), ensure_ascii=False, indent=2))
