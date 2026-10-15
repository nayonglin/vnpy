"""Read-only completeness and provenance audit of the Stage246 daily database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, required=True)
    p.add_argument('--origin-db', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    import numpy as np
    import pandas as pd
    root, out = args.repo_root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = root / 'examples/portfolio_backtesting/backtest_outputs'
    universe = pd.read_csv(base / 'qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv').product_vt_symbol.tolist()
    mapping = pd.read_csv(base / 'tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv')
    mapping = mapping[mapping.continuous_symbol_vt.isin(universe) & mapping.date.between('2019-06-01', '2026-10-14')].copy()
    mapping = mapping[mapping.main_contract_vt.notna() & mapping.main_contract_vt.str.contains('.', regex=False)]
    with sqlite3.connect(f'file:{root / ".vntrader/database.db"}?mode=ro', uri=True) as db:
        integrity = db.execute('pragma integrity_check').fetchone()[0]
        daily = pd.read_sql_query("select symbol || '.' || exchange as main_contract_vt, substr(datetime,1,10) as date, open_price, high_price, low_price, close_price, volume, open_interest from dbbardata where interval='d'", db)
        db.execute('attach database ? as origin', (f'file:{args.origin_db.resolve()}?mode=ro',))
        # EXCEPT checks every stored value, independent of insertion order/id.
        columns = 'symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price'
        removed_or_changed = db.execute(f'select count(*) from (select {columns} from origin.dbbardata except select {columns} from main.dbbardata)').fetchone()[0]
        added = db.execute(f'select count(*) from (select {columns} from main.dbbardata except select {columns} from origin.dbbardata)').fetchone()[0]
    keys = ['main_contract_vt', 'date']
    if daily.duplicated(keys).any() or mapping.duplicated(['continuous_symbol_vt', 'date']).any():
        raise SystemExit('duplicate daily or mapping keys')
    merged = mapping.merge(daily, on=keys, how='left', indicator=True)
    missing = merged[merged._merge.eq('left_only')]
    present = merged[merged._merge.eq('both')]
    price_cols = ['open_price', 'high_price', 'low_price', 'close_price']
    numeric = present[price_cols + ['volume', 'open_interest']]
    valid = np.isfinite(numeric).all(axis=1) & present[price_cols].gt(0).all(axis=1)
    valid &= present[['volume', 'open_interest']].ge(0).all(axis=1)
    valid &= present.high_price.ge(present[price_cols].max(axis=1)) & present.low_price.le(present[price_cols].min(axis=1))
    invalid = present[~valid]
    # Mapping calendar consistency: each product spans every date in the union
    # from its first available trading day (new listings are not backfilled).
    calendar = sorted(set(mapping.date))
    calendar_gaps = []
    for product, group in mapping.groupby('continuous_symbol_vt'):
        expected = {day for day in calendar if day >= group.date.min()}
        calendar_gaps.extend({'product': product, 'date': day} for day in sorted(expected-set(group.date)))
    missing.to_csv(out / 'daily_missing_mapped_final.csv', index=False)
    invalid.to_csv(out / 'daily_invalid_mapped_final.csv', index=False)
    payload = {
        'sqlite_integrity': integrity, 'daily_rows': len(daily), 'mapped_contract_days_including_warmup': len(mapping),
        'products': len(universe), 'distinct_contracts': int(mapping.main_contract_vt.nunique()),
        'missing_mapped_daily_bars': len(missing), 'invalid_mapped_daily_bars': len(invalid),
        'mapping_calendar_gaps': calendar_gaps, 'origin_rows_removed_or_changed': removed_or_changed,
        'rows_added_to_origin': added, 'latest_completed_trading_date': '2026-10-14',
        'status': 'passed' if integrity == 'ok' and not len(missing) and not len(invalid) and not removed_or_changed and not calendar_gaps else 'failed',
    }
    (out / 'daily_coverage_final.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
