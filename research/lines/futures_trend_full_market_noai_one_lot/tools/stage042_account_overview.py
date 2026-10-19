"""Display a frozen budget-cap1 account; no strategy imports or financial replay.

The approved Stage032 Plotly block is reused by AST selection (not copied or
executed as a script). Everything outside that block is a new source adapter.
"""
from pathlib import Path
import argparse
import ast
from datetime import datetime
import hashlib
import html
import json
import os
import sys
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PLOT_SOURCE=Path(__file__).with_name('stage032_account_overview.py')
BUDGET_FLAGS=('native_risk_budget_restored','one_lot_is_maximum_not_fixed','next_open_risk_recheck')
BUDGET_DISCLOSURE=('原生风险预算已恢复：fixed_size=0先运行原预算定仓，预算不允许1手则不开仓；'
    '允许后最多1手。所有新开（含移仓重开）于真实开盘复核原信号预算及开盘重算预算，取较小值；'
    '该预算不保证跳空退出时的实际亏损上限。此前固定1手结果不代表此口径。')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def require(condition,reason):
    if not condition:raise ValueError(reason)


def safe_member(root,name):
    relative=Path(name)
    require(not relative.is_absolute() and '..' not in relative.parts,'unsafe_hash_path:'+name)
    p=(root/relative).resolve()
    require(p.is_relative_to(root.resolve()) and p.is_file(),'unsafe_hash_path:'+name)
    return p


def check_output(source,parent,output):
    source,parent,output=map(lambda p:Path(p).resolve(),(source,parent,output))
    for protected in (source,parent):
        require(not output.is_relative_to(protected) and not protected.is_relative_to(output),'output_overlaps_input')
    require(not output.exists(),'output_already_exists')


def verify_hashes(source,manifest):
    bound={}
    require(isinstance(manifest.get('hashes'),dict) and manifest['hashes'],'missing_source_hashes')
    for name,expected in manifest['hashes'].items():
        p=safe_member(source,name);actual=sha(p)
        require(actual==expected,'source_hash_mismatch:'+name);bound[name]=actual
    for name,expected in manifest.get('code_snapshot_hashes',{}).items():
        p=safe_member(source,'code_snapshot/'+name);actual=sha(p)
        require(actual==expected,'snapshot_hash_mismatch:'+name);bound['code_snapshot/'+name]=actual
    for name in ('daily.csv','summary.json','closed_episodes.csv','residual_open_positions.json','trades.csv'):
        require(name in bound,'missing_source_binding:'+name)
    return bound


def load_bundle(source,parent):
    source,parent=Path(source).resolve(),Path(parent).resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    parent_summary=json.loads((parent/'summary.json').read_text())
    manifest_hash=sha(source/'manifest.json')
    require(manifest_hash==parent_summary['source_manifest_sha256'],'parent_manifest_mismatch')
    require(manifest['run_id']==source.name,'run_id_directory_mismatch')
    bound=verify_hashes(source,manifest)
    metrics=json.loads((source/'summary.json').read_text())
    require(metrics==parent_summary['backtest_metrics'],'parent_metrics_mismatch')
    for flag in BUDGET_FLAGS:
        require(manifest.get(flag) is True and metrics.get(flag) is True,'budget_policy:'+flag)
    p=manifest['parameters']
    require(p.get('fixed_size')==0 and p.get('max_position_size')==1,'budget_policy:sizing_parameters')
    require(manifest.get('position_count_limit_removed') is True and metrics.get('position_count_limit_removed') is True,'budget_policy:position_limit')
    require(metrics['mode']==manifest['mode']=='daily-proxy','unsupported_display_mode')
    episodes=pd.read_csv(source/'closed_episodes.csv')
    require(len(episodes)==metrics['completed_episodes'],'episode_count_mismatch')
    residual=json.loads((source/'residual_open_positions.json').read_text())
    require(isinstance(residual,list) and len(residual)==metrics['residual_open_positions'],'residual_count_mismatch')
    trades=pd.read_csv(source/'trades.csv')
    if 'total_trade_count' in metrics:require(len(trades)==metrics['total_trade_count'],'trade_count_mismatch')
    d=pd.read_csv(source/'daily.csv');dates=pd.to_datetime(d.date,errors='raise')
    require(len(d)>0 and dates.is_monotonic_increasing and not dates.duplicated().any(),'daily_dates_invalid')
    require(len(d)==metrics['total_days'] and d.date.iloc[-1]==metrics['analysis_end'],'daily_interval_mismatch')
    require(dates.iloc[0]>=pd.Timestamp(metrics['analysis_start']),'daily_before_analysis_start')
    equity=pd.to_numeric(d.equity,errors='raise');capital=float(metrics['initial_capital'])
    require(np.isfinite(equity).all() and equity.gt(0).all() and np.isfinite(capital) and capital>0,'invalid_equity')
    require(np.allclose(equity,capital+d.net_pnl.cumsum(),atol=1e-5,rtol=0),'equity_net_pnl_mismatch')
    require(np.allclose(equity,d.balance,atol=1e-6,rtol=0),'equity_balance_mismatch')
    peak=equity.cummax().clip(lower=capital);dd_amount=equity-peak;dd_pct=(equity/peak-1)*100
    for col,series in [('highlevel',peak),('drawdown',dd_amount),('ddpercent',dd_pct)]:
        require(np.allclose(d[col],series,atol=1e-7,rtol=0),'daily_metric_mismatch:'+col)
    for key,value,tolerance in [('end_balance',equity.iloc[-1],1e-6),('total_return',(equity.iloc[-1]/capital-1)*100,1e-8),('max_ddpercent',dd_pct.min(),1e-8),('max_drawdown',dd_amount.min(),1e-6)]:
        require(abs(float(metrics[key])-value)<tolerance,'summary_metric_mismatch:'+key)
    trough=int(dd_pct.idxmin())
    peak_indices=equity.loc[:trough][equity.loc[:trough].eq(peak.iloc[trough])].index
    peak_date=d.date.iloc[int(peak_indices[-1])] if len(peak_indices) else 'initial_capital'
    residual_dates=sorted({str(r.get('date') or r.get('datetime',''))[:10] for r in residual})
    facts=dict(run_id=manifest['run_id'],start=d.date.iloc[0],end=d.date.iloc[-1],analysis_start=metrics['analysis_start'],
        points=len(d),initial_capital=capital,end_equity=float(equity.iloc[-1]),total_return_pct=metrics['total_return'],
        max_drawdown_pct=float(dd_pct.min()),max_drawdown_amount=float(dd_amount.min()),max_drawdown_peak_date=peak_date,
        max_drawdown_trough_date=d.date.iloc[trough],peak_equity_for_max_dd=float(peak.iloc[trough]),
        trough_equity_for_max_dd=float(equity.iloc[trough]),ending_drawdown_pct=float(dd_pct.iloc[-1]),sharpe_ratio=metrics['sharpe_ratio'],
        completed_episodes=len(episodes),total_fills=len(trades),residual_open_positions=len(residual),residual_open_dates=residual_dates,
        residual_positions=residual,mode=metrics['mode'],budget_restoration={k:True for k in BUDGET_FLAGS},budget_disclosure=BUDGET_DISCLOSURE,
        strategy_rerun=False,market_download=False,production_access=False,created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        source_directory=str(source),parent_recap_directory=str(parent),source_manifest_sha256=manifest_hash,
        source_daily_sha256=bound['daily.csv'],source_summary_sha256=bound['summary.json'],source_hashes=bound,
        parent_recap_summary_sha256=sha(parent/'summary.json'),generator_sha256=sha(Path(__file__)),plot_source_sha256=sha(PLOT_SOURCE),
        source_boundaries=metrics.get('boundaries',[]))
    return dict(source=source,parent=parent,manifest=manifest,metrics=metrics,d=d,dates=dates,equity=equity,capital=capital,
                peak=peak,dd_amount=dd_amount,dd_pct=dd_pct,trough=trough,facts=facts)


def make_plot(bundle):
    # Reuse exactly the approved plotting statements, without running its main,
    # data adapter, hard-coded labels, output writes, or any strategy code.
    tree=ast.parse(PLOT_SOURCE.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    statements=[];active=False
    for node in main.body:
        targets=[x.id for x in node.targets if isinstance(x,ast.Name)] if isinstance(node,ast.Assign) else []
        if 'x' in targets:active=True
        if active:statements.append(node)
        if active and 'plot' in targets:break
    require(active and 'plot' in targets,'stage032_plot_block_not_found')
    scope={**bundle,'go':go,'make_subplots':make_subplots}
    exec(compile(ast.Module(body=statements,type_ignores=[]),str(PLOT_SOURCE),'exec'),scope)
    return scope['fig'],scope['plot']


def make_page(bundle,plot,output):
    f=bundle['facts'];m=bundle['metrics'];esc=html.escape
    boundary=(f'日线近似研究；日内C2/C9止损与重试、供需过滤按授权停用。权益包含未平仓浮盈亏、手续费与滑点；'
              f'期末{f["residual_open_positions"]}项仓位未强制平仓。非完整C9或实盘业绩。')
    f['boundaries']=boundary
    peak_label='初始本金' if f['max_drawdown_peak_date']=='initial_capital' else f['max_drawdown_peak_date']
    parent_link=esc(os.path.relpath(bundle['parent']/'index.html',Path(output).resolve()),quote=True)
    cards=''.join(f'<div><span>{esc(label)}</span><strong>{esc(value)}</strong></div>' for label,value in [
        ('初始资金',f'{f["initial_capital"]/10000:.2f}万元'),('期末权益',f'{f["end_equity"]/10000:.2f}万元'),
        ('总收益',f'{f["total_return_pct"]:.2f}%'),('最大回撤',f'{f["max_drawdown_pct"]:.2f}%'),('Sharpe',f'{f["sharpe_ratio"]:.4f}')])
    details=esc(json.dumps(f['residual_positions'],ensure_ascii=False,indent=2))
    full_boundaries=''.join('<li>'+esc(str(s))+'</li>' for s in f['source_boundaries'])
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>全市场无AI风险预算最多一手 · 资金与回撤</title><style>body{font:15px -apple-system,BlinkMacSystemFont,Arial,sans-serif;color:#24364a;background:#f4f7fa;margin:0}.wrap{max-width:1250px;margin:auto;padding:28px 24px}h1{font-size:25px;margin:0 0 10px}.muted{color:#607286;line-height:1.7}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:22px 0}.cards div{background:white;border:1px solid #e0e7ee;border-radius:9px;padding:17px}.cards span{display:block;color:#66798b;margin-bottom:8px}.cards strong{font-size:23px}.chart{background:white;border-radius:10px;padding:15px 6px}.policy{background:#e9f4f6;border-left:3px solid #147d92;padding:12px 15px;margin-top:14px;line-height:1.7}a{color:#147d92}footer{margin-top:18px;font-size:13px;line-height:1.8}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:650px){.cards{grid-template-columns:repeat(2,1fr)}.wrap{padding:20px 10px}}</style>'
      '<main class="wrap"><h1>整体资金曲线与回撤</h1><div class="muted">全市场 · 无AI选品 · 原风险预算后最多1手 · 无4品种上限<br>'
      f'{esc(f["start"])}—{esc(f["end"]) }，{f["points"]}个真实日末权益点。拖动框选可缩放，两图日期联动；工具栏可重置。</div>'
      f'<div class="policy">{esc(BUDGET_DISCLOSURE)}</div><section class="cards">{cards}</section><section class="chart">{plot}</section><footer>{esc(boundary)}'
      f'<br>回撤 =（当日总权益 ÷ 截至当日历史最高权益 − 1）× 100%，历史最高权益包含初始本金。最大回撤：{esc(peak_label)}高点 → {esc(f["max_drawdown_trough_date"])}低点；期末仍距高点{f["ending_drawdown_pct"]:.2f}%。'
      f'<br><a href="equity_drawdown.png">查看/保存高清图</a> · <a href="{parent_link}">打开{f["completed_episodes"]}笔完整交易逐笔复盘</a>'
      f'<br>期末残仓开仓日期：{esc("、".join(f["residual_open_dates"]) or "无")}。<details><summary>残仓清单与完整研究边界</summary><pre>{details}</pre><ul>{full_boundaries}</ul></details>'
      f'<br>冻结来源：{esc(f["run_id"])}；manifest SHA256：{f["source_manifest_sha256"]}。每日权益 SHA256：{f["source_daily_sha256"]}。<br><a href="summary.json">全部来源与输出哈希</a> · <a href="equity_drawdown.csv">每日权益CSV</a>。未重跑策略、未下载行情、未访问生产。</footer></main></html>')


def save_png(bundle,output):
    sys.path.append('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.font_manager import FontProperties
    fontpath='/System/Library/Fonts/STHeiti Medium.ttc';font_manager.fontManager.addfont(fontpath);font=FontProperties(fname=fontpath)
    plt.rcParams.update({'axes.unicode_minus':False,'font.family':font.get_name(),'figure.facecolor':'#f7f9fb','axes.spines.top':False,'axes.spines.right':False})
    f=bundle['facts'];dates=bundle['dates'];y=bundle['equity']/10000;high=bundle['peak']/10000;dd=bundle['dd_pct'];trough=bundle['trough']
    picture,axes=plt.subplots(2,1,figsize=(14,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1]},layout='constrained')
    picture.suptitle('全市场无AI｜风险预算最多一手｜整体资金与回撤',fontproperties=font,fontsize=18)
    axes[0].plot(dates,y,color='#147d92',lw=1.5,label='日末总权益（含成本）');axes[0].plot(dates,high,color='#a4afbd',lw=.9,ls=':',label='历史高点')
    axes[0].axhline(f['initial_capital']/10000,color='#b7c2cc',ls='--',lw=.9,label=f'{f["initial_capital"]/10000:g}万本金')
    axes[0].scatter(dates.iloc[-1],y.iloc[-1],color='#147d92',s=20,zorder=3)
    axes[0].annotate(f'期末 {y.iloc[-1]:.2f} 万元',xy=(dates.iloc[-1],y.iloc[-1]),xytext=(-110,18),textcoords='offset points',fontproperties=font,color='#126c7e',fontsize=11)
    axes[0].set_ylabel('总权益（万元）',fontproperties=font);axes[0].legend(loc='upper left',frameon=False,prop=font,ncol=3);axes[0].grid(alpha=.16)
    axes[1].fill_between(dates,dd,0,color='#c9414a',alpha=.16);axes[1].plot(dates,dd,color='#c9414a',lw=1)
    axes[1].scatter(dates.iloc[trough],dd.iloc[trough],color='#962d37',s=23,zorder=3)
    axes[1].annotate(f'最大回撤 {dd.iloc[trough]:.2f}%\n{f["max_drawdown_trough_date"]}',xy=(dates.iloc[trough],dd.iloc[trough]),xytext=(-140,8),textcoords='offset points',fontproperties=font,fontsize=10,color='#962d37',arrowprops=dict(arrowstyle='-',color='#962d37'))
    axes[1].set_ylim(float(dd.min())*1.18,2);axes[1].set_ylabel('回撤（%）',fontproperties=font);axes[1].grid(alpha=.16)
    axes[1].set_xlabel(f'{f["start"]}—{f["end"]}｜风险预算恢复/开盘复核｜日线近似｜含{f["residual_open_positions"]}项期末仓浮盈亏',fontproperties=font,fontsize=10)
    axes[0].set_title(f'总收益 {f["total_return_pct"]:.2f}%   |   Sharpe {f["sharpe_ratio"]:.4f}   |   冻结每日权益，无策略重跑',fontproperties=font,fontsize=11,loc='left',color='#65778a')
    picture.savefig(output/'equity_drawdown.png',dpi=160);plt.close(picture)


def generate(source,parent,output):
    source,parent,output=map(lambda p:Path(p).resolve(),(source,parent,output));check_output(source,parent,output)
    bundle=load_bundle(source,parent);fig,plot=make_plot(bundle);page=make_page(bundle,plot,output)
    output.mkdir(parents=True)
    save_png(bundle,output)
    (output/'index.html').write_text(page,encoding='utf-8');(output/'figure.json').write_text(fig.to_json(),encoding='utf-8')
    pd.DataFrame({'date':bundle['d'].date,'equity':bundle['equity'],'high_watermark':bundle['peak'],
                  'drawdown_amount':bundle['dd_amount'],'drawdown_pct':bundle['dd_pct']}).to_csv(output/'equity_drawdown.csv',index=False)
    require(sha(source/'manifest.json')==bundle['facts']['source_manifest_sha256'],'source_changed_during_render')
    require(sha(parent/'summary.json')==bundle['facts']['parent_recap_summary_sha256'],'parent_changed_during_render')
    require(verify_hashes(source,bundle['manifest'])==bundle['facts']['source_hashes'],'source_changed_during_render')
    facts=bundle['facts'];facts['artifact_sha256']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    facts['artifact_bytes']={p.name:p.stat().st_size for p in output.iterdir() if p.is_file()}
    (output/'summary.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    return facts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();print(json.dumps(generate(args.source,args.parent,args.output),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
