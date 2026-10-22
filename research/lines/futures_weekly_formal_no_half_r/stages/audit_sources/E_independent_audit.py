from pathlib import Path
from collections import defaultdict,deque
import json,hashlib,sys,ast,sqlite3
import pandas as pd,numpy as np
ROOT=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian');LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs';result={}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def finance(p,db_path):
 d=pd.read_csv(p/'daily.csv');t=pd.read_csv(p/'trades.csv');positions=pd.read_csv(p/'positions.csv');par=json.loads((p/'effective_parameters.json').read_text());sizes=par['sizes'];slips=par['slippages'];rates=par['rates'];t['sign']=t.direction.map({'多':1,'空':-1});t['signed']=t.sign*t.volume;t['cost']=[r.volume*slips[r.vt_symbol]*sizes[r.vt_symbol] for r in t.itertuples()];t['cash_delta']=[-r.signed*r.price*sizes[r.vt_symbol]-r.cost for r in t.itertuples()]
 assert t.sign.notna().all() and t.volume.gt(0).all() and t.price.gt(0).all() and np.isfinite(t[['volume','price','cash_delta','cost']].to_numpy()).all(),'invalid_trade_values'
 assert all(float(x)==0 for x in rates.values()) and float(d.commission.sum())==0,'nonzero_commission_requires_independent_fee_model'
 cash=t.groupby('trading_date').cash_delta.sum().reindex(d.date,fill_value=0).cumsum()+150000;pos=positions[positions.date.ge('2020-01-01')].copy();pos['mark']=[r.end_pos*r.close_price*sizes[r.vt_symbol] for r in pos.itertuples()];equity=cash.to_numpy()+pos.groupby('date').mark.sum().reindex(d.date,fill_value=0).to_numpy();rets=pd.Series(equity).pct_change().fillna(0)
 assert np.isfinite(equity).all() and np.isfinite(rets.to_numpy()).all() and np.isfinite(d.account_equity.to_numpy()).all(),'nonfinite_equity_or_returns'
 r=dict(end_equity=float(equity[-1]),return_pct=float((equity[-1]/150000-1)*100),dd_pct=float(((equity/np.maximum.accumulate(equity))-1).min()*100),sharpe_252_sample=float(rets.mean()/rets.std(ddof=1)*np.sqrt(252)),slippage=float(t.cost.sum()),commission=float(d.commission.sum()),trades=len(t),ledger_max_residual=float(np.max(abs(equity-d.account_equity))),daily_cost_max_residual=float(np.max(abs(t.groupby('trading_date').cost.sum().reindex(d.date,fill_value=0).to_numpy()-d.slippage))),signed_volume_mismatch=int((t.signed!=t.signed_volume).sum()),rate_values=sorted(set(rates.values())),account_days=len(d),first_day=d.date.min(),last_day=d.date.max())
 queues=defaultdict(deque);pairs=[]
 for x in t.itertuples():
  q=queues[x.vt_symbol];n=float(x.volume)
  if x.offset=='开':q.append([int(x.sign),n,float(x.price),str(x.trade_id)]);continue
  while n>1e-8:
   if not q:raise ValueError('unmatched close '+x.trade_id)
   sign,qty,price,tid=q[0]
   if sign!=-x.sign:raise ValueError('same sign close '+x.trade_id)
   v=min(n,qty);net=(sign*(x.price-price)-2*slips[x.vt_symbol])*sizes[x.vt_symbol]*v;pairs.append(dict(entry=tid,exit=x.trade_id,volume=v,pnl=net));n-=v;q[0][1]-=v
   if q[0][1]<1e-8:q.popleft()
 f=pd.DataFrame(pairs);r.update(closed_fifo_matches=len(f),closed_lots=float(f.volume.sum()),lot_weighted_win_pct=float(f.loc[f.pnl>0,'volume'].sum()/f.volume.sum()*100),fifo_match_win_pct=float(f.pnl.gt(0).mean()*100),remaining_open_lots=float(sum(x[1] for q in queues.values() for x in q)))
 r.update(closed_net_pnl=float(f.pnl.sum()),average_winning_match=float(f.loc[f.pnl>0,'pnl'].mean()),average_losing_match_abs=float(-f.loc[f.pnl<0,'pnl'].mean()),profit_factor=float(f.loc[f.pnl>0,'pnl'].sum()/-f.loc[f.pnl<0,'pnl'].sum()))
 by={(day,sym):g for (day,sym),g in t.groupby(['trading_date','vt_symbol'])};maxp=0
 for x in pos.itertuples():
  hold=(x.close_price-x.pre_close)*x.start_pos*sizes[x.vt_symbol];g=by.get((x.date,x.vt_symbol));trade=0 if g is None else float(((x.close_price-g.price)*g.signed*sizes[x.vt_symbol]-g.cost).sum());maxp=max(maxp,abs(hold+trade-x.net_pnl))
 r['per_symbol_pnl_max_residual']=maxp
 held=positions.loc[positions.start_pos.ne(0)|positions.end_pos.ne(0)|positions.trade_count.ne(0)]
 with sqlite3.connect(f'file:{db_path}?mode=ro',uri=True) as db:raw=pd.read_sql_query("select symbol||'.'||exchange vt_symbol, substr(datetime,1,10) date, close_price from dbbardata where interval='d'",db)
 j=held.merge(raw,on=['vt_symbol','date'],how='left',suffixes=('_export','_raw'));r.update(held_or_traded_rows=len(held),daily_raw_mismatches=int((j.close_price_raw.isna()|~np.isfinite(j.close_price_raw)|j.close_price_raw.le(0)|(j.close_price_export-j.close_price_raw).abs().gt(1e-8)).sum()))
 return r
marker=OUT/'E_completed_attempt.json'
if not marker.exists():raise ValueError('E_not_completed_yet')
C=Path(json.loads(marker.read_text())['path']);terminal=json.loads((C/'terminal.json').read_text())
assert terminal['status']=='completed_pending_independent_review' and terminal['error'] is None
result['E_path']=str(C)
result['D']=finance(OUT/'D_attempt011',OUT/'data/daily.sqlite')
result['E']=finance(C,OUT/'stage005_data/daily.sqlite')
m=json.loads((C/'input_manifest.json').read_text());bad=[p for p,h in m.items() if sha(p)!=h];result['input_count']=len(m);result['input_sha_mismatches']=bad
values=['open','high','low','close','volume','open_oi','close_oi'];base=next(Path(p) for p in m if 'full_minute_bars' in p and p.endswith('.csv'));frame=pd.read_csv(base);frame.bar_datetime=pd.to_datetime(frame.bar_datetime);proofs=[Path(p) for p in m if p.endswith('_proof.json')];frozen=json.loads(Path('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/C_final/input_manifest.json').read_text());sourcebad=[];conflicts=0;proofrows=0
for proof in proofs:
 d=json.loads(proof.read_text());s=d['source'];raw=Path(s['raw_path'])
 if s.get('parent_proof_path'):
  parent=Path(s['parent_proof_path']);parent_meta=json.loads(parent.read_text());parent_inputs=m
  if sha(parent)!=s.get('parent_proof_sha256') or parent_inputs.get(str(parent))!=s.get('parent_proof_sha256') or any(s.get(k)!=v for k,v in parent_meta['source'].items()):sourcebad.append(str(proof)+':parent_proof_identity')
 if sha(raw)!=s['source_sha256']:sourcebad.append(str(raw))
 if s.get('kind')=='existing_completed_minute_cache' and (s['original_sha256'] not in set(frozen.values()) or sha(s['original_path'])!=s['original_sha256']):sourcebad.append(s['original_path'])
 patch=pd.read_parquet(proof.with_name(proof.name.replace('_proof.json','.parquet')));patch.bar_datetime=pd.to_datetime(patch.bar_datetime);proofrows+=len(patch)
 rawframe=pd.read_parquet(raw);rawframe.bar_datetime=pd.to_datetime(rawframe.bar_datetime);rawindex=rawframe.set_index(['vt_symbol','bar_datetime']);patchindex=patch.set_index(['vt_symbol','bar_datetime'])
 assert sha(proof.with_name(proof.name.replace('_proof.json','.parquet')))==d['sha256'] and len(patch)==int(d['rows'])
 assert not rawindex.index.duplicated().any() and not patchindex.index.duplicated().any()
 expected_keys=set()
 for task in d['tasks']:
  first=pd.Timestamp(task['natural_date']+' '+task['start']);end=pd.Timestamp(task['natural_date'])+pd.Timedelta(days=1) if task['end_exclusive']=='24:00' else pd.Timestamp(task['natural_date']+' '+task['end_exclusive'])
  expected_keys.update((task['vt_symbol'],dt) for dt in pd.date_range(first,end-pd.Timedelta(minutes=1),freq='min'))
 assert set(patchindex.index)==expected_keys,'proof_task_fragment_key_mismatch'
 if s.get('kind')=='tqsdk_completed_snapshot':
  for symbol,g in rawframe.groupby('vt_symbol'):
   b=s['serial_bounds'][symbol]
   assert pd.Timestamp(b['earliest'])==g.bar_datetime.min() and pd.Timestamp(b['latest'])==g.bar_datetime.max() and int(b['rows'])==len(g)
   assert g.bar_datetime.max()+pd.Timedelta(minutes=1)<=pd.Timestamp(s['snapshot_at'])

 if not patchindex.index.isin(rawindex.index).all() or not np.allclose(patchindex[values].to_numpy(float),rawindex.loc[patchindex.index,values].to_numpy(float),rtol=0,atol=1e-8):sourcebad.append(str(proof)+':raw_values')
 if s.get('kind')=='tqsdk_completed_snapshot':
  for task in d['tasks']:
   first=pd.Timestamp(task['natural_date']+' '+task['start']);end=pd.Timestamp(task['natural_date'])+pd.Timedelta(days=1) if task['end_exclusive']=='24:00' else pd.Timestamp(task['natural_date']+' '+task['end_exclusive']);last=end-pd.Timedelta(minutes=1);bounds=s['serial_bounds'][task['vt_symbol']]
   if not(pd.Timestamp(bounds['earliest'])<first and pd.Timestamp(bounds['latest'])>=last and pd.Timestamp(bounds['latest'])<pd.Timestamp(s['snapshot_at']) and end<=pd.Timestamp(s['snapshot_at'])):sourcebad.append(str(proof)+':snapshot_bounds')
 old=frame.set_index(['vt_symbol','bar_datetime']);new=patch.set_index(['vt_symbol','bar_datetime']);common=old.index.intersection(new.index)
 if len(common):conflicts+=int(not np.allclose(old.loc[common,values].to_numpy(float),new.loc[common,values].to_numpy(float),rtol=0,atol=1e-8))
 newrows=patch.loc[~pd.MultiIndex.from_frame(patch[['vt_symbol','bar_datetime']]).isin(old.index)];frame=pd.concat([frame,newrows],ignore_index=True)
pre_catalog_keys=pd.MultiIndex.from_frame(frame[['vt_symbol','bar_datetime']])
catalog_root=OUT/'stage003_anchor_catalog';catalog_manifest=json.loads((catalog_root/'manifest.json').read_text());catalog=pd.read_csv(catalog_root/'catalog.csv');catalog.bar_datetime=pd.to_datetime(catalog.bar_datetime)
cat_source_bad=[p for p,h in catalog_manifest['source_files'].items() if h not in set(frozen.values()) or sha(p)!=h]
catindex=catalog.set_index(['vt_symbol','bar_datetime'])
append=catalog.loc[~pd.MultiIndex.from_frame(catalog[['vt_symbol','bar_datetime']]).isin(pre_catalog_keys)].copy();frame=pd.concat([frame,append],ignore_index=True)
result['catalog']={'rows':len(catalog),'appended_rows':len(append),'manifest_sha_match':sha(catalog_root/'catalog.csv')==catalog_manifest['catalog_sha256'],'source_hash_or_frozen_mismatches':cat_source_bad,'duplicate_keys':int(catalog.duplicated(['vt_symbol','bar_datetime']).sum())}
result.update(proofs=len(proofs),proof_rows=proofrows,source_hash_or_frozen_mismatches=sourcebad,overlay_conflicting_patches=conflicts,overlay_duplicate_minutes=int(frame.duplicated(['vt_symbol','bar_datetime']).sum()))
groups={s:g.set_index('bar_datetime') for s,g in frame.groupby('vt_symbol')};sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'));from qmt_roll_intraday_execution import session_minutes
cal=pd.read_csv(OUT/'stage005_data/mapping.csv').date.unique();audit=json.loads((C/'execution_audit.json').read_text());scans=pd.read_csv(C/'minute_scan_requests.csv');missing=0;invalid=0;duplicates=0
for r in scans.itertuples():
 grid=session_minutes(r.vt_symbol,r.trading_date,cal);grid=grid[grid>=pd.Timestamp(r.execution_datetime)];g=groups[r.vt_symbol];missing+=len(grid.difference(g.index));v=g.loc[g.index.isin(grid)];duplicates+=int(v.index.duplicated().sum());x=v[['open','high','low','close']].to_numpy();invalid+=int(not(np.isfinite(x).all() and (x>0).all() and (v.low<=v[['open','close']].min(axis=1)).all() and (v.high>=v[['open','close']].max(axis=1)).all()))
anchorbad=0
for r in audit['anchor_requests']:
 if r.get('anchor_present') is not True:anchorbad+=1;continue
 g=groups[r['vt_symbol']];v=g.loc[g.index==pd.Timestamp(r['expected_start'])];anchorbad+=int(len(v)!=1 or abs(float(v.open.iloc[0])-float(r['price']))>1e-8)
used_catalog=[]
for row in audit['anchor_requests']:
 key=(row['vt_symbol'],pd.Timestamp(row['expected_start']))
 if key not in pre_catalog_keys:
  if key not in catindex.index:raise ValueError('anchor_not_in_any_source:'+str(key))
  catrow=catindex.loc[key];used_catalog.append({'vt_symbol':key[0],'bar_datetime':key[1],'source_path':catrow.source_path})
used=pd.DataFrame(used_catalog,columns=['vt_symbol','bar_datetime','source_path']).drop_duplicates(['vt_symbol','bar_datetime']);catrawbad=[]
for source,g in used.groupby('source_path'):
 raw=pd.read_csv(source);raw.bar_datetime=pd.to_datetime(raw.bar_datetime);keys=pd.MultiIndex.from_frame(g[['vt_symbol','bar_datetime']]);selected=raw.loc[pd.MultiIndex.from_frame(raw[['vt_symbol','bar_datetime']]).isin(keys)].set_index(['vt_symbol','bar_datetime'])
 if len(selected)!=len(keys) or selected.index.duplicated().any():catrawbad.append(source+':missing_or_duplicate');continue
 if not np.allclose(selected.loc[keys,values].to_numpy(float),catindex.loc[keys,values].to_numpy(float),rtol=0,atol=1e-8):catrawbad.append(source+':values')
result['catalog'].update(actual_used_unique_anchors=len(used),actual_used_sources=sorted(used.source_path.unique()),actual_anchor_original_raw_mismatches=catrawbad)
result['E'].update(minute_scans=len(scans),missing_requested_minutes=missing,invalid_minute_scans=invalid,duplicate_minutes=duplicates,anchor_requests=len(audit['anchor_requests']),bad_anchors=anchorbad,execution_failures=len(audit['failures']))
wb=pd.read_csv(C/'weekly_bars.csv');rawcols=['open_price','high_price','low_price','close_price','volume','open_interest'];errs=[]
with sqlite3.connect(f'file:{OUT/"stage005_data/daily.sqlite"}?mode=ro',uri=True) as db:raw=pd.read_sql_query("select symbol||'.'||exchange vt_symbol, substr(datetime,1,10) date, open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where interval='d'",db)
raw=raw.set_index(['vt_symbol','date']);calgroups={}
for day in sorted(cal):calgroups.setdefault(tuple(pd.Timestamp(day).isocalendar()[:2]),[]).append(day)
for r in wb.itertuples():
 days=ast.literal_eval(r.source_days);key=tuple(pd.Timestamp(r.week_end).isocalendar()[:2]);idx=pd.MultiIndex.from_tuples([(r.vt_symbol,d) for d in days]);rows=raw.reindex(idx)
 if days!=calgroups[key] or days[-1]!=r.week_end or rows.isna().any().any() or rows.volume.le(0).any():errs.append([r.vt_symbol,r.week_end,'source_days']);continue
 expect=np.array([rows.open_price.iloc[0],rows.high_price.max(),rows.low_price.min(),rows.close_price.iloc[-1],rows.volume.sum(),rows.open_interest.iloc[-1]]);actual=np.array([r.open,r.high,r.low,r.close,r.volume,r.open_interest])
 if not np.allclose(expect,actual,rtol=0,atol=1e-8):errs.append([r.vt_symbol,r.week_end,'values'])
rd=pd.read_csv(C/'weekly_readiness.csv');result['weekly']=dict(exported_bars=len(wb),weekly_raw_mismatches=errs,readiness_days=len(rd),zero_ready_target_days=int(rd.ready_target_contracts.eq(0).sum()),median_ready_targets=float(rd.ready_target_contracts.median()),max_ready_targets=int(rd.ready_target_contracts.max()),coverage=json.loads((C/'weekly_coverage.json').read_text()))
actual=json.loads((C/'actual_strategy_settings.json').read_text());settings=actual[0]['actual'];result['actual_flags']={k:settings[k] for k in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter','research_exact_array_manager_size','rollover_delay_trading_days','rollover_shape_history_mode']}
result['strategy_class']=actual[0]['strategy_class']
ai=pd.read_csv(C/'entry_candidates.csv');ai_fields=[x for x in ai.columns if 'ai_product_pool' in x]
result['ai_candidates']={'rows':len(ai),'columns':ai_fields,'enabled_values':sorted(ai.ai_product_pool_enabled.dropna().astype(int).unique().tolist()),'allowed_values':sorted(ai.ai_product_pool_allowed.dropna().astype(int).unique().tolist()),'nonempty_signal_dates':int(ai.ai_product_pool_signal_date.fillna('').astype(str).ne('').sum()),'nonzero_scores':int(ai.ai_product_pool_score.fillna(0).abs().gt(1e-12).sum()),'nonzero_ranks':int(ai.ai_product_pool_rank.fillna(0).ne(0).sum())}
universe=pd.read_csv(settings['product_universe_csv_path']);result['universe']={'rows':len(universe),'products':universe.product_vt_symbol.tolist(),'sha256':sha(settings['product_universe_csv_path'])}

result['disabled_event_rows']={name:len(pd.read_csv(C/(name+'.csv'))) for name in ['intraday_events','stop_retry_events','c2_events','minute_scan_requests']}
prev=json.loads((OUT/'D_attempt011/effective_parameters.json').read_text());new=json.loads((C/'effective_parameters.json').read_text())
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [r for k in sorted(set(a)|set(b)) for r in diff(a.get(k),b.get(k),path+'.'+k)]
 if a!=b:return [{'path':path,'D':a,'E':b}]
 return []
result['effective_parameter_deltas_D_to_E']=diff(prev,new)
result['input_manifest_postflight']=json.loads((C/'postflight.json').read_text())
# Additional independent checks introduced for the enlarged data source.
t=pd.read_csv(C/'trades.csv');daily=pd.read_csv(C/'daily.csv');positions=pd.read_csv(C/'positions.csv')
with sqlite3.connect((OUT/'stage005_data/daily.sqlite').as_uri()+'?mode=ro',uri=True) as db:
    raw=pd.read_sql_query("select symbol||'.'||exchange vt_symbol,substr(datetime,1,10) date,volume from dbbardata where interval='d'",db)
held=positions.loc[positions.start_pos.ne(0)|positions.end_pos.ne(0)|positions.trade_count.ne(0)]
hj=held.merge(raw,on=['vt_symbol','date'],how='left');result['held_or_traded_zero_or_missing_volume']=int((hj.volume.isna()|hj.volume.le(0)|~np.isfinite(hj.volume)).sum())
actual_binding=json.loads((C/'actual_database_binding.json').read_text());result['actual_database_binding']=actual_binding
assert Path(actual_binding['database_list'][0][2]).resolve()==(OUT/'stage005_data/daily.sqlite').resolve()
assert actual_binding['expected']==str(OUT/'stage005_data/daily.sqlite')
inputs_postflight=json.loads((C/'postflight.json').read_text());assert inputs_postflight['inputs_unchanged'] and not inputs_postflight['mismatches']
result['engine_capital']=actual[0]['engine_capital'];assert result['engine_capital']==150000
assert daily.account_capital.eq(150000).all() and daily.c3_capital.eq(150000).all()
# Every exported fill links back to an actual canonical minute request, not a daily-open proxy.
anchor_by_order={a['order_id']:a for a in audit['anchor_requests']};trade_anchor_bad=[]
for row in t.itertuples():
    anchor=anchor_by_order.get(row.order_id)
    stamp=pd.Timestamp(row.datetime).tz_convert('Asia/Shanghai').tz_localize(None)
    canonical=session_minutes(row.vt_symbol,row.trading_date,cal)[0]
    if anchor is None or stamp!=canonical or pd.Timestamp(anchor['expected_start'])!=canonical or str(anchor['actual_time'])!=str(anchor['expected_start']) or abs(float(anchor['price'])-float(row.price))>1e-8:
        trade_anchor_bad.append(row.trade_id)
result['actual_fill_anchor_link_mismatches']=trade_anchor_bad
internal=pd.read_csv(C/'internal_equity_daily.csv');joined=daily.merge(internal,on='date',validate='one_to_one');result['internal_equity_max_residual']=float((joined.account_equity-joined.estimated_equity).abs().max())
result['traded_products']=sorted({__import__('re').match('[A-Za-z]+',x).group() for x in t.vt_symbol});result['traded_product_count']=len(result['traded_products'])
result['margin_exposure']={'days_positive':int(daily.total_margin_exact.gt(0).sum()),'mean_margin_equity_pct':float((daily.total_margin_exact/daily.account_equity*100).mean())}
# Identify the data-only source change to old D: every held/traded date gained from source completion.
with sqlite3.connect((OUT/'data/daily.sqlite').as_uri()+'?mode=ro',uri=True) as db:old_days=pd.read_sql_query("select symbol||'.'||exchange vt_symbol,substr(datetime,1,10) date from dbbardata where interval='d'",db)
newheld=held.merge(old_days,on=['vt_symbol','date'],how='left',indicator=True);result['E_held_or_traded_days_absent_old_D_database']=newheld.loc[newheld._merge.eq('left_only'),['date','vt_symbol','start_pos','end_pos','trade_count']].to_dict('records')
# Persist annual comparison from actual exported ledgers; no new strategy execution.
annual=[]
for label,path in [('D',OUT/'D_attempt011'),('E',C)]:
    q=pd.read_csv(path/'daily.csv');q['year']=q.date.str[:4];opening=150000.
    for year,g in q.groupby('year',sort=True):
        end=float(g.account_equity.iloc[-1]);annual.append(dict(arm=label,year=year,pnl=float(g.net_pnl.sum()),return_pct=(end/opening-1)*100,end_equity=end));opening=end
result['annual']=annual
checks={
 'ledger':result['E']['ledger_max_residual']<1e-7,
 'per_symbol':result['E']['per_symbol_pnl_max_residual']<1e-7,
 'daily_cost':result['E']['daily_cost_max_residual']<1e-7,
 'signed_volume':result['E']['signed_volume_mismatch']==0,
 'daily_raw':result['E']['daily_raw_mismatches']==0,
 'held_volume':result['held_or_traded_zero_or_missing_volume']==0,
 'sha':not result['input_sha_mismatches'],
 'proof_sources':not result['source_hash_or_frozen_mismatches'],
 'proof_overlay':result['overlay_conflicting_patches']==0 and result['overlay_duplicate_minutes']==0,
 'catalog_source':not result['catalog']['source_hash_or_frozen_mismatches'] and not result['catalog']['actual_anchor_original_raw_mismatches'],
 'anchors':result['E']['bad_anchors']==0 and result['E']['execution_failures']==0 and not trade_anchor_bad,
 'weekly':not result['weekly']['weekly_raw_mismatches'],
 'flags':all(result['actual_flags'][k] is False for k in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']),
 'no_intraday_events':all(v==0 for v in result['disabled_event_rows'].values()),
 'AI_disabled':result['ai_candidates']['enabled_values']==[0] and result['ai_candidates']['allowed_values']==[1] and result['ai_candidates']['nonempty_signal_dates']==0 and result['ai_candidates']['nonzero_scores']==0 and result['ai_candidates']['nonzero_ranks']==0,
 'internal_equity':result['internal_equity_max_residual']<1e-7,
 'window':result['E']['last_day']=='2026-10-22' and result['E']['first_day']=='2020-01-02'
}
result['checks']=checks;result['verdict']='PASS_RESEARCH_ACCOUNTING_WITH_LIMITATIONS' if all(checks.values()) else 'REJECT_UNRESOLVED_AUDIT_CHECKS';result['new_financial_replays']=0
out=OUT/'stage005_independent_review';out.mkdir(exist_ok=True)
(out/'E_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k in ['E_path','D','E','checks','verdict','margin_exposure','traded_product_count','traded_products','weekly','effective_parameter_deltas_D_to_E','E_held_or_traded_days_absent_old_D_database']},ensure_ascii=False,indent=2))
