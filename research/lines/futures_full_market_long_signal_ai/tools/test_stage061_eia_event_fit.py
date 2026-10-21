"""New EIA contract only; no research estimator fit or native data reads."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

SOURCE = Path(__file__).with_name('stage061_eia_event_fit.py')
if SOURCE.exists():
    spec = importlib.util.spec_from_file_location('stage061_test_subject', SOURCE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
else:
    m = None


def row(event, family='X.A', u='2019-12-20', known='2019-12-24', **kw):
    value = dict(event_id=event, product_id=family, family_id=family, u_date=u,
        u_index=1, reference_epoch='fixture', entry_index=1, exit_index=3,
        entry_date='2019-12-21', exit_date=known, label_known_date=known,
        label_state='closed_complete_bar_model', net_R_stress=1.,
        label_history_ready20=1, is_report_event=1, report_id='r1',
        inventory_s=2., past_sham_s=4., external_missing=0,
        stress_u_cost_R=1., low20_distance_R=2., r1_atr=3.)
    value.update(kw)
    return value


class SyntheticEstimator:
    """Replace only the forbidden research estimation; all other code is real."""
    def fit(self, x, y, sample_weight):
        if x.shape[1] != 10 or not np.isfinite(x).all():
            raise AssertionError('invalid estimator design')
        self.coef_ = np.zeros(10)
        self.intercept_ = float(np.average(y, weights=sample_weight))
        return self

    def predict(self, x):
        return x @ self.coef_ + self.intercept_


class EIAFitTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Stage061 implementation missing')

    def test_strict_event_maturity_keeps_non_oil_and_F_family(self):
        frame = pd.DataFrame([row('ok'), row('equal', known='2020-01-01'),
            row('future', u='2020-01-01'), row('not_event', is_report_event=0),
            row('unknown', label_state='held_unknown', net_R_stress=np.nan),
            row('non_oil', family='DCE.I'), row('F', product_id='X.A_F')])
        self.assertEqual(m.training_slice(frame, '2020-01-01').event_id.tolist(),
                         ['F', 'non_oil', 'ok'])

    def test_family_inclusive_uniqueness_then_report_cohort_equal_weight(self):
        # A[1,3], AF[2,2] -> U=5/6,1/2; B alone U=1.
        # Same report, different u: no per-u normalization is allowed.
        frame = pd.DataFrame([row('a'), row('af', product_id='X.A_F',
            u='2019-12-21', entry_index=2, exit_index=2),
            row('b', family='X.B', report_id='r2', entry_index=2, exit_index=2)])
        got = m.training_weights(frame)
        np.testing.assert_allclose(got.uniqueness, [5/6, .5, 1.], atol=1e-15)
        np.testing.assert_allclose(got.sample_weight, [15/16, 9/16, 1.5], atol=1e-15)
        self.assertAlmostEqual(got.groupby(frame.report_id).sample_weight.sum().loc['r1'], 1.5)

    def test_scaler_half_pools_only_mature_shared_observed_scalars(self):
        frame = pd.DataFrame([row('one', stress_u_cost_R=1., inventory_s=0., past_sham_s=4.),
            row('two', stress_u_cost_R=3., inventory_s=2., past_sham_s=2.),
            row('missing', stress_u_cost_R=np.nan, inventory_s=1e100,
                past_sham_s=-1e100, external_missing=1)])
        scaler = m.fit_scalers(frame, np.array([1., 3., 1.]))
        self.assertAlmostEqual(scaler['common']['mean'][0], 2.5)
        self.assertAlmostEqual(scaler['common']['var'][0], .75)
        self.assertEqual(scaler['q']['mean'], 2.)
        self.assertEqual(scaler['q']['var'], 1.)
        designs = [m.design_matrix(frame, arm, scaler) for arm in m.ARMS]
        for x in designs:
            self.assertEqual(x.shape, (3, 10))
            self.assertTrue(np.isfinite(x).all())
            np.testing.assert_array_equal(x[2, 7:], [0., 0., 0.])
            self.assertEqual(x[2, 3], 1.)
        np.testing.assert_array_equal(designs[0][:, 7:], np.zeros((3, 3)))
        self.assertEqual(designs[1][0, 7], -2.)
        np.testing.assert_array_equal(designs[0][:, :7], designs[2][:, :7])

    def test_prediction_keeps_non_event_unknown_and_all_families(self):
        frame = pd.DataFrame([row('non_oil', family='DCE.I', label_state='held_unknown'),
            row('non_event', is_report_event=0), row('not_ready', label_history_ready20=0),
            row('missing', external_missing=1), row('zero')])
        got = m.prediction_frame(frame, [1., 1., 1., 1., 0.], 'INVENTORY', '2020-01-01')
        self.assertEqual(got.selected.tolist(), [1, 0, 0, 1, 0])
        self.assertEqual(len(got), 5)
        with self.assertRaisesRegex(ValueError, 'finite'):
            m.prediction_frame(frame, [np.nan] * 5, 'INVENTORY', '2020-01-01')

    def test_interactions_use_standardized_controls_without_second_rescaling(self):
        frame = pd.DataFrame([row('one', r1_atr=1., low20_distance_R=4., inventory_s=0., past_sham_s=4.),
            row('two', r1_atr=3., low20_distance_R=8., inventory_s=2., past_sham_s=6.)])
        scaler = m.fit_scalers(frame, [1., 1.])
        x = m.design_matrix(frame, 'INVENTORY', scaler)
        np.testing.assert_allclose(x[:, 7:],
            [[-3/np.sqrt(5), 3/np.sqrt(5), 3/np.sqrt(5)],
             [-1/np.sqrt(5), -1/np.sqrt(5), -1/np.sqrt(5)]], rtol=0, atol=1e-15)

    def test_event_join_neutralizes_shared_missing_without_deleting_mother(self):
        labels = pd.DataFrame([row('event'), row('other', u='2019-12-21')]).drop(
            columns=['is_report_event', 'report_id', 'inventory_s', 'past_sham_s', 'external_missing'])
        events = pd.DataFrame([dict(u_date='2019-12-20', report_id='r2',
            s=5., inventory_s=0., past_sham_s=0., external_missing=1)])
        got = m.join_events(labels, events)
        self.assertEqual(got.is_report_event.tolist(), [1, 0])
        self.assertEqual(got.external_missing.tolist(), [1, 1])
        self.assertEqual(got.inventory_s.tolist(), [0., 0.])
        self.assertEqual(got.past_sham_s.tolist(), [0., 0.])

    def test_past_sham_rejects_future_or_outside_last52_calendar_ordinals(self):
        features = pd.DataFrame([
            dict(report_id='r1', ordinal=1, s=2., past_sham_report_id='', external_missing=1),
            dict(report_id='r2', ordinal=2, s=3., past_sham_report_id='r1', external_missing=0)])
        m.validate_past_sham(features)
        features.loc[1, 'past_sham_report_id'] = 'r2'
        with self.assertRaisesRegex(ValueError, 'past'):
            m.validate_past_sham(features)
        features.loc[1, ['ordinal', 'past_sham_report_id']] = [54, 'r1']
        with self.assertRaisesRegex(ValueError, 'past'):
            m.validate_past_sham(features)

    def test_shared_missing_cannot_hide_available_current_and_past_information(self):
        features = pd.DataFrame([
            dict(report_id='r1', ordinal=1, s=2., past_sham_report_id='', external_missing=1),
            dict(report_id='r2', ordinal=2, s=3., past_sham_report_id='', external_missing=1)])
        with self.assertRaisesRegex(ValueError, 'shared missing'):
            m.validate_past_sham(features)

    def test_event_map_cannot_substitute_a_scalar_or_superseded_report(self):
        features = pd.DataFrame([dict(report_id='r1', u_date='2020-01-02',
            inventory_s=2., past_sham_s=3., external_missing=0,
            superseded_before_first_decision=False)])
        events = features.drop(columns='superseded_before_first_decision').copy()
        m.validate_event_map(events, features)
        events.loc[0, 'inventory_s'] = 7.
        with self.assertRaisesRegex(ValueError, 'event map'):
            m.validate_event_map(events, features)
        events.loc[0, 'inventory_s'] = 2.
        features.loc[0, 'superseded_before_first_decision'] = True
        with self.assertRaisesRegex(ValueError, 'event map'):
            m.validate_event_map(events, features)

    def test_future_poison_does_not_enter_mature_scalers(self):
        frame = pd.DataFrame([row('train'), row('future', u='2023-01-01',
            known='2023-01-02', inventory_s=1e200, r1_atr=-1e200)])
        train = m.training_slice(frame, '2020-01-01')
        before = m.fit_scalers(train, m.training_weights(train).sample_weight)
        frame.loc[1, ['r1_atr', 'inventory_s']] = [7e200, -9e200]
        train = m.training_slice(frame, '2020-01-01')
        after = m.fit_scalers(train, m.training_weights(train).sample_weight)
        self.assertEqual(before, after)

    def test_six_cells_full_forward_mother_persisted_without_research_fit(self):
        frame = pd.DataFrame([row('train'), row('train_other', family='DCE.I'),
            row('2020', u='2020-01-02', known='2020-01-04'),
            row('2023', u='2023-01-02', known='2023-01-04', label_state='held_unknown', net_R_stress=np.nan),
            row('2026', u='2026-10-16', known='', is_report_event=0,
                label_state='open_at_source_end', net_R_stress=np.nan)])
        with tempfile.TemporaryDirectory() as td:
            result = m.run_matrix(frame, Path(td), estimator_factory=SyntheticEstimator,
                                  execution_kind='synthetic_fixture')
            self.assertEqual(result['fit_calls_completed'], 6)
            self.assertEqual(result['actual_fit_calls_completed'], 0)
            pred = pd.read_csv(result['predictions']['path'], dtype={'event_id': str})
            self.assertEqual(len(pred), 9)
            self.assertEqual(set(pred.event_id), {'2020', '2023', '2026'})
            self.assertTrue(np.isfinite(pred.score).all())
            self.assertEqual(int(pred.loc[pred.event_id.eq('2026'), 'selected'].sum()), 0)
            self.assertEqual(len(result['fits']), 6)
            for fit in result['fits']:
                self.assertEqual(fit['head_dimension'], 10)
                self.assertTrue(Path(fit['training_weights']['path']).exists())
                self.assertTrue(Path(fit['input_projection']['path']).exists())

    def test_preflight_saves_source_bound_terminal_and_cannot_fit(self):
        # Replace only normalized disk ingestion, exercising the real CLI worker.
        frame = pd.DataFrame([row('train'), row('2020', u='2020-01-02', known='2020-01-04'),
                              row('2023', u='2023-01-02', known='2023-01-04')])
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'preflight'
            args = SimpleNamespace(mode='preflight', protocol=m.PROTOCOL, protocol_sha256=m.PROTOCOL_SHA,
                source_manifest='unused_source_boundary', source_manifest_sha256='fixture', output=out)
            with patch.object(m, 'load_inputs', return_value=(frame, dict(path='fixture', sha256='fixture', bytes=0), {})):
                result = m.execute(args)
            terminal = json.loads((out / 'preflight_terminal.json').read_text())
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(result['fit_calls_started'], 0)
            self.assertEqual(terminal['actual_fit_calls_completed'], 0)
            self.assertEqual(manifest['terminal']['sha256'], m.file_binding(out / 'preflight_terminal.json')['sha256'])
            self.assertTrue((out / 'preflight_started.json').exists())
            self.assertEqual(terminal['source']['sha256'], m.file_binding(SOURCE)['sha256'])

    def test_source_changed_or_missing_root_authorization_cannot_start_actual_fit(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'auth.json'
            path.write_text(json.dumps(dict(kind='stage061_fit_once', protocol_sha256='p',
                source_import_manifest_sha256='i', source_sha256='old', fit_calls=6, authorized=True)))
            with self.assertRaisesRegex(ValueError, 'authorization'):
                m.authorize(path, m.file_binding(path)['sha256'], {'sha256': 'p'}, {'sha256': 'i'}, {'sha256': 'new'})


if __name__ == '__main__':
    unittest.main()
