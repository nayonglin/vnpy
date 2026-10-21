import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
P=Path(__file__).with_name('stage130_contract_choice_fit.py')
s=importlib.util.spec_from_file_location('fit130',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FixedActionSemantics(unittest.TestCase):
 def test_union_division_and_date_mass(self):
  f=pd.DataFrame(dict(family_id=['x','x','x','y'],u_date=['d0','d0','d1','d1'],entry_index=[1,1,2,2],exit_index=[3,2,3,2]))
  w,g=m.training_weights(f)
  self.assertEqual(g.loc[g.u_date.eq('d0'),'union_length'].iloc[0],3)
  self.assertAlmostEqual(w.sample_weight.iloc[0],w.sample_weight.iloc[1])
  self.assertTrue(np.allclose(w.groupby(f.u_date).sample_weight.sum(),2))
  self.assertAlmostEqual(g.loc[g.u_date.eq('d0'),'uniqueness'].iloc[0],2/3)
 def test_duplicate_group_does_not_double_mass(self):
  f=pd.DataFrame(dict(family_id=['x','y'],u_date=['d','d'],entry_index=[1,1],exit_index=[3,3]))
  w,_=m.training_weights(f);ff=pd.concat([f,f.iloc[[0]]],ignore_index=True);ww,_=m.training_weights(ff)
  self.assertAlmostEqual(w.sample_weight.iloc[0]/w.sample_weight.sum(),ww.sample_weight.iloc[[0,2]].sum()/ww.sample_weight.sum())
 def fixture(self):
  p=pd.DataFrame(dict(sequence_index=[0,1],event_id=['p0','p1'],product_id=['X.A','X.A_F'],family_id=['X.A']*2,u_date=['2020-01-02']*2,u_index=[1]*2,reference_epoch=['a','af']))
  a=pd.DataFrame(dict(sequence_index=[0,1,2],action_sequence_index=[0,1,2],event_id=['aa','ab','af'],action_id=['aa','ab','af'],mother_sequence_index=[0,0,1],mother_event_id=['p0','p0','p1'],product_id=['X.A','X.A','X.A_F'],family_id=['X.A']*3,u_date=['2020-01-02']*3,u_index=[1]*3,reference_epoch=['a','b','af'],actual_epoch=['a','b','af'],anchor_epoch=['a','a','af'],u_action_eligible=[1,1,1],entry_capacity_qty=[1,2,4],label_history_ready20=[1]*3,label_state=['unknown','closed_complete_bar_model','closed_complete_bar_model'],participation_state=['unknown','participated','participated'],net_R_stress=[np.nan,2.,3.],label_known_date=['','2020-01-03','2020-01-03']))
  return p,a
 def test_B_month_choice_but_same_ordinary_priority(self):
  p,a=self.fixture();out=m.make_choices(p,a,np.array([1.,2.,99.]),'main','2020-01-01')
  A=out[out.arm.eq('A')];B=out[out.arm.eq('B')]
  self.assertEqual(A.loc[A.selected.eq(1),'chosen_epoch'].tolist(),['a'])
  self.assertEqual(B.loc[B.selected.eq(1),'chosen_epoch'].tolist(),['b'])
  self.assertEqual(len(out),4)
 def test_B_ignores_u_ineligible_top(self):
  p,a=self.fixture();a.loc[1,'u_action_eligible']=0
  out=m.make_choices(p,a,np.array([1.,9.,8.]),'main','2020-01-01')
  self.assertEqual(out.loc[out.arm.eq('B')&out.selected.eq(1),'chosen_epoch'].tolist(),['a'])
 def test_no_positive_score_keeps_parents(self):
  p,a=self.fixture();o=m.make_choices(p,a,np.array([-1.,0.,-9.]),'main','2020-01-01')
  self.assertEqual(len(o),4);self.assertEqual(int(o.selected.sum()),0)
 def test_unknown_prediction_not_filtered(self):
  p,a=self.fixture();o=m.make_choices(p,a,np.array([5.,1.,0.]),'main','2020-01-01')
  self.assertEqual(o.loc[o.selected.eq(1),'chosen_action_id'].tolist(),['aa','aa'])
 def test_unknown_differential_not_zero(self):
  p,a=self.fixture();o=m.make_choices(p,a,np.array([1.,2.,0.]),'holdout_0','2020-01-01')
  r,d,l=m.held_diagnostics(o,a);g=r['groups']['holdout_0']
  self.assertEqual(g['unknown_differential_selected_events'],1);self.assertEqual(g['status'],'unknown')
 def test_same_unknown_action_increment_zero_disclosed(self):
  p,a=self.fixture();o=m.make_choices(p,a,np.array([2.,1.,0.]),'holdout_0','2020-01-01')
  r,d,l=m.held_diagnostics(o,a);g=r['groups']['holdout_0']
  self.assertEqual(g['unknown_differential_selected_events'],0);self.assertEqual(g['common_unresolved_same_action'],1)
  self.assertEqual(g['known_u_equal_mean_increment_R'],0.)
 def test_missing_features_not_zero_raw(self):
  x=np.array([[np.nan,3.]+[0.]*24]);s={'common':{'mean':[4.]*26,'scale':[2.]*26}}
  z=m.design(x,s);self.assertEqual(z.shape,(1,52));self.assertEqual(z[0,0],0.);self.assertEqual(z[0,26],1.);self.assertEqual(z[0,1],-.5)
if __name__=='__main__':unittest.main()
