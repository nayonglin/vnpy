"""Stage005 data-only周线raw信号 -> 下一交易日首分钟下载任务。

本工具不构造引擎、不调用策略构造器/回调/账户/订单/仓位或绩效函数。
由实际C9 profile + live overrides + _build_setting解析完整配置，冻结为只读
纯信号对象；只使用_build_history_df/_generate_signal及其纯指标辅助函数。
任务是保守行情预取集合，不得作为严格回放的准入或跳单条件。它不覆盖无新
raw信号的退出、换月、加仓等路径，严格引擎真实触发的缺锚仍须另补。
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
import argparse, hashlib, inspect, json, os, sqlite3, sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
STANDARD_TASK_COLUMNS=['vt_symbol','trading_day','natural_date','start','end_exclusive','session']
FORBIDDEN_MEMBERS={
    'on_bars','on_bar','on_init','on_start','on_stop','run_backtesting','rebalance_portfolio',
    'open_position','close_position','buy','sell','short','cover','send_order','cancel_order',
    'set_target','get_target','get_pos','get_all_positions','get_account','calculate_result',
    'strategy_engine','engine','states','pos_data','target_data','orders','active_orderids',
    'base_capital','settled_balance','portfolio_equity_high_water','equity_start_positions',
}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def write_json(path,payload):
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n')


def build_pure_reader(strategy_class,setting):
    """匹配Template.update_setting的参数解析，跳过所有__init__，禁止执行路径。"""
    parameters=set(strategy_class.parameters)
    non_strategy={'account_capital','c3_capital'}
    unknown=set(setting)-parameters-non_strategy
    if unknown:raise ValueError('unknown_setting:'+','.join(sorted(unknown)))
    effective={name:setting[name] if name in setting else getattr(strategy_class,name) for name in strategy_class.parameters}
    def readonly_set(self,name,value):raise RuntimeError('data_only_reader_read_only:'+name)
    def guarded_get(self,name):
        if name in FORBIDDEN_MEMBERS:raise RuntimeError('data_only_forbidden_member:'+name)
        return object.__getattribute__(self,name)
    pure_class=type('DataOnlyRawSignalReader',(strategy_class,),{'__setattr__':readonly_set,'__getattribute__':guarded_get})
    reader=object.__new__(pure_class)
    for name,value in effective.items():object.__setattr__(reader,name,value)
    # No variables/engine/account/positions/orders are constructed.
    return reader,effective


def next_day_task(symbol,signal_day,calendar,opener):
    dates=sorted({str(day)[:10] for day in calendar})
    index=bisect_right(dates,str(signal_day)[:10])
    if index>=len(dates):return None
    next_day=dates[index]
    stamp=pd.Timestamp(opener(symbol,next_day,dates))
    return dict(vt_symbol=symbol,trading_day=next_day,natural_date=stamp.strftime('%Y-%m-%d'),
                start=stamp.strftime('%H:%M'),end_exclusive=(stamp+pd.Timedelta(minutes=1)).strftime('%H:%M'),
                session='day' if stamp.hour<18 else 'night')


def scan_raw_candidates(symbol,bars,am,reader,target_by_date,start,end,counters=None):
    """仅真实逐合约日线推进指标，不读取/推演任何账户状态。"""
    for bar in bars:
        am.update_bar(bar)
        if counters is not None:counters['real_daily_bars']+=1
        day=bar.datetime.strftime('%Y-%m-%d')
        if not (start<=day<=end) or target_by_date.get(day)!=symbol or not am.fresh or not am.inited:continue
        history=reader._build_history_df(am)
        signal=reader._generate_signal(am,history)
        if counters is not None:
            counters['history_function_calls']+=1;counters['signal_function_calls']+=1
        if not signal.get('signal'):continue
        yield dict(vt_symbol=symbol,signal_date=day,signal=str(signal['signal']),observed_weeks=int(am.count),
                   breakout=bool(signal.get('breakout')),risk_mode=str(signal.get('risk_mode','')))


def resolve_configuration(data,start,end):
    """只解析run_stage005_full_market.py F组实际参数构造链，无引擎/回调。"""
    vendor=Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
    sys.path[:0]=[str(ROOT),str(vendor),str(ROOT/'examples/portfolio_backtesting'),str(Path(__file__).parent)]
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
    from weekly_adapter import weekly_strategy_class,completed_weeks
    official=s901.build_official_live_strategy_overrides()
    live={**official,'mapping_csv_path':str(data/'mapping.csv'),'product_universe_csv_path':str(data/'universe.csv'),
          'enable_stage847_half_r_stop_retry':False,'enable_stage827_intraday_c2_stop':False,'enable_ai_product_pool_filter':False}
    products=mm.load_product_universe_symbols(live['product_universe_csv_path'])
    metadata=mm.build_contract_metadata(mapping_path=data/'mapping.csv',supported_symbols=products)
    calendar=sorted(pd.read_csv(data/'mapping.csv').date.unique())
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
    if any(setting.get(k) is not False for k in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop','enable_ai_product_pool_filter']):raise ValueError('contract_flags_not_disabled')
    strategy_class=weekly_strategy_class(profile['strategy_cls'],completed_weeks(calendar))
    reader,effective=build_pure_reader(strategy_class,setting)
    exact=int(effective.get('research_exact_array_manager_size') or 0)
    if exact!=41:raise ValueError('unexpected_actual_exact_AM_size:'+str(exact))
    preload=max(s901.s847.s827.s772._preload_for_start(pd.Timestamp(start)),pd.Timestamp(start)-pd.Timedelta(days=365))
    sources={str(Path(inspect.getsourcefile(f)).resolve()):sha(inspect.getsourcefile(f)) for f in [profile['strategy_cls']._generate_signal,profile['strategy_cls']._build_history_df,s901.s847._c9_profile,s901.s847.s827.s772._build_setting,s901.build_official_live_strategy_overrides,s901.s847.s513._c3_overrides,mm.build_contract_metadata,weekly_strategy_class]}
    return reader,metadata,calendar,dict(setting=setting,effective_parameters=effective,spec=asdict(spec),
        universe=products,array_manager_size=exact,preload_start=str(preload)[:10],
        configuration_chain='Stage847._c9_profile -> Stage901 capital/live overrides -> Stage772._build_setting(metadata, spec, Stage513._c3_overrides(start), start) -> Template parameter resolution; no constructors',
        method_sources=sources)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=LINE/'outputs/stage005_data');parser.add_argument('--out',type=Path,default=LINE/'outputs/stage005_anchor_plan');args=parser.parse_args()
    start,end='2020-01-01','2026-10-22';data=args.data.resolve();out=args.out.resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('immutable_output_already_exists:'+str(out))
    data_manifest=json.loads((data/'completed_manifest.json').read_text())
    for path,digest in data_manifest['files'].items():
        if sha(path)!=digest:raise ValueError('completed_data_changed:'+path)
    reader,metadata,calendar,configuration=resolve_configuration(data,start,end)
    from vnpy.trader.constant import Exchange,Interval
    from vnpy.trader.object import BarData
    from vnpy.trader.utility import ArrayManager
    from weekly_adapter import WeeklyArrayManager,completed_weeks
    from stage005_sessions import canonical_open_timestamp
    mapping=pd.read_csv(data/'mapping.csv').fillna('')
    mapping=mapping[mapping.continuous_symbol_vt.isin(metadata['product_symbols'])]
    mapping_by_product={p:dict(zip(g.date,g.main_contract_vt)) for p,g in mapping.groupby('continuous_symbol_vt')}
    weeks=completed_weeks(calendar);counters=dict(real_daily_bars=0,history_function_calls=0,signal_function_calls=0)
    candidates=[];tasks=[];terminal_signals=[];before=sha(data/'daily.sqlite')
    db=sqlite3.connect(f'file:{data/"daily.sqlite"}?mode=ro&immutable=1',uri=True)
    until=(pd.Timestamp(end)+pd.Timedelta(days=1)).date().isoformat()
    try:
        for i,symbol in enumerate(metadata['vt_symbols']):
            code,exchange=symbol.split('.');product=metadata['source_symbol_by_contract'][symbol]
            am=WeeklyArrayManager(ArrayManager(configuration['array_manager_size']),weeks)
            query=db.execute("select datetime,open_price,high_price,low_price,close_price,volume,turnover,open_interest from dbbardata where symbol=? and exchange=? and interval='d' and datetime>=? and datetime<? order by datetime",(code,exchange,configuration['preload_start'],until))
            def bars():
                for stamp,o,h,l,c,v,t,oi in query:
                    yield BarData(symbol=code,exchange=Exchange(exchange),datetime=datetime.fromisoformat(str(stamp)),interval=Interval.DAILY,gateway_name='READ_ONLY_DAILY',open_price=float(o),high_price=float(h),low_price=float(l),close_price=float(c),volume=float(v),turnover=float(t),open_interest=float(oi))
            for row in scan_raw_candidates(symbol,bars(),am,reader,mapping_by_product.get(product,{}),start,end,counters):
                candidates.append(dict(row,product_vt_symbol=product))
                task=next_day_task(symbol,row['signal_date'],[d for d in calendar if d<=end],canonical_open_timestamp)
                if task is None:terminal_signals.append(row)
                else:tasks.append(task)
            if (i+1)%250==0:print(json.dumps(dict(symbols_done=i+1,raw_signals=len(candidates),**counters)),flush=True)
    finally:db.close()
    if sha(data/'daily.sqlite')!=before:raise ValueError('daily_source_changed')
    out.mkdir(parents=True,exist_ok=True)
    task_frame=pd.DataFrame(tasks,columns=STANDARD_TASK_COLUMNS).drop_duplicates().sort_values(['trading_day','vt_symbol'])
    task_frame.to_csv(out/'tasks.csv',index=False)
    pd.DataFrame(candidates).to_csv(out/'raw_signals.csv',index=False)
    write_json(out/'configuration.json',configuration)
    inputs={str(data/'completed_manifest.json'):sha(data/'completed_manifest.json'),**data_manifest['files'],str(Path(__file__).resolve()):sha(__file__),**configuration['method_sources']}
    write_json(out/'input_manifest.json',inputs)
    summary=dict(status='completed_data_only_prefetch_plan',purpose='raw_signal_superset_for_download_only_not_engine_admission',
        start=start,end=end,universe_product_count=len(metadata['product_symbols']),mapped_contract_count=len(metadata['vt_symbols']),
        raw_signals=len(candidates),unique_tasks=len(task_frame),terminal_signal_without_next_day=terminal_signals,
        **counters,financial_replays=0,strategy_constructors=0,account_instances=0,position_simulations=0,order_simulations=0,
        on_bars_calls=0,run_backtesting_calls=0,rebalance_calls=0,order_api_calls=0,network_calls=0,
        actual_array_manager_size=configuration['array_manager_size'],database_unchanged=True,
        caveats=['download superset only; does not establish actual orders','strict exits rollovers and add-ons may still request more anchors','daily OHLC used only for completed-week indicators; never supplied as execution price'])
    write_json(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)

if __name__=='__main__':main()
