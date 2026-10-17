.py311/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from types import SimpleNamespace
import hashlib,json,sys
root=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
sys.path.insert(0,str(root/'tools'))
import stage087_off_data_scope as scope
import stage087_off_data_provider as provider
pins={root/'tools/stage087_off_data_scope.py':'7c65bb01147a687529e27901d82b74ff4284a4dc1c84be2c7fe22e8f3aa5d737',root/'tools/stage087_off_data_provider.py':'d8ecebf5b27ebb4179f81f7b960165a14ddbe9ce8655837bbf58ff1ecbf4706f'}
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in pins.items())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v)+'\n')
results={}
with TemporaryDirectory(prefix='critical_probe_',dir=root/'outputs/stage090_off_data_scope_independent_review') as temp:
 f=Path(temp).resolve();tools=f/'tools';tools.mkdir();accounts=f/'accounts';out=f/'scope'
 for n in ['stage065_run_pairwise_off.py','stage087_off_data_scope.py','stage087_off_data_provider.py','stage021_blocking_data_gate.py','stage022_run_c0_qualified_wait.py','contract.md']:(tools/n).write_text('# finite owner validation probe only\n')
 runner=tools/'stage065_run_pairwise_off.py';source=tools/'stage087_off_data_scope.py';provider_path=tools/'stage087_off_data_provider.py';contract=tools/'contract.md'
 sources={str(p):scope.sha(p) for p in [source,provider_path,tools/'stage021_blocking_data_gate.py',tools/'stage022_run_c0_qualified_wait.py',contract]}
 bindings={str(p):dict(sha256=scope.sha(p),bytes=p.stat().st_size)for p in [runner,source,provider_path]}
 account=accounts/'A_OFF';now=datetime.now(timezone.utc);started=now-timedelta(hours=3)
 correct=account/'readiness_used_by_runner.json';wrong=account/'other_readiness.json'
 write(correct,dict(schema='fixture_finite_authorization',arm='A_OFF'))
 write(wrong,dict(schema='fixture_unrelated_NOT_financial_readiness',arm='B_OFF'))
 preflight=dict(source_bindings=bindings,execution_readiness=dict(path=str(correct),sha256=scope.sha(correct),document=json.loads(correct.read_bytes())))
 write(account/'preflight_used.json',preflight)
 context=dict(schema='stage065_run_context_v1',arm='A_OFF',attempt=1,run_id='strict_probe',output_directory=str(account),writer='stage065_account_checkpoint.py',source_bindings=bindings,started_at=started.isoformat(),preflight_sha256=scope.sha(account/'preflight_used.json'))
 write(account/'run_context.json',context)
 review=f/'review.json';write(review,dict(independent_review=True,p0_findings=0,p1_findings=0,source_bindings={str(p):bindings[str(p)]for p in [source,provider_path]}))
 process='Sun Oct 18 00:00:00 2026 '+str(runner)+' --run --arm A_OFF --execution-readiness '+str(correct)+' --execution-readiness-sha256 '+scope.sha(correct)
 doc=dict(schema='stage087_off_owner_v1',arm='A_OFF',attempt=1,run_id='strict_probe',account_output=str(account),wait_root=str(account/'data_wait'),runner_path=str(runner),runner_sha256=scope.sha(runner),engine_pid=98765,process_identity=process,run_started_at=now.isoformat(),source_fingerprints=sources,fixture_only=False,data_scope_review_path=str(review),data_scope_review_sha256=scope.sha(review))
 for k,p in [('run_context',account/'run_context.json'),('preflight',account/'preflight_used.json'),('execution_readiness',wrong)]:doc[k+'_path']=str(p);doc[k+'_sha256']=scope.sha(p)
 ownerpath=f/'owner.json';write(ownerpath,doc)
 with patch.multiple(scope,ACCOUNT_ROOT=accounts,TOOLS=tools,SOURCE=source,PROVIDER=provider_path,PROTOCOL=contract):
  owner=scope.load_owner(ownerpath,scope.sha(ownerpath),_observer=lambda pid:process)
  owner.verify()
  reported=scope.remaining_engine_seconds(owner,dict(wait=dict(started_at=now.isoformat())))
  actual=7200-(datetime.now(timezone.utc)-started).total_seconds()
  results['owner_binding']={'finite_fixture_only':True,'nonfixture_validation_branch':True,'wrong_readiness_accepted':doc['execution_readiness_path']!=preflight['execution_readiness']['path'],'context_started_at':context['started_at'],'owner_run_started_at':doc['run_started_at'],'context_run_seconds_remaining':actual,'reported_remaining_seconds':reported,'verify_accepted':True}
 # Direct provider role is a public production path. All child/SDK seams are replaced:
 # this proves launch admission only, and cannot open Tq/network or fake a real packet.
 packet=f/'direct_run_packet';packet.mkdir();write(packet/'preflight.json',dict(source_fingerprints={}))
 fakeowner=SimpleNamespace(fixture_allowed=False,document=dict(fixture_only=False),sha256='finite',path=f/'no_actual_owner.json')
 fakecurrent=dict(digest='finite',wait=dict(started_at=started.isoformat()))
 class Child:
  pid=99999
  def wait(self,timeout=None):return 0
  def poll(self):return 0
 calls=[]
 def launch(*args,**kwargs):calls.append('fake_child_only');return Child()
 with patch.object(provider,'read_packet',return_value=({},fakecurrent,dict(source_fingerprints={}),scope.Bindings())),patch.object(provider,'sdk_preflight',return_value={}),patch.object(provider.subprocess,'Popen',side_effect=launch),patch.object(scope,'remaining_engine_seconds',return_value=0)as budget:
  result=provider.run_once(fakeowner,packet)
 results['direct_provider_admission']={'finite_fake_child_only':True,'expired_budget_seconds':0,'remaining_engine_seconds_calls':budget.call_count,'fake_launches':len(calls),'returned_status':result['status'],'real_provider_starts':0,'network_connections':0}
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in pins.items())
print(json.dumps(results,ensure_ascii=False,indent=2))
PY
