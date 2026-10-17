"""One batch of accepted local completed bars; append-only research coverage."""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
OUTPUT=LINE/'outputs/stage002_local_minute_overlay'
PROJECT=ROOT/'examples/portfolio_backtesting'
SOURCE=PROJECT/'downloaded_futures/tqsdk_stage491_covered_key_full_session_backfill'
CACHE=PROJECT/'backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'
MAPPING=PROJECT/'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
OLD=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3'
A0=LINE/'outputs/stage001_first_screen/A0_attempt2'
PROTOCOL=LINE/'stages/20261017_2250_stage002_local_minute_coverage_protocol.md'
EXPECTED_BASE='5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189'
VALUES=['open','high','low','close','volume','open_oi','close_oi']
FORMAL19={'AP.CZCE','CF.CZCE','FG.CZCE','MA.CZCE','OI.CZCE','SA.CZCE','SH.CZCE','SM.CZCE',
    'jm.DCE','lh.DCE','lc.GFEX','si.GFEX','au.SHFE','cu.SHFE','fu.SHFE','hc.SHFE','rb.SHFE','ru.SHFE','sp.SHFE'}
sys.path.insert(0,str(PROJECT))
from qmt_roll_intraday_execution import session_minutes,local_timestamp


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v)for v in value]
    if isinstance(value,(Path,datetime,pd.Timestamp)):return str(value)
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float)and not np.isfinite(value):return None
    return value


def write_json(path,value):Path(path).write_text(json.dumps(safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def normal_times(frame):
    result=frame.copy()
    times=pd.to_datetime(result.bar_datetime,errors='raise')
    if times.dt.tz is not None:times=times.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
    result['bar_datetime']=times
    return result


def session_grid(symbol,day,calendar):
    # The original helper uses only current and preceding actual exchange date.
    # Supply precisely those dates to avoid reparsing a 16-year calendar per day.
    calendar=pd.DatetimeIndex(calendar)
    day=local_timestamp(day).normalize()
    position=calendar.get_indexer([day])[0]
    if position<0:raise ValueError('source_calendar_day_missing')
    return session_minutes(symbol,day,calendar[max(0,position-1):position+1])


def read_database_daily(path,symbol):
    native,exchange=symbol.rsplit('.',1)
    path=Path(path).resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)as db:
        db.execute('PRAGMA query_only=ON')
        result=pd.read_sql_query('SELECT substr(datetime,1,10) AS trade_date,open_price AS open,high_price AS high,low_price AS low,close_price AS close,volume,open_interest AS close_oi FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND datetime>=? AND datetime<? ORDER BY datetime',db,
            params=[native,exchange,'d','2020-01-01','2026-10-15'])
    result['open_oi']=np.nan
    return result


def validate_session(source,expected,daily,base):
    selected=source.loc[source.bar_datetime.isin(expected)].copy().sort_values('bar_datetime')
    audit=dict(status='quarantined',reason='',expected_minutes=len(expected),actual_rows=len(selected),
        missing_minutes=len(expected.difference(selected.bar_datetime)),new_minutes=0,base_overlap_minutes=0,
        daily_open_oi_check='unknown',aggregate={},daily_mismatch_fields=[])
    empty=selected.iloc[0:0].copy()
    if selected.bar_datetime.duplicated().any():audit['reason']='duplicate_minute';return empty,audit
    if len(selected)!=len(expected)or audit['missing_minutes']:
        audit['reason']='incomplete_session';return empty,audit
    numeric=selected[VALUES].apply(pd.to_numeric,errors='coerce')
    prices=numeric[['open','high','low','close']]
    valid=np.isfinite(numeric.to_numpy()).all() and bool((prices>0).all().all())
    valid=valid and bool((numeric[['volume','open_oi','close_oi']]>=0).all().all())
    valid=valid and bool((numeric.low<=numeric[['open','close']].min(axis=1)).all())
    valid=valid and bool((numeric.high>=numeric[['open','close']].max(axis=1)).all())
    if not valid:audit['reason']='invalid_minute_ohlcvoi';return empty,audit
    aggregate=dict(open=float(numeric.open.iloc[0]),high=float(numeric.high.max()),
        low=float(numeric.low.min()),close=float(numeric.close.iloc[-1]),volume=float(numeric.volume.sum()),
        open_oi=float(numeric.open_oi.iloc[0]),close_oi=float(numeric.close_oi.iloc[-1]))
    audit['aggregate']=aggregate
    required=['open','high','low','close','volume','close_oi']
    if daily is None or any(not np.isfinite(float(daily.get(k,np.nan)))for k in required):
        audit['reason']='daily_missing_or_invalid';return empty,audit
    if np.isfinite(float(daily.get('open_oi',np.nan))):required.append('open_oi');audit['daily_open_oi_check']='checked'
    mismatches=[k for k in required if not np.isclose(aggregate[k],float(daily[k]),rtol=1e-12,atol=1e-8)]
    if mismatches:audit['reason']='daily_aggregate_mismatch';audit['daily_mismatch_fields']=mismatches;return empty,audit
    overlap=base.loc[base.bar_datetime.isin(expected)].copy().sort_values('bar_datetime')
    if overlap.bar_datetime.duplicated().any():raise ValueError('duplicate_base_key')
    audit['base_overlap_minutes']=len(overlap)
    if len(overlap):
        comparable=selected.set_index('bar_datetime').loc[overlap.bar_datetime,VALUES].to_numpy(dtype=float)
        existing=overlap[VALUES].to_numpy(dtype=float)
        if not np.isclose(comparable,existing,rtol=1e-12,atol=1e-8,equal_nan=True).all():
            audit['reason']='base_overlap_conflict';return empty,audit
    added=selected.loc[~selected.bar_datetime.isin(overlap.bar_datetime)].copy()
    audit.update(status='accepted',reason='complete_daily_matched_base_preserved',new_minutes=len(added))
    return added,audit


def minute_keys(frame):
    return pd.MultiIndex.from_arrays([frame.vt_symbol.astype(str),pd.to_datetime(frame.bar_datetime)],names=['vt_symbol','bar_datetime'])


def merge_frames_preserving_base(base,overlay):
    base=normal_times(base);overlay=normal_times(overlay)
    if minute_keys(base).has_duplicates or minute_keys(overlay).has_duplicates:raise ValueError('duplicate_minute_merge_key')
    if len(minute_keys(base).intersection(minute_keys(overlay))):raise ValueError('overlay_contains_base_key')
    added=overlay.copy()
    added['bar_date']=added.bar_datetime.dt.normalize()
    added['minute_source']='stage002_accepted_local_completed'
    return pd.concat([base,added],ignore_index=True,sort=False).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)


def prove_read_disjointness(overlay,anchors,scans,calendar):
    used=set()
    for row in anchors.itertuples():used.add((str(row.vt_symbol),local_timestamp(row.expected_start)))
    for row in scans.itertuples():
        grid=session_grid(str(row.vt_symbol),row.trading_date,calendar)
        requested=grid[grid>=local_timestamp(row.requested_start)]
        if hasattr(row,'expected_bar_count')and len(requested)!=int(row.expected_bar_count):raise ValueError('a0_recorded_scan_count_mismatch')
        used.update((str(row.vt_symbol),stamp)for stamp in requested)
    added={(str(row.vt_symbol),pd.Timestamp(row.bar_datetime))for row in overlay[['vt_symbol','bar_datetime']].itertuples()}
    intersection=sorted(added & used)
    return dict(path_equivalent=not intersection,intersection_count=len(intersection),
        anchor_request_rows=len(anchors),scan_request_rows=len(scans),distinct_actual_read_keys=len(used),
        added_keys=len(added),intersection_examples=[(x,str(t))for x,t in intersection[:10]],
        reasoning='Only absent base keys are appended; every recorded A0 canonical anchor and requested entry-session minute is disjoint from added keys.')


@contextmanager
def temporary_minute_overlay(s901,overlay):
    original=s901._load_stage861_full_minute_bars
    names=('_FULL_MINUTE_BY_SYMBOL_CACHE','_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS','_LAST_MINUTE_AUDIT')
    state={name:getattr(s901,name)for name in names}
    def load(symbols):
        base=original(symbols)
        selected=overlay.loc[overlay.vt_symbol.astype(str).isin(symbols)].copy()
        return merge_frames_preserving_base(base,selected)
    s901._load_stage861_full_minute_bars=load
    s901._FULL_MINUTE_BY_SYMBOL_CACHE=None;s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS=set()
    try:yield
    finally:
        s901._load_stage861_full_minute_bars=original
        for name,value in state.items():setattr(s901,name,value)


def build_overlay(attempt=1):
    output=OUTPUT if attempt==1 else OUTPUT/f'attempt{attempt}'
    if attempt<1:raise ValueError('invalid_overlay_attempt')
    previous=OUTPUT if attempt==2 else OUTPUT/f'attempt{attempt-1}'
    if attempt>1 and (not(previous/'build_failure.json').is_file()or(previous/'summary.json').exists()):raise ValueError('previous_overlay_attempt_not_failed')
    if output.exists():raise FileExistsError('existing_overlay_attempt_refusing_rebuild')
    expected=json.loads((OLD/'input_manifest.json').read_text())
    paths=sorted(SOURCE.rglob('*_completed_minute_backtest.csv'))
    if len(paths)!=134:raise ValueError('stage491_fixed_source_inventory_changed')
    inventory=[]
    for number,path in enumerate(paths):
        relative=str(path.relative_to(ROOT));digest=sha256(path)
        if expected.get(relative)!=digest:raise ValueError(f'unaccepted_local_completed_source:{relative}')
        inventory.append(dict(source_id=f's491_{number:03d}',path=str(path),sha256=digest,bytes=path.stat().st_size))
    if sha256(CACHE)!=EXPECTED_BASE:raise ValueError('accepted_base_cache_changed')
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'attempt_started.json',dict(started_at=datetime.now().astimezone(),attempt=attempt,financial_replays=0,downloads=0))
    started=time.monotonic();source_inputs={str(CACHE):EXPECTED_BASE,str(MAPPING):sha256(MAPPING),str(PROTOCOL):sha256(PROTOCOL),
        str(OLD/'input_manifest.json'):sha256(OLD/'input_manifest.json'),str(Path(__file__)):sha256(Path(__file__))}
    try:
        mapping=pd.read_csv(MAPPING,usecols=['date'])
        calendar=pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
        database=ROOT/'.vntrader/database.db'
        database_sha=sha256(database)
        if expected.get(str(database.relative_to(ROOT)))!=database_sha:raise ValueError('accepted_primary_daily_database_changed')
        if Path(str(database)+'-wal').exists()and Path(str(database)+'-wal').stat().st_size:raise ValueError('unexpected_primary_database_wal')
        source_inputs[str(database)]=database_sha
        base=normal_times(pd.read_csv(CACHE,usecols=['vt_symbol','bar_datetime',*VALUES]))
        if minute_keys(base).has_duplicates:raise ValueError('duplicate_original_cache_key')
        base_by={symbol:group for symbol,group in base.groupby('vt_symbol',sort=False)}
        accepted_sessions=[];sessions=[];daily_manifest=[]
        for number,source in enumerate(inventory):
            path=Path(source['path']);native=path.name.removesuffix('_completed_minute_backtest.csv')
            exchange=path.parent.name;symbol=f'{native}.{exchange}'
            product=f'{re.sub("[0-9]+$","",native)}.{exchange}'
            if product not in FORMAL19:raise ValueError(f'source_outside_fixed_formal19:{symbol}')
            raw=normal_times(pd.read_csv(path));raw['source_row_number']=np.arange(len(raw))+2
            if set(raw.vt_symbol.astype(str))!={symbol}:raise ValueError(f'source_contract_identity_mismatch:{symbol}')
            daily_path=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/f'{native}.csv'
            if daily_path.exists():
                daily_digest=sha256(daily_path)
                if expected.get(str(daily_path.relative_to(ROOT)))!=daily_digest:raise ValueError(f'accepted_daily_source_changed:{symbol}')
                source_inputs[str(daily_path)]=daily_digest
                daily=pd.read_csv(daily_path);daily_kind='accepted_exact_symbol_daily_csv'
            else:
                daily_path=database;daily_digest=database_sha
                daily=read_database_daily(database,symbol);daily_kind='accepted_exact_symbol_database_daily_open_oi_unknown'
            daily['trade_date']=pd.to_datetime(daily.trade_date).dt.normalize()
            natural=pd.DatetimeIndex(raw.bar_datetime.dt.normalize().unique())
            candidates=daily.loc[daily.trade_date.between('2020-01-01','2026-10-14')]
            date_counts=candidates.trade_date.value_counts()
            cache_rows=base_by.get(symbol,base.iloc[0:0])
            for day in sorted(candidates.trade_date.unique()):
                day=pd.Timestamp(day);position=calendar.get_indexer([day])[0]
                if position<0:continue
                previous=calendar[max(0,position-1)]
                if not (day in natural or previous in natural or previous+pd.Timedelta(days=1)in natural):continue
                grid=session_grid(symbol,day,calendar)
                daily_row=None if date_counts[day]!=1 else candidates.loc[candidates.trade_date.eq(day)].iloc[0].to_dict()
                added,audit=validate_session(raw,grid,daily_row,cache_rows)
                audit.update(vt_symbol=symbol,product_vt_symbol=product,trading_date=str(day.date()),
                    source_id=source['source_id'],source_path=str(path),source_sha256=source['sha256'],
                    session_first=str(grid[0]),session_last=str(grid[-1]),daily_source_path=str(daily_path),daily_source_sha256=daily_digest,daily_source_kind=daily_kind)
                audit['aggregate']=json.dumps(audit['aggregate'],sort_keys=True)
                audit['daily_mismatch_fields']=','.join(audit['daily_mismatch_fields'])
                sessions.append(audit)
                if len(added):
                    added=added.copy();added['trading_date']=str(day.date());added['source_id']=source['source_id'];added['source_sha256']=source['sha256']
                    accepted_sessions.append(added)
            daily_manifest.append(dict(path=str(daily_path),sha256=daily_digest,vt_symbol=symbol,kind=daily_kind))
            if (number+1)%20==0:print(f'local completed sources {number+1}/{len(inventory)}; sessions={len(sessions)}',flush=True)
        overlay=pd.concat(accepted_sessions,ignore_index=True)if accepted_sessions else base.iloc[0:0].copy()
        if minute_keys(overlay).has_duplicates:raise ValueError('duplicate_accepted_overlay_key')
        if len(minute_keys(base).intersection(minute_keys(overlay))):raise ValueError('overlay_not_disjoint_from_base')
        anchors_path=A0/'execution_anchor_requests.csv';scans_path=A0/'minute_scan_requests.csv'
        anchors=pd.read_csv(anchors_path);scans=pd.read_csv(scans_path)
        source_inputs[str(anchors_path)]=sha256(anchors_path);source_inputs[str(scans_path)]=sha256(scans_path)
        equality=prove_read_disjointness(overlay,anchors,scans,calendar)
        if not equality['path_equivalent']:raise ValueError('overlay_changes_previously_consumed_A0_keys')
        # Strict A0 already proves each recorded key existed. Recheck membership
        # without reconstructing or rerunning its financial path.
        oldkeys=set()
        for row in anchors.itertuples():oldkeys.add((str(row.vt_symbol),local_timestamp(row.expected_start)))
        for row in scans.itertuples():
            grid=session_grid(str(row.vt_symbol),row.trading_date,calendar)
            oldkeys.update((str(row.vt_symbol),stamp)for stamp in grid[grid>=local_timestamp(row.requested_start)])
        base_index=minute_keys(base)
        missing_old=sum(key not in base_index for key in oldkeys)
        equality['original_read_keys_missing_in_base']=missing_old
        if missing_old:raise ValueError('a0_consumed_key_missing_from_original_base')
        changed=[p for p,h in source_inputs.items()if sha256(p)!=h]
        changed.extend(source['path']for source in inventory if sha256(source['path'])!=source['sha256'])
        if changed:raise ValueError(f'inputs_mutated_during_overlay_build:{changed}')
        columns=['vt_symbol','tq_symbol','bar_datetime',*VALUES,'trading_date','source_id','source_sha256','source_row_number']
        for name in columns:
            if name not in overlay:overlay[name]=pd.Series(dtype=object)
        overlay=overlay[columns].sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
        overlay.to_csv(output/'overlay.csv',index=False,encoding='utf-8-sig')
        table=pd.DataFrame(sessions)
        table.to_csv(output/'session_manifest.csv',index=False,encoding='utf-8-sig')
        table.loc[table.status.ne('accepted')].to_csv(output/'quarantine.csv',index=False,encoding='utf-8-sig')
        write_json(output/'source_manifest.json',dict(sources=inventory,daily_sources=daily_manifest,input_sha256=source_inputs))
        write_json(output/'a0_path_equivalence.json',equality)
        summary=dict(status='completed_local_overlay_pending_independent_review',financial_replays=0,downloads=0,
            base_cache_sha256=EXPECTED_BASE,base_cache_unchanged=True,base_rows=len(base),
            source_family='Stage491 completed-row only',source_files=len(inventory),source_bytes=sum(x['bytes']for x in inventory),
            candidate_sessions=len(table),accepted_sessions=int(table.status.eq('accepted').sum()),
            quarantined_sessions=int(table.status.ne('accepted').sum()),quarantine_reasons=dict(Counter(table.loc[table.status.ne('accepted'),'reason'])),
            added_minutes=len(overlay),new_key_intersection_with_base=0,accepted_overlap_minutes=int(table.loc[table.status.eq('accepted'),'base_overlap_minutes'].sum()),
            added_contracts=int(overlay.vt_symbol.nunique()),a0_path_equivalence=equality,
            elapsed_seconds=time.monotonic()-started,attempt=attempt,protocol_sha256=source_inputs[str(PROTOCOL)],
            builder_sha256=source_inputs[str(Path(__file__))],overlay_sha256=sha256(output/'overlay.csv'),
            session_manifest_sha256=sha256(output/'session_manifest.csv'),source_manifest_sha256=sha256(output/'source_manifest.json'),
            production_qualified=False,order_api_calls=0,cancel_api_calls=0,all_inputs_unchanged=True,
            limitations=['This batch certifies available completed sessions, not every potential future strategy path. Strict unknown sessions still fail closed.'])
        write_json(output/'summary.json',summary)
        print(json.dumps(safe(summary),ensure_ascii=False),flush=True)
    except Exception as error:
        write_json(output/'build_failure.json',dict(status='failed_no_accepted_overlay',attempt=attempt,error=repr(error),financial_replays=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true',required=True);parser.add_argument('--attempt',type=int,default=1);args=parser.parse_args()
    build_overlay(args.attempt)
