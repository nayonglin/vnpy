"""Frozen blocked-candidate observations using the pinned canonical chart engine.

The trade-shaped intermediate exists only to call the canonical aggregation
contract. It is stripped before export: these records have no trades or PnL.
No strategy, market download, credentials, or production imports are used.
"""
from __future__ import annotations
import argparse
import html
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from stage248_recap_html import ROOT, LINE, CANONICAL, RENDERER_SHA, sha, read, load_renderer, validate_output
from stage253_recap import MAPPING

BASE=LINE/'outputs/stage255_blocked_signals'
CUTOFF='2026-10-14'
PUBLIC_SOURCE_FIELDS=('signal_id candidate_key signal_date signal_datetime contract_vt_symbol product_vt_symbol direction signal_family entry_context candidate_index candidate_status record_kind blocking_reason_code blocking_reason_zh primary_reason_code is_ai_primary_block ai_pool_disallowed ai_allowed ai_eval_date ai_rank ai_score ai_score_rank_semantics ai_reason_zh reference_price reference_price_date reference_price_source_field reference_price_semantics additional_blocking_reason_codes additional_blocking_reasons_zh atr_shock_blocked range_atr_blocked source_file source_row_index source_sha256 source_run source_run_provenance_sha256 data_completeness').split()
CHART_FIELDS=('draw_intraday chart_x_start chart_x_end daily_start daily_end monthly_start monthly_end missing_15m_dates missing_context_dates context_fallback_dates source_switch_x').split()


def flag(value)->bool:
    return str(value).lower() in ('1','1.0','true')


def signal_rows(signals:pd.DataFrame)->pd.DataFrame:
    """Only date/price anchors are passed to canonical context aggregation."""
    if signals.signal_id.duplicated().any():raise ValueError('Duplicate signal identity')
    rows=[]
    for i,s in enumerate(signals.itertuples(index=False)):
        day=pd.Timestamp(s.signal_date).normalize()
        price=float(s.reference_price)
        if not np.isfinite(price) or price<=0:raise ValueError('Missing signal reference price')
        rows.append(dict(result_rank=i+1,result_type='signal',is_tail=0,draw_intraday=0,
            lot_id='',lot_count=0,open_trade_id=s.signal_id,close_trade_id='',
            vt_symbol=s.contract_vt_symbol,product=s.product_vt_symbol,direction=s.direction,
            entry_date=day,exit_date=day,entry_price=price,exit_price=price,
            weighted_exit_price=np.nan,price_change_pct=np.nan,price_change_label='',
            volume=np.nan,realized_pnl=np.nan,r_multiple=np.nan,selection_basis='',
            holding_calendar_days=0,exit_reason='',signal=getattr(s,'signal_family',''),
            profit_r_threshold=np.nan,loss_r_threshold=np.nan))
    return pd.DataFrame(rows)


def signal_meta(internal:dict,source:dict)->dict:
    """Public signal-only schema: never leak the trade-layout placeholders."""
    result={key:internal[key] for key in CHART_FIELDS if key in internal}
    result.update({key:source.get(key) for key in PUBLIC_SOURCE_FIELDS if key in source})
    for key in ('is_ai_primary_block','ai_pool_disallowed','atr_shock_blocked','range_atr_blocked'):
        result[key]=flag(result.get(key))
    result.update(vt_symbol=source['contract_vt_symbol'],product=source['product_vt_symbol'],
        signal_date=str(pd.Timestamp(source['signal_date']).date()),
        signal_x=internal['entry_x'],reference_source=internal['entry_source'],
        reference_marker_price=internal['entry_marker_price'])
    rank=source.get('ai_rank')
    if rank is None or pd.isna(rank) or float(rank)<=0:
        result['ai_rank']=None;result['ai_score']=None
    return result


def one(text:str,old:str,new:str)->str:
    if text.count(old)!=1:raise ValueError(f'Canonical replacement count changed: {old[:60]}')
    return text.replace(old,new,1)


def span(text:str,start:str,end:str,new:str)->str:
    pattern=re.escape(start)+r'.*?'+re.escape(end)
    result,count=re.subn(pattern,lambda _:new,text,flags=re.S)
    if count!=1:raise ValueError(f'Canonical span count changed: {start}')
    return result


def adapt_html(page:str)->str:
    """Asserted label/filter/marker adaptation; chart implementation untouched."""
    page=span(page,'<select id="result">','</select>','<select id="result" aria-label="终态拦截原因"></select><select id="ai" aria-label="AI资格口径"><option value="all">全部AI资格</option><option value="primary">AI直接拦截</option><option value="disallowed">当月AI未准入（含其他主因）</option><option value="allowed">当月AI允许</option></select>')
    page=span(page,'<select id="sort">','</select>','<select id="sort" aria-label="信号日期排序"><option value="oldest">信号日期从早到晚</option><option value="newest">信号日期从晚到早</option></select>')
    page=one(page,'grid-template-columns:160px 180px 150px 170px minmax(300px,1fr) auto auto','grid-template-columns:190px 200px 160px 110px 130px minmax(250px,1fr) auto auto')
    page=one(page,"const rankBasis=summary.rank_basis||'r_multiple';", "const aiEl=document.getElementById('ai');")
    page=span(page,'if(summary.intraday_top_selection){','}\nconst periodInputs=', 'const periodInputs=')
    page=one(page,"r.meta.entry_date.slice(0,4)","r.meta.signal_date.slice(0,4)")
    page=one(page,"function apply(){", "options(resultEl,uniq(records.map(r=>r.meta.blocking_reason_zh)),'终态原因');\nfunction apply(){")
    page=span(page,'function apply(){','\nfunction rfmt(v)',"""function apply(){const reason=resultEl.value,y=yearEl.value,p=productEl.value,ai=aiEl.value;filtered=records.filter(r=>(!reason||r.meta.blocking_reason_zh===reason)&&(!y||r.meta.signal_date.startsWith(y))&&(!p||r.meta.product===p)&&(ai==='all'||(ai==='primary'&&r.meta.is_ai_primary_block)||(ai==='disallowed'&&r.meta.ai_pool_disallowed)||(ai==='allowed'&&!r.meta.ai_pool_disallowed)));filtered.sort((a,b)=>{const cmp=a.meta.signal_date.localeCompare(b.meta.signal_date)||a.meta.signal_id.localeCompare(b.meta.signal_id);return sortEl.value==='newest'?-cmp:cmp});active=0;refreshSelect();render()}
function rfmt(v)""")
    page=span(page,'function refreshSelect(){','\nfunction colors',"""function refreshSelect(){tradeEl.innerHTML=filtered.map((r,i)=>`<option value="${i}">#${i+1} ${r.meta.signal_date} ${r.meta.vt_symbol} ${r.meta.direction} · ${r.meta.blocking_reason_zh}</option>`).join('');tradeEl.value=String(active)}
function colors""")
    page=span(page,'const resultLabel=',';document.getElementById(\'metrics\')',"""const aiLabel=m.is_ai_primary_block?'AI直接拦截':(m.ai_pool_disallowed?'当月AI未准入；终态为其他原因':'当月AI允许');const secondary=JSON.parse(m.additional_blocking_reasons_zh||'[]').join('；');const rankText=m.ai_rank===null?'未记录（不显示默认0）':`第${m.ai_rank}名 / ${fmt(m.ai_score,4)}`;const post=m.available_post_signal_bars<50?`后窗仅${m.available_post_signal_bars}/50日，已截断`:'后窗50日';const metric=[['候选',`#${active+1}/${filtered.length}`],['信号日 / 方向',`${m.signal_date} / ${m.direction}`],['具体合约',m.vt_symbol],['终态原因',m.blocking_reason_zh],['AI口径',`${aiLabel}<br>评估日：${m.ai_eval_date||'未记录'}`],['AI排名 / 分数',rankText],['信号日参考价（非成交）',fmt(m.reference_price)],['图窗',`${post}<br>${contextGap}`],['附加诊断',secondary||'无附加记录'],['参考价K线来源',m.reference_source],['候选类型',m.record_kind==='planned_open_unfilled'?'已计划但未成交':'已记录跳过候选'],['原始证据',`候选索引 ${m.candidate_index}；CSV数据行 ${Number(m.source_row_index)+1}`]];document.getElementById('metrics')""")
    page=one(page,"x:[m.entry_x,m.exit_x],y:[m.entry_marker_price,m.exit_marker_price]", "x:[m.signal_x],y:[m.reference_marker_price]")
    page=one(page,"name:'同源成交价格',marker:{symbol:['triangle-up','triangle-down'],size:12,color:['#2563eb','#9333ea']}","name:'信号参考（非成交）',marker:{symbol:'diamond',size:12,color:'#d97706'}")
    page=one(page,'${resultLabel} #${active+1} ${m.vt_symbol} ${m.direction}｜${m.entry_date} → ${m.exit_date}｜R=${rfmt(m.r_multiple)}｜PnL=${fmt(m.realized_pnl,0)}｜${m.selection_basis}｜${source}', '${m.vt_symbol} ${m.direction}｜信号 ${m.signal_date}（非成交）｜${m.blocking_reason_zh}｜${source}')
    page=one(page,'uirevision:m.open_trade_id','uirevision:m.signal_id')
    page=span(page,"shapes:[{type:'rect'",']};visible.forEach',"shapes:[{type:'line',xref:'x',yref:'paper',x0:m.signal_x,x1:m.signal_x,y0:0,y1:1,line:{color:'#d97706',width:1.5,dash:'dot'}},...switches],annotations:[{xref:'x',yref:'paper',x:m.signal_x,y:1,text:'信号参考（非成交）',showarrow:false,font:{color:'#d97706'}}]};visible.forEach")
    page=one(page,'resultEl.onchange=apply;','aiEl.onchange=apply;resultEl.onchange=apply;')
    for old,new in [
        ('日K严格展示开仓前300个交易日至最终平仓后50个交易日的可用历史','观察图窗为信号前300个交易日至后50个交易日，最晚截止2026-10-14；后窗不足时如实截断'),
        ('月K独立展示开仓前10个月至最终平仓后10个月','月K等高周期复用相同观察截止，均线仅以此前真实历史预热'),
        ('蓝线=开仓日，紫线=最终平仓日，淡黄色=持仓区间','橙色菱形和竖线=信号参考（非成交），没有持仓区间'),
        ('上一笔','上一条'),('下一笔','下一条'),
        ('没有符合筛选条件的交易','没有符合筛选条件的候选'),
        ('当前勾选的周期在这笔交易上没有可绘制数据','当前勾选的周期在此候选上没有可绘制数据'),
        ('当前交易无15分钟数据，已跳过15分钟K；切到已补数交易时恢复。','此观察页未提供15分钟数据，已跳过该周期。'),
        ('当前交易无15分钟数据。','此观察页未提供15分钟数据。')]:
        page=one(page,old,new)
    return page


def load_source(signals_path:Path,run:Path)->tuple:
    source_summary=read(signals_path.parent/'source_summary.json')
    assert source_summary['source_run']==str(run.resolve())
    assert sha(signals_path)==source_summary['blocked_signals_sha256']
    for name,expected in source_summary['source_hashes'].items():assert sha(run/name)==expected
    signals=pd.read_csv(signals_path)
    assert len(signals)==source_summary['blocked_signals_rows'] and len(signals)>0
    assert set(signals.record_kind)<= {'candidate_rejected','planned_open_unfilled'}
    assert not signals.has_actual_open_fill.map(flag).any()
    assert not signals.reference_price_is_execution.map(flag).any()
    assert signals.signal_date.between('2025-01-01',CUTOFF).all()
    assert set(signals.source_run)=={str(run.resolve())}
    assert set(signals.source_run_provenance_sha256)=={sha(run/'run_provenance.json')}
    inputs=read(run/'input_manifest.json')
    market_hashes={str(path):sha(ROOT/path) for path in [Path('.vntrader/database.db'),MAPPING]}
    for relative,expected in market_hashes.items():assert inputs[relative]==expected
    return signals,source_summary,market_hashes


def generate(signals_path:Path,run:Path,output:Path=BASE/'recap')->None:
    output=validate_output(output,BASE)
    signals,evidence,market_hashes=load_source(signals_path,run)
    signals=signals.sort_values(['signal_date','signal_id']).reset_index(drop=True)
    rows=signal_rows(signals)
    mapping=pd.read_csv(ROOT/MAPPING,parse_dates=['date']).dropna(subset=['main_contract_vt'])
    mapping=mapping[mapping.date.le(CUTOFF)]
    with sqlite3.connect(f'file:{ROOT}/.vntrader/database.db?mode=ro',uri=True) as db:
        bars=pd.read_sql_query("SELECT symbol || '.' || exchange AS vt_symbol, datetime AS date, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume FROM dbbardata WHERE interval='d' ORDER BY datetime",db)
    bars.date=pd.to_datetime(bars.date).dt.normalize();bars=bars[bars.date.le(CUTOFF)]
    cache={key:frame.drop(columns='vt_symbol').reset_index(drop=True) for key,frame in bars.groupby('vt_symbol',sort=False)}
    def contract_daily(symbol):
        if symbol not in cache:raise RuntimeError(f'Missing contract: {symbol}')
        return cache[symbol]
    renderer=load_renderer({'_contract_daily':contract_daily,'_daily_from_existing_minute_files':lambda *args:pd.DataFrame()})
    context={};minute_dates={}
    for i,row in enumerate(rows.itertuples(index=False)):
        daily,minute_days=renderer['_context_daily'](row,mapping,cache,allow_daily_download=False,allow_noncritical_daily_gaps=True,data_end=pd.Timestamp(CUTOFF))
        # The canonical monthly context may extend farther than 50 days. Keep
        # its real prior warmup, but never show or aggregate extra future bars.
        daily=daily[daily.date.le(daily.loc[daily.display.eq(1),'date'].max())].copy()
        context[row.open_trade_id]=daily;minute_dates[row.open_trade_id]=minute_days
        if (i+1)%25==0:print(f'context {i+1}/{len(rows)}',flush=True)
    records,_=renderer['_records'](rows,context,minute_dates,pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume']))
    manifests=[]
    for record,source in zip(records,signals.to_dict('records')):
        record['meta']=signal_meta(record['meta'],source);meta=record['meta'];dates=record['daily']['date']
        meta['available_pre_signal_bars']=sum(day<meta['signal_date'] for day in dates)
        meta['available_post_signal_bars']=sum(day>meta['signal_date'] for day in dates)
        assert meta['available_pre_signal_bars']<=300 and meta['available_post_signal_bars']<=50
        assert max(dates)<=CUTOFF
        meta['chart_x_start']=record['daily']['x'][0]-.5;meta['chart_x_end']=record['daily']['x'][-1]+.5
        meta['reference_price_matches_exact_daily_close']=None
        if meta['reference_source']==meta['vt_symbol']:
            actual=record['daily']['close'][dates.index(meta['signal_date'])]
            meta['reference_price_matches_exact_daily_close']=bool(np.isclose(actual,meta['reference_price'],rtol=0,atol=1e-8))
        manifests.append({**meta,**{f'{period}_bars':len(record[period]['x']) for period in ['daily','day30','day10','weekly','monthly','intraday']}})
    manifest=pd.DataFrame(manifests)
    warning='候选未成交，仅绘制信号日收盘参考；后续K线是事后观察，不是模拟交易收益。来源为Stage254正式参数＋现有数据诊断，严格数据验收未通过（原运行2个普通首锚缺口）。'
    coverage=f'全部已记录的被拦截候选共{len(signals)}条：181条跳过与1条已计划但未成交；AI直接拦截36条，当月AI未准入91条（含55条先因其他原因终止）。'
    summary=dict(page_title='全部已记录的被拦截候选 · 2025-01-01—2026-10-14',source_label='Stage254 正式参数·候选记录',source_version='run_diagnostic',source_warning=warning,coverage_note=coverage,footer_scope='没有成交、持仓PnL、R或胜负定义；未记录的理论信号不在此页。',episode_scope='all',record_count=len(records),record_kind_counts=signals.record_kind.value_counts().to_dict(),primary_reason_counts=signals.blocking_reason_code.value_counts().to_dict(),ai_primary_block_count=int(signals.is_ai_primary_block.map(flag).sum()),ai_pool_disallowed_count=int(signals.ai_pool_disallowed.map(flag).sum()),source_bundle=str(run.resolve()),signals_path=str(signals_path.resolve()),signals_sha256=sha(signals_path),source_summary_sha256=sha(signals_path.parent/'source_summary.json'),source_sha256=evidence['source_hashes'],market_sha256=market_hashes,renderer_path=str(CANONICAL),renderer_sha256=RENDERER_SHA,adapter_sha256=sha(Path(__file__)),proxy_signal_count=int(manifest.context_fallback_dates.map(bool).sum()),context_gap_signal_count=int(manifest.missing_context_dates.map(bool).sum()),proxy_reference_count=int(manifest.reference_marker_price.isna().sum()),reference_close_mismatch_count=int(manifest.reference_price_matches_exact_daily_close.eq(False).sum()),post_window_truncated_count=int(manifest.available_post_signal_bars.lt(50).sum()),cutoff=CUTOFF,minute_chart_available=False,source_data_incomplete=True,strict_data_accepted=False,rerun=False,market_download=False,training=False,production_access=False,generated_at=datetime.now().astimezone().isoformat())
    page=adapt_html(renderer['_html'](records,summary))
    overview='<section class="panel" style="padding:16px;margin:12px 0"><b>'+html.escape(warning)+'</b><p>'+coverage+'</p><p>MA5极值、坡度等在候选记录前清空的理论信号没有完整日志；不能把本页视作所有理论信号全集。附加ATR诊断只挂在原候选下，未重复计数。定仓为零保留其实际理由，不概括为资金不足。</p><p>信号参考价来自候选 planned_entry_price（策略信号日收盘），不是次日可成交价。灰虚线为精确合约与主力背景的切换；没有15分钟图，不补造缺失。</p><p><a href="../blocked_signals.csv">候选明细CSV</a> · <a href="../source_summary.json">来源与覆盖</a> · <a href="../rollover_delay_context.csv">换月延期上下文</a>（6次发起、17条等待/计划，另1条到期；不增加候选数）</p></section>'
    page=one(page,'<div class="toolbar">',overview+'<div class="toolbar">')
    # Guard the source remains frozen while context is assembled.
    assert sha(signals_path)==summary['signals_sha256']
    output.mkdir(parents=True)
    manifest.to_csv(output/'chart_manifest.csv',index=False)
    for name,data in [('records.json',records),('summary.json',summary)]:
        (output/name).write_text(json.dumps(renderer['_json_safe'](data),ensure_ascii=False,indent=2 if name=='summary.json' else None,separators=(',',':'),allow_nan=False))
    (output/'index.html').write_text(page)
    print(json.dumps(dict(html=str(output/'index.html'),records=len(records),summary=str(output/'summary.json'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--signals',type=Path,required=True);parser.add_argument('--source-run',type=Path,required=True);parser.add_argument('--output',type=Path,default=BASE/'recap')
    args=parser.parse_args();generate(args.signals,args.source_run,args.output)
