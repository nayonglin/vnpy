"""Frozen311 private integer reservation callback; no data reads or actual CLI.

The caller supplies its configured131 kernel. Its run function code/defaults
remain unchanged; only a copied globals dictionary receives this callback.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal,localcontext,ROUND_CEILING,ROUND_FLOOR,ROUND_HALF_EVEN
import math
import time
import types
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp

PROTOCOL_SHA='f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259'
DELTA=Decimal('0.000001')
LIMIT=2**50
INTEGER_TOLERANCE=1e-7
GRID_ORDER='old float r/m/d/score/caps -> Decimal(str(value)); integer L multiplied in Decimal; no extra float coefficient product'


def dec(value):
    value=float(value)
    if not math.isfinite(value):raise ValueError('nonfinite_original_float')
    return Decimal(str(value))


def build_problem(rows,equity,F0,M0,economics):
    """Roundtrip old float values first, then multiply L/score/d in Decimal."""
    E=float(equity);R=max(0.,.02*E-float(F0));M=max(0.,.25*E-float(M0));single=.0025*E
    if not math.isfinite(E) or E<=0:raise ValueError('nonpositive_equity_for_integer_problem')
    ordered=sorted(enumerate(rows),key=lambda z:tuple(str(z[1][v]) for v in ('family_id','product_id','reference_epoch','event_id')))
    if len({str(r['family_id']) for r in rows})!=len(rows):raise ValueError('accepted_family_not_unique')
    with localcontext() as context:
        context.prec=80
        p=dict(delta_cny=str(DELTA),grid_operation_order=GRID_ORDER,equity=E,held_F0=float(F0),held_buffered_margin=float(M0),
            unquantized_caps=dict(single=single,risk=R,margin=M),
            single_risk_cap=int((dec(single)/DELTA).to_integral_value(rounding=ROUND_FLOOR)),
            risk_cap=int((dec(R)/DELTA).to_integral_value(rounding=ROUND_FLOOR)),
            margin_cap=int((dec(M)/DELTA).to_integral_value(rounding=ROUND_FLOOR)),variables=[],A=[],B=[],C=[],upper=[])
        for source_index,row in ordered:
            e=economics[row['reference_epoch']];L=int(row['round_lot']);cap=int(row['entry_capacity_qty'])
            if L<=0 or L!=float(row['round_lot']) or L!=float(e['round_lot']) or cap<0 or cap!=float(row['entry_capacity_qty']):
                raise ValueError('lot_or_capacity_not_nonnegative_integer')
            s=float(row['score']);d=.25*float(row['N_u'])*float(e['contract_multiplier'])
            r=float(row['unit_risk_u']);m=float(row['unit_margin_u']);fee=float(row['unit_fee_reserve_u'])
            if not all(math.isfinite(v) and v>0 for v in (s,d,r,m)) or not math.isfinite(fee) or fee<0:
                raise ValueError('invalid_frozen_score_or_units')
            A=int((Decimal(L)*dec(r)/DELTA).to_integral_value(rounding=ROUND_CEILING))
            B=int((Decimal(L)*dec(m)/DELTA).to_integral_value(rounding=ROUND_CEILING))
            C=int((Decimal(L)*dec(s)*dec(d)/DELTA).to_integral_value(rounding=ROUND_HALF_EVEN))
            upper=min(cap//L,p['single_risk_cap']//A,p['risk_cap']//A,p['margin_cap']//B)
            p['variables'].append(dict(source_index=source_index,**{v:str(row[v]) for v in ('family_id','product_id','reference_epoch','event_id')},
                L=L,score=s,d=d,r=r,m=m,fee=fee,u_capacity=cap,original_target_qty_unscaled=float(row['target_qty_unscaled']),
                original_target_qty_prefloor=float(row['target_qty_prefloor']),original_joint_scale=float(row['joint_scale']),
                original_qty_cap=int(row['qty_cap']),original_unfloored_qty_cap=int(row['original_qty_cap']),
                original_allocated_risk=float(row['allocated_risk']),original_allocated_margin=float(row['allocated_buffered_margin']),
                original_allocated_fee=float(row['allocated_fee'])))
            for key,value in (('A',A),('B',B),('C',C),('upper',upper)):p[key].append(value)
    validate_problem(p)
    return p


def validate_problem(p):
    size=len(p['upper'])
    if any(len(p[k])!=size for k in ('A','B','C','variables')):raise ValueError('integer_problem_shape')
    values=[p['risk_cap'],p['margin_cap'],p['single_risk_cap']]+p['A']+p['B']+p['C']+p['upper']
    values += [sum(abs(c)*u for c,u in zip(p[k],p['upper'])) for k in ('A','B','C')]
    if any(not isinstance(v,int) or abs(v)>=LIMIT for v in values):raise ValueError('unsupported_integer_coefficient_or_possible_sum')
    if any(v<0 for v in p['upper']) or p['risk_cap']<0 or p['margin_cap']<0:raise ValueError('negative_integer_bound')


def feasible(p,k,equalities=()):
    return (len(k)==len(p['upper']) and all(0<=x<=u for x,u in zip(k,p['upper']))
        and sum(a*x for a,x in zip(p['A'],k))<=p['risk_cap']
        and sum(b*x for b,x in zip(p['B'],k))<=p['margin_cap']
        and all(sum(a*x for a,x in zip(coef,k))==rhs for coef,rhs in equalities))


def audit_number(value):
    if value is None:return None
    result=float(value)
    return result if math.isfinite(result) else str(result)


def solve_problem(p,solver_stages=None):
    """Primary and lex stages share one wall/node budget; never fallback."""
    validate_problem(p);stages=[] if solver_stages is None else solver_stages;began=time.perf_counter();deadline=began+10.;nodes=0
    n=len(p['upper']);upper=list(p['upper'])
    if all(c>=0 for c in p['C']) and feasible(p,upper):
        stages.append(dict(kind='analytic',stage='primary_and_lex',status=0,success=True,k=upper,
            integer_objective=sum(c*x for c,x in zip(p['C'],upper)),reason='all_upper_feasible_and_C_nonnegative',
            elapsed_seconds=time.perf_counter()-began))
        k=upper
    else:
        def solve_stage(objective,equalities,name,prefix):
            nonlocal nodes
            remaining=deadline-time.perf_counter();remaining_nodes=100000-nodes
            if remaining<=0 or remaining_nodes<=0:raise RuntimeError('shared_batch_solver_budget_exhausted')
            options=dict(presolve=True,mip_rel_gap=0.,time_limit=remaining,node_limit=remaining_nodes)
            stage=dict(kind='milp',stage=name,objective=list(objective),prefix=list(prefix),
                equalities=[dict(coefficients=list(a),rhs=int(b)) for a,b in equalities],options=options,status='started')
            stages.append(stage);started=time.perf_counter()
            try:
                matrix=[p['A'],p['B']]+[list(a) for a,b in equalities]
                lower=[-np.inf,-np.inf]+[b for a,b in equalities]
                high=[p['risk_cap'],p['margin_cap']]+[b for a,b in equalities]
                result=milp(np.asarray(objective,dtype=float),integrality=np.ones(n,dtype=np.int8),
                    bounds=Bounds(np.zeros(n),np.asarray(upper,dtype=float)),
                    constraints=LinearConstraint(np.asarray(matrix,dtype=float),np.asarray(lower,dtype=float),np.asarray(high,dtype=float)),options=options)
                stage.update(status=int(result.status),success=bool(result.success),message=str(result.message),
                    x=None if result.x is None else [audit_number(v) for v in result.x],fun=audit_number(result.fun),
                    dual_bound=audit_number(getattr(result,'mip_dual_bound',None)),mip_gap=audit_number(getattr(result,'mip_gap',None)),
                    node_count=audit_number(getattr(result,'mip_node_count',None)))
                if result.status!=0 or not result.success:raise RuntimeError('solver_status_not_optimal')
                values=np.asarray(result.x,dtype=float)
                if values.shape!=(n,) or not np.isfinite(values).all():raise RuntimeError('solver_x_nonfinite_or_shape')
                k=[int(round(v)) for v in values]
                if any(abs(float(v)-x)>INTEGER_TOLERANCE for v,x in zip(values,k)):raise RuntimeError('solver_integer_distance')
                if not feasible(p,k,equalities):raise RuntimeError('python_integer_constraint_failure')
                I=sum(a*x for a,x in zip(objective,k));fun=float(result.fun);bound=float(result.mip_dual_bound);gap=float(result.mip_gap)
                count=float(result.mip_node_count)
                if not all(math.isfinite(v) for v in (fun,bound,gap,count)) or gap<0 or count<0 or int(count)!=count:
                    raise RuntimeError('solver_nonfinite_certificate_or_node_count')
                nodes+=int(count)
                with localcontext() as context:
                    context.prec=80
                    absolute=Decimal(I)-dec(bound);fun_error=abs(dec(fun)-Decimal(I))
                    diagnostic=abs(dec(gap)*abs(dec(fun))-abs(dec(fun)-dec(bound))) if fun!=0 else Decimal(0)
                    stage.update(k=k,integer_objective=I,absolute_integer_bound_gap=float(absolute),
                        fun_integer_error=float(fun_error),relative_gap_absolute_consistency_error=float(diagnostic),
                        relative_gap_semantics='diagnostic only; zero fun uses absolute certificate',
                        resource_use=dict(risk=sum(a*x for a,x in zip(p['A'],k)),margin=sum(b*x for b,x in zip(p['B'],k))))
                    if not Decimal(0)<=absolute<Decimal('.5'):raise RuntimeError('absolute_integer_bound_certificate')
                    if fun_error>=Decimal('.5') or diagnostic>=Decimal('.5'):raise RuntimeError('fun_or_relative_gap_inconsistent')
                if nodes>100000 or time.perf_counter()>deadline:raise RuntimeError('shared_batch_solver_budget_exceeded')
                stage['certificate_accepted']=True
                return k
            except Exception as error:
                stage['failure']=dict(type=type(error).__name__,reason=str(error));raise
            finally:stage['elapsed_seconds']=time.perf_counter()-started
        k=solve_stage([-c for c in p['C']],[],'primary',[]);optimum=sum(c*x for c,x in zip(p['C'],k));equalities=[(list(p['C']),optimum)];prefix=[]
        for i in range(n):
            row=[0]*n;row[i]=1
            if upper[i]==0:
                stages.append(dict(kind='analytic',stage='lex_'+str(i),status=0,success=True,prefix=list(prefix),
                    k=list(k),integer_objective=0,reason='individual_upper_zero'))
            else:
                objective=[0]*n;objective[i]=-1
                k=solve_stage(objective,equalities,'lex_'+str(i),prefix)
            prefix.append(k[i]);equalities.append((row,k[i]))
        if not feasible(p,k) or sum(c*x for c,x in zip(p['C'],k))!=optimum:raise RuntimeError('final_primary_or_feasibility_mismatch')
    return dict(k=k,n=[v['L']*x for v,x in zip(p['variables'],k)],objective=sum(c*x for c,x in zip(p['C'],k)),
        solver_stages=stages,analytic=bool(stages and stages[0]['kind']=='analytic'),total_nodes=nodes,
        total_seconds=time.perf_counter()-began)


def apply_solution(rows,p,solution):
    result=deepcopy(rows);numbers=solution['n']
    if not feasible(p,solution['k']):raise RuntimeError('final_integer_resources')
    with localcontext() as context:
        context.prec=80
        raw_R=Decimal(0);raw_M=Decimal(0)
        for v,n in zip(p['variables'],numbers):
            risk=Decimal(n)*dec(v['r']);margin=Decimal(n)*dec(v['m'])
            if n<0 or n%v['L'] or n>v['u_capacity'] or risk>dec(p['unquantized_caps']['single']):
                raise RuntimeError('unquantized_single_or_capacity_failure')
            raw_R+=risk;raw_M+=margin
            row=result[v['source_index']]
            row.update(qty_cap=int(n),allocated_risk=n*v['r'],allocated_buffered_margin=n*v['m'],allocated_fee=n*v['fee'],
                budget_state='joint_integer_reserved' if n else 'joint_integer_zero_allocation',allocation_mode='joint_integer')
            if row['allocated_risk']>p['unquantized_caps']['single']:
                raise RuntimeError('final_float_single_resource_failure')
        if raw_R>dec(p['unquantized_caps']['risk']) or raw_M>dec(p['unquantized_caps']['margin']):
            raise RuntimeError('unquantized_total_resource_failure')
    if (math.fsum(r['allocated_risk'] for r in result)>p['unquantized_caps']['risk']
            or math.fsum(r['allocated_buffered_margin'] for r in result)>p['unquantized_caps']['margin']):
        raise RuntimeError('final_float_resource_failure')
    return result


class PrivateAllocator:
    def __init__(self,legacy,dates,scenario,account_id,start,end):
        self.legacy=legacy;self.dates=dates;self.scenario=scenario;self.account_id=account_id
        self.expected=list(range(start-1 if start>0 else 0,end));self.audit=[]

    def reserve(self,candidates,equity,F0,M0,economics,scenario,policy='NARROW'):
        at=len(self.audit)
        if at>=len(self.expected):raise RuntimeError('unexpected_extra_reservation_call')
        u=self.expected[at]
        record=dict(batch_index=at,u_index=u,u_date=str(self.dates[u]),account_id=self.account_id,scenario=scenario,
            equity=float(equity),held_F0=float(F0),held_buffered_margin=float(M0),status='started',mode='legacy_empty',
            old_rows=[],actual_rows=[],problem=None,solver_stages=[])
        self.audit.append(record)
        try:
            if scenario!=self.scenario or policy!='NARROW':raise ValueError('account_scenario_or_policy_mismatch')
            if any(int(c['u_index'])!=u or str(c['u_date'])!=str(self.dates[u]) for c in candidates):
                raise ValueError('prepare_call_index_disagrees_with_candidate_u')
            old=self.legacy(candidates,equity,F0,M0,economics,scenario,policy)
            if len(old)!=len(candidates):raise RuntimeError('legacy_reservation_rows_changed')
            record['old_rows']=deepcopy(old);actual=old
            families={r['family_id'] for r in old}
            if old:
                scales={float(r['joint_scale']) for r in old}
                if len(scales)!=1 or not all(math.isfinite(s) for s in scales):raise ValueError('legacy_common_scale_invalid')
                scale=next(iter(scales));record['original_joint_scale']=scale
                if len(families)<2:record['mode']='legacy_single_family'
                elif not scale<1:record['mode']='legacy_scale_one'
                else:
                    record['mode']='joint_integer';record['problem']=build_problem(old,equity,F0,M0,economics)
                    solution=solve_problem(record['problem'],record['solver_stages']);record['solution']={k:v for k,v in solution.items() if k!='solver_stages'}
                    actual=apply_solution(old,record['problem'],solution)
            record['actual_rows']=deepcopy(actual);record['status']='completed'
            record['changed_qty']=any(a['qty_cap']!=b['qty_cap'] for a,b in zip(old,actual))
            record['changed_freeze']=any(any(a[k]!=b[k] for k in ('allocated_risk','allocated_buffered_margin','allocated_fee')) for a,b in zip(old,actual))
            return actual
        except Exception as error:
            record['status']='failed';record['failure']=dict(type=type(error).__name__,reason=str(error));raise

    def diagnostics(self):
        stages=[s for a in self.audit for s in a['solver_stages']]
        return dict(batch_calls=len(self.audit),expected_batch_calls=len(self.expected),
            triggered_batches=sum(a['mode']=='joint_integer' for a in self.audit),
            changed_qty_batches=sum(bool(a.get('changed_qty')) for a in self.audit),
            changed_freeze_batches=sum(bool(a.get('changed_freeze')) for a in self.audit),
            solver_calls=sum(s['kind']=='milp' for s in stages),
            analytic_batches=sum(bool(a.get('solution',{}).get('analytic')) for a in self.audit))


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=1e6,prepared=None,*,policy='NARROW',base_kernel=None):
    if base_kernel is None:raise ValueError('caller_configured_base_kernel_required')
    if policy!='NARROW' or not 0<=start<=end<len(dates):raise ValueError('fixed_policy_or_account_window')
    original=base_kernel.run_cash_account;legacy=original.__globals__['reserve_capped']
    if legacy is not base_kernel.reserve_capped:raise ValueError('configured_kernel_callback_identity')
    allocator=PrivateAllocator(legacy,dates,scenario,account_id,start,end)
    private_globals=dict(original.__globals__);private_globals['reserve_capped']=allocator.reserve
    private=types.FunctionType(original.__code__,private_globals,original.__name__,original.__defaults__,original.__closure__)
    private.__kwdefaults__=None if original.__kwdefaults__ is None else dict(original.__kwdefaults__)
    try:
        book=private(signals,market,dates,economics,scenario,account_id,start,end,initial,prepared,policy=policy)
        if len(allocator.audit)!=len(allocator.expected):raise RuntimeError('reservation_call_count_mismatch')
        book['allocation_audit']=allocator.audit;book['allocation_diagnostics']=allocator.diagnostics()
        book['allocation_implementation']=dict(original_code_identity_preserved=private.__code__ is original.__code__,
            defaults_preserved=private.__defaults__==original.__defaults__,kwdefaults_preserved=private.__kwdefaults__==original.__kwdefaults__,
            private_globals_only=True,original_callback_unchanged=original.__globals__['reserve_capped'] is legacy,
            grid_operation_order=GRID_ORDER,protocol_sha256=PROTOCOL_SHA)
        return book
    except Exception as error:
        error.allocation_audit=allocator.audit;error.allocation_diagnostics=allocator.diagnostics();raise
