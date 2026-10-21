"""Root-authorized new DOMAIN52 math/forecast/selection review; never fits.

Old COMMON normal equations are inherited; only excluded-domain contributions
are recomputed. A completed model-phase checkpoint is never replayed for cash.
"""
from __future__ import annotations
import argparse
import bisect
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
PROTOCOL=LINE/'outputs/stage217_training_domain_loss_protocol/protocol.json'
PROTOCOL_SHA='b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53'
OUTPUT=LINE/'outputs/stage220_training_domain_loss_review/model_forecast_selection1'
SCOPES=('main','holdout_0','holdout_1'); CUTOFFS=('2020-01-01','2023-01-01'); END='2026-10-16'
FIELDS=['sequence_index','event_id','action_sequence_index','action_id','mother_sequence_index','mother_event_id',
 'product_id','family_id','u_date','u_index','reference_epoch','actual_epoch','anchor_epoch','u_action_eligible',
 'entry_index','exit_index','label_known_date','label_state','net_R_stress','participation_state']
NUMERIC=['sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_index','exit_index','net_R_stress']
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']

def load(name):
    spec=importlib.util.spec_from_file_location('review220_'+name,TOOLS/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def small(b):
    assert b['bytes']<2000000 and binding(b['path'])==b
    return json.loads(Path(b['path']).read_text())

def stat(b):
    p=Path(b['path']);s=p.stat();assert s.st_size==b['bytes']
    return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,inherited_sha256=b['sha256'],rehashed=False)

def sources():
    return [binding(TOOLS/n) for n in ('stage220_training_domain_model_review.py',
     'test_stage220_training_domain_model_review.py','stage207_local_curve_information_review.py','stage156_voluntary_choices.py')]

def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def near(a,b,rtol=1e-10,atol=1e-10):
    np.testing.assert_allclose(a,b,rtol=rtol,atol=atol,equal_nan=True)

def family(v):return int(hashlib.sha256(str(v).encode()).hexdigest(),16)%2

def design(raw,scaler):
    finite=np.isfinite(raw);s=scaler['common']
    x=np.column_stack((np.where(finite,(raw-np.asarray(s['mean']))/np.asarray(s['scale']),0.),(~finite).astype(float)))
    assert x.shape==(len(raw),52) and np.isfinite(x).all();return x

def training_mask(u,epochs,calendar):
    """Independent bisect/calendar math, with no producer/domain helper import."""
    out=[]
    for k,e in zip(u,epochs):
        month=e.rsplit('.',1)[1];y,m=int(month[:4]),int(month[4:]);assert 1<=m<=12
        y,m=(y-1,12) if m==1 else (y,m-1);target=f'{y:04d}-{m:02d}-01'
        if target<calendar[0]:out.append(False);continue
        D=int(k)+1;assert D<len(calendar),'unknown source successor in training'
        K=bisect.bisect_left(calendar,target)
        out.append(calendar[D]<target if K==len(calendar) else D<K)
    return np.asarray(out,bool)

def inherited_equations(H0,r0,z_excluded,w_excluded,y_excluded,c):
    P=np.diag(np.r_[np.ones(52),0.])
    with threadpool_limits(limits=1):
        he=z_excluded.T@(w_excluded[:,None]*z_excluded)
        re=z_excluded.T@(w_excluded*y_excluded)
    return c*(H0-P-he)+P,c*(r0-re)

def actual(auth,output):
    began=time.monotonic();output.mkdir(parents=True,exist_ok=False)
    counts=dict(fit=0,cash=0,SQL=0,old_fit=0,old_prediction=0,old_selection=0,old_cash_replay=0,
      source_projection=0,large_old_input_hashes=0,actions_reads=0,mothers_reads=0,common_reads=0,
      training_cache_reads=0,new_score_reads=0,old_score_reads=0,new_choice_reads=0,old_choice_reads=0)
    try:
        protocol=small(auth['protocol']);manifest=small(auth['manifest']);accepted=load('stage207_local_curve_information_review');selector=load('stage156_voluntary_choices')
        assert manifest['status']=='completed' and manifest['protocol_sha256']==PROTOCOL_SHA and manifest['input_bindings']==protocol['input_bindings']
        assert manifest['source_bundle']==auth['producer_source_bundle']
        for b in manifest['source_bundle']:assert binding(b['path'])==b
        terminal=small(manifest['terminal']);summary=small(manifest['summary']);preflight=small(manifest['preflight']);records=small(manifest['fit_records'])
        assert terminal['exit_code']==0 and manifest['counters']==terminal['counters']==summary['counters']
        c=manifest['counters'];assert c['fit_calls_attempted']==c['fit_calls_completed']==6
        assert c['prediction_model_rows']==1933480 and c['candidate_selection_calls']==3 and c['control_choices_csv_reads']==2
        for k in ('old_fit','cash','old_cash','SQL','new_labels','source_projection','q_npz_reads','training_weights_recomputed','control_score_csv_reads','control_main_selection_calls','control_held_selection_calls'):
            assert c[k]==0,k
        assert preflight['ready'] and preflight['all_support_before_any_fit'] and len(preflight['cells'])==len(records)==6
        inputs=protocol['input_bindings'];old_records=small(inputs['control_fit_records']);old={(r['scope'],r['cutoff']):r for r in old_records}
        domain=small(inputs['training_domain_summary']);domain={(r['scope'],r['cutoff']):r for r in domain['folds']}
        inherited={k:inputs[k] for k in ('actions','mothers','common','control_choices_main_K','control_held_K')}
        for r in old_records:inherited['train/'+r['scope']+'/'+r['cutoff']]=r['training_identity_weights']
        before={k:stat(b) for k,b in inherited.items()}
        counts['actions_reads']+=1;a=pd.read_csv(inputs['actions']['path'],usecols=FIELDS,dtype=str,keep_default_na=False,float_precision='round_trip')
        for f in NUMERIC:a[f]=pd.to_numeric(a[f],errors='coerce')
        counts['mothers_reads']+=1;m=pd.read_csv(inputs['mothers']['path'],usecols=IDENTITY,dtype=str,keep_default_na=False)
        for f in ('sequence_index','u_index'):m[f]=m[f].astype(np.int64)
        assert len(a)==1552456 and len(m)==399252 and a.action_id.is_unique and m.event_id.is_unique
        assert np.array_equal(a.sequence_index,np.arange(len(a))) and np.array_equal(m.sequence_index,np.arange(len(m)))
        counts['common_reads']+=1
        with np.load(inputs['common']['path'],allow_pickle=False) as z:raw=z['common'].astype(float);assert raw.shape==(len(a),26)
        b=inputs['calendar'];assert binding(b['path'])==b
        cal=np.load(b['path'],allow_pickle=False)
        calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal] if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        assert len(calendar)==5587 and calendar==sorted(set(calendar))
        fitted={};math_checks=[]
        for r in records:
            key=(r['scope'],r['cutoff']);o=old[key];cut=key[1]
            use=a.u_action_eligible.eq(1)&a.label_state.eq('closed_complete_bar_model')&a.u_date.lt(cut)&a.label_known_date.ne('')&a.label_known_date.lt(cut)&np.isfinite(a.net_R_stress)
            if key[0]!='main':use &= a.family_id.map(family).ne(int(key[0][-1]))
            ti=np.flatnonzero(use.to_numpy());assert len(ti)==o['training_rows']==r['training_rows']
            counts['training_cache_reads']+=1
            cache=pd.read_csv(o['training_identity_weights']['path'],usecols=[f for f in FIELDS if f!='participation_state']+['sample_weight'],dtype=str,keep_default_na=False)
            for f in NUMERIC+['sample_weight']:cache[f]=cache[f].astype(float)
            assert len(cache)==len(ti)
            for f in FIELDS:
                if f=='participation_state':continue
                left,right=cache[f].to_numpy(),a[f].to_numpy()[ti]
                assert np.array_equal(left,right,equal_nan=True) if f in NUMERIC else np.array_equal(left,right),(key,f)
            w=cache.sample_weight.to_numpy(float);mask=training_mask(a.u_index.to_numpy()[ti],a.reference_epoch.to_numpy()[ti],calendar)
            W,WA=math.fsum(w),math.fsum(w[mask]);factor=W/WA;new=w[mask]*factor;d=r['domain'];ref=domain[key]
            assert mask.any() and np.isfinite(w).all() and (w>0).all() and np.isfinite(new).all() and (new>0).all()
            assert int(mask.sum())==d['retained_rows']==ref['admissible_rows'] and int((~mask).sum())==d['excluded_rows']==ref['inadmissible_rows']
            assert d['gate_unknown_rows']==ref['unknown_rows']==0 and W==d['old_weight_mass']==ref['old_weight_mass'] and WA==d['admissible_old_weight_mass']==ref['admissible_old_weight_mass']
            assert factor==d['weight_uniform_factor'] and abs(math.fsum(new)-W)<=8*math.ulp(W)
            ess=lambda x:math.fsum(x)**2/math.fsum(float(v)*float(v) for v in x)
            for k,v in [('old_effective_sample_size',ess(w)),('retained_old_effective_sample_size',ess(w[mask])),('candidate_effective_sample_size',ess(new))]:near(d[k],v,rtol=1e-12,atol=1e-9)
            with np.load(r['training_domain_support']['path'],allow_pickle=False) as z:
                assert np.array_equal(z['sequence_index'],ti) and np.array_equal(z['admissible_mask'],mask) and np.array_equal(z['old_weight'],w)
                nw=np.zeros(len(ti));nw[mask]=new;assert np.array_equal(z['new_weight'],nw)
            os=small(o['scaler']);ns=small(r['scaler']);assert ns['new_scaling'] is False and ns['reused_scaler']==o['scaler']
            for k,v in os.items():assert ns[k]==v
            model=small(r['portable_model']);assert model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky') and len(model['coef'])==52
            assert model['feature_names']==os['feature_names'] and model['scope']==key[0] and model['cutoff']==cut
            assert binding(o['normal_equations']['path'])==o['normal_equations']
            with np.load(o['normal_equations']['path'],allow_pickle=False) as z:H0=z['lhs'];rhs0=z['rhs']
            xe=design(raw[ti[~mask]],os);ze=np.column_stack((xe,np.ones(len(xe))))
            H,rhs=inherited_equations(H0,rhs0,ze,w[~mask],a.net_R_stress.to_numpy()[ti[~mask]],factor)
            assert binding(r['normal_equations']['path'])==r['normal_equations']
            with np.load(r['normal_equations']['path'],allow_pickle=False) as z:
                near(H,z['lhs'],rtol=1e-10,atol=1e-7);near(rhs,z['rhs'],rtol=1e-10,atol=1e-7)
                beta=np.r_[model['coef'],model['intercept']];near(z['coefficient_with_intercept'],beta,rtol=0,atol=0);near(z['weight_sum'],math.fsum(new),rtol=0,atol=0)
                err=float(np.max(np.abs(H-z['lhs'])))
            near(H@beta,rhs,rtol=1e-8,atol=1e-7)
            fitted[key]=(model,os);math_checks.append(dict(scope=key[0],cutoff=cut,retained_rows=int(mask.sum()),excluded_rows=int((~mask).sum()),factor=factor,max_H_abs_error=err,max_normal_residual=float(np.max(np.abs(H@beta-rhs)))))
            print(json.dumps(dict(phase='new_domain_model_verified',scope=key[0],cutoff=cut)),flush=True)
        assert set(fitted)=={(s,c) for s in SCOPES for c in CUTOFFS}
        actual_choices={}
        for role in ('choices_main','choices_holdout'):
            counts['new_choice_reads']+=1;actual_choices[role]=pd.read_csv(manifest[role]['path'],dtype=str,keep_default_na=False)
        for role in ('control_choices_main_K','control_held_K'):
            counts['old_choice_reads']+=1;actual_choices[role]=pd.read_csv(inputs[role]['path'],dtype=str,keep_default_na=False)
        forward=a.u_date.ge('2020-01-01').to_numpy();seen={True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)};score_counts=Counter();max_score_error=0.
        def stream():
            nonlocal max_score_error
            counts['new_score_reads']+=1
            for chunk in pd.read_csv(manifest['child_scores']['path'],chunksize=65536,dtype=str,keep_default_na=False,float_precision='round_trip'):
                for f in ('sequence_index','mother_sequence_index','u_index','u_action_eligible'):chunk[f]=chunk[f].astype(np.int64)
                chunk['score']=chunk.score.astype(float);ids=chunk.sequence_index.to_numpy(int)
                for f in selector.SCORE_FIELDS:
                    if f not in ('scope','cutoff','score'):assert np.array_equal(chunk[f],a[f].to_numpy()[ids]),f
                assert chunk.arm.eq('DOMAIN52').all() and np.isfinite(chunk.score).all() and forward[ids].all()
                for key,part in chunk.groupby(['scope','cutoff'],sort=False):
                    ii=part.sequence_index.to_numpy(int);main=key[0]=='main';assert key in fitted and not seen[main][ii].any()
                    assert part.u_date.ge(key[1]).all() and (part.u_date.lt('2023-01-01') if key[1]=='2020-01-01' else part.u_date.le(END)).all()
                    if not main:assert part.family_id.map(family).eq(int(key[0][-1])).all()
                    seen[main][ii]=True;model,scaler=fitted[key]
                    with threadpool_limits(limits=1):expected=design(raw[ii],scaler)@np.asarray(model['coef'])+model['intercept']
                    near(part.score.to_numpy(),expected);max_score_error=max(max_score_error,float(np.max(np.abs(part.score.to_numpy()-expected))));score_counts[key]+=len(part)
                yield from chunk.to_dict('records')
        bounds=small(manifest['boundaries'])['epochs'];new_bounds={};held_new=[];selection=[]
        for scope,rows in itertools.groupby(stream(),key=lambda r:r['scope']):
            parents=m.loc[m.u_date.ge('2020-01-01')]
            if scope!='main':parents=parents.loc[parents.family_id.map(family).eq(int(scope[-1]))]
            result=selector.select_full_pool(parents.to_dict('records'),(dict(r,scope='main') for r in rows),calendar,END,audit_sink=lambda _:None)
            role='choices_main' if scope=='main' else 'choices_holdout';accepted.check_choice_rows(result['choices'],actual_choices[role],scope,'DOMAIN52')
            for e,b in result['boundaries'].items():assert b==bounds[e];new_bounds[e]=b
            if scope!='main':held_new.extend(dict(r,scope=scope) for r in result['choices'])
            selection.append(dict(scope=scope,parent_rows=len(result['choices']),selected=sum(r['selected'] for r in result['choices'])))
            print(json.dumps(dict(phase='full_new_selection_verified',scope=scope)),flush=True)
        assert [x['scope'] for x in selection]==list(SCOPES) and new_bounds==bounds and sum(score_counts.values())==1933480
        assert all(np.array_equal(z,forward) for z in seen.values())
        for r in records:assert score_counts[(r['scope'],r['cutoff'])]==r['prediction_children']
        # Independent action-equivalence receipt; score magnitude intentionally ignored.
        new=actual_choices['choices_main'].sort_values('sequence_index',key=lambda x:x.astype(int));control=actual_choices['control_choices_main_K'].sort_values('sequence_index',key=lambda x:x.astype(int))
        assert len(new)==len(control)==161014
        for f in IDENTITY+['anchor_epoch']:assert new[f].tolist()==control[f].tolist()
        changed=np.zeros(len(new),bool)
        for f in ('chosen_action_id','chosen_action_sequence_index','chosen_epoch','selected'):changed|=new[f].to_numpy()!=control[f].to_numpy()
        ident=small(manifest['selection_identity']);assert int(changed.sum())==ident['changed_parent_rows'] and bool(changed.any())==manifest['cash_eligible']==ident['cash_eligible']
        saved=small(manifest['held_diagnostic']);days_saved=pd.read_csv(manifest['held_daily']['path'],dtype={'u_date':str,'scope':str},float_precision='round_trip');held_checks={}
        old_held=actual_choices['control_held_K'].copy()
        for f in ('sequence_index','u_index','selected'):old_held[f]=old_held[f].astype(int)
        for scope in SCOPES[1:]:
            h,days=accepted.held_diagnostic(old_held.loc[old_held.scope.eq(scope)].to_dict('records'),[r for r in held_new if r['scope']==scope],a)
            h['selected_by_arm']['DOMAIN52']=h['selected_by_arm'].pop('CURVE53');g=saved['groups'][scope]
            for k,v in h.items():
                if k=='annual':
                    assert len(v)==len(g[k])
                    for x,y in zip(v,g[k]):
                        assert x['year']==y['year']
                        for q in x:
                            if q!='year':assert x[q] is y[q] if x[q] is None else np.isclose(x[q],y[q],rtol=1e-10,atol=1e-11)
                elif isinstance(v,dict):assert v==g[k]
                elif v is None:assert g[k] is None
                else:near(v,g[k])
            dd=days_saved.loc[days_saved.scope.eq(scope)].reset_index(drop=True);assert dd.u_date.tolist()==days.u_date.tolist()
            for k in ('delta_R','known_family_u','unknown_family_u'):near(dd[k].to_numpy(),days[k].to_numpy())
            held_checks[scope]=h
        after={k:stat(b) for k,b in inherited.items()};assert before==after
        receipt=dict(schema='stage220_domain_model_review_v1',status='completed',core_blockers=0,manifest=auth['manifest'],protocol=auth['protocol'],source_bundle=sources(),producer_source_bundle=manifest['source_bundle'],counters=counts,
          math_checks=math_checks,new_prediction_model_rows=sum(score_counts.values()),max_forward_abs_error=max_score_error,selection_checks=selection,changed_main_parents=int(changed.sum()),cash_eligible=manifest['cash_eligible'],held_checks=held_checks,
          inherited_source_stat_before=before,inherited_source_stat_after=after,old_math_inherited=True,old_cash_replayed=False,remaining_phase='new_cash_review_only_if_run',
          limitations=['conditional historical algorithm comparison, not unseen OOS','original firstexit held target is not K cash target','no strict firstrelease PIT or real execution qualification'],goal_complete=False)
        write(output/'review_receipt.json',receipt);write(output/'terminal.json',dict(status='completed',exit_code=0,counters=counts,elapsed_seconds=time.monotonic()-began))
        print(json.dumps(dict(status='completed',core_blockers=0,prediction_rows=sum(score_counts.values()),max_forward_error=max_score_error,changed_main=int(changed.sum()))),flush=True)
    except BaseException as exc:
        write(output/'failure.json',dict(status='failed',error=str(exc),traceback=traceback.format_exc(),counters=counts,automatic_retry=False));raise

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--actual',action='store_true',required=True);p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True);p.add_argument('--output',type=Path,default=OUTPUT);args=p.parse_args(argv)
    assert args.output.resolve()==OUTPUT and not OUTPUT.exists();ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256;auth=small(ab)
    required=dict(schema='stage217_exact_root_model_review_authorization_v1',authorized_by='root',protocol_sha256=PROTOCOL_SHA,output=str(OUTPUT))
    assert all(auth.get(k)==v for k,v in required.items()) and auth['source_bundle']==sources() and auth['protocol']==binding(PROTOCOL) and auth['protocol']['sha256']==PROTOCOL_SHA
    actual(auth,OUTPUT)

if __name__=='__main__':main()
