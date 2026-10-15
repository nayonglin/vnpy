"""只读整合Stage246真实结果和Stage247独立归因，不运行引擎或改变策略。"""
from pathlib import Path
import argparse
import hashlib
import json
import re

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--stage',type=Path,required=True)
    a=ap.parse_args()
    import pandas as pd
    import numpy as np
    src,out=a.source.resolve(),a.output.resolve()
    names=['trades.csv','daily.csv','entry_candidates.csv','execution_proxy_usage.csv','stop_retry_events.csv','trade_outcomes_complete_cycles.csv','effective_parameters.json']
    fingerprints={n:hashlib.sha256((src/n).read_bytes()).hexdigest() for n in names}
    trades=pd.read_csv(src/'trades.csv').fillna('')
    usage=pd.read_csv(src/'execution_proxy_usage.csv').fillna('')
    candidates=pd.read_csv(src/'entry_candidates.csv').fillna('')
    daily=pd.read_csv(src/'daily.csv').set_index('date')
    stops=pd.read_csv(src/'stop_retry_events.csv').fillna('')
    minute_evidence=pd.read_csv(out/'execution_review/synthetic_fill_tick_grid_audit.csv').fillna('')
    minute_by_trade={k:g.to_dict('records') for k,g in minute_evidence.groupby('trade_id')}
    cycles=pd.read_csv(out/'ai_review/cycles_with_original_ai.csv').fillna('')
    source_cycles=pd.read_csv(src/'trade_outcomes_complete_cycles.csv')
    selected=source_cycles[source_cycles.first_datetime.str[:10].ge('2025-09-01')]
    assert set(cycles.first_trade_id)==set(selected.first_trade_id)
    assert len(cycles)==57 and np.isclose(cycles.net_pnl.sum(),selected.net_pnl.sum())
    idx=lambda x: int(str(x).split('.')[-1])
    cycles['sequence']=cycles.first_trade_id.map(idx)
    cycles=cycles.sort_values('sequence').reset_index(drop=True)
    tmap=trades.set_index('trade_id').to_dict('index')
    umap=usage.set_index('trade_id').to_dict('index')
    cmap=candidates.set_index('candidate_index').to_dict('index')
    smap=stops.set_index('trade_id').to_dict('index')
    first_ids=list(dict.fromkeys(cycles.original_trade_id))
    epmap={tid:f'S{i+1:02d}' for i,tid in enumerate(first_ids)}
    labels={
      'stage847_intraday_05r_initial_stop':'C9首次0.5R止损',
      'stage847_intraday_retry_failed_05r_stop':'C9重试后再次0.5R止损',
      'stage847_intraday_reentry_at_original_entry':'C9同日按原价重试',
      'raw_night_2100_2105_first_open':'原始分钟夜盘21:00开盘代理',
      'raw_day_0900_0905_first_open':'原始分钟日盘09:00开盘代理',
      'fallback_daily_next_open':'正式日线开盘价后备',
      'long_prev2day_stop':'多头前两日低点退出',
      'short_prev2day_stop':'空头前两日高点退出',
      'long_base_stop':'多头初始止损退出',
      'short_base_stop':'空头初始止损退出',
      'long_risk_cluster_heat_deleverage':'多头品种风险容量去杠杆',
      'short_risk_cluster_heat_deleverage':'空头品种风险容量去杠杆',
      'rollover_close':'主力换月平仓',
    }
    def fmt(x):
        return f'{float(x):,.2f}'
    def moment(x):
        return str(x).replace('T',' ').replace('+08:00','')
    records=[]
    for i,r in cycles.iterrows():
        first,last,original=r.first_trade_id,r.last_trade_id,r.original_trade_id
        et,xt,eu,xu=tmap[first],tmap[last],umap[first],umap[last]
        candidate=cmap[int(r.candidate_index)]
        assert candidate['candidate_status']=='opened'
        assert candidate['contract_vt_symbol']==r.vt_symbol
        assert str(candidate['date'])==str(eu['signal_date'])
        row=r.to_dict(); row['review_id']=f'T{i+1:02d}';row['episode_id']=epmap[original]
        row['position_direction']=r.direction_x
        row['exit_price']=xt['price'];row['entry_price']=et['price']
        row['entry_price_source']=eu['price_source'];row['exit_price_source']=xu['price_source']
        row['exit_reason']=xu['price_source'] if str(xu['price_source']).startswith('stage') else xt['exit_reason']
        row['exit_reason_zh']=labels.get(row['exit_reason'],row['exit_reason'] or '来源记录未注明')
        row['signal_account_equity']=float(daily.loc[str(candidate['date']),'account_equity'])
        row['signal_sizing_equity']=float(candidate['sizing_equity'])
        row['sizing_equity_excess']=row['signal_sizing_equity']-row['signal_account_equity']
        row['sizing_equity_ratio']=row['signal_sizing_equity']/row['signal_account_equity']
        row['signal_rsi']=candidate['rsi_value']
        row['oi_restore_applied']=candidate['oi_price_confirm_risk_restore_applied']
        row['risk_multiplier']=candidate['risk_multiplier']
        row['signal_stop_distance']=candidate['stop_distance']
        row['entry_proxy_time']=eu['proxy_first_time']
        row['exit_proxy_time']=xu['proxy_first_time']
        event=smap.get(original,{})
        for key in ['first_stop_time','reentry_time','retry_failed_time','risk_price','progress_price']:
            row['c9_'+key]=event.get(key,'')
        row['c9_stop_price']=event.get('stop_price','')
        row['night_event']=any(str(event.get(k,''))[11:16]>='21:00' for k in ['first_stop_time','reentry_time','retry_failed_time'] if event.get(k))
        row['price_result']='盈利' if row['net_pnl']>1e-7 else ('亏损' if row['net_pnl']<-1e-7 else '持平')
        minute_flags=[]
        for mid in [first,last]:
            for evidence in minute_by_trade.get(mid,[]):
                if evidence['fill_outside_bar_range']:
                    minute_flags.append(f"{mid}于{evidence['bar_datetime']}记录成交{fmt(evidence['synthetic_fill_price'])}，超出该分钟低{fmt(evidence['low'])}—高{fmt(evidence['high'])}；成交模型未证明这个止损价可执行，且偏差对策略有利。")
                if evidence['off_tick']:
                    minute_flags.append(f"{mid}记录成交价{fmt(evidence['synthetic_fill_price'])}不符合该合约最小跳价{evidence['pricetick']:g}的整数倍；本报告保留原价复算，不把它当作合法成交报价。")
                if evidence['first_bar_both_adverse_progress']:
                    minute_flags.append(f"{mid}触发分钟同时触及止损与进展阈值；OHLC不能识别先后，正式实现采用了其中一种顺序。")
                if evidence['retry_bar_also_touches_stop']:
                    minute_flags.append(f"{mid}重试所在分钟也触及止损价，正式实现从下一根才检查；该分钟内先后存在歧义。")
        row['minute_evidence_flags']=' '.join(minute_flags)
        records.append(row)
    ledger=pd.DataFrame(records)
    ledger.to_csv(out/'trade_by_trade_ledger.csv',index=False,encoding='utf-8-sig')
    fields={'review_id':'复盘编号','episode_id':'原始信号编号','first_trade_id':'开仓成交ID','last_trade_id':'平仓成交ID','vt_symbol':'合约','position_direction':'方向','first_datetime':'开仓记录时间','last_datetime':'平仓记录时间','opened_volume':'手数','entry_price':'开仓价','exit_price':'平仓价','gross_pnl':'毛盈亏元','slippage':'滑点元','net_pnl':'净盈亏元','signal_date':'信号日','ai_product_pool_signal_date':'AI池评估日','ai_product_pool_rank':'AI池名次','is_retry':'是否重试','exit_reason_zh':'退出原因','signal_account_equity':'信号日净账权益元','signal_sizing_equity':'定仓内部权益元','sizing_equity_excess':'内部权益多计元','minute_evidence_flags':'分钟执行核验'}
    ledger[list(fields)].rename(columns=fields).to_csv(out/'逐笔复盘明细.csv',index=False,encoding='utf-8-sig')
    ids=set(ledger.first_trade_id)|set(ledger.last_trade_id)
    fills=trades[trades.trade_id.isin(ids)].copy()
    fills['engine_sequence']=fills.trade_id.map(idx)
    fills.sort_values('engine_sequence').merge(usage,on='trade_id',suffixes=('_trade','_usage'),validate='one_to_one').to_csv(out/'all_114_fills.csv',index=False,encoding='utf-8-sig')
    assert len(fills)==114 and ledger.open_trade_count.eq(1).all() and ledger.close_trade_count.eq(1).all()
    independent=pd.read_csv(out/'stats_review/independent_complete_cycles.csv').set_index('first_trade_id')
    for r in ledger.itertuples():
        assert np.isclose(r.net_pnl,independent.loc[r.first_trade_id,'net_pnl'],rtol=0,atol=1e-6)
    header=['## 全部57个持仓周期逐笔复盘','',
      '按开仓成交ID排列。T为完整持仓周期，S为原始入场信号；同一S下的第二个T是重试，不是新AI选品。全部57周期均为一开一平，因此覆盖114笔成交。这里的“00:00”为正式引擎记录日期标签，实际价格来源另列，不能解释为零点实盘成交。',
      '', '共同限制：定仓内部权益存在前文已核验的累计偏差；C9分钟按自然日扫描，不是严格事件时间引擎。表内损益是固定已发生回测成交的归因，不能直接解释为修复后的策略收益。','',
      '|编号/信号|合约/方向|开仓→平仓日期|手数|净盈亏（元）|退出依据|', '|---|---|---|---:|---:|---|']
    for r in ledger.itertuples():
        direction='多' if r.position_direction=='long' else '空'
        leg='重试' if bool(r.is_retry) else '首开'
        header.append(f'|{r.review_id}/{r.episode_id} {leg}|{r.vt_symbol} {direction}|{r.first_datetime[:10]}→{r.last_datetime[:10]}|{r.opened_volume:g}|{r.net_pnl:,.2f}|{r.exit_reason_zh}|')
    for r in ledger.to_dict('records'):
        direction='多头' if r['position_direction']=='long' else '空头'
        leg='同日重试' if r['is_retry'] else '原始开仓'
        header += ['',f"### {r['review_id']} / {r['episode_id']} · {r['vt_symbol']} · {direction} · {leg} · {r['price_result']} {fmt(r['net_pnl'])}元",'']
        rank=f"固定fu（编号11，不是模型第11名）" if r['pool_kind']=='fixed_fu' else f"模型名次{int(r['ai_product_pool_rank'])}"
        header += [f"- **入场依据**：信号日{r['signal_date']}，`{r['signal']}`；月池评估日{r['ai_product_pool_signal_date']}，{rank}。原始候选{int(r['candidate_index'])}，RSI={float(r['signal_rsi']):.2f}。重试腿沿用同一原始候选，不重新评分。",
          f"- **价量与执行**：{r['first_trade_id']}于{moment(r['first_datetime'])}记开仓{r['opened_volume']:g}手，价{fmt(r['entry_price'])}；{r['last_trade_id']}于{moment(r['last_datetime'])}记平仓，价{fmt(r['exit_price'])}。开仓价格源：{labels.get(r['entry_price_source'],r['entry_price_source'])}；平仓价格源：{labels.get(r['exit_price_source'],r['exit_price_source'])}。",
          f"- **损益核算**：毛盈亏{fmt(r['gross_pnl'])}元 − 滑点{fmt(r['slippage'])}元 − 手续费{fmt(r['commission'])}元 = 净盈亏{fmt(r['net_pnl'])}元。退出依据：{r['exit_reason_zh']}。",
          f"- **定仓证据**：信号日最终净账权益{fmt(r['signal_account_equity'])}元，策略实际用于原始定仓的内部权益{fmt(r['signal_sizing_equity'])}元（高出{fmt(r['sizing_equity_excess'])}元，比例{r['sizing_equity_ratio']:.3f}倍）。记录的信号止损距离{fmt(r['signal_stop_distance'])}；最终手数还受品种/组合限额约束，不能按权益比例直接推算修复后的手数。"]
        if r['c9_first_stop_time']:
            text=f"- **C9事件链**：首止{moment(r['c9_first_stop_time'])}，0.5R止损价{fmt(r['c9_stop_price'])}，该事件R价格距离{fmt(r['c9_risk_price'])}。"
            text+=f"回到原入场价重试：{moment(r['c9_reentry_time'])}。" if r['c9_reentry_time'] else '未触发重试。'
            if r['c9_retry_failed_time']: text+=f"再次止损：{moment(r['c9_retry_failed_time'])}。"
            if r['night_event']: text+='事件含21点以后分钟，涉及下一交易日夜盘，不能当作严格同一交易日事件顺序。'
            header.append(text)
        if r['minute_evidence_flags']:
            header.append('- **分钟执行核验**：'+r['minute_evidence_flags'])
        reason=r['exit_reason']
        if reason=='stage847_intraday_05r_initial_stop':
            verdict='按当前引擎所扫描分钟与判定顺序，记录先触发−0.5R止损；这不等于已验证真实交易日内先后路径或止损可成交性，同分钟歧义以上述执行核验为准。'
        elif reason=='stage847_intraday_retry_failed_05r_stop':
            verdict='原价收复未延续，重试再次止损；与首开合为一次信号事件后再评价，不能把它视为新的独立选品失败。'
        elif reason.endswith('risk_cluster_heat_deleverage'):
            verdict='退出由品种风险容量触发；它不是普通止盈信号，需同时考虑被高估的内部权益与容量语义。'
        elif reason.endswith('base_stop'):
            verdict='持仓未能守住正式初始止损条件；日线信号经下一开盘代理执行，成交亏损可能大于信号时计划风险。'
        elif reason.endswith('prev2day_stop'):
            verdict='持仓触发前两日极值退出；最终盈亏由持仓路径与下一次实际开盘代理共同决定，不能仅用入场胜率解释。'
        elif reason=='rollover_close':
            verdict='这是合约换月平仓，不等于趋势方向出现反向信号。'
        else: verdict='以成交与事件来源为准；没有足够证据把这一笔归结为特定市场宏观原因。'
        if abs(r['gross_pnl'])<1e-7 and r['net_pnl']<0: verdict+='该笔价差持平，净亏全部来自滑点。'
        elif r['gross_pnl']<0: verdict+='价差本身已亏损，滑点进一步扩大损失。'
        elif r['net_pnl']>0: verdict+='这是必须保留的盈利对照，不能只复盘亏损样本。'
        header.append('- **逐笔判断**：'+verdict)
    marker='<!-- STAGE247_GENERATED_TRADES -->'
    current=a.stage.read_text(encoding='utf-8').split(marker)[0].rstrip()
    a.stage.write_text(current+'\n\n'+marker+'\n\n'+'\n'.join(header)+'\n',encoding='utf-8')
    monthly=pd.read_csv(out/'stats_review/monthly_mtm.csv')
    ms=pd.read_csv(out/'stats_review/monthly_cycle_episode_stats.csv')
    relevant=ms[(ms.level=='cycle') & (ms.basis=='exit')].copy()
    if relevant.empty:
        raise RuntimeError(f'monthly_cycle_basis_unexpected:{sorted(ms.basis.unique())}')
    monthly=monthly.merge(relevant[['month','count','wins','win_rate_pct']],on='month',how='left',validate='one_to_one')
    monthly.to_csv(out/'monthly_combined.csv',index=False,encoding='utf-8-sig')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for font in ['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Supplemental/Arial Unicode.ttf']:
        if Path(font).exists():
            font_manager.fontManager.addfont(font)
            plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
            break
    plt.rcParams['axes.unicode_minus']=False
    window=daily.loc[daily.index>='2025-09-01'].copy()
    prev=float(daily.loc[daily.index<'2025-09-01','account_equity'].iloc[-1])
    fig,axes=plt.subplots(3,1,figsize=(12,10),gridspec_kw={'height_ratios':[1.2,1,1]})
    axes[0].plot(pd.to_datetime(window.index),window.account_equity/10000,color='#235c75',lw=1.6)
    axes[0].axhline(prev/10000,color='#777',ls='--',lw=.8)
    axes[0].set_ylabel('权益（万元）');axes[0].set_title('2025年9月以来：正式回测逐笔复盘',loc='left',fontweight='bold',fontsize=16)
    axes[0].text(.01,.04,f'期初 {prev/10000:,.2f}万 → 期末 {window.account_equity.iloc[-1]/10000:,.2f}万',transform=axes[0].transAxes)
    x=np.arange(len(monthly))
    axes[1].bar(x,monthly.net_mtm_pnl/10000,color=['#b6503b' if v<0 else '#297568' for v in monthly.net_mtm_pnl])
    axes[1].axhline(0,color='#777',lw=.7);axes[1].set_ylabel('月度盯市盈亏（万元）')
    axes[1].set_xticks(x,monthly.month,rotation=45,ha='right')
    axes[2].bar(x,monthly.win_rate_pct.fillna(0),color='#517aa3')
    for k,row in monthly.iterrows():
        axes[2].text(k,float(row.win_rate_pct or 0)+1,f'{int(row.wins)}/{int(row["count"])}',ha='center',fontsize=9)
    axes[2].set_ylim(0,100);axes[2].set_ylabel('平仓周期胜率（%）');axes[2].set_xticks(x,monthly.month,rotation=45,ha='right')
    for ax in axes:
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18)
    fig.text(.08,.005,'柱上标注为盈利周期数/平仓周期数；月度盯市与平仓归属不同。固定正式规则、手续费为零；含已披露的权益定仓与时序缺陷。',fontsize=9)
    fig.tight_layout(rect=(0,.03,1,1));fig.savefig(out/'period_overview.png',dpi=170);fig.savefig(out/'period_overview.svg');plt.close(fig)
    for n,h in fingerprints.items(): assert hashlib.sha256((src/n).read_bytes()).hexdigest()==h
    checks={'status':'passed','source_files_unchanged':True,'cycle_count':len(ledger),'fill_count':len(fills),'episode_count':len(epmap),'net_pnl':float(ledger.net_pnl.sum()),'independent_cycle_pnl_matched':True,'source_sha256':fingerprints}
    (out/'report_build_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in checks.items() if k!='source_sha256'},ensure_ascii=False))

if __name__=='__main__':main()
