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
RISK_GRID: list[float] = [0.01, 0.02, 0.03, 0.04]
CAPITAL: float = 200_000
SAVE_ARTIFACTS: bool = False


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

        train_candidates: list[tuple[float, float, dict[str, Any]]] = []
        for risk_ratio in RISK_GRID:
            _, _, train_stats = run_backtest(
                risk_ratio=risk_ratio,
                analysis_start=train_start,
                analysis_end=train_end,
                capital=CAPITAL,
                save_artifacts=False,
                file_prefix=f"qmt_roll_wf_train_{window_id}_{str(risk_ratio).replace('.', 'p')}",
                chart_title=f"QMT Roll WF Train {window_id}",
            )
            score: float = compute_score(train_stats)
            train_candidates.append((risk_ratio, score, train_stats))
            train_rows.append(
                build_summary_row(
                    train_stats,
                    analysis_start=train_start,
                    analysis_end=train_end,
                    phase="train",
                    window_id=window_id,
                    risk_ratio=risk_ratio,
                    score=score,
                )
            )

        chosen_risk, chosen_score, chosen_train_stats = max(train_candidates, key=lambda item: item[1])
        test_prefix: str = f"qmt_roll_wf_test_{window_id}_{str(chosen_risk).replace('.', 'p')}"
        _, _, test_stats = run_backtest(
            risk_ratio=chosen_risk,
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
                selected_risk_ratio=chosen_risk,
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
