from __future__ import annotations

from pathlib import Path

from vnpy.trader.constant import Interval
from vnpy_portfoliostrategy import BacktestingEngine

from main_contract_mapping import build_contract_metadata
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, OUTPUT_DIR, save_backtest_artifacts


def main() -> None:
    metadata = build_contract_metadata()
    vt_symbols: list[str] = metadata["vt_symbols"]
    rates: dict[str, float] = metadata["rates"]
    slippages: dict[str, float] = metadata["slippages"]
    sizes: dict[str, int] = metadata["sizes"]
    priceticks: dict[str, float] = metadata["priceticks"]
    margin_ratios: dict[str, float] = metadata["margin_ratios"]

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=Interval.DAILY,
        start=START_DT,
        end=END_DT,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=1_000_000,
    )

    mapping_csv_path: Path = (OUTPUT_DIR / "tqsdk_main_contract_mapping_2020_2026_04.csv").resolve()

    setting: dict[str, object] = {
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
        "max_capital_usage_ratio": 0.9,
        "risk_ratio_of_total_assets": 0.01,
        "risk_ratio_breakout": 0.01,
        "risk_ratio_ma_cross_breakout": 0.01,
        "min_risk_per_trade": 1000.0,
        "max_risk_per_trade": 50_000_000.0,
        "margin_ratio_overrides": ",".join(f"{symbol}={ratio}" for symbol, ratio in margin_ratios.items()),
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
        "stop_loss_pct": 0.02,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 0.0,
        "add_position_min_profit": 0.001,
        "atr_2x_mid_stop_enabled": True,
        "exit_on_alignment_break": True,
        "enable_ma_trend_stop": True,
        "enable_add_position": True,
        "add_position_threshold": 0.01,
        "second_add_position_threshold": 0.01,
        "max_add_layers": 1,
        "regular_add_volume_multiplier": 0.5,
        "regular_add_use_day_extreme_stop": True,
        "restrict_regular_add_to_first": True,
        "require_reversal_for_add": True,
        "wick_chop_filter_enabled": False,
        "wick_chop_filter_lookback": 10,
        "wick_chop_filter_max_days": 4,
        "enable_donchian_add_position": True,
        "donchian_entry_period": 20,
        "donchian_add_period": 20,
        "donchian_add_max_layers": 2,
        "donchian_add_volume_multipliers": "2.0,1.0",
        "case2_requires_breakout": True,
        "tick_add": 1,
        "warmup_days": 90,
    }
    engine.add_strategy(QmtRollPortfolioStrategy, setting)

    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()

    statistics: dict = engine.calculate_statistics()
    print(statistics)
    save_backtest_artifacts(
        engine,
        statistics,
        file_prefix="qmt_roll",
        chart_title="QMT Roll Portfolio Backtest",
        mapping_csv_path=mapping_csv_path,
    )

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
