"""Compare real frozen sample serial/parallel contexts and final canonical records.
Selection is structural (direction/product/overlay/background gap), never PnL.
Writes one new validation JSON; does not create a recap or alter financial input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import pandas as pd

import stage001_frozen_recap as base
from stage025_parallel_context_recap import build_contexts


def validate(source, output, *, workers=4, sample_size=12):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    source_manifest_hash = base.sha256(source / 'manifest.json')
    identity, frames, metrics = base.read_bundle(source)
    metadata = frames['contract_metadata.csv']
    products = {str(row.vt_symbol):str(row.product) for row in metadata.itertuples()}
    renderer = base.load_display_functions(products)
    closed = renderer._closed_lots_from_trade_ledger(frames['trades.csv'], sizes=metadata.set_index('vt_symbol')['size'].to_dict(), allow_residual_open=True, source_prefix=identity['run_id'])
    episodes = renderer._all_trade_episodes(closed)
    episodes['draw_intraday'] = 1
    ordered = episodes.sort_values(['entry_date','open_trade_id'])
    selected = []
    def add(frame, reason):
        for row in frame.itertuples(index=False):
            if str(row.open_trade_id) not in [item[0] for item in selected]:
                selected.append((str(row.open_trade_id), reason))
                return
    # Explicitly include both directions and several exchanges/products.
    add(ordered[ordered.direction.eq('long')], 'first_long')
    add(ordered[ordered.direction.eq('short')], 'first_short')
    trades = frames['trades.csv']
    if 'execution_only_quote' in trades:
        overlay_ids = set(trades.loc[trades.execution_only_quote.astype(str).str.lower().eq('true'), 'trade_id'].astype(str))
        overlay_rows = ordered[ordered.close_trade_id.astype(str).apply(lambda value:any(part in overlay_ids for part in value.split(',')))]
        add(overlay_rows, 'actual_execution_quote_overlay_exit')
    mapping, market = frames['mapping.csv'], frames['market_daily.csv']
    market_keys = market[['vt_symbol','date']].drop_duplicates()
    joined = mapping.merge(market_keys, left_on=['main_contract_vt','date'], right_on=['vt_symbol','date'], how='left', indicator=True)
    absent = joined[joined['_merge'].eq('left_only')]
    known_dates = {str(key):set(group['date']) for key,group in market.groupby('vt_symbol',sort=False)}
    missing_by_product = {(str(key[0]).lower(),str(key[1])):list(group.date) for key,group in absent.groupby(['product','exchange'],sort=False)}
    found_gap = False
    for row in ordered.itertuples(index=False):
        missing = missing_by_product.get((str(row.product).lower(),str(row.vt_symbol).split('.')[1]), [])
        exact = known_dates.get(str(row.vt_symbol), set())
        first_month, last_month = pd.Timestamp(row.entry_date).to_period('M') - 10, pd.Timestamp(row.exit_date).to_period('M') + 10
        if any(first_month <= date.to_period('M') <= last_month and date not in exact for date in missing):
            add(ordered[ordered.open_trade_id.eq(row.open_trade_id)], 'missing_exact_and_main_context_quote')
            found_gap = True
            break
    for _, group in ordered.groupby('product',sort=False):
        if len(selected) >= sample_size:
            break
        add(group, 'first_trade_distinct_product')
    sample = episodes[episodes.open_trade_id.astype(str).isin([item[0] for item in selected])].copy()
    cache = {str(key):group.drop(columns='vt_symbol').copy().sort_values('date').reset_index(drop=True) for key,group in market.groupby('vt_symbol',sort=False)}
    def contract_daily(symbol):
        if symbol not in cache:
            raise RuntimeError('Missing local frozen daily bars for '+symbol)
        return cache[symbol]
    renderer._context_daily.__globals__['_contract_daily'] = contract_daily
    groups = base.context_mapping_groups(mapping)
    serial, serial_dates = {}, {}
    started = time.monotonic()
    for row in sample.itertuples(index=False):
        group = groups[(str(row.product).lower(),str(row.vt_symbol).split('.')[1])]
        daily, dates = renderer._context_daily(row, group, cache, allow_daily_download=False,
            allow_noncritical_daily_gaps=True, data_end=pd.Timestamp(identity['end']))
        serial[str(row.open_trade_id)], serial_dates[str(row.open_trade_id)] = daily, dates
    serial_seconds = time.monotonic() - started
    started = time.monotonic()
    parallel, parallel_dates = build_contexts(sample, mapping, cache, pd.Timestamp(identity['end']), workers=workers)
    parallel_seconds = time.monotonic() - started
    for key in serial:
        pd.testing.assert_frame_equal(serial[key], parallel[key])
        if serial[key].attrs != parallel[key].attrs or serial_dates[key] != parallel_dates[key]:
            raise AssertionError('Parallel context attrs/dates differ:'+key)
    minute = pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume'])
    if 'bars_15m.csv' in identity['hashes']:
        path = source/'bars_15m.csv'
        if base.sha256(path)!=identity['hashes']['bars_15m.csv']:
            raise ValueError('minute_hash_changed')
        minute = pd.read_csv(path)
        minute['bar_datetime'] = pd.to_datetime(minute.bar_datetime)
        minute['trading_day'] = pd.to_datetime(minute.trading_day).dt.normalize()
    started = time.monotonic()
    serial_records, serial_manifest = renderer._records(sample, serial, serial_dates, minute)
    record_seconds = time.monotonic() - started
    parallel_records, parallel_manifest = renderer._records(sample, parallel, parallel_dates, minute)
    if renderer._json_safe(serial_records) != renderer._json_safe(parallel_records):
        raise AssertionError('Parallel final canonical records differ')
    pd.testing.assert_frame_equal(serial_manifest, parallel_manifest)
    if base.sha256(source/'manifest.json') != source_manifest_hash:
        raise ValueError('Source changed during validation')
    canonical_records = json.dumps(renderer._json_safe(serial_records),ensure_ascii=False,separators=(',',':'))
    result = {
        'status':'PASS', 'source':str(source), 'source_manifest_sha256':source_manifest_hash,
        'canonical_renderer_sha256':base.sha256(base.CANONICAL),
        'adapter_sha256':base.sha256(Path(base.__file__)),
        'parallel_entry_sha256':base.sha256(Path(__file__).with_name('stage025_parallel_context_recap.py')),
        'validator_sha256':base.sha256(Path(__file__)), 'workers':workers,
        'sample_episodes':len(sample), 'full_episodes':len(episodes),
        'products':sorted(sample['product'].unique().tolist()), 'directions':sorted(sample.direction.unique().tolist()),
        'selection_reasons':dict(selected), 'missing_context_candidate_found':found_gap,
        'sample_missing_context_days':sum(len(frame.attrs.get('missing_context_dates',[])) for frame in serial.values()),
        'sample_proxy_context_days':sum(int(frame.context_fallback.sum()) for frame in serial.values()),
        'serial_context_seconds':serial_seconds, 'parallel_context_seconds':parallel_seconds,
        'serial_records_seconds':record_seconds,
        'full_serial_context_linear_estimate_seconds':serial_seconds/len(sample)*len(episodes),
        'full_parallel_context_linear_estimate_seconds':parallel_seconds/len(sample)*len(episodes),
        'full_serial_records_linear_estimate_seconds':record_seconds/len(sample)*len(episodes),
        'contexts_values_attrs_dates_equal':True, 'final_records_and_manifest_equal':True,
        'records_sha256':hashlib.sha256(canonical_records.encode()).hexdigest(),
        'financial_replays':0, 'market_downloads':0, 'source_mutations':0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=range(1,5), default=4)
    parser.add_argument('--sample-size', type=int, default=12)
    args=parser.parse_args()
    validate(args.source,args.output,workers=args.workers,sample_size=args.sample_size)


if __name__=='__main__':
    main()
