import hashlib
import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage046_dynamic_exit_source.py'
DAYS = ['2021-01-08', '2021-01-11', '2021-01-12']
SYMBOL = 'jm2105.DCE'


def module():
    assert TOOL.exists(), 'dynamic exit data provider is not implemented'
    spec = importlib.util.spec_from_file_location('test_dynamic046', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True))


def make_source(tmp_path, change=None):
    cache = tmp_path / 'cache'; cache.mkdir()
    chunks = []
    for i, (start, day) in enumerate([('2021-01-08 09:00', DAYS[0]), ('2021-01-08 21:00', DAYS[1]),
            ('2021-01-11 09:00', DAYS[1]), ('2021-01-11 21:00', DAYS[2]), ('2021-01-12 09:00', DAYS[2])]):
        chunks.append(pd.DataFrame({'vt_symbol': SYMBOL, 'bar_datetime': pd.date_range(start, periods=5, freq='min'),
            'bar_date': day, 'open': 100. + i, 'high': 101. + i, 'low': 99. + i, 'close': 100. + i, 'volume': 10.}))
    frame = pd.concat(chunks, ignore_index=True)
    if change == 'day_only':
        frame = frame.loc[~frame.bar_datetime.dt.hour.eq(21)].reset_index(drop=True)
    if change == 'zero_first':
        frame.loc[5, 'volume'] = 0.
    clock = frame[['vt_symbol', 'bar_datetime', 'bar_date']].copy()
    if change == 'missing_first':
        frame = frame.drop(index=5)
    if change == 'wrong_clock':
        mask = frame.bar_date.eq(DAYS[1]) & frame.bar_datetime.dt.hour.eq(21)
        frame.loc[mask, 'bar_datetime'] += pd.Timedelta(minutes=30)
        clock = frame[['vt_symbol', 'bar_datetime', 'bar_date']].copy()
    if change == 'invalid_ohlc':
        frame.loc[5, 'low'] = 10000.
    records = []
    for day, daily in frame.groupby('bar_date'):
        active = daily[daily.volume.gt(0)]
        records.append({'bar_date': day, 'open': float(active.open.iloc[0]), 'high': float(active.high.max()),
            'low': float(active.low.min()), 'close': float(active.close.iloc[-1]), 'volume': float(active.volume.sum())})
    reference = pd.DataFrame(records)
    database = tmp_path / 'original.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE dbbardata (symbol TEXT, exchange TEXT, datetime TEXT, interval TEXT, open_price REAL, high_price REAL, low_price REAL, close_price REAL, volume REAL)')
        connection.executemany('INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?)', [('jm2105', 'DCE', r['bar_date'] + ' 00:00:00', 'd',
            r['open'], r['high'], r['low'], r['close'] + (1 if change == 'A_mismatch' and r['bar_date'] == DAYS[1] else 0),
            r['volume']) for r in records])
    private = tmp_path / 'private.db'; shutil.copyfile(database, private)
    if change == 'source_mismatch':
        reference.loc[reference.bar_date.eq(DAYS[0]), 'close'] += 1
    frame.to_csv(cache / 'minutes.csv', index=False)
    clock.to_csv(cache / 'expected.csv.gz', index=False, compression='gzip')
    reference.to_csv(cache / 'daily.csv', index=False)
    write(cache / 'sessions.json', {'synthetic_sessions': True})
    write(cache / 'audit.json', {'synthetic_only': True})
    entry = {'vt_symbol': SYMBOL, 'status': 'complete', 'path': 'minutes.csv', 'sha256': identity(cache / 'minutes.csv')['sha256'],
        'rows': len(frame), 'audit_path': 'audit.json'}
    for key, name in [('expected_minutes', 'expected.csv.gz'), ('daily_reference', 'daily.csv'), ('sessions', 'sessions.json')]:
        entry[key + '_path'] = name; entry[key + '_sha256'] = identity(cache / name)['sha256']
    if change == 'row_count':
        entry['rows'] += 1
    if change == 'incomplete':
        entry['status'] = 'failed'
    guards = [{'vt_symbol': SYMBOL, 'bar_date': DAYS[0 if change == 'guard_observation' else 1]}] if change in {'guard_observation', 'guard_next'} else []
    source = {'files': [entry], 'nontradable_guard_days': guards, 'coverage_complete': False}
    for key, value in [('calendar', {'rows': [{'date': day, 'trading': True} for day in DAYS]}),
            ('nontradable_guard_days', {'days': guards}), ('collection_plan', {'synthetic': True}), ('quality_blockers', {'synthetic': True})]:
        path = cache / (key + '.json'); write(path, value)
        source[key + '_path'] = path.name; source[key + '_sha256'] = identity(path)['sha256']
    write(cache / 'manifest.json', source)
    files = {'source_database': identity(database)} | {path.name: identity(path) for path in cache.iterdir()}
    return {'cache': cache, 'files': files, 'database': private, 'calendar': DAYS,
        'expected_source_sha256': identity(cache / 'manifest.json')['sha256']}


def provider(tmp_path, change=None):
    setup = make_source(tmp_path, change)
    return module().DynamicExitSource(**setup), setup


def intent(day=DAYS[0], volume=2, symbol=SYMBOL):
    return {'order_id': 'BACKTESTING.dynamic-C', 'decision_date': day, 'vt_symbol': symbol, 'volume': volume}


def test_dynamic_intent_uses_exact_contract_clock_and_private_readonly_reference(tmp_path):
    value, setup = provider(tmp_path)
    original = setup['database'].read_bytes()
    quote = value(intent(), DAYS[1])
    assert quote['price'] == 101. and quote['first_time'] == '2021-01-08T21:00:00'
    assert quote['fill_date'] == DAYS[1] and quote['source'] == 'stage046_dynamic_full_minute'
    assert setup['database'].read_bytes() == original
    value.verify_used_inputs()
    receipt = value.receipt()
    assert receipt['request_count'] == receipt['qualified_count'] == 1
    assert receipt['loaded_contracts'] == [SYMBOL] and receipt['source_global_coverage_complete'] is False


def test_quantity_is_rechecked_after_contract_data_is_cached(tmp_path):
    value, _ = provider(tmp_path)
    value(intent(volume=10), DAYS[1])
    with pytest.raises(RuntimeError, match='first_bar_volume_insufficient'):
        value(intent(volume=11), DAYS[1])
    assert value.receipt()['loaded_contracts'] == [SYMBOL]
    assert value.receipt()['request_count'] == 2 and value.receipt()['qualified_count'] == 1


def test_new_date_request_is_not_restricted_to_an_A_observation_table(tmp_path):
    value, _ = provider(tmp_path)
    first = value(intent(), DAYS[1]); second = value(intent(day=DAYS[1]), DAYS[2])
    assert first['price'] == 101. and second['price'] == 103.
    assert second['first_time'] == '2021-01-11T21:00:00'


def test_calendar_without_night_uses_next_nine_am(tmp_path):
    value, _ = provider(tmp_path, 'day_only')
    assert value(intent(), DAYS[1])['first_time'] == '2021-01-11T09:00:00'


@pytest.mark.parametrize('change,error', [('zero_first', 'first_bar_volume_insufficient'),
    ('missing_first', 'clock_or_trading_day'), ('wrong_clock', 'unsupported_expected_anchor'),
    ('invalid_ohlc', 'invalid_ohlcv'), ('A_mismatch', 'required_daily_parity_failed'),
    ('source_mismatch', 'required_daily_parity_failed'), ('guard_observation', 'source_guard_day'),
    ('guard_next', 'source_guard_day'), ('row_count', 'row_count'), ('incomplete', 'contract_not_complete')])
def test_unqualified_request_aborts_instead_of_holding_or_changing_window(tmp_path, change, error):
    value, _ = provider(tmp_path, change)
    with pytest.raises((ValueError, RuntimeError), match=error):
        value(intent(), DAYS[1])


@pytest.mark.parametrize('volume', [0, -1, 1.5, float('nan'), float('inf'), None])
def test_invalid_actual_quantity_is_not_coerced_into_a_trade(tmp_path, volume):
    value, _ = provider(tmp_path)
    with pytest.raises((RuntimeError, ValueError), match='quantity'):
        value(intent(volume=volume), DAYS[1])


@pytest.mark.parametrize('day,fill', [(DAYS[0], DAYS[0]), (DAYS[0], DAYS[2]), (DAYS[2], '2021-01-13'),
    ('2021-01-09', DAYS[1]), ('20210108', DAYS[1])])
def test_no_same_day_delayed_missing_or_invented_calendar_fill(tmp_path, day, fill):
    value, _ = provider(tmp_path)
    with pytest.raises((RuntimeError, ValueError)):
        value(intent(day=day), fill)


def test_unknown_C_contract_is_not_mapped_to_another_contract(tmp_path):
    value, _ = provider(tmp_path)
    with pytest.raises(RuntimeError, match='contract_missing'):
        value(intent(symbol='jm9999.DCE'), DAYS[1])


@pytest.mark.parametrize('name', ['minutes.csv', 'expected.csv.gz', 'daily.csv', 'sessions.json', 'audit.json'])
def test_consumed_source_file_is_hash_checked_before_use(tmp_path, name):
    value, setup = provider(tmp_path)
    with (setup['cache'] / name).open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(RuntimeError, match='changed'):
        value(intent(), DAYS[1])


@pytest.mark.parametrize('name', ['manifest.json', 'calendar.json', 'nontradable_guard_days.json'])
def test_metadata_drift_is_rejected_during_construction(tmp_path, name):
    setup = make_source(tmp_path)
    with (setup['cache'] / name).open('ab') as stream:
        stream.write(b' ')
    with pytest.raises(RuntimeError, match='changed'):
        module().DynamicExitSource(**setup)


def test_database_drift_after_construction_is_rejected_before_parity_read(tmp_path):
    value, setup = provider(tmp_path)
    with sqlite3.connect(setup['database']) as connection:
        connection.execute('UPDATE dbbardata SET close_price=1000')
    with pytest.raises(RuntimeError, match='database_changed'):
        value(intent(), DAYS[1])


def test_cached_file_drift_is_still_caught_at_end(tmp_path):
    value, setup = provider(tmp_path)
    value(intent(), DAYS[1])
    with (setup['cache'] / 'minutes.csv').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(RuntimeError, match='changed'):
        value.verify_used_inputs()


def test_missing_frozen_source_binding_cannot_be_added_on_demand(tmp_path):
    setup = make_source(tmp_path); del setup['files']['minutes.csv']
    with pytest.raises(RuntimeError, match='not_bound'):
        module().DynamicExitSource(**setup)


def test_supplied_calendar_must_equal_source_calendar_in_the_same_range(tmp_path):
    setup = make_source(tmp_path); setup['calendar'] = [DAYS[0], DAYS[2]]
    with pytest.raises(RuntimeError, match='calendar'):
        module().DynamicExitSource(**setup)


def test_source_symlink_does_not_pass_by_resolving_to_an_approved_file(tmp_path):
    value, setup = provider(tmp_path)
    path = setup['cache'] / 'minutes.csv'; copy = setup['cache'] / 'copy.csv'
    shutil.copyfile(path, copy); path.unlink(); path.symlink_to(copy)
    with pytest.raises((ValueError, RuntimeError), match='symlink|bound|changed'):
        value(intent(), DAYS[1])


@pytest.mark.parametrize('shared', ['same_path', 'hardlink'])
def test_original_database_cannot_be_used_as_the_private_copy(tmp_path, shared):
    import os

    setup = make_source(tmp_path); original = Path(setup['files']['source_database']['path'])
    if shared == 'same_path':
        setup['database'] = original
    else:
        setup['database'].unlink(); os.link(original, setup['database'])
    with pytest.raises(RuntimeError, match='private_database_copy'):
        module().DynamicExitSource(**setup)


def test_source_path_cannot_escape_cache_even_when_external_file_is_bound(tmp_path):
    setup = make_source(tmp_path)
    manifest_path = setup['cache'] / 'manifest.json'; manifest = json.loads(manifest_path.read_text())
    outside = tmp_path / 'outside.csv'; shutil.copyfile(setup['cache'] / 'minutes.csv', outside)
    manifest['files'][0]['path'] = '../outside.csv'; write(manifest_path, manifest)
    setup['files']['outside'] = identity(outside); setup['files']['manifest.json'] = identity(manifest_path)
    setup['expected_source_sha256'] = identity(manifest_path)['sha256']
    with pytest.raises((ValueError, RuntimeError), match='outside_cache'):
        module().DynamicExitSource(**setup)


def test_cold_os_sandbox_consumes_dynamic_source_without_model_or_broker_calls(tmp_path):
    import subprocess
    import sys

    setup = make_source(tmp_path)
    baseline_path = ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage003_frozen_baseline_event_qualification.py'
    spec = importlib.util.spec_from_file_location('dynamic046_baseline', baseline_path)
    baseline = importlib.util.module_from_spec(spec); spec.loader.exec_module(baseline)
    p = baseline.load_runner().load_metadata_preflight_module().load_preflight_module()
    paths = p.prepare_worker_root(tmp_path / 'cold_worker')
    p.write_sandbox_profile(paths['profile'], paths['worker_root'])
    model_spec = json.loads((ROOT / 'artifacts/stage040_holding_panel/model_spec.json').read_text())
    encoded = {key: str(value) if isinstance(value, Path) else value for key, value in setup.items()}
    code = '\n'.join([
        'import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace',
        f'baseline=SimpleNamespace(**runpy.run_path({str(baseline_path)!r}))',
        'p=baseline.load_runner().load_metadata_preflight_module().load_preflight_module()',
        f"p._validate_worker_bootstrap(Path({str(paths['runtime'])!r}))",
        f"p.prove_external_write_denied(Path({str(tmp_path / 'outside_probe')!r}))",
        'sys.path.extend([str(p.python_site_packages())])',
        f"factory=runpy.run_path({str(ROOT / 'tools/stage045_holding_inference.py')!r})['holding_guard_class']",
        f"guard=factory(p,baseline)((Path({str(paths['worker_root'])!r}),),registry={{}},spec={model_spec!r})",
        f"provider=runpy.run_path({str(TOOL)!r})['DynamicExitSource']",
        'guard.assert_no_sensitive_modules_loaded()',
        'with p.NetworkBlock(),guard:',
        f' value=provider(**{encoded!r})',
        f' quote=value({intent()!r},{DAYS[1]!r})',
        ' value.verify_used_inputs()',
        "assert quote['price']==101. and not any(guard.counters.values()) and guard.decision_count==0",
        'print(json.dumps(value.receipt()))'])
    result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
        '-I', '-S', '-B', '-c', code], cwd=paths['runtime'], env=p.expected_worker_environment(paths['runtime']),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['qualified_count'] == 1 and receipt['A_observation_table_used'] is False
    assert not (tmp_path / 'outside_probe').exists()
