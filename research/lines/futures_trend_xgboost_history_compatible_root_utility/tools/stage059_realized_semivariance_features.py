from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from functools import lru_cache
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/stage059_realized_semivariance_features'
CONTRACT = ROOT / 'stages/20260907_0913_stage058_semivariance_information_contract.md'
BASE_FEATURES = ('directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
    'directional_close_location', 'log_holding_bars', 'layer_stop_buffer',
    'portfolio_drawdown', 'margin_to_equity', 'loss_streak')
FEATURES = ('favorable_semivariance_5m', 'adverse_semivariance_5m')
IDS = ('observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('semivariance059_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def candidate_spec(base):
    if base['features'] != list(BASE_FEATURES):
        raise RuntimeError('semivariance_base_features_changed')
    result = copy.deepcopy(base)
    result['features'] = [*BASE_FEATURES, *FEATURES]
    return result


def features_for_day(bars, expected, job, reference, guards):
    source = load('stage036_full_minute_source')
    day, symbol = job['date'], job['vt_symbol']
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('semivariance_date_invalid')
    snapshot = job['snapshot']; positions = snapshot['actual_positions']; bar = snapshot['bar']
    if (snapshot['phase'] != 'after_strategy_on_bars' or set(positions) != {symbol}
            or bar['vt_symbol'] != symbol or bar['datetime'][:10] != day):
        raise ValueError('semivariance_current_state_invalid')
    quantity = float(positions[symbol])
    if not math.isfinite(quantity) or quantity == 0 or not quantity.is_integer():
        raise ValueError('semivariance_position_invalid')
    if (symbol, day) in guards:
        raise ValueError('semivariance_guard_day')
    current = source.normalize(bars.loc[bars.bar_date.eq(day)], expected.loc[expected.bar_date.eq(day)], symbol)
    end = pd.Timestamp(day) + pd.Timedelta(hours=15)
    if (current.bar_datetime + pd.Timedelta(minutes=1)).gt(end).any() or current.bar_datetime.iloc[-1] + pd.Timedelta(minutes=1) != end:
        raise ValueError('semivariance_close_clock_invalid')
    actual, status = source.aggregate_day(current)
    baseline = {name: float(bar[name + '_price']) for name in ('open', 'high', 'low', 'close')}
    baseline['volume'] = float(bar['volume'])
    if (status != 'positive_volume' or not source.same_values(actual, baseline)
            or not source.same_values(actual, reference) or not source.same_values(reference, baseline)):
        raise ValueError('semivariance_daily_parity_failed')
    initial = float(current.open.iloc[0])
    if current.volume.iloc[0] <= 0 or initial != actual['open']:
        raise ValueError('semivariance_initial_observation_missing')
    segment_ids = current.bar_datetime.diff().ne(pd.Timedelta(minutes=1)).cumsum()
    samples = []
    previous = initial
    previous_source = current.bar_datetime.iloc[0]
    for segment_id, segment in current.groupby(segment_ids, sort=False):
        if len(segment) % 5 or segment.bar_datetime.iloc[0].minute % 5:
            raise ValueError('semivariance_five_minute_grid_incomplete')
        for start in range(0, len(segment), 5):
            block = segment.iloc[start:start + 5]
            trades = block.loc[block.volume.gt(0)]
            sample_end = block.bar_datetime.iloc[-1] + pd.Timedelta(minutes=1)
            if not trades.empty:
                previous = float(trades.close.iloc[-1])
                previous_source = trades.bar_datetime.iloc[-1] + pd.Timedelta(minutes=1)
            if previous_source > sample_end:
                raise ValueError('semivariance_forward_price_used')
            samples.append({'segment_id': int(segment_id), 'sample_end': sample_end.isoformat(),
                'source_end': previous_source.isoformat(), 'close': previous,
                'grid_volume': float(block.volume.sum()), 'zero_trade_grid': trades.empty})
    # Last-price sampling keeps verified no-trade intervals distinct from missing minutes.
    returns = np.diff(np.log(np.array([initial, *[v['close'] for v in samples]], dtype=float)))
    squares = returns ** 2
    directional = returns * (1 if quantity > 0 else -1)
    favorable = float(squares[directional > 0].sum())
    adverse = float(squares[directional < 0].sum())
    variance = float(squares.sum())
    if (not np.isfinite(returns).all() or not all(math.isfinite(v) and v >= 0 for v in (favorable, adverse, variance))
            or abs(favorable + adverse - variance) > 1e-12 or previous != actual['close']):
        raise ValueError('semivariance_decomposition_invalid')
    for sample, value in zip(samples, returns):
        sample['log_return'] = float(value)
    values = {FEATURES[0]: favorable, FEATURES[1]: adverse, 'realized_variance_5m': variance,
        'day_minute_count': len(current), 'sample_count': len(samples), 'segment_count': int(segment_ids.nunique()),
        'zero_trade_grid_count': sum(v['zero_trade_grid'] for v in samples),
        'first_minute': current.bar_datetime.iloc[0].isoformat(), 'last_minute': current.bar_datetime.iloc[-1].isoformat(),
        'asof_close': end.isoformat(), 'initial_open': initial, 'day_close': previous,
        'day_volume': actual['volume'], 'direction': 'long' if quantity > 0 else 'short'}
    return values, samples


def prepare_inputs():
    identity = load('stage050_holding_failure_diagnostics')
    prior = load('stage052_late_session_features')
    sources, jobs, _, paths, guards = prior.prepare_inputs()
    old_root = ROOT / 'artifacts/stage052_late_session_features'
    identity.bind(old_root / 'summary.json',
        {'sha256': '3a8ebe7ed70010886707f73de9115775af61a3ef9c537e016bb731bda35e0b20'}, sources)
    old_summary = identity.read_json(old_root / 'summary.json')
    identity.bind(old_root / 'input_manifest.json', old_summary['outputs']['input_manifest.json'], sources)
    expected = identity.read_json(old_root / 'input_manifest.json')['source_identities']
    for path, value in list(sources.items()):
        if path in expected:
            identity.bind(path, expected[path], sources)
    base = identity.read_json(prior.PANEL / 'model_spec.json')
    spec = candidate_spec(base)
    for path in [Path(__file__).resolve(), CONTRACT, ROOT / 'tests/test_stage059_realized_semivariance_features.py']:
        identity.bind(path, {}, sources)
    return sources, jobs, spec, paths, guards


def run():
    if OUTPUT.exists():
        raise RuntimeError('semivariance_output_already_exists')
    identity = load('stage050_holding_failure_diagnostics')
    network = identity.load('network', identity.NETWORK_TOOL).NetworkBlock()
    records, sample_rows = [], []
    try:
        with network:
            sources, jobs, spec, paths, guards = prepare_inputs()
            OUTPUT.mkdir(mode=0o700)
            identity.write_json(OUTPUT / 'input_manifest.json', {'source_identities': sources,
                'features': list(FEATURES), 'sampling_minutes': 5, 'window': 'entire_producer_trading_day',
                'label_access': False, 'scope': 'all_1002_frozen_A_observations_not_universal_C_coverage'})
            by_contract = {}
            for job in jobs:
                by_contract.setdefault(job['vt_symbol'], []).append(job)
            for number, (symbol, views) in enumerate(paths.items(), 1):
                bars = pd.read_csv(views['minutes'], dtype=str)
                expected = pd.read_csv(views['expected_minutes'], dtype=str)
                reference = pd.read_csv(views['daily_reference'], dtype=str)
                if reference.bar_date.duplicated().any():
                    raise RuntimeError('semivariance_reference_duplicate')
                references = reference.set_index('bar_date').to_dict('index')
                bars_by_day = {day: values for day, values in bars.groupby('bar_date', sort=False)}
                clocks_by_day = {day: values for day, values in expected.groupby('bar_date', sort=False)}
                for job in by_contract[symbol]:
                    record = {key: job[key] for key in IDS}
                    try:
                        day = job['date']
                        if day not in bars_by_day or day not in clocks_by_day or day not in references:
                            raise ValueError('semivariance_required_day_missing')
                        values, samples = features_for_day(bars_by_day[day], clocks_by_day[day], job, references[day], guards)
                        record.update(status='qualified', error='', **values)
                        sample_rows.extend({**{key: job[key] for key in IDS}, **value} for value in samples)
                    except (ValueError, RuntimeError) as exc:
                        record.update(status='failed', error=str(exc), **{key: None for key in FEATURES})
                    records.append(record)
                if number % 20 == 0 or number == len(paths):
                    print(json.dumps({'contracts_checked': number, 'planned': len(paths), 'observations_checked': len(records)}), flush=True)
            frame = pd.DataFrame(records).set_index('observation_id').loc[[v['observation_id'] for v in jobs]].reset_index()
            qualified = frame.status.eq('qualified')
            unique = {key: int(frame.loc[qualified, key].nunique()) for key in FEATURES}
            passed = bool(qualified.all() and all(value > 1 for value in unique.values()))
            outputs = {'observation_semivariance_features.csv': frame, 'sampled_prices.csv': pd.DataFrame(sample_rows)}
            for name, data in outputs.items():
                with (OUTPUT / name).open('x') as stream:
                    data.to_csv(stream, index=False, float_format='%.17g')
            identity.write_json(OUTPUT / 'candidate_spec.json', spec)
            for path, expected_identity in list(sources.items()):
                identity.bind(path, expected_identity, sources)
            if network.attempts or any(name.split('.')[0] in ('xgboost', 'vnpy_ctp') for name in sys.modules):
                raise RuntimeError('semivariance_native_or_network_used')
            summary = {'stage': 'stage059_realized_semivariance_features',
                'status': 'features_qualified_no_models' if passed else 'feature_qualification_failed_no_models',
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'all_observations_qualified': passed,
                'observation_count': len(frame), 'contract_count': len(paths), 'root_count': int(frame.root_id.nunique()),
                'qualified_count': int(qualified.sum()), 'failed_count': int((~qualified).sum()),
                'failure_counts': frame.loc[~qualified, 'error'].value_counts().to_dict(),
                'feature_unique_counts': unique, 'feature_count': len(spec['features']), 'sample_count': len(sample_rows),
                'zero_trade_grid_count': sum(v['zero_trade_grid'] for v in sample_rows),
                'source_count': len(sources), 'source_global_coverage_complete': False, 'source_scope': 'A_observations_only',
                'network_attempt_count': network.attempts, 'new_download_count': 0, 'new_label_count': 0,
                'historical_fit_predict_count': 0, 'new_strategy_replay_count': 0, 'reviewer_started': False,
                'outputs': {name: identity.file_identity(OUTPUT / name) for name in
                    ['input_manifest.json', *outputs, 'candidate_spec.json']}}
            identity.write_json(OUTPUT / 'summary.json', summary)
            print(json.dumps(summary, allow_nan=False), flush=True)
            return summary
    except BaseException as exc:
        if OUTPUT.exists():
            identity.write_json(OUTPUT / 'failure.json', {'status': 'execution_failed', 'completed': len(records),
                'error': str(exc), 'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__':
    run()
