from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
import run_qmt_roll_stage931_official_live_ctp_submit_adapter as stage931


class Stage372SubmitBoundaryTest(unittest.TestCase):
    def _row(self) -> dict[str, object]:
        return {
            "intent_id": "STAGE905-STAGE260-" + "a" * 64,
            "execution_profile": "stage372-20w",
            "official_live_version": STAGE372_20W_PROFILE.official_version,
            "capital": 200_000.0,
            "capital_label": "20w",
            "source": "stage260_stage372_daily",
            "offset": "open",
        }

    def test_stage372_valid_daily_intent_passes_profile_gate(self) -> None:
        self.assertEqual(
            stage931._execution_profile_intent_blockers(
                STAGE372_20W_PROFILE,
                self._row(),
            ),
            [],
        )

    def test_stage372_c9_source_is_rejected_before_api_slot(self) -> None:
        row = self._row()
        row.update(
            {
                "source": "stage904_c9_intraday_retry_open",
                "intent_role": "c9_retry_open_once",
                "position_cycle_id": "cycle-1",
            }
        )

        blockers = stage931._execution_profile_intent_blockers(
            STAGE372_20W_PROFILE,
            row,
        )

        self.assertIn(
            "intent_source_not_allowed_for_execution_profile",
            blockers,
        )
        self.assertIn("stage372_c9_intent_metadata_forbidden", blockers)

    def test_stage372_identity_mismatch_is_rejected(self) -> None:
        row = self._row()
        row["capital"] = 150_000.0

        blockers = stage931._execution_profile_intent_blockers(
            STAGE372_20W_PROFILE,
            row,
        )

        self.assertIn("execution_profile_capital_mismatch", blockers)

    def test_stage931_cli_defaults_to_stage372_profile(self) -> None:
        args = stage931.parse_args(
            ["--command", "once", "--target-date", "2026-07-18"]
        )

        self.assertEqual(args.execution_profile, "stage372-20w")


if __name__ == "__main__":
    unittest.main()
