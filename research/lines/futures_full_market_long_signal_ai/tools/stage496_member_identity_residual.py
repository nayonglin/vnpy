"""Frozen Stage495 disclosed-member identity residual experiment.

Import performs no research I/O. Historical actual is disabled without an exact
root authorization; tests use synthetic inputs only. No cash, SQL or network.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
ARMS=('B_MEMBER_AVAILABILITY','C_MEMBER_IDENTITY')
END='2026-10-16'
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION_ID=['sequence_index','event_id','actual_epoch','action_sequence_index','action_id','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']
Y_FIELDS=['entry_index','exit_index','entry_date','exit_date','label_state','label_known_date','net_R_stress','participation_state']
ACTION_USECOLS=ACTION_ID+Y_FIELDS
_MODULES={}


def load(name):
    if name not in _MODULES:
        spec=importlib.util.spec_from_file_location('stage496_pure_'+name[:-3],TOOLS/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_MODULES[name]=module
    return _MODULES[name]


def member_token(exchange,name,member_id):
    """Exact accepted reporting label; do not normalize Unicode or merge aliases."""
    if not isinstance(name,str) or not isinstance(member_id,str):raise ValueError('identity must be strings')
    if name:return 'N|'+str(exchange)+'|'+name
    if member_id:return 'I|'+str(exchange)+'|'+member_id
    raise ValueError('empty member identity')


def disclosed_observation(exchange,long_vector,short_vector):
    quantities={};signed={};gross_by_token={};totals=[]
    for sign,vector in ((1,long_vector),(-1,short_vector)):
        total=0.
        for item in vector:
            state=item.get('qty_state');qty=item.get('qty')
            if state in ('empty_slot','unidentified_true_zero'):
                if state=='unidentified_true_zero' and qty!=0:raise ValueError('nonzero unidentified row')
                continue
            if state!='valid' or isinstance(qty,bool) or not isinstance(qty,(int,float)) or not math.isfinite(qty) or qty<0 or qty!=int(qty):
                raise ValueError('invalid verified disclosed quantity')
            token=member_token(exchange,item.get('member_name',''),item.get('member_id',''))
            total+=qty;quantities[token]=quantities.get(token,0.)+qty
            signed[token]=signed.get(token,0.)+sign*qty;gross_by_token[token]=gross_by_token.get(token,0.)+qty
        if total<=0:raise ValueError('both visible sides must have positive sum')
        totals.append(total)
    gross=sum(totals)
    return dict(signed={k:v/gross for k,v in signed.items()},gross={k:v/gross for k,v in gross_by_token.items()},
        signed_total=(totals[0]-totals[1])/gross,long_sum=totals[0],short_sum=totals[1],observed_gross=gross)


def train_vocabulary(observations):
    return sorted({token for obs in observations for token,qty in obs['gross'].items() if qty>0})


def encode_observations(observations,vocabulary):
    index={v:i for i,v in enumerate(vocabulary)}
    if len(index)!=len(vocabulary):raise ValueError('duplicate vocabulary')
    z=np.zeros((len(observations),len(vocabulary)),float);b=np.ones((len(observations),2),float)
    for i,obs in enumerate(observations):
        b[i,1]=obs['signed_total']
        for token,value in obs['signed'].items():
            if token in index:z[i,index[token]]=value
    if not np.isfinite(z).all() or not np.isfinite(b).all() or (np.abs(z).sum(axis=1)>1.+1e-12).any():raise ValueError('invalid bounded disclosure design')
    return z,b


def normalize_weights(weights):
    w=np.asarray(weights,float)
    if w.ndim!=1 or not len(w) or not np.isfinite(w).all() or (w<=0).any():raise ValueError('invalid positive source weights')
    return w/w.sum()


def identity_support(z,b,weights):
    z=np.asarray(z,float);b=np.asarray(b,float);w=normalize_weights(weights)
    if z.ndim!=2 or b.shape!=(len(z),2) or len(w)!=len(z) or not np.isfinite(z).all() or not np.isfinite(b).all():raise ValueError('identity support shape/finite')
    p=z.shape[1]
    if p<2:return dict(ready=False,reason='fewer_than_two_positive_mass_tokens',token_count=p)
    H=np.vstack([np.ones(p),b.T@(w[:,None]*z)])
    _,singular,Vt=np.linalg.svd(H,full_matrices=True)
    tol=np.finfo(float).eps*max(H.shape)*(singular[0] if len(singular) else 0.)
    rank=int((singular>tol).sum());P=Vt[rank:].T
    q=z@P
    trace=float(np.einsum('ij,i,ij->',q,w,q)) if P.shape[1] else 0.
    ready=P.shape[1]>0 and trace>1e-12
    return dict(ready=ready,reason='' if ready else 'no_identity_direction_beyond_B',token_count=p,
        constraint_rank=rank,null_dimension=P.shape[1],constraint_singular_values=singular.tolist(),constraint_rank_tolerance=float(tol),
        constraint_matrix=H.tolist(),null_basis=P.tolist(),projected_weighted_trace=trace,
        raw_weighted_trace=float(np.einsum('ij,i,ij->',z,w,z)),weight_sum=float(w.sum()))


def fit_B(b,residual,weights,on_completed=None):
    b=np.asarray(b,float);y=np.asarray(residual,float);w=normalize_weights(weights)
    if b.shape!=(len(y),2) or not np.isfinite(b).all() or not np.isfinite(y).all():raise ValueError('invalid B input')
    lhs=b.T@(w[:,None]*b)+np.diag([0.,1.]);rhs=b.T@(w*y);coef=np.linalg.solve(lhs,rhs)
    if on_completed is not None:on_completed()
    if not np.allclose(lhs@coef,rhs,rtol=1e-10,atol=1e-12):raise ValueError('B normal equations')
    return dict(coef_B=coef.tolist(),B_lhs=lhs.tolist(),B_rhs=rhs.tolist(),B_alpha=1.,B_intercept_penalized=False,
        weight_sum=float(w.sum()),B_normal_equation_error=float(np.max(np.abs(lhs@coef-rhs))))


def fit_C(z,b,residual,weights,B,support=None,on_completed=None):
    z=np.asarray(z,float);b=np.asarray(b,float);y=np.asarray(residual,float);w=normalize_weights(weights)
    support=identity_support(z,b,w) if support is None else support
    if not support['ready']:raise ValueError('source identity support not ready')
    P=np.array(support['null_basis'],float);q=z@P;target=y-b@np.array(B['coef_B'])
    gram=q.T@(w[:,None]*q);rhs=q.T@(w*target);theta=np.linalg.solve(gram+np.eye(gram.shape[0]),rhs)
    if on_completed is not None:on_completed()
    beta=P@theta
    eig=np.linalg.eigvalsh(gram);df=float(np.sum(eig/(eig+1.)));trace=float(np.trace(gram))
    if df>1.+1e-10 or trace>1.+1e-10 or abs(beta.sum())>1e-9 or not np.allclose(b.T@(w*(z@beta)),0.,atol=1e-10):raise ValueError('C capacity or orthogonality contract failed')
    if not np.allclose((gram+np.eye(len(theta)))@theta,rhs,rtol=1e-10,atol=1e-12):raise ValueError('C normal equations')
    return dict(coef_C=beta.tolist(),C_theta=theta.tolist(),null_basis=P.tolist(),constraint_matrix=support['constraint_matrix'],
        identity_gram=gram.tolist(),identity_rhs=rhs.tolist(),identity_gram_eigenvalues=eig.tolist(),identity_df=df,identity_trace_gram=trace,
        identity_alpha=1.,identity_no_intercept=True,identity_no_zscore=True,coefficient_sum=float(beta.sum()),
        B_orthogonality_max_abs=float(np.max(np.abs(b.T@(w*(z@beta))))),new_identity_parameter_count=z.shape[1],
        C_normal_equation_error=float(np.max(np.abs((gram+np.eye(len(theta)))@theta-rhs))))


def fit_residual_heads(z,b,residual,weights):
    B=fit_B(b,residual,weights);C=fit_C(z,b,residual,weights,B)
    return dict(**B,**C)


def apply_head(base_scores,observations,head,arm):
    if arm not in ARMS:raise ValueError('unknown arm')
    scores=np.array(base_scores,float,copy=True);states=['source_missing_fallback_A']*len(scores)
    ids=[i for i,obs in enumerate(observations) if obs is not None]
    if ids:
        z,b=encode_observations([observations[i] for i in ids],head['vocabulary'])
        scores[ids]+=b@np.array(head['coef_B'])
        if arm==ARMS[1]:scores[ids]+=z@np.array(head['coef_C'])
        for i in ids:states[i]='applied'
    return scores,states


def family_group(value):return int(hashlib.sha256(str(value).encode()).hexdigest(),16)%2


def training_slice(frame,cutoff,scope):
    ok=(frame.u_date.lt(cutoff)&frame.label_state.eq('closed_complete_bar_model')&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)&
        frame.u_action_eligible.eq(1)&frame.pre_domain.astype(bool)&frame.source_observed.astype(bool)&np.isfinite(frame.net_R_stress))
    if scope!='main':ok &= frame.family_id.map(family_group).ne(int(scope[-1]))
    return frame.loc[ok].copy()


def lookup_exact(u_date,u_index,epoch,calendar,lookup):
    if not 0<=int(u_index)<len(calendar) or calendar[int(u_index)]!=u_date:raise ValueError('u/calendar identity changed')
    return lookup.get((calendar[int(u_index)-1],epoch)) if int(u_index)>0 and epoch else None


def h():return load('stage489_fomc_residual_experiment.py')
def binding(path):return h().binding(path)
def read_bytes(bound):return h().read_bytes(bound)
def read_json(bound):return json.loads(read_bytes(bound))
def inherited_stat(bound):return h().inherited_stat(bound)
def write_json(path,value):return h().write_json(path,value)
def checkpoint(path,value):return h().checkpoint(path,value)
def write_table(path,frame):return h().write_table(path,frame)
def safe(value):return h().safe(value)


def source_bundle():
    return sorted([binding(TOOLS/n) for n in ['stage496_member_identity_residual.py','test_stage496_member_identity_residual.py',
        'stage489_fomc_residual_experiment.py','stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py']],key=lambda b:b['path'])


def before_delivery_K(epoch,u_index,calendar,boundaries):
    selector=load('stage156_voluntary_choices.py')
    if epoch not in boundaries:boundaries[epoch]=selector.calendar_boundary(epoch,calendar,END)
    b=boundaries[epoch];D=int(u_index)+1
    return (False if b['K_state']=='before_calendar_blocked' or D>=len(calendar) else
        D<b['K_index'] if b['K_index'] is not None else calendar[D]<b['K_target_date'])


def project_source_once(bound,calendar,out):
    """Only accepted normalized scope vectors; source raw and prices not opened."""
    before=inherited_stat(bound);lookup={};observations=[];meta=[];states=Counter();count=0
    date_index={d:i for i,d in enumerate(calendar)}
    with gzip.open(bound['path'],'rt',newline='') as stream:
        reader=csv.DictReader(stream)
        required={'scope_id','source_date','epoch','product_id','exchange','mapping_state','scope_status','long_vector_json','short_vector_json','long_vector_sha256','short_vector_sha256','long_sum','short_sum'}
        if not required.issubset(reader.fieldnames):raise ValueError('accepted162 vector schema changed')
        for row in reader:
            count+=1;states[row['scope_status']]+=1
            if row['scope_status']!='verified':continue
            if row['mapping_state']!='exact_epoch' or not row['epoch'] or row['product_id']!=row['epoch'].rsplit('.',1)[0] or row['exchange']!=row['epoch'].split('.')[0]:raise ValueError('verified exact scope identity mismatch')
            source_date=row['source_date'];v=date_index.get(source_date)
            if v is None or v+1>=len(calendar):raise ValueError('accepted source outside complete calendar')
            key=(source_date,row['epoch'])
            if key in lookup:raise ValueError('duplicate exact source epoch/date')
            for side in ('long','short'):
                if hashlib.sha256(row[side+'_vector_json'].encode()).hexdigest()!=row[side+'_vector_sha256']:raise ValueError('accepted vector row hash changed')
            obs=disclosed_observation(row['exchange'],json.loads(row['long_vector_json']),json.loads(row['short_vector_json']))
            if obs['long_sum']!=float(row['long_sum']) or obs['short_sum']!=float(row['short_sum']):raise ValueError('accepted vector total differs')
            sid=len(observations);lookup[key]=sid;observations.append(obs)
            meta.append(dict(source_observation_index=sid,scope_id=row['scope_id'],source_date=source_date,u_date=calendar[v+1],u_index=v+1,
                reference_epoch=row['epoch'],product_id=row['product_id'],family_id=row['product_id'].removesuffix('_F'),
                long_vector_sha256=row['long_vector_sha256'],short_vector_sha256=row['short_vector_sha256'],
                signed_total=obs['signed_total'],observed_gross=obs['observed_gross'],positive_mass_tokens=sum(v>0 for v in obs['gross'].values())))
    after=inherited_stat(bound)
    if before!=after:raise ValueError('accepted162 scope stat drift')
    if count!=211023 or len(observations)!=170803:raise ValueError('complete accepted162 scope domain changed')
    source_meta=pd.DataFrame(meta)
    artifact=write_table(out/'source_scope_identity_projection.csv.gz',source_meta)
    # Reusable sparse numeric source, not duplicate original vectors or raw.
    sparse=out/'source_sparse_disclosed.jsonl.gz'
    with sparse.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
            for sid,obs in enumerate(observations):
                gz.write((json.dumps(dict(source_observation_index=sid,**obs),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode())
    return lookup,observations,source_meta,dict(source_scope_identity_projection=artifact,source_sparse_disclosed=binding(sparse)),dict(
        reads=1,before=before,after=after,normalized_scope_rows=count,verified_scope_rows=len(observations),states=dict(states),source_raw_reads=0)


def source_X_preflight(source_meta,observations,calendar):
    """Zero-Y structural support, deliberately not a mature-action certification."""
    boundaries={};meta=source_meta.copy();meta['pre_domain']=[before_delivery_K(r.reference_epoch,r.u_index,calendar,boundaries) for r in meta.itertuples()]
    cells=[]
    for scope in SCOPES:
        for cutoff in CUTOFFS:
            train=meta.loc[meta.u_date.lt(cutoff)&meta.pre_domain]
            pred=meta.loc[meta.u_date.ge(cutoff)&meta.u_date.le(END)&meta.pre_domain&
                (meta.u_date.lt('2023-01-01') if cutoff==CUTOFFS[0] else True)]
            if scope!='main':
                group=int(scope[-1]);train=train.loc[train.family_id.map(family_group).ne(group)];pred=pred.loc[pred.family_id.map(family_group).eq(group)]
            vocab=train_vocabulary([observations[i] for i in train.source_observation_index]);known=set(vocab)
            supported=sum(any(abs(v)>0 and token in known for token,v in observations[i]['signed'].items()) for i in pred.source_observation_index)
            ready=bool(len(train)>0 and len(vocab)>=2 and supported>0)
            cells.append(dict(scope=scope,cutoff=cutoff,ready=ready,source_rows=len(train),source_token_count=len(vocab),forward_supported_source_rows=supported))
    return dict(schema='stage496_source_X_preflight_v1',ready=len(cells)==6 and all(c['ready'] for c in cells),cells=cells,
        numeric_Y_read=False,original_actions_read=False,mature_action_support_certified=False)


def validate_action_domain(count,forward,products,families,canonical,expected_rows=1552456,expected_forward=966740):
    """The complete policy domain may contain products with no observed children."""
    products=set(products);families=set(families);policy_products=set(canonical);policy_families=set(canonical.values())
    if count!=expected_rows or forward!=expected_forward:
        raise ValueError('original action row count changed '+json.dumps(dict(actual_rows=count,expected_rows=expected_rows,
            actual_forward=forward,expected_forward=expected_forward),sort_keys=True))
    if not products.issubset(policy_products) or not families.issubset(policy_families):
        raise ValueError('observed child outside canonical mother policy '+json.dumps(dict(
            foreign_products=sorted(products-policy_products),foreign_families=sorted(families-policy_families)),sort_keys=True))
    return dict(canonical_policy_products=len(policy_products),canonical_policy_families=len(policy_families),
        observed_child_products=len(products),observed_child_families=len(families),observed_child_product_ids=sorted(products),
        observed_child_family_ids=sorted(families),policy_products_without_observed_children=sorted(policy_products-products),
        policy_families_without_observed_children=sorted(policy_families-families),nochild_policy_rows_retained=True)


def project_actions_once(bound,lookup,observations,calendar,out,mothers):
    before=inherited_stat(bound);parts=[];labels=[];count=forward=0;products=set();families=set();boundaries={};forward_parents=set();forward_products=set();forward_families=set()
    pairs=mothers[['product_id','family_id']].drop_duplicates()
    if pairs.product_id.duplicated().any():raise ValueError('canonical product/family identity not unique')
    canonical=dict(zip(pairs.product_id,pairs.family_id))
    for chunk in pd.read_csv(bound['path'],usecols=ACTION_USECOLS,dtype=str,keep_default_na=False,compression='gzip',chunksize=100000,float_precision='round_trip'):
        seq=pd.to_numeric(chunk.sequence_index,errors='raise').to_numpy(np.int64)
        if not np.array_equal(seq,np.arange(count,count+len(chunk))):raise ValueError('complete original action sequence changed')
        if not chunk.sequence_index.eq(chunk.action_sequence_index).all() or not chunk.action_id.eq(chunk.event_id).all() or not chunk.actual_epoch.eq(chunk.reference_epoch).all():raise ValueError('original action identity aliases changed')
        idx=pd.to_numeric(chunk.u_index,errors='raise').to_numpy(np.int64)
        if (idx<0).any() or (idx>=len(calendar)).any() or not np.array_equal(np.array(calendar)[idx],chunk.u_date.to_numpy()):raise ValueError('original action/calendar mismatch')
        if not chunk.family_id.eq(chunk.product_id.str.removesuffix('_F')).all() or not chunk.product_id.eq(chunk.reference_epoch.str.rsplit('.',n=1).str[0]).all():raise ValueError('original family/epoch mismatch')
        count+=len(chunk);products.update(chunk.product_id);families.update(chunk.family_id)
        source_ids=np.array([lookup.get((calendar[u-1],e),-1) if u>0 else -1 for u,e in zip(idx,chunk.reference_epoch)],np.int64)
        chunk['source_observation_index']=source_ids
        visible=chunk.loc[source_ids>=0].copy()
        if len(visible):
            visible['source_observed']=True
            visible['pre_domain']=[before_delivery_K(r.reference_epoch,int(r.u_index),calendar,boundaries) and int(r.u_action_eligible)==1 for r in visible.itertuples()]
            parts.append(visible)
        forward_mask=chunk.u_date.between(CUTOFFS[0],END);f=chunk.loc[forward_mask,['action_id']+Y_FIELDS].copy();labels.append(f);forward+=len(f)
        forward_parents.update(pd.to_numeric(chunk.loc[forward_mask,'mother_sequence_index'],errors='raise').to_numpy(np.int64));forward_products.update(chunk.loc[forward_mask,'product_id']);forward_families.update(chunk.loc[forward_mask,'family_id'])
    after=inherited_stat(bound)
    if before!=after:raise ValueError('original129 actions stat drift')
    domain_precheck=write_json(out/'original_action_domain_precheck.json',dict(original_action_rows=count,forward_action_rows=forward,
        observed_child_products=len(products),observed_child_families=len(families),observed_child_product_ids=sorted(products),observed_child_family_ids=sorted(families),
        canonical_policy_products=len(canonical),canonical_policy_families=len(set(canonical.values())),
        canonical_policy_product_ids=sorted(canonical),canonical_policy_family_ids=sorted(set(canonical.values())),
        sequence_contiguity_checked=True,canonical_nochild_policy_retained=True))
    domain=validate_action_domain(count,forward,products,families,canonical)
    domain.update(forward_observed_child_products=len(forward_products),forward_observed_child_families=len(forward_families),
        forward_policy_products_without_observed_children=sorted(set(canonical)-forward_products),
        forward_policy_families_without_observed_children=sorted(set(canonical.values())-forward_families),
        full_forward_mother_rows=len(mothers),forward_observed_parent_rows=len(forward_parents),
        forward_mother_rows_without_observed_children=int((~mothers.sequence_index.isin(forward_parents)).sum()))
    features=pd.concat(parts,ignore_index=True);forward_labels=pd.concat(labels,ignore_index=True)
    for col in ['sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_index','exit_index','net_R_stress']:
        features[col]=pd.to_numeric(features[col].replace('',np.nan),errors='raise')
    forward_labels.net_R_stress=pd.to_numeric(forward_labels.net_R_stress.replace('',np.nan),errors='raise')
    if features.action_id.duplicated().any() or forward_labels.action_id.duplicated().any():raise ValueError('action projection duplicate identity')
    artifacts=dict(original_action_domain_precheck=domain_precheck,source_observable_actions_labels=write_table(out/'source_observable_actions_labels.csv.gz',features),
        forward_outcome_projection=write_table(out/'forward_outcome_projection.csv.gz',forward_labels))
    return features,forward_labels,artifacts,dict(reads=1,before=before,after=after,total_rows=count,forward_Y_rows=forward,source_observable_rows=len(features),
        usecols=ACTION_USECOLS,numeric_Y_read=True,numeric_Y_used_for_source_gate=False,new_labels_generated=0,observed_child_domain=domain)


def mature_plans(features,observations,calendar,out):
    original=load('stage130_contract_choice_fit.py');plans={};cells=[];artifacts={}
    for scope in SCOPES:
        for cutoff in CUTOFFS:
            train=training_slice(features,cutoff,scope)
            if train.empty:
                cells.append(dict(scope=scope,cutoff=cutoff,ready=False,reason='no_mature_source_action'));continue
            weights,groups=original.training_weights(train);w=normalize_weights(weights.sample_weight.to_numpy(float))
            obs=[observations[i] for i in train.source_observation_index];vocab=train_vocabulary(obs);z,b=encode_observations(obs,vocab);support=identity_support(z,b,w)
            forward=features.loc[features.u_date.ge(cutoff)&features.u_date.le(END)&features.pre_domain&
                (features.u_date.lt(CUTOFFS[1]) if cutoff==CUTOFFS[0] else True)]
            if scope!='main':forward=forward.loc[forward.family_id.map(family_group).eq(int(scope[-1]))]
            known=set(vocab);forward_supported=sum(any(abs(value)>0 and token in known for token,value in observations[i]['signed'].items()) for i in forward.source_observation_index)
            support['forward_supported_rows']=forward_supported;support['ready']=bool(support['ready'] and forward_supported>0)
            if forward_supported<=0:support['reason']='no_forward_identity_support'
            train=train.copy();train['source_sample_weight_mean1']=weights.sample_weight.to_numpy(float);train['sample_weight_sum1']=w
            directory=out/'folds'/scope/cutoff;directory.mkdir(parents=True)
            support_binding=write_json(directory/'support_pre_fit.json',dict(scope=scope,cutoff=cutoff,**support,vocabulary=vocab,
                numeric_Y_already_read=True,no_predictive_estimate_fitted=True,weights='original130 algorithm reapplied conditional source/eligible/K/maturity/held complement then sum1'))
            train_binding=write_table(directory/'training_identity_weights.csv.gz',train)
            artifacts[scope+'|'+cutoff]=dict(support=support_binding,training=train_binding)
            cells.append(dict(scope=scope,cutoff=cutoff,ready=support['ready'],reason=support['reason'],training_rows=len(train),
                training_families=int(train.family_id.nunique()),token_count=len(vocab),projected_weighted_trace=support.get('projected_weighted_trace'),
                forward_supported_rows=forward_supported,max_training_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),support=support_binding))
            plans[scope,cutoff]=dict(train=train,z=z,b=b,weights=w,vocabulary=vocab,support=support,training_binding=train_binding)
    return plans,dict(schema='stage496_mature_identity_support_v1',ready=len(cells)==6 and all(c['ready'] for c in cells),cells=cells,
        all_six_before_any_fit=True,numeric_Y_already_read=True,numeric_Y_distribution_analyzed=False),artifacts


def authorize(args):
    pb=binding(args.protocol)
    if pb['sha256']!=args.protocol_sha256 or Path(pb['path'])!=LINE/'outputs/stage495_member_identity_protocol/protocol.json':raise ValueError('exact495 protocol path/SHA required')
    p=read_json(pb)
    if p.get('schema')!='stage495_member_identity_residual_protocol_v1' or pb['sha256']!='d3e3a5430b18ef71293cb950c06c5ef4e68f56d452edad3a8bf2bd343a653918':raise ValueError('frozen495 schema/SHA required')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=read_json(ab);bundle=source_bundle();out=Path(args.output).resolve();recovery=args.command=='recover-source-fit'
    required_schema='stage496_member_identity_recovery_authorization_v1' if recovery else 'stage496_member_identity_fit_authorization_v1'
    if (auth.get('schema')!=required_schema or auth.get('authorized_by')!='root' or auth.get('mode')!=args.command or
        not h().same(auth.get('protocol',{}),pb) or auth.get('source_bundle')!=bundle or auth.get('output')!=str(out) or
        auth.get('new_fits_max')!=12 or auth.get('actual_run_limit')!=1):raise ValueError('exact root496 fit/recovery authorization differs')
    if out.exists() or LINE/'outputs/stage496_member_identity_residual' not in out.parents:raise ValueError('fresh own Stage496 output required')
    if recovery:
        prior=read_json(auth['recovery_from_manifest']);terminal=read_json(prior['terminal'])
        roles=('source_scope_identity_projection','source_sparse_disclosed','source_X_preflight')
        if (prior.get('schema')!='stage496_member_identity_fit_manifest_v1' or prior.get('status')!='failed' or
            not h().same(prior.get('protocol_binding',{}),pb) or prior.get('new_fits_attempted')!=0 or prior.get('new_fits_completed')!=0 or
            terminal.get('error')!='ValueError: complete original action policy domain changed' or
            set(auth.get('recovery_source_checkpoints',{}))!=set(roles) or
            any(not h().same(prior['artifacts'][role],auth['recovery_source_checkpoints'][role]) for role in roles) or
            auth.get('prior_original129_whitelist_streams_completed')!=1 or auth.get('additional_original129_whitelist_streams_max')!=1 or
            auth.get('additional_member_scopes_streams_max')!=0 or auth.get('reuse_completed_source_X_preflight') is not True):
            raise ValueError('exact failed-guard source-checkpoint recovery contract differs')
    return out,p,pb,ab,bundle,auth


def restore_source_checkpoints(auth,calendar):
    """Restore completed Stage496 source outputs; never reopen accepted162 source."""
    saved=auth['recovery_source_checkpoints'];meta=h().read_table(saved['source_scope_identity_projection'])
    h().as_numbers(meta,['source_observation_index','u_index','signed_total','observed_gross','positive_mass_tokens'])
    if len(meta)!=170803 or not np.array_equal(meta.source_observation_index.to_numpy(),np.arange(170803)) or meta.duplicated(['source_date','reference_epoch']).any():
        raise ValueError('completed source checkpoint identity changed')
    lookup={}
    for row in meta.itertuples():
        u=int(row.u_index)
        if u<=0 or u>=len(calendar) or calendar[u]!=row.u_date or calendar[u-1]!=row.source_date:raise ValueError('source checkpoint exact predecessor mismatch')
        lookup[row.source_date,row.reference_epoch]=int(row.source_observation_index)
    observations=[]
    with gzip.GzipFile(fileobj=io.BytesIO(read_bytes(saved['source_sparse_disclosed'])),mode='rb') as stream:
        for line in stream:
            value=json.loads(line);sid=value.pop('source_observation_index')
            if sid!=len(observations):raise ValueError('sparse source checkpoint row order changed')
            if (not math.isfinite(value['observed_gross']) or value['observed_gross']<=0 or
                not np.isfinite(list(value['signed'].values())).all() or not np.isfinite(list(value['gross'].values())).all() or
                abs(sum(value['gross'].values())-1.)>1e-12 or sum(abs(v) for v in value['signed'].values())>1.+1e-12):
                raise ValueError('sparse source checkpoint numeric integrity')
            observations.append(value)
    if len(observations)!=len(meta):raise ValueError('source sparse/meta checkpoint length changed')
    gate=read_json(saved['source_X_preflight'])
    if gate.get('schema')!='stage496_source_X_preflight_v1' or gate.get('ready') is not True or len(gate.get('cells',[]))!=6:raise ValueError('completed source-X gate required')
    receipt=dict(recovery_from_manifest=auth['recovery_from_manifest'],source_checkpoint_bindings=saved,
        original162_member_scopes_reads_this_process=0,source_raw_reads=0,completed_source_X_preflight_reused=True,
        derived_source_metadata_reads=1,derived_sparse_source_reads=1,source_preflight_reads=1,
        prior_original129_whitelist_streams_completed=1,additional_original129_whitelist_streams_authorized=1,
        cumulative_original129_whitelist_streams_if_completed=2,prior_fits_attempted=0,prior_fits_completed=0)
    return lookup,observations,meta,dict(saved),receipt,gate


def validate_small_lineage(inputs):
    accepted=read_json(inputs['source_acceptance']);member=read_json(inputs['member_manifest'])
    if (not accepted.get('source_measurement_arithmetic_accepted') or not h().same(accepted.get('source_manifest',{}),inputs['member_manifest']) or
        member.get('schema')!='stage162_member_distribution_manifest_v1' or member.get('status')!='completed'):
        raise ValueError('accepted165/162 arithmetic lineage required')
    scopes=next((b for b in member['artifacts'] if b.get('role')=='normalized_scopes'),{})
    if not h().same(scopes,inputs['member_scopes']):raise ValueError('accepted162 normalized scope binding differs')
    oldfit=read_json(inputs['fit489_manifest'])
    if oldfit.get('status')!='completed':raise ValueError('completed489 causal projections required')
    for role in ('forward_mothers_projection','causal_actions_projection'):
        if not h().same(oldfit['artifacts'][role],inputs[role]):raise ValueError('reused489 projection lineage mismatch '+role)
    for role in ('original_actions','original_common','original130_scores','causal_actions_projection','forward_mothers_projection'):
        inherited_stat(inputs[role])
    return dict(source_acceptance=inputs['source_acceptance'],member_manifest=inputs['member_manifest'],fit489_manifest=inputs['fit489_manifest'],
        strict_first_publication_PIT_certified=False,large_hashes_inherited=True)


def predict_one(obs,head):
    seen=set(head['vocabulary']);beta=dict(zip(head['vocabulary'],head['coef_C']))
    b=head['coef_B'];B=float(b[0]+b[1]*obs['signed_total'])
    C=sum(beta.get(token,0.)*value for token,value in obs['signed'].items())
    return B,B+C,sum(value for token,value in obs['signed'].items() if token in seen),sum(value for token,value in obs['gross'].items() if token in seen)


def execute(args):
    out,p,pb,ab,bundle,auth=authorize(args);out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();began=datetime.now(timezone.utc).isoformat();attempted=completed=0;status='failed';error=None;artifacts={};receipts={};choice_bindings={}
    write_json(out/'started.json',dict(protocol=pb,authorization=ab,source_bundle=bundle,started_at=began,auto_retry=False))
    def progress(phase):checkpoint(out/'progress.json',dict(phase=phase,new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0))
    def record_completed():
        nonlocal completed
        completed+=1;progress('physical_microfit_completed')
    try:
        inputs=p['input_bindings'];receipts['lineage']=validate_small_lineage(inputs)
        calendar=h().decode_calendar(np.load(io.BytesIO(read_bytes(inputs['calendar'])),allow_pickle=False))
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('complete052 calendar required')
        mothers=h().read_table(inputs['forward_mothers_projection']);h().as_numbers(mothers,['sequence_index','u_index'])
        if mothers.columns.tolist()!=IDENTITY or len(mothers)!=161014 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('complete489 forward mother7 projection required')
        progress('source_projection')
        if args.command=='recover-source-fit':
            lookup,observations,source_meta,source_artifacts,receipts['source_checkpoint_recovery'],sourcegate=restore_source_checkpoints(auth,calendar)
            artifacts.update(source_artifacts)
        else:
            lookup,observations,source_meta,source_artifacts,receipts['member_scopes']=project_source_once(inputs['member_scopes'],calendar,out);artifacts.update(source_artifacts)
            sourcegate=source_X_preflight(source_meta,observations,calendar);artifacts['source_X_preflight']=write_json(out/'source_X_preflight.json',sourcegate)
        if not sourcegate['ready']:
            status='support_stopped';summary=dict(status=status,reason='zeroY_source_support_failed',new_fit=0,new_cash=0,goal_complete=False)
        else:
            progress('one_original129_actions_whitelist')
            features,forward_labels,new_artifacts,receipts['original_actions']=project_actions_once(inputs['original_actions'],lookup,observations,calendar,out,mothers);artifacts.update(new_artifacts)
            receipts['original_actions']['prior_completed_streams']=1 if args.command=='recover-source-fit' else 0
            receipts['original_actions']['cumulative_completed_streams']=2 if args.command=='recover-source-fit' else 1
            if len(features)!=165413:raise ValueError('inherited165 observed full action count differs')
            plans,maturegate,support_artifacts=mature_plans(features,observations,calendar,out)
            artifacts['mature_support_cells']=support_artifacts;artifacts['mature_preflight']=write_json(out/'mature_preflight.json',maturegate)
            if not maturegate['ready']:
                status='support_stopped';summary=dict(status=status,reason='all_six_mature_source_support_failed',new_fit=0,new_cash=0,goal_complete=False)
            else:
                original=load('stage130_contract_choice_fit.py');progress('original_COMMON_one_projection');before=inherited_stat(inputs['original_common'])
                with np.load(inputs['original_common']['path'],allow_pickle=False) as data:
                    raw=data['common']
                    if data['columns'].tolist()!=original.COMMON or raw.shape!=(1552456,26):raise ValueError('frozen26 COMMON schema differs')
                    selected_common=raw[features.sequence_index.to_numpy(np.int64)].astype(float);del raw
                after=inherited_stat(inputs['original_common'])
                if before!=after:raise ValueError('COMMON stat drift')
                receipts['original_common']=dict(reads=1,before=before,after=after,projected_rows=len(features))
                np.savez_compressed(out/'source_observable_common26.npz',common=selected_common,columns=np.array(original.COMMON),sequence_index=features.sequence_index.to_numpy(np.int64))
                artifacts['source_observable_common26']=binding(out/'source_observable_common26.npz')
                records=inputs['original_models']
                if {(r['scope'],r['cutoff']) for r in records}!={(s,c) for s in SCOPES for c in CUTOFFS}:raise ValueError('exact original six model cells required')
                heads={};fits=[]
                for scope in SCOPES:
                    for cutoff in CUTOFFS:
                        plan=plans[scope,cutoff];train=plan['train'];record=next(r for r in records if r['scope']==scope and r['cutoff']==cutoff)
                        portable=read_json(record['portable_model']);scaler=read_json(record['scaler']);idx=train.index.to_numpy(np.int64)
                        base=original.design(selected_common[idx],scaler)@np.array(portable['coef'])+float(portable['intercept'])
                        residual=train.net_R_stress.to_numpy(float)-base;directory=out/'folds'/scope/cutoff
                        artifacts.setdefault('training_residuals',{})[scope+'|'+cutoff]=write_table(directory/'training_residual_projection.csv.gz',pd.DataFrame(dict(
                            action_id=train.action_id.to_numpy(),frozen_base_score=base,original_net_R_stress=train.net_R_stress.to_numpy(float),target_residual=residual)))
                        attempted+=1;progress('fit_B:'+scope+':'+cutoff);B=fit_B(plan['b'],residual,plan['weights'],record_completed)
                        B.update(scope=scope,cutoff=cutoff,training_rows=len(train),vocabulary=plan['vocabulary'],frozen_base_model=record['portable_model'],
                            frozen_base_scaler=record['scaler'],training_binding=plan['training_binding'],training_residual_is_in_sample_not_crossfit=True)
                        Bb=write_json(directory/(ARMS[0]+'.json'),B);fits.append(dict(scope=scope,cutoff=cutoff,arm=ARMS[0],head=Bb));progress('B_completed')
                        attempted+=1;progress('fit_C:'+scope+':'+cutoff);C=fit_C(plan['z'],plan['b'],residual,plan['weights'],B,plan['support'],record_completed)
                        head={**B,**C};Cb=write_json(directory/(ARMS[1]+'.json'),head);heads[scope,cutoff]=head;fits.append(dict(scope=scope,cutoff=cutoff,arm=ARMS[1],head=Cb));progress('C_completed')
                        # Release the cell's dense source design; no re-fit or score-derived word selection.
                        del plan['z'];del plan['b']
                if (attempted,completed)!=(12,12):raise ValueError('exact12 new residual estimates required')
                artifacts['fit_records']=write_json(out/'fit_records.json',fits)
                overlays={};diagnostics=[];coverage_by_id={};feature_by_id=features.set_index('action_id',verify_integrity=True)
                for scope in SCOPES:
                    for cutoff in CUTOFFS:
                        domain=features.loc[features.u_date.ge(cutoff)&features.u_date.le(END)&features.pre_domain&
                            (features.u_date.lt(CUTOFFS[1]) if cutoff==CUTOFFS[0] else True)]
                        if scope!='main':domain=domain.loc[domain.family_id.map(family_group).eq(int(scope[-1]))]
                        head=heads[scope,cutoff];cache={}
                        for row in domain.itertuples():
                            sid=int(row.source_observation_index)
                            if sid not in cache:cache[sid]=predict_one(observations[sid],head)
                            B,C,seen_signed,seen_gross=cache[sid];coverage_by_id[scope,cutoff,row.action_id]=(seen_signed,seen_gross)
                            overlays[scope,cutoff,ARMS[0],row.action_id]=B;overlays[scope,cutoff,ARMS[1],row.action_id]=C
                            diagnostics.append(dict(scope=scope,cutoff=cutoff,action_id=row.action_id,u_date=row.u_date,product_id=row.product_id,family_id=row.family_id,
                                source_observation_index=sid,seen_signed=seen_signed,seen_gross=seen_gross,OOV_gross=1.-seen_gross,identity_increment=C-B))
                artifacts['forward_identity_coverage']=write_table(out/'forward_identity_coverage.csv.gz',pd.DataFrame(diagnostics))
                accum={}
                for scope in SCOPES:
                    parents=mothers if scope=='main' else mothers.loc[mothers.family_id.map(family_group).eq(int(scope[-1]))]
                    for arm in ('A',)+ARMS:accum[scope,arm]=h().ChoiceAccumulator(parents,calendar,scope)
                counts=Counter();state_counts=Counter();coverage_counts={};score_overlays=[];scoreb=inputs['original130_scores'];before=inherited_stat(scoreb);progress('one_original130_score_stream')
                with gzip.open(scoreb['path'],'rt',newline='') as stream:
                    reader=csv.DictReader(stream)
                    if any(c not in reader.fieldnames for c in load('stage156_voluntary_choices.py').SCORE_FIELDS):raise ValueError('original score schema changed')
                    for row in reader:
                        scope=row['scope'];cutoff=row['cutoff'];aid=row['action_id']
                        if scope not in SCOPES or cutoff not in CUTOFFS:raise ValueError('original six score cells changed')
                        counts[scope,cutoff]+=1;accum[scope,'A'].observe(row);score=float(row['score']);audit=None
                        coverage_key=(scope,row['u_date'][:4],row['product_id'],row['family_id'])
                        cv=coverage_counts.setdefault(coverage_key,np.zeros(7,float));cv[0]+=1;cv[1]+=int(aid in feature_by_id.index)
                        if (scope,cutoff,aid) in coverage_by_id:
                            seen_signed,seen_gross=coverage_by_id[scope,cutoff,aid];cv[2]+=1;cv[3]+=seen_gross;cv[4]+=1.-seen_gross;cv[5]+=int(seen_gross==0.);cv[6]+=seen_signed
                        for arm in ARMS:
                            key=(scope,cutoff,arm,aid);applied=key in overlays;candidate=dict(row)
                            state='applied' if applied else 'source_present_domain_fallback_A' if aid in feature_by_id.index else 'source_missing_fallback_A'
                            if applied:candidate['score']=score+overlays[key]
                            accum[scope,arm].observe(candidate);state_counts[scope,arm,state]+=1
                            if aid in feature_by_id.index:
                                if audit is None:audit=dict(row,score_A=score)
                                audit['score_'+arm]=float(candidate['score']);audit['head_state_'+arm]=state
                        if audit is not None:score_overlays.append(audit)
                after=inherited_stat(scoreb)
                if before!=after:raise ValueError('original score stat drift')
                old_records=read_json(inputs['original130_fit_records'])
                if sum(counts.values())!=1933480 or {(r['scope'],r['cutoff']):r['prediction_children'] for r in old_records}!=dict(counts):raise ValueError('complete original six prediction cells changed')
                receipts['original130_scores']=dict(reads=1,before=before,after=after,rows=sum(counts.values()),cells=[dict(scope=s,cutoff=c,rows=n) for (s,c),n in sorted(counts.items())])
                artifacts['source_score_overlays']=write_table(out/'source_score_overlays.csv.gz',pd.DataFrame(score_overlays));selected={};boundaries={}
                for scope in SCOPES:
                    for arm in ('A',)+ARMS:
                        frame=accum[scope,arm].finish(arm);selected[scope,arm]=frame;choice_bindings[scope,arm]=write_table(out/f'choices_{scope}_{arm}.csv.gz',frame)
                        for epoch,b in accum[scope,arm].boundaries.items():
                            if epoch in boundaries and boundaries[epoch]!=b:raise ValueError('K inconsistent across cells')
                            boundaries[epoch]=b
                coverage_rows=[]
                for scope in SCOPES:
                    parents=mothers if scope=='main' else mothers.loc[mothers.family_id.map(family_group).eq(int(scope[-1]))]
                    for (year,product,family),part in parents.assign(year=parents.u_date.str[:4]).groupby(['year','product_id','family_id'],sort=True):
                        cv=coverage_counts.get((scope,year,product,family),np.zeros(7,float))
                        coverage_rows.append(dict(scope=scope,year=year,product_id=product,family_id=family,mother_rows=len(part),child_rows=int(cv[0]),
                            source_observed_children=int(cv[1]),source_missing_children=int(cv[0]-cv[1]),qualified_source_children=int(cv[2]),
                            known_gross_mass_sum=float(cv[3]),OOV_gross_mass_sum=float(cv[4]),allOOV_children=int(cv[5]),known_signed_mass_sum=float(cv[6]),
                            no_observed_children_mothers=int((~part.sequence_index.isin(accum[scope,'A'].observed)).sum())))
                artifacts['full_policy_coverage_by_year_product']=write_table(out/'full_policy_coverage_by_year_product.csv.gz',pd.DataFrame(coverage_rows))
                family_coverage=pd.DataFrame(coverage_rows).drop(columns=['product_id']).groupby(['scope','year','family_id'],sort=True,as_index=False).sum(numeric_only=True)
                artifacts['full_policy_coverage_by_year_family']=write_table(out/'full_policy_coverage_by_year_family.csv.gz',family_coverage)
                oldchoices=h().read_table(inputs['accepted156_choices'],usecols=['event_id','chosen_action_id','selected'])
                check=selected['main','A'];old=oldchoices.set_index('event_id').reindex(check.event_id)
                if check.chosen_action_id.tolist()!=old.chosen_action_id.tolist() or check.selected.tolist()!=pd.to_numeric(old.selected,errors='raise').tolist():raise ValueError('A full-domain main choices differ accepted156')
                boundary_binding=write_json(out/'boundaries.json',dict(schema='stage156_voluntary_K_only_v1',epochs=boundaries,
                    policy_version=load('stage156_voluntary_choices.py').POLICY_VERSION,sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False))
                contrasts={};held_daily=[]
                for name,active,control in [('B_minus_A',ARMS[0],'A'),('C_minus_A',ARMS[1],'A'),('C_minus_B',ARMS[1],ARMS[0])]:
                    groups={}
                    for scope in SCOPES[1:]:
                        groups[scope],daily=h().paired_held(selected[scope,active],selected[scope,control],forward_labels)
                        daily['scope']=scope;daily['contrast']=name;held_daily.append(daily)
                    contrasts[name]=dict(groups=groups,unknown_bounds_available=False,full_policy_cash_qualified=False)
                held_binding=write_json(out/'held_gate.json',dict(schema='stage496_member_identity_held_contrasts_v1',contrasts=contrasts,
                    not_blind_OOS=True,same_action_cancellation_not_imputation=True))
                artifacts['held_daily']=write_table(out/'held_daily.csv.gz',pd.concat(held_daily,ignore_index=True));artifacts['held_gate']=held_binding
                artifacts.update(boundaries=boundary_binding,forward_mothers_projection=inputs['forward_mothers_projection'],
                    causal_actions_projection=inputs['causal_actions_projection'],calendar=inputs['calendar'])
                for (scope,arm),b in choice_bindings.items():artifacts['choices_'+scope+'_'+arm]=b
                status='completed';summary=dict(status=status,new_fit=completed,new_cash=0,full_original_mothers_provenance=399252,full_original_actions=1552456,
                    forward_parent_rows=len(mothers),forward_products=98,forward_families=95,full_forward_main_children=966740,source_observable_actions=len(features),
                    state_counts=[dict(scope=s,arm=a,state=st,rows=n) for (s,a,st),n in sorted(state_counts.items())],
                    choices=[dict(scope=s,candidate=a,parents=len(f),selected=int(f.selected.sum())) for (s,a),f in selected.items()],
                    historical_PIT_qualified=False,full_mechanism_identified=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        if source_bundle()!=bundle:raise ValueError('source bundle changed during actual')
        receipts.update(new_fits=completed,new_cash=0,native_SQL=0,downloads=0,original52_fits=0,source_raw_reads=0,old_control_cash_replays=0)
        artifacts['read_receipt']=write_json(out/'read_receipt.json',receipts);artifacts['summary']=write_json(out/'summary.json',summary);progress(status)
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        if (out/'original_action_domain_precheck.json').exists() and 'original_action_domain_precheck' not in artifacts:
            artifacts['original_action_domain_precheck']=binding(out/'original_action_domain_precheck.json')
        terminal=write_json(out/'terminal.json',dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-start,new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0,native_SQL=0,auto_retry=False))
        manifest=dict(schema='stage496_member_identity_fit_manifest_v1',status=status,protocol_binding=pb,protocol_sha256=pb['sha256'],authorization=ab,
            source_bundle=bundle,terminal=terminal,artifacts=artifacts,new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0,production_qualified=False,goal_complete=False)
        manifest_binding=write_json(out/'manifest.json',manifest)
        if status=='completed':
            write_json(out/'cash_handoff.json',dict(schema='stage496_member_identity_cash_handoff_v1',protocol_binding=pb,protocol_sha256=pb['sha256'],
                fit_manifest_binding=manifest_binding,arms={arm:dict(choices_main_binding=choice_bindings['main',arm],held_diagnostic_binding=held_binding) for arm in ARMS},
                causal_actions_projection_binding=inputs['causal_actions_projection'],forward_mothers_projection_binding=inputs['forward_mothers_projection'],
                boundaries_binding=boundary_binding,calendar_binding=inputs['calendar'],held_gate_binding=held_binding))
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for command in ('fit','recover-source-fit'):
        actual=sub.add_parser(command)
        for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):actual.add_argument('--'+name,required=True)
    args=parser.parse_args(argv);print(json.dumps(safe(execute(args)),ensure_ascii=False))


if __name__=='__main__':main()
