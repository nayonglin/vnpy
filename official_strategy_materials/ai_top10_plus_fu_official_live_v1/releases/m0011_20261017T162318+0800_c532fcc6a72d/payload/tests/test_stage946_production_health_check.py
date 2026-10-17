from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import plistlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage946_official_live_production_health_check as health  # noqa: E402


class Stage946ProductionHealthCheckTest(unittest.TestCase):
    def _job_row(self, name: str) -> dict[str, object]:
        label = health.PRODUCTION_JOB_LABELS[name]
        root = health.REPO_ROOT
        environment = {
            "OFFICIAL_LIVE_OUTPUT_DIR": str(health.PRODUCTION_OUTPUT_ROOT),
            "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(
                health.PRODUCTION_SIGNAL_INPUT_ROOT
            ),
        }
        if name in {"day_session", "night_session"}:
            environment.update(
                {
                    "OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED": "1",
                    "OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED": "1",
                }
            )
        running = name == "day_session"
        return {
            "target_date": "2026-07-20",
            "source_path": f"source/{label}.plist",
            "installed_path": f"installed/{label}.plist",
            "source_exists": True,
            "installed_exists": True,
            "bytes_match": True,
            "source_secure": True,
            "installed_secure": True,
            "label_match": True,
            "working_directory": str(root),
            "program_arguments": [
                str(root / ".py311/bin/python"),
                str(
                    root
                    / "examples/portfolio_backtesting"
                    / health.PRODUCTION_JOB_SCRIPT_NAMES[name]
                ),
                *(
                    ["--session", "day" if name == "day_session" else "night"]
                    if name in {"day_session", "night_session"}
                    else ["--job", health.PRODUCTION_SUPPORT_JOB_KEYS[name]]
                ),
            ],
            "environment_variables": environment,
            "forbidden_environment_keys": [],
            "launchctl": {
                "label": label,
                "loaded": True,
                "state": "running" if running else "exited",
                "pid": 4321 if running else None,
                "last_exit_code": None,
            },
        }

    def _latest(self, *, pid: int = 4321) -> dict[str, object]:
        return {
            "execution_profile": "c9-15w",
            "official_live_version": health.C9_15W_PROFILE.official_version,
            "capital": health.C9_15W_PROFILE.capital,
            "capital_label": health.C9_15W_PROFILE.capital_label,
            "runtime_profile": "production-live",
            "mode": "live-real",
            "submit_mode": "live-real",
            "detector_mode": "persistent",
            "daemon_status": "daemon_running",
            "target_date": "2026-07-20",
            "launchd_provenance": {
                "complete": 1,
                "xpc_service_name": health.PRODUCTION_LABELS["day"],
                "pid": pid,
                "launchctl_job_pid": pid,
            },
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "order_api_evidence_complete": 1,
        }

    def _readiness(self) -> dict[str, object]:
        now = time.time_ns()
        return {
            "schema_version": 1,
            "status": "ready",
            "service_generation": "service-generation-1",
            "connection_generation": "connection-generation-1",
            "runtime_profile": "production-live",
            "official_version": health.C9_15W_PROFILE.official_version,
            "capital": health.C9_15W_PROFILE.capital,
            "issued_epoch_ns": now - 1_000_000,
            "expires_epoch_ns": now + 30_000_000_000,
        }

    def _build(
        self,
        *,
        latest: dict[str, object] | None = None,
        receipt: dict[str, object] | None = None,
        current_sessions: tuple[str, ...] = ("day_am",),
        now: str = "2026-07-21T09:00:00+08:00",
        day_running: bool = True,
        surface_override: dict[str, object] | None = None,
    ) -> dict[str, object]:
        rows = {name: self._job_row(name) for name in health.PRODUCTION_JOB_LABELS}
        if not day_running:
            rows["day_session"]["launchctl"] = {
                "label": health.PRODUCTION_LABELS["day"],
                "loaded": True,
                "state": "exited",
                "pid": None,
                "last_exit_code": 0,
            }
        daily_receipt = receipt or {
            "receipt_sha256": "d" * 64,
            "target_cutoff_date": "2026-07-20",
            "data_inventory": {
                "semantic_freshness": {
                    "next_trading_session_date": "2026-07-21",
                }
            },
        }
        critical_files = [
            {
                "path": f"examples/portfolio_backtesting/launchd/{label}.plist",
                "sha256": "a" * 64,
                "size_bytes": 1,
            }
            for label in health.PRODUCTION_JOB_LABELS.values()
        ]
        surface_jobs = {
            health.PRODUCTION_JOB_LABELS[name]: dict(row["launchctl"])
            for name, row in rows.items()
        }

        def read_json(path: Path) -> dict[str, object]:
            if path == health.LATEST_STAGE930_SUMMARY:
                return latest or self._latest()
            if path == health.READINESS_PATH:
                return self._readiness()
            if path == health.PRODUCTION_DAILY_DATA_RECEIPT:
                return {
                    "target_cutoff_date": daily_receipt["target_cutoff_date"],
                }
            return {}

        with (
            patch.object(health, "PRODUCTION_DEPLOY_ROOT", health.REPO_ROOT),
            patch.object(health, "_path_has_symlink_component", return_value=False),
            patch.object(health, "_git_head", return_value="a" * 40),
            patch.object(
                health,
                "validate_exact_owned_launchd_surface",
                return_value=surface_override or {
                    "status": "verified_exact",
                    "blockers": [],
                    "disk_owned_labels": sorted(surface_jobs),
                    "domain_owned_labels": sorted(surface_jobs),
                    "loaded_owned_labels": sorted(surface_jobs),
                    "unknown_owned_labels": [],
                    "unknown_domain_owned_labels": [],
                    "unknown_loaded_owned_labels": [],
                    "jobs": surface_jobs,
                },
            ),
            patch.object(
                health,
                "_plist_status",
                side_effect=lambda label, **_kwargs: rows[
                    next(
                        name
                        for name, expected in health.PRODUCTION_JOB_LABELS.items()
                        if expected == label
                    )
                ],
            ),
            patch.object(health, "_discover_relevant_installed_labels", return_value=()),
            patch.object(
                health,
                "_launchctl_status",
                side_effect=lambda label: {
                    "label": label,
                    "loaded": False,
                    "state": "",
                    "pid": None,
                    "last_exit_code": None,
                },
            ),
            patch.object(
                health,
                "load_and_validate_release_manifest",
                return_value={
                    "manifest_sha256": "b" * 64,
                    "source_commit": "a" * 40,
                    "created_at_utc": "2026-07-21T05:00:00Z",
                    "strategy_semantics_qualification": {
                        "status": "passed",
                        "evidence_id": "c" * 64,
                    },
                    "critical_files": critical_files,
                },
            ),
            patch.object(
                health,
                "load_and_validate_production_qualification_evidence",
                return_value={"evidence_sha256": "c" * 64},
            ),
            patch.object(
                health,
                "load_and_validate_production_daily_data_receipt",
                return_value=daily_receipt,
            ),
            patch.object(
                health,
                "validate_production_venv_link",
                return_value=(Path("/venv"), Path("/venv/bin/python"), ()),
            ),
            patch.object(health, "validate_stage179_activation_receipt", return_value=[]),
            patch.object(
                health,
                "_active_session_names",
                return_value=current_sessions,
            ),
            patch.object(health, "_read_json", side_effect=read_json),
            patch.object(health, "_age_seconds", return_value=1.0),
            patch.object(
                health,
                "_build_storage_summary",
                return_value={
                    "minimum_free_bytes": health.PRODUCTION_MIN_FREE_BYTES,
                    "filesystems": [{"below_minimum": False}],
                    "directories": [],
                },
            ),
            patch.object(Path, "exists", return_value=False),
        ):
            return health.build_health_summary(
                now=datetime.fromisoformat(now)
            )

    def test_healthy_summary_binds_seven_jobs_single_pid_and_c9_readiness(self) -> None:
        summary = self._build()

        self.assertEqual(
            "healthy_production_live_session_running",
            summary["health_status"],
        )
        self.assertEqual([], summary["blockers"])
        self.assertEqual(7, len(summary["production_jobs"]))
        self.assertEqual(
            [health.PRODUCTION_LABELS["day"]],
            summary["running_session_labels"],
        )

    def test_stale_stage930_pid_is_blocked(self) -> None:
        summary = self._build(latest=self._latest(pid=9999))
        self.assertIn(
            "production_stage930_launchd_pid_mismatch",
            summary["blockers"],
        )

    def test_signed_future_next_session_marks_holiday_scheduled(self) -> None:
        receipt = {
            "receipt_sha256": "d" * 64,
            "target_cutoff_date": "2026-07-17",
            "data_inventory": {
                "semantic_freshness": {
                    "next_trading_session_date": "2026-07-21",
                }
            },
        }
        summary = self._build(
            receipt=receipt,
            now="2026-07-20T09:00:00+08:00",
            day_running=False,
        )
        self.assertEqual("non_trading_day", summary["calendar_status"])
        self.assertEqual("", summary["expected_session_label"])
        self.assertEqual(
            "healthy_production_live_scheduled",
            summary["health_status"],
        )
        self.assertNotIn(
            "expected_production_session_not_running",
            summary["blockers"],
        )

    def test_unknown_unloaded_owned_plist_is_a_health_blocker(self) -> None:
        unknown = "local.qmt-roll.official-live.unregistered-unloaded"
        summary = self._build(
            surface_override={
                "status": "blocked",
                "blockers": [f"unknown_owned_label:{unknown}"],
                "disk_owned_labels": [
                    *health.PRODUCTION_JOB_LABELS.values(),
                    unknown,
                ],
                "domain_owned_labels": list(
                    health.PRODUCTION_JOB_LABELS.values()
                ),
                "loaded_owned_labels": list(
                    health.PRODUCTION_JOB_LABELS.values()
                ),
                "unknown_owned_labels": [unknown],
                "unknown_domain_owned_labels": [],
                "unknown_loaded_owned_labels": [],
                "jobs": {},
            }
        )

        self.assertTrue(
            any(
                blocker.startswith("production_owned_launchd_surface_not_exact:")
                and unknown in blocker
                for blocker in summary["blockers"]
            )
        )
        self.assertIn(
            f"unexpected_launchd_plist_installed:{unknown}",
            summary["blockers"],
        )

    def test_secure_plist_status_redacts_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_dir = root / "repo"
            install_dir = root / "install"
            repo_dir.mkdir()
            install_dir.mkdir()
            label = health.PRODUCTION_LABELS["day"]
            payload = {
                "Label": label,
                "WorkingDirectory": str(ROOT),
                "ProgramArguments": [sys.executable, "/tmp/launcher.py"],
                "EnvironmentVariables": {
                    "OFFICIAL_LIVE_OUTPUT_DIR": "/tmp/output",
                    "CTP_PASSWORD": "never-print-this-value",
                },
            }
            encoded = plistlib.dumps(payload)
            for parent in (repo_dir, install_dir):
                path = parent / f"{label}.plist"
                path.write_bytes(encoded)
                path.chmod(0o600)
            with (
                patch.object(health, "LAUNCHD_REPO_DIR", repo_dir),
                patch.object(health, "LAUNCHD_INSTALL_DIR", install_dir),
                patch.object(
                    health,
                    "_launchctl_status",
                    return_value={"loaded": False},
                ),
            ):
                row = health._plist_status(label)

        self.assertIn("CTP_PASSWORD", row["forbidden_environment_keys"])
        self.assertEqual("<redacted>", row["environment_variables"]["CTP_PASSWORD"])
        self.assertNotIn("never-print-this-value", json.dumps(row))

    def test_symlink_or_group_writable_plist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.plist"
            target.write_bytes(plistlib.dumps({"Label": "x"}))
            target.chmod(0o620)
            raw, payload, secure = health._read_secure_plist(target)
            self.assertFalse(secure)
            self.assertEqual(b"", raw)
            self.assertIn("_read_error", payload)

            link = root / "link.plist"
            link.symlink_to(target)
            _raw, _payload, secure = health._read_secure_plist(link)
            self.assertFalse(secure)


if __name__ == "__main__":
    unittest.main()
