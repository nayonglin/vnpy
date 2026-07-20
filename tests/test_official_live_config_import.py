from __future__ import annotations

import importlib
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
            "fail_closed",
            module.OFFICIAL_LIVE_EXECUTION_POLICY["real_submit_default"],
        )
        with self.assertRaises(AssertionError):
            dict(module.OFFICIAL_LIVE_STRATEGY_OVERRIDES)

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
