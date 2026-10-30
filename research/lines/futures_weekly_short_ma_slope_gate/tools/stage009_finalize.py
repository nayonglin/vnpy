"""Read-only acceptance and atomic Chinese delivery of Stage009's complete study.

No financial engine, downloader, report renderer or production service is called.
Only a source-bound final review and five reviewed figures permit publication.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
import argparse,csv,hashlib,json,math,os,tempfile,shutil

LINE=Path(__file__).resolve().parents[1];STAGES=LINE/'stages'
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
VARIANTS=('A_idle','A_R','C_idle','C_R');END='2026-10-29';TOTAL=300000.;TRADING=150000.;RESERVE=150000.
FIGURES=('01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_reserve_effect_heatmaps.png','05_cohort_reserve_summary.png')
FREEZE=STAGES/'stage009_freeze.json';REGISTRY=LINE/'outputs/stage009_multistart/registry.json';CACHE=LINE/'outputs/stage009_derived/cache';RECEIPTS=STAGES/'stage009_independent_receipts'
REPORT=LINE/'artifacts/stage009_multistart';REVIEWED=LINE/'artifacts/stage009_multistart_reviewed';REVIEW=STAGES/'stage009_independent_final.json';VISUAL=STAGES/'stage009_reviewed_visual_receipt.json'

def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def need(value,label):
 if not value:raise ValueError('stage009_delivery:'+label)
def near(a,b):
 if a is None or b is None:return a is None and b is None
 try:return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6)
 except (TypeError,ValueError):return False
def compare(candidate,control):
 need(math.isfinite(float(candidate)) and math.isfinite(float(control)),'finite_pair_metric')
 return 0 if near(candidate,control) else (1 if float(candidate)>float(control) else -1)
def truth(value):
 if type(value) is bool:return value
 if value=='True':return True
 if value=='False':return False
 raise ValueError('stage009_delivery:explicit_boolean_required')
def csv_rows(path):
 with Path(path).open(newline='') as f:return list(csv.DictReader(f))
def maturity(start):return END>=str(int(start[:4])+1)+start[4:]
def number(value,digits=2):
 if value is None or not math.isfinite(float(value)):return '未定义/N/A'
 return f'{float(value):,.{digits}f}'
def link(path):return '['+Path(path).name+']('+str(Path(path).resolve())+')'

class SourceBook:
 def __init__(self):self.files={}
 def add(self,path,digest=None):
  path=str(Path(path).resolve());need(Path(path).is_file(),'missing_source:'+path)
  if path in self.files:
   if digest is not None:need(self.files[path]==digest,'conflicting_source_sha:'+path)
   return self.files[path]
  actual=sha(path);need(digest is None or actual==digest,'source_sha_mismatch:'+path);self.files[path]=actual;return actual
 def add_map(self,mapping,base=None):
  need(isinstance(mapping,dict),'explicit_source_map_required')
  for name,digest in mapping.items():
   p=Path(name)
   if not p.is_absolute() and base is not None:p=Path(base)/p
   self.add(p,digest)
 def verify(self):
  for path,digest in self.files.items():need(Path(path).is_file() and sha(path)==digest,'source_changed_during_finalize:'+path)

def require_inventory(freeze,registry,receipt_keys,cache_keys):
 expected={s+'|'+a for s in STARTS for a in ['A','C']};expected_cache={s+'|'+v for s in STARTS for v in VARIANTS}
 need(freeze.get('starts')==list(STARTS) and freeze.get('cutoff')==END and freeze.get('planned_financial_replays')==46,'frozen23_and46_new')
 jobs=registry.get('jobs',{});need(set(jobs)==expected and len(jobs)==46,'exact46_candidate_jobs')
 need(all(j.get('status')=='validated' and j.get('reused') is False for j in jobs.values()),'all46_new_validated')
 need(registry.get('financial_replays_started')==46 and registry.get('financial_engine_batch_complete') is True,'exact46_completed_engines')
 need(set(receipt_keys)==expected and len(receipt_keys)==46,'exact46_independent_receipts')
 need(set(cache_keys)==expected_cache and len(cache_keys)==92,'exact92_complete_caches')
 return expected

def checkpoint_identity(freeze,freeze_sha,arm,start):
 payload=dict(source_head=freeze['source_head'],freeze_sha256=freeze_sha,cutoff=freeze['cutoff'],arm=arm,start=start,engine_initial_capital=freeze.get('engine_initial_capital'),reserve_initial_capital=freeze.get('reserve_initial_capital'),total_initial_capital=freeze.get('total_initial_capital'))
 return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def require_final_review(review,freeze_sha,comparison_sha):
 need(str(review.get('status','')).startswith('PASS') and all(review.get(k)==0 for k in ['P0','P1','P2','failures']),'final_review_pass_zero_findings')
 need(review.get('freeze_sha256')==freeze_sha and review.get('arm_windows')==46 and review.get('paired_windows')==46 and review.get('independent_starts')==23,'final_review_scope_freeze')
 need(review.get('report_comparison_sha256')==comparison_sha,'final_review_report_binding')

def require_visual(visual,review_sha,reviewed_dir):
 need(visual.get('independent_review_sha256')==review_sha,'visual_exact_locked_review')
 mapping=visual.get('reviewed_figures_sha256',{});expected={str((Path(reviewed_dir)/n).resolve()) for n in FIGURES}
 need(isinstance(mapping,dict) and set(mapping)==expected,'exact_five_reviewed_images')
 for p,h in mapping.items():need(Path(p).is_file() and sha(p)==h,'reviewed_figure_sha:'+p)

def require_report_rows(ledgers,summary,pairs):
 expected={(s,v) for s in STARTS for v in VARIANTS};keys=[(r['start'],r['variant']) for r in summary]
 need(len(keys)==92 and len(set(keys))==92 and set(keys)==expected and set(ledgers)==expected,'exact92_summary_and_caches')
 pkeys=[(r['start'],r['arm']) for r in pairs];expected_pairs={(s,a) for s in STARTS for a in ['A','C']}
 need(len(pkeys)==46 and len(set(pkeys))==46 and set(pkeys)==expected_pairs,'exact46_reserve_idle_pairs')
 for row in summary:
  start=row['start'];variant=row['variant'];m=ledgers[(start,variant)]['metrics'];eligible=maturity(start)
  need(row['arm']==variant[0] and row['mode']==('reserve' if variant.endswith('_R') else 'idle'),'summary_variant_role')
  need(near(row.get('initial_capital'),TOTAL) and m.get('initial_capital')==TOTAL,'same_total300k_capital')
  need(truth(row['vote_eligible'])==eligible and truth(row['observation_only']) is (not eligible),'summary_vote_scope')
  if 'cohort' in row:need(row['cohort']==('January' if start[5:7]=='01' else 'June'),'summary_cohort')
  for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count','total_transferred','reserve_end_balance','trading_end_equity']:
   need(near(row[key],m[key]),'summary_metric:'+start+variant+key)
 for row in pairs:
  start,arm=row['start'],row['arm'];eligible=maturity(start);idle=ledgers[(start,arm+'_idle')]['metrics'];reserve=ledgers[(start,arm+'_R')]['metrics']
  need(truth(row['vote_eligible'])==eligible and truth(row['observation_only']) is (not eligible),'paired_vote_scope')
  need(row['cohort']==('January' if start[5:7]=='01' else 'June'),'paired_cohort')
  for prefix,m in [('idle',idle),('reserve',reserve)]:
   for key in ['end_equity','total_return_pct','max_dd_pct','sharpe']:need(near(row[prefix+'_'+key],m[key]),'paired_metric:'+start+arm+prefix+key)
  gates=dict(equity_gate=compare(reserve['end_equity'],idle['end_equity'])>0,dd_gate=compare(reserve['max_dd_pct'],idle['max_dd_pct'])>=0,sharpe_gate=compare(reserve['sharpe'],idle['sharpe'])>=0)
  for key,value in gates.items():need(truth(row[key])==value,'paired_gate:'+start+arm+key)
  need(truth(row['three_gate_pass'])==all(gates.values()),'paired_three_gates')
 need(sum(maturity(s) for s in STARTS)==22 and [s for s in STARTS if not maturity(s)]==['2026-01-01'],'22mature_one_observation_per_arm')

def require_comparison(comp,freeze_sha,source_head):
 expected=dict(expected_new_engines=46,arm_windows=46,paired_windows=46,summary_rows=92,independent_starts=23,complete_pairs_per_arm=22,observation_per_arm=1,total_daily_points=141996,total_initial_capital=TOTAL,engine_initial_capital=TRADING,reserve_initial_capital=RESERVE)
 need(all(comp.get(k)==v for k,v in expected.items()),'report_exact_scope_and_amounts')
 need(comp.get('variants')==list(VARIANTS) and comp.get('five_figures')==list(FIGURES) and comp.get('starts')==list(STARTS) and comp.get('cutoff')==END,'report_exact_named_variants_figures_and_windows')
 need(comp.get('freeze_sha256')==freeze_sha and comp.get('source_head')==source_head and comp.get('financial_source_head',source_head)==source_head,'report_frozen_source_identity')
 need(comp.get('promotion_decision')=='NO_PROMOTION','research_no_promotion')

def normalized_settings(settings,start):
 result=deepcopy(settings);need(len(result)==1,'one_actual_strategy')
 for part in ['setting','actual']:
  need(result[0][part].get('trade_start_date')==start,'true_declared_trade_start');result[0][part]['trade_start_date']='<independent-start>'
 need(result[0]['actual'].get('capital_base')==TRADING,'true_trading150k_capital')
 return result

def check_candidate(book,freeze,freeze_sha,start,arm,job,receipt):
 path=Path(job['path']).resolve();cp_path=Path(job['checkpoint']).resolve();cp=load(cp_path);key=start+'|'+arm
 need(path==(LINE/'outputs'/f"stage009_{arm}_{start.replace('-','')}_attempt001").resolve(),'assigned_new_candidate_path:'+key)
 book.add(cp_path);book.add_map(job['files_sha256'])
 need(job.get('reused') is False and cp.get('reused') is False,'no_candidate_reuse')
 need(cp.get('files_sha256')==job['files_sha256'] and Path(cp['path']).resolve()==path,'checkpoint_registry_snapshot')
 actual={str(p.resolve()) for p in path.iterdir() if p.is_file()};need(actual==set(job['files_sha256']),'candidate_exact_output_set')
 for obj in [job,cp]:need(obj.get('freeze_sha256')==freeze_sha and obj.get('source_head')==freeze['source_head'] and obj.get('start')==start and obj.get('arm')==arm and obj.get('end')==END,'candidate_checkpoint_frozen_identity')
 expected=checkpoint_identity(freeze,freeze_sha,arm,start);need(cp.get('checkpoint_key')==job.get('checkpoint_key')==expected,'candidate_checkpoint_key')
 need(str(receipt.get('status','')).startswith('PASS') and all(receipt.get(k)==0 for k in ['P0','P1','P2','failures']),'independent_window_pass')
 need(receipt.get('requested_start',receipt.get('start'))==start and receipt.get('arm')==arm and receipt.get('end')==END,'independent_window_scope')
 book.add(Path(__file__).with_name('stage009_independent_window.py'),receipt['auditor_source_sha256'])
 if 'old_raw_auditor_source' in receipt:book.add(receipt['old_raw_auditor_source'],receipt['old_raw_auditor_sha256'])
 need(receipt.get('freeze_sha256')==freeze_sha and receipt.get('frozen_source_head',receipt.get('source_head'))==freeze['source_head'],'independent_window_freeze')
 need(Path(receipt['path']).resolve()==path and receipt.get('source_files_sha256')==job['files_sha256'],'independent_window_snapshot_binding')
 pre=load(path/'preflight.json');terminal=load(path/'terminal.json');book.add_map(load(path/'input_manifest.json'))
 need(pre.get('head')==freeze['source_head'] and pre.get('frozen_source_head')==freeze['source_head'] and pre.get('freeze_sha256')==freeze_sha,'candidate_real_HEAD')
 need(pre.get('data_identity')==freeze['data_identity'] and pre.get('start')==start and pre.get('end')==END,'candidate_actual_data_window')
 need(pre.get('reserve_topup_enabled') is True and pre.get('engine_initial_capital')==TRADING and pre.get('reserve_initial_capital')==RESERVE and pre.get('total_initial_capital')==TOTAL,'candidate_actual_two_buckets')
 need(terminal.get('status')=='completed_pending_independent_review' and terminal.get('error') is None and load(path/'postflight.json').get('inputs_unchanged') is True,'candidate_complete_postflight')
 need(datetime.fromisoformat(terminal['completed_at'])>=datetime.fromisoformat(terminal['started_at']) and terminal.get('order_api_count')==0,'candidate_time_and_order_count')
 proof=load(path/'reserve_acceptance.json');need(proof.get('accepted') is True and proof.get('enabled') is True,'actual_reserve_accepted')
 for name in ['phase_proof','snapshot_proof','checks_proof']:need(proof.get(name,{}).get('accepted') is True,'actual_reserve_proof:'+name)
 need(proof['phase_proof'].get('post_sizing_fill_count')==0 and proof['phase_proof'].get('all_event_raw_account_equity_matches_same_day_raw_daily') is True,'real_event_equity_anchor')
 need(proof['checks_proof'].get('nonpositive_equity_purchasing_power_guard') is True,'no_nonpositive_purchase_power')
 return cp,terminal

def check_cache(book,freeze,freeze_sha,start,variant,job,idle_job):
 import pandas as pd
 import numpy as np
 folder=CACHE/(start.replace('-','')+'_'+variant);doc=load(folder/'ledger.json');manifest=load(folder/'delivery_manifest.json');book.add(folder/'delivery_manifest.json');book.add_map(manifest['files_sha256'],folder);book.add_map(doc['sources_sha256']);book.add_map(doc['derivation_sources_sha256'])
 mode='reserve' if variant.endswith('_R') else 'idle';source=job if mode=='reserve' else idle_job
 need(doc.get('key')==start+'|'+variant and doc.get('start')==start and doc.get('end')==END and doc.get('arm')==variant[0] and doc.get('variant')==variant and doc.get('mode')==mode,'cache_identity')
 need(doc.get('freeze_sha256')==freeze_sha and doc.get('source_head')==freeze['source_head'],'cache_study_identity')
 need(Path(doc['source_path']).resolve()==Path(source['path']).resolve() and doc['attempt_snapshot']==source['files_sha256'],'cache_exact_actual_source')
 need({str(p.resolve()) for p in Path(doc['source_path']).iterdir() if p.is_file()}==set(doc['attempt_snapshot']),'cache_source_output_file_set')
 d=pd.read_csv(folder/'daily.csv');raw=pd.read_csv(Path(doc['source_path'])/'daily.csv');m=doc['metrics']
 need(d.date.astype(str).str[:10].tolist()==raw.date.astype(str).str[:10].tolist() and len(d)==m['trading_days'] and str(d.date.iloc[0])[:10]==m['actual_start'] and str(d.date.iloc[-1])[:10]==END,'cache_full_source_calendar')
 need(m.get('initial_capital')==TOTAL and near(d.total_account_equity.iloc[0],TOTAL) and near(d.raw_account_equity.iloc[0],TRADING) and near(d.reserve_balance.iloc[0],RESERVE) and near(raw.trade_count.iloc[0],0),'fresh300k_two_buckets')
 need(np.allclose(d.raw_account_equity,raw.account_equity,rtol=1e-10,atol=1e-6) and np.allclose(d.raw_account_equity,TRADING+raw.net_pnl.cumsum(),rtol=1e-10,atol=1e-6),'raw150k_true_PnL')
 for key,expected in [('trading_account_equity',d.raw_account_equity+d.cumulative_transfer),('reserve_balance',RESERVE-d.cumulative_transfer),('total_account_equity',d.raw_account_equity+RESERVE),('nav',d.total_account_equity/TOTAL),('drawdown_pct',(d.total_account_equity/np.maximum.accumulate(np.r_[TOTAL,d.total_account_equity])[1:]-1)*100)]:need(np.allclose(d[key],expected,rtol=1e-10,atol=1e-6),'cache_daily_bridge:'+key)
 need(d.reserve_balance.ge(-1e-6).all() and d.cumulative_transfer.diff().fillna(0).ge(-1e-6).all(),'reserve_no_refill_no_overdraw')
 if mode=='idle':need(d.cumulative_transfer.eq(0).all() and d.reserve_balance.eq(RESERVE).all() and doc['transfer_event_count']==0,'idle_stays150k_no_transfers')
 else:
  for key,target in [('end_equity','end_equity'),('total_return_pct','total_return_pct'),('max_dd_pct','max_dd_pct'),('sharpe','sharpe'),('total_slippage','total_slippage')]:need(near(m[key],job['metrics'][target]),'reserve_cache_checkpoint_metric:'+key)
  need(near(m['modeled_fill_count'],job['metrics']['total_trade_count']),'reserve_fill_count')
  need(doc['transfer_event_count']==job['transfer_event_count'] and near(m['total_transferred'],job['cumulative_transfer']) and near(m['reserve_end_balance'],job['reserve_balance_end']),'reserve_transfer_counts_match_real_checkpoint')
 need(near(doc['accounting']['complete_contract_rounds']['closed_net_pnl']+doc['accounting']['open_round_net_mtm'],m['net_pnl']) and near(m['net_pnl'],raw.net_pnl.sum()),'closed_plus_open_real_profit')
 normalized_settings(doc['settings'],start);return doc,d

def require_independent_metrics(ledger,receipt):
 m=ledger['metrics'];rm=receipt['metrics'];a=ledger['accounting'];rounds=a['complete_contract_rounds']
 need(rm.get('initial_capital')==TOTAL,'independent_metrics_total300k')
 for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage']:need(near(m[key],rm[key]),'independent_total_metric:'+key)
 need(near(m['modeled_fill_count'],rm['total_trade_count']),'independent_real_fill_count')
 for key in ['count','wins','losses','flat','win_rate_pct','average_win','average_loss_abs','payoff_ratio','profit_factor','closed_net_pnl']:need(near(rounds[key],rm['rounds'][key]),'independent_round_stat:'+key)
 need(near(a['open_round_net_mtm'],rm['open_round_net_mtm']),'independent_open_round_MTM')
 for key,independent in [('trading_margin_peak_pct','configured_margin_max_trading_pct'),('trading_margin_over100_days','configured_margin_over100_trading_days'),('trading_margin_undefined_days','configured_margin_undefined_trading_days'),('total_margin_peak_pct','configured_margin_max_total_pct'),('total_margin_over100_days','configured_margin_over100_total_days'),('total_margin_undefined_days','nonpositive_total_equity_days')]:need(near(ledger['risk'][key],receipt['risk'][independent]),'independent_two_bucket_risk:'+key)

def require_cohorts(cohorts,pairs):
 expected={(arm,cohort,sample) for arm in ['A','C'] for cohort in ['January','June','combined'] for sample in ['complete_ge_1y','observation_lt_1y']};keys=[(r['arm'],r['cohort'],r['sample']) for r in cohorts];need(len(keys)==12 and len(set(keys))==12 and set(keys)==expected,'exact12_cohorts')
 for row in cohorts:
  eligible=row['sample']=='complete_ge_1y';selected=[p for p in pairs if p['arm']==row['arm'] and truth(p['vote_eligible'])==eligible and (row['cohort']=='combined' or p['cohort']==row['cohort'])]
  values=dict(windows=len(selected),vote_windows=len(selected) if eligible else 0,observation_windows=0 if eligible else len(selected),return_wins=sum(truth(p['equity_gate']) for p in selected) if eligible else 0,three_gate_pass_count=sum(truth(p['three_gate_pass']) for p in selected) if eligible else 0)
  for key,value in values.items():need(near(row[key],value),'cohort_count:'+str(keys)+key)

def collect_state(locked_review_sha):
 import pandas as pd
 import numpy as np
 need(isinstance(locked_review_sha,str) and len(locked_review_sha)==64 and sha(REVIEW)==locked_review_sha,'explicit_locked_final_review_sha')
 book=SourceBook();freeze=load(FREEZE);freeze_sha=book.add(FREEZE);registry=load(REGISTRY);book.add(REGISTRY)
 receipt_paths={p.stem[:-2]+'|'+p.stem[-1]:p for p in RECEIPTS.glob('*.json')};cache_keys={s+'|'+v for s in STARTS for v in VARIANTS if (CACHE/(s.replace('-','')+'_'+v)/'ledger.json').is_file()}
 require_inventory(freeze,registry,set(receipt_paths),cache_keys);need(registry.get('freeze_sha256')==freeze_sha and registry.get('source_head')==freeze['source_head'],'registry_freeze');book.add_map(freeze['source_files_sha256'])
 book.add(freeze['idle_control_registry'],freeze['idle_control_registry_sha256']);book.add(freeze['idle_control_freeze'],freeze['idle_control_freeze_sha256']);idle_registry=load(freeze['idle_control_registry'])
 need(set(idle_registry['jobs'])==set(registry['jobs']) and all(j.get('status')=='validated' for j in idle_registry['jobs'].values()),'exact46_frozen_idle_jobs')
 ledgers={};curves={};receipts={};terminals={};reference_settings=reference_effective=None
 for start in STARTS:
  for arm in ['A','C']:
   key=start+'|'+arm;job=registry['jobs'][key];rp=receipt_paths[key];book.add(rp);receipt=load(rp);cp,terminal=check_candidate(book,freeze,freeze_sha,start,arm,job,receipt);receipts[(start,arm)]=rp;terminals[(start,arm)]=terminal
   idle=idle_registry['jobs'][key];book.add(idle['checkpoint']);oldcp=load(idle['checkpoint']);need(oldcp.get('files_sha256')==idle['files_sha256'] and Path(oldcp['path']).resolve()==Path(idle['path']).resolve(),'idle_frozen_checkpoint');book.add_map(idle['files_sha256'])
   for variant in [arm+'_idle',arm+'_R']:
    d,curve=check_cache(book,freeze,freeze_sha,start,variant,job,idle)
    if variant.endswith('_R'):require_independent_metrics(d,receipt)
    ledgers[(start,variant)]=d;curves[(start,variant)]=curve;normalized=normalized_settings(d['settings'],start)
    if reference_settings is None:reference_settings=normalized;reference_effective=d['effective']
    need(normalized==reference_settings and d['effective']==reference_effective,'only_declared_start_differs_in_settings')
 summary=csv_rows(REPORT/'summary.csv');pairs=csv_rows(REPORT/'paired.csv');require_report_rows(ledgers,summary,pairs);cohorts=csv_rows(REPORT/'cohort_summary.csv');require_cohorts(cohorts,pairs)
 daily=pd.read_csv(REPORT/'all_daily.csv');need(len(daily)==141996,'exact141996_actual_daily_points')
 groups={key:g for key,g in daily.groupby(['start','variant'],sort=False)};need(set(groups)==set(curves),'all92_daily_curve_keys')
 for key,d in curves.items():
  actual=groups[key];need(actual.date.astype(str).str[:10].tolist()==d.date.astype(str).str[:10].tolist(),'report_full_daily_calendar')
  for field in ['raw_account_equity','trading_account_equity','reserve_balance','cumulative_transfer','total_account_equity','net_pnl','nav','drawdown_pct']:need(np.allclose(actual[field],d[field],rtol=1e-10,atol=1e-6),'report_daily_exact_cache:'+str(key)+field)
 comp=load(REPORT/'comparison.json');require_comparison(comp,freeze_sha,freeze['source_head'])
 need(comp.get('promotion_decision')=='NO_PROMOTION' and load(REPORT/'decision.json').get('promotion_decision')=='NO_PROMOTION','research_no_promotion')
 book.add_map(comp['source_files_sha256']);book.add_map(load(REPORT/'source_hashes.json'));manifest=load(REPORT/'delivery_manifest.json');book.add_map(manifest['files_sha256'],REPORT)
 for p in REPORT.rglob('*'):
  if p.is_file():book.add(p)
 review=load(REVIEW);require_final_review(review,freeze_sha,sha(REPORT/'comparison.json'));book.add(REVIEW,locked_review_sha);visual=load(VISUAL);require_visual(visual,locked_review_sha,REVIEWED);book.add(VISUAL);book.add_map(visual['reviewed_figures_sha256'])
 if 'source_inputs_sha256' in visual:book.add_map(visual['source_inputs_sha256'])
 for p in list(STAGES.glob('*stage009*'))+list((LINE/'tools').glob('*stage009*')):
  if p.is_file() and p.name!='stage009_delivery_manifest.json':book.add(p)
 for folder in [RECEIPTS,REGISTRY.parent,REVIEWED]:
  for p in folder.rglob('*'):
   if p.is_file():book.add(p)
 need(sha(REVIEW)==locked_review_sha,'locked_review_changed_during_collection');return dict(book=book,freeze=freeze,freeze_sha=freeze_sha,registry=registry,idle_registry=idle_registry,ledgers=ledgers,terminals=terminals,receipts=receipts,summary=summary,pairs=pairs,cohorts=cohorts,comparison=comp,review=review,review_sha=locked_review_sha)

def render_window(idle,reserve,terminal,idle_terminal,receipt_path,receipt_sha,checkpoint_sha,now):
 start=reserve['start'];arm=reserve['arm'];m=reserve['metrics'];old=idle['metrics'];a=reserve['accounting'];r=a['complete_contract_rounds'];risk=reserve['risk'];eligible=maturity(start)
 rows=[]
 for label,key,digits in [('期末总权益','end_equity',2),('净利润','net_pnl',2),('总收益%','total_return_pct',6),('最大回撤%','max_dd_pct',6),('Sharpe','sharpe',6),('总滑点','total_slippage',2),('成交笔数（开平分别计）','modeled_fill_count',0),('交易桶期末权益','trading_end_equity',2),('备用桶余额','reserve_end_balance',2),('累计内部转入','total_transferred',2)]:rows.append('| '+label+' | '+number(old[key],digits)+' | '+number(m[key],digits)+' |')
 return f"""# Stage009 独立起点 {start} / {arm}_R 对 {arm}_idle

- line_id=futures_weekly_short_ma_slope_gate；登记时间{now.isoformat()}；非重要突破，离线研究，NO_PROMOTION。
- 候选真实金融运行时间：{terminal['started_at']}—{terminal['completed_at']}。每窗新引擎150,000交易桶＋150,000永久隔离备用桶，总本金300,000、空仓独立起跑；实际{m['actual_start']}—{m['actual_end']}，{m['trading_days']}交易日。{'完整满一年，参与投票' if eligible else '不足一年观察，不投票'}。
- 对照为精确冻结旧账本＋恒定闲置150,000，无本轮新对照引擎；旧账本真实运行时间{idle_terminal['started_at']}—{idle_terminal['completed_at']}。登记时间不是旧源执行时间。
- A原始无价格门；C仅short_case1a同物理epoch已有有效日线（含信号日）底部20%拒开。多头价格门和新增多空MA斜率门关闭，原19、原MA5/10/20、动态底仓、不加仓、21周ready/41storage、滑点与手续费0不变。
- 只对起点后有效flat/reverse新候选、方向允许、周止损有效且C未被底20%拒绝者，在父级sizing前补足交易权益至150,000，最多用剩余备用金。盈利不回填，不出金；env_probe/换月/退出/预热不转资，同一候选不重复。补资不保证最后成交。
- 原始引擎账本仍为150,000＋真实交易盈亏；交易E=raw＋累计T，备用R=150,000−累计T，总W=raw＋150,000=300,000＋真实累计盈亏。内部转账不是净利或alpha；备用未用也计本金，不提前参与风险或保证金。

|指标|旧账本＋闲置备用，同30万|本轮补资，同30万|
|---|---:|---:|
"""+'\n'.join(rows)+f"""

- 完整周期胜率{number(r['win_rate_pct'],6)}%；胜/负/平{r['wins']}/{r['losses']}/{r['flat']}，完整周期{r['count']}；平均盈利{number(r['average_win'])}、平均亏损绝对额{number(r['average_loss_abs'])}；平均盈亏比{number(r['payoff_ratio'],6)}；Profit Factor{number(r['profit_factor'],6)}。
- 已平完整周期净额{number(r['closed_net_pnl'])}；末未平周期净盯市{number(a['open_round_net_mtm'])}、周期数{number(a.get('open_round_count'),0)}；实际补资事件{reserve['transfer_event_count']}，全部T不列交易利润。
- 静态保证金×1.65/交易桶峰值{number(risk['trading_margin_peak_pct'],6)}%、超100%{risk['trading_margin_over100_days']}日；/总账户峰值{number(risk['total_margin_peak_pct'],6)}%、超100%{risk['total_margin_over100_days']}日；不是历史实际券商保证金或强平证明。
- 新账本{link(reserve['source_path'])}；旧账本{link(idle['source_path'])}；独审{link(receipt_path)}，SHA={receipt_sha}；新checkpoint SHA={checkpoint_sha}。全部来源、缓存与图表由最终manifest绑定。
- 新增参数仅固定备用150,000与有效信号补足150,000规则；金额和触发不扫描。旧版本/旧回测修改、删除均无；本窗经济负结果保留，不做正式晋级或生产连接。
- 运行前后过拟合判断：有历史内选择风险，重叠起点不是独立OOS；继续价值在于完成固定网格审计，不以单窗盈利救参。TODO：纳入两组各22成熟票＋1观察，保留最弱窗口和所有负结果。
"""

def render_summary(state,now):
 lines=[]
 for arm in ['A','C']:
  for cohort in ['January','June','combined']:
   chosen=[p for p in state['pairs'] if p['arm']==arm and truth(p['vote_eligible']) and (cohort=='combined' or p['cohort']==cohort)]
   lines.append(f"| {arm} | {cohort} | {len(chosen)} | {sum(truth(p['equity_gate']) for p in chosen)} | {sum(truth(p['three_gate_pass']) for p in chosen)} |")
 windows=[]
 for start in STARTS:
  for arm in ['A','C']:
   old=state['ledgers'][(start,arm+'_idle')]['metrics'];new=state['ledgers'][(start,arm+'_R')]['metrics'];pair=next(p for p in state['pairs'] if p['start']==start and p['arm']==arm);windows.append(f"| {start}{'*' if not maturity(start) else ''} | {arm} | {number(old['end_equity'],0)}/{number(new['end_equity'],0)} | {number(old['total_return_pct'])}%/{number(new['total_return_pct'])}% | {number(old['max_dd_pct'])}%/{number(new['max_dd_pct'])}% | {number(old['sharpe'],3)}/{number(new['sharpe'],3)} | {'通过' if truth(pair['three_gate_pass']) else '未通过'} |")
 return f"""# Stage009 双桶备用金：23独立起点同30万本金验证

- line_id=futures_weekly_short_ma_slope_gate；登记时间{now.isoformat()}，非重要突破，NO_PROMOTION。最终独审{state['review']['status']}、P0/P1/P2/失败均0；会计通过不代表策略晋级。
- 新金融46次，A_R/C_R各23；旧A/C各23精确复用＋固定闲置150,000作同本金对照，共92份缓存、46配对、141,996日净值点。全部2015—2025每年1/1和6/1及2026-1/1至2026-10-29，四变体每窗初始总300,000，交易与备用各150,000。每arm22成熟票＋2026Jan一观察；不冒称固定1/2/3年窗，不截长曲线，不平均不同长度收益作预期。
- 金融冻结HEAD={state['freeze']['source_head']}；freeze SHA={state['freeze_sha']}；最终独审锁定SHA={state['review_sha']}。
- 改动：新增有效新信号时内部补足至原交易初资，备用永久隔离且无外部现金流。交易超150,000后按全部交易权益原规则动态计算；不重置原风控历史，不用备用提前充购买力。原始raw账本仍15万＋PnL；总W=raw＋15万，以30万作正式指标，内部转账不计净利。没有删除或覆盖旧回测。

|臂|cohort|成熟票|期末权益严格胜|三门同时通过|
|---|---|---:|---:|---:|
"""+'\n'.join(lines)+"\n\n|请求起点|臂|idle/补资期末总权益|总收益|最大回撤|Sharpe|三门|\n|---|---|---:|---:|---:|---:|---|\n"+'\n'.join(windows)+f"""

* 2026-01-01不足一年，只展示不投票。权益必须严格更高，回撤不更差、Sharpe不更低；平权益不通过。完整胜率/平均赢亏/盈亏比/PF、末MTM、滑点、成交、转资、交易桶与总账户保证金和生存均见46逐窗中文记录、summary/paired/cohort表及源缓存。

五张已审图：
"""+'\n'.join('- '+link(REVIEWED/n) for n in FIGURES)+f"""

- 调研判断沿用冻结设计的Backtrader Fund Tracking/BackBroker资金流与盈亏分离；本地采用内部守恒，不引入新预测信息。更高权益可能来自更多风险暴露、整数手数和动态资金路径反馈，不能称补资alpha。
- 运行前后过拟合风险均有：在已看历史上迭代、23起点重叠共享未来。固定金额、固定触发和完整网格有敏感性审计价值；不按结果挑年份/阈值/金额救参。结论按全部成熟窗口和负结果保留，NO_PROMOTION。
- 局限：缓存非完整上市/PIT历史，零手续费、静态规格/保证金×1.65、日线next-open、无盘口/容量/券商执行时真实现金guard证明；信号规划正权益保护不是完整券商购买力模型。备用机会成本已在总30万本金计入。会计与独审通过不证明可实盘。
- 本封存工具0金融回放、0下载、0生产/CTP/订单API；冻结6金融必需文件、旧Stage008、LINE、根总账及44品种线未修改。TODO：保存来源、46新账本/独审、92缓存及所有图表哈希，不自动晋级。
"""

def atomic_publish(windows_dir,stage_path,manifest_path,window_texts,stage_text,sources,metadata=None):
 windows_dir=Path(windows_dir);stage_path=Path(stage_path);manifest_path=Path(manifest_path)
 need(not windows_dir.exists() and not stage_path.exists() and not manifest_path.exists(),'immutable_delivery_exists')
 need(len(window_texts)==46 and len(set(window_texts))==46 and all(Path(n).name==n and n.endswith('.md') for n in window_texts),'exact46_safe_window_records')
 stage_path.parent.mkdir(parents=True,exist_ok=True);published=[]
 with tempfile.TemporaryDirectory(prefix='.stage009_publish_',dir=stage_path.parent) as td:
  temp=Path(td);tw=temp/'windows';tw.mkdir();planned={}
  for name,text in window_texts.items():p=tw/name;p.write_text(text);planned[str((windows_dir/name).resolve())]=sha(p)
  ts=temp/'stage.md';ts.write_text(stage_text);planned[str(stage_path.resolve())]=sha(ts);merged=dict(sources)
  for p,h in planned.items():need(p not in merged or merged[p]==h,'new_delivery_source_conflict');merged[p]=h
  doc=dict(schema='stage009_final_delivery_v1',accepted=True,review_status='PASS_WITH_LIMITATIONS',promotion_decision='NO_PROMOTION',financial_replays=46,reused_candidate_engines=0,arm_windows=46,independent_starts=23,derived_variant_windows=92,paired_windows=46,complete_pairs_per_arm=22,observation_per_arm=1,total_daily_points=141996,atomic_commit_marker=True,self_hash_excluded=True,files_sha256=merged,**(metadata or {}));tm=temp/'manifest.json';tm.write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
  try:
   need(not windows_dir.exists() and not stage_path.exists() and not manifest_path.exists(),'delivery_appeared_during_preparation');windows_dir.mkdir();published.append(windows_dir)
   for p in tw.iterdir():os.link(p,windows_dir/p.name)
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
 ap=argparse.ArgumentParser();ap.add_argument('--locked-review-sha',required=True);ap.add_argument('--validate-only',action='store_true');args=ap.parse_args();state=collect_state(args.locked_review_sha);state['book'].verify()
 if args.validate_only:print(json.dumps(dict(accepted=True,validation_only=True,bound_files=len(state['book'].files),arm_windows=46,caches=92,pairs=46,financial_replays_in_this_process=0)));return
 now=datetime.now(ZoneInfo('Asia/Shanghai'));stage=STAGES/(now.strftime('%Y%m%d_%H%M')+'_stage009_reserve_multistart_result.md');windows={}
 for start in STARTS:
  for arm in ['A','C']:
   key=(start,arm);job=state['registry']['jobs'][start+'|'+arm];old=state['idle_registry']['jobs'][start+'|'+arm];rp=state['receipts'][key];windows[start.replace('-','')+'_'+arm+'_result.md']=render_window(state['ledgers'][(start,arm+'_idle')],state['ledgers'][(start,arm+'_R')],state['terminals'][key],load(Path(old['path'])/'terminal.json'),rp,sha(rp),sha(job['checkpoint']),now)
 need(sha(REVIEW)==args.locked_review_sha,'final_review_changed_before_publish');manifest=STAGES/'stage009_delivery_manifest.json';doc=atomic_publish(STAGES/'stage009_windows',stage,manifest,windows,render_summary(state,now),state['book'].files,metadata=dict(freeze_sha256=state['freeze_sha'],financial_source_head=state['freeze']['source_head'],final_independent_review_sha256=args.locked_review_sha,published_at=now.isoformat(),market_downloads=0,production_accesses=0));print(json.dumps(dict(accepted=True,manifest=str(manifest),manifest_sha256=sha(manifest),stage=str(stage),window_records=46,bound_files=len(doc['files_sha256']),financial_replays_in_this_process=0),ensure_ascii=False))
if __name__=='__main__':main()
