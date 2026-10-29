from pathlib import Path
import pandas as pd,json,hashlib
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';OLD=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage032_A_attempt002');NEW=L/'outputs/stage001_A_attempt003'
results={}
for n in ['daily','trades','execution_clock','entry_candidates','weekly_bars','execution_anchor_requests','internal_equity_daily']:
 old=pd.read_csv(OLD/(n+'.csv'),low_memory=False);new=pd.read_csv(NEW/(n+'.csv'),low_memory=False)
 col=next((c for c in ['trading_date','date','week_end'] if c in old),None)
 if col:new=new.loc[new[col].astype(str).str[:10].le('2026-10-28')]
 cols=[c for c in old if c not in ['result_scope','profile']]
 pd.testing.assert_frame_equal(old[cols].reset_index(drop=True),new[cols].reset_index(drop=True),check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-8)
 results[n]=dict(equal=True,rows=len(old),columns=len(cols))
# Read only financial position rows; all inactive/zero rows are still covered by whole-run audit.
cols=['date','vt_symbol','start_pos','end_pos','pre_close','close_price','net_pnl','slippage','commission','trade_count']
def positions(p):
 rows=[]
 for f in pd.read_csv(p/'positions.csv',usecols=cols,chunksize=100000):
  keep=f.date.astype(str).str[:10].le('2026-10-28')&f[['start_pos','end_pos','net_pnl','slippage','commission','trade_count']].abs().sum(axis=1).ne(0);rows.append(f.loc[keep])
 return pd.concat(rows).reset_index(drop=True)
a,b=positions(OLD),positions(NEW);pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-8);results['active_positions']=dict(equal=True,rows=len(a),columns=len(cols))
# Retry003 only corrected environment acceptance; strategy-generated primary ledgers unchanged from rejected002.
for arm in ['A','C']:
 old=L/'outputs'/f'stage001_{arm}_attempt002';new=L/'outputs'/f'stage001_{arm}_attempt003'
 if not (new/'terminal.json').exists():continue
 result={'limitation':'Rejected002 stopped before exporting daily/trades; only preserved diagnostics can be compared.'}
 for n in ['weekly_stop_audit','initial_stop_audit','weekly_stop_guard_failures','invalid_weekly_stop_rejections','short_ma_slope_decisions']:
  suffix='.json' if n=='short_ma_slope_decisions' else '.csv';a=old/(n+suffix);b=new/(n+suffix)
  ha=hashlib.sha256(a.read_bytes()).hexdigest();hb=hashlib.sha256(b.read_bytes()).hexdigest();assert ha==hb,(arm,n);result[n]=dict(equal=True,sha256=ha)
 results['retry002_003_'+arm]=result
out=dict(status='PASS_BASELINE_IDENTITY_AND_MECHANICAL_RETRY',checks=results,financial_replays=0,limitations='2020 independent baseline compared through original 10/28 cutoff; no claim truncated 2015 curve equals independent2020 start.')
(L/'stages/stage001_independent_baseline_identity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
