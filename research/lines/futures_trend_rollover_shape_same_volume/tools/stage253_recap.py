"""Frozen Stage251/252 adapter; reuse canonical chart functions via Stage248.

No backtest engine imports, broker/production access, or market downloads.
"""
from __future__ import annotations
import argparse,ast,html,json,re,sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from stage248_recap_html import ROOT,LINE,CANONICAL,RENDERER_SHA,sha,read,close,validate_output,load_renderer

OUT=LINE/'outputs/stage253_ai_forensics'
PROFILES={
 'ai_no_half_r':('stage251_half_r_ab/C_final',False,'AI选品开 · 0.5R关 · 严格冻结回测','1aa46f544b6c339a2805d9dbcea0d727b7ed65bd325af1476a83c6c93b217c64','f044262c8ecde8aa00d50a4ad6a3c4f1be69a6e4f76609b431a76139a2f7e92d'),
 'no_ai_no_half_r':('stage252_no_ai_ab/C_no_ai_no_half_r_existing_data',True,'AI选品关 · 0.5R关 · 数据不完整估算','4e3c9f344583e3b7b4b53ab934c156ca9ae7242e56f90773188db4556e847a98','e85d9162a67acfbadd6be2f463d5cec9304f6f4924d662e688a194bc388f9ffe')}
REQUIRED=['metrics.json','daily.csv','trades.csv','effective_parameters.json','run_provenance.json','input_manifest.json','statistics_audit/summary.json','statistics_audit/complete_cycles.csv','statistics_audit/open_positions.csv']
MAPPING=Path('examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv')

def require_bundle(run:Path)->None:
    missing=[name for name in REQUIRED if not (run/name).is_file()]
    if missing:raise ValueError(f'Incomplete frozen bundle: {missing}')

def load_source(profile:str)->dict:
    relative,diagnostic,label,trade_sha,provenance_sha=PROFILES[profile]
    run=LINE/'outputs'/relative;require_bundle(run)
    assert sha(run/'trades.csv')==trade_sha and sha(run/'run_provenance.json')==provenance_sha
    metrics=read(run/'metrics.json');stats=read(run/'statistics_audit/summary.json');provenance=read(run/'run_provenance.json');inputs=read(run/'input_manifest.json')
    assert provenance['completed_at'] and provenance['all_data_and_model_inputs_unchanged_during_run']
    assert provenance['diagnostic_incomplete_minutes']==diagnostic
    assert sha(run/'input_manifest.json')==provenance['input_manifest_sha256']
    for filename,expected in stats['source_hashes'].items():assert sha(run/filename)==expected
    for relative in [Path('.vntrader/database.db'),MAPPING]:assert sha(ROOT/relative)==inputs[str(relative)]
    trades=pd.read_csv(run/'trades.csv').set_index('trade_id',verify_integrity=True)
    daily=pd.read_csv(run/'daily.csv',parse_dates=['date']);cycles=pd.read_csv(run/'statistics_audit/complete_cycles.csv');residual=pd.read_csv(run/'statistics_audit/open_positions.csv')
    assert daily.date.is_monotonic_increasing and not daily.date.duplicated().any()
    assert set(trades.variant)=={metrics['variant']} and set(daily.variant)=={metrics['variant']}
    assert daily.date.between(metrics['start'],metrics['end']).all()
    close(len(trades),metrics['total_trade_count'],'fill count');close(len(cycles),stats['closed_cycles'],'cycle count')
    close(len(residual),stats['end_open_contracts'],'residual count')
    close(daily.account_equity.iloc[-1],metrics['end_equity'],'end equity')
    close(daily.net_pnl.sum(),metrics['end_equity']-metrics['account_capital'],'daily total')
    close(cycles.net_pnl.sum()+residual.net_mtm.sum(),daily.net_pnl.sum(),'closed plus residual MTM')
    close(daily.slippage.sum(),metrics['total_slippage'],'slippage')
    consumed=[]
    for value in pd.concat([cycles.trade_ids,residual.trade_ids]):consumed.extend(ast.literal_eval(value))
    assert len(consumed)==len(set(consumed))==len(trades) and set(consumed)==set(trades.index)
    return dict(run=run,metrics=metrics,stats=stats,provenance=provenance,daily=daily,trades=trades,cycles=cycles,residual=residual,diagnostic=diagnostic,label=label,source_sha256={name:sha(run/name) for name in REQUIRED})

def episode_rows(cycles:pd.DataFrame,trades:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for i,c in enumerate(cycles.itertuples(index=False)):
        fills=trades.loc[ast.literal_eval(c.trade_ids)];opens=fills[fills.offset.isin(['开','Open'])];exits=fills[~fills.offset.isin(['开','Open'])]
        if len(opens)!=1 or exits.empty:raise ValueError('Cycle requires exactly one entry and completed exits')
        entry=opens.iloc[0];final=trades.loc[c.last_trade_id]
        close(exits.volume.sum(),entry.volume,'closed volume');close(entry.volume,c.opened_volume,'cycle volume')
        weighted=np.average(exits.price,weights=exits.volume);change=(weighted/entry.price-1)*100
        start=pd.Timestamp(c.entry_date);end=pd.Timestamp(c.exit_date)
        close(float(entry.price),float(c.entry_price),'entry price');close(float(final.price),float(c.exit_price),'final price')
        reasons=' / '.join(dict.fromkeys(exits.exit_reason.fillna('未标注').astype(str)))
        rows.append(dict(open_trade_id=c.first_trade_id,close_trade_id=c.last_trade_id,lot_id=c.first_trade_id,lot_count=len(exits),vt_symbol=c.vt_symbol,product=c.product,direction='多' if c.direction=='long' else '空',entry_date=start,exit_date=end,entry_price=entry.price,exit_price=final.price,weighted_exit_price=weighted,volume=c.opened_volume,price_change_pct=change,price_change_label=f'标的原价涨跌 {change:+.2f}%（非账户收益）',realized_pnl=c.net_pnl,r_multiple=float('nan'),result_type='profit' if c.net_pnl>1e-7 else 'loss' if c.net_pnl< -1e-7 else 'flat',result_rank=i+1,is_tail=0,draw_intraday=0,profit_r_threshold=float('nan'),loss_r_threshold=float('nan'),holding_calendar_days=(end-start).days,exit_reason=reasons,signal='冻结账本；图表均线不是策略信号',selection_basis=f'{c.first_trade_id} → {c.last_trade_id}｜{int(c.opened_volume)}手｜{c.first_datetime} → {c.last_datetime}｜{reasons}'))
    return pd.DataFrame(rows)

def generate(profile:str)->None:
    output=validate_output(OUT/f'recap_{profile}',OUT);s=load_source(profile);metrics=s['metrics'];episodes=episode_rows(s['cycles'],s['trades'])
    mapping=pd.read_csv(ROOT/MAPPING,parse_dates=['date']).dropna(subset=['main_contract_vt']);mapping=mapping[mapping.date.le(metrics['end'])]
    with sqlite3.connect(f'file:{ROOT}/.vntrader/database.db?mode=ro',uri=True) as db:
        bars=pd.read_sql_query("SELECT symbol || '.' || exchange AS vt_symbol, datetime AS date, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume FROM dbbardata WHERE interval='d' ORDER BY datetime",db)
    bars.date=pd.to_datetime(bars.date).dt.normalize();bars=bars[bars.date.le(metrics['end'])]
    cache={key:frame.drop(columns='vt_symbol').reset_index(drop=True) for key,frame in bars.groupby('vt_symbol',sort=False)}
    def contract_daily(symbol):
        if symbol not in cache:raise RuntimeError(f'Missing exact contract {symbol}')
        return cache[symbol]
    renderer=load_renderer({'_contract_daily':contract_daily,'_daily_from_existing_minute_files':lambda *args:pd.DataFrame()})
    context={};minute_dates={}
    print(f'{profile}: {len(episodes)} completed cycles; {len(s["residual"])} residual contracts disclosed',flush=True)
    for i,row in enumerate(episodes.itertuples(index=False)):
        context[row.open_trade_id],minute_dates[row.open_trade_id]=renderer['_context_daily'](row,mapping,cache,allow_daily_download=False,allow_noncritical_daily_gaps=True,data_end=pd.Timestamp(metrics['end']))
        if (i+1)%50==0:print(f'context {i+1}/{len(episodes)}',flush=True)
    records,manifest=renderer['_records'](episodes,context,minute_dates,pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume']))
    for record,row in zip(records,episodes.itertuples(index=False)):
        for key in ['entry_price','exit_price','realized_pnl','volume']:close(record['meta'][key],getattr(row,key),f'rendered {key}')
        assert record['meta']['entry_source']==row.vt_symbol==record['meta']['exit_source']
        assert record['meta']['entry_date']==str(row.entry_date.date()) and record['meta']['exit_date']==str(row.exit_date.date())
    warning=('数据不完整：本页仅为现有数据条件估算，不是严格验收结果。C2入场路径缺43,172分钟，普通成交首锚缺268个；不据此判定AI因果贡献。' if s['diagnostic'] else '已通过严格数据与账本验收的冻结研究回测；不是生产收益或部署资格。')
    warning+=' 0.5R关闭，C2保留；月池资格开关不代表关闭pairwise排序或多头仓位倾斜。分钟缓存仅覆盖选定片段，本次15分钟图未提供，不补造。'
    summary=dict(source_label=s['label'],source_version=metrics['variant'],source_warning=warning,page_title='逐笔回顾 · '+s['label'],episode_scope='all',coverage_note=f'全量{len(episodes)}个已完成持仓周期；另{len(s["residual"])}个未平仓合约单列，未伪造exit。',footer_scope=f'{len(episodes)}个完成周期；{len(s["trades"])}笔成交。',rank_basis='realized_pnl',source_bundle=str(s['run']),source_sha256=s['source_sha256'],renderer_sha256=RENDERER_SHA,renderer_path=str(CANONICAL),frozen_metrics=metrics,frozen_statistics=s['stats'],completed_cycle_count=len(episodes),profit_count=int(episodes.result_type.eq('profit').sum()),loss_count=int(episodes.result_type.eq('loss').sum()),flat_count=int(episodes.result_type.eq('flat').sum()),residual_open_contracts=len(s['residual']),residual_net_mtm=float(s['residual'].net_mtm.sum()),diagnostic=s['diagnostic'],minute_chart_available=False,rerun=False,market_download=False,training=False,production_access=False,strategy_change=False,generated_at=datetime.now().astimezone().isoformat(),proxy_episode_count=int(manifest.context_fallback_days.gt(0).sum()),context_gap_episode_count=int(manifest.missing_context_dates.map(bool).sum()),notes=['日线标记采用交易日，前夜实际成交时间保留在每笔说明。','入场与最终平仓日线来自原始精确合约；合约上市/退市之外背景由canonical主力代理并以灰线标记，不是策略信号数据。','缺少的上市前/截止后背景、MA预热不补造；R缺乏唯一风险绑定，显示N/A。','最终平仓标记用最后成交价，标的价格涨跌采用所有退出的成交量加权价。'])
    page=renderer['_html'](records,summary)
    total=metrics['end_equity'];rate=s['stats']['periods']['all']['entry_cohort_complete_cycles']['win_rate_pct']
    overview=('<section class="panel" style="padding:18px;margin:16px 0"><h2>冻结账本总览</h2>'
      f'<p>{metrics["account_capital"]:,.0f} → <b>{total:,.2f} 元</b>；总收益 {metrics["total_return_pct"]:.2f}%；最大回撤 {metrics["max_dd_pct"]:.2f}%；Sharpe {metrics["sharpe"]:.4f}；滑点 {metrics["total_slippage"]:,.0f}元；完整周期胜率 {rate:.2f}%。</p>'
      f'<p>盈/亏/平：{summary["profit_count"]}/{summary["loss_count"]}/{summary["flat_count"]}；完成周期净收益 {s["cycles"].net_pnl.sum():,.2f}元，期末未平仓净MTM {summary["residual_net_mtm"]:,.2f}元，合计与冻结权益一致。</p>'
      '<details><summary>未平仓合约与图表数据边界</summary>'+s['residual'][['vt_symbol','direction','entry_date','entry_price','signed_pos','mark_price','mark_date','net_mtm']].to_html(index=False,border=0)+'<p>'+html.escape('；'.join(summary['notes']))+'</p></details></section>')
    banner=('<div role="alert" style="padding:16px;border:2px solid '+('#b42318' if s['diagnostic'] else '#2563eb')+';background:'+('#fff0ed' if s['diagnostic'] else '#eff6ff')+';font-size:16px"><b>'+html.escape(warning)+'</b></div>')
    page=page.replace('<div class="toolbar">',banner+overview+'<div class="toolbar">',1)
    page=page.replace('<option value="profit_tail">盈利尾部</option>','').replace('<option value="loss_tail">亏损尾部</option>','')
    for name,expected in s['source_sha256'].items():assert sha(s['run']/name)==expected
    output.mkdir(parents=True);episodes.to_csv(output/'episodes.csv',index=False);manifest.to_csv(output/'chart_manifest.csv',index=False);s['residual'].to_csv(output/'residual_open_positions.csv',index=False)
    (output/'records.json').write_text(json.dumps(renderer['_json_safe'](records),ensure_ascii=False,separators=(',',':'),allow_nan=False));(output/'summary.json').write_text(json.dumps(renderer['_json_safe'](summary),ensure_ascii=False,indent=2,allow_nan=False));(output/'index.html').write_text(page)
    print(json.dumps({'html':str(output/'index.html'),'completed_cycles':len(records),'residual':len(s['residual']),'diagnostic':s['diagnostic'],'bytes':len(page.encode())}),flush=True)

def attach_attribution(profile:str)->None:
    """Add root's frozen post-hoc labels to the existing canonical explanation field."""
    output=OUT/f'recap_{profile}';source=OUT/'trade_attribution'/('NH_episodes.csv' if profile=='no_ai_no_half_r' else 'H_episodes.csv')
    source_hash=sha(source);labels=pd.read_csv(source).set_index('first_trade_id',verify_integrity=True)
    records=read(output/'records.json');summary=read(output/'summary.json');page=(output/'index.html').read_text()
    old_records=json.dumps(records,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    old_summary=json.dumps(summary,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    names={'static18_boundary':'静态18边界','fixed_fu':'固定fu','monthly_ai_ranked':'月池排名'}
    for record in records:
        meta=record['meta'];row=labels.loc[meta['open_trade_id']]
        assert row.source_run==summary['source_bundle'] and row.vt_symbol==meta['vt_symbol'] and row.entry_date==meta['entry_date']
        allowed='放行' if int(row.replayed_ai_allowed)==1 else '拦截'
        complete=str(row.entry_scan_complete).lower()=='true' and str(row.all_cycle_ordinary_anchors_complete).lower()=='true'
        rank=float(row.replayed_rank) if pd.notna(row.replayed_rank) else None
        rank_label=f'{rank:g}' if rank is not None else 'N/A'
        detail=f'当时AI会{allowed}｜{names[row.eligibility_class]}｜排名{rank_label}｜'+('本笔请求覆盖完整' if complete else '本笔存在分钟/首锚缺口')+'（事后标记，非反事实收益）'
        meta['selection_basis']+='｜'+detail
        meta['ai_attribution']={'allowed':int(row.replayed_ai_allowed),'eligibility_class':row.eligibility_class,'rank':rank,'local_coverage_complete':complete,'scope':'posthoc_observed_trade_not_counterfactual'}
    summary.update(attribution_csv=str(source),attribution_sha256=source_hash,attribution_episodes=len(records))
    new_records=json.dumps(records,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    new_summary=json.dumps(summary,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    old='const records='+old_records+'; const summary='+old_summary+';'
    assert page.count(old)==1
    page=page.replace(old,'const records='+new_records+'; const summary='+new_summary+';',1)
    assert sha(source)==source_hash
    (output/'records.json').write_text(json.dumps(records,ensure_ascii=False,separators=(',',':'),allow_nan=False));(output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False));(output/'index.html').write_text(page)
    print(json.dumps({'profile':profile,'attribution_attached':len(records),'source_sha256':source_hash}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=PROFILES,required=True);parser.add_argument('--attach-attribution',action='store_true');args=parser.parse_args()
    attach_attribution(args.profile) if args.attach_attribution else generate(args.profile)
