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
OUTPUT = ROOT / 'artifacts/stage052_late_session_features'
PANEL = ROOT / 'artifacts/stage040_holding_panel'
PANEL_SHA = 'c96b103e20da072584606f786baf7bd05973492f4abd0df8d79b67fa4a3aa94c'
CONTRACT = ROOT / 'stages/20260907_0718_stage051_late_session_information_contract.md'
BASE_FEATURES = ('directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
    'directional_close_location', 'log_holding_bars', 'layer_stop_buffer', 'portfolio_drawdown',
    'margin_to_equity', 'loss_streak')
FEATURES = ('directional_late_return_30m', 'late_volume_fraction_30m')
IDS = ('observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('late052_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def features_for_day(bars, expected, job, reference, guards):
    source = load('stage036_full_minute_source')
    day, symbol = job['date'], job['vt_symbol']
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('late_session_date_invalid')
    snapshot = job['snapshot']; positions = snapshot['actual_positions']; bar = snapshot['bar']
    if (snapshot['phase'] != 'after_strategy_on_bars' or set(positions) != {symbol}
            or bar['vt_symbol'] != symbol or bar['datetime'][:10] != day):
        raise ValueError('late_session_current_state_invalid')
    quantity = float(positions[symbol])
    if not math.isfinite(quantity) or quantity == 0 or not quantity.is_integer():
        raise ValueError('late_session_position_invalid')
    if (symbol, day) in guards:
        raise ValueError('late_session_guard_day')
    # Slice by the producer's trading day before examining values; future days are not inputs.
    current = bars.loc[bars.bar_date.eq(day)].copy()
    clock = expected.loc[expected.bar_date.eq(day)].copy()
    current = source.normalize(current, clock, symbol)
    end = pd.Timestamp(day) + pd.Timedelta(hours=15)
    if (current.bar_datetime + pd.Timedelta(minutes=1)).gt(end).any():
        raise ValueError('late_session_future_minute')
    actual, status = source.aggregate_day(current)
    baseline = {name: float(bar[name + '_price']) for name in ('open', 'high', 'low', 'close')}
    baseline['volume'] = float(bar['volume'])
    if (status != 'positive_volume' or not source.same_values(actual, baseline)
            or not source.same_values(actual, reference) or not source.same_values(reference, baseline)):
        raise ValueError('late_session_daily_parity_failed')
    start = end - pd.Timedelta(minutes=30)
    late = current.loc[current.bar_datetime.ge(start) & current.bar_datetime.lt(end)]
    required = list(pd.date_range(start, end, freq='min', inclusive='left'))
    if late.bar_datetime.tolist() != required:
        raise ValueError('late_session_clock_incomplete')
    late_volume = float(late.volume.sum())
    if late_volume <= 0 or abs(float(late.close.iloc[-1]) - baseline['close']) > 1e-7:
        raise ValueError('late_session_no_trade_or_close_mismatch')
    values = {FEATURES[0]: (1 if quantity > 0 else -1) * (float(late.close.iloc[-1]) / float(late.open.iloc[0]) - 1.),
        FEATURES[1]: late_volume / actual['volume']}
    if not all(math.isfinite(v) for v in values.values()) or not 0 < values[FEATURES[1]] <= 1:
        raise ValueError('late_session_feature_domain')
    return {**values, 'day_minute_count': len(current), 'late_minute_count': len(late),
        'first_minute': current.bar_datetime.iloc[0].isoformat(), 'last_minute': late.bar_datetime.iloc[-1].isoformat(),
        'asof_close': end.isoformat(), 'late_open': float(late.open.iloc[0]), 'late_close': float(late.close.iloc[-1]),
        'late_volume': late_volume, 'day_volume': actual['volume'], 'direction': 'long' if quantity > 0 else 'short'}


def candidate_spec(base):
    if base['features'] != list(BASE_FEATURES):
        raise RuntimeError('late_session_base_features_changed')
    result = copy.deepcopy(base)
    result['features'] = [*BASE_FEATURES, *FEATURES]
    return result


def prepare_inputs():
    identity = load('stage050_holding_failure_diagnostics')
    source = load('stage036_full_minute_source')
    sources = {}
    identity.bind(PANEL / 'summary.json', {'sha256': PANEL_SHA}, sources)
    summary = identity.read_json(PANEL / 'summary.json')
    if summary['observations'] != 1002 or summary['feature_count'] != 9 or summary['mature_observed_roots'] != 155:
        raise RuntimeError('late_session_panel_inventory_changed')
    for name, expected in summary['outputs'].items():
        identity.bind(PANEL / name, expected, sources)
    plan = identity.read_json(PANEL / 'jobs.json'); jobs = plan['jobs']
    if (len(jobs) != 1002 or len({v['observation_id'] for v in jobs}) != 1002
            or len({(v['date'], v['vt_symbol']) for v in jobs}) != 1002
            or len({v['root_id'] for v in jobs}) != 155 or len(plan['roots']) != 276):
        raise RuntimeError('late_session_job_inventory_changed')
    base = identity.read_json(PANEL / 'model_spec.json'); spec = candidate_spec(base)
    manifest_path = source.CACHE / 'manifest.json'
    identity.bind(manifest_path, {'sha256': source.SOURCE_MANIFEST_SHA}, sources)
    manifest = identity.read_json(manifest_path)
    entries = source.unique_entries(manifest)
    symbols = sorted({v['vt_symbol'] for v in jobs})
    if len(symbols) != 120 or not set(symbols).issubset(entries):
        raise RuntimeError('late_session_source_inventory')
    for key in ('calendar', 'collection_plan', 'nontradable_guard_days', 'quality_blockers'):
        identity.bind(source.safe_path(source.CACHE, manifest[key + '_path']),
            {'sha256': manifest[key + '_sha256']}, sources)
    guards = {(v['vt_symbol'], v['bar_date']) for v in manifest['nontradable_guard_days']}
    paths = {}
    for symbol in symbols:
        entry = entries[symbol]
        if entry['status'] != 'complete':
            raise RuntimeError('late_session_contract_incomplete')
        paths[symbol] = {}
        for key in ('minutes', 'expected_minutes', 'daily_reference', 'sessions'):
            path_key, sha_key = ('path', 'sha256') if key == 'minutes' else (key + '_path', key + '_sha256')
            path = source.safe_path(source.CACHE, entry[path_key])
            identity.bind(path, {'sha256': entry[sha_key]}, sources)
            paths[symbol][key] = path
    for path in [Path(__file__).resolve(), CONTRACT, ROOT / 'tests/test_stage052_late_session_features.py',
            identity.NETWORK_TOOL, *[ROOT / 'tools' / (name + '.py') for name in (
                'stage050_holding_failure_diagnostics', 'stage005_label_collection',
                'stage036_full_minute_source', 'stage035_next_window')]]:
        identity.bind(path, {}, sources)
    return sources, jobs, spec, paths, guards


def run():
    if OUTPUT.exists():
        raise RuntimeError('late_session_output_already_exists')
    identity = load('stage050_holding_failure_diagnostics')
    network = identity.load('network', identity.NETWORK_TOOL).NetworkBlock()
    records = []
    try:
        with network:
            sources, jobs, spec, paths, guards = prepare_inputs()
            OUTPUT.mkdir(mode=0o700)
            identity.write_json(OUTPUT / 'input_manifest.json', {'source_identities': sources,
                'features': list(FEATURES), 'formula_window_minutes': 30, 'label_access': False,
                'scope': 'all_1002_frozen_A_observations_not_universal_C_coverage'})
            by_contract = {}
            for job in jobs:
                by_contract.setdefault(job['vt_symbol'], []).append(job)
            for number, (symbol, views) in enumerate(paths.items(), 1):
                bars = pd.read_csv(views['minutes'], float_precision='round_trip')
                expected = pd.read_csv(views['expected_minutes'])
                reference = pd.read_csv(views['daily_reference'], float_precision='round_trip')
                if reference.bar_date.duplicated().any():
                    raise RuntimeError('late_session_reference_duplicate')
                references = reference.set_index('bar_date').to_dict('index')
                bars_by_day = {day: values for day, values in bars.groupby('bar_date', sort=False)}
                clocks_by_day = {day: values for day, values in expected.groupby('bar_date', sort=False)}
                for job in by_contract[symbol]:
                    record = {key: job[key] for key in IDS}
                    try:
                        day = job['date']
                        if day not in bars_by_day or day not in clocks_by_day or day not in references:
                            raise ValueError('late_session_required_day_missing')
                        values = features_for_day(bars_by_day[day], clocks_by_day[day], job, references[day], guards)
                        record.update(status='qualified', error='', **values)
                    except (ValueError, RuntimeError) as exc:
                        record.update(status='failed', error=str(exc), **{k: None for k in FEATURES})
                    records.append(record)
                if number % 20 == 0 or number == len(paths):
                    print(json.dumps({'contracts_checked': number, 'planned': len(paths), 'observations_checked': len(records)}), flush=True)
            frame = pd.DataFrame(records).set_index('observation_id').loc[[v['observation_id'] for v in jobs]].reset_index()
            qualified = frame.status.eq('qualified')
            unique = {key: int(frame.loc[qualified, key].nunique()) for key in FEATURES}
            passed = bool(qualified.all() and all(value > 1 for value in unique.values()))
            with (OUTPUT / 'observation_late_features.csv').open('x') as stream:
                frame.to_csv(stream, index=False, float_format='%.17g')
            identity.write_json(OUTPUT / 'candidate_spec.json', spec)
            for path, expected in list(sources.items()):
                identity.bind(path, expected, sources)
            if network.attempts or any(name.split('.')[0] in ('xgboost', 'vnpy_ctp') for name in sys.modules):
                raise RuntimeError('late_session_native_or_network_used')
            summary = {'stage': 'stage052_late_session_features',
                'status': 'features_qualified_no_models' if passed else 'feature_qualification_failed_no_models',
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'all_observations_qualified': passed,
                'observation_count': len(frame), 'contract_count': len(paths), 'root_count': frame.root_id.nunique(),
                'qualified_count': int(qualified.sum()), 'failed_count': int((~qualified).sum()),
                'failure_counts': frame.loc[~qualified, 'error'].value_counts().to_dict(),
                'feature_unique_counts': unique, 'feature_count': len(spec['features']),
                'source_count': len(sources), 'source_global_coverage_complete': False,
                'source_scope': 'A_observations_only', 'network_attempt_count': network.attempts,
                'new_download_count': 0, 'new_label_count': 0, 'historical_fit_predict_count': 0,
                'new_strategy_replay_count': 0, 'reviewer_started': False,
                'outputs': {name: identity.file_identity(OUTPUT / name) for name in (
                    'input_manifest.json', 'observation_late_features.csv', 'candidate_spec.json')}}
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
