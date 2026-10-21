"""One root-authorized new-model/forecast/K/held review; no fit or cash replay.

Accepted old COMMON normal blocks and weights are inherited. New q equations,
all new forward scores and held diagnostics are recomputed independently.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

TOOLS=Path(__file__).resolve().parent; LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage204_local_curve_information_protocol/protocol.json'
PROTOCOL_SHA='b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca'
MANIFEST=LINE/'outputs/stage205_local_curve_information_fit/actual_run1/manifest.json'
MANIFEST_SHA='a373ba2e5d8e8835131f0752b3c2b4f6fc73af71a84b3c484d9f158c013ef13f'
OUTPUT=LINE/'outputs/stage207_local_curve_information_review/model_forecast_selection1'
SCOPES=('main','holdout_0','holdout_1'); CUTOFFS=('2020-01-01','2023-01-01'); END='2026-10-16'
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id',
        'family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
        'label_state','participation_state','net_R_stress','label_known_date']
ANUM=['sequence_index','mother_sequence_index','u_index','u_action_eligible','net_R_stress']
TRAIN=['sequence_index','action_id','product_id','family_id','u_date','label_known_date',
       'label_state','u_action_eligible','net_R_stress','sample_weight']

def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def bound_json(b):
    assert b['bytes']<2000000, 'only small JSON binding checks'
    assert binding(b['path'])=={k:b[k] for k in ('path','bytes','sha256')}
    return json.loads(Path(b['path']).read_text())

def stat(b):
    p=Path(b['path']); s=p.stat(); assert s.st_size==b['bytes']
    return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,device=s.st_dev,
                mtime_ns=s.st_mtime_ns,inherited_sha256=b['sha256'],rehashed=False)

def sources():
    return [binding(TOOLS/n) for n in ('stage207_local_curve_information_review.py',
        'test_stage207_local_curve_information_review.py','stage156_voluntary_choices.py')]

def write(path,obj):
    with Path(path).open('x') as f: json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False); f.write('\n')

def near(a,b,rtol=1e-10,atol=1e-11):
    np.testing.assert_allclose(a,b,rtol=rtol,atol=atol,equal_nan=True)

def family_group(family): return int(hashlib.sha256(str(family).encode()).hexdigest(),16)%2

def q_stats(raw,w):
    finite=np.isfinite(raw); wf=w[finite]; values=raw[finite]
    assert len(values)>0 and np.isfinite(w).all() and (w>0).all()
    mean=float(np.dot(wf,values)/wf.sum()); var=float(np.dot(wf,(values-mean)**2)/wf.sum())
    assert np.isfinite(mean) and np.isfinite(var) and var>0
    return dict(mean=mean,var=var,scale=math.sqrt(var),finite_count=int(finite.sum()),
        missing_count=int((~finite).sum()),finite_weight_sum=float(wf.sum()),missing_weight_sum=float(w[~finite].sum()),
        raw_finite_min=float(values.min()),raw_finite_max=float(values.max()),training_rows=len(raw))

def design(raw,q,scaler,qs):
    finite=np.isfinite(raw); mu=np.asarray(scaler['mean']); sd=np.asarray(scaler['scale'])
    x=np.column_stack((np.where(finite,(raw-mu)/sd,0.),(~finite).astype(float)))
    s=np.zeros(len(q)); known=np.isfinite(q); s[known]=(q[known]-qs['mean'])/qs['scale']
    assert x.shape==(len(q),52) and np.isfinite(x).all() and np.isfinite(s).all()
    return np.column_stack((x,s))

def q_equations(raw,q,w,y,scaler,qs):
    known=np.isfinite(q); s=np.zeros(len(q)); s[known]=(q[known]-qs['mean'])/qs['scale']
    sw=w*s; row=np.empty(54)
    for j in range(26):
        finite=np.isfinite(raw[:,j]); value=np.zeros(len(raw))
        value[finite]=(raw[finite,j]-scaler['mean'][j])/scaler['scale'][j]
        row[j]=np.dot(sw,value); row[j+26]=sw[~finite].sum()
    row[52]=np.dot(sw,s)+1.; row[53]=sw.sum()
    return row,float(np.dot(sw,y))

def inherited_equations(old_lhs,old_rhs,qrow,qrhs):
    mapping=np.r_[np.arange(52),53]; lhs=np.empty((54,54)); rhs=np.empty(54)
    lhs[np.ix_(mapping,mapping)]=old_lhs; rhs[mapping]=old_rhs
    lhs[52,:]=qrow; lhs[:,52]=qrow; rhs[52]=qrhs
    return lhs,rhs

def check_choice_rows(expected,actual,scope,arm):
    observed=actual.loc[actual.scope.eq(scope)].set_index('sequence_index')
    assert len(expected)==len(observed) and not observed.index.duplicated().any()
    wanted=pd.DataFrame(expected); wanted['scope']=scope; wanted['arm']=arm
    got=observed.loc[wanted.sequence_index.astype(str)].reset_index()
    numeric={'sequence_index','u_index','proposed_score','chosen_action_sequence_index','score','selected'}
    for key in wanted:
        if key in numeric:
            values=pd.to_numeric(got[key],errors='coerce').to_numpy(float)
            near(values,wanted[key].to_numpy(float),rtol=1e-12,atol=1e-12)
            assert np.array_equal(got[key].eq('').to_numpy(),wanted[key].isna().to_numpy())
        else:
            assert got[key].tolist()==wanted[key].fillna('').astype(str).tolist(),('choice_difference',scope,key)

def held_diagnostic(control,candidate,actions):
    chosen={}
    for arm,rows in [('COMMON52',control),('CURVE53',candidate)]:
        for r in sorted(rows,key=lambda r:(not bool(r['selected']),r['sequence_index'])):
            chosen.setdefault((arm,r['family_id'],r['u_index']),r)
    keys={(f,u) for arm,f,u in chosen if arm=='COMMON52'}
    assert keys=={(f,u) for arm,f,u in chosen if arm=='CURVE53'}
    by_id=actions.set_index('action_id'); daily=[]; same_unknown=0; different_unknown=0; all_delta=[]
    def value(identifier):
        if not identifier: return 0.
        a=by_id.loc[identifier]
        if a.participation_state=='known_nonparticipation': return 0.
        if (a.label_state=='closed_complete_bar_model' and math.isfinite(a.net_R_stress)
                and a.label_known_date and a.label_known_date<=END): return float(a.net_R_stress)
        return math.nan
    for f,u in sorted(keys):
        aa=chosen[('COMMON52',f,u)]; bb=chosen[('CURVE53',f,u)]
        assert aa['u_date']==bb['u_date']; ai=aa['chosen_action_id']; bi=bb['chosen_action_id']
        av,bv=value(ai),value(bi); known=math.isfinite(av) and math.isfinite(bv)
        same=ai==bi; delta=0. if same else bv-av if known else math.nan
        same_unknown+=int(same and bool(ai) and not known); unknown=not same and not known
        different_unknown+=int(unknown); all_delta.append(delta)
        daily.append(dict(u_date=aa['u_date'],delta_R=delta,known=math.isfinite(delta),unknown=unknown))
    day=pd.DataFrame(daily).groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),
        known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index()
    mean=float(day.delta_R.mean()) if day.delta_R.notna().any() else None
    result=dict(known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=different_unknown,
        common_unresolved_same_action=same_unknown,full_family_u=len(keys),known_increment_family_u=int(np.isfinite(all_delta).sum()),
        known_source_days=int(day.delta_R.notna().sum()),selected_by_arm={
            'COMMON52':sum(int(r['selected']) for r in control),'CURVE53':sum(int(r['selected']) for r in candidate)},
        nominal_pass=mean is not None and mean>0 and different_unknown==0,
        annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()) if v.delta_R.notna().any() else None,
            source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum())) for y,v in day.groupby(day.u_date.str[:4])])
    return result,day

def actual(auth,output):
    started=time.monotonic(); output.mkdir(parents=True,exist_ok=False)
    counts=dict(fit=0,cash=0,SQL=0,source_projection=0,large_input_hash_scans=0,common_reads=0,q_reads=0,
        cached_training_reads=0,action_reads=0,mother_reads=0,new_score_reads=0,old_score_reads=0,new_choice_reads=0)
    try:
        protocol=json.loads(PROTOCOL.read_text()); manifest=bound_json(auth['manifest'])
        assert manifest['status']=='completed' and manifest['cash_eligible'] and manifest['protocol_sha256']==PROTOCOL_SHA
        assert manifest['input_bindings']==protocol['input_bindings']
        assert manifest['source_bundle']==auth['producer_source_bundle']
        for src in manifest['source_bundle']: assert binding(src['path'])==src
        old_manifest=bound_json(protocol['input_bindings']['control_fit_manifest'])
        old_records=bound_json(protocol['input_bindings']['control_fit_records'])
        assert old_manifest['fit_records']==protocol['input_bindings']['control_fit_records']
        records=bound_json(manifest['fit_records']); gate=bound_json(manifest['direction_gate'])
        preflight=bound_json(manifest['preflight']); summary=bound_json(manifest['summary']); terminal=bound_json(manifest['terminal'])
        assert manifest['source_read_receipt']['before']==manifest['source_read_receipt']['after']
        assert manifest['counters']==summary['counters']==terminal['counters']
        expected={'fit_calls_attempted':6,'fit_calls_completed':6,'old_fit':0,'cash':0,'old_cash':0,'SQL':0,
            'source_projection':0,'new_labels':0,'downloads':0,'large_input_hash_scans':0,
            'action_csv_reads':1,'mother_csv_reads':1,'common_npz_reads':1,'q_npz_reads':1,'training_weight_csv_reads':6,
            'training_weights_recomputed':0,'control_score_csv_reads':1,'prediction_calls_attempted':6,
            'prediction_calls_completed':6,'prediction_model_rows':1933480,'candidate_selection_calls':3,
            'control_held_selection_calls':2,'control_main_selection_calls':0}
        assert manifest['counters']==expected and manifest['control_choices_main_reused']==protocol['input_bindings']['control_choices_main_K']
        assert preflight['ready'] and preflight['all_support_before_any_fit'] and len(preflight['cells'])==6
        inherited={k:protocol['input_bindings'][k] for k in ('actions','mothers','common','q_vector','control_child_scores')}
        for r in old_records: inherited['train/'+r['scope']+'/'+r['cutoff']]=r['training_identity_weights']
        before={k:stat(b) for k,b in inherited.items()}
        counts['q_reads']+=1
        with np.load(protocol['input_bindings']['q_vector']['path'],allow_pickle=False) as d:
            assert np.array_equal(d['sequence_index'],np.arange(1552456)); q=d['q_raw']
        counts['common_reads']+=1
        with np.load(protocol['input_bindings']['common']['path'],allow_pickle=False) as d:
            common=d['common']; columns=d['columns'].tolist()
        assert common.shape==(1552456,26) and q.shape==(1552456,) and not np.isinf(q).any()
        old_by={(r['scope'],r['cutoff']):r for r in old_records}; fitted={}; model_checks=[]
        assert len(records)==6 and {(r['scope'],r['cutoff']) for r in records}=={(s,c) for s in SCOPES for c in CUTOFFS}
        with threadpool_limits(limits=1):
            for r in records:
                key=(r['scope'],r['cutoff']); old=old_by[key]
                assert r['training_identity_weights']==old['training_identity_weights'] and r['common_scaler']==old['scaler']
                assert r['control_normal_equations']==old['normal_equations'] and not r['training_weights_recomputed']
                counts['cached_training_reads']+=1
                t=pd.read_csv(old['training_identity_weights']['path'],usecols=TRAIN,dtype=str,keep_default_na=False)
                for c in ('sequence_index','u_action_eligible','net_R_stress','sample_weight'): t[c]=t[c].astype(float)
                ti=t.sequence_index.to_numpy(np.int64); w=t.sample_weight.to_numpy(float); y=t.net_R_stress.to_numpy(float)
                assert len(t)==r['training_rows']==old['training_rows'] and np.all(np.diff(ti)>0)
                assert t.action_id.is_unique and t.u_date.lt(key[1]).all() and t.label_known_date.ne('').all() and t.label_known_date.lt(key[1]).all()
                assert t.label_state.eq('closed_complete_bar_model').all() and t.u_action_eligible.eq(1).all() and np.isfinite(y).all()
                if key[0]!='main': assert t.family_id.map(family_group).ne(int(key[0][-1])).all()
                scaler=bound_json(r['scaler']); os=bound_json(old['scaler']); model=bound_json(r['portable_model'])
                assert scaler['common']==os['common'] and scaler['common']['columns']==columns
                assert len(model['coef'])==53 and model['feature_names']==os['feature_names']+['local_curve_q_standardized']
                assert model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky')
                qs=q_stats(q[ti],w)
                for name,val in qs.items(): near(val,r['q_statistics'][name]); near(val,scaler['q'][name])
                with np.load(r['training_q_support']['path'],allow_pickle=False) as d:
                    assert np.array_equal(d['sequence_index'],ti); near(d['q_raw'],q[ti],rtol=0,atol=0)
                row,qrhs=q_equations(common[ti],q[ti],w,y,os['common'],qs)
                with np.load(old['normal_equations']['path'],allow_pickle=False) as d: lhs,rhs=inherited_equations(d['lhs'],d['rhs'],row,qrhs)
                beta=np.r_[model['coef'],model['intercept']]
                with np.load(r['normal_equations']['path'],allow_pickle=False) as d:
                    near(d['lhs'],lhs,rtol=1e-10,atol=1e-7); near(d['rhs'],rhs,rtol=1e-10,atol=1e-7)
                    near(d['coefficient_with_intercept'],beta,rtol=0,atol=0); near(d['weight_sum'],w.sum())
                assert np.isfinite(beta).all(); near(lhs@beta,rhs,rtol=1e-8,atol=1e-7)
                assert beta[52]<0 and beta[52]==r['q_coefficient'] and r['q_strictly_negative']
                fitted[key]=(model,os['common'],qs)
                model_checks.append(dict(scope=key[0],cutoff=key[1],training_rows=len(t),q_statistics=qs,
                    q_coefficient=float(beta[52]),independent_equation_max_abs_residual=float(np.abs(lhs@beta-rhs).max())))
                print(json.dumps(dict(phase='new_model_math_verified',scope=key[0],cutoff=key[1])),flush=True)
        assert gate['passed'] and gate['exact_six_unique_models'] and all(x['strictly_negative'] for x in gate['outcomes'])
        for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
            rows=[json.loads(s) for s in (MANIFEST.parent/name).read_text().splitlines()]
            assert [r['count'] for r in rows]==list(range(1,7)) and {(r['scope'],r['cutoff']) for r in rows}==set(fitted)
        checkpoint=dict(schema='stage207_new_model_math_checkpoint_v1',status='completed',core_blockers=0,
            manifest=auth['manifest'],models=model_checks,counters=counts.copy(),inherited_old_common_math=True)
        write(output/'models_checkpoint.json',checkpoint)
        counts['action_reads']+=1
        a=pd.read_csv(protocol['input_bindings']['actions']['path'],usecols=ACTION,dtype=str,keep_default_na=False)
        for c in ANUM: a[c]=pd.to_numeric(a[c],errors='coerce')
        assert len(a)==1552456 and np.array_equal(a.sequence_index,np.arange(len(a))) and a.action_id.is_unique
        counts['mother_reads']+=1
        m=pd.read_csv(protocol['input_bindings']['mothers']['path'],usecols=IDENTITY,dtype=str,keep_default_na=False)
        for c in ('sequence_index','u_index'): m[c]=m[c].astype(int)
        assert len(m)==399252 and np.array_equal(m.sequence_index,np.arange(len(m))) and m.event_id.is_unique
        forward=a.u_date.ge(CUTOFFS[0]).to_numpy(); forward_m=m.loc[m.u_date.ge(CUTOFFS[0])]
        assert forward.sum()==966740 and len(forward_m)==161014
        calendar_raw=np.load(io.BytesIO(Path(protocol['input_bindings']['calendar']['path']).read_bytes()),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in calendar_raw]
            if calendar_raw.dtype.kind in 'iu' else calendar_raw.astype('datetime64[D]').astype(str).tolist())
        spec=importlib.util.spec_from_file_location('accepted156',TOOLS/'stage156_voluntary_choices.py')
        voluntary=importlib.util.module_from_spec(spec); spec.loader.exec_module(voluntary)
        accepted156=bound_json(protocol['input_bindings']['control_choice_manifest'])
        assert binding(TOOLS/'stage156_voluntary_choices.py')==accepted156['implementation']
        actual_choices={}
        for role in ('choices_main','choices_holdout','control_held_K'):
            counts['new_choice_reads']+=1
            actual_choices[role]=pd.read_csv(manifest[role]['path'],dtype=str,keep_default_na=False)
            assert len(actual_choices[role])==161014
        saved_bounds=bound_json(manifest['boundaries'])['epochs']; bounds={}; held_new=[]; held_old=[]
        score_seen={True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)}; score_counts=Counter(); max_score_error=0.; old_rows=0
        def score_stream(candidate):
            nonlocal max_score_error,old_rows
            role='child_scores' if candidate else 'control_child_scores'
            b=manifest[role] if candidate else protocol['input_bindings'][role]
            counts['new_score_reads' if candidate else 'old_score_reads']+=1
            use=voluntary.SCORE_FIELDS+(['arm','q_raw','q_design','q_missing_diagnostic'] if candidate else [])
            num={'sequence_index':'int64','mother_sequence_index':'int64','u_index':'int64','u_action_eligible':'int64','score':'float64'}
            if candidate: num.update(q_raw='float64',q_design='float64',q_missing_diagnostic='int64')
            for chunk in pd.read_csv(b['path'],usecols=use,dtype={k:num.get(k,str) for k in use},keep_default_na=False,
                    na_values={'q_raw':['']},float_precision='round_trip',chunksize=50000):
                if not candidate:
                    old_rows+=len(chunk); chunk=chunk.loc[chunk.scope.ne('main')]
                if chunk.empty: continue
                ids=chunk.sequence_index.to_numpy(int)
                for c in voluntary.SCORE_FIELDS:
                    if c in ('scope','cutoff','score'): continue
                    assert np.array_equal(chunk[c].to_numpy(),a[c].to_numpy()[ids]),('forecast_identity',c)
                assert np.isfinite(chunk.score).all() and forward[ids].all()
                for key,part in chunk.groupby(['scope','cutoff'],sort=False):
                    ii=part.sequence_index.to_numpy(int); which=key[0]=='main'
                    assert key in fitted and part.u_date.ge(key[1]).all()
                    assert (part.u_date.lt('2023-01-01') if key[1]=='2020-01-01' else part.u_date.le(END)).all()
                    if not which: assert part.family_id.map(family_group).eq(int(key[0][-1])).all()
                    if candidate:
                        assert not score_seen[which][ii].any(); score_seen[which][ii]=True
                        model,common_scaler,qs=fitted[key]; x=design(common[ii],q[ii],common_scaler,qs)
                        with threadpool_limits(limits=1): expected_score=x@np.asarray(model['coef'])+model['intercept']
                        near(part.score.to_numpy(),expected_score,rtol=1e-10,atol=1e-10)
                        max_score_error=max(max_score_error,float(np.abs(part.score.to_numpy()-expected_score).max()))
                        near(part.q_raw.to_numpy(),q[ii],rtol=0,atol=0); near(part.q_design.to_numpy(),x[:,52],rtol=1e-12,atol=1e-12)
                        assert np.array_equal(part.q_missing_diagnostic.to_numpy(),(~np.isfinite(q[ii])).astype(int))
                        assert part.arm.eq('CURVE53').all(); score_counts[key]+=len(part)
                for row in chunk.to_dict('records'): yield row
        select_checks=[]
        for candidate in (True,False):
            observed_scopes=[]
            for scope,stream in itertools.groupby(score_stream(candidate),key=lambda r:r['scope']):
                observed_scopes.append(scope); assert scope in (SCOPES if candidate else SCOPES[1:])
                parents=forward_m if scope=='main' else forward_m.loc[forward_m.family_id.map(family_group).eq(int(scope[-1]))]
                adapted=(dict(r,scope='main') for r in stream)
                result=voluntary.select_full_pool(parents.to_dict('records'),adapted,calendar,END,audit_sink=lambda row:None)
                role='choices_main' if scope=='main' else 'choices_holdout' if candidate else 'control_held_K'
                arm='CURVE53' if candidate else 'COMMON52'
                check_choice_rows(result['choices'],actual_choices[role],scope,arm)
                for epoch,b in result['boundaries'].items():
                    assert b==saved_bounds[epoch]
                    if candidate: bounds[epoch]=b
                reduced=[dict(sequence_index=r['sequence_index'],family_id=r['family_id'],u_index=r['u_index'],
                    u_date=r['u_date'],selected=r['selected'],chosen_action_id=r['chosen_action_id'],scope=scope) for r in result['choices']]
                if scope!='main': (held_new if candidate else held_old).extend(reduced)
                select_checks.append(dict(arm=arm,scope=scope,parent_rows=len(reduced),selected=sum(r['selected'] for r in reduced)))
                print(json.dumps(dict(phase='complete_K_selection_verified',arm=arm,scope=scope)),flush=True)
            assert observed_scopes==list(SCOPES if candidate else SCOPES[1:])
        assert sum(score_counts.values())==1933480 and old_rows==1933480
        assert all(np.array_equal(seen,forward) for seen in score_seen.values()) and bounds==saved_bounds
        for r in records: assert score_counts[(r['scope'],r['cutoff'])]==r['prediction_children']
        saved_held=bound_json(manifest['held_diagnostic']); days_saved=pd.read_csv(manifest['held_daily']['path'],float_precision='round_trip')
        held_checks={}
        for scope in SCOPES[1:]:
            computed,days=held_diagnostic([r for r in held_old if r['scope']==scope],[r for r in held_new if r['scope']==scope],a)
            saved=saved_held['groups'][scope]
            for key,val in computed.items():
                if key=='annual':
                    assert len(val)==len(saved[key])
                    for aa,bb in zip(val,saved[key]):
                        assert aa['year']==bb['year']
                        for k in aa:
                            if k!='year':
                                if aa[k] is None: assert bb[k] is None
                                else: near(aa[k],bb[k])
                elif isinstance(val,dict): assert val==saved[key]
                elif val is None: assert saved[key] is None
                else: near(val,saved[key])
            sd=days_saved.loc[days_saved.scope.eq(scope)].reset_index(drop=True)
            assert days.u_date.tolist()==sd.u_date.tolist()
            for c in ('delta_R','known_family_u','unknown_family_u'): near(days[c],sd[c])
            held_checks[scope]=computed
        assert all(stat(b)==before[k] for k,b in inherited.items())
        receipt=dict(schema='stage207_model_forecast_selection_review_v1',status='completed',core_blockers=0,
            manifest=auth['manifest'],authorization=auth,source_bundle=sources(),models_checkpoint=binding(output/'models_checkpoint.json'),
            model_checks=model_checks,prediction_rows=1933480,max_forward_score_abs_error=max_score_error,
            selection_checks=select_checks,held=held_checks,all_held_gates_pass=all(r['nominal_pass'] for r in held_checks.values()),
            counters=counts,inherited_source_stat_unchanged=True,cash_phase='pending_root_separate_authorization',
            cumulative_fit=427,cumulative_cash=226,elapsed_seconds=time.monotonic()-started,
            limitations=['COMMON52 block/weight computation inherited from accepted132','not strict release-vintage PIT',
                'q plus fixed imputation package, no numeric/missing causal isolation','held failures cannot be overridden by cash results'])
        write(output/'review_receipt.json',receipt)
        write(output/'terminal.json',dict(status='completed',exit_code=0,counters=counts,elapsed_seconds=time.monotonic()-started))
        print(json.dumps(dict(status='completed',core_blockers=0,max_forward_score_abs_error=max_score_error,
            held={k:{x:v[x] for x in ('known_u_equal_mean_increment_R','unknown_differential_selected_events','common_unresolved_same_action','nominal_pass')} for k,v in held_checks.items()},counters=counts)),flush=True)
    except BaseException as exc:
        write(output/'failure.json',dict(status='failed',error=str(exc),traceback=traceback.format_exc(),counters=counts,automatic_retry=False))
        raise

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--actual',required=True,action='store_true'); p.add_argument('--authorization',required=True)
    p.add_argument('--authorization-sha256',required=True); p.add_argument('--output',type=Path,default=OUTPUT); args=p.parse_args(argv)
    output=args.output.resolve(); assert output==OUTPUT and not output.exists()
    ab=binding(args.authorization); assert ab['sha256']==args.authorization_sha256; auth=bound_json(ab)
    assert binding(PROTOCOL)['sha256']==PROTOCOL_SHA and auth['source_bundle']==sources()
    assert auth['schema']=='stage207_exact_root_review_authorization_v1' and auth['authorized_by']=='root'
    assert auth['phase']=='model_forecast_selection' and auth['protocol_sha256']==PROTOCOL_SHA and auth['output']==str(output)
    assert auth['manifest']==dict(path=str(MANIFEST),bytes=43188,sha256=MANIFEST_SHA)
    actual(auth,output)

if __name__=='__main__': main()
