"""G data-only原19周线三均线raw信号首分钟预取计划；不执行任何金融回放。

复用已冻结纯reader/扫描/次日任务函数。容量41、真实完成周就绪21，完整设置
严格对照E9；唯一行为变化来自实际G类。候选仅用于补数据，不能当策略准入、
跳单或成交证明；退出、换月和加仓缺锚仍由实际严格路径暴露。
"""
from __future__ import annotations
from dataclasses import asdict,replace
from datetime import datetime
from pathlib import Path
import argparse,inspect,json,os,sqlite3,sys,tempfile
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))
from stage005_signal_anchor_plan import build_pure_reader,scan_raw_candidates,next_day_task,sha,write_json,STANDARD_TASK_COLUMNS

ORIGINAL19=frozenset('AP.CZCE CF.CZCE FG.CZCE MA.CZCE OI.CZCE SA.CZCE SH.CZCE SM.CZCE au.SHFE cu.SHFE fu.SHFE hc.SHFE jm.DCE lc.GFEX lh.DCE rb.SHFE ru.SHFE si.GFEX sp.SHFE'.split())
START,END='2020-01-01','2026-10-22'
CONTRACT=LINE/'stages/20261023_1446_stage008_three_ma_19_contract.md'
E9=LINE/'outputs/E_attempt009'


def assert_original19(products,preflight):
    values=list(products)
    if len(values)!=19 or set(values)!=ORIGINAL19 or preflight.get('universe_product_count')!=19 or set(preflight.get('universe_products',[]))!=ORIGINAL19:
        raise ValueError('original19_exact_pool_required')
    return sorted(values)


def assert_g_setting(setting):
    if int(setting.get('research_exact_array_manager_size',0))!=41:
        raise ValueError('G_capacity_must_remain_41')
    if tuple(setting.get(k) for k in ('ma_short','ma_mid','ma_long'))!=(5,10,20):
        raise ValueError('G_three_ma_must_be_5_10_20')
    if float(setting.get('capital_base',0))!=150000:
        raise ValueError('G_capital_must_be_150000')
    if any(setting.get(k) is not False for k in ('enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter')):
        raise ValueError('G_three_switches_must_be_disabled')


def resolve_configuration(data,start=START,end=END):
    """Actual profile/spec/live overrides链；不以类默认值替代已冻结设置。"""
    data=Path(data).resolve()
    if (start,end)!=(START,END):raise ValueError('G_frozen_window_required')
    vendor=Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
    sys.path[:0]=[str(ROOT),str(vendor),str(ROOT/'examples/portfolio_backtesting'),str(TOOLS)]
    os.environ.update(MPLCONFIGDIR='/private/tmp/weekly-research-mpl',TZ='Asia/Shanghai',
        OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0',
        OFFICIAL_LIVE_SIGNAL_INPUT_DIR=str(LINE/'outputs/empty_signals'),OFFICIAL_LIVE_OUTPUT_DIR=str(LINE/'outputs/empty_signals'))
    import time
    time.tzset()
    from vnpy.trader.setting import SETTINGS
    SETTINGS.update({'log.file':False,'log.console':False,'log.active':False})
    import contract_metadata as cm
    cm.ALL_FUTURES_CONTRACT_METADATA_PATH=data/'metadata.csv'
    import main_contract_mapping as mm
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    from weekly_adapter import completed_weeks
    from stage008_three_ma import three_ma_weekly_strategy_class
    preflight=json.loads((E9/'preflight.json').read_text())
    reference=json.loads((E9/'actual_strategy_settings.json').read_text())
    if len(reference)!=1 or reference[0]['engine_capital']!=150000:raise ValueError('E9_reference_invalid')
    official=s901.build_official_live_strategy_overrides()
    # Retain official original19 universe path. Never substitute stage005 full91.
    live={**official,'mapping_csv_path':str(data/'mapping.csv'),
          'enable_stage847_half_r_stop_retry':False,'enable_stage827_intraday_c2_stop':False,'enable_ai_product_pool_filter':False}
    products=mm.load_product_universe_symbols(live['product_universe_csv_path'])
    assert_original19(products,preflight)
    metadata=mm.build_contract_metadata(mapping_path=data/'mapping.csv',supported_symbols=products)
    assert_original19(metadata['product_symbols'],preflight)
    calendar=sorted(str(d)[:10] for d in pd.read_csv(data/'mapping.csv').date.unique())
    old_start,old_end=s901.s847.START,s901.s847.END
    try:
        s901.s847.START=pd.Timestamp(start);s901.s847.END=pd.Timestamp(end)
        profile=s901.s847._c9_profile(metadata)
    finally:s901.s847.START=old_start;s901.s847.END=old_end
    spec=profile['spec']
    capital=replace(spec.capital,variant=s901.OFFICIAL_LIVE_PROFILE_NAME,
        label=f'{s901.OFFICIAL_LIVE_CAPITAL_LABEL} {s901.OFFICIAL_LIVE_ALIAS} live default',
        account_capital=s901.OFFICIAL_LIVE_CAPITAL,c3_capital=s901.OFFICIAL_LIVE_CAPITAL,
        note=f'{spec.capital.note} | Stage901 official live default operator override. C9 is promoted to live default by explicit operator request; no parameter search.')
    spec=replace(spec,capital=capital,overrides={**spec.overrides,**live},profile=s901.OFFICIAL_LIVE_PROFILE_NAME)
    base=dict(s901.s847.s513._c3_overrides(pd.Timestamp(start).to_pydatetime()))
    setting=s901.s847.s827.s772._build_setting(metadata=metadata,spec=spec,base_c3_overrides=base,start=pd.Timestamp(start))
    assert_g_setting(setting)
    if setting!=reference[0]['setting']:
        changed=[k for k in sorted(set(setting)|set(reference[0]['setting'])) if setting.get(k)!=reference[0]['setting'].get(k)]
        raise ValueError('G_settings_differ_from_E9:'+','.join(changed))
    strategy_class=three_ma_weekly_strategy_class(profile['strategy_cls'],completed_weeks(calendar))
    reader,effective=build_pure_reader(strategy_class,setting)
    assert_g_setting(effective)
    preload=max(s901.s847.s827.s772._preload_for_start(pd.Timestamp(start)),pd.Timestamp(start)-pd.Timedelta(days=365))
    functions=[profile['strategy_cls']._generate_signal,profile['strategy_cls']._build_history_df,
        s901.s847._c9_profile,s901.s847.s827.s772._build_setting,s901.build_official_live_strategy_overrides,
        s901.s847.s513._c3_overrides,mm.build_contract_metadata,three_ma_weekly_strategy_class,
        strategy_class._generate_signal,strategy_class._build_history_df,completed_weeks,
        build_pure_reader,scan_raw_candidates,next_day_task]
    paths={Path(inspect.getsourcefile(f)).resolve() for f in functions}
    paths.update([E9/'preflight.json',E9/'actual_strategy_settings.json',Path(live['product_universe_csv_path']).resolve(),CONTRACT,Path(__file__).resolve()])
    sources={str(p):sha(p) for p in paths}
    return reader,metadata,calendar,dict(setting=setting,effective_parameters=effective,spec=asdict(spec),
        universe=sorted(products),array_manager_size=41,ready_observed_weeks=21,preload_start=str(preload)[:10],
        base_profile_class=profile['strategy_cls'].__name__,actual_signal_class=strategy_class.__name__,
        E9_setting_exact_match=True,legacy_ma_extra_long_unused=True,
        configuration_chain='Stage847._c9_profile -> Stage901 capital/live overrides (original19) -> Stage772._build_setting(metadata,spec,Stage513._c3_overrides(start),start) -> actual G three_ma_weekly_strategy_class -> Template parameter resolution; no constructors',
        method_sources=sources)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=LINE/'outputs/stage005_data')
    parser.add_argument('--out',type=Path,default=LINE/'outputs/stage008_anchor_plan')
    args=parser.parse_args();data=args.data.resolve();out=args.out.resolve()
    if out.exists():raise ValueError('immutable_output_already_exists:'+str(out))
    manifest_path=data/'completed_manifest.json'
    data_manifest=json.loads(manifest_path.read_text())
    inputs={str(manifest_path):sha(manifest_path),**data_manifest['files']}
    for path,digest in inputs.items():
        if sha(path)!=digest:raise ValueError('completed_data_changed:'+path)
    reader,metadata,calendar,configuration=resolve_configuration(data)
    inputs.update(configuration['method_sources'])
    from vnpy.trader.constant import Exchange,Interval
    from vnpy.trader.object import BarData
    from vnpy.trader.utility import ArrayManager
    from weekly_adapter import completed_weeks
    from stage008_three_ma import ThreeMaWeeklyArrayManager
    from stage005_sessions import canonical_open_timestamp
    for f in (ThreeMaWeeklyArrayManager,canonical_open_timestamp):
        p=Path(inspect.getsourcefile(f)).resolve();inputs[str(p)]=sha(p)
    mapping=pd.read_csv(data/'mapping.csv').fillna('')
    mapping=mapping[mapping.continuous_symbol_vt.isin(ORIGINAL19)]
    if mapping.duplicated(['date','continuous_symbol_vt']).any():raise ValueError('duplicate_mapping_product_day')
    mapping_by_product={p:dict(zip(g.date,g.main_contract_vt)) for p,g in mapping.groupby('continuous_symbol_vt')}
    weeks=completed_weeks(calendar);task_calendar=[d for d in calendar if d<=END]
    counters=dict(real_daily_bars=0,history_function_calls=0,signal_function_calls=0)
    candidates=[];tasks=[];terminal=[]
    db=sqlite3.connect(f'file:{data/"daily.sqlite"}?mode=ro&immutable=1',uri=True)
    until=(pd.Timestamp(END)+pd.Timedelta(days=1)).date().isoformat()
    try:
        for i,symbol in enumerate(metadata['vt_symbols']):
            code,exchange=symbol.split('.');product=metadata['source_symbol_by_contract'][symbol]
            if product not in ORIGINAL19:raise ValueError('unexpected_non_original19_contract:'+symbol)
            am=ThreeMaWeeklyArrayManager(ArrayManager(41),weeks)
            query=db.execute("select datetime,open_price,high_price,low_price,close_price,volume,turnover,open_interest from dbbardata where symbol=? and exchange=? and interval='d' and datetime>=? and datetime<? order by datetime",(code,exchange,configuration['preload_start'],until))
            def bars():
                for stamp,o,h,l,c,v,t,oi in query:
                    yield BarData(symbol=code,exchange=Exchange(exchange),datetime=datetime.fromisoformat(str(stamp)),interval=Interval.DAILY,gateway_name='READ_ONLY_DAILY',open_price=float(o),high_price=float(h),low_price=float(l),close_price=float(c),volume=float(v),turnover=float(t),open_interest=float(oi))
            for row in scan_raw_candidates(symbol,bars(),am,reader,mapping_by_product.get(product,{}),START,END,counters):
                if row['observed_weeks']<21:raise ValueError('G_premature_signal')
                candidates.append(dict(row,product_vt_symbol=product))
                task=next_day_task(symbol,row['signal_date'],task_calendar,canonical_open_timestamp)
                if task is None:terminal.append(row)
                else:tasks.append(task)
            if (i+1)%100==0:print(json.dumps(dict(symbols_done=i+1,raw_signals=len(candidates),**counters)),flush=True)
    finally:db.close()
    for path,digest in inputs.items():
        if sha(path)!=digest:raise ValueError('input_changed_during_scan:'+path)
    frame=pd.DataFrame(tasks,columns=STANDARD_TASK_COLUMNS).drop_duplicates().sort_values(['trading_day','vt_symbol'])
    summary=dict(status='completed_data_only_prefetch_plan',purpose='raw_signal_superset_for_download_only_not_engine_admission',
        start=START,end=END,universe_product_count=19,mapped_contract_count=len(metadata['vt_symbols']),raw_signals=len(candidates),
        unique_tasks=len(frame),terminal_signal_without_next_day=terminal,**counters,
        financial_replays=0,strategy_constructors=0,account_instances=0,position_simulations=0,order_simulations=0,
        on_bars_calls=0,run_backtesting_calls=0,rebalance_calls=0,order_api_calls=0,network_calls=0,
        actual_array_manager_size=41,ready_observed_weeks=21,E9_setting_exact_match=True,inputs_unchanged=True,
        caveats=['data-only raw candidates are not orders or strategy admission conditions',
            'strict exits rollovers and add-ons may require additional real anchors',
            'daily OHLC is only used for indicators; never supplied as execution price',
            'no volume-based signal skip or timestamp switch; final actual-fill execution audit is separate'])
    out.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix=out.name+'.pending-',dir=out.parent))
    frame.to_csv(temporary/'tasks.csv',index=False)
    pd.DataFrame(candidates,columns=['vt_symbol','signal_date','signal','observed_weeks','breakout','risk_mode','product_vt_symbol']).to_csv(temporary/'raw_signals.csv',index=False)
    write_json(temporary/'configuration.json',configuration)
    write_json(temporary/'input_manifest.json',inputs)
    write_json(temporary/'summary.json',summary)
    if out.exists():raise ValueError('output_created_concurrently:'+str(out))
    temporary.rename(out)
    print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)

if __name__=='__main__':main()
