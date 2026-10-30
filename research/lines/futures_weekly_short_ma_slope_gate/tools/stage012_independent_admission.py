"""Independent source/whole-check induction proof for nonbinding50k reuse.

No financial engine is instantiated. Terminal cumulative T is never the only
admission criterion: every native sizing check and positive event is replayed,
and exact source/actual settings/ledger identities are bound first.
"""
from pathlib import Path
import ast,copy,hashlib,json,math,time
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';checks=0
SPECIAL={'risk_ratio_volume_open_interest_surge':.06,'risk_ratio_open_interest_surge':.06,'risk_ratio_open_interest_decline':.025}
EXPECTED_BINDING=['2016-06-01','2017-01-01','2017-06-01','2018-01-01','2018-06-01','2019-01-01','2019-06-01','2020-01-01','2021-06-01']
FIELDS={'reserve_balance','reserve_cumulative_transfer','reserve_signal_checks','reserve_transfer_events','reserve_daily_snapshots','research_reserve_initial','research_reserve_floor','research_reserve_account_start','total_account_equity','research_reserve_enabled'}
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6),label)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def fingerprint(p):
 s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def reserve_AST():
 old=LINE/'tools/stage009_reserve.py';new=LINE/'tools/stage012_reserve.py';a=ast.parse(old.read_text());b=ast.parse(new.read_text());changed=0
 for n in b.body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RESERVE_INITIAL' for t in n.targets):
   ok(isinstance(n.value,ast.Constant) and n.value.value==50000.,'new_reserve_exact50k');n.value.value=150000.;changed+=1
 ok(changed==1 and ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False),'only_one_RESERVE_INITIAL_constant_AST_delta')
 return {'old_sha256':sha(old),'new_sha256':sha(new),'normalized_AST_sha256':hashlib.sha256(ast.dump(a,include_attributes=False).encode()).hexdigest(),'exact_one_constant_delta':True}
def consumer_scan(graph):
 references={};scanned=0
 allowed={'run_stage009.py','stage009_reserve.py','stage009_contract.py','test_stage009_reserve.py','test_stage009_runner.py'}
 for q in graph:
  p=Path(q)
  if p.suffix!='.py':continue
  tree=ast.parse(p.read_text());scanned+=1;rows=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Attribute) and n.attr in FIELDS:rows.append([n.lineno,n.attr])
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'getattr','hasattr'} and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value in FIELDS:rows.append([n.lineno,n.args[1].value])
  if rows:
   ok(p.parent.resolve()==(LINE/'tools').resolve() and p.name in allowed,'no_hidden_R_or_W_trading_consumer:'+str(p));references[str(p)]=rows
 # The only engine-side read outside the wallet wrapper is the count of all
 # sizing checks in run_stage009.Engine._fill_order. It only appends a phase
 # witness. Check count is unchanged when the funding amount changes.
 tree=ast.parse((LINE/'tools/run_stage009.py').read_text());engine=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='Engine');fill=next(n for n in engine.body if isinstance(n,ast.FunctionDef) and n.name=='_fill_order');attrs=[n for n in ast.walk(fill) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='getattr' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value in FIELDS]
 ok(len(attrs)==1 and attrs[0].args[1].value=='reserve_signal_checks','engine_only_check_count_for_exported_phase_witness')
 ok(not any(isinstance(n,ast.If) for n in fill.body),'phase_witness_does_not_gate_engine_fill')
 return {'python_sources_scanned':scanned,'exact_field_references':references,'external_trading_consumers':0,'runner_engine_read':'reserve_signal_checks cardinality only; phase witness; never gates fill'}
def native(row,actual):return (row['direction']=='long' and row['signal'] in {'long_case1a','long_case2'} and actual['long_entry_enabled']) or (row['direction']=='short' and row['signal']=='short_case1a' and actual['short_entry_enabled'])
def prove_window(path,start,source_groups,source_lookup):
 actual=load(path/'actual_strategy_settings.json')[0]['actual'];effective=load(path/'effective_parameters.json');pre=load(path/'preflight.json');oldreceipt=load(STAGES/'stage009_independent_receipts'/f'{start}_C.json');calls=load(path/'reserve_checks.json');events=load(path/'reserve_events.json');raw=pd.read_csv(path/'daily.csv');rawmap=dict(zip(raw.date.astype(str).str[:10],raw.account_equity));seen=set();cum=0.;eventindex=0;first=None;qualified=0;positive=0;previous='';proof_rows=[]
 ok(oldreceipt['status']=='PASS_WITH_LIMITATIONS' and all(oldreceipt[k]==0 for k in ['P0','P1','P2','failures']),'old_independent_finance_accepted');ok(pre['arm']=='C' and pre['short_price_range_gate_enabled'] is True and pre['reserve_topup_enabled'] is True,'only_original_funded_C_control')
 for name,value in SPECIAL.items():near(actual[name],value,'original_special_risk:'+name)
 for name,value in [('risk_ratio_of_total_assets',.018),('risk_ratio_breakout',.018),('risk_ratio_ma_cross_breakout',.018),('min_risk_per_trade',1000.),('oi_price_confirm_risk_restore_multiplier',2.),('directional_30d_risk_boost_multiplier',1.5),('directional_30d_low_volume_risk_multiplier',.5)]:near(actual[name],value,'original_risk_control:'+name)
 ok(all(v==0. for v in effective['rates'].values()),'zero_commission_frozen')
 for row in calls:
  day=str(row['date'])[:10];ok(day>=previous,'ordered_every_check');previous=day;before=(rawmap[day] if day>=start else 150000.)+cum;near(row['trading_equity_before'],before,'original_marked_trading_equity');near(row['reserve_before'],150000.-cum,'original_reserve_chain');near(row['raw_account_equity'],before-cum,'original_raw_equity')
  basic=day>=start and row['entry_context'] in {'flat_entry','reverse_entry'} and native(row,actual);eligible=False
  if basic:
   src=source_lookup[(row['vt_symbol'],day)];stop=float(row['weekly_stop_price']);valid=math.isfinite(stop) and stop>0 and (stop<float(src.close) if row['direction']=='long' else stop>float(src.close));ok(bool(row['weekly_stop_valid'])==valid,'real_stop_direction')
   blocked=False
   if valid and row['direction']=='short':
    g=source_groups[(row['vt_symbol'],src.contract_epoch_id)];g=g.loc[g.date.le(day)];lo=float(g.low.min());hi=float(g.high.max());blocked=hi==lo or float(src.close)<=lo+.2*(hi-lo);ok(row['range_checked'] is True and row['range_would_block']==blocked,'real_C_bottom20_qualification');near(row['range_low'],lo,'real_C_range_low');near(row['range_high'],hi,'real_C_range_high')
   eligible=valid and not blocked
  ok(row['eligible']==eligible,'eligibility_not_trusted');dup=eligible and row['candidate_key'] in seen;ok(row['duplicate']==dup,'duplicate_check')
  amount=0.
  if eligible and not dup:seen.add(row['candidate_key']);amount=min(max(150000.-before,0.),150000.-cum);qualified+=1
  near(row['transfer_amount'],amount,'old_full_transfer_formula');candidate=min(max(150000.-before,0.),max(0.,50000.-cum)) if eligible and not dup else 0.
  if first is None and not math.isclose(candidate,amount,rel_tol=1e-10,abs_tol=1e-6):first=dict(check_index=len(proof_rows)+1,date=day,candidate_key=row['candidate_key'],old_transfer=amount,new50k_transfer=candidate,cumulative_before=cum,new_remaining_before=max(0.,50000.-cum))
  if first is None:near(candidate,amount,'every50k_prefix_transfer_exact')
  if amount:
   e=events[eventindex];eventindex+=1;positive+=1;ok(e['candidate_key']==row['candidate_key'],'real_event_identity');near(e['transfer_amount'],amount,'real_event_amount')
  cum+=amount;near(row['cumulative_transfer'],cum,'original_cumulative_after');near(row['reserve_after'],150000.-cum,'original_reserve_after');near(row['trading_equity_after'],before+amount,'original_trading_after');near(row['total_account_equity'],before+(150000.-cum+amount),'original_W_conservation')
  proof_rows.append([row['candidate_key'],bool(eligible),bool(dup),amount,candidate,cum])
 ok(eventindex==len(events),'no_extra_events');near(cum,oldreceipt['reserve_diagnostics']['cumulative_transfer'],'old_receipt_terminal_T')
 bridge=pd.read_csv(path/'reserve_daily.csv');ok(bridge.date.astype(str).str[:10].tolist()==raw.date.astype(str).str[:10].tolist(),'old_full_daily_calendar');ok(bridge.cumulative_transfer.is_monotonic_increasing and bridge.cumulative_transfer.ge(-1e-6).all(),'no_reserve_refill')
 nonbinding=first is None;ok(nonbinding==(cum<=50000.+1e-6),'prefix_proof_agrees_terminal_only_after_full_checks')
 if nonbinding:ok((bridge.cumulative_transfer<=50000.+1e-6).all(),'all_daily_reserve50k_nonnegative')
 return dict(start=start,arm='C',method='proven_nonbinding_reuse' if nonbinding else 'fresh_engine_required',source_path=str(path),nonbinding=nonbinding,signal_checks=len(calls),qualified_unique_checks=qualified,positive_transfer_events=positive,cumulative_transfer=cum,reserve50k_end=50000.-cum if nonbinding else None,first_binding=first,check_transcript_sha256=hashlib.sha256(json.dumps(proof_rows,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),old_independent_receipt_sha256=sha(STAGES/'stage009_independent_receipts'/f'{start}_C.json'),settings_sha256=sha(path/'actual_strategy_settings.json'),effective_sha256=sha(path/'effective_parameters.json'),old_input_manifest_sha256=sha(path/'input_manifest.json'))
def main():
 out=STAGES/'stage012_independent_reuse_admission.json';cacheout=STAGES/'stage012_independent_hash_cache.json'
 if out.exists() or cacheout.exists():raise ValueError('immutable_stage012_admission_exists')
 started=time.monotonic();f=load(STAGES/'stage009_freeze.json');regpath=LINE/'outputs/stage009_multistart/registry.json';reg=load(regpath);manifestpath=STAGES/'stage009_delivery_manifest.json';ok(sha(manifestpath)=='b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424','specified_original_final_manifest');ok(load(manifestpath)['files_sha256'][str(regpath)]==sha(regpath),'old_registry_bound_final')
 graph={};selected=[]
 for start in f['starts']:
  j=reg['jobs'][start+'|C'];ok(j['status']=='validated','all23old_C_validated');path=Path(j['path']);selected.append((start,path));graph.update(j['files_sha256']);graph.update(load(path/'input_manifest.json'));rp=STAGES/'stage009_independent_receipts'/f'{start}_C.json';graph[str(rp)]=sha(rp)
 for key,name in {'daily_sqlite_sha256':'daily.sqlite','mapping_sha256':'mapping.csv','physical_epoch_daily_sha256':'physical_epoch_daily.csv','receipt_sha256':'receipt.json'}.items():graph[str(Path(f['data_directory'])/name)]=f['data_identity'][key]
 graph[str(manifestpath)]=sha(manifestpath);graph[str(regpath)]=sha(regpath);graph[str(STAGES/'stage009_freeze.json')]=sha(STAGES/'stage009_freeze.json')
 cache={};total=0
 for q,want in sorted(graph.items()):
  before=fingerprint(q);actual=sha(q);ok(actual==want,'source_and_full_ledger_SHA:'+q);ok(fingerprint(q)==before,'stable_hash_read:'+q);cache[q]={'sha256':actual,'stat':before};total+=Path(q).stat().st_size
 scan=consumer_scan(graph);astproof=reserve_AST();data=pd.read_csv(Path(f['data_directory'])/'physical_epoch_daily.csv',dtype={'date':str,'vt_symbol':str,'contract_epoch_id':str});source_lookup={(r.vt_symbol,r.date):r for r in data.itertuples()};groups={(s,e):g.sort_values('date') for (s,e),g in data.groupby(['vt_symbol','contract_epoch_id'])};windows=[prove_window(p,s,groups,source_lookup) for s,p in selected];binding=[r['start'] for r in windows if not r['nonbinding']];reusable=[r['start'] for r in windows if r['nonbinding']];ok(binding==EXPECTED_BINDING and len(reusable)==14,'exact9binding_14nonbinding')
 cacheout.write_text(json.dumps(dict(schema='stage012_independent_hash_cache_v1',files=cache,files_count=len(cache),bytes_verified=total,old_cache_files_modified=False),ensure_ascii=False,indent=2)+'\n')
 result=dict(schema='stage012_independent_nonbinding_admission_v1',accepted=True,status='PASS_14_PROVEN_NONBINDING_9_REQUIRE_FRESH_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,checks=checks,source_consumer_scan=scan,reserve_AST=astproof,data_identity=f['data_identity'],old_final_manifest_sha256=sha(manifestpath),old_registry_sha256=sha(regpath),source_hash_cache=str(cacheout),source_hash_cache_sha256=sha(cacheout),deduplicated_files=len(cache),deduplicated_bytes=total,starts=f['starts'],cutoff=f['cutoff'],reuse_starts=reusable,fresh_starts=binding,windows=windows,induction='Before first candidate, E/positions/orders/risk histories are equal. At every check, native eligibility and duplicate state are equal because no inherited trading consumer reads unused R or auxiliary W. Whenever old T is fully payable by new50k, the same transfer leads to the same E and unchanged funding-cache refresh; parent sizing/orders/fills/MTM/fees remain identical. This induction proves complete paths for14 windows. Nine first divergent transfers invalidate reuse and require fresh engines. Future prices are never used by strategy; as-of historical T is used only to validate a saved-cache identity.',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',new_runner_admission='Pending frozen Stage012 runner/contract source and real binding canary; this proof does not claim23 new engines',overfit_risk='YES: fixed50k chosen after viewing same overlapping history; no amount scan',continued_value='YES: measures commitment/capital/survival tradeoff, not alpha',seconds=time.monotonic()-started,auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['windows','source_consumer_scan','induction']},ensure_ascii=False))
if __name__=='__main__':main()
