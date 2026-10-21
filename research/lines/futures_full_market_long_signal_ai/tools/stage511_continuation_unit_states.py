"""Causal unit-opportunity prefixes under the accepted131/157 price policy.

Import is pure.  Actual source construction is an explicit CLI operation and
requires a root510 frozen protocol and a fresh output directory.  Unit paths
exclude account occupancy, quantity, margin and account-risk reductions.
Post-close states and future execution observations are separate outputs.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def positive(value):
    return finite(value) and float(value) > 0


COSTS = {
    'base': dict(fee_min=2., fee_bps=.0001, slip_bps=.0001, slip_ticks=1),
    'stress': dict(fee_min=6., fee_bps=.0003, slip_bps=.0003, slip_ticks=3),
}


def execution_quote(reference, econ, scenario, side):
    """Accepted042 Decimal quote arithmetic, with explicit unknown status."""
    empty = dict(quote_state=None, fill_price=None, fee_per_lot=None,
                 slippage_per_lot=None, contract_multiplier=econ.get('contract_multiplier'),
                 tickized=int(positive(econ.get('tick_size'))))
    if not positive(reference):
        return dict(empty, quote_state='reference_unknown_or_nonpositive')
    if not positive(econ.get('contract_multiplier')):
        return dict(empty, quote_state='multiplier_unknown_or_nonpositive')
    s = COSTS[scenario]
    ref = Decimal(str(reference))
    tick = econ.get('tick_size')
    slip = abs(ref) * Decimal(str(s['slip_bps']))
    if positive(tick):
        slip = max(slip, Decimal(str(tick)) * s['slip_ticks'])
    raw = ref + slip if side == 'BUY' else ref - slip
    if positive(tick):
        td = Decimal(str(tick))
        raw = (raw / td).to_integral_value(
            rounding=ROUND_CEILING if side == 'BUY' else ROUND_FLOOR) * td
    fill = float(raw)
    if not positive(fill):
        return dict(empty, quote_state='nonpositive_adverse_fill')
    multiplier = float(econ['contract_multiplier'])
    return dict(empty, quote_state='observed_research_quote', fill_price=fill,
        fee_per_lot=max(s['fee_min'],abs(fill)*multiplier*s['fee_bps']),
        slippage_per_lot=abs(fill-float(reference))*multiplier)


def sell_quote(reference, econ, scenario):
    return execution_quote(reference, econ, scenario, 'SELL')


def capacity(volume, lot):
    if not finite(volume) or float(volume)<0 or not positive(lot) or not float(lot).is_integer():
        return None, None, 'execution_capacity_unknown'
    lot = int(lot)
    gross = int((Decimal(str(volume))/100/lot).to_integral_value(
        rounding=ROUND_FLOOR))*lot
    entry = (gross//(2*lot))*lot
    return gross, entry, ('known_roundtrip_capacity' if entry>=lot
                          else 'capacity_below_one_roundtrip')


def qualified(econ):
    return bool(econ.get('economics_status')=='exact_epoch_metadata_snapshot'
        and positive(econ.get('contract_multiplier'))
        and positive(econ.get('round_lot'))
        and float(econ['round_lot']).is_integer())


def lifecycle(epoch, econ, calendar):
    month = epoch.rsplit('.',1)[-1]
    if len(month)!=6 or not month.isdigit() or not 1<=int(month[4:])<=12:
        raise ValueError('complete YYYYMM identity required')
    candidates = [month[:4]+'-'+month[4:]+'-01']
    for field in ('known_lifecycle_exit_boundary','nominal_month_first_date',
                  'maturity_date','de_listed_date'):
        value = econ.get(field)
        if isinstance(value,str) and len(value)>=10 and value[:10]>='1900-01-01':
            candidates.append(value[:10])
    target = min(candidates)
    return bisect.bisect_left(calendar,target), target


def calendar_boundary(epoch, calendar, sample_end):
    """Exact156 nominal prior-month rule; never clip unavailable K to end."""
    month = epoch.rsplit('.',1)[-1]
    if len(month)!=6 or not month.isdigit() or not 1<=int(month[4:])<=12:
        raise ValueError('complete YYYYMM identity required')
    year,m = int(month[:4]),int(month[4:])
    year,m = (year-1,12) if m==1 else (year,m-1)
    target = f'{year:04d}-{m:02d}-01'
    if target<calendar[0]:
        k,day,state = None,None,'before_calendar_blocked'
    else:
        j = bisect.bisect_left(calendar,target)
        k,day,state = ((None,None,'after_calendar_pending') if j==len(calendar)
                       else (j,calendar[j],'in_calendar'))
    return dict(K_target_date=target,K_index=k,K_date=day,K_state=state,
        K_after_sample_end=day>sample_end if day is not None else target>sample_end)


class EpochBars:
    """Explicit bound132 arrays; no SQL, database stat or implicit protocol I/O."""
    def __init__(self, series, end_index):
        self.s = series
        self.end = end_index
        self.positions = {int(k):j for j,k in enumerate(series['days'])}
        self.legal_days = [int(k) for k,v in zip(series['days'],series['valid'])
                           if v and int(k)<=end_index]

    def __call__(self,k):
        j = self.positions.get(k)
        if j is None or k>self.end or not self.s['valid'][j]:
            return None
        s = self.s
        O,H,L,C,V = (float(v) for v in s['values'][j])
        prior = self.positions.get(k-1)
        previous = (float(s['values'][prior,3]) if prior is not None
                    and s['valid'][prior] else None)
        return dict(open=O,high=H,low=L,close=C,volume=V,
            N=float(s['N'][j]),low20=float(s['low20'][j]),
            run=int(s['run'][j]),previous_close=previous)

    def next_open(self,k):
        j = bisect.bisect_left(self.legal_days,k)
        if j==len(self.legal_days):
            return None
        day = self.legal_days[j]
        return day,float(self.s['values'][self.positions[day],0])


def anchor_request(anchor, current_reference, next_day, expiry, existing=None):
    """Exact131 priority; the immutable u anchor need not be held epoch."""
    if next_day >= expiry:
        return 'lifecycle_exit'
    if existing:
        return existing
    if not current_reference:
        return 'observation_exit_requested'
    if current_reference != anchor:
        return 'liquidity_reference_changed'
    return None


def stop_reference(bar, boundary):
    if bar['open'] <= boundary:
        return float(bar['open']), 'gap_stop'
    if bar['low'] <= boundary:
        return float(boundary), 'stop_boundary'
    return None, None


def _get_bar(bars, k):
    return bars(k) if callable(bars) else bars.get(k)


def unit_path(action, bars, canonical, end_index):
    """Advance one offered action without looking ahead to form any state.

    ``bars`` supplies accepted legal bar + contemporaneous indicators or None.
    ``canonical`` supplies the full mother-grid identity, not selected signals.
    A second, label-only pass records the earliest legal execution open for
    every voluntary request. It never changes state existence/riskset flags.
    """
    u = int(action['u_index'])
    D = u + 1
    states = []
    summary = dict(action_id=action['action_id'],
        participation_state=None, terminal_state='not_entered',
        entry_index=None, entry_reference=None, N_u=action.get('N_u'),
        SL0=None, R0=None, exit_index=None, exit_reference=None,
        terminal_reason=None, exit_available_phase=None,
        state_count=0, riskset_count=0, stale_count=0)
    result = dict(summary=summary, states=states, execution_observations=[])
    if not int(action['u_action_eligible']):
        summary['participation_state'] = 'u_ineligible'
        return result
    k_index = action.get('K_index')
    if action.get('K_state') == 'before_calendar_blocked' or (
            k_index is not None and D >= int(k_index)):
        summary['participation_state'] = 'D_not_before_K'
        return result
    expiry = int(action['source_lifecycle_index'])
    if k_index is not None:
        expiry = min(expiry, int(k_index))
    if D >= expiry or D < int(action.get('listed_index', 0)):
        summary['participation_state'] = 'lifecycle_entry_rejected'
        return result
    if action.get('economics_qualified', True) is False:
        summary['participation_state'] = 'instrument_economics_unqualified'
        return result
    if D > end_index:
        summary['participation_state'] = 'intent_right_censored'
        return result
    entry = _get_bar(bars, D)
    if entry is None:
        summary['participation_state'] = 'entry_execution_unknown'
        return result
    F = float(entry['open'])
    N_u = float(action['N_u'])
    R0 = .25 * N_u
    SL0 = F - R0
    if F <= float(action['low20_u']):
        summary['participation_state'] = 'stale_breakout_cancel_at_open'
        return result
    if SL0 <= 0 or not positive(N_u):
        summary['participation_state'] = 'invalid_initial_risk_cancel'
        return result
    summary.update(participation_state='entered', entry_index=D,
                   entry_reference=F, SL0=SL0, R0=R0)
    boundary = max(SL0, float(action['low20_u']))
    force = None
    mark = F
    stale_days = 0
    deferred = False
    last_valid_index = D
    for k in range(D, end_index+1):
        bar = entry if k == D else _get_bar(bars, k)
        boundary_in = boundary
        previous_mark = mark
        force_in = force
        deferred_in = deferred
        if bar is None:
            deferred = True
            force = 'research_deferred_liquidation'
            stale_days += 1
            mark_state = 'stale'
        else:
            reason = 'research_deferred_liquidation' if deferred else force
            if reason:
                reference = float(bar['open'])
            else:
                reference, reason = stop_reference(bar, boundary)
            if reference is not None:
                summary.update(terminal_state='closed_complete_bar_model',
                    exit_index=k, exit_reference=reference,
                    terminal_reason=reason,
                    exit_available_phase='intraday' if reason == 'stop_boundary' else 'open')
                break
            mark = float(bar['close'])
            last_valid_index = k
            mark_state = 'native_close'
            stale_days = 0
            # Match131: max(SL0, own low20), not a monotone trailing max.
            boundary = max(SL0, float(bar['low20']))
            force = anchor_request(action['anchor_epoch'], canonical.get(k),
                                   k+1, expiry, force)
        raw = {} if bar is None else bar
        state = dict(action_id=action['action_id'], t_index=k,
            entry_index=D, entry_reference=F, N_u=N_u, R0=R0, SL0=SL0,
            age_source_days=k-D+1, boundary_in=boundary_in,
            boundary_next=boundary, previous_mark=previous_mark,
            force_in=force_in, deferred_in=int(deferred_in),
            mark=mark, mark_state=mark_state,
            last_valid_index=last_valid_index,
            stale_days=stale_days, deferred=int(deferred), force_next=force,
            canonical_reference=canonical.get(k, ''),
            canonical_matches_anchor=int(canonical.get(k, '') == action['anchor_epoch']),
            effective_lifecycle_index=expiry,
            lifecycle_remaining_source_days=expiry-k,
            K_remaining_source_days=None if k_index is None else int(k_index)-k,
            open=raw.get('open'), high=raw.get('high'), low=raw.get('low'),
            close=raw.get('close'), volume=raw.get('volume'),
            N_t=raw.get('N'), low20_t=raw.get('low20'), history_run=raw.get('run'),
            previous_close=raw.get('previous_close'),
            current_native_valid=int(bar is not None),
            riskset=int(bar is not None and not force),
            next_planned_index=k+1)
        states.append(state)
    else:
        summary['terminal_state'] = ('stale_open_unresolved' if deferred
                                      else 'open_right_censored')
    summary.update(state_count=len(states),
        riskset_count=sum(s['riskset'] for s in states),
        stale_count=sum(s['mark_state'] == 'stale' for s in states))
    # Future open observations are isolated and must not be merged into X.
    # Real native adapters index legal days once per epoch.  Do not scan the
    # remaining whole calendar for every overlapping action/request.
    if hasattr(bars, 'next_open'):
        next_open = bars.next_open
    else:
        legal_days = sorted(k for k, b in bars.items()
                            if b is not None and k <= end_index)
        def next_open(k):
            j = bisect.bisect_left(legal_days, k)
            if j == len(legal_days):
                return None
            day = legal_days[j]
            return day, float(bars[day]['open'])
    for s in states:
        if not s['riskset']:
            continue
        planned = s['t_index']+1
        observed = next_open(planned)
        result['execution_observations'].append(dict(
            action_id=action['action_id'], t_index=s['t_index'],
            planned_index=planned,
            exit_index=None if observed is None else observed[0],
            reference=None if observed is None else observed[1],
            state='pending_no_legal_open' if observed is None else
                  'observed_next_open' if observed[0] == planned else
                  'observed_deferred_first_legal_open',
            available_phase=None if observed is None else 'open'))
    return result


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value,dict):
        return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [clean(v) for v in value]
    if isinstance(value,np.generic):
        value=value.item()
    if isinstance(value,float) and not math.isfinite(value):
        return None
    return value


def write_json(path,value):
    with Path(path).open('x') as f:
        json.dump(clean(value),f,ensure_ascii=False,sort_keys=True,
                  indent=2,allow_nan=False)
        f.write('\n')


def binding(path):
    path=Path(path).resolve()
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(b,role,receipt):
    before=Path(b['path']).stat()
    raw=Path(b['path']).read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    after=Path(b['path']).stat()
    if len(raw)!=b['bytes'] or digest!=b['sha256']:
        raise ValueError('input binding changed: '+role)
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(
            after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('input changed during unique read: '+role)
    receipt[role]=dict(binding=b,physical_reads=1,bytes_read=len(raw),
        sha_verified_during_unique_read=True)
    return raw


def selected_rows(raw,fields):
    """Excluded outcome columns are neither requested nor numerically parsed."""
    for chunk in pd.read_csv(io.BytesIO(raw),compression='gzip',
            usecols=fields,dtype=str,keep_default_na=False,chunksize=100000):
        for values in chunk[fields].itertuples(index=False,name=None):
            yield dict(zip(fields,values))


class _HashSink:
    def __init__(self,f):
        self.f=f
        self.digest=hashlib.sha256()
        self.bytes=0
    def write(self,data):
        n=self.f.write(data)
        self.digest.update(data[:n]);self.bytes+=n
        return n
    def flush(self):
        return self.f.flush()


class CsvSink:
    """Hash newly produced compressed bytes while writing; no output re-read."""
    def __init__(self,path,fields):
        self.path=Path(path).resolve();self.fields=fields;self.rows=0
        self.f=self.path.open('xb');self.h=_HashSink(self.f)
        self.gz=gzip.GzipFile(filename='',fileobj=self.h,mode='wb',mtime=0,
                              compresslevel=1)
        self.text=io.TextIOWrapper(self.gz,newline='')
        self.writer=csv.writer(self.text)
        self.writer.writerow(fields)
        self.closed=False
    def row(self,row):
        values=[]
        for key in self.fields:
            value=row.get(key)
            if value is None or isinstance(value,(float,np.floating)) and not math.isfinite(value):
                value=''
            elif isinstance(value,(bool,np.bool_)):
                value=int(value)
            values.append(value)
        self.writer.writerow(values);self.rows+=1
    def close(self):
        if not self.closed:
            self.text.close();self.f.close();self.closed=True
        return dict(path=str(self.path),bytes=self.h.bytes,
                    sha256=self.h.digest.hexdigest(),rows=self.rows)


META_FIELDS=['sequence_index','action_id','mother_sequence_index','mother_event_id',
    'product_id','family_id','reference_epoch','anchor_epoch','u_date','u_index',
    'D_index','u_action_eligible','u_ineligibility_reason','family_hash_group']
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date',
    'u_index','reference_epoch','family_hash_group','child_count',
    'eligible_child_count','nochild']
CAUSAL_FIELDS=META_FIELDS+['D_date','N_u','low20_u','u_close','u_history_run',
    'u_native_valid','u_gross_capacity_qty','entry_capacity_qty','u_capacity_state',
    'source_lifecycle_index','source_lifecycle_target_date','listed_date',
    'listed_index','economics_qualified','economics_status','contract_multiplier',
    'tick_size','round_lot','future_info_scope','K_target_date','K_index','K_date',
    'K_state','K_after_sample_end','effective_lifecycle_index']
SUMMARY_FIELDS=CAUSAL_FIELDS+['participation_state','terminal_state',
    'entry_index','entry_date','entry_reference','SL0','R0',
    'exit_index','exit_date','exit_reference','terminal_reason',
    'exit_available_phase','state_count','riskset_count','stale_count',
    'base_entry_quote_state','stress_entry_quote_state']
STATE_FIELDS=['sequence_index','action_id','product_id','family_id','reference_epoch',
    'anchor_epoch','family_hash_group','u_index','u_date','D_index','D_date',
    't_index','t_date','entry_index','entry_date','entry_reference','N_u','R0','SL0',
    'age_source_days','boundary_in','boundary_next','previous_mark','force_in',
    'deferred_in','mark','mark_state','stale_days','deferred','force_next',
    'last_valid_index',
    'canonical_reference','canonical_matches_anchor','source_lifecycle_index',
    'source_lifecycle_target_date','effective_lifecycle_index',
    'lifecycle_remaining_source_days','K_target_date','K_index','K_date','K_state',
    'K_remaining_source_days','open','high','low','close','volume','N_t','low20_t',
    'history_run','previous_close','current_native_valid','current_gross_capacity_qty',
    'current_next_entry_capacity_qty','current_capacity_state','riskset',
    'state_values_complete','next_planned_index','next_planned_date',
    'base_entry_quote_state','stress_entry_quote_state']
QUOTE_FIELDS=['quote_state','fill_price','fee_per_lot','slippage_per_lot','tickized']
OBS_COMMON=['sequence_index','action_id','product_id','family_id','reference_epoch',
    'contract_multiplier','tick_size','round_lot','economics_status','future_info_scope']
TERMINAL_FIELDS=OBS_COMMON+['entry_index','entry_date','entry_reference',
    'terminal_state','terminal_reason','exit_index','exit_date','exit_reference',
    'available_at','available_phase','terminal_bar_open','terminal_bar_high',
    'terminal_bar_low','terminal_bar_close','terminal_bar_volume','terminal_bar_valid']+[
    f'{cost}_{side}_{field}' for cost in COSTS
    for side in ('entry_BUY','entry_SELL_estimate','terminal_SELL') for field in QUOTE_FIELDS]
VOLUNTARY_FIELDS=OBS_COMMON+['t_index','t_date','planned_index','planned_date',
    'exit_index','exit_date','reference','state','available_at','available_phase']+[
    f'{cost}_SELL_{field}' for cost in COSTS for field in QUOTE_FIELDS]


def _day(calendar,k):
    return calendar[k] if k is not None and 0<=k<len(calendar) else None


def quote_fields(prefix,reference,econ,side):
    result={}
    for cost in COSTS:
        quote=execution_quote(reference,econ,cost,side)
        for key in QUOTE_FIELDS:
            result[f'{cost}_{prefix}_{key}']=quote[key]
    return result


def load_native(raw,end_index,domain):
    """No call to old132 restore: arrays/calendar are already explicit inputs."""
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets']
        flat={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
    rows=int(offsets[-1])
    if len(epochs)!=domain['native_epochs'] or rows!=domain['native_rows']:
        raise ValueError('native full accepted domain differs')
    if offsets[0]!=0 or len(offsets)!=len(epochs)+1 or np.any(np.diff(offsets)<0):
        raise ValueError('native offsets malformed')
    if len(set(epochs))!=len(epochs) or any(len(a)!=rows for a in flat.values()):
        raise ValueError('native array lengths/epoch identities differ')
    x=flat['values']
    valid=flat['accepted'].astype(bool)&np.isfinite(x).all(axis=1)&(x>0).all(axis=1)
    valid&=(x[:,2]<=np.minimum(x[:,0],x[:,3]))&(x[:,1]>=np.maximum(x[:,0],x[:,3]))
    if not np.array_equal(valid,flat['valid']):
        raise ValueError('accepted cached legal-bar flags differ')
    result={}
    for i,epoch in enumerate(epochs):
        lo,hi=int(offsets[i]),int(offsets[i+1])
        series={key:a[lo:hi] for key,a in flat.items()}
        if np.any(np.diff(series['days'])<=0):
            raise ValueError('native epoch days not strictly ordered')
        result[epoch]=EpochBars(series,end_index)
    return result,dict(native_epochs=len(epochs),native_rows=rows,
        cached_indicator_provenance='accepted132 N/low20/run; extracted at causal u/t, not recomputed whole-indicator history',
        legal_bar_flags_recomputed=True)


def construct(protocol,out):
    """One bounded read of each root-bound input; pure tests use tiny fixtures."""
    started=time.monotonic();out=Path(out);out.mkdir(exist_ok=False)
    write_json(out/'started.json',dict(started_at=utc_now(),
        protocol_schema=protocol['schema'],retry=False,fit=0,cash=0,SQL=0))
    receipt={};sinks={};summary={};phase='input_loading'
    try:
        if protocol['metadata_field_allowlist']!=META_FIELDS or protocol['mother_field_allowlist']!=MOTHER_FIELDS:
            raise ValueError('exact prospective field whitelist required')
        inputs=protocol['inputs'];domain=protocol['domain'];sample_end=protocol['sample_end']
        raw=read_bound(inputs['calendar'],'calendar',receipt)
        arr=np.load(io.BytesIO(raw),allow_pickle=False);del raw
        calendar=([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:]
                   for v in arr] if arr.dtype.kind in 'iu' else
                  arr.astype('datetime64[D]').astype(str).tolist())
        if calendar!=sorted(set(calendar)) or sample_end not in calendar:
            raise ValueError('calendar uniqueness/end binding')
        end_index=calendar.index(sample_end)
        raw=read_bound(inputs['economics'],'economics',receipt)
        economics=json.loads(raw)['instruments'];del raw
        raw=read_bound(inputs['native_cache'],'native_cache',receipt)
        market,native_receipt=load_native(raw,end_index,domain);del raw
        write_json(out/'native_loaded.json',native_receipt)
        raw=read_bound(inputs['mothers'],'mothers',receipt)
        mothers=[];references=defaultdict(dict);products=set();families=set();exchanges=set()
        nochild=0
        for row in selected_rows(raw,MOTHER_FIELDS):
            seq=int(row['sequence_index']);u=int(row['u_index'])
            if seq!=len(mothers) or _day(calendar,u)!=row['u_date']:
                raise ValueError('mother sequence/calendar differs')
            if row['family_id']!=row['product_id'].removesuffix('_F'):
                raise ValueError('mother family mapping differs')
            group=int(hashlib.sha256(row['family_id'].encode()).hexdigest(),16)%2
            if int(row['family_hash_group'])!=group:
                raise ValueError('mother family hash differs')
            if u in references[row['product_id']]:
                raise ValueError('duplicate canonical product-day mother')
            references[row['product_id']][u]=row['reference_epoch']
            products.add(row['product_id']);families.add(row['family_id'])
            exchanges.add(row['product_id'].split('.')[0])
            nochild+=int(row['nochild']);mothers.append(row)
        del raw
        observed=(len(mothers),nochild,len(products),len(families),len(exchanges))
        expected=tuple(domain[k] for k in ('mothers','no_child_mothers','policy_products',
                                         'policy_families','exchanges'))
        if observed!=expected:
            raise ValueError('full mother domain differs '+str(observed))
        child_count=np.zeros(len(mothers),dtype=np.int64)
        eligible_count=np.zeros(len(mothers),dtype=np.int64)
        write_json(out/'mother_loaded.json',dict(mothers=len(mothers),nochild=nochild,
            products=sorted(products),families=sorted(families),exchanges=sorted(exchanges)))
        for name,fields in (
            ('action_path_summary',SUMMARY_FIELDS),('unit_states',STATE_FIELDS),
            ('baseline_terminal_observations',TERMINAL_FIELDS),
            ('voluntary_exit_observations',VOLUNTARY_FIELDS),
            ('mother_domain',MOTHER_FIELDS+['observed_child_count','observed_eligible_child_count'])):
            sinks[name]=CsvSink(out/(name+'.csv.gz'),fields)
        phase='metadata_unique_stream'
        raw=read_bound(inputs['metadata'],'metadata',receipt)
        count=0;child_products=set();child_families=set()
        participation=Counter();terminal=Counter();force_states=Counter()
        quote_states=Counter();states_total=0;riskset_total=0;stale_total=0
        cohort=defaultdict(Counter);cohort_dates=defaultdict(set);cohort_family_days=defaultdict(set)
        causal_validation=Counter();epoch_clock={}
        for row in selected_rows(raw,META_FIELDS):
            seq=int(row['sequence_index']);mseq=int(row['mother_sequence_index'])
            u=int(row['u_index']);D=int(row['D_index']);eligible=int(row['u_action_eligible'])
            if seq!=count or eligible not in (0,1) or D!=u+1 or _day(calendar,u)!=row['u_date']:
                raise ValueError('action sequential/causal calendar identity differs')
            if not 0<=mseq<len(mothers):raise ValueError('mother sequence missing')
            mother=mothers[mseq]
            if any(row[a]!=mother[b] for a,b in (
                    ('mother_event_id','event_id'),('product_id','product_id'),
                    ('family_id','family_id'),('u_date','u_date'),
                    ('u_index','u_index'),('anchor_epoch','reference_epoch'),
                    ('family_hash_group','family_hash_group'))):
                raise ValueError('action canonical mother relationship differs')
            if row['reference_epoch'].rsplit('.',1)[0]!=row['product_id']:
                raise ValueError('action epoch product differs')
            if bool(row['u_ineligibility_reason'])==bool(eligible):
                raise ValueError('prospective eligibility reason differs')
            child_count[mseq]+=1;eligible_count[mseq]+=eligible
            child_products.add(row['product_id']);child_families.add(row['family_id'])
            epoch=row['reference_epoch'];econ=economics.get(epoch,{})
            bars=market.get(epoch)
            own=None if bars is None else bars(u)
            if epoch not in epoch_clock:
                life,target=lifecycle(epoch,econ,calendar)
                K=calendar_boundary(epoch,calendar,sample_end)
                listed=econ.get('listed_date')
                listed=listed[:10] if isinstance(listed,str) and len(listed)>=10 else None
                epoch_clock[epoch]=(life,target,K,listed,
                    bisect.bisect_left(calendar,listed) if listed else 0)
            life,target,K,listed,listed_index=epoch_clock[epoch]
            gross,entry_cap,capacity_state=capacity(
                None if own is None else own['volume'],econ.get('round_lot'))
            action=dict(row,u_index=u,D_index=D,u_action_eligible=eligible,
                D_date=_day(calendar,D),N_u=None if own is None else own['N'],
                low20_u=None if own is None else own['low20'],
                u_close=None if own is None else own['close'],
                u_history_run=None if own is None else own['run'],
                u_native_valid=int(own is not None),u_gross_capacity_qty=gross,
                entry_capacity_qty=entry_cap,u_capacity_state=capacity_state,
                source_lifecycle_index=life,source_lifecycle_target_date=target,
                listed_date=listed,listed_index=listed_index,
                economics_qualified=qualified(econ),economics_status=econ.get('economics_status'),
                contract_multiplier=econ.get('contract_multiplier'),tick_size=econ.get('tick_size'),
                round_lot=econ.get('round_lot'),future_info_scope=econ.get('future_info_scope'),
                **K)
            action['effective_lifecycle_index']=min(life,K['K_index']) if K['K_index'] is not None else life
            if eligible:
                anchor_bars=market.get(row['anchor_epoch'])
                anchor=None if anchor_bars is None else anchor_bars(u)
                if own is None or own['run']<20 or not positive(own['N']) or not positive(own['low20']):
                    raise ValueError('original eligible action lacks causal native readiness')
                if not qualified(econ) or entry_cap is None or entry_cap<int(econ['round_lot']) or anchor is None:
                    raise ValueError('original eligible action lacks economics/capacity/anchor')
                if D<len(calendar) and (D>=life or listed and calendar[D]<listed):
                    raise ValueError('original eligible action source lifecycle/listing contradiction')
                for cost in COSTS:
                    if any(execution_quote(own['close'],econ,cost,side)['quote_state']!='observed_research_quote'
                           for side in ('BUY','SELL')):
                        raise ValueError('original eligible action u cost quote contradiction')
                causal_validation['eligible_causal_native_economics_capacity_anchor_verified']+=1
            result=unit_path(action,bars if bars is not None else {},
                             references[row['product_id']],end_index)
            s=result['summary'];s.update(action)
            s['entry_date']=_day(calendar,s['entry_index'])
            s['exit_date']=_day(calendar,s['exit_index'])
            entry_quote={}
            for cost in COSTS:
                states=[execution_quote(s['entry_reference'],econ,cost,side)['quote_state']
                        for side in ('BUY','SELL')]
                entry_quote[cost+'_entry_quote_state']=(
                    'observed_research_quote' if all(v=='observed_research_quote' for v in states)
                    else '|'.join(states))
            s.update(entry_quote);sinks['action_path_summary'].row(s)
            participation[s['participation_state']]+=1;terminal[s['terminal_state']]+=1
            obs_common={key:action.get(key) for key in OBS_COMMON}
            obs_common['sequence_index']=seq
            if s['participation_state']=='entered':
                observed_terminal=dict(obs_common,entry_index=s['entry_index'],
                    entry_date=s['entry_date'],entry_reference=s['entry_reference'],
                    terminal_state=s['terminal_state'],terminal_reason=s['terminal_reason'],
                    exit_index=s['exit_index'],exit_date=s['exit_date'],
                    exit_reference=s['exit_reference'],available_at=s['exit_date'],
                    available_phase=s['exit_available_phase'])
                terminal_bar=bars(s['exit_index']) if s['exit_index'] is not None else None
                for field in ('open','high','low','close','volume'):
                    observed_terminal['terminal_bar_'+field]=None if terminal_bar is None else terminal_bar[field]
                observed_terminal['terminal_bar_valid']=int(terminal_bar is not None)
                observed_terminal.update(quote_fields('entry_BUY',s['entry_reference'],econ,'BUY'))
                observed_terminal.update(quote_fields('entry_SELL_estimate',s['entry_reference'],econ,'SELL'))
                observed_terminal.update(quote_fields('terminal_SELL',s['exit_reference'],econ,'SELL'))
                sinks['baseline_terminal_observations'].row(observed_terminal)
            group=int(row['family_hash_group'])
            cohort_cells=[]
            for cutoff in protocol['cutoffs']:
                if row['u_date']<cutoff and K['K_date'] is not None and K['K_date']<cutoff:
                    for scope in ('main','holdout_0','holdout_1'):
                        if scope!='main' and group==int(scope[-1]):continue
                        key=(cutoff,scope);cohort_cells.append(key)
                        cohort[key]['all_cohort_actions']+=1
                        cohort[key]['u_eligible_actions']+=eligible
                        cohort[key]['participation:'+s['participation_state']]+=1
            for state in result['states']:
                state.update({key:action.get(key) for key in (
                    'sequence_index','product_id','family_id','reference_epoch','anchor_epoch',
                    'family_hash_group','u_index','u_date','D_index','D_date',
                    'source_lifecycle_index','source_lifecycle_target_date','K_target_date',
                    'K_index','K_date','K_state')})
                state.update(entry_date=s['entry_date'],t_date=_day(calendar,state['t_index']),
                    next_planned_date=_day(calendar,state['next_planned_index']),**entry_quote)
                gc,ec,cs=capacity(state['volume'],econ.get('round_lot'))
                state.update(current_gross_capacity_qty=gc,
                    current_next_entry_capacity_qty=ec,current_capacity_state=cs,
                    state_values_complete=int(all(finite(state[v]) for v in
                        ('close','N_t','low20_t','previous_close','SL0','R0','boundary_next'))))
                sinks['unit_states'].row(state);states_total+=1
                riskset_total+=state['riskset'];stale_total+=int(state['mark_state']=='stale')
                force_states[state['force_next'] or 'free_choice']+=1
                for key in cohort_cells:
                    if state['t_date']>=key[0]:continue
                    cohort[key]['held_close_states']+=1
                    cohort[key]['decision_states']+=state['riskset']
                    cohort[key]['stale_states']+=int(state['mark_state']=='stale')
                    cohort[key]['mandatory_states']+=int(bool(state['force_next']))
                    if state['riskset']:
                        cohort_dates[key].add(state['t_date'])
                        cohort_family_days[key].add((row['family_id'],state['t_date']))
            for obs in result['execution_observations']:
                observation=dict(obs_common,**obs,
                    t_date=_day(calendar,obs['t_index']),planned_date=_day(calendar,obs['planned_index']),
                    exit_date=_day(calendar,obs['exit_index']),
                    available_at=_day(calendar,obs['exit_index']))
                observation.update(quote_fields('SELL',obs['reference'],econ,'SELL'))
                sinks['voluntary_exit_observations'].row(observation)
                for cost in COSTS:
                    qstate=observation[cost+'_SELL_quote_state']
                    quote_states[cost+':voluntary:'+qstate]+=1
                for key in cohort_cells:
                    if observation['t_date']>=key[0]:continue
                    known=(s['exit_date'] is not None and s['exit_date']<key[0]
                           and observation['exit_date'] is not None and observation['exit_date']<key[0])
                    for cost in COSTS:
                        qknown=(known and observation[cost+'_SELL_quote_state']=='observed_research_quote'
                            and observed_terminal[cost+'_terminal_SELL_quote_state']=='observed_research_quote')
                        cohort[key][cost+':paired_exit_price_quote_known' if qknown else
                                    cost+':paired_exit_price_quote_unknown']+=1
            count+=1
            if count%100000==0:
                checkpoint=dict(action_rows=count,held_states=states_total,riskset_states=riskset_total,
                    elapsed_seconds=time.monotonic()-started,fit=0,cash=0,SQL=0)
                write_json(out/f'progress_{count:07d}.json',checkpoint)
                print(json.dumps(checkpoint),flush=True)
        del raw
        if count!=domain['actions'] or len(child_products)!=domain['observed_child_products'] or len(child_families)!=domain['observed_child_families']:
            raise ValueError('complete child action domain differs')
        if not child_products<=products or not child_families<=families:
            raise ValueError('child domain escapes full mother policy domain')
        for i,row in enumerate(mothers):
            if child_count[i]!=int(row['child_count']) or eligible_count[i]!=int(row['eligible_child_count']):
                raise ValueError('mother full child/eligible action conservation differs')
            sinks['mother_domain'].row(dict(row,observed_child_count=int(child_count[i]),
                observed_eligible_child_count=int(eligible_count[i])))
        phase='finalizing_outputs'
        artifacts={name:sink.close() for name,sink in sinks.items()}
        cohort_report=[]
        for cutoff in protocol['cutoffs']:
            for scope in ('main','holdout_0','holdout_1'):
                key=(cutoff,scope)
                cohort_report.append(dict(cutoff=cutoff,scope=scope,
                    counts=dict(cohort[key]),distinct_decision_dates=len(cohort_dates[key]),
                    distinct_family_days=len(cohort_family_days[key]),
                    independent_sample_count=None))
        summary=dict(schema='stage511_unit_continuation_summary_v1',status='completed',
            sample_end=sample_end,source_read_receipt=receipt,native=native_receipt,
            domain=dict(mothers=len(mothers),nochild=nochild,policy_products=len(products),
                policy_families=len(families),exchanges=len(exchanges),actions=count,
                observed_child_products=len(child_products),observed_child_families=len(child_families)),
            participation=dict(participation),terminal=dict(terminal),held_close_states=states_total,
            decision_riskset_states=riskset_total,stale_states=stale_total,
            force_state_counts=dict(force_states),quote_states=dict(quote_states),
            causal_validation=dict(causal_validation),cohort_support=cohort_report,
            state_key=['sequence_index','t_index'],
            riskset_rule='alive close, current legal native bar, no existing force; no future quote/terminal gate',
            maturity_cohort_rule='u<cutoff and original known K_date<cutoff; all outcomes and unknown retained',
            labels='future raw execution observations separated; no delta/R/reward computed',
            price_model_scope='independent unit opportunity price path plus entry/exits quote-support flags; not actual account holdings or real execution',
            overlap='rolling actions/months and same market dates overlap; counts are not independent N',
            PIT='cached source/economics provenance inherited; full original PIT not newly certified',
            elapsed_seconds=time.monotonic()-started,fit=0,cash=0,SQL=0,API=0,
            new_reward_labels=0,original129_reads=0,closed505_reads=0,projection489_reads=0,
            COMMON_reads=0,score_reads=0,automatic_retry=False,goal_complete=False)
        write_json(out/'summary.json',summary)
        artifacts['summary']=binding(out/'summary.json')
        write_json(out/'source_read_receipt.json',receipt)
        artifacts['source_read_receipt']=binding(out/'source_read_receipt.json')
        manifest=dict(schema='stage511_unit_continuation_manifest_v1',status='completed',
            artifacts=artifacts,counters=dict(metadata_streams=1,mother_streams=1,
                native_cache_reads=1,economics_reads=1,calendar_reads=1,fit=0,cash=0,SQL=0,
                numeric_reward_source_reads=0,new_reward_labels=0),
            automatic_retry=False,source_bundle=source_bundle(),
            protocol_binding=protocol.get('_protocol_binding'))
        write_json(out/'manifest.json',manifest)
        write_json(out/'terminal.json',dict(status='completed',exit_code=0,
            ended_at=utc_now(),elapsed_seconds=time.monotonic()-started,
            actions=count,held_states=states_total,decision_states=riskset_total,fit=0,cash=0,SQL=0))
        print(json.dumps(dict(status='completed',actions=count,held_states=states_total,
                             decision_states=riskset_total)),flush=True)
        return summary
    except Exception:
        artifacts={name:sink.close() for name,sink in sinks.items()}
        write_json(out/'failed_checkpoint.json',dict(status='failed',phase=phase,
            partial_artifacts=artifacts,source_read_receipt=receipt,summary_so_far=summary,
            traceback=traceback.format_exc(),automatic_retry=False,
            elapsed_seconds=time.monotonic()-started,fit=0,cash=0,SQL=0))
        write_json(out/'terminal.json',dict(status='failed',exit_code=1,
            ended_at=utc_now(),phase=phase,automatic_retry=False))
        raise


def source_bundle():
    return [binding(Path(__file__).with_name(name)) for name in (
        'stage511_continuation_unit_states.py','test_stage511_continuation_unit_states.py')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    protocol_path=Path(args.protocol).resolve()
    raw=protocol_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.protocol_sha256:
        raise ValueError('frozen Stage510 protocol hash differs')
    protocol=json.loads(raw)
    if (protocol.get('schema')!='stage510_unit_continuation_construction_v1'
            or protocol.get('authorized_stage')!=511 or protocol.get('root_authorized') is not True):
        raise ValueError('root frozen construction authorization required')
    for key in ('metadata_streams','mother_streams','native_cache_reads','economics_reads','calendar_reads'):
        if protocol['budget'].get(key)!=1:raise ValueError('exact unique-read budget required '+key)
    for key in ('fit','cash','SQL','API','download','new_reward_labels'):
        if protocol['budget'].get(key)!=0:raise ValueError('forbidden operation budget '+key)
    protocol['_protocol_binding']=dict(path=str(protocol_path),bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest())
    construct(protocol,Path(args.output).resolve())


if __name__ == '__main__':
    main()
