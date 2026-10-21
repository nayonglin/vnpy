"""Only596 new synthetic boundaries; never historical account replay."""
import copy
import unittest
import pandas as pd
import stage597_winner_addition_kernel as k

E='P.X.203001';Q='Q.X.203001'
DATES=[f'2020-01-{i:02d}' for i in range(1,9)]
ECON={e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,round_lot=1,tick_size=.1,vendor_margin_rate=.1) for e in (E,Q)}
class Market:
    def __init__(self,*,stop=False,gap=False):self.stop=stop;self.gap=gap
    def bar(self,e,u):
        O=100. if u<2 else 98. if self.gap and u==2 and e==E else 110.
        L=98.5 if self.stop and u==2 and e==E else min(O,99.5 if u<2 else 109.5)
        return dict(open=O,high=max(O,111.),low=L,close=100. if u==0 else 110.,volume=1000.)
    def indicator(self,e,u):return dict(N=4.,low20=90.,run_length=60)
def signal(u,e=E,event=None):
    return dict(event_id=event or f'e{u}_{e}',mother_event_id=f'm{u}',product_id=e.rsplit('.',1)[0],family_id=e.rsplit('.',1)[0],reference_epoch=e,anchor_epoch=e.rsplit('.',1)[0]+'.201912',
        u_index=u,u_date=DATES[u],D_index=u+1,N_u=4.,low20_u=90.,u_close=100. if u==0 else 110.,history_run=60,
        lifecycle_index=99,entry_capacity_qty=5,u_gross_capacity_qty=10,potential=1)
def run(module,market,repeated=False):
    pots={0:[signal(0)]}
    if repeated:pots[1]=[signal(1)]
    refs={u:{'P.X':'P.X.201912','Q.X':'Q.X.201912'} for u in range(len(DATES))}
    return module.run_cash_account(pd.DataFrame(),market,DATES,ECON,'base','same',1,3,prepared=(pots,refs))
def position(**changes):
    p=dict(root_id='old',family_id='P.X',product_id='P.X',epoch=E,qty=5,initial_qty=5,entry_fill=100.1,entry_fees=5.,risk_per_lot=14.,last_mark=110.,stale=False,deferred=False,force_reason=None,reduce_to=None,expiry=99)
    p.update(changes);return p
def totals(**changes):
    t=dict(equity=1000000.,initial_risk=70.,buffered_margin=1210.);t.update(changes);return t

# All entry signals use a different canonical anchor from their actual epoch;
# canonical references remain unchanged, as legitimate nonfront131 positions do.
class WinnerAddition596(unittest.TestCase):
    def test_no_eligible_add_matches_original_economics(self):
        for stop in (False,True):
            m=Market(stop=stop);a=run(k.accepted,m);c=run(k,m)
            self.assertEqual(c['add_root_ids'],[])
            for aa,cc in zip(a['daily'],c['daily']):
                for key in ('equity','cash','cumulative_fees','cumulative_slippage','initial_risk','buffered_margin'):
                    self.assertAlmostEqual(aa[key],cc[key],places=8)
            af=sorted((r['root_id'],r['date'],r['side'],r['qty'],r['fill_price'],r['fee']) for r in a['fills'])
            cf=sorted((r['root_id'],r['date'],r['side'],r['qty'],r['fill_price'],r['fee']) for r in c['fills'])
            self.assertEqual(af,cf)

    def test_intraday_old_stop_cannot_cancel_open_add_and_batches_keep_SL0(self):
        b=run(k,Market(stop=True),True);adds=[f for f in b['fills'] if f.get('entry_kind')=='add' and f['side']=='BUY']
        self.assertEqual(len(adds),1);self.assertEqual(adds[0]['date'],DATES[2]);self.assertEqual(adds[0]['qty'],2)
        ep={p['entry_kind']:p for p in b['closed_episodes']}
        self.assertEqual(ep['fresh']['SL0'],99.);self.assertEqual(ep['add']['SL0'],109.)
        d=[f for f in b['fills'] if f['date']==DATES[2]]
        self.assertEqual(d[0]['side'],'BUY');self.assertEqual(sum(f['qty'] for f in d),9)
        self.assertNotEqual(ep['fresh']['root_id'],ep['add']['root_id'])

    def test_known_opening_sell_cancels_add_not_fresh(self):
        b=run(k,Market(gap=True),True)
        self.assertEqual(b['add_root_ids'],[]);self.assertEqual(b['add_audit'][0]['D_qty'],0)
        self.assertEqual(b['add_audit'][0]['reason'],'add_opening_family_sell')

    def test_aggregate_remaining_fee_not_raw_profit(self):
        c=signal(1);c['u_close']=100.2
        m=Market();m.bar=lambda e,u:dict(open=100.2,high=101.,low=100.,close=100.2,volume=1000.)
        p=position(qty=3,initial_qty=10,entry_fees=20.,last_mark=100.2)
        proposal,audit=k.add_proposal(c,[p],totals(),m,DATES,1,ECON,'base')
        quote=k.adverse_quote(100.2,'SELL',ECON[E],'base')
        expected=3*(10*(quote['fill_price']-100.1)-2.-quote['fee_per_lot'])
        self.assertAlmostEqual(audit['net_remaining_profit'],expected);self.assertIsNone(proposal)
        self.assertEqual(p['entry_fees'],20.)

    def test_family_F0_not_released_by_old_stop_and_zero_add_does_not_crowd(self):
        p=position(qty=5,risk_per_lot=499.9);p['boundary']=109.9
        add,audit=k.add_proposal(signal(1),[p],totals(initial_risk=2499.5),Market(),DATES,1,ECON,'base')
        self.assertAlmostEqual(audit['family_headroom'],.5);self.assertIsNone(add);self.assertEqual(audit['prebatch_qty_upper'],0)
        fresh=dict(signal(1,Q),entry_kind='fresh')
        original=k.accepted.reserve_capped([fresh],1000000.,2499.5,1210.,ECON,'base')
        mixed=k.reserve_mixed([fresh],1000000.,2499.5,1210.,ECON,'base')
        for field in ('joint_scale','qty_cap','allocated_risk','allocated_buffered_margin','allocated_fee'):self.assertEqual(original[0][field],mixed[0][field])

    def test_shared_capacity_counts_old_quantity_and_all_gross(self):
        add,audit=k.add_proposal(signal(1),[position(qty=8,initial_qty=8)],totals(),Market(),DATES,1,ECON,'base')
        self.assertEqual(audit['add_capacity_u'],1);self.assertEqual(add['add_capacity_u'],1)
        self.assertEqual(k.shared_add_quantity(5,1,10,3,5),1)
        self.assertEqual(k.shared_add_quantity(5,1,10,7,5),0)

    def test_other_stale_equity_and_any_parent_exit_state_block_add(self):
        other=position(root_id='other',family_id='Q.X',product_id='Q.X',epoch=Q,stale=True)
        add,audit=k.add_proposal(signal(1),[position(),other],totals(),Market(),DATES,1,ECON,'base')
        self.assertIsNone(add);self.assertTrue(audit['unknown'])
        for field,value in [('force_reason','lifecycle_exit'),('reduce_to',4)]:
            add,audit=k.add_proposal(signal(1),[position(**{field:value})],totals(),Market(),DATES,1,ECON,'base')
            self.assertIsNone(add)

    def test_every_batch_original_risk_still_counts(self):
        b=run(k,Market(),True);roots=b['open_episodes']
        self.assertEqual(len(roots),2);self.assertEqual(len(b['add_root_ids']),1)
        self.assertAlmostEqual(b['daily'][-1]['initial_risk'],sum(p['qty']*p['risk_per_lot'] for p in roots))
        self.assertEqual(next(p for p in roots if p['entry_kind']=='fresh')['SL0'],99.)

if __name__=='__main__':unittest.main()
