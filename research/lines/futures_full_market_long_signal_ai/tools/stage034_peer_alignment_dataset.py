"""Frozen cross-family peer contexts from the accepted Stage009 normalized panel."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

PROTOCOL_SHA = '6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b'
SCOPES = ('main', 'holdout_0', 'holdout_1')
COLUMNS = ['market_lag_median_r1', 'market_lag_breadth', 'market_lag_iqr_r1',
    'market_lag_missing', 'peer_count', 'rho_abs_sum', 'relation_missing', 'q_aligned', 'q_shuffled']
MARKET = COLUMNS[:4]
NULL_PREFIX = 'stage032-peer-alignment-null-v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')


def binding(path, **extra):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), sha256=sha(raw), bytes=len(raw), **extra)


def bound(item, checks):
    path = Path(item['path']); raw = path.read_bytes()
    if not path.is_absolute() or sha(raw) != item['sha256'] or ('bytes' in item and len(raw) != item['bytes']):
        raise ValueError('bound input changed: '+str(path))
    checks[str(path)] = dict(sha256=sha(raw), bytes=len(raw))
    return raw


def family_group(family):
    return int(hashlib.sha256(family.encode()).hexdigest(), 16) % 2


def hash_permutation(peer_names, u, own):
    prefix = NULL_PREFIX+'|'+u+'|'+own+'|'
    return np.array(sorted(range(len(peer_names)),
        key=lambda k: (hashlib.sha256((prefix+peer_names[k]).encode()).digest(), peer_names[k])), dtype=np.int64)


def market_summary(sorted_values, exclude_rank=None):
    """Quantiles after exact own-family exclusion, using the Stage009 linear rule."""
    n = len(sorted_values)-(exclude_rank is not None)
    if not n:
        return (0., 0., 0., 1.)
    def value_at(k):
        return float(sorted_values[k+int(exclude_rank is not None and k >= exclude_rank)])
    def quantile(q):
        at = (n-1)*q; low = int(at); high = min(low+1, n-1)
        a, b = value_at(low), value_at(high)
        return a+(b-a)*(at-low)
    positives = int(np.count_nonzero(sorted_values > 0))
    if exclude_rank is not None:
        positives -= int(sorted_values[exclude_rank] > 0)
    return (quantile(.5), positives/n, quantile(.75)-quantile(.25), 0.)


def build_contexts(frame, calendar, *, progress=False):
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError('source calendar must be increasing unique')
    required = ['event_id', 'family_id', 'u_date', 'feature_ready', 'r1_atr']
    if not set(required).issubset(frame.columns) or frame.event_id.duplicated().any():
        raise ValueError('missing fields or duplicate parent event identity')
    if not frame.feature_ready.isin([0, 1]).all() or not frame.u_date.isin(calendar).all():
        raise ValueError('invalid ready flag or source day')
    ready = frame.loc[frame.feature_ready.eq(1)].copy().reset_index(drop=True)
    if not np.isfinite(ready.r1_atr.to_numpy(dtype=float)).all():
        raise ValueError('nonfinite accepted ready r1')
    families = sorted(frame.family_id.unique()); family_index = {name: j for j, name in enumerate(families)}
    dates = {day: j for j, day in enumerate(calendar)}; number_families = len(families)
    panel = np.full((len(calendar), number_families), np.nan, dtype=np.float64)
    means = ready.groupby(['u_date', 'family_id'], sort=False).r1_atr.mean()
    for (day, family), value in means.items():
        panel[dates[day], family_index[family]] = float(value)
    # Neither label_identified nor D/outcome values enter aggregation, edges or the null.
    contexts = {scope: np.zeros((len(ready), 9), dtype='<f8') for scope in SCOPES}
    states = {scope: np.full(len(ready), '', dtype=object) for scope in SCOPES}
    membership = np.array([family_group(name) for name in families], dtype=np.int8)
    allowed = [np.ones(number_families, dtype=bool), membership != 0, membership != 1]
    date_groups = ready.groupby('u_date', sort=True).indices
    max_rho_roundoff = 0.; clipped_rho_entries = 0; hash_calls = 0
    with threadpool_limits(limits=1):
        for date_number, (u, row_indices) in enumerate(date_groups.items(), 1):
            current = dates[u]; shock = panel[current-1] if current else np.full(number_families, np.nan)
            shock_finite = np.isfinite(shock)
            history = panel[current-21:current-1] if current >= 21 else None
            valid_history = np.zeros(number_families, dtype=bool)
            constant_history = np.zeros(number_families, dtype=bool)
            rho = np.zeros((number_families, number_families), dtype=np.float64)
            if history is not None:
                complete = np.isfinite(history).all(axis=0)
                positions = np.flatnonzero(complete)
                if len(positions):
                    x = history[:, positions]; centered = x-x.mean(axis=0)
                    squares = np.einsum('ij,ij->j', centered, centered)
                    positive = squares > 0
                    constant_history[positions[~positive]] = True
                    positions = positions[positive]; valid_history[positions] = True
                    centered = centered[:, positive]; squares = squares[positive]
                    if len(positions):
                        standardized = centered/np.sqrt(squares)
                        correlation = standardized.T@standardized
                        overflow = np.maximum(np.abs(correlation)-1, 0.)
                        max_rho_roundoff = max(max_rho_roundoff, float(overflow.max(initial=0.)))
                        if np.any(overflow > 1e-12):
                            raise ValueError('Pearson correlation outside numerical roundoff bound')
                        clipped_rho_entries += int(np.count_nonzero(overflow))
                        rho[np.ix_(positions, positions)] = np.clip(correlation, -1., 1.)
            pool_summaries = []
            for pool in allowed:
                peers = np.flatnonzero(pool & shock_finite)
                order = np.argsort(shock[peers], kind='stable'); peers = peers[order]
                values = shock[peers]
                ranks = {int(peer): rank for rank, peer in enumerate(peers)}
                pool_summaries.append((values, ranks))
            queries = {}
            for row in row_indices:
                query = family_index[ready.at[row, 'family_id']]
                queries.setdefault(query, []).append(int(row))
            base_peer_mask = valid_history & shock_finite
            for query, target_rows in queries.items():
                all_peers = np.flatnonzero(base_peer_mask)
                all_peers = all_peers[all_peers != query]
                if valid_history[query] and len(all_peers):
                    names = [families[j] for j in all_peers]
                    hashed_peers = all_peers[hash_permutation(names, u, families[query])]
                    hash_calls += len(names)
                else:
                    hashed_peers = np.empty(0, dtype=np.int64)
                for scope_number, scope in enumerate(SCOPES):
                    values, ranks = pool_summaries[scope_number]
                    context = np.zeros(9, dtype=np.float64)
                    context[:4] = market_summary(values, ranks.get(query))
                    context[6] = 1.
                    if not valid_history[query]:
                        state = 'query_constant' if constant_history[query] else 'query_history_missing'
                    else:
                        peer_indices = all_peers[allowed[scope_number][all_peers]]
                        n = len(peer_indices); context[4] = n
                        if not n:
                            state = 'empty_peer_set'
                        else:
                            weights = rho[query, peer_indices]; z = float(np.abs(weights).sum())
                            context[5] = z
                            if z == 0:
                                state = 'zero_rho_abs_sum'
                            else:
                                permutation = hashed_peers[allowed[scope_number][hashed_peers]]
                                if len(permutation) != n:
                                    raise ValueError('null peer multiset changed')
                                context[6] = 0.
                                context[7] = float(weights@shock[peer_indices]/z)
                                context[8] = float(weights@shock[permutation]/z)
                                state = 'relation_ready'
                    contexts[scope][target_rows] = context
                    states[scope][target_rows] = state
            if progress and date_number % 500 == 0:
                print(json.dumps(dict(completed_source_dates=date_number, u_date=u, model_fits=0)), flush=True)
    if any(not np.isfinite(values).all() for values in contexts.values()):
        raise ValueError('nonfinite completed context')
    counts = dict(parent_rows=len(frame), feature_ready=len(ready), context_rows=len(ready),
        family_count=len(families), scope_count=len(SCOPES), source_calendar_days=len(calendar),
        ready_unknown_label=int(ready.label_identified.eq(0).sum()) if 'label_identified' in ready else None,
        max_rho_roundoff=max_rho_roundoff, clipped_rho_entries=clipped_rho_entries,
        hash_digest_calls=hash_calls, all_ready_rows_retained=True,
        scope_states={scope: {str(key): int(value) for key, value in Counter(states[scope]).items()} for scope in SCOPES})
    return contexts, ready.event_id.tolist(), counts, states


def save_arrays(output, contexts, event_ids):
    output = Path(output); arrays = output/'contexts.npz'
    if tuple(contexts) != SCOPES:
        raise ValueError('context scope order mismatch')
    values = {}
    for scope in SCOPES:
        array = np.asarray(contexts[scope], dtype='<f8')
        if array.shape != (len(event_ids), 9) or not np.isfinite(array).all():
            raise ValueError('invalid context shape or values')
        values[scope] = array
    with arrays.open('xb') as stream:
        np.savez_compressed(stream, **values)
    identities = output/'event_ids.csv.gz'
    with identities.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
                pd.DataFrame(dict(sequence_index=np.arange(len(event_ids)), event_id=event_ids)).to_csv(
                    stream, index=False, lineterminator='\n')
    return arrays, identities


def calendar_from_bytes(raw):
    values = np.load(io.BytesIO(raw), allow_pickle=False)
    if values.ndim != 1 or values.dtype.kind not in ('i', 'u'):
        raise ValueError('calendar must contain YYYYMMDD integers')
    calendar = []
    for value in values:
        text = str(int(value)); day = text[:4]+'-'+text[4:6]+'-'+text[6:]
        datetime.strptime(day, '%Y-%m-%d'); calendar.append(day)
    if calendar != sorted(set(calendar)):
        raise ValueError('invalid calendar order')
    return calendar


def export_dataset(protocol_path, protocol_sha256, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True); checks = {}
    if protocol_sha256 != PROTOCOL_SHA:
        raise ValueError('only frozen Stage033 protocol accepted')
    raw = bound(dict(path=str(Path(protocol_path).resolve()), sha256=protocol_sha256), checks)
    protocol = json.loads(raw); bound(protocol['frozen_spec'], checks)
    if (protocol['context_columns'] != COLUMNS or protocol['context_scopes'] != list(SCOPES)
        or protocol['context_dtype'] != '<f8' or protocol['relation_window_source_days'] != 20
        or protocol['shock_lag_source_days'] != 1 or protocol['null_prefix'] != NULL_PREFIX):
        raise ValueError('frozen context contract changed')
    parent = json.loads(bound(protocol['data_manifest'], checks))
    review = json.loads(bound(protocol['data_review'], checks))
    if not review['independent_review'] or not review['qualified_for_fixed_proxy_experiment'] or review['data_manifest'] != protocol['data_manifest']:
        raise ValueError('accepted parent dataset receipt required')
    bound(protocol['source_feature_code'], checks)
    calendar = calendar_from_bytes(bound(parent['source_calendar'], checks))
    usecols = ['event_id', 'family_id', 'product_id', 'u_date', 'feature_ready',
        'label_identified', 'r1_atr', *MARKET]
    frame = pd.read_csv(io.BytesIO(bound(parent['feature_label_csv'], checks)), compression='gzip', usecols=usecols,
        dtype={name: str for name in ('event_id', 'family_id', 'product_id', 'u_date')}, keep_default_na=False)
    frame['r1_atr'] = pd.to_numeric(frame.r1_atr, errors='coerce')
    if not frame.family_id.eq(frame.product_id.str.replace(r'_F$', '', regex=True)).all():
        raise ValueError('parent own/F family mapping mismatch')
    expected = parent['counts']
    if len(frame) != expected['rows'] or int(frame.feature_ready.sum()) != expected['feature_ready']:
        raise ValueError('accepted parent cohort count mismatch')
    contexts, event_ids, counts, states = build_contexts(frame, calendar, progress=True)
    if counts['ready_unknown_label'] != expected['ready_unknown_label']:
        raise ValueError('ready unknown row count changed')
    ready = frame.loc[frame.feature_ready.eq(1)].reset_index(drop=True)
    reference = ready[MARKET].to_numpy(dtype=float)
    difference = np.abs(contexts['main'][:, :4]-reference)
    if not np.allclose(contexts['main'][:, :4], reference, rtol=1e-12, atol=1e-12):
        raise ValueError('main market4 differs from accepted Stage009 formula')
    counts['main_market4_max_abs_error'] = float(difference.max(initial=0.))
    counts['main_market4_scalar_checks'] = int(reference.size)
    counts['sql_queries'] = 0
    arrays, identity = save_arrays(output, contexts, event_ids)
    state_path = output/'context_states.csv.gz'
    with state_path.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
                pd.DataFrame(dict(sequence_index=np.arange(len(event_ids)), event_id=event_ids,
                    **{scope+'_state': states[scope] for scope in SCOPES})).to_csv(stream, index=False, lineterminator='\n')
    return dict(schema='stage034_peer_alignment_dataset_v1',
        protocol=binding(protocol_path), parent_manifest=protocol['data_manifest'], parent_review=protocol['data_review'],
        parent_feature_labels=parent['feature_label_csv'], parent_source_code=protocol['source_feature_code'],
        context_npz=binding(arrays, keys=list(SCOPES), shape=[len(event_ids), 9], dtype='<f8', columns=COLUMNS),
        event_ids_csv=binding(identity, rows=len(event_ids), columns=['sequence_index', 'event_id']),
        context_states=binding(state_path, rows=len(event_ids)),
        source_calendar=parent['source_calendar'], source_calendar_scope_dates=parent['source_calendar_scope_dates'],
        source_bindings=checks, counts=counts, source_code=binding(Path(__file__)),
        tests=binding(Path(__file__).with_name('test_stage034_peer_alignment_dataset.py')),
        runtime=dict(executable=sys.executable, python=sys.version, numpy=np.__version__, pandas=pd.__version__),
        context_columns=COLUMNS, context_scopes=list(SCOPES),
        pool_rules=dict(main='all observable families minus own/F', holdout_0='hash%2 != 0 minus own/F', holdout_1='hash%2 != 1 minus own/F'),
        null_rule=protocol['null_rule'], null_prefix=NULL_PREFIX,
        information_cutoff='shock at t=u-1, synchronous relation only t-20 through t-1, no D or labels for input',
        parent_ready_and_unknown_states_retained=True, labels_rebuilt=False,
        raw_OHLC_or_absolute_volume_or_absolute_ATR_saved=False, sql_queries=0, database_accessed=False,
        database_full_hash_recomputed=False, model_fits=0, financial_runs=0, network_calls=0,
        financial_ready=False, production_qualified=False,
        qualification_status='pending independent Stage037 input/model review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); started = datetime.now().astimezone().isoformat(timespec='seconds'); began = time.monotonic()
    try:
        result = export_dataset(args.protocol, args.protocol_sha256, args.output)
        terminal = dict(schema='stage034_actual_terminal_v1', exit_code=0, started_at=started,
            finished_at=datetime.now().astimezone().isoformat(timespec='seconds'), elapsed_seconds=time.monotonic()-began,
            actual_build_invocations=1, command=sys.argv, source_sha256=sha(Path(__file__).read_bytes()),
            counts=result['counts'], context_npz=result['context_npz'], event_ids_csv=result['event_ids_csv'],
            sql_queries=0, model_fits=0, financial_runs=0, network_calls=0)
        write_json(args.output/'actual_terminal.json', terminal)
        result['actual_terminal'] = binding(args.output/'actual_terminal.json')
        write_json(args.output/'manifest.json', result)
        print(json.dumps(dict(exit_code=0, manifest=binding(args.output/'manifest.json'), counts=result['counts'],
            elapsed_seconds=terminal['elapsed_seconds']), ensure_ascii=False, allow_nan=False), flush=True)
    except BaseException as exc:
        if args.output.is_dir() and not (args.output/'actual_terminal.json').exists():
            write_json(args.output/'actual_terminal.json', dict(schema='stage034_actual_terminal_v1', exit_code=1,
                started_at=started, finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                elapsed_seconds=time.monotonic()-began, actual_build_invocations=1, command=sys.argv,
                error_type=type(exc).__name__, error=str(exc), sql_queries=0, model_fits=0, financial_runs=0))
        raise


if __name__ == '__main__':
    main()
