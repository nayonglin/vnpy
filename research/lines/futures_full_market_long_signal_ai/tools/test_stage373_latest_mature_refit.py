"""One synthetic contract fixture; exactly one small Ridge fit, zero historical I/O."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


class LatestMatureContract(unittest.TestCase):
    def test_maturity_train_only_statistics_and_exact_weighted_solution(self):
        # Removing either maturity predicate, fitting scaler on future rows,
        # changing interval/member weights, or predicting history must fail here.
        source = Path(__file__).with_name('stage373_latest_mature_refit.py')
        self.assertTrue(source.is_file(), 'new fit-only trainer is not implemented')
        spec = importlib.util.spec_from_file_location('fixture373', source)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        protocol = tool.load_protocol()
        kernels, columns = tool.load_math(protocol)
        dates = ['2022-12-29', '2023-01-03', '2023-01-03', '2023-01-03',
                 '2026-10-15', '2026-10-20', '2026-10-15', '2026-10-15',
                 '2026-10-15', '2026-10-15', '2026-10-15', '2026-10-15']
        known = ['2022-12-30', '2023-01-10', '2023-01-11', '2023-01-11',
                 '2026-10-16', '2026-10-20', '2026-10-20', '',
                 '2026-10-16', '2026-10-16', '', '2026-10-16']
        frame = pd.DataFrame(dict(sequence_index=np.arange(12),
            action_id=[f'a{i}' for i in range(12)], family_id=['A']*3+['B']*9,
            u_date=dates, label_known_date=known,
            label_state=['closed_complete_bar_model']*7+['path_or_execution_unknown']+
                        ['closed_complete_bar_model']*3+['open_right_censored'],
            u_action_eligible=[1]*8+[0, 1, 1, 1],
            net_R_stress=[-1., 2., -2., 4., 1., 999., 999., 999., 999., np.inf, 999., 999.],
            entry_index=[1, 2, 3, 2, 8]+[10]*7,
            exit_index=[3, 4, 5, 5, 9]+[11]*7))
        raw = np.tile(np.arange(12, dtype=float)[:, None], (1, 26))
        raw[:, 1] = np.nan
        raw[:, 2] = 7.
        problem = tool.build_training(frame, raw, kernels, columns)
        self.assertEqual(problem['train'].action_id.tolist(), ['a0', 'a1', 'a2', 'a3', 'a4'])
        self.assertEqual((problem['record']['old_rows'], problem['record']['new_rows'],
                          problem['record']['added_rows']), (1, 5, 4))
        # A's overlapping groups have uniqueness 2/3 and 3/4. On 2023-01-03,
        # A's two member masses are 3/8 each, B's is 1; then normalize equal-u.
        expected_w = np.array([5/3, 5/14, 5/14, 20/21, 5/3])
        np.testing.assert_allclose(problem['weights'], expected_w, rtol=0, atol=1e-15)
        self.assertAlmostEqual(problem['scaler']['common']['mean'][0], 89/42)
        self.assertEqual(problem['scaler']['common']['finite_count'][1], 0)
        self.assertEqual(problem['scaler']['common']['scale'][1:3], [1., 1.])
        poisoned = raw.copy()
        poisoned[5:] = -1e100
        changed = frame.copy()
        changed.loc[5:, 'net_R_stress'] = -1e90
        changed.loc[9, 'net_R_stress'] = np.inf  # Preserve nonfinite exclusion.
        other = tool.build_training(changed, poisoned, kernels, columns)
        self.assertEqual(problem['scaler'], other['scaler'])
        np.testing.assert_array_equal(problem['x'], other['x'])
        np.testing.assert_array_equal(problem['y'], other['y'])
        np.testing.assert_array_equal(problem['weights'], other['weights'])
        # No added mature observation stops before attempting any fit.
        empty = tool.build_training(frame.iloc[:1], raw[:1], kernels, columns)
        def forbidden():
            raise AssertionError('no-added case attempted a fit')
        self.assertIsNone(tool.fit_training(empty, forbidden, forbidden))
        calls = []
        with patch.object(tool.Ridge, 'predict', side_effect=AssertionError('historical prediction forbidden')):
            result = tool.fit_training(problem, lambda: calls.append('attempt'),
                                       lambda: calls.append('complete'))
        self.assertEqual(calls, ['attempt', 'complete'])
        z = np.column_stack([problem['x'], np.ones(5)])
        lhs = z.T @ (expected_w[:, None]*z)
        lhs[np.arange(52), np.arange(52)] += 1.
        rhs = z.T @ (expected_w*np.array([-1., 2., -2., 4., 1.]))
        beta = np.r_[result['portable']['coef'], result['portable']['intercept']]
        np.testing.assert_allclose(lhs@beta, rhs, rtol=1e-8, atol=1e-7)
        np.testing.assert_allclose(beta, np.linalg.solve(lhs, rhs), rtol=1e-8, atol=1e-8)
        np.testing.assert_allclose(result['normal_equations']['lhs'], lhs, rtol=0, atol=1e-12)
        self.assertEqual(result['historical_predictions'], 0)


if __name__ == '__main__':
    unittest.main()
