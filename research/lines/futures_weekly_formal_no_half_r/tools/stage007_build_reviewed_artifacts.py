"""Stage007最终审查展示：E009通过；F016零量平仓导致整体执行否决。

冻结模型账本数值不改；F仅为DIAGNOSTIC ONLY，不代表有效可执行表现。
必须指定最终--review-json，四项旧展示须先有逐字节一致备份后才允许覆盖。
无行情下载、定价修补、品种删减、参数调整或财务回测调用。
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, math, os, re, tempfile
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
OUT=LINE/'outputs';ART=LINE/'artifacts'
START='2020-01-01';END='2026-10-22';CAPITAL=150000.
NAMES=['stage007_equity_drawdown.png','stage007_annual_results.csv','stage007_product_results.csv','stage007_comparison_summary.json']
FLAGS=['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']
METRICS=['end_equity','total_return_pct','cagr_pct','max_dd_pct','sharpe','total_slippage','total_trade_count',
         'nonzero_daily_win_rate_pct','max_broker10_margin_to_equity_pct','p95_broker10_margin_to_equity_pct']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def require_close(actual,expected,name,tolerance=1e-6):
    if not math.isfinite(float(actual)) or abs(float(actual)-float(expected))>tolerance:
        raise ValueError(name+':'+repr((actual,expected)))


def native_product(vt_symbol,products):
    match=re.fullmatch(r'([A-Za-z]+)[0-9]{3,4}(F?)\.([A-Z]+)',str(vt_symbol))
    if match is None:raise ValueError('native_contract_parse_failed:'+str(vt_symbol))
    product=match.group(1)+('_F' if match.group(2) else '')+'.'+match.group(3)
    if product not in products:raise ValueError('native_contract_outside_frozen_universe:'+str(vt_symbol))
    return product


def annual_rows(daily,arm,label):
    rows=[];starting=CAPITAL
    for year,group in daily.sort_values('date').groupby(daily.sort_values('date').date.dt.year,sort=True):
        ending=float(group.account_equity.iloc[-1]);pnl=float(group.net_pnl.sum())
        require_close(ending-starting,pnl,'annual_equity_pnl_conservation')
        rows.append(dict(arm=arm,label=label,year=int(year),period=f'{year} YTD' if year==2026 else str(year),
            period_start=group.date.iloc[0].strftime('%Y-%m-%d'),period_end=group.date.iloc[-1].strftime('%Y-%m-%d'),
            starting_equity=starting,ending_equity=ending,net_pnl=pnl,return_pct=(ending/starting-1)*100,
            trade_count=int(group.trade_count.sum()),slippage=float(group.slippage.sum()),commission=float(group.commission.sum())))
        starting=ending
    return rows


def load_arm(arm,products,sources):
    pointer_path=OUT/(arm+'_completed_attempt.json');sources[str(pointer_path)]=sha(pointer_path)
    pointer=json.loads(pointer_path.read_text());path=(OUT/('E_attempt009' if arm=='E' else 'F_attempt016')).resolve()
    if path.parent!=OUT.resolve() or not path.name.startswith(arm+'_attempt'):raise ValueError('completed_pointer_outside_arm_scope')
    names=['terminal.json','metrics.json','actual_strategy_settings.json','effective_parameters.json','daily.csv','trades.csv','positions.csv']
    payload={}
    for name in names:
        p=path/name;sources[str(p)]=sha(p)
        payload[name]=json.loads(p.read_text()) if name.endswith('.json') else pd.read_csv(p,low_memory=False)
    terminal=payload['terminal.json'];metrics=payload['metrics.json'];effective=payload['effective_parameters.json']
    if not str(terminal.get('status','')).startswith('completed') or terminal.get('error'):raise ValueError('arm_not_completed:'+arm)
    settings=payload['actual_strategy_settings.json']
    if len(settings)!=1 or settings[0]['strategy_class']!='WeeklyIndicatorsStrategy':raise ValueError('actual_weekly_class_not_verified:'+arm)
    actual=settings[0]['actual']
    if any(actual.get(key) is not False for key in FLAGS):raise ValueError('actual_disabled_flags_not_verified:'+arm)
    require_close(settings[0]['engine_capital'],CAPITAL,'engine_capital')
    require_close(effective['spec']['capital']['account_capital'],CAPITAL,'effective_account_capital')
    require_close(effective['spec']['capital']['c3_capital'],CAPITAL,'effective_c3_capital')
    if int(actual.get('research_exact_array_manager_size',0))!=41:raise ValueError('actual_AM41_not_verified')
    expected_scope='weekly_half_r_c2_ai_off_'+('full91' if arm=='F' else 'same_data_original19')
    if metrics.get('arm')!=arm or metrics.get('result_scope')!=expected_scope:raise ValueError('actual_arm_scope_mismatch')
    daily=payload['daily.csv'];daily['date']=pd.to_datetime(daily.date).dt.normalize()
    if daily.date.duplicated().any():raise ValueError('duplicate_daily_date')
    daily=daily.loc[daily.date.between(START,END)].sort_values('date').reset_index(drop=True)
    if daily.empty or daily.date.iloc[-1]!=pd.Timestamp(END):raise ValueError('requested_terminal_date_missing')
    for name in ['account_equity','net_pnl','slippage','commission','trade_count']:
        daily[name]=pd.to_numeric(daily[name],errors='raise')
        if not np.isfinite(daily[name].to_numpy(float)).all():raise ValueError('nonfinite_daily_'+name)
    require_close(metrics['end_equity'],daily.account_equity.iloc[-1],'metrics_terminal_equity')
    require_close(metrics['total_return_pct'],(daily.account_equity.iloc[-1]/CAPITAL-1)*100,'metrics_total_return')
    require_close(daily.net_pnl.sum(),daily.account_equity.iloc[-1]-CAPITAL,'daily_equity_pnl_conservation')
    require_close(daily.slippage.sum(),metrics['total_slippage'],'metrics_slippage')
    require_close(daily.commission.sum(),0,'zero_commission_contract')
    trades=payload['trades.csv'];trade_date='trading_date' if 'trading_date' in trades else 'date'
    trades=trades.loc[pd.to_datetime(trades[trade_date]).between(START,END)].copy()
    require_close(metrics['total_trade_count'],len(trades),'metrics_actual_fill_count')
    require_close(daily.trade_count.sum(),len(trades),'daily_actual_fill_count')
    positions=payload['positions.csv'];positions['date']=pd.to_datetime(positions.date).dt.normalize()
    positions=positions.loc[positions.date.between(START,END)].copy()
    require_close(positions.net_pnl.sum(),daily.account_equity.iloc[-1]-CAPITAL,'positions_equity_pnl_conservation')
    observed_symbols=set(positions.vt_symbol.astype(str))|set(trades.vt_symbol.astype(str))
    missing=observed_symbols-set(effective['sizes'])
    if missing:raise ValueError('observed_contract_missing_effective_metadata:'+','.join(sorted(missing)))
    contract_map={symbol:native_product(symbol,products) for symbol in observed_symbols}
    for frame in [positions,trades]:
        missing=set(frame.vt_symbol.astype(str))-set(contract_map)
        if missing:raise ValueError('actual_contract_missing_metadata:'+','.join(sorted(missing)))
        frame['product_vt_symbol']=frame.vt_symbol.map(contract_map)
    optional={}
    for name in ['preflight.json','weekly_coverage.json','data_quality.json','postflight.json']:
        p=path/name
        if p.exists():sources[str(p)]=sha(p);optional[name]=json.loads(p.read_text())
    if optional.get('postflight.json',{}).get('inputs_unchanged') is False:raise ValueError('run_input_mutation_rejected')
    nonzero_positions=positions.loc[positions[['start_pos','end_pos','trade_count']].abs().sum(axis=1)>0]
    traded_products=sorted(trades.product_vt_symbol.unique())
    summary=dict(arm=arm,display_name='Full market (91 families)' if arm=='F' else 'Original 19 products (same data)',
        path=str(path),pointer_review_status=pointer.get('review_status'),result_scope=expected_scope,
        actual_strategy_class=settings[0]['strategy_class'],actual_flags={key:actual[key] for key in FLAGS},
        actual_array_manager_size=41,initial_capital=CAPITAL,start=START,end=END,
        actual_start=daily.date.iloc[0].strftime('%Y-%m-%d'),actual_end=daily.date.iloc[-1].strftime('%Y-%m-%d'),
        trading_days=len(daily),metrics={key:float(metrics[key]) for key in METRICS if key in metrics},
        actual_fill_count=len(trades),actual_traded_product_count=len(traded_products),actual_traded_products=traded_products,
        total_fill_volume=float(trades.volume.sum()),total_commission=float(daily.commission.sum()),
        active_product_days=int(len(nonzero_positions[['date','product_vt_symbol']].drop_duplicates())),
        active_margin_days=int((daily.total_margin_exact>0).sum()) if 'total_margin_exact' in daily else None,
        average_margin_to_equity_pct=float((daily.total_margin_exact/daily.account_equity).mean()*100) if 'total_margin_exact' in daily else None,
        weekly_coverage=optional.get('weekly_coverage.json'),data_quality=optional.get('data_quality.json'),
        identity_basis='actual captured strategy settings, effective capital, arm/result_scope, raw fills and daily ledger',
        inherited_label_note_deployable_pass_used_as_identity=False)
    return daily,trades,positions,effective,summary


def plot_comparison(arms,path):
    os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(12.5,7.5),sharex=True,gridspec_kw={'height_ratios':[2.1,1]})
    colors={'E':'#2864A5','F':'#B3261E'}
    for arm,(daily,_,_,_,summary) in arms.items():
        top.plot(daily.date,daily.account_equity,label=('E: Reviewed original 19 products' if arm=='E' else 'F: DIAGNOSTIC ONLY - REJECTED (zero-volume exit)'),color=colors[arm],lw=1.5,ls='-' if arm=='E' else '--')
        high=daily.account_equity.cummax().clip(lower=CAPITAL)
        dd=(daily.account_equity/high-1)*100
        bottom.plot(daily.date,dd,color=colors[arm],lw=1.2,ls='-' if arm=='E' else '--')
    top.axhline(CAPITAL,color='#777777',lw=.7,ls='--');top.set_ylabel('Modeled equity (CNY)')
    top.yaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:,.0f}'))
    top.legend(loc='upper left',frameon=False,fontsize=9)
    bottom.axhline(0,color='#777777',lw=.7);bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Trading date')
    for axis in [top,bottom]:axis.grid(alpha=.2);axis.spines[['top','right']].set_visible(False)
    fig.suptitle('F REJECTED: ZERO-VOLUME EXIT | DIAGNOSTIC ONLY\nWeekly AM41; Half-R / C2 / AI off; CNY 150,000; 2020-01-01 to 2026-10-22; zero commission',fontsize=12,color='#A8201A',fontweight='bold')
    top.text(.99,.02,'F IS NOT QUALIFIED EXECUTABLE PERFORMANCE',transform=top.transAxes,ha='right',va='bottom',fontsize=9,color='#A8201A',fontweight='bold',bbox=dict(facecolor='white',alpha=.85,edgecolor='#B3261E',boxstyle='round,pad=.3'))
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(path,dpi=170);plt.close(fig)



REJECTION='REJECT_EXECUTION_ZERO_VOLUME'


def review_has_rejection(value):
    if isinstance(value,dict):return any(review_has_rejection(item) for item in value.values())
    if isinstance(value,list):return any(review_has_rejection(item) for item in value)
    return isinstance(value,str) and REJECTION in value


def bind_pre_review_artifacts(sources):
    backup=OUT/'stage007_pre_review_artifacts';digests={}
    for name in NAMES:
        original=ART/name;copy=backup/name
        if not original.is_file() or not copy.is_file():raise ValueError('required_pre_review_artifact_backup_missing:'+name)
        digest=sha(original)
        if sha(copy)!=digest:raise ValueError('pre_review_artifact_backup_not_byte_identical:'+name)
        sources[str(copy)]=digest;digests[name]=digest
    return digests


def apply_final_review(arms,annual,product_results,summary,review_path,review_payload,backup_digests):
    if not review_has_rejection(review_payload):raise ValueError('final_review_does_not_explicitly_reject_zero_volume_execution')
    f=arms['F'][4];require_close(f['metrics']['end_equity'],212500,'frozen_F016_diagnostic_equity')
    if f['actual_fill_count']!=240 or f['actual_traded_product_count']!=49:raise ValueError('frozen_F016_diagnostic_model_counts_changed')
    e=arms['E'][4]
    if Path(e['path']).name!='E_attempt009' or Path(f['path']).name!='F_attempt016':raise ValueError('frozen_E009_F016_required')
    bad=arms['F'][1].loc[arms['F'][1].trade_id.eq('BACKTESTING.44')]
    if len(bad)!=1:raise ValueError('reviewed_unexecutable_exit_not_found')
    bad=bad.iloc[0]
    if bad.vt_symbol!='eb2105.DCE' or str(bad.trading_date)[:10]!='2021-05-06' or str(bad.exit_reason)!='long_base_stop':raise ValueError('reviewed_exit_identity_changed')
    require_close(bad.price,9127,'frozen_rejected_exit_price');require_close(bad.volume,7,'frozen_rejected_exit_volume')
    e.update(execution_audit_status='PASS',result_classification='REVIEWED_RESEARCH_BASELINE',
        metrics_basis='Offline modeled ledger; execution review passed within documented zero-commission/data limitations; not production qualification.')
    f['display_name']='Full market (91 families) - DIAGNOSTIC ONLY / EXECUTION REJECTED'
    f.update(execution_audit_status=REJECTION,result_classification='DIAGNOSTIC_ONLY_REJECTED',
        modeled_fill_count=f.pop('actual_fill_count'),modeled_traded_product_count=f.pop('actual_traded_product_count'),
        modeled_traded_products=f.pop('actual_traded_products'),modeled_fill_volume=f.pop('total_fill_volume'),
        qualified_executable_trade_count=None,qualified_executable_product_count=None,
        qualified_counts_status='NOT_ESTABLISHED: entire F account path rejected; do not subtract one bad fill and call remaining fills qualified.',
        metrics_basis='Frozen diagnostic model ledger only. These metrics are not valid executable strategy performance.')
    statuses={'E':'PASS','F':REJECTION}
    annual['execution_audit_status']=annual.arm.map(statuses)
    annual['performance_classification']=annual.arm.map({'E':'reviewed offline research baseline','F':'DIAGNOSTIC ONLY - EXECUTION REJECTED'})
    product_results=product_results.rename(columns={'actual_fill_count':'modeled_fill_count','actual_fill_volume_open_and_close':'modeled_fill_volume_open_and_close'})
    product_results['execution_audit_status']=REJECTION
    product_results['performance_classification']='DIAGNOSTIC ONLY - EXECUTION REJECTED'
    product_results['qualified_executable_counts_status']='NOT_ESTABLISHED; model fills/products are not qualified executable trades'
    summary['schema']='stage007_reviewed_weekly_full_market_comparison_v2'
    summary['decision']=REJECTION
    summary['promotion_decision']='NO_PROMOTION'
    summary['F_valid_executable_backtest']=False
    summary['F_classification']='DIAGNOSTIC_ONLY_REJECTED'
    summary['E_execution_audit_status']='PASS'
    summary['F_execution_audit_status']=REJECTION
    summary['final_independent_review']=dict(path=str(review_path),sha256=sha(review_path),required_verdict=REJECTION)
    summary['reviewed_rejection_finding']=dict(trade_id='BACKTESTING.44',contract='eb2105.DCE',trading_date='2021-05-06',
        execution_time='09:00',modeled_exit_price_unchanged=9127,modeled_exit_volume_unchanged=7,
        minute_trade_volume=0,exit_reason='long_base_stop',
        conclusion='Zero-volume first minute carries the previous session price; the seven-lot modeled exit is unexecutable. F full-path performance rejected.',
        prices_changed=False,products_removed=False,financial_replays=0)
    summary['validation']='Frozen ledger arithmetic and identity checked; E execution review passed, F independent execution review REJECTED.'
    summary['comparison']['interpretation']='Diagnostic arithmetic differences only; cannot establish that F improves executable performance over E.'
    summary['product_table'].update(execution_audit_status=REJECTION,pnl_classification='F diagnostic daily MTM ledger only; not executable performance',
        modeled_traded_products=49,modeled_fills=240,qualified_executable_product_count=None,qualified_executable_trade_count=None)
    summary['pre_review_artifacts_byte_preserved']={str(OUT/'stage007_pre_review_artifacts'/name):digest for name,digest in backup_digests.items()}
    summary['limitations'].insert(0,'F REJECTED: an unexecutable zero-volume exit contaminates its subsequent account path. Preserve all model values only as diagnostic evidence; do not report F as qualified performance.')
    return annual,product_results


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--review-json',type=Path,required=True);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:return self_test()
    review_path=args.review_json.resolve()
    review_payload=json.loads(review_path.read_text())
    if not review_has_rejection(review_payload):raise ValueError('final_review_missing_required_zero_volume_rejection')
    sources={str(review_path):sha(review_path)}
    backup_digests=bind_pre_review_artifacts(sources)
    universe_path=OUT/'stage005_data/universe.csv';sources[str(universe_path)]=sha(universe_path)
    universe=pd.read_csv(universe_path,low_memory=False)
    if universe.product_vt_symbol.duplicated().any() or len(universe)!=91 or set(universe.eligible.astype(int))!={1}:raise ValueError('frozen_full91_universe_invalid')
    products=set(universe.product_vt_symbol.astype(str))
    arms={arm:load_arm(arm,products,sources) for arm in ['E','F']}
    if not arms['E'][0].date.equals(arms['F'][0].date):raise ValueError('E_F_account_calendar_not_identical')
    annual=pd.DataFrame([row for arm,values in arms.items() for row in annual_rows(values[0],arm,values[4]['display_name'])])
    f_daily,f_trades,f_positions,_,f_summary=arms['F']
    raw_path=OUT/'stage005_anchor_plan/raw_signals.csv';sources[str(raw_path)]=sha(raw_path)
    raw=pd.read_csv(raw_path,low_memory=False)
    raw=raw.loc[pd.to_datetime(raw.signal_date).between(START,END) & raw.signal.fillna('').astype(str).ne('')].copy()
    raw['native_product']=raw.vt_symbol.map(lambda value:native_product(value,products))
    if 'product_vt_symbol' in raw and not raw.native_product.equals(raw.product_vt_symbol):raise ValueError('raw_signal_native_product_mismatch')
    actual_fills=f_trades.groupby('product_vt_symbol').size();actual_volume=f_trades.groupby('product_vt_symbol').volume.sum()
    pnl=f_positions.groupby('product_vt_symbol').net_pnl.sum();raw_counts=raw.groupby('native_product').size()
    product_results=universe[['exchange','product','product_vt_symbol']].copy()
    product_results['actual_fill_count']=product_results.product_vt_symbol.map(actual_fills).fillna(0).astype(int)
    product_results['actual_fill_volume_open_and_close']=product_results.product_vt_symbol.map(actual_volume).fillna(0.)
    product_results['net_pnl_daily_mtm']=product_results.product_vt_symbol.map(pnl).fillna(0.)
    product_results['raw_signal_count_data_only_prefetch']=product_results.product_vt_symbol.map(raw_counts).fillna(0).astype(int)
    product_results['raw_signal_scope']='data_only_completed_week_AM41_mapping_target_prefetch_not_actual_entry_orders'
    product_results['zero_fill_interpretation']='zero fills does not imply no signal; raw counts exclude exits rollovers sizing and portfolio state'
    require_close(product_results.actual_fill_count.sum(),len(f_trades),'full91_product_fill_conservation')
    require_close(product_results.net_pnl_daily_mtm.sum(),f_daily.account_equity.iloc[-1]-CAPITAL,'full91_product_pnl_conservation')
    require_close(product_results.raw_signal_count_data_only_prefetch.sum(),len(raw),'full91_raw_signal_count_conservation')
    sources[str(Path(__file__).resolve())]=sha(__file__)
    summary=dict(schema='stage007_weekly_full_market_comparison_v1',generated_at=datetime.now().astimezone().isoformat(),
        contract=dict(start=START,end=END,capital=CAPITAL,indicators='completed weekly; AM41 observations',half_r=False,C2=False,AI_selection=False,
                      E_universe='original19 same-data control',F_universe='91 frozen historically observed futures families; not a promise that all trade'),
        arms={arm:values[4] for arm,values in arms.items()},
        comparison=dict(ending_equity_F_minus_E=float(arms['F'][0].account_equity.iloc[-1]-arms['E'][0].account_equity.iloc[-1]),
            return_pct_F_minus_E=float(arms['F'][4]['metrics']['total_return_pct']-arms['E'][4]['metrics']['total_return_pct']),
            max_dd_pct_F_minus_E=float(arms['F'][4]['metrics']['max_dd_pct']-arms['E'][4]['metrics']['max_dd_pct']),
            sharpe_F_minus_E=float(arms['F'][4]['metrics']['sharpe']-arms['E'][4]['metrics']['sharpe'])),
        product_table=dict(rows=91,pnl_basis='sum actual daily contract net_pnl from 2020-01-01; daily MTM incl terminal unrealized, modeled slippage deducted, commission zero',
            net_pnl_sum=float(product_results.net_pnl_daily_mtm.sum()),raw_signal_source=str(raw_path),
            raw_signal_count_data_only_prefetch=len(raw),raw_signal_counts_are_actual_orders=False,
            zero_fills_does_not_imply_no_signal=True),
        validation='derived accounting/identity assertions passed; independent review status must be read separately',
        source_files_sha256=sources,decision='RESEARCH_ONLY_NO_PROMOTION',production_qualified=False,
        limitations=['Zero commission; modeled slippage does not establish real executable liquidity or capacity.',
            'Strict first-minute anchors and internal accounting do not establish strict PIT/OOS validity.',
            'Full market means the frozen91 family universe; listing history mapping daily data and41 completed observed weeks limit actual coverage.',
            'Weekly coverage and held/traded data audit limitations are retained per arm; missing/no-ready is not proof of no raw signal.',
            'Raw signal counts are a data-only prefetch plan and cannot be used as entry eligibility or inferred from zero fills.',
            'Inherited label note and deployable_pass are excluded from identity and promotion claims.'])
    annual,product_results=apply_final_review(arms,annual,product_results,summary,review_path,review_payload,backup_digests)
    ART.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage007_build_',dir=ART) as temporary:
        temp=Path(temporary);annual.to_csv(temp/NAMES[1],index=False);product_results.to_csv(temp/NAMES[2],index=False)
        plot_comparison(arms,temp/NAMES[0])
        summary['output_files_sha256']={name:sha(temp/name) for name in NAMES[:3]}
        (temp/NAMES[3]).write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for path,digest in sources.items():
            if sha(path)!=digest:raise ValueError('artifact_source_changed_during_build:'+path)
        for name in NAMES:
            if not (ART/name).is_file() or sha(ART/name)!=backup_digests[name]:raise ValueError('pre_review_artifact_changed_before_publication:'+name)
        for name in NAMES:os.rename(temp/name,ART/name)
    print(json.dumps(dict(status='artifacts_generated_from_completed_ledgers',outputs=[str(ART/name) for name in NAMES],
        E_path=arms['E'][4]['path'],F_path=arms['F'][4]['path'],F_diagnostic_modeled_products=f_summary['modeled_traded_product_count'],F_execution_audit_status=REJECTION,financial_replays=0),ensure_ascii=False))


def self_test():
    # 年度复利基数必须继承上一年末权益；2026必须标YTD，不能拿15万重复作分母。
    daily=pd.DataFrame(dict(date=pd.to_datetime(['2025-12-30','2025-12-31','2026-01-02']),
        account_equity=[180000.,200000.,190000.],net_pnl=[30000.,20000.,-10000.],
        trade_count=[1,1,1],slippage=[1.,2.,3.],commission=[0.,0.,0.]))
    rows=annual_rows(daily,'F','Synthetic arithmetic only')
    require_close(rows[0]['return_pct'],100/3,'synthetic_first_year_return')
    require_close(rows[1]['starting_equity'],200000,'synthetic_year_carry')
    require_close(rows[1]['return_pct'],-5,'synthetic_ytd_return')
    if rows[1]['period']!='2026 YTD':raise ValueError('synthetic_ytd_label')
    print('Synthetic annual arithmetic passed; no financial replay, no artifact generation.')

if __name__=='__main__':main()
