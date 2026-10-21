"""Independent frozen226 clock audit. Import has no I/O.

Root alone launches actual review once. Only new227 projected metadata, its
small reports, and the single bound calendar are read. Never reads original129
tables, prices, X/Y, models, training caches, scores, cash books, or SQL.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
from collections import Counter
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import traceback

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage226_K_clock_support_protocol/protocol.json'
PROTOCOL_SHA = 'ccaf36d3a5233cb826f86f012009ad4f5d30b45a210cb3eac09ff01b869a0a3f'
RAW_ACTION = ['sequence_index', 'action_sequence_index', 'action_id', 'mother_sequence_index',
    'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch',
    'anchor_epoch', 'u_action_eligible', 'D_index', 'label_history_ready20', 'participation_state',
    'label_state', 'filled', 'trade_label_known', 'entry_index', 'entry_date', 'exit_index',
    'exit_date', 'unknown_index', 'unknown_date', 'label_known_date', 'label_known_phase',
    'participation_known_date', 'participation_known_phase', 'last_path_index', 'cancel_reason']
RAW_MOTHER = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
TIMING = ('known_nonparticipation', 'not_history_ready', 'intent_right_censored',
    'closed_before_K', 'closed_on_K_priority_reprice', 'closed_after_K', 'unknown_before_K',
    'unknown_on_K', 'unknown_after_K', 'unknown_unclassified', 'open_K_reached',
    'open_K_pending', 'K_before_calendar_unavailable')
CALENDAR = ('blocked_beforecalendar', 'unknown_D_sentinel', 'allowed_D_before_K',
    'blocked_D_on_or_after_K', 'allowed_aftercalendar_D_before_target',
    'blocked_aftercalendar_D_on_or_after_target')
LABELS = {'known_nonparticipation', 'not_history_ready', 'intent_right_censored',
    'closed_complete_bar_model', 'entry_execution_unknown', 'path_or_execution_unknown',
    'input_or_economics_unresolved', 'open_right_censored'}
POTENTIAL = {'closed_on_K_priority_reprice', 'closed_after_K', 'unknown_after_K', 'open_K_reached'}
UNRESOLVED = {'unknown_before_K', 'unknown_on_K', 'unknown_unclassified', 'open_K_pending',
    'intent_right_censored', 'not_history_ready', 'K_before_calendar_unavailable'}
MOTHER_COUNTERS = ['child_count', 'u_eligible_child_count', 'calendar_allowed_child_count',
    'calendar_unknown_child_count', 'primary_domain_child_count', 'potential_support_child_count',
    'unresolved_primary_child_count', 'known_zero_exposure_primary_child_count',
    'primary_resolved_before_K_child_count'] + ['timing_'+s+'_child_count' for s in TIMING] + [
    'primary_timing_'+s+'_child_count' for s in TIMING]
MOTHER_TO_METRIC = dict(zip(MOTHER_COUNTERS[:9], ['action_count', 'u_eligible_count',
    'calendar_allowed_count', 'calendar_unknown_count', 'primary_domain_count', 'potential_support_count',
    'unresolved_primary_count', 'known_zero_exposure_primary_count', 'primary_resolved_before_K_count']))


def integer(value):
    f = float(value)
    if not math.isfinite(f) or int(f) != f:
        raise ValueError('finite integer metadata required')
    return int(f)


def absent(value):
    return value is None or str(value) in ('', 'nan', 'NaN', 'None', 'null')


def optional_integer(value):
    return None if absent(value) else integer(value)


def bound_k(epoch, calendar, sample_end):
    """Independent nominal month arithmetic and left successor; no156 import."""
    ym = epoch.rsplit('.', 1)[-1]
    if len(ym) != 6 or not ym.isdigit():
        raise ValueError('complete epoch month required')
    y, m = int(ym[:4]), int(ym[4:])
    date(y, m, 1)
    previous = y * 12 + m - 2
    target = date(previous // 12, previous % 12 + 1, 1).isoformat()
    if target < calendar[0]:
        k, day, state = None, None, 'before_calendar_blocked'
    else:
        position = bisect_left(calendar, target)
        k = position if position < len(calendar) else None
        day = calendar[k] if k is not None else None
        state = 'in_calendar' if k is not None else 'after_calendar_pending'
    return dict(K_target_date=target, K_index=k, K_date=day, K_state=state,
                K_after_sample_end=(day or target) > sample_end)


def clock(row, stem, calendar, sample_end):
    index, day = optional_integer(row.get(stem+'_index')), row.get(stem+'_date')
    if index is None and absent(day):
        return None
    if index is None or absent(day) or not 0 <= index < len(calendar) or calendar[index] != day or day > sample_end:
        raise ValueError(stem+' date/index mismatch')
    return index


def derive_metadata(row, calendar, sample_end, boundary_cache=None):
    u = integer(row['u_index'])
    if not 0 <= u < len(calendar) or calendar[u] != row['u_date'] or row['u_date'] > sample_end:
        raise ValueError('u date/index mismatch')
    if integer(row['D_index']) != u+1:
        raise ValueError('D date/index successor mismatch')
    eligible = integer(row['u_action_eligible'])
    filled, known = integer(row['filled']), integer(row['trade_label_known'])
    if any(v not in (0, 1) for v in (eligible, filled, known, integer(row['label_history_ready20']))):
        raise ValueError('binary original flags required')
    epoch = row['reference_epoch']
    if epoch.rsplit('.', 1)[0] != row['product_id']:
        raise ValueError('exact epoch product identity mismatch')
    if boundary_cache is None:
        b = bound_k(epoch, calendar, sample_end)
    else:
        if epoch not in boundary_cache:
            boundary_cache[epoch] = bound_k(epoch, calendar, sample_end)
        b = boundary_cache[epoch]
    d = u+1 if u+1 < len(calendar) else None
    d_date = calendar[d] if d is not None else None
    if b['K_state'] == 'before_calendar_blocked':
        allowed, calendar_state = False, 'blocked_beforecalendar'
    elif d is None:
        allowed, calendar_state = None, 'unknown_D_sentinel'
    elif b['K_index'] is None:
        allowed = d_date < b['K_target_date']
        calendar_state = 'allowed_aftercalendar_D_before_target' if allowed else 'blocked_aftercalendar_D_on_or_after_target'
    else:
        allowed = d < b['K_index']
        calendar_state = 'allowed_D_before_K' if allowed else 'blocked_D_on_or_after_K'
    state = row['label_state']
    if state not in LABELS:
        raise ValueError('unfrozen original label state '+state)
    entry, exit_, unknown = (clock(row, stem, calendar, sample_end) for stem in ('entry', 'exit', 'unknown'))
    last = optional_integer(row['last_path_index'])
    if last is not None and not 0 <= last < len(calendar):
        raise ValueError('last path index outside calendar')
    if filled and entry is None:
        raise ValueError('filled path missing entry clock')
    if entry is not None and exit_ is not None and entry > exit_:
        raise ValueError('entry/exit clock order mismatch')
    if state == 'closed_complete_bar_model' and (exit_ is None or filled != 1 or known != 1):
        raise ValueError('closed path clock/flags mismatch')
    if state == 'known_nonparticipation' and (filled or known):
        raise ValueError('nonparticipation cannot be a known trade label')
    if state in ('known_nonparticipation', 'not_history_ready', 'intent_right_censored'):
        timing = state
    elif b['K_state'] == 'before_calendar_blocked':
        timing = 'K_before_calendar_unavailable'
    elif state == 'closed_complete_bar_model':
        # Pending target is later than the final source date: a known observed
        # exit is definitely earlier, without inventing an exact future K.
        relation = -1 if b['K_index'] is None else (exit_ > b['K_index']) - (exit_ < b['K_index'])
        timing = {-1: 'closed_before_K', 0: 'closed_on_K_priority_reprice', 1: 'closed_after_K'}[relation]
    elif state == 'open_right_censored':
        if filled != 1 or known:
            raise ValueError('open path flags mismatch')
        timing = 'open_K_reached' if b['K_index'] is not None and b['K_date'] <= sample_end else 'open_K_pending'
    elif unknown is None:
        timing = 'unknown_unclassified'
    else:
        relation = -1 if b['K_index'] is None else (unknown > b['K_index']) - (unknown < b['K_index'])
        timing = {-1: 'unknown_before_K', 0: 'unknown_on_K', 1: 'unknown_after_K'}[relation]
    primary = eligible == 1 and allowed is True
    return dict(D_date=d_date, D_state='unknown_D_sentinel' if d is None else 'after_sample_end' if d_date > sample_end else 'in_sample_calendar',
        **b, calendar_allowed=allowed, calendar_state=calendar_state, primary_domain=primary,
        path_state=state, timing_state=timing, potential_clock_or_repricing_support=primary and timing in POTENTIAL,
        known_zero_exposure_before_K=timing == 'known_nonparticipation',
        unresolved_clock_obscures_no_effect=timing in UNRESOLVED)


def equal_metadata(actual, expected):
    for key, value in expected.items():
        if key not in actual:
            raise ValueError('projection missing '+key)
        raw = actual[key]
        if value is None:
            good = absent(raw)
        elif isinstance(value, bool):
            good = str(raw) in (('1', 'True', 'true') if value else ('0', 'False', 'false'))
        elif isinstance(value, int):
            good = integer(raw) == value
        else:
            good = str(raw) == value
        if not good:
            raise ValueError('derived metadata mismatch '+key+' at '+str(actual.get('sequence_index')))


def audit_rows(mothers, rows, calendar, sample_end, compare=True, expected_mothers=None, expected_actions=None):
    """Single projected stream; all cells include fixed zero groups and mothers."""
    import numpy as np
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError('sorted unique calendar required')
    if expected_mothers is None:
        mothers = list(mothers)
        expected_mothers = len(mothers)
    parents = []
    declared = np.zeros((expected_mothers, len(MOTHER_COUNTERS)+1), dtype=np.int64) if compare else None
    event_ids = set()
    for n, row in enumerate(mothers):
        if n >= expected_mothers or integer(row['sequence_index']) != n or row['event_id'] in event_ids:
            raise ValueError('contiguous unique mother identity required')
        event_ids.add(row['event_id'])
        u = integer(row['u_index'])
        if not 0 <= u < len(calendar) or calendar[u] != row['u_date']:
            raise ValueError('mother date/index mismatch')
        parents.append(tuple(row[k] for k in RAW_MOTHER))
        if compare:
            declared[n] = [integer(row[k]) for k in MOTHER_COUNTERS+['nochild']]
    if len(parents) != expected_mothers:
        raise ValueError('complete mother count mismatch')
    del event_ids
    actual = np.zeros((expected_mothers, len(MOTHER_COUNTERS)+1), dtype=np.int64)
    years = [str(y) for y in range(2010, 2027)]
    families = sorted({p[3] for p in parents})
    products = sorted({p[2] for p in parents})
    cells = {(s, dim, g): Counter() for s in ('all', '2020onward') for dim, groups in
             [('global', ['ALL']), ('year', years), ('family', families), ('product', products)] for g in groups}
    metric_names = set(MOTHER_TO_METRIC.values()) | {'calendar_unknown_u_eligible_count', 'mother_count', 'nochild_mother_count',
        'primary_domain_mother_count', 'potential_support_mother_count'} | {'calendar_'+s+'_count' for s in CALENDAR} | {
        'timing_'+s+'_count' for s in TIMING} | {'primary_timing_'+s+'_count' for s in TIMING} | {'label_'+s+'_count' for s in LABELS}
    seen_ids, boundaries, anchor_rows, participations = set(), {}, {}, Counter()
    positions = set((i*(expected_actions-1))//15 for i in range(16)) if expected_actions else set()
    count = 0
    for count, row in enumerate(rows, 1):
        n = count-1
        if integer(row['sequence_index']) != n or integer(row['action_sequence_index']) != n or row['action_id'] in seen_ids:
            raise ValueError('contiguous unique original action identity required')
        seen_ids.add(row['action_id'])
        parent = integer(row['mother_sequence_index'])
        if not 0 <= parent < len(parents):
            raise ValueError('action outside complete parent domain')
        p = parents[parent]
        if (row['mother_event_id'], row['product_id'], row['family_id'], row['u_date'],
            integer(row['u_index']), row['anchor_epoch']) != (p[1], p[2], p[3], p[4], integer(p[5]), p[6]):
            raise ValueError('original parent/anchor identity mismatch')
        derived = derive_metadata(row, calendar, sample_end, boundaries)
        if compare:
            equal_metadata(row, derived)
        primary = int(derived['primary_domain'])
        timing = derived['timing_state']
        metrics = Counter(action_count=1, u_eligible_count=integer(row['u_action_eligible']),
            calendar_allowed_count=int(derived['calendar_allowed'] is True),
            calendar_unknown_count=int(derived['calendar_allowed'] is None),
            calendar_unknown_u_eligible_count=int(derived['calendar_allowed'] is None and integer(row['u_action_eligible']) == 1),
            primary_domain_count=primary,
            potential_support_count=int(derived['potential_clock_or_repricing_support']),
            unresolved_primary_count=primary*int(derived['unresolved_clock_obscures_no_effect']),
            known_zero_exposure_primary_count=primary*int(derived['known_zero_exposure_before_K']),
            primary_resolved_before_K_count=primary*int(timing in ('closed_before_K', 'known_nonparticipation')))
        metrics['calendar_'+derived['calendar_state']+'_count'] = 1
        metrics['timing_'+timing+'_count'] = 1
        metrics['primary_timing_'+timing+'_count'] = primary
        metrics['label_'+row['label_state']+'_count'] = 1
        participations[row['participation_state']] += 1
        for scope in ('all', '2020onward') if row['u_date'] >= '2020-01-01' else ('all',):
            for dim, group in [('global', 'ALL'), ('year', row['u_date'][:4]), ('family', row['family_id']), ('product', row['product_id'])]:
                cells[(scope, dim, group)].update(metrics)
        for i, key in enumerate(MOTHER_COUNTERS):
            metric = MOTHER_TO_METRIC.get(key, key.replace('_child_count', '_count'))
            actual[parent, i] += metrics[metric]
        if n in positions:
            anchor_rows[n] = {k: row[k] for k in RAW_ACTION} | derived
    if expected_actions is not None and count != expected_actions:
        raise ValueError('complete action count mismatch')
    for n, p in enumerate(parents):
        actual[n, -1] = int(actual[n, 0] == 0)
        metrics = Counter(mother_count=1, nochild_mother_count=int(actual[n, -1]),
            primary_domain_mother_count=int(actual[n, 4] > 0), potential_support_mother_count=int(actual[n, 5] > 0))
        for scope in ('all', '2020onward') if p[4] >= '2020-01-01' else ('all',):
            for dim, group in [('global', 'ALL'), ('year', p[4][:4]), ('family', p[3]), ('product', p[2])]:
                cells[(scope, dim, group)].update(metrics)
    if compare and not np.array_equal(declared, actual):
        first = np.argwhere(declared != actual)[0].tolist()
        raise ValueError('per-mother partition mismatch '+str(first))
    for (scope, dim, group), cell in cells.items():
        if sum(cell['timing_'+s+'_count'] for s in TIMING) != cell['action_count'] or sum(
            cell['calendar_'+s+'_count'] for s in CALENDAR) != cell['action_count'] or sum(
            cell['primary_timing_'+s+'_count'] for s in TIMING) != cell['primary_domain_count'] or sum(
            cell['label_'+s+'_count'] for s in LABELS) != cell['action_count']:
            raise ValueError('nonexhaustive independent partition '+str((scope, dim, group)))
    metrics = sorted(metric_names)
    scopes = {s: {k: cells[(s, 'global', 'ALL')][k] for k in metrics} for s in ('all', '2020onward')}
    groups = {dim: {g: {k: cell[k] for k in metrics} for (s, d, g), cell in cells.items() if s == 'all' and d == dim}
              for dim in ('global', 'year', 'family', 'product')}
    # Small convenience names are independent review receipt terms, not227 schema.
    for dim_groups in groups.values():
        for cell in dim_groups.values():
            cell['action_rows'], cell['primary_domain_rows'] = cell['action_count'], cell['primary_domain_count']
    return dict(scopes=scopes, cells=cells, metrics=metrics, groups=groups,
        fixed_partitions=dict(year=years, family=families, product=products), anchors=anchor_rows,
        participation_state_counts=dict(participations),
        counts=dict(action_rows=count, primary_domain_rows=scopes['all']['primary_domain_count'],
                    mother_rows=len(parents), nochild_mothers=scopes['all']['nochild_mother_count']))


class HashRead:
    def __init__(self, stream):
        self.stream, self.digest, self.bytes = stream, hashlib.sha256(), 0
    def read(self, n=-1):
        data = self.stream.read(n)
        self.digest.update(data)
        self.bytes += len(data)
        return data


def binding(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write_json(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write('\n')


def check_binding(raw, bound, name):
    if len(raw) != bound['bytes'] or hashlib.sha256(raw).hexdigest() != bound['sha256']:
        raise ValueError('binding differs '+name)


def read_json_bound(path, manifest, role):
    raw = path.read_bytes()
    check_binding(raw, manifest['artifacts'][role], role)
    return json.loads(raw)


def actual(actual_dir, output):
    """One root-triggered review. Fresh destination prevents accidental retry."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    actual_dir = Path(actual_dir).resolve()
    started = time.monotonic()
    write_json(output/'started.json', dict(status='running', started_at=datetime.now(timezone.utc).isoformat(),
        automatic_retry=False, original129_actions_reads=0, original129_mothers_reads=0,
        labels=0, fit=0, cash=0, SQL=0, prices=0))
    try:
        protocol_raw = PROTOCOL.read_bytes()
        if hashlib.sha256(protocol_raw).hexdigest() != PROTOCOL_SHA:
            raise ValueError('frozen226 protocol changed')
        protocol = json.loads(protocol_raw)
        if protocol['actions_usecols'] != RAW_ACTION or protocol['mothers_usecols'] != RAW_MOTHER:
            raise ValueError('frozen raw metadata allowlist differs')
        manifest = json.loads((actual_dir/'manifest.json').read_bytes())
        terminal = json.loads((actual_dir/'terminal.json').read_bytes())
        if terminal.get('status') != 'completed' or terminal.get('exit_code') != 0:
            raise ValueError('227 actual did not complete')
        if manifest['protocol_sha256'] != PROTOCOL_SHA or manifest['input_bindings'] != protocol['input_bindings']:
            raise ValueError('227 frozen source input identity differs')
        # Small reports are hash-bound; full new compressed projections are hashed
        # in the same one pass that independently reads their metadata below.
        artifact_by_name = {Path(b['path']).name: (role, b) for role, b in manifest['artifacts'].items()}
        def small(name):
            role, bound = artifact_by_name[name]
            raw = (actual_dir/name).read_bytes()
            check_binding(raw, bound, name)
            return json.loads(raw)
        summary, anchors, gate, source_receipt = (small(name) for name in (
            'summary.json', 'anchors.json', 'interpretation_gate.json', 'source_read_receipt.json'))
        small('terminal.json')
        expected_io = dict(actions_single_stream_reads_attempted=1, actions_single_stream_reads_completed=1,
            mothers_reads_attempted=1, mothers_reads_completed=1, calendar_reads=1, Y_numeric_reads=0,
            X_reads=0, old_score_prediction_selection_reads=0, old_training_cache_reads=0,
            prices_or_native_cache_reads=0, SQL=0, download=0, large_input_hashes=0, new_label=0, fit=0, cash=0)
        if any(doc.get('counters') != expected_io for doc in (manifest, terminal, summary, source_receipt)):
            raise ValueError('227 exact read budget receipt differs')
        if source_receipt['actions_usecols'] != RAW_ACTION or source_receipt['mothers_usecols'] != RAW_MOTHER:
            raise ValueError('227 original read allowlist differs')
        if source_receipt['before'] != source_receipt['after']:
            raise ValueError('227 original file stat changed')
        for role in ('actions', 'mothers', 'calendar'):
            stat = source_receipt['before'][role]
            bound = protocol['input_bindings'][role]
            if any(stat[k] != bound[k] for k in ('path', 'bytes')) or stat['inherited_sha256'] != bound['sha256'] or stat['rehashed'] is not False:
                raise ValueError('227 original stat/binding receipt differs '+role)
        accepted_raw = Path(protocol['input_bindings']['accepted_dataset_manifest']['path']).read_bytes()
        check_binding(accepted_raw, protocol['input_bindings']['accepted_dataset_manifest'], 'accepted129 small manifest')
        accepted = json.loads(accepted_raw)
        calendar_binding = protocol['input_bindings']['calendar']
        raw = Path(calendar_binding['path']).read_bytes()
        check_binding(raw, calendar_binding, 'calendar')
        import numpy as np
        a = np.load(io.BytesIO(raw), allow_pickle=False)
        calendar = [date(int(d)//10000, int(d)//100 % 100, int(d) % 100).isoformat() for d in a] if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist()
        receipts = {}
        def projected(name, raw_columns):
            path = actual_dir/name
            before = path.stat()
            with path.open('rb') as base:
                hashed = HashRead(base)
                with gzip.GzipFile(fileobj=hashed, mode='rb') as compressed:
                    with io.TextIOWrapper(compressed, encoding='utf8', newline='') as text:
                        reader = csv.DictReader(text)
                        derived_columns = [
                            'D_date', 'D_state', 'K_target_date', 'K_index', 'K_date', 'K_state', 'K_after_sample_end',
                            'calendar_allowed', 'calendar_state', 'primary_domain', 'path_state', 'timing_state',
                            'potential_clock_or_repricing_support', 'known_zero_exposure_before_K', 'unresolved_clock_obscures_no_effect']
                        expected_header = RAW_ACTION+derived_columns if name == 'action_projection.csv.gz' else RAW_MOTHER+MOTHER_COUNTERS+['nochild']
                        if reader.fieldnames != expected_header:
                            raise ValueError('projection exact metadata header differs '+name)
                        for row in reader:
                            yield row
                # Gzip consumes its complete compressed members before EOF.
                sha = hashed.digest.hexdigest()
            after = path.stat()
            role, bound = artifact_by_name[name]
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('projection changed during independent stream')
            if hashed.bytes != bound['bytes'] or sha != bound['sha256']:
                raise ValueError('projected compressed stream binding differs '+name)
            receipts[name] = dict(path=str(path), reads=1, bytes=hashed.bytes, sha256=sha, raw_metadata_columns=raw_columns)
        result = audit_rows(projected('mother_projection.csv.gz', RAW_MOTHER),
            projected('action_projection.csv.gz', RAW_ACTION), calendar, protocol['sample_end'], compare=True,
            expected_mothers=protocol['expected_mothers'], expected_actions=protocol['expected_actions'])
        if summary['fixed_partitions'] != result['fixed_partitions']:
            raise ValueError('fixed original group domain differs')
        if summary['participation_state_counts'] != result['participation_state_counts']:
            raise ValueError('original participation state counts differ')
        independent_labels = {s: result['scopes']['all']['label_'+s+'_count'] for s in LABELS if result['scopes']['all']['label_'+s+'_count']}
        if independent_labels != accepted['counts']['label_states'] or result['counts']['nochild_mothers'] != accepted['counts']['mother_rows_without_children']:
            raise ValueError('accepted129 inherited state/nochild conservation differs')
        columns = summary['metric_columns']
        if set(columns) != set(result['metrics']):
            raise ValueError('summary metric domain differs')
        for scope in ('all', '2020onward'):
            if summary['scopes'][scope] != result['scopes'][scope]:
                raise ValueError('independent global counts differ '+scope)
        for dim in ('year', 'family', 'product'):
            name = 'by_'+dim+'.csv'
            role, bound = artifact_by_name[name]
            raw = (actual_dir/name).read_bytes()
            check_binding(raw, bound, name)
            seen = set()
            for row in csv.DictReader(io.StringIO(raw.decode('utf8'))):
                key = (row['scope'], dim, row['group'])
                if key in seen or key not in result['cells']:
                    raise ValueError('partition cell duplicate/extra '+str(key))
                seen.add(key)
                if any(integer(row[k]) != result['cells'][key][k] for k in columns):
                    raise ValueError('fixed group counts differ '+str(key))
            wanted = {(s, dim, g) for s in ('all', '2020onward') for g in result['fixed_partitions'][dim]}
            if seen != wanted:
                raise ValueError('fixed zero cells dropped '+dim)
        expected_positions = sorted(result['anchors'])
        if anchors['positions'] != expected_positions or anchors['total_actions'] != protocol['expected_actions']:
            raise ValueError('mechanical anchor positions differ')
        for row in anchors['anchors']:
            n = integer(row['sequence_index'])
            if n not in result['anchors']:
                raise ValueError('unexpected anchor')
            expected = result['anchors'].pop(n)
            if any(str(row[k]) != str(expected[k]) for k in RAW_ACTION):
                raise ValueError('anchor original metadata differs')
            equal_metadata(row, {k: v for k, v in expected.items() if k not in RAW_ACTION})
        if result['anchors']:
            raise ValueError('missing mechanical anchors')
        c = result['scopes']['all']
        all_resolved = bool(c['primary_domain_count'] and c['primary_domain_count'] == c['primary_resolved_before_K_count'])
        no_effect = all_resolved and c['calendar_unknown_u_eligible_count'] == 0
        expected_gate = dict(status='stop_fixed_target_axis_no_clock_support' if no_effect else 'potential_or_unresolved_support_only',
            primary_domain_actions=c['primary_domain_count'], potential_support_actions=c['potential_support_count'],
            unresolved_primary_actions=c['unresolved_primary_count'], calendar_unknown_u_eligible_actions=c['calendar_unknown_u_eligible_count'],
            all_primary_paths_resolved_before_K=all_resolved, no_effect_necessary_condition_met=no_effect,
            automatic_Y_K_authorized=False, fit_authorized=False, cash_authorized=False)
        if any(gate.get(k) != v for k, v in expected_gate.items()):
            raise ValueError('interpretation necessary-condition gate differs')
        report = dict(schema='stage228_independent_K_clock_review_v1', status='completed', exit_code=0,
            findings=dict(P0=0, P1=0, P2=0), independent_counts=result['scopes'],
            fixed_partitions=result['fixed_partitions'], mechanical_anchors_reviewed=len(expected_positions),
            no_effect_necessary_condition=no_effect, source_read_receipt_227=source_receipt,
            interpretation_gate_227=gate, new_projection_reads=receipts, calendar_reads=1,
            original_actions_reads=0, original_mothers_reads=0, numeric_Y_reads=0, X_reads=0,
            old_training_cache_reads=0, model_reads=0, cash_reads=0, SQL=0, new_fit=0, new_cash=0,
            cumulative_fit=433, cumulative_cash=234, production_qualified=False, increased_betting_qualified=False,
            goal_complete=False, elapsed_seconds=time.monotonic()-started,
            limitation='Only clock support and metadata arithmetic; not K-price/Y difference, predictability, alpha, or a reopened DOMAIN52.')
        write_json(output/'receipt.json', report)
        write_json(output/'terminal.json', dict(status='completed', exit_code=0, findings=report['findings'],
            elapsed_seconds=time.monotonic()-started, new_fit=0, new_cash=0))
        write_json(output/'manifest.json', dict(schema='stage228_review_manifest_v1',
            inputs=dict(protocol=binding(PROTOCOL), actual_manifest=binding(actual_dir/'manifest.json'),
                        implementation=binding(__file__), tests=binding(Path(__file__).with_name('test_stage228_K_clock_support_review.py'))),
            artifacts={name: binding(output/name) for name in ('started.json', 'receipt.json', 'terminal.json')}))
        return report
    except BaseException:
        write_json(output/'terminal.json', dict(status='failed', exit_code=1, traceback=traceback.format_exc(),
            automatic_retry=False, elapsed_seconds=time.monotonic()-started, new_fit=0, new_cash=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(actual(args.actual_dir, args.output), ensure_ascii=False))
