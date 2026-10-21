"""Frozen585 pure monthly-source and one-slope residual calculations."""
from collections import Counter
from datetime import date
from decimal import Decimal
import calendar as cal
import math
import numpy as np
import pandas as pd

def shift_month(m,n):
    y,k=map(int,m.split('-'));x=y*12+k-1+n
    return f'{x//12:04d}-{x%12+1:02d}'
def monthend(m):
    y,k=map(int,m.split('-'));return f'{m}-{cal.monthrange(y,k)[1]:02d}'
def regime(m):return 'before2009-07' if m<'2009-07' else '2009-07..2018-02' if m<'2018-03' else '2018-03onward'

def project_source(rows,contract,calendar,end):
    bad=set(contract['bad_year_indices']);week=set(contract['weekend_indices']);conflict=set(contract['conflict_indices'])
    candidates={};states=Counter();quarantine=[]
    for i,r in enumerate(rows):
        try:
            d=date.fromisoformat(r['opendate']);p=Decimal(r['price'])
            state=('bad_year' if i in bad or d.year<1900 else 'weekend' if i in week or d.weekday()>4 else
                   'invalid_price' if not p.is_finite() or p<=0 else 'future_quote' if d.isoformat()>end else 'candidate')
        except (ValueError,KeyError,TypeError,ArithmeticError):state='invalid_date_or_price'
        states[state]+=1
        if state!='candidate':quarantine.append(dict(raw_index=i,state=state,record=r));continue
        candidates.setdefault(d.isoformat()[:7],[]).append((d.isoformat(),i,float(p)))
    if not candidates:raise ValueError('no dated positive weekday candidates')
    months=[];m=min(candidates);last=end[:7]
    while m<=last:
        group=candidates.get(m,[]);selected=max(group,key=lambda x:(x[0],x[1])) if group else None
        state=('incomplete_calendar_month' if monthend(m)>end else 'missing_endpoint' if selected is None else
               'duplicate_last_date' if sum(x[0]==selected[0] for x in group)>1 else 'frozen_conflict' if selected[1] in conflict else 'known')
        months.append(dict(reference_month=m,regime=regime(m),monthend=monthend(m),candidate_rows=len(group),
            endpoint_raw_index=selected[1] if selected else None,quote_date=selected[0] if selected else '',
            price=selected[2] if selected else None,endpoint_state=state));m=shift_month(m,1)
    lookup={x['reference_month']:x for x in months}
    for x in months:
        bm=shift_month(x['reference_month'],-3);b=lookup.get(bm);reason=x['endpoint_state']
        if reason=='known':reason='missing_base_endpoint' if b is None or b['endpoint_state']!='known' else 'cross_regime' if b['regime']!=x['regime'] else 'known'
        x.update(base_month=bm,base_quote_date=b['quote_date'] if b else '',base_price=b['price'] if b else None,
            g=math.log(x['price']/b['price']) if reason=='known' else None,q_state=reason)
    mapped=[]
    for i,u in enumerate(calendar):
        m=shift_month(u[:7],-1);x=lookup.get(m);reason=x['q_state'] if x else 'missing_reference_month'
        if x and (u<=x['monthend'] or (x['quote_date'] and x['quote_date']>x['monthend'])):raise ValueError('future or same-date source consumption')
        mapped.append(dict(u_index=i,u_date=u,u_calendar_month=u[:7],reference_month=m,macro_available=int(reason=='known'),
            g=x['g'] if reason=='known' else None,reason=reason,endpoint_raw_index=x['endpoint_raw_index'] if x else None,
            quote_date=x['quote_date'] if x else '',base_month=x['base_month'] if x else shift_month(m,-3),
            base_quote_date=x['base_quote_date'] if x else '',regime=x['regime'] if x else regime(m)))
    return pd.DataFrame(months),pd.DataFrame(mapped),dict(raw_rows=len(rows),row_states=dict(states),
        quarantined_indices=[x['raw_index'] for x in quarantine],quarantined_rows=quarantine,
        endpoint_selection_before_conflict=True,earlier_endpoint_fallback=False,raw_repair=False,
        publication_clock_certified=False,conditional_later_u_reconstruction=True)

def training_statistics(train,macro,cutoff):
    if train.empty or train.action_id.duplicated().any():raise ValueError('empty or duplicate cached train')
    if not (train.u_action_eligible.eq(1)&train.label_state.eq('closed_complete_bar_model')&train.u_date.lt(cutoff)&train.label_known_date.ne('')&train.label_known_date.lt(cutoff)).all():raise ValueError('original mature own-fold domain differs')
    vals=train[['sample_weight','net_R_stress','Ahat']].to_numpy(float)
    if not np.isfinite(vals).all() or (vals[:,0]<=0).any():raise ValueError('invalid original w/Y/Ahat')
    ids=train.u_index.to_numpy(int)
    if (ids<0).any() or (ids>=len(macro)).any() or not np.array_equal(train.u_date.to_numpy(),macro.u_date.to_numpy()[ids]):raise ValueError('cached train source-u differs')
    source=macro.iloc[ids].reset_index(drop=True);known=source.macro_available.eq(1).to_numpy()
    t=train.loc[known].reset_index(drop=True);s=source.loc[known].reset_index(drop=True)
    M=s.reference_month.nunique();stats=dict(original_rows=len(train),known_rows=len(t),M=M,
        reference_years=int(s.reference_month.str[:4].nunique()),u_years=int(s.u_date.str[:4].nunique()),
        reference_quarters=sorted(set(pd.PeriodIndex(s.reference_month,freq='M').asfreq('Q').astype(str))) if len(s) else [],
        u_quarters=sorted(set(pd.PeriodIndex(s.u_date,freq='D').asfreq('Q').astype(str))) if len(s) else [],
        support_pass=False,feature_mean=None,feature_scale=None,original_known_weight_sum=0.,normalized_weight_sum=0.,G=None,rhs=None)
    columns=['reference_month','u_calendar_month','rows','original_weight_sum','weighted_residual_sum','g']
    if t.empty:return stats,pd.DataFrame(columns=columns)
    q=s.g.to_numpy(float);w=t.sample_weight.to_numpy(float);r=t.net_R_stress.to_numpy(float)-t.Ahat.to_numpy(float)
    if not np.isfinite(q).all():raise ValueError('known training q nonfinite')
    total=float(w.sum());w=w/total;mu=float(w@q);scale=float(np.sqrt(w@((q-mu)**2)))
    stats.update(feature_mean=mu,feature_scale=scale,original_known_weight_sum=total,normalized_weight_sum=float(w.sum()),support_pass=bool(M>=60 and np.isfinite(scale) and scale>0))
    if scale>0:
        z=(q-mu)/scale;X=np.column_stack([np.ones(len(q)),z]);stats.update(G=(X.T@(w[:,None]*X)).tolist(),rhs=(X.T@(w*r)).tolist())
    tmp=pd.DataFrame(dict(reference_month=s.reference_month,u_calendar_month=s.u_date.str[:7],original_weight=t.sample_weight,
        weighted_residual=t.sample_weight*r,g=q))
    months=tmp.groupby(['reference_month','u_calendar_month'],sort=True).agg(rows=('g','size'),original_weight_sum=('original_weight','sum'),weighted_residual_sum=('weighted_residual','sum'),g=('g','first')).reset_index()
    return stats,months[columns]

def fit_models(records,event=None):
    if len(records)!=6 or not all(r['support_pass'] for r in records):raise ValueError('all six preflights required before any solve')
    heads={}
    for r in records:
        for arm in ('B','C'):
            if event:event('attempt',r,arm)
            G=np.ones((1,1)) if arm=='B' else np.array(r['G']);rhs=np.array(r['rhs'])[:len(G)]
            coef=np.linalg.solve(G+np.eye(len(G)),rhs);eig=np.linalg.eigvalsh(G)
            head=dict(scope=r['scope'],cutoff=r['cutoff'],arm=arm,coef=coef.tolist(),G=G.tolist(),rhs=rhs.tolist(),
                ridge_lambda=1.,all_coefficients_penalized=True,feature_mean=r['feature_mean'],feature_scale=r['feature_scale'],
                M=r['M'],normalized_weight_sum=r['normalized_weight_sum'],effective_df=float(np.sum(eig/(eig+1))))
            if not np.isfinite(coef).all():raise ValueError('nonfinite fixed residual head')
            heads[(r['scope'],r['cutoff'],arm)]=head
            if event:event('completed',r,arm)
    return heads

def predict_delta(macro,head):
    known=macro.macro_available.eq(1).to_numpy();delta=np.zeros(len(macro));delta[known]=head['coef'][0]
    if head['arm']=='C':delta[known]+=head['coef'][1]*(macro.loc[known,'g'].to_numpy(float)-head['feature_mean'])/head['feature_scale']
    if not np.isfinite(delta).all():raise ValueError('nonfinite forward offset')
    return delta

def apply_delta(base,delta,available):
    b=np.asarray(base,float);out=b.copy();known=np.asarray(available,bool);out[known]+=np.asarray(delta,float)[known]
    if not np.array_equal(out[~known].view(np.uint64),b[~known].view(np.uint64)):raise ValueError('missing source must preserve A bits')
    return out
