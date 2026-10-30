"""Final read-only acceptance and atomic Chinese delivery for Stage008.

This tool never invokes an engine, downloader, report generator or production
service. The delivery manifest is the exclusive last-published commit marker.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,csv,hashlib,json,math,os,tempfile,shutil

LINE=Path(__file__).resolve().parents[1];STAGES=LINE/'stages'
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
END='2026-10-29'
FIGURES=('01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_start_to_cutoff_heatmaps.png','05_cohort_summary_weakest.png')
FREEZE=STAGES/'stage008_freeze.json';REGISTRY=LINE/'outputs/stage008_multistart/registry.json'
CACHE=LINE/'outputs/stage008_derived/cache';RECEIPTS=STAGES/'stage008_independent_receipts'
REPORT=LINE/'artifacts/stage008_multistart';REVIEWED=LINE/'artifacts/stage008_multistart_reviewed'
REVIEW=STAGES/'stage008_independent_final.json';VISUAL=STAGES/'stage008_reviewed_visual_receipt.json'

def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def need(v,label):
 if not v:raise ValueError('stage008_delivery:'+label)
def near(a,b):
 if a is None or b is None:return a is None and b is None
 try:return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6)
 except (TypeError,ValueError):return False
def compare(a,b):
 need(a is not None and b is not None and math.isfinite(float(a)) and math.isfinite(float(b)),'finite_comparison')
 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7):return 0
 return 1 if float(a)>float(b) else -1
def truth(x):
 if type(x) is bool:return x
 if x=='True':return True
 if x=='False':return False
 raise ValueError('stage008_delivery:explicit_boolean_required')
def csv_rows(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def maturity(start):return END>=str(int(start[:4])+1)+start[4:]
def number(x,digits=2):
 if x is None:return '未定义/N/A'
 v=float(x)
 if not math.isfinite(v):return '未定义/N/A'
 return f'{v:,.{digits}f}'
def link(p):return '['+Path(p).name+']('+str(Path(p).resolve())+')'

class SourceBook:
 def __init__(self):self.files={}
 def add(self,p,digest=None):
  p=str(Path(p).resolve());need(Path(p).is_file(),'missing_source:'+p)
  if p in self.files:
   if digest is not None:need(self.files[p]==digest,'conflicting_source_digest:'+p)
   return self.files[p]
  actual=sha(p);need(digest is None or actual==digest,'source_sha_mismatch:'+p);self.files[p]=actual;return actual
 def add_map(self,items,base=None):
  need(isinstance(items,dict),'source_map_required')
  for name,digest in items.items():
   p=Path(name)
   if not p.is_absolute() and base is not None:p=Path(base)/p
   self.add(p,digest)
 def verify(self):
  for p,digest in self.files.items():need(Path(p).is_file() and sha(p)==digest,'source_changed_during_finalization:'+p)

def require_inventory(freeze,registry,receipt_keys,cache_keys):
 expected={s+'|'+a for s in STARTS for a in ['A','C']}
 need(freeze.get('starts')==list(STARTS) and freeze.get('cutoff')==END,'frozen_exact23_starts')
 jobs=registry.get('jobs',{});need(set(jobs)==expected and len(jobs)==46,'exact46_registry')
 need(all(j.get('status')=='validated' for j in jobs.values()),'all46_validated')
 need(registry.get('financial_replays_started')==42 and registry.get('financial_engine_batch_complete') is True,'exact42_completed_engines')
 need(sum(j.get('reused') is True for j in jobs.values())==4 and all(type(j.get('reused')) is bool for j in jobs.values()),'four_reused42_fresh')
 need(set(receipt_keys)==expected and len(receipt_keys)==46,'exact46_independent_receipts')
 need(set(cache_keys)==expected and len(cache_keys)==46,'exact46_financial_caches')
 return expected

def require_final_review(review,freeze_sha,comparison_sha):
 need(str(review.get('status','')).startswith('PASS'),'final_independent_review_must_pass')
 need(all(review.get(k)==0 for k in ['P0','P1','P2','failures']),'final_review_no_open_findings')
 need(review.get('freeze_sha256')==freeze_sha,'final_review_freeze_identity')
 need(review.get('arm_windows')==46,'final_review46_arm_windows')
 count=review.get('paired_windows',review.get('independent_pairs'))
 need(count==23,'final_review23_pairs')
 need(review.get('report_comparison_sha256')==comparison_sha,'final_review_current_report_binding')

def require_visual(visual,review_sha,reviewed_dir):
 need(visual.get('independent_review_sha256')==review_sha,'visual_locked_review_binding')
 actual=visual.get('reviewed_figures_sha256',{});expected={str((Path(reviewed_dir)/n).resolve()) for n in FIGURES}
 need(isinstance(actual,dict) and set(actual)==expected,'exact_five_reviewed_images')
 for p,h in actual.items():need(Path(p).is_file() and sha(p)==h,'reviewed_image_sha:'+p)

def require_report_rows(ledgers,summary,pairs):
 expected={(s,a) for s in STARTS for a in ['A','C']}
 keys=[(r['start'],r['arm']) for r in summary]
 need(len(keys)==46 and len(set(keys))==46 and set(keys)==expected,'summary_exact46')
 pkeys=[r['start'] for r in pairs];need(len(pkeys)==23 and len(set(pkeys))==23 and set(pkeys)==set(STARTS),'paired_exact23')
 for row in summary:
  key=(row['start'],row['arm']);d=ledgers[key];m=d['metrics'];eligible=maturity(row['start'])
  need(truth(row['vote_eligible'])==eligible and truth(row['observation_only']) is (not eligible),'summary_vote_scope:'+str(key))
  need(row['cohort']==('January' if row['start'][5:7]=='01' else 'June'),'summary_cohort')
  for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count']:
   need(near(row[k],m[k]),'summary_metric:'+str(key)+k)
 for row in pairs:
  start=row['start'];eligible=maturity(start);a=ledgers[(start,'A')]['metrics'];c=ledgers[(start,'C')]['metrics']
  need(truth(row['vote_eligible'])==eligible and truth(row['observation_only']) is (not eligible),'paired_vote_scope:'+start)
  need(row['cohort']==('January' if start[5:7]=='01' else 'June'),'paired_cohort')
  for side,m in [('A',a),('C',c)]:
   for field,key in [('end_equity','end_equity'),('return_pct','total_return_pct'),('max_dd_pct','max_dd_pct'),('sharpe','sharpe')]:need(near(row[side+'_'+field],m[key]),'paired_metric:'+start+side+field)
  gates=dict(equity_gate=compare(c['end_equity'],a['end_equity'])>0,dd_gate=compare(c['max_dd_pct'],a['max_dd_pct'])>=0,sharpe_gate=compare(c['sharpe'],a['sharpe'])>=0)
  for k,v in gates.items():need(truth(row[k])==v,'paired_gate:'+start+k)
  need(truth(row['three_gate_pass'])==all(gates.values()),'paired_three_gate:'+start)
 need(sum(maturity(s) for s in STARTS)==22 and [s for s in STARTS if not maturity(s)]==['2026-01-01'],'22mature_one_observation')

def check_receipt_and_cache(book,freeze,freeze_sha,start,arm,job,receipt,cache_dir):
 key=start+'|'+arm;path=Path(job['path']).resolve();checkpoint=Path(job['checkpoint']).resolve();cp=load(checkpoint);d=load(cache_dir/'ledger.json')
 book.add(checkpoint);book.add_map(job['files_sha256'])
 need((receipt.get('requested_start'),receipt.get('arm'),receipt.get('end'))==(start,arm,END),'receipt_window:'+key)
 need(receipt.get('status')=='PASS_WITH_LIMITATIONS' and all(receipt.get(k)==0 for k in ['P0','P1','P2','failures']),'receipt_pass:'+key)
 need(receipt.get('freeze_sha256')==freeze_sha and receipt.get('frozen_source_head')==freeze['source_head'],'receipt_frozen_identity:'+key)
 need(Path(receipt['path']).resolve()==path==Path(cp['path']).resolve(),'receipt_exact_run_path:'+key)
 need(receipt.get('reused') is job['reused'] and cp.get('reused') is job['reused'],'receipt_reuse_identity:'+key)
 if job['reused']:need(str(path)==str(Path(freeze['reuse_runs'][key]).resolve()),'exact_reused_run:'+key)
 else:
  expected=LINE/'outputs'/f"stage008_{arm}_{start.replace('-','')}_attempt001";need(path==expected.resolve(),'fresh_run_assigned_path:'+key)
  pre=load(path/'preflight.json');need(pre.get('freeze_sha256')==freeze_sha and pre.get('frozen_source_head')==freeze['source_head'],'fresh_run_freeze_identity:'+key)
 need(receipt['source_files_sha256']==job['files_sha256']==cp['files_sha256'],'receipt_checkpoint_snapshot:'+key)
 need({str(p.resolve()) for p in path.iterdir() if p.is_file()}==set(job['files_sha256']),'financial_output_file_set:'+key)
 expected_key=hashlib.sha256(json.dumps(dict(source_head=freeze['source_head'],freeze_sha256=freeze_sha,cutoff=END,arm=arm,start=start),sort_keys=True).encode()).hexdigest()
 need(cp.get('checkpoint_key')==job['checkpoint_key']==expected_key,'checkpoint_exact_key:'+key)
 need(cp.get('freeze_sha256')==job.get('freeze_sha256')==freeze_sha and cp.get('source_head')==job.get('source_head')==freeze['source_head'],'checkpoint_freeze_source_identity:'+key)
 need(d.get('key')==key and d.get('start')==start and d.get('arm')==arm and d.get('end')==END and d.get('freeze_sha256')==freeze_sha,'cache_identity:'+key)
 need(d['checkpoint_key']==expected_key and d['checkpoint_sha256']==sha(checkpoint) and d['attempt_snapshot']==job['files_sha256'] and Path(d['source_path']).resolve()==path,'cache_checkpoint_binding:'+key)
 cm=load(cache_dir/'delivery_manifest.json');book.add(cache_dir/'delivery_manifest.json');book.add_map(cm['files_sha256'],cache_dir);book.add_map(d['source_files_sha256']);book.add_map(d['derivation_sources_sha256']);book.add_map(load(path/'input_manifest.json'))
 terminal=load(path/'terminal.json');need(terminal.get('status')=='completed_pending_independent_review' and terminal.get('error') is None and load(path/'postflight.json').get('inputs_unchanged') is True,'terminal_postflight:'+key)
 pre=d['preflight'];settings=d['settings'];need(pre['start']==start and pre['end']==END and pre['data_identity']==freeze['data_identity'],'cache_actual_preflight:'+key)
 need(pre.get('short_ma_slope_gate_enabled') is False and pre.get('long_ma_slope_gate_enabled',False) is False and pre.get('long_price_range_gate_enabled',False) is False and pre.get('daily_addon_enabled') is False,'no_long_or_MA_or_addon:'+key)
 need(len(settings)==1 and settings[0]['actual'].get('trade_start_date')==start and settings[0]['actual'].get('capital_base')==150000,'actual_cold_start_setting:'+key)
 need(pre.get('universe_product_count')==19 and pre.get('ready_need')==21 and pre.get('storage_capacity')==41,'original19_warmup_contract:'+key)
 cold=receipt['cold_start_warmup_evidence'];need(cold.get('requested_start')==start and near(cold.get('first_equity'),150000) and cold.get('first_day_financial_positions')==0,'independent_cold_start:'+key)
 window=d['window'];need(window['vote_eligible']==maturity(start) and window['observation_only'] is (not maturity(start)) and window['actual_first_day']==job['actual_start'] and window['trading_days']==job['trading_days'],'cache_exact_window:'+key)
 proofs=d['gate_certificates']
 for side in ['short','long']:
  g=proofs.get(side+'_ma_slope_acceptance.json')
  if g is not None:need(g.get('accepted') is True and g.get('enabled') is False and g.get('applied_block_count')==0,'actual_MA_off:'+key+side)
 g=proofs.get('long_price_range_acceptance.json')
 if g is not None:need(g.get('accepted') is True and g.get('enabled') is False and g.get('applied_block_count')==0,'actual_long_off:'+key)
 g=proofs.get('short_price_range_acceptance.json')
 if arm=='C':need(g is not None and g.get('accepted') is True and g.get('enabled') is True and g.get('threshold_fraction')==.2 and g.get('includes_signal_day') is True,'actual_short_bottom20_on:'+key)
 elif g is not None:need(g.get('accepted') is True and g.get('enabled') is False and g.get('applied_block_count')==0,'actual_A_range_off:'+key)
 m=d['metrics'];rm=receipt['metrics']
 need(m.get('initial_capital')==150000 and m.get('actual_start')==job['actual_start'] and m.get('actual_end')==END,'metrics_exact_financial_window:'+key)
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage']:need(near(m[k],rm[k]),'independent_metric:'+key+k)
 need(near(m['modeled_fill_count'],rm['total_trade_count']),'independent_fill_count:'+key)
 rounds=d['accounting']['complete_contract_rounds']
 for k in ['count','wins','losses','flat','win_rate_pct','average_win','average_loss_abs','payoff_ratio','profit_factor','closed_net_pnl']:need(near(rounds[k],rm['rounds'][k]),'independent_round_metric:'+key+k)
 need(near(d['accounting']['open_round_net_mtm'],rm['open_round_net_mtm']) and near(rounds['closed_net_pnl']+d['accounting']['open_round_net_mtm'],m['net_pnl']),'closed_plus_open_bridge:'+key)
 auditor=LINE/'tools/stage008_independent_window.py';book.add(auditor,receipt['auditor_source_sha256']);return d,terminal

def cohort_stats(ledgers,pairs):
 result={}
 for cohort in ['January','June','combined']:
  for eligible in [True,False]:
   chosen=[p for p in pairs if truth(p['vote_eligible'])==eligible and (cohort=='combined' or p['cohort']==cohort)];starts=[p['start'] for p in chosen];row=dict(windows=len(chosen),vote_windows=len(chosen) if eligible else 0,observation_windows=0 if eligible else len(chosen),return_wins=sum(compare(ledgers[(s,'C')]['metrics']['end_equity'],ledgers[(s,'A')]['metrics']['end_equity'])>0 for s in starts) if eligible else 0,return_ties=sum(compare(ledgers[(s,'C')]['metrics']['end_equity'],ledgers[(s,'A')]['metrics']['end_equity'])==0 for s in starts) if eligible else 0,return_losses=sum(compare(ledgers[(s,'C')]['metrics']['end_equity'],ledgers[(s,'A')]['metrics']['end_equity'])<0 for s in starts) if eligible else 0,dd_wins=sum(compare(ledgers[(s,'C')]['metrics']['max_dd_pct'],ledgers[(s,'A')]['metrics']['max_dd_pct'])>0 for s in starts) if eligible else 0,sharpe_wins=sum(compare(ledgers[(s,'C')]['metrics']['sharpe'],ledgers[(s,'A')]['metrics']['sharpe'])>0 for s in starts) if eligible else 0,three_gate_pass_count=sum(truth(p['three_gate_pass']) for p in chosen) if eligible else 0)
   for arm in ['A','C']:
    selected=[ledgers[(s,arm)] for s in starts];row[arm+'_negative_return_count']=sum(d['metrics']['total_return_pct']<0 for d in selected);row[arm+'_positive_return_count']=sum(d['metrics']['total_return_pct']>0 for d in selected);row[arm+'_flat_return_count']=sum(d['metrics']['total_return_pct']==0 for d in selected);row[arm+'_survival_failure_count']=sum(d['metrics']['nonpositive_equity_days']>0 or d['metrics']['end_equity']<=0 for d in selected);row[arm+'_configured_margin_failure_count']=sum(d['risk']['actual_margin_to_equity_max_pct'] is None or d['risk']['nonpositive_equity_risk_ratio_undefined_days']>0 or d['risk']['actual_margin_over100_days']>0 for d in selected)
   result[(cohort,'complete_ge_1y' if eligible else 'observation_lt_1y')]=row
 return result

def collect_state():
 book=SourceBook();freeze=load(FREEZE);freeze_sha=book.add(FREEZE);registry=load(REGISTRY);book.add(REGISTRY)
 receipt_paths={p.stem[:-2]+'|'+p.stem[-1]:p for p in RECEIPTS.glob('*.json')}
 cache_keys={s+'|'+a for s in STARTS for a in ['A','C'] if (CACHE/(s.replace('-','')+'_'+a)/'ledger.json').is_file()}
 require_inventory(freeze,registry,set(receipt_paths),cache_keys);need(registry.get('freeze_sha256')==freeze_sha and registry.get('source_head')==freeze['source_head'],'registry_freeze_binding');book.add_map(freeze['source_files_sha256']);book.add_map(freeze['reused_delivery_sha256'])
 ledgers={};terminals={};receipts={};reference_settings=reference_effective=None
 for start in STARTS:
  for arm in ['A','C']:
   key=start+'|'+arm;rp=receipt_paths[key];book.add(rp);r=load(rp);d,t=check_receipt_and_cache(book,freeze,freeze_sha,start,arm,registry['jobs'][key],r,CACHE/(start.replace('-','')+'_'+arm));ledgers[(start,arm)]=d;terminals[(start,arm)]=t;receipts[(start,arm)]=(rp,r)
   if reference_settings is None:reference_settings=d['normalized_settings'];reference_effective=d['effective']
   need(d['normalized_settings']==reference_settings and d['effective']==reference_effective,'only_start_changes_across_windows')
   if arm=='C':need(d['settings']==ledgers[(start,'A')]['settings'] and d['effective']==ledgers[(start,'A')]['effective'],'same_pair_real_settings:'+start)
 summary=csv_rows(REPORT/'summary.csv');pairs=csv_rows(REPORT/'paired.csv');require_report_rows(ledgers,summary,pairs);cohorts=csv_rows(REPORT/'cohort_summary.csv');expected_stats=cohort_stats(ledgers,pairs)
 need(len(cohorts)==6 and {(r['cohort'],r['sample']) for r in cohorts}==set(expected_stats),'six_exact_cohort_rows')
 for row in cohorts:
  stats=expected_stats[(row['cohort'],row['sample'])]
  for key,value in stats.items():need(near(row[key],value),'cohort_count:'+row['cohort']+row['sample']+key)
 comparison=load(REPORT/'comparison.json');need(comparison.get('arm_windows')==46 and comparison.get('independent_pairs')==23 and comparison.get('complete_vote_pairs')==22 and comparison.get('observation_pairs')==1 and comparison.get('expected_engine_replays')==42 and comparison.get('reused_arms')==4,'report_complete_counts');need(comparison.get('freeze_sha256')==freeze_sha and comparison.get('financial_source_head')==freeze['source_head'] and comparison.get('five_figures')==list(FIGURES),'report_frozen_identity_and_figures')
 need(comparison.get('promotion_decision')=='NO_PROMOTION','research_no_promotion')
 book.add_map(comparison['source_files_sha256']);book.add_map(load(REPORT/'source_hashes.json'));manifest=load(REPORT/'delivery_manifest.json');book.add_map(manifest['files_sha256'],REPORT)
 for p in REPORT.rglob('*'):
  if p.is_file():book.add(p)
 review=load(REVIEW);require_final_review(review,freeze_sha,sha(REPORT/'comparison.json'));review_sha=book.add(REVIEW);visual=load(VISUAL);require_visual(visual,review_sha,REVIEWED);book.add(VISUAL);book.add_map(visual['reviewed_figures_sha256'])
 for p in list(STAGES.glob('*stage008*'))+list(LINE.joinpath('tools').glob('*stage008*')):
  if p.is_file() and p.name!='stage008_delivery_manifest.json':book.add(p)
 for p in RECEIPTS.iterdir():
  if p.is_file():book.add(p)
 for p in REGISTRY.parent.rglob('*'):
  if p.is_file():book.add(p)
 for p in REVIEWED.rglob('*'):
  if p.is_file():book.add(p)
 return dict(book=book,freeze=freeze,freeze_sha=freeze_sha,registry=registry,ledgers=ledgers,terminals=terminals,receipts=receipts,summary=summary,pairs=pairs,cohorts=cohorts,cohort_stats=expected_stats,comparison=comparison,review=review,review_sha=review_sha,visual=visual,weakest=csv_rows(REPORT/'weakest_windows.csv'))

def render_window(d,job,terminal,receipt_path,receipt_sha,checkpoint_sha,now):
 m=d['metrics'];r=d['accounting']['complete_contract_rounds'];a=d['accounting'];risk=d['risk'];w=d['window'];arm=d['arm'];start=d['start'];reused=job['reused'];mode='复用已完成并重新验收的冻结账本，本批未重跑此引擎' if reused else '本批新建独立进程/引擎，从本起点15万元空仓起跑'
 return f"""# Stage008 独立窗口 {start} / {arm}

- line_id：futures_weekly_short_ma_slope_gate；模式day；登记时间{now.isoformat()}；非重要突破，离线研究/NO_PROMOTION。
- 回测类别：{mode}。源回放真实时间：{terminal.get('started_at','未记录')}—{terminal.get('completed_at','未记录')}；登记时间不是源回测执行时间。
- 组别：{'A原始无价格门' if arm=='A' else 'C仅空头历史底部20%过滤'}；请求起点{start}，实际{m['actual_start']}—{m['actual_end']}，{int(m['trading_days'])}交易日；初始150000、空仓，无外部现金流。{'完整>=1年，参与配对投票' if w['vote_eligible'] else '不足1年观察窗口，只展示、不投票'}。
- 参数：原19品种、动态底仓、不加仓，原MA5/10/20信号/退出保持，多空新增MA斜率过滤关闭，多头价格过滤关闭。C仅short_case1a按信号日close<=L+0.2(H-L)拒开；L/H来自同真实合约同physical epoch、日期<=信号日的本地已有有效日线。A此门关闭但可能保留would诊断。换月/平仓/风险退出不加过滤。
- 成本/风险：手续费0、原滑点、静态交易所保证金×1.65；21周ready/41storage，原AI/MACD/半R/C2/RSI退出/short_case2关闭，原资金/止损/保证金门保留。
- 预热只更新指标，不承接旧仓或收益；每个窗口重新创建引擎。不是长曲线切片，不把重叠窗口视为统计独立样本。

| 指标 | 数值 |
|---|---:|
| 期末权益 | {number(m['end_equity'])}元 |
| 净盈亏 | {number(m['net_pnl'])}元 |
| 总收益 | {number(m['total_return_pct'],6)}% |
| 最大回撤 | {number(m['max_dd_pct'],6)}% |
| Sharpe | {number(m['sharpe'],6)} |
| 总滑点 | {number(m['total_slippage'])}元 |
| 手续费 | {number(m.get('total_commission',0))}元 |
| 成交笔数，开平分别计 | {int(m['modeled_fill_count'])} |
| 完整已平周期 | {int(r['count'])} |
| 胜/负/平 | {int(r['wins'])}/{int(r['losses'])}/{int(r['flat'])} |
| 完整周期胜率 | {number(r['win_rate_pct'],6)}% |
| 平均盈利/平均亏损绝对额 | {number(r['average_win'])}/{number(r['average_loss_abs'])}元 |
| 平均盈亏比 | {number(r['payoff_ratio'],6)} |
| Profit Factor，总赢/总亏 | {number(r['profit_factor'],6)} |
| 已平完整周期净额 | {number(r['closed_net_pnl'])}元 |
| 末未平周期净盯市 | {number(a['open_round_net_mtm'])}元 |
| 末未平周期数 | {int(a.get('open_round_count',0))} |
| 配置保证金×1.65/权益峰值 | {number(risk['actual_margin_to_equity_max_pct'],6)}% |
| 配置占用>100%天数 | {int(risk['actual_margin_over100_days'])} |

- 账本来源：{link(job['path'])}；派生缓存{link(CACHE/(start.replace('-','')+'_'+arm)/'ledger.json')}；独审{link(receipt_path)}。
- 独审收据SHA：{receipt_sha}；完整checkpoint SHA：{checkpoint_sha}；全部输入/输出SHA由最终delivery manifest绑定，未修改源账本。
- 运行前/后过拟合判断：有历史内选择风险，固定20%、固定23起点，无结果后改规则或筛窗；此单窗不能代表跨周期有效。
- 继续价值：本次固定独立起点验证有价值，是否继续按完整23配对及成熟January/June cohort共同判断，不用单一赢家救失败。
- 局限：已有缓存不证明完整上市历史/PIT，已知缺口分类保留；零手续费、静态规格/保证金及无真实盘口/容量资格。配置风险不等于实际券商历史风险。
- 本窗新增/修改参数仅请求起点与组别开关；旧策略/旧回测修改或删除：无。源结果经济失败照常保留；无额外下载/生产/CTP/订单API。
- TODO：冻结本窗，纳入总stage与23配对报告；不单独调参或晋级。
"""

def render_summary(state,now,stage_path):
 d=state;ledgers=d['ledgers'];pairs=d['pairs'];stats=d['cohort_stats'];comp=d['comparison'];review=d['review'];fullA=ledgers[('2015-01-01','A')]['metrics'];fullC=ledgers[('2015-01-01','C')]['metrics'];roundA=ledgers[('2015-01-01','A')]['accounting']['complete_contract_rounds'];roundC=ledgers[('2015-01-01','C')]['accounting']['complete_contract_rounds'];cohort_lines=[]
 for name,cn in [('January','年初'),('June','年中6月1日'),('combined','合并')]:
  row=stats[(name,'complete_ge_1y')];cohort_lines.append(f"| {cn} | {row['windows']} | {row['return_wins']}/{row['return_ties']}/{row['return_losses']} | {row['dd_wins']} | {row['sharpe_wins']} | {row['three_gate_pass_count']} | {row['A_negative_return_count']}/{row['C_negative_return_count']} | {row['C_survival_failure_count']} | {row['C_configured_margin_failure_count']} |")
 pair_lines=[]
 bystart={p['start']:p for p in pairs}
 for start in STARTS:
  p=bystart[start];a=ledgers[(start,'A')]['metrics'];c=ledgers[(start,'C')]['metrics'];star='*' if not maturity(start) else '';pair_lines.append(f"| {start}{star} | {number(a['end_equity'],0)}/{number(c['end_equity'],0)} | {number(a['total_return_pct'])}%/{number(c['total_return_pct'])}% | {number(a['max_dd_pct'])}%/{number(c['max_dd_pct'])}% | {number(a['sharpe'],3)}/{number(c['sharpe'],3)} | {'通过' if truth(p['three_gate_pass']) else '未通过'} |")
 weak_lines=[]
 for row in d['weakest']:
  if row['scope']=='complete_ge_1y' and row['arm']=='C':weak_lines.append(f"| {row['metric']} | {row['start']} | {number(row['value'],6)} |")
 figlinks='\n'.join(f'{i}. {link(REVIEWED/name)}' for i,name in enumerate(FIGURES,1))
 decision=comp['strategy_verdict'];continue_text='是，有进一步固定样本外/成本资格验证价值，但当前仍非正式晋级证明。' if decision=='PASS_USER_SCOPE_COMPLETE_WINDOWS_ONLY' else '否，不继续沿本规则调参或谋求晋级；本轮固定验证本身有价值且已完成。若另做研究，应先固定归因合同或等待新样本外数据，不挑年份、扫阈值救结果。'
 return f"""# Stage008 去掉多头过滤：23独立起点至同截止验证

- line_id=futures_weekly_short_ma_slope_gate；模式day；记录{now.isoformat()}；工作区{LINE.parents[2]}；是否重要突破：否，固定研究验证，不自动晋级。
- 结论：{decision} / NO_PROMOTION。独审{review['status']}，P0/P1/P2={review['P0']}/{review['P1']}/{review['P2']}，无未解决失败。财务/来源通过不等于策略稳健或生产资格。
- 用户明确范围：2015—2025每年1月1日和6月1日、另2026年1月1日至2026-10-29，共23独立窗口/46臂窗；年中按仓库6月1日定义。原始A与仅空头底20%C各15万元空仓起跑，42次新引擎+4份已审精确复用。复用窗口是2015 A/C及2020 A/C，其源回放时间逐窗保留，未冒称新跑。
- 本轮不是默认固定1/2/3年周期，也不是当前正式A多周期晋级：用户指定所有起点到相同截止，原19历史研究对照。更短2026Jan观察只展示、不投票；22个>=1年窗口参与投票（January11、June11）。窗口相互重叠，是独立财务状态，不是统计独立样本或新OOS。
- 冻结金融源HEAD：{d['freeze']['source_head']}；freeze SHA：{d['freeze_sha']}；最新完整交易日2026-10-29，未使用未完成10/30日线。
- 本次规则/运行入口变更冻结时间：{d['freeze']['created_at']}；交付中文记录时间：{now.isoformat()}，两者与各terminal的真实回放执行时间分别保留。

## 本次变更、参数与执行

- 删除：从本轮候选去掉Stage007多头顶部20%过滤/新高例外wrapper，直接复用Stage005/006仅空头原类；原Stage007代码和负结果不删除。多空新增均线斜率门均关闭，多头无新增价格门。
- 新增：23请求起点、独立进程队列、源绑定checkpoint、46独审收据与逐窗中文记录、23配对表/6cohort行/五图及最终交付。修改参数仅起点；原品种/风险/成本/退出/20%阈值不变。旧回测结果修改/删除：无。
- C：P=信号日close，L/H为同真实合约同physical epoch、date<=signal_date全部已有有效日线极值；P<=L+0.2(H-L)不新开空，flat range拒开、缺源失败。A此门关闭但部分旧源保留would诊断。多头、换月、退出、原MA信号和全部父级资金风控保持。
- 原19池、动态底仓、不加仓、150000初资，原滑点、手续费0、静态margin×1.65，21周ready/41storage；AI/MACD/半R/C2/RSI退出/short_case2关闭。无现金流转移，各窗口不承接其他账户权益或仓位；预热只更新指标。
- 先验收全2015复用A/C，再跑2015June A/C canary并独审，批准后才批量其余；经济负收益/DD40/deployable失败不会停止或重试，只有数据/代码/完整性失败才停止派发。所有未满批结果只算checkpoint，不是最终报告。
- 每次回放真实起止分钟、参数、结果与source hash见{link(STAGES/'stage008_windows')}的46记录；运行队列/完成时间在{link(REGISTRY)}和各terminal。

## 全周期与成熟cohort

| 指标 | A无价格门 | C仅空头底20% |
|---|---:|---:|
| 2015首个交易日 | {fullA['actual_start']} | {fullC['actual_start']} |
| 期末权益 | {number(fullA['end_equity'])} | {number(fullC['end_equity'])} |
| 总收益 | {number(fullA['total_return_pct'],6)}% | {number(fullC['total_return_pct'],6)}% |
| 最大回撤 | {number(fullA['max_dd_pct'],6)}% | {number(fullC['max_dd_pct'],6)}% |
| Sharpe | {number(fullA['sharpe'],6)} | {number(fullC['sharpe'],6)} |
| 总滑点 | {number(fullA['total_slippage'])} | {number(fullC['total_slippage'])} |
| 成交笔数 | {int(fullA['modeled_fill_count'])} | {int(fullC['modeled_fill_count'])} |
| 完整周期胜率 | {number(roundA['win_rate_pct'],6)}% | {number(roundC['win_rate_pct'],6)}% |
| 平均盈利/平均亏损绝对额 | {number(roundA['average_win'])}/{number(roundA['average_loss_abs'])} | {number(roundC['average_win'])}/{number(roundC['average_loss_abs'])} |
| 平均盈亏比 | {number(roundA['payoff_ratio'],6)} | {number(roundC['payoff_ratio'],6)} |
| Profit Factor | {number(roundA['profit_factor'],6)} | {number(roundC['profit_factor'],6)} |

成熟窗三门：C权益严格更高、DD不更差、Sharpe不更低，权益相同不通过；CSV浮点只按已声明容差判序列化微扰，不放行实质漂移。

| cohort | 完整窗口 | 收益胜/平/负 | DD严格胜 | Sharpe严格胜 | 三门全过 | A/C负收益窗 | C生存失败窗 | C配置占用失败窗 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(cohort_lines)}

不同窗口长度不能直接平均总收益当预期收益。聚合只作配对计数、cohort分层、中位/最差DD/Sharpe和生存/占用描述；不以单一赢家覆盖失败窗口。

## 23配对完整表

以下每格A/C顺序；*仅2026年初不足1年观察、不投票。三门标记为展示事实，不会把观察窗计入成熟胜率。

| 请求起点 | 期末权益A/C | 总收益A/C | 最大回撤A/C | SharpeA/C | 三门 |
|---|---:|---:|---:|---:|---|
{chr(10).join(pair_lines)}

## C最弱或压力最高的成熟窗口

| 指标 | 起点→同截止 | 数值 |
|---|---|---:|
{chr(10).join(weak_lines)}

保证金字段只代表静态交易所保证金×1.65/权益，legacy broker10为×1.1，不得称实际历史券商保证金或生产可承载。未平净盯市保留在权益，已平/未平桥和胜率/均盈亏/平均盈亏比/Profit Factor见逐窗记录及summary；不能只删某臂未平来救比较，也不能将共享资本路径差叫过滤器独立alpha。

## 五图、验收与来源

{figlinks}

- 表格与decision：{link(REPORT/'summary.csv')}、{link(REPORT/'paired.csv')}、{link(REPORT/'cohort_summary.csv')}、{link(REPORT/'weakest_windows.csv')}、{link(REPORT/'decision.json')}；原报告{link(REPORT/'report.md')}。
- 独审{link(REVIEW)}、46独审收据{link(RECEIPTS)}；已审图收据{link(VISUAL)}绑定最终独审SHA {d['review_sha']}。原pending图和comparison不修改。
- 全46状态validated、23配对、46财务cache及来源/输入/输出SHA、实际start/初资/零库存、同窗参数、长门/MA关闭、C短门、逐笔/逐日/库存/成本/末值、所有曲线点已验收。根最后再次全源哈希验证，manifest最后发布作为commit标记。
- 本批新金融回放42，复用4；报告/验收自身不调用金融引擎。行情下载、CTP/订单API、生产访问为0。旧Stage001—007、LINE/registry根总账、44品种及正式物料不修改。

## 调研、反思与TODO

- 参考官方订单时序https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/ 和区间位置实现https://github.com/mementum/backtrader/blob/master/backtrader/indicators/stochastic.py 。固定同约因果范围与next-open，不引入示例默认窗口或额外平滑。
- 运行前过拟合判断：有。20%规则是在已看历史内提出，23起点相互重叠，不能伪称新样本外；固定清单不扫参数降低进一步选择。
- 运行后过拟合判断：有。即便多数窗口获胜也不消除样本内选择，不挑年份/方向/品种或邻近阈值救失败。继续价值：{continue_text}
- 数据与置信度限制：缓存不是完整上市首日起历史/PIT真值，原已知无交易/结构缺口与暖机不足保留；零手续费、静态规格/保证金、日K next-open与无真实盘口/容量/涨跌停执行资格。独审会计一致不等于数据绝对全准或可上线。
- TODO：冻结46窗口及原始输入/账本/收据/图与哈希，向用户报告全23表与成熟cohort结果。后续研究须另固定合同，本轮不自动加窗、调参或晋级。
"""

def atomic_publish(windows_dir,stage_path,manifest_path,window_texts,stage_text,sources,metadata=None):
 windows_dir=Path(windows_dir);stage_path=Path(stage_path);manifest_path=Path(manifest_path)
 need(not windows_dir.exists() and not stage_path.exists() and not manifest_path.exists(),'immutable_delivery_paths_already_exist')
 need(len(set(window_texts))==len(window_texts) and all(Path(n).name==n and n.endswith('.md') for n in window_texts),'safe_unique_window_names')
 stage_path.parent.mkdir(parents=True,exist_ok=True);published=[]
 with tempfile.TemporaryDirectory(prefix='.stage008_publish_',dir=stage_path.parent) as td:
  temp=Path(td);tw=temp/'windows';tw.mkdir();planned={}
  for name,text in window_texts.items():p=tw/name;p.write_text(text);planned[str((windows_dir/name).resolve())]=sha(p)
  ts=temp/'stage.md';ts.write_text(stage_text);planned[str(stage_path.resolve())]=sha(ts)
  merged=dict(sources)
  for p,h in planned.items():need(p not in merged or merged[p]==h,'new_delivery_source_conflict');merged[p]=h
  doc=dict(schema='stage008_final_delivery_v1',accepted=True,review_status='PASS_WITH_LIMITATIONS',promotion_decision='NO_PROMOTION',financial_replays=42,reused_arms=4,arm_windows=46,independent_pairs=23,complete_vote_pairs=22,observation_pairs=1,atomic_commit_marker=True,self_hash_excluded=True,files_sha256=merged,**(metadata or {}))
  tm=temp/'manifest.json';tm.write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
  try:
   need(not windows_dir.exists() and not stage_path.exists() and not manifest_path.exists(),'delivery_appeared_during_preparation')
   os.rename(tw,windows_dir);published.append(windows_dir)
   os.link(ts,stage_path);published.append(stage_path)
   for p,h in merged.items():need(Path(p).is_file() and sha(p)==h,'final_precommit_source_drift:'+p)
   os.link(tm,manifest_path);published.append(manifest_path)
  except BaseException:
   for p in reversed(published):
    if p.is_dir():shutil.rmtree(p)
    elif p.exists():p.unlink()
   raise
 return doc

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--validate-only',action='store_true');args=ap.parse_args();state=collect_state();state['book'].verify()
 if args.validate_only:print(json.dumps(dict(accepted=True,validation_only=True,bound_sources=len(state['book'].files),arm_windows=46,pairs=23,new_engines=42,reused=4)));return
 now=datetime.now(ZoneInfo('Asia/Shanghai'));stage=STAGES/(now.strftime('%Y%m%d_%H%M')+'_stage008_multistart_result.md');windows={}
 for start in STARTS:
  for arm in ['A','C']:
   key=(start,arm);job=state['registry']['jobs'][start+'|'+arm];rp,r=state['receipts'][key];name=start.replace('-','')+'_'+arm+'_result.md';windows[name]=render_window(state['ledgers'][key],job,state['terminals'][key],rp,sha(rp),sha(job['checkpoint']),now)
 need(len(windows)==46,'exact46_chinese_window_records');text=render_summary(state,now,stage)
 manifest=STAGES/'stage008_delivery_manifest.json';doc=atomic_publish(STAGES/'stage008_windows',stage,manifest,windows,text,state['book'].files,metadata=dict(freeze_sha256=state['freeze_sha'],financial_source_head=state['freeze']['source_head'],strategy_verdict=state['comparison']['strategy_verdict'],market_downloads=0,production_accesses=0,final_independent_review_sha256=state['review_sha'],published_at=now.isoformat()))
 print(json.dumps(dict(accepted=True,manifest=str(manifest),manifest_sha256=sha(manifest),stage=str(stage),window_records=46,bound_files=len(doc['files_sha256']),financial_replays_in_this_process=0),ensure_ascii=False))
if __name__=='__main__':main()
