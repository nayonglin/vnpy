from __future__ import annotations

from run_qmt_boll_reversal_backtest import run_backtest


def main() -> None:
    _, _, statistics = run_backtest(
        file_prefix="qmt_boll_reversal_refactor_v5_rsi_extreme",
        chart_title="QMT Boll Reversal Refactor V5 RSI Extreme Backtest",
        strategy_overrides={
            "boll_entry_mode": "reentry_reversal_bar",
            "exit_on_boll_middle_touch": True,
            "max_holding_days": 5,
            "block_short_when_all_ma_rising": True,
            "block_long_when_all_ma_falling": True,
            "previous_day_stop_enabled": True,
            "range_filter_enabled": False,
            "reversal_rsi_filter_enabled": True,
            "reversal_rsi_long_max": 35.0,
            "reversal_rsi_short_min": 65.0,
        },
    )
    print(statistics)


if __name__ == "__main__":
    main()
