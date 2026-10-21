"""Fixed historical source-learnability diagnostic; never a production pool.

Preserve unknown outcomes in the evaluation universe, fit only past labels, and
compare paired loss identification bounds. These are not confidence intervals.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import warnings
from zoneinfo import ZoneInfo
from importlib.metadata import version
import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from stage044_asof_features import FEATURE_NAMES
from stage045_monthly_target_readiness import training_gate

LINE=Path(__file__).resolve().parents[1]
PARAMS=dict(C=.20,penalty='l2',solver='lbfgs',max_iter=1000,random_state=42)


def _inputs(y,p):
    y=np.asarray(y,dtype=float);p=np.asarray(p,dtype=float)
    if y.shape!=p.shape or not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('invalid_probability')
    if not np.isin(y[~np.isnan(y)],[0.,1.]).all():raise ValueError('invalid_binary_target')
    return y,p


def _loss(label,p,metric):
    if metric=='brier':return np.square(p-label)
    if metric=='logloss':
        clipped=np.clip(p,1e-15,1-1e-15)
        return -(label*np.log(clipped)+(1-label)*np.log1p(-clipped))
    if metric=='error':return ((p>=.5).astype(int)!=label).astype(float)
    raise ValueError('unknown_metric')


def loss_bounds(y,p,metric):
    y,p=_inputs(y,p);a,b=_loss(0,p,metric),_loss(1,p,metric)
    fixed=_loss(np.nan_to_num(y,nan=0),p,metric);known=~np.isnan(y)
    return np.where(known,fixed,np.minimum(a,b)),np.where(known,fixed,np.maximum(a,b))


def pair_bounds(y,p,prior,metric):
    y,p=_inputs(y,p);_,prior=_inputs(y,prior)
    a=_loss(0,prior,metric)-_loss(0,p,metric);b=_loss(1,prior,metric)-_loss(1,p,metric)
    fixed=_loss(np.nan_to_num(y,nan=0),prior,metric)-_loss(np.nan_to_num(y,nan=0),p,metric)
    known=~np.isnan(y)
    return np.where(known,fixed,np.minimum(a,b)),np.where(known,fixed,np.maximum(a,b))


def split_year(frame,year):
    cutoff=pd.Timestamp(f'{year}-01-01');nextcut=pd.Timestamp(f'{year+1}-01-01')
    train=frame[frame.asof_member & frame.point_target_identified & (frame.eval_date<cutoff) & (frame.label_end<cutoff)]
    test=frame[frame.asof_member & (frame.eval_date>=cutoff) & (frame.eval_date<nextcut)]
    return train.copy(),test.copy()


def test_gate(frame,year):
    data=frame[frame.asof_member & frame.maturity_clock_reached & frame.eval_date.dt.year.eq(year)]
    months=sorted(set(data.eval_date.dt.month))
    y=pd.to_numeric(data.robust_target,errors='raise')
    zero=int(y.eq(0).sum());one=int(y.eq(1).sum());products=int(data[y.notna()].product_vt_symbol.nunique())
    return dict(year=year,mature_months=len(months),class0_rows=zero,class1_rows=one,products=products,
                engineering_floor_pass=months==list(range(1,13)) and min(zero,one)>=24 and products>=6,
                required=dict(continuous_mature_months=12,min_each_class=24,min_products=6))


def join_inputs(target_path,feature_path,old_binding_path):
    target=pd.read_csv(target_path,parse_dates=['eval_date','label_end'])
    features=pd.read_csv(feature_path,parse_dates=['eval_date'])
    keys=['eval_date','product_vt_symbol']
    if len(target)!=19698 or len(features)!=19698:raise ValueError('full_cohort_row_count_changed')
    if target.duplicated(keys).any() or features.duplicated(keys).any():raise ValueError('duplicate_keys')
    wanted=keys+['domain_role',*FEATURE_NAMES]
    frame=target.merge(features[wanted],on=keys,how='outer',validate='one_to_one',indicator=True)
    if not frame._merge.eq('both').all():raise ValueError('feature_target_keys_differ')
    if not np.isfinite(frame.loc[frame.asof_member,list(FEATURE_NAMES)].to_numpy(float)).all():raise ValueError('asof_feature_missing_stop')
    old=json.loads(Path(old_binding_path).read_text())['products']
    canonical=lambda name:'.'.join([name.split('.')[0].upper(),name.split('.')[1]])
    names={canonical(name) for name in old}
    if len(names)!=18 or 'FU.SHFE' in names:raise ValueError('original18_contract')
    frame['original18']=frame.product_vt_symbol.map(canonical).isin(names)
    if set(frame.loc[frame.domain_role.eq('old18'),'product_vt_symbol'].map(canonical))!=names:
        raise ValueError('feature_original18_role_not_validated')
    if (frame.asof_member & frame.product_vt_symbol.map(canonical).eq('FU.SHFE')).any():raise ValueError('fixed_fu_in_competition')
    return frame.drop(columns='_merge')


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(target_path,feature_path,old_binding_path,output_path):
    if output_path.exists():raise ValueError('immutable_output_exists')
    frame=join_inputs(target_path,feature_path,old_binding_path)
    output_path.mkdir(parents=True);(output_path/'models').mkdir()
    started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();predictions=[];folds=[];fits=0
    for year in range(2018,2027):
        train,test=split_year(frame,year)
        fold=dict(year=year,cutoff=f'{year}-01-01',expanded_train=training_gate(frame,f'{year}-01-01'),
                  original18_train=training_gate(frame[frame.original18],f'{year}-01-01'),
                  test_gate=test_gate(frame,year),test_rows=len(test),formal_AC_run=False,usable_for_trading=False,
                  historical_upstream_hindsight=True,models={})
        folds.append(fold)
        if not fold['expanded_train']['engineering_floor_pass'] or test.empty:
            fold['status']='skipped_training_floor';continue
        fold['status']='diagnostic_fit_test_gate_pass' if fold['test_gate']['engineering_floor_pass'] else 'diagnostic_fit_test_gate_fail'
        ytrain=train.robust_target.astype(int).to_numpy();prior=float(ytrain.mean())
        test['class_prior_probability']=prior
        for arm,data in [('expanded',train),('original18',train[train.original18])]:
            gate=fold[arm+'_train']
            if not gate['engineering_floor_pass']:
                fold['models'][arm]=dict(status='skipped_training_floor',gate=gate);continue
            model=make_pipeline(StandardScaler(),LogisticRegression(**PARAMS))
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                model.fit(data[list(FEATURE_NAMES)].to_numpy(float),data.robust_target.astype(int).to_numpy())
            probability=model.predict_proba(test[list(FEATURE_NAMES)].to_numpy(float))[:,1]
            test[arm+'_probability']=probability
            scaler=model.named_steps['standardscaler'];clf=model.named_steps['logisticregression']
            path=output_path/'models'/f'{year}_{arm}_research_only.joblib';joblib.dump(model,path);fits+=1
            fold['models'][arm]=dict(status='fit_diagnostic_only',train_rows=len(data),
                     train_first_eval=str(data.eval_date.min().date()),train_last_eval=str(data.eval_date.max().date()),
                     max_train_label_end=str(data.label_end.max().date()),class_prior=float(data.robust_target.mean()),
                     scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),
                     coef=clf.coef_[0].tolist(),intercept=float(clf.intercept_[0]),n_iter=clf.n_iter_.tolist(),
                     model_path=str(path),sha256=_sha(path))
        test['usable_for_trading']=False;test['year']=year
        columns=['eval_date','product_vt_symbol','original18','reference_epoch','asof_member','label_end','maturity_clock_reached',
                 'label_observable','point_target_identified','robust_target','target_state','year','class_prior_probability','expanded_probability','usable_for_trading']
        if 'original18_probability' in test:columns.append('original18_probability')
        predictions.append(test[columns])
    if not predictions:raise ValueError('no_fold_passed_training_floor')
    pred=pd.concat(predictions,ignore_index=True);monthly=[];top10=[]
    nonoverlap=[];last_end=None
    for day,g in pred.groupby('eval_date',sort=True):
        if not g.maturity_clock_reached.all():continue
        ends=g.label_end.dropna().unique()
        if len(ends)!=1:raise ValueError('cohort_label_clock_not_common')
        if last_end is None or day>=last_end:
            nonoverlap.append(day);last_end=pd.Timestamp(ends[0])
    for day,g in pred.groupby('eval_date',sort=True):
        y=pd.to_numeric(g.robust_target,errors='raise').to_numpy(float)
        prior=g.class_prior_probability.to_numpy(float)
        for arm in ['expanded','original18']:
            column=arm+'_probability'
            if column not in g or g[column].isna().all():continue
            p=g[column].to_numpy(float)
            if not np.isfinite(p).all():raise ValueError('partial_predictions')
            record=dict(eval_date=str(day.date()),year=day.year,model=arm,N=len(g),known=int(np.isfinite(y).sum()),
                        mature=bool(g.maturity_clock_reached.all()),nonoverlap_60d=day in nonoverlap)
            for metric in ['brier','logloss','error']:
                lo,hi=loss_bounds(y,p,metric);dlo,dhi=pair_bounds(y,p,prior,metric)
                record.update({metric+'_lower':float(lo.mean()),metric+'_upper':float(hi.mean()),
                               metric+'_improvement_lower':float(dlo.mean()),metric+'_improvement_upper':float(dhi.mean()),
                               metric+'_known_only':None if not np.isfinite(y).any() else float(_loss(y[np.isfinite(y)],p[np.isfinite(y)],metric).mean())})
            monthly.append(record)
            ordered=g.sort_values([column,'product_vt_symbol'],ascending=[False,True],kind='stable')
            selected=ordered.head(min(10,len(ordered)));sy=pd.to_numeric(selected.robust_target,errors='raise')
            correct=int(sy.eq(1).sum());unknown=int(sy.isna().sum());k=len(selected)
            top10.append(dict(eval_date=str(day.date()),model=arm,K=k,positive_lower=correct,positive_upper=correct+unknown,
                              precision_lower=correct/k,precision_upper=(correct+unknown)/k,
                              products='|'.join(selected.product_vt_symbol),usable_for_trading=False))
    month=pd.DataFrame(monthly);annual=[]
    for (year,arm),g in month.groupby(['year','model'],sort=True):
        mature=g[g.mature]
        record=dict(year=int(year),model=arm,months=len(g),mature_months=len(mature),
                    evaluated_full_U_rows=int(g.N.sum()),identified_rows=int(g.known.sum()),
                    test_engineering_floor_pass=next(f['test_gate']['engineering_floor_pass'] for f in folds if f['year']==year))
        for col in g.columns:
            if col.endswith(('_lower','_upper','_known_only')):
                record[col]=None if mature.empty or mature[col].notna().sum()==0 else float(mature[col].mean())
        annual.append(record)
    annual=pd.DataFrame(annual)
    passing=[f['year'] for f in folds if f['status']=='diagnostic_fit_test_gate_pass']
    latest_date=pred.eval_date.max();latest=pred[pred.eval_date.eq(latest_date)].sort_values(['expanded_probability','product_vt_symbol'],ascending=[False,True]).copy()
    latest['research_rank']=range(1,len(latest)+1)
    summary=dict(started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                  market_model_fits=fits,prediction_rows=len(pred),predicted_months=int(pred.eval_date.nunique()),
                  test_gate_pass_years=passing,required_yearly_blocks=3,test_coverage_block_gate_pass=len(passing)>=3,
                  cross_cycle_predictive_validated=False,
                  original18_models_fitted=sum('fit_diagnostic_only'==f['models'].get('original18',{}).get('status') for f in folds),
                  latest_eval=str(latest_date.date()),latest_asof_products=len(latest),
                  robust_improvement_years=[int(r['year']) for r in annual.to_dict('records') if r['model']=='expanded' and r['brier_improvement_lower'] is not None and r['brier_improvement_lower']>0],
                  formal_AC_runs=0,formal_model_replaced=False,production_modified=False,orders=0,
                  label_source='conditional_static_economics_daily_open_reference_unitR',
                  temporal_interpretation='historical pseudo-OOS; upstream source strategy used these years during development',
                  calibration_claim=False,usable_for_trading=False,decision='RESEARCH_DIAGNOSTIC_ONLY_NO_PROMOTION')
    pred.to_csv(output_path/'all_asof_predictions.csv',index=False)
    month.to_csv(output_path/'monthly_loss_identification_bounds.csv',index=False)
    annual.to_csv(output_path/'annual_diagnostics.csv',index=False)
    pd.DataFrame(top10).to_csv(output_path/'research_top10_label_bounds.csv',index=False)
    latest.to_csv(output_path/'latest_full_universe_research_scores.csv',index=False)
    month[month.nonoverlap_60d].to_csv(output_path/'nonoverlap_60d_monthly_diagnostics.csv',index=False)
    (output_path/'folds.json').write_text(json.dumps(folds,ensure_ascii=False,indent=2)+'\n')
    (output_path/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    inputs={str(p):_sha(p) for p in [target_path,feature_path,old_binding_path]}
    code={str(p):_sha(p) for p in [Path(__file__),LINE/'tools/stage044_asof_features.py',LINE/'tools/stage045_monthly_target_readiness.py']}
    contract_path=output_path/'feature_contract.json'
    contract_path.write_text(json.dumps(dict(features=list(FEATURE_NAMES),params=PARAMS,
              definition_source=str(LINE/'tools/stage044_asof_features.py'),
              definition_sha256=_sha(LINE/'tools/stage044_asof_features.py'),
              scope='past-only exact same-epoch AM41, train-only scaler, conditional research target',
              original18_binding_sha256=_sha(old_binding_path),usable_for_trading=False),ensure_ascii=False,indent=2)+'\n')
    declared_classes={
        'all_asof_predictions.csv':'decision_asset',
        'latest_full_universe_research_scores.csv':'decision_asset',
        'research_top10_label_bounds.csv':'decision_asset',
        'feature_contract.json':'feature_contract',
        'monthly_loss_identification_bounds.csv':'qualification_evidence',
        'annual_diagnostics.csv':'qualification_evidence',
        'nonoverlap_60d_monthly_diagnostics.csv':'qualification_evidence',
        'folds.json':'qualification_evidence',
        'summary.json':'qualification_evidence',
    }
    declared_paths=[(output_path/name,kind) for name,kind in declared_classes.items()]
    for fold in folds:
        for model in fold['models'].values():
            if model.get('status')=='fit_diagnostic_only':declared_paths.append((Path(model['model_path']),'model_artifact'))
    assets=[dict(path=str(p),sha256=_sha(p),reproducibility_required=True,asset_class=kind,usable_for_trading=False)
            for p,kind in declared_paths]
    receipt_paths=[target_path.parent/'bindings.json',target_path.parent/'source_chain.json',feature_path.parent/'summary.json',
                   LINE/'outputs/stage046b_final/revalidation_receipt.json',LINE/'config/training_source_v1.json',
                   LINE/'outputs/stage041_monthly_label_protocol/summary.json',
                   LINE/'stages/20261020_2158_stage047_learnability_protocol.md']
    receipts={str(p):_sha(p) for p in receipt_paths if p.is_file()}
    manifest=dict(issued_at=summary['completed_at'],inputs=inputs,code=code,features=list(FEATURE_NAMES),params=PARAMS,assets=assets,
                  source_chain_receipt_hashes=receipts,
                  package_versions={name:version(name) for name in ['scikit-learn','numpy','pandas','scipy','joblib']},
                  production_or_official_release=False,git_staged=False,historical_economics_validated=False,actual_session_verified=False,
                  source_dependency_receipts='refer to target/features bindings and Stage046 source replay receipt')
    (output_path/'local_reproducibility_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['target_path','feature_path','old_binding_path','output_path']:parser.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(**vars(args)),ensure_ascii=False,indent=2))
