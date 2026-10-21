"""Bounded independent-review counterexamples; no actual cash or market inputs."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

SOURCE = Path(__file__).with_name('stage158_voluntary_review.py')


class ReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'Stage158 independent reviewer missing')
        spec = importlib.util.spec_from_file_location('review158_fixture', SOURCE)
        self.r = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.r)

    def test_nominal_month_year_roll_and_no_terminal_clamp(self):
        cal = ['2024-11-29', '2024-12-02', '2025-01-02']
        self.assertEqual(self.r.deadline('DCE.L.202501', cal, cal[0]),
            dict(K_target_date='2024-12-01', K_index=1, K_date='2024-12-02', K_state='in_calendar', K_after_sample_end=True))
        self.assertEqual(self.r.deadline('DCE.L.202503', cal, cal[0])['K_state'], 'after_calendar_pending')
        self.assertIsNone(self.r.deadline('DCE.L.202503', cal, cal[0])['K_index'])
        self.assertEqual(self.r.deadline('DCE.L.202401', cal, cal[0])['K_state'], 'before_calendar_blocked')

    def test_D_equals_K_blocked_and_missing_next_day_unknown(self):
        cal = ['2024-11-29', '2024-12-02', '2025-01-02']
        b = self.r.deadline('DCE.L.202501', cal, cal[-1])
        self.assertEqual(self.r.admission(0, 1, 4., b, cal, cal[-1])['new_eligible'], 0)
        later = self.r.deadline('DCE.L.202503', cal, cal[-1])
        self.assertIsNone(self.r.admission(2, 1, 4., later, cal, cal[-1])['new_eligible'])
        self.assertEqual(self.r.admission(0, 0, 4., later, cal, cal[-1])['new_eligible'], 0)

    def test_filter_before_argmax_not_old_choice_veto(self):
        cal = ['2024-11-29', '2024-12-02', '2025-01-02']
        rows = [dict(action_id='near', reference_epoch='DCE.L.202501', score=10),
                dict(action_id='far', reference_epoch='DCE.L.202502', score=2)]
        legal = [a for a in rows if self.r.admission(0, 1, a['score'], self.r.deadline(a['reference_epoch'], cal, cal[-1]), cal, cal[-1])['new_eligible'] == 1]
        self.assertEqual(min(legal, key=self.r.action_order)['action_id'], 'far')

    def test_exact_ties_and_ordinary_before_F_without_score_comparison(self):
        a = dict(action_id='a', reference_epoch='DCE.L.202503', score=2)
        z = dict(action_id='z', reference_epoch='DCE.L.202503', score=2)
        far = dict(action_id='0', reference_epoch='DCE.L.202504', score=2)
        self.assertEqual(min([far, z, a], key=self.r.action_order)['action_id'], 'a')
        rows = [dict(product_id='DCE.L_F', family_id='DCE.L', u_index=1, mother_sequence_index=1, **dict(a, score=100)),
                dict(product_id='DCE.L', family_id='DCE.L', u_index=1, mother_sequence_index=0, **z)]
        self.assertEqual(self.r.family_choices(rows), {0: rows[1]})

    def test_effective_min_and_root_trace_catches_fabricated_boundary(self):
        self.assertEqual(self.r.effective_boundary(8, dict(K_index=5, K_state='in_calendar'), 4), (5, 'voluntary_calendar'))
        self.assertEqual(self.r.effective_boundary(3, dict(K_index=5, K_state='in_calendar'), 2), (3, 'source_lifecycle'))
        self.assertEqual(self.r.effective_boundary(99, dict(K_index=None, K_state='after_calendar_pending'), 4), (99, 'source_lifecycle'))
        with self.assertRaises(AssertionError):
            self.r.effective_boundary(8, dict(K_index=5, K_state='in_calendar'), 5)
        with self.assertRaises(AssertionError):
            self.r.check_root_boundary(dict(expiry='9', event_id='a'), {'a': dict(lifecycle_index=5)})

    def test_original_paired_indices_and_survival_failure_no_epsilon(self):
        idx = np.array([[0, 0], [1, 1]], dtype=np.int32)
        stats, dist = self.r.paired(np.array([.1, .3]), np.array([0., .1]), idx)
        np.testing.assert_allclose(dist, [.1, .2])
        self.assertAlmostEqual(stats['ci95_low'], .1025)
        invalid, values = self.r.paired(None, np.zeros(2), idx)
        self.assertIsNone(invalid['ci95_low'])
        self.assertTrue(np.isnan(values).all())

    def test_scalar_validation_preserves_null_and_tolerance_rejection(self):
        self.r.fields({'index':'12','missing':''},{'index':12,'missing':float('nan')},'fixture')
        with self.assertRaises(AssertionError):self.r.fields({'index':'13'},{'index':12},'wrong fixture index')
        with self.assertRaises(AssertionError):self.r.fields({'index':''},{'index':12},'missing fixture index')


if __name__ == '__main__': unittest.main()
