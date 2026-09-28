from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import traceback

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage036_full_minute_source'
OUTPUT = ROOT / 'artifacts' / STAGE
CONTRACT = ROOT / 'stages/20260906_0916_stage036_full_minute_source_contract.md'
FREEZE = ROOT / 'stages/stage036_input_freeze.json'
CACHE_LINE = ROOT.parents[2] / '.worktrees/stage080-nextday-hourly-long-add/research/lines/futures_trend_nextday_hourly_long_add'
CACHE = CACHE_LINE / 'artifacts/stage085/inputs'
SOURCE_MANIFEST_SHA = '4b6655ec696699345475b8506f35192d586cfb9b0bd149a51c35f9f5915da0ec'
VALUES = ['open', 'high', 'low', 'close', 'volume']


def window_module():
    spec = importlib.util.spec_from_file_location('source_window035', ROOT / 'tools/stage035_next_window.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


WINDOW = window_module()


def safe_path(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('source_path_outside_cache')
    return path


def unique_entries(manifest):
    result = {}
    for row in manifest['files']:
        symbol = row['vt_symbol']
        if symbol in result:
            raise ValueError('source_duplicate_contract')
        result[symbol] = row
    return result


def normalize(frame, expected, symbol):
    result = frame.copy()
    clock = expected.copy()
    keys = ['vt_symbol', 'bar_datetime', 'bar_date']
    for value in (result, clock):
        value['bar_datetime'] = WINDOW.parse_clock(value.bar_datetime)
        if (value.empty or not value.vt_symbol.eq(symbol).all()
                or value.bar_datetime.duplicated().any()
                or not value.bar_datetime.is_monotonic_increasing
                or not value.bar_date.astype(str).str.fullmatch(r'\d{4}-\d{2}-\d{2}').all()):
            raise ValueError('source_invalid_clock_or_symbol')
    if not result[keys].reset_index(drop=True).equals(clock[keys].reset_index(drop=True)):
        raise ValueError('source_minute_clock_or_trading_day_mismatch')
    for name in VALUES:
        result[name] = pd.to_numeric(result[name], errors='raise')
    valid = np.isfinite(result[VALUES]).all(axis=1)
    valid &= result[VALUES[:4]].gt(0).all(axis=1) & result.volume.ge(0)
    valid &= result.high.ge(result[['open', 'low', 'close']].max(axis=1))
    valid &= result.low.le(result[['open', 'high', 'close']].min(axis=1))
    if not valid.all():
        raise ValueError('source_invalid_ohlcv')
    return result


def aggregate_day(frame):
    active = frame[frame.volume.gt(0)]
    status = 'positive_volume'
    if active.empty:
        active = frame
        values = frame[VALUES[:4]].to_numpy()
        status = 'untraded_flat' if np.all(values == values.flat[0]) else 'untraded_nonflat'
    return {
        'open': float(active.open.iloc[0]), 'high': float(active.high.max()),
        'low': float(active.low.min()), 'close': float(active.close.iloc[-1]),
        'volume': float(active.volume.sum()),
    }, status


def same_values(left, right):
    if left is None or right is None:
        return False
    return all(math.isfinite(float(left[name])) and math.isfinite(float(right[name]))
               and (float(left[name]) == float(right[name]) if name == 'volume'
                    else abs(float(left[name]) - float(right[name])) <= 1e-7) for name in VALUES)


@contextmanager
def readonly_database(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        yield connection
    finally:
        connection.close()


def daily_reference(connection, vt_symbol):
    symbol, exchange = vt_symbol.rsplit('.', 1)
    rows = connection.execute(
        'SELECT datetime, open_price, high_price, low_price, close_price, volume '
        'FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? ORDER BY datetime',
        (symbol, exchange, 'd')).fetchall()
    result = {}
    for row in rows:
        day = row[0][:10]
        if day in result:
            raise ValueError('source_duplicate_A_daily')
        result[day] = dict(zip(VALUES, row[1:]))
    return result


def qualify(bars, expected, day, next_day, night, quantity, parity, guards):
    if not math.isfinite(quantity) or quantity <= 0 or quantity != int(quantity):
        raise ValueError('source_invalid_observed_quantity')
    result = WINDOW.evaluate(bars, day, next_day, night, quantity)
    result['proxy_status'] = result['status']
    result['observation_daily_compatible'] = bool(parity.get(day, False))
    result['next_daily_compatible'] = bool(parity.get(next_day, False))
    result['required_guard_day'] = day in guards or next_day in guards
    result['window_clock_complete'] = False
    result['expected_open_matches'] = False
    if 'start' in result:
        start, end = pd.Timestamp(result['start']), pd.Timestamp(result['end_exclusive'])
        actual = bars[bars.bar_datetime.ge(start) & bars.bar_datetime.lt(end)]
        legal = expected[expected.bar_datetime.ge(start) & expected.bar_datetime.lt(end)]
        ticks = list(pd.date_range(start, end, freq='min', inclusive='left'))
        result['window_clock_complete'] = (
            list(actual.bar_datetime) == ticks == list(legal.bar_datetime)
            and actual.bar_date.eq(next_day).all() and legal.bar_date.eq(next_day).all())
        future = expected[expected.bar_date.eq(next_day)
                          & expected.bar_datetime.gt(pd.Timestamp(day) + pd.Timedelta(hours=15))]
        if not future.empty:
            first = future.bar_datetime.min().isoformat()
            result['first_expected_time'] = first
            result['expected_open_matches'] = first == result.get('first_time')
    # Preserve the original price/volume result separately from new source gates.
    if result['proxy_status'] == 'proxy_supported':
        if not result['window_clock_complete']:
            result['status'] = 'window_clock_incomplete'
        elif not result['expected_open_matches']:
            result['status'] = 'expected_open_mismatch'
        elif result['required_guard_day']:
            result['status'] = 'source_guard_day'
        elif not result['observation_daily_compatible'] or not result['next_daily_compatible']:
            result['status'] = 'required_daily_parity_failed'
        else:
            result['status'] = 'source_proxy_qualified_not_execution'
    result['window_clock_complete'] = bool(result['window_clock_complete'])
    return result


def states_and_source():
    raw = (CACHE / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_MANIFEST_SHA:
        raise ValueError('source_manifest_changed_since_inventory')
    source = json.loads(raw)
    states = json.loads(gzip.decompress((WINDOW.SOURCE / 'holding_cost_states.json.gz').read_bytes()))
    states = [row for row in states if row['inventory_state_status'] == 'inventory_reconciled_holding']
    if len(states) != 1002 or any(len(row['contract_costs']) != 1 for row in states):
        raise ValueError('source_observation_inventory_changed')
    symbols = {next(iter(row['contract_costs'])) for row in states}
    entries = unique_entries(source)
    if len(symbols) != 120 or not symbols <= entries.keys():
        raise ValueError('source_candidate_contract_missing')
    return states, source, {symbol: entries[symbol] for symbol in sorted(symbols)}


def collect_inputs():
    files = WINDOW.collect_inputs()
    files.update(full_source_runner=Path(__file__).resolve(), full_source_contract=CONTRACT,
                 full_source_tests=ROOT / 'tests/test_stage036_full_minute_source.py',
                 old_window_freeze=WINDOW.FREEZE, old_window_summary=WINDOW.OUTPUT / 'summary.json',
                 old_window_manifest=WINDOW.OUTPUT / 'input_manifest.json', old_windows=WINDOW.OUTPUT / 'windows.csv',
                 new_source_manifest=CACHE / 'manifest.json')
    _, source, entries = states_and_source()
    for key in ('calendar', 'collection_plan', 'nontradable_guard_days', 'quality_blockers'):
        files['new_source_' + key] = safe_path(CACHE, source[key + '_path'])
    files['new_source_request'] = CACHE / 'request.json'
    for symbol, entry in entries.items():
        files[f'new_minutes/{symbol}'] = safe_path(CACHE, entry['path'])
        for key in ('expected_minutes', 'daily_reference', 'sessions', 'audit'):
            files[f'new_{key}/{symbol}'] = safe_path(CACHE, entry[key + '_path'])
    for name in ('stage081_market_data.py', 'stage082_market_data.py', 'stage085_full_history.py'):
        files['new_source_producer/' + name] = CACHE_LINE / 'tools' / name
    return dict(sorted(files.items()))


def configured():
    runner = WINDOW.configured()
    runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = len(collect_inputs())
    return runner


def verify_source_assets(source, entries):
    for key in ('calendar', 'collection_plan', 'nontradable_guard_days', 'quality_blockers'):
        path = safe_path(CACHE, source[key + '_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != source[key + '_sha256']:
            raise ValueError('source_metadata_hash_mismatch:' + key)
    for symbol, entry in entries.items():
        pairs = [('path', 'sha256')]
        pairs += [(key + '_path', key + '_sha256') for key in ('expected_minutes', 'daily_reference', 'sessions')]
        for path_key, sha_key in pairs:
            if hashlib.sha256(safe_path(CACHE, entry[path_key]).read_bytes()).hexdigest() != entry[sha_key]:
                raise ValueError('source_contract_file_changed:' + symbol + ':' + path_key)


def run():
    if OUTPUT.exists():
        raise RuntimeError('source_campaign_already_exists')
    runner = configured(); manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    old = WINDOW.configured()
    old_manifest = json.loads((WINDOW.OUTPUT / 'input_manifest.json').read_text())
    old.validate_frozen_input_contract(WINDOW.FREEZE, old_manifest)
    old.validate_current_input_manifest(old_manifest)
    old_summary = json.loads((WINDOW.OUTPUT / 'summary.json').read_text())
    if runner._file_identity(WINDOW.OUTPUT / 'windows.csv') != old_summary['output']:
        raise ValueError('source_old_window_output_changed')
    batch = WINDOW.inventory_tool().load('stage004_label_batch')
    OUTPUT.mkdir(mode=0o700)
    batch.write_json(OUTPUT / 'input_manifest.json', manifest)
    try:
        states, source, entries = states_and_source()
        verify_source_assets(source, entries)
        calendar = pd.read_csv(WINDOW.inventory_tool().SOURCE / 'workers/A/daily.csv.gz', usecols=['date']).date.tolist()
        source_calendar = [row['date'] for row in json.loads((CACHE / source['calendar_path']).read_text())['rows'] if row['trading']]
        if calendar != [day for day in source_calendar if calendar[0] <= day <= calendar[-1]]:
            raise ValueError('source_A_calendar_mismatch')
        next_date = dict(zip(calendar, calendar[1:]))
        night_path = Path(manifest['files']['production_portfolio/analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py']['path'])
        nights = WINDOW.night_products(night_path)
        state_groups = {}
        for row in states:
            state_groups.setdefault(next(iter(row['contract_costs'])), []).append(row)
        guards = {(row['vt_symbol'], row['bar_date']) for row in source['nontradable_guard_days']}
        daily_rows = []; windows = []; contracts = []
        with readonly_database(Path(manifest['files']['source_database']['path'])) as connection:
            for ordinal, (symbol, entry) in enumerate(entries.items(), 1):
                raw = pd.read_csv(CACHE / entry['path'])
                expected = pd.read_csv(CACHE / entry['expected_minutes_path'], usecols=['vt_symbol', 'bar_datetime', 'bar_date'])
                frame = normalize(raw, expected, symbol)
                expected['bar_datetime'] = WINDOW.parse_clock(expected.bar_datetime)
                if len(frame) != entry['rows']:
                    raise ValueError('source_row_count_mismatch:' + symbol)
                reference = pd.read_csv(CACHE / entry['daily_reference_path'])
                if reference.bar_date.duplicated().any():
                    raise ValueError('source_duplicate_daily_reference')
                source_daily = reference.set_index('bar_date')[VALUES].to_dict('index')
                a_daily = daily_reference(connection, symbol)
                parity = {}; local_rows = []
                for day, portion in frame.groupby('bar_date', sort=True):
                    aggregate, status = aggregate_day(portion)
                    provider = source_daily.get(day); baseline = a_daily.get(day)
                    match_source = same_values(aggregate, provider)
                    match_a = same_values(aggregate, baseline)
                    source_a = same_values(provider, baseline)
                    qualified = status != 'untraded_nonflat' and match_source and match_a and source_a
                    parity[day] = qualified
                    item = {'vt_symbol': symbol, 'bar_date': day, 'minute_count': len(portion),
                            'aggregate_status': status, 'minute_source_match': match_source,
                            'minute_A_match': match_a, 'source_A_match': source_a,
                            'A_reference_present': baseline is not None, 'source_reference_present': provider is not None,
                            'source_guard_day': (symbol, day) in guards, 'daily_compatible': qualified}
                    for prefix, values in [('minute', aggregate), ('source', provider), ('A', baseline)]:
                        item.update({prefix + '_' + name: values[name] if values else None for name in VALUES})
                    local_rows.append(item)
                daily_rows.extend(local_rows)
                for row in state_groups[symbol]:
                    day = row['date']; quantity = abs(float(row['contract_costs'][symbol]['quantity']))
                    result = qualify(frame, expected, day, next_date.get(day), row['product_vt_symbol'] in nights,
                                     quantity, parity, {date for contract, date in guards if contract == symbol})
                    windows.append({'date': day, 'next_calendar_day': next_date.get(day), 'vt_symbol': symbol,
                                    'product_vt_symbol': row['product_vt_symbol'], 'actual_volume': quantity, **result})
                contracts.append({'vt_symbol': symbol, 'minute_rows': len(frame), 'daily_rows': len(local_rows),
                                  'compatible_days': sum(parity.values()), 'observation_count': len(state_groups[symbol])})
                if ordinal % 20 == 0:
                    print(json.dumps({'stage': STAGE, 'contracts_done': ordinal, 'contracts_total': len(entries)}), flush=True)
        if len(windows) != len(states):
            raise ValueError('source_observation_dropped')
        runner.validate_current_input_manifest(manifest)
        outputs = {}
        for name, values in [('windows', windows), ('daily_comparison', daily_rows), ('contracts', contracts)]:
            frame = pd.DataFrame(values)
            if name == 'windows': frame = frame.sort_values(['date', 'product_vt_symbol'])
            path = OUTPUT / (name + '.csv')
            runner._write_bytes_exclusive(path, frame.to_csv(index=False).encode())
            outputs[name] = runner._file_identity(path)
        counts = dict(Counter(row['status'] for row in windows))
        passed = counts.get('source_proxy_qualified_not_execution', 0) == len(states)
        result = {
            'stage': STAGE, 'status': 'source_proxy_qualified_not_execution' if passed else 'source_proxy_qualification_failed',
            'observation_count': len(windows), 'candidate_contract_count': len(contracts),
            'source_minute_rows': sum(row['minute_rows'] for row in contracts), 'daily_comparison_count': len(daily_rows),
            'daily_compatible_count': sum(row['daily_compatible'] for row in daily_rows),
            'daily_guard_count': sum(row['source_guard_day'] for row in daily_rows),
            'daily_aggregate_status_counts': dict(Counter(row['aggregate_status'] for row in daily_rows)),
            'daily_mismatch_counts': {key: sum(not row[key] for row in daily_rows) for key in
                                      ['minute_source_match', 'minute_A_match', 'source_A_match', 'A_reference_present']},
            'status_counts': counts, 'proxy_status_counts': dict(Counter(row['proxy_status'] for row in windows)),
            'gate_counts': {key: sum(row[key] for row in windows) for key in
                            ['observation_daily_compatible', 'next_daily_compatible', 'required_guard_day',
                             'window_clock_complete', 'expected_open_matches']},
            'source_manifest_sha256': SOURCE_MANIFEST_SHA,
            'source_global_coverage_complete': source['coverage_complete'],
            'source_conditional_coverage_inherited': False, 'all_observations_qualified': passed,
            'A_calendar_exact': True, 'file_contract_sha256': manifest['file_contract_sha256'], 'outputs': outputs,
            'new_download_count': 0, 'new_replay_count': 0, 'new_utility_label_count': 0,
            'model_fit_predict_count': 0, 'reviewer_started': False,
        }
        batch.write_json(OUTPUT / 'summary.json', result)
        print(json.dumps(result), flush=True)
    except BaseException as exc:
        batch.write_json(OUTPUT / 'failure.json', {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        runner = configured(); manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        value = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
                 'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        value['execution_authorized'] = True
        WINDOW.inventory_tool().load('stage004_label_batch').write_json(FREEZE, value)
        print(json.dumps(value), flush=True)
    else:
        run()


if __name__ == '__main__':
    main()
