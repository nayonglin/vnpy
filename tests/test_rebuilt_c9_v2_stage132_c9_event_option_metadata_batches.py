from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage132_c9_event_option_metadata_batches as s132


def _event(event_id: str | None = None) -> dict[str, object]:
    event_id = event_id or s132.event_id_for("m2209.DCE", "2022-03-09")
    return {
        "event_id": event_id,
        "vt_symbol": "m2209.DCE",
        "tqsdk_underlying": "DCE.m2209",
        "product_vt_symbol": "m.DCE",
        "entry_date": "2022-03-09",
        "query_start": "2022-03-09 00:00:00",
        "query_end": "2022-03-09 23:59:59",
        "query_expired_as_of_entry": False,
    }


def _untouched_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": ["DCE.m2209-C-3000", "DCE.m2209-P-3000"],
            "underlying_symbol": ["DCE.m2209", "DCE.m2209"],
            "option_class": ["CALL", "PUT"],
            "expire_datetime": [1659682800, 1659682800],
            "last_exercise_datetime": [1659682800, 1659682800],
            "strike_price": [3000.0, 3000.0],
            "expired": [False, False],
            "volume_multiple": [10, 10],
            "price_tick": [0.5, 0.5],
            "vendor_extra": ["keep-a", "keep-b"],
        }
    )


class Stage132EventOptionMetadataBatchesTest(unittest.TestCase):
    def test_frozen_source_and_batch_plan_match_predeclared_canary(self) -> None:
        events, source_audit = s132.load_frozen_events()
        plan = s132.build_batch_plan(events)

        self.assertTrue(source_audit["source_audit_pass"])
        self.assertEqual(len(events), 365)
        self.assertEqual(len(plan), 365)
        self.assertEqual(plan["batch_index"].nunique(), 37)
        self.assertEqual(plan.iloc[:10]["event_id"].tolist(), list(s132.CANARY_EVENT_IDS))
        self.assertTrue(plan.iloc[:10]["is_canary"].all())
        self.assertFalse(plan.iloc[10:]["is_canary"].any())

    def test_source_loader_fails_closed_on_hash_or_event_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            event = _event(s132.event_id_for("m2209.DCE", "2022-03-09"))
            pd.DataFrame([event]).to_csv(path, index=False)

            with self.assertRaises(ValueError):
                s132.load_frozen_events(path=path, expected_sha256="0" * 64, expected_rows=1)

            actual_hash = s132.file_sha256(path)
            dirty = pd.DataFrame([event]).assign(query_expired_as_of_entry=True)
            dirty.to_csv(path, index=False)
            with self.assertRaises(ValueError):
                s132.load_frozen_events(
                    path=path,
                    expected_sha256=s132.file_sha256(path),
                    expected_rows=1,
                )
            self.assertNotEqual(actual_hash, s132.file_sha256(path))

    def test_normalization_preserves_untouched_and_handles_seconds_ns_datetime(self) -> None:
        seconds = 1659682800
        ns = seconds * 1_000_000_000
        untouched = pd.DataFrame(
            {
                "instrument_id": ["A", "B", "C"],
                "underlying_symbol": ["DCE.m2209"] * 3,
                "option_class": ["CALL", "P", "put"],
                "expire_datetime": [seconds, ns, pd.Timestamp("2022-08-05 15:00:00")],
                "last_exercise_datetime": [seconds, ns, pd.Timestamp("2022-08-05 15:00:00")],
                "strike_price": [2900, 3000, 3100],
                "expired": [False, 0, "false"],
                "volume_multiple": [10, 10, 10],
                "price_tick": [0.5, 0.5, 0.5],
                "vendor_extra": [1, 2, 3],
            }
        )
        before = untouched.copy(deep=True)

        normalized = s132.normalize_option_metadata(untouched)

        pd.testing.assert_frame_equal(untouched, before)
        self.assertEqual(normalized["option_class"].tolist(), ["CALL", "PUT", "PUT"])
        self.assertTrue(normalized["expire_datetime"].notna().all())
        self.assertTrue(normalized["last_exercise_datetime"].notna().all())
        self.assertTrue(normalized["expired"].eq(False).all())
        self.assertNotIn("vendor_extra", normalized.columns)

    def test_metadata_audit_reconciles_symbol_set_and_rejects_wrong_underlying(self) -> None:
        untouched = _untouched_metadata()
        symbols = untouched["instrument_id"].tolist()
        normalized = s132.normalize_option_metadata(untouched)

        clean = s132.audit_extracted_metadata(
            symbols,
            untouched,
            normalized,
            requested_underlying="DCE.m2209",
        )
        self.assertTrue(clean["integrity_pass"])

        dirty = normalized.copy()
        dirty.loc[0, "underlying_symbol"] = "DCE.y2209"
        failed = s132.audit_extracted_metadata(
            symbols,
            untouched,
            dirty,
            requested_underlying="DCE.m2209",
        )
        self.assertFalse(failed["integrity_pass"])
        self.assertEqual(failed["wrong_underlying_count"], 1)

    def test_terminal_status_cacheability_is_fail_closed(self) -> None:
        self.assertTrue(s132.is_cacheable_terminal("extracted"))
        self.assertTrue(s132.is_cacheable_terminal("empty_chain"))
        self.assertTrue(s132.is_cacheable_terminal("underlying_not_in_option_catalog"))
        for status in [
            "authentication_failed",
            "timeout",
            "query_failed",
            "integrity_failed",
            "missing",
        ]:
            self.assertFalse(s132.is_cacheable_terminal(status), status)

    def test_catalog_missing_classifier_requires_exact_vendor_evidence(self) -> None:
        exact = (
            "查询合约服务报错 failed to execute graphql operation, errors: "
            "[variable instrument_id: [CZCE.MA809] contains non-existent instrument: CZCE.MA809]"
        )

        self.assertEqual(
            s132.classify_query_exception(
                exact, requested_underlying="CZCE.MA809"
            ),
            "underlying_not_in_option_catalog",
        )
        self.assertEqual(
            s132.classify_query_exception(
                exact, requested_underlying="CZCE.CF009"
            ),
            "query_failed",
        )
        self.assertEqual(
            s132.classify_query_exception("connection reset by peer"),
            "query_failed",
        )
        self.assertEqual(
            s132.classify_query_exception("authentication failed"),
            "authentication_failed",
        )

    def test_attempt_publish_is_atomic_manifested_and_cacheable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            untouched = _untouched_metadata()
            normalized = s132.normalize_option_metadata(untouched)
            symbols = untouched["instrument_id"].tolist()
            audit = s132.audit_extracted_metadata(
                symbols,
                untouched,
                normalized,
                requested_underlying="DCE.m2209",
            )
            status = s132.make_attempt_status(
                terminal_status="extracted",
                event=event,
                symbols=symbols,
                untouched=untouched,
                normalized=normalized,
                audit=audit,
                elapsed_seconds=1.25,
            )

            attempt_dir = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=symbols,
                untouched=untouched,
                normalized=normalized,
                status=status,
            )

            self.assertTrue(attempt_dir.is_dir())
            self.assertFalse(any(path.name.startswith(".tmp") for path in attempt_dir.parent.iterdir()))
            validation = s132.validate_attempt_dir(attempt_dir)
            self.assertTrue(validation["attempt_integrity_pass"])
            self.assertTrue(validation["cacheable"])
            manifest = pd.read_csv(attempt_dir / s132.ATTEMPT_MANIFEST_NAME)
            self.assertNotIn(s132.ATTEMPT_MANIFEST_NAME, manifest["file"].tolist())
            self.assertNotIn(s132.ATTEMPT_CHECKSUM_NAME, manifest["file"].tolist())
            expected_checksum = (
                f"{s132.file_sha256(attempt_dir / s132.ATTEMPT_MANIFEST_NAME)}  "
                f"{s132.ATTEMPT_MANIFEST_NAME}\n"
            )
            self.assertEqual(
                (attempt_dir / s132.ATTEMPT_CHECKSUM_NAME).read_text(encoding="ascii"),
                expected_checksum,
            )
            request = json.loads(
                (attempt_dir / s132.ATTEMPT_REQUEST_NAME).read_text(encoding="utf-8")
            )
            for key in ("tool_sha256", "test_sha256", "predecl_sha256"):
                self.assertRegex(request[key], r"^[0-9a-f]{64}$")

    def test_failed_attempt_is_retained_but_not_cached_or_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            failed_status = s132.make_attempt_status(
                terminal_status="query_failed",
                event=event,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                audit={},
                elapsed_seconds=0.5,
                message="network exploded",
            )
            first = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                status=failed_status,
            )
            second = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                status=failed_status,
            )

            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse(s132.validate_attempt_dir(first)["cacheable"])
            self.assertIsNone(s132.find_cacheable_attempt(attempts_root, str(event["event_id"])))

    def test_cache_validation_recomputes_metadata_semantics_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            untouched = _untouched_metadata()
            normalized = s132.normalize_option_metadata(untouched)
            symbols = untouched["instrument_id"].tolist()
            audit = s132.audit_extracted_metadata(
                symbols,
                untouched,
                normalized,
                requested_underlying="DCE.m2209",
            )
            attempt = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=symbols,
                untouched=untouched,
                normalized=normalized,
                status=s132.make_attempt_status(
                    terminal_status="extracted",
                    event=event,
                    symbols=symbols,
                    untouched=untouched,
                    normalized=normalized,
                    audit=audit,
                    elapsed_seconds=0.5,
                ),
            )
            dirty = pd.read_csv(attempt / s132.NORMALIZED_METADATA_NAME)
            dirty.loc[0, "strike_price"] = float(dirty.loc[0, "strike_price"]) + 0.01
            dirty.to_csv(
                attempt / s132.NORMALIZED_METADATA_NAME,
                index=False,
                encoding="utf-8-sig",
            )
            manifest = s132.build_output_manifest(
                attempt,
                excluded_names={s132.ATTEMPT_MANIFEST_NAME, s132.ATTEMPT_CHECKSUM_NAME},
            )
            s132._write_csv(manifest, attempt / s132.ATTEMPT_MANIFEST_NAME)
            (attempt / s132.ATTEMPT_CHECKSUM_NAME).write_text(
                s132.detached_checksum_line(attempt / s132.ATTEMPT_MANIFEST_NAME),
                encoding="ascii",
            )

            validation = s132.validate_attempt_dir(attempt)

            self.assertFalse(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])
            self.assertIn("normalized_recompute", validation["blocking_reason"])

    def test_cache_validation_binds_request_to_frozen_event_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event(s132.event_id_for("m2209.DCE", "2022-03-09"))
            status = s132.make_attempt_status(
                terminal_status="empty_chain",
                event=event,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                audit={},
                elapsed_seconds=0.1,
            )
            attempt = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                status=status,
            )
            request_path = attempt / s132.ATTEMPT_REQUEST_NAME
            request = json.loads(request_path.read_text())
            request["query_start"] = "2022-03-10 00:00:00"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            manifest = s132.build_output_manifest(
                attempt,
                excluded_names={s132.ATTEMPT_MANIFEST_NAME, s132.ATTEMPT_CHECKSUM_NAME},
            )
            s132._write_csv(manifest, attempt / s132.ATTEMPT_MANIFEST_NAME)
            (attempt / s132.ATTEMPT_CHECKSUM_NAME).write_text(
                s132.detached_checksum_line(attempt / s132.ATTEMPT_MANIFEST_NAME),
                encoding="ascii",
            )

            validation = s132.validate_attempt_dir(attempt)

            self.assertFalse(validation["cacheable"])
            self.assertIn("identity", validation["blocking_reason"])

    def test_cache_validation_fails_closed_on_malformed_schema_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            untouched = _untouched_metadata()
            normalized = s132.normalize_option_metadata(untouched)
            symbols = untouched["instrument_id"].tolist()
            audit = s132.audit_extracted_metadata(
                symbols,
                untouched,
                normalized,
                requested_underlying="DCE.m2209",
            )
            attempt = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=symbols,
                untouched=untouched,
                normalized=normalized,
                status=s132.make_attempt_status(
                    terminal_status="extracted",
                    event=event,
                    symbols=symbols,
                    untouched=untouched,
                    normalized=normalized,
                    audit=audit,
                    elapsed_seconds=0.1,
                ),
            )
            (attempt / s132.UNTOUCHED_SCHEMA_NAME).write_text("{", encoding="utf-8")
            manifest = s132.build_output_manifest(
                attempt,
                excluded_names={s132.ATTEMPT_MANIFEST_NAME, s132.ATTEMPT_CHECKSUM_NAME},
            )
            s132._write_csv(manifest, attempt / s132.ATTEMPT_MANIFEST_NAME)
            (attempt / s132.ATTEMPT_CHECKSUM_NAME).write_text(
                s132.detached_checksum_line(attempt / s132.ATTEMPT_MANIFEST_NAME),
                encoding="ascii",
            )

            validation = s132.validate_attempt_dir(attempt)

            self.assertFalse(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])

    def test_empty_chain_attempt_is_cacheable_without_metadata_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            status = s132.make_attempt_status(
                terminal_status="empty_chain",
                event=event,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                audit={},
                elapsed_seconds=0.2,
            )
            attempt = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                status=status,
            )

            self.assertTrue(s132.validate_attempt_dir(attempt)["cacheable"])
            self.assertFalse((attempt / s132.UNTOUCHED_METADATA_NAME).exists())
            self.assertFalse((attempt / s132.NORMALIZED_METADATA_NAME).exists())

            (attempt / s132.NORMALIZED_METADATA_NAME).write_text("unexpected\n", encoding="utf-8")
            manifest = s132.build_output_manifest(
                attempt,
                excluded_names={s132.ATTEMPT_MANIFEST_NAME, s132.ATTEMPT_CHECKSUM_NAME},
            )
            s132._write_csv(manifest, attempt / s132.ATTEMPT_MANIFEST_NAME)
            (attempt / s132.ATTEMPT_CHECKSUM_NAME).write_text(
                s132.detached_checksum_line(attempt / s132.ATTEMPT_MANIFEST_NAME),
                encoding="ascii",
            )
            self.assertFalse(s132.validate_attempt_dir(attempt)["cacheable"])

    def test_catalog_missing_attempt_is_cacheable_only_with_exact_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            event = _event()
            exact_message = (
                "查询合约服务报错 failed to execute graphql operation, errors: "
                "[variable instrument_id: [DCE.m2209] contains non-existent instrument: DCE.m2209]"
            )
            status = s132.make_attempt_status(
                terminal_status="underlying_not_in_option_catalog",
                event=event,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                audit={},
                elapsed_seconds=0.2,
                message=exact_message,
            )
            attempt = s132.publish_attempt(
                attempts_root=attempts_root,
                event=event,
                source_sha256="a" * 64,
                symbols=[],
                untouched=pd.DataFrame(),
                normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                status=status,
            )
            self.assertTrue(s132.validate_attempt_dir(attempt)["cacheable"])

            status_path = attempt / s132.ATTEMPT_STATUS_NAME
            payload = json.loads(status_path.read_text())
            payload["message"] = (
                "failed to execute graphql operation, errors: "
                "[variable instrument_id: [DCE.y2209] contains non-existent instrument: DCE.y2209]"
            )
            status_path.write_text(json.dumps(payload), encoding="utf-8")
            manifest = s132.build_output_manifest(
                attempt,
                excluded_names={s132.ATTEMPT_MANIFEST_NAME, s132.ATTEMPT_CHECKSUM_NAME},
            )
            s132._write_csv(manifest, attempt / s132.ATTEMPT_MANIFEST_NAME)
            (attempt / s132.ATTEMPT_CHECKSUM_NAME).write_text(
                s132.detached_checksum_line(attempt / s132.ATTEMPT_MANIFEST_NAME),
                encoding="ascii",
            )
            self.assertFalse(s132.validate_attempt_dir(attempt)["cacheable"])

    def test_redaction_removes_credentials_and_common_secret_assignments(self) -> None:
        message = "failed username=alice password=hunter2 token=abc123"
        redacted = s132.redact_message(message, secrets=["alice", "hunter2", "abc123"])
        self.assertNotIn("alice", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_status_json_contains_no_dataframe_or_credentials(self) -> None:
        status = s132.make_attempt_status(
            terminal_status="empty_chain",
            event=_event(),
            symbols=[],
            untouched=pd.DataFrame(),
            normalized=pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
            audit={},
            elapsed_seconds=0.1,
            message="username=alice password=hunter2",
        )
        payload = json.dumps(status)
        self.assertNotIn("hunter2", payload)
        self.assertNotIn("alice", payload)
        self.assertNotIn("DataFrame", payload)

    def test_empty_attempt_inventory_has_stable_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = s132.inventory_attempts(Path(tmp) / "missing")

        self.assertEqual(inventory.columns.tolist(), s132.ATTEMPT_INVENTORY_COLUMNS)

    def test_terminal_summary_reports_fixed_denominator_coverage_ratio(self) -> None:
        statuses = pd.DataFrame(
            {
                "terminal_status": (
                    ["extracted"] * 3
                    + ["empty_chain"] * 5
                    + ["underlying_not_in_option_catalog"] * 2
                    + ["missing"] * 355
                ),
                "cacheable": [True] * 10 + [False] * 355,
            }
        )

        summary = s132.summarize_terminal_statuses(statuses, denominator=365)

        self.assertEqual(summary["extracted_event_count"], 3)
        self.assertEqual(summary["request_ledger_completion_ratio"], 10 / 365)
        self.assertEqual(summary["metadata_coverage_ratio"], 3 / 365)

        invalid = statuses.copy()
        invalid.loc[:9, "cacheable"] = False
        invalid_summary = s132.summarize_terminal_statuses(invalid, denominator=365)
        self.assertEqual(invalid_summary["extracted_event_count"], 0)
        self.assertEqual(invalid_summary["empty_chain_event_count"], 0)
        self.assertEqual(invalid_summary["catalog_missing_event_count"], 0)
        self.assertEqual(invalid_summary["metadata_coverage_ratio"], 0.0)

    def test_wall_clock_timeout_covers_finally_cleanup(self) -> None:
        started = time.time()
        with self.assertRaises(s132.EventTimeoutError):
            with s132._wall_clock_timeout(0.03):
                try:
                    pass
                finally:
                    time.sleep(0.1)
        self.assertLess(time.time() - started, 0.09)

    def test_canary_runner_with_injected_fetcher_passes_and_resumes(self) -> None:
        events, _ = s132.load_frozen_events()
        plan = s132.build_batch_plan(events)
        canary = plan[plan["is_canary"].astype(bool)].copy()
        first_event_id = str(canary.iloc[0]["event_id"])

        def fake_fetcher(event: dict[str, object], _max_seconds: int):
            if str(event["event_id"]) != first_event_id:
                return (
                    "empty_chain",
                    [],
                    pd.DataFrame(),
                    pd.DataFrame(columns=s132.NORMALIZED_COLUMNS),
                    {},
                    "",
                    0.01,
                )
            underlying = str(event["tqsdk_underlying"])
            untouched = _untouched_metadata().copy()
            untouched["instrument_id"] = [f"{underlying}-C-100", f"{underlying}-P-100"]
            untouched["underlying_symbol"] = underlying
            normalized = s132.normalize_option_metadata(untouched)
            symbols = untouched["instrument_id"].tolist()
            audit = s132.audit_extracted_metadata(
                symbols,
                untouched,
                normalized,
                requested_underlying=underlying,
            )
            return "extracted", symbols, untouched, normalized, audit, "", 0.02

        with tempfile.TemporaryDirectory() as tmp:
            attempts_root = Path(tmp) / "attempts"
            first = s132.run_event_selection(
                canary,
                attempts_root=attempts_root,
                source_sha256="a" * 64,
                fetcher=fake_fetcher,
                max_seconds=1,
            )
            inventory = s132.inventory_attempts(attempts_root)
            status = s132.build_event_terminal_status(plan, inventory)
            gate = s132.audit_canary(status)
            second = s132.run_event_selection(
                canary,
                attempts_root=attempts_root,
                source_sha256="a" * 64,
                fetcher=fake_fetcher,
                max_seconds=1,
            )
            forced = s132.run_event_selection(
                canary,
                attempts_root=attempts_root,
                source_sha256="a" * 64,
                fetcher=fake_fetcher,
                max_seconds=1,
                force_retry=True,
            )

        self.assertEqual(first["new_attempt_count"], 10)
        self.assertEqual(first["cached_skip_count"], 0)
        self.assertTrue(gate["canary_gate_pass"])
        self.assertEqual(gate["canary_extracted_count"], 1)
        self.assertEqual(gate["canary_empty_chain_count"], 9)
        self.assertEqual(second["new_attempt_count"], 0)
        self.assertEqual(second["cached_skip_count"], 10)
        self.assertEqual(forced["new_attempt_count"], 10)
        self.assertEqual(forced["cached_skip_count"], 0)


if __name__ == "__main__":
    unittest.main()
