from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage018_low_corr_leg_inventory_audit as s018


class Stage018LowCorrLegInventoryAuditTest(unittest.TestCase):
    def test_inventory_file_records_missing_and_present_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "present.csv"
            existing.write_text("date,value\n2026-01-01,1\n", encoding="utf-8")
            missing = Path(tmp) / "missing.csv"

            present_row = s018.inventory_file("present_input", existing, required_for="demo")
            missing_row = s018.inventory_file("missing_input", missing, required_for="demo")

        self.assertTrue(present_row["exists"])
        self.assertGreater(present_row["size_bytes"], 0)
        self.assertEqual(present_row["status"], "present")
        self.assertFalse(missing_row["exists"])
        self.assertEqual(missing_row["size_bytes"], 0)
        self.assertEqual(missing_row["status"], "missing")

    def test_assess_reuse_gate_blocks_direct_xsmom_reuse_when_raw_inputs_are_missing(self) -> None:
        inventory = [
            {"name": "stage345_product_returns", "group": "xsmom_raw_input", "status": "missing"},
            {"name": "stage345_satellite_daily", "group": "xsmom_raw_input", "status": "missing"},
            {"name": "stage167_c9_curves", "group": "current_c9", "status": "present"},
            {"name": "stage167_c9_curves", "group": "current_c9_margin", "status": "present"},
        ]

        decision = s018.assess_reuse_gate(inventory)

        self.assertFalse(decision["can_directly_reuse_old_xsmom_outputs"])
        self.assertFalse(decision["can_rebuild_standalone_xsmom_now"])
        self.assertTrue(decision["current_c9_curve_margin_available"])
        self.assertEqual(decision["decision"], "stage018_rebuild_xsmom_inputs_first_keep_readonly")

    def test_detect_required_columns_marks_c9_margin_fields_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "curves.csv"
            path.write_text(
                "date,requested_start_month,account_equity,total_margin_exact,broker10_margin_to_equity_pct\n"
                "2026-01-01,2026-01,150000,10000,7.3333\n",
                encoding="utf-8",
            )

            row = s018.inventory_file(
                "stage167_c9_curves",
                path,
                required_for="current C9 curve and margin audit",
                required_columns=("account_equity", "total_margin_exact", "broker10_margin_to_equity_pct"),
                group="current_c9_margin",
            )

        self.assertEqual(row["status"], "present")
        self.assertEqual(row["missing_columns"], "")
        self.assertTrue(row["has_required_columns"])


if __name__ == "__main__":
    unittest.main()
