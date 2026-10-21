"""Eight bounded synthetic contracts; no historical data, model or book reuse."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load(name):
    path = TOOLS / name
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('fixture_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegistrationContracts(unittest.TestCase):
    def setUp(self):
        self.fit = load('stage190_registration_fit.py')
        self.cash = load('stage191_registration_cash.py')
        self.assertIsNotNone(self.fit, 'Stage190 adapter is missing')
        self.assertIsNotNone(self.cash, 'Stage191 adapter is missing')

    def test_shared_missing_control_exact_zero_and_observed_only_weighted_scalar(self):
        q = np.array([0., 1., np.nan])
        stat = self.fit.q_statistics(q, np.array([1., 3., 100.]))
        self.assertEqual((stat['finite_count'], stat['mean'], stat['var']), (2, .75, .1875))
        common = dict(common=dict(mean=[0.] * 26, scale=[1.] * 26))
        raw = np.zeros((3, 26)); raw[1, 4] = np.nan
        control = self.fit.design54(raw, q, common, stat, 'CONTROL54')
        active = self.fit.design54(raw, q, common, stat, 'REGISTRATION54')
        np.testing.assert_array_equal(control[:, :53], active[:, :53])
        np.testing.assert_array_equal(control[:, 53], [0., 0., 0.])
        np.testing.assert_array_equal(active[:, 52], [0., 0., 1.])
        self.assertEqual(active[2, 53], 0.)
        self.assertNotEqual(active[0, 53], 0.)

    def test_all_six_unique_folds_support_precedes_any_fit_and_nonfinite_cannot_pass(self):
        good = self.fit.q_statistics([0., 1.], [1., 1.])
        cells = [dict(scope=s, cutoff=c, q_statistics=good)
                 for s in self.fit.SCOPES for c in self.fit.CUTOFFS]
        self.assertTrue(self.fit.global_preflight(cells)['ready'])
        for values in ([np.nan, np.inf], [1., 1.]):
            changed = [dict(c) for c in cells]
            changed[-1]['q_statistics'] = self.fit.q_statistics(values, [1., 1.])
            result = self.fit.global_preflight(changed)
            self.assertFalse(result['ready'])
            self.assertEqual(result['fit_calls_authorized'], 0)
        self.assertFalse(self.fit.global_preflight(cells[:-1] + [cells[0]])['ready'])
        with self.assertRaisesRegex(ValueError, 'weight'):
            self.fit.q_statistics([0., 1.], [1., np.inf])

    def test_projection_zero_missing_identity_and_exact_decision_clock(self):
        cal = ['2020-01-02', '2020-01-03', '2020-01-06', '2020-01-07']
        actions = pd.DataFrame([dict(action_id='a' + str(i), event_id='a' + str(i),
            action_sequence_index=i, mother_sequence_index=i, mother_event_id='p' + str(i),
            product_id=p, family_id='CU', u_date=cal[2], u_index=2,
            reference_epoch=p + '.202005', anchor_epoch=p + '.202005')
            for i, p in enumerate(('SHFE.CU', 'SHFE.CU_F'))])
        projection = actions.copy()
        projection['scalar_primary'] = ['0', '']
        projection['scalar_missing'] = ['0', '1']
        projection['feature_state'] = ['conditional_archive_scalar_known', 'report_pair_unavailable']
        for field, value in dict(decision_date=cal[2], decision_index='2',
            prospective_entry_date=cal[3], prospective_entry_index='3',
            report_v=cal[1], report_v_index='1', report_w=cal[0], report_w_index='0').items():
            projection[field] = value
        q = self.fit.align_projection(actions, projection, cal)
        self.assertEqual(q[0], 0.); self.assertTrue(np.isnan(q[1]))
        changed = projection.copy(); changed.loc[1, 'report_v_index'] = '2'
        with self.assertRaisesRegex(ValueError, 'clock'):
            self.fit.align_projection(actions, changed, cal)
        changed = projection.copy(); changed.loc[1, 'anchor_epoch'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.fit.align_projection(actions, changed, cal)
        changed = projection.copy(); changed.loc[1, 'scalar_primary'] = '0'
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.fit.align_projection(actions, changed, cal)

    def test_source_acceptance_cannot_substitute_bool_for_exact_review_manifest_bindings(self):
        binding = lambda n: dict(path='/fixture/' + n, bytes=1, sha256=n * 64)
        inputs = {r: binding(str(i)) for i, r in enumerate(self.fit.NEW_INPUT_ROLES)}
        inputs.update({r:binding(str(i+10)) for i,r in enumerate(('dataset_manifest','actions','mothers','calendar'))})
        protocol=dict(design_basis=binding('d'),legacy_representation_basis=binding('s'))
        small = dict(
            normalization_manifest=dict(schema='stage186_warehouse_history_normalization_manifest_v1',status='completed',calender=inputs['calendar']),
            projection_manifest=dict(schema='stage188_registration_projection_v1',status='completed',
                input_bindings=dict(normalization_manifest=inputs['normalization_manifest'],
                    normalization_review=inputs['normalization_review'],
                    dataset_manifest=inputs['dataset_manifest'],actions=inputs['actions'],mothers=inputs['mothers'],
                    calendar=inputs['calendar'],feature_design=protocol['design_basis'],scope_ruling=protocol['legacy_representation_basis']),
                actions_projection=inputs['projection_actions']),
            normalization_review=dict(schema='stage187_registration_normalization_review_v1',
                accepted=True,C=0,I=0,M=0,normalization_manifest=inputs['normalization_manifest']),
            projection_review=dict(schema='stage187_registration_projection_review_v1',accepted=True,C=0,I=0,M=0,
                projection_manifest=inputs['projection_manifest'],normalization_manifest=inputs['normalization_manifest'],
                normalization_review=inputs['normalization_review']),
            source_acceptance=dict(schema='stage189_registration_source_acceptance_v1',source_measurement_arithmetic_accepted=True,
                normalization_manifest=inputs['normalization_manifest'],
                normalization_review=inputs['normalization_review'],
                projection_manifest=inputs['projection_manifest'], projection_review=inputs['projection_review'],
                projection_actions=inputs['projection_actions']))
        self.fit.check_new_lineage(small, inputs, protocol)
        small['projection_review']['projection_manifest'] = binding('x')
        with self.assertRaisesRegex(ValueError, 'review'):
            self.fit.check_new_lineage(small, inputs, protocol)

    def cash_fixture(self):
        dates = [f'2020-01-{i:02d}' for i in range(1, 31)]
        store = self.cash.cache_source.NativeBars(dates)
        for epoch in ('P.X.203001', 'P.X.202912'):
            valid = np.ones(30, bool); valid[[23, 24]] = False
            store.series[epoch] = dict(days=np.arange(30),
                values=np.tile([100., 102., 100., 101., 2000.], (30, 1)),
                accepted=np.ones(30, bool), valid=valid, N=np.repeat(4., 30),
                low20=np.repeat(98., 30), run=np.arange(1, 31))
        mothers = pd.DataFrame([dict(sequence_index=7+j, event_id='p'+str(j), product_id='P.X',
            family_id='P.X', u_date=dates[20+j], u_index=20+j, reference_epoch='P.X.202912')
            for j in range(10)])
        actions = pd.DataFrame([dict(action_id='child'+str(j), event_id='child'+str(j),
            action_sequence_index=42+j, mother_event_id='p0', mother_sequence_index=7,
            product_id='P.X', family_id='P.X', u_date=dates[20], u_index=20,
            reference_epoch=e, anchor_epoch='P.X.202912', u_action_eligible=1,
            entry_capacity_qty=10, N_u=4., low20_u=98., u_close=101.)
            for j, e in enumerate(store.series)])
        choices = pd.DataFrame([dict(mothers.iloc[0], policy='NARROW', scope='main',
            cutoff='2020-01-01', chosen_action_id='child'+str(j), chosen_action_sequence_index=42+j,
            chosen_epoch=e, anchor_epoch='P.X.202912', score=.4, selected=1, arm=arm)
            for j, (arm, e) in enumerate(zip(self.cash.ARMS, store.series))])
        econ = {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
            round_lot=1, tick_size=.1, vendor_margin_rate=.1) for e in store.series}
        boundaries = {e: dict(K_index=23, K_date=dates[23], K_target_date='2020-01-01',
            K_state='within_calendar', K_after_sample_end=False) for e in store.series}
        return actions, mothers, choices, boundaries, self.cash.CachedMarket(store), dates, econ

    def test_cash_arm_mapping_and_missing_quotes_keep_own_child_and_K(self):
        a, m, choices, b, market, dates, econ = self.cash_fixture()
        original = choices.copy(deep=True)
        signals = {arm: self.cash.make_arm_signals(a, m, choices, b, market, dates, econ, arm)
                   for arm in self.cash.ARMS}
        self.assertEqual(signals['CONTROL54'].reference_epoch.tolist(), ['P.X.203001'])
        self.assertEqual(signals['REGISTRATION54'].reference_epoch.tolist(), ['P.X.202912'])
        self.assertEqual(signals['REGISTRATION54'].lifecycle_index.tolist(), [23])
        pd.testing.assert_frame_equal(original, choices)
        choices.loc[choices.arm.eq('CONTROL54'), 'selected'] = 0
        self.assertTrue(self.cash.make_arm_signals(a, m, choices, b, market, dates, econ, 'CONTROL54').empty)
        b['P.X.202912']['K_index'] = 21
        with self.assertRaisesRegex(ValueError, 'D<K'):
            self.cash.make_arm_signals(a, m, choices, b, market, dates, econ, 'REGISTRATION54')

    def test_all_eight_independent_recursive_books_checkpoint_before_metadata(self):
        a, m, c, b, market, dates, econ = self.cash_fixture()
        signals = {arm: self.cash.make_arm_signals(a, m, c, b, market, dates, econ, arm)
                   for arm in self.cash.ARMS}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            books, accounts = self.cash.run_account_checkpoints(out, signals, m, market, dates, econ,
                {w: [dates[21], dates[25]] for w in self.cash.WINDOWS}, fixture=True)
            terminal = json.loads((out / 'financial_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'], terminal['new_cash_accounts'],
                              terminal['raw_ledgers_checkpointed']), (8, 8, 8))
            self.assertEqual(len({id(book) for book in books.values()}), 8)
            self.assertEqual(len(accounts), 8)
            for spec in self.cash.account_specs():
                book = books[(spec['arm'], spec['window'], spec['cost'])]
                self.assertEqual([f['side'] for f in book['fills']], ['BUY', 'SELL'])
                self.assertEqual(book['fills'][-1]['date'], dates[25])
                self.assertTrue((out / spec['account_id'] / 'checkpoint.json').exists())
            with self.assertRaises(FileExistsError):
                self.cash.run_account_checkpoints(out, signals, m, market, dates, econ,
                    {w: [dates[21], dates[25]] for w in self.cash.WINDOWS}, fixture=True)

    def test_failure_retains_attempt_completed_counts_and_first_book_checkpoint(self):
        a, m, c, b, market, dates, econ = self.cash_fixture()
        signals = {arm: self.cash.make_arm_signals(a, m, c, b, market, dates, econ, arm)
                   for arm in self.cash.ARMS}
        original = self.cash.kernel.run_cash_account; calls = []
        def fail_second(*args, **kwargs):
            calls.append(args[5])
            if len(calls) == 2:
                raise RuntimeError('bounded second-account failure')
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(self.cash.kernel, 'run_cash_account', side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, 'second-account'):
                    self.cash.run_account_checkpoints(out, signals, m, market, dates, econ,
                        {w: [dates[21], dates[25]] for w in self.cash.WINDOWS}, fixture=True)
            terminal = json.loads((out / 'financial_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'], terminal['new_cash_accounts'],
                              terminal['raw_ledgers_checkpointed']), (2, 1, 1))
            self.assertTrue((out / self.cash.account_specs()[0]['account_id'] / 'checkpoint.json').exists())

    def test_new_arm_paired_ci_and_unknown_DD_or_differential_held_cannot_pass(self):
        daily, summaries = {}, {}
        for arm in self.cash.ARMS:
            for window in self.cash.WINDOWS:
                for cost in self.cash.COSTS:
                    key = arm, window, cost
                    active = arm == 'REGISTRATION54'
                    daily[key] = pd.DataFrame(dict(date=['d1', 'd2'],
                        equity=[1.1e6, 1.21e6] if active else [1e6, 1e6], ever_insolvent=[False, False]))
                    summaries[key] = dict(total_return_pct=21. if active else 0.,
                        max_drawdown_pct=-1. if active else -2., fills=2)
        points, _ = self.cash.compare_accounts(summaries, daily,
            {w: np.tile([1, 0], (2000, 1)) for w in self.cash.WINDOWS})
        self.assertEqual({p['contrast'] for p in points}, {'REGISTRATION54_minus_CONTROL54'})
        self.assertAlmostEqual(points[0]['ci95_low'], np.log(1.1))
        held = dict(groups={g: dict(known_u_equal_mean_increment_R=0., nominal_pass=True,
            unknown_differential_selected_events=0, status='supported') for g in ('holdout_0', 'holdout_1')})
        self.assertTrue(self.cash.fixed_gate(points, held, False,
            wealth_positive=True, execution_unknown=False)['nominal_pass'])
        points[1]['drawdown_percentage_point_difference'] = None
        self.assertFalse(self.cash.fixed_gate(points, held, False,
            wealth_positive=True, execution_unknown=False)['nominal_pass'])
        points[1]['drawdown_percentage_point_difference'] = 1.
        held['groups']['holdout_1']['unknown_differential_selected_events'] = 1
        gate = self.cash.fixed_gate(points, held, False, wealth_positive=True, execution_unknown=False)
        self.assertTrue(gate['cash_nominal_pass']); self.assertFalse(gate['nominal_pass'])
        self.assertFalse(gate['production_qualified'])


if __name__ == '__main__':
    unittest.main()
