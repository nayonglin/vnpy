"""Continue only never-started Stage109 source dates after confirmed process loss.

This is an explicitly interrupted acquisition, not a replacement one-pass claim.
Original files remain untouched. No scientific, model, or cash parameters change.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import threading
import time

LINE = pathlib.Path(__file__).resolve().parents[1]
OLD = LINE / 'outputs/stage109_member_category_history'
OUT = LINE / 'outputs/stage116_source_recovery'
SOURCE = pathlib.Path(__file__).with_name('stage109_member_category_history.py')
SOURCE_SHA = '0f41c2cc36e6e404b45020867db9aba0136976ceae63bdda9fc9dc47a1d5e212'
PROTOCOL = LINE / 'outputs/stage108_member_category_history_protocol/protocol.json'
PROTOCOL_SHA = '384195b05855ad1520de8df7988ae2eca2f1ca4f42db8cd3d231a3984ec28253'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}


def partition_dates(dates, started, records, raw_dates, reuse):
    assert len(started) == len(set(started)), 'duplicate started requests'
    all_dates, sent, reused = set(dates), set(started), set(reuse)
    assert sent <= all_dates and reused <= all_dates and not sent & reused
    assert set(records) <= all_dates
    assert set(records) <= sent | reused, 'unstarted completed record'
    assert raw_dates <= sent, 'orphan raw outside started requests'
    return {'completed': sorted(set(records) - reused),
            'interrupted': sorted(sent - set(records)),
            'remaining': [day for day in dates if day not in sent | reused]}


def require_dead(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    raise AssertionError(f'original PID {pid} still exists; do not duplicate it')


def main():
    original_source = SOURCE.read_bytes()
    assert sha(original_source) == SOURCE_SHA
    raw_protocol = PROTOCOL.read_bytes()
    assert sha(raw_protocol) == PROTOCOL_SHA
    protocol = json.loads(raw_protocol)
    date_bound = protocol['source_dates']
    date_bytes = pathlib.Path(date_bound['path']).read_bytes()
    assert len(date_bytes) == date_bound['size'] and sha(date_bytes) == date_bound['sha256']
    dates = json.loads(date_bytes)['dates']
    original_started = json.loads((OLD / 'started.json').read_bytes())
    require_dead(original_started['pid'])
    assert not (OLD / 'completion_receipt.json').exists(), 'original already terminal'
    assert original_started['implementation_sha256'] == SOURCE_SHA
    requests_bytes = (OLD / 'requests_started.jsonl').read_bytes()
    started_rows = [json.loads(row) for row in requests_bytes.splitlines()]
    started_dates = [row['date'] for row in started_rows]
    records = {p.stem: json.loads(p.read_bytes()) for p in (OLD / 'dates').glob('*.json')}
    reuse = [item['date'] for item in protocol['reuse']]
    raw_dates = {p.name.removeprefix('pm').removesuffix('.response.gz') for p in (OLD / 'raw').glob('*.response.gz')}
    plan = partition_dates(dates, started_dates, records, raw_dates, reuse)
    assert len(dates) == 3588 and len(started_dates) == 2895 and len(plan['completed']) == 2893
    assert plan['interrupted'] == ['20231213', '20231214'] and len(plan['remaining']) == 680
    for day in plan['interrupted']:
        assert day not in raw_dates and not (OLD / 'normalized' / f'{day}.json.gz').exists(), 'interrupted raw must be inspected, not discarded'
    for day in plan['completed']:
        rec = records[day]
        assert rec['status'] == 'http_200' and not rec.get('truncated') and not rec.get('error')
        assert pathlib.Path(rec['archive_path']).stat().st_size == rec['archive_bytes']
    for day in reuse:
        assert records[day]['status'] == 'reused_stage104_106'
    original_elapsed = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(original_started['started_utc'])).total_seconds()
    assert 0 < original_elapsed < protocol['wall_time_max_seconds']
    # Reuse the exact, frozen network/normalization functions, not their main().
    spec = importlib.util.spec_from_file_location('frozen_stage109', SOURCE)
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    OUT.mkdir(exist_ok=True)
    guard = OUT / 'started.json'
    with guard.open('xb') as stream:
        stream.write(source.encode({'stage': 116, 'pid': os.getpid(), 'started_utc': source.now(),
            'execution_kind': 'explicit_interrupted_acquisition_continuation', 'wrapper': binding(pathlib.Path(__file__)),
            'original_started': binding(OLD / 'started.json'), 'original_requests_started': binding(OLD / 'requests_started.jsonl'),
            'source_implementation_sha256': SOURCE_SHA, 'new_requests_planned': len(plan['remaining'])}))
    for folder in ('raw', 'normalized', 'dates'):
        (OUT / folder).mkdir(exist_ok=True)
    source.OUT = OUT
    source.P = dict(protocol)
    # A lost in-flight request may have consumed at most 2 MiB. Reserve the
    # maximum for each rather than pretending no bytes arrived before loss.
    unknown_bytes_upper = len(plan['interrupted']) * protocol['per_response_bytes_max']
    source.P['response_body_bytes_max'] -= unknown_bytes_upper
    source.START = time.monotonic() - original_elapsed
    source.DATES = dates
    original_body_bytes = sum(records[day]['raw_body_bytes'] for day in plan['completed'])
    source.STATE.update(new_get_started=len(started_dates), new_get_finished=len(plan['completed']),
        response_body_bytes=original_body_bytes, reserved_bytes=0, reused_dates=len(reuse),
        consecutive_block_or_network_failures=0, stop_reason=None,
        states={day: record['status'] for day, record in records.items()})
    # Copy only small date records; raw/normalized files stay referenced at their
    # original paths. Original request logs, anchors and responses are immutable.
    provenance = []
    for day in dates:
        if day in records:
            src = OLD / 'dates' / f'{day}.json'
            (OUT / 'dates' / src.name).write_bytes(src.read_bytes())
            provenance.append({'date': day, 'origin': 'original_stage109', 'date_record': binding(src),
                               'status': records[day]['status']})
        elif day in plan['interrupted']:
            row = next(row for row in started_rows if row['date'] == day)
            record = {'date': day, 'status': 'interrupted_unknown', 'reused': False,
                      'reason': 'process_lost_after_request_started_without_persisted_raw_or_final_record',
                      'request_started': row, 'automatic_retry': False,
                      'response_body_bytes_unknown_upper_bound': protocol['per_response_bytes_max']}
            source.atomic_json(OUT / 'dates' / f'{day}.json', record)
            source.STATE['states'][day] = record['status']
            provenance.append({'date': day, 'origin': 'original_stage109_interrupted_unknown', 'status': record['status']})
        else:
            provenance.append({'date': day, 'origin': 'stage116_never_started_continuation'})
    with (OUT / 'source_provenance.jsonl').open('wb') as stream:
        for row in provenance:
            stream.write(source.encode(row) + b'\n')
    recovery_protocol = {'schema': 'stage116_interrupted_source_recovery_v1', 'created_utc': source.now(),
        'original_protocol': binding(PROTOCOL), 'fixed_financial_protocol': binding(LINE / 'outputs/stage110_member_category_protocol/protocol.json'),
        'wrapper': binding(pathlib.Path(__file__)), 'original_started': binding(OLD / 'started.json'),
        'original_requests_started': binding(OLD / 'requests_started.jsonl'), 'original_progress': binding(OLD / 'progress.json'),
        'source_implementation': binding(SOURCE), 'source_provenance': binding(OUT / 'source_provenance.jsonl'),
        'prior_started': len(started_dates), 'prior_finished': len(plan['completed']), 'reuse_count': len(reuse),
        'interrupted_dates': plan['interrupted'], 'interrupted_request_count': len(plan['interrupted']),
        'remaining_never_started_dates': plan['remaining'], 'remaining_get_count': len(plan['remaining']),
        'original_body_bytes_known': original_body_bytes, 'unknown_body_bytes_upper_bound': unknown_bytes_upper,
        'GET_total_max': protocol['new_get_max'], 'body_total_max': protocol['response_body_bytes_max'],
        'wall_origin_utc': original_started['started_utc'], 'wall_total_max_seconds': protocol['wall_time_max_seconds'],
        'unchanged': 'endpoint, dates, no retry, no redirects, concurrency2, 25s deadline, 2MiB per body, 3GiB shared body, 4h original wall; no financial changes',
        'original_evidence_modified': False, 'interrupted_acquisition': True, 'single_uninterrupted_execution_claim': False,
        'implementation_sha256_meaning': 'original_stage109 fetch/normalize/finalize implementation; wrapper separately bound',
        'fit': 0, 'cash': 0, 'sql': 0}
    source.atomic_json(OUT / 'recovery_protocol.json', recovery_protocol)
    for day in plan['remaining']:
        source.TASKS.put(day)
    threads = [threading.Thread(target=source.worker, args=(i,), name=f'recovery-source-worker-{i}') for i in range(2)]
    for thread in threads:
        thread.start()
    print('RECOVERY_STARTED ' + json.dumps(source.progress(), ensure_ascii=False), flush=True)
    last_progress = time.monotonic()
    while any(thread.is_alive() for thread in threads):
        for thread in threads:
            thread.join(timeout=0.5)
        if time.monotonic() - last_progress >= 60:
            print('RECOVERY_PROGRESS ' + json.dumps(source.progress(), ensure_ascii=False), flush=True)
            last_progress = time.monotonic()
    source.progress()
    # Preserve original finalizer output separately, so nobody can mistake its
    # intermediate receipt for the final composite recovery terminal.
    original_atomic_json = source.atomic_json
    def finalizer_atomic(path, value):
        if path.name == 'completion_receipt.json':
            path = path.with_name('base_stage109_completion_receipt.json')
        original_atomic_json(path, value)
    source.atomic_json = finalizer_atomic
    source.finalize()
    source.atomic_json = original_atomic_json
    resumed_requests = [json.loads(row) for row in (OUT / 'requests_started.jsonl').read_bytes().splitlines()]
    assert len(resumed_requests) == len({r['date'] for r in resumed_requests})
    assert not set(r['date'] for r in resumed_requests) & set(started_dates)
    assert len(resumed_requests) == source.STATE['new_get_started'] - len(started_dates)
    assert (OLD / 'requests_started.jsonl').read_bytes() == requests_bytes
    summary = json.loads((OUT / 'summary.json').read_bytes())
    recovery = {'schema': 'stage116_interrupted_source_recovery_v1', 'wrapper': binding(pathlib.Path(__file__)),
        'original_started': binding(OLD / 'started.json'), 'original_requests_started': binding(OLD / 'requests_started.jsonl'),
        'interrupted_dates': plan['interrupted'], 'interrupted_request_count': len(plan['interrupted']),
        'complete_terminal_statuses': len(dates), 'prior_finished': len(plan['completed']),
        'resumed_started': len(resumed_requests), 'resumed_finished': source.STATE['new_get_finished'] - len(plan['completed']),
        'resumed_requests_started': binding(OUT / 'requests_started.jsonl'), 'recovery_protocol': binding(OUT / 'recovery_protocol.json'),
        'source_provenance': binding(OUT / 'source_provenance.jsonl'), 'original_body_bytes_known': original_body_bytes,
        'unknown_body_bytes_upper_bound': unknown_bytes_upper, 'interrupted_acquisition': True,
        'single_uninterrupted_execution_claim': False, 'original_evidence_modified': False,
        'implementation_sha256_meaning': recovery_protocol['implementation_sha256_meaning'],
        'states': summary['counts'], 'fit': 0, 'cash': 0, 'sql': 0}
    source.atomic_json(OUT / 'recovery_receipt.json', recovery)
    composite = dict(summary, execution_stage=116, implementation_sha256=SOURCE_SHA,
        date_manifest_sha256=sha((OUT / 'date_manifest.jsonl').read_bytes()), recovery=recovery,
        recovery_receipt=binding(OUT / 'recovery_receipt.json'), terminal_statuses_complete=True,
        new_response_body_bytes_known=source.STATE['response_body_bytes'], unknown_response_body_bytes_upper_bound=unknown_bytes_upper)
    source.atomic_json(OUT / 'completion_receipt.json', composite)
    print('RECOVERY_COMPLETE ' + json.dumps(composite, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
