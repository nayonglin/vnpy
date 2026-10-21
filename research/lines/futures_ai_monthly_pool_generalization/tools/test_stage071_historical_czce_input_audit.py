import unittest
import pandas as pd
from stage071_historical_czce_input_audit import declared_grid,outside_grid_diagnostic,policy_tier

def rule(night=None):
 return dict(contract_epoch_id='CZCE.CF.201509',source_trade_date='2015-06-09',previous_source_trade_date='2015-06-08',day_segments_json='[["09:00","10:15"],["10:30","11:30"],["13:30","15:00"]]',night_interval_json='null' if night is None else __import__('json').dumps(['2015-06-08T21:00:00','2015-06-08T'+night+':00']),expected_reference_minutes=225+(0 if night is None else 150 if night=='23:30' else 120),explicit_gaps_json='[]')
class HistoricalAuditTests(unittest.TestCase):
 def test_day225_does_not_declare_night(self):
  r=rule();g=declared_grid(r);self.assertEqual(len(g),225);self.assertEqual(g[0],pd.Timestamp('2015-06-09 09:00'));self.assertEqual(g[-1],pd.Timestamp('2015-06-09 14:59'))
 def test_night150_is_not_current120(self):
  r=rule('23:30');g=declared_grid(r);self.assertEqual(len(g),375);self.assertIn(pd.Timestamp('2015-06-08 23:29'),g);self.assertNotIn(pd.Timestamp('2015-06-08 23:30'),g)
 def test_night120_fixed_new_schedule(self):self.assertEqual(len(declared_grid(rule('23:00'))),345)
 def test_day_clip_cannot_hide_undeclared_prior_night(self):
  r=rule();g=declared_grid(r);d=outside_grid_diagnostic(pd.DataFrame({'bar_datetime':list(g)+[pd.Timestamp('2015-06-08 21:00')]}),r,g)
  self.assertEqual(d['unexpected_overnight_rows'],1);self.assertTrue(d['reject_extra_session_rows'])
 def test_both_endpoints_are_visible(self):
  r=rule('23:30');g=declared_grid(r);d=outside_grid_diagnostic(pd.DataFrame({'bar_datetime':list(g)+[pd.Timestamp('2015-06-08 23:30'),pd.Timestamp('2015-06-09 15:00')]}),r,g)
  self.assertEqual(d['unexpected_overnight_rows'],1);self.assertEqual(d['unexpected_day_rows'],1)
 def test_other_day_rows_are_not_current_session_evidence(self):
  r=rule();g=declared_grid(r);d=outside_grid_diagnostic(pd.DataFrame({'bar_datetime':list(g)+[pd.Timestamp('2015-06-08 14:59'),pd.Timestamp('2015-06-09 21:00')]}),r,g);self.assertFalse(d['reject_extra_session_rows'])
 def test_lunch_break_is_not_a_valid_minute(self):
  r=rule();g=declared_grid(r);d=outside_grid_diagnostic(pd.DataFrame({'bar_datetime':list(g)+[pd.Timestamp('2015-06-09 10:15')]}),r,g);self.assertEqual(d['unexpected_day_rows'],1)
 def test_retrospective_and_early_gap_are_separate_sensitivity_tier(self):
  for gap in ['early_day_break225_is_explicit_reference_assumption_not_contemporaneous_primary_verified','SM_2018_2019_contemporaneous_contract_or_no_night_notice_not_retrieved']:
   r=rule();r['explicit_gaps_json']=__import__('json').dumps([gap]);self.assertEqual(policy_tier(r),'sensitivity_only_additional_primary_gap')
  self.assertEqual(policy_tier(rule()),'document_supported_reference_only')
 def test_extra_night_provider_does_not_poison_or_rescue_other_provider(self):
  from unittest.mock import patch
  import stage071_historical_czce_input_audit as m
  r=rule();r['evidence_ids']='C01';g=declared_grid(r);rid='rid';frame=pd.DataFrame({'bar_datetime':list(g)+list(g)+[pd.Timestamp('2015-06-08 21:00')],'minute_source':['a']*len(g)+['b']*(len(g)+1),'vt_symbol':['CF509.CZCE']*(2*len(g)+1)})
  audits=[dict(requirement_id=rid,component=x,source_id=x,status='conditional_reference_input_qualified') for x in ('a','b')]
  passed=[dict(requirement_id=rid,binding=dict(source_id=x),minute_path=[]) for x in ('a','b')]
  with patch.dict(m._RULES,{rid:r}),patch.dict(m._CARDS,{'C01':{}}),patch.dict(m.uniform._REQUESTS,{rid:{'metadata_order_book_id_hint':'META'}}),patch.dict(m.uniform._META,{'META':{'trading_code':'CF509','exchange':'CZCE'}}),patch.dict(m.uniform._GRIDS,{rid:g}),patch.object(m.uniform,'_audit_frame',return_value=(audits,passed)):
   a,p=m.audit_frame(frame,{},[rid]);self.assertEqual([x['binding']['source_id'] for x in p],['a']);self.assertEqual(a[1]['status'],'undeclared_overnight_rows');self.assertEqual(a[1]['baseline055_status'],'conditional_reference_input_qualified')
 def test_wrong_declared_minute_count_fails(self):
  r=rule('23:30');r['expected_reference_minutes']=345
  with self.assertRaisesRegex(ValueError,'minutes'):declared_grid(r)
