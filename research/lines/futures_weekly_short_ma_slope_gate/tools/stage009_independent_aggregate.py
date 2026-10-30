"""Independent Stage009 final audit: reads immutable files; never runs an engine.

Intentionally does not import Stage009 accounting/derive/report/plot producers.
The existing 46 full fill/funding audit receipts supply inventory proofs; this
adds exact-source binding, actual-open 21-week readiness and independent report
recomputation from all 92 raw daily ledgers and transfer events.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,ast,hashlib,json,math,subprocess
import numpy as np
import pandas as pd
from PIL import Image
L=Path(__file__).resolve().parents[1]; ROOT=L.parents[2]
F=L/'stages/stage009_freeze.json'; B=L/'outputs/stage009_multistart'
REPORT=L/'artifacts/stage009_multistart'; CACHE=L/'outputs/stage009_derived/cache'
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
VARIANTS=('A_idle','A_R','C_idle','C_R')
FIGURES=('01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_reserve_effect_heatmaps.png','05_cohort_reserve_summary.png')
FREEZE_SHA='d53d36fc21b8308b220cd69484697ae3d1b29074abd23311f28f58feec4e406a'
AUDITOR_SHA='63e9ba6821b3b4c377ed7b67ca035b4daa4fc9ddd8bb824141047f280e237ac9'
REVIEWED_SOURCES={'stage009_reviewed_visual.py':'1304eb90be7df49054426a727848175fa8d061029c6416e2e4c9d888fa79ea68','test_stage009_reviewed_visual.py':'7cbd1f096427c0d469e6fd6c24025439c905c57d26ccda779bcc212e998ea05a','stage009_independent_stream_v2.py':'7ee738981d36174e147501f47600f1ce15ec4e25af81414e3762421c9e6d3054'}
checks=0

def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):
 if b is None:ok(a is None or pd.isna(a),label);return
 if isinstance(b,str):ok(a==b,label);return
 ok(np.allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=1e-10,atol=1e-6,equal_nan=False),label)
def cmp(a,b):return 0 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6) else (1 if a>b else -1)
def verify_map(mapping):
 for p,h in mapping.items():ok(Path(p).is_file() and sha(p)==h,'source_hash:'+p)
def merge_map(target,source):
 for p,h in source.items():
  if p in target:ok(target[p]==h,'conflicting_source_pin:'+p)
  target[p]=h

def recompute(raw,events):
 d=raw.copy();d['date']=d.date.astype(str).str[:10]
 ok(len(d)>0 and not d.date.duplicated().any() and d.date.is_monotonic_increasing,'raw_calendar')
 near(d.account_equity,150000+d.net_pnl.cumsum(),'raw_pnl');near(d.account_equity.iloc[0],150000,'cold150k')
 cash={};cum=0.;reserve=150000.;seen=set();last=''
 for e in events:
  day=str(e['date'])[:10];ok(day>=last and day in set(d.date),'event_scope_order');last=day
  ok(e['candidate_key'] not in seen,'no_duplicate_transfer');seen.add(e['candidate_key'])
  rawday=float(d.loc[d.date.eq(day),'account_equity'].iloc[0]);before=rawday+cum
  amount=min(max(150000-before,0),reserve);ok(amount>0,'positive_transfer')
  for k,v in dict(raw_account_equity=rawday,trading_equity_before=before,transfer_amount=amount,reserve_before=reserve,trading_equity_after=before+amount,reserve_after=reserve-amount,total_account_equity=rawday+150000,cumulative_transfer=cum+amount).items():near(e[k],v,'event_'+k)
  cum+=amount;reserve-=amount;cash[day]=cash.get(day,0)+amount
 transfer=d.date.map(cash).fillna(0).to_numpy();cumulative=transfer.cumsum();rawval=d.account_equity.to_numpy(float)
 w=rawval+150000.;t=rawval+cumulative;r=150000.-cumulative
 dd=100*(w/np.maximum.accumulate(np.r_[300000.,w])[1:]-1)
 prev=np.r_[300000.,w[:-1]];returns=np.divide(w-prev,prev,out=np.full_like(w,np.nan),where=prev!=0)
 defined=bool(np.isfinite(returns).all());std=returns.std(ddof=1) if defined else 0
 metrics=dict(initial_capital=300000.,end_equity=w[-1],net_pnl=d.net_pnl.sum(),total_return_pct=(w[-1]/300000.-1)*100,max_dd_pct=dd.min(),sharpe=returns.mean()/std*np.sqrt(252) if defined and std>0 else 0.,sharpe_returns_defined=defined,total_slippage=d.slippage.sum(),total_commission=d.commission.sum(),modeled_fill_count=int(d.trade_count.sum()),trading_days=len(d),nonpositive_total_equity_days=int((w<=0).sum()),nonpositive_trading_equity_days=int((t<=0).sum()),trading_end_equity=t[-1],reserve_end_balance=r[-1],total_transferred=cum,transfer_event_days=int((transfer>0).sum()),transfer_event_count=len(events))
 for label,eq in [('trading',t),('total',w)]:
  ratio=d.total_margin_exact.to_numpy(float)*165/np.where(eq>0,eq,np.nan)
  metrics[label+'_margin_peak_pct']=float(np.nanmax(ratio)) if np.isfinite(ratio).any() else None
  metrics[label+'_margin_over100_days']=int((ratio>100).sum());metrics[label+'_margin_undefined_days']=int((eq<=0).sum())
 curves=dict(raw_account_equity=rawval,transfer_amount=transfer,cumulative_transfer=cumulative,trading_account_equity=t,reserve_balance=r,total_account_equity=w,nav=w/300000.,drawdown_pct=dd)
 return d,metrics,curves

def actual_open_warmup(path,start,epoch_lookup,calendar):
 raw=pd.read_csv(path/'daily.csv');dates=raw.date.astype(str).str[:10].tolist()
 ok(dates==[d for d in calendar if start<=d<='2026-10-29'],'full_calendar:'+str(path))
 near(raw.account_equity.iloc[0],150000,'first_raw');near(raw.net_pnl.iloc[0],0,'first_pnl')
 pre=load(path/'preflight.json');ok(pre['ready_need']==21 and pre['storage_capacity']==41,'ready21_storage41')
 settings=load(path/'actual_strategy_settings.json')[0]['actual'];ok(settings['trade_start_date']==start,'actual_cold_start')
 fills=pd.read_csv(path/'trades.csv');ok(not fills.trading_date.eq(dates[0]).any(),'no_inherited_firstday_fills')
 anchors=pd.read_csv(path/'execution_anchor_requests.csv');opens=fills.loc[fills.offset.isin(['开','open','Offset.OPEN'])]
 aa=anchors.loc[anchors.order_id.isin(opens.order_id)]
 ok(len(aa)==len(opens) and not aa.order_id.duplicated().any(),'actual_open_anchor_bijection')
 weekly=pd.read_csv(path/'weekly_bars.csv');calendar_weeks={}
 for day in calendar:calendar_weeks.setdefault(tuple(datetime.fromisoformat(day).isocalendar()[:2]),[]).append(day)
 completed={days[-1]:tuple(days) for days in calendar_weeks.values() if days[-1]!=calendar[-1] or datetime.fromisoformat(days[-1]).weekday()==4}
 for w in weekly[['week_end','source_days']].drop_duplicates().itertuples():
  ok(w.week_end in completed and tuple(ast.literal_eval(w.source_days))==completed[w.week_end],'actual_complete_exchange_week_no_partial_or_missing_session')
 groups={(s,e):sorted(g.week_end.tolist()) for (s,e),g in weekly.groupby(['vt_symbol','contract_epoch_id'])}
 counts=[];proofs=[]
 for a in aa.itertuples():
  day=str(a.signal_date)[:10];ok(day>=start,'no_prewindow_signal');epoch=epoch_lookup[(a.vt_symbol,day)]
  weeks=groups[(a.vt_symbol,epoch)];n=sum(w<=day for w in weeks);ok(n>=21,'actual_open_21_completed_weeks')
  counts.append(n);proofs.append(dict(order_id=a.order_id,symbol=a.vt_symbol,signal_date=day,epoch=epoch,completed_weeks=n))
 # Cold position file must have no inherited financial exposure on first day.
 for chunk in pd.read_csv(path/'positions.csv',usecols=['date','start_pos','end_pos','net_pnl','slippage','commission','trade_count'],chunksize=100000):
  q=chunk.loc[chunk.date.astype(str).str[:10].le(dates[0])];near(q.drop(columns='date').to_numpy(),0,'no_prewindow_or_firstday_position_finance')
 readiness=pd.read_csv(path/'weekly_readiness.csv');ok(readiness.date.astype(str).str[:10].tolist()==dates,'readiness_full_calendar')
 return dict(actual_first_day=dates[0],financial_days=len(dates),actual_open_fills=len(opens),minimum_completed_weeks=min(counts) if counts else None,first_open_signal_date=min((x['signal_date'] for x in proofs),default=None),first_day_readiness=readiness.iloc[0].to_dict(),actual_open_proof_sha256=hashlib.sha256(json.dumps(proofs,sort_keys=True).encode()).hexdigest())

def audit(report,available=False):
 ok(sha(F)==FREEZE_SHA,'locked_freeze');f=load(F);ok(tuple(f['starts'])==STARTS,'23_starts');ok(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==f['source_head'],'actual_frozen_HEAD');ok(sha(L/'tools/stage009_independent_window.py')==AUDITOR_SHA,'locked_window_auditor')
 sources={str(F):FREEZE_SHA,str(L/'tools/stage009_independent_window.py'):AUDITOR_SHA,str(Path(__file__)):sha(Path(__file__)),str(Path(__file__).with_name('test_stage009_independent_aggregate.py')):sha(Path(__file__).with_name('test_stage009_independent_aggregate.py'))}
 merge_map(sources,{str(Path(p) if Path(p).is_absolute() else ROOT/p):h for p,h in f['source_files_sha256'].items()})
 reg=load(B/'registry.json');old=load(f['idle_control_registry']);ok(reg['freeze_sha256']==FREEZE_SHA,'registry_freeze');ok(set(reg['jobs'])==set(old['jobs'])=={s+'|'+a for s in STARTS for a in ['A','C']},'exact46_candidate_and_idle_job_keys')
 data=L/'outputs/data_stage001_20261029/data_approved';dd=pd.read_csv(data/'physical_epoch_daily.csv',usecols=['vt_symbol','date','contract_epoch_id']);epochs={(r.vt_symbol,r.date):r.contract_epoch_id for r in dd.itertuples()};calendar=sorted(pd.read_csv(data/'mapping.csv',usecols=['date']).date.unique())
 receipts={};warmup={}
 for start in STARTS:
  for arm in ['A','C']:
   rp=L/'stages/stage009_independent_receipts'/f'{start}_{arm}.json'
   if not rp.exists() and available:continue
   r=load(rp);key=start+'|'+arm;cp=load(B/'checkpoints'/f'{start}_{arm}.json');j=reg['jobs'][key]
   ok(r['status']=='PASS_WITH_LIMITATIONS' and all(r[k]==0 for k in ['P0','P1','P2','failures']),'window_receipt_pass')
   ok((r['requested_start'],r['arm'],r['end'],r['freeze_sha256'],r['auditor_source_sha256'])==(start,arm,'2026-10-29',FREEZE_SHA,AUDITOR_SHA),'receipt_identity')
   ok(j['status']=='validated' and r['path']==j['path']==cp['path'],'receipt_exact_validated_attempt');ok(r['source_files_sha256']==cp['files_sha256']==j['files_sha256'],'receipt_checkpoint_registry_equal')
   ok(r['raw_core_checks']>0 and r['funding_checks']>0,'real_full_window_review')
   p=Path(r['path']);ok(set(r['source_files_sha256'])=={str(x) for x in p.iterdir() if x.is_file()},'no_omitted_attempt_file')
   merge_map(sources,r['source_files_sha256']);merge_map(sources,load(p/'input_manifest.json'));sources[str(rp)]=sha(rp)
   sources[str(B/'checkpoints'/f'{start}_{arm}.json')]=sha(B/'checkpoints'/f'{start}_{arm}.json')
   receipts[key]=r;warmup[key+'|reserve']=actual_open_warmup(p,start,epochs,calendar)
 if available:return dict(status='PARTIAL_NOT_FINAL',receipts=len(receipts),warmup=warmup,checks=checks)
 ok(len(receipts)==46 and reg['financial_engine_batch_complete'] is True and reg['financial_replays_started']==46,'46_real_completed')
 sources[str(B/'registry.json')]=sha(B/'registry.json')
 for name,digest in REVIEWED_SOURCES.items():
  vp=L/'tools'/name;ok(vp.is_file() and sha(vp)==digest,'locked_pure_postprocessor_source:'+name);sources[str(vp)]=digest
 comparison=load(report/'comparison.json');ok(comparison['source_head']==comparison['financial_source_head']==f['source_head'],'report_source_head');ok(comparison['total_initial_capital']==300000 and comparison['engine_initial_capital']==comparison['reserve_initial_capital']==150000,'report_capital_basis');ok(comparison['freeze_sha256']==FREEZE_SHA and comparison['promotion_decision']=='NO_PROMOTION','report_identity')
 ok(comparison['arm_windows']==comparison['paired_windows']==46 and comparison['independent_starts']==23 and comparison['summary_rows']==92 and comparison['total_daily_points']==141996,'report_counts')
 ok(tuple(comparison['starts'])==STARTS and tuple(comparison['variants'])==VARIANTS,'report_exact_scope')
 merge_map(sources,comparison['source_files_sha256']);ok(load(report/'source_hashes.json')==comparison['source_files_sha256'],'source_manifest_same')
 manifest=load(report/'delivery_manifest.json');ok({p.name for p in report.iterdir() if p.is_file()}==set(manifest['files_sha256'])|{'delivery_manifest.json'},'report_exact_manifest_file_set');verify_map({str(report/p):h for p,h in manifest['files_sha256'].items()})
 merge_map(sources,{str(p):sha(p) for p in report.iterdir() if p.is_file()})
 summary=pd.read_csv(report/'summary.csv');pairs=pd.read_csv(report/'paired.csv');cohorts=pd.read_csv(report/'cohort_summary.csv');daily=pd.read_csv(report/'all_daily.csv')
 ok(len(summary)==92 and set(zip(summary.start,summary.variant))=={(s,v) for s in STARTS for v in VARIANTS},'exact92_summary')
 ok(len(pairs)==46 and set(zip(pairs.start,pairs.arm))=={(s,a) for s in STARTS for a in ['A','C']},'exact46_pairs')
 ok(len(cohorts)==12 and set(zip(cohorts.arm,cohorts.cohort,cohorts['sample']))=={(a,c,s) for a in ['A','C'] for c in ['January','June','combined'] for s in ['complete_ge_1y','observation_lt_1y']},'exact12cohorts')
 ok(len(daily)==141996 and not daily.duplicated(['start','variant','date']).any(),'141996unique')
 recomputed={};expected_events=[]
 for row in summary.itertuples():
  start,variant=row.start,row.variant;arm=variant[0];reserve=variant.endswith('_R');key=start+'|'+arm
  path=Path(reg['jobs'][key]['path'] if reserve else old['jobs'][key]['path']);ok(row.source_path==str(path),'summary_exact_source')
  ledger=load(CACHE/(start.replace('-','')+'_'+variant)/'ledger.json')
  events=load(path/'reserve_events.json') if reserve else [];expected_events.extend(dict(e,start=start,variant=variant) for e in events)
  raw,m,curves=recompute(pd.read_csv(path/'daily.csv'),events);q=daily.loc[daily.start.eq(start)&daily.variant.eq(variant)]
  ok(q.date.tolist()==raw.date.tolist(),'report_calendar');ok(row.actual_start==raw.date.iloc[0] and row.actual_end=='2026-10-29','summary_dates')
  for name,want in m.items():near(getattr(row,name),want,'summary_metric:'+name)
  for name,want in curves.items():near(q[name].to_numpy(),want,'all_daily:'+name)
  for name in ['account_equity','net_pnl','slippage','commission','trade_count','total_margin_exact']:near(q[name].to_numpy(),raw[name].to_numpy(),'source_daily:'+name)
  ok(row.vote_eligible==(start!='2026-01-01') and row.observation_only==(start=='2026-01-01'),'mature_vote_scope')
  roundstats=ledger['accounting']['complete_contract_rounds']
  if reserve:
   ok(roundstats==receipts[key]['metrics']['rounds'],'signed_rounds');near(ledger['accounting']['open_round_net_mtm'],receipts[key]['metrics']['open_round_net_mtm'],'signed_open_mtm')
  else:
   oldledger=load(L/'outputs/stage008_derived/cache'/(start.replace('-','')+'_'+arm)/'ledger.json')
   ok(ledger['accounting']==oldledger['accounting'],'exact_idle_accounting');merge_map(sources,oldledger['source_files_sha256'])
   warmup[key+'|idle']=actual_open_warmup(path,start,epochs,calendar)
  for name,want in roundstats.items():near(getattr(row,'round_'+name),want,'closed_round_stats:'+name)
  near(row.open_round_net_mtm,ledger['accounting']['open_round_net_mtm'],'open_mtm');near(roundstats['closed_net_pnl']+row.open_round_net_mtm,m['net_pnl'],'closed_open_wealth_bridge')
  recomputed[(start,variant)]=m
 for p in pairs.itertuples():
  a=recomputed[(p.start,p.arm+'_idle')];r=recomputed[(p.start,p.arm+'_R')]
  comparisons={field:cmp(r[field],a[field]) for field in ['end_equity','max_dd_pct','sharpe']}
  for field in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count']:
   for prefix,value in [('idle_',a[field]),('reserve_',r[field]),('delta_',r[field]-a[field])]:near(getattr(p,prefix+field),value,'pair_'+prefix+field)
  for name,value in [('return_comparison',comparisons['end_equity']),('dd_comparison',comparisons['max_dd_pct']),('sharpe_comparison',comparisons['sharpe']),('equity_gate',comparisons['end_equity']>0),('dd_gate',comparisons['max_dd_pct']>=0),('sharpe_gate',comparisons['sharpe']>=0)]:near(getattr(p,name),value,'pair_'+name)
  ok(p.three_gate_pass==(comparisons['end_equity']>0 and comparisons['max_dd_pct']>=0 and comparisons['sharpe']>=0),'pair_three_gate')
  ok(p.vote_eligible==(p.start!='2026-01-01') and p.observation_only==(p.start=='2026-01-01'),'pair_vote');ok(p.cohort==('January' if p.start[5:7]=='01' else 'June'),'pair_cohort')
  near(p.total_transferred,r['total_transferred'],'pair_transfer');near(p.reserve_end_balance,r['reserve_end_balance'],'pair_reserve')
 for c in cohorts.itertuples():
  mature=c.sample=='complete_ge_1y';ok(c.sample in ['complete_ge_1y','observation_lt_1y'],'cohort_sample')
  pp=pairs.loc[pairs.arm.eq(c.arm)&pairs.vote_eligible.eq(mature)]
  if c.cohort!='combined':ok(c.cohort in ['January','June'],'cohort_label');pp=pp.loc[pp.cohort.eq(c.cohort)]
  rr=summary.loc[summary.start.isin(pp.start)&summary.variant.eq(c.arm+'_R')];n=len(pp);near(c.windows,n,'cohort_N');near(c.vote_windows,n if mature else 0,'cohort_votes');near(c.observation_windows,0 if mature else n,'cohort_observations')
  for label,field,value in [('return_wins','return_comparison',1),('return_ties','return_comparison',0),('return_losses','return_comparison',-1),('dd_wins','dd_comparison',1),('sharpe_wins','sharpe_comparison',1),('three_gate_pass_count','three_gate_pass',True)]:near(getattr(c,label),int(pp[field].eq(value).sum()) if mature else 0,'cohort_'+label)
  for label in ['return_wins','dd_wins','sharpe_wins','three_gate_pass_count']:near(getattr(c,label+'_rate_pct'),getattr(c,label)/n*100 if mature and n else None,'cohort_rate')
  expected=dict(reserve_negative_return_count=int(rr.total_return_pct.lt(0).sum()),reserve_nonpositive_total_windows=int(rr.nonpositive_total_equity_days.gt(0).sum()),reserve_nonpositive_trading_windows=int(rr.nonpositive_trading_equity_days.gt(0).sum()),exhausted_reserve_windows=int(rr.reserve_end_balance.le(1e-6).sum()),reserve_trading_margin_failure_windows=int((rr.trading_margin_over100_days.gt(0)|rr.nonpositive_trading_equity_days.gt(0)).sum()),median_transfer=rr.total_transferred.median() if n else None,median_dd_pct=rr.max_dd_pct.median() if n else None,worst_dd_pct=rr.max_dd_pct.min() if n else None,median_sharpe=rr.sharpe.median() if n else None,worst_sharpe=rr.sharpe.min() if n else None)
  for name,want in expected.items():near(getattr(c,name),want,'cohort_'+name)
 reported_events=pd.read_csv(report/'reserve_events.csv');ok(len(reported_events)==len(expected_events),'all_report_events')
 if expected_events:ok(set(reported_events.columns)==set(expected_events[0]),'report_event_exact_fields')
 for got,want in zip(reported_events.to_dict('records'),expected_events):
  for field,value in want.items():
   if value is None:ok(pd.isna(got[field]),'report_event_null:'+field)
   elif isinstance(value,(bool,int,float)):near(got[field],value,'report_event_numeric:'+field)
   else:ok(got[field]==value,'report_event_text:'+field)
 ok(tuple(comparison['five_figures'])==FIGURES,'exact_five_figures');figure_sizes={}
 for name in FIGURES:
  with Image.open(report/name) as im:ok(im.format=='PNG' and im.width>=1500 and im.height>=1000,'figure_valid_png');figure_sizes[name]=[im.width,im.height];im.verify()
 decision=load(report/'decision.json');ok(decision['promotion_decision']=='NO_PROMOTION' and decision['strategy_verdict']==comparison['strategy_verdict'],'no_promotion_verdict')
 for arm in ['A','C']:
  cc=cohorts.loc[cohorts.arm.eq(arm)&cohorts.cohort.eq('combined')&cohorts['sample'].eq('complete_ge_1y')].iloc[0]
  for k,v in comparison['arms'][arm].items():near(v,cc[k],'decision_'+k)
  ok(decision['arms'][arm]==comparison['arms'][arm],'decision_arms_same')
 economic_pass=all(x['three_gate_pass_count']==22 and all(x[k]==0 for k in ['reserve_negative_return_count','reserve_nonpositive_total_windows','reserve_nonpositive_trading_windows','reserve_trading_margin_failure_windows']) for x in comparison['arms'].values())
 ok(comparison['strategy_verdict']==('PASS_FIXED_USER_SCOPE_ONLY' if economic_pass else 'MIXED_OR_FAIL_NO_RESCUE_TUNING'),'economic_verdict_recomputed')
 verify_map(sources)
 outputs={str(p):sha(p) for p in report.iterdir() if p.is_file()}
 return dict(arms=comparison['arms'],status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,freeze_sha256=FREEZE_SHA,source_head=f['source_head'],arm_windows=46,paired_windows=46,independent_starts=23,summary_rows=92,cohort_rows=12,total_daily_points=141996,independent_checks=checks,raw_core_checks=sum(r['raw_core_checks'] for r in receipts.values()),funding_checks=sum(r['funding_checks'] for r in receipts.values()),report_comparison_sha256=sha(report/'comparison.json'),report_directory=str(report),report_files_sha256=outputs,source_files_sha256=sources,auditor_source_sha256=sha(Path(__file__)),window_auditor_sha256=AUDITOR_SHA,warmup_coldstart_evidence=warmup,figure_sizes=figure_sizes,financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',strategy_verdict=comparison['strategy_verdict'],reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),limitations=comparison['limitations'])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=REPORT);ap.add_argument('--available',action='store_true');ap.add_argument('--output',type=Path);args=ap.parse_args()
 if args.output:ok(not args.output.exists(),'immutable_final_review')
 r=audit(args.report,args.available)
 if args.output:
  ok(not args.available,'partial_review_cannot_sign_final');args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ['source_files_sha256','report_files_sha256','warmup_coldstart_evidence','warmup']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
