"""Independent bounded audit for frozen495/496/497; no fit or cash replay.

Original COMMON, original129 and original raw membership sources are not opened.
The once-only old130 score stream verifies every new choice. Cash is exclusively
delegated to independent500; this tool never reads native cache or old A books.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import gzip
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

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='d3e3a5430b18ef71293cb950c06c5ef4e68f56d452edad3a8bf2bd343a653918'
ARMS=('B_MEMBER_AVAILABILITY','C_MEMBER_IDENTITY')
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
END='2026-10-16'
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
_spec=importlib.util.spec_from_file_location('independent498_accepted490',TOOLS/'stage490_fomc_economic_review.py')
prior=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(prior)
# A fresh private module namespace only; no source file or author module mutation.
prior.ARMS=ARMS
write,bind,nums,truth,identities=prior.write,prior.bind,prior.nums,prior.truth,prior.identities
READS=Counter()
ERRORS={}


def source_bundle():
    return sorted([bind(Path(__file__)),bind(TOOLS/'test_stage498_member_identity_review.py'),
        bind(TOOLS/'stage490_fomc_economic_review.py')],key=lambda x:x['path'])


def eq(a,b,label,atol=1e-12,rtol=1e-10):
    a,b=np.asarray(a,float),np.asarray(b,float)
    assert a.shape==b.shape,(label,'shape',a.shape,b.shape)
    assert np.array_equal(np.isnan(a),np.isnan(b)),(label,'NaN')
    assert np.array_equal(np.isfinite(a),np.isfinite(b)),(label,'finite')
    good=np.isfinite(a);error=np.abs(a[good]-b[good])
    ERRORS[label]=max(ERRORS.get(label,0.),float(error.max()) if error.size else 0.)
    assert np.all(error<=atol+rtol*np.abs(b[good])),(label,ERRORS[label])


class Reader(prior.Reader):
    def read(self,b,retain=True):
        path=str(Path(b['path']).resolve())
        if path not in self.raw:READS['bound_file:'+path]+=1
        return super().read(b,retain=retain)


def group(family):return int(hashlib.sha256(str(family).encode()).hexdigest(),16)%2


def source_phase(r,p,fit,calendar,out,prefix_limit):
    art=fit['artifacts'];meta=r.table(art['source_scope_identity_projection'])
    nums(meta,['source_observation_index','u_index','signed_total','observed_gross','positive_mass_tokens'])
    assert len(meta)==170803 and meta.source_observation_index.tolist()==list(range(len(meta)))
    assert not meta.duplicated(['source_date','reference_epoch']).any()
    assert meta.product_id.eq(meta.reference_epoch.str.rsplit('.',n=1).str[0]).all()
    assert meta.family_id.eq(meta.product_id.str.removesuffix('_F')).all()
    observations=[]
    raw=r.read(art['source_sparse_disclosed']);READS['new_sparse_source_complete_stream']+=1
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        for i,line in enumerate(stream):
            x=json.loads(line);assert x['source_observation_index']==i
            row=meta.iloc[i];u=int(row.u_index)
            assert 0<u<len(calendar) and row.u_date==calendar[u] and row.source_date==calendar[u-1]
            assert row.reference_epoch.split('.')[0] in ('SHFE','INE')
            assert x['long_sum']>0 and x['short_sum']>0
            eq(x['observed_gross'],x['long_sum']+x['short_sum'],'source disclosed gross')
            eq(x['signed_total'],(x['long_sum']-x['short_sum'])/x['observed_gross'],'source signed total')
            eq([row.signed_total,row.observed_gross],[x['signed_total'],x['observed_gross']],'source meta sparse numeric')
            assert set(x['signed'])==set(x['gross'])
            assert all(isinstance(k,str) and k.startswith(('N|'+row.reference_epoch.split('.')[0]+'|','I|'+row.reference_epoch.split('.')[0]+'|')) for k in x['gross'])
            assert all(math.isfinite(v) and v>=0 for v in x['gross'].values())
            assert all(math.isfinite(v) and abs(v)<=x['gross'][k]+1e-12 for k,v in x['signed'].items())
            eq(sum(x['gross'].values()),1.,'source normalized gross');eq(sum(x['signed'].values()),x['signed_total'],'source normalized signed')
            assert sum(abs(v) for v in x['signed'].values())<=1.+1e-12
            assert int(row.positive_mass_tokens)==sum(v>0 for v in x['gross'].values())
            observations.append(x)
    assert len(observations)==len(meta)
    # A fixed tiny anchor against the accepted normalized original, not its raw
    # 1.26GB archive and not a second complete normalized source scan.
    original=p['input_bindings']['member_scopes'];before=prior.stat(original['path']);prefix_rows=anchored=0
    sid_lookup={(x.source_date,x.reference_epoch):int(x.source_observation_index) for x in meta.itertuples()}
    with gzip.open(original['path'],'rt',newline='') as stream:
        reader=csv.DictReader(stream)
        for physical_index in range(prefix_limit):
            row=next(reader);prefix_rows+=1
            if row['scope_status']!='verified':continue
            sid=sid_lookup[row['source_date'],row['epoch']];expected=observations[sid];signed={};gross={};sums=[]
            for side,sign in [('long',1),('short',-1)]:
                vector=json.loads(row[side+'_vector_json']);assert hashlib.sha256(row[side+'_vector_json'].encode()).hexdigest()==row[side+'_vector_sha256']
                assert row[side+'_vector_sha256']==meta.iloc[sid][side+'_vector_sha256']
                total=0.
                for entry in vector:
                    if entry['qty_state']!='valid':continue
                    qty=entry['qty'];assert not isinstance(qty,bool) and isinstance(qty,(int,float)) and qty>=0 and qty==int(qty)
                    name=entry['member_name'];member_id=entry['member_id'];assert name or member_id
                    token=('N|' if name else 'I|')+row['exchange']+'|'+(name if name else member_id)
                    total+=qty;signed[token]=signed.get(token,0.)+sign*qty;gross[token]=gross.get(token,0.)+qty
                sums.append(total);eq(total,float(row[side+'_sum']),'prefix original disclosed total')
            G=sum(sums);assert G>0 and set(signed)==set(expected['signed']) and set(gross)==set(expected['gross'])
            for key in signed:eq(signed[key]/G,expected['signed'][key],'prefix exact-name signed contributions');eq(gross[key]/G,expected['gross'][key],'prefix exact-name gross contributions')
            anchored+=1
    assert prior.stat(original['path'])==before and prefix_rows==prefix_limit and anchored>0
    READS['old_normalized_member_prefix_rows']=prefix_rows
    write(out/'source_prefix_anchor.json',dict(fixed_first_physical_rows=prefix_rows,verified_anchors=anchored,
        complete_original_normalized_streams=0,original1p26GB_raw_reads=0,large_file_SHA_inherited_not_rehashed=True,before=before))
    features=r.table(art['source_observable_actions_labels']);nums(features,['sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_index','exit_index','net_R_stress','source_observation_index'])
    assert len(features)==165413 and not features.action_id.duplicated().any() and features.source_observation_index.notna().all()
    assert features.source_observed.map(str).str.lower().eq('true').all()
    assert features.sequence_index.eq(features.action_sequence_index).all() and features.action_id.eq(features.event_id).all()
    assert features.actual_epoch.eq(features.reference_epoch).all()
    src=meta.iloc[features.source_observation_index.astype(int)].reset_index(drop=True)
    for c in ('u_date','reference_epoch','product_id','family_id'):assert src[c].tolist()==features[c].tolist(),c
    assert src.u_index.tolist()==features.u_index.tolist()
    bounds={};eligible=[]
    for x in features.itertuples():eligible.append(int(x.u_action_eligible)==1 and prior.domain(x.reference_epoch,int(x.u_index),calendar,bounds))
    assert np.array_equal(truth(features.pre_domain),eligible)
    labels=r.table(art['forward_outcome_projection']);nums(labels,['entry_index','exit_index','net_R_stress'])
    assert len(labels)==966740 and not labels.action_id.duplicated().any()
    overlap=features.loc[features.u_date.between(CUTOFFS[0],END)]
    target=labels.set_index('action_id').loc[overlap.action_id]
    for c in ('label_state','label_known_date','participation_state','entry_date','exit_date'):assert target[c].tolist()==overlap[c].tolist(),c
    eq(target.net_R_stress.to_numpy(),overlap.net_R_stress.to_numpy(),'duplicated forward source Y')
    summary=dict(scope_rows=len(meta),source_observed_actions=len(features),full_forward_outcomes=len(labels),
        source_new_sparse_streams=1,original162_normalized_prefix_rows=prefix_rows,original162_vector_values_completely_recertified=False,
        inherited163_raw_and_normalized_parser_qualification=True,original129_values_recertified=False,
        historical_first_seen_PIT_proved=False,all_tokens_only_brokers=False,
        token_meaning='historical exchange reporting labels; some pre2013 scopes may include nonbroker members; not end investors')
    write(out/'source_phase.json',summary)
    return meta,observations,features,labels,summary


def union(intervals):
    result=[]
    for s,e in sorted((int(s),int(e)) for s,e in intervals):
        assert e>=s>=0
        if result and s<=result[-1][1]+1:result[-1]=(result[-1][0],max(e,result[-1][1]))
        else:result.append((s,e))
    return result


def independent_weights(train):
    f=train.reset_index(drop=True);base=np.zeros(len(f));groups=[]
    for (family,day),idx in f.groupby(['family_id','u_date'],sort=True).indices.items():
        idx=np.asarray(idx,int);intervals=union(zip(f.entry_index.to_numpy()[idx],f.exit_index.to_numpy()[idx]))
        groups.append(dict(family=family,idx=idx,intervals=intervals,length=sum(e-s+1 for s,e in intervals)))
    for family in sorted({x['family'] for x in groups}):
        rows=[x for x in groups if x['family']==family];last=max(e for x in rows for s,e in x['intervals']);delta=np.zeros(last+2,int)
        for x in rows:
            for s,e in x['intervals']:delta[s]+=1;delta[e+1]-=1
        concurrency=np.cumsum(delta[:-1]);inv=np.zeros(len(concurrency));good=concurrency>0;inv[good]=1./concurrency[good]
        prefix=np.r_[0.,np.cumsum(inv)]
        for x in rows:
            uniqueness=sum(prefix[e+1]-prefix[s] for s,e in x['intervals'])/x['length']
            base[x['idx']]=uniqueness/len(x['idx'])
    total=pd.Series(base).groupby(f.u_date,sort=False).transform('sum').to_numpy();raw=base/total
    assert np.isfinite(raw).all() and (raw>0).all()
    return raw/raw.sum(),raw/raw.mean()


def encode(obs,vocabulary):
    index={k:i for i,k in enumerate(vocabulary)};z=np.zeros((len(obs),len(index)));b=np.ones((len(obs),2))
    for i,x in enumerate(obs):
        b[i,1]=x['signed_total']
        for token,value in x['signed'].items():
            if token in index:z[i,index[token]]=value
    return z,b


def model_phase(r,p,fit,observations,features,out):
    art=fit['artifacts'];records=r.doc(art['fit_records']);assert len(records)==12
    assert {(x['scope'],x['cutoff'],x['arm']) for x in records}=={(s,c,a) for s in SCOPES for c in CUTOFFS for a in ARMS}
    with np.load(io.BytesIO(r.read(art['source_observable_common26'])),allow_pickle=False) as data:
        common=data['common'];columns=data['columns'].tolist();seq=data['sequence_index']
    assert common.shape==(len(features),26) and seq.tolist()==features.sequence_index.astype(int).tolist()
    heads={};counts=[]
    for scope in SCOPES:
        for cutoff in CUTOFFS:
            key=scope+'|'+cutoff;mask=(features.u_date.lt(cutoff)&features.label_state.eq('closed_complete_bar_model')&features.label_known_date.ne('')&features.label_known_date.lt(cutoff)&features.u_action_eligible.eq(1)&truth(features.pre_domain)&np.isfinite(features.net_R_stress))
            if scope!='main':mask &= features.family_id.map(group).ne(int(scope[-1]))
            train=features.loc[mask];saved=r.table(art['mature_support_cells'][key]['training'])
            assert len(train)>0 and saved.action_id.tolist()==train.action_id.tolist()
            w,mean1=independent_weights(train)
            eq(prior.float_tokens(saved.sample_weight_sum1),w,'all conditional sum1 weights')
            eq(prior.float_tokens(saved.source_sample_weight_mean1),mean1,'all conditional mean1 weights')
            obs=[observations[i] for i in train.source_observation_index.astype(int)];vocabulary=sorted({k for x in obs for k,v in x['gross'].items() if v>0})
            z,b=encode(obs,vocabulary);support=r.doc(art['mature_support_cells'][key]['support']);assert support['ready'] and support['vocabulary']==vocabulary
            B=r.doc(next(x['head'] for x in records if (x['scope'],x['cutoff'],x['arm'])==(scope,cutoff,ARMS[0])))
            C=r.doc(next(x['head'] for x in records if (x['scope'],x['cutoff'],x['arm'])==(scope,cutoff,ARMS[1])))
            assert B['vocabulary']==C['vocabulary']==vocabulary
            base_record=next(x for x in p['input_bindings']['original_models'] if x['scope']==scope and x['cutoff']==cutoff)
            model=r.doc(base_record['portable_model']);scaler=r.doc(base_record['scaler']);assert columns==scaler['common']['columns']
            raw=common[train.index];finite=np.isfinite(raw);mu=np.array(scaler['common']['mean']);sd=np.array(scaler['common']['scale'])
            design=np.column_stack([np.where(finite,(raw-mu)/sd,0.),(~finite).astype(float)])
            base=design@np.array(model['coef'])+model['intercept'];y=train.net_R_stress.to_numpy()-base
            residual=r.table(art['training_residuals'][key]);assert residual.action_id.tolist()==train.action_id.tolist()
            eq(prior.float_tokens(residual.frozen_base_score),base,'all frozen52 training predictions')
            eq(prior.float_tokens(residual.original_net_R_stress),train.net_R_stress.to_numpy(),'all inherited training target copies')
            eq(prior.float_tokens(residual.target_residual),y,'all residual targets')
            lhs=b.T@(w[:,None]*b)+np.diag([0.,1.]);rhs=b.T@(w*y);gamma=np.array(B['coef_B'])
            eq(B['B_lhs'],lhs,'all B lhs');eq(B['B_rhs'],rhs,'all B rhs');eq(lhs@gamma,rhs,'all B normal certificates')
            assert B['B_alpha']==1 and B['B_intercept_penalized'] is False
            eq(C['coef_B'],gamma,'C frozen B coefficients')
            Q=np.array(C['null_basis']);H=np.vstack([np.ones(len(vocabulary)),b.T@(w[:,None]*z)])
            singular=np.linalg.svd(H,compute_uv=False);tol=np.finfo(float).eps*max(H.shape)*singular[0];rank=int((singular>tol).sum())
            assert Q.shape==(len(vocabulary),len(vocabulary)-rank) and Q.shape[1]>0
            eq(Q.T@Q,np.eye(Q.shape[1]),'all null bases orthonormal');eq(H@Q,np.zeros((len(H),Q.shape[1])),'all null constraints')
            eq(C['constraint_matrix'],H,'all constraint matrices')
            q=z@Q;gram=q.T@(w[:,None]*q);crhs=q.T@(w*(y-b@gamma));theta=np.array(C['C_theta']);beta=np.array(C['coef_C'])
            eq(C['identity_gram'],gram,'all identity Gram');eq(C['identity_rhs'],crhs,'all identity RHS')
            eq((gram+np.eye(len(theta)))@theta,crhs,'all C normal certificates');eq(beta,Q@theta,'all token coefficients')
            eq(beta.sum(),0.,'all sumzero coefficients');eq(b.T@(w*(z@beta)),np.zeros(2),'all B orthogonality')
            eig=np.linalg.eigvalsh(gram);df=float(np.sum(eig/(1.+eig)));trace=float(np.trace(gram))
            eq(C['identity_df'],df,'all effective df');eq(C['identity_trace_gram'],trace,'all identity trace')
            assert 1e-12<trace<=1.+1e-10 and df<=trace+1e-10 and df>=-1e-12
            assert C['identity_alpha']==1 and C['identity_no_intercept'] is True and C['identity_no_zscore'] is True
            heads[scope,cutoff]=dict(vocabulary=vocabulary,coef_B=gamma,coef_C=beta,coef_lookup=dict(zip(vocabulary,beta)),known=set(vocabulary))
            counts.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),tokens=len(vocabulary),constraint_rank=rank,null_dimension=Q.shape[1],trace=trace,effective_df=df))
            write(out/('model_'+scope+'_'+cutoff+'.json'),counts[-1])
    report=dict(heads_checked=12,cells=counts,estimator_fits=0,original_COMMON_reads=0,source_derived_COMMON_rows=len(common),
        original_COMMON_raw_projection_values_independently_recertified=False,original_labels_inherited=True)
    write(out/'model_phase.json',report);return heads,report


def increment(obs,head):
    B=float(head['coef_B'][0]+head['coef_B'][1]*obs['signed_total'])
    identity=sum(head['coef_lookup'].get(k,0.)*v for k,v in obs['signed'].items())
    return B,B+identity,sum(v for k,v in obs['signed'].items() if k in head['known']),sum(v for k,v in obs['gross'].items() if k in head['known'])


class Choices:
    def __init__(self,mothers,scope,calendar):
        self.parents={int(x['sequence_index']):x for x in mothers.to_dict('records')};self.scope=scope;self.calendar=calendar
        self.best={};self.observed=set();self.positive=set();self.boundaries={}
    def observe(self,row,score):
        seq=int(row['mother_sequence_index']);p=self.parents[seq];u=int(row['u_index'])
        for x,y in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),('u_date','u_date'),('anchor_epoch','reference_epoch')]:assert row[x]==str(p[y]),x
        assert u==int(p['u_index']) and self.calendar[u]==row['u_date']
        assert row['cutoff']==('2020-01-01' if row['u_date']<'2023-01-01' else '2023-01-01')
        assert self.scope=='main' or group(row['family_id'])==int(self.scope[-1])
        self.observed.add(seq);eligible=int(row['u_action_eligible']);assert eligible in (0,1) and math.isfinite(score)
        if eligible and score>0:
            self.positive.add(seq)
            if prior.domain(row['reference_epoch'],u,self.calendar,self.boundaries):
                rank=(-score,row['reference_epoch'],row['action_id'])
                if seq not in self.best or rank<self.best[seq][0]:self.best[seq]=(rank,dict(row,score=score))
    def finish(self):
        winners={}
        for _,row in sorted(self.best.values(),key=lambda x:(int(x[1]['u_index']),x[1]['family_id'],x[1]['product_id'].endswith('_F'),x[1]['product_id'],x[1]['reference_epoch'],x[1]['action_id'])):
            winners.setdefault((row['family_id'],int(row['u_index'])),row)
        chosen={int(x['mother_sequence_index']):x for x in winners.values()};rows=[]
        for seq,p in sorted(self.parents.items()):
            proposal=self.best.get(seq);proposal=proposal[1] if proposal else None;win=chosen.get(seq)
            state='selected' if win else 'family_priority_suppressed' if proposal else 'no_observed_children' if seq not in self.observed else 'no_calendar_eligible_positive_action' if seq in self.positive else 'no_original_eligible_positive_action'
            rows.append(dict(p,proposed_action_id=proposal['action_id'] if proposal else '',proposed_epoch=proposal['reference_epoch'] if proposal else '',proposed_score=proposal['score'] if proposal else np.nan,
                chosen_action_id=win['action_id'] if win else '',chosen_action_sequence_index=int(win['sequence_index']) if win else -1,chosen_epoch=win['reference_epoch'] if win else '',
                anchor_epoch=p['reference_epoch'],score=win['score'] if win else np.nan,selected=int(win is not None),selection_state=state))
        return pd.DataFrame(rows)


def forward_phase(r,p,fit,meta,observations,features,heads,calendar,out):
    art=fit['artifacts'];mothers=r.table(art['forward_mothers_projection']);nums(mothers,['sequence_index','u_index'])
    assert list(mothers)==IDENTITY and len(mothers)==161014 and mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95
    accum={};expected_increment={};by_id=features.set_index('action_id',verify_integrity=True);cache={}
    for scope in SCOPES:
        parents=mothers if scope=='main' else mothers.loc[mothers.family_id.map(group).eq(int(scope[-1]))]
        for arm in ('A',)+ARMS:accum[scope,arm]=Choices(parents,scope,calendar)
    overlays=r.table(art['source_score_overlays']);nums(overlays,['score_A','score_'+ARMS[0],'score_'+ARMS[1]])
    assert not overlays.duplicated(['scope','cutoff','action_id']).any()
    overlay=overlays.set_index(['scope','cutoff','action_id']);seen=set();counts=Counter();states=Counter();coverage_counts={};expected_coverage=[]
    before=prior.stat(p['input_bindings']['original130_scores']['path'])
    READS['original130_score_complete_stream']+=1
    with gzip.open(p['input_bindings']['original130_scores']['path'],'rt',newline='') as stream:
        for row in csv.DictReader(stream):
            s,c,aid=row['scope'],row['cutoff'],row['action_id'];assert s in SCOPES and c in CUTOFFS;counts[s,c]+=1
            base=float(row['score']);present=aid in by_id.index;inc=(0.,0.);state='source_missing_fallback_A';seen_signed=seen_gross=0.
            if present:
                x=by_id.loc[aid]
                for field in ('reference_epoch','product_id','family_id','u_date'):assert row[field]==x[field],field
                assert int(row['u_index'])==int(x.u_index) and int(row['sequence_index'])==int(x.sequence_index)
                state='source_present_domain_fallback_A'
                if str(x.pre_domain).lower()=='true':
                    k=(s,c,int(x.source_observation_index))
                    if k not in cache:cache[k]=increment(observations[int(x.source_observation_index)],heads[s,c])
                    inc=cache[k][:2];seen_signed,seen_gross=cache[k][2:];state='applied'
                    expected_coverage.append(dict(scope=s,cutoff=c,action_id=aid,u_date=row['u_date'],product_id=row['product_id'],family_id=row['family_id'],
                        source_observation_index=int(x.source_observation_index),seen_signed=seen_signed,seen_gross=seen_gross,OOV_gross=1.-seen_gross,identity_increment=inc[1]-inc[0]))
                key=(s,c,aid);assert key in overlay.index;z=overlay.loc[key];seen.add(key)
                eq(z.score_A,base,'all source old A scores')
                for j,a in enumerate(ARMS):eq(z['score_'+a],base+inc[j],'all identity forward scores');assert z['head_state_'+a]==state
                expected_increment[key]=inc
            ck=(s,row['u_date'][:4],row['product_id'],row['family_id']);cv=coverage_counts.setdefault(ck,np.zeros(7))
            cv[0]+=1;cv[1]+=int(present)
            if state=='applied':cv[2]+=1;cv[3]+=seen_gross;cv[4]+=1.-seen_gross;cv[5]+=int(seen_gross==0.);cv[6]+=seen_signed
            accum[s,'A'].observe(row,base)
            for j,a in enumerate(ARMS):accum[s,a].observe(row,base+inc[j]);states[s,a,state]+=1
    assert prior.stat(p['input_bindings']['original130_scores']['path'])==before
    assert sum(counts.values())==1933480 and len(seen)==len(overlays)
    saved_counts={(x['scope'],x['cutoff']):x['prediction_children'] for x in r.doc(p['input_bindings']['original130_fit_records'])};assert dict(counts)==saved_counts
    expected_cov=pd.DataFrame(expected_coverage);saved_cov=r.table(art['forward_identity_coverage']);nums(saved_cov,['source_observation_index','seen_signed','seen_gross','OOV_gross','identity_increment'])
    expected_cov=expected_cov.set_index(['scope','cutoff','action_id']).sort_index();saved_cov=saved_cov.set_index(['scope','cutoff','action_id']).sort_index()
    assert expected_cov.index.equals(saved_cov.index)
    for col in ('u_date','product_id','family_id','source_observation_index'):assert expected_cov[col].tolist()==saved_cov[col].tolist(),col
    for col in ('seen_signed','seen_gross','OOV_gross','identity_increment'):eq(saved_cov[col].to_numpy(),expected_cov[col].to_numpy(),'all forward coverage '+col)
    coverage_rows=[]
    for scope in SCOPES:
        parents=mothers if scope=='main' else mothers.loc[mothers.family_id.map(group).eq(int(scope[-1]))]
        for (year,product,family),part in parents.assign(year=parents.u_date.str[:4]).groupby(['year','product_id','family_id'],sort=True):
            cv=coverage_counts.get((scope,year,product,family),np.zeros(7))
            coverage_rows.append(dict(scope=scope,year=year,product_id=product,family_id=family,mother_rows=len(part),child_rows=int(cv[0]),
                source_observed_children=int(cv[1]),source_missing_children=int(cv[0]-cv[1]),qualified_source_children=int(cv[2]),known_gross_mass_sum=cv[3],OOV_gross_mass_sum=cv[4],
                allOOV_children=int(cv[5]),known_signed_mass_sum=cv[6],no_observed_children_mothers=int((~part.sequence_index.isin(accum[scope,'A'].observed)).sum())))
    expected_policy=pd.DataFrame(coverage_rows)
    for role,keys,expected in [
        ('full_policy_coverage_by_year_product',['scope','year','product_id','family_id'],expected_policy),
        ('full_policy_coverage_by_year_family',['scope','year','family_id'],expected_policy.drop(columns='product_id').groupby(['scope','year','family_id'],sort=True,as_index=False).sum(numeric_only=True))]:
        saved=r.table(art[role]).set_index(keys).sort_index();expected=expected.set_index(keys).sort_index();assert saved.index.equals(expected.index),role
        for col in expected.columns:
            vals=pd.to_numeric(saved[col]).to_numpy();want=expected[col].to_numpy()
            if col in ('known_gross_mass_sum','OOV_gross_mass_sum','known_signed_mass_sum'):eq(vals,want,'all policy coverage '+col)
            else:assert vals.tolist()==want.tolist(),(role,col)
    choices={};strict=['event_id','product_id','family_id','u_date','reference_epoch','proposed_action_id','proposed_epoch','chosen_action_id','chosen_epoch','anchor_epoch','selection_state']
    for key,acc in accum.items():
        s,a=key;expected=acc.finish();saved=r.table(art['choices_'+s+'_'+a]);nums(saved,['sequence_index','u_index','selected','chosen_action_sequence_index','score','proposed_score'])
        # Persist independent winner evidence before float comparisons, not after.
        expected.to_csv(out/('expected_choices_'+s+'_'+a+'.csv.gz'),index=False,compression='gzip')
        identities(saved,expected,strict,'all new choice identity '+s+' '+a)
        for col in ['sequence_index','u_index','selected','chosen_action_sequence_index']:assert saved[col].tolist()==expected[col].tolist(),col
        for col in ['score','proposed_score']:eq(saved[col].to_numpy(),expected[col].to_numpy(),'all choice numeric '+col)
        assert saved.scope.eq(s).all() and saved.candidate.eq(a).all();choices[key]=saved
    accepted=r.table(p['input_bindings']['accepted156_choices'],usecols=['event_id','chosen_action_id','selected']);accepted=accepted.set_index('event_id').loc[choices['main','A'].event_id]
    assert accepted.chosen_action_id.tolist()==choices['main','A'].chosen_action_id.tolist()
    assert pd.to_numeric(accepted.selected).tolist()==choices['main','A'].selected.tolist()
    report=dict(original_score_rows=sum(counts.values()),all9_choices_independently_reconstructed=True,mainA_accepted156_identity_exact=True,
        heldA_absolute_winners_independently_reconstructed=True,full_policy_year_product_family_coverage_checked=True,
        original_score_streams=1,source_score_overlay_rows=len(overlays),states=[dict(scope=s,arm=a,state=st,rows=n) for (s,a,st),n in sorted(states.items())])
    write(out/'forward_phase.json',report);return mothers,choices,report


def held_pair(active,control,labels):
    lookup=labels.set_index('action_id',verify_integrity=True)
    def values(frame):
        a=frame.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index']).set_index(['family_id','u_index']).sort_index()
        values=[]
        for aid in a.chosen_action_id:
            if not aid:values.append(0.);continue
            if aid not in lookup.index:values.append(np.nan);continue
            x=lookup.loc[aid]
            values.append(0. if x.participation_state=='known_nonparticipation' else float(x.net_R_stress)
                if x.label_state=='closed_complete_bar_model' and x.label_known_date and x.label_known_date<=END and np.isfinite(x.net_R_stress) else np.nan)
        return a,np.asarray(values)
    a,av=values(active);b,bv=values(control);assert a.index.equals(b.index) and a.u_date.equals(b.u_date)
    same=a.chosen_action_id.eq(b.chosen_action_id).to_numpy();known=np.isfinite(av)&np.isfinite(bv)
    delta=np.where(same,0.,np.where(known,av-bv,np.nan));unknown=(~same)&(~known)
    facts=pd.DataFrame(dict(u_date=a.u_date.to_numpy(),delta_R=delta,known=np.isfinite(delta),unknown=unknown))
    daily=facts.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index()
    mean=float(daily.delta_R.mean()) if daily.delta_R.notna().any() else None
    result=dict(known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=int(unknown.sum()),same_action_cancelled_family_u=int(same.sum()),
        same_selected_outcome_not_loaded_cancelled=int((same&a.chosen_action_id.ne('').to_numpy()&(~known)).sum()),
        full_family_u=len(a),known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(daily.delta_R.notna().sum()),
        unknown_R_bounds=None,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or unknown.any() else 'supported',
        annual=[dict(year=y,mean_delta_R=float(part.delta_R.mean()) if part.delta_R.notna().any() else None,unknown_family_u=int(part.unknown_family_u.sum())) for y,part in daily.groupby(daily.u_date.str[:4])])
    return result,daily


def held_phase(r,fit,choices,labels,out):
    saved=r.doc(fit['artifacts']['held_gate']);saved_daily=r.table(fit['artifacts']['held_daily']);nums(saved_daily,['delta_R','known_family_u','unknown_family_u'])
    results={};contrasts={'B_minus_A':(ARMS[0],'A'),'C_minus_A':(ARMS[1],'A'),'C_minus_B':(ARMS[1],ARMS[0])}
    for name,(active,control) in contrasts.items():
        results[name]={}
        for scope in SCOPES[1:]:
            expected,daily=held_pair(choices[scope,active],choices[scope,control],labels);actual=saved['contrasts'][name]['groups'][scope]
            assert set(actual)==set(expected)
            for key,v in expected.items():
                if key=='known_u_equal_mean_increment_R':
                    if v is None:assert actual[key] is None
                    else:eq(actual[key],v,'all held known equal-u means')
                elif key=='annual':
                    assert len(actual[key])==len(v)
                    for a,b in zip(actual[key],v):
                        assert a['year']==b['year'] and a['unknown_family_u']==b['unknown_family_u']
                        if b['mean_delta_R'] is None:assert a['mean_delta_R'] is None
                        else:eq(a['mean_delta_R'],b['mean_delta_R'],'all held annual means')
                else:assert actual[key]==v,(name,scope,key)
            sd=saved_daily.loc[saved_daily.scope.eq(scope)&saved_daily.contrast.eq(name)]
            assert sd.u_date.tolist()==daily.u_date.tolist()
            for col in ('known_family_u','unknown_family_u'):assert sd[col].tolist()==daily[col].tolist(),col
            eq(sd.delta_R.to_numpy(),daily.delta_R.to_numpy(),'all held daily deltas')
            results[name][scope]=expected
    report=dict(contrasts_checked=3,held_groups_checked=6,full_forward_outcomes=len(labels),differing_unknown_not_imputed=True,results=results)
    write(out/'held_phase.json',report);return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','fit-manifest','fit-manifest-sha256','authorization','authorization-sha256','output'):ap.add_argument('--'+name,required=True)
    args=ap.parse_args();out=Path(args.output).resolve();assert LINE/'outputs/stage498_member_identity_independent_review' in out.parents
    assert not out.exists();r=Reader();docs={};argsdict=vars(args)
    for role in ('protocol','fit_manifest','authorization'):
        b=bind(argsdict[role]);assert b['sha256']==argsdict[role+'_sha256'];docs[role]=r.doc(b)
    p,fit,auth=(docs[x] for x in ('protocol','fit_manifest','authorization'))
    assert args.protocol_sha256==PROTOCOL_SHA and fit['protocol_sha256']==PROTOCOL_SHA
    assert fit['status']=='completed' and fit['new_fits_completed']==12
    assert auth['schema']=='stage498_exact_root_review_authorization_v1' and auth['authorized_by']=='root' and auth['output']==str(out) and auth['protocol_sha256']==PROTOCOL_SHA
    assert auth['reviewer_fit']==auth['reviewer_cash_replay']==0 and auth['old130_score_streams_max']==1
    assert auth['source_bundle']==source_bundle() and auth['native_cache_reads']==0 and auth['old_A_cash_ledger_reads']==0
    assert auth['original_COMMON_reads']==auth['original129_reads']==auth['original_member_raw_reads']==0
    assert auth['old_normalized_member_prefix_rows_max']==3
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();status='failed';error=None;reports={}
    write(out/'started.json',dict(arguments=argsdict,one_bounded_independent_review=True,reviewer_fits=0,cash_replays=0))
    try:
        # Only artifacts used by source/model/choice/held are registered; no cash
        # projection or native cache is force-read by Reader.finish().
        exclude={'causal_actions_projection'}
        r.register({k:v for k,v in fit['artifacts'].items() if k not in exclude});r.register(fit['source_bundle'])
        calendar_array=np.load(io.BytesIO(r.read(p['input_bindings']['calendar'])),allow_pickle=False)
        calendar=[f'{int(x):08d}'[:4]+'-'+f'{int(x):08d}'[4:6]+'-'+f'{int(x):08d}'[6:] for x in calendar_array]
        assert len(calendar)==5587 and calendar==sorted(set(calendar))
        meta,obs,features,labels,reports['source']=source_phase(r,p,fit,calendar,out,auth['old_normalized_member_prefix_rows_max'])
        heads,reports['model']=model_phase(r,p,fit,obs,features,out)
        mothers,choices,reports['forward']=forward_phase(r,p,fit,meta,obs,features,heads,calendar,out)
        reports['held']=held_phase(r,fit,choices,labels,out)
        r.finish()
        receipt=dict(schema='stage498_member_identity_independent_actual_review_v1',completed=True,reviewed_scope_material_P0=0,reviewed_scope_material_P1=0,reviewed_scope_material_P2=0,
            reports=reports,max_abs_errors=ERRORS,actual_reads=dict(READS),cash_scope_reviewed=False,cash_scope_delegated='independent500',
            reviewer_estimator_fits=0,reviewer_strategy_cash_replays=0,original_COMMON_original129_original1p26GB_raw_reads=0,native_cache_reads=0,old_A_cash_ledger_reads=0,
            source_value_scope='new sparse arithmetic/clock/identity, accepted163 normalized/raw parser inherited; no second complete original-vector recertification',
            original_COMMON_value_scope='new source-only derived slice checked against frozen model; source-index projection implementation and accepted original qualification inherited',
            all_token_broker_only_claim=False,original_member_legal_identity_continuity=False,strict_first_seen_PIT=False,alpha_proved=False,increased_betting_qualified=False,goal_complete=False)
        write(out/'review_receipt.json',receipt);status='completed';print(json.dumps(dict(status=status,reviewed_material_blockers=0,output=str(out)),ensure_ascii=False),flush=True)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());write(out/'failure.json',error);raise
    finally:write(out/'terminal.json',dict(status=status,error=error,elapsed_seconds=time.monotonic()-started,completed_phases=sorted(reports),actual_reads=dict(READS),cash_scope_reviewed=False,no_automatic_retry=True,reviewer_fits_cash_replays=0))


if __name__=='__main__':main()
