from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
sys.path.insert(0, str(TOOLS_DIR))

import stage004_official_promotion_robustness as stage004


class Stage004RunnerTest(unittest.TestCase):
    @staticmethod
    def _summary_row() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "end_equity": 150_000.0,
                    "total_return_pct": 0.0,
                    "max_dd_pct": 0.0,
                    "sharpe": 0.0,
                    "total_slippage": 0.0,
                    "total_trade_count": 0,
                    "account_survival_pass": 1,
                    "broker10_100_pass": 1,
                    "window_name": "mstart_2018_01",
                    "window_label": "stale fixed label",
                    "requested_start_month": "2018-01",
                    "start_month": "2018-01",
                    "start_year": 2018,
                    "start_month_num": 1,
                }
            ]
        )

    def test_run_window_replaces_fixed_legacy_provenance(self) -> None:
        window = {
            "window_id": "weak_2022_01_1y",
            "group": "weak_one_year",
            "start": pd.Timestamp("2022-01-01"),
            "end": pd.Timestamp("2022-12-31"),
        }
        arm = stage004.ARMS[0]
        with patch.object(stage004.s1, "_run_arm", return_value=(self._summary_row(), pd.DataFrame(), {})):
            result = stage004._run_window({}, window, arm).iloc[0]

        self.assertEqual("weak_2022_01_1y", result["window_name"])
        self.assertEqual("2022-01-01 independent start to 2022-12-31", result["window_label"])
        self.assertEqual("2022-01", result["requested_start_month"])
        self.assertEqual("2022-01", result["start_month"])
        self.assertEqual(2022, result["start_year"])
        self.assertEqual(1, result["start_month_num"])

    def test_validate_summary_requires_exact_window_arm_identity(self) -> None:
        rows: list[dict[str, object]] = []
        for window in stage004.WINDOWS:
            for arm in stage004.ARMS:
                row = self._summary_row().iloc[0].to_dict()
                row.update({"window_id": window["window_id"], "promotion_arm": arm["arm"]})
                rows.append(row)
        valid = pd.DataFrame(rows)
        stage004._validate_summary(valid)

        with self.assertRaisesRegex(RuntimeError, "stage004_window_arm_identity_mismatch"):
            stage004._validate_summary(valid.iloc[:-1].copy())

    def test_validate_summary_fails_closed_on_missing_metric(self) -> None:
        rows: list[dict[str, object]] = []
        for window in stage004.WINDOWS:
            for arm in stage004.ARMS:
                row = self._summary_row().iloc[0].to_dict()
                row.update({"window_id": window["window_id"], "promotion_arm": arm["arm"]})
                rows.append(row)
        invalid = pd.DataFrame(rows)
        invalid.loc[0, "sharpe"] = float("nan")

        with self.assertRaisesRegex(RuntimeError, "stage004_critical_metric_missing"):
            stage004._validate_summary(invalid)


if __name__ == "__main__":
    unittest.main()
