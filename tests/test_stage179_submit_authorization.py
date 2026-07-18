from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_submit_authorization import (  # noqa: E402
    authorized_submit_intents,
    publish_submit_authorization,
    revoke_submit_authorization,
    validate_submit_authorization,
)


class Stage179SubmitAuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "submit-authorization.json"

    def publish(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "path": self.path,
            "target_date": "2026-07-18",
            "runtime_profile": "simnow",
            "order_scope": "test",
            "service_generation": "service-1",
            "connection_generation": "connection-1",
            "cycle_id": "cycle-1",
            "intent_scope": "all",
            "authorized_intents": [
                {
                    "intent_id": "intent-approved",
                    "payload_sha256": "a" * 64,
                    "intent_kind": "open",
                }
            ],
            "issued_epoch_ns": 1_000_000_000,
            "expires_epoch_ns": 31_000_000_000,
            "controller_evidence": {
                "target_date": "2026-07-18",
                "controller_status": "phase_d_controller_live_real_ready_no_submit_step",
                "stage905_executor_status": "executor_dry_run_ready",
                "stage905_blocked_count": 0,
                "stage905_ready_count": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
            "stage927_evidence": {
                "real_submit_permitted": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
            "broker_gate_evidence": {
                "status": "ready",
                "service_generation": "service-1",
                "connection_generation": "connection-1",
                "expires_epoch_ns": 31_000_000_000,
            },
            "tick_watermark_evidence": {
                "all_symbols_ready": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
        }
        values.update(overrides)
        return publish_submit_authorization(**values)

    def validate(self, **overrides: object) -> list[str]:
        values: dict[str, object] = {
            "path": self.path,
            "target_date": "2026-07-18",
            "runtime_profile": "simnow",
            "order_scope": "test",
            "service_generation": "service-1",
            "connection_generation": "connection-1",
            "now_epoch_ns": 2_000_000_000,
        }
        values.update(overrides)
        return validate_submit_authorization(**values)

    def test_authorization_is_target_profile_and_connection_bound(self) -> None:
        payload = self.publish()

        self.assertEqual([], self.validate())
        self.assertEqual(64, len(str(payload["record_digest"])))
        self.assertIn(
            "stage179_submit_authorization_target_date_mismatch",
            self.validate(target_date="2026-07-19"),
        )
        self.assertIn(
            "stage179_submit_authorization_connection_generation_mismatch",
            self.validate(connection_generation="connection-2"),
        )

    def test_authorization_binds_exact_intent_and_payload_identity(self) -> None:
        self.publish()

        self.assertEqual(
            [],
            self.validate(
                intent_id="intent-approved",
                payload_sha256="a" * 64,
                intent_kind="open",
            ),
        )
        self.assertIn(
            "stage179_submit_authorization_intent_not_authorized",
            self.validate(
                intent_id="post-publish-new-intent",
                payload_sha256="b" * 64,
                intent_kind="open",
            ),
        )
        self.assertIn(
            "stage179_submit_authorization_payload_sha256_mismatch",
            self.validate(
                intent_id="intent-approved",
                payload_sha256="b" * 64,
                intent_kind="open",
            ),
        )
        self.assertEqual(
            {"intent-approved": "a" * 64},
            authorized_submit_intents(self.path),
        )

    def test_authorized_intent_set_rejects_duplicates_and_malformed_hashes(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "stage179_submit_authorization_authorized_intent_duplicate",
        ):
            self.publish(
                authorized_intents=[
                    {
                        "intent_id": "same",
                        "payload_sha256": "a" * 64,
                        "intent_kind": "open",
                    },
                    {
                        "intent_id": "same",
                        "payload_sha256": "a" * 64,
                        "intent_kind": "open",
                    },
                ]
            )
        with self.assertRaisesRegex(
            ValueError,
            "stage179_submit_authorization_payload_sha256_invalid",
        ):
            self.publish(
                authorized_intents=[
                    {
                        "intent_id": "bad",
                        "payload_sha256": "not-a-sha",
                        "intent_kind": "open",
                    }
                ]
            )

    def test_broker_readiness_expiry_is_a_hard_upper_bound(self) -> None:
        self.publish(
            expires_epoch_ns=40_000_000_000,
            broker_gate_evidence={
                "status": "ready",
                "service_generation": "service-1",
                "connection_generation": "connection-1",
                "expires_epoch_ns": 31_000_000_000,
            },
        )

        self.assertIn(
            "stage179_submit_authorization_exceeds_broker_readiness_expiry",
            self.validate(now_epoch_ns=2_000_000_000),
        )
        self.assertIn(
            "stage179_submit_authorization_broker_readiness_expired",
            self.validate(now_epoch_ns=31_000_000_000),
        )

    def test_controller_stage927_and_tick_evidence_each_expire(self) -> None:
        for evidence_name, blocker_prefix in (
            ("controller_evidence", "controller_evidence"),
            ("stage927_evidence", "stage927_evidence"),
            ("tick_watermark_evidence", "tick_watermark_evidence"),
        ):
            with self.subTest(evidence_name=evidence_name):
                base = self.publish()
                evidence = dict(base[evidence_name])
                evidence["expires_epoch_ns"] = 1_500_000_000
                self.publish(
                    **{
                        evidence_name: evidence,
                    }
                )
                blockers = self.validate(now_epoch_ns=2_000_000_000)
                self.assertIn(
                    "stage179_submit_authorization_"
                    f"{blocker_prefix}_expired",
                    blockers,
                )

    def test_expiry_revoke_and_tamper_fail_closed(self) -> None:
        self.publish()
        self.assertIn(
            "stage179_submit_authorization_expired",
            self.validate(now_epoch_ns=31_000_000_000),
        )

        revoke_submit_authorization(
            self.path,
            reason="stage930_cycle_blocked",
            revoked_epoch_ns=3_000_000_000,
        )
        self.assertIn(
            "stage179_submit_authorization_not_authorized",
            self.validate(),
        )

        self.publish()
        text = self.path.read_text(encoding="utf-8")
        self.path.write_text(text.replace('"cycle-1"', '"cycle-x"'), encoding="utf-8")
        self.assertIn(
            "stage179_submit_authorization_digest_mismatch",
            self.validate(),
        )

    def test_reduce_close_scope_blocks_open_at_lease_and_child_send(self) -> None:
        self.publish(
            intent_scope="reduce_close_only",
            authorized_intents=[
                {
                    "intent_id": "intent-approved-close",
                    "payload_sha256": "c" * 64,
                    "intent_kind": "close",
                }
            ],
        )

        self.assertIn(
            "stage179_submit_authorization_reduce_close_only",
            self.validate(intent_kind="open"),
        )
        self.assertEqual([], self.validate(intent_kind="close"))
        self.assertIn(
            "stage179_submit_authorization_reduce_close_only",
            self.validate(intent_kind="close", child_offset="open"),
        )
        self.assertEqual(
            [],
            self.validate(intent_kind="close", child_offset="close"),
        )


if __name__ == "__main__":
    unittest.main()
