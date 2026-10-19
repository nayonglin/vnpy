"""Display only: hash-bound account equity and drawdown, without strategy imports."""
from pathlib import Path
import hashlib,html,json,sys
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LINE=Path(__file__).resolve().parents[1]
SOURCE=LINE/'outputs/run_20261018_lifecycle_unlimited_v2'
PARENT=LINE/'outputs/recap_20261018_lifecycle_unlimited_v2_reviewed'
OUTPUT=LINE/'outputs/overview_20261019_lifecycle_unlimited_v2'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    if OUTPUT.exists():raise FileExistsError(OUTPUT)
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    parent=json.loads((PARENT/'summary.json').read_text())
    assert sha(SOURCE/'manifest.json')==parent['source_manifest_sha256']
    for name in ('daily.csv','summary.json'):
        assert sha(SOURCE/name)==manifest['hashes'][name],name
    metrics=json.loads((SOURCE/'summary.json').read_text());assert metrics==parent['backtest_metrics']
    d=pd.read_csv(SOURCE/'daily.csv');dates=pd.to_datetime(d.date,errors='raise')
    assert dates.is_monotonic_increasing and not dates.duplicated().any()
    assert len(d)==metrics['total_days'] and d.date.iloc[-1]==metrics['analysis_end']
    equity=pd.to_numeric(d.equity,errors='raise');capital=float(metrics['initial_capital'])
    assert np.isfinite(equity).all() and equity.gt(0).all()
    assert np.allclose(equity,capital+d.net_pnl.cumsum(),atol=1e-5,rtol=0)
    assert np.allclose(equity,d.balance,atol=1e-6,rtol=0)
    peak=equity.cummax().clip(lower=capital);dd_amount=equity-peak;dd_pct=(equity/peak-1)*100
    for col,series in [('highlevel',peak),('drawdown',dd_amount),('ddpercent',dd_pct)]:
        assert np.allclose(d[col],series,atol=1e-7,rtol=0),col
    assert abs(equity.iloc[-1]-metrics['end_balance'])<1e-6
    assert abs((equity.iloc[-1]/capital-1)*100-metrics['total_return'])<1e-8
    assert abs(dd_pct.min()-metrics['max_ddpercent'])<1e-8
    assert abs(dd_amount.min()-metrics['max_drawdown'])<1e-6
    trough=int(dd_pct.idxmin());peak_idx=int(equity.loc[:trough][equity.loc[:trough].eq(peak.iloc[trough])].index[-1])
    facts={'run_id':manifest['run_id'],'start':d.date.iloc[0],'end':d.date.iloc[-1],
        'points':len(d),'initial_capital':capital,'end_equity':float(equity.iloc[-1]),
        'total_return_pct':metrics['total_return'],'max_drawdown_pct':float(dd_pct.min()),
        'max_drawdown_amount':float(dd_amount.min()),'max_drawdown_peak_date':d.date.iloc[peak_idx],
        'max_drawdown_trough_date':d.date.iloc[trough],'peak_equity_for_max_dd':float(peak.iloc[trough]),
        'trough_equity_for_max_dd':float(equity.iloc[trough]),'ending_drawdown_pct':float(dd_pct.iloc[-1]),
        'sharpe_ratio':metrics['sharpe_ratio'],'residual_open_positions':metrics['residual_open_positions'],
        'mode':metrics['mode'],'strategy_rerun':False,'market_download':False,'production_access':False,
        'created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'source_directory':str(SOURCE),'source_manifest_sha256':sha(SOURCE/'manifest.json'),
        'source_daily_sha256':sha(SOURCE/'daily.csv'),'source_summary_sha256':sha(SOURCE/'summary.json'),
        'parent_recap_summary_sha256':sha(PARENT/'summary.json'),'generator_sha256':sha(Path(__file__))}
    x=d.date.tolist();y=(equity/10000).tolist();high=(peak/10000).tolist();dd=dd_pct.tolist()
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.12,row_heights=[.64,.36],
        subplot_titles=['整体资金曲线 · 含成本的日末总权益','回撤曲线 · 相对此前权益高点'])
    fig.add_trace(go.Scatter(x=x,y=y,name='总权益',line=dict(color='#147d92',width=2),hovertemplate='%{x}<br>总权益 %{y:.2f} 万元<extra></extra>'),row=1,col=1)
    fig.add_trace(go.Scatter(x=x,y=high,name='历史高点',line=dict(color='#94a3b8',width=1,dash='dot'),hovertemplate='%{x}<br>历史高点 %{y:.2f} 万元<extra></extra>'),row=1,col=1)
    fig.add_trace(go.Scatter(x=x,y=dd,name='回撤',fill='tozeroy',fillcolor='rgba(201,65,74,.16)',line=dict(color='#c9414a',width=1.5),hovertemplate='%{x}<br>回撤 %{y:.2f}%<extra></extra>'),row=2,col=1)
    fig.add_trace(go.Scatter(x=[x[trough]],y=[dd[trough]],name='最大回撤',mode='markers',marker=dict(color='#962d37',size=8),hovertemplate='%{x}<br>最大回撤 %{y:.2f}%<extra></extra>'),row=2,col=1)
    fig.add_hline(y=capital/10000,line_dash='dash',line_color='#bbc4cf',row=1,col=1)
    fig.update_layout(template='plotly_white',height=730,margin=dict(l=70,r=35,t=50,b=45),
        font=dict(family='-apple-system,BlinkMacSystemFont,Arial,sans-serif',color='#223344'),
        hovermode='x unified',legend=dict(orientation='h',y=1.12,x=0),dragmode='zoom')
    fig.update_yaxes(title_text='万元',row=1,col=1)
    fig.update_yaxes(title_text='回撤 %',ticksuffix='%',range=[float(dd_pct.min())*1.18,2],row=2,col=1)
    fig.update_xaxes(type='date',showgrid=True)
    fig.update_annotations(font_size=14)
    plot=fig.to_html(full_html=False,include_plotlyjs=True,div_id='account-overview',config={'responsive':True,'displaylogo':False})
    boundary='日线近似研究：日内C2/C9止损与重试、供需过滤按原授权停用。权益包含未平仓浮盈亏及手续费、滑点；期末12项正常仓位未强制平仓。非完整C9或实盘业绩。'
    cards=''.join(f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>' for label,value in [
        ('初始资金','100.00万元'),('期末权益',f'{equity.iloc[-1]/10000:.2f}万元'),
        ('总收益',f'{metrics["total_return"]:.2f}%'),('最大回撤',f'{dd_pct.min():.2f}%'),('Sharpe',f'{metrics["sharpe_ratio"]:.4f}')])
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全市场无AI一手研究 · 资金与回撤</title><style>body{font:15px -apple-system,BlinkMacSystemFont,Arial,sans-serif;color:#24364a;background:#f4f7fa;margin:0}.wrap{max-width:1250px;margin:auto;padding:28px 24px}h1{font-size:25px;margin:0 0 10px}.muted{color:#607286;line-height:1.7}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:22px 0}.cards div{background:white;border:1px solid #e0e7ee;border-radius:9px;padding:17px}.cards span{display:block;color:#66798b;margin-bottom:8px}.cards strong{font-size:23px}.chart{background:white;border-radius:10px;padding:15px 6px}a{color:#147d92}footer{margin-top:18px;font-size:13px;line-height:1.8}@media(max-width:650px){.cards{grid-template-columns:repeat(2,1fr)}.wrap{padding:20px 10px}}</style><main class="wrap"><h1>整体资金曲线与回撤</h1><div class="muted">全市场 · 无AI选品 · 100万起始资金 · 每品种最多1手 · 无4品种上限<br>2015-01-05—2026-10-16，2862个真实日末权益点。拖动框选可缩放，两图日期联动；工具栏可重置。</div><section class="cards">'+cards+'</section><section class="chart">'+plot+'</section><footer>'+html.escape(boundary)+f'<br>回撤 =（当日总权益 ÷ 截至当日历史最高权益 − 1）× 100%。最大回撤：{x[peak_idx]}高点 → {x[trough]}低点；期末仍距高点{dd_pct.iloc[-1]:.2f}%。<br><a href="equity_drawdown.png">查看/保存高清图</a> · <a href="../recap_20261018_lifecycle_unlimited_v2_reviewed/index.html">打开3218笔逐笔复盘（约225MB）</a><br>冻结来源：{html.escape(manifest["run_id"])}；manifest SHA256：{facts["source_manifest_sha256"]}。未重跑策略、未下载行情、未访问生产。</footer></main></html>'
    sys.path.append('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='/System/Library/Fonts/STHeiti Medium.ttc')
    plt.rcParams.update({'axes.unicode_minus':False,'font.family':font.get_name(),'figure.facecolor':'#f7f9fb','axes.spines.top':False,'axes.spines.right':False})
    from matplotlib import font_manager
    font_manager.fontManager.addfont('/System/Library/Fonts/STHeiti Medium.ttc')
    picture,axes=plt.subplots(2,1,figsize=(14,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1]},layout='constrained')
    picture.suptitle('全市场无AI一手研究｜整体资金与回撤',fontproperties=font,fontsize=18)
    axes[0].plot(dates,y,color='#147d92',lw=1.5,label='日末总权益（含成本）');axes[0].plot(dates,high,color='#a4afbd',lw=.9,ls=':',label='历史高点')
    axes[0].axhline(capital/10000,color='#b7c2cc',ls='--',lw=.9,label='100万本金')
    axes[0].scatter(dates.iloc[-1],y[-1],color='#147d92',s=20,zorder=3)
    axes[0].annotate(f'期末 {y[-1]:.2f} 万元',xy=(dates.iloc[-1],y[-1]),xytext=(-110,18),textcoords='offset points',fontproperties=font,color='#126c7e',fontsize=11)
    axes[0].set_ylabel('总权益（万元）',fontproperties=font);axes[0].legend(loc='upper left',frameon=False,prop=font,ncol=3);axes[0].grid(alpha=.16)
    axes[1].fill_between(dates,dd,0,color='#c9414a',alpha=.16);axes[1].plot(dates,dd,color='#c9414a',lw=1)
    axes[1].scatter(dates.iloc[trough],dd[trough],color='#962d37',s=23,zorder=3)
    axes[1].annotate(f'最大回撤 {dd[trough]:.2f}%\n{x[trough]}',xy=(dates.iloc[trough],dd[trough]),xytext=(-140,8),textcoords='offset points',fontproperties=font,fontsize=10,color='#962d37',arrowprops=dict(arrowstyle='-',color='#962d37'))
    axes[1].set_ylim(float(dd_pct.min())*1.18,2);axes[1].set_ylabel('回撤（%）',fontproperties=font);axes[1].grid(alpha=.16)
    axes[1].set_xlabel('2015-01-05—2026-10-16｜日线近似；日内止损/重试及供需过滤停用；含12项期末未平仓浮盈亏',fontproperties=font,fontsize=10)
    axes[0].set_title(f'总收益 {metrics["total_return"]:.2f}%   |   Sharpe {metrics["sharpe_ratio"]:.4f}   |   原始冻结每日权益，无策略重跑',fontproperties=font,fontsize=11,loc='left',color='#65778a')
    OUTPUT.mkdir(parents=True)
    picture.savefig(OUTPUT/'equity_drawdown.png',dpi=160);plt.close(picture)
    (OUTPUT/'index.html').write_text(page,encoding='utf-8');(OUTPUT/'figure.json').write_text(fig.to_json(),encoding='utf-8')
    pd.DataFrame({'date':x,'equity':equity,'high_watermark':peak,'drawdown_amount':dd_amount,'drawdown_pct':dd_pct}).to_csv(OUTPUT/'equity_drawdown.csv',index=False)
    facts['boundaries']=boundary;facts['artifact_sha256']={p.name:sha(p) for p in OUTPUT.iterdir()}
    (OUTPUT/'summary.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(facts,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
