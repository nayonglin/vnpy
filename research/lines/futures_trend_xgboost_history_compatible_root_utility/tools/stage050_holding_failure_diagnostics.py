from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/stage050_holding_failure_diagnostics'
CONTRACT = ROOT / 'stages/20260907_0653_stage050_holding_failure_contract.md'
SNAPSHOT = ROOT / 'artifacts/stage043_label_collection/20260907_051249_482153'
TRAINING = ROOT / 'artifacts/stage044_holding_training'
C_ROOT = ROOT / 'artifacts/stage049b_holding_full_replay'
A_ROOT = ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage004_counterfactual_validation/workers/A'
NETWORK_TOOL = ROOT.parent / 'futures_trend_xgboost_formal_signal_marginal_utility_v2/tools/stage001_import_preflight.py'
TARGETS = ['return_marginal', 'drawdown_marginal']
KEYS = ['observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol']
FEATURES = ['directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
    'directional_close_location', 'log_holding_bars', 'layer_stop_buffer',
    'portfolio_drawdown', 'margin_to_equity', 'loss_streak']
PINS = {
    SNAPSHOT / 'summary.json': 'c4d00014ce724bb20645dfcb79eec6d2728ebbff70a2143d65f2cd0b89a3aacd',
    TRAINING / 'summary.json': '69e4e9bd8dab96be26288ea51a76fca5cc834c773a92b0408dbf957b63b71a5a',
    C_ROOT / 'summary.json': '322e986176dad1165e423112e595ab5818cb7c71795f18bc42c94893ed09d532',
    ROOT / 'stages/stage049b_input_freeze.json': '3152fe4138ce34d6e523ade9c6cf69022e3edddbb6fea13d30036584a88742b1',
}
TOL = 1e-6


@lru_cache(None)
def load(name, path=None):
    spec = importlib.util.spec_from_file_location('holding_failure_' + name,
        path or ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def file_identity(path):
    path = Path(path).resolve(strict=True)
    stat = path.stat()
    return {'path': str(path), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
        'sha256': load('stage005_label_collection').digest(path)}


def bind(path, expected, sources):
    actual = file_identity(path)
    if any(actual[key] != value for key, value in expected.items() if key in actual):
        raise RuntimeError(f'holding_diagnostic_source_changed:{path}')
    previous = sources.get(actual['path'])
    if previous is not None and previous != actual:
        raise RuntimeError(f'holding_diagnostic_source_drift:{path}')
    sources[actual['path']] = actual


def validate_training(data, metadata, spec):
    models = load('stage044_holding_models')
    for cutoff, bundle in metadata.items():
        models.validate_metadata(bundle, spec)
        train = models.training_rows(data, cutoff, spec)
        columns = ['observation_id', 'root_id', 'date', 'label_end_date', *spec['features'],
            *spec['targets'], 'sample_weight']
        signature = hashlib.sha256(train[columns].to_csv(index=False, float_format='%.17g').encode()).hexdigest()
        if (bundle['cutoff'] != cutoff or bundle['train_frame_sha256'] != signature
                or bundle['train_observation_ids'] != train.observation_id.tolist()
                or bundle['train_root_ids'] != train.root_id.tolist()
                or bundle['train_weights'] != train.sample_weight.tolist()):
            raise RuntimeError('holding_diagnostic_training_rows_changed')
        for target, head in bundle['heads'].items():
            values = train[target].to_numpy(dtype=float)
            weights = train.sample_weight.to_numpy(dtype=float)
            constant = bool(np.all(values == values[0]))
            mean = float(values[0] if constant else np.average(values, weights=weights))
            std = 0. if constant else float(np.sqrt(np.average((values - mean) ** 2, weights=weights)))
            if head['mean'] != mean or head['std'] != std:
                raise RuntimeError('holding_diagnostic_training_transform_changed')
    return len(metadata)


def join_predictions(data, predictions, metadata):
    if (data.empty or data.observation_id.duplicated().any() or predictions.observation_id.duplicated().any()
            or set(data.observation_id) != set(predictions.observation_id)
            or data.duplicated(['root_id', 'date']).any() or not data.label_status.eq('verified').all()
            or not np.isfinite(data[TARGETS + FEATURES].to_numpy(dtype=float)).all()):
        raise RuntimeError('holding_diagnostic_inventory_invalid')
    p = predictions.set_index('observation_id').loc[data.observation_id].reset_index()
    data = data.reset_index(drop=True)
    if not data[KEYS].equals(p[KEYS]):
        raise RuntimeError('holding_diagnostic_prediction_identity')
    if (not p.cutoff.eq(data.date.str[:7] + '-01').all()
            or not set(p.cutoff).issubset(metadata)
            or not p.status.isin(['untrained', 'predicted']).all()
            or not p['exit'].map(lambda v: isinstance(v, (bool, np.bool_))).all()):
        raise RuntimeError('holding_diagnostic_prediction_status')
    trained = p.status.eq('predicted')
    if (not np.isfinite(p.loc[trained, TARGETS].to_numpy(dtype=float)).all()
            or not p.loc[~trained, TARGETS].isna().all().all()
            or p.loc[~trained, 'exit'].any()
            or not p.loc[trained, 'exit'].eq(p.loc[trained, TARGETS].lt(0).all(axis=1)).all()):
        raise RuntimeError('holding_diagnostic_prediction_action')
    result = data.copy()
    result[['cutoff', 'status', 'exit']] = p[['cutoff', 'status', 'exit']]
    result['evaluable'] = trained
    for target in TARGETS:
        result['pred_' + target] = p[target]
        result['baseline_' + target] = np.nan
    for cutoff, indices in result.groupby('cutoff').groups.items():
        month = metadata[cutoff]
        if not result.loc[indices, 'status'].eq('predicted' if month['status'] == 'trained' else 'untrained').all():
            raise RuntimeError('holding_diagnostic_metadata_status')
        if month['status'] == 'trained':
            for target in TARGETS:
                result.loc[indices, 'baseline_' + target] = month['heads'][target]['mean']
    return result


def root_weights(roots):
    return 1. / roots.map(roots.value_counts()).to_numpy(dtype=float)


def regression_metrics(actual, predicted, baseline, weights):
    arrays = [np.asarray(v, dtype=float) for v in (actual, predicted, baseline, weights)]
    if (any(v.ndim != 1 or not np.isfinite(v).all() for v in arrays)
            or len({len(v) for v in arrays}) != 1 or np.any(arrays[3] <= 0)):
        raise RuntimeError('holding_diagnostic_regression_invalid')
    y, p, b, w = arrays
    if not len(y):
        return {'count': 0, **{k: None for k in ('mse', 'mae', 'baseline_mse', 'baseline_mae', 'mse_skill', 'bias')}}
    mse, base_mse = (float(np.average((v - y) ** 2, weights=w)) for v in (p, b))
    return {'count': len(y), 'mse': mse, 'mae': float(np.average(np.abs(p - y), weights=w)),
        'baseline_mse': base_mse, 'baseline_mae': float(np.average(np.abs(b - y), weights=w)),
        'mse_skill': 1. - mse / base_mse if base_mse > 0 else None,
        'bias': float(np.average(p - y, weights=w))}


def action_metrics(frame):
    rows = frame.loc[frame.evaluable]
    action = rows['exit']; truth = rows[TARGETS].lt(0).all(axis=1)
    tp, fp = int((action & truth).sum()), int((action & ~truth).sum())
    fn, tn = int((~action & truth).sum()), int((~action & ~truth).sum())
    return {'count': len(rows), 'roots': rows.root_id.nunique(), 'exits': int(action.sum()),
        'true_exits': int(truth.sum()), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'precision': tp / (tp + fp) if tp + fp else None, 'recall': tp / (tp + fn) if tp + fn else None,
        'exit_return_positive': int((action & rows.return_marginal.gt(0)).sum()),
        'exit_drawdown_positive': int((action & rows.drawdown_marginal.gt(0)).sum()),
        'exit_both_positive': int((action & rows[TARGETS].gt(0).all(axis=1)).sum()),
        'exit_any_zero': int((action & rows[TARGETS].eq(0).any(axis=1)).sum())}


def first_exits(frame):
    return frame.loc[frame.evaluable & frame['exit']].sort_values(['date', 'observation_id']).drop_duplicates('root_id')


def crosswalk(a, c):
    keys = ['date', 'product_vt_symbol', 'vt_symbol']
    columns = keys + FEATURES + ['exit']
    if a.duplicated(keys).any() or c.duplicated(keys).any():
        raise RuntimeError('holding_diagnostic_path_duplicate')
    pairs = a[columns].merge(c[columns], on=keys, how='outer', validate='one_to_one',
        suffixes=('_A', '_C'), indicator=True)
    common = pairs['_merge'].eq('both')
    changes = {}
    for name in [*FEATURES, 'exit']:
        pairs['changed_' + name] = common & pairs[name + '_A'].ne(pairs[name + '_C'])
        changes[name] = int(pairs['changed_' + name].sum())
    return pairs, {'common': int(common.sum()), 'A_only': int(pairs['_merge'].eq('left_only').sum()),
        'C_only': int(pairs['_merge'].eq('right_only').sum()), 'action_changed': changes.pop('exit'),
        'feature_changed': changes, 'all_features_equal': int((common & ~pairs[['changed_' + f for f in FEATURES]].any(axis=1)).sum()),
        'C_label_transfer_count': 0}


def holding_decomposition(am, em, a, e, product, decision, end, equity, label):
    if decision not in am.index or decision not in em.index:
        raise RuntimeError('holding_diagnostic_anchor_missing')
    prefix = em.index <= decision
    if (abs(float(a.set_index('date').loc[decision, 'account_equity']) - equity) > TOL
            or abs(float(e.set_index('date').loc[decision, 'account_equity']) - equity) > TOL
            or np.max(np.abs((am.loc[em.index] - em).loc[prefix].to_numpy())) > TOL):
        raise RuntimeError('holding_diagnostic_observation_prefix_or_anchor_changed')
    return load('stage017_label_path_decomposition').decompose(am, em, a, e, product, decision, end, equity, label)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)


def label_folder(stage, identifier):
    if (stage not in ('stage041b_holding_labels', 'stage042_holding_labels')
            or not identifier or not identifier.isalnum()):
        raise RuntimeError('holding_diagnostic_label_owner')
    return ROOT / 'artifacts' / stage / 'jobs' / identifier


def prepare_inputs():
    sources = {}
    for path, sha in PINS.items():
        bind(path, {'sha256': sha}, sources)
    snapshot, training, candidate = (read_json(p / 'summary.json') for p in (SNAPSHOT, TRAINING, C_ROOT))
    if (snapshot['verified'] != 1002 or not snapshot['training_ready'] or training['status'] != 'passed'
            or candidate['status'] != 'passed' or candidate['comparison']['primary_gate_passed']):
        raise RuntimeError('holding_diagnostic_frozen_campaign_status')
    # The completed summary pins the receipt; the frozen contract pins its ancestry.
    manifest_path = C_ROOT / 'input_manifest.json'
    manifest = read_json(manifest_path); freeze = read_json(ROOT / 'stages/stage049b_input_freeze.json')
    contract = {key: {k: value[k] for k in ('path', 'size', 'mtime_ns', 'sha256')}
        for key, value in sorted(manifest['files'].items())}
    sha = hashlib.sha256(json.dumps(contract, ensure_ascii=True, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if sha != freeze['file_contract_sha256'] or sha != candidate['file_contract_sha256']:
        raise RuntimeError('holding_diagnostic_C_contract_changed')
    bind(manifest_path, {}, sources)
    expected = {v['path']: v for v in manifest['files'].values()}
    for path, identity in snapshot['source_identities'].items():
        bind(path, identity, sources)
    for name, identity in snapshot['outputs'].items():
        bind(SNAPSHOT / name, identity, sources)
    for name, identity in training['output_identities'].items():
        bind(TRAINING / name, identity, sources)
    train_manifest = read_json(TRAINING / 'input_manifest.json')
    if train_manifest['dataset_identity']['snapshot_sha256'] != PINS[SNAPSHOT / 'summary.json']:
        raise RuntimeError('holding_diagnostic_training_snapshot_mismatch')
    spec = train_manifest['spec']
    if spec['features'] != FEATURES or spec['targets'] != TARGETS:
        raise RuntimeError('holding_diagnostic_feature_contract_changed')
    data = pd.read_csv(SNAPSHOT / 'observations.csv', float_precision='round_trip')
    predictions = pd.read_csv(TRAINING / 'baseline_observation_predictions.csv', float_precision='round_trip')
    index = read_json(TRAINING / 'model_index.json'); metadata = {}
    if list(index) != [v.strftime('%Y-%m-01') for v in pd.period_range('2020-01', '2026-08', freq='M')]:
        raise RuntimeError('holding_diagnostic_month_inventory')
    for cutoff, item in index.items():
        path = TRAINING / 'models' / cutoff / 'metadata.json'
        bind(path, {'sha256': item['metadata_sha256']}, sources)
        metadata[cutoff] = read_json(path)
    validate_training(data, metadata, spec)
    joined = join_predictions(data, predictions, metadata)
    if len(joined) != 1002 or int(joined['exit'].sum()) != training['baseline_predicted_exit_count']:
        raise RuntimeError('holding_diagnostic_observation_count')
    bind(A_ROOT / 'receipt.json', expected[str(A_ROOT / 'receipt.json')], sources)
    a_receipt = read_json(A_ROOT / 'receipt.json'); mapping = a_receipt['contract_products']
    for name in ('daily', 'positions'):
        bind(A_ROOT / (name + '.csv'), a_receipt['frames'][name], sources)
    c = C_ROOT / 'workers/C'
    bind(c / 'receipt.json', {'sha256': candidate['receipt_sha256']}, sources)
    c_receipt = read_json(c / 'receipt.json')
    if c_receipt['contract_products'] != mapping:
        raise RuntimeError('holding_diagnostic_mapping_changed')
    bind(c / 'holding_trace.json.gz', c_receipt['trace']['file'], sources)
    raw = gzip.decompress((c / 'holding_trace.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != c_receipt['trace']['raw_sha256']:
        raise RuntimeError('holding_diagnostic_trace_changed')
    trace = json.loads(raw); archives = read_json(c / 'archive_receipt.json')
    bind(c / 'archive_receipt.json', {}, sources)
    collector = load('stage005_label_collection')

    def archive(folder, name, receipt, archive_receipt):
        identity = archive_receipt[name]
        if (identity['raw_sha256'] != receipt['frames'][name]['sha256']
                or identity['raw_size'] != receipt['frames'][name]['size']):
            raise RuntimeError('holding_diagnostic_archive_binding')
        path = folder / (name + '.csv.gz')
        bind(path, identity['archive'], sources); collector.verify_archive(path, identity)
        return path

    c_paths = {name: archive(c, name, c_receipt, archives) for name in ('daily', 'positions')}
    plan_path = ROOT / 'artifacts/stage040_holding_panel/jobs.json'
    jobs = {v['observation_id']: v for v in read_json(plan_path)['jobs']}
    selected = []
    for row in first_exits(joined).to_dict('records'):
        identifier = row['observation_id']; job = jobs[identifier]
        folder = label_folder(row['label_source_stage'], identifier)
        for name in ('label.json', 'receipt.json', 'archive_receipt.json'):
            path = folder / name
            bind(path, snapshot['source_identities'][str(path)], sources)
        label, receipt, receipt_archives = (read_json(folder / name) for name in ('label.json', 'receipt.json', 'archive_receipt.json'))
        if (label['status'] != 'passed' or label['observation_id'] != identifier or label['root_id'] != row['root_id']
                or label['date'] != row['date'] or label['end_date'] != row['label_end_date']
                or not label['prefix_seven_exact'] or not label['features_current_exact']
                or label['receipt_sha256'] != sources[str(folder / 'receipt.json')]['sha256']
                or receipt['contract_products'] != mapping
                or any(label['marginal'][k] != row[k] for k in TARGETS)):
            raise RuntimeError('holding_diagnostic_label_identity')
        views = {name: archive(folder, name, receipt, receipt_archives) for name in ('daily', 'positions')}
        selected.append((row, job, views))
    for path in [Path(__file__).resolve(), CONTRACT, ROOT / 'tests/test_stage050_holding_failure_diagnostics.py',
            NETWORK_TOOL, *[ROOT / 'tools' / (name + '.py') for name in (
            'stage005_label_collection', 'stage006_monthly_models', 'stage040_holding_panel',
            'stage044_holding_models', 'stage017_label_path_decomposition')]]:
        bind(path, expected.get(str(path), {}), sources)
    return sources, joined, selected, mapping, c_paths, trace, candidate


def run():
    if OUTPUT.exists():
        raise RuntimeError('holding_diagnostic_output_already_exists')
    network = load('network', NETWORK_TOOL).NetworkBlock()
    try:
        with network:
            sources, joined, selected, mapping, c_paths, trace, candidate = prepare_inputs()
            OUTPUT.mkdir(mode=0o700)
            write_json(OUTPUT / 'input_manifest.json', {'source_identities': sources,
                'evidence_type': 'post_failure_holding_diagnostics', 'new_candidate': False})
            first = first_exits(joined)
            regressions = []
            for period, rows in [('all', joined), *list(joined.groupby(joined.date.str[:4]))]:
                eligible = rows.loc[rows.evaluable]
                for weighting, weights in [('observation', np.ones(len(eligible))), ('root_equal', root_weights(eligible.root_id))]:
                    for target in TARGETS:
                        regressions.append({'period': period, 'weighting': weighting, 'target': target,
                            **regression_metrics(eligible[target], eligible['pred_' + target], eligible['baseline_' + target], weights)})
            actions = [{'period': period, **action_metrics(rows)}
                for period, rows in [('all', joined), *list(joined.groupby(joined.date.str[:4]))]]
            c_rows = pd.DataFrame([{'date': v['date'], 'product_vt_symbol': v['product_vt_symbol'],
                'vt_symbol': v['snapshot']['bar']['vt_symbol'], **v['features'], 'exit': v['prediction']['exit']}
                for v in trace['decisions']])
            pairs, drift = crosswalk(joined, c_rows)
            ledger = load('stage017_label_path_decomposition')
            a = pd.read_csv(A_ROOT / 'daily.csv', float_precision='round_trip')
            c = pd.read_csv(c_paths['daily'], float_precision='round_trip')
            columns = ['date', 'vt_symbol', 'net_pnl']
            am, error_a = ledger.product_ledger(pd.read_csv(A_ROOT / 'positions.csv',
                usecols=columns, float_precision='round_trip'), a, mapping)
            cm, error_c = ledger.product_ledger(pd.read_csv(c_paths['positions'],
                usecols=columns, float_precision='round_trip'), c, mapping)
            if not am.index.equals(cm.index) or a.date.iloc[0] != '2020-01-02' or a.date.iloc[-1] != '2026-08-28':
                raise RuntimeError('holding_diagnostic_full_period_changed')
            cash_error = max(float(np.max(np.abs(150000. + v.total_net_pnl.cumsum() - v.account_equity))) for v in (a, c))
            delta = cm - am
            cash_error = max(cash_error, float(np.max(np.abs(delta.sum(axis=1).cumsum().to_numpy()
                - (c.account_equity - a.account_equity).to_numpy()))))
            if cash_error > TOL:
                raise RuntimeError('holding_diagnostic_full_cash_not_conserved')
            decompositions, days, products = [], [], []
            for number, (row, job, views) in enumerate(selected, 1):
                e = pd.read_csv(views['daily'], float_precision='round_trip')
                ep = pd.read_csv(views['positions'], usecols=columns, float_precision='round_trip')
                em, error = ledger.product_ledger(ep, e, mapping)
                values, day, product = holding_decomposition(am, em, a, e, row['product_vt_symbol'],
                    row['date'], row['label_end_date'], job['account_equity'], row['return_marginal'])
                decompositions.append({**{k: row[k] for k in [*KEYS, *TARGETS]},
                    'account_equity': job['account_equity'], 'label_end_date': row['label_end_date'],
                    'daily_reconciliation_error_cash': error, **values})
                days.append(day.assign(observation_id=row['observation_id']))
                products.append(product.assign(observation_id=row['observation_id']))
                if number % 10 == 0 or number == len(selected):
                    print(json.dumps({'first_exit_decomposed': number, 'planned': len(selected)}), flush=True)
            decomposed = pd.DataFrame(decompositions)
            full_products = pd.DataFrame({'product': am.columns, 'A_net_pnl': am.sum().to_numpy(),
                'C_net_pnl': cm.sum().to_numpy(), 'C_minus_A': delta.sum().to_numpy()})
            full_years = pd.DataFrame({'date': a.date, 'A_net_pnl': a.total_net_pnl,
                'C_net_pnl': c.total_net_pnl, 'C_minus_A': c.total_net_pnl - a.total_net_pnl})
            full_years = full_years.groupby(full_years.date.str[:4])[['A_net_pnl', 'C_net_pnl', 'C_minus_A']].sum().reset_index(names='year')
            outputs = {'joined_predictions.csv': joined, 'first_exits.csv': first,
                'regression_metrics.csv': pd.DataFrame(regressions), 'action_metrics.csv': pd.DataFrame(actions),
                'path_crosswalk.csv': pairs, 'first_exit_decomposition.csv': decomposed,
                'first_exit_daily.csv': pd.concat(days, ignore_index=True) if days else pd.DataFrame(),
                'first_exit_products.csv': pd.concat(products, ignore_index=True) if products else pd.DataFrame(),
                'full_path_product_delta.csv': full_products, 'full_path_year_delta.csv': full_years}
            for name, frame in outputs.items():
                with (OUTPUT / name).open('x') as stream:
                    frame.to_csv(stream, index=False, float_format='%.17g')
            for path, identity in list(sources.items()):
                bind(path, identity, sources)
            forbidden = [key for key in sys.modules if key.split('.')[0] in ('xgboost', 'vnpy_ctp')]
            if forbidden or network.attempts:
                raise RuntimeError('holding_diagnostic_native_or_network_used')
            wrong = decomposed.loc[decomposed.return_marginal.gt(0)] if len(decomposed) else decomposed
            summary = {'stage': 'stage050_holding_failure_diagnostics', 'status': 'passed',
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'source_count': len(sources),
                'observations': len(joined), 'evaluable': int(joined.evaluable.sum()),
                'training_statistics_verified_months': 80, 'actions': actions[0],
                'first_exit_actions': action_metrics(first), 'regression': regressions[:4], 'path_drift': drift,
                'first_exit_decomposition': ledger.describe(decomposed) if len(decomposed) else {'count': 0},
                'positive_return_first_exits': len(wrong),
                'positive_return_first_exits_target_positive': int(wrong.target_delta_cash.gt(TOL).sum()) if len(wrong) else 0,
                'full_path_C_minus_A_cash': float(delta.to_numpy().sum()),
                'full_path_cash_max_error': cash_error, 'product_day_max_error': max(error_a, error_c),
                'A_metrics': candidate['A_metrics'], 'C_metrics': candidate['C_metrics'],
                'candidate_primary_gate_passed': False, 'drawdown_decomposed': False,
                'new_label_count': 0, 'new_fit_count': 0, 'new_prediction_count': 0,
                'new_strategy_replay_count': 0, 'network_attempt_count': network.attempts,
                'reviewer_started': False, 'evidence_type': 'post_failure_descriptive_not_new_candidate',
                'output_identities': {name: file_identity(OUTPUT / name) for name in ['input_manifest.json', *outputs]}}
            write_json(OUTPUT / 'summary.json', summary)
            print(json.dumps(summary, allow_nan=False), flush=True)
            return summary
    except BaseException as exc:
        if OUTPUT.exists():
            write_json(OUTPUT / 'failure.json', {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__':
    run()
