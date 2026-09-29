"""Standalone, isolated stock research CLI. Recommended: python -I run.py ..."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys

THIS_FILE = Path(__file__).resolve()
REPOSITORY = THIS_FILE.parents[3]


def bootstrap():
    # The repository's sitecustomize preloads the FUTURES .vntrader. Restart
    # in Python isolated mode before choosing the stock runtime. No global edits.
    # The shared venv's editable .pth exposes repository sitecustomize even
    # under -I. Disable that guard only in this stock child process and restart.
    if not sys.flags.isolated or os.environ.get('QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD') != '1':
        child_env = dict(os.environ, QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD='1')
        os.execve(sys.executable, [sys.executable, '-I', str(THIS_FILE), *sys.argv[1:]], child_env)
    sys.path.insert(0, str(REPOSITORY))
    from examples.stock_backtesting.qmt357.runtime import activate_runtime
    return activate_runtime()


def _safe_output(root: Path, name: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', name):
        raise ValueError('run-id must be a safe directory name')
    if root.is_symlink():
        raise ValueError('Stock outputs must not be redirected with a symlink')
    target = root / name
    if target.is_symlink() or target.resolve().parent != root.resolve():
        raise ValueError('Output path escapes the stock directory')
    if target.exists():
        raise FileExistsError(f'Frozen result already exists: {target}')
    return target


def run_backtest(args):
    import pandas as pd
    from examples.stock_backtesting.qmt357.config import ROOT, VERSION, INDEX_SYMBOL, BacktestSettings, MIGRATION_NOTES
    from examples.stock_backtesting.qmt357.data import load_snapshot
    from examples.stock_backtesting.qmt357.engine import StockBacktestingEngine
    from examples.stock_backtesting.qmt357.signals import SignalSettings
    from examples.stock_backtesting.qmt357.strategy import Qmt357StockStrategy
    from examples.stock_backtesting.qmt357.annual_metrics import annual_statistics

    run_id = args.run_id or datetime.now().strftime('run_%Y%m%d_%H%M%S_%f')
    target = _safe_output(ROOT / 'outputs', run_id)
    snapshot = ROOT / 'data' / args.snapshot
    if not snapshot.exists():
        raise FileNotFoundError(f'Snapshot missing: {snapshot}; use download then prepare')
    panel, metadata = load_snapshot(snapshot)
    calendar = sorted(panel.loc[panel.vt_symbol == INDEX_SYMBOL, 'date'].unique())
    if len(calendar) < 61:
        raise ValueError('Snapshot needs at least 60 warmup/signal sessions and a next execution session')
    start = pd.Timestamp(args.start) if args.start else pd.Timestamp(calendar[59])
    end = pd.Timestamp(args.end) if args.end else pd.Timestamp(calendar[-1])
    if start > end or end > pd.Timestamp(calendar[-1]) or sum(d < start for d in calendar) < 59:
        raise ValueError('Requested dates exceed snapshot coverage or omit 59 prior warmup sessions')
    settings = BacktestSettings(capital=args.capital, commission_rate=args.commission_rate,
        minimum_commission=args.minimum_commission, stamp_duty_rate=args.stamp_duty_rate,
        slippage_per_share=args.slippage_per_share)
    engine = StockBacktestingEngine(settings)
    engine.set_panel(panel, start.to_pydatetime(), end.to_pydatetime())
    engine.add_strategy(Qmt357StockStrategy, {})
    engine.run_backtesting()
    daily = engine.calculate_result()
    summary = engine.calculate_statistics(daily)
    annual = annual_statistics(daily, engine.round_trips, capital=settings.capital,
                               annual_days=settings.annual_days)
    from vnpy.trader.utility import TEMP_DIR
    manifest = dict(version=VERSION, created_at=datetime.now().astimezone().isoformat(),
        execution_timing='close_signal_next_open', settings=asdict(settings),
        signal_settings=asdict(SignalSettings()), start=str(start.date()), end=str(end.date()),
        snapshot=metadata, snapshot_path=str(snapshot), vnpy_settings=str(TEMP_DIR),
        python=sys.version, database_opened=False, migration_notes=MIGRATION_NOTES,
        source_provenance=json.loads((ROOT / 'provenance.json').read_text(encoding='utf-8')),
        code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*.py'))},
        role='independent_stock_migration_validation_not_live',
        partial_unfilled_orders=sum(x['reason']=='end_of_data_unfilled' for x in engine.rejections))
    target.mkdir(parents=True, exist_ok=False)
    daily.to_csv(target / 'daily_equity.csv', encoding='utf-8-sig')
    pd.DataFrame(annual).to_csv(target / 'annual_summary.csv', index=False, encoding='utf-8-sig')
    for filename, rows, columns in [
        ('trades.csv', engine.executions, ['date','vt_symbol','direction','price','shares','commission','slippage']),
        ('signals.csv', engine.strategy.signal_log, ['date','vt_symbol','score','condition_count']),
        ('gates.csv', engine.strategy.gate_log, ['date','allowed']),
        ('round_trips.csv', engine.round_trips, ['vt_symbol','entry_date','exit_date','net_pnl']),
        ('rejections.csv', engine.rejections, ['date','vt_orderid','vt_symbol','reason']),
        ('position_coverage.csv', engine.position_coverage,
            ['date','vt_symbol','shares','mark_price','market_value','has_bar','is_suspended',
             'last_quote_date','stale_sessions','stale_calendar_days']),
        ('orders.csv', [dict(orderid=o.vt_orderid, vt_symbol=o.vt_symbol,
            signal_date=o.datetime.isoformat(), direction=o.direction.value, requested_shares=o.volume,
            filled_shares=o.traded, status=o.status.value) for o in engine.limit_orders.values()],
            ['orderid','vt_symbol','signal_date','direction','requested_shares','filled_shares','status']),
    ]:
        (pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)).to_csv(target / filename, index=False, encoding='utf-8-sig')
    for filename, payload in [('manifest.json',manifest), ('summary.json',summary),
                              ('annual_summary.json', annual)]:
        (target / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    limitations = metadata.get('data_limitations', [])
    labels = dict(end_equity='期末权益', total_return_pct='总收益（%）', max_drawdown_pct='最大回撤（%）',
        sharpe='Sharpe', total_slippage='总滑点成本（元）', total_commission='总手续费含印花税（元）',
        total_trade_count='成交笔数（买卖各算一笔）', closed_round_trips='已闭合交易次数',
        win_rate_pct='闭合交易净胜率（%）', open_positions='期末持仓只数', trading_days='回测交易日数',
        stale_holding_days='旧价持仓股票日数', max_stale_calendar_days='最长旧报价自然日数',
        end_stale_market_value='期末旧价持仓市值')
    report = '\n'.join([
        '# QMT 357 股票迁移回测', '',
        f'- 区间：{start.date()} 至 {end.date()}；本金：{settings.capital:,.2f}。',
        '- 执行：日线收盘决策、次日开盘；期末未平仓按末次可见收盘价计价。',
        '- 这是固定参数迁移验证，不等价于原 QMT 14:50 回测或实盘。',
        f'- 成分来源声明：{metadata.get("membership_source", "未独立验证")}。',
        '- 结果：', *[f'  - {labels.get(k, k)}: {v}' for k,v in summary.items()], '',
        '## 连续账户的逐年统计', '',
        '各年承接上年期末权益，不逐年重置本金；首尾年仅统计实际覆盖日期，收益未作年化。年度回撤从该年期初权益重新计算。', '',
        '| 年份 | 实际起止 | 期末权益 | 年内收益 | 年内最大回撤 | Sharpe | 成交笔数 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |',
        *[f'| {r["year"]} | {r["start_date"]}—{r["end_date"]} | {r["end_equity"]:,.2f} | {r["return_pct"]:.2f}% | {r["max_drawdown_pct"]:.2f}% | {r["sharpe"]:.3f} | {r["total_trade_count"]} |' for r in annual], '',
        '## 数据限制', '', *[f'- {v}' for v in limitations],
        f'- 全快照无显式行动的因子变化数：{metadata.get("factor_changes_without_actions", "未知")}；即使事件日未持仓，也可能影响信号，不能以账本对平替代数据正确性。',
        '- 月度成分或静态自定义股票池不代表完整历史可投资宇宙，详见manifest。',
        '- 固定佣金、印花税和滑点是研究假设；未重建券商历史费用、分红税和逐笔流动性。',
        '- 持仓缺行情/停牌的旧价计值见position_coverage.csv；stale_holding_days按股票×日期计数，不能视为真实可变现权益。',
        '', '## 迁移合同', '', *[f'- {v}' for v in MIGRATION_NOTES],
    ])
    (target / 'report.md').write_text(report + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(target), summary=summary), ensure_ascii=False, indent=2))


def main():
    original_cwd = Path.cwd()
    bootstrap()
    from examples.stock_backtesting.qmt357.config import ROOT, BacktestSettings
    parser = argparse.ArgumentParser(description='独立 QMT357 A股数据和 vn.py 回测入口')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('runtime', help='检查私有运行目录')
    sub.add_parser('test', help='运行独立股票测试')
    prepare = sub.add_parser('prepare', help='只读导入CSV/parquet到私有快照')
    prepare.add_argument('--source', type=Path, required=True)
    prepare.add_argument('--name', required=True)
    prepare.add_argument('--universe-mode', choices=['historical','static_snapshot','custom'], default='historical')
    download = sub.add_parser('download', help='下载到股票专用缓存')
    download.add_argument('--provider', choices=['tushare','baostock','baostock-sina'], default='tushare')
    download.add_argument('--start', default='20231001')
    download.add_argument('--end', default='20251231')
    backtest = sub.add_parser('backtest', help='从私有快照执行固定参数回测')
    backtest.add_argument('--snapshot', required=True)
    backtest.add_argument('--start')
    backtest.add_argument('--end')
    backtest.add_argument('--run-id')
    for name in ['capital','commission_rate','minimum_commission','stamp_duty_rate','slippage_per_share']:
        backtest.add_argument('--' + name.replace('_','-'), type=float, default=getattr(BacktestSettings(),name))
    args = parser.parse_args()
    try:
        if args.command == 'runtime':
            from vnpy_portfoliostrategy.backtesting import BacktestingEngine  # noqa: F401
            from vnpy.trader.utility import TEMP_DIR
            print(json.dumps(dict(vnpy_settings=str(TEMP_DIR), database_opened=False,
                futures_modules=[name for name in sys.modules if name.startswith(('qmt_roll','qmt_range','run_qmt_roll'))])))
        elif args.command == 'prepare':
            from examples.stock_backtesting.qmt357.data import prepare_snapshot
            source = args.source if args.source.is_absolute() else original_cwd / args.source
            print(prepare_snapshot(source, args.name, args.universe_mode))
        elif args.command == 'download':
            if args.provider == 'tushare':
                from examples.stock_backtesting.qmt357.download import download_panel
            elif args.provider == 'baostock-sina':
                from examples.stock_backtesting.qmt357.history_download import download_panel
            else:
                from examples.stock_backtesting.qmt357.baostock_download import download_panel
            print(download_panel(start=args.start, end=args.end))
        elif args.command == 'test':
            import pytest
            return pytest.main([str(ROOT / 'tests'), '-q'])
        else:
            run_backtest(args)
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as exc:
        print(f'Stock task failed: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
