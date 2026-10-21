"""Only new independent category-scope and strict mother-calendar boundaries."""
import importlib.util
from pathlib import Path
import unittest
import copy
from datetime import date,timedelta
P=Path(__file__).with_name('stage114_member_category_review.py')

def rows(instrument,fc=(4,6),nfc=(6,4),new=False):
 labels=('期货公司会员/境外特殊经纪参与者','非期货公司会员/境外特殊非经纪参与者') if new else ('期货公司','非期货公司')
 return [dict(INSTRUMENTID=instrument,RANK=rank,CJ2=v[0],CJ3=v[1],**{'PARTICIPANTABBR'+str(n):label for n in (1,2,3)}) for rank,label,v in [(-1,labels[0],fc),(0,labels[1],nfc)]]

class NewCategoryBoundaries(unittest.TestCase):
 def setUp(self):
  self.assertTrue(P.exists(),'independent114 implementation missing')
  spec=importlib.util.spec_from_file_location('review114',P);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
 def test_integer_roles_and_true_zero(self):
  self.assertEqual(self.m.exact_integer('3.0'),3)
  for v in ('3.5','NaN','Inf',True,-1):
   with self.assertRaises(ValueError):self.m.exact_integer(v,nonnegative=True)
  a=self.m.product_scalar(rows('cuall',(0,0),(0,0)), 'cu')
  self.assertTrue(a['observed']);self.assertEqual(a['s'],0.);self.assertEqual(a['gross'],0)
 def test_all_unique_priority_but_broken_all_has_no_fallback(self):
  a=self.m.product_scalar(rows('cuall')+rows('cu2001',(0,0),(0,0)),'cu')
  self.assertAlmostEqual(a['s'],.1);self.assertEqual(a['scopes'],['cuall'])
  self.assertFalse(self.m.product_scalar(rows('cuall')[:1]+rows('cu2001'),'cu')['observed'])
  self.assertFalse(self.m.product_scalar(rows('cuall')+rows('cuall'),'cu')['observed'])
 def test_every_raw_contract_in_inventory_required_not_just_category_rows(self):
  ordinary=dict(INSTRUMENTID='cu2002',RANK=1,PARTICIPANTABBR1='某某期货公司',PARTICIPANTABBR2='某某期货公司',PARTICIPANTABBR3='某某期货公司')
  a=self.m.product_scalar(rows('cu2001')+[ordinary],'cu');self.assertFalse(a['observed'])
  b=self.m.product_scalar(rows('cu2001')+[dict(ordinary,INSTRUMENTID='cu2001')],'cu');self.assertTrue(b['observed'])
 def test_sum_four_quantities_before_ratio_not_average_contract_ratios(self):
  a=self.m.product_scalar(rows('cu2001',(0,4),(4,0))+rows('cu2002',(9,0),(0,9)),'cu')
  self.assertTrue(a['observed']);self.assertAlmostEqual(a['s'],-5/26)
  self.assertNotAlmostEqual(a['s'],0.);self.assertEqual(set(a['versions']),{'legacy'})
  self.assertEqual(self.m.product_scalar(rows('cuall',new=True),'cu')['versions'],['expanded'])
  self.assertFalse(self.m.product_scalar(rows('cu2001')+rows('cu2002',new=True),'cu')['observed'])
 def test_exact_labels_ranks_and_per_scope_balance(self):
  self.assertFalse(self.m.product_scalar(rows('cuall')+rows('cu'),'cu')['observed'])
  r=rows('cuall');r[0]['RANK']=0
  self.assertFalse(self.m.product_scalar(r,'cu')['observed'])
  r=rows('cuall');r[1]['PARTICIPANTABBR2']='非期货公司会员'
  self.assertFalse(self.m.product_scalar(r,'cu')['observed'])
  self.assertFalse(self.m.product_scalar(rows('cu2001',(1,1),(2,1))+rows('cu2002',(1,2),(1,1)),'cu')['observed'])
 def test_cash_gate_primary_stress_strict_other_zero_legal(self):
  self.m.np=__import__('numpy')
  points={(w,c):dict(return_percentage_point_difference=1. if (w,c)==('primary_2020','stress') else 0.,drawdown_percentage_point_difference=0.,ci95_low=.001,active_total_return_pct=1.,identification='observed_cash_comparison')for w in ('primary_2020','cold_2023')for c in ('base','stress')}
  held={'groups':{g:dict(nominal_pass=True,status='supported',unknown_differential_selected_events=0)for g in ('holdout_0','holdout_1')}}
  self.assertEqual(self.m.cash_gate(points,held,False,True,True)['status'],'supported_research_model_only')
  held['groups']['holdout_0']['unknown_differential_selected_events']=1
  self.assertEqual(self.m.cash_gate(points,held,False,False,True)['status'],'unknown_differential_held_outcome')
  points[('primary_2020','stress')]['return_percentage_point_difference']=0.
  self.assertEqual(self.m.cash_gate(points,held,True,False,True)['status'],'unsupported')

 def test_previous_mother_day_not_latest_report_or_native_arithmetic(self):
  a=self.m.lag_dates(['2020-01-02','2020-01-06','2020-01-07','2020-01-06'])
  self.assertEqual(a,{'2020-01-02':None,'2020-01-06':'2020-01-02','2020-01-07':'2020-01-06'})

class SourceRecoveryAccounting(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('review114',P);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  self.dates=sorted([(date(2012,1,4)+timedelta(days=i)).strftime('%Y%m%d')for i in range(3586)]+['20231213','20231214'])
  self.reuse=self.dates[:13];self.new=[d for d in self.dates if d not in self.reuse]
  self.unknown=['20231213','20231214'];prior=[d for d in self.new if d not in self.unknown][:2893]
  self.template='https://example.invalid/pm{date}.dat'
  request=lambda d:dict(date=d,url=self.template.format(date=d),attempt=1,automatic_retry=False,redirect_following=False)
  self.original=[request(d)for d in prior+self.unknown]
  rest=[d for d in self.new if d not in prior+self.unknown]
  self.segments=[[request(d)for d in rest[:6]],[request(d)for d in rest[6:]]]
  self.records=[]
  for d in self.dates:
   if d in self.reuse:r=dict(date=d,status='reused_stage104_106',reused=True)
   elif d in self.unknown:r=dict(date=d,status='interrupted_unknown',reused=False,automatic_retry=False,request_started=request(d))
   else:r=dict(request(d),status='network_error'if d in rest[:6]else'http_200',reused=False)
   self.records.append(r)
  self.recovery=dict(schema='stage116_interrupted_source_recovery_v1',interrupted_dates=self.unknown,interrupted_request_count=2,complete_terminal_statuses=3588,prior_finished=2893,resumed_started=680,resumed_finished=680,interrupted_acquisition=True,single_uninterrupted_execution_claim=False,original_evidence_modified=False,fit=0,cash=0,sql=0)
  self.completion=dict(stage=109,date_count=3588,new_get_started=3575,new_get_finished=3573,reused_dates=13,recovery=copy.deepcopy(self.recovery),terminal_statuses_complete=True)
 def check(self):
  self.assertTrue(hasattr(self.m,'audit_request_accounting'),'114 cannot honestly audit interrupted acquisition')
  return self.m.audit_request_accounting(self.completion,self.records,self.recovery,self.original,self.segments,self.dates,self.new,self.reuse,self.template)
 def test_two_segments_have_no_retries_and_two_unknown_are_never_success(self):
  report=self.check();self.assertEqual(report['true_finished'],3573);self.assertEqual(report['interrupted_unknown'],2)
  self.assertEqual(report['resumed_segment_sizes'],[6,674]);self.assertEqual(report['status_counts']['network_error'],6)
 def test_duplicate_request_across_segments_rejected(self):
  self.segments[1][0]=copy.deepcopy(self.segments[0][0])
  with self.assertRaises(AssertionError):self.check()
 def test_forged_unknown_completion_or_dropped_identity_rejected(self):
  for change in ('fake_success','fake_finished','dropped','fake_raw'):
   oldrecords=copy.deepcopy(self.records);oldcompletion=copy.deepcopy(self.completion)
   if change=='fake_success':next(r for r in self.records if r['date']==self.unknown[0])['status']='http_200'
   if change=='fake_finished':self.completion['new_get_finished']=3575
   if change=='dropped':self.records.pop()
   if change=='fake_raw':next(r for r in self.records if r['date']==self.unknown[0])['archive_path']='forged'
   with self.assertRaises(AssertionError):self.check()
   self.records=oldrecords;self.completion=oldcompletion
 def test_not_requested_preserved_and_not_counted_as_finished(self):
  last=self.segments[-1].pop();self.records[self.dates.index(last['date'])]=dict(date=last['date'],status='not_requested',reused=False)
  self.recovery.update(resumed_started=679,resumed_finished=679);self.completion.update(new_get_started=3574,new_get_finished=3572,recovery=copy.deepcopy(self.recovery))
  report=self.check();self.assertEqual(report['not_requested'],1);self.assertEqual(report['true_finished'],3572)
 def test_receipt_counts_and_request_url_must_match(self):
  self.recovery['resumed_finished']=681
  with self.assertRaises(AssertionError):self.check()
  self.recovery['resumed_finished']=680;self.segments[0][0]['url']='https://example.invalid/changed'
  with self.assertRaises(AssertionError):self.check()
 def test_combined_request_log_keeps_exact_prior_failure_prefix(self):
  self.assertTrue(hasattr(self.m,'split_resume_request_segments'))
  first=b'{"date":"20231215"}\n';combined=first+b'{"date":"20231225"}\n'
  self.assertEqual(self.m.split_resume_request_segments(combined,first),[[{'date':'20231215'}],[{'date':'20231225'}]])
  with self.assertRaises(AssertionError):self.m.split_resume_request_segments(combined,b'{"date":"20231218"}\n')

class SummaryMetadataBoundary(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('review114',P);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
  helper=P.with_name('stage102_cash_diagnostics.py');spec=importlib.util.spec_from_file_location('diagnostics114',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);self.m._fields=m._fields
 def test_string_bool_null_and_numeric_summary_fields_remain_typed(self):
  self.assertTrue(hasattr(self.m,'check_account_summary_table'))
  row=dict(valuation='research_accrual_cash_scenario_not_broker_settlement',qualified=False,net=1.25,unavailable=None)
  self.m.check_account_summary_table(row,dict(row,nested=dict(unused=True)))
 def test_wrong_metadata_or_numeric_value_is_rejected(self):
  self.assertTrue(hasattr(self.m,'check_account_summary_table'))
  for row,expected in [(dict(valuation='broker_settlement'),dict(valuation='research_accrual_cash_scenario_not_broker_settlement')),(dict(net=1.5),dict(net=1.25))]:
   with self.assertRaises(AssertionError):self.m.check_account_summary_table(row,expected)

if __name__=='__main__':unittest.main()
