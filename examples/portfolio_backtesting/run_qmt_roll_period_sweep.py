from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest


SAVE_ARTIFACTS: bool = False
BASE_RISK_RATIO: float = 0.045
RISK_OVERRIDES: dict[str, float] = {
    "risk_ratio_of_total_assets": 0.045,
    "risk_ratio_open_interest_surge": 0.06,
    "risk_ratio_volume_open_interest_surge": 0.06,
    "risk_ratio_open_interest_decline": 0.025,
}
STRATEGY_OVERRIDES: dict[str, object] = {
    "max_single_trade_capital_usage_ratio": 0.70,
}
CONFIG_LABEL: str = "global_champion_cap_1m_single_cap_0p70"
CAPITAL: float = 200_000

PERIOD_WINDOWS: list[tuple[str, datetime, datetime]] = [
    ("full_sample", START_DT, END_DT),
    ("period_2020_2021", datetime(2020, 1, 1), datetime(2021, 12, 31)),
    ("period_2022_2023", datetime(2022, 1, 1), datetime(2023, 12, 31)),
    ("period_2024_2026", datetime(2024, 1, 1), END_DT),
    ("roll_2020_2022", datetime(2020, 1, 1), datetime(2022, 12, 31)),
    ("roll_2021_2023", datetime(2021, 1, 1), datetime(2023, 12, 31)),
    ("roll_2022_2024", datetime(2022, 1, 1), datetime(2024, 12, 31)),
    ("roll_2023_2026", datetime(2023, 1, 1), END_DT),
]


def run_period_sweep() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for window_name, analysis_start, analysis_end in PERIOD_WINDOWS:
        print(f"[period] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            risk_overrides=RISK_OVERRIDES,
            strategy_overrides=STRATEGY_OVERRIDES,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=CAPITAL,
            save_artifacts=SAVE_ARTIFACTS,
            file_prefix=f"qmt_roll_{window_name}",
            chart_title=f"QMT Roll {window_name}",
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                window_name=window_name,
                config_label=CONFIG_LABEL,
                risk_ratio=BASE_RISK_RATIO,
                base_risk=RISK_OVERRIDES["risk_ratio_of_total_assets"],
                oi_surge_risk=RISK_OVERRIDES["risk_ratio_open_interest_surge"],
                vol_oi_surge_risk=RISK_OVERRIDES["risk_ratio_volume_open_interest_surge"],
                oi_decline_risk=RISK_OVERRIDES["risk_ratio_open_interest_decline"],
                capital=CAPITAL,
            )
        )

    result_df: pd.DataFrame = pd.DataFrame(rows)
    result_df.sort_values(["analysis_start", "analysis_end"], inplace=True)
    return result_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df: pd.DataFrame = run_period_sweep()
    output_path: Path = (OUTPUT_DIR / "qmt_roll_period_sweep_summary.csv").resolve()
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[period] summary csv: {output_path}")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
