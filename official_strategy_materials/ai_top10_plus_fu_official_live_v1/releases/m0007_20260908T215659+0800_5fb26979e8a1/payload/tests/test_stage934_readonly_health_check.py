from __future__ import annotations

import os
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


PORTFOLIO_DIR = (
    Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
)
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))
os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")

import run_qmt_roll_stage934_official_live_automation_health_check as stage934  # noqa: E402


class Stage934ReadonlyHealthCheckTest(unittest.TestCase):
    def _healthy_latest(self, **overrides: object) -> dict[str, object]:
        latest: dict[str, object] = {
            "exists": True,
            "daemon_status": "daemon_running",
            "execution_profile": "c9-15w",
            "official_live_version": (
                "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
            ),
            "capital": 150_000.0,
            "capital_label": "15w",
            "runtime_profile": "production-readonly",
            "mode": "dry-run",
            "submit_mode": "disabled",
            "launchd_provenance": {
                "complete": 1,
                "xpc_service_name": (
                    "local.qmt-roll.official-live.15w."
                    "c9-readonly-night-session"
                ),
            },
            "ai_pool_preflight": {
                "automation_status": "monthly_ai_pool_already_current"
            },
            "latest_cycle": {},
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "order_api_evidence_complete": 1,
            "order_api_evidence_missing_fields": [],
        }
        latest.update(overrides)
        return latest

    def test_current_session_labels_are_c9_readonly_only(self) -> None:
        self.assertEqual(
            {
                "day": "local.qmt-roll.official-live.15w.c9-readonly-day-session",
                "night": "local.qmt-roll.official-live.15w.c9-readonly-night-session",
            },
            stage934.SESSION_LABELS,
        )
        self.assertEqual(
            {
                "c9_postclose_precompute": (
                    "local.qmt-roll.official-live.15w."
                    "c9-readonly-postclose-precompute"
                )
            },
            stage934.PRECOMPUTE_LABELS,
        )

    def test_postclose_precompute_is_bound_to_stage909_c9_readonly_plist(self) -> None:
        label = stage934.PRECOMPUTE_LABELS["c9_postclose_precompute"]
        path = stage934.LAUNCHD_REPO_DIR / f"{label}.plist"
        with path.open("rb") as handle:
            payload = plistlib.load(handle)

        arguments = payload["ProgramArguments"]
        operational_root = Path("/Users/bytedance/Desktop/person/vnpy")
        self.assertEqual(
            [
                str(operational_root / ".py311/bin/python"),
                str(
                    operational_root
                    / "examples/portfolio_backtesting/"
                    "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py"
                ),
            ],
            arguments[:2],
        )
        self.assertIn("c9-15w", arguments)

    def test_readonly_readiness_never_requires_real_submit_arming(self) -> None:
        latest = self._healthy_latest(
            latest_cycle={
                "stage903": {
                    "summary": {
                        "stage905_ready_count": 1,
                        "stage905_executor_status": "executor_dry_run_ready",
                    }
                },
                "stage927": {"summary": {"real_submit_permitted": 0}},
                "stage931_submit_blockers": ["real_submit_not_armed"],
            },
        )

        result = stage934._execution_readiness(
            latest,
            summary_fresh=True,
            process_running=True,
            daemon_running=True,
            expected_launchd_label=(
                "local.qmt-roll.official-live.15w.c9-readonly-night-session"
            ),
        )

        self.assertEqual(
            "readonly_observation_ready_with_intents",
            result["execution_readiness_status"],
        )
        self.assertEqual([], result["readiness_blockers"])
        self.assertNotIn(
            "stage927_real_submit_permitted=0",
            result["readiness_blockers"],
        )

    def test_any_order_api_call_blocks_readonly_qualification(self) -> None:
        latest = self._healthy_latest(order_api_called_count=1)

        result = stage934._execution_readiness(
            latest,
            summary_fresh=True,
            process_running=True,
            daemon_running=True,
        )

        self.assertEqual(
            "readonly_observation_blocked",
            result["execution_readiness_status"],
        )
        self.assertIn(
            "stage930_readonly_order_api_called_count=1",
            result["readiness_blockers"],
        )

    def test_send_or_cancel_count_cannot_hide_behind_zero_aggregate(self) -> None:
        for field_name in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
        ):
            with self.subTest(field_name=field_name):
                latest = {
                    **self._healthy_latest(),
                    field_name: 1,
                }

                result = stage934._execution_readiness(
                    latest,
                    summary_fresh=True,
                    process_running=True,
                    daemon_running=True,
                )

                self.assertEqual(
                    "readonly_observation_blocked",
                    result["execution_readiness_status"],
                )
                self.assertIn(
                    f"stage930_readonly_{field_name}=1",
                    result["readiness_blockers"],
                )

                stale_result = stage934._execution_readiness(
                    latest,
                    summary_fresh=False,
                    process_running=False,
                    daemon_running=False,
                )
                self.assertEqual(
                    "readonly_observation_blocked",
                    stale_result["execution_readiness_status"],
                )
                self.assertIn(
                    f"stage930_readonly_{field_name}=1",
                    stale_result["readiness_blockers"],
                )

    def test_missing_or_invalid_order_api_evidence_fails_closed(self) -> None:
        for field_name in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        ):
            for invalid_value in (None, "0", 0.0, True, -1):
                with self.subTest(
                    field_name=field_name,
                    invalid_value=invalid_value,
                ):
                    latest = self._healthy_latest()
                    if invalid_value is None:
                        latest.pop(field_name)
                    else:
                        latest[field_name] = invalid_value

                    result = stage934._execution_readiness(
                        latest,
                        summary_fresh=True,
                        process_running=True,
                        daemon_running=True,
                    )

                    self.assertEqual(
                        "readonly_observation_blocked",
                        result["execution_readiness_status"],
                    )
                    self.assertIn(
                        f"stage930_readonly_{field_name}_missing_or_invalid",
                        result["readiness_blockers"],
                    )

        for latest in (
            self._healthy_latest(order_api_evidence_complete=0),
            self._healthy_latest(
                order_api_evidence_missing_fields=["stage931.summary.send"]
            ),
        ):
            result = stage934._execution_readiness(
                latest,
                summary_fresh=True,
                process_running=True,
                daemon_running=True,
            )
            self.assertEqual(
                "readonly_observation_blocked",
                result["execution_readiness_status"],
            )
            self.assertIn(
                "stage930_readonly_order_api_evidence_incomplete",
                result["readiness_blockers"],
            )

    def test_readonly_identity_runtime_and_launchd_provenance_are_exact(self) -> None:
        invalid_cases = {
            "execution_profile": "stage372-20w",
            "official_live_version": "wrong-version",
            "capital": 200_000.0,
            "capital_label": "20w",
            "runtime_profile": "offline",
            "mode": "live-real",
            "submit_mode": "live-real",
            "launchd_provenance": {
                "complete": 0,
                "xpc_service_name": (
                    "local.qmt-roll.official-live.15w."
                    "c9-readonly-night-session"
                ),
            },
        }
        for field_name, invalid_value in invalid_cases.items():
            with self.subTest(field_name=field_name):
                result = stage934._execution_readiness(
                    self._healthy_latest(**{field_name: invalid_value}),
                    summary_fresh=True,
                    process_running=True,
                    daemon_running=field_name not in {"mode", "submit_mode"},
                    expected_launchd_label=(
                        "local.qmt-roll.official-live.15w."
                        "c9-readonly-night-session"
                    ),
                )

                self.assertEqual(
                    "readonly_observation_blocked",
                    result["execution_readiness_status"],
                )
                self.assertTrue(result["readiness_blockers"])

        wrong_label = stage934._execution_readiness(
            self._healthy_latest(),
            summary_fresh=True,
            process_running=True,
            daemon_running=True,
            expected_launchd_label=(
                "local.qmt-roll.official-live.15w.c9-readonly-day-session"
            ),
        )
        self.assertIn(
            "stage930_launchd_provenance_label_mismatch",
            wrong_label["readiness_blockers"],
        )

    def test_latest_summary_is_discovered_in_isolated_session_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_root = root / "old"
            session_root = root / "readonly-night"
            old_root.mkdir()
            session_root.mkdir()
            old_path = old_root / (
                f"{stage934.STAGE930_PREFIX}_summary_old_"
                f"{stage934.STAGE930_MODEL_TAG}.json"
            )
            new_path = session_root / (
                f"{stage934.STAGE930_PREFIX}_summary_new_"
                f"{stage934.STAGE930_MODEL_TAG}.json"
            )
            old_path.write_text(
                json.dumps({"daemon_status": "old"}), encoding="utf-8"
            )
            time.sleep(0.01)
            new_path.write_text(
                json.dumps(
                    {
                        "daemon_status": "daemon_running",
                        "execution_profile": "c9-15w",
                        "official_live_version": (
                            "official_live_stage847_c9_15w_"
                            "stage819_05r_stop_retry_once"
                        ),
                        "capital": 150_000.0,
                        "capital_label": "15w",
                        "runtime_profile": "production-readonly",
                        "launchd_provenance": {
                            "complete": 1,
                            "xpc_service_name": (
                                "local.qmt-roll.official-live.15w."
                                "c9-readonly-night-session"
                            ),
                        },
                        "send_order_api_called_count": 1,
                        "cancel_order_api_called_count": 2,
                        "order_api_called_count": 3,
                        "order_api_evidence_complete": 1,
                        "order_api_evidence_missing_fields": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                stage934,
                "_stage930_output_dirs",
                return_value=(old_root, session_root),
            ):
                result = stage934._latest_stage930_summary()

        self.assertEqual(str(new_path), result["path"])
        self.assertEqual("daemon_running", result["daemon_status"])
        self.assertEqual("c9-15w", result["execution_profile"])
        self.assertEqual("production-readonly", result["runtime_profile"])
        self.assertEqual(1, result["launchd_provenance"]["complete"])
        self.assertEqual(1, result["send_order_api_called_count"])
        self.assertEqual(2, result["cancel_order_api_called_count"])
        self.assertEqual(1, result["order_api_evidence_complete"])

    def test_latest_summary_projection_never_invents_zero_api_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / (
                f"{stage934.STAGE930_PREFIX}_summary_missing_"
                f"{stage934.STAGE930_MODEL_TAG}.json"
            )
            payload = self._healthy_latest()
            payload.pop("send_order_api_called_count")
            path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(
                stage934,
                "_stage930_output_dirs",
                return_value=(root,),
            ):
                latest = stage934._latest_stage930_summary()

        self.assertIsNone(latest["send_order_api_called_count"])
        readiness = stage934._execution_readiness(
            latest,
            summary_fresh=True,
            process_running=True,
            daemon_running=True,
        )
        self.assertIn(
            "stage930_readonly_send_order_api_called_count_missing_or_invalid",
            readiness["readiness_blockers"],
        )


if __name__ == "__main__":
    unittest.main()
