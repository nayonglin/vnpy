from __future__ import annotations

import importlib
import sys
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
MODULE_NAME = "stage136_ap010_canary_fill_window_backfill"
MODULE_PATH = TOOLS_DIR / f"{MODULE_NAME}.py"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"production module missing: {MODULE_PATH}")
    return importlib.import_module(MODULE_NAME)


class Stage136PlanTest(unittest.TestCase):
    def test_plan_is_single_fixed_ap010_order_window(self) -> None:
        s136 = _module()

        plan = s136.build_plan(Path("/tmp/stage136"), Path("/tmp/final"))

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan.loc[0, "contract_vt"], "AP010.CZCE")
        self.assertEqual(plan.loc[0, "download_start_datetime"], "2020-09-01 20:55:00")
        self.assertEqual(plan.loc[0, "download_end_datetime"], "2020-09-02 15:15:00")
        self.assertTrue(str(plan.loc[0, "output_path"]).endswith("CZCE/AP010_minute_backtest.csv"))

    def test_decision_requires_download_temp_publish_and_post_audit(self) -> None:
        s136 = _module()
        ready = s136.make_decision(
            pd.DataFrame([{"status": "downloaded", "sha256": "abc"}]),
            pd.DataFrame([{"strict_ready": True, "sha256": "abc"}]),
            pd.DataFrame([{"action": "published", "published_exists": True, "published_sha256": "abc"}]),
            pd.DataFrame([{"strict_ready": True, "sha256": "abc"}]),
        )
        failed = s136.make_decision(
            pd.DataFrame([{"status": "downloaded", "sha256": "abc"}]),
            pd.DataFrame([{"strict_ready": True, "sha256": "abc"}]),
            pd.DataFrame([{"action": "published", "published_exists": True, "published_sha256": "abc"}]),
            pd.DataFrame([{"strict_ready": True, "sha256": "different"}]),
        )

        self.assertTrue(ready["ready_for_stage135_canary"])
        self.assertFalse(failed["ready_for_stage135_canary"])
        self.assertEqual(failed["decision"], "stage136_ap010_fill_window_blocked_keep_stage135_paused")
        self.assertFalse(failed["sha_chain_ready"])

    def test_closed_state_quality_rejects_all_open_snapshots(self) -> None:
        s136 = _module()
        stale = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [100.0, 101.0],
                "low": [100.0, 101.0],
                "close": [100.0, 101.0],
                "volume": [0.0, 0.0],
            }
        )
        closed = stale.copy()
        closed.loc[0, ["high", "close", "volume"]] = [102.0, 101.5, 10.0]

        stale_audit = s136.audit_closed_state_quality(stale)
        closed_audit = s136.audit_closed_state_quality(closed)

        self.assertFalse(stale_audit["closed_state_ready"])
        self.assertTrue(closed_audit["closed_state_ready"])


if __name__ == "__main__":
    unittest.main()
