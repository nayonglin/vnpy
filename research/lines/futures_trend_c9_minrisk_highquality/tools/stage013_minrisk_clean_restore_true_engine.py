from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage013"
MODEL_TAG = "stage013_minrisk_clean_restore_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage002_delayed_restore_true_engine as s002
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_minrisk_clean_restore_true_engine"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage013_minrisk_1lot_clean30_restore"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
OBSERVATION_BARS = 30
HEAT_R = 0.50
SCOUT_VOLUME = 1
PER_PAGE = 4
MAX_ATLAS_ROWS = 20

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
COST_STRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
TRADES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
QUALITY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_restore_events_{MODEL_TAG}.csv"
OPEN_ADJUSTMENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_adjustments_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
EVENT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s002._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    return s002._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s002._safe_float(value, default=default)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s002._drawdown_pct(equity)


def _read_required_csv(path: Path) -> pd.DataFrame:
    return s002._read_required_csv(path)


def _normalize_day(value: Any) -> pd.Timestamp:
    return s002.s827._normalize_date(value)


def _to_naive_ts(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _align_timestamp_timezone(value: Any, reference: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    ref = pd.Timestamp(reference)
    if ts.tzinfo is None and ref.tzinfo is not None:
        return ts.tz_localize(ref.tzinfo)
    if ts.tzinfo is not None and ref.tzinfo is None:
        return ts.tz_localize(None)
    return ts


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    return s002._index_for_time(day, value)


class QmtRollPortfolioStrategyStage013MinRiskCleanRestore(s002.s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage013_minrisk_clean_restore: bool = False
    stage013_observation_bars: int = OBSERVATION_BARS
    stage013_heat_r: float = HEAT_R
    stage013_scout_volume: int = SCOUT_VOLUME

    parameters = s002.s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage013_minrisk_clean_restore",
        "stage013_observation_bars",
        "stage013_heat_r",
        "stage013_scout_volume",
    ]
    variables = s002.s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage013_clean_restore_event_count",
        "stage013_clean_restore_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage013_quality_restore_events: list[dict[str, Any]] = []
        self.stage013_open_adjustments: list[dict[str, Any]] = []
        # The Stage002 runner exports these conventional frame names.
        self.stage002_restore_events = self.stage013_quality_restore_events
        self.stage002_open_adjustments = self.stage013_open_adjustments
        self.stage013_clean_restore_event_count: int = 0
        self.stage013_clean_restore_stop_count: int = 0
        self._stage013_pending_restore: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._stage013_reserve_volume_override: dict[str, int] = {}

    def _stage013_pending_key(self, vt_symbol: str, direction: str, value: Any) -> tuple[str, str, str]:
        trade_date = _normalize_day(value).strftime("%Y-%m-%d")
        return str(vt_symbol), str(direction), trade_date

    def _stage013_pop_pending_for_trade(
        self,
        vt_symbol: str,
        direction: str,
        trade_datetime: Any,
    ) -> dict[str, Any] | None:
        exact_key = self._stage013_pending_key(vt_symbol, direction, trade_datetime)
        if exact_key in self._stage013_pending_restore:
            return self._stage013_pending_restore.pop(exact_key)

        trade_day = _normalize_day(trade_datetime)
        candidates: list[tuple[pd.Timestamp, tuple[str, str, str]]] = []
        for key in self._stage013_pending_restore:
            symbol_key, direction_key, pending_day_text = key
            if symbol_key != str(vt_symbol) or direction_key != str(direction):
                continue
            pending_day = pd.Timestamp(pending_day_text)
            lag_days = int((trade_day - pending_day).days)
            if 0 <= lag_days <= 7:
                candidates.append((pending_day, key))
        if not candidates:
            return None
        _, selected_key = max(candidates, key=lambda item: item[0])
        return self._stage013_pending_restore.pop(selected_key)

    def _stage013_entry_day(self, contract_vt_symbol: str, value: Any) -> pd.DataFrame:
        bars = self.stage827_minute_by_symbol.get(str(contract_vt_symbol), pd.DataFrame())
        if bars.empty:
            return pd.DataFrame()
        trade_date = _normalize_day(value)
        return bars[bars["bar_date"].eq(trade_date)].copy().sort_values("bar_datetime").reset_index(drop=True)

    def _stage013_has_observation_window(self, contract_vt_symbol: str, value: Any) -> bool:
        day = self._stage013_entry_day(contract_vt_symbol, value)
        return len(day) >= max(1, int(self.stage013_observation_bars))

    def _reserve_intrabar_entry(
        self,
        product_vt_symbol: str,
        sizing_snapshot: dict[str, Any],
        volume: int,
        *,
        count_active_position: bool,
    ) -> None:
        override = self._stage013_reserve_volume_override.pop(product_vt_symbol, None)
        if override is not None:
            sizing_snapshot = dict(sizing_snapshot)
            sizing_snapshot["selected_volume"] = int(override)
            volume = int(override)
        super()._reserve_intrabar_entry(
            product_vt_symbol,
            sizing_snapshot,
            volume,
            count_active_position=count_active_position,
        )

    def _open_position(
        self,
        state: Any,
        contract_vt_symbol: str,
        direction: str,
        volume: int,
        bar: Any,
        signal: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        sizing_snapshot: dict[str, Any] | None = None,
    ) -> None:
        original_volume = max(0, int(volume))
        enabled = bool(self.enable_stage013_minrisk_clean_restore)
        eligible_signal = str(signal) != "rollover_reopen"
        min_lot = max(1, int(getattr(self, "min_position_size", 1) or 1), int(self.stage013_scout_volume))
        stop_price = _safe_float((sizing_snapshot or {}).get("stop_price"))
        entry_price = float(bar.close_price)
        risk_price = abs(entry_price - stop_price) if np.isfinite(stop_price) else np.nan
        min_risk = max(float(self.get_pricetick(contract_vt_symbol)), 1e-9)
        has_valid_risk = np.isfinite(risk_price) and risk_price >= min_risk
        has_minutes = self._stage013_has_observation_window(contract_vt_symbol, bar.datetime)
        should_split = (
            enabled
            and eligible_signal
            and original_volume > min_lot
            and has_valid_risk
            and has_minutes
        )
        if not should_split:
            super()._open_position(
                state,
                contract_vt_symbol,
                direction,
                volume,
                bar,
                signal,
                history,
                signal_data,
                sizing_snapshot=sizing_snapshot,
            )
            return

        scout_volume = min(min_lot, original_volume)
        deferred_volume = max(0, original_volume - scout_volume)
        adjusted_sizing = dict(sizing_snapshot or {})
        adjusted_sizing.update(
            {
                "selected_volume": scout_volume,
                "stage013_minrisk_clean_restore_applied": 1,
                "stage013_original_selected_volume": original_volume,
                "stage013_scout_volume": scout_volume,
                "stage013_deferred_volume": deferred_volume,
                "stage013_observation_bars": int(self.stage013_observation_bars),
                "stage013_heat_r": float(self.stage013_heat_r),
                "stage013_integer_lot_policy": "one_lot_scout_min_position_size",
            }
        )
        super()._open_position(
            state,
            contract_vt_symbol,
            direction,
            scout_volume,
            bar,
            signal,
            history,
            signal_data,
            sizing_snapshot=adjusted_sizing,
        )
        key = self._stage013_pending_key(contract_vt_symbol, direction, bar.datetime)
        self._stage013_pending_restore[key] = {
            "product_vt_symbol": state.product_vt_symbol,
            "contract_vt_symbol": contract_vt_symbol,
            "direction": direction,
            "signal": signal,
            "entry_datetime": bar.datetime,
            "entry_price_planned": entry_price,
            "stop_price": stop_price,
            "risk_price_planned": risk_price,
            "original_volume": original_volume,
            "scout_volume": scout_volume,
            "deferred_volume": deferred_volume,
        }
        self._stage013_reserve_volume_override[state.product_vt_symbol] = scout_volume
        self.stage013_open_adjustments.append(
            {
                "datetime": bar.datetime,
                "product_vt_symbol": state.product_vt_symbol,
                "vt_symbol": contract_vt_symbol,
                "direction": direction,
                "signal": signal,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "risk_price": risk_price,
                "original_volume": original_volume,
                "scout_volume": scout_volume,
                "deferred_volume": deferred_volume,
                "observation_bars": int(self.stage013_observation_bars),
                "heat_r": float(self.stage013_heat_r),
                "note": "flat/reverse signal split into one-lot scout plus deferred restore; missing risk/minute data keeps official path",
            }
        )

    def stage827_intraday_exit_after_open_trade(self, trade: s002.s827.TradeData) -> dict[str, Any] | None:
        if not bool(self.enable_stage013_minrisk_clean_restore):
            return super().stage827_intraday_exit_after_open_trade(trade)
        event = self._stage013_minrisk_clean_restore_after_open_trade(trade)
        if event:
            return event
        return super(s002.s847.QmtRollPortfolioStrategyStage847C9StopRetry, self).stage827_intraday_exit_after_open_trade(trade)

    def _stage013_quality_metrics(
        self,
        entry_day: pd.DataFrame,
        entry_price: float,
        risk_price: float,
        position_direction: str,
    ) -> dict[str, Any]:
        observation_bars = max(1, int(self.stage013_observation_bars))
        first = entry_day.head(observation_bars).copy()
        if first.empty:
            return {}
        last_close = _safe_float(first.iloc[-1].get("close"))
        if position_direction == "short":
            directional = (entry_price - last_close) / risk_price
            first_mfe = (entry_price - pd.to_numeric(first["low"], errors="coerce").min()) / risk_price
            first_mae = (pd.to_numeric(first["high"], errors="coerce").max() - entry_price) / risk_price
        else:
            directional = (last_close - entry_price) / risk_price
            first_mfe = (pd.to_numeric(first["high"], errors="coerce").max() - entry_price) / risk_price
            first_mae = (entry_price - pd.to_numeric(first["low"], errors="coerce").min()) / risk_price
        return {
            "observation_start": pd.Timestamp(first.iloc[0]["bar_datetime"]).isoformat(),
            "observation_end": pd.Timestamp(first.iloc[-1]["bar_datetime"]).isoformat(),
            "observation_end_bar_index": int(len(first) - 1),
            "observation_close": last_close,
            "first_30m_directional_r": directional,
            "first_30m_mfe_r": max(0.0, first_mfe) if np.isfinite(first_mfe) else np.nan,
            "first_30m_mae_r": max(0.0, first_mae) if np.isfinite(first_mae) else np.nan,
            "clean_passed": int(np.isfinite(directional) and directional > 0.0 and np.isfinite(first_mae) and first_mae <= float(self.stage013_heat_r)),
        }

    def _stage013_first_c9_stop_or_progress(
        self,
        entry_day: pd.DataFrame,
        entry_price: float,
        risk_price: float,
        position_direction: str,
        *,
        start_idx: int = 0,
    ) -> dict[str, Any]:
        sign = s002.s827._direction_sign(position_direction)
        stop_price = entry_price - sign * float(self.stage847_stop_retry_r) * risk_price
        progress_price = entry_price + sign * float(self.stage847_stop_retry_r) * risk_price
        for idx in range(max(0, int(start_idx)), len(entry_day)):
            item = entry_day.iloc[idx]
            high = _safe_float(item.get("high"))
            low = _safe_float(item.get("low"))
            if position_direction == "long":
                adverse_hit = low <= stop_price
                progress_hit = high >= progress_price
            else:
                adverse_hit = high >= stop_price
                progress_hit = low <= progress_price
            if adverse_hit:
                return {
                    "event": "stop",
                    "idx": idx,
                    "time": pd.Timestamp(item["bar_datetime"]).isoformat(),
                    "stop_price": stop_price,
                    "progress_price": progress_price,
                    "same_bar_progress": int(progress_hit),
                }
            if progress_hit:
                return {
                    "event": "progress",
                    "idx": idx,
                    "time": pd.Timestamp(item["bar_datetime"]).isoformat(),
                    "stop_price": stop_price,
                    "progress_price": progress_price,
                    "same_bar_progress": 1,
                }
        return {"event": "none", "idx": -1, "time": "", "stop_price": stop_price, "progress_price": progress_price}

    def _stage013_record_restore_diagnostic(
        self,
        *,
        state: Any,
        contract_vt_symbol: str,
        direction: str,
        restore_price: float,
        stop_price: float,
        restore_volume: int,
        event_datetime: Any,
    ) -> None:
        fake_bar = SimpleNamespace(datetime=event_datetime, close_price=restore_price)
        size = self.get_size(contract_vt_symbol)
        margin_ratio = self._margin_ratio_for_symbol(contract_vt_symbol)
        sizing_snapshot = {
            "risk_mode": state.risk_mode,
            "risk_ratio": None,
            "risk_amount": None,
            "limited_balance": self._limited_available_balance(),
            "allowed_capital": self._allowed_capital(),
            "free_capital": self._free_capital_after_reservations(),
            "reserved_margin_before": self._reserved_margin_in_use(),
            "stop_price": stop_price,
            "risk_per_contract": abs(restore_price - stop_price) * size,
            "margin_ratio": margin_ratio,
            "margin_per_contract": restore_price * size * margin_ratio,
            "contracts_by_risk": None,
            "contracts_by_margin": None,
            "contracts_by_single_trade_cap": None,
            "selected_volume": restore_volume,
            "risk_multiplier": self._current_streak_multiplier(),
            "sizing_method": "stage013_minrisk_clean_restore",
            "stage013_minrisk_clean_restore_applied": 1,
        }
        self._record_entry_risk_diagnostic(
            product_vt_symbol=state.product_vt_symbol,
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            bar=fake_bar,
            signal="stage013_minrisk_clean_restore",
            layer_kind="stage013_minrisk_clean_restore",
            volume=restore_volume,
            stop_price=stop_price,
            risk_mode=state.risk_mode,
            sizing_snapshot=sizing_snapshot,
        )

    def _stage013_append_restore_layer(
        self,
        *,
        state: Any,
        direction: str,
        restore_volume: int,
        restore_price: float,
        stop_price: float,
        event_datetime: Any,
    ) -> None:
        trade_date = _normalize_day(event_datetime).strftime("%Y-%m-%d")
        state.layers.append(
            s002.PositionLayer(
                kind="stage013_minrisk_clean_restore",
                direction=direction,
                volume=max(1, int(restore_volume)),
                entry_price=float(restore_price),
                stop_price=float(stop_price),
                highest_price=float(restore_price),
                lowest_price=float(restore_price),
                signal="stage013_minrisk_clean_restore",
                entry_date=trade_date,
                margin_ratio=self._margin_ratio_for_symbol(state.contract_vt_symbol),
                entry_price_synced=False,
            )
        )

    def _stage013_find_restore_stop(
        self,
        entry_day: pd.DataFrame,
        position_direction: str,
        entry_price: float,
        *,
        start_idx: int,
    ) -> dict[str, Any]:
        for idx in range(max(0, int(start_idx)), len(entry_day)):
            item = entry_day.iloc[idx]
            if position_direction == "long":
                hit = _safe_float(item.get("low")) <= entry_price
            else:
                hit = _safe_float(item.get("high")) >= entry_price
            if hit:
                return {"idx": idx, "time": pd.Timestamp(item["bar_datetime"]).isoformat()}
        return {"idx": -1, "time": ""}

    def _stage013_reentry_after_stop(
        self,
        entry_day: pd.DataFrame,
        position_direction: str,
        entry_price: float,
        stop_price: float,
        stop_idx: int,
    ) -> dict[str, Any]:
        reentry_idx = -1
        reentry_time = ""
        max_retries = max(0, int(self.stage847_max_retries))
        if max_retries > 0:
            for idx in range(int(stop_idx) + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    reclaimed = _safe_float(item.get("high")) >= entry_price
                else:
                    reclaimed = _safe_float(item.get("low")) <= entry_price
                if reclaimed:
                    reentry_idx = idx
                    reentry_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break

        retry_failed_idx = -1
        retry_failed_time = ""
        if reentry_idx >= 0:
            for idx in range(reentry_idx + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    retry_stop_hit = _safe_float(item.get("low")) <= stop_price
                else:
                    retry_stop_hit = _safe_float(item.get("high")) >= stop_price
                if retry_stop_hit:
                    retry_failed_idx = idx
                    retry_failed_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break
        return {
            "reentry_idx": reentry_idx,
            "reentry_time": reentry_time,
            "retry_failed_idx": retry_failed_idx,
            "retry_failed_time": retry_failed_time,
            "max_retries": max_retries,
        }

    def _stage013_append_quality_event(self, event: dict[str, Any]) -> None:
        self.stage013_quality_restore_events.append(event)

    def _stage013_minrisk_clean_restore_after_open_trade(self, trade: s002.s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s002.s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        pending = self._stage013_pop_pending_for_trade(trade.vt_symbol, position_direction, trade.datetime)
        if not pending:
            return None

        entry_day = self._stage013_entry_day(trade.vt_symbol, trade.datetime)
        entry_price = float(trade.price)
        stop_price = _safe_float(pending.get("stop_price"))
        risk_price = _safe_float(pending.get("risk_price_planned"))
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        base_event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": state.product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "original_stop_price": stop_price,
            "risk_price": risk_price,
            "observation_bars": int(self.stage013_observation_bars),
            "heat_r": float(self.stage013_heat_r),
            "original_volume": int(pending["original_volume"]),
            "scout_volume": int(pending["scout_volume"]),
            "deferred_volume": int(pending["deferred_volume"]),
            "stage013_checked": 1,
        }
        if entry_day.empty or len(entry_day) < int(self.stage013_observation_bars):
            event = {**base_event, "final_state": "official_path_missing_stage861_observation", "exit_reason": "no_stage013_restore"}
            self._stage013_append_quality_event(event)
            return None
        if entry_price <= 0 or not np.isfinite(risk_price) or risk_price < min_risk:
            event = {**base_event, "final_state": "official_path_invalid_plan_day_risk", "exit_reason": "no_stage013_restore"}
            self._stage013_append_quality_event(event)
            return None

        quality = self._stage013_quality_metrics(entry_day, entry_price, risk_price, position_direction)
        if not quality:
            event = {**base_event, "final_state": "no_restore_no_observation", "exit_reason": "no_stage013_restore"}
            self._stage013_append_quality_event(event)
            return None
        obs_end_idx = int(quality["observation_end_bar_index"])

        first_c9 = self._stage013_first_c9_stop_or_progress(entry_day, entry_price, risk_price, position_direction)
        if first_c9["event"] == "stop" and int(first_c9["idx"]) <= obs_end_idx:
            c9_event = super()._stage847_stop_retry_event_after_open_trade(trade)
            event = {
                **base_event,
                **quality,
                "c9_first_event": "stop_before_quality_window_end",
                "c9_first_stop_time": first_c9["time"],
                "c9_first_stop_bar_index": int(first_c9["idx"]),
                "progress_price": first_c9["progress_price"],
                "adverse_price": first_c9["stop_price"],
                "restore_price": np.nan,
                "restore_time": "",
                "restore_volume": 0,
                "restore_stop_time": "",
                "restore_stop_bar_index": -1,
                "final_state": "c9_stop_retry_before_quality_restore",
                "exit_reason": "stage847_intraday_05r_stop_retry_priority",
            }
            self._stage013_append_quality_event(event)
            return c9_event

        if not bool(quality["clean_passed"]):
            c9_event = None
            if first_c9["event"] != "progress":
                c9_event = super()._stage847_stop_retry_event_after_open_trade(trade)
            event = {
                **base_event,
                **quality,
                "c9_first_event": first_c9["event"],
                "c9_first_stop_time": first_c9["time"] if first_c9["event"] == "stop" else "",
                "c9_first_stop_bar_index": int(first_c9["idx"]) if first_c9["event"] == "stop" else -1,
                "progress_price": first_c9["progress_price"],
                "adverse_price": first_c9["stop_price"],
                "restore_price": np.nan,
                "restore_time": "",
                "restore_volume": 0,
                "restore_stop_time": "",
                "restore_stop_bar_index": -1,
                "final_state": "no_restore_not_clean_30m",
                "exit_reason": "no_stage013_restore",
            }
            self._stage013_append_quality_event(event)
            return c9_event

        restore_volume = int(pending["deferred_volume"])
        if restore_volume <= 0:
            event = {**base_event, **quality, "final_state": "no_restore_no_deferred_volume", "exit_reason": "no_stage013_restore"}
            self._stage013_append_quality_event(event)
            return None

        restore_price = float(quality["observation_close"])
        restore_time = str(quality["observation_end"])
        restore_stop_price = entry_price
        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        event_datetime = _align_timestamp_timezone(restore_time, trade.datetime)

        self._stage013_append_restore_layer(
            state=state,
            direction=position_direction,
            restore_volume=restore_volume,
            restore_price=restore_price,
            stop_price=restore_stop_price,
            event_datetime=event_datetime,
        )
        restore_layer_index = len(state.layers) - 1
        self._stage013_record_restore_diagnostic(
            state=state,
            contract_vt_symbol=contract_vt_symbol,
            direction=position_direction,
            restore_price=restore_price,
            stop_price=restore_stop_price,
            restore_volume=restore_volume,
            event_datetime=event_datetime,
        )
        self._record_trade_event(
            bar=event_bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=position_direction,
            offset="Open",
            reason="stage013_clean_30m_restore_open",
            volume=restore_volume,
            price=restore_price,
        )
        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "open",
                "source": "stage013_clean_30m_restore_open",
                "price": restore_price,
                "volume": restore_volume,
                "time": restore_time,
            }
        ]

        restore_stop = self._stage013_find_restore_stop(
            entry_day,
            position_direction,
            entry_price,
            start_idx=obs_end_idx + 1,
        )
        c9_after = {"event": "none", "idx": -1, "time": "", "stop_price": first_c9["stop_price"], "progress_price": first_c9["progress_price"]}
        if first_c9["event"] != "progress":
            c9_after = self._stage013_first_c9_stop_or_progress(
                entry_day,
                entry_price,
                risk_price,
                position_direction,
                start_idx=obs_end_idx + 1,
            )

        estimated_restore_pnl = np.nan
        restore_stop_state = "not_stopped_entry_day"
        if int(restore_stop["idx"]) >= 0:
            estimated_restore_pnl = (
                s002.s827._direction_sign(position_direction)
                * (restore_stop_price - restore_price)
                * self.get_size(contract_vt_symbol)
                * restore_volume
            )
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason="stage013_clean_restore_stop_at_entry",
                volume=restore_volume,
                price=restore_stop_price,
            )
            self._close_layers(state, [restore_layer_index], restore_stop_price, exit_reason="stage013_clean_restore_stop_at_entry")
            self._apply_state_target(state, execution_price_override=restore_stop_price)
            synthetic_trades.append(
                {
                    "action": "close",
                    "source": "stage013_clean_restore_stop_at_entry",
                    "price": restore_stop_price,
                    "volume": restore_volume,
                    "time": restore_stop["time"],
                }
            )
            self.stage013_clean_restore_stop_count += 1
            restore_stop_state = "entry_day_stop"
        else:
            self._apply_state_target(state, execution_price_override=restore_price)

        scout_c9_state = "no_c9_stop_after_restore"
        scout_c9_stop_time = ""
        scout_c9_reentry_time = ""
        scout_c9_retry_failed_time = ""
        if c9_after["event"] == "stop":
            c9_stop_idx = int(c9_after["idx"])
            c9_stop_price = float(c9_after["stop_price"])
            retry = self._stage013_reentry_after_stop(
                entry_day,
                position_direction,
                entry_price,
                c9_stop_price,
                c9_stop_idx,
            )
            scout_volume = int(pending["scout_volume"])
            synthetic_trades.append(
                {
                    "action": "close",
                    "source": "stage013_scout_stage847_05r_initial_stop",
                    "price": c9_stop_price,
                    "volume": scout_volume,
                    "time": c9_after["time"],
                }
            )
            scout_c9_state = "flat_no_reentry"
            scout_c9_stop_time = str(c9_after["time"])
            scout_c9_reentry_time = str(retry["reentry_time"])
            scout_c9_retry_failed_time = str(retry["retry_failed_time"])
            if int(retry["reentry_idx"]) >= 0:
                synthetic_trades.append(
                    {
                        "action": "open",
                        "source": "stage013_scout_stage847_reentry_at_original_entry",
                        "price": entry_price,
                        "volume": scout_volume,
                        "time": retry["reentry_time"],
                    }
                )
                scout_c9_state = "open_after_reentry"
                if int(retry["retry_failed_idx"]) >= 0:
                    synthetic_trades.append(
                        {
                            "action": "close",
                            "source": "stage013_scout_stage847_retry_failed_05r_stop",
                            "price": c9_stop_price,
                            "volume": scout_volume,
                            "time": retry["retry_failed_time"],
                        }
                    )
                    scout_c9_state = "flat_retry_failed"

            if scout_c9_state != "open_after_reentry":
                remaining_indexes = [
                    index for index, layer in enumerate(state.layers) if layer.direction == position_direction
                ]
                if remaining_indexes:
                    close_volume = int(sum(state.layers[index].volume for index in remaining_indexes))
                    self._record_trade_event(
                        bar=event_bar,
                        contract_vt_symbol=contract_vt_symbol,
                        product_vt_symbol=product_vt_symbol,
                        position_direction=position_direction,
                        offset="Close",
                        reason=f"stage013_scout_stage847_05r_{scout_c9_state}",
                        volume=close_volume,
                        price=c9_stop_price,
                    )
                    if len(remaining_indexes) == len(state.layers):
                        self._close_all_layers_and_set_flat_target(
                            state,
                            c9_stop_price,
                            execution_price_override=c9_stop_price,
                            exit_reason=f"stage013_scout_stage847_05r_{scout_c9_state}",
                        )
                    else:
                        self._close_layers(
                            state,
                            remaining_indexes,
                            c9_stop_price,
                            exit_reason=f"stage013_scout_stage847_05r_{scout_c9_state}",
                        )
                        self._apply_state_target(state, execution_price_override=c9_stop_price)

            c9_event = {
                "datetime": trade.datetime,
                "trade_id": trade.vt_tradeid,
                "vt_symbol": trade.vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "direction": position_direction,
                "entry_price": entry_price,
                "stop_price": c9_stop_price,
                "progress_price": c9_after["progress_price"],
                "risk_price": risk_price,
                "stop_r": float(self.stage847_stop_retry_r),
                "max_retries": int(retry["max_retries"]),
                "volume": int(pending["scout_volume"]),
                "first_stop_time": c9_after["time"],
                "first_stop_bar_index": c9_stop_idx,
                "reentry_time": retry["reentry_time"],
                "reentry_bar_index": int(retry["reentry_idx"]),
                "retry_failed_time": retry["retry_failed_time"],
                "retry_failed_bar_index": int(retry["retry_failed_idx"]),
                "retry_reentered": int(int(retry["reentry_idx"]) >= 0),
                "retry_failed": int(int(retry["retry_failed_idx"]) >= 0),
                "final_state": scout_c9_state,
                "final_exit_price": np.nan if scout_c9_state == "open_after_reentry" else c9_stop_price,
                "note": "stage013 scout c9 stop/retry after quality decision",
                "exit_reason": f"stage013_scout_stage847_05r_{scout_c9_state}",
            }
            self.stage847_stop_retry_events.append(c9_event)

        self.stage013_clean_restore_event_count += 1
        final_state = "clean_restore_open"
        if restore_stop_state != "not_stopped_entry_day":
            final_state = "clean_restore_stopped_entry_day"
        if scout_c9_state != "no_c9_stop_after_restore":
            final_state = f"{final_state}_scout_{scout_c9_state}"

        event = {
            **base_event,
            **quality,
            "c9_first_event": first_c9["event"],
            "c9_first_stop_time": first_c9["time"] if first_c9["event"] == "stop" else "",
            "c9_first_stop_bar_index": int(first_c9["idx"]) if first_c9["event"] == "stop" else -1,
            "progress_price": first_c9["progress_price"],
            "adverse_price": first_c9["stop_price"],
            "restore_price": restore_price,
            "restore_time": restore_time,
            "restore_volume": restore_volume,
            "restore_stop_price": restore_stop_price,
            "restore_stop_time": restore_stop["time"],
            "restore_stop_bar_index": int(restore_stop["idx"]),
            "restore_stop_state": restore_stop_state,
            "estimated_restore_pnl": estimated_restore_pnl,
            "scout_c9_state": scout_c9_state,
            "scout_c9_stop_time": scout_c9_stop_time,
            "scout_c9_reentry_time": scout_c9_reentry_time,
            "scout_c9_retry_failed_time": scout_c9_retry_failed_time,
            "final_state": final_state,
            "exit_reason": "stage013_minrisk_clean_restore",
            "note": "one-lot scout restores deferred official volume only after clean first 30 visible minute bars; restored layer stop is scout entry",
            "synthetic_trades": synthetic_trades,
        }
        self._stage013_append_quality_event(event)
        return event


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s002.s928._with_legacy_stage372_spec()
    try:
        profile = s002.s928._c9_15w_profile(metadata, window)
    finally:
        s002.s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C_ARM}_2018_01",
        label="Stage013 min-risk clean 30m restore official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage013 frozen min-risk clean restore. "
            "New flat/reverse C9 entries with valid plan-day risk and Stage861 30 visible entry-day minute bars first open "
            "one scout lot; if first 30 bars close in the trade direction and MAE stays <=0.5R, restore the deferred original "
            "volume at the 30th bar close. Missing risk or minute coverage keeps the official path. No parameter, product, "
            "direction, year or month scan."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage013_minrisk_clean_restore": True,
        "stage013_observation_bars": OBSERVATION_BARS,
        "stage013_heat_r": HEAT_R,
        "stage013_scout_volume": SCOUT_VOLUME,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage013MinRiskCleanRestore
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s002.s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    quality_events = frames.get("restore_events", pd.DataFrame())
    open_adjustments = frames.get("open_adjustments", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum())
    restored = quality_events[quality_events.get("restore_volume", pd.Series(dtype=float)).fillna(0).astype(float) > 0] if not quality_events.empty else pd.DataFrame()
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm": C_ARM,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "window_id": FULL_WINDOW_ID,
            "window_start": START.date().isoformat(),
            "window_end": END.date().isoformat(),
            "actual_start": pd.to_datetime(combined["date"], errors="coerce").min().date().isoformat(),
            "actual_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
            "trading_days": int(len(combined)),
            "stop_retry_event_count": int(len(stop_retry_events)),
            "quality_check_event_count": int(len(quality_events)),
            "clean_restore_event_count": int(len(restored)),
            "restore_stop_count": int(
                restored["restore_stop_state"].astype(str).ne("not_stopped_entry_day").sum() if not restored.empty else 0
            ),
            "restore_volume": float(pd.to_numeric(restored.get("restore_volume", 0), errors="coerce").fillna(0).sum()) if not restored.empty else 0.0,
            "open_adjustment_count": int(len(open_adjustments)),
            "broker10_cap_event_count": broker10_cap_event_count,
            "closed_trade_rows": int(len(trades)),
        }
    )
    return row


def _candidate_curve(combined: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    curve = combined.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["arm"] = C_ARM
    curve["window_id"] = FULL_WINDOW_ID
    curve["window_start"] = START.date().isoformat()
    curve["window_end"] = END.date().isoformat()
    curve["account_capital"] = CAPITAL
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    curve["variant"] = profile["spec"].capital.variant
    return curve


def _load_baseline() -> tuple[pd.Series, pd.DataFrame]:
    summary = _read_required_csv(s002.BASELINE_SUMMARY_IN)
    curves = _read_required_csv(s002.BASELINE_CURVES_IN)
    base_summary = summary[summary["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_summary.empty:
        raise RuntimeError(f"missing baseline full window: {FULL_WINDOW_ID}")
    base_curve = curves[curves["window_id"].astype(str).eq(FULL_WINDOW_ID)].copy()
    if base_curve.empty:
        raise RuntimeError(f"missing baseline curve full window: {FULL_WINDOW_ID}")
    row = base_summary.iloc[0].copy()
    row["stage"] = STAGE
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["arm"] = A_ARM
    row["official_live_version"] = OFFICIAL_LIVE_VERSION
    row["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    row["quality_check_event_count"] = 0
    row["clean_restore_event_count"] = 0
    row["restore_stop_count"] = 0
    row["restore_volume"] = 0.0
    row["open_adjustment_count"] = 0
    base_curve["arm"] = A_ARM
    base_curve["stage"] = STAGE
    base_curve["model_tag"] = MODEL_TAG
    return row, base_curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["arm"].eq(A_ARM)].iloc[0]
    c = summary[summary["arm"].eq(C_ARM)].iloc[0]
    return_retention = float(c["total_return_pct"]) / float(a["total_return_pct"]) * 100.0 if float(a["total_return_pct"]) else np.nan
    equity_retention = (float(c["end_equity"]) - CAPITAL) / (float(a["end_equity"]) - CAPITAL) * 100.0
    return pd.DataFrame(
        [
            {
                "A_arm": A_ARM,
                "C_arm": C_ARM,
                "A_end_equity": float(a["end_equity"]),
                "C_end_equity": float(c["end_equity"]),
                "end_equity_delta": float(c["end_equity"]) - float(a["end_equity"]),
                "A_total_return_pct": float(a["total_return_pct"]),
                "C_total_return_pct": float(c["total_return_pct"]),
                "return_retention_pct": return_retention,
                "equity_gain_retention_pct": equity_retention,
                "A_max_dd_pct": float(a["max_dd_pct"]),
                "C_max_dd_pct": float(c["max_dd_pct"]),
                "dd_improvement_pp": float(c["max_dd_pct"]) - float(a["max_dd_pct"]),
                "A_sharpe": float(a["sharpe"]),
                "C_sharpe": float(c["sharpe"]),
                "sharpe_delta": float(c["sharpe"]) - float(a["sharpe"]),
                "A_total_slippage": float(a["total_slippage"]),
                "C_total_slippage": float(c["total_slippage"]),
                "A_total_trade_count": float(a["total_trade_count"]),
                "C_total_trade_count": float(c["total_trade_count"]),
                "A_win_rate_pct": float(a["nonzero_daily_win_rate_pct"]),
                "C_win_rate_pct": float(c["nonzero_daily_win_rate_pct"]),
                "A_max_broker10_pct": float(a["max_broker10_margin_to_equity_pct"]),
                "C_max_broker10_pct": float(c["max_broker10_margin_to_equity_pct"]),
                "broker10_improvement_pp": float(a["max_broker10_margin_to_equity_pct"]) - float(c["max_broker10_margin_to_equity_pct"]),
                "A_days_over_100pct": int(a.get("days_over_100pct", 0)),
                "C_days_over_100pct": int(c.get("days_over_100pct", 0)),
                "C_quality_check_event_count": int(c.get("quality_check_event_count", 0)),
                "C_clean_restore_event_count": int(c.get("clean_restore_event_count", 0)),
                "C_restore_stop_count": int(c.get("restore_stop_count", 0)),
                "C_restore_volume": float(c.get("restore_volume", 0.0)),
                "C_open_adjustment_count": int(c.get("open_adjustment_count", 0)),
            }
        ]
    )


def _cost_stress(profile: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in [1.0, 2.0, 3.0]:
        row = s002.s650._metrics(combined, profile["spec"].capital, cost_multiplier=multiplier)
        row.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm": C_ARM,
                "cost_multiplier": multiplier,
                "window_id": FULL_WINDOW_ID,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        trough = group.loc[group["drawdown_pct"].idxmin()]
        before = group[group["date"].le(trough["date"])]
        peak = before.loc[before["account_equity"].idxmax()]
        rows.append(
            {
                "arm": arm,
                "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
                "peak_equity": float(peak["account_equity"]),
                "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
                "trough_equity": float(trough["account_equity"]),
                "trough_dd_pct": float(trough["drawdown_pct"]),
                "max_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").max()),
                "p95_broker10_margin_to_equity_pct": float(pd.to_numeric(group["broker10_margin_to_equity_pct"], errors="coerce").quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {A_ARM: "#2563eb", C_ARM: "#0f766e"}
    labels = {
        A_ARM: "A official C9/15w",
        C_ARM: "C min-risk clean 30m restore",
    }
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct"],
            label=labels.get(arm, arm),
            color=colors.get(arm),
        )
    axes[0].set_title("Stage013 full-path equity")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.7)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in [
        "original_volume",
        "scout_volume",
        "deferred_volume",
        "restore_volume",
        "estimated_restore_pnl",
        "first_30m_directional_r",
        "first_30m_mae_r",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["year", "final_state"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            original_volume=("original_volume", "sum"),
            scout_volume=("scout_volume", "sum"),
            deferred_volume=("deferred_volume", "sum"),
            restore_volume=("restore_volume", "sum"),
            estimated_restore_pnl=("estimated_restore_pnl", "sum"),
            median_first_30m_directional_r=("first_30m_directional_r", "median"),
            median_first_30m_mae_r=("first_30m_mae_r", "median"),
        )
        .reset_index()
        .sort_values(["year", "final_state"])
    )


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["restore_volume_num"] = pd.to_numeric(data.get("restore_volume"), errors="coerce").fillna(0.0)
    data["estimated_restore_pnl_num"] = pd.to_numeric(data.get("estimated_restore_pnl"), errors="coerce").fillna(0.0)
    data["deferred_volume_num"] = pd.to_numeric(data.get("deferred_volume"), errors="coerce").fillna(0.0)
    restored = data[data["restore_volume_num"] > 0].copy()
    no_restore = data[data["restore_volume_num"] <= 0].copy()
    selected: list[pd.DataFrame] = []
    if not restored.empty:
        selected.append(restored.sort_values("restore_volume_num", ascending=False).head(6))
        selected.append(restored.sort_values("estimated_restore_pnl_num").head(6))
    if not no_restore.empty:
        selected.append(no_restore.sort_values("deferred_volume_num", ascending=False).head(8))
    if not selected:
        return pd.DataFrame()
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "datetime", "direction", "final_state"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s002.s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = _normalize_day(row["datetime"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s002.s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "scout entry"),
                    ("progress_price", "#16a34a", "--", "+0.5R C9 progress"),
                    ("adverse_price", "#dc2626", ":", "-0.5R C9 stop"),
                    ("restore_price", "#7c3aed", "-.", "clean restore"),
                    ("restore_stop_price", "#ea580c", "-.", "restore stop entry"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("observation_end", "#64748b", "30m check"),
                    ("restore_time", "#7c3aed", "restore"),
                    ("restore_stop_time", "#ea580c", "restore stop"),
                    ("c9_first_stop_time", "#dc2626", "C9 stop"),
                    ("scout_c9_stop_time", "#b91c1c", "scout C9 stop"),
                ]:
                    idx = _index_for_time(day, row.get(time_col))
                    if idx >= 0:
                        ax.axvline(idx, color=color, linewidth=1.0, alpha=0.85, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{vt_symbol} {row.get('direction')} {entry_date:%Y-%m-%d} "
                    f"{row.get('final_state')} orig/scout/rest={int(_safe_float(row.get('original_volume'), 0))}/"
                    f"{int(_safe_float(row.get('scout_volume'), 0))}/"
                    f"{int(_safe_float(row.get('restore_volume'), 0))} "
                    f"dir30={_safe_float(row.get('first_30m_directional_r'), 0):.2f} "
                    f"mae30={_safe_float(row.get('first_30m_mae_r'), 0):.2f}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": row.get("direction", ""),
                    "final_state": row.get("final_state", ""),
                    "original_volume": _safe_float(row.get("original_volume")),
                    "scout_volume": _safe_float(row.get("scout_volume")),
                    "restore_volume": _safe_float(row.get("restore_volume")),
                    "first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                    "first_30m_mae_r": _safe_float(row.get("first_30m_mae_r")),
                    "restore_time": row.get("restore_time", ""),
                    "restore_stop_time": row.get("restore_stop_time", ""),
                }
            )
        fig.suptitle("Stage013 min-risk clean-restore entry-day minute-K atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(comparison: pd.DataFrame, cost_stress: pd.DataFrame) -> dict[str, Any]:
    row = comparison.iloc[0]
    cost_3x = cost_stress[cost_stress["cost_multiplier"].eq(3.0)].iloc[0].to_dict()
    retention_pass = float(row["return_retention_pct"]) >= 80.0
    dd_pass = float(row["dd_improvement_pp"]) > 0.0
    broker_pass = float(row["C_max_broker10_pct"]) <= float(row["A_max_broker10_pct"]) + 1e-9
    sharpe_pass = float(row["sharpe_delta"]) >= -0.10
    if retention_pass and dd_pass and broker_pass and sharpe_pass:
        label = "stage013_full_period_pass_requires_multistart_ab_protocol"
    elif not retention_pass:
        label = "stage013_failed_return_retention_no_param_rescue"
    elif not dd_pass:
        label = "stage013_failed_drawdown_no_param_rescue"
    else:
        label = "stage013_mixed_full_period_no_promotion"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "baseline_arm": A_ARM,
        "candidate_arm": C_ARM,
        "candidate_hypothesis": (
            "Default to one-lot minimum risk while the entry has not proven itself; release the deferred official volume "
            "only when the first 30 visible entry-day minute bars close in the trade direction and stay within 0.5R MAE."
        ),
        "predeclared_metrics": [
            "full-period end_equity/return/max_drawdown/Sharpe/slippage/trades/win_rate",
            "return retention >= 80%",
            "max drawdown improves versus A",
            "broker10 peak and days_over_100pct do not worsen",
            "2x/3x cost stress does not create a hidden failure",
            "visual path chart and minute-K atlas must support the metric story",
        ],
        "decision": label,
        "pass_flags": {
            "return_retention_80pct": bool(retention_pass),
            "drawdown_improved": bool(dd_pass),
            "broker10_not_worse": bool(broker_pass),
            "sharpe_not_materially_worse": bool(sharpe_pass),
        },
        "comparison": comparison.to_dict(orient="records"),
        "cost_3x_candidate": cost_3x,
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "summary": str(SUMMARY_OUT),
            "comparison": str(COMPARISON_OUT),
            "curve": str(CURVE_OUT),
            "cost_stress": str(COST_STRESS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "quality_events": str(QUALITY_EVENTS_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "Gao et al. market intraday momentum and Li/Sakkas/Urquhart international ITSM support early intraday path "
            "as useful information, but only as an execution confirmation. pysystemtrade and event-driven backtest material "
            "support preserving time order and risk accounting rather than fitting product/year branches."
        ),
        "overfit_reflection_before": (
            "No: the rule is one frozen execution discipline with no product/year/direction/month branch and no parameter scan."
        ),
        "continue_value_before": (
            "Yes: Stage011/012 made the 30m quality label and plan-day risk ledger auditable; a true path engine is the next required test."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
    }


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    event_summary: pd.DataFrame,
    cost_stress: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    view_cols = [
        "arm",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "stop_retry_event_count",
        "quality_check_event_count",
        "clean_restore_event_count",
        "restore_stop_count",
        "open_adjustment_count",
    ]
    lines = [
        "# Stage013 最小风险 clean 30m 恢复真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- A：当前官方 C9/15w 全路径。",
        "- C：C9/15w + `minrisk_1lot_clean30_restore`。",
        "- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- Market Intraday Momentum 记录第一半小时收益对后续时段有样本外预测力，说明早段路径可作为信息吸收的执行层线索。",
        "- Intraday Time Series Momentum 国际证据显示早段 intraday momentum 不是单一市场偶然现象，但跨市场共性有限，不能复制固定收益模型。",
        "- pysystemtrade / event-driven backtest 资料强调交易规则、风险账本和执行顺序分离；本阶段只把早段路径作为恢复风险闸门，不改变 C9 alpha。",
        "- 我的判断：可研究的是“先小风险观察，证明后释放风险”的普世执行纪律；不可做的是按弱年份、品种、方向或窗口救参数。",
        "",
        "## 预声明规则",
        "",
        "- flat/reverse 新信号原始手数 `>1`，且 plan-day stop/risk 与 Stage861 入场日 30 根分钟K可用时，先开 `1` 手 scout。",
        "- plan-day risk 或 Stage861 30m 不可用时保持官方路径，不把缺字段样本降风险。",
        "- C9 `0.5R` stop/retry 在 30m 确认前优先；若先触发，则不恢复风险。",
        "- 前 30 根可见分钟K满足 `directional_r > 0` 且 `MAE <= 0.5R` 时，在第 30 根收盘价恢复剩余官方手数。",
        "- 恢复层止损为 scout 原入场价，避免恢复动作增加原始风险预算；不扫观察窗口、热度阈值、恢复比例、品种、方向、年份或月份。",
        "",
        "## Summary",
        "",
        _md_table(summary[view_cols], max_rows=10),
        "",
        "## A/C Comparison",
        "",
        _md_table(comparison, max_rows=5),
        "",
        "## Cost Stress Candidate",
        "",
        _md_table(cost_stress[["cost_multiplier", "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]], max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Events By Year",
        "",
        _md_table(event_summary, max_rows=40),
        "",
        "## Visual Outputs",
        "",
        f"- path chart：`{PATH_CHART_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage013] loading metadata and Stage861 minute bars", flush=True)
    metadata = s002.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s002.s928._load_stage861_full_minute_bars(vt_symbols)
    s002.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s002.s825._minute_groups(minute_bars)

    print("[stage013] running candidate true engine", flush=True)
    profile = _candidate_profile(metadata)
    combined, frames = s002._run_candidate(profile, metadata)
    c_summary = _candidate_summary(profile, combined, frames)
    c_curve = _candidate_curve(combined, profile)
    a_summary, a_curve = _load_baseline()

    summary = pd.DataFrame([a_summary.to_dict(), c_summary])
    curve = pd.concat([a_curve, c_curve], ignore_index=True, sort=False)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    comparison = _comparison(summary)
    cost_stress = _cost_stress(profile, combined)
    path_diag = _path_diagnostics(curve)
    quality_events = frames.get("restore_events", pd.DataFrame()).copy()
    event_summary = _event_summary(quality_events)
    atlas_paths, atlas_manifest = _plot_atlas(quality_events, minute_bars)
    closed_lots = s002.s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    decision = _decision(comparison, cost_stress)
    if decision["decision"] == "stage013_full_period_pass_requires_multistart_ab_protocol":
        decision["overfit_reflection_after"] = (
            "No immediate full-period overfit signal: the frozen C rule retained 80%+ return and improved path risk, "
            "but promotion still requires predeclared multi-start/cost/visual checks and A/B protocol."
        )
        decision["continue_value_after"] = (
            "Yes: this shape would deserve multistart validation, but no parameter tuning is allowed."
        )
    elif decision["decision"] == "stage013_failed_return_retention_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No new overfit was introduced, but changing 1 lot, 30 bars, or 0.5R after seeing this failure would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape if return retention is below 80%; inspect visuals once and switch principle rather than rescue parameters."
        )
    elif decision["decision"] == "stage013_failed_drawdown_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No parameter search occurred; the failure is structural because the frozen rule did not lower full-path drawdown."
        )
        decision["continue_value_after"] = (
            "No for this exact shape; do not tune windows or ratios to force drawdown improvement."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No parameter search occurred, but mixed evidence is not enough for promotion; tuning around this shape would be overfitting."
        )
        decision["continue_value_after"] = (
            "Limited: only use visual failure attribution to decide whether a different first-principles structure is needed."
        )

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    cost_stress.to_csv(COST_STRESS_OUT, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_risk", pd.DataFrame()).to_csv(ENTRY_RISK_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_OUT, index=False, encoding="utf-8-sig")
    frames.get("trade_events", pd.DataFrame()).to_csv(TRADE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("intraday_events", pd.DataFrame()).to_csv(INTRADAY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("stop_retry_events", pd.DataFrame()).to_csv(STOP_RETRY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    quality_events.to_csv(QUALITY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("open_adjustments", pd.DataFrame()).to_csv(OPEN_ADJUSTMENTS_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(summary, comparison, path_diag, event_summary, cost_stress, atlas_paths, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
