from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import math
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/stage040_holding_panel'
CONTRACT = ROOT / 'stages/20260906_1102_stage040_holding_utility_contract.md'
SOURCE = ROOT / 'artifacts/stage033_holding_observer/workers/A'
COST = ROOT / 'artifacts/stage034_fill_inventory'
FEATURES = ('directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
            'directional_close_location', 'log_holding_bars', 'layer_stop_buffer',
            'portfolio_drawdown', 'margin_to_equity', 'loss_streak')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('panel040_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('holding_feature_nonfinite')
    return value


def visible_features(row, inventory, equity_peak):
    observer, cost = load('stage033_holding_observer'), load('stage034_fill_inventory')
    if (row['phase'] != 'after_strategy_on_bars' or observer.classify(row) != row['state_status']
            or cost.cost_state(row, inventory) != 'inventory_reconciled_holding'):
        raise ValueError('holding_features_unqualified')
    symbol, quantity = next(iter(row['actual_positions'].items()))
    bar = row['bar']; sign = 1 if quantity > 0 else -1
    if bar['vt_symbol'] != symbol or bar['datetime'][:10] != row['date']:
        raise ValueError('holding_feature_bar_time')
    o, h, low, c = [finite(bar[name + '_price']) for name in ('open', 'high', 'low', 'close')]
    average = finite(inventory[symbol]['average_entry_price'])
    equity, peak, margin = finite(row['estimated_equity']), finite(equity_peak), finite(row['total_margin_in_use'])
    age, streak = finite(row['bars_since_entry']), finite(row['loss_streak'])
    stops = [finite(layer['stop_price']) for layer in row['layers']]
    if (min(o, h, low, c, average, equity, *stops) <= 0 or not low <= min(o, c) <= max(o, c) <= h
            or peak < equity or margin < 0 or min(age, streak) < 0 or not age.is_integer() or not streak.is_integer()):
        raise ValueError('holding_feature_domain')
    values = (sign * (c / average - 1), sign * (c / o - 1), (h - low) / c,
              sign * (2 * c - h - low) / (h - low) if h > low else 0., math.log1p(age),
              min(sign * (c - stop) / c for stop in stops), equity / peak - 1, margin / equity, streak)
    return dict(zip(FEATURES, map(finite, values)))


def training_selection(jobs, cutoff):
    if datetime.strptime(cutoff, '%Y-%m-%d').day != 1:
        raise ValueError('holding_cutoff_not_month_start')
    seen, roots, selected = set(), {}, []
    for job in jobs:
        identifier, root = job['observation_id'], job['root_id']
        identity = (job['status'], job['end_date'])
        if identifier in seen or (root in roots and roots[root] != identity):
            raise ValueError('holding_training_identity')
        seen.add(identifier); roots[root] = identity
        if job['status'] == 'mature':
            if not job['end_date'] or job['end_date'] <= job['date']:
                raise ValueError('holding_label_endpoint')
            if job['date'] < cutoff and job['end_date'] < cutoff:
                selected.append(job)
        elif job['status'] != 'right_censored_open' or job['end_date']:
            raise ValueError('holding_training_status')
    counts = Counter(job['root_id'] for job in selected)
    return [(job['observation_id'], 1. / counts[job['root_id']]) for job in selected]


def holding_utility(a_rows, e_rows, start, end, equity):
    equity = finite(equity)
    if equity <= 0 or end <= start:
        raise ValueError('holding_utility_endpoint')
    curves, dates = [], None
    for rows in (a_rows, e_rows):
        selected = [row for row in rows if start <= str(row['date'])[:10] <= end]
        keys = [str(row['date'])[:10] for row in selected]
        if (not keys or keys != sorted(set(keys)) or keys[0] != start or keys[-1] != end
                or (dates is not None and keys != dates)):
            raise ValueError('holding_utility_calendar')
        dates = keys
        values = [finite(row['account_equity']) for row in selected]
        if min(values) <= 0 or abs(values[0] - equity) > 1e-7:
            raise ValueError('holding_utility_anchor')
        peak, drawdown = equity, 0.
        for value in values:
            peak = max(peak, value); drawdown = min(drawdown, value / peak - 1)
        curves.append((values[-1], drawdown))
    a, e = curves
    return {'return_marginal': (a[0] - e[0]) / equity, 'drawdown_marginal': a[1] - e[1],
            'A_end_equity': a[0], 'E_end_equity': e[0], 'A_max_drawdown': a[1], 'E_max_drawdown': e[1],
            'observation_equity': equity, 'start_date': start, 'end_date': end}


def read_csv(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as stream:
        return list(csv.DictReader(stream))


def build_panel(rows, costs, roots, daily):
    import pandas as pd

    if len(rows) != len(costs):
        raise ValueError('holding_panel_cost_inventory')
    linked, _ = load('stage033b_holding_population').group_roots(rows, pd.DataFrame(roots))
    links = {(row.date, row.product_vt_symbol): row.event_id for row in linked.itertuples()}
    root_map = {row['event_id']: row for row in roots}
    daily_equity = {row['date']: finite(row['account_equity']) for row in daily}
    jobs, features, peak, seen, last = [], [], 150000., set(), None
    for row, cost in zip(rows, costs):
        key = row['date'], row['product_vt_symbol']
        if key in seen or (last is not None and key <= last) or key != (cost['date'], cost['product_vt_symbol']):
            raise ValueError('holding_panel_order')
        last = key; seen.add(key)
        if daily_equity[row['date']] <= 0:
            raise ValueError('holding_ledger_equity_nonpositive')
        peak = max(peak, finite(row['estimated_equity']))
        if cost['inventory_state_status'] != 'inventory_reconciled_holding':
            continue
        book = {symbol: {name: item[name] for name in ('quantity', 'average_entry_price', 'source_trade_ids')}
                for symbol, item in cost['contract_costs'].items()}
        values = visible_features(row, book, peak)
        root_id = links[key]; root = root_map[root_id]
        symbol, quantity = next(iter(row['actual_positions'].items()))
        if (quantity > 0) != (root['direction'] == 'long'):
            raise ValueError('holding_panel_root_direction')
        payload = [root_id, *key, symbol]
        identifier = hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()
        identity = {'observation_id': identifier, 'date': row['date'], 'product_vt_symbol': key[1], 'vt_symbol': symbol}
        features.append({**identity, **values})
        jobs.append({**identity, 'root_id': root_id, 'status': root['status'], 'end_date': root['end_date'],
                     'direction': root['direction'], 'equity_peak': peak, 'account_equity': daily_equity[row['date']],
                     'snapshot': row, 'inventory': book,
                     'features': values})
    return features, jobs


def source_paths():
    control = load('stage039_exit_controls')
    return [Path(__file__).resolve(), ROOT / 'tests/test_stage040_holding_panel.py', CONTRACT,
        ROOT / 'stages/stage004_model_spec.json', ROOT / 'stages/20260906_1116_stage040_accounting_clarification.md',
        SOURCE / 'holding_states.json.gz', SOURCE / 'daily.csv.gz', SOURCE / 'archive_receipt.json',
        SOURCE / 'observer_receipt.json', COST / 'holding_cost_states.json.gz', COST / 'root_population.csv',
        COST / 'summary.json', control.FREEZE, control.OUTPUT / 'input_manifest.json', control.OUTPUT / 'summary.json']


def verify_sources():
    control = load('stage039_exit_controls'); _, runner = control.configured()
    manifest = json.loads((control.OUTPUT / 'input_manifest.json').read_text())
    runner.validate_frozen_input_contract(control.FREEZE, manifest)
    runner.validate_current_input_manifest(manifest)
    summary = json.loads((control.OUTPUT / 'summary.json').read_text())
    if summary['status'] != 'engineering_controls_passed_not_model':
        raise ValueError('holding_controls_not_passed')
    batch = load('stage004_label_batch')
    for arm, item in summary['results'].items():
        root = control.OUTPUT / 'workers' / arm
        if (batch.digest(root / 'receipt.json') != item['receipt_sha256']
                or runner._file_identity(root / 'exit_audit.json') != item['exit_audit_identity']):
            raise ValueError('holding_control_receipt_changed')
    collector = load('stage005_label_collection')
    archives = json.loads((SOURCE / 'archive_receipt.json').read_text())
    collector.verify_archive(SOURCE / 'daily.csv.gz', archives['daily'])
    receipt = json.loads((SOURCE / 'observer_receipt.json').read_text())
    collector.verify_identity(SOURCE / 'holding_states.json.gz', receipt['trace_identity'])
    if hashlib.sha256(gzip.decompress((SOURCE / 'holding_states.json.gz').read_bytes())).hexdigest() != receipt['raw_sha256']:
        raise ValueError('holding_trace_raw_changed')
    for item in json.loads((COST / 'summary.json').read_text())['outputs'].values():
        identity = item.get('compressed', item)
        collector.verify_identity(identity['path'], identity)
        if 'compressed' in item:
            if hashlib.sha256(gzip.decompress(Path(identity['path']).read_bytes())).hexdigest() != item['raw_sha256']:
                raise ValueError('holding_cost_raw_changed')
    return runner


def main():
    if OUTPUT.exists():
        raise ValueError('holding_panel_exists')
    runner = verify_sources(); batch = load('stage004_label_batch')
    identities = {str(path): runner._file_identity(path) for path in source_paths()}
    rows = json.loads(gzip.decompress((SOURCE / 'holding_states.json.gz').read_bytes()))
    costs = json.loads(gzip.decompress((COST / 'holding_cost_states.json.gz').read_bytes()))
    roots, daily = read_csv(COST / 'root_population.csv'), read_csv(SOURCE / 'daily.csv.gz')
    features, jobs = build_panel(rows, costs, roots, daily)
    cutoffs = sorted({row['date'][:7] + '-01' for row in daily})
    by_id = {job['observation_id']: job for job in jobs}
    months = []
    for cutoff in cutoffs:
        selected = training_selection(jobs, cutoff)
        root_count = len({by_id[key]['root_id'] for key, _ in selected})
        months.append({'cutoff': cutoff, 'mature_roots': root_count, 'observation_count': len(selected),
                       'minimum_roots_met': root_count >= 60, 'weights': selected})
    if len(jobs) != 1002 or len({job['root_id'] for job in jobs if job['status'] == 'mature'}) != 155:
        raise ValueError('holding_panel_population_changed')
    canary, seen = [], set()
    for job in jobs:
        if job['status'] == 'mature' and job['root_id'] not in seen:
            seen.add(job['root_id']); canary.append(job['observation_id'])
            if len(canary) == 2:
                break
    short = next(job for job in jobs if job['status'] == 'mature' and job['direction'] == 'short')
    canary = list(dict.fromkeys([*canary, short['observation_id']]))
    old = json.loads((ROOT / 'stages/stage004_model_spec.json').read_text())
    model = {'features': FEATURES, 'estimator': old['estimator'], 'versions': old['versions'],
        'minimum_mature_roots': 60, 'weight': 'one_unit_per_mature_root',
        'target_transform': 'training_fold_weighted_mean_population_std', 'constant_target': 'training_weighted_mean',
        'schedule': 'strict_month_before_mature_expanding', 'action': 'exit_only_both_inverse_predictions_negative',
        'targets': ['return_marginal', 'drawdown_marginal'], 'evidence': 'development_walk_forward_not_untouched_holdout'}
    for path, identity in identities.items():
        if runner._file_identity(Path(path)) != identity:
            raise ValueError('holding_panel_source_drift')
    OUTPUT.mkdir(mode=0o700)
    with (OUTPUT / 'features.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(features[0])); writer.writeheader(); writer.writerows(features)
    batch.write_json(OUTPUT / 'jobs.json', {'jobs': jobs, 'canary_ids': canary, 'roots': roots})
    batch.write_json(OUTPUT / 'monthly_inventory.json', months)
    batch.write_json(OUTPUT / 'model_spec.json', model)
    result = {'stage': 'stage040_holding_panel', 'status': 'panel_ready_not_labels_or_model',
        'observations': len(jobs), 'root_inventory': len(roots), 'mature_observed_roots': 155,
        'censored_observations': sum(job['status'] != 'mature' for job in jobs), 'feature_count': len(FEATURES),
        'first_eligible_month': next(row['cutoff'] for row in months if row['minimum_roots_met']),
        'canary_ids': canary, 'source_identities': identities,
        'outputs': {name: runner._file_identity(OUTPUT / name) for name in
                    ('features.csv', 'jobs.json', 'monthly_inventory.json', 'model_spec.json')},
        'label_count': 0, 'new_replay_count': 0, 'historical_fit_predict_count': 0, 'reviewer_count': 0}
    batch.write_json(OUTPUT / 'summary.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in {'source_identities', 'outputs'}}), flush=True)


if __name__ == '__main__':
    main()
