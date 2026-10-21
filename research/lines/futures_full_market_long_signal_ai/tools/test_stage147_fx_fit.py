"""New FX behavior fixtures only; no old suite, native source, or actual fit."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
P=Path(__file__).with_name('stage147_fx_fit.py')
s=importlib.util.spec_from_file_location('fx147',P)
m=importlib.util.module_from_spec(s) if P.exists() else None
if m is not None:s.loader.exec_module(m)

class FxFit(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(m,'FX bridge/selection is not implemented')
 def test_zero_column_bridge_checks_full_forward_not_only_selected(self):
  with self.assertRaisesRegex(ValueError,'zero-column'):
   m.check_zero_bridge(np.array([.1,.2,np.nan]),np.array([0,1]),np.array([1,2]))
 def test_all_q_scalers_must_pass_before_any_fit_callback(self):
  calls=[]
  cells=[{'q':np.array([1.,2.]),'weights':np.ones(2)},{'q':np.ones(2),'weights':np.ones(2)}]
  with self.assertRaisesRegex(ValueError,'variance'):
   m.preflight_scalar_cells(cells,lambda cell:calls.append(cell))
  self.assertEqual(calls,[])
 def test_54_design_keeps_original_52_and_distinct_missing_slot(self):
  raw=np.zeros((2,26));raw[0,0]=np.nan
  scaler={'common':{'mean':[0.]*26,'scale':[1.]*26},'scalar':{'mean':2.,'scale':2.}}
  x=m.design(raw,np.array([4.,np.nan]),scaler)
  self.assertEqual(x.shape,(2,54));self.assertEqual(x[0,26],1.);self.assertEqual(x[0,52],0.);self.assertEqual(x[0,53],1.)
  self.assertEqual(x[1,52],1.);self.assertEqual(x[1,53],0.)
 def fixture(self):
  mothers=pd.DataFrame({'sequence_index':[0,1,2], 'event_id':['p0','p1','p2'], 'product_id':['X.A','X.A_F','X.B'], 'family_id':['X.A','X.A','X.B'], 'u_date':['2020-01-02']*3, 'u_index':[1]*3, 'reference_epoch':['a','af','']})
  actions=pd.DataFrame({'sequence_index':[0,1,2], 'action_sequence_index':[0,1,2], 'action_id':['a','b','af'], 'mother_sequence_index':[0,0,1], 'product_id':['X.A','X.A','X.A_F'], 'family_id':['X.A']*3, 'u_date':['2020-01-02']*3, 'u_index':[1]*3, 'reference_epoch':['a','b','af'], 'anchor_epoch':['a','a','af'], 'u_action_eligible':[1,1,1]})
  return mothers,actions
 def test_fx_selects_full_domain_independent_of_old_control_and_keeps_empty_mother(self):
  mothers,actions=self.fixture();out=m.fx_choices(mothers,actions,np.array([1.,9.,99.]),'main','2020-01-01')
  self.assertEqual(out.event_id.tolist(),['p0','p1','p2']);self.assertEqual(out.arm.tolist(),['FX']*3)
  self.assertEqual(out.loc[out.selected.eq(1),'chosen_epoch'].tolist(),['b'])
  self.assertEqual(out.loc[out.event_id.eq('p2'),'selection_state'].iloc[0],'no_observed_children')
 def test_unknown_different_action_is_not_zero_and_same_unknown_is_disclosed(self):
  mothers,actions=self.fixture()
  old=m.fx_choices(mothers,actions,np.array([3.,1.,0.]),'holdout_0','2020-01-01');old['arm']='CONTROL_REUSED'
  new=m.fx_choices(mothers,actions,np.array([1.,3.,0.]),'holdout_0','2020-01-01')
  actions['label_state']=['unknown','closed_complete_bar_model','unknown'];actions['participation_state']=['unknown','participated','unknown'];actions['net_R_stress']=[np.nan,2.,np.nan];actions['label_known_date']=['','2020-01-03','']
  report,_,_=m.held_diagnostics(pd.concat([old,new],ignore_index=True),actions)
  self.assertEqual(report['groups']['holdout_0']['unknown_differential_selected_events'],1)
  same=new.copy();same['arm']='CONTROL_REUSED'
  actions.loc[1,['label_state','net_R_stress','label_known_date']]=['unknown',np.nan,'']
  report,_,_=m.held_diagnostics(pd.concat([same,new],ignore_index=True),actions)
  self.assertEqual(report['groups']['holdout_0']['common_unresolved_same_action'],1)
  self.assertEqual(report['groups']['holdout_0']['known_u_equal_mean_increment_R'],0.)
if __name__=='__main__':unittest.main()
