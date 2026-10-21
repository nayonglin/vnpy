#!/usr/bin/env python3
"""Stage484: one metadata-only request projection. No market/label/fit execution."""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import csv
from datetime import datetime, time, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ACTION = ['sequence_index', 'action_sequence_index', 'action_id', 'mother_sequence_index',
          'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index',
          'reference_epoch', 'anchor_epoch', 'u_action_eligible']
MOTHER = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
UTC = timezone.utc
NY = ZoneInfo('America/New_York')
SH = ZoneInfo('Asia/Shanghai')
SCHEMA = 'stage483_fomc_exact_request_protocol_v1'
LINE = 'futures_full_market_long_signal_ai'
CONTEXT = ['fomc_ordinal', 'fomc_event_id', 'source_start', 'source_event', 'pre_date',
           'decision_u_date', 'decision_u_index', 'D_date', 'D_index']


def digest_row(digest, values):
    digest.update((json.dumps(list(values), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode())


def integer(value):
    if isinstance(value, (int, np.integer)):
        return int(value)
    text = str(value)
    if not text or str(int(text)) != text:
        raise ValueError('noncanonical_integer ' + text)
    return int(text)


def calendar_days(raw):
    array = np.load(io.BytesIO(raw), allow_pickle=False)
    if array.ndim != 1:
        raise ValueError('one_dimensional_calendar_required')
    if array.dtype.kind in 'iu':
        # These are YYYYMMDD integers, never Unix-day counts.
        days = [datetime.strptime(f'{int(v):08d}', '%Y%m%d').date().isoformat() for v in array]
    elif array.dtype.kind == 'M':
        days = array.astype('datetime64[D]').astype(str).tolist()
    else:
        raise ValueError('calendar_dtype_not_accepted')
    validate_calendar(days)
    return days


def validate_calendar(calendar):
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError('strict_unique_calendar_required')
    for day in calendar:
        if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
            raise ValueError('noncanonical_calendar_day')


def event_clocks(events, calendar, study_start, study_end):
    """A finite calendar is not extrapolated at either end; UTC supplies elapsed time."""
    validate_calendar(calendar)
    cutoffs = [datetime.combine(datetime.strptime(d, '%Y-%m-%d').date(), time(15, 15), SH).astimezone(UTC) for d in calendar]
    rows = []
    for ordinal, event in enumerate(events):
        start = str(event.get('start', ''))
        row = dict(fomc_ordinal=ordinal, fomc_event_id=f'fomc:{ordinal}:{start}', source_start=start,
                   source_event=str(event.get('Event', '')), announcement_ny='', announcement_utc='',
                   announcement_shanghai='', deadline_utc='', deadline_shanghai='', pre_date='',
                   pre_index='', pre_cutoff_utc='', u_date='', u_index='', u_cutoff_utc='',
                   decision_elapsed_hours='', D_date='', D_index='', eligible=0,
                   pre_status='unknown', D_status='unknown', status='missing_start')
        if not start:
            rows.append(row)
            continue
        naive = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
        if naive.strftime('%Y-%m-%d %H:%M:%S') != start:
            raise ValueError('noncanonical_event_timestamp')
        local = naive.replace(tzinfo=NY)
        if local.astimezone(UTC).astimezone(NY).replace(tzinfo=None) != naive:
            raise ValueError('nonexistent_new_york_event_timestamp')
        if local.utcoffset() != naive.replace(tzinfo=NY, fold=1).utcoffset():
            raise ValueError('ambiguous_new_york_event_timestamp')
        announcement = local.astimezone(UTC)
        deadline = announcement + timedelta(hours=25)
        row.update(announcement_ny=local.isoformat(), announcement_utc=announcement.isoformat(),
                   announcement_shanghai=announcement.astimezone(SH).isoformat(), deadline_utc=deadline.isoformat(),
                   deadline_shanghai=deadline.astimezone(SH).isoformat())
        pre = bisect_left(cutoffs, announcement) - 1
        if pre >= 0:
            row.update(pre_date=calendar[pre], pre_index=pre, pre_cutoff_utc=cutoffs[pre].isoformat(), pre_status='mapped')
            if not cutoffs[pre] < announcement:
                raise ValueError('pre_cutoff_not_strictly_before_announcement')
        else:
            row['pre_status'] = 'no_previous_source_day'
        # Do not pretend an event long before the finite calendar maps to its first day.
        if deadline < cutoffs[0]:
            row.update(status='before_source_calendar', D_status='no_u')
            rows.append(row)
            continue
        u = bisect_left(cutoffs, deadline)
        if u == len(calendar):
            row.update(status='no_u_in_source_calendar', D_status='no_u')
            rows.append(row)
            continue
        elapsed = (cutoffs[u] - announcement).total_seconds() / 3600
        if elapsed < 25:
            raise ValueError('decision_before_25_elapsed_utc_hours')
        row.update(u_date=calendar[u], u_index=u, u_cutoff_utc=cutoffs[u].isoformat(), decision_elapsed_hours=elapsed)
        if u + 1 < len(calendar):
            row.update(D_date=calendar[u + 1], D_index=u + 1, D_status='mapped')
        else:
            row['D_status'] = 'no_future_source_day'
        if calendar[u] < study_start:
            row['status'] = 'u_before_study'
        elif calendar[u] > study_end:
            row['status'] = 'u_after_study'
        else:
            row.update(eligible=1, status='eligible')
            if row['D_status'] != 'mapped':
                row['status'] = 'eligible_no_future_D'
            elif row['pre_status'] != 'mapped':
                row['status'] = 'eligible_no_pre_date'
        rows.append(row)
    return rows


def csv_writer(path, fields, compressed=False):
    stream = gzip.open(path, 'xt', encoding='utf8', newline='') if compressed else Path(path).open('x', encoding='utf8', newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='raise')
    writer.writeheader()
    return stream, writer


def build_requests(calendar, mothers, actions, events, scope, output):
    """Small pure join plus one full action iterator; no hidden source loads."""
    clocks = event_clocks(events, calendar, scope['study_start'], scope['study_end'])
    if len(clocks) != scope.get('event_rows', 385):
        raise ValueError('full_event_count_changed')
    eligible = [r for r in clocks if r['eligible']]
    by_u_events = defaultdict(list)
    for event in eligible:
        by_u_events[event['u_index']].append(event)
    pre_dates = {r['pre_date'] for r in eligible if r['pre_date']}
    mother_rows = mothers.to_dict('records') if isinstance(mothers, pd.DataFrame) else [dict(r) for r in mothers]
    if len(mother_rows) != scope['mother_rows']:
        raise ValueError('full_original_mother_rows_changed')
    mdigest = hashlib.sha256()
    mother_ids = set()
    products = {}
    by_u_mothers = defaultdict(list)
    for index, row in enumerate(mother_rows):
        row.update(sequence_index=integer(row['sequence_index']), u_index=integer(row['u_index']))
        if row['sequence_index'] != index or not row['event_id'] or row['event_id'] in mother_ids:
            raise ValueError('mother_sequence_or_global_identity_changed')
        mother_ids.add(row['event_id'])
        u = row['u_index']
        if not 0 <= u < len(calendar) or row['u_date'] != calendar[u]:
            raise ValueError('mother_source_calendar_disagreement')
        if row['family_id'] != row['product_id'].removesuffix('_F'):
            raise ValueError('mother_ordinary_F_family_alias_disagreement')
        if row['reference_epoch'] and row['reference_epoch'].rsplit('.', 1)[0] != row['product_id']:
            raise ValueError('mother_reference_epoch_product_disagreement')
        if row['product_id'] in products and products[row['product_id']] != row['family_id']:
            raise ValueError('product_family_alias_changed')
        products[row['product_id']] = row['family_id']
        by_u_mothers[u].append(index)
        digest_row(mdigest, (row[k] for k in MOTHER))
    if len(products) != scope['products'] or len(set(products.values())) != scope['families']:
        raise ValueError('full_product_or_family_roster_changed')
    roster = set(products)
    for u, indices in by_u_mothers.items():
        if len(indices) != scope['products'] or {mother_rows[i]['product_id'] for i in indices} != roster:
            raise ValueError('mother_day_roster_not_complete')
    for u in by_u_events:
        if u not in by_u_mothers:
            raise ValueError('eligible_u_missing_full_mother_roster')
    adigest = hashlib.sha256()
    actions_by_u = defaultdict(list)
    observed = set()
    full_children = np.zeros(len(mother_rows), dtype=np.int64)
    action_ids = set()
    action_products = Counter()
    count = 0
    for raw in actions:
        row = {k: raw[k] for k in ACTION}
        for key in ('sequence_index', 'action_sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible'):
            row[key] = integer(row[key])
        parent = row['mother_sequence_index']
        if (row['sequence_index'] != count or row['action_sequence_index'] != count
                or not row['action_id'] or row['action_id'] in action_ids or not 0 <= parent < len(mother_rows)):
            raise ValueError('action_global_alias_sequence_parent_disagreement ' + str(count))
        action_ids.add(row['action_id'])
        mother = mother_rows[parent]
        if (row['mother_event_id'] != mother['event_id'] or row['anchor_epoch'] != mother['reference_epoch']
                or any(row[k] != mother[k] for k in ('product_id', 'family_id', 'u_date', 'u_index'))):
            raise ValueError('action_mother_identity_disagreement ' + str(count))
        if (row['u_action_eligible'] not in (0, 1) or not row['reference_epoch']
                or row['reference_epoch'].rsplit('.', 1)[0] != row['product_id']):
            raise ValueError('action_epoch_or_eligibility_disagreement ' + str(count))
        digest_row(adigest, (row[k] for k in ACTION))
        full_children[parent] += 1
        action_products[row['product_id']] += 1
        if row['u_date'] in pre_dates:
            observed.add((row['reference_epoch'], row['u_date']))
        if row['u_index'] in by_u_events:
            actions_by_u[row['u_index']].append(row)
        count += 1
    if count != scope['action_rows'] or sum(int(v) for v in full_children) != count:
        raise ValueError('full_original_child_count_changed')
    pdigest = hashlib.sha256()
    for row, n in zip(mother_rows, full_children):
        digest_row(pdigest, (row['sequence_index'], row['event_id'], int(n)))
    clock_stream, clock_writer = csv_writer(output / 'full_event_clock_status.csv', list(clocks[0]))
    with clock_stream:
        clock_writer.writerows(clocks)
    mother_stream, mother_writer = csv_writer(output / 'all_event_mother_requests.csv.gz', CONTEXT + MOTHER + ['child_count_original'], True)
    child_stream, child_writer = csv_writer(output / 'all_event_child_requests.csv.gz', CONTEXT + ACTION + ['raw_request_id', 'pre_observed_any_epoch', 'requestable'], True)
    rawkeys = {}
    mother_count = child_count = no_pre_support = nochild = ineligible_children = 0
    link_digest = hashlib.sha256()
    with mother_stream, child_stream:
        for event in eligible:
            context = {k: event[k] for k in CONTEXT if k not in ('decision_u_date', 'decision_u_index')}
            context.update(decision_u_date=event['u_date'], decision_u_index=event['u_index'])
            u = event['u_index']
            for index in by_u_mothers[u]:
                n = int(full_children[index])
                mother_writer.writerow(dict(context, **mother_rows[index], child_count_original=n))
                mother_count += 1
                nochild += int(n == 0)
            local_child_count = 0
            for row in actions_by_u[u]:
                exact = (row['reference_epoch'], event['pre_date'])
                encoded = json.dumps(exact, separators=(',', ':'), ensure_ascii=False)
                request_id = hashlib.sha256(encoded.encode()).hexdigest()
                support = int(exact in observed)
                if exact not in rawkeys:
                    rawkeys[exact] = dict(raw_request_id=request_id, reference_epoch=exact[0], pre_date=exact[1],
                                          pre_observed_any_epoch=support, requestable=int(bool(exact[1])),
                                          child_link_count=0, events=set(), products=set())
                key = rawkeys[exact]
                key['child_link_count'] += 1
                key['events'].add(event['fomc_event_id'])
                key['products'].add(row['product_id'])
                child_writer.writerow(dict(context, **row, raw_request_id=request_id, pre_observed_any_epoch=support, requestable=int(bool(exact[1]))))
                digest_row(link_digest, (event['fomc_event_id'], row['action_sequence_index'], row['mother_sequence_index'], request_id))
                child_count += 1
                local_child_count += 1
                no_pre_support += 1 - support
                ineligible_children += int(row['u_action_eligible'] == 0)
            if local_child_count != sum(int(full_children[i]) for i in by_u_mothers[u]):
                raise ValueError('event_request_child_links_lost')
    key_fields = ['raw_request_id', 'reference_epoch', 'pre_date', 'pre_observed_any_epoch', 'requestable', 'child_link_count', 'event_count', 'product_aliases']
    key_stream, key_writer = csv_writer(output / 'unique_epoch_pre_date_requests.csv.gz', key_fields, True)
    with key_stream:
        for row in rawkeys.values():
            row = dict(row)
            row['event_count'] = len(row.pop('events'))
            row['product_aliases'] = json.dumps(sorted(row.pop('products')), ensure_ascii=False, separators=(',', ':'))
            key_writer.writerow(row)
    if mother_count != len(eligible) * scope['products'] or sum(r['child_link_count'] for r in rawkeys.values()) != child_count:
        raise ValueError('mother_or_request_link_conservation_failed')
    roster_digest = hashlib.sha256()
    for product, family in sorted(products.items()):
        digest_row(roster_digest, (product, family))
    return dict(schema='stage484_fomc_event_requests_v1', line_id=LINE,
                full_event_rows=len(clocks), event_status_counts=dict(Counter(r['status'] for r in clocks)),
                eligible_event_count=len(eligible), unique_eligible_u_count=len(by_u_events),
                full_original_mother_rows=len(mother_rows), full_original_action_rows=count,
                full_product_count=len(products), full_family_count=len(set(products.values())),
                full_mother_metadata_sha256=mdigest.hexdigest(), full_action_metadata_sha256=adigest.hexdigest(),
                full_parent_child_count_sha256=pdigest.hexdigest(), full_product_family_roster_sha256=roster_digest.hexdigest(),
                full_action_count_by_product=dict(sorted(action_products.items())), full_product_family_roster=products,
                expanded_mother_requests=mother_count, expanded_child_requests=child_count, unique_raw_requests=len(rawkeys),
                expanded_nochild_mothers=nochild, expanded_pre_unobserved_children=no_pre_support,
                expanded_u_action_eligible0_children=ineligible_children, request_link_sha256=link_digest.hexdigest(),
                ordinary_F_preserved=True, pre_support_source='same exact epoch/pre_date in all original metadata, independent of labels and eligibility',
                eligibility='decision_u in study only; no value, label, child, pre-support or D filter',
                clock_assumption='conditional America/New_York; elapsed UTC+25h; Shanghai15:15 finite research calendar',
                calendar_mapping_historical_publication_certified=False, PIT_qualified=False, training_ready=False,
                fit=0, cash=0, network=0, Y_or_exit_state_reads=0, COMMON_or_score_reads=0, native_or_SQL_reads=0)


def stat_bound(bound):
    path = Path(bound['path']).resolve()
    stat = path.stat()
    if not path.is_file() or stat.st_size != bound['bytes']:
        raise ValueError('source_bound_size_changed ' + str(path))
    return dict(path=str(path), bytes=stat.st_size, device=stat.st_dev, inode=stat.st_ino,
                mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns,
                inherited_sha256=bound['sha256'], content_rehashed=False)


def write_json(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def output_binding(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def action_stream(bound):
    # The only action source read. Forbidden label/exit columns never enter a DataFrame.
    for frame in pd.read_csv(bound['path'], usecols=ACTION, dtype=str, keep_default_na=False, chunksize=50000):
        frame = frame.loc[:, ACTION]
        for values in frame.itertuples(index=False, name=None):
            yield dict(zip(ACTION, values))


def run(args):
    protocol_path = Path(args.protocol).resolve()
    protocol_raw = protocol_path.read_bytes()
    protocol_sha = hashlib.sha256(protocol_raw).hexdigest()
    if protocol_sha != args.protocol_sha256:
        raise ValueError('protocol_sha256_disagreement')
    protocol = json.loads(protocol_raw)
    if protocol.get('schema') != SCHEMA or protocol.get('line_id') != LINE or protocol.get('action_usecols') != ACTION or protocol.get('mother_usecols') != MOTHER:
        raise ValueError('fixed_protocol_schema_or_white_list_changed')
    expected_budget = dict(metadata_action_streams=1, mothers_reads=1, calendar_reads=1, fomc_raw_reads=1,
                           old_large_file_rehashes=0, native_or_source_bodies=0, SQL=0,
                           Y_or_exit_state_reads=0, COMMON_or_scores=0, fit=0, cash=0, network=0)
    if protocol['budget'] != expected_budget:
        raise ValueError('fixed_metadata_only_budget_changed')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='stage484_input_read_receipt_v1', protocol_sha256=protocol_sha,
                   protocol_path=str(protocol_path), reads_attempted={}, reads_completed={},
                   selected_columns={'actions_metadata': ACTION, 'mothers': MOTHER, 'fomc_raw': ['start', 'Event']},
                   old_large_file_rehashes=0, Y_or_exit_state_reads=0, COMMON_or_scores=0, native_or_source_bodies=0,
                   SQL=0, fit=0, cash=0, network=0)
    started = datetime.now(SH).isoformat()
    try:
        bounds = protocol['input_bindings']
        if set(bounds) != {'actions_metadata', 'mothers', 'calendar', 'fomc_raw'}:
            raise ValueError('exact_four_input_bindings_required')
        receipt['before'] = {key: stat_bound(bound) for key, bound in bounds.items()}
        receipt['reads_attempted']['calendar'] = 1
        calendar = calendar_days(Path(bounds['calendar']['path']).read_bytes())
        receipt['reads_completed']['calendar'] = 1
        receipt['reads_attempted']['fomc_raw'] = 1
        fomc_raw = Path(bounds['fomc_raw']['path']).read_bytes()
        events = pd.read_csv(io.BytesIO(fomc_raw), usecols=['start', 'Event'], dtype=str, keep_default_na=False).to_dict('records')
        receipt['reads_completed']['fomc_raw'] = 1
        del fomc_raw
        receipt['reads_attempted']['mothers'] = 1
        mothers = pd.read_csv(bounds['mothers']['path'], usecols=MOTHER, dtype=str, keep_default_na=False).loc[:, MOTHER]
        receipt['reads_completed']['mothers'] = 1
        receipt['reads_attempted']['actions_metadata'] = 1
        summary = build_requests(calendar, mothers, action_stream(bounds['actions_metadata']), events, protocol['scope'], output)
        receipt['reads_completed']['actions_metadata'] = 1
        receipt['after'] = {key: stat_bound(bound) for key, bound in bounds.items()}
        if receipt['before'] != receipt['after']:
            raise ValueError('source_stats_changed_during_run')
        receipt['input_stats_unchanged'] = True
        summary.update(protocol_sha256=protocol_sha, started_at=started, completed_at=datetime.now(SH).isoformat(),
                       input_sha256_inherited_not_rehashed={key: bound['sha256'] for key, bound in bounds.items()},
                       goal_complete=False, financial_metrics='N/A: no backtest, market values, labels, fit or cash')
        write_json(output / 'summary.json', summary)
        write_json(output / 'input_read_receipt.json', receipt)
        files = [output_binding(p) for p in sorted(output.iterdir()) if p.is_file()]
        write_json(output / 'manifest.json', dict(schema='stage484_manifest_v1', protocol_sha256=protocol_sha, files=files,
                   source=output_binding(Path(__file__)), scope='pure metadata requests only; no production activation'))
        write_json(output / 'terminal.json', dict(status='completed', started_at=started, completed_at=datetime.now(SH).isoformat(),
                   protocol_sha256=protocol_sha, auto_retry=False, output=str(output),
                   manifest=output_binding(output / 'manifest.json')))
        print(json.dumps(dict(status='completed', output=str(output), full_event_rows=summary['full_event_rows'],
                              expanded_child_requests=summary['expanded_child_requests'], unique_raw_requests=summary['unique_raw_requests']), ensure_ascii=False))
        return 0
    except Exception as exc:
        try:
            if 'bounds' in locals():
                receipt['after'] = {key: stat_bound(bound) for key, bound in bounds.items()}
                receipt['input_stats_unchanged'] = receipt.get('before') == receipt['after']
        except Exception as stat_exc:
            receipt['after_stat_error'] = f'{type(stat_exc).__name__}: {stat_exc}'
        if not (output / 'input_read_receipt.json').exists():
            write_json(output / 'input_read_receipt.json', receipt)
        write_json(output / 'terminal.json', dict(status='failed', started_at=started, completed_at=datetime.now(SH).isoformat(),
                   protocol_sha256=protocol_sha, auto_retry=False, error=f'{type(exc).__name__}: {exc}', output=str(output)))
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', required=True, help='must not exist; no automatic retry')
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
