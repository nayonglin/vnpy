import importlib.util
from pathlib import Path
import unittest

import pandas as pd

from stage012_c2_reference_frontier import ROOT, initial_risk, classify_daily, parse_boolean, frozen_initial_stop_host
from types import SimpleNamespace


class C2IdentificationTests(unittest.TestCase):
    def test_long_four_cases(self):
        for high, low, expected in [(109,91,"neither"),(109,89,"stop_only"),(111,91,"confirm_only"),(111,89,"both_unidentified")]:
            self.assertEqual(classify_daily("long",100,high,low,100,10)["daily_case"], expected)

    def test_short_four_cases(self):
        self.assertEqual(classify_daily("short",100,109,91,100,10)["daily_case"], "neither")
        self.assertEqual(classify_daily("short",100,111,91,100,10)["daily_case"], "stop_only")
        self.assertEqual(classify_daily("short",100,109,89,100,10)["daily_case"], "confirm_only")
        self.assertEqual(classify_daily("short",100,111,89,100,10)["daily_case"], "both_unidentified")

    def test_equal_threshold_counts_as_touch(self):
        self.assertEqual(classify_daily("long",100,110,90,100,10)["daily_case"], "both_unidentified")

    def test_wrong_side_gap_is_not_rescued_by_abs(self):
        self.assertEqual(initial_risk("long",90,95,1)["risk_status"], "gap_wrong_side_or_zero")
        self.assertEqual(initial_risk("short",110,105,1)["risk_status"], "gap_wrong_side_or_zero")

    def test_subtick_risk_is_not_floored_into_valid_case(self):
        self.assertEqual(initial_risk("long",100,99.9,1)["risk_status"], "below_configured_tick")
        self.assertEqual(initial_risk("long",100,99,1)["risk_status"], "valid")

    def test_invalid_prices_do_not_mean_no_stop(self):
        with self.assertRaisesRegex(ValueError, "OHLC"):
            classify_daily("long",100,99,101,100,10)

    def test_daily_both_contains_two_current_kernel_paths(self):
        path=ROOT/"examples/portfolio_backtesting/qmt_roll_intraday_execution.py"
        spec=importlib.util.spec_from_file_location("c2_kernel_probe",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        stop_first=pd.DataFrame([dict(open=100,high=101,low=89,close=95),dict(open=95,high=111,low=94,close=100)])
        confirm_first=pd.DataFrame([dict(open=100,high=111,low=99,close=105),dict(open=105,high=106,low=89,close=100)])
        self.assertEqual(module.first_stop(stop_first,90,110,long=True)[0],0)
        self.assertEqual(module.first_stop(confirm_first,90,110,long=True)[0],-1)
        result=classify_daily("long",100,111,89,100,10)
        self.assertEqual(set(result["possible_actions"]),{"c2_stop","confirmation_disarms_c2"})
        self.assertFalse(result["daily_action_identified"])

    def test_csv_false_does_not_become_truthy(self):
        self.assertEqual(parse_boolean(pd.Series(["True","False"])).tolist(),[True,False])
        with self.assertRaisesRegex(ValueError,"boolean"):
            parse_boolean(pd.Series(["unknown"]))

    def test_frozen_initial_stop_override_and_short_base(self):
        host, _=frozen_initial_stop_host()
        bar=SimpleNamespace(close_price=100.,low_price=99.,high_price=103.)
        history=pd.DataFrame([dict(close=100.,low=99.,high=103.)]*3)
        self.assertEqual(host._entry_stop_price("long",bar,history,True),99.)
        self.assertEqual(host._entry_stop_price("short",bar,history,True),102.)


if __name__ == "__main__":
    unittest.main()
