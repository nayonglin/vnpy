"""J/H weekly bar-open model report: immutable derived artifacts, no replay.

Only conserved model ledgers and the daily-bar-open acceptance gate are read.
The imported Stage008 functions are pure FIFO/curve/table arithmetic; its minute
ledger loader, execution classifier and report main are never called.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse,json,os,re,sys,tempfile
import numpy as np
import pandas as pd
TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))
import stage008_build_artifacts as math_report
from stage008_build_artifacts import fifo_segments,curve_metrics,product_rows,annual_rows,sha,require_close,native_product,ordered_fills,require_new_outputs
CAPITAL=150000.;START='2020-01-01';END='2026-10-22'
SCOPE='weekly_bar_open_original19';EXECUTION_MODEL='declared_daily_bar_open_next_bar_v1'
FLAGS=['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']
ORIGINAL19=frozenset('AP.CZCE CF.CZCE FG.CZCE MA.CZCE OI.CZCE SA.CZCE SH.CZCE SM.CZCE au.SHFE cu.SHFE fu.SHFE hc.SHFE jm.DCE lc.GFEX lh.DCE rb.SHFE ru.SHFE si.GFEX sp.SHFE'.split())


def bind_review(review,paths):
    if review.get('schema')!='stage011_independent_review_v1':raise ValueError('unsupported_final_review_schema')
    for arm in ['J','H']:
        value=review.get(arm+'_attempt_path','')
        if not value or Path(value).resolve()!=Path(paths[arm]).resolve():raise ValueError('final_review_wrong_'+arm+'_attempt')
    verdict=str(review.get('verdict',''))
    if verdict!='PASS_OFFLINE_RESEARCH' and not verdict.startswith('REJECT_'):raise ValueError('unsupported_final_review_verdict')
    return review


def classify_bar_open(audit,review=None):
    if review is not None and (review.get('schema')!='stage011_independent_review_v1' or (review.get('verdict')!='PASS_OFFLINE_RESEARCH' and not str(review.get('verdict','')).startswith('REJECT_'))):raise ValueError('unsupported_final_review_schema_or_verdict')
    audit=audit or {};verdict=str(audit.get('verdict','NOT_ESTABLISHED'))
    correct=(audit.get('schema')=='stage011_daily_bar_open_acceptance_v1' and verdict=='PASS_DECLARED_BAR_OPEN_MODEL'
        and all(audit.get(k)==0 for k in ['minute_reads','proxy_reads','daily_price_mismatch_count','daily_data_invalid_count']))
    model_pass=bool(audit.get('accepted') is True and correct)
    review_verdict='' if review is None else str(review.get('verdict',''))
    rejected=(audit.get('accepted') is False or verdict.startswith('REJECT_') or review_verdict.startswith('REJECT_') or (audit.get('accepted') is True and not correct))
    accepted=bool(model_pass and not rejected and review_verdict=='PASS_OFFLINE_RESEARCH')
    classification='DIAGNOSTIC_ONLY_BAR_OPEN_MODEL_REJECTED' if rejected else 'REVIEWED_OFFLINE_BAR_OPEN_MODEL_NO_PROMOTION' if accepted else 'CONDITIONAL_BAR_OPEN_MODEL_PENDING_INDEPENDENT_REVIEW'
    return dict(performance_classification=classification,execution_audit_status=review_verdict if review_verdict.startswith('REJECT_') else verdict,
        bar_open_model_accepted=model_pass,valid_performance_accepted=accepted,production_qualified=False,promotion_decision='NO_PROMOTION',
        execution_model=EXECUTION_MODEL,minute_quote_confirmed=False,
        qualified_executable_trade_count=None,qualified_executable_product_count=None,
        qualified_counts_status='NOT_ESTABLISHED: daily-bar-open offline model counts do not qualify executable capacity or production')


def load_ledger(path,arm,products,calendar=None):
    path=Path(path).resolve();sources={}
    if arm not in {'J','H'}:raise ValueError('J_H_only')
    def read(name):
        p=path/name;sources[str(p)]=sha(p)
        return json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal,metrics,effective=(read(name) for name in ['terminal.json','metrics.json','effective_parameters.json'])
    if terminal.get('error') or terminal.get('status') not in {'completed_pending_independent_review','rejected_execution_bar_open'}:raise ValueError('complete_bar_open_ledger_required:'+arm)
    settings,preflight,acceptance=(read(name) for name in ['actual_strategy_settings.json','preflight.json','bar_open_acceptance.json'])
    expected='WeeklyIndicatorsStrategy' if arm=='J' else 'ThreeMaWeeklyIndicatorsStrategy'
    if len(settings)!=1 or settings[0].get('strategy_class')!=expected:raise ValueError('actual_class_mismatch:'+arm)
    actual=settings[0]['actual']
    if any(actual.get(k) is not False for k in FLAGS):raise ValueError('disabled_flags_mismatch:'+arm)
    if int(actual.get('research_exact_array_manager_size',0))!=41:raise ValueError('storage_capacity_mismatch:'+arm)
    if tuple(actual.get(k) for k in ['ma_short','ma_mid','ma_long'])!=(5,10,20):raise ValueError('three_base_MA_periods_mismatch:'+arm)
    if arm=='J' and actual.get('ma_extra_long')!=40:raise ValueError('J_MA40_period_mismatch')
    if set(products)!=ORIGINAL19 or set(preflight.get('universe_products',[]))!=ORIGINAL19:raise ValueError('original19_pool_mismatch:'+arm)
    require_close(settings[0]['engine_capital'],CAPITAL,'engine_capital')
    require_close(actual['capital_base'],CAPITAL,'actual_capital_base')
    for key in ['account_capital','c3_capital']:require_close(effective['spec']['capital'][key],CAPITAL,'effective_'+key)
    if metrics.get('arm')!=arm or metrics.get('result_scope')!=SCOPE:raise ValueError('arm_scope_mismatch:'+arm)
    if preflight.get('execution_model')!=EXECUTION_MODEL or preflight.get('minute_quote_confirmed') is not False:raise ValueError('declared_bar_open_model_identity_mismatch:'+arm)
    if acceptance.get('schema')!='stage011_daily_bar_open_acceptance_v1':raise ValueError('daily_bar_open_acceptance_schema_required')
    if acceptance.get('accepted') not in [True,False] or acceptance.get('verdict') not in {'PASS_DECLARED_BAR_OPEN_MODEL','REJECT_BAR_OPEN_MODEL'}:raise ValueError('daily_bar_open_acceptance_status_required')
    daily,trades,positions,clock=(read(name) for name in ['daily.csv','trades.csv','positions.csv','execution_clock.csv'])
    if trades.empty:trades=ordered_fills(trades,clock)
    daily['date']=pd.to_datetime(daily.date).dt.normalize();daily=daily.sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.duplicated().any() or not daily.date.between(START,END).all() or daily.date.iloc[0]!=pd.Timestamp('2020-01-02') or daily.date.iloc[-1]!=pd.Timestamp(END):raise ValueError('full_requested_daily_window_required:'+arm)
    if calendar is not None and daily.date.dt.strftime('%Y-%m-%d').tolist()!=list(calendar):raise ValueError('full_account_calendar_mismatch:'+arm)
    for col in ['account_equity','net_pnl','slippage','commission','trade_count']:
        daily[col]=pd.to_numeric(daily[col],errors='raise')
        if not np.isfinite(daily[col].to_numpy(float)).all():raise ValueError('nonfinite_account_column:'+col)
    require_close(np.abs((CAPITAL+daily.net_pnl.cumsum())-daily.account_equity).max(),0.,'daily_account_conservation')
    require_close(acceptance['trade_count'],len(trades),'bar_open_audited_trade_count')
    if int(acceptance['anchor_request_count'])<0:raise ValueError('negative_bar_open_request_count')
    positions['date']=pd.to_datetime(positions.date).dt.normalize();positions=positions.loc[positions.date.between(START,END)].copy()
    trade_days=pd.to_datetime(trades['trading_date'] if 'trading_date' in trades else trades.date)
    if not trade_days.between(START,END).all():raise ValueError('trade_outside_model_window')
    for frame in [trades,positions]:frame['product_vt_symbol']=frame.vt_symbol.map(lambda s:native_product(s,products))
    terminal_positions=positions.loc[positions.date.eq(daily.date.iloc[-1])]
    if terminal_positions.vt_symbol.duplicated().any():raise ValueError('duplicate_terminal_position')
    marks=dict(zip(terminal_positions.vt_symbol,terminal_positions.close_price))
    segments,fifo=fifo_segments(trades,effective,clock,marks)
    segments['product_vt_symbol']=segments.vt_symbol.map(lambda s:native_product(s,products)) if len(segments) else pd.Series(dtype=str)
    actual_pos=terminal_positions.set_index('vt_symbol').end_pos.astype(float).to_dict()
    for symbol in set(actual_pos)|set(fifo['open_net_positions']):require_close(actual_pos.get(symbol,0.),fifo['open_net_positions'].get(symbol,0.),'FIFO_terminal_position:'+symbol)
    recomputed=curve_metrics(daily)
    for key in ['end_equity','total_return_pct','max_dd_pct']:require_close(recomputed[key],metrics[key],'source_'+key)
    if recomputed['sharpe'] is not None:require_close(recomputed['sharpe'],metrics['sharpe'],'source_sharpe')
    require_close(recomputed['modeled_fill_count'],len(trades),'daily_fill_count');require_close(metrics['total_trade_count'],len(trades),'source_fill_count')
    require_close(fifo['total_slippage'],daily.slippage.sum(),'FIFO_slippage');require_close(fifo['total_commission'],daily.commission.sum(),'FIFO_commission')
    require_close(daily.commission.sum(),0.,'zero_commission_contract')
    require_close(fifo['ledger_net_pnl'],daily.account_equity.iloc[-1]-CAPITAL,'FIFO_full_ledger_conservation')
    require_close(positions.net_pnl.sum(),daily.net_pnl.sum(),'product_MTM_conservation')
    recomputed.update(pool_product_count=19,modeled_traded_product_count=int(trades.product_vt_symbol.nunique()),modeled_traded_products=sorted(trades.product_vt_symbol.unique()),modeled_fill_volume=float(trades.volume.sum()))
    optional={}
    for name in ['postflight.json','data_quality.json','weekly_coverage.json']:
        if (path/name).exists():optional[name]=read(name)
    if optional.get('postflight.json',{}).get('inputs_unchanged') is False:raise ValueError('input_mutation_rejected')
    return dict(path=str(path),arm=arm,daily=daily,trades=trades,positions=positions,effective=effective,settings=settings,
        source_metrics=metrics,metrics=recomputed,segments=segments,fifo_stats=fifo,sources=sources,optional=optional,terminal=terminal,bar_open_acceptance=acceptance,
        identity_basis='actual J/H class, disabled flags, original19, capital150000, declared daily-bar-open model, full account calendar and conserved model ledger; inherited labels are excluded')


def plot_comparison(ledgers,statuses,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    accepted=all(s['valid_performance_accepted'] for s in statuses.values())
    rejected=any('REJECTED' in s['performance_classification'] for s in statuses.values())
    heading='J / H WEEKLY BAR-OPEN MODEL - OFFLINE RESEARCH' if accepted else 'J / H DIAGNOSTIC ONLY - MODEL REJECTED' if rejected else 'J / H CONDITIONAL MODEL - INDEPENDENT REVIEW PENDING'
    fig,(top,bottom)=plt.subplots(2,1,figsize=(12.5,7.8),sharex=True,gridspec_kw={'height_ratios':[2.1,1]})
    for arm,color,label in [('J','#2864A5','J: MA5/10/20/40 control'),('H','#C16A08','H: MA5/10/20 user variant')]:
        d=ledgers[arm]['daily'];style='-' if statuses[arm]['valid_performance_accepted'] else '--'
        if 'REJECTED' in statuses[arm]['performance_classification']:color='#B3261E';label+=' / REJECTED DIAGNOSTIC'
        top.plot(d.date,d.account_equity,color=color,lw=1.5,ls=style,label=label)
        peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100,color=color,lw=1.2,ls=style)
    top.axhline(CAPITAL,color='#777777',lw=.7,ls='--');top.set_ylabel('Modeled equity (CNY)');top.legend(frameon=False,fontsize=9)
    top.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:,.0f}'))
    bottom.axhline(0,color='#777777',lw=.7);bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Trading date')
    for axis in [top,bottom]:axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
    fig.suptitle(heading+'\nOriginal 19; completed-week signals; next trading-day daily open; daily risk exits at next daily open\nCNY 150,000; 2020-01-01 to 2026-10-22; Half-R/C2/AI off; zero commission; no promotion',fontsize=10.5,fontweight='bold',color='#A8201A' if rejected else '#383838')
    top.text(.99,.02,'Daily OHLCV open model; calendar timestamps are model labels',transform=top.transAxes,ha='right',va='bottom',fontsize=8)
    fig.tight_layout(rect=[0,0,1,.90]);fig.savefig(path,dpi=170);plt.close(fig)


def build_artifacts(line_dir,review_json=None):
    line=Path(line_dir).resolve();out=line/'outputs';art=line/'artifacts';table_dir=art/'stage011';plot_path=art/'stage011_equity_drawdown.png'
    require_new_outputs([table_dir,plot_path])
    old_artifacts={str(p):sha(p) for p in art.rglob('*') if p.is_file()} if art.exists() else {}
    sources={str(Path(__file__).resolve()):sha(__file__),str(Path(math_report.__file__).resolve()):sha(math_report.__file__)}
    paths={}
    for arm in ['J','H']:
        pointer=out/(arm+'_completed_attempt.json');value=json.loads(pointer.read_text());sources[str(pointer)]=sha(pointer)
        path=Path(value['path'])
        if not path.is_absolute() or path.resolve().parent!=out.resolve() or not re.fullmatch(arm+r'_attempt[0-9]{3}',path.name):raise ValueError('completed_pointer_outside_scope:'+arm)
        paths[arm]=path.resolve()
    calendar_path=out/'stage005_data/mapping.csv';sources[str(calendar_path)]=sha(calendar_path)
    calendar=sorted(d for d in pd.read_csv(calendar_path,usecols=['date']).date.astype(str).unique() if START<=d<=END)
    ledgers={arm:load_ledger(paths[arm],arm,ORIGINAL19,calendar) for arm in ['J','H']}
    if not ledgers['J']['daily'].date.equals(ledgers['H']['daily'].date):raise ValueError('J_H_account_calendars_differ')
    if ledgers['J']['settings'][0]['setting']!=ledgers['H']['settings'][0]['setting']:raise ValueError('J_H_actual_settings_changed_beyond_strategy_class')
    for name in ['sizes','rates','slippages']:
        if ledgers['J']['effective'][name]!=ledgers['H']['effective'][name]:raise ValueError('J_H_cost_metadata_differ:'+name)
    review=None
    if review_json is not None:
        review_json=Path(review_json).resolve();review=bind_review(json.loads(review_json.read_text()),paths);sources[str(review_json)]=sha(review_json)
    statuses={arm:classify_bar_open(ledger['bar_open_acceptance'],review) for arm,ledger in ledgers.items()}
    annual=pd.DataFrame([r for arm,ledger in ledgers.items() for r in annual_rows(ledger['daily'],arm,statuses[arm])])
    products=pd.DataFrame([r for arm,ledger in ledgers.items() for r in product_rows(ledger,ORIGINAL19,statuses[arm])])
    segment_tables=[];arms={}
    for arm,ledger in ledgers.items():
        sources.update(ledger['sources']);segments=ledger['segments'].copy();segments.insert(0,'arm',arm)
        for key in ['performance_classification','execution_audit_status','qualified_counts_status']:segments[key]=statuses[arm][key]
        segment_tables.append(segments)
        arms[arm]=dict(path=ledger['path'],**statuses[arm],modeled_metrics=ledger['metrics'],closed_fifo=ledger['fifo_stats'],identity_basis=ledger['identity_basis'],
            bar_open_acceptance=ledger['bar_open_acceptance'],weekly_coverage=ledger['optional'].get('weekly_coverage.json'),
            metrics_basis='conserved daily-bar-open offline model; not tick/minute execution or capacity evidence')
    summary=dict(schema='stage011_weekly_bar_open_original19_artifacts_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        contract=dict(start=START,end=END,capital=CAPITAL,products=sorted(ORIGINAL19),pool_count=19,scope=SCOPE,execution_model=EXECUTION_MODEL,
            J_MA_periods=[5,10,20,40],H_MA_periods=[5,10,20],storage41=True,J_ready=41,H_ready=21,half_R=False,C2=False,AI=False,
            weekly_entry='completed weekly signal -> next trading day daily open (next weekly K open)',daily_risk_exit='next daily open',calendar_time_is_model_label=True),
        arms=arms,comparison=dict(modeled_ending_equity_H_minus_J=ledgers['H']['metrics']['end_equity']-ledgers['J']['metrics']['end_equity'],
            modeled_return_pct_H_minus_J=ledgers['H']['metrics']['total_return_pct']-ledgers['J']['metrics']['total_return_pct'],
            modeled_drawdown_pct_H_minus_J=ledgers['H']['metrics']['max_dd_pct']-ledgers['J']['metrics']['max_dd_pct'],
            interpretation='arithmetic model comparison only; pending/rejected paths remain diagnostics'),
        final_independent_review=None if review is None else dict(path=str(review_json),sha256=sha(review_json),verdict=review['verdict']),
        decision='PASS_OFFLINE_RESEARCH_NO_PROMOTION' if all(s['valid_performance_accepted'] for s in statuses.values()) else 'DIAGNOSTIC_ONLY_REJECTED' if any('REJECTED' in s['performance_classification'] for s in statuses.values()) else 'PENDING_INDEPENDENT_REVIEW',
        promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=0,minute_evidence_files_read=0,
        limitations=['Daily-bar-open prices are declared model assumptions, without spread/depth/queue/capacity evidence.',
            'Zero commission and original fixed slippage; not new PIT/OOS evidence; repeated historical-window use remains.',
            'Per-product MTM decomposes a coupled account, not independent marginal alpha.',
            'FIFO segments may split entries; open inventory is excluded from closed win-rate/payoff statistics.',
            'MA3 uses storage41/readiness21; 30-period risk warms at31; inherited rollover shape can use20 observations.',
            'Inherited labels/notes/deployable_pass do not establish identity or production qualification.'],source_files_sha256=sources)
    art.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage011_build_',dir=art) as temporary:
        temp=Path(temporary);table=temp/'stage011';table.mkdir()
        annual.to_csv(table/'annual.csv',index=False);products.to_csv(table/'products.csv',index=False);pd.concat(segment_tables,ignore_index=True).to_csv(table/'closed_fifo_segments.csv',index=False)
        plot_comparison(ledgers,statuses,temp/'stage011_equity_drawdown.png')
        summary['output_files_sha256']={name:sha(table/name) for name in ['annual.csv','products.csv','closed_fifo_segments.csv']}
        summary['output_files_sha256']['stage011_equity_drawdown.png']=sha(temp/'stage011_equity_drawdown.png')
        (table/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for path,digest in sources.items():
            if sha(path)!=digest:raise ValueError('source_changed_while_building:'+path)
        for path,digest in old_artifacts.items():
            if sha(path)!=digest:raise ValueError('previous_artifact_changed:'+path)
        require_new_outputs([table_dir,plot_path]);os.rename(table,table_dir);os.link(temp/'stage011_equity_drawdown.png',plot_path)
    return dict(status='DERIVED_BAR_OPEN_MODEL_ARTIFACTS_ONLY',J_classification=statuses['J']['performance_classification'],H_classification=statuses['H']['performance_classification'],
        outputs=[str(plot_path),*[str(table_dir/name) for name in ['annual.csv','products.csv','closed_fifo_segments.csv','comparison.json']]],financial_replays=0,minute_evidence_files_read=0,previous_artifact_files_preserved=len(old_artifacts))


def main():
    default=next((p/'research/lines/futures_weekly_formal_no_half_r' for p in Path(__file__).resolve().parents if (p/'official_strategy_materials/CURRENT.json').is_file()),None)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--line-dir',type=Path,default=default);parser.add_argument('--review-json',type=Path);args=parser.parse_args()
    if args.line_dir is None:raise ValueError('--line-dir required outside repository')
    print(json.dumps(build_artifacts(args.line_dir,args.review_json),ensure_ascii=False))

if __name__=='__main__':main()
