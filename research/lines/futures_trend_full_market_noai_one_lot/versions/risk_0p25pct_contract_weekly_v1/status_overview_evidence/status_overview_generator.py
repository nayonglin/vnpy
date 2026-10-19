"""Readonly publication of one complete arm and one failed arm. No paired ranking."""
from pathlib import Path
import sys,json,hashlib,html,shutil,os
root=Path.cwd();line=root/'research/lines/futures_trend_full_market_noai_one_lot';sys.path.insert(0,str(line/'tools'))
import stage096_quarter_pair_overview as charts
import stage042_account_overview as base
enabled=line/'outputs/run_20261020_risk025_contract_weekly_v1';recap=line/'outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v3'
failed=line/'outputs/run_20261020_risk025_no_weekly_v1';review=line/'stages/20261020_0157_stage100_failed_v1_independent_review.json'
proposal=line/'stages/20261020_0158_stage104_causal_capacity_exit_proposal.md';output=line/'outputs/overview_20261020_risk025_v1_status_v2'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
assert not output.exists();arm=charts.load_arm(enabled,recap,True);er=read(recap/'summary.json')['independent_review']['metadata'];fr=read(review)
assert er['status']==er['verdict']=='PASS_WITH_LIMITS' and er['source_manifest_sha256']==sha(enabled/'manifest.json')
assert fr['status']=='FAIL_INCOMPLETE_LIFECYCLE' and fr['remaining_p1']==1 and not(failed/'manifest.json').exists()
assert sha(failed/'protocol.json')=='fcb1176e51cf4bedd56879e4db2367ea16a0d7144fd4e6eb6f9574427af52914'
assert sha(failed/'failure_snapshot.json')=='bbb1459983f309d50b9e9ea84db72b9d157a262438a89babf5f8c9b619638550'
assert read(failed/'protocol.json')['parameters']==arm['manifest']['parameters']
bound={str(p):sha(p) for p in (review,review.with_suffix('.md'),proposal,proposal.with_suffix('.json'),failed/'protocol.json',failed/'failure_snapshot.json')}
fig,plot=base.make_plot(arm);metrics=arm['metrics'];rows=[]
for key,label,unit in charts.METRICS:
 value=metrics.get(key);text='N/A' if value is None else f'{value:,.4f}'+unit
 rows.append('<tr><td>'+html.escape(label)+'</td><td>'+html.escape(text)+'</td><td>未完成，不提供全期指标</td></tr>')
cost=metrics['total_commission']+metrics['total_slippage'];gross=metrics['end_balance']-metrics['initial_capital']+cost
link=html.escape(os.path.relpath(recap/'index.html',output),quote=True)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0.25%风险双版本：回测状态与含周线版资金曲线</title><style>body{font:15px sans-serif;color:#24364a;background:#f5f7fa;margin:24px;line-height:1.7}main{max-width:1400px;margin:auto}table{border-collapse:collapse;width:100%;background:white}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:right}.note{background:#e9f4f6;padding:14px}.failure{background:#fff0e8;border-left:5px solid #bd592b;padding:14px}a{color:#147d92}</style><main><h1>0.25%总权益风险：双版本执行状态</h1><p class="note">初始资金1,000,000元；单笔初始止损风险预算上限为当时账户总权益×0.0025，初始2500元；整手及其它风控可令实际风险更低，开盘再取原授权预算与当时权益预算的较小值。无一手/四品种帽、不加仓、无AI、全市场。含周线版只对开多要求当前交易合约自身已完成周MA5&gt;10&gt;20&gt;40，空头不加周门。</p><p class="failure"><strong>无法形成完整双版绩效比较。</strong>含周线版完整回放2015-01-05—2026-10-16，共2862日，并通过独立实际审查。无周线版于2019-06-27因JR201907剩余12手无法按原整单规则在截止前退出而停止，没有最终manifest或全期绩效。失败日前缀不能拿来与完整含版比较；此处只画含版自身曲线，没有关闭版或旧版本替代曲线。</p><p><a href="'''+link+'''">含交易合约周线版：完整逐笔复盘</a> · <a href="failed_review.md">无周线版：独立失败审查</a> · <a href="capacity_exit_proposal.md">待决定：统一容量退出方案</a></p><table><thead><tr><th>指标</th><th>含交易合约周线（完整）</th><th>不含周线（未完成）</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><h2>含周线版：账户资金与回撤</h2><p>权益包含全部成交成本及期末持仓浮盈亏；下图仅代表本完整运行。可缩放、联动与复位。</p>'''+plot+'''<p><a href="equity_drawdown.png">资金/回撤PNG</a> · <a href="equity_drawdown.csv">逐日曲线CSV</a> · <a href="summary.json">来源及哈希凭证</a></p><p>含版成本归因：毛交易损益'''+f'{gross:,.2f}'+'''元，手续费与滑点合计'''+f'{cost:,.2f}'+'''元，净损益'''+f'{metrics["end_balance"]-metrics["initial_capital"]:,.2f}'+'''元。毛交易损益为日末净损益加回全部成交成本，不是去成本的新回测。</p><p>无周线失败原因：JR实际初始stop风险2400元≤预算2658.83元；截止日真日量7&lt;整单12，未假造成交。不是0.25%预算计算错误。6/28真量49已过原截止，不能用于补救。按当日真实量分批退出和因果提前退出属于新的共同执行政策，须明确后再同源重跑两版；目前本页不认领该方案已实施或已批准。</p><p>研究边界：日线近似，获授权停用C2/C9日内规则及缺冻结CSV供需过滤；费用/保证金/规格为静态快照，日量不等于真实开盘盘口容量。名义stop预算不保证跳空/成本后的损失上限。胜率及盈亏比按完整原始OPEN扣成本后的episode；部分平仓、每手不另计样本。只是一条同样本历史路径，有后验选择风险，不构成样本外或正式晋级证据。</p><p>调研判断：<a href="https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size">CME仓位预算方法</a>支持风险金额和stop距离共同定量；<a href="https://backtrader.com/docu/filler/">官方容量填单文档</a>说明成交量限制须显式建模。预算合规无法保证未来退出流动性；本失败不能当周线过滤alpha优劣证据。</p></main></html>'''
charts.unchanged((arm,));assert all(sha(Path(p))==h for p,h in bound.items());output.mkdir()
fn,png_proof=charts.png_for(True);fn(arm,output)
(output/'index.html').write_text(page);(output/'figure.json').write_text(fig.to_json())
import pandas as pd
pd.DataFrame(dict(date=arm['d'].date,equity=arm['equity'],peak=arm['peak'],drawdown_pct=arm['dd_pct'])).to_csv(output/'equity_drawdown.csv',index=False)
for p,name in ((review,'failed_review.json'),(review.with_suffix('.md'),'failed_review.md'),(proposal,'capacity_exit_proposal.md'),(proposal.with_suffix('.json'),'capacity_exit_proposal.json')):shutil.copy2(p,output/name)
shutil.copy2(__file__,output/'status_overview_generator.py')
charts.unchanged((arm,));assert all(sha(Path(p))==h for p,h in bound.items())
proof=dict(status='ONE_COMPLETE_ONE_FAILED_NO_PAIRED_RANKING',enabled=arm['proof'],failed_source=str(failed),failed_protocol_sha256=sha(failed/'protocol.json'),failed_snapshot_sha256=sha(failed/'failure_snapshot.json'),failed_review_sha256=sha(review),failed_full_period_metrics_valid=False,points=2862,trace_count=len(fig.data),png_adapter=png_proof,proposal_only=True,input_bindings=bound,financial_replays=0,artifact_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()})
(output/'summary.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'directory':str(output),'points':2862,'traces':len(fig.data),'status':proof['status']},ensure_ascii=False))
