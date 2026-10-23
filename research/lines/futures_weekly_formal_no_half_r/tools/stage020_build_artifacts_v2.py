"""Stage020 v2 pure L/M report: runtime portfolio gate is bound by its proof.

The v1 report required an unserialized actual-settings attribute. This copy
removes that display-only assertion; runtime proof False remains mandatory.

No strategy, account replay, model/feature CSV, minute data or downloader runs.
Candidate opened flags describe plans; actual entries are linked by order IDs.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,re,sys,tempfile
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage018_build_artifacts as prior
base=prior.base;ai=prior.ai
CAPITAL=prior.CAPITAL;START=prior.START;END=prior.END;POOL=prior.POOL;FLAGS=prior.FLAGS
_gate=prior._gate

def bind_review(review,paths):
    if review.get('schema')!='stage020_independent_review_v1':raise ValueError('wrong_review_schema')
    for arm in ['L','M']:
        p=Path(review.get(arm+'_attempt_path',''))
        if not p.is_absolute() or p.resolve()!=paths[arm].resolve():raise ValueError('wrong_review_attempt:'+arm)
    verdict=str(review.get('verdict',''))
    if verdict!='PASS_OFFLINE_RESEARCH' and not verdict.startswith('REJECT_'):raise ValueError('wrong_review_verdict')
    return review

def load_m(path,calendar=None):
    path=Path(path).resolve();sources={}
    def read(name):
        p=path/name;sources[str(p)]=base.sha(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal,metrics,effective,settings,preflight=[read(n) for n in ['terminal.json','metrics.json','effective_parameters.json','actual_strategy_settings.json','preflight.json']]
    if terminal.get('error') or terminal.get('status') not in {'completed_pending_independent_review','rejected_execution_bar_open'}:raise ValueError('complete_M_ledger_required')
    if len(settings)!=1 or settings[0]['strategy_class']!='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy' or metrics.get('arm')!='M' or metrics.get('result_scope')!='weekly_three_ma_no_position_cap_original19':raise ValueError('M_identity_mismatch')
    actual=settings[0]['actual']
    if any(actual.get(k) is not False for k in FLAGS):raise ValueError('M_disabled_flags_mismatch')
    if tuple(actual.get(k) for k in ['ma_short','ma_mid','ma_long'])!=(5,10,20) or actual.get('research_exact_array_manager_size')!=41:raise ValueError('M_weekly_indicator_contract_mismatch')
    if set(preflight.get('universe_products',[]))!=POOL or preflight.get('ready_need')!=21 or preflight.get('storage_capacity')!=41:raise ValueError('M_pool_or_warmup_mismatch')
    if preflight.get('execution_model')!=base.EXECUTION_MODEL or preflight.get('minute_quote_confirmed') is not False:raise ValueError('M_bar_open_model_mismatch')
    for value in [actual.get('capital_base'),settings[0]['engine_capital'],effective['spec']['capital']['account_capital'],effective['spec']['capital']['c3_capital']]:base.require_close(value,CAPITAL,'M_capital')
    macd=read('macd_acceptance.json');quality=read('bar_open_acceptance.json');ai_proof=read('ai_selection_acceptance.json')
    _gate(macd,'stage014_macd_disabled_acceptance_v1',dict(accepted=True,strategy_class='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy',macd_disabled=True,macd_calculation_attempts=0,candidate_case3_count=0,unknown_candidate_signals=0,rollover_macd_hist_non_null_count=0),'MACD')
    _gate(ai_proof,'stage012_ai_selection_off_v1',dict(accepted=True,model_load_attempts=0,runtime_loaded=False,nonzero_ai_candidate_fields=0),'AI')
    if quality.get('schema')!='stage011_daily_bar_open_acceptance_v1' or quality.get('verdict') not in {'PASS_DECLARED_BAR_OPEN_MODEL','REJECT_BAR_OPEN_MODEL'} or type(quality.get('accepted')) is not bool:raise ValueError('M_daily_open_acceptance_required')
    short=read('short_case2_acceptance.json')
    _gate(short,'stage018_short_case2_acceptance_v1',dict(accepted=True,strategy_class='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy',accepted_signals=['short_case1a','short_case2'],short_case2_gate_allowed=True,short_case1a_gate_allowed=True,case3_gate_allowed=False,short_signal_rejected_count=0,MA_decision_periods=[5,10,20],MA40_decision_enabled=False),'short_case2')
    candidates=read('entry_candidates.csv');allowed={'long_case1a','long_case2','short_case1a','short_case2'}
    if not set(candidates.signal).issubset(allowed) or candidates.skip_reason.eq('short_signal_rejected').any():raise ValueError('M_short_candidate_gate_mismatch')
    for key,value in [('short_case2_candidates',int(candidates.signal.eq('short_case2').sum())),('short_case2_opened',int((candidates.signal.eq('short_case2')&candidates.candidate_status.eq('opened')).sum()))]:base.require_close(short[key],value,'M_short_plan_count:'+key)
    if candidates.skip_reason.eq('concurrent_limit').any() or any(set(pd.to_numeric(candidates[k],errors='raise').unique())!={19} for k in ['max_concurrent_positions','effective_max_concurrent_positions']):raise ValueError('M_position_cap_candidates_mismatch')
    cap=read('no_position_cap_acceptance.json')
    _gate(cap,'stage020_no_position_cap_acceptance_v1',dict(accepted=True,strategy_class='ShortCase2NoMacdThreeMaWeeklyIndicatorsStrategy',universe_product_count=19,original_position_limit=4,candidate_effective_limit=19,configured_position_limit=19,candidate_effective_limit_values=[19],candidate_configured_limit_values=[19],concurrent_limit=0,portfolio_env_gate_enabled=False,implementation='universe_capacity_19_nonbinding_for_fixed_original19',MA40_decision_enabled=False,MA_decision_periods=[5,10,20]),'position_cap')
    if actual.get('max_concurrent_positions')!=19 or settings[0]['setting'].get('max_concurrent_positions')!=19:raise ValueError('M_position_cap_setting_mismatch')
    data_quality=read('data_quality.json');reads=read('data_read_counts.json')
    if any(data_quality.get(k) for k in ['held_or_traded_daily_gaps','held_or_traded_zero_volume','captured_bar_failures']) or any(reads.get(k)!=0 for k in ['minute_reads','proxy_reads','ai_selection_model_load_attempts']):raise ValueError('M_data_quality_or_reads_failed')
    if quality.get('modeled_clock_mismatch_count',0)!=0:raise ValueError('M_modeled_clock_mismatch')
    daily,trades,positions,clock=[read(n) for n in ['daily.csv','trades.csv','positions.csv','execution_clock.csv']]
    if trades.empty:trades=base.ordered_fills(trades,clock)
    daily['date']=pd.to_datetime(daily.date).dt.normalize();daily=daily.sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.duplicated().any() or not daily.date.between(START,END).all() or daily.date.iloc[0]!=pd.Timestamp('2020-01-02') or daily.date.iloc[-1]!=pd.Timestamp(END):raise ValueError('M_full_window_required')
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
    curve.update(pool_product_count=19,modeled_traded_product_count=int(trades.product_vt_symbol.nunique()),modeled_traded_products=sorted(trades.product_vt_symbol.unique()),modeled_fill_volume=float(trades.volume.sum()))
    return dict(path=str(path),arm='M',daily=daily,trades=trades,positions=positions,segments=segments,fifo_stats=fifo,metrics=curve,effective=effective,settings=settings,sources=sources,bar_open_acceptance=quality,macd_acceptance=macd,ai_selection_acceptance=ai_proof,short_case2_acceptance=short,no_position_cap_acceptance=cap)

def compare_parameter_contract(l,m):
    """Reject any setting/cost/spec change outside the four declared limit leaves."""
    import copy
    for name in ['setting','actual']:
        left=copy.deepcopy(l['settings'][0][name]);right=copy.deepcopy(m['settings'][0][name])
        if left.pop('max_concurrent_positions',None)!=4 or right.pop('max_concurrent_positions',None)!=19 or left!=right:raise ValueError('L_M_settings_differ:'+name)
    left=copy.deepcopy(l['effective']);right=copy.deepcopy(m['effective'])
    for key in ['capital','overrides']:
        if left['spec'][key].pop('max_concurrent_positions',None)!=4 or right['spec'][key].pop('max_concurrent_positions',None)!=19:raise ValueError('L_M_effective_limit_mismatch:'+key)
    if left!=right:raise ValueError('L_M_effective_parameters_differ')

def entry_attribution(ledger):
    value=prior.entry_attribution(ledger)
    value['note']='Candidate opened is a plan; rows without order IDs are not fills. Independent review documents cancellation/rebalance reasons. FIFO signal PnL decomposes a coupled path, not marginal alpha or the M-L difference.'
    return value

def plot(ledgers,statuses,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(12.5,7.8),sharex=True,gridspec_kw={'height_ratios':[2.1,1]})
    for arm,color,label in [('L','#2864A5','L: maximum 4 positions'),('M','#C16A08','M: all 19 eligible; no extra count cap')]:
        d=ledgers[arm]['daily'];style='-' if statuses[arm]['valid_performance_accepted'] else '--'
        if 'REJECTED' in statuses[arm]['performance_classification']:color='#B3261E';label+=' / REJECTED DIAGNOSTIC'
        top.plot(d.date,d.account_equity,color=color,lw=1.5,ls=style,label=label);peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100,color=color,lw=1.2,ls=style)
    title='OFFLINE RESEARCH / NO PROMOTION' if all(s['valid_performance_accepted'] for s in statuses.values()) else 'DIAGNOSTIC ONLY / REJECTED' if any('REJECTED' in s['performance_classification'] for s in statuses.values()) else 'CONDITIONAL MODEL / REVIEW PENDING'
    fig.suptitle('L / M '+title+'\nOriginal19; MA5/10/20; no MA40/MACD; storage41 / ready21; daily-bar-open model\n2020-01-02 to 2026-10-22; CNY150,000; Half-R/C2/all AI off; zero commission',fontsize=10.5,fontweight='bold')
    top.axhline(CAPITAL,color='#777',lw=.7,ls='--');top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'));top.legend(frameon=False)
    bottom.axhline(0,color='#777',lw=.7);bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Trading date')
    for axis in [top,bottom]:axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
    fig.tight_layout(rect=[0,0,1,.90]);fig.savefig(path,dpi=170);plt.close(fig)

def build_artifacts(line_dir,review_json=None):
    line=Path(line_dir).resolve();out=line/'outputs';art=line/'artifacts';tables=art/'stage020';image=art/'stage020_equity_drawdown.png'
    base.require_new_outputs([tables,image]);old={str(p):base.sha(p) for p in art.rglob('*') if p.is_file()} if art.exists() else {}
    paths={arm:out/(arm+'_attempt001') for arm in ['L','M']};calendar_path=out/'stage005_data/mapping.csv'
    calendar=sorted(d for d in pd.read_csv(calendar_path,usecols=['date']).date.astype(str).unique() if START<=d<=END)
    ledgers={'L':prior.load_l(paths['L'],calendar),'M':load_m(paths['M'],calendar)}
    compare_parameter_contract(ledgers['L'],ledgers['M'])
    control=Path(json.loads((paths['M']/'preflight.json').read_text())['control_path'])
    if not control.is_absolute() or control.resolve()!=paths['L']:raise ValueError('M_control_path_mismatch')
    sources={str(p):base.sha(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('stage020_build_artifacts.py').resolve(),Path(prior.__file__).resolve(),Path(prior.prior.__file__).resolve(),Path(base.__file__).resolve(),Path(ai.__file__).resolve(),Path(base.math_report.__file__).resolve(),calendar_path]}
    pointer=out/'stage020_contract_pointer.json';contract=json.loads(pointer.read_text());contract_path=Path(contract['path'])
    if not contract_path.is_absolute() or base.sha(contract_path)!=contract['sha256']:raise ValueError('position_cap_contract_changed')
    sources.update({str(pointer):base.sha(pointer),str(contract_path):contract['sha256']})
    review_path=Path(review_json).resolve() if review_json is not None else line/'stages/stage020_M_independent_review.json';review=None
    if review_path.exists():review=bind_review(json.loads(review_path.read_text()),paths);sources[str(review_path)]=base.sha(review_path)
    elif review_json is not None:raise FileNotFoundError(review_path)
    statuses={a:prior.prior.status(r['bar_open_acceptance'],review) for a,r in ledgers.items()};segments=[];arms={}
    for arm,r in ledgers.items():
        attribution=entry_attribution(r);sources.update(r['sources']);s=r['segments'].copy();s.insert(0,'arm',arm)
        for key in ['performance_classification','execution_audit_status','qualified_counts_status']:s[key]=statuses[arm][key]
        segments.append(s);arms[arm]=dict(path=r['path'],actual_strategy_class=r['settings'][0]['strategy_class'],**statuses[arm],modeled_metrics=r['metrics'],closed_fifo=r['fifo_stats'],bar_open_acceptance=r['bar_open_acceptance'],ai_selection_acceptance=r['ai_selection_acceptance'],macd_acceptance=r['macd_acceptance'],entry_fill_attribution=attribution)
    for a in ['L','M']:arms[a]['short_case2_acceptance']=ledgers[a]['short_case2_acceptance']
    arms['M']['no_position_cap_acceptance']=ledgers['M']['no_position_cap_acceptance']
    annual=pd.DataFrame([x for a,r in ledgers.items() for x in base.annual_rows(r['daily'],a,statuses[a])]);products=pd.DataFrame([x for a,r in ledgers.items() for x in base.product_rows(r,POOL,statuses[a])])
    summary=dict(schema='stage020_no_position_cap_original19_artifacts_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),arms=arms,
        contract=dict(start='2020-01-02',end=END,capital=CAPITAL,pool=sorted(POOL),MA=[5,10,20],MA40=False,MACD=False,storage=41,ready=21,short_signals=['short_case1a','short_case2'],L_max_concurrent_positions=4,M_max_concurrent_positions=19,one_position_per_product=True,all_AI=False,half_R=False,C2=False,execution_model=base.EXECUTION_MODEL),
        comparison=dict(modeled_ending_equity_M_minus_L=ledgers['M']['metrics']['end_equity']-ledgers['L']['metrics']['end_equity'],modeled_return_pct_M_minus_L=ledgers['M']['metrics']['total_return_pct']-ledgers['L']['metrics']['total_return_pct'],modeled_drawdown_pct_M_minus_L=ledgers['M']['metrics']['max_dd_pct']-ledgers['L']['metrics']['max_dd_pct'],interpretation='Coupled portfolio paths; aggregate difference is not independent marginal alpha from a position slot.'),
        decision='PASS_OFFLINE_RESEARCH_NO_PROMOTION' if all(s['valid_performance_accepted'] for s in statuses.values()) else 'DIAGNOSTIC_ONLY_REJECTED' if any('REJECTED' in s['performance_classification'] for s in statuses.values()) else 'PENDING_INDEPENDENT_REVIEW',
        final_independent_review=None if review is None else dict(path=str(review_path),sha256=base.sha(review_path),verdict=review['verdict']),production_qualified=False,promotion_decision='NO_PROMOTION',financial_replays=0,minute_evidence_files_read=0,
        limitations=['Declared daily-bar-open model, zero fees and fixed original slippage; no spread/depth/queue/capacity qualification.','Repeated historical window is not new PIT/OOS evidence.','Coupled product/signal MTM is not independent marginal alpha; terminal open MTM remains separate from closed FIFO statistics.','Candidate opened flags are plans, not actual fills.','Inherited labels/notes/deployable_pass do not establish identity.'],source_files_sha256=sources)
    art.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage020_',dir=art) as temporary:
        temp=Path(temporary);t=temp/'stage020';t.mkdir();annual.to_csv(t/'annual.csv',index=False);products.to_csv(t/'products.csv',index=False);pd.concat(segments,ignore_index=True).to_csv(t/'closed_fifo_segments.csv',index=False);plot(ledgers,statuses,temp/image.name)
        summary['output_files_sha256']={n:base.sha(t/n) for n in ['annual.csv','products.csv','closed_fifo_segments.csv']};summary['output_files_sha256'][image.name]=base.sha(temp/image.name)
        (t/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for p,d in {**sources,**old}.items():
            if base.sha(p)!=d:raise ValueError('immutable_input_or_artifact_changed:'+p)
        base.require_new_outputs([tables,image]);os.rename(t,tables);os.link(temp/image.name,image)
    return dict(status='DERIVED_L_M_ARTIFACTS_ONLY',outputs=[str(image),str(tables)],financial_replays=0,minute_evidence_files_read=0)

def main():
    default=next((p/'research/lines/futures_weekly_formal_no_half_r' for p in Path(__file__).resolve().parents if (p/'official_strategy_materials/CURRENT.json').is_file()),None)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--line-dir',type=Path,default=default);p.add_argument('--review-json',type=Path);args=p.parse_args()
    if args.line_dir is None:raise ValueError('--line-dir required outside repository')
    print(json.dumps(build_artifacts(args.line_dir,args.review_json),ensure_ascii=False))
if __name__=='__main__':main()
