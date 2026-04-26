from __future__ import annotations

from run_qmt_alignment_backtest import OPEN_BROWSER_CHART
from run_qmt_range_reversion_backtest import run_backtest


def main() -> None:
    engine, _, statistics = run_backtest(
        file_prefix="qmt_range_reversion_v2_score",
        chart_title="QMT Range Reversion V2 Score Backtest",
        strategy_overrides={
            "range_entry_mode": "score",
            "range_score_threshold": 3.0,
            "range_soft_adx_max": 32.0,
            "range_soft_position_long_max": 0.35,
            "range_soft_position_short_min": 0.65,
            "range_soft_rsi_long_max": 45.0,
            "range_soft_rsi_short_min": 55.0,
        },
    )
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
