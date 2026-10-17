"""Post-replay descriptive audit; never select parameters or start a replay."""
from __future__ import annotations

import json
import ast
from pathlib import Path
import re
import sqlite3

import stage263_build_expanded_source as source
import pandas as pd


def main():
    root, output = source.ROOT, source.OUTPUT
    summary_path = output / 'source_summary.json'
    summary = json.loads(summary_path.read_text())
    # Read the very source identity used by replay. Do not infer AM from a stale note.
    strategy_path = root/'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py'
    tree = ast.parse(strategy_path.read_text())
    strategy_class = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='QmtRollPortfolioStrategy')
    defaults = {node.target.id:ast.literal_eval(node.value) for node in strategy_class.body
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)
        and node.target.id in {'array_manager_size_floor','donchian_entry_period'}}
    am_size = max(40 + int(defaults['donchian_entry_period']) + 20, int(defaults['array_manager_size_floor']))
    positions = pd.read_csv(output / 'source_position_changes.csv')
    candidates = pd.read_csv(output / 'source_entry_candidate_snapshots.csv')
    trades = pd.read_csv(output / 'source_trades.csv')
    coverage = pd.read_csv(output / 'market_daily_coverage.csv')
    coverage['date'] = pd.to_datetime(coverage.date)
    database = sqlite3.connect(f'file:{root / ".vntrader/database.db"}?mode=ro', uri=True)
    observed = {}
    try:
        for vt in sorted(coverage.main_contract_vt.dropna().unique()):
            symbol, exchange = vt.split('.')
            rows = database.execute("SELECT datetime FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<=? ORDER BY datetime", (symbol, exchange, '2015-01-01', '2026-10-09')).fetchall()
            dates = pd.DatetimeIndex([pd.Timestamp(row[0]).normalize() for row in rows])
            counts, count, previous = {}, 0, None
            for date in dates:
                if exchange == 'CZCE' and previous is not None and date >= previous + pd.DateOffset(years=5):
                    count = 0
                count += 1
                counts[date] = count
                previous = date
            observed[vt] = counts
    finally:
        database.close()
    coverage['main_contract_same_epoch_observed_bars'] = [observed.get(v, {}).get(pd.Timestamp(d), 0) for d, v in zip(coverage.date, coverage.main_contract_vt)]
    ready_column = f'main_AM{am_size}_ready'
    coverage[ready_column] = coverage.coverage_ok & coverage.main_contract_same_epoch_observed_bars.ge(am_size)
    coverage.to_csv(output / 'main_history_readiness.csv', index=False)
    def product(vt):
        symbol, exchange = str(vt).split('.')
        return f'{re.match(r"[A-Za-z]+", symbol).group()}.{exchange}'
    positions['product'] = positions.vt_symbol.map(product)
    positions['date'] = pd.to_datetime(positions.date)
    product_pnl = positions.groupby(['date','product']).net_pnl.sum().rename('net_pnl').reset_index()
    product_pnl['year'] = product_pnl.date.dt.year
    candidates['year'] = pd.to_datetime(candidates.date).dt.year
    trades['year'] = pd.to_datetime(trades.date).dt.year
    coverage['year'] = coverage.date.dt.year
    rows = []
    for year in range(2015, 2027):
        cv = coverage[coverage.year.eq(year)]
        pnl = product_pnl[product_pnl.year.eq(year)]
        cand = candidates[candidates.year.eq(year)]
        tr = trades[trades.year.eq(year)]
        rows.append({'year':year, 'source_candidate_rows':len(cand), 'source_trade_rows':len(tr),
            'nonzero_product_pnl_days':int(pnl.net_pnl.abs().gt(1e-9).sum()),
            'source_product_days':len(pnl), 'source_product_net_pnl_sum':float(pnl.net_pnl.sum()),
            'market_calendar_product_days':len(cv), 'market_coverage_product_days':int(cv.coverage_ok.sum()),
            f'main_AM{am_size}_ready_product_days':int(cv[ready_column].sum()),
            f'AM{am_size}_ready_rate_of_covered':float(cv[ready_column].sum()/cv.coverage_ok.sum()) if cv.coverage_ok.sum() else None,
            'note':f'AM{am_size} rate reconstructed from actual DB bar sequences with same CZCE epoch guard; not entry probability.'})
    pd.DataFrame(rows).to_csv(output / 'source_opportunity_by_year.csv', index=False)
    audit = {'source_opportunity_by_year':rows, 'effective_source_AM_size':am_size,
        'diagnostic_correction':'Initial descriptive AM140 readiness assumed a stale default. Actual source preserved master AM120 throughout; this audit uses actual default120. No source replay or signal parameters changed.',
        'accepted_complete_replays':1, 'rejected_incomplete_replays':len(list(output.glob('failed_attempt_*/failure.json'))),
        'audit_code':source.identity(Path(__file__)),
        'diagnostics': {p.name:source.identity(p) for p in [output/'source_opportunity_by_year.csv',output/'main_history_readiness.csv']},
        'interpretation':f'Zero candidate/PnL rows do not establish informative labels; AM{am_size} readiness is a data limitation, never repaired by lowering the window.'}
    (output/'source_opportunity_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    summary.update(audit)
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
