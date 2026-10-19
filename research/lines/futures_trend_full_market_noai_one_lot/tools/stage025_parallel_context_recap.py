"""Optional read-only, at-most-four-process context adapter for frozen Stage038 recaps.

Each spawned worker receives only one product/exchange mapping and its possible
exact/main contract bars. Canonical context and record functions remain verbatim.
No financial replay, historical fetch, or mutation of the frozen source occurs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace
import time

import pandas as pd

import stage001_frozen_recap as base


def _key(row):
    product_value = str(row.product)
    product, exchange = product_value.split('.', 1) if '.' in product_value else (product_value, str(row.vt_symbol).split('.', 1)[1])
    return product.lower(), exchange


def _product_contexts(payload):
    rows, mapping, cache, data_end = payload
    renderer = base.load_display_functions({})
    def contract_daily(symbol):
        if symbol not in cache:
            raise RuntimeError('Missing local frozen daily bars for ' + symbol)
        return cache[symbol]
    renderer._context_daily.__globals__['_contract_daily'] = contract_daily
    daily_by_episode, dates_by_episode = {}, {}
    for record in rows:
        row = SimpleNamespace(**record)
        daily, dates = renderer._context_daily(row, mapping, cache, allow_daily_download=False,
            allow_noncritical_daily_gaps=True, data_end=data_end)
        daily_by_episode[str(row.open_trade_id)] = daily
        dates_by_episode[str(row.open_trade_id)] = dates
    return daily_by_episode, dates_by_episode


def build_contexts(episodes, mapping, bar_cache, data_end, *, workers=4):
    if not isinstance(workers, int) or not 1 <= workers <= 4:
        raise ValueError('workers must be an integer from 1 through 4')
    groups = base.context_mapping_groups(mapping)
    rows_by_product = {}
    for row in episodes.itertuples(index=False):
        rows_by_product.setdefault(_key(row), []).append(row._asdict())
    payloads = []
    for key, rows in sorted(rows_by_product.items(), key=lambda item: -len(item[1])):
        product_mapping = groups.get(key, mapping.iloc[:0])
        symbols = set(product_mapping['main_contract_vt'].astype(str)) | {str(row['vt_symbol']) for row in rows}
        cache = {symbol:bar_cache[symbol] for symbol in symbols if symbol in bar_cache}
        payloads.append((rows, product_mapping, cache, data_end))
    all_daily, all_dates = {}, {}
    if workers == 1:
        results = map(_product_contexts, payloads)
        for daily, dates in results:
            all_daily.update(daily)
            all_dates.update(dates)
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            futures = [pool.submit(_product_contexts, payload) for payload in payloads]
            for future in as_completed(futures):
                daily, dates = future.result()
                all_daily.update(daily)
                all_dates.update(dates)
                print(f'Parallel canonical context {len(all_daily)}/{len(episodes)} ({workers} workers)', flush=True)
    ids = episodes['open_trade_id'].astype(str).tolist()
    if set(all_daily) != set(ids) or set(all_dates) != set(ids) or len(set(ids)) != len(ids):
        raise ValueError('Parallel context episode identity mismatch')
    return {key:all_daily[key] for key in ids}, {key:all_dates[key] for key in ids}


def render_parallel(source, output, *, workers=4):
    entry = Path(__file__).resolve()
    provenance = {'mode':'product_partitioned_spawn', 'workers':workers,
                  'entry':str(entry), 'entry_sha256':base.sha256(entry),
                  'canonical_functions_changed':False, 'financial_replay_performed':False}
    return base.render_bundle(Path(source), Path(output),
        context_builder=partial(build_contexts, workers=workers), context_provenance=provenance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=range(1,5), default=4)
    args = parser.parse_args()
    started = time.monotonic()
    summary = render_parallel(args.source, args.output, workers=args.workers)
    print(json.dumps({'run_id':summary['run_id'], 'chart_episodes':summary['chart_episodes'],
                      'workers':args.workers, 'elapsed_seconds':time.monotonic()-started}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
