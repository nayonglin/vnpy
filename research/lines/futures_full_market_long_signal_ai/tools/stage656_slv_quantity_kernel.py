"""Pure frozen653 SLV clock, nested residual heads and conditional statistics.

Importing this module performs no file IO or historical fit. All data is supplied
by the one-pass runner. Same-cutoff base Ahat is not an OOF/DML prediction.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import math
import numpy as np
import pandas as pd

NY=ZoneInfo('America/New_York')
CN=ZoneInfo('Asia/Shanghai')
FEATURES=['Ahat','P','Ahat*P','Q','Ahat*Q']
SCOPES=('main','holdout_0','holdout_1')
ARMS=('A','B','C')
CONTRASTS={'C_minus_B':('C','B'),'C_minus_A':('C','A'),'B_minus_A':('B','A')}
MAP_COLUMNS=['u_index','u_date','source_id','source_date','previous_date','available_at_utc','P','Q','pair_valid','source_reason']


def assumed_available_at(asof):
    """Next two full Mon-Fri dates then next date00NY, without exchange holidays."""
    d=date.fromisoformat(str(asof));count=0
    while count<2:
        d+=timedelta(days=1)
        count+=d.weekday()<5
    return datetime.combine(d+timedelta(days=1),time.min,NY)


def positive_number(value):
    try:v=float(value)
    except (ValueError,TypeError):return None
    return v if math.isfinite(v) and v>0 else None


def build_source_pairs(rows):
    original=pd.DataFrame(rows).copy()
    if original.empty or original.date.duplicated().any():raise ValueError('nonempty unique accepted source dates required')
    source=original.sort_values(['date','source_row_1based'],kind='stable').to_dict('records');out=[]
    previous=None
    for raw in source:
        r=dict(raw);d=str(r['date']);date.fromisoformat(d)
        available=assumed_available_at(d).astimezone(timezone.utc).isoformat()
        prior=str(previous['date']) if previous else ''
        numbers=[positive_number(x.get(k)) if x is not None else None for x,k in [(r,'shares_outstanding_parsed'),(previous,'shares_outstanding_parsed'),(r,'nav_per_share_literal'),(previous,'nav_per_share_literal')]]
        valid=all(v is not None for v in numbers)
        q=math.log(numbers[0]/numbers[1]) if valid else np.nan
        p=math.log(numbers[2]/numbers[3]) if valid else np.nan
        r.update(source_id=d+'|'+prior,source_date=d,previous_date=prior,previous_source_row_1based=str(previous['source_row_1based']) if previous else '',available_at_utc=available,P=p,Q=q,pair_valid=valid,source_reason='valid_adjacent_pair' if valid else 'no_original_previous_row' if previous is None else 'adjacent_original_four_values_not_positive_finite')
        out.append(r);previous=raw
    return pd.DataFrame(out)


def map_source_to_calendar(pairs,calendar):
    records=pairs.to_dict('records')
    records.sort(key=lambda r:(datetime.fromisoformat(r['available_at_utc']),r['source_date'],int(r['source_row_1based'])))
    out=[];at=0;latest=None
    for u,d in enumerate(calendar):
        cutoff=datetime.combine(date.fromisoformat(d),time(15),CN)
        while at<len(records) and datetime.fromisoformat(records[at]['available_at_utc'])<=cutoff:
            latest=records[at];at+=1
        r={k:latest[k] for k in MAP_COLUMNS if k not in ('u_index','u_date')} if latest else dict(source_id='',source_date='',previous_date='',available_at_utc='',P=np.nan,Q=np.nan,pair_valid=False,source_reason='no_assumed_available_source')
        r.update(u_index=u,u_date=d);out.append(r)
    return pd.DataFrame(out,columns=MAP_COLUMNS)


def source_group_weights(sample_weight,source_id):
    w=np.asarray(sample_weight,float);ids=np.asarray(source_id,str)
    if not len(w) or not np.isfinite(w).all() or (w<=0).any() or (ids=='').any():raise ValueError('positive finite weights and nonempty source identities required')
    _,inverse=np.unique(ids,return_inverse=True);total=np.bincount(inverse,weights=w)
    result=w/total[inverse]
    if not np.allclose(np.bincount(inverse,weights=result),1.,rtol=0,atol=1e-12):raise ValueError('source groups not normalized to one')
    return result


def raw_design(base,p,q):
    a=np.asarray(base,float);p=np.asarray(p,float);q=np.asarray(q,float)
    return np.column_stack([a,p,a*p,q,a*q])


def fit_heads(train,scope,cutoff,on_fit=None):
    support=train.loc[train.pair_valid.astype(bool)].copy()
    if support.empty:raise ValueError('no common source support; cannot fit either arm')
    raw=raw_design(support.Ahat,support.P,support.Q)
    y=support.net_R_stress.to_numpy(float)-support.Ahat.to_numpy(float)
    if not np.isfinite(raw).all() or not np.isfinite(y).all():raise ValueError('nonfinite common residual fit inputs')
    w=source_group_weights(support.sample_weight,support.source_id);M=int(support.source_id.nunique())
    mean=np.average(raw,axis=0,weights=w);variance=np.average((raw-mean)**2,axis=0,weights=w)
    scale=np.sqrt(variance);scale[scale==0]=1.
    heads={}
    for arm,n in [('B',3),('C',5)]:
        if on_fit:on_fit(arm)
        z=np.column_stack([np.ones(len(raw)),(raw[:,:n]-mean[:n])/scale[:n]])
        G=z.T@(w[:,None]*z);rhs=z.T@(w*y);penalty=np.diag([0.]+[1.]*n)
        beta=np.linalg.solve(G+penalty,rhs)
        heads[arm]=dict(schema='stage656_nested_residual_head_v1',scope=scope,cutoff=cutoff,arm=arm,feature_names=FEATURES[:n],feature_mean=mean[:n].tolist(),feature_scale=scale[:n].tolist(),intercept=float(beta[0]),coef=beta[1:].tolist(),lambda_fixed=1.,training_rows=len(support),source_groups=M,weight_sum=float(w.sum()),weighted_target_mean=float(np.average(y,weights=w)),G=G.tolist(),rhs=rhs.tolist(),penalized_normal_equation_residual=float(np.max(np.abs((G+penalty)@beta-rhs))),same_cutoff_Ahat_not_OOF=True)
    return heads


def predict_scores(base,p,q,pair_valid,head):
    a=np.asarray(base,float);active=np.asarray(pair_valid,bool);score=a.copy()
    if active.any():
        raw=raw_design(a[active],np.asarray(p,float)[active],np.asarray(q,float)[active])[:,:len(head['feature_names'])]
        if not np.isfinite(raw).all():raise ValueError('valid pair contains nonfinite prediction slope')
        z=(raw-np.asarray(head['feature_mean']))/np.asarray(head['feature_scale'])
        score[active]=a[active]+head['intercept']+z@np.asarray(head['coef'])
    if not np.array_equal(score[~active].view(np.uint64),a[~active].view(np.uint64)):raise ValueError('invalid source not bitwise original A fallback')
    if not np.isfinite(score).all():raise ValueError('nonfinite full-domain score')
    return score


def _bool(series):
    if pd.api.types.is_bool_dtype(series):return series.to_numpy(bool)
    return series.astype(str).str.lower().isin(['1','true','1.0']).to_numpy(bool)


def _mean(values):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    return float(a.mean()) if len(a) else None


def _circular_indices(G):
    if not G:return np.empty((2000,0),dtype=np.int32)
    rng=np.random.default_rng(20261021)
    starts=rng.integers(0,G,size=(2000,math.ceil(G/252)),dtype=np.int64)
    return ((starts[:,:,None]+np.arange(252))%G).reshape(2000,-1)[:,:G].astype(np.int32)


def _conditional_ci(values,indices):
    values=np.asarray(values,float);known=np.isfinite(values);point=_mean(values)
    if not len(values):return dict(point=None,low=None,high=None,known_groups=0,missing_groups=0,valid_repetitions=0)
    draws=values[indices];counts=np.isfinite(draws).sum(axis=1);sums=np.where(np.isfinite(draws),draws,0.).sum(axis=1)
    estimates=np.divide(sums,counts,out=np.full(2000,np.nan),where=counts>0);finite=estimates[np.isfinite(estimates)]
    ci=np.quantile(finite,[.025,.975],method='linear').tolist() if len(finite) else [None,None]
    return dict(point=point,low=ci[0],high=ci[1],known_groups=int(known.sum()),missing_groups=int((~known).sum()),valid_repetitions=len(finite),conditional_only=True)


def policy_statistics(choices,forward,source_map,calendar,end='2026-10-16'):
    """Full mother own/paired contributions; no fit or raw-data IO.

    An explicit flat is known zero; identical-action paired difference is zero
    even when its own outcome is unknown. Different unknown actions stay NaN.
    """
    cs=choices.copy();identity=['scope','cutoff','action_id'];labels=['label_state','participation_state','net_R_stress','label_known_date']
    lf=forward[identity+labels].copy()
    if lf.duplicated(identity).any():raise ValueError('duplicate forward scope/cutoff/action')
    lf=lf.rename(columns={'action_id':'chosen_action_id'})
    cs=cs.merge(lf,on=['scope','cutoff','chosen_action_id'],how='left',validate='many_to_one')
    # Do not trust a prejoined source to replace the original mother-u identity.
    for col in ['source_id','source_date','pair_valid']:
        if col in cs:cs=cs.drop(columns=[col])
    cs=cs.merge(source_map[['u_index','u_date','source_id','source_date','pair_valid']],on=['u_index','u_date'],how='left',validate='many_to_one')
    if cs.source_id.isna().any():raise ValueError('mother outside immutable source calendar')
    cs['era']=np.where(cs.u_date.lt('2023-01-01'),'early','late');cs['year']=cs.u_date.str[:4]
    selected=_bool(cs.selected);closed=cs.label_state.eq('closed_complete_bar_model').to_numpy();known_date=cs.label_known_date.fillna('').astype(str)
    mature=known_date.str.fullmatch(r'\d{4}-\d{2}-\d{2}').to_numpy()&known_date.le(end).to_numpy()
    y=pd.to_numeric(cs.net_R_stress,errors='coerce').to_numpy(float);nonpart=cs.participation_state.eq('known_nonparticipation').to_numpy()
    ownknown=(~selected)|nonpart|(closed&mature&np.isfinite(y));contribution=np.full(len(cs),np.nan)
    contribution[(~selected)|nonpart]=0.;contribution[selected&closed&mature&np.isfinite(y)&~nonpart]=y[selected&closed&mature&np.isfinite(y)&~nonpart]
    cs['own_known']=ownknown;cs['own_unknown']=~ownknown;cs['contribution']=contribution
    if cs.duplicated(['scope','arm','event_id']).any():raise ValueError('duplicate full mother choices')
    one=cs[['scope','event_id','u_date','u_index','family_id','product_id','era','year','source_id','source_date']].drop_duplicates(['scope','event_id'])
    pair=one.copy()
    for arm in ARMS:
        armrows=cs.loc[cs.arm.eq(arm),['scope','event_id','chosen_action_id','contribution','own_known','selected']].rename(columns={k:arm+'_'+k for k in ['chosen_action_id','contribution','own_known','selected']})
        pair=pair.merge(armrows,on=['scope','event_id'],how='left',validate='one_to_one')
    for contrast,(hi,lo) in CONTRASTS.items():
        same=pair[hi+'_chosen_action_id'].fillna('').eq(pair[lo+'_chosen_action_id'].fillna('')).to_numpy()
        both=np.isfinite(pair[hi+'_contribution'])&np.isfinite(pair[lo+'_contribution'])
        values=(pair[hi+'_contribution']-pair[lo+'_contribution']).to_numpy(float);values[same]=0.
        identified=same|both
        pair[contrast]=np.where(identified,values,np.nan);pair[contrast+'_same_action_unknown']=same&~both
    # One complete source grid per era is shared by every scope and arm.
    used=source_map.loc[source_map.u_index.isin(one.u_index.unique())].copy();used['era']=np.where(used.u_date.lt('2023-01-01'),'early','late')
    grids={era:used.loc[used.era.eq(era),'source_id'].drop_duplicates().tolist() for era in ['early','late']}
    indices={era:_circular_indices(len(grid)) for era,grid in grids.items()}
    grouped=[]
    for scope in SCOPES:
        for era,grid in grids.items():
            own=cs.loc[cs.scope.eq(scope)&cs.era.eq(era)];pr=pair.loc[pair.scope.eq(scope)&pair.era.eq(era)]
            byown={key:g for key,g in own.groupby(['arm','source_id'],sort=False)};bypr={sid:g for sid,g in pr.groupby('source_id',sort=False)}
            for sid in grid:
                row=dict(scope=scope,era=era,source_id=sid)
                for arm in ARMS:
                    part=byown.get((arm,sid));n=0 if part is None else len(part);nk=0 if part is None else int(part.own_known.sum())
                    row.update({arm+'_mothers':n,arm+'_selected':0 if part is None else int(_bool(part.selected).sum()),arm+'_mean':np.nan if not nk else float(part.contribution.mean()),arm+'_known':nk,arm+'_unknown':n-nk})
                part=bypr.get(sid)
                for contrast in CONTRASTS:
                    n=0 if part is None else len(part);known=0 if part is None else int(np.isfinite(part[contrast]).sum())
                    row.update({contrast+'_mean':np.nan if not known else float(part[contrast].mean()),contrast+'_identified':known,contrast+'_unknown':n-known,contrast+'_same_action_unknown':0 if part is None else int(part[contrast+'_same_action_unknown'].sum())})
                grouped.append(row)
    groups=pd.DataFrame(grouped);summary=dict(conditional_only=True,fullE_identified=False,bootstrap=dict(seed=20261021,block_length=252,repetitions=2000,each_era_seed_reset=True,source_group_grid_shared_all_scopes=True,missing_group_handling='NaN group remains missing; average only finite sampled conditional group means; no unknown outcome filled zero'),scope_era={})
    for scope in SCOPES:
        summary['scope_era'][scope]={}
        for era,grid in grids.items():
            g=groups.loc[groups.scope.eq(scope)&groups.era.eq(era)].set_index('source_id').reindex(grid)
            metrics={name:_conditional_ci(g[name].to_numpy(float),indices[era]) for name in ['A_mean','B_mean','C_mean']+[x+'_mean' for x in CONTRASTS]}
            summary['scope_era'][scope][era]=dict(source_groups=len(grid),metrics=metrics)
    def positive(scope,era,metric,stat):
        v=summary['scope_era'][scope][era]['metrics'][metric][stat]
        return v is not None and v>0
    gate=dict(main_C_minus_B_CI_low_positive_both_eras=all(positive('main',e,'C_minus_B_mean','low') for e in grids),held0_held1_C_minus_B_point_positive_all4=all(positive(s,e,'C_minus_B_mean','point') for s in SCOPES[1:] for e in grids),C_knownconditional_own_mean_positive_all6=all(positive(s,e,'C_mean','point') for s in SCOPES for e in grids),main_C_knownconditional_own_CI_low_positive_both_eras=all(positive('main',e,'C_mean','low') for e in grids))
    gate['passed']=all(gate.values());gate['new_cash_authorized']=False;gate['fullE_qualified']=False
    # Squared errors use exactly the same original eligible/mature action mask.
    ff=forward.copy();ff=ff.merge(source_map[['u_index','u_date','source_id']],on=['u_index','u_date'],how='left',validate='many_to_one') if 'source_id' not in ff else ff
    fy=pd.to_numeric(ff.net_R_stress,errors='coerce');kd=ff.label_known_date.fillna('').astype(str)
    fm=_bool(ff.u_action_eligible)&ff.label_state.eq('closed_complete_bar_model').to_numpy()&kd.str.fullmatch(r'\d{4}-\d{2}-\d{2}').to_numpy()&kd.le(end).to_numpy()&np.isfinite(fy)
    mse=[]
    if all(k in ff for k in ['score','B_score','C_score']):
        ff=ff.loc[fm].copy();ff['era']=np.where(ff.u_date.lt('2023-01-01'),'early','late')
        for arm,col in [('A','score'),('B','B_score'),('C','C_score')]:ff['squared_error_'+arm]=(pd.to_numeric(ff[col])-pd.to_numeric(ff.net_R_stress))**2
        for key,g in ff.groupby(['scope','era','source_id'],sort=True):mse.append(dict(scope=key[0],era=key[1],source_id=key[2],known_action_rows=len(g),**{arm+'_MSE':float(g['squared_error_'+arm].mean()) for arm in ARMS}))
    annual=[];family=[];families=sorted(cs.family_id.unique())
    for scope in SCOPES:
        for arm in ARMS:
            own=cs.loc[cs.scope.eq(scope)&cs.arm.eq(arm)]
            for year in [str(y) for y in range(2020,2027)]:
                part=own.loc[own.year.eq(year)]
                values=part.groupby('source_id',sort=False).contribution.mean()
                annual.append(dict(scope=scope,arm=arm,year=year,mothers=len(part),selected=int(_bool(part.selected).sum()),known=int(part.own_known.sum()),unknown=int(part.own_unknown.sum()),source_groups=int(part.source_id.nunique()),knownconditional_source_equal_mean=_mean(values)))
                for fid in families:
                    f=part.loc[part.family_id.eq(fid)];means=f.groupby('source_id',sort=False).contribution.mean()
                    family.append(dict(scope=scope,arm=arm,year=year,family_id=fid,mothers=len(f),selected=int(_bool(f.selected).sum()),known=int(f.own_known.sum()),unknown=int(f.own_unknown.sum()),source_groups=int(f.source_id.nunique()),knownconditional_source_equal_mean=_mean(means)))
    return dict(choices=cs,group_stats=groups,action_MSE=pd.DataFrame(mse),annual=pd.DataFrame(annual),family_coverage=pd.DataFrame(family),indices=indices,grids=grids,summary=summary,gate=gate)
