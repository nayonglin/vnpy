"""Six new prospective selection fixtures; no accepted data or financial work."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name('stage156_voluntary_choices.py')


def mother(i, product='DCE.L', anchor='DCE.L.202505', day='2024-10-01', u=0):
    return dict(sequence_index=i, event_id=f'm{i}', product_id=product,
                family_id=product.removesuffix('_F'), u_date=day, u_index=u, reference_epoch=anchor)


def child(i, parent, epoch, score, action=None):
    return dict(sequence_index=i, action_id=action or f'a{i}', mother_sequence_index=parent['sequence_index'],
                mother_event_id=parent['event_id'], product_id=parent['product_id'], family_id=parent['family_id'],
                u_date=parent['u_date'], u_index=parent['u_index'], reference_epoch=epoch,
                anchor_epoch=parent['reference_epoch'], u_action_eligible=1,
                score=score, scope='main', cutoff='2023-01-01')


class VoluntaryChoiceFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'Stage156 implementation missing')
        spec = importlib.util.spec_from_file_location('stage156_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_january_previous_month_and_calendar_successor(self):
        """Catch January year underflow or use of a nontrading December first."""
        b = self.m.calendar_boundary('DCE.L.202501', ['2024-11-29', '2024-12-02', '2024-12-03'], '2024-12-03')
        self.assertEqual(b['K_target_date'], '2024-12-01')
        self.assertEqual((b['K_index'], b['K_date']), (1, '2024-12-02'))
        before = self.m.calendar_boundary('DCE.L.202401', ['2024-11-29'], '2024-11-29')
        self.assertEqual(before['K_state'], 'before_calendar_blocked')
        self.assertIsNone(before['K_date'])

    def test_entry_on_K_is_rejected_without_consulting_D_bar(self):
        """Catch <= at the admission boundary; audit must retain the rejected action."""
        cal = ['2024-11-29', '2024-12-02', '2025-01-02']
        p = mother(0, day=cal[0], u=0)
        result = self.m.select_full_pool([p], [child(0, p, 'DCE.L.202501', 2)], cal, cal[-1])
        self.assertEqual(result['choices'][0]['selected'], 0)
        self.assertEqual(len(result['audit']), 1)
        self.assertEqual(result['audit'][0]['new_eligible'], 0)
        self.assertEqual(result['audit'][0]['eligibility_state'], 'D_on_or_after_K')

    def test_boundary_after_sample_is_not_clamped_and_missing_D_stays_unknown(self):
        """Catch fake terminal-day exit or manufactured next-session dates."""
        cal = ['2025-01-29', '2025-01-30', '2025-02-03']
        b = self.m.calendar_boundary('DCE.L.202503', cal, '2025-01-30')
        self.assertEqual((b['K_index'], b['K_date']), (2, '2025-02-03'))
        self.assertTrue(b['K_after_sample_end'])
        pending = self.m.calendar_boundary('DCE.L.202504', cal, '2025-01-30')
        self.assertIsNone(pending['K_index'])
        self.assertEqual(pending['K_state'], 'after_calendar_pending')
        p = mother(0, day=cal[-1], u=2)
        result = self.m.select_full_pool([p], [child(0, p, 'DCE.L.202504', 1)], cal, cal[-1])
        self.assertIsNone(result['audit'][0]['D_date'])
        self.assertIsNone(result['audit'][0]['new_eligible'])
        self.assertEqual(result['choices'][0]['selected'], 0)

    def test_filter_full_pool_before_argmax_reselects_lower_scored_month(self):
        """Catch post-vetoing only the old selected near month."""
        cal = ['2024-11-29', '2024-12-02', '2025-01-02']
        p = mother(0, day=cal[0], u=0)
        children = [child(0, p, 'DCE.L.202501', 10), child(1, p, 'DCE.L.202502', 2)]
        result = self.m.select_full_pool([p], children, cal, cal[-1])
        row = result['choices'][0]
        self.assertEqual(row['chosen_action_id'], 'a1')
        self.assertEqual(row['old_chosen_action_id'], 'a0')
        self.assertEqual(row['chosen_action_sequence_index'], 1)

    def test_ordinary_family_priority_and_exact_month_action_ties(self):
        """Catch selecting F by its higher score or unstable exact-month ties."""
        cal = ['2024-10-01', '2024-10-02', '2024-12-02', '2025-01-02']
        ordinary = mother(0, day=cal[0], u=0)
        f = mother(1, product='DCE.L_F', anchor='DCE.L_F.202505', day=cal[0], u=0)
        children = [child(4, ordinary, 'DCE.L.202502', 2),
                    child(3, ordinary, 'DCE.L.202501', 2, 'z'),
                    child(2, ordinary, 'DCE.L.202501', 2, 'a'),
                    child(5, f, 'DCE.L_F.202502', 100)]
        result = self.m.select_full_pool([ordinary, f], children, cal, cal[-1])
        self.assertEqual(result['choices'][0]['chosen_action_id'], 'a')
        self.assertEqual(result['choices'][1]['selection_state'], 'family_priority_suppressed')
        self.assertEqual(sum(r['selected'] for r in result['choices']), 1)

    def test_complete_parents_include_no_observation_and_wrong_cutoff_is_rejected(self):
        """Catch dropping no-child parents or silently using the wrong forward model."""
        cal = ['2024-10-01', '2024-10-02', '2024-12-02']
        p = mother(0, day=cal[0], u=0)
        empty = mother(1, product='DCE.S', anchor='', day=cal[0], u=0)
        result = self.m.select_full_pool([p, empty], [], cal, cal[-1])
        self.assertEqual([r['event_id'] for r in result['choices']], ['m0', 'm1'])
        self.assertEqual(result['choices'][1]['selection_state'], 'no_observed_children')
        wrong = child(0, p, 'DCE.L.202501', 1)
        wrong['cutoff'] = '2020-01-01'
        with self.assertRaisesRegex(ValueError, 'cutoff'):
            self.m.select_full_pool([p], [wrong], cal, cal[-1], strict_cutoff=True)


if __name__ == '__main__':
    unittest.main()
