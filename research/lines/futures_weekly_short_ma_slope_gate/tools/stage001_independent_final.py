from pathlib import Path
import json,hashlib,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
checks={}
def check(k,v):
 checks[k]=bool(v)
 if not v:raise AssertionError(k)
reports={};opens={};settings={};effective={};pre={}
for arm in ['A','C']:
 p=L/'outputs'/f'stage001_{arm}_attempt003';reports[arm]=json.loads((L/f'stages/stage001_independent_{arm}_results.json').read_text());settings[arm]=json.loads((p/'actual_strategy_settings.json').read_text());effective[arm]=json.loads((p/'effective_parameters.json').read_text());pre[arm]=json.loads((p/'preflight.json').read_text());dec=json.loads((p/'short_ma_slope_decisions.json').read_text());f=pd.read_csv(p/'trades.csv');anchors=pd.read_csv(p/'execution_anchor_requests.csv');can=pd.read_csv(p/'entry_candidates.csv');roll=pd.read_csv(p/'rollover_shape_same_volume.csv');counts={'new_short':0,'roll_short':0}
 for t in f.loc[f.direction.eq('空')&f.offset.eq('开')].itertuples():
  a=anchors.loc[anchors.order_id.astype(str).eq(str(t.order_id))];check(arm+'_unique_anchor_'+str(t.trade_id),len(a)==1);day=str(a.iloc[0].signal_date)[:10];native=can.loc[can.date.astype(str).str[:10].eq(day)&can.contract_vt_symbol.eq(t.vt_symbol)&can.direction.eq('short')&can.candidate_status.eq('opened')];rr=roll.loc[roll.date.astype(str).str[:10].eq(day)&roll.target_contract_vt_symbol.eq(t.vt_symbol)&roll.direction.eq('short')&roll.status.eq('targeted')&roll.final_volume.gt(0)]
  check(arm+'_unique_open_context_'+str(t.trade_id),(len(native)>0) != (len(rr)>0))
  if len(native):
   counts['new_short']+=1;ds=[r for r in dec if r['signal_date']==day and r['vt_symbol']==t.vt_symbol];check(arm+'_native_open_decision_'+str(t.trade_id),bool(ds) and not any(r['applied_block'] for r in ds))
   if arm=='C':check('C_native_open_nonpositive_'+str(t.trade_id),not any(r['would_block'] for r in ds))
  else:counts['roll_short']+=1
 opens[arm]=counts
 # Independently derive every required held/traded contract-day from fills,
 # so an absent carry row cannot silently disappear from the repricing audit.
 daily_dates=pd.read_csv(p/'daily.csv',usecols=['date']).date.astype(str).str[:10].tolist()
 present={}
 for chunk in pd.read_csv(p/'positions.csv',usecols=['date','vt_symbol','start_pos','end_pos','trade_count'],chunksize=100000):
  active=chunk.loc[chunk[['start_pos','end_pos','trade_count']].abs().sum(axis=1).ne(0)]
  for day,g in active.groupby('date'):present.setdefault(str(day)[:10],set()).update(g.vt_symbol)
 groups={day:g for day,g in f.groupby('trading_date')};held={}
 for day in daily_dates:
  g=groups.get(day,f.iloc[:0]);required={sym for sym,q in held.items() if q!=0}|set(g.vt_symbol)
  check(arm+'_held_day_presence_'+day,required<=present.get(day,set()))
  for t in g.itertuples():held[t.vt_symbol]=held.get(t.vt_symbol,0)+(1 if t.direction=='多' else -1)*t.volume
 check(arm+'_no_supply_source',not Path(settings[arm][0]['actual']['supply_demand_signal_path']).exists())
 check(arm+'_supply_flag_preserved',settings[arm][0]['actual']['enable_supply_demand_headwind_filter'] is True)
check('same_full_settings',settings['A']==settings['C']);check('same_full_effective',effective['A']==effective['C']);check('same_data_identity',pre['A']['data_identity']==pre['C']['data_identity'])
report=L/'artifacts/stage001_comparison';comparison=json.loads((report/'comparison.json').read_text());summary=pd.read_csv(report/'summary.csv')
for path,digest in {**comparison['source_files_sha256'],**comparison['output_files_sha256']}.items():check('report_binding:'+path,Path(path).is_file() and sha(path)==digest)
for arm,role in [('A','baseline'),('C','candidate')]:
 row=summary.loc[summary.role.eq(role)].iloc[0];m=reports[arm]['metrics']
 for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','open_round_net_mtm']:check('summary_'+arm+'_'+key,math.isclose(float(row[key]),float(m[key]),rel_tol=1e-10,abs_tol=1e-6))
 for rkey,mkey in [('round_count','count'),('round_wins','wins'),('round_losses','losses'),('round_flat','flat'),('round_win_rate_pct','win_rate_pct'),('round_average_win','average_win'),('round_average_loss_abs','average_loss_abs'),('round_payoff_ratio','payoff_ratio'),('round_profit_factor','profit_factor'),('round_closed_net_pnl','closed_net_pnl')]:check('summary_'+arm+'_'+rkey,math.isclose(float(row[rkey]),float(m['rounds'][mkey]),rel_tol=1e-10,abs_tol=1e-6))
check('mixed_fail_verdict',comparison['fixed_candidate_result']=='MIXED_OR_FAIL_NO_RESCUE_TUNING');check('no_promotion',comparison['promotion_decision']=='NO_PROMOTION')
identity=json.loads((L/'stages/stage001_independent_baseline_identity.json').read_text());check('baseline_identity_pass',identity['status']=='PASS_BASELINE_IDENTITY_AND_MECHANICAL_RETRY')
output=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,checks=checks,final_cross_checks=len(checks),arm_check_counts={a:r['checks'] for a,r in reports.items()},actual_short_open_context_counts=opens,financial_replays=0,production_qualified=False,strategy_verdict='MIXED_OR_FAIL_NO_RESCUE_TUNING',promotion_decision='NO_PROMOTION',limitations=['Independent consistency/repricing of frozen records does not establish exchange data truth or PIT/OOS.','Repeated history, zero commission, static margin, next-daily-open model, no depth/capacity qualification.','Rejected002 does not have exported full ledgers; only saved diagnostics are comparable with003.'])
(L/'stages/stage001_independent_final.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items() if k!='checks'},ensure_ascii=False))
