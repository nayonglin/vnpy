import importlib
import unittest


class FreezeContractTests(unittest.TestCase):
    def module(self):
        try:
            module = importlib.import_module('stage257_freeze_experiment')
        except ModuleNotFoundError:
            module = None
        self.assertIsNotNone(module, 'Stage257 freezer has not been implemented')
        return module

    def test_date_keyed_draw_does_not_shift_when_earlier_history_is_added(self):
        m = self.module()
        universe = list('abcdefghijklmno')
        first = m.iid_draw(universe, 8, 3, '2023-06-30')
        m.iid_draw(universe, 8, 3, '2022-01-28')
        self.assertEqual(first, m.iid_draw(list(reversed(universe)), 8, 3, '2023-06-30'))
        self.assertEqual(len(set(first)), 8)

    def test_turnover_preserves_exact_intersection_when_width_changes(self):
        m = self.module()
        previous = set('abcdefgh')
        members = set(m.turnover_draw(list('abcdefghijklmno'), 9, previous, 5, 1, '2023-02-28'))
        self.assertEqual(len(members), 9)
        self.assertEqual(len(members & previous), 5)
        self.assertTrue(members <= set('abcdefghijklmno'))

    def test_impossible_turnover_fails_instead_of_clipping_or_redrawing(self):
        m = self.module()
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            m.turnover_draw(list('abcdefghij'), 8, set('abcdefgh'), 1, 1, '2023-02-28')

    def test_only_common_windows_alias_and_full_windows_keep_199(self):
        m = self.module()
        import csv
        from pathlib import Path
        line = Path(__file__).resolve().parents[1]
        with (line/'outputs/stage257_multicycle_design/proposed_windows.csv').open(encoding='utf-8-sig') as f:
            windows = list(csv.DictReader(f))
        accounts, aliases = m.account_plan(windows)
        self.assertEqual(len(accounts), 1955)
        self.assertEqual(len(aliases), 200)
        self.assertEqual(len(set(aliases.values())), 4)
        self.assertTrue(set(aliases.values()) <= set(accounts))
        self.assertEqual(sum(a['kind']=='turnover_matched' for a in accounts.values()), 199)
        self.assertEqual(sum(a['kind']=='legacy_ai' for a in accounts.values()), 2)
        for window in windows:
            iid = [a for a in accounts.values() if a['window_id']==window['window_id'] and a['kind']=='random_monthly']
            expected = 0 if window['policy_phase']=='common_pre_ai_only' else 199 if window['group'] in ['historical_full','ai_primary'] else 49
            self.assertEqual(len(iid), expected)


if __name__ == '__main__':
    unittest.main()
