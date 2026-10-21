"""Ten bounded synthetic behaviors for causal cross-session cash accounting."""
import importlib.util
from datetime import date,timedelta
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

sp=importlib.util.spec_from_file_location('s042',Path(__file__).with_name('stage042_cross_session_experiment.py'))
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)

def fixture(missing=(),finish=60):
    dates=[(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(finish)]
    epoch='X.A.203001';records=[];panel=[]
    for i,d in enumerate(dates):
        if i<55:o,h,l,c=100.,101.,99.,100.
        elif i==55:o,h,l,c=105.,106.,104.,105.
        else:o,h,l,c=106.,107.,105.,106.
        if i not in missing:records.append(dict(contract_epoch_id=epoch,trade_date=d,open=o,high=h,low=l,close=c,volume=10.,quality_status='accepted'))
        panel.append(dict(event_id=f'e{i}',product_id='X.A',exchange='X',product='A',u_date=d,reference_epoch=epoch if i not in missing else '',
            status='observed_long_research_opportunity' if i not in missing else 'no_accepted_observation',planned_execution_date=dates[i+1] if i+1<len(dates) else '',direction='long'))
    econ={epoch:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=1.,round_lot=1.,tick_size=None,vendor_margin_rate=.2,listed_date='2019-01-01',
        known_lifecycle_exit_boundary='2030-01-01',nominal_month_first_date='2030-01-01',future_info_scope='product_default_snapshot')}
    return dates,records,pd.DataFrame(panel),econ

class CrossSessionBehavior(unittest.TestCase):
    def test_N_seed_recursion_gap_reset_and_future_prefix(self):
        d,r,p,e=fixture();market=m.Market.from_records(r,d)
        self.assertAlmostEqual(market.indicator('X.A.203001',19)['N'],2.)
        self.assertAlmostEqual(market.indicator('X.A.203001',55)['N'],2.2)
        prefix=m.Market.from_records(r[:56],d)
        self.assertEqual(prefix.indicator('X.A.203001',55),market.indicator('X.A.203001',55))
        broken=m.Market.from_records([x for x in r if x['trade_date']!=d[50]],d)
        self.assertEqual(broken.indicator('X.A.203001',55)['run_length'],5)
        self.assertTrue(np.isnan(broken.indicator('X.A.203001',55)['N']))

    def test_signal_uses_prior55_and_retains_all_missing_product_days(self):
        d,r,p,e=fixture(missing=(57,));market=m.Market.from_records(r,d);s=m.build_signals(p,market,d,e)
        self.assertEqual(len(s),60);self.assertEqual(int(s.loc[54,'policy_ready55']),0)
        self.assertEqual(int(s.loc[55,'breakout']),1);self.assertEqual(s.loc[55,'high55_before'],101.)
        self.assertEqual(s.loc[57,'signal_state'],'no_accepted_observation')
        self.assertEqual(int(s.loc[58,'policy_ready55']),0)

    def test_exit_boundary_is_previous_close_and_gap_loss_is_not_capped(self):
        self.assertEqual(m.price_exit_reference(100,95,96,None),(96.,'stop_boundary'))
        self.assertEqual(m.price_exit_reference(70,60,96,None),(70.,'gap_stop'))
        self.assertLess((70-100)/20,-1)
        self.assertEqual(m.next_boundary(90,98),98);self.assertEqual(m.next_boundary(90,94),94)

    def test_roll_exits_old_epoch_and_earlier_F_lifecycle_is_used(self):
        self.assertEqual(m.close_exit_request('X.A.203001','X.A.203002',10,20),'liquidity_reference_changed')
        self.assertEqual(m.close_exit_request('X.A.203001',None,10,20),'observation_exit_requested')
        self.assertEqual(m.close_exit_request('X.A.203001','X.A.203001',20,20),'lifecycle_exit')
        econ={'known_lifecycle_exit_boundary':'2027-02-26','nominal_month_first_date':'2027-03-01'}
        self.assertEqual(m.lifecycle_index(econ,'DCE.L_F.202703',['2027-02-25','2027-02-26','2027-03-01']),1)

    def test_family_selection_uses_economics_before_plain_priority(self):
        candidates=[dict(event_id='f',family_id='DCE.L',product_id='DCE.L_F',reference_epoch='DCE.L_F.202703'),dict(event_id='n',family_id='DCE.L',product_id='DCE.L',reference_epoch='DCE.L.202703')]
        economics={'DCE.L.202703':{'economics_status':'unresolved_exact_epoch_metadata'},'DCE.L_F.202703':{'economics_status':'exact_epoch_metadata_snapshot','contract_multiplier':5,'round_lot':1}}
        chosen,rejected=m.select_family_candidates(candidates,set(),economics,cash=True)
        self.assertEqual([c['event_id'] for c in chosen],['f']);self.assertEqual(rejected['n'],'instrument_economics_unqualified')
        chosen,_=m.select_family_candidates(candidates,set(),economics,cash=False)
        self.assertEqual([c['event_id'] for c in chosen],['n'])

    def test_u_reservation_uses_prefloor_fraction_and_D_cannot_reallocate(self):
        d,r,p,e=fixture();eco=e['X.A.203001']
        candidates=[dict(event_id='a',family_id='X.A',reference_epoch='X.A.203001',u_close=100.,N_u=1.)]
        reservations=m.reserve_batch(candidates,100000.,0.,0.,e,'base')
        a=reservations[0];self.assertEqual(a['qty_cap'],41);self.assertAlmostEqual(a['allocated_risk'],250.)
        q,details=m.execution_quantity(a,100.01,eco,'base')
        self.assertEqual(q,41)  # fractional own reserve absorbs tiny cost increase; floor-then-reserve would lose a lot.
        q,_=m.execution_quantity(a,1000.,eco,'base');self.assertLess(q,41)
        self.assertEqual(a['qty_cap'],41)
        two=[dict(candidates[0]),dict(candidates[0],event_id='b',family_id='X.B',reference_epoch='X.B.203001')]
        economics=dict(e,**{'X.B.203001':dict(eco)})
        separate=m.reserve_batch(two,100000.,0.,0.,economics,'base')
        before=dict(separate[1]);qa,_=m.execution_quantity(separate[0],1e9,eco,'base')
        qb,_=m.execution_quantity(separate[1],100.01,eco,'base')
        self.assertEqual(qa,0);self.assertEqual(qb,41);self.assertEqual(separate[1],before)
        crowded=m.reserve_batch(candidates*2,100000.,1990.,0.,e,'base')
        self.assertTrue(all(v['qty_cap']==0 for v in crowded));self.assertTrue(all(v['joint_scale']<1 for v in crowded))

    def test_partial_exit_cash_mark_and_slippage_are_not_double_counted(self):
        ledger=m.CashLedger(1000.)
        root=dict(root_id='r',event_id='e',family_id='X.A',product_id='X.A',epoch='X.A.203001',entry_date='2020-01-01',multiplier=10.,risk_per_lot=20.,margin_rate=.2,round_lot=1)
        ledger.enter(root,2,100.,101.,2.,10.)
        ledger.mark('r',110.,False)
        self.assertAlmostEqual(ledger.totals()['equity'],1176.)
        ledger.exit('r',1,112.,111.,3.,10.,'2020-01-02','reduce')
        self.assertAlmostEqual(ledger.totals()['equity'],1183.)
        ledger.exit('r',1,108.,107.,3.,10.,'2020-01-03','exit')
        t=ledger.totals();self.assertEqual(t['cash'],1150.);self.assertEqual(t['unrealized'],0.)
        self.assertEqual(ledger.closed[0]['net_pnl'],150.);self.assertEqual(t['cumulative_slippage'],40.)

    def test_missing_path_is_unknown_but_cash_delays_exit_without_freeing(self):
        d,r,p,e=fixture(missing=(57,));market=m.Market.from_records(r,d);signals=m.build_signals(p,market,d,e)
        price=m.run_price_chain(signals,market,d,e)
        self.assertEqual(price['episodes'][0]['state'],'path_or_execution_unknown')
        cash=m.run_cash_account(signals,market,d,e,'base','test',56,59,100000.)
        daily=pd.DataFrame(cash['daily']);self.assertGreater(daily.loc[daily.date.eq(d[57]),'stale_notional'].iloc[0],0.)
        exits=[v for v in cash['fills'] if v['side']=='SELL']
        self.assertEqual(exits[0]['date'],d[58]);self.assertEqual(exits[0]['reason'],'research_deferred_liquidation')

    def test_first_window_open_uses_pre_u_budget_and_terminal_is_not_fake_exit(self):
        d,r,p,e=fixture();market=m.Market.from_records(r,d);signals=m.build_signals(p,market,d,e)
        cash=m.run_cash_account(signals,market,d,e,'base','test',56,56,100000.)
        buys=[x for x in cash['fills'] if x['side']=='BUY'];self.assertEqual(len(buys),1);self.assertEqual(buys[0]['date'],d[56])
        self.assertEqual(cash['budgets'][0]['u_date'],d[55]);self.assertTrue(cash['budgets'][0]['pre_window_reservation'])
        self.assertEqual(cash['summary']['closed_trades'],0);self.assertEqual(cash['summary']['open_positions'],1)
        poisoned=[dict(x,**{name:x[name]*100 for name in ('open','high','low','close')}) if x['trade_date']>d[56] else dict(x) for x in r]
        future=m.Market.from_records(poisoned,d);future_signals=m.build_signals(p,future,d,e)
        repeated=m.run_cash_account(future_signals,future,d,e,'base','test',56,56,100000.)
        prefix=m.Market.from_records([x for x in r if x['trade_date']<=d[56]],d)
        prefix_signals=m.build_signals(p.iloc[:57],prefix,d,e)
        truncated=m.run_cash_account(prefix_signals,prefix,d,e,'base','test',56,56,100000.)
        self.assertEqual(cash['fills'],repeated['fills']);self.assertEqual(cash['fills'],truncated['fills'])
        self.assertEqual(cash['budgets'],repeated['budgets']);self.assertEqual(cash['budgets'],truncated['budgets'])

    def test_insolvency_is_permanent_and_reductions_preserve_round_lot(self):
        self.assertTrue(m.insolvency_flag(False,-1));self.assertTrue(m.insolvency_flag(True,1000000))
        positions=[dict(qty=11,round_lot=2,risk_per_lot=100.,last_mark=100.,multiplier=10.,margin_rate=.2)]
        target=m.reduction_targets(positions,1000.)
        self.assertEqual(target,[0])
        no=m.reserve_batch([dict(event_id='a',family_id='X.A',reference_epoch='X.A.203001',u_close=100.,N_u=1.)],-1.,0.,0.,fixture()[3],'base')
        self.assertEqual(no[0]['qty_cap'],0)

if __name__=='__main__':unittest.main()
