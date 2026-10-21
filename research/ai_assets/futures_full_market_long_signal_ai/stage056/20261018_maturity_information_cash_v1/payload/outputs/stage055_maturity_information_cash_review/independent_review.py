"""One independent saved-output review. No SQL, fit, author imports or policy rerun."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd
from cash_adapter import bound, csv, numeric, compare, ERRORS, review_account

OUT = Path(__file__).resolve().parent
PROTOCOL_SHA = '968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c'
ARMS = ('COMMON', 'ALIGNED', 'SHUFFLED')
OWN = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
       'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MATURITY = ['normalizer','peer_count','tenor_span_years','return_mean','return_std','return_min','return_max',
            'front_next_basis_u','front_next_basis_prev','front_next_tenor_span_years',
            'q_missing','front_next_missing','normalizer_missing']
COMMON = OWN + MATURITY + ['stress_u_cost_R','low20_distance_R']


def sha(raw): return hashlib.sha256(raw).hexdigest()
def binding(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=sha(raw))
def write_json(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
def read_projection(item,columns):
    return pd.read_csv(io.BytesIO(bound(item)),compression='gzip',usecols=columns,dtype=str,keep_default_na=False)
def group(family): return int(sha(str(family).encode()),16)%2


def verify_manifests(fit_binding,cash_binding):
    fit=json.loads(bound(fit_binding));cash=json.loads(bound(cash_binding))
    assert fit['schema']=='stage053_maturity_information_fit_v1' and cash['schema']=='stage054_maturity_cash_comparison_v1'
    assert fit['status']==cash['status']=='completed'
    assert fit['protocol']==cash['protocol'] and fit['protocol']['sha256']==PROTOCOL_SHA
    assert cash['fit_manifest']==fit_binding
    assert fit['actual_fit_calls_started']==fit['actual_fit_calls_completed']==27
    assert cash['started_research_cash_accounts']==cash['computed_research_cash_accounts']==cash['completed_research_cash_accounts']==12
    assert cash['native_source_queries']==1 and cash['actual_model_fit_calls']==0
    for manifest in (fit,cash):
        bound(manifest['source']);bound(manifest['tests'])
        for artifact in manifest['artifacts']:bound(artifact)
    ft=json.loads(bound(fit['terminal']));ct=json.loads(bound(cash['terminal']))
    assert ft['status']==ct['status']=='completed' and ft['exit_code']==ct['exit_code']==0
    assert ft['actual_start_count']==ft['completed_actual_runs']==1
    assert ft['native_source_queries']==0 and ft['new_cash_accounts']==0
    assert ft['actual_fit_calls_started']==ft['actual_fit_calls_completed']==27
    assert ct['started_research_cash_accounts']==ct['computed_research_cash_accounts']==ct['completed_research_cash_accounts']==12
    assert ct['native_source_queries']==1 and ct['actual_model_fit_calls']==0
    protocol=json.loads(bound(fit['protocol']));assert protocol['common_columns']==COMMON
    log=[json.loads(line) for line in Path(fit['fit_log']['path']).read_text().splitlines()]
    assert sum(r['event']=='fit_started' for r in log)==sum(r['event']=='fit_completed' for r in log)==27
    assert all(r['execution_kind']=='actual' for r in log)
    return fit,cash,protocol


def load_independent_inputs(p,fit):
    idcols=['event_id','product_id','family_id','u_date','u_index']
    numbers=['entry_index','exit_index','net_R_stress','label_history_ready20',
        'stress_u_fee_roundtrip_per_lot','stress_u_slippage_roundtrip_per_lot','cash_risk_unit',
        'u_close','low20_u','N_u','history_run','lifecycle_index']
    cols=idcols+['reference_epoch','entry_date','exit_date','label_known_date','label_state','participation_state',
                 'planned_execution_date']+numbers
    labels=read_projection(p['labels'],cols)
    maturity=read_projection(p['maturity_features'],idcols+MATURITY+['q_aligned','q_shuffled'])
    own=read_projection(p['own_features'],['event_id']+OWN)
    for frame in (labels,maturity,own):
        assert len(frame)==399252 and not frame.event_id.duplicated().any()
    for col in idcols:assert labels[col].equals(maturity[col]),col
    assert set(own.event_id)==set(labels.event_id)
    assert labels.family_id.eq(labels.product_id.str.removesuffix('_F')).all()
    frame=labels.merge(maturity.drop(columns=idcols[1:]),on='event_id',validate='one_to_one',sort=False)
    frame=frame.merge(own,on='event_id',validate='one_to_one',sort=False)
    # Match the specified normalized-text conversion, independently of any
    # author function; Python float() can round decimal strings differently.
    for column in ['u_index']+numbers+OWN+MATURITY+['q_aligned','q_shuffled']:
        frame[column]=pd.to_numeric(frame[column].replace('',np.nan),errors='raise')
    with np.errstate(invalid='ignore',divide='ignore'):
        frame['stress_u_cost_R']=(frame.stress_u_fee_roundtrip_per_lot+frame.stress_u_slippage_roundtrip_per_lot)/frame.cash_risk_unit
        frame['low20_distance_R']=(frame.u_close-frame.low20_u)/(2*frame.N_u)
    values=frame[COMMON].to_numpy(float);values[~np.isfinite(values)]=np.nan
    prepared=fit['prepared_common'];assert prepared['rows']==len(frame) and prepared['columns']==COMMON
    assert prepared['event_ids_sha256']==sha(('\n'.join(frame.event_id)+'\n').encode())
    stored=np.load(io.BytesIO(bound(prepared['common'])),allow_pickle=False)
    assert stored['columns'].tolist()==COMMON
    compare(stored['common'],values,'prepared_common_input',atol=0.,rtol=0.)
    assert prepared['old009_labels_masks_predictions_parsed'] is False
    # Exact saved raw26 is the path replay input; independently recomputed
    # scalers below are compared separately and never perturb tree routing.
    frame[COMMON]=stored['common']
    return frame


def independent_weights(train):
    n=len(train);uni=np.empty(n)
    for _,indices in train.groupby('family_id',sort=False).indices.items():
        rows=train.iloc[indices];start=rows.entry_index.to_numpy(int);end=rows.exit_index.to_numpy(int)
        assert np.all(start<=end) and np.all(start>=0)
        # Inclusive intervals: event owns both its entry and exit source days.
        counts=np.zeros(int(end.max())+2,dtype=np.int64)
        for a,b in zip(start,end):counts[a:b+1]+=1
        inv=np.zeros(len(counts));mask=counts>0;inv[mask]=1/counts[mask]
        for i,a,b in zip(indices,start,end):uni[i]=inv[a:b+1].mean()
    totals=pd.Series(uni).groupby(train.u_date.to_numpy()).transform('sum').to_numpy()
    normalized=uni/totals;w=normalized*len(train)/normalized.sum()
    return uni,normalized,w


def stats(x,w):
    finite=np.isfinite(x)
    if not finite.any():return 0.,0.,1.,0
    denominator=w[finite].sum();m=float(np.dot(x[finite],w[finite])/denominator)
    v=float(np.dot((x[finite]-m)**2,w[finite])/denominator)
    return m,v,math.sqrt(v) if v>0 else 1.,int(finite.sum())


def independent_scalers(train,w):
    common=np.array([stats(train[col].to_numpy(float),w) for col in COMMON])
    q=stats(np.r_[train.q_aligned.to_numpy(float),train.q_shuffled.to_numpy(float)],np.r_[w/2,w/2])
    return common,q


def matrix(test,arm,common,q):
    x=test[COMMON].to_numpy(float);missing=~np.isfinite(x)
    z=(np.where(missing,common[:,0],x)-common[:,0])/common[:,2]
    raw=np.zeros(len(test)) if arm=='COMMON' else test['q_'+arm.lower()].to_numpy(float)
    qz=(np.where(np.isfinite(raw),raw,q[0])-q[0])/q[2]
    return np.column_stack((z,missing.astype(float),qz))


def traverse_portable(portable,x):
    assert portable['n_features']==53 and portable['leaf_values_include_learning_rate'] is True
    assert portable['loss']=='squared_error' and portable['link']=='identity'
    assert len(portable['trees'])==100
    result=np.full(len(x),portable['baseline'],dtype=float)
    for tree in portable['trees']:
        n=len(tree);leaf=np.array([r['is_leaf'] for r in tree],bool)
        assert leaf.sum()<=7 and leaf.sum()>=1
        features=np.array([r['feature_idx'] for r in tree],int)
        thresholds=np.array([r['num_threshold'] for r in tree],float)
        left=np.array([r['left'] for r in tree],int);right=np.array([r['right'] for r in tree],int)
        values=np.array([r['value'] for r in tree],float)
        assert np.isfinite(values).all() and np.isfinite(thresholds).all()
        node=np.zeros(len(x),dtype=np.int32);depth=0
        while True:
            active=np.flatnonzero(~leaf[node])
            if not len(active):break
            assert depth<3
            current=node[active];v=x[active,features[current]]
            goleft=v<=thresholds[current]
            if np.isnan(v).any():
                missing=np.array([r['missing_go_to_left'] for r in tree],bool)
                goleft=np.where(np.isnan(v),missing[current],goleft)
            node[active]=np.where(goleft,left[current],right[current]);depth+=1
            assert ((node>=0)&(node<n)).all()
        result+=values[node]
    return result


def review_fit(fit,p,frame):
    predictions={name:pd.read_csv(io.BytesIO(bound(item)),compression='gzip') for name,item in fit['predictions'].items()}
    expected=set(frame.loc[frame.u_date.ge('2020-01-01'),'event_id'])
    for name,pred in predictions.items():
        assert not pred.duplicated(['event_id','arm']).any()
        for arm in ARMS:
            ids=set(pred.loc[pred.arm.eq(arm),'event_id'])
            if name in ('main','holdout_combined'):assert ids==expected
            elif name=='holdout_0':assert ids==set(frame.loc[frame.u_date.ge('2020-01-01')&frame.family_id.map(group).eq(0),'event_id'])
            elif name=='holdout_1':assert ids==set(frame.loc[frame.u_date.ge('2020-01-01')&frame.family_id.map(group).eq(1),'event_id'])
        assert np.isfinite(pred.score).all()
    assert set(predictions['holdout_combined'].scope)=={'holdout_0','holdout_1'}
    details=[];preprocessing={}
    assert len(fit['fits'])==27 and len({r['fit_id'] for r in fit['fits']})==27
    for record in fit['fits']:
        cutoff=record['cutoff'];scope=record['scope'];arm=record['arm'];held=None if scope=='main' else int(scope[-1])
        use=frame.label_state.eq('closed_complete_bar_model')&frame.u_date.lt(cutoff)&frame.label_known_date.ne('')&frame.label_known_date.lt(cutoff)
        if held is not None:use&=frame.family_id.map(group).ne(held)
        train=frame.loc[use].sort_values(['u_date','event_id'])
        assert len(train)==record['training_rows'] and np.isfinite(train.net_R_stress).all()
        assert sha(('\n'.join(train.event_id)+'\n').encode())==record['training_ids_sha256']
        weights=csv(record['training_weights']['path'])
        assert weights.event_id.tolist()==train.event_id.tolist()
        for col in ['product_id','family_id','u_date','reference_epoch','entry_date','exit_date','label_known_date','label_state']:
            assert weights[col].tolist()==train[col].tolist(),col
        key=(cutoff,scope)
        if key not in preprocessing:
            uni,norm,w=independent_weights(train);common,q=independent_scalers(train,w)
            preprocessing[key]=(uni,norm,w,common,q)
        uni,norm,w,common,q=preprocessing[key]
        numeric(weights,['uniqueness','u_normalized_weight','sample_weight','net_R_stress','entry_index','exit_index','u_index'])
        for col,expected_w in [('uniqueness',uni),('u_normalized_weight',norm),('sample_weight',w)]:
            compare(weights[col],expected_w,'training_'+col,atol=1e-9,rtol=1e-9)
        for col in ['net_R_stress','entry_index','exit_index','u_index']:compare(weights[col],train[col],'training_'+col,atol=0.,rtol=2e-15)
        scaler=json.loads(bound(record['scaler']))
        assert scaler['common']['columns']==COMMON and scaler['feature_names']==COMMON+[c+'_missing' for c in COMMON]+['q']
        for i,k in enumerate(('mean','var','scale','finite_count')):compare(scaler['common'][k],common[:,i],'common_scaler_'+k,atol=1e-9,rtol=1e-9)
        for i,k in enumerate(('mean','var','scale','finite_count')):compare(scaler['q'][k],q[i],'q_scaler_'+k,atol=1e-9,rtol=1e-9)
        select=frame.u_date.ge(cutoff)
        if record['next_cutoff_exclusive'] is not None:select&=frame.u_date.lt(record['next_cutoff_exclusive'])
        if held is not None:select&=frame.family_id.map(group).eq(held)
        test=frame.loc[select].sort_values(['u_date','event_id']);assert len(test)==record['prediction_rows']
        actual=predictions[scope].loc[lambda r:r.cutoff.eq(cutoff)&r.arm.eq(arm)].set_index('event_id').loc[test.event_id]
        assert actual.index.tolist()==test.event_id.tolist()
        for c in ['product_id','family_id','u_date']:assert actual[c].tolist()==test[c].tolist(),c
        assert np.array_equal(actual.history_ready20.to_numpy(),test.label_history_ready20.to_numpy())
        replay_common=np.column_stack([scaler['common'][k] for k in ('mean','var','scale','finite_count')])
        replay_q=tuple(scaler['q'][k] for k in ('mean','var','scale','finite_count'))
        portable=json.loads(bound(record['portable_model']));replayed=traverse_portable(portable,matrix(test,arm,replay_common,replay_q))
        compare(actual.score,replayed,'portable_all_predictions',atol=2e-9,rtol=2e-9)
        action=(test.label_history_ready20.eq(1).to_numpy()&np.isfinite(replayed)&(replayed>0)).astype(int)
        assert np.array_equal(actual.selected.to_numpy(),action)
        details.append(dict(fit_id=record['fit_id'],train=len(train),predictions=len(test),held_group=held,
            latest_u=str(train.u_date.max()),latest_known=str(train.label_known_date.max()),portable_trees=len(portable['trees'])))
        print(json.dumps(dict(phase='fit_checked',fit_id=record['fit_id'],rows=len(test))),flush=True)
    combined=predictions['holdout_combined'].sort_values(['event_id','arm']).reset_index(drop=True)
    split=pd.concat([predictions['holdout_0'],predictions['holdout_1']]).sort_values(['event_id','arm']).reset_index(drop=True)
    pd.testing.assert_frame_equal(combined,split)
    return predictions,details


def review_signals(experiment,frame,predictions,calendar):
    maps={};lookup={d:i for i,d in enumerate(calendar)}
    for arm in ARMS:
        signal=csv(experiment/('signals_'+arm+'.csv.gz'))
        assert signal.event_id.tolist()==frame.event_id.tolist() and len(signal)==399252
        for c in ['product_id','family_id','u_date','reference_epoch']:assert signal[c].tolist()==frame[c].tolist(),c
        numeric(signal,['u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','score','potential'])
        assert np.array_equal(signal.u_index.to_numpy(),signal.u_date.map(lookup).to_numpy())
        compare(signal.D_index,signal.u_index+1,'signal_D_index',atol=0.,rtol=0.)
        for col in ['label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index']:
            compare(signal[col],frame[col],'signal_'+col,atol=0.,rtol=2e-15)
        pred=predictions['main'].loc[lambda d:d.arm.eq(arm)].set_index('event_id')
        score=signal.event_id.map(pred.score)
        compare(signal.score,score,'signals_main_score',atol=0.,rtol=2e-15)
        action=signal.label_history_ready20.eq(1)&np.isfinite(score)&score.gt(0)
        assert np.array_equal(signal.potential.to_numpy(),action.astype(int).to_numpy())
        assert not signal.loc[signal.u_date.lt('2020-01-01'),'potential'].any()
        # Native cash adapter needs execution date; it is derived from accepted calendar, not future labels.
        signal['planned_execution_date']=signal.D_index.map(lambda i:calendar[int(i)] if int(i)<len(calendar) else '')
        maps[arm]=signal.set_index('event_id',drop=False)
    return maps


def review_held(experiment,predictions,frame):
    report=json.loads((experiment/'held_conditional_diagnostic.json').read_text())
    actual_daily=pd.read_csv(experiment/'held_identified_daily.csv.gz')
    linked=predictions['holdout_combined'].merge(frame[['event_id','label_state','participation_state','net_R_stress']],on='event_id',validate='many_to_one')
    domain=linked.label_state.eq('closed_complete_bar_model')|linked.participation_state.eq('known_nonparticipation')
    linked['id_domain']=domain
    outcome=np.where(linked.participation_state.eq('known_nonparticipation'),0.,linked.net_R_stress)
    linked['masked']=np.where(domain,linked.selected*outcome,np.nan)
    findings={}
    for scope,rows in linked.groupby('scope'):
        day=rows.loc[rows.id_domain].groupby(['u_date','arm']).masked.mean().unstack('arm')
        day['ALIGNED_minus_SHUFFLED']=day.ALIGNED-day.SHUFFLED
        day['ALIGNED_minus_COMMON']=day.ALIGNED-day.COMMON
        observed=actual_daily.loc[actual_daily.scope.eq(scope)].set_index('u_date').loc[day.index]
        for col in list(ARMS)+['ALIGNED_minus_SHUFFLED','ALIGNED_minus_COMMON']:
            compare(observed[col],day[col],'held_daily_'+col,atol=1e-12,rtol=1e-10)
        r=report['groups'][scope];assert r['identified_common_events']==int(rows.loc[rows.id_domain,'event_id'].nunique())
        assert r['identified_source_days']==len(day)
        for ref in ('SHUFFLED','COMMON'):
            compare(r['ALIGNED_minus_'+ref+'_daily_equal_mean_R'],day['ALIGNED_minus_'+ref].mean(),'held_equal_u_point')
        for arm,ar in rows.groupby('arm'):
            count=r['arms'][arm];selected=ar.selected.eq(1)
            assert count['full_mother_events']==len(ar) and count['selected']==int(selected.sum())
            assert count['finite_scores']==int(np.isfinite(ar.score).sum())
            assert count['selected_closed']==int((selected&ar.label_state.eq('closed_complete_bar_model')).sum())
            assert count['selected_known_nonparticipation']==int((selected&ar.participation_state.eq('known_nonparticipation')).sum())
            assert count['selected_unknown_or_open']==int((selected&~ar.id_domain).sum())
            assert count['selected_label_states']==ar.loc[selected,'label_state'].value_counts().to_dict()
        unknown=rows.loc[~rows.id_domain].pivot(index='event_id',columns='arm',values='selected')
        differential=int(unknown.ALIGNED.ne(unknown.SHUFFLED).sum())
        assert r['unknown_differential_selected_events']==differential
        point=float(day.ALIGNED_minus_SHUFFLED.mean())
        status='unsupported' if point<=0 else 'unknown' if differential else 'supported'
        assert r['status']==status
        findings[scope]=dict(point_R=point,status=status,unknown_differential=differential,full_events=int(rows.event_id.nunique()))
    assert set(findings)=={'holdout_0','holdout_1'} and report['unknown_not_zero'] is True
    return findings


def independent_cash_diagnostics(directory,summary):
    daily=pd.read_csv(directory/'daily.csv.gz');fills=pd.read_csv(directory/'fills.csv.gz')
    positions=pd.read_csv(directory/'position_days.csv.gz');diag=summary['diagnostics']
    initial=float(summary['initial_capital']);eq=daily.equity.to_numpy(float);prior=initial;years=[]
    for year,rows in daily.groupby(daily.date.str[:4],sort=True):
        x=np.r_[prior,rows.equity.to_numpy(float)];r=next(t for t in diag['annual_slices'] if t['year']==year)
        for field,value in [('starting_equity',prior),('ending_equity',x[-1]),('cash_growth',x[-1]-prior),
            ('max_drawdown_pct',(x/np.maximum.accumulate(x)-1).min()*100)]:compare(r[field],value,'annual_'+field)
        if prior>0:compare(r['return_pct'],(x[-1]/prior-1)*100,'annual_return_pct')
        else:assert r['return_pct'] is None
        assert r['source_days']==len(rows) and r['partial']==(year=='2026')
        assert r['continuous_account_slice'] is True and r['independent_cold_start'] is False
        prior=float(x[-1]);years.append(year)
    assert len(years)==len(diag['annual_slices'])
    # Reconstruct attribution directly from fills and marked surviving holdings.
    family_set=set(fills.family_id) if 'family_id' in fills else set()
    if 'family_id' in positions:family_set|=set(positions.family_id)
    records=[]
    for family in sorted(family_set):
        f=fills.loc[fills.family_id.eq(family)]
        fg=f.groupby('date')[['realized_gross','fee']].sum().reindex(daily.date,fill_value=0.)
        z=positions.loc[positions.family_id.eq(family)] if 'family_id' in positions else pd.DataFrame()
        unreal=z.groupby('date').unrealized.sum().reindex(daily.date,fill_value=0.) if len(z) else pd.Series(0.,index=daily.date)
        contribution=fg.realized_gross.to_numpy()-fg.fee.to_numpy()+np.diff(np.r_[0.,unreal.to_numpy()])
        yearly=pd.DataFrame(dict(year=daily.date.str[:4],value=contribution,fee=fg.fee.to_numpy())).groupby('year').sum()
        for year,row in yearly.iterrows():records.append(dict(family_id=family,year=year,net_equity_contribution=row.value,fee=row.fee))
    expected=pd.DataFrame(records,columns=['family_id','year','net_equity_contribution','fee']).sort_values(['family_id','year'])
    actual=pd.read_csv(directory/'family_year_contributions.csv.gz',dtype={'year':str}).sort_values(['family_id','year'])
    assert actual[['family_id','year']].to_records(index=False).tolist()==expected[['family_id','year']].to_records(index=False).tolist()
    for col in ['net_equity_contribution','fee']:compare(actual[col],expected[col],'family_year_'+col)
    compare(expected.net_equity_contribution.sum(),eq[-1]-initial,'family_year_total_equity_change')
    for record in diag['family_year_concentration']:
        rows=expected.loc[expected.year.eq(record['year'])];wins=rows.loc[rows.net_equity_contribution.gt(0)].sort_values('net_equity_contribution',ascending=False)
        losses=rows.loc[rows.net_equity_contribution.lt(0)].sort_values('net_equity_contribution')
        wp=wins.net_equity_contribution.sum();lp=-losses.net_equity_contribution.sum()
        compare(record['gross_positive_contributions'],wp,'concentration_positive');compare(record['gross_negative_contributions'],lp,'concentration_negative')
        if wp:
            assert record['largest_winning_family']==wins.iloc[0].family_id
            compare(record['largest_winner_share'],wins.iloc[0].net_equity_contribution/wp,'concentration_largest')
            compare(record['top5_winner_share'],wins.head(5).net_equity_contribution.sum()/wp,'concentration_top5')
        if lp:
            assert record['largest_losing_family']==losses.iloc[0].family_id
            compare(record['largest_loser_share'],-losses.iloc[0].net_equity_contribution/lp,'concentration_loser')
    assert diag['stale_days']==int(daily.stale_positions.gt(0).sum())
    for field,col,method in [('max_stale_notional','stale_notional','max'),('minimum_stale_zero_equity','stale_zero_equity','min'),('minimum_all_open_zero_equity','unresolved_zero_equity','min')]:
        compare(diag[field],getattr(daily[col],method)(),'cash_diagnostics_'+field)
    log=np.diff(np.log(np.r_[initial,eq])) if np.all(eq>0) and not summary['ever_insolvent'] else None
    if log is not None:compare(diag['cumulative_log_growth'],log.sum(),'cash_log_growth')
    saved=pd.read_csv(directory/'daily_log_growth.csv.gz')
    if log is not None:compare(saved.daily_log_growth,log,'daily_log_growth')
    else:assert saved.daily_log_growth.isna().all()
    return daily


def review_statistics(experiment,p,summaries,dailies,held):
    saved=json.loads((experiment/'paired_bootstrap.json').read_text());config=p['bootstrap']
    assert saved['config']==config and saved['same_indices_all_contrasts'] is True
    indices=np.load(io.BytesIO(bound(saved['indices'])),allow_pickle=False);n=len(dailies[('ALIGNED','base','primary_2020')])
    rng=np.random.default_rng(config['seed']);blocks=math.ceil(n/config['block_length_source_days'])
    starts=rng.integers(0,n,size=(config['repetitions'],blocks),dtype=np.int64)
    expected=((starts[:,:,None]+np.arange(config['block_length_source_days']))%n).reshape(config['repetitions'],-1)[:,:n].astype(np.int32)
    assert np.array_equal(indices,expected) and sha(indices.tobytes(order='C'))==saved['indices_array_sha256']
    distribution=pd.read_csv(experiment/'paired_bootstrap_distribution.csv.gz')
    points=json.loads((experiment/'point_comparisons.json').read_text());assert len(points)==8
    boot={}
    def logs(key):
        d=dailies[key];eq=np.r_[1_000_000.,d.equity.to_numpy(float)]
        return None if not np.all(eq>0) or summaries[key]['ever_insolvent'] else np.diff(np.log(eq))
    for ref in ('SHUFFLED','COMMON'):
        name='ALIGNED_minus_'+ref;a=logs(('ALIGNED','base','primary_2020'));b=logs((ref,'base','primary_2020'));r=saved['contrasts'][name]
        if a is None or b is None:assert r['status']=='survival_failure_no_log_repair';continue
        diff=a-b;dist=diff[expected].mean(axis=1);low,high=np.quantile(dist,[.025,.975])
        for col,value in [('mean_daily_log_difference',diff.mean()),('cumulative_log_difference',diff.sum()),('ci95_low',low),('ci95_high',high)]:compare(r[col],value,'bootstrap_'+col,atol=1e-14,rtol=1e-10)
        compare(distribution[name],dist,'bootstrap_distribution',atol=1e-14,rtol=1e-10)
        boot[name]=r
    for r in points:
        arm=r['contrast'].removeprefix('ALIGNED_minus_');ka=('ALIGNED',r['scenario'],r['window_id']);kb=(arm,r['scenario'],r['window_id'])
        a,b=summaries[ka],summaries[kb];la,lb=logs(ka),logs(kb)
        assert r['survival_failure']==(la is None or lb is None)
        if la is not None and lb is not None:compare(r['cumulative_log_growth_difference'],la.sum()-lb.sum(),'point_log')
        compare(r['return_percentage_point_difference'],a['total_return_pct']-b['total_return_pct'],'point_return')
        compare(r['drawdown_percentage_point_difference'],a['max_drawdown_pct']-b['max_drawdown_pct'],'point_DD')
        compare(r['all_open_zero_ending_equity_difference'],a['all_open_long_zero_scenario_equity']-b['all_open_long_zero_scenario_equity'],'point_open_zero')
    primary=[r for r in points if r['scenario']=='base' and r['window_id']=='primary_2020']
    first=len(boot)==2 and all(r['ci95_low']>0 for r in boot.values()) and all(not r['survival_failure'] and r['return_percentage_point_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in primary)
    stress=summaries[('ALIGNED','stress','primary_2020')];cold=[r for r in points if r['window_id']=='cold_2023']
    second=not stress['ever_insolvent'] and stress['total_return_pct']>0 and all(not r['survival_failure'] and r['cumulative_log_growth_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in cold)
    statuses=[('unknown' if first and any(r['all_open_zero_ending_equity_difference']<=0 for r in primary) else 'supported' if first else 'unsupported'),
       ('unknown' if second and (stress['all_open_long_zero_scenario_equity']<=1_000_000. or any(r['all_open_zero_ending_equity_difference']<=0 for r in cold)) else 'supported' if second else 'unsupported'),
       ('unsupported' if any(r['status']=='unsupported' for r in held.values()) else 'supported' if all(r['status']=='supported' for r in held.values()) else 'unknown')]
    conditions=json.loads((experiment/'continuation_conditions.json').read_text())
    assert [r['status'] for r in conditions['conditions']]==statuses
    assert conditions['goal_complete'] is False and conditions['production_qualified'] is False and conditions['narrow_stop_or_increased_bet_qualified'] is False
    return dict(bootstrap=boot,continuation_statuses=statuses,points=points,bootstrap_index_shape=list(indices.shape))


def review_native(cash,signals,calendar,experiment):
    audit=json.loads(gzip.decompress(bound(cash['excluded_raw_audit'])));assert audit['sql_queries']==0 and audit['raw_ohlc'] is True
    checked=[];all_signals=signals['COMMON']
    for case in audit['cases']:
        s=all_signals.loc[case['event_id']];assert case['epoch']==s.reference_epoch
        history=[r for r in case['bars'] if r['date']<=case['u_date']]
        assert len(history)==int(s.history_run) and all(not r.get('native_missing') and r['valid_positive_volume'] for r in history)
        N=None;trs=[];previous=None
        for r in history:
            tr=r['high']-r['low'] if previous is None else max(r['high']-r['low'],abs(r['high']-previous),abs(r['low']-previous))
            trs.append(tr)
            if len(trs)==20:N=sum(trs)/20
            elif len(trs)>20:N=(19*N+tr)/20
            previous=r['close']
        assert len(history)>=20
        compare([N,min(r['low'] for r in history[-20:]),history[-1]['close']],[s.N_u,s.low20_u,s.u_close],'finite_native_N_low20_close',atol=1e-9,rtol=1e-11)
        local={r['date']:r for r in case['bars'] if not r.get('native_missing') and r.get('valid_positive_volume')}
        entry=s.planned_execution_date
        native_fills=0
        for directory in sorted((experiment/'cash').iterdir()):
            fills=pd.read_csv(directory/'fills.csv.gz')
            rows=fills.loc[fills.event_id.eq(case['event_id'])]
            for fill in rows.itertuples(index=False):
                if fill.date not in local:continue
                bar=local[fill.date]
                if fill.side=='BUY':
                    assert fill.date==entry
                    compare(fill.reference_price,bar['open'],'native_entry_open',atol=1e-9,rtol=1e-12);native_fills+=1
                elif fill.reason in ['gap_stop','research_deferred_liquidation','risk_margin_joint_reduction','liquidity_reference_changed','lifecycle_exit','observation_exit_requested']:
                    compare(fill.reference_price,bar['open'],'native_exit_open',atol=1e-9,rtol=1e-12);native_fills+=1
                elif fill.reason=='stop_boundary':
                    assert bar['open']>fill.reference_price and bar['low']<=fill.reference_price
                    native_fills+=1
        checked.append(dict(kind=case['kind'],event_id=case['event_id'],continuous_warmup_rows=len(history),total_local_bars=len(case['bars']),local_fill_prices_checked=native_fills))
    return dict(cases=checked,raw_copied=False,full_native_strategy_replay=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fit-manifest',required=True);parser.add_argument('--fit-sha256',required=True)
    parser.add_argument('--cash-manifest',required=True);parser.add_argument('--cash-sha256',required=True);args=parser.parse_args()
    began=time.monotonic();started=datetime.now(timezone.utc).isoformat()
    fb=binding(args.fit_manifest);cb=binding(args.cash_manifest)
    assert fb['sha256']==args.fit_sha256 and cb['sha256']==args.cash_sha256
    fit,cash,p=verify_manifests(fb,cb);frame=load_independent_inputs(p,fit)
    predictions,fit_results=review_fit(fit,p,frame)
    cal=np.load(io.BytesIO(bound(p['calendar'])),allow_pickle=False)
    calendar=[f'{str(int(v))[:4]}-{str(int(v))[4:6]}-{str(int(v))[6:8]}' for v in cal]
    economics=json.loads(bound(p['economic_projection']))['instruments'];experiment=Path(args.cash_manifest).resolve().parent
    signals=review_signals(experiment,frame,predictions,calendar);held=review_held(experiment,predictions,frame)
    all_summary=json.loads((experiment/'cash_summary.json').read_text());assert len(all_summary['accounts'])==12
    saved={r['account_id']:r for r in all_summary['accounts']};account_results=[];summaries={};dailies={}
    for arm in ARMS:
        for scenario in p['cash_scenarios']:
            for window in p['cash_windows']:
                account=arm+'__'+scenario+'__'+window['id'];directory=experiment/'cash'/account
                result=review_account(directory,scenario,window,p,signals[arm],economics,calendar)
                assert result['summary']==saved[account];summary=result['summary']
                summaries[(arm,scenario,window['id'])]=summary
                dailies[(arm,scenario,window['id'])]=independent_cash_diagnostics(directory,summary)
                account_results.append(result);print(json.dumps(dict(phase='cash_checked',account_id=account,fills=result['fills_checked'])),flush=True)
    statistics=review_statistics(experiment,p,summaries,dailies,held);native=review_native(cash,signals,calendar,experiment)
    receipt=dict(schema='stage055_independent_maturity_cash_review_v1',status='accepted_saved_research_arithmetic_not_alpha_or_goal',
       protocol_sha256=PROTOCOL_SHA,fit_manifest=fb,cash_manifest=cb,fit_cells_checked=27,preprocessing_cells_checked=9,
       predictions_checked=sum(r['predictions'] for r in fit_results),fits=fit_results,accounts_checked=12,
       fills_checked=sum(r['fills_checked'] for r in account_results),daily_rows_checked=sum(r['daily_rows_checked'] for r in account_results),
       position_rows_checked=sum(r['position_rows_checked'] for r in account_results),accounts=account_results,held=held,
       statistics=statistics,bounded_native=native,maximum_comparison_errors=ERRORS,max_abs_error=max(ERRORS.values()),
       critical=0,important=0,minor=0,sql_queries=0,model_fit_calls=0,strategy_replays=0,author_core_imports=0,downloads=0,
       goal_complete=False,production_qualified=False,narrow_stop_or_increased_bet_qualified=False,
       limitations=['Conditional closed-label target and identified-domain held diagnostic are not full policy value.',
          'Saved fill arithmetic plus bounded raw cases is not a second complete native strategy replay.',
          'Static specifications, close marks, research selection and six complete years limit inference.'])
    write_json(OUT/'review_receipt.json',receipt)
    terminal=dict(status='completed',exit_code=0,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),
       elapsed_seconds=time.monotonic()-began,source=binding(__file__),cash_adapter=binding(OUT/'cash_adapter.py'),
       independent_cash_core=binding(OUT/'cash_review_core.py'),sql_queries=0,model_fit_calls=0,strategy_replays=0)
    write_json(OUT/'actual_terminal.json',terminal)
    print(json.dumps(dict(status=receipt['status'],fits=27,accounts=12,predictions=receipt['predictions_checked'],max_error=receipt['max_abs_error'],elapsed_seconds=terminal['elapsed_seconds'])),flush=True)


if __name__=='__main__':main()
