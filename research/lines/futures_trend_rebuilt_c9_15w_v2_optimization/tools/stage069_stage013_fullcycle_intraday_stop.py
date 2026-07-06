from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
THIS_TOOLS_DIR = Path(__file__).resolve().parent
UPSTREAM_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for candidate in (str(THIS_TOOLS_DIR), str(UPSTREAM_TOOLS_DIR), str(PORTFOLIO_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import stage064_stage013_reserve_topup_true_engine as s064


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage069"
MODEL_TAG = "stage069_stage013_fullcycle_intraday_stop_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage069_stage013_fullcycle_intraday_stop"

REQUESTED_START = pd.Timestamp("2021-07-01")
REQUESTED_END = pd.Timestamp("2026-07-02")
LATEST_START = pd.Timestamp("2026-01-01")
BASE_CAPITAL = float(s064.BASE_TRADING_CAPITAL)

BASELINE = "stage069_stage013_baseline"
C1_NO_REENTRY = "stage069_fullcycle_intraday_stop_no_reentry"
C2_DAILY_REENTRY = "stage069_fullcycle_intraday_stop_daily_reentry_once"
VARIANTS = (BASELINE, C1_NO_REENTRY, C2_DAILY_REENTRY)
VARIANT_LABELS = {
    BASELINE: "Stage013 baseline",
    C1_NO_REENTRY: "full-cycle intraday stop, no reentry",
    C2_DAILY_REENTRY: "full-cycle intraday stop, daily reentry once",
}
VARIANT_COLORS = {
    BASELINE: "#111827",
    C1_NO_REENTRY: "#2563eb",
    C2_DAILY_REENTRY: "#f97316",
}

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage069_stage013_fullcycle_intraday_stop"
STAGES_DIR = LINE_DIR / "stages"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
KEY_2022_2023_PATH = OUT / f"{OUTPUT_PREFIX}_key_2022_2023_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv.gz"
EVENT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
TRADE_DATE_ALIGNMENT_PATH = OUT / f"{OUTPUT_PREFIX}_trade_date_alignment_{MODEL_TAG}.csv"
CHART_VARIANT_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.png"
CHART_MONTHLY_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_start_return_dd_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_underwater_days_{MODEL_TAG}.png"
CHART_KEY_EQUITY_PATH = OUT / f"{OUTPUT_PREFIX}_key_month_equity_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


Direction = s064.s013.s847.s827.Direction
Offset = s064.s013.s847.s827.Offset
TradeData = s064.s013.s847.s827.TradeData
BarData = s064.s013.s847.s827.BarData
ProductState = s064.s013.s847.s827.s804.QmtRollPortfolioStrategyLongTighterInitialStop.__mro__[-2]


def _json_safe(value: Any) -> Any:
    return s064._json_safe(value)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s064._drawdown_pct(equity)


def _daily_sharpe(nav: pd.Series) -> float:
    return s064._daily_sharpe(nav)


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _build_monthly_starts() -> list[pd.Timestamp]:
    return [pd.Timestamp(item).normalize() for item in pd.date_range(REQUESTED_START, LATEST_START, freq="MS")]


def _event_bar(strategy: Any, vt_symbol: str, fallback: Any) -> Any:
    engine_bars: dict[str, Any] = getattr(strategy.strategy_engine, "bars", {})
    return engine_bars.get(vt_symbol) or fallback


def _normalize_day(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


class QmtRollPortfolioStrategyStage069FullCycleIntradayStop(
    s064.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate
):
    enable_stage069_fullcycle_intraday_stop: bool = False
    stage069_daily_reentry_once: bool = False
    stage069_max_reentries_per_day: int = 1

    parameters = s064.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.parameters + [
        "enable_stage069_fullcycle_intraday_stop",
        "stage069_daily_reentry_once",
        "stage069_max_reentries_per_day",
    ]
    variables = s064.s013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables + [
        "stage069_fullcycle_intraday_stop_count",
        "stage069_fullcycle_intraday_reentry_count",
        "stage069_fullcycle_intraday_retry_failed_count",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage069_fullcycle_intraday_events: list[dict[str, Any]] = []
        self.stage069_fullcycle_intraday_stop_count: int = 0
        self.stage069_fullcycle_intraday_reentry_count: int = 0
        self.stage069_fullcycle_intraday_retry_failed_count: int = 0
        self._stage069_daily_reentry_used: dict[tuple[str, str], int] = {}

    def _stage069_enabled(self) -> bool:
        return bool(self.enable_stage069_fullcycle_intraday_stop) and bool(getattr(self, "trading", False))

    def _stage069_day_bars(self, vt_symbol: str, bar_date: Any) -> pd.DataFrame:
        minute_by_symbol = getattr(self, "stage827_minute_by_symbol", {}) or {}
        bars = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
        if bars.empty:
            return pd.DataFrame()
        day = _normalize_day(bar_date)
        frame = bars[bars["bar_date"].eq(day)].copy().reset_index(drop=True)
        if frame.empty:
            return pd.DataFrame()
        return frame

    @staticmethod
    def _stage069_stop_hit(direction: str, row: pd.Series, stop_price: float) -> bool:
        if direction == "long":
            return float(row["low"]) <= stop_price
        return float(row["high"]) >= stop_price

    @staticmethod
    def _stage069_stop_fill(direction: str, row: pd.Series, stop_price: float) -> float:
        open_price = float(row["open"])
        if direction == "long" and open_price <= stop_price:
            return open_price
        if direction == "short" and open_price >= stop_price:
            return open_price
        return float(stop_price)

    @staticmethod
    def _stage069_reentry_hit(direction: str, row: pd.Series, boundary_price: float) -> bool:
        if direction == "long":
            return float(row["high"]) >= boundary_price
        return float(row["low"]) <= boundary_price

    @staticmethod
    def _stage069_reentry_fill(direction: str, row: pd.Series, boundary_price: float) -> float:
        open_price = float(row["open"])
        if direction == "long" and open_price >= boundary_price:
            return open_price
        if direction == "short" and open_price <= boundary_price:
            return open_price
        return float(boundary_price)

    def _stage069_first_stop(
        self,
        direction: str,
        day_bars: pd.DataFrame,
        stop_price: float,
        start_index: int = 0,
    ) -> dict[str, Any] | None:
        if day_bars.empty or stop_price <= 0:
            return None
        for idx in range(max(0, int(start_index)), len(day_bars)):
            row = day_bars.iloc[idx]
            if self._stage069_stop_hit(direction, row, stop_price):
                return {
                    "index": int(idx),
                    "time": pd.Timestamp(row["bar_datetime"]).isoformat(),
                    "price": self._stage069_stop_fill(direction, row, stop_price),
                    "same_bar_range_note": "stop_bar",
                }
        return None

    def _stage069_first_reentry(
        self,
        direction: str,
        day_bars: pd.DataFrame,
        boundary_price: float,
        start_index: int,
    ) -> dict[str, Any] | None:
        for idx in range(max(0, int(start_index)), len(day_bars)):
            row = day_bars.iloc[idx]
            if self._stage069_reentry_hit(direction, row, boundary_price):
                return {
                    "index": int(idx),
                    "time": pd.Timestamp(row["bar_datetime"]).isoformat(),
                    "price": self._stage069_reentry_fill(direction, row, boundary_price),
                }
        return None

    def _stage069_emit_synthetic_trade(
        self,
        *,
        bar: Any,
        vt_symbol: str,
        position_direction: str,
        offset: Any,
        price: float,
        volume: int,
        event_time: str,
        source: str,
        reason: str,
        sequence_index: int,
    ) -> None:
        if price <= 0 or volume <= 0:
            return
        if offset == Offset.CLOSE:
            direction = Direction.SHORT if position_direction == "long" else Direction.LONG
            self._queue_pending_close_reason(vt_symbol, reason, volume)
        else:
            direction = Direction.LONG if position_direction == "long" else Direction.SHORT

        # The portfolio backtesting engine buckets trades by replay dt date
        # (`engine.datetime`), which can differ from individual contract
        # BarData.datetime around night-session/calendar-date boundaries.
        # Keep the true minute trigger in proxy fields/events, but account the
        # synthetic fill on the owning daily bar to avoid orphan daily_result keys.
        trade_datetime = pd.to_datetime(getattr(self.strategy_engine, "datetime", None), errors="coerce")
        if pd.isna(trade_datetime):
            trade_datetime = pd.to_datetime(getattr(bar, "datetime", self.current_bar_date), errors="coerce")
        trade_datetime = pd.Timestamp(trade_datetime).to_pydatetime()
        engine = self.strategy_engine
        engine.trade_count += 1
        trade = TradeData(
            symbol=bar.symbol,
            exchange=bar.exchange,
            orderid=f"stage069.{len(self.stage069_fullcycle_intraday_events) + 1}.{sequence_index}",
            tradeid=str(engine.trade_count),
            direction=direction,
            offset=offset,
            price=float(price),
            volume=int(volume),
            datetime=trade_datetime,
            gateway_name=engine.gateway_name,
        )
        self.update_trade(trade)
        engine.trades[trade.vt_tradeid] = trade
        engine.source_counter[source] += 1
        engine.trade_usage_rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "orderid": str(trade.orderid),
                "signal_date": _date_text(getattr(bar, "datetime", self.current_bar_date)),
                "fill_date": _date_text(trade_datetime),
                "vt_symbol": str(vt_symbol),
                "direction": direction.value,
                "offset": "Open" if offset == Offset.OPEN else "Close",
                "order_price": float(price),
                "trade_price": float(price),
                "price_delta": 0.0,
                "order_volume": float(volume),
                "price_source": source,
                "proxy_bar_count": np.nan,
                "proxy_first_time": event_time,
                "proxy_last_time": event_time,
            }
        )

    def _stage069_close_without_reentry(
        self,
        *,
        state: Any,
        bar: Any,
        indexes: list[int],
        exit_price: float,
        exit_reason: str,
        profit_giveback_context: bool = False,
    ) -> str:
        if len(indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state,
                exit_price,
                execution_price_override=exit_price,
                exit_reason=exit_reason,
                profit_giveback_context=profit_giveback_context,
            )
            return exit_reason

        closed_volume = sum(state.layers[index].volume for index in indexes)
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=state.contract_vt_symbol,
            product_vt_symbol=state.product_vt_symbol,
            position_direction=state.direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        self._close_layers(
            state,
            indexes,
            exit_price,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            self.execution_price_overrides[state.contract_vt_symbol] = exit_price
            self.set_target(state.contract_vt_symbol, 0)
        return exit_reason

    def _stage069_process_boundary(
        self,
        *,
        state: Any,
        bar: Any,
        boundary_source: str,
        stop_price: float,
        indexes: list[int],
        base_exit_reason: str,
        allow_reentry: bool,
        profit_giveback_context: bool = False,
    ) -> str:
        if not state.layers or not state.contract_vt_symbol or stop_price <= 0:
            return ""

        event_bar = _event_bar(self, state.contract_vt_symbol, bar)
        day_bars = self._stage069_day_bars(state.contract_vt_symbol, event_bar.datetime)
        first_stop = self._stage069_first_stop(state.direction, day_bars, stop_price)
        if not first_stop:
            return ""

        close_volume = sum(state.layers[index].volume for index in indexes)
        if close_volume <= 0:
            return ""

        current_day = _date_text(event_bar.datetime)
        daily_key = (state.contract_vt_symbol, current_day)
        used = int(self._stage069_daily_reentry_used.get(daily_key, 0))
        can_reentry = (
            bool(allow_reentry)
            and bool(self.stage069_daily_reentry_once)
            and used < max(0, int(self.stage069_max_reentries_per_day))
            and len(indexes) == len(state.layers)
        )

        reentry = None
        retry_stop = None
        final_state = "flat_no_reentry"
        exit_reason = f"stage069_intraday_{boundary_source}_stop_no_reentry"
        synthetic_sequence: list[dict[str, Any]] = []

        if can_reentry:
            reentry = self._stage069_first_reentry(
                state.direction,
                day_bars,
                stop_price,
                int(first_stop["index"]) + 1,
            )
            if reentry:
                retry_stop = self._stage069_first_stop(
                    state.direction,
                    day_bars,
                    stop_price,
                    int(reentry["index"]) + 1,
                )
                self._stage069_daily_reentry_used[daily_key] = used + 1
                final_state = "open_after_reentry"
                exit_reason = f"stage069_intraday_{boundary_source}_stop_reentry_open"
                synthetic_sequence = [
                    {
                        "offset": Offset.CLOSE,
                        "source": f"stage069_{boundary_source}_initial_stop",
                        "reason": f"stage069_intraday_{boundary_source}_initial_stop",
                        "price": float(first_stop["price"]),
                        "volume": close_volume,
                        "time": str(first_stop["time"]),
                    },
                    {
                        "offset": Offset.OPEN,
                        "source": f"stage069_{boundary_source}_reentry",
                        "reason": f"stage069_intraday_{boundary_source}_reentry",
                        "price": float(reentry["price"]),
                        "volume": close_volume,
                        "time": str(reentry["time"]),
                    },
                ]
                if retry_stop:
                    final_state = "flat_retry_failed"
                    exit_reason = f"stage069_intraday_{boundary_source}_retry_failed"
                    synthetic_sequence.append(
                        {
                            "offset": Offset.CLOSE,
                            "source": f"stage069_{boundary_source}_retry_failed",
                            "reason": exit_reason,
                            "price": float(retry_stop["price"]),
                            "volume": close_volume,
                            "time": str(retry_stop["time"]),
                        }
                    )

        event = {
            "datetime": event_bar.datetime,
            "date": current_day,
            "vt_symbol": state.contract_vt_symbol,
            "product_vt_symbol": state.product_vt_symbol,
            "direction": state.direction,
            "boundary_source": boundary_source,
            "base_exit_reason": base_exit_reason,
            "exit_reason": exit_reason,
            "stop_price": float(stop_price),
            "first_stop_time": first_stop.get("time", ""),
            "first_stop_bar_index": int(first_stop.get("index", -1)),
            "first_stop_price": float(first_stop.get("price", np.nan)),
            "reentry_time": reentry.get("time", "") if reentry else "",
            "reentry_bar_index": int(reentry.get("index", -1)) if reentry else -1,
            "reentry_price": float(reentry.get("price", np.nan)) if reentry else np.nan,
            "retry_failed_time": retry_stop.get("time", "") if retry_stop else "",
            "retry_failed_bar_index": int(retry_stop.get("index", -1)) if retry_stop else -1,
            "retry_failed_price": float(retry_stop.get("price", np.nan)) if retry_stop else np.nan,
            "retry_reentered": int(reentry is not None),
            "retry_failed": int(retry_stop is not None),
            "final_state": final_state,
            "volume": int(close_volume),
            "layer_count": int(len(indexes)),
            "all_layers": int(len(indexes) == len(state.layers)),
            "minute_bar_count": int(len(day_bars)),
            "allow_reentry": int(bool(can_reentry)),
            "synthetic_trade_count": int(len(synthetic_sequence)),
        }
        self.stage069_fullcycle_intraday_events.append(event)
        self.stage069_fullcycle_intraday_stop_count += 1
        self.stage069_fullcycle_intraday_reentry_count += int(reentry is not None)
        self.stage069_fullcycle_intraday_retry_failed_count += int(retry_stop is not None)

        if synthetic_sequence:
            for sequence_index, item in enumerate(synthetic_sequence, start=1):
                self._stage069_emit_synthetic_trade(
                    bar=event_bar,
                    vt_symbol=state.contract_vt_symbol,
                    position_direction=state.direction,
                    offset=item["offset"],
                    price=float(item["price"]),
                    volume=int(item["volume"]),
                    event_time=str(item["time"]),
                    source=str(item["source"]),
                    reason=str(item["reason"]),
                    sequence_index=sequence_index,
                )
            if final_state == "flat_retry_failed":
                contract_vt_symbol = state.contract_vt_symbol
                state.reset()
                self.set_target(contract_vt_symbol, 0)
            else:
                self._apply_state_target(state)
            return exit_reason

        return self._stage069_close_without_reentry(
            state=state,
            bar=event_bar,
            indexes=indexes,
            exit_price=float(first_stop["price"]),
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )

    def _process_prev2day_stop(self, state: Any, bar: Any, history: pd.DataFrame) -> str:
        if not self._stage069_enabled():
            return super()._process_prev2day_stop(state, bar, history)
        if not self.enable_prev2day_stop or not state.layers:
            return ""
        if state.bars_since_entry < 2 or len(history) < 3:
            return ""
        if self._should_relax_prev2day_stop_for_locked_trend(state, bar, history):
            self.profit_lock_trend_relaxed_prev2day_skip_count += 1
            return ""

        prev2_window = history.iloc[-3:-1]
        if len(prev2_window) < 2:
            return ""

        if state.direction == "long":
            raw_stop = float(prev2_window["low"].min())
            final_stop = raw_stop if state.prev2day_stop_price is None else max(state.prev2day_stop_price, raw_stop)
            state.prev2day_stop_price = final_stop
            if self._should_relax_prev2day_stop_for_post_quality(state, history):
                day_bars = self._stage069_day_bars(state.contract_vt_symbol, bar.datetime)
                if self._stage069_first_stop("long", day_bars, final_stop):
                    state.post_quality_prev2day_relax_done = True
                    self.post_entry_quality_prev2day_relax_skip_count += 1
                    return ""
            return self._stage069_process_boundary(
                state=state,
                bar=bar,
                boundary_source="prev2day",
                stop_price=final_stop,
                indexes=list(range(len(state.layers))),
                base_exit_reason="long_prev2day_stop",
                allow_reentry=True,
            )

        raw_stop = float(prev2_window["high"].max())
        final_stop = raw_stop if state.prev2day_stop_price is None else min(state.prev2day_stop_price, raw_stop)
        state.prev2day_stop_price = final_stop
        if self._should_relax_prev2day_stop_for_post_quality(state, history):
            day_bars = self._stage069_day_bars(state.contract_vt_symbol, bar.datetime)
            if self._stage069_first_stop("short", day_bars, final_stop):
                state.post_quality_prev2day_relax_done = True
                self.post_entry_quality_prev2day_relax_skip_count += 1
                return ""
        return self._stage069_process_boundary(
            state=state,
            bar=bar,
            boundary_source="prev2day",
            stop_price=final_stop,
            indexes=list(range(len(state.layers))),
            base_exit_reason="short_prev2day_stop",
            allow_reentry=True,
        )

    def _process_layer_stops(self, state: Any, bar: Any) -> str:
        if not self._stage069_enabled():
            return super()._process_layer_stops(state, bar)
        direction = state.direction
        triggered_indexes: list[int] = []
        base_triggered = False
        base_stop_price = 0.0
        base_profit_giveback_context = False
        triggered_stop_prices: list[float] = []
        day_bars = self._stage069_day_bars(state.contract_vt_symbol, bar.datetime)

        for index, layer in enumerate(state.layers):
            if self._stage069_first_stop(direction, day_bars, float(layer.stop_price)):
                if layer.kind == "base":
                    base_triggered = True
                    base_stop_price = float(layer.stop_price)
                    base_profit_giveback_context = bool(layer.profit_giveback_stop_active)
                    break
                triggered_indexes.append(index)
                triggered_stop_prices.append(float(layer.stop_price))

        if base_triggered:
            return self._stage069_process_boundary(
                state=state,
                bar=bar,
                boundary_source="base",
                stop_price=base_stop_price,
                indexes=list(range(len(state.layers))),
                base_exit_reason=f"{direction}_base_stop",
                allow_reentry=True,
                profit_giveback_context=base_profit_giveback_context,
            )

        if not triggered_indexes:
            return ""

        stop_reference = max(triggered_stop_prices) if direction == "long" else min(triggered_stop_prices)
        exit_reason = (
            f"stage069_intraday_{direction}_layer_stop_partial"
            if len(state.layers) > len(triggered_indexes)
            else f"stage069_intraday_{direction}_layer_stop_all"
        )
        return self._stage069_process_boundary(
            state=state,
            bar=bar,
            boundary_source="layer",
            stop_price=stop_reference,
            indexes=triggered_indexes,
            base_exit_reason=f"{direction}_layer_stop",
            allow_reentry=len(state.layers) == len(triggered_indexes),
            profit_giveback_context=all(bool(state.layers[index].profit_giveback_stop_active) for index in triggered_indexes),
        )


def _stage069_profile(metadata: dict[str, Any], variant: str) -> dict[str, Any]:
    profile = s064.s013._stage013_profile(metadata)
    spec = profile["spec"]
    if variant == BASELINE:
        capital = replace(
            spec.capital,
            variant=BASELINE,
            label=VARIANT_LABELS[BASELINE],
            note=f"{spec.capital.note} | Stage069 A baseline, no full-cycle intraday stop overlay.",
        )
        result = dict(profile)
        result["profile"] = BASELINE
        result["strategy_cls"] = profile["strategy_cls"]
        result["spec"] = replace(spec, capital=capital, profile=BASELINE)
        return result

    reentry_enabled = variant == C2_DAILY_REENTRY
    capital = replace(
        spec.capital,
        variant=variant,
        label=VARIANT_LABELS[variant],
        note=(
            f"{spec.capital.note} | Stage069 research-only execution overlay. "
            "Daily dynamic stop boundaries are checked on minute bars; reentry is fixed to at most once per day "
            f"and enabled={reentry_enabled}."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage069_fullcycle_intraday_stop": True,
        "stage069_daily_reentry_once": bool(reentry_enabled),
        "stage069_max_reentries_per_day": 1,
    }
    result = dict(profile)
    result["profile"] = variant
    result["strategy_cls"] = QmtRollPortfolioStrategyStage069FullCycleIntradayStop
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=variant)
    return result


def _align_orphan_trade_dates(engine: Any) -> pd.DataFrame:
    keys = sorted(engine.daily_results.keys())
    if not keys:
        return pd.DataFrame()
    key_set = set(keys)
    rows: list[dict[str, Any]] = []
    for trade in engine.trades.values():
        original_timestamp = pd.Timestamp(trade.datetime)
        original_date = original_timestamp.date()
        if original_date in key_set:
            continue
        prior = [item for item in keys if item <= original_date]
        aligned_date = prior[-1] if prior else keys[0]
        intraday_offset = original_timestamp - original_timestamp.normalize()
        aligned_timestamp = pd.Timestamp(aligned_date) + intraday_offset
        if original_timestamp.tzinfo is not None:
            aligned_timestamp = aligned_timestamp.tz_localize(original_timestamp.tzinfo)
        trade.datetime = aligned_timestamp.to_pydatetime()
        rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "order_id": trade.vt_orderid,
                "vt_symbol": trade.vt_symbol,
                "direction": trade.direction.value,
                "offset": trade.offset.value,
                "price": float(trade.price),
                "volume": int(trade.volume),
                "original_datetime": original_timestamp.isoformat(),
                "original_date": original_date.isoformat(),
                "aligned_datetime": aligned_timestamp.isoformat(),
                "aligned_date": aligned_date.isoformat(),
                "reason": "trade_date_not_in_portfolio_daily_results",
            }
        )
    return pd.DataFrame(rows)


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s064.s013.s847.s827.s778.s653.s517.START_DT
    original_end = s064.s013.s847.s827.s778.s653.s517.END_DT
    original_preload = s064.s013.s847.s827.s778.s653.s517.PRELOAD_START_DT
    try:
        s064.s013.s847.s827.s778.s653.s517.START_DT = s064.s013.s847.START.to_pydatetime()
        s064.s013.s847.s827.s778.s653.s517.END_DT = s064.s013.s847.END.to_pydatetime()
        s064.s013.s847.s827.s778.s653.s517.PRELOAD_START_DT = (
            s064.s013.s847.s827.s772._preload_for_start(s064.s013.s847.START).to_pydatetime()
        )
        s064.s013.s847.s827.s778.s653.s517.assert_stage196_database_sentinels()
        s064.s013.s847.s827.s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s064.s013.s847.s827.s778.s653.s517.PRELOAD_START_DT,
            s064.s013.s847.s827.s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s064.s013.s847.s827.s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = s064.s013.s847.Stage847StopRetryEngine(open_map)
        engine.output = (lambda msg: print(msg, flush=True)) if os.environ.get("STAGE069_DEBUG") else (lambda msg: None)
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s064.s013.s847.s827.Interval.DAILY,
            start=preload_start,
            end=s064.s013.s847.s827.s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s064.s013.s847.s827.s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=dict(s064.s013.s847.s513._c3_overrides(s064.s013.s847.START.to_pydatetime())),
            start=s064.s013.s847.START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        trade_date_alignment = _align_orphan_trade_dates(engine)
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            daily_df = pd.DataFrame(
                [{"net_pnl": 0.0, "trade_count": 0.0, "slippage": 0.0, "commission": 0.0, "turnover": 0.0}],
                index=pd.Index([s064.s013.s847.END.date()], name="date"),
            )

        daily = daily_df.copy()
        daily = daily.loc[
            (daily.index >= s064.s013.s847.START.date()) & (daily.index <= s064.s013.s847.END.date())
        ].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["variant"] = spec.capital.variant
        daily["combo_variant"] = spec.capital.variant
        daily["label"] = spec.capital.label
        daily["risk_multiplier"] = spec.capital.risk_multiplier
        daily["note"] = spec.capital.note

        positions = s064.s013.s847.s827.s778.build_positions_df(engine)
        if not positions.empty:
            positions["variant"] = spec.capital.variant
            positions["combo_variant"] = spec.capital.variant
            positions["label"] = spec.capital.label
            positions["risk_multiplier"] = spec.capital.risk_multiplier
            margin_daily, _ = s064.s013.s847.s513._position_margin(positions, metadata)
        else:
            margin_daily = pd.DataFrame(
                columns=["variant", "combo_variant", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            )
        combined = s064.s013.s847.s827.s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        c2_events = pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else [])
        stop_retry_events = pd.DataFrame(getattr(strategy, "stage847_stop_retry_events", []) if strategy else [])
        if not stop_retry_events.empty and "synthetic_trades" in stop_retry_events.columns:
            stop_retry_events = stop_retry_events.drop(columns=["synthetic_trades"])
        stage069_events = pd.DataFrame(getattr(strategy, "stage069_fullcycle_intraday_events", []) if strategy else [])
        pilot_gate_events = pd.DataFrame(getattr(strategy, "stage013_pilot_gate_events", []) if strategy else [])
        intraday_events = pd.concat([c2_events, stop_retry_events, stage069_events], ignore_index=True, sort=False)
        frames = {
            "trades": s064.s013.s847.s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s064.s013.s847.s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s064.s013.s847.s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "stage069_events": stage069_events,
            "pilot_gate_events": pilot_gate_events,
            "pending_orders": s064.s013.s847._active_limit_orders_frame(engine),
            "trade_date_alignment": trade_date_alignment,
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = s064.s013.s847.START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s064.s013.s847.s827.s778.s653.s517.START_DT = original_start
        s064.s013.s847.s827.s778.s653.s517.END_DT = original_end
        s064.s013.s847.s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _run_variant(metadata: dict[str, Any], variant: str, start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s064.s013.s847.START
    original_end = s064.s013.s847.END
    original_minute_by_symbol = s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s064.s901._ensure_c9_minute_bars(metadata)
    try:
        s064.s013.s847.START = start.normalize()
        s064.s013.s847.END = REQUESTED_END.normalize()
        profile = _stage069_profile(metadata, variant)
        combined, frames = _run_profile(profile, metadata)
    finally:
        s064.s013.s847.START = original_start
        s064.s013.s847.END = original_end
        s064.s013.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol

    curve = combined.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["version"] = variant
    curve["variant_label"] = VARIANT_LABELS[variant]
    curve["requested_start"] = _date_text(start)
    curve["requested_start_month"] = _start_month_text(start)
    curve["requested_end"] = _date_text(REQUESTED_END)
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce").ffill() / BASE_CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce").ffill())
    curve["days_since_start"] = np.arange(len(curve), dtype=int)
    for frame in frames.values():
        if frame.empty:
            continue
        frame["stage"] = STAGE
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
        frame["version"] = variant
        frame["variant_label"] = VARIANT_LABELS[variant]
        frame["requested_start"] = _date_text(start)
        frame["requested_start_month"] = _start_month_text(start)
        frame["requested_end"] = _date_text(REQUESTED_END)
    return curve, frames


def _summary_from_curve(curve: pd.DataFrame, events: pd.DataFrame, variant: str, start: pd.Timestamp) -> dict[str, Any]:
    frame = curve.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / BASE_CAPITAL
    drawdown = _drawdown_pct(equity)
    below = equity < BASE_CAPITAL - 1e-9
    below_dates = frame.loc[below, "date"]
    event_count = int(len(events))
    reentry_count = int(pd.to_numeric(events.get("retry_reentered", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    retry_failed_count = int(pd.to_numeric(events.get("retry_failed", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    end_equity = float(equity.iloc[-1])
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": variant,
        "variant_label": VARIANT_LABELS[variant],
        "requested_start": _date_text(start),
        "requested_start_month": _start_month_text(start),
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "account_capital": BASE_CAPITAL,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / BASE_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else 0.0,
        "sharpe": _daily_sharpe(nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "final_nav": float(nav.iloc[-1]),
        "days_below_initial": int(below.sum()),
        "last_below_initial": _date_text(below_dates.iloc[-1]) if not below_dates.empty else "",
        "stage069_event_count": event_count,
        "stage069_reentry_count": reentry_count,
        "stage069_retry_failed_count": retry_failed_count,
    }


def _variant_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, group in summary.groupby("version", sort=False):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        underwater = pd.to_numeric(group["days_below_initial"], errors="coerce").fillna(0)
        rows.append(
            {
                "version": version,
                "variant_label": VARIANT_LABELS.get(version, version),
                "start_count": int(len(group)),
                "positive_count": int(returns.gt(0.0).sum()),
                "min_return_pct": float(returns.min()),
                "p10_return_pct": float(returns.quantile(0.10)),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_dd_pct": float(dds.min()),
                "median_dd_pct": float(dds.median()),
                "max_days_below_initial": int(underwater.max()),
                "median_days_below_initial": float(underwater.median()),
                "total_trade_count_sum": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0.0).sum()),
                "total_slippage_sum": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "stage069_event_count_sum": int(pd.to_numeric(group["stage069_event_count"], errors="coerce").fillna(0).sum()),
                "stage069_reentry_count_sum": int(pd.to_numeric(group["stage069_reentry_count"], errors="coerce").fillna(0).sum()),
                "stage069_retry_failed_count_sum": int(
                    pd.to_numeric(group["stage069_retry_failed_count"], errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _year_summary(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_year"] = frame["requested_start_month"].astype(str).str.slice(0, 4)
    rows: list[dict[str, Any]] = []
    for (version, year), group in frame.groupby(["version", "start_year"], sort=True):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        underwater = pd.to_numeric(group["days_below_initial"], errors="coerce").fillna(0)
        rows.append(
            {
                "version": version,
                "start_year": year,
                "start_count": int(len(group)),
                "positive_count": int(returns.gt(0.0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "worst_dd_pct": float(dds.min()),
                "max_days_below_initial": int(underwater.max()),
            }
        )
    return pd.DataFrame(rows)


def _key_2022_2023(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary[summary["requested_start_month"].astype(str).str.startswith(("2022-", "2023-"))].copy()
    columns = [
        "version",
        "requested_start_month",
        "total_return_pct",
        "max_dd_pct",
        "days_below_initial",
        "last_below_initial",
        "total_trade_count",
        "total_slippage",
        "stage069_event_count",
        "stage069_reentry_count",
        "stage069_retry_failed_count",
    ]
    return frame[columns].sort_values(["requested_start_month", "version"]).reset_index(drop=True)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    frame = events.copy()
    for column in ["retry_reentered", "retry_failed", "synthetic_trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0), errors="coerce").fillna(0)
    grouped = frame.groupby(["version", "boundary_source", "final_state"], dropna=False).agg(
        event_count=("vt_symbol", "count"),
        reentry_count=("retry_reentered", "sum"),
        retry_failed_count=("retry_failed", "sum"),
        synthetic_trade_count=("synthetic_trade_count", "sum"),
    )
    return grouped.reset_index().sort_values(["version", "boundary_source", "final_state"])


def run_backtests() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if not s064.CANDIDATE_AI_PATH.exists():
        print("[stage069] Stage062 candidate AI file missing; rebuilding AI file only", flush=True)
        s064.s062.build_full_monthly_ai_file()

    starts = _build_monthly_starts()
    metadata = s064.s901.s513._metadata()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    closed_frames: list[pd.DataFrame] = []
    trade_date_alignment_frames: list[pd.DataFrame] = []
    total_runs = len(starts) * len(VARIANTS)

    run_index = 0
    with s064.s062._patched_live_ai_path(s064.CANDIDATE_AI_PATH):
        for start in starts:
            for variant in VARIANTS:
                run_index += 1
                print(
                    f"[stage069] run {run_index}/{total_runs} variant={variant} start={_date_text(start)}",
                    flush=True,
                )
                curve, frames = _run_variant(metadata, variant, start)
                events = frames.get("stage069_events", pd.DataFrame()).copy()
                summary_row = _summary_from_curve(curve, events, variant, start)
                alignment = frames.get("trade_date_alignment", pd.DataFrame()).copy()
                summary_row["trade_date_alignment_count"] = int(len(alignment))
                summary_rows.append(summary_row)
                curve_frames.append(curve)
                if not events.empty:
                    event_frames.append(events)
                if not alignment.empty:
                    trade_date_alignment_frames.append(alignment)
                trades = frames.get("trades", pd.DataFrame()).copy()
                if not trades.empty:
                    trade_frames.append(trades)
                closed = s719._build_closed_lots(
                    trades,
                    frames.get("entry_risk", pd.DataFrame()).copy(),
                    frames.get("entry_candidates", pd.DataFrame()).copy(),
                    metadata,
                )
                if not closed.empty:
                    closed["stage"] = STAGE
                    closed["model_tag"] = MODEL_TAG
                    closed["line_id"] = LINE_ID
                    closed["version"] = variant
                    closed["variant_label"] = VARIANT_LABELS[variant]
                    closed["requested_start"] = _date_text(start)
                    closed["requested_start_month"] = _start_month_text(start)
                    closed["requested_end"] = _date_text(REQUESTED_END)
                    closed_frames.append(closed)

    summary = pd.DataFrame(summary_rows).sort_values(["version", "requested_start"]).reset_index(drop=True)
    events = pd.concat(event_frames, ignore_index=True, sort=False) if event_frames else pd.DataFrame()
    return {
        "summary": summary,
        "variant_summary": _variant_summary(summary),
        "year_summary": _year_summary(summary),
        "key_2022_2023": _key_2022_2023(summary),
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "events": events,
        "event_summary": _event_summary(events),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "closed_lots": pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame(),
        "trade_date_alignment": pd.concat(trade_date_alignment_frames, ignore_index=True, sort=False)
        if trade_date_alignment_frames
        else pd.DataFrame(),
    }


def _plot_outputs(summary: pd.DataFrame, variant_summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    plot = variant_summary.copy()
    x = np.arange(len(plot))
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), constrained_layout=True)
    axes[0].bar(x - 0.2, plot["min_return_pct"], width=0.4, color="#ef4444", label="min return %")
    axes[0].bar(x + 0.2, plot["median_return_pct"], width=0.4, color="#22c55e", label="median return %")
    axes[0].axhline(0.0, color="#111827", linewidth=0.9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(plot["variant_label"], rotation=15, ha="right")
    axes[0].set_title("Monthly starts: return")
    axes[0].set_ylabel("return %")
    axes[0].legend(loc="best")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(x - 0.2, plot["worst_dd_pct"], width=0.4, color="#2563eb", label="worst DD %")
    axes[1].bar(x + 0.2, plot["max_days_below_initial"], width=0.4, color="#f97316", label="max days below initial")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(plot["variant_label"], rotation=15, ha="right")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_VARIANT_PATH, dpi=160)
    plt.close(fig)

    order = sorted(summary["requested_start_month"].astype(str).unique())
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    for version in VARIANTS:
        data = summary[summary["version"].eq(version)].copy()
        data["requested_start_month"] = pd.Categorical(data["requested_start_month"].astype(str), categories=order, ordered=True)
        data = data.sort_values("requested_start_month")
        axes[0].plot(
            data["requested_start_month"].astype(str),
            data["total_return_pct"],
            marker="o",
            markersize=3,
            linewidth=1.0,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
        axes[1].plot(
            data["requested_start_month"].astype(str),
            data["max_dd_pct"],
            marker="o",
            markersize=3,
            linewidth=1.0,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    axes[0].axhline(0.0, color="#111827", linewidth=0.9, linestyle="--")
    axes[0].set_title("Monthly starts to 2026-07-02: return")
    axes[0].set_ylabel("return %")
    axes[1].set_title("Monthly starts to 2026-07-02: max drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].tick_params(axis="x", rotation=60)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_MONTHLY_PATH, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(18, 6), constrained_layout=True)
    for version in VARIANTS:
        data = summary[summary["version"].eq(version)].copy()
        data["requested_start_month"] = pd.Categorical(data["requested_start_month"].astype(str), categories=order, ordered=True)
        data = data.sort_values("requested_start_month")
        ax.plot(
            data["requested_start_month"].astype(str),
            data["days_below_initial"],
            marker="o",
            markersize=3,
            linewidth=1.0,
            color=VARIANT_COLORS[version],
            label=VARIANT_LABELS[version],
        )
    ax.set_title("Monthly starts: days below initial capital")
    ax.set_ylabel("days")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)

    key_starts = ["2022-01", "2022-05", "2022-09", "2023-01", "2023-05", "2023-09"]
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False, constrained_layout=True)
    for ax, start in zip(axes.ravel(), key_starts, strict=False):
        for version in VARIANTS:
            frame = curves[
                curves["requested_start_month"].astype(str).eq(start) & curves["version"].astype(str).eq(version)
            ].sort_values("date")
            if frame.empty:
                continue
            ax.plot(frame["date"], frame["account_equity"], linewidth=1.0, color=VARIANT_COLORS[version], label=VARIANT_LABELS[version])
        ax.axhline(BASE_CAPITAL, color="#111827", linewidth=0.8, linestyle="--")
        ax.set_title(f"Account equity start {start}")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="best")
    fig.savefig(CHART_KEY_EQUITY_PATH, dpi=160)
    plt.close(fig)


def _decision(results: dict[str, pd.DataFrame]) -> dict[str, Any]:
    variant = results["variant_summary"].set_index("version")
    baseline = variant.loc[BASELINE]
    no_reentry = variant.loc[C1_NO_REENTRY]
    reentry = variant.loc[C2_DAILY_REENTRY]

    decision_name = "stage069_fullcycle_intraday_stop_keep_research_only"
    reason = (
        "全周期动态保护线日内止损是结构性风控尝试，但本轮没有同时改善最小收益、最长水下和最差回撤；"
        "每日一次重进场显著增加换手和二次止损，说明止损后当天收复同一保护线即重进这条规则在震荡段过于敏感。"
    )
    trade_multiplier = (
        float(reentry["total_trade_count_sum"]) / float(baseline["total_trade_count_sum"])
        if float(baseline["total_trade_count_sum"]) > 0
        else np.inf
    )
    if (
        int(reentry["positive_count"]) >= int(baseline["positive_count"])
        and float(reentry["min_return_pct"]) > float(baseline["min_return_pct"])
        and float(reentry["worst_dd_pct"]) > float(baseline["worst_dd_pct"])
        and float(reentry["median_return_pct"]) >= 0.95 * float(baseline["median_return_pct"])
        and trade_multiplier <= 1.50
    ):
        decision_name = "stage069_daily_reentry_once_candidate_needs_independent_audit"
        reason = (
            "C2 在预声明约束下同时改善最小收益和最差回撤，中位收益保留超过 95%，交易次数没有超过 1.5 倍；"
            "仍需独立 agent 审计合成成交和分钟触发顺序后，才允许讨论合入。"
        )

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_mode": "day",
        "requested_start": REQUESTED_START.date().isoformat(),
        "latest_start": LATEST_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "base_capital": BASE_CAPITAL,
        "variants": list(VARIANTS),
        "start_count_per_arm": int(results["summary"]["requested_start_month"].nunique()),
        "decision": decision_name,
        "decision_reason": reason,
        "baseline_min_return_pct": float(baseline["min_return_pct"]),
        "baseline_median_return_pct": float(baseline["median_return_pct"]),
        "baseline_worst_dd_pct": float(baseline["worst_dd_pct"]),
        "c1_min_return_pct": float(no_reentry["min_return_pct"]),
        "c1_median_return_pct": float(no_reentry["median_return_pct"]),
        "c1_worst_dd_pct": float(no_reentry["worst_dd_pct"]),
        "c2_min_return_pct": float(reentry["min_return_pct"]),
        "c2_median_return_pct": float(reentry["median_return_pct"]),
        "c2_worst_dd_pct": float(reentry["worst_dd_pct"]),
        "c2_trade_count_multiplier_vs_baseline": float(trade_multiplier),
        "strategy_changed": True,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Backtrader/CFTC/CME stop-order references all indicate stop trigger and execution price must be separated; "
            "Stage069 models open-through-stop as worse open fill and same-bar stop-first ordering."
        ),
        "overfit_reflection_before": (
            "否。规则来自结构性执行问题：把已有动态保护线从日线收盘触发提前到分钟触发；不新增产品、日期、R倍数或窗口扫描。"
        ),
        "overfit_reflection_after": (
            "否。三臂固定、全月起点复验，不按 2022/2023 个别路径调整阈值；若后续开始调 stop buffer 或 reentry 次数才会转为过拟合。"
        ),
        "continue_value_before": (
            "有。Stage068 已显示持仓后亏损大于开仓日亏损，且止损触发到成交存在额外损耗。"
        ),
        "continue_value_after": (
            "有，但只作为反证和诊断继续有价值。C2 已经被证伪；C1 说明日内止损能缩短部分水下但会牺牲左尾，"
            "下一步更有价值的是慢确认/资金层，而不是继续调同日重进参数。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "key_2022_2023": str(KEY_2022_2023_PATH),
            "curves": str(CURVES_PATH),
            "events": str(EVENTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "trades": str(TRADES_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "trade_date_alignment": str(TRADE_DATE_ALIGNMENT_PATH),
            "chart_variant": str(CHART_VARIANT_PATH),
            "chart_monthly": str(CHART_MONTHLY_PATH),
            "chart_underwater": str(CHART_UNDERWATER_PATH),
            "chart_key_equity": str(CHART_KEY_EQUITY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def write_records(decision: dict[str, Any], results: dict[str, pd.DataFrame]) -> Path:
    now = datetime.now()
    variant_summary = results["variant_summary"]
    year_summary = results["year_summary"]
    key = results["key_2022_2023"]
    event_summary = results["event_summary"]
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage069 Stage013 full-cycle intraday stop",
                "",
                f"- generated_at: `{decision['generated_at']}`",
                f"- line_id: `{LINE_ID}`",
                f"- start frequency: monthly `{REQUESTED_START.date()}` to `{LATEST_START.date()}`",
                f"- end: `{REQUESTED_END.date()}`",
                f"- AI file: `{s064.CANDIDATE_AI_PATH}`",
                "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
                "",
                "## Variant Summary",
                "",
                _md_table(variant_summary),
                "",
                "## Year Summary",
                "",
                _md_table(year_summary, max_rows=60),
                "",
                "## 2022-2023 Starts",
                "",
                _md_table(key, max_rows=120),
                "",
                "## Event Summary",
                "",
                _md_table(event_summary, max_rows=80),
                "",
                "## Decision",
                "",
                f"- decision: `{decision['decision']}`",
                f"- reason: {decision['decision_reason']}",
                f"- overfit before: {decision['overfit_reflection_before']}",
                f"- overfit after: {decision['overfit_reflection_after']}",
                f"- continue before: {decision['continue_value_before']}",
                f"- continue after: {decision['continue_value_after']}",
                "",
                "## Outputs",
                "",
                *[f"- {key_name}: `{path}`" for key_name, path in decision["outputs"].items()],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage069_stage013_fullcycle_intraday_stop.md"
    base = variant_summary[variant_summary["version"].eq(BASELINE)].iloc[0]
    c1 = variant_summary[variant_summary["version"].eq(C1_NO_REENTRY)].iloc[0]
    c2 = variant_summary[variant_summary["version"].eq(C2_DAILY_REENTRY)].iloc[0]
    stage_lines = [
        "# Stage069 Stage013 full-cycle intraday stop",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否；这是执行/退出 overlay 研究，不是 alpha 新信号，本轮不晋级",
        "- 是否触发A/B：否；未达到可晋级结论前只做隔离研究",
        "",
        "## 外部调研与判断",
        "",
        "- Backtrader stop order execution 文档提示 stop 触发和成交价要区分；本阶段把开盘穿越 stop 记为更差开盘成交。",
        "- CFTC/CME 对期货 stop with protection 的说明也强调触发价不等于保证成交价；本阶段不做完美成交假设。",
        "- 本次判断：只用原策略已经存在的动态保护线，不扫 R 倍数、stop buffer、重进次数、日期或品种。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改正式入口：无",
        "- 删除文件：无",
        "- 新增研究参数：`enable_stage069_fullcycle_intraday_stop`、`stage069_daily_reentry_once`、`stage069_max_reentries_per_day=1`",
        "- 修改正式参数：无",
        "- 删除参数：无",
        "",
        "## 回测参数",
        "",
        "- 起点：`2021-07` 到 `2026-01` 逐月，共 `55` 个起点/臂",
        "- 终点：`2026-07-02`",
        "- 对照臂：A Stage013 baseline；C1 全周期动态保护线分钟止损不重进；C2 全周期动态保护线分钟止损、每天最多一次收复同一保护线重进",
        f"- 资金：`{BASE_CAPITAL:,.0f}`",
        f"- AI 池：`{s064.CANDIDATE_AI_PATH}`",
        "",
        "## 结果摘要",
        "",
        f"- A baseline：正收益 `{int(base['positive_count'])}/55`，最小/中位收益 `{float(base['min_return_pct']):.4f}%/{float(base['median_return_pct']):.4f}%`，最差回撤 `{float(base['worst_dd_pct']):.4f}%`，最长水下 `{int(base['max_days_below_initial'])}` 天，总交易 `{float(base['total_trade_count_sum']):.0f}`。",
        f"- C1 no reentry：正收益 `{int(c1['positive_count'])}/55`，最小/中位收益 `{float(c1['min_return_pct']):.4f}%/{float(c1['median_return_pct']):.4f}%`，最差回撤 `{float(c1['worst_dd_pct']):.4f}%`，最长水下 `{int(c1['max_days_below_initial'])}` 天，总交易 `{float(c1['total_trade_count_sum']):.0f}`，Stage069 事件 `{int(c1['stage069_event_count_sum'])}`。",
        f"- C2 daily reentry：正收益 `{int(c2['positive_count'])}/55`，最小/中位收益 `{float(c2['min_return_pct']):.4f}%/{float(c2['median_return_pct']):.4f}%`，最差回撤 `{float(c2['worst_dd_pct']):.4f}%`，最长水下 `{int(c2['max_days_below_initial'])}` 天，总交易 `{float(c2['total_trade_count_sum']):.0f}`，Stage069 事件 `{int(c2['stage069_event_count_sum'])}`，重进 `{int(c2['stage069_reentry_count_sum'])}`，二次失败 `{int(c2['stage069_retry_failed_count_sum'])}`。",
        "- 分年观察：C1 在 `2022/2023` 启动月明显改善，但 `2024/2025/2026` 启动月明显恶化；C2 在 `2024/2025` 几乎全线恶化，且重进后再次失败比例高。",
        "- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数见 summary/variant_summary；胜率不在本阶段新增，避免合成重进场成交被误读为独立 alpha 胜率。",
        "",
        "## 统计口径 Review",
        "",
        "- C1/C2 只改变 prev2day/base/layer 动态保护线的日内触发时间；AI 月度池、入场信号、仓位计算保持 Stage013。",
        "- C2 的重进锚点是同一动态保护线，不是原始入场价；同一根分钟K不允许先止损再重进，重进从下一根分钟K开始搜索。",
        "- 开盘直接穿越 stop 时按开盘价成交，避免止损价完美成交偏乐观。",
        "- layer partial stop 也可被分钟线触发；只有全仓边界允许每日一次重进。",
        "",
        "## 独立审计补充",
        "",
        "- 独立 agent 复核结论：研究线内只读反证结论有条件通过，数据支持不晋级。",
        "- 口径风险：base/layer/profit-lock/trailing 类动态保护线可能先用当日完整日K更新，再回扫当日分钟线触发，存在执行顺序/PIT 风险；prev2day stop 边界来自前两日，相对安全。",
        "- 因此 Stage069 不能作为执行级精确日内止损证据，只能作为反证和诊断；若继续，应先改成分钟级顺序更新或只使用开盘前已知边界。",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 停止 C2 这种“当天收复同一保护线即重进”的形状，不做 stop buffer / 次数 / 品种救参。",
        "- C1 只保留为诊断工具，不晋级；如果继续研究，应转向更慢确认，例如收盘确认、次日开盘确认、账户状态门槛或储备金层，而不是日内立即重进。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
    return stage_path


def main() -> None:
    print("[stage069] run full-cycle intraday stop study", flush=True)
    results = run_backtests()
    results["summary"].to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["variant_summary"].to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["year_summary"].to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["key_2022_2023"].to_csv(KEY_2022_2023_PATH, index=False, encoding="utf-8-sig")
    results["curves"].to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    results["events"].to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    results["event_summary"].to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    results["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    results["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    results["trade_date_alignment"].to_csv(TRADE_DATE_ALIGNMENT_PATH, index=False, encoding="utf-8-sig")
    _plot_outputs(results["summary"], results["variant_summary"], results["curves"])
    decision = _decision(results)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stage_path = write_records(decision, results)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
