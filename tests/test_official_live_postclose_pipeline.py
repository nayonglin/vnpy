from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_official_live_postclose_pipeline as pipeline  # noqa: E402


class OfficialLivePostclosePipelineTest(unittest.TestCase):
    def _new(self) -> dict[str, object]:
        return pipeline.new_postclose_pipeline_receipt(
            pipeline_run_id="a" * 32,
            schedule_date="2026-08-03",
            target_date="2026-08-03",
            source_commit="b" * 40,
            manifest_sha256="c" * 64,
            generated_at_utc="2026-08-03T08:35:00Z",
        )

    def test_pipeline_requires_ordered_stages_and_zero_order_apis(self) -> None:
        payload = pipeline.record_postclose_pipeline_stage(
            self._new(),
            stage="resolve-target",
            status="succeeded",
            started_at_utc="2026-08-03T08:35:00Z",
            finished_at_utc="2026-08-03T08:35:01Z",
        )

        self.assertEqual("running", payload["status"])
        self.assertEqual(0, payload["send_order_api_called_count"])
        self.assertEqual(0, payload["cancel_order_api_called_count"])
        self.assertEqual(0, payload["order_api_called_count"])
        with self.assertRaisesRegex(
            pipeline.PostclosePipelineError,
            "postclose_pipeline_stage_order_invalid",
        ):
            pipeline.record_postclose_pipeline_stage(
                payload,
                stage="generate-postclose-report",
                status="succeeded",
                started_at_utc="2026-08-03T08:35:02Z",
                finished_at_utc="2026-08-03T08:35:03Z",
            )

    def test_failure_fills_downstream_skips_and_retry_is_bounded(self) -> None:
        payload = self._new()
        for stage, status in (
            ("resolve-target", "succeeded"),
            ("refresh-market-data", "succeeded"),
            ("check-monthly-ai-pool", "succeeded"),
            ("refresh-monthly-ai-pool", "failed"),
        ):
            payload = pipeline.record_postclose_pipeline_stage(
                payload,
                stage=stage,
                status=status,
                started_at_utc="2026-08-03T08:35:00Z",
                finished_at_utc="2026-08-03T08:35:01Z",
                blocker=(
                    "production_support_monthly_ai_pool_process_failed"
                    if status == "failed"
                    else ""
                ),
            )
        payload = pipeline.finish_postclose_pipeline_receipt(
            payload,
            status="failed",
            root_blocker="production_support_monthly_ai_pool_process_failed",
            email_disposition={"notification_status": "sent"},
            finished_at_utc="2026-08-03T08:35:02Z",
        )

        self.assertEqual("refresh-monthly-ai-pool", payload["root_stage"])
        self.assertTrue(pipeline.postclose_pipeline_retry_eligible(payload))
        later = payload["stages"][4:]
        self.assertTrue(later)
        self.assertTrue(
            all(row["status"] == "skipped_upstream_failed" for row in later)
        )
        retried = dict(payload)
        retried["retry_of"] = "d" * 32
        self.assertFalse(pipeline.postclose_pipeline_retry_eligible(retried))

    def test_atomic_private_round_trip_rejects_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "state"
            parent.mkdir(mode=0o700)
            path = parent / "latest.json"
            payload = self._new()
            pipeline.write_postclose_pipeline_receipt(path, payload)
            loaded = pipeline.load_and_validate_postclose_pipeline_receipt(
                path,
                source_commit="b" * 40,
                manifest_sha256="c" * 64,
                schedule_date="2026-08-03",
            )

            self.assertEqual(payload["pipeline_run_id"], loaded["pipeline_run_id"])
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            with self.assertRaisesRegex(
                pipeline.PostclosePipelineError,
                "postclose_pipeline_source_commit_mismatch",
            ):
                pipeline.load_and_validate_postclose_pipeline_receipt(
                    path,
                    source_commit="e" * 40,
                    manifest_sha256="c" * 64,
                )

    def test_nonzero_order_api_is_rejected(self) -> None:
        payload = self._new()
        payload["order_api_called_count"] = 1
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "state"
            parent.mkdir(mode=0o700)
            with self.assertRaisesRegex(
                pipeline.PostclosePipelineError,
                "postclose_pipeline_order_api_nonzero",
            ):
                pipeline.write_postclose_pipeline_receipt(
                    parent / "latest.json",
                    payload,
                )

    def test_lock_is_private_and_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "state"
            parent.mkdir(mode=0o700)
            path = parent / "pipeline.lock"
            first = pipeline.open_postclose_pipeline_lock(path)
            try:
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
                with self.assertRaisesRegex(
                    pipeline.PostclosePipelineError,
                    "postclose_pipeline_lock_busy",
                ):
                    pipeline.open_postclose_pipeline_lock(path)
            finally:
                fcntl.flock(first.fileno(), fcntl.LOCK_UN)
                first.close()


if __name__ == "__main__":
    unittest.main()
