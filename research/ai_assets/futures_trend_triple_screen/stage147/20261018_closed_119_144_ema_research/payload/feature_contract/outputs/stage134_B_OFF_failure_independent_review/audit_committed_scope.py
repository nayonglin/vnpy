from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
import hashlib,json,sys
B=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen');O=B/'outputs/stage134_B_OFF_failure_independent_review'
s=json.loads((O/'audit_only_snapshot.json').read_bytes());owner=s['input_fingerprints'];bindings={}
def read(p,h=None):
 p=Path(p);assert p.is_absolute()and p.is_file()and not any(x.is_symlink()for x in (p,*p.parents));raw=p.read_bytes();assert raw==p.read_bytes();actual=hashlib.sha256(raw).hexdigest()
 if h:assert actual==h,(str(p),actual,h)
 bindings[str(p)]=dict(sha256=actual,bytes=len(raw));return raw
def js(p,h=None):return json.loads(read(p,h))
def owned(p,h):
 assert owner[str(p)]['sha256']==h,('not_owned_input',str(p))
 return js(p,h)
prior={};prior_bind={}
for name,h in [('stage115_batch003_runtime_data_independent_review','649ad19bc0900e42e5855bc43757ef6091b2481c3bb62ccc4e56c457b475d5d6'),('stage119_closed_operator_batches_incremental_review','ce4dfc81d81f30e6fa5ba9d0250ed8581517aa1fc0f39c73bb8b1e842251bd6c'),('stage122_final_operator_increment_review','950762ec4d89453f976317ef8d368d2aa0c9626296bf1a31f0e285540280cd17')]:
 p=B/'outputs'/name/'review_receipt.json';r=js(p,h);assert r['independent_review']is True and r['p0_findings']==r['p1_findings']==0;prior_bind[name]=dict(path=str(p),sha256=h)
 for x in r.get('accepted_deliveries',r.get('accepted_scope_list',[])):
  assert x['request_sha256']not in prior
  prior[x['request_sha256']]=dict(receipt_path=x.get('receipt_path',x.get('receipt',{}).get('path')),receipt_sha256=x.get('receipt_sha256',x.get('receipt',{}).get('sha256')),data_sha256=x.get('delivery_sha256'),review=name)
assert len(prior)==151
pointers={x['request_sha256']:x for x in s['resolver_audit']if x['status']=='qualified_delivery_pointer_accepted'}
assert len(pointers)==159 and sum(x['status']=='qualified_delivery_pointer_accepted'for x in s['resolver_audit'])==159
commits=[(i,x)for i,x in enumerate(s['wait_audit'])if x['event']=='data_qualified_appended']
failed={x['request_sha256']for x in s['wait_audit']if x['event']=='data_gate_failed'}
assert len(commits)==len({x['request_sha256']for _,x in commits})==159 and set(pointers)=={x['request_sha256']for _,x in commits}
assert len(failed)==1 and not(failed&set(pointers))
rows=[];extra=[];full=set();anchors=set();union=set();totalM=0
for index,event in commits:
 d=event['request_sha256'];p=pointers[d];assert event['old_keys_changed']==0 and not isinstance(event['old_keys_changed'],bool)
 for key in ['receipt_path','receipt_sha256','data_path','data_sha256']:assert event[key]==p[key]
 q=owned(p['request_path'],p['request_file_sha256']);response=owned(p['response_path'],p['response_sha256']);receipt=owned(p['receipt_path'],p['receipt_sha256'])
 assert Path(p['request_path']).parent==Path(s['owner']['output_directory'])/'data_wait'/('request_'+d)
 assert hashlib.sha256(json.dumps({k:v for k,v in q.items()if k!='request_sha256'},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==d==q['request_sha256']==receipt['request_sha256']
 assert response==dict(schema='stage022_delivery_pointer_v1',request_sha256=d,receipt_path=p['receipt_path'],receipt_sha256=p['receipt_sha256'])
 assert receipt['data_path']==p['data_path']and receipt['data_sha256']==p['data_sha256']and owner[p['data_path']]['sha256']==p['data_sha256']
 assert receipt['schema']=='stage021_independent_minute_delivery_v1'and receipt['owner_sha256']==s['upstream_bindings']['owner']['sha256']
 assert receipt['independent_review']is True and receipt['qualified_research_data']is True and receipt['p0_findings']==receipt['p1_findings']==0 and receipt['fixture_only']is False
 assert receipt['owner_run_id']==s['owner']['run_id']and receipt['owner_arm']=='B_OFF'
 assert receipt['source_fingerprints']==p['source_fingerprints']
 assert all(path in owner and owner[path]['sha256']==h for path,h in receipt['source_fingerprints'].items())
 wanted={(x['vt_symbol'],x['execution_trade_date'],x['requirement_kind']):x for x in q['requirements']};accepted={(x['vt_symbol'],x['execution_trade_date'],x['requirement_kind']):x for x in receipt['accepted_requirements']}
 assert len(wanted)==len(q['requirements'])and set(wanted)==set(accepted)
 reqs=[];ks=set();Rcount=Ecount=Mcount=0
 for ident,x in wanted.items():
  a=accepted[ident];assert a['accepted']is True and a['completed_bars_and_daily_qualified']is True and a['accepted_timestamps']==x['required_timestamps']
  R=set(x['required_timestamps']);E=set(x['existing_source_timestamps']);M=set(x['missing_or_unqualified_timestamps']);assert E<=R and M==R-E
  keys={(ident[0],t)for t in R};ks|=keys;union|=keys;(full if ident[2]=='full_session'else anchors).update(keys)
  Rcount+=len(R);Ecount+=len(E);Mcount+=len(M);reqs.append(dict(symbol=ident[0],day=ident[1],kind=ident[2],R=len(R),E=len(E),M=len(M),required_timestamps=x['required_timestamps']))
 assert event['accepted_keys']==len(ks)and event['appended_keys']==Mcount
 totalM+=Mcount
 row=dict(gate_index=index,request_sha256=d,request_path=p['request_path'],request_file_sha256=p['request_file_sha256'],response_path=p['response_path'],response_sha256=p['response_sha256'],receipt_path=p['receipt_path'],receipt_sha256=p['receipt_sha256'],data_path=p['data_path'],data_sha256=p['data_sha256'],accepted_keys=len(ks),appended_keys=event['appended_keys'],old_keys_changed=0,R=Rcount,E=Ecount,M=Mcount,requirements=reqs,qualification_basis='prior_independent_review_plus_actual_commit'if d in prior else'existing_021_receipt_and_actual_strict_gate_commit')
 if d in prior:
  a=prior[d];assert a['receipt_path']==p['receipt_path']and a['receipt_sha256']==p['receipt_sha256']and a['data_sha256']==p['data_sha256'];row['inherited_review']=a['review']
 else:
  folder=Path(p['receipt_path']).parent;checks=owned(folder/'checks.json',receipt['source_fingerprints'][str(folder/'checks.json')]);proof=owned(folder/'completion_evidence.json',receipt['source_fingerprints'][str(folder/'completion_evidence.json')])
  assert checks['commit_inheritance']is False and checks['old_value_comparison_delegated_to_actual021']is True and checks['existing_keys']==Ecount and checks['new_keys']==Mcount
  assert checks['A0_disjointness']['intersection_count']==0 and checks['A0_disjointness']['path_equivalent']is True
  assert all(c['accepted']is True and c['completion_evidence_complete']is True and c['daily_mismatch_fields']==[]for c in checks['targets'])
  assert len(proof)==len(ks)and all(str(x['completed']).lower()=='true'for x in proof)
  parse=js(folder/'parse_result.json');assert parse['actual_stage021_parser_passed']is True and parse['status']=='accepted'and parse['receipt_sha256']==p['receipt_sha256']
  read(p['data_path'],p['data_sha256']);extra.append(row)
 rows.append(row)
assert len(extra)==8 and set(prior)<=set(pointers)
# Eight previously uncovered entries use their existing parser acceptance and actual strict gate commits only.
for row in extra:
 row['existing_actual021_parser_accepted']=True;row['parser_or_price_reaggregation_rerun']=False
last=next(x for x in s['resolver_audit']if x['status']=='wait_budget_exceeded');assert last['request_sha256']in failed and not Path(last['response_path']).exists()
failure_request=owned(last['request_path'],last['request_file_sha256'])
assert failure_request['requirements'][0]['vt_symbol']=='CF505.CZCE'and failure_request['requirements'][0]['execution_trade_date']=='2025-04-11'
end=datetime.fromisoformat(last['started_at'])+timedelta(seconds=last['elapsed_wait_seconds']);context_start=datetime.fromisoformat(json.loads(Path(s['upstream_bindings']['run_context.json']['path']).read_bytes())['started_at'])
assert last['elapsed_wait_seconds']<1800 and 7199<(end-context_start).total_seconds()<7202
scope=dict(schema='stage134_committed_scope_audit_only_v1',audit_only=True,new_frozen_dataset=False,origin='stage065 failed capture, not Stage063',capture=s['upstream_bindings']['failure_capture.pkl.gz'],terminal=s['upstream_bindings']['actual_terminal'],context=s['upstream_bindings']['run_context.json'],committed_deliveries=rows,inherited_reviews=prior_bind,previously_uncovered_eight=extra,rights=dict(unique_keys=len(union),full_keys=len(full),explicit_anchor_only_keys=len(anchors-full),qualified_anchor_keys=len(full|anchors),appended_keys=totalM,existing_keys=sum(x['E']for x in rows)),counts=dict(requested=160,pointer_accepted=159,committed=159,gate_failed=1,original_151_confirmed=len(prior),previously_uncovered_eight=8),failure_excluded=dict(request_sha256=last['request_sha256'],request_path=last['request_path'],request_file_sha256=last['request_file_sha256'],no_response=True,no_commit=True,elapsed_wait_seconds=last['elapsed_wait_seconds'],approx_budget_end=str(end),approx_whole_elapsed_seconds=(end-context_start).total_seconds(),actual_error='TimeoutError qualified_data_wait_budget_exceeded; wrapped by RuntimeError backtest_bar_failed 2025-04-11'),measured_metadata_and_eight_delivery_bindings=bindings,source_price_reaggregation=False,old_market_sources_rehashed=False,partial_financial_tables_read=False)
(O/'committed_scope_audit.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in scope.items()if k not in ['committed_deliveries','measured_metadata_and_eight_delivery_bindings','previously_uncovered_eight']},ensure_ascii=False,indent=2))
print(json.dumps({'eight':[{'digest':x['request_sha256'],'scopes':[{k:v for k,v in r.items()if k!='required_timestamps'}for r in x['requirements']],'receipt_sha256':x['receipt_sha256']}for x in extra]},ensure_ascii=False,indent=2))

