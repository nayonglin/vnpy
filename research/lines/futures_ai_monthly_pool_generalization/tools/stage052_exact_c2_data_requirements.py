"""Exact held-epoch C2 first-blocker requirements; no minute fill/label invention.

Replays only frozen046b selected windows. Trade dates are source-calendar labels,
not natural dates. Source reference tape is not broker execution evidence.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse,hashlib,json,math,multiprocessing as mp,sqlite3,time
import numpy as np
import pandas as pd
import stage042_coldstart_coverage as source
LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage052_exact_c2_data_requirements'
BASE=LINE/'outputs/stage046b_final'
REASON='c2_order_or_fill_unknown_without_minute_path'
_SELECTED={};_SAMPLE_KEYS=set();_META_HINTS={}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def same(a,b):return math.isclose(float(a),float(b),rel_tol=0.,abs_tol=1e-9)

def extract_window_requirements(coverage,case,result,metadata):
    """Use first-unknown state+tape only; never substitute target representative."""
    first=[]
    for path in result['paths']:
        items=[(i,t) for i,t in enumerate(path['trace']) if t['status']!='known']
        if items:first.append((path,*items[0]))
    if not first:raise ValueError('first_unknown_missing_in_replay')
    earliest=min(first,key=lambda x:x[2]['day'])[2]
    if earliest['day']!=coverage['first_unknown_day'] or '|'.join(earliest['unknown_reasons'])!=coverage['first_unknown_reason']:
        raise ValueError('first_unknown_replay_mismatch')
    rows=[]
    for path,index,trace in first:
        day=trace['day'];session=case['sessions'].get(day,{})
        r=dict(exchange=coverage['exchange'],product=coverage['product'],product_vt_symbol=coverage['product_vt_symbol'],eval_date=coverage['eval_date'],path_id=path['path_id'],source_trade_date=day,first_unknown_reason='|'.join(trace['unknown_reasons']),
          contract_epoch_id='',requirement_id='',state_id='',asof_target_epoch=session.get('target_contract',''),held_differs_from_asof_target=None,extraction_status='exact_held_state_unknown',
          direction=None,entry_price=None,stop_price=None,qty=None,layer_risk_price=None,configured_guard_tick=None,effective_fill_tick=None,source_open=None,source_high=None,source_low=None,source_close=None,
          episode_id=None,episode_signal_day=None,layer_signal_day=None,episode_initial_currency_R=None,entry_kind=None,source_day_fill_leg_count=0,source_day_reference_fill_legs_json='[]',
          source_logical_anchor_datetime='',physical_session_verified=False,broker_symbol_qualified=False,metadata_order_book_id_hint='',metadata_trading_hours_hint='',source_execution_tick_native_hint='',
          complete_trade_session_required=True,include_applicable_prior_evening_night=True,source_trade_date_is_natural_day=False,full_60d_recovery_guaranteed=False)
        if trace['unknown_reasons']!=[REASON]:r['extraction_status']='first_unknown_is_other_reason';rows.append(r);continue
        state=trace.get('state')
        if not isinstance(state,dict) or not isinstance(state.get('contract'),str) or not state['contract']:
            rows.append(r);continue
        epoch=state['contract'];r['contract_epoch_id']=epoch;r['held_differs_from_asof_target']=epoch!=r['asof_target_epoch']
        r['requirement_id']=hashlib.sha256((epoch+'|'+day).encode()).hexdigest()[:20]
        hint=metadata.get(epoch,{})
        r['metadata_order_book_id_hint']=hint['order_book_id'] if isinstance(hint.get('order_book_id'),str) else '';r['metadata_trading_hours_hint']=hint['trading_hours'] if isinstance(hint.get('trading_hours'),str) else ''
        for key in ('direction','entry_price','stop_price','qty'):r[key]=state.get(key)
        record=session.get('contracts',{}).get(epoch)
        if record is None:r['extraction_status']='exact_held_record_missing';rows.append(r);continue
        r.update(configured_guard_tick=record.get('c2_guard_tick'),effective_fill_tick=record.get('economics',{}).get('tick'),source_execution_tick_native_hint=record.get('native_for_execution_tick',''),source_logical_anchor_datetime=record.get('anchor',{}).get('execution_datetime',''))
        for key in ('open','high','low','close'):r['source_'+key]=record['bar'][key]
        current=[];alllegs=[]
        for episode in path['episodes']:
            legs=[leg for leg in episode['tape'] if leg['trading_day']==day]
            alllegs.extend(legs)
            for leg in legs:
                if leg['kind']=='open' and leg['contract']==epoch:current.append((episode,leg))
        r['source_day_fill_leg_count']=len(alllegs)
        fields=('kind','contract','trading_day','price','qty','rollover','fee_category','commission','extra_slippage','realized_gross_delta')
        r['source_day_reference_fill_legs_json']=canonical([{key:leg.get(key) for key in fields} for leg in alllegs])
        if len(current)!=1:r['extraction_status']='source_entry_leg_unidentified';rows.append(r);continue
        episode,leg=current[0]
        if not same(leg['price'],r['entry_price']) or leg['qty']!=r['qty']:
            raise ValueError('first_unknown_state_entry_leg_mismatch')
        r.update(episode_id=episode['episode_id'],episode_signal_day=episode['signal_day'],episode_initial_currency_R=None if episode['snapshot'] is None else episode['snapshot']['risk_currency'],entry_kind='roll' if leg['rollover'] else 'fresh')
        previous=path['trace'][index-1] if index else None;pending=None if previous is None else previous.get('pending')
        if pending and pending['kind']=='roll' and leg['rollover'] and pending.get('new',{}).get('contract')==epoch:r['layer_signal_day']=pending['new'].get('signal_day')
        elif pending and pending['kind']=='open' and not leg['rollover'] and pending.get('contract')==epoch:r['layer_signal_day']=pending.get('signal_day')
        else:r['extraction_status']='source_pending_origin_unidentified';rows.append(r);continue
        if r['direction'] not in ('long','short') or type(r['qty']) is not int or r['qty']<=0 or any(isinstance(r[k],bool) or r[k] is None or not math.isfinite(float(r[k])) or float(r[k])<=0 for k in ('entry_price','stop_price','configured_guard_tick','effective_fill_tick')):
            r['extraction_status']='exact_state_fields_unknown';rows.append(r);continue
        r['layer_risk_price']=(r['entry_price']-r['stop_price'])*(1 if r['direction']=='long' else -1)
        if r['layer_risk_price']<max(r['configured_guard_tick'],1e-9):raise ValueError('first_unknown_C2_guard_inconsistent')
        r['extraction_status']='exact_C2_state_identified'
        statekeys=('contract_epoch_id','source_trade_date','direction','entry_price','stop_price','qty','configured_guard_tick','effective_fill_tick','layer_signal_day','episode_signal_day','episode_initial_currency_R','entry_kind')
        r['state_id']=hashlib.sha256(canonical({k:r[k] for k in statekeys}).encode()).hexdigest()[:24]
        rows.append(r)
    return rows

def aggregate_requirements(rows):
    groups=defaultdict(list);states=defaultdict(list)
    for r in rows:
        if r['contract_epoch_id'] and r['requirement_id']:
            groups[(r['contract_epoch_id'],r['source_trade_date'])].append(r)
            if r['state_id']:states[r['state_id']].append(r)
    demands=[];variants=[]
    for (epoch,day),group in sorted(groups.items()):
        first=group[0]
        demands.append(dict(requirement_id=first['requirement_id'],contract_epoch_id=epoch,source_trade_date=day,exchange=first['exchange'],product=first['product'],metadata_order_book_id_hint=first['metadata_order_book_id_hint'],metadata_trading_hours_hint=first['metadata_trading_hours_hint'],window_path_mappings=len(group),distinct_month_windows=len({(r['product_vt_symbol'],r['eval_date']) for r in group}),state_variants=len({r['state_id'] for r in group if r['state_id']}),all_states_identified=all(r['extraction_status']=='exact_C2_state_identified' for r in group),minute_resolution='1m',complete_trade_session_required=True,include_applicable_prior_evening_night=True,known_natural_session_start='',known_natural_session_end='',physical_session_verified=False,broker_symbol_qualified=False,full_60d_recovery_guaranteed=False))
    for state_id,group in sorted(states.items()):
        first=dict(group[0]);first['window_path_mappings']=len(group);first['distinct_month_windows']=len({(r['product_vt_symbol'],r['eval_date']) for r in group});variants.append(first)
    return demands,variants

def worker(key):
    context=source.ProductCases(key);rows=[];samples=[]
    for cov in _SELECTED[key]:
        index=source._CAL.index(cov['eval_date']);summary,detail=source.summarize_case(context,index,keep_trace=True)
        for field in ('first_unknown_day','first_unknown_reason','status','path_count','known_paths','all_paths_value_known'):
            if summary[field]!=cov[field]:raise ValueError('frozen_window_changed:'+str(key)+':'+cov['eval_date']+':'+field)
        if detail is None or 'result' not in detail:raise ValueError('frozen_selected_replay_failed')
        extracted=extract_window_requirements(cov,detail['case'],detail['result'],_META_HINTS)
        if not extracted:raise ValueError('selected_window_has_no_requirement_mapping')
        rows.extend(extracted)
        samplekey=(key[0],key[1],cov['eval_date'])
        if samplekey in _SAMPLE_KEYS:samples.append(dict(coverage=cov,case_sha256=hashlib.sha256(canonical(detail['case']).encode()).hexdigest(),result=detail['result'],extracted=extracted))
    return dict(key=key,rows=rows,samples=samples,windows=len(_SELECTED[key]))

def run(workers=4):
    global _SELECTED,_SAMPLE_KEYS,_META_HINTS
    if (OUT/'summary.json').exists():raise ValueError('immutable_result_exists')
    OUT.mkdir(parents=True,exist_ok=True)
    start=now();timer=time.perf_counter();binding=json.loads((BASE/'bindings.json').read_text())
    for path,expected in binding['source_code_sha256'].items():
        if sha(path)!=expected:raise ValueError('frozen_source_changed:'+path)
    for path,key in [(source.PANEL,'panel_sha256'),(source.ECON,'economic_inventory_sha256'),(source.CALFILE,'calendar_sha256')]:
        if sha(path)!=binding[key]:raise ValueError('frozen_input_changed:'+str(path))
    before=source.DB.stat();dbidentity=dict(path=str(source.DB),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino)
    if any(dbidentity[k]!=binding['source_database'][k] for k in ('bytes','mtime_ns','inode')):raise ValueError('source_database_identity_changed')
    coverage=pd.read_csv(BASE/'monthly_coldstart_coverage.csv')
    for k in ('asof_eligible','maturity_clock_reached'):
        if not coverage[k].map(lambda v:type(v) is bool).all():raise ValueError('explicit_coverage_bool_required:'+k)
    selected=coverage.loc[coverage.asof_eligible&coverage.maturity_clock_reached&coverage.first_unknown_reason.eq(REASON)].sort_values(['exchange','product','eval_date'])
    if len(selected)!=2209:raise ValueError('frozen_selected_count_changed')
    selected_rows=json.loads(selected.to_json(orient='records'));_SELECTED=defaultdict(list)
    for r in selected_rows:_SELECTED[(r['exchange'],r['product'])].append(r)
    chosen=np.linspace(0,len(selected_rows)-1,12,dtype=int);_SAMPLE_KEYS={(selected_rows[i]['exchange'],selected_rows[i]['product'],selected_rows[i]['eval_date']) for i in chosen}
    rawdates=pd.to_datetime(np.load(source.CALFILE,allow_pickle=False).astype(str),format='%Y%m%d');source._CAL=[str(d.date()) for d in rawdates if pd.Timestamp('2010-01-01')<=d<=pd.Timestamp('2026-10-16')]
    with sqlite3.connect(source.PANEL.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');panel=pd.read_sql_query('SELECT * FROM panel ORDER BY exchange,product,eval_date',c)
    source._PANELS={key:g.to_dict('records') for key,g in panel.groupby(['exchange','product'],sort=True)}
    with sqlite3.connect(source.DB.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');raw=pd.read_sql_query('SELECT exchange,product,contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,source_id FROM daily_bars ORDER BY exchange,product,contract_epoch_id,trade_date',c)
    source._RAW={key:g for key,g in raw.groupby(['exchange','product'],sort=False)}
    source._ECON={r['contract_epoch_id']:r for r in pd.read_csv(source.ECON).to_dict('records')};_META_HINTS={k:{x:r.get(x) for x in ('order_book_id','trading_hours','exchange')} for k,r in source._ECON.items()}
    rows=[];samples=[];completed=0
    print(canonical(dict(phase='frozen_inputs_loaded',selected_windows=len(selected_rows),products=len(_SELECTED),workers=min(4,max(1,workers)),elapsed_seconds=round(time.perf_counter()-timer,2))),flush=True)
    with mp.get_context('fork').Pool(min(4,max(1,workers))) as pool:
        for result in pool.imap_unordered(worker,sorted(_SELECTED),chunksize=1):
            rows.extend(result['rows']);samples.extend(result['samples']);completed+=1
            if completed%10==0:print(canonical(dict(products_done=completed,total_products=len(_SELECTED),window_path_mappings=len(rows),elapsed_seconds=round(time.perf_counter()-timer,2))),flush=True)
    rows.sort(key=lambda r:(r['exchange'],r['product'],r['eval_date'],r['path_id']))
    if {(r['exchange'],r['product'],r['eval_date']) for r in rows}!={(r['exchange'],r['product'],r['eval_date']) for r in selected_rows}:raise ValueError('selected_window_mapping_not_preserved')
    demands,variants=aggregate_requirements(rows)
    pd.DataFrame(rows).to_csv(OUT/'window_path_state_mappings.csv',index=False)
    pd.DataFrame(demands).to_csv(OUT/'exact_contract_session_requirements.csv',index=False)
    pd.DataFrame(variants).to_csv(OUT/'distinct_state_requirements.csv',index=False)
    if len(samples)!=12:raise ValueError('fixed_trace_sample_count_changed')
    (OUT/'trace_samples').mkdir(exist_ok=False)
    for item in samples:
        c=item['coverage'];p=OUT/'trace_samples'/f"{c['exchange']}_{c['product']}_{c['eval_date']}.json";p.write_text(json.dumps(item,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for path,expected in binding['source_code_sha256'].items():
        if sha(path)!=expected:raise ValueError('source_changed_during_replay:'+path)
    after=source.DB.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('source_database_changed_during_replay')
    source_hashes={p:sha(p) for p in binding['source_code_sha256']};source_hashes.update({str(p):sha(p) for p in [BASE/'bindings.json',BASE/'monthly_coldstart_coverage.csv',source.PANEL,source.ECON,source.CALFILE,Path(__file__),Path(__file__).with_name('test_stage052_exact_c2_data_requirements.py'),LINE/'config/training_source_v1.json']})
    output_hashes={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('summary.json','PLAN.md')}
    summary=dict(started_at=start,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,selected_mature_windows=2209,replayed_windows=2209,window_path_mappings=len(rows),exact_identified_state_rows=sum(r['extraction_status']=='exact_C2_state_identified' for r in rows),extraction_status_counts=pd.Series([r['extraction_status'] for r in rows]).value_counts().to_dict(),distinct_contract_trade_sessions=len(demands),distinct_states=len(variants),products=len(_SELECTED),held_differs_from_asof_target=sum(r['held_differs_from_asof_target'] is True for r in rows),roll_entry_rows=sum(r['entry_kind']=='roll' for r in rows),fixed_trace_samples=12,sample_rule='12 evenly spaced indices across original selected windows sorted exchange/product/eval_date before replay; no outcome filtering',source_database=dbidentity,source_database_unchanged=True,source_sha256=source_hashes,output_sha256=output_hashes,model_fits=0,minute_downloads=0,minute_fills_added=0,training_labels_added=0,production_changes=0,all_60day_known_restored=False,scope='exact source-state first C2 blocker data requirements only; logical source trade dates not physical sessions',required_session='complete historical trading session including applicable prior natural evening/night; actual session/calendar remains unqualified',native_symbol='metadata order_book_id hint only, not broker qualification',unknown_handling='no representative substitution or execution fill imputation',independent_review='pending Stage053 reviewer',halfR_and_retry=False,C2_enabled=True)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(canonical({k:v for k,v in summary.items() if k not in ('source_sha256','output_sha256')}),flush=True)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args();run(args.workers)
