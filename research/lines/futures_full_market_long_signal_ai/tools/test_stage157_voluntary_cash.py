"""Stage157 new synthetic boundaries only: no source arrays or actual books."""
import importlib.util
from pathlib import Path
import unittest
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load():
    path = TOOLS/'stage157_voluntary_cash.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('fixture157', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VoluntaryCash(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.assertIsNotNone(self.m, 'Stage157 implementation is missing')

    def signals(self, source=29, D=21):
        return pd.DataFrame([dict(event_id='child', mother_event_id='parent',
            product_id='P.X', family_id='P.X', reference_epoch='P.X.202002',
            anchor_epoch='P.X.202002', lifecycle_index=source, D_index=D)])

    def boundary(self, k=23, state='within_calendar'):
        return {'P.X.202002':dict(K_index=k, K_date=None if k is None else f'd{k}',
            K_target_date='2020-01-01', K_state=state, K_after_sample_end=False)}

    def test_source_boundary_is_never_extended_and_original_frame_is_not_mutated(self):
        original = self.signals(source=22)
        adapted = self.m.apply_boundaries(original, self.boundary(23))
        self.assertEqual(adapted.lifecycle_index.tolist(), [22])
        self.assertEqual(adapted.source_lifecycle_index.tolist(), [22])
        self.assertEqual(adapted.voluntary_boundary_index.tolist(), [23])
        self.assertEqual(original.columns.tolist(), self.signals().columns.tolist())
        adapted = self.m.apply_boundaries(self.signals(source=29), self.boundary(23))
        self.assertEqual(adapted.lifecycle_index.tolist(), [23])
        self.assertEqual(adapted.effective_boundary_origin.tolist(), ['voluntary_calendar'])

    def test_entry_on_K_is_a_selector_contract_failure(self):
        with self.assertRaisesRegex(ValueError, 'D<K'):
            self.m.apply_boundaries(self.signals(D=23), self.boundary(23))
        self.assertEqual(self.m.apply_boundaries(self.signals(D=22), self.boundary(23)).D_index.iloc[0],22)

    def test_after_calendar_boundary_stays_pending_without_terminal_clamp(self):
        adapted = self.m.apply_boundaries(self.signals(source=99),
            self.boundary(None,'after_calendar_pending'))
        self.assertEqual(adapted.lifecycle_index.tolist(), [99])
        self.assertTrue(pd.isna(adapted.voluntary_boundary_index.iloc[0]))
        self.assertEqual(adapted.effective_boundary_origin.tolist(), ['source_lifecycle'])

    def fixture_book(self):
        dates = [f'2020-01-{j:02d}' for j in range(1,31)]
        records=[]
        for k,day in enumerate(dates):
            if k in (23,24):
                continue
            records.append(dict(contract_epoch_id='P.X.202002',trade_date=day,
                open=100.,high=102.,low=98. if k<=20 else 100.,close=101.,volume=2000.,quality_status='accepted'))
        market=self.m.ref.Market.from_records(records,dates)
        ind=market.indicator('P.X.202002',20)
        sig=self.signals().assign(u_index=20,u_date=dates[20],N_u=ind['N'],low20_u=ind['low20'],
            u_close=101.,history_run=21,entry_capacity_qty=10,potential=1)
        sig=self.m.apply_boundaries(sig,self.boundary(23))
        econ={'P.X.202002':dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.1)}
        refs={k:{'P.X':'P.X.202002'} for k in range(len(dates))}
        return sig,market,dates,econ,refs

    def test_requested_K_exit_missing_quotes_preserves_quantity_and_old_mark_then_real_fill(self):
        sig,market,dates,econ,refs=self.fixture_book()
        book=self.m.kernel.run_cash_account(sig,market,dates,econ,'base','synthetic157',21,25,
            prepared=({20:sig.to_dict('records')},refs))
        self.assertEqual([f['side'] for f in book['fills']],['BUY','SELL'])
        self.assertEqual(book['fills'][-1]['date'],dates[25])
        by_day={p['date']:p for p in book['position_days']}
        self.assertEqual(by_day[dates[22]]['force_next'],'lifecycle_exit')
        self.assertEqual(by_day[dates[23]]['qty'],by_day[dates[22]]['qty'])
        self.assertEqual(by_day[dates[24]]['mark_state'],'stale')
        self.assertEqual(by_day[dates[24]]['mark'],by_day[dates[22]]['mark'])
        self.assertEqual(book['open_episodes'],[])
        annual=self.m.sector_year_attribution(book)
        self.assertEqual(len(annual),4)
        self.assertEqual([r['net_equity_contribution'] for r in annual
            if (r['dimension'],r['group']) in (('market_sector','financial'),('product_variant','F'))],[0.,0.])

    def test_full_original_canonical_not_selected_subset_drives_anchor_change(self):
        sig=self.signals().assign(u_index=0,u_date='2020-01-01')
        mothers=pd.DataFrame([dict(product_id='P.X',u_date='2020-01-01',reference_epoch='P.X.202002'),
            dict(product_id='P.X',u_date='2020-01-02',reference_epoch='P.X.202003')])
        potential,refs=self.m.author.organize(sig,mothers,['2020-01-01','2020-01-02'])
        self.assertEqual(refs[1]['P.X'],'P.X.202003')
        self.assertNotIn(1,potential)
        self.assertEqual(self.m.author.ARMS,('A','B'))

    def test_exact_four_new_accounts_and_nominal_gate_does_not_clear_unknown(self):
        specs=self.m.account_specs()
        self.assertEqual(len(specs),4)
        self.assertEqual({s['arm'] for s in specs},{'VOLUNTARY_RESELECT'})
        points=[dict(window=w,cost=c,active_total_return_pct=10.,
            return_percentage_point_difference=1.,drawdown_percentage_point_difference=1.,
            ci95_low=.001,identification='identified') for w in self.m.WINDOWS for c in self.m.COSTS]
        result=self.m.fixed_gate(points,True,wealth_positive=True,execution_unknown=False)
        self.assertTrue(result['cash_nominal_pass'])
        self.assertFalse(result['nominal_pass'])
        self.assertFalse(result['production_qualified'])
        points[1]['drawdown_percentage_point_difference']=0.
        self.assertFalse(self.m.fixed_gate(points,False,wealth_positive=True,execution_unknown=False)['cash_nominal_pass'])


if __name__=='__main__':
    unittest.main()
