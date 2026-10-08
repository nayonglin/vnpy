from __future__ import annotations

from collections import Counter
from copy import copy
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage450_minute_execution_equity_rebuild as s450  # noqa: E402
import analyze_qmt_roll_stage451_true_path_1455_vwap_replay as s451  # noqa: E402
import analyze_qmt_roll_stage452_iterative_1455_proxy_backfill as s452  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_roll_backtest import SameDayCloseBacktestingEngine, build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage501_asymmetric_entry_exit_execution_v1"
OUTPUT_PREFIX = "qmt_roll_stage501_asymmetric_entry_exit_execution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
RERUN_VARIANT = "stage079_rerun_same_day_close"
ASYMM_VARIANT = "stage079_entry_next_real_open_exit_same_1455_vwap"

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

NIGHT_SESSION_PRODUCTS = {
    "au.SHFE",
    "cu.SHFE",
    "rb.SHFE",
    "hc.SHFE",
    "fu.SHFE",
    "ru.SHFE",
    "sp.SHFE",
    "MA.CZCE",
    "OI.CZCE",
    "CF.CZCE",
    "FG.CZCE",
    "SA.CZCE",
    "SM.CZCE",
    "jm.DCE",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _naive_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _direction_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _offset_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def _is_open_order(order: Any) -> bool:
    return _offset_text(order.offset) == "Open"


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return f"{letters or symbol}.{exchange}"


def _has_night_session(vt_symbol: str) -> bool:
    return _product_from_contract(vt_symbol) in NIGHT_SESSION_PRODUCTS


def _window_price(
    vt_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    mode: str,
) -> dict[str, Any] | None:
    bars = s452._load_raw_bars(vt_symbol)
    if bars.empty:
        return None
    window = bars[(bars["bar_datetime"] >= start) & (bars["bar_datetime"] < end)].copy()
    if window.empty:
        return None
    for column in ["open", "close", "volume"]:
        window[column] = pd.to_numeric(window[column], errors="coerce")
    window = window.dropna(subset=["open", "close"]).sort_values("bar_datetime")
    if window.empty:
        return None
    if mode == "first_open":
        price = float(window["open"].iloc[0])
    elif mode == "vwap_close":
        volume = window["volume"].fillna(0.0)
        volume_sum = float(volume.sum())
        price = float((window["close"] * volume).sum() / volume_sum) if volume_sum > 0 else float(window["close"].mean())
    else:
        raise ValueError(mode)
    if not np.isfinite(price) or price <= 0:
        return None
    return {
        "proxy_price": price,
        "proxy_bar_count": int(len(window)),
        "proxy_first_time": window["bar_datetime"].iloc[0],
        "proxy_last_time": window["bar_datetime"].iloc[-1],
    }


def _same_day_close_proxy_from_raw(vt_symbol: str, signal_date: pd.Timestamp) -> dict[str, Any] | None:
    start = pd.Timestamp(signal_date).normalize() + pd.Timedelta(hours=14, minutes=55)
    end = pd.Timestamp(signal_date).normalize() + pd.Timedelta(hours=15)
    proxy = _window_price(vt_symbol, start, end, mode="vwap_close")
    if proxy is not None:
        proxy["price_source"] = "raw_same_day_1455_1500_vwap"
    return proxy


def _next_real_open_proxy_from_raw(
    vt_symbol: str,
    signal_date: pd.Timestamp,
    fill_date: pd.Timestamp,
) -> dict[str, Any] | None:
    signal_date = pd.Timestamp(signal_date).normalize()
    fill_date = pd.Timestamp(fill_date).normalize()
    if _has_night_session(vt_symbol):
        night_start = signal_date + pd.Timedelta(hours=21)
        night_end = signal_date + pd.Timedelta(hours=21, minutes=5)
        proxy = _window_price(vt_symbol, night_start, night_end, mode="first_open")
        if proxy is not None:
            proxy["price_source"] = "raw_night_2100_2105_first_open"
            return proxy

    day_start = fill_date + pd.Timedelta(hours=9)
    day_end = fill_date + pd.Timedelta(hours=9, minutes=5)
    proxy = _window_price(vt_symbol, day_start, day_end, mode="first_open")
    if proxy is not None:
        proxy["price_source"] = "raw_day_0900_0905_first_open"
    return proxy


def _seed_proxy_maps() -> tuple[dict[tuple[pd.Timestamp, str], dict[str, Any]], dict[tuple[pd.Timestamp, pd.Timestamp, str], dict[str, Any]]]:
    detail = pd.read_csv(s451.STAGE149_DETAIL_PATH, encoding="utf-8-sig")
    for column in ["date", "next_trade_date"]:
        detail[column] = pd.to_datetime(detail[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ["same_last5_vwap", "preferred_real_open_proxy"]:
        detail[column] = pd.to_numeric(detail.get(column, np.nan), errors="coerce")
    close_map: dict[tuple[pd.Timestamp, str], dict[str, Any]] = {}
    open_map: dict[tuple[pd.Timestamp, pd.Timestamp, str], dict[str, Any]] = {}
    for row in detail.dropna(subset=["date", "vt_symbol"]).sort_values(["date", "vt_symbol", "trade_id"]).itertuples(index=False):
        signal_date = pd.Timestamp(row.date).normalize()
        vt_symbol = str(row.vt_symbol)
        close_price = _safe_float(row.same_last5_vwap, np.nan)
        if pd.notna(close_price) and close_price > 0.0:
            close_map.setdefault(
                (signal_date, vt_symbol),
                {
                    "proxy_price": float(close_price),
                    "price_source": "stage149_same_last5_vwap_symbol_date",
                    "proxy_bar_count": np.nan,
                    "proxy_first_time": "",
                    "proxy_last_time": "",
                },
            )
        fill_date = pd.Timestamp(row.next_trade_date).normalize() if pd.notna(row.next_trade_date) else pd.NaT
        open_price = _safe_float(row.preferred_real_open_proxy, np.nan)
        if pd.notna(fill_date) and pd.notna(open_price) and open_price > 0.0:
            open_map.setdefault(
                (signal_date, fill_date, vt_symbol),
                {
                    "proxy_price": float(open_price),
                    "price_source": f"stage149_{getattr(row, 'preferred_real_open_proxy_type', 'preferred_real_open')}",
                    "proxy_bar_count": np.nan,
                    "proxy_first_time": "",
                    "proxy_last_time": "",
                },
            )
    return close_map, open_map


class AsymmetricEntryExitExecutionEngine(SameDayCloseBacktestingEngine):
    """Delay only opening orders; fill closing orders on the same-day 14:55 window proxy."""

    def __init__(
        self,
        close_proxy_map: dict[tuple[pd.Timestamp, str], dict[str, Any]],
        open_proxy_map: dict[tuple[pd.Timestamp, pd.Timestamp, str], dict[str, Any]],
    ) -> None:
        super().__init__()
        self.close_proxy_map = close_proxy_map
        self.open_proxy_map = open_proxy_map
        self.trade_usage_rows: list[dict[str, Any]] = []
        self.source_counter: Counter[str] = Counter()

    def new_bars(self, dt) -> None:
        self.datetime = dt

        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            bar: BarData | None = self.history_data.get((dt, vt_symbol), None)
            if bar:
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar
            elif vt_symbol in self.bars:
                old_bar: BarData = self.bars[vt_symbol]
                bar = BarData(
                    symbol=old_bar.symbol,
                    exchange=old_bar.exchange,
                    datetime=dt,
                    open_price=old_bar.close_price,
                    high_price=old_bar.close_price,
                    low_price=old_bar.close_price,
                    close_price=old_bar.close_price,
                    gateway_name=old_bar.gateway_name,
                )
                self.bars[vt_symbol] = bar

        self.cross_delayed_open_orders()
        self.strategy.on_bars(bars)
        self.cross_same_day_close_orders()

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def _resolve_open_price(self, order: Any, bar: BarData) -> tuple[float, str, dict[str, Any]]:
        vt_symbol = str(order.vt_symbol)
        signal_date = _naive_date(order.datetime)
        fill_date = _naive_date(self.datetime)
        proxy = self.open_proxy_map.get((signal_date, fill_date, vt_symbol))
        if proxy is None:
            proxy = _next_real_open_proxy_from_raw(vt_symbol, signal_date, fill_date)
        if proxy is not None and _safe_float(proxy.get("proxy_price"), 0.0) > 0:
            return float(proxy["proxy_price"]), str(proxy["price_source"]), proxy
        fallback = float(bar.open_price or 0.0) or float(order.price)
        return fallback, "fallback_daily_next_open", {}

    def _resolve_close_price(self, order: Any) -> tuple[float, str, dict[str, Any]]:
        vt_symbol = str(order.vt_symbol)
        signal_date = _naive_date(self.datetime)
        proxy = self.close_proxy_map.get((signal_date, vt_symbol))
        if proxy is None:
            proxy = _same_day_close_proxy_from_raw(vt_symbol, signal_date)
        if proxy is not None and _safe_float(proxy.get("proxy_price"), 0.0) > 0:
            return float(proxy["proxy_price"]), str(proxy["price_source"]), proxy
        return float(order.price), "fallback_order_price_same_day_close", {}

    def _fill_order(self, order: Any, trade_price: float, price_source: str, proxy: dict[str, Any], execution_leg: str) -> None:
        if trade_price <= 0:
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
                "signal_date": _naive_date(order.datetime),
                "fill_date": _naive_date(self.datetime),
                "vt_symbol": str(order.vt_symbol),
                "direction": _direction_text(order.direction),
                "offset": _offset_text(order.offset),
                "execution_leg": execution_leg,
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

    def cross_delayed_open_orders(self) -> None:
        for order in list(self.active_limit_orders.values()):
            if not _is_open_order(order):
                continue
            bar: BarData | None = self.bars.get(order.vt_symbol)
            if bar is None or float(order.price) <= 0:
                continue
            trade_price, price_source, proxy = self._resolve_open_price(order, bar)
            self._fill_order(order, trade_price, price_source, proxy, "entry_next_real_open")

    def cross_same_day_close_orders(self) -> None:
        for order in list(self.active_limit_orders.values()):
            if _is_open_order(order):
                continue
            bar: BarData | None = self.bars.get(order.vt_symbol)
            if bar is None or float(order.price) <= 0:
                continue
            trade_price, price_source, proxy = self._resolve_close_price(order)
            self._fill_order(order, trade_price, price_source, proxy, "exit_same_day_1455_vwap")


def _load_stage079_baseline() -> pd.DataFrame:
    frame = pd.read_csv(s450.STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["window_name"].eq("start_2020") & frame["variant"].eq(BASELINE_VARIANT)].copy()
    for column in ["equity", "c3_net_pnl", "c3_slippage", "c3_trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _make_engine(asymmetric: bool) -> SameDayCloseBacktestingEngine:
    if not asymmetric:
        return SameDayCloseBacktestingEngine()
    close_map, open_map = _seed_proxy_maps()
    return AsymmetricEntryExitExecutionEngine(close_map, open_map)


def _run_c3_engine(*, asymmetric: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    engine = _make_engine(asymmetric)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(metadata["margin_ratios"], risk_ratio=BASE_RISK_RATIO, strategy_overrides=overrides)
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError("C3 engine produced empty daily result")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    source_counts = pd.DataFrame(
        [{"price_source": key, "trade_count": int(value)} for key, value in getattr(engine, "source_counter", Counter()).items()]
    )
    return daily, usage, source_counts


def _build_long_daily(baseline: pd.DataFrame, rerun_daily: pd.DataFrame, asymmetric_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base = baseline[["date", "equity", "c3_slippage", "c3_trade_count", "c3_net_pnl"]].copy()
    base.rename(
        columns={
            "equity": "account_equity",
            "c3_slippage": "slippage",
            "c3_trade_count": "trade_count",
            "c3_net_pnl": "net_pnl",
        },
        inplace=True,
    )
    base["variant"] = BASELINE_VARIANT
    base["label"] = "Stage079 baseline from Stage403"
    rows.append(base)

    rerun = rerun_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    rerun["variant"] = RERUN_VARIANT
    rerun["label"] = "Stage079 same-day close rerun"
    rows.append(rerun)

    asym = asymmetric_daily[["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
    asym["variant"] = ASYMM_VARIANT
    asym["label"] = "Stage079 open T+1 real window, close same-day 14:55 VWAP"
    rows.append(asym)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _plot(long_daily: pd.DataFrame) -> None:
    colors = {
        BASELINE_VARIANT: "#4c78a8",
        RERUN_VARIANT: "#72b7b2",
        ASYMM_VARIANT: "#e45756",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in long_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        x = pd.to_datetime(frame["date"])
        nav = frame["account_equity"].astype(float) / ACCOUNT_CAPITAL
        axes[0].plot(x, nav, label=label, color=colors.get(variant), linewidth=1.2)
        axes[1].plot(x, (nav / nav.cummax() - 1.0) * 100.0, label=label, color=colors.get(variant), linewidth=1.0)
    axes[0].set_title("Stage079 asymmetric execution replay")
    axes[0].set_ylabel("NAV")
    axes[0].legend(fontsize=8)
    axes[1].set_title("Underwater drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    usage: pd.DataFrame,
    source_counts: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "annual_cold_start_dd30_pass_rate",
        "quarter_cold_start_dd30_pass_rate",
    ]
    horizon_cols = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    gate_cols = [
        "variant",
        "hard_constraint_pass",
        "score_90d",
        "score_180d",
        "short_holding_score",
        "improved_count_90d",
        "improved_count_180d",
        "promotion_gate_pass",
        "failed_hard_constraints",
    ]
    usage_view = usage.copy()
    if not usage_view.empty:
        usage_view = usage_view.reindex(usage_view["price_delta"].abs().sort_values(ascending=False).index).head(30)
    report = [
        "# Stage201 非对称执行回放审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行语义实验；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 口径：开仓订单延迟到下一真实可交易窗口；平仓/减仓订单仍在当日 `14:55-15:00` VWAP 代理成交。",
        "- 重要边界：若平仓信号仍依赖完整日K收盘价，则该口径不是完整实盘语义，只能作为“退出不隔夜延迟”的上界审计；后续需验证平仓信号能否在14:55前冻结。",
        "",
        "## 外部调研判断",
        "",
        "- QuantConnect/Backtrader 类事件驱动回测通常要求已完成bar信号在下一可用bar成交，以避免 look-ahead。",
        "- 同bar close 成交属于 cheat-on-close 类语义；可以作为敏感性审计，但不能默认等同实盘。",
        "- 因此本阶段只把它标为非对称执行口径，不直接升级为部署候选。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 非对称成交数：`{decision['asymmetric_trade_count']}`。",
        f"- 开仓下一真实窗口成交数：`{decision['entry_next_real_open_trade_count']}`。",
        f"- 平仓当日14:55成交数：`{decision['exit_same_day_trade_count']}`。",
        f"- fallback成交数：`{decision['fallback_trade_count']}`。",
        f"- 原始重跑与Stage403期末权益差：`{decision['rerun_vs_stage403_end_equity_delta']:.2f}`。",
        "",
        "## 全周期指标",
        "",
        _md_table(summary[summary_cols]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[horizon_cols].sort_values(["variant", "horizon_days"])),
        "",
        "## 分数与门禁",
        "",
        _md_table(gate[gate_cols]),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]
        ),
        "",
        "## 成交价格来源",
        "",
        _md_table(source_counts.sort_values("trade_count", ascending=False) if not source_counts.empty else source_counts),
        "",
        "## 最大成交价替换样本",
        "",
        _md_table(
            usage_view[
                [
                    "signal_date",
                    "fill_date",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "execution_leg",
                    "order_price",
                    "trade_price",
                    "price_delta",
                    "order_volume",
                    "price_source",
                ]
            ]
            if not usage_view.empty
            else usage_view,
            max_rows=30,
        ),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只改变事先定义的撮合时点，不按结果筛日期、品种或参数。",
        "- 运行后过拟合反思：以门禁结果为准；若表现好，也必须降权看待，因为当日平仓可能仍使用完整收盘信息。",
        "- 运行前继续价值反思：是。它能区分开仓延迟与退出延迟哪个才是 T+1 全延迟失败的主要原因。",
        "- 运行后继续价值反思：若硬失败，停止该执行语义；若硬通过，再做平仓信号前置可行性验证。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    baseline = _load_stage079_baseline()
    rerun_daily, _, _ = _run_c3_engine(asymmetric=False)
    asym_daily, usage, source_counts = _run_c3_engine(asymmetric=True)
    long_daily = _build_long_daily(baseline, rerun_daily, asym_daily)
    summary, horizon, score, cost, gate = s451._evaluate(long_daily)
    _plot(long_daily)

    stage403_end = float(summary[summary["variant"].eq(BASELINE_VARIANT)]["end_equity"].iloc[0])
    rerun_end = float(summary[summary["variant"].eq(RERUN_VARIANT)]["end_equity"].iloc[0])
    asym_gate = gate[gate["variant"].eq(ASYMM_VARIANT)].iloc[0]
    fallback_count = int(usage["price_source"].astype(str).str.startswith("fallback").sum()) if not usage.empty else 0
    entry_count = int(usage["execution_leg"].eq("entry_next_real_open").sum()) if not usage.empty else 0
    exit_count = int(usage["execution_leg"].eq("exit_same_day_1455_vwap").sum()) if not usage.empty else 0
    decision_label = (
        "asymmetric_execution_semantic_hard_pass_need_exit_signal_freeze_audit"
        if int(asym_gate["hard_constraint_pass"]) == 1
        else "asymmetric_execution_semantic_hard_fail_reject"
    )
    decision = {
        "stage": "Stage201",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "asymmetric_trade_count": int(len(usage)),
        "entry_next_real_open_trade_count": entry_count,
        "exit_same_day_trade_count": exit_count,
        "fallback_trade_count": fallback_count,
        "rerun_vs_stage403_end_equity_delta": rerun_end - stage403_end,
        "hard_constraint_pass_variants": gate[gate["hard_constraint_pass"].eq(1)]["variant"].tolist(),
        "promotion_gate_pass_variants": gate[gate["promotion_gate_pass"].eq(1)]["variant"].tolist(),
        "asymmetric_failed_hard_constraints": str(asym_gate.get("failed_hard_constraints", "")),
        "asymmetric_score_90d": _safe_float(asym_gate.get("score_90d")),
        "asymmetric_score_180d": _safe_float(asym_gate.get("score_180d")),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "score": str(SCORE_PATH),
            "cost": str(COST_PATH),
            "gate": str(GATE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若硬通过，验证平仓信号能否在14:55前冻结；若硬失败，说明只延迟开仓、当天退出仍不足以修复真实执行问题。",
    }

    long_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, gate, usage, source_counts, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
