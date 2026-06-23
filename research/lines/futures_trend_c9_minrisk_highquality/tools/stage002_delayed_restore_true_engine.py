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
STAGE = "Stage002"
MODEL_TAG = "stage002_delayed_restore_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage928_c9_15w_halfyear_to_latest as s928
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_portfolio_strategy import PositionLayer


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage002_delayed_restore_true_engine"
BT_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

A_ARM = "A_official_stage847_c9_15w"
C_ARM = "C_stage002_delayed_restore_50pct_after_05r"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
INITIAL_FRACTION = 0.50
PROGRESS_R = 0.50
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

STAGE928_TAG = "stage928_c9_15w_halfyear_to_latest_v1"
STAGE928_PREFIX = "qmt_roll_stage928_c9_15w_halfyear_to_latest"
BASELINE_SUMMARY_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_summary_{STAGE928_TAG}.csv"
BASELINE_CURVES_IN = BT_OUTPUT_DIR / f"{STAGE928_PREFIX}_curves_{STAGE928_TAG}.csv"

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
RESTORE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_events_{MODEL_TAG}.csv"
OPEN_ADJUSTMENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_adjustments_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    times = pd.to_datetime(day["bar_datetime"], errors="coerce")
    matches = day.index[times.eq(ts)]
    if len(matches):
        return int(matches[0])
    diffs = (times - ts).abs()
    if diffs.empty:
        return -1
    pos = int(diffs.idxmin())
    return pos if diffs.loc[pos] <= pd.Timedelta(minutes=1) else -1


class QmtRollPortfolioStrategyStage002DelayedRestore(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage002_delayed_restore: bool = False
    stage002_initial_fraction: float = INITIAL_FRACTION
    stage002_progress_r: float = PROGRESS_R

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage002_delayed_restore",
        "stage002_initial_fraction",
        "stage002_progress_r",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage002_restore_event_count",
        "stage002_restore_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage002_restore_events: list[dict[str, Any]] = []
        self.stage002_open_adjustments: list[dict[str, Any]] = []
        self.stage002_restore_event_count: int = 0
        self.stage002_restore_stop_count: int = 0
        self._stage002_pending_restore: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._stage002_reserve_volume_override: dict[str, int] = {}

    def _stage002_pending_key(self, vt_symbol: str, direction: str, value: Any) -> tuple[str, str, str]:
        trade_date = s827._normalize_date(value).strftime("%Y-%m-%d")
        return str(vt_symbol), str(direction), trade_date

    def _stage002_pop_pending_for_trade(
        self,
        vt_symbol: str,
        direction: str,
        trade_datetime: Any,
    ) -> dict[str, Any] | None:
        exact_key = self._stage002_pending_key(vt_symbol, direction, trade_datetime)
        if exact_key in self._stage002_pending_restore:
            return self._stage002_pending_restore.pop(exact_key)

        trade_day = s827._normalize_date(trade_datetime)
        candidates: list[tuple[pd.Timestamp, tuple[str, str, str]]] = []
        for key in self._stage002_pending_restore:
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
        return self._stage002_pending_restore.pop(selected_key)

    def _reserve_intrabar_entry(
        self,
        product_vt_symbol: str,
        sizing_snapshot: dict[str, Any],
        volume: int,
        *,
        count_active_position: bool,
    ) -> None:
        override = self._stage002_reserve_volume_override.pop(product_vt_symbol, None)
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
        enabled = bool(self.enable_stage002_delayed_restore)
        eligible_signal = str(signal) != "rollover_reopen"
        should_split = enabled and eligible_signal and original_volume >= 2
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

        initial_fraction = min(max(float(self.stage002_initial_fraction), 0.0), 1.0)
        scout_volume = max(1, int(math.floor(original_volume * initial_fraction)))
        scout_volume = min(scout_volume, original_volume)
        deferred_volume = max(0, original_volume - scout_volume)
        if deferred_volume <= 0:
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

        adjusted_sizing = dict(sizing_snapshot or {})
        adjusted_sizing.update(
            {
                "selected_volume": scout_volume,
                "stage002_delayed_restore_applied": 1,
                "stage002_original_selected_volume": original_volume,
                "stage002_initial_fraction": initial_fraction,
                "stage002_scout_volume": scout_volume,
                "stage002_deferred_volume": deferred_volume,
                "stage002_progress_r": float(self.stage002_progress_r),
                "stage002_integer_lot_policy": "floor_initial_fraction_min1",
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
        key = self._stage002_pending_key(contract_vt_symbol, direction, bar.datetime)
        stop_price = float(adjusted_sizing.get("stop_price") or 0.0)
        entry_price = float(bar.close_price)
        risk_price = abs(entry_price - stop_price)
        self._stage002_pending_restore[key] = {
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
            "initial_fraction": initial_fraction,
            "progress_r": float(self.stage002_progress_r),
        }
        self._stage002_reserve_volume_override[state.product_vt_symbol] = scout_volume
        self.stage002_open_adjustments.append(
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
                "initial_fraction": initial_fraction,
                "progress_r": float(self.stage002_progress_r),
                "note": "flat/reverse signal split into scout plus deferred restore; rollover reopen excluded",
            }
        )

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        c9_event = super()._stage847_stop_retry_event_after_open_trade(trade)
        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if c9_event:
            self._stage002_pop_pending_for_trade(trade.vt_symbol, position_direction, trade.datetime)
            c9_event["stage002_delayed_restore_checked"] = 0
            return c9_event
        if not bool(self.enable_stage002_delayed_restore):
            return None
        return self._stage002_delayed_restore_event_after_open_trade(trade)

    def _stage002_record_restore_diagnostic(
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
            "sizing_method": "stage002_delayed_restore",
            "stage002_delayed_restore_applied": 1,
        }
        self._record_entry_risk_diagnostic(
            product_vt_symbol=state.product_vt_symbol,
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            bar=fake_bar,
            signal="stage002_delayed_restore",
            layer_kind="stage002_delayed_restore",
            volume=restore_volume,
            stop_price=stop_price,
            risk_mode=state.risk_mode,
            sizing_snapshot=sizing_snapshot,
        )

    def _stage002_append_restore_layer(
        self,
        *,
        state: Any,
        direction: str,
        restore_volume: int,
        restore_price: float,
        stop_price: float,
        event_datetime: Any,
    ) -> None:
        trade_date = s827._normalize_date(event_datetime).strftime("%Y-%m-%d")
        state.layers.append(
            PositionLayer(
                kind="stage002_delayed_restore",
                direction=direction,
                volume=max(1, int(restore_volume)),
                entry_price=float(restore_price),
                stop_price=float(stop_price),
                highest_price=float(restore_price),
                lowest_price=float(restore_price),
                signal="stage002_delayed_restore",
                entry_date=trade_date,
                margin_ratio=self._margin_ratio_for_symbol(state.contract_vt_symbol),
                entry_price_synced=False,
            )
        )

    def _stage002_delayed_restore_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        pending = self._stage002_pop_pending_for_trade(trade.vt_symbol, position_direction, trade.datetime)
        if not pending:
            return None

        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        if bars.empty:
            return None
        trade_date = s827._normalize_date(trade.datetime)
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        if entry_day.empty:
            return None

        entry_price = float(trade.price)
        stop_price = float(pending.get("stop_price") or 0.0)
        if entry_price <= 0 or stop_price <= 0:
            return None

        risk_price = abs(entry_price - stop_price)
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = s827._direction_sign(position_direction)
        progress_r = float(self.stage002_progress_r)
        restore_price = entry_price + sign * progress_r * risk_price
        adverse_price = entry_price - sign * progress_r * risk_price
        restore_stop_price = entry_price

        progress_idx = -1
        progress_time = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                progress_hit = float(item.high) >= restore_price
                adverse_hit = float(item.low) <= adverse_price
            else:
                progress_hit = float(item.low) <= restore_price
                adverse_hit = float(item.high) >= adverse_price
            if progress_hit and adverse_hit:
                return None
            if adverse_hit:
                return None
            if progress_hit:
                progress_idx = idx
                progress_time = pd.Timestamp(item.bar_datetime).isoformat()
                break
        if progress_idx < 0:
            return None

        stop_idx = -1
        stop_time = ""
        for idx in range(progress_idx, len(entry_day)):
            item = entry_day.iloc[idx]
            if position_direction == "long":
                stop_hit = float(item["low"]) <= restore_stop_price
            else:
                stop_hit = float(item["high"]) >= restore_stop_price
            if stop_hit:
                stop_idx = idx
                stop_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                break

        restore_volume = int(pending["deferred_volume"])
        if restore_volume <= 0:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        event_datetime = getattr(self.strategy_engine, "datetime", trade.datetime)
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)

        self._stage002_append_restore_layer(
            state=state,
            direction=position_direction,
            restore_volume=restore_volume,
            restore_price=restore_price,
            stop_price=restore_stop_price,
            event_datetime=event_datetime,
        )
        self._stage002_record_restore_diagnostic(
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
            reason="stage002_delayed_restore_open",
            volume=restore_volume,
            price=restore_price,
        )
        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "open",
                "source": "stage002_delayed_restore_open",
                "price": restore_price,
                "volume": restore_volume,
                "time": progress_time,
            }
        ]

        final_state = "restore_open"
        exit_reason = "stage002_delayed_restore_open"
        final_exit_price = np.nan
        restore_stop_state = "not_stopped_entry_day"
        estimated_restore_pnl = np.nan
        if stop_idx >= 0:
            final_state = "restore_stopped"
            exit_reason = "stage002_delayed_restore_stop_at_original_entry"
            final_exit_price = restore_stop_price
            restore_stop_state = "same_bar_stop" if stop_idx == progress_idx else "entry_day_stop"
            estimated_restore_pnl = sign * (restore_stop_price - restore_price) * self.get_size(contract_vt_symbol) * restore_volume
            add_index = len(state.layers) - 1
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason=exit_reason,
                volume=restore_volume,
                price=restore_stop_price,
            )
            self._close_layers(state, [add_index], restore_stop_price, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=restore_stop_price)
            synthetic_trades.append(
                {
                    "action": "close",
                    "source": exit_reason,
                    "price": restore_stop_price,
                    "volume": restore_volume,
                    "time": stop_time,
                }
            )
            self.stage002_restore_stop_count += 1
        else:
            self._apply_state_target(state, execution_price_override=restore_price)

        self.stage002_restore_event_count += 1
        original_order_id = str(getattr(trade, "vt_orderid", "") or trade.orderid)
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "original_order_id": original_order_id,
            "expected_restore_open_order_id": f"{original_order_id}.stage847_c9.1",
            "expected_restore_close_order_id": f"{original_order_id}.stage847_c9.2" if stop_idx >= 0 else "",
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "original_stop_price": stop_price,
            "risk_price": risk_price,
            "progress_r": progress_r,
            "progress_price": restore_price,
            "adverse_price": adverse_price,
            "restore_price": restore_price,
            "restore_stop_price": restore_stop_price,
            "original_volume": int(pending["original_volume"]),
            "scout_volume": int(pending["scout_volume"]),
            "deferred_volume": int(pending["deferred_volume"]),
            "restore_volume": restore_volume,
            "initial_fraction": float(pending["initial_fraction"]),
            "progress_time": progress_time,
            "progress_bar_index": progress_idx,
            "stop_time": stop_time,
            "stop_bar_index": stop_idx,
            "restore_stop_state": restore_stop_state,
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "estimated_restore_pnl": estimated_restore_pnl,
            "exit_reason": exit_reason,
            "stage002_delayed_restore_checked": 1,
            "note": "entry-day +0.5R progress restores deferred original volume; restored layer stop is original entry price",
            "synthetic_trades": synthetic_trades,
        }
        self.stage002_restore_events.append(event)
        return event


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        profile = s928._c9_15w_profile(metadata, window)
    finally:
        s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C_ARM}_2018_01",
        label="Stage002 delayed restore official C9/15w",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage002 frozen delayed restore. New flat/reverse C9 entries first open "
            "floor(50%) scout volume; deferred original volume is restored only if entry-day minute bars first reach "
            "+0.5R progress before -0.5R adverse. Restored layer stop is original entry, total intended risk stays "
            "below the original full-size entry. No parameter, product, direction, year or month scan."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage002_delayed_restore": True,
        "stage002_initial_fraction": INITIAL_FRACTION,
        "stage002_progress_r": PROGRESS_R,
    }
    result = dict(profile)
    result["profile"] = C_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage002DelayedRestore
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C_ARM)
    return result


def _run_candidate(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s847.START
    original_end = s847.END
    legacy_state = s928._with_legacy_stage372_spec()
    try:
        s847.START = START
        s847.END = END
        combined, frames = _run_profile_with_stage002_frames(profile, metadata)
    finally:
        s847.START = original_start
        s847.END = original_end
        s928._restore_legacy_state(legacy_state)
    return combined, frames


def _run_profile_with_stage002_frames(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s827.s778.s653.s517.START_DT
    original_end = s827.s778.s653.s517.END_DT
    original_preload = s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s827.s778.s653.s517.START_DT = START.to_pydatetime()
        s827.s778.s653.s517.END_DT = END.to_pydatetime()
        s827.s778.s653.s517.PRELOAD_START_DT = s827.s772._preload_for_start(START).to_pydatetime()
        s827.s778.s653.s517.assert_stage196_database_sentinels()
        s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s827.s778.s653.s517.PRELOAD_START_DT,
            s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s847.Stage847StopRetryEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s827.Interval.DAILY,
            start=preload_start,
            end=s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s513._c3_overrides(START.to_pydatetime())),
            start=START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= START.date()) & (daily.index <= END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        restore_events = pd.DataFrame(getattr(strategy, "stage002_restore_events", []) if strategy else [])
        if not restore_events.empty and "synthetic_trades" in restore_events.columns:
            restore_events = restore_events.drop(columns=["synthetic_trades"])
        open_adjustments = pd.DataFrame(getattr(strategy, "stage002_open_adjustments", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events, restore_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "restore_events": restore_events,
            "open_adjustments": open_adjustments,
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["window_id"] = FULL_WINDOW_ID
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s827.s778.s653.s517.START_DT = original_start
        s827.s778.s653.s517.END_DT = original_end
        s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _candidate_summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    spec = profile["spec"]
    row = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    restore_events = frames.get("restore_events", pd.DataFrame())
    open_adjustments = frames.get("open_adjustments", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum())
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
            "restore_event_count": int(len(restore_events)),
            "restore_stop_count": int(
                restore_events["final_state"].astype(str).eq("restore_stopped").sum() if not restore_events.empty else 0
            ),
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
    summary = _read_required_csv(BASELINE_SUMMARY_IN)
    curves = _read_required_csv(BASELINE_CURVES_IN)
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
    base_curve["arm"] = A_ARM
    base_curve["stage"] = STAGE
    base_curve["model_tag"] = MODEL_TAG
    return row, base_curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    a = summary[summary["arm"].eq(A_ARM)].iloc[0]
    c = summary[summary["arm"].eq(C_ARM)].iloc[0]
    return_retention = float(c["total_return_pct"]) / float(a["total_return_pct"]) * 100.0 if float(a["total_return_pct"]) else np.nan
    equity_retention = (float(c["end_equity"]) - CAPITAL) / (float(a["end_equity"]) - CAPITAL) * 100.0
    row = {
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
        "C_open_adjustment_count": int(c.get("open_adjustment_count", 0)),
        "C_restore_event_count": int(c.get("restore_event_count", 0)),
        "C_restore_stop_count": int(c.get("restore_stop_count", 0)),
    }
    return pd.DataFrame([row])


def _cost_stress(profile: dict[str, Any], combined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in [1.0, 2.0, 3.0]:
        row = s650._metrics(combined, profile["spec"].capital, cost_multiplier=multiplier)
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
        C_ARM: "C delayed restore 50% after +0.5R",
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
    axes[0].set_title("Stage002 full-path equity")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
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
    for column in ["restore_volume", "original_volume", "scout_volume", "deferred_volume", "estimated_restore_pnl"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["year", "final_state", "restore_stop_state"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            original_volume=("original_volume", "sum"),
            scout_volume=("scout_volume", "sum"),
            restore_volume=("restore_volume", "sum"),
            estimated_restore_pnl=("estimated_restore_pnl", "sum"),
            median_progress_bar=("progress_bar_index", "median"),
            median_stop_bar=("stop_bar_index", "median"),
        )
        .reset_index()
        .sort_values(["year", "final_state", "restore_stop_state"])
    )


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["restore_volume_num"] = pd.to_numeric(data.get("restore_volume"), errors="coerce").fillna(0.0)
    data["estimated_restore_pnl_num"] = pd.to_numeric(data.get("estimated_restore_pnl"), errors="coerce").fillna(0.0)
    selected: list[pd.DataFrame] = []
    opened = data[data["final_state"].astype(str).eq("restore_open")].copy()
    stopped = data[data["final_state"].astype(str).eq("restore_stopped")].copy()
    if not opened.empty:
        selected.append(opened.sort_values("restore_volume_num", ascending=False).head(8))
    if not stopped.empty:
        selected.append(stopped.sort_values("estimated_restore_pnl_num").head(8))
    if not selected:
        return pd.DataFrame()
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "datetime", "direction", "progress_time"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = s827._normalize_date(row["datetime"])
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
                s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "scout entry"),
                    ("progress_price", "#16a34a", "--", "+0.5R restore"),
                    ("adverse_price", "#7c2d12", ":", "-0.5R adverse"),
                    ("restore_stop_price", "#dc2626", "-.", "restore stop at entry"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("progress_time", "#16a34a", "restore"),
                    ("stop_time", "#dc2626", "restore stop"),
                ]:
                    idx = _index_for_time(day, row.get(time_col))
                    if idx >= 0:
                        ax.axvline(idx, color=color, linewidth=1.0, alpha=0.9, label=label)
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
                    f"state={row.get('final_state')} stop_state={row.get('restore_stop_state')} "
                    f"orig/scout/restore={int(_safe_float(row.get('original_volume'), 0))}/"
                    f"{int(_safe_float(row.get('scout_volume'), 0))}/"
                    f"{int(_safe_float(row.get('restore_volume'), 0))}"
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
                    "restore_stop_state": row.get("restore_stop_state", ""),
                    "original_volume": _safe_float(row.get("original_volume")),
                    "scout_volume": _safe_float(row.get("scout_volume")),
                    "restore_volume": _safe_float(row.get("restore_volume")),
                    "progress_time": row.get("progress_time", ""),
                    "stop_time": row.get("stop_time", ""),
                }
            )
        fig.suptitle("Stage002 delayed restore true-engine entry-day minute-K atlas", fontsize=12)
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
        label = "stage002_full_period_pass_next_halfyear_multistart"
    elif not retention_pass:
        label = "stage002_failed_return_retention_stop_shape_no_param_rescue"
    elif not dd_pass:
        label = "stage002_failed_drawdown_no_param_rescue"
    else:
        label = "stage002_mixed_full_period_no_promotion"
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
            "Use minute-level entry-day path confirmation to delay, not increase, the original C9 risk budget: "
            "open a 50% scout and restore the deferred remainder only after +0.5R progress comes before -0.5R adverse."
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
            "restore_events": str(RESTORE_EVENTS_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
        "external_research_judgment": (
            "pysystemtrade/Carver-style systematic futures material and position-sizing/pyramiding references support "
            "broad risk-budget discipline and confirmation before releasing risk; they do not justify copying exact "
            "minute parameters or rescuing weak windows."
        ),
        "overfit_reflection_before": (
            "No: the rule is frozen from Stage001 first principles, reuses C9's existing 0.5R unit, and does not scan "
            "ratio/R/product/direction/month/year."
        ),
        "continue_value_before": (
            "Yes: Stage001 proxy only proved PnL retention directionally; a true path engine is required before any "
            "promotion discussion."
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
        "restore_event_count",
        "open_adjustment_count",
    ]
    lines = [
        "# Stage002 延迟恢复风险真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- A：当前官方 C9/15w 全路径。",
        "- C：C9/15w + `delayed_restore_50pct_after_0.5R_progress`。",
        "- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- pysystemtrade / Robert Carver 系统化趋势框架支持风险预算、多市场、多起点验证；不支持单弱窗口补丁。",
        "- 趋势跟随仓位管理资料说明 position sizing 会显著改变风险收益路径；确认后释放风险可以研究，但不能增加总风险或扫参数救结果。",
        "- 本阶段只采用第一性原则：先小仓、方向证明后恢复原风险、失败快速承认；不复制外部具体分钟参数。",
        "",
        "## 预声明规则",
        "",
        "- flat/reverse 新信号原始手数 `>=2` 时，先开 `floor(50%)` scout；`1` 手信号无法拆分，保持原版。",
        "- rollover reopen 不拆分，避免换月时人为降风险。",
        "- 入场日分钟 K 若先触达有利 `+0.5R`，恢复剩余原始手数；若先触达不利 `-0.5R`，交给 C9 stop/retry，且不恢复。",
        "- 恢复层止损固定为原入场价，因此不是额外 pyramiding，也不增加原始风险预算。",
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
        "## Restore Events By Year",
        "",
        _md_table(event_summary, max_rows=30),
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
    print(f"[stage002] loading metadata and minute bars", flush=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s928._load_stage861_full_minute_bars(vt_symbols)
    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    print("[stage002] running candidate true engine", flush=True)
    profile = _candidate_profile(metadata)
    combined, frames = _run_candidate(profile, metadata)
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
    restore_events = frames.get("restore_events", pd.DataFrame()).copy()
    event_summary = _event_summary(restore_events)
    atlas_paths, atlas_manifest = _plot_atlas(restore_events, minute_bars)
    closed_lots = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    decision = _decision(comparison, cost_stress)
    if decision["decision"] == "stage002_full_period_pass_next_halfyear_multistart":
        decision["overfit_reflection_after"] = (
            "No immediate full-period overfit signal: the frozen C rule retained 80%+ return and improved path risk, "
            "but completion still requires half-year/monthly cold-start visual verification before any promotion."
        )
        decision["continue_value_after"] = (
            "Yes: escalate to predeclared half-year and monthly starts, plus cost-pressure visuals; do not tune the rule."
        )
    elif decision["decision"] == "stage002_failed_return_retention_stop_shape_no_param_rescue":
        decision["overfit_reflection_after"] = (
            "No new overfit was introduced, but trying to rescue the shape by changing 50% or 0.5R after seeing this result "
            "would be overfitting."
        )
        decision["continue_value_after"] = (
            "No for this exact shape if full-period return retention is below 80%; switch to a different first-principles "
            "execution idea instead of parameter rescue."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No parameter search occurred, but the mixed result is insufficient for promotion; further tuning around this "
            "same shape would be overfitting."
        )
        decision["continue_value_after"] = (
            "Limited: only inspect visual failure mode once, then either run a fixed multi-start if full-period evidence is "
            "strong enough or stop the shape."
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
    restore_events.to_csv(RESTORE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("open_adjustments", pd.DataFrame()).to_csv(OPEN_ADJUSTMENTS_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(summary, comparison, path_diag, event_summary, cost_stress, atlas_paths, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
