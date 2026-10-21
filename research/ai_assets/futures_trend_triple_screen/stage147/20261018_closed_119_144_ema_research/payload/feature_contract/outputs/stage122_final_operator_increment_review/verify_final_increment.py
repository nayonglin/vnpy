from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
import csv,hashlib,io,json,os,sys
B=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
OUT=B/'outputs/stage122_final_operator_increment_review'
F=json.loads((OUT/'frozen_terminal_inputs.json').read_bytes())
INV=json.loads((OUT/'bounded_inventory.json').read_bytes())
OWNER=B/'outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/owner.json'
OWNER_SHA='ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb'
RUN='81ffc8f704ce4c5eb701e97e0397b12a'
cache={};measured={};declared={};inherited={};conflicts=[]
def read(path,sha=None):
 p=Path(path);assert p.is_absolute() and p.is_file() and not any(x.is_symlink()for x in (p,*p.parents)),str(p)
 if str(p)not in cache:
  raw=p.read_bytes();assert raw==p.read_bytes(),('changed_during_read',str(p));cache[str(p)]=raw
 raw=cache[str(p)];h=hashlib.sha256(raw).hexdigest()
 if sha is not None:assert h==sha,(str(p),h,sha)
 measured[str(p)]=dict(sha256=h,bytes=len(raw))
 return raw
def js(path,sha=None):return json.loads(read(path,sha))
def declare(path,sha,reason):
 p=str(path)
 if p in declared and declared[p]['sha256']!=sha:raise AssertionError(('source_binding_conflict',p))
 declared[p]=dict(sha256=sha,qualification_provenance=reason)
def metadata_bindings(rows,reason):
 for p,v in rows.items():
  h=v['sha256']if isinstance(v,dict)else v;declare(p,h,reason)
  if p in measured:assert measured[p]['sha256']==h
  else:inherited[p]=dict(sha256=h,reason=reason)
def direct_bindings(rows):
 for p,v in rows.items():
  h=v['sha256']if isinstance(v,dict)else v;raw=read(p,h)
  if isinstance(v,dict):assert len(raw)==v['bytes']
  declare(p,h,'direct_same_bytes_SHA')
def table(path,sha=None):
 return list(csv.DictReader(io.StringIO(read(path,sha).decode('utf-8-sig'))))
def keys(rows):return {(r['vt_symbol'],r['bar_datetime'].replace(' ','T'))for r in rows}
def arg(argv,key):return argv[argv.index(key)+1]
old_receipt_path=B/'outputs/stage115_batch003_runtime_data_independent_review/review_receipt.json'
old=js(old_receipt_path,'649ad19bc0900e42e5855bc43757ef6091b2481c3bb62ccc4e56c457b475d5d6')
assert old['independent_review']and old['p0_findings']==old['p1_findings']==0
old_verification=js(old['evidence']['verification']['path'],old['evidence']['verification']['sha256'])
old_bound=old_verification['source_fingerprints']
owner=js(OWNER,OWNER_SHA);assert owner['run_id']==RUN and owner['arm']=='B_OFF'
canonical_sources=old['source_bindings'];direct_bindings(canonical_sources)
R111=js(old['runtime_review']['path'],old['runtime_review']['sha256'])
own_two={p:v for p,v in canonical_sources.items()if Path(p).name in ('stage109_provider_runtime_launcher.py','sitecustomize.py')}
assert R111['source_bindings']==own_two and R111['independent_review']is True and R111['p0_findings']==R111['p1_findings']==0
prior119=js(B/'outputs/stage119_closed_operator_batches_incremental_review/review_receipt.json','ce4dfc81d81f30e6fa5ba9d0250ed8581517aa1fc0f39c73bb8b1e842251bd6c')
assert prior119['independent_review'] is True and prior119['p0_findings']==prior119['p1_findings']==0
old_digests={x['request_sha256']for x in old['accepted_deliveries']}|{x['request_sha256']for x in prior119['accepted_deliveries']}
selected={s['digest']for s in INV['scopes']}
assert len(selected)==125 and not(selected&old_digests)
selected_folders={str(OWNER.parent/('request_'+d))for d in selected}
def scope_sources(rows,reason):
 metadata_bindings(rows,reason)
 # Only the new exact request closures are freshly read; legacy market/cache sources remain inherited.
 for p,h in rows.items():
  h=h['sha256']if isinstance(h,dict)else h
  if any(p.startswith(f+'/')for f in selected_folders):read(p,h)
  elif p in old_bound:assert old_bound[p]['sha256']==h

batches=[];deliveries=[];sidecars=[];runtime_roles=Counter()
for frozen in F['terminals']:
 if not frozen.get('present_at_freeze')or not frozen.get('stable_initial_double_read'):continue
 bid=frozen['batch_id'];terminal=js(frozen['path'],frozen['sha256'])
 assert terminal==frozen['document']and terminal['batch_id']==bid and terminal['run_id']==RUN and terminal['terminal_observed']is True
 assert terminal['financial_session_polled_by_operator']is False and terminal['new_financial_runs']==terminal['new_training_runs']==0
 mp=Path(terminal['source_runtime_sidecar']['path']);mh=terminal['source_runtime_sidecar']['sha256'];m=js(mp,mh)
 assert m['source_bindings']==canonical_sources and m['owner_path']==str(OWNER)and m['owner_sha256']==OWNER_SHA
 assert m['runtime_review']==old['runtime_review']and m['original_scope_review']==old['original_scope_review']
 assert m['probe_only']is False and m['old_financial_context_includes_this_sidecar']is False and m['automatic_retry']is False
 assert terminal['source_runtime_sidecar']['old_financial_context_includes_this_sidecar']is False
 assert arg(m['command'],'--role')=='drive'and arg(m['command'],'--batch-id')==bid and arg(m['command'],'--max-connections')=='4'and arg(m['command'],'--budget-seconds')=='3600'
 for p,v in m['owner_bindings'].items():
  assert p in old_bound and old_bound[p]==v,(bid,p)
  declare(p,v['sha256'],'inherited_Stage115_owner_context_preflight_readiness_identity')
 sdk=m['sdk_identity'];assert sdk['sdk_version']=='3.10.2'and sdk['sdk_package']==old['external_runtime_binding']['sdk_package']and sdk['sdk_dist_info']==old['external_runtime_binding']['sdk_dist_info']
 direct_bindings(sdk['sdk_accepted_source_bindings'])
 for path,binding in [(Path(sdk['sdk_package'])/'__init__.py',sdk['sdk_init_binding']),(Path(sdk['sdk_dist_info'])/'METADATA',sdk['sdk_metadata_binding'])]:
  assert len(read(path,binding['sha256']))==binding['bytes']
 local=[]
 for sp in sorted((mp.parent/'interpreters').glob('pid_*.json')):
  r=js(sp);assert r['manifest_path']==str(mp)and r['manifest_sha256']==mh and r['source_bindings']==canonical_sources
  assert r['owner_path']==str(OWNER)and r['owner_sha256']==OWNER_SHA and r['runtime_review']==m['runtime_review']and r['original_scope_review']==m['original_scope_review']
  assert r['sdk_version']=='3.10.2'and r['sdk_package']==sdk['sdk_package']and r['sdk_dist_info']==sdk['sdk_dist_info']and r['sdk_accepted_source_bindings']==sdk['sdk_accepted_source_bindings']
  assert r['sdk_init_binding']==sdk['sdk_init_binding']and r['sdk_metadata_binding']==sdk['sdk_metadata_binding']
  assert r['numeric_runtime_is_frozen']is True and r['python_executable']==m['python_executable']and set(r['numeric_modules'])=={'numpy','pandas','scipy','sklearn','joblib'}
  assert all(Path(x['file']).is_relative_to(Path(r['frozen_site']))for x in r['numeric_modules'].values())
  assert r['sdk_imported']is False and r['credentials_read']is False and r['network_calls']==0
  row=dict(batch_id=bid,path=str(sp),sha256=measured[str(sp)]['sha256'],pid=r['pid'],ppid=r['ppid'],role=arg(r['argv'],'--role'),argv=r['argv'],numeric_modules=r['numeric_modules'],sdk_version=r['sdk_version'],sdk_package=r['sdk_package'],sdk_dist_info=r['sdk_dist_info'],third_party_resolution=r['third_party_resolution'])
  local.append(row);runtime_roles[row['role']]+=1
 ds=[r for r in local if r['role']=='drive'];assert len(ds)==1
 driver=ds[0];pidmap={r['pid']:r for r in local};assert len(pidmap)==len(local)
 assert arg(driver['argv'],'--batch-id')==bid
 for r in local:
  if r['role']!='drive':assert r['ppid']in pidmap
  if r['role']=='worker':assert pidmap[r['ppid']]['role']=='run'and arg(r['argv'],'--parent-pid')==str(r['ppid'])
  elif r['role']!='drive':assert r['ppid']==driver['pid']
 sidecars+=local
 lt=js(mp.parent/'launcher_terminal.json',terminal['launcher_terminal_sha256']);assert lt==terminal['launcher_terminal']and lt['manifest_path']==str(mp)and lt['manifest_sha256']==mh and lt['exit_code']==terminal['exit_code']
 jp=OWNER.parent/'batches'/bid/'journal.json';j=js(jp,terminal['journal_sha256']);assert j==terminal['journal']and j['owner_sha256']==OWNER_SHA and j['max_provider_connections']==4
 assert 0<=j['provider_connections']<=4 and len(j['events'])==j['provider_connections']
 assert (terminal['exit_code']==1 and j['status']=='blocked'and j['error']=='ValueError:request_not_current_owner_wait')or(terminal['exit_code']==0 and j['status']in {'stopped_no_current_wait','paused_budget_or_four_connections'})
 batches.append(dict(batch_id=bid,operator_terminal_path=frozen['path'],operator_terminal_sha256=frozen['sha256'],driver_tool_session=terminal['driver_session_id'],driver_tool_terminal_chunk=terminal['terminal_tool_chunk_id'],driver_exit_code=terminal['exit_code'],runtime_manifest=dict(path=str(mp),sha256=mh),sidecars=len(local),roles=dict(Counter(x['role']for x in local)),journal_path=str(jp),journal_sha256=terminal['journal_sha256'],status=j['status'],error=j.get('error'),provider_connections=j['provider_connections'],published_requests=[e['request_sha256']for e in j['events']]))

# The frozen resolver argv list identifies local deliveries even when journal events are empty.
from decimal import Decimal
all_rows={};full_keys=set();anchor_keys=set();cross_overlap=0;requirements=[];samples={}
selection_rules=[
 ('network',lambda r:r['requirements'][0]['day'][:4]=='2021'and r['requirements'][0]['R']==225,'2021/225 network'),
 ('network',lambda r:any(a['R']==555 for a in r['requirements']),'2022/555 night session'),
 ('network',lambda r:any(a['R']==465 for a in r['requirements'])and len(r['requirements'])==1,'2023/465 session'),
 ('network',lambda r:len(r['requirements'])>1 and any(a['kind']=='full_session'for a in r['requirements']),'mixed full+anchor rights'),
 ('accepted_local',lambda r:r['digest'].startswith('49019a3e'),'new R qualification of fu2209; not old191 commit inheritance'),
 ('accepted_local',lambda r:any(a['E']==120 for a in r['requirements']),'120 existing/225 missing local'),
 ('accepted_local',lambda r:r['requirements'][0]['day'][:4]=='2024'and any(a['R']==225 and a['E']==224 for a in r['requirements']),'2024/225 existing224 local'),
 ('accepted_local',lambda r:r['requirements'][0]['day'][:4]=='2025'and any(a['E']==344 for a in r['requirements']),'2025/345 existing344 local')]
for route,predicate,reason in selection_rules:
 hits=[r for r in INV['scopes']if r['route']==route and predicate(r)];assert hits,reason;samples.setdefault(hits[0]['digest'],reason)
assert len(samples)==8
sample_inputs={}
for obs in INV['scopes']:
 d=obs['digest'];folder=OWNER.parent/('request_'+d);pr=js(folder/'review/parse_result.json');rp=Path(pr['receipt_path']);receipt=js(rp,pr['receipt_sha256'])
 qp=Path(obs['request_path']);q=js(qp,obs['file_sha256']);finger=js(qp.with_name('request_fingerprint.json'));response=js(qp.with_name('response.json'))
 assert hashlib.sha256(json.dumps({k:v for k,v in q.items()if k!='request_sha256'},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==d==q['request_sha256']==receipt['request_sha256']==pr['request_sha256']
 assert finger==dict(request_path=str(qp),request_sha256=d,request_file_sha256=obs['file_sha256'])
 assert response==dict(schema='stage022_delivery_pointer_v1',request_sha256=d,receipt_path=str(rp),receipt_sha256=pr['receipt_sha256'])
 assert receipt['owner_sha256']==OWNER_SHA and receipt['owner_run_id']==RUN and receipt['owner_arm']=='B_OFF'
 assert receipt['independent_review']is True and receipt['qualified_research_data']is True and receipt['p0_findings']==receipt['p1_findings']==0 and receipt['fixture_only']is False
 assert pr['actual_stage021_parser_passed']is True and pr['status']=='accepted'and pr['fixture_only']is False
 matching_resolves=[r for r in sidecars if r['role']=='resolve'and arg(r['argv'],'--request')==str(qp)]
 assert matching_resolves and all(arg(r['argv'],'--request-file-sha256')==obs['file_sha256']for r in matching_resolves)
 scope_sources(receipt['source_fingerprints'],'existing_independent_exact_request_qualification_source_pins')
 checks=js(folder/'review/checks.json');completion=js(folder/'review/completion_evidence.json')
 assert checks['commit_inheritance']is False and checks['old_value_comparison_delegated_to_actual021']is True
 assert checks['A0_disjointness']['path_equivalent']is True and checks['A0_disjointness']['intersection_count']==0
 wanted={(a['vt_symbol'],a['execution_trade_date'],a['requirement_kind']):a for a in q['requirements']}
 accepted={(a['vt_symbol'],a['execution_trade_date'],a['requirement_kind']):a for a in receipt['accepted_requirements']}
 targets={(a['vt_symbol'],a['execution_trade_date'],a['requirement_kind']):a for a in checks['targets']}
 assert len(wanted)==len(q['requirements'])and set(wanted)==set(accepted)==set(targets)
 expected=set();Rs=Es=Ms=0
 for identity,a in wanted.items():
  R=set(a['required_timestamps']);E=set(a['existing_source_timestamps']);M=set(a['missing_or_unqualified_timestamps']);assert len(R)==len(a['required_timestamps'])and E<=R and M==R-E
  ac=accepted[identity];ch=targets[identity]
  assert ac['accepted']is True and ac['completed_bars_and_daily_qualified']is True and ac['accepted_timestamps']==a['required_timestamps']
  assert ch['accepted']is True and ch['status']=='accepted'and ch['completion_evidence_complete']is True and ch['daily_mismatch_fields']==[]and ch['expected_minutes']==ch['actual_rows']==len(R)
  assert ch['qualification_kind']==('anchor_only_not_full_session'if identity[2]=='anchor'else'completed_full_session_daily7')
  ks={(identity[0],x)for x in R};expected|=ks;(full_keys if identity[2]=='full_session'else anchor_keys).update(ks)
  Rs+=len(R);Es+=len(E);Ms+=len(M)
  requirements.append(dict(request_sha256=d,route=obs['route'],symbol=identity[0],day=identity[1],kind=identity[2],R=len(R),E=len(E),M=len(M)))
 assert checks['existing_keys']==Es and checks['new_keys']==Ms
 data=table(receipt['data_path'],receipt['data_sha256']);assert keys(data)==expected and len(data)==len(expected)
 assert len(completion)==len(expected)and keys(completion)==expected and all(str(x['completed']).lower()=='true'for x in completion)
 for row in data:
  key=(row['vt_symbol'],row['bar_datetime'].replace(' ','T'));values=tuple(row[k]for k in ['open','high','low','close','volume','open_oi','close_oi'])
  if key in all_rows:
   cross_overlap+=1;assert tuple(Decimal(x)for x in values)==tuple(Decimal(x)for x in all_rows[key]),('cross_delivery_seven_value_conflict',key)
  else:all_rows[key]=values
 route=obs['route'];runtime_batch=obs['provider_event_batch']if route=='network'else obs['batches'][0]
 parent_pid=worker_pid=None;references=None;raw=None
 if route=='network':
  packet=folder/'minute_packet';pm=js(packet/'packet_manifest.json');pf=js(packet/'preflight.json');to=js(packet/'terminal_observed.json')
  parent=js(packet/'network_attempt1/parent_receipt.json',to['parent_receipt_sha256']);worker=js(packet/'network_attempt1/worker_receipt.json')
  assert pm['request_sha256']==pf['request_sha256']==to['request_sha256']==parent['request_sha256']==worker['request_sha256']==d
  assert pm['request_path']==str(qp)and pm['request_file_sha256']==obs['file_sha256']and pm['covers_whole_request']is True and pm['packet_count']==1 and pm['family']=='minute'
  assert pm['owner_sha256']==pf['owner_sha256']==to['owner_sha256']==parent['owner_sha256']==worker['owner_sha256']==OWNER_SHA
  assert pf['sdk_version']=='3.10.2'and pf['soft_seconds']==570 and pf['hard_seconds']==600 and pf['provider_connections_max']==1 and pf['automatic_retry']is False and pf['auth_checks_unmodified']is True
  assert to['terminal_observed']is True and to['exit_code']==to['subprocess_returncode']==0 and to['all_inputs_unchanged']is True
  assert to['driver_source_sha256']==canonical_sources[str(B/'tools/stage087_off_data_scope.py')]['sha256']and to['provider_source_sha256']==canonical_sources[str(B/'tools/stage087_off_data_provider.py')]['sha256']
  assert parent['status']=='worker_terminal'and parent['exit_code']==0 and parent['hard_kill']is False and parent['all_inputs_unchanged']is True and parent['automatic_retry']is False and parent['provider_attempts_max']==1 and parent['elapsed_seconds']<600
  assert worker['accepted']is True and worker['status']=='all_target_minutes_completed'and worker['provider_connections_attempted']==1 and worker['automatic_retry']is False and worker['TqSim_created']is True
  assert to['preflight_sha256']==parent['preflight_sha256']==measured[str(packet/'preflight.json')]['sha256']
  for rel,h in parent['artifact_sha256'].items():read(packet/'network_attempt1'/rel,h)
  scope_sources(pf['source_fingerprints'],'provider_preflight');scope_sources(pm['input_sha256'],'packet_manifest')
  references=js(pm['daily_references_path'],pm['daily_references_sha256']);scope_sources(references['source_fingerprints'],'daily_reference')
  assert references['owner_sha256']==OWNER_SHA and references['request_sha256']==d
  assert {(c['target']['vt_symbol'],c['target']['execution_trade_date'],c['target']['requirement_kind']):c['target']for c in references['contexts']}==wanted
  raw=table(packet/'network_attempt1/raw_completed_minutes.csv');proof=table(packet/'network_attempt1/completion_evidence.csv')
  assert len(raw)==len(proof)==len(expected)and keys(raw)==keys(proof)==expected
  assert all(x['completed'].lower()=='true'and x['method']=='observed_later_serial_kline'and datetime.fromisoformat(x['successor_time'])>=datetime.fromisoformat(x['bar_datetime'])+timedelta(minutes=1)for x in proof)
  parent_pid=to['subprocess_pid'];ps=[s for s in sidecars if s['batch_id']==runtime_batch and s['pid']==parent_pid];assert len(ps)==1 and ps[0]['role']=='run'and ps[0]['ppid']==to['driver_pid']
  ws=[s for s in sidecars if s['batch_id']==runtime_batch and s['role']=='worker'and arg(s['argv'],'--packet-dir')==str(packet)];assert len(ws)==1 and ws[0]['ppid']==parent_pid;worker_pid=ws[0]['pid']
 else:
  assert not(folder/'minute_packet').exists()
  # Local receipts are fresh qualification of R, not inherited financial commits.
  assert d not in [x for br in batches for x in br['published_requests']]
 deliveries.append(dict(request_sha256=d,route=route,runtime_batch=runtime_batch,observed_resolve_batches=obs['batches'],R=Rs,E=Es,M=Ms,requirements=[x for x in requirements if x['request_sha256']==d],receipt=dict(path=str(rp),sha256=pr['receipt_sha256']),response=dict(path=str(qp.with_name('response.json')),sha256=measured[str(qp.with_name('response.json'))]['sha256']),parse_result_sha256=measured[str(folder/'review/parse_result.json')]['sha256'],delivery_sha256=receipt['data_sha256'],provider_parent_pid=parent_pid,provider_worker_pid=worker_pid,parent_worker_exit_code=0 if route=='network'else'N/A_no_provider_attempt',actual021_parser_accepted=True,exact_rights=True,commit_inheritance=False,independent_price_sample=d in samples))
 if d in samples:sample_inputs[d]=(q,rp,pr['receipt_sha256'],data,raw,references,checks,receipt)
# Only eight predetermined route/shape/year scopes receive independent price recalculation.
frozen_site=Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
sys.path[:0]=[str(B/'tools'),str(frozen_site)];sys.dont_write_bytecode=True;os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import pandas as pd
import stage021_blocking_data_gate as gate
assert all(Path(x.__file__).resolve().is_relative_to(frozen_site)for x in (np,pd))
assert hashlib.sha256((B/'tools/stage021_blocking_data_gate.py').read_bytes()).hexdigest()=='150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'
sample_results=[]
for d,(q,rp,h,data,raw,refs,checks,receipt)in sample_inputs.items():
 frame,full,anchor,_=gate._read_delivery(q,gate.QualifiedDelivery(rp,h))
 if raw is not None:
  rf=pd.DataFrame(raw);rf['bar_datetime']=pd.to_datetime(rf.bar_datetime)
  assert np.array_equal(rf.sort_values(['vt_symbol','bar_datetime'])[gate.FIELDS[2:]].to_numpy(float),frame.sort_values(['vt_symbol','bar_datetime'])[gate.FIELDS[2:]].to_numpy(float))
 for target in q['requirements']:
  symbol,day,kind=(target[k]for k in ['vt_symbol','execution_trade_date','requirement_kind']);part=frame.loc[frame.vt_symbol.eq(symbol)&frame.bar_datetime.isin(pd.to_datetime(target['required_timestamps']))].sort_values('bar_datetime')
  if refs is not None:daily=next(c['daily']for c in refs['contexts']if c['target']==target)
  else:
   native,exchange=symbol.split('.');candidates=[p for p in receipt['source_fingerprints']if p.endswith('/'+exchange+'/'+native+'.csv')and'/tqsdk_daily_'in p]
   daily=None
   for path in candidates:
    hits=[r for r in table(path,receipt['source_fingerprints'][path])if r['trade_date']==day]
    if hits:assert len(hits)==1;daily={k:float(hits[0][k])for k in ['open','high','low','close','volume','open_oi','close_oi']};break
   assert daily is not None,('sample_daily_reference_not_found',symbol,day)
  if kind=='full_session':agg=dict(open=float(part.open.iloc[0]),high=float(part.high.max()),low=float(part.low.min()),close=float(part.close.iloc[-1]),volume=float(part.volume.sum()),open_oi=float(part.open_oi.iloc[0]),close_oi=float(part.close_oi.iloc[-1]))
  else:agg=dict(open=float(part.open.iloc[0]),open_oi=float(part.open_oi.iloc[0]))
  assert all(np.isclose(v,float(daily[k]),rtol=1e-12,atol=1e-8)for k,v in agg.items()),('sample_daily_mismatch',symbol,day)
 sample_results.append(dict(request_sha256=d,reason=samples[d],route=next(x['route']for x in deliveries if x['request_sha256']==d),rows=len(frame),full_keys=len(full),explicit_anchor_keys=len(anchor),actual021_parser_pass=True,all_target_aggregate_or_anchor_fields_match=True,network_raw_delivery_seven_equal=raw is not None))
# No current-wait read: final stop is checked with frozen argv/request and immutable context clock.
pending=INV['pending'];assert len(pending)==1
p=pending[0];qp=Path(p['request_path']);q=js(qp,p['file_sha256'])
assert q['request_sha256']==p['digest']and not qp.with_name('response.json').exists()
assert p['requirements']==[dict(symbol='CF505.CZCE',day='2025-04-11',kind='full_session',R=345,E=0,M=345)]
packet=OWNER.parent/('request_'+p['digest'])/'minute_packet';pm=js(packet/'packet_manifest.json');pf=js(packet/'preflight.json')
assert pm['request_sha256']==p['digest']and pf['sdk_version']=='3.10.2'and not(packet/'terminal_observed.json').exists()and not(packet/'network_attempt1').exists()
context=js(owner['run_context_path'],owner['run_context_sha256'])
last=F['terminals'][-1]['document'];remaining=7200-(datetime.fromisoformat(last['recorded_at'])-datetime.fromisoformat(context['started_at'])).total_seconds()
assert 0<remaining<840 and last['batch_id']=='batch129'and last['exit_code']==0 and last['journal']['status']=='paused_budget_or_four_connections'and last['journal']['provider_connections']==0 and last['journal']['events']==[]
final=[];changed=[]
for f in F['terminals']:
 raw=Path(f['path']).read_bytes();h=hashlib.sha256(raw).hexdigest();final.append(dict(batch_id=f['batch_id'],initial_sha256=f['sha256'],final_sha256=h,unchanged=h==f['sha256']))
 if h!=f['sha256']:changed.append(f['batch_id'])
assert not changed
assert not any(x in sys.modules for x in ['tqsdk','stage087_off_data_provider'])
report=dict(schema='stage122_final_closed_operator_increment_verification_v1',frozen_at=F['frozen_at'],checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),batches=batches,sidecars=sidecars,deliveries=deliveries,requirements=requirements,terminal_final_checks=final,changed_exclusions=changed,provider_connections=sum(x['provider_connections']for x in batches),runtime_roles=dict(runtime_roles),runtime_manifests=len(batches),sidecar_count=len(sidecars),accepted_routes=dict(Counter(x['route']for x in deliveries)),full_rights_unique_keys=len(full_keys),anchor_rights_unique_keys=len(anchor_keys),explicit_anchor_only_keys=len(anchor_keys-full_keys),all_unique_keys=len(all_rows),request_R_sum=sum(x['R']for x in deliveries),request_E_sum=sum(x['E']for x in deliveries),request_M_sum=sum(x['M']for x in deliveries),cross_delivery_overlap_count=cross_overlap,cross_delivery_values_unchanged=True,price_samples=sample_results,sample_rows=sum(x['rows']for x in sample_results),pending_excluded=dict(**p,packet_prepared_not_run=True,no_response=True,no_terminal_or_attempt=True,whole_remaining_at_batch129_terminal_recorded_at_seconds=remaining,context_started_at=context['started_at'],budget_7200_reserve_840_preserved=True),zero_connection_batches=[x['batch_id']for x in batches if x['provider_connections']==0],exit1_batches=[x['batch_id']for x in batches if x['driver_exit_code']==1],measured_bindings=measured,declared_source_bindings=declared,inherited_existing_source_bindings={p:v for p,v in inherited.items()if p not in measured},source_bindings=canonical_sources,runtime_review=old['runtime_review'],inherited_115=dict(path=str(old_receipt_path),sha256='649ad19bc0900e42e5855bc43757ef6091b2481c3bb62ccc4e56c457b475d5d6'),inherited_119=dict(path=str(B/'outputs/stage119_closed_operator_batches_incremental_review/review_receipt.json'),sha256='ce4dfc81d81f30e6fa5ba9d0250ed8581517aa1fc0f39c73bb8b1e842251bd6c'),old_data_rechecked=False,no_full_market_hash=True,no_test_provider_network_financial_model_execution=True,no_PnL_or_financial_session_poll=True)
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k not in ['batches','sidecars','deliveries','requirements','terminal_final_checks','measured_bindings','declared_source_bindings','inherited_existing_source_bindings']},ensure_ascii=False,indent=2))

