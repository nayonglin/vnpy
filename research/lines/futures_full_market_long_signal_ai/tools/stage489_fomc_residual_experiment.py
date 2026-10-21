"""Fixed FOMC numeric-package residual heads. Import performs no research I/O.

Twelve tiny weighted Ridge solves, complete original forward policies, no cash.
Only an exact root authorization enables the single fit/selection actual.
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
PROTOCOL=LINE/'outputs/stage487_fomc_residual_protocol/protocol_source_budget_recovery1.json'
PROTOCOL_SHA='cf55afebcbf3a51139fc18a2b86522cb8c96f477c56f1798b505801375998aac'
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
CASH_FIELDS=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
    'entry_capacity_qty','N_u','low20_u','u_close']
Y_FIELDS=['sequence_index','action_id','entry_index','exit_index','entry_date','exit_date',
    'label_state','label_known_date','net_R_stress','participation_state']
ACTION_USECOLS=list(dict.fromkeys(CASH_FIELDS+Y_FIELDS))
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
ARMS=('B_PRE_LIQUIDITY','C_PRE_LIQUIDITY_FOMC')
END='2026-10-16'
_MODULES={}


def load(name):
    if name not in _MODULES:
        spec=importlib.util.spec_from_file_location('stage489_pure_'+name[:-3],TOOLS/name)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_MODULES[name]=module
    return _MODULES[name]


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_bytes(bound):
    raw=Path(bound['path']).read_bytes()
    if len(raw)!=bound['bytes'] or hashlib.sha256(raw).hexdigest()!=bound['sha256']:
        raise ValueError('bound_input_changed '+bound['path'])
    return raw


def read_json(bound):return json.loads(read_bytes(bound))


def inherited_stat(bound):
    p=Path(bound['path']);s=p.stat()
    if not p.is_file() or s.st_size!=bound['bytes']:raise ValueError('inherited_size_changed '+str(p))
    return dict(path=str(p),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
        inherited_sha256=bound['sha256'],rehashed=False)


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,(np.integer,np.bool_)):return value.item()
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    return value


def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:json.dump(safe(value),stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    return binding(p)


def checkpoint(path,value):
    p=Path(path);temp=p.with_name(p.name+'.tmp')
    with temp.open('w') as stream:json.dump(safe(value),stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    temp.replace(p)


def write_table(path,frame):
    p=Path(path)
    with p.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
            with io.TextIOWrapper(gz,newline='') as stream:frame.to_csv(stream,index=False,float_format='%.17g')
    return binding(p)


def read_table(bound,usecols=None):
    return pd.read_csv(io.BytesIO(read_bytes(bound)),compression='gzip' if bound['path'].endswith('.gz') else None,
        usecols=usecols,dtype=str,keep_default_na=False,float_precision='round_trip')


def as_numbers(frame,columns):
    for c in columns:
        if c in frame:frame[c]=pd.to_numeric(frame[c].replace('',np.nan),errors='raise')
    return frame


def family_group(value):return int(hashlib.sha256(str(value).encode()).hexdigest(),16)%2


def as_bool(values):
    v=pd.Series(values).astype(str).str.lower()
    if not v.isin(['true','false','1','0']).all():raise ValueError('explicit boolean required')
    return v.isin(['true','1']).to_numpy(bool)


def numeric_mask(frame):
    """Synthetic/direct contract; actual source adapter also accepts verified logL."""
    vsm=np.column_stack([pd.to_numeric(frame[c],errors='coerce') for c in ('clean_volume','settlement','contract_multiplier')])
    verified=as_bool(frame.source_numerically_verified)
    pair=np.column_stack([pd.to_numeric(frame[c],errors='coerce') for c in ('FF4','SP500')])
    positive=np.isfinite(vsm).all(axis=1)&(vsm>0).all(axis=1)
    pair_ok=np.isfinite(pair).all(axis=1)
    state=np.select([~verified,~positive,~pair_ok],['source_not_numeric_verified','nonpositive_or_nonfinite_VSM','raw_pair_missing'],default='numeric_valid_conditional')
    mask=verified&positive&pair_ok;L=np.full(len(frame),np.nan);L[positive]=np.log(vsm[positive]).sum(axis=1)
    return mask,L,state


def equal_event_family_weights(frame):
    if len(frame)==0:raise ValueError('empty weighting domain')
    event='fomc_event_id' if 'fomc_event_id' in frame else 'event_id'
    counts=frame.groupby([event,'family_id'],sort=False).size()
    groups=frame.groupby(event,sort=False).family_id.nunique()
    values=np.array([1./(groups[e]*counts[e,f]) for e,f in zip(frame[event],frame.family_id)],float)
    return values/values.mean()


def center_events(frame):
    result=frame.copy();event='fomc_event_id' if 'fomc_event_id' in frame else 'event_id'
    result['event_center']=np.nan;result['L_centered']=np.nan
    for _,indices in result.groupby(event,sort=False).groups.items():
        ids=list(indices);part=result.loc[ids];valid=part.feature_mask.astype(bool)&part.pre_domain.astype(bool)
        if not valid.any():
            result.loc[ids,'feature_mask']=False;continue
        domain=part.loc[valid];weights=equal_event_family_weights(domain)
        center=float(np.average(domain.L.to_numpy(float),weights=weights))
        result.loc[ids,'event_center']=center;result.loc[ids,'L_centered']=part.L.to_numpy(float)-center
    result['feature_mask']=result.feature_mask.astype(bool)&np.isfinite(result.L_centered)
    return result


def training_slice(frame,cutoff,scope):
    ok=(frame.u_date.ge('2010-01-01')&frame.u_date.lt(cutoff)&frame.label_state.eq('closed_complete_bar_model')&
        frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)&frame.u_action_eligible.eq(1)&
        frame.pre_domain.astype(bool)&frame.feature_mask.astype(bool)&np.isfinite(frame.net_R_stress))
    if scope!='main':ok &= frame.family_id.map(family_group).ne(int(scope[-1]))
    return frame.loc[ok].copy()


def head_design(frame,scaler,arm):
    raw=frame[['L_centered','FF4','SP500']].to_numpy(float)
    z=(raw-np.array(scaler['mean']))/np.array(scaler['scale'])
    if not np.isfinite(z).all():raise ValueError('nonfinite head design')
    base=np.column_stack([np.ones(len(z)),z[:,0]])
    return base if arm.startswith('B') else np.column_stack([base,z[:,1],z[:,2],z[:,0]*z[:,1],z[:,0]*z[:,2]])


def fit_head(frame,residual,weights,arm):
    raw=frame[['L_centered','FF4','SP500']].to_numpy(float);weights=np.asarray(weights,float);y=np.asarray(residual,float)
    if len(raw)==0 or not np.isfinite(raw).all() or not np.isfinite(y).all() or not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('invalid mature head input')
    mu=np.average(raw,axis=0,weights=weights);var=np.average((raw-mu)**2,axis=0,weights=weights)
    std=np.sqrt(var);constant=std==0;std[constant]=1.
    scaler=dict(mean=mu.tolist(),scale=std.tolist(),variance=var.tolist(),constant=constant.tolist())
    x=head_design(frame,scaler,arm);lhs=x.T@(weights[:,None]*x);penalty=np.eye(x.shape[1]);penalty[0,0]=0.
    lhs+=penalty;rhs=x.T@(weights*y);coef=np.linalg.solve(lhs,rhs)
    error=float(np.max(np.abs(lhs@coef-rhs)))
    if not np.isfinite(coef).all() or not np.allclose(lhs@coef,rhs,rtol=1e-9,atol=1e-8):raise ValueError('head normal equations failure')
    return dict(arm=arm,scaler=scaler,coef=coef.tolist(),lhs=lhs.tolist(),rhs=rhs.tolist(),
        normal_equation_max_abs_residual=error,alpha=1.,constant_penalized=False,interaction_rescaled=False,training_rows=len(frame))


def predict_head(frame,head):return head_design(frame,head['scaler'],head['arm'])@np.array(head['coef'])


def overlay_scores(rows,features,heads,arm):
    output=rows.copy();lookup=features.set_index('action_id',verify_integrity=True)
    output['head_state']='non_event_fallback_A'
    for (scope,cutoff),idx in output.groupby(['scope','cutoff'],sort=False).groups.items():
        ids=[i for i in idx if output.at[i,'action_id'] in lookup.index]
        if not ids:continue
        event=lookup.loc[output.loc[ids,'action_id']].copy();event.index=ids
        output.loc[ids,'head_state']='field_missing_fallback_A';valid=event.feature_mask.astype(bool)
        good=event.index[valid]
        if len(good):
            output.loc[good,'score']=output.loc[good,'score'].to_numpy(float)+predict_head(event.loc[good],heads[scope,cutoff,arm])
            output.loc[good,'head_state']='applied'
    return output


def forward_mothers_from_choices(frame,expected=161014):
    result=frame[IDENTITY].copy();as_numbers(result,['sequence_index','u_index'])
    if len(result)!=expected or result.event_id.duplicated().any() or result.sequence_index.duplicated().any():raise ValueError('full forward mother identity required')
    if not result.u_date.between('2020-01-01',END).all():raise ValueError('forward parent date outside original domain')
    return result


def decode_calendar(values):
    return ([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:] for v in values]
        if values.dtype.kind in 'iu' else values.astype('datetime64[D]').astype(str).tolist())


def source_bundle():
    return sorted([binding(TOOLS/n) for n in ['stage489_fomc_residual_experiment.py','test_stage489_fomc_residual_experiment.py',
        'stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py']],key=lambda b:b['path'])


def protocol_authorization(args):
    pb=binding(args.protocol)
    if pb['sha256']!=args.protocol_sha256 or pb['sha256']!=PROTOCOL_SHA or Path(pb['path'])!=PROTOCOL:raise ValueError('frozen protocol SHA differs')
    p=read_json(pb)
    if p.get('schema')!='stage487_fomc_residual_protocol_v1':raise ValueError('fixed487 protocol identity differs')
    sb=binding(args.source_manifest)
    if sb['sha256']!=args.source_manifest_sha256:raise ValueError('source manifest SHA differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization SHA differs')
    auth=read_json(ab);out=Path(args.output).resolve();bundle=source_bundle()
    if (auth.get('schema')!='stage489_fomc_fit_authorization_v1' or auth.get('authorized_by')!='root' or
            auth.get('mode')!='fit' or not same(auth.get('protocol',{}),pb) or
            not same(auth.get('source_manifest',{}),sb) or auth.get('source_bundle')!=bundle or
            auth.get('output')!=str(out) or auth.get('new_fits_max')!=12 or auth.get('actual_run_limit')!=1):raise ValueError('exact root fit authorization differs')
    return out,p,pb,sb,ab,bundle


def raw_pair(bound):
    rows=list(csv.DictReader(io.StringIO(read_bytes(bound).decode('utf-8-sig'))))
    if len(rows)!=385:raise ValueError('fixed raw FOMC observation count differs')
    def number(v):
        try:return float(v)
        except (ValueError,TypeError):return np.nan
    return pd.DataFrame([dict(fomc_ordinal=i,source_start=r['start'],FF4=number(r['FF4']),SP500=number(r['SP500'])) for i,r in enumerate(rows)])


def build_features(inputs,source_manifest,calendar):
    metadata=inputs['event_metadata'];child=read_table(metadata['all_event_child_requests.csv.gz'])
    as_numbers(child,['fomc_ordinal','sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible','D_index'])
    if len(child)!=54089 or child.action_id.duplicated().any():raise ValueError('exact original all-event child domain differs')
    source=read_table(source_manifest['artifacts']['exact_pre_fields'],usecols=['raw_request_id','reference_epoch','pre_date',
        'source_numerically_verified','log_turnover_source_verified','source_numeric_state','rule_state','lifecycle_state'])
    if len(source)!=54089 or source.raw_request_id.duplicated().any():raise ValueError('all54089 source requests required')
    source=source.rename(columns={'log_turnover_source_verified':'L'})
    joined=child.merge(source,on=['raw_request_id','reference_epoch','pre_date'],how='left',validate='many_to_one',indicator=True)
    if not joined['_merge'].eq('both').all():raise ValueError('source identity does not cover exact epoch/pre-date requests')
    joined=joined.drop(columns='_merge');pair=raw_pair(inputs['fomc_raw'])
    joined=joined.merge(pair,on=['fomc_ordinal','source_start'],how='left',validate='many_to_one',indicator=True)
    if not joined['_merge'].eq('both').all():raise ValueError('raw ordinal/start identity mismatch')
    joined=joined.drop(columns='_merge');joined.L=pd.to_numeric(joined.L.replace('',np.nan),errors='raise')
    verified=as_bool(joined.source_numerically_verified);pair_ok=np.isfinite(joined[['FF4','SP500']].to_numpy(float)).all(axis=1)
    joined['feature_mask']=verified&np.isfinite(joined.L)&pair_ok
    joined['feature_state']=np.select([~verified,~np.isfinite(joined.L),~pair_ok],
        ['source_not_numeric_verified','nonpositive_or_nonfinite_turnover','raw_pair_missing'],default='numeric_valid_conditional')
    selector=load('stage156_voluntary_choices.py');boundaries={};domain=[]
    for row in joined.to_dict('records'):
        epoch=row['reference_epoch']
        if epoch not in boundaries:boundaries[epoch]=selector.calendar_boundary(epoch,calendar,END)
        b=boundaries[epoch];D=int(row['u_index'])+1
        if int(row['D_index'])!=D or D>=len(calendar) or row['D_date']!=calendar[D]:raise ValueError('source next-D identity differs')
        gate=(False if b['K_state']=='before_calendar_blocked' else D<b['K_index'] if b['K_index'] is not None else calendar[D]<b['K_target_date'])
        domain.append(bool(int(row['u_action_eligible'])==1 and gate))
    joined['pre_domain']=domain;joined=center_events(joined)
    joined.loc[~joined.pre_domain,'feature_state']='original_eligibility_or_DK_domain_fallback_A'
    joined['feature_mask'] &= joined.pre_domain
    return joined,boundaries


def project_actions_once(bound,features,out):
    event_ids=set(features.action_id);parts=[];total=forward=0;before=inherited_stat(bound)
    causal=out/'causal_actions_projection.csv.gz'
    with causal.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz:
            with io.TextIOWrapper(gz,newline='') as sink:
                header=True
                for chunk in pd.read_csv(bound['path'],usecols=ACTION_USECOLS,dtype=str,keep_default_na=False,
                        compression='gzip',chunksize=100000,float_precision='round_trip'):
                    seq=pd.to_numeric(chunk.sequence_index,errors='raise').to_numpy(np.int64)
                    if not np.array_equal(seq,np.arange(total,total+len(chunk))):raise ValueError('original action sequence changed')
                    if not chunk.sequence_index.eq(chunk.action_sequence_index).all() or not chunk.event_id.eq(chunk.action_id).all():raise ValueError('original action alias changed')
                    total+=len(chunk);part=chunk.loc[chunk.action_id.isin(event_ids)]
                    if len(part):parts.append(part.copy())
                    f=chunk.loc[chunk.u_date.between('2020-01-01',END),CASH_FIELDS]
                    f.to_csv(sink,index=False,header=header);header=False;forward+=len(f)
    if total!=1552456 or forward!=966740:raise ValueError('complete original action domain differs')
    after=inherited_stat(bound)
    if before!=after:raise ValueError('original actions stat drift')
    labels=pd.concat(parts,ignore_index=True)
    if len(labels)!=54089 or labels.action_id.duplicated().any() or set(labels.action_id)!=event_ids:raise ValueError('event action exact target identity differs')
    for col in ['sequence_index','action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_index','exit_index','net_R_stress']:
        labels[col]=pd.to_numeric(labels[col].replace('',np.nan),errors='raise')
    for col in ['sequence_index','action_sequence_index','mother_sequence_index','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']:
        expected=features.set_index('action_id')[col];actual=labels.set_index('action_id')[col].reindex(expected.index)
        if not np.array_equal(expected.to_numpy(),actual.to_numpy()):raise ValueError('event/original action identity differs '+col)
    # Only target fields join; all source/request identity was independently preserved above.
    target=labels[Y_FIELDS].copy();enriched=features.merge(target,on=['action_id','sequence_index'],how='left',validate='one_to_one')
    return enriched,binding(causal),dict(reads=1,before=before,after=after,total_rows=total,forward_causal_rows=forward,event_target_rows=len(labels),usecols=ACTION_USECOLS)


class ChoiceAccumulator:
    """One-pass use of accepted156 ranking/boundaries; no new selection rule."""
    def __init__(self,mothers,calendar,scope):
        self.selector=load('stage156_voluntary_choices.py');self.calendar=calendar;self.scope=scope
        self.parents={int(r['sequence_index']):r for r in mothers.to_dict('records')};self.best={};self.observed=set();self.original_positive=set();self.boundaries={};self.rows=0

    def observe(self,row):
        seq=int(row['mother_sequence_index']);p=self.parents.get(seq)
        if p is None:raise ValueError('score outside full scope mother domain')
        for c in ('mother_event_id','product_id','family_id','u_date','anchor_epoch'):
            target={'mother_event_id':'event_id','anchor_epoch':'reference_epoch'}.get(c,c)
            if str(row[c])!=str(p[target]):raise ValueError('score/parent identity mismatch '+c)
        u=int(row['u_index'])
        if u!=int(p['u_index']) or not 0<=u<len(self.calendar) or self.calendar[u]!=row['u_date']:raise ValueError('score calendar identity mismatch')
        if row['cutoff']!=self.selector.cutoff_for(row['u_date']):raise ValueError('original deployment fold differs')
        if self.scope!='main' and family_group(row['family_id'])!=int(self.scope[-1]):raise ValueError('held prediction family leaked')
        if row['reference_epoch'].rsplit('.',1)[0]!=row['product_id']:raise ValueError('exact month/product mismatch')
        original=int(row['u_action_eligible']);score=float(row['score'])
        if original not in (0,1) or not math.isfinite(score):raise ValueError('nonfinite or nonbinary prospective score row')
        self.rows+=1;self.observed.add(seq);epoch=row['reference_epoch']
        if epoch not in self.boundaries:self.boundaries[epoch]=self.selector.calendar_boundary(epoch,self.calendar,END)
        b=self.boundaries[epoch];D=u+1
        gate=(False if b['K_state']=='before_calendar_blocked' or D>=len(self.calendar) else
              D<b['K_index'] if b['K_index'] is not None else self.calendar[D]<b['K_target_date'])
        if original==1 and score>0:self.original_positive.add(seq)
        if original==1 and score>0 and gate:
            if seq not in self.best or self.selector.rank_action(row)<self.selector.rank_action(self.best[seq]):self.best[seq]=dict(row)

    def finish(self,candidate):
        winners=self.selector.family_winners(self.best);rows=[]
        for seq,p in sorted(self.parents.items()):
            proposal=self.best.get(seq);winner=winners.get(seq)
            state=('selected' if winner else 'family_priority_suppressed' if proposal else 'no_observed_children' if seq not in self.observed else
                'no_calendar_eligible_positive_action' if seq in self.original_positive else 'no_original_eligible_positive_action')
            rows.append(dict(p,proposed_action_id=proposal['action_id'] if proposal else '',proposed_epoch=proposal['reference_epoch'] if proposal else '',
                proposed_score=float(proposal['score']) if proposal else np.nan,chosen_action_id=winner['action_id'] if winner else '',
                chosen_action_sequence_index=int(winner['sequence_index']) if winner else -1,chosen_epoch=winner['reference_epoch'] if winner else '',
                anchor_epoch=p['reference_epoch'],score=float(winner['score']) if winner else np.nan,selected=int(winner is not None),selection_state=state,
                scope=self.scope,cutoff=self.selector.cutoff_for(p['u_date']),arm='VOLUNTARY_RESELECT',candidate=candidate,policy='NARROW',account_deadline_certified=False))
        frame=pd.DataFrame(rows)
        if frame.loc[frame.selected.eq(1)].duplicated(['family_id','u_index']).any():raise ValueError('duplicate family action')
        return frame


def paired_held(active,control,labels):
    label=labels.set_index('action_id',verify_integrity=True)
    def values(frame):
        f=frame.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index']).set_index(['family_id','u_index']).sort_index()
        out=[]
        for aid in f.chosen_action_id:
            if not aid:out.append(0.);continue
            if aid not in label.index:out.append(np.nan);continue
            r=label.loc[aid]
            if r.participation_state=='known_nonparticipation':out.append(0.)
            elif r.label_state=='closed_complete_bar_model' and r.label_known_date and r.label_known_date<=END and np.isfinite(r.net_R_stress):out.append(float(r.net_R_stress))
            else:out.append(np.nan)
        return f,np.array(out)
    a,av=values(active);b,bv=values(control)
    if not a.index.equals(b.index) or not a.u_date.equals(b.u_date):raise ValueError('held complete family-u pair differs')
    same=a.chosen_action_id.eq(b.chosen_action_id).to_numpy();known=np.isfinite(av)&np.isfinite(bv)
    delta=np.where(same,0.,np.where(known,av-bv,np.nan));unknown=~same&~known
    f=pd.DataFrame(dict(u_date=a.u_date.to_numpy(),delta_R=delta,known=np.isfinite(delta),unknown=unknown))
    daily=f.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index()
    mean=float(daily.delta_R.mean()) if daily.delta_R.notna().any() else None
    return dict(known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=int(unknown.sum()),
        same_action_cancelled_family_u=int(same.sum()),same_selected_outcome_not_loaded_cancelled=int((same&(a.chosen_action_id.ne('').to_numpy())&~known).sum()),
        full_family_u=len(a),known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(daily.delta_R.notna().sum()),
        unknown_R_bounds=None,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or unknown.any() else 'supported',
        annual=[dict(year=y,mean_delta_R=float(p.delta_R.mean()) if p.delta_R.notna().any() else None,unknown_family_u=int(p.unknown_family_u.sum())) for y,p in daily.groupby(daily.u_date.str[:4])]),daily


def execute_fit(args):
    out,p,pb,sb,ab,bundle=protocol_authorization(args);out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();began=datetime.now(timezone.utc).isoformat();attempted=completed=0;status='failed';error=None;artifacts={};receipts={}
    write_json(out/'started.json',dict(protocol=pb,source_manifest=sb,authorization=ab,source_bundle=bundle,started_at=began,auto_retry=False))
    def progress(phase):checkpoint(out/'progress.json',dict(phase=phase,new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0))
    progress('preparing_sources')
    try:
        inputs=p['input_bindings'];source=read_json(sb)
        if (source.get('schema')!='stage488_pre_fields_manifest_v1' or source.get('protocol_sha256')!=pb['sha256'] or
                'exact_pre_fields' not in source.get('artifacts',{}) or not read_json(source['artifacts']['terminal']).get('completed')):
            raise ValueError('completed488 source manifest required')
        calendar=decode_calendar(np.load(io.BytesIO(read_bytes(inputs['calendar'])),allow_pickle=False))
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('original full calendar required')
        choicesA=read_table(inputs['forward_full_mothers_from156_choices']);mothers=forward_mothers_from_choices(choicesA)
        if mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('complete98/95 forward policy required')
        forward_binding=write_table(out/'forward_mothers_projection.csv.gz',mothers);receipts['forward_mother_reads']=1
        features,event_boundaries=build_features(inputs,source,calendar)
        features,causal_binding,receipts['original_actions']=project_actions_once(inputs['original_actions'],features,out)
        artifacts['event_features_labels']=write_table(out/'event_features_labels.csv.gz',features)
        progress('reading_original_common_once');before=inherited_stat(inputs['original_common'])
        with np.load(inputs['original_common']['path'],allow_pickle=False) as data:
            original=load('stage130_contract_choice_fit.py')
            common_raw=data['common']
            if data['columns'].tolist()!=original.COMMON or common_raw.shape!=(1552456,26):raise ValueError('frozen26 COMMON schema differs')
            event_common=common_raw[features.sequence_index.to_numpy(np.int64)].astype(float)
            del common_raw
        after=inherited_stat(inputs['original_common'])
        if before!=after:raise ValueError('COMMON stat drift')
        receipts['original_COMMON']=dict(reads=1,before=before,after=after,projected_event_rows=len(features))
        np.savez_compressed(out/'event_common26.npz',common=event_common,columns=np.array(original.COMMON),sequence_index=features.sequence_index.to_numpy(np.int64))
        artifacts['event_common26']=binding(out/'event_common26.npz')
        records=inputs['original_models'];heads={};folds=[]
        if {(r['scope'],r['cutoff']) for r in records}!={(s,c) for s in SCOPES for c in CUTOFFS}:raise ValueError('original six model cells required')
        for scope in SCOPES:
            for cutoff in CUTOFFS:
                record=next(r for r in records if r['scope']==scope and r['cutoff']==cutoff)
                base=read_json(record['portable_model']);scaler=read_json(record['scaler'])
                train=training_slice(features,cutoff,scope)
                if train.empty:raise ValueError('no mature training in fixed cell '+scope+' '+cutoff)
                idx=train.index.to_numpy(np.int64);x=original.design(event_common[idx],scaler)
                base_score=x@np.array(base['coef'])+float(base['intercept']);residual=train.net_R_stress.to_numpy(float)-base_score
                weights=equal_event_family_weights(train);train['sample_weight']=weights;train['frozen_base_score']=base_score;train['head_target_residual']=residual
                directory=out/'folds'/scope/cutoff;directory.mkdir(parents=True)
                train_b=write_table(directory/'training_rows_weights.csv.gz',train)
                for arm in ARMS:
                    if attempted>=12:raise ValueError('twelve fit budget exhausted')
                    attempted+=1;progress('fit_running:'+scope+':'+cutoff+':'+arm)
                    head=fit_head(train,residual,weights,arm);completed+=1;head.update(scope=scope,cutoff=cutoff,
                        event_count=int(train.fomc_event_id.nunique()),family_count=int(train.family_id.nunique()),
                        max_training_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),training_binding=train_b,
                        frozen_base_model=record['portable_model'],frozen_base_scaler=record['scaler'],training_residual_is_in_sample_not_crossfit=True)
                    hb=write_json(directory/(arm+'.json'),head);heads[scope,cutoff,arm]=head
                    folds.append(dict(scope=scope,cutoff=cutoff,arm=arm,head=hb,training_rows=train_b));progress('fit_complete:'+arm)
        if (attempted,completed)!=(12,12):raise ValueError('exact12 head fits required')
        artifacts['fit_records']=write_json(out/'fit_records.json',folds)
        features['action_id']=features.action_id.astype(str);feature_by_id=features.set_index('action_id',verify_integrity=True)
        overlays={};overlay_rows=[]
        for scope in SCOPES:
            for cutoff in CUTOFFS:
                domain=features.loc[features.u_date.ge(cutoff)&(features.u_date.lt('2023-01-01') if cutoff=='2020-01-01' else True)&features.feature_mask]
                if scope!='main':domain=domain.loc[domain.family_id.map(family_group).eq(int(scope[-1]))]
                for arm in ARMS:
                    if len(domain):
                        values=predict_head(domain,heads[scope,cutoff,arm])
                        for aid,value in zip(domain.action_id,values):overlays[scope,cutoff,arm,aid]=float(value)
        accum={};parents={}
        for scope in SCOPES:
            parents[scope]=mothers if scope=='main' else mothers.loc[mothers.family_id.map(family_group).eq(int(scope[-1]))]
            for arm in ('A',)+ARMS:accum[scope,arm]=ChoiceAccumulator(parents[scope],calendar,scope)
        scoreb=inputs['original130_scores'];before=inherited_stat(scoreb);counts=Counter();state_counts=Counter();progress('one_original_score_stream')
        with gzip.open(scoreb['path'],'rt',newline='') as stream:
            reader=csv.DictReader(stream)
            if any(c not in reader.fieldnames for c in load('stage156_voluntary_choices.py').SCORE_FIELDS):raise ValueError('original score schema changed')
            for row in reader:
                scope=row['scope'];cutoff=row['cutoff'];aid=row['action_id']
                if scope not in SCOPES or cutoff not in CUTOFFS:raise ValueError('score cell outside fixed original six')
                counts[scope,cutoff]+=1;accum[scope,'A'].observe(row);original_score=float(row['score'])
                audit=None
                for arm in ARMS:
                    key=(scope,cutoff,arm,aid);applied=key in overlays
                    state='applied' if applied else 'field_missing_fallback_A' if aid in feature_by_id.index else 'non_event_fallback_A'
                    candidate=dict(row)
                    if applied:candidate['score']=original_score+overlays[key]
                    accum[scope,arm].observe(candidate);state_counts[scope,arm,state]+=1
                    if aid in feature_by_id.index:
                        if audit is None:audit=dict(row,score_A=original_score)
                        audit['score_'+arm]=float(candidate['score']);audit['head_state_'+arm]=state
                if audit is not None:overlay_rows.append(audit)
        after=inherited_stat(scoreb)
        if before!=after:raise ValueError('original score stat drift')
        if sum(v for (s,c),v in counts.items() if s=='main')!=966740 or sum(counts.values())!=1933480:raise ValueError('complete original main/held score domain differs')
        for cutoff in CUTOFFS:
            if counts['holdout_0',cutoff]+counts['holdout_1',cutoff]!=counts['main',cutoff]:raise ValueError('held scores do not partition original main actions')
        old_records=read_json(inputs['original130_fit_records'])
        if {(r['scope'],r['cutoff']):r['prediction_children'] for r in old_records}!=dict(counts):raise ValueError('exact six original prediction cell counts differ')
        receipts['original_scores']=dict(reads=1,before=before,after=after,rows=sum(counts.values()),cells=[dict(scope=s,cutoff=c,rows=n) for (s,c),n in sorted(counts.items())])
        artifacts['event_score_overlays']=write_table(out/'event_score_overlays.csv.gz',pd.DataFrame(overlay_rows))
        selected={};choice_bindings={};all_boundaries=dict(event_boundaries)
        for scope in SCOPES:
            for arm in ('A',)+ARMS:
                frame=accum[scope,arm].finish(arm);selected[scope,arm]=frame
                choice_bindings[scope,arm]=write_table(out/f'choices_{scope}_{arm}.csv.gz',frame)
                for epoch,b in accum[scope,arm].boundaries.items():
                    if epoch in all_boundaries and all_boundaries[epoch]!=b:raise ValueError('boundary inconsistent across scopes')
                    all_boundaries[epoch]=b
        check=selected['main','A'];old=choicesA.set_index('event_id').reindex(check.event_id)
        if check.chosen_action_id.tolist()!=old.chosen_action_id.tolist():raise ValueError('reused original157 main selection did not reproduce accepted156')
        boundaries_doc=dict(schema='stage156_voluntary_K_only_v1',epochs=all_boundaries,policy_version=load('stage156_voluntary_choices.py').POLICY_VERSION,
            sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False)
        boundaries_binding=write_json(out/'boundaries.json',boundaries_doc)
        contrasts={};held_daily=[]
        for name,active,control in [('B_minus_A',ARMS[0],'A'),('C_minus_A',ARMS[1],'A'),('C_minus_B',ARMS[1],ARMS[0])]:
            groups={}
            for scope in SCOPES[1:]:
                groups[scope],daily=paired_held(selected[scope,active],selected[scope,control],features)
                daily['scope']=scope;daily['contrast']=name;held_daily.append(daily)
            contrasts[name]=dict(groups=groups,unknown_bounds_available=False,full_policy_cash_qualified=False)
        held_doc=dict(schema='stage489_fomc_held_contrasts_v1',contrasts=contrasts,
            not_blind_OOS=True,family_held_shares_same_global_events=True,same_action_cancellation_not_imputation=True)
        held_binding=write_json(out/'held_gate.json',held_doc);artifacts['held_daily']=write_table(out/'held_daily.csv.gz',pd.concat(held_daily,ignore_index=True))
        artifacts.update(forward_mothers_projection=forward_binding,causal_actions_projection=causal_binding,boundaries=boundaries_binding,held_gate=held_binding,calendar=inputs['calendar'])
        for (scope,arm),b in choice_bindings.items():artifacts['choices_'+scope+'_'+arm]=b
        if source_bundle()!=bundle:raise ValueError('source changed during actual')
        receipts.update(new_fit=completed,new_cash=0,original_mother_reads=0,metadata227_reads=0,native_SQL=0,downloads=0,
            source_exact_pre_reads=1,FOMC_raw_reads=1,event_child_reads=1,calendar_reads=1,unaffected_scores_exact_copy=True)
        artifacts['source_read_receipt']=write_json(out/'source_read_receipt.json',receipts)
        summary=dict(status='completed',new_fit=completed,new_cash=0,full_original_mothers_provenance=399252,
            full_original_actions=1552456,forward_parent_rows=len(mothers),forward_products=98,forward_families=95,
            full_forward_main_children=966740,event_rows=len(features),event_numeric_feature_rows=int(features.feature_mask.sum()),
            state_counts=[dict(scope=s,arm=a,state=st,rows=n) for (s,a,st),n in sorted(state_counts.items())],
            choices=[dict(scope=s,candidate=a,parents=len(f),selected=int(f.selected.sum())) for (s,a),f in selected.items()],
            historical_PIT_qualified=False,full_mechanism_identified=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        artifacts['summary']=write_json(out/'summary.json',summary);status='completed';progress('completed')
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=write_json(out/'terminal.json',dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-start,new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0,native_SQL=0,auto_retry=False))
        manifest=dict(schema='stage489_fomc_residual_fit_manifest_v1',status=status,protocol_binding=pb,protocol_sha256=pb['sha256'],
            source_manifest=sb,authorization=ab,source_bundle=bundle,terminal=terminal,artifacts=artifacts,
            new_fits_attempted=attempted,new_fits_completed=completed,new_cash=0,production_qualified=False,goal_complete=False)
        manifest_binding=write_json(out/'manifest.json',manifest)
        if status=='completed':
            handoff=dict(schema='stage489_fomc_residual_cash_handoff_v1',protocol_binding=pb,protocol_sha256=pb['sha256'],
                fit_manifest_binding=manifest_binding,arms={arm:dict(choices_main_binding=choice_bindings['main',arm],held_diagnostic_binding=held_binding) for arm in ARMS},
                causal_actions_projection_binding=causal_binding,forward_mothers_projection_binding=forward_binding,boundaries_binding=boundaries_binding,
                calendar_binding=inputs['calendar'],held_gate_binding=held_binding)
            write_json(out/'cash_handoff.json',handoff)
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    fit=sub.add_parser('fit')
    for name in ['protocol','protocol-sha256','source-manifest','source-manifest-sha256','authorization','authorization-sha256','output']:
        fit.add_argument('--'+name,required=True)
    args=parser.parse_args(argv);print(json.dumps(safe(execute_fit(args)),ensure_ascii=False))


if __name__=='__main__':main()
