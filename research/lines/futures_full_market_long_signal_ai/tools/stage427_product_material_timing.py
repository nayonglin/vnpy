"""Frozen426 pure-X and historical timing diagnostic; no model or cash account."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage426_product_material_timing_protocol/protocol.json'
OUT=LINE/'outputs/stage427_product_material_timing/actual_run1'
MOTHER=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
MEMBERS=['epochs','offsets','days','values','valid']

def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def small_binding(path):
    p=Path(path);b=p.read_bytes();return {'path':str(p.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def stat(ref):
    p=Path(ref['path']);s=p.stat()
    if s.st_size!=ref['bytes'] or s.st_mtime_ns!=ref['mtime_ns']:raise ValueError('input stat differs '+str(p))
    return {'path':str(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino}

def locate(cache,epoch,day):
    if not epoch or epoch not in cache:return None,'missing_epoch'
    days,values,valid=cache[epoch];j=int(np.searchsorted(days,day))
    if j>=len(days) or int(days[j])!=day:return None,'missing_exact_day'
    if not bool(valid[j]):return None,'invalid_bar'
    return (j,values[j]),'known'

def source_return(cache,epoch,u):
    previous,ps=locate(cache,epoch,u-1);current,cs=locate(cache,epoch,u)
    result={'epoch':epoch,'u_index':int(u),'previous_close':None,'u_close':None,'r':None,'state':ps if ps!='known' else cs}
    if previous is not None:result['previous_close']=float(previous[1][3])
    if current is not None:result['u_close']=float(current[1][3])
    if previous is None or current is None:return result
    p,c=result['previous_close'],result['u_close']
    if not np.isfinite([p,c]).all() or min(p,c)<=0:result['state']='nonpositive_or_nonfinite_close';return result
    result['r']=float(np.log(c/p));result['state']='known';return result

def bad_news(rb,hc):
    return None if rb is None or hc is None else .5*(min(rb,0.)+min(hc,0.))

def price_timing(cache,epoch,u):
    r=source_return(cache,epoch,u);d,ds=locate(cache,epoch,u+1)
    result={'epoch':epoch,'previous_close':r['previous_close'],'u_close':r['u_close'],'D_open':None,'D_close':None,
            'own_u':r['r'],'gap':None,'after_open':None,'total':None,'state':r['state'] if r['state']!='known' else ds}
    if d is not None:result['D_open'],result['D_close']=float(d[1][0]),float(d[1][3])
    if r['r'] is None or d is None:return result
    c,o,dc=result['u_close'],result['D_open'],result['D_close']
    if not np.isfinite([c,o,dc]).all() or min(c,o,dc)<=0:result['state']='nonpositive_or_nonfinite_D_price';return result
    result.update(gap=float(np.log(o/c)),after_open=float(np.log(dc/o)),total=float(np.log(dc/c)),state='known')
    if abs(result['total']-result['gap']-result['after_open'])>1e-12:raise ValueError('return decomposition')
    return result

def corr(x,y):
    if len(x)<3:return None
    a=np.asarray(x,float)-np.mean(x);b=np.asarray(y,float)-np.mean(y)
    den=float(np.sqrt(np.dot(a,a)*np.dot(b,b)))
    if den<=0 or not np.isfinite(den):return None
    return float(np.dot(a,b)/den)

def partial_corr(x,y,c):
    if len(x)<4:return None
    matrix=np.cov(np.column_stack([x,y,c]),rowvar=False,ddof=1)
    if not np.isfinite(matrix).all() or matrix[2,2]<=0:return None
    xx=matrix[0,0]-matrix[0,2]**2/matrix[2,2];yy=matrix[1,1]-matrix[1,2]**2/matrix[2,2]
    # Exact collinearity can leave floating roundoff; undefined must remain null.
    if xx<=1e-14*matrix[0,0] or yy<=1e-14*matrix[1,1]:return None
    return float((matrix[0,1]-matrix[0,2]*matrix[1,2]/matrix[2,2])/np.sqrt(xx*yy))

def block_indices(n,length,resamples,seed):
    if n<=0 or length<=0:raise ValueError('invalid block dimensions')
    length=min(n,length);blocks=(n+length-1)//length
    starts=np.random.default_rng(seed).integers(0,n-length+1,size=(resamples,blocks))
    return (starts[:,:,None]+np.arange(length)[None,None,:]).reshape(resamples,-1)[:,:n]

def statistics(data):
    a=np.asarray(data,float);finite=np.isfinite(a).all(axis=1);a=a[finite]
    out={'joint_count':len(a),'nonjoint_count':len(data)-len(a),'q_negative_joint':0,'q_knownzero_joint':0}
    for j,name in enumerate(('gap','after_open','total'),2):
        out[name+'_correlation']=corr(a[:,0],a[:,j]) if len(a) else None
        out[name+'_partial_correlation']=partial_corr(a[:,0],a[:,j],a[:,1]) if len(a) else None
    if len(a):
        negative=a[:,0]<0;zero=a[:,0]==0;out['q_negative_joint']=int(negative.sum());out['q_knownzero_joint']=int(zero.sum())
        out['after_open_knownzero_minus_negative_mean']=float(a[zero,3].mean()-a[negative,3].mean()) if zero.any() and negative.any() else None
    else:out['after_open_knownzero_minus_negative_mean']=None
    return out

def counts(frame):
    q=frame.q.to_numpy(float);return {'all_I_mothers':len(frame),'q_known':int(np.isfinite(q).sum()),'q_negative':int((q<0).sum()),'q_knownzero':int((q==0).sum()),'q_missing':int((~np.isfinite(q)).sum()),'source_states':dict(Counter(frame.source_state)), 'timing_states':dict(Counter(frame.timing_state))}

def summarize(frame,bootstrap):
    fields=['q','own_u','gap','after_open','total'];a=frame[fields].to_numpy(float);result={'counts':counts(frame),'statistics':statistics(a)}
    if bootstrap:
        n=len(frame);indices=block_indices(n,252,2000,20261020)
        keys=[name+suffix for name in ('gap','after_open','total') for suffix in ('_correlation','_partial_correlation')]+['after_open_knownzero_minus_negative_mean']
        reps={k:[] for k in keys}
        for row in indices:
            stats=statistics(a[row])
            for k in keys:reps[k].append(stats[k])
        result['bootstrap']={'resamples':2000,'block_trade_dates':252,'seed':20261020,'calendar_date_count':n,
            'indices_sha256':hashlib.sha256(indices.astype('<i8',copy=False).tobytes()).hexdigest(),'same_indices_all_statistics':True,'statistics':{}}
        for k,values in reps.items():
            known=np.array([v for v in values if v is not None],float)
            result['bootstrap']['statistics'][k]={'lower_2_5':float(np.percentile(known,2.5)) if len(known) else None,'upper_97_5':float(np.percentile(known,97.5)) if len(known) else None,'defined':len(known),'undefined':2000-len(known)}
        result['_replicates']=reps
    return result

def positive(x):return x is not None and x>0

def run_actual():
    if OUT.exists():raise ValueError('fresh output required; no auto retry')
    raw=PROTOCOL.read_bytes();protocol=json.loads(raw)
    if protocol['schema']!='stage426_product_material_price_timing_protocol_v1':raise ValueError('protocol schema')
    OUT.mkdir(parents=True);started=time.monotonic();reads={'mother_full_read':0,'native_npz_open':0,'members':{k:0 for k in MEMBERS}}
    status='failed';failure=None;result={};before={};after={}
    save(OUT/'started.json',{'protocol':small_binding(PROTOCOL),'time_utc':datetime.now(timezone.utc).isoformat()})
    try:
        before={k:stat(v) for k,v in protocol['inputs'].items()}
        reads['mother_full_read']+=1
        mothers=pd.read_csv(protocol['inputs']['mothers']['path'],usecols=MOTHER,dtype={'sequence_index':'int64','u_index':'int64'},keep_default_na=False)[MOTHER]
        if len(mothers)!=399252 or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95 or mothers.product_id.str.split('.').str[0].nunique()!=6:raise ValueError('full mother domain')
        if not np.array_equal(mothers.sequence_index,np.arange(len(mothers))) or mothers.duplicated(['product_id','u_index']).any():raise ValueError('mother identity')
        dates=mothers[['u_index','u_date']].drop_duplicates().sort_values('u_index')
        if dates.u_index.duplicated().any() or dates.u_date.duplicated().any() or not np.array_equal(np.diff(dates.u_index),np.ones(len(dates)-1)):raise ValueError('complete global calendar grid')
        if len(mothers)!=98*len(dates):raise ValueError('all products on entire calendar')
        reads['native_npz_open']+=1
        with np.load(protocol['inputs']['cache']['path'],allow_pickle=False) as z:
            flat={}
            for k in MEMBERS:flat[k]=z[k];reads['members'][k]+=1
        epochs=flat['epochs'].tolist();offsets=flat['offsets'];days=flat['days'];values=flat['values'];valid=flat['valid']
        if len(epochs)!=9520 or len(set(epochs))!=9520 or offsets.shape!=(9521,) or offsets[0]!=0 or offsets[-1]!=1552456 or values.shape!=(1552456,5) or days.shape!=(1552456,) or valid.shape!=(1552456,):raise ValueError('accepted cache dimensions')
        cache={}
        for i,e in enumerate(epochs):
            lo,hi=int(offsets[i]),int(offsets[i+1]);d=days[lo:hi]
            if not len(d) or np.any(np.diff(d)<=0):raise ValueError('native epoch order')
            cache[e]=(d,values[lo:hi],valid[lo:hi])
        representatives={p:mothers.loc[mothers.product_id.eq(p)].set_index('u_index') for p in ('SHFE.RB','SHFE.HC','DCE.I')}
        if any(len(f)!=len(dates) for f in representatives.values()):raise ValueError('source product full domain')
        dayrows=[];facts=[]
        for row in dates.itertuples(index=False):
            u=int(row.u_index);rb=source_return(cache,representatives['SHFE.RB'].loc[u,'reference_epoch'],u);hc=source_return(cache,representatives['SHFE.HC'].loc[u,'reference_epoch'],u)
            q=bad_news(rb['r'],hc['r']);source_state='known' if q is not None else 'RB:'+rb['state']+';HC:'+hc['state']
            d={'u_index':u,'u_date':row.u_date,'q':q,'source_state':source_state}
            for prefix,x in [('RB',rb),('HC',hc)]:
                for k in ('epoch','previous_close','u_close','r','state'):d[prefix+'_'+k]=x[k]
            dayrows.append(d)
            mother=representatives['DCE.I'].loc[u];timing=price_timing(cache,mother.reference_epoch,u)
            facts.append(dict(mother_sequence_index=int(mother.sequence_index),mother_event_id=mother.event_id,product_id='DCE.I',u_index=u,u_date=row.u_date,q=q,source_state=source_state,timing_state=timing.pop('state'),**timing))
        dayframe=pd.DataFrame(dayrows);factframe=pd.DataFrame(facts)
        for frame,name in [(dayframe,'source_day_features.csv.gz'),(factframe,'I_price_timing_facts.csv.gz')]:frame.to_csv(OUT/name,index=False,compression={'method':'gzip','mtime':0})
        qmap=dayframe.set_index('u_index').q;states=dayframe.set_index('u_index').source_state
        projection=mothers[MOTHER].copy();app=projection.product_id.eq('DCE.I');projection['q']=0.;projection['q_state']='structurally_not_applicable'
        projection.loc[app,'q']=projection.loc[app,'u_index'].map(qmap);projection.loc[app,'q_state']=projection.loc[app,'u_index'].map(states)
        projection.to_csv(OUT/'mother_projection.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        yearly={str(year):summarize(group,False) for year,group in factframe.groupby(factframe.u_date.str[:4])}
        eras={};replicates={}
        for name,(begin,end) in protocol['diagnostic']['eras'].items():
            selected=factframe.loc[factframe.u_date.ge(begin)&factframe.u_date.le(end)].copy();eras[name]=summarize(selected,True)
            replicates[name]=eras[name].pop('_replicates')
        keys=['after_open_partial_correlation','after_open_knownzero_minus_negative_mean']
        era_positive=all(positive(eras[e]['statistics'][k]) for e in eras for k in keys)
        ci_positive=all(positive(eras['after_paper']['bootstrap']['statistics'][k]['lower_2_5']) for k in keys)
        passed_years=[y for y in map(str,range(2021,2026)) if all(positive(yearly.get(y,{}).get('statistics',{}).get(k)) for k in keys)]
        year_gate=len(passed_years)*3>=5*2
        known=factframe[['total','gap','after_open']].dropna();maxerror=float(np.max(np.abs(known.total-known.gap-known.after_open))) if len(known) else None
        result={'schema':'stage427_product_material_timing_results_v1','domain':{'mothers':len(mothers),'products':98,'families':95,'exchanges':6,'dates':len(dates),'I_source_counts':counts(factframe),'structurally_not_applicable_mothers':int((~app).sum())},
            'eras':eras,'all_years':yearly,'gate':{'both_eras_two_statistics_positive':era_positive,'after_paper_both_CI_lower_positive':ci_positive,'complete_2021_2025_positive_years':passed_years,'at_least_two_thirds_years':year_gate,'independent_review_complete':False,'numeric_eligible_pending_review':bool(era_positive and ci_positive and year_gate),'financial_authorized':False},
            'return_decomposition_max_abs_error':maxerror,'clock':'historical complete u daily reconstruction; not historical publication certificate','interpretation':'fixed chain timing diagnostic, no strategy/account performance; no causal identification or COMMON52-conditional claim'}
        save(OUT/'results.json',result);save(OUT/'bootstrap_replicates.json',replicates)
        after={k:stat(v) for k,v in protocol['inputs'].items()}
        if before!=after:raise ValueError('source stat changed')
        status='completed'
    except Exception as exc:failure={'type':type(exc).__name__,'message':str(exc)}
    receipt={'schema':'stage427_receipt_v1','status':status,'protocol':small_binding(PROTOCOL),'implementation':small_binding(__file__),'reads':reads,'inputs_before':before,'inputs_after':after,'inputstat_unchanged':before==after and bool(after),'large_input_hashes_recomputed':0,'action_csv_reads':0,'Y_reads':0,'SQL':0,'API':0,'fits':0,'cash':0,'forward_D':0,'account_mutations':0,'failure':failure,'elapsed_seconds':time.monotonic()-started,'completed_at':datetime.now(timezone.utc).isoformat()}
    save(OUT/'receipt.json',receipt);save(OUT/'terminal.json',{'status':status,'exit_code':0 if status=='completed' else 1,'failure':failure,'elapsed_seconds':receipt['elapsed_seconds']})
    save(OUT/'manifest.json',{'status':status,'protocol':small_binding(PROTOCOL),'artifacts':{p.name:small_binding(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}})
    if failure:raise RuntimeError(str(failure))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true',required=True);parser.parse_args()
    result=run_actual();print(json.dumps({'status':'completed','gate':result['gate'],'domain':result['domain']},ensure_ascii=False))
