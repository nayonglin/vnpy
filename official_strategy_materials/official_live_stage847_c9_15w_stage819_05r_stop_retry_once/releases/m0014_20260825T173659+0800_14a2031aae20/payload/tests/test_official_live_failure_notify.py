from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_official_live_email_notify as email_notify  # noqa: E402
import qmt_roll_official_live_failure_notify as failure_notify  # noqa: E402


BASE_NOW = datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc)


def _race_worker(
    state_path_text: str,
    lock_path_text: str,
    counter_path_text: str,
    index: int,
) -> None:
    state_path = Path(state_path_text)
    lock_path = Path(lock_path_text)
    counter_path = Path(counter_path_text)

    def sender(**_kwargs: object) -> dict[str, str]:
        with counter_path.open("ab", buffering=0) as handle:
            handle.write(b"x")
        return {"email_status": "sent"}

    result = failure_notify._notify_official_live_failure(
        job="postclose-precompute",
        boundary="precompute",
        blocker=f"production_support_race_{index}",
        schedule_date="2026-07-23",
        release_commit="a" * 40,
        state_path=state_path,
        lock_path=lock_path,
        now=BASE_NOW,
        email_sender=sender,
    )
    if result.get("notification_status") not in {
        "sent",
        "suppressed_terminal",
    }:
        raise AssertionError(result)


class OfficialLiveFailureNotifyTest(unittest.TestCase):
    def _private_root(self, directory: str) -> Path:
        root = Path(directory).resolve()
        root.chmod(0o700)
        return root

    def _invoke(
        self,
        *,
        root: Path,
        sender: object,
        now: datetime = BASE_NOW,
        job: str = "postclose-report",
        boundary: str = "target-date-resolver",
        blocker: str = "production_support_target_date_resolver_failed",
        schedule_date: str = "2026-07-23",
        release_commit: str = "a" * 40,
        pipeline_run_id: str = "",
        root_stage: str = "",
    ) -> dict[str, object]:
        return failure_notify._notify_official_live_failure(
            job=job,
            boundary=boundary,
            blocker=blocker,
            schedule_date=schedule_date,
            release_commit=release_commit,
            pipeline_run_id=pipeline_run_id,
            root_stage=root_stage,
            state_path=root / "state.json",
            lock_path=root / "state.lock",
            now=now,
            email_sender=sender,
        )

    def test_signal_asset_blocker_is_preserved_without_exposing_secrets(self) -> None:
        self.assertEqual(
            "production_signal_ai_pool_binding_mismatch",
            failure_notify.normalize_official_live_failure_blocker(
                "production_signal_ai_pool_binding_mismatch",
                fallback="production_support_unexpected_failure",
            ),
        )
        self.assertEqual(
            "production_signal_artifact_missing",
            failure_notify.normalize_official_live_failure_blocker(
                "production_signal_artifact_missing:official_summary",
                fallback="production_support_unexpected_failure",
            ),
        )
        self.assertEqual(
            "production_signal_pending_cohort_invalid",
            failure_notify.normalize_official_live_failure_blocker(
                "production_signal_pending_cohort_invalid:artifact_schema_mismatch",
                fallback="production_support_unexpected_failure",
            ),
        )
        self.assertEqual(
            "production_support_unexpected_failure",
            failure_notify.normalize_official_live_failure_blocker(
                "production_signal_pending_cohort_invalid:secret_token",
                fallback="production_support_unexpected_failure",
            ),
        )
        self.assertEqual(
            "production_support_unexpected_failure",
            failure_notify.normalize_official_live_failure_blocker(
                "production_signal_future_unknown_error",
                fallback="production_support_unexpected_failure",
            ),
        )

    def test_pipeline_context_is_sanitized_metadata_not_dedupe_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            calls: list[dict[str, object]] = []

            def sender(**kwargs: object) -> dict[str, str]:
                calls.append(kwargs)
                return {"email_status": "sent"}

            first = self._invoke(
                root=root,
                sender=sender,
                job="postclose-pipeline",
                boundary="postclose-pipeline:refresh-monthly-ai-pool",
                blocker="production_support_monthly_ai_pool_process_failed",
                pipeline_run_id="b" * 32,
                root_stage="refresh-monthly-ai-pool",
            )
            second = self._invoke(
                root=root,
                sender=sender,
                now=BASE_NOW + timedelta(hours=1),
                job="postclose-pipeline",
                boundary="postclose-pipeline:refresh-monthly-ai-pool",
                blocker="production_support_monthly_ai_pool_process_failed",
                pipeline_run_id="c" * 32,
                root_stage="refresh-monthly-ai-pool",
            )

        self.assertEqual("sent", first["notification_status"])
        self.assertEqual("suppressed_terminal", second["notification_status"])
        self.assertEqual(1, len(calls))
        metadata = calls[0]["metadata"]
        self.assertEqual("b" * 32, metadata["pipeline_run_id"])
        self.assertEqual("refresh-monthly-ai-pool", metadata["root_stage"])

    def test_sent_and_dry_run_are_terminal_for_same_fingerprint(self) -> None:
        for terminal in ("sent", "dry_run_written"):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as directory:
                root = self._private_root(directory)
                calls: list[dict[str, object]] = []

                def sender(**kwargs: object) -> dict[str, str]:
                    calls.append(kwargs)
                    return {"email_status": terminal}

                first = self._invoke(root=root, sender=sender)
                second = self._invoke(
                    root=root,
                    sender=sender,
                    now=BASE_NOW + timedelta(hours=1),
                )

                self.assertEqual(terminal, first["notification_status"])
                self.assertEqual(
                    "suppressed_terminal",
                    second["notification_status"],
                )
                self.assertEqual(1, len(calls))

    def test_terminal_fingerprint_survives_interleaved_other_fingerprint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            calls: list[dict[str, object]] = []

            def sender(**kwargs: object) -> dict[str, str]:
                calls.append(kwargs)
                return {"email_status": "sent"}

            first_a = self._invoke(
                root=root,
                sender=sender,
                blocker="production_support_failure_a",
            )
            first_b = self._invoke(
                root=root,
                sender=sender,
                blocker="production_support_failure_b",
            )
            second_a = self._invoke(
                root=root,
                sender=sender,
                blocker="production_support_failure_a",
                now=BASE_NOW + timedelta(hours=1),
            )

        self.assertEqual("sent", first_a["notification_status"])
        self.assertEqual("sent", first_b["notification_status"])
        self.assertEqual("suppressed_terminal", second_a["notification_status"])
        self.assertEqual(2, len(calls))

    def test_nonterminal_statuses_observe_thirty_minute_cooldown(self) -> None:
        statuses = (
            "send_failed",
            "disabled",
            "blocked_missing_config",
            "helper_failed",
        )
        for status in statuses:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = self._private_root(directory)
                call_count = 0

                def sender(**_kwargs: object) -> dict[str, str]:
                    nonlocal call_count
                    call_count += 1
                    if status == "helper_failed":
                        raise RuntimeError("safe-test-error")
                    return {"email_status": status}

                first = self._invoke(root=root, sender=sender)
                before = self._invoke(
                    root=root,
                    sender=sender,
                    now=BASE_NOW + timedelta(seconds=1799),
                )
                after = self._invoke(
                    root=root,
                    sender=sender,
                    now=BASE_NOW + timedelta(seconds=1801),
                )

                self.assertEqual(status, first["notification_status"])
                self.assertEqual(
                    "suppressed_cooldown",
                    before["notification_status"],
                )
                self.assertEqual(status, after["notification_status"])
                self.assertEqual(2, call_count)

    def test_reserved_crash_state_observes_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            state_path = root / "state.json"
            lock_path = root / "state.lock"
            fingerprint = failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-23",
                "postclose-report",
                "target-date-resolver",
                "production_support_target_date_resolver_failed",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "updated_at": BASE_NOW.isoformat(),
                        "entries": {
                            fingerprint: {
                                "fingerprint": fingerprint,
                                "release_commit": "a" * 40,
                                "schedule_date": "2026-07-23",
                                "job": "postclose-report",
                                "boundary": "target-date-resolver",
                                "blocker": (
                                    "production_support_target_date_resolver_failed"
                                ),
                                "status": "reserved",
                                "updated_at": BASE_NOW.isoformat(),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            state_path.chmod(0o600)
            calls = 0

            def sender(**_kwargs: object) -> dict[str, str]:
                nonlocal calls
                calls += 1
                return {"email_status": "sent"}

            before = failure_notify._notify_official_live_failure(
                job="postclose-report",
                boundary="target-date-resolver",
                blocker="production_support_target_date_resolver_failed",
                schedule_date="2026-07-23",
                release_commit="a" * 40,
                state_path=state_path,
                lock_path=lock_path,
                now=BASE_NOW + timedelta(seconds=1799),
                email_sender=sender,
            )
            after = failure_notify._notify_official_live_failure(
                job="postclose-report",
                boundary="target-date-resolver",
                blocker="production_support_target_date_resolver_failed",
                schedule_date="2026-07-23",
                release_commit="a" * 40,
                state_path=state_path,
                lock_path=lock_path,
                now=BASE_NOW + timedelta(seconds=1801),
                email_sender=sender,
            )

        self.assertEqual("suppressed_cooldown", before["notification_status"])
        self.assertEqual("sent", after["notification_status"])
        self.assertEqual(1, calls)

    def test_release_date_job_boundary_and_blocker_change_fingerprint(self) -> None:
        values = {
            failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-23",
                "postclose-report",
                "target-date-resolver",
                "production_support_target_date_resolver_failed",
            ),
            failure_notify._failure_fingerprint(
                "b" * 40,
                "2026-07-23",
                "postclose-report",
                "target-date-resolver",
                "production_support_target_date_resolver_failed",
            ),
            failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-24",
                "postclose-report",
                "target-date-resolver",
                "production_support_target_date_resolver_failed",
            ),
            failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-23",
                "postclose-precompute",
                "target-date-resolver",
                "production_support_target_date_resolver_failed",
            ),
            failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-23",
                "postclose-report",
                "daily-data-receipt",
                "production_support_target_date_resolver_failed",
            ),
            failure_notify._failure_fingerprint(
                "a" * 40,
                "2026-07-23",
                "postclose-report",
                "target-date-resolver",
                "production_support_daily_data_receipt_invalid",
            ),
        }

        self.assertEqual(6, len(values))
        self.assertTrue(all(len(value) == 64 for value in values))

    def test_mailer_exception_returns_helper_failed_without_recursion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            calls = 0

            def sender(**_kwargs: object) -> dict[str, str]:
                nonlocal calls
                calls += 1
                raise RuntimeError("raw-secret-must-not-survive")

            result = self._invoke(root=root, sender=sender)
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))

        self.assertEqual("helper_failed", result["notification_status"])
        self.assertEqual("RuntimeError", result["error_type"])
        self.assertEqual(1, calls)
        serialized = json.dumps([result, state], ensure_ascii=False)
        self.assertNotIn("raw-secret-must-not-survive", serialized)

    def test_state_and_lock_are_0600_and_state_is_valid_atomic_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)

            def sender(**_kwargs: object) -> dict[str, str]:
                return {"email_status": "sent"}

            self._invoke(root=root, sender=sender)
            state_path = root / "state.json"
            lock_path = root / "state.lock"
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            temporary_files = list(root.glob(".*.tmp"))

            self.assertEqual(0o700, stat.S_IMODE(root.stat().st_mode))
            self.assertEqual(0o600, stat.S_IMODE(state_path.stat().st_mode))
            self.assertEqual(0o600, stat.S_IMODE(lock_path.stat().st_mode))
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual([], temporary_files)

    def test_unsafe_parent_or_lock_symlink_returns_helper_failed_without_send(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            root.chmod(0o770)
            calls = 0

            def sender(**_kwargs: object) -> dict[str, str]:
                nonlocal calls
                calls += 1
                return {"email_status": "sent"}

            unsafe_parent = self._invoke(root=root, sender=sender)
            root.chmod(0o700)

        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            target = root / "target.txt"
            target.write_text("unchanged", encoding="utf-8")
            lock_path = root / "state.lock"
            lock_path.symlink_to(target)
            unsafe_lock = failure_notify._notify_official_live_failure(
                job="postclose-report",
                boundary="target-date-resolver",
                blocker="production_support_target_date_resolver_failed",
                schedule_date="2026-07-23",
                release_commit="a" * 40,
                state_path=root / "state.json",
                lock_path=lock_path,
                now=BASE_NOW,
                email_sender=sender,
            )
            target_text = target.read_text(encoding="utf-8")

        self.assertEqual("helper_failed", unsafe_parent["notification_status"])
        self.assertEqual("helper_failed", unsafe_lock["notification_status"])
        self.assertEqual(0, calls)
        self.assertEqual("unchanged", target_text)

    def test_secret_sentinels_never_reach_subject_body_metadata_state_or_audit(
        self,
    ) -> None:
        sentinels = (
            "CTP_PASSWORD_SENTINEL",
            "SMTP_PASSWORD_SENTINEL",
            "AUTH_CODE_SENTINEL",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            captured: list[dict[str, object]] = []

            def sender(**kwargs: object) -> dict[str, str]:
                captured.append(kwargs)
                raise RuntimeError("SMTP_PASSWORD_SENTINEL")

            result = self._invoke(
                root=root,
                sender=sender,
                blocker="CTP_PASSWORD_SENTINEL:AUTH_CODE_SENTINEL",
                release_commit="AUTH_CODE_SENTINEL",
                root_stage="SMTP_PASSWORD_SENTINEL",
            )
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))

            env_file = root / "email.env"
            env_file.write_text(
                "OFFICIAL_LIVE_EMAIL_ENABLED=1\n"
                "OFFICIAL_LIVE_EMAIL_SMTP_HOST=smtp.example.invalid\n"
                "OFFICIAL_LIVE_EMAIL_SMTP_PORT=465\n"
                "OFFICIAL_LIVE_EMAIL_SMTP_USER=user@example.invalid\n"
                "OFFICIAL_LIVE_EMAIL_SMTP_PASSWORD=SMTP_PASSWORD_SENTINEL\n"
                "OFFICIAL_LIVE_EMAIL_FROM=user@example.invalid\n"
                "OFFICIAL_LIVE_EMAIL_TO=recipient@example.invalid\n"
                "OFFICIAL_LIVE_EMAIL_USE_SSL=1\n",
                encoding="utf-8",
            )
            audit_path = root / "audit.ndjson"
            with (
                patch.object(email_notify, "OUTPUT_DIR", root),
                patch.object(email_notify, "EMAIL_AUDIT_LOG_PATH", audit_path),
                patch.object(
                    email_notify,
                    "_send_message",
                    side_effect=RuntimeError("SMTP_PASSWORD_SENTINEL"),
                ),
            ):
                email_result = email_notify.send_official_live_email_notification(
                    subject="safe subject",
                    body="safe body",
                    event_type="stage200_secret_audit",
                    severity="warning",
                    attachments=[],
                    metadata={"safe": 1},
                    env_file=env_file,
                )
            audit_text = audit_path.read_text(encoding="utf-8")

        serialized = json.dumps(
            [result, state, captured, email_result, audit_text],
            ensure_ascii=False,
            default=str,
        )
        for sentinel in sentinels:
            self.assertNotIn(sentinel, serialized)
        self.assertEqual("RuntimeError", email_result["error_type"])
        self.assertNotIn("error", email_result)

    def test_one_hundred_fork_races_have_exactly_one_mailer_winner(self) -> None:
        context = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as directory:
            root = self._private_root(directory)
            state_path = root / "state.json"
            lock_path = root / "state.lock"
            counter_path = root / "counter.bin"
            counter_path.write_bytes(b"")
            for index in range(100):
                processes = [
                    context.Process(
                        target=_race_worker,
                        args=(
                            str(state_path),
                            str(lock_path),
                            str(counter_path),
                            index,
                        ),
                    )
                    for _ in range(2)
                ]
                for process in processes:
                    process.start()
                for process in processes:
                    process.join(timeout=10)
                    self.assertEqual(0, process.exitcode)
            counter = counter_path.read_bytes()

        self.assertEqual(100, len(counter))


if __name__ == "__main__":
    unittest.main()
