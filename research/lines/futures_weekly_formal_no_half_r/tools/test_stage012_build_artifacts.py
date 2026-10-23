"""Actual synthetic ledgers verify the all-AI-off report gate; no model data read."""
from pathlib import Path
import json,sys,tempfile,unittest
HERE=Path(__file__).resolve().parent
TOOLS=HERE if (HERE/'stage011_build_artifacts.py').is_file() and HERE.name=='tools' else Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools')
sys.path[:0]=[str(HERE),str(TOOLS)]
from test_stage011_build_artifacts import fixture
try:import stage012_build_artifacts as report
except ImportError:report=None

class Tests(unittest.TestCase):
 def api(self):self.assertIsNotNone(report,'stage012 AI-off wrapper missing')
 def setup_ledger(self,line):
  out=fixture(line)
  for arm in ['J','H']:
   p=out/(arm+'_attempt001');path=p/'actual_strategy_settings.json';value=json.loads(path.read_text())
   for flag in report.AI_FLAGS:value[0]['actual'][flag]=False;value[0]['setting'][flag]=False
   path.write_text(json.dumps(value))
   (p/'ai_selection_acceptance.json').write_text(json.dumps(dict(schema='stage012_ai_selection_off_v1',accepted=True,model_load_attempts=0,runtime_loaded=False,nonzero_ai_candidate_fields=0)))
  return out
 def test_all_false_proof_pins_json_and_wrapper_after_real_ledger_math(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=self.setup_ledger(Path(tmp));p=out/'J_attempt001'
   ledger=report.load_ledger(p,'J',report.base.ORIGINAL19,['2020-01-02','2026-10-22'])
   self.assertEqual(ledger['fifo_stats']['ledger_net_pnl'],80.)
   self.assertEqual(ledger['sources'][str((p/'ai_selection_acceptance.json').resolve())],report.base.sha(p/'ai_selection_acceptance.json'))
   self.assertEqual(ledger['sources'][str(Path(report.__file__).resolve())],report.base.sha(report.__file__))
 def test_each_pairwise_flag_true_rejects_even_if_proof_says_pass(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=self.setup_ledger(Path(tmp));p=out/'J_attempt001';path=p/'actual_strategy_settings.json';original=json.loads(path.read_text())
   for flag in report.AI_FLAGS:
    with self.subTest(flag=flag):
     value=json.loads(json.dumps(original));value[0]['actual'][flag]=True;path.write_text(json.dumps(value))
     with self.assertRaisesRegex(ValueError,'flags'):report.load_ledger(p,'J',report.base.ORIGINAL19)
 def test_missing_or_any_failed_ai_evidence_is_fail_closed(self):
  self.api()
  with tempfile.TemporaryDirectory() as tmp:
   out=self.setup_ledger(Path(tmp));p=out/'H_attempt001';path=p/'ai_selection_acceptance.json';original=json.loads(path.read_text())
   for key,bad in [('schema','stage008_ai'),('accepted',False),('model_load_attempts',1),('runtime_loaded',True),('nonzero_ai_candidate_fields',1)]:
    with self.subTest(key=key):
     value={**original,key:bad};path.write_text(json.dumps(value))
     with self.assertRaisesRegex(ValueError,'AI_selection'):report.load_ledger(p,'H',report.base.ORIGINAL19)
   path.unlink()
   with self.assertRaises(FileNotFoundError):report.load_ledger(p,'H',report.base.ORIGINAL19)
 def test_context_restores_stage011_globals_after_success_and_rejection(self):
  self.api();flags=report.base.FLAGS;loader=report.base.load_ledger
  with tempfile.TemporaryDirectory() as tmp:
   out=self.setup_ledger(Path(tmp));p=out/'J_attempt001'
   report.load_ledger(p,'J',report.base.ORIGINAL19)
   self.assertIs(report.base.FLAGS,flags);self.assertIs(report.base.load_ledger,loader)
   (p/'ai_selection_acceptance.json').write_text(json.dumps({'schema':'invalid'}))
   with self.assertRaisesRegex(ValueError,'AI_selection'):report.build_artifacts(Path(tmp))
   self.assertIs(report.base.FLAGS,flags);self.assertIs(report.base.load_ledger,loader)
 def test_wrapper_keeps_stage011_outputs_schema_and_pending_status(self):
  self.api();source_sha=report.base.sha(report.base.__file__)
  with tempfile.TemporaryDirectory() as tmp:
   line=Path(tmp);out=self.setup_ledger(line)
   result=report.build_artifacts(line)
   comparison=json.loads((line/'artifacts/stage011/comparison.json').read_text())
   self.assertEqual(comparison['schema'],'stage011_weekly_bar_open_original19_artifacts_v1')
   self.assertEqual(comparison['decision'],'PENDING_INDEPENDENT_REVIEW')
   for arm in ['J','H']:self.assertIn(str((out/(arm+'_attempt001/ai_selection_acceptance.json')).resolve()),comparison['source_files_sha256'])
   self.assertIn(str(Path(report.__file__).resolve()),comparison['source_files_sha256'])
   self.assertEqual(result['financial_replays'],0);self.assertEqual(result['minute_evidence_files_read'],0)
   with self.assertRaises(FileExistsError):report.build_artifacts(line)
  self.assertEqual(report.base.sha(report.base.__file__),source_sha)

if __name__=='__main__':unittest.main()
