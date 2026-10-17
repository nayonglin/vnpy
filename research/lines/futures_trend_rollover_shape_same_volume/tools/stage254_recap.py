"""Stage254 frozen 2025-start recap; canonical charts, no engine or network."""
from __future__ import annotations
import argparse,ast,html,json,sqlite3,shutil
from pathlib import Path
from datetime import datetime
import pandas as pd
from stage248_recap_html import ROOT,LINE,CANONICAL,RENDERER_SHA,sha,read,close,load_renderer,validate_output
from stage253_recap import episode_rows,MAPPING,REQUIRED as BASE_REQUIRED

BASE=LINE/'outputs/stage254_formal_2025'
REQUIRED=BASE_REQUIRED+['statistics_audit/complete_episodes.csv','statistics_audit/retry_links.csv','execution_anchor_requests.csv']

def require_bundle(run:Path)->None:
    missing=[name for name in REQUIRED if not (run/name).is_file()]
    if missing:raise ValueError(f'Incomplete frozen bundle: {missing}')

def optional_table(path:Path,columns:list[str])->pd.DataFrame:
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame(columns=columns)

def cycle_rows(cycles:pd.DataFrame,trades:pd.DataFrame)->pd.DataFrame:
    result=episode_rows(cycles,trades)
    by_id=cycles.set_index('first_trade_id',verify_integrity=True)
    result['root_id']=result.open_trade_id.map(by_id.root_id)
    result['is_retry']=result.open_trade_id.map(by_id.is_retry).map(lambda value:str(value).lower()=='true')
    for i,row in result.iterrows():
        result.at[i,'selection_basis']+=f'｜{"0.5R重试" if row.is_retry else "初次开仓"}｜交易段 root={row.root_id}'
    return result

def load_bundle(run:Path)->dict:
    require_bundle(run)
    metrics=read(run/'metrics.json');stats=read(run/'statistics_audit/summary.json');provenance=read(run/'run_provenance.json');inputs=read(run/'input_manifest.json')
    if metrics['start']!='2025-01-01' or metrics['end']!='2026-10-14':raise ValueError('Unexpected Stage254 interval')
    close(metrics['account_capital'],150000.,'fresh account capital')
    assert provenance['completed_at'] and provenance['all_data_and_model_inputs_unchanged_during_run']
    assert sha(run/'input_manifest.json')==provenance['input_manifest_sha256']
    for filename,expected in stats['source_hashes'].items():assert sha(run/filename)==expected
    for relative in [Path('.vntrader/database.db'),MAPPING]:assert sha(ROOT/relative)==inputs[str(relative)]
    trades=pd.read_csv(run/'trades.csv').set_index('trade_id',verify_integrity=True);daily=pd.read_csv(run/'daily.csv',parse_dates=['date'])
    cycles=pd.read_csv(run/'statistics_audit/complete_cycles.csv');residual=optional_table(run/'statistics_audit/open_positions.csv',['trade_ids','net_mtm'])
    groups=optional_table(run/'statistics_audit/complete_episodes.csv',['root_id','net_pnl']);retry=optional_table(run/'statistics_audit/retry_links.csv',['root_id','retry_id'])
    assert daily.date.is_monotonic_increasing and not daily.date.duplicated().any()
    assert daily.date.between(metrics['start'],metrics['end']).all()
    assert set(trades.variant)=={metrics['variant']} and set(daily.variant)=={metrics['variant']}
    close(len(trades),metrics['total_trade_count'],'fill count');close(len(cycles),stats['closed_cycles'],'cycles');close(len(groups),stats['closed_episodes'],'episodes');close(len(residual),stats['end_open_contracts'],'residual')
    close(daily.account_equity.iloc[-1],metrics['end_equity'],'end equity');close(daily.net_pnl.sum(),metrics['end_equity']-metrics['account_capital'],'daily pnl')
    close(cycles.net_pnl.sum()+residual.net_mtm.sum(),daily.net_pnl.sum(),'closed plus remaining MTM');close(daily.slippage.sum(),metrics['total_slippage'],'slippage')
    consumed=[]
    for value in pd.concat([cycles.trade_ids,residual.trade_ids]):consumed.extend(ast.literal_eval(value))
    assert len(consumed)==len(set(consumed))==len(trades) and set(consumed)==set(trades.index)
    anchors=pd.read_csv(run/'execution_anchor_requests.csv');anchor_missing=int(anchors.coverage_status.ne('complete').sum())
    return dict(run=run,metrics=metrics,stats=stats,provenance=provenance,daily=daily,trades=trades,cycles=cycles,residual=residual,groups=groups,retry=retry,anchor_missing=anchor_missing,incomplete=bool(stats['unique_missing_minutes'] or anchor_missing),diagnostic=bool(provenance['diagnostic_incomplete_minutes']),source_sha256={name:sha(run/name) for name in REQUIRED})

def generate(run:Path,output:Path=BASE/'recap')->None:
    output=validate_output(output,BASE);s=load_bundle(run);metrics=s['metrics'];episodes=cycle_rows(s['cycles'],s['trades'])
    mapping=pd.read_csv(ROOT/MAPPING,parse_dates=['date']).dropna(subset=['main_contract_vt']);mapping=mapping[mapping.date.le(metrics['end'])]
    with sqlite3.connect(f'file:{ROOT}/.vntrader/database.db?mode=ro',uri=True) as db:
        bars=pd.read_sql_query("SELECT symbol || '.' || exchange AS vt_symbol, datetime AS date, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume FROM dbbardata WHERE interval='d' ORDER BY datetime",db)
    bars.date=pd.to_datetime(bars.date).dt.normalize();bars=bars[bars.date.le(metrics['end'])]
    cache={key:frame.drop(columns='vt_symbol').reset_index(drop=True) for key,frame in bars.groupby('vt_symbol',sort=False)}
    def contract_daily(symbol):
        if symbol not in cache:raise RuntimeError(f'Missing exact contract: {symbol}')
        return cache[symbol]
    renderer=load_renderer({'_contract_daily':contract_daily,'_daily_from_existing_minute_files':lambda *args:pd.DataFrame()})
    context={};minute_dates={}
    for i,row in enumerate(episodes.itertuples(index=False)):
        context[row.open_trade_id],minute_dates[row.open_trade_id]=renderer['_context_daily'](row,mapping,cache,allow_daily_download=False,allow_noncritical_daily_gaps=True,data_end=pd.Timestamp(metrics['end']))
        if (i+1)%25==0:print(f'context {i+1}/{len(episodes)}',flush=True)
    records,manifest=renderer['_records'](episodes,context,minute_dates,pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume']))
    for record,row in zip(records,episodes.itertuples(index=False)):
        for key in ['entry_price','exit_price','realized_pnl','volume']:close(record['meta'][key],getattr(row,key),f'rendered {key}')
        assert record['meta']['entry_source']==row.vt_symbol==record['meta']['exit_source']
        assert record['meta']['entry_date']==str(row.entry_date.date()) and record['meta']['exit_date']==str(row.exit_date.date())
        record['meta'].update(is_retry=bool(row.is_retry),root_id=str(row.root_id))
    missing=int(s['stats']['unique_missing_minutes']);status='正式参数＋现有数据诊断，严格数据验收未通过' if s['diagnostic'] or s['incomplete'] else '冻结独立回测；验收状态以运行报告为准'
    warning=f'{status}。2025-01-01起空仓15万元，不是全周期曲线截取；正式配置AI资格与0.5R开启，C2保留。入场路径去重缺{missing:,}分钟，普通首锚缺{s["anchor_missing"]}次。'
    warning+=' 只使用本地行情；本次15分钟图未提供，未填补缺失。研究回测不是生产收益或部署资格。'
    summary=dict(source_label='Stage254 正式参数 · 2025独立起点',source_version=metrics['variant'],source_warning=warning,page_title='正式参数独立回测复盘 · 2025-01-01—2026-10-14',episode_scope='all',coverage_note=f'{len(episodes)}个完整持仓周期，含{int(episodes.is_retry.sum())}个重试周期；合并重试后{s["stats"]["closed_episodes"]}个已完成交易段，期末另{len(s["residual"])}个未平仓合约。',footer_scope='每个初次/重试持仓周期均单独保留，不伪造连续持仓或最终退出。',rank_basis='realized_pnl',source_bundle=str(run.resolve()),source_sha256=s['source_sha256'],source_provenance=s['provenance'],renderer_path=str(CANONICAL),renderer_sha256=RENDERER_SHA,frozen_metrics=metrics,frozen_statistics=s['stats'],completed_cycle_count=len(episodes),completed_retry_cycles=int(episodes.is_retry.sum()),completed_signal_episodes=len(s['groups']),residual_open_contracts=len(s['residual']),residual_net_mtm=float(s['residual'].net_mtm.sum()),profit_count=int(episodes.result_type.eq('profit').sum()),loss_count=int(episodes.result_type.eq('loss').sum()),flat_count=int(episodes.result_type.eq('flat').sum()),data_incomplete=s['incomplete'],missing_entry_minutes=missing,missing_ordinary_anchor_requests=s['anchor_missing'],minute_chart_available=False,rerun=False,market_download=False,training=False,production_access=False,generated_at=datetime.now().astimezone().isoformat(),proxy_episode_count=int(manifest.context_fallback_days.gt(0).sum()),context_gap_episode_count=int(manifest.missing_context_dates.map(bool).sum()))
    summary.update(diagnostic_mode=s['diagnostic'],strict_data_accepted=False if s['diagnostic'] or s['incomplete'] else None)
    if s['diagnostic']:summary['page_title']='正式参数＋现有数据诊断复盘 · 2025-01-01—2026-10-14'
    page=renderer['_html'](records,summary);rate=s['stats']['periods']['all']['entry_cohort_complete_cycles']['win_rate_pct'];group_rate=s['stats']['periods']['all']['entry_cohort_complete_episodes']['win_rate_pct']
    residual_html=s['residual'].to_html(index=False,border=0) if len(s['residual']) else '<p>期末没有未平仓合约。</p>'
    overview=f'<section class="panel" style="padding:18px;margin:16px 0"><h2>冻结独立回测总览</h2><p>150,000 → <b>{metrics["end_equity"]:,.2f}元</b>；总收益{metrics["total_return_pct"]:.2f}%；最大回撤{metrics["max_dd_pct"]:.2f}%；Sharpe {metrics["sharpe"]:.4f}；滑点{metrics["total_slippage"]:,.0f}元。</p><p>完整周期勝率{rate:.2f}%；合并重试交易段胜率{group_rate:.2f}%。期末未平仓净MTM {summary["residual_net_mtm"]:,.2f}元，未计入已完成周期胜率。</p><details><summary>未平仓持仓</summary>{residual_html}</details><details><summary>合并重试的完整交易段</summary>{s["groups"].to_html(index=False,border=0)}</details><p>图表日期使用交易日，实际前夜成交时间在逐笔说明中保留。上市/退市之外主力代理背景由灰线标识，不能视为策略信号；R未做唯一风险绑定，显示N/A。均线和缺失历史不补造。</p></section>'
    banner='<div role="alert" style="padding:16px;border:2px solid #b42318;background:#fff4ed"><b>'+html.escape(warning)+'</b></div>'
    page=page.replace('<div class="toolbar">',banner+overview+'<div class="toolbar">',1).replace('<option value="profit_tail">盈利尾部</option>','').replace('<option value="loss_tail">亏损尾部</option>','')
    for name,expected in s['source_sha256'].items():assert sha(run/name)==expected
    output.mkdir(parents=True);episodes.to_csv(output/'episodes.csv',index=False);manifest.to_csv(output/'chart_manifest.csv',index=False)
    for name in ['open_positions.csv','complete_episodes.csv','retry_links.csv']:shutil.copy2(run/'statistics_audit'/name,output/name)
    (output/'records.json').write_text(json.dumps(renderer['_json_safe'](records),ensure_ascii=False,separators=(',',':'),allow_nan=False));(output/'summary.json').write_text(json.dumps(renderer['_json_safe'](summary),ensure_ascii=False,indent=2,allow_nan=False));(output/'index.html').write_text(page)
    print(json.dumps({'html':str(output/'index.html'),'cycles':len(records),'retry_cycles':summary['completed_retry_cycles'],'remaining_contracts':len(s['residual']),'data_incomplete':s['incomplete']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True,help='Explicit completed frozen run; never infer the failed strict run.');parser.add_argument('--output',type=Path,default=BASE/'recap');args=parser.parse_args();generate(args.run,args.output)
