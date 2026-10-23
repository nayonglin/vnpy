"""Read frozen H and true K no-MACD ledgers; derive offline artifacts only."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,re,sys,tempfile
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage011_build_artifacts as base
import stage012_build_artifacts as ai
CAPITAL=base.CAPITAL;START=base.START;END=base.END;POOL=base.ORIGINAL19
FLAGS=tuple(dict.fromkeys([*base.FLAGS,*ai.AI_FLAGS]))

def bind_review(review,paths):
    if review.get('schema')!='stage014_independent_review_v1':raise ValueError('wrong_review_schema')
    for arm in ['H','K']:
        p=Path(review.get(arm+'_attempt_path',''))
        if not p.is_absolute() or p.resolve()!=paths[arm].resolve():raise ValueError('wrong_review_attempt:'+arm)
    v=str(review.get('verdict',''))
    if v!='PASS_OFFLINE_RESEARCH' and not v.startswith('REJECT_'):raise ValueError('wrong_review_verdict')
    return review

def _gate(payload,schema,conditions,name):
    if payload.get('schema')!=schema or any((payload.get(k) is not v) if isinstance(v,bool) else payload.get(k)!=v for k,v in conditions.items()):raise ValueError(name+'_acceptance_required')

def load_k(path,calendar=None):
    path=Path(path).resolve();sources={}
    def read(name):
        p=path/name;sources[str(p)]=base.sha(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal,metrics,effective,settings,preflight=[read(n) for n in ['terminal.json','metrics.json','effective_parameters.json','actual_strategy_settings.json','preflight.json']]
    if terminal.get('error') or terminal.get('status') not in {'completed_pending_independent_review','rejected_execution_bar_open'}:raise ValueError('complete_K_ledger_required')
    if len(settings)!=1 or settings[0]['strategy_class']!='NoMacdThreeMaWeeklyIndicatorsStrategy' or metrics.get('arm')!='K' or metrics.get('result_scope')!='weekly_no_macd_original19':raise ValueError('K_identity_mismatch')
    actual=settings[0]['actual']
    if any(actual.get(k) is not False for k in FLAGS):raise ValueError('K_disabled_flags_mismatch')
    if tuple(actual.get(k) for k in ['ma_short','ma_mid','ma_long'])!=(5,10,20) or actual.get('research_exact_array_manager_size')!=41:raise ValueError('K_weekly_indicator_contract_mismatch')
    if set(preflight.get('universe_products',[]))!=POOL or preflight.get('ready_need')!=21 or preflight.get('storage_capacity')!=41:raise ValueError('K_pool_or_warmup_mismatch')
    if preflight.get('execution_model')!=base.EXECUTION_MODEL or preflight.get('minute_quote_confirmed') is not False:raise ValueError('K_bar_open_model_mismatch')
    for value in [actual.get('capital_base'),settings[0]['engine_capital'],effective['spec']['capital']['account_capital'],effective['spec']['capital']['c3_capital']]:base.require_close(value,CAPITAL,'K_capital')
    macd=read('macd_acceptance.json');quality=read('bar_open_acceptance.json');ai_proof=read('ai_selection_acceptance.json')
    _gate(macd,'stage014_macd_disabled_acceptance_v1',dict(accepted=True,macd_disabled=True,macd_calculation_attempts=0,candidate_case3_count=0,rollover_macd_hist_non_null_count=0),'MACD')
    _gate(ai_proof,'stage012_ai_selection_off_v1',dict(accepted=True,model_load_attempts=0,runtime_loaded=False,nonzero_ai_candidate_fields=0),'AI')
    if quality.get('schema')!='stage011_daily_bar_open_acceptance_v1' or quality.get('verdict') not in {'PASS_DECLARED_BAR_OPEN_MODEL','REJECT_BAR_OPEN_MODEL'} or type(quality.get('accepted')) is not bool:raise ValueError('K_daily_open_acceptance_required')
    daily,trades,positions,clock=[read(n) for n in ['daily.csv','trades.csv','positions.csv','execution_clock.csv']]
    if trades.empty:trades=base.ordered_fills(trades,clock)
    daily['date']=pd.to_datetime(daily.date).dt.normalize();daily=daily.sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.duplicated().any() or not daily.date.between(START,END).all() or daily.date.iloc[0]!=pd.Timestamp('2020-01-02') or daily.date.iloc[-1]!=pd.Timestamp(END):raise ValueError('K_full_window_required')
    if calendar is not None and daily.date.dt.strftime('%Y-%m-%d').tolist()!=list(calendar):raise ValueError('K_full_calendar_required')
    if not np.isfinite(daily[['account_equity','net_pnl','slippage','commission','trade_count']].to_numpy(float)).all():raise ValueError('K_nonfinite_daily')
    base.require_close(np.abs(CAPITAL+daily.net_pnl.cumsum()-daily.account_equity).max(),0.,'K_daily_conservation')
    positions['date']=pd.to_datetime(positions.date).dt.normalize();positions=positions.loc[positions.date.between(START,END)].copy()
    days=pd.to_datetime(trades['trading_date'] if 'trading_date' in trades else trades.date)
    if not days.between(START,END).all():raise ValueError('K_fill_outside_window')
    for frame in [trades,positions]:frame['product_vt_symbol']=frame.vt_symbol.map(lambda s:base.native_product(s,POOL))
    last=positions.loc[positions.date.eq(END)]
    if last.vt_symbol.duplicated().any():raise ValueError('K_duplicate_terminal_position')
    segments,fifo=base.fifo_segments(trades,effective,clock,dict(zip(last.vt_symbol,last.close_price)))
    segments['product_vt_symbol']=segments.vt_symbol.map(lambda s:base.native_product(s,POOL)) if len(segments) else pd.Series(dtype=str)
    actual_pos=last.set_index('vt_symbol').end_pos.astype(float).to_dict()
    for symbol in set(actual_pos)|set(fifo['open_net_positions']):base.require_close(actual_pos.get(symbol,0),fifo['open_net_positions'].get(symbol,0),'K_terminal_position')
    curve=base.curve_metrics(daily)
    for key in ['end_equity','total_return_pct','max_dd_pct']:base.require_close(curve[key],metrics[key],'K_source_'+key)
    if curve['sharpe'] is not None:base.require_close(curve['sharpe'],metrics['sharpe'],'K_source_sharpe')
    for count in [curve['modeled_fill_count'],metrics['total_trade_count'],quality['trade_count']]:base.require_close(count,len(trades),'K_fill_count')
    base.require_close(fifo['total_slippage'],daily.slippage.sum(),'K_slippage');base.require_close(fifo['total_commission'],daily.commission.sum(),'K_commission')
    base.require_close(daily.commission.sum(),0.,'K_zero_fee');base.require_close(fifo['ledger_net_pnl'],curve['end_equity']-CAPITAL,'K_FIFO_conservation');base.require_close(positions.net_pnl.sum(),daily.net_pnl.sum(),'K_product_conservation')
    postflight=read('postflight.json')
    if postflight.get('inputs_unchanged') is not True:raise ValueError('K_inputs_changed')
    curve.update(pool_product_count=19,modeled_traded_product_count=int(trades.product_vt_symbol.nunique()),modeled_traded_products=sorted(trades.product_vt_symbol.unique()),modeled_fill_volume=float(trades.volume.sum()))
    return dict(path=str(path),arm='K',daily=daily,trades=trades,positions=positions,segments=segments,fifo_stats=fifo,metrics=curve,effective=effective,settings=settings,sources=sources,bar_open_acceptance=quality,macd_acceptance=macd,ai_selection_acceptance=ai_proof)

def status(quality,review):
    value=base.classify_bar_open(quality);verdict='' if review is None else review['verdict']
    if verdict.startswith('REJECT_'):value.update(performance_classification='DIAGNOSTIC_ONLY_REVIEW_REJECTED',execution_audit_status=verdict)
    elif verdict=='PASS_OFFLINE_RESEARCH' and value['bar_open_model_accepted']:value.update(performance_classification='REVIEWED_OFFLINE_BAR_OPEN_MODEL_NO_PROMOTION',valid_performance_accepted=True)
    return value

def plot(ledgers,statuses,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(12.5,7.8),sharex=True,gridspec_kw={'height_ratios':[2.1,1]})
    for arm,color,label in [('H','#2864A5','H: 3-MA + MACD control'),('K','#C16A08','K: 3-MA, MACD disabled')]:
        d=ledgers[arm]['daily'];style='-' if statuses[arm]['valid_performance_accepted'] else '--'
        if 'REJECTED' in statuses[arm]['performance_classification']:color='#B3261E';label+=' / REJECTED DIAGNOSTIC'
        top.plot(d.date,d.account_equity,color=color,lw=1.5,ls=style,label=label);peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100,color=color,lw=1.2,ls=style)
    accepted=all(s['valid_performance_accepted'] for s in statuses.values());rejected=any('REJECTED' in s['performance_classification'] for s in statuses.values())
    title='OFFLINE RESEARCH / NO PROMOTION' if accepted else 'DIAGNOSTIC ONLY / REJECTED' if rejected else 'CONDITIONAL MODEL / REVIEW PENDING'
    fig.suptitle('H / K '+title+'\nOriginal19; MA5/10/20; storage41 / ready21; daily-bar-open model\n2020-01-01 to 2026-10-22; CNY150,000; Half-R/C2/all AI off; zero commission',fontsize=11,fontweight='bold')
    top.axhline(CAPITAL,color='#777',lw=.7,ls='--');top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'));top.legend(frameon=False)
    bottom.axhline(0,color='#777',lw=.7);bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Trading date')
    for axis in [top,bottom]:axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
    fig.tight_layout(rect=[0,0,1,.90]);fig.savefig(path,dpi=170);plt.close(fig)

def build_artifacts(line_dir,review_json=None):
    line=Path(line_dir).resolve();out=line/'outputs';art=line/'artifacts';tables=art/'stage014';image=art/'stage014_equity_drawdown.png'
    base.require_new_outputs([tables,image]);old={str(p):base.sha(p) for p in art.rglob('*') if p.is_file()} if art.exists() else {}
    pointer=out/'K_completed_attempt.json';k=Path(json.loads(pointer.read_text())['path'])
    if not k.is_absolute() or k.resolve().parent!=out or not re.fullmatch('K_attempt[0-9]{3}',k.name):raise ValueError('K_pointer_outside_scope')
    paths={'H':out/'H_attempt001','K':k.resolve()};calendar_path=out/'stage005_data/mapping.csv'
    calendar=sorted(d for d in pd.read_csv(calendar_path,usecols=['date']).date.astype(str).unique() if START<=d<=END)
    ledgers={'H':ai.load_ledger(paths['H'],'H',POOL,calendar),'K':load_k(paths['K'],calendar)}
    base.require_close(ledgers['H']['metrics']['end_equity'],979390.,'frozen_H_control_equity')
    h_pre=json.loads((paths['H']/'preflight.json').read_text())
    if h_pre.get('ready_need')!=21 or h_pre.get('storage_capacity')!=41:raise ValueError('H_warmup_identity')
    for name in ['setting','actual']:
        if ledgers['H']['settings'][0][name]!=ledgers['K']['settings'][0][name]:raise ValueError('H_K_actual_settings_differ:'+name)
    for name in ['sizes','rates','slippages']:
        if ledgers['H']['effective'][name]!=ledgers['K']['effective'][name]:raise ValueError('H_K_costs_differ:'+name)
    sources={str(p):base.sha(p) for p in [Path(__file__).resolve(),Path(base.__file__).resolve(),Path(ai.__file__).resolve(),Path(base.math_report.__file__).resolve(),pointer,calendar_path]}
    review=None
    if review_json is not None:
        review_json=Path(review_json).resolve();review=bind_review(json.loads(review_json.read_text()),paths);sources[str(review_json)]=base.sha(review_json)
    statuses={a:status(r['bar_open_acceptance'],review) for a,r in ledgers.items()};segments=[];arms={}
    for arm,r in ledgers.items():
        sources.update(r['sources']);s=r['segments'].copy();s.insert(0,'arm',arm)
        for key in ['performance_classification','execution_audit_status','qualified_counts_status']:s[key]=statuses[arm][key]
        segments.append(s);arms[arm]=dict(path=r['path'],actual_strategy_class=r['settings'][0]['strategy_class'],**statuses[arm],modeled_metrics=r['metrics'],closed_fifo=r['fifo_stats'],bar_open_acceptance=r['bar_open_acceptance'],ai_selection_acceptance=r['ai_selection_acceptance'])
    arms['K']['macd_acceptance']=ledgers['K']['macd_acceptance']
    annual=pd.DataFrame([x for a,r in ledgers.items() for x in base.annual_rows(r['daily'],a,statuses[a])]);products=pd.DataFrame([x for a,r in ledgers.items() for x in base.product_rows(r,POOL,statuses[a])])
    summary=dict(schema='stage014_no_macd_original19_artifacts_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),arms=arms,
        contract=dict(start=START,end=END,capital=CAPITAL,pool=sorted(POOL),MA=[5,10,20],storage=41,ready=21,K_MACD=False,H_MACD=True,all_AI=False,half_R=False,C2=False,execution_model=base.EXECUTION_MODEL),
        comparison=dict(modeled_ending_equity_K_minus_H=ledgers['K']['metrics']['end_equity']-ledgers['H']['metrics']['end_equity'],modeled_return_pct_K_minus_H=ledgers['K']['metrics']['total_return_pct']-ledgers['H']['metrics']['total_return_pct'],modeled_drawdown_pct_K_minus_H=ledgers['K']['metrics']['max_dd_pct']-ledgers['H']['metrics']['max_dd_pct']),
        decision='PASS_OFFLINE_RESEARCH_NO_PROMOTION' if all(s['valid_performance_accepted'] for s in statuses.values()) else 'DIAGNOSTIC_ONLY_REJECTED' if any('REJECTED' in s['performance_classification'] for s in statuses.values()) else 'PENDING_INDEPENDENT_REVIEW',
        final_independent_review=None if review is None else dict(path=str(review_json),sha256=base.sha(review_json),verdict=review['verdict']),production_qualified=False,promotion_decision='NO_PROMOTION',financial_replays=0,minute_evidence_files_read=0,
        limitations=['Declared daily-bar-open model, zero fees and fixed original slippage; no spread/depth/queue/capacity qualification.','Repeated historical window is not new PIT/OOS evidence.','Coupled product MTM is not independent marginal alpha; terminal open MTM is separate from closed FIFO statistics.','Inherited labels/notes/deployable_pass do not establish strategy identity.'],source_files_sha256=sources)
    art.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage014_',dir=art) as temporary:
        temp=Path(temporary);t=temp/'stage014';t.mkdir();annual.to_csv(t/'annual.csv',index=False);products.to_csv(t/'products.csv',index=False);pd.concat(segments,ignore_index=True).to_csv(t/'closed_fifo_segments.csv',index=False);plot(ledgers,statuses,temp/image.name)
        summary['output_files_sha256']={n:base.sha(t/n) for n in ['annual.csv','products.csv','closed_fifo_segments.csv']};summary['output_files_sha256'][image.name]=base.sha(temp/image.name)
        (t/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for p,d in {**sources,**old}.items():
            if base.sha(p)!=d:raise ValueError('immutable_input_or_artifact_changed:'+p)
        base.require_new_outputs([tables,image]);os.rename(t,tables);os.link(temp/image.name,image)
    return dict(status='DERIVED_H_K_ARTIFACTS_ONLY',outputs=[str(image),str(tables)],financial_replays=0,minute_evidence_files_read=0)

def main():
    default=next((p/'research/lines/futures_weekly_formal_no_half_r' for p in Path(__file__).resolve().parents if (p/'official_strategy_materials/CURRENT.json').is_file()),None)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--line-dir',type=Path,default=default);p.add_argument('--review-json',type=Path);args=p.parse_args()
    if args.line_dir is None:raise ValueError('--line-dir required outside repository')
    print(json.dumps(build_artifacts(args.line_dir,args.review_json),ensure_ascii=False))
if __name__=='__main__':main()
