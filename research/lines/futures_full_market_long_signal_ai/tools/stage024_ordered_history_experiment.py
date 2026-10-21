"""Frozen Stage022 S/ORDER/BAG information screen; not an account backtest.

The fit command executes the fixed 108 annual models. Individual fit records
survive an interrupted export; export-only requires all 108 records and never
calls Ridge.fit. No data download or SQLite access.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
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
from threadpoolctl import threadpool_info, threadpool_limits

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage022_ordered_history_protocol/protocol.json'
PROTOCOL_SHA='ae0708cb9eb232d5c5d7936fc705f77b2f361e4b039442e707b82c828b27f99a'
OWN=['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
     'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
ARMS=('S','ORDER','BAG')
SCOPES=(('main',None),('holdout_0',0),('holdout_1',1))
YEARS=tuple(range(2015,2027))
FIT_CALLS=0
CI_COLUMNS=[f'{arm}_{side}' for arm in ARMS for side in ('lower','upper')]+[
    f'{contrast}_{side}' for contrast in ('ORDER_minus_S','ORDER_minus_BAG','participation') for side in ('lower','upper')]+[
    f'stress_{arm}_{side}' for arm in ARMS for side in ('lower','upper')]+[
    f'stress_{contrast}_{side}' for contrast in ('ORDER_minus_S','ORDER_minus_BAG','participation') for side in ('lower','upper')]

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
def canonical_bag(sequence):
    q=np.asarray(sequence,dtype=float)
    indices=np.lexsort((q[:,:,3],q[:,:,2],q[:,:,1],q[:,:,0]),axis=1)
    return np.take_along_axis(q,indices[:,:,None],axis=1)
def fit_scalers(summary,sequence,weights):
    s=np.asarray(summary,dtype=float);q=np.asarray(sequence,dtype=float);w=np.asarray(weights,dtype=float)
    if s.shape!=(len(w),11) or q.shape!=(len(w),20,4) or len(w)==0:raise ValueError('bad scaler shape')
    if not np.isfinite(s).all() or not np.isfinite(q).all() or not np.isfinite(w).all() or (w<=0).any():raise ValueError('invalid scaler input')
    sm=np.average(s,axis=0,weights=w);sv=np.average((s-sm)**2,axis=0,weights=w)
    qm=np.average(q.mean(axis=1),axis=0,weights=w)
    qv=np.average(((q-qm)**2).mean(axis=1),axis=0,weights=w)
    return {'S':{'mean':sm.tolist(),'var':sv.tolist(),'scale':np.where(sv>0,np.sqrt(sv),1.).tolist()},
        'block':{'mean':qm.tolist(),'var':qv.tolist(),'scale':np.where(qv>0,np.sqrt(qv),1.).tolist()},
        'weighting':'train_date_equal_population; pooled_four_channels_weight_over_twenty'}
def make_mapping():
    rng=np.random.default_rng(20261018)
    return {'W_base':rng.normal(size=(91,128)),'b':rng.uniform(0,2*np.pi,size=128)}
def feature_head(summary,sequence,arm,scalers,mapping):
    if arm not in ARMS:raise ValueError('unknown arm')
    s=(np.asarray(summary,dtype=float)-np.asarray(scalers['S']['mean']))/np.asarray(scalers['S']['scale'])
    if arm=='S':z=s;active=11
    else:
        q=np.asarray(sequence,dtype=float)
        if arm=='BAG':q=canonical_bag(q)
        q=(q-np.asarray(scalers['block']['mean']))/np.asarray(scalers['block']['scale'])
        z=np.column_stack([s,q.reshape(len(q),80)]);active=91
    phi=np.sqrt(2/128)*np.cos(z@(mapping['W_base'][:active]/np.sqrt(active))+mapping['b'])
    result=np.column_stack([s,phi])
    if result.shape!=(len(s),139) or not np.isfinite(result).all():raise ValueError('invalid head features')
    return result
def fit_one(train,ordered,arm,fit_id,cutoff,held_group,mapping):
    global FIT_CALLS
    if train.empty or not train.u_date.lt(cutoff).all() or not train.label_known_date.lt(cutoff).all():raise ValueError('empty or unmatured training input')
    if held_group is not None and train.family_id.map(family_group).eq(held_group).any():raise ValueError('held family entered training')
    train=train.sort_values(['u_date','event_id']);s=train[OWN].to_numpy(float);q=ordered[train.sequence_index.to_numpy(int)]
    weights=date_weights(train);y=train.proxy_lower.to_numpy(float)
    if not np.isfinite(y).all():raise ValueError('nonfinite target')
    scalers=fit_scalers(s,q,weights)
    with threadpool_limits(limits=1):
        head=feature_head(s,q,arm,scalers,mapping);model=Ridge(alpha=1.,solver='cholesky',fit_intercept=True)
        model.fit(head,y,sample_weight=weights)
    FIT_CALLS+=1
    return dict(fit_id=fit_id,arm=arm,cutoff_exclusive=cutoff,heldout_group=held_group,
        training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=sorted(train.family_id.unique()),
        training_ids=train.event_id.tolist(),training_weights=weights.tolist(),
        training_ids_sha256=sha_bytes(('\n'.join(train.event_id)+'\n').encode()),
        training_weights_sha256=sha_bytes(weights.astype('<f8').tobytes()),training_sort=['u_date','event_id'],
        weights_rule='inverse_rows_per_date_normalized_to_mean_one',weights_by_date=dict(zip(train.u_date,map(float,weights))),
        max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),feature_names=OWN,
        scalers=scalers,coef=model.coef_.tolist(),intercept=float(model.intercept_),estimator='sklearn.linear_model.Ridge',
        alpha=1.,solver='cholesky',fit_intercept=True,active_dimension=11 if arm=='S' else 91,head_dimension=139,
        rff_dimensions=128,bandwidth='gamma=1/(2*d_active)',blas_threads=1)
def predict_from_record(record,frame,ordered,mapping):
    with threadpool_limits(limits=1):
        head=feature_head(frame[OWN].to_numpy(float),ordered[frame.sequence_index.to_numpy(int)],record['arm'],record['scalers'],mapping)
        return head@np.asarray(record['coef'],dtype=float)+float(record['intercept'])
def interval_product(coefficient,lower,upper):
    a=np.asarray(coefficient);return np.where(a>=0,a*lower,a*upper),np.where(a>=0,a*upper,a*lower)
def daily_metrics(pred,calendar):
    rows=[]
    for day,g in pred.loc[pred.label_identified.eq(1)].groupby('u_date',sort=True):
        lo=g.proxy_lower.to_numpy(float);hi=g.proxy_upper.to_numpy(float)
        masks={arm:g['pred_'+arm].gt(0).to_numpy(float) for arm in ARMS};row={'u_date':day,'identified_rows':len(g)}
        for arm,mask in masks.items():
            row[arm+'_lower']=float(np.mean(mask*lo));row[arm+'_upper']=float(np.mean(mask*hi))
            row['stress_'+arm+'_lower']=float(np.mean(mask*(lo-.8)));row['stress_'+arm+'_upper']=float(np.mean(mask*(hi-.8)))
            row[arm+'_selection_rate']=float(mask.mean());row[arm+'_mse_proxy_lower']=float(np.mean((g['pred_'+arm].to_numpy(float)-lo)**2))
        for name,coef in [('ORDER_minus_S',masks['ORDER']-masks['S']),('ORDER_minus_BAG',masks['ORDER']-masks['BAG']),('participation',masks['ORDER']-masks['ORDER'].mean())]:
            for prefix,l,u in [('',lo,hi),('stress_',lo-.8,hi-.8)]:
                a,b=interval_product(coef,l,u);row[prefix+name+'_lower']=float(a.mean());row[prefix+name+'_upper']=float(b.mean())
        rows.append(row)
    columns=['identified_rows',*CI_COLUMNS,*[arm+'_selection_rate' for arm in ARMS],*[arm+'_mse_proxy_lower' for arm in ARMS]]
    result=pd.DataFrame(rows).set_index('u_date') if rows else pd.DataFrame(columns=columns)
    return result.reindex(pd.Index(calendar,name='u_date'))
def finite_mean(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return float(a.mean()) if len(a) else None
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
        'primary_ORDER_selected_identified_dates_ge60':primary['cohort']['ORDER']['selected_identified_dates']>=60,
        'primary_ORDER_selected_identified_families_ge8':primary['cohort']['ORDER']['selected_identified_families']>=8,
        'primary_ORDER_lower_ci_positive':positive(ci['ORDER_lower']['ci95_lower']),
        'primary_ORDER_minus_S_lower_ci_positive':positive(ci['ORDER_minus_S_lower']['ci95_lower']),
        'primary_ORDER_minus_BAG_lower_ci_positive':positive(ci['ORDER_minus_BAG_lower']['ci95_lower']),
        'primary_participation_lower_ci_positive':positive(ci['participation_lower']['ci95_lower']),
        'same_mask_cost_1R_primary_ORDER_lower_positive':positive(means['stress_ORDER_lower']),
        'four_complete_years_ORDER_minus_S_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['ORDER_minus_S_lower']) for y in range(2020,2026))>=4,
        'four_complete_years_ORDER_minus_BAG_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['ORDER_minus_BAG_lower']) for y in range(2020,2026))>=4,
        'partial_2026_ORDER_lower_positive':positive(reports['main']['annual']['2026']['date_equal_means']['ORDER_lower'])}
    for metric in ('ORDER_lower','ORDER_minus_S_lower','ORDER_minus_BAG_lower','participation_lower'):
        gates['all_2015_'+metric+'_positive']=positive(secondary['date_equal_means'][metric])
    for group in (0,1):
        for metric in ('ORDER_lower','ORDER_minus_S_lower','ORDER_minus_BAG_lower'):
            gates[f'holdout_{group}_primary_{metric}_positive']=positive(reports[f'holdout_{group}']['primary_2020']['date_equal_means'][metric])
    if len(gates)!=20:raise ValueError('screen gate closure is not twenty')
    return dict(schema='stage024_fixed_ordered_history_screen_v1',scopes=reports,gates=gates,quality_information_screen_pass=all(gates.values()),
        representation_primary_contrast='ORDER-BAG',selection_mask='score>0',label_metric='date_equal ideal continuous barrier normalized proxy; not account returns',
        participation_diagnostic='ex-post same-day label-identified ORDER participation; not u-executable random strategy',
        financial_metrics={k:None for k in ('ending_equity','total_return','max_drawdown','sharpe','total_slippage','total_trades','win_rate')},financial_ready=False,production_qualified=False),daily_frames
def load_protocol():
    if file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen022 protocol changed')
    p=json.loads(PROTOCOL.read_bytes());read_bound(p['frozen_spec'])
    if p['arms']!=list(ARMS) or p['actual_fit_calls_expected']!=108 or p['gates_count']!=20:raise ValueError('unexpected experiment contract')
    return p
def csv_from_binding(binding):
    raw=read_bound(binding)
    if str(binding['path']).endswith('.gz'):raw=gzip.decompress(raw)
    return pd.read_csv(io.BytesIO(raw),dtype=str,keep_default_na=False)
def load_inputs(bindings):
    protocol=load_protocol()
    for key in ('data_manifest','data_review'):
        if bindings[key]['sha256']!=protocol[key]['sha256']:raise ValueError('unexpected parent binding '+key)
    parent=json.loads(read_bound(bindings['data_manifest']));review=json.loads(read_bound(bindings['data_review']))
    if review.get('qualified_for_fixed_proxy_experiment') is not True or review['data_manifest']['sha256']!=bindings['data_manifest']['sha256']:raise ValueError('009 fixed proxy qualification missing')
    frame=csv_from_binding(parent['feature_label_csv'])
    required={'event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status','feature_ready',
        'history_state','label_identified','label_state','label_known_date','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper',*OWN}
    if not required<=set(frame) or len(frame)!=399252 or frame.event_id.duplicated().any() or frame.duplicated(['product_id','u_date']).any():raise ValueError('invalid original mother frame identity/schema')
    for col in ('feature_ready','label_identified','path_ambiguous'):
        if not frame[col].isin(['0','1']).all():raise ValueError('nonbinary flag')
        frame[col]=frame[col].astype(int)
    for col in [*OWN,'gross_lower','gross_upper','proxy_lower','proxy_upper']:frame[col]=pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    ready=frame.feature_ready.eq(1);known=frame.label_identified.eq(1)
    if (int(ready.sum()),int(known.sum()),int((ready&~known).sum()))!=(194709,194168,541):raise ValueError('accepted counts changed')
    if not np.isfinite(frame.loc[ready,OWN].to_numpy(float)).all() or (known&~ready).any():raise ValueError('invalid ready feature')
    outcomes=['gross_lower','gross_upper','proxy_lower','proxy_upper']
    if not np.isfinite(frame.loc[known,outcomes].to_numpy(float)).all() or frame.loc[~known,outcomes].notna().any().any():raise ValueError('unknown/identified outcome contract broken')
    if frame.loc[known,'proxy_lower'].gt(frame.loc[known,'proxy_upper']).any():raise ValueError('inverted interval')
    for side in ('lower','upper'):
        if not np.allclose(frame.loc[known,'gross_'+side]-.2,frame.loc[known,'proxy_'+side],rtol=0,atol=1e-10):raise ValueError('base cost changed')
    if frame.loc[~known,'label_known_date'].ne('').any() or not frame.loc[known,'label_known_date'].eq(frame.loc[known,'planned_execution_date']).all() or not frame.loc[known,'label_known_date'].gt(frame.loc[known,'u_date']).all():raise ValueError('maturity contract changed')
    if not frame.family_id.eq(frame.product_id.str.replace(r'_F$','',regex=True)).all():raise ValueError('family mapping differs')
    sequence_manifest=json.loads(read_bound(bindings['sequence_manifest']))
    for key,expected in [('protocol',PROTOCOL_SHA),('parent_manifest',bindings['data_manifest']['sha256']),('parent_review',bindings['data_review']['sha256'])]:
        if sequence_manifest[key]['sha256']!=expected:raise ValueError('023 parent binding differs '+key)
    dates=parent['source_calendar_scope_dates']
    if dates!=sorted(set(dates)) or dates[-1]!='2026-10-16' or sequence_manifest['source_calendar_scope_dates']!=dates:raise ValueError('source date grid changed')
    if not frame.u_date.isin(dates).all():raise ValueError('outer date missing from grid')
    ids=csv_from_binding(sequence_manifest['event_ids_csv'])
    if list(ids.columns)!=['sequence_index','event_id'] or ids.event_id.tolist()!=frame.loc[ready,'event_id'].tolist():raise ValueError('sequence identity/order differs from original009 ready rows')
    if ids.sequence_index.astype(int).tolist()!=list(range(194709)):raise ValueError('sequence indices not one to one')
    raw=read_bound(sequence_manifest['sequence_npz'])
    with np.load(io.BytesIO(raw),allow_pickle=False) as stored:
        if stored.files!=['ordered']:raise ValueError('sequence NPZ contains extra fields')
        ordered=stored['ordered']
    if ordered.dtype.str!='<f4' or ordered.shape!=(194709,20,4) or not np.isfinite(ordered).all():raise ValueError('invalid ordered matrix')
    frame['sequence_index']=-1;frame.loc[ready,'sequence_index']=np.arange(194709)
    frame=frame[sorted(required)+['sequence_index']]
    return frame,ordered,dates,dict(protocol=protocol,parent_manifest=parent,data_review=review,sequence_manifest=sequence_manifest)
def prediction_frame(test,records,ordered,mapping,scope,year):
    cols=['event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status','history_state',
        'label_identified','label_state','label_known_date','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper']
    result=test[cols].copy();result['scope']=scope;result['test_year']=year
    for arm in ARMS:
        result['pred_'+arm]=predict_from_record(records[arm],test,ordered,mapping);result['mask_'+arm]=result['pred_'+arm].gt(0).astype(int)
    return result
def save_training_membership(train,cell_dir):
    cell_dir.mkdir(parents=True,exist_ok=False);path=cell_dir/'training_membership.npz'
    np.savez_compressed(path,event_id=train.event_id.to_numpy(dtype=str),sequence_index=train.sequence_index.to_numpy(dtype='<i4'),weights=date_weights(train).astype('<f8'))
    return file_binding(path)
def perform_fits(frame,ordered,calendar,out,mapping):
    predictions={scope:[] for scope,_ in SCOPES};mapping_binding=file_binding(out/'rff_mapping.npz')
    for year in YEARS:
        cutoff=next(d for d in calendar if d.startswith(str(year)))
        for scope,group in SCOPES:
            train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group)
            cell_dir=out/'fits'/f'{year}_{scope}';membership=save_training_membership(train,cell_dir);records={}
            for arm in ARMS:
                fit_id=f'{year}_{scope}_{arm}';record=fit_one(train,ordered,arm,fit_id,cutoff,group,mapping)
                record.pop('training_ids');record.pop('training_weights')
                record.update(test_year=year,scope=scope,protocol_sha256=PROTOCOL_SHA,training_membership=membership,mapping=mapping_binding,
                    source_versions=dict(numpy=np.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__))
                write_json(cell_dir/(arm+'.json'),record);records[arm]=record
                print(json.dumps(dict(completed_fit=fit_id,actual_fit_calls=FIT_CALLS,training_rows=len(train),test_rows=len(test))),flush=True)
            predictions[scope].append(prediction_frame(test,records,ordered,mapping,scope,year))
    if FIT_CALLS!=108:raise ValueError('did not perform exactly108 fixed fits')
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}
def replay_fits(frame,ordered,calendar,previous,mapping):
    predictions={scope:[] for scope,_ in SCOPES};paths=list((previous/'fits').glob('*/*.json'))
    if len(paths)!=108:raise ValueError('incomplete saved108-fit closure')
    for year in YEARS:
        cutoff=next(d for d in calendar if d.startswith(str(year)))
        for scope,group in SCOPES:
            train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group);records={}
            ids_sha=sha_bytes(('\n'.join(train.event_id)+'\n').encode());weights_sha=sha_bytes(date_weights(train).astype('<f8').tobytes())
            for arm in ARMS:
                record=json.loads((previous/'fits'/f'{year}_{scope}'/(arm+'.json')).read_bytes())
                if record['training_ids_sha256']!=ids_sha or record['training_weights_sha256']!=weights_sha or record['cutoff_exclusive']!=cutoff or record['heldout_group']!=group or record['protocol_sha256']!=PROTOCOL_SHA:raise ValueError('saved fit identity changed')
                read_bound(record['mapping']);raw=read_bound(record['training_membership'])
                with np.load(io.BytesIO(raw),allow_pickle=False) as audit:
                    if audit['event_id'].tolist()!=train.event_id.tolist() or not np.array_equal(audit['sequence_index'],train.sequence_index.to_numpy(int)) or not np.array_equal(audit['weights'],date_weights(train)):raise ValueError('saved training membership differs')
                records[arm]=record
            predictions[scope].append(prediction_frame(test,records,ordered,mapping,scope,year))
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}
def artifacts(out):
    result=[]
    for path in sorted(out.rglob('*')):
        if not path.is_file() or path.name=='manifest.json':continue
        role='model_artifact' if path.suffix=='.npz' or 'fits' in path.parts else 'qualification_evidence' if path.name=='actual_terminal.json' else 'feature_contract' if path.name in ('protocol.json','input_bindings.json') else 'decision_asset'
        result.append(dict(file_binding(path),role=role,reproducibility_required=True,raw_ohlc=False))
    return result
def execute(args):
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('refuse overwrite/repeated fit '+str(out))
    previous=None
    if args.command=='fit':bindings=json.loads(Path(args.bindings).read_bytes())
    else:
        previous=Path(args.experiment).resolve();bindings=json.loads((previous/'input_bindings.json').read_bytes())
        source_binding=json.loads((previous/'source_binding.json').read_bytes())
        if source_binding['sha256']!=file_binding(__file__)['sha256']:raise ValueError('export code differs from saved fit source')
    frame,ordered,calendar,evidence=load_inputs(bindings)
    out.mkdir(parents=True,exist_ok=False);write_json(out/'input_bindings.json',bindings);write_json(out/'protocol.json',evidence['protocol']);write_json(out/'source_binding.json',file_binding(__file__))
    status='failed';error=None;metrics=None
    try:
        if args.command=='fit':
            mapping=make_mapping();np.savez_compressed(out/'rff_mapping.npz',**mapping);predictions=perform_fits(frame,ordered,calendar,out,mapping)
        else:
            with np.load(previous/'rff_mapping.npz',allow_pickle=False) as saved:mapping={key:saved[key] for key in saved.files}
            expected=make_mapping()
            if any(not np.array_equal(mapping[k],expected[k]) for k in expected):raise ValueError('stored random map changed')
            predictions=replay_fits(frame,ordered,calendar,previous,mapping)
            write_json(out/'replayed_fit_source.json',dict(path=str(previous),fit_records=108,fit_calls_this_command=0))
        metrics,daily=report_predictions(predictions,calendar)
        metrics['input_states']=dict(all_outer_rows=len(frame),ready=int(frame.feature_ready.sum()),identified=int(frame.label_identified.sum()),ready_unknown=int((frame.feature_ready.eq(1)&frame.label_identified.eq(0)).sum()),label_states=dict(Counter(frame.label_state)))
        for scope,pred in predictions.items():pred.to_csv(out/f'predictions_{scope}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        for name,d in daily.items():d.to_csv(out/f'daily_{name}.csv',index=True)
        write_json(out/'metrics.json',metrics);status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'actual_terminal.json',dict(command=args.command,status=status,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,actual_ridge_fit_calls=FIT_CALLS,
            actual_financial_runs=0,fixture=False,exit_code=0 if status=='completed' else 1,error=error,python=sys.executable,numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,platform=platform.platform(),threadpools=threadpool_info(),network_calls=0,sql_queries=0))
    write_json(out/'manifest.json',dict(schema='stage024_fixed_ordered_history_experiment_v1',status=status,source=file_binding(__file__),tests=file_binding(Path(__file__).with_name('test_stage024_ordered_history_experiment.py')),
        protocol=file_binding(PROTOCOL),input_bindings=bindings,artifacts=artifacts(out),actual_fit_calls=FIT_CALLS,saved_fit_records=108,export_only=args.command=='export-only',quality_information_screen_pass=metrics['quality_information_screen_pass'],financial_ready=False,production_qualified=False,financial_runs=0))
    return dict(status=status,actual_fit_calls=FIT_CALLS,output=str(out),quality_information_screen_pass=metrics['quality_information_screen_pass'])
def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    fit=sub.add_parser('fit');fit.add_argument('--bindings',required=True);fit.add_argument('--output',required=True)
    replay=sub.add_parser('export-only');replay.add_argument('--experiment',required=True);replay.add_argument('--output',required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False))
if __name__=='__main__':main()
