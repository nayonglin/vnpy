from __future__ import annotations

from run_qmt_alignment_backtest import OPEN_BROWSER_CHART
from run_qmt_range_reversion_core4_directed_backtest import run_backtest


def main() -> None:
    engine, _, statistics = run_backtest(
        file_prefix="qmt_range_reversion_core4_directed_product_signal_v2",
        chart_title="QMT Range Reversion Core4 Directed Product Signal V2 Backtest",
        strategy_tag="range_reversion_core4_directed_product_signal_v2",
        setting_overrides={"range_use_product_continuous_signal": True},
    )
    print(statistics)

    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
