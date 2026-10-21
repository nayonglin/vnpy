"""One bounded Stage108-authorized pass over public SHFE source files only."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import queue
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_full_market_long_signal_ai'
OUT = LINE / 'outputs/stage109_member_category_history'
PROTOCOL = LINE / 'outputs/stage108_member_category_history_protocol/protocol.json'
PROTOCOL_SHA = '384195b05855ad1520de8df7988ae2eca2f1ca4f42db8cd3d231a3984ec28253'
Q = ('CJ1', 'CJ2', 'CJ3', 'CJ1_CHG', 'CJ2_CHG', 'CJ3_CHG')
LOCK = threading.Lock()
STOP = threading.Event()
TASKS = queue.Queue()
STATE = {'new_get_started': 0, 'new_get_finished': 0, 'response_body_bytes': 0, 'reserved_bytes': 0,
         'reused_dates': 0, 'consecutive_block_or_network_failures': 0, 'stop_reason': None, 'states': {}, 'last_finished_date': None}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def atomic_json(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(encode(value))
    tmp.replace(path)


def number(row, key):
    if key not in row:
        return {'state': 'missing_key', 'type': 'absent', 'raw': None, 'value': None}
    raw = row[key]
    typ = type(raw).__name__
    if raw is None:
        return {'state': 'null', 'type': typ, 'raw': raw, 'value': None}
    if isinstance(raw, bool):
        return {'state': 'invalid_boolean', 'type': typ, 'raw': raw, 'value': None}
    text = str(raw).strip()
    if not text:
        return {'state': 'empty_string', 'type': typ, 'raw': raw, 'value': None}
    try:
        value = Decimal(text)
        if not value.is_finite():
            status = 'nonfinite'
        elif value != value.to_integral_value():
            status = 'noninteger'
        else:
            value = int(value)
            return {'state': 'true_zero' if value == 0 else 'finite_integer', 'type': typ, 'raw': raw, 'value': value}
    except (InvalidOperation, ValueError, TypeError):
        status = 'invalid_text'
    return {'state': status, 'type': typ, 'raw': raw, 'value': None}


def normalize(day, body, header):
    info = {'date': day, 'parse_state': None, 'category_rows': 0, 'unknown_category_candidates': 0, 'scope_count': 0}
    normalized = {'date': day, 'category_rows': [], 'unknown_category_candidates': [], 'scope_QA': []}
    try:
        parse_body = gzip.decompress(body) if header.get('Content-Encoding', '').lower() == 'gzip' else body
        obj = json.loads(parse_body)
    except Exception as exc:
        info.update(parse_state='not_json', parse_error=type(exc).__name__ + ': ' + str(exc), prefix_hex=body[:24].hex())
        return info, normalized
    if not isinstance(obj, dict) or not isinstance(obj.get('o_cursor'), list) or any(not isinstance(r, dict) for r in obj['o_cursor']):
        info.update(parse_state='unrecognized_schema', top_level_type=type(obj).__name__)
        return info, normalized
    rows = obj['o_cursor']
    fields = sorted({k for row in rows for k in row})
    clocks = {k: v for k, v in obj.items() if k != 'o_cursor'}
    report = obj.get('report_date')
    observed_products = sorted({re.sub(r'\d+$', '', str(r.get('INSTRUMENTID', '')).strip()).lower() for r in rows if re.fullmatch(r'[A-Za-z]+\d{4}', str(r.get('INSTRUMENTID', '')).strip())})
    info.update(parse_state='json_cursor', row_count=len(rows), row_fields=fields, row_schema_sha256=sha(encode(fields)), top_level_keys=list(obj),
                report_metadata=clocks, report_date_state=('absent' if report is None else ('matches' if str(report).replace('-', '') == day else 'mismatch')),
                observed_real_contract_products=observed_products)
    for index, row in enumerate(rows):
        rank = number(row, 'RANK')
        labels = [str(row.get(f'PARTICIPANTABBR{n}', '')).strip() for n in (1, 2, 3)]
        if rank['value'] not in (-1, 0):
            if any('期货公司' in label or '非经纪参与者' in label for label in labels):
                normalized['unknown_category_candidates'].append({'original_row_index': index, 'raw_row': row, 'rank': rank})
            continue
        instrument = str(row.get('INSTRUMENTID', '')).strip()
        scope = 'product_all' if instrument.lower().endswith('all') else ('actual_contract' if re.fullmatch(r'[A-Za-z]+\d{4}', instrument) else 'unknown')
        product = instrument[:-3].lower() if scope == 'product_all' else re.sub(r'\d+$', '', instrument).lower()
        role = 'NFC' if labels[0].startswith('非期货公司') else ('FC' if labels[0].startswith('期货公司') else 'UNKNOWN')
        normalized['category_rows'].append({'date': day, 'original_row_index': index, 'instrument': instrument, 'scope': scope, 'product': product,
            'rank': rank, 'raw_label': labels[0], 'qa_role_only_not_actor_mapping': role, 'label_columns_agree': len(set(labels)) == 1,
            'raw_row': row, 'quantity_states': {key: number(row, key) for key in Q},
            'raw_id_states': {f'PARTICIPANTID{n}': {'present': f'PARTICIPANTID{n}' in row, 'raw': row.get(f'PARTICIPANTID{n}'), 'type': type(row.get(f'PARTICIPANTID{n}')).__name__ if f'PARTICIPANTID{n}' in row else 'absent'} for n in (1, 2, 3)}})
    groups = collections.defaultdict(list)
    for row in normalized['category_rows']:
        groups[row['instrument']].append(row)
    for instrument, group in sorted(groups.items()):
        roles = [r['qa_role_only_not_actor_mapping'] for r in group]
        duplicate = len(roles) - len(set(roles))
        missing = sum(v['value'] is None for r in group for v in r['quantity_states'].values())
        negative = sum(r['quantity_states'][k]['value'] is not None and r['quantity_states'][k]['value'] < 0 for r in group for k in ('CJ1', 'CJ2', 'CJ3'))
        sums = {k: (sum(r['quantity_states'][k]['value'] for r in group) if all(r['quantity_states'][k]['value'] is not None for r in group) else None) for k in Q}
        difference = sums['CJ2'] - sums['CJ3'] if sums['CJ2'] is not None and sums['CJ3'] is not None else None
        nfc = [r for r in group if r['qa_role_only_not_actor_mapping'] == 'NFC']
        normalized['scope_QA'].append({'date': day, 'instrument': instrument, 'scope': group[0]['scope'], 'product': group[0]['product'],
            'category_rows': len(group), 'raw_labels': [r['raw_label'] for r in group], 'duplicate_roles': duplicate, 'missing_invalid_quantities': missing,
            'negative_levels': negative, 'label_columns_disagree': sum(not r['label_columns_agree'] for r in group), 'quantity_sums': sums,
            'buy_sell_difference': difference, 'buy_sell_balanced': difference == 0 if difference is not None else None,
            'numeric_pair_valid': len(group) == 2 and set(roles) == {'FC', 'NFC'} and not duplicate and not missing and not negative and all(r['label_columns_agree'] for r in group) and group[0]['scope'] != 'unknown',
            'nfc_both_true_zero': len(nfc) == 1 and nfc[0]['quantity_states']['CJ2']['state'] == 'true_zero' and nfc[0]['quantity_states']['CJ3']['state'] == 'true_zero',
            'all_listed_months_scope_qualified': False, 'cross_date_definition_continuity_qualified': False})
    qa = normalized['scope_QA']
    info.update(category_rows=len(normalized['category_rows']), unknown_category_candidates=len(normalized['unknown_category_candidates']), scope_count=len(qa),
                category_products=sorted({r['product'] for r in qa}), raw_category_labels=sorted({r['raw_label'] for r in normalized['category_rows']}),
                category_scope_counts=dict(collections.Counter(r['scope'] for r in qa)),
                absent_for_observed_contract_products=sorted(set(observed_products) - {r['product'] for r in qa}),
                missing_invalid_quantities=sum(r['missing_invalid_quantities'] for r in qa), negative_levels=sum(r['negative_levels'] for r in qa),
                duplicate_roles=sum(r['duplicate_roles'] for r in qa), unbalanced_scopes=sum(r['buy_sell_balanced'] is False for r in qa),
                balance_unknown_scopes=sum(r['buy_sell_balanced'] is None for r in qa), valid_numeric_pairs=sum(r['numeric_pair_valid'] for r in qa),
                nfc_both_true_zero_scopes=sum(r['nfc_both_true_zero'] for r in qa))
    return info, normalized


def save_normalized(day, body, headers):
    audit, normalized = normalize(day, body, headers)
    b = gzip.compress(encode(normalized), compresslevel=6, mtime=0)
    path = OUT / 'normalized' / f'{day}.json.gz'
    path.write_bytes(b)
    audit.update(normalized_path=str(path), normalized_gzip_bytes=len(b), normalized_gzip_sha256=sha(b))
    return audit


def progress():
    with LOCK:
        p = {k: v for k, v in STATE.items() if k != 'states'}
        p['state_counts'] = dict(collections.Counter(STATE['states'].values()))
    p.update(updated_utc=now(), elapsed_seconds=round(time.monotonic() - START, 2), pid=os.getpid(), protocol_sha256=PROTOCOL_SHA)
    atomic_json(OUT / 'progress.json', p)
    return p


def fetch(day, worker_id, session):
    start = time.monotonic()
    record = {'date': day, 'worker': worker_id, 'url': P['url_template'].format(date=day), 'started_utc': now(), 'attempt': 1,
              'automatic_retry': False, 'redirect_following': False, 'timeout_seconds': 25, 'reused': False}
    with LOCK:
        if STOP.is_set() or time.monotonic() - START >= P['wall_time_max_seconds']:
            return False
        if STATE['new_get_started'] >= P['new_get_max']:
            raise AssertionError('GET budget exceeded')
        STATE['new_get_started'] += 1
        STATE['states'][day] = 'request_started'
        with (OUT / 'requests_started.jsonl').open('ab') as stream:
            stream.write(encode(record) + b'\n')
            stream.flush()
    body = bytearray()
    response = None
    network_failure = False
    try:
        remaining = min(25.0, P['wall_time_max_seconds'] - (time.monotonic() - START))
        response = session.get(record['url'], stream=True, timeout=(remaining, remaining), allow_redirects=False)
        record.update(http_status=response.status_code, response_url=response.url, headers=dict(response.headers))
        while True:
            remaining = min(25.0 - (time.monotonic() - start), P['wall_time_max_seconds'] - (time.monotonic() - START))
            if remaining <= 0:
                raise requests.exceptions.ReadTimeout('fixed total request/wall deadline reached')
            try:
                response.raw._fp.fp.raw._sock.settimeout(remaining)
            except AttributeError:
                pass
            individual_room = P['per_response_bytes_max'] - len(body)
            if individual_room <= 0:
                record.update(truncated=True, stop_reason='per_response_byte_cap')
                break
            with LOCK:
                global_room = P['response_body_bytes_max'] - STATE['response_body_bytes'] - STATE['reserved_bytes']
                chunk_cap = min(65536, individual_room, global_room)
                if chunk_cap > 0:
                    STATE['reserved_bytes'] += chunk_cap
            if chunk_cap <= 0:
                with LOCK:
                    STATE['stop_reason'] = 'global_body_budget_exhausted'
                STOP.set()
                record.update(truncated=True, stop_reason='global_body_budget_exhausted')
                break
            data = b''
            try:
                data = response.raw.read(chunk_cap, decode_content=False)
            finally:
                with LOCK:
                    STATE['reserved_bytes'] -= chunk_cap
                    STATE['response_body_bytes'] += len(data)
                    assert STATE['response_body_bytes'] <= P['response_body_bytes_max']
            if not data:
                record['truncated'] = False
                break
            body.extend(data)
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc), truncated=bool(body))
        network_failure = True
    finally:
        if response is not None:
            response.close()
    data = bytes(body)
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    path = OUT / 'raw' / f'pm{day}.response.gz'
    path.write_bytes(compressed)
    record.update(raw_body_bytes=len(data), raw_body_sha256=sha(data), archive_path=str(path), archive_bytes=len(compressed), archive_sha256=sha(compressed),
                  elapsed_seconds=round(time.monotonic() - start, 3), finished_utc=now())
    record.update(save_normalized(day, data, record.get('headers', {})))
    record['status'] = ('network_error' if network_failure else ('truncated' if record.get('truncated') else ('http_200' if record.get('http_status') == 200 else 'http_non200')))
    atomic_json(OUT / 'dates' / f'{day}.json', record)
    bad = network_failure or record.get('http_status') in (403, 429)
    with LOCK:
        STATE['new_get_finished'] += 1
        STATE['states'][day] = record['status']
        STATE['last_finished_date'] = day
        STATE['consecutive_block_or_network_failures'] = STATE['consecutive_block_or_network_failures'] + 1 if bad else 0
        if STATE['consecutive_block_or_network_failures'] >= 5:
            STATE['stop_reason'] = 'five_consecutive_block_or_network_failures'
            STOP.set()
    return True


def worker(worker_id):
    session = requests.Session()
    session.trust_env = False  # No implicit credentials, netrc, or proxy environment.
    session.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,*/*', 'Accept-Encoding': 'identity'})
    adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=Retry(total=0, connect=0, read=0, redirect=0, status=0))
    session.mount('https://', adapter)
    last_finish = None
    try:
        while not STOP.is_set():
            if time.monotonic() - START >= P['wall_time_max_seconds']:
                with LOCK:
                    STATE['stop_reason'] = 'wall_time_budget_exhausted'
                STOP.set()
                break
            if last_finish is not None:
                time.sleep(max(0.0, 0.15 - (time.monotonic() - last_finish)))
            try:
                day = TASKS.get_nowait()
            except queue.Empty:
                break
            try:
                if not fetch(day, worker_id, session):
                    break
            finally:
                TASKS.task_done()
            last_finish = time.monotonic()
    finally:
        session.close()


def finalize():
    daily, month, support = [], collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    total = collections.Counter()
    for day in DATES:
        path = OUT / 'dates' / f'{day}.json'
        if path.exists():
            record = json.loads(path.read_bytes())
        else:
            record = {'date': day, 'status': 'not_requested', 'reason': STATE['stop_reason'] or 'not_started', 'reused': False}
            atomic_json(path, record)
        daily.append(record)
        month[day[:6]][record['status']] += 1
        total[record['status']] += 1
        for k in ('category_rows', 'scope_count', 'unknown_category_candidates', 'missing_invalid_quantities', 'negative_levels', 'duplicate_roles', 'unbalanced_scopes', 'balance_unknown_scopes', 'valid_numeric_pairs', 'nfc_both_true_zero_scopes'):
            total[k] += record.get(k, 0)
        if record.get('normalized_path'):
            normalized = json.loads(gzip.decompress(Path(record['normalized_path']).read_bytes()))
            for item in normalized['scope_QA']:
                c = support[(day[:6], item['product'], item['scope'])]
                c['supported_dates'] += 1
                c['category_rows'] += item['category_rows']
                for k in ('missing_invalid_quantities', 'negative_levels', 'duplicate_roles', 'label_columns_disagree'):
                    c[k] += item[k]
                c['nfc_both_true_zero'] += item['nfc_both_true_zero']
                c['unbalanced_scopes'] += item['buy_sell_balanced'] is False
    with (OUT / 'date_manifest.jsonl').open('wb') as stream:
        for record in daily:
            stream.write(encode(record) + b'\n')
    atomic_json(OUT / 'month_availability.json', dict(month))
    with (OUT / 'month_product_scope_support.csv').open('w', newline='') as stream:
        fields = ['month', 'product', 'scope', 'supported_dates', 'category_rows', 'missing_invalid_quantities', 'negative_levels', 'duplicate_roles', 'label_columns_disagree', 'nfc_both_true_zero', 'unbalanced_scopes']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key, counts in sorted(support.items()):
            writer.writerow(dict(zip(('month', 'product', 'scope'), key), **counts))
    summary = {'stage': 109, 'protocol_sha256': PROTOCOL_SHA, 'finished_utc': now(), 'date_count': len(DATES), 'new_get_started': STATE['new_get_started'],
               'new_get_finished': STATE['new_get_finished'], 'new_response_body_bytes': STATE['response_body_bytes'], 'reused_dates': 13,
               'stop_reason': STATE['stop_reason'], 'elapsed_seconds': round(time.monotonic() - START, 3), 'counts': dict(total),
               'fit': 0, 'cash': 0, 'sql': 0, 'financial_scalar_created': False, 'first_publication_qualified': False,
               'cross_date_definition_continuity_qualified': False, 'all_listed_months_scope_qualified': False}
    atomic_json(OUT / 'summary.json', summary)
    atomic_json(OUT / 'completion_receipt.json', dict(summary, implementation_sha256=sha(Path(__file__).read_bytes()), date_manifest_sha256=sha((OUT / 'date_manifest.jsonl').read_bytes())))
    print('COMPLETE ' + json.dumps(summary, ensure_ascii=False), flush=True)


def main():
    global START, P, DATES
    raw = PROTOCOL.read_bytes()
    assert sha(raw) == PROTOCOL_SHA
    P = json.loads(raw)
    source = Path(P['source_dates']['path']).read_bytes()
    assert len(source) == P['source_dates']['size'] and sha(source) == P['source_dates']['sha256']
    DATES = json.loads(source)['dates']
    assert len(DATES) == len(set(DATES)) == 3588 and DATES == sorted(DATES)
    assert set(P['new_get_dates']) | {x['date'] for x in P['reuse']} == set(DATES)
    assert len(P['new_get_dates']) == 3575 and not P['automatic_retry'] and not P['redirect_following']
    for bound in P['bound_inputs']:
        b = Path(bound['path']).read_bytes()
        assert len(b) == bound['size'] and sha(b) == bound['sha256']
    OUT.mkdir(exist_ok=True)
    assert not (OUT / 'started.json').exists(), 'one pass only: prior start anchor exists'
    for name in ('raw', 'dates', 'normalized'):
        (OUT / name).mkdir(exist_ok=True)
    START = time.monotonic()
    atomic_json(OUT / 'started.json', {'stage': 109, 'started_utc': now(), 'pid': os.getpid(), 'protocol_sha256': PROTOCOL_SHA,
        'source_dates_sha256': P['source_dates']['sha256'], 'implementation_sha256': sha(Path(__file__).read_bytes()),
        'new_date_count': 3575, 'reuse_count': 13, 'execution_kind': 'foreground_pollable_exec_session', 'automatic_retry': False})
    print('STARTED ' + (OUT / 'started.json').read_text(), flush=True)
    # Old bodies are read and referenced once; neither copied nor downloaded.
    for item in P['reuse']:
        body = Path(item['path']).read_bytes()
        assert len(body) == item['size'] and sha(body) == item['sha256']
        record = {'date': item['date'], 'status': 'reused_stage104_106', 'reused': True, 'source_path': item['path'],
                  'raw_body_bytes': len(body), 'raw_body_sha256': item['sha256']}
        record.update(save_normalized(item['date'], body, {}))
        atomic_json(OUT / 'dates' / f"{item['date']}.json", record)
        STATE['states'][item['date']] = record['status']
        STATE['reused_dates'] += 1
    for day in P['new_get_dates']:
        TASKS.put(day)
    threads = [threading.Thread(target=worker, args=(i,), name=f'source-worker-{i}') for i in range(2)]
    for thread in threads:
        thread.start()
    progress()
    last_progress = time.monotonic()
    while any(thread.is_alive() for thread in threads):
        for thread in threads:
            thread.join(timeout=0.5)
        if time.monotonic() - last_progress >= 60:
            print('PROGRESS ' + json.dumps(progress(), ensure_ascii=False), flush=True)
            last_progress = time.monotonic()
    progress()
    finalize()


if __name__ == '__main__':
    main()
