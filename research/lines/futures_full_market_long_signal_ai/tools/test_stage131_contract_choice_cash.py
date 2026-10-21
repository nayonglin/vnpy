"""Only new Stage131 semantics; synthetic arrays, no actual native/fit/cash run."""
import importlib.util
from pathlib import Path
import unittest
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load(name):
    path = TOOLS/name
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('test131_'+path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractChoiceCash(unittest.TestCase):
    def setUp(self):
        self.k = load('stage131_contract_choice_kernel.py')
        self.assertIsNotNone(self.k, 'Stage131 local kernel is missing')

    def market(self, *, volume=2000., missing=(), stop_on=()):
        dates = [f'2020-01-{j:02d}' for j in range(1, 31)]
        records = []
        for epoch in ('P.X.203001', 'P.X.202912'):
            for k, date in enumerate(dates):
                if epoch == 'P.X.203001' and k in missing:
                    continue
                low = 98. if k <= 20 else 98.5 if k in stop_on else 100.
                records.append(dict(contract_epoch_id=epoch, trade_date=date, open=100., high=102., low=low,
                                    close=101., volume=volume, quality_status='accepted'))
        return self.k.ref.Market.from_records(records, dates), dates

    def econ(self):
        return {e: dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
                round_lot=1, tick_size=.1, vendor_margin_rate=.1) for e in ('P.X.203001', 'P.X.202912')}

    def signal(self, market, dates, *, epoch='P.X.203001', anchor='P.X.202912'):
        ind = market.indicator(epoch, 20)
        return pd.DataFrame([dict(event_id='action', mother_event_id='parent', product_id='P.X', family_id='P.X',
            reference_epoch=epoch, anchor_epoch=anchor, u_index=20, u_date=dates[20], D_index=21,
            N_u=ind['N'], low20_u=ind['low20'], u_close=101., history_run=21,
            lifecycle_index=99, entry_capacity_qty=10, potential=1)])

    def test_full_roundtrip_capacity_boundary(self):
        self.assertEqual(self.k.capacity_limits(199., 1), (1, 0))
        self.assertEqual(self.k.capacity_limits(200., 1), (2, 1))
        self.assertEqual(self.k.capacity_limits(399., 2), (2, 0))
        self.assertEqual(self.k.capacity_limits(400., 2), (4, 2))
        self.assertIsNone(self.k.capacity_limits(float('nan'), 1))

    def test_anchor_request_latches_after_reference_returns(self):
        p = dict(anchor_epoch='anchor', expiry=99, force_reason=None)
        self.assertIsNone(self.k.anchor_request(p, 'anchor', 1))
        p['force_reason'] = self.k.anchor_request(p, 'other', 2)
        self.assertEqual(self.k.anchor_request(p, 'anchor', 3), 'liquidity_reference_changed')
        self.assertEqual(self.k.anchor_request(p, '', 99), 'lifecycle_exit')

    def test_noncanonical_entry_is_not_immediate_day_exit(self):
        market, dates = self.market()
        sig = self.signal(market, dates)
        refs = {k: {'P.X': 'P.X.202912'} for k in range(30)}
        book = self.k.run_cash_account(sig, market, dates, self.econ(), 'base', 'fixture', 21, 23,
                                       prepared=({20: sig.to_dict('records')}, refs))
        self.assertEqual(len(book['fills']), 1)
        self.assertEqual(len(book['open_episodes']), 1)
        self.assertEqual(book['open_episodes'][0]['anchor_epoch'], 'P.X.202912')
        self.assertLessEqual(book['fills'][0]['qty'], 10)

    def test_same_day_buy_stop_share_gross_capacity(self):
        market, dates = self.market(stop_on=(21,))
        sig = self.signal(market, dates)
        refs = {k: {'P.X': 'P.X.202912'} for k in range(30)}
        book = self.k.run_cash_account(sig, market, dates, self.econ(), 'base', 'fixture', 21, 22,
                                       prepared=({20: sig.to_dict('records')}, refs))
        self.assertEqual([f['side'] for f in book['fills']], ['BUY', 'SELL'])
        audit = book['capacity_audit']
        self.assertEqual(audit[-1]['cumulative_same_epoch_day_gross_qty'], 2*book['fills'][0]['qty'])
        self.assertEqual(audit[-1]['capacity_state'], 'within_fixed_daily_capacity')

    def test_missing_exact_previous_bar_does_not_backfill_older_volume(self):
        market, dates = self.market(missing=(22,))
        self.assertIsNone(self.k.capacity_at(market, 'P.X.203001', 22, 1))
        self.assertIsNotNone(self.k.capacity_at(market, 'P.X.203001', 21, 1))

    def test_missing_D_is_entry_unknown_without_fake_fill(self):
        market, dates = self.market(missing=(21,))
        sig = self.signal(market, dates)
        refs = {k: {'P.X': 'P.X.202912'} for k in range(30)}
        book = self.k.run_cash_account(sig, market, dates, self.econ(), 'base', 'fixture', 21, 23,
                                       prepared=({20: sig.to_dict('records')}, refs))
        self.assertEqual(book['fills'], [])
        self.assertEqual(book['entry_execution_unknown'][0]['state'], 'entry_execution_unknown')
        self.assertTrue(book['execution_unknown'])

    def test_multiple_sells_share_one_pool_and_keep_ideal_quantity(self):
        market, dates = self.market(volume=1000.)
        ledger = self.k.CapacityLedger(1000000., market, dates, self.econ(), 'fixture')
        root = dict(root_id='r', event_id='a', family_id='P.X', product_id='P.X', epoch='P.X.203001',
            entry_date=dates[21], multiplier=10., margin_rate=.2, risk_per_lot=10., round_lot=1,
            R0=1., entry_index=21, anchor_epoch='P.X.202912')
        ledger.enter(root, 8, 100., 100., 0., 0.)
        ledger.exit('r', 2, 100., 100., 0., 0., dates[21], 'reduction')
        ledger.exit('r', 6, 100., 100., 0., 0., dates[21], 'stop_boundary')
        self.assertEqual([a['cumulative_same_epoch_day_gross_qty'] for a in ledger.capacity_audit], [8, 10, 16])
        self.assertEqual(ledger.capacity_audit[-1]['capacity_state'], 'execution_capacity_unknown')
        self.assertEqual(ledger.fills[-1]['qty'], 6)
        self.assertIn('r', ledger.capacity_unknown_roots)

    def test_capacity_does_not_reassign_other_family_budget(self):
        econ = self.econ()
        econ['Q.X.203001'] = dict(econ['P.X.203001'])
        candidates = [dict(event_id=x, reference_epoch=e, u_close=100., N_u=4., entry_capacity_qty=cap)
                      for x, e, cap in [('a', 'P.X.203001', 1), ('b', 'Q.X.203001', 10000)]]
        original = self.k.original.reserve_batch(candidates, 1000000., 0., 0., econ, 'base', 'NARROW')
        capped = self.k.reserve_capped(candidates, 1000000., 0., 0., econ, 'base')
        self.assertEqual(capped[0]['qty_cap'], 1)
        for field in ('joint_scale', 'allocated_risk', 'allocated_buffered_margin', 'allocated_fee'):
            self.assertEqual(capped[1][field], original[1][field])
        self.assertEqual(self.k.ref.NATIVE_QUERIES, 0)

    def test_cash_signal_uses_selected_real_epoch_and_retains_parent_anchor(self):
        m = load('stage131_contract_choice_cash.py')
        self.assertIsNotNone(m, 'Stage131 cash wrapper is missing')
        market, dates = self.market()
        mothers = pd.DataFrame([dict(event_id='parent', product_id='P.X', family_id='P.X',
            u_date=dates[20], u_index=20, reference_epoch='P.X.202912')])
        actions = pd.DataFrame([dict(action_id='action', action_sequence_index=0, mother_event_id='parent',
            product_id='P.X', family_id='P.X', u_date=dates[20], u_index=20, reference_epoch='P.X.203001',
            anchor_epoch='P.X.202912', u_action_eligible=1, entry_capacity_qty=10,
            label_state='path_or_execution_unknown')])
        choices = mothers.assign(scope='main', policy='NARROW', arm='B', cutoff='2020-01-01', selected=1,
            chosen_action_id='action', chosen_action_sequence_index=0, chosen_epoch='P.X.203001',
            anchor_epoch='P.X.202912', score=1., selection_state='selected')
        result = m.make_signals(actions, mothers, choices, 'B', market, dates, self.econ())
        self.assertEqual(result.reference_epoch.tolist(), ['P.X.203001'])
        self.assertEqual(result.event_id.tolist(), ['action'])
        self.assertEqual(result.mother_event_id.tolist(), ['parent'])
        self.assertEqual(result.potential.tolist(), [1])
        self.assertEqual(result.N_u.iloc[0], market.indicator('P.X.203001', 20)['N'])

    def test_execution_capacity_unknown_cannot_pass_nominal_cash_gate(self):
        m = load('stage131_contract_choice_cash.py')
        self.assertIsNotNone(m, 'Stage131 cash wrapper is missing')
        points = [dict(window=w, cost=c, return_percentage_point_difference=1.,
            drawdown_percentage_point_difference=0., ci95_low=.001, active_total_return_pct=1.,
            identification='observed_cash_comparison') for w in ('primary_2020', 'cold_2023') for c in ('base', 'stress')]
        held = {'groups': {g: dict(nominal_pass=True, status='supported', unknown_differential_selected_events=0)
                          for g in ('holdout_0', 'holdout_1')}}
        held['groups']['main'] = dict(nominal_pass=False, status='unsupported')
        gate = m.continuation_gate(points, held, False, wealth_positive=True, execution_unknown=True)
        self.assertEqual(gate['status'], 'unknown_execution_capacity_or_entry')
        self.assertFalse(gate['nominal_pass'])
        self.assertFalse(gate['production_qualified'])


if __name__ == '__main__':
    unittest.main()
