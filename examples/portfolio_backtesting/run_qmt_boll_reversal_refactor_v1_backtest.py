from __future__ import annotations

from run_qmt_boll_reversal_backtest import run_backtest


def main() -> None:
    _, _, statistics = run_backtest(
        file_prefix="qmt_boll_reversal_refactor_v1",
        chart_title="QMT Boll Reversal Refactor V1 Backtest",
        strategy_overrides={
            "boll_entry_mode": "reentry_confirmed",
            "exit_on_boll_middle_touch": True,
            "max_holding_days": 5,
            "block_short_when_all_ma_rising": True,
            "block_long_when_all_ma_falling": True,
        },
    )
    print(statistics)


if __name__ == "__main__":
    main()
