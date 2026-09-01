from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Direction, Interval, Offset
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage826_stage819_intraday_ac_overlay as s826
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage827"
MODEL_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
OUTPUT_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL
STOP_R = 1.0
CONFIRM_R = 1.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

_GLOBAL_MINUTE_BY_SYMBOL: dict[str, pd.DataFrame] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _direction_sign(direction: str) -> float:
    return 1.0 if direction == "long" else -1.0


def _normalize_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


class QmtRollPortfolioStrategyStage827C2(s804.QmtRollPortfolioStrategyLongTighterInitialStop):
    enable_stage827_intraday_c2_stop: bool = False
    stage827_intraday_c2_stop_r: float = STOP_R
    stage827_intraday_c2_confirm_r: float = CONFIRM_R

    parameters = s804.QmtRollPortfolioStrategyLongTighterInitialStop.parameters + [
        "enable_stage827_intraday_c2_stop",
        "stage827_intraday_c2_stop_r",
        "stage827_intraday_c2_confirm_r",
    ]
    variables = s804.QmtRollPortfolioStrategyLongTighterInitialStop.variables + [
        "stage827_intraday_c2_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage827_minute_by_symbol = _GLOBAL_MINUTE_BY_SYMBOL
        self.stage827_intraday_c2_events: list[dict[str, Any]] = []
        self.stage827_intraday_c2_stop_count: int = 0

    def stage827_intraday_exit_after_open_trade(self, trade: TradeData) -> dict[str, Any] | None:
        if not self.enable_stage827_intraday_c2_stop:
            return None
        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        trade_date = _normalize_date(trade.datetime)
        trade_date_text = trade_date.strftime("%Y-%m-%d")
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        if bars.empty:
            return None
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy()
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

        sign = _direction_sign(position_direction)
        stop_price = entry_price - sign * float(self.stage827_intraday_c2_stop_r) * risk_price
        confirm_price = entry_price + sign * float(self.stage827_intraday_c2_confirm_r) * risk_price
        hit_time = ""
        hit_note = ""
        for item in entry_day.itertuples(index=False):
            if position_direction == "long":
                stop_hit = float(item.low) <= stop_price
                confirm_hit = float(item.high) >= confirm_price
            else:
                stop_hit = float(item.high) >= stop_price
                confirm_hit = float(item.low) <= confirm_price
            if stop_hit:
                hit_time = pd.Timestamp(item.bar_datetime).isoformat()
                hit_note = "same_bar_conservative_stop_first" if confirm_hit else "1R stop before 1R confirm"
                break
            if confirm_hit:
                return None
        if not hit_time:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None
        exit_reason = "stage827_intraday_c2_1r_stop"
        engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
        event_bar = engine_bars.get(contract_vt_symbol)

        if len(candidate_indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state,
                stop_price,
                execution_price_override=stop_price,
                exit_reason=exit_reason,
            )
        else:
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason=exit_reason,
                volume=close_volume,
                price=stop_price,
            )
            self._close_layers(state, candidate_indexes, stop_price, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=stop_price)

        self.stage827_intraday_c2_stop_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "confirm_price": confirm_price,
            "risk_price": risk_price,
            "volume": close_volume,
            "hit_time": hit_time,
            "note": hit_note,
            "exit_reason": exit_reason,
        }
        self.stage827_intraday_c2_events.append(event)
        return event


class Stage827IntradayC2Engine(s778.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine):
    def _fill_order(self, order: Any, bar: BarData) -> None:
        trade_price, price_source, proxy = self._resolve_trade_price(order, bar)
        if trade_price <= 0 or float(order.price) <= 0:
            return
        if order.status == Status.SUBMITTING:
            order.status = Status.NOTTRADED
            self.strategy.update_order(order)

        order.traded = order.volume
        order.status = Status.ALLTRADED
        self.strategy.update_order(order)

        if order.vt_orderid in self.active_limit_orders:
            self.active_limit_orders.pop(order.vt_orderid)

        self.trade_count += 1
        trade = TradeData(
            symbol=order.symbol,
            exchange=order.exchange,
            orderid=order.orderid,
            tradeid=str(self.trade_count),
            direction=order.direction,
            offset=order.offset,
            price=trade_price,
            volume=order.volume,
            datetime=self.datetime,
            gateway_name=self.gateway_name,
        )
        self.strategy.update_trade(trade)
        self.trades[trade.vt_tradeid] = trade
        self.source_counter[price_source] += 1
        self.trade_usage_rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "orderid": str(order.orderid),
                "signal_date": s778.s653.s517.s506.s501._naive_date(order.datetime),
                "fill_date": s778.s653.s517.s506.s501._naive_date(self.datetime),
                "vt_symbol": str(order.vt_symbol),
                "direction": s778.s653.s517.s506.s501._direction_text(order.direction),
                "offset": s778.s653.s517.s506.s501._offset_text(order.offset),
                "order_price": float(order.price),
                "trade_price": float(trade_price),
                "price_delta": float(trade_price) - float(order.price),
                "order_volume": float(order.volume),
                "price_source": price_source,
                "proxy_bar_count": proxy.get("proxy_bar_count", np.nan),
                "proxy_first_time": proxy.get("proxy_first_time", ""),
                "proxy_last_time": proxy.get("proxy_last_time", ""),
            }
        )

        if order.offset == Offset.OPEN:
            hook = getattr(self.strategy, "stage827_intraday_exit_after_open_trade", None)
            if callable(hook):
                exit_event = hook(trade)
                if exit_event:
                    self._fill_synthetic_intraday_close(order, trade, exit_event)

    def _fill_synthetic_intraday_close(self, order: Any, open_trade: TradeData, exit_event: dict[str, Any]) -> None:
        close_volume = int(exit_event.get("volume") or 0)
        close_price = float(exit_event.get("stop_price") or 0.0)
        if close_volume <= 0 or close_price <= 0:
            return
        close_direction = Direction.SHORT if open_trade.direction == Direction.LONG else Direction.LONG
        self.trade_count += 1
        trade = TradeData(
            symbol=order.symbol,
            exchange=order.exchange,
            orderid=f"{order.orderid}.stage827_c2",
            tradeid=str(self.trade_count),
            direction=close_direction,
            offset=Offset.CLOSE,
            price=close_price,
            volume=close_volume,
            datetime=self.datetime,
            gateway_name=self.gateway_name,
        )
        self.strategy.update_trade(trade)
        self.trades[trade.vt_tradeid] = trade
        self.source_counter["stage827_intraday_c2_1r_stop"] += 1
        self.trade_usage_rows.append(
            {
                "trade_id": trade.vt_tradeid,
                "orderid": str(trade.orderid),
                "signal_date": s778.s653.s517.s506.s501._naive_date(order.datetime),
                "fill_date": s778.s653.s517.s506.s501._naive_date(self.datetime),
                "vt_symbol": str(order.vt_symbol),
                "direction": s778.s653.s517.s506.s501._direction_text(close_direction),
                "offset": "Close",
                "order_price": close_price,
                "trade_price": close_price,
                "price_delta": 0.0,
                "order_volume": float(close_volume),
                "price_source": "stage827_intraday_c2_1r_stop",
                "proxy_bar_count": np.nan,
                "proxy_first_time": exit_event.get("hit_time", ""),
                "proxy_last_time": exit_event.get("hit_time", ""),
            }
        )


def _profile(metadata: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    profile = s825._profile(metadata)
    spec = profile["spec"]
    suffix = "c2_engine" if enabled else "baseline"
    capital = replace(
        spec.capital,
        variant=f"stage827_stage819_{suffix}_2018",
        label=f"Stage827 Stage819 {suffix} 2018 start",
        note=(
            f"{spec.capital.note} | Stage827 isolated strategy subclass. "
            "C2 intraday first-1R stop is enabled only for the C arm."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": bool(enabled),
        "stage827_intraday_c2_stop_r": STOP_R,
        "stage827_intraday_c2_confirm_r": CONFIRM_R,
    }
    result = dict(profile)
    result["profile"] = f"stage827_stage819_{suffix}"
    result["strategy_cls"] = QmtRollPortfolioStrategyStage827C2
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _run_profile(profile: dict[str, Any], metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    spec = replace(profile["spec"])
    original_start = s778.s653.s517.START_DT
    original_end = s778.s653.s517.END_DT
    original_preload = s778.s653.s517.PRELOAD_START_DT
    try:
        s778.s653.s517.START_DT = START.to_pydatetime()
        s778.s653.s517.END_DT = END.to_pydatetime()
        s778.s653.s517.PRELOAD_START_DT = s772._preload_for_start(START).to_pydatetime()

        s778.s653.s517.assert_stage196_database_sentinels()
        s778.s653.s517.s506._patch_stage506_raw_roots()
        preload_start = max(
            s778.s653.s517.PRELOAD_START_DT,
            s778.s653.s517.START_DT - pd.Timedelta(days=365).to_pytimedelta(),
        )
        _, open_map = s778.s653.s517.s506.s501._seed_proxy_maps()
        engine = Stage827IntradayC2Engine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=Interval.DAILY,
            start=preload_start,
            end=s778.s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s772._build_setting(
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

        positions = s778.build_positions_df(engine)
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
        combined = s772._combine_daily(daily, margin_daily, spec)
        strategy = getattr(engine, "strategy", None)
        frames = {
            "trades": s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": pd.DataFrame(getattr(strategy, "stage827_intraday_c2_events", []) if strategy else []),
        }
        for frame in frames.values():
            if frame.empty:
                continue
            frame["profile"] = profile["profile"]
            frame["start_month"] = START.strftime("%Y-%m")
            frame["variant"] = spec.capital.variant
        return combined, frames
    finally:
        s778.s653.s517.START_DT = original_start
        s778.s653.s517.END_DT = original_end
        s778.s653.s517.PRELOAD_START_DT = original_preload


def _metric(profile: dict[str, Any], combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, curve = s804._metric_from_combined(profile, combined, START)
    summary["arm"] = profile["profile"]
    curve["arm"] = profile["profile"]
    return summary, curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].str.endswith("baseline")].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_A": row["end_equity"] - base["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_A": row["max_dd_pct"] - base["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_A": row["sharpe"] - base["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_slippage_delta_vs_A": row["total_slippage"] - base["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "total_trade_count_delta_vs_A": row["total_trade_count"] - base["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, comparison: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> None:
    intraday = frames.get("intraday_events", pd.DataFrame())
    c_closed = frames.get("closed_lots", pd.DataFrame())
    intraday_by_year = pd.DataFrame()
    if not intraday.empty:
        data = intraday.copy()
        data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
        data["year"] = data["datetime"].dt.year
        intraday_by_year = (
            data.groupby("year", dropna=False)
            .agg(events=("vt_symbol", "size"), products=("product_vt_symbol", "nunique"), volume=("volume", "sum"))
            .reset_index()
        )

    lines = [
        "# Stage827 Stage819 C2组合引擎A/C",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：隔离 subclass + 自定义 engine 的完整组合回放尝试；不改正式策略文件、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：Stage819 原始候选，使用同一 subclass 但关闭 C2。",
        "- C：开仓成交后，用入场日分钟K判断 `1R` 逆向止损是否先于 `1R` 顺向确认；若是，则同日合成平仓成交，更新组合持仓、资金和后续信号路径。",
        "- 同一根分钟K同时触发止损和确认，按保守口径记为止损先发生。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Intraday Stop Events By Year",
        "",
        _md_table(intraday_by_year, max_rows=30),
        "",
        "## Closed Lots Snapshot",
        "",
        _md_table(
            c_closed[["lot_id", "vt_symbol", "direction", "entry_date", "exit_date", "realized_pnl", "exit_reason", "signal"]].head(20)
            if not c_closed.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Judgment",
        "",
        "- 本阶段比 Stage826 更接近真实组合路径，因为 C2 平仓会影响后续持仓、资金、保证金和信号再入场。",
        "- 若 C 提高收益但恶化回撤，不能晋级；下一步应先归因二阶风险，而不是调参数救结果。",
        "- 仍需谨慎：当前 engine 是日线引擎内合成同日分钟止损成交，不是完整分钟bar组合引擎。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global _GLOBAL_MINUTE_BY_SYMBOL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    _GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [_profile(metadata, enabled=False), _profile(metadata, enabled=True)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    merged_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "entry_risk": [],
        "entry_candidates": [],
        "trade_events": [],
        "intraday_events": [],
    }
    closed_frames: list[pd.DataFrame] = []

    for profile in profiles:
        combined, frames = _run_profile(profile, metadata)
        summary, curve = _metric(profile, combined)
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

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    output_frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    output_frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, comparison, output_frames)

    c_row = comparison[comparison["arm"].str.endswith("c2_engine")].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "rules": {
            "C2_engine": {
                "stop_r": STOP_R,
                "confirm_r": CONFIRM_R,
                "same_bar_policy": "conservative_stop_first",
            }
        },
        "comparison": comparison.to_dict("records"),
        "intraday_event_count": int(len(output_frames["intraday_events"])),
        "decision": "engine_ac_research_only_not_promoted",
        "candidate_result": c_row,
        "overfit_reflection": (
            "C2 is still frozen at 1R/1R. The engine replay increases evidence quality, but minute coverage and "
            "synthetic same-day close semantics still require more validation before promotion."
        ),
        "continue_value": (
            "Continue if C2 beats A in this engine path; next validation should be monthly starts and cost stress, not threshold tuning."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
