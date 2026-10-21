"""Stage050 one-shot saved-output audit, requiring root's final manifest SHA.

This file never reads SQL or imports an author calculation module. It checks
normalized tables and the bounded native slices from the unique Stage049 build.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from review_core import numeric, require, review_labels, review_peer_mapping, review_front_support

BASE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPECTED_PROTOCOL = '3d24505daecf220c232ae71acb841a59bd5717e20906d5bf60f4b2dcb0d09413'


def binding(path):
    p = Path(path)
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda: stream.read(1024*1024), b''):
            h.update(b)
    return {'path': str(p.resolve()), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()}


def table(path):
    return pd.read_csv(path, float_precision='round_trip')


def legal_bar(bar):
    if bar.get('native_missing', False):
        return False
    vals = [bar.get(x) for x in ['open', 'high', 'low', 'close', 'volume']]
    if not all(x is not None and math.isfinite(x) and x > 0 for x in vals):
        return False
    o, h, low, c, _ = vals
    return low <= min(o, c) and h >= max(o, c)


def expiry_index(e, epoch, dates):
    month = epoch.rsplit('.', 1)[1]
    candidates = [month[:4]+'-'+month[4:]+'-01']
    for name in ['known_lifecycle_exit_boundary', 'nominal_month_first_date', 'maturity_date', 'de_listed_date']:
        value = e.get(name)
        if isinstance(value, str) and len(value) >= 10 and value[:10] >= '1900-01-01':
            candidates.append(value[:10])
    return int(np.searchsorted(dates, min(candidates)))


def review_native_cases(payload, labels, features, dates):
    reports, feature_count = [], 0
    for case in payload['cases']:
        if case['kind'] == 'maturity_relation_first':
            feature_count += 1
            f = case['feature']
            actual = features.loc[features.event_id.eq(f['event_id'])].iloc[0]
            native = case['native_pairs']
            peer_returns = {}
            for epoch, bars in native.items():
                require(len(bars) == 2 and all(legal_bar(b) for b in bars), 'native maturity legal adjacent pair')
                require([b['source_index'] for b in bars] == [int(f['u_index'])-1, int(f['u_index'])], 'native pair clock')
                peer_returns[epoch] = math.log(bars[1]['close']/bars[0]['close'])
            for mapping in case['mapping']:
                numeric([mapping['log_return']], [peer_returns[mapping['peer_epoch']]], 'native peer return', 1e-14)
                numeric([mapping['shuffled_log_return']], [peer_returns[mapping['shuffled_source_epoch']]], 'native shuffled return', 1e-14)
            eligible = []
            for epoch, bars in native.items():
                month = epoch.rsplit('.', 1)[1]
                month_date = month[:4]+'-'+month[4:]+'-01'
                if month_date > f['u_date']:
                    eligible.append((month, epoch, bars))
            eligible.sort()
            front = eligible[0]
            following = next(x for x in eligible if x[0] != front[0])
            require(actual.front_epoch == front[1] and actual.next_epoch == following[1], 'native front-next includes query pool')
            numeric([actual.front_next_basis_u, actual.front_next_basis_prev],
                    [math.log(following[2][1]['close']/front[2][1]['close']),
                     math.log(following[2][0]['close']/front[2][0]['close'])], 'native front-next levels', 1e-14)
            reports.append({'kind': case['kind'], 'event_id': f['event_id'], 'native_pairs': len(native), 'passed': True})
            continue
        e = case['event']
        row = labels.loc[labels.event_id.eq(e['event_id'])].iloc[0]
        history, path = case['N_history'], case['path']
        require(len(history) == int(e['history_run']), 'native continuous N segment length')
        lows, trs, previous, N = [], [], None, math.nan
        for k, bar in enumerate(history):
            require(legal_bar(bar), 'native valid N history')
            if k:
                require(bar['source_index'] == history[k-1]['source_index']+1, 'native N contiguous')
            h, low, c = bar['high'], bar['low'], bar['close']
            tr = h-low if previous is None else max(h-low, abs(h-previous), abs(low-previous))
            trs.append(tr)
            lows.append(low)
            if len(trs) == 20:
                N = sum(trs)/20
            elif len(trs) > 20:
                N = (19*N+tr)/20
            previous = c
        numeric([row.N_u], [N], 'native N seeded recurrence', 1e-11)
        low20 = min(lows[-20:]) if len(lows) >= 20 else math.nan
        numeric([row.low20_u], [low20], 'native prior low20', 1e-11)
        if case.get('economics') and pd.notna(row.lifecycle_index):
            require(int(row.lifecycle_index) == expiry_index(case['economics'], e['reference_epoch'], dates), 'native declared lifecycle mapping')
        if row.label_state == 'entry_execution_unknown':
            require(path and not legal_bar(path[0]), 'native unknown D not next available bar')
        elif row.participation_state == 'known_nonparticipation':
            if row.cancel_reason != 'known_entry_ineligible_lifecycle':
                require(path and legal_bar(path[0]), 'native cancellation has legal quote')
                F = path[0]['open']
                reason = 'stale_boundary_at_open' if F <= low20 else 'invalid_initial_stop' if F-2*N <= 0 else None
                require(reason == row.cancel_reason, 'native quote cancellation reason')
        elif int(row.filled) == 1:
            require(path and legal_bar(path[0]), 'native entry exists')
            D, F = int(row.entry_index), path[0]['open']
            numeric([row.entry_reference], [F], 'native ideal entry')
            SL0, boundary, force = F-2*N, max(F-2*N, low20), None
            schedule = {x['u_date']: x['reference_epoch'] for x in case['reference_schedule']}
            expiry = expiry_index(case['economics'], e['reference_epoch'], dates)
            found = None
            for bar in path:
                k = bar['source_index']
                require(k >= D, 'native path starts after decision')
                if not legal_bar(bar):
                    found = ('path_or_execution_unknown', k, None, None)
                    break
                o, low = bar['open'], bar['low']
                if force:
                    found = ('closed_complete_bar_model', k, o, force)
                elif o <= boundary:
                    found = ('closed_complete_bar_model', k, o, 'gap_stop')
                elif low <= boundary:
                    found = ('closed_complete_bar_model', k, boundary, 'stop_boundary')
                if found:
                    break
                lows.append(low)
                boundary = max(SL0, min(lows[-20:]))
                current = schedule.get(bar['date'])
                force = ('lifecycle_exit' if k+1 >= expiry else
                         'observation_exit_requested' if not current else
                         'liquidity_reference_changed' if current != e['reference_epoch'] else None)
            if found:
                require(row.label_state == found[0], 'native absorbing first event state')
                if found[0] == 'closed_complete_bar_model':
                    require(int(row.exit_index) == found[1] and row.exit_reason == found[3], 'native first-hit exit clock/reason')
                    numeric([row.exit_reference], [found[2]], 'native first-hit reference', 1e-9)
                else:
                    require(int(row.unknown_index) == found[1], 'native absorbing unknown first date')
            else:
                require(row.label_state == 'open_right_censored', 'native terminal open not fake exit')
        reports.append({'kind': case['kind'], 'event_id': e['event_id'], 'history_bars': len(history), 'path_days': len(path), 'passed': True})
    return {'cases': reports, 'case_count': len(reports), 'native_feature_cases': feature_count,
            'scope': 'bounded first-cause cases only; not all source OHLC or all curve memberships independently re-read'}


def run(args):
    start = time.monotonic()
    began = datetime.now(timezone.utc).isoformat()
    root = Path(args.experiment).resolve()
    man_path = root/'manifest.json'
    man_bind = binding(man_path)
    require(man_bind['sha256'] == args.manifest_sha256, 'root authorized final manifest')
    manifest = json.loads(man_path.read_text())
    require(manifest['status'] == 'completed', 'actual complete')
    assets = []
    for item in manifest['artifacts']:
        actual = binding(item['path'])
        require(actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes'], 'required asset SHA '+str(item['path']))
        require(not item['raw_ohlc'] and item['reproducibility_required'], 'required normalized role')
        assets.append(actual)
    for field in ['source', 'tests', 'feature_module', 'feature_tests', 'accepted_kernel']:
        item = manifest[field]
        actual = binding(item['path'])
        require(actual == {k: item[k] for k in ['path', 'bytes', 'sha256']}, 'frozen source identity '+field)
    terminal = json.loads((root/'actual_terminal.json').read_text())
    require(terminal['exit_code'] == 0 and terminal['status'] == 'completed', 'real terminal complete')
    require(terminal['native_source_queries'] == 1 and terminal['actual_model_fit_calls'] == 0 and terminal['new_cash_accounts'] == 0, 'single build scope')
    protocol_path = root/'protocol.json'
    require(binding(protocol_path)['sha256'] == EXPECTED_PROTOCOL, 'same frozen048 copied protocol')
    protocol = json.loads(protocol_path.read_text())
    mother = pd.read_csv(protocol['panel']['path'], dtype=str, keep_default_na=False,
                         usecols=['event_id', 'product_id', 'exchange', 'product', 'u_date', 'reference_epoch', 'status', 'planned_execution_date', 'direction'])
    calendar_raw = np.load(protocol['calendar']['path'], allow_pickle=False)
    if calendar_raw.dtype.kind in 'iu':
        dates = [str(int(x))[:4]+'-'+str(int(x))[4:6]+'-'+str(int(x))[6:8] for x in calendar_raw]
    else:
        dates = [str(x)[:10] for x in calendar_raw]
    labels, features = table(root/'event_economic_labels.csv.gz'), table(root/'features_all.csv.gz')
    peers = table(root/'peer_mapping.csv.gz')
    labels_result = review_labels(labels, features, mother, dates)
    peers_result = review_peer_mapping(features, peers)
    control_result = review_front_support(features, peers, labels)
    economic_projection = json.loads(Path(protocol['economic_projection']['path']).read_text())['instruments']
    represented = labels.reference_epoch.fillna('').map(economic_projection)
    economic_errors = {}
    for output, source in [('multiplier', 'contract_multiplier'), ('round_lot', 'round_lot'), ('tick_size', 'tick_size')]:
        mapped = represented.map(lambda x: x.get(source) if isinstance(x, dict) else np.nan).astype(float)
        mapped = mapped.where(np.isfinite(mapped) & (mapped > 0), np.nan)
        economic_errors[output] = numeric(labels[output], mapped, 'represented epoch economic '+output)
    interval = table(root/'dependency_intervals.csv.gz')
    pd.testing.assert_frame_equal(interval, labels[interval.columns], check_dtype=False)
    cover = labels[['product_id', 'family_id', 'u_date', 'label_state', 'participation_state', 'label_history_ready20', 'filled', 'trade_label_known']].copy()
    cover['u_year'] = cover.u_date.str[:4].astype(int)
    cover['q_ready'] = features.q_missing.eq(0).astype(int)
    keys = ['u_year', 'product_id', 'family_id', 'label_state', 'participation_state']
    expected = cover.groupby(keys, dropna=False).agg(rows=('u_date', 'size'), history_ready20=('label_history_ready20', 'sum'),
                 filled=('filled', 'sum'), trade_label_known=('trade_label_known', 'sum'), q_ready=('q_ready', 'sum')).reset_index()
    pd.testing.assert_frame_equal(table(root/'time_family_coverage.csv.gz'), expected, check_dtype=False)
    summary = json.loads((root/'label_state_summary.json').read_text())
    for field, expected_count in [('mother_rows', len(labels)), ('products', labels.product_id.nunique()), ('source_dates', labels.u_date.nunique()),
                                  ('history_ready20', labels.label_history_ready20.sum()), ('filled', labels.filled.sum()), ('complete_trade_labels', labels.trade_label_known.sum())]:
        require(summary[field] == int(expected_count), 'label summary '+field)
    for field, column in [('label_states', 'label_state'), ('participation_states', 'participation_state'),
                           ('cancel_reasons', 'cancel_reason'), ('unknown_reasons', 'unknown_reason'), ('exit_reasons', 'exit_reason')]:
        require(summary[field] == dict(Counter(labels[column].dropna())), 'label state decomposition '+field)
    fs = json.loads((root/'feature_summary.json').read_text())
    for field, value in [('mother_rows', len(labels)), ('feature_rows', len(features)), ('peer_rows', len(peers)),
                         ('q_ready', features.q_missing.eq(0).sum()), ('q_missing', features.q_missing.eq(1).sum())]:
        require(fs[field] == int(value), 'feature summary '+field)
    reasons = features.q_missing_reason.fillna('ready').replace('', 'ready')
    require(fs['q_state_counts'] == dict(Counter(reasons)), 'feature missing decomposition')
    raw_item = manifest['excluded_raw_audit']
    raw_bind = binding(raw_item['path'])
    require(raw_bind['sha256'] == raw_item['sha256'] and raw_item['raw_ohlc'] and not raw_item['reproducibility_required'], 'finite raw audit separately excluded')
    with gzip.open(raw_item['path'], 'rt') as stream:
        native = review_native_cases(json.load(stream), labels, features, dates)
    closed = labels.label_state.eq('closed_complete_bar_model')
    duration = labels.loc[closed, 'holding_source_days'].to_numpy(float)
    duration_report = {'scope': 'closed complete independent events only, not IID or strategy tuning',
                       'count': len(duration), 'median': float(np.median(duration)),
                       'p95_linear': float(np.quantile(duration, .95)), 'max': int(np.max(duration))}
    primary = labels.u_date.ge('2020-01-01')
    support_2020 = {'mother': int(primary.sum()), 'ready20': int(labels.loc[primary, 'label_history_ready20'].sum()),
                    'q_ready': int(features.loc[primary, 'q_missing'].eq(0).sum()), 'closed': int((closed & primary).sum())}
    result = {'schema': 'stage050_independent_actual_review_v1', 'status': 'completed', 'started_at': began,
              'finished_at': datetime.now(timezone.utc).isoformat(), 'elapsed_seconds': time.monotonic()-start,
              'manifest': man_bind, 'required_assets_verified': assets, 'author_terminal': terminal,
              'source_bindings': [binding(__file__), binding(HERE/'review_core.py')], 'labels': labels_result,
              'peer_mapping': peers_result, 'front_next_control_support': control_result,
              'represented_epoch_economic_errors': economic_errors, 'closed_holding_source_days': duration_report,
              'support_2020_onward': support_2020, 'dependency_intervals_rows': len(interval), 'coverage_rows': len(expected),
              'all_summary_decompositions': True, 'finite_native': native,
              'findings': {'critical': 0, 'important': 0, 'minor': 0},
              'scope_limits': ['independent_event_labels_not_cash_accounts', 'conditional_filled_complete_labels',
                               'static_snapshot_and_after_close_availability_assumptions', 'bounded_native_source_review_not_full_OHLC_replay',
                               'no_AI_quality_or_tiny_stop_or_betting_proof'],
              'operations': {'SQL': 0, 'model_fits': 0, 'strategy_replays': 0, 'cash_accounts': 0, 'downloads': 0},
              'financial_metrics': None, 'production_qualified': False}
    target = HERE/'review_receipt.json'
    require(not target.exists(), 'refuse overwrite prior final review')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': result['status'], 'receipt': binding(target), 'elapsed_seconds': result['elapsed_seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    run(parser.parse_args())
