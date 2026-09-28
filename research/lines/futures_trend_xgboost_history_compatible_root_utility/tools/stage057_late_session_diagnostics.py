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
OUTPUT = ROOT / 'artifacts/stage057_late_session_diagnostics'
CONTRACT = ROOT / 'stages/20260907_0848_stage057_late_session_diagnostic_contract.md'
BASE_FEATURES = ['directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
    'directional_close_location', 'log_holding_bars', 'layer_stop_buffer',
    'portfolio_drawdown', 'margin_to_equity', 'loss_streak']
LATE_FEATURES = ['directional_late_return_30m', 'late_volume_fraction_30m']
TARGETS = ['return_marginal', 'drawdown_marginal']
TRANSITIONS = ['both_hold', 'both_exit', 'cancelled_exit', 'added_exit', 'untrained']
PINS = {
    'stage050_holding_failure_diagnostics': '866003550548f579c8181f003b993d300719e70096cc5d1638441dfee314515c',
    'stage053_late_session_training': '9ca987c18819cd0e3ec0f6d56282825f2b0d4b5bea7a0e702d16471c5ab60715',
    'stage052_late_session_features': '3a8ebe7ed70010886707f73de9115775af61a3ef9c537e016bb731bda35e0b20',
    'stage049b_holding_full_replay': '322e986176dad1165e423112e595ab5818cb7c71795f18bc42c94893ed09d532',
    'stage056_late_session_full_replay': '398927cb6aa012b7c5f2482abeb2033fd358bc7eb252a505d669e36a4279e7f6',
}
TOL = 1e-6


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('late_diagnostic057_' + name,
        ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pair_points(old, new):
    fixed = ['observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol',
        'label_end_date', 'label_status', 'label_source_stage', *BASE_FEATURES, *TARGETS,
        'cutoff', 'status', 'evaluable', *['baseline_' + target for target in TARGETS]]
    for frame in (old, new):
        if (frame.empty or frame.observation_id.isna().any() or frame.observation_id.duplicated().any()
                or not frame.label_status.eq('verified').all()
                or not np.isfinite(frame[BASE_FEATURES + TARGETS].to_numpy(dtype=float)).all()
                or not frame.cutoff.eq(frame.date.str[:7] + '-01').all()
                or not frame.evaluable.map(lambda v: isinstance(v, (bool, np.bool_))).all()
                or not frame['exit'].map(lambda v: isinstance(v, (bool, np.bool_))).all()
                or not frame.status.isin(['predicted', 'untrained']).all()
                or not frame.evaluable.eq(frame.status.eq('predicted')).all()):
            raise RuntimeError('late_pair_inventory_invalid')
        active = frame.evaluable
        pred = frame[['pred_' + target for target in TARGETS]]
        baseline = frame[['baseline_' + target for target in TARGETS]]
        if (not np.isfinite(pred.loc[active].to_numpy(dtype=float)).all()
                or not np.isfinite(baseline.loc[active].to_numpy(dtype=float)).all()
                or not pred.loc[~active].isna().all().all()
                or not baseline.loc[~active].isna().all().all()
                or frame.loc[~active, 'exit'].any()
                or not frame.loc[active, 'exit'].eq(pred.loc[active].lt(0).all(axis=1)).all()):
            raise RuntimeError('late_pair_prediction_invalid')
    if set(old.observation_id) != set(new.observation_id):
        raise RuntimeError('late_pair_inventory_changed')
    old = old.reset_index(drop=True)
    new = new.set_index('observation_id').loc[old.observation_id].reset_index()
    if not old[fixed].equals(new[fixed]):
        raise RuntimeError('late_pair_domain_or_baseline_changed')
    result = old[fixed].copy()
    for name in ['exit', *['pred_' + target for target in TARGETS]]:
        result[name + '_old'] = old[name]
        result[name + '_new'] = new[name]
    result['transition'] = np.select([
        ~result.evaluable, result.exit_old & result.exit_new,
        result.exit_old & ~result.exit_new, ~result.exit_old & result.exit_new],
        ['untrained', 'both_exit', 'cancelled_exit', 'added_exit'], default='both_hold')
    return result


def transition_metrics(paired):
    result = {}
    for name in TRANSITIONS:
        rows = paired.loc[paired.transition.eq(name)]
        eligible = rows.loc[rows.evaluable]
        truth = eligible[TARGETS].lt(0).all(axis=1)
        result[name] = {'count': len(rows), 'roots': int(rows.root_id.nunique()),
            'true_exit_labels': int(truth.sum()), 'false_exit_labels': int((~truth).sum()),
            'return_positive_labels': int(eligible.return_marginal.gt(0).sum()),
            'drawdown_positive_labels': int(eligible.drawdown_marginal.gt(0).sum()),
            'both_positive_labels': int(eligible[TARGETS].gt(0).all(axis=1).sum()),
            'any_zero_labels': int(eligible[TARGETS].eq(0).any(axis=1).sum())}
    return result


def first_exit_comparison(old, new):
    helper = load('stage050_holding_failure_diagnostics')
    columns = ['root_id', 'observation_id', 'date', *TARGETS]
    table = helper.first_exits(old)[columns].merge(helper.first_exits(new)[columns],
        on='root_id', how='outer', suffixes=('_old', '_new'), indicator=True, validate='one_to_one')
    common = table['_merge'].eq('both')
    earlier = pd.Series(False, index=table.index)
    earlier.loc[common] = table.loc[common, 'date_new'].lt(table.loc[common, 'date_old'])
    table['comparison'] = np.select([
        table['_merge'].eq('left_only'), table['_merge'].eq('right_only'),
        table.observation_id_old.eq(table.observation_id_new), earlier],
        ['old_only', 'new_only', 'same_observation', 'new_earlier'], default='new_later')
    return table, {name: int(table.comparison.eq(name).sum()) for name in
        ['same_observation', 'new_earlier', 'new_later', 'new_only', 'old_only']}


def path_crosswalk(old, new, features):
    keys = ['date', 'product_vt_symbol', 'vt_symbol']
    columns = keys + features + ['exit']
    for frame in (old, new):
        if (not set(columns).issubset(frame.columns) or frame[keys].isna().any().any()
                or frame.duplicated(keys).any()
                or not np.isfinite(frame[features].to_numpy(dtype=float)).all()
                or not frame['exit'].map(lambda v: isinstance(v, (bool, np.bool_))).all()):
            raise RuntimeError('late_path_invalid')
    pairs = old[columns].merge(new[columns], on=keys, how='outer', validate='one_to_one',
        suffixes=('_old', '_new'), indicator=True)
    common = pairs['_merge'].eq('both')
    changed = {}
    for name in [*features, 'exit']:
        pairs['changed_' + name] = common & pairs[name + '_old'].ne(pairs[name + '_new'])
        changed[name] = int(pairs['changed_' + name].sum())
    same_features = common & ~pairs[['changed_' + name for name in features]].any(axis=1)
    actions = pairs.loc[pairs.changed_exit].sort_values(keys)
    first = None if actions.empty else actions[keys + ['exit_old', 'exit_new']].iloc[0].to_dict()
    return pairs, {'common': int(common.sum()), 'old_only': int(pairs['_merge'].eq('left_only').sum()),
        'new_only': int(pairs['_merge'].eq('right_only').sum()), 'action_changed': changed.pop('exit'),
        'feature_changed': changed, 'all_features_equal': int(same_features.sum()),
        'same_features_changed_action': int((same_features & pairs.changed_exit).sum()),
        'first_common_action_change': first, 'label_transfer_count': 0}


def compare_ledgers(daily, matrices):
    helper = load('stage017_label_path_decomposition')
    calendar = daily['A'].date.tolist()
    columns = matrices['A'].columns
    error = 0.
    for name in ('A', 'C9', 'C11'):
        frame, matrix = daily[name], matrices[name]
        helper.validate_daily(frame)
        if (frame.date.tolist() != calendar or matrix.index.tolist() != calendar
                or not matrix.columns.equals(columns) or not np.isfinite(matrix.to_numpy()).all()):
            raise RuntimeError('late_ledger_calendar_or_products_changed')
        error = max(error, float(np.max(np.abs(150000. + frame.total_net_pnl.cumsum() - frame.account_equity))),
            float(np.max(np.abs(matrix.sum(axis=1).to_numpy() - frame.total_net_pnl.to_numpy()))))
    products = pd.DataFrame({'product': columns, **{k: m.sum().to_numpy() for k, m in matrices.items()}})
    years = pd.DataFrame({'year': daily['A'].date.str[:4], **{k: v.total_net_pnl for k, v in daily.items()}})
    years = years.groupby('year').sum().reset_index()
    result = {}
    for old, new in [('A', 'C9'), ('A', 'C11'), ('C9', 'C11')]:
        key = new + '_minus_' + old
        products[key] = products[new] - products[old]
        years[key] = years[new] - years[old]
        delta = (matrices[new] - matrices[old]).sum(axis=1)
        equity = (daily[new].account_equity - daily[old].account_equity).to_numpy()
        error = max(error, float(np.max(np.abs(delta.cumsum().to_numpy() - equity))),
            abs(float(products[key].sum()) - equity[-1]), abs(float(years[key].sum()) - equity[-1]))
        result[key] = float(equity[-1])
        changed = np.flatnonzero(np.abs(equity) > TOL)
        result['first_equity_difference_' + new + '_' + old] = calendar[int(changed[0])] if len(changed) else None
    if error > TOL:
        raise RuntimeError('late_ledger_cash_not_conserved')
    return products, years, {**result, 'cash_max_error': error, 'drawdown_causal_decomposition': False}


def prepare_inputs():
    helper = load('stage050_holding_failure_diagnostics')
    sources, summaries = {}, {}

    def bound(path, expected):
        helper.bind(path, expected, sources)
        return helper.read_json(path)

    for stage, sha in PINS.items():
        summaries[stage] = bound(ROOT / 'artifacts' / stage / 'summary.json', {'sha256': sha})
    prior = summaries['stage050_holding_failure_diagnostics']
    old_path = ROOT / 'artifacts/stage050_holding_failure_diagnostics/joined_predictions.csv'
    helper.bind(old_path, prior['output_identities'][old_path.name], sources)
    old = pd.read_csv(old_path, float_precision='round_trip')
    training_root = ROOT / 'artifacts/stage053_late_session_training'
    training = summaries[training_root.name]
    for name, identity in training['output_identities'].items():
        helper.bind(training_root / name, identity, sources)
    manifest = helper.read_json(training_root / 'input_manifest.json')
    snapshot_path = helper.SNAPSHOT / 'summary.json'
    snapshot = bound(snapshot_path, {'sha256': manifest['dataset_identity']['snapshot_sha256']})
    data_path = helper.SNAPSHOT / 'observations.csv'
    helper.bind(data_path, snapshot['outputs'][data_path.name], sources)
    data = pd.read_csv(data_path, float_precision='round_trip')
    base_path = ROOT / 'artifacts/stage040_holding_panel/model_spec.json'
    base = bound(base_path, {'sha256': manifest['dataset_identity']['model_spec_sha256']})
    feature_root = ROOT / 'artifacts/stage052_late_session_features'
    for name in ['candidate_spec.json', 'observation_late_features.csv']:
        helper.bind(feature_root / name, summaries[feature_root.name]['outputs'][name], sources)
    spec = helper.read_json(feature_root / 'candidate_spec.json')
    if manifest['spec'] != spec or spec['features'] != BASE_FEATURES + LATE_FEATURES:
        raise RuntimeError('late_diagnostic_spec_changed')
    data = load('stage053_late_session_training').join_features(data,
        pd.read_csv(feature_root / 'observation_late_features.csv', float_precision='round_trip'), base, spec)
    if hashlib.sha256(data.to_csv(index=False, float_format='%.17g').encode()).hexdigest() != manifest['dataset_identity']['combined_dataset_sha256']:
        raise RuntimeError('late_diagnostic_combined_dataset_changed')
    index = helper.read_json(training_root / 'model_index.json')
    if list(index) != [v.strftime('%Y-%m-01') for v in pd.period_range('2020-01', '2026-08', freq='M')]:
        raise RuntimeError('late_diagnostic_months_changed')
    metadata = {cutoff: bound(training_root / 'models' / cutoff / 'metadata.json',
        {'sha256': item['metadata_sha256']}) for cutoff, item in index.items()}
    helper.validate_training(data, metadata, spec)
    new = helper.join_predictions(data, pd.read_csv(training_root / 'baseline_observation_predictions.csv',
        float_precision='round_trip'), metadata)
    pair_points(old, new)
    if len(new) != 1002 or int(new.evaluable.sum()) != 574 or int(new['exit'].sum()) != training['baseline_predicted_exit_count']:
        raise RuntimeError('late_diagnostic_observations_changed')
    replay_manifest = bound(ROOT / 'artifacts/stage056_late_session_full_replay/input_manifest.json',
        {'sha256': '37538d7056261174772a3dc77417530a488defa83f4535281432f36ae8c5d7bf'})
    expected = {v['path']: v for v in replay_manifest['files'].values()}
    a_receipt = bound(helper.A_ROOT / 'receipt.json', expected[str(helper.A_ROOT / 'receipt.json')])
    mapping = a_receipt['contract_products']
    paths = {'A': {}}
    for name in ['daily', 'positions']:
        path = helper.A_ROOT / (name + '.csv')
        helper.bind(path, a_receipt['frames'][name], sources)
        paths['A'][name] = path
    traces = {}
    for arm, stage in [('C9', 'stage049b_holding_full_replay'), ('C11', 'stage056_late_session_full_replay')]:
        candidate = summaries[stage]
        if candidate['status'] != 'passed' or candidate['comparison']['primary_gate_passed']:
            raise RuntimeError('late_diagnostic_expected_failed_candidate')
        folder = ROOT / 'artifacts' / stage / 'workers/C'
        receipt = bound(folder / 'receipt.json', {'sha256': candidate['receipt_sha256']})
        if receipt['contract_products'] != mapping or candidate['A_metrics'] != prior['A_metrics']:
            raise RuntimeError('late_diagnostic_baseline_changed')
        archive = bound(folder / 'archive_receipt.json', {})
        paths[arm] = {}
        for name in ['daily', 'positions']:
            identity = archive[name]
            if identity['raw_sha256'] != receipt['frames'][name]['sha256'] or identity['raw_size'] != receipt['frames'][name]['size']:
                raise RuntimeError('late_diagnostic_archive_binding')
            path = folder / (name + '.csv.gz')
            helper.bind(path, identity['archive'], sources)
            helper.load('stage005_label_collection').verify_archive(path, identity)
            paths[arm][name] = path
        path = folder / 'holding_trace.json.gz'
        helper.bind(path, receipt['trace']['file'], sources)
        raw = gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != receipt['trace']['raw_sha256']:
            raise RuntimeError('late_diagnostic_trace_changed')
        trace = json.loads(raw)
        traces[arm] = pd.DataFrame([{'date': v['date'], 'product_vt_symbol': v['product_vt_symbol'],
            'vt_symbol': v['snapshot']['bar']['vt_symbol'], **v['features'], 'exit': v['prediction']['exit']}
            for v in trace['decisions']])
        del raw, trace
    dependencies = [Path(__file__).resolve(), CONTRACT, ROOT / 'tests/test_stage057_late_session_diagnostics.py',
        helper.NETWORK_TOOL, *[ROOT / 'tools' / (name + '.py') for name in [
            'stage005_label_collection', 'stage006_monthly_models', 'stage040_holding_panel',
            'stage044_holding_models', 'stage050_holding_failure_diagnostics',
            'stage052_late_session_features', 'stage053_late_session_training', 'stage017_label_path_decomposition']]]
    for path in dependencies:
        helper.bind(path, manifest['source_identities'].get(str(path), {}), sources)
    return sources, old, new, paths, traces, mapping, summaries


def run():
    if OUTPUT.exists():
        raise RuntimeError('late_diagnostic_output_already_exists')
    helper = load('stage050_holding_failure_diagnostics')
    network = helper.load('network', helper.NETWORK_TOOL).NetworkBlock()
    OUTPUT.mkdir(mode=0o700)
    try:
        with network:
            sources, old, new, paths, traces, mapping, summaries = prepare_inputs()
            helper.write_json(OUTPUT / 'input_manifest.json', {'source_identities': sources,
                'evidence_type': 'incremental_post_failure_diagnostic', 'new_candidate': False,
                'upstream_labels_and_minute_audits': 'inherited_frozen_not_reexecuted'})
            paired = pair_points(old, new)
            first, first_counts = first_exit_comparison(old, new)
            ac, ac_stats = path_crosswalk(new, traces['C11'], BASE_FEATURES + LATE_FEATURES)
            cc, cc_stats = path_crosswalk(traces['C9'], traces['C11'], BASE_FEATURES)
            regressions, actions = [], []
            for arm, frame in [('old9', old), ('new11', new)]:
                for period, rows in [('all', frame), *list(frame.groupby(frame.date.str[:4]))]:
                    actions.append({'arm': arm, 'period': period, **helper.action_metrics(rows)})
                    eligible = rows.loc[rows.evaluable]
                    for weighting, weights in [('observation', np.ones(len(eligible))),
                            ('root_equal', helper.root_weights(eligible.root_id))]:
                        for target in TARGETS:
                            regressions.append({'arm': arm, 'period': period, 'weighting': weighting, 'target': target,
                                **helper.regression_metrics(eligible[target], eligible['pred_' + target],
                                    eligible['baseline_' + target], weights)})
            daily, matrices = {}, {}
            ledger = load('stage017_label_path_decomposition')
            for arm, files in paths.items():
                daily[arm] = pd.read_csv(files['daily'], float_precision='round_trip')
                matrices[arm], _ = ledger.product_ledger(pd.read_csv(files['positions'],
                    usecols=['date', 'vt_symbol', 'net_pnl'], float_precision='round_trip'), daily[arm], mapping)
            if len(daily['A']) != 1614 or daily['A'].date.iloc[0] != '2020-01-02' or daily['A'].date.iloc[-1] != '2026-08-28':
                raise RuntimeError('late_diagnostic_full_period_changed')
            products, years, cash = compare_ledgers(daily, matrices)
            outputs = {'paired_predictions.csv': paired, 'new_joined_predictions.csv': new,
                'first_exit_comparison.csv': first, 'regression_metrics.csv': pd.DataFrame(regressions),
                'action_metrics.csv': pd.DataFrame(actions), 'A_C11_crosswalk.csv': ac, 'C9_C11_crosswalk.csv': cc,
                'full_path_products.csv': products, 'full_path_years.csv': years}
            for name, frame in outputs.items():
                with (OUTPUT / name).open('x') as stream:
                    frame.to_csv(stream, index=False, float_format='%.17g')
            for path, identity in list(sources.items()):
                helper.bind(path, identity, sources)
            if network.attempts or any(k.split('.')[0] in ('xgboost', 'vnpy_ctp') for k in sys.modules):
                raise RuntimeError('late_diagnostic_native_or_network_used')
            first_actions = {}
            for arm, frame in [('old9', old), ('new11', new)]:
                values = helper.action_metrics(helper.first_exits(frame))
                values.pop('recall')
                first_actions[arm] = values
            summary = {'stage': 'stage057_late_session_diagnostics', 'status': 'passed',
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'source_count': len(sources),
                'observations': len(paired), 'evaluable': int(paired.evaluable.sum()),
                'transitions': transition_metrics(paired), 'first_exit_comparison': first_counts,
                'first_exit_actions_selection_conditioned_not_policy_recall': first_actions,
                'actions': [row for row in actions if row['period'] == 'all'],
                'regression': [row for row in regressions if row['period'] == 'all'],
                'A_C11_drift': ac_stats, 'C9_C11_drift': cc_stats, 'full_path': cash,
                'A_metrics': summaries['stage056_late_session_full_replay']['A_metrics'],
                'C9_metrics': summaries['stage049b_holding_full_replay']['C_metrics'],
                'C11_metrics': summaries['stage056_late_session_full_replay']['C_metrics'],
                'training_statistics_verified_months': 80, 'new_fit_count': 0, 'new_prediction_count': 0,
                'new_label_count': 0, 'new_strategy_replay_count': 0, 'network_attempt_count': network.attempts,
                'reviewer_started': False, 'evidence_type': 'descriptive_not_new_candidate',
                'output_identities': {name: helper.file_identity(OUTPUT / name) for name in ['input_manifest.json', *outputs]}}
            helper.write_json(OUTPUT / 'summary.json', summary)
            print(json.dumps(summary, allow_nan=False), flush=True)
            return summary
    except BaseException as exc:
        helper.write_json(OUTPUT / 'failure.json', {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__':
    run()
