"""Independent237 K-target review. Actual data requires exact root authorization.

No estimator.fit, old forecast, old selection or account replay. Accepted218
normal equations are updated only by the exact target difference.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
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

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage237_K_target_protocol/protocol.json'
PROTOCOL_SHA='8aad5f5b6afefec4b078ba7a32f48b806119977156ade22da04eb4e433885c06'
OUTPUT=LINE/'outputs/stage239_K_target_review/actual_run2'
ACTUAL=LINE/'outputs/stage238_K_target_fit/actual_run1'
SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
CONTROLS=('DOMAIN52','COMMON52');CANDIDATE='K_TARGET52';END='2026-10-16';PHASE='after_all_source_close'
POTENTIAL={'closed_on_K_priority_reprice','closed_after_K','unknown_after_K','open_K_reached'}
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']


def require(condition,message):
    if not condition:raise ValueError(message)


def near(a,b,rtol=1e-10,atol=1e-10):
    np.testing.assert_allclose(a,b,rtol=rtol,atol=atol,equal_nan=True)


def family(value):return int(hashlib.sha256(str(value).encode()).hexdigest(),16)%2


def deployment(day):return CUTOFFS[0] if day<CUTOFFS[1] else CUTOFFS[1]


def target_arrays(frame):
    old=pd.to_numeric(frame.net_R_stress,errors='coerce').to_numpy(float)
    new=old.copy()
    use=frame.primary_domain.astype(int).eq(1)&frame.timing_state.isin(POTENTIAL)
    new[use.to_numpy()]=[float(t) if t else math.nan for t in frame.loc[use,'K_stress_net_R']]
    return old,new


def support_contract(T,primary,old_dates,new_dates,known,new_y,phases,support,cutoff):
    T=np.asarray(T,np.int64);mask=np.asarray(support['admissible_mask'])
    require(mask.dtype==bool and np.array_equal(support['sequence_index'],T),'original_ordered_T_mismatch')
    require(np.array_equal(mask,np.asarray(primary,dtype=bool)),'original_S_mask_mismatch')
    ow=np.asarray(support['old_weight']);nw=np.asarray(support['new_weight'])
    require(ow.shape==nw.shape==mask.shape==T.shape,'support_shape')
    require(np.isfinite(ow).all() and (ow>0).all() and np.equal(nw[~mask],0.).all(),'old_or_excluded_weight')
    w=nw[mask]
    require(mask.any() and np.isfinite(w).all() and (w>0).all(),'empty_or_invalid_allowed_weight')
    old_dates=np.asarray(old_dates,dtype=str);new_dates=np.asarray(new_dates,dtype=str)
    valid=np.asarray(known,dtype=bool)&np.isfinite(np.asarray(new_y,float))&(np.asarray(phases)==PHASE)
    valid &= (old_dates!='')&(old_dates<cutoff)&(new_dates!='')&(new_dates<=old_dates)
    require(valid[mask].all(),'common_C_not_exact_S')
    return T[mask],w.copy()


def policy_value(action_id,labels,end=END):
    if not action_id:return 0.
    require(action_id in labels,'selected_label_missing')
    r=labels[action_id];require(int(r['primary_domain'])==1,'selected_nonprimary_label')
    if int(r['policy_reward_known'])==1:
        require(r.get('policy_known_phase')==PHASE,'policy_zero_phase')
        return 0. if r.get('policy_known_date','') and r['policy_known_date']<=end else None
    if int(r['K_stress_known'])==1:
        require(r.get('K_stress_known_phase')==PHASE,'K_target_phase')
        v=float(r['K_stress_net_R'])
        return v if math.isfinite(v) and r.get('K_stress_known_date','') and r['K_stress_known_date']<=end else None
    return None


def contrast(candidate,control,labels,end=END):
    a,b=policy_value(candidate,labels,end),policy_value(control,labels,end)
    if candidate==control:return 0.,False,bool(candidate and a is None)
    if a is None or b is None:return None,True,False
    return a-b,False,False


def held_cells(events):
    groups={};daily=[]
    for control in CONTROLS:
        groups[control]={}
        for scope in SCOPES[1:]:
            for cut in CUTOFFS:
                e=[r for r in events if r['control']==control and r['scope']==scope and deployment(r['u_date'])==cut]
                days=[];by_day=defaultdict(list)
                for row in e:by_day[row['u_date']].append(row)
                for day,rows in sorted(by_day.items()):
                    values=[float(r['delta_R']) for r in rows if r['delta_R'] is not None]
                    d=dict(control=control,scope=scope,cutoff=cut,u_date=day,
                        delta_R=float(math.fsum(values)/len(values)) if values else None,
                        known_family_u=len(values),unknown_family_u=sum(r['unknown'] for r in rows),
                        same_unresolved=sum(r['same_unresolved'] for r in rows))
                    days.append(d);daily.append(d)
                values=[d['delta_R'] for d in days if d['delta_R'] is not None]
                mean=float(math.fsum(values)/len(values)) if values else None
                unknown=sum(r['unknown'] for r in e)
                cell=dict(known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=unknown,
                    common_unresolved_same_action=sum(r['same_unresolved'] for r in e),full_family_u=len(e),
                    known_increment_family_u=sum(r['delta_R'] is not None for r in e),known_source_days=len(values),
                    selected_by_arm={control:sum(r['control_selected'] for r in e),CANDIDATE:sum(r['candidate_selected'] for r in e)},
                    nominal_pass=bool(mean is not None and math.isfinite(mean) and mean>0 and unknown==0 and values))
                groups[control][scope+'/'+cut]=cell
    return dict(groups=groups,all_eight_pass=all(c['nominal_pass'] for g in groups.values() for c in g.values()),
                target='strict K stress narrow_R'),pd.DataFrame(daily)


def delta_equations(H,rhs,x,w,old,new):
    z=np.column_stack((x,np.ones(len(x))))
    with threadpool_limits(limits=1):delta=z.T@(np.asarray(w)*(np.asarray(new)-np.asarray(old)))
    return np.asarray(H).copy(),np.asarray(rhs)+delta


def verify_solution(H,rhs,beta):
    near(H@beta,rhs,rtol=1e-8,atol=1e-7)
    with threadpool_limits(limits=1):solved=np.linalg.solve(H,rhs)
    near(beta,solved,rtol=1e-8,atol=1e-7)
    return float(np.max(np.abs(H@beta-rhs))),float(np.max(np.abs(beta-solved)))


def load(name):
    spec=importlib.util.spec_from_file_location('review239_'+name,TOOLS/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bound(b):
    raw=Path(b['path']).read_bytes()
    require(len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],'bound_input_changed '+b['path'])
    return raw


def small(b):
    require(b['bytes']<2000000,'not_a_small_JSON');return json.loads(bound(b))


def stat(b):
    s=Path(b['path']).stat();require(s.st_size==b['bytes'],'inherited_size_changed')
    return dict(path=b['path'],bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,inherited_sha256=b['sha256'],rehashed=False)


def sources():
    return sorted([binding(TOOLS/n) for n in ('stage239_K_target_review.py','test_stage239_K_target_review.py',
        'stage220_training_domain_model_review.py','stage156_voluntary_choices.py')],key=lambda b:b['path'])


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def compare(expected,actual,path='report'):
    if isinstance(expected,dict):
        for k,v in expected.items():require(k in actual,'missing '+path+'/'+k);compare(v,actual[k],path+'/'+k)
    elif isinstance(expected,list):
        require(len(expected)==len(actual),'list_length '+path)
        for i,(a,b) in enumerate(zip(expected,actual)):compare(a,b,path+'/'+str(i))
    elif isinstance(expected,float):near(expected,actual)
    else:require(expected==actual,'value_mismatch '+path+' '+repr((expected,actual)))


class HashReader(io.RawIOBase):
    def __init__(self,source):self.source=source;self.digest=hashlib.sha256()
    def readable(self):return True
    def readinto(self,buf):
        n=self.source.readinto(buf)
        if n:self.digest.update(memoryview(buf)[:n])
        return n


def new_csv_chunks(b,chunksize=65536):
    with Path(b['path']).open('rb') as source:
        hashed=HashReader(source)
        with io.BufferedReader(hashed) as stream:
            with gzip.GzipFile(fileobj=stream) as compressed:
                for chunk in pd.read_csv(compressed,dtype=str,keep_default_na=False,chunksize=chunksize,float_precision='round_trip'):
                    yield chunk
            while stream.read(1024*1024):pass
        require(hashed.digest.hexdigest()==b['sha256'] and Path(b['path']).stat().st_size==b['bytes'],'new_CSV_binding_changed')


def new_csv(b):return pd.concat(list(new_csv_chunks(b)),ignore_index=True)


def producer_sources(protocol):
    return sorted([binding(TOOLS/n) for n in protocol['source_allowlist']],key=lambda b:b['path'])


def control_completed(name,manifest,review,manifest_binding,terminal=None):
    if name=='COMMON52_main':
        return bool(manifest.get('schema')=='stage156_voluntary_choices_manifest_v1' and
            review.get('schema')=='stage158_voluntary_independent_review_v1' and review.get('completed') is True and
            all(review.get(k)==0 for k in ('C','I','M')) and review.get('research_arithmetic_accepted') is True and
            review.get('inputs',{}).get('choice_manifest')==manifest_binding and
            terminal is not None and terminal.get('schema')=='stage156_terminal_v1' and
            terminal.get('status')=='completed' and terminal.get('exit_code')==0)
    return manifest['status']=='completed' and review['status']=='completed'


def guard(protocol,pb,manifest,mb):
    require(manifest['status']=='completed' and manifest['protocol_sha256']==PROTOCOL_SHA,'producer_not_completed237')
    require(manifest['protocol']==pb and manifest['input_bindings']==protocol['input_bindings'],'producer_input_or_protocol')
    bundle=producer_sources(protocol)
    require(manifest['source_bundle']==bundle,'producer_source_changed')
    auth=small(manifest['authorization'])
    required=dict(schema=protocol['authorization_schema'],authorized_by='root',stage='fit',exact_source_authorized=True,
        protocol_sha256=PROTOCOL_SHA,output=str(ACTUAL),source_bundle=bundle,input_bindings=protocol['input_bindings'],
        controls=protocol['controls'],folds=protocol['folds'])
    compare(required,auth,'producer_authorization')
    require(manifest['controls']==protocol['controls'] and manifest['folds']==protocol['folds'],'producer_control_or_fold_identity')
    for b in protocol['existing_small_source_bindings']:bound(b)
    terminal=small(manifest['terminal']);summary=small(manifest['summary']);preflight=small(manifest['preflight'])
    require(terminal['status']=='completed' and terminal['exit_code']==0 and terminal['automatic_retry'] is False,'producer_terminal')
    require(manifest['counters']==terminal['counters']==summary['counters'],'producer_counter_chain')
    c=manifest['counters']
    require(c['fit_calls_attempted']==c['fit_calls_completed'] and c['fit_calls_completed'] in (0,6),'producer_fit_count')
    require(manifest['new_cash']==0 and summary['new_cash']==0,'unexpected_cash')
    for key in ('old_fit','old_prediction','old_selection','old_cash','new_cash','SQL','old130_training_csv',
                'original_actions_reads','native_cache_reads','download','old_large_hash'):
        require(c[key]==0,'forbidden_producer_operation '+key)
    for key,value in [('labels_K_csv',1),('mothers_csv',1),('COMMON_npz',1),('calendar',1),('support_npz',6),('old_scaler_small_json',6)]:
        require(c[key]==value,'producer_read_budget '+key)
    require(len(preflight['cells'])==6 and preflight['all_six_before_any_fit'],'producer_preflight_order')
    require(c['fit_calls_completed']==(6 if preflight['ready'] else 0),'preflight_vs_fit_count')
    for key,value in [('control_choice_csv',4),('prediction_calls_attempted',6),('prediction_calls_completed',6),
                      ('prediction_model_rows',1933480),('candidate_selection_calls',3)]:
        require(c[key]==(value if preflight['ready'] else 0),'producer_forward_budget '+key)
    started=small(manifest['artifacts']['started.json'])
    compare(dict(protocol=pb,authorization=manifest['authorization'],source_bundle=bundle),started,'producer_started')
    reads=small(manifest['source_read_receipt'])
    require(reads['before']==reads['after'] and reads['counters']==c,'producer_inherited_stat_changed')
    expected_bindings={k:protocol['input_bindings'][k] for k in ('labels_K','mothers','common')}
    for f in protocol['folds']:expected_bindings['support/'+f['scope']+'/'+f['cutoff']]=f['support']
    for control,parts in protocol['controls'].items():
        for role,b in parts.items():expected_bindings[control+'/'+role]=b
    require(reads['bindings']==expected_bindings and set(reads['before'])==set(expected_bindings),'producer_read_binding_population')
    for role,b in reads['bindings'].items():
        r=reads['before'][role]
        require(r['bytes']==b['bytes'] and r['inherited_sha256']==b['sha256'] and r['rehashed'] is False,'producer_read_identity')
    inputs=protocol['input_bindings'];measurement=small(inputs['measurement_manifest']);review=small(inputs['measurement_review'])
    require(measurement['status']=='completed' and review['status']=='completed','K_measurement_not_accepted')
    require(measurement['artifacts']['labels_K.csv.gz']==inputs['labels_K'] and review['actual_manifest']==inputs['measurement_manifest'],
            'K_measurement_binding')
    require(review['core_findings']==dict(P0=0,P1=0,P2=0),'K_measurement_core_findings')
    records=small(inputs['domain_fit_records']);old={(r['scope'],r['cutoff']):r for r in records}
    domain=small(inputs['domain_fit_manifest']);domain_review=small(inputs['domain_model_review'])
    require(domain['status']=='completed' and domain['fit_records']==inputs['domain_fit_records'] and
            domain_review['core_blockers']==0 and domain_review['manifest']==inputs['domain_fit_manifest'],'DOMAIN_control_lineage')
    for f in protocol['folds']:
        r=old[(f['scope'],f['cutoff'])]
        for a,b in [('support','training_domain_support'),('original_common_scaler','common_scaler'),
                    ('control_normal_equations','normal_equations'),('control_portable_model','portable_model')]:
            require(f[a]==r[b],'fold_control_binding '+a)
    for name,lineage in protocol['control_lineage'].items():
        cm=small(lineage['manifest']);cr=small(lineage['review'])
        terminal=small(cm['artifacts']['terminal']) if name=='COMMON52_main' else None
        require(control_completed(name,cm,cr,lineage['manifest'],terminal),'control_not_completed '+name)
    require(domain['choices_main']==protocol['controls']['DOMAIN52']['main'] and
            domain['choices_holdout']==protocol['controls']['DOMAIN52']['held'],'DOMAIN_choice_binding')
    common=small(inputs['control_choice_manifest']);held=small(inputs['control_held_K_manifest'])
    require(common['artifacts']['choices_main']==protocol['controls']['COMMON52']['main'] and
            held['control_held_K']==protocol['controls']['COMMON52']['held'],'COMMON_choice_binding')
    return preflight


def read_inputs(protocol,counts):
    inputs=protocol['input_bindings']
    inherited={k:inputs[k] for k in ('labels_K','mothers','common')}
    for f in protocol['folds']:inherited['support/'+f['scope']+'/'+f['cutoff']]=f['support']
    for control,parts in protocol['controls'].items():
        for role,b in parts.items():inherited[control+'/'+role]=b
    before={k:stat(b) for k,b in inherited.items()}
    counts['labels_reads']+=1
    a=pd.read_csv(inputs['labels_K']['path'],usecols=protocol['labels_usecols'],dtype=str,keep_default_na=False,float_precision='round_trip')
    old,new=target_arrays(a)
    copy=a.primary_domain.eq('1')&a.timing_state.eq('closed_before_K')
    require(a.loc[copy,'net_R_stress'].equals(a.loc[copy,'K_stress_net_R']),'copied_target_token_mismatch')
    for k in ('sequence_index','mother_sequence_index','u_index','u_action_eligible','trade_label_known','primary_domain','policy_reward_known','K_stress_known'):
        a[k]=a[k].astype(np.int64)
    for k in ('entry_index','exit_index'):a[k]=pd.to_numeric(a[k],errors='coerce')
    a['net_R_stress']=old;a['candidate_y']=new
    a['event_id']=a.action_id;a['action_sequence_index']=a.sequence_index;a['actual_epoch']=a.reference_epoch
    require(len(a)==protocol['expected']['actions'] and np.array_equal(a.sequence_index,np.arange(len(a))) and a.action_id.is_unique,'full_action_identity')
    counts['mother_reads']+=1
    m=pd.read_csv(inputs['mothers']['path'],usecols=protocol['mothers_usecols'],dtype=str,keep_default_na=False)
    for k in ('sequence_index','u_index'):m[k]=m[k].astype(np.int64)
    require(len(m)==protocol['expected']['mothers'] and np.array_equal(m.sequence_index,np.arange(len(m))) and m.event_id.is_unique,'full_mother_identity')
    pi=a.mother_sequence_index.to_numpy(np.int64)
    require((pi>=0).all() and (pi<len(m)).all(),'parent_outside_domain')
    for left,right in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),('u_date','u_date'),('u_index','u_index'),('anchor_epoch','reference_epoch')]:
        require(np.array_equal(a[left].to_numpy(),m[right].to_numpy()[pi]),'parent_child_identity '+left)
    counts['common_reads']+=1
    with np.load(inputs['common']['path'],allow_pickle=False) as z:raw=z['common'].astype(float);columns=z['columns'].tolist()
    require(raw.shape==(len(a),26),'COMMON_shape')
    counts['calendar_reads']+=1;arr=np.load(io.BytesIO(bound(inputs['calendar'])),allow_pickle=False)
    calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in arr]
        if arr.dtype.kind in 'iu' else arr.astype('datetime64[D]').astype(str).tolist())
    require(len(calendar)==5587 and calendar==sorted(set(calendar)),'calendar_identity')
    require(np.array_equal(np.asarray(calendar)[a.u_index.to_numpy()],a.u_date.to_numpy()),'action_calendar')
    return a,m,raw,columns,calendar,inherited,before


def prepare(protocol,a,raw,columns,calendar,counts,math_helper):
    plans=[];cells=[];family_group=a.family_id.map({f:family(f) for f in a.family_id.unique()})
    for f in protocol['folds']:
        scope,cut=f['scope'],f['cutoff']
        use=a.u_action_eligible.eq(1)&a.label_state.eq('closed_complete_bar_model')&a.u_date.lt(cut)&a.label_known_date.ne('')&a.label_known_date.lt(cut)&np.isfinite(a.net_R_stress)
        if scope!='main':use &= family_group.ne(int(scope[-1]))
        T=np.flatnonzero(use.to_numpy());counts['support_reads']+=1
        with np.load(f['support']['path'],allow_pickle=False) as z:support={k:z[k] for k in f['support_keys']}
        scaler=small(f['original_common_scaler']);counts['scaler_reads']+=1
        require(scaler['scope']==scope and scaler['cutoff']==cut and scaler['common']['columns']==columns and len(scaler['feature_names'])==52,'scaler_identity')
        mask=np.asarray(support['admissible_mask']);require(len(T)==f['original_T_rows'],'original_T_row_count')
        ti=T[mask] if mask.shape==T.shape else np.array([],dtype=np.int64)
        cell=dict(scope=scope,cutoff=cut,original_T_rows=len(T),retained_S_rows=len(ti),C_rows=0,
            target_changed_rows=0,ready=False,training_domain_support=f['support'],common_scaler=f['original_common_scaler'])
        if mask.shape==T.shape:
            valid=(a.K_stress_known.to_numpy()[ti]==1)&np.isfinite(a.candidate_y.to_numpy()[ti])
            valid &= (a.label_known_phase.to_numpy()[ti]==PHASE)&(a.K_stress_known_phase.to_numpy()[ti]==PHASE)
            valid &= (a.K_stress_known_date.to_numpy()[ti]!='')&(a.K_stress_known_date.to_numpy()[ti]<=a.label_known_date.to_numpy()[ti])
            cell.update(C_rows=int(valid.sum()),target_changed_rows=int(np.count_nonzero(a.candidate_y.to_numpy()[ti]!=a.net_R_stress.to_numpy()[ti])))
        try:
            ids,w=support_contract(T,a.primary_domain.to_numpy()[T],a.label_known_date.to_numpy()[T],
                a.K_stress_known_date.to_numpy()[T],(a.K_stress_known.to_numpy()[T]==1)&(a.label_known_phase.to_numpy()[T]==PHASE),a.candidate_y.to_numpy()[T],
                a.K_stress_known_phase.to_numpy()[T],support,cut)
            require(len(ids)==f['retained_S_rows'],'retained_S_count')
            independent=math_helper.training_mask(a.u_index.to_numpy()[T],a.reference_epoch.to_numpy()[T],calendar)
            require(np.array_equal(independent,mask),'independent_S_calendar_mask')
            require(abs(math.fsum(w)-f['reference_domain']['candidate_weight_mass'])<=8*math.ulp(f['reference_domain']['candidate_weight_mass']),'exact_weight_mass')
            for start in range(0,len(ids),65536):math_helper.design(raw[ids[start:start+65536]],scaler)
            changed=a.candidate_y.to_numpy()[ids]!=a.net_R_stress.to_numpy()[ids]
            cell.update(C_rows=len(ids),target_changed_rows=int(changed.sum()),ready=True)
            plans.append(dict(fold=f,ti=ids,w=w,scaler=scaler,changed=changed,cell=cell))
        except ValueError as exc:
            cell['reason']=str(exc)
        cells.append(cell)
    require(len(cells)==6 and {(c['scope'],c['cutoff']) for c in cells}=={(s,c) for s in SCOPES for c in CUTOFFS},'six_unique_folds')
    return plans,cells


def check_models(protocol,manifest,a,raw,plans,counts,math_helper):
    records=small(manifest['fit_records']);record_map={(r['scope'],r['cutoff']):r for r in records}
    require(len(records)==6 and len(record_map)==6,'six_new_models');models={};checks=[]
    for plan in plans:
        f=plan['fold'];key=(f['scope'],f['cutoff']);r=record_map[key];ids=plan['ti'];w=plan['w'];scaler=plan['scaler']
        require(r['scaler']==f['original_common_scaler'] and r['weight_source']==f['support'],'new_scaling_or_weight_source')
        model=small(r['portable_model'])
        require(model['scope']==key[0] and model['cutoff']==key[1] and model['arm']==CANDIDATE and
            model['feature_names']==scaler['feature_names'] and model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky'),'portable_model_identity')
        beta=np.r_[np.asarray(model['coef'],float),float(model['intercept'])]
        require(beta.shape==(53,) and np.isfinite(beta).all(),'model_coefficient_shape')
        with np.load(io.BytesIO(bound(f['control_normal_equations'])),allow_pickle=False) as z:H0=z['lhs'];rhs0=z['rhs']
        counts['old_equation_reads']+=1;changed=plan['changed'];ii=ids[changed]
        x=math_helper.design(raw[ii],scaler)
        H,rhs=delta_equations(H0,rhs0,x,w[changed],a.net_R_stress.to_numpy()[ii],a.candidate_y.to_numpy()[ii])
        with np.load(io.BytesIO(bound(r['normal_equations'])),allow_pickle=False) as z:
            near(H,z['lhs'],rtol=1e-10,atol=1e-7);near(rhs,z['rhs'],rtol=1e-10,atol=1e-7)
            near(beta,z['coefficient_with_intercept'],rtol=0,atol=0);near(z['weight_sum'],math.fsum(w),rtol=0,atol=0)
        residual,coefficient_error=verify_solution(H,rhs,beta)
        models[key]=(model,scaler)
        checks.append(dict(scope=key[0],cutoff=key[1],retained_S_rows=len(ids),target_changed_rows=len(ii),
            max_normal_residual=residual,max_independent_solve_coefficient_error=coefficient_error))
        print(json.dumps(dict(phase='new_target_model_verified',scope=key[0],cutoff=key[1])),flush=True)
    return models,checks


def cast_choices(frame):
    for key in ('sequence_index','u_index','chosen_action_sequence_index','selected'):frame[key]=frame[key].astype(np.int64)
    return frame


def validate_choices(frame,a,m,kind):
    f=cast_choices(frame).sort_values('sequence_index',kind='stable').reset_index(drop=True)
    wanted=m.loc[m.u_date.ge(CUTOFFS[0])].sort_values('sequence_index',kind='stable')
    require(len(f)==161014 and f.event_id.is_unique,'full_choice_population')
    for key in IDENTITY:require(np.array_equal(f[key].to_numpy(),wanted[key].to_numpy()),'choice_identity '+key)
    require(f.anchor_epoch.eq(f.reference_epoch).all() and f.selected.isin([0,1]).all(),'choice_anchor_or_flag')
    require(np.array_equal(f.cutoff.to_numpy(),np.where(f.u_date.lt(CUTOFFS[1]),CUTOFFS[0],CUTOFFS[1])),'choice_deployment')
    scope=np.repeat('main',len(f)) if kind=='main' else f.family_id.map(lambda x:'holdout_'+str(family(x))).to_numpy()
    require(np.array_equal(f.scope.to_numpy(),scope),'choice_family_scope')
    chosen=f.loc[f.selected.eq(1)];ids=chosen.chosen_action_sequence_index.to_numpy(np.int64)
    require((ids>=0).all() and (ids<len(a)).all(),'chosen_index')
    for l,r in [('chosen_action_id','action_id'),('chosen_epoch','reference_epoch'),('event_id','mother_event_id'),
                ('product_id','product_id'),('u_index','u_index')]:
        require(np.array_equal(chosen[l].to_numpy(),a.iloc[ids][r].to_numpy()),'chosen_source_identity '+l)
    require(a.iloc[ids].primary_domain.eq(1).all() and f.loc[f.selected.eq(0),'chosen_action_id'].eq('').all(),'selected_nonprimary_or_unselected_nonempty')
    require(not chosen.duplicated(['family_id','u_index']).any(),'multiple_selected_family_u')
    return f


def main_identity(candidate,control):
    action=['chosen_action_id','chosen_action_sequence_index','chosen_epoch','selected']
    fields=IDENTITY+['anchor_epoch']+action;different={};changed=np.zeros(len(candidate),bool)
    for key in fields:
        d=candidate[key].to_numpy()!=control[key].to_numpy();different[key]=int(d.sum())
        if key in IDENTITY+['anchor_epoch']:require(not d.any(),'main_control_identity '+key)
        changed |= d
    return dict(full_parent_rows=len(candidate),compared_fields=fields,differences_by_field=different,
        changed_parent_rows=int(changed.sum()),identical_actions=not bool(changed.any()),cash_eligible=bool(changed.any()),
        score_magnitude_used_for_sizing_or_priority=False)


def compare_choices(expected,actual,scope):
    f=actual.loc[actual.scope.eq(scope)].sort_values('sequence_index',kind='stable').reset_index(drop=True)
    e=pd.DataFrame(expected).sort_values('sequence_index',kind='stable').reset_index(drop=True)
    require(len(e)==len(f),'new_selection_domain')
    numeric={'sequence_index','u_index','chosen_action_sequence_index','selected'}
    for key in IDENTITY+['anchor_epoch','chosen_action_id','chosen_action_sequence_index','chosen_epoch','selected',
                         'proposed_action_id','proposed_epoch','selection_state','cutoff']:
        left=f[key].astype(np.int64).to_numpy() if key in numeric else f[key].to_numpy()
        right=e[key].astype(np.int64).to_numpy() if key in numeric else e[key].to_numpy()
        require(np.array_equal(left,right),'new_selection_mismatch '+scope+'/'+key)
    for key in ('score','proposed_score'):
        near(pd.to_numeric(f[key],errors='coerce').to_numpy(),pd.to_numeric(e[key],errors='coerce').to_numpy())


def family_choices(frame):
    require(not frame.loc[frame.selected.eq(1)].duplicated(['family_id','u_index']).any(),'multiple_family_actions')
    part=frame.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index'])
    return {(r['family_id'],int(r['u_index'])):r for r in part.to_dict('records')}


def held_events(candidate,controls,a):
    needed=set(candidate.loc[candidate.selected.eq(1),'chosen_action_sequence_index'].astype(int))
    for parts in controls.values():needed.update(parts['held'].loc[parts['held'].selected.eq(1),'chosen_action_sequence_index'].astype(int))
    lookup={r['action_id']:r for r in a.iloc[sorted(needed)].to_dict('records')}
    active=family_choices(candidate);events=[]
    for name,parts in controls.items():
        base=family_choices(parts['held']);require(active.keys()==base.keys(),'held_family_u_population')
        for key,r in active.items():
            b=base[key];require(r['u_date']==b['u_date'] and r['scope']==b['scope'],'held_identity')
            delta,unknown,same=contrast(r['chosen_action_id'],b['chosen_action_id'],lookup)
            events.append(dict(control=name,scope=r['scope'],u_date=r['u_date'],family_id=key[0],delta_R=delta,
                unknown=unknown,same_unresolved=same,candidate_selected=int(r['selected']),control_selected=int(b['selected'])))
    return events


def verify_forward(protocol,manifest,a,m,raw,calendar,models,counts,math_helper,selector):
    choices={}
    for role,kind in [('choices_main','main'),('choices_holdout','held')]:
        counts['new_choice_reads']+=1;choices[kind]=validate_choices(new_csv(manifest[role]),a,m,kind)
    controls={}
    for name,parts in protocol['controls'].items():
        controls[name]={}
        for kind,b in parts.items():
            counts['old_choice_reads']+=1
            frame=pd.read_csv(b['path'],usecols=protocol['control_choices_usecols'],dtype=str,keep_default_na=False)
            controls[name][kind]=validate_choices(frame,a,m,kind)
    forward=a.u_date.ge(CUTOFFS[0]).to_numpy();seen={True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)}
    score_counts=Counter();max_error=0.;bounds={};selections=[]
    def stream():
        nonlocal max_error
        counts['new_score_reads']+=1
        for chunk in new_csv_chunks(manifest['child_scores']):
            for key in ('sequence_index','mother_sequence_index','u_index','u_action_eligible'):chunk[key]=chunk[key].astype(np.int64)
            chunk['score']=chunk.score.astype(float);ids=chunk.sequence_index.to_numpy(np.int64)
            require((ids>=0).all() and (ids<len(a)).all() and forward[ids].all(),'new_prediction_outside_forward_domain')
            for key in selector.SCORE_FIELDS:
                if key not in ('scope','cutoff','score'):require(np.array_equal(chunk[key].to_numpy(),a[key].to_numpy()[ids]),'new_score_identity '+key)
            require(chunk.arm.eq(CANDIDATE).all() and np.isfinite(chunk.score).all(),'new_score_arm_finite')
            for key,part in chunk.groupby(['scope','cutoff'],sort=False):
                ii=part.sequence_index.to_numpy(np.int64);main=key[0]=='main'
                require(key in models and not seen[main][ii].any() and len(np.unique(ii))==len(ii),'duplicate_or_invalid_model_prediction')
                require(part.u_date.ge(key[1]).all() and (part.u_date.lt(CUTOFFS[1]) if key[1]==CUTOFFS[0] else part.u_date.le(END)).all(),'prediction_deployment_interval')
                if not main:require(part.family_id.map(family).eq(int(key[0][-1])).all(),'held_prediction_family')
                model,scaler=models[key]
                with threadpool_limits(limits=1):expected=math_helper.design(raw[ii],scaler)@np.asarray(model['coef'])+model['intercept']
                near(part.score.to_numpy(),expected)
                max_error=max(max_error,float(np.max(np.abs(part.score.to_numpy()-expected))));seen[main][ii]=True;score_counts[key]+=len(part)
            yield from chunk.to_dict('records')
    for scope,rows in itertools.groupby(stream(),key=lambda r:r['scope']):
        require(scope in SCOPES and scope not in {r['scope'] for r in selections},'noncontiguous_or_duplicate_scope')
        parents=m.loc[m.u_date.ge(CUTOFFS[0])]
        if scope!='main':parents=parents.loc[parents.family_id.map(family).eq(int(scope[-1]))]
        result=selector.select_full_pool(parents.to_dict('records'),(dict(r,scope='main') for r in rows),calendar,END,audit_sink=lambda _:None)
        compare_choices(result['choices'],choices['main' if scope=='main' else 'held'],scope)
        for epoch,b in result['boundaries'].items():
            require(epoch not in bounds or bounds[epoch]==b,'selection_K_boundary_disagrees');bounds[epoch]=b
        selections.append(dict(scope=scope,parent_rows=len(result['choices']),selected=sum(r['selected'] for r in result['choices'])))
    require(sum(score_counts.values())==1933480 and all(np.array_equal(s,forward) for s in seen.values()) and len(selections)==3,'complete_new_forward_support')
    for f in protocol['folds']:require(score_counts[(f['scope'],f['cutoff'])]==f['prediction_children'],'fold_forward_count')
    saved_bounds=small(manifest['boundaries']);compare(bounds,saved_bounds['epochs'],'boundaries')
    identities={name:main_identity(choices['main'],parts['main']) for name,parts in controls.items()}
    saved=small(manifest['selection_identity']);compare(identities,saved,'both_main_identities')
    diagnostic,daily=held_cells(held_events(choices['held'],controls,a))
    saved_held=small(manifest['held_diagnostic']);compare(diagnostic,saved_held,'held')
    counts['new_held_daily_reads']+=1;actual_daily=new_csv(manifest['held_daily'])
    sort=['control','scope','cutoff','u_date'];daily=daily.sort_values(sort).reset_index(drop=True);actual_daily=actual_daily.sort_values(sort).reset_index(drop=True)
    require(len(daily)==len(actual_daily),'held_daily_population')
    for key in sort:require(daily[key].tolist()==actual_daily[key].tolist(),'held_daily_identity '+key)
    for key in ('delta_R','known_family_u','unknown_family_u','same_unresolved'):
        near(pd.to_numeric(daily[key],errors='coerce').to_numpy(float),pd.to_numeric(actual_daily[key],errors='coerce').to_numpy(float))
    changed=all(not r['identical_actions'] for r in identities.values());eligible=bool(changed and diagnostic['all_eight_pass'])
    gate=dict(all_eight_held_pass=diagnostic['all_eight_pass'],main_differs_from_both=changed,cash_eligible=eligible,
              new_cash=0,automatic_cash_authorized=False)
    compare(gate,small(manifest['continuation_gate']),'continuation_gate')
    require(manifest['cash_eligible']==eligible,'manifest_cash_eligibility')
    return dict(new_prediction_rows=sum(score_counts.values()),max_forward_abs_error=max_error,selection_checks=selections,
        main_identities=identities,held=diagnostic,continuation_gate=gate)


def actual(auth,output):
    started=time.monotonic();output.mkdir(parents=True,exist_ok=False)
    counts=dict(fit=0,cash=0,SQL=0,old_fit=0,old_prediction=0,old_selection=0,old_cash=0,original_actions_reads=0,
        labels_reads=0,mother_reads=0,common_reads=0,calendar_reads=0,support_reads=0,scaler_reads=0,
        old_equation_reads=0,new_score_reads=0,new_choice_reads=0,old_choice_reads=0,new_held_daily_reads=0)
    write(output/'started.json',dict(status='started',authorization=auth,source_bundle=sources(),automatic_retry=False))
    try:
        pb=binding(PROTOCOL);require(pb['sha256']==PROTOCOL_SHA,'frozen237_changed');protocol=small(pb)
        manifest=small(auth['actual_manifest']);preflight=guard(protocol,pb,manifest,auth['actual_manifest'])
        math_helper=load('stage220_training_domain_model_review');selector=load('stage156_voluntary_choices')
        a,m,raw,columns,calendar,inherited,before=read_inputs(protocol,counts)
        plans,cells=prepare(protocol,a,raw,columns,calendar,counts,math_helper)
        saved={(r['scope'],r['cutoff']):r for r in preflight['cells']}
        require(len(saved)==6,'six_preflight_cells')
        for cell in cells:compare({k:v for k,v in cell.items() if k!='reason'},saved[(cell['scope'],cell['cutoff'])],'same_C_preflight')
        ready=all(c['ready'] for c in cells);require(preflight['ready']==ready,'preflight_ready_mismatch')
        report=dict(schema='stage239_K_target_independent_review_v1',status='completed',core_blockers=0,
            protocol=pb,actual_manifest=auth['actual_manifest'],source_bundle=sources(),same_C_cells=cells,
            independent_estimator_fit_calls=0,increased_betting_qualified=False,goal_complete=False,production_qualified=False,
            alpha_qualified=False,interpretation='historical fixed target-only arithmetic, not unseen or execution qualification')
        if ready:
            models,checks=check_models(protocol,manifest,a,raw,plans,counts,math_helper)
            report['math_checks']=checks
            report.update(verify_forward(protocol,manifest,a,m,raw,calendar,models,counts,math_helper,selector))
        else:
            require(manifest['actual_fit_calls_completed']==0 and manifest['cash_eligible'] is False,'zero_fit_stop_not_respected')
            report.update(new_prediction_rows=0,continuation_gate=dict(cash_eligible=False,new_cash=0),reason='same_C_failed_zero_fit')
        after={k:stat(b) for k,b in inherited.items()};require(before==after,'inherited_input_changed_during_review')
        report.update(counters=counts,inherited_stat_before=before,inherited_stat_after=after,elapsed_seconds=time.monotonic()-started)
        write(output/'receipt.json',report);write(output/'terminal.json',dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-started,counters=counts))
        write(output/'manifest.json',dict(schema='stage239_K_target_review_manifest_v1',status='completed',protocol=pb,
            actual_manifest=auth['actual_manifest'],artifacts={n:binding(output/n) for n in ('started.json','receipt.json','terminal.json')}))
        print(json.dumps(dict(status='completed',core_blockers=0,new_prediction_rows=report['new_prediction_rows'],
            continuation_gate=report['continuation_gate'],fit=0,cash=0)),flush=True)
    except Exception as exc:
        write(output/'terminal.json',dict(status='failed',exit_code=1,error_type=type(exc).__name__,error=str(exc),
            traceback=traceback.format_exc(),counters=counts,automatic_retry=False,elapsed_seconds=time.monotonic()-started));raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--actual',action='store_true',required=True)
    parser.add_argument('--authorization',required=True);parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--output',type=Path,default=OUTPUT);args=parser.parse_args(argv)
    require(args.output.resolve()==OUTPUT and not OUTPUT.exists(),'fresh_exact_review_output_required')
    ab=binding(args.authorization);require(ab['sha256']==args.authorization_sha256,'review_authorization_SHA')
    auth=small(ab);required=dict(schema='stage237_exact_root_review_authorization_v1',authorized_by='root',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(OUTPUT),source_bundle=sources())
    compare(required,auth,'root_review_authorization')
    require(auth['actual_manifest']==binding(ACTUAL/'manifest.json'),'exact_actual_manifest_binding')
    actual(auth,OUTPUT)


if __name__=='__main__':main()
