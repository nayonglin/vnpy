"""One authorized historical snapshot, never a receiver, fit or cash runner.

Actual load_snapshot is gated by an exact root source authorization. Its single
cache load/economics load/day-data SELECT are intentionally not performed by
the author. Pure warmup helpers accept synthetic arrays without actual inputs.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import numpy as np

TOOLS=Path(__file__).resolve().parent
SNAPSHOT_DATE='2026-10-16'
CORE_SHA='8728cb5730c775c973322ea6f030ed1200f5bb931fd5c448f85e26c415ca35d6'
QUERY=('SELECT contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,'
       'quality_status,source_id,source_locator FROM daily_bars '
       'WHERE trade_date=? ORDER BY contract_epoch_id')
BAR_NAMES=('open','high','low','close','volume')
CACHE_KEYS=('days','values','accepted','valid','N','low20','run')


def load_core():
    path=TOOLS/'stage320_causal_forward_core.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=CORE_SHA:
        raise ValueError('accepted320 core changed')
    spec=importlib.util.spec_from_file_location('stage326_accepted320',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _number(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def _safe(value):
    if isinstance(value,dict): return {str(k):_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_safe(v) for v in value]
    if isinstance(value,np.ndarray): return _safe(value.tolist())
    if isinstance(value,np.generic): return _safe(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value


def _state_at(s,j,*,history=True,close_oi=None):
    state=dict(schema='stage320_wilder_state_v1',last_seen=None,last_day=None,
        last_close=None,N=None,seed=0.,run=0,lows=[],history=[])
    if j<0: return state
    state['last_seen']=int(s.days[j])
    if bool(s.valid[j]):
        run=int(s.run[j]); begin=j-run+1
        if run<1 or begin<0 or int(s.days[j]-s.days[begin])!=run-1:
            raise ValueError('cached valid run/source-calendar mismatch')
        seed=0.;previous=None
        for k in range(begin,min(j+1,begin+20)):
            if not s.valid[k]: raise ValueError('cached run contains invalid seed bar')
            O,H,L,C,V=map(float,s.values[k])
            seed+=H-L if previous is None else max(H-L,abs(H-previous),abs(L-previous))
            previous=C
        lows=[]
        for k in range(max(begin,j-19),j+1):
            d=int(s.days[k]);L=float(s.values[k,2])
            while lows and lows[-1][1]>=L: lows.pop()
            lows.append([d,L])
        if run>=20 and (not math.isfinite(float(s.N[j])) or float(s.low20[j])!=lows[0][1]):
            raise ValueError('cached Wilder/low20 checkpoint inconsistency')
        state.update(last_day=int(s.days[j]),last_close=float(s.values[j,3]),
                     N=_number(s.N[j]),seed=seed,run=run,lows=lows)
    elif int(s.run[j])!=0:
        raise ValueError('invalid cached bar has nonzero run')
    if history:
        for k in range(max(0,j-20),j+1):
            state['history'].append(dict(day=int(s.days[k]),values=[_number(v) for v in s.values[k]],
                valid=bool(s.valid[k]),N=_number(s.N[k]),low20=_number(s.low20[k]),run=int(s.run[k]),
                close_oi=_number(close_oi) if k==j else None))
    return state


def warmup_epoch(epoch,series,u_index,*,close_oi=None,core=None):
    """Use cached N verbatim; reconstruct seed/queues, never replay-reseed N."""
    core=core or load_core()
    s=SimpleNamespace(**series) if isinstance(series,dict) else series
    j=int(np.searchsorted(s.days,u_index))
    if j>=len(s.days) or s.days[j]!=u_index:
        raise ValueError('no exact current bar; stale state cannot be carried to u')
    state=core.WilderState.from_dict(_state_at(s,j,close_oi=close_oi))
    begin=max(0,j-20)
    evidence=dict(epoch=epoch,u_index=int(u_index),
        checkpoint_before_window=_state_at(s,begin-1,history=False),tail=[],
        cache_reference=dict(N=_number(s.N[j]),low20=_number(s.low20[j]),run=int(s.run[j])))
    for k in range(begin,j+1):
        evidence['tail'].append(dict(day=int(s.days[k]),values=[_number(v) for v in s.values[k]],
            accepted=bool(s.accepted[k]),valid=bool(s.valid[k]),cached_N=_number(s.N[k]),
            cached_low20=_number(s.low20[k]),cached_run=int(s.run[k]),
            close_oi=_number(close_oi) if k==j else None))
    evidence['final_state']=state.to_dict()
    return state,evidence


class SnapshotMarket:
    """Bounded arrays only: no lookup may carry an earlier quote forward."""
    def __init__(self,series,dates): self.series=series;self.dates=list(dates)

    def bar(self,epoch,k):
        s=self.series.get(epoch)
        if s is None:return None
        j=int(np.searchsorted(s.days,k))
        if j>=len(s.days) or s.days[j]!=k or not s.valid[j]:return None
        return {name:float(v) for name,v in zip(BAR_NAMES,s.values[j])}

    def indicator(self,epoch,k):
        s=self.series.get(epoch);j=int(np.searchsorted(s.days,k)) if s is not None else -1
        if j<0 or j>=len(s.days) or s.days[j]!=k or not s.valid[j]:
            return dict(N=math.nan,low20=math.nan,run_length=0,high55_before=math.nan)
        return dict(N=float(s.N[j]),low20=float(s.low20[j]),run_length=int(s.run[j]),high55_before=math.nan)


def assemble_snapshot(series,dates,economics,products,current_rows,*,snapshot_date=SNAPSHOT_DATE,core=None):
    """Pure array join used by the authorized loader and the sole tiny group."""
    core=core or load_core();dates=list(dates)
    if dates!=sorted(set(dates)) or snapshot_date not in dates:raise ValueError('source calendar/date mismatch')
    u=dates.index(snapshot_date);current={}
    for r in current_rows:
        if r['trade_date']!=snapshot_date or r['contract_epoch_id'] in current:
            raise ValueError('same-day SQL identity duplicate/date mismatch')
        current[r['contract_epoch_id']]=r
    arrays={};forward_series={};states={};inventory=[];evidence=[];expected=set()
    for epoch,raw in sorted(series.items()):
        s=SimpleNamespace(**raw) if isinstance(raw,dict) else raw
        n=int(np.searchsorted(s.days,u,side='right'))
        inventory.append(dict(epoch=epoch,product_id=epoch.rsplit('.',1)[0],rows=len(s.days),
            last_index=int(s.days[n-1]) if n else None,last_date=dates[int(s.days[n-1])] if n else None,
            has_current_bar=bool(n and s.days[n-1]==u)))
        begin=max(0,n-21)
        tail={k:np.asarray(getattr(s,k))[begin:n].copy() for k in CACHE_KEYS}
        tail['close_oi']=np.full(n-begin,np.nan)
        if n and s.days[n-1]==u:
            expected.add(epoch)
            if epoch not in current:raise ValueError('current cache row absent from same-day SQL')
            r=current[epoch];wanted=np.asarray([r[k] for k in BAR_NAMES],float)
            if (not np.array_equal(wanted,np.asarray(s.values[n-1],float),equal_nan=True)
                    or bool(s.accepted[n-1])!=(r['quality_status']=='accepted')):
                raise ValueError('same-day SQL/cache OHLCV/quality mismatch')
            oi=_number(r['close_oi']);tail['close_oi'][-1]=oi if oi is not None else np.nan
            state,audit=warmup_epoch(epoch,s,u,close_oi=oi,core=core)
            states[epoch]=state.to_dict();forward_series[epoch]=state;evidence.append(audit)
        else:
            forward_series[epoch]=SimpleNamespace(**tail)
        arrays[epoch]=SimpleNamespace(**tail)
    if set(current)!=expected:raise ValueError('same-day SQL/cache epoch population mismatch')
    D_context=(dict(confirmed=True,D_index=u+1,D_date=dates[u+1],proof='bound_original_source_calendar')
               if u+1<len(dates) else dict(confirmed=False,D_index=None,D_date=None,proof='no_next_session_in_bound_source_calendar'))
    products=sorted(products);counts=Counter(e.rsplit('.',1)[0] for e in current)
    accepted=Counter(e.rsplit('.',1)[0] for e,r in current.items() if r['quality_status']=='accepted')
    product_states=[dict(product_id=p,current_rows=counts[p],accepted_quality_rows=accepted[p],
        status='observed_current_rows' if counts[p] else 'no_current_observation') for p in products]
    return dict(schema='stage326_historical_snapshot_v1',development_only=True,frozen_at=None,
        u_date=snapshot_date,u_index=u,dates=dates,economics=economics,products=products,
        series_by_epoch=forward_series,warmup_state=states,market=SnapshotMarket(arrays,dates),
        D_context=D_context,clock=dict(source_completed_at=None,D_open_at=None),
        product_states=product_states,_inventory=inventory,_warmup_evidence=evidence,
        _current_rows=list(current.values()))


def _stat(path):
    p=Path(path).resolve();s=p.stat()
    return dict(path=str(p),bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
                wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())


def _check_stat(binding):
    got=_stat(binding['path'])
    for key in ('path','bytes','inode','mtime_ns','wal_present','shm_present'):
        if key in binding and binding[key]!=got[key]:raise ValueError('source stat changed '+key)
    ex=binding.get('stat_expectation',{})
    for k,want in ex.items():
        if {'st_size':got['bytes'],'st_ino':got['inode'],'st_mtime_ns':got['mtime_ns']}[k]!=want:
            raise ValueError('source stat expectation changed '+k)
    return got


def _bound_small(binding):
    _check_stat(binding);raw=Path(binding['path']).read_bytes()
    if len(raw)>100000 or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('small binding mismatch '+binding['path'])
    return raw


def _write(path,value):
    with Path(path).open('x') as f:json.dump(_safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def _binding(path):
    p=Path(path);raw=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _jsonl(path,rows):
    with gzip.open(path,'xt',encoding='utf-8',compresslevel=1) as f:
        for row in rows:f.write(json.dumps(_safe(row),ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    return _binding(path)


def load_snapshot(authorization,*,output,core=None):
    """Root-only once-read path. No actual source is opened before exact gate.

    authorization is a root JSON path or the exact decoded object; schema,
    source bundle, source inputs, fixed date, development-only and budgets are
    checked. The caller owns journal receipts; this is never historical PIT.
    """
    auth=(json.loads(Path(authorization).read_text()) if isinstance(authorization,(str,Path)) else dict(authorization))
    if (auth.get('schema')!='stage326_historical_snapshot_authorization_v1' or auth.get('authorized') is not True
            or auth.get('snapshot_date')!=SNAPSHOT_DATE or auth.get('development_only') is not True
            or auth.get('read_budget')!=dict(cache_loads=1,economics_loads=1,day_data_selects=1)):
        raise ValueError('exact root historical source authorization required')
    bundle=json.loads(_bound_small(auth['source_bundle']))
    for b in bundle['sources']:_bound_small(b)
    declared=json.loads(_bound_small(bundle['input_bindings']))
    inputs=auth['inputs']
    if inputs!=declared['inputs']:raise ValueError('authorized input bindings differ from frozen326')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh snapshot output required')
    before={k:_check_stat(v) for k,v in inputs.items()}
    out.mkdir(parents=True)
    counts=dict(native_cache_loads=0,economic_projection_loads=0,day_data_SELECT=0,schema_queries=0)
    receipt=dict(schema='stage326_historical_snapshot_source_receipt_v1',status='started',
        snapshot_date=SNAPSHOT_DATE,development_only=True,frozen_at=None,read_counts=counts,
        inputs=inputs,source_before=before,database_rehashed=False,large_files_rehashed=False)
    _write(out/'source_started.json',receipt)
    try:
        meta=json.loads(_bound_small(inputs['cache_manifest']))
        if (meta['schema']!='stage132_native_store_recovery_cache_v1' or meta['native_epochs']!=9520
                or meta['native_rows']!=1552456):raise ValueError('original132 cache metadata mismatch')
        for k in ('path','bytes','sha256'):
            if meta['file'][k]!=inputs['native_cache'][k]:raise ValueError('cache file identity mismatch')
        for k in ('path','bytes','sha256','inode','mtime_ns'):
            if meta['database'][k]!=inputs['database'][k]:raise ValueError('database/cache lineage mismatch')
        calendar_raw=_bound_small(inputs['calendar'])
        a=np.load(io.BytesIO(calendar_raw),allow_pickle=False)
        dates=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in a]
               if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
        if len(dates)!=5587 or dates!=sorted(set(dates)) or SNAPSHOT_DATE not in dates:
            raise ValueError('original source calendar mismatch')
        counts['native_cache_loads']+=1
        with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
            epochs=z['epochs'].tolist();offsets=z['offsets'];flat={k:z[k] for k in CACHE_KEYS}
        if (len(epochs)!=9520 or len(set(epochs))!=9520 or len(offsets)!=9521 or offsets[0]!=0
                or offsets[-1]!=1552456 or np.any(np.diff(offsets)<=0)
                or any(len(v)!=1552456 for v in flat.values())):raise ValueError('cache flat shape mismatch')
        u=dates.index(SNAPSHOT_DATE)
        if int(np.max(flat['days']))!=u:raise ValueError('cache last day is not fixed snapshot date')
        series={e:{k:a[int(offsets[i]):int(offsets[i+1])] for k,a in flat.items()} for i,e in enumerate(epochs)}
        products=sorted({e.rsplit('.',1)[0] for e in epochs})
        roster=list(csv.DictReader(io.StringIO(_bound_small(inputs['roster']).decode())))
        roster_products=[r['product_id'] for r in roster]
        if (len(products)!=98 or len({p.removesuffix('_F') for p in products})!=95
                or len(roster_products)!=98 or set(roster_products)!=set(products)):
            raise ValueError('original complete98/95 domain mismatch')
        _bound_small(inputs['unit_contract'])
        counts['economic_projection_loads']+=1
        with Path(inputs['economics']['path']).open() as f:economics=json.load(f)['instruments']
        counts['day_data_SELECT']+=1
        with sqlite3.connect(Path(inputs['database']['path']).resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            db.row_factory=sqlite3.Row
            current=[dict(r) for r in db.execute(QUERY,(SNAPSHOT_DATE,))]
        snap=assemble_snapshot(series,dates,economics,products,current,core=core)
        snap['model']=json.loads(_bound_small(inputs['model']))
        snap['scaler']=json.loads(_bound_small(inputs['scaler']))
        artifacts=dict(current_rows=_jsonl(out/'current_rows.jsonl.gz',snap.pop('_current_rows')),
            warmup_evidence=_jsonl(out/'warmup_evidence.jsonl.gz',snap.pop('_warmup_evidence')),
            epoch_inventory=_jsonl(out/'epoch_inventory.jsonl.gz',snap.pop('_inventory')))
        after={k:_stat(v['path']) for k,v in inputs.items()}
        if before!=after:raise ValueError('source changed during one-shot snapshot load')
        receipt.update(status='completed',source_after=after,source_stat_unchanged=True,
            same_day_SQL_rows=len(current),current_epoch_count=len(snap['warmup_state']),
            current_SQL_cache_population_and_OHLCV_quality_match=True,products=98,families=95,
            product_states=snap['product_states'],artifacts=artifacts,D_context=snap['D_context'],
            clock=snap['clock'],first_publication_time='unknown',source_completed_at=None,
            local_loaded_at=datetime.now(timezone.utc).isoformat(),
            OI_semantics='current exact normalized326 database close_oi; all earlier warmup OI unknown, never0',
            budget_complete=counts==dict(native_cache_loads=1,economic_projection_loads=1,day_data_SELECT=1,schema_queries=0))
        _write(out/'source_receipt.json',receipt)
        snap.update(source_receipt=dict(receipt,binding=_binding(out/'source_receipt.json')),
            source='accepted132_cache_and_same_day326_SQL',
            version=inputs['native_cache']['sha256']+':'+artifacts['current_rows']['sha256'],
            received_at=receipt['local_loaded_at'],completed_at=None)
        return snap
    except Exception as exc:
        receipt.update(status='failed',error_type=type(exc).__name__,error=str(exc),
                       source_after={k:_stat(v['path']) for k,v in inputs.items()})
        _write(out/'source_failed.json',receipt)
        exc.source_receipt=receipt
        raise
