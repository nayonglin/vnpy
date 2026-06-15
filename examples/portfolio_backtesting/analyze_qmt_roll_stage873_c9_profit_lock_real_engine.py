from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import analyze_qmt_roll_stage863_stage847_c10_budget_lock_engine as s863
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage873"
MODEL_TAG = "stage873_c9_profit_lock_real_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage873_c9_profit_lock_real_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C14_ARM = "stage873_stage819_c9_lock1_after2r"

START = s847.START
END = s847.END
TRIGGER_R = 2.0
LOCK_R = 1.0
PER_PAGE = 6
MAX_ATLAS_ROWS = 18

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
PROFIT_LOCK_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profit_lock_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


class QmtRollPortfolioStrategyStage873ProfitLock(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage873_profit_lock_after_2r: bool = False
    stage873_profit_lock_trigger_r: float = TRIGGER_R
    stage873_profit_lock_lock_r: float = LOCK_R

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage873_profit_lock_after_2r",
        "stage873_profit_lock_trigger_r",
        "stage873_profit_lock_lock_r",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage873_profit_lock_exit_count",
        "stage873_profit_lock_activation_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage873_profit_lock_events: list[dict[str, Any]] = []
        self.stage873_profit_lock_state: dict[int, dict[str, Any]] = {}
        self.stage873_profit_lock_exit_count: int = 0
        self.stage873_profit_lock_activation_count: int = 0

    def _stage873_mark_initial_stops(self, state: Any) -> None:
        for layer in getattr(state, "layers", []) or []:
            if not hasattr(layer, "stage873_initial_stop_price"):
                setattr(layer, "stage873_initial_stop_price", float(layer.stop_price))

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
        self._stage873_mark_initial_stops(state)

    def _append_layer(
        self,
        state: Any,
        kind: str,
        volume: int,
        bar: Any,
        signal: str,
        history: pd.DataFrame,
        use_day_extreme_stop: bool = True,
        sizing_snapshot_extra: dict[str, Any] | None = None,
    ) -> None:
        super()._append_layer(
            state,
            kind,
            volume,
            bar,
            signal,
            history,
            use_day_extreme_stop=use_day_extreme_stop,
            sizing_snapshot_extra=sizing_snapshot_extra,
        )
        self._stage873_mark_initial_stops(state)

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        event = super().stage827_intraday_exit_after_open_trade(trade)
        if event:
            return event
        if not bool(self.enable_stage873_profit_lock_after_2r):
            return None
        return self._stage873_profit_lock_after_open_trade(trade)

    def _process_layer_stops(self, state: Any, bar: Any) -> str:
        if bool(self.enable_stage873_profit_lock_after_2r):
            reason = self._stage873_process_profit_lock_for_state(state, bar)
            if reason:
                return reason
        return super()._process_layer_stops(state, bar)

    def _stage873_layer_levels(self, layer: Any) -> dict[str, float] | None:
        entry_price = _safe_float(getattr(layer, "entry_price", np.nan))
        initial_stop = _safe_float(getattr(layer, "stage873_initial_stop_price", np.nan))
        if not np.isfinite(initial_stop):
            initial_stop = _safe_float(getattr(layer, "stop_price", np.nan))
        if not np.isfinite(entry_price) or entry_price <= 0 or not np.isfinite(initial_stop):
            return None
        risk_price = abs(entry_price - initial_stop)
        if not np.isfinite(risk_price) or risk_price <= 0:
            return None
        direction = str(getattr(layer, "direction", ""))
        sign = s827._direction_sign(direction)
        trigger_price = entry_price + sign * float(self.stage873_profit_lock_trigger_r) * risk_price
        lock_price = entry_price + sign * float(self.stage873_profit_lock_lock_r) * risk_price
        return {
            "entry_price": entry_price,
            "initial_stop_price": initial_stop,
            "risk_price": risk_price,
            "trigger_price": trigger_price,
            "lock_price": lock_price,
        }

    def _stage873_scan_layer_day(
        self,
        *,
        layer: Any,
        day: pd.DataFrame,
        active_before_day: bool,
    ) -> dict[str, Any] | None:
        levels = self._stage873_layer_levels(layer)
        if levels is None or day.empty:
            return None
        layer_id = id(layer)
        direction = str(getattr(layer, "direction", ""))
        active = bool(active_before_day)
        activation_time = ""
        activation_ts = pd.NaT
        activation_bar_index = -1
        if active:
            prior = self.stage873_profit_lock_state.get(layer_id, {})
            activation_time = str(prior.get("activation_time", ""))
            activation_ts = pd.to_datetime(activation_time, errors="coerce")
            activation_bar_index = int(prior.get("activation_bar_index", -1) or -1)

        for idx, item in enumerate(day.itertuples(index=False)):
            bar_ts = pd.Timestamp(item.bar_datetime)
            high = float(item.high)
            low = float(item.low)
            if direction == "long":
                trigger_hit = high >= levels["trigger_price"]
                lock_hit = low <= levels["lock_price"]
            else:
                trigger_hit = low <= levels["trigger_price"]
                lock_hit = high >= levels["lock_price"]

            if not active:
                if trigger_hit:
                    active = True
                    activation_ts = bar_ts
                    activation_time = bar_ts.isoformat()
                    activation_bar_index = idx
                    self.stage873_profit_lock_state[layer_id] = {
                        "activation_time": activation_time,
                        "activation_bar_index": activation_bar_index,
                        **levels,
                    }
                    self.stage873_profit_lock_activation_count += 1
                # Same-bar trigger+lock order is unknowable in OHLC minute data.
                # Activate from the next minute to avoid optimistic same-bar exits.
                continue

            if pd.notna(activation_ts) and bar_ts <= activation_ts:
                continue

            if lock_hit:
                return {
                    "layer_id": layer_id,
                    "activation_time": activation_time,
                    "activation_bar_index": activation_bar_index,
                    "exit_time": pd.Timestamp(item.bar_datetime).isoformat(),
                    "exit_bar_index": idx,
                    "exit_price": levels["lock_price"],
                    **levels,
                }
        return None

    def _stage873_current_day(self, vt_symbol: str, date_value: Any) -> pd.DataFrame:
        bars = self.stage827_minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
        if bars.empty:
            return pd.DataFrame()
        day = bars[bars["bar_date"].eq(s827._normalize_date(date_value))].copy()
        if day.empty:
            return pd.DataFrame()
        return day.sort_values("bar_datetime").reset_index(drop=True)

    def _stage873_record_event(
        self,
        *,
        event_datetime: Any,
        vt_symbol: str,
        product_vt_symbol: str,
        direction: str,
        layer: Any,
        scan: dict[str, Any],
        volume: int,
        exit_reason: str,
        entry_day: bool,
    ) -> dict[str, Any]:
        size = self.get_size(vt_symbol)
        estimated_pnl = (
            (float(scan["exit_price"]) - float(scan["entry_price"])) * size * volume
            if direction == "long"
            else (float(scan["entry_price"]) - float(scan["exit_price"])) * size * volume
        )
        event = {
            "datetime": event_datetime,
            "date": s827._normalize_date(event_datetime).date().isoformat(),
            "vt_symbol": vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": direction,
            "layer_kind": str(getattr(layer, "kind", "")),
            "layer_signal": str(getattr(layer, "signal", "")),
            "layer_entry_date": str(getattr(layer, "entry_date", "")),
            "entry_price": float(scan["entry_price"]),
            "initial_stop_price": float(scan["initial_stop_price"]),
            "risk_price": float(scan["risk_price"]),
            "trigger_r": float(self.stage873_profit_lock_trigger_r),
            "lock_r": float(self.stage873_profit_lock_lock_r),
            "trigger_price": float(scan["trigger_price"]),
            "lock_price": float(scan["lock_price"]),
            "activation_time": str(scan.get("activation_time", "")),
            "activation_bar_index": int(scan.get("activation_bar_index", -1)),
            "exit_time": str(scan.get("exit_time", "")),
            "exit_bar_index": int(scan.get("exit_bar_index", -1)),
            "exit_price": float(scan["exit_price"]),
            "volume": int(volume),
            "estimated_pnl_at_lock": float(estimated_pnl),
            "entry_day": int(bool(entry_day)),
            "exit_reason": exit_reason,
        }
        self.stage873_profit_lock_events.append(event)
        return event

    def _stage873_profit_lock_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None
        direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != direction:
            return None

        trade_date = s827._normalize_date(trade.datetime)
        day = self._stage873_current_day(str(trade.vt_symbol), trade_date)
        if day.empty:
            return None

        self._stage873_mark_initial_stops(state)
        best: tuple[int, int, dict[str, Any]] | None = None
        for index, layer in enumerate(list(state.layers)):
            if str(getattr(layer, "direction", "")) != direction:
                continue
            scan = self._stage873_scan_layer_day(layer=layer, day=day, active_before_day=False)
            if scan is None:
                continue
            key = (int(scan["exit_bar_index"]), index)
            if best is None or key < (best[1], best[0]):
                best = (index, int(scan["exit_bar_index"]), scan)
        if best is None:
            return None

        index, _exit_idx, scan = best
        if index >= len(state.layers):
            return None
        layer = state.layers[index]
        volume = int(getattr(layer, "volume", 0) or 0)
        if volume <= 0:
            return None
        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        exit_reason = "stage873_profit_lock_1r_after_2r_entry_day"
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        self._record_trade_event(
            bar=event_bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=volume,
            price=float(scan["exit_price"]),
        )
        self._close_layers(state, [index], float(scan["exit_price"]), exit_reason=exit_reason)
        if state.layers:
            self._apply_state_target(state, execution_price_override=float(scan["exit_price"]))
        else:
            if float(scan["exit_price"]) > 0:
                self.execution_price_overrides[contract_vt_symbol] = float(scan["exit_price"])
            self.set_target(contract_vt_symbol, 0)

        self.stage873_profit_lock_exit_count += 1
        event = self._stage873_record_event(
            event_datetime=trade.datetime,
            vt_symbol=str(trade.vt_symbol),
            product_vt_symbol=product_vt_symbol,
            direction=direction,
            layer=layer,
            scan=scan,
            volume=volume,
            exit_reason=exit_reason,
            entry_day=True,
        )
        event["trade_id"] = trade.vt_tradeid
        event["synthetic_trades"] = [
            {
                "action": "close",
                "source": exit_reason,
                "price": float(scan["exit_price"]),
                "volume": volume,
                "time": str(scan["exit_time"]),
            }
        ]
        return event

    def _stage873_process_profit_lock_for_state(self, state: Any, bar: Any) -> str:
        if state is None or not getattr(state, "layers", None) or not getattr(state, "contract_vt_symbol", ""):
            return ""
        direction = str(getattr(state, "direction", ""))
        if direction not in {"long", "short"}:
            return ""
        day = self._stage873_current_day(str(state.contract_vt_symbol), getattr(bar, "datetime", None))
        if day.empty:
            return ""

        self._stage873_mark_initial_stops(state)
        active_ids = {id(layer) for layer in state.layers}
        for key in list(self.stage873_profit_lock_state):
            if key not in active_ids:
                self.stage873_profit_lock_state.pop(key, None)

        best: tuple[int, int, dict[str, Any]] | None = None
        for index, layer in enumerate(list(state.layers)):
            if str(getattr(layer, "direction", "")) != direction:
                continue
            active = id(layer) in self.stage873_profit_lock_state
            scan = self._stage873_scan_layer_day(layer=layer, day=day, active_before_day=active)
            if scan is None:
                continue
            key = (int(scan["exit_bar_index"]), index)
            if best is None or key < (best[1], best[0]):
                best = (index, int(scan["exit_bar_index"]), scan)
        if best is None:
            return ""

        index, _exit_idx, scan = best
        if index >= len(state.layers):
            return ""
        layer = state.layers[index]
        volume = int(getattr(layer, "volume", 0) or 0)
        if volume <= 0:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        exit_price = float(scan["exit_price"])
        exit_reason = "stage873_profit_lock_1r_after_2r"
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=volume,
            price=exit_price,
        )
        self._close_layers(state, [index], exit_price, exit_reason=exit_reason)
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        self.stage873_profit_lock_exit_count += 1
        self._stage873_record_event(
            event_datetime=getattr(bar, "datetime", None),
            vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            direction=direction,
            layer=layer,
            scan=scan,
            volume=volume,
            exit_reason=exit_reason,
            entry_day=False,
        )
        self.stage873_profit_lock_state.pop(id(layer), None)
        return exit_reason


def _c14_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C14_ARM}_2018",
        label="Stage873 Stage819 C9 plus 2R/1R minute profit lock",
        note=(
            f"{spec.capital.note} | Stage873 C14. Keep C9 unchanged. For each live layer, once minute path first "
            "touches +2R from its filled entry and original stop distance, move a hard protective exit to +1R. "
            "Same-bar trigger and lock is not exited because minute OHLC cannot prove order."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage873_profit_lock_after_2r": True,
        "stage873_profit_lock_trigger_r": TRIGGER_R,
        "stage873_profit_lock_lock_r": LOCK_R,
    }
    result = dict(profile)
    result["profile"] = C14_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage873ProfitLock
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
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
        profit_lock_events = pd.DataFrame(getattr(strategy, "stage873_profit_lock_events", []) if strategy else [])
        if not profit_lock_events.empty and "synthetic_trades" in profit_lock_events.columns:
            profit_lock_events = profit_lock_events.drop(columns=["synthetic_trades"])
        intraday_events = pd.concat([c2_events, stop_retry_events, profit_lock_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "profit_lock_events": profit_lock_events,
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s827.s778.s653.s517.START_DT = original_start
        s827.s778.s653.s517.END_DT = original_end
        s827.s778.s653.s517.PRELOAD_START_DT = original_preload


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
    c9 = summary[summary["arm"].eq(C9_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_C4": row["end_equity"] - c4["end_equity"],
                "end_equity_delta_vs_C9": row["end_equity"] - c9["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_C4": row["max_dd_pct"] - c4["max_dd_pct"],
                "max_dd_delta_vs_C9": row["max_dd_pct"] - c9["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_C4": row["sharpe"] - c4["sharpe"],
                "sharpe_delta_vs_C9": row["sharpe"] - c9["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in ["volume", "estimated_pnl_at_lock", "entry_day", "activation_bar_index", "exit_bar_index"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["profile", "exit_reason", "year"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            volume=("volume", "sum"),
            entry_day_events=("entry_day", "sum"),
            estimated_pnl_at_lock=("estimated_pnl_at_lock", "sum"),
            median_activation_bar=("activation_bar_index", "median"),
            median_exit_bar=("exit_bar_index", "median"),
        )
        .reset_index()
        .sort_values(["profile", "year", "exit_reason"])
    )


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C14_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C14_ARM: "#0f766e"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 stop/retry",
        C14_ARM: "C14 C9 + 2R/1R lock",
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
    axes[0].set_title("Stage873 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["abs_estimated_pnl_at_lock"] = pd.to_numeric(data.get("estimated_pnl_at_lock", 0), errors="coerce").abs()
    selected: list[pd.DataFrame] = []
    selected.append(data.sort_values("abs_estimated_pnl_at_lock", ascending=False).head(10))
    if "entry_day" in data.columns:
        selected.append(data[pd.to_numeric(data["entry_day"], errors="coerce").eq(1)].head(4))
    if not selected:
        return pd.DataFrame()
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "exit_time", "entry_price", "volume"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_profit_lock_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.2 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            exit_time = pd.to_datetime(row.get("exit_time"), errors="coerce")
            plot_date = s827._normalize_date(exit_time) if pd.notna(exit_time) else s827._normalize_date(row["datetime"])
            direction = str(row["direction"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(plot_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {plot_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                for price_col, color, linestyle, label in [
                    ("entry_price", "#2563eb", "-", "entry"),
                    ("trigger_price", "#0f766e", "--", "+2R trigger"),
                    ("lock_price", "#dc2626", "--", "+1R lock"),
                    ("initial_stop_price", "#7c2d12", ":", "initial stop"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("activation_time", "#0f766e", "activation"),
                    ("exit_time", "#dc2626", "lock exit"),
                ]:
                    ts = pd.to_datetime(row.get(time_col), errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.9, alpha=0.85, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{vt_symbol} {direction} {plot_date:%Y-%m-%d} "
                f"reason={row.get('exit_reason', '')} vol={int(_safe_float(row.get('volume'), 0))} "
                f"entry={_safe_float(row.get('entry_price')):.2f} lock={_safe_float(row.get('lock_price')):.2f} "
                f"estPnL={_safe_float(row.get('estimated_pnl_at_lock')):,.0f}"
            )
            ax.set_title(title, fontsize=8.2, loc="left")
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "plot_date": plot_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "exit_reason": row.get("exit_reason", ""),
                    "volume": int(_safe_float(row.get("volume"), 0)),
                    "entry_price": _safe_float(row.get("entry_price")),
                    "trigger_price": _safe_float(row.get("trigger_price")),
                    "lock_price": _safe_float(row.get("lock_price")),
                    "estimated_pnl_at_lock": _safe_float(row.get("estimated_pnl_at_lock")),
                    "activation_time": row.get("activation_time", ""),
                    "exit_time": row.get("exit_time", ""),
                }
            )
        fig.suptitle("Stage873 C9 + 2R/1R real profit-lock minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(comparison: pd.DataFrame) -> str:
    c14 = comparison[comparison["arm"].eq(C14_ARM)]
    if c14.empty:
        return "stage873_profit_lock_failed_no_c14"
    row = c14.iloc[0]
    c9_broker = comparison.loc[comparison["arm"].eq(C9_ARM), "max_broker10_margin_to_equity_pct"].iloc[0]
    if (
        row["end_equity_delta_vs_C9"] > 0
        and row["max_dd_delta_vs_C9"] >= 0
        and row["sharpe_delta_vs_C9"] > 0
        and row["max_broker10_margin_to_equity_pct"] <= c9_broker
    ):
        return "stage873_profit_lock_promising_needs_robustness"
    return "stage873_profit_lock_not_promoted"


def _write_report(
    comparison: pd.DataFrame,
    event_summary: pd.DataFrame,
    profit_lock_events: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    lines = [
        "# Stage873 C9 + 2R/1R 真实利润锁定引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结真实逐分钟引擎验证；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle Trading 原始规则强调趋势跟随要让利润奔跑，并用止损纪律控制风险：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf",
        "- Backtrader StopTrail 文档说明追踪止损是可执行语义，但真实回测必须验证是否误杀趋势右尾：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "- Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- 我的判断：固定止盈已被 Stage872 反证，本阶段只验证一条冻结的利润保护，不再扫 R。",
        "",
        "## 规则语义",
        "",
        "- C4：Stage830 broker10 entry cap。",
        "- C9：Stage847 C4 + `0.5R` stop-first + 原入场价 reclaim 后允许一次重试。",
        "- C14：C9 保持不变；每个 live layer 按实际成交 entry 与原始 stop distance 计算 R。逐分钟先触及 `+2R` 后，保护位上移到 `+1R`；之后逐分钟触及 `+1R` 即合成平仓。",
        "- 同一根分钟K同时触发 `+2R` 与 `+1R` 回落时不在同根出场，避免 OHLC 顺序不明带来的乐观偏差。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Profit Lock Event Summary",
        "",
        _md_table(event_summary, max_rows=40),
        "",
        "## Largest Profit Lock Events",
        "",
        _md_table(
            profit_lock_events.sort_values("estimated_pnl_at_lock", ascending=False).head(20)
            if not profit_lock_events.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Charts",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策：`{decision}`",
        "- 若 C14 未同时改善 C9 收益、回撤、Sharpe 与 broker10，则停止利润锁定分支，不继续救参。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s863._load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [s830._cap_profile(metadata), s847._c9_profile(metadata), _c14_profile(metadata)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    merged_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "entry_risk": [],
        "entry_candidates": [],
        "trade_events": [],
        "intraday_events": [],
        "stop_retry_events": [],
        "profit_lock_events": [],
    }
    closed_frames: list[pd.DataFrame] = []

    for profile in profiles:
        combined, frames = _run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        summary["arm"] = profile["profile"]
        curve["arm"] = profile["profile"]
        summaries.append(summary)
        curves.append(curve)
        for key in merged_frames:
            frame = frames.get(key, pd.DataFrame())
            if not frame.empty:
                merged_frames[key].append(frame)
        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
        if not closed.empty:
            closed["arm"] = profile["profile"]
            closed["variant"] = profile["spec"].capital.variant
            closed_frames.append(closed)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    output_frames = {
        key: pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame()
        for key, value in merged_frames.items()
    }
    output_frames["closed_lots"] = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    profit_lock_events = output_frames["profit_lock_events"].copy()
    event_summary = _event_summary(profit_lock_events)
    _plot_path(curve)
    atlas_paths, atlas_manifest = _plot_profit_lock_atlas(
        profit_lock_events[profit_lock_events.get("profile", "").astype(str).eq(C14_ARM)].copy()
        if not profit_lock_events.empty and "profile" in profit_lock_events.columns
        else pd.DataFrame(),
        minute_bars,
    )
    decision = _decision(comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    output_frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    output_frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["stop_retry_events"].to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    profit_lock_events.to_csv(PROFIT_LOCK_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(comparison, event_summary, profit_lock_events, atlas_paths, decision)

    c14_events = (
        profit_lock_events[profit_lock_events["profile"].astype(str).eq(C14_ARM)].copy()
        if not profit_lock_events.empty and "profile" in profit_lock_events.columns
        else pd.DataFrame()
    )
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": True,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "minute_source": {
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "rule": {
            "base_arm": C9_ARM,
            "trigger_r": TRIGGER_R,
            "lock_r": LOCK_R,
            "same_bar_policy": "activate_only_no_exit_on_same_bar_trigger_and_lock",
            "scope": "per live layer, original stop distance, minute path during holding period",
        },
        "comparison": comparison.to_dict("records"),
        "event_summary": event_summary.to_dict("records"),
        "c14_profit_lock_events": int(len(c14_events)),
        "c14_profit_lock_entry_day_events": int(pd.to_numeric(c14_events.get("entry_day", 0), errors="coerce").fillna(0).sum())
        if not c14_events.empty
        else 0,
        "decision": decision,
        "overfit_reflection": (
            "本阶段只把 Stage872 最强上限线索冻结为 +2R 后锁 +1R 的真实逐分钟引擎；没有扫描 R、"
            "时间窗、品种、方向、年份或重试次数。同根触发/回落不出场，以压低 OHLC 顺序乐观偏差。"
        ),
        "continue_value": (
            "若 C14 同时改善 C9 收益、回撤、Sharpe 与 broker10，才继续做滚动起点/成本压力；"
            "否则停止利润锁定分支。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "profit_lock_events": str(PROFIT_LOCK_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
