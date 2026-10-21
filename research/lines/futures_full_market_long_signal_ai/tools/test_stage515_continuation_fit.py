"""New fixed-continuation synthetic checks; never reads historical payloads."""
import importlib.util
import csv
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
import numpy as np


class ContinuationFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = Path(__file__).with_name('stage515_continuation_fit.py')
        spec = importlib.util.spec_from_file_location('stage515_toy', p)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def state(self, **changes):
        s = dict(mark=110, SL0=98, boundary_next=105, close=110,
                 previous_close=108, N_t=10, R0=2, age_source_days=4,
                 source_lifecycle_target_date='2021-02-01',
                 K_target_date='2021-01-01', t_date='2020-12-30')
        s.update(changes)
        return s

    def test_causal_features_real_dates_missing_not_sentinel(self):
        np.testing.assert_allclose(self.m.raw_features(self.state()), [6, 2.5, 1, 5, 4, 2])
        s = self.state(previous_close='', source_lifecycle_target_date='',
                       K_target_date='', effective_lifecycle_index=999999)
        x = self.m.raw_features(s)
        self.assertTrue(np.isnan(x[[2, 5]]).all())
        s['exit_reference'] = -999999  # Future labels are not feature inputs.
        np.testing.assert_equal(x, self.m.raw_features(s))

    def test_paired_sell_cost_once_sunk_entry_cancels_unknown_not_zero(self):
        b = dict(contract_multiplier=10, stress_terminal_SELL_quote_state='observed_research_quote',
                 stress_terminal_SELL_fill_price=111, stress_terminal_SELL_fee_per_lot=5,
                 stress_entry_BUY_fee_per_lot=999)
        v = dict(stress_SELL_quote_state='observed_research_quote',
                 stress_SELL_fill_price=109, stress_SELL_fee_per_lot=3)
        self.assertAlmostEqual(self.m.paired_target(b, v, 2, 'stress'), .9)
        v['stress_SELL_quote_state'] = 'pending_no_legal_open'
        self.assertTrue(np.isnan(self.m.paired_target(b, v, 2, 'stress')))
        terminal=dict(participation_state='entered',terminal_state='open_right_censored',
                      stress_terminal_SELL_quote_state='observed_research_quote',available_at='')
        self.assertTrue(np.isnan(self.m.unchanged_terminal_delta(terminal,'stress')))
        terminal.update(terminal_state='closed_complete_bar_model',available_at='2025-01-02')
        self.assertEqual(self.m.unchanged_terminal_delta(terminal,'stress'),0.)
        terminal.update(stress_terminal_SELL_quote_state='unknown')
        self.assertTrue(np.isnan(self.m.unchanged_terminal_delta(terminal,'stress')))
        terminal.update(participation_state='stale_breakout_cancel_at_open')
        self.assertEqual(self.m.unchanged_terminal_delta(terminal,'stress'),0.)

    def test_equal_date_family_then_duplicate_paths_split_mass(self):
        day = np.array([1, 1, 1, 2])
        family = np.array([0, 0, 1, 0])
        w = self.m.date_family_weights(day, family)
        np.testing.assert_allclose(w, [.125, .125, .25, .5])
        self.assertEqual(w.sum(), 1.)

    def test_cutoff_known_quote_strict_and_held_excluded(self):
        d = dict(u_day=np.array([1, 1, 1, 1]), k_day=np.array([2, 10, 2, 2]),
                 t_day=np.array([3, 3, 3, 3]), baseline_day=np.array([4, 4, 4, 4]),
                 voluntary_day=np.array([4, 4, 10, 4]), family_hash=np.array([0, 0, 0, 1]),
                 entry_supported=np.ones(4, dtype=bool), y_stress=np.ones(4))
        np.testing.assert_equal(self.m.training_mask(d, 10, 'holdout_1'), [1, 0, 0, 0])
        d['y_stress'][0] = np.nan
        self.assertEqual(self.m.training_mask(d, 10, 'main').sum(), 1)

    def test_missing_train_scaler_and_flags_not_outcome_or_test_leak(self):
        x = np.array([[1., np.nan, 3, 4, 5, 6], [3., 8., 3, 4, 5, 6]])
        scaler = self.m.fit_scaler(x, np.array([.25, .75]))
        self.assertAlmostEqual(scaler['mean'][0], 2.5)
        self.assertAlmostEqual(scaler['mean'][1], 8.)
        design = self.m.design_matrix(x, scaler)
        self.assertEqual(design.shape, (2, 13))
        self.assertEqual(design[0, 2], 0.)
        self.assertEqual(design[0, 8], 1.)
        self.assertEqual(design[1, 8], 0.)
        self.assertEqual(design[:, 3].max(), 0.)

    def test_fixed_ridge_sum_one_intercept_free_normal_equation(self):
        x = np.tile(np.arange(6, dtype=float), (5, 1))
        y = np.array([1., 2., 3., 4., 5.])
        w = np.full(5, .2)
        model = self.m.fit_head(x, y, w)
        self.assertAlmostEqual(model['coef'][0], 3.)
        np.testing.assert_allclose(model['coef'][1:], 0., atol=1e-12)
        self.assertLess(model['normal_equation_max_abs_residual'], 1e-10)
        self.assertAlmostEqual(model['effective_df'], 1.)

    def test_policy_first_negative_and_prediction_date_heads(self):
        zero = dict(mean=[0.] * 6, scale=[1.] * 6, coef=[1.] + [0.] * 12)
        negative = dict(mean=[0.] * 6, scale=[1.] * 6, coef=[-1.] + [0.] * 12)
        models = {'main|2020-01-01': zero, 'main|2023-01-01': negative}
        p = self.m.predict_state(models, '2022-12-30', self.state())
        q = self.m.predict_state(models, '2023-01-03', self.state())
        self.assertEqual((p['prediction'], q['prediction']), (1., -1.))
        self.assertEqual(self.m.first_negative([1., np.nan, 0., -1., -2.]), 3)
        self.assertEqual(self.m.predict_state(models, '2019-12-30', self.state())['status'],
                         'before_first_cutoff_hold')

    def test_synthetic_four_table_join_unknown_cohort_kept_and_sources_once(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp); inputs={}; tables={key:[] for key in (
                'action_path_summary','unit_states','baseline_terminal_observations','voluntary_exit_observations')}
            family='X.P'; group=int(hashlib.sha256(family.encode()).hexdigest(),16)%2
            for seq in range(2):
                a={key:'' for key in self.m.SUMMARY_FIELDS}
                a.update(sequence_index=seq,action_id='a'+str(seq),product_id=family,family_id=family,
                    reference_epoch='X.P.202001',u_date='2019-01-01',family_hash_group=group,
                    u_action_eligible=1,participation_state='entered',terminal_state='closed',
                    K_date='2019-02-01',K_target_date='2019-02-01',
                    source_lifecycle_target_date='2019-03-01',entry_date='2019-01-02',
                    riskset_count=1,state_count=1,stale_count=0)
                tables['action_path_summary'].append(a)
                state={key:'' for key in self.m.STATE_FIELDS};state.update(self.state())
                state.update(sequence_index=seq,action_id=a['action_id'],family_id=family,
                    family_hash_group=group,t_index=seq,t_date='2019-01-03',riskset=1)
                tables['unit_states'].append(state)
                b={key:'' for key in self.m.BASE_FIELDS};b.update(sequence_index=seq,
                    action_id=a['action_id'],contract_multiplier=10,available_at='2019-01-05',available_phase='open',
                    stress_entry_BUY_quote_state=self.m.KNOWN_QUOTE,
                    stress_entry_SELL_estimate_quote_state=self.m.KNOWN_QUOTE)
                v={key:'' for key in self.m.VOL_FIELDS};v.update(sequence_index=seq,
                    action_id=a['action_id'],t_index=seq,t_date='2019-01-03',
                    available_at='2019-01-04',available_phase='open')
                for cost in ('base','stress'):
                    b[cost+'_terminal_SELL_quote_state']=self.m.KNOWN_QUOTE
                    b[cost+'_terminal_SELL_fill_price']=111;b[cost+'_terminal_SELL_fee_per_lot']=5
                    v[cost+'_SELL_quote_state']=self.m.KNOWN_QUOTE if seq==0 else 'unknown_quote'
                    v[cost+'_SELL_fill_price']=109;v[cost+'_SELL_fee_per_lot']=3
                tables['baseline_terminal_observations'].append(b)
                tables['voluntary_exit_observations'].append(v)
            fields=dict(action_path_summary=self.m.SUMMARY_FIELDS,unit_states=self.m.STATE_FIELDS,
                baseline_terminal_observations=self.m.BASE_FIELDS,voluntary_exit_observations=self.m.VOL_FIELDS)
            for key,rows in tables.items():
                f=p/(key+'.csv.gz')
                with gzip.open(f,'wt',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields[key]);writer.writeheader();writer.writerows(rows)
                inputs[key]=self.m.binding(f)
            out=p/'new';out.mkdir();receipt={}
            d,meta,mapping,selected_anchors=self.m.extract_compact(inputs,out,receipt,
                dict(actions=2,decision_riskset_states=2,held_close_states=2,entered_paths=2))
            self.assertEqual(len(receipt),4)
            self.assertTrue(all(r['physical_reads']==1 for r in receipt.values()))
            self.assertTrue(np.isnan(d['y_stress'][1]))
            self.assertAlmostEqual(d['y_stress'][0],.9)
            self.assertEqual(meta['cohort_counts']['2020-01-01|main']['all_cohort_actions'],2)
            self.assertEqual(mapping,{0:'a0',1:'a1'})
            self.assertEqual(selected_anchors,{})


if __name__ == '__main__':
    unittest.main()
