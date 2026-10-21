"""Independent Stage023 stored-representation review; no SQL or author imports."""
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd


ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT/'research/lines/futures_full_market_long_signal_ai'
OUT = LINE/'outputs/stage025_ordered_history_review'
MANIFEST = LINE/'outputs/stage023_ordered_history_dataset/export/manifest.json'
EXPECTED = '3b8da3d7e94a9e3e3fc755b233d2bb93ef6ebf6813a66a0a0a913052eb8bf64a'


def bind(item):
    p = Path(item['path']); raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == item['sha256'], (str(p), digest)
    assert len(raw) == item['bytes'], str(p)
    return raw


def check_quantized(name, true, quantized, divisor=1.0):
    q = np.asarray(quantized, dtype=np.float32)
    if q.ndim == 2:
        reconstructed = q.astype(np.float64).sum(axis=1)/divisor
        bound = np.spacing(np.abs(q)).astype(np.float64).sum(axis=1)/divisor/2
    else:
        reconstructed = q.astype(np.float64)
        bound = np.spacing(np.abs(q)).astype(np.float64)/2
    # Parent CSV decimal parsing and 009/023 fsum order may differ by ~1e-15.
    bound += 1e-12*np.maximum(1, np.abs(true))
    error = np.abs(reconstructed-true)
    assert np.all(error <= bound), (name, float((error-bound).max()))
    return dict(rows=len(true), max_abs_error=float(error.max()),
                max_error_fraction_of_quantization_bound=float((error/bound).max()),
                violations=int(np.sum(error > bound)))


def main():
    started = datetime.now().astimezone().isoformat(timespec='seconds')
    began = time.monotonic()
    raw = MANIFEST.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    assert digest == EXPECTED, digest
    m = json.loads(raw)
    protocol = json.loads(bind(m['protocol']))
    assert protocol['sequence']['dtype'] == '<f4'
    sequence_raw = bind(m['sequence_npz'])
    with np.load(io.BytesIO(sequence_raw), allow_pickle=False) as data:
        assert data.files == ['ordered']
        q = data['ordered']
    assert q.shape == (194709, 20, 4) and q.dtype.str == '<f4'
    assert np.isfinite(q).all()
    assert np.all(q[:, :, 1] >= 0)
    assert np.all((q[:, :, 2] >= 0) & (q[:, :, 2] <= 1))
    ids = pd.read_csv(io.BytesIO(bind(m['event_ids_csv'])), compression='gzip')
    assert ids.columns.tolist() == ['sequence_index', 'event_id']
    assert np.array_equal(ids.sequence_index.to_numpy(), np.arange(len(q)))
    assert not ids.event_id.duplicated().any()
    columns = ['event_id', 'feature_ready', 'label_identified', 'r1_atr', 'r5_atr',
               'r20_atr', 'range_atr', 'close_location', 'log_volume_ratio20']
    parent = pd.read_csv(io.BytesIO(bind(m['parent_feature_labels'])), compression='gzip',
                         usecols=columns)
    ready = parent.loc[parent.feature_ready.eq(1)].reset_index(drop=True)
    assert len(parent) == 399252 and len(ready) == len(q)
    assert np.array_equal(ids.event_id.to_numpy(), ready.event_id.to_numpy())
    assert int(ready.label_identified.sum()) == 194168
    checks = {}
    for name, channel in [('r1_atr', 0), ('range_atr', 1),
                          ('close_location', 2), ('log_volume_ratio20', 3)]:
        checks[name] = check_quantized(name, ready[name].to_numpy(), q[:, -1, channel])
    checks['r5_atr'] = check_quantized('r5_atr', ready.r5_atr.to_numpy(),
                                      q[:, -5:, 0], np.sqrt(5.))
    checks['r20_atr'] = check_quantized('r20_atr', ready.r20_atr.to_numpy(),
                                       q[:, :, 0], np.sqrt(20.))
    terminal = json.loads(bind(m['actual_terminal']))
    assert terminal['exit_code'] == 0
    record = dict(schema='stage025_representation_review_v1',
                  independent_review=True, status='accepted_stored_representation_only',
                  source_manifest=dict(path=str(MANIFEST), sha256=digest, bytes=len(raw)),
                  ready_rows=len(q), scalar_values=int(q.size), parent_rows=len(parent),
                  known_rows=int(ready.label_identified.sum()), unknown_rows=int(ready.label_identified.eq(0).sum()),
                  dtype=q.dtype.str, shape=list(q.shape), full_id_order_equal=True,
                  full_S_quantization_relations=checks,
                  source_code_read=m['source_code'], six_behavior_tests_read=m['tests'],
                  critical=0, important=0, minor=0,
                  actual_024_results_reviewed=False, fit_calls=0, sql_queries=0,
                  database_full_hashes=0, author_calculation_imports=0, financial_backtests=0,
                  financial_ready=False, production_qualified=False,
                  limitations=['This independently tests all saved rows against accepted S summaries; it does not re-read raw OHLC or claim full source requalification.',
                               'Remaining historical formulas reviewed from code; full 024 model/result review awaits root completion notice.'])
    (OUT/'representation_review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    terminal_out = dict(schema='stage025_representation_actual_terminal_v1',
                        exit_code=0, started_at=started,
                        finished_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                        elapsed_seconds=time.monotonic()-began,
                        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        fit_calls=0, sql_queries=0, financial_backtests=0)
    (OUT/'representation_actual_terminal.json').write_text(json.dumps(terminal_out, indent=2)+'\n')
    print(json.dumps(dict(status=record['status'], rows=len(q), checks=checks,
                          elapsed_seconds=terminal_out['elapsed_seconds']), ensure_ascii=False))


if __name__ == '__main__':
    main()
