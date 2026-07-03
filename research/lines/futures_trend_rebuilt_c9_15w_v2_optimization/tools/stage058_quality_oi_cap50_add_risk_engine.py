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


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage026_cool_quality_add_risk_engine as s026  # noqa: E402
import stage049_contract_oi_migration_audit as s049  # noqa: E402


PROJECT_DIR = s026.PROJECT_DIR
LINE_ID = s026.LINE_ID
STAGE = "Stage058"
MODEL_TAG = "stage058_quality_oi_cap50_add_risk_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine"
PROFILE_NAME = "stage058_quality_oi_cap50_add_risk_engine"

V2_LINE_DIR = s026.V2_LINE_DIR
REQUESTED_START = s026.REQUESTED_START
REQUESTED_END = s026.REQUESTED_END

STAGE058_AI_RANK_MIN = 1
STAGE058_AI_RANK_MAX = 8
STAGE058_QUALITY_ADD_RISK_FRACTION = 0.25
STAGE058_OI_ADD_RISK_FRACTION = 0.25
STAGE058_TOTAL_ADD_RISK_CAP = 0.50
STAGE058_CONTRACT_OI_SHARE_MIN = 0.50
STAGE058_MAX_FEATURE_AGE_DAYS = s049.MAX_FEATURE_AGE_DAYS

STAGE051_OUTPUT_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / s026.UPSTREAM_LINE_ID
    / "outputs"
    / "stage051_contract_oi_repaired_rerun"
)
STAGE051_PREFIX = "rebuilt_c9_stage051_contract_oi_repaired_rerun"
STAGE051_TAG = "stage051_contract_oi_repaired_rerun_v1"
CONTRACT_OI_SNAPSHOTS_PATH = (
    STAGE051_OUTPUT_DIR / f"{STAGE051_PREFIX}_contract_oi_snapshots_{STAGE051_TAG}.csv"
)

OUTPUT_DIR = V2_LINE_DIR / "outputs" / "stage058_quality_oi_cap50_add_risk_engine"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv.gz"
STAGE058_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_oi_cap50_add_risk_events_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_vs_stage013_{MODEL_TAG}.csv"
AB_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ab_summary_vs_stage013_{MODEL_TAG}.csv"
ABSOLUTE_EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
NAV_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_nav_chart_{MODEL_TAG}.png"
GOAL_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_audit_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

_STAGE058_OI_LOOKUP: dict[str, pd.DataFrame] | None = None


def _json_safe(value: Any) -> Any:
    return s026._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s026._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return s026._date_text(value)


def _start_month_text(value: Any) -> str:
    return s026._start_month_text(value)


def _to_float(value: Any, default: float = np.nan) -> float:
    return s026._to_float(value, default)


def _to_int(value: Any, default: int = 0) -> int:
    return s026._to_int(value, default)


def _stage058_trade_date_key(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return pd.NaT
    return pd.Timestamp(timestamp.date())


def _stage058_contract_key(contract_vt_symbol: Any) -> str:
    normalized = s049._normalise_contract_vt(contract_vt_symbol)
    return s049._contract_key(normalized)


def _stage058_build_oi_lookup(snapshots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frame = snapshots.copy()
    frame["asof_date"] = pd.to_datetime(frame["asof_date"], errors="coerce").dt.normalize()
    frame["feature_date"] = pd.to_datetime(frame["feature_date"], errors="coerce").dt.normalize()
    frame["contract_vt_symbol"] = frame["contract_vt_symbol"].map(s049._normalise_contract_vt)
    frame["contract_key"] = frame["contract_vt_symbol"].map(s049._contract_key)
    frame["contract_oi_share"] = pd.to_numeric(frame["contract_oi_share"], errors="coerce")
    frame["oi_rank"] = pd.to_numeric(frame["oi_rank"], errors="coerce")
    frame = frame.dropna(subset=["asof_date"])
    frame = frame.sort_values(["contract_key", "asof_date", "feature_date"]).reset_index(drop=True)
    return {str(key): group.reset_index(drop=True) for key, group in frame.groupby("contract_key", sort=False)}


def _stage058_load_oi_lookup() -> dict[str, pd.DataFrame]:
    global _STAGE058_OI_LOOKUP
    if _STAGE058_OI_LOOKUP is None:
        snapshots = pd.read_csv(CONTRACT_OI_SNAPSHOTS_PATH, encoding="utf-8-sig")
        _STAGE058_OI_LOOKUP = _stage058_build_oi_lookup(snapshots)
    return _STAGE058_OI_LOOKUP


def _stage058_contract_oi_fields(
    *,
    contract_vt_symbol: Any,
    entry_date: Any,
    oi_lookup: dict[str, pd.DataFrame],
    max_feature_age_days: int = STAGE058_MAX_FEATURE_AGE_DAYS,
) -> dict[str, Any]:
    contract_vt = s049._normalise_contract_vt(contract_vt_symbol)
    contract_key = s049._contract_key(contract_vt)
    date_key = _stage058_trade_date_key(entry_date)
    defaults = {
        "stage058_contract_oi_contract_vt": contract_vt,
        "stage058_contract_oi_contract_key": contract_key,
        "stage058_contract_oi_matched": 0,
        "stage058_contract_oi_feature_date": "",
        "stage058_contract_oi_asof_date": "",
        "stage058_contract_oi_feature_age_days": np.nan,
        "stage058_contract_oi_share": np.nan,
        "stage058_contract_oi_rank": np.nan,
        "stage058_contract_count": np.nan,
        "stage058_contract_is_mapping_main": 0,
        "stage058_contract_is_top1_oi": 0,
        "stage058_contract_is_top2_oi": 0,
        "stage058_contract_oi_top1_contract_vt": "",
        "stage058_contract_oi_top1_share": np.nan,
        "stage058_contract_oi_top2_contract_vt": "",
        "stage058_contract_oi_top2_share": np.nan,
        "stage058_contract_oi_top2_cumulative_share": np.nan,
        "stage058_contract_oi_main_contract_vt": "",
        "stage058_contract_oi_mapping_main_share": np.nan,
        "stage058_contract_oi_share_min": STAGE058_CONTRACT_OI_SHARE_MIN,
        "stage058_contract_oi_share_hit": 0,
        "stage058_contract_oi_lookup_reason": "oi_missing",
    }
    if pd.isna(date_key):
        defaults["stage058_contract_oi_lookup_reason"] = "entry_date_missing"
        return defaults
    group = oi_lookup.get(contract_key)
    if group is None or group.empty:
        defaults["stage058_contract_oi_lookup_reason"] = "contract_key_missing"
        return defaults

    asof_values = group["asof_date"].to_numpy(dtype="datetime64[ns]")
    pos = int(np.searchsorted(asof_values, np.datetime64(date_key), side="right") - 1)
    if pos < 0:
        defaults["stage058_contract_oi_lookup_reason"] = "no_prior_asof"
        return defaults
    row = group.iloc[pos]
    asof_date = pd.Timestamp(row["asof_date"]).normalize()
    age_days = int((date_key - asof_date).days)
    if age_days < 0 or age_days > int(max_feature_age_days):
        defaults["stage058_contract_oi_lookup_reason"] = "asof_too_old"
        defaults["stage058_contract_oi_feature_age_days"] = age_days
        defaults["stage058_contract_oi_asof_date"] = asof_date.date().isoformat()
        return defaults

    share = _to_float(row.get("contract_oi_share"), np.nan)
    share_hit = bool(np.isfinite(share) and share >= STAGE058_CONTRACT_OI_SHARE_MIN)
    feature_date = pd.Timestamp(row["feature_date"]).normalize()
    return {
        **defaults,
        "stage058_contract_oi_matched": 1,
        "stage058_contract_oi_feature_date": feature_date.date().isoformat(),
        "stage058_contract_oi_asof_date": asof_date.date().isoformat(),
        "stage058_contract_oi_feature_age_days": age_days,
        "stage058_contract_oi_share": share,
        "stage058_contract_oi_rank": _to_float(row.get("oi_rank"), np.nan),
        "stage058_contract_count": _to_float(row.get("contract_count"), np.nan),
        "stage058_contract_is_mapping_main": int(bool(row.get("contract_is_mapping_main", False))),
        "stage058_contract_is_top1_oi": int(bool(row.get("contract_is_top1_oi", False))),
        "stage058_contract_is_top2_oi": int(bool(row.get("contract_is_top2_oi", False))),
        "stage058_contract_oi_top1_contract_vt": str(row.get("top1_contract_vt", "") or ""),
        "stage058_contract_oi_top1_share": _to_float(row.get("top1_oi_share"), np.nan),
        "stage058_contract_oi_top2_contract_vt": str(row.get("top2_contract_vt", "") or ""),
        "stage058_contract_oi_top2_share": _to_float(row.get("top2_oi_share"), np.nan),
        "stage058_contract_oi_top2_cumulative_share": _to_float(row.get("top2_cumulative_oi_share"), np.nan),
        "stage058_contract_oi_main_contract_vt": str(row.get("main_contract_vt", "") or ""),
        "stage058_contract_oi_mapping_main_share": _to_float(row.get("mapping_main_oi_share"), np.nan),
        "stage058_contract_oi_share_hit": int(share_hit),
        "stage058_contract_oi_lookup_reason": "matched",
    }


def _stage058_apply_quality_oi_cap50_add_risk(
    *,
    sizing: dict[str, Any],
    direction: str,
    entry_context: str,
    target_contract: Any,
    entry_date: Any,
    oi_lookup: dict[str, pd.DataFrame],
    enabled: bool,
    ai_rank_min: int = STAGE058_AI_RANK_MIN,
    ai_rank_max: int = STAGE058_AI_RANK_MAX,
    quality_add_fraction: float = STAGE058_QUALITY_ADD_RISK_FRACTION,
    oi_add_fraction: float = STAGE058_OI_ADD_RISK_FRACTION,
    total_add_cap: float = STAGE058_TOTAL_ADD_RISK_CAP,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, _to_int(sizing.get("selected_volume"), 0))
    ai_rank = _to_float(sizing.get("ai_product_pool_rank"), np.nan)
    quality_hit = bool(selected_before > 1 and np.isfinite(ai_rank) and ai_rank_min <= ai_rank <= ai_rank_max)
    oi_fields = _stage058_contract_oi_fields(
        contract_vt_symbol=target_contract,
        entry_date=entry_date,
        oi_lookup=oi_lookup,
    )
    oi_hit = int(oi_fields["stage058_contract_oi_share_hit"]) == 1

    raw_fraction = (float(quality_add_fraction) if quality_hit else 0.0) + (
        float(oi_add_fraction) if oi_hit else 0.0
    )
    capped_fraction = min(float(raw_fraction), float(total_add_cap))
    selected_after_candidate = int(np.floor(float(selected_before) * (1.0 + capped_fraction)))
    added_volume = max(0, selected_after_candidate - selected_before)

    selected_after = selected_before
    applied = 0
    if not enabled:
        reason = "disabled"
    elif selected_before <= 0:
        reason = "zero_selected_volume"
    elif str(entry_context or "") != "flat_entry":
        reason = "non_flat_entry_context"
    elif not quality_hit and not oi_hit:
        reason = "quality_and_oi_not_hit"
    elif added_volume <= 0:
        reason = "floor_combo_no_integer_increment"
    else:
        selected_after = selected_after_candidate
        applied = 1
        reason = "stage058_quality_oi_cap50_floor_add_risk"

    fields = {
        "stage058_quality_oi_add_risk_enabled": int(bool(enabled)),
        "stage058_quality_oi_add_risk_applied": applied,
        "stage058_quality_oi_add_risk_reason": reason,
        "stage058_quality_oi_selected_volume_before": selected_before,
        "stage058_quality_oi_selected_volume_after": selected_after,
        "stage058_quality_oi_add_risk_added_volume": selected_after - selected_before,
        "stage058_quality_oi_candidate_added_volume": added_volume,
        "stage058_quality_oi_ai_rank": ai_rank,
        "stage058_quality_oi_ai_rank_min": int(ai_rank_min),
        "stage058_quality_oi_ai_rank_max": int(ai_rank_max),
        "stage058_quality_oi_quality_hit": int(quality_hit),
        "stage058_quality_oi_oi_hit": int(oi_hit),
        "stage058_quality_oi_quality_add_fraction": float(quality_add_fraction),
        "stage058_quality_oi_oi_add_fraction": float(oi_add_fraction),
        "stage058_quality_oi_raw_add_fraction": float(raw_fraction),
        "stage058_quality_oi_total_add_cap": float(total_add_cap),
        "stage058_quality_oi_capped_add_fraction": float(capped_fraction),
        "stage058_quality_oi_direction": str(direction or ""),
        **oi_fields,
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage058QualityOiCap50AddRisk(
    s026.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate
):
    enable_stage058_quality_oi_cap50_add_risk: bool = False
    stage058_ai_rank_min: int = STAGE058_AI_RANK_MIN
    stage058_ai_rank_max: int = STAGE058_AI_RANK_MAX
    stage058_quality_add_risk_fraction: float = STAGE058_QUALITY_ADD_RISK_FRACTION
    stage058_oi_add_risk_fraction: float = STAGE058_OI_ADD_RISK_FRACTION
    stage058_total_add_risk_cap: float = STAGE058_TOTAL_ADD_RISK_CAP

    parameters = s026.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage058_quality_oi_cap50_add_risk",
        "stage058_ai_rank_min",
        "stage058_ai_rank_max",
        "stage058_quality_add_risk_fraction",
        "stage058_oi_add_risk_fraction",
        "stage058_total_add_risk_cap",
    ]
    variables = s026.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage058_quality_oi_add_risk_count",
        "stage058_quality_oi_add_risk_added_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage058_oi_lookup = _stage058_load_oi_lookup()
        self.stage058_quality_oi_add_risk_events: list[dict[str, Any]] = []
        self.stage058_quality_oi_add_risk_count: int = 0
        self.stage058_quality_oi_add_risk_added_volume: int = 0

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage058_quality_oi_cap50_add_risk:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            bar = plan.get("target_bar")
            bar_datetime = getattr(bar, "datetime", None)
            if bar_datetime is None:
                continue
            target_contract = str(plan.get("target_contract") or product_vt_symbol)
            sizing = s026._stage026_sizing_with_signal_fields(plan)
            selected_after, fields = _stage058_apply_quality_oi_cap50_add_risk(
                sizing=sizing,
                direction=str(plan.get("direction") or ""),
                entry_context="flat_entry",
                target_contract=target_contract,
                entry_date=bar_datetime,
                oi_lookup=self.stage058_oi_lookup,
                enabled=bool(self.enable_stage058_quality_oi_cap50_add_risk),
                ai_rank_min=int(self.stage058_ai_rank_min),
                ai_rank_max=int(self.stage058_ai_rank_max),
                quality_add_fraction=float(self.stage058_quality_add_risk_fraction),
                oi_add_fraction=float(self.stage058_oi_add_risk_fraction),
                total_add_cap=float(self.stage058_total_add_risk_cap),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage058_quality_oi_add_risk_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            event = self._stage058_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage058_quality_oi_add_risk_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage058_quality_oi_add_risk_count += 1
            self.stage058_quality_oi_add_risk_added_volume += int(
                fields["stage058_quality_oi_add_risk_added_volume"]
            )
        return plans

    def _stage058_event_from_plan(
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
            "reason": "stage058_quality_oi_cap50_add_risk",
            "volume": int(fields["stage058_quality_oi_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage058_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s026.s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{s026.OFFICIAL_LIVE_CAPITAL_LABEL} {s026.OFFICIAL_LIVE_ALIAS} Stage058 quality+OI cap50 add-risk engine",
        account_capital=s026.OFFICIAL_LIVE_CAPITAL,
        c3_capital=s026.OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage058 isolated research candidate. "
            "Keep Stage013 account-state pilot and C9 stop-retry unchanged; opened flat-entry sizing receives "
            "25% for AI rank 1-8 and 25% for point-in-time contract OI share >= 50%, capped at 50% total, "
            "using floor integer size only."
        ),
    )
    overrides = {
        **spec.overrides,
        **s026.build_official_live_strategy_overrides(),
        "enable_stage058_quality_oi_cap50_add_risk": True,
        "stage058_ai_rank_min": STAGE058_AI_RANK_MIN,
        "stage058_ai_rank_max": STAGE058_AI_RANK_MAX,
        "stage058_quality_add_risk_fraction": STAGE058_QUALITY_ADD_RISK_FRACTION,
        "stage058_oi_add_risk_fraction": STAGE058_OI_ADD_RISK_FRACTION,
        "stage058_total_add_risk_cap": STAGE058_TOTAL_ADD_RISK_CAP,
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage058QualityOiCap50AddRisk
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage058(
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    _stage058_load_oi_lookup()
    original_start = s026.s847.START
    original_end = s026.s847.END
    original_minute_by_symbol = s026.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s026.s901._ensure_c9_minute_bars(metadata)
    try:
        s026.s847.START = analysis_start.normalize()
        s026.s847.END = analysis_end.normalize()
        profile = _stage058_profile(metadata)
        combined, frames = s026.s013._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s026.s847.START = original_start
        s026.s847.END = original_end
        s026.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

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
    result["official_live_version"] = s026.OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = s026.OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    return result


def _append_frame(target: list[pd.DataFrame], frame: pd.DataFrame, start: pd.Timestamp) -> None:
    frame = _frame_with_run_columns(frame, start)
    if not frame.empty:
        target.append(frame)


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    row = s026.s167._summarize_curve(curve, requested_start)
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
    return [pd.Timestamp(value).normalize() for value in s026.s167._build_start_dates()]


def _run_multistart() -> dict[str, pd.DataFrame]:
    metadata = s026.s901.s513._metadata()
    starts = _build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage058] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage058(metadata, start, REQUESTED_END)

        curve = combined.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["official_live_version"] = s026.OFFICIAL_LIVE_VERSION
        curve["official_live_alias"] = s026.OFFICIAL_LIVE_ALIAS
        curve["requested_start"] = _date_text(start)
        curve["requested_start_month"] = _start_month_text(start)
        curve["requested_end"] = _date_text(REQUESTED_END)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(s026.OFFICIAL_LIVE_CAPITAL)
        curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
        curve["drawdown_pct"] = s026.s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start))

        _append_frame(candidate_frames, frames.get("entry_candidates", pd.DataFrame()), start)
        _append_frame(trade_frames, frames.get("trades", pd.DataFrame()), start)
        _append_frame(entry_risk_frames, frames.get("entry_risk", pd.DataFrame()), start)
        _append_frame(trade_event_frames, frames.get("trade_events", pd.DataFrame()), start)

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    stage058_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage058_quality_oi_cap50_add_risk")].copy()
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
        "stage058_events": stage058_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s026.s013.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_stage013", "_stage058"),
    )
    merged["stage058_vs_stage013_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage058"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage058"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _ab_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s026.s013.SUMMARY_PATH, encoding="utf-8-sig")
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
        suffixes=("_stage013_A", "_stage058_C"),
    )
    for metric in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]:
        merged[f"{metric}_delta_C_minus_A"] = (
            pd.to_numeric(merged[f"{metric}_stage058_C"], errors="coerce")
            - pd.to_numeric(merged[f"{metric}_stage013_A"], errors="coerce")
        )
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage058_engine"
    audit_curves["date"] = pd.to_datetime(audit_curves["date"], errors="coerce").dt.normalize()
    audit_curves["equity"] = pd.to_numeric(audit_curves["equity"], errors="coerce")
    audit_curves = audit_curves.dropna(subset=["date", "equity"])
    return s026.s009._run_audit(audit_curves)


def _ai_audit(candidates: pd.DataFrame, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    pool, pool_audit = s026.s167._load_ai_pool()
    month_audit = s026.s167._ai_month_audit(candidates, summary, pool)
    pool_frame = s026.s167._pool_audit_frame(pool)
    return month_audit, pool_frame, pool_audit


def _plot_absolute_equity(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], linewidth=0.9, alpha=0.76, label=str(start))
        axes[1].plot(group["date"], group["drawdown_pct"], linewidth=0.9, alpha=0.76, label=str(start))
    axes[0].axhline(s026.OFFICIAL_LIVE_CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    axes[0].set_title("Stage058 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage058 Drawdown By Cold Start")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(ABSOLUTE_EQUITY_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_nav(curves: pd.DataFrame) -> None:
    fig, ax = plt.subplots(1, 1, figsize=(18, 8), constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        ax.plot(group["date"], group["nav"], linewidth=0.9, alpha=0.76, label=str(start))
    ax.axhline(1.0, color="#111827", linestyle="--", linewidth=0.9)
    ax.set_title("Stage058 NAV By Cold Start")
    ax.set_ylabel("NAV = account equity / 150k")
    ax.set_xlabel("date")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(NAV_CHART_PATH, dpi=160)
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
    if not s026.s013.GOAL_AGGREGATE_PATH.exists():
        return {}
    aggregate = pd.read_csv(s026.s013.GOAL_AGGREGATE_PATH, encoding="utf-8-sig")
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
    stage058_events: pd.DataFrame,
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
    quality_hits = (
        pd.to_numeric(stage058_events.get("stage058_quality_oi_quality_hit", pd.Series(dtype=float)), errors="coerce")
        .fillna(0)
        .sum()
        if not stage058_events.empty
        else 0
    )
    oi_hits = (
        pd.to_numeric(stage058_events.get("stage058_quality_oi_oi_hit", pd.Series(dtype=float)), errors="coerce")
        .fillna(0)
        .sum()
        if not stage058_events.empty
        else 0
    )
    both_hits = (
        (
            pd.to_numeric(stage058_events.get("stage058_quality_oi_quality_hit", pd.Series(dtype=float)), errors="coerce")
            .fillna(0)
            .eq(1)
            & pd.to_numeric(stage058_events.get("stage058_quality_oi_oi_hit", pd.Series(dtype=float)), errors="coerce")
            .fillna(0)
            .eq(1)
        ).sum()
        if not stage058_events.empty
        else 0
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
        "stage058_event_count": int(len(stage058_events)),
        "stage058_added_volume_sum": (
            int(
                pd.to_numeric(
                    stage058_events.get("stage058_quality_oi_add_risk_added_volume", pd.Series(dtype=float)),
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
            if not stage058_events.empty
            else 0
        ),
        "stage058_quality_hit_event_count": int(quality_hits),
        "stage058_oi_hit_event_count": int(oi_hits),
        "stage058_both_hit_event_count": int(both_hits),
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
        return "stage058_strict_goal_pass_needs_independent_review"
    base_neg = metrics.get("stage013_all_gt1y_negative_count")
    if (
        base_neg is not None
        and metrics["all_gt1y_negative_count"] < int(base_neg)
        and metrics["retention_80pct_pass_count"] == metrics["retention_rows"]
        and metrics["return_win_count_vs_stage013"] >= max(1, metrics["return_compare_rows"] // 2)
    ):
        return "stage058_directionally_positive_needs_full_ab_review"
    return "stage058_not_promoted_keep_for_attribution"


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    worst: pd.DataFrame,
    retention: pd.DataFrame,
    ab_summary: pd.DataFrame,
    stage058_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    report = f"""# Stage058 quality + OI cap50 真实引擎 A/B

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- A：Stage013 account-state pilot gate。
- B：不设独立 B；quality/OI 是入场 sizing overlay，不是可独立交易策略。
- C：Stage013 + Stage058 quality/OI cap50 add-risk engine。
- 线上母本：`{s026.OFFICIAL_LIVE_VERSION}` / `{s026.OFFICIAL_LIVE_PROFILE_NAME}`
- 回测区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`；起点为每年 `01-01/07-01`
- 阶段性质：独立研究 profile 真实引擎；不改官方 live config、不连接 CTP、不调用下单

## 外部调研判断

- Meta-labeling / bet-sizing 资料支持 secondary layer 调整 primary signal 的参与强度，而不是重写方向。
- pysystemtrade/systematic trading 框架强调 signal、position sizing、组合风险和成本要分层验证；本阶段只改 opened flat-entry 的 sizing。
- managed futures/trend following 资料说明长期优势来自跨市场趋势右尾和分散化，不能用历史局部坏窗口写品种/日期黑名单。

## 固定规则

- 只作用于 opened `flat_entry`。
- quality 腿：`AI rank 1-8` 且 `selected_volume>1`，给 `+25%`。
- OI 腿：目标合约点时 `contract_oi_share>=50%`，给 `+25%`。
- 合计加风险上限 `50%`，动作是 `floor(selected_volume * (1 + capped_fraction))`；不做 ceil，不强制最小加 1 手。
- OI 来源：Stage051 逐合约 OI 快照，`asof_date=feature_date+1`，最大旧值 `{STAGE058_MAX_FEATURE_AGE_DAYS}` 天。
- 已有仓位、换月、加仓、反手、开仓日实时止损重试、AI 月池、保证金和成本逻辑保持 C9/Stage013 原样。

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
- Stage058 触发事件：`{metrics['stage058_event_count']}`；增加手数：`{metrics['stage058_added_volume_sum']}`
- 事件构成：quality hit `{metrics['stage058_quality_hit_event_count']}`，OI hit `{metrics['stage058_oi_hit_event_count']}`，both hit `{metrics['stage058_both_hit_event_count']}`
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

## Stage058 事件样本

{_md_table(stage058_events.head(40), max_rows=40)}

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
- stage058_events: `{STAGE058_EVENTS_PATH}`
- goal_aggregate: `{GOAL_AGGREGATE_PATH}`
- retention: `{RETENTION_PATH}`
- ab_summary: `{AB_SUMMARY_PATH}`
- absolute_equity_chart: `{ABSOLUTE_EQUITY_CHART_PATH}`
- nav_chart: `{NAV_CHART_PATH}`
- goal_audit_chart: `{GOAL_AUDIT_CHART_PATH}`
- decision: `{DECISION_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    stage_dir = V2_LINE_DIR / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    generated = pd.Timestamp(decision["generated_at"])
    record_path = stage_dir / f"{generated.strftime('%Y%m%d_%H%M')}_stage058_quality_oi_cap50_add_risk_engine.md"
    metrics = decision["metrics"]
    lines = [
        "# Stage058 quality + OI cap50 真实引擎 A/B",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        f"- 工作区：`{PROJECT_DIR}`",
        "- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：待结果判断；当前为候选真实验证",
        "- 是否触发A/B：是；A=Stage013，B=不适用，C=Stage013+Stage058",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：meta-labeling/bet sizing、pysystemtrade/systematic trading、AQR managed futures/trend following。",
        "- 我的判断：quality 与 OI 都是主信号上的点时 sizing overlay，不能独立交易；若要接近正式候选，必须在真实引擎里改善路径稳健性，同时不伤 AI 月池和趋势右尾。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        f"- 新增参数：`stage058_ai_rank_min={STAGE058_AI_RANK_MIN}`、`stage058_ai_rank_max={STAGE058_AI_RANK_MAX}`、"
        f"`stage058_quality_add_risk_fraction={STAGE058_QUALITY_ADD_RISK_FRACTION}`、"
        f"`stage058_oi_add_risk_fraction={STAGE058_OI_ADD_RISK_FRACTION}`、"
        f"`stage058_total_add_risk_cap={STAGE058_TOTAL_ADD_RISK_CAP}`、"
        f"`stage058_contract_oi_share_min={STAGE058_CONTRACT_OI_SHARE_MIN}`、"
        f"`stage058_max_feature_age_days={STAGE058_MAX_FEATURE_AGE_DAYS}`",
        "- 修改参数：无正式参数修改",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        f"- 数据区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`",
        f"- 账户规模：`{s026.OFFICIAL_LIVE_CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。",
        "- 样本过滤：每半年独立冷启动。",
        "- 策略口径：只对 opened flat_entry 中的质量腿/OI腿做 capped floor 整数加风险；不开独立 B。",
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
        f"- Stage058 触发事件：`{metrics['stage058_event_count']}`；增加手数 `{metrics['stage058_added_volume_sum']}`",
        f"- 事件构成：quality hit `{metrics['stage058_quality_hit_event_count']}`；OI hit `{metrics['stage058_oi_hit_event_count']}`；both hit `{metrics['stage058_both_hit_event_count']}`",
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
            "- 下一步：day 模式下先停下汇报；只有在真实引擎结果通过收益保留、负窗口和 A/B 对比后，才允许进入独立复核或更密集起点压力测试。",
            "",
            "## 过拟合反思",
            "",
            f"- 运行前判断：{decision['overfit_reflection_before']}",
            f"- 运行后判断：{decision['overfit_reflection_after']}",
            "- 原因：本阶段只验证一个预声明组合规则；若失败后继续扫 OI 阈值、AI topN、权重或 ceil/min+1 就会过拟合。",
            "",
            "## 继续价值反思",
            "",
            f"- 运行前判断：{decision['continue_value_before']}",
            f"- 运行后判断：{decision['continue_value_after']}",
            "- 原因：真实引擎结果能判断 Stage057 最强代理是否能落地，而不是只看 closed-lot 代理曲线。",
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
    stage058_events = frames["stage058_events"]

    ai_month_audit, ai_pool_audit, ai_pool_meta = _ai_audit(candidates, summary)
    aggregate, to_final, fixed, worst = _goal_audit(curves)
    retention = _retention_summary(summary)
    ab_summary = _ab_summary(summary)

    _plot_absolute_equity(curves)
    _plot_nav(curves)
    _plot_goal_audit(aggregate, worst, fixed)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    stage058_events.to_csv(STAGE058_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_pool_audit.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    ab_summary.to_csv(AB_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    metrics = _metrics(summary, aggregate, retention, stage058_events, ai_month_audit, ab_summary)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_A": "stage013_account_state_pilot_gate_engine",
        "standalone_B": "not_applicable_sizing_overlay",
        "candidate_C": PROFILE_NAME,
        "official_live_version": s026.OFFICIAL_LIVE_VERSION,
        "official_live_alias": s026.OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": s026.OFFICIAL_LIVE_PROFILE_NAME,
        "capital": s026.OFFICIAL_LIVE_CAPITAL,
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "stage058_parameters": {
            "ai_rank_min": STAGE058_AI_RANK_MIN,
            "ai_rank_max": STAGE058_AI_RANK_MAX,
            "quality_add_risk_fraction": STAGE058_QUALITY_ADD_RISK_FRACTION,
            "oi_add_risk_fraction": STAGE058_OI_ADD_RISK_FRACTION,
            "total_add_risk_cap": STAGE058_TOTAL_ADD_RISK_CAP,
            "contract_oi_share_min": STAGE058_CONTRACT_OI_SHARE_MIN,
            "max_feature_age_days": STAGE058_MAX_FEATURE_AGE_DAYS,
            "contract_oi_snapshots_path": str(CONTRACT_OI_SNAPSHOTS_PATH),
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
            "External references support PIT sizing overlays and cross-market trend preservation. "
            "Stage058 freezes one quality/OI capped floor rule and rejects post-hoc threshold rescue."
        ),
        "overfit_reflection_before": (
            "否，暂不算明显过拟合。规则来自 Stage057 最强代理但只取一个固定组合，且 OI 使用点时 asof，不按坏窗口调品种、日期或方向。"
        ),
        "continue_value_before": (
            "有价值。Stage057 只是 closed-lot proxy，必须用真实引擎验证整数手、保证金、止损重试、AI 月池和成本联动。"
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
            "stage058_events": str(STAGE058_EVENTS_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "ai_pool_audit": str(AI_POOL_AUDIT_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "ab_summary": str(AB_SUMMARY_PATH),
            "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
            "nav_chart": str(NAV_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    if decision["decision"] == "stage058_strict_goal_pass_needs_independent_review":
        decision["overfit_reflection_after"] = (
            "仍需谨慎。虽然达到硬目标，但它来自代理筛选后的真实化，必须独立复核、成本压力和更密起点后才能讨论正式化。"
        )
        decision["continue_value_after"] = "有价值，应进入独立 agent/code review 和更密集起点压力测试。"
    elif decision["decision"] == "stage058_directionally_positive_needs_full_ab_review":
        decision["overfit_reflection_after"] = (
            "低到中等。真实引擎改善了部分目标且收益保留过线；下一步只能做预声明复核，不能救参。"
        )
        decision["continue_value_after"] = "有价值，作为候选继续审计。"
    else:
        decision["overfit_reflection_after"] = (
            "真实引擎证据不足。若失败后继续调 OI 阈值、AI topN、权重、ceil 或品种方向，就是过拟合。"
        )
        decision["continue_value_after"] = "有限。若 C 没有改善路径稳健性，应停止该组合落地，回到新 PIT 源或账户外层结构。"

    _write_report(decision, summary, aggregate, worst, retention, ab_summary, stage058_events, ai_month_audit)
    decision["outputs"]["stage_record"] = str(_write_stage_record(decision))
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
