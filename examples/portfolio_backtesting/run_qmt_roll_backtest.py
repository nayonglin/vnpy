from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy import BacktestingEngine
from vnpy_portfoliostrategy.backtesting import Status

from main_contract_mapping import build_contract_metadata, get_preferred_mapping_path, load_product_universe_symbols
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, save_backtest_artifacts

START_YEAR_WINDOWS: list[tuple[str, str, datetime, datetime]] = [
    ("since_2020", "20年开始", datetime(2020, 1, 1), END_DT),
    ("since_2021", "21年开始", datetime(2021, 1, 1), END_DT),
    ("since_2022", "22年开始", datetime(2022, 1, 1), END_DT),
    ("since_2023", "23年开始", datetime(2023, 1, 1), END_DT),
    ("since_2024", "24年开始", datetime(2024, 1, 1), END_DT),
    ("since_2025", "25年开始", datetime(2025, 1, 1), END_DT),
    ("since_2026", "26年开始", datetime(2026, 1, 1), END_DT),
]


class SameDayCloseBacktestingEngine(BacktestingEngine):
    """Portfolio backtesting engine that executes strategy orders on the same daily bar close."""

    def new_bars(self, dt) -> None:
        """Push daily bars, let strategy react, then match orders at the same bar close."""
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

        self.strategy.on_bars(bars)
        self.cross_limit_order_on_close()

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def cross_limit_order_on_close(self) -> None:
        """Match active limit orders at current bar close to model same-day close execution."""
        for order in list(self.active_limit_orders.values()):
            bar: BarData = self.bars[order.vt_symbol]
            close_price: float = float(bar.close_price)

            if close_price <= 0:
                continue

            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self.strategy.update_order(order)

            # Strategy orders are generated using the same bar close as the limit price.
            if order.price <= 0:
                continue

            trade_price: float = float(order.price)
            if trade_price <= 0:
                trade_price = close_price

            order.traded = order.volume
            order.status = Status.ALLTRADED
            self.strategy.update_order(order)

            if order.vt_orderid in self.active_limit_orders:
                self.active_limit_orders.pop(order.vt_orderid)

            self.trade_count += 1

            trade: TradeData = TradeData(
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


def build_backtest_engine(
    *,
    preload_start: datetime = PRELOAD_START_DT,
    capital: float = 500_000,
    product_universe_csv_path: str | None = None,
) -> tuple[BacktestingEngine, dict[str, Any]]:
    assert_stage196_database_sentinels()
    supported_symbols = load_product_universe_symbols(product_universe_csv_path)
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    vt_symbols: list[str] = metadata["vt_symbols"]
    rates: dict[str, float] = metadata["rates"]
    slippages: dict[str, float] = metadata["slippages"]
    sizes: dict[str, int] = metadata["sizes"]
    priceticks: dict[str, float] = metadata["priceticks"]
    engine = SameDayCloseBacktestingEngine()
    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=Interval.DAILY,
        start=preload_start,
        end=backtest_end,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=capital,
    )
    return engine, metadata


def build_roll_setting(
    margin_ratios: dict[str, float],
    risk_ratio: float = 0.045,
    risk_overrides: dict[str, float] | None = None,
    strategy_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    mapping_csv_path: Path = get_preferred_mapping_path().resolve()
    risk_overrides = risk_overrides or {}
    strategy_overrides = strategy_overrides or {}
    default_risk_ratio: float = float(risk_overrides.get("risk_ratio_of_total_assets", risk_ratio))
    breakout_risk_ratio: float = float(risk_overrides.get("risk_ratio_breakout", default_risk_ratio))
    ma_cross_risk_ratio: float = float(risk_overrides.get("risk_ratio_ma_cross_breakout", default_risk_ratio))
    volume_open_interest_surge_ratio: float = float(
        risk_overrides.get("risk_ratio_volume_open_interest_surge", 0.06)
    )
    open_interest_surge_ratio: float = float(risk_overrides.get("risk_ratio_open_interest_surge", 0.06))
    open_interest_decline_ratio: float = float(risk_overrides.get("risk_ratio_open_interest_decline", 0.025))

    setting: dict[str, object] = {
        "mapping_csv_path": str(mapping_csv_path),
        "ma_short": 5,
        "ma_mid": 10,
        "ma_long": 20,
        "ma_extra_long": 40,
        "rsi_length": 6,
        "enable_rsi_filter": False,
        "enable_rsi_partial_exit": True,
        "rsi_partial_exit_threshold": 95.0,
        "rsi_partial_exit_ratio": 0.5,
        "capital_base": 500_000,
        "fixed_size": 0,
        "min_position_size": 1,
        "max_position_size": 500,
        "max_concurrent_positions": 8,
        "long_entry_enabled": True,
        "short_entry_enabled": True,
        "rollover_reopen_enabled": True,
        "reverse_on_opposite_signal": False,
        "max_capital_usage_ratio": 0.9,
        "max_single_trade_capital_usage_ratio": 0.70,
        "risk_ratio_of_total_assets": default_risk_ratio,
        "risk_ratio_breakout": breakout_risk_ratio,
        "risk_ratio_ma_cross_breakout": ma_cross_risk_ratio,
        "risk_ratio_volume_open_interest_surge": volume_open_interest_surge_ratio,
        "risk_ratio_open_interest_surge": open_interest_surge_ratio,
        "risk_ratio_open_interest_decline": open_interest_decline_ratio,
        "min_risk_per_trade": 1000.0,
        "max_risk_per_trade": 50_000_000.0,
        "margin_ratio_overrides": ",".join(f"{symbol}={ratio}" for symbol, ratio in margin_ratios.items()),
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
        "stop_loss_pct": 0.02,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 0.0,
        "enable_prev2day_stop": True,
        "add_position_min_profit": 0.001,
        "atr_2x_mid_stop_enabled": True,
        "exit_on_alignment_break": False,
        "enable_ma_trend_stop": True,
        "enable_add_position": False,
        "add_position_threshold": 0.01,
        "second_add_position_threshold": 0.01,
        "max_add_layers": 1,
        "regular_add_volume_multiplier": 0.5,
        "regular_add_use_day_extreme_stop": True,
        "restrict_regular_add_to_first": True,
        "require_reversal_for_add": True,
        "ma5_extreme_filter_enabled": True,
        "ma5_extreme_compare_days": 3,
        "ma5_angle_reversal_filter_enabled": False,
        "ma5_angle_reversal_lookback_days": 10,
        "ma5_angle_reversal_angle_threshold_deg": 45.0,
        "short_ma5_slope_filter_enabled": True,
        "wick_chop_filter_enabled": True,
        "wick_chop_filter_lookback": 10,
        "wick_chop_filter_max_days": 5,
        "enable_donchian_add_position": False,
        "donchian_entry_period": 20,
        "donchian_add_period": 20,
        "donchian_add_max_layers": 1,
        "donchian_add_volume_multipliers": "1.0",
        "case2_requires_breakout": False,
        "tick_add": 1,
        "warmup_days": 90,
    }
    setting.update(strategy_overrides)
    return setting


def build_summary_row(
    statistics: dict[str, Any],
    *,
    analysis_start: datetime,
    analysis_end: datetime,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "end_balance": float(statistics.get("end_balance", 0) or 0),
        "total_return_pct": float(statistics.get("total_return", 0) or 0),
        "annual_return_pct": float(statistics.get("annual_return", 0) or 0),
        "max_drawdown": float(statistics.get("max_drawdown", 0) or 0),
        "max_dd_percent": float(statistics.get("max_ddpercent", 0) or 0),
        "max_drawdown_duration": int(statistics.get("max_drawdown_duration", 0) or 0),
        "sharpe_ratio": float(statistics.get("sharpe_ratio", 0) or 0),
        "return_drawdown_ratio": float(statistics.get("return_drawdown_ratio", 0) or 0),
        "total_trade_count": int(statistics.get("total_trade_count", 0) or 0),
        "win_ratio_pct": float(statistics.get("win_ratio", 0) or 0),
        "daily_trade_count": float(statistics.get("daily_trade_count", 0) or 0),
    }
    row.update(extra)
    return row


def compute_round_trip_win_ratio(engine: BacktestingEngine) -> tuple[float, int, int]:
    """Compute round-trip win ratio using FIFO pairing across long/short positions."""
    trades: list[TradeData] = sorted(
        engine.get_all_trades(),
        key=lambda trade: (pd.Timestamp(trade.datetime), trade.vt_tradeid),
    )
    if not trades:
        return 0.0, 0, 0

    size_map: dict[str, int] = getattr(engine, "sizes", {})
    open_queues: dict[tuple[str, str], deque[dict[str, float]]] = {}
    realized_pnls: list[float] = []

    for trade in trades:
        price: float = float(trade.price)
        volume: float = float(trade.volume)
        vt_symbol: str = trade.vt_symbol
        contract_size: float = float(size_map.get(vt_symbol, 1))

        if trade.offset.value == "Open":
            position_direction: str = "long" if trade.direction.value == "Long" else "short"
            queue_key = (vt_symbol, position_direction)
            open_queues.setdefault(queue_key, deque()).append({"price": price, "volume": volume})
            continue

        position_direction = "long" if trade.direction.value == "Short" else "short"
        queue_key = (vt_symbol, position_direction)
        queue = open_queues.setdefault(queue_key, deque())
        remaining: float = volume

        while remaining > 1e-9 and queue:
            entry = queue[0]
            matched_volume: float = min(remaining, float(entry["volume"]))
            entry_price: float = float(entry["price"])
            pnl: float
            if position_direction == "long":
                pnl = (price - entry_price) * matched_volume * contract_size
            else:
                pnl = (entry_price - price) * matched_volume * contract_size
            realized_pnls.append(pnl)

            entry["volume"] = float(entry["volume"]) - matched_volume
            remaining -= matched_volume
            if float(entry["volume"]) <= 1e-9:
                queue.popleft()

    if not realized_pnls:
        return 0.0, 0, 0

    win_count: int = sum(1 for pnl in realized_pnls if pnl > 0)
    round_trip_count: int = len(realized_pnls)
    win_ratio_pct: float = win_count / round_trip_count * 100.0
    return win_ratio_pct, win_count, round_trip_count


def run_start_year_sweep(
    *,
    risk_ratio: float,
    risk_overrides: dict[str, float] | None,
    strategy_overrides: dict[str, object] | None,
    capital: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
        print(f"[start-year] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, analysis_df, statistics = run_backtest(
            risk_ratio=risk_ratio,
            risk_overrides=risk_overrides,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=capital,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"qmt_roll_{window_name}",
            chart_title=f"QMT Roll {window_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                window_name=window_name,
                display_label=display_label,
                capital=capital,
            )
        )

        if analysis_df is not None and not analysis_df.empty:
            curve_df = analysis_df[["balance"]].reset_index().rename(columns={"index": "date"}).copy()
            curve_df["date"] = pd.to_datetime(curve_df["date"])
            first_balance: float = float(curve_df["balance"].iloc[0] or capital or 1.0)
            if abs(first_balance) < 1e-9:
                first_balance = float(capital or 1.0)
            curve_df["normalized_nav"] = curve_df["balance"] / first_balance
            curve_df["window_name"] = window_name
            curve_df["display_label"] = display_label
            curve_df["analysis_start"] = analysis_start.date().isoformat()
            curve_df["analysis_end"] = analysis_end.date().isoformat()
            curve_frames.append(curve_df)

    summary_df = pd.DataFrame(rows).sort_values(["analysis_start", "analysis_end"]).reset_index(drop=True)
    if curve_frames:
        curves_df = pd.concat(curve_frames, ignore_index=True)
        curves_df.sort_values(["analysis_start", "date"], inplace=True)
        curves_df.reset_index(drop=True, inplace=True)
    else:
        curves_df = pd.DataFrame(
            columns=[
                "date",
                "balance",
                "normalized_nav",
                "window_name",
                "display_label",
                "analysis_start",
                "analysis_end",
            ]
        )
    return summary_df, curves_df


def run_backtest(
    risk_ratio: float = 0.045,
    *,
    risk_overrides: dict[str, float] | None = None,
    strategy_overrides: dict[str, object] | None = None,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
    preload_start: datetime | None = None,
    capital: float = 500_000,
    save_artifacts: bool = True,
    include_start_year_sweep: bool | None = None,
    file_prefix: str = "qmt_roll",
    chart_title: str = "QMT Roll Portfolio Backtest",
) -> tuple[BacktestingEngine, Any, dict[str, Any]]:
    preload_start = preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=capital,
        product_universe_csv_path=str((strategy_overrides or {}).get("product_universe_csv_path", "") or ""),
    )
    margin_ratios: dict[str, float] = metadata["margin_ratios"]
    setting: dict[str, object] = build_roll_setting(
        margin_ratios,
        risk_ratio=risk_ratio,
        risk_overrides=risk_overrides,
        strategy_overrides=strategy_overrides,
    )
    setting["capital_base"] = capital
    engine.add_strategy(QmtRollPortfolioStrategy, setting)

    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is not None:
        analysis_df = daily_df.copy()
        analysis_df = analysis_df.loc[
            (analysis_df.index >= analysis_start.date())
            & (analysis_df.index <= analysis_end.date())
        ]
    else:
        analysis_df = None

    statistics: dict = engine.calculate_statistics(analysis_df)
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count
    engine.daily_df = analysis_df
    if include_start_year_sweep is None:
        include_start_year_sweep = save_artifacts

    period_sweep_summary_df: pd.DataFrame | None = None
    period_equity_curves_df: pd.DataFrame | None = None
    if include_start_year_sweep:
        period_sweep_summary_df, period_equity_curves_df = run_start_year_sweep(
            risk_ratio=risk_ratio,
            risk_overrides=risk_overrides,
            strategy_overrides=strategy_overrides,
            capital=capital,
        )
    if save_artifacts:
        mapping_csv_path = Path(str(setting["mapping_csv_path"])).resolve()
        save_backtest_artifacts(
            engine,
            statistics,
            file_prefix=file_prefix,
            chart_title=chart_title,
            mapping_csv_path=mapping_csv_path,
            analysis_start=analysis_start,
            period_sweep_summary_df=period_sweep_summary_df,
            period_equity_curves_df=period_equity_curves_df,
        )
    return engine, analysis_df, statistics


def main() -> None:
    engine, _, statistics = run_backtest()
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
