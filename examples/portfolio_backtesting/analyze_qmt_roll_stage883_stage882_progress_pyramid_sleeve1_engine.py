from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from types import SimpleNamespace
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
from qmt_roll_portfolio_strategy import PositionLayer


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage883"
MODEL_TAG = "stage883_stage882_progress_pyramid_sleeve1_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C17_ARM = "stage883_stage819_c9_progress_pyramid_sleeve1_once"

START = s847.START
END = s847.END
PYRAMID_PROGRESS_R = 0.5
PYRAMID_MAX_ADD_VOLUME = 1
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
STAGE863_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_summary_{STAGE863_TAG}.csv"
STAGE863_CURVE_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_curve_{STAGE863_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
PYRAMID_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pyramid_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
PATH_DIAGNOSTICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_diagnostics_{MODEL_TAG}.csv"
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


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
    if len(matches):
        return int(matches[0])
    diffs = (pd.to_datetime(day["bar_datetime"], errors="coerce") - ts).abs()
    if diffs.empty:
        return -1
    pos = int(diffs.idxmin())
    return pos if diffs.loc[pos] <= pd.Timedelta(minutes=1) else -1


class QmtRollPortfolioStrategyStage883ProgressPyramid(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage883_progress_pyramid_once: bool = False
    stage883_pyramid_progress_r: float = PYRAMID_PROGRESS_R
    stage883_pyramid_max_add_volume: int = PYRAMID_MAX_ADD_VOLUME

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage883_progress_pyramid_once",
        "stage883_pyramid_progress_r",
        "stage883_pyramid_max_add_volume",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage883_pyramid_event_count",
        "stage883_pyramid_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage883_pyramid_events: list[dict[str, Any]] = []
        self.stage883_pyramid_event_count: int = 0
        self.stage883_pyramid_stop_count: int = 0

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        c9_event = super()._stage847_stop_retry_event_after_open_trade(trade)
        if c9_event:
            c9_event["stage883_pyramid_checked"] = 0
            return c9_event
        if not bool(self.enable_stage883_progress_pyramid_once):
            return None
        return self._stage883_progress_pyramid_event_after_open_trade(trade)

    def _stage883_record_add_diagnostic(
        self,
        *,
        state: Any,
        contract_vt_symbol: str,
        direction: str,
        add_price: float,
        stop_price: float,
        add_volume: int,
        event_datetime: Any,
    ) -> None:
        fake_bar = SimpleNamespace(datetime=event_datetime, close_price=add_price)
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
            "risk_per_contract": abs(add_price - stop_price) * size,
            "margin_ratio": margin_ratio,
            "margin_per_contract": add_price * size * margin_ratio,
            "contracts_by_risk": None,
            "contracts_by_margin": None,
            "contracts_by_single_trade_cap": None,
            "selected_volume": add_volume,
            "risk_multiplier": self._current_streak_multiplier(),
            "sizing_method": "stage883_progress_pyramid",
        }
        self._record_entry_risk_diagnostic(
            product_vt_symbol=state.product_vt_symbol,
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            bar=fake_bar,
            signal="stage883_progress_pyramid",
            layer_kind="stage883_pyramid",
            volume=add_volume,
            stop_price=stop_price,
            risk_mode=state.risk_mode,
            sizing_snapshot=sizing_snapshot,
        )

    def _stage883_append_pyramid_layer(
        self,
        *,
        state: Any,
        direction: str,
        add_volume: int,
        add_price: float,
        stop_price: float,
        event_datetime: Any,
    ) -> None:
        trade_date = s827._normalize_date(event_datetime).strftime("%Y-%m-%d")
        state.layers.append(
            PositionLayer(
                kind="stage883_pyramid",
                direction=direction,
                volume=max(1, int(add_volume)),
                entry_price=float(add_price),
                stop_price=float(stop_price),
                highest_price=float(add_price),
                lowest_price=float(add_price),
                signal="stage883_progress_pyramid",
                entry_date=trade_date,
                margin_ratio=self._margin_ratio_for_symbol(state.contract_vt_symbol),
                entry_price_synced=False,
            )
        )

    def _stage883_progress_pyramid_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        trade_date = s827._normalize_date(trade.datetime)
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        if bars.empty:
            return None
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        if entry_day.empty:
            return None

        entry_price = float(trade.price)
        if entry_price <= 0:
            return None

        candidate_indexes: list[int] = []
        risk_prices: list[float] = []
        for index, layer in enumerate(state.layers):
            if layer.direction != position_direction:
                continue
            candidate_indexes.append(index)
            risk_prices.append(abs(entry_price - float(layer.stop_price)))
        if not candidate_indexes:
            return None

        risk_price = max(risk_prices) if risk_prices else 0.0
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = s827._direction_sign(position_direction)
        progress_r = float(self.stage883_pyramid_progress_r)
        add_price = entry_price + sign * progress_r * risk_price
        adverse_price = entry_price - sign * progress_r * risk_price
        add_stop_price = entry_price

        progress_idx = -1
        progress_time = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                progress_hit = float(item.high) >= add_price
                adverse_hit = float(item.low) <= adverse_price
            else:
                progress_hit = float(item.low) <= add_price
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
                stop_hit = float(item["low"]) <= add_stop_price
            else:
                stop_hit = float(item["high"]) >= add_stop_price
            if stop_hit:
                stop_idx = idx
                stop_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                break

        base_volume = sum(state.layers[index].volume for index in candidate_indexes)
        add_volume = min(int(base_volume), max(1, int(self.stage883_pyramid_max_add_volume)))
        if add_volume <= 0:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        event_datetime = getattr(self.strategy_engine, "datetime", trade.datetime)
        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)

        self._stage883_append_pyramid_layer(
            state=state,
            direction=position_direction,
            add_volume=add_volume,
            add_price=add_price,
            stop_price=add_stop_price,
            event_datetime=event_datetime,
        )
        self._stage883_record_add_diagnostic(
            state=state,
            contract_vt_symbol=contract_vt_symbol,
            direction=position_direction,
            add_price=add_price,
            stop_price=add_stop_price,
            add_volume=add_volume,
            event_datetime=event_datetime,
        )
        self._record_trade_event(
            bar=event_bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=position_direction,
            offset="Open",
            reason="stage883_progress_pyramid_open",
            volume=add_volume,
            price=add_price,
        )
        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "open",
                "source": "stage883_progress_pyramid_open",
                "price": add_price,
                "volume": add_volume,
                "time": progress_time,
            }
        ]

        final_state = "pyramid_addon_open"
        exit_reason = "stage883_progress_pyramid_open"
        final_exit_price = np.nan
        estimated_add_pnl = np.nan
        add_stop_state = "not_stopped_entry_day"
        if stop_idx >= 0:
            final_state = "pyramid_addon_stopped"
            exit_reason = "stage883_progress_pyramid_addon_stop"
            final_exit_price = add_stop_price
            add_stop_state = "same_bar_stop" if stop_idx == progress_idx else "entry_day_stop"
            estimated_add_pnl = sign * (add_stop_price - add_price) * self.get_size(contract_vt_symbol) * add_volume
            add_index = len(state.layers) - 1
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason=exit_reason,
                volume=add_volume,
                price=add_stop_price,
            )
            self._close_layers(state, [add_index], add_stop_price, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=add_stop_price)
            synthetic_trades.append(
                {
                    "action": "close",
                    "source": exit_reason,
                    "price": add_stop_price,
                    "volume": add_volume,
                    "time": stop_time,
                }
            )
            self.stage883_pyramid_stop_count += 1
        else:
            self._apply_state_target(state, execution_price_override=add_price)

        self.stage883_pyramid_event_count += 1
        original_order_id = str(getattr(trade, "vt_orderid", "") or trade.orderid)
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "original_order_id": original_order_id,
            "expected_pyramid_open_order_id": f"{original_order_id}.stage847_c9.1",
            "expected_pyramid_close_order_id": f"{original_order_id}.stage847_c9.2" if stop_idx >= 0 else "",
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "risk_price": risk_price,
            "progress_r": progress_r,
            "progress_price": add_price,
            "adverse_price": adverse_price,
            "pyramid_add_price": add_price,
            "pyramid_stop_price": add_stop_price,
            "pyramid_add_volume": add_volume,
            "base_volume_snapshot": base_volume,
            "progress_time": progress_time,
            "progress_bar_index": progress_idx,
            "stop_time": stop_time,
            "stop_bar_index": stop_idx,
            "add_stop_state": add_stop_state,
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "estimated_add_pnl": estimated_add_pnl,
            "exit_reason": exit_reason,
            "stage883_pyramid_checked": 1,
            "note": "entry-day +0.5R progress sleeve; addon volume is capped at one lot and stop is original entry price",
            "synthetic_trades": synthetic_trades,
        }
        self.stage883_pyramid_events.append(event)
        return event


def _c17_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C17_ARM}_2018",
        label="Stage883 Stage819 C9 plus one-lot +0.5R progress sleeve",
        note=(
            f"{spec.capital.note} | Stage883 C17. Keep C9 unchanged. If the entry-day path first reaches "
            "+0.5R progress before -0.5R adverse, synthesize one capped one-lot add-on sleeve at +0.5R. "
            "The add-on layer has a hard stop at the original entry price; no threshold, volume, product, "
            "direction, or year scan."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage883_progress_pyramid_once": True,
        "stage883_pyramid_progress_r": PYRAMID_PROGRESS_R,
        "stage883_pyramid_max_add_volume": PYRAMID_MAX_ADD_VOLUME,
    }
    result = dict(profile)
    result["profile"] = C17_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage883ProgressPyramid
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
        pyramid_events = pd.DataFrame(getattr(strategy, "stage883_pyramid_events", []) if strategy else [])
        if not pyramid_events.empty and "synthetic_trades" in pyramid_events.columns:
            pyramid_events = pyramid_events.drop(columns=["synthetic_trades"])
        intraday_events = pd.concat([c2_events, stop_retry_events, pyramid_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "pyramid_events": pyramid_events,
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


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C17_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    rows: list[dict[str, Any]] = []
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
                "max_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].max()),
                "p95_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in ["pyramid_add_volume", "base_volume_snapshot", "estimated_add_pnl", "progress_bar_index", "stop_bar_index"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce")
    return (
        data.groupby(["final_state", "add_stop_state", "year"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            pyramid_add_volume=("pyramid_add_volume", "sum"),
            base_volume_snapshot=("base_volume_snapshot", "sum"),
            estimated_add_pnl=("estimated_add_pnl", "sum"),
            median_progress_bar=("progress_bar_index", "median"),
            median_stop_bar=("stop_bar_index", "median"),
        )
        .reset_index()
        .sort_values(["year", "final_state", "add_stop_state"])
    )


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C17_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C17_ARM: "#0f766e"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 stop/retry",
        C17_ARM: "C17 C9 + 1-lot +0.5R sleeve",
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
    axes[0].set_title("Stage883 equity path")
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
    data["estimated_add_pnl_num"] = pd.to_numeric(data.get("estimated_add_pnl"), errors="coerce").fillna(0.0)
    selected: list[pd.DataFrame] = []
    open_events = data[data["final_state"].astype(str).eq("pyramid_addon_open")].copy()
    stopped = data[data["final_state"].astype(str).eq("pyramid_addon_stopped")].copy()
    if not open_events.empty:
        selected.append(open_events.sort_values("pyramid_add_volume", ascending=False).head(8))
    if not stopped.empty:
        selected.append(stopped.sort_values("estimated_add_pnl_num").head(8))
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
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.25 * len(part))), constrained_layout=True)
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
                    ("entry_price", "#2563eb", "-", "original entry/add stop"),
                    ("pyramid_add_price", "#16a34a", "--", "+0.5R add"),
                    ("adverse_price", "#7c2d12", ":", "-0.5R adverse"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for time_col, color, label in [
                    ("progress_time", "#16a34a", "add"),
                    ("stop_time", "#dc2626", "addon stop"),
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
                    f"state={row.get('final_state')} stop_state={row.get('add_stop_state')} "
                    f"add_vol={int(_safe_float(row.get('pyramid_add_volume'), 0))} "
                    f"est_add_pnl={_safe_float(row.get('estimated_add_pnl')):,.0f}"
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
                    "add_stop_state": row.get("add_stop_state", ""),
                    "pyramid_add_volume": _safe_float(row.get("pyramid_add_volume")),
                    "estimated_add_pnl": _safe_float(row.get("estimated_add_pnl")),
                    "progress_time": row.get("progress_time", ""),
                    "stop_time": row.get("stop_time", ""),
                }
            )
        fig.suptitle("Stage883 one-lot +0.5R progress sleeve true-engine entry-day atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    event_summary: pd.DataFrame,
    atlas_paths: list[Path],
    decision_label: str,
) -> None:
    lines = [
        "# Stage883 Stage882 1手顺势加仓 sleeve 真实引擎审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结真实组合引擎审计；不改 Stage372 正式版、不改官方候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py GitHub：组合策略必须落到事件驱动回测成交与仓位状态，代理收益不能替代真实资金路径。",
        "- Turtle/趋势跟随 pyramiding 资料：只给已经盈利的仓位加仓，并对新增风险设置独立止损。",
        "- CFTC stop-loss 教育材料：止损是风险控制工具，不是保证成交质量或收益的 alpha。",
        "- 我的判断：Stage882 证明同手数加仓右尾真实但账户不可生存，因此下一步只能把它降为固定 1 手 sleeve，检验是否还能保留一部分右尾而不推高回撤和保证金。",
        "",
        "## 冻结规则",
        "",
        "- B：C9，即 Stage847 C4 + `0.5R` stop/retry once。",
        "- C：C17，即 C9 保持不变；若入场日先触达 `+0.5R` progress 而不是先触达 `-0.5R` adverse，则按 `+0.5R` 合成最多 `1` 手 add-on sleeve。",
        "- 新增仓止损：原始入场价；入场日回打即合成平仓；否则作为普通仓位进入后续日线退出路径。",
        "- 不扫描 progress R、加仓比例、止损位置、品种、方向、年份或分钟窗口。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Pyramid Event Summary",
        "",
        _md_table(event_summary, max_rows=80),
        "",
        "## Charts",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策：`{decision_label}`",
        "- 通过线：C17 必须在 C9 上同时改善收益、Sharpe，且不恶化最大回撤和 broker10 峰值，才允许进入滚动起点和成本压力。",
        "- 若不通过，说明把右尾参与压缩成小 sleeve 后仍无法改善 C9 的风险收益，停止本 sleeve 分支，不做小数救参。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage863_summary = _load_required_csv(STAGE863_SUMMARY_PATH)
    stage863_curve = _load_required_csv(STAGE863_CURVE_PATH)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s863._load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _c17_profile(metadata)
    combined, frames = _run_profile(profile, metadata)
    c17_summary, c17_curve = s827._metric(profile, combined)
    c17_summary["arm"] = C17_ARM
    c17_curve["arm"] = C17_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    pyramid_events = frames.get("pyramid_events", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = C17_ARM
        closed_lots["variant"] = profile["spec"].capital.variant

    summary = pd.concat(
        [
            stage863_summary[stage863_summary["arm"].isin([C4_ARM, C9_ARM])],
            c17_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage863_curve[stage863_curve["arm"].isin([C4_ARM, C9_ARM])],
            c17_curve,
        ],
        ignore_index=True,
        sort=False,
    )
    comparison = _comparison(summary)
    path_diag = _path_diagnostics(curve)
    event_summary = _event_summary(pyramid_events)
    atlas_paths, atlas_manifest = _plot_atlas(pyramid_events, minute_bars)
    _plot_path(curve)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    stop_retry_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pyramid_events.to_csv(PYRAMID_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    path_diag.to_csv(PATH_DIAGNOSTICS_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    c17_row = comparison[comparison["arm"].eq(C17_ARM)].iloc[0].to_dict()
    c9_row = comparison[comparison["arm"].eq(C9_ARM)].iloc[0].to_dict()
    c17_passes = (
        float(c17_row["end_equity_delta_vs_C9"]) > 0
        and float(c17_row["sharpe_delta_vs_C9"]) > 0
        and float(c17_row["max_dd_delta_vs_C9"]) >= 0
        and float(c17_row["max_broker10_margin_to_equity_pct"])
        <= float(c9_row["max_broker10_margin_to_equity_pct"])
    )
    decision_label = (
        "stage883_progress_pyramid_sleeve1_engine_promising_needs_rolling_cost_stress"
        if c17_passes
        else "stage883_progress_pyramid_sleeve1_engine_not_promoted"
    )
    _write_report(comparison, path_diag, event_summary, atlas_paths, decision_label)

    synthetic_open_orders = set(pyramid_events.get("expected_pyramid_open_order_id", pd.Series(dtype=str)).astype(str))
    synthetic_open_trades = (
        trades[trades.get("order_id", pd.Series(dtype=str)).astype(str).isin(synthetic_open_orders)].copy()
        if not trades.empty and synthetic_open_orders
        else pd.DataFrame()
    )
    synthetic_open_trade_ids = set(synthetic_open_trades.get("trade_id", pd.Series(dtype=str)).astype(str))
    synthetic_lots = (
        closed_lots[closed_lots.get("open_trade_id", pd.Series(dtype=str)).astype(str).isin(synthetic_open_trade_ids)].copy()
        if not closed_lots.empty and synthetic_open_trade_ids
        else pd.DataFrame()
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "minute_source": {
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "rule_type": "c9_plus_once_progress_pyramid",
        "rule": {
            "base_arm": C9_ARM,
            "progress_r": PYRAMID_PROGRESS_R,
            "max_add_volume": PYRAMID_MAX_ADD_VOLUME,
            "addon_stop": "original_entry_price",
            "same_bar_policy": "ambiguous +0.5R and -0.5R before add is skipped; add bar can stop addon at original entry",
            "no_parameter_scan": True,
        },
        "event_summary": {
            "pyramid_events": int(len(pyramid_events)),
            "pyramid_open_events": int(pyramid_events["final_state"].astype(str).eq("pyramid_addon_open").sum())
            if not pyramid_events.empty
            else 0,
            "pyramid_stopped_events": int(
                pyramid_events["final_state"].astype(str).eq("pyramid_addon_stopped").sum()
            )
            if not pyramid_events.empty
            else 0,
            "pyramid_add_volume": float(
                pd.to_numeric(pyramid_events.get("pyramid_add_volume", 0), errors="coerce").fillna(0).sum()
            )
            if not pyramid_events.empty
            else 0.0,
            "synthetic_open_trades": int(len(synthetic_open_trades)),
            "synthetic_closed_lots": int(len(synthetic_lots)),
            "synthetic_lot_realized_pnl": float(
                pd.to_numeric(synthetic_lots.get("realized_pnl", 0), errors="coerce").fillna(0).sum()
            )
            if not synthetic_lots.empty
            else 0.0,
        },
        "event_summary_table": event_summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "path_diagnostics": path_diag.to_dict("records"),
        "decision": decision_label,
        "candidate_result": c17_row,
        "overfit_reflection": (
            "不是本轮调参式过拟合。规则只用 Stage882 失败后预声明的右尾参与预算方向：+0.5R 后最多 1 手 sleeve、原入场价止损，"
            "没有扫阈值、比例、品种、方向或年份。但如果本轮失败后继续微调 0.25R/0.75R、2手/3手或止损位置，就会过拟合。"
        ),
        "continue_value": (
            "只有当 C17 同时改善 C9 的收益、Sharpe、最大回撤和 broker10，才有继续滚动起点和成本压力的价值；"
            "否则小 sleeve 右尾参与也应停止，不应继续救 pyramiding 分支。"
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
            "pyramid_events": str(PYRAMID_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "path_diagnostics": str(PATH_DIAGNOSTICS_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))
    print("event_summary")
    print(event_summary.to_string(index=False) if not event_summary.empty else "empty")


if __name__ == "__main__":
    main()
