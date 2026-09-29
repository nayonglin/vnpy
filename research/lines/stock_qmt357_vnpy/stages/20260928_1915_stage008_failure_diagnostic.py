"""Reproduce the hard failure and persist diagnostic state, never performance."""
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import sys

THIS = Path(__file__).resolve()
ROOT = THIS.parents[4]
if not sys.flags.isolated or os.environ.get('QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD') != '1':
    env = dict(os.environ, QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD='1')
    os.execve(sys.executable, [sys.executable, '-I', str(THIS)], env)
sys.path.insert(0, str(ROOT))
from examples.stock_backtesting.qmt357_commit4ac255e.runtime import activate_runtime
activate_runtime()
from examples.stock_backtesting.qmt357.data import load_snapshot
from examples.stock_backtesting.qmt357_commit4ac255e.config import BacktestSettings
from examples.stock_backtesting.qmt357_commit4ac255e.engine import Commit4ac255eEngine
from examples.stock_backtesting.qmt357_commit4ac255e.strategy import Commit4ac255eStrategy

panel, metadata = load_snapshot(ROOT / 'examples/stock_backtesting/qmt357/data/history_201910_20260928')
engine = Commit4ac255eEngine(BacktestSettings())
engine.set_panel(panel, datetime(2020, 1, 1), datetime(2026, 9, 28))
engine.add_strategy(Commit4ac255eStrategy, {})
try:
    engine.run_backtesting()
except ValueError as exc:
    symbol = '000001.SZSE'
    payload = dict(status='FAILED_REPLAY_DIAGNOSTIC_ONLY_NOT_FULL_PERIOD_RESULT',
        error=str(exc), failure_date=str(engine.datetime.date()),
        snapshot_sha256=metadata['panel_sha256'], settings=asdict(engine.settings),
        last_completed_date=str(engine.equity_rows[-1]['date']),
        held_at_failure={s: asdict(h) for s, h in engine.holdings.items()},
        failure_row=engine.current_rows.get(symbol),
        failed_symbol_trades=[t for t in engine.executions if t['vt_symbol'] == symbol],
        failed_symbol_trailing=[t for t in engine.strategy.trail_log if t['vt_symbol'] == symbol],
        processed_trades=len(engine.executions), published_full_period_results=False)
    target = THIS.with_suffix('.json')
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps(dict(error=str(exc), diagnostic=str(target),
        last_completed_date=payload['last_completed_date']), ensure_ascii=False))
else:
    raise AssertionError('Expected factor guard failure did not reproduce')
