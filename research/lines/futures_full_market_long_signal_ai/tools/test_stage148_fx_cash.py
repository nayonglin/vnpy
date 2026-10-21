"""Stage148 synthetic-only boundaries; no source data, fit or cash replay."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load():
    path = TOOLS/'stage148_fx_cash.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('fixture148', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FXCash(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.assertIsNotNone(self.m, 'Stage148 implementation is missing')

    def test_exact_four_fx_books_no_control_replay_schedule(self):
        specs = self.m.account_specs()
        self.assertEqual(len(specs), 4)
        self.assertEqual({(s['window'], s['cost']) for s in specs},
            {(w, c) for w in ('primary_2020', 'cold_2023') for c in ('base', 'stress')})
        self.assertEqual({s['arm'] for s in specs}, {'FX'})
        self.assertTrue(all(s['account_id'].startswith('NARROW_FX_') for s in specs))
        self.assertEqual(self.m.author.ARMS, ('A', 'B'))

    def test_cash_progress_preserves_each_started_account_without_overwrite(self):
        self.assertTrue(hasattr(self.m,'write_cash_progress'),'unique progress writer is missing')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            self.m.write_cash_progress(out,1,0,'first')
            self.m.write_cash_progress(out,2,1,'second')
            paths = sorted(out.glob('cash_progress_*.json'))
            self.assertEqual(len(paths),2)
            self.assertIn('"cash_accounts_started": 1',paths[0].read_text())
            self.assertIn('"cash_accounts_started": 2',paths[1].read_text())

    def fixture(self):
        dates = [f'2020-01-{i:02d}' for i in range(1, 25)]
        store = self.m.cache_source.NativeBars(dates)
        for epoch in ('P.X.203001', 'P.X.202912'):
            store.series[epoch] = dict(days=np.arange(23), values=np.tile([100., 102., 98., 101., 2000.], (23, 1)),
                accepted=np.ones(23, bool), valid=np.ones(23, bool), N=np.repeat(4., 23),
                low20=np.repeat(98., 23), run=np.arange(1, 24))
        mothers = pd.DataFrame([dict(sequence_index=7, event_id='new_fx_parent', product_id='P.X',
            family_id='P.X', u_date=dates[20], u_index=20, reference_epoch='P.X.202912')])
        common = dict(mothers.iloc[0], policy='NARROW', scope='main', cutoff='2020-01-01',
            chosen_action_id='child', chosen_action_sequence_index=42, chosen_epoch='P.X.203001',
            anchor_epoch='P.X.202912', score=.4)
        choices = pd.DataFrame([dict(common, arm='CONTROL_REUSED', selected=0), dict(common, arm='FX', selected=1)])
        actions = pd.DataFrame([dict(action_id='child', event_id='child', action_sequence_index=42,
            mother_event_id='new_fx_parent', product_id='P.X', family_id='P.X', u_date=dates[20],
            u_index=20, reference_epoch='P.X.203001', anchor_epoch='P.X.202912', u_action_eligible=1,
            entry_capacity_qty=10, N_u=4., low20_u=98., u_close=101., label_state='open_right_censored')])
        economics = {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
            round_lot=1, tick_size=.1, vendor_margin_rate=.1) for e in store.series}
        return actions, mothers, choices, self.m.CachedMarket(store), dates, economics

    def test_fx_alias_preserves_new_global_choice_child_anchor_and_original_module(self):
        result = self.m.make_fx_signals(*self.fixture())
        self.assertEqual(result.event_id.tolist(), ['child'])
        self.assertEqual(result.mother_event_id.tolist(), ['new_fx_parent'])
        self.assertEqual(result.reference_epoch.tolist(), ['P.X.203001'])
        self.assertEqual(result.anchor_epoch.tolist(), ['P.X.202912'])
        self.assertEqual(result.arm.tolist(), ['FX'])
        self.assertEqual(result.control_id.tolist(), ['FX'])
        self.assertEqual(result.entry_capacity_qty.tolist(), [10])
        self.assertEqual(self.m.author.ARMS, ('A', 'B'))

    def points(self):
        return [dict(window=w, cost=c, active_total_return_pct=10.,
            return_percentage_point_difference=1., drawdown_percentage_point_difference=1.,
            ci95_low=.001, identification='identified') for w in self.m.WINDOWS for c in self.m.COSTS]

    def held(self, unknown=0):
        return dict(groups={g: dict(nominal_pass=True, status='unknown' if unknown else 'supported',
            known_u_equal_mean_increment_R=0., unknown_differential_selected_events=unknown,
            common_unresolved_same_action=2) for g in ('holdout_0', 'holdout_1')})

    def test_fixed_primary_requires_strictly_shallower_drawdown(self):
        points = self.points()
        gate = self.m.fixed_gate(points, self.held(), False, wealth_positive=True, execution_unknown=False)
        self.assertTrue(gate['cash_nominal_pass'])
        for p in points:
            if (p['window'], p['cost']) == ('primary_2020', 'stress'):
                p['drawdown_percentage_point_difference'] = 0.
        self.assertFalse(self.m.fixed_gate(points, self.held(), False,
            wealth_positive=True, execution_unknown=False)['cash_nominal_pass'])

    def test_unknown_never_passes_or_becomes_zero_increment(self):
        for held, stale, execution in ((self.held(3), False, False), (self.held(), True, False),
                                      (self.held(), False, True)):
            gate = self.m.fixed_gate(self.points(), held, stale, wealth_positive=True, execution_unknown=execution)
            self.assertFalse(gate['nominal_pass'])
            self.assertFalse(gate['production_qualified'])
            self.assertFalse(gate['goal_complete'])
        held = self.held(); held['groups']['holdout_0']['known_u_equal_mean_increment_R'] = None
        self.assertFalse(self.m.fixed_gate(self.points(), held, False,
            wealth_positive=True, execution_unknown=False)['held_known_nominal_pass'])

    def test_sector_variant_attribution_keeps_open_mark_and_does_not_rededuct_slippage(self):
        roots = [dict(root_id='c',event_id='c',product_id='CFFEX.IF_F',family_id='CFFEX.IF',
            net_pnl=70.,entry_fees=10.,exit_fees=20.,realized_gross=100.)]
        opened = [dict(root_id='o',event_id='o',product_id='SHFE.CU',family_id='SHFE.CU',
            entry_fees=5.,exit_fees=0.,realized_gross=2.,unrealized=40.)]
        fills = [dict(root_id='c',fee=30.,slippage=8.),dict(root_id='o',fee=5.,slippage=3.)]
        groups,tails = self.m.extra_reports(dict(closed_episodes=roots,open_episodes=opened,fills=fills))
        by = {(r['dimension'],r['group']):r for r in groups}
        self.assertEqual(set(by), {('market_sector','financial'),('market_sector','commodity'),
            ('product_variant','ordinary'),('product_variant','F')})
        self.assertEqual(by[('market_sector','financial')].get('net_equity_contribution'),70.)
        self.assertEqual(by[('market_sector','commodity')].get('net_equity_contribution'),37.)
        self.assertEqual(by[('product_variant','F')]['slippage_attribution'],8.)
        empty,_ = self.m.extra_reports(dict(closed_episodes=[],open_episodes=[],fills=[]))
        self.assertEqual(len(empty),4)

    def test_pair_uses_exact_dates_and_original_indices_without_log_repair(self):
        def daily(eq):
            return pd.DataFrame(dict(date=['u1','u2'], equity=eq, ever_insolvent=['False','False']))
        idx = np.tile([1,0], (2000,1))
        stats, dist = self.m.paired_statistics(daily([1.1e6,1.21e6]), daily([1e6,1e6]), idx)
        self.assertAlmostEqual(stats['ci95_low'], np.log(1.1))
        self.assertEqual(len(dist), 2000)
        self.assertFalse(stats['indices_regenerated'])
        stats, dist = self.m.paired_statistics(daily([0.,1.21e6]), daily([1e6,1e6]), idx)
        self.assertIsNone(stats['ci95_low'])
        self.assertTrue(np.isnan(dist).all())
        with self.assertRaises(ValueError):
            self.m.paired_statistics(daily([1e6,1e6]), daily([1e6,1e6]).assign(date=['wrong','dates']), idx)


if __name__ == '__main__':
    unittest.main()
