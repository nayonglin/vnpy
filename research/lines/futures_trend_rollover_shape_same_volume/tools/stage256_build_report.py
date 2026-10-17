"""Stage256 frozen-account reporting only; no engine, pool mutation or network."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import html
import re
from datetime import datetime
from pathlib import Path
import unittest
import numpy as np
import pandas as pd


def wilson_interval(b:int,n:int)->list[float]:
    if n<=0 or not 0<=b<=n:raise ValueError('Invalid Monte Carlo count')
    z=1.959963984540054;p=b/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]


def cycle_ledger(trades:pd.DataFrame,positions:pd.DataFrame,params:dict,last_date:str)->tuple:
    if trades.empty:return [],[],0.
    active={};closed=[];cost_total=0.
    trades=trades.assign(_id=trades.trade_id.str.rsplit('.',n=1).str[-1].astype(int)).sort_values('_id')
    for t in trades.to_dict('records'):
        symbol=t['vt_symbol'];size=float(params['contract_sizes'][symbol])
        cost=float(t['volume'])*size*(float(t['price'])*float(params['rates'][symbol])+float(params['slippages'][symbol]))
        cost_total+=cost;signed=float(t['signed_volume']);opening=t['offset'] in ('开','Open','OPEN')
        if symbol not in active:
            if not opening:raise ValueError('Close without an active cycle')
            active[symbol]=dict(vt_symbol=symbol,first_trade_id=t['trade_id'],entry_date=t.get('trading_date'),signed_pos=0.,cash=0.,cost=0.,opened_volume=0.,trade_count=0)
        item=active[symbol];prior=item['signed_pos']
        if opening:
            if prior and np.sign(prior)!=np.sign(signed):raise ValueError('Cross-direction open')
            item['opened_volume']+=abs(signed)
        elif np.sign(prior)==np.sign(signed) or abs(prior)+1e-8<abs(signed):raise ValueError('Invalid close quantity')
        item['signed_pos']+=signed;item['cash']-=signed*float(t['price'])*size;item['cost']+=cost;item['trade_count']+=1
        if abs(item['signed_pos'])<1e-8:
            item.update(last_trade_id=t['trade_id'],exit_date=t.get('trading_date'),net_pnl=item['cash']-item['cost'])
            closed.append(item);del active[symbol]
    marks=positions[positions.date.eq(last_date)].set_index('vt_symbol') if len(positions) else pd.DataFrame()
    remaining=[]
    for symbol,item in active.items():
        if symbol not in marks.index:raise ValueError('Open position has no final mark')
        mark=marks.loc[symbol]
        if abs(float(mark.end_pos)-item['signed_pos'])>1e-8:raise ValueError('Final position differs from ledger')
        item['net_mtm']=item['cash']+item['signed_pos']*float(mark.close_price)*params['contract_sizes'][symbol]-item['cost']
        remaining.append(item)
    return closed,remaining,cost_total


def period_stats(daily:pd.DataFrame,start:str,end:str,capital:float)->dict:
    before=daily[daily.date.lt(start)];part=daily[daily.date.between(start,end)]
    if part.empty:return dict(start_equity=None,end_equity=None,return_pct=None,max_dd_pct=None,net_pnl=None)
    initial=float(before.account_equity.iloc[-1]) if len(before) else capital
    path=np.r_[initial,part.account_equity.to_numpy(float)];peak=np.maximum.accumulate(path)
    return dict(start_equity=initial,end_equity=float(path[-1]),return_pct=(path[-1]/initial-1)*100 if initial>0 else None,max_dd_pct=float(np.min(path/peak-1)*100) if (peak>0).all() else None,net_pnl=float(part.net_pnl.sum()))


def digest(path:Path)->str:
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read_json(path:Path)->dict:return json.loads(path.read_text())


def read_csv(path:Path,columns=())->pd.DataFrame:
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame(columns=columns)


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def close(a,b,label):
    if not math.isclose(float(a),float(b),abs_tol=1e-6,rel_tol=1e-10):raise ValueError(f'{label}: {a} != {b}')


def number(value)->float:
    return float(value) if value is not None else float('nan')


REQUIRED=['metrics.json','daily.csv','trades.csv','positions.csv','execution_clock.csv','execution_proxy_usage.csv','effective_parameters.json','minute_scan_requests.csv','execution_anchor_requests.csv','entry_candidates.csv','run_provenance.json','stage256_account_provenance.json']
EXPECTED=['AI_MONTHLY','AI_INITIAL_FIXED']+[f'RANDOM_{i:03d}' for i in range(1,200)]


def account_summary(experiment:Path,account_id:str,manifest:dict)->tuple:
    run=experiment/'accounts'/account_id
    row=dict(account_id=account_id,kind=manifest['accounts'][account_id]['kind'],path_id=manifest['accounts'][account_id].get('path_id'),status='incomplete',error='')
    missing=[name for name in REQUIRED if not (run/name).is_file()]
    if missing:
        row['error']='未完成/缺文件：'+','.join(missing)
        return row,None,[],[],{},[]
    inputs={name:digest(run/name) for name in REQUIRED}
    row['_source_hashes']=inputs
    try:
        metrics=read_json(run/'metrics.json');provenance=read_json(run/'run_provenance.json');params=read_json(run/'effective_parameters.json')
        sidecar=read_json(run/'stage256_account_provenance.json');spec=manifest['accounts'][account_id]
        if sidecar.get('account_id')!=account_id or not sidecar.get('completed_at'):raise ValueError('Missing Stage256 account identity')
        if sidecar.get('input_sha256_before')!=sidecar.get('input_sha256_after'):raise ValueError('Stage256 input guard failed')
        if sidecar['input_sha256_before']['pool']!=spec['pool_sha256'] or sidecar['input_sha256_before']['registry']!=digest(experiment/'experiment_manifest.json'):raise ValueError('Stage256 pool/manifest identity mismatch')
        if sidecar.get('half_r_enabled') is not False or sidecar.get('ai_pool_enabled') is not True:raise ValueError('Stage256 policy switch mismatch')
        if not provenance.get('completed_at'):raise ValueError('Missing completion receipt')
        if provenance.get('minute_input_sha256')!=manifest['minute_cache_sha256']:raise ValueError('Minute cache identity mismatch')
        if not provenance.get('all_data_and_model_inputs_unchanged_during_run'):raise ValueError('Input change guard not passed')
        if metrics['start']!=manifest['start'] or metrics['end']!=manifest['end']:raise ValueError('Account interval mismatch')
        capital=float(manifest['capital']);close(metrics['account_capital'],capital,'capital')
        daily=read_csv(run/'daily.csv').sort_values('date').reset_index(drop=True)
        if daily.empty or daily.date.duplicated().any() or not daily.date.between(manifest['start'],manifest['end']).all():raise ValueError('Daily chronology mismatch')
        close(daily.account_equity.iloc[-1],metrics['end_equity'],'end equity')
        close(capital+daily.net_pnl.sum(),metrics['end_equity'],'net accounting')
        close((daily.account_equity-(capital+daily.net_pnl.cumsum())).abs().max(),0,'daily accounting')
        trades=read_csv(run/'trades.csv');clock=read_csv(run/'execution_clock.csv');usage=read_csv(run/'execution_proxy_usage.csv');positions=read_csv(run/'positions.csv', ['date','vt_symbol','end_pos','close_price','net_pnl'])
        close(len(trades),metrics['total_trade_count'],'fill count')
        if len(trades):
            if not trades.trade_id.is_unique or set(trades.trade_id)!=set(clock.trade_id) or set(trades.trade_id)!=set(usage.trade_id):raise ValueError('Trade/clock identity mismatch')
            mapped=trades.trade_id.map(clock.set_index('trade_id').trading_date)
            if 'trading_date' in trades and not trades.trading_date.eq(mapped).all():raise ValueError('Trade date/clock mismatch')
            trades['trading_date']=mapped
        cycles,opened,cost=cycle_ledger(trades,positions,params,str(daily.date.iloc[-1]))
        close(sum(x['net_pnl'] for x in cycles)+sum(x['net_mtm'] for x in opened),daily.net_pnl.sum(),'closed plus open MTM')
        close(cost,daily.slippage.sum()+daily.commission.sum(),'costs')
        close(daily.slippage.sum(),metrics['total_slippage'],'slippage')
        wins=[x['net_pnl'] for x in cycles if x['net_pnl']>1e-6];losses=[x['net_pnl'] for x in cycles if x['net_pnl']<-1e-6]
        scans=read_csv(run/'minute_scan_requests.csv', ['vt_symbol','trading_date','coverage_status','requested_start','session_end_exclusive','missing_bar_count','expected_bar_count'])
        if len(scans):
            if not scans.groupby(['vt_symbol','trading_date']).session_end_exclusive.nunique().le(1).all():raise ValueError('Inconsistent scan union')
            scans=scans.sort_values('requested_start').drop_duplicates(['vt_symbol','trading_date'])
        anchors=read_csv(run/'execution_anchor_requests.csv',['vt_symbol','trading_date','expected_start','coverage_status','order_id'])
        anchor_keys=anchors.drop_duplicates(['vt_symbol','trading_date','expected_start'])
        bad_scans=scans[scans.coverage_status.ne('complete')];bad_anchors=anchors[anchors.coverage_status.ne('complete')]
        bad_keys=set(zip(bad_scans.vt_symbol,bad_scans.trading_date));bad_orders=set(bad_anchors.order_id)
        affected=trades.iloc[0:0].copy()
        if len(trades):
            mask=[(t.offset in ('开','Open','OPEN') and (t.vt_symbol,t.trading_date) in bad_keys) or t.order_id in bad_orders for t in trades.itertuples()]
            affected=trades.loc[mask]
        notional=sum(abs(float(t.volume)*float(t.price)*params['contract_sizes'][t.vt_symbol]) for t in affected.itertuples())
        diag=bool(provenance.get('diagnostic_incomplete_minutes'));gaps=bool(len(bad_scans) or len(bad_anchors))
        row.update(status='complete',end_equity=float(metrics['end_equity']),total_return_pct=float(metrics['total_return_pct']),max_dd_pct=float(metrics['max_dd_pct']),sharpe=number(metrics['sharpe']),total_slippage=float(daily.slippage.sum()),commission=float(daily.commission.sum()),fill_count=len(trades),actual_turnover=float(daily.turnover.sum()),closed_cycles=len(cycles),cycle_win_rate_pct=len(wins)/len(cycles)*100 if cycles else None,profit_factor=sum(wins)/-sum(losses) if losses else None,profit_factor_infinite=bool(wins and not losses),mean_win_loss_ratio=(np.mean(wins)/-np.mean(losses)) if wins and losses else None,cycle_wins=len(wins),cycle_losses=len(losses),cycle_flats=len(cycles)-len(wins)-len(losses),end_open_contracts=len(opened),end_open_episode_net_mtm=sum(x['net_mtm'] for x in opened),largest_closed_cycle_pnl=max([x['net_pnl'] for x in cycles],default=None),worst_closed_cycle_pnl=min([x['net_pnl'] for x in cycles],default=None),max_broker10_margin_to_equity_pct=metrics.get('max_broker10_margin_to_equity_pct'),days_equity_below_zero=metrics.get('days_equity_below_zero'),scan_keys=len(scans),incomplete_scan_keys=len(bad_scans),missing_entry_minutes=int(scans.missing_bar_count.sum()),required_entry_minutes=int(scans.expected_bar_count.sum()),ordinary_anchor_keys=len(anchor_keys),missing_ordinary_anchor_keys=int(anchor_keys.coverage_status.ne('complete').sum()),missing_anchor_fill_requests=len(bad_anchors),affected_fill_count=len(affected),affected_fill_gross_notional=notional,diagnostic_mode=diag,path_data_incomplete=gaps,strict_engine_and_data=not(diag or gaps),minute_input_sha256=provenance['minute_input_sha256'],run_provenance_sha256=inputs['run_provenance.json'],end_equity_2x_slippage_static=float(metrics['end_equity']-daily.slippage.sum()),total_return_pct_2x_slippage_static=float((metrics['end_equity']-daily.slippage.sum())/capital*100-100))
        static=daily[['date','account_equity','net_pnl']].copy();static['account_equity']-=daily.slippage.cumsum();static['net_pnl']-=daily.slippage
        row['max_dd_pct_2x_slippage_static']=period_stats(static,manifest['start'],manifest['end'],capital)['max_dd_pct']
        for label,start,end in [('2025','2025-01-01','2025-12-31'),('2026','2026-01-01',manifest['end']),('since_202509','2025-09-01',manifest['end'])]:
            row.update({f'{label}_{key}':value for key,value in period_stats(daily,start,end,capital).items()})
        candidates=read_csv(run/'entry_candidates.csv',['candidate_status'])
        row['recorded_candidates']=len(candidates);row['blocked_candidates']=int(candidates.candidate_status.eq('skipped').sum())
        positions=positions[positions.date.between(manifest['start'],manifest['end'])].copy()
        products=[]
        if len(positions):
            positions['product']=positions.vt_symbol.map(lambda x:re.sub(r'\d+','',x))
            products=[dict(account_id=account_id,product=k,net_pnl=float(g.net_pnl.sum()),turnover=float(g.turnover.sum())) for k,g in positions.groupby('product')]
            close(sum(x['net_pnl'] for x in products),daily.net_pnl.sum(),'product contributions')
        signal_volumes={}
        if len(trades):
            signal_dates=usage.set_index('trade_id').signal_date
            for t in trades[trades.offset.isin(['开','Open','OPEN'])].itertuples():
                key=(str(signal_dates.loc[t.trade_id]),t.vt_symbol,'long' if t.signed_volume>0 else 'short')
                signal_volumes[key]=signal_volumes.get(key,0.)+float(t.volume)
        gap_rows=[dict(account_id=account_id,kind='entry_scan',vt_symbol=t.vt_symbol,trading_date=t.trading_date,missing_minutes=int(t.missing_bar_count)) for t in bad_scans.itertuples()]
        gap_rows += [dict(account_id=account_id,kind='ordinary_anchor',vt_symbol=t.vt_symbol,trading_date=t.trading_date,missing_minutes=1) for t in anchor_keys[anchor_keys.coverage_status.ne('complete')].itertuples()]
        audit_path=experiment/'independent_reviews/accounts'/f'{account_id}.json'
        row['independent_audit_status']='pending'
        if audit_path.is_file():
            audit=read_json(audit_path)
            audit_hashes=audit.get('source_hashes',{})
            valid=audit.get('experiment_manifest_sha256')==digest(experiment/'experiment_manifest.json') and all(audit_hashes.get(name)==value for name,value in inputs.items() if name!='stage256_account_provenance.json')
            row['independent_audit_status']=audit.get('status','unknown') if valid else 'stale'
        return row,daily,products,[dict(account_id=account_id,**x) for x in cycles],signal_volumes,gap_rows
    except (ValueError,KeyError,AssertionError,TypeError) as exc:
        row.update(status='validation_failed',error=f'{type(exc).__name__}: {exc}')
        return row,None,[],[],{},[]


def pool_turnover(experiment:Path,manifest:dict)->pd.DataFrame:
    rows=[];dates=list(manifest['expected_eval_dates'])
    for account_id,info in manifest['accounts'].items():
        path=Path(info['pool_file']);path=path if path.is_absolute() else experiment/path
        if digest(path)!=info['pool_sha256']:raise ValueError('Frozen pool hash mismatch: '+account_id)
        pool=read_csv(path);symbol_col='product_vt_symbol' if 'product_vt_symbol' in pool else 'vt_symbol'
        previous=None
        for date in dates:
            part=pool[pool.eval_date.astype(str).eq(date)]
            current=set(part[symbol_col].astype(str))-{'fu.SHFE'}
            if len(part)!=11 or len(current)!=10 or not current<=set(manifest['non_fu_universe']):raise ValueError('Wrong pool membership: '+account_id+' '+date)
            rows.append(dict(account_id=account_id,eval_date=date,non_fu_count=10,non_fu_members='|'.join(sorted(current)),added_count=None if previous is None else len(current-previous),retained_count=None if previous is None else len(current&previous),removed_count=None if previous is None else len(previous-current),turnover_rate=None if previous is None else len(current-previous)/10))
            previous=current
    return pd.DataFrame(rows)


def comparison_summary(accounts:pd.DataFrame)->dict:
    complete=accounts.status.eq('complete');random=accounts[accounts.account_id.str.startswith('RANDOM_')]
    result=dict(expected_accounts=201,completed_accounts=int(complete.sum()),expected_random_accounts=199,completed_random_accounts=int(random.status.eq('complete').sum()),all_accounts_complete=bool(len(accounts)==201 and complete.all()),b=None,plus_one_exceedance_q=None,wilson95_conditional_exceedance_probability=None,strict_support=False,conclusion='201个账户未全部完成，不给最终胜负或经验尾部排名。')
    if not result['all_accounts_complete']:return result
    ai=accounts.set_index('account_id').loc['AI_MONTHLY'];fixed=accounts.set_index('account_id').loc['AI_INITIAL_FIXED']
    b=int(random.end_equity.ge(ai.end_equity).sum())
    risks=dict(sharpe=bool(ai.sharpe>=random.sharpe.median()),drawdown_depth=bool(-ai.max_dd_pct<=(-random.max_dd_pct).median()))
    segments={year:bool(ai[f'{year}_return_pct']>=random[f'{year}_return_pct'].median()) for year in ('2025','2026')}
    principal=accounts[accounts.account_id.ne('AI_INITIAL_FIXED')]
    audit_pass=accounts.independent_audit_status.astype(str).str.lower().str.startswith('pass').all()
    strict=bool(principal.strict_engine_and_data.all() and audit_pass)
    tail=b<=9;support=strict and tail and all(risks.values()) and all(segments.values())
    if not audit_pass:conclusion='独立审查尚未全部通过；可展示诊断结果，不给严格胜出/有效性结论。'
    elif not strict:
        conclusion=('201账户独立账目与逻辑审查通过，但分钟覆盖不完整；' +
                    ('诊断排名也未达到预注册优势阈值，不能证明AI选品明显优于随机。' if not tail else '仅展示诊断排名，不能给严格胜出/有效性结论。'))
    elif support:conclusion='这段历史对既有AI月池政策有较强支持；不代表跨周期泛化或纯AI预测能力。'
    elif tail and not (all(risks.values()) and all(segments.values())):conclusion='收益占优但风险/稳定性不占优，未形成较强支持。'
    else:conclusion='未形成较强支持；不能自动反推AI一定无效。'
    fields=['end_equity','total_return_pct','max_dd_pct','sharpe','2025_return_pct','2026_return_pct','end_equity_2x_slippage_static']
    quantiles={field:{label:float(random[field].quantile(q)) for label,q in [('min',0),('p05',.05),('p25',.25),('median',.5),('p75',.75),('p95',.95),('max',1)]} for field in fields}
    result.update(b=b,plus_one_exceedance_q=(b+1)/200,wilson95_conditional_exceedance_probability=wilson_interval(b,199),raw_exceedance_fraction=b/199,rank_gate=tail,risk_gates=risks,segment_gates=segments,strict_data_and_review_gate=strict,all_independent_audits_passed=bool(audit_pass),strict_support=bool(support),conclusion=conclusion,random_quantiles=quantiles,ai_minus_fixed_end_equity=float(ai.end_equity-fixed.end_equity),principal_accounts_with_minute_gaps=int(principal.path_data_incomplete.sum()),principal_accounts_in_diagnostic_mode=int(principal.diagnostic_mode.sum()))
    return result


def figures(accounts:pd.DataFrame,bands:pd.DataFrame,turnover:pd.DataFrame,summary:dict)->list:
    import plotly.graph_objects as go
    figures=[];byid=accounts.set_index('account_id');random=accounts[accounts.account_id.str.startswith('RANDOM_')&accounts.status.eq('complete')]
    if not bands.empty:
        chart=go.Figure()
        chart.add_trace(go.Scatter(x=bands.date,y=bands.p95,name='随机逐日P95',line=dict(width=0),hovertemplate='%{x}<br>P95 %{y:,.0f}<extra></extra>'))
        chart.add_trace(go.Scatter(x=bands.date,y=bands.p05,name='随机P05—P95区间',fill='tonexty',fillcolor='rgba(100,116,139,.18)',line=dict(width=0)))
        chart.add_trace(go.Scatter(x=bands.date,y=bands['median'],name='随机逐日中位',line=dict(color='#64748b',width=2)))
        for key,name,color in [('AI_MONTHLY','既有AI月池','#c2410c'),('AI_INITIAL_FIXED','初始AI固定名单','#2563eb')]:
            if key in bands:chart.add_trace(go.Scatter(x=bands.date,y=bands[key],name=name,line=dict(color=color,width=2.3)))
        chart.update_layout(title='连续账户净权益：随机逐日分位带不是可交易的组合',xaxis_title='交易日',yaxis_title='权益（元）',hovermode='x unified',template='plotly_white',height=520)
        figures.append(('净权益路径',chart))
    if len(random):
        chart=go.Figure(go.Histogram(x=random.end_equity,name=f'已完成随机账户（{len(random)}）',marker_color='#94a3b8',nbinsx=25))
        for key,name,color in [('AI_MONTHLY','既有AI月池','#c2410c'),('AI_INITIAL_FIXED','初始AI固定名单','#2563eb')]:
            if key in byid.index and byid.loc[key,'status']=='complete':chart.add_vline(x=float(byid.loc[key,'end_equity']),line_color=color,line_width=3,annotation_text=name,annotation_position='top right' if key=='AI_MONTHLY' else 'top left')
        chart.update_layout(title='固定199条随机路径的期末权益分布'+('' if summary['all_accounts_complete'] else '（仅已完成快照，不给最终排名）'),xaxis_title='模型内成本后期末权益（元）',yaxis_title='账户数量',template='plotly_white',height=440)
        figures.append(('期末权益分布',chart))
    if len(turnover):
        chart=go.Figure();rand=turnover[turnover.account_id.str.startswith('RANDOM_')].dropna(subset=['added_count'])
        q=rand.groupby('eval_date').added_count.quantile([.05,.5,.95]).unstack()
        chart.add_trace(go.Scatter(x=q.index,y=q[.95],name='随机换入P95',line=dict(width=0)))
        chart.add_trace(go.Scatter(x=q.index,y=q[.05],name='随机换入P05—P95',fill='tonexty',fillcolor='rgba(100,116,139,.18)',line=dict(width=0)))
        chart.add_trace(go.Scatter(x=q.index,y=q[.5],name='随机换入中位',line=dict(color='#64748b')))
        for key,name,color in [('AI_MONTHLY','AI换入数','#c2410c'),('AI_INITIAL_FIXED','固定名单换入数','#2563eb')]:
            part=turnover[turnover.account_id.eq(key)].dropna(subset=['added_count'])
            chart.add_trace(go.Scatter(x=part.eval_date,y=part.added_count,name=name,mode='lines+markers',line=dict(color=color)))
        chart.update_layout(title='每期非fu名单换入数（首次建池不计换手）',xaxis_title='评估日；当日不提前生效',yaxis_title='换入品种数 / 10个名额',template='plotly_white',height=420)
        figures.append(('月池换手',chart))
    return figures


def fmt(value,digits=2):
    if value is None or pd.isna(value):return 'N/A'
    return f'{value:,.{digits}f}'


def static_comparison(experiment:Path,accounts:pd.DataFrame,bands:pd.DataFrame,summary:dict)->None:
    """Final-only export; standard matplotlib with the Stage249 font fallback."""
    if not summary['all_accounts_complete'] or bands.empty:return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Supplemental/Arial Unicode.ttf']:
        if Path(name).exists():
            font_manager.fontManager.addfont(name);plt.rcParams['font.family']=font_manager.FontProperties(fname=name).get_name();break
    plt.rcParams['axes.unicode_minus']=False
    random=accounts[accounts.account_id.str.startswith('RANDOM_')];byid=accounts.set_index('account_id')
    fig,axes=plt.subplots(2,1,figsize=(13,10),gridspec_kw={'height_ratios':[1.35,1]})
    dates=pd.to_datetime(bands.date)
    axes[0].fill_between(dates,bands.p05.to_numpy()/10000,bands.p95.to_numpy()/10000,color='#94a3b8',alpha=.25,label='随机逐日P05—P95')
    axes[0].plot(dates,bands['median']/10000,color='#64748b',linewidth=1.5,label='随机逐日中位')
    for account,label,color in [('AI_MONTHLY','既有AI月池','#c2410c'),('AI_INITIAL_FIXED','初始AI固定名单','#2563eb')]:
        axes[0].plot(dates,bands[account]/10000,color=color,linewidth=1.9,label=label)
    axes[0].set_title('2025独立15万元账户：关闭0.5R，保留C2与其余正式底座',loc='left',fontweight='bold')
    axes[0].set_ylabel('净权益（万元，含未平仓MTM）');axes[0].legend(frameon=False,ncol=2);axes[0].grid(alpha=.17)
    axes[1].hist(random.end_equity/10000,bins=25,color='#94a3b8',edgecolor='white',label='全部199个随机账户')
    for account,label,color in [('AI_MONTHLY','既有AI月池','#c2410c'),('AI_INITIAL_FIXED','初始AI固定名单','#2563eb')]:
        value=byid.loc[account,'end_equity']/10000
        axes[1].axvline(value,color=color,linewidth=2,label=f'{label}：{value:.3f}万')
    axes[1].set_xlabel('期末权益（万元）');axes[1].set_ylabel('账户数');axes[1].legend(frameon=False)
    lo,hi=summary['wilson95_conditional_exceedance_probability']
    axes[1].set_title(f"条件随机参照：b={summary['b']}/199，q={summary['plus_one_exceedance_q']:.2%}；Wilson 95% {lo:.2%}—{hi:.2%}",loc='left',fontsize=11)
    status='仅现有数据诊断分布，不给严格胜出结论' if not summary['strict_data_and_review_gate'] else summary['conclusion']
    fig.suptitle('Stage256｜'+status,fontsize=14,y=.995)
    fig.text(.075,.01,'2025-01-01—2026-10-14；手续费0，保留模型滑点。逐日分位带不是可交易组合；q不是泛化p值。\n固定名单也从15万元独立开始，期末含未平仓MTM；不得与2020起点的历史累计收益混用。',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.97));fig.savefig(experiment/'report_comparison.png',dpi=170);fig.savefig(experiment/'report_comparison.svg');plt.close(fig)


def write_report(experiment:Path,accounts:pd.DataFrame,bands:pd.DataFrame,turnover:pd.DataFrame,summary:dict)->None:
    selected=accounts[accounts.account_id.isin(['AI_MONTHLY','AI_INITIAL_FIXED'])].copy()
    columns={'account_id':'账户','status':'状态','end_equity':'期末权益','total_return_pct':'收益%','max_dd_pct':'最大回撤%','sharpe':'Sharpe','2025_return_pct':'2025收益%','2026_return_pct':'2026截至末日收益%','total_slippage':'滑点','fill_count':'成交笔数','closed_cycles':'完整周期','cycle_win_rate_pct':'周期胜率%','profit_factor':'盈亏因子','end_open_episode_net_mtm':'未平仓周期净MTM','missing_entry_minutes':'入场缺分钟','missing_ordinary_anchor_keys':'缺首锚','end_equity_2x_slippage_static':'2倍滑点静态期末权益'}
    selected=selected[[c for c in columns if c in selected]].rename(columns=columns)
    notes=[
        '比较同一关闭0.5R底座：C2、独立pairwise候选排序与多头量倾斜保留。AI臂是既有月池政策，不是纯AI能力测试。每账户15万元，2025-01-01独立空仓开始，数据截止2026-10-14。',
        '本轮AI为2025年独立15万元账户，不是Stage251从2020开始的1542.32%累计收益。固定初始名单同样从2025年15万元起步；期末权益包含未平仓净MTM，完整周期胜率不包含未平仓。',
        '每期10个非fu＋固定fu；199个随机路径全部保留，包括无交易和真实亏损路径。故障单独标记，不删除、换种子或改窗口。',
        '执行记录：首批三个账户曾因导入环境失败，RANDOM_101曾在初始化读取共同基础池CSV时遇到并发空文件；均发生在交易前。保留原失败日志后，用相同账户ID、相同冻结池重启，没有替换样本或修改抽样。成功账户实际候选19品种完整性由独立审计核验。',
        'q=(b+1)/200，b为随机期末权益大于等于AI的路径数，平局计入超越。Wilson区间基于b/199，只表示此历史和抽样协议条件下的Monte Carlo不确定度，不是泛化p值、AI无效概率或未来盈利概率。',
        '2026分段继承2025年末权益与仓位，不是独立冷启动，也不是第二份独立市场证据。逐日分位带不是一条真实可交易账户路径。',
        '任何主比较路径存在未解决分钟缺口，整批仅为现有数据诊断分布；不得剔除缺口账户来改善排名。缺口关联成交额只量化受影响路径暴露，不代表已估出误差或收益修正。',
        '2倍滑点是每个账户自身固定成交路径再扣一份滑点的静态压力估算，不包含仓位、信号、退出与保证金反馈，不能称重跑。现有手续费为0，不能称真实券商费后收益。',
        'AI名单更连续；独立月随机10/18预期换入4.44个品种。结果含换池惯性、行业暴露、竞争和资金反馈。固定初始AI组只回答保留当时名单的结果，不能单独隔离预测能力。',
        '保留既有后验选择、2026年3—5月成员锁定后补分、旧训练源未因Stage249修复而重生成等限制。此历史不是未触碰OOS；更多种子不增加新的市场历史。',
    ]
    rank_text='未完成：不计算最终经验尾部排名。'
    if summary['all_accounts_complete']:
        lo,hi=summary['wilson95_conditional_exceedance_probability']
        rank_text=f"b={summary['b']}/199；加一经验超越比例 q={summary['plus_one_exceedance_q']:.2%}；条件超越概率的 Wilson 95% 区间 {lo:.2%}—{hi:.2%}。"
    gate_text='完整账户尚未齐备，风险与分段门待计算。'
    if summary['all_accounts_complete']:
        labels=[('Sharpe不低于随机中位',summary['risk_gates']['sharpe']),('回撤深度不大于随机中位',summary['risk_gates']['drawdown_depth']),('2025收益不低于随机中位',summary['segment_gates']['2025']),('2026收益不低于随机中位',summary['segment_gates']['2026'])]
        gate_text='；'.join(label+'：'+('通过' if value else '未通过') for label,value in labels)
        ai=accounts.set_index('account_id').loc['AI_MONTHLY']
        random=accounts[accounts.account_id.str.startswith('RANDOM_')]
        notes[:0]=[
            f"实际结果：AI收益{ai.total_return_pct:.2f}%，随机中位{random.total_return_pct.median():.2f}%；199组中{summary['b']}组期末权益不低于AI。预注册较强支持要求最多9组，本次未达到。此结论不等于证明AI完全无用。",
            f"分段表现：2025年AI收益{ai['2025_return_pct']:.2f}%，随机中位{random['2025_return_pct'].median():.2f}%；2026年至截止日AI收益{ai['2026_return_pct']:.2f}%，随机中位{random['2026_return_pct'].median():.2f}%。本段历史表现为2025落后、2026较抗跌，不能直接归因为普适预测能力。",
            f"数据覆盖不对称：AI入场扫描缺分钟{int(ai.missing_entry_minutes)}、缺普通成交首锚{int(ai.missing_ordinary_anchor_keys)}；随机组每户入场扫描缺分钟{int(random.missing_entry_minutes.min()):,}—{int(random.missing_entry_minutes.max()):,}、缺首锚{int(random.missing_ordinary_anchor_keys.min())}—{int(random.missing_ordinary_anchor_keys.max())}。相同缓存并不代表各条路径覆盖相同，无法据此确定收益误差大小与方向。",
        ]
    markdown=['# Stage256 随机10品种与既有AI月池比较',f"生成：{summary['generated_at']}",f"完成 {summary['completed_accounts']}/201 账户；随机 {summary['completed_random_accounts']}/199。",summary['conclusion'],rank_text,gate_text,'## AI与固定初始名单']
    markdown.append(selected.to_csv(index=False))
    if summary.get('random_quantiles'):markdown+=['## 199组随机分布分位',pd.DataFrame(summary['random_quantiles']).to_csv()]
    markdown+=['## 判断边界']+['- '+x for x in notes]
    markdown+=['## 文件','完整201账户：report_accounts.csv；完整199随机：report_random_199.csv；周期：report_cycles.csv；逐品种贡献：report_product_contribution.csv；实际共同/独有开仓信号：report_signal_comparison.csv；逐日分位：report_daily_quantiles.csv；名单换手：report_pool_turnover.csv；缺口：report_data_gaps.csv；来源：report_input_hashes.json。','## 反思','本轮没有按结果选种子、窗口或参数，不新增这类过拟合；既有历史选模风险仍在。此对照值得完成，但不能通过加种子、改阈值或补挑案例挽救不利结果。']
    (experiment/'report.md').write_text('\n\n'.join(markdown)+'\n')
    import plotly.io as pio
    chart_html=[]
    for i,(title,figure) in enumerate(figures(accounts,bands,turnover,summary)):
        chart_html.append(pio.to_html(figure,full_html=False,include_plotlyjs=True if i==0 else False,config={'displaylogo':False,'responsive':True}))
        figure.write_json(experiment/f'report_chart_{i+1}.json')
    quantile_html=pd.DataFrame(summary.get('random_quantiles',{})).to_html(float_format=lambda x:f'{x:,.3f}') if summary.get('random_quantiles') else '<p>全部账户完成前不生成最终分布分位。</p>'
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage256 随机10与AI月池</title><style>body{font:15px/1.6 system-ui,sans-serif;color:#1e293b;background:#f8fafc;margin:0}main{max-width:1400px;margin:auto;padding:28px}section{background:white;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin:18px 0;overflow:auto}.status{background:#fff7ed;border-left:5px solid #c2410c}table{border-collapse:collapse;font-size:13px;white-space:nowrap}td,th{padding:7px 10px;border-bottom:1px solid #e2e8f0;text-align:right}h1{font-size:27px}a{color:#1d4ed8}</style><main><h1>Stage256：既有AI月池与随机10品种</h1>'
    page+=f'<section class="status"><b>{html.escape(summary["conclusion"])}</b><p>完整账户 {summary["completed_accounts"]}/201；随机 {summary["completed_random_accounts"]}/199</p><p>{html.escape(rank_text)}</p><p>{html.escape(gate_text)}</p></section>'
    page+='<section><h2>AI月池与初始固定名单</h2>'+selected.to_html(index=False,float_format=lambda x:f'{x:,.3f}')+'</section>'
    page+=''.join('<section>'+x+'</section>' for x in chart_html)
    page+='<section><h2>完整随机分布分位</h2>'+quantile_html+'</section><section><h2>解释与边界</h2><ul>'+''.join('<li>'+html.escape(note)+'</li>' for note in notes)+'</ul></section>'
    page+='<section><h2>完整明细与来源</h2>'+''.join(f'<p><a href="{name}">{label}</a></p>' for name,label in [('report_accounts.csv','201账户完整明细'),('report_random_199.csv','199随机路径完整明细'),('report_product_contribution.csv','逐品种贡献'),('report_cycles.csv','完整持仓周期'),('report_signal_comparison.csv','实际共同与独有开仓信号'),('report_pool_turnover.csv','22期名单交集与换入'),('report_data_gaps.csv','实际数据缺口'),('report_input_hashes.json','冻结输入SHA'),('report_summary.json','机器结论与门')])+'</section></main></html>'
    (experiment/'report.html').write_text(page)


def build(experiment:Path)->dict:
    experiment=experiment.resolve();manifest_path=experiment/'experiment_manifest.json';manifest=read_json(manifest_path)
    if set(manifest['accounts'])!=set(EXPECTED) or manifest['random_count']!=199:raise ValueError('Expected exactly the preregistered 201 accounts')
    manifest_sha=digest(manifest_path);rows=[];daily_by_id={};products=[];cycles=[];signals={};gaps=[];source_hashes={}
    for i,account_id in enumerate(EXPECTED):
        row,daily,prod,cyc,sig,gap=account_summary(experiment,account_id,manifest)
        source_hashes[account_id]=row.pop('_source_hashes',{})
        rows.append(row);products.extend(prod);cycles.extend(cyc);signals[account_id]=sig;gaps.extend(gap)
        if daily is not None:daily_by_id[account_id]=daily
        if (i+1)%25==0:print(f'报告读取 {i+1}/201',flush=True)
    accounts=pd.DataFrame(rows);summary=comparison_summary(accounts)
    random_ids=[x for x in EXPECTED if x.startswith('RANDOM_') and x in daily_by_id]
    bands=pd.DataFrame()
    if random_ids:
        calendars={tuple(daily_by_id[x].date) for x in daily_by_id}
        if len(calendars)!=1:raise ValueError('Account daily calendars differ; no silent interpolation')
        matrix=pd.concat([daily_by_id[x].set_index('date').account_equity.rename(x) for x in random_ids],axis=1)
        bands=pd.DataFrame({'date':matrix.index,'p05':matrix.quantile(.05,axis=1).values,'median':matrix.median(axis=1).values,'p95':matrix.quantile(.95,axis=1).values,'random_account_count':len(random_ids)})
        for account_id in ['AI_MONTHLY','AI_INITIAL_FIXED']:
            if account_id in daily_by_id:bands[account_id]=daily_by_id[account_id].set_index('date').account_equity.reindex(bands.date).values
    turnover=pool_turnover(experiment,manifest)
    signal_comparisons=[];ai_signals=signals.get('AI_MONTHLY',{})
    if 'AI_MONTHLY' in daily_by_id:
        for account_id in EXPECTED[1:]:
            if account_id not in daily_by_id:continue
            other=signals[account_id];common=ai_signals.keys()&other.keys()
            signal_comparisons.append(dict(account_id=account_id,ai_actual_open_signals=len(ai_signals),other_actual_open_signals=len(other),common_signals=len(common),ai_only_signals=len(ai_signals.keys()-other.keys()),other_only_signals=len(other.keys()-ai_signals.keys()),common_with_different_volume=sum(not math.isclose(ai_signals[k],other[k]) for k in common),comparison_scope='actual opening fills grouped by signal_date/contract/direction; not counterfactual outcomes'))
    for name,frame in [('accounts',accounts),('random_199',accounts[accounts.account_id.str.startswith('RANDOM_')]),('daily_quantiles',bands),('pool_turnover',turnover),('product_contribution',pd.DataFrame(products)),('cycles',pd.DataFrame(cycles)),('signal_comparison',pd.DataFrame(signal_comparisons)),('data_gaps',pd.DataFrame(gaps))]:
        frame.to_csv(experiment/f'report_{name}.csv',index=False,encoding='utf-8-sig')
    summary.update(generated_at=datetime.now().astimezone().isoformat(),experiment=str(experiment),experiment_manifest_sha256=manifest_sha,report_script_sha256=digest(Path(__file__)),capital=manifest['capital'],start=manifest['start'],end=manifest['end'],master_seed=manifest['master_seed'],minute_cache_sha256=manifest['minute_cache_sha256'],mc_interval_semantics='Wilson 95% for b/199 conditional on frozen history and random-pool generator; q=(b+1)/200 is a plus-one descriptive empirical exceedance statistic, not a generalization p value.',cost_stress_semantics='Fixed own-fill path, subtract one extra slippage; no sizing/margin/execution feedback.',rerun=False,market_download=False,training=False,production_access=False)
    if digest(manifest_path)!=manifest_sha:raise ValueError('Experiment manifest changed during report')
    (experiment/'report_input_hashes.json').write_text(json.dumps(dict(experiment_manifest_sha256=manifest_sha,accounts=source_hashes),ensure_ascii=False,indent=2)+'\n')
    (experiment/'report_summary.json').write_text(json.dumps(safe(summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    write_report(experiment,accounts,bands,turnover,summary)
    static_comparison(experiment,accounts,bands,summary)
    print(json.dumps(safe({key:summary[key] for key in ['completed_accounts','completed_random_accounts','b','plus_one_exceedance_q','conclusion']}),ensure_ascii=False),flush=True)
    return summary


class ReportTests(unittest.TestCase):
    def test_wilson_zero_and_all_are_not_certainty(self):
        low,high=wilson_interval(0,199)
        self.assertAlmostEqual(low,0)
        self.assertGreater(high,0)
        self.assertLess(high,.025)
        low,high=wilson_interval(199,199)
        self.assertLess(low,1)
        self.assertAlmostEqual(high,1)

    def test_partial_close_and_residual_costed_once(self):
        trades=pd.DataFrame([
            dict(trade_id='T.1',vt_symbol='x1.EX',offset='开',signed_volume=2,volume=2,price=100),
            dict(trade_id='T.2',vt_symbol='x1.EX',offset='平',signed_volume=-1,volume=1,price=110),
            dict(trade_id='T.3',vt_symbol='y1.EX',offset='开',signed_volume=-1,volume=1,price=100),
            dict(trade_id='T.4',vt_symbol='y1.EX',offset='平',signed_volume=1,volume=1,price=105)])
        positions=pd.DataFrame([dict(date='2026-01-02',vt_symbol='x1.EX',end_pos=1,close_price=120)])
        params=dict(contract_sizes={'x1.EX':10,'y1.EX':10},rates={'x1.EX':0,'y1.EX':0},slippages={'x1.EX':1,'y1.EX':1})
        cycles,opened,cost=cycle_ledger(trades,positions,params,'2026-01-02')
        self.assertEqual(len(cycles),1)
        self.assertAlmostEqual(cycles[0]['net_pnl'],-70)
        self.assertAlmostEqual(opened[0]['net_mtm'],270)
        self.assertAlmostEqual(cost,50)

    def test_zero_trade_account_is_valid(self):
        self.assertEqual(cycle_ledger(pd.DataFrame(),pd.DataFrame(),{},'2026-01-02'),([],[],0.))

    def test_year_uses_prior_account_equity(self):
        daily=pd.DataFrame(dict(date=['2025-12-31','2026-01-02','2026-01-05'],account_equity=[200000,180000,210000],net_pnl=[50000,-20000,30000],slippage=[0,0,0]))
        result=period_stats(daily,'2026-01-01','2026-10-14',150000)
        self.assertAlmostEqual(result['return_pct'],5)
        self.assertAlmostEqual(result['max_dd_pct'],-10)
        self.assertEqual(result['start_equity'],200000)

    def test_partial_batch_does_not_rank(self):
        summary=comparison_summary(pd.DataFrame([dict(account_id='AI_MONTHLY',status='complete'),dict(account_id='RANDOM_001',status='complete')]))
        self.assertIsNone(summary['b'])
        self.assertIsNone(summary['plus_one_exceedance_q'])
        self.assertFalse(summary['strict_support'])

    def test_distribution_chart_reads_median_column(self):
        accounts=pd.DataFrame([dict(account_id='AI_MONTHLY',status='complete',end_equity=160000),dict(account_id='AI_INITIAL_FIXED',status='complete',end_equity=150000),dict(account_id='RANDOM_001',status='complete',end_equity=140000)])
        bands=pd.DataFrame(dict(date=['2025-01-02'],p05=[150000],median=[150000],p95=[150000],AI_MONTHLY=[150000],AI_INITIAL_FIXED=[150000]))
        charts=figures(accounts,bands,pd.DataFrame(),{'all_accounts_complete':False})
        self.assertEqual(list(charts[0][1].data[2].y),[150000])
        self.assertEqual(len(charts),2)

    def test_ties_count_and_gap_forces_diagnostic(self):
        rows=[]
        for account in EXPECTED:
            rows.append(dict(account_id=account,status='complete',end_equity=101 if account=='AI_MONTHLY' else 100,total_return_pct=1,max_dd_pct=-10,sharpe=1,independent_audit_status='PASS_COVERAGE_COMPLETE',strict_engine_and_data=True,path_data_incomplete=False,diagnostic_mode=False,end_equity_2x_slippage_static=90,**{'2025_return_pct':1,'2026_return_pct':1}))
        frame=pd.DataFrame(rows)
        self.assertEqual(comparison_summary(frame)['plus_one_exceedance_q'],.005)
        frame.loc[frame.account_id.eq('RANDOM_001'),['end_equity','path_data_incomplete','strict_engine_and_data']]=[101,True,False]
        summary=comparison_summary(frame)
        self.assertEqual(summary['b'],1)
        self.assertEqual(summary['plus_one_exceedance_q'],.01)
        self.assertFalse(summary['strict_support'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--experiment',type=Path);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:unittest.main(argv=['stage256_build_report'],exit=True)
    elif args.experiment:build(args.experiment)
    else:parser.error('--experiment or --self-test is required')
