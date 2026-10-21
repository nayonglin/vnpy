"""Stage033 frozen COMMON/ALIGNED/SHUFFLED peer information experiment.

Exactly108 annual Ridge fits, no RFF/SQL/download/account engine. Scope-specific
contexts include strict peer/market exclusion. Saved complete fits support
export-only coefficient replay without estimator fitting.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
for _key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
import sklearn
import scipy
from threadpoolctl import threadpool_info,threadpool_limits
LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage033_peer_alignment_protocol/protocol.json'
PROTOCOL_SHA='6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b'
OWN=['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr','compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
CONTEXT_COLUMNS=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing','peer_count','rho_abs_sum','relation_missing','q_aligned','q_shuffled']
ARMS=('COMMON','ALIGNED','SHUFFLED')
SCOPES=(('main',None),('holdout_0',0),('holdout_1',1))
YEARS=tuple(range(2015,2027))
FIT_CALLS=0
CI_COLUMNS=[f'{arm}_{side}' for arm in ARMS for side in ('lower','upper')]+[f'{contrast}_{side}' for contrast in ('ALIGNED_minus_COMMON','ALIGNED_minus_SHUFFLED','participation') for side in ('lower','upper')]+[f'stress_{arm}_{side}' for arm in ARMS for side in ('lower','upper')]+[f'stress_{contrast}_{side}' for contrast in ('ALIGNED_minus_COMMON','ALIGNED_minus_SHUFFLED','participation') for side in ('lower','upper')]

def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()

def file_binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),sha256=sha_bytes(raw),bytes=len(raw))

def read_bound(binding):
    p=Path(binding['path']);raw=p.read_bytes()
    if sha_bytes(raw)!=binding['sha256'] or ('bytes' in binding and len(raw)!=binding['bytes']):
        raise ValueError('input binding mismatch: '+str(p))
    return raw

def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())

def family_group(family): return int(hashlib.sha256(family.encode()).hexdigest(),16)%2

def training_slice(frame,cutoff,held_group=None):
    use=(frame.feature_ready.eq(1)&frame.label_identified.eq(1)&frame.u_date.ge('2010-01-01')&
         frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff))
    if held_group is not None:use &= frame.family_id.map(family_group).ne(held_group)
    return frame.loc[use].sort_values(['u_date','event_id']).copy()

def test_slice(frame,year,held_group=None):
    use=frame.feature_ready.eq(1)&frame.u_date.str.startswith(str(year))
    if held_group is not None:use &= frame.family_id.map(family_group).eq(held_group)
    return frame.loc[use].sort_values(['u_date','event_id']).copy()

def date_weights(train):
    counts=train.groupby('u_date').size();w=(1./train.u_date.map(counts)).to_numpy(float)
    return w/w.mean()

def interval_product(coefficient,lower,upper):
    a=np.asarray(coefficient);return np.where(a>=0,a*lower,a*upper),np.where(a>=0,a*upper,a*lower)

def finite_mean(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return float(a.mean()) if len(a) else None

def csv_from_binding(binding):
    raw=read_bound(binding)
    if str(binding['path']).endswith('.gz'):raw=gzip.decompress(raw)
    return pd.read_csv(io.BytesIO(raw),dtype=str,keep_default_na=False)


def raw_design(frame,contexts,scope,arm):
    if scope not in ('main','holdout_0','holdout_1') or scope not in contexts:raise ValueError('scope-specific context absent')
    if arm not in ARMS:raise ValueError('invalid arm')
    indices=frame.sequence_index.to_numpy(int)
    if (indices<0).any() or (indices>=len(contexts[scope])).any():raise ValueError('invalid sequence identity')
    context=contexts[scope][indices]
    q=np.zeros(len(frame)) if arm=='COMMON' else context[:,7 if arm=='ALIGNED' else 8]
    result=np.column_stack([frame[OWN].to_numpy(float),context[:,:7],q])
    if result.shape!=(len(frame),19) or not np.isfinite(result).all():raise ValueError('invalid nineteen-slot features')
    return result

def fit_scalers(common18,q_aligned,q_shuffled,weights):
    x=np.asarray(common18,dtype=float);qa=np.asarray(q_aligned,dtype=float);qs=np.asarray(q_shuffled,dtype=float);w=np.asarray(weights,dtype=float)
    if x.shape!=(len(w),18) or qa.shape!=(len(w),) or qs.shape!=(len(w),) or not len(w):raise ValueError('invalid scaler shapes')
    if not all(np.isfinite(v).all() for v in (x,qa,qs,w)) or (w<=0).any():raise ValueError('invalid scaler values')
    mean=np.average(x,axis=0,weights=w);var=np.average((x-mean)**2,axis=0,weights=w)
    qm=float(np.average((qa+qs)/2,weights=w));qv=float(np.average(((qa-qm)**2+(qs-qm)**2)/2,weights=w))
    return dict(common18=dict(mean=mean.tolist(),var=var.tolist(),scale=np.where(var>0,np.sqrt(var),1.).tolist()),
        q=dict(mean=qm,var=qv,scale=math.sqrt(qv) if qv>0 else 1.),weighting='common train/date_equal population; q ALIGNED/SHUFFLED each half weight')

def scale_design(raw,scalers):
    raw=np.asarray(raw,dtype=float)
    common=(raw[:,:18]-np.asarray(scalers['common18']['mean']))/np.asarray(scalers['common18']['scale'])
    q=(raw[:,18]-scalers['q']['mean'])/scalers['q']['scale']
    return np.column_stack([common,q])

def cell_scalers(train,contexts,scope):
    a=raw_design(train,contexts,scope,'ALIGNED');s=raw_design(train,contexts,scope,'SHUFFLED')
    if not np.array_equal(a[:,:18],s[:,:18]):raise ValueError('arms do not share common18')
    return fit_scalers(a[:,:18],a[:,18],s[:,18],date_weights(train))

def fit_one(train,contexts,scope,arm,fit_id,cutoff,held_group,scalers=None):
    global FIT_CALLS
    train=train.sort_values(['u_date','event_id'])
    if train.empty or not train.u_date.lt(cutoff).all() or not train.label_known_date.lt(cutoff).all():raise ValueError('empty/unmatured training')
    if held_group is not None and train.family_id.map(family_group).eq(held_group).any():raise ValueError('held family in train')
    weights=date_weights(train);y=train.proxy_lower.to_numpy(float)
    if not np.isfinite(y).all():raise ValueError('nonfinite target')
    if scalers is None:scalers=cell_scalers(train,contexts,scope)
    x=scale_design(raw_design(train,contexts,scope,arm),scalers)
    with threadpool_limits(limits=1):
        model=Ridge(alpha=1.,solver='cholesky',fit_intercept=True);model.fit(x,y,sample_weight=weights)
    FIT_CALLS+=1
    return dict(fit_id=fit_id,scope=scope,context_scope=scope,arm=arm,cutoff_exclusive=cutoff,heldout_group=held_group,
        training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=sorted(train.family_id.unique()),
        training_ids_sha256=sha_bytes(('\n'.join(train.event_id)+'\n').encode()),training_weights_sha256=sha_bytes(weights.astype('<f8').tobytes()),
        training_sort=['u_date','event_id'],weights_rule='inverse_rows_per_date_normalized_to_mean_one',
        weights_by_date=dict(zip(train.u_date,map(float,weights))),max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
        feature_names=OWN+CONTEXT_COLUMNS[:7]+['q'],scalers=scalers,coef=model.coef_.tolist(),intercept=float(model.intercept_),
        estimator='sklearn.linear_model.Ridge',alpha=1.,solver='cholesky',fit_intercept=True,head_dimension=19,blas_threads=1)

def predict_from_record(record,frame,contexts):
    if record['context_scope']!=record['scope']:raise ValueError('saved scope binding differs')
    x=scale_design(raw_design(frame,contexts,record['context_scope'],record['arm']),record['scalers'])
    with threadpool_limits(limits=1):return x@np.asarray(record['coef'],dtype=float)+float(record['intercept'])

def load_protocol():
    if file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen033 protocol changed')
    p=json.loads(PROTOCOL.read_bytes());read_bound(p['frozen_spec']);read_bound(p['parent_protocol'])
    if p['arms']!=list(ARMS) or p['actual_fit_calls_expected']!=108 or p['gates_count']!=20 or p['context_columns']!=CONTEXT_COLUMNS:raise ValueError('unexpected033 contract')
    return p

def load_inputs(bindings):
    protocol=load_protocol()
    for key in ('data_manifest','data_review'):
        if bindings[key]['sha256']!=protocol[key]['sha256']:raise ValueError('unexpected parent binding '+key)
    parent=json.loads(read_bound(bindings['data_manifest']));review=json.loads(read_bound(bindings['data_review']))
    if review.get('qualified_for_fixed_proxy_experiment') is not True or review['data_manifest']['sha256']!=bindings['data_manifest']['sha256']:raise ValueError('009 fixed-proxy qualification missing')
    frame=csv_from_binding(parent['feature_label_csv'])
    required={'event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status','feature_ready','history_state','label_identified','label_state','label_known_date','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper',*OWN}
    if not required<=set(frame) or len(frame)!=399252 or frame.event_id.duplicated().any() or frame.duplicated(['product_id','u_date']).any():raise ValueError('mother identity/schema differs')
    for col in ('feature_ready','label_identified','path_ambiguous'):
        if not frame[col].isin(['0','1']).all():raise ValueError('nonbinary flag')
        frame[col]=frame[col].astype(int)
    for col in [*OWN,'gross_lower','gross_upper','proxy_lower','proxy_upper']:frame[col]=pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    ready=frame.feature_ready.eq(1);known=frame.label_identified.eq(1)
    if (int(ready.sum()),int(known.sum()),int((ready&~known).sum()))!=(194709,194168,541):raise ValueError('accepted counts changed')
    if not np.isfinite(frame.loc[ready,OWN].to_numpy(float)).all() or (known&~ready).any():raise ValueError('invalid ready feature')
    outcomes=['gross_lower','gross_upper','proxy_lower','proxy_upper']
    if not np.isfinite(frame.loc[known,outcomes].to_numpy(float)).all() or frame.loc[~known,outcomes].notna().any().any():raise ValueError('outcome/unknown contract broken')
    if frame.loc[known,'proxy_lower'].gt(frame.loc[known,'proxy_upper']).any():raise ValueError('inverted interval')
    for side in ('lower','upper'):
        if not np.allclose(frame.loc[known,'gross_'+side]-.2,frame.loc[known,'proxy_'+side],rtol=0,atol=1e-10):raise ValueError('base label cost changed')
    if frame.loc[~known,'label_known_date'].ne('').any() or not frame.loc[known,'label_known_date'].eq(frame.loc[known,'planned_execution_date']).all() or not frame.loc[known,'label_known_date'].gt(frame.loc[known,'u_date']).all():raise ValueError('maturity contract changed')
    if not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all():raise ValueError('family mapping differs')
    context_manifest=json.loads(read_bound(bindings['context_manifest']))
    for key,expected in [('protocol',PROTOCOL_SHA),('parent_manifest',bindings['data_manifest']['sha256']),('parent_review',bindings['data_review']['sha256'])]:
        if context_manifest[key]['sha256']!=expected:raise ValueError('034 parent binding differs '+key)
    dates=parent['source_calendar_scope_dates']
    if dates!=sorted(set(dates)) or len(dates)!=4074 or dates[-1]!='2026-10-16' or context_manifest['source_calendar_scope_dates']!=dates:raise ValueError('source grid changed')
    if not frame.u_date.isin(dates).all():raise ValueError('outer date outside grid')
    ids=csv_from_binding(context_manifest['event_ids_csv'])
    if list(ids.columns)!=['sequence_index','event_id'] or ids.event_id.tolist()!=frame.loc[ready,'event_id'].tolist() or ids.sequence_index.astype(int).tolist()!=list(range(194709)):raise ValueError('context event identity/order differs')
    with np.load(io.BytesIO(read_bound(context_manifest['context_npz'])),allow_pickle=False) as saved:
        if set(saved.files)!={s for s,_ in SCOPES}:raise ValueError('context scope keys differ')
        contexts={scope:saved[scope] for scope,_ in SCOPES}
    for scope,values in contexts.items():
        if values.shape!=(194709,9) or values.dtype.str!='<f8' or not np.isfinite(values).all():raise ValueError('invalid context matrix '+scope)
    if context_manifest['context_npz']['columns']!=CONTEXT_COLUMNS:raise ValueError('context column schema differs')
    frame['sequence_index']=-1;frame.loc[ready,'sequence_index']=np.arange(194709)
    # Drop the old009 global market columns completely; only034 scope context enters X.
    frame=frame[sorted(required)+['sequence_index']]
    return frame,contexts,dates,dict(protocol=protocol,parent_manifest=parent,data_review=review,context_manifest=context_manifest)

def prediction_frame(test,records,contexts,scope,year):
    cols=['event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status','history_state','label_identified','label_state','label_known_date','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper']
    result=test[cols].copy();result['scope']=scope;result['test_year']=year
    for arm in ARMS:
        if records[arm]['scope']!=scope:raise ValueError('prediction scope mismatch')
        result['pred_'+arm]=predict_from_record(records[arm],test,contexts);result['mask_'+arm]=result['pred_'+arm].gt(0).astype(int)
    ctx=contexts[scope][test.sequence_index.to_numpy(int)]
    for j,name in enumerate(CONTEXT_COLUMNS):result[name]=ctx[:,j]
    return result

def save_training_membership(train,directory):
    directory.mkdir(parents=True,exist_ok=False);p=directory/'training_membership.npz'
    np.savez_compressed(p,sequence_index=train.sequence_index.to_numpy(dtype='<i4'),weights=date_weights(train).astype('<f8'))
    return file_binding(p)

def perform_fits(frame,contexts,calendar,out,context_manifest_binding):
    predictions={scope:[] for scope,_ in SCOPES}
    for year in YEARS:
        cutoff=next(d for d in calendar if d.startswith(str(year)))
        for scope,group in SCOPES:
            train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group);scalers=cell_scalers(train,contexts,scope)
            directory=out/'fits'/f'{year}_{scope}';membership=save_training_membership(train,directory);records={}
            for arm in ARMS:
                fit_id=f'{year}_{scope}_{arm}';record=fit_one(train,contexts,scope,arm,fit_id,cutoff,group,scalers)
                record.update(test_year=year,protocol_sha256=PROTOCOL_SHA,training_membership=membership,context_manifest=context_manifest_binding,
                    source_versions=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__))
                write_json(directory/(arm+'.json'),record);records[arm]=record
                print(json.dumps(dict(completed_fit=fit_id,actual_fit_calls=FIT_CALLS,training_rows=len(train),test_rows=len(test))),flush=True)
            predictions[scope].append(prediction_frame(test,records,contexts,scope,year))
    if FIT_CALLS!=108:raise ValueError('expected exactly108 actual fits')
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}

def replay_fits(frame,contexts,calendar,previous):
    if len(list((previous/'fits').glob('*/*.json')))!=108:raise ValueError('incomplete saved108-fit closure')
    predictions={scope:[] for scope,_ in SCOPES}
    for year in YEARS:
        cutoff=next(d for d in calendar if d.startswith(str(year)))
        for scope,group in SCOPES:
            train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group);records={}
            ids_sha=sha_bytes(('\n'.join(train.event_id)+'\n').encode());w=date_weights(train)
            for arm in ARMS:
                record=json.loads((previous/'fits'/f'{year}_{scope}'/(arm+'.json')).read_bytes())
                if record['training_ids_sha256']!=ids_sha or record['training_weights_sha256']!=sha_bytes(w.astype('<f8').tobytes()) or record['cutoff_exclusive']!=cutoff or record['heldout_group']!=group or record['protocol_sha256']!=PROTOCOL_SHA:raise ValueError('saved fit identity differs')
                read_bound(record['context_manifest'])
                with np.load(io.BytesIO(read_bound(record['training_membership'])),allow_pickle=False) as audit:
                    if not np.array_equal(audit['sequence_index'],train.sequence_index.to_numpy(int)) or not np.array_equal(audit['weights'],w):raise ValueError('saved training membership differs')
                records[arm]=record
            predictions[scope].append(prediction_frame(test,records,contexts,scope,year))
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}

def daily_metrics(pred,calendar):
    rows=[]
    for day,g in pred.loc[pred.label_identified.eq(1)].groupby('u_date',sort=True):
        lo=g.proxy_lower.to_numpy(float);hi=g.proxy_upper.to_numpy(float)
        masks={arm:g['pred_'+arm].gt(0).to_numpy(float) for arm in ARMS};row={'u_date':day,'identified_rows':len(g)}
        for arm,mask in masks.items():
            row[arm+'_lower']=float(np.mean(mask*lo));row[arm+'_upper']=float(np.mean(mask*hi))
            row['stress_'+arm+'_lower']=float(np.mean(mask*(lo-.8)));row['stress_'+arm+'_upper']=float(np.mean(mask*(hi-.8)))
            row[arm+'_selection_rate']=float(mask.mean());row[arm+'_mse_proxy_lower']=float(np.mean((g['pred_'+arm].to_numpy(float)-lo)**2))
        for name,coef in [('ALIGNED_minus_COMMON',masks['ALIGNED']-masks['COMMON']),('ALIGNED_minus_SHUFFLED',masks['ALIGNED']-masks['SHUFFLED']),('participation',masks['ALIGNED']-masks['ALIGNED'].mean())]:
            for prefix,l,u in [('',lo,hi),('stress_',lo-.8,hi-.8)]:
                a,b=interval_product(coef,l,u);row[prefix+name+'_lower']=float(a.mean());row[prefix+name+'_upper']=float(b.mean())
        rows.append(row)
    columns=['identified_rows',*CI_COLUMNS,*[arm+'_selection_rate' for arm in ARMS],*[arm+'_mse_proxy_lower' for arm in ARMS]]
    result=pd.DataFrame(rows).set_index('u_date') if rows else pd.DataFrame(columns=columns)
    return result.reindex(pd.Index(calendar,name='u_date'))

def cohort_counts(pred):
    known=pred.label_identified.eq(1);unknown=~known
    result=dict(feature_ready_predictions=len(pred),identified_rows=int(known.sum()),unknown_rows=int(unknown.sum()),unknown_label_states=dict(Counter(pred.loc[unknown,'label_state'])),unknown_rate=finite_mean(unknown))
    for arm in ARMS:
        mask=pred['pred_'+arm].gt(0);selected=known&mask
        result[arm]=dict(all_ready_selection_rate=finite_mean(mask),identified_selection_rate=finite_mean(mask.loc[known]),
            unknown_selection_rate=finite_mean(mask.loc[unknown]),selected_identified_rows=int(selected.sum()),
            selected_identified_dates=int(pred.loc[selected,'u_date'].nunique()),selected_identified_families=int(pred.loc[selected,'family_id'].nunique()),
            selected_unknown_rows=int((mask&unknown).sum()),selected_unknown_dates=int(pred.loc[mask&unknown,'u_date'].nunique()),
            selected_unknown_families=int(pred.loc[mask&unknown,'family_id'].nunique()))
    result['context_coverage']=dict(relation_missing_rate=finite_mean(pred.relation_missing),market_lag_missing_rate=finite_mean(pred.market_lag_missing),mean_peer_count=finite_mean(pred.peer_count),mean_rho_abs_sum=finite_mean(pred.rho_abs_sum))
    return result

def rare_quality_diagnostics(pred):
    known=pred.label_identified.eq(1);result={}
    for arm in ARMS:
        selected=known&pred['pred_'+arm].gt(0);g=pred.loc[selected];n=len(g)
        certain=int(g.label_state.eq('profit_only').sum());ambiguous=int(g.label_state.eq('double_touch_interval').sum())
        result[arm]=dict(selected_identified_rows=n,dates=int(g.u_date.nunique()),families=int(g.family_id.nunique()),
            certain_profit_only_rows=certain,double_touch_rows=ambiguous,target_touch_fraction_lower=certain/n if n else None,
            target_touch_fraction_upper=(certain+ambiguous)/n if n else None,mean_interval_width=finite_mean(g.proxy_upper-g.proxy_lower),
            excluded_certain_profit_only_rows=int((known&~pred['pred_'+arm].gt(0)&pred.label_state.eq('profit_only')).sum()),
            interpretation='diagnostic target-first fraction bounds; not win rate, cash profits or a rare-event threshold')
    return result

def bootstrap_intervals(daily,columns):
    n=len(daily);block=min(60,n)
    if n==0:raise ValueError('empty source grid')
    blocks=math.ceil(n/block);rng=np.random.default_rng(20261018);array=daily[columns].to_numpy(float)
    results=np.full((2000,len(columns)),np.nan);index_hash=hashlib.sha256()
    for i in range(2000):
        starts=rng.integers(0,n-block+1,size=blocks);index=(starts[:,None]+np.arange(block)[None,:]).ravel()[:n]
        index_hash.update(index.astype('<i8').tobytes());chosen=array[index];valid=np.isfinite(chosen);den=valid.sum(axis=0)
        results[i]=np.divide(np.where(valid,chosen,0).sum(axis=0),den,out=np.full(len(columns),np.nan),where=den>0)
    metrics={}
    for j,c in enumerate(columns):
        sample=results[:,j];sample=sample[np.isfinite(sample)];interval=np.quantile(sample,[.025,.975]).tolist() if len(sample) else [None,None]
        metrics[c]=dict(mean=finite_mean(array[:,j]),ci95_lower=interval[0],ci95_upper=interval[1],finite_source_days=int(np.isfinite(array[:,j]).sum()),finite_bootstrap_replicates=len(sample))
    return dict(block_length=60,effective_block_length=block,repetitions=2000,seed=20261018,source_grid_days=n,
        common_indices_sha256=index_hash.hexdigest(),metrics=metrics,uncertainty_scope='fixed predictions only; excludes retraining, research selection and cash uncertainty')

def positive(value):return value is not None and math.isfinite(value) and value>0

def report_predictions(predictions,calendar):
    combined=pd.concat([predictions['holdout_0'],predictions['holdout_1']],ignore_index=True)
    if combined.event_id.duplicated().any():raise ValueError('family holdout predictions overlap')
    reports={};daily_frames={}
    for scope,pred in dict(predictions,holdout_combined=combined).items():
        scope_report={'annual':{}}
        for year in YEARS:
            f=pred.loc[pred.u_date.str.startswith(str(year))];dates=[d for d in calendar if d.startswith(str(year))];d=daily_metrics(f,dates)
            scope_report['annual'][str(year)]=dict(cohort=cohort_counts(f),date_equal_means={c:finite_mean(d[c]) for c in d},source_grid_days=len(dates),no_identified_days=int(d.identified_rows.isna().sum()),rare_quality=rare_quality_diagnostics(f))
        for period,start in [('all_2015','2015-01-01'),('primary_2020','2020-01-01')]:
            f=pred.loc[pred.u_date.ge(start)];dates=[d for d in calendar if d>=start];d=daily_metrics(f,dates);daily_frames[scope+'_'+period]=d
            scope_report[period]=dict(cohort=cohort_counts(f),date_equal_means={c:finite_mean(d[c]) for c in d},source_grid_days=len(dates),no_identified_days=int(d.identified_rows.isna().sum()),rare_quality=rare_quality_diagnostics(f))
            if scope=='main':scope_report[period]['bootstrap']=bootstrap_intervals(d,CI_COLUMNS)
        reports[scope]=scope_report
    primary=reports['main']['primary_2020'];secondary=reports['main']['all_2015'];ci=primary['bootstrap']['metrics'];means=primary['date_equal_means']
    gates={
        'primary_ALIGNED_selected_identified_dates_ge60':primary['cohort']['ALIGNED']['selected_identified_dates']>=60,
        'primary_ALIGNED_selected_identified_families_ge8':primary['cohort']['ALIGNED']['selected_identified_families']>=8,
        'primary_ALIGNED_lower_ci_positive':positive(ci['ALIGNED_lower']['ci95_lower']),
        'primary_ALIGNED_minus_COMMON_lower_ci_positive':positive(ci['ALIGNED_minus_COMMON_lower']['ci95_lower']),
        'primary_ALIGNED_minus_SHUFFLED_lower_ci_positive':positive(ci['ALIGNED_minus_SHUFFLED_lower']['ci95_lower']),
        'primary_participation_lower_ci_positive':positive(ci['participation_lower']['ci95_lower']),
        'same_mask_cost_1R_primary_ALIGNED_lower_positive':positive(means['stress_ALIGNED_lower']),
        'four_complete_years_ALIGNED_minus_COMMON_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['ALIGNED_minus_COMMON_lower']) for y in range(2020,2026))>=4,
        'four_complete_years_ALIGNED_minus_SHUFFLED_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['ALIGNED_minus_SHUFFLED_lower']) for y in range(2020,2026))>=4,
        'partial_2026_ALIGNED_lower_positive':positive(reports['main']['annual']['2026']['date_equal_means']['ALIGNED_lower'])}
    for metric in ('ALIGNED_lower','ALIGNED_minus_COMMON_lower','ALIGNED_minus_SHUFFLED_lower','participation_lower'):
        gates['all_2015_'+metric+'_positive']=positive(secondary['date_equal_means'][metric])
    for group in (0,1):
        for metric in ('ALIGNED_lower','ALIGNED_minus_COMMON_lower','ALIGNED_minus_SHUFFLED_lower'):
            gates[f'holdout_{group}_primary_{metric}_positive']=positive(reports[f'holdout_{group}']['primary_2020']['date_equal_means'][metric])
    if len(gates)!=20:raise ValueError('screen gate closure is not twenty')
    return dict(schema='stage035_fixed_peer_alignment_screen_v1',scopes=reports,gates=gates,quality_information_screen_pass=all(gates.values()),
        information_primary_contrast='ALIGNED-SHUFFLED',selection_mask='score>0',label_metric='date_equal ideal continuous barrier normalized proxy; not account returns',
        participation_diagnostic='ex-post same-day label-identified ALIGNED participation; not u-executable random strategy',
        financial_metrics={k:None for k in ('ending_equity','total_return','max_drawdown','sharpe','total_slippage','total_trades','win_rate')},financial_ready=False,production_qualified=False),daily_frames


def artifacts(out):
    rows=[]
    for p in sorted(out.rglob('*')):
        if not p.is_file() or p.name=='manifest.json':continue
        role='model_artifact' if 'fits' in p.parts else 'qualification_evidence' if p.name=='actual_terminal.json' else 'feature_contract' if p.name in ('protocol.json','input_bindings.json') else 'decision_asset'
        rows.append(dict(file_binding(p),role=role,reproducibility_required=True,raw_ohlc=False))
    return rows

def execute(args):
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('refuse overwrite/repeated fit '+str(out))
    previous=None
    if args.command=='fit':bindings=json.loads(Path(args.bindings).read_bytes())
    else:
        previous=Path(args.experiment).resolve();old=json.loads((previous/'manifest.json').read_bytes())
        if old['source']['sha256']!=file_binding(__file__)['sha256']:raise ValueError('export source differs')
        for item in old['artifacts']:read_bound(item)
        bindings=json.loads((previous/'input_bindings.json').read_bytes())
    out.mkdir(parents=True,exist_ok=False);status='failed';error=None;metrics=None
    try:
        frame,contexts,calendar,evidence=load_inputs(bindings)
        write_json(out/'input_bindings.json',bindings);write_json(out/'protocol.json',evidence['protocol'])
        if args.command=='fit':predictions=perform_fits(frame,contexts,calendar,out,bindings['context_manifest'])
        else:
            predictions=replay_fits(frame,contexts,calendar,previous)
            write_json(out/'replayed_fit_source.json',dict(path=str(previous),saved_fit_records=108,fit_calls_this_command=0))
        metrics,dailies=report_predictions(predictions,calendar)
        metrics['input_states']=dict(all_outer_rows=len(frame),ready=int(frame.feature_ready.sum()),identified=int(frame.label_identified.sum()),ready_unknown=int((frame.feature_ready.eq(1)&frame.label_identified.eq(0)).sum()),label_states=dict(Counter(frame.label_state)))
        for scope,p in predictions.items():p.to_csv(out/f'predictions_{scope}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        for name,d in dailies.items():d.to_csv(out/f'daily_{name}.csv',index=True)
        write_json(out/'metrics.json',metrics);status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'actual_terminal.json',dict(command=args.command,status=status,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,actual_ridge_fit_calls=FIT_CALLS,actual_financial_runs=0,sql_queries=0,network_calls=0,fixture=False,python=sys.executable,numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,platform=platform.platform(),threadpools=threadpool_info(),source=file_binding(__file__)))
    write_json(out/'manifest.json',dict(schema='stage035_fixed_peer_alignment_experiment_v1',status=status,source=file_binding(__file__),tests=file_binding(Path(__file__).with_name('test_stage035_peer_alignment_experiment.py')),protocol=file_binding(PROTOCOL),input_bindings=bindings,artifacts=artifacts(out),actual_fit_calls=FIT_CALLS,saved_fit_records=108,export_only=args.command=='export-only',quality_information_screen_pass=metrics['quality_information_screen_pass'],financial_ready=False,production_qualified=False,financial_runs=0))
    return dict(status=status,actual_fit_calls=FIT_CALLS,output=str(out),quality_information_screen_pass=metrics['quality_information_screen_pass'])

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    fit=sub.add_parser('fit');fit.add_argument('--bindings',required=True);fit.add_argument('--output',required=True)
    replay=sub.add_parser('export-only');replay.add_argument('--experiment',required=True);replay.add_argument('--output',required=True)
    print(json.dumps(execute(p.parse_args()),ensure_ascii=False))
if __name__=='__main__':main()
