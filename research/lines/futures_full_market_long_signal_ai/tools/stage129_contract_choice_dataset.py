"""Stage129 all observed month actions, causal COMMON26 and own NARROW paths.

Pure array helpers are safe for tiny fixtures. Actual native reads require an
exact root authorization and a fresh output directory. No fitting or cash.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
PROTOCOL_SHA = 'bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0'
VERSION = 'stage129_contract_choice_action_v1'
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
OWN = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location',
       'gap_atr','compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MATURITY = ['normalizer','peer_count','tenor_span_years','return_mean','return_std',
            'return_min','return_max','front_next_basis_u','front_next_basis_prev',
            'front_next_tenor_span_years','q_missing','front_next_missing','normalizer_missing']
COMMON = OWN + MATURITY + ['stress_u_cost_R', 'low20_distance_R']


def load_module(name):
    spec = importlib.util.spec_from_file_location('stage129_' + name, TOOLS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old_labels = load_module('stage070_narrow_labels')
kernel = old_labels.kernel
ref = kernel.ref
NUMERIC = list(old_labels.NUMERIC_FIELDS) + ['net_R_common2N_base', 'net_R_common2N_stress']
OBJECT = old_labels.OBJECT_FIELDS
EXTRA = ['action_sequence_index', 'action_id', 'actual_epoch', 'mother_sequence_index', 'mother_event_id',
         'anchor_epoch', 'product', 'exchange', 'status', 'direction', 'planned_execution_date',
         'observation_state', 'own_feature_state', 'u_action_eligible', 'u_ineligibility_reason',
         'gross_capacity_qty', 'entry_capacity_qty', 'capacity_state', 'u_volume', 'D_index',
         'history_run', 'label_history_ready20', 'filled', 'trade_label_known', 'policy', 'policy_k']
ACTION_COLUMNS = list(dict.fromkeys(IDENTITY + EXTRA + NUMERIC + OBJECT))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def action_id(mother_id, epoch):
    key = dict(version=VERSION, mother_event_id=mother_id, actual_epoch=epoch)
    return VERSION + '_' + hashlib.sha256(canonical(key).encode()).hexdigest()


def capacity(volume, lot):
    if not ref.positive(volume) or not ref.positive(lot) or not float(lot).is_integer():
        return math.nan, math.nan, 'execution_capacity_unknown'
    lot = int(lot)
    gross = lot * math.floor(.01 * float(volume) / lot)
    entry = lot * (gross // (2 * lot))
    return gross, entry, 'known_roundtrip_capacity' if entry >= lot else 'capacity_below_one_roundtrip'


def anchor_request(existing, anchor, current, next_day, expiry):
    """A pending request is latched; held epoch need not equal initial anchor."""
    if existing:
        return existing
    if next_day >= expiry:
        return 'lifecycle_exit'
    if not current:
        return 'observation_exit_requested'
    if current != anchor:
        return 'liquidity_reference_changed'
    return None


def own11(series, j):
    """009 rolling20 TR features, distinct from Wilder20 label N."""
    if j < 20:
        return None, math.nan, 'insufficient_same_epoch_history'
    begin = j - 20
    if int(series.days[j] - series.days[begin]) != 20:
        return None, math.nan, 'source_calendar_gap_rewarm'
    if not series.valid[begin:j+1].all():
        return None, math.nan, 'invalid_history_bar'
    values = series.values[begin:j+1]
    tr = [max(float(b[1]-b[2]), abs(float(b[1]-a[3])), abs(float(b[2]-a[3]))) for a,b in zip(values, values[1:])]
    atr = math.fsum(tr)/20.
    if not ref.positive(atr):
        return None, atr, 'zero_or_nonfinite_atr'
    u, previous = values[-1], values[-2]
    try:
        result = [(u[3]-previous[3])/atr, (u[3]-values[-6,3])/(math.sqrt(5)*atr),
                  (u[3]-values[0,3])/(math.sqrt(20)*atr), (u[3]-u[0])/atr,
                  (u[1]-u[2])/atr, (u[3]-u[2])/(u[1]-u[2]) if u[1]>u[2] else .5,
                  (u[0]-previous[3])/atr, (math.fsum(tr[-5:])/5)/atr,
                  math.log(u[4]/(math.fsum(values[:-1,4])/20)),
                  (u[3]-max(values[:-1,1]))/atr, atr/u[3]]
    except (ValueError, OverflowError, ZeroDivisionError):
        return None, atr, 'nonfinite_own_features'
    if not all(ref.finite(v) for v in result):
        return None, atr, 'nonfinite_own_features'
    return result, atr, 'ready'


def maturity_pool(children, market, u, ordinal):
    """One immutable product-u pool, subsequently queried by every month."""
    pool = []
    for epoch, j in children:
        series = market.series[epoch]
        nominal = epoch.rsplit('.', 1)[1]
        first = (date(int(nominal[:4]), int(nominal[4:]), 1) - date(1970,1,1)).days
        if (first <= ordinal or j == 0 or not series.valid[j] or not series.valid[j-1]
                or int(series.days[j]-series.days[j-1]) != 1):
            continue
        current, previous = float(series.values[j,3]), float(series.values[j-1,3])
        pool.append((epoch, nominal, (first-ordinal)/365., math.log(current/previous), current, previous))
    return sorted(pool, key=lambda p: (p[1], p[0]))


def maturity13(pool, epoch, series, j):
    peers = [p for p in pool if p[0] != epoch]
    tau = np.asarray([p[2] for p in peers], dtype=float)
    returns = np.asarray([p[3] for p in peers], dtype=float)
    n = len(peers)
    C, N = float(series.values[j,3]), float(series.N[j])
    normalizer = N/C if series.valid[j] and ref.positive(N) and ref.positive(C) else math.nan
    missing_normalizer = int(not math.isfinite(normalizer))
    q_missing = bool(missing_normalizer or len({p[1] for p in peers}) < 3)
    if not q_missing:
        centered = tau-tau.mean()
        denominator = float(centered @ centered)
        q_missing = not (denominator > 0 and math.isfinite(denominator))
    front = following = None
    for p in pool:
        if front is None:
            front = p
        elif p[1] != front[1]:
            following = p
            break
    bu = bp = span = math.nan
    if following is not None:
        bu, bp = math.log(following[4]/front[4]), math.log(following[5]/front[5])
        span = following[2]-front[2]
    return [normalizer, n, float(tau.max()-tau.min()) if n else math.nan,
            float(returns.mean()) if n else math.nan, float(returns.std(ddof=0)) if n else math.nan,
            float(returns.min()) if n else math.nan, float(returns.max()) if n else math.nan,
            bu, bp, span, int(q_missing), int(following is None), missing_normalizer]


def context(mothers, market, dates, economics):
    """Index child rows without any target, D-price or future readiness screen."""
    if list(dates) != list(market.dates) or list(dates) != sorted(set(dates)):
        raise ValueError('market calendar mismatch')
    if (mothers.event_id.duplicated().any() or mothers.duplicated(['product_id','u_date']).any()
            or mothers.sequence_index.tolist() != list(range(len(mothers)))):
        raise ValueError('mother identity or ordering mismatch')
    lookup = {d:k for k,d in enumerate(dates)}
    if not mothers.u_date.map(lookup).equals(mothers.u_index.astype(int)):
        raise ValueError('mother native u index mismatch')
    if not mothers.family_id.eq(mothers.product_id.str.removesuffix('_F')).all():
        raise ValueError('ordinary/F family mismatch')
    index = {(p,int(u)):i for i,(p,u) in enumerate(zip(mothers.product_id,mothers.u_index))}
    children = [[] for _ in range(len(mothers))]
    references = {}
    for row in mothers.itertuples(index=False):
        if row.product_id not in references:
            references[row.product_id] = np.full(len(dates), None, dtype=object)
        references[row.product_id][row.u_index] = row.reference_epoch or None
    counts = Counter(native_source_rows=0, source_rows_mapped_to_actions=0, orphan_product_rows=0,
                     source_rows_outside_mother_dates=0, pre2010_rows=0)
    for epoch, series in market.series.items():
        parts = epoch.split('.')
        if len(parts) != 3 or len(parts[2]) != 6 or not parts[2].isdigit():
            raise ValueError('noncanonical epoch identity')
        product = '.'.join(parts[:2])
        for j, u_raw in enumerate(series.days):
            u = int(u_raw); counts['native_source_rows'] += 1
            if dates[u] < '2010-01-01':
                counts['pre2010_rows'] += 1
            i = index.get((product,u))
            if i is None:
                counts['orphan_product_rows' if product not in references else 'source_rows_outside_mother_dates'] += 1
                continue
            children[i].append((epoch,j)); counts['source_rows_mapped_to_actions'] += 1
    for members in children:
        members.sort(key=lambda p: p[0])
    counts['mother_rows'] = len(mothers)
    counts['mother_rows_without_children'] = sum(not c for c in children)
    counts['action_rows'] = sum(map(len,children))
    expiry = {epoch: ref.lifecycle_index(e, epoch, np.asarray(dates,dtype='U10')) for epoch,e in economics.items()}
    # Exact native calendar grid lookup is shared across all independent paths.
    positions = {}
    for epoch, series in market.series.items():
        array = np.full(len(dates), -1, dtype=np.int32)
        array[series.days] = np.arange(len(series.days),dtype=np.int32)
        positions[epoch] = array
    return children, references, expiry, positions, counts


def simulate_action(mother, epoch, j, market, dates, economics, references, expiry, positions, seq, end):
    u = int(mother.u_index); D = u+1
    series = market.series[epoch]; e = economics.get(epoch,{})
    key = action_id(mother.event_id, epoch)
    row = dict.fromkeys(OBJECT, None)
    row.update({name: math.nan for name in NUMERIC})
    row.update(sequence_index=seq, event_id=key, product_id=mother.product_id, family_id=mother.family_id,
               u_date=mother.u_date, u_index=u, reference_epoch=epoch, action_sequence_index=seq, action_id=key,
               actual_epoch=epoch, mother_sequence_index=int(mother.sequence_index), mother_event_id=mother.event_id,
               anchor_epoch=mother.reference_epoch, product=mother.product_id.split('.')[1], exchange=mother.product_id.split('.')[0],
               direction='long', planned_execution_date=dates[D] if D<len(dates) else '',
               status='observed_long_research_opportunity' if series.valid[j] else 'invalid_native_observation',
               observation_state='observed_valid_u_native_bar' if series.valid[j] else 'invalid_u_native_bar',
               own_feature_state='', u_action_eligible=0, u_ineligibility_reason='', D_index=D,
               history_run=int(series.run[j]), label_history_ready20=0, filled=0, trade_label_known=0,
               policy='NARROW', policy_k=.25, economics_status=e.get('economics_status','unresolved_exact_epoch_metadata'),
               future_info_scope=e.get('future_info_scope'), participation_state='not_history_ready', label_state='not_history_ready',
               u_volume=float(series.values[j,4]))
    lot = e.get('round_lot')
    gross, entry, capacity_state = capacity(row['u_volume'], lot)
    row.update(gross_capacity_qty=gross, entry_capacity_qty=entry, capacity_state=capacity_state)
    for field, source in [('multiplier','contract_multiplier'),('round_lot','round_lot'),('tick_size','tick_size')]:
        if ref.positive(e.get(source)):
            row[field] = float(e[source])
    if not series.valid[j]:
        row.update(label_reason='no_accepted_u_reference_bar', u_ineligibility_reason='invalid_u_native_bar')
        return row
    N,L20,C = float(series.N[j]), float(series.low20[j]), float(series.values[j,3])
    row.update(N_u=N, low20_u=L20, u_close=C)
    ready = series.run[j]>=20 and ref.positive(N) and ref.positive(L20)
    row['label_history_ready20'] = int(ready)
    if not ready:
        row.update(label_reason='insufficient_or_gap_history20', u_ineligibility_reason='insufficient_or_gap_history20')
        return row
    row['R0_points'] = .25*N
    if not ref.qualified_economics(e):
        row.update(participation_state='economics_unresolved',label_state='input_or_economics_unresolved',
                   label_reason='instrument_economics_unqualified',u_ineligibility_reason='economics_unresolved')
        return row
    mult = float(e['contract_multiplier']); risk = .25*N*mult
    row.update(cash_risk_unit=risk, lifecycle_index=expiry[epoch])
    try:
        for s in ('base','stress'):
            estimate = kernel.unit_estimate(C,N,e,s,'NARROW')
            row[s+'_u_fee_roundtrip_per_lot'] = estimate['fee_roundtrip_per_lot']
            row[s+'_u_slippage_roundtrip_per_lot'] = estimate['buy']['slippage_per_lot']+estimate['sell']['slippage_per_lot']
            row[s+'_u_risk_estimate_per_lot'] = estimate['risk_per_lot']
    except ValueError:
        row.update(participation_state='economics_unresolved',label_state='input_or_economics_unresolved',
                   label_reason='unrepresentable_u_cost_quote',u_ineligibility_reason='unrepresentable_u_cost_quote')
        return row
    anchor = mother.reference_epoch
    if not anchor or market.bar(anchor,u) is None:
        row.update(participation_state='no_anchor',label_state='input_or_economics_unresolved',
                   label_reason='no_accepted_u_anchor',u_ineligibility_reason='no_accepted_u_anchor')
        return row
    # Calendar-end censoring is not a u eligibility failure. A searchsorted
    # sentinel expiry also cannot establish a future lifecycle cancellation.
    if D < len(dates) and (D >= expiry[epoch] or (e.get('listed_date') and dates[D]<e['listed_date'])):
        row['u_ineligibility_reason'] = 'known_entry_ineligible_lifecycle'
    elif capacity_state != 'known_roundtrip_capacity':
        row['u_ineligibility_reason'] = capacity_state
    else:
        row['u_action_eligible'] = 1

    def cancel(reason, known):
        row.update(participation_state='known_nonparticipation',label_state='known_nonparticipation',
                   cancel_reason=reason,participation_known_date=dates[known],
                   participation_known_phase=old_labels.PHASE,policy_diagnostic_pnl=0.)

    def unknown(state, reason, k):
        row.update(label_state=state,unknown_reason=reason,unknown_index=k,unknown_date=dates[k])

    if D < len(dates) and (D>=expiry[epoch] or (e.get('listed_date') and dates[D]<e['listed_date'])):
        cancel('known_entry_ineligible_lifecycle',u)
        return row
    if D > end:
        row.update(participation_state='not_yet_observable',label_state='intent_right_censored')
        return row
    pos = positions[epoch]
    dj = int(pos[D])
    if dj < 0 or not series.valid[dj]:
        row['participation_state'] = 'execution_unknown'
        unknown('entry_execution_unknown','missing_or_invalid_D_bar',D)
        return row
    F = float(series.values[dj,0]); SL0 = F-.25*N
    row.update(entry_reference=F,SL0=SL0)
    if F<=L20:
        cancel('stale_boundary_at_open',D)
        return row
    if SL0<=0:
        cancel('invalid_initial_stop',D)
        return row
    try:
        buys = {s:ref.adverse_quote(F,'BUY',e,s) for s in ('base','stress')}
    except ValueError:
        row.update(participation_state='economics_unresolved',label_state='input_or_economics_unresolved',
                   label_reason='unrepresentable_entry_cost_quote')
        return row
    row.update(participation_state='filled',participation_known_date=dates[D],participation_known_phase=old_labels.PHASE,
               filled=1,entry_index=D,entry_date=dates[D])
    B = ref.next_boundary(SL0,L20); row['entry_boundary']=B
    for s in ('base','stress'):
        row[s+'_entry_fill']=buys[s]['fill_price']; row[s+'_entry_fee_per_lot']=buys[s]['fee_per_lot']
        row[s+'_entry_slippage_per_lot']=buys[s]['slippage_per_lot']
    force = None
    for k in range(D,end+1):
        kj = int(pos[k])
        if kj < 0 or not series.valid[kj]:
            unknown('path_or_execution_unknown','missing_or_invalid_held_old_epoch_bar',k)
            break
        O,_,low,close,_ = series.values[kj]
        reference,reason = ref.price_exit_reference(O,low,B,force)
        row.update(last_path_index=k,holding_source_days=k-D+1)
        if reference is not None:
            try:
                sells={s:ref.adverse_quote(reference,'SELL',e,s) for s in ('base','stress')}
            except ValueError:
                unknown('input_or_economics_unresolved','unrepresentable_exit_cost_quote',k)
                break
            row.update(label_state='closed_complete_bar_model',trade_label_known=1,exit_index=k,exit_date=dates[k],
                       label_known_date=dates[k],label_known_phase=old_labels.PHASE,exit_reference=reference,
                       exit_boundary=B,exit_reason=reason,gross_points_reference=reference-F,gross_R_reference=(reference-F)/(.25*N))
            for s in ('base','stress'):
                buy,sell=buys[s],sells[s]
                fee=buy['fee_per_lot']+sell['fee_per_lot']; slip=buy['slippage_per_lot']+sell['slippage_per_lot']
                net=mult*(sell['fill_price']-buy['fill_price'])-fee
                row.update({s+'_exit_fill':sell['fill_price'],s+'_exit_fee_per_lot':sell['fee_per_lot'],
                            s+'_exit_slippage_per_lot':sell['slippage_per_lot'],s+'_total_fee_per_lot':fee,
                            s+'_total_slippage_per_lot':slip,'net_pnl_'+s+'_per_lot':net,'net_R_'+s:net/risk,
                            'net_R_common2N_'+s:net/(2*N*mult)})
            break
        row.update(terminal_mark=float(close),label_state='open_right_censored')
        B=ref.next_boundary(SL0,series.low20[kj])
        force=anchor_request(force,anchor,references[mother.product_id][k],k+1,expiry[epoch])
    return row


def action_stream(mothers, market, dates, economics):
    children,references,expiry,positions,counts=context(mothers,market,dates,economics)
    end=max(mothers.u_index.astype(int)); seq=0
    ordinals=np.asarray(dates,dtype='datetime64[D]').astype(np.int64)
    state_counts=Counter();eligibility=Counter();capacity_counts=Counter()
    def generate():
        nonlocal seq
        for mother,members in zip(mothers.itertuples(index=False),children):
            u=int(mother.u_index)
            pool=maturity_pool(members,market,u,int(ordinals[u]))
            for epoch,j in members:
                series=market.series[epoch]
                row=simulate_action(mother,epoch,j,market,dates,economics,references,expiry,positions,seq,end)
                own,_,own_state=own11(series,j)
                row['own_feature_state']=own_state
                values=np.full(26,np.nan,dtype=float)
                if own is not None:
                    values[:11]=own
                values[11:24]=maturity13(pool,epoch,series,j)
                if ref.positive(row.get('N_u')):
                    denominator=2*row['N_u']*row['multiplier']
                    if ref.positive(denominator):
                        values[24]=(row['stress_u_fee_roundtrip_per_lot']+row['stress_u_slippage_roundtrip_per_lot'])/denominator
                    values[25]=(row['u_close']-row['low20_u'])/(2*row['N_u'])
                if np.isinf(values).any():
                    raise ValueError('infinite action feature')
                closed=row['label_state']=='closed_complete_bar_model'
                if closed != (ref.finite(row.get('net_R_stress')) and bool(row.get('label_known_date'))):
                    raise AssertionError('trade target leaked to unknown/cancelled row')
                state_counts[row['label_state']]+=1
                eligibility[row['u_ineligibility_reason'] or 'eligible']+=1
                capacity_counts[row['capacity_state']]+=1
                yield row,values
                seq+=1
        if seq!=counts['action_rows']:
            raise AssertionError('action count changed in stream')
        counts['label_states']=dict(state_counts);counts['u_eligibility_states']=dict(eligibility)
        counts['capacity_states']=dict(capacity_counts)
    return generate(),counts


def build_arrays(mothers,market,dates,economics):
    """Tiny fixture convenience; actual run streams rows instead of this list."""
    stream,counts=action_stream(mothers,market,dates,economics)
    rows=[];features=[]
    for row,values in stream:
        rows.append(row);features.append(values)
    return pd.DataFrame(rows,columns=ACTION_COLUMNS),np.asarray(features,dtype=float).reshape(-1,26),counts


def file_binding(path):
    path=Path(path).resolve(); digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk);size+=len(chunk)
    return dict(path=str(path),bytes=size,sha256=digest.hexdigest())


def read_bound(binding):
    raw=Path(binding['path']).read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('input binding mismatch: '+binding['path'])
    return raw


def source_bundle():
    names=['stage129_contract_choice_dataset.py','test_stage129_contract_choice_dataset.py',
           'stage070_narrow_labels.py','stage070_policy_kernel.py','stage042_cross_session_experiment.py',
           'stage009_day_proxy_dataset.py','stage049_maturity_features.py']
    return [file_binding(TOOLS/name) for name in names]


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')


def authorize(args):
    pb=file_binding(args.protocol)
    if pb['sha256']!=args.protocol_sha256 or pb['sha256']!=PROTOCOL_SHA:
        raise ValueError('only exact frozen128 protocol authorized')
    protocol=json.loads(read_bound(pb))
    ab=file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:
        raise ValueError('authorization binding mismatch')
    auth=json.loads(read_bound(ab));bundle=source_bundle()
    if (auth.get('schema')!='stage128_exact_root_authorization_v1' or auth.get('stage')!='dataset'
            or auth.get('authorized_by')!='root' or auth.get('exact_source_authorized') is not True
            or auth.get('protocol_sha256')!=PROTOCOL_SHA or auth.get('output')!=str(Path(args.output).resolve())
            or auth.get('source_bundle')!=bundle):
        raise ValueError('exact root dataset authorization required')
    if protocol.get('schema')!='stage128_contract_choice_protocol_v1' or protocol['features']['common_columns']!=COMMON:
        raise ValueError('protocol semantics differ')
    for binding in protocol['source_bindings']:
        read_bound(binding)
    return protocol,pb,auth,ab,bundle


def execute(args):
    protocol,pb,auth,ab,bundle=authorize(args)
    if ref.NATIVE_QUERIES:
        raise ValueError('native read already consumed in this process')
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();status='failed';error=None
    counts={};source_receipt={};actions_count=0;input_bindings={}
    write_json(output/'actual_started.json',dict(status='started',started_at=began,stage='dataset',source_bundle=bundle,protocol=pb,authorization=ab))
    try:
        market_binding=protocol['inputs']['market_protocol']
        market_protocol=json.loads(read_bound(market_binding));input_bindings['market_protocol']=market_binding
        if market_protocol['database']!=protocol['source']['database']:
            raise ValueError('source database binding differs from inherited market bridge')
        calendar_binding=market_protocol['calendar'];dates=ref.parse_calendar(read_bound(calendar_binding))
        economic_binding=market_protocol['economic_projection'];economic=json.loads(read_bound(economic_binding))
        economics=economic['instruments'];input_bindings.update(calendar=calendar_binding,economic_projection=economic_binding)
        mother_binding=protocol['inputs']['narrow_labels'];input_bindings['narrow_labels']=mother_binding
        manifest_binding=protocol['inputs']['narrow_manifest'];old_manifest=json.loads(read_bound(manifest_binding))
        if old_manifest.get('status')!='completed' or old_manifest.get('mother_rows')!=399252:
            raise ValueError('accepted original mother manifest required')
        input_bindings['narrow_manifest']=manifest_binding
        mother_raw=read_bound(mother_binding)
        mothers=pd.read_csv(io.BytesIO(mother_raw),compression='gzip',usecols=IDENTITY,keep_default_na=False)[IDENTITY]
        del mother_raw
        if (len(mothers)!=399252 or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95
                or mothers.product_id.str.split('.').str[0].nunique()!=6):
            raise ValueError('complete mother scope changed')
        market,source_receipt=ref.load_native_once(protocol['source']['database'],dates,'2010-01-01',protocol['scope']['end'])
        if source_receipt['native_contract_days']!=1552456 or source_receipt['native_epochs']!=9520:
            raise ValueError('native accepted scope changed')
        stream,counts=action_stream(mothers,market,dates,economics)
        if counts['orphan_product_rows'] or counts['source_rows_outside_mother_dates'] or counts['pre2010_rows']:
            raise ValueError('native rows not mapped to full mother scope')
        common=np.empty((counts['action_rows'],26),dtype=np.float64)
        with gzip.open(output/'actions.csv.gz','wt',newline='',compresslevel=6) as target:
            writer=csv.DictWriter(target,fieldnames=ACTION_COLUMNS,extrasaction='raise');writer.writeheader()
            for row,values in stream:
                common[actions_count]=values
                writer.writerow({k:('' if v is None or isinstance(v,(float,np.floating)) and not math.isfinite(v) else v) for k,v in row.items()})
                actions_count+=1
        if actions_count!=counts['action_rows']:
            raise AssertionError('stream row count mismatch')
        with (output/'common26.npz').open('wb') as target:
            np.savez_compressed(target,common=common,columns=np.asarray(COMMON,dtype='U40'))
        del common
        mothers.to_csv(output/'mothers.csv.gz',index=False,compression=dict(method='gzip',mtime=0))
        ref.assert_db_binding(protocol['source']['database'])
        if source_bundle()!=bundle:
            raise ValueError('implementation changed during actual build')
        status='completed'
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        raise
    finally:
        terminal=dict(status=status,mode='actual',stage='dataset',protocol=pb,source_bundle=bundle,
                      started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,
                      native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,actual_fit_calls_completed=0,
                      new_cash_accounts=0,cash_replays=0,
                      completed_action_rows=actions_count,completed_actual_builds=int(status=='completed'),
                      downloads=0,whole_database_hashes=0,fixture=False,python=sys.executable)
        write_json(output/'actual_terminal.json',terminal)
    roles={role:file_binding(output/name) for role,name in [('actions','actions.csv.gz'),('common','common26.npz'),('mothers','mothers.csv.gz'),('terminal','actual_terminal.json')]}
    artifacts=[dict(role=role,**binding) for role,binding in roles.items()]
    manifest=dict(schema='stage129_contract_choice_dataset_v1',status=status,mode='actual',protocol=pb,authorization=ab,
                  source_bundle=bundle,input_bindings=input_bindings,artifacts=artifacts,**roles,
                  mother_rows=len(mothers),action_rows=actions_count,products=98,families=95,exchanges=6,
                  columns=COMMON,counts=counts,source_read_receipt=source_receipt,native_source_queries=ref.NATIVE_QUERIES,
                  actual_model_fit_calls=0,actual_fit_calls_completed=0,new_cash_accounts=0,cash_replays=0,
                  production_qualified=False,goal_complete=False)
    write_json(output/'manifest.json',manifest)
    return dict(status=status,output=str(output),mother_rows=len(mothers),action_rows=actions_count,native_source_queries=ref.NATIVE_QUERIES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
