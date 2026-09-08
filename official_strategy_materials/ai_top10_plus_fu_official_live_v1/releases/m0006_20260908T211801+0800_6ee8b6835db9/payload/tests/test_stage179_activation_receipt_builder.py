from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage179_activation_receipt as receipt_builder  # noqa: E402
from qmt_roll_official_execution_profile import C9_15W_PROFILE  # noqa: E402
from qmt_roll_official_live_release_manifest import ReleaseManifestError  # noqa: E402
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (  # noqa: E402
    serialize_stage179_activation_receipt,
    validate_stage179_activation_receipt,
)


class Stage179ActivationReceiptBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "receipt@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Receipt Test"],
            cwd=self.repo,
            check=True,
        )
        (self.repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "tracked.txt"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )
        self.head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo,
            text=True,
            check=True,
            capture_output=True,
        ).stdout.strip()
        self.output = Path(self.tempdir.name) / "activation.json"
        self.manifest = {
            "manifest_sha256": "a" * 64,
            "source_commit": self.head,
            "created_at_utc": "2026-07-21T06:00:00Z",
            "critical_files": [{"path": "tracked.txt"}],
            "strategy_semantics_qualification": {
                "status": "passed",
                "evidence_id": "b" * 64,
            },
        }
        self.runtime_identity = {
            "python_realpath": "/trusted/.py311/bin/python3.11",
            "python_sha256": "1" * 64,
            "vnpy_ctp_extension_sha256s": {
                "vnctpmd": "2" * 64,
                "vnctptd": "3" * 64,
            },
            "formal_framework_executable_sha256s": {
                "thostmduserapi_se": "4" * 64,
                "thosttraderapi_se": "5" * 64,
            },
            "formal_framework_realpaths": [
                "/trusted/.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs",
                "/trusted/.py311/lib",
            ],
        }

    def build(self) -> dict[str, object]:
        with (
            patch.object(
                receipt_builder,
                "load_and_validate_release_manifest",
                return_value=self.manifest,
            ),
            patch.object(
                receipt_builder,
                "load_and_validate_production_qualification_evidence",
                return_value={
                    "evidence_sha256": "b" * 64,
                    "trusted_runner": dict(self.runtime_identity),
                },
            ),
            patch.object(
                receipt_builder,
                "_production_runtime_identity",
                return_value=dict(self.runtime_identity),
            ),
        ):
            return receipt_builder.build_stage179_activation_receipt(
                output_path=self.output,
                release_manifest_path=Path(self.tempdir.name) / "release.json",
                production_qualification_evidence=(
                    Path(self.tempdir.name) / "qualification.json"
                ),
                confirmation=(
                    receipt_builder.PRODUCTION_ACTIVATION_RECEIPT_CONFIRM_TEXT
                ),
                repo_root=self.repo,
                created_at_utc="2026-07-21T06:05:00Z",
            )

    def test_builder_writes_atomic_canonical_0600_receipt(self) -> None:
        payload = self.build()

        self.assertEqual(0o600, self.output.stat().st_mode & 0o777)
        self.assertEqual(
            serialize_stage179_activation_receipt(payload),
            self.output.read_bytes(),
        )
        self.assertEqual(
            (),
            validate_stage179_activation_receipt(
                self.output,
                manifest_sha256="a" * 64,
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
            ),
        )
        self.assertEqual(payload, self.build())

    def test_builder_rejects_missing_confirmation_or_evidence_mismatch(self) -> None:
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "confirmation_missing",
        ):
            receipt_builder.build_stage179_activation_receipt(
                output_path=self.output,
                release_manifest_path="release.json",
                production_qualification_evidence="qualification.json",
                confirmation="approved-ish",
                repo_root=self.repo,
            )

        with (
            patch.object(
                receipt_builder,
                "load_and_validate_release_manifest",
                return_value=self.manifest,
            ),
            patch.object(
                receipt_builder,
                "load_and_validate_production_qualification_evidence",
                return_value={
                    "evidence_sha256": "c" * 64,
                    "trusted_runner": dict(self.runtime_identity),
                },
            ),
            patch.object(
                receipt_builder,
                "_production_runtime_identity",
                return_value=dict(self.runtime_identity),
            ),
            self.assertRaisesRegex(
                ReleaseManifestError,
                "qualification_evidence_mismatch",
            ),
        ):
            receipt_builder.build_stage179_activation_receipt(
                output_path=self.output,
                release_manifest_path="release.json",
                production_qualification_evidence="qualification.json",
                confirmation=(
                    receipt_builder.PRODUCTION_ACTIVATION_RECEIPT_CONFIRM_TEXT
                ),
                repo_root=self.repo,
                created_at_utc="2026-07-21T06:05:00Z",
            )

    def test_builder_recomputes_and_rejects_runtime_binary_drift(self) -> None:
        drifted = copy.deepcopy(self.runtime_identity)
        drifted["python_sha256"] = "9" * 64
        with (
            patch.object(
                receipt_builder,
                "load_and_validate_release_manifest",
                return_value=self.manifest,
            ),
            patch.object(
                receipt_builder,
                "load_and_validate_production_qualification_evidence",
                return_value={
                    "evidence_sha256": "b" * 64,
                    "trusted_runner": dict(self.runtime_identity),
                },
            ),
            patch.object(
                receipt_builder,
                "_production_runtime_identity",
                return_value=drifted,
            ),
            self.assertRaisesRegex(
                ReleaseManifestError,
                "activation_receipt_runtime_binary_identity_mismatch",
            ),
        ):
            receipt_builder.build_stage179_activation_receipt(
                output_path=self.output,
                release_manifest_path="release.json",
                production_qualification_evidence="qualification.json",
                confirmation=(
                    receipt_builder.PRODUCTION_ACTIVATION_RECEIPT_CONFIRM_TEXT
                ),
                repo_root=self.repo,
                created_at_utc="2026-07-21T06:05:00Z",
            )

    def test_validator_rejects_noncanonical_or_group_readable_receipt(self) -> None:
        payload = self.build()
        self.output.write_text(json.dumps(payload), encoding="utf-8")
        self.output.chmod(0o600)
        self.assertEqual(
            ("stage179_activation_receipt_invalid",),
            validate_stage179_activation_receipt(
                self.output,
                manifest_sha256="a" * 64,
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
            ),
        )
        self.output.write_bytes(serialize_stage179_activation_receipt(payload))
        self.output.chmod(0o640)
        self.assertEqual(
            ("stage179_activation_receipt_invalid",),
            validate_stage179_activation_receipt(
                self.output,
                manifest_sha256="a" * 64,
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
            ),
        )


if __name__ == "__main__":
    unittest.main()
