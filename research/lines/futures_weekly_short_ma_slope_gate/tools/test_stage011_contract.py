import importlib.util,json,tempfile,unittest
from copy import deepcopy
from pathlib import Path


class UniformContractTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage011_contract'), 'Stage011 contract missing')
  import stage011_contract as contract
  return contract

 def fixture(self,root):
  m=self.subject();old=m.load(m.LINE/'stages/stage009_freeze.json');data=Path(old['data_directory'])
  f=dict(schema='stage011_frozen_uniform_risk_23starts_v1',source_head='a'*40,cutoff=m.CUTOFF,starts=list(m.STARTS),arms=['A','C'],data_directory=str(data),data_identity=old['data_identity'],source_files_sha256={str(p):m.sha(p) for p in m.required_financial_sources()},engine_initial_capital=150000.,reserve_initial_capital=150000.,total_initial_capital=300000.,planned_arm_windows=46,planned_financial_replays=46,baseline_arm_windows=46,max_workers=2,canary_start='2015-01-01',risk_overrides=m.NEW_RISK,baseline_freeze=str(m.LINE/'stages/stage009_freeze.json'),baseline_registry=str(m.LINE/'outputs/stage009_multistart/registry.json'),baseline_delivery_manifest=str(m.LINE/'stages/stage009_delivery_manifest.json'),baseline_reporting_manifest=str(m.LINE/'stages/stage010_delivery_manifest.json'))
  f['source_files_sha256'].update(old['source_files_sha256'])
  for prefix in m.BASELINE_IDENTITIES:f[prefix+'_sha256']=m.sha(f[prefix])
  p=root/'freeze.json';m.atomic_json(p,f);return m,p,f

 def test_fixed_scope_baseline_is_stage009_reserve_and_exact_three_deltas(self):
  with tempfile.TemporaryDirectory() as td:
   m,p,f=self.fixture(Path(td));self.assertEqual(m.validate_freeze(p)[0],f)
   for key,value in [('max_workers',3),('planned_financial_replays',42),('engine_initial_capital',300000),('risk_overrides',{}),('source_files_sha256',{}),('baseline_registry',str(m.LINE/'outputs/stage008_multistart/registry.json'))]:
    bad=deepcopy(f);bad[key]=value;m.atomic_json(p,bad)
    with self.subTest(key=key),self.assertRaises(ValueError):m.validate_freeze(p)

 def test_data_four_hashes_reject_even_when_candidate_hash_is_well_formed(self):
  with tempfile.TemporaryDirectory() as td:
   m,p,f=self.fixture(Path(td));f['data_identity']['mapping_sha256']='b'*64;m.atomic_json(p,f)
   with self.assertRaises(ValueError):m.validate_freeze(p)

 def test_checkpoint_key_changes_with_risk_or_baseline_identity(self):
  m=self.subject();f=dict(source_head='a'*40,cutoff=m.CUTOFF,risk_overrides=m.NEW_RISK,baseline_registry_sha256='a'*64,engine_initial_capital=150000,reserve_initial_capital=150000,total_initial_capital=300000)
  expected=m.checkpoint_key(f,'b'*64,'A','2015-01-01')
  for key,value in [('risk_overrides',{}),('baseline_registry_sha256','c'*64)]:self.assertNotEqual(expected,m.checkpoint_key(dict(f,**{key:value}),'b'*64,'A','2015-01-01'))

 def test_run_inputs_cannot_omit_financial_source_data_or_old_checkpoint(self):
  m=self.subject()
  self.assertTrue(hasattr(m,'validate_run_inputs'),'Stage011 input admission coverage missing')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();run=root/'run';run.mkdir();source=root/'source.py';source.write_text('fixed');old=root/'old.json';old.write_text('{}');cp=root/'checkpoint.json';cp.write_text('{}');freeze_path=root/'freeze.json';freeze_path.write_text('{}')
   f=dict(source_files_sha256={str(source):m.sha(source)},data_directory=str(root),data_identity={k:m.sha(old) for k in m.DATA_FILES})
   for name in m.DATA_FILES.values():(root/name).write_text('{}')
   for prefix in m.BASELINE_IDENTITIES:f[prefix]=str(old);f[prefix+'_sha256']=m.sha(old)
   job=dict(checkpoint=str(cp),checkpoint_sha256=m.sha(cp),files_sha256={str(old):m.sha(old)})
   pre=dict(freeze_path=str(freeze_path),freeze_sha256=m.sha(freeze_path));m.atomic_json(run/'preflight.json',pre)
   manifest={str(source):m.sha(source),str(old):m.sha(old),str(cp):m.sha(cp),str(freeze_path):m.sha(freeze_path),**{str(root/name):m.sha(root/name) for name in m.DATA_FILES.values()}}
   m.atomic_json(run/'input_manifest.json',manifest);m.validate_run_inputs(run,f,job)
   for missing in [str(source),str(root/'mapping.csv'),str(cp),str(freeze_path)]:
    bad=dict(manifest);del bad[missing];m.atomic_json(run/'input_manifest.json',bad)
    with self.subTest(missing=missing),self.assertRaises(ValueError):m.validate_run_inputs(run,f,job)

 def test_checkpoint_metadata_cannot_lie_about_frozen_source(self):
  m=self.subject()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);run=root/'run';run.mkdir();f=dict(source_head='a'*40,cutoff=m.CUTOFF);cp=root/'cp.json'
   row=dict(schema='stage011_checked_uniform_risk_run_v1',reused=False,path=str(run),checkpoint_key=m.checkpoint_key(f,'b'*64,'A','2015-01-01'),files_sha256={},freeze_sha256='b'*64,source_head='c'*40,arm='A',start='2015-01-01',end=m.CUTOFF)
   m.atomic_json(cp,row)
   with self.assertRaisesRegex(ValueError,'checkpoint_identity'):m.read_checkpoint(cp,f,'b'*64,'A','2015-01-01')

if __name__=='__main__':unittest.main()
