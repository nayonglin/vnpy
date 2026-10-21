from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
L=Path('/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai');O=L/'outputs/stage133_contract_choice_decision';O.mkdir(exist_ok=False);C=L/'outputs/stage131_contract_choice_cash/actual_run1';F=L/'outputs/stage130_contract_choice_fit/actual_run1'
summ=pd.read_csv(C/'account_summaries.csv.gz');reports=json.loads((C/'diagnostics.json').read_text());rows=[]
for s in summ.to_dict('records'):
 folder=C/s['account'];closed=pd.read_csv(folder/'closed.csv.gz');opened=pd.read_csv(folder/'open.csv.gz');audit=pd.read_csv(folder/'capacity_audit.csv.gz')
 unknown=set(audit.loc[audit.capacity_state.eq('execution_capacity_unknown'),'root_id'])
 episodes=[]
 for r in closed.to_dict('records'):
  episodes.append(dict(root_id=r['root_id'],event_id=r['event_id'],epoch=r['epoch'],closed=True,net_contribution=r['net_pnl'],capacity_unknown=r['root_id'] in unknown,ever_stale=bool(r['ever_stale'])))
 for r in opened.to_dict('records'):
  net=r['realized_gross']-r['entry_fees']-r['exit_fees']+r['unrealized'];episodes.append(dict(root_id=r['root_id'],event_id=r['event_id'],epoch=r['epoch'],closed=False,net_contribution=net,capacity_unknown=r['root_id'] in unknown,ever_stale=bool(r['ever_stale'])))
 total=sum(r['net_contribution'] for r in episodes);expected=s['ending_equity']-1000000
 if not np.isclose(total,expected,rtol=1e-10,atol=1e-6):raise ValueError('episode contribution != equity growth')
 affected=[r for r in episodes if r['capacity_unknown']];stale=[r for r in episodes if r['ever_stale']]
 diag=reports[s['account']];top=sorted(affected,key=lambda r:abs(r['net_contribution']),reverse=True)
 rows.append(dict(account=s['account'],arm=s['arm'],window=s['window'],cost=s['cost'],growth=expected,all_episode_contribution=total,capacity_unknown_roots=len(unknown),capacity_unknown_net_contribution=sum(r['net_contribution']for r in affected),capacity_unknown_closed_net_contribution=sum(r['net_contribution']for r in affected if r['closed']),capacity_unknown_open_net_contribution=sum(r['net_contribution']for r in affected if not r['closed']),capacity_unknown_top_abs=top[:10],ever_stale_roots=len(stale),ever_stale_net_contribution=sum(r['net_contribution']for r in stale),historical_stale_days=diag['stale_days'],gap_stop_fills=len(diag['gap_stop_fills']),gap_stop_exceeds_1R=diag['gap_stop_exceeds_1R'],worst_gap_stop_fill=diag['worst_gap_stop_fill'],model_realized_balance=s['ending_equity']-s['unrealized'],float_pnl=s['unrealized'],annual=diag['annual_slices'],not_adjusted_backtest=True,unknown_net_not_removed_from_curve=True))
choices=pd.read_csv(F/'choices_main.csv.gz',keep_default_na=False);selection=[]
for arm,g in choices.groupby('arm'):
 sel=g[g.selected.eq(1)];noncanon=sel.chosen_epoch.ne(sel.anchor_epoch)
 selection.append(dict(arm=arm,complete_parent_rows=len(g),selected_family_u=len(sel),noncanonical_selected=int(noncanon.sum()),noncanonical_fraction=float(noncanon.mean()),selected_products=int(sel.product_id.nunique()),selected_families=int(sel.family_id.nunique())))
fy=pd.read_csv(C/'family_total_including_zero.csv.gz');concentration=[]
for (arm,window,cost),g in fy.groupby(['arm','window','cost']):
 top=g.sort_values('net_equity_contribution',ascending=False);positive=g[g.net_equity_contribution.gt(0)];den=positive.net_equity_contribution.sum()
 concentration.append(dict(arm=arm,window=window,cost=cost,positive_family_contribution=den,top5=top.head(5).to_dict('records'),top2_positive_share=float(top.head(2).net_equity_contribution.sum()/den) if den>0 else None))
r=dict(schema='stage133_descriptive_attribution_v1',status='completed_descriptive_not_rebacktest',independent_review_pending=True,accounts=rows,prospective_selection=selection,concentration=concentration,meaning='existing ledger episode attribution only; unknown profit is not asserted executable or removed to invent a counterfactual equity; no model/data/cash replay',new_SQL=0,new_fits=0,new_cash_runs=0)
p=O/'postrun_descriptive_attribution.json';p.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(selections=selection,main_stress=[{k:r[k]for k in ['arm','growth','capacity_unknown_roots','capacity_unknown_net_contribution','ever_stale_roots','ever_stale_net_contribution','historical_stale_days','gap_stop_exceeds_1R','model_realized_balance']}for r in rows if r['window']=='primary_2020'and r['cost']=='stress']),ensure_ascii=False))
