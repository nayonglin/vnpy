.py311/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
import hashlib,json,sys
line=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen');sys.path.insert(0,str(line/'tools'));sys.dont_write_bytecode=True
import stage087_off_data_scope as scope
import stage087_off_data_provider as provider
pins={'stage087_off_data_scope.py':'5919f098af14ea9819cee3445e2555f9a740ebc2c808af1afdafa508235d01fb','stage087_off_data_provider.py':'33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46'}
assert all(hashlib.sha256((line/'tools'/n).read_bytes()).hexdigest()==h for n,h in pins.items())
class Child:
 pid=99998
 def wait(self,timeout=None):return 0
 def poll(self):return 0
rows=[]
with TemporaryDirectory(prefix='exact_reserve_',dir=line/'outputs/stage094_off_data_scope_fix_independent_review')as temp:
 f=Path(temp).resolve();owner=SimpleNamespace(fixture_allowed=False,document=dict(fixture_only=False),sha256='temporary_only',path=f/'no_real_owner.json',verify=lambda:scope.Bindings());current=dict(path=f/'no_real_request.json',file_sha='temporary_only',digest='temporary_only',wait={})
 cases=[('exact_840',[840,840,0],False),('sdk_crosses_839',[900,839],True),('current_changes_after_sdk',[900,900],True)]
 for name,reserves,reject in cases:
  packet=f/name;packet.mkdir();(packet/'preflight.json').write_text('{"source_fingerprints":{}}\n');launches=[]
  def launch(*a,**k):launches.append('fake_child');return Child()
  checks=[current,ValueError('temporary_current_wait_changed')]if name=='current_changes_after_sdk'else None
  actual_kwargs=dict(side_effect=checks)if checks else dict(return_value=current)
  with patch.object(provider,'read_packet',return_value=({},current,dict(source_fingerprints={}),scope.Bindings())),patch.object(provider,'sdk_preflight',return_value={})as sdk,patch.object(scope,'read_actual_request',**actual_kwargs)as read,patch.object(scope,'remaining_engine_seconds',side_effect=reserves)as budget,patch.object(provider.subprocess,'Popen',side_effect=launch):
   try:result=provider.run_once(owner,packet);error=None
   except ValueError as exc:result=None;error=str(exc)
   assert bool(error)==reject,(name,error)
   assert len(launches)==(0 if reject else 1)
   assert (packet/'network_attempt1').exists()is(not reject)
   assert sdk.call_count==1 and read.call_count==2
   assert budget.call_count==(1 if name=='current_changes_after_sdk'else 2)
   rows.append(dict(case=name,reserves=reserves,error=error,fake_launches=len(launches),sdk_preflight_stub_calls=sdk.call_count,current_guard_calls=read.call_count,reserve_calls=budget.call_count,attempt_created=(packet/'network_attempt1').exists(),result=result))
assert all(hashlib.sha256((line/'tools'/n).read_bytes()).hexdigest()==h for n,h in pins.items())
print(json.dumps(dict(fixture_only=True,cases=rows,real_provider_starts=0,network_connections=0,financial_replays=0),ensure_ascii=False,indent=2))
PY
