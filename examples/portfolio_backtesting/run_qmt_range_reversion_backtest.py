from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qmt_range_reversion_portfolio_strategy import QmtRangeReversionPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, save_backtest_artifacts
from run_qmt_roll_backtest import build_backtest_engine, build_roll_setting


def build_range_reversion_setting(margin_ratios: dict[str, float], risk_ratio: float = 0.008) -> dict[str, object]:
    setting: dict[str, object] = build_roll_setting(margin_ratios, risk_ratio=risk_ratio)
    setting.update(
        {
            "long_entry_enabled": True,
            "short_entry_enabled": True,
            "rollover_reopen_enabled": True,
            "reverse_on_opposite_signal": False,
            "enable_prev2day_stop": False,
            "enable_rsi_partial_exit": False,
            "trailing_stop_enabled": False,
            "trailing_stop_pct": 0.0,
            "atr_2x_mid_stop_enabled": False,
            "exit_on_alignment_break": False,
            "enable_ma_trend_stop": False,
            "enable_add_position": False,
            "ma5_extreme_filter_enabled": False,
            "ma5_angle_reversal_filter_enabled": False,
            "short_ma5_slope_filter_enabled": False,
            "wick_chop_filter_enabled": False,
            "enable_donchian_add_position": False,
            "risk_ratio_of_total_assets": risk_ratio,
            "streak_risk_multipliers": "1.0,0.75,0.5,0.0",
            "entry_tr_multiplier": 0.8,
            "previous_day_stop_enabled": True,
            "exit_on_channel_middle_touch": True,
            "max_holding_days": 5,
            "channel_window": 20,
            "adx_filter_enabled": True,
            "adx_window": 14,
            "adx_max": 25.0,
            "range_position_long_max": 0.25,
            "range_position_short_min": 0.75,
            "range_rsi_long_max": 35.0,
            "range_rsi_short_min": 65.0,
            "block_short_when_all_ma_rising": True,
            "block_long_when_all_ma_falling": True,
        }
    )
    return setting


def run_backtest(
    risk_ratio: float = 0.008,
    *,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
    preload_start: datetime | None = None,
    capital: float = 200_000,
    save_artifacts: bool = True,
    file_prefix: str = "qmt_range_reversion_v1_oscillator_adx",
    chart_title: str = "QMT Range Reversion V1 Oscillator ADX Backtest",
    strategy_overrides: dict[str, object] | None = None,
) -> tuple[Any, Any, dict[str, Any]]:
    preload_start = preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=capital,
    )
    margin_ratios: dict[str, float] = metadata["margin_ratios"]
    setting: dict[str, object] = build_range_reversion_setting(margin_ratios, risk_ratio=risk_ratio)
    if strategy_overrides:
        setting.update(strategy_overrides)
    setting["capital_base"] = capital
    engine.add_strategy(QmtRangeReversionPortfolioStrategy, setting)

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

    statistics: dict[str, Any] = engine.calculate_statistics(analysis_df)
    engine.daily_df = analysis_df
    if save_artifacts:
        mapping_csv_path = Path(str(setting["mapping_csv_path"])).resolve()
        save_backtest_artifacts(
            engine,
            statistics,
            file_prefix=file_prefix,
            chart_title=chart_title,
            mapping_csv_path=mapping_csv_path,
            analysis_start=analysis_start,
        )
    return engine, analysis_df, statistics


def main() -> None:
    engine, _, statistics = run_backtest()
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
