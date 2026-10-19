import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
try:import stage023_quantity_price_overlay as s
except ModuleNotFoundError:s=None

class QuantityPriceTest(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(s,'quantity price overlay missing')
  self.contract={'contract_epoch_id':'SHFE.AL.202110','maturity_date':'2021-10-15'}
  q=dict(contract_epoch_id='SHFE.AL.202110',date='2021-09-24',open=23520.,high=23635.,low=22760.,close=23115.,volume=191338.,close_oi=90833.)
  self.quotes=[{**q,'source_id':'official:SHFE_futures_2021'},{**q,'source_id':'rqalpha','volume':180549.,'close_oi':87233.}]
 def test_real_equal_prices_allow_conservative_positive_volume_without_quantity_certification(self):
  okay,reason=s.qualify_quotes(self.contract,'2021-09-24',self.quotes,quantity_quarantine=True)
  self.assertTrue(okay,reason);self.assertEqual(reason,'eligible_price_consensus_quantity_conflict')
 def test_exact_epoch_date_unknown_and_post_maturity_rejected(self):
  for c,d,qq in [(None,'2021-09-24',self.quotes),(self.contract,'2021-09-24',[self.quotes[0],{**self.quotes[1],'contract_epoch_id':'SHFE.AL.203110'}]),(self.contract,'2021-09-23',self.quotes),(self.contract,'2021-10-16',[{**x,'date':'2021-10-16'} for x in self.quotes])]:
   with self.subTest(c=c,d=d):self.assertFalse(s.qualify_quotes(c,d,qq,quantity_quarantine=True)[0])
 def test_all_present_price_observations_must_agree_including_third_source(self):
  for field in ['open','high','low','close']:
   third={**self.quotes[0],'source_id':'old_tq:SHFE.al2110',field:self.quotes[0][field]+5}
   self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',self.quotes+[third],quantity_quarantine=True)[0])
 def test_quantity_only_quarantine_and_no_price_quarantine(self):
  self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',self.quotes,quantity_quarantine=False)[0])
  self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',self.quotes,quantity_quarantine=True,price_quarantine=True)[0])
 def test_each_source_volume_at_least_one_and_prices_valid(self):
  for field,val in [('volume',0),('volume',.5),('volume',float('nan')),('low',24000),('close',float('nan'))]:
   q=[self.quotes[0],{**self.quotes[1],field:val}]
   self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',q,quantity_quarantine=True)[0])
 def test_requires_unique_rq_and_at_least_official(self):
  self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',[self.quotes[0]],quantity_quarantine=True)[0])
  self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',[self.quotes[1],{**self.quotes[0],'source_id':'old_tq:x'}],quantity_quarantine=True)[0])
  self.assertFalse(s.qualify_quotes(self.contract,'2021-09-24',self.quotes+[self.quotes[1]],quantity_quarantine=True)[0])
if __name__=='__main__':unittest.main()
