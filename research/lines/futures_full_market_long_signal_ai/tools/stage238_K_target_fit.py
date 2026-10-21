"""Frozen237 target-only six-model experiment; root-only actual, zero cash.

Accepted218 fit/design/selection kernels are reused without old actual drivers.
Pure new target/support/policy helpers accept tiny inputs without data I/O.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage237_K_target_protocol/protocol.json'
PROTOCOL_SHA='8aad5f5b6afefec4b078ba7a32f48b806119977156ade22da04eb4e433885c06'
OUTPUT=LINE/'outputs/stage238_K_target_fit/actual_run1'
CANDIDATE='K_TARGET52';CONTROLS=('DOMAIN52','COMMON52')
SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01');END='2026-10-16'
PHASE='after_all_source_close'
SUPPORT_KEYS=('sequence_index','admissible_mask','old_weight','new_weight')
SOURCE_NAMES=('stage238_K_target_fit.py','test_stage238_K_target_fit.py','stage218_training_domain_loss_fit.py',
    'stage205_local_curve_information_fit.py','stage214_training_domain_probe.py','stage130_contract_choice_fit.py',
    'stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')
_HELPERS=None


def helpers():
    global _HELPERS
    if _HELPERS is None:
        spec=importlib.util.spec_from_file_location('accepted218_for238',TOOLS/'stage218_training_domain_loss_fit.py')
        kernel=importlib.util.module_from_spec(spec);spec.loader.exec_module(kernel)
        shared,_=kernel.helpers();old,voluntary=shared.helpers();_HELPERS=(kernel,shared,old,voluntary)
    return _HELPERS


def candidate_target(old_y,old_tokens,K_tokens,timing,primary):
    """Copy legacy float bits; parse only genuinely re-quoted K target tokens."""
    old=np.asarray(old_y,dtype=np.float64);result=old.copy();timing=np.asarray(timing);primary=np.asarray(primary).astype(bool)
    old_tokens=np.asarray(old_tokens,dtype=str);K_tokens=np.asarray(K_tokens,dtype=str)
    copy=primary&(timing=='closed_before_K');copy_ok=np.ones(len(old),bool)
    copy_ok[copy]=old_tokens[copy]==K_tokens[copy]
    quote=primary&np.isin(timing,['closed_on_K_priority_reprice','closed_after_K','unknown_after_K','open_K_reached'])
    result[quote]=[float(t) if t else math.nan for t in K_tokens[quote]]
    return result,copy_ok


def support_preflight(actions,T,cache,y,copy_ok,cutoff):
    """No row repair: accepted S and exact weights either all qualify or stop."""
    T=np.asarray(T,np.int64);reasons=[]
    report=dict(original_T_rows=len(T),retained_S_rows=0,C_rows=0,target_changed_rows=0,ready=False,reasons=reasons)
    if set(cache)!=set(SUPPORT_KEYS):
        reasons.append('support_keys');return report,np.empty(0,np.int64),np.empty(0,float)
    seq,mask,ow,nw=(np.asarray(cache[k]) for k in SUPPORT_KEYS)
    if any(a.shape!=T.shape for a in (seq,mask,ow,nw)) or mask.dtype.kind!='b' or ow.dtype!=np.float64 or nw.dtype!=np.float64:
        reasons.append('support_shape_or_dtype');return report,np.empty(0,np.int64),np.empty(0,float)
    if not np.array_equal(seq,T):reasons.append('original_T_identity')
    if not np.array_equal(mask,actions.primary_domain.to_numpy()[T]==1):reasons.append('S_primary_mask')
    S=T[mask];w=nw[mask];report['retained_S_rows']=len(S)
    if not len(S):reasons.append('empty_S')
    if not np.isfinite(ow).all() or (ow<=0).any() or not np.isfinite(w).all() or (w<=0).any() or (nw[~mask]!=0).any():
        reasons.append('exact_weight_support')
    report.update(old_weight_mass=math.fsum(ow) if np.isfinite(ow).all() else None,
                  new_weight_mass=math.fsum(w) if np.isfinite(w).all() else None)
    part=actions.iloc[S]
    known=part.K_stress_known.astype(str).eq('1').to_numpy()&np.isfinite(np.asarray(y)[S])
    clock=(part.K_stress_known_date.ne('')&part.K_stress_known_date.le(part.label_known_date)&
        part.label_known_date.lt(cutoff)&part.label_known_date.ne('')&part.label_known_phase.eq(PHASE)&
        part.K_stress_known_phase.eq(PHASE)).to_numpy()
    if not known.all():reasons.append('K_strict_unknown_or_nonfinite')
    if not clock.all():reasons.append('K_clock_not_dominated')
    if not np.asarray(copy_ok)[S].all():reasons.append('copy_before_K_token_mismatch')
    report['C_rows']=int((known&clock&np.asarray(copy_ok)[S]).sum())
    report['target_changed_rows']=int(np.count_nonzero(np.asarray(y)[S]!=actions.net_R_stress.to_numpy(float)[S]))
    report['ready']=not reasons and report['C_rows']==len(S)
    return report,S,w


def gated_fits(preflight,callback):
    cells=preflight.get('cells',[])
    exact=len(cells)==6 and {(r['scope'],r['cutoff']) for r in cells}=={(s,c) for s in SCOPES for c in CUTOFFS}
    return callback() if exact and preflight.get('ready') and all(r['ready'] for r in cells) else None


def policy_value(choice,lookup,end=END):
    if int(choice['selected'])==0:
        if choice['chosen_action_id']:raise ValueError('unselected_with_action')
        return 0.
    row=lookup.get(choice['chosen_action_id'])
    if row is None or int(row['primary_domain'])!=1:raise ValueError('selected_missing_or_nonprimary_K_label')
    if str(row['K_stress_known'])=='1':
        value=float(row['K_stress_net_R'])
        if not math.isfinite(value) or row['K_stress_known_phase']!=PHASE or not row['K_stress_known_date']:
            raise ValueError('known_K_label_inconsistent')
        return value if row['K_stress_known_date']<=end else math.nan
    if (row['participation_state']=='known_nonparticipation' and str(row['policy_reward_known'])=='1'
            and row['policy_reward']=='0' and row['policy_known_phase']==PHASE and row['policy_known_date']
            and row['policy_known_date']<=end):return 0.
    return math.nan


def held_compare(candidate,control,lookup,control_name):
    """Complete family-u policy comparison, four deployment cells per control."""
    groups={};daily=[]
    for scope in ('holdout_0','holdout_1'):
        for cutoff in CUTOFFS:
            lo,hi=(cutoff,'2023-01-01') if cutoff==CUTOFFS[0] else (cutoff,None)
            arms={}
            for name,frame in ((control_name,control),(CANDIDATE,candidate)):
                part=frame.loc[frame.scope.eq(scope)&frame.u_date.ge(lo)&
                    (frame.u_date.lt(hi) if hi else frame.u_date.le(END))].copy()
                if not part.cutoff.eq(cutoff).all():raise ValueError('held_deployment_cutoff_mismatch')
                if part.loc[part.selected.astype(int).eq(1)].duplicated(['family_id','u_index']).any():
                    raise ValueError('held_multiple_family_actions')
                part=part.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index'])
                part['value']=[policy_value(r,lookup) for r in part.to_dict('records')]
                arms[name]=part.set_index(['family_id','u_index']).sort_index()
            aa=arms[control_name];bb=arms[CANDIDATE]
            if not aa.index.equals(bb.index) or not aa.u_date.equals(bb.u_date):raise ValueError('held_policy_population_mismatch')
            same=aa.chosen_action_id.eq(bb.chosen_action_id).to_numpy();known=np.isfinite(aa.value.to_numpy())&np.isfinite(bb.value.to_numpy())
            delta=np.where(same,0.,np.where(known,bb.value.to_numpy()-aa.value.to_numpy(),math.nan))
            unknown=~same&~known;unresolved=same&aa.chosen_action_id.ne('').to_numpy()&~known
            f=pd.DataFrame(dict(u_date=aa.u_date.to_numpy(),delta_R=delta,known=np.isfinite(delta),unknown=unknown,same_unresolved=unresolved))
            days=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),
                unknown_family_u=('unknown','sum'),same_unresolved=('same_unresolved','sum')).reset_index()
            days['control']=control_name;days['scope']=scope;days['cutoff']=cutoff;daily.append(days)
            mean=float(days.delta_R.mean()) if days.delta_R.notna().any() else None
            groups[scope+'/'+cutoff]=dict(scope=scope,cutoff=cutoff,control=control_name,
                known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=int(unknown.sum()),
                common_unresolved_same_action=int(unresolved.sum()),full_family_u=len(aa),
                known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(days.delta_R.notna().sum()),
                selected_by_arm={k:int(v.selected.astype(int).sum()) for k,v in arms.items()},
                nominal_pass=bool(mean is not None and math.isfinite(mean) and mean>0 and not unknown.any()))
    return groups,pd.concat(daily,ignore_index=True)


def after_selection_gate(groups,identities):
    expected={s+'/'+c for s in ('holdout_0','holdout_1') for c in CUTOFFS}
    held=bool(set(groups)==set(CONTROLS) and all(set(v)==expected and all(c['nominal_pass'] for c in v.values()) for v in groups.values()))
    changed=bool(set(identities)==set(CONTROLS) and all(not v['identical_actions'] for v in identities.values()))
    return dict(all_eight_held_pass=held,main_differs_from_both=changed,cash_eligible=held and changed,
                reason='held_or_main_gate_failed_zero_cash' if not(held and changed) else 'eligible_for_separately_frozen_cash_only',
                new_cash=0,automatic_cash_authorized=False)


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_small(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('small_binding_changed '+b['path'])
    return raw


def source_bundle():return sorted([binding(TOOLS/n) for n in SOURCE_NAMES],key=lambda b:b['path'])


def write_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def load_inputs(protocol,counters):
    kernel,shared,old,_=helpers();inputs=protocol['input_bindings']
    small={}
    for role,b in inputs.items():
        if role not in ('labels_K','mothers','common','calendar'):small[role]=json.loads(read_small(b))
    if (small['measurement_decision'].get('status')!='accepted_object_measurement_only'
            or small['measurement_manifest'].get('status')!='completed'
            or small['measurement_review'].get('core_blockers',small['measurement_review'].get('P0',0))!=0):
        raise ValueError('accepted_K_measurement_required')
    if not shared.same_binding(small['measurement_manifest']['artifacts']['labels_K.csv.gz'],inputs['labels_K']):
        raise ValueError('accepted_K_labels_binding')
    if small['domain_model_review'].get('core_blockers')!=0 or not shared.same_binding(small['domain_model_review']['manifest'],inputs['domain_fit_manifest']):
        raise ValueError('accepted_domain_control_required')
    for role in ('mothers','common'):
        if not shared.same_binding(small['dataset_manifest'][role],inputs[role]):raise ValueError('original_dataset_binding '+role)
    controls=protocol['controls'];lineage=protocol['control_lineage']
    for role,b in [('DOMAIN52',inputs['domain_fit_manifest']),('COMMON52_main',inputs['control_choice_manifest']),('COMMON52_held',inputs['control_held_K_manifest'])]:
        if not shared.same_binding(lineage[role]['manifest'],b):raise ValueError('control_lineage_binding')
    inherited={k:inputs[k] for k in ('labels_K','mothers','common')}
    for name,parts in controls.items():
        for kind,b in parts.items():inherited[name+'/'+kind]=b
    for f in protocol['folds']:inherited['support/'+f['scope']+'/'+f['cutoff']]=f['support']
    before={k:shared.inherited_stat(b) for k,b in inherited.items()}
    counters['labels_K_csv']+=1
    a=pd.read_csv(inputs['labels_K']['path'],usecols=protocol['labels_usecols'],dtype=str,keep_default_na=False)
    old_tokens=a.net_R_stress.to_numpy(copy=True);K_tokens=a.K_stress_net_R.to_numpy(copy=True)
    for k in ('sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_index','exit_index','net_R_stress','primary_domain'):
        a[k]=pd.to_numeric(a[k],errors='coerce')
    a['event_id']=a.action_id;a['action_sequence_index']=a.sequence_index;a['actual_epoch']=a.reference_epoch
    if len(a)!=1552456 or a.action_id.duplicated().any() or not np.array_equal(a.sequence_index,np.arange(len(a))):
        raise ValueError('complete_K_action_identity')
    y,copy_ok=candidate_target(a.net_R_stress.to_numpy(float),old_tokens,K_tokens,a.timing_state.to_numpy(),a.primary_domain.to_numpy())
    counters['mothers_csv']+=1
    m=pd.read_csv(inputs['mothers']['path'],usecols=protocol['mothers_usecols'],dtype=str,keep_default_na=False)
    for k in ('sequence_index','u_index'):m[k]=pd.to_numeric(m[k],errors='raise')
    if len(m)!=399252 or m.event_id.duplicated().any() or not np.array_equal(m.sequence_index,np.arange(len(m))):raise ValueError('complete_original_mother_identity')
    pi=a.mother_sequence_index.to_numpy(np.int64)
    if (pi<0).any() or (pi>=len(m)).any():raise ValueError('invalid_parent_index')
    for left,right in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),('u_date','u_date'),('u_index','u_index'),('anchor_epoch','reference_epoch')]:
        if not np.array_equal(a[left].to_numpy(),m[right].to_numpy()[pi]):raise ValueError('parent_child_mismatch '+left)
    counters['COMMON_npz']+=1
    with np.load(inputs['common']['path'],allow_pickle=False) as z:common=z['common'];columns=z['columns'].tolist()
    if common.shape!=(1552456,26) or common.dtype!=np.float64 or columns!=old.COMMON:raise ValueError('accepted_COMMON26_coordinates')
    counters['calendar']+=1;cal=np.load(io.BytesIO(read_small(inputs['calendar'])),allow_pickle=False)
    calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal] if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
    if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('accepted_calendar')
    return a,m,common,calendar,y,copy_ok,small,inherited,before


def prepare_folds(a,m,common,y,copy_ok,protocol,small,counters):
    _,shared,old,_=helpers();plans=[];cells=[]
    records={(r['scope'],r['cutoff']):r for r in small['domain_fit_records']}
    for f in protocol['folds']:
        scope,cutoff=f['scope'],f['cutoff'];next_cutoff=CUTOFFS[1] if cutoff==CUTOFFS[0] else None
        train,pred,parent=old.fold_slices(a,m,cutoff,next_cutoff,scope);T=train.sequence_index.to_numpy(np.int64)
        counters['support_npz']+=1
        with np.load(f['support']['path'],allow_pickle=False) as z:cache={k:z[k] for k in SUPPORT_KEYS}
        report,S,w=support_preflight(a,T,cache,y,copy_ok,cutoff)
        report.update(scope=scope,cutoff=cutoff,training_domain_support=f['support'],common_scaler=f['original_common_scaler'],
            prediction_children=len(pred),prediction_mothers=len(parent),training_rows=len(S),weight_recomputed=False,
            original_target_parser='legacy_pd_to_numeric',candidate_parser='old_copy_quote_roundtrip_only')
        ref=records[(scope,cutoff)]
        if not shared.same_binding(ref['training_domain_support'],f['support']) or not shared.same_binding(ref['common_scaler'],f['original_common_scaler']):
            report['reasons'].append('accepted218_fold_binding')
        if len(T)!=f['original_T_rows'] or len(S)!=f['retained_S_rows']:report['reasons'].append('accepted218_support_count')
        if report.get('old_weight_mass')!=ref['domain']['old_weight_mass'] or report.get('new_weight_mass')!=ref['domain']['candidate_weight_mass']:
            report['reasons'].append('accepted218_weight_mass')
        if len(pred)!=f['prediction_children'] or len(parent)!=f['prediction_mothers']:report['reasons'].append('original_forward_support')
        counters['old_scaler_small_json']+=1;scaler=json.loads(read_small(f['original_common_scaler']))
        if scaler.get('scope')!=scope or scaler.get('cutoff')!=cutoff or scaler.get('feature_names')!=old.FEATURE_NAMES or scaler.get('common',{}).get('columns')!=old.COMMON:
            report['reasons'].append('accepted130_scaler')
        try:
            for start in range(0,len(S),65536):old.design(common[S[start:start+65536]],scaler)
        except ValueError:report['reasons'].append('full52_design_nonfinite')
        report['ready']=report['ready'] and not report['reasons']
        cells.append(report);plans.append(dict(report=report,ti=S,weights=w,scaler=scaler,
            pi=pred.sequence_index.to_numpy(np.int64),mi=parent.sequence_index.to_numpy(np.int64)))
    return plans,dict(schema='stage238_all_six_same_C_preflight_v1',ready=all(r['ready'] for r in cells),cells=cells,
        all_six_before_any_fit=True,new_training_rows_admitted=0,old_training_csv_reads=0)


def validate_choices(frame,m,a,scope_kind):
    _,_,old,_=helpers();expected=m.loc[m.u_date.ge(CUTOFFS[0])].sort_values('sequence_index')
    f=frame.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    if len(f)!=161014 or f.event_id.duplicated().any():raise ValueError('full_choice_parent_population')
    for k in old.IDENTITY:
        if not np.array_equal(f[k].to_numpy(),expected[k].to_numpy()):raise ValueError('choice_parent_identity '+k)
    if not f.anchor_epoch.eq(f.reference_epoch).all():raise ValueError('choice_anchor')
    if not f.selected.isin([0,1]).all():raise ValueError('choice_selected_flag')
    if not np.array_equal(f.cutoff.to_numpy(),np.where(f.u_date.lt(CUTOFFS[1]),CUTOFFS[0],CUTOFFS[1])):raise ValueError('choice_cutoff')
    wanted=np.repeat('main',len(f)) if scope_kind=='main' else f.family_id.map(lambda x:'holdout_'+str(old.family_group(x))).to_numpy()
    if not np.array_equal(f.scope.to_numpy(),wanted):raise ValueError('choice_scope')
    selected=f.loc[f.selected.eq(1)];idx=selected.chosen_action_sequence_index.to_numpy(np.int64)
    if (idx<0).any() or (idx>=len(a)).any():raise ValueError('chosen_action_index')
    for left,right in [('chosen_action_id','action_id'),('chosen_epoch','reference_epoch'),('event_id','mother_event_id'),('product_id','product_id'),('u_index','u_index')]:
        if not np.array_equal(selected[left].to_numpy(),a.iloc[idx][right].to_numpy()):raise ValueError('chosen_action_identity '+left)
    if not a.iloc[idx].primary_domain.eq(1).all() or f.loc[f.selected.eq(0),'chosen_action_id'].ne('').any():raise ValueError('selected_nonprimary_or_empty_mismatch')
    return f


def forward_and_select(a,m,common,calendar,plans,models,protocol,counters,save_csv,save_json):
    kernel,shared,old,voluntary=helpers();children=[];seen={True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)}
    for plan,model in zip(plans,models):
        r=plan['report'];pi=plan['pi'];scope=r['scope'];counters['prediction_calls_attempted']+=1
        x=old.design(common[pi],plan['scaler']);score=x@np.asarray(model['coef'])+model['intercept'];del x
        if not np.isfinite(score).all() or seen[scope=='main'][pi].any():raise ValueError('forward_score_identity_or_finiteness')
        seen[scope=='main'][pi]=True;counters['prediction_calls_completed']+=1;counters['prediction_model_rows']+=len(pi)
        child=a.iloc[pi][shared.CHILD_FIELDS].copy();child['score']=score;child['scope']=scope;child['cutoff']=r['cutoff'];child['arm']=CANDIDATE;children.append(child)
    expected=a.u_date.ge(CUTOFFS[0]).to_numpy()
    if counters['prediction_model_rows']!=1933480 or any(not np.array_equal(v,expected) for v in seen.values()):raise ValueError('complete_forward_domain')
    children=pd.concat(children,ignore_index=True);roles={'child_scores':save_csv('child_scores.csv.gz',children)}
    choices=[];boundaries={};selection=[]
    for scope in SCOPES:
        parents=m.loc[m.u_date.ge(CUTOFFS[0])]
        if scope!='main':parents=parents.loc[parents.family_id.map(old.family_group).eq(int(scope[-1]))]
        counters['candidate_selection_calls']+=1
        chosen,bounds,summary=shared.choose_scope(parents,children.loc[children.scope.eq(scope)],scope,CANDIDATE,calendar)
        choices.append(chosen);selection.append(dict(scope=scope,summary=summary))
        for epoch,b in bounds.items():
            if epoch in boundaries and boundaries[epoch]!=b:raise ValueError('inconsistent_K_boundaries')
            boundaries[epoch]=b
    choices=pd.concat(choices,ignore_index=True)
    main=validate_choices(choices.loc[choices.scope.eq('main')],m,a,'main')
    held=validate_choices(choices.loc[choices.scope.ne('main')],m,a,'held')
    controls={}
    for name,parts in protocol['controls'].items():
        controls[name]={}
        for kind,b in parts.items():
            counters['control_choice_csv']+=1
            frame=pd.read_csv(b['path'],usecols=protocol['control_choices_usecols'],dtype=str,keep_default_na=False)
            for k in ('sequence_index','u_index','chosen_action_sequence_index','selected'):frame[k]=pd.to_numeric(frame[k],errors='raise')
            controls[name][kind]=validate_choices(frame,m,a,kind)
    identities={name:kernel.selection_identity(main,parts['main']) for name,parts in controls.items()}
    needed=set(held.loc[held.selected.eq(1),'chosen_action_sequence_index'])
    for parts in controls.values():needed.update(parts['held'].loc[parts['held'].selected.eq(1),'chosen_action_sequence_index'])
    lookup={r['action_id']:r for r in a.iloc[sorted(map(int,needed))].to_dict('records')}
    groups={};daily=[]
    for name,parts in controls.items():groups[name],table=held_compare(held,parts['held'],lookup,name);daily.append(table)
    gate=after_selection_gate(groups,identities)
    diagnostic=dict(schema='stage238_strict_K_held_diagnostic_v1',groups=groups,all_eight_pass=gate['all_eight_held_pass'],
        target='strict K stress narrow_R',meaning='family-u then equal-u complete prospective policies; not cash',
        distinct_unknown_filled_zero=False,same_unresolved_trade_target_remains_null=True)
    roles.update(choices_main=save_csv('choices_main.csv.gz',main),choices_holdout=save_csv('choices_holdout.csv.gz',held),
        held_daily=save_csv('held_daily.csv.gz',pd.concat(daily,ignore_index=True)),held_diagnostic=save_json('held_diagnostic.json',diagnostic),
        selection_identity=save_json('selection_identity.json',identities),continuation_gate=save_json('continuation_gate.json',gate),
        selection_summary=save_json('selection_summary.json',selection),boundaries=save_json('boundaries.json',
        dict(schema='stage238_fixed155_K_boundaries_v1',epochs=boundaries,policy_version=voluntary.POLICY_VERSION,sample_end=END,calendar=protocol['input_bindings']['calendar'])))
    return roles,gate


def authorize(args):
    pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen237_protocol')
    protocol=json.loads(read_small(pb));ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization_sha')
    auth=json.loads(read_small(ab));output=Path(args.output).resolve();bundle=source_bundle()
    required=dict(schema='stage237_exact_root_fit_authorization_v1',authorized_by='root',stage='fit',exact_source_authorized=True,
                  protocol_sha256=PROTOCOL_SHA,output=str(output))
    if (output!=OUTPUT or output.exists() or any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=bundle
            or auth.get('input_bindings')!=protocol['input_bindings'] or auth.get('controls')!=protocol['controls'] or auth.get('folds')!=protocol['folds']):
        raise ValueError('fresh_exact_root_target_fit_authorization_required')
    if protocol['source_allowlist']!=list(SOURCE_NAMES):raise ValueError('frozen_source_allowlist')
    for b in protocol['existing_small_source_bindings']:read_small(b)
    return protocol,pb,auth,ab,output,bundle


def actual(args):
    protocol,pb,auth,ab,out,bundle=authorize(args);out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();counters=dict(labels_K_csv=0,mothers_csv=0,COMMON_npz=0,calendar=0,support_npz=0,
        old_scaler_small_json=0,control_choice_csv=0,fit_calls_attempted=0,fit_calls_completed=0,prediction_calls_attempted=0,
        prediction_calls_completed=0,prediction_model_rows=0,candidate_selection_calls=0,old_fit=0,old_prediction=0,old_selection=0,
        old_cash=0,new_cash=0,old130_training_csv=0,original_actions_reads=0,native_cache_reads=0,SQL=0,download=0,old_large_hash=0)
    artifacts={};roles={};records=[];failure=None;status='failed';evidence={};gate=dict(cash_eligible=False,reason='not_completed')
    def save_json(name,obj):write_json(out/name,obj);b=binding(out/name);artifacts[name]=b;return b
    def save_csv(name,frame):
        frame.to_csv(out/name,index=False,float_format='%.17g',compression=dict(method='gzip',compresslevel=1,mtime=0));b=helpers()[1].file_binding(out/name);artifacts[name]=b;return b
    def save_npz(name,**values):
        with (out/name).open('xb') as f:np.savez(f,**values)
        b=binding(out/name);artifacts[name]=b;return b
    def checkpoint(name,scope,cutoff):
        with (out/name).open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,attempted=counters['fit_calls_attempted'],completed=counters['fit_calls_completed']))+'\n');f.flush()
    save_json('started.json',dict(protocol=pb,authorization=ab,source_bundle=bundle,automatic_retry=False,started_at=datetime.now(timezone.utc).isoformat()))
    try:
        kernel,shared,old,_=helpers()
        a,m,common,calendar,y,copy_ok,small,inherited,before=load_inputs(protocol,counters)
        evidence=dict(bindings=inherited,before=before)
        plans,preflight=prepare_folds(a,m,common,y,copy_ok,protocol,small,counters)
        roles['preflight']=save_json('preflight.json',preflight)
        def fit_all():
            models=[]
            for plan in plans:
                report=plan['report'];scope=report['scope'];cutoff=report['cutoff'];S=plan['ti']
                directory=Path('folds')/scope/cutoff;(out/directory).mkdir(parents=True,exist_ok=False)
                x=old.design(common[S],plan['scaler'])
                if counters['fit_calls_attempted']>=6:raise ValueError('fit_budget')
                counters['fit_calls_attempted']+=1;checkpoint('fit_attempts.jsonl',scope,cutoff)
                def on_complete():counters['fit_calls_completed']+=1;checkpoint('fit_completed.jsonl',scope,cutoff)
                model,eq,residual=kernel.fit_arrays(x,y[S],plan['weights'],on_complete);del x
                model.update(schema='stage238_portable_K_target_ridge52_v1',scope=scope,cutoff=cutoff,arm=CANDIDATE,
                    feature_names=old.FEATURE_NAMES,scaler=report['common_scaler'],target='K_stress_net_R')
                mb=save_json(str(directory/'portable_model.json'),model);eb=save_npz(str(directory/'normal_equations.npz'),**eq)
                records.append(dict(**report,dimension=52,arm=CANDIDATE,scaler=report['common_scaler'],portable_model=mb,
                    normal_equations=eb,normal_equation_max_abs_residual=residual,weight_source=report['training_domain_support']))
                models.append(model);print(json.dumps(dict(phase='new_model_saved',scope=scope,cutoff=cutoff,completed=counters['fit_calls_completed'])),flush=True)
            return models
        models=gated_fits(preflight,fit_all)
        roles['fit_records']=save_json('fit_records.json',records)
        if models is None:gate=dict(cash_eligible=False,all_eight_held_pass=False,main_differs_from_both=False,reason='same_C_preflight_failed_zero_fit_zero_cash',new_cash=0)
        else:
            if counters['fit_calls_attempted']!=6 or counters['fit_calls_completed']!=6:raise ValueError('six_fit_completion')
            forward,gate=forward_and_select(a,m,common,calendar,plans,models,protocol,counters,save_csv,save_json);roles.update(forward)
        evidence['after']={k:shared.inherited_stat(b) for k,b in inherited.items()}
        if evidence['before']!=evidence['after'] or source_bundle()!=bundle:raise ValueError('source_changed_during_actual')
        roles['source_read_receipt']=save_json('source_read_receipt.json',dict(**evidence,counters=counters,
            alias_identity_inherited_from_accepted129=True,copy_before_K_legacy_bits_preserved=True,newweight_factor_reapplied=False))
        status='completed'
    except Exception as exc:
        failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());save_json('failure.json',failure)
    for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
        if (out/name).exists():artifacts[name]=binding(out/name)
    summary=dict(status=status,reason=gate['reason'],cash_eligible=gate['cash_eligible'],all_eight_held_pass=gate.get('all_eight_held_pass',False),
        main_differs_from_both=gate.get('main_differs_from_both',False),counters=counters,actual_fit_calls_attempted=counters['fit_calls_attempted'],
        actual_fit_calls_completed=counters['fit_calls_completed'],prediction_children=counters['prediction_model_rows'],new_cash=0,
        cumulative_fit=433+counters['fit_calls_completed'],cumulative_cash=234,goal_complete=False,alpha_qualified=False,production_qualified=False,increased_betting_qualified=False)
    roles['summary']=save_json('summary.json',summary)
    terminal=save_json('terminal.json',dict(**summary,exit_code=0 if status=='completed' else 1,elapsed_seconds=time.monotonic()-started,automatic_retry=False))
    manifest=dict(schema='stage238_K_target_fit_v1',**summary,protocol=pb,protocol_sha256=PROTOCOL_SHA,authorization=ab,
        source_bundle=bundle,input_bindings=protocol['input_bindings'],controls=protocol['controls'],control_lineage=protocol['control_lineage'],
        folds=protocol['folds'],candidate_arm=CANDIDATE,control_arms=list(CONTROLS),artifacts=artifacts.copy(),terminal=terminal,**roles)
    write_json(out/'manifest.json',manifest)
    print(json.dumps(dict(status=status,cash_eligible=summary['cash_eligible'],actual_fit_calls_completed=counters['fit_calls_completed'],output=str(out))),flush=True)
    if failure:raise RuntimeError(failure['message'])
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--actual',action='store_true')
    parser.add_argument('--authorization',type=Path,required=True);parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    if not args.actual:parser.error('exact root --actual required')
    actual(args)


if __name__=='__main__':main()
