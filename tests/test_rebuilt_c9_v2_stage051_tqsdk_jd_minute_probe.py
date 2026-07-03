from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage051_tqsdk_jd_minute_probe as s051


class Stage051TqSdkJdMinuteProbeTest(unittest.TestCase):
    def test_vt_symbol_maps_to_tqsdk_symbol_without_changing_case(self) -> None:
        self.assertEqual(s051.to_tqsdk_symbol("jd2608.DCE"), "DCE.jd2608")
        self.assertEqual(s051.to_tqsdk_symbol("SH609.CZCE"), "CZCE.SH609")

    def test_probe_plan_prioritizes_short_jd_gap_for_small_network_probe(self) -> None:
        manifest = pd.DataFrame(
            {
                "contract_vt": ["cu2608.SHFE", "jd2005.DCE", "jd2608.DCE"],
                "product_vt_symbol": ["cu.SHFE", "jd.DCE", "jd.DCE"],
                "request_start_date": ["2026-06-24", "2020-01-02", "2026-06-15"],
                "request_end_date": ["2026-06-30", "2020-04-08", "2026-06-30"],
                "observed_price_rows": [5, 63, 11],
                "priority": ["P1_tail_contract_gap", "P0_jd_true_carry_blocker", "P0_jd_true_carry_blocker"],
            }
        )

        plan = s051.build_probe_plan(manifest, max_symbols=2)

        self.assertEqual(plan["contract_vt"].tolist(), ["jd2608.DCE", "jd2005.DCE"])
        self.assertEqual(plan["tq_symbol"].tolist(), ["DCE.jd2608", "DCE.jd2005"])
        self.assertTrue(plan["probe_start_datetime"].str.endswith("21:00:00").all())
        self.assertTrue(plan["probe_end_datetime"].str.endswith("09:10:00").all())

    def test_readiness_requires_module_credentials_and_probe_plan(self) -> None:
        ready = s051.classify_probe_readiness(
            module_audit={"module_importable": True, "has_tqapi": True, "has_tqauth": True, "has_tqsim": True},
            credential_audit={"settings_datafeed_username_present": True, "settings_datafeed_password_present": True},
            probe_plan=pd.DataFrame([{"contract_vt": "jd2608.DCE"}]),
            network_enabled=True,
        )
        self.assertEqual(ready["readiness"], "ready_for_tqsdk_backtest_probe")

        blocked = s051.classify_probe_readiness(
            module_audit={"module_importable": True, "has_tqapi": True, "has_tqauth": True, "has_tqsim": True},
            credential_audit={"settings_datafeed_username_present": False, "settings_datafeed_password_present": True},
            probe_plan=pd.DataFrame([{"contract_vt": "jd2608.DCE"}]),
            network_enabled=True,
        )
        self.assertEqual(blocked["readiness"], "blocked_missing_tqsdk_credentials")


if __name__ == "__main__":
    unittest.main()
