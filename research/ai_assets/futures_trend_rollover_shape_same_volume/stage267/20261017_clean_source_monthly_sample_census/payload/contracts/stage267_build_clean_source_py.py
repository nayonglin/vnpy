"""One fixed, retrospective Floor35 source; no model fitting or production access."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

FROZEN_SITE = Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
VENDOR = Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
if not FROZEN_SITE.is_dir() or not VENDOR.is_dir():
    raise RuntimeError('frozen_runtime_missing')
sys.path.insert(0,str(FROZEN_SITE))
import numpy as np
import pandas as pd

from stage263_build_expanded_source import identity, json_value
from stage267_clean_source_adapter import CleanSource, rename_metadata

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_rollover_shape_same_volume'
OUTPUT=LINE/'outputs/stage267_clean_training_source'
CLEAN=LINE/'outputs/stage266_clean_daily/clean_daily.sqlite'
CALENDAR=LINE/'outputs/stage265_deep_daily/rqalpha/trading_dates.npy'
PROTOCOL=LINE/'stages/20261017_1952_stage267_clean_source_protocol.md'
START=pd.Timestamp('2010-01-04')
END=pd.Timestamp('2026-10-14')
EXPECTED_CLEAN='a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711'


def main():
    if sys.argv[1:] not in [['--preflight'],['--run']]:
        raise SystemExit('Use --preflight or --run; no sweep/parameter arguments.')
    run=sys.argv[1]=='--run'
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if run and ((OUTPUT/'engine.log').exists() or (OUTPUT/'source_summary.json').exists()):
        raise SystemExit('Existing run: refusing overwrite or repeated financial replay.')
    os.chdir(ROOT)
    os.environ.update(QT_QPA_PLATFORM='offscreen',TZ='Asia/Shanghai',
        OFFICIAL_LIVE_OUTPUT_DIR=str(OUTPUT),OFFICIAL_LIVE_SIGNAL_INPUT_DIR=str(OUTPUT),
        OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0')
    if hasattr(time,'tzset'):time.tzset()
    project=ROOT/'examples/portfolio_backtesting'
    sys.path[:0]=[str(ROOT),str(VENDOR),str(project)]
    import vnpy_portfoliostrategy
    import vnpy_portfoliostrategy.backtesting as vendor_engine
    import run_qmt_roll_backtest as roll
    import run_qmt_alignment_backtest as artifacts
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    import qmt_roll_portfolio_strategy as strategy_module
    from qmt_universe import VT_SYMBOLS
    from main_contract_mapping import build_contract_metadata,get_preferred_mapping_path
    from vnpy.trader.constant import Exchange,Interval
    from vnpy.trader.object import BarData
    from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO,CORR20_06_08_FLOOR35_OVERRIDES
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    assert_stage196_database_sentinels()
    if not Path(vnpy_portfoliostrategy.__file__).resolve().is_relative_to(VENDOR):
        raise RuntimeError('wrong_portfolio_vendor')
    inputs={name:identity(path) for name,path in dict(clean=CLEAN,primary_database=ROOT/'.vntrader/database.db',
        mapping=get_preferred_mapping_path(),calendar=CALENDAR,pairwise_model=pairwise.DEFAULT_MODEL_PATH,
        pairwise_summary=pairwise.DEFAULT_SUMMARY_PATH,protocol=PROTOCOL).items()}
    if inputs['clean']['sha256']!=EXPECTED_CLEAN:raise RuntimeError('clean_store_changed')
    calendar=pd.to_datetime(np.load(CALENDAR,allow_pickle=False).astype(str),format='%Y%m%d')
    source=CleanSource(CLEAN,get_preferred_mapping_path(),VT_SYMBOLS,start=START,end=END,calendar=calendar)
    original_metadata=build_contract_metadata(supported_symbols=VT_SYMBOLS)
    metadata=rename_metadata(original_metadata,source.info)
    overrides={**CORR20_06_08_FLOOR35_OVERRIDES,'trade_start_date':str(START.date())}
    settings=roll.build_roll_setting(metadata['margin_ratios'],risk_ratio=BASE_RISK_RATIO,strategy_overrides=overrides)
    am_size=max(int(settings['ma_extra_long'])+int(settings['donchian_entry_period'])+20,
                int(settings.get('array_manager_size_floor',strategy_module.QmtRollPortfolioStrategy.array_manager_size_floor)))
    coverage=source.coverage(warmup_window=am_size)
    coverage140=source.coverage(warmup_window=140)
    preflight=dict(status='clean_source_adapter_preflight',financial_replays=0,model_fits=0,
        period=[str(START.date()),str(END.date())],products=list(VT_SYMBOLS),
        contract_epochs=len(source.info),source_calendar_days=len(source.calendar),real_daily_bar_count=source.raw_row_count,
        mapped_product_days=int(coverage.mapped.sum()),real_main_bar_days=int(coverage.real_main_bar.sum()),
        am_size=am_size,warmup_ready_product_days=int(coverage.observed.sum()),
        extra_conservative_140_ready_days=int(coverage140.observed.sum()),inputs=inputs,
        runtime=dict(python=sys.executable,portfolio_package=vnpy_portfoliostrategy.__file__,
            numerical_stack={p:importlib.metadata.version(p) for p in ['pandas','numpy','scikit-learn','joblib']}))
    (OUTPUT/'preflight.json').write_text(json.dumps(preflight,ensure_ascii=False,indent=2,default=json_value)+'\n')
    print(json.dumps({k:v for k,v in preflight.items() if k not in ['inputs','runtime','products']},ensure_ascii=False),flush=True)
    if not run:return
    # These files are private research input views; the original mapping is unchanged.
    mapping_path=OUTPUT/'research_epoch_mapping.csv'
    source.mapping.to_csv(mapping_path,index=False)
    source.info.to_csv(OUTPUT/'contract_epoch_identity.csv',index=False)
    pd.DataFrame({'date':calendar[(calendar>=START)&(calendar<=pd.Timestamp('2026-12-31'))]}).to_csv(OUTPUT/'source_calendar.csv',index=False)
    current_day=[START]
    pairwise_calls=[]
    def pairwise_loader(vt_symbol):
        view=source.pairwise_bars(vt_symbol,current_day[0])
        pairwise_calls.append(dict(date=str(current_day[0].date()),research_symbol=vt_symbol,rows=len(view),
            max_input_date=str(view.date.max().date()),open_oi_missing_rows=int(view.open_oi.isna().sum())))
        return view
    pairwise.load_contract_bars=pairwise_loader
    strategy_module.build_contract_metadata=lambda *args,**kwargs:metadata
    roll.get_preferred_mapping_path=lambda:mapping_path
    deferred=[]
    fill_audit=[]
    class CleanEngine(roll.SameDayCloseBacktestingEngine):
        def load_data(self):source.fill_engine(self,BarData,Exchange,Interval)
        def cross_limit_order_on_close(self):
            # The inherited stale bars may carry valuation, but cannot authorize fills.
            absent={key:order for key,order in self.active_limit_orders.items()
                    if (self.datetime,order.vt_symbol) not in self.history_data}
            for key,order in absent.items():
                deferred.append(dict(date=self.datetime.date().isoformat(),order_id=key,vt_symbol=order.vt_symbol,
                    pos=self.strategy.get_pos(order.vt_symbol),target=self.strategy.get_target(order.vt_symbol),
                    limit_price=float(order.price),reason='no_real_clean_bar_today'))
                self.active_limit_orders.pop(key)
            before=set(self.trades)
            try:super().cross_limit_order_on_close()
            finally:
                self.active_limit_orders.update({key:order for key,order in absent.items() if order.is_active()})
            for key in set(self.trades)-before:
                trade=self.trades[key]
                if (self.datetime,trade.vt_symbol) not in self.history_data:
                    raise RuntimeError('stale_bar_fill')
                fill_audit.append(dict(date=self.datetime.date().isoformat(),vt_symbol=trade.vt_symbol,trade_id=key))
    def build_engine(*,preload_start,backtest_end,capital,product_universe_csv_path=None):
        engine=CleanEngine()
        engine.set_parameters(vt_symbols=metadata['vt_symbols'],interval=Interval.DAILY,start=preload_start,
            end=backtest_end,rates=metadata['rates'],slippages=metadata['slippages'],sizes=metadata['sizes'],
            priceticks=metadata['priceticks'],capital=capital)
        return engine,metadata
    roll.build_backtest_engine=build_engine
    class CleanFloor35(strategy_module.QmtRollPortfolioStrategy):
        def on_bars(self,bars):
            if not bars:return
            day=pd.Timestamp(next(iter(bars.values())).datetime).tz_localize(None).normalize()
            current_day[0]=day
            for vt,pos in self.pos_data.items():
                if pos and vt not in bars:
                    source.missing_held.add((str(day.date()),self.source_symbol_by_contract[vt]))
            super().on_bars(bars)
            if len(source.calendar) and day.day==1:
                print(f'progress {day.date()}',flush=True)
    roll.QmtRollPortfolioStrategy=CleanFloor35
    files=[Path(__file__),Path(__file__).with_name('stage267_clean_source_adapter.py'),
        project/'run_qmt_roll_backtest.py',project/'qmt_roll_portfolio_strategy.py',
        project/'run_qmt_alignment_backtest.py',project/'qmt_universe.py',project/'main_contract_mapping.py',
        project/'contract_metadata.py',project/'qmt_roll_ai_selection_pairwise_runtime.py',
        project/'build_qmt_roll_ai_position_training_samples.py',
        project/'run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest.py',
        Path(vendor_engine.__file__),VENDOR/'vnpy_portfoliostrategy/template.py']
    code_inputs=[identity(p) for p in files]
    started=datetime.now().astimezone().isoformat(); began=time.monotonic()
    with (OUTPUT/'engine.log').open('w',buffering=1) as log,redirect_stdout(log),redirect_stderr(log):
        engine,daily,statistics=roll.run_backtest(risk_ratio=BASE_RISK_RATIO,strategy_overrides=overrides,
            analysis_start=START.to_pydatetime(),analysis_end=END.to_pydatetime(),preload_start=START.to_pydatetime(),
            capital=200000,save_artifacts=False,include_start_year_sweep=False,
            file_prefix='stage267_clean_uniform_source',chart_title='Stage267 retrospective source')
        if daily is None or daily.empty:raise RuntimeError('empty_source')
        if pd.Timestamp(engine.datetime).tz_localize(None).normalize()!=END:raise RuntimeError('incomplete_replay')
        positions=artifacts.build_positions_df(engine)
        candidates=artifacts.build_entry_candidate_snapshots_df(engine)
        trades=artifacts.build_trades_df(engine)
        totals=positions.groupby('date').net_pnl.sum()
        ledger=daily.net_pnl.copy();ledger.index=pd.to_datetime(ledger.index).date
        max_error=float((ledger-totals.reindex(ledger.index).fillna(0)).abs().max())
        if max_error>1e-6:raise RuntimeError(f'attribution_mismatch:{max_error}')
        for name,frame in dict(position_changes=positions,entry_candidate_snapshots=candidates,trades=trades).items():
            frame.to_csv(OUTPUT/f'source_{name}.csv',index=False)
        daily.reset_index().to_csv(OUTPUT/'source_daily.csv',index=False)
    log_text=(OUTPUT/'engine.log').read_text()
    if any(x in log_text for x in ['触发异常','Traceback (most recent call last)']):raise RuntimeError('engine_exception')
    coverage=source.coverage(warmup_window=am_size)
    coverage.to_csv(OUTPUT/'product_coverage.csv',index=False)
    coverage140=source.coverage(warmup_window=140)
    coverage140.to_csv(OUTPUT/'product_coverage_extra140.csv',index=False)
    pd.DataFrame(pairwise_calls).to_csv(OUTPUT/'pairwise_input_audit.csv',index=False)
    pd.DataFrame(deferred,columns=['date','order_id','vt_symbol','pos','target','limit_price','reason']).to_csv(OUTPUT/'deferred_missing_real_bar_orders.csv',index=False)
    pd.DataFrame(fill_audit).to_csv(OUTPUT/'real_bar_fill_audit.csv',index=False)
    for item in inputs.values():
        if identity(item['path'])['sha256']!=item['sha256']:raise RuntimeError('input_changed')
    for item in code_inputs:
        if identity(item['path'])['sha256']!=item['sha256']:raise RuntimeError('code_changed')
    summary=dict(status='retrospective_fixed_policy_clean_source_not_upstream_PIT',
        started_at=started,completed_at=datetime.now().astimezone().isoformat(),elapsed_seconds=time.monotonic()-began,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_kind='stage263_floor35_200k_risk0045_clean_adapter',analysis_start=str(START.date()),analysis_end=str(END.date()),
        inputs=inputs,source_files=code_inputs,strategy_overrides=overrides,capital=200000,risk_ratio=BASE_RISK_RATIO,
        actual_am_size=am_size,upstream_model_PIT_certified=False,upstream_model_train_dates=['2020-09-17','2022-12-08'],
        retrospective_fixed_policy=True,model_fits=0,financial_replays=1,ctps_connected=0,order_api_calls=0,
        real_daily_bar_count=len(engine.history_data),contract_epoch_count=len(source.info),
        position_rows=len(positions),candidate_rows=len(candidates),trade_rows=len(trades),
        position_daily_max_abs_error=max_error,stale_bar_fills=0,deferred_missing_real_bar_order_attempts=len(deferred),
        missing_held_product_days=len(source.missing_held),pairwise_input_calls=len(pairwise_calls),
        statistics=statistics,runtime=preflight['runtime'],
        outputs={p.name:identity(p) for p in OUTPUT.glob('*.csv')},
        boundaries=['Retrospective frozen upstream model, not historical point-in-time/OOS certification.',
          'No source bars before 2010; original AM and warmup retained.',
          'Unobserved bars are never synthesized for signals or fills; prior prices carry valuation only.',
          'Missing data and account history can affect subsequent conditional source PNL; not independent product returns.',
          'Close-only rows are allowed; opening OI is never fabricated.',
          'Original fixed strategy may zero undefined derived statistics as before; 140-day extra coverage reported separately.'])
    (OUTPUT/'source_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=json_value)+'\n')
    print(json.dumps({k:summary[k] for k in ['status','elapsed_seconds','real_daily_bar_count','position_rows','candidate_rows','trade_rows','position_daily_max_abs_error','stale_bar_fills','deferred_missing_real_bar_order_attempts']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
