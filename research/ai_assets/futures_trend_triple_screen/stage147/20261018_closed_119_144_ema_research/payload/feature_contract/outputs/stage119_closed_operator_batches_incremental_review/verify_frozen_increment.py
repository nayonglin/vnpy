from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
import csv,hashlib,io,json,os,sys
B=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
OUT=B/'outputs/stage119_closed_operator_batches_incremental_review'
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
old_digests={x['request_sha256']for x in old['accepted_deliveries']}
selected={s['digest']for s in INV['scopes']}
assert len(selected)==24 and not(selected&old_digests)
selected_folders={str(OWNER.parent/('request_'+d))for d in selected}
def scope_sources(rows,reason):
 metadata_bindings(rows,reason)
 # Only the new exact request closures are freshly read; legacy market/cache sources remain inherited.
 for p,h in rows.items():
  h=h['sha256']if isinstance(h,dict)else h
  if any(p.startswith(f+'/')for f in selected_folders):read(p,h)
  elif p in old_bound:assert old_bound[p]['sha256']==h
batches=[];deliveries=[];sidecars=[];all_keys=set();runtime_roles=Counter();daily_sources=Counter()
samples={INV['scopes'][i]['digest']:reason for i,reason in [
 (2,'225-minute full; targeted independently reviewed daily'),
 (3,'single anchor; reviewed013 daily; no full-session promotion'),
 (7,'345-minute full including prior-date night session in 2020'),
 (22,'2021 boundary; 345 full with E=1 and M=344')]}
sample_inputs={}
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
 assert (bid=='batch018'and terminal['exit_code']==1 and j['status']=='blocked'and j['error']=='ValueError:request_not_current_owner_wait')or(bid!='batch018'and terminal['exit_code']==0 and j['status']=='stopped_no_current_wait')
 batches.append(dict(batch_id=bid,operator_terminal_path=frozen['path'],operator_terminal_sha256=frozen['sha256'],driver_tool_session=terminal['driver_session_id'],driver_tool_terminal_chunk=terminal['terminal_tool_chunk_id'],driver_exit_code=terminal['exit_code'],runtime_manifest=dict(path=str(mp),sha256=mh),sidecars=len(local),roles=dict(Counter(x['role']for x in local)),journal_path=str(jp),journal_sha256=terminal['journal_sha256'],status=j['status'],error=j.get('error'),provider_connections=j['provider_connections'],published_requests=[e['request_sha256']for e in j['events']]))
 for event in j['events']:
  d=event['request_sha256'];assert event['published']is True and d in selected and d not in old_digests
  folder=OWNER.parent/('request_'+d);packet=folder/'minute_packet'
  pm=js(packet/'packet_manifest.json');pf=js(packet/'preflight.json');to=js(packet/'terminal_observed.json')
  pr=js(folder/'review/parse_result.json');rp=Path(pr['receipt_path']);receipt=js(rp,pr['receipt_sha256'])
  request_path=Path(pm['request_path']);req=js(request_path,pm['request_file_sha256']);rf=js(request_path.with_name('request_fingerprint.json'));response=js(request_path.with_name('response.json'))
  assert req['request_sha256']==d==pm['request_sha256']==pf['request_sha256']==to['request_sha256']==receipt['request_sha256']
  assert rf==dict(request_path=str(request_path),request_sha256=d,request_file_sha256=pm['request_file_sha256'])
  assert response==dict(schema='stage022_delivery_pointer_v1',request_sha256=d,receipt_path=str(rp),receipt_sha256=pr['receipt_sha256'])
  assert pm['owner_sha256']==pf['owner_sha256']==to['owner_sha256']==receipt['owner_sha256']==OWNER_SHA
  assert receipt['owner_run_id']==RUN and receipt['owner_arm']=='B_OFF'and receipt['independent_review']is True and receipt['qualified_research_data']is True and receipt['p0_findings']==receipt['p1_findings']==0 and receipt['fixture_only']is False
  assert pr['status']=='accepted'and pr['actual_stage021_parser_passed']is True and pr['fixture_only']is False
  assert pf['sdk_version']=='3.10.2'and pf['soft_seconds']==570 and pf['hard_seconds']==600 and pf['provider_connections_max']==1 and pf['automatic_retry']is False and pf['auth_checks_unmodified']is True
  assert to['terminal_observed']is True and to['exit_code']==to['subprocess_returncode']==0 and to['all_inputs_unchanged']is True
  assert to['driver_pid']==driver['pid']and pidmap[to['subprocess_pid']]['role']=='run'
  parent=js(packet/'network_attempt1/parent_receipt.json',to['parent_receipt_sha256']);worker=js(packet/'network_attempt1/worker_receipt.json')
  assert parent['request_sha256']==worker['request_sha256']==d and parent['status']=='worker_terminal'and parent['exit_code']==0 and parent['hard_kill']is False and parent['all_inputs_unchanged']is True and parent['automatic_retry']is False and parent['elapsed_seconds']<600
  assert worker['accepted']is True and worker['status']=='all_target_minutes_completed'and worker['provider_connections_attempted']==1 and worker['automatic_retry']is False and worker['TqSim_created']is True
  assert to['preflight_sha256']==parent['preflight_sha256']==measured[str(packet/'preflight.json')]['sha256']
  for rel,h in parent['artifact_sha256'].items():read(packet/'network_attempt1'/rel,h)
  workers=[r for r in local if r['role']=='worker'and arg(r['argv'],'--packet-dir')==str(packet)];assert len(workers)==1 and workers[0]['ppid']==to['subprocess_pid']
  scope_sources(receipt['source_fingerprints'],'inherited_existing_exact_scope_reviewer_source_pins')
  scope_sources(pf['source_fingerprints'],'provider_preflight_source_pins')
  scope_sources(pm['input_sha256'],'packet_manifest_input_pins')
  refs=js(pm['daily_references_path'],pm['daily_references_sha256']);scope_sources(refs['source_fingerprints'],'daily_reference_existing_qualification')
  assert refs['owner_sha256']==OWNER_SHA and refs['request_sha256']==d and len(refs['contexts'])==len(req['requirements'])==1
  target=req['requirements'][0];assert refs['contexts'][0]['target']==target and pm['covers_whole_request']is True and pm['packet_count']==1 and pm['family']=='minute'
  R=set(target['required_timestamps']);E=set(target['existing_source_timestamps']);M=set(target['missing_or_unqualified_timestamps'])
  assert len(R)==len(target['required_timestamps'])and E<=R and M<=R and R-E<=M and M==R-E
  expected={(target['vt_symbol'],x)for x in R};assert not(expected&all_keys);all_keys|=expected
  a=receipt['accepted_requirements'];assert len(a)==1
  accepted=a[0];assert all(accepted[k]==target[k]for k in ['vt_symbol','execution_trade_date','requirement_kind'])and accepted['accepted_timestamps']==target['required_timestamps']and accepted['accepted']is True and accepted['completed_bars_and_daily_qualified']is True
  raw_path=packet/'network_attempt1/raw_completed_minutes.csv';proof_path=packet/'network_attempt1/completion_evidence.csv'
  raw=table(raw_path);proof=table(proof_path);data=table(receipt['data_path'],receipt['data_sha256'])
  assert len(raw)==len(data)==len(proof)==len(R)and keys(raw)==keys(data)==keys(proof)==expected
  assert all(r['completed'].lower()=='true'and r['method']=='observed_later_serial_kline'for r in proof)
  assert all(datetime.fromisoformat(r['successor_time'])>=datetime.fromisoformat(r['bar_datetime'])+timedelta(minutes=1)for r in proof)
  checks=js(folder/'review/checks.json');assert checks['commit_inheritance']is False and checks['old_value_comparison_delegated_to_actual021']is True and checks['existing_keys']==len(E)and checks['new_keys']==len(R-E)
  c=checks['targets'][0];assert len(checks['targets'])==1 and c['accepted']is True and c['status']=='accepted'and c['completion_evidence_complete']is True and c['daily_mismatch_fields']==[]and c['expected_minutes']==c['actual_rows']==len(R)
  if target['requirement_kind']=='anchor':assert c['qualification_kind']=='anchor_only_not_full_session'and len(R)==1
  else:assert c['qualification_kind']=='completed_full_session_daily7'and c['missing_minutes']==0
  assert checks['A0_disjointness']['path_equivalent']is True and checks['A0_disjointness']['intersection_count']==0
  context=refs['contexts'][0];daily_sources[context['daily_reference_source']]+=1
  if context['daily_reference_source']=='independently_reviewed_exact_request_daily':
   triplets=[x for x in refs['new_daily_rows']if x[0]['vt_symbol']==target['vt_symbol']and x[0]['trade_date']==target['execution_trade_date']]
   assert len(triplets)==1
   q,audit,detail=triplets[0];assert audit['accepted']is True and detail['actual_raw_forward_successor_checked']is True and detail['six_fields_checked']is True
   assert q['successor_datetime_ns']>q['source_datetime_ns']and detail['raw_non_target_daily_rows_qualified']is False
   assert all(float(q[k])==float(context['daily'][k])for k in context['daily'])
  row=dict(batch_id=bid,request_sha256=d,symbol=target['vt_symbol'],day=target['execution_trade_date'],kind=target['requirement_kind'],R=len(R),E=len(E),M=len(M),receipt=dict(path=str(rp),sha256=pr['receipt_sha256']),request=dict(path=str(request_path),sha256=pm['request_file_sha256']),response=dict(path=str(request_path.with_name('response.json')),sha256=measured[str(request_path.with_name('response.json'))]['sha256']),parse_result_sha256=measured[str(folder/'review/parse_result.json')]['sha256'],provider_parent_pid=to['subprocess_pid'],provider_worker_pid=workers[0]['pid'],parent_exit_code=0,parent_elapsed_seconds=parent['elapsed_seconds'],raw_sha256=measured[str(raw_path)]['sha256'],proof_sha256=measured[str(proof_path)]['sha256'],delivery_sha256=receipt['data_sha256'],source_fingerprints=len(receipt['source_fingerprints']),daily_reference_source=context['daily_reference_source'],existing_qualification_semantics_confirmed=True,original021_parse_result_confirmed=True,all_completed_keys_and_successors_confirmed=True,exact_rights_confirmed=True,source_prices_independently_recomputed=d in samples)
  deliveries.append(row)
  if d in samples:sample_inputs[d]=(req,rp,pr['receipt_sha256'],raw,context,refs,pm)
# Independently recalculate only four selected scopes; no engine, provider, deps() or market loader.
frozen_site=Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
sys.path[:0]=[str(B/'tools'),str(frozen_site)];sys.dont_write_bytecode=True;os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import pandas as pd
assert all(Path(x.__file__).resolve().is_relative_to(frozen_site)for x in (np,pd))
import stage021_blocking_data_gate as gate
assert hashlib.sha256((B/'tools/stage021_blocking_data_gate.py').read_bytes()).hexdigest()=='150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'
sample_results=[]
for d,(req,rp,h,raw,context,refs,pm)in sample_inputs.items():
 assert gate.request_sha256(req)==d
 data,full,anchor,_=gate._read_delivery(req,gate.QualifiedDelivery(rp,h))
 frame=pd.DataFrame(raw);frame['bar_datetime']=pd.to_datetime(frame.bar_datetime);ordered=data.sort_values('bar_datetime');rv=frame.sort_values('bar_datetime')[gate.FIELDS[2:]].to_numpy(dtype=float)
 assert np.array_equal(rv,ordered[gate.FIELDS[2:]].to_numpy(dtype=float))
 daily=context['daily'];target=context['target'];kind=target['requirement_kind']
 if kind=='full_session':
  aggregate=dict(open=float(ordered.open.iloc[0]),high=float(ordered.high.max()),low=float(ordered.low.min()),close=float(ordered.close.iloc[-1]),volume=float(ordered.volume.sum()),open_oi=float(ordered.open_oi.iloc[0]),close_oi=float(ordered.close_oi.iloc[-1]))
  assert len(full)==len(data)and len(anchor)==0
 else:
  aggregate=dict(open=float(ordered.open.iloc[0]),open_oi=float(ordered.open_oi.iloc[0]));assert len(full)==0 and len(anchor)==1
 assert all(np.isclose(v,daily[k],rtol=1e-12,atol=1e-8)for k,v in aggregate.items())
 reference_check='pinned_targeted_daily_qualification_metadata'
 if context['daily_reference_source']=='original_daily_csv':
  native,exchange=target['vt_symbol'].split('.');paths=[p for p in refs['source_fingerprints']if p.endswith('/'+exchange+'/'+native+'.csv')and '/tqsdk_daily_'in p];assert len(paths)==1
  rows=table(paths[0],refs['source_fingerprints'][paths[0]]);hits=[r for r in rows if r['trade_date']==target['execution_trade_date']];assert len(hits)==1
  assert all(np.isclose(float(hits[0][k]),v,rtol=1e-12,atol=1e-8)for k,v in daily.items());reference_check='one_pinned_original_daily_row'
 elif context['daily_reference_source']=='reviewed_stage013_daily':
  p=B/'outputs/stage013_missing_daily_recovery/network_attempt1/qualified_daily.csv';rows=table(p,refs['source_fingerprints'][str(p)]);hits=[r for r in rows if r['vt_symbol']==target['vt_symbol']and r['trade_date']==target['execution_trade_date']];assert len(hits)==1 and all(np.isclose(float(hits[0][k]),v,rtol=1e-12,atol=1e-8)for k,v in daily.items());reference_check='one_pinned013_qualified_daily_row'
 sample_results.append(dict(request_sha256=d,reason=samples[d],symbol=target['vt_symbol'],day=target['execution_trade_date'],rows=len(data),kind=kind,source_seven_equal_raw_delivery=True,recomputed_fields=list(aggregate),daily_values_equal=True,full_keys=len(full),explicit_anchor_only_keys=len(anchor),original021_parser_readonly_rechecked=True,daily_reference_check=reference_check))
assert len(sample_results)==4
changed=[];final_checks=[]
for frozen in F['terminals']:
 if not frozen.get('present_at_freeze'):continue
 raw=Path(frozen['path']).read_bytes();h=hashlib.sha256(raw).hexdigest();stable=h==frozen['sha256'];final_checks.append(dict(batch_id=frozen['batch_id'],path=frozen['path'],initial_sha256=frozen['sha256'],final_sha256=h,unchanged=stable))
 if not stable:changed.append(frozen['batch_id'])
accepted_batches=[r for r in batches if r['batch_id']not in changed]
accepted_deliveries=[r for r in deliveries if r['batch_id']not in changed]
assert not any(x in sys.modules for x in ['tqsdk','stage087_off_data_provider'])
report=dict(schema='stage119_frozen_increment_bounded_actual_verification_v1',reviewed_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),frozen_at=F['frozen_at'],batch_count=len(accepted_batches),batch_ids=[r['batch_id']for r in accepted_batches],changed_terminal_exclusions=changed,terminal_final_checks=final_checks,batches=accepted_batches,deliveries=accepted_deliveries,sidecars=sidecars,sidecar_count=len(sidecars),runtime_roles=dict(runtime_roles),published_deliveries=len(accepted_deliveries),provider_connections=sum(r['provider_connections']for r in accepted_batches),zero_connection_batches=[r['batch_id']for r in accepted_batches if not r['provider_connections']],driver_exit1_batches=[r['batch_id']for r in accepted_batches if r['driver_exit_code']==1],total_request_keys=sum(r['R']for r in accepted_deliveries),new_keys=sum(r['M']for r in accepted_deliveries),existing_request_keys=sum(r['E']for r in accepted_deliveries),full_keys=sum(r['R']for r in accepted_deliveries if r['kind']=='full_session'),explicit_anchor_only_keys=sum(r['R']for r in accepted_deliveries if r['kind']=='anchor'),shape_counts=dict(Counter((str(r['R'])+'_'+r['kind'])for r in accepted_deliveries)),daily_reference_sources=dict(daily_sources),independent_price_samples=sample_results,sample_rows=sum(r['rows']for r in sample_results),all_new_deliveries_link_identity_existing_qualification_once=True,no_all_delivery_price_recalculation=True,source_bindings=canonical_sources,runtime_review=old['runtime_review'],inherited_stage115_receipt=dict(path=str(old_receipt_path),sha256='649ad19bc0900e42e5855bc43757ef6091b2481c3bb62ccc4e56c457b475d5d6'),measured_bindings=measured,declared_source_bindings=declared,inherited_existing_source_bindings={p:v for p,v in inherited.items()if p not in measured},no_tests_provider_network_financial_models=True,no_B_midrun_PnL_or_financial_session_poll=True,later_batch_ids_excluded=True,no_old_batch003_delivery_recheck=True,no_full_market_hash=True)
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k not in ['batches','deliveries','sidecars','measured_bindings','declared_source_bindings','inherited_existing_source_bindings','terminal_final_checks']},ensure_ascii=False,indent=2))

