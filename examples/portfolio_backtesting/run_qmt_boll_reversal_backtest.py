from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qmt_boll_reversal_portfolio_strategy import QmtBollReversalPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, save_backtest_artifacts
from run_qmt_roll_backtest import build_backtest_engine, build_roll_setting


def build_boll_reversal_setting(margin_ratios: dict[str, float], risk_ratio: float = 0.04) -> dict[str, object]:
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
            "boll_window": 20,
            "boll_dev": 2.0,
            "entry_tr_multiplier": 0.5,
            "previous_day_stop_enabled": True,
        }
    )
    return setting


def run_backtest(
    risk_ratio: float = 0.04,
    *,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
    preload_start: datetime | None = None,
    capital: float = 200_000,
    save_artifacts: bool = True,
    file_prefix: str = "qmt_boll_reversal",
    chart_title: str = "QMT Boll Reversal Backtest",
) -> tuple[Any, Any, dict[str, Any]]:
    preload_start = preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=capital,
    )
    margin_ratios: dict[str, float] = metadata["margin_ratios"]
    setting: dict[str, object] = build_boll_reversal_setting(margin_ratios, risk_ratio=risk_ratio)
    setting["capital_base"] = capital
    engine.add_strategy(QmtBollReversalPortfolioStrategy, setting)

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
