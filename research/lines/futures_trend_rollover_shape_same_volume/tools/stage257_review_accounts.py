"""Independent, read-only Stage257 pool and full-account auditing.

Reuses only the previously independent Stage256 ledger/execution audit, never
the Stage257 freezer or runner. Writes only independent_reviews/ artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

_BASE_PATH = Path(__file__).with_name('stage256_review_accounts.py')
_SPEC = importlib.util.spec_from_file_location('_stage257_independent_ledger', _BASE_PATH)
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)
sha, read, write, csv = base.sha, base.read, base.write, base.csv
audit_ledger, audit_membership = base.audit_ledger, base.audit_membership
TOL = base.TOL
ROOT = base.ROOT
FU = 'fu.SHFE'


def replay_iid(universe, width, path_id, day, master_seed=20261016):
    """Independent implementation of the declared date-keyed PCG64 protocol."""
    values = sorted(set(universe))
    if width < 0 or width > len(values):
        raise ValueError('infeasible IID width')
    month = int(str(day)[:7].replace('-', ''))
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([master_seed, 257, 1, path_id, month])))
    return set(rng.choice(values, width, replace=False).tolist())


def replay_turnover(universe, width, previous, retention, path_id, day, master_seed=20261016):
    values = set(universe); previous = set(previous)
    keepable = sorted(previous & values); newcomers = sorted(values - previous)
    lower = max(0, width - len(newcomers)); upper = min(width, len(keepable))
    if not lower <= retention <= upper:
        raise ValueError('infeasible turnover retention')
    month = int(str(day)[:7].replace('-', ''))
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([master_seed, 257, 2, path_id, month])))
    kept = rng.choice(keepable, retention, replace=False).tolist()
    added = rng.choice(newcomers, width - retention, replace=False).tolist()
    return set(kept + added)


def audit_window(trades, daily, positions, start, end, calendar):
    """Use canonical trading dates; a previous-night physical fill is legal."""
    errors = []
    expected = sorted({str(d)[:10] for d in calendar if start <= str(d)[:10] <= end})
    observed = daily.date.astype(str).tolist()
    if not expected or observed != expected:
        errors.append('daily_calendar_mismatch')
    if len(trades):
        td = trades.get('trading_date', trades.date).astype(str)
        if not td.isin(expected).all():
            errors.append('fill_outside_window')
    if len(positions):
        warm = positions[positions.date.astype(str).lt(start)]
        if len(warm) and warm[['pos_change', 'end_pos']].abs().to_numpy().max() > TOL:
            errors.append('nonflat_warmup')
        current = positions[positions.date.astype(str).ge(start)].sort_values('date')
        first = current.groupby('vt_symbol', sort=False).head(1)
        if base.residual(first.end_pos - first.pos_change) > TOL:
            errors.append('nonflat_initial_position')
        if set(current.date.astype(str)) != set(expected):
            errors.append('position_calendar_mismatch')
    else:
        errors.append('missing_position_ledger')
    return {'errors': errors, 'expected_trading_days': len(expected),
            'first_trading_date': expected[0] if expected else None,
            'last_trading_date': expected[-1] if expected else None,
            'actual_trading_days': len(observed)}


def audit_settings(actual_rows, reference, spec, capital):
    errors = []; deltas = {}
    if len(actual_rows) != 1:
        return {'errors': ['actual_strategy_instance_count'], 'delta': {}}
    actual = actual_rows[0]
    for scope in ['setting', 'actual']:
        expected = dict(reference[scope])
        expected.update(trade_start_date=spec['start'],
                        ai_product_pool_eligibility_path=str(Path(spec['pool_file']).resolve()),
                        ai_product_pool_strategy=spec['policy_id'])
        if spec.get('_private_universe_path'):
            expected['product_universe_csv_path'] = spec['_private_universe_path']
        observed = actual[scope]
        delta = {k: [expected.get(k), observed.get(k)]
                 for k in set(expected) | set(observed) if expected.get(k) != observed.get(k)}
        deltas[scope] = delta
        if delta:
            errors.append(f'{scope}_unexpected_parameter_delta')
    flags = {'enable_stage847_half_r_stop_retry': False,
             'enable_stage827_intraday_c2_stop': True,
             'enable_ai_product_pool_filter': True,
             'enable_selection_pairwise_v2': True}
    for key, value in flags.items():
        if actual['actual'].get(key) is not value:
            errors.append(f'wrong_flag:{key}')
    non_strategy = actual.get('non_strategy_fields', {})
    if (actual.get('engine_capital') != capital
            or non_strategy != reference.get('non_strategy_fields')
            or any(v != capital for v in non_strategy.values())):
        errors.append('capital_mismatch')
    if actual.get('supply_demand_signal_rows') != reference.get('supply_demand_signal_rows'):
        errors.append('external_signal_rows_changed')
    return {'errors': errors, 'delta': deltas}


def audit_fresh_state(receipt, expected_symbols, capital):
    errors = []
    if receipt.get('fresh_engine') is not True or receipt.get('fresh_engine_and_account') is not True:
        errors.append('fresh_engine_not_recorded')
    if set(receipt.get('actual_supported_symbols', [])) != set(expected_symbols):
        errors.append('actual_loaded_universe_not_19')
    if set(receipt.get('actual_product_state_keys', [])) != set(expected_symbols):
        errors.append('initial_product_state_keys_mismatch')
    if receipt.get('initial_capital') != capital:
        errors.append('initial_capital_mismatch')
    if 'initial_positions' not in receipt or any(float(v) != 0 for v in receipt['initial_positions'].values()):
        errors.append('initial_positions_not_flat')
    return errors


def audit_aliases(accounts, aliases, windows):
    errors = []; bywindow = {w['window_id']: w for w in windows}
    for label, target in aliases.items():
        window_id = label.split('__')[0]
        w = bywindow.get(window_id); a = accounts.get(target)
        if (not w or not a or w['policy_phase'] != 'common_pre_ai_only'
                or a['kind'] != 'common_pre_ai' or a['window_id'] != window_id
                or (a['start'], a['end']) != (w['start'], w['end'])):
            errors.append(f'invalid_common_alias:{label}:{target}')
        if label in accounts:
            errors.append(f'alias_also_real_account:{label}')
    return errors


def audit_pool_frame(frame, expected, policy):
    errors = []
    if set(frame.strategy.astype(str)) != {policy}:
        errors.append('policy_id')
    if set(frame.eval_date.astype(str)) != set(expected):
        errors.append('snapshot_dates')
    if frame.duplicated(['eval_date', 'product_vt_symbol']).any():
        errors.append('duplicate_pool_member')
    for day, wanted in expected.items():
        g = frame[frame.eval_date.astype(str).eq(day)]
        if set(g.product_vt_symbol) != set(wanted) or len(g) != len(wanted):
            errors.append(f'membership:{day}')
        if sorted(g.score_rank.tolist()) != list(range(1, len(wanted) + 1)):
            errors.append(f'rank_schema:{day}')
        if set(g.top_n) != {len(wanted)}:
            errors.append(f'width_schema:{day}')
        if FU in wanted and g.loc[g.product_vt_symbol.eq(FU), 'score_rank'].tolist() != [len(wanted)]:
            errors.append(f'fu_rank_schema:{day}')
    return errors


def audit_registration(manifest, experiment):
    """Reconstruct all paths independently; no import of the freezer/runner."""
    errors = []; m = manifest; exp = Path(experiment)
    bindings = {
        'source_pool': (m['source_pool'], m['source_pool_sha256']),
        'preflight': (m['preflight_path'], m['preflight_sha256']),
        'qualification': (m['qualification_path'], m['qualification_sha256']),
        'old_manifest': (m['old_stage256_manifest'], m['old_stage256_manifest_sha256']),
        'calendar': (m['accepted_calendar_daily'], m['accepted_calendar_daily_sha256']),
        'universe': (m['frozen_universe'], m['universe_source_sha256']),
        'mapping': (m['mapping_path'], m['mapping_sha256']),
        'minute': (m['minute_csv'], m['minute_cache_sha256']),
        'membership_matrix': (exp/'frozen_monthly_members.csv', m['membership_matrix_sha256']),
        'design': (m['design_path'], m['design_sha256']),
        'runtime_overlay': (m['runtime_overlay_path'], m['runtime_overlay_sha256']),
    }
    source_hashes = {}
    for label, (path, digest) in bindings.items():
        source_hashes[str(path)] = sha(path)
        if source_hashes[str(path)] != digest:
            errors.append(f'frozen_hash_changed:{label}')
    source = csv(m['source_pool']); q = read(m['qualification_path']); pre = read(m['preflight_path'])
    old = read(m['old_stage256_manifest']); u = set(m['non_fu_universe']); common = u | {FU}
    calendar = sorted(csv(m['accepted_calendar_daily']).date.astype(str).unique())
    if len(u) != 18 or FU in u or m['capital'] != 150000 or m['master_seed'] != 20261016:
        errors.append('wrong_universe_capital_or_seed')
    if set(q) != set(source.loc[source.eval_date.ne('2019-12-31'), 'eval_date']) or len(q) != 57:
        errors.append('monthly_dates_not_exact_57')
    first_signal = next(d for d in calendar if d > m['first_ai_eval_date'])
    if first_signal != '2022-02-07' or m['first_ai_signal_date'] != first_signal:
        errors.append('first_ai_activation_date')
    prior_ai = None; qualification_rows = []; legacy_differences = []
    for day in sorted(q):
        row = q[day]
        derived_u = {product for product in u if product not in pre['confirmed_new_listing_dates']
                     or day >= pre['confirmed_new_listing_dates'][product]['calendar_41st_day']}
        original = set(source.loc[source.eval_date.eq(day), 'product_vt_symbol']) - {FU}
        ai = original & derived_u
        retain = None if prior_ai is None else len(prior_ai & ai)
        effective = next(d for d in calendar if d > day)
        if (set(row['U_members']) != derived_u or set(row['AI_members']) != ai
                or row['K'] != len(ai) or row['ai_retained'] != retain
                or row['effective_signal_trade_date'] != effective):
            errors.append(f'qualification_mismatch:{day}')
        if day >= '2024-12-31' and (derived_u != u or len(ai) != 10):
            errors.append(f'old_path_distribution_changed:{day}')
        qualification_rows.append({'eval_date': day, 'U': len(derived_u), 'K': len(ai), 'retained': retain})
        if original != ai:
            legacy_differences.append({'eval_date': day, 'removed_not_replaced': sorted(original - ai)})
        prior_ai = ai
    expected_policies = {'AI_FAIR', 'COMMON_PRE_AI', 'LEGACY_AI'} | {
        f'{family}_{i:03d}' for family in ['RANDOM', 'TURNOVER'] for i in range(1, 200)}
    if set(m['policies']) != expected_policies:
        errors.append('policy_registry_not_exact_401')
    reconstructed = {'COMMON_PRE_AI': {'2019-12-31': common},
                     'AI_FAIR': {'2019-12-31': common, **{day: set(row['AI_members']) | {FU} for day, row in q.items()}}}
    inherited = 0; snapshots = 0
    for path_id in range(1, 200):
        oldspec = old['accounts'][f'RANDOM_{path_id:03d}']; oldpath = oldspec['pool_file']
        source_hashes[oldpath] = sha(oldpath)
        if source_hashes[oldpath] != oldspec['pool_sha256']:
            errors.append(f'old_pool_hash:{path_id}')
        oldframe = csv(oldpath)
        old_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261016, path_id])))
        old_expected = {}
        for day in old['expected_eval_dates']:
            want = set(old_rng.choice(sorted(u), 10, replace=False).tolist()) | {FU}
            observed = set(oldframe.loc[oldframe.eval_date.eq(day), 'product_vt_symbol'])
            if want != observed:
                errors.append(f'old_rng_reproduction:{path_id}:{day}')
            old_expected[day] = want
        iid = {'2019-12-31': common}; matched = {'2019-12-31': common}; previous = None
        for day in sorted(q):
            row = q[day]
            if day >= '2024-12-31':
                chosen = old_expected[day]; inherited += 1
            else:
                chosen = replay_iid(row['U_members'], row['K'], path_id, day, m['master_seed']) | {FU}
            iid[day] = chosen
            if previous is None:
                generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20261016, 257, 2, path_id, int(day[:7].replace('-', ''))])))
                current = set(generator.choice(sorted(row['U_members']), row['K'], replace=False).tolist())
            else:
                current = replay_turnover(row['U_members'], row['K'], previous, row['ai_retained'], path_id, day, m['master_seed'])
            matched[day] = current | {FU}; previous = current
        reconstructed[f'RANDOM_{path_id:03d}'] = iid
        reconstructed[f'TURNOVER_{path_id:03d}'] = matched
    for key, spec in m['policies'].items():
        p = spec['pool_file']; source_hashes[p] = sha(p)
        if source_hashes[p] != spec['pool_sha256']:
            errors.append(f'policy_hash:{key}')
        if key == 'LEGACY_AI':
            if source_hashes[p] != m['source_pool_sha256']:
                errors.append('legacy_not_exact_official_bytes')
            continue
        frame = csv(p); pool_errors = audit_pool_frame(frame, reconstructed[key], spec['policy_id'])
        errors.extend(f'{key}:{e}' for e in pool_errors); snapshots += len(reconstructed[key])
        if key != 'AI_FAIR' and not pd.to_numeric(frame.score).eq(0).all():
            errors.append(f'fake_random_model_score:{key}')
        if key == 'AI_FAIR':
            ss = source.set_index(['eval_date', 'product_vt_symbol']).score
            for row in frame.itertuples():
                expected_score = ss.get((row.eval_date, row.product_vt_symbol), 0.)
                if abs(float(row.score) - float(expected_score)) > 1e-10:
                    errors.append(f'AI_score_changed:{row.eval_date}:{row.product_vt_symbol}')
    windows = m['windows']; window_by_id = {w['window_id']: w for w in windows}
    expected_windows = {('2020-01-01', '2026-10-14', 'historical_full'),
                        ('2022-02-07', '2026-10-14', 'ai_primary'),
                        ('2026-01-01', '2026-10-14', 'ytd')}
    for years, last_year in [(1, 2025), (2, 2024), (3, 2023)]:
        for year in range(2020, last_year + 1):
            for month in [1, 6]:
                start = pd.Timestamp(year=year, month=month, day=1)
                end = start + pd.DateOffset(years=years) - pd.Timedelta(days=1)
                expected_windows.add((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), f'{years}y'))
    observed_windows = {(w['start'], w['end'], str(w['group']).lower()) for w in windows}
    if len(windows) != 33 or len(window_by_id) != 33 or observed_windows != expected_windows:
        errors.append('window_matrix_not_exact_33')
    expected_accounts = set(); expected_aliases = {}; common_real = 0
    for w in windows:
        wid = w['window_id']
        phase = 'common_pre_ai_only' if w['end'] < first_signal else 'ai_active_only' if w['start'] >= first_signal else 'mixed_pre_ai_and_ai'
        if w['policy_phase'] != phase:
            errors.append(f'wrong_window_phase:{wid}')
        if phase == 'common_pre_ai_only':
            target = f'{wid}__COMMON_PRE_AI'; expected_accounts.add(target); common_real += 1
            for pool in ['AI_FAIR'] + [f'RANDOM_{i:03d}' for i in range(1, 50)]:
                expected_aliases[f'{wid}__{pool}'] = target
            continue
        n = 199 if w['group'] in ['historical_full', 'ai_primary'] else 49
        members = ['AI_FAIR'] + [f'RANDOM_{i:03d}' for i in range(1, n + 1)]
        if w['group'] == 'ai_primary':
            members += [f'TURNOVER_{i:03d}' for i in range(1, 200)]
        if w['group'] in ['historical_full', 'ai_primary']:
            members += ['LEGACY_AI']
        expected_accounts.update(f'{wid}__{pool}' for pool in members)
    if set(m['accounts']) != expected_accounts or len(expected_accounts) != 1955:
        errors.append('physical_account_matrix_mismatch')
    if m['aliases'] != expected_aliases:
        errors.append('logical_alias_matrix_mismatch')
    errors += audit_aliases(m['accounts'], m['aliases'], windows)
    for run_id, a in m['accounts'].items():
        w = window_by_id.get(a['window_id']); policy = m['policies'].get(a['pool_id'])
        if not w or not policy:
            errors.append(f'unregistered_account_dependency:{run_id}'); continue
        if (a['start'], a['end']) != (w['start'], w['end']):
            errors.append(f'account_dates:{run_id}')
        if any(a.get(k) != policy.get(k) for k in ['pool_file', 'pool_sha256', 'policy_id', 'kind', 'path_id']):
            errors.append(f'account_policy_binding:{run_id}')
    logical_count = len(m['accounts']) - common_real + len(m['aliases'])
    if logical_count != 2151 or m.get('expected_logical_account_count') != 2151 or m.get('expected_account_count') != 1955:
        errors.append('logical_account_count')
    return {'status': 'FAIL' if errors else 'PASS', 'errors': sorted(set(errors)),
            'physical_accounts': len(m['accounts']), 'logical_accounts': logical_count,
            'common_real_accounts': common_real, 'aliases': len(m['aliases']), 'windows': len(windows),
            'policies': len(m['policies']), 'snapshots_reconstructed': snapshots,
            'iid_paths': 199, 'turnover_paths': 199, 'old_monthly_memberships_reproduced_and_inherited': inherited,
            'qualification': qualification_rows, 'legacy_early_static_without_fu': True,
            'legacy_months_different_from_fair': legacy_differences,
            'calendar_source': m['accepted_calendar_daily'], 'source_hashes': source_hashes,
            'numpy_version': np.__version__, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
            'audit_script_sha256': sha(__file__), 'ledger_audit_dependency_sha256': sha(_BASE_PATH),
            'experiment_manifest_sha256': sha(exp/'experiment_manifest.json')}


REQUIRED = [name for name in base.REQUIRED if name != 'stage256_account_provenance.json'] + [
    'stage257_account_provenance.json', 'input_manifest.json', 'data_check.json',
    'batch_completion.json', 'inherited_stage251_metrics.json', 'inherited_stage251_run_provenance.json']


def audit_account(run_id, directory, spec, manifest, store):
    m = manifest; directory = Path(directory); errors = []
    frames = {name: csv(directory/name) for name in REQUIRED if name.endswith('.csv')}
    metrics = read(directory/'metrics.json'); prov = read(directory/'run_provenance.json')
    params = read(directory/'effective_parameters.json'); actual = read(directory/'actual_strategy_settings.json')
    receipt = read(directory/'stage257_account_provenance.json')
    reference = read(m['reference_settings_path'])[0]
    pref = read(m['parameters_reference_path']); refdir = Path(m['parameters_reference_path']).parent
    private = directory/'_legacy_builder_inputs'/Path(m['universe_source']).name
    external_hashes = {str(private): sha(private), spec['pool_file']: sha(spec['pool_file'])}
    if external_hashes[str(private)] != m['universe_source_sha256']:
        errors.append('private_universe_bytes_changed')
    if external_hashes[spec['pool_file']] != spec['pool_sha256']:
        errors.append('pool_bytes_changed')
    setting_spec = dict(spec, _private_universe_path=str(private.resolve()))
    settings = audit_settings(actual, reference, setting_spec, m['capital']); errors += settings['errors']
    fresh_errors = audit_fresh_state(receipt, set(m['non_fu_universe']) | {FU}, m['capital']); errors += fresh_errors
    for key in ['contract_sizes', 'priceticks', 'rates', 'slippages']:
        values = params.get(key, {})
        if not values or any(k not in pref[key] or pref[key][k] != v for k, v in values.items()):
            errors.append(f'contract_metadata_changed:{key}')
    if any(float(v) != 0 for v in params['rates'].values()):
        errors.append('nonzero_commission')
    candidates = frames['entry_candidates.csv']; pool = csv(spec['pool_file'])
    membership = audit_membership(candidates, pool)
    if membership['mismatches']:
        errors.append('candidate_membership_mismatch')
    if len(candidates) and not set(candidates.product_vt_symbol) <= set(m['non_fu_universe']) | {FU}:
        errors.append('candidate_outside_loaded_products')
    ledger = audit_ledger(frames['trades.csv'], frames['daily.csv'], frames['positions.csv'], params, m['capital'])
    errors += ledger['errors']
    execution = base.audit_execution(frames, params, store); errors += execution['errors']
    calendar = csv(m['accepted_calendar_daily']).date.astype(str).tolist()
    window = audit_window(frames['trades.csv'], frames['daily.csv'], frames['positions.csv'], spec['start'], spec['end'], calendar)
    errors += window['errors']
    for key, value in [('end_equity', ledger['end_equity']), ('total_return_pct', ledger['total_return_pct']),
                       ('max_dd_pct', ledger['max_dd_pct']), ('total_slippage', ledger['slippage']),
                       ('total_trade_count', ledger['fill_count'])]:
        reported = float(metrics.get(key, float('nan')))
        if not np.isfinite(reported) or abs(reported - value) > TOL:
            errors.append(f'metrics_mismatch:{key}')
    if metrics.get('start') != spec['start'] or metrics.get('end') != spec['end']:
        errors.append('metrics_window_mismatch')
    joined = frames['daily.csv'].merge(frames['internal_equity_daily.csv'], on='date', how='left', validate='one_to_one')
    internal_res = base.residual(joined.account_equity - joined.estimated_equity)
    settled_res = base.residual(joined.account_equity - joined.settled_balance)
    if max(internal_res, settled_res) > TOL:
        errors.append('internal_equity_mismatch')
    if prov.get('vendor_swallowed_bar_exception_guard') is not True or prov.get('captured_bar_failure_count') != 0:
        errors.append('exception_guard_failed')
    if prov.get('all_data_and_model_inputs_unchanged_during_run') is not True:
        errors.append('inputs_changed_or_unverified')
    if prov.get('minute_input_sha256') != m['minute_cache_sha256']:
        errors.append('minute_identity_mismatch')
    refprov = read(refdir/'run_provenance.json')
    if prov.get('correctness_code_sha256') != refprov['correctness_code_sha256']:
        errors.append('accepted_correctness_code_identity_changed')
    for key in ['shared_signal_input_dir', 'supply_demand_history']:
        if prov.get(key) != refprov.get(key):
            errors.append(f'shared_signal_identity_changed:{key}')
    if read(directory/'input_manifest.json') != read(refdir/'input_manifest.json'):
        errors.append('frozen_base_inputs_changed')
    input_manifest = read(directory/'input_manifest.json')
    universe_key = str(Path(m['universe_source']).relative_to(ROOT))
    if input_manifest.get(universe_key) != m['universe_source_sha256']:
        errors.append('shared_universe_race_artifact')
    for name, digest in prov.get('correctness_code_sha256', {}).items():
        if sha(ROOT/name) != digest:
            errors.append(f'runtime_core_changed:{name}')
    for key in ['window_id', 'pool_id', 'kind', 'path_id', 'start', 'end', 'policy_id', 'pool_file']:
        if receipt.get(key) != spec.get(key):
            errors.append(f'receipt_identity:{key}')
    if receipt.get('run_id') != run_id or receipt.get('account_id') != run_id or receipt.get('capital') != m['capital']:
        errors.append('receipt_account_identity')
    if receipt.get('half_r_enabled') is not False or receipt.get('ai_pool_enabled') is not True:
        errors.append('receipt_flags')
    before = receipt.get('input_sha256_before', {}); after = receipt.get('input_sha256_after', {})
    if not before or before != after:
        errors.append('receipt_inputs_changed')
    identities = {'manifest': sha(directory.parent.parent/'experiment_manifest.json'), 'pool': spec['pool_sha256'],
                  'source_pool': m['source_pool_sha256'], 'minute': m['minute_cache_sha256'],
                  'qualification': m['qualification_sha256'], 'reference_settings': sha(m['reference_settings_path']),
                  'parameters_reference': sha(m['parameters_reference_path']), 'universe_source': m['universe_source_sha256']}
    if any(before.get(k) != v for k, v in identities.items()):
        errors.append('receipt_input_binding')
    if receipt.get('manifest_sha256') != identities['manifest'] or receipt.get('pool_sha256') != spec['pool_sha256']:
        errors.append('receipt_manifest_pool_binding')
    if receipt.get('private_builder_sha256', {}).get('UNIVERSE_PATH') != m['universe_source_sha256']:
        errors.append('private_builder_universe_binding')
    marker = read(directory/'batch_completion.json')
    if marker.get('returncode') != 0 or marker.get('account_id') != run_id or marker.get('manifest_sha256') != identities['manifest']:
        errors.append('batch_not_successfully_completed')
    for name, digest in marker.get('artifact_sha256', {}).items():
        if sha(directory/name) != digest:
            errors.append(f'completed_artifact_changed:{name}')
    risk = frames['entry_risk.csv']; usage = base.normalized(frames['execution_proxy_usage.csv'])
    filled = risk[risk.get('actual_filled_volume', pd.Series(index=risk.index, dtype=float)).fillna(0).gt(0)]
    ordinary = usage[usage.offset.eq('open') & ~usage.price_source.astype(str).str.startswith('stage')] if len(usage) else usage
    qty_res = price_res = risk_res = 0.
    if len(ordinary):
        rq = filled.groupby('signal_order_id').actual_filled_volume.sum(); oq = ordinary.groupby('signal_order_id').order_volume.sum()
        if set(rq.index) != set(oq.index):
            errors.append('risk_order_binding_mismatch')
        qty_res = base.residual(rq - oq)
        rp = (filled.actual_filled_volume * filled.filled_entry_price).groupby(filled.signal_order_id).sum() / rq
        op = (ordinary.order_volume * ordinary.trade_price).groupby(ordinary.signal_order_id).sum() / oq
        price_res = base.residual(rp - op)
        if max(qty_res, price_res) > TOL:
            errors.append('risk_fill_price_or_quantity_mismatch')
        size = filled.contract_vt_symbol.map(params['contract_sizes']); tick = filled.contract_vt_symbol.map(params['priceticks'])
        per = np.maximum((filled.filled_entry_price - filled.stop_price).abs() * size, np.maximum(tick * size, 1.))
        risk_res = base.residual(per * filled.actual_filled_volume - filled.actual_risk_amount)
        if risk_res > TOL:
            errors.append('risk_amount_not_filled_quantity')
    elif len(filled):
        errors.append('risk_filled_without_open')
    if (directory/'stop_retry_events.csv').exists() and len(csv(directory/'stop_retry_events.csv')):
        errors.append('half_r_events_present')
    gaps = execution['incomplete_scans'] + execution['incomplete_anchors']
    diagnostic = prov.get('diagnostic_incomplete_minutes')
    if gaps and not diagnostic:
        errors.append('strict_run_has_execution_gaps')
    if read(directory/'data_check.json').get('stage') != 257:
        errors.append('final_export_not_completed')
    errors = sorted(set(errors))
    return {'run_id': run_id, 'account_id': run_id, 'status': 'FAIL' if errors else 'PASS_DIAGNOSTIC_GAPS' if gaps else 'PASS_DIAGNOSTIC' if diagnostic else 'PASS_STRICT',
            'errors': errors, 'accounting_passed': not errors, 'strict_performance_accepted': not errors and not gaps and not diagnostic,
            'ledger': ledger, 'execution': execution, 'membership': membership, 'settings': settings,
            'settings_delta': settings['delta'], 'window': window, 'fresh_state_errors': fresh_errors,
            'actual_loaded_products': receipt.get('actual_supported_symbols'), 'observed_candidate_products': sorted(set(candidates.get('product_vt_symbol', []))),
            'external_hashes': external_hashes, 'internal_equity_max_residual': internal_res,
            'settled_balance_max_residual': settled_res, 'risk_fill_qty_max_residual': qty_res,
            'risk_fill_price_max_residual': price_res, 'risk_amount_max_residual': risk_res,
            'diagnostic_incomplete_minutes': diagnostic, 'source_metrics_sharpe': metrics.get('sharpe')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--registration-only', action='store_true')
    parser.add_argument('--account', nargs='+', action='extend')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args(); exp = args.experiment.resolve()
    manifest = read(exp/'experiment_manifest.json')
    out = exp/'independent_reviews'; out.mkdir(exist_ok=True)
    script_hash = sha(__file__); manifest_hash = sha(exp/'experiment_manifest.json'); dependency_hash = sha(_BASE_PATH)
    registration_path = out/'registration.json'; registration = read(registration_path) if registration_path.exists() else {}
    can_reuse = (not args.refresh and registration.get('status') == 'PASS'
                 and registration.get('experiment_manifest_sha256') == manifest_hash
                 and registration.get('audit_script_sha256') == script_hash
                 and all(sha(p) == h for p, h in registration.get('source_hashes', {}).items()))
    if not can_reuse:
        registration = audit_registration(manifest, exp); write(registration_path, registration)
    if args.registration_only:
        print(base.json.dumps({k: v for k, v in registration.items() if k not in ['source_hashes', 'qualification', 'legacy_months_different_from_fair']}, ensure_ascii=False))
        return 1 if registration['errors'] else 0
    if registration['errors']:
        raise ValueError('frozen_registration_failed')
    selected = args.account or list(manifest['accounts'])
    if len(selected) != len(set(selected)) or set(selected) - set(manifest['accounts']):
        raise ValueError('unknown_or_duplicate_real_account')
    results = {}; store = None
    for ident in selected:
        spec = manifest['accounts'][ident]; directory = Path(spec['output']); review_path = out/'accounts'/f'{ident}.json'
        missing = [name for name in REQUIRED if not (directory/name).is_file()]
        if missing:
            results[ident] = {'run_id': ident, 'account_id': ident, 'status': 'INCOMPLETE', 'missing_files': missing}
            continue
        receipt = read(directory/'stage257_account_provenance.json')
        if not receipt.get('completed_at'):
            results[ident] = {'run_id': ident, 'account_id': ident, 'status': 'INCOMPLETE', 'reason': 'receipt_not_complete'}
            continue
        names = REQUIRED + (['stop_retry_events.csv'] if (directory/'stop_retry_events.csv').exists() else [])
        source_hashes = {name: sha(directory/name) for name in names}
        prior = read(review_path) if review_path.exists() else {}
        if (not args.refresh and prior.get('source_hashes') == source_hashes
                and prior.get('audit_script_sha256') == script_hash
                and prior.get('ledger_audit_dependency_sha256') == dependency_hash
                and prior.get('experiment_manifest_sha256') == manifest_hash
                and all(sha(p) == h for p, h in prior.get('external_hashes', {}).items())):
            results[ident] = prior; continue
        try:
            if store is None:
                store = base.MinuteStore(manifest['minute_csv'])
            result = audit_account(ident, directory, spec, manifest, store)
            if any(sha(directory/name) != value for name, value in source_hashes.items()):
                result['errors'].append('source_changed_during_audit'); result['status'] = 'FAIL'; result['accounting_passed'] = False
        except Exception as exc:
            result = {'run_id': ident, 'account_id': ident, 'status': 'FAIL', 'accounting_passed': False,
                      'errors': [f'{type(exc).__name__}: {exc}']}
        result.update(source_hashes=source_hashes, audit_script_sha256=script_hash,
                      ledger_audit_dependency_sha256=dependency_hash, experiment_manifest_sha256=manifest_hash,
                      reviewed_at=datetime.now(timezone.utc).isoformat())
        write(review_path, result); results[ident] = result
        print(base.json.dumps({'run_id': ident, 'status': result['status'], 'errors': result.get('errors', [])}, ensure_ascii=False), flush=True)
    for ident in manifest['accounts']:
        if ident in results:
            continue
        path = out/'accounts'/f'{ident}.json'
        prior = read(path) if path.exists() else {}
        if prior.get('experiment_manifest_sha256') == manifest_hash and prior.get('audit_script_sha256') == script_hash:
            results[ident] = prior
        else:
            results[ident] = {'run_id': ident, 'status': 'REVIEW_STALE' if prior else 'NOT_REVIEWED'}
    counts = Counter(r['status'] for r in results.values()); passed = sum(v for k, v in counts.items() if k.startswith('PASS'))
    summary = {'status': 'FAIL' if counts['FAIL'] else 'COMPLETE_DIAGNOSTIC' if passed == len(results) else 'INCOMPLETE',
               'expected_accounts': len(results), 'expected_logical_accounts': manifest['expected_logical_account_count'],
               'audited_passed': passed, 'status_counts': dict(counts), 'experiment_manifest_sha256': manifest_hash,
               'audit_script_sha256': script_hash, 'strict_comparative_conclusion_allowed': False,
               'accounts': {k: {'status': v['status'], 'errors': v.get('errors', []), 'end_equity': v.get('ledger', {}).get('end_equity')} for k, v in results.items()}}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write(out/'batches'/f'{stamp}.json', summary); write(out/'latest.json', summary)
    print(base.json.dumps({k: v for k, v in summary.items() if k != 'accounts'}, ensure_ascii=False), flush=True)
    return 1 if counts['FAIL'] else 2 if args.require_all and passed != len(results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
