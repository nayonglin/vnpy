import importlib.util
from pathlib import Path
import unittest
import pandas as pd
P=Path(__file__).with_name('stage135_month_ranking_choices.py')
spec=importlib.util.spec_from_file_location('subject135',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class Semantics(unittest.TestCase):
 def test_same_unknown_cancels(self):
  r=m.linear_expectation({'x':1},{'x':1},{'x':None})
  self.assertTrue(r['known']);self.assertEqual(r['value'],0)
 def test_unknown_not_zero(self):
  r=m.linear_expectation({'x':1},{'x':.5,'y':.5},{'x':None,'y':4})
  self.assertFalse(r['known']);self.assertIsNone(r['value']);self.assertEqual(r['unknown_positive_mass'],.5)
 def test_uniform_known(self):
  self.assertEqual(m.linear_expectation({'a':1},{'a':.5,'b':.5},{'a':3,'b':-1})['value'],2)
 def test_random_key_not_window(self):
  self.assertEqual(m.random_key(7,'DCE.M','2020-01-02','DCE.M.202005'),m.random_key(7,'DCE.M','2020-01-02','DCE.M.202005'))
  self.assertNotEqual(m.random_key(7,'DCE.M','2020-01-02','DCE.M.202005'),m.random_key(8,'DCE.M','2020-01-02','DCE.M.202005'))
 def test_volume_tie(self):
  g=pd.DataFrame([dict(action_id='b',actual_epoch='e2',u_volume=100),dict(action_id='a',actual_epoch='e1',u_volume=100)])
  self.assertEqual(m.volume_choice(g)['action_id'],'a')
 def test_materialize_keeps_population(self):
  b=pd.DataFrame([dict(event_id='a',selected=1,chosen_action_id='old',reference_epoch='anchor',scope='main',anchor_epoch='anchor'),dict(event_id='b',selected=0,chosen_action_id='',reference_epoch='other',scope='main',anchor_epoch='other')])
  o=pd.DataFrame([dict(control_id='RANDOM_POS_00',scope='main',mother_event_id='a',chosen_action_id='new',chosen_action_sequence_index=2,chosen_epoch='child',score=1)])
  z=m.materialize(b,o,'RANDOM_POS_00')
  self.assertEqual(z.event_id.tolist(),['a','b']);self.assertEqual(z.reference_epoch.tolist(),['anchor','other']);self.assertEqual(z.chosen_action_id.tolist(),['new',''])
if __name__=='__main__':unittest.main()
