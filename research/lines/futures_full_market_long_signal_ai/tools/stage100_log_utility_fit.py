"""Frozen099 same-unit L/G curvature contrast; zero SQL and exact root auth only.

Target-domain failure is a scientific terminal state, never a row filter. Mature
training is checked at its cutoff; future closed outcomes are checked only after
all complete forward scores have been saved. No previous actual is invoked.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
_spec=importlib.util.spec_from_file_location('stage100_pure071',TOOLS/'stage071_settlement_narrow_fit.py')
legacy=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(legacy)
PROTOCOL=LINE/'outputs/stage099_log_utility_protocol/protocol.json'
PROTOCOL_SHA='0d51abfc6e466ccda0c293b23dad71928e06b0f5929e395150e90812e6f3582e'
STAGE_ROOT=LINE/'outputs/stage100_log_utility_fit'
COMMON=legacy.COMMON
IDENTITY=legacy.IDENTITY
LABEL_COLUMNS=legacy.LABEL_COLUMNS+['participation_state']
FEATURE_NAMES=COMMON+[c+'_missing' for c in COMMON]
ARMS=('L','G')
CUTOFFS=('2020-01-01','2023-01-01')
END='2026-10-16'
F=.0025
COST_INDEX=COMMON.index('stress_u_cost_R')
PARAMETERS=dict(alpha=1.,fit_intercept=True,solver='cholesky')
INPUT_ROLES={'common_npz','common_identity','narrow_labels','narrow_manifest'}
file_binding=legacy.file_binding
read_bound=legacy.read_bound
same_binding=legacy.same_binding
write_json=legacy.write_json
write_csv=legacy.write_csv
write_npz=legacy.write_npz


def source_bundle():
    return sorted([file_binding(TOOLS/n) for n in ('stage100_log_utility_fit.py',
        'test_stage100_log_utility_fit.py','stage071_settlement_narrow_fit.py')],key=lambda b:b['path'])


def target_domain(y,c):
    """Retain each row and raw value; no clipping, epsilon, deletion or repair."""
    y,c=np.asarray(y,float),np.asarray(c,float)
    if y.ndim!=1 or y.shape!=c.shape:raise ValueError('target arrays must be aligned vectors')
    a=np.full(len(y),np.nan);z=a.copy();wealth=a.copy();g=a.copy()
    state=np.full(len(y),'valid',dtype=object)
    cost_valid=np.isfinite(c)&(c>=0)
    state[~cost_valid]='invalid_cost_c'
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        a[cost_valid]=1/(1+8*c[cost_valid])
        a_valid=cost_valid&np.isfinite(a)&(a>0)&(a<=1)
        state[cost_valid&~a_valid]='invalid_budget_a'
        y_valid=np.isfinite(y)
        state[a_valid&~y_valid]='nonfinite_raw_y'
        z[a_valid&y_valid]=a[a_valid&y_valid]*y[a_valid&y_valid]
        z_valid=a_valid&y_valid&np.isfinite(z)
        state[a_valid&y_valid&~z_valid]='nonfinite_z'
        wealth[z_valid]=1+F*z[z_valid]
        wealth_valid=z_valid&np.isfinite(wealth)&(wealth>0)
        state[z_valid&~wealth_valid]='nonpositive_or_nonfinite_reference_wealth'
        g[wealth_valid]=np.log1p(F*z[wealth_valid])/F
        state[wealth_valid&~np.isfinite(g)]='nonfinite_log_utility'
    return pd.DataFrame(dict(raw_y=y,cost_c=c,a=a,z=z,L_target=z,G_target=g,
        reference_wealth=wealth,domain_state=state))


def _domain_summary(domain):
    invalid=domain.domain_state.ne('valid')
    return dict(status='domain_failure' if invalid.any() else 'valid',rows=len(domain),
        valid_rows=int((~invalid).sum()),invalid_rows=int(invalid.sum()),
        reason_counts=domain.domain_state.value_counts().sort_index().to_dict(),
        failure_meaning='reference_ruin_or_domain_failure' if invalid.any() else None,
        drop_clip_epsilon_or_retry=False)


def _head(common,scaler):
    x=np.asarray(common,float)
    if x.ndim!=2 or x.shape[1]!=26:raise ValueError('current common26 shape differs')
    missing=~np.isfinite(x)
    mean=np.asarray(scaler['common']['mean']);scale=np.asarray(scaler['common']['scale'])
    result=np.column_stack([(np.where(missing,mean,x)-mean)/scale,missing.astype(float)])
    if result.shape!=(len(x),52) or not np.isfinite(result).all():raise ValueError('nonfinite or non52 head')
    return result


def prepare_fold(frame,common,cutoff,next_cutoff):
    x=np.asarray(common,float)
    if x.shape!=(len(frame),26):raise ValueError('common26 mother shape differs')
    # Same accepted071 eligibility, before its finite-y assertion: invalid mature
    # y must produce a scientific domain failure rather than a runtime exception.
    use=(frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)
        &frame.label_state.eq('closed_complete_bar_model'))
    train=frame.loc[use].sort_values(['u_date','event_id']).copy()
    if train.empty:raise ValueError('empty own-policy mature training')
    prediction=legacy.prediction_slice(frame,cutoff,next_cutoff)
    ti=train.sequence_index.to_numpy(int);pi=prediction.sequence_index.to_numpy(int)
    weights=legacy.training_weights(train)
    domain=target_domain(train.net_R_stress.to_numpy(float),x[ti,COST_INDEX])
    report=dict(_domain_summary(domain),cutoff=cutoff,scope='main',
        max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()))
    training=train[LABEL_COLUMNS].reset_index(drop=True).copy()
    for name in weights:training[name]=weights[name].to_numpy()
    for name in domain:training[name]=domain[name].to_numpy()
    result=dict(train=train,prediction=prediction,weights=weights,training=training,domain_report=report)
    if report['status']=='domain_failure':return result
    accepted=legacy.training_slice(frame,cutoff)
    if not accepted.event_id.equals(train.event_id):raise ValueError('accepted071 mature identity differs')
    w=weights.sample_weight.to_numpy(float)
    stats=[legacy.finite_stats(x[ti,j],w) for j in range(26)]
    scaler=dict(common=dict(columns=COMMON,**{k:[s[k] for s in stats] for k in ('mean','var','scale','finite_count')}),
        feature_names=FEATURE_NAMES,head_dimension=52,scope='main',cutoff=cutoff,
        weighting='accepted071_own_mature_family_interval_uniqueness_equal_u_mean1',
        missing='train_finite_mean_imputation; unscaled26_missing_indicators; no_external_slot')
    result.update(scaler=scaler,train_head=_head(x[ti],scaler),prediction_head=_head(x[pi],scaler))
    return result


def fit_cell(frame,common,cutoff,next_cutoff,directory,on_fit=None,on_completed=None):
    prepared=prepare_fold(frame,common,cutoff,next_cutoff)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    training_binding=write_csv(directory/'training_identity_weights_targets.csv.gz',prepared['training'])
    domain=dict(prepared['domain_report'],training_identity_weights_targets=training_binding)
    write_json(directory/'training_domain.json',domain)
    if domain['status']=='domain_failure':return None,[],domain
    train,prediction=prepared['train'],prepared['prediction']
    x,xt=prepared['train_head'],prepared['prediction_head'];w=prepared['weights'].sample_weight.to_numpy(float)
    write_json(directory/'scaler.json',prepared['scaler'])
    prediction_binding=write_csv(directory/'prediction_identity.csv.gz',prediction[IDENTITY+['label_history_ready20']])
    identity_sha=hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()
    results=[];records=[]
    for arm in ARMS:
        target=directory/arm;target.mkdir()
        y=prepared['training'][arm+'_target'].to_numpy(float)
        estimator=legacy.Ridge(**PARAMETERS)
        if on_fit is not None:on_fit('main',cutoff,arm)
        with legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=w)
        if on_completed is not None:on_completed('main',cutoff,arm)
        scores=estimator.predict(xt)
        portable=dict(schema='stage100_portable_ridge_v1',scope='main',arm=arm,policy='NARROW',cutoff=cutoff,
            parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_),
            target='z' if arm=='L' else 'log1p(f*z)/f',f=F,
            reconstruction='bound_common_X + fold_train_only_scaler; no_saved52_head_cache')
        write_json(target/'portable_model.json',portable)
        with (target/'model.joblib').open('xb') as stream:legacy.joblib.dump(estimator,stream,compress=3)
        augmented=np.column_stack([x,np.ones(len(x))]);lhs=augmented.T@(w[:,None]*augmented)
        lhs[np.arange(52),np.arange(52)]+=1.;rhs=augmented.T@(w*y)
        beta=np.r_[estimator.coef_,estimator.intercept_]
        if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('52 normal equations differ')
        ne=write_npz(target/'normal_equations.npz',lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,weight_sum=np.array(w.sum()))
        if not np.allclose(scores,xt@np.asarray(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):
            raise ValueError('portable52 predictions differ')
        p=legacy.prediction_frame(prediction,scores,'NARROW',arm,cutoff);p['scope']='main';results.append(p)
        records.append(dict(scope='main',arm=arm,policy='NARROW',cutoff=cutoff,dimension=52,target=portable['target'],f=F,
            training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),
            prediction_rows=len(p),selected=int(p.selected.sum()),training_identity_sha256=identity_sha,
            max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
            training_identity_weights_targets=training_binding,prediction_identity=prediction_binding,
            scaler=file_binding(directory/'scaler.json'),training_domain=file_binding(directory/'training_domain.json'),
            portable_model=file_binding(target/'portable_model.json'),model=file_binding(target/'model.joblib'),
            normal_equations=ne,normal_equation_max_abs_residual=float(np.max(np.abs(lhs@beta-rhs))),full_head_cache_saved=False))
    return pd.concat(results,ignore_index=True),records,domain


def oos_domain(frame,common):
    """Post-prediction audit, never a mask for training, prediction or action."""
    x=np.asarray(common,float)
    if x.shape!=(len(frame),26):raise ValueError('common26 mother shape differs')
    use=(frame.u_date.ge(CUTOFFS[0])&frame.u_date.le(END)&frame.label_state.eq('closed_complete_bar_model')
        &frame.label_known_date.ne('')&frame.label_known_date.le(END))
    selected=frame.loc[use]
    domain=target_domain(selected.net_R_stress.to_numpy(float),x[selected.sequence_index.to_numpy(int),COST_INDEX])
    projection=frame[LABEL_COLUMNS].copy()
    for col in ('raw_y','cost_c','a','z','L_target','G_target','reference_wealth'):projection[col]=np.nan
    projection['domain_state']='not_evaluated_original_state'
    projection['domain_evaluated']=use.astype(np.int8)
    for col in domain:projection.loc[use,col]=domain[col].to_numpy()
    report=dict(_domain_summary(domain),scope='forward_closed_known_by_end',start=CUTOFFS[0],end=END,
        checked_after_complete_predictions=True,full_mother_rows=len(frame),
        original_label_states=frame.label_state.value_counts().to_dict(),unevaluated_rows=int((~use).sum()),
        unknown_open_cancel_targets_remain_null=True,used_as_prediction_or_action_gate=False)
    return report,projection


def opportunity_metrics(predictions,projection,all_families):
    linked=predictions.merge(projection[['event_id','label_state','participation_state','label_known_date',
        'domain_evaluated','domain_state','L_target','G_target']],on='event_id',validate='many_to_one')
    linked['year']=linked.u_date.str[:4]
    years=sorted(linked.year.unique())
    def one(g,arm,**keys):
        known=g.domain_evaluated.eq(1)&g.domain_state.eq('valid')
        ready=known&g.history_ready20.eq(1);selected=g.selected.eq(1)
        return dict(arm=arm,**keys,rows=len(g),selected=int(selected.sum()),
            closed_known_valid=int(known.sum()),closed_action_ready_known=int(ready.sum()),
            mse_own_target_closed_known=float(np.mean((g.loc[known,'score']-g.loc[known,arm+'_target'])**2)) if known.any() else None,
            selected_nonclosed=int((selected&~g.label_state.eq('closed_complete_bar_model')).sum()),
            selected_target_unknown_or_invalid=int((selected&~known).sum()),label_states=g.label_state.value_counts().to_dict())
    overall=[];annual=[];family_year=[]
    for arm in ARMS:
        a=linked.loc[linked.arm.eq(arm)];overall.append(one(a,arm,scope='main'))
        for year in years:
            v=a.loc[a.year.eq(year)];annual.append(one(v,arm,scope='main',year=year))
            for family in all_families:
                family_year.append(one(v.loc[v.family_id.eq(family)],arm,scope='main',family_id=family,year=year))
    return dict(schema='stage100_opportunity_metrics_v1',overall=overall,annual=annual,family_year=family_year,
        all_families_including_zero=True,predictive_error_is_not_cash_value=True,arms_have_different_target_units=False,
        same_budget_unit_but_different_curvature=True)


def _csv(binding):
    return pd.read_csv(io.BytesIO(read_bound(binding)),compression='gzip',usecols=LABEL_COLUMNS,dtype=str,keep_default_na=False)


def load_inputs(inputs,protocol):
    for role,binding in protocol['input_roles'].items():
        if not same_binding(inputs[role],binding):raise ValueError('frozen099 input differs: '+role)
    narrow=json.loads(read_bound(inputs['narrow_manifest']))
    if (narrow.get('schema')!='stage070_narrow_labels_v1' or narrow.get('status')!='completed' or narrow.get('mode')!='actual'
            or not same_binding(narrow.get('labels_narrow',{}),inputs['narrow_labels'])):raise ValueError('accepted NARROW manifest differs')
    frame=_csv(inputs['narrow_labels'])
    # Do not call071.validate_labels here: its global closed-y finite assertion
    # would precheck future target domain before complete forward predictions.
    legacy._numeric(frame,['sequence_index','u_index','entry_index','exit_index','net_R_stress','label_history_ready20'])
    for col in ('sequence_index','u_index'):
        v=frame[col].to_numpy(float)
        if not np.isfinite(v).all() or not np.equal(v,np.floor(v)).all():raise ValueError('noninteger mother identity')
        frame[col]=v.astype(np.int64)
    if (len(frame)!=399252 or frame.event_id.duplicated().any() or not np.array_equal(frame.sequence_index,np.arange(399252))
            or not frame.label_history_ready20.isin([0,1]).all() or not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all()
            or frame.duplicated(['product_id','u_date']).any() or frame.product_id.nunique()!=98
            or frame.product_id.str.split('.').str[0].nunique()!=6 or int(frame.u_date.ge(CUTOFFS[0]).sum())!=161014):
        raise ValueError('accepted complete mother identity/readiness differs')
    frame['label_history_ready20']=frame.label_history_ready20.astype(np.int8)
    order_sha=hashlib.sha256(('\n'.join(frame.event_id)+'\n').encode()).hexdigest()
    identity=json.loads(read_bound(inputs['common_identity']))
    if (identity.get('rows')!=399252 or identity.get('columns')!=COMMON or identity.get('event_ids_sha256')!=order_sha
            or not same_binding(identity.get('common',{}),inputs['common_npz'])):raise ValueError('accepted common identity differs')
    with np.load(io.BytesIO(read_bound(inputs['common_npz'])),allow_pickle=False) as saved:
        if saved['columns'].tolist()!=COMMON or saved['common'].shape!=(399252,26):raise ValueError('accepted common26 schema differs')
        common=saved['common'].astype(np.float64)
    return frame,common


def authorize(args):
    out=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in out.parents:raise ValueError('output outside Stage100 root')
    if out.exists():raise FileExistsError('fresh output required; no automatic retry')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen099 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes())
    binding=file_binding(args.authorization)
    if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(binding));required=dict(schema='stage099_exact_root_authorization_v1',authorized_by='root',stage='fit',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root100 authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('exact fit source/test bindings differ')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('fit input roles differ')
    for role,b in protocol['input_roles'].items():
        if not same_binding(auth['input_bindings'][role],b):raise ValueError('authorization frozen input differs: '+role)
    return out,protocol,auth,binding


def _check_complete_predictions(predictions,frame):
    expected=set(frame.loc[frame.u_date.ge(CUTOFFS[0]),'event_id'])
    if len(predictions)!=322028 or predictions.duplicated(['event_id','arm']).any() or set(predictions.arm)!=set(ARMS):
        raise ValueError('full322028 main predictions differ')
    for arm in ARMS:
        if set(predictions.loc[predictions.arm.eq(arm),'event_id'])!=expected:raise ValueError('full forward mother shrank')


def run_actual(out,protocol,auth,authorization_binding):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();attempted=completed=0
    write_json(out/'actual_started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),
        source_bundle=bundle,protocol=file_binding(PROTOCOL),authorization=authorization_binding,fixture=False))
    write_json(out/'input_bindings.json',auth['input_bindings'])
    def journal(name,scope,cutoff,arm,count):
        with (out/name).open('a') as stream:
            stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,arm=arm,count=count))+'\n');stream.flush()
    def on_fit(scope,cutoff,arm):
        nonlocal attempted
        attempted+=1;journal('fit_attempts.jsonl',scope,cutoff,arm,attempted)
    def on_completed(scope,cutoff,arm):
        nonlocal completed
        completed+=1;journal('fit_completed.jsonl',scope,cutoff,arm,completed)
    try:
        frame,common=load_inputs(auth['input_bindings'],protocol)
        predictions=[];records=[];training_domains=[];main_binding=partial_binding=oos_binding=metrics_binding=None
        for i,cutoff in enumerate(CUTOFFS):
            p,r,domain=fit_cell(frame,common,cutoff,CUTOFFS[i+1] if i+1<len(CUTOFFS) else None,
                out/'folds'/cutoff,on_fit=on_fit,on_completed=on_completed)
            training_domains.append(domain);records.extend(r)
            if domain['status']=='domain_failure':break
            predictions.append(p)
            write_csv(out/'folds'/cutoff/'predictions_main.csv.gz',p)
            print(json.dumps(dict(phase='fit_cell_complete',cutoff=cutoff,completed=completed)),flush=True)
        oos_checked=False;oos_report=None
        train_pass=all(d['status']=='valid' for d in training_domains) and len(training_domains)==len(CUTOFFS)
        combined=pd.concat(predictions,ignore_index=True) if predictions else None
        if train_pass:
            if attempted!=4 or completed!=4:raise ValueError('fixed4 fit budget differs')
            _check_complete_predictions(combined,frame)
            # These bytes exist before future domain is ever evaluated.
            main_binding=write_csv(out/'predictions_main.csv.gz',combined)
            oos_report,projection=oos_domain(frame,common);oos_checked=True
            oos_binding=write_csv(out/'domain_projection.csv.gz',projection)
            write_json(out/'opportunity_metrics.json',opportunity_metrics(combined,projection,sorted(frame.family_id.unique())))
            metrics_binding=file_binding(out/'opportunity_metrics.json')
        elif combined is not None:
            partial_binding=write_csv(out/'partial_predictions_main.csv.gz',combined)
        domain_pass=train_pass and oos_checked and oos_report['status']=='valid'
        status='completed' if domain_pass else 'domain_failure'
        report=dict(schema='stage100_log_utility_domain_v1',status='valid' if domain_pass else 'domain_failure',
            domain_pass=domain_pass,cash_eligible=domain_pass,training_folds=training_domains,oos_checked=oos_checked,oos_domain=oos_report,
            f=F,raw='net_R_stress',a='1/(1+8*stress_u_cost_R)',L='a*raw',G='log1p(f*L)/f',
            oos_prediction_binding_before_check=main_binding,whole_candidate_fail_stop=True,unknown_not_zero=True,
            interpretation='isolated_u_plan_continuous_budget_utility_proxy_not_actual_joint_cash_log',automatic_retry=False)
        write_json(out/'domain_report.json',report);write_json(out/'fit_records.json',records)
        saved_rows=len(combined) if combined is not None else 0
        write_json(out/'summary.json',dict(schema='stage100_fit_summary_v1',status=status,actual_fit_calls_completed=completed,
            prediction_rows=saved_rows,complete_main_predictions=main_binding is not None,head_dimension=52,mother_rows=len(frame),
            mother_label_states=frame.label_state.value_counts().to_dict(),domain_pass=domain_pass,cash_eligible=domain_pass,
            full_head_cache_saved=False,strict_pit_claim=False,goal_complete=False,
            runtime=dict(python=sys.version,sklearn=legacy.sklearn.__version__)))
        if source_bundle()!=bundle:raise ValueError('source changed during fit actual')
        write_json(out/'actual_terminal.json',dict(status=status,completed=domain_pass,execution_completed=True,exit_code=0,
            actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,new_cash_accounts=0,
            new_labels=0,downloads=0,whole_database_hashes=0,prediction_rows=saved_rows,domain_pass=domain_pass,cash_eligible=domain_pass,
            fixture=False,automatic_retry=False,elapsed_seconds=time.monotonic()-started))
        roles={'predictions_main.csv.gz':'complete_main_cash_scores_before_OOS_domain_check','partial_predictions_main.csv.gz':'partial_forward_scores_not_cash_eligible',
            'domain_projection.csv.gz':'full_mother_postprediction_domain_projection','domain_report.json':'whole_candidate_domain_verdict',
            'actual_started.json':'actual_start_audit','actual_terminal.json':'actual_terminal','input_bindings.json':'bound_input_references',
            'fit_attempts.jsonl':'fit_attempt_journal','fit_completed.jsonl':'fit_completion_journal','fit_records.json':'all_model_bindings',
            'opportunity_metrics.json':'annual_all_family_including_zero_target_state_metrics','summary.json':'run_summary'}
        artifacts=[]
        for path in sorted(out.rglob('*')):
            if not path.is_file():continue
            relative=str(path.relative_to(out))
            role=roles.get(relative,{'scaler.json':'fold_train_only_scaler','training_identity_weights_targets.csv.gz':'fold_mature_training_IDs_weights_both_targets',
                'prediction_identity.csv.gz':'fold_complete_prediction_identity','training_domain.json':'fold_mature_domain_verdict',
                'predictions_main.csv.gz':'fold_complete_forward_scores','model.joblib':'ridge_model','portable_model.json':'portable_ridge52',
                'normal_equations.npz':'ridge53_normal_equations_including_intercept'}.get(path.name,'audit_artifact'))
            artifacts.append(dict(file_binding(path),role=role,reproducibility_required=True,raw_ohlc=False))
        manifest=dict(schema='stage100_log_utility_fit_v1',status=status,mode='actual',completed=domain_pass,execution_completed=True,
            protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,authorization=authorization_binding,
            terminal=file_binding(out/'actual_terminal.json'),source_bundle=bundle,input_bindings=auth['input_bindings'],
            predictions_main=main_binding,partial_predictions_main=partial_binding,domain_report=file_binding(out/'domain_report.json'),
            domain_projection=oos_binding,opportunity_metrics=metrics_binding,fit_records=file_binding(out/'fit_records.json'),artifacts=artifacts,
            actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,
            prediction_rows=saved_rows,domain_pass=domain_pass,cash_eligible=domain_pass,goal_complete=False,production_qualified=False)
        write_json(out/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (out/'actual_terminal.json').exists():write_json(out/'actual_terminal.json',dict(status='failed',completed=False,execution_completed=False,exit_code=1,
            actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,
            domain_pass=False,cash_eligible=False,error_type=type(error).__name__,error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-sha256','authorization','authorization-sha256'):parser.add_argument('--'+name,required=True)
    out,protocol,auth,binding=authorize(parser.parse_args(argv))
    if legacy.sklearn.__version__!='1.6.1':raise ValueError('accepted sklearn1.6.1 runtime required')
    manifest=run_actual(out,protocol,auth,binding)
    print(json.dumps(dict(status=manifest['status'],output=str(out),actual_fit_calls_completed=manifest['actual_fit_calls_completed'],
        domain_pass=manifest['domain_pass'],cash_eligible=manifest['cash_eligible'])),flush=True)


if __name__=='__main__':main()
