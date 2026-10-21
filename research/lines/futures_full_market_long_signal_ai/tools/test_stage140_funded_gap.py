from pathlib import Path
import importlib.util,unittest
P=Path(__file__).with_name('stage140_funded_gap.py')
s=importlib.util.spec_from_file_location('subject140',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Accounting(unittest.TestCase):
 def test_open_after_partial_reduction(self):
  self.assertEqual(m.root_contribution(dict(realized_gross=80,entry_fees=10,exit_fees=5,unrealized=25),False),90)
 def test_closed_fee_once(self):
  self.assertEqual(m.root_contribution(dict(realized_gross=80,entry_fees=10,exit_fees=5,net_pnl=65),True),65)
 def test_risk_coordinate_cross_lots(self):
  z=m.decompose(200,90,100,60,True,True)
  self.assertEqual(z['risk_component'],70);self.assertEqual(z['unit_component'],40);self.assertEqual(z['participation_component'],0)
 def test_only_AI_no_fabricated_peer_y(self):
  z=m.decompose(-30,0,10,None,True,False)
  self.assertEqual(z['participation_component'],-30);self.assertIsNone(z['control_unit_return']);self.assertEqual(z['risk_component'],0)
 def test_neither_zero(self):
  z=m.decompose(0,0,None,None,False,False)
  self.assertEqual(z['delta_CNY'],0);self.assertIsNone(z['AI_unit_return'])
 def test_zero_risk_reject(self):
  with self.assertRaises(ValueError):m.decompose(3,1,0,1,True,True)
 def test_window_prestart(self):
  self.assertTrue(m.window_opportunity(10,11,20));self.assertFalse(m.window_opportunity(20,11,20));self.assertFalse(m.window_opportunity(9,11,20))
 def test_signed_amounts_survive_net_cancellation(self):
  import pandas as pd
  rows=[]
  for v in [10.,-9.]:
   rows.append(dict(control_id='RANDOM_POS_00',window='primary_2020',cost='stress',**{k:(v if k=='delta_CNY' else 0.) for k in m.MEASURES}))
  z=m.group_table(pd.DataFrame(rows),[]).iloc[0]
  self.assertEqual(z['delta_CNY'],1);self.assertEqual(z['positive_delta_CNY'],10);self.assertEqual(z['negative_delta_CNY'],-9)
 def test_integer_calendar_yyyymmdd(self):
  import numpy as np
  self.assertEqual(m.calendar_dates(np.array([20050104,20261016],dtype=np.int64)),['2005-01-04','2026-10-16'])
 def test_false_string(self):
  self.assertFalse(m.flag('False'));self.assertTrue(m.flag('True'))
if __name__=='__main__':unittest.main()
