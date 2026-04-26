from __future__ import annotations

from run_qmt_alignment_backtest import OPEN_BROWSER_CHART
from run_qmt_range_reversion_core4_directed_backtest import run_backtest


def main() -> None:
    engine, _, statistics = run_backtest(
        file_prefix="qmt_range_reversion_core4_directed_product_signal_no_prevday_stop_v5",
        chart_title="QMT Range Reversion Core4 Directed Product Signal No Prevday Stop V5 Backtest",
        strategy_tag="range_reversion_core4_directed_product_signal_no_prevday_stop_v5",
        setting_overrides={
            "range_use_product_continuous_signal": True,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "previous_day_stop_enabled": False,
        },
    )
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
