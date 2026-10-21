"""Full-cohort monthly coldstart future60 conditional coverage, never training."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import sqlite3
import time
import numpy as np
import pandas as pd
import talib
from stage039_continuous_source import run_continuous_source
from stage040_daily_source_panel import history_status
from stage018_finite_path_ledger import execution

LINE=Path(__file__).resolve().parents[1];ROOT=LINE.parents[2]
PRIOR=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs'
DB=PRIOR/'stage266_clean_daily/clean_daily.sqlite'
PANEL=LINE/'outputs/stage040_daily_source_panel/daily_source_panel.sqlite'
ECON=LINE/'outputs/stage006_economic_coverage/epoch_economic_inventory.csv'
CALFILE=PRIOR/'stage265_deep_daily/rqalpha/trading_dates.npy'
OUT=LINE/'outputs/stage042_coldstart_coverage'
_RAW={};_PANELS={};_ECON={};_CAL=[];_MONTHS=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
from zoneinfo import ZoneInfo

def asof_status(rows,index):
    row=rows[index]
    if str(row['product']).endswith('_F'):return 'monthly_average_F'
    if row['exchange']=='SHFE' and str(row['product']).upper()=='FU':return 'fixed_fu'
    if not row.get('input_ready'):return 'asof_AM41_not_ready'
    if index<119:return 'past120_clock_insufficient'
    if any(not r.get('reference_epoch') for r in rows[index-119:index+1]):return 'past120_representative_missing'
    return 'eligible'

def session_signal(row):
    if not row.get('input_ready') or not row.get('reference_epoch'):return 'unknown',None
    if row.get('fresh_direction_allowed') and row.get('hardblock_status')!='known':return 'unknown',None
    if not row.get('fresh_after_hardblocks'):return 'known',None
    return 'known',dict(direction=row['signal_direction'],contract=row['reference_epoch'],qty=2,
                        stop_price=float(row['signal_stop']),signal_high=float(row['high']),signal_low=float(row['low']))

def economics_fields(row,native,day):
    result=dict(multiplier=None,tick=None,historical_validated=False)
    guard=None if row is None or pd.isna(row.get('tick_size')) else float(row['tick_size'])
    if row is not None:
        result['multiplier']=None if pd.isna(row.get('contract_multiplier')) else float(row['contract_multiplier'])
        result['tick']=None if guard is None else execution.effective_pricetick(native,day,guard)
    for name,col in [('open','open_commission_ratio'),('close','close_commission_ratio'),('close_today','close_commission_today_ratio')]:
        result[name+'_per_lot']=None;result[name+'_rate']=None
        ratio=None if row is None else row.get(col)
        if ratio is None or pd.isna(ratio):continue
        if row.get('commission_type')=='by_volume':result[name+'_per_lot']=float(ratio);result[name+'_rate']=0.
        elif row.get('commission_type')=='by_money':result[name+'_per_lot']=0.;result[name+'_rate']=float(ratio)
    return result,guard

class ProductCases:
    def __init__(self,key):
        self.key=key;self.rows=_PANELS[key];self.cache={};self.epochs={};self.errors={}
        dates={d:i for i,d in enumerate(_CAL)}
        frame=_RAW.get(key)
        if frame is not None:
            for epoch,g in frame.groupby('contract_epoch_id',sort=False):
                g=g.sort_values('trade_date')
                ds=list(g.trade_date);indices=np.array([dates.get(d,-100000) for d in ds],int)
                values=g[['open','high','low','close','volume','close_oi']].to_numpy(float)
                bars=[{k:float(r[k]) for k in ['open','high','low','close','volume']} for r in g.to_dict('records')]
                self.epochs[epoch]=(ds,indices,values,bars,{d:i for i,d in enumerate(ds)})

    def record(self,epoch,day,index):
        key=(epoch,day)
        if key in self.cache:return self.cache[key]
        if epoch not in self.epochs:self.cache[key]=None;return None
        ds,indices,values,bars,positions=self.epochs[epoch];j=positions.get(day)
        if j is None:self.cache[key]=None;return None
        a=max(0,j-40)
        status=history_status(indices[a:j+1],values[a:j+1],index)
        if status!='frozen_AM41_input_ready':self.cache[key]=None;self.errors[key]=status;return None
        history=bars[a:j+1];closes=values[a:j+1,3]
        exchange,product,yyyymm=epoch.split('.')
        native=product.lower()+yyyymm[-4:]+'.'+exchange
        economics,guard=economics_fields(_ECON.get(epoch),native,day)
        identified=guard is not None and guard>0 and economics['multiplier'] is not None and economics['multiplier']>0 and economics['tick'] is not None and economics['tick']>0
        evidence=f'daily-open-assumption:{epoch}:{day}:cleanDB-exact-epoch-source-bar'
        record=dict(bar=bars[j],history=history,history_dates=ds[a:j+1],
                    rsi_value=float(talib.RSI(closes,timeperiod=6)[-1]),ma_long_prev_value=float(closes[-21:-1].mean()),
                    anchor=dict(price=bars[j]['open'],execution_datetime=day+'T00:00:00',evidence_id=evidence,logical_bar_label_not_physical=True) if identified else None,
                    economics=economics,extra_slippage_price=0.,daily_bar_complete=True,
                    daily_completeness_basis='declared_clean_daily_bar_reference_assumption_not_session_certification',
                    minute_paths=None,minute_evidence_id=None,c2_guard_tick=guard,
                    c2_guard_tick_source_id=str(ECON)+'#'+epoch+'#tick_size:static-configuration-assumption',
                    effective_fill_tick_basis=execution.pricetick_basis(native),native_for_execution_tick=native)
        self.cache[key]=record;return record

    def case(self,index):
        end=min(index+60,len(_CAL)-1);days=_CAL[index:end+1]
        epochs=sorted({r['reference_epoch'] for r in self.rows[index:end+1] if r.get('reference_epoch')})
        sessions={};missing={}
        for i in range(index,end+1):
            row=self.rows[i];day=_CAL[i];known,signal=session_signal(row)
            if known=='unknown':missing[day]=row.get('input_status','observation_missing');continue
            contracts={}
            for epoch in epochs:
                record=self.record(epoch,day,i)
                if record is not None:contracts[epoch]=record
            sessions[day]=dict(target_contract=row['reference_epoch'],roll_qty=2,contracts=contracts,fresh_signal=signal)
        return dict(calendar=_CAL,start_day=_CAL[index],observed_through=_CAL[end],monthly_eval_days=[_CAL[end]],
                    sessions=sessions,source_definition='monthly_flat_coldstart_future60_close_sum_episode_fixed_R',
                    missing_observations=missing,diagnostic_qty_policy='fixed2 lots fresh and roll; declared research delta',
                    daily_open_anchor_policy='logical source bar label T00; no physical session certification')

def summarize_case(context,index,keep_trace=False):
    row=context.rows[index];eligibility=asof_status(context.rows,index)
    base=dict(exchange=context.key[0],product=context.key[1],product_vt_symbol=row['product_vt_symbol'],eval_date=_CAL[index],
              row_role='fixed' if eligibility=='fixed_fu' else 'monthly_average_F' if eligibility=='monthly_average_F' else 'candidate',
              asof_eligible=eligibility=='eligible',asof_status=eligibility,reference_epoch=row.get('reference_epoch',''),
              target_day=_CAL[index+60] if index+60<len(_CAL) else None,observed_through=_CAL[min(index+60,len(_CAL)-1)],
              maturity_clock_reached=index+60<len(_CAL),path_count=0,known_paths=0,all_paths_value_known=False,
              cumulative_net_r=None,cumulative_gross_r=None,net_r_min=None,net_r_max=None,episodes=0,
              status='asof_ineligible',first_unknown_day=None,first_unknown_reason=None,input_error=None,
              conditional_economics=True,training_eligible=False,net_60d_training_label=False)
    if eligibility!='eligible':return base,None
    case=context.case(index)
    try:
        result=run_continuous_source(case)
        paths=result['paths'];known=[p for p in paths if p['status']=='known' and p['cumulative_net_r'] is not None]
        allknown=len(known)==len(paths)
        nets=[p['cumulative_net_r'] for p in known];gross=[p['cumulative_gross_r'] for p in known]
        unknown=[r for p in paths for r in p['trace'] if r['status']!='known']
        first=min(unknown,key=lambda r:r['day']) if unknown else None
        base.update(path_count=len(paths),known_paths=len(known),all_paths_value_known=allknown,
                    cumulative_net_r=nets[0] if allknown and all(n==nets[0] for n in nets) else None,
                    cumulative_gross_r=gross[0] if allknown and all(n==gross[0] for n in gross) else None,
                    net_r_min=min(nets) if allknown else None,net_r_max=max(nets) if allknown else None,
                    episodes=max(len(p['episodes']) for p in paths),
                    status='immature' if not base['maturity_clock_reached'] else 'conditional_value_known' if allknown else 'trajectory_unknown',
                    first_unknown_day=None if first is None else first['day'],
                    first_unknown_reason=None if first is None else '|'.join(first['unknown_reasons']))
        return base,dict(case=case,result=result) if keep_trace else None
    except Exception as exc:
        reason=str(exc)
        base.update(status='source_execution_unknown' if reason in ['fill_not_on_declared_tick_grid','held_contract_economics_changed'] else 'input_error',
                    first_unknown_reason=reason,input_error=type(exc).__name__+':'+reason)
        return base,dict(case=case,error=base['input_error'])

def product_run(key):
    started=time.perf_counter();context=ProductCases(key);rows=[];saved_errors=set()
    for index in _MONTHS:
        row,detail=summarize_case(context,index)
        rows.append(row)
        if detail and row['input_error'] not in saved_errors:
            saved_errors.add(row['input_error']);path=OUT/'error_examples'/f'{key[0]}_{key[1]}_{_CAL[index]}.json'
            path.write_text(json.dumps(detail,ensure_ascii=False,allow_nan=False)+'\n')
    path=OUT/'checkpoints'/f'{key[0]}_{key[1]}.json'
    path.write_text(json.dumps(rows,ensure_ascii=False,allow_nan=False)+'\n')
    return dict(exchange=key[0],product=key[1],rows=len(rows),eligible=sum(r['asof_eligible'] for r in rows),
                elapsed_seconds=time.perf_counter()-started,record_cache=len(context.cache),path=str(path),sha256=sha(path))

def run(workers=4,output_path=None):
    global _RAW,_PANELS,_ECON,_CAL,_MONTHS,OUT
    if output_path is not None:OUT=Path(output_path).resolve()
    if OUT.exists():raise ValueError('immutable_output_exists')
    OUT.mkdir();(OUT/'checkpoints').mkdir();(OUT/'error_examples').mkdir();(OUT/'pilot').mkdir()
    begin=now();timer=time.perf_counter();before=DB.stat()
    dependencies=[Path(__file__),LINE/'tools/stage039_continuous_source.py',LINE/'tools/stage034_episode_driver.py',LINE/'tools/stage040_daily_source_panel.py',LINE/'tools/stage031_roll_admissibility.py',LINE/'tools/stage026_daily_exit_adapter.py',LINE/'tools/stage024_fixed_r_accounting.py',LINE/'tools/stage012_c2_reference_frontier.py',ROOT/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py']
    source_shas={str(p):sha(p) for p in dependencies}
    rawdates=pd.to_datetime(np.load(CALFILE,allow_pickle=False).astype(str),format='%Y%m%d')
    _CAL=[str(d.date()) for d in rawdates if pd.Timestamp('2010-01-01')<=d<=pd.Timestamp('2026-10-16')]
    _MONTHS=[i for i,d in enumerate(_CAL) if d<'2026-10-01' and (i==len(_CAL)-1 or _CAL[i+1][:7]!=d[:7])]
    with sqlite3.connect(PANEL.resolve().as_uri()+'?mode=ro',uri=True) as c:panel=pd.read_sql_query('SELECT * FROM panel ORDER BY exchange,product,eval_date',c)
    _PANELS={key:g.to_dict('records') for key,g in panel.groupby(['exchange','product'],sort=True)}
    assert len(_PANELS)==98 and len(_MONTHS)==201
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        raw=pd.read_sql_query('SELECT exchange,product,contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,source_id FROM daily_bars ORDER BY exchange,product,contract_epoch_id,trade_date',c)
    _RAW={key:g for key,g in raw.groupby(['exchange','product'],sort=False)}
    _ECON={r['contract_epoch_id']:r for r in pd.read_csv(ECON).to_dict('records')}
    fixed=[('SHFE','AU','2021-07'),('DCE','JM','2021-09'),('DCE','A','2018-01'),('SHFE','CU','2019-06'),('CZCE','CF','2019-12'),('DCE','M','2022-05'),('GFEX','LC','2024-11'),('SHFE','FU','2020-06'),('DCE','L_F','2021-07'),('DCE','S','2020-12'),('SHFE','AU','2026-09')]
    # Twelfth pilot is deterministically the first full-clock eligible all-observed no-fresh window, input-only selection.
    empty=None
    for key,rows in _PANELS.items():
        for index in _MONTHS:
            if index+60<len(_CAL) and asof_status(rows,index)=='eligible' and all(r['input_ready'] for r in rows[index:index+61]) and not any(r['fresh_after_hardblocks'] for r in rows[index:index+61]):empty=(key[0],key[1],_CAL[index][:7]);break
        if empty:break
    assert empty is not None;fixed.append(empty)
    pilot=[];pstart=time.perf_counter()
    for exchange,product,month in fixed:
        key=(exchange,product);assert key in _PANELS,key
        index=next(i for i in _MONTHS if _CAL[i][:7]==month)
        summary,detail=summarize_case(ProductCases(key),index,True)
        pilot.append(summary)
        (OUT/'pilot'/f'{exchange}_{product}_{month}.json').write_text(json.dumps(dict(summary=summary,detail=detail),ensure_ascii=False,allow_nan=False)+'\n')
    if any(r['status']=='input_error' for r in pilot):raise ValueError('pilot_input_error_stop_before_full_run')
    (OUT/'pilot_summary.json').write_text(json.dumps(dict(rows=pilot,elapsed_seconds=time.perf_counter()-pstart,no_signal_selection_rule='first lexicographic product/chronological eligible full-observed future61 no-fresh window; diagnostic only, fullcohort unchanged'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(pilot_rows=12,pilot_seconds=round(time.perf_counter()-pstart,2),statuses=pd.Series([r['status'] for r in pilot]).value_counts().to_dict())),flush=True)
    receipts=[]
    with mp.get_context('fork').Pool(processes=min(4,max(1,workers))) as pool:
        for r in pool.imap_unordered(product_run,list(_PANELS),chunksize=1):
            receipts.append(r)
            if len(receipts)%10==0:print(json.dumps(dict(checkpoints=len(receipts),total=98,elapsed_seconds=round(time.perf_counter()-timer,1))),flush=True)
    rows=[r for checkpoint in sorted(receipts,key=lambda r:(r['exchange'],r['product'])) for r in json.loads(Path(checkpoint['path']).read_text())]
    frame=pd.DataFrame(rows);assert len(frame)==19698 and not frame.duplicated(['exchange','product','eval_date']).any()
    frame.to_csv(OUT/'monthly_coldstart_coverage.csv',index=False)
    with sqlite3.connect(OUT/'coverage.sqlite') as c:frame.to_sql('coverage',c,index=False);c.execute('CREATE UNIQUE INDEX coverage_product_month ON coverage(exchange,product,eval_date)')
    for path,expected in source_shas.items():
        if sha(path)!=expected:raise ValueError('source_changed_during_run:'+path)
    after=DB.stat();assert (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino)
    bindings=dict(issued_at=now(),source_code_sha256=source_shas,calendar_sha256=sha(CALFILE),panel_sha256=sha(PANEL),economic_inventory_sha256=sha(ECON),
                  source_database=dict(path=str(DB),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino,full_sha_rehashed=False),checkpoints=receipts,
                  tests_sha256=sha(Path(__file__).with_name('test_stage042_coldstart_coverage.py')),matrix_sha256=sha(OUT/'monthly_coldstart_coverage.csv'))
    (OUT/'bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2)+'\n')
    summary=dict(started_at=begin,completed_at=now(),elapsed_seconds=time.perf_counter()-timer,rows=len(frame),products=98,months=201,workers=min(4,max(1,workers)),
                 asof_eligible=int(frame.asof_eligible.sum()),status_counts=frame.status.value_counts().to_dict(),asof_status_counts=frame.asof_status.value_counts().to_dict(),
                 mature_eligible=int((frame.asof_eligible&frame.maturity_clock_reached).sum()),mature_known=int((frame.asof_eligible&frame.maturity_clock_reached&frame.all_paths_value_known).sum()),
                 row_roles=frame.row_role.value_counts().to_dict(),input_errors=frame.input_error.dropna().value_counts().to_dict(),
                 driver_calls=int(frame.asof_eligible.sum())+sum(r['asof_eligible'] for r in pilot),training_labels=0,model_fits=0,downloads=0,orders=0,production_modified=False,
                 target='new isolated monthly-flat-coldstart future60 source-close sum episode unitR, not old108/official performance',historical_economics_validated=False,daily_anchor_physical_verified=False,
                 extra_slippage_stress=0,diagnostic_qty=2,halfR_and_retry=False,C2_enabled=True,database_unchanged=True,
                 limits=['all 19698 rows retained; no future coverage eligibility','flat coldstart is a declared new target, not a warmed continuous or old account source','daily open T00 logical assumption not actual session anchor','daily neither/confirm C2 reference only; stop/both execution unknown','static fees historicalFalse; no trained or production labels','wholepath unknown remains sticky; no row dropped or zero-filled','unitR sums reset on ordinary fresh entry, not currency portfolio PnL','only fixed pilot and first per-product input errors retain fulltrace; others reproducible from bound generator'])
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);parser.add_argument('--output-path');args=parser.parse_args();run(args.workers,args.output_path)
