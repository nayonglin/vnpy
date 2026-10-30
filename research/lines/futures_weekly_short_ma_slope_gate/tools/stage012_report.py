"""Saved-ledger C-only reserve50k/150k comparison; never runs a financial engine."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64,html,json,math
import numpy as np
import pandas as pd
from stage009_contract import LINE,STARTS,CUTOFF,sha,load,atomic_json
from stage010_account_nav import metrics as account_metrics
from stage011_report import safe,formatted

OUT=LINE/'artifacts/stage012_reserve50k_comparison'
VARIANTS=('C_R150','C_R50')
LABELS={'C_R150':'原C：15万备用金','C_R50':'原C：5万备用金'}
HTML_NAME='Stage012_原风险C版_5万与15万备用金对比.html'


def require(value,label):
 if not value:raise ValueError('stage012_report:'+label)


def near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)


def project_curve(raw,events,reserve_initial):
 require(reserve_initial in {50000,150000},'fixed_reserve_limit')
 d=raw.copy();d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
 require(len(d)>0 and d.date.is_monotonic_increasing and not d.date.duplicated().any(),'daily_calendar')
 for k in ['account_equity','net_pnl','slippage','commission','trade_count','total_margin_exact']:
  require(k in d and np.isfinite(d[k]).all(),'finite_'+k)
 require(near(d.account_equity,150000+d.net_pnl.cumsum()),'raw_PnL_bridge')
 require(near(d.account_equity.iloc[0],150000) and near(d.net_pnl.iloc[0],0),'fresh150k')
 cum=0.;remaining=float(reserve_initial);transfers={};seen=set();last='';raw_daily=d.set_index('date').account_equity.to_dict()
 for e in events:
  date=str(e['date'])[:10];require(date in raw_daily and date>=last and str(e['event_id']) not in seen,'event_calendar_unique');last=date;seen.add(str(e['event_id']))
  before=float(raw_daily[date])+cum;amount=float(e['transfer_amount']);expected=min(max(150000-before,0),remaining)
  require(amount>0 and near(amount,expected) and amount<=remaining+1e-6,'bounded_deficit')
  fields=dict(raw_account_equity=raw_daily[date],trading_equity_before=before,trading_equity_after=before+amount,reserve_before=remaining,
   reserve_after=remaining-amount,total_account_equity=before+remaining,cumulative_transfer=cum+amount)
  for k,v in fields.items():require(near(e[k],v),'event_'+k)
  cum+=amount;remaining-=amount;transfers[date]=transfers.get(date,0)+amount
 d['transfer_amount']=d.date.map(transfers).fillna(0);d['cumulative_transfer']=d.transfer_amount.cumsum()
 d['raw_account_equity']=d.account_equity;d['trading_account_equity']=d.account_equity+d.cumulative_transfer
 d['reserve_initial']=float(reserve_initial);d['reserve_balance']=reserve_initial-d.cumulative_transfer;d['total_account_equity']=d.trading_account_equity+d.reserve_balance
 d['account_nav']=d.trading_account_equity/150000
 d['balance_drawdown_pct']=(d.trading_account_equity/np.maximum.accumulate(np.r_[150000,d.trading_account_equity])[1:]-1)*100
 require(near(d.total_account_equity,150000+reserve_initial+d.net_pnl.cumsum()),'total_budget_cash_bridge')
 return d


def summary_metrics(d):return account_metrics(d)


def cmp(a,b):return 0 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6) else (1 if a>b else -1)


def pair_metrics(old,new,start,method):
 row=dict(start=start,arm='C',cohort='January' if start[5:7]=='01' else 'June',observation_only=start=='2026-01-01',method50=method)
 for out,key in [('delta_account_end_equity','account_end_equity'),('delta_real_trading_net_pnl','real_trading_net_pnl'),('delta_account_growth_pp','account_growth_pct'),
  ('delta_balance_max_dd_pp','balance_max_dd_pct'),('delta_balance_sharpe','balance_sharpe'),('delta_deposits','total_transferred')]:row[out]=float(new[key])-float(old[key])
 require(near(row['delta_account_end_equity'],row['delta_real_trading_net_pnl']+row['delta_deposits']),'pair_account_cashflow_bridge')
 for target,field in [('real_pnl_comparison','real_trading_net_pnl'),('dd_comparison','balance_max_dd_pct'),('sharpe_comparison','balance_sharpe')]:row[target]=cmp(new[field],old[field])
 for prefix,m in [('r150',old),('r50',new)]:
  for field in ['account_end_equity','real_trading_net_pnl','total_transferred','balance_max_dd_pct','balance_sharpe']:row[prefix+'_'+field]=m[field]
 return row


def verify_map(mapping):
 for p,h in mapping.items():require(Path(p).is_file() and sha(p)==h,'source_changed:'+p)


def build(output=OUT,freeze_path=LINE/'stages/stage012_freeze.json'):
 from stage012_reuse import adjusted_events
 output=Path(output);require(not output.exists(),'immutable_output_exists');freeze=load(freeze_path)
 registry_path=LINE/'outputs/stage012_multistart/registry.json';reg=load(registry_path);oldreg=load(freeze['baseline_registry'])
 expected={s+'|C' for s in STARTS};require(set(reg['jobs'])==expected and all(j['status']=='validated' for j in reg['jobs'].values()),'23_validated_candidates')
 require(reg['financial_engine_batch_complete'] is True and reg['financial_replays_started']==9,'nine_new_financial_only')
 require(reg['counts']['fresh_validated']==9 and reg['counts']['proven_reuse_validated']==14,'9fresh14proof')
 require(reg['freeze_sha256']==sha(freeze_path),'registry_freeze')
 sources={str(Path(freeze_path).resolve()):sha(freeze_path),str(registry_path.resolve()):sha(registry_path),freeze['baseline_registry']:freeze['baseline_registry_sha256']}
 rows=[];daily=[];all_events=[]
 for start in STARTS:
  for variant,job in [('C_R150',oldreg['jobs'][start+'|C']),('C_R50',reg['jobs'][start+'|C'])]:
   limit=150000 if variant=='C_R150' else 50000;method='frozen_baseline' if limit==150000 else job['method'];path=Path(job['path'])
   folder='stage009_independent_receipts' if limit==150000 else 'stage012_independent_receipts';rp=LINE/'stages'/folder/f'{start}_C.json';audit=load(rp)
   require(audit['status']=='PASS_WITH_LIMITATIONS' and not audit['failures'],'independent_window_review');require(Path(audit['path']).resolve()==path.resolve(),'audit_source_path')
   pins=job.get('files_sha256') or job['source_files_sha256']
   for name in ['daily.csv','reserve_events.json','reserve_daily.csv','actual_strategy_settings.json','effective_parameters.json','entry_risk.csv']:
    p=path/name;h=sha(p);require(h==pins[str(p)]==audit['source_files_sha256'][str(p)],'exact_source:'+name);sources[str(p)]=h
   sources[str(rp.resolve())]=sha(rp);cp=Path(job['checkpoint']);sources[str(cp.resolve())]=sha(cp)
   raw=pd.read_csv(path/'daily.csv',float_precision='round_trip');events=load(path/'reserve_events.json')
   if method=='proven_nonbinding_reuse':events=adjusted_events(events)
   d=project_curve(raw,events,limit);m=summary_metrics(d);rounds=audit['metrics']['rounds'];open_mtm=float(audit['metrics']['open_round_net_mtm'])
   require(near(rounds['closed_net_pnl']+open_mtm,m['real_trading_net_pnl']),'closed_open_real_PnL')
   declared=pd.read_csv(path/'reserve_daily.csv',float_precision='round_trip');require(d.date.tolist()==declared.date.astype(str).str[:10].tolist(),'actual_source_calendar')
   for field in ['raw_account_equity','net_pnl','trading_account_equity','cumulative_transfer','transfer_amount']:
    require(near(d[field],declared[field]),'actual_trading_ledger_'+field)
   offset=100000 if method=='proven_nonbinding_reuse' else 0
   for field in ['reserve_balance','total_account_equity']:require(near(d[field],declared[field]-offset),'actual_reserve_projection_'+field)
   exhausted=d.reserve_balance.le(1e-6);margin=d.total_margin_exact*165/d.trading_account_equity.where(d.trading_account_equity.gt(0))
   row=dict(start=start,variant=variant,arm='C',version='reserve150k' if limit==150000 else 'reserve50k',funding_mode='external_topup',method=method,reserve_initial=limit,
    observation_only=start=='2026-01-01',**m,transfer_event_count=len(events),reserve_exhausted=bool(exhausted.any()),
    exhaustion_date=str(d.loc[exhausted,'date'].iloc[0]) if exhausted.any() else '',trading_margin_peak_pct=float(margin.max()) if margin.notna().any() else None,
    trading_margin_over100_days=int(margin.gt(100).sum()),source_path=str(path),independent_receipt=str(rp),open_round_net_mtm=open_mtm,**{'round_'+k:v for k,v in rounds.items()})
   rows.append(row);d=d.assign(start=start,variant=variant)
   daily.append(d[['start','variant','date','raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount','total_account_equity','slippage','commission','trade_count','total_margin_exact','account_nav','balance_drawdown_pct','reserve_initial']])
   all_events.extend(dict(e,start=start,variant=variant,method=method) for e in events)
 summary=pd.DataFrame(rows);curve=pd.concat(daily,ignore_index=True);si=summary.set_index(['start','variant'])
 require(len(summary)==46 and len(curve)==70998 and not curve.duplicated(['start','variant','date']).any(),'46summary70998daily')
 pairs=pd.DataFrame([pair_metrics(si.loc[(s,'C_R150')],si.loc[(s,'C_R50')],s,str(si.loc[(s,'C_R50'),'method'])) for s in STARTS])
 cohorts=[]
 for cohort in ['January','June','combined']:
  for scope in ['complete_ge_1y','observation_lt_1y']:
   g=pairs.loc[pairs.observation_only==(scope=='observation_lt_1y')]
   if cohort!='combined':g=g[g.cohort==cohort]
   cohorts.append(dict(cohort=cohort,scope=scope,n=len(g),fresh=int(g.method50.eq('fresh_engine').sum()),proof_reuse=int(g.method50.eq('proven_nonbinding_reuse').sum()),
    real_pnl_higher=int(g.real_pnl_comparison.eq(1).sum()),real_pnl_equal=int(g.real_pnl_comparison.eq(0).sum()),real_pnl_lower=int(g.real_pnl_comparison.eq(-1).sum()),
    dd_shallower=int(g.dd_comparison.eq(1).sum()),dd_equal=int(g.dd_comparison.eq(0).sum()),dd_deeper=int(g.dd_comparison.eq(-1).sum()),
    sharpe_higher=int(g.sharpe_comparison.eq(1).sum()),sharpe_equal=int(g.sharpe_comparison.eq(0).sum()),sharpe_lower=int(g.sharpe_comparison.eq(-1).sum())))
 verify_map(sources);output.mkdir(parents=True)
 tables={'summary.csv':summary,'paired.csv':pairs,'daily.csv':curve,'cohort_summary.csv':pd.DataFrame(cohorts),'reserve_events.csv':pd.DataFrame(all_events)}
 for name,frame in tables.items():frame.to_csv(output/name,index=False)
 doc=dict(schema='stage012-reserve50k-C-comparison-v1',status='INDEPENDENT_REVIEW_PENDING',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
  financial_source_head=freeze['source_head'],baseline_engine_source_head=load(freeze['baseline_freeze'])['source_head'],freeze_sha256=sha(freeze_path),starts=list(STARTS),variants=list(VARIANTS),cutoff=CUTOFF,
  financial_replays=9,proven_candidate_reuses=14,reused_baseline_controls=23,variant_windows=46,paired_windows=23,daily_points=70998,
  source_files_sha256=sources,promotion_decision='NO_PROMOTION',nav='E/150000: untransferred reserve excluded, deposits included',
  warning='Original C risk tiers retained; budgets200k/300k differ. Do not compare W returns as same-capital alpha. Fourteen candidate paths are certified nonbinding reuses, not new engines.')
 atomic_json(output/'comparison.json',safe(doc));atomic_json(output/'data_manifest.json',dict(files_sha256={str((output/n).resolve()):sha(output/n) for n in [*tables,'comparison.json']}))
 write_window_records(summary,pairs,freeze)
 return dict(report=str(output),summary_rows=46,pairs=23,daily_points=70998,new_financial=9,proof_reuse=14)


def row_values(m):
 return [m.start+('（观察）' if m.observation_only else ''),LABELS[m.variant],m.method,formatted(m.account_end_equity),formatted(m.account_growth_pct,'pct'),
  formatted(m.balance_max_dd_pct,'pct'),formatted(m.balance_sharpe,'ratio'),formatted(m.real_trading_net_pnl),formatted(m.total_transferred),formatted(m.off_account_reserve_end),
  formatted(m.total_slippage),str(int(m.modeled_fill_count)),formatted(m.round_win_rate_pct,'pct'),formatted(m.round_average_win),formatted(m.round_average_loss_abs),formatted(m.round_payoff_ratio,'ratio'),formatted(m.round_profit_factor,'ratio')]


HEADERS=['起点','版本','候选来源方法','期末交易权益','含入金增长','账户回撤','账户Sharpe','真实交易净盈亏','累计入金','场外余款','滑点','成交次数','胜率','平均盈利','平均亏损','盈亏比','PF']


def write_window_records(summary,pairs,freeze):
 folder=LINE/'stages/stage012_windows';folder.mkdir(exist_ok=True);si=summary.set_index(['start','variant'],drop=False)
 now=datetime.now(ZoneInfo('Asia/Shanghai'));baseline_head=load(freeze['baseline_freeze'])['source_head']
 for start in STARTS:
  a,b=si.loc[(start,'C_R150')],si.loc[(start,'C_R50')];p=folder/f'{now:%Y%m%d_%H%M}_stage012_C_{start.replace("-","")}.md'
  text=f'# Stage012 C：{start}独立起点5万/15万备用对照\n\n记录时间{now.isoformat()}；line_id=futures_weekly_short_ma_slope_gate，非重要突破、NO_PROMOTION。交易初资15万，空头底20过滤及原风险1.8%/6%/6%/2.5%保留；只有场外R15万→5万，参数新增/删除无，旧结果修改/删除无。\n\n候选方法={b.method}；若proven_nonbinding_reuse则0新金融，源为旧完整已审独立回测，逐check耦合证明通过；若fresh_engine则1新独立引擎。截止{CUTOFF}，实际{b.actual_start}—{b.actual_end}，{int(b.trading_days)}日。本阶段冻结源码HEAD={freeze["source_head"]}；原对照与证明复用的旧引擎HEAD={baseline_head}，候选源={b.source_path}，独审={b.independent_receipt}。\n\n'
  text+='|'+'|'.join(HEADERS)+'|\n|'+'|'.join(['---']*len(HEADERS))+'|\n'
  for row in [a,b]:text+='|'+'|'.join(row_values(row))+'|\n'
  text+=f'\n备用耗尽：原{bool(a.reserve_exhausted)}（{a.exhaustion_date or "未耗尽"}），5万版{bool(b.reserve_exhausted)}（{b.exhaustion_date or "未耗尽"}）。保证金×1.65/E峰值原{formatted(a.trading_margin_peak_pct,"pct")}、新{formatted(b.trading_margin_peak_pct,"pct")}；非正E日原{int(a.nonpositive_trading_equity_days)}、新{int(b.nonpositive_trading_equity_days)}。闭合PnL＋未平MTM原{a.round_closed_net_pnl}+{a.open_round_net_mtm}、新{b.round_closed_net_pnl}+{b.open_round_net_mtm}，均匹配真实净利。\n\nE/15万含入金，未入金不参与净值；总预算20/30万不同，不能混用W百分比当作同本金收益。复用依据源码R隔离与全部现金检查，不对绑定窗口裁剪旧曲线。调研资金流会计支持入金/盈亏分离，不能证明5万更优。运行前后过拟合风险均有（反复同历史、重叠窗口）；固定5万的资本需求验证有价值，不扫描其他金额救参。原零手续费/PIT/静态保证金/日线next-open与容量限制继承。后续仅完成全表独审和交付，不自动晋级。\n'
  p.write_text(text)


def write_reports(folder,summary,cohorts,figures,reviewed):
 state='独立复核通过（有局限）' if reviewed else '独立复核中'
 intro=f'{state}；NO_PROMOTION。原C分档风险与空头底部20%过滤保持。交易初资15万元，仅将场外备用15万改为5万。23起点至2026-10-29，候选9份真实新回放＋14份严格无绑定证明复用，对照23份旧已审独立回测；2026不足一年只观察。'
 warning='主净值＝交易权益E÷150,000，已补入计入、场外余款排除。账户增长/回撤/Sharpe含入金影响，真实交易PnL与补资分列。新旧总承诺预算20万/30万不同，不混用W百分比比较。'
 md='# Stage012：原风险C版，5万与15万场外备用\n\n'+intro+'\n\n'+warning+'\n\n'+cohorts.to_markdown(index=False)+'\n\n|'+'|'.join(HEADERS)+'|\n|'+'|'.join(['---']*len(HEADERS))+'|\n'
 rows=[]
 for _,m in summary.sort_values(['start','reserve_initial'],ascending=[True,False]).iterrows():
  values=row_values(m);md+='|'+'|'.join(values)+'|\n';rows.append('<tr data-start="'+m.start+'">'+''.join('<td>'+html.escape(v)+'</td>' for v in values)+'</tr>')
 md+='\n调研：Backtrader官方Fund Tracking及GitHub BackBroker区分现金流与真正业绩。https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/ ；https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py 。判断：较低备用承诺对无绑定窗口不改交易，对绑定窗口须真实重跑；不把更小总本金分母称alpha。过拟合风险仍有（金额由观察历史后指定、起点重叠），固定50k验证资本需求有价值，不继续扫金额救参。零手续费、非完整上市/PIT证明、静态保证金×1.65、日线next-open、盘口/券商购买力限制继承。无HTTP；file://自动交互受工具安全策略限制，未声称验收。\n'
 (folder/'report.md').write_text(md)
 titles=['2015年初全段：两线重合是已证明的相同交易路径','年初独立起点','年中独立起点','逐窗真实盈亏、回撤和补资差','备用金消耗与账户生存总览'];images=[]
 for i,(name,title) in enumerate(zip(figures,titles),1):
  enc=base64.b64encode((folder/name).read_bytes()).decode();images.append(f'<section id="fig{i}"><h2>{title}</h2><img alt="{title}" src="data:image/png;base64,{enc}"></section>')
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage012 原C风险：5万与15万备用金</title><style>body{margin:0;background:#f3f6fa;color:#172235;font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1450px;margin:auto;padding:28px 22px}h1{font-size:28px}h2{font-size:21px}section,.note{background:#fff;padding:20px;border:1px solid #dce3ed;border-radius:14px;margin:18px 0}.note{background:#eaf2fd;border-left:5px solid #2467a6}img{display:block;width:100%;height:auto}.muted{font-size:14px;color:#526177}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;white-space:nowrap;width:100%}th,td{padding:9px 12px;border-bottom:1px solid #e3e7ef;text-align:right}th{background:#edf2f8}td:first-child,td:nth-child(2),td:nth-child(3){text-align:left}tr:nth-child(even){background:#f9fbfd}select{font:inherit;padding:6px}a{color:#16528b}nav a{margin-right:18px}</style><main><h1>Stage012 · 原风险C版：5万与15万场外备用</h1>'''
 page+='<p>'+intro+'</p><div class="note">'+warning+'</div><p>普通1.8%，持仓骤增/放量持仓骤增6%，持仓下降2.5%；OI×2、方向增强×1.5/低量×0.5等保留。不使用Stage011统一1.8%版。</p><nav>'+''.join(f'<a href="#fig{i}">{t}</a>' for i,t in enumerate(titles,1))+'</nav>'+''.join(images)
 options='<option value="all">全部23个起点</option>'+''.join(f'<option value="{s}">{s}</option>' for s in STARTS)
 page+='<section><h2>完整数据：新回放与证明复用分列</h2><label>独立起点 <select id="startFilter">'+options+'</select></label><div class="scroll"><table><thead><tr>'+''.join('<th>'+v+'</th>' for v in HEADERS)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
 page+='<section class="muted">14个候选证明复用仍来自各自独立冷启动旧回测，未冒称新建引擎；9个受限起点真实重新计算手数、交易与盈亏，未裁剪旧曲线。历史窗口重叠、零手续费、数据/PIT、静态保证金和容量限制继续保留。固定金额验证有价值，但不自动晋级、不扫金额救参。文件全部内嵌，无HTTP/外部脚本/主动网络资源；自动file://交互未验收。调研：<a href="https://www.backtrader.com/blog/posts/2017-06-19-fund-tracking/fund-tracking/">Backtrader资金流</a>、<a href="https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py">GitHub实现</a>。</section></main><script>document.getElementById("startFilter").addEventListener("change",function(){document.querySelectorAll("tbody tr").forEach(r=>r.hidden=this.value!=="all"&&r.dataset.start!==this.value);});</script></html>'
 (folder/HTML_NAME).write_text(page)


def render(output=OUT,review=None):
 from stage012_plots import render_five
 output=Path(output);locked=load(output/'data_manifest.json')['files_sha256'];verify_map(locked);reviewed=review is not None
 if reviewed:
  r=load(review);require(r['status']=='PASS_WITH_LIMITATIONS' and not r['failures'] and r['data_files_sha256']==locked,'independent_data_review');verify_map(r['audited_code_sha256'])
 summary=pd.read_csv(output/'summary.csv',float_precision='round_trip');paired=pd.read_csv(output/'paired.csv',float_precision='round_trip');daily=pd.read_csv(output/'daily.csv',float_precision='round_trip');cohort=pd.read_csv(output/'cohort_summary.csv')
 figures=render_five(summary,paired,daily,reviewed=reviewed);folder=output if reviewed else output/'review_pending';folder.mkdir(exist_ok=True)
 for name,fig in figures.items():fig.savefig(folder/name,dpi=160,bbox_inches='tight');fig.clear()
 write_reports(folder,summary,cohort,list(figures),reviewed)
 atomic_json(folder/'delivery_receipt.json',dict(status='PASS_WITH_LIMITATIONS' if reviewed else 'INDEPENDENT_REVIEW_PENDING',data_files_sha256=locked,
  figure_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in figures},report_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in [HTML_NAME,'report.md']},
  independent_review_sha256=sha(review) if reviewed else None,financial_replays=0,market_downloads=0,production_accesses=0,browser_interaction_verified=False,promotion_decision='NO_PROMOTION'))
 return dict(report=str(folder),reviewed=reviewed)


if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['build','render'],required=True);p.add_argument('--output',type=Path,default=OUT);p.add_argument('--review',type=Path);a=p.parse_args()
 print(json.dumps(safe(build(a.output) if a.mode=='build' else render(a.output,a.review)),ensure_ascii=False,indent=2))
