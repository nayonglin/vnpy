from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "stage001_lag1_granger_qualification.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage001_lag1_granger_qualification", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Lag1GrangerQualificationTest(unittest.TestCase):
    def test_t1_selection_uses_prior_oi_and_same_contract_close(self) -> None:
        module = load_module()
        bars = pd.DataFrame(
            [
                ["rb2201", "SHFE", "2022-01-03", 100.0, 100.0],
                ["rb2205", "SHFE", "2022-01-03", 200.0, 80.0],
                ["rb2201", "SHFE", "2022-01-04", 110.0, 10.0],
                ["rb2205", "SHFE", "2022-01-04", 240.0, 1000.0],
                ["rb2201", "SHFE", "2022-01-05", 121.0, 10.0],
                ["rb2205", "SHFE", "2022-01-05", 252.0, 1000.0],
            ],
            columns=["symbol", "exchange", "date", "close", "open_interest"],
        )

        ledger, audit = module.build_t1_product_returns(bars, "rb.SHFE")

        self.assertEqual(ledger.iloc[0]["selected_symbol"], "rb2201")
        self.assertAlmostEqual(float(ledger.iloc[0]["return"]), 0.10)
        self.assertEqual(ledger.iloc[1]["selected_symbol"], "rb2205")
        self.assertAlmostEqual(float(ledger.iloc[1]["return"]), 0.05)
        self.assertEqual(audit["cross_contract_direct_return_count"], 0)
        self.assertEqual(audit["selection_date_not_before_return_date"], 0)

    def test_highest_oi_contract_with_invalid_close_is_not_replaced(self) -> None:
        module = load_module()
        bars = pd.DataFrame(
            [
                ["rb2201", "SHFE", "2022-01-03", 0.0, 1000.0],
                ["rb2205", "SHFE", "2022-01-03", 200.0, 900.0],
                ["rb2201", "SHFE", "2022-01-04", 110.0, 800.0],
                ["rb2205", "SHFE", "2022-01-04", 210.0, 1000.0],
            ],
            columns=["symbol", "exchange", "date", "close", "open_interest"],
        )

        ledger, audit = module.build_t1_product_returns(bars, "rb.SHFE")

        self.assertEqual(ledger.iloc[0]["selected_symbol"], "rb2201")
        self.assertEqual(ledger.iloc[0]["status"], "invalid_prior_close")
        self.assertTrue(pd.isna(ledger.iloc[0]["return"]))
        self.assertEqual(audit["invalid_prior_close_rows"], 1)

    def test_t1_oi_tie_breaks_by_contract_symbol(self) -> None:
        module = load_module()
        bars = pd.DataFrame(
            [
                ["rb2205", "SHFE", "2022-01-03", 200.0, 1000.0],
                ["rb2201", "SHFE", "2022-01-03", 100.0, 1000.0],
                ["rb2201", "SHFE", "2022-01-04", 110.0, 900.0],
                ["rb2205", "SHFE", "2022-01-04", 210.0, 1000.0],
            ],
            columns=["symbol", "exchange", "date", "close", "open_interest"],
        )

        ledger, _ = module.build_t1_product_returns(bars, "rb.SHFE")

        self.assertEqual(ledger.iloc[0]["selected_symbol"], "rb2201")
        self.assertEqual(int(ledger.iloc[0]["top_oi_tie_count"]), 2)

    def test_pair_history_is_strictly_before_entry_and_fixed_length(self) -> None:
        module = load_module()
        dates = pd.bdate_range("2021-01-01", periods=140)
        panel = pd.DataFrame(
            {
                "return_date": dates,
                "leader.DCE": np.linspace(-0.02, 0.02, len(dates)),
                "target.SHFE": np.linspace(0.01, -0.01, len(dates)),
            }
        )
        entry_date = dates[-1]

        history = module.extract_pair_history(
            panel,
            target="target.SHFE",
            leader="leader.DCE",
            entry_date=entry_date,
            lookback=132,
        )

        self.assertEqual(len(history), 132)
        self.assertLess(pd.Timestamp(history["return_date"].max()), entry_date)
        self.assertNotIn(entry_date, set(history["return_date"]))

    def test_lag1_granger_detects_forward_leader_without_reverse_edge(self) -> None:
        module = load_module()
        rng = np.random.default_rng(20260713)
        leader = rng.normal(0.0, 1.0, 260)
        target = np.zeros(260)
        for index in range(1, len(target)):
            target[index] = 0.85 * leader[index - 1] + rng.normal(0.0, 0.12)
        frame = pd.DataFrame({"target": target[-132:], "leader": leader[-132:]})

        forward = module.fit_lag1_granger(frame, target_col="target", leader_col="leader")
        reverse = module.fit_lag1_granger(frame, target_col="leader", leader_col="target")

        self.assertLess(float(forward["full_pvalue"]), 1e-8)
        self.assertGreater(float(forward["full_leader_coef"]), 0.0)
        self.assertGreater(float(forward["early_leader_coef"]), 0.0)
        self.assertGreater(float(forward["late_leader_coef"]), 0.0)
        self.assertGreater(float(reverse["full_pvalue"]), 0.05)

    def test_global_bh_and_half_sign_stability_are_both_required(self) -> None:
        module = load_module()
        pairs = pd.DataFrame(
            {
                "event_id": ["e1", "e1", "e2"],
                "leader_product": ["a.DCE", "b.DCE", "c.DCE"],
                "full_pvalue": [0.001, 0.04, 0.50],
                "full_leader_coef": [0.2, 0.3, -0.1],
                "early_leader_coef": [0.1, -0.2, -0.1],
                "late_leader_coef": [0.3, 0.2, -0.2],
                "history_complete": [1, 1, 1],
                "granger_status": ["ok", "ok", "ok"],
            }
        )

        audited = module.apply_global_fdr_and_stability(pairs, alpha=0.05)

        self.assertEqual(audited["fdr_reject"].tolist(), [1, 0, 0])
        self.assertEqual(audited["half_sign_stable"].tolist(), [1, 0, 1])
        self.assertEqual(audited["stable_incoming_edge"].tolist(), [1, 0, 0])

    def test_global_fdr_excludes_non_ok_model_rows(self) -> None:
        module = load_module()
        pairs = pd.DataFrame(
            {
                "full_pvalue": [1e-12, 0.04],
                "full_leader_coef": [0.2, 0.2],
                "early_leader_coef": [0.2, 0.2],
                "late_leader_coef": [0.2, 0.2],
                "history_complete": [1, 1],
                "granger_status": ["model_error", "ok"],
            }
        )

        audited = module.apply_global_fdr_and_stability(pairs, alpha=0.05)

        self.assertEqual(audited["fdr_reject"].tolist(), [0, 1])
        self.assertTrue(pd.isna(audited.iloc[0]["fdr_qvalue"]))

    def test_writer_accepts_evaluate_result_key_contract(self) -> None:
        module = load_module()
        decision = {
            "decision": "CLOSE_LINE_LAG1_GRANGER_NETWORK_INELIGIBLE",
            "event_count": 1,
            "event_2022_count": 0,
            "universe_product_count": 57,
            "target_product_count": 1,
            "pair_test_rows": 1,
            "complete_pair_rows": 1,
            "valid_global_bh_rows": 1,
            "raw_pvalue_min": 0.5,
            "fdr_qvalue_min": 0.5,
            "fdr_reject_rows": 0,
            "stable_incoming_edge_rows": 0,
            "target_history_complete_count": 1,
            "qualified_event_count": 0,
            "qualified_event_2022_count": 0,
            "minimum_year_qualified_event_rate": 0.0,
        }
        event_summary = pd.DataFrame(
            [
                {
                    "event_id": "e1",
                    "entry_date": pd.Timestamp("2022-01-03"),
                    "target_product": "rb.SHFE",
                    "target_history_count": 132,
                    "complete_leader_count": 56,
                    "stable_incoming_edge_count": 0,
                    "event_qualified": 0,
                }
            ]
        )
        result = {
            "decision": decision,
            "gate_matrix": pd.DataFrame(
                [{"gate_id": "g", "evidence": 0.0, "threshold": 1.0, "passed": 0}]
            ),
            "product_audit": pd.DataFrame([{"product_vt_symbol": "rb.SHFE"}]),
            "selection_ledger": pd.DataFrame([{"status": "ok"}]),
            "return_panel": pd.DataFrame([{"return_date": "2022-01-03", "rb.SHFE": 0.01}]),
            "pair_ledger": pd.DataFrame([{"event_id": "e1"}]),
            "event_summary": event_summary,
            "year_summary": pd.DataFrame(
                [{"event_year": 2022, "event_count": 1, "qualified_event_rate": 0.0}]
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = module.write_outputs(result, Path(directory))
            self.assertTrue(all(Path(path).exists() for path in paths.values()))


if __name__ == "__main__":
    unittest.main()
