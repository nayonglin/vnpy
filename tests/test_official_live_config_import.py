from __future__ import annotations

import importlib
from pathlib import Path
import sys
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
        with self.assertRaises(AssertionError):
            dict(module.OFFICIAL_LIVE_STRATEGY_OVERRIDES)


if __name__ == "__main__":
    unittest.main()
