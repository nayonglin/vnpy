"""Targeted same-source minute witnesses; reference C2 policy only, no account replay."""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
KERNEL=ROOT/'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
spec=importlib.util.spec_from_file_location('stage014_execution',KERNEL)
execution=importlib.util.module_from_spec(spec);spec.loader.exec_module(execution)
OUT=LINE/'outputs/stage014_minute_witness'
INV=LINE/'outputs/stage011_minute_coverage_inventory'
FRONTIER=LINE/'outputs/stage012_c2_reference_frontier/entry_day_c2_frontier.csv'
TARGETS=[('CZCE.CF.202005','2019-12-31','CF005.CZCE'),('DCE.JM.202201','2021-09-30','jm2201.DCE'),('DCE.M.202209','2022-05-31','m2209.DCE'),('SHFE.AU.202112','2021-07-30','au2112.SHFE')]

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def inventory_event_row(table,epoch,asof):
    rows=table.loc[table.epoch.eq(epoch)&table.eval_date.eq(asof)]
    if len(rows)!=1:raise ValueError('inventory_event_key_not_unique')
    return rows.iloc[0].to_dict()

def audit_source(frame,expected,event):
    """Reject missing/conflicted inputs before invoking the bound pure kernel."""
    f=frame.copy();f['bar_datetime']=pd.to_datetime(f.bar_datetime)
    f=f.sort_values('bar_datetime').reset_index(drop=True)
    result=dict(observed_minutes=len(f),expected_minutes=len(expected),missing_minutes=len(set(expected)-set(f.bar_datetime)),
                unexpected_minutes=len(set(f.bar_datetime)-set(expected)),real_tick_order_proven=False,
                canonical_production_trade_verified=False,not_a_60d_label=True,reference_only=True)
    if f.bar_datetime.duplicated().any():return {**result,'status':'duplicate_minute'}
    if result['missing_minutes']:return {**result,'status':'incomplete_grid'}
    if result['unexpected_minutes']:return {**result,'status':'unexpected_session_minutes'}
    values=f[['open','high','low','close']].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values<=0).any() or
        f.low.gt(f[['open','close']].min(axis=1)).any() or f.high.lt(f[['open','close']].max(axis=1)).any()):
        return {**result,'status':'invalid_ohlc'}
    aggregate=dict(open=float(f.open.iloc[0]),high=float(f.high.max()),low=float(f.low.min()),close=float(f.close.iloc[-1]))
    result['aggregate_ohlc']=aggregate
    if not all(np.isclose(aggregate[k],float(event['daily_'+k]),rtol=0,atol=1e-8) for k in aggregate):
        return {**result,'status':'daily_ohlc_mismatch'}
    if not np.isclose(float(f.open.iloc[0]),event['entry_reference_price'],rtol=0,atol=1e-8):
        return {**result,'status':'entry_open_mismatch'}
    long=event['direction']=='long';sign=1 if long else -1
    signed=sign*(float(event['entry_reference_price'])-float(event['stop']))
    if not np.isfinite(signed) or signed<=0:return {**result,'status':'invalid_signed_risk'}
    tick=float(event['tick'])
    if not np.isfinite(tick) or tick<=0:return {**result,'status':'unknown_configured_tick'}
    if signed<tick:return {**result,'status':'c2_subtick_guard_inactive'}
    try:
        index,note=execution.first_stop(f,float(event['stop']),float(event['confirm']),long=long)
        result.update(kernel_index=int(index),kernel_note=note)
        if index>=0:
            fill,fill_note=execution.stop_fill(f.iloc[index],float(event['stop']),tick,buy=not long)
            result.update(outcome='c2_stop',reference_fill_price=fill,fill_note=fill_note,
                          reference_trigger_minute=f.bar_datetime.iloc[index].isoformat())
        else:
            result['outcome']='no_trigger' if note=='no_trigger' else 'confirmation_disarms_c2'
    except ValueError as exc:
        return {**result,'status':'kernel_rejected','error':str(exc)}
    return {**result,'status':'reference_policy_resolved'}

def project(path,events):
    """One bounded column scan per file; no provider merging."""
    header=pd.read_csv(path,nrows=0).columns.tolist()
    required=['vt_symbol','bar_datetime','open','high','low','close']
    if not set(required)<=set(header):raise ValueError(f'projection_columns_absent:{path}')
    cols=required+(['minute_source'] if 'minute_source' in header else [])
    matched={e['event_id']:[] for e in events}
    symbols={e['native'].casefold() for e in events}
    for chunk in pd.read_csv(path,usecols=cols,chunksize=100000):
        chunk=chunk.loc[chunk.vt_symbol.astype(str).str.casefold().isin(symbols)].copy()
        if chunk.empty:continue
        chunk['bar_datetime']=pd.to_datetime(chunk.bar_datetime).map(execution.local_timestamp)
        for e in events:
            grid=e.get('expected')
            if grid is None:continue
            part=chunk.loc[chunk.vt_symbol.astype(str).str.casefold().eq(e['native'].casefold()) &
                           chunk.bar_datetime.ge(grid[0]) & chunk.bar_datetime.le(grid[-1])]
            if not part.empty:matched[e['event_id']].append(part)
    return {key:pd.concat(v,ignore_index=True) if v else pd.DataFrame(columns=cols) for key,v in matched.items()}

def run():
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('output_already_populated')
    OUT.mkdir(parents=True,exist_ok=True)
    raw=np.load(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/trading_dates.npy',allow_pickle=False)
    calendar=pd.DatetimeIndex(pd.to_datetime(raw.astype(str),format='%Y%m%d'))
    frontier=pd.read_csv(FRONTIER)
    inventory=pd.read_csv(INV/'event_next_day_coverage.csv')
    events=[];summaries=[]
    for epoch,asof,native in TARGETS:
        rows=frontier.loc[frontier.reference_epoch.eq(epoch)&frontier.eval_date.eq(asof)]
        assert len(rows)==1
        row=rows.iloc[0];assert row.daily_case=='both_unidentified'
        inv=inventory_event_row(inventory,epoch,asof)
        assert str(inv['any_target_date_evidence'])=='True'
        e=dict(event_id=epoch+'@'+asof,native=native,reference_epoch=epoch,eval_date=asof,
               reference_execution_date=row.reference_execution_date,direction=row.direction,
               entry_reference_price=float(row.reference_entry_price),stop=float(row.stop_threshold),
               confirm=float(row.confirm_threshold),tick=float(row.configured_tick),
               daily_open=float(row.daily_open),daily_high=float(row.daily_high),daily_low=float(row.daily_low),daily_close=float(row.daily_close))
        try:e['expected']=execution.session_minutes(native,row.reference_execution_date,calendar)
        except ValueError as exc:summaries.append(dict(event_id=e['event_id'],status='unsupported_session',error=str(exc)))
        events.append(e)
    scan=pd.read_csv(INV/'scanned_timestamp_source_files.csv')
    paths=[]
    natives=[x[2].split('.')[0].casefold() for x in TARGETS]
    for _,r in scan.iterrows():
        if r.kind=='stage861' or any(Path(r.path).name.casefold().startswith(x+'_') for x in natives):paths.append(Path(r.path))
    for r in json.loads((INV/'additional_matching_cache_headers.json').read_text()):
        if any(Path(r['path']).name.casefold().startswith(x+'_') for x in natives):paths.append(Path(r['path']))
    paths=list(dict.fromkeys(paths))
    audit_rows=[];sources=[]
    for path in paths:
        before=path.stat();projected=project(path,events);after=path.stat()
        assert (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino)
        binding=dict(source_path=str(path),bytes=before.st_size,mtime_ns=before.st_mtime_ns,inode=before.st_ino,
                     source_full_sha256=digest(path) if before.st_size<5_000_000 else None,
                     full_payload_rehashed=before.st_size<5_000_000,columns_projected='vt_symbol,bar_datetime,open,high,low,close,minute_source_if_present')
        sources.append(binding)
        for e in events:
            if e.get('expected') is None:continue
            f=projected[e['event_id']]
            if f.empty:groups=[('__file_no_target_rows__',f)]
            elif 'minute_source' in f:
                f=f.copy();f['minute_source']=f.minute_source.fillna('__unspecified__').astype(str)
                groups=list(f.groupby('minute_source',dropna=False,sort=True))
            else:groups=[('__file_provider_unspecified__',f)]
            for provider,part in groups:
                n=len(audit_rows);evidence=OUT/f'projected_source_{n:03d}.csv'
                part.to_csv(evidence,index=False)
                try:result=audit_source(part,e['expected'],e)
                except Exception as exc:result=dict(status='audit_exception',error=repr(exc))
                audit_rows.append(dict(event_id=e['event_id'],source_path=str(path),source_component=provider,
                                       evidence_file=evidence.name,evidence_sha256=digest(evidence),**result))
    for e in events:
        if e.get('expected') is None:continue
        rows=[r for r in audit_rows if r['event_id']==e['event_id']]
        resolved=[r for r in rows if r['status']=='reference_policy_resolved']
        outcomes=sorted({r['outcome'] for r in resolved})
        summaries.append(dict(event_id=e['event_id'],sources_audited=len(rows),resolved_sources=len(resolved),
                              outcome_conflict=len(outcomes)>1,possible_reference_outcomes=outcomes,
                              status='conflicting_resolved_sources' if len(outcomes)>1 else 'reference_policy_resolved' if outcomes else 'no_valid_same_source_witness',
                              unknown_source_reasons=sorted({r['status'] for r in rows if r['status']!='reference_policy_resolved'}),
                              reference_only=True,not_real_tick_order=True,not_a_trade=True,not_a_60d_label=True))
    pd.DataFrame(audit_rows).to_csv(OUT/'source_audit.csv',index=False)
    pd.DataFrame(summaries).to_csv(OUT/'event_summary.csv',index=False)
    serial_events=[{k:([x.isoformat() for x in v] if k=='expected' else v) for k,v in e.items()} for e in events]
    report=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),kernel_sha256=digest(KERNEL),
                script_sha256=digest(__file__),stage012_sha256=digest(FRONTIER),inventory_sha256=digest(INV/'event_next_day_coverage.csv'),
                training_profile_sha256=digest(LINE/'config/training_source_v1.json'),events=serial_events,sources=sources,
                event_summary=summaries,reference_policy_resolved_events=sum(x['status']=='reference_policy_resolved' for x in summaries),
                all_events=4,financial_replays=0,model_fits=0,downloads=0,
                limits=['same file component only; no cross provider stitching','session helper scope not expanded','minute adverse ties are reference policy, not tick path proof','not a full source replay or 60d economic label','source price/volume provenance and historical tradability not certified'])
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(events=summaries,sources=len(sources)),ensure_ascii=False))

if __name__=='__main__':run()
