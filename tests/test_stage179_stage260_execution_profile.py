from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_official_execution_profile as execution_profiles
from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
from qmt_roll_official_pending_artifact import (
    load_validated_artifact_snapshot,
    materialize_validated_artifact_snapshot,
)
from run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate import (
    run_daily_execution_gate,
)


class Stage260ExecutionProfileTest(unittest.TestCase):
    _COHORT_ID = "c" * 64

    def setUp(self) -> None:
        temp_context = tempfile.TemporaryDirectory()
        self.addCleanup(temp_context.cleanup)
        temp_dir = Path(temp_context.name)
        self.profile = replace(
            STAGE372_20W_PROFILE,
            summary_path=temp_dir / "summary.json",
            signal_plan_path=temp_dir / "signal.csv",
            current_positions_path=temp_dir / "current.csv",
            pending_orders_path=temp_dir / "pending.csv",
            pending_orders_audit_path=temp_dir / "audit.json",
        )
        registry_patch = patch.dict(
            execution_profiles._PROFILES,
            {self.profile.profile_key: self.profile},
        )
        registry_patch.start()
        self.addCleanup(registry_patch.stop)

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

    def _snapshot(
        self,
        *,
        summary: dict[str, object] | None = None,
        signal_plan: pd.DataFrame | None = None,
        pending_orders: pd.DataFrame | None = None,
        current_positions: pd.DataFrame | None = None,
    ):
        summary = summary or self._official_summary()
        signal_plan = (
            signal_plan
            if signal_plan is not None
            else pd.DataFrame()
        )
        pending_orders = (
            pending_orders
            if pending_orders is not None
            else pd.DataFrame()
        )
        current_positions = (
            current_positions
            if current_positions is not None
            else pd.DataFrame()
        )
        summary_bytes = json.dumps(summary).encode("utf-8")
        signal_bytes = signal_plan.to_csv(index=False).encode("utf-8-sig")
        current_bytes = current_positions.to_csv(index=False).encode("utf-8-sig")
        pending_bytes = pending_orders.to_csv(index=False).encode("utf-8-sig")
        audit = {
            "schema_version": 1,
            "status": "ready",
            "cohort_id": self._COHORT_ID,
            "target_date": "2026-07-18",
            "execution_profile": STAGE372_20W_PROFILE.profile_key,
            "official_live_version": STAGE372_20W_PROFILE.official_version,
            "capital": STAGE372_20W_PROFILE.capital,
            "capital_label": STAGE372_20W_PROFILE.capital_label,
            "official_summary_sha256": hashlib.sha256(summary_bytes).hexdigest(),
            "signal_plan_sha256": hashlib.sha256(signal_bytes).hexdigest(),
            "current_positions_sha256": hashlib.sha256(current_bytes).hexdigest(),
            "pending_orders_sha256": hashlib.sha256(pending_bytes).hexdigest(),
            "pending_order_count": len(pending_orders),
            "order_api_called_count": 0,
        }
        self.profile.summary_path.write_bytes(summary_bytes)
        self.profile.signal_plan_path.write_bytes(signal_bytes)
        self.profile.current_positions_path.write_bytes(current_bytes)
        self.profile.pending_orders_path.write_bytes(pending_bytes)
        self.profile.pending_orders_audit_path.write_bytes(
            json.dumps(audit).encode("utf-8")
        )
        return load_validated_artifact_snapshot(self.profile)

    def _run(self):
        now = datetime(2026, 7, 18, 21, 0, 10)
        signal_plan = pd.DataFrame(
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
        )
        return run_daily_execution_gate(
            self.profile,
            artifact_snapshot=self._snapshot(signal_plan=signal_plan),
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

    def test_iso_timezone_snapshot_timestamp_is_fresh(self) -> None:
        signal_plan = pd.DataFrame(
            [
                {
                    "shadow_session_id": "stage372-20260817",
                    "trade_id": "trade-iso-time",
                    "vt_symbol": "JM609.DCE",
                    "direction": "long",
                    "offset": "open",
                    "volume": 1,
                    "theoretical_price": 1000.0,
                    "exit_reason": "stage372_daily_open",
                }
            ]
        )

        result = run_daily_execution_gate(
            self.profile,
            artifact_snapshot=self._snapshot(signal_plan=signal_plan),
            readonly_summary={
                "status": "readonly_snapshots_received",
                "generated_at": "2026-08-17T21:06:18.283886+08:00",
                "broker_snapshot": {
                    "position_snapshot_state": "confirmed_flat",
                },
            },
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            max_snapshot_age_seconds=300,
            now=datetime(2026, 8, 17, 21, 6, 20),
            write_outputs=False,
        )

        self.assertEqual(
            result.summary["readonly_gate"]["snapshot_age_seconds"],
            1.716,
        )
        self.assertTrue(result.summary["readonly_gate"]["passed"])
        self.assertEqual(result.summary["executable_count"], 1)

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
                self.profile,
                artifact_snapshot=self._snapshot(summary={
                    "analysis_end": "2026-07-18",
                    "execution_profile": STAGE372_20W_PROFILE.profile_key,
                    "official_live_version": "wrong-version",
                    "capital": 200_000.0,
                    "capital_label": "20w",
                }),
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
                        self.profile,
                        artifact_snapshot=self._snapshot(summary=summary),
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
            self._snapshot(
                pending_orders=stale_pending,
            )

    def test_external_signal_frame_cannot_override_validated_snapshot(self) -> None:
        attacker_signal = pd.DataFrame(
            [
                {
                    "vt_symbol": "JM609.DCE",
                    "direction": "short",
                    "offset": "open",
                    "volume": 1,
                    "theoretical_price": 1000.0,
                }
            ]
        )
        result = run_daily_execution_gate(
            self.profile,
            artifact_snapshot=self._snapshot(),
            signal_plan=attacker_signal,
            readonly_summary={},
            positions=pd.DataFrame(),
            orders=pd.DataFrame(),
            write_outputs=False,
        )

        self.assertEqual(result.summary["execution_candidate_count"], 0)
        self.assertEqual(result.summary["executable_count"], 0)

    def test_snapshot_cannot_be_rebound_to_different_artifact_paths(self) -> None:
        snapshot = self._snapshot()

        with self.assertRaisesRegex(
            ValueError,
            "execution_profile_not_canonical",
        ):
            materialize_validated_artifact_snapshot(
                STAGE372_20W_PROFILE,
                snapshot,
            )

    def test_public_loader_rejects_pre_rebound_profile_paths(self) -> None:
        self._snapshot()

        with patch.dict(
            execution_profiles._PROFILES,
            {STAGE372_20W_PROFILE.profile_key: STAGE372_20W_PROFILE},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "execution_profile_not_canonical",
            ):
                load_validated_artifact_snapshot(self.profile)

    def test_stage260_rejects_pre_rebound_profile_and_snapshot(self) -> None:
        snapshot = self._snapshot()

        with patch.dict(
            execution_profiles._PROFILES,
            {STAGE372_20W_PROFILE.profile_key: STAGE372_20W_PROFILE},
        ):
            with self.assertRaisesRegex(
                ValueError,
                "execution_profile_not_canonical",
            ):
                run_daily_execution_gate(
                    self.profile,
                    artifact_snapshot=snapshot,
                    readonly_summary={},
                    positions=pd.DataFrame(),
                    orders=pd.DataFrame(),
                    write_outputs=False,
                )

    def test_audit_generation_change_during_snapshot_read_fails_closed(self) -> None:
        self._snapshot()
        original_read_bytes = Path.read_bytes
        audit_reads = 0

        def changing_audit(path: Path) -> bytes:
            nonlocal audit_reads
            payload = original_read_bytes(path)
            if path == self.profile.pending_orders_audit_path:
                audit_reads += 1
                if audit_reads == 2:
                    return payload + b"\n"
            return payload

        with patch.object(Path, "read_bytes", new=changing_audit):
            with self.assertRaisesRegex(
                ValueError,
                "pending_artifact_snapshot_generation_changed",
            ):
                load_validated_artifact_snapshot(self.profile)


if __name__ == "__main__":
    unittest.main()
