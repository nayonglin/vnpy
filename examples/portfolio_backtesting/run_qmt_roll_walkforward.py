from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest


TRAIN_MONTHS: int = 24
TEST_MONTHS: int = 12
STEP_MONTHS: int = 6
CAPITAL: float = 200_000
SAVE_ARTIFACTS: bool = False
CANDIDATE_CONFIGS: list[dict[str, Any]] = [
    {
        "label": "champion_0045_006_006_0025",
        "risk_ratio": 0.045,
        "risk_overrides": {
            "risk_ratio_of_total_assets": 0.045,
            "risk_ratio_open_interest_surge": 0.06,
            "risk_ratio_volume_open_interest_surge": 0.06,
            "risk_ratio_open_interest_decline": 0.025,
        },
    },
    {
        "label": "alt_0045_006_006_0030",
        "risk_ratio": 0.045,
        "risk_overrides": {
            "risk_ratio_of_total_assets": 0.045,
            "risk_ratio_open_interest_surge": 0.06,
            "risk_ratio_volume_open_interest_surge": 0.06,
            "risk_ratio_open_interest_decline": 0.03,
        },
    },
    {
        "label": "alt_0040_006_006_0030",
        "risk_ratio": 0.04,
        "risk_overrides": {
            "risk_ratio_of_total_assets": 0.04,
            "risk_ratio_open_interest_surge": 0.06,
            "risk_ratio_volume_open_interest_surge": 0.06,
            "risk_ratio_open_interest_decline": 0.03,
        },
    },
    {
        "label": "alt_0040_0055_007_0025",
        "risk_ratio": 0.04,
        "risk_overrides": {
            "risk_ratio_of_total_assets": 0.04,
            "risk_ratio_open_interest_surge": 0.055,
            "risk_ratio_volume_open_interest_surge": 0.07,
            "risk_ratio_open_interest_decline": 0.025,
        },
    },
    {
        "label": "alt_0040_0055_006_0030",
        "risk_ratio": 0.04,
        "risk_overrides": {
            "risk_ratio_of_total_assets": 0.04,
            "risk_ratio_open_interest_surge": 0.055,
            "risk_ratio_volume_open_interest_surge": 0.06,
            "risk_ratio_open_interest_decline": 0.03,
        },
    },
]


def add_months(dt: datetime, months: int) -> datetime:
    return (pd.Timestamp(dt) + pd.DateOffset(months=months)).to_pydatetime()


def build_walkforward_windows() -> list[tuple[int, datetime, datetime, datetime, datetime]]:
    windows: list[tuple[int, datetime, datetime, datetime, datetime]] = []
    window_id: int = 1
    train_start: datetime = START_DT

    while True:
        test_start: datetime = add_months(train_start, TRAIN_MONTHS)
        test_end_exclusive: datetime = add_months(test_start, TEST_MONTHS)
        if test_start > END_DT:
            break

        test_end: datetime = min(END_DT, test_end_exclusive - pd.Timedelta(days=1).to_pytimedelta())
        train_end: datetime = test_start - pd.Timedelta(days=1).to_pytimedelta()
        if train_end < train_start or test_end < test_start:
            break

        windows.append((window_id, train_start, train_end, test_start, test_end))
        window_id += 1

        next_train_start: datetime = add_months(train_start, STEP_MONTHS)
        if next_train_start >= END_DT:
            break
        train_start = next_train_start

    return windows


def compute_score(statistics: dict[str, Any]) -> float:
    annual_return: float = float(statistics.get("annual_return", 0) or 0)
    sharpe_ratio: float = float(statistics.get("sharpe_ratio", 0) or 0)
    max_dd_percent: float = abs(float(statistics.get("max_ddpercent", 0) or 0))
    return_drawdown_ratio: float = float(statistics.get("return_drawdown_ratio", 0) or 0)

    penalty: float = max_dd_percent / 100.0
    return 0.45 * return_drawdown_ratio + 0.30 * sharpe_ratio + 0.25 * (annual_return / 100.0) - 0.10 * penalty


def run_walkforward() -> tuple[pd.DataFrame, pd.DataFrame]:
    train_rows: list[dict[str, object]] = []
    test_rows: list[dict[str, object]] = []

    for window_id, train_start, train_end, test_start, test_end in build_walkforward_windows():
        print(
            "[walkforward] window",
            window_id,
            f"train={train_start.date()}->{train_end.date()}",
            f"test={test_start.date()}->{test_end.date()}",
        )

        train_candidates: list[tuple[dict[str, Any], float, dict[str, Any]]] = []
        for config in CANDIDATE_CONFIGS:
            risk_ratio = float(config["risk_ratio"])
            risk_overrides = dict(config["risk_overrides"])
            _, _, train_stats = run_backtest(
                risk_ratio=risk_ratio,
                risk_overrides=risk_overrides,
                analysis_start=train_start,
                analysis_end=train_end,
                capital=CAPITAL,
                save_artifacts=False,
                file_prefix=f"qmt_roll_wf_train_{window_id}_{config['label']}",
                chart_title=f"QMT Roll WF Train {window_id}",
            )
            score: float = compute_score(train_stats)
            train_candidates.append((config, score, train_stats))
            train_rows.append(
                build_summary_row(
                    train_stats,
                    analysis_start=train_start,
                    analysis_end=train_end,
                    phase="train",
                    window_id=window_id,
                    config_label=str(config["label"]),
                    risk_ratio=risk_ratio,
                    base_risk=risk_overrides["risk_ratio_of_total_assets"],
                    oi_surge_risk=risk_overrides["risk_ratio_open_interest_surge"],
                    vol_oi_surge_risk=risk_overrides["risk_ratio_volume_open_interest_surge"],
                    oi_decline_risk=risk_overrides["risk_ratio_open_interest_decline"],
                    score=score,
                )
            )

        chosen_config, chosen_score, chosen_train_stats = max(train_candidates, key=lambda item: item[1])
        chosen_risk: float = float(chosen_config["risk_ratio"])
        chosen_overrides: dict[str, float] = dict(chosen_config["risk_overrides"])
        test_prefix: str = f"qmt_roll_wf_test_{window_id}_{chosen_config['label']}"
        _, _, test_stats = run_backtest(
            risk_ratio=chosen_risk,
            risk_overrides=chosen_overrides,
            analysis_start=test_start,
            analysis_end=test_end,
            capital=CAPITAL,
            save_artifacts=SAVE_ARTIFACTS,
            file_prefix=test_prefix,
            chart_title=f"QMT Roll WF Test {window_id}",
        )
        test_rows.append(
            build_summary_row(
                test_stats,
                analysis_start=test_start,
                analysis_end=test_end,
                phase="test",
                window_id=window_id,
                selected_config_label=str(chosen_config["label"]),
                selected_risk_ratio=chosen_risk,
                selected_base_risk=chosen_overrides["risk_ratio_of_total_assets"],
                selected_oi_surge_risk=chosen_overrides["risk_ratio_open_interest_surge"],
                selected_vol_oi_surge_risk=chosen_overrides["risk_ratio_volume_open_interest_surge"],
                selected_oi_decline_risk=chosen_overrides["risk_ratio_open_interest_decline"],
                train_score=chosen_score,
                train_annual_return_pct=float(chosen_train_stats.get("annual_return", 0) or 0),
                train_max_dd_percent=float(chosen_train_stats.get("max_ddpercent", 0) or 0),
            )
        )

    return pd.DataFrame(train_rows), pd.DataFrame(test_rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_df, test_df = run_walkforward()

    train_path: Path = (OUTPUT_DIR / "qmt_roll_walkforward_train_summary.csv").resolve()
    test_path: Path = (OUTPUT_DIR / "qmt_roll_walkforward_test_summary.csv").resolve()
    train_df.to_csv(train_path, index=False, encoding="utf-8-sig")
    test_df.to_csv(test_path, index=False, encoding="utf-8-sig")
    print(f"[walkforward] train summary csv: {train_path}")
    print(f"[walkforward] test summary csv: {test_path}")
    if not test_df.empty:
        print(test_df.to_string(index=False))


if __name__ == "__main__":
    main()
