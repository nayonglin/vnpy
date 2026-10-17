"""Needed-session qualification invariants, synthetic fixtures only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

try:
    import stage011_needed_local_completed as module
except ImportError:
    module = None

import pandas as pd


class NeededCompletedTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module, "Stage011 needed-source qualifier is not implemented")
        self.grid = pd.date_range("2020-05-18 09:00", periods=3, freq="min")
        self.rows = pd.DataFrame(dict(vt_symbol=["rb2010.SHFE"]*3,
            bar_datetime=self.grid, open=[10.,11.,12.], high=[12.,13.,14.],
            low=[9.,10.,11.], close=[11.,12.,13.], volume=[2.,3.,4.],
            open_oi=[20.,21.,22.], close_oi=[21.,22.,23.]))
        self.empty = self.rows.iloc[:0].copy()
        self.daily = dict(open=10., high=14., low=9., close=13.,
            volume=9., open_oi=20., close_oi=23.)

    def test_consistent_sources_stitch_without_replacing_existing_key(self):
        existing = self.rows.iloc[:1].copy()
        before = existing.copy(deep=True)
        added, audit = module.qualify_needed_session(
            {"a": self.rows.iloc[1:2], "b": self.rows.iloc[1:]},
            self.grid, self.daily, existing, "full_session")
        self.assertEqual(audit["status"], "accepted")
        self.assertEqual(list(added.bar_datetime), list(self.grid[1:]))
        self.assertEqual(list(added.close), [12.,13.])
        pd.testing.assert_frame_equal(existing, before)

    def test_cross_source_conflict_quarantines_whole_session(self):
        changed = self.rows.iloc[1:].copy()
        changed.loc[1,"volume"] = 30.
        added, audit = module.qualify_needed_session(
            {"a": self.rows, "b": changed}, self.grid, self.daily,
            self.empty, "full_session")
        self.assertTrue(added.empty)
        self.assertEqual(audit["reason"], "completed_source_conflict")
        self.assertEqual(audit["conflicting_minutes"], 1)

    def test_existing_conflict_is_never_overwritten(self):
        existing = self.rows.iloc[:1].copy()
        existing.loc[0,"close"] = 10.5
        added, audit = module.qualify_needed_session(
            {"a":self.rows}, self.grid, self.daily, existing, "anchor")
        self.assertTrue(added.empty)
        self.assertEqual(audit["reason"], "base_overlap_conflict")
        self.assertEqual(float(existing.iloc[0].close), 10.5)

    def test_missing_csv_or_any_of_seven_fields_rejects_without_db_fallback(self):
        for daily in (None, {k:v for k,v in self.daily.items() if k!="open_oi"}):
            with self.subTest(daily=daily):
                added, audit = module.qualify_needed_session(
                    {"a":self.rows}, self.grid, daily, self.empty, "full_session")
                self.assertTrue(added.empty)
                self.assertEqual(audit["reason"], "required_daily_csv_seven_fields_missing")

    def test_anchor_still_requires_whole_session_validation(self):
        added, audit = module.qualify_needed_session(
            {"a":self.rows.iloc[:1]}, self.grid, self.daily, self.empty, "anchor")
        self.assertTrue(added.empty)
        self.assertEqual(audit["reason"], "incomplete_session")
        self.assertTrue(module.requirement_satisfied(self.rows.iloc[:1], self.grid, "anchor"))
        self.assertFalse(module.requirement_satisfied(self.rows.iloc[:1], self.grid, "full_session"))

    def test_bound_file_sha_rejects_changed_source_before_payload_is_used(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/"completed.csv"
            payload = self.rows.to_csv(index=False).encode()
            path.write_bytes(payload)
            accepted, audit = module.read_bound_minute_source(
                path, hashlib.sha256(payload).hexdigest(), "rb2010.SHFE")
            self.assertEqual(len(accepted), 3)
            self.assertEqual(audit["status"], "accepted_source_bytes")
            path.write_bytes(payload+b"\n")
            rejected, audit = module.read_bound_minute_source(
                path, hashlib.sha256(payload).hexdigest(), "rb2010.SHFE")
            self.assertIsNone(rejected)
            self.assertEqual(audit["reason"], "old_manifest_sha_mismatch")


if __name__ == "__main__":
    unittest.main()
