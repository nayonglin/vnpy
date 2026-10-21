"""Frozen DAY proxy features/intervals; no models, fills or cash simulation."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date,datetime
import csv
import gzip
import hashlib
import io
from itertools import groupby
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

OWN_FEATURES=['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
    'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MARKET_FEATURES=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing']
IDENTITIES=['event_id','product_id','product','exchange','u_date','reference_epoch','planned_execution_date','status','direction']
BAR_FIELDS=['contract_epoch_id','exchange','product','contract_yyyymm','trade_date','open','high','low','close','volume','quality_status']
VALUE_FIELDS=['gross_lower','gross_upper','proxy_lower','proxy_upper']
PROTOCOL_SHA='2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')


def valid_prices(row):
    if row is None or row.get('quality_status')!='accepted':return False
    values=[row[k] for k in ('open','high','low','close')]
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in values):return False
    return row['low']<=min(row['open'],row['close']) and row['high']>=max(row['open'],row['close']) and row['low']<=row['high']


def valid_history_bar(row):
    return valid_prices(row) and isinstance(row['volume'],(int,float)) and math.isfinite(row['volume']) and row['volume']>0


def own_features(window):
    tr=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(window,window[1:])]
    atr=math.fsum(tr)/20
    if not math.isfinite(atr) or atr<=0:return None,atr,'zero_or_nonfinite_atr'
    u=window[-1];previous=window[-2]
    try:
        values=[(u['close']-previous['close'])/atr,(u['close']-window[-6]['close'])/(math.sqrt(5)*atr),
            (u['close']-window[0]['close'])/(math.sqrt(20)*atr),(u['close']-u['open'])/atr,
            (u['high']-u['low'])/atr,(u['close']-u['low'])/(u['high']-u['low']) if u['high']>u['low'] else .5,
            (u['open']-previous['close'])/atr,(math.fsum(tr[-5:])/5)/atr,
            math.log(u['volume']/(math.fsum(b['volume'] for b in window[:-1])/20)),
            (u['close']-max(b['high'] for b in window[:-1]))/atr,atr/u['close']]
    except (ValueError,OverflowError,ZeroDivisionError):return None,atr,'nonfinite_own_features'
    if not all(math.isfinite(v) for v in values):return None,atr,'nonfinite_own_features'
    return values,atr,'ready'


def day_label(row,*,D,scope_end,atr20):
    result=dict(label_identified=0,label_state='',label_known_date='',path_ambiguous=0,
        **{k:None for k in VALUE_FIELDS})
    if not D:result['label_state']='execution_day_unknown'
    elif D>scope_end:result['label_state']='right_censored'
    elif row is None:result['label_state']='missing_D'
    elif not valid_prices(row):result['label_state']='invalid_D_prices'
    elif not math.isfinite(atr20) or atr20<=0:result['label_state']='history_unready'
    else:
        F=row['open'];R=.25*atr20;SL=F-R;PT=F+4*R
        if not all(math.isfinite(v) for v in (F,R,SL,PT)) or R<=0 or SL<=0:
            result['label_state']='nonpositive_stop'
            return result
        stop=row['low']<=SL;profit=row['high']>=PT
        if stop and profit:lower,upper=-1.,4.;state='double_touch_interval'
        elif stop:lower=upper=-1.;state='stop_only'
        elif profit:lower=upper=4.;state='profit_only'
        else:lower=upper=(row['close']-F)/R;state='day_close'
        result.update(label_identified=1,label_state=state,label_known_date=D,path_ambiguous=int(stop and profit),
            gross_lower=lower,gross_upper=upper,proxy_lower=lower-.2,proxy_upper=upper-.2)
    return result


def quantile_linear(values,q):
    at=(len(values)-1)*q;lo=int(at);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(at-lo)


def add_market_features(frame,calendar):
    frame=frame.copy();previous=dict(zip(calendar[1:],calendar))
    selected=frame.loc[frame.feature_ready.eq(1),['u_date','family_id','r1_atr']]
    if not np.isfinite(selected.r1_atr.to_numpy(dtype=float)).all():raise ValueError('ready r1 is nonfinite')
    means=selected.groupby(['u_date','family_id'],sort=False).r1_atr.mean()
    by_date={}
    for (u,family),value in means.items():by_date.setdefault(u,{})[family]=float(value)
    features=np.empty((len(frame),4),dtype=float);families=frame.family_id.to_numpy()
    for u,indexes in frame.groupby('u_date',sort=False).indices.items():
        source=by_date.get(previous.get(u,''),{});cache={}
        for index in indexes:
            own=families[index]
            if own not in cache:
                values=sorted(value for family,value in source.items() if family!=own)
                cache[own]=[quantile_linear(values,.5),sum(v>0 for v in values)/len(values),
                    quantile_linear(values,.75)-quantile_linear(values,.25),0.] if values else [0.,0.,0.,1.]
            features[index]=cache[own]
    if not np.isfinite(features).all():raise ValueError('market context nonfinite')
    for i,name in enumerate(MARKET_FEATURES):frame[name]=features[:,i]
    frame['market_lag_missing']=frame.market_lag_missing.astype('int8')
    return frame


def build_dataset(opportunities,calendar,bar_records,*,scope_end,audit_emit=None):
    if calendar!=sorted(set(calendar)) or not calendar:raise ValueError('calendar must be nonempty unique increasing')
    for d in calendar:date.fromisoformat(d)
    frame=opportunities[IDENTITIES].copy().reset_index(drop=True).fillna('')
    if frame.event_id.duplicated().any() or frame.duplicated(['product_id','u_date']).any():raise ValueError('duplicate opportunity identity')
    if not frame.u_date.isin(calendar).all() or not frame.direction.eq('long').all():raise ValueError('opportunity calendar/direction conflict')
    if not (frame['exchange']+'.'+frame['product']).eq(frame.product_id).all():raise ValueError('product identity conflict')
    successor=dict(zip(calendar,calendar[1:]));cal_index={d:i for i,d in enumerate(calendar)}
    if not frame.planned_execution_date.eq(frame.u_date.map(successor).fillna('')).all():raise ValueError('planned D differs from accepted source calendar')
    frame['family_id']=frame['exchange']+'.'+frame['product'].str.removesuffix('_F')
    n=len(frame);own=np.full((n,len(OWN_FEATURES)),np.nan);atr=np.full(n,np.nan)
    feature_ready=np.zeros(n,dtype='int8');history=np.full(n,'no_reference_observation',dtype=object)
    identified=np.zeros(n,dtype='int8');ambiguous=np.zeros(n,dtype='int8');values=np.full((n,4),np.nan)
    known=np.full(n,'',dtype=object);states=np.full(n,'no_reference_observation',dtype=object)
    observed=frame.status.eq('observed_long_research_opportunity')
    if not frame.loc[~observed,'reference_epoch'].eq('').all():raise ValueError('no-observation row has reference')
    refs=frame.loc[observed].groupby('reference_epoch',sort=False).groups
    history[observed.to_numpy()]='reference_bar_missing';states[observed.to_numpy()]='history_unready'
    raw_rows=0;seen_epochs=set();previous_epoch=''
    for epoch,group in groupby(bar_records,key=lambda r:r['contract_epoch_id']):
        if epoch in seen_epochs or epoch<previous_epoch:raise ValueError('source must be grouped by unique ordered epoch')
        seen_epochs.add(epoch);previous_epoch=epoch
        bars=[];last=''
        for raw in group:
            r=dict(raw);d=r['trade_date']
            if d>scope_end:continue
            if d not in cal_index:raise ValueError('source bar outside calendar')
            if last and d<=last:raise ValueError('duplicate or unordered same-epoch source day')
            if epoch!=r['exchange']+'.'+r['product']+'.'+str(r['contract_yyyymm']):raise ValueError('source epoch identity conflict')
            last=d;bars.append(r);raw_rows+=1
        if epoch not in refs:continue
        positions={r['trade_date']:i for i,r in enumerate(bars)}
        for index in refs[epoch]:
            u=frame.at[index,'u_date'];D=frame.at[index,'planned_execution_date'];position=positions.get(u)
            row_D=bars[positions[D]] if D in positions else None
            if position is None:state='reference_bar_missing';own_values=None;atr_value=math.nan
            else:
                if epoch.rsplit('.',1)[0]!=frame.at[index,'product_id']:raise ValueError('reference epoch/product identity conflict')
                window=bars[max(0,position-20):position+1]
                if len(window)<21:state='insufficient_same_epoch_history';own_values=None;atr_value=math.nan
                elif cal_index[window[-1]['trade_date']]-cal_index[window[0]['trade_date']]!=20:
                    state='source_calendar_gap_rewarm';own_values=None;atr_value=math.nan
                elif not all(valid_history_bar(r) for r in window):state='invalid_history_bar';own_values=None;atr_value=math.nan
                else:own_values,atr_value,state=own_features(window)
            history[index]=state;atr[index]=atr_value
            if own_values is not None:
                own[index]=own_values;feature_ready[index]=1
                label=day_label(row_D,D=D,scope_end=scope_end,atr20=atr_value)
            else:
                label=day_label(None,D=D,scope_end=scope_end,atr20=math.nan)
                if D and D<=scope_end:label['label_state']='history_unready'
            identified[index]=label['label_identified'];states[index]=label['label_state']
            known[index]=label['label_known_date'];ambiguous[index]=label['path_ambiguous']
            values[index]=[math.nan if label[k] is None else label[k] for k in VALUE_FIELDS]
            if audit_emit is not None:
                eligible=own_values is not None and row_D is not None and valid_prices(row_D)
                F=row_D['open'] if eligible else None;R=.25*atr_value if eligible else None
                audit_emit(dict(event_id=frame.at[index,'event_id'],u_date=u,reference_epoch=epoch,planned_execution_date=D,
                    atr20=atr_value if math.isfinite(atr_value) else None,ideal_entry_F=F,risk_distance=R,
                    ideal_stop=(F-R) if eligible else None,ideal_profit=(F+4*R) if eligible else None,
                    D_high=row_D['high'] if eligible else None,D_low=row_D['low'] if eligible else None,D_close=row_D['close'] if eligible else None,
                    history_state=state,label_state=label['label_state']))
    for i,name in enumerate(OWN_FEATURES):frame[name]=own[:,i]
    frame['atr20']=atr;frame['feature_ready']=feature_ready;frame['history_state']=history
    frame['label_identified']=identified;frame['label_state']=states;frame['label_known_date']=known;frame['path_ambiguous']=ambiguous
    for i,name in enumerate(VALUE_FIELDS):frame[name]=values[:,i]
    frame=add_market_features(frame,calendar)
    columns=[*IDENTITIES,'family_id','feature_ready','history_state',*OWN_FEATURES,*MARKET_FEATURES,'atr20',
        'label_identified','label_state','label_known_date','path_ambiguous',*VALUE_FIELDS]
    frame=frame[columns]
    ready=frame.feature_ready.eq(1);labeled=frame.label_identified.eq(1)
    assert len(frame)==len(opportunities) and np.isfinite(frame.loc[ready,[*OWN_FEATURES,*MARKET_FEATURES]].to_numpy()).all()
    assert frame.loc[labeled,'label_known_date'].eq(frame.loc[labeled,'planned_execution_date']).all()
    assert frame.loc[~labeled,'label_known_date'].eq('').all() and frame.loc[~labeled,VALUE_FIELDS].isna().all().all()
    assert not {'open','high','low','close','volume','ideal_entry_F'}.intersection(frame.columns)
    stats=dict(rows=len(frame),source_contract_day_rows=raw_rows,source_epochs=len(seen_epochs),observed_rows=int(observed.sum()),
        feature_ready=int(ready.sum()),label_identified=int(labeled.sum()),ready_unknown_label=int((ready&~labeled).sum()),
        ambiguous_identified=int(frame.path_ambiguous.sum()),history_states={str(k):int(v) for k,v in frame.history_state.value_counts().items()},
        label_states={str(k):int(v) for k,v in frame.label_state.value_counts().items()},
        ready_context_missing=int(frame.loc[ready,'market_lag_missing'].sum()),
        ready_dates=int(frame.loc[ready,'u_date'].nunique()),ready_families=int(frame.loc[ready,'family_id'].nunique()))
    return frame,stats


def build_from_sqlite(opportunities,calendar,db_path,*,scope_end,audit_emit=None,scope_start='2010-01-01'):
    path=Path(db_path).resolve()
    if not path.is_file():raise FileNotFoundError(path)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON');db.row_factory=sqlite3.Row
        cursor=db.execute('SELECT '+','.join(BAR_FIELDS)+' FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date',(scope_start,scope_end))
        frame,stats=build_dataset(opportunities,calendar,(dict(r) for r in cursor),scope_end=scope_end,audit_emit=audit_emit)
    stats['sql_queries']=1
    return frame,stats


def bound(item,bindings):
    path=Path(item['path']);raw=path.read_bytes()
    if not path.is_absolute() or sha(raw)!=item['sha256'] or ('bytes' in item and len(raw)!=item['bytes']):raise ValueError('bound input changed: '+str(path))
    bindings[str(path)]=dict(sha256=sha(raw),bytes=len(raw));return raw


def db_state(path):
    path=Path(path);s=path.stat()
    return dict(path=str(path.resolve()),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,
        wal_present=Path(str(path)+'-wal').exists(),shm_present=Path(str(path)+'-shm').exists())


def calendar_from_bytes(raw):
    values=np.load(io.BytesIO(raw),allow_pickle=False)
    if values.ndim!=1 or values.dtype.kind not in ('i','u'):raise ValueError('fixed source calendar must be YYYYMMDD integers')
    result=[]
    for v in values:
        s=str(int(v));d=s[:4]+'-'+s[4:6]+'-'+s[6:];date.fromisoformat(d);result.append(d)
    if result!=sorted(set(result)):raise ValueError('calendar not increasing unique')
    return result


def export_dataset(protocol_path,protocol_sha256,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    bindings={};protocol_raw=bound(dict(path=str(Path(protocol_path).resolve()),sha256=protocol_sha256),bindings)
    if protocol_sha256!=PROTOCOL_SHA:raise ValueError('only frozen Stage007 protocol accepted')
    protocol=json.loads(protocol_raw);bound(protocol['frozen_spec'],bindings)
    if (protocol['own_features']!=OWN_FEATURES or protocol['market_features']!=MARKET_FEATURES or protocol['atr_window']!=20
        or protocol['consecutive_real_bars']!=21 or protocol['stop_atr_fraction']!=.25 or protocol['take_profit_atr_fraction']!=1.
        or protocol['horizon']!='DAY' or protocol['base_cost_budget_R']!=.2):raise ValueError('frozen formula contract changed')
    manifest=json.loads(bound(protocol['inputs']['opportunity_manifest'],bindings))
    review=json.loads(bound(protocol['inputs']['opportunity_review'],bindings))
    if review['independent_review'] is not True or review['status']!='accepted_fixed_source_catalog_calendar_long_observation_only':raise ValueError('accepted 004 observation review required')
    source=json.loads(bound(protocol['inputs']['source_bindings'],bindings))
    before=db_state(source['database']['path'])
    for key in ('bytes','mtime_ns','inode','wal_present','shm_present'):
        if before[key]!=source['database'][key]:raise ValueError('inherited database stat changed: '+key)
    if before['wal_present'] or before['shm_present']:raise ValueError('database sidecar present')
    for item in source['small_bindings']:bound(item,bindings)
    calendar_raw=bound(source['calendar'],bindings);calendar=calendar_from_bytes(calendar_raw)
    panel_item=dict(path=str(Path(protocol['inputs']['opportunity_manifest']['path']).parent/'product_day_opportunities.csv.gz'),**manifest['artifacts']['product_day_opportunities.csv.gz'])
    panel_raw=bound(panel_item,bindings)
    opportunities=pd.read_csv(io.BytesIO(panel_raw),compression='gzip',usecols=IDENTITIES,dtype=str,keep_default_na=False)
    if len(opportunities)!=399252:raise ValueError('accepted full opportunity row count changed')
    audit_columns=['event_id','u_date','reference_epoch','planned_execution_date','atr20','ideal_entry_F','risk_distance','ideal_stop','ideal_profit','D_high','D_low','D_close','history_state','label_state']
    with (output/'audit_paths.csv.gz').open('xb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=audit_columns,lineterminator='\n');writer.writeheader()
                frame,counts=build_from_sqlite(opportunities,calendar,source['database']['path'],scope_end=protocol['scope'][1],
                    scope_start=protocol['scope'][0],audit_emit=writer.writerow)
    if counts['source_contract_day_rows']!=1552456:raise ValueError('source row count differs from inherited accepted scope')
    after=db_state(source['database']['path'])
    if before!=after:raise ValueError('database changed during read')
    target=output/'feature_labels.csv.gz'
    with target.open('xb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as stream:frame.to_csv(stream,index=False,float_format='%.17g',na_rep='',lineterminator='\n')
    target_raw=target.read_bytes();dataset=dict(path=str(target.resolve()),sha256=sha(target_raw),bytes=len(target_raw),rows=len(frame),columns=list(frame.columns))
    audit_path=output/'audit_paths.csv.gz';audit_raw=audit_path.read_bytes()
    year=frame.assign(year=frame.u_date.str[:4]).groupby('year').agg(rows=('event_id','size'),feature_ready=('feature_ready','sum'),label_identified=('label_identified','sum'),ambiguous=('path_ambiguous','sum')).reset_index()
    year.to_csv(output/'year_counts.csv',index=False)
    result=dict(schema='stage009_day_proxy_dataset_v1',dataset=dataset,feature_label_csv=dataset,
        protocol=dict(path=str(Path(protocol_path).resolve()),sha256=protocol_sha256,bytes=len(protocol_raw)),
        source_calendar=source['calendar'],source_calendar_scope_dates=[d for d in calendar if protocol['scope'][0]<=d<=protocol['scope'][1]],
        source_bindings=bindings,opportunity_manifest=protocol['inputs']['opportunity_manifest'],opportunity_review=protocol['inputs']['opportunity_review'],
        inherited_database_sha256=source['database']['sha256'],database_before=before,database_after=after,database_full_hash_recomputed=False,
        counts=counts,year_counts=year.to_dict('records'),own_features=OWN_FEATURES,market_features=MARKET_FEATURES,
        audit_paths=dict(path=str(audit_path.resolve()),sha256=sha(audit_raw),bytes=len(audit_raw),scope='price_diagnostics_only_not_trainer_input'),
        source_code=dict(path=str(Path(__file__).resolve()),sha256=sha(Path(__file__).read_bytes())),
        runtime=dict(executable=sys.executable,python=sys.version,numpy=np.__version__,pandas=pd.__version__,sqlite=sqlite3.sqlite_version),
        statistical_proxy_available=True,qualified_for_fixed_proxy_experiment=False,
        fixed_proxy_experiment_qualification_status='pending_independent_stage011_review',real_economic_labels_ready=False,
        financial_ready=False,label_ready=False,model_ready=False,publication_pit_certified=False,production_qualified=False,
        semantics='continuous_price_ideal_immediate_DAY_barrier_proxy_interval_with_0.2R_budget_not_actual_PnL_or_executable_labels',
        information_cutoff='own_u_close; other_family_context_u_minus_1_source_day; identified_target_known_on_D_close_date_only',
        limitations=['All 399252 rows retained; identified subset is not the full executable market.',
            'Same epoch, 21 consecutive real positive-volume source-calendar bars; no price carry or missing-day substitution.',
            'Double-touch interval is within ideal barrier model; real gap/tick/limit/fees/margin/fills are not bounded here.',
            'F deduplication only; other renamed products and sector correlation are not declared independent.',
            'Source reconstruction is inherited bounded Stage266 qualification, not historical publication PIT.'],
        model_fits=0,financial_runs=0,native_runs=0,network_calls=0)
    write_json(output/'manifest.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--protocol-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    started=datetime.now().astimezone().isoformat(timespec='seconds');began=time.monotonic()
    try:
        result=export_dataset(args.protocol,args.protocol_sha256,args.output)
        terminal=dict(schema='stage009_actual_terminal_v1',exit_code=0,started_at=started,finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),
            elapsed_seconds=time.monotonic()-began,actual_build_invocations=1,command=sys.argv,
            source_sha256=sha(Path(__file__).read_bytes()),manifest_sha256=sha((args.output/'manifest.json').read_bytes()),dataset=result['dataset'],
            counts=result['counts'],model_fits=0,financial_runs=0,network_calls=0)
        write_json(args.output/'actual_terminal.json',terminal);print(json.dumps(terminal,ensure_ascii=False,allow_nan=False))
    except BaseException as exc:
        if args.output.is_dir() and not (args.output/'actual_terminal.json').exists():
            write_json(args.output/'actual_terminal.json',dict(schema='stage009_actual_terminal_v1',exit_code=1,started_at=started,
                finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),elapsed_seconds=time.monotonic()-began,
                actual_build_invocations=1,error_type=type(exc).__name__,error=str(exc),model_fits=0,financial_runs=0))
        raise


if __name__=='__main__':main()
