"""Pure Stage009 five-figure renderer; no file publication or financial engine.

All four variants use total initial wealth CNY300000. Input completeness and
account bridges are validated before allocating any figures. Independent source,
execution and receipt acceptance remains the caller's responsibility.
"""
import math
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import dates as mdates

STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
CUTOFF='2026-10-29'
EXPECTED_DAILY_POINTS=141996
TOTAL_INITIAL=300000.
RESERVE_INITIAL=150000.
FIGURE_NAMES=('01_full_2015_nav_drawdown.png','02_january_starts_nav.png','03_june_starts_nav.png','04_reserve_effect_heatmaps.png','05_cohort_reserve_summary.png')
VARIANTS=('A_R','A_idle','C_R','C_idle')
COLORS={'A_R':'#2467a6','A_idle':'#8b929b','C_R':'#b4234a','C_idle':'#d79532'}
LABELS={'A_R':'A reserve | no price gate','A_idle':'A idle +150k','C_R':'C reserve | short bottom20','C_idle':'C idle +150k'}
SUMMARY_FIELDS={'start','variant','arm','mode','actual_start','trading_days','vote_eligible','observation_only','end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count','total_transferred','reserve_end_balance','trading_end_equity','nonpositive_total_equity_days','nonpositive_trading_equity_days'}
PAIR_FIELDS={'start','arm','cohort','vote_eligible','observation_only','equity_gate','dd_gate','sharpe_gate','three_gate_pass'}
DAILY_FIELDS={'start','variant','date','total_account_equity','trading_account_equity','reserve_balance','cumulative_transfer','net_pnl','nav','drawdown_pct'}

def _require(value,label):
 if not value:raise ValueError('stage009_plots:'+label)

def _bool(value):
 if isinstance(value,(bool,np.bool_)):return bool(value)
 if value=='True':return True
 if value=='False':return False
 raise ValueError('stage009_plots:explicit_boolean_required')

def _near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)

def _cmp(candidate,control):
 return 0 if math.isclose(float(candidate),float(control),rel_tol=1e-10,abs_tol=1e-6) else (1 if candidate>control else -1)

def _eligible(start):return start!='2026-01-01'

def _dates(values):
 parsed=pd.to_datetime(values,errors='raise')
 _require(not parsed.isna().any(),'missing_date')
 return parsed.dt.strftime('%Y-%m-%d')

def _sharpe(equity):
 previous=np.r_[TOTAL_INITIAL,equity[:-1]]
 returns=np.divide(equity-previous,previous,out=np.full_like(equity,np.nan),where=previous!=0)
 if not np.isfinite(returns).all() or len(returns)<2:return 0.
 std=float(np.std(returns,ddof=1))
 return float(np.mean(returns)/std*np.sqrt(252)) if std>0 else 0.

def validate_inputs(summary,paired,daily):
 """Return normalized copies indexed by identity, after complete-scope checks."""
 for name,frame,fields in [('summary',summary,SUMMARY_FIELDS),('paired',paired,PAIR_FIELDS),('daily',daily,DAILY_FIELDS)]:
  _require(isinstance(frame,pd.DataFrame) and fields.issubset(frame.columns),'missing_'+name+'_columns')
 s=summary.copy();p=paired.copy();d=daily.copy()
 _require('actual_end' in s or 'end' in s,'summary_actual_end_required')
 if 'actual_end' not in s:s['actual_end']=s['end']
 elif 'end' in s:_require((_dates(s.actual_end)==_dates(s.end)).all(),'conflicting_summary_end')
 expected={(start,variant) for start in STARTS for variant in VARIANTS}
 keys=list(zip(s.start,s.variant));_require(len(keys)==92 and len(set(keys))==92 and set(keys)==expected,'exact92_summary')
 pairs=list(zip(p.start,p.arm));_require(len(pairs)==46 and len(set(pairs))==46 and set(pairs)=={(x,a) for x in STARTS for a in ['A','C']},'exact46_pairs')
 _require(len(d)==EXPECTED_DAILY_POINTS and not d.duplicated(['start','variant','date']).any(),'complete141996_unique_daily_points')
 _require(set(zip(d.start,d.variant))==expected,'exact92_daily_groups')
 for frame in [s,p]:
  for field in ['vote_eligible','observation_only']:frame[field]=frame[field].map(_bool)
 for field in ['equity_gate','dd_gate','sharpe_gate','three_gate_pass']:p[field]=p[field].map(_bool)
 if 'eligible' in p:_require((p.eligible.map(_bool)==p.vote_eligible).all(),'conflicting_pair_eligible_alias')
 s['actual_start']=_dates(s.actual_start);s['actual_end']=_dates(s.actual_end);d['date']=_dates(d.date)
 _require(not d.duplicated(['start','variant','date']).any(),'duplicate_normalized_daily_date')
 snumeric=['trading_days','end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count','total_transferred','reserve_end_balance','trading_end_equity','nonpositive_total_equity_days','nonpositive_trading_equity_days']
 dnumeric=list(DAILY_FIELDS-{'start','variant','date'})
 for frame,fields in [(s,snumeric),(d,dnumeric)]:
  for field in fields:
   frame[field]=pd.to_numeric(frame[field],errors='raise');_require(np.isfinite(frame[field].to_numpy(float)).all(),'nonfinite_'+field)
 for field in ['trading_days','modeled_fill_count','nonpositive_total_equity_days','nonpositive_trading_equity_days']:
  _require((s[field]>=0).all() and (s[field]==np.floor(s[field])).all(),'nonnegative_integer_'+field)
 _require((s.trading_days>0).all() and (s.total_slippage>=0).all(),'positive_window_nonnegative_cost')
 si=s.set_index(['start','variant']);pi=p.set_index(['start','arm']);curves={};calendar={}
 for key,g0 in d.groupby(['start','variant'],sort=False):
  start,variant=key;m=si.loc[key];g=g0.sort_values('date').reset_index(drop=True);arm=variant[0];mode='reserve' if variant.endswith('_R') else 'idle';eligible=_eligible(start)
  _require(m.arm==arm and m['mode']==mode,'variant_arm_mode_identity')
  _require(bool(m.vote_eligible)==eligible and bool(m.observation_only)==(not eligible),'summary_observation_scope')
  _require(m.actual_end==CUTOFF and start<=m.actual_start<=CUTOFF,'exact_summary_window')
  _require(len(g)==int(m.trading_days) and g.date.iloc[0]==m.actual_start and g.date.iloc[-1]==CUTOFF,'complete_daily_endpoints_count')
  dates=tuple(g.date)
  if start in calendar:_require(calendar[start]==dates,'same_start_four_variant_calendar')
  else:calendar[start]=dates
  e=g.total_account_equity.to_numpy(float);r=g.reserve_balance.to_numpy(float);t=g.cumulative_transfer.to_numpy(float);trading=g.trading_account_equity.to_numpy(float)
  _require(_near(e,trading+r) and _near(r+t,RESERVE_INITIAL),'bucket_conservation')
  _require((r>=-1e-6).all() and (r<=RESERVE_INITIAL+1e-6).all() and (np.diff(r)<=1e-6).all() and (t>=-1e-6).all() and (np.diff(t)>=-1e-6).all(),'isolated_monotone_reserve')
  if mode=='idle':_require(_near(r,RESERVE_INITIAL) and _near(t,0.),'idle_reserve_never_spent')
  _require(_near(e,TOTAL_INITIAL+g.net_pnl.cumsum().to_numpy(float)),'transfer_not_profit')
  _require(_near(e[0],TOTAL_INITIAL) and _near(g.net_pnl.iloc[0],0.),'fresh_total_account_start')
  drawdown=(e/np.maximum.accumulate(np.r_[TOTAL_INITIAL,e])[1:]-1)*100
  _require(_near(g.nav.to_numpy(float),e/TOTAL_INITIAL) and _near(g.drawdown_pct.to_numpy(float),drawdown),'NAV300k_and_initial_highwater_DD')
  fields=dict(end_equity=e[-1],total_return_pct=(e[-1]/TOTAL_INITIAL-1)*100,max_dd_pct=float(drawdown.min()),sharpe=_sharpe(e),total_transferred=t[-1],reserve_end_balance=r[-1],trading_end_equity=trading[-1],nonpositive_total_equity_days=int((e<=0).sum()),nonpositive_trading_equity_days=int((trading<=0).sum()))
  for field,value in fields.items():_require(_near(float(m[field]),value),'summary_daily_metric_'+field)
  g['plot_date']=pd.to_datetime(g.date);curves[key]=g
 for (start,arm),row in pi.iterrows():
  eligible=_eligible(start);cohort='January' if start[5:7]=='01' else 'June'
  _require(bool(row.vote_eligible)==eligible and bool(row.observation_only)==(not eligible) and row.cohort==cohort,'paired_observation_cohort_scope')
  a=si.loc[(start,arm+'_idle')];c=si.loc[(start,arm+'_R')]
  gates=dict(equity_gate=_cmp(c.end_equity,a.end_equity)>0,dd_gate=_cmp(c.max_dd_pct,a.max_dd_pct)>=0,sharpe_gate=_cmp(c.sharpe,a.sharpe)>=0)
  for field,value in gates.items():_require(bool(row[field])==value,'paired_gate_'+field)
  _require(bool(row.three_gate_pass)==all(gates.values()),'paired_three_gate')
 _require(int(p.vote_eligible.sum())==44 and int(p.observation_only.sum())==2,'22_mature_pairs_per_arm_two_observations')
 return si,pi,curves

def _figure(size):
 fig=Figure(figsize=size,facecolor='white');FigureCanvasAgg(fig);return fig

def _decorate(ax):
 ax.grid(alpha=.16);ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8)

def _title(fig,index,description,reviewed):
 state='REVIEWED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING'
 fig.suptitle(f'STAGE009 {index}/5 | {state} | NO PROMOTION\n'+description,fontsize=11,fontweight='bold')

def _curve(ax,frame,variant,field='nav'):
 ax.plot(frame.plot_date,frame[field],color=COLORS[variant],lw=1.5 if variant.endswith('_R') else 1.1,ls='-' if variant.endswith('_R') else '--',label=LABELS[variant],alpha=1 if variant.endswith('_R') else .9)

def _footer(fig,text):fig.text(.035,.014,text,fontsize=8,color='#596579',va='bottom')

def _legend(fig,ax,y):
 handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,ncol=4,frameon=False,fontsize=8,loc='upper center',bbox_to_anchor=(.5,y))

def _grid(si,curves,cohort,reviewed):
 starts=[s for s in STARTS if (s[5:7]=='01')==(cohort=='January')];index=2 if cohort=='January' else 3;fig=_figure((15.2,11.5));axes=fig.subplots(4,3)
 for i,start in enumerate(starts):
  ax=axes.flat[i];meta=si.loc[(start,'A_R')]
  for variant in VARIANTS:_curve(ax,curves[(start,variant)],variant)
  ax.axhline(1.,color='#c4c8cf',lw=.6,ls=':');observation=' * OBS' if not _eligible(start) else ''
  ax.set_title(f'{start}{observation} -> {CUTOFF}',fontsize=8.5,fontweight='bold');ax.text(.02,.97,f'actual {meta.actual_start} | {int(meta.trading_days)} trading days',transform=ax.transAxes,fontsize=6.8,va='top',color='#596579')
  span=(pd.Timestamp(CUTOFF)-pd.Timestamp(start)).days
  ax.xaxis.set_major_locator(mdates.YearLocator(base=4 if span>365*6 else (2 if span>365*3 else 1)) if span>365 else mdates.MonthLocator(bymonth=[1,4,7,10]));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y' if span>365 else '%b%y'));_decorate(ax);ax.tick_params(labelsize=7)
  if i%3==0:ax.set_ylabel('Total NAV / 300k',fontsize=8)
 for i in range(len(starts),12):axes.flat[i].set_visible(False)
 _title(fig,index,f'{cohort} independent starts -> same cutoff | four variants, CNY300,000 each\nFresh trading/reserve accounts per start; NOT fixed1/2/3-year slices',reviewed)
 _legend(fig,axes.flat[0],.917)
 _footer(fig,'* 2026Jan is <1year: displayed, NO VOTE. Mature: January11 + June11 per arm. Overlapping windows are not independent OOS samples.\nIdle = Stage008 trading ledger + permanently idle150k. Reserve = initial trading150k + isolated150k, transferred only at valid new signals.')
 fig.tight_layout(rect=[.01,.055,.995,.955]);return fig

def _heatmaps(si,reviewed):
 fig=_figure((15.,11.8));axes=fig.subplots(2,3);metrics=[('total_return_pct','Total return delta (pp)'),('max_dd_pct','Max drawdown delta (pp)'),('sharpe','Sharpe delta')];labels=[s+(' * OBS' if not _eligible(s) else '') for s in STARTS]
 values={(arm,field):np.array([si.loc[(s,arm+'_R'),field]-si.loc[(s,arm+'_idle'),field] for s in STARTS],float) for arm in ['A','C'] for field,_ in metrics}
 for i,arm in enumerate(['A','C']):
  for j,(field,label) in enumerate(metrics):
   ax=axes[i,j];v=values[(arm,field)].reshape(-1,1);bound=max(float(np.max(np.abs(np.r_[values[('A',field)],values[('C',field)]]))),.001);im=ax.imshow(v,aspect='auto',cmap='RdYlGn',vmin=-bound,vmax=bound)
   ax.set_title(f'{arm} reserve - {arm} idle | {label}',fontsize=10);ax.set_xticks([]);ax.set_yticks(np.arange(23),labels,fontsize=7)
   for k,value in enumerate(v[:,0]):
    rgba=im.cmap(im.norm(value));lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2];ax.text(0,k,f'{value:+.3f}' if field=='sharpe' else f'{value:+.2f}',ha='center',va='center',fontsize=7,color='white' if lum<.5 else '#17202a')
   fig.colorbar(im,ax=ax,fraction=.045,pad=.025)
 _title(fig,4,'Reserve effect relative to same-capital idle control | all23 starts\nPositive = reserve better for that metric; A/C share a scale within each metric',reviewed)
 _footer(fig,'* 2026Jan observation only, excluded from mature votes. Different window lengths: no mean total-return forecast.\nBoth controls and candidates start with total300k; transfers are internal capital flows, not profit or standalone alpha.')
 fig.tight_layout(rect=[.005,.055,.995,.99]);return fig

def _cohort_figure(si,pi,reviewed):
 fig=_figure((15.2,10.8));axes=fig.subplots(2,2);groups=[(a,c) for a in ['A','C'] for c in ['January','June']];x=np.arange(4);width=.18
 gate_fields=[('equity_gate','Equity strictly higher','#2467a6'),('dd_gate','DD no worse','#719b89'),('sharpe_gate','Sharpe no lower','#9571aa'),('three_gate_pass','All3 gates','#242e3a')]
 for offset,(field,label,color) in enumerate(gate_fields):
  counts=[]
  for arm,cohort in groups:
   rows=pi.reset_index();rows=rows.loc[(rows.arm==arm)&(rows.cohort==cohort)&rows.vote_eligible];counts.append(int(rows[field].sum()))
  bars=axes[0,0].bar(x+(offset-1.5)*width,counts,width,label=label,color=color)
  for b,n in zip(bars,counts):axes[0,0].text(b.get_x()+b.get_width()/2,n+.12,str(n),ha='center',fontsize=7)
 axes[0,0].set_xticks(x,[f'{a} {c}\nN=11' for a,c in groups]);axes[0,0].set_ylim(0,12.8);axes[0,0].set_ylabel('Mature paired passes');axes[0,0].legend(frameon=False,fontsize=7.5,ncol=2);axes[0,0].set_title('January / June complete windows: no observation votes',fontsize=10);_decorate(axes[0,0])
 ax=axes[0,1];cohorts=['January','June'];positions=np.arange(2)
 for i,variant in enumerate(VARIANTS):
  counts=[]
  for cohort in cohorts:
   starts=[s for s in STARTS if _eligible(s) and (s[5:7]=='01')==(cohort=='January')];counts.append(sum(si.loc[(s,variant),'total_return_pct']<0 for s in starts))
  bars=ax.bar(positions+(i-1.5)*width,counts,width,color=COLORS[variant],label=variant)
  for b,n in zip(bars,counts):ax.text(b.get_x()+b.get_width()/2,n+.10,str(n),ha='center',fontsize=7)
 ax.set_xticks(positions,['January (11)','June (11)']);ax.set_ylim(0,12.8);ax.set_ylabel('Negative-total-return windows');ax.set_title('Same300k principal: negative mature windows',fontsize=10);ax.legend(frameon=False,fontsize=8,ncol=4);_decorate(ax)
 ax=axes[1,0];consumption=[]
 for arm,cohort in groups:
  starts=[s for s in STARTS if _eligible(s) and (s[5:7]=='01')==(cohort=='January')];consumption.append([si.loc[(s,arm+'_R'),'total_transferred']/1000 for s in starts])
 boxes=ax.boxplot(consumption,positions=np.arange(1,5),patch_artist=True,widths=.5,showfliers=False)
 for i,patch in enumerate(boxes['boxes']):patch.set_facecolor(COLORS[groups[i][0]+'_R']);patch.set_alpha(.25)
 for i,points in enumerate(consumption):ax.scatter(np.full(len(points),i+1)+np.linspace(-.12,.12,len(points)),points,s=17,color=COLORS[groups[i][0]+'_R'],alpha=.85,zorder=3)
 ax.set_xticks(np.arange(1,5),[f'{a} {c}\nN=11' for a,c in groups]);ax.set_ylim(-5,160);ax.set_ylabel('Reserve transferred (CNY thousands)');ax.set_title('Mature reserve consumption: every window retained',fontsize=10);_decorate(ax)
 ax=axes[1,1];ax.axis('off');rows=[]
 for variant in VARIANTS:
  m=si.loc[('2026-01-01',variant)];rows.append([variant,f'{m.total_return_pct:+.2f}%',f'{m.max_dd_pct:.2f}%',f'{m.sharpe:.3f}',f'{m.total_transferred/1000:.1f}',f'{m.reserve_end_balance/1000:.1f}'])
 table=ax.table(cellText=rows,colLabels=['Variant','Return','DD','Sharpe','Used k','Left k'],loc='center',cellLoc='center');table.auto_set_font_size(False);table.set_fontsize(8);table.scale(1.,1.5)
 ax.set_title('2026-01-01 <1year OBSERVATION: NO VOTE',fontsize=10,fontweight='bold');ax.text(.01,.12,'22 mature windows per arm = January11 + June11.\nAll3: equity strictly higher, DD no worse, Sharpe no lower.\nTransfer frequency/amount reflects risk exposure, not alpha.',transform=ax.transAxes,fontsize=8,color='#596579',va='top')
 _title(fig,5,'Reserve vs idle | complete-window cohort summary and capital use\nEach arm:22 mature comparisons + one observation; total92 variant-windows',reviewed)
 _footer(fig,'Capital300k includes unused reserve: it is not free money. No fund replenishment, interest, extra alpha claim, rescue tuning or promotion.\nZero commission, static exchange margin x1.65 and inherited execution/data limits remain; no live/capacity qualification.')
 fig.tight_layout(rect=[.01,.06,.995,.99]);return fig

def render_five(summary:pd.DataFrame,paired:pd.DataFrame,daily:pd.DataFrame,reviewed=False)->dict[str,Figure]:
 """Return five unsaved Figures in fixed order; caller owns save/close/manifest."""
 _require(type(reviewed) is bool,'explicit_reviewed_boolean')
 si,pi,curves=validate_inputs(summary,paired,daily)
 result={};created=[]
 try:
  fig=_figure((13.8,8.));created.append(fig);a,b=fig.subplots(2,1,sharex=True,gridspec_kw={'height_ratios':[2,1]})
  for variant in VARIANTS:_curve(a,curves[('2015-01-01',variant)],variant);_curve(b,curves[('2015-01-01',variant)],variant,'drawdown_pct')
  a.axhline(1.,color='#bac0c8',ls=':',lw=.7);b.axhline(0.,color='#bac0c8',ls=':',lw=.7);a.set_ylabel('Total NAV = wealth / 300,000');b.set_ylabel('Drawdown (%)');b.set_xlabel('Exchange trading date');a.legend(frameon=False,fontsize=8,ncol=2)
  for ax in [a,b]:_decorate(ax)
  actual=si.loc[('2015-01-01','A_R'),'actual_start'];_title(fig,1,f'Full independent start2015-01-01 / actual{actual} -> {CUTOFF}\nFour variants, same CNY300,000 total initial wealth | original19, no addon',reviewed)
  _footer(fig,'A_R blue / A_idle gray | C_R red / C_idle orange. Reserve funds only valid new signals; idle150k remains isolated throughout.\nInternal transfers never enter profit. Linear NAV retains zero/negative wealth if present; inherited daily next-open execution.')
  fig.tight_layout(rect=[.01,.065,.995,.99]);result[FIGURE_NAMES[0]]=fig
  for cohort,name in [('January',FIGURE_NAMES[1]),('June',FIGURE_NAMES[2])]:
   fig=_grid(si,curves,cohort,reviewed);created.append(fig);result[name]=fig
  fig=_heatmaps(si,reviewed);created.append(fig);result[FIGURE_NAMES[3]]=fig
  fig=_cohort_figure(si,pi,reviewed);created.append(fig);result[FIGURE_NAMES[4]]=fig
  return result
 except Exception:
  for fig in created:fig.clear()
  raise
