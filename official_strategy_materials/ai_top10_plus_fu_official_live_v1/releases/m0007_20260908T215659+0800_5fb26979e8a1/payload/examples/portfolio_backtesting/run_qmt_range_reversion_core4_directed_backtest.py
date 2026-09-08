from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qmt_range_reversion_directed_portfolio_strategy import QmtRangeReversionDirectedPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, save_backtest_artifacts
from run_qmt_roll_backtest import build_backtest_engine, build_roll_setting, compute_round_trip_win_ratio


PROJECT_DIR: Path = Path(__file__).resolve().parent
CORE_UNIVERSE_PATH: Path = PROJECT_DIR / "qmt_range_reversion_core4_directed_universe_v1.csv"


def build_core4_directed_setting(
    margin_ratios: dict[str, float],
    *,
    risk_ratio: float = 0.008,
    capital: float = 200_000,
    product_universe_path: str | Path = CORE_UNIVERSE_PATH,
) -> dict[str, object]:
    product_universe_path = Path(product_universe_path)
    setting: dict[str, object] = build_roll_setting(
        margin_ratios,
        risk_ratio=risk_ratio,
        strategy_overrides={
            "product_universe_csv_path": str(product_universe_path),
        },
    )
    setting.update(
        {
            "capital_base": capital,
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
            "range_entry_mode": "score",
            "range_signal_style": "reversion",
            "range_score_threshold": 4.0,
            "range_soft_adx_max": 32.0,
            "range_soft_position_long_max": 0.35,
            "range_soft_position_short_min": 0.65,
            "range_soft_rsi_long_max": 45.0,
            "range_soft_rsi_short_min": 55.0,
            "range_efficiency_filter_enabled": True,
            "range_efficiency_window": 20,
            "range_efficiency_max": 0.40,
            "range_intraday_stop_enabled": True,
            "range_intraday_stop_gap_open_enabled": True,
            "range_direction_hints_path": str(product_universe_path),
            "range_direction_hints_required": True,
            "range_reversion_rsi_band_filter_enabled": True,
            "range_soft_rsi_long_min": 25.0,
            "range_soft_rsi_short_max": 75.0,
            "max_concurrent_positions": 4,
            "max_single_trade_capital_usage_ratio": 0.45,
            "max_capital_usage_ratio": 0.80,
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
    file_prefix: str = "qmt_range_reversion_core4_directed_v1",
    chart_title: str = "QMT Range Reversion Core4 Directed V1 Backtest",
    strategy_tag: str = "range_reversion_core4_directed_v1",
    setting_overrides: dict[str, object] | None = None,
    product_universe_path: str | Path = CORE_UNIVERSE_PATH,
) -> tuple[Any, Any, dict[str, Any]]:
    preload_start = preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    product_universe_path = Path(product_universe_path)
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=capital,
        product_universe_csv_path=str(product_universe_path),
    )
    margin_ratios: dict[str, float] = metadata["margin_ratios"]
    setting = build_core4_directed_setting(
        margin_ratios,
        risk_ratio=risk_ratio,
        capital=capital,
        product_universe_path=product_universe_path,
    )
    if setting_overrides:
        setting.update(setting_overrides)
    engine.add_strategy(QmtRangeReversionDirectedPortfolioStrategy, setting)

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
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count
    statistics["strategy_tag"] = strategy_tag
    statistics["product_universe_csv_path"] = str(product_universe_path)
    statistics["risk_ratio"] = risk_ratio
    statistics["capital"] = capital
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
