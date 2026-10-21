"""Independent numeric/identity review; imports no trainer or sklearn, never fits."""
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import gzip,hashlib,io,json,math
from collections import Counter
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[5]
LINE=ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT=Path(__file__).resolve().parent
EXP=LINE/'outputs/stage010_day_proxy_experiment/experiment'
PINS={'manifest.json':'fc1abeaffb5a15e9b782109fbbadedeab3fb56d4d40eb663d3ba3fb42f0a9b27',
    'metrics.json':'fd1d389573399709619ab9ac3172af422afc7c6195af4a0661e8efdf4559ddfc',
    'actual_terminal.json':'42ef5f676ac57a47b87d3e6e26663548d3e5499993747a0fceeab200cf8f7cec',
    'fits.jsonl':'28e5c62700127fbf9d04245b6288b70c1b589d3ac3453ba917f0f365d1167b71'}
SOURCE_SHA='c8ddce7c93184f793b9c42d2366ffd24b9f9651d5c4a96411bb0388098539ffa'
OWN=['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr','compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MARKET=['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing']
CI=['M1_lower','M1_upper','M0_lower','paired_lower','paired_upper','participation_lower','participation_upper','stress_M1_lower',
    'stress_M0_lower','stress_paired_lower','stress_paired_upper','stress_participation_lower','stress_participation_upper',
    'intercept_lower','momentum_lower','cash_lower','excluded_positive_proxy_lower','excluded_positive_proxy_upper']
BINDINGS={};CACHE={};RESIDUALS={}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def bound(item):
    p=Path(item['path']);key=str(p)
    if key not in CACHE:CACHE[key]=p.read_bytes()
    raw=CACHE[key]
    assert digest(raw)==item['sha256'],key
    if 'bytes'in item:assert len(raw)==item['bytes'],key
    BINDINGS[key]=dict(sha256=digest(raw),bytes=len(raw));return raw
def document(item):return json.loads(bound(item))
def binding(path):
    raw=Path(path).read_bytes();return dict(path=str(Path(path).resolve()),sha256=digest(raw),bytes=len(raw))
def csv_frame(raw,compressed=False):return pd.read_csv(io.BytesIO(gzip.decompress(raw) if compressed else raw),dtype=str,keep_default_na=False)
def number(frame,columns):
    for c in columns:frame[c]=pd.to_numeric(frame[c].replace('',np.nan),errors='raise')
def close(actual,expected,name,atol=2e-11,rtol=2e-10):
    a=np.asarray(actual,dtype=float);b=np.asarray(expected,dtype=float)
    assert a.shape==b.shape,(name,a.shape,b.shape)
    assert np.array_equal(np.isnan(a),np.isnan(b)),('NaN pattern',name)
    finite=np.isfinite(a)&np.isfinite(b)
    if finite.any():RESIDUALS[name]=float(np.max(np.abs(a[finite]-b[finite])))
    assert np.allclose(a,b,atol=atol,rtol=rtol,equal_nan=True),('numeric disagreement',name,RESIDUALS.get(name))
def compare(actual,expected,path='root'):
    if isinstance(expected,dict):
        assert set(actual)==set(expected),(path,'dictionary keys',set(actual)^set(expected))
        for k in expected:compare(actual[k],expected[k],path+'.'+k)
    elif isinstance(expected,list):
        assert len(actual)==len(expected),(path,'list length')
        for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+f'[{i}]')
    elif isinstance(expected,bool) or expected is None or isinstance(expected,str):assert actual==expected,(path,actual,expected)
    else:close(actual,expected,path)
def mean(values):
    v=np.asarray(values,float);v=v[np.isfinite(v)];return float(v.mean()) if len(v) else None
def group(family):return int.from_bytes(hashlib.sha256(family.encode()).digest(),'big')%2

def cohorts(p):
    known=p.label_identified.eq(1);unknown=~known;chosen=known&p.pred_M1.gt(0);any_chosen=p.pred_M1.gt(0)
    return dict(feature_ready_predictions=len(p),identified_rows=int(known.sum()),unknown_rows=int(unknown.sum()),
        unknown_label_states=dict(Counter(p.loc[unknown,'label_state'])),
        all_ready_M0_selection_rate=mean(p.pred_M0.gt(0)),all_ready_M1_selection_rate=mean(any_chosen),
        unknown_M0_selection_rate=mean(p.loc[unknown,'pred_M0'].gt(0)),unknown_M1_selection_rate=mean(p.loc[unknown,'pred_M1'].gt(0)),
        identified_M1_selected_rows=int(chosen.sum()),identified_M1_selected_dates=int(p.loc[chosen,'u_date'].nunique()),
        identified_M1_selected_families=int(p.loc[chosen,'family_id'].nunique()),
        all_ready_M1_selected_dates=int(p.loc[any_chosen,'u_date'].nunique()),all_ready_M1_selected_families=int(p.loc[any_chosen,'family_id'].nunique()),
        ambiguous_identified_rows=int(p.loc[known,'path_ambiguous'].sum()),unknown_rate=mean(unknown))

def daily(p,dates):
    p=p.loc[p.label_identified.eq(1)].copy()
    lo=p.proxy_lower.to_numpy(float);hi=p.proxy_upper.to_numpy(float)
    m0=p.pred_M0.gt(0).to_numpy(float);m1=p.pred_M1.gt(0).to_numpy(float)
    a=m1-m0;participation=p.groupby('u_date').pred_M1.transform(lambda s:s.gt(0).mean()).to_numpy(float)
    b=m1-participation;center=(lo+hi)/2;radius=(hi-lo)/2
    paired=a*center-np.abs(a)*radius;paired_hi=a*center+np.abs(a)*radius
    part=b*center-np.abs(b)*radius;part_hi=b*center+np.abs(b)*radius
    assert np.all(paired[a==0]==0) and np.all(paired_hi[a==0]==0)
    values=dict(M1_lower=m1*lo,M1_upper=m1*hi,M0_lower=m0*lo,paired_lower=paired,paired_upper=paired_hi,
        participation_lower=part,participation_upper=part_hi,stress_M1_lower=m1*lo-.8*m1,stress_M0_lower=m0*lo-.8*m0,
        stress_paired_lower=paired-.8*a,stress_paired_upper=paired_hi-.8*a,
        stress_participation_lower=part-.8*b,stress_participation_upper=part_hi-.8*b,
        intercept_lower=p.intercept_score.gt(0).to_numpy()*lo,momentum_lower=p.momentum_mask.to_numpy()*lo,cash_lower=np.zeros(len(p)),
        excluded_positive_proxy_lower=(1-m1)*np.maximum(lo,0),excluded_positive_proxy_upper=(1-m1)*np.maximum(hi,0),
        M1_selection_rate=m1,M0_selection_rate=m0,M0_mse_proxy_lower=(p.pred_M0.to_numpy()-lo)**2,
        M1_mse_proxy_lower=(p.pred_M1.to_numpy()-lo)**2,ambiguous_rate=p.path_ambiguous.to_numpy(float))
    table=pd.DataFrame(values);table['u_date']=p.u_date.to_numpy()
    output=table.groupby('u_date').mean();output['identified_rows']=p.groupby('u_date').size()
    return output.reindex(pd.Index(dates,name='u_date'))

def calibration(p):
    p=p.loc[p.label_identified.eq(1)];result={}
    for model in ('M0','M1'):
        column='pred_'+model;classes=np.searchsorted([-1.,0.,1.,4.],p[column].to_numpy(),side='right');rows=[]
        for i,name in enumerate(['lt_minus1','minus1_to_0','0_to_1','1_to_4','ge_4']):
            s=p.loc[classes==i];d=s.groupby('u_date')[[column,'proxy_lower','proxy_upper']].mean()
            rows.append(dict(bin=name,rows=len(s),dates=len(d),predicted=mean(d[column]),proxy_lower=mean(d.proxy_lower),proxy_upper=mean(d.proxy_upper)))
        result[model]=rows
    return result

def bootstrap(d):
    array=d[CI].to_numpy();n=len(d);block=min(60,n);needed=(n+block-1)//block
    rng=np.random.default_rng(20261018);samples=np.empty((2000,len(CI)));index_hash=hashlib.sha256()
    for i in range(2000):
        starts=rng.integers(n-block+1,size=needed)
        indexes=np.concatenate([np.arange(start,start+block,dtype=np.int64) for start in starts])[:n]
        index_hash.update(indexes.astype('<i8').tobytes());selected=array[indexes]
        finite=np.isfinite(selected);counts=finite.sum(0)
        samples[i]=np.divide(np.nansum(selected,axis=0),counts,out=np.full(len(CI),np.nan),where=counts>0)
    result={}
    for i,name in enumerate(CI):
        x=samples[:,i];x=x[np.isfinite(x)];interval=np.quantile(x,[.025,.975]) if len(x) else [None,None]
        result[name]=dict(mean=mean(array[:,i]),ci95_lower=float(interval[0]) if interval[0] is not None else None,
            ci95_upper=float(interval[1]) if interval[1] is not None else None,finite_source_days=int(np.isfinite(array[:,i]).sum()),finite_bootstrap_replicates=len(x))
    return dict(block_length=60,effective_block_length=block,repetitions=2000,seed=20261018,source_grid_days=n,
        common_indices_sha256=index_hash.hexdigest(),metrics=result,
        uncertainty_scope='fixed predictions; date-equal conditional proxy only; not research selection or cash uncertainty')

def positive(value):return value is not None and np.isfinite(value) and value>0

def run():
    manifest=document(dict(path=str(EXP/'manifest.json'),sha256=PINS['manifest.json']))
    assert manifest['schema']=='stage010_fixed_proxy_experiment_v1' and manifest['status']=='completed'
    assert manifest['actual_fit_calls']==72 and manifest['export_only'] is False
    assert manifest['source']['sha256']==SOURCE_SHA
    bound(manifest['source']);bound(manifest['test']);bound(manifest['protocol'])
    for item in manifest['artifacts']:bound(item)
    for name,pin in PINS.items():bound(dict(path=str(EXP/name),sha256=pin))
    terminal=json.loads(CACHE[str(EXP/'actual_terminal.json')]);reported=json.loads(CACHE[str(EXP/'metrics.json')])
    assert terminal['exit_code']==0 and terminal['status']=='completed' and terminal['actual_ridge_fit_calls']==72 and terminal['fixture'] is False
    assert terminal['command']=='fit' and terminal['financial_runs']==0 and terminal['network_calls']==0
    assert all(item['num_threads']==1 for item in terminal['threadpools'])
    data_manifest=document(manifest['bindings']['data_manifest']);receipt=document(manifest['bindings']['data_review'])
    assert receipt['qualified_for_fixed_proxy_experiment'] is True and receipt['data_manifest']['sha256']==manifest['bindings']['data_manifest']['sha256']
    assert receipt['real_economic_labels_ready'] is False and data_manifest['real_economic_labels_ready'] is False
    raw=bound(data_manifest['feature_label_csv']);data=csv_frame(raw,True)
    number(data,[*OWN,*MARKET,'atr20','gross_lower','gross_upper','proxy_lower','proxy_upper','feature_ready','label_identified','path_ambiguous'])
    dates=data_manifest['source_calendar_scope_dates'];assert len(dates)==4074 and len(data)==399252
    family_groups=data.family_id.map(group);ready=data.feature_ready.eq(1);labeled=data.label_identified.eq(1)
    assert np.isfinite(data.loc[ready,OWN+MARKET].to_numpy()).all()
    assert data.family_id.eq(data.product_id.str.replace(r'_F$','',regex=True)).all()
    assert data.event_id.is_unique and not data.duplicated(['product_id','u_date']).any()
    records=[json.loads(line) for line in CACHE[str(EXP/'fits.jsonl')].decode().splitlines()]
    expected_keys={(y,s,m) for y in range(2015,2027) for s in ('main','holdout_0','holdout_1') for m in ('M0','M1')}
    lookup={(r['test_year'],r['scope'],r['model']):r for r in records};assert len(records)==len(lookup)==72 and set(lookup)==expected_keys
    predictions={};replay_rows=Counter();fit_checks=[]
    for scope in ('main','holdout_0','holdout_1'):
        path=EXP/f'predictions_{scope}.csv.gz';p=csv_frame(CACHE[str(path)],True)
        numeric=['label_identified','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper','test_year','pred_M0','pred_M1','mask_M0','mask_M1','intercept_score','momentum_mask','cash_mask']
        number(p,numeric);assert p.event_id.is_unique and not {'open','high','low','close','volume'}.intersection(p)
        hold=None if scope=='main' else int(scope[-1]);predictions[scope]=p
        for year in range(2015,2027):
            cutoff=next(d for d in dates if d[:4]==str(year))
            train_mask=ready&labeled&data.u_date.ge('2010-01-01')&data.u_date.lt(cutoff)&data.label_known_date.ne('')&data.label_known_date.lt(cutoff)
            test_mask=ready&data.u_date.str.startswith(str(year))
            if hold is not None:train_mask&=family_groups.ne(hold);test_mask&=family_groups.eq(hold)
            train=data.loc[train_mask].sort_values(['u_date','event_id']);test=data.loc[test_mask].sort_values(['u_date','event_id'])
            observed=p.loc[p.test_year.eq(year)]
            assert observed.event_id.tolist()==test.event_id.tolist(),('prediction complete cohort',scope,year)
            assert observed.scope.eq(scope).all()
            for name in ('product_id','family_id','exchange','u_date','reference_epoch','planned_execution_date','status','history_state','label_state','label_known_date'):
                assert observed[name].tolist()==test[name].tolist(),('prediction copied identity',name,scope,year)
            for name in ('label_identified','path_ambiguous','gross_lower','gross_upper','proxy_lower','proxy_upper'):
                close(observed[name],test[name],f'copied_{name}_{scope}_{year}')
            u=train.u_date.to_numpy();unique,inverse,counts=np.unique(u,return_inverse=True,return_counts=True)
            w=1./counts[inverse];w/=w.mean();weight_hash=digest(w.astype('<f8').tobytes())
            ids=digest(('\n'.join(train.event_id)+'\n').encode());y=train.proxy_lower.to_numpy(float);W=w.sum()
            for model,features in [('M0',OWN),('M1',OWN+MARKET)]:
                r=lookup[year,scope,model];name=f'{year}_{scope}_{model}'
                assert r['fit_id']==name and r['feature_names']==features
                assert r['alpha']==1. and r['solver']=='cholesky' and r['fit_intercept'] is True and r['blas_threads']==1
                assert r['heldout_group']==hold and r['cutoff_exclusive']==cutoff and r['protocol_sha256']==manifest['protocol']['sha256']
                assert r['training_rows']==len(train) and r['training_dates']==len(unique) and r['training_ids_sha256']==ids
                assert r['weights_sha256']==weight_hash and r['training_families']==sorted(train.family_id.unique())
                assert r['max_u_date']==train.u_date.max() and r['max_label_known_date']==train.label_known_date.max()
                assert train.label_known_date.lt(cutoff).all() and train.u_date.lt(cutoff).all()
                assert set(r['weights_by_date'])==set(unique)
                close([r['weights_by_date'][d] for d in unique],w[np.searchsorted(u,unique)],'weights_by_date_'+name)
                X=train[features].to_numpy(float);mu=(X*w[:,None]).sum(0)/W;var=((X-mu)**2*w[:,None]).sum(0)/W
                scale=np.sqrt(var);scale[var==0]=1
                close(r['scaler']['mean'],mu,'scaler_mean_'+name);close(r['scaler']['var'],var,'scaler_var_'+name);close(r['scaler']['scale'],scale,'scaler_scale_'+name)
                close(r['intercept_reference'],np.average(y,weights=w),'intercept_reference_'+name)
                Z=(X-np.array(r['scaler']['mean']))/np.array(r['scaler']['scale']);beta=np.array(r['coef'])
                residual=Z@beta+r['intercept']-y
                gradient=Z.T@(w*residual)+beta;scale_grad=max(1.,float(np.max(np.abs(Z.T@(w*y)))))
                normalized=float(np.max(np.abs(gradient)))/scale_grad;intercept_residual=float(abs(w@residual))/W
                assert normalized<2e-9 and intercept_residual<2e-10,('saved coefficient normal equations',name,normalized,intercept_residual)
                testX=test[features].to_numpy(float);replay=((testX-np.array(r['scaler']['mean']))/np.array(r['scaler']['scale']))@beta+r['intercept']
                close(replay,observed['pred_'+model],'prediction_'+name)
                assert np.array_equal((replay>0).astype(int),observed['mask_'+model].to_numpy(int)),('fixed mask',name)
                assert np.array_equal((observed['pred_'+model]>0).astype(int),observed['mask_'+model].to_numpy(int))
                replay_rows[scope+'_'+model]+=len(test)
                fit_checks.append(dict(fit_id=name,training_rows=len(train),prediction_rows=len(test),training_ids_sha256=ids,
                    weights_sha256=weight_hash,normal_equation_relative_residual=normalized,intercept_weighted_residual=intercept_residual))
            assert np.array_equal(observed.momentum_mask.to_numpy(),test.r20_atr.gt(0).astype(int).to_numpy())
            close(observed.intercept_score,np.full(len(test),lookup[year,scope,'M0']['intercept_reference']),'intercept_score_'+scope+str(year))
            assert observed.cash_mask.eq(0).all()
    assert len(predictions['main'])==len(predictions['holdout_0'])+len(predictions['holdout_1'])
    assert set(predictions['main'].event_id)==set(predictions['holdout_0'].event_id)|set(predictions['holdout_1'].event_id)
    assert not set(predictions['holdout_0'].family_id)&set(predictions['holdout_1'].family_id)
    predictions['holdout_combined']=pd.concat([predictions['holdout_0'],predictions['holdout_1']],ignore_index=True)
    reports={};recomputed_daily={}
    for scope,p in predictions.items():
        reports[scope]={'annual':{}}
        for year in range(2015,2027):
            selected=p.loc[p.u_date.str.startswith(str(year))];grid=[d for d in dates if d[:4]==str(year)];d=daily(selected,grid)
            value=dict(cohort=cohorts(selected),date_equal_means={c:mean(d[c]) for c in d},source_grid_days=len(grid),no_identified_days=int(d.identified_rows.isna().sum()),calibration=calibration(selected))
            compare(value,reported['scopes'][scope]['annual'][str(year)],f'metrics.{scope}.{year}');reports[scope]['annual'][str(year)]=value
        for period,start in [('all_2015','2015-01-01'),('primary_2020','2020-01-01')]:
            selected=p.loc[p.u_date.ge(start)];grid=[d for d in dates if d>=start];d=daily(selected,grid);recomputed_daily[scope+'_'+period]=d
            saved=pd.read_csv(io.BytesIO(CACHE[str(EXP/f'daily_{scope}_{period}.csv')]),index_col=0)
            assert saved.index.tolist()==grid and set(saved)==set(d)
            for col in d:close(saved[col],d[col],f'daily.{scope}.{period}.{col}')
            value=dict(cohort=cohorts(selected),date_equal_means={c:mean(d[c]) for c in d},source_grid_days=len(grid),no_identified_days=int(d.identified_rows.isna().sum()))
            if scope=='main':value['bootstrap']=bootstrap(d)
            compare(value,reported['scopes'][scope][period],f'metrics.{scope}.{period}');reports[scope][period]=value
    main=reports['main'];primary=main['primary_2020'];full=main['all_2015'];metrics=primary['date_equal_means'];ci=primary['bootstrap']['metrics'];support=primary['cohort']
    gates=dict(primary_selected_dates_at_least_60=support['identified_M1_selected_dates']>=60,primary_selected_families_at_least_8=support['identified_M1_selected_families']>=8,
        primary_M1_lower_positive=positive(metrics['M1_lower']),primary_paired_lower_ci_positive=positive(ci['paired_lower']['ci95_lower']),
        primary_participation_lower_ci_positive=positive(ci['participation_lower']['ci95_lower']),all_2015_M1_lower_positive=positive(full['date_equal_means']['M1_lower']),
        all_2015_paired_lower_positive=positive(full['date_equal_means']['paired_lower']),all_2015_participation_lower_positive=positive(full['date_equal_means']['participation_lower']),
        same_mask_cost_1R_primary_positive=positive(metrics['stress_M1_lower']),four_complete_years_paired_lower_positive=sum(positive(main['annual'][str(y)]['date_equal_means']['paired_lower']) for y in range(2020,2026))>=4,
        partial_2026_M1_lower_positive=positive(main['annual']['2026']['date_equal_means']['M1_lower']))
    for held in (0,1):
        for metric in ('M1_lower','paired_lower'):gates[f'holdout_{held}_primary_{metric}_positive']=positive(reports[f'holdout_{held}']['primary_2020']['date_equal_means'][metric])
    gates={k:bool(v) for k,v in gates.items()};assert gates==reported['gates'] and bool(all(gates.values()))==reported['quality_information_screen_pass']==manifest['quality_information_screen_pass']
    input_states=dict(all_outer_rows=len(data),feature_ready_rows=int(ready.sum()),input_status=dict(Counter(data.status)),history_states=dict(Counter(data.history_state)),label_states=dict(Counter(data.label_state)),unready_rows=int((~ready).sum()))
    assert input_states==reported['input_states']
    results=dict(schema='stage012_independent_proxy_result_checks_v1',status='independent_numeric_identity_interval_metric_and_gate_checks_passed',
        root_actual_terminal_handoff=dict(session=38894,terminal_chunk='326eab',exit_code=0,actual_fit_calls=72,elapsed_seconds=45.66433912498178),
        bindings=BINDINGS,review_source=binding(__file__),actual_fit_records=len(records),fit_checks=fit_checks,full_prediction_replay_rows=dict(replay_rows),
        numerical_max_residuals=RESIDUALS,recomputed_gates=gates,quality_information_screen_pass=bool(all(gates.values())),
        primary_summary=primary,all_2015_summary=full,annual_main=main['annual'],
        holdout_primary={k:reports[k]['primary_2020'] for k in ('holdout_0','holdout_1','holdout_combined')},
        checks=dict(all72_training_keys_and_maturity=True,all72_weights_and_weighted_scalers=True,all72_saved_coefficients_satisfy_weighted_ridge_normal_equations=True,
            all_ready_test_cohorts_and_unknown_predictions_preserved=True,all_predictions_pure_coefficient_replay=True,all_masks_fixed_gt_zero=True,
            paired_intervals_common_mask_cancellation=True,participation_equal_rate_signed_interval=True,same_mask_1R_pressure=True,
            all_scope_year_period_metrics_and_saved_daily_tables=True,both_period_shared_60day_2000_seed_bootstraps=True,all_15_gates=True),
        severity=dict(Critical=0,Important=0,Minor=0),model_fits_by_reviewer=0,SQL_queries=0,financial_runs=0,network_calls=0,
        real_economic_labels_ready=False,financial_ready=False,production_qualified=False,
        conclusion='fixed_cross_market_feature_package_and_DAY_proxy_policy_failed_information_quality_screen; arithmetic accepted, no cash/alpha approval')
    (OUT/'actual_review_checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=results['status'],actual_fit_records=72,prediction_replay_rows=dict(replay_rows),quality_information_screen_pass=results['quality_information_screen_pass'],gates=gates,model_fits_by_reviewer=0,SQL_queries=0),ensure_ascii=False))

if __name__=='__main__':run()
