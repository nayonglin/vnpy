"""Label-free causal u adapter for frozen pure COMMON52. No CLI or data receiver.

Inputs are already received/as-of authorized snapshots. This module does not set
T0, certify completion/deadlines, fit, query SQL, read prices, or run cash.
Only accepted small source definitions are AST-extracted, never their imports,
label entrypoints or actual CLIs. Numeric missing values remain NaN in results;
an external journal must encode them as JSON null without changing their state.
"""
from __future__ import annotations

import ast
import bisect
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
COMMON = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location',
          'gap_atr','compression5_20','log_volume_ratio20','breakout20_atr','atr_pct',
          'normalizer','peer_count','tenor_span_years','return_mean','return_std',
          'return_min','return_max','front_next_basis_u','front_next_basis_prev',
          'front_next_tenor_span_years','q_missing','front_next_missing','normalizer_missing',
          'stress_u_cost_R','low20_distance_R']
SOURCES = {
    'stage004_product_day_opportunities.py': 'a6093f91c30fe835f3ddd84882a074f7b13185ef36013d2ed6f41a0e9ee8f8af',
    'stage042_cross_session_experiment.py': 'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d',
    'stage070_policy_kernel.py': 'ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe',
    'stage129_contract_choice_dataset.py': '9888c1321e2242f06bf461806141326b88e113884fcf655040746e48c5e78035',
    'stage130_contract_choice_fit.py': 'f10b79f1c1db14af7a314795eeced2611d4de0402e1f5cae53ebaf4a43bc5d35',
    'stage156_voluntary_choices.py': '4c56ad2f0e812a10aca9a153e3328c8a8aa6e8df1a1b588f3aecf898713f7200',
    'stage157_voluntary_cash.py': '367d8202040fd30eb05b0070895c9a03706645446bd102c6d5de04f22824ba9b',
}


def _extract(filename, names, namespace):
    path = TOOLS/filename
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCES[filename]:
        raise ValueError('accepted small source changed: '+filename)
    nodes = []
    found = set()
    for node in ast.parse(raw, filename=str(path)).body:
        declared = ({node.name} if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else
                    {v.id for target in node.targets for v in ast.walk(target) if isinstance(v, ast.Name)}
                    if isinstance(node, ast.Assign) else set())
        if declared & set(names):
            nodes.append(node); found.update(declared & set(names))
    if found != set(names):
        raise ValueError('missing pure definitions: '+repr(set(names)-found))
    env = dict(namespace)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), env)
    return env


@lru_cache(maxsize=1)
def _helpers():
    env = dict(np=np, math=math, date=date, Decimal=Decimal,
               ROUND_CEILING=ROUND_CEILING, ROUND_FLOOR=ROUND_FLOOR,
               Counter=Counter, bisect=bisect, re=re, json=json, hashlib=hashlib)
    ref = _extract('stage042_cross_session_experiment.py',
        ['finite','positive','qualified_economics','lifecycle_index','margin_rate',
         'fee_at','adverse_quote','SCENARIOS','MARGIN_BUFFER'], env)
    k = _extract('stage070_policy_kernel.py', ['POLICIES','policy_k','unit_estimate'], ref)
    own = _extract('stage129_contract_choice_dataset.py',
        ['VERSION','canonical','action_id','capacity','own11','maturity_pool','maturity13'],
        dict(env, ref=SimpleNamespace(**ref)))
    mother = _extract('stage004_product_day_opportunities.py',
        ['VERSION','canonical','digest','finite','oi_status','candidate'], env)
    choose = _extract('stage156_voluntary_choices.py',
        ['POLICY_VERSION','SCORE_FIELDS','integer','calendar_boundary','cutoff_for',
         'rank_action','family_winners','select_full_pool'], env)
    score = _extract('stage130_contract_choice_fit.py', ['design'], env)
    boundary = _extract('stage157_voluntary_cash.py', ['apply_boundaries'], env)
    return SimpleNamespace(ref=SimpleNamespace(**ref), kernel=SimpleNamespace(**k),
        own=SimpleNamespace(**own), mother=SimpleNamespace(**mother),
        choose=SimpleNamespace(**choose), score=score['design'],
        apply_boundaries=boundary['apply_boundaries'])


class WilderState:
    """Original042 recurrence plus bounded feature window; append completed bars.

    u_index is the stable source-calendar index, not the count of observed bars.
    A saved snapshot represents its latest u only; use an older saved snapshot
    for an older u. Array-style inputs may contain future rows: build truncates
    those arrays before any feature, reference or eligibility calculation.
    """
    def __init__(self):
        self.last_seen = None
        self.last_day = None
        self.last_close = None
        self.N = None
        self.seed = 0.
        self.run = 0
        self.lows = []
        self.history = []

    def append(self, u_index, bar):
        if isinstance(u_index, bool) or int(u_index) != u_index or u_index < 0:
            raise ValueError('nonnegative source-calendar index required')
        u_index = int(u_index)
        if self.last_seen is not None and u_index <= self.last_seen:
            raise ValueError('append must advance source-calendar index')
        h = _helpers()
        values = [bar.get(v) for v in ('open','high','low','close','volume')]
        valid = not h.mother.candidate(bar)
        if not valid or self.last_day is None or u_index != self.last_day+1:
            self.last_day = self.last_close = self.N = None
            self.seed = 0.; self.run = 0; self.lows = []
        low20 = None
        if valid:
            O,H,L,C,V = map(float, values)
            tr = H-L if self.last_close is None else max(H-L, abs(H-self.last_close), abs(L-self.last_close))
            self.run += 1
            if self.run <= 20:
                self.seed += tr
                if self.run == 20: self.N = self.seed/20.
            else:
                self.N = (19.*self.N+tr)/20.
            self.lows = [v for v in self.lows if v[0] >= u_index-19]
            while self.lows and self.lows[-1][1] >= L: self.lows.pop()
            self.lows.append([u_index,L])
            if self.run >= 20: low20 = self.lows[0][1]
            self.last_day = u_index; self.last_close = C
        self.last_seen = u_index
        # JSON-safe state uses null for invalid numerics, never JSON NaN.
        safe = [float(v) if h.ref.finite(v) else None for v in values]
        oi, _ = h.mother.oi_status(bar.get('close_oi'))
        self.history.append(dict(day=u_index, values=safe, valid=valid, N=self.N,
                                 low20=low20, run=self.run, close_oi=oi))
        self.history = self.history[-21:]
        return self

    def to_dict(self):
        return json.loads(json.dumps(dict(schema='stage320_wilder_state_v1',
            last_seen=self.last_seen,last_day=self.last_day,last_close=self.last_close,
            N=self.N,seed=self.seed,run=self.run,lows=self.lows,history=self.history), allow_nan=False))

    @classmethod
    def from_dict(cls, value):
        value = json.loads(json.dumps(value, allow_nan=False))
        if value.pop('schema', None) != 'stage320_wilder_state_v1':
            raise ValueError('Wilder state schema mismatch')
        state = cls()
        if set(value) != set(state.__dict__): raise ValueError('Wilder state keys mismatch')
        state.__dict__.update(value)
        return state

    def to_series(self):
        rows = self.history
        return SimpleNamespace(days=np.asarray([r['day'] for r in rows], dtype=np.int64),
            values=np.asarray([r['values'] for r in rows], dtype=float).reshape(-1,5),
            valid=np.asarray([r['valid'] for r in rows], dtype=bool),
            N=np.asarray([r['N'] for r in rows], dtype=float),
            low20=np.asarray([r['low20'] for r in rows], dtype=float),
            run=np.asarray([r['run'] for r in rows], dtype=np.int64),
            close_oi=np.asarray([r['close_oi'] for r in rows], dtype=float))


def _calendar(dates, u, D_context):
    dates = list(dates)
    if not dates or dates != sorted(set(dates)) or not 0 <= u < len(dates):
        raise ValueError('unique source-calendar and valid u required')
    for d in dates:
        if date.fromisoformat(d).isoformat() != d: raise ValueError('canonical source date required')
    confirmed = D_context.get('confirmed')
    if not isinstance(confirmed, bool): raise ValueError('explicit D confirmed boolean required')
    if confirmed:
        if (u+1 >= len(dates) or D_context.get('D_index') != u+1
                or D_context.get('D_date') != dates[u+1]):
            raise ValueError('confirmed D must be actual next source-calendar session')
        return dates
    return dates[:u+1]


def _prefix(series, u):
    if isinstance(series, WilderState):
        if series.last_seen != u: raise ValueError('Wilder snapshot must represent requested u')
        series = series.to_series()
    days = np.asarray(series.days)
    if (days.ndim != 1 or not np.issubdtype(days.dtype, np.integer)
            or (len(days) and (days[0] < 0 or np.any(np.diff(days) <= 0)))):
        raise ValueError('unique increasing integer source indices required')
    n = int(np.searchsorted(days,u,side='right'))
    arrays = dict(days=days[:n].copy())
    for key in ('values','valid','N','low20','run'):
        value = np.asarray(getattr(series,key))
        if len(value) != len(days): raise ValueError('series shape mismatch '+key)
        arrays[key] = value[:n].copy()
    if arrays['values'].shape != (n,5): raise ValueError('OHLCV5 required')
    oi = getattr(series,'close_oi',None)
    if oi is not None and len(oi) != len(days): raise ValueError('close OI shape mismatch')
    arrays['close_oi'] = np.asarray(oi[:n] if oi is not None else [math.nan]*n,dtype=float)
    return SimpleNamespace(**arrays)


def _lifecycle_target(economics, epoch):
    month = epoch.rsplit('.',1)[1]
    candidates = [month[:4]+'-'+month[4:]+'-01']
    for field in ('known_lifecycle_exit_boundary','nominal_month_first_date','maturity_date','de_listed_date'):
        value = economics.get(field)
        if isinstance(value,str) and len(value)>=10 and value[:10]>='1900-01-01': candidates.append(value[:10])
    return min(candidates)


def build_u_observations(series_by_epoch, u_index, dates, economics, products, *, D_context):
    """Return full accepted-product mother domain, raw candidates and statuses.

    products is the fixed accepted product-id iterable (or records containing
    product_id). Unlisted products are reported unsupported, not silently added.
    Daily local sequence indices join this batch; stable event/action hashes use
    original004/129 versions and date/epoch identities. No future labels exist.
    """
    h = _helpers(); u = h.choose.integer(u_index)
    calendar = _calendar(dates,u,D_context); day = calendar[u]
    if day < '2023-01-01': raise ValueError('this adapter deploys fixed main2023 only')
    products = [p['product_id'] if isinstance(p,dict) else p for p in products]
    if len(set(products)) != len(products): raise ValueError('duplicate accepted product')
    products = sorted(products)
    series = {}; groups = {p:[] for p in products}; statuses = []
    for epoch, original in sorted(series_by_epoch.items()):
        parts = epoch.split('.')
        if len(parts)!=3 or not re.fullmatch(r'\d{6}',parts[2]): raise ValueError('true YYYYMM epoch required')
        date(int(parts[2][:4]),int(parts[2][4:]),1)
        product = '.'.join(parts[:2])
        s = _prefix(original,u)
        j = int(np.searchsorted(s.days,u))
        current = j < len(s.days) and s.days[j] == u
        if product not in groups:
            if current:
                statuses.append(dict(product_id=product,reference_epoch=epoch,u_date=day,status='unsupported_product'))
            continue
        series[epoch] = s
        if current: groups[product].append((epoch,j))
    market = SimpleNamespace(series=series)
    mothers=[]; candidates=[]; raw_rows=[]; references={}
    for seq, product in enumerate(products):
        members = groups[product]
        valid = [(epoch,j) for epoch,j in members if series[epoch].valid[j]]
        def rank(pair):
            epoch,j = pair; s = series[epoch]
            oi,_ = h.mother.oi_status(float(s.close_oi[j]))
            return (-float(s.values[j,4]),oi is None,-oi if oi is not None else 0.,epoch)
        anchor = min(valid,key=rank)[0] if valid else ''
        references[product] = anchor
        key = dict(version=h.mother.VERSION,product_id=product,u_date=day)
        mother_id = h.mother.VERSION+'_'+h.mother.digest(h.mother.canonical(key).encode())
        mother = dict(sequence_index=seq,event_id=mother_id,product_id=product,
            family_id=product.removesuffix('_F'),u_date=day,u_index=u,reference_epoch=anchor,
            status='observed_long_research_opportunity' if anchor else 'no_accepted_observation',
            candidate_count=len(valid),rejected_count=len(members)-len(valid),
            planned_execution_date=calendar[u+1] if u+1<len(calendar) else '')
        mothers.append(mother)
        statuses.append(dict(product_id=product,u_date=day,status=mother['status'],
            observed_months=len(members),accepted_months=len(valid),anchor_epoch=anchor,
            anchor_oi_status=h.mother.oi_status(float(series[anchor].close_oi[-1]))[1] if anchor else 'no_reference'))
        pool = h.own.maturity_pool(members,market,u,(date.fromisoformat(day)-date(1970,1,1)).days)
        for epoch,j in members:
            s=series[epoch]; e=economics.get(epoch,{}); action=h.own.action_id(mother_id,epoch)
            gross,entry,capacity_state=h.own.capacity(float(s.values[j,4]),e.get('round_lot'))
            target=_lifecycle_target(e,epoch); expiry=h.ref.lifecycle_index(e,epoch,np.asarray(calendar,dtype='U10'))
            row=dict(sequence_index=len(candidates),action_sequence_index=len(candidates),
                event_id=action,action_id=action,mother_sequence_index=seq,mother_event_id=mother_id,
                product_id=product,family_id=mother['family_id'],u_date=day,u_index=u,D_index=u+1,
                reference_epoch=epoch,actual_epoch=epoch,anchor_epoch=anchor,direction='long',
                u_action_eligible=0,u_ineligibility_reason='',N_u=math.nan,low20_u=math.nan,u_close=math.nan,
                history_run=int(s.run[j]),label_history_ready20=0,gross_capacity_qty=gross,
                u_gross_capacity_qty=gross,entry_capacity_qty=entry,capacity_state=capacity_state,
                lifecycle_index=expiry,source_lifecycle_target_date=target,
                source_lifecycle_state='after_calendar_pending' if expiry==len(calendar) else 'in_calendar',
                economics_status=e.get('economics_status','unresolved_exact_epoch_metadata'),policy='NARROW')
            if not s.valid[j]: reason='invalid_u_native_bar'
            else:
                N,L,C=float(s.N[j]),float(s.low20[j]),float(s.values[j,3])
                ready=int(s.run[j])>=20 and h.ref.positive(N) and h.ref.positive(L)
                if not ready: reason='insufficient_or_gap_history20'
                else:
                    row.update(N_u=N,low20_u=L,u_close=C,label_history_ready20=1)
                    reason='economics_unresolved'
                    if h.ref.qualified_economics(e):
                        try:
                            row['multiplier']=float(e['contract_multiplier'])
                            for scenario in ('base','stress'):
                                unit=h.kernel.unit_estimate(C,N,e,scenario,'NARROW')
                                row[scenario+'_u_fee_roundtrip_per_lot']=unit['fee_roundtrip_per_lot']
                                row[scenario+'_u_slippage_roundtrip_per_lot']=unit['buy']['slippage_per_lot']+unit['sell']['slippage_per_lot']
                            if not anchor: reason='no_accepted_u_anchor'
                            elif u+1<len(calendar) and (u+1>=expiry or (e.get('listed_date') and calendar[u+1]<e['listed_date'])):
                                reason='known_entry_ineligible_lifecycle'
                            elif capacity_state!='known_roundtrip_capacity': reason=capacity_state
                            else: reason='';row['u_action_eligible']=1
                        except ValueError:
                            reason='unrepresentable_u_cost_quote'
            row['u_ineligibility_reason']=reason
            own,_,own_state=h.own.own11(s,j); row['own_feature_state']=own_state
            raw=np.full(26,np.nan)
            if own is not None: raw[:11]=own
            raw[11:24]=h.own.maturity13(pool,epoch,s,j)
            if h.ref.positive(row['N_u']):
                denominator=2*row['N_u']*row.get('multiplier',math.nan)
                if h.ref.positive(denominator):
                    raw[24]=(row.get('stress_u_fee_roundtrip_per_lot',math.nan)+row.get('stress_u_slippage_roundtrip_per_lot',math.nan))/denominator
                raw[25]=(row['u_close']-row['low20_u'])/(2*row['N_u'])
            if np.isinf(raw).any(): raise ValueError('infinite causal action feature')
            candidates.append(row);raw_rows.append(dict(row,raw26=raw.tolist()))
    return dict(u_index=u,u_date=day,mothers=mothers,candidates=candidates,raw_rows=raw_rows,
                references=references,statuses=statuses,D_context=dict(D_context))


def infer_scores(raw_rows, model, scaler):
    """Pure frozen main2023 transform; retain every candidate and missing flag."""
    order=COMMON+[v+'_missing' for v in COMMON]
    if any(v.get('scope')!='main' or v.get('cutoff')!='2023-01-01' for v in (model,scaler)):
        raise ValueError('fixed original main2023 model/scaler required')
    if model.get('feature_names')!=order or scaler.get('feature_names')!=order or scaler['common']['columns']!=COMMON:
        raise ValueError('original26/52 feature order mismatch')
    coef=np.asarray(model['coef'],float); mu=np.asarray(scaler['common']['mean'],float); sd=np.asarray(scaler['common']['scale'],float)
    if (coef.shape!=(52,) or mu.shape!=(26,) or sd.shape!=(26,) or not np.isfinite(coef).all()
            or not np.isfinite(mu).all() or not np.isfinite(sd).all() or not (sd>0).all()
            or not math.isfinite(float(model['intercept']))): raise ValueError('invalid fixed model/scaler')
    rows=list(raw_rows)
    if not rows: return []
    raw=np.asarray([r['raw26'] for r in rows],float)
    if raw.shape!=(len(rows),26): raise ValueError('raw26 shape mismatch')
    z=_helpers().score(raw,scaler); scores=z@coef+float(model['intercept'])
    if not np.isfinite(scores).all(): raise ValueError('nonfinite frozen prediction')
    return [dict(r,score=float(s),design52=v.tolist(),scope='main',cutoff='2023-01-01')
            for r,s,v in zip(rows,scores,z)]


def select_u(observations, scores, dates, *, D_context):
    """Original156 selection and original157 effective boundary; no cash replay."""
    u=observations['u_index']; calendar=_calendar(dates,u,D_context); h=_helpers()
    prior=observations['D_context']
    if D_context['confirmed'] and (not prior.get('confirmed') or
            any(prior.get(k)!=D_context.get(k) for k in ('D_index','D_date'))):
        raise ValueError('confirmed D requires observations built under the same confirmed context')
    result=h.choose.select_full_pool(observations['mothers'],scores,calendar,calendar[u])
    lookup={r['action_id']:r for r in observations['candidates']}; signals=[]
    for choice in result['choices']:
        if not choice['selected']: continue
        r=lookup[choice['chosen_action_id']]
        fields=('event_id','mother_event_id','action_sequence_index','product_id','family_id','u_date',
                'u_index','D_index','reference_epoch','anchor_epoch','label_history_ready20','N_u',
                'low20_u','u_close','history_run','lifecycle_index','entry_capacity_qty','u_gross_capacity_qty',
                'source_lifecycle_target_date','source_lifecycle_state')
        signals.append(dict({k:r[k] for k in fields},potential=1,score=choice['score'],
                            arm='VOLUNTARY_RESELECT',control_id='VOLUNTARY_RESELECT',policy='NARROW',cutoff='2023-01-01'))
    if signals:
        signals=h.apply_boundaries(pd.DataFrame(signals),result['boundaries']).to_dict('records')
    result['signals']=signals
    result['references']=dict(observations['references'])
    result['prepared']=({u:signals},{u:dict(observations['references'])})
    result['statuses']=observations['statuses']
    return result
