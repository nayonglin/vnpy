from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent))
try:
 import stage010_expiry_execution_overlay as s
except ModuleNotFoundError:
 s=None

class ExpiryOverlayTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(s,'expiry execution overlay not implemented')
  self.contract={'contract_epoch_id':'CFFEX.IH.201812','maturity_date':'2018-12-21'}
  self.official=dict(open=2336.2,high=2336.2,low=2275.4,close=2294.8,volume=7126.,close_oi=0.)
  self.rq={**self.official,'close_oi':3497.}
 def test_accepts_only_expiry_OI_conflict_positive_real_volume(self):
  self.assertEqual(s.qualify_pair(self.contract,'2018-12-21',self.official,self.rq),(True,'eligible_expiry_oi_timing_conflict'))
 def test_rejects_non_maturity_and_missing_maturity(self):
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-20',self.official,self.rq)[0])
  self.assertFalse(s.qualify_pair({'maturity_date':''},'2018-12-21',self.official,self.rq)[0])
 def test_rejects_any_OHLC_or_volume_disagreement(self):
  for field in ['open','high','low','close','volume']:
   with self.subTest(field=field):
    altered={**self.rq,field:self.rq[field]+1}
    self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',self.official,altered)[0])
 def test_rejects_zero_volume_and_nonzero_official_OI_and_no_conflict(self):
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',{**self.official,'volume':0},{**self.rq,'volume':0})[0])
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',{**self.official,'close_oi':1},self.rq)[0])
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',self.official,self.official)[0])
 def test_rejects_invalid_geometry_and_nonfinite_prices(self):
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',{**self.official,'low':2400},{**self.rq,'low':2400})[0])
  self.assertFalse(s.qualify_pair(self.contract,'2018-12-21',{**self.official,'close':float('nan')},self.rq)[0])

if __name__=='__main__':unittest.main()
