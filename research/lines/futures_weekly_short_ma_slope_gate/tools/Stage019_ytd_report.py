"""Read-only presentation of an existing independently cold-started YTD replay.

No engine, strategy, market client, live broker or email component is imported.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math,os,subprocess
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly19-stage019-mpl')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
SOURCE=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/stage014_C_20260101_attempt001')
REVIEW=LINE/'stages/stage014_independent_receipts/2026-01-01_C.json'
OUT=LINE/'artifacts/stage019_2026_ytd'
INITIAL=150000.0

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def near(actual,expected):
 if not np.allclose(actual,expected,rtol=1e-10,atol=1e-6):raise ValueError('YTD accounting mismatch')

def main():
 if OUT.exists():raise ValueError('Preserve existing report; use a new explicit attempt')
 accepted=json.loads(REVIEW.read_text())
 assert accepted['status']=='PASS_WITH_LIMITATIONS'and not accepted['failures']
 assert accepted['requested_start']=='2026-01-01'and accepted['end']=='2026-10-30'
 assert accepted['method']=='fresh_engine'and accepted['reused']is False
 pins=accepted['source_files_sha256']
 for path,want in pins.items():assert sha(path)==want,path
 d=pd.read_csv(SOURCE/'daily.csv',float_precision='round_trip')
 r=pd.read_csv(SOURCE/'reserve_daily.csv',float_precision='round_trip')
 transfers=pd.read_csv(SOURCE/'reserve_events.csv',float_precision='round_trip')
 trades=pd.read_csv(SOURCE/'trades.csv',float_precision='round_trip')
 assert d.date.tolist()==r.date.tolist()and not d.date.duplicated().any()
 assert len(d)==198 and d.date.iloc[0]=='2026-01-05'and d.date.iloc[-1]=='2026-10-30'
 curve=d[['date','net_pnl','slippage','commission','trade_count','total_margin_exact']].copy()
 curve['daily_deposit']=curve.date.map(transfers.groupby('date').transfer_amount.sum()).fillna(0.0)
 curve['cumulative_deposit']=curve.daily_deposit.cumsum()
 curve['trading_equity']=INITIAL+curve.net_pnl.cumsum()+curve.cumulative_deposit
 curve['off_account_reserve']=INITIAL-curve.cumulative_deposit
 curve['account_nav']=curve.trading_equity/INITIAL
 e=curve.trading_equity.to_numpy(float);previous=np.r_[INITIAL,e[:-1]]
 curve['drawdown_pct']=100*(e/np.maximum.accumulate(np.r_[INITIAL,e])[1:]-1)
 near(curve.trading_equity,r.trading_account_equity)
 near(curve.cumulative_deposit,r.cumulative_transfer)
 near(curve.off_account_reserve,r.reserve_balance)
 near(curve.trading_equity-curve.cumulative_deposit,d.account_equity)
 near(curve.off_account_reserve+curve.cumulative_deposit,INITIAL)
 near(curve.slippage.sum(),2930);near(curve.commission.sum(),0)
 assert int(curve.trade_count.sum())==len(trades)==36
 returns=(e-previous)/previous
 trough=int(curve.drawdown_pct.idxmin());peak=int(curve.loc[:trough,'trading_equity'].idxmax())
 margin=100*curve.total_margin_exact*1.65/curve.trading_equity
 rounds=accepted['metrics']['rounds']
 summary=dict(schema='Stage019.existing-independent-YTD-result.v1',requested_start='2026-01-01',
  actual_start=curve.date.iloc[0],actual_end=curve.date.iloc[-1],trading_days=len(curve),
  variant='Stage014 C_R150 / m0002 fixed alpha',method='verified_existing_fresh_engine_window',
  financial_replays_this_turn=0,original_window_fresh_engine=True,full_period_curve_sliced=False,
  initial_trading_capital=INITIAL,initial_external_reserve=INITIAL,end_trading_equity=float(e[-1]),
  account_growth_including_deposits_pct=100*(e[-1]/INITIAL-1),net_trading_profit=float(curve.net_pnl.sum()),
  trading_profit_over_initial_pct=float(curve.net_pnl.sum()/INITIAL*100),
  external_deposits=float(curve.cumulative_deposit.iloc[-1]),reserve_remaining=float(curve.off_account_reserve.iloc[-1]),
  deposit_event_count=len(transfers),max_drawdown_pct=float(curve.drawdown_pct.min()),
  account_sharpe=float(returns.mean()/returns.std(ddof=1)*math.sqrt(252)),
  total_slippage=float(curve.slippage.sum()),total_commission=float(curve.commission.sum()),
  modeled_fill_count=len(trades),rounds=rounds,terminal_open_net_mtm=float(accepted['metrics']['open_round_net_mtm']),
  drawdown_peak_date=curve.date.iloc[peak],drawdown_peak_equity=float(e[peak]),
  drawdown_trough_date=curve.date.iloc[trough],drawdown_trough_equity=float(e[trough]),
  minimum_equity=float(min(e)),model_margin_peak_pct=float(margin.max()),model_margin_over100_days=int(margin.gt(100).sum()),
  source_window=str(SOURCE),original_review=str(REVIEW),production_qualified=False,
  current_source_head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
  limitations=['same_observed_history_not_OOS','zero_commission','fixed_slippage','static_margin_multiplier_1.65',
   'declared_next_daily_open_not_tick_capacity','research_topup_instant_on_eligible_signal_not_manual_transfer_latency'])
 near(summary['end_trading_equity'],173100);near(summary['net_trading_profit'],22380)
 near(summary['external_deposits'],720);near(summary['reserve_remaining'],149280)
 near(summary['max_drawdown_pct'],accepted['account_display']['max_dd_pct'])
 near(summary['account_sharpe'],accepted['account_display']['sharpe'])
 near(summary['net_trading_profit'],rounds['closed_net_pnl']+summary['terminal_open_net_mtm'])
 OUT.mkdir(parents=True)
 curve.to_csv(OUT/'daily.csv',index=False)
 month=curve.assign(month=curve.date.str[:7]).groupby('month',as_index=False).agg(
  net_trading_profit=('net_pnl','sum'),deposits=('daily_deposit','sum'),end_equity=('trading_equity','last'),
  fills=('trade_count','sum'))
 month.to_csv(OUT/'monthly.csv',index=False)
 transfers[['date','vt_symbol','direction','transfer_amount','trading_equity_before','trading_equity_after','reserve_after']].to_csv(OUT/'deposits.csv',index=False)
 trades[['datetime','vt_symbol','direction','offset','price','volume']].to_csv(OUT/'trades.csv',index=False)
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False))
 font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
 plt.rcParams.update({'font.family':font.get_name(),'font.size':10,'axes.unicode_minus':False,'axes.edgecolor':'#ccd4df'})
 fig,(ax,dd)=plt.subplots(2,1,figsize=(11.4,6.6),gridspec_kw={'height_ratios':[3,1.1]},sharex=True)
 fig.patch.set_facecolor('white');fig.subplots_adjust(top=.79,bottom=.16,left=.09,right=.95,hspace=.13)
 fig.text(.09,.94,'2026年至今｜19品种周线 C_R150',fontproperties=font,fontsize=21,weight='bold',color='#15243b')
 fig.text(.09,.888,'初始交易资金15万元 · 场外备用金15万元 · 原风险档位 · 空头底部20%过滤 · 无加仓',fontproperties=font,fontsize=10.5,color='#53647b')
 fig.text(.09,.838,'期末 173,100元    交易净利 +22,380元    累计补资 720元    最大回撤 −36.16%',fontproperties=font,fontsize=12,color='#15243b')
 dates=pd.to_datetime(curve.date);plot_dates=pd.to_datetime(['2026-01-01',*curve.date]);nav=np.r_[1,curve.account_nav]
 ax.plot(plot_dates,nav,color='#2367cb',linewidth=2.3);ax.axhline(1,color='#8996a8',linestyle='--',linewidth=.9)
 ax.set_ylabel('交易净值（15万元 = 1）',fontproperties=font);ax.set_ylim(.94,1.66)
 for i,label,xytext,ha in [(peak,'3/23 高点 1.559',(-18,18),'right'),(trough,'9/10 回撤谷点 0.995',(-12,22),'right'),(197,'10/30 期末 1.154',(-8,20),'right')]:
  ax.scatter(dates.iloc[i],curve.account_nav.iloc[i],color='#2367cb',s=22,zorder=4)
  ax.annotate(label,(dates.iloc[i],curve.account_nav.iloc[i]),xytext=xytext,textcoords='offset points',ha=ha,fontproperties=font,fontsize=9,color='#23354f')
 for event in transfers.itertuples():
  date=pd.Timestamp(event.date);value=float(curve.loc[curve.date.eq(event.date),'account_nav'].iloc[0])
  ax.scatter(date,value,s=48,marker='D',color='#c2720d',zorder=5)
  ax.annotate('9/11 补入720元',(date,value),xytext=(10,6),textcoords='offset points',fontproperties=font,fontsize=9,color='#a05d08')
 dd.fill_between(dates,curve.drawdown_pct,0,color='#cf5263',alpha=.22);dd.plot(dates,curve.drawdown_pct,color='#b13d50',linewidth=1.1)
 dd.axhline(0,color='#8996a8',linewidth=.7);dd.set_ylabel('回撤（%）',fontproperties=font);dd.set_ylim(-42,2)
 dd.xaxis.set_major_locator(mdates.MonthLocator());dd.xaxis.set_major_formatter(mdates.DateFormatter('%m月'))
 for a in (ax,dd):
  a.grid(axis='y',color='#e7ecf2',linewidth=.7);a.spines[['top','right']].set_visible(False)
 dd.set_xlim(pd.Timestamp('2026-01-01'),pd.Timestamp('2026-11-01'))
 fig.text(.09,.075,'净值包含已补入的720元，剩余场外备用金149,280元不参与净值；补资不是交易利润。',fontproperties=font,fontsize=9,color='#59677a')
 fig.text(.09,.036,'2026-01-01独立起点，实际198个交易日（1/5—10/30）；复核已有完整回测，未重跑金融引擎。手续费0，非新OOS。',fontproperties=font,fontsize=8.5,color='#66758a')
 fig.savefig(OUT/'2026_ytd_nav.png',dpi=180,facecolor='white');plt.close(fig)
 source_map={**pins,str(REVIEW):sha(REVIEW),str(Path(__file__)):sha(__file__)}
 manifest=dict(generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),source_files_sha256=source_map,
  outputs_sha256={p.name:sha(p)for p in OUT.iterdir()if p.is_file()},status='INDEPENDENT_REVIEW_PENDING',
  financial_replays_this_turn=0,original_method='fresh_engine',plot_points=199,actual_daily_rows=198,
  initial_plot_point='2026-01-01 initial money only; not market data',production_qualified=False)
 (OUT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False,allow_nan=False))

if __name__=='__main__':main()
