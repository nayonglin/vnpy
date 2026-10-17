from __future__ import annotations

from pathlib import Path
import os
import plistlib
import pwd
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage946_official_live_production_health_check as health


class LocalProductionPathsTest(unittest.TestCase):
    def test_committed_jobs_target_this_machine_canonical_runtime(self) -> None:
        """A copied old-machine plist must not pass local deployment checks."""
        self._assert_committed_jobs_target_this_machine()

    def test_sanitized_home_does_not_change_launchd_account_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, "home", return_value=Path(directory)):
                self._assert_committed_jobs_target_this_machine()

    def _assert_committed_jobs_target_this_machine(self) -> None:
        account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        stable = account_home / "Desktop/person/vnpy_production_live"
        state = account_home / "Library/Application Support/qmt-roll-stage179/production-live"
        source = PORTFOLIO_DIR / "launchd"
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory)
            for label in health.PRODUCTION_JOB_LABELS.values():
                (installed / f"{label}.plist").write_bytes(
                    (source / f"{label}.plist").read_bytes()
                )
                (installed / f"{label}.plist").chmod(0o600)
            with (
                patch.object(health, "LAUNCHD_REPO_DIR", source),
                patch.object(health, "LAUNCHD_INSTALL_DIR", installed),
            ):
                for name, label in health.PRODUCTION_JOB_LABELS.items():
                    with self.subTest(job=name):
                        row = health._plist_status(label, launchctl_row={})
                        self.assertTrue(row["bytes_match"])
                        self.assertTrue(row["label_match"])
                        self.assertEqual(str(stable), row["working_directory"])
                        self.assertEqual(
                            [
                                str(stable / ".py311/bin/python"),
                                str(stable / "examples/portfolio_backtesting" / health.PRODUCTION_JOB_SCRIPT_NAMES[name]),
                            ],
                            row["program_arguments"][:2],
                        )
                        self.assertEqual(
                            str(state / "official-live"),
                            row["environment_variables"]["OFFICIAL_LIVE_OUTPUT_DIR"],
                        )
                        self.assertEqual(
                            str(state / "signal-input"),
                            row["environment_variables"]["OFFICIAL_LIVE_SIGNAL_INPUT_DIR"],
                        )
                        payload = plistlib.loads((installed / f"{label}.plist").read_bytes())
                        for key in ("StandardOutPath", "StandardErrorPath"):
                            self.assertEqual(state / "logs", Path(payload[key]).parent)
                        if name in {"day_session", "night_session"}:
                            arguments = payload["ProgramArguments"]
                            for flag, expected in (
                                ("--release-manifest", state / "release-manifest.json"),
                                ("--activation-receipt", state / "runtime/state/activation_receipt.json"),
                                ("--stage179-runtime-root", state / "runtime"),
                                ("--output-root", state / "official-live"),
                                ("--signal-input-root", state / "signal-input"),
                            ):
                                self.assertEqual(str(expected), arguments[arguments.index(flag) + 1])


if __name__ == "__main__":
    unittest.main()
