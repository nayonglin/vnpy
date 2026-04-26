from __future__ import annotations

from run_qmt_boll_reversal_backtest import run_backtest


def main() -> None:
    _, _, statistics = run_backtest(
        file_prefix="qmt_boll_reversal_refactor_v2_range_filter",
        chart_title="QMT Boll Reversal Refactor V2 Range Filter Backtest",
        strategy_overrides={
            "boll_entry_mode": "reentry_confirmed",
            "exit_on_boll_middle_touch": True,
            "max_holding_days": 5,
            "block_short_when_all_ma_rising": True,
            "block_long_when_all_ma_falling": True,
            "range_filter_enabled": True,
            "range_filter_lookback": 120,
            "range_filter_min_observations": 60,
            "range_max_bandwidth_quantile": 0.60,
            "range_max_ma_spread_quantile": 0.70,
        },
    )
    print(statistics)


if __name__ == "__main__":
    main()
