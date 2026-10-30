"""Atomic five-figure report for 23 user-declared fresh start-to-cutoff pairs.

Financial caches are independently derived by stage008_accounting.py. No engine
or market download is invoked here; all 46 arm-windows are mandatory.
"""
from __future__ import annotations
import argparse,json,math,os,tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage008_accounting as acct
LINE=acct.LINE;OUT=LINE/'artifacts/stage008_multistart';A_COLOR='#2467a6';C_COLOR='#b4234a'
FIGURE_NAMES=['01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_start_to_cutoff_heatmaps.png','05_cohort_summary_weakest.png']

def compare_metric(candidate,baseline):
 if candidate is None or baseline is None or not math.isfinite(float(candidate)) or not math.isfinite(float(baseline)):raise ValueError('finite_paired_metric_required')
 if np.isclose(candidate,baseline,rtol=1e-10,atol=1e-7):return 0
 return 1 if candidate>baseline else -1

def flatten_cache(d):
 m=d['metrics'];a=d['accounting'];r=d['risk'];w=d['window'];peak=r['actual_margin_to_equity_max_pct'];survival=m['nonpositive_equity_days']==0 and m['end_equity']>0;margin_unknown=peak is None or r['nonpositive_equity_risk_ratio_undefined_days']>0
 return dict(start=d['start'],arm=d['arm'],cohort=w['cohort'],vote_eligible=w['vote_eligible'],observation_only=w['observation_only'],reused=d['reused'],source_path=d['source_path'],**m,nav_end=m['end_equity']/150000.,**{'fifo_'+k:v for k,v in a['closed_fifo'].items()},**{'round_'+k:v for k,v in a['complete_contract_rounds'].items()},open_round_count=a['open_round_count'],open_round_net_mtm=a['open_round_net_mtm'],open_remaining_net_mtm=a['open_remaining_net_mtm'],**r,survival_pass=survival,configured_margin_pass=not margin_unknown and r['actual_margin_over100_days']==0,configured_margin_unknown=margin_unknown)

def make_pairs(summary):
 expected={(s,a) for s in acct.STARTS for a in ['A','C']};keys=list(zip(summary.start,summary.arm))
 if len(keys)!=46 or len(set(keys))!=46 or set(keys)!=expected:raise ValueError('all46_unique_arm_windows_required_before_final_publication')
 pairs=[]
 for start in acct.STARTS:
  sub=summary.loc[summary.start.eq(start)];a=sub.loc[sub.arm.eq('A')].iloc[0];c=sub.loc[sub.arm.eq('C')].iloc[0];meta=acct.window_meta(start)
  for row in [a,c]:
   if bool(row.vote_eligible)!=meta['vote_eligible'] or bool(row.observation_only)!=meta['observation_only'] or row.cohort!=meta['cohort']:raise ValueError('vote_scope_metadata_drift')
   if row.actual_start!=meta['actual_first_day'] or row.actual_end!=acct.END or row.trading_days!=meta['trading_days']:raise ValueError('paired_actual_window_drift')
  checks={k:compare_metric(c[k],a[k]) for k in ['end_equity','max_dd_pct','sharpe']};delta={f'delta_{k}':float(c[k]-a[k]) for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count']}
  pairs.append(dict(start=start,cohort=meta['cohort'],actual_start=meta['actual_first_day'],end=acct.END,trading_days=meta['trading_days'],vote_eligible=meta['vote_eligible'],observation_only=meta['observation_only'],A_end_equity=a.end_equity,C_end_equity=c.end_equity,A_return_pct=a.total_return_pct,C_return_pct=c.total_return_pct,A_max_dd_pct=a.max_dd_pct,C_max_dd_pct=c.max_dd_pct,A_sharpe=a.sharpe,C_sharpe=c.sharpe,return_comparison=checks['end_equity'],dd_comparison=checks['max_dd_pct'],sharpe_comparison=checks['sharpe'],equity_gate=checks['end_equity']>0,dd_gate=checks['max_dd_pct']>=0,sharpe_gate=checks['sharpe']>=0,three_gate_pass=checks['end_equity']>0 and checks['max_dd_pct']>=0 and checks['sharpe']>=0,**delta))
 return pd.DataFrame(pairs)

def aggregate(summary,paired):
 rows=[]
 for cohort in ['January','June','combined']:
  for sample,eligible in [('complete_ge_1y',True),('observation_lt_1y',False)]:
   p=paired.loc[paired.vote_eligible.eq(eligible)]
   if cohort!='combined':p=p.loc[p.cohort.eq(cohort)]
   selected=summary.loc[summary.start.isin(p.start)];n=len(p);voters=n if eligible else 0
   row=dict(cohort=cohort,sample=sample,windows=n,vote_windows=voters,observation_windows=0 if eligible else n,return_wins=int(p.return_comparison.gt(0).sum()) if eligible else 0,return_ties=int(p.return_comparison.eq(0).sum()) if eligible else 0,return_losses=int(p.return_comparison.lt(0).sum()) if eligible else 0,dd_wins=int(p.dd_comparison.gt(0).sum()) if eligible else 0,sharpe_wins=int(p.sharpe_comparison.gt(0).sum()) if eligible else 0,three_gate_pass_count=int(p.three_gate_pass.sum()) if eligible else 0)
   for key in ['return_wins','dd_wins','sharpe_wins','three_gate_pass_count']:row[key+'_rate_pct']=row[key]/voters*100 if voters else None
   for arm in ['A','C']:
    s=selected.loc[selected.arm.eq(arm)];peak=s.actual_margin_to_equity_max_pct;unknown=peak.isna()|s.nonpositive_equity_risk_ratio_undefined_days.gt(0);survival=s.nonpositive_equity_days.eq(0)&s.end_equity.gt(0)
    row.update({arm+'_negative_return_count':int(s.total_return_pct.lt(0).sum()),arm+'_positive_return_count':int(s.total_return_pct.gt(0).sum()),arm+'_flat_return_count':int(s.total_return_pct.eq(0).sum()),arm+'_survival_failure_count':int((~survival).sum()),arm+'_configured_margin_failure_count':int((s.actual_margin_over100_days.gt(0)|unknown).sum()),arm+'_configured_margin_unknown_count':int(unknown.sum()),arm+'_median_dd_pct':float(s.max_dd_pct.median()) if len(s) else None,arm+'_worst_dd_pct':float(s.max_dd_pct.min()) if len(s) else None,arm+'_median_sharpe':float(s.sharpe.median()) if len(s) else None,arm+'_worst_sharpe':float(s.sharpe.min()) if len(s) else None,arm+'_minimum_total_return_pct':float(s.total_return_pct.min()) if len(s) else None})
   rows.append(row)
 return pd.DataFrame(rows)

def weakest_windows(summary):
 result=[]
 for scope,mask in [('complete_ge_1y',summary.vote_eligible),('observation_lt_1y',~summary.vote_eligible),('all_displayed',pd.Series(True,index=summary.index))]:
  for arm in ['A','C']:
   s=summary.loc[mask&summary.arm.eq(arm)]
   if s.empty:continue
   for metric,ascending in [('total_return_pct',True),('max_dd_pct',True),('sharpe',True),('total_slippage',False),('actual_margin_to_equity_max_pct',False)]:
    row=s.sort_values([metric,'start'],ascending=[ascending,True]).iloc[0];result.append(dict(scope=scope,arm=arm,metric=metric,value=row[metric],start=row.start,actual_start=row.actual_start,end=row.actual_end,trading_days=row.trading_days,vote_eligible=row.vote_eligible))
 return pd.DataFrame(result)

def load_complete_bundle():
 freeze=acct.freeze_contract();registry=json.loads(acct.REGISTRY.read_text());expected={s+'|'+a for s in acct.STARTS for a in ['A','C']}
 if registry['freeze_sha256']!=acct.FREEZE_SHA or set(registry['jobs'])!=expected or any(x.get('status')!='validated' for x in registry['jobs'].values()):raise ValueError('all46_registry_jobs_must_be_validated')
 caches={};sources={str(p.resolve()):acct.sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage008_report.py'),acct.FREEZE,acct.PREFLIGHT,Path(acct.__file__)]};reference_settings=reference_effective=None
 for start in acct.STARTS:
  for arm in ['A','C']:
   key=start+'|'+arm;job=registry['jobs'][key];expected_path=Path(freeze['reuse_runs'].get(key,str(LINE/'outputs'/f'stage008_{arm}_{start.replace("-","")}_attempt001'))).resolve()
   if Path(job['path']).resolve()!=expected_path or (job['start'],job['arm'],job['end'])!=(start,arm,acct.END):raise ValueError('registry_source_not_declared')
   path=acct.cache_path(start,arm)
   if not path.exists():raise ValueError('missing_derived_cache:'+key)
   d=acct.verify_cache(path,job,deep=False)
   if d['start']!=start or d['arm']!=arm or d['attempt_snapshot']!=job['files_sha256']:raise ValueError('cache_registration_or_snapshot_mismatch')
   acct.check_registered_metrics(d['metrics'],job['metrics'])
   if reference_settings is None:reference_settings=d['normalized_settings'];reference_effective=d['effective']
   if d['normalized_settings']!=reference_settings or d['effective']!=reference_effective:raise ValueError('nondeclared_parameter_change_across_starts')
   if arm=='C' and (d['settings']!=caches[(start,'A')]['settings'] or d['effective']!=caches[(start,'A')]['effective']):raise ValueError('same_window_arm_parameters_differ')
   daily=pd.read_csv(path/'daily.csv');daily['date']=pd.to_datetime(daily.date);acct.validate_window(d['preflight'],daily,start);nav,dd=acct.range_contract.nav_drawdown(daily.account_equity)
   if not np.allclose(daily.nav,nav,rtol=1e-12,atol=1e-12) or not np.allclose(daily.drawdown_pct,dd,rtol=1e-12,atol=1e-12):raise ValueError('derived_NAV_or_DD_drift')
   d['_daily']=daily;d['_cache_path']=path;caches[(start,arm)]=d
   for p,h in d['source_files_sha256'].items():
    if p in sources and sources[p]!=h:raise ValueError('conflicting_frozen_source_hash')
    sources[p]=h
   for p in path.iterdir():
    if p.is_file():sources[str(p.resolve())]=acct.sha(p)
 acct.verify_sources(sources);return caches,sources,freeze

def _plot_setup():
 os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import matplotlib.dates as mdates
 return plt,mdates

def _decorate(ax):ax.grid(alpha=.16);ax.spines[['top','right']].set_visible(False)
def _state(reviewed):return 'REVIEW PASSED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'

def render_figures(caches,summary,paired,cohorts,weakest,out,reviewed=False):
 plt,mdates=_plot_setup();out=Path(out);state=_state(reviewed)
 # 1. Exact full-period independent2015 NAV and DD.
 fig,(a,b)=plt.subplots(2,1,figsize=(13,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for arm,color in [('A',A_COLOR),('C',C_COLOR)]:
  d=caches[('2015-01-01',arm)]['_daily'];a.plot(d.date,d.nav,color=color,lw=1.5,label=arm+(' no price gate' if arm=='A' else ' short bottom-20% only'));b.plot(d.date,d.drawdown_pct,color=color,lw=1.3)
 a.axhline(1,color='#aaa',lw=.6,ls='--');a.legend(frameon=False);a.set_ylabel('NAV = equity / 150,000');b.set_ylabel('Drawdown (%)');b.set_xlabel('Exchange trading date')
 for ax in [a,b]:_decorate(ax)
 fig.suptitle('STAGE008 1/5 | '+state+' | NO PROMOTION\nFull independent start: requested2015-01-01 / actual2015-01-05 -> 2026-10-29\nOriginal19 | CNY150,000 each | no addon / MA slope and long price gates OFF',fontsize=11,fontweight='bold');fig.tight_layout(rect=[0,.02,1,.88]);fig.savefig(out/FIGURE_NAMES[0],dpi=155);plt.close(fig)
 # 2/3. January/June fresh accounts to identical cutoff, never fixed-year slices.
 for cohort,count,index in [('January',12,1),('June',11,2)]:
  starts=[s for s in acct.STARTS if acct.window_meta(s)['cohort']==cohort];fig,axes=plt.subplots(4,3,figsize=(14.6,11.2));flat=axes.flat
  for i,start in enumerate(starts):
   ax=flat[i];meta=acct.window_meta(start)
   for arm,color in [('A',A_COLOR),('C',C_COLOR)]:
    d=caches[(start,arm)]['_daily'];ax.plot(d.date,d.nav,color=color,lw=1.,label=arm)
   star='*' if meta['observation_only'] else '';ax.set_title(start+star+' -> '+acct.END,fontsize=9,fontweight='bold');ax.text(.02,.95,'actual '+meta['actual_first_day']+' | '+str(meta['trading_days'])+' days',transform=ax.transAxes,fontsize=7,va='top',color='#667085');span=meta['elapsed_calendar_days'];loc=mdates.YearLocator(base=4 if span>365*6 else (2 if span>365*3 else 1)) if span>365 else mdates.MonthLocator(bymonth=[1,4,7,10]);ax.xaxis.set_major_locator(loc);ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y' if span>365 else '%b%Y'));ax.tick_params(labelsize=7);_decorate(ax)
   if i%3==0:ax.set_ylabel('NAV',fontsize=8)
  for i in range(len(starts),12):flat[i].set_visible(False)
  flat[0].legend(frameon=False,fontsize=7,loc='lower right');fig.suptitle(f'STAGE008 {index+1}/5 | {cohort} fresh-start-to-cutoff NAV | '+state+'\nUser scope: each stated start -> 2026-10-29; NOT fixed1/2/3-year windows | CNY150,000 each',fontsize=11,fontweight='bold');fig.text(.06,.015,'A blue: no price gate; C red: short bottom-20% only. Each window is a fresh account; never a full-curve slice. '+('* 2026Jan <1year: observation only, excluded from voting.' if cohort=='January' else 'All11 June1 windows cover at least one full year.'),fontsize=8,color='#667085');fig.tight_layout(rect=[.01,.045,.995,.91]);fig.savefig(out/FIGURE_NAMES[index],dpi=155);plt.close(fig)
 # 4. Per-start returns/DD and paired deltas with separate scales.
 fig,axes=plt.subplots(2,3,figsize=(14.8,12));ordered=paired.set_index('start').loc[acct.STARTS];spec=[('A_return_pct','A total return (%)','YlGnBu'),('C_return_pct','C total return (%)','YlGnBu'),('delta_total_return_pct','C - A total return (pp)','RdYlGn'),('A_max_dd_pct','A max drawdown (%)','RdYlGn'),('C_max_dd_pct','C max drawdown (%)','RdYlGn'),('delta_sharpe','C - A Sharpe','RdYlGn')]
 labels=[s+('*' if acct.window_meta(s)['observation_only'] else '') for s in acct.STARTS]
 for ax,(field,title,cmap) in zip(axes.flat,spec):
  values=ordered[field].to_numpy(float).reshape(-1,1)
  if field in {'A_return_pct','C_return_pct'}:
   shared=np.r_[ordered.A_return_pct.to_numpy(),ordered.C_return_pct.to_numpy()];lo,hi=float(shared.min()),float(shared.max())
  elif field in {'A_max_dd_pct','C_max_dd_pct'}:lo,hi=min(-100.,float(ordered[['A_max_dd_pct','C_max_dd_pct']].min().min())),0.
  else:bound=max(float(np.abs(values).max()),.001);lo,hi=-bound,bound
  if hi==lo:step=max(abs(lo)*.1,.001);lo-=step;hi+=step
  image=ax.imshow(values,aspect='auto',cmap=cmap,vmin=lo,vmax=hi);ax.set_xticks([]);ax.set_yticks(range(23),labels,fontsize=7);ax.set_title(title,fontsize=10)
  for j,v in enumerate(values[:,0]):
   rgba=image.cmap(image.norm(v));lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2];ax.text(0,j,f'{v:.2f}' if 'sharpe' in field else f'{v:,.1f}',ha='center',va='center',fontsize=7,color='white' if lum<.5 else '#17202a')
  fig.colorbar(image,ax=ax,fraction=.045,pad=.025)
 fig.suptitle('STAGE008 4/5 | 23 exact start-to-cutoff pairs | '+state+'\nDifferent durations: do NOT interpret average total returns as expected return',fontsize=11,fontweight='bold');fig.text(.06,.015,'* 2026Jan <1year is shown but does not vote. All A/C pairs use identical source, capital, costs and date window; cutoff2026-10-29.',fontsize=8,color='#667085');fig.tight_layout(rect=[0,.04,1,.93]);fig.savefig(out/FIGURE_NAMES[3],dpi=155);plt.close(fig)
 # 5. Complete-window cohort votes, risks and weakest windows; no mean return.
 fig,axes=plt.subplots(2,2,figsize=(14.8,10));complete=cohorts[cohorts['sample'].eq('complete_ge_1y')].set_index('cohort').loc[['January','June','combined']]
 x=np.arange(3);width=.22
 for offset,key,color,label in [(-1,'return_wins','#2467a6','Equity strictly higher'),(0,'dd_wins','#b4234a','Drawdown better'),(1,'sharpe_wins','#c08128','Sharpe higher')]:axes[0,0].bar(x+offset*width,complete[key],width,color=color,label=label)
 axes[0,0].set_xticks(x,['January (11)','June (11)','Combined (22)']);axes[0,0].set_ylabel('Paired wins / complete windows');axes[0,0].legend(fontsize=8,frameon=False);_decorate(axes[0,0])
 ax=axes[0,1];ax.axis('off');table_rows=[[k,int(v.windows),int(v.three_gate_pass_count),int(v.A_negative_return_count),int(v.C_negative_return_count),int(v.C_survival_failure_count),int(v.C_configured_margin_failure_count)] for k,v in complete.iterrows()];tab=ax.table(cellText=table_rows,colLabels=['Cohort','N','3-gates','A neg','C neg','C dead','C margin fail'],loc='center',cellLoc='center');tab.auto_set_font_size(False);tab.set_fontsize(8);tab.scale(1.1,1.7);ax.set_title('Complete >=1year only: strict equity>, DD>=, Sharpe>=',fontsize=10)
 ax=axes[1,0];ax.axis('off');weak=weakest.loc[weakest.scope.eq('complete_ge_1y')&weakest.arm.eq('C')];friendly={'total_return_pct':'Total return (%)','max_dd_pct':'Max drawdown (%)','sharpe':'Sharpe','total_slippage':'Slippage (CNY)','actual_margin_to_equity_max_pct':'Static margin peak (%)'};wrows=[[friendly.get(str(r.metric),str(r.metric)),str(r.start),f'{float(r.value):,.3f}'] for r in weak.itertuples()];tab=ax.table(cellText=wrows,colLabels=['C weakest / risk-highest','Start -> 2026-10-29','Value'],loc='center',cellLoc='center');tab.auto_set_font_size(False);tab.set_fontsize(8);tab.scale(1.05,1.45);ax.set_title('Weakest complete-window C (not a new tuned sample)',fontsize=10)
 ax=axes[1,1];ax.axis('off');obs=paired.loc[paired.observation_only].iloc[0];texts=['2026-01-01 observation only: NO VOTE',f"A return {obs.A_return_pct:,.2f}% | C return {obs.C_return_pct:,.2f}%",f"A DD {obs.A_max_dd_pct:.2f}% | C DD {obs.C_max_dd_pct:.2f}%",f"A Sharpe {obs.A_sharpe:.3f} | C Sharpe {obs.C_sharpe:.3f}",'',f"Complete C median / worst DD: {complete.loc['combined','C_median_dd_pct']:.2f}% / {complete.loc['combined','C_worst_dd_pct']:.2f}%",f"Complete C median / worst Sharpe: {complete.loc['combined','C_median_sharpe']:.3f} / {complete.loc['combined','C_worst_sharpe']:.3f}",'','Static exchange margin x1.65; zero commission.','Cached history is not complete listing/PIT truth.','Capital-path differences are not direct filter alpha.'];ax.text(.03,.95,'\n'.join(texts),va='top',fontsize=10,linespacing=1.7)
 fig.suptitle('STAGE008 5/5 | User-defined start-to-now cohort summary | '+state+'\n23 displayed pairs / 22 complete votes / one observation | NO PROMOTION',fontsize=11,fontweight='bold');fig.text(.06,.015,'No fixed1/2/3-year claims; no mean total-return forecast. Margin fail uses configured static x1.65 ratio, not historical actual broker margin.',fontsize=8,color='#667085');fig.tight_layout(rect=[0,.045,1,.91]);fig.savefig(out/FIGURE_NAMES[4],dpi=155);plt.close(fig)
 return FIGURE_NAMES

def build(out=OUT):
 out=Path(out)
 if out.resolve()!=OUT.resolve() or out.exists():raise ValueError('assigned_immutable_stage008_output_required')
 caches,sources,freeze=load_complete_bundle();summary=pd.DataFrame([flatten_cache(caches[(s,a)]) for s in acct.STARTS for a in ['A','C']]);paired=make_pairs(summary);cohorts=aggregate(summary,paired);weakest=weakest_windows(summary);complete=cohorts[(cohorts.cohort=='combined')&(cohorts['sample']=='complete_ge_1y')].iloc[0];total_points=sum(len(d['_daily']) for d in caches.values());elig=paired[paired.vote_eligible]
 conclusion='PASS_USER_SCOPE_COMPLETE_WINDOWS_ONLY' if bool(elig.three_gate_pass.all()) and complete.C_negative_return_count==0 and complete.C_survival_failure_count==0 and complete.C_configured_margin_failure_count==0 else 'MIXED_OR_FAIL_NO_RESCUE_TUNING'
 doc=dict(schema='stage008_user23_start_to_cutoff_report_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),review_status='PENDING_INDEPENDENT_REVIEW',strategy_verdict=conclusion,promotion_decision='NO_PROMOTION',production_qualified=False,scope='User-declared23 independent starts -> same cutoff; NOT fixed1/2/3-year validation',starts=acct.STARTS,cutoff=acct.END,arm_windows=46,independent_pairs=23,complete_vote_pairs=22,observation_pairs=1,expected_engine_replays=42,reused_arms=4,financial_replays=0,market_downloads=0,production_accesses=0,total_daily_points=total_points,freeze_sha256=acct.FREEZE_SHA,financial_source_head=freeze['source_head'],five_figures=FIGURE_NAMES,curve_definition='NAV=actual account_equity/150000; DD includes initial150000 high-water mark; every start is a fresh engine/account, never a slice.',vote_rule='Complete>=1year only; C equity strictly>A, C DD>=A, C Sharpe>=A; ties in equity do not pass; rtol1e-10/atol1e-7 only CSV numeric round-trip tolerance.',aggregation_warning='Different durations: paired counts/cohort risks/median-worst DD and Sharpe are descriptive. No average total return is an expected-return estimate.',source_files_sha256=sources,cohort_summary=cohorts.to_dict('records'),weakest_windows=weakest.to_dict('records'),data_identity=freeze['data_identity'],limitations=['Historical repeated development, no new OOS/PIT or production qualification.','Original19 static universe, zero commission, fixed slippage and static exchange margin x1.65.','Configured margin failures are not historical actual broker margin. Under1year observation is displayed without votes.','Cached same-physical-epoch history is not complete listing history; inherited known gaps/classifications remain.','No partial publication: all46 financial caches and all23 pairs verified before atomic final output.'])
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.stage008_final_',dir=out.parent) as tmp:
  tables=Path(tmp)/'report';tables.mkdir();summary.to_csv(tables/'summary.csv',index=False);paired.to_csv(tables/'paired.csv',index=False);cohorts.to_csv(tables/'cohort_summary.csv',index=False);weakest.to_csv(tables/'weakest_windows.csv',index=False);all_daily=[];annual=[]
  for (start,arm),d in caches.items():all_daily.append(d['_daily'].assign(start=start,arm=arm));annual.append(pd.read_csv(d['_cache_path']/'annual.csv').assign(start=start,arm=arm))
  pd.concat(all_daily,ignore_index=True).to_csv(tables/'all_daily.csv',index=False);pd.concat(annual,ignore_index=True).to_csv(tables/'annual.csv',index=False);render_figures(caches,summary,paired,cohorts,weakest,tables);doc['output_files_sha256']={str(out/p.name):acct.sha(p) for p in tables.iterdir() if p.is_file()};acct.write_json(tables/'comparison.json',doc);acct.write_json(tables/'decision.json',dict(strategy_verdict=conclusion,promotion_decision='NO_PROMOTION',complete_pairs=22,observation_only_pairs=1,return_win_count=int(complete.return_wins),three_gate_pass_count=int(complete.three_gate_pass_count),C_negative_complete_windows=int(complete.C_negative_return_count),C_survival_failure_count=int(complete.C_survival_failure_count),C_configured_margin_failure_count=int(complete.C_configured_margin_failure_count),scope=doc['scope']))
  report='# Stage008 固定23独立起点至同截止：多起点报告\n\n结论：'+conclusion+' / NO_PROMOTION。\n\n用户范围为2015—2025各1/1、6/1及2026-1/1到2026-10-29，不是固定1/2/3年窗口。46臂窗全部验收后原子发布，4复用/42新引擎；每臂150000空仓独立起跑。\n\nJanuary11完整+1观察，June11完整，combined22完整投票；2026Jan不足1年只展示不投票。权益严格更高、DD不更差、Sharpe不更低三门；窗口长度不同，不把总收益均值当预期收益。\n\n'+cohorts.to_csv(index=False)+'\n\n逐窗summary/paired、年度annual、最弱窗weakest和五图在同目录。0报告金融回放/0下载/0生产，原始账本与配置未改。独审状态PENDING，财务派生成功不等于策略晋级。\n';(tables/'report.md').write_text(report);acct.write_json(tables/'source_hashes.json',sources);manifest=dict(schema='stage008_atomic_final_delivery_v1',review_status='PENDING_INDEPENDENT_REVIEW',files_sha256={p.name:acct.sha(p) for p in tables.iterdir() if p.is_file()},self_hash_excluded=True,all46_arm_windows_verified=True,total_daily_points=total_points,financial_replays=0);acct.write_json(tables/'delivery_manifest.json',manifest);acct.verify_sources(sources)
  if out.exists():raise ValueError('immutable_output_appeared_during_build')
  os.rename(tables,out)
 print(json.dumps(dict(status='ALL46_DERIVED_PENDING_INDEPENDENT_REVIEW',pairs=23,votes=22,observation=1,total_points=total_points,strategy_verdict=conclusion,return_wins=int(complete.return_wins),three_gate_passes=int(complete.three_gate_pass_count)),ensure_ascii=False));return doc

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=OUT);x=ap.parse_args();build(x.out)
if __name__=='__main__':main()
