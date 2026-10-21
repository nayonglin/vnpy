"""Frozen284: two scalar residual offsets and complete156 main reselection.

Import and tiny fixtures perform no actual financial work. Actual requires exact
root authorization, accepted287 source arithmetic and a fresh output directory.
Old52 models, weights, target, source arrays and cash programs stay unchanged.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import date,datetime,time,timedelta,timezone
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import time as clock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage284_wasde_offset_protocol/protocol.json'
PROTOCOL_SHA='b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193'
CLARIFICATIONS=PROTOCOL.with_name('technical_clarifications.json')
CLARIFICATIONS_SHA='b67e22d679d375d5f4eddd66d53e458a6dcdca2240f2366bcaf575baedc1580f'
CANDIDATE='WASDE_PUBLICATION_MONTH_OFFSET';END='2026-10-16'
CUTOFFS=('2020-01-01','2023-01-01')
TRAIN_FIELDS=['sequence_index','action_id','product_id','family_id','u_date','u_index',
    'reference_epoch','u_action_eligible','label_known_date','label_state','net_R_stress','sample_weight']
INPUT_ROLES={'fit_manifest','execution_protocol','market_protocol','mothers','actions','calendar',
    'source_manifest','source_review_receipt','control_choices_main','control_choice_manifest'}
SOURCE_NAMES=('stage285_wasde_offset_fit_select.py','test_stage285_wasde_offset_fit_select.py',
    'stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')
_BASE=None;_SELECTOR=None


def old_helper(selector=False):
    global _BASE,_SELECTOR
    current=_SELECTOR if selector else _BASE
    if current is None:
        name='stage156_voluntary_choices.py' if selector else 'stage130_contract_choice_fit.py'
        spec=importlib.util.spec_from_file_location('stage285_accepted_'+name[:-3],TOOLS/name)
        current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current)
        if selector:_SELECTOR=current
        else:_BASE=current
    return current


def flag(value):
    if value is True or value=='True':return True
    if value is False or value=='False':return False
    raise ValueError('projection_feature_eligible_not_boolean')


def available(day):
    return datetime.combine(date.fromisoformat(day)+timedelta(days=2),time(),
        ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()


def build_months(records):
    """Only already accepted projections; duplicates do not add report evidence."""
    grouped={};audit=[]
    for raw in records:
        r=dict(raw);sources=str(r.get('sources',''))
        v2=bool(re.search(r'[-_]V2(?:\.|\b)',sources,re.I))
        if (not flag(r['feature_eligible']) or r.get('state')!='quantity_observed'
                or v2 or r.get('correction_known_at')=='unknown'):
            audit.append(dict(WasdeNumber=r.get('WasdeNumber',''),release_date=r.get('release_date',''),
                state='excluded_projection',reason=r.get('unknown_reason') or 'V2_or_not_eligible'))
            continue
        day=date.fromisoformat(r['release_date']).isoformat();month=day[:7]
        if r.get('release_month')!=month or not str(r.get('WasdeNumber','')):
            raise ValueError('projection_release_identity')
        try:q=Decimal(r['q_raw'])
        except InvalidOperation:raise ValueError('projection_q_not_decimal')
        if not q.is_finite() or q<0 or not math.isfinite(float(q)):
            raise ValueError('projection_q_domain')
        boundary=available(day)
        if r.get('candidate_available_at_utc') and r['candidate_available_at_utc']!=boundary:
            raise ValueError('projection_availability_differs')
        grouped.setdefault(month,[]).append(dict(r,release_date=day,q_decimal=q,
            available_at_utc=boundary))
    months={}
    for month,rows in sorted(grouped.items()):
        pairs={(r['release_date'],r['q_decimal']) for r in rows}
        ids=sorted({str(r['WasdeNumber']) for r in rows})
        if len(pairs)!=1:
            record=dict(state='conflicting_publication_month',release_month=month,
                source_reports=ids,eligible=False,report_rows=len(rows))
        else:
            day,q=next(iter(pairs))
            record=dict(state='unique_publication_month',release_month=month,release_date=day,
                q_raw=str(q),q=float(q),available_at_utc=available(day),
                source_report=day+'|'+','.join(ids),source_reports=ids,
                duplicate_rows=len(rows)-1,eligible=True,report_rows=len(rows))
        months[month]=record;audit.append(record)
    return months,audit


def pulse_at(product,day,months):
    result=dict(eligible=False,q=math.nan,source_report='',release_date='',available_at_utc='',
        pulse_state='unmapped_product' if product!='DCE.C' else 'no_eligible_publication_in_month')
    if product!='DCE.C':return result
    d=date.fromisoformat(day);r=months.get(day[:7])
    if r is None:return result
    if not r['eligible']:
        result['pulse_state']=r['state'];return result
    close=datetime.combine(d,time(15),ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)
    result.update(source_report=r['source_report'],release_date=r['release_date'],available_at_utc=r['available_at_utc'])
    if close<datetime.fromisoformat(r['available_at_utc']):
        result['pulse_state']='before_available_at';return result
    result.update(eligible=True,q=r['q'],pulse_state='eligible_publication_month')
    return result


def fit_scalar(q,report_ids,residual,weights):
    q,ids,res,w=np.asarray(q,float),np.asarray(report_ids),np.asarray(residual,float),np.asarray(weights,float)
    if any(v.shape!=q.shape for v in (ids,res,w)) or q.ndim!=1:
        raise ValueError('scalar_training_shape')
    if (not np.isfinite(q).all() or not np.isfinite(res).all() or not np.isfinite(w).all()
            or (w<=0).any() or any(str(i)=='' for i in ids)):
        raise ValueError('scalar_training_finite_identity')
    z=np.zeros(len(q));total=float(w.sum())
    mean=float(np.average(q,weights=w)) if len(q) else None
    var=float(np.average((q-mean)**2,weights=w)) if len(q) else None
    nreports=len(set(ids.tolist()));supported=bool(nreports>=2 and var is not None and var>0 and math.isfinite(var))
    scale=math.sqrt(var) if supported else None
    if supported:z=(q-mean)/scale
    numerator=float(np.dot(w*z,res));denominator=float(np.dot(w,z*z)+1.)
    gamma=numerator/denominator if supported else 0.
    if not math.isfinite(gamma):raise ValueError('scalar_solution_nonfinite')
    model=dict(status='supported' if supported else 'unsupported',gamma=gamma,mean=mean,var=var,scale=scale,
        eligible_training_rows=len(q),distinct_release_identities=nreports,original_support_weight_sum=total,
        numerator=numerator,denominator=denominator,alpha=1.,fit_intercept=False,
        new_missing=False,new_product_ID=False,objective_weights_renormalized=False,
        normal_equation_abs_residual=abs(denominator*gamma-numerator) if supported else None)
    return model,z


def frozen_scores(raw,scaler,model):
    beta=np.asarray(model['coef'],float)
    if beta.shape!=(52,) or not np.isfinite(beta).all() or not math.isfinite(model['intercept']):
        raise ValueError('frozen52_model_dimension')
    scores=old_helper().design(raw,scaler)@beta+model['intercept']
    if not np.isfinite(scores).all():raise ValueError('frozen52_score_nonfinite')
    return scores


def shift_scores(old,q,model):
    scores=np.asarray(old,float).copy();q=np.asarray(q,float)
    if scores.shape!=q.shape or not np.isfinite(scores).all():raise ValueError('forward_score_shape_or_finite')
    z=np.zeros(len(q));delta=np.zeros(len(q))
    finite=np.isfinite(q)
    if model['status']=='supported':
        z[finite]=(q[finite]-model['mean'])/model['scale'];delta[finite]=model['gamma']*z[finite]
    changed=delta!=0
    scores[changed]=scores[changed]+delta[changed]
    if not np.isfinite(scores).all():raise ValueError('offset_score_nonfinite')
    return scores,z,delta


def validate_training(frame,cutoff,expected):
    f=frame.loc[:,TRAIN_FIELDS].copy()
    if len(f)!=expected or f.action_id.duplicated().any():raise ValueError('original_training_rows_or_identity')
    for name in ('sequence_index','u_index','u_action_eligible'):
        a=f[name].astype(float).to_numpy()
        if not np.isfinite(a).all() or not np.equal(a,np.floor(a)).all() or (a<0).any():
            raise ValueError('original_training_integer_identity')
        f[name]=a.astype(np.int64)
    for name in ('net_R_stress','sample_weight'):f[name]=f[name].astype(float)
    if (not np.isfinite(f.net_R_stress).all() or not np.isfinite(f.sample_weight).all()
            or not f.sample_weight.gt(0).all() or not f.u_action_eligible.eq(1).all()
            or not f.label_state.eq('closed_complete_bar_model').all() or not f.u_date.lt(cutoff).all()
            or f.label_known_date.eq('').any() or not f.label_known_date.lt(cutoff).all()
            or not f.family_id.eq(f.product_id.str.removesuffix('_F')).all()
            or not f.reference_epoch.str.rsplit('.',n=1).str[0].eq(f.product_id).all()
            or (np.diff(f.sequence_index.to_numpy())<=0).any()):
        raise ValueError('original_training_maturity_or_weights')
    return f


def select_full(mothers,scores,calendar,end=END):
    result=old_helper(True).select_full_pool(mothers,scores,calendar,end,audit_sink=lambda row:None)
    for row in result['choices']:row['candidate']=CANDIDATE
    return result


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_small(b):
    if b['bytes']>200000:raise ValueError('small_input_limit')
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('small_binding_changed')
    return raw


def read_json(b):return json.loads(read_small(b))


def inherited_stat(b):
    p=Path(b['path']);s=p.stat()
    if not p.is_file() or s.st_size!=b['bytes']:raise ValueError('inherited_size_changed '+str(p))
    return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,device=s.st_dev,mtime_ns=s.st_mtime_ns,
        inherited_sha256=b['sha256'],rehashed=False)


def source_bundle():return sorted((binding(TOOLS/n) for n in SOURCE_NAMES),key=lambda b:b['path'])


def write_json(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists() or LINE/'outputs/stage285_wasde_offset_fit_select' not in out.parents:
        raise ValueError('fresh_stage285_output_required')
    pb,cb=binding(PROTOCOL),binding(CLARIFICATIONS)
    if pb['sha256']!=PROTOCOL_SHA or cb['sha256']!=CLARIFICATIONS_SHA:raise ValueError('frozen284_or_clarification_changed')
    protocol=read_json(pb);read_json(cb);ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root_authorization_sha')
    auth=read_json(ab)
    expected=dict(schema='stage285_exact_root_authorization_v1',authorized_by='root',exact_source_authorized=True,
        protocol_sha256=PROTOCOL_SHA,technical_clarifications_sha256=CLARIFICATIONS_SHA,
        candidate=CANDIDATE,output=str(out),max_new_fit=2,max_new_cash=0)
    if any(auth.get(k)!=v for k,v in expected.items()) or auth.get('source_bundle')!=source_bundle():
        raise ValueError('exact_root285_authorization_required')
    inputs=auth.get('inputs',{})
    if set(inputs)!=INPUT_ROLES or Path(args.source_manifest).resolve()!=Path(inputs['source_manifest']['path']).resolve():
        raise ValueError('explicit_source_manifest_or_roles')
    return out,protocol,pb,cb,auth,ab


def validate_inputs(protocol,inputs,counters):
    small={name:read_json(inputs[name]) for name in ('fit_manifest','execution_protocol','market_protocol',
        'source_manifest','source_review_receipt','control_choice_manifest')}
    fit,source,review=small['fit_manifest'],small['source_manifest'],small['source_review_receipt']
    if (fit.get('schema')!='stage130_contract_choice_fit_v1' or fit.get('status')!='completed'
            or fit.get('actual_fit_calls_completed')!=6):raise ValueError('accepted130_manifest_required')
    for role in ('mothers','actions'):
        if not same(inputs[role],fit['input_bindings'][role]):raise ValueError('original129_binding '+role)
    if not same(protocol['training']['original_common'],fit['input_bindings']['common']) or not same(protocol['forward']['scores'],fit['child_scores']):
        raise ValueError('original130_common_or_scores')
    if not same(inputs['execution_protocol'],fit['protocol']) or not same(inputs['market_protocol'],small['execution_protocol']['inputs']['market_protocol']):
        raise ValueError('unchanged_execution_market')
    if not same(inputs['calendar'],small['market_protocol']['calendar']):raise ValueError('original_calendar')
    if source.get('schema')!='stage282_wasde_incremental_projection_manifest_v1' or source.get('status')!='completed':
        raise ValueError('completed282_source_required')
    if (review.get('schema')!='stage287_wasde_incremental_review_v1' or review.get('status')!='completed'
            or review.get('core_blockers')!=0 or review.get('research_arithmetic_accepted') is not True
            or not same(review.get('source_manifest',{}),inputs['source_manifest'])):
        raise ValueError('accepted287_exact_source_arithmetic_required_not_PIT')
    cm=small['control_choice_manifest']
    if cm.get('schema')!='stage156_voluntary_choices_manifest_v1' or cm.get('parent_rows')!=161014:
        raise ValueError('original156_full_control_required')
    if not same(cm['artifacts']['choices_main'],inputs['control_choices_main']) or not same(cm['inputs']['fit_manifest'],inputs['fit_manifest']):
        raise ValueError('original156_control_binding')
    records=read_json(fit['fit_records']);main=[r for r in records if r['scope']=='main']
    for f in protocol['training']['original_folds']:
        old=next(r for r in main if r['cutoff']==f['cutoff'])
        for k in ('training_rows','training_dates','training_families','training_groups','prediction_children','prediction_mothers','max_u_date','max_label_known_date'):
            if old[k]!=f[k]:raise ValueError('frozen_original_fold '+k)
        for k in ('scaler','portable_model','training_identity_weights'):
            if not same(old[k],f[k]):raise ValueError('frozen_original_fold_binding '+k)
    projection=source['artifacts']['report_projection'];raw=read_small(projection)
    reports=pd.read_csv(io.BytesIO(raw),compression='gzip',dtype=str,keep_default_na=False).to_dict('records')
    counters['source_projection_reads']+=1;months,audit=build_months(reports)
    cal=np.load(io.BytesIO(read_small(inputs['calendar'])),allow_pickle=False);counters['calendar_reads']+=1
    calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal]
        if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
    if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('source_calendar_identity')
    return months,audit,calendar,projection


def forward_stream(path,models,months,counters,corn_sink):
    fields=old_helper(True).SCORE_FIELDS;cache={}
    for chunk in pd.read_csv(path,usecols=fields,dtype=str,keep_default_na=False,chunksize=100000,float_precision='round_trip'):
        counters['non_main_scores_skipped']+=int(chunk.scope.ne('main').sum());main=chunk.loc[chunk.scope.eq('main')].copy()
        for cutoff,frame in main.groupby('cutoff',sort=False):
            if cutoff not in models:raise ValueError('unexpected_main_cutoff')
            old=frame.score.astype(float).to_numpy();q=np.full(len(frame),np.nan);pulses={}
            for i,row in enumerate(frame.to_dict('records')):
                if row['product_id']=='DCE.C':
                    key=row['u_date']
                    if key not in cache:cache[key]=pulse_at('DCE.C',key,months)
                    p=cache[key];pulses[i]=p;q[i]=p['q']
            shifted,z,delta=shift_scores(old,q,models[cutoff])
            if not np.array_equal(shifted[np.isnan(q)].view(np.uint64),old[np.isnan(q)].view(np.uint64)):
                raise ValueError('zero_offset_bridge_changed')
            for i,row in enumerate(frame.to_dict('records')):
                counters['main_score_rows']+=1;counters['main_scores_'+cutoff]+=1
                row['score']=float(shifted[i])
                if i in pulses:
                    p=pulses[i];counters['corn_forward_rows']+=1;counters['corn_eligible_rows']+=int(p['eligible'])
                    counters['corn_nonzero_delta']+=int(delta[i]!=0)
                    corn_sink(dict(row,old_score=float(old[i]),new_score=float(shifted[i]),q=p['q'] if p['eligible'] else '',
                        z=float(z[i]),delta=float(delta[i]),gamma=models[cutoff]['gamma'],
                        source_report=p['source_report'],release_date=p['release_date'],available_at_utc=p['available_at_utc'],
                        pulse_state=p['pulse_state'],old_positive=int(old[i]>0),new_positive=int(shifted[i]>0)))
                yield row


def execute(args):
    out,protocol,pb,cb,auth,ab=authorize(args);inputs=auth['inputs'];out.mkdir(parents=True,exist_ok=False)
    began=clock.monotonic();artifacts={};before_bundle=source_bundle();counters=Counter()
    counters.update(dict(fit_attempted=0,fit_completed=0,cash=0,old_control_replay=0,SQL=0,labels=0,
        old_large_hash=0,common_npz_reads=0,training_csv_reads=0,mother_csv_reads=0,score_csv_reads=0,
        control_choices_reads=0,source_projection_reads=0,calendar_reads=0,main_score_rows=0,non_main_scores_skipped=0,
        corn_forward_rows=0,corn_eligible_rows=0,corn_nonzero_delta=0))
    def save_json(name,value):
        write_json(out/name,value);b=binding(out/name);artifacts[name.removesuffix('.json')]=b;return b
    def save_csv(name,frame):
        frame.to_csv(out/name,index=False,compression={'method':'gzip','mtime':0},float_format='%.17g')
        b=binding(out/name);artifacts[name.removesuffix('.csv.gz')]=b;return b
    save_json('started.json',dict(schema='stage285_started_v1',protocol=pb,clarifications=cb,authorization=ab,
        source_bundle=before_bundle,candidate=CANDIDATE,automatic_retry=False))
    status='failed';failure=None;stats_before={};fold_records=[];choice_summary=None
    try:
        months,month_audit,calendar,projection=validate_inputs(protocol,inputs,counters)
        save_json('source_months.json',dict(months=months,audit=month_audit,source_projection=projection,
            publication_month_pulse=True,first_seen_PIT_proved=False))
        large={k:inputs[k] for k in ('mothers','actions','control_choices_main')}
        large.update(common=protocol['training']['original_common'],scores=protocol['forward']['scores'])
        for f in protocol['training']['original_folds']:large['train_'+f['cutoff']]=f['training_identity_weights']
        stats_before={k:inherited_stat(b) for k,b in large.items()}
        selector=old_helper(True);mothers=pd.read_csv(inputs['mothers']['path'],usecols=selector.IDENTITY,dtype=str,keep_default_na=False)
        counters['mother_csv_reads']+=1
        for k in ('sequence_index','u_index'):mothers[k]=mothers[k].astype(np.int64)
        if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
                or mothers.family_id.nunique()!=95 or not np.array_equal(mothers.sequence_index,np.arange(399252))
                or not np.array_equal(mothers.u_date.to_numpy(),np.asarray(calendar)[mothers.u_index.to_numpy()])):
            raise ValueError('complete_original_mother_identity')
        forward=mothers.loc[mothers.u_date.ge(CUTOFFS[0])&mothers.u_date.le(END)]
        if len(forward)!=161014:raise ValueError('full_forward_mothers')
        with np.load(protocol['training']['original_common']['path'],allow_pickle=False) as z:
            common=z['common'];columns=z['columns'].tolist()
        counters['common_npz_reads']+=1
        if common.shape!=(1552456,26) or columns!=old_helper().COMMON:raise ValueError('original_COMMON26_shape_names')
        plans=[]
        for f in protocol['training']['original_folds']:
            cutoff=f['cutoff'];scaler=read_json(f['scaler']);base=read_json(f['portable_model'])
            if (base['scope']!='main' or base['cutoff']!=cutoff or len(base['coef'])!=52
                    or base['feature_names']!=scaler['feature_names'] or base['feature_names']!=old_helper().FEATURE_NAMES
                    or scaler['common']['columns']!=columns or base['parameters']!=old_helper().PARAMETERS):
                raise ValueError('immutable_original_base_model')
            train=pd.read_csv(f['training_identity_weights']['path'],usecols=TRAIN_FIELDS,dtype=str,keep_default_na=False)
            counters['training_csv_reads']+=1;train=validate_training(train,cutoff,f['training_rows'])
            if (train.u_date.nunique()!=f['training_dates'] or train.family_id.nunique()!=f['training_families']
                    or train.u_date.max()!=f['max_u_date'] or train.label_known_date.max()!=f['max_label_known_date']
                    or train.sequence_index.max()>=len(common)
                    or not np.array_equal(train.u_date.to_numpy(),np.asarray(calendar)[train.u_index.to_numpy()])):
                raise ValueError('original_training_summary_identity')
            selected=train.loc[train.product_id.eq('DCE.C')].copy();cache={}
            for day in selected.u_date.unique():cache[day]=pulse_at('DCE.C',day,months)
            pulse=[cache[day] for day in selected.u_date]
            mask=np.asarray([p['eligible'] for p in pulse],bool);selected=selected.loc[mask].reset_index(drop=True)
            pulse=[p for p,use in zip(pulse,mask) if use]
            q=np.asarray([p['q'] for p in pulse]);ids=np.asarray([p['source_report'] for p in pulse])
            s52=frozen_scores(common[selected.sequence_index.to_numpy()],scaler,base)
            y=selected.net_R_stress.to_numpy();w=selected.sample_weight.to_numpy();residual=y-s52
            # Both original domains/base inputs are validated before either solve.
            plans.append(dict(f=f,selected=selected,pulse=pulse,q=q,ids=ids,s52=s52,residual=residual,w=w))
        del common
        models={}
        for plan in plans:
            f=plan['f'];cutoff=f['cutoff'];counters['fit_attempted']+=1
            save_json('fit_progress.json' if counters['fit_attempted']==1 else 'fit_progress_2.json',dict(counters))
            model,z=fit_scalar(plan['q'],plan['ids'],plan['residual'],plan['w'])
            counters['fit_completed']+=1;model.update(scope='main',cutoff=cutoff,candidate=CANDIDATE,
                original_training_rows=f['training_rows'],frozen_base_model=f['portable_model'],frozen_base_scaler=f['scaler'],
                original_training_identity_weights=f['training_identity_weights'],held_status='unsupported_no_held_fit')
            models[cutoff]=model;model_ref=save_json('offset_model_'+cutoff+'.json',model)
            table=plan['selected'].copy();table['q_raw']=plan['q'];table['s52']=plan['s52'];table['residual']=plan['residual']
            table['z']=z;table['gamma']=model['gamma'];table['delta']=model['gamma']*z
            table['nonzero_design']=(z!=0).astype(int)
            for k in ('source_report','release_date','available_at_utc'):table[k]=[p[k] for p in plan['pulse']]
            table_ref=save_csv('train_offset_'+cutoff+'.csv.gz',table)
            fold_records.append(dict(scope='main',cutoff=cutoff,model=model_ref,training_eligible_finite=table_ref,
                original_training_rows=f['training_rows'],status=model['status'],gamma=model['gamma']))
        if counters['fit_attempted']!=2 or counters['fit_completed']!=2:raise ValueError('exact_two_scalar_solves')
        corn_fields=selector.SCORE_FIELDS+['old_score','new_score','q','z','delta','gamma','source_report',
            'release_date','available_at_utc','pulse_state','old_positive','new_positive']
        counters['score_csv_reads']+=1
        with gzip.open(out/'forward_corn_delta.csv.gz','xt',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=corn_fields);writer.writeheader()
            score_stream=forward_stream(protocol['forward']['scores']['path'],models,months,counters,writer.writerow)
            result=select_full(forward.to_dict('records'),score_stream,calendar)
        artifacts['forward_corn_delta']=binding(out/'forward_corn_delta.csv.gz')
        if (counters['main_score_rows']!=966740 or counters['non_main_scores_skipped']!=966740
                or {c:counters['main_scores_'+c] for c in CUTOFFS}!={f['cutoff']:f['prediction_children'] for f in protocol['training']['original_folds']}):
            raise ValueError('full_forward_main_domain')
        choices=pd.DataFrame(result['choices'])
        if len(choices)!=161014 or choices.event_id.tolist()!=forward.event_id.tolist():raise ValueError('full_new_parent_identity')
        original=pd.read_csv(inputs['control_choices_main']['path'],dtype=str,keep_default_na=False,
            usecols=['event_id','family_id','chosen_action_id','selected'])
        counters['control_choices_reads']+=1
        if original.event_id.tolist()!=choices.event_id.tolist():raise ValueError('old_control_parent_identity')
        outside=choices.family_id.ne('DCE.C').to_numpy()
        if not np.array_equal(original.chosen_action_id.to_numpy()[outside],choices.chosen_action_id.to_numpy()[outside]):
            raise ValueError('unaffected_family_choice_bridge')
        differences=original.chosen_action_id.to_numpy()!=choices.chosen_action_id.to_numpy()
        choice_summary=dict(result['summary'],candidate=CANDIDATE,changed_parent_choices_vs156=int(differences.sum()),
            changed_outside_DCE_C_family=int(np.count_nonzero(differences&outside)),all98_original_products_retained=True,
            held_fit=0,held_status='unsupported_not_passed',zero_score_bridge_verified=True,
            cash_eligible=bool(choices.selected.any()),source_month_conflicts=sum(not v['eligible'] for v in months.values()))
        save_csv('choices_main.csv.gz',choices)
        save_json('boundaries.json',dict(schema='stage156_voluntary_K_only_v1',epochs=result['boundaries'],
            policy_version=selector.POLICY_VERSION,sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False))
        save_json('selection_summary.json',choice_summary);save_json('fit_records.json',fold_records)
        if before_bundle!=source_bundle():raise ValueError('285_source_changed_during_actual')
        after={k:inherited_stat(b) for k,b in large.items()}
        if after!=stats_before:raise ValueError('old_input_stat_changed_during_actual')
        save_json('input_stat_receipt.json',dict(before=stats_before,after=after,old_large_rehash=0))
        status='completed'
    except BaseException as exc:
        failure=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        terminal=dict(schema='stage285_terminal_v1',status=status,exit_code=0 if status=='completed' else 1,
            elapsed_seconds=clock.monotonic()-began,counters=dict(counters),failure=failure,automatic_retry=False,
            new_cash=0,production_qualified=False,first_seen_PIT_proved=False)
        save_json('terminal.json',terminal)
    manifest=dict(schema='stage285_wasde_offset_fit_select_manifest_v1',status=status,protocol=pb,protocol_sha256=PROTOCOL_SHA,
        technical_clarifications=cb,candidate=CANDIDATE,authorization=ab,source_bundle=before_bundle,
        inputs=dict(inputs,technical_clarifications=cb),
        artifacts=artifacts,folds=fold_records,counters=dict(counters),cash_eligible=choice_summary['cash_eligible'],
        source_review_is_arithmetic_only=True,held_status='unsupported_not_passed',old52_refit=0,
        old_labels_rebuilt=0,control_replay=0,new_cash=0,first_seen_PIT_proved=False,production_qualified=False,goal_complete=False)
    write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),fit_completed=counters['fit_completed'],cash=0,
        changed_parent_choices_vs156=choice_summary['changed_parent_choices_vs156'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('authorization','authorization-sha256','source-manifest','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args(argv)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
