"""Three frozen independent-2015 accounts, pure accounting and NAV/DD only."""
from __future__ import annotations
import argparse,json,os,tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage006_report as base
LINE=Path(__file__).resolve().parents[1];OUT=LINE/'artifacts/stage007_comparison';FIGURE=LINE/'artifacts/stage007_nav_drawdown.png';CAPITAL=150000.;LONG_THRESHOLD=.8;TOP_FRACTION=.2
PATHS={'original':LINE/'outputs/stage006_A_attempt001','short_only':LINE/'outputs/stage006_C_attempt001','long_top20':LINE/'outputs/stage007_C_attempt001'}
LABELS={'original':'Original: no price-range gates','short_only':'Stage006: short bottom-20% only','long_top20':'NEW Stage007: short bottom-20% + long top-20% / breakout exempt'}
sha=base.sha;verify_sources=base.verify_sources;nav_drawdown=base.nav_drawdown

def validate_long_gate(pre,proof):
 expected_pre=dict(long_price_range_gate_enabled=True,long_price_range_threshold=LONG_THRESHOLD,long_price_range_history='all_available_same_physical_epoch_daily_strictly_before_signal',long_breakout_above_prior_high_exempt=True)
 expected=dict(accepted=True,enabled=True,top_fraction=TOP_FRACTION,position_threshold=LONG_THRESHOLD,comparison='prior_low_plus_0p8_range_lte_signal_close_lte_prior_high',history_scope='all_available_same_physical_epoch_daily_strictly_before_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=False,breakout_exemption=True,breakout_rule='signal_close_strictly_gt_prior_high',rollover_gate_applied=False,flat_range_policy='equal_high_block_above_high_exempt_below_high_allow',signals=['long_case1a','long_case2'],listing_start_completeness_proven=False)
 if any(pre.get(k)!=v for k,v in expected_pre.items()) or any(proof.get(k)!=v for k,v in expected.items()):raise ValueError('actual_long_prior_top20_with_strict_breakout_contract_required')
 return True

def require_output(out,figure):
 if Path(out).resolve()!=OUT.resolve() or Path(figure).resolve()!=FIGURE.resolve():raise ValueError('assigned_stage007_outputs_only')
 if OUT.exists() or FIGURE.exists():raise ValueError('immutable_report_exists')

def plot(ledgers,path,reviewed=False):
 os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,(a,b)=plt.subplots(2,1,figsize=(13,7.7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for role,color,lw,ls in [('original','#8b939c',1.1,'--'),('short_only','#2467a6',1.4,'-'),('long_top20','#b4234a',2.1,'-')]:
  d=ledgers[role]['daily'];nav,dd=nav_drawdown(d.account_equity);a.plot(d.date,nav,color=color,lw=lw,ls=ls,label=LABELS[role]+f' | NAV {nav[-1]:.3f}');b.plot(d.date,dd,color=color,lw=lw,ls=ls)
 a.axhline(1.,color='#9ca3af',lw=.7,ls='--');a.legend(frameon=False,fontsize=8.5,loc='upper left');a.set_ylabel('NAV = equity / CNY150,000');b.set_ylabel('Drawdown (%)');b.set_xlabel('Exchange trading date')
 for ax in [a,b]:ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
 state='INDEPENDENT REVIEW PASSED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING';fig.suptitle('STAGE007 / '+state+' / OFFLINE RESEARCH / NO PROMOTION\n2015-01-05 to 2026-10-29 | original19 | CNY150,000 each | no addon / MA slope gates OFF\nLong uses strictly-prior cached daily range; short rule unchanged; daily next-open; zero commission',fontsize=10.5,fontweight='bold')
 fig.text(.1,.025,'Long: prior L+0.8(H-L) <= signal close <= prior H blocks; close > prior H exempts ONLY this gate.\nShort still includes signal day in cached epoch bottom-20% range. Cache is not complete listing history; static margin x1.65.',fontsize=8,color='#667085');fig.tight_layout(rect=[0,.065,1,.89]);fig.savefig(path,dpi=170);plt.close(fig)

def build(out=OUT,figure=FIGURE):
 require_output(out,figure);ledgers={}
 for role,path in PATHS.items():
  print('Auditing frozen independent-2015 ledger: '+role,flush=True);x=base.load_price_ledger(path,'baseline' if role=='original' else 'candidate');x['role']=role;ledgers[role]=x
  if role=='long_top20':validate_long_gate(x['preflight'],x['acceptances'].get('long_price_range_acceptance.json',{}))
  elif x['preflight'].get('long_price_range_gate_enabled',False) is not False:raise ValueError('old_control_long_gate_unexpected')
 for x in ledgers.values():base.same_contract(ledgers['short_only'],x)
 sources={str(p.resolve()):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage007_report.py'),Path(base.__file__),Path(base.legacy.__file__)]}
 for x in ledgers.values():
  for p,d in x['sources'].items():
   if p in sources and sources[p]!=d:raise ValueError('conflicting_source_hash')
   sources[p]=d
 verify_sources(sources);rows=[]
 for role,x in ledgers.items():
  rows.append(dict(role=role,version_label=LABELS[role],**x['metrics'],nav_end=x['metrics']['end_equity']/CAPITAL,**{'fifo_'+k:v for k,v in x['accounting']['closed_fifo'].items()},**{'round_'+k:v for k,v in x['accounting']['complete_contract_rounds'].items()},**x['risk'],open_round_count=x['accounting']['open_round_count'],open_round_net_mtm=x['accounting']['open_round_net_mtm'],open_remaining_net_mtm=x['accounting']['open_remaining_net_mtm']))
 candidate=ledgers['long_top20'];diff={};gates={}
 for role in ['short_only','original']:
  old=ledgers[role];diff[role]={k:candidate['metrics'][k]-old['metrics'][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']};gates[role]={k:bool(candidate['metrics'][k]>=old['metrics'][k]) for k in ['end_equity','max_dd_pct','sharpe']}
 doc=dict(schema='stage007_prior_long_top20_breakout_three_arm_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='DERIVED_PENDING_INDEPENDENT_REVIEW',review_status='PENDING_INDEPENDENT_REVIEW',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,market_downloads=0,contract=dict(start='2015-01-01',actual_start='2015-01-05',end='2026-10-29',capital=CAPITAL,trading_days=len(candidate['daily']),data_identity=candidate['preflight']['data_identity'],same_settings=True,same_effective=True,MA_slope_gates_enabled=False,short_history_includes_signal_day=True,long_history_includes_signal_day=False,long_history_scope='all_available_same_physical_epoch_daily_strictly_before_signal',long_block='prior_L+0.8*(prior_H-prior_L) <= P <= prior_H',long_exempt='P > prior_H exempts only this price gate'),frozen_accounting_loader_adapter=candidate['loader_adapter'],new_long_acceptance=candidate['acceptances']['long_price_range_acceptance.json'],unchanged_short_acceptance=candidate['acceptances']['short_price_range_acceptance.json'],curve_definition=dict(nav='account_equity / 150000',drawdown_pct='100*(account_equity/cummax([150000]+account_equity)-1)',includes_terminal_open_mtm=True),difference_vs=diff,fixed_candidate_gates_vs=gates,strategy_verdict_vs_short_only='PASS_FIXED_WINDOW_ONLY' if all(gates['short_only'].values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING',source_files_sha256=sources,limits=['Three accounts independently start 2015 with CNY150000 and zero positions; no 2020 splice.','Cached same-epoch data is not a claim of complete listing history; prior long range excludes signal day, short rule includes it.','A strict close-above-prior-high exemption does not bypass existing signal, sizing, margin or safety requirements.','Zero commission, static exchange margin x1.65, inherited PIT/lifecycle/data gaps and no quote/capacity evidence.','Whole-account differences include dynamic capital/integer-lot/risk feedback, not direct filter alpha.'])
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.stage007_report_',dir=out.parent) as tmp:
  t=Path(tmp);tables=t/'tables';tables.mkdir();pic=t/'nav.png';curves=[]
  pd.DataFrame(rows).to_csv(tables/'summary.csv',index=False);pd.DataFrame([r for x in ledgers.values() for r in base.legacy.annual_rows(x)]).to_csv(tables/'annual.csv',index=False)
  for role,x in ledgers.items():
   d=x['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].copy();d['nav'],d['drawdown_pct']=nav_drawdown(d.account_equity);d.to_csv(tables/f'{role}_daily.csv',index=False);curves.append(d[['date','account_equity','nav','drawdown_pct']].assign(role=role));x['rounds'].to_csv(tables/f'{role}_complete_rounds.csv',index=False);x['opened'].to_csv(tables/f'{role}_terminal_open_rounds.csv',index=False)
  pd.concat(curves,ignore_index=True).to_csv(tables/'nav_drawdown.csv',index=False);plot(ledgers,pic);doc['output_files_sha256']={str(out/p.name):sha(p) for p in tables.glob('*.csv')}|{str(figure):sha(pic)};(tables/'comparison.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n');(tables/'delivery_manifest.json').write_text(json.dumps(dict(schema='stage007_report_delivery_v1',review_status='PENDING_INDEPENDENT_REVIEW',financial_replays=0,files_sha256=doc['output_files_sha256']|{str(out/'comparison.json'):sha(tables/'comparison.json')},self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n');verify_sources(sources)
  for x in ledgers.values():
   if base.legacy.snapshot_dir(x['path'])!=x['attempt_snapshot']:raise ValueError('frozen_attempt_changed')
  require_output(out,figure);os.link(pic,figure)
  try:os.rename(tables,out)
  except Exception:figure.unlink();raise
 print(json.dumps(dict(status=doc['status'],gates=gates,difference=diff,rows=rows),ensure_ascii=False));return doc

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--figure',type=Path,default=FIGURE);x=ap.parse_args();build(x.out,x.figure)
if __name__=='__main__':main()
