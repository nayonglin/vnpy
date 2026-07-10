from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import itertools
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage121"
MODEL_TAG = "stage121_stage074_cold_start_ramp_true_engine_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1, 7)
LATEST_START = pd.Timestamp("2026-01-01")
CAPITAL = float(OFFICIAL_LIVE_CAPITAL)
RAMP_FLOOR = 0.35
RAMP_TRADING_DAYS = 252

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage121_stage074_cold_start_ramp_true_engine"
STAGES_DIR = LINE_DIR / "stages"
STAGE167_OUT = PORTFOLIO_DIR / "backtest_outputs"
STAGE167_CURVES_PATH = (
    STAGE167_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
RAW_COMBINED_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_raw_combined_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_ai_month_audit_{MODEL_TAG}.csv"
RAMP_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ramp_audit_{MODEL_TAG}.csv"
CHART_METRICS_PATH = OUT / f"{OUTPUT_PREFIX}_metrics_by_start_{MODEL_TAG}.png"
CHART_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_equity_focus_from_2021_07_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

OFFICIAL_VERSION = "official_c9_15w_reference"
CANDIDATE_VERSION = "stage074_cold_start_ramp_true_engine"
VARIANTS = (OFFICIAL_VERSION, CANDIDATE_VERSION)
VARIANT_LABELS = {
    OFFICIAL_VERSION: "Official C9/15w",
    CANDIDATE_VERSION: "Stage074 cold-start ramp true engine",
}
VARIANT_COLORS = {
    OFFICIAL_VERSION: "#111827",
    CANDIDATE_VERSION: "#2563eb",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _naive_day(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp.normalize()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _max_consecutive_true(mask: pd.Series) -> int:
    runs = (len(list(group)) for value, group in itertools.groupby(mask.astype(bool).tolist()) if value)
    return int(max(runs, default=0))


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= min(REQUESTED_END, LATEST_START):
                starts.append(start)
    return starts


def _age_ramp_multiplier(age_index: int, *, floor: float = RAMP_FLOOR, days: int = RAMP_TRADING_DAYS) -> float:
    floor_value = max(0.0, min(1.0, float(floor)))
    ramp_days = max(1, int(days))
    if ramp_days <= 1:
        return floor_value if age_index <= 0 else 1.0
    age_for_risk = max(float(age_index) - 1.0, 0.0)
    ramp = floor_value + (1.0 - floor_value) * min(age_for_risk, ramp_days - 1.0) / (ramp_days - 1.0)
    return float(np.clip(ramp, floor_value, 1.0))


class QmtRollPortfolioStrategyStage121ColdStartRamp(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage121_cold_start_ramp: bool = False
    stage121_cold_start_ramp_floor: float = RAMP_FLOOR
    stage121_cold_start_ramp_trading_days: int = RAMP_TRADING_DAYS

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage121_cold_start_ramp",
        "stage121_cold_start_ramp_floor",
        "stage121_cold_start_ramp_trading_days",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage121_cold_start_ramp_multiplier",
        "stage121_raw_estimated_equity",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage121_cold_start_ramp_multiplier: float = 1.0
        self.stage121_raw_estimated_equity: float = self.base_capital

    def _stage121_enabled(self) -> bool:
        return bool(self.enable_stage121_cold_start_ramp)

    def _stage121_trade_day_index(self, dt: Any) -> int:
        if not self.available_trade_dates:
            return 0
        current = _naive_day(dt)
        start = _naive_day(self.trade_start_date) if str(self.trade_start_date or "").strip() else pd.Timestamp(self.available_trade_dates[0])
        dates = pd.DatetimeIndex([_naive_day(item) for item in self.available_trade_dates])
        start_index = int(dates.searchsorted(start, side="left"))
        current_index = int(dates.searchsorted(current, side="left"))
        if current_index >= len(dates):
            current_index = len(dates) - 1
        return max(0, current_index - start_index)

    def _stage121_multiplier_for_date(self, dt: Any) -> float:
        if not self._stage121_enabled():
            return 1.0
        index = self._stage121_trade_day_index(dt)
        return _age_ramp_multiplier(
            index,
            floor=float(self.stage121_cold_start_ramp_floor),
            days=int(self.stage121_cold_start_ramp_trading_days),
        )

    def _stage121_ramp_fields(self, dt: Any) -> dict[str, Any]:
        multiplier = self._stage121_multiplier_for_date(dt)
        return {
            "stage121_cold_start_ramp_enabled": int(self._stage121_enabled()),
            "stage121_cold_start_ramp_floor": float(self.stage121_cold_start_ramp_floor),
            "stage121_cold_start_ramp_trading_days": int(self.stage121_cold_start_ramp_trading_days),
            "stage121_cold_start_ramp_trade_day_index": self._stage121_trade_day_index(dt),
            "stage121_cold_start_ramp_multiplier": multiplier,
            "stage121_raw_estimated_equity": float(self.stage121_raw_estimated_equity or self.estimated_equity or self.base_capital),
        }

    def _refresh_risk_state(self, bars: dict[str, Any]) -> None:
        super()._refresh_risk_state(bars)
        if self._stage121_enabled():
            current = self.current_bar_date
            if current is None and bars:
                current = next(iter(bars.values())).datetime
            self.stage121_raw_estimated_equity = float(self.estimated_equity or self.base_capital)
            self.stage121_cold_start_ramp_multiplier = self._stage121_multiplier_for_date(current)

    def _sizing_equity_snapshot(self) -> dict[str, float | int]:
        fields = dict(super()._sizing_equity_snapshot())
        if self._stage121_enabled():
            multiplier = self._stage121_multiplier_for_date(self.current_bar_date or pd.Timestamp(self.trade_start_date))
            raw_sizing_equity = max(0.0, float(fields.get("sizing_equity") or 0.0))
            raw_effective_cap = max(0.0, float(fields.get("effective_sizing_equity_cap") or raw_sizing_equity))
            ramped_sizing_equity = max(0.0, raw_sizing_equity * multiplier)
            fields["stage121_unramped_sizing_equity"] = raw_sizing_equity
            fields["stage121_ramped_sizing_equity"] = ramped_sizing_equity
            fields["sizing_equity"] = min(raw_sizing_equity, ramped_sizing_equity)
            fields["effective_sizing_equity_cap"] = min(raw_effective_cap, fields["sizing_equity"])
            fields.update(self._stage121_ramp_fields(self.current_bar_date or pd.Timestamp(self.trade_start_date)))
        return fields

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: Any,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sizing = dict(
            super()._calculate_entry_sizing(
                vt_symbol,
                direction,
                bar,
                history,
                signal_data,
                risk_mode_override=risk_mode_override,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot,
            )
        )
        if self._stage121_enabled():
            sizing.update(self._stage121_ramp_fields(getattr(bar, "datetime", self.current_bar_date)))
        return sizing


def _stage121_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage121_official_c9_15w_stage074_cold_start_ramp"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage121 official C9/15w with Stage074 cold-start capital ramp",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage121 true-engine validation of upstream Stage074 cold-start ramp. "
            "The ramp is applied to the engine's sizing/risk equity, not to a completed equity curve."
        ),
    )
    overrides = {
        **spec.overrides,
        **s901.build_official_live_strategy_overrides(),
        "enable_stage121_cold_start_ramp": True,
        "stage121_cold_start_ramp_floor": RAMP_FLOOR,
        "stage121_cold_start_ramp_trading_days": RAMP_TRADING_DAYS,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = QmtRollPortfolioStrategyStage121ColdStartRamp
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_stage121(metadata: dict[str, Any], analysis_start: pd.Timestamp, analysis_end: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = analysis_start.normalize()
        s847.END = analysis_end.normalize()
        profile = _stage121_profile(metadata)
        combined, frames = s847._run_profile(profile, metadata)
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


def _read_official_curves() -> pd.DataFrame:
    frame = pd.read_csv(STAGE167_CURVES_PATH)
    frame = frame[frame["requested_start_month"].astype(str).isin([_start_month_text(item) for item in _build_start_dates()])].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(REQUESTED_END)].copy()
    frame["version"] = OFFICIAL_VERSION
    frame["variant_label"] = VARIANT_LABELS[OFFICIAL_VERSION]
    frame["account_capital_for_metrics"] = CAPITAL
    frame["account_equity_for_metrics"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    return frame


def _candidate_curve(combined: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    frame = combined.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    frame["version"] = CANDIDATE_VERSION
    frame["variant_label"] = VARIANT_LABELS[CANDIDATE_VERSION]
    frame["requested_start"] = _date_text(start)
    frame["requested_start_month"] = _start_month_text(start)
    frame["requested_end"] = _date_text(REQUESTED_END)
    frame["account_capital_for_metrics"] = CAPITAL
    frame["account_equity_for_metrics"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    return frame


def _flat_candidate_curve(dates: pd.Series, start: pd.Timestamp) -> pd.DataFrame:
    frame = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce").dt.normalize()})
    frame = frame.dropna(subset=["date"]).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    for column in ["trade_count", "turnover", "commission", "slippage", "trading_pnl", "holding_pnl", "total_pnl", "net_pnl"]:
        frame[column] = 0.0
    frame["account_equity"] = CAPITAL
    frame["stage"] = STAGE
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    frame["version"] = CANDIDATE_VERSION
    frame["variant_label"] = VARIANT_LABELS[CANDIDATE_VERSION]
    frame["requested_start"] = _date_text(start)
    frame["requested_start_month"] = _start_month_text(start)
    frame["requested_end"] = _date_text(REQUESTED_END)
    frame["account_capital_for_metrics"] = CAPITAL
    frame["account_equity_for_metrics"] = CAPITAL
    frame["stage121_flat_no_trade_curve_expanded"] = 1
    return frame


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity_for_metrics"], errors="coerce").ffill()
    capital = float(frame["account_capital_for_metrics"].iloc[0])
    drawdown = _drawdown_pct(equity)
    below = equity < capital - 1e-9
    min_idx = int(equity.idxmin())
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": str(frame["version"].iloc[0]),
        "variant_label": str(frame["variant_label"].iloc[0]),
        "requested_start_month": str(frame["requested_start_month"].iloc[0]),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.iloc[min_idx]),
        "min_equity_date": _date_text(frame["date"].iloc[min_idx]),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(frame.get("broker10_margin_to_equity_pct", pd.Series(dtype=float)), errors="coerce").max()
        )
        if "broker10_margin_to_equity_pct" in frame.columns
        else np.nan,
    }


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq(OFFICIAL_VERSION)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for version in VARIANTS:
        group = summary[summary["version"].eq(version)].copy()
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_drawdown_pct"], errors="coerce")
        days = pd.to_numeric(group["days_below_initial"], errors="coerce")
        consecutive = pd.to_numeric(group["max_consecutive_below_initial_days"], errors="coerce")
        retention: list[float] = []
        for _, row in group.iterrows():
            start = str(row["requested_start_month"])
            if start in official.index and float(official.loc[start, "total_return_pct"]):
                retention.append(float(row["total_return_pct"] / official.loc[start, "total_return_pct"]))
        rows.append(
            {
                "version": version,
                "variant_label": VARIANT_LABELS[version],
                "start_count": int(len(group)),
                "positive_count": int(returns.gt(0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "min_return_retention_ratio": float(np.nanmin(retention)) if retention else np.nan,
                "median_return_retention_ratio": float(np.nanmedian(retention)) if retention else np.nan,
                "worst_drawdown_pct": float(dds.min()),
                "median_drawdown_pct": float(dds.median()),
                "max_days_below_initial": int(days.max()),
                "median_days_below_initial": float(days.median()),
                "max_consecutive_below_initial_days": int(consecutive.max()),
                "median_consecutive_below_initial_days": float(consecutive.median()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "total_trade_count_sum": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _retention(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[summary["version"].eq(OFFICIAL_VERSION)].set_index("requested_start_month")
    rows: list[dict[str, Any]] = []
    for _, row in summary[summary["version"].eq(CANDIDATE_VERSION)].iterrows():
        start = str(row["requested_start_month"])
        base = official.loc[start]
        rows.append(
            {
                "requested_start_month": start,
                "return_delta_pct": float(row["total_return_pct"] - base["total_return_pct"]),
                "return_retention_ratio": float(row["total_return_pct"] / base["total_return_pct"])
                if float(base["total_return_pct"])
                else np.nan,
                "drawdown_delta_pct": float(row["max_drawdown_pct"] - base["max_drawdown_pct"]),
                "days_below_delta": int(row["days_below_initial"] - base["days_below_initial"]),
                "max_consecutive_below_delta": int(
                    row["max_consecutive_below_initial_days"] - base["max_consecutive_below_initial_days"]
                ),
                "official_return_pct": float(base["total_return_pct"]),
                "candidate_return_pct": float(row["total_return_pct"]),
                "official_max_drawdown_pct": float(base["max_drawdown_pct"]),
                "candidate_max_drawdown_pct": float(row["max_drawdown_pct"]),
                "official_days_below_initial": int(base["days_below_initial"]),
                "candidate_days_below_initial": int(row["days_below_initial"]),
                "official_max_consecutive_below_initial_days": int(base["max_consecutive_below_initial_days"]),
                "candidate_max_consecutive_below_initial_days": int(row["max_consecutive_below_initial_days"]),
            }
        )
    return pd.DataFrame(rows)


def _ramp_audit(entry_candidates: pd.DataFrame) -> pd.DataFrame:
    if entry_candidates.empty or "stage121_cold_start_ramp_multiplier" not in entry_candidates.columns:
        if not entry_candidates.empty and {"estimated_equity", "sizing_equity"}.issubset(entry_candidates.columns):
            estimated = pd.to_numeric(entry_candidates["estimated_equity"], errors="coerce")
            sizing = pd.to_numeric(entry_candidates["sizing_equity"], errors="coerce")
            ratio = (sizing / estimated.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
            valid_ratio = ratio.dropna()
            return pd.DataFrame(
                [
                    {
                        "rows": int(len(entry_candidates)),
                        "has_stage121_fields": 0,
                        "derived_from_sizing_equity": 1,
                        "enabled_rows": int(len(valid_ratio)),
                        "min_multiplier": float(valid_ratio.min()) if not valid_ratio.empty else np.nan,
                        "max_multiplier": float(valid_ratio.max()) if not valid_ratio.empty else np.nan,
                        "invalid_multiplier_rows": int((valid_ratio.lt(RAMP_FLOOR - 0.02) | valid_ratio.gt(1.0 + 1e-9)).sum()),
                        "post_ramp_not_one_rows": -1,
                        "note": "stage121 fields are not whitelisted in entry candidate snapshots; ratio derives from sizing_equity/estimated_equity.",
                    }
                ]
            )
        return pd.DataFrame(
            [
                {
                    "rows": int(len(entry_candidates)),
                    "has_stage121_fields": 0,
                    "derived_from_sizing_equity": 0,
                    "enabled_rows": 0,
                    "min_multiplier": np.nan,
                    "max_multiplier": np.nan,
                    "invalid_multiplier_rows": 0,
                    "post_ramp_not_one_rows": 0,
                    "note": "no entry candidates available.",
                }
            ]
        )
    frame = entry_candidates.copy()
    multiplier = pd.to_numeric(frame["stage121_cold_start_ramp_multiplier"], errors="coerce")
    day_index = pd.to_numeric(frame.get("stage121_cold_start_ramp_trade_day_index", pd.Series(dtype=float)), errors="coerce")
    return pd.DataFrame(
        [
            {
                "rows": int(len(frame)),
                "has_stage121_fields": 1,
                "derived_from_sizing_equity": 0,
                "enabled_rows": int(pd.to_numeric(frame.get("stage121_cold_start_ramp_enabled", 0), errors="coerce").fillna(0).eq(1).sum()),
                "min_multiplier": float(multiplier.min()),
                "max_multiplier": float(multiplier.max()),
                "invalid_multiplier_rows": int((multiplier.lt(RAMP_FLOOR - 1e-12) | multiplier.gt(1.0 + 1e-12)).sum()),
                "post_ramp_not_one_rows": int((day_index.ge(RAMP_TRADING_DAYS + 1) & multiplier.lt(1.0 - 1e-12)).sum()),
                "note": "direct stage121 fields present.",
            }
        ]
    )


def build() -> dict[str, pd.DataFrame]:
    metadata = s847.s513._metadata()
    official_curves = _read_official_curves()
    candidate_curves: list[pd.DataFrame] = []
    raw_combined_frames: list[pd.DataFrame] = []
    entry_candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []

    starts = _build_start_dates()
    for index, start in enumerate(starts, start=1):
        print(f"[stage121] run {index}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = _run_stage121(metadata, start, REQUESTED_END)
        combined = combined.copy()
        combined["requested_start"] = _date_text(start)
        combined["requested_start_month"] = _start_month_text(start)
        combined["requested_end"] = _date_text(REQUESTED_END)
        raw_combined_frames.append(combined)
        trades_frame = frames.get("trades", pd.DataFrame()).copy()
        curve = _candidate_curve(combined, start)
        if len(curve) == 1 and trades_frame.empty:
            official_dates = official_curves[official_curves["requested_start_month"].astype(str).eq(_start_month_text(start))]["date"]
            if not official_dates.empty:
                curve = _flat_candidate_curve(official_dates, start)
        candidate_curves.append(curve)
        for name, target in (
            ("entry_candidates", entry_candidate_frames),
            ("trades", trade_frames),
            ("trade_events", trade_event_frames),
        ):
            frame = frames.get(name, pd.DataFrame()).copy()
            if frame.empty:
                continue
            frame["stage"] = STAGE
            frame["model_tag"] = MODEL_TAG
            frame["line_id"] = LINE_ID
            frame["version"] = CANDIDATE_VERSION
            frame["requested_start"] = _date_text(start)
            frame["requested_start_month"] = _start_month_text(start)
            frame["requested_end"] = _date_text(REQUESTED_END)
            target.append(frame)

    candidate = pd.concat(candidate_curves, ignore_index=True, sort=False)
    raw_combined = pd.concat(raw_combined_frames, ignore_index=True, sort=False)
    entry_candidates = pd.concat(entry_candidate_frames, ignore_index=True, sort=False) if entry_candidate_frames else pd.DataFrame()
    trades = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    trade_events = pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame()
    curves = pd.concat([official_curves, candidate], ignore_index=True, sort=False)
    curves = curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby(["version", "requested_start_month"])])
    summary = summary.sort_values(["requested_start_month", "version"]).reset_index(drop=True)
    ai_month_audit = pd.DataFrame()
    if not entry_candidates.empty:
        pool, _pool_audit = s167._load_ai_pool()
        ai_month_audit = s167._ai_month_audit(entry_candidates, summary[summary["version"].eq(CANDIDATE_VERSION)], pool)
    return {
        "curves": curves,
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "retention": _retention(summary),
        "raw_combined": raw_combined,
        "entry_candidates": entry_candidates,
        "trades": trades,
        "trade_events": trade_events,
        "ai_month_audit": ai_month_audit,
        "ramp_audit": _ramp_audit(entry_candidates),
    }


def plot_outputs(results: dict[str, pd.DataFrame]) -> None:
    curves = results["curves"].copy()
    summary = results["summary"].copy()
    starts = sorted(summary["requested_start_month"].astype(str).unique())
    x = np.arange(len(starts))
    width = 0.35

    fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=True, constrained_layout=True)
    for offset, version in zip((-width / 2, width / 2), VARIANTS, strict=True):
        group = summary[summary["version"].eq(version)].set_index("requested_start_month").loc[starts]
        axes[0].bar(x + offset, group["total_return_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[1].bar(x + offset, group["max_drawdown_pct"], width=width, label=VARIANT_LABELS[version], color=VARIANT_COLORS[version])
        axes[2].bar(
            x + offset,
            group["max_consecutive_below_initial_days"],
            width=width,
            label=VARIANT_LABELS[version],
            color=VARIANT_COLORS[version],
        )
    axes[0].set_title("Terminal return by half-year start")
    axes[0].set_ylabel("return %")
    axes[1].set_title("Max drawdown by half-year start")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_title("Max consecutive days below initial capital")
    axes[2].set_ylabel("days")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(starts, rotation=45, ha="right")
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].legend(ncol=2)
    fig.savefig(CHART_METRICS_PATH, dpi=160)
    plt.close(fig)

    focus_starts = [item for item in starts if item >= "2021-07"]
    fig, axes = plt.subplots(2, 1, figsize=(18, 12), sharex=True, constrained_layout=True)
    for ax, version in zip(axes, VARIANTS, strict=True):
        subset = curves[curves["version"].eq(version) & curves["requested_start_month"].astype(str).isin(focus_starts)]
        for start, group in subset.groupby("requested_start_month", sort=True):
            group = group.sort_values("date")
            ax.plot(group["date"], group["account_equity_for_metrics"], linewidth=1.0, alpha=0.82, label=str(start))
        ax.axhline(CAPITAL, color="#6b7280", linestyle="--", linewidth=0.9)
        ax.set_title(VARIANT_LABELS[version])
        ax.set_ylabel("account equity")
        ax.grid(True, alpha=0.25)
        ax.legend(ncol=5, fontsize=8)
    axes[-1].set_xlabel("date")
    fig.savefig(CHART_EQUITY_PATH, dpi=160)
    plt.close(fig)


def write_outputs(results: dict[str, pd.DataFrame]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    results["curves"].to_csv(CURVES_PATH, index=False, compression="gzip")
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["retention"].to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    results["raw_combined"].to_csv(RAW_COMBINED_PATH, index=False, compression="gzip")
    results["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    results["trades"].to_csv(TRADES_PATH, index=False, compression="gzip")
    results["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, compression="gzip")
    results["ai_month_audit"].to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    results["ramp_audit"].to_csv(RAMP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    plot_outputs(results)

    variant_summary = results["variant_summary"].copy()
    retention = results["retention"].copy()
    ai_audit = results["ai_month_audit"].copy()
    ramp_audit = results["ramp_audit"].copy()
    fail_ai = int(ai_audit["status"].astype(str).eq("FAIL").sum()) if not ai_audit.empty and "status" in ai_audit.columns else 0
    candidate = variant_summary[variant_summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    official = variant_summary[variant_summary["version"].eq(OFFICIAL_VERSION)].iloc[0].to_dict()
    retention_ok = float(candidate["median_return_retention_ratio"]) >= 0.5
    dd_improved = float(candidate["worst_drawdown_pct"]) > float(official["worst_drawdown_pct"])
    underwater_improved = int(candidate["max_consecutive_below_initial_days"]) < int(official["max_consecutive_below_initial_days"])
    ramp_ok = (
        int(ramp_audit["has_stage121_fields"].iloc[0]) == 1
        and int(ramp_audit["invalid_multiplier_rows"].iloc[0]) == 0
        and int(ramp_audit["post_ramp_not_one_rows"].iloc[0]) == 0
    )
    promoted = bool(retention_ok and dd_improved and underwater_improved and fail_ai == 0 and ramp_ok)
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage121_stage074_ramp_true_engine_promoted_to_review" if promoted else "stage121_stage074_ramp_true_engine_not_promoted",
        "promoted_to_next_review": promoted,
        "official_summary": official,
        "candidate_summary": candidate,
        "retention_ok_median_ge_50pct": retention_ok,
        "worst_drawdown_improved": dd_improved,
        "max_consecutive_underwater_improved": underwater_improved,
        "ai_fail_rows": fail_ai,
        "ramp_audit": ramp_audit.iloc[0].to_dict() if not ramp_audit.empty else {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Stage121 Stage074 cold-start ramp true engine",
        "",
        "## 口径",
        "",
        "- A：读取 Stage167 已有正式 C9/15w 多周期真实引擎曲线。",
        "- C：正式 C9/15w 信号、AI、0.5R 止损重试、保证金和整数手不变；仅把上游 Stage074 的冷启动资金 ramp 接入真实引擎 sizing/risk equity。",
        f"- 固定参数：floor `{RAMP_FLOOR}`，ramp `{RAMP_TRADING_DAYS}` 个交易日；不扫参。",
        "- 本阶段不连接 CTP、不读取账户、不调用订单 API。",
        "",
        "## 汇总",
        "",
        _md_table(variant_summary),
        "",
        "## 逐起点对比",
        "",
        _md_table(retention.round(6), 80),
        "",
        "## Ramp 审计",
        "",
        _md_table(ramp_audit, 20),
        "",
        "## AI 审计状态",
        "",
        _md_table(ai_audit.groupby("status", dropna=False).size().reset_index(name="rows") if not ai_audit.empty else pd.DataFrame()),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 是否进入下一步 review：`{promoted}`。",
        "",
        "## 输出文件",
        "",
        f"- curves：`{CURVES_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- variant_summary：`{VARIANT_SUMMARY_PATH}`",
        f"- retention_vs_official：`{RETENTION_PATH}`",
        f"- entry_candidates：`{ENTRY_CANDIDATES_PATH}`",
        f"- trades：`{TRADES_PATH}`",
        f"- AI month audit：`{AI_MONTH_AUDIT_PATH}`",
        f"- ramp audit：`{RAMP_AUDIT_PATH}`",
        f"- metrics chart：`{CHART_METRICS_PATH}`",
        f"- equity chart：`{CHART_EQUITY_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage121_stage074_cold_start_ramp_true_engine.md"
    stage_record = [
        "# Stage121 Stage074 cold-start ramp true engine",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 阶段性质：上游 Stage074 cold-start ramp 真引擎 A/C 验证。",
        f"- 是否重要突破：{'是，若后续 review 通过可进入候选讨论' if promoted else '否，真引擎未通过晋级条件'}",
        "- 是否触发A/B：是；A=正式 C9/15w，C=正式 C9/15w + Stage074 cold-start ramp。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk/vn.py/PySystemTrade 等资料支持用可复验 backtest 和 capital correction 检查资金层，但交易信号和资金层要分开看。",
        "- 我的判断：Stage074 是账户/资金层，不是 alpha；必须用真实引擎验证整数手、保证金、止损重试事件顺序后才有意义。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无正式入口修改。",
        "- 删除脚本：无。",
        f"- 新增参数：`enable_stage121_cold_start_ramp=True`、`stage121_cold_start_ramp_floor={RAMP_FLOOR}`、`stage121_cold_start_ramp_trading_days={RAMP_TRADING_DAYS}`。",
        "- 修改参数：无正式交易信号参数；只改变研究候选的 sizing/risk equity。",
        "- 删除参数：无。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：`2020-01` 到 `2026-01` 逐半年起点，统一终点 `2026-06-30`。",
        f"- 账户规模：A/C 均 `{CAPITAL:,.0f}`。",
        "- 成本口径：沿用正式真实引擎成本。",
        "- 样本过滤：无。",
        "- 策略/归因口径：真实引擎；ramp 在每日风控刷新后进入 sizing/risk equity，不是事后曲线乘数。",
        "",
        "## 结果",
        "",
        _md_table(variant_summary),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- daily：`{CURVES_PATH}`",
        f"- orders：`{TRADES_PATH}`",
        f"- quality：`{AI_MONTH_AUDIT_PATH}`",
        f"- chart：`{CHART_EQUITY_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`。",
        f"- 是否进入下一步：`{promoted}`。",
        "- 下一步：若未通过，停止 cold-start ramp floor/days 救参；若通过，先做独立 review，再考虑更密日级起点。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。floor 和 ramp_days 固定继承 Stage074，没有根据本次结果调整。",
        f"- 运行后判断：{'否，但仍需独立 review；若后续改 floor/days 就会变成过拟合' if promoted else '否。本次是冻结验证；失败后继续扫 floor/days 会变成过拟合'}。",
        "- 原因：本阶段只验证 proxy 能否穿过真实引擎，不按坏窗口反推参数。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有。Stage074 proxy 是上游有防守效果的账户外层，必须补真实引擎证据。",
        f"- 运行后判断：{'有，先进入 review 而不是直接晋级' if promoted else '有限，不建议继续救这个线性 ramp 形状'}。",
        "- 原因：真引擎结果决定整数手、保证金和止损重试顺序是否保留 proxy 优势。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是，记录本阶段结论。",
        "- 是否更新 `research/registry.md`：否。",
        "- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要条目。",
    ]
    stage_path.write_text("\n".join(stage_record) + "\n", encoding="utf-8")


def main() -> None:
    results = build()
    write_outputs(results)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "summary": results["variant_summary"].to_dict(orient="records"),
                "retention": results["retention"].to_dict(orient="records"),
                "ramp_audit": results["ramp_audit"].to_dict(orient="records"),
                "ai_fail_rows": int(results["ai_month_audit"]["status"].astype(str).eq("FAIL").sum())
                if not results["ai_month_audit"].empty and "status" in results["ai_month_audit"].columns
                else 0,
                "report": str(REPORT_PATH),
                "equity_chart": str(CHART_EQUITY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
