from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage927_official_live_real_submit_arming_gate as stage927  # noqa: E402


class Stage927ScopePermitTest(unittest.TestCase):
    target_date = "2026-07-18"

    def payloads(self) -> dict[str, dict[str, object]]:
        common = {
            "official_live_version": stage927.OFFICIAL_LIVE_VERSION,
            "official_live_alias": stage927.OFFICIAL_LIVE_ALIAS,
            "order_api_called_count": 0,
        }
        payloads = {
            name: copy.deepcopy(common)
            for name in (
                "stage903",
                "stage906",
                "stage910",
                "stage912",
                "stage913",
                "stage916",
                "stage921",
                "stage923",
                "stage924",
                "stage926",
            )
        }
        for name in ("stage903", "stage906", "stage923", "stage924"):
            payloads[name]["target_date"] = self.target_date
        payloads.update(
            {
                "stage925": {},
                "stage932": {},
                "kill_switch": {},
            }
        )
        payloads["stage903"].update(
            {
                "mode": "live-real",
                "controller_status": "phase_d_controller_live_real_blocked",
                "kill_switch_active": False,
                "execution_profile": stage927.C9_15W_PROFILE.profile_key,
                "capital": stage927.OFFICIAL_LIVE_CAPITAL,
                "capital_label": stage927.OFFICIAL_LIVE_CAPITAL_LABEL,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_evidence_complete": 1,
                "stage905_exit_code": 0,
                "stage905_executor_status": "executor_no_intents",
                "stage905_ready_count": 0,
                "stage905_blocked_count": 0,
                "stage914_exit_code": 0,
                "stage914_preflight_status": "production_readonly_preflight_passed",
                "stage914_blocking_failure_count": 0,
                "stage914_order_api_called_count": 0,
                "stage907_env_profile": "production-live",
                "stage907_refresh_status": "readonly_refresh_completed_snapshot_ready",
                "stage907_readonly_status_after": "readonly_snapshots_received",
                "stage907_position_snapshot_state_after": "positions_received",
                "stage907_snapshot_evidence_complete": 1,
                "stage907_broker_query_bundle_complete": 1,
                "stage907_stage174_stdout_file_payload_match": 1,
                "stage907_snapshot_generation_uuid": "generation-1",
                "stage907_stage174_invocation_id": "invocation-1",
                "stage907_stage174_file_summary_sha256": "a" * 64,
                "stage907_stage174_stdout_summary_sha256": "a" * 64,
            }
        )
        payloads["stage906"].update(
            {
                "reconciliation_status": "reconcile_aligned",
                "account_state_alignment": "aligned",
                "broker_snapshot_ready": 1,
                "readonly_status": "readonly_snapshots_received",
                "readonly_snapshot_age_seconds": 15.0,
                "max_snapshot_age_seconds": 300,
                "position_snapshot_state": "positions_received",
                "active_broker_order_count": 0,
            }
        )
        return payloads

    def base_rows(self, *, reconcile_passed: bool = True) -> list[dict[str, object]]:
        names = [
            "profile_is_current_c9",
            "acceptance_suite_passed_fail_closed",
            "completion_audit_proven",
            "controller_not_killed_and_no_order_api",
            "health_alive",
            "static_order_boundary_passed",
            "scheduler_dynamic_target_ready",
            "no_unresolved_fail_closed_incident",
            "account_recovery_not_required",
            "account_recovery_ack_suite_passed",
            "aligned_idle_integration_passed",
            "kill_switch_inactive",
        ]
        rows = [
            {
                "check": name,
                "category": "test",
                "passed": 1,
                "severity": "block",
                "observed": "green",
                "required": "green",
                "blocker": "",
            }
            for name in names
        ]
        rows.append(
            {
                "check": "broker_shadow_reconcile_aligned",
                "category": "reconcile",
                "passed": int(reconcile_passed),
                "severity": "block",
                "observed": "aligned" if reconcile_passed else "divergent",
                "required": "aligned",
                "blocker": "" if reconcile_passed else "transient_shadow_divergence",
            }
        )
        rows.append(
            {
                "check": "controller_live_real_clean_ready",
                "category": "controller",
                "passed": 0,
                "severity": "block",
                "observed": "executor_no_intents",
                "required": "ready intent",
                "blocker": "controller_has_no_current_ready_intent",
            }
        )
        return rows

    def evaluate(
        self,
        *,
        payloads: dict[str, dict[str, object]] | None = None,
        reconcile_passed: bool = True,
        env_enabled: bool = True,
        confirm_ok: bool = True,
        mutate_rows: dict[str, int] | None = None,
    ) -> tuple[dict[str, object], dict[str, object], str]:
        current_payloads = payloads or self.payloads()
        rows = self.base_rows(reconcile_passed=reconcile_passed)
        for row in rows:
            name = str(row["check"])
            if mutate_rows and name in mutate_rows:
                row["passed"] = mutate_rows[name]
                row["blocker"] = "forced_failure" if not mutate_rows[name] else ""
        stage927._append_scope_capability_checks(
            rows,
            payloads=current_payloads,
            target_date=self.target_date,
            account_recovery_not_required=True,
            real_submit_env_enabled=env_enabled,
            confirm_live_real_ok=confirm_ok,
        )
        checks = pd.DataFrame(rows)
        source_paths = {name: None for name in current_payloads}
        return stage927._build_scope_capabilities(
            checks=checks,
            payloads=current_payloads,
            source_paths=source_paths,
            target_date=self.target_date,
            real_submit_env_enabled=env_enabled,
            confirm_live_real_ok=confirm_ok,
        )

    def assert_permits(
        self,
        capabilities: dict[str, object],
        *,
        reduce_close: int,
        retry_open: int,
        initial_open: int | None = None,
    ) -> None:
        expected_initial_open = retry_open if initial_open is None else initial_open
        self.assertEqual(
            reduce_close,
            capabilities["reduce_close"]["permitted"],  # type: ignore[index]
        )
        self.assertEqual(
            retry_open,
            capabilities["retry_open"]["permitted"],  # type: ignore[index]
        )
        self.assertEqual(
            expected_initial_open,
            capabilities["initial_open"]["permitted"],  # type: ignore[index]
        )

    def test_exact_no_intents_idle_still_produces_both_capabilities(self) -> None:
        inputs, capabilities, digest = self.evaluate()

        self.assert_permits(capabilities, reduce_close=1, retry_open=1)
        self.assertEqual("c9-15w", inputs["execution_profile"])
        self.assertEqual(150_000.0, inputs["capital"])
        self.assertEqual("15w", inputs["capital_label"])
        self.assertTrue(
            stage927.verify_scope_evidence_digest(
                scope_evidence_inputs=inputs,
                scope_capabilities=capabilities,
                scope_evidence_digest=digest,
            )
        )

    def test_transient_shadow_divergence_is_reduce_only(self) -> None:
        _, capabilities, _ = self.evaluate(reconcile_passed=False)

        self.assert_permits(capabilities, reduce_close=1, retry_open=0)
        self.assertNotIn(
            "broker_shadow_reconcile_aligned",
            capabilities["reduce_close"]["required_checks"],  # type: ignore[index]
        )
        self.assertIn(
            "broker_shadow_reconcile_aligned",
            capabilities["retry_open"]["failed_checks"],  # type: ignore[index]
        )
        self.assertIn(
            "broker_shadow_reconcile_aligned",
            capabilities["initial_open"]["failed_checks"],  # type: ignore[index]
        )

    def test_initial_open_is_new_risk_but_does_not_need_current_ready_intent(self) -> None:
        _, capabilities, _ = self.evaluate()
        self.assertEqual(1, capabilities["initial_open"]["permitted"])
        self.assertNotIn(
            "controller_live_real_clean_ready",
            capabilities["initial_open"]["required_checks"],  # type: ignore[index]
        )
        self.assertIn(
            "broker_shadow_reconcile_aligned",
            capabilities["initial_open"]["required_checks"],  # type: ignore[index]
        )

        _, divergent, _ = self.evaluate(reconcile_passed=False)
        self.assertEqual(0, divergent["initial_open"]["permitted"])

    def test_ambiguous_no_ready_state_is_not_no_intents_idle(self) -> None:
        payloads = self.payloads()
        payloads["stage903"]["stage905_executor_status"] = "executor_no_ready_intents"

        _, capabilities, _ = self.evaluate(payloads=payloads)

        self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_exact_ready_controller_is_accepted(self) -> None:
        payloads = self.payloads()
        payloads["stage903"].update(
            {
                "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                "stage905_executor_status": "executor_dry_run_ready",
                "stage905_ready_count": 1,
            }
        )

        _, capabilities, _ = self.evaluate(payloads=payloads)

        self.assert_permits(capabilities, reduce_close=1, retry_open=1)

    def test_broker_snapshot_or_account_bundle_failure_blocks_both(self) -> None:
        cases = {
            "broker_snapshot_not_ready": ("stage906", "broker_snapshot_ready", 0),
            "snapshot_stale": ("stage906", "readonly_snapshot_age_seconds", 301.0),
            "active_broker_order": ("stage906", "active_broker_order_count", 1),
            "wrong_env_profile": ("stage903", "stage907_env_profile", "broker-test"),
            "bundle_incomplete": ("stage903", "stage907_broker_query_bundle_complete", 0),
            "readback_digest_mismatch": (
                "stage903",
                "stage907_stage174_stdout_summary_sha256",
                "b" * 64,
            ),
        }
        for name, (source, field, value) in cases.items():
            with self.subTest(name=name):
                payloads = self.payloads()
                payloads[source][field] = value
                _, capabilities, _ = self.evaluate(payloads=payloads)
                self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_wrong_current_identity_blocks_both(self) -> None:
        cases = {
            "old_evidence_version": (
                "stage912",
                "official_live_version",
                "official_live_stage847_c9_30w_stage819_05r_stop_retry_once",
            ),
            "wrong_target": ("stage906", "target_date", "2026-07-17"),
            "wrong_profile": ("stage903", "execution_profile", "stage372-20w"),
            "wrong_capital": ("stage903", "capital", 200_000.0),
            "wrong_capital_label": ("stage903", "capital_label", "20w"),
        }
        for name, (source, field, value) in cases.items():
            with self.subTest(name=name):
                payloads = self.payloads()
                payloads[source][field] = value
                _, capabilities, _ = self.evaluate(payloads=payloads)
                self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_missing_or_nonzero_order_api_evidence_blocks_both(self) -> None:
        for value in (None, 1, False):
            with self.subTest(value=value):
                payloads = self.payloads()
                if value is None:
                    payloads["stage910"].pop("order_api_called_count")
                else:
                    payloads["stage910"]["order_api_called_count"] = value
                _, capabilities, _ = self.evaluate(payloads=payloads)
                self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_every_long_lived_hard_gate_blocks_both(self) -> None:
        for check_name in (
            "profile_is_current_c9",
            "acceptance_suite_passed_fail_closed",
            "completion_audit_proven",
            "controller_not_killed_and_no_order_api",
            "health_alive",
            "static_order_boundary_passed",
            "scheduler_dynamic_target_ready",
            "no_unresolved_fail_closed_incident",
            "account_recovery_not_required",
            "account_recovery_ack_suite_passed",
            "aligned_idle_integration_passed",
            "kill_switch_inactive",
        ):
            with self.subTest(check_name=check_name):
                _, capabilities, _ = self.evaluate(
                    mutate_rows={check_name: 0}
                )
                self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_env_and_exact_confirm_are_scope_hard_gates(self) -> None:
        for env_enabled, confirm_ok in ((False, True), (True, False), (False, False)):
            with self.subTest(env_enabled=env_enabled, confirm_ok=confirm_ok):
                _, capabilities, _ = self.evaluate(
                    env_enabled=env_enabled,
                    confirm_ok=confirm_ok,
                )
                self.assert_permits(capabilities, reduce_close=0, retry_open=0)

    def test_digest_binds_inputs_capabilities_and_source_payloads(self) -> None:
        inputs, capabilities, digest = self.evaluate()
        tampered_inputs = copy.deepcopy(inputs)
        tampered_inputs["capital"] = 200_000.0
        self.assertFalse(
            stage927.verify_scope_evidence_digest(
                scope_evidence_inputs=tampered_inputs,
                scope_capabilities=capabilities,
                scope_evidence_digest=digest,
            )
        )
        tampered_capabilities = copy.deepcopy(capabilities)
        tampered_capabilities["retry_open"]["permitted"] = 0  # type: ignore[index]
        self.assertFalse(
            stage927.verify_scope_evidence_digest(
                scope_evidence_inputs=inputs,
                scope_capabilities=tampered_capabilities,
                scope_evidence_digest=digest,
            )
        )

        payloads = self.payloads()
        payloads["stage910"]["generated_at"] = "2026-07-18 21:00:01"
        changed_inputs, _, changed_digest = self.evaluate(payloads=payloads)
        self.assertNotEqual(
            inputs["source_evidence"]["stage910"]["payload_sha256"],  # type: ignore[index]
            changed_inputs["source_evidence"]["stage910"]["payload_sha256"],  # type: ignore[index]
        )
        self.assertNotEqual(digest, changed_digest)


if __name__ == "__main__":
    unittest.main()
