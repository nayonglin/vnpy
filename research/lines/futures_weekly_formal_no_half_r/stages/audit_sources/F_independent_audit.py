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
   v=min(n,qty);net=(sign*(x.price-price)-2*slips[x.vt_symbol])*sizes[x.vt_symbol]*v;pairs.append(dict(entry=tid,exit=x.trade_id,vt_symbol=x.vt_symbol,volume=v,pnl=net));n-=v;q[0][1]-=v
   if q[0][1]<1e-8:q.popleft()
 f=pd.DataFrame(pairs);r.update(closed_fifo_matches=len(f),closed_lots=float(f.volume.sum()),lot_weighted_win_pct=float(f.loc[f.pnl>1e-8,'volume'].sum()/f.volume.sum()*100),fifo_match_win_pct=float(f.pnl.gt(1e-8).mean()*100),remaining_open_lots=float(sum(x[1] for q in queues.values() for x in q)))
 r.update(closed_net_pnl=float(f.pnl.sum()),average_winning_match=float(f.loc[f.pnl>1e-8,'pnl'].mean()),average_losing_match_abs=float(-f.loc[f.pnl< -1e-8,'pnl'].mean()),profit_factor=float(f.loc[f.pnl>1e-8,'pnl'].sum()/-f.loc[f.pnl< -1e-8,'pnl'].sum()))
 # Independent inventory conservation from fills, including every exported no-trade day.
 ordered=pos.sort_values(['vt_symbol','date']).copy();fill_delta=t.groupby(['trading_date','vt_symbol']).signed.sum();ix=pd.MultiIndex.from_frame(ordered[['date','vt_symbol']]);ordered['fill_delta']=fill_delta.reindex(ix,fill_value=0).to_numpy();ordered['from_fills_end']=ordered.groupby('vt_symbol').fill_delta.cumsum();ordered['from_fills_start']=ordered.from_fills_end-ordered.fill_delta
 r['end_inventory_from_fills_max_residual']=float((ordered.from_fills_end-ordered.end_pos).abs().max());r['start_inventory_from_fills_max_residual']=float((ordered.from_fills_start-ordered.start_pos).abs().max());r['position_change_from_fills_max_residual']=float((ordered.fill_delta-ordered.pos_change).abs().max());r['fill_days_missing_position_rows']=int((~fill_delta.index.isin(ix)).sum())
 by={(day,sym):g for (day,sym),g in t.groupby(['trading_date','vt_symbol'])};maxp=0
 for x in pos.itertuples():
  hold=(x.close_price-x.pre_close)*x.start_pos*sizes[x.vt_symbol];g=by.get((x.date,x.vt_symbol));trade=0 if g is None else float(((x.close_price-g.price)*g.signed*sizes[x.vt_symbol]-g.cost).sum());maxp=max(maxp,abs(hold+trade-x.net_pnl))
 r['per_symbol_pnl_max_residual']=maxp
 held=positions.loc[positions.start_pos.ne(0)|positions.end_pos.ne(0)|positions.trade_count.ne(0)]
 with sqlite3.connect(f'file:{db_path}?mode=ro',uri=True) as db:raw=pd.read_sql_query("select symbol||'.'||exchange vt_symbol, substr(datetime,1,10) date, close_price from dbbardata where interval='d'",db)
 j=held.merge(raw,on=['vt_symbol','date'],how='left',suffixes=('_export','_raw'));r.update(held_or_traded_rows=len(held),daily_raw_mismatches=int((j.close_price_raw.isna()|~np.isfinite(j.close_price_raw)|j.close_price_raw.le(0)|(j.close_price_export-j.close_price_raw).abs().gt(1e-8)).sum()))
 return r
marker=OUT/'F_completed_attempt.json'
if not marker.exists():raise ValueError('F_not_completed_yet')
C=Path(json.loads(marker.read_text())['path']);terminal=json.loads((C/'terminal.json').read_text())
assert terminal['status']=='completed_pending_independent_review' and terminal['error'] is None
result['F_path']=str(C)
baseline_audit=OUT/'stage005_independent_review/E_audit.json'
result['E']=json.loads(baseline_audit.read_text())['E'];result['baseline_E_audit_sha256']=sha(baseline_audit)
result['E_merge_bridge']=json.loads((OUT/'stage007_independent_review/E_bridge_audit.json').read_text());assert result['E_merge_bridge']['verdict']=='PASS_EXACT_FINANCIAL_EQUIVALENCE'
result['F']=finance(C,OUT/'stage005_data/daily.sqlite')
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
groups={s:g.set_index('bar_datetime') for s,g in frame.groupby('vt_symbol')};sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'));sys.path.insert(0,str(LINE/'tools'));from stage005_sessions import session_minutes,product_symbol
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
result['F'].update(minute_scans=len(scans),missing_requested_minutes=missing,invalid_minute_scans=invalid,duplicate_minutes=duplicates,anchor_requests=len(audit['anchor_requests']),bad_anchors=anchorbad,execution_failures=len(audit['failures']))
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
result['warmup']={'configured_preload_start':'2019-06-01','first_actual_week_source_day':min(min(ast.literal_eval(x)) for x in wb.source_days),'first_completed_week':str(wb.week_end.min()),'warmup_days':settings['warmup_days'],'weekly_array_manager_size':settings['research_exact_array_manager_size'],'first_ready_target_day':None if rd.ready_target_contracts.eq(0).all() else str(rd.loc[rd.ready_target_contracts.gt(0),'date'].min()),'zero_ready_days_full_window':int(rd.ready_target_contracts.eq(0).sum()),'scope_limit':'Account calendar starts 2020-01-02 but early 2020 is not fully warmed weekly trading history; no COVID-drawdown robustness claim.'}
ai=pd.read_csv(C/'entry_candidates.csv');ai_fields=[x for x in ai.columns if 'ai_product_pool' in x]
result['ai_candidates']={'rows':len(ai),'columns':ai_fields,'enabled_values':sorted(ai.ai_product_pool_enabled.dropna().astype(int).unique().tolist()),'allowed_values':sorted(ai.ai_product_pool_allowed.dropna().astype(int).unique().tolist()),'nonempty_signal_dates':int(ai.ai_product_pool_signal_date.fillna('').astype(str).ne('').sum()),'nonzero_scores':int(ai.ai_product_pool_score.fillna(0).abs().gt(1e-12).sum()),'nonzero_ranks':int(ai.ai_product_pool_rank.fillna(0).ne(0).sum())}
universe=pd.read_csv(settings['product_universe_csv_path']);result['universe']={'rows':len(universe),'products':universe.product_vt_symbol.tolist(),'sha256':sha(settings['product_universe_csv_path'])}

result['disabled_event_rows']={name:len(pd.read_csv(C/(name+'.csv'))) for name in ['intraday_events','stop_retry_events','c2_events','minute_scan_requests']}
prev=json.loads((OUT/'E_attempt009/effective_parameters.json').read_text());new=json.loads((C/'effective_parameters.json').read_text())
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [r for k in sorted(set(a)|set(b)) for r in diff(a.get(k),b.get(k),path+'.'+k)]
 if a!=b:return [{'path':path,'E':a,'F':b}]
 return []
result['effective_parameter_deltas_E_to_F']=diff(prev,new)
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
minute_volumes=[dict(vt_symbol=r['vt_symbol'],bar_datetime=r['expected_start'],volume=float(groups[r['vt_symbol']].loc[pd.Timestamp(r['expected_start']),'volume'])) for r in [anchor_by_order[row.order_id] for row in t.itertuples()]]
result['actual_minute_volumes']={'rows':len(minute_volumes),'minimum':min(x['volume'] for x in minute_volumes),'zero_or_negative':[x for x in minute_volumes if x['volume']<=0],'details':minute_volumes}
for row,quote in zip(t.itertuples(),minute_volumes):quote.update(trade_id=row.trade_id,trade_volume=float(row.volume),fill_to_minute_volume_ratio=None if quote['volume']<=0 else float(row.volume)/quote['volume'])
quote_frame=pd.DataFrame(minute_volumes);valid_ratios=quote_frame.fill_to_minute_volume_ratio.dropna();aggregate=quote_frame.groupby(['vt_symbol','bar_datetime'],as_index=False).agg(trade_volume=('trade_volume','sum'),minute_volume=('volume','first'),fills=('trade_id','count'));aggregate['aggregate_ratio']=aggregate.trade_volume/aggregate.minute_volume.where(aggregate.minute_volume.gt(0));excess=aggregate.loc[aggregate.aggregate_ratio.gt(1)]
result['quote_capacity_diagnostic']={'maximum_per_fill_ratio':None if valid_ratios.empty else float(valid_ratios.max()),'per_fill_ratio_gt_1_count':int(valid_ratios.gt(1).sum()),'unique_symbol_minute_groups':len(aggregate),'maximum_aggregate_ratio':None if aggregate.aggregate_ratio.dropna().empty else float(aggregate.aggregate_ratio.max()),'aggregate_ratio_gt_1_groups':excess.to_dict('records'),'top_aggregate_ratios':aggregate.sort_values('aggregate_ratio',ascending=False).head(10).to_dict('records'),'boundary':'Positive traded minute volume and these ratios do not certify opening quote depth, capacity, or market impact. No capacity gate or fill rule was changed.'}
internal=pd.read_csv(C/'internal_equity_daily.csv');joined=daily.merge(internal,on='date',validate='one_to_one');result['internal_equity_max_residual']=float((joined.account_equity-joined.estimated_equity).abs().max())
result['traded_products']=sorted({product_symbol(x) for x in t.vt_symbol});result['traded_product_count']=len(result['traded_products'])
result['margin_exposure']={'days_positive':int(daily.total_margin_exact.gt(0).sum()),'mean_margin_equity_pct':float((daily.total_margin_exact/daily.account_equity*100).mean())}
# Reconstruct per-product closed and marked PnL. Closed pairs exclude terminal open inventories.
queues=defaultdict(deque);pairs=[]
parameters=json.loads((C/'effective_parameters.json').read_text());sizes=parameters['sizes'];slips=parameters['slippages']
for row in t.itertuples():
    sign=1 if row.direction=='多' else -1;n=float(row.volume);q=queues[row.vt_symbol]
    if row.offset=='开':q.append([sign,n,float(row.price),str(row.trade_id)]);continue
    while n>1e-8:
        direction,qty,price,entry=q[0];v=min(n,qty);pnl=(direction*(row.price-price)-2*slips[row.vt_symbol])*sizes[row.vt_symbol]*v
        pairs.append(dict(product=product_symbol(row.vt_symbol),vt_symbol=row.vt_symbol,entry=entry,exit=row.trade_id,exit_date=row.trading_date,volume=v,pnl=pnl))
        n-=v;q[0][1]-=v
        if q[0][1]<1e-8:q.popleft()
fifo=pd.DataFrame(pairs);positions['product']=positions.vt_symbol.map(product_symbol);t['product']=t.vt_symbol.map(product_symbol)
marked=positions.loc[positions.date.ge('2020-01-01')].groupby('product').net_pnl.sum();product_rows=[]
for product,g in t.groupby('product',sort=True):
    f=fifo.loc[fifo['product'].eq(product)];wins=f.loc[f.pnl>1e-8,'pnl'];losses=-f.loc[f.pnl< -1e-8,'pnl'];remaining=sum(x[1] for symbol,q in queues.items() if product_symbol(symbol)==product for x in q)
    product_rows.append(dict(product=product,trade_count=len(g),slippage=float(sum(r.volume*slips[r.vt_symbol]*sizes[r.vt_symbol] for r in g.itertuples())),net_mtm_pnl=float(marked.get(product,0)),closed_matches=len(f),wins=len(wins),losses=len(losses),flat=int(f.pnl.abs().le(1e-8).sum()),win_rate_pct=float(f.pnl.gt(1e-8).mean()*100),average_win=None if wins.empty else float(wins.mean()),average_loss_abs=None if losses.empty else float(losses.mean()),payoff_ratio=None if wins.empty or losses.empty else float(wins.mean()/losses.mean()),profit_factor=None if losses.empty else float(wins.sum()/losses.sum()),closed_net_pnl=float(f.pnl.sum()),remaining_open_lots=float(remaining)))
result['per_product']=product_rows
assert abs(sum(x['net_mtm_pnl'] for x in product_rows)-(result['F']['end_equity']-150000))<1e-7
terminal_open=[]
last_close=positions.sort_values('date').groupby('vt_symbol').tail(1).set_index('vt_symbol')
for symbol,q in queues.items():
    for direction,quantity,price,entry_id in q:
        terminal_open.append({'product':product_symbol(symbol),'vt_symbol':symbol,'direction':direction,'volume':quantity,'entry_price':price,'entry_trade_id':entry_id,'last_valuation_date':str(last_close.loc[symbol,'date']),'last_close':float(last_close.loc[symbol,'close_price']),'unrealized_gross_pnl':direction*(float(last_close.loc[symbol,'close_price'])-price)*sizes[symbol]*quantity})
result['terminal_open_positions']=terminal_open
result['closed_fifo_stats']={'matches':len(fifo),'wins':int(fifo.pnl.gt(1e-8).sum()),'losses':int(fifo.pnl.lt(-1e-8).sum()),'flat':int(fifo.pnl.abs().le(1e-8).sum()),'win_rate_pct':float(fifo.pnl.gt(1e-8).mean()*100),'average_win':float(fifo.loc[fifo.pnl>1e-8,'pnl'].mean()),'average_loss_abs':float(-fifo.loc[fifo.pnl< -1e-8,'pnl'].mean()),'payoff_ratio':float(fifo.loc[fifo.pnl>1e-8,'pnl'].mean()/-fifo.loc[fifo.pnl< -1e-8,'pnl'].mean()),'profit_factor':float(fifo.loc[fifo.pnl>1e-8,'pnl'].sum()/-fifo.loc[fifo.pnl< -1e-8,'pnl'].sum()),'remaining_open_lots':float(sum(x[1] for q in queues.values() for x in q))}
# Persist annual comparison from actual exported ledgers; no new strategy execution.
annual=[]
for label,path in [('E',OUT/'E_attempt009'),('F',C)]:
    q=pd.read_csv(path/'daily.csv');q['year']=q.date.str[:4];opening=150000.
    for year,g in q.groupby('year',sort=True):
        end=float(g.account_equity.iloc[-1]);annual.append(dict(arm=label,year=year,pnl=float(g.net_pnl.sum()),return_pct=(end/opening-1)*100,end_equity=end));opening=end
result['annual']=annual
checks={
 'positive_actual_minute_volume':not result['actual_minute_volumes']['zero_or_negative'],
 'ledger':result['F']['ledger_max_residual']<1e-7,
 'inventory_conservation':result['F']['end_inventory_from_fills_max_residual']==0 and result['F']['start_inventory_from_fills_max_residual']==0 and result['F']['position_change_from_fills_max_residual']==0 and result['F']['fill_days_missing_position_rows']==0,
 'per_symbol':result['F']['per_symbol_pnl_max_residual']<1e-7,
 'daily_cost':result['F']['daily_cost_max_residual']<1e-7,
 'signed_volume':result['F']['signed_volume_mismatch']==0,
 'daily_raw':result['F']['daily_raw_mismatches']==0,
 'held_volume':result['held_or_traded_zero_or_missing_volume']==0,
 'sha':not result['input_sha_mismatches'],
 'proof_sources':not result['source_hash_or_frozen_mismatches'],
 'proof_overlay':result['overlay_conflicting_patches']==0 and result['overlay_duplicate_minutes']==0,
 'catalog_source':not result['catalog']['source_hash_or_frozen_mismatches'] and not result['catalog']['actual_anchor_original_raw_mismatches'],
 'anchors':result['F']['bad_anchors']==0 and result['F']['execution_failures']==0 and not trade_anchor_bad,
 'weekly':not result['weekly']['weekly_raw_mismatches'],
 'flags':all(result['actual_flags'][k] is False for k in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']),
 'no_intraday_events':all(v==0 for v in result['disabled_event_rows'].values()),
 'AI_disabled':result['ai_candidates']['enabled_values']==[0] and result['ai_candidates']['allowed_values']==[1] and result['ai_candidates']['nonempty_signal_dates']==0 and result['ai_candidates']['nonzero_scores']==0 and result['ai_candidates']['nonzero_ranks']==0,
 'internal_equity':result['internal_equity_max_residual']<1e-7,
 'window':result['F']['last_day']=='2026-10-22' and result['F']['first_day']=='2020-01-02'
}
result['checks']=checks;result['verdict']='PASS_RESEARCH_ACCOUNTING_WITH_LIMITATIONS' if all(checks.values()) else 'REJECT_UNRESOLVED_AUDIT_CHECKS';result['new_financial_replays']=0
out=OUT/'stage007_independent_review';out.mkdir(exist_ok=True)
(out/'F_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['F_path','E','F','checks','verdict','closed_fifo_stats','traded_product_count','traded_products','margin_exposure']},ensure_ascii=False,indent=2))
