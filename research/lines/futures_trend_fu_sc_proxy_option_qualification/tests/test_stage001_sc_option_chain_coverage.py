from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "stage001_sc_option_chain_coverage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage001_sc_option_chain_coverage", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extracted_fetcher(event, _max_seconds):
    underlying = str(event["tqsdk_underlying"])
    symbol = underlying + "C500"
    untouched = pd.DataFrame([{"instrument_id": symbol, "underlying_symbol": underlying}])
    normalized = untouched.copy()
    return "extracted", [symbol], untouched, normalized, {"integrity_pass": True}, "", 0.01


class ScOptionChainCoverageTest(unittest.TestCase):
    def test_query_plan_uses_all_events_and_t1_sc_mapping(self) -> None:
        module = load_module()
        plan, hashes = module.build_query_plan()

        self.assertEqual(len(plan), 32)
        self.assertEqual(plan["event_id"].nunique(), 32)
        self.assertEqual(int(plan["is_core_window"].sum()), 6)
        self.assertTrue(plan["selection_date"].lt(plan["entry_date"]).all())
        self.assertTrue(plan["tqsdk_underlying"].str.startswith("INE.sc").all())
        self.assertIn("stage132_producer_sha256", hashes)

    def test_canary_failure_stops_remaining_events(self) -> None:
        module = load_module()
        calls = []

        def failing_fetcher(event, max_seconds):
            calls.append(str(event["event_id"]))
            if len(calls) == 1:
                return "empty_chain", [], pd.DataFrame(), pd.DataFrame(), {}, "", 0.01
            return extracted_fetcher(event, max_seconds)

        with tempfile.TemporaryDirectory() as directory:
            result = module.run(
                output_dir=Path(directory), enable_network=True, fetcher=failing_fetcher
            )
        self.assertEqual(len(calls), 6)
        self.assertEqual(result["decision"]["decision"], "CLOSE_LINE_OPTION_CHAIN_INELIGIBLE")
        self.assertLess(result["decision"]["cache_valid_count"], 32)
        self.assertFalse(result["decision"]["ready_for_option_strategy_ab"])

    def test_all_extracted_only_allows_execution_data_predecl(self) -> None:
        module = load_module()
        calls = []

        def recording_fetcher(event, max_seconds):
            calls.append(str(event["event_id"]))
            return extracted_fetcher(event, max_seconds)

        with tempfile.TemporaryDirectory() as directory:
            result = module.run(
                output_dir=Path(directory), enable_network=True, fetcher=recording_fetcher
            )
        self.assertEqual(len(calls), 32)
        self.assertEqual(
            result["decision"]["decision"], "ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY"
        )
        self.assertEqual(result["decision"]["extracted_event_count"], 32)
        self.assertTrue(result["decision"]["ready_for_stage002_execution_data_predecl"])
        self.assertFalse(result["decision"]["ready_for_option_strategy_ab"])
        self.assertFalse(result["decision"]["premium_or_bar_downloaded"])


if __name__ == "__main__":
    unittest.main()

