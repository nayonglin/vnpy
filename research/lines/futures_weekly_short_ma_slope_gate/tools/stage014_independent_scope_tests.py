import unittest
from stage014_independent_scope import canonical_starts,mature,completed_weeks
class IndependentScopeTests(unittest.TestCase):
 def test_default_59_includes_real_2026_four_no_future_November(self):
  s=canonical_starts();self.assertEqual(len(s),59);self.assertEqual(s[-4:],['2026-01-01','2026-03-01','2026-06-01','2026-09-01']);self.assertNotIn('2026-11-01',s)
 def test_calendar_year_maturity_does_not_confuse_252_or_365_days(self):
  s=canonical_starts();self.assertEqual(sum(mature(x) for x in s),54);self.assertFalse(mature('2025-11-01'));self.assertTrue(mature('2025-10-30'));self.assertFalse(mature('2025-10-31'))
 def test_month_set_must_be_frozen_not_silent_fallback(self):
  for ms in [(1,1,6,9,11),(1,3,6,11),(1,3,6,9,13),(3,1,6,9,11)]:
   with self.subTest(ms=ms),self.assertRaises(ValueError):canonical_starts(ms)
 def test_Thursday_terminal_week_is_open_Friday_is_complete(self):
  ds=['2026-10-26','2026-10-27','2026-10-28','2026-10-29'];self.assertEqual(completed_weeks(ds),{});self.assertEqual(list(completed_weeks(ds+['2026-10-30']).values()),[ds+['2026-10-30']])
 def test_future_Monday_not_needed_to_close_Friday(self):
  ds=['2026-10-30'];self.assertEqual(list(completed_weeks(ds).values()),[ds]);self.assertNotIn('2026-11-02',sum(completed_weeks(ds).values(),[]))
if __name__=='__main__':unittest.main()
