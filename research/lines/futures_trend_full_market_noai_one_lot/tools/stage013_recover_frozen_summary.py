"""Finalize an endpoint-complete frozen ledger after JSON date serialization failure. No replay."""
from pathlib import Path
import json,sys,inspect,importlib.metadata
import numpy as np
import pandas as pd
from stage004_run import (LINE,CAPITAL,START,END,FullMarketDailyEngine,safe,sha,
                          native_strategy,ConfirmedDailyNextRealOpenEngine,s847)
import vnpy_portfoliostrategy.backtesting as vendor

def recover(output):
    if (output/'manifest.json').exists() or (output/'summary.json').exists():raise FileExistsError('never overwrite final bundle')
    protocol=json.loads((output/'protocol.json').read_text())
    starts=json.loads((output/'code_start_hashes.json').read_text())
    for source,digest in starts.items():
        if sha(output/'code_snapshot'/Path(source).name)!=digest:raise ValueError('runtime_snapshot_changed')
    log=(output/'engine.log').read_text()
    if 'Historical backtest complete' not in log or 'The daily mark-to-market profit and loss calculation is complete' not in log or 'Traceback' in log:raise ValueError('incomplete_replay')
    daily=pd.read_csv(output/'daily.csv');daily['date']=pd.to_datetime(daily.date).dt.date;daily=daily.set_index('date')
    if str(daily.index[-1])!=protocol['end']:raise ValueError('endpoint_mismatch')
    trades=pd.read_csv(output/'trades.csv');closed=pd.read_csv(output/'closed_episodes.csv')
    contracts=pd.read_csv(output/'contract_metadata.csv');snapshots=pd.read_csv(output/'account_snapshots.csv').set_index('date')
    if not np.allclose(daily.equity,CAPITAL+daily.net_pnl.cumsum(),atol=1e-7,rtol=0):raise ValueError('equity_not_reconciled')
    difference=np.abs(daily.equity.to_numpy()-snapshots.reindex([str(d) for d in daily.index]).strategy_equity.to_numpy())
    error=float(difference.max())
    if not np.isfinite(difference).all() or error>1e-5:raise ValueError('strategy_account_disagreement')
    residual=json.loads((output/'residual_open_positions.json').read_text())
    e=FullMarketDailyEngine({});e.capital=CAPITAL
    stats=e.calculate_statistics(daily,output=False)
    warning=('有效性限制：4个到期合约残余仓位占满正式4品种并发上限，最后成交2022-09-01；2023—2026无新成交。'
             '期末权益与全区间Sharpe仅为缺少可执行退出/结算证据下的冻结账面统计，不代表持续交易至今的可实现业绩；本轮不可用于正式策略晋升或优劣判断。')
    boundaries=[warning,*protocol['boundaries']]
    summary=dict(stats,initial_capital=CAPITAL,total_trade_count=len(trades),total_slippage=float(daily.slippage.sum()),
        total_commission=float(daily.commission.sum()),win_rate_pct=float(closed.net_pnl.gt(0).mean()*100),
        completed_episodes=len(closed),residual_open_positions=len(residual),strategy_account_max_abs_error=error,
        mode=protocol['mode'],analysis_start=protocol['start'],analysis_end=protocol['end'],
        universe_product_count=int(contracts.product_vt_symbol.nunique()),
        traded_product_count=int(contracts[contracts.vt_symbol.isin(trades.vt_symbol)].product_vt_symbol.nunique()),
        max_margin=float(snapshots.margin.max()),deferred_missing_bar_order_attempts=len(pd.read_csv(output/'deferred_orders.csv')),
        missing_held_contract_days=len(pd.read_csv(output/'held_missing.csv')),blocked_open_order_attempts=len(pd.read_csv(output/'blocked_open_orders.csv')),
        elapsed_seconds=None,last_fill_date=str(trades.date.max()),performance_certifiable=False,
        validity_status='diagnostic_book_result_expired_residual_deadlock',boundaries=boundaries)
    receipt=dict(reason='native statistics date object JSON serialization failed after all ledger/account gates',
        financial_replay_performed=False,original_runtime_snapshot_verified=True,endpoint=str(daily.index[-1]),
        account_max_abs_error=error,recovery_tool_sha256=sha(Path(__file__)),
        elapsed_seconds_unavailable=True,original_runtime_hashes=starts)
    (output/'summary.json').write_text(json.dumps(safe(summary),ensure_ascii=False,indent=2))
    (output/'recovery_receipt.json').write_text(json.dumps(safe(receipt),ensure_ascii=False,indent=2))
    manifest=dict(protocol);manifest['boundaries']=boundaries;manifest['finalization']='frozen_csv_recovery_no_financial_rerun'
    manifest['hashes']={p.name:sha(p) for p in output.iterdir() if p.is_file()}
    paths=[Path(native_strategy.__file__),Path(vendor.__file__),Path(inspect.getfile(ConfirmedDailyNextRealOpenEngine)),Path(s847.__file__)]
    manifest['code_hashes']={str(p):sha(p) for p in paths};manifest['original_runtime_code_hashes']=starts
    manifest['code_snapshot_hashes']={p.name:sha(p) for p in (output/'code_snapshot').iterdir()}
    manifest['runtime']={'python':sys.executable,'version':sys.version,'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','vnpy_portfoliostrategy']}}
    (output/'manifest.json').write_text(json.dumps(safe(manifest),ensure_ascii=False,indent=2))
    print(json.dumps(safe(summary),ensure_ascii=False,indent=2))
if __name__=='__main__':recover(Path(sys.argv[1]).resolve())
