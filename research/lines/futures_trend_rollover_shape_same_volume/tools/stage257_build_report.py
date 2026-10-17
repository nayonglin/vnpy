"""Stage257 frozen multicycle account reporting. No replay, network or input writes.

The Stage256 ledger helpers are reused unchanged. The CLI only reads registered
physical accounts; aliases are never added to a Monte Carlo sample. Invoke only
when a report snapshot is requested. Incomplete runs yield progress, not a verdict.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import html
import json
import math
import os
from pathlib import Path
import re
import tempfile
import numpy as np
import pandas as pd
from stage256_build_report import cycle_ledger, period_stats, digest, read_csv, read_json, close, safe, wilson_interval

FROZEN_MANIFEST_SHA='f91edbcaf969703e79ce34be5e83a07d513a2a9dc65494c7f4e1a77b0e3866cf'
REQUIRED=['metrics.json','daily.csv','trades.csv','positions.csv','execution_clock.csv','execution_proxy_usage.csv','effective_parameters.json','minute_scan_requests.csv','execution_anchor_requests.csv','entry_candidates.csv','actual_strategy_settings.json','run_provenance.json','stage257_account_provenance.json']
PHASES=['ai_active_only','mixed_pre_ai_and_ai','common_pre_ai_only']
QUANTILES=[('min',0),('p05',.05),('p25',.25),('median',.5),('p75',.75),('p95',.95),('max',1)]
METRICS=['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','fill_count','max_broker10_margin_to_equity_pct','end_equity_2x_slippage_static','total_return_pct_2x_slippage_static']


def curve_statistics(daily,capital,start,end):
    result=period_stats(daily,start,end,capital)
    static=daily.copy();static['account_equity']=daily.account_equity-daily.slippage.cumsum();static['net_pnl']=daily.net_pnl-daily.slippage
    pressure=period_stats(static,start,end,capital)
    path=np.r_[capital,daily.account_equity.to_numpy(float)];peak=np.maximum.accumulate(path)
    longest=current=0
    for below in path[1:]<peak[1:]-1e-8:
        current=current+1 if below else 0;longest=max(longest,current)
    years=(pd.Timestamp(end)-pd.Timestamp(start)).days/365.25
    result.update(end_equity_2x_slippage_static=pressure['end_equity'],total_return_pct_2x_slippage_static=pressure['return_pct'],max_dd_pct_2x_slippage_static=pressure['max_dd_pct'],longest_drawdown_trading_days=int(longest),days_equity_nonpositive=int(daily.account_equity.le(0).sum()),minimum_equity=float(path.min()),cagr_pct=((path[-1]/capital)**(1/years)-1)*100 if years>0 and path[-1]>0 else None)
    return result


def audit_binding(audit,run_id,manifest_sha,hashes):
    if not audit:return 'pending'
    if (audit.get('run_id',audit.get('account_id'))!=run_id or audit.get('experiment_manifest_sha256')!=manifest_sha
            or set(audit.get('source_hashes',{}))!=set(hashes)
            or any(audit.get('source_hashes',{}).get(k)!=v for k,v in hashes.items())):
        return 'stale'
    status=str(audit.get('status','unknown'))
    if status.startswith('PASS') and audit.get('errors'):return 'FAIL_inconsistent_audit'
    return status


def account_summary(experiment,run_id,manifest,manifest_sha):
    spec=manifest['accounts'][run_id];run=Path(spec.get('output',experiment/'accounts'/run_id))
    row=dict(run_id=run_id,**{k:spec.get(k) for k in ['window_id','pool_id','kind','path_id','start','end']},status='incomplete',error='',independent_audit_status='pending')
    missing=[n for n in REQUIRED if not (run/n).is_file()]
    if missing:
        row['error']='缺文件：'+','.join(missing);return row,None,[],[],[],{}
    hashes={n:digest(run/n) for n in REQUIRED};stamps={n:(run/n).stat().st_mtime_ns for n in REQUIRED}
    try:
        side=read_json(run/'stage257_account_provenance.json');prov=read_json(run/'run_provenance.json');metrics=read_json(run/'metrics.json');params=read_json(run/'effective_parameters.json');actual=read_json(run/'actual_strategy_settings.json')
        if side.get('run_id')!=run_id or side.get('account_id')!=run_id or not side.get('completed_at'):raise ValueError('sidecar run identity/completion')
        if any(side.get(k)!=spec.get(k) for k in ['window_id','pool_id','kind','path_id','start','end','policy_id']):raise ValueError('sidecar/window/policy mismatch')
        pre=side.get('input_sha256_before',{});post=side.get('input_sha256_after',{})
        if not pre or pre!=post:raise ValueError('input guard mismatch')
        if side.get('manifest_sha256')!=manifest_sha or pre.get('manifest')!=manifest_sha or pre.get('pool')!=spec['pool_sha256']:raise ValueError('frozen manifest/pool mismatch')
        if side.get('pool_sha256')!=spec['pool_sha256']:raise ValueError('sidecar pool hash mismatch')
        if side.get('fresh_engine_and_account') is not True or side.get('fresh_engine') is not True:raise ValueError('not a fresh account')
        capital=float(manifest['capital']);close(side.get('initial_capital'),capital,'initial capital')
        if any(float(v)!=0 for v in side.get('initial_positions',{}).values()):raise ValueError('initial position nonzero')
        if side.get('half_r_enabled') is not False or side.get('ai_pool_enabled') is not True:raise ValueError('wrong account flags')
        if len(actual)!=1:raise ValueError('actual strategy count')
        av=actual[0]['actual']
        for k,v in {'enable_stage847_half_r_stop_retry':False,'enable_stage827_intraday_c2_stop':True,'enable_ai_product_pool_filter':True,'enable_selection_pairwise_v2':True}.items():
            if av.get(k) is not v:raise ValueError('actual flag '+k)
        if av.get('trade_start_date')!=spec['start'] or av.get('ai_product_pool_strategy')!=spec['policy_id']:raise ValueError('actual policy/start mismatch')
        if not prov.get('completed_at') or not prov.get('all_data_and_model_inputs_unchanged_during_run') or not prov.get('minute_input_unchanged_during_run') or prov.get('captured_bar_failure_count')!=0:raise ValueError('run completion/input/failure guard')
        if prov.get('minute_input_sha256')!=manifest['minute_cache_sha256'] or pre.get('minute')!=manifest['minute_cache_sha256']:raise ValueError('minute identity')
        if metrics.get('start')!=spec['start'] or metrics.get('end')!=spec['end']:raise ValueError('metrics interval')
        close(metrics['account_capital'],capital,'account capital')
        d=read_csv(run/'daily.csv').sort_values('date').reset_index(drop=True)
        if d.empty or d.date.duplicated().any() or not d.date.between(spec['start'],spec['end']).all():raise ValueError('invalid daily chronology')
        if not np.isfinite(d[['account_equity','net_pnl','slippage','commission']].to_numpy(float)).all():raise ValueError('nonfinite economic daily')
        close((d.account_equity-(capital+d.net_pnl.cumsum())).abs().max(),0,'daily cash account')
        close(d.account_equity.iloc[-1],metrics['end_equity'],'end equity');close((metrics['end_equity']/capital-1)*100,metrics['total_return_pct'],'return')
        t=read_csv(run/'trades.csv',['trade_id','vt_symbol','order_id','signed_volume','volume','price','offset']);clock=read_csv(run/'execution_clock.csv',['trade_id','trading_date']);usage=read_csv(run/'execution_proxy_usage.csv',['trade_id','price_source'])
        if not t.trade_id.is_unique or not clock.trade_id.is_unique or not usage.trade_id.is_unique or set(t.trade_id)!=set(clock.trade_id) or set(t.trade_id)!=set(usage.trade_id):raise ValueError('trade identity')
        if len(t):
            dates=t.trade_id.map(clock.set_index('trade_id').trading_date)
            if not dates.isin(d.date).all():raise ValueError('fill outside window')
            if 'trading_date' in t and not t.trading_date.eq(dates).all():raise ValueError('clock/date mismatch')
            t['trading_date']=dates
            if usage.price_source.astype(str).str.contains('stage847|retry',case=False).any():raise ValueError('unexpected halfR/retry fills')
        p=read_csv(run/'positions.csv',['date','vt_symbol','end_pos','close_price','net_pnl','turnover','pos_change'])
        warm=p[p.date.lt(spec['start'])]
        if len(warm) and warm[['end_pos','pos_change']].abs().to_numpy().max()>1e-8:raise ValueError('warmup positions not flat')
        p=p[p.date.between(spec['start'],spec['end'])]
        first=p.sort_values('date').groupby('vt_symbol').head(1)
        if len(first):close((first.end_pos-first.pos_change).abs().max(),0,'starting positions')
        cycles,opened,cost=cycle_ledger(t,p,params,str(d.date.iloc[-1]))
        close(sum(x['net_pnl'] for x in cycles)+sum(x['net_mtm'] for x in opened),d.net_pnl.sum(),'cycles plus MTM')
        close(cost,d.slippage.sum()+d.commission.sum(),'cost');close(len(t),metrics['total_trade_count'],'fills');close(d.slippage.sum(),metrics['total_slippage'],'slippage')
        if len(p):close(p.net_pnl.sum(),d.net_pnl.sum(),'product MTM sum')
        scans=read_csv(run/'minute_scan_requests.csv',['vt_symbol','trading_date','coverage_status','requested_start','session_end_exclusive','missing_bar_count','expected_bar_count'])
        if len(scans):
            if not scans.groupby(['vt_symbol','trading_date']).session_end_exclusive.nunique().le(1).all():raise ValueError('scan suffix end mismatch')
            scans=scans.sort_values('requested_start').drop_duplicates(['vt_symbol','trading_date'])
        anchors=read_csv(run/'execution_anchor_requests.csv',['vt_symbol','trading_date','expected_start','coverage_status','order_id']);ak=anchors.drop_duplicates(['vt_symbol','trading_date','expected_start'])
        bs=scans[scans.coverage_status.ne('complete')];ba=anchors[anchors.coverage_status.ne('complete')];bad_keys=set(zip(bs.vt_symbol,bs.trading_date));bad_orders=set(ba.order_id)
        affected=t.iloc[:0]
        if len(t):affected=t.loc[[(x.offset in ('开','Open','OPEN') and (x.vt_symbol,x.trading_date) in bad_keys) or x.order_id in bad_orders for x in t.itertuples()]]
        vals=np.array([x['net_pnl'] for x in cycles]);wins=vals[vals>1e-6];loss=vals[vals<-1e-6];curve=curve_statistics(d,capital,spec['start'],spec['end'])
        held=p.assign(held=p.end_pos.abs().gt(1e-8)).groupby('date').held.any().reindex(d.date,fill_value=False) if len(p) else pd.Series(False,index=d.date)
        margin=d.broker10_margin_to_equity_pct if 'broker10_margin_to_equity_pct' in d else pd.Series(dtype=float)
        candidates=read_csv(run/'entry_candidates.csv',['candidate_status'])
        row.update(curve,status='complete',total_return_pct=curve.pop('return_pct'),engine_max_dd_pct=metrics.get('max_dd_pct'),sharpe=metrics.get('sharpe'),total_slippage=float(d.slippage.sum()),commission=float(d.commission.sum()),fill_count=len(t),actual_turnover=float(d.turnover.sum()),closed_cycles=len(cycles),closed_episodes=len(cycles),cycle_wins=len(wins),cycle_losses=len(loss),cycle_flats=int(len(vals)-len(wins)-len(loss)),cycle_win_rate_pct=len(wins)/len(vals)*100 if len(vals) else None,profit_factor=float(wins.sum()/-loss.sum()) if len(loss) else None,profit_factor_infinite=bool(len(wins) and not len(loss)),end_open_contracts=len(opened),end_open_mtm=sum(x['net_mtm'] for x in opened),largest_closed_cycle_pnl=float(vals.max()) if len(vals) else None,top5_winner_share_positive_pct=float(np.sort(wins)[-5:].sum()/wins.sum()*100) if len(wins) else None,max_broker10_margin_to_equity_pct=float(margin.max()) if len(margin) else None,days_broker_margin_over_100=int(margin.gt(100).sum()),eod_holding_day_pct=float(held.mean()*100),eod_flat_day_pct=float((~held).mean()*100),scan_keys=len(scans),incomplete_scan_keys=len(bs),missing_entry_minutes=int(scans.missing_bar_count.sum()),ordinary_anchor_keys=len(ak),missing_ordinary_anchor_keys=int(ak.coverage_status.ne('complete').sum()),missing_anchor_fill_requests=len(ba),affected_fill_count=len(affected),affected_fill_gross_notional=sum(abs(float(x.volume)*float(x.price)*params['contract_sizes'][x.vt_symbol]) for x in affected.itertuples()),diagnostic_mode=bool(prov['diagnostic_incomplete_minutes']),path_data_incomplete=bool(len(bs) or len(ba)),strict_engine_and_data=not(prov['diagnostic_incomplete_minutes'] or len(bs) or len(ba)),recorded_candidates=len(candidates),blocked_candidates=int(candidates.candidate_status.eq('skipped').sum()),source_run=str(run),run_provenance_sha256=hashes['run_provenance.json'])
        audit_path=experiment/'independent_reviews/accounts'/f'{run_id}.json';audit=read_json(audit_path) if audit_path.is_file() else None
        if audit:
            for name in audit.get('source_hashes',{}):
                if Path(name).name!=name:raise ValueError('audit source path must be local filename')
                if name not in hashes and (run/name).is_file():
                    stamps[name]=(run/name).stat().st_mtime_ns;hashes[name]=digest(run/name)
        row['independent_audit_status']=audit_binding(audit,run_id,manifest_sha,hashes);row['independent_audit_sha256']=digest(audit_path) if audit else None
        products=[]
        if len(p):
            p=p.assign(product=p.vt_symbol.str.replace(r'\d+','',regex=True))
            products=[dict(run_id=run_id,window_id=spec['window_id'],product=k,net_pnl=float(g.net_pnl.sum()),turnover=float(g.turnover.sum())) for k,g in p.groupby('product')]
        gaps=[dict(run_id=run_id,window_id=spec['window_id'],kind='entry_scan',vt_symbol=x.vt_symbol,trading_date=x.trading_date,missing_minutes=int(x.missing_bar_count)) for x in bs.itertuples()]+[dict(run_id=run_id,window_id=spec['window_id'],kind='ordinary_anchor',vt_symbol=x.vt_symbol,trading_date=x.trading_date,missing_minutes=1) for x in ak[ak.coverage_status.ne('complete')].itertuples()]
        if any((run/n).stat().st_mtime_ns!=stamps[n] for n in stamps):raise ValueError('source changed during read')
        return row,d,products,[dict(run_id=run_id,window_id=spec['window_id'],**x) for x in cycles],gaps,hashes
    except (ValueError,KeyError,AssertionError,TypeError,IndexError) as exc:
        row.update(status='validation_failed',error=f'{type(exc).__name__}: {exc}');return row,None,[],[],[],hashes


def window_comparison(manifest,w,accounts,family='random_monthly'):
    if accounts.run_id.duplicated().any():raise ValueError('duplicate physical run_id')
    specs={k:v for k,v in manifest['accounts'].items() if v['window_id']==w['window_id']}
    common=w['policy_phase']=='common_pre_ai_only';ai_ids=[k for k,v in specs.items() if v['kind']==('common_pre_ai' if common else 'ai_fair')]
    if len(ai_ids)!=1:raise ValueError('window needs one actual AI/common account')
    random_ids=[k for k,v in specs.items() if v['kind']==family]
    expected=0 if common else manifest['turnover_random_count'] if family=='turnover_matched' else manifest['full_random_count'] if w['group'] in ['historical_full','ai_primary'] else manifest['rolling_random_count']
    if len(random_ids)!=expected:raise ValueError('registered sample size differs from frozen design')
    byid=accounts.set_index('run_id');ai=byid.loc[ai_ids[0]] if ai_ids[0] in byid.index else None
    random=accounts[accounts.run_id.isin(random_ids)];complete=random[random.status.eq('complete')]
    done=bool(ai is not None and ai.status=='complete' and len(complete)==expected)
    labels=[k for k,v in manifest.get('aliases',{}).items() if v==ai_ids[0]]
    role='common_alias_no_AI_evidence' if common else 'primary_N199' if w['window_id']==manifest['primary_window'] and w['group']=='ai_primary' and expected==199 and family=='random_monthly' else 'turnover_mechanism_N199' if family=='turnover_matched' else 'auxiliary_historical_N199' if expected==199 else 'rolling_descriptive_N49'
    result=dict(**w,family=family,evidence_role=role,ai_run_id=ai_ids[0],random_n=expected,completed_random=len(complete),ai_complete=bool(ai is not None and ai.status=='complete'),sample_complete=done,logical_label_count=len(labels) if common else expected+1,votes=bool(w['complete_duration'] and w['duration_years'] in [1,2,3] and not common),b=None,q=None,rank_gate=None,strict_data_review_gate=False,all_independent_audits_passed=False,return_delta_pp=None,dd_depth_delta_pp=None,sharpe_delta=None)
    if ai is not None and ai.status=='complete':
        result.update({f'ai_{k}':safe(ai.get(k)) for k in METRICS+['days_equity_nonpositive','days_broker_margin_over_100']})
    if not done:return result
    participants=accounts[accounts.run_id.isin(ai_ids+random_ids)]
    for col in ['end_equity','total_return_pct','max_dd_pct']:
        if not np.isfinite(participants[col].to_numpy(float)).all():raise ValueError('nonfinite completed endpoint '+col)
    audit=participants.independent_audit_status.astype(str).str.startswith('PASS').all()
    strict=bool(audit and participants.strict_engine_and_data.all())
    result.update(all_independent_audits_passed=bool(audit),strict_data_review_gate=strict,accounts_with_data_gaps=int(participants.path_data_incomplete.sum()),accounts_in_diagnostic_mode=int(participants.diagnostic_mode.sum()))
    if common:
        result.update(return_delta_pp=0.,dd_depth_delta_pp=0.,sharpe_delta=0.);return result
    for col in METRICS:
        v=pd.to_numeric(complete[col],errors='coerce') if col in complete else pd.Series(dtype=float)
        if len(v)==expected and np.isfinite(v).all():
            for label,q in QUANTILES:result[f'random_{col}_{label}']=float(v.quantile(q))
    b=int(complete.end_equity.ge(ai.end_equity).sum())
    risk_ok=bool(np.isfinite(pd.to_numeric(participants.sharpe,errors='coerce')).all())
    result.update(b=b,q=(b+1)/(expected+1),raw_exceedance_fraction=b/expected,wilson95_conditional_exceedance_probability=wilson_interval(b,expected),rank_gate=(b<=manifest['strong_support_max_random_ge_ai']) if role=='primary_N199' else None,return_delta_pp=float(ai.total_return_pct-complete.total_return_pct.median()),dd_depth_delta_pp=float(-ai.max_dd_pct-(-complete.max_dd_pct).median()),sharpe_delta=float(ai.sharpe-complete.sharpe.median()) if risk_ok else None,sharpe_not_below_median=bool(ai.sharpe>=complete.sharpe.median()) if risk_ok else None,dd_depth_not_above_median=bool(-ai.max_dd_pct<=(-complete.max_dd_pct).median()))
    return result


def cohort_summary(windows,comparisons):
    rows=[];lookup=comparisons.set_index('window_id') if len(comparisons) else pd.DataFrame()
    for years in [1,2,3]:
        for phase in ['all_ai_exposed',*PHASES]:
            for cohort in ['combined','January','June']:
                wanted=[w for w in windows if w['duration_years']==years and w['complete_duration'] and (w['policy_phase']!='common_pre_ai_only' if phase=='all_ai_exposed' else w['policy_phase']==phase) and (cohort=='combined' or w['start_cohort']==cohort)]
                observed=[lookup.loc[w['window_id']] for w in wanted if w['window_id'] in lookup.index and bool(lookup.loc[w['window_id'],'sample_complete'])]
                values=[float(x.return_delta_pp) for x in observed if pd.notna(x.return_delta_pp)]
                full=bool(len(wanted)>0 and len(observed)==len(wanted));median=float(np.median(values)) if values else None
                rows.append(dict(duration_years=years,policy_phase=phase,start_cohort=cohort,expected_windows=len(wanted),completed_windows=len(observed),complete=full,median_return_delta_pp=median,median_dd_depth_delta_pp=float(np.median([x.dd_depth_delta_pp for x in observed])) if observed else None,median_sharpe_delta=float(np.median([x.sharpe_delta for x in observed if pd.notna(x.sharpe_delta)])) if any(pd.notna(x.sharpe_delta) for x in observed) else None,AI_at_least_median_windows=sum(v>=0 for v in values) if phase!='common_pre_ai_only' else None,support_gate=bool(full and median is not None and median>=0) if phase=='ai_active_only' and cohort!='combined' else None,evidence_scope='overlapping windows, shared random paths; no independent vote test; common phase not evidence'))
    return pd.DataFrame(rows)


def make_bands(w,manifest,daily_by_id,family='random_monthly'):
    specs={k:v for k,v in manifest['accounts'].items() if v['window_id']==w['window_id']}
    available={k:daily_by_id[k] for k in specs if k in daily_by_id}
    if not available:return pd.DataFrame()
    if len({tuple(x.date) for x in available.values()})!=1:raise ValueError('different calendar in same window; no interpolation')
    dates=next(iter(available.values())).date.to_list();first=pd.Timestamp(w['start'])-pd.Timedelta(seconds=1)
    result=pd.DataFrame({'date':[first.isoformat(),*dates]})
    random=[k for k,v in specs.items() if v['kind']==family and k in available]
    expected=manifest['turnover_random_count'] if family=='turnover_matched' else manifest['full_random_count'] if w['group'] in ['historical_full','ai_primary'] else manifest['rolling_random_count']
    if len(random)==expected:
        matrix=np.column_stack([np.r_[manifest['capital'],available[k].account_equity] for k in random])
        for name,q in [('p05',.05),('median',.5),('p95',.95)]:result[name]=np.quantile(matrix,q,axis=1)
        result['random_n']=len(random)
    for k,spec in specs.items():
        if k in available and spec['kind'] in ['ai_fair','legacy_ai','common_pre_ai']:
            result[spec['pool_id']]=np.r_[manifest['capital'],available[k].account_equity]
    result['window_id']=w['window_id'];result['family']=family
    return result


def standard_figures(windows,bands,comparisons,cohorts,turnover_bands):
    """Five fixed, offline interactive figures. Bands require every registered path."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    def panel(fig,w,row,col,family='IID',data=None):
        d=bands.get(w['window_id'],pd.DataFrame()) if data is None else data
        if d.empty:
            fig.add_annotation(text='尚无完成账户',showarrow=False,row=row,col=col);return
        if 'p05' in d:
            fig.add_trace(go.Scatter(x=d.date,y=d.p95/10000,line=dict(width=0),name=family+' P95',showlegend=False),row=row,col=col)
            fig.add_trace(go.Scatter(x=d.date,y=d.p05/10000,line=dict(width=0),fill='tonexty',fillcolor='rgba(70,130,180,.16)',name=family+' P05–P95',showlegend=False),row=row,col=col)
            fig.add_trace(go.Scatter(x=d.date,y=d['median']/10000,line=dict(color='#547aa5',dash='dash'),name=family+' 中位',showlegend=False),row=row,col=col)
        for name,color,label in [('AI_FAIR','#e08230','研究 AI'),('LEGACY_AI','#888888','原物料参照'),('COMMON_PRE_AI','#728968','共同前史账户')]:
            if name in d:fig.add_trace(go.Scatter(x=d.date,y=d[name]/10000,name=label,line=dict(color=color,width=2),showlegend=False),row=row,col=col)
        if 'p05' not in d:fig.add_annotation(text='随机样本未齐：分位带暂不展示',showarrow=False,xanchor='left',row=row,col=col)
    full=[w for w in windows if w['group'] in ('historical_full','ai_primary')]
    full=sorted(full,key=lambda w:w['start'])
    f=make_subplots(rows=max(1,len(full)),cols=1,subplot_titles=[w['window_id'] for w in full] or ['全周期：等待数据'])
    for i,w in enumerate(full,1):
        panel(f,w,i,1)
        tb=turnover_bands.get(w['window_id'],pd.DataFrame())
        if len(tb) and 'median' in tb:
            f.add_trace(go.Scatter(x=tb.date,y=tb['median']/10000,name='换池匹配随机中位',line=dict(color='#ad64ab',dash='dot'),showlegend=False),row=i,col=1)
    figures=[('01_full_period','全周期：研究 AI 橙色、IID 蓝色、换池匹配紫色、原物料灰色',f)]
    for years,key,title in [(1,'02_one_year','完整 1 年冷启动'),(2,'03_two_year','完整 2 年冷启动'),(3,'04_three_year','完整 3 年冷启动')]:
        subset=sorted([w for w in windows if w['group']==f'{years}y'],key=lambda w:(w['start'],w['window_id']))
        fig=make_subplots(rows=max(1,math.ceil(len(subset)/2)),cols=2,subplot_titles=[f"{w['start']} → {w['end']} · {w['policy_phase']}" for w in subset])
        for i,w in enumerate(subset):panel(fig,w,i//2+1,i%2+1)
        figures.append((key,title,fig))
    fig=make_subplots(rows=1,cols=2,subplot_titles=['全部窗口：AI−IID 中位收益百分点','纯 AI 六 cohort：收益差中位数'])
    if len(comparisons) and 'return_delta_pp' in comparisons:
        c=comparisons[comparisons.sample_complete.astype(bool)].sort_values(['start','duration_years'])
        if len(c):fig.add_trace(go.Heatmap(z=[[safe(v)] for v in c.return_delta_pp],y=c.window_id,x=['收益差 pp'],colorscale='RdBu',zmid=0,colorbar=dict(title='pp'),hoverongaps=False),row=1,col=1)
    if len(cohorts):
        c=cohorts[cohorts.policy_phase.eq('ai_active_only')&cohorts.start_cohort.ne('combined')]
        z=[[safe(c.loc[(c.duration_years==y)&(c.start_cohort==s),'median_return_delta_pp'].iloc[0]) if len(c[(c.duration_years==y)&(c.start_cohort==s)]) and bool(c.loc[(c.duration_years==y)&(c.start_cohort==s),'complete'].iloc[0]) else None for s in ['January','June']] for y in [1,2,3]]
        fig.add_trace(go.Heatmap(z=z,x=['January','June'],y=['1 年','2 年','3 年'],colorscale='RdBu',zmid=0,showscale=False,hoverongaps=False),row=1,col=2)
    figures.append(('05_multicycle_summary','多周期汇总：空白表示未完成；共同前史不计 AI 证据',fig))
    for key,title,fig in figures:
        fig.update_layout(title=title,template='plotly_white',height=800 if key in ('01_full_period','05_multicycle_summary') else max(450,math.ceil(sum(w['group']=={'02_one_year':'1y','03_two_year':'2y','04_three_year':'3y'}.get(key,'') for w in windows)/2)*260),margin=dict(l=60,r=25,t=90,b=50),font=dict(family='Arial, sans-serif',size=11))
        if key!='05_multicycle_summary':fig.update_yaxes(title_text='权益（万元）')
    return figures



def standard_static_images(windows,bands,comparisons,cohorts,turnover_bands,output):
    """The fixed five exportable images, using the runner's existing matplotlib overlay."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt,dates as mdates,font_manager
    fonts={f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams.update({'font.family':[f for f in ['Arial Unicode MS','PingFang SC','Heiti TC','Noto Sans CJK SC','DejaVu Sans'] if f in fonts],'axes.unicode_minus':False,'font.size':9})
    paths=[]
    def save(fig,name):
        for extension in ['png','svg']:
            p=Path(output)/(name+'.'+extension);fig.savefig(p,dpi=140);paths.append(p)
        plt.close(fig)
    def panel(ax,w,d):
        phase={'ai_active_only':'纯 AI','mixed_pre_ai_and_ai':'共同前史＋AI','common_pre_ai_only':'共同前史'}[w['policy_phase']]
        ax.set_title(f"{w['start']} → {w['end']} · {phase}",fontsize=9)
        if d.empty:
            ax.text(.5,.5,'尚无完成账户',ha='center',va='center',transform=ax.transAxes);ax.set_axis_off();return
        dates=pd.to_datetime(d.date,format='mixed')
        if 'p05' in d:
            ax.fill_between(dates,d.p05/10000,d.p95/10000,color='#547aa5',alpha=.15,label='IID P05–P95')
            ax.plot(dates,d['median']/10000,color='#547aa5',linestyle='--',label='IID 中位')
        else:ax.text(.02,.96,'随机样本未齐：不展示分位带',transform=ax.transAxes,va='top',fontsize=8,color='#777777')
        for name,color,label in [('AI_FAIR','#e08230','研究 AI'),('LEGACY_AI','#888888','原物料参照'),('COMMON_PRE_AI','#728968','共同前史')]:
            if name in d:ax.plot(dates,d[name]/10000,color=color,lw=1.4,label=label)
        locator=mdates.AutoDateLocator(minticks=3,maxticks=5);ax.xaxis.set_major_locator(locator);ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.set_ylabel('权益（万元）');ax.grid(alpha=.2)
        if ax.lines:ax.legend(fontsize=7,loc='best')
    full=sorted([w for w in windows if w['group'] in ['historical_full','ai_primary']],key=lambda w:w['start'])
    fig,axes=plt.subplots(max(1,len(full)),1,figsize=(13,4.2*max(1,len(full))),squeeze=False,layout='constrained')
    for i,w in enumerate(full):
        ax=axes[i,0];panel(ax,w,bands.get(w['window_id'],pd.DataFrame()));tb=turnover_bands.get(w['window_id'],pd.DataFrame())
        if len(tb) and 'median' in tb:
            ax.plot(pd.to_datetime(tb.date,format='mixed'),tb['median']/10000,color='#ad64ab',linestyle=':',label='换池匹配随机中位');ax.legend(fontsize=8)
    fig.suptitle('全周期独立账户 · 初始 15 万 · 未全量时仅进度',fontsize=13);save(fig,'01_full_period')
    for years,name in [(1,'02_one_year'),(2,'03_two_year'),(3,'04_three_year')]:
        subset=sorted([w for w in windows if w['group']==f'{years}y'],key=lambda w:w['start']);nrows=max(1,math.ceil(len(subset)/2))
        fig,axes=plt.subplots(nrows,2,figsize=(14,2.85*nrows),squeeze=False,layout='constrained')
        for ax in axes.flat:ax.set_axis_off()
        for i,w in enumerate(subset):
            ax=axes.flat[i];ax.set_axis_on();panel(ax,w,bands.get(w['window_id'],pd.DataFrame()))
        fig.suptitle(f'完整 {years} 年 · 按起点排序（同年 1 月先于 6 月）',fontsize=13);save(fig,name)
    fig,axes=plt.subplots(1,2,figsize=(15,10),gridspec_kw={'width_ratios':[2,1]},layout='constrained')
    items=sorted(windows,key=lambda w:(w['start'],w['duration_years']));values=[];lookup=comparisons.set_index('window_id') if len(comparisons) else pd.DataFrame()
    for w in items:
        v=lookup.loc[w['window_id']] if w['window_id'] in lookup.index else None
        values.append(float(v.return_delta_pp) if v is not None and v.sample_complete and pd.notna(v.return_delta_pp) else np.nan)
    z=np.array(values,dtype=float).reshape(-1,1);bound=max(1.,float(np.max(np.abs(z[np.isfinite(z)])))) if np.isfinite(z).any() else 1.
    if len(z):
        image=axes[0].imshow(np.ma.masked_invalid(z),aspect='auto',cmap='RdBu',vmin=-bound,vmax=bound)
        axes[0].set_yticks(range(len(items)),[w['window_id'] for w in items],fontsize=7);axes[0].set_xticks([0],['AI − IID 中位（pp）']);fig.colorbar(image,ax=axes[0],shrink=.6)
    axes[0].set_title('全部窗口 · 空白=未完成；共同前史不算证据')
    pure=cohorts[cohorts.policy_phase.eq('ai_active_only')&cohorts.start_cohort.ne('combined')] if len(cohorts) else pd.DataFrame();z=np.full((3,2),np.nan)
    for i,y in enumerate([1,2,3]):
        for j,c in enumerate(['January','June']):
            cell=pure[(pure.duration_years==y)&(pure.start_cohort==c)] if len(pure) else pd.DataFrame()
            if len(cell) and bool(cell.iloc[0].complete) and pd.notna(cell.iloc[0].median_return_delta_pp):z[i,j]=cell.iloc[0].median_return_delta_pp
    bound=max(1.,float(np.max(np.abs(z[np.isfinite(z)])))) if np.isfinite(z).any() else 1.
    im=axes[1].imshow(np.ma.masked_invalid(z),aspect='auto',cmap='RdBu',vmin=-bound,vmax=bound);fig.colorbar(im,ax=axes[1],shrink=.6)
    axes[1].set_yticks(range(3),['1 年','2 年','3 年']);axes[1].set_xticks([0,1],['1 月','6 月']);axes[1].set_title('纯 AI 六 cohort · 收益差中位数（pp）')
    for i in range(3):
        for j in range(2):axes[1].text(j,i,f'{z[i,j]:.1f}' if np.isfinite(z[i,j]) else '未完成',ha='center',va='center')
    fig.suptitle('多周期描述汇总 · 不合并 q，不作独立投票检验',fontsize=13);save(fig,'05_multicycle_summary')
    return paths


def main_window_table(comparisons):
    labels={'window_id':'窗口','start':'起始日','end':'结束日','policy_phase':'阶段','sample_complete':'样本齐全','completed_random':'随机已完成','random_n':'随机计划 N','ai_end_equity':'AI 期末权益','ai_total_return_pct':'AI 收益 %','random_total_return_pct_median':'随机中位收益 %','return_delta_pp':'收益差 pp','ai_max_dd_pct':'AI 最大回撤 %','dd_depth_delta_pp':'回撤深度差 pp','ai_sharpe':'AI Sharpe','sharpe_delta':'Sharpe 差','b':'随机≥AI 个数 b','q':'加一比例 q','strict_data_review_gate':'严格数据验收'}
    display=comparisons.reindex(columns=list(labels)).rename(columns=labels).copy()
    if '阶段' in display:display['阶段']=display['阶段'].map({'ai_active_only':'纯 AI 期','mixed_pre_ai_and_ai':'共同前史＋AI','common_pre_ai_only':'仅共同前史'})
    if '样本齐全' in display:display['样本齐全']=display['样本齐全'].map({True:'齐全',False:'未齐'})
    if '严格数据验收' in display:display['严格数据验收']=display['严格数据验收'].map({True:'通过',False:'未通过 / 诊断'})
    return display


def policy_descriptions(manifest):
    qp=Path(manifest['qualification_path'])
    if digest(qp)!=manifest['qualification_sha256']:raise ValueError('qualification source changed')
    q=read_json(qp);details=[]
    for pool_id,spec in manifest['policies'].items():
        p=Path(spec['pool_file'])
        if digest(p)!=spec['pool_sha256']:raise ValueError('frozen policy changed: '+pool_id)
        frame=read_csv(p);previous=None
        for date,group in frame.groupby('eval_date',sort=True):
            members=set(group.product_vt_symbol)-{'fu.SHFE'}
            if date in q:
                valid=set(q[date]['U_members']);effective=members&valid
                # LEGACY is descriptive only; it intentionally retains its original nominal list.
                details.append(dict(pool_id=pool_id,kind=spec['kind'],eval_date=date,effective_signal_date=q[date]['effective_signal_trade_date'],qualified_universe_n=len(valid),target_effective_nonfu_K=q[date]['K'],nominal_nonfu_width=len(members),effective_nonfu_width=len(effective),nominal_new_members=len(members-previous) if previous is not None else None,member_set=';'.join(sorted(members)),fu_present='fu.SHFE' in set(group.product_vt_symbol)))
                previous=members
    details=pd.DataFrame(details);window_rows=[]
    for w in manifest['windows']:
        for pool_id in {s['pool_id'] for s in manifest['accounts'].values() if s['window_id']==w['window_id']}:
            d=details[details.pool_id.eq(pool_id)].sort_values('effective_signal_date')
            if len(d):
                before=d[d.effective_signal_date.le(w['start'])].tail(1);within=d[d.effective_signal_date.gt(w['start'])&d.effective_signal_date.le(w['end'])];active=pd.concat([before,within]).drop_duplicates('eval_date')
            else:active=d
            window_rows.append(dict(window_id=w['window_id'],pool_id=pool_id,policy_phase=w['policy_phase'],ai_months_active=len(active),effective_nonfu_width_min=float(active.effective_nonfu_width.min()) if len(active) else None,effective_nonfu_width_max=float(active.effective_nonfu_width.max()) if len(active) else None,effective_nonfu_width_snapshot_mean=float(active.effective_nonfu_width.mean()) if len(active) else None,mean_monthly_nominal_new_members=float(within.nominal_new_members.mean()) if len(d) and len(within) else None,pre_ai_rule='共同基础 19（含 fu），真实上市和预热门约束；无 AI 月选择' if w['policy_phase']!='ai_active_only' and pool_id!='LEGACY_AI' else '原物料前史 18，无 fu' if pool_id=='LEGACY_AI' else '不适用'))
    return details,pd.DataFrame(window_rows)


def decision_summary(manifest,accounts,comparisons,cohorts,registration_ok):
    done=accounts.status.eq('complete');audited=accounts.independent_audit_status.astype(str).str.startswith('PASS')&done
    complete=bool(done.all() and audited.all() and registration_ok)
    main=comparisons[comparisons.window_id.eq(manifest['primary_window'])].iloc[0]
    six=cohorts[cohorts.policy_phase.eq('ai_active_only')&cohorts.start_cohort.ne('combined')]
    primary_gates=all(main.get(k) is not None and pd.notna(main.get(k)) and bool(main.get(k)) for k in ['rank_gate','sharpe_not_below_median','dd_depth_not_above_median'])
    cohort_gate=bool(len(six)==6 and six.complete.all() and six.support_gate.fillna(False).all())
    strict=bool(complete and accounts.strict_engine_and_data.fillna(False).all()) if 'strict_engine_and_data' in accounts else False
    if not complete:
        grade='INCOMPLETE';verdict='账户或独立审计尚未收齐，仅进度快照；不作最终排名结论。'
    elif not strict:
        grade='COMPLETE_DIAGNOSTIC_ONLY';verdict='冻结样本与账本审计完成，但诊断模式或执行缺口限制解释；不能给出严格优越性结论。'
    elif primary_gates and cohort_gate:
        grade='HISTORICAL_SUPPORT_NOT_PROMOTION';verdict='预声明历史比较门满足，仍不是点时训练证明、未来盈利概率或生产晋升。'
    else:
        grade='NO_BROAD_HISTORICAL_SUPPORT';verdict='至少一项主要收益、风险或纯 AI 跨周期门未满足，不支持广泛历史优势。'
    return dict(status=grade,verdict=verdict,physical_expected=len(accounts),physical_complete=int(done.sum()),physical_validation_failed=int(accounts.status.eq('validation_failed').sum()),physical_independently_audited=int(audited.sum()),all_accounts_and_reviews_complete=complete,registration_review_passed=bool(registration_ok),primary_gates_satisfied=primary_gates if complete else None,six_pure_ai_cohorts_satisfied=cohort_gate if complete else None,strict_data_review_gate=strict,promotion_eligible=False)


def carryover_years(manifest,daily_by_id):
    records=[]
    for rid,d in daily_by_id.items():
        s=manifest['accounts'][rid]
        if s['window_id']!='full_20200101_20261014':continue
        for year in sorted({x[:4] for x in d.date}):
            records.append(dict(run_id=rid,window_id=s['window_id'],pool_id=s['pool_id'],year=int(year),**period_stats(d,year+'-01-01',year+'-12-31',manifest['capital']),scope='carryover capital/positions; NOT independent yearly account'))
    return pd.DataFrame(records)


def table_html(frame,columns=None):
    if frame.empty:return '<p>尚无符合条件的完成结果。</p>'
    if columns is not None:frame=frame[[c for c in columns if c in frame]]
    return '<div class="table-wrap">'+frame.to_html(index=False,escape=True,float_format=lambda v:f'{v:,.3f}',na_rep='—',border=0)+'</div>'


def build_report(experiment,output,require_complete=False):
    experiment=Path(experiment).resolve();output=Path(output).resolve();mp=experiment/'experiment_manifest.json';mh=digest(mp)
    if mh!=FROZEN_MANIFEST_SHA:raise ValueError('Stage257 manifest differs from pre-performance freeze')
    manifest=read_json(mp)
    if output==experiment or output==experiment/'accounts' or experiment/'accounts' in output.parents:raise ValueError('output must not replace experiment/account inputs')
    registration_path=experiment/'independent_reviews/registration.json';registration=read_json(registration_path) if registration_path.is_file() else {}
    registration_ok=registration.get('status')=='PASS' and registration.get('experiment_manifest_sha256')==mh and not registration.get('errors')
    allrows=[];daily_by_id={};products=[];cycles=[];gaps=[];bindings={}
    for rid in manifest['accounts']:
        row,d,ps,cs,gs,hashes=account_summary(experiment,rid,manifest,mh)
        allrows.append(row);products.extend(ps);cycles.extend(cs);gaps.extend(gs)
        if d is not None:daily_by_id[rid]=d
        if hashes:bindings[rid]=dict(source_hashes=hashes,independent_audit_sha256=row.get('independent_audit_sha256'),independent_audit_status=row['independent_audit_status'])
    accounts=pd.DataFrame(allrows)
    # Require the common accepted trading calendar, including flat/no-trade days.
    calendar=read_csv(Path(manifest['accepted_calendar_daily'])).date.astype(str)
    for rid,d in list(daily_by_id.items()):
        spec=manifest['accounts'][rid];expected=calendar[calendar.between(spec['start'],spec['end'])].tolist()
        if d.date.tolist()!=expected:
            accounts.loc[accounts.run_id.eq(rid),['status','error']]=['validation_failed','daily calendar differs from accepted common calendar'];del daily_by_id[rid]
    comparisons=pd.DataFrame([window_comparison(manifest,w,accounts) for w in manifest['windows']])
    primary=next(w for w in manifest['windows'] if w['window_id']==manifest['primary_window'])
    turnover=pd.DataFrame([window_comparison(manifest,primary,accounts,'turnover_matched')])
    cohorts=cohort_summary(manifest['windows'],comparisons);decision=decision_summary(manifest,accounts,comparisons,cohorts,registration_ok)
    if require_complete and not decision['all_accounts_and_reviews_complete']:raise ValueError('require-complete: missing/failed account, stale/pending independent audit or registration')
    details,widths=policy_descriptions(manifest)
    accounts=accounts.merge(widths,on=['window_id','pool_id'],how='left',validate='one_to_one')
    aliases=pd.DataFrame([dict(alias_run_id=k,source_run_id=v,window_id=manifest['accounts'][v]['window_id'],source_status=accounts.set_index('run_id').loc[v,'status'],independent_evidence=False) for k,v in manifest['aliases'].items()])
    good=accounts[accounts.status.eq('complete')]
    legacy=accounts[accounts.kind.eq('legacy_ai')].copy()
    if len(legacy):
        ai=accounts[accounts.kind.eq('ai_fair')].set_index('window_id')
        legacy['legacy_minus_fair_equity']=[r.end_equity-ai.loc[r.window_id].get('end_equity',np.nan) if hasattr(r,'end_equity') and r.status=='complete' else None for r in legacy.itertuples()]
    yearly=carryover_years(manifest,daily_by_id)
    worst=[]
    for col,ascending,label in [('end_equity',True,'最低期末权益'),('max_dd_pct',True,'最深回撤'),('max_broker10_margin_to_equity_pct',False,'最高保证金/权益'),('longest_drawdown_trading_days',False,'最长回撤交易日'),('days_equity_nonpositive',False,'资金生存失败天数')]:
        if col in good:
            for row in good.sort_values(col,ascending=ascending).head(10).to_dict('records'):worst.append(dict(risk_order=label,**row))
    worst=pd.DataFrame(worst)
    bands={w['window_id']:make_bands(w,manifest,daily_by_id) for w in manifest['windows']}
    tb={primary['window_id']:make_bands(primary,manifest,daily_by_id,'turnover_matched')}
    bridge_path=experiment/'independent_reviews/agent_reviews/first_batch_reference_bridges.json'
    bridge=read_json(bridge_path) if bridge_path.is_file() else {}
    summary=dict(reference_bridge_review=dict(path=str(bridge_path),sha256=digest(bridge_path) if bridge else None,results=bridge),stage=257,generated_at=datetime.now().astimezone().isoformat(),**decision,experiment_manifest_sha256=mh,script_sha256=digest(Path(__file__)),ledger_dependency_sha256=digest(Path(__file__).with_name('stage256_build_report.py')),registration_review_sha256=digest(registration_path) if registration_path.is_file() else None,logical_expected=len(manifest['accounts'])-len(set(manifest['aliases'].values()))+len(manifest['aliases']),alias_labels=len(manifest['aliases']),window_count=len(manifest['windows']),primary_window=manifest['primary_window'],primary_endpoint='end_equity; b=count(random>=AI); q=(b+1)/(N+1)',common_pre_ai_evidence=False,data_input_sha256=manifest['minute_cache_sha256'],primary_comparison=comparisons[comparisons.window_id.eq(manifest['primary_window'])].to_dict('records')[0],turnover_comparison=turnover.to_dict('records')[0],bound_accounts=bindings,limitations=['全部账户为冻结现有分钟诊断回放；会计通过不等于执行严格完整。','共同前史不含可识别 AI 选择效应；公平资格/固定 fu 与原物料规则差异另列。','49 条只描述；重叠窗口与共享政策不是独立样本，不合并 q。','历史模型/特征发布时点未重建；2025–2026 已用于研究，2026 部分名单存在后补分。','两倍滑点是固定各自成交的静态扣减，不重算后续手数、退出或风险门。','资金归零、无交易、极端亏损和缺口账户保留，不按结果选种子。'])
    # The immutable snapshot directory is completed before report/index.html is atomically replaced.
    output.mkdir(parents=True,exist_ok=True);snapshots=output/'snapshots';snapshots.mkdir(exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.building-',dir=snapshots))
    frames={'accounts':accounts,'windows':comparisons,'turnover_comparison':turnover,'cohorts':cohorts,'aliases':aliases,'legacy_references':legacy,'product_contributions':pd.DataFrame(products),'closed_cycles':pd.DataFrame(cycles),'data_gaps':pd.DataFrame(gaps),'full2020_yearly_carryover':yearly,'worst_accounts':worst,'pool_monthly_descriptions':details,'window_pool_descriptions':widths}
    for name,frame in frames.items():frame.to_csv(staging/(name+'.csv'),index=False)
    for wid,frame in bands.items():
        if len(frame):frame.to_csv(staging/(wid+'_curves.csv'),index=False)
    if len(tb[primary['window_id']]):tb[primary['window_id']].to_csv(staging/'primary_turnover_curves.csv',index=False)
    static_paths=standard_static_images(manifest['windows'],bands,comparisons,cohorts,tb,staging)
    figs=standard_figures(manifest['windows'],bands,comparisons,cohorts,tb)
    fragments=[]
    for i,(name,title,fig) in enumerate(figs):
        fig.write_html(staging/(name+'.html'),include_plotlyjs=True,full_html=True)
        fragments.append(fig.to_html(full_html=False,include_plotlyjs=True if i==0 else False,div_id=name))
    bridge_text='<p>首批独立桥接复核：'+ ('原物料 2020 全期参照与 Stage251 C_final 的 646 条成交核心、1,641 日日账逐值一致；AI 起点公平版与原物料的 336 条成交、1,136 日日账逐值一致。此为底座与参照复现证据，不是随机对照优势。' if bridge.get('legacy_full_vs_stage251_C_final',{}).get('passed') and bridge.get('primary_fair_vs_legacy',{}).get('passed') else '桥接证据尚未齐全，暂不作复现结论。')+'</p>'
    text_head=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Stage257 多周期研究 · {decision['status']}</title><style>body{{max-width:1500px;margin:30px auto;padding:0 22px;font:15px/1.65 -apple-system,BlinkMacSystemFont,sans-serif;color:#203040;background:#f8fafc}}h1,h2{{line-height:1.35}}.banner{{padding:18px;background:#fff1cf;border-left:5px solid #ce8f24}}.table-wrap{{overflow:auto;background:white;margin:18px 0;max-height:700px}}table{{border-collapse:collapse;font-size:12px}}th,td{{padding:7px 10px;border-bottom:1px solid #e1e6eb;white-space:nowrap;text-align:right}}th{{position:sticky;top:0;background:#edf2f7}}code{{overflow-wrap:anywhere}}a{{color:#215f98}}</style><h1>Stage257：关闭 0.5R 后的 AI 月池多周期研究</h1><div class="banner"><b>{decision['status']}</b> · {html.escape(decision['verdict'])}<br>完成 {decision['physical_complete']:,} / 1,955 个实体账户，独审通过 {decision['physical_independently_audited']:,}；33 个窗口全部列出，2,151 个逻辑标签含 200 个共同前史别名。</div><p>每窗独立空仓 150,000 元，手续费 0、原模型滑点；0.5R 关闭、C2 保留。初始本金计入回撤。研究 AI、公平同宽随机和换池匹配随机基于冻结规则，2 条原物料 AI 只作参照。报告生成时间：{summary['generated_at']}。</p>'''
    method='''<h2>判定与证据等级</h2><p>唯一主要终点为 2022-02-07 起独立账户的期末权益。199 个 IID 随机全部完成才计算 b（随机权益≥AI 的个数）与 q=(b+1)/200；主要排名门 b≤9，且 Sharpe 不低于随机中位、回撤深度不高于随机中位。六个纯 AI 1/2/3 年×1月/6月 cohort 的收益差中位数须均非负。全部账户和独审未齐时不宣告最终结论；诊断执行缺口阻止严格优越性验收。49 路径单窗只描述，分母 50，不进行 5% 显著性判断。</p><p>2020 全周期和换池匹配组分别报告，不能合并为 398 次同种抽样。Wilson 区间是冻结历史与随机政策条件下的超越比例不确定度，不是未来胜率。窗口高度重叠、同随机路径跨窗复用，不能套独立投票检验。YTD 不参与成熟窗口判断；共同前史别名不计 N、b/q 或 AI 胜率。</p>'''
    windowcols=['window_id','start','end','policy_phase','evidence_role','sample_complete','completed_random','random_n','ai_end_equity','ai_total_return_pct','random_total_return_pct_median','return_delta_pp','ai_max_dd_pct','dd_depth_delta_pp','ai_sharpe','sharpe_delta','b','q','all_independent_audits_passed','strict_data_review_gate']
    sections=[text_head,method,'<h2>全部 33 窗与独立年度账户</h2>',table_html(main_window_table(comparisons)),'<h2>主要窗口：换池匹配随机独立家族</h2>',table_html(main_window_table(turnover)),'<h2>两条原物料参照</h2>',bridge_text,table_html(legacy,['run_id','status','end_equity','total_return_pct','max_dd_pct','sharpe','legacy_minus_fair_equity','independent_audit_status']),'<h2>固定五图</h2><p>橙色为研究 AI，蓝色为随机中位和 P05–P95 分位带（不是可交易账户），灰色为原物料，绿色为共同前史。未收齐随机的窗口不画部分样本分位带。每条曲线从初始 15 万开始。</p>',*fragments,'<p>五张独立图片：'+ ' · '.join(f'<a href="{p.name}">{p.name}</a>' for p in static_paths)+'</p>','<h2>期限 × 起点 × AI 历史阶段</h2>',table_html(cohorts),'<h2>最弱窗口、风险与资金生存</h2><p>下表为当前完成账户的风险极值；未完成时不能视为最终最差。回撤深度差为 AI 深度减随机中位，正数更差。保证金按每日 broker10 占权益衡量；日末持仓比例不含日内已开平敞口。</p>',table_html(worst,['risk_order','window_id','pool_id','end_equity','max_dd_pct','sharpe','max_broker10_margin_to_equity_pct','days_broker_margin_over_100','days_equity_nonpositive','longest_drawdown_trading_days','end_equity_2x_slippage_static','total_slippage','path_data_incomplete']),'<h2>全期逐年贡献：承接资金和持仓</h2><p>这是 2020 全账户的年度切片，不能当作年度冷启动。完整随机年度明细见 CSV；这里展示研究 AI 和原物料。</p>',table_html(yearly[yearly.pool_id.isin(['AI_FAIR','LEGACY_AI'])] if len(yearly) else yearly),'<h2>数据、模型与过拟合边界</h2><ul>',''.join('<li>'+html.escape(x)+'</li>' for x in summary['limitations']),'</ul><p>57 个 AI 月份中有效非 fu 宽度为 7 的 6 个月、8 的 10 个月、9 的 2 个月、10 的 39 个月；固定 fu 另计。前史共同基础 19 并不等于当时全部可交易，真实上市与预热门继续约束。过滤早期未上市名额改善比较公平性，不能修复原 AI 训练或特征的历史可见性。</p><p>本次报告不调参、不改窗、不增种子，不新增按结果选择的过拟合；已有研究选择与历史模型风险仍在。继续完成已冻结样本有价值，可区分起点、期限和换池惯性；扩大样本不能制造更多独立市场历史，也不能用诊断结果承诺未来收益。</p>','<h2>审计绑定与下载</h2>',f'<p>Manifest SHA256：<code>{mh}</code><br>分钟输入 SHA256：<code>{manifest["minute_cache_sha256"]}</code><br>报告器 SHA256：<code>{summary["script_sha256"]}</code></p><p>逐账户完整来源哈希与独审状态在 summary.json；来源变动会标记 stale。亏损、零成交、未完成和失败账户都在 accounts.csv。完整周期胜率仅已平仓周期；期末残余 MTM 另列，关闭 0.5R 时周期与合并 retry 的 episode 相同。2 倍滑点按各自真实成交成本再扣一次，属于静态压力。</p><ul>', ''.join(f'<li><a href="{name}.csv">{name}.csv</a></li>' for name in frames),'<li><a href="summary.json">summary.json</a> · <a href="artifact_manifest.json">产物 SHA 清单</a></li></ul></html>']
    (staging/'index.html').write_text(''.join(sections),encoding='utf-8')
    (staging/'summary.json').write_text(json.dumps(safe(summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    artifacts={p.name:digest(p) for p in staging.iterdir() if p.is_file()}
    (staging/'artifact_manifest.json').write_text(json.dumps(dict(experiment_manifest_sha256=mh,artifacts=artifacts),ensure_ascii=False,indent=2)+'\n')
    if digest(mp)!=mh:raise ValueError('manifest changed during report build')
    snapshot_name=datetime.now().strftime('%Y%m%dT%H%M%S%f');published=snapshots/snapshot_name;staging.rename(published)
    pointer=dict(snapshot=str(published),summary_sha256=digest(published/'summary.json'),status=decision['status'])
    temporary=output/'.latest.json.tmp';temporary.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n');os.replace(temporary,output/'latest.json')
    relative='snapshots/'+snapshot_name+'/index.html';entry=output/'.index.html.tmp';entry.write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={relative}"><a href="{relative}">Stage257 报告快照 · {decision["status"]}</a>');os.replace(entry,output/'index.html')
    return pointer


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--output',type=Path);ap.add_argument('--require-complete',action='store_true');args=ap.parse_args(argv)
    result=build_report(args.experiment,args.output or args.experiment/'report',args.require_complete)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
