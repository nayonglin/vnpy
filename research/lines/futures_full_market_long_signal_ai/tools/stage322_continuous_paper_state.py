"""Thin pure-state bridge for accepted131; no CLI, data reads, fit or scheduler.

Caller321 owns receipt/T0/deadline checks. The caller supplies the accepted
kernel, already received market view, confirmed calendar and as-of economics.
Only a private globals dictionary changes; original functions remain untouched.
"""
from __future__ import annotations
from bisect import bisect_left
from copy import deepcopy
import hashlib
import json
import math
import types

SCHEMA='stage322_continuous_paper_state_v1'
LEDGER_FIELDS=('initial','realized','fees','slippage','positions','closed','fills','capacity_audit')
LINEAGE=('source_lifecycle_target_date','source_lifecycle_state','K_target_date','K_state',
         'effective_lifecycle_target_date','expiry_state')
ECON_FIELDS=('event_id','family_id','product_id','reference_epoch','anchor_epoch','u_index','u_date','D_index',
             'N_u','low20_u','u_close','entry_capacity_qty','round_lot','unit_risk_u','unit_margin_u',
             'unit_fee_reserve_u','target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap',
             'original_qty_cap','capacity_entry_qty_u','allocated_risk','allocated_buffered_margin',
             'allocated_fee','budget_state')

def _clean(value):
    if isinstance(value,dict):return {str(k):_clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_clean(v) for v in value]
    if isinstance(value,(set,frozenset)):return sorted(_clean(v) for v in value)
    if hasattr(value,'item'):return _clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if value is None or isinstance(value,(str,int,float,bool)):return value
    raise TypeError('state value is not JSON-safe: '+type(value).__name__)

def _canonical(value):return json.dumps(_clean(value),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def _hash(value):return hashlib.sha256(_canonical(value).encode()).hexdigest()

def _code_identity(code):
    # marshal's reference flags may change when a nested CodeType is retained
    # by FunctionType. Hash stable code fields, not that serialization detail.
    def constant(x):
        if isinstance(x,types.CodeType):return _code_identity(x)
        if isinstance(x,tuple):return [constant(v) for v in x]
        return x
    return _hash(dict(bytecode=code.co_code.hex(),constants=[constant(x) for x in code.co_consts],
        names=code.co_names,variables=code.co_varnames,free=code.co_freevars,cells=code.co_cellvars,
        args=[code.co_argcount,code.co_posonlyargcount,code.co_kwonlyargcount],flags=code.co_flags))

def _kernel_identity(kernel):
    run=kernel.run_cash_account;g=run.__globals__
    names=('reserve_capped','anchor_request','execution_quantity','adverse_quote','insolvency_flag',
           'next_boundary','reduction_targets','select_family_candidates')
    return dict(run=_code_identity(run.__code__),
        functions={n:_code_identity(g[n].__code__) for n in names},
        constants={n:g[n] for n in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER')},
        costs=deepcopy(kernel.ref.SCENARIOS))

def _validate(state,kernel=None):
    if state.get('schema')!=SCHEMA or state.get('phase') not in ('awaiting_u','awaiting_D'):
        raise ValueError('invalid paper state schema/phase')
    if state['scenario'] not in ('base','stress') or not state['account_id']:
        raise ValueError('invalid paper scenario/account')
    ledger=state['ledger']
    if (ledger['scenario'],ledger['account_id'])!=(state['scenario'],state['account_id']):
        raise ValueError('paper scenario/account crossed')
    if ledger['initial']!=1000000. or state['policy']!='NARROW':raise ValueError('frozen initial/policy changed')
    if kernel is not None and _kernel_identity(kernel)!=state['kernel_identity']:raise ValueError('paper kernel identity changed')
    if state['phase']=='awaiting_D':
        seal=state.get('sealed')
        if not seal or seal['u_index']!=state['last_u'] or seal['D_index']!=state['last_u']+1:
            raise ValueError('invalid sealed u/D')
        if seal['ledger_sha256']!=_hash(ledger):raise ValueError('sealed ledger changed')
        if seal['pending_sha256']!=_hash(state['pending']):raise ValueError('sealed pending changed')

def new_state(*,scenario,account_id,start_u,base_kernel,initial=1000000.):
    if int(start_u)!=start_u or start_u<0 or float(initial)!=float(base_kernel.INITIAL) or initial!=1000000.:
        raise ValueError('frozen initial/start_u required')
    ledger=dict(initial=float(initial),realized=0.,fees=0.,slippage=0.,positions={},closed=[],fills=[],
                capacity_audit=[],capacity_gross=[],capacity_unknown_roots=[],scenario=scenario,account_id=account_id)
    state=dict(schema=SCHEMA,policy='NARROW',scenario=scenario,account_id=account_id,start_u=int(start_u),
        phase='awaiting_u',last_u=None,last_D=None,next_u=int(start_u),ever_insolvent=False,
        kernel_identity=_kernel_identity(base_kernel),ledger=ledger,pending=[],budgets=[],daily=[],position_days=[],
        entry_execution_unknown=[],calendar=[],sealed=None,last_advance=None)
    _validate(state,base_kernel);return state

class _Through:
    def __init__(self,market,through):self.market=market;self.through=through
    def _get(self,name,epoch,k):
        if k>self.through:raise ValueError('market request after causal cutoff')
        return getattr(self.market,name)(epoch,k)
    def bar(self,epoch,k):return self._get('bar',epoch,k)
    def indicator(self,epoch,k):return self._get('indicator',epoch,k)

def _calendar(state,dates,D):
    dates=list(dates)
    if D>=len(dates) or len(set(dates))!=len(dates) or dates!=sorted(dates):raise ValueError('confirmed ordered D calendar required')
    if dates[:len(state['calendar'])]!=state['calendar']:raise ValueError('calendar must append, not rewrite')
    return dates

def _bind_expiry(row,dates,*,position=False):
    # Targets are sealed lineage. len(calendar) from historical finite samples
    # must never become a fictitious real expiry in a streaming view.
    targets=[row.get(k) for k in ('source_lifecycle_target_date','K_target_date')]
    targets=[x for x in targets if isinstance(x,str) and x]
    target=row.get('effective_lifecycle_target_date')
    if target and targets and target!=min(targets):raise ValueError('sealed expiry target changed')
    target=target or (min(targets) if targets else None)
    if target:
        j=bisect_left(dates,target);pending=j==len(dates)
        row['effective_lifecycle_target_date']=target;row['expiry_state']='pending_calendar' if pending else 'known_calendar'
        row['expiry' if position else 'lifecycle_index']=len(dates)+1 if pending else j
    return row

def _economic_scope(state,candidates,economics):
    epochs={r['reference_epoch'] for r in candidates}|{p['epoch'] for p in state['ledger']['positions'].values()}
    return {e:economics.get(e,{}) for e in sorted(epochs)}

def _reserve_projection(rows):return [{k:r[k] for k in ECON_FIELDS if k in r} for r in rows]
def _cell(value):return (lambda:value).__closure__[0]

def _restore_ledger(state,kernel,market,dates,economics,candidates):
    metadata={r['event_id']:r for r in candidates}
    class LocalLedger(kernel.CapacityLedger):
        def enter(self,root,*args,**kwargs):
            root=dict(root)
            for key in LINEAGE:
                if key in metadata.get(root['event_id'],{}):root[key]=metadata[root['event_id']][key]
            _bind_expiry(root,dates,position=True)
            return super().enter(root,*args,**kwargs)
    ledger=LocalLedger(state['ledger']['initial'],market,dates,economics,state['account_id'])
    for key in LEDGER_FIELDS:setattr(ledger,key,deepcopy(state['ledger'][key]))
    ledger.capacity_gross={(r[0],int(r[1])):int(r[2]) for r in state['ledger']['capacity_gross']}
    ledger.capacity_unknown_roots=set(state['ledger']['capacity_unknown_roots'])
    byid={r['budget_id']:r for r in state['budgets']}
    for p in ledger.positions.values():
        reduction=p.get('reduction_record')
        if reduction and reduction['budget_id'] in byid:p['reduction_record']=byid[reduction['budget_id']]
        _bind_expiry(p,dates,position=True)
    return ledger

def _snapshot(ledger,state):
    result={k:deepcopy(getattr(ledger,k)) for k in LEDGER_FIELDS}
    result.update(capacity_gross=[[e,k,q] for (e,k),q in sorted(ledger.capacity_gross.items())],
        capacity_unknown_roots=sorted(ledger.capacity_unknown_roots),scenario=state['scenario'],account_id=state['account_id'])
    return _clean(result)

def _globals(kernel,state,ledger,dates):
    g=dict(kernel.run_cash_account.__globals__);original_anchor=g['anchor_request'];original_insolvent=g['insolvency_flag']
    def anchor(p,reference,next_day):
        _bind_expiry(p,dates,position=True)
        return original_anchor(p,reference,next_day)
    g['anchor_request']=anchor
    g['insolvency_flag']=lambda previous,equity:original_insolvent(previous or state['ever_insolvent'],equity)
    return g

def _refresh(ledger,u,references,g):
    for p in ledger.positions.values():
        if not p['stale']:
            p['force_reason']=g['anchor_request'](p,references.get(p['product_id']),u+1)
            if p['force_reason'] and not p.get('anchor_request_date'):
                p['anchor_request_date']=ledger.dates[u];p['anchor_request_reason']=p['force_reason']

def _upsert(state,rows):
    byid={r['budget_id']:r for r in state['budgets']}
    for row in rows:
        key=row['budget_id']
        if key in byid:
            if byid[key]['u_date']!=row['u_date']:raise ValueError('budget identity reused on another u')
            byid[key].update(_clean(row))
        else:
            value=_clean(row);state['budgets'].append(value);byid[key]=value
    for p in state['ledger']['positions'].values():
        r=p.get('reduction_record')
        if r and r['budget_id'] in byid:p['reduction_record']=byid[r['budget_id']]
    return byid

def seal_u(state,*,u_index,prepared,market,dates,economics,base_kernel):
    _validate(state,base_kernel)
    if state['phase']!='awaiting_u' or u_index!=state['next_u']:raise ValueError('u already sealed or not next own-state u')
    s=deepcopy(state);u=int(u_index);D=u+1;dates=_calendar(s,dates,D)
    potential,references=prepared;candidates=_clean(deepcopy(potential.get(u,[])));urefs=_clean(references.get(u,{}))
    if any(int(r['u_index'])!=u or int(r['D_index'])!=D or r['u_date']!=dates[u] for r in candidates):raise ValueError('candidate u/D mismatch')
    source=dict(candidates=candidates,references=urefs)
    effective=[_bind_expiry(deepcopy(r),dates) for r in candidates]
    view=_Through(market,u);ledger=_restore_ledger(s,base_kernel,view,dates,economics,effective)
    g=_globals(base_kernel,s,ledger,dates);_refresh(ledger,u,urefs,g)
    rows=[];captured=[];original_reserve=g['reserve_capped']
    def reserve(*args,**kwargs):
        result=original_reserve(*args,**kwargs);captured.append(deepcopy(_reserve_projection(result)));return result
    g['reserve_capped']=reserve
    constants=[x for x in base_kernel.run_cash_account.__code__.co_consts if isinstance(x,types.CodeType) and x.co_name=='prepare']
    if len(constants)!=1:raise ValueError('accepted131 prepare code not found')
    code=constants[0]
    values=dict(account_id=s['account_id'],budgets=rows,dates=dates,economics=economics,end=D,
        insolvent=s['ever_insolvent'],ledger=ledger,policy='NARROW',potential={u:effective},scenario=s['scenario'])
    if set(code.co_freevars)!=set(values):raise ValueError('accepted131 explicit prepare closure changed')
    cells={k:_cell(v) for k,v in values.items()}
    prepare=types.FunctionType(code,g,'prepare',(False,),tuple(cells[k] for k in code.co_freevars))
    pending=prepare(u,s['last_D'] is None)
    if len(captured)!=1:raise ValueError('expected one original reserve call')
    s['ever_insolvent']=bool(cells['insolvent'].cell_contents);s['ledger']=_snapshot(ledger,s)
    byid=_upsert(s,rows);s['pending']=[byid[r['budget_id']] for r in pending]
    if s['daily'] and s['daily'][-1]['date']==dates[u]:
        row=s['daily'][-1];reservation=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in pending)
        row.update(new_order_reserve=reservation,total_reserve=row['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),
            new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),
            new_order_fee_reserve=sum(r['allocated_fee'] for r in pending))
        for p in s['position_days']:
            if p['date']==dates[u] and p['root_id'] in ledger.positions:p['reduce_to_next']=ledger.positions[p['root_id']].get('reduce_to')
    s.update(last_u=u,calendar=dates,phase='awaiting_D')
    s['sealed']=dict(u_index=u,D_index=D,u_date=dates[u],D_date=dates[D],source_prepared=source,
        source_prepared_sha256=_hash(source),economics_sha256=_hash(_economic_scope(s,candidates,economics)),
        reserve_economic_sha256=_hash(captured[0]),ledger_sha256=_hash(s['ledger']),
        pending_sha256=_hash(s['pending']),budget_ids=[r['budget_id'] for r in rows])
    _validate(s,base_kernel);return _clean(s)

def advance_D(state,*,D_index,references,market,dates,economics,base_kernel):
    _validate(state,base_kernel)
    if state['phase']!='awaiting_D' or D_index!=state['sealed']['D_index'] or D_index==state['last_D']:
        raise ValueError('D not sealed next session or already advanced')
    s=deepcopy(state);seal=s['sealed'];u=seal['u_index'];D=int(D_index);dates=_calendar(s,dates,D)
    source=seal['source_prepared']
    if _hash(source)!=seal['source_prepared_sha256']:raise ValueError('sealed prepared source changed')
    if _hash(_economic_scope(s,source['candidates'],economics))!=seal['economics_sha256']:raise ValueError('sealed economics changed')
    effective=[_bind_expiry(deepcopy(r),dates) for r in source['candidates']]
    view=_Through(market,D);ledger=_restore_ledger(s,base_kernel,view,dates,economics,effective)
    g=_globals(base_kernel,s,ledger,dates);_refresh(ledger,u,source['references'],g)
    original_reserve=g['reserve_capped'];calls=[]
    def reserve(*args,**kwargs):
        result=original_reserve(*args,**kwargs)
        if _hash(_reserve_projection(result))!=seal['reserve_economic_sha256']:raise ValueError('recomputed u budget differs from sealed economics')
        calls.append(1);return result
    def factory(initial,*args,**kwargs):
        if float(initial)!=ledger.initial:raise ValueError('single-D run attempted initial reset')
        return ledger
    g['reserve_capped']=reserve;g['CapacityLedger']=factory
    original=base_kernel.run_cash_account
    run=types.FunctionType(original.__code__,g,original.__name__,original.__defaults__,original.__closure__)
    run.__kwdefaults__=deepcopy(original.__kwdefaults__)
    drefs=references.get(D,references) if isinstance(references,dict) else references
    book=run(None,view,dates,economics,s['scenario'],s['account_id'],D,D,initial=ledger.initial,
        prepared=({u:effective},{D:drefs}),policy='NARROW')
    if len(calls)!=1:raise ValueError('single-D run must verify one sealed reserve')
    oldids={r['budget_id']:r for r in s['budgets']}
    for row in book['budgets']:
        # A singleton run calls its pre-window prepare with True. Preserve the
        # already sealed continuous-u metadata; economic fields were checked.
        old=oldids.get(row['budget_id'])
        if old is not None:row['pre_window_reservation']=old['pre_window_reservation']
    s['ledger']=_snapshot(ledger,s);_upsert(s,book['budgets'])
    s['daily'].extend(_clean(book['daily']));s['position_days'].extend(_clean(book['position_days']))
    s['entry_execution_unknown'].extend(_clean(book['entry_execution_unknown']))
    s['ever_insolvent']=bool(s['ever_insolvent'] or book['daily'][-1]['ever_insolvent'])
    s.update(last_D=D,next_u=D,phase='awaiting_u',calendar=dates,pending=[],sealed=None)
    s['last_advance']=dict(D_index=D,D_date=dates[D],verified_u=u,
        source_prepared_sha256=seal['source_prepared_sha256'],reserve_economic_sha256=seal['reserve_economic_sha256'],
        economics_sha256=seal['economics_sha256'],ledger_sha256=_hash(s['ledger']))
    _validate(s,base_kernel);return _clean(s)

def export_state(state):
    return _canonical(dict(schema=SCHEMA,state=state,sha256=_hash(state)))

def restore_state(payload):
    obj=json.loads(payload) if isinstance(payload,(str,bytes,bytearray)) else deepcopy(payload)
    if obj.get('schema')!=SCHEMA or _hash(obj['state'])!=obj['sha256']:raise ValueError('paper state digest mismatch')
    state=obj['state'];_validate(state)
    byid={r['budget_id']:r for r in state['budgets']}
    state['pending']=[byid[r['budget_id']] for r in state['pending']]
    for p in state['ledger']['positions'].values():
        r=p.get('reduction_record')
        if r and r['budget_id'] in byid:p['reduction_record']=byid[r['budget_id']]
    return state
