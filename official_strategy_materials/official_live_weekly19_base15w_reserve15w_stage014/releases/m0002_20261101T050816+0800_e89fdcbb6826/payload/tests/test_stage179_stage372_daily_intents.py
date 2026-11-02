from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
import run_qmt_roll_stage905_official_live_executor_dry_run as stage905


class Stage372DailyIntentTest(unittest.TestCase):
    _COHORT_ID = "c" * 64

    def _decisions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "decision_id": "a" * 64,
                    "execution_profile": "stage372-20w",
                    "official_live_version": STAGE372_20W_PROFILE.official_version,
                    "capital": 200_000.0,
                    "capital_label": "20w",
                    "trade_date": "2026-07-18",
                    "pending_cohort_id": self._COHORT_ID,
                    "intent_source": "stage260_stage372_daily",
                    "execution_action": "simnow_executable",
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "planned_volume": 1.0,
                    "theoretical_price": 1000.0,
                    "execution_reason": "",
                }
            ]
        )

    def _snapshots(self) -> stage905.Stage905SnapshotInputs:
        return stage905.Stage905SnapshotInputs(
            pending_orders=pd.DataFrame(),
            contracts=pd.DataFrame(
                [
                    {
                        "vt_symbol": "JM609.DCE",
                        "pricetick": 0.5,
                        "min_volume": 1,
                        "max_volume": 100,
                    }
                ]
            ),
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            stage902_summary={
                "blocking_failure_count": 0,
                "blocking_failure_count_for_reduce_close": 0,
                "allow_new_open": 1,
                "allow_reduce_close": 1,
            },
            stage260_summary={
                "execution_profile": "stage372-20w",
                "official_live_version": STAGE372_20W_PROFILE.official_version,
                "capital": 200_000.0,
                "capital_label": "20w",
                "trade_date": "2026-07-18",
                "pending_cohort_id": self._COHORT_ID,
                "executable_count": 1,
                "order_api_called_count": 0,
            },
            execution_ledger_rows=[],
        )

    def _run(self) -> stage905.Stage905RunResult:
        return stage905.run_executor_dry_run(
            "2026-07-18",
            execution_profile=STAGE372_20W_PROFILE,
            stage260_decisions=self._decisions(),
            snapshots=self._snapshots(),
            include_stage901_pending=False,
            write_compat_outputs=False,
        )

    def test_stage372_replay_is_deterministic_and_never_reads_stage904(self) -> None:
        with patch.object(
            stage905,
            "_read_csv_maybe",
            side_effect=AssertionError("stage372 in-memory run must not read artifacts"),
        ):
            first = self._run()
            second = self._run()

        self.assertEqual(first.summary["execution_profile"], "stage372-20w")
        self.assertEqual(first.summary["ready_count"], 1)
        self.assertEqual(first.summary["send_order_api_called_count"], 0)
        self.assertEqual(
            first.intents.iloc[0]["intent_id"],
            second.intents.iloc[0]["intent_id"],
        )
        self.assertEqual(
            first.intents.iloc[0]["source"],
            "stage260_stage372_daily",
        )
        self.assertEqual(
            first.intents.iloc[0]["pending_cohort_id"],
            self._COHORT_ID,
        )

    def test_stage372_rejects_any_c9_action_input(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "stage372_intraday_input_forbidden",
        ):
            stage905.run_executor_dry_run(
                "2026-07-18",
                execution_profile=STAGE372_20W_PROFILE,
                stage904_actions=pd.DataFrame(
                    [
                        {
                            "monitor_action": "retry_open_dry_run",
                            "source": "stage904_c9_intraday_retry_open",
                        }
                    ]
                ),
                stage904_summary={"target_date": "2026-07-18"},
                stage260_decisions=self._decisions(),
                snapshots=self._snapshots(),
                include_stage901_pending=False,
                write_compat_outputs=False,
            )

    def test_stage372_rejects_missing_or_stale_pending_cohort(self) -> None:
        decisions = self._decisions()
        decisions.loc[0, "pending_cohort_id"] = "d" * 64
        with self.assertRaisesRegex(
            ValueError,
            "stage260_decision_pending_cohort_mismatch",
        ):
            stage905.run_executor_dry_run(
                "2026-07-18",
                execution_profile=STAGE372_20W_PROFILE,
                stage260_decisions=decisions,
                snapshots=self._snapshots(),
                include_stage901_pending=False,
                write_compat_outputs=False,
            )

    def test_stage372_rejects_wrong_decision_source(self) -> None:
        decisions = self._decisions()
        decisions.loc[0, "intent_source"] = "stage904_c9_intraday_retry_open"
        with self.assertRaisesRegex(
            ValueError,
            "intent_source_not_allowed_for_execution_profile",
        ):
            stage905.run_executor_dry_run(
                "2026-07-18",
                execution_profile=STAGE372_20W_PROFILE,
                stage260_decisions=decisions,
                snapshots=self._snapshots(),
                include_stage901_pending=False,
                write_compat_outputs=False,
            )


if __name__ == "__main__":
    unittest.main()
