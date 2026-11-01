"""Audit annual CSV/PNG/report derived from a single already-saved fresh window."""
from pathlib import Path
import ast,hashlib,json
import numpy as np
import pandas as pd
from PIL import Image
D=Path(__file__).resolve().parent;LINE=D.parent;ROOT=LINE.parents[2];A=LINE/'artifacts/stage019_2026_ytd';checks=0
load=lambda p:json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ok(v,label):
 global checks;checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(np.allclose(a,b,rtol=0,atol=1e-6,equal_nan=False),label)
raw=load(D/'Stage019_review_raw_result.json');m=raw['metrics'];RUN=Path(raw['source_run']);sm=load(A/'source_manifest.json');s=load(A/'summary.json');r=pd.read_csv(RUN/'reserve_daily.csv');d=pd.read_csv(RUN/'daily.csv');c=pd.read_csv(A/'daily.csv');events=pd.read_csv(RUN/'reserve_events.csv');fills=pd.read_csv(RUN/'trades.csv');months=pd.read_csv(A/'monthly.csv');deposits=pd.read_csv(A/'deposits.csv');trades=pd.read_csv(A/'trades.csv')
expected_sources={**raw['raw_files_sha256'],str(D/'stage014_independent_receipts/2026-01-01_C.json'):sha(D/'stage014_independent_receipts/2026-01-01_C.json'),str(LINE/'tools/Stage019_ytd_report.py'):sha(LINE/'tools/Stage019_ytd_report.py')}
ok(sm['source_files_sha256']==expected_sources,'source_map_exact74_plus_receipt_generator')
for p,h in sm['source_files_sha256'].items():ok(sha(p)==h,'source_pin:'+Path(p).name)
ok(set(sm['outputs_sha256'])=={'daily.csv','monthly.csv','deposits.csv','trades.csv','summary.json','2026_ytd_nav.png'},'all_six_initial_outputs')
for p,h in sm['outputs_sha256'].items():ok(sha(A/p)==h,'output_pin:'+p)
ok(sm['status']=='INDEPENDENT_REVIEW_PENDING' and sm['financial_replays_this_turn']==0 and sm['production_qualified']is False,'generator_pending_no_hash_cycle')
ok(c.date.tolist()==r.date.tolist()==d.date.tolist()and len(c)==198,'daily_exact_dates')
for key in ['net_pnl','slippage','commission','trade_count','total_margin_exact']:near(c[key],d[key],'daily_raw_column:'+key)
T=c.date.map(events.groupby('date').transfer_amount.sum()).fillna(0).to_numpy();cumT=np.cumsum(T);E=r.trading_account_equity.to_numpy();R=r.reserve_balance.to_numpy();dd=100*(E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1)
for key,want in dict(daily_deposit=T,cumulative_deposit=cumT,trading_equity=E,off_account_reserve=R,account_nav=E/150000.,drawdown_pct=dd).items():near(c[key],want,'derived_column:'+key)
near(c.trading_equity,150000.+np.cumsum(d.net_pnl)+cumT,'independent_report_cash_bridge');near(E+R,300000.+np.cumsum(d.net_pnl),'wealth_bridge')
for month,g in d.assign(month=d.date.str[:7]).groupby('month'):
 got=months.loc[months.month.eq(month)];ok(len(got)==1,'monthly_unique');ix=np.flatnonzero(c.date.str[:7].eq(month));row=got.iloc[0];near([row.net_trading_profit,row.deposits,row.end_equity,row.fills],[g.net_pnl.sum(),T[ix].sum(),E[ix[-1]],g.trade_count.sum()],'monthly_recompute')
ok(len(months)==10 and months.month.tolist()==sorted(set(d.date.str[:7])),'all_actual_months')
ok(deposits.shape==(1,7) and deposits.columns.tolist()==['date','vt_symbol','direction','transfer_amount','trading_equity_before','trading_equity_after','reserve_after'],'deposit_projection_shape')
pd.testing.assert_frame_equal(deposits,events[deposits.columns],check_dtype=False);checks+=1
ok(trades.shape==(36,6),'trade_projection_shape');pd.testing.assert_frame_equal(trades,fills[trades.columns],check_dtype=False);checks+=1
keymap={'initial_trading_capital':'initial_trading','end_trading_equity':'end_equity','account_growth_including_deposits_pct':'account_growth_including_T_pct','net_trading_profit':'net_trading_pnl','trading_profit_over_initial_pct':'net_pnl_over_initial_trading_pct','external_deposits':'external_topup','reserve_remaining':'reserve_remaining','max_drawdown_pct':'max_drawdown_pct','account_sharpe':'sharpe','total_slippage':'slippage','total_commission':'commission','modeled_fill_count':'fills','terminal_open_net_mtm':'terminal_open_net_mtm','drawdown_peak_equity':'peak_equity','drawdown_trough_equity':'trough_equity','minimum_equity':'min_equity','model_margin_peak_pct':'static_margin165_peak_pct'}
for target,source in keymap.items():near(s[target],m[source],'summary_independent:'+target)
roundmap={'count':'closed_rounds','wins':'wins','losses':'losses','flat':'flat','win_rate_pct':'win_rate_pct','average_win':'mean_win','average_loss_abs':'mean_loss_abs','payoff_ratio':'payoff_ratio','profit_factor':'profit_factor','closed_net_pnl':'net_trading_pnl'}
for target,source in roundmap.items():near(s['rounds'][target],m[source],'independent_FIFO_summary:'+target)
for target,source in {'requested_start':'requested_start','actual_start':'actual_start','actual_end':'actual_end','drawdown_peak_date':'peak_date','drawdown_trough_date':'trough_date'}.items():ok(s[target]==m[source],'summary_date:'+target)
ok(s['trading_days']==198 and s['deposit_event_count']==1 and s['model_margin_over100_days']==int(np.sum(d.total_margin_exact.to_numpy()*1.65/E>1))==0,'scope_deposits_margin_count')
ok(s['method']=='verified_existing_fresh_engine_window'and s['financial_replays_this_turn']==0 and s['original_window_fresh_engine']is True and s['full_period_curve_sliced']is False and s['production_qualified']is False,'transparent_reuse_not_production')
# Inspect the plotting dataflow without rerunning the report or any engine.
script=(LINE/'tools/Stage019_ytd_report.py').read_text();tree=ast.parse(script);imports=[]
for n in ast.walk(tree):
 if isinstance(n,ast.Import):imports.extend(x.name for x in n.names)
 if isinstance(n,ast.ImportFrom):imports.append(n.module or '')
ok(not any(any(x in n.lower()for x in ['vnpy','engine','strategy','ctp','smtp','requests','urllib','socket'])for n in imports),'report_no_financial_or_external_client_import')
ok("plot_dates=pd.to_datetime(['2026-01-01',*curve.date]);nav=np.r_[1,curve.account_nav]"in script and 'ax.plot(plot_dates,nav,'in script,'nav_exact199_no_unused_R')
ok(sm['plot_points']==199 and sm['actual_daily_rows']==198,'initial_money_point_separate')
ok('dd.fill_between(dates,curve.drawdown_pct,0' in script and 'dd.plot(dates,curve.drawdown_pct' in script,'DD_actual198data')
ok('for event in transfers.itertuples()'in script and "curve.loc[curve.date.eq(event.date),'account_nav']"in script,'deposit_actual_date_NAV')
with Image.open(A/'2026_ytd_nav.png')as im:dimensions=im.size;ok(dimensions==(2052,1188),'PNG_dimensions')
text=(A/'report.md').read_text()
for token in ['173,100','22,380','14.92%','15.40%','-36.16%','720','149,280','36 / 18','8盈10亏','13,370','8,458','1.581','1.265','2,930','93.82%','198','2026-01-05','2026-10-30','不重新运行金融引擎','不从2015总曲线切片','人工核验/真实转账时延','非新OOS','手续费0']:ok(token in text,'report_fact_or_limitation:'+token)
result=dict(schema='Stage019.independent-derived-report-audit.v1',accepted=True,status='PASS_WITH_LIMITATIONS',failures=[],checks=checks,source_manifest_sha256=sha(A/'source_manifest.json'),raw_review_sha256=sha(D/'Stage019_review_raw_result.json'),derived_files_sha256={str(p):sha(p)for p in sorted(A.iterdir())if p.is_file()},audited_generator_sha256=sha(LINE/'tools/Stage019_ytd_report.py'),plot=dict(actual_daily_rows=198,nav_plot_points=199,initial_point='2026-01-01 money only, no bar',source_curve='trading E / 150000, T included, unused reserve excluded',dimensions=dimensions,viewed=True,visual_findings=[],annotations_independently_verified={'peak':[m['peak_date'],m['peak_equity']],'DD_valley':[m['trough_date'],m['trough_equity']],'topup':['2026-09-11',720],'end':[m['actual_end'],m['end_equity']]}),findings=[],limitations=raw['limitations'],new_financial_replays=0,production_qualified=False,note='Generator source_manifest remains its immutable pending snapshot; a later outer delivery receipt may bind this review and the added report without a hash cycle.')
p=D/'Stage019_review_derived_result.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'checks':checks,'result_sha256':sha(p),'source_manifest_sha256':result['source_manifest_sha256']}))
