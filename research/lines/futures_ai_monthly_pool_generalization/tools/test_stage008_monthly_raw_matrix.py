import unittest
import ast
from copy import deepcopy
import json

import pandas as pd
import numpy as np

from training_source_profile import apply_training_overrides
from stage008_monthly_raw_matrix import ROOT, choose_representative, strict_history, frozen_signal_host, signal_fields


class SourceProfileTests(unittest.TestCase):
    def test_half_r_and_retry_switch_is_off(self):
        base = dict(enable_stage847_half_r_stop_retry=True, enable_stage827_intraday_c2_stop=True)
        changed = apply_training_overrides(base)
        self.assertIs(changed["enable_stage847_half_r_stop_retry"], False)
        self.assertTrue(changed["enable_stage827_intraday_c2_stop"])
        self.assertTrue(base["enable_stage847_half_r_stop_retry"])
        self.assertEqual(set(changed), set(base))

    def test_frozen_method_adapter_and_hardblock_schema(self):
        host, _ = frozen_signal_host()
        x = np.arange(41, dtype=float) + 100
        frame = pd.DataFrame(dict(open=x, high=x+2, low=x-2, close=x+1, volume=100., close_oi=200.))
        fields = signal_fields(host, frame)
        self.assertTrue(fields["input_ready"])
        self.assertTrue(fields["long_hardblock_known"])
        self.assertTrue(fields["short_hardblock_known"])
        self.assertIs(host.enable_stage847_half_r_stop_retry, False)

    def test_actual_frozen_half_r_hook_skips_retry_but_preserves_c2(self):
        current = json.loads((ROOT / "official_strategy_materials/CURRENT.json").read_text())
        file = ROOT / "official_strategy_materials" / current["strategy_version"] / "releases" / current["release_id"] / "payload/examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py"
        tree = ast.parse(file.read_text())
        original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "QmtRollPortfolioStrategyStage847C9StopRetry")
        method = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == "stage827_intraday_exit_after_open_trade")
        class Base:
            def stage827_intraday_exit_after_open_trade(self, trade):
                self.c2_calls += 1
                return {"probe": "C2"}
        klass = ast.ClassDef(name="Probe", bases=[ast.Name(id="Base", ctx=ast.Load())], keywords=[], body=[deepcopy(method)], decorator_list=[])
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), klass], type_ignores=[])
        namespace = {"Base": Base}
        exec(compile(ast.fix_missing_locations(module), str(file), "exec"), namespace)
        host = namespace["Probe"]()
        host.enable_stage847_half_r_stop_retry = apply_training_overrides({"enable_stage847_half_r_stop_retry": True})["enable_stage847_half_r_stop_retry"]
        host.c2_calls = 0
        def forbidden_half_r_retry(trade):
            self.fail("disabled half-R retry callback was invoked")
        host._stage847_stop_retry_event_after_open_trade = forbidden_half_r_retry
        self.assertEqual(host.stage827_intraday_exit_after_open_trade(object()), {"probe": "C2"})
        self.assertEqual(host.c2_calls, 1)


class MatrixInputTests(unittest.TestCase):
    def candidates(self):
        return pd.DataFrame([
            dict(contract_epoch_id="X.P.202401", trade_date="2024-01-31", volume=10., close_oi=30.),
            dict(contract_epoch_id="X.P.202402", trade_date="2024-01-31", volume=10., close_oi=50.),
            dict(contract_epoch_id="X.P.202403", trade_date="2024-02-01", volume=999., close_oi=999.)])

    def test_selection_uses_only_same_day_volume_then_oi(self):
        selected = choose_representative(self.candidates(), pd.Timestamp("2024-01-31"))
        self.assertEqual(selected["contract_epoch_id"], "X.P.202402")

    def test_tie_uses_lexicographic_epoch_and_is_permutation_invariant(self):
        frame = self.candidates()
        frame.loc[0, "close_oi"] = 50.
        a = choose_representative(frame, pd.Timestamp("2024-01-31"))
        b = choose_representative(frame.iloc[::-1], pd.Timestamp("2024-01-31"))
        self.assertEqual(a["contract_epoch_id"], "X.P.202401")
        self.assertEqual(a["contract_epoch_id"], b["contract_epoch_id"])

    def test_no_current_observation_does_not_use_future(self):
        self.assertIsNone(choose_representative(self.candidates(), pd.Timestamp("2024-01-30")))

    def history(self):
        dates = pd.bdate_range("2024-01-01", periods=50)
        frame = pd.DataFrame(dict(trade_date=dates, open=100., high=102., low=99., close=101., volume=10., close_oi=20.))
        return frame, dates

    def test_missing_calendar_day_cannot_be_replaced_with_older_bar(self):
        frame, dates = self.history()
        with self.assertRaisesRegex(ValueError, "calendar"):
            strict_history(frame.drop(index=20), dates, dates[45])

    def test_history_has_41_same_calendar_days_and_no_future(self):
        frame, dates = self.history()
        result = strict_history(frame, dates, dates[45])
        self.assertEqual(len(result), 41)
        self.assertEqual(result.trade_date.max(), dates[45])
        self.assertEqual(result.trade_date.min(), dates[5])

    def test_duplicate_and_bad_ohlc_are_rejected(self):
        frame, dates = self.history()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            strict_history(pd.concat([frame, frame.iloc[[10]]]), dates, dates[45])
        frame.loc[10, "low"] = 500.
        with self.assertRaisesRegex(ValueError, "OHLC"):
            strict_history(frame, dates, dates[45])


if __name__ == "__main__":
    unittest.main()
