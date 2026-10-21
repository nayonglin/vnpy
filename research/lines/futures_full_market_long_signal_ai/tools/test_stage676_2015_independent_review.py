"""Small adversarial fixtures; no real data, fitting, or financial replay."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage676_2015_independent_review.py')


class ReviewBoundaryFixtures(unittest.TestCase):
    def reviewer(self):
        self.assertTrue(SOURCE.exists(), 'Stage676 checker is not implemented')
        spec = importlib.util.spec_from_file_location('review676_fixture', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_three_cutoffs_keep_early_model_identity(self):
        r = self.reviewer()
        self.assertEqual([r.cutoff_for(x) for x in ['2015-01-05', '2019-12-31', '2020-01-01', '2022-12-30', '2023-01-01']],
                         ['2015-01-01', '2015-01-01', '2020-01-01', '2020-01-01', '2023-01-01'])

    def test_maturity_excludes_same_day_future_unknown_and_ineligible(self):
        r = self.reviewer()
        f = pd.DataFrame(dict(u_action_eligible=[1, 1, 1, 1, 0, 1],
            label_state=['closed_complete_bar_model']*5 + ['open_right_censored'],
            u_date=['2014-01-01', '2015-01-01', '2014-12-30', '2014-01-01', '2014-01-01', '2014-01-01'],
            label_known_date=['2014-01-02', '2014-01-02', '2015-01-01', '', '2014-01-02', '2014-01-02'],
            net_R_stress=[1.]*6))
        self.assertEqual(r.training_mask(f).tolist(), [True, False, False, False, False, False])

    def test_normal_equation_check_detects_tampered_intercept(self):
        r = self.reviewer()
        lhs = np.array([[2., 1.], [1., 3.]])
        beta = np.array([1., 2.])
        rhs = lhs @ beta
        r.check_equations(lhs, rhs, beta)
        with self.assertRaises(AssertionError):
            r.check_equations(lhs, rhs, beta + [0., .01])

    def test_K_same_day_entry_is_forbidden(self):
        r = self.reviewer()
        helpers = r.pure_helpers()
        calendar = ['2014-12-31', '2015-01-05', '2015-02-02', '2015-03-02']
        b = helpers['v'].deadline('SHFE.rb.201503', calendar, '2015-03-02')
        self.assertEqual(b['K_index'], 2)
        self.assertEqual(helpers['v'].admission(1, 1, 1., b, calendar, '2015-03-02')['new_eligible'], 0)


if __name__ == '__main__':
    unittest.main()
