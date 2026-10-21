"""Independent063 saved-source/model/cash audit; no fit, SQL or policy replay."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib,io,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from cash_adapter import bound,csv,numeric,compare,ERRORS,review_account
from cash_diagnostics_checks import independent_cash_diagnostics,review_native
from source_checks import check_source,read_csv_binding

OUT=Path(__file__).resolve().parent
PROTOCOL_SHA='ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158'
ARMS=('COMMON_EVENT','INVENTORY','PAST_SHAM')
REFERENCES=('COMMON_EVENT','PAST_SHAM')
COMMON=['stress_u_cost_R','low20_distance_R','r1_atr']
FEATURES=['cost_z','distance_z','r1_z','cost_missing','distance_missing','r1_missing','external_missing','s_z','s_z*r1_z','s_z*distance_z']
OIL={'INE.SC','INE.LU','SHFE.FU','SHFE.BU'}
WINDOWS=[dict(id='primary_2020',start='2020-01-01',end='2026-10-16'),dict(id='cold_2023',start='2023-01-01',end='2026-10-16')]


def sha(raw):return hashlib.sha256(raw).hexdigest()
def binding(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=sha(raw))
def write_json(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def check_manifests(fb,cb):
    fit=json.loads(bound(fb));cash=json.loads(bound(cb))
    assert fit['schema']=='stage061_eia_event_fit_v1' and fit['mode']=='actual'
    assert cash['schema']=='stage062_eia_event_cash_compare_v1'
    assert fit['status']==cash['status']=='completed'
    assert fit['protocol']==cash['protocol'] and fit['protocol']['sha256']==PROTOCOL_SHA
    assert cash['fit_manifest']==fb and fit['source_import_manifest']==cash['source_import_manifest']
    assert fit['actual_fit_calls_started']==fit['actual_fit_calls_completed']==6
    assert cash['started_research_cash_accounts']==cash['computed_research_cash_accounts']==cash['completed_research_cash_accounts']==12
    for m in [fit,cash]:
        for item in m['artifacts']:bound(item)
        bound(m['source']);bound(m['tests']);bound(m['authorization'])
        t=json.loads(bound(m['terminal']));assert t['status']=='completed' and t['exit_code']==0
    ft=json.loads(bound(fit['terminal']));ct=json.loads(bound(cash['terminal']))
    assert ft['actual_fit_calls_started']==ft['actual_fit_calls_completed']==6
    assert ft['native_source_queries']==ft['new_cash_accounts']==0
    assert ct['actual_model_fit_calls']==0 and ct['native_source_queries']==1
    assert ct['started_research_cash_accounts']==ct['computed_research_cash_accounts']==ct['completed_research_cash_accounts']==12
    p=json.loads(bound(fit['protocol']));bridge=json.loads(bound(cash['market_economics_bridge']))
    assert cash['market_economics_bridge']['sha256']=='968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c'
    assert p['inputs']['design_order']==FEATURES and p['learner']['arms']==list(ARMS)
    authf=json.loads(bound(fit['authorization']));authc=json.loads(bound(cash['authorization']))
    assert authf['kind']=='stage061_fit_once' and authc['kind']=='stage062_cash_once'
    for auth,source in [(authf,fit),(authc,cash)]:
        assert auth['authorized'] is True and auth['protocol_sha256']==PROTOCOL_SHA
        assert auth['source_sha256']==source['source']['sha256'] and auth['source_import_manifest_sha256']==fit['source_import_manifest']['sha256']
    assert authf['fit_calls']==6 and authc['cash_accounts']==12 and authc['native_source_queries']==1
    assert authc['fit_manifest_sha256']==fb['sha256']
    return fit,cash,p,bridge


def prepare_independent_frame(fit,p,events):
    columns=['event_id','product_id','family_id','u_date','u_index','reference_epoch','entry_index','exit_index',
      'entry_date','exit_date','label_known_date','label_state','net_R_stress','label_history_ready20',
      'N_u','low20_u','u_close','history_run','lifecycle_index','planned_execution_date']
    labels=read_csv_binding(fit['inputs']['labels'],usecols=columns,dtype=str,keep_default_na=False)
    assert len(labels)==399252 and not labels.event_id.duplicated().any()
    assert labels.family_id.eq(labels.product_id.str.removesuffix('_F')).all()
    identity=json.loads(bound(p['inputs']['prepared_common_identity']))
    assert identity['event_ids_sha256']==sha(('\n'.join(labels.event_id)+'\n').encode())
    stored=np.load(io.BytesIO(bound(p['inputs']['prepared_common'])),allow_pickle=False)
    assert stored['columns'].tolist()==identity['columns'] and stored['common'].shape==(399252,len(identity['columns']))
    for c in COMMON:labels[c]=stored['common'][:,identity['columns'].index(c)]
    for c in ['u_index','entry_index','exit_index','net_R_stress','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index']:
        labels[c]=pd.to_numeric(labels[c].replace('',np.nan),errors='raise')
    assert labels.u_date.ge('2020-01-01').sum()==161014
    assert labels.label_history_ready20.sum()==195328 and labels.label_state.eq('closed_complete_bar_model').sum()==180507
    value=events[['u_date','report_id','inventory_s','past_sham_s','external_missing']]
    assert not value.u_date.duplicated().any()
    frame=labels.merge(value,on='u_date',how='left',validate='many_to_one',sort=False)
    frame['is_report_event']=frame.report_id.notna().astype(int)
    frame['report_id']=frame.report_id.fillna('');frame['external_missing']=frame.external_missing.fillna(1).astype(int)
    frame[['inventory_s','past_sham_s']]=frame[['inventory_s','past_sham_s']].fillna(0.)
    assert frame.event_id.tolist()==labels.event_id.tolist()
    projection=csv(Path(fit['terminal']['path']).parent/'input_projection.csv.gz')
    assert projection.event_id.tolist()==frame.event_id.tolist()
    for c in ['product_id','family_id','u_date','reference_epoch','report_id','label_state','label_known_date']:
        assert projection[c].tolist()==frame[c].tolist()
    for c in COMMON+['is_report_event','external_missing','inventory_s','past_sham_s']:
        compare(pd.to_numeric(projection[c].replace('',np.nan),errors='raise'),frame[c],'full_input_'+c,atol=1e-12,rtol=1e-12)
    return frame


def unique_weights(train):
    unique=np.empty(len(train))
    for _,indices in train.groupby('family_id',sort=False).indices.items():
        rows=train.iloc[indices];a=rows.entry_index.to_numpy(int);b=rows.exit_index.to_numpy(int)
        counts=np.zeros(int(b.max())+2,dtype=int)
        for start,end in zip(a,b):
            assert 0<=start<=end
            counts[start:end+1]+=1
        inv=np.zeros(len(counts));mask=counts>0;inv[mask]=1/counts[mask]
        for i,start,end in zip(indices,a,b):unique[i]=inv[start:end+1].mean()
    reporttot=pd.Series(unique).groupby(train.report_id.to_numpy()).transform('sum').to_numpy()
    report=unique/reporttot;w=report*len(train)/report.sum()
    return unique,report,w


def finite_stats(x,w):
    finite=np.isfinite(x)
    if not finite.any():return 0.,0.,1.,0
    m=float(np.dot(x[finite],w[finite])/w[finite].sum())
    v=float(np.dot((x[finite]-m)**2,w[finite])/w[finite].sum())
    return m,v,math.sqrt(v) if v>0 else 1.,int(finite.sum())


def design(frame,arm,scaler):
    x=frame[COMMON].to_numpy(float);missing=~np.isfinite(x)
    mean=np.array(scaler['common']['mean']);scale=np.array(scaler['common']['scale'])
    z=(np.where(missing,mean,x)-mean)/scale
    external=frame.external_missing.to_numpy(int);q=np.zeros(len(frame))
    if arm!='COMMON_EVENT':
        raw=frame['inventory_s' if arm=='INVENTORY' else 'past_sham_s'].to_numpy(float)
        use=external==0;assert np.isfinite(raw[use]).all()
        q[use]=(raw[use]-scaler['q']['mean'])/scaler['q']['scale']
    return np.column_stack((z,missing.astype(float),external,q,q*z[:,2],q*z[:,1]))


def review_fits(fit,frame):
    prediction=read_csv_binding(fit['predictions'],keep_default_na=False,na_values=[''])
    prediction['report_id']=prediction.report_id.fillna('')
    assert len(prediction)==483042 and set(prediction.arm)==set(ARMS) and not prediction.duplicated(['event_id','arm']).any()
    expected=set(frame.loc[frame.u_date.ge('2020-01-01'),'event_id'])
    for arm in ARMS:assert set(prediction.loc[prediction.arm.eq(arm),'event_id'])==expected
    assert np.isfinite(prediction.score).all()
    assert len(fit['fits'])==6 and len({r['fit_id'] for r in fit['fits']})==6
    logs=[json.loads(line) for line in (Path(fit['terminal']['path']).parent/'fit_log.jsonl').read_text().splitlines()]
    assert sum(r['event']=='fit_started' for r in logs)==sum(r['event']=='fit_completed' for r in logs)==6
    cache={};results=[]
    for r in fit['fits']:
        cutoff,arm=r['cutoff'],r['arm']
        use=frame.is_report_event.eq(1)&frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)&frame.label_state.eq('closed_complete_bar_model')
        train=frame.loc[use].sort_values(['u_date','event_id'])
        assert len(train)==r['train_rows'] and train.report_id.nunique()==r['report_cohorts']
        assert set(train.family_id)==set(r['training_families'])
        if cutoff not in cache:cache[cutoff]=unique_weights(train)
        unique,report,w=cache[cutoff]
        weights=csv(r['training_weights']['path']);assert weights.event_id.tolist()==train.event_id.tolist()
        for c in ['family_id','product_id','u_date','report_id','label_known_date','entry_date','exit_date','reference_epoch']:
            assert weights[c].tolist()==train[c].tolist(),c
        for c,a in [('uniqueness',unique),('report_normalized_weight',report),('sample_weight',w)]:
            compare(pd.to_numeric(weights[c]),a,'train_'+c,atol=1e-9,rtol=1e-9)
        scaler=json.loads(bound(r['scaler']));assert scaler['feature_names']==FEATURES
        for i,c in enumerate(COMMON):
            stats=finite_stats(train[c].to_numpy(float),w)
            for j,key in enumerate(['mean','var','scale','finite_count']):compare(scaler['common'][key][i],stats[j],'common_scaler_'+key,atol=1e-10,rtol=1e-10)
        observed=train.external_missing.eq(0).to_numpy()
        v=np.r_[np.where(observed,train.inventory_s,np.nan),np.where(observed,train.past_sham_s,np.nan)]
        qstats=finite_stats(v,np.r_[w/2,w/2])
        for j,key in enumerate(['mean','var','scale','finite_count']):compare(scaler['q'][key],qstats[j],'q_scaler_'+key,atol=1e-10,rtol=1e-10)
        mask=frame.u_date.ge(cutoff)
        if r['next_cutoff_exclusive'] is not None:mask&=frame.u_date.lt(r['next_cutoff_exclusive'])
        test=frame.loc[mask].sort_values(['u_date','event_id']);assert len(test)==r['prediction_rows']
        projection=np.load(io.BytesIO(bound(r['input_projection'])),allow_pickle=False)
        assert projection['train_event_ids'].tolist()==train.event_id.tolist() and projection['prediction_event_ids'].tolist()==test.event_id.tolist()
        compare(projection['train_X'],design(train,arm,scaler),'training_design_all_columns',atol=2e-11,rtol=2e-11)
        compare(projection['prediction_X'],design(test,arm,scaler),'prediction_design_all_columns',atol=2e-11,rtol=2e-11)
        compare(projection['sample_weight'],w,'projection_weight',atol=1e-9,rtol=1e-9)
        compare(projection['y'],train.net_R_stress,'projection_y',atol=1e-13,rtol=1e-13)
        # Exact saved floating projection drives the numeric equations; its
        # derivation and train-only statistics were independently checked above.
        x=projection['train_X'];sw=projection['sample_weight'];y=projection['y']
        xm=np.sum(x*sw[:,None],axis=0)/sw.sum();ym=float(np.sum(y*sw)/sw.sum())
        xc=x-xm;yc=y-ym;normal=(xc*sw[:,None]).T@xc+np.eye(10);rhs=(xc*sw[:,None]).T@yc
        model=json.loads(bound(r['portable_model']));eq=json.loads(bound(r['normal_equations']))
        assert model['alpha']==1 and model['fit_intercept'] is True and model['solver']=='cholesky' and model['feature_names']==FEATURES
        coef=np.asarray(model['coef'],float);intercept=float(model['intercept']);assert coef.shape==(10,) and np.isfinite(coef).all()
        compare(eq['weighted_X_mean'],xm,'normal_Xmean',atol=1e-10,rtol=1e-10)
        compare(eq['weighted_y_mean'],ym,'normal_ymean',atol=1e-10,rtol=1e-10)
        compare(eq['centered_XtWX_plus_alphaI'],normal,'normal_matrix',atol=1e-7,rtol=1e-10)
        compare(eq['centered_XtWy'],rhs,'normal_rhs',atol=1e-7,rtol=1e-10)
        residual=normal@coef-rhs;assert np.max(np.abs(residual))<=1e-7+1e-10*np.max(np.abs(rhs))
        assert np.linalg.eigvalsh(normal).min()>=.999999
        compare(intercept,ym-xm@coef,'ridge_intercept_equation',atol=1e-10,rtol=1e-10)
        scored=projection['prediction_X']@coef+intercept
        actual=prediction.loc[prediction.arm.eq(arm)&prediction.cutoff.eq(cutoff)].set_index('event_id').loc[test.event_id]
        compare(actual.score,scored,'all_ridge_predictions',atol=1e-10,rtol=1e-10)
        for c in ['product_id','family_id','u_date','report_id']:assert actual[c].tolist()==test[c].tolist()
        assert np.array_equal(actual.external_missing,test.external_missing) and np.array_equal(actual.is_report_event,test.is_report_event)
        action=test.is_report_event.eq(1).to_numpy()&test.label_history_ready20.eq(1).to_numpy()&(scored>0)
        assert np.array_equal(actual.selected,action.astype(int))
        assert np.array_equal(actual.history_ready20,test.label_history_ready20)
        results.append(dict(fit_id=r['fit_id'],train_rows=len(train),report_cohorts=int(train.report_id.nunique()),families=int(train.family_id.nunique()),predictions=len(test),coefficient_max_abs_equation_residual=float(np.max(np.abs(residual)))))
        print(json.dumps(dict(phase='fit_checked',fit_id=r['fit_id'],rows=len(test))),flush=True)
    return prediction,results


def review_signals(experiment,frame,prediction,dates):
    maps={};dateindex={d:i for i,d in enumerate(dates)}
    for arm in ARMS:
        signal=csv(experiment/('signals_'+arm+'.csv.gz'));assert signal.event_id.tolist()==frame.event_id.tolist()
        numeric(signal,['u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','score','potential','is_report_event','external_missing'])
        for c in ['product_id','family_id','u_date','reference_epoch']:assert signal[c].tolist()==frame[c].tolist()
        for c in ['label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index']:compare(signal[c],frame[c],'cash_signal_'+c,atol=0.,rtol=2e-15)
        assert np.array_equal(signal.u_index,signal.u_date.map(dateindex))
        compare(signal.D_index,signal.u_index+1,'cash_signal_D',atol=0.,rtol=0.)
        pred=prediction.loc[prediction.arm.eq(arm)].set_index('event_id')
        score=signal.event_id.map(pred.score);compare(signal.score,score,'cash_signal_score',atol=0.,rtol=2e-15)
        event=signal.event_id.map(pred.is_report_event).fillna(0).astype(int)
        assert np.array_equal(signal.is_report_event,event)
        action=event.eq(1)&signal.label_history_ready20.eq(1)&np.isfinite(score)&score.gt(0)
        assert np.array_equal(signal.potential,action.astype(int))
        signal['planned_execution_date']=signal.D_index.map(lambda i:dates[int(i)] if int(i)<len(dates) else '')
        maps[arm]=signal.set_index('event_id',drop=False)
    coverage=pd.read_csv(experiment/'all_family_signal_coverage.csv.gz')
    for arm in ARMS:
        expected=maps[arm].groupby('family_id').agg(mother_rows=('event_id','size'),event_rows=('is_report_event','sum'),selected=('potential','sum'))
        actual=coverage.loc[coverage.arm.eq(arm)].set_index('family_id').loc[expected.index]
        for c in ['mother_rows','event_rows','selected']:compare(actual[c],expected[c],'all_family_signal_'+c,atol=0.,rtol=0.)
    return maps


def native_safe(x):
    if isinstance(x,dict):return {str(k):native_safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [native_safe(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x


def exposure_records(directory):
    rows=[]
    definitions=[('open_episodes','terminal_open',['event_id','epoch','qty','entry_fill','last_mark','stale']),
      ('position_days','historical_stale',['event_id','epoch','date','qty','entry_fill','mark']),
      ('closed_episodes','closed_after_unknown_path',['event_id','epoch','entry_date','exit_date','initial_qty','entry_fill','net_pnl'])]
    for name,kind,cols in definitions:
        table=pd.read_csv(directory/(name+'.csv.gz'),float_precision='round_trip')
        if table.empty:continue
        if name=='position_days':table=table.loc[table.mark_state.eq('stale')]
        if name=='closed_episodes':table=table.loc[table.ever_stale.astype(bool)]
        for row in table.to_dict('records'):rows.append(native_safe(dict(kind=kind,**{c:row.get(c) for c in cols})))
    rows.sort(key=lambda x:json.dumps(x,sort_keys=True))
    actual=json.loads((directory/'unresolved_exposure.json').read_text())
    assert actual['records']==rows and actual['finite_R_bound'] is None
    return rows


def check_family_groups(directory,summary,allfamilies):
    annual=pd.read_csv(directory/'family_year_contributions.csv.gz',dtype={'year':str})
    assert set(annual.family_id)==set(allfamilies)
    allrows=pd.read_csv(directory/'all_family_contributions.csv.gz')
    expected=annual.groupby('family_id')[['net_equity_contribution','fee']].sum().sort_index()
    observed=allrows.set_index('family_id').loc[expected.index]
    for c in ['net_equity_contribution','fee']:compare(observed[c],expected[c],'all_family_'+c)
    group=np.where(annual.family_id.isin(OIL),'direct_oil','other_families')
    expected_group=annual.assign(diagnostic_group=group).groupby(['diagnostic_group','year'])[['net_equity_contribution','fee']].sum().sort_index()
    observed_group=pd.read_csv(directory/'direct_oil_other_year_contributions.csv.gz',dtype={'year':str}).set_index(['diagnostic_group','year']).loc[expected_group.index]
    for c in ['net_equity_contribution','fee']:compare(observed_group[c],expected_group[c],'direct_oil_other_'+c)
    diag=summary['oil_and_other_diagnostics'];assert diag['all_families']==len(allfamilies) and set(diag['direct_oil_families'])==OIL
    assert diag['all_families_trade_eligible'] is True and diag['grouping_is_attribution_only'] is True and diag['strict_family_holdout'] is False
    winners=expected.loc[expected.net_equity_contribution.gt(0)].sort_values('net_equity_contribution',ascending=False)
    if len(winners):
        assert diag['largest_winner']['family_id']==winners.index[0]
        pos=winners.net_equity_contribution.sum()
        compare(diag['largest_winner_positive_contribution_share'],winners.iloc[0].net_equity_contribution/pos,'group_top_winner')
        compare(diag['top5_positive_contribution_share'],winners.head(5).net_equity_contribution.sum()/pos,'group_top5_winner')
    return dict(all_families=len(allfamilies),family_year_cells=len(annual),direct_oil_groups_only_diagnostic=True)


def review_statistics(experiment,summaries,dailies,exposures):
    saved=json.loads((experiment/'paired_bootstrap.json').read_text());indices=np.load(io.BytesIO(bound(saved['indices'])),allow_pickle=False)
    n=len(dailies[('INVENTORY','base','primary_2020')]);rng=np.random.default_rng(20261018)
    starts=rng.integers(0,n,size=(2000,math.ceil(n/252)),dtype=np.int64)
    expected=((starts[:,:,None]+np.arange(252))%n).reshape(2000,-1)[:,:n].astype(np.int32)
    assert np.array_equal(indices,expected) and sha(indices.tobytes(order='C'))==saved['indices_array_sha256']
    assert saved['block_length_source_days']==252 and saved['repetitions']==2000 and saved['seed']==20261018
    dist=pd.read_csv(experiment/'paired_bootstrap_distribution.csv.gz');points=json.loads((experiment/'point_comparisons.json').read_text());assert len(points)==8
    def logs(key):
        e=np.r_[1_000_000.,dailies[key].equity.to_numpy(float)]
        return None if not np.all(e>0) or summaries[key]['ever_insolvent'] else np.diff(np.log(e))
    boots={}
    for reference in REFERENCES:
        name='INVENTORY_minus_'+reference;a=logs(('INVENTORY','base','primary_2020'));b=logs((reference,'base','primary_2020'));r=saved['contrasts'][name]
        if a is None or b is None:assert r['status']=='survival_failure_no_log_repair';continue
        diff=a-b;distribution=diff[expected].mean(axis=1);low,high=np.quantile(distribution,[.025,.975])
        for key,value in [('mean_daily_log_difference',diff.mean()),('cumulative_log_difference',diff.sum()),('ci95_low',low),('ci95_high',high)]:compare(r[key],value,'bootstrap_'+key,atol=1e-14,rtol=1e-10)
        compare(dist[name],distribution,'bootstrap_distribution',atol=1e-14,rtol=1e-10);boots[name]=r
    for r in points:
        ref=r['contrast'].removeprefix('INVENTORY_minus_');ka=('INVENTORY',r['scenario'],r['window_id']);kb=(ref,r['scenario'],r['window_id']);a=summaries[ka];b=summaries[kb]
        al,bl=logs(ka),logs(kb);assert r['survival_failure']==(al is None or bl is None)
        if al is not None and bl is not None:compare(r['cumulative_log_growth_difference'],al.sum()-bl.sum(),'point_log')
        for name,key in [('return_percentage_point_difference','total_return_pct'),('drawdown_percentage_point_difference','max_drawdown_pct'),('all_open_zero_ending_equity_difference','all_open_long_zero_scenario_equity')]:compare(r[name],a[key]-b[key],'point_'+name)
        sa,sb=exposures[ka],exposures[kb];unknown=r['unresolved']
        assert unknown['differential_unresolved_exposure']==(sa!=sb)
        assert unknown['left_unresolved_records']==len(sa) and unknown['right_unresolved_records']==len(sb)
        assert unknown['left_exposure_sha256']==sha(json.dumps(sa,sort_keys=True).encode())
        assert unknown['right_exposure_sha256']==sha(json.dumps(sb,sort_keys=True).encode())
    primary=[r for r in points if r['scenario']=='base' and r['window_id']=='primary_2020'];cold=[r for r in points if r['window_id']=='cold_2023']
    nominal1=len(boots)==2 and all(v['ci95_low']>0 for v in boots.values()) and all(not r['survival_failure'] and r['return_percentage_point_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in primary)
    stress=summaries[('INVENTORY','stress','primary_2020')]
    nominal2=not stress['ever_insolvent'] and stress['total_return_pct']>0 and all(not r['survival_failure'] and r['cumulative_log_growth_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in cold)
    uncertain1=any(r['unresolved']['differential_unresolved_exposure'] for r in primary)
    uncertain2=stress['unresolved_records']>0 or any(r['unresolved']['differential_unresolved_exposure'] for r in cold)
    def state(n,u,s):return 'unsupported' if s else 'unknown' if u else 'supported' if n else 'unsupported'
    statuses=[state(nominal1,uncertain1,any(r['survival_failure'] for r in primary)),state(nominal2,uncertain2,stress['ever_insolvent'] or any(r['survival_failure'] for r in cold))]
    result=json.loads((experiment/'continuation_conditions.json').read_text());assert [r['status'] for r in result['conditions']]==statuses
    for flag in ['goal_complete','production_qualified','narrow_stop_qualified','increased_bet_qualified']:assert result[flag] is False
    return dict(bootstrap=boots,continuation_statuses=statuses,decision=result['decision'],points=points,indices_shape=list(indices.shape))


def main():
    parser=argparse.ArgumentParser()
    for flag in ['fit-manifest','fit-sha256','cash-manifest','cash-sha256']:parser.add_argument('--'+flag,required=True)
    args=parser.parse_args();start=time.monotonic();began=datetime.now(timezone.utc).isoformat()
    fb=binding(args.fit_manifest);cb=binding(args.cash_manifest)
    assert fb['sha256']==args.fit_sha256 and cb['sha256']==args.cash_sha256
    fit,cash,p,bridge=check_manifests(fb,cb)
    cal=np.load(io.BytesIO(bound(bridge['calendar'])),allow_pickle=False)
    dates=[f'{str(int(x))[:4]}-{str(int(x))[4:6]}-{str(int(x))[6:8]}' for x in cal]
    source,events,source_result=check_source(fit['source_import_manifest'],dates)
    frame=prepare_independent_frame(fit,p,events);predictions,fit_results=review_fits(fit,frame)
    economics=json.loads(bound(bridge['economic_projection']))['instruments'];experiment=Path(args.cash_manifest).resolve().parent
    signals=review_signals(experiment,frame,predictions,dates);allfamilies=set(frame.family_id)
    saved=json.loads((experiment/'cash_summary.json').read_text());summary_map={r['account_id']:r for r in saved['accounts']};assert len(summary_map)==12
    results=[];summaries={};dailies={};exposures={};groups=[]
    for arm in ARMS:
        for scenario in ['base','stress']:
            for window in WINDOWS:
                name=arm+'__'+scenario+'__'+window['id'];directory=experiment/'cash'/name
                result=review_account(directory,scenario,window,p,signals[arm],economics,dates);summary=result['summary'];assert summary==summary_map[name]
                key=(arm,scenario,window['id']);summaries[key]=summary
                dailies[key]=independent_cash_diagnostics(directory,summary,allfamilies)
                exposures[key]=exposure_records(directory);assert summary['unresolved_records']==len(exposures[key])
                groups.append(dict(account_id=name,**check_family_groups(directory,summary,allfamilies)))
                results.append(result);print(json.dumps(dict(phase='cash_checked',account_id=name,fills=result['fills_checked'])),flush=True)
    statistics=review_statistics(experiment,summaries,dailies,exposures)
    native=review_native(cash,signals,dates,experiment)
    receipt=dict(schema='stage063_eia_independent_actual_review_v1',status='accepted_saved_research_calculation_not_complete_goal',
       protocol_sha256=PROTOCOL_SHA,fit_manifest=fb,cash_manifest=cb,source_import_manifest=fit['source_import_manifest'],
       source_checks=source_result,model_cells_checked=6,predictions_checked=sum(r['predictions'] for r in fit_results),fits=fit_results,
       accounts_checked=12,fills_checked=sum(r['fills_checked'] for r in results),daily_rows_checked=sum(r['daily_rows_checked'] for r in results),
       position_rows_checked=sum(r['position_rows_checked'] for r in results),accounts=results,all_family_oil_group_checks=groups,
       statistics=statistics,bounded_native=native,maximum_comparison_errors=ERRORS,max_abs_error=max(ERRORS.values()),
       critical=0,important=0,minor=0,sql_queries=0,model_fit_calls=0,strategy_replays=0,author_core_imports=0,network_downloads=0,
       original_captured_vintage_qualified=False,broker_truth_qualified=False,goal_complete=False,production_qualified=False,
       narrow_stop_or_increased_bet_qualified=False)
    write_json(OUT/'review_receipt.json',receipt)
    terminal=dict(status='completed',exit_code=0,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,
       sources={n:binding(OUT/n) for n in ['independent_review.py','source_checks.py','cash_adapter.py','cash_review_core.py','cash_diagnostics_checks.py']},
       sql_queries=0,model_fit_calls=0,strategy_replays=0,network_downloads=0)
    write_json(OUT/'actual_terminal.json',terminal)
    print(json.dumps(dict(status=receipt['status'],model_cells=6,predictions=receipt['predictions_checked'],accounts=12,max_error=receipt['max_abs_error'],elapsed_seconds=terminal['elapsed_seconds'])),flush=True)


if __name__=='__main__':main()
