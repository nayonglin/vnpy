"""Build frozen, causal 20-by-4 histories for the already accepted Stage009 cohort."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import gzip
import hashlib
import importlib.util
import io
from itertools import groupby
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

PARENT_PATH = Path(__file__).with_name('stage009_day_proxy_dataset.py')
_SPEC = importlib.util.spec_from_file_location('stage009_sequence_parent', PARENT_PATH)
_PARENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PARENT)
OWN_FEATURES = _PARENT.OWN_FEATURES
BAR_FIELDS = _PARENT.BAR_FIELDS
PROTOCOL_SHA = 'ae0708cb9eb232d5c5d7936fc705f77b2f361e4b039442e707b82c828b27f99a'
CHANNELS = ['delta_close_atr', 'range_atr', 'close_location', 'log_relative_volume']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
        allow_nan=False)+'\n')


def binding(path, **extra):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), sha256=sha(raw), bytes=len(raw), **extra)


def bound(item, checks):
    path = Path(item['path']); raw = path.read_bytes()
    if not path.is_absolute() or sha(raw) != item['sha256'] or ('bytes' in item and len(raw) != item['bytes']):
        raise ValueError('bound input changed: '+str(path))
    checks[str(path)] = dict(sha256=sha(raw), bytes=len(raw))
    return raw


def window_representation(window, calendar):
    """Only 21 bars ending at u are accepted; no execution-day row is consumed."""
    index = calendar if isinstance(calendar, dict) else {d: i for i, d in enumerate(calendar)}
    if len(window) != 21:
        raise ValueError('exactly 21 same-epoch bars required')
    epoch = window[0]['contract_epoch_id']
    if any(row['contract_epoch_id'] != epoch for row in window):
        raise ValueError('history crosses epoch')
    positions = [index.get(row['trade_date'], -1) for row in window]
    if positions[0] < 0 or positions != list(range(positions[0], positions[0]+21)):
        raise ValueError('history is not 21 consecutive source-calendar bars')
    if not all(_PARENT.valid_history_bar(row) for row in window):
        raise ValueError('invalid positive-volume history bar')
    summary, atr, state = _PARENT.own_features(window)
    if state != 'ready' or summary is None:
        raise ValueError('parent history not feature ready')
    volume_mean = math.fsum(row['volume'] for row in window[:-1])/20
    values = np.empty((20, 4), dtype=np.float64)
    for j in range(1, 21):
        previous, row = window[j-1], window[j]
        width = row['high']-row['low']
        values[j-1] = ((row['close']-previous['close'])/atr, width/atr,
            (row['close']-row['low'])/width if width > 0 else .5,
            math.log(row['volume']/volume_mean))
    if not np.isfinite(values).all():
        raise ValueError('nonfinite historical representation')
    return values, atr, summary


def canonical_bag(ordered):
    """Canonicalize complete already-quantized four-tuples, with no temporal tie key."""
    ordered = np.asarray(ordered)
    if ordered.ndim != 3 or ordered.shape[2] != 4 or ordered.dtype.str != '<f4' or not np.isfinite(ordered).all():
        raise ValueError('finite little-endian float32 four-tuples required')
    keys = tuple(ordered[:, :, channel] for channel in (3, 2, 1, 0))
    indices = np.lexsort(keys, axis=1)
    return np.take_along_axis(ordered, indices[:, :, None], axis=1)


def build_sequences(parent, calendar, bar_records, *, scope_end):
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError('calendar must be nonempty unique increasing')
    if parent.event_id.duplicated().any():
        raise ValueError('duplicate parent event identity')
    if not parent.feature_ready.isin([0, 1]).all() or not parent.label_identified.isin([0, 1]).all():
        raise ValueError('invalid parent ready/identified flags')
    ready = parent.loc[parent.feature_ready.eq(1)].reset_index(drop=True)
    columns = ['event_id', 'reference_epoch', 'product_id', 'u_date', 'atr20', *OWN_FEATURES]
    refs = {}
    for i, row in enumerate(ready[columns].itertuples(index=False, name=None)):
        refs.setdefault(row[1], []).append((i, row))
    index = {d: i for i, d in enumerate(calendar)}
    output = np.empty((len(ready), 20, 4), dtype='<f4')
    written = np.zeros(len(ready), dtype=bool)
    raw_rows = 0; epochs = 0; previous_epoch = ''; max_atr_error = 0.; max_summary_error = 0.
    for epoch, group in groupby(bar_records, key=lambda row: row['contract_epoch_id']):
        if epoch <= previous_epoch:
            raise ValueError('source epochs not unique ordered')
        previous_epoch = epoch; epochs += 1; bars = []; last = ''
        for raw in group:
            row = dict(raw); d = row['trade_date']
            if d > scope_end:
                continue
            if d not in index or (last and d <= last):
                raise ValueError('source date outside calendar or duplicate/unordered')
            if epoch != row['exchange']+'.'+row['product']+'.'+str(row['contract_yyyymm']):
                raise ValueError('source epoch identity conflict')
            last = d; bars.append(row); raw_rows += 1
        if epoch not in refs:
            continue
        positions = {row['trade_date']: i for i, row in enumerate(bars)}
        for sequence_index, expected in refs[epoch]:
            event_id, reference, product_id, u, expected_atr, *expected_summary = expected
            if reference != epoch or epoch.rsplit('.', 1)[0] != product_id:
                raise ValueError('parent reference identity conflict')
            position = positions.get(u)
            if position is None:
                raise ValueError('accepted ready u missing from source')
            window = bars[max(0, position-20):position+1]
            values, atr, summary = window_representation(window, index)
            if not math.isclose(atr, expected_atr, rel_tol=5e-13, abs_tol=1e-13):
                raise ValueError('parent ATR mismatch: '+event_id)
            if not np.allclose(summary, expected_summary, rtol=5e-13, atol=1e-13):
                raise ValueError('parent S11 mismatch: '+event_id)
            max_atr_error = max(max_atr_error, abs(atr-expected_atr))
            max_summary_error = max(max_summary_error, float(np.max(np.abs(np.array(summary)-expected_summary))))
            output[sequence_index] = values.astype('<f4')
            written[sequence_index] = True
    if not written.all() or not np.isfinite(output).all():
        raise ValueError('unbuilt or nonfinite accepted ready rows')
    counts = dict(parent_rows=len(parent), feature_ready=len(ready), sequence_rows=len(output),
        source_contract_day_rows=raw_rows, source_epochs=epochs,
        label_identified=int(ready.label_identified.sum()),
        ready_unknown_label=int(ready.label_identified.eq(0).sum()),
        sequence_scalar_values=int(output.size), parent_atr_max_abs_error=max_atr_error,
        parent_S11_max_abs_error=max_summary_error, all_ready_rows_retained=bool(written.all()))
    return output, ready.event_id.tolist(), counts


def save_arrays(output, ordered, event_ids):
    output = Path(output)
    values = np.asarray(ordered, dtype='<f4')
    if values.shape != (len(event_ids), 20, 4) or not np.isfinite(values).all():
        raise ValueError('invalid representation shape or values')
    sequence = output/'ordered_history.npz'
    with sequence.open('xb') as stream:
        np.savez_compressed(stream, ordered=values)
    identities = output/'event_ids.csv.gz'
    with identities.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
                pd.DataFrame(dict(sequence_index=np.arange(len(event_ids)), event_id=event_ids)).to_csv(
                    stream, index=False, lineterminator='\n')
    return sequence, identities


def export_dataset(protocol_path, protocol_sha256, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    checks = {}
    if protocol_sha256 != PROTOCOL_SHA:
        raise ValueError('only frozen Stage022 protocol accepted')
    protocol_binding = dict(path=str(Path(protocol_path).resolve()), sha256=protocol_sha256)
    protocol_raw = bound(protocol_binding, checks); protocol = json.loads(protocol_raw)
    bound(protocol['frozen_spec'], checks)
    if protocol['sequence'] != dict(bars=20, channels=CHANNELS, dtype='<f4', order='oldest_to_newest',
        bag='lexsort_all_four_tuple_no_date_tie', flatten='time_then_channel'):
        raise ValueError('sequence contract changed')
    parent = json.loads(bound(protocol['data_manifest'], checks))
    review = json.loads(bound(protocol['data_review'], checks))
    if not review['independent_review'] or not review['qualified_for_fixed_proxy_experiment'] or review['data_manifest'] != protocol['data_manifest']:
        raise ValueError('accepted parent dataset receipt required')
    bound(protocol['source_feature_code'], checks)
    if protocol['source_feature_code']['path'] != str(PARENT_PATH.resolve()):
        raise ValueError('parent feature implementation path mismatch')
    source = json.loads(bound(protocol['source_bindings'], checks))
    before = _PARENT.db_state(source['database']['path'])
    for key in ('bytes', 'mtime_ns', 'inode', 'wal_present', 'shm_present'):
        if before[key] != source['database'][key]:
            raise ValueError('inherited database stat changed: '+key)
    if before['wal_present'] or before['shm_present']:
        raise ValueError('database sidecar present')
    calendar = _PARENT.calendar_from_bytes(bound(source['calendar'], checks))
    if parent['source_calendar_scope_dates'] != [d for d in calendar if source['scope_start'] <= d <= source['scope_end']]:
        raise ValueError('parent source calendar scope changed')
    data_raw = bound(parent['feature_label_csv'], checks)
    usecols = ['event_id', 'reference_epoch', 'product_id', 'u_date', 'atr20',
        'feature_ready', 'label_identified', *OWN_FEATURES]
    frame = pd.read_csv(io.BytesIO(data_raw), compression='gzip', usecols=usecols,
        dtype={name: str for name in ('event_id', 'reference_epoch', 'product_id', 'u_date')},
        keep_default_na=False)
    # No D field, label value or execution-price diagnostic is read by this builder.
    for column in ['atr20', *OWN_FEATURES]:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    expected = parent['counts']
    if len(frame) != expected['rows'] or int(frame.feature_ready.sum()) != expected['feature_ready']:
        raise ValueError('parent cohort count mismatch')
    db_path = Path(source['database']['path']).resolve()
    with closing(sqlite3.connect(db_path.as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON'); db.row_factory = sqlite3.Row
        query = 'SELECT '+','.join(BAR_FIELDS)+' FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date'
        cursor = db.execute(query, (source['scope_start'], source['scope_end']))
        ordered, event_ids, counts = build_sequences(frame, calendar, (dict(row) for row in cursor), scope_end=source['scope_end'])
    counts['sql_queries'] = 1
    if counts['source_contract_day_rows'] != expected['source_contract_day_rows'] or counts['source_epochs'] != expected['source_epochs']:
        raise ValueError('parent source scan count mismatch')
    if counts['label_identified'] != expected['label_identified'] or counts['ready_unknown_label'] != expected['ready_unknown_label']:
        raise ValueError('parent known/unknown ready cohort changed')
    after = _PARENT.db_state(source['database']['path'])
    if before != after:
        raise ValueError('database changed during read')
    sequence, identities = save_arrays(output, ordered, event_ids)
    return dict(schema='stage023_ordered_history_dataset_v1',
        sequence_npz=binding(sequence, key='ordered', shape=list(ordered.shape), dtype=ordered.dtype.str,
            channels=CHANNELS, order='oldest_to_newest'),
        event_ids_csv=binding(identities, rows=len(event_ids), columns=['sequence_index', 'event_id']),
        protocol=binding(protocol_path), parent_manifest=protocol['data_manifest'], parent_review=protocol['data_review'],
        parent_feature_labels=parent['feature_label_csv'], parent_source_code=protocol['source_feature_code'],
        source_calendar=source['calendar'], source_calendar_scope_dates=parent['source_calendar_scope_dates'],
        source_bindings=checks, counts=counts, database_before=before, database_after=after,
        inherited_database_sha256=source['database']['sha256'], database_full_hash_recomputed=False,
        source_code=binding(Path(__file__)), tests=binding(Path(__file__).with_name('test_stage023_ordered_history_dataset.py')),
        runtime=dict(executable=sys.executable, python=sys.version, numpy=np.__version__, pandas=pd.__version__, sqlite=sqlite3.sqlite_version),
        bag_saved=False, bag_contract='derive lexsort complete quantized tuples by channels 0,1,2,3; no age tie',
        raw_OHLC_or_absolute_volume_or_absolute_ATR_saved=False,
        information_cutoff='same-reference-epoch u close, 21 consecutive source-calendar bars, never D features',
        parent_ready_and_unknown_states_retained=True, labels_rebuilt=False,
        model_fits=0, financial_runs=0, network_calls=0, financial_ready=False, production_qualified=False,
        qualification_status='pending independent Stage025 representation/model review',
        limitations=['Quantized representation of inherited bounded historical source, not publication PIT proof.',
            'No new tradability, account-return, stop-size or leverage evidence.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now().astimezone().isoformat(timespec='seconds'); began = time.monotonic()
    try:
        result = export_dataset(args.protocol, args.protocol_sha256, args.output)
        terminal = dict(schema='stage023_actual_terminal_v1', exit_code=0, started_at=started,
            finished_at=datetime.now().astimezone().isoformat(timespec='seconds'), elapsed_seconds=time.monotonic()-began,
            actual_build_invocations=1, command=sys.argv, source_sha256=sha(Path(__file__).read_bytes()),
            counts=result['counts'], sequence_npz=result['sequence_npz'], event_ids_csv=result['event_ids_csv'],
            model_fits=0, financial_runs=0, network_calls=0)
        write_json(args.output/'actual_terminal.json', terminal)
        result['actual_terminal'] = binding(args.output/'actual_terminal.json')
        write_json(args.output/'manifest.json', result)
        print(json.dumps(dict(exit_code=0, manifest=binding(args.output/'manifest.json'),
            counts=result['counts'], elapsed_seconds=terminal['elapsed_seconds']), ensure_ascii=False, allow_nan=False))
    except BaseException as exc:
        if args.output.is_dir() and not (args.output/'actual_terminal.json').exists():
            write_json(args.output/'actual_terminal.json', dict(schema='stage023_actual_terminal_v1', exit_code=1,
                started_at=started, finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                elapsed_seconds=time.monotonic()-began, actual_build_invocations=1,
                command=sys.argv, error_type=type(exc).__name__, error=str(exc),
                model_fits=0, financial_runs=0, network_calls=0))
        raise


if __name__ == '__main__':
    main()
