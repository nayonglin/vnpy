"""Pure five-figure view of all 59 fresh C/R150 accounts; no reads or writes.

Every date sequence is pinned below to the frozen additive mapping snapshot.
Account E includes transfers; untransferred reserve never enters account NAV.
"""
import hashlib
import numpy as np
import pandas as pd
from matplotlib import dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from stage014_contract import STARTS,MONTHS,MATURE_STARTS,OBSERVATION_STARTS,CUTOFF
from stage013_plots import balance_sharpe

INITIAL=150000.
EXPECTED_DAILY_POINTS=86049
FROZEN_MAPPING_SHA256='2dd16b914b6e89ba41798b3c8ca8ed0f91b16097b3ac3504c55d3846b97fc204'
# start: (actual first exchange date, exact count, SHA256 of newline-joined dates)
WINDOW_SCOPE={
 '2015-01-01':('2015-01-05',2872,'eb87f9565210f4d9ffc8990487cdcd93a796df84fb7e21031c4d9c138ec02bbc'),
 '2015-03-01':('2015-03-02',2837,'b6e23d752013de2ed65ab526bb9b0bf3e89c034d60e77b3075f8bc230536bfde'),
 '2015-06-01':('2015-06-01',2774,'7a80ffd3e05ae1fd6180580abbbf7f888675bfc624c290eed5506b03be3bc0a7'),
 '2015-09-01':('2015-09-01',2709,'a7a169fbebfb35de8cb995a143869c8f1a28e528fe4ff773449d0e34fae45ef3'),
 '2015-11-01':('2015-11-02',2672,'f3265edb74594a56d115dcb48afa791c8af9364111899070641ce05630a81cec'),
 '2016-01-01':('2016-01-04',2628,'d1877d9f2974dbd38eb6055752586ff52675a1040da8b0e98e704540ef1429ae'),
 '2016-03-01':('2016-03-01',2592,'655bb27e36a7c060d8e88017caa808bd91c7055e27d300564e190559d8675d39'),
 '2016-06-01':('2016-06-01',2528,'5e587330c6c93a6b2d2c5aadc75c31f224d4014716e925e2fc4fa34d13692c65'),
 '2016-09-01':('2016-09-01',2464,'aad015b1296389cc1de835c9584e4b1d915156cef8cdb9e5146bb445bd1a2244'),
 '2016-11-01':('2016-11-01',2428,'846029ed7ca9bba2e112e3dfead4da8c0866a7837326c38438b69434f272dbf7'),
 '2017-01-01':('2017-01-03',2384,'d63da9e26e65dc2714000f432bf4726bf7f0b87152414087717c305a8b29b03d'),
 '2017-03-01':('2017-03-01',2348,'fdb8f59dff222a5acda7fddc58cde60210a0367e5740cfd2165a31c69b687750'),
 '2017-06-01':('2017-06-01',2287,'a847519bc4177cf9679ec090f3c1022d77285c426a5f6be670f713992fbad614'),
 '2017-09-01':('2017-09-01',2221,'869adfb28b71c9f00366808a26c9b8c4fcd84ab8d1ff861a14b41cb605e93c53'),
 '2017-11-01':('2017-11-01',2183,'1c7f93d841a670fec926b1de5d89931a21a43f6c9a2745505660de8c77f04c29'),
 '2018-01-01':('2018-01-02',2140,'84f16a15df5a429d9fb1e7a3d942f12a3df5a03d9e2909b92d408680128061ab'),
 '2018-03-01':('2018-03-01',2103,'c60d431efb5ccdc402b095a8c00968836197804e4ff9d889897fbc55f06f4538'),
 '2018-06-01':('2018-06-01',2041,'163abd5c88a3b3b35f870a3eb5769bca3f8f91d3445399679e56bc6cb5b4c47e'),
 '2018-09-01':('2018-09-03',1976,'2b8a845c58fe1330d5b35ae3dc0f170d2319af22f43c53ce9c845ff6c2ee7526'),
 '2018-11-01':('2018-11-01',1939,'98aad487d3879a56976816f52154b53c353a33518e5615e183a308aa46cecb01'),
 '2019-01-01':('2019-01-02',1897,'f2ac46dfdce5960deb4b6d0043b0913233228e488703020de76611950c2803eb'),
 '2019-03-01':('2019-03-01',1860,'ff5d515e5a2d7997d8b2e32ec74cf3303acac603dda5242f954c72f507339566'),
 '2019-06-01':('2019-06-03',1798,'d209497f9fee3dfbe128fbdf54c99c311e61932d938e1891aad5cb1b9ee38971'),
 '2019-09-01':('2019-09-02',1734,'87a7879c92f0d677f985d583e85c8e7af7cccec12e07118a9ec29319a2db0e30'),
 '2019-11-01':('2019-11-01',1696,'b9238e5ab8deead1c825d4f80b840c3a0561b62b4fdea7998c1826d75edd7ec2'),
 '2020-01-01':('2020-01-02',1653,'e33460f1b7c83b18bedeb8d9680e932b3f05a22fc5da19f23d76197d22d18613'),
 '2020-03-01':('2020-03-02',1617,'3198286ec801934d000aa89cd3a11d659cb85fcc557711b2964bd8eada192955'),
 '2020-06-01':('2020-06-01',1556,'dd9730de90ee07867e9255e0a534656459d0ee51f54b3c98daa6dd0317db5515'),
 '2020-09-01':('2020-09-01',1492,'d863f395d497ba60e15d24190b5348392113e5ab92e85620b1899accbf37bf12'),
 '2020-11-01':('2020-11-02',1454,'05881d7cc49d32fd48ab11f65a0b40ff1fc925b9343059aaa19bb738eb6aed77'),
 '2021-01-01':('2021-01-04',1410,'f9cd271c7621364a0b3c602e5c706071fe9fb865fa32711ecf116a9d5d03e6d3'),
 '2021-03-01':('2021-03-01',1375,'d016a79c0b1b248912d4e9c4fa6b83c64e2d3dd67d03e7a9e3c5d230f0315b2d'),
 '2021-06-01':('2021-06-01',1313,'688f21c0db2c7d602ff887d94c34c8433cccf9fd1496943a5db278c68f5263b6'),
 '2021-09-01':('2021-09-01',1248,'07af6ac16ddc9d66962f0dc50333f7ce09e656b94548afb707f6cc6201405363'),
 '2021-11-01':('2021-11-01',1212,'57babd11bc9a43a7e3c080fc92aabf7d4316e14678360b6f8d0c05d3833cd5a6'),
 '2022-01-01':('2022-01-04',1167,'58a765d4a2415a5d52f5c1026e14ee997fc52fd492cce1f2a45b9fb06af8a42c'),
 '2022-03-01':('2022-03-01',1132,'02c853edcfe309e063f3824d70cd195a4724d2ba51ab43ef5be2fa972dce1fcf'),
 '2022-06-01':('2022-06-01',1071,'25a4700ce88d1f38d3779bd307d066822c9b5f62c8174e6b09b3494fbf1cef87'),
 '2022-09-01':('2022-09-01',1006,'ef6b078fbb08c91dff6a49566938087dd19914aaed3b75f72e30ce24b05b2c3e'),
 '2022-11-01':('2022-11-01',969,'dba395f392921c417625217591e77dbfda9022310efe72f2a1ee027f9d620ef1'),
 '2023-01-01':('2023-01-03',925,'5b5c538e47ef21598ae2ee1dae79697d2ff771cbb4a6f138243146b3b1f72c93'),
 '2023-03-01':('2023-03-01',889,'920917d9f5eaef8f9b8d09160344b1fd1e021049075368bb1a67e4a6a01e5028'),
 '2023-06-01':('2023-06-01',827,'786a1e300acc78a5080da6877ca4b7af4d3e294cd7f2c7614e8cf285a3b35290'),
 '2023-09-01':('2023-09-01',763,'eabcde9004b0e7558f7a77be355d7102aa4174d4cae250658e51fd1fed0f4351'),
 '2023-11-01':('2023-11-01',726,'4b723f4a26b8a1d74a946766ece06e0ecb8345e665301d4695dc24d6520b33f6'),
 '2024-01-01':('2024-01-02',683,'ee180fc15edb6da1b509ba52c6ee925a38c7c7665b49adcd22c4f46ab72098df'),
 '2024-03-01':('2024-03-01',646,'28becd2d0dc8e566fc376e53ecd34891718e81988c396f03cb852b7d669a285a'),
 '2024-06-01':('2024-06-03',585,'27f74a06451d900a4c3b551e3319edac87e7a525bd5fe71394b5e38d6a5ebee4'),
 '2024-09-01':('2024-09-02',521,'f6e5c1aca0f5bf4eeb14209fca06b50bc4992c9ce53e6507b0b8c7daa4c6a065'),
 '2024-11-01':('2024-11-01',484,'ceed31fd5e48cc413d04fe70bcdac02a063b7aad2632f7fee2a2522fde3f10f9'),
 '2025-01-01':('2025-01-02',441,'78cdc808c2e8a997f70791f307437f0665fdd3703c1a71fe0dff7de658aa4496'),
 '2025-03-01':('2025-03-03',405,'81ebfc6e52c2356b902f8b0f7ae8b462d4f1e8b86aecbc6386a05394e4870474'),
 '2025-06-01':('2025-06-03',344,'085306143f8ffbb7302a7efe1ac0b035d0de87913bbeb9f339a5b3acfcb04787'),
 '2025-09-01':('2025-09-01',280,'c8a94de0b781b3409c6e1157899ed0ffaa314192bb6e6d7fe1a90366bf6f6172'),
 '2025-11-01':('2025-11-03',241,'4503fdbcf3cbcffe00b6fed829f6153ff584f44b6458912c08f66416e8c79d55'),
 '2026-01-01':('2026-01-05',198,'c4c9ec57f09850674b7ba7520888c36493d1695c114280d370057236ff38bfa1'),
 '2026-03-01':('2026-03-02',164,'9e30d6218acb9463c03c7dc1bb3dc5c43c89fb76177fcf69e0c6bd229cd81c28'),
 '2026-06-01':('2026-06-01',103,'997a9a7f5aa81c37368fe17d3ecb3d492276ef33dbb978340378d949a356b9c8'),
 '2026-09-01':('2026-09-01',38,'bf47abf7df2f0ac0b324086d8b7638199232e550f2c3673196986b413308cc6a'),
}
FIGURE_NAMES=('01_full_2015_account_and_funding.png','02_all_month_cohort_curves.png','03_all_start_year_curves.png',
 '04_all_window_metric_matrices.png','05_funding_risk_and_cohort_overview.png')
MONTH_NAMES={1:'January',3:'March',6:'June',9:'September',11:'November'}
MONTH_COLORS={1:'#2168ad',3:'#d88624',6:'#278a62',9:'#be3e55',11:'#8357a8'}
YEAR_COLORS={year:__import__('matplotlib').colormaps['turbo']((year-2015)/11) for year in range(2015,2027)}
FOOTER=('C_R150 only: original 19 / short bottom 20% veto / original OI risks 1.8%, 6%, 6%, 2.5%; no add-on or new MA/long-price gate.\n'
 'Account NAV = E / 150k, initial 1: external reserve excluded; deposits INCLUDED. Account growth/DD/Sharpe include cashflows; real PnL is separate.\n'
 '59 fresh independent account replays / 54 mature / 5 observation; overlapping histories are not independent OOS. Cutoff 2026-10-30; NO_PROMOTION.')
NULLABLE_ROUND_FIELDS={'round_win_rate_pct','round_average_win','round_average_loss_abs','round_payoff_ratio','round_profit_factor'}
ROUND_FIELDS=NULLABLE_ROUND_FIELDS|{'round_count','round_wins','round_losses','round_flat','round_closed_net_pnl','open_round_net_mtm'}
SUMMARY_FIELDS={'start','variant','arm','version','method','funding_mode','cohort_month','reserve_initial','initial_trading_capital',
 'actual_start','actual_end','trading_days','observation_only','account_end_equity','account_growth_pct','balance_max_dd_pct','balance_sharpe',
 'balance_returns_defined','real_trading_net_pnl','total_transferred','off_account_reserve_end','total_slippage','total_commission','modeled_fill_count',
 'transfer_event_days','transfer_event_count','reserve_exhausted','exhaustion_date','nonpositive_trading_equity_days','trading_margin_peak_pct',
 'trading_margin_over100_days'}|ROUND_FIELDS
DAILY_FIELDS={'start','variant','date','raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer',
 'transfer_amount','total_account_equity','slippage','commission','trade_count','total_margin_exact','account_nav','balance_drawdown_pct'}


def require(value,label):
 if not value:raise ValueError('stage014_plots:'+label)


def near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)


def boolean(value):
 if isinstance(value,(bool,np.bool_)):return bool(value)
 if value=='True':return True
 if value=='False':return False
 raise ValueError('stage014_plots:explicit_boolean_required')


def validate_round_fields(row):
 for field in ('round_count','round_wins','round_losses','round_flat'):
  value=float(row[field]);require(np.isfinite(value) and value>=0 and value==int(value),'round_integer_'+field)
 require(row.round_count==row.round_wins+row.round_losses+row.round_flat,'round_count_bridge')
 for field in NULLABLE_ROUND_FIELDS:
  value=row[field];require(pd.isna(value) or (np.isfinite(float(value)) and value>=0),'round_finite_or_null_'+field)
 if row.round_count:
  require(near(row.round_win_rate_pct,row.round_wins/row.round_count*100),'round_win_rate')
 if not row.round_count or not row.round_losses:require(pd.isna(row.round_profit_factor),'PF_undefined_without_loss_denominator')
 if not row.round_wins or not row.round_losses:require(pd.isna(row.round_payoff_ratio),'payoff_undefined_without_both_sides')
 if not pd.isna(row.round_payoff_ratio):
  require(pd.notna(row.round_average_win) and pd.notna(row.round_average_loss_abs) and row.round_average_loss_abs>0,'round_payoff_denominator')
  require(near(row.round_payoff_ratio,row.round_average_win/row.round_average_loss_abs),'round_payoff')
 if not pd.isna(row.round_profit_factor):
  require(row.round_losses>0 and pd.notna(row.round_average_loss_abs) and row.round_average_loss_abs>0,'round_PF_denominator')
  require(not row.round_wins or pd.notna(row.round_average_win),'round_PF_numerator')
  gross_win=0. if not row.round_wins else row.round_wins*row.round_average_win
  require(near(row.round_profit_factor,gross_win/(row.round_losses*row.round_average_loss_abs)),'round_PF')
 require(near(row.round_closed_net_pnl+row.open_round_net_mtm,row.real_trading_net_pnl),'closed_plus_open_real_PnL')


def validate_inputs(summary,daily):
 for name,frame,fields in [('summary',summary,SUMMARY_FIELDS),('daily',daily,DAILY_FIELDS)]:
  require(isinstance(frame,pd.DataFrame) and fields<=set(frame),'missing_'+name+'_columns')
 s,d=summary.copy(),daily.copy()
 require(len(s)==59 and not s.start.duplicated().any() and set(s.start)==set(STARTS),'exact59_summary')
 require(len(d)==EXPECTED_DAILY_POINTS and set(d.start)==set(STARTS) and not d.duplicated(['start','date']).any(),'exact86049_daily')
 strings={'start','variant','arm','version','method','funding_mode','actual_start','actual_end','exhaustion_date'}
 bools={'observation_only','balance_returns_defined','reserve_exhausted'}
 for field in bools:s[field]=s[field].map(boolean)
 for frame,fields in [(s,SUMMARY_FIELDS-strings-bools),(d,DAILY_FIELDS-{'start','variant','date'})]:
  for field in fields:
   frame[field]=pd.to_numeric(frame[field],errors='raise');a=frame[field].to_numpy(float)
   allowed=(np.isfinite(a)|np.isnan(a)) if field in NULLABLE_ROUND_FIELDS|{'trading_margin_peak_pct'} else np.isfinite(a)
   require(allowed.all(),'finite_'+field)
 for frame,fields in [(s,('actual_start','actual_end')),(d,('date',))]:
  for field in fields:
   date=pd.to_datetime(frame[field],errors='raise');require(date.notna().all() and (date==date.dt.normalize()).all(),'daily_dates')
   frame[field]=date.dt.strftime('%Y-%m-%d')
 for frame,fields in [(s,('cohort_month','trading_days','modeled_fill_count','transfer_event_days','transfer_event_count','nonpositive_trading_equity_days','trading_margin_over100_days')),(d,('trade_count',))]:
  for field in fields:require((frame[field]>=0).all() and (frame[field]==np.floor(frame[field])).all(),'nonnegative_integer_'+field)
 for frame,fields in [(s,('total_slippage','total_commission')),(d,('slippage','commission','trade_count','transfer_amount','total_margin_exact'))]:
  for field in fields:require((frame[field]>=0).all(),'nonnegative_'+field)
 si=s.set_index('start',drop=False);curves={}
 for start,group in d.groupby('start',sort=False):
  m=si.loc[start];g=group.sort_values('date').reset_index(drop=True);actual,count,digest=WINDOW_SCOPE[start]
  require(m.variant=='C_R150' and m.arm=='C' and m.version=='reserve150k' and m.method=='fresh_engine' and m.funding_mode=='external_topup','single_C_R150_fresh_identity')
  require(g.variant.eq('C_R150').all(),'daily_single_C_R150')
  require(m.cohort_month==int(start[5:7]) and bool(m.observation_only)==(start in OBSERVATION_STARTS),'month_maturity_scope')
  require(m.actual_start==actual and m.actual_end==CUTOFF and m.trading_days==count,'frozen_window_endpoints_count')
  require(len(g)==count and hashlib.sha256('\n'.join(g.date).encode()).hexdigest()==digest,'frozen_mapping_calendar_'+start)
  e=g.trading_account_equity.to_numpy(float);raw=g.raw_account_equity.to_numpy(float);pnl=g.net_pnl.to_numpy(float)
  t=g.cumulative_transfer.to_numpy(float);r=g.reserve_balance.to_numpy(float)
  require(near(m.initial_trading_capital,INITIAL) and near(m.reserve_initial,INITIAL),'E150k_R150k')
  require(near(raw,INITIAL+pnl.cumsum()) and near(e,raw+t),'E_real_PnL_deposit_bridge')
  require(near(t,g.transfer_amount.cumsum()) and near(r+t,INITIAL) and (r>=-1e-6).all() and (r<=INITIAL+1e-6).all(),'isolated_reserve_cash_bridge')
  require(near(g.total_account_equity,e+r) and near(g.total_account_equity,300000+pnl.cumsum()),'W_conservation_only')
  require(near(e[0],INITIAL) and near(pnl[0],0) and near(t[0],0),'fresh_initial_NAV1')
  dd=(e/np.maximum.accumulate(np.r_[INITIAL,e])[1:]-1)*100
  require(near(g.account_nav,e/INITIAL) and near(g.balance_drawdown_pct,dd),'NAV_and_E_drawdown')
  sh,defined=balance_sharpe(e);require(bool(m.balance_returns_defined)==defined,'E_Sharpe_defined')
  exhausted=np.flatnonzero(r<=1e-6);date='' if pd.isna(m.exhaustion_date) else str(m.exhaustion_date)
  require(bool(m.reserve_exhausted)==bool(len(exhausted)) and date==(g.date.iloc[int(exhausted[0])] if len(exhausted) else ''),'exhaustion_identity')
  margin=np.divide(g.total_margin_exact.to_numpy(float)*165,e,out=np.full_like(e,np.nan),where=e>0)
  require(near(m.trading_margin_peak_pct,np.nanmax(margin)) if np.isfinite(margin).any() else pd.isna(m.trading_margin_peak_pct),'margin_peak_positive_E_only')
  calculated=dict(account_end_equity=e[-1],account_growth_pct=(e[-1]/INITIAL-1)*100,balance_max_dd_pct=dd.min(),balance_sharpe=sh,
   real_trading_net_pnl=pnl.sum(),total_transferred=t[-1],off_account_reserve_end=r[-1],total_slippage=g.slippage.sum(),total_commission=g.commission.sum(),
   modeled_fill_count=g.trade_count.sum(),transfer_event_days=int(g.transfer_amount.gt(0).sum()),nonpositive_trading_equity_days=int((e<=0).sum()),trading_margin_over100_days=int((margin>100).sum()))
  for field,value in calculated.items():require(near(m[field],value),'summary_daily_'+field)
  require(m.transfer_event_count>=m.transfer_event_days and ((m.transfer_event_count==0)==(m.transfer_event_days==0)),'event_count_daily_bound')
  validate_round_fields(m);g['plot_date']=pd.to_datetime(g.date);curves[start]=g
 return si,curves


def _figure(size):
 fig=Figure(figsize=size,facecolor='white');FigureCanvasAgg(fig);return fig


def _title(fig,index,description,reviewed):
 state='INDEPENDENT REVIEWED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'
 fig.suptitle(f'STAGE014 {index}/5 | {state} | NO_PROMOTION\n'+description,fontsize=11,fontweight='bold',y=.986)


def _footer(fig,extra=''):
 fig.text(.025,.012,FOOTER+('\n'+extra if extra else ''),fontsize=7.2,color='#505c6e',va='bottom')


def _decorate(ax):
 ax.grid(alpha=.16);ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8)


def _curve(ax,start,g,color,label):
 obs=start in OBSERVATION_STARTS
 line=ax.plot(g.plot_date,g.account_nav,color=color,lw=1.25,ls='--' if obs else '-',label=label)[0];line.set_gid(start)


def _ticks(ax,start):
 span=(pd.Timestamp(CUTOFF)-pd.Timestamp(start)).days
 ax.xaxis.set_major_locator(mdates.YearLocator(4 if span>365*6 else 2 if span>365*3 else 1) if span>365 else mdates.MonthLocator(bymonth=[1,4,7,10]))
 ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y' if span>365 else '%b%y'))


def _cohort_curves(curves,reviewed):
 fig=_figure((16,13));axes=fig.subplots(3,2)
 for ax,month in zip(axes.flat,MONTHS):
  starts=[s for s in STARTS if int(s[5:7])==month]
  for start in starts:_curve(ax,start,curves[start],YEAR_COLORS[int(start[:4])],start[:4]+(' OBS' if start in OBSERVATION_STARTS else ''))
  ax.set_title(f'{MONTH_NAMES[month]}: all {len(starts)} requested starts',fontsize=10,fontweight='bold')
  ax.set_ylabel('E account NAV / 150k');_decorate(ax);_ticks(ax,starts[0]);ax.legend(fontsize=6.9,ncol=4,frameon=False)
 axes.flat[-1].axis('off');axes.flat[-1].text(.03,.85,'Each line is a fresh account, starting at NAV 1.\nAll starts are retained; no best-window selection.\nDashed = <1 calendar year observation.\n2026 November is future and is not generated.\nDates remain exchange dates, not aligned pseudo-time.',fontsize=10,va='top',linespacing=1.8)
 _title(fig,2,'Five month cohorts: every one of the 59 fresh E account curves\nYear colors are consistent across cohorts; external reserve is excluded from NAV',reviewed)
 _footer(fig);fig.tight_layout(rect=[.01,.09,.995,.915],h_pad=2.5);return fig


def _year_curves(curves,reviewed):
 fig=_figure((16,12));axes=fig.subplots(4,3)
 for ax,year in zip(axes.flat,range(2015,2027)):
  starts=[s for s in STARTS if s.startswith(str(year))]
  for start in starts:
   month=int(start[5:7]);_curve(ax,start,curves[start],MONTH_COLORS[month],MONTH_NAMES[month]+(' OBS' if start in OBSERVATION_STARTS else ''))
  ax.set_title(f'{year}: {len(starts)} starts'+(' / Nov future' if year==2026 else ''),fontsize=9,fontweight='bold')
  if (year-2015)%3==0:ax.set_ylabel('E NAV / 150k',fontsize=8)
  _decorate(ax);_ticks(ax,starts[0]);ax.tick_params(labelsize=7)
 handles,labels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=5,frameon=False,fontsize=8,loc='upper center',bbox_to_anchor=(.5,.925))
 _title(fig,3,'All twelve start years: 2015-2025 each five starts; 2026 four reached starts\nMonth colors fixed; dashed curves are the five observation windows',reviewed)
 _footer(fig);fig.tight_layout(rect=[.01,.085,.995,.895],h_pad=1.6);return fig


def _matrices(si,reviewed):
 fig=_figure((16,12));axes=fig.subplots(2,2)
 for ax,field,title in zip(axes.flat,('real_trading_net_pnl','balance_max_dd_pct','balance_sharpe','total_transferred'),('Real trading PnL (CNY k)','Account E max DD (%)','Account E Sharpe','Deposits consumed (CNY k)')):
  values=np.full((12,5),np.nan)
  for start,row in si.iterrows():
   if field!='balance_sharpe' or row.balance_returns_defined:values[int(start[:4])-2015,MONTHS.index(int(start[5:7]))]=row[field]/1000 if field in {'real_trading_net_pnl','total_transferred'} else row[field]
  finite=values[np.isfinite(values)];bound=max(float(np.abs(finite).max()),.001) if len(finite) else 1.
  cmap=__import__('matplotlib').colormaps['RdBu'].copy();cmap.set_bad('#d5dbe2')
  im=ax.imshow(np.ma.masked_invalid(values),aspect='auto',cmap=cmap,vmin=-bound,vmax=bound)
  ax.set_title(title,fontsize=11,fontweight='bold');ax.set_xticks(range(5),[MONTH_NAMES[m] for m in MONTHS],fontsize=8);ax.set_yticks(range(12),range(2015,2027),fontsize=8)
  for i in range(12):
   for j,month in enumerate(MONTHS):
    start=f'{2015+i}-{month:02d}-01';value=values[i,j]
    text='FUTURE' if start not in STARTS else 'N/A' if not np.isfinite(value) else f'{value:+,.1f}' if field in {'real_trading_net_pnl','total_transferred'} else f'{value:.3f}' if field=='balance_sharpe' else f'{value:.2f}'
    if start in OBSERVATION_STARTS:text+=' *'
    rgba=im.cmap(im.norm(value)) if np.isfinite(value) else (1,1,1,1)
    lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
    ax.text(j,i,text,ha='center',va='center',fontsize=7.8,color='white' if lum<.5 else '#17202a')
  fig.colorbar(im,ax=ax,fraction=.035,pad=.02)
 _title(fig,4,'All year x month cells: real trading PnL, E drawdown / Sharpe, funding\n* = observation; grey 2026 November is future; undefined Sharpe is N/A',reviewed)
 _footer(fig,'Funding consumed is capital moved, not trading profit; no promotion voting or common-window ranking.');fig.tight_layout(rect=[.01,.09,.995,.91],h_pad=2);return fig


def _table(ax,rows,columns,title,widths=None,size=7.3):
 ax.axis('off');t=ax.table(cellText=rows,colLabels=columns,loc='center',cellLoc='center',colWidths=widths);t.auto_set_font_size(False);t.set_fontsize(size);t.scale(1,1.65);ax.set_title(title,fontsize=10,fontweight='bold')


def _overview(si,reviewed):
 fig=_figure((16,13.3));axes=fig.subplots(3,2)
 ax=axes[0,0];x=np.arange(5)
 for k,obs in enumerate((False,True)):
  counts=[int(((si.cohort_month==m)&si.observation_only.eq(obs)&si.real_trading_net_pnl.lt(0)).sum()) for m in MONTHS]
  bars=ax.bar(x+(k-.5)*.33,counts,.33,color='#2168ad' if not obs else '#bd7d24',label='Mature' if not obs else 'Observation')
  for bar,n in zip(bars,counts):ax.text(bar.get_x()+bar.get_width()/2,n+.12,str(n),ha='center',fontsize=8)
 ax.set_xticks(x,[MONTH_NAMES[m][:3] for m in MONTHS]);ax.set_ylabel('Windows with real trading PnL < 0');ax.set_title('Actual loss windows: mature and observation separate',fontsize=10,fontweight='bold');ax.set_ylim(0,12.5);ax.legend(frameon=False,fontsize=8);_decorate(ax)
 ax=axes[0,1]
 for i,month in enumerate(MONTHS):
  for obs in (False,True):
   q=si.loc[si.cohort_month.eq(month)&si.observation_only.eq(obs)];values=q.total_transferred.to_numpy(float)/1000
   ax.scatter(i+np.linspace(-.12,.12,len(q)),values,color=MONTH_COLORS[month],marker='*' if obs else 'o',s=80 if obs else 20,edgecolors='black' if obs else 'none',linewidths=.4)
 ax.axhline(150,color='#8593a6',ls=':',lw=1);ax.set_xticks(x,[MONTH_NAMES[m][:3] for m in MONTHS]);ax.set_ylabel('Deposits (CNY k)');ax.set_ylim(-5,165);ax.set_title('All 59 funding paths retained; stars = observation',fontsize=10,fontweight='bold');_decorate(ax)
 ax=axes[1,0]
 for k,obs in enumerate((False,True)):
  q=si.loc[si.observation_only.eq(obs)];counts=[int(q.reserve_exhausted.sum()),int(q.nonpositive_trading_equity_days.gt(0).sum()),int(q.trading_margin_over100_days.gt(0).sum())]
  bars=ax.bar(np.arange(3)+(k-.5)*.33,counts,.33,color='#2168ad' if not obs else '#bd7d24',label=f'{"Mature" if not obs else "OBS"} n={len(q)}')
  for bar,n in zip(bars,counts):ax.text(bar.get_x()+bar.get_width()/2,n+.2,str(n),ha='center',fontsize=8)
 ax.set_xticks(range(3),['Reserve exhausted','Any E <= 0','Margin x1.65/E >100%']);ax.set_ylabel('Windows');ax.set_ylim(0,59);ax.set_title('Capital exhaustion, survival and margin pressure',fontsize=10,fontweight='bold');ax.legend(frameon=False,fontsize=8);_decorate(ax)
 rows=[]
 for month in MONTHS:
  m=si.loc[si.cohort_month.eq(month)&~si.observation_only];o=si.loc[si.cohort_month.eq(month)&si.observation_only]
  rows.append([MONTH_NAMES[month],f'{len(m)}/{len(o)}',f'{m.real_trading_net_pnl.min()/1000:+.1f}',f'{m.balance_max_dd_pct.min():.2f}%',f'{m.total_transferred.max()/1000:.1f}'])
 _table(axes[1,1],rows,['Cohort','Mature/OBS n','Mature min PnL k','Mature worst DD','Mature max T k'],'Five month groups: mature summaries; OBS shown below',[.17,.18,.25,.22,.18],7.1)
 rows=[]
 for start in OBSERVATION_STARTS:
  m=si.loc[start];rows.append([start,f'{m.real_trading_net_pnl/1000:+.1f}',f'{m.balance_max_dd_pct:.2f}%',f'{m.balance_sharpe:.3f}' if m.balance_returns_defined else 'N/A',f'{m.total_transferred/1000:.1f}',f'{m.round_profit_factor:.3f}' if pd.notna(m.round_profit_factor) else 'N/A',f'{m.round_payoff_ratio:.3f}' if pd.notna(m.round_payoff_ratio) else 'N/A'])
 _table(axes[2,0],rows,['Start OBS','PnL k','E DD','E Sharpe','T k','PF','Payoff'],'All five <1 year observation windows; undefined ratios N/A',[.22,.15,.13,.14,.1,.13,.13],7.1)
 ax=axes[2,1];ax.axis('off');m=si.loc[~si.observation_only];worst=m.real_trading_net_pnl.idxmin();undefined=int((~si.balance_returns_defined).sum())
 text=f'59 fresh accounts; 54 mature + 5 observation.\nWorst mature real PnL: {worst} / {m.loc[worst,"real_trading_net_pnl"]:,.0f} CNY.\nUndefined E Sharpe: {undefined}/59; displayed N/A.\nMargin ratios exclude E<=0 days, recorded separately.\nZero closed rounds / missing win-loss denominator: PF/payoff N/A.\nNAV uses E only: 150k + real PnL + deposits.\nUntransferred reserve stays outside risk and margin capacity.\nOverlapping histories / zero fees / static margin / capacity limits.\nNo selected winners, OOS independence claim or promotion. NO_PROMOTION.'
 ax.text(.015,.9,text,fontsize=8.2,va='top',linespacing=1.65);ax.set_title('Interpretation and limitations',fontsize=10,fontweight='bold')
 _title(fig,5,'C/R150 funding needs and downside: all mature / observation and month groups\nAccount statistics include cashflows; real trading PnL remains separate',reviewed)
 _footer(fig);fig.tight_layout(rect=[.01,.09,.995,.925],h_pad=3);return fig


def render_five(summary,daily,reviewed=False)->dict[str,Figure]:
 require(type(reviewed) is bool,'explicit_reviewed_boolean');si,curves=validate_inputs(summary,daily);figures={};created=[]
 try:
  fig=_figure((14.5,11.3));created.append(fig);nav,dd,fund=fig.subplots(3,1,sharex=True,gridspec_kw={'height_ratios':[2,1,1]});g=curves['2015-01-01']
  nav.plot(g.plot_date,g.account_nav,color='#2168ad',lw=1.4,label='C_R150 account NAV');nav.set_ylabel('E account NAV / 150k');nav.legend(frameon=False,fontsize=8)
  dd.plot(g.plot_date,g.balance_drawdown_pct,color='#be3e55',lw=1.1);dd.set_ylabel('E drawdown (%)')
  fund.plot(g.plot_date,g.cumulative_transfer/1000,color='#2168ad',label='Cumulative deposits');fund.plot(g.plot_date,g.reserve_balance/1000,color='#7c8b9d',ls='--',label='External reserve remaining');fund.set_ylabel('Funding / reserve (CNY k)');fund.legend(frameon=False,fontsize=8,ncol=2);fund.set_xlabel('Exchange trading date')
  for ax in (nav,dd,fund):_decorate(ax)
  _title(fig,1,'Full 2015-01-01 start / actual 2015-01-05 through 2026-10-30\nE NAV and drawdown above; internal funding flow and isolated reserve below',reviewed);_footer(fig);fig.tight_layout(rect=[.01,.1,.995,.92]);figures[FIGURE_NAMES[0]]=fig
  for name,builder,args in [(FIGURE_NAMES[1],_cohort_curves,(curves,reviewed)),(FIGURE_NAMES[2],_year_curves,(curves,reviewed)),(FIGURE_NAMES[3],_matrices,(si,reviewed)),(FIGURE_NAMES[4],_overview,(si,reviewed))]:
   fig=builder(*args);created.append(fig);figures[name]=fig
  return figures
 except Exception:
  for fig in created:fig.clear()
  raise
