"""Fixed commit replay using immutable baseline or variant-private snapshots."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile

THIS_FILE = Path(__file__).resolve()
REPOSITORY = THIS_FILE.parents[3]
# Capture before bootstrap or any local business imports. Replay is a fresh
# isolated process; concurrent source edits are rejected, never archived as if
# they were the originally loaded implementation.
LAUNCH_SOURCES = {p: p.read_bytes() for p in (
    sorted((THIS_FILE.parent.parent / 'qmt357').glob('*.py'))
    + sorted(THIS_FILE.parent.glob('*.py')) + [THIS_FILE.parent / 'provenance.json'])}


def bootstrap():
    if not sys.flags.isolated or os.environ.get('QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD') != '1':
        env = dict(os.environ, QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD='1')
        os.execve(sys.executable, [sys.executable, '-I', str(THIS_FILE), *sys.argv[1:]], env)
    sys.path.insert(0, str(REPOSITORY))
    from examples.stock_backtesting.qmt357_commit4ac255e.runtime import activate_runtime
    activate_runtime()


def _write_json(path, payload):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                    allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


@contextmanager
def _recorded_execution(target, identity, source_bytes, source_root):
    """Freeze before constructing an engine; a failed run is never performance."""
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(target / 'code_snapshot.tar.gz', 'w:gz') as archive:
        for path, content in source_bytes.items():
            item = tarfile.TarInfo(str(path.relative_to(source_root)))
            item.size = len(content)
            archive.addfile(item, io.BytesIO(content))
    identity['code_archive_sha256'] = hashlib.sha256((target / 'code_snapshot.tar.gz').read_bytes()).hexdigest()
    _write_json(target / 'run_identity.json', identity)
    manifest = dict(identity, run_identity_sha256=hashlib.sha256((target / 'run_identity.json').read_bytes()).hexdigest())
    _write_json(target / 'manifest.json', manifest)
    state = {'engine': None}
    try:
        yield state
        engine = state['engine']
        manifest.update(status='COMPLETE', complete_period_result=True,
            finished_at=datetime.now().astimezone().isoformat(),
            partial_unfilled_orders=sum(x['reason'] == 'end_of_data_unfilled' for x in engine.rejections))
        _write_json(target / 'manifest.json', manifest)
    except BaseException as exc:
        engine = state['engine']
        days = getattr(engine, 'equity_rows', [])
        now = getattr(engine, 'datetime', None)
        failure = dict(type=type(exc).__name__, message=str(exc),
            failure_date=str(now.date()) if now else None,
            last_completed_date=str(days[-1]['date']) if days else None,
            completed_sessions=len(days), processed_trades=len(getattr(engine, 'executions', [])),
            processed_orders=len(getattr(engine, 'limit_orders', {})),
            open_positions=len(getattr(engine, 'holdings', {})),
            held_symbols=sorted(getattr(engine, 'holdings', {})),
            diagnostic_only_not_full_period_result=True)
        # These files belong to this newly allocated run only. An exception
        # during result publication must not leave apparently complete stats.
        for name in ('summary.json', 'annual_summary.json', 'annual_summary.csv',
                     'report.md', 'daily_equity.csv'):
            (target / name).unlink(missing_ok=True)
            (target / (name + '.tmp')).unlink(missing_ok=True)
        manifest.update(status='FAILED', complete_period_result=False,
                        finished_at=datetime.now().astimezone().isoformat(), failure=failure)
        _write_json(target / 'failure.json', dict(status='FAILED', complete_period_result=False,
            run_identity_sha256=manifest['run_identity_sha256'], **failure))
        _write_json(target / 'manifest.json', manifest)
        raise


def run_backtest(args):
    import pandas as pd
    from examples.stock_backtesting.qmt357.run import _safe_output
    from examples.stock_backtesting.qmt357.signals import SignalSettings
    from examples.stock_backtesting.qmt357.annual_metrics import annual_statistics
    from examples.stock_backtesting.qmt357_commit4ac255e.config import (
        ROOT, BASE_ROOT, VERSION, INDEX_SYMBOL, BacktestSettings, TRAILING_CONTRACT, MIGRATION_NOTES)

    run_id = args.run_id or datetime.now().strftime('run_%Y%m%d_%H%M%S_%f')
    target = _safe_output(ROOT / 'outputs', run_id)
    if args.variant_snapshot:
        from examples.stock_backtesting.qmt357_commit4ac255e.data import load_snapshot, _snapshot_path
        snapshot = _snapshot_path(args.variant_snapshot)
        snapshot_scope = 'variant_private'
    else:
        from examples.stock_backtesting.qmt357.data import load_snapshot, _snapshot_path
        snapshot = _snapshot_path(args.snapshot)
        snapshot_scope = 'baseline_readonly'
    if not snapshot.exists():
        raise FileNotFoundError(f'Snapshot missing ({snapshot_scope}): {snapshot}; prepare an immutable snapshot in this scope first')
    from examples.stock_backtesting.qmt357_commit4ac255e.engine import Commit4ac255eEngine
    from examples.stock_backtesting.qmt357_commit4ac255e.strategy import Commit4ac255eStrategy
    panel, metadata = load_snapshot(snapshot)
    calendar = sorted(panel.loc[panel.vt_symbol == INDEX_SYMBOL, 'date'].unique())
    if len(calendar) < 61:
        raise ValueError('Snapshot needs 60 warmup/signal sessions and a next execution session')
    start = pd.Timestamp(args.start) if args.start else pd.Timestamp(calendar[59])
    end = pd.Timestamp(args.end) if args.end else pd.Timestamp(calendar[-1])
    if start > end or end > pd.Timestamp(calendar[-1]) or sum(d < start for d in calendar) < 59:
        raise ValueError('Requested dates exceed snapshot coverage or omit 59 prior warmup sessions')
    settings = BacktestSettings(**{name: getattr(args, name) for name in (
        'capital', 'commission_rate', 'minimum_commission', 'stamp_duty_rate', 'slippage_per_share')})
    source_bytes = LAUNCH_SOURCES
    hashes = lambda root: {p.name: hashlib.sha256(content).hexdigest()
                           for p, content in source_bytes.items() if p.parent == root and p.suffix == '.py'}
    from vnpy.trader.utility import TEMP_DIR
    identity = dict(version=VERSION, run_id=run_id, status='RUNNING', complete_period_result=False,
        created_at=datetime.now().astimezone().isoformat(),
        execution_timing='close_signal_next_open', settings=asdict(settings),
        signal_settings=asdict(SignalSettings()), trailing_contract=TRAILING_CONTRACT,
        start=str(start.date()), end=str(end.date()), snapshot=metadata, snapshot_path=str(snapshot),
        snapshot_scope=snapshot_scope,
        vnpy_settings=str(TEMP_DIR), python=sys.version, database_opened=False,
        migration_notes=MIGRATION_NOTES,
        source_provenance=json.loads(source_bytes[ROOT / 'provenance.json']),
        code_sha256=hashes(ROOT), baseline_code_sha256=hashes(BASE_ROOT),
        role='independent_stock_fixed_commit_research_not_live')
    with _recorded_execution(target, identity, source_bytes, ROOT.parent) as execution:
        if any(p.read_bytes() != content for p, content in source_bytes.items()):
            raise RuntimeError('Source changed since process startup; replay rejected')
        engine = Commit4ac255eEngine(settings, unsupported_actions=
            metadata.get('source_metadata', {}).get('unsupported_corporate_actions', []))
        execution['engine'] = engine
        engine.set_panel(panel, start.to_pydatetime(), end.to_pydatetime())
        engine.add_strategy(Commit4ac255eStrategy, {})
        engine.run_backtesting()
        daily = engine.calculate_result()
        summary = engine.calculate_statistics(daily)
        annual = annual_statistics(daily, engine.round_trips, capital=settings.capital,
                                   annual_days=settings.annual_days)
        if any(p.read_bytes() != content for p, content in source_bytes.items()):
            raise RuntimeError('Source changed during replay; result cannot be frozen')
        daily.to_csv(target / 'daily_equity.csv', encoding='utf-8-sig')
        pd.DataFrame(annual).to_csv(target / 'annual_summary.csv', index=False, encoding='utf-8-sig')
        logs = [
        ('trades', engine.executions, ['date','vt_symbol','direction','price','shares','commission','slippage']),
        ('signals', engine.strategy.signal_log, ['date','vt_symbol','score','condition_count']),
        ('gates', engine.strategy.gate_log, ['date','allowed']),
        ('round_trips', engine.round_trips, ['vt_symbol','entry_date','exit_date','net_pnl']),
        ('rejections', engine.rejections, ['date','vt_orderid','vt_symbol','reason']),
        ('position_coverage', engine.position_coverage, ['date','vt_symbol','shares','mark_price','market_value',
            'has_bar','is_suspended','last_quote_date','stale_sessions','stale_calendar_days']),
        ('trailing_stops', engine.strategy.trail_log, ['date','vt_symbol','buy_price','observed_close','peak','old_stop','new_stop']),
        ('orders', [dict(orderid=o.vt_orderid, vt_symbol=o.vt_symbol, signal_date=o.datetime.isoformat(),
            direction=o.direction.value, requested_shares=o.volume, filled_shares=o.traded, status=o.status.value)
            for o in engine.limit_orders.values()], ['orderid','vt_symbol','signal_date','direction',
            'requested_shares','filled_shares','status']),
        ]
        for name, rows, columns in logs:
            (pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)).to_csv(
                target / f'{name}.csv', index=False, encoding='utf-8-sig')
        for name, payload in [('summary', summary), ('annual_summary', annual)]:
            _write_json(target / f'{name}.json', payload)
        report = ['# QMT commit 4ac255e 参数及分级移动止损回测', '',
        f'- 区间：{start.date()} 至 {end.date()}；本金：{settings.capital:,.2f}元。',
        '- 独立研究版：每日90%、最多3只、单只32%、止损2%、止盈45%，浮盈保本与10/20/30/40%分级锁盈。',
        '- 沿用迁移版信号和现金账本：收盘决策、次日开盘，不等价于原QMT 14:50回放。',
        '- 保本/锁盈是价格触发线，非扣费后保证收益；跳空和跌停可导致实际亏损超过2%。', '',
        '## 汇总', '', *[f'- {key}: {value}' for key, value in summary.items()], '',
        '## 连续账户年度统计', '',
        '各年承接上年权益；年度回撤从该年期初权益计算；首尾不完整年不年化。', '',
        '| 年份 | 实际起止 | 期末权益 | 年内收益 | 年内最大回撤 | Sharpe | 成交笔数 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |',
        *[f'| {r["year"]} | {r["start_date"]}—{r["end_date"]} | {r["end_equity"]:,.2f} | {r["return_pct"]:.2f}% | {r["max_drawdown_pct"]:.2f}% | {r["sharpe"]:.3f} | {r["total_trade_count"]} |' for r in annual], '',
        '## 数据与迁移限制', '', *[f'- {v}' for v in metadata.get('data_limitations', [])],
        f'- 全快照缺显式行动因子变化数：{metadata.get("factor_changes_without_actions", "未知")}；持仓遇到时硬失败，未持仓也可能影响信号。',
        '- 使用月度成分历史，非逐日精确历史池；除权日毛现金分红到账，未模拟分红税/实际到账日。',
        '- 费用固定假设，非历史券商费率还原。无真实账户连接，不是实盘或策略有效性验收。',
        *[f'- {note}' for note in MIGRATION_NOTES], '']
        (target / 'report.md').write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps(dict(output=str(target), summary=summary), ensure_ascii=False, indent=2))


def main():
    bootstrap()
    from examples.stock_backtesting.qmt357_commit4ac255e.config import ROOT, BASE_ROOT, BacktestSettings
    parser = argparse.ArgumentParser(description='独立股票commit4ac255e固定参数+分级止损回测')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('runtime')
    sub.add_parser('test', help='检查原版与commit版全部股票测试')
    backtest = sub.add_parser('backtest')
    snapshots = backtest.add_mutually_exclusive_group(required=True)
    snapshots.add_argument('--snapshot', help='原股票data目录下的冻结快照名，只读')
    snapshots.add_argument('--variant-snapshot', help='本版本data/snapshots下的独立冻结快照名')
    backtest.add_argument('--start')
    backtest.add_argument('--end')
    backtest.add_argument('--run-id')
    for name in ['capital','commission_rate','minimum_commission','stamp_duty_rate','slippage_per_share']:
        backtest.add_argument('--' + name.replace('_', '-'), type=float, default=getattr(BacktestSettings(), name))
    args = parser.parse_args()
    try:
        if args.command == 'runtime':
            from vnpy_portfoliostrategy.backtesting import BacktestingEngine  # noqa: F401
            from vnpy.trader.utility import TEMP_DIR
            print(json.dumps(dict(vnpy_settings=str(TEMP_DIR), database_opened=False,
                futures_modules=[n for n in sys.modules if n.startswith(('qmt_roll','qmt_range','run_qmt_roll'))])))
        elif args.command == 'test':
            import pytest
            return pytest.main([str(BASE_ROOT / 'tests'), str(ROOT / 'tests'), '-q', '--import-mode=importlib'])
        else:
            run_backtest(args)
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as exc:
        print(f'Stock commit task failed: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
