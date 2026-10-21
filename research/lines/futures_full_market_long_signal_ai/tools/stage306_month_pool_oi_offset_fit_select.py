"""Frozen304: six own-fold scalar residual offsets, complete main/held K choice.

Actual is root-only and cache/vector-only. Import and new tiny fixtures never
read the research arrays, refit old52, generate labels or run a cash account.
"""
from __future__ import annotations
import argparse
from collections import Counter
import importlib.util
import io
import itertools
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage304_month_pool_oi_share_protocol/protocol.json'
PROTOCOL_SHA='729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4'
CANDIDATE='LAGGED_MONTH_POOL_OI_SHARE_OFFSET';END='2026-10-16'
SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
LABEL_FIELDS=['action_id','label_state','participation_state','net_R_stress','label_known_date']
INPUT_ROLES={'fit_manifest','execution_protocol','market_protocol','mothers','actions','calendar',
    'source_manifest','source_proof_stage','static_review_receipt','control_choices_main','control_choice_manifest',
    'control_held_choices','control_held_manifest','control_held_review'}
SOURCE_NAMES=('stage306_month_pool_oi_offset_fit_select.py','test_stage306_month_pool_oi_offset_fit_select.py',
    'stage285_wasde_offset_fit_select.py','stage130_contract_choice_fit.py',
    'stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')
_HELPERS=None


def helpers():
    global _HELPERS
    if _HELPERS is None:
        spec=importlib.util.spec_from_file_location('stage306_pure285',TOOLS/'stage285_wasde_offset_fit_select.py')
        _HELPERS=importlib.util.module_from_spec(spec);spec.loader.exec_module(_HELPERS)
    return _HELPERS


def validate_vector(sequence,q,available,expected):
    seq=np.asarray(sequence);q=np.asarray(q);a=np.asarray(available)
    if (seq.shape!=(expected,) or seq.dtype.kind not in 'iu' or not np.array_equal(seq,np.arange(expected))
            or q.shape!=(expected,) or q.dtype!=np.dtype('float64') or a.shape!=(expected,)
            or (a.dtype.kind!='b' and a.dtype!=np.dtype('uint8')) or not np.isin(a,[0,1]).all()
            or not np.array_equal(a.astype(bool),np.isfinite(q)) or np.isinf(q).any()):
        raise ValueError('source_vector_alignment_availability_or_dtype')
    return q


def validate_training(frame,scope,cutoff,expected):
    train=helpers().validate_training(frame,cutoff,expected)
    if scope not in SCOPES or cutoff not in CUTOFFS:raise ValueError('unknown_original_fold')
    if scope!='main':
        groups=train.family_id.map(helpers().old_helper().family_group)
        if groups.eq(int(scope[-1])).any():raise ValueError('held_family_entered_training')
    return train


def fit_scalar(q,u_dates,residual,w):
    model,z=helpers().fit_scalar(q,u_dates,residual,w)
    model['distinct_u_dates']=model.pop('distinct_release_identities')
    return model,z


def shift_row(raw,q,models):
    row=dict(raw);key=(row['scope'],row['cutoff'])
    if key not in models:raise ValueError('score_outside_fixed_fold')
    seq=helpers().old_helper(True).integer(row['sequence_index'])
    if not 0<=seq<len(q):raise ValueError('forward_sequence_outside_source_vector')
    old=float(row['score']);value=float(q[seq]);m=models[key]
    if not np.isfinite(old):raise ValueError('original_forward_score_nonfinite')
    delta=0.;z=0.
    if np.isfinite(value) and m['status']=='supported':
        z=(value-m['mean'])/m['scale'];delta=m['gamma']*z
    row['score']=old+delta if delta!=0 else old
    if not np.isfinite(row['score']):raise ValueError('new_forward_score_nonfinite')
    return dict(row,source_q=value,z=z,delta=delta,old_score=old)


def select_scope(mothers,scores,scope,calendar,end=END):
    selector=helpers().old_helper(True)
    def aliases():
        for raw in scores:
            if raw['scope']!=scope:raise ValueError('mixed_forward_scope')
            yield dict(raw,scope='main')
    result=selector.select_full_pool(mothers,aliases(),calendar,end,audit_sink=lambda row:None)
    for row in result['choices']:row.update(scope=scope,candidate=CANDIDATE)
    return result


def source_bundle():
    return sorted((helpers().binding(TOOLS/n) for n in SOURCE_NAMES),key=lambda b:b['path'])


def authorize(args):
    h=helpers();out=Path(args.output).resolve();pb=h.binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen304_changed')
    if out.exists() or LINE/'outputs/stage306_month_pool_oi_offset_fit_select' not in out.parents:
        raise ValueError('fresh_stage306_output_required')
    ab=h.binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization_hash_changed')
    auth=h.read_json(ab)
    fixed=dict(schema='stage306_exact_root_authorization_v1',authorized_by='root',exact_source_authorized=True,
        protocol_sha256=PROTOCOL_SHA,candidate=CANDIDATE,output=str(out),max_new_fit=6,max_new_cash=0)
    if any(auth.get(k)!=v for k,v in fixed.items()) or auth.get('source_bundle')!=source_bundle():
        raise ValueError('exact306_source_authorization_required')
    inputs=auth.get('inputs',{})
    if set(inputs)!=INPUT_ROLES or Path(args.source_manifest).resolve()!=Path(inputs['source_manifest']['path']).resolve():
        raise ValueError('exact306_inputs_or_explicit_source_manifest')
    return out,h.read_json(pb),pb,auth,ab


def validate_inputs(p,inputs):
    h=helpers();d={k:h.read_json(inputs[k]) for k in ('fit_manifest','execution_protocol','market_protocol',
        'source_manifest','static_review_receipt','control_choice_manifest','control_held_manifest','control_held_review')}
    fit=d['fit_manifest'];src=d['source_manifest'];static=d['static_review_receipt'];same=h.same
    if not same(inputs['fit_manifest'],p['identity_inputs']['original130_manifest']):raise ValueError('original130_exact_identity')
    if fit.get('status')!='completed' or fit.get('actual_fit_calls_completed')!=6:raise ValueError('completed130_required')
    for role in ('actions','mothers'):
        if not same(inputs[role],fit['input_bindings'][role]):raise ValueError('original129_'+role)
    if (not same(inputs['execution_protocol'],fit['protocol'])
            or not same(inputs['market_protocol'],d['execution_protocol']['inputs']['market_protocol'])
            or not same(inputs['calendar'],d['market_protocol']['calendar'])
            or not same(p['identity_inputs']['original_common'],fit['input_bindings']['common'])
            or not same(p['identity_inputs']['old_scores'],fit['child_scores'])):
        raise ValueError('original_market_common_scores_binding')
    if (src.get('schema')!='stage305_month_pool_oi_source_manifest_v1' or src.get('status')!='completed'
            or src.get('protocol_sha256')!=PROTOCOL_SHA):raise ValueError('completed305_exact304_source_required')
    for role in ('actions','mothers','common'):
        expected=fit['input_bindings'][role]
        if not same(src['inputs'][role],expected):raise ValueError('305_original_domain_'+role)
    h.read_small(inputs['source_proof_stage'])
    if (static.get('schema')!='stage308_month_pool_oi_static_review_v1' or static.get('status')!='completed'
            or static.get('core_blockers')!=0 or static.get('protocol_sha256')!=PROTOCOL_SHA):
        raise ValueError('accepted308_static_receipt_required')
    checked={b['path']:b for b in static['reviewed_source_bundle']}
    for n in SOURCE_NAMES[:2]:
        b=h.binding(TOOLS/n)
        if not same(checked.get(b['path'],{}),b):raise ValueError('308_exact306_source_not_reviewed')
    cm=d['control_choice_manifest']
    if (cm.get('schema')!='stage156_voluntary_choices_manifest_v1' or cm.get('parent_rows')!=161014
            or not same(cm['artifacts']['choices_main'],inputs['control_choices_main'])
            or not same(cm['inputs']['fit_manifest'],inputs['fit_manifest'])):raise ValueError('accepted156_main_control')
    held=d['control_held_manifest'];review=d['control_held_review']
    if (not same(held['control_held_K'],inputs['control_held_choices'])
            or not same(held['input_bindings']['control_child_scores'],p['identity_inputs']['old_scores'])
            or not same(held['input_bindings']['control_fit_manifest'],inputs['fit_manifest'])
            or held.get('control_arm')!='COMMON52' or review.get('status')!='completed'
            or review.get('core_blockers')!=0 or not same(review['manifest'],inputs['control_held_manifest'])):
        raise ValueError('accepted_pure52_held_K_control')
    original=h.read_json(fit['fit_records'])
    if len(original)!=6:raise ValueError('original_six_fold_records')
    for f in p['identity_inputs']['original130_folds']:
        r=next(v for v in original if (v['scope'],v['cutoff'])==(f['scope'],f['cutoff']))
        for k in ('training_rows','training_dates','training_families','training_groups','prediction_children','prediction_mothers','max_u_date','max_label_known_date'):
            if r[k]!=f[k]:raise ValueError('original_fold_summary_'+k)
        for k in ('training_identity_weights','portable_model','scaler'):
            if not same(r[k],f[k]):raise ValueError('original_fold_binding_'+k)
    return src['artifacts']['source_vector']


def score_rows(path,counters):
    for chunk in pd.read_csv(path,usecols=helpers().old_helper(True).SCORE_FIELDS,dtype=str,
            keep_default_na=False,chunksize=100000,float_precision='round_trip'):
        counters['score_rows_read']+=len(chunk)
        yield from chunk.to_dict('records')


def read_choices(bound,mothers,held=False):
    fields=helpers().old_helper(True).IDENTITY+['selected','chosen_action_id','chosen_epoch','chosen_action_sequence_index','scope']
    frame=pd.read_csv(bound['path'],usecols=fields,dtype=str,keep_default_na=False)
    for k in ('sequence_index','u_index','selected','chosen_action_sequence_index'):frame[k]=frame[k].astype(np.int64)
    frame=frame.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    if len(frame)!=len(mothers) or frame.event_id.tolist()!=mothers.event_id.tolist():raise ValueError('control_full_parent_identity')
    for k in helpers().old_helper(True).IDENTITY:
        if frame[k].tolist()!=mothers[k].tolist():raise ValueError('control_parent_identity_'+k)
    scopes={'holdout_0','holdout_1'} if held else {'main'}
    if set(frame.scope)!=scopes or not frame.selected.isin([0,1]).all():raise ValueError('control_choice_scope_or_selection')
    if held:
        expected=mothers.family_id.map(helpers().old_helper().family_group).map(lambda g:'holdout_'+str(g))
        if frame.scope.tolist()!=expected.tolist():raise ValueError('held_control_family_scope')
    return frame


def label_subset(path,ids,counters):
    parts=[];seen=0
    for frame in pd.read_csv(path,usecols=LABEL_FIELDS,dtype=str,keep_default_na=False,chunksize=100000):
        seen+=len(frame);part=frame.loc[frame.action_id.isin(ids)].copy()
        if len(part):parts.append(part)
    counters['label_action_streams']+=1
    if seen!=1552456:raise ValueError('original_action_label_domain')
    result=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=LABEL_FIELDS)
    if result.action_id.duplicated().any() or set(result.action_id)!=ids:raise ValueError('selected_held_action_labels_missing')
    result['net_R_stress']=result.net_R_stress.replace('',np.nan).astype(float)
    return result


def held_diagnostic(control,candidate,actions,labels_skipped=False):
    choices=pd.concat([control.assign(arm='A'),candidate.assign(arm='B')],ignore_index=True)
    diagnostic,daily,_=helpers().old_helper().held_diagnostics(choices,actions)
    diagnostic.update(schema='stage306_month_pool_oi_held_original_target_v1',candidate=CANDIDATE,
        control='COMMON52_SAME_K',target='original129 net_R_stress closed_complete known<=2026-10-16; not K cash',
        labels_skipped_exact_identity=labels_skipped,coverage_or_live_quality_proved=False)
    for g in diagnostic['groups'].values():
        g['known_nonharm']=bool(g['known_u_equal_mean_increment_R'] is not None and g['known_u_equal_mean_increment_R']>=0)
        if labels_skipped:
            g['common_unresolved_same_action']=None;g['common_outcomes']='not_inspected_exact_same_actions'
    diagnostic['both_groups_known_nonharm']=all(diagnostic['groups'][s]['known_nonharm'] for s in SCOPES[1:])
    diagnostic['any_differential_unknown']=any(diagnostic['groups'][s]['unknown_differential_selected_events'] for s in SCOPES[1:])
    return diagnostic,daily


def execute(args):
    out,p,pb,auth,ab=authorize(args);h=helpers();inputs=auth['inputs'];out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();artifacts={};bundle=source_bundle();counts=Counter(dict(fit_attempted=0,fit_completed=0,
        cash=0,SQL=0,old52_refit=0,new_labels=0,old_large_hash=0,common_reads=0,source_vector_reads=0,
        training_csv_reads=0,score_csv_reads=0,score_rows_read=0,mother_csv_reads=0,control_choice_reads=0,label_action_streams=0))
    def save_json(name,value):
        h.write_json(out/name,value);b=h.binding(out/name);artifacts[name.removesuffix('.json')]=b;return b
    def save_csv(name,value):
        value.to_csv(out/name,index=False,compression={'method':'gzip','mtime':0,'compresslevel':1},float_format='%.17g')
        b=h.binding(out/name);artifacts[name.removesuffix('.csv.gz')]=b;return b
    save_json('started.json',dict(protocol=pb,authorization=ab,source_bundle=bundle,candidate=CANDIDATE,automatic_retry=False))
    status='failed';error=None;folds=[];changed_main=None;diagnostic=None
    try:
        vector=validate_inputs(p,inputs)
        large={k:inputs[k] for k in ('mothers','actions','control_choices_main','control_held_choices')}
        large.update(common=p['identity_inputs']['original_common'],scores=p['identity_inputs']['old_scores'],source_vector=vector)
        for f in p['identity_inputs']['original130_folds']:large[f['scope']+'/'+f['cutoff']]=f['training_identity_weights']
        before={k:h.inherited_stat(b) for k,b in large.items()}
        with np.load(vector['path'],allow_pickle=False) as z:q=validate_vector(z['sequence_index'],z['q'],z['available'],1552456)
        counts['source_vector_reads']+=1
        cal=np.load(io.BytesIO(h.read_small(inputs['calendar'])),allow_pickle=False)
        calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal]
            if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('original_source_calendar')
        selector=h.old_helper(True);old=h.old_helper()
        mothers=pd.read_csv(inputs['mothers']['path'],usecols=selector.IDENTITY,dtype=str,keep_default_na=False);counts['mother_csv_reads']+=1
        for k in ('sequence_index','u_index'):mothers[k]=mothers[k].astype(np.int64)
        if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
                or mothers.family_id.nunique()!=95 or not np.array_equal(mothers.sequence_index,np.arange(399252))
                or not np.array_equal(mothers.u_date,np.asarray(calendar)[mothers.u_index.to_numpy()])):
            raise ValueError('complete_original_mothers')
        forward=mothers.loc[mothers.u_date.ge(CUTOFFS[0])&mothers.u_date.le(END)].reset_index(drop=True)
        if len(forward)!=161014:raise ValueError('forward_full_parent_domain')
        with np.load(p['identity_inputs']['original_common']['path'],allow_pickle=False) as z:
            common=z['common'];columns=z['columns'].tolist()
        counts['common_reads']+=1
        if common.shape!=(1552456,26) or columns!=old.COMMON:raise ValueError('original_common26')
        models={}
        for f in p['identity_inputs']['original130_folds']:
            scope,cutoff=f['scope'],f['cutoff'];base=h.read_json(f['portable_model']);scaler=h.read_json(f['scaler'])
            if (base['scope']!=scope or base['cutoff']!=cutoff or base['parameters']!=old.PARAMETERS
                    or base['feature_names']!=old.FEATURE_NAMES or scaler['feature_names']!=old.FEATURE_NAMES
                    or scaler['common']['columns']!=columns or scaler['scope']!=scope or scaler['cutoff']!=cutoff):
                raise ValueError('own_fold_immutable_base_and_scaler')
            frame=pd.read_csv(f['training_identity_weights']['path'],usecols=h.TRAIN_FIELDS,dtype=str,keep_default_na=False)
            counts['training_csv_reads']+=1;train=validate_training(frame,scope,cutoff,f['training_rows'])
            if (train.u_date.nunique()!=f['training_dates'] or train.family_id.nunique()!=f['training_families']
                    or train.u_date.max()!=f['max_u_date'] or train.label_known_date.max()!=f['max_label_known_date']
                    or train.sequence_index.max()>=len(q) or not np.array_equal(train.u_date,np.asarray(calendar)[train.u_index.to_numpy()])):
                raise ValueError('original_training_summary_or_calendar')
            ti=train.sequence_index.to_numpy();finite=np.isfinite(q[ti]);selected=train.loc[finite]
            seq=selected.sequence_index.to_numpy();s52=h.frozen_scores(common[seq],scaler,base)
            y=selected.net_R_stress.to_numpy();w=selected.sample_weight.to_numpy();residual=y-s52
            counts['fit_attempted']+=1;save_json('fit_attempt_'+str(counts['fit_attempted'])+'.json',dict(scope=scope,cutoff=cutoff,**dict(counts)))
            model,z=fit_scalar(q[seq],selected.u_date.to_numpy(),residual,w);counts['fit_completed']+=1
            model.update(schema='stage306_frozen52_scalar_offset_v1',scope=scope,cutoff=cutoff,candidate=CANDIDATE,
                original_training_rows=len(train),frozen_base_model=f['portable_model'],frozen_base_scaler=f['scaler'],
                original_training_identity_weights=f['training_identity_weights'],source_vector=vector)
            models[(scope,cutoff)]=model
            stem=scope+'_'+cutoff;mb=save_json('offset_'+stem+'.json',model)
            target=out/('train_finite_'+stem+'.npz')
            with target.open('xb') as stream:np.savez_compressed(stream,sequence_index=seq,sample_weight=w,y=y,s52=s52,residual=residual,z=z,delta=model['gamma']*z)
            tb=h.binding(target);artifacts['train_finite_'+stem]=tb
            folds.append(dict(scope=scope,cutoff=cutoff,model=mb,training_finite=tb,status=model['status'],gamma=model['gamma'],
                training_rows=len(train),finite_source_rows=len(seq),distinct_u_dates=model['distinct_u_dates']))
            print(json.dumps(dict(phase='scalar_fold_complete',scope=scope,cutoff=cutoff,completed=counts['fit_completed'])),flush=True)
        del common,frame,train,selected
        if counts['fit_attempted']!=6 or counts['fit_completed']!=6:raise ValueError('exact_six_scalar_solves')
        choices=[];boundaries={};summaries=[];seen=[];counts['score_csv_reads']+=1;stats={};anchors=[]
        def shifted(rows,scope):
            for raw in rows:
                value=shift_row(raw,q,models);key=(scope,raw['cutoff']);c=stats.setdefault(key,Counter())
                c['rows']+=1;c['finite_q']+=int(np.isfinite(value['source_q']));c['nonzero_delta']+=int(value['delta']!=0)
                c['negative_to_positive']+=int(value['old_score']<=0<value['score']);c['positive_to_nonpositive']+=int(value['old_score']>0>=value['score'])
                if c['rows']<=2:
                    anchor=dict(value)
                    if not np.isfinite(anchor['source_q']):anchor['source_q']=None
                    anchors.append(anchor)
                yield value
        for scope,rows in itertools.groupby(score_rows(p['identity_inputs']['old_scores']['path'],counts),key=lambda r:r['scope']):
            if scope not in SCOPES or scope in seen:raise ValueError('original_score_scope_order_or_duplicate')
            seen.append(scope);parents=forward if scope=='main' else forward.loc[forward.family_id.map(old.family_group).eq(int(scope[-1]))]
            result=select_scope(parents.to_dict('records'),shifted(rows,scope),scope,calendar)
            choices.append(pd.DataFrame(result['choices']));summaries.append(dict(scope=scope,summary=result['summary']))
            for epoch,b in result['boundaries'].items():
                if epoch in boundaries and boundaries[epoch]!=b:raise ValueError('same_epoch_K_boundary_changed')
                boundaries[epoch]=b
            print(json.dumps(dict(phase='scope_selection_complete',scope=scope,parent_rows=len(result['choices']))),flush=True)
        if seen!=list(SCOPES) or counts['score_rows_read']!=1933480:raise ValueError('full_old_score_domain')
        for f in p['identity_inputs']['original130_folds']:
            if stats.get((f['scope'],f['cutoff']),{}).get('rows')!=f['prediction_children']:raise ValueError('complete_fold_forward_children')
        combined=pd.concat(choices,ignore_index=True);main=combined.loc[combined.scope.eq('main')].sort_values('sequence_index').reset_index(drop=True)
        held=combined.loc[combined.scope.ne('main')].sort_values('sequence_index').reset_index(drop=True)
        for f in (main,held):
            if len(f)!=161014 or f.event_id.tolist()!=forward.event_id.tolist():raise ValueError('complete_new_parent_scope_union')
        control=read_choices(inputs['control_choices_main'],forward);oldheld=read_choices(inputs['control_held_choices'],forward,True);counts['control_choice_reads']+=2
        changed_main=int(np.count_nonzero(main.chosen_action_id.to_numpy()!=control.chosen_action_id.to_numpy()))
        changed_held=int(np.count_nonzero(held.chosen_action_id.to_numpy()!=oldheld.chosen_action_id.to_numpy()))
        if changed_held:
            ids=set(oldheld.loc[oldheld.selected.eq(1),'chosen_action_id'])|set(held.loc[held.selected.eq(1),'chosen_action_id'])
            labels=label_subset(inputs['actions']['path'],ids,counts)
        else:labels=pd.DataFrame(columns=LABEL_FIELDS);labels['net_R_stress']=pd.Series(dtype=float)
        diagnostic,daily=held_diagnostic(oldheld,held,labels,labels_skipped=not changed_held)
        save_csv('choices_main.csv.gz',main);save_csv('choices_holdout.csv.gz',held)
        save_json('boundaries.json',dict(schema='stage156_voluntary_K_only_v1',epochs=boundaries,policy_version=selector.POLICY_VERSION,
            sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False))
        save_json('held_diagnostic.json',diagnostic);save_csv('held_daily.csv.gz',daily)
        save_json('selection_summary.json',dict(scopes=summaries,changed_main_parent_choices=changed_main,changed_held_parent_choices=changed_held,
            same_K_controls=True,cash_eligible=bool(changed_main),no_action_change_economic_identity_needs_independent_review=True))
        save_json('forward_summary.json',dict(folds=[dict(scope=k[0],cutoff=k[1],**dict(v)) for k,v in stats.items()],
            anchors=anchors,full_scores_not_duplicated=True,zero_offset_bits_preserved_by_conditional_add=True))
        save_json('fit_records.json',folds)
        after={k:h.inherited_stat(b) for k,b in large.items()}
        if after!=before or source_bundle()!=bundle:raise ValueError('source_or_input_stat_changed')
        save_json('input_stat_receipt.json',dict(before=before,after=after,old_large_hashes=0))
        status='completed'
    except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        save_json('terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,
            elapsed_seconds=time.monotonic()-started,counters=dict(counts),automatic_retry=False,new_cash=0))
    manifest=dict(schema='stage306_month_pool_oi_offset_fit_select_manifest_v1',status=status,protocol=pb,protocol_sha256=PROTOCOL_SHA,
        candidate=CANDIDATE,source_bundle=bundle,authorization=ab,inputs=inputs,artifacts=artifacts,folds=folds,counters=dict(counts),
        cash_eligible=bool(changed_main),changed_main_parent_choices=changed_main,
        held_known_nonharm=diagnostic['both_groups_known_nonharm'],held_differential_unknown=diagnostic['any_differential_unknown'],
        held_nominal_nonharm=(diagnostic['both_groups_known_nonharm'] if all(diagnostic['groups'][s]['known_u_equal_mean_increment_R'] is not None for s in SCOPES[1:]) else 'unsupported'),
        held_groups={s:{k:diagnostic['groups'][s][k] for k in ('known_u_equal_mean_increment_R','unknown_differential_selected_events','status')} for s in SCOPES[1:]},
        old52_refit=0,new_cash=0,old_control_replay=0,production_qualified=False,goal_complete=False)
    h.write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),scalar_fit_completed=counts['fit_completed'],new_cash=0,changed_main_parent_choices=changed_main)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('authorization','authorization-sha256','source-manifest','output'):parser.add_argument('--'+n,required=True)
    print(json.dumps(execute(parser.parse_args(argv)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
