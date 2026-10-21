#!/usr/bin/env python3
"""Frozen440 soybean deterioration -> DCE.M historical timing diagnostic.

Importing performs no data I/O. No model, cash account, SQL, API or download.
Actual execution requires root-issued byte bindings and a fresh output directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time as dtime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from stage427_product_material_timing import block_indices, corr, partial_corr, price_timing

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage440_crop_condition_timing_protocol/protocol.json'
PROTOCOL_SHA = '8ef8794e51f857aa77cbc34dda4c6bef51b9ef1b94e30c59e04a2dd8d1a45c52'
BOOTSTRAP = {'resamples': 2000, 'block_global_trade_dates': 252, 'seed': 20261020}
MOTHER = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
MEMBERS = ['epochs', 'offsets', 'days', 'values', 'valid']
FIELDS = ['q', 'own_u', 'gap', 'after_open', 'total']
PRIMARY = ['after_open_partial_correlation', 'after_open_worsening_minus_nonworsening_mean']
STAT_KEYS = [name + suffix for name in ('gap', 'after_open', 'total')
             for suffix in ('_correlation', '_partial_correlation')] + [
                 'q_own_u_correlation', PRIMARY[1]]
PROJECTABLE = {'active', 'censored_no_D'}
NY, SH = ZoneInfo('America/New_York'), ZoneInfo('Asia/Shanghai')


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def binding(path):
    p = Path(path); blob = p.read_bytes()
    return {'path': str(p.resolve()), 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}


def checked_binding(ref):
    p = Path(ref['path']); blob = p.read_bytes()
    if len(blob) != ref['bytes'] or hashlib.sha256(blob).hexdigest() != ref['sha256']:
        raise ValueError('binding mismatch: ' + str(p))
    return blob


def stat_binding(ref):
    p = Path(ref['path']); s = p.stat()
    if s.st_size != ref['bytes'] or s.st_mtime_ns != ref['mtime_ns']:
        raise ValueError('input stat mismatch: ' + str(p))
    return {'path': str(p.resolve()), 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'inode': s.st_ino}


def availability_clock(body_release_date):
    """Frozen conservative assumption, not proof of historical first receipt."""
    released = date.fromisoformat(body_release_date)
    midnight = datetime.combine(released + timedelta(days=1), dtime(0), NY)
    return {'release_year': released.year, 'availability_new_york': midnight.isoformat(),
            'availability_shanghai': midnight.astimezone(SH).isoformat()}


def validate_calendar(calendar):
    rows = [{'u_index': int(r['u_index']), 'u_date': str(r['u_date'])} for r in calendar]
    if not rows or len({r['u_index'] for r in rows}) != len(rows):
        raise ValueError('empty or duplicate global calendar')
    if len({r['u_date'] for r in rows}) != len(rows):
        raise ValueError('duplicate global trade date')
    for i, row in enumerate(rows):
        date.fromisoformat(row['u_date'])
        if i and (row['u_index'] != rows[i-1]['u_index'] + 1 or row['u_date'] <= rows[i-1]['u_date']):
            raise ValueError('calendar must be complete increasing global u grid')
    return rows


def project_events(events, calendar):
    """Retain all source events, latest released report wins each decision u."""
    days = validate_calendar(calendar)
    closes = [datetime.combine(date.fromisoformat(r['u_date']), dtime(15), SH) for r in days]
    projected, grouped = [], {}
    seen = set()
    for source in events:
        row = dict(source)
        if row['event_key'] in seen:
            raise ValueError('duplicate source event_key')
        seen.add(row['event_key'])
        if row['crop'] != 'Soybeans':
            raise ValueError('only fixed Soybeans may enter timing projection')
        q = row['q']
        if q is not None and not np.isfinite(float(q)):
            raise ValueError('source q must be finite or null')
        if row['source_state'] != 'known' and q is not None:
            raise ValueError('unknown source cannot carry a q value')
        row.update(q=float(q) if q is not None else None, release_year=None,
                   reference_year=date.fromisoformat(row['reference_week']).year if row['reference_week'] else None,
                   availability_new_york=None, availability_shanghai=None, u_index=None, u_date=None,
                   D_index=None, D_date=None, D_open_lower_bound_shanghai=None,
                   availability_before_D_open_lower_bound=None, exact_session_time_unknown=True, superseded_by=None)
        release = row['body_release_date']
        if not release:
            row['projection_state'] = 'missing_release'; projected.append(row); continue
        row.update(availability_clock(release))
        available = datetime.fromisoformat(row['availability_shanghai'])
        position = next((i for i, close in enumerate(closes) if close >= available), None)
        if position is None:
            row['projection_state'] = 'censored_no_u'; projected.append(row); continue
        decision = days[position]
        row.update(u_index=decision['u_index'], u_date=decision['u_date'])
        if position + 1 == len(days):
            row['projection_state'] = 'censored_no_D'
        else:
            following = days[position + 1]
            execution = datetime.combine(date.fromisoformat(decision['u_date']), dtime(21), SH)
            if execution <= available:
                raise ValueError('M D-open conservative lower bound is before availability')
            row.update(D_index=following['u_index'], D_date=following['u_date'],
                       D_open_lower_bound_shanghai=execution.isoformat(),
                       availability_before_D_open_lower_bound=True, projection_state='active')
        grouped.setdefault(row['u_index'], []).append(row)
        projected.append(row)
    for group in grouped.values():
        latest = max(r['availability_shanghai'] for r in group)
        winners = [r for r in group if r['availability_shanghai'] == latest]
        if len(winners) != 1:
            raise ValueError('latest release for one u is not unique')
        for row in group:
            if row is not winners[0]:
                row.update(projection_state='superseded', superseded_by=winners[0]['event_key'])
    return projected


def attach_timing(events, representatives, cache):
    """Read only in-memory exact same-epoch bars; all source states survive."""
    output = []
    for event in events:
        row = dict(event)
        row.update(epoch=None, previous_close=None, u_close=None, D_open=None, D_close=None,
                   own_u=None, gap=None, after_open=None, total=None,
                   timing_state='not_evaluated_' + row['projection_state'])
        if row['projection_state'] == 'active':
            representative = representatives.get(row['u_index'])
            if representative is None:
                row['timing_state'] = 'missing_representative'
            else:
                row['mother_sequence_index'] = representative.get('sequence_index')
                row['mother_event_id'] = representative.get('event_id')
                timing = price_timing(cache, representative['reference_epoch'], row['u_index'])
                row.update(timing_state=timing.pop('state'), **timing)
        row['joint'] = all(row.get(k) is not None and np.isfinite(row[k]) for k in FIELDS)
        row['nonjoint_reasons'] = [] if row['joint'] else [
            reason for reason, failed in ((row['source_state'], row['q'] is None),
                                         (row['projection_state'], row['projection_state'] != 'active'),
                                         (row['timing_state'], any(row[k] is None for k in FIELDS[1:]))) if failed]
        output.append(row)
    return output


def calendar_matrix(calendar, events):
    """One latest source observation per u; no-event dates remain all NaN."""
    days = validate_calendar(calendar); positions = {r['u_index']: i for i, r in enumerate(days)}
    matrix = np.full((len(days), len(FIELDS)), np.nan)
    seen = set()
    for row in events:
        if row['projection_state'] not in PROJECTABLE or row['u_index'] not in positions:
            continue
        if row['u_index'] in seen:
            raise ValueError('more than one retained source per u')
        seen.add(row['u_index'])
        matrix[positions[row['u_index']]] = [np.nan if row.get(k) is None else float(row[k]) for k in FIELDS]
    return matrix


def statistics(data):
    a = np.asarray(data, float).reshape(-1, len(FIELDS))
    joint = np.isfinite(a).all(axis=1); selected = a[joint]
    result = {'joint_count': len(selected), 'nonjoint_calendar_dates': len(a)-len(selected),
              'q_worsening_joint': 0, 'q_nonworsening_joint': 0}
    for j, name in enumerate(('gap', 'after_open', 'total'), 2):
        result[name + '_correlation'] = corr(selected[:, 0], selected[:, j]) if len(selected) else None
        result[name + '_partial_correlation'] = partial_corr(selected[:, 0], selected[:, j], selected[:, 1]) if len(selected) else None
    result['q_own_u_correlation'] = corr(selected[:, 0], selected[:, 1]) if len(selected) else None
    result[PRIMARY[1]] = None
    if len(selected):
        worse = selected[:, 0] > 0; other = selected[:, 0] <= 0
        result.update(q_worsening_joint=int(worse.sum()), q_nonworsening_joint=int(other.sum()))
        if worse.any() and other.any():
            result[PRIMARY[1]] = float(selected[worse, 3].mean() - selected[other, 3].mean())
    return result


def summarize(calendar, events, bootstrap):
    matrix = calendar_matrix(calendar, events)
    u_set = {int(r['u_index']) for r in calendar}
    retained = [r for r in events if r['projection_state'] in PROJECTABLE and r['u_index'] in u_set]
    result = {'counts': {'calendar_dates': len(calendar), 'retained_events': len(retained),
                        'no_event_dates': len(calendar)-len(retained),
                        'q_known': sum(r['q'] is not None for r in retained),
                        'q_missing': sum(r['q'] is None for r in retained),
                        'q_worsening': sum(r['q'] is not None and r['q'] > 0 for r in retained),
                        'q_nonworsening': sum(r['q'] is not None and r['q'] <= 0 for r in retained),
                        'source_states': dict(Counter(r['source_state'] for r in retained)),
                        'timing_states': dict(Counter(r.get('timing_state', 'not_evaluated') for r in retained))},
              'statistics': statistics(matrix)}
    result['counts']['joint_events'] = result['statistics']['joint_count']
    result['counts']['nonjoint_events'] = len(retained)-result['statistics']['joint_count']
    if bootstrap:
        indices = block_indices(len(calendar), BOOTSTRAP['block_global_trade_dates'],
                                BOOTSTRAP['resamples'], BOOTSTRAP['seed'])
        replicates = {key: [] for key in STAT_KEYS}
        for index in indices:
            stats = statistics(matrix[index])
            for key in STAT_KEYS:
                replicates[key].append(stats[key])
        result['bootstrap'] = dict(BOOTSTRAP, calendar_date_count=len(calendar),
                                   indices_sha256=hashlib.sha256(indices.astype('<i8', copy=False).tobytes()).hexdigest(),
                                   same_indices_all_statistics=True, statistics={})
        for key, values in replicates.items():
            known = np.asarray([v for v in values if v is not None], float)
            result['bootstrap']['statistics'][key] = {
                'lower_2_5': float(np.percentile(known, 2.5)) if len(known) else None,
                'upper_97_5': float(np.percentile(known, 97.5)) if len(known) else None,
                'defined': len(known), 'undefined': BOOTSTRAP['resamples']-len(known)}
        result['_replicates'] = replicates
    return result


def positive(value):
    return value is not None and np.isfinite(value) and value > 0


def result_gate(eras, yearly):
    points = all(positive(eras[era]['statistics'][key]) for era in eras for key in PRIMARY)
    intervals = all(positive(eras['later_2023_2025']['bootstrap']['statistics'][key]['lower_2_5']) for key in PRIMARY)
    years = [str(year) for year in (2023, 2024, 2025)
             if all(positive(yearly.get(str(year), {}).get('statistics', {}).get(key)) for key in PRIMARY)]
    return {'both_eras_two_primary_points_positive': bool(points),
            'later_both_primary_CI_lower_positive': bool(intervals),
            'later_years_both_primary_positive': years, 'at_least_two_of_three_later_years': len(years) >= 2,
            'independent_price_review_complete': False,
            'numeric_eligible_pending_review': bool(points and intervals and len(years) >= 2),
            'financial_authorized': False, 'adding_exposure_authorized': False}


def source_events(rows):
    """Explicit adapter of Stage438 crop_rows.jsonl; never reparse raw TXT."""
    events = []
    for raw in rows:
        if raw['crop'] != 'Soybeans':
            continue
        body, current, adjacent = raw['body_release'], raw['current'], raw['adjacent_change']
        known = body['status'] == current['status'] == adjacent['status'] == 'known'
        q = None
        if known:
            release, previous_release = raw['metadata_release_date'], adjacent['previous_metadata_release_date']
            reference, previous_reference = raw['reference_week_date'], adjacent['previous_reference_week_date']
            if body['body_release_date'] != release or not previous_release or previous_release >= release:
                raise ValueError('known source release identities disagree')
            if not reference or not previous_reference or date.fromisoformat(reference).year != date.fromisoformat(previous_reference).year:
                raise ValueError('known source reference weeks must share year')
            if (date.fromisoformat(reference)-date.fromisoformat(previous_reference)).days != 7 or adjacent['reference_gap_days'] != 7:
                raise ValueError('known source is not adjacent original seven-day change')
            if adjacent['same_report_previous_week_used_as_original'] is not False or not adjacent['previous_source']:
                raise ValueError('known change must use previous original report')
            before, now, delta = adjacent['previous_original_GE'], current['good_plus_excellent'], adjacent['value_pp']
            if not np.isfinite([before, now, delta]).all() or not (0 <= before <= 100 and 0 <= now <= 100) or now-before != delta:
                raise ValueError('original GE arithmetic mismatch')
            q = float(before-now)
        reasons = []
        for label, value in (('body_release', body), ('current', current), ('adjacent_change', adjacent)):
            if value['status'] != 'known':
                reasons.extend(label + ':' + reason for reason in value.get('unknown_reasons', [value['status']]))
        if not known and not reasons:
            reasons = ['source_not_known']
        if raw['historical_first_seen'] != 'unknown':
            raise ValueError('first-seen qualification changed from frozen source boundary')
        events.append({'event_key': 'Soybeans:' + raw['metadata_release_date'] + ':' + raw['source']['sha256'],
                       'crop': 'Soybeans', 'metadata_release_date': raw['metadata_release_date'],
                       'body_release_date': body['body_release_date'] if body['status'] == 'known' else None,
                       'reference_week': raw['reference_week_date'], 'q': q,
                       'source_state': 'known' if known else 'unknown:' + ';'.join(reasons),
                       'historical_first_seen': 'unknown', 'source_evidence': raw})
    return events


def source_qualification(events, core_problems):
    counts = Counter(int(r['metadata_release_date'][:4]) for r in events if r['source_state'] == 'known')
    development = sum(counts[y] for y in range(2017, 2023))
    later = sum(counts[y] for y in range(2023, 2026))
    passed = development >= 50 and later >= 30 and all(counts[y] >= 10 for y in (2023, 2024, 2025)) and core_problems == 0
    return {'known_adjacent_changes_by_release_year': dict(sorted(counts.items())),
            'development_2017_2022': development, 'later_2023_2025': later,
            'minimums': {'development': 50, 'later': 30, 'each_2023_2024_2025': 10},
            'source_review_remaining_core_problems': core_problems, 'passed_before_price_reads': passed}


def load_execution(execution_path, authorization_path):
    execution_blob = Path(execution_path).read_bytes()
    execution = json.loads(execution_blob)
    authorization = json.loads(Path(authorization_path).read_bytes())
    if authorization['schema'] != 'stage441_timing_authorization_v1' or authorization['authorized'] is not True:
        raise ValueError('root Stage441 authorization required')
    if authorization['purpose'] != 'one_bounded_historical_timing_run' or authorization['max_actual_starts'] != 1:
        raise ValueError('one bounded run authorization required')
    if authorization['implementation'] != binding(__file__) or authorization['execution_inputs'] != binding(execution_path):
        raise ValueError('authorization does not bind exact implementation/execution bytes')
    for key in ('fits', 'cash', 'API', 'SQL', 'downloads', 'forward_D', 'account_mutations'):
        if authorization[key] != 0:
            raise ValueError('forbidden operation in authorization: ' + key)
    if execution['schema'] != 'stage441_execution_inputs_v1' or execution['era_assignment'] != 'decision_u_date':
        raise ValueError('execution input schema/era assignment')
    if execution['clock_interpretation'] != 'u21_lower_bound_exact_session_unknown':
        raise ValueError('execution must preserve lower-bound session clock interpretation')
    protocol_blob = checked_binding(execution['protocol'])
    if hashlib.sha256(protocol_blob).hexdigest() != PROTOCOL_SHA:
        raise ValueError('frozen protocol changed')
    protocol = json.loads(protocol_blob)
    if protocol['schema'] != 'stage440_fixed_soy_condition_M_timing_protocol_v1':
        raise ValueError('protocol schema')
    checked_binding(protocol['inputs']['timing_helpers'])
    checked_binding(protocol['inputs']['source_scope437'])
    output = Path(authorization['output_dir']).resolve()
    if output.parent != (LINE / 'outputs/stage441_crop_condition_timing').resolve() or output.exists():
        raise ValueError('fresh Stage441 child output directory required; no auto retry')
    if execution.get('output_dir', str(output)) != str(output):
        raise ValueError('output directory binding differs')
    return execution, authorization, protocol, output


def mother_domain(mothers):
    if len(mothers) != 399252 or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95 or mothers.product_id.str.split('.').str[0].nunique() != 6:
        raise ValueError('accepted full mother universe changed')
    if not np.array_equal(mothers.sequence_index, np.arange(len(mothers))) or mothers.duplicated(['product_id', 'u_index']).any():
        raise ValueError('mother identity')
    dates = mothers[['u_index', 'u_date']].drop_duplicates().sort_values('u_index')
    calendar = validate_calendar(dates.to_dict('records'))
    if len(mothers) != 98*len(calendar) or any(v != len(calendar) for v in mothers.groupby('product_id').size()):
        raise ValueError('all 98 products must retain full global calendar')
    return calendar


def retained_cache(flat, needed_epochs):
    epochs, offsets = flat['epochs'].tolist(), flat['offsets']
    days, values, valid = flat['days'], flat['values'], flat['valid']
    if len(epochs) != 9520 or len(set(epochs)) != 9520 or offsets.shape != (9521,) or offsets[0] != 0 or offsets[-1] != 1552456 or values.shape != (1552456, 5) or days.shape != (1552456,) or valid.shape != (1552456,):
        raise ValueError('accepted native cache dimensions')
    cache = {}
    for i, epoch in enumerate(epochs):
        if epoch not in needed_epochs:
            continue
        lo, hi = int(offsets[i]), int(offsets[i+1]); exact_days = days[lo:hi]
        if not len(exact_days) or np.any(np.diff(exact_days) <= 0):
            raise ValueError('native needed epoch order')
        # Copies ensure only required M epochs retain price arrays after flat is freed.
        cache[epoch] = (exact_days.copy(), values[lo:hi].copy(), valid[lo:hi].copy())
    return cache


def projection_summary(mothers, calendar, events):
    retained = {r['u_index']: r for r in events if r['projection_state'] in PROJECTABLE}
    states = Counter('no_new_release' if day['u_index'] not in retained else
                     ('known_event' if retained[day['u_index']]['q'] is not None else 'source_missing') for day in calendar)
    per_product = [{'product_id': str(product), 'mother_rows': int(len(group)),
                    'structurally_not_applicable': product != 'DCE.M'} for product, group in mothers.groupby('product_id', sort=True)]
    return {'mothers': len(mothers), 'products': 98, 'families': 95, 'exchanges': 6,
            'global_trade_dates': len(calendar), 'applicable_product': 'DCE.M',
            'applicable_mother_rows': len(calendar), 'other_97_structural_mother_rows': len(mothers)-len(calendar),
            'all_original_mother_identities_retained': True,
            'M_calendar_projection_states': dict(states), 'per_product': per_product,
            'no_carry_forward': True, 'projection_summary_only_original_mothers_unchanged': True}


def run_actual(execution_path, authorization_path):
    # This function is invoked only by root after source review and exact signing.
    execution, authorization, protocol, out = load_execution(execution_path, authorization_path)
    out.mkdir(); started = time.monotonic()
    operations = {'actual_starts': 1, 'actual_terminals': 0, 'source_crop_rows_full_read': 0,
                  'source_review_json_read': 0, 'mother_full_read': 0, 'native_npz_open': 0,
                  'npz_members': {key: 0 for key in MEMBERS}, 'source_raw_TXT_reads': 0,
                  'API': 0, 'downloads': 0, 'SQL': 0, 'fits': 0, 'cash': 0, 'forward_D': 0,
                  'account_mutations': 0, 'large_input_hashes_recomputed': 0, 'Y_score_reads': 0}
    save(out / 'started.json', {'schema': 'stage441_started_v1', 'time_utc': datetime.now(timezone.utc).isoformat(),
                               'authorization': binding(authorization_path), 'execution_inputs': binding(execution_path),
                               'implementation': binding(__file__), 'protocol': execution['protocol']})
    status, failure, result, before, after = 'failed', None, None, {}, {}
    try:
        operations['source_review_json_read'] += 1
        review = json.loads(checked_binding(execution['source_review']))
        if not isinstance(review, dict) or execution['source_review_remaining_core_problems'] != 0:
            raise ValueError('root must bind completed zero-core source review')
        operations['source_crop_rows_full_read'] += 1
        source_blob = checked_binding(execution['source_crop_rows'])
        source_rows = [json.loads(line) for line in source_blob.decode('utf-8').splitlines() if line.strip()]
        events = source_events(source_rows)
        if len(source_rows) != 618 or len(events) != 309:
            raise ValueError('all 618 crop slots / 309 soybean slots must survive')
        qualification = source_qualification(events, execution['source_review_remaining_core_problems'])
        save(out / 'source_qualification.json', qualification)
        if not qualification['passed_before_price_reads']:
            raise ValueError('frozen source minimums failed; no prices may be read')
        before = {key: stat_binding(protocol['inputs'][key]) for key in ('mothers', 'cache')}
        operations['mother_full_read'] += 1
        mothers = pd.read_csv(protocol['inputs']['mothers']['path'], usecols=MOTHER,
                              dtype={'sequence_index': 'int64', 'u_index': 'int64'}, keep_default_na=False)[MOTHER]
        calendar = mother_domain(mothers)
        events = project_events(events, calendar)
        representatives = {int(row['u_index']): {**row, 'sequence_index': int(row['sequence_index'])}
                           for row in mothers.loc[mothers.product_id.eq('DCE.M')].to_dict('records')}
        needed = {representatives[e['u_index']]['reference_epoch'] for e in events if e['projection_state'] == 'active'}
        needed.discard('')
        operations['native_npz_open'] += 1
        with np.load(protocol['inputs']['cache']['path'], allow_pickle=False) as archive:
            flat = {}
            for key in MEMBERS:
                flat[key] = archive[key]; operations['npz_members'][key] += 1
        cache = retained_cache(flat, needed); del flat
        facts = attach_timing(events, representatives, cache)
        save(out / 'event_facts.json', {'schema': 'stage441_all_soy_event_facts_v1', 'events': facts})
        eras, replicates, yearly = {}, {}, {}
        for name, (begin, end) in protocol['eras'].items():
            selected_calendar = [r for r in calendar if begin <= r['u_date'] <= end]
            eras[name] = summarize(selected_calendar, facts, True)
            replicates[name] = eras[name].pop('_replicates')
        for year in range(2017, 2026):
            selected_calendar = [r for r in calendar if r['u_date'][:4] == str(year)]
            yearly[str(year)] = summarize(selected_calendar, facts, False)
        known = [r for r in facts if r['joint']]
        decomposition_error = max((abs(r['total']-r['gap']-r['after_open']) for r in known), default=None)
        if decomposition_error is not None and decomposition_error > 1e-12:
            raise ValueError('return decomposition identity failed')
        result = {'schema': 'stage441_crop_condition_timing_results_v1',
                  'source_qualification': qualification, 'domain': projection_summary(mothers, calendar, facts),
                  'all_source_event_count': len(events), 'event_projection_states': dict(Counter(r['projection_state'] for r in facts)),
                  'source_states_all_events': dict(Counter(r['source_state'] for r in facts)),
                  'eras': eras, 'all_years': yearly, 'era_assignment': 'decision_u_date',
                  'gate': result_gate(eras, yearly), 'return_decomposition_max_abs_error': decomposition_error,
                  'retained_M_cache_epochs': len(cache), 'required_M_cache_epochs': len(needed),
                  'interpretation': {'prices': 'gross timing association; no fees, slippage, fills, stops or capital account',
                                    'own_u': 'close-to-close own return contains intervals before and after publication; not purely post-release',
                                    'D_clock': 'u21 Shanghai is earliest possible D-open lower bound, exact historical session time unknown; no-night D09 opens later',
                                    'PIT': 'NY following-day midnight availability assumption; archival historical first-seen remains unknown',
                                    'bootstrap': 'complete decision-u global calendar, shared noncircular 252-date moving blocks; only three later crop years, conditional and fragile',
                                    'not_identified': protocol['statistics']['not_identified']}}
        save(out / 'results.json', result); save(out / 'bootstrap_replicates.json', replicates)
        after = {key: stat_binding(protocol['inputs'][key]) for key in ('mothers', 'cache')}
        if before != after:
            raise ValueError('price source stat changed during run')
        status = 'completed'
    except Exception as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
    operations['actual_terminals'] = 1
    elapsed = time.monotonic()-started
    receipt = {'schema': 'stage441_receipt_v1', 'status': status, 'failure': failure,
               'implementation': binding(__file__), 'protocol': execution['protocol'],
               'authorization': binding(authorization_path), 'execution_inputs': binding(execution_path),
               'source_crop_rows': execution['source_crop_rows'], 'source_review': execution['source_review'],
               'operations': operations, 'inputs_before': before, 'inputs_after': after,
               'price_inputstat_unchanged': bool(before) and before == after,
               'elapsed_seconds': elapsed, 'completed_at': datetime.now(timezone.utc).isoformat()}
    save(out / 'receipt.json', receipt)
    save(out / 'terminal.json', {'status': status, 'exit_code': 0 if status == 'completed' else 1,
                                'failure': failure, 'elapsed_seconds': elapsed, 'operations': operations})
    save(out / 'manifest.json', {'schema': 'stage441_manifest_v1', 'status': status,
                                'artifacts': {p.name: binding(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'manifest.json'}})
    if failure:
        raise RuntimeError(str(failure))
    print(json.dumps({'status': status, 'gate': result['gate'], 'operations': operations}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--execution-inputs', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    run_actual(args.execution_inputs, args.authorization)
