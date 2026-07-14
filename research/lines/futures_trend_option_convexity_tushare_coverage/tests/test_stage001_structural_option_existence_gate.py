from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "stage001_structural_option_existence_gate.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("stage001_structural_option_existence_gate", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StructuralOptionExistenceGateTest(unittest.TestCase):
    def test_structural_gate_reproduces_frozen_2022_ceiling(self) -> None:
        module = load_module()
        ledger, product_summary, decision = module.evaluate()

        self.assertEqual(len(ledger), 16)
        self.assertEqual(int(ledger["same_underlying_option_existed"].sum()), 4)
        self.assertTrue(decision["input_hash_ok"])
        self.assertEqual(decision["structural_event_coverage_ratio"], 0.25)
        self.assertAlmostEqual(decision["critical_total_original_risk_amount"], 3_143_984.2, places=6)
        self.assertAlmostEqual(decision["structurally_eligible_risk_amount"], 831_960.0, places=6)
        self.assertAlmostEqual(
            decision["structural_risk_coverage_ratio"], 831_960.0 / 3_143_984.2, places=12
        )
        self.assertEqual(decision["decision"], "CLOSE_LINE_MARKET_STRUCTURE_INELIGIBLE")
        self.assertFalse(decision["ready_for_option_strategy_ab"])

        key = product_summary[
            product_summary["product_vt_symbol"].isin(module.KEY_PRODUCTS)
        ]
        self.assertEqual(len(key), len(module.KEY_PRODUCTS))
        self.assertTrue(key["event_coverage_ratio"].eq(0.0).all())

    def test_output_is_sanitized_and_fail_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            paths = module.write_outputs(Path(directory))
            decision_text = paths["decision"].read_text(encoding="utf-8")
            decision = json.loads(decision_text)

            self.assertNotIn("TUSHARE_TOKEN", decision_text)
            self.assertNotIn("token_length", decision_text)
            self.assertEqual(decision["tushare_smoke_status"], "invalid_token_no_data_downloaded")
            self.assertFalse(all(decision["gates"].values()))
            self.assertTrue(paths["ledger"].exists())
            self.assertTrue(paths["product_summary"].exists())
            self.assertTrue(paths["report"].exists())


if __name__ == "__main__":
    unittest.main()
