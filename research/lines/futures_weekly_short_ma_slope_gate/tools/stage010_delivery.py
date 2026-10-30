"""Offline-only report/figure publication for the Stage010 saved-data projection."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
import html
import json
import pandas as pd
from stage010_account_nav import LINE,sha,require

OUTPUT=LINE/'artifacts/stage010_off_account_nav'
LABELS={'A_idle':'A原版','A_R':'A＋场外补资','C_idle':'C原版','C_R':'C＋场外补资'}
HTML_NAME='Stage010_15万起点_场外补资净值报告.html'


def freeze_data():
    paths=[OUTPUT/name for name in ['projection.json','daily.csv','summary.csv','paired.csv']]
    locked={str(p):sha(p) for p in paths}
    (OUTPUT/'data_manifest.json').write_text(json.dumps(dict(schema='stage010-data-lock-v1',files_sha256=locked),ensure_ascii=False,indent=2)+'\n')
    return locked


def verify_data():
    locked=json.loads((OUTPUT/'data_manifest.json').read_text())['files_sha256']
    for path,expected in locked.items():require(sha(path)==expected,'projection_data_changed')
    return locked


def accepted_review(path):
    obj=json.loads(Path(path).read_text())
    require(obj['status']=='PASS_WITH_LIMITATIONS' and not obj['failures'],'independent_review_required')
    require(obj['data_files_sha256']==verify_data(),'independent_review_exact_data_lock')
    for source,expected in obj['audited_code_sha256'].items():require(sha(source)==expected,'audited_code_changed')
    return obj


def render(review_path=None):
    from stage010_plots import render_five
    verify_data();reviewed=review_path is not None
    review=accepted_review(review_path) if reviewed else None
    summary=pd.read_csv(OUTPUT/'summary.csv',float_precision='round_trip')
    paired=pd.read_csv(OUTPUT/'paired.csv',float_precision='round_trip')
    daily=pd.read_csv(OUTPUT/'daily.csv',float_precision='round_trip')
    figures=render_five(summary,paired,daily,reviewed=reviewed)
    destination=OUTPUT if reviewed else OUTPUT/'review_pending';destination.mkdir(exist_ok=True)
    for name,fig in figures.items():
        fig.savefig(destination/name,dpi=160,bbox_inches='tight');fig.clear()
    figure_names=list(figures)
    write_reports(summary,figure_names,destination,reviewed)
    receipt=dict(schema='stage010-display-delivery-v1',published_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        review_status='PASS_WITH_LIMITATIONS' if reviewed else 'INDEPENDENT_REVIEW_PENDING',financial_replays=0,market_downloads=0,
        production_accesses=0,initial_trading_capital=150000,off_account_reserve_in_nav=False,deposits_in_nav=True,
        data_files_sha256=verify_data(),figure_files_sha256={str(destination/n):sha(destination/n) for n in figure_names},
        report_files_sha256={str(destination/n):sha(destination/n) for n in [HTML_NAME,'report.md']},
        independent_review_sha256=sha(review_path) if reviewed else None,source_files_sha256=json.loads((OUTPUT/'projection.json').read_text())['source_files_sha256'],
        promotion_decision='NO_PROMOTION')
    (destination/'delivery_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return receipt


def write_reports(summary,figure_names,destination,reviewed):
    state='独立复核通过（有局限）' if reviewed else '独立复核中'
    warning='净值＝交易账户权益÷150,000。场外未转入备用金不计入，已补入资金计入。账户增长、回撤、账户Sharpe均含入金影响，不能当作剔除现金流后的策略收益。'
    text=f'''# Stage010：15万起点、场外补资账户净值\n\n状态：{state}；NO_PROMOTION。截止2026-10-29，23独立起点、92组曲线、46配对、141,996日点；2026-1/1不足一年，仅观察。\n\n{warning}\n\n交易权益 = 150,000 + 累计真实交易净盈亏 + 累计场外入金。补资触发、金额、仓位、成交及行情全沿用Stage009，仅投影已有缓存；本次0金融回放、0行情下载、0生产访问、0HTTP服务。\n\nA原版为19品种周线底仓无新增价格过滤；C原版仅保留空头历史区间底部20%拦截。两者均无加仓、无多头顶部过滤、无MA斜率过滤。＋场外补资为对应Stage009交易路径；未补入余额始终不进入本图。\n\n账户Sharpe按账户简单日变化率、样本标准差、252年化；分母非正则为0且defined=False，不作业绩解释。起点与末点、真实盈亏、补资、费用、成交、已平仓交易统计见summary.csv。指标差仅描述账户展示差异，不用于重新投票或晋级。\n\n|起点|版本|交易账户期末权益|含入金账户增长|账户回撤|账户Sharpe|真实交易净盈亏|累计入金|场外余款|滑点|成交次数|已平仓胜率|平均盈利|平均亏损绝对值|盈亏比|PF|\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'''
    table_rows=[]
    order={v:i for i,v in enumerate(['A_idle','A_R','C_idle','C_R'])}
    data=summary.assign(_order=summary.variant.map(order)).sort_values(['start','_order'])
    for _,m in data.iterrows():
        vals=[m.start+('（观察）' if m.observation_only else ''),LABELS[m.variant],f'{m.account_end_equity:,.0f}',f'{m.account_growth_pct:+.2f}%',f'{m.balance_max_dd_pct:.2f}%',f'{m.balance_sharpe:.3f}',f'{m.real_trading_net_pnl:+,.0f}',f'{m.total_transferred:,.0f}',f'{m.off_account_reserve_end:,.0f}',f'{m.total_slippage:,.0f}',str(int(m.modeled_fill_count)),f'{m.round_win_rate_pct:.2f}%',f'{m.round_average_win:,.2f}',f'{m.round_average_loss_abs:,.2f}',f'{m.round_payoff_ratio:.3f}',f'{m.round_profit_factor:.3f}']
        text+='|'+'|'.join(vals)+'|\n'
        table_rows.append('<tr data-start="'+html.escape(str(m.start))+'">'+''.join('<td>'+html.escape(v)+'</td>' for v in vals)+'</tr>')
    text+='''\n调研判断：Backtrader官方Fund Tracking与其GitHub实现区分账户余额和现金流调整后业绩；本次按用户明确选择含补资的账户曲线，同时单列真实交易净盈亏。参考：https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/；GitHub实现：https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py\n\n过拟合反思（运行前后）：本次仅展示变更，不新增参数过拟合；此前反复看历史和重叠起点的局限仍在。继续完成有价值，解决账户口径不一致；图表增长提高不构成策略改善或晋级。\n\n继承局限：历史缓存并非完整上市/PIT历史、零手续费、静态规格/保证金×1.65、日线next-open、缺乏盘口容量与券商实时购买力证明；策略未晋级。未修改旧Stage009、其他44品种研究线或生产材料。\n'''
    (destination/'report.md').write_text(text)
    titles=['2015年初至今：账户净值与回撤','每年年初独立起点','每年年中独立起点','各窗口账户指标差','盈亏与补资拆分总览']
    pictures=[]
    for i,(name,title) in enumerate(zip(figure_names,titles),1):
        encoded=base64.b64encode((destination/name).read_bytes()).decode('ascii')
        pic=f'<section id="fig{i}"><h2>{html.escape(title)}</h2><img alt="{html.escape(title)}" src="data:image/png;base64,{encoded}"></section>'
        pictures.append(pic)
    options='<option value="all">全部23个起点</option>'+''.join(f'<option value="{s}">{s}</option>' for s in sorted(summary.start.unique()))
    heads=['独立起点','版本','期末交易权益','含入金增长','账户回撤','账户Sharpe','真实交易盈亏','累计入金','场外余款','滑点','成交次数','已平仓胜率','平均盈利','平均亏损','盈亏比','PF']
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Stage010 · 15万起点场外补资净值</title><style>
body{margin:0;background:#f4f6fa;color:#172235;font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1450px;margin:auto;padding:30px 22px}h1{font-size:29px;line-height:1.35}h2{font-size:21px}section,.box{background:white;padding:20px;margin:18px 0;border:1px solid #dce3ed;border-radius:14px}img{display:block;width:100%;height:auto}strong{color:#164b80}.note{background:#eaf2fd;border-left:5px solid #2467a6}.muted{color:#526177;font-size:14px}nav a{display:inline-block;margin:5px 18px 5px 0;color:#16528b}select{font:inherit;padding:6px 12px}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;white-space:nowrap;width:100%}td,th{padding:9px 12px;border-bottom:1px solid #e3e7ef;text-align:right}th{background:#edf2f8;position:sticky;top:0}td:first-child,td:nth-child(2),th:first-child,th:nth-child(2){text-align:left}tr:nth-child(even){background:#f9fbfd}
</style><main><h1>Stage010 · 15万起点，备用金完全场外</h1>'''
    page+=f'<p class="muted">{html.escape(state)} · 数据截止2026-10-29 · 23独立起点 / 92组账户曲线 · 单文件离线报告</p>'
    page+='<div class="box note"><strong>账户净值＝交易账户权益÷150,000；起始净值1。</strong><br>'+html.escape(warning)+'<br>交易账户权益＝150,000＋真实交易净盈亏＋累计场外补资。未转入余额仅列作备查。</div>'
    page+='<p>A：19品种原周线底仓；C：空头历史区间底部20%拦截。两者均无加仓，无多头或MA斜率过滤。补资时点、手数、成交沿用已审Stage009；本次只重做展示。</p><nav>'+''.join(f'<a href="#fig{i}">{t}</a>' for i,t in enumerate(titles,1))+'</nav>'
    page+=''.join(pictures)
    page+='<section><h2>逐窗口数据：账户余额与真实盈亏分列</h2><label>独立起点 <select id="startFilter">'+options+'</select></label><p class="muted">2026年初不足一年，仅供观察。含入金增长、账户回撤与账户Sharpe不作现金流调整后的策略业绩解释。</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join(table_rows)+'</tbody></table></div></section>'
    page+='<section class="muted"><p>本文件图片、数据和筛选逻辑全部内嵌；不依赖HTTP、外部脚本、字体或行情服务。0金融重跑、0下载、0生产访问。</p><p>本次只改展示，不新增参数过拟合；能解决净值口径差异，有价值完成。历史反复研究、重叠窗口、零手续费等原局限继续保留，NO_PROMOTION。</p><p>调研依据：<a href="https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/">Backtrader 官方 Fund Tracking</a>。<a href="https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py">GitHub资金流实现</a>。其资金流与盈亏分离原则用于单列真实交易盈亏；本页依用户要求显示含入金账户曲线。</p></section></main><script>document.getElementById("startFilter").addEventListener("change",function(){document.querySelectorAll("tbody tr").forEach(r=>r.hidden=this.value!=="all"&&r.dataset.start!==this.value);});</script></html>'
    (destination/HTML_NAME).write_text(page)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--review',type=Path)
    a=p.parse_args()
    if a.freeze:print(json.dumps(freeze_data(),ensure_ascii=False,indent=2))
    else:print(json.dumps(render(a.review),ensure_ascii=False,indent=2))
