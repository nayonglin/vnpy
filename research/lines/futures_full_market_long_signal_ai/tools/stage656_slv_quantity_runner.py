"""Frozen653 SLV quantity experiment IO; only root may launch --actual once.

Imports do not read data. --check-source reads only small bindings and file stats.
The actual pass inherits accepted payload SHA identities and verifies stat before/
after each single whitelist read; it never hashes old financial payloads again.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE / 'outputs/stage653_slv_quantity_increment_protocol/protocol.json'
PROTOCOL_SHA = 'bf1fbf5d03b51ea3e2abd3e2536b1106435dfdc754b8617623edadc4651ef680'
OUTPUT_ROOT = LINE / 'outputs/stage656_slv_quantity_increment'
ARMS = ('A', 'B', 'C')
SCOPES = ('main', 'holdout_0', 'holdout_1')
TRAIN = ['sequence_index', 'action_id', 'product_id', 'family_id', 'u_date',
         'u_index', 'u_action_eligible', 'label_state', 'participation_state',
         'label_known_date', 'net_R_stress', 'sample_weight', 'Ahat']
SCORE_FIELDS = ['sequence_index', 'action_id', 'mother_sequence_index',
                'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index',
                'reference_epoch', 'anchor_epoch', 'u_action_eligible', 'score',
                'scope', 'cutoff']
LABELS = ['label_state', 'participation_state', 'net_R_stress', 'label_known_date']
FORWARD = SCORE_FIELDS + LABELS
MOTHER = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date',
          'u_index', 'reference_epoch']
MAP_FIELDS = ['source_id', 'source_date', 'previous_date', 'available_at_utc',
              'P', 'Q', 'pair_valid', 'source_reason']
STAT_FIELDS = ('bytes', 'device', 'inode', 'mtime_ns')


def load_local_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simple(binding):
    return {key: binding[key] for key in ('path', 'bytes', 'sha256')}


def file_stat(path):
    stat = Path(path).stat()
    return dict(bytes=stat.st_size, device=stat.st_dev, inode=stat.st_ino,
                mtime_ns=stat.st_mtime_ns)


def check_stat(path, expected):
    actual = file_stat(path)
    if actual != {key: expected[key] for key in STAT_FIELDS}:
        raise ValueError('accepted source stat differs: ' + str(path))
    return actual


def small_binding(path, limit=2_000_000):
    path = Path(path).resolve()
    if path.stat().st_size > limit:
        raise ValueError('small binding limit exceeded: ' + str(path))
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()), data


def read_bound_json(binding):
    actual, data = small_binding(binding['path'])
    if actual != simple(binding):
        raise ValueError('small JSON binding differs: ' + binding['path'])
    return json.loads(data)


def jsonable(value):
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def output_binding(path):
    """New files only; old payloads must never be passed here."""
    path = Path(path).resolve()
    if OUTPUT_ROOT.resolve() not in path.parents:
        raise ValueError('only new656 artifacts may be hashed here')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(jsonable(value), stream, ensure_ascii=False, sort_keys=True,
                  indent=2, allow_nan=False)
        stream.write('\n')
    return output_binding(path)


def write_frame(path, frame):
    frame.to_csv(path, index=False, mode='x', float_format='%.17g',
                 compression={'method': 'gzip', 'mtime': 0})
    return output_binding(path)


def family_group(family):
    return int(hashlib.sha256(str(family).encode('utf-8')).hexdigest(), 16) % 2


def source_roles(protocol, handoff):
    roles = {}
    for fold in protocol['folds']:
        role = 'train_' + fold['scope'] + '_' + fold['cutoff']
        roles[role] = (fold['train_compact'], fold['stat_snapshot'])
        accepted = next(row for row in handoff['original52_baseline']
                        if (row['scope'], row['cutoff']) == (fold['scope'], fold['cutoff']))
        if simple(fold['train_compact']) != simple(accepted['train_compact']):
            raise ValueError('654/653 train binding differs: ' + role)
    for role in ('forward_base_compact', 'calendar'):
        binding = protocol['inputs'][role]
        if simple(binding) != simple(handoff['core_inputs'][role]):
            raise ValueError('654/653 core binding differs: ' + role)
        roles[role] = (binding, handoff['core_stat_snapshot'][role])
    role = 'mothers_forward'
    if simple(protocol['inputs'][role]) != simple(handoff['optional_full_selection_inputs'][role]):
        raise ValueError('654/653 full mother binding differs')
    roles[role] = (protocol['inputs'][role], handoff['optional_stat_snapshot'][role])
    if simple(protocol['source']) != simple(handoff['source_daily']):
        raise ValueError('654/653 source binding differs')
    roles['slv_source'] = (protocol['source'], handoff['source_stat_snapshot'])
    if len(roles) != 10 or len({b['path'] for b, _ in roles.values()}) != 10:
        raise ValueError('exact ten source roles required')
    return roles


def validate_source_ready(protocol_path, protocol_sha256, ready_path):
    """Read small review/source bindings and stat metadata, never payloads."""
    protocol_binding, data = small_binding(protocol_path)
    if (Path(protocol_binding['path']) != PROTOCOL.resolve()
            or protocol_sha256 != PROTOCOL_SHA
            or protocol_binding['sha256'] != PROTOCOL_SHA):
        raise ValueError('exact frozen653 protocol required')
    protocol = json.loads(data)
    if protocol['schema'] != 'stage653_slv_quantity_increment_protocol_v1':
        raise ValueError('wrong653 schema')
    ready_binding, ready_data = small_binding(ready_path)
    ready = json.loads(ready_data)
    if ready.get('schema') != 'stage656_slv_quantity_source_ready_v1':
        raise ValueError('wrong656 source-ready schema')
    if simple(ready['protocol']) != protocol_binding:
        raise ValueError('source-ready protocol differs')
    for name, frozen in [('input_handoff', protocol['input_handoff']),
                         ('method_notes', protocol['method_notes'])]:
        if simple(ready[name]) != simple(frozen):
            raise ValueError('source-ready small input differs: ' + name)
    handoff = read_bound_json(protocol['input_handoff'])
    read_bound_json(protocol['method_notes'])
    review = read_bound_json(ready['method_review'])
    if (review.get('schema') != 'stage655_frozen653_protocol_review_v1'
            or review.get('method_GO') is not True
            or review['stage653_protocol']['sha256'] != PROTOCOL_SHA
            or review.get('reviewed_before_new_Y') is not True
            or review.get('financial_payload_reads') != 0):
        raise ValueError('655 frozen protocol pre-review is not GO')
    required = {str((TOOLS / name).resolve()) for name in
                ('stage656_slv_quantity_runner.py', 'stage656_slv_quantity_kernel.py',
                 'test_stage656_slv_quantity_kernel.py', 'stage156_voluntary_choices.py')}
    sources = ready['sources']
    if len({binding['path'] for binding in sources}) != len(sources):
        raise ValueError('duplicate source-ready source path')
    if not required.issubset({binding['path'] for binding in sources}):
        raise ValueError('source-ready lacks runner/kernel/fixture/original selector')
    for binding in sources:
        actual, _ = small_binding(binding['path'])
        if actual != simple(binding):
            raise ValueError('source changed since ready: ' + binding['path'])
    fixture = read_bound_json(ready['fixture_receipt'])
    if fixture.get('status') not in ('passed', 'completed') or fixture.get('exit_code') != 0:
        raise ValueError('new656 fixture receipt is not passing')
    roles = source_roles(protocol, handoff)
    stats = {role: check_stat(binding['path'], expected)
             for role, (binding, expected) in roles.items()}
    return dict(protocol=protocol, protocol_binding=protocol_binding,
                ready=ready, ready_binding=ready_binding, handoff=handoff,
                source_roles=roles, checked_stats=stats)


def validate_source_go(path, state):
    binding, data = small_binding(path)
    go = json.loads(data)
    if (go.get('schema') != 'stage655_slv_source_go_v1'
            or go.get('source_GO') is not True
            or simple(go['protocol']) != state['protocol_binding']
            or simple(go['source_ready']) != state['ready_binding']
            or any(go.get(key) != 0 for key in ('preactual_payload_reads', 'fit', 'cash'))):
        raise ValueError('655 exact source GO required before actual')
    read_bound_json(go['reviewer_ready'])
    return binding, go


class SinglePassInputs:
    def __init__(self, roles):
        self.roles = roles
        self.records = {}

    def read_table(self, role, columns, numeric=()):
        if role in self.records:
            raise ValueError('old source read attempted twice: ' + role)
        binding, expected = self.roles[role]
        before = check_stat(binding['path'], expected)
        record = dict(role=role, accepted_binding=simple(binding), stat_before=before,
                      read_passes_attempted=1, read_passes_completed=0,
                      separate_payload_hash_passes=0, columns=list(columns))
        self.records[role] = record
        chunks = []
        with pd.read_csv(binding['path'], compression='gzip', dtype=str,
                         keep_default_na=False, usecols=list(columns),
                         chunksize=100_000) as reader:
            for chunk in reader:
                chunk = chunk.loc[:, columns]
                for name in numeric:
                    chunk[name] = pd.to_numeric(chunk[name], errors='raise')
                chunks.append(chunk)
        frame = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
        record.update(stat_after=check_stat(binding['path'], expected),
                      read_passes_completed=1, rows=len(frame))
        return frame

    def read_calendar(self):
        role = 'calendar'
        if role in self.records:
            raise ValueError('calendar read twice')
        binding, expected = self.roles[role]
        before = check_stat(binding['path'], expected)
        self.records[role] = dict(role=role, accepted_binding=simple(binding),
                                  stat_before=before, read_passes_attempted=1,
                                  read_passes_completed=0, separate_payload_hash_passes=0)
        data = Path(binding['path']).read_bytes()
        if len(data) != binding['bytes'] or hashlib.sha256(data).hexdigest() != binding['sha256']:
            raise ValueError('calendar bytes differ')
        calendar = json.loads(data)
        if len(calendar) != 5587 or calendar != sorted(set(calendar)):
            raise ValueError('immutable full source calendar differs')
        self.records[role].update(stat_after=check_stat(binding['path'], expected),
                                  read_passes_completed=1, rows=len(calendar),
                                  sha256_checked_in_same_read=True)
        return calendar

    def verify_final_stats(self):
        for role, (binding, expected) in self.roles.items():
            final = check_stat(binding['path'], expected)
            if role in self.records:
                self.records[role]['stat_at_terminal'] = final


def add_source_map(frame, mapping, calendar):
    index = frame.u_index.to_numpy(float)
    if (not np.isfinite(index).all() or not np.equal(index, np.floor(index)).all()
            or (index < 0).any() or (index >= len(calendar)).any()):
        raise ValueError('finite integral in-calendar u_index required')
    index = index.astype(np.int64)
    if frame.u_date.tolist() != [calendar[i] for i in index]:
        raise ValueError('literal u_date/calendar identity differs')
    mapped = mapping.iloc[index].reset_index(drop=True)
    if mapped.u_index.tolist() != index.tolist() or mapped.u_date.tolist() != frame.u_date.tolist():
        raise ValueError('source-calendar map is not full immutable calendar')
    return pd.concat([frame.reset_index(drop=True), mapped[MAP_FIELDS]], axis=1)


def validate_train(train, fold):
    cutoff, scope = fold['cutoff'], fold['scope']
    if (len(train) != fold['training_check']['training_rows']
            or train.action_id.duplicated().any() or train.sequence_index.duplicated().any()):
        raise ValueError('accepted own training row identity differs')
    if not (train.u_action_eligible.eq(1)
            & train.label_state.eq('closed_complete_bar_model')
            & train.u_date.lt(cutoff) & train.label_known_date.ne('')
            & train.label_known_date.lt(cutoff)).all():
        raise ValueError('accepted original mature training domain differs')
    values = train[['sample_weight', 'net_R_stress', 'Ahat']].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 0] <= 0).any():
        raise ValueError('finite training inputs/positive inherited weight required')
    if (train.u_date.max() != fold['training_check']['max_u_date']
            or train.label_known_date.max() != fold['training_check']['max_label_known_date']
            or train.u_date.nunique() != fold['training_check']['training_dates']
            or train.family_id.nunique() != fold['training_check']['training_families']):
        raise ValueError('inherited training coverage/maturity differs')
    if scope != 'main' and train.family_id.map(family_group).eq(int(scope[-1])).any():
        raise ValueError('held-family label leakage')


def validate_forward(forward, mothers, protocol):
    if (len(forward) != protocol['scope']['forward_child_rows']
            or forward.duplicated(['scope', 'cutoff', 'action_id']).any()
            or not np.isfinite(forward.score).all()
            or not forward.u_action_eligible.isin((0, 1)).all()):
        raise ValueError('complete frozen forward child domain differs')
    if (len(mothers) != protocol['scope']['mothers_per_complete_main_or_combined_held']
            or mothers.sequence_index.duplicated().any() or mothers.event_id.duplicated().any()
            or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95):
        raise ValueError('full98/95 mother identity differs')
    expected_cutoff = np.where(forward.u_date.lt('2023-01-01'), '2020-01-01', '2023-01-01')
    if (set(forward.scope) != set(SCOPES)
            or not np.array_equal(forward.cutoff.to_numpy(), expected_cutoff)
            or not forward.u_date.between('2020-01-01', protocol['scope']['forward_end']).all()):
        raise ValueError('scope/cutoff deployment differs')
    for fold in protocol['folds']:
        selected = forward.scope.eq(fold['scope']) & forward.cutoff.eq(fold['cutoff'])
        if int(selected.sum()) != fold['prediction_children']:
            raise ValueError('own-fold forward count differs')
        if fold['scope'] != 'main' and not forward.loc[selected, 'family_id'].map(family_group).eq(int(fold['scope'][-1])).all():
            raise ValueError('forward own-held family scope differs')
    main = forward.loc[forward.scope.eq('main')]
    held = forward.loc[forward.scope.ne('main')]
    if (main.action_id.duplicated().any() or held.action_id.duplicated().any()
            or set(main.action_id) != set(held.action_id)):
        raise ValueError('main/held complete child coverage differs')
    linked = main.merge(held[['action_id', *LABELS]], on='action_id',
                        validate='one_to_one', suffixes=('', '_held'))
    for name in LABELS:
        left, right = linked[name], linked[name + '_held']
        if not (left.eq(right) | (left.isna() & right.isna())).all():
            raise ValueError('scope target literals differ: ' + name)


def choose_all(forward, mothers, calendar, end):
    """Reuse exact original156 eligibility, rank/tie and family priority rules."""
    selector = load_local_module('slv656_original156', 'stage156_voluntary_choices.py')
    results, records = [], []
    for scope in SCOPES:
        children = forward.loc[forward.scope.eq(scope)]
        parents = mothers if scope == 'main' else mothers.loc[mothers.family_id.map(family_group).eq(int(scope[-1]))]
        parent_records = parents.to_dict('records')
        for arm in ARMS:
            score_column = 'score' if arm == 'A' else arm + '_score'
            fields = children[SCORE_FIELDS].copy()
            fields['score'] = children[score_column].to_numpy()
            fields['scope'] = 'main'  # original156 accepts exactly one aliased scope
            columns = fields.columns.tolist()
            rows = (dict(zip(columns, values)) for values in fields.itertuples(index=False, name=None))
            result = selector.select_full_pool(parent_records, rows, calendar, end,
                                               audit_sink=lambda _: None)
            choices = pd.DataFrame(result['choices'])
            choices['scope'], choices['arm'] = scope, arm
            results.append(choices)
            records.append(dict(scope=scope, arm=arm, summary=result['summary']))
            print(json.dumps(dict(phase='selection_complete', scope=scope, arm=arm,
                                  mothers=len(choices), selected=int(choices.selected.sum()))), flush=True)
    choices = pd.concat(results, ignore_index=True)
    for kind, part in [('main', choices.loc[choices.scope.eq('main')]),
                       ('held_union', choices.loc[choices.scope.ne('main')])]:
        if len(part) != 3 * len(mothers) or part.duplicated(['arm', 'event_id']).any():
            raise ValueError('full three-arm mother domain differs: ' + kind)
        for arm in ARMS:
            if set(part.loc[part.arm.eq(arm), 'event_id']) != set(mothers.event_id):
                raise ValueError('mother identities shrunk: ' + kind + '/' + arm)
    return choices, records


def run_actual(args, state):
    if not args.source_go:
        raise ValueError('--source-go required for root-only actual')
    go_binding, go = validate_source_go(args.source_go, state)
    output = Path(args.output).resolve()
    if OUTPUT_ROOT.resolve() not in output.parents or output.exists():
        raise ValueError('fresh directory below656 output root required')
    output.mkdir(parents=True)
    started = time.monotonic()
    artifacts, heads, fit_counts = {}, {}, dict(attempted=0, completed=0)
    protocol = state['protocol']
    inputs = SinglePassInputs(state['source_roles'])
    source_bindings = state['ready']['sources']
    kernel = load_local_module('slv656_kernel', 'stage656_slv_quantity_kernel.py')

    def event(filename, value):
        with (output / filename).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()

    artifacts['started'] = write_json(output / 'started.json',
        dict(schema='stage656_slv_started_v1', status='started',
             started_utc=datetime.now(timezone.utc).isoformat(),
             protocol=state['protocol_binding'], source_ready=state['ready_binding'],
             source_go=go_binding, automatic_retry=False, original_payload_rehashes=0,
             base_refits=0, cash=0, SQL=0, network=0))
    try:
        calendar = inputs.read_calendar()
        source = inputs.read_table('slv_source', protocol['source_columns'])
        if len(source) != 5160:
            raise ValueError('all5160 original source rows required')
        pairs = kernel.build_source_pairs(source.to_dict('records'))
        mapping = kernel.map_source_to_calendar(pairs, calendar)
        if (len(pairs) != 5160 or len(mapping) != len(calendar)
                or mapping.u_index.tolist() != list(range(len(calendar)))
                or mapping.u_date.tolist() != calendar):
            raise ValueError('source/map completeness differs')
        artifacts['source_pairs'] = write_frame(output / 'source_pairs.csv.gz', pairs)
        artifacts['source_calendar'] = write_frame(output / 'source_calendar.csv.gz', mapping)
        for fold in protocol['folds']:
            scope, cutoff = fold['scope'], fold['cutoff']
            role = 'train_' + scope + '_' + cutoff
            train = inputs.read_table(role, TRAIN,
                ['sequence_index', 'u_index', 'u_action_eligible', 'net_R_stress', 'sample_weight', 'Ahat'])
            validate_train(train, fold)
            train = add_source_map(train, mapping, calendar)
            artifacts[role] = write_frame(output / (role + '.csv.gz'), train)

            def on_fit(arm):
                if arm not in ('B', 'C') or fit_counts['attempted'] >= 12:
                    raise ValueError('fixed twelve-fit budget exceeded')
                fit_counts['attempted'] += 1
                event('fit_journal.jsonl', dict(event='attempted', scope=scope,
                    cutoff=cutoff, arm=arm, attempt=fit_counts['attempted']))

            fitted = kernel.fit_heads(train, scope, cutoff, on_fit=on_fit)
            if set(fitted) != {'B', 'C'}:
                raise ValueError('exact two nested residual heads required')
            for arm in ('B', 'C'):
                head = fitted[arm]
                heads[(scope, cutoff, arm)] = head
                name = 'head_' + scope + '_' + cutoff + '_' + arm
                artifacts[name] = write_json(output / (name + '.json'), head)
                fit_counts['completed'] += 1
                event('fit_journal.jsonl', dict(event='completed', scope=scope,
                    cutoff=cutoff, arm=arm, completed=fit_counts['completed']))
            print(json.dumps(dict(phase='fold_complete', scope=scope, cutoff=cutoff,
                                  completed_fit_calls=fit_counts['completed'])), flush=True)
            del train

        forward = inputs.read_table('forward_base_compact', FORWARD,
            ['sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible', 'score', 'net_R_stress'])
        mothers = inputs.read_table('mothers_forward', MOTHER, ['sequence_index', 'u_index'])
        validate_forward(forward, mothers, protocol)
        forward = add_source_map(forward, mapping, calendar)
        mothers = add_source_map(mothers, mapping, calendar)
        forward['B_score'] = np.nan
        forward['C_score'] = np.nan
        for fold in protocol['folds']:
            scope, cutoff = fold['scope'], fold['cutoff']
            mask = forward.scope.eq(scope) & forward.cutoff.eq(cutoff)
            part = forward.loc[mask]
            for arm in ('B', 'C'):
                predictions = kernel.predict_scores(part.score.to_numpy(float),
                    part.P.to_numpy(float), part.Q.to_numpy(float),
                    part.pair_valid.to_numpy(), heads[(scope, cutoff, arm)])
                if len(predictions) != len(part) or not np.isfinite(predictions).all():
                    raise ValueError('complete finite own-fold prediction required')
                forward.loc[mask, arm + '_score'] = predictions
        unavailable = ~forward.pair_valid.astype(bool).to_numpy()
        for arm in ('B', 'C'):
            if not np.array_equal(forward.loc[unavailable, arm + '_score'].to_numpy(float).view(np.uint64),
                                  forward.loc[unavailable, 'score'].to_numpy(float).view(np.uint64)):
                raise ValueError('unavailable input not bitwise A fallback')
        artifacts['forward_thin'] = write_frame(output / 'forward_thin.csv.gz', forward)
        # Source-mapped mother literals let the independent reviewer retain zero-child rows.
        artifacts['mothers_thin'] = write_frame(output / 'mothers_thin.csv.gz', mothers)
        choices, records = choose_all(forward, mothers[MOTHER], calendar, protocol['scope']['forward_end'])
        stats = kernel.policy_statistics(choices, forward, mapping, calendar,
                                         end=protocol['scope']['forward_end'])
        for name, key in [('choices', 'choices'), ('source_group_statistics', 'group_stats'),
                          ('action_MSE', 'action_MSE'), ('annual', 'annual'),
                          ('family_coverage', 'family_coverage')]:
            artifacts[name] = write_frame(output / (name + '.csv.gz'), stats[key])
        for era in ('early', 'late'):
            path = output / ('bootstrap_indices_' + era + '.npy')
            with path.open('xb') as stream:
                np.save(stream, np.asarray(stats['indices'][era]), allow_pickle=False)
            artifacts['bootstrap_indices_' + era] = output_binding(path)
        artifacts['bootstrap_grids'] = write_json(output / 'bootstrap_grids.json', stats['grids'])
        artifacts['selection_records'] = write_json(output / 'selection_records.json', records)
        artifacts['gate'] = write_json(output / 'gate.json', stats['gate'])
        if fit_counts != dict(attempted=12, completed=12):
            raise ValueError('exact twelve actual fit calls required')
        if set(inputs.records) != set(state['source_roles']):
            raise ValueError('exact ten original inputs must each be read once')
        inputs.verify_final_stats()
        financial_bytes = sum(record['accepted_binding']['bytes'] for role, record in inputs.records.items()
                              if role not in ('slv_source', 'calendar'))
        if financial_bytes != protocol['implementation']['compressed_financial_read_budget']:
            raise ValueError('single-pass compressed financial budget differs')
        # These are only small result-before/source JSON receipts and code.
        # Rechecking them must never become a second old payload pass.
        small_inputs = [state['protocol_binding'], protocol['input_handoff'],
            protocol['method_notes'], state['ready']['method_review'],
            state['ready']['fixture_receipt'], state['ready_binding'],
            go_binding, go['reviewer_ready']]
        for binding in source_bindings + small_inputs:
            if small_binding(binding['path'])[0] != simple(binding):
                raise ValueError('result-before/source binding changed during actual: ' + binding['path'])
        artifacts['source_io_receipt'] = write_json(output / 'source_io_receipt.json',
            dict(schema='stage656_single_pass_io_v1', records=inputs.records,
                 compressed_financial_bytes=financial_bytes, separate_old_payload_hash_passes=0,
                 model_reads=0, scaler_reads=0, COMMON_reads=0, native_reads=0,
                 old_choice_reads=0, SQL=0, network=0, original_source_mutations=False))
        summary = dict(stats['summary'])
        summary.update(status='completed', actual_fit_calls_attempted=12,
            actual_fit_calls_completed=12, base_refits=0, new_cash=0, SQL=0, network=0,
            full_forward_rows=len(forward), main_mothers=len(mothers),
            registered_products=98, registered_families=95,
            old_choices_read=False, old_offsets_consumed=False,
            goal_complete=False, production_qualified=False, increased_betting_qualified=False)
        artifacts['summary'] = write_json(output / 'summary.json', summary)
        artifacts['fit_journal'] = output_binding(output / 'fit_journal.jsonl')
        terminal = dict(schema='stage656_slv_terminal_v1', status='completed', exit_code=0,
            actual_fit_calls_attempted=12, actual_fit_calls_completed=12,
            base_refits=0, cash=0, SQL=0, network=0, automatic_retry=False,
            elapsed_seconds=time.monotonic() - started, goal_complete=False)
        artifacts['terminal'] = write_json(output / 'terminal.json', terminal)
        write_json(output / 'manifest.json', dict(schema='stage656_slv_quantity_actual_v1',
            status='completed', protocol=state['protocol_binding'],
            source_ready=state['ready_binding'], source_go=go_binding,
            sources=source_bindings, artifacts=artifacts,
            actual_fit_calls_attempted=12, actual_fit_calls_completed=12,
            base_refits=0, cash=0, SQL=0, network=0, goal_complete=False,
            production_qualified=False, increased_betting_qualified=False))
        return terminal
    except BaseException as error:
        if not (output / 'terminal.json').exists():
            artifacts['terminal'] = write_json(output / 'terminal.json', dict(schema='stage656_slv_terminal_v1',
                status='failed', exit_code=1, actual_fit_calls_attempted=fit_counts['attempted'],
                actual_fit_calls_completed=fit_counts['completed'], base_refits=0, cash=0,
                SQL=0, network=0, automatic_retry=False, error_type=type(error).__name__,
                error=str(error), traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - started, source_io_records=inputs.records))
        if not (output / 'manifest.json').exists():
            write_json(output / 'manifest.json', dict(schema='stage656_slv_quantity_actual_v1',
                status='failed', protocol=state['protocol_binding'],
                source_ready=state['ready_binding'], source_go=go_binding,
                sources=source_bindings, artifacts=artifacts,
                actual_fit_calls_attempted=fit_counts['attempted'],
                actual_fit_calls_completed=fit_counts['completed'], base_refits=0,
                cash=0, SQL=0, network=0, automatic_retry=False, goal_complete=False))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=PROTOCOL)
    parser.add_argument('--protocol-sha256', default=PROTOCOL_SHA)
    parser.add_argument('--source-ready', type=Path, required=True)
    parser.add_argument('--source-go', type=Path)
    parser.add_argument('--output', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-source', action='store_true')
    mode.add_argument('--actual', action='store_true')
    args = parser.parse_args(argv)
    state = validate_source_ready(args.protocol, args.protocol_sha256, args.source_ready)
    if args.check_source:
        print(json.dumps(dict(status='source_checked', financial_payload_reads=0,
            model_reads=0, scaler_reads=0, actual_fit=0, cash=0,
            protocol=state['protocol_binding'], source_ready=state['ready_binding'],
            source_roles=len(state['source_roles'])), ensure_ascii=False), flush=True)
        return
    if args.output is None:
        parser.error('--actual requires --output')
    print(json.dumps(jsonable(run_actual(args, state)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
