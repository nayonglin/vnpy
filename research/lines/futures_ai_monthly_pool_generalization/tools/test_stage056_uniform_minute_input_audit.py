import copy,unittest
import pandas as pd
import stage056_uniform_minute_input_audit as audit


def fixtures():
 req=dict(contract_epoch_id='CZCE.CF.202005',source_trade_date='2020-01-02',product='CF',exchange='CZCE',metadata_order_book_id_hint='CF2005')
 epoch=dict(contract_epoch_id='CZCE.CF.202005',contract_yyyymm='202005',order_book_id='CF2005',product='CF',exchange='CZCE')
 meta=dict(order_book_id='CF2005',underlying_symbol='CF',exchange='CZCE',trading_code='CF005',listed_date='2019-05-15',de_listed_date='2020-05-15')
 return req,epoch,meta


class AuditIdentityTests(unittest.TestCase):
 def setUp(self):self.assertTrue(callable(getattr(audit,'make_identity_binding',None)),'missing exact minute identity API')
 def test_exact_epoch_metadata_lifetime_and_payload_key(self):
  req,epoch,meta=fixtures();r=audit.make_identity_binding(req,epoch,meta,'file-sha:component','a',['CF005.CZCE'])
  self.assertEqual(r['contract_epoch_id'],'CZCE.CF.202005');self.assertEqual(r['component'],'a');self.assertFalse(r['broker_symbol_qualified'])
  self.assertIn('exact_epoch',r['identity_basis'])
 def test_CZCE_short_code_not_enough_for_wrong_decade(self):
  req,epoch,meta=fixtures();wrong={**req,'contract_epoch_id':'CZCE.CF.201005','source_trade_date':'2010-01-02'}
  with self.assertRaises(ValueError):audit.make_identity_binding(wrong,epoch,meta,'x','a',['CF005.CZCE'])
 def test_wrong_month_metadata_or_lifetime_rejected(self):
  req,epoch,meta=fixtures()
  for ep,mt,day in [({**epoch,'contract_yyyymm':'202009'},meta,req['source_trade_date']),(epoch,{**meta,'order_book_id':'CF2015'},req['source_trade_date']),(epoch,meta,'2020-06-01')]:
   with self.subTest(ep=ep,day=day),self.assertRaises(ValueError):audit.make_identity_binding({**req,'source_trade_date':day},ep,mt,'x','a',['CF005.CZCE'])
 def test_payload_contract_mismatch_or_empty_identity_rejected(self):
  req,ep,mt=fixtures()
  for symbols,source,component in [(['CF009.CZCE'],'x','a'),([], 'x','a'),(['CF005.CZCE'],'','a'),(['CF005.CZCE'],'x','')]:
   with self.subTest(symbols=symbols),self.assertRaises(ValueError):audit.make_identity_binding(req,ep,mt,source,component,symbols)
 def test_component_envelope_retains_unexpected_lunch_row(self):
  expected=pd.to_datetime(['2020-01-02T09:00','2020-01-02T14:59'])
  frame=pd.DataFrame(dict(bar_datetime=pd.to_datetime(['2020-01-01T21:00','2020-01-02T09:00','2020-01-02T12:00','2020-01-02T14:59','2020-01-03T09:00'])))
  result=audit.session_envelope(frame,expected)
  self.assertEqual(len(result),3);self.assertIn(pd.Timestamp('2020-01-02T12:00'),set(result.bar_datetime))
 def test_missing_pilot_excludes_large_out_of_scope_source(self):
  self.assertTrue(callable(getattr(audit,'choose_missing_pilot',None)),'missing bounded pilot selector')
  frame=pd.DataFrame([dict(requirement_id='a',epoch='CZCE.CF.202005',source_trade_date='2020-01-02',qualification_level='incomplete_grid',source_path='/a/large.csv'),dict(requirement_id='a',epoch='CZCE.CF.202005',source_trade_date='2020-01-02',qualification_level='incomplete_grid',source_path='/z/small.csv')])
  result=audit.choose_missing_pilot(frame,{'/z/small.csv':['a']},{'a':{}})
  self.assertEqual(result['source_path'],'/z/small.csv')
 def test_identity_inputs_not_mutated(self):
  req,ep,mt=fixtures();before=copy.deepcopy([req,ep,mt]);audit.make_identity_binding(req,ep,mt,'x','a',['cf005.CZCE']);self.assertEqual(before,[req,ep,mt])

if __name__=='__main__':unittest.main()
