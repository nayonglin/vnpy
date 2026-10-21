"""New cached-bridge/control/comparison boundaries only; no actual data or books."""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load():
    path = TOOLS/'stage136_month_ranking_cash.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('fixture136', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MonthRankingCash(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.assertIsNotNone(self.m, 'Stage136 implementation is missing')

    def store(self):
        store = self.m.cache_source.NativeBars([f'2020-01-{k:02d}' for k in range(1, 25)])
        x = np.tile([100., 102., 98., 101., 2000.], (23, 1))
        for epoch in ('P.X.203001', 'P.X.202912'):
            store.series[epoch] = dict(days=np.arange(23), values=x.copy(), accepted=np.ones(23, bool),
                valid=np.ones(23, bool), N=np.repeat(4., 23), low20=np.repeat(98., 23), run=np.arange(1, 24))
        return store

    def fixtures(self):
        store = self.store()
        market = self.m.CachedMarket(store)
        dates = store.calendar
        mothers = pd.DataFrame([dict(sequence_index=7, event_id='parent', product_id='P.X', family_id='P.X',
            u_date=dates[20], u_index=20, reference_epoch='P.X.202912')])
        overrides = pd.DataFrame([dict(control_id='MAX_VOLUME_POS', scope='main', cutoff='2020-01-01',
            mother_sequence_index=7, mother_event_id='parent', product_id='P.X', family_id='P.X',
            u_date=dates[20], u_index=20, chosen_action_id='child', chosen_action_sequence_index=42,
            chosen_epoch='P.X.203001', anchor_epoch='P.X.202912', score=.4, u_volume=2000., rule_key='2000')])
        actions = pd.DataFrame([dict(action_id='child', event_id='child', action_sequence_index=42,
            mother_event_id='parent', product_id='P.X', family_id='P.X', u_date=dates[20], u_index=20,
            reference_epoch='P.X.203001', anchor_epoch='P.X.202912', u_action_eligible=1,
            entry_capacity_qty=10, N_u=4., low20_u=98., u_close=101.,
            label_state='open_right_censored')])
        economics = {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
            round_lot=1, tick_size=.1, vendor_margin_rate=.1) for e in store.series}
        return overrides, mothers, actions, market, dates, economics

    def test_cached_bridge_never_falls_back_or_recomputes(self):
        store = self.store()
        store.series['P.X.203001']['valid'][21] = False
        market = self.m.CachedMarket(store)
        self.assertEqual(market.bar('P.X.203001', 20)['volume'], 2000.)
        self.assertIsNone(market.bar('P.X.203001', 21))
        self.assertIsNone(market.bar('P.X.203001', 23))
        self.assertIsNone(market.bar('absent', 20))
        self.assertEqual(market.indicator('P.X.203001', 20)['N'], 4.)
        self.assertEqual(market.indicator('P.X.203001', 20)['run_length'], 21)
        self.assertTrue(math.isnan(market.indicator('P.X.203001', 21)['N']))
        self.assertEqual(market.indicator('absent', 20)['run_length'], 0)

    def test_selected_subset_uses_own_child_and_keeps_unknown_outcome(self):
        args = self.fixtures()
        result = self.m.make_control_signals(*args)
        self.assertEqual(result.event_id.tolist(), ['child'])
        self.assertEqual(result.mother_event_id.tolist(), ['parent'])
        self.assertEqual(result.reference_epoch.tolist(), ['P.X.203001'])
        self.assertEqual(result.anchor_epoch.tolist(), ['P.X.202912'])
        self.assertEqual(result.control_id.tolist(), ['MAX_VOLUME_POS'])
        self.assertEqual(result.entry_capacity_qty.tolist(), [10])

    def test_changed_parent_and_nonpositive_score_cannot_enter_cash(self):
        args = list(self.fixtures())
        args[0] = args[0].assign(mother_sequence_index=8)
        with self.assertRaises(ValueError):
            self.m.make_control_signals(*args)
        args = list(self.fixtures())
        args[0] = args[0].assign(score=-.1)
        with self.assertRaises(ValueError):
            self.m.make_control_signals(*args)

    def daily(self, factor, *, insolvent=False):
        return pd.DataFrame(dict(date=['2020-01-01', '2020-01-02'],
            equity=[1_000_000*factor, 1_000_000*factor*factor], ever_insolvent=[False, insolvent]))

    def test_random_comparison_averages_twenty_daily_logs(self):
        controls = {f'RANDOM_POS_{i:02d}': self.daily(1.01 if i < 10 else 1.09) for i in range(20)}
        index = np.tile([0, 1], (2000, 1))
        point, distribution = self.m.paired_log_contrast(self.daily(1.1), controls, index)
        expected = math.log(1.1)-.5*math.log(1.01)-.5*math.log(1.09)
        self.assertEqual(point['status'], 'valid')
        self.assertEqual(point['control_count'], 20)
        self.assertAlmostEqual(point['mean_daily_log_difference'], expected, places=13)
        self.assertAlmostEqual(point['ci95_low'], expected, places=13)
        self.assertTrue(np.allclose(distribution, expected, rtol=0., atol=1e-13))

    def test_bad_seed_or_date_mismatch_is_not_dropped_or_repaired(self):
        controls = {f'RANDOM_POS_{i:02d}': self.daily(1.01) for i in range(20)}
        controls['RANDOM_POS_19'] = self.daily(0.)
        index = np.tile([0, 1], (2000, 1))
        point, distribution = self.m.paired_log_contrast(self.daily(1.1), controls, index)
        self.assertEqual(point['status'], 'survival_failure_no_log_repair')
        self.assertEqual(point['invalid_control_ids'], ['RANDOM_POS_19'])
        self.assertIsNone(point['ci95_low'])
        self.assertTrue(np.isnan(distribution).all())
        controls['RANDOM_POS_19'] = self.daily(1.01).assign(date=['wrong', 'dates'])
        with self.assertRaises(ValueError):
            self.m.paired_log_contrast(self.daily(1.1), controls, index)

    def test_saved_false_bool_is_not_interpreted_as_insolvency(self):
        ai = self.daily(1.1).assign(ever_insolvent=['False', 'False'])
        point, _ = self.m.paired_log_contrast(ai, {'MAX_VOLUME_POS': self.daily(1.01)}, np.tile([0, 1], (2000, 1)))
        self.assertEqual(point['status'], 'valid')

    def test_empty_ledger_export_retains_nine_readable_schemas(self):
        book = dict(fills=[], budgets=[], daily=[], position_days=[], closed_episodes=[], open_episodes=[],
            capacity_audit=[], entry_execution_unknown=[])
        with tempfile.TemporaryDirectory() as directory:
            ledger = self.m.write_ledgers(Path(directory), book)
            self.assertEqual(len(ledger), 9)
            self.assertIn('capacity_state', pd.read_csv(ledger['capacity_audit']['path']).columns)
            self.assertIn('event_id', pd.read_csv(ledger['rejections']['path']).columns)


if __name__ == '__main__':
    unittest.main()
