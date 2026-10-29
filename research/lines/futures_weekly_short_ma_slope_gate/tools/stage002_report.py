"""Three frozen full-engine ledgers; no strategy replay and no synthetic overlay."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,os
import numpy as np
import pandas as pd
from stage001_report import load_ledger,verify_sources,sha,annual_rows
LINE=Path(__file__).resolve().parents[1]
def main():
 out=LINE/'artifacts/stage002_comparison'
 if out.exists():raise ValueError('immutable_report_exists')
 paths={'original':LINE/'outputs/stage001_A_attempt003','short_only':LINE/'outputs/stage001_C_attempt003','symmetric':LINE/'outputs/stage002_C_attempt001'}
 ledgers={role:load_ledger(p,'baseline' if role=='original' else 'candidate') for role,p in paths.items()}
 base=ledgers['short_only'];candidate=ledgers['symmetric'];pre=candidate['preflight']
 if pre.get('long_ma_slope_gate_enabled') is not True or candidate['acceptances']['long_ma_slope_acceptance.json'].get('enabled') is not True:raise ValueError('actual_long_gate_not_enabled')
 sources={str(Path(__file__).resolve()):sha(__file__)}
 for role,x in ledgers.items():
  if x['preflight']['data_identity']!=base['preflight']['data_identity'] or x['settings']!=base['settings'] or x['effective']!=base['effective'] or not x['daily'].date.equals(base['daily'].date):raise ValueError('non_same_contract_comparison')
  if role!='symmetric' and x['preflight'].get('long_ma_slope_gate_enabled',False):raise ValueError('frozen_control_long_gate_unexpected')
  for p,d in x['sources'].items():
   if p in sources and sources[p]!=d:raise ValueError('conflicting_hash')
   sources[p]=d
  x['role']=role
 gates={k:bool(candidate['metrics'][k]>=base['metrics'][k]) for k in ['end_equity','max_dd_pct','sharpe']}
 rows=[dict(role=role,**x['metrics'],**{'round_'+k:v for k,v in x['accounting']['complete_contract_rounds'].items()},**x['risk'],open_round_net_mtm=x['accounting']['open_round_net_mtm']) for role,x in ledgers.items()]
 verify_sources(sources);out.mkdir(parents=True)
 pd.DataFrame(rows).to_csv(out/'summary.csv',index=False)
 pd.DataFrame([r for x in ledgers.values() for r in annual_rows(x)]).to_csv(out/'annual.csv',index=False)
 for role,x in ledgers.items():
  x['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].to_csv(out/f'{role}_daily.csv',index=False)
  x['rounds'].to_csv(out/f'{role}_complete_rounds.csv',index=False)
 os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.ticker import FuncFormatter
 fig,(top,bottom)=plt.subplots(2,1,figsize=(12,7.2),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 for role,color,label in [('original','#7d8995','Original: no slope gates'),('short_only','#2467a6','Stage001: short gate only'),('symmetric','#c36f19','Stage002: long + short gates')]:
  d=ledgers[role]['daily'];e=d.account_equity.to_numpy();p=np.maximum.accumulate(np.r_[150000,e])[1:];top.plot(d.date,e,color=color,lw=1.2,label=label);bottom.plot(d.date,(e/p-1)*100,color=color,lw=1)
 top.legend(frameon=False);top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'));bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
 for ax in [top,bottom]:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
 fig.suptitle('STAGE002 / REVIEW PENDING / OFFLINE RESEARCH / NO PROMOTION\n2020-01-02 to 2026-10-29; original19; CNY150,000 each; no addon\nCompleted weekly MA5/10; daily next-open; zero commission; static margin x1.65',fontsize=10.5,fontweight='bold');fig.tight_layout(rect=[0,0,1,.89]);pic=LINE/'artifacts/stage002_equity_drawdown.png';fig.savefig(pic,dpi=160);plt.close(fig)
 doc=dict(schema='stage002_symmetric_ma_slope_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),review_status='PENDING_INDEPENDENT_REVIEW',promotion_decision='NO_PROMOTION',production_qualified=False,fixed_candidate_gates_vs_short_only=gates,strategy_verdict='PASS_FIXED_WINDOW_ONLY' if all(gates.values()) else 'MIXED_OR_FAIL_NO_RESCUE_TUNING',difference_vs_short_only={k:candidate['metrics'][k]-base['metrics'][k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe']},source_files_sha256=sources,output_files_sha256={str(p):sha(p) for p in out.glob('*.csv')}|{str(pic):sha(pic)},financial_replays=0)
 (out/'comparison.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'DERIVED_PENDING_INDEPENDENT_REVIEW','gates':gates,'difference':doc['difference_vs_short_only']}))
if __name__=='__main__':main()
