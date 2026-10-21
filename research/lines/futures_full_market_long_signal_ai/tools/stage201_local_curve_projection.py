"""Stage200's single pure-X local log-price chord projection; no financial work.

Import/project are safe for tiny fixtures. Only --actual reads the two bound
Stage129 CSVs, once each and with the frozen column allowlists.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE / 'outputs/stage200_local_curve_qualification_protocol/protocol.json'
PROTOCOL_SHA = '944f1b91312898d55d99b96995d665d737f64f41caa23115fadaf167fb0aa180'
OUTPUT = LINE / 'outputs/stage201_local_curve_projection/actual_run1'
ACTION = ['sequence_index', 'action_id', 'mother_sequence_index', 'mother_event_id',
          'actual_epoch', 'product_id', 'family_id', 'u_date', 'u_index', 'u_close']
MOTHER = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date',
          'u_index', 'reference_epoch']
READY = 'source_ready'


def binding(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def source_stat(bound):
    path = Path(bound['path']); info = path.stat()
    if not path.is_file() or info.st_size != bound['bytes']:
        raise ValueError('inherited source size differs: ' + str(path))
    return dict(path=str(path.resolve()), bytes=info.st_size, inode=info.st_ino,
                device=info.st_dev, mtime_ns=info.st_mtime_ns,
                inherited_sha256=bound['sha256'], rehashed=False)


def project(actions, mothers):
    """Keep original identity/order; only pool quotes can supply strict neighbors."""
    if list(actions.columns) != ACTION or list(mothers.columns) != MOTHER:
        raise ValueError('exact frozen input columns required')
    a = actions.reset_index(drop=True); m = mothers.reset_index(drop=True)
    n, total = len(a), len(m)
    if (not np.array_equal(a.sequence_index, np.arange(n))
            or not np.array_equal(m.sequence_index, np.arange(total))
            or a.action_id.duplicated().any() or m.event_id.duplicated().any()
            or m.duplicated(['product_id', 'u_date']).any()):
        raise ValueError('nonunique or unordered source identity')
    parent = a.mother_sequence_index.to_numpy(dtype=np.int64)
    if (not np.array_equal(parent, a.mother_sequence_index.to_numpy())
            or np.any(parent < 0) or np.any(parent >= total)):
        raise ValueError('invalid mother sequence identity')
    for child, mother in [('mother_event_id', 'event_id'), ('product_id', 'product_id'),
                          ('family_id', 'family_id'), ('u_date', 'u_date'), ('u_index', 'u_index')]:
        if not np.array_equal(a[child].to_numpy(), m[mother].to_numpy()[parent]):
            raise ValueError('action/mother identity differs: ' + child)
    parts = a.actual_epoch.str.extract(r'^(.*)\.([0-9]{4})(0[1-9]|1[0-2])$')
    if parts.isna().any().any() or not parts[0].eq(a.product_id).all() or parts[1].eq('0000').any():
        raise ValueError('noncanonical complete epoch/product identity')
    month = 12 * parts[1].astype(np.int64).to_numpy() + parts[2].astype(np.int64).to_numpy() - 1
    first = (parts[1] + '-' + parts[2] + '-01').to_numpy(dtype='datetime64[D]')
    if not m.u_date.str.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}').all():
        raise ValueError('explicit ISO source dates required')
    u = m.u_date.to_numpy(dtype='datetime64[D]')[parent]
    price = a.u_close.to_numpy(dtype=np.float64)
    positive = np.isfinite(price) & (price > 0)
    future = first > u
    pool = positive & future
    pool_count = np.bincount(parent[pool], minlength=total)
    positions = np.flatnonzero(pool)
    positions = positions[np.lexsort((month[positions], parent[positions]))]
    group, months = parent[positions], month[positions]
    repeated = (group[1:] == group[:-1]) & (months[1:] == months[:-1])
    bad_groups = np.unique(group[1:][repeated])
    duplicate = np.isin(parent, bad_groups)
    # A duplicate eligible pool month closes the entire exact product/u group.
    positions = positions[~duplicate[positions]]
    group = parent[positions]
    left = np.r_[False, group[1:] == group[:-1]] if len(group) else np.array([], dtype=bool)
    right = np.r_[group[:-1] == group[1:], False] if len(group) else np.array([], dtype=bool)
    status = np.full(n, 'nonpositive_or_nonfinite_quote', dtype=object)
    status[positive & ~future] = 'nominal_month_not_after_u'
    status[positions] = 'no_lower_neighbor'
    status[positions[left & ~right]] = 'no_upper_neighbor'
    status[duplicate] = 'duplicate_nominal_month'
    q = np.full(n, np.nan); lower = np.full(n, '', dtype=object); upper = lower.copy()
    lower_gap = np.full(n, np.nan); upper_gap = lower_gap.copy()
    lower_pos = np.full(n, -1, dtype=np.int64); upper_pos = lower_pos.copy()
    lower_pos[positions[left]] = positions[np.flatnonzero(left) - 1]
    upper_pos[positions[right]] = positions[np.flatnonzero(right) + 1]
    epochs = a.actual_epoch.to_numpy()
    lower[positions[left]] = epochs[lower_pos[positions[left]]]
    upper[positions[right]] = epochs[upper_pos[positions[right]]]
    lower_gap[positions[left]] = month[positions[left]] - month[lower_pos[positions[left]]]
    upper_gap[positions[right]] = month[upper_pos[positions[right]]] - month[positions[right]]
    ready = positions[left & right]
    lo, hi = lower_pos[ready], upper_pos[ready]
    q[ready] = np.log(price[ready]) - ((month[hi] - month[ready]) * np.log(price[lo])
                    + (month[ready] - month[lo]) * np.log(price[hi])) / (month[hi] - month[lo])
    status[ready] = READY
    projection = a.drop(columns='u_close').copy()
    projection['q_raw'] = q; projection['projection_status'] = status
    projection['nominal_month'] = parts[1] + parts[2]
    projection['pool_count'] = pool_count[parent]
    for name, values in [('lower_epoch', lower), ('upper_epoch', upper),
                         ('lower_month_gap', lower_gap), ('upper_month_gap', upper_gap)]:
        projection[name] = values
    mother = m.copy()
    mother['child_count'] = np.bincount(parent, minlength=total)
    mother['pool_count'] = pool_count
    mother['source_ready_count'] = np.bincount(parent[ready], minlength=total)
    mother['projection_status'] = np.where(mother.child_count.eq(0), 'no_child',
        np.where(mother.source_ready_count.gt(0), 'source_ready_some', 'source_ready_none'))
    mother.loc[bad_groups, 'projection_status'] = 'duplicate_nominal_month'
    # Mechanical sequence-spaced anchors, chosen without prices, signs or outcomes.
    ordered = np.sort(ready)
    chosen = ordered[np.linspace(0, len(ordered)-1, min(16, len(ordered)), dtype=int)] if len(ordered) else []
    anchors = []
    for i in chosen:
        j, k = lower_pos[i], upper_pos[i]
        anchors.append(dict(sequence_index=int(a.sequence_index.iloc[i]), action_id=str(a.action_id.iloc[i]),
            product_id=str(a.product_id.iloc[i]), u_date=str(a.u_date.iloc[i]),
            query_epoch=str(epochs[i]), lower_epoch=str(epochs[j]), upper_epoch=str(epochs[k]),
            query_month_index=int(month[i]), lower_month_index=int(month[j]), upper_month_index=int(month[k]),
            query_price=float(price[i]), lower_price=float(price[j]), upper_price=float(price[k]), q_raw=float(q[i])))
    return projection, mother, anchors


def coverage(frame, key):
    work = pd.DataFrame({key: frame[key], 'source_ready': np.isfinite(frame.q_raw).astype(np.int64)})
    result = work.groupby(key, sort=True, dropna=False).source_ready.agg(['size', 'sum']).reset_index()
    return result.rename(columns={'size': 'action_rows', 'sum': 'source_ready_rows'})


def actual():
    started = time.monotonic()
    frozen = binding(PROTOCOL)
    if frozen['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen Stage200 protocol differs')
    protocol = json.loads(PROTOCOL.read_text())
    if protocol['read_action_columns'] != ACTION or protocol['read_mother_columns'] != MOTHER:
        raise ValueError('frozen column contract differs')
    inputs = protocol['input_bindings']
    if binding(inputs['dataset_manifest']['path']) != inputs['dataset_manifest']:
        raise ValueError('accepted dataset manifest differs')
    dataset = json.loads(Path(inputs['dataset_manifest']['path']).read_text())
    for role in ('actions', 'mothers'):
        if dataset[role] != inputs[role]:
            raise ValueError('accepted dataset binding differs: ' + role)
    if (dataset['action_rows'] != protocol['action_domain']
            or dataset['mother_rows'] != protocol['mother_domain']):
        raise ValueError('accepted dataset domains differ')
    before = {role: source_stat(inputs[role]) for role in ('actions', 'mothers')}
    sources = [binding(TOOLS / name) for name in
               ('stage201_local_curve_projection.py', 'test_stage201_local_curve_projection.py')]
    OUTPUT.mkdir(parents=True, exist_ok=False)
    counters = dict(projection=1, action_csv_reads=0, mother_csv_reads=0, fit=0, cash=0,
                    selection=0, SQL=0, downloads=0, large_input_hash_scans=0)
    write_json(OUTPUT / 'started.json', dict(schema='stage201_started_v1',
        started_at=datetime.now(timezone.utc).isoformat(), protocol=frozen,
        read_action_columns=ACTION, read_mother_columns=MOTHER, source_before=before, source_bundle=sources))
    try:
        integer = {'sequence_index': 'int64', 'u_index': 'int64'}
        action_types = {key: str for key in ACTION}
        action_types.update(integer, mother_sequence_index='int64', u_close='float64')
        mother_types = {key: str for key in MOTHER}; mother_types.update(integer)
        counters['action_csv_reads'] += 1
        actions = pd.read_csv(inputs['actions']['path'], usecols=ACTION, dtype=action_types,
            keep_default_na=False, na_values={'u_close': ['']}, float_precision='round_trip')[ACTION]
        counters['mother_csv_reads'] += 1
        mothers = pd.read_csv(inputs['mothers']['path'], usecols=MOTHER, dtype=mother_types,
            keep_default_na=False, float_precision='round_trip')[MOTHER]
        if len(actions) != protocol['action_domain'] or len(mothers) != protocol['mother_domain']:
            raise ValueError('complete input domains differ')
        projection, mother_projection, anchors = project(actions, mothers)
        after = {role: source_stat(inputs[role]) for role in ('actions', 'mothers')}
        if before != after:
            raise ValueError('source stat changed during the one permitted read')
        projection.to_csv(OUTPUT / 'action_projection.csv.gz', index=False, float_format='%.17g',
                          compression={'method': 'gzip', 'mtime': 0})
        mother_projection.to_csv(OUTPUT / 'mother_projection.csv.gz', index=False,
                                 compression={'method': 'gzip', 'mtime': 0})
        np.savez_compressed(OUTPUT / 'q_vector.npz', q_raw=projection.q_raw.to_numpy(),
                            sequence_index=projection.sequence_index.to_numpy())
        projection['year'] = projection.u_date.str[:4]
        for key in ('year', 'product_id', 'projection_status'):
            coverage(projection, key).to_csv(OUTPUT / ('coverage_by_' + key + '.csv'), index=False)
        summary = dict(schema='stage201_projection_summary_v1', status='completed',
            action_rows=len(projection), mother_rows=len(mother_projection),
            source_ready_rows=int(np.isfinite(projection.q_raw).sum()),
            products=int(mothers.product_id.nunique()), families=int(mothers.family_id.nunique()),
            exchanges=int(mothers.product_id.str.split('.').str[0].nunique()),
            action_states={str(k): int(v) for k, v in projection.projection_status.value_counts().items()},
            mother_states={str(k): int(v) for k, v in mother_projection.projection_status.value_counts().items()},
            anchor_policy='up to 16 evenly sequence-spaced source-ready identities, no outcome selection',
            counters=counters, cumulative_fit=421, cumulative_cash=226,
            interpretation='nominal-month pure-X shape support only; not alpha, execution, or strict release-vintage PIT proof')
        write_json(OUTPUT / 'anchors.json', dict(policy=summary['anchor_policy'], anchors=anchors))
        write_json(OUTPUT / 'summary.json', summary)
        terminal = dict(schema='stage201_terminal_v1', status='completed', counters=counters,
            source_before=before, source_after=after, elapsed_seconds=time.monotonic()-started)
        write_json(OUTPUT / 'terminal.json', terminal)
        artifacts = [binding(path) for path in sorted(OUTPUT.iterdir()) if path.is_file()]
        write_json(OUTPUT / 'manifest.json', dict(schema='stage201_projection_manifest_v1',
            status='completed', protocol=frozen, input_bindings=inputs, source_bundle=sources,
            source_read_receipt=dict(before=before, after=after, counters=counters), artifacts=artifacts,
            action_rows=len(projection), mother_rows=len(mother_projection)))
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        if not (OUTPUT / 'terminal.json').exists():
            write_json(OUTPUT / 'terminal.json', dict(schema='stage201_terminal_v1', status='failed',
                counters=counters, error_type=type(exc).__name__, error=str(exc),
                elapsed_seconds=time.monotonic()-started))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual', action='store_true', help='one frozen full-domain projection into fresh actual_run1')
    if not parser.parse_args().actual:
        parser.error('--actual is required; importing project() performs no reads')
    actual()
