"""Pure date-aware N002/P001 report after fixed real-roll-tail data repair; true historical class and normalized-data identity."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os
import numpy as np
import pandas as pd
import stage020_build_artifacts_v2 as prior
base=prior.base;FLAGS=prior.FLAGS;POOL=prior.POOL;CAPITAL=prior.CAPITAL;_gate=prior._gate
def load_history(path,arm,calendar):
    START="2015-01-01" if arm=="N" else "2020-01-01";END="2026-10-23"
    if arm not in {"N","P"}:raise ValueError("unknown_history_arm")
    path=Path(path).resolve();sources={}
    def read(name):
        p=path/name;sources[str(p)]=base.sha(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal,metrics,effective,settings,preflight=[read(n) for n in ['terminal.json','metrics.json','effective_parameters.json','actual_strategy_settings.json','preflight.json']]
    if terminal.get('error') or terminal.get('status') not in {'completed_pending_independent_review','rejected_execution_bar_open'}:raise ValueError('complete_M_ledger_required')
    if len(settings)!=1 or settings[0]['strategy_class']!='HistoricalSafetyStrategy' or metrics.get('arm')!=arm or metrics.get('result_scope')!='weekly_history_single_sided_close_oi_original19':raise ValueError('M_identity_mismatch')
    actual=settings[0]['actual']
    if any(actual.get(k) is not False for k in FLAGS):raise ValueError('M_disabled_flags_mismatch')
    if tuple(actual.get(k) for k in ['ma_short','ma_mid','ma_long'])!=(5,10,20) or actual.get('research_exact_array_manager_size')!=41:raise ValueError('M_weekly_indicator_contract_mismatch')
    if set(preflight.get('universe_products',[]))!=POOL or preflight.get('ready_need')!=21 or preflight.get('storage_capacity')!=41:raise ValueError('M_pool_or_warmup_mismatch')
    if preflight.get('execution_model')!=base.EXECUTION_MODEL or preflight.get('minute_quote_confirmed') is not False:raise ValueError('M_bar_open_model_mismatch')
    for value in [actual.get('capital_base'),settings[0]['engine_capital'],effective['spec']['capital']['account_capital'],effective['spec']['capital']['c3_capital']]:base.require_close(value,CAPITAL,'M_capital')
    macd=read('macd_acceptance.json');quality=read('bar_open_acceptance.json');ai_proof=read('ai_selection_acceptance.json')
    _gate(macd,'stage014_macd_disabled_acceptance_v1',dict(accepted=True,strategy_class='HistoricalSafetyStrategy',macd_disabled=True,macd_calculation_attempts=0,candidate_case3_count=0,unknown_candidate_signals=0,rollover_macd_hist_non_null_count=0),'MACD')
    _gate(ai_proof,'stage012_ai_selection_off_v1',dict(accepted=True,model_load_attempts=0,runtime_loaded=False,nonzero_ai_candidate_fields=0),'AI')
    if quality.get('schema')!='stage011_daily_bar_open_acceptance_v1' or quality.get('verdict') not in {'PASS_DECLARED_BAR_OPEN_MODEL','REJECT_BAR_OPEN_MODEL'} or type(quality.get('accepted')) is not bool:raise ValueError('M_daily_open_acceptance_required')
    short=read('short_case2_acceptance.json')
    _gate(short,'stage018_short_case2_acceptance_v1',dict(accepted=True,strategy_class='HistoricalSafetyStrategy',accepted_signals=['short_case1a','short_case2'],short_case2_gate_allowed=True,short_case1a_gate_allowed=True,case3_gate_allowed=False,short_signal_rejected_count=0,MA_decision_periods=[5,10,20],MA40_decision_enabled=False),'short_case2')
    candidates=read('entry_candidates.csv');allowed={'long_case1a','long_case2','short_case1a','short_case2'}
    if not set(candidates.signal).issubset(allowed) or candidates.skip_reason.eq('short_signal_rejected').any():raise ValueError('M_short_candidate_gate_mismatch')
    for key,value in [('short_case2_candidates',int(candidates.signal.eq('short_case2').sum())),('short_case2_opened',int((candidates.signal.eq('short_case2')&candidates.candidate_status.eq('opened')).sum()))]:base.require_close(short[key],value,'M_short_plan_count:'+key)
    if candidates.skip_reason.eq('concurrent_limit').any() or any(set(pd.to_numeric(candidates[k],errors='raise').unique())!={19} for k in ['max_concurrent_positions','effective_max_concurrent_positions']):raise ValueError('M_position_cap_candidates_mismatch')
    cap=read('no_position_cap_acceptance.json')
    _gate(cap,'stage020_no_position_cap_acceptance_v1',dict(accepted=True,strategy_class='HistoricalSafetyStrategy',universe_product_count=19,original_position_limit=4,candidate_effective_limit=19,configured_position_limit=19,candidate_effective_limit_values=[19],candidate_configured_limit_values=[19],concurrent_limit=0,portfolio_env_gate_enabled=False,implementation='universe_capacity_19_nonbinding_for_fixed_original19',MA40_decision_enabled=False,MA_decision_periods=[5,10,20]),'position_cap')
    if actual.get('max_concurrent_positions')!=19 or settings[0]['setting'].get('max_concurrent_positions')!=19:raise ValueError('M_position_cap_setting_mismatch')
    data_quality=read('data_quality.json');reads=read('data_read_counts.json')
    if any(data_quality.get(k) for k in ['held_or_traded_daily_gaps','held_or_traded_zero_volume','captured_bar_failures']) or any(reads.get(k)!=0 for k in ['minute_reads','proxy_reads','ai_selection_model_load_attempts']):raise ValueError('M_data_quality_or_reads_failed')
    if quality.get('modeled_clock_mismatch_count',0)!=0:raise ValueError('M_modeled_clock_mismatch')
    daily,trades,positions,clock=[read(n) for n in ['daily.csv','trades.csv','positions.csv','execution_clock.csv']]
    if trades.empty:trades=base.ordered_fills(trades,clock)
    daily['date']=pd.to_datetime(daily.date).dt.normalize();daily=daily.sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.duplicated().any() or not daily.date.between(START,END).all() or daily.date.iloc[0]!=pd.Timestamp(calendar[0]) or daily.date.iloc[-1]!=pd.Timestamp(END):raise ValueError('M_full_window_required')
    if calendar is not None and daily.date.dt.strftime('%Y-%m-%d').tolist()!=list(calendar):raise ValueError('M_full_calendar_required')
    if not np.isfinite(daily[['account_equity','net_pnl','slippage','commission','trade_count']].to_numpy(float)).all():raise ValueError('M_nonfinite_daily')
    base.require_close(np.abs(CAPITAL+daily.net_pnl.cumsum()-daily.account_equity).max(),0.,'M_daily_conservation')
    positions['date']=pd.to_datetime(positions.date).dt.normalize();positions=positions.loc[positions.date.between(START,END)].copy()
    days=pd.to_datetime(trades['trading_date'] if 'trading_date' in trades else trades.date)
    if not days.between(START,END).all():raise ValueError('M_fill_outside_window')
    for frame in [trades,positions]:frame['product_vt_symbol']=frame.vt_symbol.map(lambda s:base.native_product(s,POOL))
    nonzero=positions.loc[positions.end_pos.ne(0)]
    max_daily=int(nonzero.groupby('date').product_vt_symbol.nunique().max()) if len(nonzero) else 0
    if max_daily>19 or cap.get('max_daily_product_positions')!=max_daily:raise ValueError('M_position_cap_observed_positions_mismatch')
    last=positions.loc[positions.date.eq(END)]
    if last.vt_symbol.duplicated().any():raise ValueError('M_duplicate_terminal_position')
    segments,fifo=base.fifo_segments(trades,effective,clock,dict(zip(last.vt_symbol,last.close_price)))
    segments['product_vt_symbol']=segments.vt_symbol.map(lambda s:base.native_product(s,POOL)) if len(segments) else pd.Series(dtype=str)
    actual_pos=last.set_index('vt_symbol').end_pos.astype(float).to_dict()
    for symbol in set(actual_pos)|set(fifo['open_net_positions']):base.require_close(actual_pos.get(symbol,0),fifo['open_net_positions'].get(symbol,0),'M_terminal_position')
    curve=base.curve_metrics(daily)
    for key in ['end_equity','total_return_pct','max_dd_pct']:base.require_close(curve[key],metrics[key],'M_source_'+key)
    if curve['sharpe'] is not None:base.require_close(curve['sharpe'],metrics['sharpe'],'M_source_sharpe')
    for count in [curve['modeled_fill_count'],metrics['total_trade_count'],quality['trade_count']]:base.require_close(count,len(trades),'M_fill_count')
    base.require_close(fifo['total_slippage'],daily.slippage.sum(),'M_slippage');base.require_close(fifo['total_commission'],daily.commission.sum(),'M_commission')
    base.require_close(daily.commission.sum(),0.,'M_zero_fee');base.require_close(fifo['ledger_net_pnl'],curve['end_equity']-CAPITAL,'M_FIFO_conservation');base.require_close(positions.net_pnl.sum(),daily.net_pnl.sum(),'M_product_conservation')
    postflight=read('postflight.json')
    if postflight.get('inputs_unchanged') is not True:raise ValueError('M_inputs_changed')
    safety=read('historical_safety_acceptance.json')
    _gate(safety,'stage023_historical_safety_acceptance_v1',dict(accepted=True,arm=arm,strategy_class='HistoricalSafetyStrategy',historical_safety_enabled=True,requested_start=START,requested_end=END,actual_calendar_matches=True,readiness_calendar_matches=True,epoch_failure_count=0,quantity_units='single_sided_volume_close_oi',strict_next_trading_day_open=True),'history_safety')
    im=read('input_manifest.json')
    if any(base.sha(p)!=digest for p,digest in im.items()):raise ValueError('history_inputs_changed_live:'+arm)
    curve.update(pool_product_count=19,modeled_traded_product_count=int(trades.product_vt_symbol.nunique()),modeled_traded_products=sorted(trades.product_vt_symbol.unique()),modeled_fill_volume=float(trades.volume.sum()))
    return dict(path=str(path),arm=arm,daily=daily,trades=trades,positions=positions,segments=segments,fifo_stats=fifo,metrics=curve,effective=effective,settings=settings,sources=sources,bar_open_acceptance=quality,macd_acceptance=macd,ai_selection_acceptance=ai_proof,short_case2_acceptance=short,no_position_cap_acceptance=cap)

def risk_summary(ledger):
    d=ledger['daily']; st=ledger['settings'][0]['actual']
    multiplier=float(st['stage830_broker_margin_multiplier'])
    if multiplier!=float(st['forced_margin_deleverage_broker_multiplier']):raise ValueError('margin_multiplier_disagreement')
    raw=d.total_margin_exact/d.account_equity*100
    actual=raw*multiplier
    base.require_close((d.broker10_total_margin_exact-d.total_margin_exact*1.1).abs().max(),0.,'legacy_broker10_is_110pct')
    p=ledger['positions'].copy();p['product']=p.vt_symbol.map(lambda x:base.native_product(x,POOL))
    count=p.loc[p.end_pos.ne(0)].groupby('date').product.nunique().reindex(d.date,fill_value=0)
    fills=base.ordered_fills(ledger['trades'],pd.read_csv(Path(ledger['path'])/'execution_clock.csv'))
    inv={};maximum=0;max_event=None
    for row in fills.to_dict('records'):
        sign=base.math_report._direction(row['direction']);sym=row['vt_symbol'];inv[sym]=inv.get(sym,0)+sign*float(row['volume'])
        active={base.native_product(k,POOL) for k,v in inv.items() if abs(v)>1e-8}
        if len(active)>maximum:maximum=len(active);max_event=dict(trade_id=str(row['trade_id']),execution_datetime=str(row['execution_datetime']))
    c=pd.read_csv(Path(ledger['path'])/'entry_candidates.csv');cleanup=pd.read_csv(Path(ledger['path'])/'historical_target_cleanup.csv')
    return dict(broker_margin_multiplier=multiplier,raw_margin_to_equity_avg_pct=float(raw.mean()),raw_margin_to_equity_max_pct=float(raw.max()),actual_margin_to_equity_avg_pct=float(actual.mean()),actual_margin_to_equity_max_pct=float(actual.max()),actual_margin_over100_days=int(actual.gt(100).sum()),actual_margin_peak_day=d.loc[actual.idxmax(),'date'].strftime('%Y-%m-%d'),legacy_broker10_multiplier=1.1,max_daily_close_products=int(count.max()),daily_close_over4_days=int(count.gt(4).sum()),max_after_fill_products=maximum,max_after_fill_first_event=max_event,entry_candidate_count=len(c),candidate_status_counts=c.candidate_status.value_counts().to_dict(),candidate_skip_counts=c.skip_reason.fillna('').value_counts().to_dict(),historical_target_cleanup_count=len(cleanup),historical_epoch_transitions=len(json.loads((Path(ledger['path'])/'historical_epoch_transitions.json').read_text())))

def plot(ledgers,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(a,b)=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for arm,color,label in [('N','#2467a6','N: 2015 start'),('P','#c36f19','P: 2020 bridge')]:
        d=ledgers[arm]['daily'];a.plot(d.date,d.account_equity,lw=1.4,color=color,label=label)
        peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:];b.plot(d.date,(d.account_equity/peak-1)*100,lw=1.1,color=color)
    a.axhline(CAPITAL,color='#888',lw=.7,ls='--');a.legend(frameon=False);a.set_ylabel('Modeled equity (CNY)');a.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'))
    b.set_ylabel('Drawdown (%)');b.set_xlabel('Trading date')
    for ax in [a,b]:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('OFFLINE RESEARCH / NO PROMOTION\nOriginal19; weekly MA5/10/20; no MA40/MACD/AI/0.5R/C2; no extra 4-position cap\nThrough 2026-10-23; CNY150,000 each; single-sided volume / close OI; daily-open model; zero commission',fontsize=10.5,fontweight='bold')
    fig.tight_layout(rect=[0,0,1,.9]);fig.savefig(path,dpi=170);plt.close(fig)

def build(line,data,review_path):
    line=Path(line).resolve();data=Path(data).resolve();review_path=Path(review_path).resolve()
    review=json.loads(review_path.read_text());paths={arm:line/'outputs'/(arm+('_attempt002' if arm=='N' else '_attempt001')) for arm in ['N','P']}
    if review.get('verdict')!='PASS_OFFLINE_RESEARCH' or review.get('schema')!='stage023_fresh_independent_review_v1':raise ValueError('fresh_independent_review_required')
    for arm in paths:
        if Path(review[arm+'_attempt_path']).resolve()!=paths[arm]:raise ValueError('review_wrong_arm:'+arm)
    art=line/'artifacts';tables=art/'stage026_v2';fig=art/'stage026_v2_history_equity_drawdown.png';base.require_new_outputs([tables,fig]);tables.mkdir(parents=True)
    source={str(Path(__file__).resolve()):base.sha(__file__),str(review_path):base.sha(review_path),str(data/'source_manifest.json'):base.sha(data/'source_manifest.json')}
    calendar=sorted(pd.read_csv(data/'mapping.csv').date.astype(str).unique())
    ledgers={arm:load_history(p,arm,[d for d in calendar if ('2015-01-01' if arm=='N' else '2020-01-01')<=d<='2026-10-23']) for arm,p in paths.items()}
    statuses=dict(performance_classification='REVIEWED_OFFLINE_RESEARCH_NO_PROMOTION',execution_audit_status='PASS_DECLARED_BAR_OPEN_MODEL',qualified_counts_status='OFFLINE_MODEL_ONLY_NO_PRODUCTION_QUALIFICATION')
    arms={};annual=[];segments=[];products=[]
    for arm,r in ledgers.items():
        source.update(r['sources']);risk=risk_summary(r)
        arms[arm]=dict(modeled_metrics=r['metrics'],closed_fifo=r['fifo_stats'],risk=risk,entry_fill_attribution=prior.entry_attribution(r));source.update(r['sources'])
        annual.extend(base.annual_rows(r['daily'],arm,statuses));products.extend(base.product_rows(r,POOL,statuses))
        s=r['segments'].copy();s.insert(0,'arm',arm);segments.append(s)
    m=prior.load_m(line/'outputs/M_attempt001');source.update(m['sources'])
    p=ledgers['P'];common=p['daily'].loc[p['daily'].date.le('2026-10-22')].copy();bridge=base.curve_metrics(common)
    old=m['daily'].set_index('date');new=common.set_index('date')
    if not old.index.equals(new.index):raise ValueError('M_P_bridge_calendar_mismatch')
    difference=new.account_equity-old.account_equity;changed=difference.abs().gt(1e-8)
    bridge.update(old_M_end_equity=m['metrics']['end_equity'],P_minus_M_same_end_equity=bridge['end_equity']-m['metrics']['end_equity'],first_equity_difference=None if not changed.any() else difference[changed].index[0].strftime('%Y-%m-%d'),new_P_20261023_pnl=float(p['daily'].iloc[-1].net_pnl),interpretation='Data normalization and historical safety adaptation jointly differ from M. Different account start paths are not independent marginal alpha.')
    pd.DataFrame(annual).to_csv(tables/'annual.csv',index=False);pd.DataFrame(products).to_csv(tables/'products.csv',index=False);pd.concat(segments,ignore_index=True).to_csv(tables/'closed_fifo_segments.csv',index=False)
    plot(ledgers,fig)
    summary=dict(schema='stage026_history_artifacts_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),arms=arms,bridge=bridge,data_receipt=json.loads((data/'receipt.json').read_text()),decision='PASS_OFFLINE_RESEARCH_NO_PROMOTION',production_qualified=False,promotion_decision='NO_PROMOTION',financial_replays=0,limitations=['Static original19 universe and historical repeated sample; not PIT/OOS proof.','Zero commission, fixed slippage; no quote/depth/capacity qualification.','Unclassified main gaps0;573 proven zero-volume and18 invalid frozen mappings are excluded. This is not complete historical PIT main reconstruction. FU1905 old180 May2018 observation remains isolated.','Canonical volume/closeOI and source authority choice have declared vendor-conflict limitations.','P bridge includes safety cleanup if observed; not a pure start-date or pure data comparison.','Full lifecycle unknown for six observed future contracts is labeled; no invented dates.'],source_files_sha256=source)
    summary['output_files_sha256']={str(p):base.sha(p) for p in [fig,*tables.glob('*.csv')]}
    if any(base.sha(p)!=d for p,d in source.items()):raise ValueError('report_sources_changed')
    (tables/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status='DERIVED_ONLY',outputs=[str(tables),str(fig)])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--line-dir',type=Path,required=True);p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--review-json',type=Path,required=True);a=p.parse_args();build(a.line_dir,a.data_dir,a.review_json)
