"""Read-only financial ledger projection and offline Stage014 C/R150 reporting.

No trading engines are imported or run. Only 59 accepted fresh runs may publish.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,base64,html,json
import numpy as np
import pandas as pd
from stage014_contract import LINE,STARTS,MONTHS,MATURE_STARTS,OBSERVATION_STARTS,CUTOFF,sha,load,atomic_json
from stage013_report import project_curve as _project_curve
from stage010_account_nav import metrics as summary_metrics
from stage011_report import safe,formatted
from stage014_plots import FROZEN_MAPPING_SHA256,WINDOW_SCOPE,EXPECTED_DAILY_POINTS,MONTH_NAMES,validate_inputs,validate_round_fields

OUT=LINE/'artifacts/stage014_five_starts_R150'
HTML_NAME='Stage014_原C15万备用_每年五起点完整回测.html'
VARIANT='C_R150'
HEADERS=['起点','成熟度','方法','期末交易权益','含入金增长','账户回撤','账户Sharpe','真实净盈亏','累计入金','场外余款','滑点','成交次数','闭合轮次','胜率','平均盈利','平均亏损','盈亏比','PF']


def require(value,label):
 if not value:raise ValueError('stage014_report:'+label)


def near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)


def project_curve(raw,events):return _project_curve(raw,events,150000)


def require_complete(reg):
 expected={s+'|C' for s in STARTS}
 require(set(reg['jobs'])==expected and all(j['status']=='validated' and j.get('method')=='fresh_engine' and j.get('reused') is False for j in reg['jobs'].values()),'59_validated_fresh_only')
 require(reg.get('financial_engine_batch_complete') is True and reg.get('financial_replays_started')==59,'59_new_financial_only')
 return True


def mapping_calendar(path,expected_sha):
 require(expected_sha==FROZEN_MAPPING_SHA256 and sha(path)==expected_sha,'frozen_mapping_identity')
 dates=sorted(set(pd.read_csv(path,usecols=['date']).date.astype(str)))
 result={start:[d for d in dates if start<=d<=CUTOFF] for start in STARTS}
 import hashlib
 for start,days in result.items():
  first,count,digest=WINDOW_SCOPE[start]
  require(len(days)==count and days[0]==first and days[-1]==CUTOFF and hashlib.sha256('\n'.join(days).encode()).hexdigest()==digest,'frozen_mapping_calendar_'+start)
 return result


def verify_map(mapping):
 for path,h in mapping.items():require(Path(path).is_file() and sha(path)==h,'source_changed:'+str(path))


def cohort_summary(summary):
 rows=[]
 for cohort in [*MONTH_NAMES.values(),'combined']:
  for obs in (False,True):
   q=summary.loc[summary.observation_only.eq(obs)]
   if cohort!='combined':q=q.loc[q.cohort_month.eq(next(m for m,n in MONTH_NAMES.items() if n==cohort))]
   n=len(q)
   rows.append(dict(cohort=cohort,scope='observation_lt_1y' if obs else 'mature_ge_1y',windows=n,
    negative_real_pnl_windows=int(q.real_trading_net_pnl.lt(0).sum()),positive_real_pnl_windows=int(q.real_trading_net_pnl.gt(0).sum()),
    min_real_pnl=float(q.real_trading_net_pnl.min()) if n else None,median_real_pnl=float(q.real_trading_net_pnl.median()) if n else None,
    worst_E_dd_pct=float(q.balance_max_dd_pct.min()) if n else None,minimum_defined_E_sharpe=float(q.loc[q.balance_returns_defined,'balance_sharpe'].min()) if q.balance_returns_defined.any() else None,
    undefined_E_sharpe_windows=int((~q.balance_returns_defined).sum()),reserve_exhausted_windows=int(q.reserve_exhausted.sum()),
    nonpositive_E_windows=int(q.nonpositive_trading_equity_days.gt(0).sum()),margin_pressure_windows=int(q.trading_margin_over100_days.gt(0).sum()),
    median_deposit=float(q.total_transferred.median()) if n else None,maximum_deposit=float(q.total_transferred.max()) if n else None))
 return pd.DataFrame(rows)


def build(output=OUT,freeze_path=LINE/'stages/stage014_freeze.json'):
 output=Path(output);require(not output.exists(),'immutable_output_exists');freeze=load(freeze_path)
 registry_path=LINE/'outputs/stage014_multistart/registry.json';reg=load(registry_path);require_complete(reg)
 require(reg['freeze_sha256']==sha(freeze_path),'registry_freeze_identity')
 mapping=Path(freeze['data_directory'])/'mapping.csv';calendar=mapping_calendar(mapping,freeze['data_identity']['mapping_sha256'])
 sources={str(Path(freeze_path).resolve()):sha(freeze_path),str(registry_path.resolve()):sha(registry_path),str(mapping.resolve()):sha(mapping)}
 for path in [Path(__file__),Path(__file__).with_name('stage014_plots.py'),Path(__file__).with_name('test_stage014_report.py'),Path(__file__).with_name('test_stage014_plots.py'),Path(__file__).with_name('stage010_account_nav.py'),Path(__file__).with_name('stage011_report.py'),Path(__file__).with_name('stage013_report.py'),Path(__file__).with_name('stage013_plots.py')]:sources[str(path.resolve())]=sha(path)
 rows=[];curves=[];events_out=[]
 for start in STARTS:
  job=reg['jobs'][start+'|C'];path=Path(job['path']);receipt=LINE/'stages/stage014_independent_receipts'/f'{start}_C.json';audit=load(receipt)
  require(audit['status']=='PASS_WITH_LIMITATIONS' and not audit['failures'] and Path(audit['path']).resolve()==path.resolve(),'accepted_window_identity:'+start)
  require(audit.get('method','fresh_engine')=='fresh_engine','accepted_fresh_method')
  pins=job['files_sha256']
  for name in ['daily.csv','reserve_daily.csv','reserve_events.json','actual_strategy_settings.json','effective_parameters.json','entry_risk.csv']:
   p=path/name;h=sha(p);require(h==pins[str(p)]==audit['source_files_sha256'][str(p)],'actual_source_hash:'+name);sources[str(p.resolve())]=h
  sources[str(receipt.resolve())]=sha(receipt);checkpoint=Path(job['checkpoint']);sources[str(checkpoint.resolve())]=sha(checkpoint)
  raw=pd.read_csv(path/'daily.csv',float_precision='round_trip');events=load(path/'reserve_events.json');d=project_curve(raw,events)
  require(d.date.tolist()==calendar[start],'actual_complete_frozen_calendar:'+start)
  declared=pd.read_csv(path/'reserve_daily.csv',float_precision='round_trip');require(d.date.tolist()==declared.date.astype(str).str[:10].tolist(),'actual_wallet_calendar')
  for field in ['raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount','total_account_equity']:
   require(near(d[field],declared[field]),'actual_wallet_projection:'+field)
  m=summary_metrics(d);r=audit['metrics']['rounds'];open_mtm=float(audit['metrics']['open_round_net_mtm'])
  exhausted=d.reserve_balance.le(1e-6);margin=d.total_margin_exact*165/d.trading_account_equity.where(d.trading_account_equity.gt(0))
  row=dict(start=start,variant=VARIANT,arm='C',version='reserve150k',method='fresh_engine',funding_mode='external_topup',cohort_month=int(start[5:7]),
   reserve_initial=150000.,observation_only=start in OBSERVATION_STARTS,**m,transfer_event_count=len(events),reserve_exhausted=bool(exhausted.any()),
   exhaustion_date=str(d.loc[exhausted,'date'].iloc[0]) if exhausted.any() else '',trading_margin_peak_pct=float(margin.max()) if margin.notna().any() else None,
   trading_margin_over100_days=int(margin.gt(100).sum()),source_path=str(path),independent_receipt=str(receipt),open_round_net_mtm=open_mtm,**{'round_'+k:v for k,v in r.items()})
  validate_round_fields(pd.Series(row));rows.append(row);d=d.assign(start=start,variant=VARIANT)
  fields=['start','variant','date','raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount','total_account_equity','slippage','commission','trade_count','total_margin_exact','account_nav','balance_drawdown_pct']
  curves.append(d[fields]);events_out.extend(dict(e,start=start,variant=VARIANT,method='fresh_engine') for e in events)
 summary=pd.DataFrame(rows);daily=pd.concat(curves,ignore_index=True);validate_inputs(summary,daily);cohorts=cohort_summary(summary)
 verify_map(sources);output.mkdir(parents=True)
 tables={'summary.csv':summary,'daily.csv':daily,'cohort_summary.csv':cohorts,'reserve_events.csv':pd.DataFrame(events_out)}
 for name,frame in tables.items():frame.to_csv(output/name,index=False)
 atomic_json(output/'source_manifest.json',dict(source_files_sha256=sources))
 atomic_json(output/'calendar.json',dict(mapping_path=str(mapping.resolve()),mapping_sha256=FROZEN_MAPPING_SHA256,dates_by_start=calendar))
 doc=dict(schema='stage014_five_starts_C_R150_comparison_v1',status='INDEPENDENT_REVIEW_PENDING',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
  source_head=freeze['source_head'],freeze_sha256=sha(freeze_path),starts=list(STARTS),months=list(MONTHS),cutoff=CUTOFF,variant=VARIANT,financial_replays=59,reused_candidates=0,
  summary_rows=59,daily_points=EXPECTED_DAILY_POINTS,mature_windows=54,observation_windows=5,engine_initial_capital=150000,reserve_initial_capital=150000,
  nav='E/150000: deposits included, external reserve excluded',source_files_sha256=sources,promotion_decision='NO_PROMOTION')
 atomic_json(output/'comparison.json',doc)
 atomic_json(output/'data_manifest.json',dict(files_sha256={str((output/name).resolve()):sha(output/name) for name in [*tables,'source_manifest.json','calendar.json','comparison.json']}))
 write_window_records(summary,freeze)
 return dict(report=str(output),summary_rows=59,daily_points=EXPECTED_DAILY_POINTS,new_financial=59,mature=54,observation=5)


def row_values(m):
 zero=int(m.round_count)==0
 return [str(m.start),'观察<1年' if m.observation_only else '成熟>=1年',str(m.method),formatted(m.account_end_equity),formatted(m.account_growth_pct,'pct'),
  formatted(m.balance_max_dd_pct,'pct'),formatted(m.balance_sharpe,'ratio') if m.balance_returns_defined else 'N/A',formatted(m.real_trading_net_pnl),
  formatted(m.total_transferred),formatted(m.off_account_reserve_end),formatted(m.total_slippage),str(int(m.modeled_fill_count)),str(int(m.round_count)),
  'N/A' if zero else formatted(m.round_win_rate_pct,'pct'),'N/A' if not m.round_wins else formatted(m.round_average_win),
  'N/A' if not m.round_losses else formatted(m.round_average_loss_abs),formatted(m.round_payoff_ratio,'ratio'),formatted(m.round_profit_factor,'ratio')]


def write_window_records(summary,freeze):
 folder=LINE/'stages/stage014_windows';folder.mkdir(exist_ok=True);si=summary.set_index('start',drop=False);now=datetime.now(ZoneInfo('Asia/Shanghai'))
 for start in STARTS:
  m=si.loc[start];values=row_values(m);path=folder/f'{now:%Y%m%d_%H%M}_stage014_C_{start.replace("-","")}.md'
  text=f'# Stage014 原C/R150：{start}独立起点\n\n记录时间{now.isoformat()}；line_id=futures_weekly_short_ma_slope_gate，非重要突破，NO_PROMOTION。本窗为fresh_engine，独立新建账户/持仓/策略状态；{values[1]}。原19品种、short bottom20与原风险1.8%/6%/6%/2.5%不变；E15万＋R15万，参数新增/删除无。只扩充固定1/3/6/9/11月起点与截止2026-10-30；旧结果未改未删。\n\n'
  text+=f'实际{m.actual_start}—{m.actual_end}，{int(m.trading_days)}交易日；冻结源码HEAD={freeze["source_head"]}；源={m.source_path}；独审={m.independent_receipt}。\n\n'
  text+='|'+'|'.join(HEADERS)+'|\n|'+'|'.join(['---']*len(HEADERS))+'|\n|'+'|'.join(values)+'|\n'
  text+=f'\n手续费{formatted(m.total_commission)}，备用耗尽={bool(m.reserve_exhausted)}（{m.exhaustion_date or "未耗尽"}），补资事件{int(m.transfer_event_count)}次/{int(m.transfer_event_days)}日。非正E共{int(m.nonpositive_trading_equity_days)}日；保证金×1.65/E峰{formatted(m.trading_margin_peak_pct,"pct")}、超100% {int(m.trading_margin_over100_days)}日，E<=0时margin比率不定义。闭合PnL {formatted(m.round_closed_net_pnl)}＋未平MTM {formatted(m.open_round_net_mtm)}＝真实PnL {formatted(m.real_trading_net_pnl)}。\n\n'
  text+='E/15万含已入金，未转入场外R排除；入金不是利润。E Sharpe不可定义则N/A，PF/盈亏比缺分母或0闭合轮次则N/A，不伪造0或Inf。调研Backtrader资金流/vn.py独立回测支持会计与独立状态，不证明alpha。运行前后过拟合风险均有（同历史重复观察、起点重叠）；固定五起点反证有价值，不筛窗、不扫参数救参。零手续费/PIT/静态保证金/next-open/容量限制继承。后续仅全表独审与交付，不自动晋级。\n'
  path.write_text(text)


def write_reports(folder,summary,cohorts,figures,reviewed):
 state='独立复核通过（有局限）' if reviewed else '独立复核中'
 intro=f'{state}；NO_PROMOTION。原C_R150，15万交易＋15万场外备用。2015—2025每年1/3/6/9/11月＋2026已到达四窗，共59份真实独立回放，54成熟、5观察，统一至2026-10-30；2026Nov未到达不生成。'
 warning='主净值E/150000从1开始，已补入计入、未转入R排除；含入金账户增长/回撤/Sharpe并非去现金流策略收益。真实PnL、补资和场外余额分列。不可定义Sharpe/PF/盈亏比显示N/A，非正E不裁剪。'
 md='# Stage014：原C/15万备用，每年五起点\n\n'+intro+'\n\n'+warning+'\n\n'+cohorts.to_markdown(index=False)+'\n\n|'+'|'.join(HEADERS)+'|\n|'+'|'.join(['---']*len(HEADERS))+'|\n'
 rows=[]
 for _,m in summary.sort_values('start').iterrows():
  values=row_values(m);md+='|'+'|'.join(values)+'|\n';rows.append('<tr data-start="'+str(m.start)+'">'+''.join('<td>'+html.escape(v)+'</td>' for v in values)+'</tr>')
 limitation='固定59起点全部保留、每窗独立冷启动，不能把高度重叠历史当独立OOS。手续费0、PIT/生命周期、静态保证金×1.65、next-open和容量限制继承。反复同历史有过拟合风险，扩充预先固定起点有反证价值，不扫日期/金额/品种救参，不自动晋级。'
 research='调研：Backtrader Fund Tracking（https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/）与vn.py官方回测实现（https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py）；资料支持会计和独立状态，不能证明策略有效。'
 (folder/'report.md').write_text(md+'\n'+limitation+'\n\n'+research+'\n')
 titles=['2015全段E净值/回撤/资金流','五个月组完整59条曲线','十二起始年份完整59条曲线','所有起点盈亏/账户回撤/Sharpe/补资矩阵','资金需求/风险/生存与成熟观察摘要']
 images=[]
 for i,(name,title) in enumerate(zip(figures,titles),1):
  enc=base64.b64encode((folder/name).read_bytes()).decode();images.append(f'<section id="fig{i}"><h2>{title}</h2><img alt="{title}" src="data:image/png;base64,{enc}"></section>')
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage014 原C/R150 五起点</title><style>body{margin:0;background:#f3f6fa;color:#172235;font:16px/1.65 system-ui,sans-serif}main{max-width:1480px;margin:auto;padding:28px 22px}section,.note{background:#fff;padding:20px;border:1px solid #dce3ed;border-radius:14px;margin:18px 0}.note{background:#eaf2fd}img{display:block;width:100%;height:auto}.scroll{overflow:auto}table{border-collapse:collapse;white-space:nowrap;font-size:13px;width:100%}th,td{padding:8px 11px;border-bottom:1px solid #e3e7ef;text-align:right}th{background:#edf2f8}td:first-child,td:nth-child(2),td:nth-child(3){text-align:left}select{font:inherit;padding:6px}nav a{margin-right:15px}</style><main><h1>Stage014 · 原C15万备用，每年五起点</h1>'
 page+='<p>'+intro+'</p><div class="note">'+warning+'</div><p>原19品种、空头历史底部20%过滤与原风险1.8%/6%/6%/2.5%保留；无加仓、无新增多头顶部或MA斜率门。</p><nav>'+''.join(f'<a href="#fig{i}">{title}</a>' for i,title in enumerate(titles,1))+'</nav>'+''.join(images)
 options='<option value="all">全部59个起点</option>'+''.join(f'<option value="{start}">{start}</option>' for start in STARTS)
 page+='<section><h2>全部59窗数据：成熟/观察分列</h2><label>独立起点 <select id="startFilter">'+options+'</select></label><div class="scroll"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in HEADERS)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
 page+='<section><h2>各月及总体分组（成熟/观察分开）</h2><div class="scroll">'+cohorts.to_html(index=False,border=0,na_rep='N/A')+'</div></section><section>'+limitation+'<p>'+research+'</p><p>图像全部内嵌，无HTTP或主动外部资源；file://浏览器自动交互未验收，不绕过工具安全限制。</p></section></main><script>document.getElementById("startFilter").addEventListener("change",function(){document.querySelectorAll("tr[data-start]").forEach(r=>r.hidden=this.value!=="all"&&r.dataset.start!==this.value);});</script></html>'
 (folder/HTML_NAME).write_text(page)


def render(output=OUT,review=None):
 from stage014_plots import render_five
 output=Path(output);locked=load(output/'data_manifest.json')['files_sha256'];verify_map(locked);reviewed=review is not None
 if reviewed:
  r=load(review);require(r['status']=='PASS_WITH_LIMITATIONS' and not r['failures'] and r['data_files_sha256']==locked,'accepted_independent_data_review');verify_map(r['audited_code_sha256'])
 summary=pd.read_csv(output/'summary.csv',float_precision='round_trip');daily=pd.read_csv(output/'daily.csv',float_precision='round_trip');cohorts=pd.read_csv(output/'cohort_summary.csv')
 figures=render_five(summary,daily,reviewed=reviewed);folder=output if reviewed else output/'review_pending';folder.mkdir(exist_ok=True)
 for name,fig in figures.items():fig.savefig(folder/name,dpi=160,bbox_inches='tight');fig.clear()
 write_reports(folder,summary,cohorts,list(figures),reviewed)
 atomic_json(folder/'delivery_receipt.json',dict(status='PASS_WITH_LIMITATIONS' if reviewed else 'INDEPENDENT_REVIEW_PENDING',data_files_sha256=locked,
  figure_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in figures},report_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in [HTML_NAME,'report.md']},independent_review_sha256=sha(review) if reviewed else None,
  financial_replays=0,market_downloads=0,production_accesses=0,browser_interaction_verified=False,promotion_decision='NO_PROMOTION'))
 return dict(report=str(folder),reviewed=reviewed)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['build','render'],required=True);p.add_argument('--output',type=Path,default=OUT);p.add_argument('--review',type=Path);a=p.parse_args()
 print(json.dumps(safe(build(a.output) if a.mode=='build' else render(a.output,a.review)),ensure_ascii=False,indent=2))
