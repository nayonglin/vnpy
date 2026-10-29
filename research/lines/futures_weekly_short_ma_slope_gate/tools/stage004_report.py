"""Four frozen full-engine ledgers: common-capital NAV/DD, no strategy replay."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,tempfile
import numpy as np
import pandas as pd
from stage001_report import load_ledger,verify_sources,sha,annual_rows,snapshot_dir
LINE=Path(__file__).resolve().parents[1];OUT=LINE/'artifacts/stage004_comparison';FIGURE=LINE/'artifacts/stage004_nav_drawdown.png';CAPITAL=150000.
PATHS={'original':LINE/'outputs/stage001_A_attempt003','short_only':LINE/'outputs/stage001_C_attempt003','symmetric':LINE/'outputs/stage002_C_attempt001','long_ma5':LINE/'outputs/stage004_C_attempt001'}
LABELS={'original':'Original: no slope gates','short_only':'Stage001: short MA5/10 gate only','symmetric':'Stage002: long MA5/10 + short MA5/10','long_ma5':'NEW Stage004: long MA5 only + short MA5/10'}

def nav_drawdown(equity):
 e=np.asarray(equity,dtype=float)
 if not len(e) or not np.isfinite(e).all() or (e<=0).any():raise ValueError('finite_positive_nonempty_equity_required')
 return e/CAPITAL,(e/np.maximum.accumulate(np.r_[CAPITAL,e])[1:]-1.)*100.

def require_same_contract(ledgers):
 if set(ledgers)!=set(PATHS):raise ValueError('four_assigned_roles_required')
 base=ledgers['original']
 for role,x in ledgers.items():
  pre=x['preflight'];dates=x['daily'].date
  if pre.get('start')!='2020-01-01' or pre.get('end')!='2026-10-29' or dates.iloc[0]!=pd.Timestamp('2020-01-02') or dates.iloc[-1]!=pd.Timestamp('2026-10-29') or not dates.equals(base['daily'].date):raise ValueError('same_full2020_to20261029_calendar_required')
  if pre.get('daily_addon_enabled') is not False:raise ValueError('no_addon_required')
  if any(x[k]!=base[k] for k in ['settings','effective','database_sha256']) or pre['data_identity']!=base['preflight']['data_identity']:raise ValueError('same_data_settings_effective_required')
  expected_short=role!='original';expected_long=role in {'symmetric','long_ma5'}
  if pre.get('short_ma_slope_gate_enabled') is not expected_short or pre.get('long_ma_slope_gate_enabled',False) is not expected_long:raise ValueError('gate_role_mismatch:'+role)
 pre=ledgers['long_ma5']['preflight'];proof=ledgers['long_ma5']['acceptances'].get('long_ma_slope_acceptance.json',{})
 if pre.get('long_ma_slope_periods')!=[5] or proof.get('MA_periods')!=[5] or proof.get('operator')!='SINGLE' or proof.get('rule')!='completed_week_MA5_current_lt_previous' or proof.get('accepted') is not True or proof.get('enabled') is not True:raise ValueError('actual_long_MA5_only_contract_required')
 return True

def require_output(out,figure):
 if Path(out).resolve()!=OUT.resolve() or Path(figure).resolve()!=FIGURE.resolve():raise ValueError('assigned_stage004_outputs_only')
 if OUT.exists() or FIGURE.exists():raise ValueError('immutable_report_or_figure_exists')

def plot(ledgers,path,reviewed=False):
 os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.ticker import FuncFormatter
 fig,(top,bottom)=plt.subplots(2,1,figsize=(13.3,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for role,color,style,lw,alpha in [('original','#8b939c','--',1.1,.8),('short_only','#2467a6','-',1.3,.85),('symmetric','#c08128',':',1.6,.95),('long_ma5','#b4234a','-',2.2,1.)]:
  d=ledgers[role]['daily'];nav,dd=nav_drawdown(d.account_equity);top.plot(d.date,nav,color=color,ls=style,lw=lw,alpha=alpha,label=LABELS[role]+f' | end NAV {nav[-1]:.3f}');bottom.plot(d.date,dd,color=color,ls=style,lw=max(.9,lw-.3),alpha=alpha)
 top.axhline(1.,color='#697586',lw=.7,ls='--');top.legend(frameon=False,fontsize=9,loc='upper left');top.set_ylabel('NAV = modeled equity / CNY150,000');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:.1f}x'));bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
 for ax in [top,bottom]:ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
 status='INDEPENDENT REVIEW PASSED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'
 fig.suptitle('STAGE004 / '+status+' / OFFLINE RESEARCH / NO PROMOTION\n2020-01-02 to 2026-10-29 | original19 | CNY150,000 each | dynamic base, no addon\nCompleted weekly MA; daily next-open; zero commission; static exchange margin x1.65',fontsize=10.5,fontweight='bold')
 fig.text(.11,.025,'Same frozen daily source and full-engine ledgers. NAV is equity / initial capital; not profit or annualized return.\nIncludes terminal open-position MTM. Historical PIT, cost, margin and execution-capacity limitations remain.',fontsize=8,color='#667085')
 fig.tight_layout(rect=[0,.06,1,.89]);fig.savefig(path,dpi=170);plt.close(fig)

def build(out=OUT,figure=FIGURE):
 require_output(out,figure)
 ledgers={}
 for role,path in PATHS.items():
  print('Auditing frozen ledger: '+role,flush=True);ledgers[role]=load_ledger(path,'baseline' if role=='original' else 'candidate');ledgers[role]['role']=role
 require_same_contract(ledgers)
 sources={str(Path(__file__).resolve()):sha(__file__),str(Path(__file__).with_name('test_stage004_report.py')):sha(Path(__file__).with_name('test_stage004_report.py')),str(Path(__file__).with_name('stage001_report.py')):sha(Path(__file__).with_name('stage001_report.py'))}
 for x in ledgers.values():
  for p,d in x['sources'].items():
   if p in sources and sources[p]!=d:raise ValueError('conflicting_source_hash')
   sources[p]=d
 verify_sources(sources)
 rows=[]
 for role,x in ledgers.items():
  m=x['metrics'];rows.append(dict(role=role,version_label=LABELS[role],**m,nav_end=m['end_equity']/CAPITAL,**{'fifo_'+k:v for k,v in x['accounting']['closed_fifo'].items()},**{'round_'+k:v for k,v in x['accounting']['complete_contract_rounds'].items()},**x['risk'],open_round_net_mtm=x['accounting']['open_round_net_mtm'],open_remaining_net_mtm=x['accounting']['open_remaining_net_mtm'],open_round_count=x['accounting']['open_round_count']))
 candidate=ledgers['long_ma5'];comparisons={};gates={}
 for role in ['original','short_only','symmetric']:
  old=ledgers[role];comparisons[role]={k:candidate['metrics'][k]-old['metrics'][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']};gates[role]={k:bool(candidate['metrics'][k]>=old['metrics'][k]) for k in ['end_equity','max_dd_pct','sharpe']}
 doc=dict(schema='stage004_four_arm_longMA5_only_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),review_status='PENDING_INDEPENDENT_REVIEW',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,market_downloads=0,source_files_sha256=sources,contract=dict(capital=CAPITAL,requested_start='2020-01-01',actual_start='2020-01-02',end='2026-10-29',trading_days=len(candidate['daily']),data_identity=candidate['preflight']['data_identity'],same_actual_settings=True,same_effective_parameters=True,MA5_only_long_rule='completed_week_MA5_current_lt_previous',short_rule='MA5_delta_gt0_OR_MA10_delta_gt0',other_rules_frozen=True),curve_definition=dict(nav='account_equity / 150000',drawdown_pct='100 * (account_equity / cummax([150000]+account_equity) - 1)',initial_capital=CAPITAL,includes_terminal_open_mtm=True),difference_vs=comparisons,fixed_candidate_gates_vs=gates,strategy_verdict_vs_symmetric='PASS_FIXED_WINDOW_ONLY' if all(gates['symmetric'].values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING',limits=['Zero commission; fixed slippage; static exchange margin x1.65 is not historical actual broker margin.','Repeated historical development sample; no new PIT/OOS or quote/depth/capacity evidence.','NAV contains actual terminal open-position MTM; not all profit is realized.','Whole-account path difference includes capital/rounding/entry/risk feedback; not direct filter alpha.'])
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.stage004_report_',dir=out.parent) as tmp:
  temp=Path(tmp);tables=temp/'tables';tables.mkdir();pic=temp/'nav_drawdown.png'
  pd.DataFrame(rows).to_csv(tables/'summary.csv',index=False);pd.DataFrame([r for x in ledgers.values() for r in annual_rows(x)]).to_csv(tables/'annual.csv',index=False)
  curves=[]
  for role,x in ledgers.items():
   d=x['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].copy();d['nav'],d['drawdown_pct']=nav_drawdown(d.account_equity);d.to_csv(tables/f'{role}_daily.csv',index=False);curves.append(d[['date','account_equity','nav','drawdown_pct']].assign(role=role))
   x['rounds'].to_csv(tables/f'{role}_complete_rounds.csv',index=False);x['opened'].to_csv(tables/f'{role}_terminal_open_rounds.csv',index=False)
  pd.concat(curves,ignore_index=True).to_csv(tables/'nav_drawdown.csv',index=False)
  plot(ledgers,pic);doc['output_files_sha256']={str(out/p.name):sha(p) for p in tables.glob('*.csv')}|{str(figure):sha(pic)}
  (tables/'comparison.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
  manifest=dict(schema='stage004_report_delivery_v1',review_status='PENDING_INDEPENDENT_REVIEW',financial_replays=0,files_sha256=doc['output_files_sha256']|{str(out/'comparison.json'):sha(tables/'comparison.json')},self_hash_excluded=True)
  (tables/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n');verify_sources(sources)
  for x in ledgers.values():
   if snapshot_dir(x['path'])!=x['attempt_snapshot']:raise ValueError('source ledger changed during report')
  require_output(out,figure);os.link(pic,figure)
  try:os.rename(tables,out)
  except Exception:figure.unlink();raise
 print(json.dumps(dict(status='DERIVED_PENDING_INDEPENDENT_REVIEW',difference_vs=comparisons,fixed_gates=gates,rows=rows),ensure_ascii=False))
 return doc

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--figure',type=Path,default=FIGURE);a=ap.parse_args();build(a.out,a.figure)
if __name__=='__main__':main()
