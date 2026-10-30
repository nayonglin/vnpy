"""Compare new2015 A through10/28 to immutable prior Stage033 A; no replay."""
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';OLD=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage033_A_attempt001');NEW=L/'outputs/stage006_A_attempt001'
known={'daily.csv':'7587f3736d4d495365333a81b8b717208c1001786a936af7321d5663e17b756b','trades.csv':'75a9547c5457111964ece4e29df59eb7aff0bf06a1ef2b17400491502e18c1ab','execution_clock.csv':'cebb06851006057f488938a8480593707026ead4f32eec49a586a4a34480f0c9','preflight.json':'88e08b5c2cf9ea71714f15993356f50c4abed1f862c4218805caa0351183acb0'}
for n,h in known.items():assert hashlib.sha256((OLD/n).read_bytes()).hexdigest()==h,(n,'old identity changed')
results={}
for n in ['daily','trades','execution_clock','entry_candidates','weekly_bars','execution_anchor_requests','internal_equity_daily','weekly_readiness']:
 a=pd.read_csv(OLD/(n+'.csv'),low_memory=False);b=pd.read_csv(NEW/(n+'.csv'),low_memory=False);col=next((c for c in ['trading_date','date','week_end'] if c in a),None)
 if col:b=b.loc[b[col].astype(str).str[:10].le('2026-10-28')]
 cols=[c for c in a if c not in ['result_scope','profile']];pd.testing.assert_frame_equal(a[cols].reset_index(drop=True),b[cols].reset_index(drop=True),check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-8);results[n]=dict(equal=True,rows=len(a),columns=len(cols))
cols=['date','vt_symbol','start_pos','end_pos','pre_close','close_price','net_pnl','slippage','commission','trade_count']
def active_positions(p):
 out=[]
 for f in pd.read_csv(p/'positions.csv',usecols=cols,chunksize=100000):
  keep=f.date.astype(str).str[:10].le('2026-10-28')&f[['start_pos','end_pos','net_pnl','slippage','commission','trade_count']].abs().sum(axis=1).ne(0);out.append(f.loc[keep])
 return pd.concat(out).reset_index(drop=True)
a,b=active_positions(OLD),active_positions(NEW);pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=False,rtol=1e-12,atol=1e-8);results['financial_positions']=dict(equal=True,rows=len(a),columns=len(cols))
r=dict(status='PASS_2015_BASELINE_EXACT_THROUGH_PRIOR_CUTOFF',old_run=str(OLD),new_run=str(NEW),old_source_bound_sha256=known,cutoff='2026-10-28',checks=results,financial_replays=0,scope='Same2015 independent start, excluding only scope/profile tags; not a2020 curve truncation.')
(L/'stages/stage006_independent_identity.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
