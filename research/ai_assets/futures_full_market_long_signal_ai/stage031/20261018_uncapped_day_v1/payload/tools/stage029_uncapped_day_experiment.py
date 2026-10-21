"""Stage028 fixed full-cohort OPEN/DAY policy: remove only the four-R cap.

No models, SQL, downloads, positions or account arithmetic. Original009 states
control every economic branch; raw audit prices are consumed, never exported.
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
from pathlib import Path
import platform
import sys
import time
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage028_uncapped_day_protocol/protocol.json'
PROTOCOL_SHA='5c2ed793c64f74d503e7a474a93e4885905087b087e7925756c8395eb35100f2'
IDENTITIES=['event_id','product_id','product','exchange','u_date','reference_epoch','planned_execution_date','status','direction']
YEARS=tuple(range(2010,2027))
POLICY_FIELDS=['A_gross_lower','A_gross_upper','B_gross_lower','B_gross_upper','A_lower','A_upper','B_lower','B_upper',
    'paired_lower','paired_upper','stress_A_lower','stress_A_upper','stress_B_lower','stress_B_upper','stress_paired_lower','stress_paired_upper',
    'tail_gain','giveback','double_penalty_lower','double_penalty_upper','new_realized_tail']
CI_COLUMNS=['A_lower','A_upper','B_lower','B_upper','paired_lower','paired_upper','stress_A_lower','stress_A_upper',
    'stress_B_lower','stress_B_upper','stress_paired_lower','stress_paired_upper','tail_gain','giveback',
    'double_penalty_lower','double_penalty_upper','new_realized_tail']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def binding(path,role=None):
    p=Path(path).resolve();raw=p.read_bytes();r=dict(path=str(p),sha256=sha(raw),bytes=len(raw))
    if role:r.update(role=role,reproducibility_required=True,raw_ohlc=False)
    return r
def read_bound(item):
    raw=Path(item['path']).read_bytes()
    if sha(raw)!=item['sha256'] or ('bytes' in item and len(raw)!=item['bytes']):raise ValueError('input binding mismatch '+item['path'])
    return raw
def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def family_group(family):return int(hashlib.sha256(family.encode()).hexdigest(),16)%2
def numbers(series):return np.array([float(x) if x is not None and str(x)!='' else np.nan for x in series],dtype=float)
def near(a,b):return np.isclose(a,b,atol=1e-9,rtol=1e-12)
def policy_payoff(state,a_lower,a_upper,close_r):
    state=np.asarray(state);lo=np.asarray(a_lower,dtype=float);hi=np.asarray(a_upper,dtype=float);c=np.asarray(close_r,dtype=float)
    stop=state=='stop_only';dual=state=='double_touch_interval';profit=state=='profit_only';day=state=='day_close'
    if not np.all(stop|dual|profit|day) or not np.isfinite(lo).all() or not np.isfinite(hi).all() or not np.isfinite(c).all():raise ValueError('invalid identified policy input')
    if np.any((stop&((lo!=-1)|(hi!=-1)))|(dual&((lo!=-1)|(hi!=4)))|(profit&((lo!=4)|(hi!=4)))|(day&(lo!=hi))):raise ValueError('gross interval disagrees with inherited state')
    b=np.where(stop|dual,-1.,np.where(day,lo,c))
    d=np.where(profit,c-4.,0.)
    pl=np.where(dual,-5.,d);pu=d.copy()
    result=dict(A_gross_lower=lo,A_gross_upper=hi,B_gross_lower=b,B_gross_upper=b,
        A_lower=lo-.2,A_upper=hi-.2,B_lower=b-.2,B_upper=b-.2,paired_lower=pl,paired_upper=pu,
        tail_gain=np.where(profit,np.maximum(d,0),0),giveback=np.where(profit,np.minimum(d,0),0),
        double_penalty_lower=np.where(dual,-5.,0),double_penalty_upper=np.zeros_like(d),new_realized_tail=(b>4).astype(float))
    for arm in ('A','B'):
        for side in ('lower','upper'):result['stress_'+arm+'_'+side]=result[arm+'_'+side]-.8
    # Matched fills/costs cancel algebraically; do not recover the difference by float subtraction.
    result['stress_paired_lower']=pl.copy();result['stress_paired_upper']=pu.copy()
    return result
def build_events(features,audit,calendar):
    if calendar!=sorted(set(calendar)) or not calendar:raise ValueError('invalid source grid')
    if features.event_id.duplicated().any() or audit.event_id.duplicated().any() or features.duplicated(['product_id','u_date']).any():raise ValueError('duplicate event/product-day')
    cols=IDENTITIES+['family_id','feature_ready','history_state','label_identified','label_state','label_known_date','path_ambiguous']
    frame=features[cols].copy().reset_index(drop=True)
    for col in ('feature_ready','label_identified','path_ambiguous'):
        if not frame[col].astype(str).isin(['0','1']).all():raise ValueError('nonbinary '+col)
        frame[col]=frame[col].astype('int8')
    if not frame.u_date.isin(calendar).all() or not frame.direction.eq('long').all():raise ValueError('invalid scope/direction')
    if not (frame.exchange+'.'+frame['product']).eq(frame.product_id).all() or not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all():raise ValueError('product/family identity differs')
    observed=frame.status.eq('observed_long_research_opportunity');known=frame.label_identified.eq(1);ready=frame.feature_ready.eq(1)
    if (known&~ready).any() or (ready&~observed).any():raise ValueError('invalid readiness')
    if not frame.loc[known,'label_known_date'].eq(frame.loc[known,'planned_execution_date']).all() or frame.loc[~known,'label_known_date'].ne('').any():raise ValueError('invalid maturity/unknown')
    if set(audit.event_id)!=set(frame.loc[observed,'event_id']):raise ValueError('audit is not complete observed cohort')
    ai=audit.set_index('event_id',verify_integrity=True);fi=frame.set_index('event_id',verify_integrity=True)
    for col in ('u_date','reference_epoch','planned_execution_date','history_state','label_state'):
        if not ai[col].equals(fi[col].reindex(ai.index)):raise ValueError('audit identity/state mismatch '+col)
    idx=frame.index[known];paths=ai.reindex(frame.loc[known,'event_id'])
    F,H,L,C,r,sl,pt,atr=[numbers(paths[col]) for col in ['ideal_entry_F','D_high','D_low','D_close','risk_distance','ideal_stop','ideal_profit','atr20']]
    if not np.isfinite(np.column_stack([F,H,L,C,r,sl,pt,atr])).all() or np.any(np.minimum.reduce([F,H,L,C,r,sl,pt,atr])<=0):raise ValueError('invalid finite positive price/risk audit')
    if np.any((L>np.minimum(F,C))&~near(L,np.minimum(F,C))) or np.any((H<np.maximum(F,C))&~near(H,np.maximum(F,C))):raise ValueError('illegal audit OHLC')
    for actual,expected,name in [(r,.25*atr,'R/ATR'),(sl,F-r,'SL'),(pt,F+4*r,'PT'),(atr,numbers(features.loc[idx,'atr20']),'audit/feature ATR')]:
        if not np.all(near(actual,expected)):raise ValueError('audit numeric consistency '+name)
    states=frame.loc[known,'label_state'].to_numpy();expect_stop=np.isin(states,['stop_only','double_touch_interval']);expect_profit=np.isin(states,['profit_only','double_touch_interval'])
    # Exact raw predicates are diagnostics. Only bounded CSV consistency uses tolerance;
    # state, fill, payoff, tail and gates never use this tolerance as an economic comparator.
    raw_stop=L<=sl;raw_profit=H>=pt
    stop_mismatch=raw_stop!=expect_stop;profit_mismatch=raw_profit!=expect_profit
    if np.any(stop_mismatch&~near(L,sl)) or np.any(profit_mismatch&~near(H,pt)):raise ValueError('raw audit incompatible with inherited state beyond tolerance')
    a_lo=numbers(features.loc[idx,'gross_lower']);a_hi=numbers(features.loc[idx,'gross_upper']);c=(C-F)/r
    day=states=='day_close'
    if not np.all(near(a_lo[day],c[day])):raise ValueError('day_close gross inconsistent with bound audit')
    values=policy_payoff(states,a_lo,a_hi,c)
    for side in ('lower','upper'):
        inherited=numbers(features.loc[idx,'proxy_'+side])
        if not np.all(near(inherited,values['A_'+side])):raise ValueError('inherited A base cost inconsistent')
        values['A_'+side]=inherited;values['stress_A_'+side]=inherited-.8
    if features.loc[~known,['gross_lower','gross_upper','proxy_lower','proxy_upper']].replace('',np.nan).notna().any().any():raise ValueError('unknown original outcomes populated')
    for col in POLICY_FIELDS:
        frame[col]=np.nan;frame.loc[idx,col]=values[col]
    frame['D_close_R']=np.nan;frame.loc[idx,'D_close_R']=c
    frame['raw_stop_touch_diagnostic']=np.nan;frame.loc[idx,'raw_stop_touch_diagnostic']=raw_stop.astype(int)
    frame['raw_profit_touch_diagnostic']=np.nan;frame.loc[idx,'raw_profit_touch_diagnostic']=raw_profit.astype(int)
    frame['evaluation_state']=np.where(~ready,'not_feature_ready',frame.label_state);frame.loc[known,'evaluation_state']='identified'
    frame['family_group']=frame.family_id.map(family_group).astype('int8')
    frame['A_width']=frame.A_upper-frame.A_lower;frame['B_width']=frame.B_upper-frame.B_lower;frame['paired_width']=frame.paired_upper-frame.paired_lower
    for side in ('lower','upper'):
        decomposed=frame.loc[idx,'tail_gain']+frame.loc[idx,'giveback']+frame.loc[idx,'double_penalty_'+side]
        if not np.allclose(decomposed,frame.loc[idx,'paired_'+side],atol=1e-12,rtol=0):raise AssertionError('paired decomposition broken')
        if not np.array_equal(frame.loc[idx,'paired_'+side],frame.loc[idx,'stress_paired_'+side]):raise AssertionError('matched cost cancellation broken')
    if len(frame)!=len(features) or frame.loc[~known,POLICY_FIELDS].notna().any().any():raise AssertionError('outer/unknown preservation broken')
    diagnostics=dict(outer_rows=len(frame),observed_rows=int(observed.sum()),audit_rows=len(audit),feature_ready_rows=int(ready.sum()),identified_rows=int(known.sum()),
        ready_unknown_rows=int((ready&~known).sum()),raw_stop_predicate_disagreements=int(stop_mismatch.sum()),raw_profit_predicate_disagreements=int(profit_mismatch.sum()),
        max_abs_stop_mismatch_price_distance=float(np.max(np.abs(L[stop_mismatch]-sl[stop_mismatch]))) if stop_mismatch.any() else 0.,
        max_abs_profit_mismatch_price_distance=float(np.max(np.abs(H[profit_mismatch]-pt[profit_mismatch]))) if profit_mismatch.any() else 0.,
        max_abs_day_close_gross_consistency_error=float(np.max(np.abs(a_lo[day]-c[day]))) if day.any() else 0.,
        price_tolerance_for_numeric_consistency_only=dict(atol=1e-9,rtol=1e-12),economic_branch='original009 label_state only',raw_prices_exported=False)
    return frame,diagnostics
def daily_metrics(events,calendar):
    known=events.loc[events.label_identified.eq(1)]
    columns=[*POLICY_FIELDS,'A_width','B_width','paired_width','identified_rows']
    if known.empty:return pd.DataFrame(index=pd.Index(calendar,name='u_date'),columns=columns,dtype=float)
    result=known.groupby('u_date',sort=True)[POLICY_FIELDS+['A_width','B_width','paired_width']].mean()
    result['identified_rows']=known.groupby('u_date').size()
    for side in ('lower','upper'):
        if not np.allclose(result.tail_gain+result.giveback+result['double_penalty_'+side],result['paired_'+side],atol=1e-12,rtol=0):raise AssertionError('daily decomposition broken')
    return result.reindex(pd.Index(calendar,name='u_date'))
def finite_mean(values):
    v=np.asarray(values,dtype=float);v=v[np.isfinite(v)]
    return float(v.mean()) if len(v) else None
def counts(frame):
    ready=frame.feature_ready.eq(1);known=frame.label_identified.eq(1);tail=known&frame.new_realized_tail.eq(1)
    return dict(outer_rows=len(frame),observed_rows=int(frame.status.eq('observed_long_research_opportunity').sum()),feature_ready_rows=int(ready.sum()),identified_rows=int(known.sum()),
        unready_rows=int((~ready).sum()),ready_unknown_rows=int((ready&~known).sum()),label_states=dict(Counter(frame.label_state)),
        ready_unknown_states=dict(Counter(frame.loc[ready&~known,'label_state'])),new_realized_tail_rows=int(tail.sum()),
        new_realized_tail_dates=int(frame.loc[tail,'u_date'].nunique()),new_realized_tail_families=int(frame.loc[tail,'family_id'].nunique()),
        right_tail_definition='known B_gross strictly greater than4 at actual DAY close; not high/MFE',
        original_double_touch_rows=int((known&frame.label_state.eq('double_touch_interval')).sum()),
        profit_only_giveback_rows=int((known&frame.giveback.lt(0)).sum()))
def bootstrap(daily):
    n=len(daily);block=min(60,n)
    if not n:raise ValueError('empty source-date grid')
    k=math.ceil(n/block);rng=np.random.default_rng(20261018);array=daily[CI_COLUMNS].to_numpy(float);sims=np.full((2000,len(CI_COLUMNS)),np.nan);h=hashlib.sha256()
    for i in range(2000):
        starts=rng.integers(0,n-block+1,size=k);index=(starts[:,None]+np.arange(block)[None,:]).ravel()[:n];h.update(index.astype('<i8').tobytes())
        selected=array[index];valid=np.isfinite(selected);den=valid.sum(axis=0)
        sims[i]=np.divide(np.where(valid,selected,0).sum(axis=0),den,out=np.full(len(CI_COLUMNS),np.nan),where=den>0)
    metrics={}
    for j,c in enumerate(CI_COLUMNS):
        sample=sims[:,j];sample=sample[np.isfinite(sample)];ci=np.quantile(sample,[.025,.975]).tolist() if len(sample) else [None,None]
        metrics[c]=dict(mean=finite_mean(array[:,j]),ci95_lower=ci[0],ci95_upper=ci[1],finite_source_days=int(np.isfinite(array[:,j]).sum()),finite_bootstrap_replicates=len(sample))
    return dict(block_length_source_days=60,effective_block_length=block,repetitions=2000,seed=20261018,source_grid_days=n,common_indices_sha256=h.hexdigest(),metrics=metrics,
        uncertainty_scope='fixed historical ideal policy; excludes research selection, real execution and account uncertainty')
def positive(v):return v is not None and math.isfinite(v) and v>0
def report(events,calendar):
    scopes={'main':events,'family_0':events.loc[events.family_group.eq(0)],'family_1':events.loc[events.family_group.eq(1)]}
    scopes['family_combined']=pd.concat([scopes['family_0'],scopes['family_1']],ignore_index=True)
    if len(scopes['family_combined'])!=len(events) or scopes['family_combined'].event_id.duplicated().any():raise AssertionError('family partition closure broken')
    reports={};dailies={}
    for name,frame in scopes.items():
        r={'annual':{}}
        for year in YEARS:
            part=frame.loc[frame.u_date.str.startswith(str(year))];grid=[d for d in calendar if d.startswith(str(year))];daily=daily_metrics(part,grid)
            r['annual'][str(year)]=dict(cohort=counts(part),date_equal_means={c:finite_mean(daily[c]) for c in daily},source_grid_days=len(grid),no_identified_days=int(daily.identified_rows.isna().sum()))
        for period,start in [('all_2010','2010-01-01'),('primary_2020','2020-01-01')]:
            part=frame.loc[frame.u_date.ge(start)];grid=[d for d in calendar if d>=start];daily=daily_metrics(part,grid);dailies[name+'_'+period]=daily
            r[period]=dict(cohort=counts(part),date_equal_means={c:finite_mean(daily[c]) for c in daily},source_grid_days=len(grid),no_identified_days=int(daily.identified_rows.isna().sum()))
            if name=='main':r[period]['bootstrap']=bootstrap(daily)
        reports[name]=r
    p=reports['main']['primary_2020'];a=reports['main']['all_2010'];pm=p['date_equal_means'];ci=p['bootstrap']['metrics'];tail=p['cohort']
    gates=dict(primary_B_lower_ci_positive=positive(ci['B_lower']['ci95_lower']),primary_paired_lower_ci_positive=positive(ci['paired_lower']['ci95_lower']),
        primary_same_mask_cost_1R_B_positive=positive(pm['stress_B_lower']),all_2010_B_lower_positive=positive(a['date_equal_means']['B_lower']),all_2010_paired_lower_positive=positive(a['date_equal_means']['paired_lower']),
        family_0_primary_paired_lower_positive=positive(reports['family_0']['primary_2020']['date_equal_means']['paired_lower']),family_1_primary_paired_lower_positive=positive(reports['family_1']['primary_2020']['date_equal_means']['paired_lower']),
        four_complete_years_paired_lower_positive=sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['paired_lower']) for y in range(2020,2026))>=4,
        partial_2026_B_lower_positive=positive(reports['main']['annual']['2026']['date_equal_means']['B_lower']),primary_realized_tail_dates_ge60=tail['new_realized_tail_dates']>=60,primary_realized_tail_families_ge8=tail['new_realized_tail_families']>=8)
    if len(gates)!=11:raise AssertionError('expected11 gates')
    return dict(schema='stage029_fixed_uncapped_day_metrics_v1',scopes=reports,gates=gates,uncapped_policy_screen_pass=all(gates.values()),
        family_interpretation='heterogeneity partition only; no trained-family holdout',label_metric='date_equal normalized ideal OPEN/DAY proxy; not cash returns',
        financial_metrics={k:None for k in ['ending_equity','total_return','max_drawdown','sharpe','total_slippage','total_trades','win_rate']},financial_ready=False,production_qualified=False),dailies
def csv_read(item):
    raw=read_bound(item)
    if str(item['path']).endswith('.gz'):raw=gzip.decompress(raw)
    return pd.read_csv(io.BytesIO(raw),dtype=str,keep_default_na=False)
def load_inputs():
    raw=PROTOCOL.read_bytes()
    if sha(raw)!=PROTOCOL_SHA:raise ValueError('028 protocol changed')
    protocol=json.loads(raw);read_bound(protocol['frozen_spec']);read_bound(protocol['parent_protocol'])
    parent=json.loads(read_bound(protocol['data_manifest']));review=json.loads(read_bound(protocol['data_review']))
    if review.get('qualified_for_fixed_proxy_experiment') is not True or review['data_manifest']['sha256']!=protocol['data_manifest']['sha256']:raise ValueError('011 fixed proxy acceptance missing')
    features=csv_read(parent['feature_label_csv']);audit=csv_read(parent['audit_paths']);calendar=parent['source_calendar_scope_dates']
    if len(features)!=399252 or len(audit)!=212852 or len(calendar)!=4074:raise ValueError('original input counts changed')
    if calendar[0]!='2010-01-04' or calendar[-1]!='2026-10-16':raise ValueError('source grid scope changed')
    events,diagnostics=build_events(features,audit,calendar)
    if (diagnostics['feature_ready_rows'],diagnostics['identified_rows'],diagnostics['ready_unknown_rows'])!=(194709,194168,541):raise ValueError('accepted ready/known/unknown counts changed')
    inputs=dict(protocol=binding(PROTOCOL),parent_manifest=protocol['data_manifest'],parent_review=protocol['data_review'],feature_label_csv=parent['feature_label_csv'],audit_input_only=parent['audit_paths'],raw_prices_exported=False)
    return events,calendar,diagnostics,inputs,protocol
def artifact_list(out):
    result=[]
    for p in sorted(out.iterdir()):
        if not p.is_file() or p.name=='manifest.json':continue
        role='qualification_evidence' if p.name in ['actual_terminal.json','adaptation_diagnostics.json'] else 'feature_contract' if p.name in ['protocol.json','input_bindings.json'] else 'decision_asset'
        result.append(binding(p,role))
    return result
def execute(args):
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('refuse overwrite/repeated full calculation '+str(out))
    out.mkdir(parents=True,exist_ok=False);status='failed';error=None;metrics=None
    try:
        events,calendar,diagnostics,inputs,protocol=load_inputs()
        write_json(out/'input_bindings.json',inputs);write_json(out/'protocol.json',protocol);write_json(out/'adaptation_diagnostics.json',diagnostics)
        print(json.dumps(dict(phase='all_events_built',rows=len(events),identified=diagnostics['identified_rows'],model_fits=0)),flush=True)
        metrics,dailies=report(events,calendar)
        events.to_csv(out/'event_intervals.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        for name,frame in dailies.items():frame.to_csv(out/('daily_'+name+'.csv'),index=True)
        write_json(out/'metrics.json',metrics);status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'actual_terminal.json',dict(status=status,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,
            actual_model_fit_calls=0,financial_runs=0,sql_queries=0,network_calls=0,fixture=False,python=sys.executable,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform(),source=binding(__file__)))
    write_json(out/'manifest.json',dict(schema='stage029_fixed_uncapped_day_experiment_v1',status=status,source=binding(__file__),tests=binding(Path(__file__).with_name('test_stage029_uncapped_day_experiment.py')),
        protocol=binding(PROTOCOL),input_bindings=inputs,source_calendar_scope_dates=calendar,counts=diagnostics,artifacts=artifact_list(out),uncapped_policy_screen_pass=metrics['uncapped_policy_screen_pass'],actual_model_fit_calls=0,financial_runs=0,financial_ready=False,production_qualified=False,
        label_only_columns=[c for c in events if c not in IDENTITIES+['family_id','feature_ready','history_state','label_identified','label_state','label_known_date','path_ambiguous','family_group','evaluation_state']]))
    return dict(status=status,output=str(out),uncapped_policy_screen_pass=metrics['uncapped_policy_screen_pass'],model_fits=0,financial_runs=0)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);print(json.dumps(execute(parser.parse_args()),ensure_ascii=False))
if __name__=='__main__':main()
