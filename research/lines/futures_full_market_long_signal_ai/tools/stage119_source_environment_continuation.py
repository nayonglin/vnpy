"""Correct sandbox DNS environment; acquire only 674 never-attempted dates.

Keep Stage109 and Stage116 evidence immutable, including six DNS failures and
two interrupted unknown requests. No retries or financial parameter changes.
"""
from __future__ import annotations
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
PREV = LINE / 'outputs/stage116_source_recovery'
OUT = LINE / 'outputs/stage119_source_environment_continuation'
SOURCE = pathlib.Path(__file__).with_name('stage109_member_category_history.py')
SOURCE_SHA = '0f41c2cc36e6e404b45020867db9aba0136976ceae63bdda9fc9dc47a1d5e212'
PROTOCOL = LINE / 'outputs/stage108_member_category_history_protocol/protocol.json'
PROTOCOL_SHA = '384195b05855ad1520de8df7988ae2eca2f1ca4f42db8cd3d231a3984ec28253'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}


def require_dead(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return
    raise AssertionError(f'prior source PID {pid} exists; refuse duplication')


def main():
    assert sha(SOURCE.read_bytes()) == SOURCE_SHA
    assert sha(PROTOCOL.read_bytes()) == PROTOCOL_SHA
    protocol = json.loads(PROTOCOL.read_bytes())
    date_bound = protocol['source_dates']
    date_bytes = pathlib.Path(date_bound['path']).read_bytes()
    assert len(date_bytes) == date_bound['size'] and sha(date_bytes) == date_bound['sha256']
    dates = json.loads(date_bytes)['dates']
    original_anchor = json.loads((OLD / 'started.json').read_bytes())
    prior_anchor = json.loads((PREV / 'started.json').read_bytes())
    require_dead(original_anchor['pid'])
    require_dead(prior_anchor['pid'])
    old_log_bytes = (OLD / 'requests_started.jsonl').read_bytes()
    first_resume_log_bytes = (PREV / 'requests_started.jsonl').read_bytes()
    prior_terminal_bytes = (PREV / 'completion_receipt.json').read_bytes()
    old_requests = [json.loads(row) for row in old_log_bytes.splitlines()]
    first_resume_requests = [json.loads(row) for row in first_resume_log_bytes.splitlines()]
    prior_terminal = json.loads(prior_terminal_bytes)
    assert prior_terminal['new_get_started'] == 2901 and prior_terminal['new_get_finished'] == 2899
    assert prior_terminal['stop_reason'] == 'five_consecutive_block_or_network_failures'
    assert len(old_requests) == 2895 and len(first_resume_requests) == 6
    prior_records = {p.stem: json.loads(p.read_bytes()) for p in (PREV / 'dates').glob('*.json')}
    assert set(prior_records) == set(dates) and len(dates) == 3588
    interrupted = sorted(day for day, r in prior_records.items() if r['status'] == 'interrupted_unknown')
    errors = sorted(day for day, r in prior_records.items() if r['status'] == 'network_error')
    remaining = [day for day in dates if prior_records[day]['status'] == 'not_requested']
    assert interrupted == ['20231213', '20231214']
    assert errors == ['20231215', '20231218', '20231219', '20231220', '20231221', '20231222']
    assert len(remaining) == 674
    all_attempted = {r['date'] for r in old_requests + first_resume_requests}
    assert len(all_attempted) == 2901 and not all_attempted & set(remaining)
    for day in errors:
        record = prior_records[day]
        assert record['raw_body_bytes'] == 0 and record['error_type'] == 'ConnectionError'
        assert '[Errno 8]' in record['error'] and 'NameResolutionError' in record['error']
    elapsed = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(original_anchor['started_utc'])).total_seconds()
    assert 0 < elapsed < protocol['wall_time_max_seconds']
    spec = importlib.util.spec_from_file_location('frozen_stage109', SOURCE)
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    OUT.mkdir(exist_ok=True)
    with (OUT / 'started.json').open('xb') as stream:
        stream.write(source.encode({'stage': 119, 'pid': os.getpid(), 'started_utc': source.now(),
            'execution_kind': 'root_authorized_sandbox_dns_environment_correction_never_attempted_only',
            'wrapper': binding(pathlib.Path(__file__)), 'new_requests_planned': len(remaining),
            'prior_completion': binding(PREV / 'completion_receipt.json'),
            'automatic_retry': False, 'root_authorization': 'continue only 674 neverstarted using previously working network environment; preserve six DNS failures and two unknowns'}))
    for folder in ('raw', 'normalized', 'dates'):
        (OUT / folder).mkdir(exist_ok=True)
    # Final resumed log includes all six failed attempts, then only new dates.
    (OUT / 'requests_started.jsonl').write_bytes(first_resume_log_bytes)
    source.OUT = OUT
    source.P = dict(protocol)
    unknown_bytes_upper = 2 * protocol['per_response_bytes_max']
    source.P['response_body_bytes_max'] -= unknown_bytes_upper
    source.START = time.monotonic() - elapsed
    source.DATES = dates
    source.STATE.update(new_get_started=2901, new_get_finished=2899,
        response_body_bytes=prior_terminal['new_response_body_bytes'], reserved_bytes=0,
        reused_dates=13, consecutive_block_or_network_failures=0, stop_reason=None,
        states={day: r['status'] for day, r in prior_records.items() if day not in remaining})
    for day, record in prior_records.items():
        if day not in remaining:
            (OUT / 'dates' / f'{day}.json').write_bytes((PREV / 'dates' / f'{day}.json').read_bytes())
    original_provenance = [json.loads(row) for row in (PREV / 'source_provenance.jsonl').read_bytes().splitlines()]
    with (OUT / 'source_provenance.jsonl').open('wb') as stream:
        for row in original_provenance:
            day = row['date']
            if day in errors:
                row = dict(row, origin='stage116_sandbox_DNS_failure_no_retry', date_record=binding(PREV / 'dates' / f'{day}.json'))
            elif day in remaining:
                row = dict(row, origin='stage119_environment_corrected_never_attempted_continuation')
            stream.write(source.encode(row) + b'\n')
    extra_segments = [{'stage': 116, 'wrapper': prior_anchor['wrapper'],
        'started': binding(PREV / 'started.json'), 'completion': binding(PREV / 'completion_receipt.json'),
        'recovery_receipt': binding(PREV / 'recovery_receipt.json'),
        'requests_started': binding(PREV / 'requests_started.jsonl'),
        'attempted_dates': errors, 'finished': 6, 'network_errors': 6, 'body_bytes': 0,
        'environment_error': 'sandbox DNS Errno8', 'retried': False}]
    recovery_protocol = {'schema': 'stage116_interrupted_source_recovery_v1', 'created_utc': source.now(),
        'original_protocol': binding(PROTOCOL), 'fixed_financial_protocol': binding(LINE / 'outputs/stage110_member_category_protocol/protocol.json'),
        'wrapper': binding(pathlib.Path(__file__)), 'original_started': binding(OLD / 'started.json'),
        'original_requests_started': binding(OLD / 'requests_started.jsonl'),
        'source_implementation': binding(SOURCE), 'source_provenance': binding(OUT / 'source_provenance.jsonl'),
        'extra_execution_segments': extra_segments, 'requests_started_prefix': binding(PREV / 'requests_started.jsonl'),
        'interrupted_dates': interrupted, 'interrupted_request_count': 2,
        'prior_started': 2895, 'prior_finished': 2893, 'reuse_count': 13,
        'remaining_never_started_dates': remaining, 'remaining_get_count': len(remaining),
        'prior_resumed_DNS_failure_dates_no_retry': errors,
        'original_body_bytes_known': prior_terminal['new_response_body_bytes'], 'unknown_body_bytes_upper_bound': unknown_bytes_upper,
        'GET_total_max': 3575, 'body_total_max': protocol['response_body_bytes_max'],
        'wall_origin_utc': original_anchor['started_utc'], 'wall_total_max_seconds': protocol['wall_time_max_seconds'],
        'environment_correction': 'root explicitly authorized removal of sandbox DNS restriction; exchange network failures/HTTP blocks are not bypassed',
        'unchanged': 'endpoint, dates, no retries, no redirects, concurrency2, 25s deadline, 2MiB per body, shared3GiB, original4h wall, all science and financial parameters',
        'original_evidence_modified': False, 'interrupted_acquisition': True, 'single_uninterrupted_execution_claim': False,
        'implementation_sha256_meaning': 'original_stage109 fetch/normalize/finalize implementation; all wrappers separately bound',
        'fit': 0, 'cash': 0, 'sql': 0}
    source.atomic_json(OUT / 'recovery_protocol.json', recovery_protocol)
    for day in remaining:
        source.TASKS.put(day)
    threads = [threading.Thread(target=source.worker, args=(i,), name=f'authorized-source-worker-{i}') for i in range(2)]
    for thread in threads:
        thread.start()
    print('CONTINUATION_STARTED ' + json.dumps(source.progress(), ensure_ascii=False), flush=True)
    last_progress = time.monotonic()
    while any(thread.is_alive() for thread in threads):
        for thread in threads:
            thread.join(timeout=0.5)
        if time.monotonic() - last_progress >= 60:
            print('CONTINUATION_PROGRESS ' + json.dumps(source.progress(), ensure_ascii=False), flush=True)
            last_progress = time.monotonic()
    source.progress()
    original_atomic = source.atomic_json
    def finalizer_atomic(path, value):
        if path.name == 'completion_receipt.json':
            path = path.with_name('base_stage109_completion_receipt.json')
        original_atomic(path, value)
    source.atomic_json = finalizer_atomic
    source.finalize()
    source.atomic_json = original_atomic
    resumed_bytes = (OUT / 'requests_started.jsonl').read_bytes()
    assert resumed_bytes.startswith(first_resume_log_bytes)
    resumed = [json.loads(row) for row in resumed_bytes.splitlines()]
    assert len(resumed) == len({r['date'] for r in resumed})
    assert not set(r['date'] for r in resumed) & set(r['date'] for r in old_requests)
    assert len(resumed) == source.STATE['new_get_started'] - 2895
    assert (OLD / 'requests_started.jsonl').read_bytes() == old_log_bytes
    assert (PREV / 'requests_started.jsonl').read_bytes() == first_resume_log_bytes
    assert (PREV / 'completion_receipt.json').read_bytes() == prior_terminal_bytes
    summary = json.loads((OUT / 'summary.json').read_bytes())
    recovery = {'schema': 'stage116_interrupted_source_recovery_v1', 'wrapper': binding(pathlib.Path(__file__)),
        'original_started': binding(OLD / 'started.json'), 'original_requests_started': binding(OLD / 'requests_started.jsonl'),
        'interrupted_dates': interrupted, 'interrupted_request_count': 2, 'complete_terminal_statuses': len(dates),
        'prior_finished': 2893, 'resumed_started': len(resumed), 'resumed_finished': source.STATE['new_get_finished'] - 2893,
        'resumed_requests_started': binding(OUT / 'requests_started.jsonl'), 'recovery_protocol': binding(OUT / 'recovery_protocol.json'),
        'source_provenance': binding(OUT / 'source_provenance.jsonl'), 'extra_execution_segments': extra_segments,
        'requests_started_prefix': binding(PREV / 'requests_started.jsonl'),
        'original_body_bytes_known': prior_terminal['new_response_body_bytes'], 'unknown_body_bytes_upper_bound': unknown_bytes_upper,
        'interrupted_acquisition': True, 'single_uninterrupted_execution_claim': False, 'original_evidence_modified': False,
        'implementation_sha256_meaning': recovery_protocol['implementation_sha256_meaning'],
        'environment_correction': recovery_protocol['environment_correction'], 'states': summary['counts'], 'fit': 0, 'cash': 0, 'sql': 0}
    source.atomic_json(OUT / 'recovery_receipt.json', recovery)
    composite = dict(summary, execution_stage=119, implementation_sha256=SOURCE_SHA,
        date_manifest_sha256=sha((OUT / 'date_manifest.jsonl').read_bytes()), recovery=recovery,
        recovery_receipt=binding(OUT / 'recovery_receipt.json'), terminal_statuses_complete=True,
        new_response_body_bytes_known=source.STATE['response_body_bytes'], unknown_response_body_bytes_upper_bound=unknown_bytes_upper)
    source.atomic_json(OUT / 'completion_receipt.json', composite)
    print('CONTINUATION_COMPLETE ' + json.dumps(composite, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
