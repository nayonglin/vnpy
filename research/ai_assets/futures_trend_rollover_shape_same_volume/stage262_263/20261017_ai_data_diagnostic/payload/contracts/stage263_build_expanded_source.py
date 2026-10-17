"""Research-only, one-source floor35 replay; no production mutation or CTP."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

# Use the restored model's original numerical stack before importing pandas/numpy.
FROZEN_SITE = Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
if not FROZEN_SITE.is_dir():
    raise RuntimeError('frozen_numerical_runtime_missing')
sys.path.insert(0, str(FROZEN_SITE))
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume'
OUTPUT = LINE / 'outputs/stage263_ai_data_expansion'
START = pd.Timestamp('2015-01-01')
END = pd.Timestamp('2026-10-08')
VENDOR = Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')


def epoch_start(dates, candidate_date):
    """Use only observed dates at/before candidate; a >=5-year gap starts an epoch."""
    candidate = pd.Timestamp(candidate_date).normalize()
    valid = pd.DatetimeIndex(dates).tz_localize(None).normalize()
    valid = valid[valid <= candidate].drop_duplicates().sort_values()
    if valid.empty:
        return candidate
    start = valid[0]
    for previous, current in zip(valid[:-1], valid[1:]):
        if current >= previous + pd.DateOffset(years=5):
            start = current
    return pd.Timestamp(start)


def filter_epoch_history(frame, candidate_date, start):
    if frame.empty:
        return frame.copy()
    dates = pd.to_datetime(frame['date']).dt.tz_localize(None).dt.normalize()
    return frame.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(candidate_date))].copy().reset_index(drop=True)


def reset_contract_epoch(strategy, vt_symbol, current_bar):
    """Never erase an economic position to resolve a reused contract identifier."""
    failures = []
    for field in ('pos_data', 'target_data', 'equity_start_positions'):
        if int(getattr(strategy, field).get(vt_symbol, 0)) != 0:
            failures.append(field)
    for field in ('pending_close_lots', 'pending_close_reasons'):
        if getattr(strategy, field).get(vt_symbol):
            failures.append(field)
    if any(key[0] == vt_symbol and value for key, value in strategy.pending_entry_diagnostics.items()):
        failures.append('pending_entry_diagnostics')
    if any(order.vt_symbol == vt_symbol for order in strategy.strategy_engine.active_limit_orders.values()):
        failures.append('active_limit_orders')
    states = [s for s in strategy.states.values() if s.contract_vt_symbol == vt_symbol]
    if any(s.active_volume() for s in states):
        failures.append('product_layers')
    if failures:
        raise RuntimeError(f'epoch_not_quiescent:{vt_symbol}:{failures}')
    old = strategy.ams[vt_symbol]
    strategy.ams[vt_symbol] = type(old)(size=old.size)
    for field in ('last_close_prices', 'equity_start_positions', 'execution_price_overrides',
                  'pending_close_lots', 'pending_close_reasons'):
        getattr(strategy, field).pop(vt_symbol, None)
    for key in list(strategy.pending_entry_diagnostics):
        if key[0] == vt_symbol:
            strategy.pending_entry_diagnostics.pop(key)
    for state in states:
        state.reset()
    # SameDayCloseBacktestingEngine already replaced this slot with today's real bar.
    if hasattr(current_bar, 'datetime'):
        strategy.strategy_engine.bars[vt_symbol] = current_bar


def identity(path):
    path = Path(path).resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f'input_changed_while_hashing:{path}')
    return {'path': str(path), 'bytes': after.st_size, 'sha256': digest.hexdigest()}


def json_value(value):
    if hasattr(value, 'item'):
        return value.item()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def main():
    if len(sys.argv) != 1:
        raise SystemExit('Fixed single replay; no parameter sweep arguments are supported.')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT / 'source_summary.json'
    if summary_path.exists() or (OUTPUT / 'engine.log').exists():
        raise SystemExit('Existing replay or log: do not overwrite or silently rerun the source.')
    os.chdir(ROOT)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['OFFICIAL_LIVE_OUTPUT_DIR'] = str(OUTPUT)
    os.environ['OFFICIAL_LIVE_SIGNAL_INPUT_DIR'] = str(OUTPUT)
    os.environ['OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED'] = '0'
    os.environ['OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED'] = '0'
    os.environ['TZ'] = 'Asia/Shanghai'
    if hasattr(time, 'tzset'):
        time.tzset()
    if not VENDOR.is_dir():
        raise RuntimeError('frozen_vendor_missing')
    project = ROOT / 'examples/portfolio_backtesting'
    sys.path[:0] = [str(ROOT), str(VENDOR), str(project)]
    import vnpy_portfoliostrategy
    import vnpy_portfoliostrategy.backtesting as vendor_engine
    import vnpy_sqlite
    import sklearn
    import numpy as np
    from vnpy.trader.constant import Exchange
    from vnpy.trader.utility import ArrayManager
    import run_qmt_roll_backtest as roll
    import run_qmt_alignment_backtest as artifacts
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    import build_qmt_roll_ai_position_training_samples as position_features
    from main_contract_mapping import get_preferred_mapping_path
    from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
    from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
        BASE_RISK_RATIO, CORR20_06_08_FLOOR35_OVERRIDES,
    )
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    assert_stage196_database_sentinels()
    if not str(Path(vnpy_portfoliostrategy.__file__).resolve()).startswith(str(VENDOR)):
        raise RuntimeError('wrong_portfolio_vendor')
    preflight_model = pairwise.SelectionPairwiseRuntimeModel()
    preflight_columns = list(preflight_model.model.feature_names_in_)
    preflight_prediction = preflight_model.model.predict_proba(pd.DataFrame([[0.0] * len(preflight_columns)], columns=preflight_columns)).tolist()
    runtime_preflight = {'sklearn': {'version': sklearn.__version__, 'file': sklearn.__file__},
        'numpy': {'version': np.__version__, 'file': np.__file__},
        'pandas': {'version': pd.__version__, 'file': pd.__file__},
        'dummy_pairwise_probability': preflight_prediction}
    (OUTPUT / 'runtime_preflight.json').write_text(json.dumps(runtime_preflight, ensure_ascii=False, indent=2))
    print(json.dumps(runtime_preflight, ensure_ascii=False), flush=True)

    database_path = ROOT / '.vntrader/database.db'
    inputs = {'database': identity(database_path), 'mapping': identity(get_preferred_mapping_path()),
              'pairwise_model': identity(pairwise.DEFAULT_MODEL_PATH),
              'pairwise_summary': identity(pairwise.DEFAULT_SUMMARY_PATH),
              'protocol': identity(OUTPUT / 'source_protocol.md')}
    source_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    source_files = [Path(__file__), project / 'run_qmt_roll_backtest.py',
                    project / 'qmt_roll_portfolio_strategy.py', project / 'run_qmt_alignment_backtest.py',
                    project / 'qmt_universe.py', project / 'main_contract_mapping.py',
                    project / 'contract_metadata.py', project / 'qmt_roll_ai_selection_pairwise_runtime.py',
                    project / 'build_qmt_roll_ai_position_training_samples.py',
                    project / 'run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest.py',
                    Path(vendor_engine.__file__), VENDOR / 'vnpy_portfoliostrategy/template.py',
                    Path(vnpy_sqlite.__file__).parent / 'sqlite_database.py']
    source_identities = [identity(p) for p in source_files]
    czce_dates = {}
    connection = sqlite3.connect(f'file:{database_path}?mode=ro', uri=True)
    try:
        for symbol, date in connection.execute("SELECT symbol,datetime FROM dbbardata WHERE exchange='CZCE' AND interval='d' AND datetime>=? AND datetime<=? ORDER BY symbol,datetime", ('2015-01-01', '2026-10-09')):
            czce_dates.setdefault(f'{symbol}.CZCE', []).append(pd.Timestamp(date).normalize())
    finally:
        connection.close()

    current_day = [START]
    loaded_csv_inputs = {}
    raw_loader = pairwise.load_contract_bars
    # Runtime's imported reference must be replaced, not merely the defining module name.
    def bounded_pairwise_loader(vt_symbol):
        raw = raw_loader(vt_symbol)
        csv_path = position_features._contract_csv_path(vt_symbol)
        if csv_path.exists() and str(csv_path) not in loaded_csv_inputs:
            loaded_csv_inputs[str(csv_path)] = identity(csv_path)
        if not vt_symbol.endswith('.CZCE') or raw.empty:
            return raw
        start = epoch_start(czce_dates.get(vt_symbol, []), current_day[0])
        return filter_epoch_history(raw, current_day[0], start)
    pairwise.load_contract_bars = bounded_pairwise_loader

    class EpochIsolatedFloor35(QmtRollPortfolioStrategy):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.research_last_real_date = {}
            self.research_epoch_resets = []
            self.research_callback_count = 0

        def on_bars(self, bars):
            if not bars:
                return
            day = pd.Timestamp(next(iter(bars.values())).datetime).tz_localize(None).normalize()
            current_day[0] = day
            for vt_symbol, bar in bars.items():
                previous = self.research_last_real_date.get(vt_symbol)
                if bar.exchange == Exchange.CZCE and previous is not None and day >= previous + pd.DateOffset(years=5):
                    prior_count = self.ams[vt_symbol].count
                    reset_contract_epoch(self, vt_symbol, bar)
                    self.research_epoch_resets.append({'vt_symbol': vt_symbol, 'old_last_real_date': str(previous.date()),
                        'new_first_real_date': str(day.date()), 'old_am_count': prior_count,
                        'new_am_count_before_today': self.ams[vt_symbol].count})
                self.research_last_real_date[vt_symbol] = day
            super().on_bars(bars)
            self.research_callback_count += 1

    roll.QmtRollPortfolioStrategy = EpochIsolatedFloor35
    overrides = {**CORR20_06_08_FLOOR35_OVERRIDES, 'trade_start_date': START.date().isoformat()}
    started = datetime.now().astimezone().isoformat()
    began = time.monotonic()
    with (OUTPUT / 'engine.log').open('w', encoding='utf-8', buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        print('runtime_preflight', json.dumps(runtime_preflight, ensure_ascii=False), flush=True)
        engine, daily, statistics = roll.run_backtest(risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides, analysis_start=START.to_pydatetime(),
            analysis_end=END.to_pydatetime(), preload_start=START.to_pydatetime(),
            capital=200_000, save_artifacts=False, include_start_year_sweep=False,
            file_prefix='stage263_uniform_floor35_2015_2026', chart_title='Stage263 research source')
        if daily is None or daily.empty:
            raise RuntimeError('empty_source_daily')
        if pd.Timestamp(engine.datetime).tz_localize(None).normalize() < END:
            raise RuntimeError(f'engine_did_not_reach_end:{engine.datetime}')
        positions = artifacts.build_positions_df(engine)
        candidates = artifacts.build_entry_candidate_snapshots_df(engine)
        trades = artifacts.build_trades_df(engine)
        frames = {'position_changes': positions, 'entry_candidate_snapshots': candidates, 'trades': trades}
        for name, frame in frames.items():
            frame.to_csv(OUTPUT / f'source_{name}.csv', index=False)
        daily.reset_index().to_csv(OUTPUT / 'source_daily.csv', index=False)
        (OUTPUT / 'source_statistics.json').write_text(json.dumps(statistics, ensure_ascii=False, indent=2, default=json_value))
        pd.DataFrame(engine.strategy.research_epoch_resets).to_csv(OUTPUT / 'contract_epoch_resets.csv', index=False)
        # Contract attribution must reconcile exactly to the engine's daily ledger.
        totals = positions.groupby('date').net_pnl.sum()
        ledger = daily.net_pnl.copy()
        ledger.index = pd.to_datetime(ledger.index).date
        maximum_pnl_error = float((ledger - totals.reindex(ledger.index).fillna(0)).abs().max())
        if maximum_pnl_error > 1e-6:
            raise RuntimeError(f'position_daily_reconciliation_failed:{maximum_pnl_error}')
    if any(text in (OUTPUT / 'engine.log').read_text() for text in ('触发异常', 'Exception triggered', 'Traceback (most recent call last)')):
        raise RuntimeError('engine_swallowed_exception_see_log')
    # Ensure the database was not mutated by source generation (incl. concurrent repair).
    if identity(database_path)['sha256'] != inputs['database']['sha256']:
        raise RuntimeError('database_changed_during_replay')
    for entry in source_identities:
        if identity(entry['path'])['sha256'] != entry['sha256']:
            raise RuntimeError(f'source_changed_during_replay:{entry["path"]}')
    outputs = {p.name: identity(p) for p in OUTPUT.glob('source_*.csv')}
    summary = {'status': 'source_recomputed_conditionally_not_historical_PIT', 'started_at': started,
        'completed_at': datetime.now().astimezone().isoformat(), 'elapsed_seconds': time.monotonic()-began,
        'source_commit': source_head, 'source_kind': 'floor35_200k_risk0.045_daily_current_master_research_epoch_guard',
        'analysis_start': str(START.date()), 'preload_start': str(START.date()), 'trade_start_date': str(START.date()),
        'analysis_end': str(END.date()), 'capital': 200000, 'risk_ratio': BASE_RISK_RATIO,
        'strategy_overrides': overrides, 'inputs': inputs, 'source_files': source_identities,
        'pairwise_csv_inputs': list(loaded_csv_inputs.values()), 'runtime': {'python': sys.executable,
            'numerical_runtime': runtime_preflight,
            'python_version': sys.version, 'portfolio_package': str(vnpy_portfoliostrategy.__file__),
            'sqlite_package': str(vnpy_sqlite.__file__),
            'packages': {p: importlib.metadata.version(p) for p in ['pandas','numpy','scikit-learn','joblib']},
            'timezone': os.environ['TZ'], 'ctps_connected': 0, 'order_api_calls': 0},
        'statistics': statistics, 'outputs': outputs,
        'source_contract_count': len(engine.vt_symbols), 'real_daily_bar_count': len(engine.history_data),
        'callback_days': engine.strategy.research_callback_count,
        'epoch_reset_count': len(engine.strategy.research_epoch_resets), 'position_rows': len(positions),
        'candidate_rows': len(candidates), 'trade_rows': len(trades),
        'position_daily_max_abs_error': maximum_pnl_error,
        'boundaries': ['Fixed pairwise weights are posterior-frozen; conditional diagnosis only, not historical PIT.',
            '2015 begins without 2014 preload; do not shorten AM140 or tune to create early labels.',
            'Missing real bars/mapping windows must be excluded by the shared sample contract.',
            'No separate 2020 account or frozen old Stage183 data enters this source.']}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=json_value))
    print(json.dumps({k: summary[k] for k in ('status','elapsed_seconds','real_daily_bar_count','epoch_reset_count','position_rows','candidate_rows','trade_rows','position_daily_max_abs_error')}, ensure_ascii=False, indent=2))
    print(str(summary_path))


if __name__ == '__main__':
    main()
