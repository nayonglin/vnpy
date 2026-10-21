import unittest
import pandas as pd
from stage045_monthly_target_readiness import build_targets, training_gate


def row(product, value=None, *, eligible=True, mature=True, known=True, role='candidate'):
    return dict(eval_date='2020-01-31', product_vt_symbol=product, row_role=role,
                asof_eligible=eligible, maturity_clock_reached=mature,
                target_day='2020-04-30' if mature else None,
                all_paths_value_known=known, cumulative_net_r=value,
                asof_status='eligible' if eligible else 'outside')


class TargetReadinessTests(unittest.TestCase):
    def test_unknowns_preserve_universe_and_rank_bounds(self):
        f=build_targets(pd.DataFrame([row('A', -2),row('B', 0),row('C', 3),row('D', known=False)]))
        self.assertEqual(list(f.asof_universe_count), [4]*4)
        self.assertEqual(list(f.known_label_count), [3]*4)
        self.assertEqual(list(f.target_state), ['identified_bottom_half','ambiguous','identified_top_half','unknown_label'])
        self.assertEqual(list(f.robust_target), [0,None,1,None])

    def test_immaturity_does_not_shrink_asof_universe(self):
        f=build_targets(pd.DataFrame([row('A',1,mature=False),row('B',2,mature=False)]))
        self.assertEqual(list(f.asof_universe_count),[2,2])
        self.assertFalse(f.label_observable.any())
        self.assertEqual(list(f.target_state),['unknown_label']*2)

    def test_fixed_fu_and_F_stay_out_even_if_claimed_eligible(self):
        f=build_targets(pd.DataFrame([row('A',0),row('FU',99,role='fixed'),row('AU_F',-99,role='monthly_average_F')]))
        self.assertEqual(list(f.asof_universe_count),[1]*3)
        self.assertEqual(list(f.target_state),['constant_uninformative','outside_asof_universe','outside_asof_universe'])
        self.assertFalse(f.point_target_identified.any())

    def test_invalid_known_values_and_incomplete_bool_rejected(self):
        with self.assertRaises(ValueError):build_targets(pd.DataFrame([row('A',float('inf'))]))
        r=row('A',0);r['all_paths_value_known']=None
        with self.assertRaises(ValueError):build_targets(pd.DataFrame([r]))

    def test_zero_trades_are_constant_not_negatives(self):
        f=build_targets(pd.DataFrame([row(str(i),0) for i in range(4)]))
        self.assertFalse(f.point_target_identified.any())
        self.assertTrue(f.constant_observed_target.all())
        gate=training_gate(f)
        self.assertFalse(gate['engineering_floor_pass'])
        self.assertEqual(gate['robust_rows'],0)


if __name__=='__main__':unittest.main()
