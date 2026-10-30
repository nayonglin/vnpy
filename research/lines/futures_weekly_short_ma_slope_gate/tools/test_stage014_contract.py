import importlib.util,unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch

class FiveStartContractTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage014_contract'),'Stage014 local contract missing')
  import stage014_contract as m
  return m
 def test_scope_59_fresh_54_mature_5_observation_and_latest_completed_day(self):
  m=self.subject();self.assertEqual(m.MONTHS,(1,3,6,9,11));self.assertEqual(len(m.STARTS),59);self.assertEqual(m.CUTOFF,'2026-10-30');self.assertEqual((len(m.MATURE_STARTS),len(m.OBSERVATION_STARTS)),(54,5));self.assertEqual(m.STARTS[-1],'2026-09-01')
  self.assertNotIn('2026-11-01',m.STARTS);self.assertEqual(m.OBSERVATION_STARTS,('2025-11-01','2026-01-01','2026-03-01','2026-06-01','2026-09-01'))
  for start in m.STARTS:self.assertEqual(m.validate_start(start),start)
  for start in ['2015-02-01','2026-11-01','2026-11-02']:
   with self.subTest(start=start),self.assertRaises(ValueError):m.validate_start(start)
 def test_local_reserve_validator_accepts_new_march_start_without_mutating_old_contract(self):
  m=self.subject()
  from test_stage009_runner import ReserveRunnerTests
  import stage009_contract as old
  before=old.STARTS
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run,f=ReserveRunnerTests().fake_run(root)
   for p in [*run.iterdir(),root/'mapping.csv']:
    if p.is_file():p.write_text(p.read_text().replace('2015-01-05','2015-03-02').replace('2015-01-06','2015-03-03').replace('2015-01-01','2015-03-01').replace('2026-10-29','2026-10-30'))
   pre=m.load(run/'preflight.json');pre.update(arm='C',short_price_range_gate_enabled=True);m.atomic_json(run/'preflight.json',pre)
   m.atomic_json(run/'short_price_range_acceptance.json',dict(accepted=True,enabled=True,applied_block_count=0,decision_count=1))
   f['cutoff']=m.CUTOFF;r=m._validate_reserve_run(run,f,'C','2015-03-01');self.assertEqual(r['actual_start'],'2015-03-02');self.assertEqual(r['metrics']['end_equity'],285000.)
  self.assertIs(old.STARTS,before)
  with self.assertRaises(ValueError):old.validate_start('2015-03-01')
 def test_checkpoint_rejects_wrong_source_metadata_and_existing_file(self):
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run=root/'run';run.mkdir();f=dict(source_head='a'*40,cutoff=m.CUTOFF);cp=root/'cp.json';digest='b'*64
   m.atomic_json(run/'preflight.json',dict(head='a'*40,frozen_source_head='a'*40,freeze_sha256=digest));metrics=dict(end_equity=150000.);info=dict(metrics=metrics,raw_metrics=metrics)
   row=dict(schema='stage014_checked_reserve_run_v1',method='fresh_engine',reused=False,path=str(run),checkpoint_key=m.checkpoint_key(f,digest,'C','2015-03-01'),files_sha256=m.snapshot_dir(run),source_head='a'*40,freeze_sha256=digest,arm='C',start='2015-03-01',end=m.CUTOFF,**info)
   with patch.object(m,'validate_run',return_value=info):
    m.atomic_json(cp,row);self.assertEqual(m.read_checkpoint(cp,f,digest,'C','2015-03-01')['method'],'fresh_engine')
    for key,value in [('source_head','c'*40),('arm','A'),('start','2015-06-01'),('end','2026-10-29'),('method','proven_nonbinding_reuse')]:
     m.atomic_json(cp,dict(row,**{key:value}))
     with self.subTest(key=key),self.assertRaises(ValueError):m.read_checkpoint(cp,f,digest,'C','2015-03-01')
    with self.assertRaises(ValueError):m.make_checkpoint(run,cp,f,digest,'C','2015-03-01')
 def test_freeze_admits_exact_new_snapshot_and_rejects_old_scope_or_false_admission(self):
  m=self.subject();data=m.LINE/'outputs/data_stage014_20261030/data_approved'
  self.assertTrue(data.is_dir(),'Stage014 accepted data snapshot is required for freeze admission tests')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);admission=root/'admission.json';identity={key:m.sha(data/name) for key,name in m.DATA_FILES.items()};m.atomic_json(admission,dict(accepted=True,data_identity=identity))
   f=dict(schema='stage014_frozen_five_starts_R150_v1',source_head='a'*40,start_months=list(m.MONTHS),starts=list(m.STARTS),arms=['C'],cutoff=m.CUTOFF,planned_arm_windows=59,planned_financial_replays=59,planned_reused_runs=0,mature_window_count=54,observation_window_count=5,engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,max_workers=2,canary_start='2015-01-01',min_free_disk_bytes=m.MIN_FREE_DISK_BYTES,estimated_bytes_per_run=m.ESTIMATED_BYTES_PER_RUN,data_directory=str(data),data_identity=identity,data_admission=str(admission),data_admission_sha256=m.sha(admission),source_files_sha256={str(p):m.sha(p) for p in m.required_financial_sources()},baseline_freeze=str(m.LINE/'stages/stage009_freeze.json'),baseline_registry=str(m.LINE/'outputs/stage009_multistart/registry.json'),baseline_delivery_manifest=str(m.LINE/'stages/stage009_delivery_manifest.json'),baseline_reporting_manifest=str(m.LINE/'stages/stage010_delivery_manifest.json'))
   f['source_files_sha256'].update(m.load(f['baseline_freeze'])['source_files_sha256'])
   for key in m.BASELINE_IDENTITIES:f[key+'_sha256']=m.sha(f[key])
   path=root/'freeze.json';m.atomic_json(path,f);self.assertEqual(m.validate_freeze(path)[0],f)
   for key,value in [('starts',list(m.baseline.STARTS)),('cutoff','2026-10-29'),('start_months',[1,6]),('planned_financial_replays',23),('planned_reused_runs',23),('reserve_initial_capital',100000.),('data_directory',m.load(f['baseline_freeze'])['data_directory']),('source_files_sha256',{})]:
    m.atomic_json(path,dict(f,**{key:value}))
    with self.subTest(key=key),self.assertRaises(ValueError):m.validate_freeze(path)
   m.atomic_json(admission,dict(accepted=False,data_identity=identity));bad=dict(f,data_admission_sha256=m.sha(admission));m.atomic_json(path,bad)
   with self.assertRaises(ValueError):m.validate_freeze(path)
if __name__=='__main__':unittest.main()
