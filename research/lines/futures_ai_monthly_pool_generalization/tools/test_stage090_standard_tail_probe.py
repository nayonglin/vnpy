import unittest
import pandas as pd
from stage090_standard_tail_probe import project_tail, identity_status, load_pilots, ProbeDeadline

class TailProjection(unittest.TestCase):
 def test_deadline_is_not_swallowed_by_request_exception_handler(self):
  self.assertFalse(issubclass(ProbeDeadline,Exception))
 def test_real_frozen_pilot_plan(self):
  pilots=load_pilots()
  self.assertEqual(len(pilots),4)
  self.assertEqual([r['tq_symbol_proposed'] for r in pilots],['CZCE.CF005','DCE.jm2609','GFEX.lc2605','SHFE.au2202'])
 def test_integer_nanoseconds_and_padding_survive(self):
  ns=pd.Timestamp('2022-01-17T09:00:00.000000001+08:00').value
  raw=pd.DataFrame({'id':[-1,1,2],'datetime':[0,ns,ns], 'open':[float('nan'),2.,3.]})
  got=project_tail(raw)
  self.assertEqual(int(got.datetime.iloc[1]),ns)
  self.assertEqual(len(got),3)
  self.assertEqual(got.padding.tolist(),[True,False,False])
  self.assertEqual(got.local_datetime.iloc[1].nanosecond,1)
  self.assertEqual(got.local_datetime.iloc[1].hour,9)
  self.assertTrue(got.local_datetime.iloc[0] is pd.NaT)
 def test_sdk_float_minute_values_are_normalized_without_claiming_ns(self):
  ns=pd.Timestamp('2022-01-17T09:00:00+08:00').value
  raw=pd.DataFrame({'id':[-1.,1.],'datetime':[0.,float(ns)]})
  got=project_tail(raw)
  self.assertEqual(int(got.datetime.iloc[1]),ns)
  self.assertEqual(got.local_datetime.iloc[1].hour,9)
  self.assertEqual(raw.datetime.dtype,'float64')
  self.assertEqual(got.attrs['timestamp_precision'],'SDK float64; exact minute lattice validated; no subminute precision claimed')
 def test_float_off_grid_nonfinite_fractional_id_are_rejected(self):
  ns=float(pd.Timestamp('2022-01-17T09:00:00+08:00').value)
  for ids,values in [([1.],[ns+256]),([1.],[float('nan')]),([1.5],[ns]),([float('inf')],[ns]),([float(2**54)],[ns])]:
   with self.assertRaises(ValueError):project_tail(pd.DataFrame({'id':ids,'datetime':values}))
 def test_malformed_valid_timestamp_is_rejected(self):
  with self.assertRaises(ValueError):project_tail(pd.DataFrame({'id':[1],'datetime':[0]}))
 def test_identity_requires_full_symbol_month_expiry(self):
  req={'tq_symbol_proposed':'SHFE.au2202','metadata_contract_month':'202202','metadata_delisted_date':'2022-02-15'}
  quote={'instrument_id':'SHFE.au2202','exchange_id':'SHFE','delivery_year':2022,'delivery_month':2,'expired':True,'expire_datetime':1644894000.0}
  self.assertEqual(identity_status(req,quote),'identity_matches_metadata')
  for key,value in [('instrument_id','SHFE.au2302'),('delivery_year',2023),('expired',False),('expire_datetime',float('nan'))]:
   self.assertNotEqual(identity_status(req,{**quote,key:value}),'identity_matches_metadata')
if __name__=='__main__':unittest.main()
