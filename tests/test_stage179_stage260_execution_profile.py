from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sys
import unittest

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
from run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate import (
    run_daily_execution_gate,
)


class Stage260ExecutionProfileTest(unittest.TestCase):
    _COHORT_ID = "c" * 64
    _ARTIFACT_HASHES = {
        "official_summary": "1" * 64,
        "signal_plan": "2" * 64,
        "current_positions": "3" * 64,
        "pending_orders": "4" * 64,
    }

    def _official_summary(self) -> dict[str, object]:
        return {
            "analysis_end": "2026-07-18",
            "generated_at": "2026-07-18 20:59:30",
            "execution_profile": STAGE372_20W_PROFILE.profile_key,
            "official_live_version": STAGE372_20W_PROFILE.official_version,
            "capital": STAGE372_20W_PROFILE.capital,
            "capital_label": STAGE372_20W_PROFILE.capital_label,
            "current_variant": {
                "deployable_pass": 1,
                "days_over_100pct": 0,
                "days_over_90pct": 0,
                "max_broker10_margin_to_equity_pct": 55.0,
                "max_dd_pct": -16.0,
                "end_equity": 220_000.0,
            },
        }

    def _pending_audit(self, *, count: int = 0) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "ready",
            "cohort_id": self._COHORT_ID,
            "target_date": "2026-07-18",
            "execution_profile": STAGE372_20W_PROFILE.profile_key,
            "official_live_version": STAGE372_20W_PROFILE.official_version,
            "capital": STAGE372_20W_PROFILE.capital,
            "capital_label": STAGE372_20W_PROFILE.capital_label,
            "official_summary_sha256": self._ARTIFACT_HASHES["official_summary"],
            "signal_plan_sha256": self._ARTIFACT_HASHES["signal_plan"],
            "current_positions_sha256": self._ARTIFACT_HASHES["current_positions"],
            "pending_orders_sha256": self._ARTIFACT_HASHES["pending_orders"],
            "pending_order_count": count,
            "order_api_called_count": 0,
        }

    def _run(self):
        now = datetime(2026, 7, 18, 21, 0, 10)
        return run_daily_execution_gate(
            STAGE372_20W_PROFILE,
            official_summary=self._official_summary(),
            signal_plan=pd.DataFrame(
                [
                    {
                        "shadow_session_id": "stage372-20260718",
                        "trade_id": "trade-1",
                        "vt_symbol": "JM609.DCE",
                        "direction": "short",
                        "offset": "open",
                        "volume": 1,
                        "theoretical_price": 1000.0,
                        "exit_reason": "stage372_daily_open",
                    }
                ]
            ),
            pending_orders=pd.DataFrame(),
            pending_artifact_audit=self._pending_audit(),
            artifact_hashes=self._ARTIFACT_HASHES,
            current_positions=pd.DataFrame(),
            readonly_summary={
                "status": "readonly_snapshots_received",
                "generated_at": "2026-07-18 21:00:00",
                "broker_snapshot": {
                    "position_snapshot_state": "confirmed_flat",
                },
            },
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            max_snapshot_age_seconds=300,
            now=now,
            write_outputs=False,
        )

    def test_stage372_gate_emits_bound_identity_and_zero_order_api(self) -> None:
        result = self._run()

        self.assertEqual(result.summary["execution_profile"], "stage372-20w")
        self.assertEqual(
            result.summary["official_live_version"],
            STAGE372_20W_PROFILE.official_version,
        )
        self.assertEqual(result.summary["capital"], 200_000.0)
        self.assertEqual(result.summary["capital_label"], "20w")
        self.assertEqual(result.summary["order_api_called_count"], 0)
        self.assertEqual(result.summary["executable_count"], 1)
        self.assertEqual(result.summary["pending_cohort_id"], self._COHORT_ID)
        self.assertEqual(
            set(result.decisions["intent_source"]),
            {"stage260_stage372_daily"},
        )
        self.assertTrue(result.decisions.iloc[0]["decision_id"])

    def test_stage372_decision_id_is_stable_across_replay(self) -> None:
        first = self._run()
        second = self._run()

        self.assertEqual(
            first.decisions.iloc[0]["decision_id"],
            second.decisions.iloc[0]["decision_id"],
        )

    def test_explicit_summary_identity_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_version_mismatch",
        ):
            run_daily_execution_gate(
                STAGE372_20W_PROFILE,
                official_summary={
                    "analysis_end": "2026-07-18",
                    "execution_profile": STAGE372_20W_PROFILE.profile_key,
                    "official_live_version": "wrong-version",
                    "capital": 200_000.0,
                    "capital_label": "20w",
                },
                signal_plan=pd.DataFrame(),
                pending_orders=pd.DataFrame(),
                pending_artifact_audit=self._pending_audit(),
                artifact_hashes=self._ARTIFACT_HASHES,
                current_positions=pd.DataFrame(),
                readonly_summary={},
                positions=pd.DataFrame(),
                orders=pd.DataFrame(),
                write_outputs=False,
            )

    def test_missing_or_partial_summary_identity_fails_closed(self) -> None:
        for missing_fields in (
            {
                "execution_profile",
                "official_live_version",
                "capital",
                "capital_label",
            },
            {"capital_label"},
        ):
            with self.subTest(missing_fields=missing_fields):
                summary = self._official_summary()
                for field in missing_fields:
                    summary.pop(field)
                with self.assertRaisesRegex(
                    ValueError,
                    "execution_profile_identity_missing",
                ):
                    run_daily_execution_gate(
                        STAGE372_20W_PROFILE,
                        official_summary=summary,
                        signal_plan=pd.DataFrame(),
                        pending_orders=pd.DataFrame(),
                        pending_artifact_audit=self._pending_audit(),
                        artifact_hashes=self._ARTIFACT_HASHES,
                        current_positions=pd.DataFrame(),
                        readonly_summary={},
                        positions=pd.DataFrame(),
                        orders=pd.DataFrame(),
                        write_outputs=False,
                    )

    def test_stale_pending_row_cannot_be_relabelled_to_summary_date(self) -> None:
        stale_pending = pd.DataFrame(
            [
                {
                    "cohort_id": self._COHORT_ID,
                    "target_date": "2026-07-17",
                    "execution_profile": STAGE372_20W_PROFILE.profile_key,
                    "official_live_version": STAGE372_20W_PROFILE.official_version,
                    "capital": STAGE372_20W_PROFILE.capital,
                    "capital_label": STAGE372_20W_PROFILE.capital_label,
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "price": 1000.0,
                    "volume": 1,
                }
            ]
        )
        with self.assertRaisesRegex(
            ValueError,
            "pending_artifact_row_target_date_mismatch",
        ):
            run_daily_execution_gate(
                STAGE372_20W_PROFILE,
                official_summary=self._official_summary(),
                signal_plan=pd.DataFrame(),
                pending_orders=stale_pending,
                pending_artifact_audit=self._pending_audit(count=1),
                artifact_hashes=self._ARTIFACT_HASHES,
                current_positions=pd.DataFrame(),
                readonly_summary={},
                positions=pd.DataFrame(),
                orders=pd.DataFrame(),
                write_outputs=False,
            )


if __name__ == "__main__":
    unittest.main()
