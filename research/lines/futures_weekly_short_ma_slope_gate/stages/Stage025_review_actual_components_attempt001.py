"""Actual-source portability/Friday fault matrices; all transports are mock functions."""
from pathlib import Path
from datetime import datetime,timezone
import ast,copy,errno,hashlib,io,json,os,stat,subprocess,sys,tempfile,types,unittest
from unittest.mock import patch
R=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_local_backend as b
import qmt_roll_weekly19_friday_report as mail
REF='1a4f7d06c2f964f8bb3bab3b818ac5e05b7b5876';sha=lambda data:hashlib.sha256(data).hexdigest()
expected={'examples/portfolio_backtesting/qmt_roll_weekly19_local_backend.py','examples/portfolio_backtesting/qmt_roll_weekly19_friday_report.py','tests/test_weekly19_live_entry.py','tests/test_weekly19_friday_report.py'}
old=json.loads((D/'Stage024_implementation_lock.json').read_bytes())['source_sha256'];hashes=lambda:{p:sha((R/p).read_bytes())for p in old};before=hashes()
assert set(p for p in old if old[p]!=before[p])==expected and len(old)==298
changed=subprocess.check_output(['git','-C',str(R),'diff','--name-only',REF],text=True).splitlines();assert set(changed)==expected
# Compile the unchanged original seven backend Case methods, injecting the
# CURRENT method code object/globals (no AST proposal is used for the method).
path_probe=Path('/private/tmp/weekly19_stage024_missing_root_review001.py');path_ast=ast.parse(path_probe.read_bytes());path_class=copy.deepcopy(next(n for n in path_ast.body if isinstance(n,ast.ClassDef)and n.name=='Cases'))
actual_globals=dict(b.__dict__);actual_method=types.FunctionType(b.LocalEvidenceBackend.require_production.__code__,actual_globals)
ns=dict(Path=Path,tempfile=tempfile,unittest=unittest,b=b,patch=patch,namespace=actual_globals,candidate=actual_method)
exec(compile(ast.Module(body=[path_class],type_ignores=[]),str(path_probe),'exec'),ns);PathCases=ns['Cases']
assert actual_method.__code__ is b.LocalEvidenceBackend.require_production.__code__
# Compile the unchanged seven original lock test methods, replacing only the
# candidate class binding with the ACTUAL source class. Its exact exhaustion
# message assertion is deliberately retained and will differ from the prototype.
lock_probe=Path('/private/tmp/weekly19_stage024_friday_lock_review002.py');lock_ast=ast.parse(lock_probe.read_bytes());lock_class=copy.deepcopy(next(n for n in lock_ast.body if isinstance(n,ast.ClassDef)and n.name=='Cases'));report_node=copy.deepcopy(next(n for n in lock_ast.body if isinstance(n,ast.FunctionDef)and n.name=='report'))
ls=dict(Path=Path,tempfile=tempfile,unittest=unittest,mail=mail,patch=patch,os=os,errno=errno,CandidateOutbox=mail.FridayMailOutbox)
exec(compile(ast.Module(body=[report_node,lock_class],type_ignores=[]),str(lock_probe),'exec'),ls);LockCases=ls['Cases'];report=ls['report']
class ActualExhaustionSemantics(LockCases):
 def test_initial_exclusive_ENOENT_exact8_no_sender_preserves_outer_error(self):
  with patch.object(mail.os,'open',side_effect=self.hook('always_enoent')):
   try:self.out.deliver(report(),self.sender)
   except mail.ReportError as exc:
    self.assertEqual(str(exc),'outbox_open_failed');self.assertIsInstance(exc.__cause__,FileNotFoundError)
   else:self.fail('permanent error must block')
  self.assertEqual(self.creates,8);self.assertEqual(self.calls,[])
 def test_existing_inode_removed_each_time_exact8_no_sender(self):
  original=os.open;n=[0]
  def hook(name,flags,*args,**kwargs):
   if name=='.lock':
    if flags&os.O_CREAT:n[0]+=1;raise FileExistsError(errno.EEXIST,'synthetic existed')
    raise FileNotFoundError(errno.ENOENT,'synthetic removed')
   return original(name,flags,*args,**kwargs)
  with patch.object(mail.os,'open',side_effect=hook):
   try:self.out.deliver(report(),self.sender)
   except mail.ReportError as exc:self.assertEqual(str(exc),'outbox_open_failed');self.assertIsInstance(exc.__cause__,FileNotFoundError)
   else:self.fail('permanent removal must block')
  self.assertEqual(n[0],8);self.assertEqual(self.calls,[])
# Structural proof: actual backend module differs only in this bool; Friday
# module differs only by the initial-create FileNotFoundError handler.
backend_name='examples/portfolio_backtesting/qmt_roll_weekly19_local_backend.py';friday_name='examples/portfolio_backtesting/qmt_roll_weekly19_friday_report.py'
base_backend=ast.parse(subprocess.check_output(['git','-C',str(R),'show',REF+':'+backend_name]));new_backend=ast.parse((R/backend_name).read_bytes());n_backend=0
for node in ast.walk(base_backend):
 if isinstance(node,ast.Call)and isinstance(node.func,ast.Attribute)and isinstance(node.func.value,ast.Name)and node.func.value.id=='PRODUCTION_DEPLOY_ROOT'and node.func.attr=='resolve':
  for kw in node.keywords:
   if kw.arg=='strict':assert kw.value.value is True;kw.value.value=False;n_backend+=1
assert n_backend==1 and ast.dump(base_backend,include_attributes=False)==ast.dump(new_backend,include_attributes=False)
base_friday=ast.parse(subprocess.check_output(['git','-C',str(R),'show',REF+':'+friday_name]));new_friday=ast.parse((R/friday_name).read_bytes());n_friday=0
for node in ast.walk(base_friday):
 if isinstance(node,ast.Try)and node.handlers and isinstance(node.handlers[0].type,ast.Name)and node.handlers[0].type.id=='FileExistsError':
  node.handlers.append(ast.ExceptHandler(type=ast.Name(id='FileNotFoundError',ctx=ast.Load()),name=None,body=[ast.If(test=ast.Compare(left=ast.Name(id='attempt',ctx=ast.Load()),ops=[ast.Eq()],comparators=[ast.Constant(value=7)]),body=[ast.Raise(exc=None,cause=None)],orelse=[])]));n_friday+=1
assert n_friday==1 and ast.dump(base_friday,include_attributes=False)==ast.dump(new_friday,include_attributes=False)
runs=[]
suites=[('actual_backend_original7',unittest.defaultTestLoader.loadTestsFromTestCase(PathCases)),('actual_Friday_original7',unittest.defaultTestLoader.loadTestsFromTestCase(LockCases)),('actual_Friday_exact_safety2',unittest.TestSuite([ActualExhaustionSemantics('test_initial_exclusive_ENOENT_exact8_no_sender_preserves_outer_error'),ActualExhaustionSemantics('test_existing_inode_removed_each_time_exact8_no_sender')]))]
for label,suite in suites:
 stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);raw=stream.getvalue().encode();path=D/('Stage025_review_'+label+'_attempt001.log');assert not path.exists();path.write_bytes(raw)
 runs.append(dict(label=label,tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),successful=result.wasSuccessful(),path=str(path),sha256=sha(raw)))
after=hashes();assert before==after
assert runs[0]['successful']and runs[0]['tests']==7 and runs[1]['tests']==7 and runs[1]['failures']==1 and runs[1]['errors']==0 and runs[2]['successful']and runs[2]['tests']==2
receipt=dict(schema='stage025.independent.actual-source-matrices.v1',generated_at_utc=datetime.now(timezone.utc).isoformat(),status='ACTUAL_SAFETY_SEMANTICS_PASS_WITH_PROTOTYPE_MESSAGE_DIFFERENCE',source_reference=REF,reviewed_current_source_sha256=before,source_changed_from_R=sorted(expected),unchanged_old_critical_count=294,source_before_equals_after=True,structural_diff=dict(backend_only_expected_root_strict_flag=1,Friday_only_initial_exclusive_ENOENT_handler=1,other_module_ast_unchanged=True),runs=runs,prototype_assertion_difference=dict(original_probe_assertions_unchanged=True,one_original_matrix_failure_expected=True,prototype_expected='outbox_lock_race_exhausted',actual_preserved_last_raise='outbox_open_failed',actual_cause='FileNotFoundError ENOENT',semantic_supplement_exact_attempts=8,sender_calls=0,is_implementation_defect=False,reason='Prototype AST used continue through loop-else. Actual minimal source preserves pre-existing final-raise/OSError wrapping. Root explicitly accepted this vocabulary preservation; no implementation change was requested to satisfy the probe text.'),finding_status=dict(missing_expected_root_exception_contract='resolved_in_actual_source',Friday_initial_ENOENT_bounded_retry='resolved_in_actual_source',original_Q_R_Friday_failure_cause='UNKNOWN_not_claimed_resolved'),remaining_findings=[],production_qualified=False,full_CI_pending=True,limitations=['Only current four-file diff and actual-source matrix semantics accepted; final selected CI and source lock still required.','Original Q_R per-suite trace was deleted, so the independent ENOENT bug is not a proven explanation of that failure.','No prior m4 qualification or review is overwritten; new source requires its own material and trusted qualification.'],actions=dict(CTP_connections=0,orders=0,cancels=0,SMTP=0,financial_replays=0,core_writes=0,Git_index_or_commit_changes=0,credential_files_read=0))
out=D/'Stage025_review_actual_components_attempt001.json';assert not out.exists();out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(path=str(out),sha256=sha(out.read_bytes()),runs=runs,unchanged_critical=294,production_qualified=False)))
