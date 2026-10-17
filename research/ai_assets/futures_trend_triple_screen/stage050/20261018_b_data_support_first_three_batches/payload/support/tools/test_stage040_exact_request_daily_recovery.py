"""Exact actual request, fixed DB OI meaning and completion; no network."""
import copy
import json
from pathlib import Path
import unittest

import pandas as pd

try:
    import stage040_exact_request_daily_recovery as module
except ImportError:
    module = None


class ExactDailyRecoveryTests(unittest.TestCase):
    def test_exact_request_readonly_six_fields_and_successor(self):
        self.assertIsNotNone(module, "exact daily recovery adapter is missing")
        original = {str(p): module.old.sha256(p) for p in [module.DATABASE, module.REQUEST]}
        targets, excluded = module.frozen_inputs()
        self.assertEqual(len(targets), 1)
        self.assertEqual(len(excluded), 0)
        row = targets.iloc[0]
        self.assertEqual((row.vt_symbol, row.trade_date, row.requirement_kind),
                         ("SM005.CZCE", "2020-01-06", "full_session"))
        self.assertEqual([float(row[f]) for f in module.DB_FIELDS],
                         [6378., 6380., 6262., 6280., 76307., 68372.])
        request = json.loads(module.REQUEST.read_text())
        changed = copy.deepcopy(request)
        changed["requirements"][0]["vt_symbol"] = "KQ.m@CZCE.SM"
        with self.assertRaises(ValueError):
            module.exact_target(changed)
        snapshot = pd.DataFrame([dict(id=i, datetime=int(pd.Timestamp(day, tz="Asia/Shanghai").value),
            open=6378., high=6380., low=6262., close=6280., volume=76307., open_oi=68372., close_oi=70000.)
            for i, day in [(10, "2020-01-06"), (11, "2020-01-07")]])
        accepted, _ = module.qualify_daily_snapshot("SM005.CZCE", snapshot, targets)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(int(accepted.iloc[0].successor_id), 11)
        rejected, audit = module.qualify_daily_snapshot("SM005.CZCE", snapshot.iloc[:1], targets)
        self.assertTrue(rejected.empty)
        self.assertEqual(audit.iloc[0].reason, "no_forward_successor")
        swapped = snapshot.copy()
        swapped.loc[0, ["open_oi", "close_oi"]] = [70000., 68372.]
        rejected, audit = module.qualify_daily_snapshot("SM005.CZCE", swapped, targets)
        self.assertTrue(rejected.empty)
        self.assertEqual(audit.iloc[0].mismatch_fields, "open_oi")
        self.assertEqual(original, {p: module.old.sha256(p) for p in original})


if __name__ == "__main__":
    unittest.main()
