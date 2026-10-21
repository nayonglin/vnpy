"""Frozen161 source-only member distribution and complete identity projection.

Import has no I/O. The root alone starts one actual CLI run in a fresh directory.
No prices, labels, outcomes, model, cash, SQL, or network interfaces are used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import traceback

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage161_member_distribution_source_protocol/protocol.json'
PROTOCOL_SHA = 'ce6329b0f806e69d62d34a894b3738df2a65fdcf557c873bffb37392208b73ca'
CLARIFIER = PROTOCOL.with_name('implementation_clarifier.json')
CLARIFIER_SHA = '9e94d0e977f4ae56ac3329a5db9e2a23b9dea5b71e8daf99482cdd6573ec439a'
VERSION = 'stage162_exact_visible_member_distribution_v1'
MOTHER_ID = ('sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch')
ACTION_ID = MOTHER_ID + ('action_sequence_index', 'action_id', 'actual_epoch',
                         'mother_sequence_index', 'mother_event_id', 'anchor_epoch')
SIDE_FIELDS = ('sum', 'sumsq', 'H', 'named_count', 'empty_slots', 'absent_rank_count',
               'true_zero', 'unidentified_true_zero', 'reported_999', 'reported_999_count',
               'reported_999_raw_json', 'total_match', 'status', 'reasons', 'vector_json', 'vector_sha256')
SCOPE_FIELDS = ('scope_id', 'source_index', 'source_date', 'raw_instrument', 'epoch', 'product_id',
                'exchange', 'mapping_state', 'scope_status', 'scalar_primary', 'definition_version') + tuple(
                    side + '_' + field for side in ('long', 'short') for field in SIDE_FIELDS)
PROJECT_FIELDS = ('projected_epoch', 'v_date', 'v_index', 'source_day_status', 'scope_id',
                  'scope_status', 'projection_status', 'scalar_primary', 'missing', 'definition_version')
DAY_FIELDS = ('source_index', 'source_date', 'original_status', 'source_day_status', 'raw_path',
              'original_archive_bytes', 'original_archive_sha256', 'current_archive_bytes',
              'current_archive_sha256', 'archive_hash_verified', 'original_body_bytes',
              'original_body_sha256', 'current_body_bytes', 'current_body_sha256', 'body_hash_verified',
              'parse_state', 'report_date_state', 'report_metadata_json', 'raw_rows', 'scopes',
              'exact_mapped_scopes', 'scope_states_json', 'mapping_states_json')
KNOWN_STATUSES = {'http_200', 'reused_stage104_106'}
MISSING = object()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def binding(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=sha(data))


def verify(binding_value):
    got = binding(binding_value['path'])
    if any(got[k] != binding_value[k] for k in ('bytes', 'sha256')):
        raise ValueError('input_binding_mismatch ' + binding_value['path'])
    return got


def build_epoch_index(rows):
    result = defaultdict(list)
    seen = set()
    for row in rows:
        epoch, product_id = row['epoch'], row['product_id']
        exchange, code, month = epoch.split('.')
        if epoch in seen or product_id != exchange + '.' + code or not re.fullmatch(r'\d{6}', month):
            raise ValueError('invalid_or_duplicate_epoch_directory_identity')
        seen.add(epoch)
        suffix = 'F' if code.endswith('_F') else ''
        raw_code = code[:-2] if suffix else code
        key = raw_code.upper() + month[2:] + suffix
        result[key].append(dict(epoch=epoch, product_id=product_id, exchange=exchange))
    return dict(result)


def resolve_instrument(instrument, index):
    raw = str(instrument).strip()
    base = dict(epoch='', product_id='', exchange='')
    if re.fullmatch(r'[A-Za-z]+all', raw, re.IGNORECASE):
        return dict(base, mapping_state='aggregate_all_excluded')
    if not re.fullmatch(r'[A-Za-z]+\d{4}F?', raw, re.IGNORECASE):
        return dict(base, mapping_state='unrecognized_instrument')
    values = index.get(raw.upper(), [])
    if len(values) == 1:
        return dict(values[0], mapping_state='exact_epoch')
    return dict(base, mapping_state='ambiguous_epoch' if values else 'unmapped_instrument')


def quantity(raw):
    """Strict finite integer equivalence, keeping missing distinct from zero."""
    if raw is MISSING or raw is None:
        return 'missing_quantity', None
    if isinstance(raw, str):
        text = raw.strip()
        if text in ('', '-'):
            return 'missing_quantity', None
        if not re.fullmatch(r'[+-]?\d+(?:\.0+)?', text):
            return 'invalid_quantity', None
        value = int(text.split('.')[0])
    elif isinstance(raw, bool):
        return 'invalid_quantity', None
    elif isinstance(raw, int):
        value = raw
    elif isinstance(raw, float) and math.isfinite(raw) and raw.is_integer():
        value = int(raw)
    else:
        return 'invalid_quantity', None
    return ('negative_quantity', value) if value < 0 else ('valid', value)


def raw_repr(raw):
    if raw is MISSING:
        return dict(type='missing_key', repr='<missing>')
    return dict(type=type(raw).__name__, repr=repr(raw))


def text_identity(raw):
    return '' if raw is None else str(raw).strip()


def normalize_side(entries, column, common_reasons):
    vector, totals, reasons = [], [], set(common_reasons)
    identities, ranks = set(), set()
    for source_row, row, rank in entries:
        if rank == 999:
            raw = row.get('CJ' + column, MISSING)
            state, value = quantity(raw)
            totals.append(dict(source_row=source_row, qty_state=state,
                               qty=value if state == 'valid' else None, raw=raw_repr(raw)))
            continue
        if not 1 <= rank <= 20:
            continue
        ranks.add(rank)
        member_id = text_identity(row.get('PARTICIPANTID' + column))
        member_name = text_identity(row.get('PARTICIPANTABBR' + column))
        identity = ('id:' + member_id) if member_id else ('name:' + member_name if member_name else '')
        raw = row.get('CJ' + column, MISSING)
        state, value = quantity(raw)
        if not identity and state == 'missing_quantity':
            state, value = 'empty_slot', None
        elif not identity and state == 'valid':
            if value == 0:
                state = 'unidentified_true_zero'
            else:
                state, value = 'missing_identity', None
                reasons.add(state)
        elif state != 'valid':
            reasons.add(state)
            value = None
        if identity:
            if identity in identities:
                reasons.add('duplicate_side_identity')
            identities.add(identity)
        vector.append(dict(source_row=source_row, rank=rank, member_id=member_id,
                           member_name=member_name, qty_state=state, qty=value, raw=raw_repr(raw)))
    named = [v['qty'] for v in vector if v['qty_state'] == 'valid']
    total, sumsq = sum(named), sum(q*q for q in named)
    diagnostic_H = sumsq/(total*total) if total > 0 and not reasons else None
    reported, match = None, None
    if len(totals) > 1:
        reasons.add('duplicate_999')
    elif totals:
        reported = totals[0]['qty']
        if totals[0]['qty_state'] != 'valid':
            reasons.add('invalid_total_quantity')
        else:
            match = total == reported
            if not match:
                reasons.add('total_mismatch')
    if total <= 0:
        reasons.add('nonpositive_visible_total')
    status = 'unknown' if reasons else ('verified' if totals else 'total_unverified')
    # Quantity errors cannot yield a complete diagnostic H; absent999 alone can.
    if reasons - {'total_mismatch', 'invalid_total_quantity', 'duplicate_999'}:
        diagnostic_H = None
    vector_json = canonical(vector)
    return dict(sum=total, sumsq=sumsq, H=diagnostic_H, named_count=len(named),
                empty_slots=sum(v['qty_state'] == 'empty_slot' for v in vector),
                absent_rank_count=20-len(ranks), true_zero=sum(q == 0 for q in named),
                unidentified_true_zero=sum(v['qty_state'] == 'unidentified_true_zero' for v in vector),
                reported_999=reported, reported_999_count=len(totals), reported_999_raw_json=canonical(totals),
                total_match=match, status=status, reasons=sorted(reasons),
                vector_json=vector_json, vector_sha256=sha(vector_json.encode()))


def normalize_scope(rows, source_date, instrument, epoch_index):
    entries, common_reasons, seen_ranks = [], set(), set()
    for local_index, item in enumerate(rows):
        source_row, row = item if isinstance(item, tuple) else (local_index, item)
        rank_state, rank = quantity(row.get('RANK', MISSING))
        if rank_state not in ('valid', 'negative_quantity') or rank is None:
            common_reasons.add('invalid_rank')
            continue
        if rank in (-1, 0):
            continue
        if rank not in range(1, 21) and rank != 999:
            common_reasons.add('unexpected_rank')
            continue
        if 1 <= rank <= 20:
            if rank in seen_ranks:
                common_reasons.add('duplicate_rank')
            seen_ranks.add(rank)
        entries.append((source_row, row, rank))
    sides = {name: normalize_side(entries, col, common_reasons) for name, col in [('long', '2'), ('short', '3')]}
    mapped = resolve_instrument(instrument, epoch_index)
    if mapped['mapping_state'] == 'aggregate_all_excluded':
        status = 'aggregate_all_excluded'
    elif mapped['mapping_state'] != 'exact_epoch' or any(s['status'] == 'unknown' for s in sides.values()):
        status = 'unknown'
    elif any(s['status'] == 'total_unverified' for s in sides.values()):
        status = 'total_unverified'
    else:
        status = 'verified'
    result = dict(scope_id=source_date.replace('-', '') + '|' + str(instrument).strip(), source_date=source_date,
                  raw_instrument=str(instrument).strip(), **mapped, scope_status=status,
                  scalar_primary=(sides['long']['H']-sides['short']['H']) if status == 'verified' else None,
                  definition_version=VERSION)
    result.update({name+'_'+key: value for name, side in sides.items() for key, value in side.items()})
    return result


def read_verified_source(entry):
    """One file read: verify compressed archive and original HTTP body, then parse."""
    compressed = bool(entry.get('archive_path'))
    path = Path(entry['archive_path'] if compressed else entry['source_path'])
    data = path.read_bytes()
    audit = dict(raw_path=str(path), original_archive_bytes=entry.get('archive_bytes'),
                 original_archive_sha256=entry.get('archive_sha256'), current_archive_bytes=len(data),
                 current_archive_sha256=sha(data), archive_hash_verified=False,
                 original_body_bytes=entry['raw_body_bytes'], original_body_sha256=entry['raw_body_sha256'])
    if compressed:
        if len(data) != entry['archive_bytes'] or audit['current_archive_sha256'] != entry['archive_sha256']:
            raise ValueError('archive_identity_mismatch ' + str(path))
        audit['archive_hash_verified'] = True
        body = gzip.decompress(data)
    else:
        body = data
    audit.update(current_body_bytes=len(body), current_body_sha256=sha(body))
    if len(body) != entry['raw_body_bytes'] or audit['current_body_sha256'] != entry['raw_body_sha256']:
        raise ValueError('body_identity_mismatch ' + str(path))
    audit['body_hash_verified'] = True
    parse_body = gzip.decompress(body) if entry.get('headers', {}).get('Content-Encoding', '').lower() == 'gzip' else body
    try:
        obj = json.loads(parse_body)
    except (ValueError, UnicodeError):
        audit['parse_state'] = 'not_json'
        return None, audit
    if not isinstance(obj, dict) or not isinstance(obj.get('o_cursor'), list) or any(not isinstance(r, dict) for r in obj['o_cursor']):
        audit['parse_state'] = 'unrecognized_schema'
        return None, audit
    audit['parse_state'] = 'json_cursor'
    return obj, audit


def project_identity(row, epoch_field, calendar, day_states, scope_lookup):
    result = dict(row)
    u = int(row['u_index'])
    if u < 0 or u >= len(calendar) or row['u_date'] != calendar[u]:
        raise ValueError('original_u_identity_calendar_mismatch')
    epoch = row[epoch_field]
    v = u-1 if u > 0 else None
    v_date = calendar[v] if v is not None else ''
    day_status = day_states.get(v_date, 'outside_accepted_source_dates') if v_date else 'no_predecessor_session'
    scope = scope_lookup.get((v_date, epoch)) if v_date and epoch else None
    if not epoch:
        status = 'no_reference_epoch'
    elif v is None:
        status = 'no_predecessor_session'
    elif day_status not in KNOWN_STATUSES:
        status = 'source_day_unavailable'
    elif scope is None:
        status = 'exact_scope_not_disclosed'
    elif scope['scope_status'] != 'verified':
        status = 'scope_' + scope['scope_status']
    else:
        status = 'observed'
    result.update(projected_epoch=epoch, v_date=v_date, v_index=v, source_day_status=day_status,
                  scope_id=scope['scope_id'] if scope else '', scope_status=scope['scope_status'] if scope else '',
                  projection_status=status, scalar_primary=scope['scalar_primary'] if status == 'observed' else None,
                  missing=status != 'observed', definition_version=VERSION)
    return result


def identity_rows(path, fields):
    """Decode CSV but only select fixed identity cells; no outcome value is used."""
    with gzip.open(path, 'rt', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader)
        indices = [header.index(field) for field in fields]
        for cells in reader:
            yield {field: cells[index] for field, index in zip(fields, indices)}


def prepare_output(output):
    Path(output).mkdir(parents=True, exist_ok=False)


def csv_writer(path, fields):
    stream = gzip.open(path, 'wt', newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='raise')
    writer.writeheader()
    return stream, writer


def serial_row(row):
    return {key: canonical(value) if isinstance(value, (dict, list)) else value for key, value in row.items()}


class SupportCounts:
    def __init__(self):
        self.total = Counter()
        self.groups = {name: defaultdict(Counter) for name in ('year', 'exchange', 'product')}

    def add(self, row, date_field, status_field):
        status = row[status_field]
        values = dict(rows=1, observed=int(status in ('verified', 'observed')),
                      missing=int(status not in ('verified', 'observed')),
                      observed_zero=int(row.get('scalar_primary') == 0 and status in ('verified', 'observed')))
        values['state:' + status] = 1
        self.total.update(values)
        product = row.get('product_id', '') or 'UNMAPPED'
        for group, key in [('year', row[date_field][:4]), ('exchange', row.get('exchange') or product.split('.')[0]), ('product', product)]:
            self.groups[group][key].update(values)

    def as_dict(self):
        return dict(total=dict(self.total), **{'by_'+name: {key: dict(value) for key, value in sorted(items.items())}
                                             for name, items in self.groups.items()})


def stat_identity(path):
    p = Path(path)
    st = p.stat()
    return dict(path=str(p.resolve()), bytes=st.st_size, mtime_ns=st.st_mtime_ns, inode=st.st_ino)


def validate_action_identity(row):
    if (row['actual_epoch'] != row['reference_epoch']
            or row['sequence_index'] != row['action_sequence_index']
            or row['event_id'] != row['action_id']):
        raise ValueError('accepted129_action_identity_alias_mismatch')


def actual(output):
    output = Path(output)
    prepare_output(output)
    started = time.monotonic()
    write_json(output/'started.json', dict(schema='stage162_started_v1', started_utc=datetime.now(timezone.utc).isoformat(),
               protocol_sha256=PROTOCOL_SHA, implementation=binding(__file__), auto_retry=False,
               fit=0, cash=0, SQL=0, network=0, outcomes=0, native_prices=0))
    inputs, artifacts = {}, []
    try:
        protocol_binding = binding(PROTOCOL)
        if protocol_binding['sha256'] != PROTOCOL_SHA:
            raise ValueError('frozen161_protocol_identity_mismatch')
        inputs['protocol'] = protocol_binding
        clarifier_binding = binding(CLARIFIER)
        if clarifier_binding['sha256'] != CLARIFIER_SHA:
            raise ValueError('frozen161_clarifier_identity_mismatch')
        inputs['implementation_clarifier'] = clarifier_binding
        protocol = json.loads(PROTOCOL.read_text())
        src = protocol['input_bindings']
        # Small bound manifests/identity directory are verified; the large129 CSV
        # hashes are inherited and each CSV is consumed once for identity only.
        for role, entry in src.items():
            if role in ('actions', 'mothers'):
                current = stat_identity(entry['path'])
                if current['bytes'] != entry['bytes']:
                    raise ValueError('identity_csv_size_mismatch ' + role)
                inputs[role] = dict(entry, verification='accepted129_sha_inherited_single_identity_stream', stat_before=current)
            else:
                inputs[role] = verify(entry)
        dataset = json.loads(Path(src['dataset_manifest']['path']).read_text())
        for role in ('actions', 'mothers'):
            if any(dataset[role][key] != src[role][key] for key in ('path', 'bytes', 'sha256')):
                raise ValueError('accepted129_binding_closure_mismatch')
        market = json.loads(Path(src['market_protocol']['path']).read_text())
        if any(market['calendar'][key] != src['calendar'][key] for key in ('path', 'bytes', 'sha256')):
            raise ValueError('accepted052_calendar_binding_mismatch')
        import numpy as np
        array = np.load(io.BytesIO(Path(src['calendar']['path']).read_bytes()), allow_pickle=False)
        calendar = ([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in array]
                    if array.dtype.kind in 'iu' else array.astype('datetime64[D]').astype(str).tolist())
        if len(calendar) != 5587 or calendar != sorted(set(calendar)):
            raise ValueError('full052_calendar_identity_mismatch')
        directory = list(identity_rows(src['epoch_directory']['path'], ('epoch', 'product_id')))
        if len(directory) != protocol['scope']['directory_epochs'] or len({r['product_id'] for r in directory}) != 98:
            raise ValueError('directory_domain_mismatch')
        epoch_index = build_epoch_index(directory)
        with Path(src['date_manifest']['path']).open() as stream:
            entries = [json.loads(line) for line in stream if line.strip()]
        expected_dates = json.loads(Path(src['source_dates']['path']).read_text())['dates']
        if [entry['date'] for entry in entries] != expected_dates or len(entries) != 3588 or len(set(expected_dates)) != 3588:
            raise ValueError('accepted_source_dates_identity_mismatch')
        lookup, day_states, source_counts = {}, {}, SupportCounts()
        known_read, unavailable, day_counts, mapping_counts = 0, 0, Counter(), Counter()
        consumed_body_bytes, consumed_file_bytes = 0, 0
        source_stream, source_writer = csv_writer(output/'normalized_scopes.csv.gz', SCOPE_FIELDS)
        day_stream, day_writer = csv_writer(output/'source_day_audit.csv.gz', DAY_FIELDS)
        try:
            for source_index, entry in enumerate(entries):
                day = entry['date'][:4]+'-'+entry['date'][4:6]+'-'+entry['date'][6:8]
                original_status = entry['status']
                audit = dict(source_index=source_index, source_date=day, original_status=original_status,
                             source_day_status=original_status, raw_rows=0, scopes=0, exact_mapped_scopes=0,
                             scope_states_json='{}', mapping_states_json='{}', report_date_state='unavailable')
                if original_status not in KNOWN_STATUSES:
                    unavailable += 1
                    day_states[day] = original_status
                    day_counts[original_status] += 1
                    day_writer.writerow(audit)
                    continue
                obj, verified = read_verified_source(entry)
                audit.update(verified)
                known_read += 1
                consumed_body_bytes += verified['current_body_bytes']
                consumed_file_bytes += verified['current_archive_bytes']
                if obj is None:
                    audit['source_day_status'] = audit['parse_state']
                else:
                    metadata = {key: value for key, value in obj.items() if key != 'o_cursor'}
                    audit['report_metadata_json'] = canonical(metadata)
                    report_state = ('absent' if 'report_date' not in obj else
                                    'matches' if str(obj['report_date']).replace('-', '') == entry['date'] else 'mismatch')
                    audit['report_date_state'] = report_state
                    audit['raw_rows'] = len(obj['o_cursor'])
                    if report_state == 'mismatch':
                        audit['source_day_status'] = 'report_date_mismatch'
                    else:
                        grouped = defaultdict(list)
                        for source_row, row in enumerate(obj['o_cursor']):
                            grouped[text_identity(row.get('INSTRUMENTID'))].append((source_row, row))
                        states, mappings = Counter(), Counter()
                        for instrument, rows in grouped.items():
                            scope = normalize_scope(rows, day, instrument, epoch_index)
                            scope['source_index'] = source_index
                            source_writer.writerow(serial_row(scope))
                            source_counts.add(scope, 'source_date', 'scope_status')
                            states[scope['scope_status']] += 1
                            mappings[scope['mapping_state']] += 1
                            if scope['mapping_state'] == 'exact_epoch':
                                key = (day, scope['epoch'])
                                if key in lookup:
                                    raise ValueError('multiple_raw_scopes_for_exact_epoch')
                                lookup[key] = {name: scope[name] for name in ('scope_id', 'scope_status', 'scalar_primary')}
                        audit.update(scopes=len(grouped), exact_mapped_scopes=mappings['exact_epoch'],
                                     scope_states_json=canonical(dict(states)), mapping_states_json=canonical(dict(mappings)))
                        mapping_counts.update(mappings)
                day_states[day] = audit['source_day_status']
                day_counts[audit['source_day_status']] += 1
                day_writer.writerow(audit)
                if source_index % 250 == 0:
                    print('SOURCE', source_index+1, '/', len(entries), day, flush=True)
        finally:
            source_stream.close()
            day_stream.close()
        if known_read != 3580 or unavailable != 8:
            raise ValueError('accepted_source_known_unknown_domain_mismatch')
        summaries = {}
        for role, fields, epoch_field, expected in [('actions', ACTION_ID, 'actual_epoch', 1552456),
                                                     ('mothers', MOTHER_ID, 'reference_epoch', 399252)]:
            counts, main_counts, identities = SupportCounts(), SupportCounts(), hashlib.sha256()
            cutoff_counts = {cutoff: SupportCounts() for cutoff in ('2020-01-01', '2023-01-01')}
            stream, writer = csv_writer(output/(role+'_projection.csv.gz'), fields + PROJECT_FIELDS)
            row_count = 0
            try:
                for row in identity_rows(src[role]['path'], fields):
                    seq_field = 'action_sequence_index' if role == 'actions' else 'sequence_index'
                    if int(row[seq_field]) != row_count:
                        raise ValueError('original_identity_sequence_mismatch ' + role)
                    if role == 'actions':
                        validate_action_identity(row)
                    projected = project_identity(row, epoch_field, calendar, day_states, lookup)
                    writer.writerow(projected)
                    identities.update((canonical(row)+'\n').encode())
                    counts.add(projected, 'u_date', 'projection_status')
                    if row['u_date'] >= '2020-01-01':
                        main_counts.add(projected, 'u_date', 'projection_status')
                    for cutoff, availability in cutoff_counts.items():
                        if row['u_date'] < cutoff:
                            availability.add(projected, 'u_date', 'projection_status')
                    row_count += 1
            finally:
                stream.close()
            if row_count != expected:
                raise ValueError('full_identity_domain_mismatch ' + role)
            after = stat_identity(src[role]['path'])
            if after != inputs[role]['stat_before']:
                raise ValueError('identity_csv_changed_while_streaming')
            inputs[role]['stat_after'] = after
            inputs[role]['identity_projection_sha256'] = identities.hexdigest()
            summaries[role] = dict(full=counts.as_dict(), forward_2020_plus=main_counts.as_dict(),
                                   pre_cutoff_source_availability={key: value.as_dict() for key, value in cutoff_counts.items()})
        if summaries['mothers']['forward_2020_plus']['total']['rows'] != 161014:
            raise ValueError('main2020_mother_domain_mismatch')
        summary = dict(schema='stage162_support_summary_v1', definition_version=VERSION,
                       source_days=3588, known_responses_read_once=known_read, unknown_unread=unavailable,
                       directory_epochs=len(directory), directory_product_codes=len({row['product_id'] for row in directory}),
                       consumed_original_body_bytes=consumed_body_bytes, consumed_compressed_or_plain_file_bytes=consumed_file_bytes,
                       source_day_states=dict(day_counts), mapping_states=dict(mapping_counts),
                       normalized_scopes=source_counts.as_dict(), **summaries,
                       first_publication_PIT_certified=False, outcome_or_financial_inference=False,
                       pre_cutoff_availability_is_not_mature_training_support=True,
                       new_fit=0, new_cash=0, new_SQL=0, network=0, cumulative_fit=397, cumulative_cash=210)
        write_json(output/'support_summary.json', summary)
        terminal = dict(schema='stage162_terminal_v1', status='completed', elapsed_seconds=time.monotonic()-started,
                        known_responses_read_once=known_read, actions=1552456, mothers=399252,
                        new_fit=0, new_cash=0, new_SQL=0, network=0, retry=False)
        write_json(output/'terminal.json', terminal)
        for name in ('started.json', 'normalized_scopes.csv.gz', 'source_day_audit.csv.gz', 'actions_projection.csv.gz',
                     'mothers_projection.csv.gz', 'support_summary.json', 'terminal.json'):
            artifacts.append(dict(binding(output/name), role=name.split('.')[0]))
        write_json(output/'manifest.json', dict(schema='stage162_member_distribution_manifest_v1', status='completed',
                   definition_version=VERSION, protocol=inputs['protocol'], inputs=inputs,
                   source_bundle=[binding(__file__), binding(Path(__file__).with_name('test_stage162_member_distribution.py'))],
                   artifacts=artifacts, strict_first_publication_PIT=False, financial_authorization=False,
                   identity_fields=dict(actions=ACTION_ID, mothers=MOTHER_ID),
                   normalization=dict(scope_id='YYYYMMDD|strip(raw INSTRUMENTID)', source_index='119manifest zero-based order',
                                      vectors='canonical UTF8 JSON list; sort_keys=True,separators=(comma,colon),ensure_ascii=False',
                                      lag='complete0525587 predecessor v=u_index-1; no nearest-success or all fallback'),
                   new_fit=0, new_cash=0, new_SQL=0, network=0))
        print('COMPLETED', canonical(terminal), flush=True)
    except BaseException as exc:
        write_json(output/'terminal.json', dict(schema='stage162_terminal_v1', status='failed',
                   elapsed_seconds=time.monotonic()-started, error=type(exc).__name__+': '+str(exc),
                   traceback=traceback.format_exc(), retry=False, new_fit=0, new_cash=0, new_SQL=0, network=0))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Fresh output directory; root actual once only.')
    args = parser.parse_args()
    actual(args.output)


if __name__ == '__main__':
    main()
