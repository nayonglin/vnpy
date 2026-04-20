from __future__ import annotations

from pathlib import Path
from typing import Any

from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy import BacktestingEngine
from vnpy_portfoliostrategy.backtesting import Status

from main_contract_mapping import build_contract_metadata
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, OUTPUT_DIR, save_backtest_artifacts


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
                price=close_price,
                volume=order.volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )

            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade


def build_backtest_engine() -> tuple[BacktestingEngine, dict[str, Any]]:
    metadata = build_contract_metadata()
    vt_symbols: list[str] = metadata["vt_symbols"]
    rates: dict[str, float] = metadata["rates"]
    slippages: dict[str, float] = metadata["slippages"]
    sizes: dict[str, int] = metadata["sizes"]
    priceticks: dict[str, float] = metadata["priceticks"]
    margin_ratios: dict[str, float] = metadata["margin_ratios"]

    engine = SameDayCloseBacktestingEngine()
    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=Interval.DAILY,
        start=PRELOAD_START_DT,
        end=END_DT,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=1_000_000,
    )
    return engine, metadata


def build_roll_setting(margin_ratios: dict[str, float], risk_ratio: float = 0.04) -> dict[str, object]:
    mapping_csv_path: Path = (OUTPUT_DIR / "tqsdk_main_contract_mapping_2020_2026_04.csv").resolve()
    return {
        "mapping_csv_path": str(mapping_csv_path),
        "ma_short": 5,
        "ma_mid": 10,
        "ma_long": 20,
        "ma_extra_long": 40,
        "rsi_length": 6,
        "enable_rsi_filter": False,
        "capital_base": 1_000_000,
        "fixed_size": 0,
        "min_position_size": 1,
        "max_position_size": 500,
        "max_concurrent_positions": 4,
        "long_entry_enabled": True,
        "short_entry_enabled": False,
        "rollover_reopen_enabled": True,
        "reverse_on_opposite_signal": False,
        "max_capital_usage_ratio": 0.9,
        "risk_ratio_of_total_assets": risk_ratio,
        "risk_ratio_breakout": risk_ratio,
        "risk_ratio_ma_cross_breakout": risk_ratio,
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


def run_backtest(
    risk_ratio: float = 0.04,
    *,
    save_artifacts: bool = True,
    file_prefix: str = "qmt_roll",
    chart_title: str = "QMT Roll Portfolio Backtest",
) -> tuple[BacktestingEngine, Any, dict[str, Any]]:
    engine, metadata = build_backtest_engine()
    margin_ratios: dict[str, float] = metadata["margin_ratios"]
    setting: dict[str, object] = build_roll_setting(margin_ratios, risk_ratio=risk_ratio)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)

    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is not None:
        analysis_df = daily_df.copy()
        analysis_df = analysis_df.loc[analysis_df.index >= START_DT.date()]
    else:
        analysis_df = None

    statistics: dict = engine.calculate_statistics(analysis_df)
    engine.daily_df = analysis_df
    if save_artifacts:
        mapping_csv_path = Path(str(setting["mapping_csv_path"])).resolve()
        save_backtest_artifacts(
            engine,
            statistics,
            file_prefix=file_prefix,
            chart_title=chart_title,
            mapping_csv_path=mapping_csv_path,
            analysis_start=START_DT,
        )
    return engine, analysis_df, statistics


def main() -> None:
    engine, _, statistics = run_backtest()
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
