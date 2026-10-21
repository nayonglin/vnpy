"""Small new-clock checks only; zero original data, zero estimator fits."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
import unittest

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fixture470', HERE/'stage470_annual_mature_fit_select.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def families():
    return [next('F'+str(i) for i in range(100) if m.original().family_group('F'+str(i)) == g) for g in range(2)]


class AnnualClockFixture(unittest.TestCase):
    def test_exact_maturity_boundary_and_held_complements(self):
        fam = families(); records = []
        for i, (u, known, eligible, state, target, family) in enumerate([
            ('2019-12-30', '2019-12-31', 1, 'closed_complete_bar_model', 1., fam[0]),
            ('2019-12-30', '2019-12-31', 1, 'closed_complete_bar_model', 2., fam[1]),
            ('2019-12-30', '2020-01-01', 1, 'closed_complete_bar_model', 3., fam[0]),
            ('2020-01-01', '2019-12-31', 1, 'closed_complete_bar_model', 4., fam[1]),
            ('2019-12-30', '', 1, 'closed_complete_bar_model', 5., fam[0]),
            ('2019-12-30', '2019-12-31', 0, 'closed_complete_bar_model', 6., fam[0]),
            ('2019-12-30', '2019-12-31', 1, 'unresolved', 7., fam[1]),
            ('2019-12-30', '2019-12-31', 1, 'closed_complete_bar_model', np.nan, fam[1]),
            ('2020-06-01', '', 1, 'unresolved', np.nan, fam[0]),
            ('2020-06-01', '', 1, 'unresolved', np.nan, fam[1]),
            ('2021-01-01', '', 1, 'unresolved', np.nan, fam[0])]):
            records.append(dict(sequence_index=i, u_date=u, label_known_date=known,
                u_action_eligible=eligible, label_state=state, net_R_stress=target, family_id=family))
        a = pd.DataFrame(records); parents = a[['sequence_index', 'family_id', 'u_date']].copy()
        for scope in m.SCOPES:
            cell = dict(scope=scope, training_cutoff='2020-01-01', next_cutoff='2021-01-01')
            train, pred, parent = m.fold_slices(a, parents, cell)
            expected = {0, 1} if scope == 'main' else {1-int(scope[-1])}
            self.assertEqual(set(train.sequence_index), expected)
            self.assertTrue(train.label_known_date.lt('2020-01-01').all())
            self.assertTrue(train.u_date.lt('2020-01-01').all())
            if scope != 'main':
                self.assertTrue(train.family_id.map(m.original().family_group).ne(int(scope[-1])).all())
                self.assertTrue(pred.family_id.map(m.original().family_group).eq(int(scope[-1])).all())
                self.assertTrue(parent.family_id.map(m.original().family_group).eq(int(scope[-1])).all())

    def test_fixed_15_new_six_reused_dispatch_without_models(self):
        calls = {'new': [], 'reuse': []}
        for cell in m.annual_plan():
            m.dispatch_cell(cell, lambda c: calls['new'].append((c['scope'], c['training_cutoff'])),
                            lambda c: calls['reuse'].append((c['scope'], c['training_cutoff'])))
        self.assertEqual(len(calls['new']), 15); self.assertEqual(len(calls['reuse']), 6)
        self.assertEqual({v[1] for v in calls['reuse']}, {'2020-01-01', '2023-01-01'})
        self.assertEqual({v[1] for v in calls['new']}, {'2021-01-01', '2022-01-01', '2024-01-01', '2025-01-01', '2026-01-01'})
        self.assertNotIn('2026-10-20', {v[1] for v in calls['new']+calls['reuse']})

    def test_year_mapping_and_deployment_continuity(self):
        self.assertEqual(m.annual_cutoff('2020-12-31'), '2020-01-01')
        self.assertEqual(m.annual_cutoff('2021-01-01'), '2021-01-01')
        self.assertEqual(m.selector().cutoff_for('2022-12-31'), '2020-01-01')
        self.assertEqual(m.selector().cutoff_for('2023-01-01'), '2023-01-01')
        calendar = ['2020-12-30', '2020-12-31', '2021-01-04', '2021-02-01', '2021-03-01']
        parents = []; scores = []
        for i, day in enumerate(calendar[:3]):
            epoch = 'P.202104'; cutoff = m.selector().cutoff_for(day)
            parents.append(dict(sequence_index=i, event_id='m'+str(i), product_id='P',
                family_id='F', u_date=day, u_index=i, reference_epoch=epoch))
            scores.append(dict(sequence_index=i, action_id='a'+str(i), mother_sequence_index=i,
                mother_event_id='m'+str(i), product_id='P', family_id='F', u_date=day, u_index=i,
                reference_epoch=epoch, anchor_epoch=epoch, u_action_eligible=1, score=1., scope='main',
                cutoff=cutoff, training_cutoff=m.annual_cutoff(day)))
        result = m.select_scope(parents, scores, 'main', calendar)
        choices = result['choices']
        self.assertEqual([c['chosen_action_id'] for c in choices], ['a0', 'a1', 'a2'])
        self.assertEqual({c['cutoff'] for c in choices}, {'2020-01-01'})
        self.assertEqual({c['deployment_fold_cutoff'] for c in choices}, {'2020-01-01'})
        self.assertEqual([c['training_cutoff'] for c in choices], ['2020-01-01', '2020-01-01', '2021-01-01'])
        self.assertEqual({c['arm'] for c in choices}, {'VOLUNTARY_RESELECT'})
        self.assertEqual({c['scope'] for c in choices}, {'main'})
        self.assertEqual(len(result['boundaries']), 1)
        # The whole continuous choice domain goes to cash once, never one book per year.
        self.assertNotIn('capital', choices[2]); self.assertNotIn('liquidate', choices[2])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic(); suite = unittest.defaultTestLoader.loadTestsFromTestCase(AnnualClockFixture)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    terminal = dict(schema='stage470_new_behavior_fixture_terminal_v1', status='completed' if result.wasSuccessful() else 'failed',
        exit_code=0 if result.wasSuccessful() else 1, failures=len(result.failures)+len(result.errors), tests=result.testsRun,
        elapsed_seconds=time.monotonic()-start, created_at=datetime.now(timezone.utc).isoformat(),
        actual_model_fit_calls=0, fake_dispatch_new_calls=15, fake_dispatch_reuse_calls=6,
        real_data_reads=0, new_cash_accounts=0, source_bundle=m.source_bundle())
    m.write_json(out/'fixture_terminal.json', terminal)
    raise SystemExit(terminal['exit_code'])


if __name__ == '__main__':
    main()
