"""Frozen original vs price-range gate accounting; no financial engine/network.

AST adapter retains the frozen pure accounting loader and replaces only its
research-specific slope-gate identity check; original files/flags stay untouched.
"""
from __future__ import annotations
import argparse,ast,copy,hashlib,json,os,tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage001_report as legacy
LINE=Path(__file__).resolve().parents[1];OUT=LINE/'artifacts/stage005_comparison';FIGURE=LINE/'artifacts/stage005_nav_drawdown.png';CAPITAL=150000.
PATHS={'original':LINE/'outputs/stage001_A_attempt003','price_range':LINE/'outputs/stage005_C_attempt001'}
sha=legacy.sha;verify_sources=legacy.verify_sources

def validate_gate(pre,slope,price):
 if pre.get('short_ma_slope_gate_enabled') is not False or pre.get('long_ma_slope_gate_enabled',False) is not False or slope.get('enabled') is not False:raise ValueError('all_MA_slope_gates_must_be_really_disabled')
 if pre.get('arm')!='C' or pre.get('short_price_range_gate_enabled') is not True or pre.get('short_price_range_threshold')!=.2 or pre.get('short_price_range_history')!='all_available_same_physical_epoch_daily_through_signal' or price.get('accepted') is not True or price.get('enabled') is not True:raise ValueError('actual_full_cached_epoch_bottom20_gate_required')

 expected=dict(threshold_fraction=.2,comparison='signal_close_lte_low_plus_fraction_times_range',history_scope='all_available_same_physical_epoch_daily_through_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=True,rollover_gate_applied=False,flat_range_policy='reject',listing_start_completeness_proven=False)
 if any(price.get(k)!=v for k,v in expected.items()):raise ValueError('price_range_acceptance_contract_mismatch')

def price_loader_ast():
 p=Path(legacy.__file__).resolve();before=sha(p);source=ast.parse(p.read_text());node=copy.deepcopy(next(x for x in source.body if isinstance(x,ast.FunctionDef) and x.name=='load_ledger'));count=0
 for index,item in enumerate(node.body):
  if isinstance(item,ast.If) and any(isinstance(v,ast.Constant) and v.value=='slope_arm_flag_mismatch' for v in ast.walk(item)):
   node.body[index:index+1]=ast.parse("price_gate=read('short_price_range_acceptance.json')\n_stage005_validate_gate(pre,gate,price_gate)").body;count+=1;break
 if count!=1:raise ValueError('exactly_one_frozen_gate_identity_check_required')
 node.name='_stage005_pure_accounting_loader'
 labels=[n.args[0].value for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ValueError' and n.args and isinstance(n.args[0],ast.Constant)]
 literals=[n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
 receipt=dict(schema='stage005_one_gate_AST_accounting_adapter_v1',source=str(p),source_sha256=before,replaced_gate_checks=count,arm_check_changed=False,original_source_unchanged=sha(p)==before,retained_raise_labels=labels,retained_string_literals=literals,adapted_function_ast_sha256=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),accounting_body_preserved_except_declared_gate_identity=True)
 return ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])),receipt

def load_price_ledger(path):
 tree,receipt=price_loader_ast();env=dict(vars(legacy));env['_stage005_validate_gate']=validate_gate;exec(compile(tree,str(Path(__file__))+'::frozen_accounting_gate_adapter','exec'),env);x=env['_stage005_pure_accounting_loader'](path,'candidate')
 for side in ['short','long']:
  proof=x['acceptances'].get(side+'_ma_slope_acceptance.json',{})
  if proof.get('enabled') is not False or proof.get('decision_count')!=0 or proof.get('applied_block_count')!=0 or proof.get('MA_periods')!=[] or proof.get('rule')!='disabled_no_slope_wrapper':raise ValueError('actual_zero_MA_slope_diagnostics_required')
 x['loader_adapter']=receipt;return x

def same_contract(a,c):
 if a['preflight'].get('start')!='2020-01-01' or a['preflight'].get('end')!='2026-10-29' or c['preflight'].get('start')!=a['preflight']['start'] or c['preflight'].get('end')!=a['preflight']['end']:raise ValueError('fixed_2020_20261029_window_required')
 if not a['daily'].date.equals(c['daily'].date) or a['daily'].date.iloc[0]!=pd.Timestamp('2020-01-02') or a['daily'].date.iloc[-1]!=pd.Timestamp('2026-10-29'):raise ValueError('same_full_calendar_required')
 if a['preflight']['data_identity']!=c['preflight']['data_identity'] or any(a[k]!=c[k] for k in ['settings','effective','database_sha256']):raise ValueError('same_data_settings_and_effective_required')
 return True

def nav_drawdown(equity):
 e=np.asarray(equity,dtype=float)
 if not len(e) or not np.isfinite(e).all():raise ValueError('finite_equity_required')
 return e/CAPITAL,100*(e/np.maximum.accumulate(np.r_[CAPITAL,e])[1:]-1)

def require_output(out,figure):
 if Path(out).resolve()!=OUT.resolve() or Path(figure).resolve()!=FIGURE.resolve():raise ValueError('assigned_stage005_outputs_only')
 if OUT.exists() or FIGURE.exists():raise ValueError('immutable_report_exists')

def plot(ledgers,path,reviewed=False):
 os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,(a,b)=plt.subplots(2,1,figsize=(12.7,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for role,color,lw,label in [('original','#667d99',1.3,'Original: no MA slope / no price-range gate'),('price_range','#b4234a',2.,'Stage005: no MA slope; short bottom-20% gate')]:
  d=ledgers[role]['daily'];nav,dd=nav_drawdown(d.account_equity);a.plot(d.date,nav,color=color,lw=lw,label=label+f' | end NAV {nav[-1]:.3f}');b.plot(d.date,dd,color=color,lw=lw)
 a.axhline(1.,color='#9ca3af',lw=.7,ls='--');a.legend(frameon=False,fontsize=9,loc='upper left');a.set_ylabel('NAV = equity / CNY150,000');b.set_ylabel('Drawdown (%)');b.set_xlabel('Exchange trading date')
 for ax in [a,b]:ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
 state='INDEPENDENT REVIEW PASSED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING';fig.suptitle('STAGE005 / '+state+' / OFFLINE RESEARCH / NO PROMOTION\n2020-01-02 to 2026-10-29 | original19 | CNY150,000 each | no addon\nAll cached same-physical-epoch daily high/low through signal; daily next-open; zero commission',fontsize=10.5,fontweight='bold')
 fig.text(.1,.025,'Signal close <= min low + 20% * (max high - min low) rejects new short; all MA slope gates OFF.\nCache history is not a claim of complete listing history. Includes open MTM; static margin x1.65; no quote/capacity proof.',fontsize=8,color='#667085');fig.tight_layout(rect=[0,.065,1,.89]);fig.savefig(path,dpi=170);plt.close(fig)

def build(out=OUT,figure=FIGURE):
 require_output(out,figure);print('Auditing frozen original ledger',flush=True);a=legacy.load_ledger(PATHS['original'],'baseline');print('Auditing frozen price-range ledger through narrow gate adapter',flush=True);c=load_price_ledger(PATHS['price_range']);same_contract(a,c);ledgers={'original':a,'price_range':c}
 sources={str(p.resolve()):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage005_report.py'),Path(legacy.__file__)]}
 for role,x in ledgers.items():
  x['role']=role
  for p,d in x['sources'].items():
   if p in sources and sources[p]!=d:raise ValueError('conflicting_source_hash')
   sources[p]=d
 verify_sources(sources);rows=[]
 for role,x in ledgers.items():
  rows.append(dict(role=role,**x['metrics'],nav_end=x['metrics']['end_equity']/CAPITAL,**{'fifo_'+k:v for k,v in x['accounting']['closed_fifo'].items()},**{'round_'+k:v for k,v in x['accounting']['complete_contract_rounds'].items()},**x['risk'],open_round_count=x['accounting']['open_round_count'],open_round_net_mtm=x['accounting']['open_round_net_mtm'],open_remaining_net_mtm=x['accounting']['open_remaining_net_mtm']))
 gates={k:bool(c['metrics'][k]>=a['metrics'][k]) for k in ['end_equity','max_dd_pct','sharpe']};diff={k:c['metrics'][k]-a['metrics'][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']}
 doc=dict(schema='stage005_same_source_full_cached_epoch_price_range_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='DERIVED_PENDING_INDEPENDENT_REVIEW',review_status='PENDING_INDEPENDENT_REVIEW',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,market_downloads=0,contract=dict(requested_start='2020-01-01',actual_start='2020-01-02',end='2026-10-29',capital=CAPITAL,trading_days=len(c['daily']),data_identity=a['preflight']['data_identity'],same_settings=True,same_effective=True,all_MA_slope_gates_enabled=False,short_price_range_threshold=.2,short_price_range_history='all_available_same_physical_epoch_daily_through_signal',signal_price='same signal day exact contract close',range_price='cumulative maximum daily high and minimum daily low',inclusion='source date <= signal date; same physical epoch only'),loader_adapter=c['loader_adapter'],curve_definition=dict(nav='account_equity / 150000',drawdown_pct='100 * (account_equity / cummax([150000]+account_equity) - 1)',includes_terminal_open_mtm=True),fixed_candidate_gates=gates,difference_vs_original=diff,strategy_verdict='PASS_FIXED_WINDOW_ONLY' if all(gates.values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING',source_files_sha256=sources,short_price_range_gate=c['acceptances']['short_price_range_acceptance.json'],limits=['All available cached exact-epoch daily history is not a claim of complete listing history.','Signal uses daily close; range uses daily high/low through the same completed signal date, not accepted-week-only or continuous-contract history.','Zero commission, static exchange margin x1.65, inherited PIT/lifecycle/data gaps and no quote/capacity evidence.','Whole-account path differences include capital sizing, integer lots, margin/risk and later opportunity feedback; not direct filter alpha.','Historical development sample is repeatedly reused; no OOS or production promotion claim.'])
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.stage005_report_',dir=out.parent) as tmp:
  t=Path(tmp);tables=t/'tables';tables.mkdir();pic=t/'nav.png';curves=[]
  pd.DataFrame(rows).to_csv(tables/'summary.csv',index=False);pd.DataFrame([r for x in ledgers.values() for r in legacy.annual_rows(x)]).to_csv(tables/'annual.csv',index=False)
  for role,x in ledgers.items():
   daily=x['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].copy();daily['nav'],daily['drawdown_pct']=nav_drawdown(daily.account_equity);daily.to_csv(tables/f'{role}_daily.csv',index=False);curves.append(daily[['date','account_equity','nav','drawdown_pct']].assign(role=role));x['rounds'].to_csv(tables/f'{role}_complete_rounds.csv',index=False);x['opened'].to_csv(tables/f'{role}_terminal_open_rounds.csv',index=False)
  pd.concat(curves,ignore_index=True).to_csv(tables/'nav_drawdown.csv',index=False);plot(ledgers,pic);doc['output_files_sha256']={str(out/p.name):sha(p) for p in tables.glob('*.csv')}|{str(figure):sha(pic)};(tables/'comparison.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n');(tables/'delivery_manifest.json').write_text(json.dumps(dict(schema='stage005_report_delivery_v1',review_status='PENDING_INDEPENDENT_REVIEW',financial_replays=0,files_sha256=doc['output_files_sha256']|{str(out/'comparison.json'):sha(tables/'comparison.json')},self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n');verify_sources(sources)
  for x in ledgers.values():
   if legacy.snapshot_dir(x['path'])!=x['attempt_snapshot']:raise ValueError('frozen_attempt_changed')
  require_output(out,figure);os.link(pic,figure)
  try:os.rename(tables,out)
  except Exception:figure.unlink();raise
 print(json.dumps(dict(status=doc['status'],gates=gates,difference=diff,rows=rows),ensure_ascii=False));return doc

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=OUT);ap.add_argument('--figure',type=Path,default=FIGURE);x=ap.parse_args();build(x.out,x.figure)
if __name__=='__main__':main()
