from __future__ import annotations

import importlib
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))


class OfficialLiveConfigImportTest(unittest.TestCase):
    def test_stage902_age_accepts_timezone_aware_iso_timestamp(self) -> None:
        import run_qmt_roll_stage902_official_live_phase_d_readiness_gate as stage902

        generated_at = (
            datetime.now().astimezone() - timedelta(seconds=1)
        ).isoformat()

        age_seconds = stage902._age_seconds(generated_at)

        self.assertIsNotNone(age_seconds)
        self.assertGreaterEqual(age_seconds, 0.5)
        self.assertLess(age_seconds, 3.0)

    def test_stage902_age_keeps_future_and_invalid_values_fail_closed(self) -> None:
        import run_qmt_roll_stage902_official_live_phase_d_readiness_gate as stage902

        future = (
            datetime.now().astimezone() + timedelta(seconds=1)
        ).isoformat()

        self.assertLess(stage902._age_seconds(future), 0)
        self.assertIsNone(stage902._age_seconds("not-a-timestamp"))

    def test_stage902_readonly_age_gate_enforces_both_ttl_boundaries(self) -> None:
        import run_qmt_roll_stage902_official_live_phase_d_readiness_gate as stage902

        cases = (
            (0.0, True),
            (1.0, True),
            (300.0, True),
            (-0.001, False),
            (300.001, False),
            (None, False),
        )
        for age_seconds, expected in cases:
            with self.subTest(age_seconds=age_seconds):
                self.assertEqual(
                    expected,
                    stage902._readonly_snapshot_age_ready(
                        age_seconds,
                        max_snapshot_age_seconds=300,
                    ),
                )

    def test_stage906_age_accepts_legacy_naive_and_timezone_aware_timestamps(self) -> None:
        import run_qmt_roll_stage906_official_live_reconciliation_worker as stage906

        generated_values = (
            (datetime.now() - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (datetime.now() - timedelta(seconds=1)).isoformat(),
            (datetime.now().astimezone() - timedelta(seconds=1)).isoformat(),
        )
        for generated_at in generated_values:
            with self.subTest(generated_at=generated_at):
                age_seconds = stage906._age_seconds(generated_at)
                self.assertIsNotNone(age_seconds)
                self.assertGreaterEqual(age_seconds, 0.5)
                self.assertLess(age_seconds, 3.0)

    def test_stage906_snapshot_age_gate_rejects_future_invalid_and_stale(self) -> None:
        import run_qmt_roll_stage906_official_live_reconciliation_worker as stage906

        cases = (
            (0.0, True),
            (300.0, True),
            (-0.001, False),
            (300.001, False),
            (None, False),
        )
        for age_seconds, expected in cases:
            with self.subTest(age_seconds=age_seconds):
                self.assertEqual(
                    expected,
                    stage906._snapshot_age_ready(
                        age_seconds,
                        max_snapshot_age_seconds=300,
                    ),
                )

        future = (
            datetime.now().astimezone() + timedelta(seconds=1)
        ).isoformat()
        self.assertLess(stage906._age_seconds(future), 0)
        self.assertIsNone(stage906._age_seconds("not-a-timestamp"))

    def test_live_config_import_does_not_build_historical_candidate_paths(self) -> None:
        import run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest as fu_candidate

        def fail_if_called() -> Path:
            raise AssertionError("historical candidate universe should not be built during live config import")

        for module_name in [
            "qmt_roll_official_live_config",
            "qmt_roll_official_candidate_stage847_c9_config",
            "qmt_roll_official_candidate_stage819_30w_config",
            "qmt_roll_official_candidate_stage813_config",
            "qmt_roll_official_candidate_stage777_config",
        ]:
            sys.modules.pop(module_name, None)

        with patch.object(fu_candidate, "build_static18_plus_fu_universe", fail_if_called):
            module = importlib.import_module("qmt_roll_official_live_config")

        self.assertEqual(module.OFFICIAL_LIVE_ALIAS, "Stage847-C9-15w")
        self.assertEqual(
            module.OFFICIAL_LIVE_VERSION,
            "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
        )
        self.assertEqual(
            module.OFFICIAL_LIVE_RULESET_VERSION,
            "stage021_q_rollover_volume_atr_v1",
        )
        self.assertEqual(
            module.OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
            "2026-07-23",
        )
        self.assertEqual(
            "explicit_live_real_enabled",
            module.OFFICIAL_LIVE_EXECUTION_POLICY["real_submit_default"],
        )
        self.assertEqual(
            "explicit_live_real_enabled",
            module.build_official_live_manifest()["execution_policy"][
                "real_submit_default"
            ],
        )
        manifest = module.build_official_live_manifest()
        self.assertEqual(
            manifest["ruleset_version"],
            "stage021_q_rollover_volume_atr_v1",
        )
        self.assertNotIn("backtest_outputs", module.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.parts)
        self.assertIn("official_strategy_materials", module.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.parts)
        self.assertEqual(
            "ai/stage182/combined_eligibility.csv",
            manifest["ai_eligibility_logical_path"],
        )
        self.assertRegex(manifest["material_release_id"], r"^m\d{4}_")
        self.assertEqual(
            manifest["material_release_id"],
            module.OFFICIAL_LIVE_MATERIAL_RELEASE_ID,
        )
        self.assertEqual(40, len(manifest["material_release_commit"]))
        self.assertEqual(64, len(manifest["material_manifest_sha256"]))
        with self.assertRaises(AssertionError):
            dict(module.OFFICIAL_LIVE_STRATEGY_OVERRIDES)

    def test_official_live_strategy_overrides_freeze_stage021_q(self) -> None:
        import qmt_roll_official_live_config as module

        base = {"account_capital": 300_000.0, "c3_capital": 300_000.0}
        with patch.object(
            module.stage847_c9_cfg,
            "build_official_candidate_stage847_c9_overrides",
            return_value=base.copy(),
        ):
            q = module.build_official_live_strategy_overrides()

        expected_q = {
            "enable_rollover_shape_same_volume_reopen": True,
            "rollover_shape_volume_policy": "shrink_to_allowed",
            "rollover_shape_history_mode": "backwards_ratio_continuous",
            "enable_directional_30d_risk_boost": True,
            "directional_30d_risk_boost_multiplier": 1.5,
            "directional_30d_risk_adjust_long_only": False,
            "directional_30d_risk_boost_require_volume_expansion": True,
            "directional_30d_volume_ratio_threshold": 3.0,
            "enable_directional_30d_low_volume_risk_discount": True,
            "directional_30d_low_volume_ratio_threshold": 0.5,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "enable_long_signal_atr_shock_filter": True,
            "enable_short_signal_atr_shock_filter": True,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        }
        self.assertEqual(expected_q, {key: q[key] for key in expected_q})
        self.assertEqual(150_000.0, q["account_capital"])
        self.assertEqual(150_000.0, q["c3_capital"])

    def test_stage901_live_artifacts_follow_signal_input_across_process_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output_root = root / "stage909-output"
            signal_root = root / "signal-input"
            environment = dict(os.environ)
            environment.update(
                {
                    "OFFICIAL_LIVE_OUTPUT_DIR": str(output_root),
                    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(signal_root),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": (
                        f"{PORTFOLIO_DIR}{os.pathsep}"
                        f"{environment.get('PYTHONPATH', '')}"
                    ).rstrip(os.pathsep),
                }
            )
            script = "\n".join(
                [
                    "import json",
                    "import qmt_roll_official_execution_profile as profile",
                    "import qmt_roll_official_live_config as config",
                    "import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901",
                    "import run_qmt_roll_stage902_official_live_phase_d_readiness_gate as stage902",
                    "identity = stage901._official_live_identity()",
                    "payload = {",
                    "  'profile': {",
                    "    'summary': str(profile.C9_15W_PROFILE.summary_path),",
                    "    'signal': str(profile.C9_15W_PROFILE.signal_plan_path),",
                    "    'positions': str(profile.C9_15W_PROFILE.current_positions_path),",
                    "    'pending': str(profile.C9_15W_PROFILE.pending_orders_path),",
                    "  },",
                    "  'config': {",
                    "    'summary': str(config.OFFICIAL_LIVE_SUMMARY_PATH),",
                    "    'signal': str(config.OFFICIAL_LIVE_SIGNAL_PLAN_PATH),",
                    "    'positions': str(config.OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),",
                    "    'pending': str(config.OFFICIAL_LIVE_PENDING_ORDERS_PATH),",
                    "    'report': str(config.OFFICIAL_LIVE_REPORT_PATH),",
                    "  },",
                    "  'stage901': {",
                    "    'summary': str(stage901.DECISION_PATH),",
                    "    'signal': str(stage901.SIGNAL_PLAN_PATH),",
                    "    'positions': str(stage901.CURRENT_POSITIONS_PATH),",
                    "    'pending': str(stage901.PENDING_ORDERS_PATH),",
                    "    'report': str(stage901.REPORT_PATH),",
                    "  },",
                    "  'identity': identity,",
                    "  'stage902_identity_error': stage902._official_summary_identity_error(",
                    "      identity, profile=profile.C9_15W_PROFILE),",
                    "}",
                    "print('STAGE901_PATH_CONTRACT=' + json.dumps(payload, sort_keys=True))",
                ]
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=PORTFOLIO_DIR.parents[1],
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout)
        marker = "STAGE901_PATH_CONTRACT="
        contract_line = next(
            (line for line in result.stdout.splitlines() if line.startswith(marker)),
            "",
        )
        self.assertTrue(contract_line, result.stdout)
        payload = json.loads(contract_line.removeprefix(marker))
        expected = {
            "summary": str(
                signal_root
                / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_decision_"
                "stage901_stage847_c9_2026_ytd_live_shadow_v1.json"
            ),
            "signal": str(
                signal_root
                / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_signal_plan_"
                "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
            ),
            "positions": str(
                signal_root
                / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_current_positions_"
                "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
            ),
            "pending": str(
                signal_root
                / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_"
                "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
            ),
        }
        self.assertEqual(expected, payload["profile"])
        self.assertEqual(expected, {
            key: payload["config"][key]
            for key in expected
        })
        self.assertEqual(expected, {
            key: payload["stage901"][key]
            for key in expected
        })
        expected_report = str(
            signal_root
            / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_report_"
            "stage901_stage847_c9_2026_ytd_live_shadow_v1.md"
        )
        self.assertEqual(expected_report, payload["config"]["report"])
        self.assertEqual(expected_report, payload["stage901"]["report"])
        self.assertEqual(
            {
                "execution_profile": "c9-15w",
                "official_live_version": (
                    "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
                ),
                "capital": 150_000.0,
                "capital_label": "15w",
            },
            payload["identity"],
        )
        self.assertEqual("", payload["stage902_identity_error"])


if __name__ == "__main__":
    unittest.main()
