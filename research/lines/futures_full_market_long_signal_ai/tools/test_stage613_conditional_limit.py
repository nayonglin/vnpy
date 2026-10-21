"""Seven new611 synthetic behaviors, no historic native/source/old suite."""
import unittest,math
from decimal import Decimal
import pandas as pd
import stage613_conditional_limit_kernel as k
E='P.X.203001';Q='Q.X.203001';DATES=[f'2020-01-{n:02d}' for n in range(1,7)]
ECON={e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,round_lot=1,tick_size=.1,vendor_margin_rate=.1) for e in (E,Q)}
class Market:
 def __init__(self,O=101.,low=99.,close=101.,uclose=100.):self.O=O;self.low=low;self.close=close;self.uclose=uclose
 def bar(self,e,u):return dict(open=self.uclose if u==0 else self.O,high=max(self.close,self.O),low=self.uclose if u==0 else self.low,close=self.uclose if u==0 else self.close,volume=1000.)
 def indicator(self,e,u):return dict(N=4.,low20=90.,run_length=60)
def signal(e=E,L=100.,event='s'):
 return dict(event_id=event,mother_event_id='m'+event,product_id=e.rsplit('.',1)[0],family_id=e.rsplit('.',1)[0],reference_epoch=e,anchor_epoch=e,u_index=0,u_date=DATES[0],D_index=1,N_u=4.,low20_u=90.,u_close=L,lifecycle_index=99,entry_capacity_qty=5,u_gross_capacity_qty=10,potential=1)
def book(module,market,signals=None,econ=ECON):
 pots={0:signals or [signal(L=market.uclose)]};refs={u:{'P.X':E,'Q.X':Q} for u in range(len(DATES))}
 return module.run_cash_account(pd.DataFrame(),market,DATES,econ,'base','same',1,2,prepared=(pots,refs))
class ConditionalLimit611(unittest.TestCase):
 def test_marketable_open_preserves_original_economics_and_stop(self):
  for low in (98.,100.):
   m=Market(O=100.,low=low,uclose=120.);a=book(k.accepted,m);c=book(k,m)
   self.assertIn('limit_audit',c)
   self.assertEqual([(r['side'],r['qty'],r['fill_price'],r['fee']) for r in a['fills']],[(r['side'],r['qty'],r['fill_price'],r['fee']) for r in c['fills']])
   for aa,cc in zip(a['daily'],c['daily']):
    for f in ('equity','cash','initial_risk','buffered_margin','cumulative_fees','cumulative_slippage'):self.assertAlmostEqual(aa[f],cc[f],places=8)
 def test_waiting_touch_uses_raw_trigger_and_own_same_day_stop(self):
  b=book(k,Market(O=101.,low=98.));buy=next(r for r in b['fills'] if r['side']=='BUY')
  self.assertAlmostEqual(buy['reference_price'],99.9);self.assertLessEqual(buy['fill_price'],100.)
  self.assertAlmostEqual(b['closed_episodes'][0]['SL0'],98.9)
  self.assertEqual(b['limit_audit'][0]['limit_state'],'intraday_first_touch');self.assertEqual(b['limit_audit'][0]['D_state'],'entered')
 def test_untouched_expires_without_reusing_other_own_budget(self):
  m=Market(O=101.,low=100.);signals=[signal(),signal(Q,120.,'q')];b=book(k,m,signals)
  self.assertEqual([r['event_id'] for r in b['fills'] if r['side']=='BUY'],['q'])
  for r in b['budgets']:
   if r.get('budget_kind')=='new_entry':self.assertLessEqual(r['D_qty'],r['qty_cap'])
  self.assertEqual(b['limit_audit'][0]['limit_state'],'not_touched_expired')
 def test_inverse_quote_preserves_base_stress_affordability_no_clip(self):
  for cost,T in [('base','99.9'),('stress','99.7')]:
   r=k.resolve_limit(100.,100.,float(T),ECON[E],cost)
   self.assertTrue(r['filled']);self.assertEqual(Decimal(r['T']),Decimal(T));self.assertEqual(r['F'],float(T))
   self.assertEqual(r['Qfill'],k.adverse_quote(r['F'],'BUY',ECON[E],cost)['fill_price']);self.assertLessEqual(r['Qfill'],100.)
 def test_missing_tick_encoding_down_keeps_semantic_touch_threshold(self):
  e=dict(ECON[E],tick_size=None);r=k.resolve_limit(1.,1.1,.9999,e,'base')
  self.assertTrue(r['filled']);self.assertFalse(r['tickized']);self.assertTrue(r['adjusted'])
  self.assertLessEqual(Decimal(str(r['F'])),Decimal(r['T']));self.assertLessEqual(r['Qfill'],1.)
  r=k.resolve_limit(.4,.5,.3,ECON[E],'base');self.assertTrue(r['filled']);self.assertEqual(Decimal(r['T']),Decimal('.3'))
 def test_numeric_inverse_failure_is_unknown_not_zero_evidence(self):
  e=dict(ECON[E],tick_size=None);r=k.resolve_limit(5e-324,1e-320,5e-324,e,'base')
  self.assertEqual(r['state'],'numeric_inverse_unknown');self.assertFalse(r['filled'])
  m=Market(O=1e-320,low=5e-324,close=1e-320,uclose=5e-324);b=book(k,m,econ={E:e,Q:ECON[Q]})
  self.assertTrue(b['execution_unknown']);self.assertEqual(len(b['entry_execution_unknown']),1)
  self.assertEqual(b['limit_audit'][0]['D_state'],'numeric_inverse_unknown')
 def test_missing_D_and_no_valid_positive_trigger_remain_explicit(self):
  r=k.resolve_limit(.05,1.,.01,ECON[E],'base');self.assertFalse(r['filled']);self.assertEqual(r['state'],'nonpositive_trigger_cancel')
  m=Market();original=m.bar;m.bar=lambda e,u:None if u==1 else original(e,u)
  b=book(k,m);self.assertTrue(b['execution_unknown']);self.assertEqual(b['limit_audit'][0]['D_state'],'entry_execution_unknown')
if __name__=='__main__':unittest.main()
