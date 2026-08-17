from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_authorization_lock import (  # noqa: E402
    SubmitAuthorizationLockBusyError,
    exclusive_submit_authorization_lock,
    shared_submit_authorization_lock,
    submit_authorization_lock,
    submit_authorization_lock_path,
)
from qmt_roll_official_live_submit_authorization import (  # noqa: E402
    SUBMIT_AUTHORIZATION_SCHEMA_VERSION,
    authorized_submit_intent_records,
    authorized_submit_intents,
    publish_submit_authorization,
    read_submit_authorization,
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
            "execution_profile": "stage372-20w",
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
            "execution_profile": "stage372-20w",
            "runtime_profile": "simnow",
            "order_scope": "test",
            "service_generation": "service-1",
            "connection_generation": "connection-1",
            "now_epoch_ns": 2_000_000_000,
        }
        values.update(overrides)
        return validate_submit_authorization(**values)

    def fast_row(self, *, scope: str = "reduce_close_only") -> dict[str, object]:
        close = scope == "reduce_close_only"
        return {
            "intent_id": "fast-close" if close else "fast-retry-open",
            "payload_sha256": "c" * 64 if close else "d" * 64,
            "intent_kind": "close" if close else "open",
            "vt_symbol": "jm2609.DCE",
            "source": (
                "stage904_c9_intraday_close"
                if close
                else "stage904_c9_intraday_retry_open"
            ),
            "intent_role": (
                "c9_initial_stop_close" if close else "c9_retry_open_once"
            ),
            "trace_id": "trace-fast-1",
            "spool_sequence": 17,
            "state_revision": 0,
            "state_generation": "position-epoch-1:3",
            "position_epoch_id": "position-epoch-1",
            "root_position_id": "root-position-1",
            "position_cycle_id": "position-cycle-1",
            "deadline_epoch_ns": 50_000_000_000,
        }

    def publish_fast(
        self,
        *,
        scope: str = "reduce_close_only",
        **overrides: object,
    ) -> dict[str, object]:
        permit_field = (
            "reduce_close_submit_permitted"
            if scope == "reduce_close_only"
            else "retry_open_submit_permitted"
        )
        values: dict[str, object] = {
            "authorization_lane": "persistent_intraday_fast",
            "intent_scope": scope,
            "authorized_intents": [self.fast_row(scope=scope)],
            "execution_profile": "c9-15w",
            "spool_path": Path(self.tmp.name) / "stage179-spool.sqlite3",
            "spool_snapshot_digest": "1" * 64,
            "cursor_digest": "2" * 64,
            "stage902_evidence_digest": "3" * 64,
            "stage927_evidence_digest": "4" * 64,
            "controller_evidence": {
                "target_date": "2026-07-18",
                "controller_status": "persistent_intraday_fast_ready",
                "expires_epoch_ns": 31_000_000_000,
            },
            "stage927_evidence": {
                permit_field: 1,
                "expires_epoch_ns": 31_000_000_000,
            },
            "tick_watermark_evidence": {
                "all_symbols_ready": 1,
                "candidate_symbol": "jm2609.DCE",
                "candidate_symbol_ready": 1,
                "candidate_ingress_epoch_ns": 2_000_000_000,
                "expires_epoch_ns": 31_000_000_000,
            },
        }
        values.update(overrides)
        return self.publish(**values)

    def fast_validate_values(
        self,
        *,
        scope: str = "reduce_close_only",
    ) -> dict[str, object]:
        row = self.fast_row(scope=scope)
        return {
            "execution_profile": "c9-15w",
            "authorization_lane": "persistent_intraday_fast",
            "intent_scope": scope,
            **row,
            "spool_path": Path(self.tmp.name) / "stage179-spool.sqlite3",
            "spool_snapshot_digest": "1" * 64,
            "cursor_digest": "2" * 64,
            "stage902_evidence_digest": "3" * 64,
            "stage927_evidence_digest": "4" * 64,
        }

    def initial_open_row(self) -> dict[str, object]:
        return {
            "intent_id": "stage901-initial-open",
            "payload_sha256": "9" * 64,
            "intent_kind": "open",
            "vt_symbol": "jm2609.DCE",
            "source": "stage901_pending_order",
            "intent_role": "c9_initial_open",
            "trace_id": "trace-initial-open-1",
            "spool_sequence": 19,
            "state_revision": 0,
            "state_generation": "initial-position-epoch:0",
            "position_epoch_id": "initial-position-epoch",
            "root_position_id": "initial-root-position",
            "position_cycle_id": "initial-position-cycle",
            "deadline_epoch_ns": 50_000_000_000,
        }

    def publish_initial_open(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "authorization_lane": "session_initial_open",
            "intent_scope": "initial_open_only",
            "authorized_intents": [self.initial_open_row()],
            "execution_profile": "c9-15w",
            "spool_path": Path(self.tmp.name) / "stage179-spool.sqlite3",
            "spool_snapshot_digest": "1" * 64,
            "cursor_digest": "2" * 64,
            "stage902_evidence_digest": "3" * 64,
            "stage927_evidence_digest": "4" * 64,
            "controller_evidence": {
                "target_date": "2026-07-18",
                "controller_status": "session_initial_open_prearmed_ready",
                "expires_epoch_ns": 31_000_000_000,
            },
            "stage927_evidence": {
                "initial_open_submit_permitted": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
            "tick_watermark_evidence": {
                "all_symbols_ready": 1,
                "candidate_symbol": "jm2609.DCE",
                "candidate_symbol_ready": 1,
                "candidate_ingress_epoch_ns": 2_000_000_000,
                "expires_epoch_ns": 31_000_000_000,
            },
        }
        values.update(overrides)
        return self.publish(**values)

    def initial_open_validate_values(self) -> dict[str, object]:
        return {
            "execution_profile": "c9-15w",
            "authorization_lane": "session_initial_open",
            "intent_scope": "initial_open_only",
            **self.initial_open_row(),
            "spool_path": Path(self.tmp.name) / "stage179-spool.sqlite3",
            "spool_snapshot_digest": "1" * 64,
            "cursor_digest": "2" * 64,
            "stage902_evidence_digest": "3" * 64,
            "stage927_evidence_digest": "4" * 64,
        }

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
        self.assertIn(
            "stage179_submit_authorization_execution_profile_mismatch",
            self.validate(execution_profile="c9-15w-historical"),
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

    def test_v3_artifact_is_rejected_even_with_a_valid_legacy_digest(self) -> None:
        payload = self.publish()
        payload["schema_version"] = 3
        body = {
            key: value for key, value in payload.items() if key != "record_digest"
        }
        payload["record_digest"] = hashlib.sha256(
            json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        self.assertEqual(5, SUBMIT_AUTHORIZATION_SCHEMA_VERSION)
        self.assertEqual({}, authorized_submit_intents(self.path))
        self.assertEqual([], authorized_submit_intent_records(self.path))
        blockers = self.validate()
        self.assertIn(
            "stage179_submit_authorization_schema_invalid",
            blockers,
        )
        self.assertNotIn(
            "stage179_submit_authorization_digest_mismatch",
            blockers,
        )

    def test_fast_lane_requires_scope_exact_row_and_all_bindings(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "fast_lane_scope_invalid",
        ):
            self.publish_fast(scope="all")
        with self.assertRaisesRegex(
            ValueError,
            "fast_lane_exact_identity_missing",
        ):
            self.publish_fast(
                authorized_intents=[
                    {
                        "intent_id": "incomplete",
                        "payload_sha256": "a" * 64,
                        "intent_kind": "close",
                    }
                ]
            )
        row = self.fast_row()
        second = dict(row)
        second["intent_id"] = "fast-close-2"
        second["payload_sha256"] = "e" * 64
        second["spool_sequence"] = 18
        with self.assertRaisesRegex(
            ValueError,
            "fast_lane_exactly_one_intent_required",
        ):
            self.publish_fast(authorized_intents=[row, second])
        with self.assertRaisesRegex(
            ValueError,
            "fast_lane_binding_digest_missing",
        ):
            self.publish_fast(cursor_digest="")
        wrong_role = dict(row)
        wrong_role["intent_role"] = "c9_retry_open_once"
        with self.assertRaisesRegex(
            ValueError,
            "fast_close_source_role_invalid",
        ):
            self.publish_fast(authorized_intents=[wrong_role])

    def test_fast_close_authorization_binds_every_exact_field(self) -> None:
        payload = self.publish_fast()
        expected = self.fast_validate_values()

        self.assertEqual([], self.validate(**expected))
        records = authorized_submit_intent_records(self.path)
        self.assertEqual([self.fast_row()], records)
        self.assertEqual(
            {"fast-close": "c" * 64},
            authorized_submit_intents(self.path),
        )
        self.assertEqual(
            str((Path(self.tmp.name) / "stage179-spool.sqlite3").resolve()),
            payload["spool_path"],
        )

        mismatch_cases: dict[str, object] = {
            "source": "stage901_pending_order",
            "intent_role": "c9_retry_open_once",
            "trace_id": "trace-other",
            "spool_sequence": 18,
            "state_revision": 1,
            "state_generation": "position-epoch-1:4",
            "position_epoch_id": "position-epoch-2",
            "root_position_id": "root-position-2",
            "position_cycle_id": "position-cycle-2",
            "deadline_epoch_ns": 49_000_000_000,
            "spool_snapshot_digest": "5" * 64,
            "cursor_digest": "6" * 64,
            "stage902_evidence_digest": "7" * 64,
            "stage927_evidence_digest": "8" * 64,
            "spool_path": Path(self.tmp.name) / "other.sqlite3",
        }
        for field_name, wrong_value in mismatch_cases.items():
            with self.subTest(field_name=field_name):
                blockers = self.validate(**(expected | {field_name: wrong_value}))
                self.assertTrue(
                    any("mismatch" in blocker for blocker in blockers),
                    blockers,
                )

    def test_fast_retry_open_uses_scope_specific_controller_and_stage927(self) -> None:
        self.publish_fast(scope="retry_open_only")
        expected = self.fast_validate_values(scope="retry_open_only")

        self.assertEqual([], self.validate(**expected, child_offset="open"))
        self.assertIn(
            "stage179_submit_authorization_retry_open_only",
            self.validate(**expected, child_offset="close"),
        )

        self.publish_fast(
            scope="retry_open_only",
            controller_evidence={
                "target_date": "2026-07-18",
                "controller_status": (
                    "phase_d_controller_live_real_ready_no_submit_step"
                ),
                "expires_epoch_ns": 31_000_000_000,
            },
            stage927_evidence={
                "real_submit_permitted": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
        )
        blockers = self.validate(**expected)
        self.assertIn(
            "stage179_submit_authorization_fast_controller_not_ready",
            blockers,
        )
        self.assertIn(
            "stage179_submit_authorization_stage927_"
            "retry_open_submit_permitted_not_ready",
            blockers,
        )

    def test_initial_open_has_independent_exact_prearmed_lane(self) -> None:
        payload = self.publish_initial_open()
        row = self.initial_open_row()
        expected = {
            "execution_profile": "c9-15w",
            "authorization_lane": "session_initial_open",
            "intent_scope": "initial_open_only",
            **row,
            "spool_path": Path(self.tmp.name) / "stage179-spool.sqlite3",
            "spool_snapshot_digest": "1" * 64,
            "cursor_digest": "2" * 64,
            "stage902_evidence_digest": "3" * 64,
            "stage927_evidence_digest": "4" * 64,
        }

        self.assertEqual([], self.validate(**expected, child_offset="open"))
        self.assertEqual("session_initial_open", payload["authorization_lane"])
        self.assertIn(
            "stage179_submit_authorization_initial_open_only",
            self.validate(**expected, child_offset="close"),
        )

        wrong_role = dict(row)
        wrong_role["intent_role"] = "c9_retry_open_once"
        with self.assertRaisesRegex(ValueError, "initial_open_source_role_invalid"):
            self.publish_initial_open(authorized_intents=[wrong_role])

        self.publish_initial_open(
            controller_evidence={
                "target_date": "2026-07-18",
                "controller_status": "persistent_intraday_fast_ready",
                "expires_epoch_ns": 31_000_000_000,
            },
            stage927_evidence={
                "initial_open_submit_permitted": 0,
                "expires_epoch_ns": 31_000_000_000,
            },
            tick_watermark_evidence={
                "all_symbols_ready": 0,
                "expires_epoch_ns": 31_000_000_000,
            },
        )
        blockers = self.validate(**expected)
        self.assertIn(
            "stage179_submit_authorization_initial_open_controller_not_ready",
            blockers,
        )
        self.assertIn(
            "stage179_submit_authorization_stage927_"
            "initial_open_submit_permitted_not_ready",
            blockers,
        )
        self.assertIn(
            "stage179_submit_authorization_tick_gate_not_ready",
            blockers,
        )

    def test_pinned_digest_waives_only_admission_expiry(self) -> None:
        payload = self.publish_fast(
            expires_epoch_ns=3_000_000_000,
            controller_evidence={
                "target_date": "2026-07-18",
                "controller_status": "persistent_intraday_fast_ready",
                "expires_epoch_ns": 3_000_000_000,
            },
            stage927_evidence={
                "reduce_close_submit_permitted": 1,
                "expires_epoch_ns": 3_000_000_000,
            },
            broker_gate_evidence={
                "status": "ready",
                "service_generation": "service-1",
                "connection_generation": "connection-1",
                "expires_epoch_ns": 3_000_000_000,
            },
        )
        expected = self.fast_validate_values()
        self.assertIn(
            "stage179_submit_authorization_expired",
            self.validate(**expected, now_epoch_ns=4_000_000_000),
        )
        pinned = self.validate(
            **expected,
            now_epoch_ns=4_000_000_000,
            allow_expired_if_record_digest=str(payload["record_digest"]),
        )
        self.assertEqual([], pinned)
        wrong_pin = self.validate(
            **expected,
            now_epoch_ns=4_000_000_000,
            allow_expired_if_record_digest="f" * 64,
        )
        self.assertIn(
            "stage179_submit_authorization_pinned_record_digest_mismatch",
            wrong_pin,
        )
        deadline_blockers = self.validate(
            **expected,
            now_epoch_ns=50_000_000_000,
            allow_expired_if_record_digest=str(payload["record_digest"]),
        )
        self.assertIn(
            "stage179_submit_authorization_intent_deadline_expired",
            deadline_blockers,
        )

    def test_initial_open_accepts_exact_candidate_tick_evidence(self) -> None:
        expected = self.initial_open_validate_values()
        self.publish_initial_open(
            tick_watermark_evidence={
                "all_symbols_ready": 0,
                "candidate_symbol": "jm2609.DCE",
                "candidate_symbol_ready": 1,
                "candidate_ingress_epoch_ns": 2_000_000_000,
                "expires_epoch_ns": 31_000_000_000,
            },
        )

        blockers = self.validate(**expected)

        self.assertNotIn(
            "stage179_submit_authorization_tick_gate_not_ready",
            blockers,
        )

    def test_initial_open_rejects_incomplete_candidate_tick_evidence(self) -> None:
        expected = self.initial_open_validate_values()
        self.publish_initial_open(
            tick_watermark_evidence={
                "all_symbols_ready": 0,
                "candidate_symbol": "jm2609.DCE",
                "candidate_symbol_ready": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
        )

        blockers = self.validate(**expected)

        self.assertIn(
            "stage179_submit_authorization_tick_gate_not_ready",
            blockers,
        )

    def test_initial_open_rejects_tick_evidence_for_wrong_symbol(self) -> None:
        expected = self.initial_open_validate_values()
        self.publish_initial_open(
            tick_watermark_evidence={
                "all_symbols_ready": 0,
                "candidate_symbol": "AP610.CZCE",
                "candidate_symbol_ready": 1,
                "candidate_ingress_epoch_ns": 2_000_000_000,
                "expires_epoch_ns": 31_000_000_000,
            },
        )

        blockers = self.validate(**expected)

        self.assertIn(
            "stage179_submit_authorization_tick_candidate_symbol_mismatch",
            blockers,
        )

    def test_initial_open_does_not_fallback_to_global_tick_readiness(self) -> None:
        expected = self.initial_open_validate_values()
        self.publish_initial_open(
            tick_watermark_evidence={
                "all_symbols_ready": 1,
                "expires_epoch_ns": 31_000_000_000,
            },
        )

        blockers = self.validate(**expected)

        self.assertIn(
            "stage179_submit_authorization_tick_gate_not_ready",
            blockers,
        )

    def test_v4_digest_covers_new_lane_spool_and_exact_record_fields(self) -> None:
        self.publish_fast()
        payload = read_submit_authorization(self.path)
        payload["spool_snapshot_digest"] = "9" * 64
        payload["authorized_intents"][0]["state_revision"] = 99
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        self.assertEqual({}, authorized_submit_intents(self.path))
        self.assertEqual([], authorized_submit_intent_records(self.path))
        self.assertIn(
            "stage179_submit_authorization_digest_mismatch",
            self.validate(**self.fast_validate_values()),
        )

    def test_malformed_v4_times_fail_closed_without_raising(self) -> None:
        payload = self.publish_fast()
        payload["expires_epoch_ns"] = "not-an-integer"
        payload["controller_evidence"]["expires_epoch_ns"] = True
        body = {
            key: value for key, value in payload.items() if key != "record_digest"
        }
        payload["record_digest"] = hashlib.sha256(
            json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        blockers = self.validate(**self.fast_validate_values())
        self.assertIn(
            "stage179_submit_authorization_expiry_invalid",
            blockers,
        )
        self.assertIn(
            "stage179_submit_authorization_controller_evidence_expiry_missing",
            blockers,
        )

    def test_shared_and_exclusive_authorization_locks_exclude_correctly(self) -> None:
        lock_path = submit_authorization_lock_path(self.tmp.name)
        self.assertEqual(
            Path(self.tmp.name).resolve()
            / "stage179_submit_authorization.lock",
            lock_path,
        )
        with shared_submit_authorization_lock(lock_path):
            with shared_submit_authorization_lock(lock_path, blocking=False):
                pass
            with self.assertRaises(SubmitAuthorizationLockBusyError):
                with exclusive_submit_authorization_lock(
                    lock_path,
                    blocking=False,
                ):
                    self.fail("exclusive lock unexpectedly acquired")
        with exclusive_submit_authorization_lock(lock_path):
            with self.assertRaises(SubmitAuthorizationLockBusyError):
                with shared_submit_authorization_lock(
                    lock_path,
                    blocking=False,
                ):
                    self.fail("shared lock unexpectedly acquired")

    def test_authorization_lock_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "stage179_submit_authorization_lock_mode_invalid",
        ):
            with submit_authorization_lock(
                Path(self.tmp.name) / "bad.lock",
                mode="bad",  # type: ignore[arg-type]
            ):
                self.fail("invalid lock mode unexpectedly acquired")


if __name__ == "__main__":
    unittest.main()
