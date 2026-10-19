"""Hash-closed enabled/disabled weekly comparison, both at 0.25% equity risk.

Use original042/032 Plotly traces and original042 PNG AST; no baseline curve,
financial replay, provider query, or chart implementation copy.
"""
import argparse,html,json,os
from datetime import datetime
from pathlib import Path
from types import FunctionType
import numpy as np
import pandas as pd
import stage042_account_overview as base
import stage072_fractional_overview as pngbase
import stage094_quarter_risk_recap as quarter

COMMON_CODE=('stage090_quarter_risk.py','stage091_quarter_weekly.py','stage092_quarter_pending_open.py','stage093_run_quarter_pair.py')
SHARED_TABLES=('market_daily.csv','mapping.csv','contract_metadata.csv','trading_calendar.csv','lifecycle_deadlines.csv')
METRICS=(('initial_capital','初始资金','元'),('end_balance','期末权益','元'),('total_return','总收益','%'),('max_ddpercent','最大回撤','%'),('sharpe_ratio','Sharpe',''),('payoff_ratio','净盈亏比',''),('profit_factor','盈利因子',''),('win_rate_pct','净胜率','%'),('completed_episodes','完整entry','笔'),('completed_contracts','完整合约数量','手'),('total_trade_count','成交次数','笔'),('total_commission','手续费','元'),('total_slippage','滑点','元'))

def check_pair_identity(a,b):
 quarter.check(a.get('long_weekly_filter') is True and b.get('long_weekly_filter') is False,'pair_modes_not_enabled_disabled')
 quarter.check(a['parameters']==b['parameters'],'pair_parameters_differ')
 for key in ('parent_execution_manifest_sha256','parent_execution_commit','parent_execution_run_id','frozen_data_manifest_sha256'):
  quarter.check(a.get(key)==b.get(key),'pair_reference_mismatch:'+key)
 for key in COMMON_CODE:quarter.check(key in a.get('code_snapshot_hashes',{}) and a['code_snapshot_hashes'][key]==b.get('code_snapshot_hashes',{}).get(key),'pair_code_snapshot:'+key)
 for key in set(a.get('code_snapshot_hashes',{}))&set(b.get('code_snapshot_hashes',{})):quarter.check(a['code_snapshot_hashes'][key]==b['code_snapshot_hashes'][key],'pair_shared_code_changed:'+key)
 for name in SHARED_TABLES:quarter.check(name in a['hashes'] and a['hashes'][name]==b['hashes'].get(name),'pair_frozen_table:'+name)
 for key in ('start','end','mode','fractional_risk_policy'):quarter.check(a.get(key)==b.get(key),'pair_policy_or_interval:'+key)

def load_arm(source,parent,enabled):
 source,parent=Path(source).resolve(),Path(parent).resolve();identity=json.loads((source/'manifest.json').read_text());metrics=json.loads((source/'summary.json').read_text());quarter.validate_policy(identity,metrics);bound=base.verify_hashes(source,identity);quarter.check(identity['run_id']==source.name and identity['long_weekly_filter'] is enabled,'source_arm_identity');quarter.check(identity['mode']==metrics['mode']=='daily-proxy','source_mode')
 summary=json.loads((parent/'summary.json').read_text());quarter.check(summary['source_manifest_sha256']==base.sha(source/'manifest.json') and summary['backtest_metrics']==metrics,'parent_source_identity');artifacts=dict(summary['artifact_sha256'])
 for name,digest in artifacts.items():quarter.check(base.sha(base.safe_member(parent,name))==digest,'parent_artifact:'+name)
 d=pd.read_csv(source/'daily.csv',float_precision='round_trip');dates=pd.to_datetime(d.date);equity=d.equity.astype(float);capital=float(metrics['initial_capital']);quarter.check(len(d)==metrics['total_days'] and dates.is_monotonic_increasing and not dates.duplicated().any(),'daily_dates');quarter.check(np.isfinite(equity).all() and capital>0 and np.allclose(equity,capital+d.net_pnl.cumsum(),atol=1e-5,rtol=0) and np.allclose(equity,d.balance,atol=1e-5,rtol=0),'daily_accounting')
 quarter.check(d.date.iloc[-1]==metrics['analysis_end'] and dates.iloc[0]>=pd.Timestamp(metrics['analysis_start']) and identity['start']==metrics['analysis_start'] and identity['end']==metrics['analysis_end'],'daily_analysis_interval')
 peak=equity.cummax().clip(lower=capital);dd_amount=equity-peak;dd=(equity/peak-1)*100;trough=int(dd.idxmin())
 for key,v in [('highlevel',peak),('drawdown',dd_amount),('ddpercent',dd)]:quarter.check(np.allclose(d[key],v,atol=1e-7,rtol=0),'daily_'+key)
 for key,v in [('end_balance',equity.iloc[-1]),('total_return',(equity.iloc[-1]/capital-1)*100),('max_ddpercent',dd.min())]:quarter.old.near(metrics[key],v,'summary_'+key)
 residual=json.loads((source/'residual_open_positions.json').read_text());facts=dict(start=d.date.iloc[0],end=d.date.iloc[-1],initial_capital=capital,end_equity=float(equity.iloc[-1]),max_drawdown_trough_date=d.date.iloc[trough],total_return_pct=metrics['total_return'],sharpe_ratio=metrics['sharpe_ratio'],residual_open_positions=len(residual))
 proof=dict(source_directory=str(source),parent_directory=str(parent),source_manifest_sha256=base.sha(source/'manifest.json'),source_hashes=bound,parent_summary_sha256=base.sha(parent/'summary.json'),parent_artifact_sha256=artifacts,weekly_filter=enabled,weekly_policy=identity['weekly_policy'],weekly_violations=metrics['actual_long_weekly_violations'],metrics=metrics)
 return dict(source=source,parent=parent,manifest=identity,metrics=metrics,d=d,dates=dates,equity=equity,peak=peak,dd_pct=dd,dd_amount=dd_amount,trough=trough,capital=capital,facts=facts,proof=proof)

def pair_plot(enabled,disabled):
 fig,_=base.make_plot(enabled);other,_=base.make_plot(disabled)
 for trace in fig.data:trace.name='周过滤启用 · '+str(trace.name)
 for trace in other.data:trace.name='周过滤关闭 · '+str(trace.name)
 # Preserve every source trace value and axis; use color/name only to identify arms.
 for i,t in enumerate(other.data):
  if i in (0,2):t.line.color='#b77228'
  fig.add_trace(t)
 fig.update_yaxes(range=[min(float(enabled['dd_pct'].min()),float(disabled['dd_pct'].min()))*1.18,2],row=2,col=1)
 fig.update_layout(title='0.25%风险 · 周过滤启用 / 关闭 · 同口径资金与回撤',legend=dict(orientation='h'))
 return fig,fig.to_html(full_html=False,include_plotlyjs=True,config=dict(responsive=True,displaylogo=False,scrollZoom=True))

def png_for(enabled):
 literals={'全市场无AI｜风险预算最多一手｜整体资金与回撤':'全市场无AI｜0.25%权益风险｜周过滤'+('启用' if enabled else '关闭')+'｜资金与回撤','｜风险预算恢复/开盘复核｜日线近似｜含':'｜0.25%风险/开盘整单复核｜日线近似｜含'}
 fn=FunctionType(pngbase.png_function.__code__,{**pngbase.png_function.__globals__,'PNG_LITERALS':literals},pngbase.png_function.__name__);return fn()

def unchanged(arms):
 for b in arms:
  p=b['proof'];quarter.check(base.sha(b['source']/'manifest.json')==p['source_manifest_sha256'] and base.verify_hashes(b['source'],b['manifest'])==p['source_hashes'],'source_changed')
  quarter.check(base.sha(b['parent']/'summary.json')==p['parent_summary_sha256'],'parent_changed')
  for name,digest in p['parent_artifact_sha256'].items():quarter.check(base.sha(base.safe_member(b['parent'],name))==digest,'parent_artifact_changed')

def generate(enabled_source,disabled_source,enabled_recap,disabled_recap,output):
 output=Path(output).resolve()
 for p in (enabled_source,disabled_source,enabled_recap,disabled_recap):
  p=Path(p).resolve();quarter.check(not(output.is_relative_to(p) or p.is_relative_to(output)),'output_overlaps_input')
 if output.exists():raise FileExistsError(output)
 code=base.sha(Path(__file__));dependencies={n:base.sha(Path(__file__).with_name(n)) for n in ('stage042_account_overview.py','stage072_fractional_overview.py','stage094_quarter_risk_recap.py')};a,b=load_arm(enabled_source,enabled_recap,True),load_arm(disabled_source,disabled_recap,False);check_pair_identity(a['manifest'],b['manifest']);quarter.check(a['d'].date.tolist()==b['d'].date.tolist() and a['capital']==b['capital'],'pair_daily_dates_or_capital');fig,plot=pair_plot(a,b);rows=[]
 for key,label,unit in METRICS:
  av,bv=a['metrics'].get(key),b['metrics'].get(key);rows.append(dict(key=key,label=label,unit=unit,enabled=av,disabled=bv,delta=None if av is None or bv is None else av-bv))
 esc=html.escape
 def fmt(x):return 'N/A' if x is None else f'{x:,.4f}'
 table=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (r['label'],fmt(r['enabled'])+r['unit'],fmt(r['disabled'])+r['unit'],fmt(r['delta'])+r['unit']))+'</tr>' for r in rows)
 links=' · '.join('<a href="'+esc(os.path.relpath(x['parent']/'index.html',output),quote=True)+'">'+label+'逐笔复盘</a>' for x,label in ((a,'周过滤启用'),(b,'周过滤关闭')))
 boundaries=''.join('<h3>'+label+'</h3><ul>'+''.join('<li>'+esc(str(v))+'</li>' for v in x['metrics'].get('boundaries',[]))+'</ul>' for x,label in ((a,'启用版冻结边界'),(b,'关闭版冻结边界')))
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0.25%风险 · 周过滤启用与关闭</title><style>body{font:15px sans-serif;color:#24364a;background:#f5f7fa;margin:24px}main{max-width:1400px;margin:auto}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:9px;text-align:right}.note{background:#e9f4f6;padding:15px;line-height:1.8}a{color:#147d92}.chart{background:white}</style><main><h1>0.25%总权益风险 · 周过滤启用 / 关闭</h1><p class="note">'+esc(quarter.NOTE)+' '+esc(quarter.mode_note(True))+' '+esc(quarter.mode_note(False))+' 同一冻结代码、参数与行情，仅策略周过滤开关不同；同样本描述性版本比较，不作为晋级结论。0.5%父版本与N仅为执行/数据身份锚，不是本表比较臂。</p><p>'+links+'</p><p>两臂各'+str(len(a['d']))+'个日末权益点；权益含成本及期末浮盈亏。</p><table><thead><tr><th>指标</th><th>周过滤启用</th><th>周过滤关闭</th><th>启用−关闭</th></tr></thead><tbody>'+table+'</tbody></table><p>策略周线违规：启用 '+esc(str(a['metrics']['actual_long_weekly_violations']))+'；关闭 N/A（未启用，检查0，不声称通过）。</p><section class="chart">'+plot+'</section><p><a href="enabled/equity_drawdown.png">启用版PNG</a> · <a href="disabled/equity_drawdown.png">关闭版PNG</a> · <a href="summary.json">完整哈希</a></p>'+boundaries+'</main></html>'
 unchanged((a,b));output.mkdir(parents=True);png_proofs={}
 for arm,label in ((a,'enabled'),(b,'disabled')):
  target=output/label;target.mkdir();fn,proof=png_for(label=='enabled');fn(arm,target);png_proofs[label]=proof
 (output/'index.html').write_text(page);(output/'figure.json').write_text(fig.to_json());pd.DataFrame(dict(date=a['d'].date,enabled_equity=a['equity'],disabled_equity=b['equity'],enabled_peak=a['peak'],disabled_peak=b['peak'],enabled_drawdown_pct=a['dd_pct'],disabled_drawdown_pct=b['dd_pct'])).to_csv(output/'equity_pair.csv',index=False);unchanged((a,b));quarter.check(base.sha(Path(__file__))==code,'generator_changed')
 for name,digest in dependencies.items():quarter.check(base.sha(Path(__file__).with_name(name))==digest,'dependency_changed')
 report=dict(pair='risk025_weekly_enabled_vs_disabled',risk_fraction=.0025,initial_example_budget=2500,points_per_arm=len(a['d']),enabled=a['proof'],disabled=b['proof'],comparison=rows,png_adapter=png_proofs,generator_sha256=code,dependency_sha256=dependencies,plot_source_sha256=base.sha(base.PLOT_SOURCE),financial_replays=0,market_downloads=0,production_access=False,created_at=datetime.now().isoformat(),artifact_sha256={p.relative_to(output).as_posix():base.sha(p) for p in output.rglob('*') if p.is_file()})
 (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('enabled-source','disabled-source','enabled-recap','disabled-recap','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=generate(a.enabled_source,a.disabled_source,a.enabled_recap,a.disabled_recap,a.output);print(json.dumps(dict(points=r['points_per_arm'],artifacts=r['artifact_sha256']),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
