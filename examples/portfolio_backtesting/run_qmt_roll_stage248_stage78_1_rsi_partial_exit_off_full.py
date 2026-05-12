from __future__ import annotations

from datetime import datetime

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, build_official_stage78_overrides
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


def main() -> None:
    """
    Generate full-period backtest artifacts for the "RSI partial exit OFF" variant.

    We do this because the official 78-1 baseline (and some wrappers) may carry
    implicit defaults for enable_rsi_partial_exit. This runner makes OFF explicit
    and writes trades/daily for attribution analysis.
    """
    overrides = build_official_stage78_overrides()
    overrides["enable_rsi_partial_exit"] = False
    overrides["rsi_partial_exit_threshold"] = 95.0
    overrides["rsi_partial_exit_ratio"] = 0.5
    overrides["trade_start_date"] = START_DT.date().isoformat()

    run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
        analysis_start=START_DT,
        analysis_end=END_DT,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix="qmt_roll_stage248_stage78_1_rsi_partial_exit_off_full",
        chart_title=f"Stage248 78-1 RSI partial exit OFF {datetime.now():%Y-%m-%d}",
    )


if __name__ == "__main__":
    main()

