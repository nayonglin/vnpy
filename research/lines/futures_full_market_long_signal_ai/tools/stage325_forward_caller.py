"""Minimal320/321/322 caller. No data loader, CLI, T0 creation or new account.

observe_only never calls paper state methods. Future proposals stay inactive
until their actual321 receipt, containing the complete candidate budgets, is
classified timely. Caller327 owns actual authorization and source acquisition.
"""
from __future__ import annotations
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

TOOLS=Path(__file__).resolve().parent
SCHEMA='stage325_forward_caller_result_v1'
POLICY='PURE52_MAIN2023_VOLUNTARY_RESELECT_NARROW'
FILES=('stage320_causal_forward_core.py','stage321_forward_journal.py',
       'stage322_continuous_paper_state.py','stage325_forward_caller.py')

def _clean(value):
    if isinstance(value,dict):return {str(k):_clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_clean(v) for v in value]
    if hasattr(value,'tolist'):return _clean(value.tolist())
    if hasattr(value,'item'):return _clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if value is None or isinstance(value,(str,int,float,bool)):return value
    raise TypeError('caller cannot journal '+type(value).__name__)

def _bytes(value):return json.dumps(_clean(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def _hash(value):return hashlib.sha256(_bytes(value)).hexdigest()

@lru_cache(maxsize=1)
def _components():
    result={}
    for name,file in zip(('core','journal','paper'),FILES[:3]):
        spec=importlib.util.spec_from_file_location('stage325_'+name,TOOLS/file)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);result[name]=module
    return SimpleNamespace(**result)

def make_policy_identity(model,scaler,*,frozen_at=None):
    """Describe a caller-supplied freeze; does not create one or infer a T0."""
    return dict(schema='stage325_single_reference_identity_v1',policy=POLICY,frozen_at=frozen_at,
        model_content_sha256=_hash(model),scaler_content_sha256=_hash(scaler),
        source_sha256={name:hashlib.sha256((TOOLS/name).read_bytes()).hexdigest() for name in FILES})

def _identity(model,scaler,journal,identity):
    expected=make_policy_identity(model,scaler,frozen_at=identity.get('frozen_at'))
    if expected!=identity:raise ValueError('fixed policy/model/scaler/source identity mismatch')
    if journal.policy_hash!=hashlib.sha256(_bytes(identity)+b'\n').hexdigest():raise ValueError('journal policy identity mismatch')
    # Separate imports of the same real321 class are supported; a caller-made
    # receipt provider must not replace321's local UTC append implementation.
    actual=getattr(getattr(journal,'append',None),'__func__',None)
    if actual is None or actual.__code__!=_components().journal.ForwardJournal.append.__code__:
        raise ValueError('real321 ForwardJournal required')

def process_snapshot(snapshot,*,model,scaler,journal,policy_identity,mode='observe_only',states=None,base_kernel=None):
    """Process received u; explicit future states are never initialized here.

    Snapshot326 fields: u_index/u_date, dates/economics/products,
    series_by_epoch, market, D_context, source/version/source_receipt and clock
    {source_completed_at,D_open_at}. Adapter received_at is claimed metadata;
    actual receipt comes exclusively from321.append.recorded_at.
    """
    if mode not in ('observe_only','future'):raise ValueError('explicit observe_only/future mode required')
    if mode=='observe_only' and (states is not None or base_kernel is not None):raise ValueError('observe_only must be unfunded without state/kernel')
    if mode=='future' and snapshot.get('development_only') is not False:raise ValueError('development snapshot cannot become a future account')
    _identity(model,scaler,journal,policy_identity);c=_components()
    u=int(snapshot['u_index']);dates=list(snapshot['dates']);dc=dict(snapshot.get('D_context',dict(confirmed=False)))
    if u<0 or u>=len(dates) or snapshot['u_date']!=dates[u]:raise ValueError('snapshot u date/index mismatch')
    clock=dict(snapshot.get('clock') or {})
    complete=clock.get('source_completed_at',snapshot.get('completed_at'))
    opened=clock.get('D_open_at') if dc.get('confirmed') is True else None
    provenance=dict(u_index=u,u_date=dates[u],source=snapshot.get('source'),version=snapshot.get('version'),
        source_receipt=snapshot.get('source_receipt'),development_only=snapshot.get('development_only'),
        D_context=dc,clock=clock,claimed_adapter_received_at=snapshot.get('received_at'))
    token='snapshot/'+_hash(provenance)
    received=journal.append('input_snapshot',_clean(provenance),key=token+'/input')
    def gate(sealed=None):
        return c.journal.evaluate_clock(frozen_at=policy_identity['frozen_at'],source_completed_at=complete,
            received_at=received['recorded_at'],decision_sealed_at=sealed,D_open_at=opened)
    causal_clock=gate();counts=dict(new_state_calls=0,advance_D_calls=0,seal_u_calls=0,new_fit=0,
        old_control_replays=0,SQL=0)
    obs=c.core.build_u_observations(snapshot['series_by_epoch'],u,dates,snapshot['economics'],
        snapshot['products'],D_context=dc)
    current=deepcopy(states) if states is not None else None;state_problem=None
    if mode=='future':
        if current is None or base_kernel is None:state_problem='state_not_initialized'
        elif set(current)!= {'base','stress'}:raise ValueError('separate base/stress states required')
        else:
            if not causal_clock['forward_observation']:state_problem=causal_clock['status']
            for scenario,state in current.items():
                if state.get('scenario')!=scenario or state['ledger']['scenario']!=scenario:
                    raise ValueError('base/stress state crossed')
                if causal_clock['forward_observation']:
                    bound=state.get('caller_policy_sha256')
                    if bound is not None and bound!=journal.policy_hash:raise ValueError('paper state belongs to another frozen policy')
                    if bound is None and (state.get('last_u') is not None or state.get('last_D') is not None):
                        raise ValueError('noninitial paper state lacks caller policy binding')
                if state.get('phase')=='awaiting_D':
                    if state.get('sealed',{}).get('D_index')!=u:state_problem='sealed_D_not_current_u'
                elif state.get('phase')!='awaiting_u' or state.get('next_u')!=u:state_problem='state_continuity_gap'
            times=causal_clock['timestamps_utc']
            complete_at=c.journal._time(times['source_completed_at']);received_at=c.journal._time(times['received_at'])
            if complete_at is None:state_problem=state_problem or 'completion_clock_unknown'
            elif received_at<complete_at:state_problem=state_problem or 'received_before_completion'
            if not state_problem:
                # References come from the complete current-u observations,
                # before current-D facts change each scenario's own equity.
                for scenario,state in list(current.items()):
                    if state['phase']=='awaiting_D':
                        current[scenario]=c.paper.advance_D(state,D_index=u,references=obs['references'],
                            market=snapshot['market'],dates=dates,economics=snapshot['economics'],base_kernel=base_kernel)
                        counts['advance_D_calls']+=1
    scores=c.core.infer_scores(obs['raw_rows'],model,scaler)
    selected=c.core.select_u(obs,scores,dates,D_context=dc)
    evidence={epoch:deepcopy(snapshot['economics'].get(epoch,{})) for epoch in sorted({r['reference_epoch'] for r in obs['candidates']})}
    costs=deepcopy(c.core._helpers().ref.SCENARIOS)
    observed=journal.append('observations',_clean(dict(observations=obs,scores=scores,selection=selected,
        instrument_evidence=evidence,cost_scenarios=costs,input_entry_hash=received['entry_hash'],active=False)),key=token+'/observations')
    counts.update(mother_count=len(obs['mothers']),candidate_count=len(obs['candidates']),
        score_count=len(scores),selected_count=sum(bool(r['selected']) for r in selected['choices']))
    result=dict(schema=SCHEMA,mode=mode,status='observed_unfunded',active=False,u_index=u,u_date=dates[u],
        observations=obs,scores=scores,selection=selected,input_receipt=received,observation_receipt=observed,
        instrument_evidence=evidence,cost_scenarios=costs,
        decision_receipt=None,clock=causal_clock,states=current,counts=counts,policy_identity=policy_identity,
        current_D_facts_advanced=bool(counts['advance_D_calls']),gap_reason=None,
        receipt_scope='local321 actual UTC; no external publication/PIT attestation',T0_created=False)
    if mode=='observe_only':return _clean(result)

    stage_key=token+'/state/'+_hash(current)
    def gap(reason,classified,decision=None):
        record=journal.append('state_gap',_clean(dict(reason=reason,clock=classified,active=False,
            input_entry_hash=received['entry_hash'],decision_entry_hash=decision['entry_hash'] if decision else None,
            retained_fact_state_sha256=_hash(current),current_D_facts_advanced=bool(counts['advance_D_calls']),
            boundary='No candidate pending committed; existing fact state retained, never replaced by a flat/zero account.')),
            key=stage_key+'/gap/'+reason)
        result.update(status='state_gap',active=False,clock=classified,decision_receipt=decision,
            states=current,gap_reason=reason,classification_receipt=record)
        return _clean(result)
    if state_problem:return gap(state_problem,causal_clock)
    if policy_identity['frozen_at'] is None:return gap('not_frozen',causal_clock)
    # A real receipt is the pre-seal clock, not a caller-provided datetime.
    started=journal.append('decision_start',dict(input_entry_hash=received['entry_hash'],
        observation_entry_hash=observed['entry_hash'],fact_state_sha256=_hash(current),active=False),key=stage_key+'/start')
    pre=gate(started['recorded_at'])
    if not pre['timely_decision']:return gap(pre['status'],pre,started)
    candidate={}
    for scenario,state in current.items():
        candidate[scenario]=c.paper.seal_u(state,u_index=u,prepared=selected['prepared'],market=snapshot['market'],
            dates=dates,economics=snapshot['economics'],base_kernel=base_kernel)
        candidate[scenario]['caller_policy_sha256']=journal.policy_hash
        counts['seal_u_calls']+=1
    # All candidate budgets are fixed inside this immutable object. It is
    # deliberately inactive until this exact object's receipt is classified.
    proposal=journal.append('decision_proposal',_clean(dict(active=False,candidate_states=candidate,
        input_entry_hash=received['entry_hash'],observation_entry_hash=observed['entry_hash'],
        start_entry_hash=started['entry_hash'])),key=stage_key+'/proposal')
    final=gate(proposal['recorded_at'])
    if not final['timely_decision']:return gap(final['status'],final,proposal)
    classified=journal.append('decision_classification',dict(active=True,clock=final,
        proposal_entry_hash=proposal['entry_hash'],decision_sealed_at=proposal['recorded_at'],
        boundary='Activation is derived from the complete proposal receipt; this classification does not backdate or create a new seal.'),
        key=stage_key+'/timely')
    result.update(status='timely_state_sealed',active=True,states=candidate,clock=final,
        decision_receipt=proposal,classification_receipt=classified)
    return _clean(result)
