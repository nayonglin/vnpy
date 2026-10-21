"""One bounded state fixture: synthetic real131, no native/SQL/financial run."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

TOOLS=Path(__file__).resolve().parent
def load(filename):
    p=TOOLS/filename
    if not p.exists():return None
    s=importlib.util.spec_from_file_location('fixture322_'+p.stem,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class TinyState(unittest.TestCase):
    def test_sealed_budget_continues_across_restore_without_recycling_or_false_expiry(self):
        # Breaks on empty-ledger restart, repeated D, shared scenarios, discarded
        # pending, D budget recycling, len(calendar) expiry or lost missing state.
        b=load('stage322_continuous_paper_state.py')
        self.assertIsNotNone(b,'new continuous paper bridge is missing')
        k=load('stage131_contract_choice_kernel.py')
        dates=['2030-01-02','2030-01-03','2030-01-04','2030-01-07']
        epochs={x:x+'.203002' for x in ('P.X','Q.X','R.X','S.X')}
        econ={e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,round_lot=1,
                    tick_size=.1,vendor_margin_rate=.1) for e in epochs.values()}
        class Market:
            def __init__(self):self.reads=[]
            def bar(self,epoch,j):
                self.reads.append(j)
                if (epoch==epochs['Q.X'] and j==1) or (epoch==epochs['P.X'] and j==2) or (epoch==epochs['S.X'] and j==2):return None
                return dict(open=100.,high=103.,low=100.,close=100.+j,volume=200. if epoch==epochs['P.X'] else 1000000.)
            def indicator(self,epoch,j):self.reads.append(j);return dict(N=.1,low20=90.,run=21+j)
        market=Market()
        def signal(product,u,event,target):
            return dict(event_id=event,mother_event_id='m_'+event,product_id=product,family_id=product,
                reference_epoch=epochs[product],anchor_epoch=epochs[product],u_index=u,u_date=dates[u],D_index=u+1,
                N_u=.1,low20_u=90.,u_close=100.+u,history_run=21+u,lifecycle_index=2 if product!='S.X' else 99,
                entry_capacity_qty=1 if product=='P.X' else 5000,potential=1,score=.5,
                source_lifecycle_target_date='2030-02-01',source_lifecycle_state='outside_calendar',
                K_target_date=target,K_state='beyond_sample_end')
        potential={0:[signal(p,0,p,dates[2]) for p in ('P.X','Q.X','R.X')],
                   1:[signal('S.X',1,'newS','2030-02-01')]}
        refs={j:dict(epochs) for j in range(len(dates))}
        original_code=k.run_cash_account.__code__;original_factory=k.run_cash_account.__globals__['CapacityLedger']
        finished={}
        for scenario,quantity,equity1,equity2 in [('base',378,1002653.,997739.),('stress',136,1000137.,997553.)]:
            aid='tiny_'+scenario
            state=b.new_state(scenario=scenario,account_id=aid,start_u=0,base_kernel=k)
            self.assertEqual(state['ledger']['initial'],1000000.)
            original=json.loads(b.export_state(state))
            sealed=b.seal_u(state,u_index=0,prepared=(potential,refs),market=market,dates=dates[:2],economics=econ,base_kernel=k)
            self.assertEqual(json.loads(b.export_state(state)),original)
            self.assertEqual(sealed['phase'],'awaiting_D')
            self.assertEqual(len(sealed['pending']),3)
            cap={r['event_id']:r['qty_cap'] for r in sealed['pending']}
            self.assertEqual(cap['P.X'],1);self.assertEqual(cap['R.X'],quantity)
            self.assertFalse(market.reads)  # seal uses no D/open/indicator reads
            with self.assertRaises(ValueError):b.seal_u(sealed,u_index=0,prepared=(potential,refs),market=market,dates=dates[:2],economics=econ,base_kernel=k)
            restored=b.restore_state(b.export_state(sealed))
            one=b.advance_D(restored,D_index=1,references=refs[1],market=market,dates=dates[:2],economics=econ,base_kernel=k)
            self.assertEqual(one['daily'][-1]['equity'],equity1)
            self.assertEqual([f['qty'] for f in one['ledger']['fills']],[1,quantity])
            self.assertEqual(len(one['entry_execution_unknown']),1)
            self.assertTrue(all(p['force_reason'] is None for p in one['ledger']['positions'].values()))
            self.assertTrue(all(p['expiry_state']=='pending_calendar' for p in one['ledger']['positions'].values()))
            with self.assertRaises(ValueError):b.advance_D(one,D_index=1,references=refs[1],market=market,dates=dates[:2],economics=econ,base_kernel=k)
            market.reads.clear()
            # Calendar extension now confirms the previously sealed target. No
            # target is changed; lifecycle is refreshed before D2's real open.
            two_sealed=b.seal_u(one,u_index=1,prepared=(potential,refs),market=market,dates=dates[:3],economics=econ,base_kernel=k)
            self.assertTrue(all(p['expiry']==2 and p['force_reason']=='lifecycle_exit' for p in two_sealed['ledger']['positions'].values()))
            self.assertGreater(two_sealed['daily'][-1]['new_order_reserve'],0.)
            direct=b.advance_D(two_sealed,D_index=2,references=refs[2],market=market,dates=dates[:3],economics=econ,base_kernel=k)
            resumed=b.advance_D(b.restore_state(b.export_state(two_sealed)),D_index=2,references={2:refs[2]},market=market,dates=dates[:3],economics=econ,base_kernel=k)
            self.assertEqual(b.export_state(direct),b.export_state(resumed))
            self.assertEqual(direct['daily'][-1]['equity'],equity2)
            self.assertEqual(len(direct['entry_execution_unknown']),2)
            self.assertEqual(len(direct['ledger']['positions']),1)
            remaining=next(iter(direct['ledger']['positions'].values()))
            self.assertTrue(remaining['stale'] and remaining['deferred'])
            self.assertEqual(direct['ledger']['closed'][0]['exit_reason'],'lifecycle_exit')
            # Single bounded original131 synthetic execution is the comparator,
            # not an old historical replay. Quantities/fees/path must agree.
            original_book=k.run_cash_account(None,market,dates,econ,scenario,aid,1,2,prepared=(potential,refs))
            self.assertEqual(direct['ledger']['fills'],original_book['fills'])
            self.assertEqual([r['equity'] for r in direct['daily']],[r['equity'] for r in original_book['daily']])
            self.assertEqual(direct['ledger']['capacity_audit'],original_book['capacity_audit'])
            self.assertEqual(direct['daily'][0]['new_order_reserve'],original_book['daily'][0]['new_order_reserve'])
            self.assertEqual(direct['last_D'],2)
            self.assertEqual(direct['ledger']['realized'],original_book['summary']['cumulative_realized_gross'])
            self.assertEqual(direct['ledger']['fees'],original_book['summary']['total_fees'])
            finished[scenario]=direct
            market.reads.clear()
        self.assertNotEqual(finished['base']['ledger']['fees'],finished['stress']['ledger']['fees'])
        bad=copy.deepcopy(finished['base']);bad['scenario']='stress'
        with self.assertRaises(ValueError):b.restore_state(b.export_state(bad))
        payload=json.loads(b.export_state(finished['base']));payload['state']['last_D']=0
        with self.assertRaises(ValueError):b.restore_state(json.dumps(payload))
        # A previously insolvent scenario cannot quietly resume at positive E.
        paused=b.new_state(scenario='base',account_id='paused',start_u=0,base_kernel=k);paused['ever_insolvent']=True
        paused=b.seal_u(paused,u_index=0,prepared=(potential,refs),market=market,dates=dates[:2],economics=econ,base_kernel=k)
        self.assertTrue(paused['ever_insolvent']);self.assertEqual(paused['pending'],[])
        self.assertEqual(k.run_cash_account.__code__,original_code)
        self.assertIs(k.run_cash_account.__globals__['CapacityLedger'],original_factory)
        self.assertEqual(k.ref.NATIVE_QUERIES,0)

if __name__=='__main__':unittest.main()
