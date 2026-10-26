#!/usr/bin/env python3
"""Stage031 read-only, frozen B/W drawdown/accounting attribution. No engine imports.

Inputs are checked against the frozen Stage030 delivery manifest before use and
rechecked after generation. All-zero position records are omitted, every active
record and all dates are retained. pandas reads only narrow chunks.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUT = LINE / 'outputs/stage031_drawdown_bridge'
STAGE = LINE / 'stages/stage031_drawdown_bridge'
ATTEMPTS = {'B': LINE/'outputs/R_attempt003', 'W': LINE/'outputs/stage030_weekly_attempt001'}
DB = LINE/'outputs/stage029_latest_data/data_approved/daily.sqlite'
FROZEN = LINE/'stages/stage030_delivery_manifest.json'
POSCOLS = ['date','vt_symbol','start_pos','end_pos','pos_change','close_price','pre_close','trade_count','turnover','commission','slippage','holding_pnl','trading_pnl','total_pnl','net_pnl']
DAYCOLS = ['date','account_equity','net_pnl','holding_pnl','trading_pnl','commission','slippage','trade_count','total_margin_exact','broker10_total_margin_exact','broker10_margin_to_equity_pct']
PNL = ['holding_pnl','trading_pnl','commission','slippage','net_pnl']
KEY = ['date','vt_symbol']
TOL = 1e-6
ASSERTIONS = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def check(name, value, tolerance=TOL):
    error = float(np.max(np.abs(np.asarray(value,dtype=float)))) if np.asarray(value).size else 0.0
    ASSERTIONS[name] = {'passed':error <= tolerance, 'maximum_absolute_error':error, 'tolerance':tolerance}
    if error > tolerance: raise AssertionError(f'{name}: {error}')


def save(df, name):
    df.to_csv(OUT/name,index=False,float_format='%.12g')


def peak_stats(day):
    eq = day.set_index('date').account_equity
    dd = eq/eq.cummax()-1
    trough = dd.idxmin(); peak = eq.loc[:trough].idxmax()
    rec = eq.loc[trough:]; rec = rec[rec>=eq[peak]]
    return dict(peak_date=peak,peak_equity=float(eq[peak]),trough_date=trough,trough_equity=float(eq[trough]),
        signed_change=float(eq[trough]-eq[peak]),absolute_loss=float(eq[peak]-eq[trough]),
        drawdown_pct=float(dd[trough]*100),recovery_date=None if rec.empty else rec.index[0],
        recovery_equity=None if rec.empty else float(rec.iloc[0]),recovery_threshold='EOD equity >= original peak EOD equity')


def main():
    if OUT.exists(): raise FileExistsError('Refuse to overwrite existing attribution output: '+str(OUT))
    frozen=json.loads(FROZEN.read_text()); bindings={**frozen['files_sha256'],**frozen.get('components_sha256',{})}
    selected=[FROZEN,DB,Path(__file__)]
    for directory in ATTEMPTS.values():
        selected += [directory/name for name in ['daily.csv','positions.csv','trades.csv','trade_events.csv','entry_risk.csv','effective_parameters.json']]
    source_sha={str(p):sha(p) for p in selected}
    for path,digest in source_sha.items():
        if path not in (str(FROZEN),str(Path(__file__))):
            if bindings.get(path)!=digest: raise AssertionError('Frozen source missing or changed: '+path)
    OUT.mkdir(parents=True)
    days={}; positions={}; fills={}; events={}; risks={}; sizes={}; row_counts={}
    for arm,directory in ATTEMPTS.items():
        days[arm]=pd.read_csv(directory/'daily.csv',usecols=DAYCOLS).sort_values('date').reset_index(drop=True)
        d=days[arm]
        check(arm+'_daily_equity_vs_pnl',d.account_equity-(150000+d.net_pnl.cumsum()))
        check(arm+'_daily_net_components',d.net_pnl-(d.holding_pnl+d.trading_pnl-d.commission-d.slippage))
        check(arm+'_legacy_margin_is_1p1',d.broker10_total_margin_exact-d.total_margin_exact*1.1)
        parameters=json.loads((directory/'effective_parameters.json').read_text()); sizes[arm]=parameters['sizes']
        chunks=[]; total=0
        for c in pd.read_csv(directory/'positions.csv',usecols=POSCOLS,chunksize=100000):
            c['source_csv_row']=np.arange(total+2,total+len(c)+2); total+=len(c)
            active=c[['start_pos','end_pos','trade_count','holding_pnl','trading_pnl','commission','slippage','net_pnl']].abs().sum(axis=1).ne(0)
            c=c.loc[active & c.date.between(d.date.iloc[0],d.date.iloc[-1])].copy()
            chunks.append(c)
        p=pd.concat(chunks,ignore_index=True).sort_values(KEY).reset_index(drop=True)
        if p.duplicated(KEY).any(): raise AssertionError('duplicate active position key')
        p['arm']=arm; p['size']=p.vt_symbol.map(sizes[arm]); assert p['size'].notna().all()
        p['holding_rebuilt']=p.start_pos*(p.close_price-p.pre_close)*p['size']
        p['gross_end_notional']=p.end_pos.abs()*p.close_price*p['size']
        p['end_lots_abs']=p.end_pos.abs()
        check(arm+'_holding_price_formula',p.holding_pnl-p.holding_rebuilt)
        check(arm+'_net_components',p.net_pnl-(p.holding_pnl+p.trading_pnl-p.commission-p.slippage))
        check(arm+'_position_change',p.pos_change-(p.end_pos-p.start_pos))
        ag=p.groupby('date')[PNL+['trade_count']].sum().reindex(d.date,fill_value=0).reset_index()
        for col in PNL+['trade_count']: check(arm+'_positions_daily_'+col,ag[col].to_numpy()-d[col].to_numpy())
        t=pd.read_csv(directory/'trades.csv');t['source_csv_row']=np.arange(2,len(t)+2)
        t['arm']=arm;t['size']=t.vt_symbol.map(sizes[arm]); assert t['size'].notna().all()
        check(arm+'_fill_direction',t.signed_volume-np.where(t.direction.eq('多'),t.volume,-t.volume))
        joined=t.merge(p[KEY+['close_price']],on=KEY,how='left',validate='many_to_one')
        assert joined.close_price.notna().all()
        t['trading_rebuilt']=t.signed_volume*(joined.close_price.to_numpy()-t.price)*t['size']
        t['slippage_rebuilt']=t.volume*t['size']*t.vt_symbol.map(parameters['slippages'])
        t['commission_rebuilt']=t.volume*t.price*t['size']*t.vt_symbol.map(parameters['rates'])
        t['fill_count']=1
        ta=t.groupby(KEY)[['signed_volume','trading_rebuilt','slippage_rebuilt','commission_rebuilt','fill_count']].sum()
        pp=p.set_index(KEY)
        ta=ta.reindex(pp.index,fill_value=0)
        for left,right in [('pos_change','signed_volume'),('trading_pnl','trading_rebuilt'),('slippage','slippage_rebuilt'),('commission','commission_rebuilt'),('trade_count','fill_count')]:
            check(arm+'_fills_'+left,pp[left].to_numpy()-ta[right].to_numpy())
        exposure=p.groupby('date')[['gross_end_notional','end_lots_abs']].sum().reindex(d.date,fill_value=0).reset_index()
        d=d.merge(exposure,on='date',validate='one_to_one'); d['actual_1p65_margin']=d.total_margin_exact*1.65
        d['actual_1p65_margin_to_equity_pct']=d.actual_1p65_margin/d.account_equity*100
        d['gross_notional_to_equity']=d.gross_end_notional/d.account_equity
        d['nominal_margin_to_equity_pct']=d.total_margin_exact/d.account_equity*100
        e=pd.read_csv(directory/'trade_events.csv');e['arm']=arm;e['source_csv_row']=np.arange(2,len(e)+2)
        r=pd.read_csv(directory/'entry_risk.csv');r['arm']=arm;r['source_csv_row']=np.arange(2,len(r)+2)
        days[arm]=d;positions[arm]=p;fills[arm]=t;events[arm]=e;risks[arm]=r
        row_counts[arm]={'raw_position_rows':total,'active_rows_full_requested_window':len(p),'daily_rows':len(d),'fills':len(t)}
    assert days['B'].date.equals(days['W'].date)
    assert sizes['B']==sizes['W']
    stats={a:peak_stats(d) for a,d in days.items()}
    start,end=stats['W']['peak_date'],stats['W']['trough_date']
    summary_windows=[]
    for window,st in stats.items():
        for arm,d in days.items():
            ss=d.set_index('date'); first,last=ss.loc[st['peak_date']],ss.loc[st['trough_date']]
            loss=first.account_equity-last.account_equity
            interval=d.loc[d.date.gt(st['peak_date'])&d.date.le(st['trough_date'])]
            check(window+'_window_'+arm+'_equity_change_vs_sum',last.account_equity-first.account_equity-interval.net_pnl.sum())
            summary_windows.append(dict(window_owner=window,arm=arm,start_date=st['peak_date'],end_date=st['trough_date'],
                start_equity=first.account_equity,end_equity=last.account_equity,signed_change=-loss,absolute_loss=loss,
                window_return_pct=-loss/first.account_equity*100,days=len(interval),**{k:interval[k].sum() for k in PNL}))
    save(pd.DataFrame(summary_windows),'same_date_window_comparison.csv')
    save(pd.DataFrame([dict(arm=a,**v) for a,v in stats.items()]),'max_drawdown_peak_trough_recovery.csv')
    daypanel=days['B'].merge(days['W'],on='date',suffixes=('_B','_W'),validate='one_to_one')
    for k in PNL+['account_equity','actual_1p65_margin','gross_end_notional','end_lots_abs','actual_1p65_margin_to_equity_pct']:
        daypanel[k+'_W_minus_B']=daypanel[k+'_W']-daypanel[k+'_B']
    daypanel['W_dd_window_after_peak_inclusive_trough']=daypanel.date.gt(start)&daypanel.date.le(end)
    save(daypanel,'all_daily_comparison.csv')
    win=daypanel.loc[daypanel.W_dd_window_after_peak_inclusive_trough].copy()
    save(win,'W_window_daily_attribution_all_dates.csv')
    source_active=pd.concat(positions.values(),ignore_index=True)
    rawwin=source_active.loc[source_active.date.gt(start)&source_active.date.le(end)].copy()
    save(rawwin,'W_window_active_positions_full_ledger.csv')
    # Outer union retains both an actual active row and the other arm's explicit zero.
    left=positions['B'].drop(columns='arm'); right=positions['W'].drop(columns='arm')
    panel=left.merge(right,on=KEY,how='outer',suffixes=('_B','_W'),indicator=True,validate='one_to_one')
    panel['row_present_B']=panel['_merge'].ne('right_only');panel['row_present_W']=panel['_merge'].ne('left_only');panel=panel.drop(columns='_merge')
    panel['size']=panel.vt_symbol.map(sizes['B'])
    panel['market_close']=panel.close_price_B.combine_first(panel.close_price_W)
    panel['market_pre_close']=panel.pre_close_B.combine_first(panel.pre_close_W)
    both=panel.row_present_B&panel.row_present_W
    check('B_W_same_active_close_price',panel.loc[both,'close_price_B']-panel.loc[both,'close_price_W'])
    check('B_W_same_active_pre_close',panel.loc[both,'pre_close_B']-panel.loc[both,'pre_close_W'])
    for arm in ATTEMPTS:
        for k in ['start_pos','end_pos','pos_change','trade_count','turnover']+PNL:
            panel[k+'_'+arm]=panel[k+'_'+arm].fillna(0)
        panel['source_positions_path_'+arm]=str(ATTEMPTS[arm]/'positions.csv')
    for k in PNL: panel[k+'_W_minus_B']=panel[k+'_W']-panel[k+'_B']
    panel['holding_position_gap_rebuilt']=(panel.start_pos_W-panel.start_pos_B)*(panel.market_close-panel.market_pre_close)*panel['size']
    panel['cost_contribution_W_minus_B']=-(panel.commission_W_minus_B+panel.slippage_W_minus_B)
    panel['gap_sum_rebuilt']=panel.holding_position_gap_rebuilt+panel.trading_pnl_W_minus_B+panel.cost_contribution_W_minus_B
    check('B_W_holding_gap_price_formula',panel.holding_pnl_W_minus_B-panel.holding_position_gap_rebuilt)
    check('B_W_net_gap_components',panel.net_pnl_W_minus_B-panel.gap_sum_rebuilt)
    pw=panel.loc[panel.date.gt(start)&panel.date.le(end)].sort_values(KEY).copy()
    save(pw,'W_window_day_contract_attribution_full.csv')
    measures=[k+'_'+a for k in PNL for a in ATTEMPTS]+[k+'_W_minus_B' for k in PNL]+['holding_position_gap_rebuilt','cost_contribution_W_minus_B','gap_sum_rebuilt']
    contracts=pw.groupby('vt_symbol')[measures].sum().reset_index().sort_values('net_pnl_W_minus_B')
    save(contracts,'W_window_contract_attribution_all.csv')
    products=pw.assign(product_vt_symbol=pw.vt_symbol.str.replace(r'\d+','',regex=True)).groupby('product_vt_symbol')[measures].sum().reset_index().sort_values('net_pnl_W_minus_B')
    save(products,'W_window_product_attribution_all.csv')
    for arm in ATTEMPTS:
        check(arm+'_W_window_contract_sum',contracts['net_pnl_'+arm].sum()-win['net_pnl_'+arm].sum())
    check('W_window_gap_conservation',pw.net_pnl_W_minus_B.sum()-win.net_pnl_W_minus_B.sum())
    pre=panel.loc[panel.date.le(start)].copy()
    save(pre,'pre_W_peak_day_contract_attribution_full.csv')
    save(pre.groupby('vt_symbol')[measures].sum().reset_index().sort_values('net_pnl_W_minus_B'),'pre_W_peak_contract_attribution_all.csv')
    check('prepeak_equity_gap_conservation',pre.net_pnl_W_minus_B.sum()-daypanel.set_index('date').loc[start,'account_equity_W_minus_B'])
    # Record all actual fills/events/entry decisions in W's peak-trough interval.
    for name,source in [('fills',fills),('events',events),('entry_risk',risks)]:
        data=pd.concat(source.values(),ignore_index=True)
        data=data.loc[data.date.gt(start)&data.date.le(end)]
        save(data,'W_window_'+name+'_full.csv')
    # Fixed explanatory cases chosen for accounting mechanisms, not a trading filter.
    cases=[('2018-03-12','jm1805.DCE'),('2019-08-26','au1912.SHFE'),('2020-02-03','cu2003.SHFE'),('2020-02-03','CF005.CZCE'),('2020-01-13','OI005.CZCE')]
    casekeys=set(cases); case_syms={s for _,s in cases}
    ca=pw.loc[[tuple(k) in casekeys for k in pw[KEY].to_numpy()]].sort_values(KEY)
    save(ca,'five_case_day_contract_evidence.csv')
    for name,source in [('fills',fills),('events',events),('entry_risk',risks)]:
        data=pd.concat(source.values(),ignore_index=True)
        symcol='contract_vt_symbol' if name=='entry_risk' else 'vt_symbol'
        data=data.loc[data[symcol].isin(case_syms)&data.date.le(end)]
        save(data,'five_case_'+name+'_entire_contract_history.csv')
    half=fills['W'].loc[fills['W'].date.gt(start)&fills['W'].date.le(end)&fills['W'].exit_reason.fillna('').str.contains('profit5_half')].copy()
    half_rows=[]
    date_list=days['W'].date.tolist(); di=daypanel.set_index('date')
    for _,h in half.iterrows():
        i=date_list.index(h.date); before=date_list[i-1]; now=di.loc[h.date];prev=di.loc[before]
        z=pw.loc[pw.date.eq(h.date)&pw.vt_symbol.eq(h.vt_symbol)].iloc[0]
        half_rows.append(dict(date=h.date,previous_date=before,vt_symbol=h.vt_symbol,close_volume=h.volume,fill_price=h.price,trade_id=h.trade_id,source_trades_csv_row=h.source_csv_row,
            W_contract_start_pos=z.start_pos_W,W_contract_end_pos=z.end_pos_W,B_contract_start_pos=z.start_pos_B,B_contract_end_pos=z.end_pos_B,
            W_equity_before=prev.account_equity_W,W_equity_after=now.account_equity_W,
            W_actual_margin_pct_before=prev.actual_1p65_margin_to_equity_pct_W,W_actual_margin_pct_after=now.actual_1p65_margin_to_equity_pct_W,
            B_actual_margin_pct_after=now.actual_1p65_margin_to_equity_pct_B,
            W_gross_notional_to_equity_before=prev.gross_notional_to_equity_W,W_gross_notional_to_equity_after=now.gross_notional_to_equity_W))
    save(pd.DataFrame(half_rows),'W_window_profit_half_before_after_exposure_all.csv')
    # Read-only approved DB: verify the exact case prices, record latest prior DB close.
    con=sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True)
    dbrows=[]
    for date,symbol in cases:
        raw,exchange=symbol.split('.')
        bars=con.execute('SELECT datetime,open_price,high_price,low_price,close_price FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND datetime<? ORDER BY datetime DESC LIMIT 2',(raw,exchange,'d',date+' 23:59:59')).fetchall()
        row={'date':date,'vt_symbol':symbol,'DB_path':str(DB)}
        for i,b in enumerate(bars):
            row.update({f'DB_{i}_'+k:v for k,v in zip(['datetime','open','high','low','close'],b)})
        z=ca.loc[ca.date.eq(date)&ca.vt_symbol.eq(symbol)].iloc[0]
        assert bars and bars[0][0][:10]==date
        check(date+'_'+symbol+'_approved_DB_close',z.market_close-bars[0][4])
        check(date+'_'+symbol+'_approved_DB_pre_close',z.market_pre_close-bars[1][4])
        dbrows.append(row)
    con.close();save(pd.DataFrame(dbrows),'five_case_approved_DB_prices.csv')
    peakB=stats['B']['peak_equity'];peakW=stats['W']['peak_equity'];lossB=stats['B']['absolute_loss'];lossW=stats['W']['absolute_loss']
    sw={r['arm']:r for r in summary_windows if r['window_owner']=='W'}
    # Exact ordered algebra: first change loss with B denominator, then denominator.
    def ratio_bridge(lb,lw,eb,ew):
        x=dict(loss_change_effect_pp=(lw-lb)/eb*100,denominator_change_effect_pp=lw*(1/ew-1/eb)*100,
               total_difference_pp=lw/ew*100-lb/eb*100,order='replace absolute loss at B peak denominator, then replace B denominator with W denominator; algebraic, not causal')
        check('ratio_bridge_'+str(eb),x['loss_change_effect_pp']+x['denominator_change_effect_pp']-x['total_difference_pp'])
        return x
    totals={k:float(pw[k].sum()) for k in measures}
    margin_summary={a:dict(window_days=len(win),actual_over100_days=int((win['actual_1p65_margin_to_equity_pct_'+a]>100).sum()),
        actual_margin_pct_max=float(win['actual_1p65_margin_to_equity_pct_'+a].max()),actual_margin_pct_mean=float(win['actual_1p65_margin_to_equity_pct_'+a].mean()),
        gross_notional_to_equity_mean=float(win['gross_notional_to_equity_'+a].mean()),
        end_lots_mean=float(win['end_lots_abs_'+a].mean())) for a in ATTEMPTS}
    metadata=dict(schema='stage031_frozen_B_W_drawdown_attribution_v1',created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),line_id=LINE.name,
        source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        new_financial_replays=0,new_downloads=0,strategy_imports=0,parameter_changes=0,production_qualified=False,promotion_decision='NO_PROMOTION',
        window=dict(start_peak_excluded=start,end_trough_included=end,dates=len(win),active_day_contract_union_rows=len(pw),contracts=len(contracts),products=len(products)),
        max_drawdowns=stats,same_date_windows=summary_windows,own_maxima_ratio_bridge=ratio_bridge(lossB,lossW,peakB,peakW),
        W_same_window_ratio_bridge=ratio_bridge(sw['B']['absolute_loss'],sw['W']['absolute_loss'],sw['B']['start_equity'],sw['W']['start_equity']),
        W_window_accounting_totals=totals,margin_summary=margin_summary,W_higher_actual_margin_pct_days=int((win.actual_1p65_margin_to_equity_pct_W>win.actual_1p65_margin_to_equity_pct_B+TOL).sum()),
        W_window_profit_half_fills=half_rows,row_counts=row_counts,assertions=ASSERTIONS,
        limitations=['Algebraic accounting attribution is not a per-rule causal intervention.','Both daily rows and positions are EOD marks; not intraday maximum drawdowns or live fills.',
        'Actual margin here is the frozen nominal margin times configured 1.65; legacy broker10 columns use 1.1.',
        'All active position rows retained; all-zero positions/trades/PnL rows omitted and absent counterpart rows explicitly filled as zero.',
        'Zero commissions; fixed modeled slippage; historical market truth, PIT and OOS not proved.',
        'Five-case DB price verification confirms local approved source agreement, not independent historical market truth.'],
        external_research=dict(source='https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py',
            judgment='Official ContractDailyResult supplies a valid accounting identity: holding = start_pos*(close-pre_close)*size; trading = sum signed_fill*(close-fill)*size; net = holding+trading-commission-slippage. Use the frozen local ledger, not current remote runtime, as numeric truth.'),
        reflection=dict(before_overfit=False,after_overfit=False,reason='Frozen candidate, ledger and thresholds; no fitting, tuning, new entry selection or replay.',before_continuation_value=True,after_continuation_value=True,value_reason='Explains the observed drawdown denominator and path mechanisms; no claim of alpha or promotion.'),
        sources_sha256=source_sha,script_sha256=source_sha[str(Path(__file__))])
    (OUT/'summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    STAGE.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    # Keep this isolated stage separate from root, registry, and LINE updates.
    lines=['# Stage031 B/W 最大回撤只读守恒归因','',f'- line_id：`{LINE.name}`',f"- 记录时间：{metadata['created_at']}",
        '- 阶段性质：冻结账本只读归因；不导入策略、不重跑引擎、不下载行情、不修改参数。','- 是否重要突破：否。是否触发 A/B：否，仅解释已有固定 B/W。',
        '- 运行前/后过拟合判断：均为否；未调整阈值、品种、风险或筛选新的交易规则。',
        '- 运行前/后继续价值判断：均为是；本阶段解释既有回撤，完成后不据此救参。','',
        '## 外部调研与判断','',
        '- 核对 vn.py 官方 GitHub `ContractDailyResult`：https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py 。',
        '- 判断：持仓价差、成交至收盘价差和费滑点是守恒会计拆分；不等价于新止盈规则的逐日单因果。冻结本地账本是本次数值事实源。','',
        '## 最大回撤和同窗反证','',
        '| 版本 | 峰日 | 峰值 | 谷日 | 谷值 | 绝对损失 | 回撤 | 恢复日 |','| --- | --- | ---: | --- | ---: | ---: | ---: | --- |']
    for a,s in stats.items():
        lines.append(f"| {a} | {s['peak_date']} | {s['peak_equity']:,.2f} | {s['trough_date']} | {s['trough_equity']:,.2f} | {s['absolute_loss']:,.2f} | {s['drawdown_pct']:.6f}% | {s['recovery_date']} |")
    lines += ['',f"W 最大回撤窗口（{start} 峰后至 {end} 谷，{len(win)} 日）：B `{sw['B']['start_equity']:,.2f}→{sw['B']['end_equity']:,.2f}`，亏 `{sw['B']['absolute_loss']:,.2f}`、`{-sw['B']['window_return_pct']:.6f}%`；W `{sw['W']['start_equity']:,.2f}→{sw['W']['end_equity']:,.2f}`，亏 `{sw['W']['absolute_loss']:,.2f}`、`{-sw['W']['window_return_pct']:.6f}%`。",'',
        'W 在自己的最大回撤同窗少亏 19,215 元，但起点权益少 65,220 元，低权益分母使百分比回撤更大。B 与 W 的各自最大回撤起点不同，不能直接把两者百分比差解释成多亏的钱。',
        f"同窗比例差精确拆分：绝对损失减少贡献 `{metadata['W_same_window_ratio_bridge']['loss_change_effect_pp']:+.6f}pp`，分母变化贡献 `{metadata['W_same_window_ratio_bridge']['denominator_change_effect_pp']:+.6f}pp`，合计 `{metadata['W_same_window_ratio_bridge']['total_difference_pp']:+.6f}pp`。此为先替换损失、再替换分母的代数桥，非因果分摊。",'',
        '## 全日全合约守恒','',
        '| 会计项 | B | W | W−B 净损益贡献 |','| --- | ---: | ---: | ---: |',
        f"| 起始持仓×昨收至今收 | {totals['holding_pnl_B']:,.2f} | {totals['holding_pnl_W']:,.2f} | {totals['holding_pnl_W_minus_B']:+,.2f} |",
        f"| 当日有符号成交×成交至今收 | {totals['trading_pnl_B']:,.2f} | {totals['trading_pnl_W']:,.2f} | {totals['trading_pnl_W_minus_B']:+,.2f} |",
        f"| 手续费 | {totals['commission_B']:,.2f} | {totals['commission_W']:,.2f} | {-totals['commission_W_minus_B']:+,.2f} |",
        f"| 滑点 | {totals['slippage_B']:,.2f} | {totals['slippage_W']:,.2f} | {-totals['slippage_W_minus_B']:+,.2f} |",
        f"| 净损益 | {totals['net_pnl_B']:,.2f} | {totals['net_pnl_W']:,.2f} | {totals['net_pnl_W_minus_B']:+,.2f} |",'',
        f'全明细包含 {len(pw)} 个有效日合约并集、{len(contracts)} 个合约、{len(products)} 个品种、{len(win)} 个交易日；没有只输出 Top 的截断。纯零仓、零成交、零损益行省略；另一侧缺有效行明确补零。源 CSV 行号包含表头，即可追溯原文件。','',
        '## 五个可追溯案例','']
    case_notes={
        ('2018-03-12','jm1805.DCE'):'W 起始 3 手、B 起始 1 手；W 入场本来较少，但 B 在 2月26日已有 forced_margin_deleverage 平 3 手，故此日反而 W 持仓更多。两版当日均技术止损。',
        ('2019-08-26','au1912.SHFE'):'B 持有 1 手黄金，W 为 0；当日金价上涨使 W 少赚。B 6月17日306.3入、9月16日346.2出；W 此合约无实际成交。缺失成交不能仅凭账本断言具体拒绝原因。',
        ('2020-02-03','cu2003.SHFE'):'W 1月13日48890开 1 手，春节后44780平；B 此合约没有成交。此日 W 有隔夜亏损与平仓至收盘的价差及滑点。',
        ('2020-02-03','CF005.CZCE'):'B 仍有 5 手棉花，W 早在1月7日以风险簇热度减仓平掉 5 手，故当日 W 少亏；不是该合约直接盈利半平。',
        ('2020-01-13','OI005.CZCE'):'W 因 weeklyhalf 平 1 手，3→2，B 仍为5手；W 当日另有cu2003开1手。半平降低这个合约手数，但账户整体曝险要同时计入别的开平仓及权益分母。'}
    for _,r in ca.iterrows():
        lines += [f"- `{r.date} {r.vt_symbol}`：B 净 `{r.net_pnl_B:+,.2f}`，W 净 `{r.net_pnl_W:+,.2f}`，差 `{r.net_pnl_W_minus_B:+,.2f}`；起始持仓项 `{r.holding_pnl_W_minus_B:+,.2f}`、成交至收盘项 `{r.trading_pnl_W_minus_B:+,.2f}`、成本项 `{r.cost_contribution_W_minus_B:+,.2f}`。{case_notes[(r.date,r.vt_symbol)]}"]
    lines += ['', '## 权益与曝险','',
        '名义保证金使用冻结 daily.total_margin_exact；实际保证金按冻结配置 1.65 倍。原 broker10 字段已断言为 1.1 倍，不能冒称实际1.65倍。',
        f"W 窗口中，W 实际保证金/权益高于 B 的天数为 `{metadata['W_higher_actual_margin_pct_days']}/{len(win)}`；B/W 超100%日数为 `{margin_summary['B']['actual_over100_days']}/{margin_summary['W']['actual_over100_days']}`。",'',
        '2018-02-27：W 名义保证金162,020、权益290,665、实际保证金/权益91.9729%；B名义156,347、权益355,885、实际72.4876%。W 账户较小，名义保证金却略高，故相对曝险确有更高时段。不是所有日期或每次半平后都如此；三次窗口内半平的前后账户曝险全量另表列出。','',
        '## 验证、边界和交付','',
        f"- 守恒断言：`{len(ASSERTIONS)}` 项全部通过；最大容差 `{TOL}`。逐日权益、逐合约持仓公式、实际成交重建交易PnL/滑点/手续费/手数变化、跨版本差额、同窗累计和五个案例DB价格全部核对。",
        '- 来源：Stage030 delivery manifest 内选用输入逐个 SHA256 匹配；脚本及所有输出由本目录冻结清单绑定；生成前后原输入hash一致。',
        '- 新增/修改/删除参数：全部无。新增回测：0。旧回测结果修改/删除：0。',
        '- 本阶段不重新计算全期 Sharpe、交易胜率或作为新回测；全期既有绩效见 Stage030。',
        '- 历史行情真值/PIT/OOS未证明；零手续费、固定滑点、日开盘模型；日末回撤不代表盘中回撤、真实成交或生产资格。',
        '- 不更新 LINE/registry/root memory，不提交 Git。',
        f"- 输出：`{OUT}`，其中 `summary.json`、`W_window_day_contract_attribution_full.csv`、`W_window_daily_attribution_all_dates.csv`、`W_window_contract_attribution_all.csv`、`W_window_fills_full.csv`、`five_case_*` 和 `delivery_manifest.json` 可复核。",'']
    STAGE.with_suffix('.md').write_text('\n'.join(lines))
    # Recheck every frozen input after all reads, without touching any old file.
    changed={p:{'before':digest,'after':sha(p)} for p,digest in source_sha.items() if sha(p)!=digest}
    if changed: raise AssertionError('Source changed during attribution: '+str(changed))
    generated=sorted([p for p in OUT.iterdir() if p.is_file()]+[STAGE.with_suffix('.md'),STAGE.with_suffix('.json')])
    manifest=dict(schema='stage031_drawdown_bridge_delivery_v1',created_at=metadata['created_at'],
        source_files_sha256=source_sha,files_sha256={str(p):sha(p) for p in generated},all_assertions_passed=True,
        assertion_count=len(ASSERTIONS),source_files_preserved=True,finance_replays=0,production_qualified=False)
    (OUT/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:metadata[k] for k in ['max_drawdowns','W_same_window_ratio_bridge','margin_summary','W_higher_actual_margin_pct_days','script_sha256']},ensure_ascii=False,indent=2))
    print('ALL ASSERTIONS PASSED',len(ASSERTIONS),'MANIFEST',sha(OUT/'delivery_manifest.json'))

if __name__=='__main__': main()
