"""Frozen Stage007 proxy experiment. No native account, cash returns or model tuning.

The fit command consumes a root-bound accepted Stage009/011 handoff once.
export-only replays saved numeric coefficients and never calls an estimator fit.
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

for _env in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_env]='1'
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import sklearn
import scipy
from threadpoolctl import threadpool_limits, threadpool_info

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage007_quality_protocol/protocol.json'
PROTOCOL_SHA='2e5da3da4440223e3ac978256d563b80d5bd4264cec56d4085ed6062d7bad0a4'
OWN=['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
     'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MARKET=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing']
FEATURES={'M0':OWN,'M1':OWN+MARKET}
YEARS=tuple(range(2015,2027))
FIT_CALLS=0
CI_COLUMNS=['M1_lower','M1_upper','M0_lower','paired_lower','paired_upper',
            'participation_lower','participation_upper','stress_M1_lower',
            'stress_M0_lower','stress_paired_lower','stress_paired_upper',
            'stress_participation_lower','stress_participation_upper',
            'intercept_lower','momentum_lower','cash_lower',
            'excluded_positive_proxy_lower','excluded_positive_proxy_upper']

def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def file_binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return {'path':str(p),'sha256':sha_bytes(raw),'bytes':len(raw)}
def read_bound(binding):
    p=Path(binding['path']);raw=p.read_bytes()
    if sha_bytes(raw)!=binding['sha256'] or ('bytes' in binding and len(raw)!=binding['bytes']):
        raise ValueError('input binding mismatch: '+str(p))
    return raw
def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def family_group(family): return int(hashlib.sha256(family.encode()).hexdigest(),16)%2

def training_slice(frame,cutoff,held_group=None):
    use=(frame.feature_ready.eq(1)&frame.label_identified.eq(1)&frame.u_date.ge('2010-01-01')&
         frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff))
    if held_group is not None: use &= frame.family_id.map(family_group).ne(held_group)
    return frame.loc[use].sort_values(['u_date','event_id']).copy()

def fit_one(train,features,fit_id,cutoff,held_group):
    global FIT_CALLS
    if train.empty: raise ValueError('no mature training rows for '+fit_id)
    if not train.u_date.lt(cutoff).all() or not train.label_known_date.lt(cutoff).all():
        raise ValueError('unmatured training input')
    if held_group is not None and train.family_id.map(family_group).eq(held_group).any():
        raise ValueError('held family in training')
    train=train.sort_values(['u_date','event_id'])
    x=train[features].to_numpy(dtype=float);y=train.proxy_lower.to_numpy(dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError('nonfinite training values')
    counts=train.groupby('u_date').size()
    weights=(1./train.u_date.map(counts)).to_numpy(dtype=float);weights/=weights.mean()
    with threadpool_limits(limits=1):
        scaler=StandardScaler().fit(x,sample_weight=weights)
        model=Ridge(alpha=1.,solver='cholesky',fit_intercept=True)
        model.fit(scaler.transform(x),y,sample_weight=weights)
    FIT_CALLS+=1
    unique_weights=dict(zip(train.u_date,map(float,weights)))
    return dict(fit_id=fit_id,estimator='sklearn.linear_model.Ridge',alpha=1.,solver='cholesky',fit_intercept=True,
        feature_names=list(features),cutoff_exclusive=cutoff,heldout_group=held_group,training_rows=len(train),
        training_dates=len(counts),training_families=sorted(train.family_id.unique()),
        max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
        training_ids_sha256=sha_bytes(('\n'.join(train.event_id)+'\n').encode()),
        training_sort=['u_date','event_id'],weights_rule='inverse_rows_per_date_normalized_to_mean_one',
        weights_by_date=unique_weights,weights_sha256=sha_bytes(weights.astype('<f8').tobytes()),
        intercept_reference=float(np.average(y,weights=weights)),
        scaler={'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),'var':scaler.var_.tolist()},
        coef=model.coef_.tolist(),intercept=float(model.intercept_),blas_threads=1)

def predict_from_record(record,frame):
    x=frame[record['feature_names']].to_numpy(dtype=float)
    if not np.isfinite(x).all(): raise ValueError('nonfinite prediction features')
    scale=np.array(record['scaler']['scale']);mean=np.array(record['scaler']['mean'])
    return ((x-mean)/scale)@np.array(record['coef'])+record['intercept']

def coefficient_prediction_frame(test,record0,record1,scope,year):
    names=['event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date',
           'status','history_state','label_identified','label_state','label_known_date','path_ambiguous',
           'gross_lower','gross_upper','proxy_lower','proxy_upper']
    result=test[names].copy()
    result['scope']=scope;result['test_year']=year
    result['pred_M0']=predict_from_record(record0,test);result['pred_M1']=predict_from_record(record1,test)
    result['mask_M0']=result.pred_M0.gt(0).astype(int);result['mask_M1']=result.pred_M1.gt(0).astype(int)
    result['intercept_score']=record0['intercept_reference']
    result['momentum_mask']=test.r20_atr.gt(0).to_numpy(dtype=int)
    result['cash_mask']=0
    return result

def interval_product(a,lower,upper):
    return np.where(a>=0,a*lower,a*upper),np.where(a>=0,a*upper,a*lower)

def daily_metrics(pred,calendar):
    rows=[]
    for day,g in pred.loc[pred.label_identified.eq(1)].groupby('u_date',sort=True):
        lo=g.proxy_lower.to_numpy(float);hi=g.proxy_upper.to_numpy(float)
        m0=g.pred_M0.gt(0).to_numpy(dtype=float);m1=g.pred_M1.gt(0).to_numpy(dtype=float)
        paired_lo,paired_hi=interval_product(m1-m0,lo,hi)
        part_lo,part_hi=interval_product(m1-m1.mean(),lo,hi)
        stress_paired_lo,stress_paired_hi=interval_product(m1-m0,lo-.8,hi-.8)
        stress_part_lo,stress_part_hi=interval_product(m1-m1.mean(),lo-.8,hi-.8)
        rows.append(dict(u_date=day,identified_rows=len(g),M1_lower=float(np.mean(m1*lo)),M1_upper=float(np.mean(m1*hi)),
            M0_lower=float(np.mean(m0*lo)),paired_lower=float(paired_lo.mean()),paired_upper=float(paired_hi.mean()),
            participation_lower=float(part_lo.mean()),participation_upper=float(part_hi.mean()),
            stress_M1_lower=float(np.mean(m1*(lo-.8))),M1_selection_rate=float(m1.mean()),M0_selection_rate=float(m0.mean()),
            stress_M0_lower=float(np.mean(m0*(lo-.8))),stress_paired_lower=float(stress_paired_lo.mean()),
            stress_paired_upper=float(stress_paired_hi.mean()),stress_participation_lower=float(stress_part_lo.mean()),
            stress_participation_upper=float(stress_part_hi.mean()),
            intercept_lower=float(np.mean(g.intercept_score.gt(0).to_numpy()*lo)),
            momentum_lower=float(np.mean(g.momentum_mask.to_numpy()*lo)),cash_lower=0.,
            excluded_positive_proxy_lower=float(np.mean((1-m1)*np.maximum(lo,0))),
            excluded_positive_proxy_upper=float(np.mean((1-m1)*np.maximum(hi,0))),
            M0_mse_proxy_lower=float(np.mean((g.pred_M0.to_numpy()-lo)**2)),
            M1_mse_proxy_lower=float(np.mean((g.pred_M1.to_numpy()-lo)**2)),
            ambiguous_rate=float(g.path_ambiguous.mean())))
    columns=['identified_rows',*CI_COLUMNS,'M1_selection_rate','M0_selection_rate','M0_mse_proxy_lower','M1_mse_proxy_lower','ambiguous_rate']
    result=pd.DataFrame(rows).set_index('u_date') if rows else pd.DataFrame(columns=columns)
    result=result.reindex(pd.Index(calendar,name='u_date'))
    return result

def finite_mean(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return float(a.mean()) if len(a) else None

def cohort_counts(pred):
    known=pred.label_identified.eq(1);unknown=~known;selected=known&pred.pred_M1.gt(0)
    return dict(feature_ready_predictions=len(pred),identified_rows=int(known.sum()),unknown_rows=int(unknown.sum()),
        unknown_label_states=dict(Counter(pred.loc[unknown,'label_state'])),
        all_ready_M0_selection_rate=finite_mean(pred.pred_M0.gt(0)),all_ready_M1_selection_rate=finite_mean(pred.pred_M1.gt(0)),
        unknown_M0_selection_rate=finite_mean(pred.loc[unknown,'pred_M0'].gt(0)),
        unknown_M1_selection_rate=finite_mean(pred.loc[unknown,'pred_M1'].gt(0)),
        identified_M1_selected_rows=int(selected.sum()),identified_M1_selected_dates=int(pred.loc[selected,'u_date'].nunique()),
        identified_M1_selected_families=int(pred.loc[selected,'family_id'].nunique()),
        all_ready_M1_selected_dates=int(pred.loc[pred.pred_M1.gt(0),'u_date'].nunique()),
        all_ready_M1_selected_families=int(pred.loc[pred.pred_M1.gt(0),'family_id'].nunique()),
        ambiguous_identified_rows=int(pred.loc[known,'path_ambiguous'].sum()),
        unknown_rate=finite_mean(unknown))

def bootstrap_intervals(daily,columns):
    n=len(daily);block=60;repetitions=2000
    if n==0: raise ValueError('empty source-date grid')
    actual_block=min(block,n);blocks=math.ceil(n/actual_block)
    rng=np.random.default_rng(20261018);array=daily[columns].to_numpy(float)
    results=np.full((repetitions,len(columns)),np.nan);index_hash=hashlib.sha256()
    for b in range(repetitions):
        starts=rng.integers(0,n-actual_block+1,size=blocks)
        index=(starts[:,None]+np.arange(actual_block)[None,:]).ravel()[:n]
        index_hash.update(index.astype('<i8').tobytes())
        chosen=array[index];finite=np.isfinite(chosen);den=finite.sum(axis=0)
        results[b]=np.divide(np.where(finite,chosen,0).sum(axis=0),den,out=np.full(len(columns),np.nan),where=den>0)
    metrics={}
    for j,c in enumerate(columns):
        sample=results[:,j];sample=sample[np.isfinite(sample)]
        interval=np.quantile(sample,[.025,.975]).tolist() if len(sample) else [None,None]
        metrics[c]={'mean':finite_mean(array[:,j]),'ci95_lower':interval[0],'ci95_upper':interval[1],
                    'finite_source_days':int(np.isfinite(array[:,j]).sum()),'finite_bootstrap_replicates':len(sample)}
    return dict(block_length=block,effective_block_length=actual_block,repetitions=repetitions,seed=20261018,
        source_grid_days=n,common_indices_sha256=index_hash.hexdigest(),metrics=metrics,
        uncertainty_scope='fixed predictions; date-equal conditional proxy only; not research selection or cash uncertainty')

def calibration(pred):
    # Fixed diagnostic bins; never used to select a mask or tune anything.
    known=pred.loc[pred.label_identified.eq(1)]
    result={}
    for model in ('M0','M1'):
        value=known['pred_'+model];bins=np.digitize(value,[-1.,0.,1.,4.],right=False)
        result[model]=[]
        for b,label in enumerate(['lt_minus1','minus1_to_0','0_to_1','1_to_4','ge_4']):
            g=known.loc[bins==b]
            daily=g.groupby('u_date')[['pred_'+model,'proxy_lower','proxy_upper']].mean()
            result[model].append(dict(bin=label,rows=len(g),dates=len(daily),predicted=finite_mean(daily['pred_'+model]),
                proxy_lower=finite_mean(daily.proxy_lower),proxy_upper=finite_mean(daily.proxy_upper)))
    return result

def positive(value): return value is not None and math.isfinite(value) and value>0

def report_predictions(predictions,calendar):
    predictions=dict(predictions,holdout_combined=pd.concat([predictions['holdout_0'],predictions['holdout_1']],ignore_index=True))
    reports={};daily_frames={}
    for scope,pred in predictions.items():
        scope_report={'annual':{}}
        for year in YEARS:
            frame=pred.loc[pred.u_date.str.startswith(str(year))]
            dates=[d for d in calendar if d.startswith(str(year))]
            daily=daily_metrics(frame,dates)
            scope_report['annual'][str(year)]={'cohort':cohort_counts(frame),'date_equal_means':{c:finite_mean(daily[c]) for c in daily},
                'source_grid_days':len(dates),'no_identified_days':int(daily.identified_rows.isna().sum()),'calibration':calibration(frame)}
        for period,start in [('all_2015','2015-01-01'),('primary_2020','2020-01-01')]:
            frame=pred.loc[pred.u_date.ge(start)];dates=[d for d in calendar if d>=start]
            daily=daily_metrics(frame,dates);daily_frames[scope+'_'+period]=daily
            scope_report[period]={'cohort':cohort_counts(frame),'date_equal_means':{c:finite_mean(daily[c]) for c in daily},
                'source_grid_days':len(dates),'no_identified_days':int(daily.identified_rows.isna().sum())}
            if scope=='main': scope_report[period]['bootstrap']=bootstrap_intervals(daily,CI_COLUMNS)
        reports[scope]=scope_report
    primary=reports['main']['primary_2020'];alltime=reports['main']['all_2015'];means=primary['date_equal_means']
    ci=primary['bootstrap']['metrics'];cohort=primary['cohort']
    gates={
      'primary_selected_dates_at_least_60':cohort['identified_M1_selected_dates']>=60,
      'primary_selected_families_at_least_8':cohort['identified_M1_selected_families']>=8,
      'primary_M1_lower_positive':positive(means['M1_lower']),
      'primary_paired_lower_ci_positive':positive(ci['paired_lower']['ci95_lower']),
      'primary_participation_lower_ci_positive':positive(ci['participation_lower']['ci95_lower']),
      'all_2015_M1_lower_positive':positive(alltime['date_equal_means']['M1_lower']),
      'all_2015_paired_lower_positive':positive(alltime['date_equal_means']['paired_lower']),
      'all_2015_participation_lower_positive':positive(alltime['date_equal_means']['participation_lower']),
      'same_mask_cost_1R_primary_positive':positive(means['stress_M1_lower']),
      'four_complete_years_paired_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['paired_lower']) for y in range(2020,2026))>=4,
      'partial_2026_M1_lower_positive':positive(reports['main']['annual']['2026']['date_equal_means']['M1_lower'])}
    for group in (0,1):
        for metric in ('M1_lower','paired_lower'):
            gates[f'holdout_{group}_primary_{metric}_positive']=positive(reports[f'holdout_{group}']['primary_2020']['date_equal_means'][metric])
    return dict(schema='stage010_fixed_proxy_screen_metrics_v1',scopes=reports,gates=gates,
        quality_information_screen_pass=all(gates.values()),
        selected_date_support_basis='common label_identified evaluation cohort, not unknown predictions',
        label_metric='ideal continuous barrier normalized proxy; not fills/net cash return',
        financial_ready=False,production_qualified=False),daily_frames

def load_protocol():
    raw=PROTOCOL.read_bytes()
    if sha_bytes(raw)!=PROTOCOL_SHA: raise ValueError('frozen Stage007 protocol changed')
    p=json.loads(raw)
    read_bound(p['frozen_spec'])
    if p['model_features']!=FEATURES or p['annual_test_years']!=list(YEARS): raise ValueError('unexpected frozen model contract')
    return p

def load_inputs(bindings):
    protocol=load_protocol()
    manifest=json.loads(read_bound(bindings['data_manifest']))
    review=json.loads(read_bound(bindings['data_review']))
    if review.get('qualified_for_fixed_proxy_experiment') is not True:
        raise ValueError('Stage011 receipt does not qualify the fixed proxy experiment')
    if review.get('data_manifest',{}).get('sha256')!=bindings['data_manifest']['sha256']:
        raise ValueError('Stage011 receipt is for a different dataset manifest')
    if manifest['protocol']['sha256']!=PROTOCOL_SHA: raise ValueError('dataset protocol binding differs')
    read_bound(manifest['protocol'])
    dataset_binding=manifest['feature_label_csv'];raw=read_bound(dataset_binding)
    csv_raw=gzip.decompress(raw) if str(dataset_binding['path']).endswith('.gz') else raw
    frame=pd.read_csv(io.BytesIO(csv_raw),dtype=str,keep_default_na=False)
    if len(frame)!=dataset_binding['rows']: raise ValueError('dataset row count differs')
    required={'event_id','product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status',
      'feature_ready','history_state','atr20','label_identified','label_state','label_known_date','path_ambiguous',
      'gross_lower','gross_upper','proxy_lower','proxy_upper',*OWN,*MARKET}
    if not required<=set(frame): raise ValueError('missing feature dataset columns')
    if frame.event_id.duplicated().any() or frame.duplicated(['product_id','u_date']).any(): raise ValueError('duplicate identity')
    for col in ('feature_ready','label_identified','path_ambiguous'):
        if not frame[col].isin(['0','1']).all(): raise ValueError('nonbinary flag '+col)
        frame[col]=frame[col].astype(int)
    for col in [*OWN,*MARKET,'atr20','gross_lower','gross_upper','proxy_lower','proxy_upper']:
        frame[col]=pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    ready=frame.feature_ready.eq(1);known=frame.label_identified.eq(1)
    if not np.isfinite(frame.loc[ready,OWN+MARKET].to_numpy(float)).all(): raise ValueError('ready feature not finite')
    if (known&~ready).any(): raise ValueError('identified label without ready features')
    if not np.isfinite(frame.loc[known,['proxy_lower','proxy_upper','gross_lower','gross_upper']].to_numpy(float)).all():
        raise ValueError('identified label not finite')
    if frame.loc[known,'proxy_lower'].gt(frame.loc[known,'proxy_upper']).any(): raise ValueError('inverted proxy interval')
    if not np.allclose(frame.loc[known,'gross_lower']-.2,frame.loc[known,'proxy_lower'],rtol=0,atol=1e-10): raise ValueError('wrong base lower cost')
    if not np.allclose(frame.loc[known,'gross_upper']-.2,frame.loc[known,'proxy_upper'],rtol=0,atol=1e-10): raise ValueError('wrong base upper cost')
    if frame.loc[~known,['proxy_lower','proxy_upper','gross_lower','gross_upper']].notna().any().any(): raise ValueError('unknown label has outcome')
    if frame.loc[~known,'label_known_date'].ne('').any(): raise ValueError('unknown label has maturity')
    if (frame.loc[known,'label_known_date']!=frame.loc[known,'planned_execution_date']).any() or not frame.loc[known,'label_known_date'].gt(frame.loc[known,'u_date']).all():
        raise ValueError('label maturity does not match next execution date')
    if not frame.family_id.eq(frame.product_id.str.replace(r'_F$','',regex=True)).all(): raise ValueError('family mapping differs')
    dates=manifest['source_calendar_scope_dates']
    if dates!=sorted(set(dates)) or dates[0]<'2010-01-01' or dates[-1]!='2026-10-16': raise ValueError('invalid source date grid')
    if not frame.u_date.isin(dates).all(): raise ValueError('observation outside source calendar')
    if 'source_calendar' in manifest: read_bound(manifest['source_calendar'])
    return frame,dates,dict(protocol=protocol,data_manifest=manifest,data_review=review)

def test_slice(frame,year,held_group):
    use=frame.feature_ready.eq(1)&frame.u_date.str.startswith(str(year))
    if held_group is not None: use &= frame.family_id.map(family_group).eq(held_group)
    return frame.loc[use].sort_values(['u_date','event_id']).copy()

def perform_fits(frame,calendar,out):
    predictions={name:[] for name in ('main','holdout_0','holdout_1')}
    with (out/'fits.jsonl').open('x') as log:
        for year in YEARS:
            cutoff=next(d for d in calendar if d.startswith(str(year)))
            for scope,group in [('main',None),('holdout_0',0),('holdout_1',1)]:
                train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group);records={}
                for model,features in FEATURES.items():
                    fit=fit_one(train,features,f'{year}_{scope}_{model}',cutoff,group)
                    fit.update(test_year=year,scope=scope,model=model,protocol_sha256=PROTOCOL_SHA)
                    log.write(json.dumps(fit,ensure_ascii=False,allow_nan=False)+'\n');log.flush();os.fsync(log.fileno())
                    records[model]=fit
                    print(json.dumps({'completed_fit':fit['fit_id'],'training_rows':len(train),'prediction_rows':len(test),'actual_fit_calls':FIT_CALLS}),flush=True)
                predictions[scope].append(coefficient_prediction_frame(test,records['M0'],records['M1'],scope,year))
    if FIT_CALLS!=72: raise ValueError('actual experiment did not perform exactly 72 fits')
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}

def replay_fits(frame,calendar,records):
    if len(records)!=72 or len({r['fit_id'] for r in records})!=72: raise ValueError('incomplete saved fit closure')
    lookup={(r['test_year'],r['scope'],r['model']):r for r in records};predictions={n:[] for n in ('main','holdout_0','holdout_1')}
    for year in YEARS:
        cutoff=next(d for d in calendar if d.startswith(str(year)))
        for scope,group in [('main',None),('holdout_0',0),('holdout_1',1)]:
            train=training_slice(frame,cutoff,group);test=test_slice(frame,year,group)
            ids=sha_bytes(('\n'.join(train.event_id)+'\n').encode())
            r0,r1=[lookup[(year,scope,m)] for m in ('M0','M1')]
            for r in (r0,r1):
                if r['training_ids_sha256']!=ids or r['cutoff_exclusive']!=cutoff or r['heldout_group']!=group:
                    raise ValueError('saved training identity no longer matches')
            predictions[scope].append(coefficient_prediction_frame(test,r0,r1,scope,year))
    return {k:pd.concat(v,ignore_index=True) for k,v in predictions.items()}

def export_results(out,predictions,calendar,input_counts):
    metrics,daily=report_predictions(predictions,calendar)
    metrics['input_states']=input_counts
    for name,frame in predictions.items():
        frame.to_csv(out/f'predictions_{name}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    for name,frame in daily.items(): frame.to_csv(out/f'daily_{name}.csv',index=True)
    write_json(out/'metrics.json',metrics)
    return metrics

def roles(out):
    result=[]
    for p in sorted(out.iterdir()):
        if not p.is_file() or p.name=='manifest.json': continue
        role=('model_reproduction_asset' if p.name=='fits.jsonl' else
              'decision_asset' if p.name.startswith(('predictions_','daily_','metrics')) else
              'qualification_evidence' if p.name=='actual_terminal.json' else 'source_protocol_binding')
        result.append(dict(file_binding(p),role=role,raw_ohlc=False))
    return result

def execute(args):
    global FIT_CALLS
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();out=Path(args.output).resolve()
    if out.exists(): raise FileExistsError('refuse overwrite or repeat fit: '+str(out))
    if args.command=='fit':
        bindings=json.loads(Path(args.bindings).read_bytes())
    else:
        previous=Path(args.experiment).resolve();old_manifest=json.loads((previous/'manifest.json').read_bytes())
        for asset in old_manifest['artifacts']: read_bound(asset)
        bindings=json.loads((previous/'input_bindings.json').read_bytes())
        if old_manifest['source']['sha256']!=file_binding(Path(__file__))['sha256']: raise ValueError('export source differs from frozen fit source')
    frame,calendar,evidence=load_inputs(bindings)
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'input_bindings.json',bindings)
    write_json(out/'protocol.json',evidence['protocol'])
    status='failed';error=None
    try:
        if args.command=='fit': predictions=perform_fits(frame,calendar,out)
        else:
            records=[json.loads(line) for line in (previous/'fits.jsonl').read_text().splitlines()]
            predictions=replay_fits(frame,calendar,records)
            (out/'fits.jsonl').write_bytes((previous/'fits.jsonl').read_bytes())
        counts=dict(all_outer_rows=len(frame),feature_ready_rows=int(frame.feature_ready.sum()),
            input_status=dict(Counter(frame.status)),history_states=dict(Counter(frame.history_state)),
            label_states=dict(Counter(frame.label_state)),unready_rows=int(frame.feature_ready.eq(0).sum()))
        metrics=export_results(out,predictions,calendar,counts)
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        write_json(out/'actual_terminal.json',dict(command=args.command,status=status,started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            actual_ridge_fit_calls=FIT_CALLS,fixture=False,exit_code=0 if status=='completed' else 1,error=error,
            python=sys.executable,numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,
            platform=platform.platform(),threadpools=threadpool_info(),financial_runs=0,network_calls=0))
    write_json(out/'manifest.json',dict(schema='stage010_fixed_proxy_experiment_v1',status=status,
        source=file_binding(Path(__file__)),test=file_binding(Path(__file__).with_name('test_stage010_day_proxy_experiment.py')),
        protocol={'path':str(PROTOCOL),'sha256':PROTOCOL_SHA},bindings=bindings,artifacts=roles(out),
        quality_information_screen_pass=metrics['quality_information_screen_pass'],
        asset_roles={'protocol':'decision_asset','source_and_tests':'reproduction_asset','fits':'model_reproduction_asset',
          'predictions_and_metrics':'decision_asset','receipts_and_terminal':'qualification_evidence',
          'Stage009_feature_label_gzip':'derived_cache_bound_by_manifest','raw_DB_and_OHLC':'external_ignored_source_not_registered'},
        actual_fit_calls=FIT_CALLS,export_only=args.command=='export-only',financial_ready=False,production_qualified=False))
    return dict(status=status,actual_fit_calls=FIT_CALLS,output=str(out),quality_information_screen_pass=metrics['quality_information_screen_pass'])

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    fit=sub.add_parser('fit');fit.add_argument('--bindings',required=True);fit.add_argument('--output',required=True)
    export=sub.add_parser('export-only');export.add_argument('--experiment',required=True);export.add_argument('--output',required=True)
    args=p.parse_args();print(json.dumps(execute(args),ensure_ascii=False))

if __name__=='__main__': main()
