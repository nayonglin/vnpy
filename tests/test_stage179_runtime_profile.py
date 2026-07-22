from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_runtime_profile import (
    ExecutionRuntimeProfile,
    OrderScope,
    RuntimeProfileError,
    resolve_runtime_profile,
)
import run_qmt_roll_stage914_official_live_ctp_runtime_preflight as stage914
from qmt_roll_official_execution_profile import C9_15W_PROFILE, STAGE372_20W_PROFILE
from qmt_roll_official_live_phase_d_config import (
    STAGE179_ACTIVATION_CONFIRM_TEXT,
    STAGE179_ACTIVATION_ENV,
)


class Stage179RuntimeProfileTest(unittest.TestCase):
    @staticmethod
    def _runtime_binary_identity(root: Path) -> dict[str, object]:
        return {
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
                str(root / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"),
                str(root / ".py311/lib"),
            ],
        }

    def test_stage914_preflight_resolves_stage372_without_c9_global(self) -> None:
        profile = stage914.resolve_preflight_execution_profile("stage372-20w")

        self.assertEqual(profile.profile_key, "stage372-20w")
        self.assertEqual(
            profile.official_version,
            "official_live_stage372_20w_recovery_sleeve",
        )
        self.assertFalse(profile.intraday_stop_retry_enabled)

    def test_profiles_have_exact_env_mapping_and_distinct_runtime_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            resolved = {
                profile: resolve_runtime_profile(
                    profile=profile,
                    order_scope={
                        ExecutionRuntimeProfile.OFFLINE: OrderScope.NONE,
                        ExecutionRuntimeProfile.PRODUCTION_READONLY: OrderScope.READONLY,
                        ExecutionRuntimeProfile.SIMNOW: OrderScope.TEST,
                        ExecutionRuntimeProfile.BROKER_TEST: OrderScope.TEST,
                        ExecutionRuntimeProfile.PRODUCTION_LIVE: OrderScope.LIVE,
                    }[profile],
                    repo_root=repo,
                )
                for profile in ExecutionRuntimeProfile
            }

        self.assertIsNone(resolved[ExecutionRuntimeProfile.OFFLINE].env_file)
        self.assertEqual(
            "ctp_live.local.env",
            resolved[ExecutionRuntimeProfile.PRODUCTION_READONLY].env_file.name,
        )
        self.assertEqual(
            "ctp_live.local.env",
            resolved[ExecutionRuntimeProfile.PRODUCTION_LIVE].env_file.name,
        )
        self.assertEqual(
            "ctp_simnow.local.env",
            resolved[ExecutionRuntimeProfile.SIMNOW].env_file.name,
        )
        self.assertEqual(
            "ctp_broker_test.local.env",
            resolved[ExecutionRuntimeProfile.BROKER_TEST].env_file.name,
        )
        self.assertEqual(
            len(resolved),
            len({item.output_root for item in resolved.values()}),
        )
        self.assertEqual(
            len(resolved),
            len({item.spool_path for item in resolved.values()}),
        )
        self.assertEqual(
            len(resolved),
            len({item.ledger_path for item in resolved.values()}),
        )

    def test_production_framework_order_requires_formal_vnpy_ctp_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_runtime_profile(
                profile=ExecutionRuntimeProfile.PRODUCTION_READONLY,
                order_scope=OrderScope.READONLY,
                repo_root=Path(tmp),
            )

        self.assertTrue(
            str(resolved.framework_path[0]).endswith(
                "vnpy_ctp/api/libs"
            )
        )
        self.assertTrue(str(resolved.framework_path[1]).endswith(".py311/lib"))

    def test_runtime_roots_reject_resolved_alias_with_production_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            production_state = root / "production-state"
            production_state.mkdir()
            candidate_alias = root / "candidate-alias"
            candidate_alias.symlink_to(production_state, target_is_directory=True)

            with self.assertRaises(RuntimeProfileError):
                resolve_runtime_profile(
                    profile=ExecutionRuntimeProfile.OFFLINE,
                    order_scope=OrderScope.NONE,
                    repo_root=root,
                    output_root=candidate_alias,
                    protected_production_roots=(production_state,),
                )

    def test_runtime_env_rejects_cross_profile_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "examples" / "portfolio_backtesting"
            project.mkdir(parents=True)
            broker_env = project / "ctp_broker_test.local.env"
            broker_env.write_text("CTP_ENV_PROFILE=broker-test\n", encoding="utf-8")
            (project / "ctp_live.local.env").symlink_to(broker_env)

            with self.assertRaises(RuntimeProfileError):
                resolve_runtime_profile(
                    profile=ExecutionRuntimeProfile.PRODUCTION_READONLY,
                    order_scope=OrderScope.READONLY,
                    repo_root=root,
                )

    def test_profile_and_order_scope_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeProfileError):
                resolve_runtime_profile(
                    profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
                    order_scope=OrderScope.READONLY,
                    repo_root=Path(tmp),
                )

    def _production_live(self, root: Path):
        return resolve_runtime_profile(
            profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
            order_scope=OrderScope.LIVE,
            repo_root=root,
        )

    def test_production_live_default_off_stops_before_adapter_import(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            with patch.object(
                stage914,
                "load_and_validate_release_manifest",
                return_value={"manifest_sha256": "a" * 64},
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version="official-v",
                    expected_capital=200_000,
                    expected_capital_label="20w",
                    environment={},
                    confirmation="",
                    activation_receipt_path=root / "receipt.json",
                    phase_d_real_submit_ready=True,
                    stage927_ready=True,
                    kill_switch_clear=True,
                    broker_gates_fresh=True,
                    adapter_factory=lambda: calls.append("adapter"),
                )

        self.assertIn("stage179_activation_disabled", result.blockers)
        self.assertEqual([], calls)
        self.assertFalse(result.adapter_created)

    def test_legacy_stage372_identity_blocks_even_with_env_and_confirm(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            receipt = root / "receipt.json"
            receipt.write_text("{}", encoding="utf-8")
            with (
                patch.object(
                    stage914,
                    "load_and_validate_release_manifest",
                    return_value={"manifest_sha256": "a" * 64},
                ),
                patch.object(
                    stage914,
                    "validate_stage179_activation_receipt",
                    return_value=(),
                ),
                patch.object(
                    stage914,
                    "_production_runtime_identity",
                    return_value=self._runtime_binary_identity(root),
                ),
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version=STAGE372_20W_PROFILE.official_version,
                    expected_capital=STAGE372_20W_PROFILE.capital,
                    expected_capital_label=STAGE372_20W_PROFILE.capital_label,
                    expected_execution_profile=STAGE372_20W_PROFILE.profile_key,
                    environment={STAGE179_ACTIVATION_ENV: "1"},
                    confirmation=STAGE179_ACTIVATION_CONFIRM_TEXT,
                    activation_receipt_path=receipt,
                    phase_d_real_submit_ready=True,
                    stage927_ready=True,
                    kill_switch_clear=True,
                    broker_gates_fresh=True,
                    adapter_factory=lambda: calls.append("adapter"),
                )

        self.assertIn("production_live_execution_profile_not_current_official", result.blockers)
        self.assertEqual([], calls)

    def test_c9_15w_identity_does_not_add_an_operator_policy_blocker(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            with (
                patch.object(
                    stage914,
                    "load_and_validate_release_manifest",
                    return_value={"manifest_sha256": "a" * 64},
                ),
                patch.object(
                    stage914,
                    "validate_stage179_activation_receipt",
                    return_value=(),
                ),
                patch.object(
                    stage914,
                    "_production_runtime_identity",
                    return_value=self._runtime_binary_identity(root),
                ),
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version=C9_15W_PROFILE.official_version,
                    expected_capital=C9_15W_PROFILE.capital,
                    expected_capital_label=C9_15W_PROFILE.capital_label,
                    expected_execution_profile=C9_15W_PROFILE.profile_key,
                    environment={STAGE179_ACTIVATION_ENV: "1"},
                    confirmation=STAGE179_ACTIVATION_CONFIRM_TEXT,
                    activation_receipt_path=root / "receipt.json",
                    phase_d_real_submit_ready=True,
                    stage927_ready=True,
                    kill_switch_clear=True,
                    broker_gates_fresh=True,
                    adapter_factory=lambda: calls.append("adapter"),
                )

        self.assertEqual((), result.blockers)
        self.assertEqual(["adapter"], calls)
        self.assertTrue(result.adapter_created)

    def test_persistent_startup_defers_only_cycle_authorization_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            with (
                patch.object(
                    stage914,
                    "load_and_validate_release_manifest",
                    return_value={"manifest_sha256": "a" * 64},
                ),
                patch.object(
                    stage914,
                    "validate_stage179_activation_receipt",
                    return_value=(),
                ),
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version=C9_15W_PROFILE.official_version,
                    expected_capital=C9_15W_PROFILE.capital,
                    expected_capital_label=C9_15W_PROFILE.capital_label,
                    expected_execution_profile=C9_15W_PROFILE.profile_key,
                    environment={STAGE179_ACTIVATION_ENV: "1"},
                    confirmation=STAGE179_ACTIVATION_CONFIRM_TEXT,
                    activation_receipt_path=root / "receipt.json",
                    phase_d_real_submit_ready=True,
                    stage927_ready=False,
                    kill_switch_clear=True,
                    broker_gates_fresh=False,
                    defer_cycle_authorization=True,
                )

        self.assertNotIn("stage927_not_ready", result.blockers)
        self.assertNotIn("broker_gates_not_fresh", result.blockers)
        self.assertNotIn("production_live_execution_profile_not_current_official", result.blockers)

    def test_hand_built_string_profile_cannot_skip_live_gate(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = replace(self._production_live(root), profile="production-live")
            with patch.object(
                stage914,
                "load_and_validate_release_manifest",
                return_value={"manifest_sha256": "a" * 64},
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version="official-v",
                    expected_capital=200_000,
                    expected_capital_label="20w",
                    environment={STAGE179_ACTIVATION_ENV: "1"},
                    confirmation=STAGE179_ACTIVATION_CONFIRM_TEXT,
                    activation_receipt_path=root / "receipt.json",
                    phase_d_real_submit_ready=True,
                    stage927_ready=True,
                    kill_switch_clear=True,
                    broker_gates_fresh=True,
                    adapter_factory=lambda: calls.append("adapter"),
                )

        self.assertEqual(("stage179_runtime_profile_invalid",), result.blockers)
        self.assertEqual([], calls)

    def test_stage931_executable_calls_gate_before_ctp_gateway_import(self) -> None:
        stage931_path = PORTFOLIO_DIR / "run_qmt_roll_stage931_official_live_ctp_submit_adapter.py"
        source = stage931_path.read_text(encoding="utf-8")
        gate_call = source.index("stage179_gate = evaluate_stage179_pre_adapter_gate(")
        gateway_import = source.index("from vnpy_ctp import CtpGateway")

        self.assertLess(gate_call, gateway_import)
        self.assertIn('"--stage179-warm-executor"', source)
        self.assertIn("if args.stage179_warm_executor:", source)
        self.assertIn("default=ExecutionRuntimeProfile.OFFLINE.value", source)
        self.assertIn("default=OrderScope.NONE.value", source)
        self.assertIn('"--stage179-release-manifest"', source)
        self.assertIn('"--confirm-stage179-activation"', source)

        stage930_source = (
            PORTFOLIO_DIR / "run_qmt_roll_stage930_official_live_c9_session_daemon.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--stage179-warm-executor"', stage930_source)
        self.assertIn('"--stage179-execution-mode"', stage930_source)
        self.assertIn('"--release-manifest"', stage930_source)
        self.assertIn('"--confirm-stage179-activation"', stage930_source)

    def test_production_readonly_does_not_require_activation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_runtime_profile(
                profile=ExecutionRuntimeProfile.PRODUCTION_READONLY,
                order_scope=OrderScope.READONLY,
                repo_root=root,
            )
            with patch.object(
                stage914,
                "load_and_validate_release_manifest",
                return_value={"manifest_sha256": "a" * 64},
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version="official-v",
                    expected_capital=200_000,
                    expected_capital_label="20w",
                    environment=os.environ,
                    confirmation="",
                    activation_receipt_path=None,
                    phase_d_real_submit_ready=False,
                    stage927_ready=False,
                    kill_switch_clear=False,
                    broker_gates_fresh=False,
                )

        self.assertNotIn("stage179_activation_receipt_missing", result.blockers)
        self.assertNotIn("production_live_execution_profile_not_current_official", result.blockers)

    def test_submit_disabled_canary_does_not_require_activation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            with patch.object(
                stage914,
                "load_and_validate_release_manifest",
                return_value={"manifest_sha256": "a" * 64},
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version="official-v",
                    expected_capital=200_000,
                    expected_capital_label="20w",
                    environment={},
                    confirmation="",
                    activation_receipt_path=None,
                    phase_d_real_submit_ready=False,
                    stage927_ready=False,
                    kill_switch_clear=False,
                    broker_gates_fresh=False,
                )

        self.assertIn("phase_d_real_submit_not_ready", result.blockers)
        self.assertNotIn("stage179_activation_receipt_missing", result.blockers)
        self.assertNotIn("stage179_activation_receipt_unverifiable", result.blockers)

    def test_activation_receipt_is_pinned_to_manifest_identity_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            payload = {
                "schema_version": (
                    stage914.STAGE179_ACTIVATION_RECEIPT_SCHEMA_VERSION
                ),
                "manifest_sha256": "a" * 64,
                "official_version": "official-v",
                "capital": 200_000,
                "capital_label": "20w",
                "policy_decision": "approved",
                "created_at_utc": "2026-07-18T11:00:00Z",
                **self._runtime_binary_identity(Path(tmp)),
            }
            payload["receipt_sha256"] = (
                stage914.stage179_activation_receipt_digest(payload)
            )
            path.write_bytes(
                stage914.serialize_stage179_activation_receipt(payload)
            )
            path.chmod(0o600)

            self.assertEqual(
                (),
                stage914.validate_stage179_activation_receipt(
                    path,
                    manifest_sha256="a" * 64,
                    official_version="official-v",
                    capital=200_000,
                    capital_label="20w",
                ),
            )
            self.assertEqual(
                ("stage179_activation_receipt_mismatch",),
                stage914.validate_stage179_activation_receipt(
                    path,
                    manifest_sha256="b" * 64,
                    official_version="official-v",
                    capital=200_000,
                    capital_label="20w",
                ),
            )

    def test_runtime_hash_drift_after_receipt_blocks_adapter_creation(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = self._production_live(root)
            receipt = root / "receipt.json"
            signed_identity = self._runtime_binary_identity(root)
            payload = {
                "schema_version": (
                    stage914.STAGE179_ACTIVATION_RECEIPT_SCHEMA_VERSION
                ),
                "manifest_sha256": "a" * 64,
                "official_version": C9_15W_PROFILE.official_version,
                "capital": C9_15W_PROFILE.capital,
                "capital_label": C9_15W_PROFILE.capital_label,
                "policy_decision": "approved",
                "created_at_utc": "2026-07-18T11:00:00Z",
                **signed_identity,
            }
            payload["receipt_sha256"] = (
                stage914.stage179_activation_receipt_digest(payload)
            )
            receipt.write_bytes(
                stage914.serialize_stage179_activation_receipt(payload)
            )
            receipt.chmod(0o600)
            drifted_identity = dict(signed_identity)
            drifted_identity["python_sha256"] = "9" * 64
            with (
                patch.object(
                    stage914,
                    "load_and_validate_release_manifest",
                    return_value={"manifest_sha256": "a" * 64},
                ),
                patch.object(
                    stage914,
                    "_production_runtime_identity",
                    return_value=drifted_identity,
                ),
            ):
                result = stage914.evaluate_stage179_pre_adapter_gate(
                    resolved=resolved,
                    release_manifest_path=root / "release.json",
                    repo_root=root,
                    expected_official_version=C9_15W_PROFILE.official_version,
                    expected_capital=C9_15W_PROFILE.capital,
                    expected_capital_label=C9_15W_PROFILE.capital_label,
                    expected_execution_profile=C9_15W_PROFILE.profile_key,
                    environment={STAGE179_ACTIVATION_ENV: "1"},
                    confirmation=STAGE179_ACTIVATION_CONFIRM_TEXT,
                    activation_receipt_path=receipt,
                    phase_d_real_submit_ready=True,
                    stage927_ready=True,
                    kill_switch_clear=True,
                    broker_gates_fresh=True,
                    adapter_factory=lambda: calls.append("adapter"),
                )

        self.assertIn(
            "stage179_activation_receipt_runtime_binary_identity_mismatch",
            result.blockers,
        )
        self.assertEqual([], calls)
        self.assertFalse(result.adapter_created)


if __name__ == "__main__":
    unittest.main()
