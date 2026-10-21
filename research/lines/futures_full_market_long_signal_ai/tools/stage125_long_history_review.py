"""Independent 121 same-epoch calendar-month history, model and cash review.

No author calculators, research fitting, strategy replay or network. A single
read-only native SELECT independently reconstructs all source price pairs.
"""
from __future__ import annotations
import argparse, bisect, gzip, hashlib, io, json, math, os, sqlite3, time, traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='c9a9538de0160266624c2bbfd8912964a44b2cfda97e639d1079fb1614bd7421'
ID=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ARMS=('CONTROL','LONG_HISTORY');SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
WINDOWS=('primary_2020','cold_2023');COSTS=('base','stress')
AUDIT_HELPERS={'stage102_cash_adapter.py': '702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044', 'stage102_cash_core.py': '4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa', 'stage102_cash_diagnostics.py': '0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc', 'stage102_fit_checks.py': 'a7afe80d4a22f74857c1f48ca90b15467acb45385a019d4f00424c3429696e6a', 'stage102_native_checks.py': '5d869f86465e9e309b36baa9453644a004f1c0e2c4366e63e816164c57ec1ecd', 'stage102_target_math.py': '416ec9d4291e28e50e28e51de44c37a862e649d3de7ec9875bfddad90b279f6d'}

def lower_boundary(value):
    d = date.fromisoformat(value)
    return date(d.year - 1, d.month, 28 if d.month == 2 and d.day == 29 else d.day).isoformat()

def required_window(dates, index):
    """Open lower calendar boundary; no 252/365 source-row substitution."""
    return list(range(bisect.bisect_right(dates, lower_boundary(dates[index])), index + 1))

def legal_native_bar(row):
    if row is None or len(row) != 6 or row[5] != 'accepted':
        return False
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in row[:5]):
        return False
    o, h, l, c, _ = row[:5]
    return l <= min(o, c) and h >= max(o, c)

def qualified_economics(e):
    positive = lambda x: not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x) and x > 0
    return e.get('economics_status') == 'exact_epoch_metadata_snapshot' and positive(e.get('contract_multiplier')) and positive(e.get('round_lot')) and float(e['round_lot']).is_integer()

def independent_factors(dates, representatives, bars, economics):
    """Each factor fixes prev(v)'s representative before looking at v's bar."""
    assert len(dates) == len(representatives)
    result = []
    for i, day in enumerate(dates):
        previous = dates[i - 1] if i else ''
        epoch = representatives[i - 1] if i else ''
        a, b = bars.get((epoch, previous)), bars.get((epoch, day))
        if not i:
            reason = 'no_previous_mother_date'
        elif not epoch:
            reason = 'previous_reference_missing'
        elif not qualified_economics(economics.get(epoch, {})):
            reason = 'previous_reference_economics_unqualified'
        elif not legal_native_bar(a):
            reason = 'previous_bar_missing_or_invalid'
        elif not legal_native_bar(b):
            reason = 'current_bar_missing_or_invalid'
        else:
            reason = ''
        f = b[3] / a[3] if not reason else None
        if f is not None and (not math.isfinite(f) or f <= 0):
            f, reason = None, 'factor_nonfinite_or_nonpositive'
        result.append(dict(date=day, previous_date=previous, epoch=epoch,
                           previous_close=a[3] if legal_native_bar(a) else None,
                           current_close=b[3] if legal_native_bar(b) else None,
                           factor=f, observed=int(f is not None), reason=reason))
    return result

def independent_scalars(dates, factors):
    """Independent explicit fsum windows; never skips missing factors."""
    assert len(dates) == len(factors) and dates == sorted(set(dates))
    result = []
    for i, day in enumerate(dates):
        boundary = lower_boundary(day)
        indexes = required_window(dates, i)
        invalid = [k for k in indexes if factors[k] is None or not math.isfinite(factors[k]) or factors[k] <= 0]
        scalar = None
        if dates[0] > boundary:
            reason = 'insufficient_calendar_history'
        elif invalid:
            reason = 'incomplete_factor_window'
        else:
            try:
                scalar = math.expm1(math.fsum(math.log(factors[k]) for k in indexes))
            except (ValueError, OverflowError):
                pass
            if scalar is not None and math.isfinite(scalar):
                reason = ''
            else:
                scalar, reason = None, 'nonfinite_accumulation'
        result.append(dict(date=day, boundary=boundary, scalar=scalar, observed=int(scalar is not None),
                           required_factors=len(indexes), missing_factors=len(invalid), reason=reason))
    return result

def database_state(path):
    p = Path(path); s = p.stat()
    return dict(path=str(p.resolve()), bytes=s.st_size, inode=s.st_ino, mtime_ns=s.st_mtime_ns,
                wal_present=Path(str(p)+'-wal').exists(), shm_present=Path(str(p)+'-shm').exists())

def native_once(binding, calendar, output):
    """The audit's sole native SQL; no hashing, indicators or strategy replay."""
    before = database_state(binding['path'])
    for k, v in before.items():
        assert binding[k] == v, ('native snapshot', k)
    write(output/'native_query_started.json', dict(native_source_queries_started=1, database=before))
    bars = {}; epochs = set(); allowed = set(calendar)
    with sqlite3.connect('file:'+binding['path']+'?mode=ro&immutable=1', uri=True) as db:
        rows = db.execute('SELECT contract_epoch_id,trade_date,open,high,low,close,volume,quality_status FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date', (calendar[0], calendar[-1]))
        for epoch, day, o, h, l, c, volume, status in rows:
            assert day in allowed and (epoch, day) not in bars
            bars[(epoch, day)] = (o, h, l, c, volume, status); epochs.add(epoch)
    after = database_state(binding['path']); assert before == after
    assert len(bars) == 1552456 and len(epochs) == 9520
    report = dict(native_source_queries=1, native_contract_days=len(bars), native_epochs=len(epochs),
                  database_before=before, database_after=after, database_rehashed=False,
                  database_sha256_inherited=binding['sha256'])
    progress(output, 'native_read_complete', report)
    return bars, report

def bound(binding):
    raw=Path(binding['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==binding['sha256'],('binding SHA',binding['path'])
    size=binding.get('bytes',binding.get('size'))
    if size is not None:assert len(raw)==size,('binding bytes',binding['path'])
    return raw

def bind(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def audit_helpers():
    for name,sha in AUDIT_HELPERS.items():assert bind(LINE/'tools'/name)['sha256']==sha,('independent helper changed',name)
    import numpy as np
    import pandas as pd
    import stage102_cash_adapter as cash
    import stage102_cash_diagnostics as diagnostics
    from stage102_native_checks import review_native
    from stage102_fit_checks import load_labels,weights,stats,table,convert,compare_dict
    return np,pd,cash,diagnostics,review_native,load_labels,weights,stats,table,convert,compare_dict

def family_group(value):return int.from_bytes(hashlib.sha256(value.encode()).digest(),'big')%2

def identity_check(actual,expected,compare,label):
    assert actual.event_id.tolist()==expected.event_id.tolist(),label
    for key in ID:
        if key in ('sequence_index','u_index'):compare(pd.to_numeric(actual[key]),expected[key],label+'_'+key,atol=0,rtol=0)
        else:assert actual[key].tolist()==expected[key].tolist(),(label,key)

def head54(raw,observed,scalar,scaler,arm):
    finite=np.isfinite(raw);m=np.asarray(scaler['common']['mean']);z=np.asarray(scaler['common']['scale'])
    base=np.column_stack([(np.where(finite,raw,m)-m)/z,(~finite).astype(float),1-np.asarray(observed,int)])
    q=np.asarray(scalar,float);qz=np.where(np.isfinite(q),(q-scaler['scalar']['mean'])/scaler['scalar']['scale'],0.)
    return np.column_stack([base,qz if arm=='LONG_HISTORY'else np.zeros(len(q))]),base,qz

def held_diagnostics(predictions,labels,end):
    linked=predictions.loc[predictions.scope.ne('main')].merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one',sort=False)
    known=linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)&linked.label_known_date.ne('')&linked.label_known_date.le(end)&linked.history_ready20.eq(1)
    linked['diagnostic_known_domain']=known;linked['diagnostic_outcome_R']=linked.net_R_stress.where(known,np.nan)
    groups={};daily=[]
    for scope,g in linked.groupby('scope',sort=True):
        a=g.loc[g.arm.eq('CONTROL')].set_index('event_id');b=g.loc[g.arm.eq('LONG_HISTORY')].set_index('event_id').reindex(a.index)
        assert len(a)==len(b)and a.u_date.eq(b.u_date).all()
        domain=a.diagnostic_known_domain&b.diagnostic_known_domain
        z=pd.DataFrame(dict(u_date=a.loc[domain,'u_date'],delta_R=((b.selected-a.selected)*a.net_R_stress).loc[domain],mse_difference=((b.score-a.net_R_stress)**2-(a.score-a.net_R_stress)**2).loc[domain]))
        d=z.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_events=('delta_R','size'),mse_difference=('mse_difference','mean')).reset_index();d['scope']=scope;daily.append(d)
        point=float(d.delta_R.mean())if len(d)else None;disagree=b.selected.ne(a.selected)
        unresolved=~domain&~a.participation_state.eq('known_nonparticipation');unknown=int((disagree&unresolved).sum())
        states=pd.DataFrame(dict(state=a.label_state,disagreement=disagree.astype(int))).groupby('state').agg(full_events=('disagreement','size'),action_disagreements=('disagreement','sum')).reset_index().to_dict('records')
        groups[scope]=dict(nominal_pass=point is not None and point>=0,status='unsupported'if point is not None and point<0 else'unknown'if point is None or unknown else'supported',known_u_equal_mean_increment_R=point,known_common_events=int(domain.sum()),known_source_days=len(d),prediction_u_equal_MSE_difference=float(d.mse_difference.mean())if len(d)else None,full_mother_events=len(a),unknown_differential_selected_events=unknown,all_state_action_counts=states,unknown_R_bounds=None,annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()),prediction_u_equal_MSE_difference=float(v.mse_difference.mean()),known_source_days=len(v),known_events=int(v.known_events.sum()))for y,v in d.groupby(d.u_date.str[:4],sort=True)],cold_2023_view_mean_delta_R=float(d.loc[d.u_date.ge('2023-01-01'),'delta_R'].mean())if d.u_date.ge('2023-01-01').any()else None,meaning='closed_complete_bar_model and ready20 only; within-u all known rows mean including equal-action zero, then equal u; not cash/full opportunity value')
    return dict(schema='stage123_held_closed_diagnostic_v1',groups=groups,unknown_not_zero=True,cancellation_not_zero=True,full_policy_value_qualified=False,cash_return_qualified=False,contrast='LONG_HISTORY_minus_CONTROL'),pd.concat(daily,ignore_index=True),linked

def main_signal_diagnostics(labels,predictions,end):
    p=predictions.loc[predictions.scope.eq('main')]
    f=labels[['event_id','family_id','u_date','label_state','label_known_date','net_R_stress']].merge(p.pivot(index='event_id',columns='arm',values='selected'),on='event_id',validate='one_to_one',how='inner')
    f['actions_differ']=f.LONG_HISTORY.ne(f.CONTROL);f['closed_known']=f.label_state.eq('closed_complete_bar_model')&np.isfinite(f.net_R_stress)&f.label_known_date.ne('')&f.label_known_date.le(end);f['known_nonparticipation']=f.label_state.eq('known_nonparticipation');f['year']=f.u_date.str[:4]
    s=f.groupby(['year','label_state'],dropna=False).agg(rows=('event_id','size'),action_disagreements=('actions_differ','sum'),CONTROL_selected=('CONTROL','sum'),LONG_HISTORY_selected=('LONG_HISTORY','sum'),closed_known=('closed_known','sum')).reset_index()
    r=dict(main_prediction_rows_per_arm=len(f),full_mother_rows=len(labels),full_mother_label_states={str(k):int(v)for k,v in labels.label_state.value_counts(dropna=False).items()},unknown_differential_selected_events=int((f.actions_differ&~f.closed_known&~f.known_nonparticipation).sum()),known_nonparticipation_differential_selected_events=int((f.actions_differ&f.known_nonparticipation).sum()),unfilled_signal_label_uncertainty_is_not_cash_exposure=True)
    return r,s

def review_models(manifest,labels,scalar,observed,compare,table,weights,stats,compare_dict):
    root=Path(manifest['support_report']['path']).parent;inputs=manifest['input_bindings']
    with np.load(io.BytesIO(bound(inputs['common_npz'])),allow_pickle=False)as z:common=z['common'].copy();columns=z['columns'].tolist()
    identity=json.loads(bound(inputs['common_identity']));assert common.shape==(399252,26)and columns==identity['columns']and identity['event_ids_sha256']==hashlib.sha256(('\n'.join(labels.event_id)+'\n').encode()).hexdigest()
    support=json.loads(bound(manifest['support_report']));cells=[];prepared=[]
    for scope in SCOPES:
        for cutoff,stop in [('2020-01-01','2023-01-01'),('2023-01-01',None)]:
            mature=labels.label_state.eq('closed_complete_bar_model')&np.isfinite(labels.net_R_stress)&labels.u_date.lt(cutoff)&labels.label_known_date.ne('')&labels.label_known_date.lt(cutoff)
            future=labels.u_date.ge(cutoff)&(labels.u_date.lt(stop)if stop else True)
            if scope!='main':
                group=labels.family_id.map(family_group);mature&=group.ne(int(scope[-1]));future&=group.eq(int(scope[-1]))
            train=labels.loc[mature].sort_values(['u_date','event_id']);test=labels.loc[future].sort_values(['u_date','event_id']);ti=train.sequence_index.to_numpy(int);pi=test.sequence_index.to_numpy(int)
            unique,day,w=weights(train);q=scalar[ti];finite=np.isfinite(q);st=stats(q,w)
            if finite.any()and np.equal(q[finite],q[finite][0]).all():st=(float(q[finite][0]),0.,1.,int(finite.sum()))
            weighted={k:v for k,v in zip(('mean','var','scale','finite_count'),st)}
            positive=bool(finite.any()and q[finite].min()<q[finite].max()and np.isfinite(st[1])and st[1]>0)
            d=train.loc[finite];cells.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),finite_rows=int(finite.sum()),nonzero_rows=int(np.count_nonzero(q[finite])),weighted_stats=weighted,positive_weighted_variation=positive,observed_families=d.family_id.value_counts().to_dict(),observed_months=d.u_date.str[:7].value_counts().sort_index().to_dict()))
            prepared.append((scope,cutoff,train,test,ti,pi,unique,day,w,weighted))
    eligible=all(c['positive_weighted_variation']for c in cells)
    compare_dict(support,dict(schema='stage123_scalar_support_v1',status='supported'if eligible else'unsupported_scalar_support',cash_eligible=eligible,cells=cells,checked_before_any_fit=True,availability_is_not_row_or_action_gate=True,finite_support_does_not_establish_sample_sufficiency=True),'six_cell_support')
    if not eligible:
        assert manifest['status']=='unsupported_scalar_support'and manifest['actual_fit_calls_completed']==manifest['actual_fit_calls_attempted']==0 and manifest['cash_eligible']is False and manifest['prediction_rows']==0
        for key in ('predictions','predictions_main','predictions_holdout','held_diagnostic'):assert manifest[key]is None
        assert not(root/'folds').exists()
        return None,None,None,None,dict(cash_eligible=False,models_checked=0,predictions_checked=0,scalar_support=support)
    assert manifest['status']=='completed'and manifest['cash_eligible']is True
    pred=table(manifest['predictions'])
    for key in ('sequence_index','u_index','score','selected','history_ready20','external_missing'):pred[key]=pd.to_numeric(pred[key])
    assert len(pred)==644056 and pred.scope.isin(SCOPES).all() and pred.arm.isin(ARMS).all() and pred.policy.eq('NARROW').all() and not pred.duplicated(['scope','event_id','arm']).any()
    records=json.loads((root/'fit_records.json').read_text());models=[];names=columns+[c+'_missing'for c in columns]+['external_missing','fixed12_calendar_month_return_chain']
    for scope,cutoff,train,test,ti,pi,unique,day,w,qstats in prepared:
        cell=root/'folds'/scope/cutoff;saved=pd.read_csv(cell/'training_identity_weights.csv.gz',dtype=str,keep_default_na=False);identity_check(saved,train,compare,'training_identity')
        assert saved.label_known_date.tolist()==train.label_known_date.tolist()and saved.label_state.eq('closed_complete_bar_model').all()
        for key,value in [('uniqueness',unique),('u_normalized_weight',day),('sample_weight',w)]:compare(pd.to_numeric(saved[key]),value,'training_'+key,atol=1e-10)
        pi_saved=pd.read_csv(cell/'prediction_identity.csv.gz',dtype=str,keep_default_na=False);identity_check(pi_saved,test,compare,'prediction_identity');assert np.array_equal(pd.to_numeric(pi_saved.label_history_ready20),test.label_history_ready20)
        scaler=json.loads((cell/'scaler.json').read_text());st=np.asarray([stats(common[ti,j],w)for j in range(26)])
        for i,key in enumerate(('mean','var','scale','finite_count')):compare(scaler['common'][key],st[:,i],'common_scaler_'+key,atol=1e-10)
        compare_dict(scaler['scalar'],qstats,'scalar_stats')
        assert scaler['common']['columns']==columns and scaler['feature_names']==names and scaler['scope']==scope and scaler['cutoff']==cutoff and scaler['common_units']=='accepted_original_2N'
        trainx,base,qz=head54(common[ti],observed[ti],scalar[ti],scaler,'LONG_HISTORY');testx,testbase,testqz=head54(common[pi],observed[pi],scalar[pi],scaler,'LONG_HISTORY')
        with np.load(cell/'normalized_inputs.npz',allow_pickle=False)as cache:
            for key,value in [('train_base',base),('prediction_base',testbase),('train_scalar',qz),('prediction_scalar',testqz),('y',train.net_R_stress),('sample_weight',w),('train_sequence_index',ti),('prediction_sequence_index',pi)]:compare(cache[key],value,'normalized_'+key,atol=1e-10)
        for arm in ARMS:
            model=json.loads((cell/arm/'portable_model.json').read_text());coef=np.asarray(model['coef']);intercept=model['intercept']
            assert model['schema']=='stage123_portable_ridge_v1'and model['scope']==scope and model['arm']==arm and model['policy']=='NARROW'and model['cutoff']==cutoff and model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky')and model['feature_names']==names and len(coef)==54
            x=trainx if arm=='LONG_HISTORY'else np.column_stack([base,np.zeros(len(base))]);xt=testx if arm=='LONG_HISTORY'else np.column_stack([testbase,np.zeros(len(testbase))])
            a=np.column_stack([x,np.ones(len(x))]);lhs=a.T@(w[:,None]*a);lhs[np.arange(54),np.arange(54)]+=1.;rhs=a.T@(w*train.net_R_stress.to_numpy(float));beta=np.r_[coef,intercept]
            with np.load(cell/arm/'normal_equations.npz',allow_pickle=False)as ne:
                compare(ne['lhs'],lhs,'normal_equation_lhs',atol=2e-7);compare(ne['rhs'],rhs,'normal_equation_rhs',atol=2e-7);compare(ne['coefficient_with_intercept'],beta,'portable_beta',atol=1e-12);compare(ne['weight_sum'],w.sum(),'normal_weights',atol=1e-10)
            residual=float(np.max(np.abs(lhs@beta-rhs)));assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8)
            actual=pred.loc[pred.scope.eq(scope)&pred.cutoff.eq(cutoff)&pred.arm.eq(arm)];identity_check(actual,test,compare,'all_prediction_IDs');scores=xt@coef+intercept;compare(actual.score,scores,'all644056_scores',atol=1e-9)
            assert np.array_equal(actual.external_missing,1-observed[pi])and np.array_equal(actual.history_ready20,test.label_history_ready20)and np.array_equal(actual.selected,(test.label_history_ready20.eq(1).to_numpy()&np.isfinite(scores)&(scores>0)).astype(int))
            rec=next(r for r in records if(r['scope'],r['cutoff'],r['arm'])==(scope,cutoff,arm))
            for key,value in dict(policy='NARROW',dimension=54,target='net_R_stress',training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),training_external_missing=int((1-observed[ti]).sum()),prediction_rows=len(test),prediction_external_missing=int((1-observed[pi]).sum()),selected=int(actual.selected.sum()),max_u_date=train.u_date.max(),max_label_known_date=train.label_known_date.max(),training_identity_sha256=hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()).items():assert rec[key]==value,(scope,cutoff,arm,key)
            assert rec['training_label_states']==train.label_state.value_counts().to_dict()
            models.append(dict(scope=scope,cutoff=cutoff,arm=arm,training_rows=len(train),prediction_rows=len(test),selected=int(actual.selected.sum()),normal_equation_max_residual=residual,scalar_coefficient=float(coef[-1])))
    assert len(models)==len(records)==manifest['actual_fit_calls_completed']==manifest['actual_fit_calls_attempted']==12 and manifest['prediction_rows']==644056
    order=[(scope,cutoff,arm)for scope in SCOPES for cutoff in CUTOFFS for arm in ARMS]
    for filename,counter in [('fit_attempts.jsonl','attempt'),('fit_completed.jsonl','completed')]:
        events=[json.loads(line)for line in(root/filename).read_text().splitlines()if line]
        assert [(v['scope'],v['cutoff'],v['arm'])for v in events]==order and [v[counter]for v in events]==list(range(1,13))
    for key,mask in [('predictions_main',pred.scope.eq('main')),('predictions_holdout',pred.scope.ne('main'))]:
        saved=table(manifest[key]);expected=pred.loc[mask];assert len(saved)==322028 and expected.groupby('arm').size().eq(161014).all()
        assert set(saved.columns)==set(expected.columns)
        for col in saved:
            if col in ('sequence_index','u_index','score','selected','history_ready20','external_missing'):compare(pd.to_numeric(saved[col]),expected[col],'split_'+col,atol=1e-12 if col=='score'else 0,rtol=0)
            else:assert saved[col].tolist()==expected[col].tolist(),(key,col)
    held,daily,linked=held_diagnostics(pred,labels,'2026-10-16');compare_dict(json.loads(bound(manifest['held_diagnostic'])),held,'held_report')
    saved=table(manifest['held_daily']);assert saved[['u_date','scope']].equals(daily[['u_date','scope']]);compare(pd.to_numeric(saved.delta_R),daily.delta_R,'held_daily_R');compare(pd.to_numeric(saved.mse_difference),daily.mse_difference,'held_daily_MSE');assert np.array_equal(pd.to_numeric(saved.known_events),daily.known_events)
    saved=table(manifest['held_linkage']);assert saved.event_id.tolist()==linked.event_id.tolist()and saved.arm.tolist()==linked.arm.tolist()and saved.scope.tolist()==linked.scope.tolist()
    assert saved.diagnostic_known_domain.eq('True').tolist()==linked.diagnostic_known_domain.tolist();compare(pd.to_numeric(saved.diagnostic_outcome_R.replace('',np.nan)),linked.diagnostic_outcome_R,'held_unknown_null')
    metrics=json.loads((root/'opportunity_metrics.json').read_text());g=pred.merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one');g['year']=g.u_date.str[:4]
    for role,keys in [('overall',['scope','arm']),('annual',['scope','arm','year']),('family_year',['scope','arm','family_id','year'])]:
        expected=[]
        for names_,v in g.groupby(keys,sort=True):
            if not isinstance(names_,tuple):names_=(names_,)
            known=v.label_state.eq('closed_complete_bar_model')&v.history_ready20.eq(1)&v.label_known_date.ne('')&v.label_known_date.le('2026-10-16')&np.isfinite(v.net_R_stress);selected=v.selected.eq(1)
            expected.append(dict(zip(keys,names_),rows=len(v),selected=int(selected.sum()),external_missing=int(v.external_missing.sum()),closed_action_ready_known=int(known.sum()),mse_closed_known=float(np.mean((v.loc[known,'score']-v.loc[known,'net_R_stress'])**2))if known.any()else None,selected_nonclosed=int((selected&~v.label_state.eq('closed_complete_bar_model')).sum()),label_states=v.label_state.value_counts().to_dict()))
        compare_dict(metrics[role],expected,'opportunity_'+role)
    signal,states=main_signal_diagnostics(labels,pred,'2026-10-16')
    return pred,held,signal,states,dict(cash_eligible=True,models_checked=12,predictions_checked=644056,models=models,six_cell_support=support,head_dimension=54,refits=0)

def cash_gate(points,held,any_stale,main_unknown,wealth_positive):
    assert set(held['groups'])=={'holdout_0','holdout_1'}
    vals=list(points.values());p=points[('primary_2020','stress')]
    returns=p['return_percentage_point_difference']>0 and all(v['return_percentage_point_difference']>=0 for k,v in points.items()if k!=('primary_2020','stress'))
    dds=[v['drawdown_percentage_point_difference']for v in vals];known=all(x is not None and np.isfinite(x)for x in dds);dd=all(x>=0 for x in dds if x is not None and np.isfinite(x))
    low=p['ci95_low'];ci=low is not None and np.isfinite(low)and low>0
    own=all(v['active_total_return_pct']is not None and np.isfinite(v['active_total_return_pct'])and v['active_total_return_pct']>0 for v in vals)
    hn=all(g['nominal_pass']is True for g in held['groups'].values());hu=any(g.get('unknown_differential_selected_events',0)>0 or g['status']=='unknown'for g in held['groups'].values())
    nominal=bool(returns and known and dd and ci and own and wealth_positive)
    if all(v['identification']=='all_empty_unidentified'for v in vals):status='all_empty_unidentified'
    elif not(returns and dd and ci and hn and own and wealth_positive):status='unsupported'
    elif not known:status='unknown_empty_reference_DD'
    elif any_stale:status='unknown_historical_stale'
    elif hu:status='unknown_differential_held_outcome'
    else:status='supported_research_model_only'
    return dict(status=status,cash_nominal_pass=nominal,held_known_nominal_pass=bool(hn),LONG_HISTORY_own_returns_positive_in_all_four=bool(own),actual_wealth_positive=bool(wealth_positive),nominal_pass=bool(nominal and hn),financial_unknown=bool(any_stale or not known),signal_unknown_main=bool(main_unknown),held_signal_unknown=bool(hu),signal_label_uncertainty_is_not_cash_exposure=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False,independent_actual_review_required=True,no_automatic_promotion=True)

def _signal(cash_dir, held, signal_report, signal_states):
    _require(signal_report is not None and signal_states is not None, "independently reviewed main signal report and states required")
    saved = json.loads((cash_dir / "signal_identification.json").read_text())
    _require(saved["main"] == signal_report, "independent main signal report differs")
    _nested(saved["held_groups"], held["groups"], "independent held groups")
    _nested(json.loads(_bound(saved["held_binding"])), held, "held bound independent input")
    _fields(saved, dict(label_unknown_not_a_cash_gate=True), "signal cash separation")
    _fields(signal_report, dict(main_prediction_rows_per_arm=161014, full_mother_rows=399252,
                               unfilled_signal_label_uncertainty_is_not_cash_exposure=True), "main signal scope")
    _require(sum(signal_report["full_mother_label_states"].values()) == 399252, "full mother label state count")
    _require(0 <= signal_report["unknown_differential_selected_events"] <= 161014, "unknown main count")
    actual = _read(cash_dir, "main_signal_states")
    expected = pd.DataFrame(signal_states).copy()
    _require(set(actual.columns) == set(expected.columns), "signal state columns")
    for frame in (actual, expected):
        frame["year"] = frame.year.astype(str)
        _require(not frame.duplicated(["year", "label_state"]).any(), "duplicate signal state identity")
    actual = actual.sort_values(["year", "label_state"]).reset_index(drop=True)
    expected = expected.sort_values(["year", "label_state"]).reset_index(drop=True)
    _require(actual[["year", "label_state"]].fillna("").values.tolist() == expected[["year", "label_state"]].fillna("").values.tolist(), "signal state identity")
    for col in set(actual.columns) - {"year", "label_state"}:
        compare(actual[col], expected[col], "independent main states " + col)
    compare(actual.rows.sum(), 161014, "main state total")
    return signal_report["unknown_differential_selected_events"] > 0

def check_account_summary_table(row,summary):
    for field,value in summary.items():
        if not isinstance(value,(dict,list)):_fields(row,{field:value},'account summary')

def review_cash_diagnostics(cash_dir, summaries, protocol, held, bootstrap_indices, *, signal_report=None, signal_states=None):
    """Read saved8 cash only; parent supplies independently reviewed held/main.

    summaries keys: NARROW_{CONTROL|LONG_HISTORY}_{primary_2020|cold_2023}_{base|stress}.
    signal_report and signal_states are required keyword inputs from the parent
    model checker. No author imports, labels/predictions, SQL, fit or cash replay.
    """
    cash_dir = Path(cash_dir)
    _require(protocol['stage']==121 and protocol['line_id']==LINE.name,'121 scope')
    c=protocol['cash'];_fields(c,dict(initial_equity=1000000,accounts_max=8,initial_stop_N=.25,single_family_risk=.0025,total_planned_risk=.02,buffered_margin_cap=.25,margin_buffer=1.1),'121 finance')
    finance=dict(initial=c['initial_equity'],arms=c['arms'],costs=c['costs'],windows=[dict(id=k,start=v[0],end=v[1])for k,v in c['windows'].items()],bootstrap=dict(repetitions=2000,block_length=252,seed=20261018))
    _fields(finance["bootstrap"], dict(repetitions=2000, block_length=252, seed=20261018), "121 bootstrap")
    _require(finance["arms"] == list(ARMS) and finance["costs"] == list(COSTS), "fixed two arms/costs")
    _require([w["id"] for w in finance["windows"]] == list(WINDOWS), "fixed two windows")
    keys = [(a, w, c) for a in ARMS for w in WINDOWS for c in COSTS]
    name = lambda a, w, c: f"NARROW_{a}_{w}_{c}"
    names = {name(*k) for k in keys}
    _require(set(summaries) == names, "exact8 independent summaries")
    reports = json.loads((cash_dir / "diagnostics.json").read_text())
    _require(set(reports) == names, "exact8 diagnostics")
    family = _read(cash_dir, "family_year_including_zero")
    families = sorted(family.family_id.unique())
    _require(len(families) == 95 and set(zip(family.arm, family.window, family.cost)) == set(keys), "8 x all95 family universe")
    annual = _read(cash_dir, "annual_slices")
    _require(set(annual.account) == names and not annual.duplicated(["account", "year"]).any(), "unique8 account annual tables")
    summary_table = _read(cash_dir, "account_summaries")
    _require(len(summary_table) == 8 and set(zip(summary_table.arm, summary_table.window, summary_table.cost)) == set(keys), "eight summary identities")
    daily, logs, counts, family_expected = {}, {}, {}, []
    for key in keys:
        account = name(*key)
        selected = family.loc[family.arm.eq(key[0]) & family.window.eq(key[1]) & family.cost.eq(key[2])]
        daily[key], logs[key], counts[account], fy = _account(cash_dir / account, summaries[account], reports[account], selected, families)
        family_expected.append(fy.assign(arm=key[0], window=key[1], cost=key[2]))
        _daily_summary(daily[key], summaries[account], finance["initial"])
        rows = annual.loc[annual.account.eq(account)].sort_values("year")
        _require(len(rows) == len(reports[account]["annual_slices"]), "annual row count")
        for actual, expected in zip(rows.to_dict("records"), reports[account]["annual_slices"]):
            _fields(actual, expected, "saved annual table")
        row = summary_table.loc[summary_table.arm.eq(key[0]) & summary_table.window.eq(key[1]) & summary_table.cost.eq(key[2])].iloc[0].to_dict()
        check_account_summary_table(row,summaries[account])
    totals = _read(cash_dir, "family_total_including_zero")
    group_cols = ["arm", "window", "cost", "family_id"]
    measures = ["net_equity_contribution", "fee", "slippage", "fill_count", "filled_qty"]
    expected = pd.concat(family_expected).groupby(group_cols)[measures].sum().sort_index()
    _require(not totals.duplicated(group_cols).any(), "duplicate family total")
    actual = totals.set_index(group_cols).sort_index()
    _require(actual.index.tolist() == expected.index.tolist(), "8 x all95 family total grid")
    for col in measures:
        compare(actual[col], expected[col], "independent family total " + col)
    comparisons = _read(cash_dir, "comparisons")
    distributions = _read(cash_dir, "bootstrap_distributions")
    expected_columns = {w + "_" + c + "_LONG_HISTORY_minus_CONTROL" for w in WINDOWS for c in COSTS}
    _require(len(comparisons) == 4 and not comparisons.duplicated(["window", "cost"]).any(), "four unique comparisons")
    _require(set(comparisons.contrast) == {"LONG_HISTORY_minus_CONTROL"}, "single frozen contrast")
    _require(len(distributions) == 2000 and set(distributions.columns) == expected_columns, "2000 x 4 distributions")
    _require(set(bootstrap_indices) == set(WINDOWS), "two prebound old indices")
    points = {}
    for window in WINDOWS:
        dates = daily[("LONG_HISTORY", window, "stress")].date.tolist()
        _require(all(daily[k].date.tolist() == dates for k in keys if k[1] == window), "common source calendar")
        schedule = next(w for w in finance["windows"] if w["id"] == window)
        _require(dates[0] >= schedule["start"] and dates[-1] == schedule["end"], "calendar window bounds")
        index = np.load(io.BytesIO(_bound(bootstrap_indices[window])), allow_pickle=False)
        _require(index.shape == (2000, len(dates)) and index.dtype.kind in "iu" and index.min() >= 0 and index.max() < len(dates), "bound index shape/type/range")
        for cost in COSTS:
            a, b = ("LONG_HISTORY", window, cost), ("CONTROL", window, cost)
            active, control = summaries[name(*a)], summaries[name(*b)]
            empty = control["fills"] == 0
            point = dict(active_total_return_pct=active["total_return_pct"], reference_total_return_pct=control["total_return_pct"],
                         return_percentage_point_difference=active["total_return_pct"] - control["total_return_pct"],
                         drawdown_percentage_point_difference=None if empty else active["max_drawdown_pct"] - control["max_drawdown_pct"],
                         dd_comparison_state="NA_empty_reference" if empty else "active_reference",
                         identification="all_empty_unidentified" if active["fills"] == control["fills"] == 0 else "observed_cash_comparison")
            if logs[a] is None or logs[b] is None:
                values = np.full(2000, np.nan)
                point.update(status="survival_failure_no_log_repair", ci95_low=None, ci95_high=None,
                             mean_daily_log_difference=None, cumulative_log_difference=None)
            else:
                difference = logs[a] - logs[b]
                values = difference[index].mean(axis=1)
                low, high = np.quantile(values, [.025, .975])
                point.update(status="valid", ci95_low=float(low), ci95_high=float(high),
                             mean_daily_log_difference=float(difference.mean()), cumulative_log_difference=float(difference.sum()))
            row = comparisons.loc[comparisons.window.eq(window) & comparisons.cost.eq(cost)]
            _require(len(row) == 1, "expected comparison")
            _fields(row.iloc[0].to_dict(), point, window + "." + cost)
            compare(distributions[window + "_" + cost + "_LONG_HISTORY_minus_CONTROL"], values, "paired bootstrap", atol=1e-12)
            points[(window, cost)] = point
    main_unknown = _signal(cash_dir, held, signal_report, signal_states)
    any_stale = any(r["stale_days"] > 0 for r in counts.values())
    gate = cash_gate(points, held, any_stale, main_unknown, all(v is not None for v in logs.values()))
    _fields(json.loads((cash_dir / "continuation_gate.json").read_text()), dict(gate, any_historical_stale=any_stale), "continuation gate")
    disclosure = json.loads((cash_dir / "budget_and_tick_disclosure.json").read_text())
    _fields(disclosure, dict(policy="NARROW", continuous_boundary_not_necessarily_tick_order=True, no_gap_loss_cap=True,
                            normal_open_close_mark_is_frozen_research_valuation=True, zero_price_scenarios_are_not_universal_loss_bounds=True,
                            bootstrap_indices_regenerated=False, normal_open_not_automatically_financial_unknown=True), "financial disclosures")
    _require(disclosure["bootstrap_indices"] == bootstrap_indices, "disclosed old indices identity")
    _require(0 <= disclosure["stop_distance_below_tick"] <= disclosure["known_tick_rows"] <= disclosure["ready_rows"], "tick counts range")
    return dict(accounts_checked=8, all_families=95, comparisons_checked=4, repetitions=2000, block_length=252,
                seed=20261018, bootstrap_indices_regenerated=False, account_diagnostics=counts, continuation_gate=gate,
                independently_supplied_main_signal_checked=True, independently_supplied_held_checked=True,
                unknown_payoff_bound_established=False, tick_counts_independently_rederived=False)

def extras(directory,signals):
    budgets=csv(directory/'reservations.csv.gz');reject=csv(directory/'rejections.csv.gz')
    if len(budgets):
        expected=budgets.loc[pd.to_numeric(budgets.D_qty).eq(0)].set_index('budget_id').sort_index();saved=reject.set_index('budget_id').sort_index().reindex(columns=expected.columns,fill_value='')
        assert expected.equals(saved),'rejections altered or omitted'
    else:assert len(reject)==0
    fills=csv(directory/'fills.csv.gz');numeric(fills,['reference_price','qty','fee','realized_gross'])
    closed=csv(directory/'closed.csv.gz');opened=csv(directory/'open.csv.gz');roots=pd.concat([closed,opened],ignore_index=True).set_index('root_id')
    if len(roots):
        compare(pd.to_numeric(roots.SL0),pd.to_numeric(roots.entry_reference)-.25*np.array([float(signals.loc[e,'N_u'])for e in roots.event_id]),'all_roots_initial_stop')
    diagnostics=json.loads((directory.parent/'diagnostics.json').read_text())[directory.name];expected=[]
    for r in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].itertuples():
        root=roots.loc[r.root_id];loss=(float(root.entry_reference)-r.reference_price)/(.25*float(signals.loc[r.event_id,'N_u']))
        expected.append(dict(event_id=r.event_id,date=r.date,gross_loss_R=loss,qty=r.qty,realized_gross=r.realized_gross,exit_fee=r.fee))
    assert len(diagnostics['gap_stop_fills'])==len(expected)
    for a,b in zip(diagnostics['gap_stop_fills'],expected):
        assert a['event_id']==b['event_id']and a['date']==b['date']
        for k in ('gross_loss_R','qty','realized_gross','exit_fee'):compare(a[k],b[k],'gap_'+k)
    assert diagnostics['gap_stop_exceeds_1R']==sum(x['gross_loss_R']>1 for x in expected)
    return dict(rejections_preserved=len(reject),all_root_initial_stops_checked=len(roots),gap_stops=len(expected),gap_stops_gross_over1R=sum(x['gross_loss_R']>1 for x in expected))

def same(a,b):return all(a.get(k)==b.get(k)for k in ('path','sha256'))and a.get('bytes',a.get('size'))==b.get('bytes',b.get('size'))

def safe(value):
    if isinstance(value,dict):return{str(k):safe(v)for k,v in value.items()}
    if isinstance(value,(tuple,list)):return[safe(v)for v in value]
    if hasattr(value,'item'):return value.item()
    return value

def write(path,value):
    with path.open('x')as f:json.dump(safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def progress(out,name,value):
    write(out/(name+'.json'),value);print(json.dumps(dict(phase=name,completed=True)),flush=True)

def review_source(manifest, labels, protocol, table, output):
    """All representative identities, both actual-epoch bars and 399252 q values."""
    bridge = json.loads(bound(manifest['input_bindings']['market_protocol']))
    d = np.load(io.BytesIO(bound(bridge['calendar'])), allow_pickle=False)
    calendar = ([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in d]
                if d.dtype.kind in 'iu' else d.astype('datetime64[D]').astype(str).tolist())
    assert len(calendar) == 5587 and calendar == sorted(set(calendar))
    native_index = {day: i for i, day in enumerate(calendar)}
    assert np.array_equal(labels.u_index, labels.u_date.map(native_index))
    days = sorted(labels.u_date.unique()); assert len(days) == 4074
    assert labels.product_id.nunique() == 98 and labels.family_id.nunique() == 95 and labels.exchange.nunique() == 6
    assert not labels.duplicated(['product_id', 'u_date']).any()
    panel = table(bridge['panel'], ['event_id', 'product_id', 'u_date', 'reference_epoch'])
    assert len(panel) == len(labels) and panel.event_id.is_unique
    linked = labels.merge(panel, on='event_id', how='left', validate='one_to_one', suffixes=('', '_native'))
    for key in ('product_id', 'u_date', 'reference_epoch'):
        assert linked[key].tolist() == linked[key+'_native'].tolist(), ('representative source', key)
    economics = json.loads(bound(bridge['economic_projection']))['instruments']
    bars, read_report = native_once(bridge['database'], calendar, output)
    projection = table(manifest['projection']); audit = table(manifest['daily_factor_audit'])
    identity_check(projection, labels, compare, 'full_projection_identity')
    identity_check(audit, labels, compare, 'full_factor_identity')
    assert len(projection) == len(audit) == 399252
    q = np.full(len(labels), np.nan); observed = np.zeros(len(labels), dtype=int)
    factor_states = Counter(); reasons = Counter(); observed_families = Counter(); observed_months = Counter()
    reason_map = {'no_previous_mother_date': 'no_previous_mother_date', 'previous_reference_missing': 'no_previous_reference_epoch',
                  'previous_reference_economics_unqualified': 'unqualified_epoch_economics',
                  'previous_bar_missing_or_invalid': 'missing_or_invalid_previous_native_bar',
                  'current_bar_missing_or_invalid': 'missing_or_invalid_current_native_bar',
                  'factor_nonfinite_or_nonpositive': 'nonfinite_or_nonpositive_factor', '': 'observed_same_epoch_pair'}
    scalar_reasons = {'insufficient_calendar_history': 'insufficient_calendar_history',
                      'incomplete_factor_window': 'missing_required_daily_factor',
                      'nonfinite_accumulation': 'nonfinite_cumulative_return', '': ''}
    for product, group in labels.groupby('product_id', sort=True):
        group = group.sort_values('u_date'); assert group.u_date.tolist() == days
        indexes = group.sequence_index.to_numpy(int)
        fs = independent_factors(days, group.reference_epoch.tolist(), bars, economics)
        qs = independent_scalars(days, [r['factor'] for r in fs])
        a = audit.iloc[indexes].reset_index(drop=True); p = projection.iloc[indexes].reset_index(drop=True)
        expected_prev = [''] + days[:-1]
        assert a.prev_u_date.tolist() == expected_prev
        assert a.prev_reference_epoch.tolist() == [''] + group.reference_epoch.tolist()[:-1]
        compare(pd.to_numeric(a.prev_u_index), [-1] + group.u_index.astype(int).tolist()[:-1], 'previous_original_native_index', atol=0, rtol=0)
        expected_econ = [economics.get(r['epoch'], {}).get('economics_status', 'unresolved_exact_epoch_metadata') for r in fs]
        assert a.economics_status.tolist() == expected_econ
        actual_factors = pd.to_numeric(a.factor.replace('', np.nan)).to_numpy(float)
        compare(actual_factors, [r['factor'] if r['factor'] is not None else np.nan for r in fs], 'all_factor_values', atol=1e-14)
        assert a.factor_state.tolist() == [reason_map[r['reason']] for r in fs]
        compare(pd.to_numeric(a.factor_observed), [r['observed'] for r in fs], 'all_factor_masks', atol=0, rtol=0)
        # Authors intentionally leave the two prices blank without qualified economics.
        allowed_prices = [bool(i and r['epoch'] and qualified_economics(economics.get(r['epoch'], {}))) for i, r in enumerate(fs)]
        for col, key in [('prev_close', 'previous_close'), ('current_close', 'current_close')]:
            expected = [r[key] if ok and r[key] is not None else np.nan for r, ok in zip(fs, allowed_prices)]
            compare(pd.to_numeric(a[col].replace('', np.nan)), expected, 'all_same_epoch_'+col, atol=1e-12)
        assert p.lower_boundary_date.tolist() == [r['boundary'] for r in qs]
        starts = [bisect.bisect_right(days, r['boundary']) for r in qs]
        assert p.window_first_date.tolist() == [days[j] if j <= i else '' for i, j in enumerate(starts)]
        compare(pd.to_numeric(p.window_source_days), [r['required_factors'] for r in qs], 'all_window_source_days', atol=0, rtol=0)
        compare(pd.to_numeric(p.missing_factor_days), [r['missing_factors'] for r in qs], 'all_missing_factor_days', atol=0, rtol=0)
        compare(pd.to_numeric(p.valid_factor_days), [r['required_factors']-r['missing_factors'] for r in qs], 'all_valid_factor_days', atol=0, rtol=0)
        first = []
        for i, j in enumerate(starts):
            first.append(next((days[k] for k in range(j, i+1) if fs[k]['factor'] is None), ''))
        assert p.first_missing_factor_date.tolist() == first
        assert p.missing_reason.tolist() == [scalar_reasons[r['reason']] for r in qs]
        assert p.projection_state.tolist() == ['observed_fixed12_calendar_month_return_chain' if r['observed'] else 'missing' for r in qs]
        values = pd.to_numeric(p.external_scalar_raw.replace('', np.nan)).to_numpy(float)
        compare(values, [r['scalar'] if r['scalar'] is not None else np.nan for r in qs], 'all399252_compounded_scalars', atol=5e-12, rtol=5e-11)
        expected_observed = np.array([r['observed'] for r in qs], int)
        compare(pd.to_numeric(p.external_observed), expected_observed, 'external_observed', atol=0, rtol=0)
        compare(pd.to_numeric(p.external_missing), 1-expected_observed, 'external_missing', atol=0, rtol=0)
        q[indexes] = values; observed[indexes] = expected_observed
        factor_states.update(a.factor_state); reasons.update(p.missing_reason)
        eligible = group.loc[expected_observed.astype(bool)]
        observed_families.update(eligible.family_id); observed_months.update(eligible.u_date.str[:7])
    saved_receipt = json.loads(bound(manifest['source_read_receipt']))
    for k, v in dict(native_source_queries=1, native_contract_days=1552456, native_epochs=9520, database_rehashed=False).items():
        assert saved_receipt[k] == v
    assert saved_receipt['database_before'] == read_report['database_before'] == saved_receipt['database_after']
    report = dict(mother_rows=len(labels), all_factor_rows=len(audit), mother_dates=4074, products=98, families=95,
                  exchanges=6, observed=int(observed.sum()), missing=int((1-observed).sum()),
                  true_zero_observed=int(((q == 0)&(observed == 1)).sum()), factor_states=dict(factor_states),
                  missing_reasons=dict(reasons), observed_families=dict(observed_families), observed_months=dict(observed_months),
                  calendar_boundary='b(u)<v<=u; calendar12month; leap-safe', original_native_indices_preserved=True,
                  representative_fixed_at_previous_mother_day=True, same_actual_epoch_two_prices=True,
                  native=read_report, raw_price_chain_is_not_actual_strategy_PnL=True, strict_first_publication_PIT_claim=False)
    return q, observed, report, calendar, economics, bars

def closure(args):
    manifests = {}; bindings = {}
    schemas = {'projection': 'stage122_long_history_projection_v1', 'fit': 'stage123_long_history_fit_v1', 'cash': 'stage124_long_history_cash_v1'}
    for role in ('projection', 'fit', 'cash'):
        path = getattr(args, role+'_manifest')
        if not path:
            assert role == 'cash'; continue
        mb = bind(path); assert mb['sha256'] == getattr(args, role+'_sha256'), (role, 'manifest SHA')
        m = json.loads(bound(mb)); assert m['schema'] == schemas[role] and m['mode'] == 'actual' and m['protocol']['sha256'] == PROTOCOL_SHA
        assert m['status'] in (('completed', 'unsupported_scalar_support') if role == 'fit' else ('completed',))
        assert m['terminal']['sha256'] == getattr(args, role+'_terminal_sha256')
        terminal = json.loads(bound(m['terminal'])); assert terminal['status'] == m['status'] and terminal['exit_code'] == 0
        count = 12 if m['status'] == 'completed' else 0
        expected = {'projection': dict(completed_projection_rows=399252, completed_factor_audit_rows=399252, native_source_queries=1, actual_model_fit_calls=0, new_cash_accounts=0, new_labels=0, downloads=0, whole_database_hashes=0),
                    'fit': dict(actual_fit_calls_attempted=count, actual_fit_calls_completed=count, native_source_queries=0, cash_replays=0, new_labels=0),
                    'cash': dict(cash_accounts_started=8, new_cash_accounts=8, native_source_queries=1, actual_model_fit_calls=0, new_labels=0, downloads=0, whole_database_hashes=0, old_baseline_replays=0)}[role]
        for k, v in expected.items(): assert terminal[k] == v, (role, 'terminal', k)
        auth = json.loads(bound(m['authorization']))
        required = dict(schema='stage121_exact_root_authorization_v1', authorized_by='root', stage=role,
                        exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, output=str(Path(mb['path']).parent))
        for k, v in required.items(): assert auth[k] == v, (role, 'auth', k)
        assert auth['input_bindings'] == m['input_bindings'] and sorted(auth['source_bundle'], key=lambda b: b['path']) == sorted(m['source_bundle'], key=lambda b: b['path'])
        for b in m['source_bundle']: bound(b)
        artifacts = [m['support_report']] if role == 'fit' and m['status'] == 'unsupported_scalar_support' else (list(m['artifacts'].values()) if isinstance(m['artifacts'], dict) else m['artifacts'])
        paths = set()
        for b in artifacts:
            assert b['path'] not in paths and str(Path(b['path']).resolve()).startswith(str(Path(mb['path']).parent)+'/')
            paths.add(b['path']); bound(b)
        manifests[role] = m; bindings[role] = dict(manifest=mb, terminal=m['terminal'], authorization=m['authorization'], source_bundle=m['source_bundle'], artifacts_verified=len(paths))
    source, fit = manifests['projection'], manifests['fit']; protocol = json.loads(bound(source['protocol']))
    assert protocol['stage'] == 121 and protocol['line_id'] == LINE.name and source['protocol'] == fit['protocol']
    assert same(fit['input_bindings']['projection_manifest'], bindings['projection']['manifest'])
    assert same(fit['input_bindings']['projection_terminal'], source['terminal']) and same(fit['input_bindings']['projection'], source['projection'])
    for role in ('projection', 'fit'):
        for key in ('narrow_labels', 'narrow_manifest'): assert same(manifests[role]['input_bindings'][key], protocol['inputs'][key])
    for key in ('common_npz', 'common_identity'): assert same(fit['input_bindings'][key], protocol['inputs'][key])
    fixed_path = LINE/'outputs/stage124_long_history_cash/implementation_freeze.json'
    fixed = json.loads(bound(bind(fixed_path)))
    assert fixed['protocol'] == source['protocol']
    if 'cash' in manifests:
        cm = manifests['cash']; assert fit['cash_eligible'] is True and same(cm['input_bindings']['fit_manifest'], bindings['fit']['manifest'])
        for key in ('predictions_main', 'held_diagnostic'): assert same(cm['input_bindings'][key], fit[key])
        for key, b in fixed['fixed_market_inputs'].items(): assert same(cm['input_bindings'][key], b)
        assert cm['bootstrap_indices'] == fixed['bootstrap_indices'] and cm['protocol'] == source['protocol']
    else:
        assert fit['status'] == 'unsupported_scalar_support' and fit['cash_eligible'] is False
        assert not (LINE/'outputs/stage124_long_history_cash/cash/manifest.json').exists()
    return manifests, bindings, protocol, fixed

def native_cases_same_source(binding, bars):
    """All finite first-hit case bytes compared to the sole SQL source."""
    payload = json.loads(gzip.decompress(bound(binding))); checked = 0
    for case in payload['cases']:
        epoch = case['event']['reference_epoch']
        for saved in case['bars']:
            raw = bars.get((epoch, saved['date']))
            assert saved['native_missing'] == (raw is None)
            if raw is not None:
                for key, v in zip(('open', 'high', 'low', 'close', 'volume'), raw[:5]):
                    expected = v if isinstance(v, (int, float)) and math.isfinite(v) else None
                    if expected is None: assert saved[key] is None
                    else: compare(saved[key], expected, 'finite_cash_same_source_'+key, atol=0, rtol=0)
                assert saved['valid'] == legal_native_bar(raw)
            checked += 1
    return dict(case_count=len(payload['cases']), native_bars_compared=checked, additional_SQL=0)

def native_ledger_references(directory, bars, signals, calendar):
    """Saved ledger references vs raw bars; no alternate orders or cash replay."""
    fills = csv(directory/'fills.csv.gz'); positions = csv(directory/'positions.csv.gz')
    roots = pd.concat([csv(directory/'closed.csv.gz'), csv(directory/'open.csv.gz')], ignore_index=True).set_index('root_id')
    previous = {day: calendar[i-1] if i else '' for i, day in enumerate(calendar)}
    position_lookup = positions.set_index(['root_id', 'date'])
    for row in fills.to_dict('records'):
        bar = bars.get((row['epoch'], row['date'])); assert legal_native_bar(bar), ('native fill bar', row['root_id'])
        reference = float(row['reference_price'])
        if row['reason'] != 'stop_boundary':
            compare(reference, bar[0], 'all_native_open_fill_references', atol=1e-12)
        else:
            root = roots.loc[row['root_id']]; signal = signals.loc[row['event_id']]
            if row['date'] == root.entry_date:
                expected = max(float(root.SL0), float(signal.low20_u))
            else:
                prior = position_lookup.loc[(row['root_id'], previous[row['date']])]
                expected = float(prior.boundary_next)
            compare(reference, expected, 'all_native_stop_boundary_references', atol=1e-10)
            assert bar[2] <= reference and bar[0] > reference
    for row in positions.to_dict('records'):
        bar = bars.get((row['epoch'], row['date']))
        if row['mark_state'] == 'stale':
            assert not legal_native_bar(bar), ('stale despite valid native bar', row['root_id'])
        else:
            assert legal_native_bar(bar), ('marked despite unavailable native bar', row['root_id'])
            compare(float(row['mark']), bar[3], 'all_native_close_position_marks', atol=1e-12)
    return dict(fill_references_checked=len(fills), position_native_marks_checked=len(positions), strategy_replay=False, additional_SQL=0)

def review(args):
    global np,pd,compare,csv,numeric,_require,_fields,_read,_log,_account,_daily_summary,_bound,_nested
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'): os.environ[key] = '1'
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=False)
    clock = time.monotonic(); started = datetime.now(timezone.utc).isoformat(); status = 'failed'; error = None
    sources = [bind(Path(__file__)), bind(Path(__file__).with_name('test_stage125_long_history_review.py'))] + [bind(LINE/'tools'/n) for n in AUDIT_HELPERS]
    write(out/'actual_started.json', dict(started_at=started, process_id=os.getpid(), review_startups=1, not_strategy_run=True, sources=sources, exact_inputs=vars(args), new_SQL_max=1))
    snapshot = out/'checker_snapshot'; snapshot.mkdir()
    for b in sources: (snapshot/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
    try:
        np,pd,cash,diag,review_native,load_labels,weights,stats,table,convert,compare_dict = audit_helpers()
        compare,csv,numeric = cash.compare,cash.csv,cash.numeric
        for key in ('_require','_fields','_read','_log','_account','_daily_summary','_bound','_nested'): globals()[key] = getattr(diag,key)
        manifests,bindings,protocol,fixed = closure(args); progress(out, 'final_input_closure', bindings)
        labels = load_labels(manifests['projection']['input_bindings']['narrow_labels'])
        scalar,observed,source_report,calendar,economics,bars = review_source(manifests['projection'], labels, protocol, table, out)
        # Persist numerical output for any narrowly approved later checker continuation.
        with (out/'verified_projection.npz').open('xb') as f: np.savez_compressed(f, scalar=scalar, observed=observed)
        progress(out, 'all399252_representatives_price_pairs_history_projection', source_report)
        predictions,held,signal,states,models = review_models(manifests['fit'],labels,scalar,observed,compare,table,weights,stats,compare_dict)
        progress(out, 'all12_models_and644056_predictions', models)
        if held is not None:
            write(out/'verified_held.json', held); write(out/'verified_main_signal.json', signal)
            states.to_csv(out/'verified_main_signal_states.csv.gz', index=False, compression='gzip')
        accounts = []; diagnostics = None
        if not models['cash_eligible']:
            assert 'cash' not in manifests; progress(out, 'whole_candidate_support_stop', dict(zero_fits=True, zero_cash=True))
        else:
            assert 'cash' in manifests; cm = manifests['cash']; directory = Path(bindings['cash']['manifest']['path']).parent
            labels['planned_execution_date'] = [calendar[int(v)+1] if int(v)+1<len(calendar) else '' for v in labels.u_index]
            summaries = {}
            for arm in ARMS:
                p = predictions.loc[predictions.scope.eq('main')&predictions.arm.eq(arm), ['event_id','score']]
                signals = labels.merge(p, on='event_id', how='left', validate='one_to_one', sort=False)
                signals['potential'] = (signals.label_history_ready20.eq(1)&np.isfinite(signals.score)&signals.score.gt(0)).astype(int)
                signals = signals.set_index('event_id', drop=False)
                for window, span in protocol['cash']['windows'].items():
                    schedule = dict(id=window, start=span[0], end=span[1])
                    for cost in COSTS:
                        name = f'NARROW_{arm}_{window}_{cost}'
                        checked = cash.review_account(directory/name,cost,schedule,protocol,signals,economics,calendar,.25)
                        checked['additional_checks'] = extras(directory/name,signals)
                        checked['native_references'] = native_ledger_references(directory/name,bars,signals,calendar)
                        accounts.append(checked); summaries[name] = checked['summary']
                        progress(out, 'account_'+name, checked)
            assert len(accounts) == 8; progress(out,'all8_cash_ledgers_budgets_fees_slippage',accounts)
            native = next(b for b in cm['artifacts'] if Path(b['path']).name == 'finite_native_cases.json.gz')
            progress(out,'finite_native_cash_cases',dict(same_source=native_cases_same_source(native,bars),first_hit=review_native(native,'cash')))
            diagnostics = review_cash_diagnostics(directory,summaries,protocol,held,fixed['bootstrap_indices'],signal_report=signal,signal_states=states)
            disclosure = json.loads((directory/'budget_and_tick_disclosure.json').read_text()); ready = labels.label_history_ready20.eq(1)
            assert disclosure['ready_rows'] == int(ready.sum()) and disclosure['known_tick_rows'] == int((ready&labels.tick_size.gt(0)).sum())
            assert disclosure['stop_distance_below_tick'] == int((ready&labels.R0_points.lt(labels.tick_size)).sum())
            assert disclosure['reservation_records'] == sum(a['budgets_checked']['rows'] for a in accounts)
            progress(out,'all4_CI_held_gates_unknown_attribution',dict(diagnostics=diagnostics,signal=signal))
        assert sources == [bind(b['path']) for b in sources]
        write(out/'review_receipt.json',dict(schema='stage125_long_history_independent_review_v1',completed=True,C=0,I=0,M=0,review_startups=1,full_review_completions=1,input_closure=bindings,checker_sources=sources,source_review=source_report,model_review=models,cash_accounts=accounts,diagnostics=diagnostics,main_signal_identification=signal,numeric_max_errors=cash.ERRORS,execution=dict(new_SQL=1,fit=0,research_cash=0,whole_native_strategy_replay=0,old_model_recheck=0,old_suite=0,whole_DB_H5_hash=0,new_network_requests=0),research_arithmetic_accepted=True,fixed_package_supported=diagnostics is not None and diagnostics['continuation_gate']['status']=='supported_research_model_only',strict_first_publication_PIT_established=False,narrow_stop_universal_loss_bound=False,goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        status = 'completed'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'; write(out/'failure.json',dict(error=error,traceback=traceback.format_exc())); raise
    finally:
        write(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,error=error,exit_code=0 if status=='completed' else 1,review_startups=1,full_review_completions=int(status=='completed'),research_runs=0,new_SQL=int((out/'native_query_started.json').exists())))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('projection','fit','cash'):
        for key in ('manifest','sha256','terminal-sha256'): parser.add_argument('--'+role+'-'+key,required=role!='cash')
    parser.add_argument('--output',required=True)
    review(parser.parse_args())
