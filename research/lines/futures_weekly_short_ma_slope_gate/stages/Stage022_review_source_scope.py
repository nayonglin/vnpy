"""Bind lock002 and prove declared notification-only source deltas; no runtime run."""
from pathlib import Path
from copy import deepcopy
import ast,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;load=lambda p:json.loads(Path(p).read_text());BASE='30b236c973367a859ceae053ee8f1f37a36ac558';lockpath=D/'Stage022_implementation_lock_attempt002.json';lock=load(lockpath);checks=0

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ok(v,k):
 global checks;checks+=1
 if not v:raise AssertionError(k)
def rawbase(p):return subprocess.check_output(['git','show',BASE+':'+p],cwd=ROOT)
def defs(raw):
 result={}
 def walk(n,path=''):
  current=path
  if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
   current=(path+'.'if path else'')+n.name;result[current]=n
  for c in ast.iter_child_nodes(n):walk(c,current)
 walk(ast.parse(raw));return result
def eq(a,b,k):ok(ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),k)
ok(lock['base_commit']==BASE and lock['critical_file_count']==291 and lock['suite_count']==92,'expected_lock_identity')
pins=lock['critical_files_sha256'];ok(len(pins)==291,'all291critical')
for p,h in pins.items():ok(sha(ROOT/p)==h,'physical_critical_pin:'+p)
# Compare Git blob IDs for all existing critical files without materializing all baseline blobs.
proc=subprocess.run(['git','ls-tree','-rz',BASE,'--',*pins],cwd=ROOT,stdout=subprocess.PIPE,check=True);baseline={}
for row in proc.stdout.split(b'\0'):
 if row:
  header,path=row.split(b'\t',1);baseline[path.decode()]=header.decode().split()[2]
changed=[];added=[]
for p in pins:
 if p not in baseline:added.append(p);continue
 data=(ROOT/p).read_bytes();blob=hashlib.sha1(('blob '+str(len(data))+'\0').encode()+data).hexdigest()
 if blob!=baseline[p]:changed.append(p)
ok(set(changed)==set(lock['changed_existing_critical_files']),'exact8_existing_critical_deltas');ok(set(added)==set(lock['new_critical_files']),'exact3_newcritical')
frozen=[p for p in pins if '/weekly19_frozen/'in p or '/weekly19_assets/'in p];ok(not(set(changed)&set(frozen)),'all_frozen_alpha_and_assets_unchanged')
paths=['examples/portfolio_backtesting/qmt_roll_weekly19_runtime.py','examples/portfolio_backtesting/qmt_roll_weekly19_live_pipeline.py','examples/portfolio_backtesting/qmt_roll_weekly19_local_backend.py','examples/portfolio_backtesting/qmt_roll_weekly19_friday_report.py'];old={p:defs(rawbase(p))for p in paths};new={p:defs((ROOT/p).read_text())for p in paths}
rt=paths[0];pipeline=paths[1];backend=paths[2];friday=paths[3]
# Runtime existing definitions differ in exactly two methods; the new reason helper is additional.
rtchanges=[name for name in old[rt]if name in new[rt]and ast.dump(old[rt][name],include_attributes=False)!=ast.dump(new[rt][name],include_attributes=False)and isinstance(old[rt][name],(ast.FunctionDef,ast.AsyncFunctionDef))]
ok(set(rtchanges)=={'IntentEngine.send_order','Runtime._apply_single_broker_fill'},'only2_runtime_existing_method_deltas')
send=deepcopy(new[rt]['IntentEngine.send_order']);removed=[]
for node in list(send.body):
 if isinstance(node,ast.If)and any(isinstance(c,ast.Constant)and c.value=='exit_reason'for c in ast.walk(node))and any(isinstance(c,ast.Attribute)and c.attr=='_mail_close_reason'for c in ast.walk(node)):
  send.body.remove(node);removed.append(node)
ok(len(removed)==1,'single_new_close_metadata_clause');eq(send,old[rt]['IntentEngine.send_order'],'send_order_old_routing_and_sizing_AST_exact_except_added_metadata')
fill=deepcopy(new[rt]['Runtime._apply_single_broker_fill']);hits=0
for node in ast.walk(fill):
 if isinstance(node,ast.If)and ast.dump(node.test,include_attributes=False)==ast.dump(ast.parse("plan['offset'] == 'close'",mode='eval').body,include_attributes=False):
  if len(node.body)==2 and isinstance(node.body[0],ast.Assign)and isinstance(node.body[0].value,ast.Call)and isinstance(node.body[0].value.func,ast.Attribute)and node.body[0].value.func.attr=='_close_fill':
   node.body=[ast.Expr(value=node.body[0].value)];hits+=1
ok(hits==1,'only_new_actual_close_fill_evidence_clause');eq(fill,old[rt]['Runtime._apply_single_broker_fill'],'all_original_fill_semantics_ownership_duplicates_rollback_AST_exact')
for name in ['_runtime','_apply_events','_assert_completed_history_sequence','_refresh_advice','_report','run_weekly19_session_cycle']:
 eq(new[pipeline][name],old[pipeline][name],'unchanged_pipeline_helper:'+name)
for name in old[backend]:
 if name in new[backend]and isinstance(old[backend][name],(ast.FunctionDef,ast.AsyncFunctionDef))and not name.endswith('.send_mail'):
  eq(new[backend][name],old[backend][name],'unchanged_backend_method:'+name)
for name in ['FridayMailOutbox.__init__','FridayMailOutbox._directory','FridayMailOutbox._open','FridayMailOutbox._write','report_digest','_canonical','_sha','_money','_now']:
 eq(new[friday][name],old[friday][name],'inherited_outbox_IO_or_primitive_exact:'+name)
# Friday funding/account computations are unchanged; only one append's exit-reason text is new.
f=deepcopy(new[friday]['build_friday_report']);hits=0
for n in ast.walk(f):
 if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='append'and len(n.args)==1 and isinstance(n.args[0],ast.BinOp):
  arg=n.args[0]
  if isinstance(arg.right,ast.IfExp)and any(isinstance(c,ast.Name)and c.id=='format_exit_reason'for c in ast.walk(arg.right)):
   n.args[0]=arg.left;hits+=1
ok(hits==1,'one_exit_reason_text_append');eq(f,old[friday]['build_friday_report'],'all_original_friday_funding_cash_calculations_AST_exact')
# The existing m2 release remains immutable; it is not this new code's qualification.
m2=ROOT/'official_strategy_materials/official_live_weekly19_base15w_reserve15w_stage014/releases/m0002_20261101T050816+0800_e89fdcbb6826';oldproof=load(D/'Stage019_review_raw_result.json');ok(sha(m2/'manifest.json')==oldproof['m2_manifest_sha256'],'existing_m2_manifest_unchanged');m=load(m2/'manifest.json')
for r in m['files']:ok(sha(m2/r['payload_path'])==r['sha256'],'m2_payload_unchanged:'+r['logical_path'])
result=dict(schema='Stage022.independent-source-scope-lock002.v1',accepted=True,status='PASS_SOURCE_SCOPE_WITH_LIMITATIONS',failures=[],checks=checks,base_commit=BASE,lock_path=str(lockpath),lock_sha256=sha(lockpath),critical_files_sha256=pins,critical_count=291,changed_existing=sorted(changed),new_files=sorted(added),frozen_alpha_asset_pins_unchanged=len(frozen),runtime_changed_existing_methods=rtchanges,normalized_AST_proofs=['send_order original routing/sizing identical except new exit_reason metadata clause','apply_broker_fill original validation/order/quantity/PnL/duplicate/rollback identical except postvalidated evidence append','pipeline original strategy/session/funding/advice helpers unchanged','all backend methods except send_mail unchanged','Friday funding calculation AST unchanged except exit reason display text','private outbox IO/helper AST preserved'],m2_manifest_sha256=sha(m2/'manifest.json'),m2_payload_files_verified=len(m['files']),source_qualified=False,production_qualified=False,financial_replays=0,network_calls=0,note='Scope receipt only. Final acceptance additionally needs integration tests and complete offline CI002. Old execution intent_kind logic deliberately retained.')
p=D/'Stage022_review_source_scope_attempt002.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'accepted':True,'checks':checks,'critical':291,'existing_changed':len(changed),'new':len(added),'m2_payloads':len(m['files']),'receipt_sha256':sha(p)}))
