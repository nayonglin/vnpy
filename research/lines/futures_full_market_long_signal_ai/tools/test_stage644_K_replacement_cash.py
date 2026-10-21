"""Eight new synthetic contracts only; no history/cache/actual execution."""
import copy
import importlib.util
from pathlib import Path
import unittest
import pandas as pd

TOOLS=Path(__file__).resolve().parent

def load():
    p=TOOLS/'stage644_K_replacement_kernel.py'
    if not p.exists():return None
    spec=importlib.util.spec_from_file_location('fixture644',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def econ(tick=.1):
    return dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
        round_lot=1,tick_size=tick,vendor_margin_rate=.2,future_info_scope='synthetic')

def signal(event,epoch,u,K,product='P.X',N=8.):
    return dict(event_id=event,mother_event_id='mother_'+event,action_sequence_index=u,
        product_id=product,family_id=product,reference_epoch=epoch,anchor_epoch='anchor_'+product,
        u_index=u,u_date=f'2020-01-{u+1:02d}',D_index=u+1,N_u=N,low20_u=90.,u_close=100.,
        label_history_ready20=1,history_run=30,entry_capacity_qty=50,u_gross_capacity_qty=100,
        potential=1,score=.1,arm='VOLUNTARY_RESELECT',policy='NARROW',cutoff='2020-01-01',
        source_lifecycle_index=15,voluntary_boundary_index=K,effective_lifecycle_index=K,
        lifecycle_index=K,effective_boundary_origin='voluntary_calendar',K_state='within_calendar',
        K_target_date=f'2020-01-{K+1:02d}',K_date=f'2020-01-{K+1:02d}')

class Market:
    def __init__(self,dates,epochs):
        self.dates=dates;self.series={e:{} for e in epochs}
        self.bars={(e,k):dict(open=100.,high=101.,low=99.,close=100.,volume=1000000.)
            for e in epochs for k in range(len(dates))}
    def bar(self,e,k):return copy.deepcopy(self.bars.get((e,k)))
    def indicator(self,e,k):return dict(N=8.,low20=90.,run_length=30)

class ReplacementCash(unittest.TestCase):
    def setUp(self):
        self.m=load();self.assertIsNotNone(self.m,'new644 kernel is not implemented')
    def fixture(self,third=False,other=False):
        dates=[f'2020-01-{k+1:02d}' for k in range(9)]
        ss=[signal('old','old',0,3),signal('new','new',2,5)]
        if third:ss.append(signal('third','third',4,8))
        if other:ss.append(signal('other','other',0,8,'Q.X'))
        es={s['reference_epoch']:econ() for s in ss};market=Market(dates,es)
        refs={k:{'P.X':'anchor_P.X','Q.X':'anchor_Q.X'} for k in range(9)}
        sig=pd.DataFrame(ss);pot={k:g.to_dict('records') for k,g in sig.groupby('u_index')}
        return sig,market,dates,es,(pot,refs)
    def runbook(self,fixture,end=3):
        sig,market,dates,es,prepared=fixture
        return self.m.run_cash_account(sig,market,dates,es,'base','synthetic644',1,end,prepared=prepared)
    def parent(self):
        return dict(root_id='parent',event_id='old',family_id='P.X',product_id='P.X',epoch='old',
            anchor_epoch='anchor_P.X',qty=10,risk_per_lot=30.,last_mark=100.,multiplier=10.,
            margin_rate=.2,round_lot=1,expiry=3,force_reason='lifecycle_exit',stale=False,
            stale_days=0,deferred=False,reduce_to=None,source_lifecycle_index=15,
            voluntary_boundary_index=3,effective_lifecycle_index=3,effective_boundary_origin='voluntary_calendar')
    def total(self):return dict(equity=1000000.,initial_risk=300.,buffered_margin=2200.)
    def token(self):
        return self.m.reserve_slot(signal('new','new',2,5),self.parent(),self.total(),
            {'old':econ(),'new':econ()},'base',[])

    def test_no_replacement_retains_original_131_economic_path(self):
        f=self.fixture();f[0].drop(f[0].index[f[0].event_id.eq('new')],inplace=True)
        f[4][0].pop(2)
        old=self.m.accepted.run_cash_account(f[0],f[1],f[2],f[3],'base','synthetic644',1,6,prepared=f[4])
        new=self.runbook(f,6)
        for role in ('fills','daily','budgets','position_days'):
            self.assertEqual(len(old[role]),len(new[role]))
            for a,b in zip(old[role],new[role]):
                for k,v in a.items():self.assertEqual(v,b[k],(role,k))
        self.assertEqual(old['summary'],new['summary'])
        self.assertEqual(new['replacement_root_ids'],[])

    def test_ordinary_old_slot_stays_occupied_and_contingent_is_not_double_reserved(self):
        b=self.runbook(self.fixture())
        u=b['daily'][1]
        self.assertEqual(u['date'],'2020-01-03')
        self.assertEqual(u['new_order_reserve'],0.)
        self.assertGreater(u['replacement_contingent_funds'],0.)
        self.assertEqual(u['total_reserve'],u['buffered_margin'])
        ordinary=[r for r in b['budgets'] if r['event_id']=='new']
        self.assertEqual(len(ordinary),1)
        self.assertEqual(ordinary[0]['budget_state'],'family_occupied')
        self.assertEqual(len(b['replacement_root_ids']),1)

    def test_integer_slot_reserves_old_sell_estimate_and_new_roundtrip_without_profit_credit(self):
        t=self.token()
        self.assertEqual((t['old_risk'],t['old_buffered_margin'],t['old_sell_fee_u']),(300.,2200.,20.))
        self.assertEqual(t['qty_cap'],9)
        self.assertAlmostEqual(t['target_qty_prefloor'],9.732142857142858)
        self.assertAlmostEqual(t['allocated_risk'],253.03571428571428)
        self.assertAlmostEqual(t['allocated_funds'],2180.)
        proof={'confirmed':True,'unknown':False,'ell':0.,'reason':'confirmed_full_K_open'}
        self.m.size_batch([t],{'parent':proof},{'new':110.},{'old':econ(),'new':econ()},'base')
        self.assertLessEqual(t['D_qty'],9)
        b=self.runbook(self.fixture())
        self.assertEqual(b['daily'][-1]['cumulative_fees'],sum(f['fee'] for f in b['fills']))
        self.assertEqual(b['daily'][-1]['equity_identity_error'],0.)
        # A continuous110 risk allowance retains one lot when r rises100→100.01.
        parent=self.parent();parent.update(qty=1,risk_per_lot=110.,last_mark=1000.)
        small=self.m.reserve_slot(signal('new','new',2,5,N=38.32),parent,self.total(),
            {'old':econ(None),'new':econ(None)},'base',[])
        self.assertEqual(small['qty_cap'],1)
        self.assertAlmostEqual(small['allocated_risk'],110.)
        self.m.size_batch([small],{'parent':proof},{'new':105.},{'new':econ(None)},'base')
        self.assertAlmostEqual(small['unit_risk_u'],100.)
        self.assertAlmostEqual(small['unit_risk_D'],100.01)
        self.assertEqual(small['D_qty'],1)
        parent.update(risk_per_lot=1000.,last_mark=248.4/2.2)
        fund=self.m.reserve_slot(signal('new','new',2,5),parent,
            dict(equity=1e6,initial_risk=1000.,buffered_margin=248.4),
            {'old':econ(),'new':econ()},'base',[])
        self.assertAlmostEqual(fund['target_qty_prefloor'],1.1)
        self.assertAlmostEqual(fund['allocated_funds'],246.4)
        self.m.size_batch([fund],{'parent':proof},{'new':110.},{'new':econ()},'base')
        self.assertEqual(fund['D_qty'],1)  # Own fractional funds survive; never>qu.

    def test_loss_common_scale_never_recycles_cancelled_parent_or_rounding(self):
        t=self.token();t.update(u_equity=10000.,u_total_risk=200.,u_total_margin=20000.,
            old_risk=5.,old_buffered_margin=5.,ordinary_allocated_risk=0.,ordinary_allocated_funds=0.,
            allocated_risk=10.,allocated_funds=1000.,old_buffered_margin_slot=10000.,qty_cap=10,
            N_u=.1,old_root_id='p1')
        other=dict(t,event_id='two',reference_epoch='two',old_root_id='p2',old_risk=5.)
        proofs={'p1':dict(confirmed=True,unknown=False,ell=1000.,reason='confirmed_full_K_open'),
            'p2':dict(confirmed=True,unknown=False,ell=0.,reason='confirmed_full_K_open')}
        self.m.size_batch([t,other],proofs,{'new':100.,'two':90.},
            {'new':econ(),'two':econ()},'base')
        self.assertEqual(t['E_virtual'],9000.)
        self.assertEqual(other['q_self'],0)
        self.assertEqual(t['R_other'],195.)  # p2 canceled keeps its old slot.
        self.assertEqual(t['R_free'],0.)
        self.assertEqual(t['D_qty'],0)

    def test_u_requires_strict_pure_K_own_canonical_and_no_stale_or_reduction(self):
        c=signal('new','new',2,5);refs={2:{'P.X':'anchor_P.X'}};es={'old':econ(),'new':econ()}
        self.assertEqual(self.m.replacement_reason(self.parent(),c,2,refs,es,self.total()),('',False))
        variants=[('source_lifecycle_index',3),('effective_boundary_origin','same_source_and_voluntary'),
            ('stale',True),('reduce_to',0),('force_reason','liquidity_reference_changed')]
        for key,value in variants:
            p=self.parent();p[key]=value
            self.assertNotEqual(self.m.replacement_reason(p,c,2,refs,es,self.total())[0],'')
        self.assertTrue(self.m.replacement_reason(self.parent(),c,2,{},es,self.total())[1])
        self.assertNotEqual(self.m.replacement_reason(self.parent(),dict(c,reference_epoch='old'),2,refs,es,self.total())[0],'')
        pending=self.parent();pending.update(voluntary_boundary_index=None,effective_boundary_origin='source_lifecycle')
        self.assertFalse(self.m.replacement_reason(pending,c,2,refs,es,self.total())[1])

    def test_old_missing_partial_wrong_exit_or_unknown_capacity_cannot_unlock_new_buy(self):
        t=self.token();fill=dict(root_id='parent',epoch='old',side='SELL',qty=10,
            date='2020-01-04',reason='lifecycle_exit',fill_price=99.9,fee=20.,
            capacity_state='within_fixed_daily_capacity')
        good=self.m.confirm_old(t,[fill],{},'2020-01-04')
        self.assertTrue(good['confirmed']);self.assertAlmostEqual(good['ell'],30.)
        for fs,pos in [([],{'parent':dict(qty=10)}),([dict(fill,qty=5)],{'parent':dict(qty=5)}),
                ([dict(fill,reason='research_deferred_liquidation')],{}),
                ([dict(fill,capacity_state='execution_capacity_unknown')],{})]:
            p=self.m.confirm_old(t,fs,pos,'2020-01-04');self.assertFalse(p['confirmed'])
        f=self.fixture();f[1].bars.pop(('old',3))
        b=self.runbook(f)
        self.assertFalse(any(r['event_id']=='new' and r['side']=='BUY' for r in b['fills']))
        self.assertTrue(b['replacement_unknown'])

    def test_new_raw_open_stop_two_leg_cost_and_saved_K_allow_later_own_replacement(self):
        f=self.fixture();f[1].bars[('new',3)]['low']=97.
        b=self.runbook(f);root=next(r for r in b['closed_episodes'] if r['event_id']=='new')
        self.assertEqual(root['SL0'],98.)
        self.assertNotEqual(root['SL0'],root['entry_fill']-2.)
        self.assertEqual(root['source_lifecycle_index'],15)
        self.assertEqual(root['voluntary_boundary_index'],5)
        self.assertGreater(root['entry_fees'],0.);self.assertGreater(root['exit_fees'],0.)
        b2=self.runbook(self.fixture(third=True),6)
        self.assertEqual(len(b2['replacement_root_ids']),2)
        self.assertEqual([f['event_id'] for f in b2['fills'] if f['side']=='BUY'],['old','new','third'])

    def test_D_sizing_uses_frozen_u_not_unrelated_D_low_close_and_extreme_buy_cash(self):
        a=self.fixture(other=True);b=self.fixture(other=True)
        a[1].bars[('other',3)].update(low=90.,close=95.)
        b[1].bars[('other',3)].update(low=99.,close=100000.)
        aa=self.runbook(a);bb=self.runbook(b)
        qa=[f['qty'] for f in aa['fills'] if f['event_id']=='new' and f['side']=='BUY']
        qb=[f['qty'] for f in bb['fills'] if f['event_id']=='new' and f['side']=='BUY']
        self.assertEqual(qa,qb);self.assertTrue(qa)
        t=self.token();t.update(qty_cap=10,allocated_risk=1000000.,allocated_funds=2500.,
            old_buffered_margin_slot=2500.,u_equity=1e9,u_total_risk=300.,u_total_margin=2200.)
        self.m.size_batch([t],{'parent':dict(confirmed=True,unknown=False,ell=0.,reason='confirmed_full_K_open')},
            {'new':100.},{'new':econ(40.)},'base')
        self.assertEqual(t['fund_unit_D'],322.)
        self.assertEqual(t['q_self'],7)
        self.assertEqual(t['D_qty'],7)
        rp=TOOLS/'stage644_K_replacement_cash.py'
        spec=importlib.util.spec_from_file_location('fixture644runner',rp)
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        rm=runner.RecordingMarket(a[1]);rm.account='test';self.assertIsNone(rm.bar('missing',0))
        self.assertTrue(rm.bars[('missing',0)]['missing'])
        refs=runner.RecordingReferences({});refs.account='test'
        self.assertIsNone(refs.get(0,{}).get('P.X'))
        self.assertFalse(refs.queried[(0,'P.X')]['present'])
        points=[dict(active_total_return_pct=10.,return_percentage_point_difference=1.,
            drawdown_percentage_point_difference=0.,ci95_low=.1) for _ in range(4)]
        summaries=[dict(account=str(i),execution_unknown=False,replacement_unknown=False,
            terminal_unresolved_open=0) for i in range(4)]
        reports={str(i):dict(stale_days=0) for i in range(4)}
        self.assertTrue(runner.fixed_gate(points,summaries,reports,True,True)['nominal_pass'])
        points[0]['ci95_low']=0.
        self.assertFalse(runner.fixed_gate(points,summaries,reports,False,True)['nominal_pass'])
        points[0]['ci95_low']=.1;summaries[0]['replacement_unknown']=True
        self.assertFalse(runner.fixed_gate(points,summaries,reports,False,True)['nominal_pass'])

if __name__=='__main__':unittest.main()
