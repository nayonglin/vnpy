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
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage018"
MODEL_TAG = "stage018_regime_pilot_gate_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage018_regime_pilot_gate_engine"
PROFILE_NAME = "stage018_regime_pilot_gate_engine"

STAGE018_TARGET_REGIME = "high_vol_low_eff"
STAGE018_MIN_HISTORY_DAYS = 252
STAGE018_PILOT_MIN_VOLUME = 1
STAGE018_VOL_HIGH_Q = 0.67
STAGE018_EFF_LOW_Q = 0.33

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage018_regime_pilot_gate_engine"
BACKTEST_OUTPUT_DIR = PORTFOLIO_DIR / "backtest_outputs"

MARKET_DAILY_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_market_walkforward_market_daily_product_suitability_market_wf_v2.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
REGIME_GATE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_regime_gate_events_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_TO_FINAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_to_final_windows_{MODEL_TAG}.csv"
GOAL_FIXED_HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_fixed_horizon_windows_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_cycle_retention_{MODEL_TAG}.csv"
REGIME_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_causal_regime_table_{MODEL_TAG}.csv"
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


def _bucket_from_quantiles(value: float, low: float, high: float) -> str:
    if not np.isfinite(value) or not np.isfinite(low) or not np.isfinite(high):
        return "missing"
    if value <= low:
        return "low"
    if value >= high:
        return "high"
    return "mid"


def _stage018_joint_regime(vol_bucket: str, eff_bucket: str, breadth_share: float) -> str:
    if vol_bucket == "missing" or eff_bucket == "missing" or not np.isfinite(float(breadth_share)):
        return "missing"
    breadth_bucket = "breadth_high" if float(breadth_share) >= 0.67 else "breadth_low" if float(breadth_share) <= 0.33 else "breadth_mid"
    regime = "neutral"
    if breadth_bucket == "breadth_high" and eff_bucket != "low":
        regime = "broad_trend"
    if breadth_bucket == "breadth_low" and eff_bucket == "low":
        regime = "narrow_chop"
    if vol_bucket == "low" and eff_bucket == "low":
        regime = "quiet_low_eff"
    if eff_bucket == "high" and vol_bucket != "high":
        regime = "trend_clean"
    if eff_bucket == "high" and vol_bucket == "high":
        regime = "high_vol_high_eff"
    if vol_bucket == "high" and eff_bucket == "low":
        regime = "high_vol_low_eff"
    return regime


def _stage018_build_causal_regime_table(
    market_daily_path: Path = MARKET_DAILY_PATH,
    *,
    min_history_days: int = STAGE018_MIN_HISTORY_DAYS,
) -> pd.DataFrame:
    usecols = [
        "date",
        "product_vt_symbol",
        "market_realized_vol_60d",
        "market_trend_efficiency_60d",
        "market_ma20_over_ma60_60d",
    ]
    product_daily = pd.read_csv(market_daily_path, encoding="utf-8-sig", usecols=usecols, parse_dates=["date"])
    product_daily["date"] = product_daily["date"].dt.normalize()
    for column in usecols:
        if column not in {"date", "product_vt_symbol"}:
            product_daily[column] = pd.to_numeric(product_daily[column], errors="coerce")

    daily = (
        product_daily.groupby("date", dropna=False)
        .agg(
            product_count=("product_vt_symbol", "nunique"),
            median_realized_vol_60d=("market_realized_vol_60d", "median"),
            median_trend_efficiency_60d=("market_trend_efficiency_60d", "median"),
            ma20_over_ma60_share_60d=("market_ma20_over_ma60_60d", lambda value: float(value.gt(0.0).mean())),
        )
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )

    prior_vol = daily["median_realized_vol_60d"].shift(1)
    prior_eff = daily["median_trend_efficiency_60d"].shift(1)
    min_periods = max(2, int(min_history_days))
    daily["causal_vol_low_q"] = prior_vol.expanding(min_periods=min_periods).quantile(1.0 - STAGE018_VOL_HIGH_Q)
    daily["causal_vol_high_q"] = prior_vol.expanding(min_periods=min_periods).quantile(STAGE018_VOL_HIGH_Q)
    daily["causal_eff_low_q"] = prior_eff.expanding(min_periods=min_periods).quantile(STAGE018_EFF_LOW_Q)
    daily["causal_eff_high_q"] = prior_eff.expanding(min_periods=min_periods).quantile(1.0 - STAGE018_EFF_LOW_Q)

    vol_buckets: list[str] = []
    eff_buckets: list[str] = []
    regimes: list[str] = []
    for row in daily.itertuples(index=False):
        vol_bucket = _bucket_from_quantiles(
            float(row.median_realized_vol_60d),
            float(row.causal_vol_low_q) if pd.notna(row.causal_vol_low_q) else np.nan,
            float(row.causal_vol_high_q) if pd.notna(row.causal_vol_high_q) else np.nan,
        )
        eff_bucket = _bucket_from_quantiles(
            float(row.median_trend_efficiency_60d),
            float(row.causal_eff_low_q) if pd.notna(row.causal_eff_low_q) else np.nan,
            float(row.causal_eff_high_q) if pd.notna(row.causal_eff_high_q) else np.nan,
        )
        vol_buckets.append(vol_bucket)
        eff_buckets.append(eff_bucket)
        regimes.append(_stage018_joint_regime(vol_bucket, eff_bucket, float(row.ma20_over_ma60_share_60d)))
    daily["stage018_vol60_bucket"] = vol_buckets
    daily["stage018_eff60_bucket"] = eff_buckets
    daily["stage018_joint_regime_raw_date"] = regimes

    effective = daily.copy()
    effective["stage018_regime_source_date"] = effective["date"]
    effective["date"] = effective["date"].shift(-1)
    effective = effective.dropna(subset=["date"]).copy()
    effective["date"] = pd.to_datetime(effective["date"], errors="coerce").dt.normalize()
    effective["stage018_joint_regime"] = effective["stage018_joint_regime_raw_date"]
    return effective


def _stage018_load_regime_map(market_daily_path: str | Path = MARKET_DAILY_PATH) -> dict[str, dict[str, Any]]:
    table = _stage018_build_causal_regime_table(Path(market_daily_path))
    return {
        pd.Timestamp(row.date).date().isoformat(): {
            "stage018_joint_regime": str(row.stage018_joint_regime),
            "stage018_regime_source_date": pd.Timestamp(row.stage018_regime_source_date).date().isoformat(),
            "stage018_vol60_bucket": str(row.stage018_vol60_bucket),
            "stage018_eff60_bucket": str(row.stage018_eff60_bucket),
            "stage018_median_realized_vol_60d": float(row.median_realized_vol_60d),
            "stage018_median_trend_efficiency_60d": float(row.median_trend_efficiency_60d),
            "stage018_ma20_over_ma60_share_60d": float(row.ma20_over_ma60_share_60d),
        }
        for row in table.itertuples(index=False)
    }


def _stage018_apply_regime_pilot_gate(
    *,
    sizing: dict[str, Any],
    entry_context: str,
    regime_info: dict[str, Any] | None,
    min_position_size: int,
    enabled: bool,
    target_regime: str = STAGE018_TARGET_REGIME,
    pilot_min_volume: int = STAGE018_PILOT_MIN_VOLUME,
) -> tuple[int, dict[str, Any]]:
    selected_before = max(0, int(sizing.get("selected_volume") or 0))
    min_size = max(0, int(min_position_size or 0))
    pilot_volume = max(0, int(pilot_min_volume or 0))
    info = dict(regime_info or {})
    regime = str(info.get("stage018_joint_regime") or "missing")
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
    else:
        selected_after = min(selected_before, max(min_size, pilot_volume))
        if 0 < selected_after < min_size:
            selected_after = 0
        applied = int(selected_after != selected_before)
        reason = "stage018_high_vol_low_eff_flat_entry_pilot" if applied else "already_at_stage018_pilot_size"

    fields = {
        "stage018_regime_gate_enabled": int(bool(enabled)),
        "stage018_regime_gate_applied": applied,
        "stage018_regime_gate_reason": reason,
        "stage018_regime_gate_target_regime": str(target_regime),
        "stage018_regime_gate_joint_regime": regime,
        "stage018_regime_gate_source_date": str(info.get("stage018_regime_source_date") or ""),
        "stage018_regime_gate_vol60_bucket": str(info.get("stage018_vol60_bucket") or "missing"),
        "stage018_regime_gate_eff60_bucket": str(info.get("stage018_eff60_bucket") or "missing"),
        "stage018_regime_gate_median_realized_vol_60d": info.get("stage018_median_realized_vol_60d", np.nan),
        "stage018_regime_gate_median_trend_efficiency_60d": info.get(
            "stage018_median_trend_efficiency_60d", np.nan
        ),
        "stage018_regime_gate_ma20_over_ma60_share_60d": info.get("stage018_ma20_over_ma60_share_60d", np.nan),
        "stage018_regime_gate_selected_volume_before": selected_before,
        "stage018_regime_gate_selected_volume_after": selected_after,
        "stage018_regime_gate_reduced_volume": selected_before - selected_after,
        "stage018_regime_gate_pilot_min_volume": pilot_volume,
    }
    return selected_after, fields


class QmtRollPortfolioStrategyStage018RegimePilotGate(s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate):
    enable_stage018_regime_pilot_gate: bool = False
    stage018_regime_gate_target_regime: str = STAGE018_TARGET_REGIME
    stage018_regime_pilot_min_volume: int = STAGE018_PILOT_MIN_VOLUME
    stage018_market_daily_path: str = str(MARKET_DAILY_PATH)

    parameters = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage018_regime_pilot_gate",
        "stage018_regime_gate_target_regime",
        "stage018_regime_pilot_min_volume",
        "stage018_market_daily_path",
    ]
    variables = s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage018_regime_gate_count",
        "stage018_regime_gate_reduced_volume",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage018_regime_gate_events: list[dict[str, Any]] = []
        self.stage018_regime_gate_count: int = 0
        self.stage018_regime_gate_reduced_volume: int = 0
        self.stage018_regime_by_date = _stage018_load_regime_map(
            str(getattr(self, "stage018_market_daily_path", str(MARKET_DAILY_PATH)) or MARKET_DAILY_PATH)
        )

    def _plan_flat_entry_candidates(self, day_contexts: list[Any]) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        if not self.enable_stage018_regime_pilot_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            bar = plan.get("target_bar")
            bar_datetime = getattr(bar, "datetime", None)
            date_key = pd.Timestamp(bar_datetime).date().isoformat() if bar_datetime is not None else ""
            sizing = dict(plan.get("sizing") or {})
            selected_after, fields = _stage018_apply_regime_pilot_gate(
                sizing=sizing,
                entry_context="flat_entry",
                regime_info=self.stage018_regime_by_date.get(date_key),
                min_position_size=int(getattr(self, "min_position_size", 1) or 1),
                enabled=bool(self.enable_stage018_regime_pilot_gate),
                target_regime=str(self.stage018_regime_gate_target_regime),
                pilot_min_volume=int(self.stage018_regime_pilot_min_volume),
            )
            sizing.update(fields)
            plan["sizing"] = sizing
            if int(fields["stage018_regime_gate_applied"]) != 1:
                continue

            sizing["selected_volume"] = selected_after
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage018_regime_pilot_gate_zero"

            event = self._stage018_event_from_plan(str(product_vt_symbol), plan, fields)
            self.stage018_regime_gate_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage018_regime_gate_count += 1
            self.stage018_regime_gate_reduced_volume += int(fields["stage018_regime_gate_reduced_volume"])
        return plans

    def _stage018_event_from_plan(
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
            "reason": "stage018_regime_pilot_gate",
            "volume": int(fields["stage018_regime_gate_selected_volume_after"]),
            "price": close_price,
            "entry_context": "flat_entry",
            "signal": str(plan.get("signal") or ""),
            "candidate_status_after": str(plan.get("candidate_status") or ""),
            "skip_reason_after": str(plan.get("skip_reason") or ""),
            **fields,
        }


def _stage018_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s013._stage013_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage018 regime pilot gate",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage018 isolated research candidate. "
            "When prior-day market state is high-vol/low-efficiency, flat-entry sizing is reduced to a single-contract "
            "pilot; no product/date/direction blacklist and no official live config mutation."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage018_regime_pilot_gate": True,
        "stage018_regime_gate_target_regime": STAGE018_TARGET_REGIME,
        "stage018_regime_pilot_min_volume": STAGE018_PILOT_MIN_VOLUME,
        "stage018_market_daily_path": str(MARKET_DAILY_PATH),
    }
    result = dict(profile)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage018RegimePilotGate
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return result


def _run_live_stage018(
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
        profile = _stage018_profile(metadata)
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
    intraday_event_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage018] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_live_stage018(metadata, start, REQUESTED_END)

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

    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    regime_events = (
        trade_events[trade_events["reason"].astype(str).eq("stage018_regime_pilot_gate")].copy()
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
        "intraday_events": (
            pd.concat(intraday_event_frames, ignore_index=True, sort=False) if intraday_event_frames else pd.DataFrame()
        ),
        "regime_gate_events": regime_events,
    }


def _retention_summary(candidate_summary: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(s006.SUMMARY_PATH, encoding="utf-8-sig")
    cols = ["requested_start_month", "total_return_pct", "end_equity", "max_dd_pct", "sharpe"]
    merged = base[cols].merge(
        candidate_summary[cols],
        on="requested_start_month",
        how="inner",
        suffixes=("_base_stage006", "_stage018"),
    )
    merged["stage018_vs_base_return_ratio"] = (
        pd.to_numeric(merged["total_return_pct_stage018"], errors="coerce")
        / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
    )
    merged["passes_80pct_retention"] = (
        pd.to_numeric(merged["total_return_pct_stage018"], errors="coerce")
        >= pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce") * 0.8
    ).astype("int64")
    return merged


def _goal_audit(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit_curves = curves[["requested_start_month", "date", "account_equity"]].copy()
    audit_curves.rename(columns={"account_equity": "equity"}, inplace=True)
    audit_curves["variant"] = "stage018_engine"
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
    axes[0].set_title("Stage018 Absolute Account Equity By Cold Start")
    axes[0].set_ylabel("account equity")
    axes[1].set_title("Stage018 Drawdown By Cold Start")
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
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(GOAL_AUDIT_CHART_PATH, dpi=160)
    plt.close(fig)


def _stage018_metrics(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    regime_events: pd.DataFrame,
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
        "regime_gate_event_count": int(len(regime_events)),
        "regime_gate_reduced_volume_sum": (
            int(
                pd.to_numeric(
                    regime_events.get("stage018_regime_gate_reduced_volume", pd.Series(dtype=float)),
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
            if not regime_events.empty
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
    regime_events: pd.DataFrame,
    ai_month_audit: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} high-vol/low-efficiency 小风险试探真实引擎",
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
        "- 趋势跟随资料支持用波动、趋势效率、广度识别不利环境，但不支持复制固定阈值或简单高波动禁开。",
        "- 本阶段采纳 Stage017 的低自由度形状，并改为前一交易日可知的 causal expanding quantile，避免同日和未来信息泄漏。",
        "- 否决：高波动一刀切、按 `2022-07`、品种、方向或 source_start 黑名单化。",
        "",
        "## 参数",
        "",
        f"- `stage018_target_regime`: `{STAGE018_TARGET_REGIME}`",
        f"- `stage018_min_history_days`: `{STAGE018_MIN_HISTORY_DAYS}`",
        f"- `stage018_pilot_min_volume`: `{STAGE018_PILOT_MIN_VOLUME}`",
        "- causal 口径：用前一交易日 market daily 状态；vol/eff 分桶仅使用此前历史 expanding quantile。",
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
        "## Stage018 触发事件",
        "",
        _md_table(
            regime_events[
                [
                    "requested_start_month",
                    "date",
                    "product_vt_symbol",
                    "direction",
                    "stage018_regime_gate_joint_regime",
                    "stage018_regime_gate_source_date",
                    "stage018_regime_gate_selected_volume_before",
                    "stage018_regime_gate_selected_volume_after",
                    "stage018_regime_gate_reduced_volume",
                ]
            ].head(40)
            if not regime_events.empty
            else regime_events,
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
    record_path = stage_dir / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage018_regime_pilot_gate_engine.md"
    metrics = decision["metrics"]
    lines = [
        "# Stage018 high-vol/low-efficiency 小风险试探真实引擎",
        "",
        f"- 记录时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        "- 新增参数：`enable_stage018_regime_pilot_gate=True`、"
        f"`stage018_regime_gate_target_regime={STAGE018_TARGET_REGIME}`、"
        f"`stage018_regime_pilot_min_volume={STAGE018_PILOT_MIN_VOLUME}`。",
        "- 修改参数：无，官方线上 C9/15w 配置未改；本阶段只在独立研究 profile 内覆盖。",
        "- 删除参数：无。",
        "- 规则：前一交易日 causal 市场状态为 `high_vol_low_eff` 时，`flat_entry` 新开仓降到 1 手试探；不按品种、日期、方向黑名单。",
        "",
        "## 回测参数",
        "",
        f"- 起点：`2018-01-01` 起每半年一个独立冷启动，共 `{metrics['sample_count']}` 个。",
        f"- 终点：`{REQUESTED_END.date()}`。",
        f"- 资金：`{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- regime 数据：`{MARKET_DAILY_PATH}`；最小历史 `{STAGE018_MIN_HISTORY_DAYS}` 交易日。",
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
        f"- Stage018 触发次数：`{metrics['regime_gate_event_count']}`；累计减少手数："
        f"`{metrics['regime_gate_reduced_volume_sum']}`。",
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
            "- 若未满足严格任意结束日目标，不能继续扫 regime 分位数、窗口或手数；应归因触发事件是否错杀右尾。",
            "- 鸡蛋仍不能直接塞入共享 AI topN；如果 Stage018 有价值，再单独做非挤占小预算真实引擎。",
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
    regime_table = _stage018_build_causal_regime_table(MARKET_DAILY_PATH)
    regime_table.to_csv(REGIME_TABLE_PATH, index=False, encoding="utf-8-sig")

    frames = _run_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    candidates = frames["entry_candidates"]
    regime_events = frames["regime_gate_events"]

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
    regime_events.to_csv(REGIME_GATE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_pool_audit.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    to_final.to_csv(GOAL_TO_FINAL_PATH, index=False, encoding="utf-8-sig")
    fixed.to_csv(GOAL_FIXED_HORIZON_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")

    metrics = _stage018_metrics(summary, aggregate, retention, regime_events, ai_month_audit)
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
        "stage018_parameters": {
            "target_regime": STAGE018_TARGET_REGIME,
            "min_history_days": STAGE018_MIN_HISTORY_DAYS,
            "pilot_min_volume": STAGE018_PILOT_MIN_VOLUME,
            "vol_high_quantile": STAGE018_VOL_HIGH_Q,
            "eff_low_quantile": STAGE018_EFF_LOW_Q,
            "causal_effective_date": "previous_market_date_state_shifted_to_next_trade_date",
        },
        "ai_pool_audit": ai_pool_meta,
        "metrics": metrics,
        "decision": (
            "stage018_strict_goal_pass_research_candidate_needs_review"
            if strict_goal_pass
            else "stage018_goal_not_met_keep_or_reject_after_attribution"
        ),
        "strategy_changed": True,
        "official_live_strategy_changed": False,
        "true_engine": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following references support regime/volatility awareness, but not copied thresholds or broad high-vol "
            "bans. Stage018 freezes one causal high-vol/low-efficiency pilot gate for true-engine testing."
        ),
        "overfit_reflection_before": (
            "否。本阶段只把 Stage017 低自由度信号写成一个 causal 真实引擎，不按日期、品种、方向或 source_start 黑名单化。"
        ),
        "continue_value_before": (
            "是。Stage017 显示 high-vol/low-efficiency 在曲线、entry 和 AI top8 上同向偏弱，值得真实引擎验证。"
        ),
        "overfit_reflection_after": (
            "否，但如果继续调整 quantile、min_history、手数或叠加 drawdown/active 条件来贴合最差窗口，就会过拟合。"
        ),
        "continue_value_after": (
            "取决于严格目标与收益保留结果；若不能降低任意结束日负窗口且保留右尾，就应回到只读归因或换新信息源。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "regime_gate_events": str(REGIME_GATE_EVENTS_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "ai_pool_audit": str(AI_POOL_AUDIT_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_to_final": str(GOAL_TO_FINAL_PATH),
            "goal_fixed_horizon": str(GOAL_FIXED_HORIZON_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "regime_table": str(REGIME_TABLE_PATH),
            "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "goal_audit_chart": str(GOAL_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    _write_report(decision, summary, aggregate, worst, retention, regime_events, ai_month_audit)
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
