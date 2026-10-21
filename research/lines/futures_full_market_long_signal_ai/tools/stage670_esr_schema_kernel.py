"""Frozen669 ESR input-schema recovery; original666 economics and heads unchanged.

This is conditional revised-source research, not historical release/PIT proof.
Original A is supplied as an offset, never refit; no target or stop is rebuilt.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import math
import re
import numpy as np
import pandas as pd

NY=ZoneInfo('America/New_York')
CN=ZoneInfo('Asia/Shanghai')
FEATURES=['Ahat','sin_phase','cos_phase','Ahat*sin_phase','Ahat*cos_phase','Q','Ahat*Q']
ECONOMIC_GROUPS=('corn','soy_complex','upland_cotton')
MAP_FIELDS=['commodity_id','source_id','report_period','available_at_utc','period_valid','phase','netSales','source_reason','weekly_group']
MY_MONTHS={month:i+1 for i,month in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}


def assumed_available_at(period):
    return datetime.combine(date.fromisoformat(str(period))+timedelta(days=14),time.min,NY)


def _finite(value):
    try:v=float(value)
    except (ValueError,TypeError):return np.nan
    return v if math.isfinite(v) else np.nan


def _bool(values):
    s=pd.Series(values)
    if pd.api.types.is_bool_dtype(s):return s.to_numpy(bool)
    return s.astype(str).str.lower().isin(['1','1.0','true']).to_numpy(bool)


def prepare_sources(source_frames,source_specs,clock):
    """Retain every original MYCO row; period group validity is shared."""
    out=[]
    for spec in source_specs:
        cid=int(spec['commodity_id']);frame=source_frames[cid].copy()
        required={'source_row','period_end_date','commodityId','myDefinition','mycoTypeName','weekNumber','netSales'}
        if not required.issubset(frame.columns):raise ValueError('accepted ESR source schema missing')
        if not pd.to_numeric(frame.commodityId,errors='raise').eq(cid).all():raise ValueError('ESR source identity differs')
        counts=frame.groupby('period_end_date',sort=False).size().to_dict()
        for original in frame.to_dict('records'):
            r=dict(original);period=str(r['period_end_date']);pd_date=date.fromisoformat(period)
            phase=np.nan;reason='valid_singleton_Standard';valid=True
            if counts[period]!=1:valid=False;reason='period_group_non_singleton_MYCO'
            elif str(r['mycoTypeName'])!='Standard':valid=False;reason='period_group_not_Standard'
            blackout=any(str(lo)<=period<=str(hi) for lo,hi in clock['blackout_period_end_ranges'])
            match=re.fullmatch(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\s*/\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})',str(r['myDefinition']).strip())
            my_valid=False
            if match:
                month=int(spec['MY_start_month']);y=int(match.group(2))
                my_valid=(MY_MONTHS[match.group(1)]==month and MY_MONTHS[match.group(3)]==(month-2)%12+1 and int(match.group(4))==y+1)
                if my_valid:
                    begin=date(y,month,1);finish=date(y+1,month,1)
                    phase=(pd_date-begin).days/(finish-begin).days
            if not my_valid or not math.isfinite(phase) or not 0<=phase<1:
                valid=False
                if reason=='valid_singleton_Standard':reason='invalid_marketing_year_phase'
            quantity=_finite(r['netSales'])
            if not math.isfinite(quantity):
                valid=False
                if reason=='valid_singleton_Standard':reason='nonfinite_signed_netSales'
            if blackout:
                valid=False
                reason='frozen_period_blackout'
            r.update(netSales_literal=str(original['netSales']),commodity_id=cid,period_end=period,source_id=f'{cid}|{period}',
                available_at_utc=assumed_available_at(period).astimezone(timezone.utc).isoformat(),
                period_group_rows=int(counts[period]),period_valid=bool(valid),phase=phase,
                netSales=quantity,source_reason=reason)
            out.append(r)
    return pd.DataFrame(out)


def build_calendar_map(calendar,sources):
    """Latest eligible period group, including invalid groups; never valid backfill."""
    if calendar!=sorted(set(calendar)):raise ValueError('sorted unique calendar required')
    periods=sorted(set(sources.period_end.astype(str)))
    global_events=[(assumed_available_at(p),p) for p in periods]
    all_groups={}
    for cid,part in sources.groupby('commodity_id',sort=True):
        groups=[]
        for period,g in part.groupby('period_end',sort=True):
            singleton=len(g)==1;r=g.iloc[0]
            groups.append(dict(commodity_id=int(cid),source_id=f'{int(cid)}|{period}',report_period=period,
                available_at_utc=str(r.available_at_utc),period_valid=bool(singleton and _bool(g.period_valid)[0]),
                phase=float(r.phase) if singleton else np.nan,netSales=float(r.netSales) if singleton else np.nan,
                source_reason=str(r.source_reason) if singleton else 'period_group_non_singleton_MYCO',
                source_rows='|'.join(g.source_row.astype(str)),period_group_rows=len(g)))
        groups.sort(key=lambda r:(r['available_at_utc'],r['report_period']))
        all_groups[int(cid)]=groups
    positions={cid:0 for cid in all_groups};latest={cid:None for cid in all_groups};global_at=0;week='';out=[]
    for u,d in enumerate(calendar):
        cutoff=datetime.combine(date.fromisoformat(d),time(15),CN)
        while global_at<len(global_events) and global_events[global_at][0]<=cutoff:
            week=global_events[global_at][1];global_at+=1
        for cid,groups in all_groups.items():
            at=positions[cid]
            while at<len(groups) and datetime.fromisoformat(groups[at]['available_at_utc'])<=cutoff:
                latest[cid]=groups[at];at+=1
            positions[cid]=at
            r=dict(latest[cid]) if latest[cid] is not None else dict(commodity_id=cid,source_id='',report_period='',available_at_utc='',period_valid=False,phase=np.nan,netSales=np.nan,source_reason='no_assumed_available_source',source_rows='',period_group_rows=0)
            r.update(u_index=u,u_date=d,weekly_group=week);out.append(r)
    return pd.DataFrame(out)


def prefix_scales(sources,cutoff):
    bound=datetime.combine(date.fromisoformat(str(cutoff)),time.min,CN)
    result={}
    for cid,part in sources.groupby('commodity_id',sort=True):
        available=part.available_at_utc.map(lambda x:datetime.fromisoformat(str(x))<bound).to_numpy(bool)
        mask=_bool(part.period_valid)&available&np.isfinite(pd.to_numeric(part.netSales,errors='coerce'))
        values=np.abs(part.loc[mask,'netSales'].to_numpy(float))
        scale=float(np.median(values)) if len(values) else np.nan
        supported=bool(math.isfinite(scale) and scale>0)
        result[str(int(cid))]=dict(commodity_id=int(cid),cutoff=str(cutoff),scale=scale if supported else None,supported=supported,prefix_rows=len(values),max_prefix_period=None if not len(values) else str(part.loc[mask,'period_end'].max()),source_only=True,cutoff_strict=True)
    return result


def feature_rows(frame,calendar_map,scales,family_mapping):
    """Return every original action, with shared B/C source support and fallback."""
    original=frame.reset_index(drop=True).copy();fm={r['family_id']:r for r in family_mapping}
    original['commodity_id']=[int(fm[f]['commodity_id']) if f in fm else -1 for f in original.family_id]
    original['economic_group']=[str(fm[f]['economic_group']) if f in fm else '' for f in original.family_id]
    mapping=calendar_map[['u_index','u_date']+MAP_FIELDS].copy()
    if mapping.duplicated(['u_index','u_date','commodity_id']).any():raise ValueError('duplicate fullcalendar/source key')
    linked=original.merge(mapping,on=['u_index','u_date','commodity_id'],how='left',sort=False,validate='many_to_one')
    # Unmapped families still belong to the common weekly event grid.
    week=calendar_map[['u_index','u_date','weekly_group']].drop_duplicates()
    if week.duplicated(['u_index','u_date']).any():raise ValueError('weekly grid not shared across source commodities')
    lookup={(int(r.u_index),str(r.u_date)):str(r.weekly_group) for r in week.itertuples(index=False)}
    keys=[(int(u),str(d)) for u,d in zip(linked.u_index,linked.u_date)]
    if any(key not in lookup for key in keys):raise ValueError('original action date not full calendar')
    linked['weekly_group']=[lookup[key] for key in keys]
    for col in ['source_id','report_period','available_at_utc','source_reason']:
        linked[col]=linked[col].fillna('' if col!='source_reason' else 'unmapped_exact_A')
    linked['period_valid']=_bool(linked.period_valid)
    linked['source_scale']=[scales.get(str(int(cid)),{}).get('scale') for cid in linked.commodity_id]
    scale=pd.to_numeric(linked.source_scale,errors='coerce').to_numpy(float)
    scaleok=np.asarray([scales.get(str(int(cid)),{}).get('supported',False) is True for cid in linked.commodity_id])&np.isfinite(scale)&(scale>0)
    valid=_bool(linked.period_valid)&scaleok
    linked['sourcevalid']=valid
    linked['sin_phase']=np.sin(2*np.pi*pd.to_numeric(linked.phase,errors='coerce'))
    linked['cos_phase']=np.cos(2*np.pi*pd.to_numeric(linked.phase,errors='coerce'))
    q=np.full(len(linked),np.nan);q[valid]=np.arcsinh(linked.loc[valid,'netSales'].to_numpy(float)/scale[valid]);linked['Q']=q
    badscale=linked.commodity_id.ne(-1).to_numpy()&~scaleok
    linked.loc[badscale,'source_reason']=linked.loc[badscale,'source_reason'].astype(str)+'|unsupported_prefix_scale'
    return linked


def source_group_weights(frame,excluded_group=None):
    """Each report period totals1, nested equal economy/source then old weights."""
    result=pd.Series(0.,index=frame.index,dtype=float)
    sw=pd.to_numeric(frame.sample_weight,errors='coerce').to_numpy(float)
    mask=_bool(frame.sourcevalid)&np.isfinite(sw)&(sw>0)&frame.economic_group.ne('').to_numpy()
    if excluded_group is not None:mask&=frame.economic_group.ne(excluded_group).to_numpy()
    part=frame.loc[mask]
    if part.empty:return result
    for _,week in part.groupby('report_period',sort=False):
        groups=list(week.groupby('economic_group',sort=False));ng=len(groups)
        for _,economy in groups:
            sources=list(economy.groupby('commodity_id',sort=False));ns=len(sources)
            for _,source in sources:
                old=source.sample_weight.to_numpy(float)
                result.loc[source.index]=old/old.sum()/ng/ns
    if not np.allclose(result.loc[part.index].groupby(part.report_period).sum(),1.,rtol=0,atol=1e-12):raise ValueError('report periods not totalweight one')
    return result


def raw_design(base,phase,q):
    a=np.asarray(base,float);p=np.asarray(phase,float);q=np.asarray(q,float)
    s=np.sin(2*np.pi*p);c=np.cos(2*np.pi*p)
    return np.column_stack([a,s,c,a*s,a*c,q,a*q])


def fit_heads(train,scope,cutoff,excluded_group=None,on_fit=None):
    weights=source_group_weights(train,excluded_group);active=weights.to_numpy(float)>0
    support=train.loc[active];groups=set(support.economic_group)
    reason='' if len(support) else 'no_positive_common_training_support'
    if excluded_group is not None and not (set(ECONOMIC_GROUPS)-{excluded_group}).issubset(groups):reason='other_two_economic_groups_not_both_supported'
    basic=dict(scope=str(scope),cutoff=str(cutoff),excluded_group=excluded_group,supported=not bool(reason),support_reason=reason,training_rows=len(support),report_periods=int(support.report_period.nunique()),training_economic_groups=sorted(groups),source_counts={str(int(k)):int(v) for k,v in support.commodity_id.value_counts().items()},same_cutoff_Ahat_not_OOF=True,lambda_fixed=1.,base_refits=0)
    if reason:return {arm:dict(basic,arm=arm,feature_names=FEATURES[:n]) for arm,n in [('B',5),('C',7)]}
    raw=raw_design(support.Ahat,support.phase,support.Q);y=support.net_R_stress.to_numpy(float)-support.Ahat.to_numpy(float);w=weights.loc[support.index].to_numpy(float)
    if not np.isfinite(raw).all() or not np.isfinite(y).all():raise ValueError('nonfinite sourcevalid residual inputs')
    mean=np.average(raw,axis=0,weights=w);var=np.average((raw-mean)**2,axis=0,weights=w);scale=np.sqrt(var);scale[scale==0]=1.
    heads={}
    for arm,n in [('B',5),('C',7)]:
        z=np.column_stack([np.ones(len(raw)),(raw[:,:n]-mean[:n])/scale[:n]])
        g=z.T@(w[:,None]*z);rhs=z.T@(w*y);penalty=np.diag([0.]+[1.]*n)
        if on_fit:on_fit(arm)
        beta=np.linalg.solve(g+penalty,rhs)
        heads[arm]=dict(basic,schema='stage667_esr_nested_residual_head_v1',arm=arm,feature_names=FEATURES[:n],feature_mean=mean[:n].tolist(),feature_scale=scale[:n].tolist(),intercept=float(beta[0]),coef=beta[1:].tolist(),weight_sum=float(w.sum()),weighted_target_mean=float(np.average(y,weights=w)),G=g.tolist(),rhs=rhs.tolist(),penalized_normal_equation_residual=float(np.max(np.abs((g+penalty)@beta-rhs))))
    return heads


def predict(frame,head):
    base=frame['Ahat' if 'Ahat' in frame else 'score'].to_numpy(float);out=base.copy()
    valid=_bool(frame.sourcevalid)&bool(head.get('supported',False))
    if valid.any():
        raw=raw_design(base[valid],frame.loc[valid,'phase'],frame.loc[valid,'Q'])[:,:len(head['feature_names'])]
        if not np.isfinite(raw).all():raise ValueError('nonfinite sourcevalid prediction design')
        z=(raw-np.asarray(head['feature_mean']))/np.asarray(head['feature_scale'])
        out[valid]=base[valid]+head['intercept']+z@np.asarray(head['coef'])
    if not np.array_equal(out[~valid].view(np.uint64),base[~valid].view(np.uint64)):raise ValueError('fallback not bitwise originalA')
    if not np.isfinite(out).all():raise ValueError('nonfinite complete forward score')
    return out


def paired_contribution(high_ids,low_ids,high_values,low_values):
    same=np.asarray(high_ids,str)==np.asarray(low_ids,str)
    high=np.asarray(high_values,float);low=np.asarray(low_values,float);both=np.isfinite(high)&np.isfinite(low)
    known=same|both;out=np.full(len(high),np.nan);out[both]=high[both]-low[both];out[same]=0.
    return out,known,same&~both


def shared_bootstrap_indices(groups):
    if not groups:return np.empty((2000,0),dtype=np.int32)
    rng=np.random.default_rng(20261021);starts=rng.integers(0,groups,size=(2000,math.ceil(groups/52)),dtype=np.int64)
    return ((starts[:,:,None]+np.arange(52))%groups).reshape(2000,-1)[:,:groups].astype(np.int32)


def conditional_ci(values,indices):
    a=np.asarray(values,float);known=np.isfinite(a)
    if not len(a):return dict(point=None,low=None,high=None,known_groups=0,missing_groups=0,valid_repetitions=0,conditional_only=True)
    point=float(a[known].mean()) if known.any() else None;draw=a[indices];counts=np.isfinite(draw).sum(axis=1);sums=np.where(np.isfinite(draw),draw,0.).sum(axis=1)
    estimates=np.divide(sums,counts,out=np.full(len(indices),np.nan),where=counts>0);finite=estimates[np.isfinite(estimates)]
    lo,hi=np.quantile(finite,[.025,.975],method='linear') if len(finite) else (None,None)
    return dict(point=point,low=None if lo is None else float(lo),high=None if hi is None else float(hi),known_groups=int(known.sum()),missing_groups=int((~known).sum()),valid_repetitions=len(finite),conditional_only=True)
