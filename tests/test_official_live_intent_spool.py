from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_tick_types import DurableTickCursor
from qmt_roll_official_live_time import utc_iso_from_epoch_ns
from qmt_roll_official_live_trace import ClockStamp, LatencyTrace, TRACE_DEADLINE_NS
import qmt_roll_official_live_intent_spool as spool


class _Clock:
    def __init__(self, *, epoch_ns: int, monotonic_ns: int, domain: str = "boot-a") -> None:
        self._epoch_ns = epoch_ns
        self._monotonic_ns = monotonic_ns
        self._domain = domain

    def epoch_ns(self) -> int:
        return self._epoch_ns

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def clock_domain_id(self) -> str:
        return self._domain


class OfficialLiveIntentSpoolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.path = Path(self.tempdir.name) / "intent-spool.sqlite3"
        self.connection = spool.open_spool(self.path)
        self.addCleanup(self.connection.close)

    def cursor(self, sequence: int, offset: int | None = None) -> DurableTickCursor:
        return DurableTickCursor(
            feed_session_id="feed-a",
            ingress_sequence=sequence,
            journal_byte_offset=offset if offset is not None else sequence * 100,
        )

    def intent(
        self,
        label: str,
        *,
        offset: str = "open",
        deadline_epoch_ns: int = TRACE_DEADLINE_NS + 100,
        executor_status: str = "dry_run_order_request_payload_ready",
    ) -> dict[str, object]:
        ingress_epoch_ns = deadline_epoch_ns - TRACE_DEADLINE_NS
        if ingress_epoch_ns < 0:
            raise ValueError("deadline_before_trace_window")
        ingress_monotonic_ns = ingress_epoch_ns
        clock = _Clock(
            epoch_ns=ingress_epoch_ns,
            monotonic_ns=ingress_monotonic_ns,
        )
        trace = LatencyTrace.from_ingress_row(
            {
                "feed_session_id": "feed-a",
                "ingress_sequence": 1,
                "symbol_sequence": 1,
                "ingress_epoch_ns": ingress_epoch_ns,
                "ingress_monotonic_ns": ingress_monotonic_ns,
                "clock_domain_id": "boot-a",
                "received_at_utc": utc_iso_from_epoch_ns(ingress_epoch_ns),
                "trace_id": "stage179-tick/feed-a/1",
                "vt_symbol": "JM609.DCE",
            },
            clock=clock,
        )
        trace = trace.record_stamp(
            "stage904_detected",
            ClockStamp(
                epoch_ns=ingress_epoch_ns,
                monotonic_ns=ingress_monotonic_ns,
                clock_domain_id="boot-a",
                utc_iso=utc_iso_from_epoch_ns(ingress_epoch_ns),
            ),
        ).record_stamp(
            "stage905_intent_ready",
            ClockStamp(
                epoch_ns=ingress_epoch_ns + 1,
                monotonic_ns=ingress_monotonic_ns + 1,
                clock_domain_id="boot-a",
                utc_iso=utc_iso_from_epoch_ns(ingress_epoch_ns + 1),
            ),
        )
        business_payload = {
            "intent_id": label,
            "trace_id": trace.trace_id,
            "target_date": "2026-07-16",
            "source": (
                "stage904_c9_intraday_close"
                if offset == "close"
                else "stage904_c9_intraday_retry_open"
            ),
            "offset": offset,
            "executor_status": executor_status,
            "deadline_epoch_ns": trace.deadline_epoch_ns,
            "deadline_monotonic_ns": trace.deadline_monotonic_ns,
            "state_generation": f"epoch-{label}:1",
            "position_epoch_id": f"epoch-{label}",
            "vt_symbol": "JM609.DCE",
            "planned_volume": 1,
            "limit_price": 1245.5,
            "source_feed_session_id": trace.feed_session_id,
            "source_ingress_sequence": trace.ingress_sequence,
            "source_symbol_sequence": trace.symbol_sequence,
            "durable_cursor_feed_session_id": "feed-a",
            "durable_cursor_ingress_sequence": 1,
            "durable_cursor_journal_byte_offset": 100,
            "durable_cursor_journal_schema": "stage179_framed_v1",
        }
        spool_payload_json = json.dumps(
            business_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return {
            **business_payload,
            "trace_json": trace.to_json(),
            "spool_payload_json": spool_payload_json,
            "payload_sha256": hashlib.sha256(
                spool_payload_json.encode("utf-8")
            ).hexdigest(),
        }

    def commit(
        self,
        intents: list[dict[str, object]],
        *,
        expected: DurableTickCursor | None = None,
        next_cursor: DurableTickCursor | None = None,
        connection: object | None = None,
        stamp_spool: bool = True,
    ) -> object:
        result = spool.commit_detector_batch(
            self.connection if connection is None else connection,
            consumer_id="stage941",
            expected_cursor=expected,
            next_cursor=next_cursor or self.cursor(1),
            intents=intents,
            now_epoch_ns=102,
            now_monotonic_ns=102,
            clock_domain_id="boot-a",
        )
        if stamp_spool:
            for intent in intents:
                spool.record_trace_observation(
                    self.connection if connection is None else connection,
                    intent_id=str(intent["intent_id"]),
                    stage="spool_committed",
                    epoch_ns=102,
                    monotonic_ns=102,
                    clock_domain_id="boot-a",
                )
        return result

    def test_open_spool_enforces_wal_full_and_schema_v1(self) -> None:
        self.assertEqual(
            "wal",
            self.connection.execute("PRAGMA journal_mode").fetchone()[0].lower(),
        )
        self.assertEqual(2, self.connection.execute("PRAGMA synchronous").fetchone()[0])
        self.assertEqual(1, self.connection.execute("PRAGMA foreign_keys").fetchone()[0])
        self.assertEqual(100, self.connection.execute("PRAGMA busy_timeout").fetchone()[0])
        meta = dict(self.connection.execute("SELECT key, value FROM spool_meta"))
        self.assertEqual("1", meta["schema_version"])
        self.assertTrue(meta["spool_uuid"])
        self.assertEqual(1, self.connection.execute("PRAGMA user_version").fetchone()[0])

    def test_existing_schema_v1_rejects_index_contract_tamper(self) -> None:
        self.connection.execute("DROP INDEX intents_claim_idx")
        self.connection.close()

        with self.assertRaisesRegex(
            spool.SpoolValidationError,
            "existing_schema_fingerprint_mismatch",
        ):
            spool.open_spool(self.path)

    def test_commit_batch_atomically_inserts_intents_and_advances_cursor(self) -> None:
        next_cursor = self.cursor(1)

        result = self.commit([self.intent("open-1")], next_cursor=next_cursor)

        self.assertEqual(1, result.inserted_count)
        self.assertEqual(
            next_cursor,
            spool.read_detector_cursor(self.connection, consumer_id="stage941"),
        )
        self.assertEqual(1, spool.spool_counts(self.connection)["ready"])

    def test_invalid_second_intent_rolls_back_first_insert_and_cursor(self) -> None:
        invalid = self.intent("bad")
        invalid["payload_sha256"] = "not-a-sha"

        with self.assertRaises(spool.SpoolValidationError):
            self.commit([self.intent("open-1"), invalid])

        self.assertEqual(0, spool.spool_counts(self.connection)["total"])
        self.assertIsNone(
            spool.read_detector_cursor(self.connection, consumer_id="stage941")
        )

    def test_outer_dataframe_nan_does_not_override_canonical_business_payload(self) -> None:
        intent = self.intent("open-1")
        intent["unrelated_dataframe_column"] = float("nan")

        result = self.commit([intent])

        self.assertEqual(1, result.inserted_count)

    def test_state_generation_must_bind_position_epoch_canonically(self) -> None:
        intent = self.intent("open-1")
        business = json.loads(intent["spool_payload_json"])
        business["state_generation"] = "different-epoch:01"
        intent["spool_payload_json"] = json.dumps(
            business,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        intent["payload_sha256"] = hashlib.sha256(
            intent["spool_payload_json"].encode("utf-8")
        ).hexdigest()

        with self.assertRaises(spool.SpoolValidationError):
            self.commit([intent])

        self.assertEqual(0, spool.spool_counts(self.connection)["total"])

    def test_same_id_mismatch_rolls_back_cursor_but_exact_replay_is_idempotent(self) -> None:
        first_cursor = self.cursor(1)
        second_cursor = self.cursor(2)
        original = self.intent("open-1")
        self.commit([original], next_cursor=first_cursor)

        replay = self.commit(
            [dict(original)],
            expected=first_cursor,
            next_cursor=second_cursor,
        )
        self.assertEqual(0, replay.inserted_count)
        self.assertEqual(second_cursor, spool.read_detector_cursor(self.connection, consumer_id="stage941"))

        conflicting = dict(original)
        changed_payload = json.loads(conflicting["spool_payload_json"])
        changed_payload["planned_volume"] = 2
        conflicting["spool_payload_json"] = json.dumps(
            changed_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        conflicting["payload_sha256"] = hashlib.sha256(
            conflicting["spool_payload_json"].encode("utf-8")
        ).hexdigest()
        third_cursor = self.cursor(3)
        with self.assertRaises(spool.SpoolConflictError):
            self.commit(
                [conflicting],
                expected=second_cursor,
                next_cursor=third_cursor,
            )
        self.assertEqual(second_cursor, spool.read_detector_cursor(self.connection, consumer_id="stage941"))

    def test_lost_ack_replay_is_idempotent_and_cannot_insert_new_intent(self) -> None:
        first_cursor = self.cursor(1)
        original = self.intent("open-1")
        self.commit([original], next_cursor=first_cursor)

        replay = self.commit(
            [dict(original)],
            expected=None,
            next_cursor=first_cursor,
        )
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(1, replay.idempotent_count)

        with self.assertRaises(spool.DetectorCursorConflictError):
            self.commit(
                [self.intent("open-2")],
                expected=None,
                next_cursor=first_cursor,
            )
        self.assertEqual(1, spool.spool_counts(self.connection)["total"])

    def test_lost_ack_replay_rejects_truncated_batch_manifest(self) -> None:
        first_cursor = self.cursor(1)
        first = self.intent("open-1")
        second = self.intent("open-2")
        self.commit([first, second], next_cursor=first_cursor)

        with self.assertRaises(spool.DetectorCursorConflictError):
            self.commit(
                [dict(first)],
                expected=None,
                next_cursor=first_cursor,
            )

        self.assertEqual(2, spool.spool_counts(self.connection)["total"])

    def test_lost_ack_replay_reuses_first_stage905_observation(self) -> None:
        cursor = self.cursor(1)
        original = self.intent("open-1")
        self.commit([original], next_cursor=cursor)
        replay = dict(original)
        replay_trace = json.loads(replay["trace_json"])
        replay_trace["stamps"]["stage905_intent_ready"] = {
            "epoch_ns": 102,
            "monotonic_ns": 102,
            "clock_domain_id": "boot-a",
            "utc_iso": utc_iso_from_epoch_ns(102),
        }
        replay["trace_json"] = json.dumps(
            replay_trace,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        result = self.commit(
            [replay],
            expected=None,
            next_cursor=cursor,
        )

        self.assertTrue(result.idempotent_replay)
        observations = spool.read_trace_observations(
            self.connection,
            intent_id="open-1",
        )
        self.assertEqual(101, observations["stage905_intent_ready"].epoch_ns)

    def test_cursor_compare_and_swap_rejects_stale_expected_cursor(self) -> None:
        first_cursor = self.cursor(1)
        self.commit([], next_cursor=first_cursor)

        with self.assertRaises(spool.DetectorCursorConflictError):
            self.commit(
                [self.intent("open-1")],
                expected=None,
                next_cursor=self.cursor(2),
            )

        self.assertEqual(first_cursor, spool.read_detector_cursor(self.connection, consumer_id="stage941"))
        self.assertEqual(0, spool.spool_counts(self.connection)["total"])

    def test_cursor_requires_strict_sequence_and_offset_progress(self) -> None:
        first_cursor = self.cursor(1)
        self.commit([], next_cursor=first_cursor)

        for invalid_next in (
            self.cursor(1, offset=200),
            self.cursor(2, offset=100),
        ):
            with self.subTest(invalid_next=invalid_next):
                with self.assertRaises(spool.DetectorCursorConflictError):
                    self.commit(
                        [],
                        expected=first_cursor,
                        next_cursor=invalid_next,
                    )

        self.assertEqual(
            first_cursor,
            spool.read_detector_cursor(self.connection, consumer_id="stage941"),
        )

    def test_clean_feed_rollover_cas_succeeds_once(self) -> None:
        old_cursor = self.cursor(1)
        new_cursor = DurableTickCursor(
            feed_session_id="feed-b",
            ingress_sequence=1,
            journal_byte_offset=120,
        )
        self.commit([], next_cursor=old_cursor)
        evidence = spool.DetectorFeedRolloverEvidence(
            previous_cursor=old_cursor,
            previous_journal_segment_path="/tmp/feed-a.ndjson",
            previous_heartbeat_revision_uuid="heartbeat-a-terminal",
            previous_clean_shutdown=True,
            recovery_previous_durable_cursor=old_cursor,
            prior_uncommitted_gap_count=0,
            new_feed_session_id="feed-b",
            new_journal_segment_path="/tmp/feed-b.ndjson",
            new_heartbeat_revision_uuid="heartbeat-b-running",
        )

        first = spool.commit_detector_batch(
            self.connection,
            consumer_id="stage941",
            expected_cursor=old_cursor,
            next_cursor=new_cursor,
            intents=[],
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            feed_rollover_evidence=evidence,
        )
        replay = spool.commit_detector_batch(
            self.connection,
            consumer_id="stage941",
            expected_cursor=old_cursor,
            next_cursor=new_cursor,
            intents=[],
            now_epoch_ns=201,
            now_monotonic_ns=201,
            clock_domain_id="boot-a",
            feed_rollover_evidence=evidence,
        )

        self.assertEqual(new_cursor, first.cursor)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(
            1,
            self.connection.execute(
                "SELECT COUNT(*) FROM detector_feed_rollovers"
            ).fetchone()[0],
        )

    def test_feed_rollover_requires_caught_up_clean_gap_free_lineage(self) -> None:
        old_cursor = self.cursor(1)
        new_cursor = DurableTickCursor(
            feed_session_id="feed-b",
            ingress_sequence=1,
            journal_byte_offset=120,
        )
        self.commit([], next_cursor=old_cursor)
        invalid_evidence = (
            spool.DetectorFeedRolloverEvidence(
                previous_cursor=old_cursor,
                previous_journal_segment_path="/tmp/feed-a.ndjson",
                previous_heartbeat_revision_uuid="heartbeat-a-terminal",
                previous_clean_shutdown=False,
                recovery_previous_durable_cursor=old_cursor,
                prior_uncommitted_gap_count=0,
                new_feed_session_id="feed-b",
                new_journal_segment_path="/tmp/feed-b.ndjson",
                new_heartbeat_revision_uuid="heartbeat-b-running",
            ),
            spool.DetectorFeedRolloverEvidence(
                previous_cursor=old_cursor,
                previous_journal_segment_path="/tmp/feed-a.ndjson",
                previous_heartbeat_revision_uuid="heartbeat-a-terminal",
                previous_clean_shutdown=True,
                recovery_previous_durable_cursor=self.cursor(2),
                prior_uncommitted_gap_count=0,
                new_feed_session_id="feed-b",
                new_journal_segment_path="/tmp/feed-b.ndjson",
                new_heartbeat_revision_uuid="heartbeat-b-running",
            ),
            spool.DetectorFeedRolloverEvidence(
                previous_cursor=old_cursor,
                previous_journal_segment_path="/tmp/feed-a.ndjson",
                previous_heartbeat_revision_uuid="heartbeat-a-terminal",
                previous_clean_shutdown=True,
                recovery_previous_durable_cursor=old_cursor,
                prior_uncommitted_gap_count=1,
                new_feed_session_id="feed-b",
                new_journal_segment_path="/tmp/feed-b.ndjson",
                new_heartbeat_revision_uuid="heartbeat-b-running",
            ),
        )

        for evidence in invalid_evidence:
            with self.subTest(evidence=evidence):
                with self.assertRaises(spool.DetectorCursorConflictError):
                    spool.commit_detector_batch(
                        self.connection,
                        consumer_id="stage941",
                        expected_cursor=old_cursor,
                        next_cursor=new_cursor,
                        intents=[],
                        now_epoch_ns=200,
                        now_monotonic_ns=200,
                        clock_domain_id="boot-a",
                        feed_rollover_evidence=evidence,
                    )

        self.assertEqual(
            old_cursor,
            spool.read_detector_cursor(self.connection, consumer_id="stage941"),
        )

    def test_batch_cursor_must_cover_every_intent_durable_cursor(self) -> None:
        intent = self.intent("open-1")
        business = json.loads(intent["spool_payload_json"])
        business["durable_cursor_ingress_sequence"] = 2
        business["durable_cursor_journal_byte_offset"] = 200
        intent["spool_payload_json"] = json.dumps(
            business,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        intent["payload_sha256"] = hashlib.sha256(
            intent["spool_payload_json"].encode("utf-8")
        ).hexdigest()

        with self.assertRaises(spool.DetectorCursorConflictError):
            self.commit([intent], next_cursor=self.cursor(1))

        self.assertIsNone(
            spool.read_detector_cursor(self.connection, consumer_id="stage941")
        )

    def test_newer_close_is_leased_before_older_open_and_blocks_next_open(self) -> None:
        first_cursor = self.cursor(1)
        self.commit([self.intent("open-1")], next_cursor=first_cursor)
        self.commit(
            [self.intent("close-1", offset="close")],
            expected=first_cursor,
            next_cursor=self.cursor(2),
        )

        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=5,
        )
        self.assertIsNotNone(lease)
        self.assertEqual("close-1", lease.intent.intent_id)
        self.assertEqual(0, lease.intent.priority)
        self.assertIsNone(
            spool.lease_next(
                self.connection,
                owner_id="executor-b",
                now_epoch_ns=201,
                now_monotonic_ns=201,
                clock_domain_id="boot-a",
                lease_seconds=5,
            )
        )

    def test_exact_deadline_expires_open_and_blocks_close_critical(self) -> None:
        self.commit(
            [
                self.intent("open-1"),
                self.intent("close-1", offset="close"),
            ]
        )

        deadline = TRACE_DEADLINE_NS + 100
        before = spool.expire_due_intents(
            self.connection,
            now_epoch_ns=deadline - 1,
            now_monotonic_ns=deadline - 1,
            clock_domain_id="boot-a",
        )
        at_deadline = spool.expire_due_intents(
            self.connection,
            now_epoch_ns=deadline,
            now_monotonic_ns=deadline,
            clock_domain_id="boot-a",
        )

        self.assertEqual((0, 0), (before.expired_open_count, before.blocked_close_count))
        self.assertEqual(
            (1, 1),
            (at_deadline.expired_open_count, at_deadline.blocked_close_count),
        )
        counts = spool.spool_counts(self.connection)
        self.assertEqual(1, counts["expired"])
        self.assertEqual(1, counts["blocked"])

    def test_expired_lease_requeues_only_with_explicit_no_side_effect(self) -> None:
        self.commit([self.intent("open-1")])
        first = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=1,
        )
        self.assertIsNotNone(first)

        state = spool.recover_expired_lease(
            self.connection,
            now_epoch_ns=1_000_000_200,
            now_monotonic_ns=1_000_000_200,
            clock_domain_id="boot-a",
            evidence=spool.LeaseRecoveryEvidence(
                intent_id="open-1",
                lease_owner="executor-a",
                lease_token=first.lease_token,
                ledger_disposition="no_side_effect",
                ledger_fingerprint="ledger-v2:test",
                ledger_watermark=7,
                ledger_checksum_sha256=hashlib.sha256(b"ledger-7").hexdigest(),
            ),
        )
        self.assertEqual("ready", state)
        stored_evidence = json.loads(
            self.connection.execute(
                "SELECT recovery_evidence_json FROM intents WHERE intent_id='open-1'"
            ).fetchone()[0]
        )
        self.assertEqual(first.lease_token, stored_evidence["lease_token"])
        self.assertEqual(7, stored_evidence["ledger_watermark"])

        second = spool.lease_next(
            self.connection,
            owner_id="executor-b",
            now_epoch_ns=1_000_000_201,
            now_monotonic_ns=1_000_000_201,
            clock_domain_id="boot-a",
            lease_seconds=1,
        )
        self.assertIsNotNone(second)
        state = spool.recover_expired_lease(
            self.connection,
            now_epoch_ns=2_000_000_201,
            now_monotonic_ns=2_000_000_201,
            clock_domain_id="boot-a",
            evidence=spool.LeaseRecoveryEvidence(
                intent_id="open-1",
                lease_owner="executor-b",
                lease_token=second.lease_token,
                ledger_disposition="unknown",
                ledger_fingerprint="ledger-v2:test",
                ledger_watermark=8,
                ledger_checksum_sha256=hashlib.sha256(b"ledger-8").hexdigest(),
            ),
        )
        self.assertEqual("side_effect_unknown", state)
        self.assertEqual(1, spool.spool_counts(self.connection)["side_effect_unknown"])

    def test_recovery_evidence_must_match_current_lease_token(self) -> None:
        self.commit([self.intent("open-1")])
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=1,
        )
        self.assertIsNotNone(lease)

        with self.assertRaises(spool.SpoolTransitionError):
            spool.recover_expired_lease(
                self.connection,
                now_epoch_ns=1_000_000_200,
                now_monotonic_ns=1_000_000_200,
                clock_domain_id="boot-a",
                evidence=spool.LeaseRecoveryEvidence(
                    intent_id="open-1",
                    lease_owner="executor-a",
                    lease_token="stale-token",
                    ledger_disposition="no_side_effect",
                    ledger_fingerprint="ledger-v2:test",
                    ledger_watermark=7,
                    ledger_checksum_sha256=hashlib.sha256(b"ledger-7").hexdigest(),
                ),
            )
        self.assertEqual(1, spool.spool_counts(self.connection)["leased"])

    def test_trace_observations_are_separate_and_payload_seed_is_immutable(self) -> None:
        intent = self.intent("open-1")
        self.commit([intent], stamp_spool=False)
        payload_before = self.connection.execute(
            "SELECT payload_json FROM intents WHERE intent_id='open-1'"
        ).fetchone()[0]

        created = spool.record_trace_observation(
            self.connection,
            intent_id="open-1",
            stage="spool_committed",
            epoch_ns=500,
            monotonic_ns=400,
            clock_domain_id="boot-a",
        )
        replayed = spool.record_trace_observation(
            self.connection,
            intent_id="open-1",
            stage="spool_committed",
            epoch_ns=500,
            monotonic_ns=400,
            clock_domain_id="boot-a",
        )
        with self.assertRaises(spool.SpoolConflictError):
            spool.record_trace_observation(
                self.connection,
                intent_id="open-1",
                stage="spool_committed",
                epoch_ns=501,
                monotonic_ns=401,
                clock_domain_id="boot-a",
            )

        payload_after = self.connection.execute(
            "SELECT payload_json FROM intents WHERE intent_id='open-1'"
        ).fetchone()[0]
        observations = spool.read_trace_observations(
            self.connection,
            intent_id="open-1",
        )
        self.assertTrue(created)
        self.assertFalse(replayed)
        self.assertEqual(payload_before, payload_after)
        self.assertEqual(500, observations["spool_committed"].epoch_ns)

    def test_unstamped_commit_is_not_leaseable_until_spool_stamp_is_durable(self) -> None:
        self.commit([self.intent("open-1")], stamp_spool=False)

        self.assertIsNone(
            spool.lease_next(
                self.connection,
                owner_id="executor-a",
                now_epoch_ns=200,
                now_monotonic_ns=200,
                clock_domain_id="boot-a",
                lease_seconds=5,
            )
        )
        spool.record_trace_observation(
            self.connection,
            intent_id="open-1",
            stage="spool_committed",
            epoch_ns=150,
            monotonic_ns=150,
            clock_domain_id="boot-a",
        )
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=5,
        )

        self.assertIsNotNone(lease)
        observations = spool.read_trace_observations(
            self.connection,
            intent_id="open-1",
        )
        self.assertEqual(200, observations["executor_dequeued"].epoch_ns)

    def test_spool_stamp_must_follow_stage905_in_same_clock_domain(self) -> None:
        self.commit([self.intent("open-1")], stamp_spool=False)

        for monotonic_ns, domain in ((100, "boot-a"), (150, "boot-b")):
            with self.subTest(monotonic_ns=monotonic_ns, domain=domain):
                with self.assertRaises(spool.SpoolValidationError):
                    spool.record_trace_observation(
                        self.connection,
                        intent_id="open-1",
                        stage="spool_committed",
                        epoch_ns=150,
                        monotonic_ns=monotonic_ns,
                        clock_domain_id=domain,
                    )

    def test_later_close_preempts_already_leased_open_before_sending(self) -> None:
        first_cursor = self.cursor(1)
        self.commit([self.intent("open-1")], next_cursor=first_cursor)
        open_lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=5,
        )
        self.assertIsNotNone(open_lease)
        self.commit(
            [self.intent("close-1", offset="close")],
            expected=first_cursor,
            next_cursor=self.cursor(2),
        )

        transitioned = spool.transition_intent(
            self.connection,
            intent_id="open-1",
            owner_id="executor-a",
            lease_token=open_lease.lease_token,
            expected_state="leased",
            new_state="sending",
            now_epoch_ns=300,
            now_monotonic_ns=300,
            clock_domain_id="boot-a",
        )

        self.assertEqual("blocked", transitioned.state)
        self.assertEqual(1, spool.spool_counts(self.connection)["ready"])

    def test_leased_intent_cannot_cross_absolute_deadline_into_sending(self) -> None:
        intent = self.intent("open-1")
        self.commit([intent])
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=30,
        )
        self.assertIsNotNone(lease)

        transitioned = spool.transition_intent(
            self.connection,
            intent_id="open-1",
            owner_id="executor-a",
            lease_token=lease.lease_token,
            expected_state="leased",
            new_state="sending",
            now_epoch_ns=int(intent["deadline_epoch_ns"]),
            now_monotonic_ns=int(intent["deadline_monotonic_ns"]),
            clock_domain_id="boot-a",
        )

        self.assertEqual("expired", transitioned.state)

    def test_clock_domain_change_fails_closed_before_leasing(self) -> None:
        self.commit([self.intent("open-1")])

        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-b",
            lease_seconds=5,
        )

        self.assertIsNone(lease)
        self.assertEqual(1, spool.spool_counts(self.connection)["expired"])

    def test_stored_payload_tamper_rolls_back_lease_claim(self) -> None:
        self.commit([self.intent("open-1")])
        self.connection.execute(
            "UPDATE intents SET payload_json='{}' WHERE intent_id='open-1'"
        )

        with self.assertRaisesRegex(
            spool.SpoolValidationError,
            "stored_payload_sha256_mismatch",
        ):
            spool.lease_next(
                self.connection,
                owner_id="executor-a",
                now_epoch_ns=200,
                now_monotonic_ns=200,
                clock_domain_id="boot-a",
                lease_seconds=5,
            )

        self.assertEqual(1, spool.spool_counts(self.connection)["ready"])

    def test_stored_trace_identity_tamper_rolls_back_lease_claim(self) -> None:
        self.commit([self.intent("open-1")])
        stored_trace = json.loads(
            self.connection.execute(
                "SELECT trace_json FROM intents WHERE intent_id='open-1'"
            ).fetchone()[0]
        )
        stored_trace["vt_symbol"] = "RB610.SHFE"
        self.connection.execute(
            "UPDATE intents SET trace_json=? WHERE intent_id='open-1'",
            (
                json.dumps(
                    stored_trace,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )

        with self.assertRaisesRegex(
            spool.SpoolValidationError,
            "stored_trace_binding_mismatch:vt_symbol",
        ):
            spool.lease_next(
                self.connection,
                owner_id="executor-a",
                now_epoch_ns=200,
                now_monotonic_ns=200,
                clock_domain_id="boot-a",
                lease_seconds=5,
            )

        self.assertEqual(1, spool.spool_counts(self.connection)["ready"])

    def test_redundant_kind_priority_tamper_rolls_back_lease_claim(self) -> None:
        self.commit([self.intent("close-1", offset="close")])
        self.connection.execute(
            "UPDATE intents SET intent_kind='open', priority=1 "
            "WHERE intent_id='close-1'"
        )

        with self.assertRaisesRegex(
            spool.SpoolValidationError,
            "stored_payload_binding_mismatch",
        ):
            spool.lease_next(
                self.connection,
                owner_id="executor-a",
                now_epoch_ns=200,
                now_monotonic_ns=200,
                clock_domain_id="boot-a",
                lease_seconds=5,
            )

        self.assertEqual(1, spool.spool_counts(self.connection)["ready"])

    def test_transition_intent_requires_matching_lease_token_and_state(self) -> None:
        self.commit([self.intent("close-1", offset="close")])
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=5,
        )
        self.assertIsNotNone(lease)

        with self.assertRaises(spool.SpoolTransitionError):
            spool.transition_intent(
                self.connection,
                intent_id="close-1",
                owner_id="executor-a",
                lease_token="wrong-token",
                expected_state="leased",
                new_state="sending",
                now_epoch_ns=300,
                now_monotonic_ns=300,
                clock_domain_id="boot-a",
            )
        transitioned = spool.transition_intent(
            self.connection,
            intent_id="close-1",
            owner_id="executor-a",
            lease_token=lease.lease_token,
            expected_state="leased",
            new_state="sending",
            now_epoch_ns=300,
            now_monotonic_ns=300,
            clock_domain_id="boot-a",
        )
        self.assertEqual("sending", transitioned.state)

    def test_blocked_intent_requires_task11_ledger_reconciliation_api(self) -> None:
        self.commit(
            [
                self.intent(
                    "close-1",
                    offset="close",
                    executor_status="blocked",
                )
            ]
        )

        with self.assertRaisesRegex(
            spool.SpoolTransitionError,
            "transition_not_allowed:blocked->reconciled",
        ):
            spool.transition_intent(
                self.connection,
                intent_id="close-1",
                owner_id="task11-ledger-reconciler",
                lease_token="not-a-lease-token",
                expected_state="blocked",
                new_state="reconciled",
                now_epoch_ns=200,
                now_monotonic_ns=200,
                clock_domain_id="boot-a",
                ledger_disposition="side_effect_present",
            )

    def test_expired_sending_lease_recovers_only_to_side_effect_unknown(self) -> None:
        self.commit([self.intent("close-1", offset="close")])
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=1,
        )
        self.assertIsNotNone(lease)
        spool.transition_intent(
            self.connection,
            intent_id="close-1",
            owner_id="executor-a",
            lease_token=lease.lease_token,
            expected_state="leased",
            new_state="sending",
            now_epoch_ns=300,
            now_monotonic_ns=300,
            clock_domain_id="boot-a",
        )

        state = spool.recover_expired_lease(
            self.connection,
            now_epoch_ns=1_000_000_200,
            now_monotonic_ns=1_000_000_200,
            clock_domain_id="boot-a",
            evidence=spool.LeaseRecoveryEvidence(
                intent_id="close-1",
                lease_owner="executor-a",
                lease_token=lease.lease_token,
                ledger_disposition="unknown",
                ledger_fingerprint="ledger-v2:test",
                ledger_watermark=9,
                ledger_checksum_sha256=hashlib.sha256(b"ledger-9").hexdigest(),
            ),
        )

        self.assertEqual("side_effect_unknown", state)
        self.assertEqual(1, spool.spool_counts(self.connection)["side_effect_unknown"])

    def test_confirmed_side_effect_recovery_remains_cas_reconcilable(self) -> None:
        self.commit([self.intent("close-1", offset="close")])
        lease = spool.lease_next(
            self.connection,
            owner_id="executor-a",
            now_epoch_ns=200,
            now_monotonic_ns=200,
            clock_domain_id="boot-a",
            lease_seconds=1,
        )
        self.assertIsNotNone(lease)
        spool.transition_intent(
            self.connection,
            intent_id="close-1",
            owner_id="executor-a",
            lease_token=lease.lease_token,
            expected_state="leased",
            new_state="sending",
            now_epoch_ns=300,
            now_monotonic_ns=300,
            clock_domain_id="boot-a",
        )

        recovered = spool.recover_expired_lease(
            self.connection,
            now_epoch_ns=1_000_000_200,
            now_monotonic_ns=1_000_000_200,
            clock_domain_id="boot-a",
            evidence=spool.LeaseRecoveryEvidence(
                intent_id="close-1",
                lease_owner="executor-a",
                lease_token=lease.lease_token,
                ledger_disposition="side_effect_present",
                ledger_fingerprint="ledger-v2:test",
                ledger_watermark=10,
                ledger_checksum_sha256=hashlib.sha256(b"ledger-10").hexdigest(),
            ),
        )
        reconciled = spool.transition_intent(
            self.connection,
            intent_id="close-1",
            owner_id="executor-a",
            lease_token=lease.lease_token,
            expected_state="side_effect_unknown",
            new_state="reconciled",
            now_epoch_ns=1_000_000_300,
            now_monotonic_ns=1_000_000_300,
            clock_domain_id="boot-a",
            ledger_disposition="side_effect_present",
        )

        self.assertEqual("side_effect_unknown", recovered)
        self.assertEqual("reconciled", reconciled.state)
        self.assertEqual("", reconciled.lease_token)

    def test_two_connection_claim_race_has_exactly_one_winner(self) -> None:
        self.commit([self.intent("open-1")])
        barrier = threading.Barrier(2)

        def claim(owner_id: str) -> str:
            connection = spool.open_spool(self.path)
            try:
                barrier.wait(timeout=5)
                lease = spool.lease_next(
                    connection,
                    owner_id=owner_id,
                    now_epoch_ns=200,
                    now_monotonic_ns=200,
                    clock_domain_id="boot-a",
                    lease_seconds=5,
                )
                return lease.intent.intent_id if lease is not None else ""
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = list(pool.map(claim, ("executor-a", "executor-b")))

        self.assertEqual(1, sum(bool(value) for value in winners))
        self.assertEqual(1, spool.spool_counts(self.connection)["leased"])

    def test_busy_writer_is_explicit_and_never_advances_cursor(self) -> None:
        blocker = spool.open_spool(self.path)
        self.addCleanup(blocker.close)
        blocker.execute("BEGIN IMMEDIATE")
        self.addCleanup(lambda: blocker.execute("ROLLBACK") if blocker.in_transaction else None)

        with self.assertRaisesRegex(
            spool.SpoolStorageError,
            "begin_immediate_failed",
        ):
            self.commit([self.intent("open-1")])

        self.assertIsNone(
            spool.read_detector_cursor(self.connection, consumer_id="stage941")
        )
        self.assertEqual(0, spool.spool_counts(self.connection)["total"])

    def test_missing_socket_does_not_rollback_and_poll_scan_recovers(self) -> None:
        self.commit([self.intent("open-1")])

        notified = spool.notify_executor(spool.wakeup_socket_path(self.path))
        self.connection.close()
        reopened = spool.open_spool(self.path)
        self.addCleanup(reopened.close)
        self.connection = reopened

        self.assertFalse(notified)
        self.assertEqual(1, spool.spool_counts(reopened)["ready"])


if __name__ == "__main__":
    unittest.main()
