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
import analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine as s840
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage847"
MODEL_TAG = "stage847_stage830_c4_stop_retry_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"

STAGE830_TAG = s840.STAGE830_TAG
STAGE830_PREFIX = s840.STAGE830_PREFIX

BASE_ARM = s830.BASE_ARM
C2_ARM = s830.C2_ARM
C4_ARM = s830.CAP_ARM
C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"

START = s827.START
END = s827.END
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL

STOP_RETRY_R = 0.5
MAX_RETRIES = 1
PER_PAGE = 4
MAX_ATLAS_ROWS = 16
OPENING_RANGE_BARS = 15

STAGE830_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_summary_{STAGE830_TAG}.csv"
STAGE830_CURVE_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_curve_{STAGE830_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
C2_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c2_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
CAP_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cap_events_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_event_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required Stage830 output: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


class QmtRollPortfolioStrategyStage847C9StopRetry(s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap):
    enable_stage847_half_r_stop_retry: bool = False
    stage847_stop_retry_r: float = STOP_RETRY_R
    stage847_max_retries: int = MAX_RETRIES

    parameters = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.parameters + [
        "enable_stage847_half_r_stop_retry",
        "stage847_stop_retry_r",
        "stage847_max_retries",
    ]
    variables = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.variables + [
        "stage847_stop_retry_event_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage847_stop_retry_events: list[dict[str, Any]] = []
        self.stage847_stop_retry_event_count: int = 0

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        if self.enable_stage847_half_r_stop_retry:
            event = self._stage847_stop_retry_event_after_open_trade(trade)
            if event:
                return event
        return super().stage827_intraday_exit_after_open_trade(trade)

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
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
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().reset_index(drop=True)
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
        stop_price = entry_price - sign * float(self.stage847_stop_retry_r) * risk_price
        progress_price = entry_price + sign * float(self.stage847_stop_retry_r) * risk_price
        first_stop_idx = -1
        first_stop_time = ""
        first_note = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                adverse_hit = float(item.low) <= stop_price
                progress_hit = float(item.high) >= progress_price
            else:
                adverse_hit = float(item.high) >= stop_price
                progress_hit = float(item.low) <= progress_price
            if adverse_hit:
                first_stop_idx = idx
                first_stop_time = pd.Timestamp(item.bar_datetime).isoformat()
                first_note = "same_bar_conservative_05r_stop_first" if progress_hit else "0.5R adverse before 0.5R progress"
                break
            if progress_hit:
                return None
        if first_stop_idx < 0:
            return None

        reentry_idx = -1
        reentry_time = ""
        max_retries = max(0, int(self.stage847_max_retries))
        if max_retries > 0:
            for idx in range(first_stop_idx + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    reclaimed = float(item["high"]) >= entry_price
                else:
                    reclaimed = float(item["low"]) <= entry_price
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
                    retry_stop_hit = float(item["low"]) <= stop_price
                else:
                    retry_stop_hit = float(item["high"]) >= stop_price
                if retry_stop_hit:
                    retry_failed_idx = idx
                    retry_failed_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "close",
                "source": "stage847_intraday_05r_initial_stop",
                "price": stop_price,
                "volume": close_volume,
                "time": first_stop_time,
            }
        ]
        final_state = "flat_no_reentry"
        exit_reason = "stage847_intraday_05r_stop_no_reentry"
        final_exit_price = stop_price

        if reentry_idx >= 0:
            synthetic_trades.append(
                {
                    "action": "open",
                    "source": "stage847_intraday_reentry_at_original_entry",
                    "price": entry_price,
                    "volume": close_volume,
                    "time": reentry_time,
                }
            )
            final_state = "open_after_reentry"
            exit_reason = "stage847_intraday_05r_stop_reentry_open"
            final_exit_price = np.nan
            if retry_failed_idx >= 0:
                synthetic_trades.append(
                    {
                        "action": "close",
                        "source": "stage847_intraday_retry_failed_05r_stop",
                        "price": stop_price,
                        "volume": close_volume,
                        "time": retry_failed_time,
                    }
                )
                final_state = "flat_retry_failed"
                exit_reason = "stage847_intraday_retry_failed_05r_stop"
                final_exit_price = stop_price

        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        if final_state != "open_after_reentry":
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

        self.stage847_stop_retry_event_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "progress_price": progress_price,
            "risk_price": risk_price,
            "stop_r": float(self.stage847_stop_retry_r),
            "max_retries": max_retries,
            "volume": close_volume,
            "first_stop_time": first_stop_time,
            "first_stop_bar_index": first_stop_idx,
            "reentry_time": reentry_time,
            "reentry_bar_index": reentry_idx,
            "retry_failed_time": retry_failed_time,
            "retry_failed_bar_index": retry_failed_idx,
            "retry_reentered": int(reentry_idx >= 0),
            "retry_failed": int(retry_failed_idx >= 0),
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "note": first_note,
            "exit_reason": exit_reason,
            "synthetic_trades": synthetic_trades,
        }
        self.stage847_stop_retry_events.append(event)
        return event


class Stage847StopRetryEngine(s840.Stage840IntradayEngine):
    def _fill_synthetic_intraday_close(self, order: Any, open_trade: s827.TradeData, exit_event: dict[str, Any]) -> None:
        sequence = exit_event.get("synthetic_trades")
        if not isinstance(sequence, list) or not sequence:
            super()._fill_synthetic_intraday_close(order, open_trade, exit_event)
            return

        for index, item in enumerate(sequence, start=1):
            action = str(item.get("action") or "")
            price = float(item.get("price") or 0.0)
            volume = int(item.get("volume") or 0)
            source = str(item.get("source") or "stage847_intraday_stop_retry")
            if price <= 0 or volume <= 0:
                continue
            if action == "close":
                direction = s827.Direction.SHORT if open_trade.direction == s827.Direction.LONG else s827.Direction.LONG
                offset = s827.Offset.CLOSE
            elif action == "open":
                direction = open_trade.direction
                offset = s827.Offset.OPEN
            else:
                continue
            self.trade_count += 1
            trade = s827.TradeData(
                symbol=order.symbol,
                exchange=order.exchange,
                orderid=f"{order.orderid}.stage847_c9.{index}",
                tradeid=str(self.trade_count),
                direction=direction,
                offset=offset,
                price=price,
                volume=volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )
            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade
            self.source_counter[source] += 1
            self.trade_usage_rows.append(
                {
                    "trade_id": trade.vt_tradeid,
                    "orderid": str(trade.orderid),
                    "signal_date": s827.s778.s653.s517.s506.s501._naive_date(order.datetime),
                    "fill_date": s827.s778.s653.s517.s506.s501._naive_date(self.datetime),
                    "vt_symbol": str(order.vt_symbol),
                    "direction": s827.s778.s653.s517.s506.s501._direction_text(direction),
                    "offset": "Open" if offset == s827.Offset.OPEN else "Close",
                    "order_price": price,
                    "trade_price": price,
                    "price_delta": 0.0,
                    "order_volume": float(volume),
                    "price_source": source,
                    "proxy_bar_count": np.nan,
                    "proxy_first_time": item.get("time", ""),
                    "proxy_last_time": item.get("time", ""),
                }
            )


def _c9_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s830._cap_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C9_ARM}_2018",
        label="Stage847 Stage819 C4 plus 0.5R stop retry-on-reclaim 2018 start",
        note=(
            f"{spec.capital.note} | Stage847 frozen C9. After C4 entry, if entry-day price first hits "
            "0.5R adverse before 0.5R progress, synthesize a -0.5R stop. If price later reclaims the original "
            "entry level on the same entry day, reopen once at the original entry price; if the retry again hits "
            "0.5R adverse the same day, close and do not retry again."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "enable_stage847_half_r_stop_retry": True,
        "stage847_stop_retry_r": STOP_RETRY_R,
        "stage847_max_retries": MAX_RETRIES,
    }
    result = dict(profile)
    result["profile"] = C9_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _active_limit_orders_frame(engine: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for vt_orderid, order in (getattr(engine, "active_limit_orders", {}) or {}).items():
        rows.append(
            {
                "vt_orderid": str(vt_orderid),
                "orderid": str(getattr(order, "orderid", "")),
                "vt_symbol": str(getattr(order, "vt_symbol", "")),
                "direction": _enum_text(getattr(order, "direction", "")),
                "offset": _enum_text(getattr(order, "offset", "")),
                "price": float(getattr(order, "price", 0.0) or 0.0),
                "volume": int(float(getattr(order, "volume", 0) or 0)),
                "traded": int(float(getattr(order, "traded", 0) or 0)),
                "datetime": getattr(order, "datetime", ""),
                "status": _enum_text(getattr(order, "status", "")),
            }
        )
    return pd.DataFrame(rows)


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
        engine = Stage847StopRetryEngine(open_map)
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
            daily_df = pd.DataFrame(
                [
                    {
                        "net_pnl": 0.0,
                        "trade_count": 0.0,
                        "slippage": 0.0,
                        "commission": 0.0,
                        "turnover": 0.0,
                    }
                ],
                index=pd.Index([END.date()], name="date"),
            )

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
        intraday_events = pd.concat([c2_events, stop_retry_events], ignore_index=True, sort=False)
        frames = {
            "trades": s827.s778.build_trades_df(engine),
            "positions": positions,
            "entry_risk": s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates": s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
            "intraday_events": intraday_events,
            "c2_events": c2_events,
            "stop_retry_events": stop_retry_events,
            "pending_orders": _active_limit_orders_frame(engine),
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
    base = summary[summary["arm"].eq(BASE_ARM)].iloc[0]
    c2 = summary[summary["arm"].eq(C2_ARM)].iloc[0]
    c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_A": row["end_equity"] - base["end_equity"],
                "end_equity_delta_vs_C2": row["end_equity"] - c2["end_equity"],
                "end_equity_delta_vs_C4": row["end_equity"] - c4["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_A": row["max_dd_pct"] - base["max_dd_pct"],
                "max_dd_delta_vs_C2": row["max_dd_pct"] - c2["max_dd_pct"],
                "max_dd_delta_vs_C4": row["max_dd_pct"] - c4["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_A": row["sharpe"] - base["sharpe"],
                "sharpe_delta_vs_C4": row["sharpe"] - c4["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM, C9_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {BASE_ARM: "#2563eb", C2_ARM: "#dc2626", C4_ARM: "#16a34a", C9_ARM: "#7c3aed"}
    labels = {
        BASE_ARM: "A baseline",
        C2_ARM: "C2 naked",
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 0.5R stop + retry once",
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
    axes[0].set_title("Stage847 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM, C9_ARM])].copy()
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


def _events_by_year(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    temp = events.copy()
    for column, default in {
        "retry_reentered": 0,
        "retry_failed": 0,
        "risk_price": np.nan,
    }.items():
        if column not in temp.columns:
            temp[column] = default
    temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
    temp["year"] = temp["datetime"].dt.year
    agg = (
        temp.groupby("year", dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            volume=("volume", "sum"),
            reentered=("retry_reentered", "sum"),
            retry_failed=("retry_failed", "sum"),
            avg_risk_price=("risk_price", "mean"),
        )
        .reset_index()
    )
    return agg


def _stop_retry_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for bucket, group in events.groupby("final_state", dropna=False):
        rows.append(
            {
                "final_state": str(bucket),
                "events": int(len(group)),
                "products": int(group["product_vt_symbol"].nunique()),
                "volume": float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "median_risk_price": float(pd.to_numeric(group["risk_price"], errors="coerce").median()),
                "first_stop_min_bar": int(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").min()),
                "first_stop_median_bar": float(pd.to_numeric(group["first_stop_bar_index"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values("events", ascending=False).reset_index(drop=True)


def _select_atlas_events(events: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_date"] = pd.to_datetime(data["datetime"], errors="coerce").map(
        lambda value: s827._normalize_date(value) if pd.notna(value) else pd.NaT
    )
    lots = closed_lots.copy()
    if not lots.empty:
        lots["entry_date_norm"] = pd.to_datetime(lots["entry_date"], errors="coerce").map(
            lambda value: s827._normalize_date(value) if pd.notna(value) else pd.NaT
        )
        lots["event_key"] = (
            lots["vt_symbol"].astype(str)
            + "|"
            + lots["direction"].astype(str)
            + "|"
            + lots["entry_date_norm"].dt.strftime("%Y-%m-%d")
        )
        data["event_key"] = (
            data["vt_symbol"].astype(str)
            + "|"
            + data["direction"].astype(str)
            + "|"
            + data["entry_date"].dt.strftime("%Y-%m-%d")
        )
        lot_cols = ["event_key", "realized_pnl", "r_multiple", "exit_reason"]
        data = data.merge(lots[lot_cols].drop_duplicates("event_key"), on="event_key", how="left")
    selected: list[pd.DataFrame] = []
    for state in ["flat_no_reentry", "open_after_reentry", "flat_retry_failed"]:
        part = data[data["final_state"].astype(str).eq(state)].copy()
        if part.empty:
            continue
        if "realized_pnl" in part.columns:
            if state == "open_after_reentry":
                part = part.sort_values("realized_pnl", ascending=False)
            else:
                part = part.sort_values("realized_pnl")
        part["atlas_reason"] = state
        selected.append(part.head(6))
    if not selected:
        return pd.DataFrame()
    return pd.concat(selected, ignore_index=True, sort=False).drop_duplicates(["vt_symbol", "entry_date", "direction"]).head(MAX_ATLAS_ROWS)


def _plot_event_atlas(events: pd.DataFrame, closed_lots: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events, closed_lots)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = s827._normalize_date(row["entry_date"])
            direction = str(row["direction"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = day[day["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True) if not day.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                entry_price = _safe_float(row.get("entry_price"))
                stop_price = _safe_float(row.get("stop_price"))
                progress_price = _safe_float(row.get("progress_price"))
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.95, label="entry/reentry")
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linestyle="--", linewidth=0.9, label="0.5R stop")
                if np.isfinite(progress_price):
                    ax.axhline(progress_price, color="#16a34a", linestyle="--", linewidth=0.85, label="0.5R progress")
                for marker_col, color, label in [
                    ("first_stop_time", "#dc2626", "first stop"),
                    ("reentry_time", "#2563eb", "reentry"),
                    ("retry_failed_time", "#7c2d12", "retry failed"),
                ]:
                    ts = pd.to_datetime(row.get(marker_col), errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.9, alpha=0.8, label=label)
                if len(day) >= OPENING_RANGE_BARS:
                    ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.18)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{row.get('atlas_reason', '')} | {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                f"state={row.get('final_state', '')} pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"R={_safe_float(row.get('r_multiple')):.2f} first={row.get('first_stop_time', '')} "
                f"reentry={row.get('reentry_time', '')} retry_fail={row.get('retry_failed_time', '')}"
            )
            ax.set_title(title, fontsize=8.1, loc="left")
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "final_state": row.get("final_state", ""),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "first_stop_time": row.get("first_stop_time", ""),
                    "reentry_time": row.get("reentry_time", ""),
                    "retry_failed_time": row.get("retry_failed_time", ""),
                }
            )
        fig.suptitle("Stage847 C9 stop/retry entry-day minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    cap_events: pd.DataFrame,
    c2_events: pd.DataFrame,
    stop_retry_events: pd.DataFrame,
    event_summary: pd.DataFrame,
    closed_lots: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    cap_by_year = pd.DataFrame()
    if not cap_events.empty:
        temp = cap_events.copy()
        temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
        temp["year"] = temp["datetime"].dt.year
        cap_by_year = (
            temp.groupby("year", dropna=False)
            .agg(
                events=("reason", "size"),
                blocked=("reason", lambda s: int(s.astype(str).eq("broker10_margin_cap_block").sum())),
                reduced_volume=("reduced_volume", "sum"),
                avg_projected_before=("projected_broker10_margin_to_equity_before", "mean"),
                avg_projected_after=("projected_broker10_margin_to_equity_after", "mean"),
            )
            .reset_index()
        )

    lines = [
        "# Stage847 C4 + 0.5R实时止损重试真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage819 候选独立研究线的冻结真实引擎 A/C；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types",
        "- CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management",
        "- CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- 我的判断：止损和再入场必须在成交事件顺序里验证；lot-level proxy 只能给线索，不能证明组合资金路径。",
        "",
        "## 规则语义",
        "",
        "- A：Stage827 baseline，即 Stage819 原始候选复现。",
        "- C2：开仓后若入场日分钟K先触发 `1R` 逆向止损而非 `1R` 顺向确认，则同日止损。",
        "- C4：C2 保持不变；flat-entry 开仓前若 projected broker10 margin/equity 超过 `100%`，则降手数到不超过 `100%`。",
        "- C9：C4 保持不变；若入场日先触发 `0.5R` 逆向且未先触发 `0.5R` 顺向进展，则先按 `-0.5R` 合成平仓；若同一入场日后续重新穿越原入场价，则只允许一次按原入场价合成重开；若重开后再次触发 `0.5R` 逆向，则再次平仓且不再重试。",
        "- 同一根分钟K同时触发进展和逆向，按保守口径记为止损先发生。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=12),
        "",
        "## C9 Stop-Retry Summary",
        "",
        _md_table(event_summary, max_rows=20),
        "",
        "## C9 Events By Year",
        "",
        _md_table(_events_by_year(stop_retry_events), max_rows=20),
        "",
        "## C2 Events By Year",
        "",
        _md_table(_events_by_year(c2_events), max_rows=20),
        "",
        "## Cap Events By Year",
        "",
        _md_table(cap_by_year, max_rows=20),
        "",
        "## Largest C9 Events",
        "",
        _md_table(stop_retry_events.sort_values("volume", ascending=False).head(20) if not stop_retry_events.empty else pd.DataFrame(), max_rows=20),
        "",
        "## C9 Closed Lots Snapshot",
        "",
        _md_table(
            closed_lots[["lot_id", "vt_symbol", "direction", "entry_date", "exit_date", "volume", "realized_pnl", "exit_reason", "signal"]].head(20)
            if not closed_lots.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Charts",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        *[f"- stop/retry atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只验证 Stage846 的 P2 线索能否穿过真实组合资金联动；不允许因为单次结果继续扫 R 倍数、分钟窗口或重试次数。",
        "- 若 C9 未同时改善 C4 的收益、回撤、Sharpe 和 broker10 路径，则不进入官方候选、不触发 A/B。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage830_summary = _load_required_csv(STAGE830_SUMMARY_PATH)
    stage830_curve = _load_required_csv(STAGE830_CURVE_PATH)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _c9_profile(metadata)
    combined, frames = _run_profile(profile, metadata)
    c9_summary, c9_curve = s827._metric(profile, combined)
    c9_summary["arm"] = C9_ARM
    c9_curve["arm"] = C9_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    c2_events = frames.get("c2_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = C9_ARM
        closed_lots["variant"] = profile["spec"].capital.variant

    cap_events = pd.DataFrame()
    if not trade_events.empty and "reason" in trade_events.columns:
        cap_events = trade_events[trade_events["reason"].astype(str).str.startswith("broker10_margin_cap")].copy()
        for column in [
            "selected_volume_before",
            "selected_volume_after",
            "reduced_volume",
            "estimated_equity",
            "reserved_margin_before",
            "margin_per_contract",
            "broker_margin_multiplier",
            "cap_ratio",
            "max_affordable_volume",
            "projected_broker10_margin_to_equity_before",
            "projected_broker10_margin_to_equity_after",
        ]:
            cap_events[column] = pd.to_numeric(cap_events.get(column, 0), errors="coerce").fillna(0.0)

    summary = pd.concat(
        [
            stage830_summary[stage830_summary["arm"].isin([BASE_ARM, C2_ARM, C4_ARM])],
            c9_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage830_curve[stage830_curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM])],
            c9_curve,
        ],
        ignore_index=True,
        sort=False,
    )
    comparison = _comparison(summary)
    path_diag = _path_diagnostics(curve)
    event_summary = _stop_retry_event_summary(stop_retry_events)
    atlas_paths, atlas_manifest = _plot_event_atlas(stop_retry_events, closed_lots)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    c2_events.to_csv(C2_EVENTS_PATH, index=False, encoding="utf-8-sig")
    stop_retry_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    cap_events.to_csv(CAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(comparison, path_diag, cap_events, c2_events, stop_retry_events, event_summary, closed_lots, atlas_paths)

    c9_row = comparison[comparison["arm"].eq(C9_ARM)].iloc[0].to_dict()
    c4_row = comparison[comparison["arm"].eq(C4_ARM)].iloc[0].to_dict()
    c9_beats_c4_return = float(c9_row["end_equity_delta_vs_C4"]) > 0
    c9_beats_c4_dd = float(c9_row["max_dd_delta_vs_C4"]) >= 0
    c9_beats_c4_sharpe = float(c9_row["sharpe_delta_vs_C4"]) >= 0
    c9_beats_c4_broker = float(c9_row["max_broker10_margin_to_equity_pct"]) <= float(
        c4_row["max_broker10_margin_to_equity_pct"]
    )
    decision_label = (
        "stage847_c9_promising_requires_yearly_cost_pressure_stress"
        if c9_beats_c4_return and c9_beats_c4_dd and c9_beats_c4_sharpe and c9_beats_c4_broker
        else "stage847_c9_not_promoted_stop_retry_fullpath_failed"
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
        "rule_type": "frozen_intraday_stop_retry_once",
        "rule": {
            "base_arm": C4_ARM,
            "c2_preserved": True,
            "broker10_entry_cap_preserved": True,
            "stop_retry_r": STOP_RETRY_R,
            "max_retries": MAX_RETRIES,
            "reentry_price": "original_entry_price",
            "retry_failure_stop": "same_0.5R_stop_price",
            "same_bar_policy": "conservative_stop_first",
        },
        "event_summary": {
            "c2_events": int(len(c2_events)),
            "stop_retry_events": int(len(stop_retry_events)),
            "stop_retry_reentered": int(pd.to_numeric(stop_retry_events.get("retry_reentered", 0), errors="coerce").fillna(0).sum())
            if not stop_retry_events.empty
            else 0,
            "stop_retry_retry_failed": int(pd.to_numeric(stop_retry_events.get("retry_failed", 0), errors="coerce").fillna(0).sum())
            if not stop_retry_events.empty
            else 0,
            "cap_events": int(len(cap_events)),
            "cap_blocked": int(cap_events["reason"].astype(str).eq("broker10_margin_cap_block").sum()) if not cap_events.empty else 0,
            "cap_reduced_volume": float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0).sum())
            if not cap_events.empty
            else 0.0,
        },
        "comparison": comparison.to_dict("records"),
        "path_diagnostics": path_diag.to_dict("records"),
        "stop_retry_event_summary": event_summary.to_dict("records"),
        "decision": decision_label,
        "candidate_result": c9_row,
        "overfit_reflection": (
            "C9 uses exactly the Stage846 P2 rule shape fixed before this engine run: 0.5R first adverse stop, "
            "one reentry only at original entry reclaim, and a final 0.5R retry-failure stop. No year, product, "
            "direction, R multiple, OR length, confirmation window, or retry-count scan is performed."
        ),
        "continue_value": (
            "Continue to yearly/cost/pressure stress only if C9 improves C4 after full portfolio capital linkage; "
            "otherwise stop this stop-retry branch and return to broader mechanisms."
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
            "c2_events": str(C2_EVENTS_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "cap_events": str(CAP_EVENTS_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))
    print("stop_retry_event_summary")
    print(event_summary.to_string(index=False))


if __name__ == "__main__":
    main()
