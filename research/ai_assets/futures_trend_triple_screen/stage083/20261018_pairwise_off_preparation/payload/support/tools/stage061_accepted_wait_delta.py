"""Freeze terminal Stage036 committed deliveries; append with exact usage rights.

This module never runs a provider, model, account engine, or financial replay.
Numerical imports are lazy: configure Stage022's frozen runtime first. The only
supported terminal contract is the real Stage063 failed B_TS owner contract.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile

VALUES = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']
FIELDS = ['vt_symbol', 'bar_datetime', *VALUES]
MANIFEST_SCHEMA = 'stage061_accepted_wait_delta_manifest_v1'
REVIEW_SCHEMA = 'stage061_independent_wait_delta_review_v1'
CACHE_NAMES = ('_FULL_MINUTE_BY_SYMBOL_CACHE', '_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS', '_LAST_MINUTE_AUDIT')
DELIVERY_PARSER_SOURCE_SHA256 = '150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _payload(path, payloads):
    """Read each actually consumed object once; parsers never reopen its path."""
    path = Path(path)
    key = str(path)
    if key not in payloads:
        if not path.is_absolute() or path.is_symlink():
            raise ValueError(f'consumed_source_absolute_non_symlink_required:{path}')
        payloads[key] = path.read_bytes()
    return payloads[key]


def _bound_payload(path, expected, sources, payloads, owner=None):
    path = Path(path)
    key = str(path)
    if not path.is_absolute() or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f'source_absolute_path_and_sha_required:{path}')
    if owner is not None and owner.get(key, {}).get('sha256') != expected:
        raise ValueError(f'terminal_source_mismatch:{path}')
    if key in sources and sources[key] != expected:
        raise ValueError(f'source_identity_mismatch:{path}')
    payload = _payload(path, payloads)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f'source_hash_changed:{path}')
    sources[key] = expected
    return payload


def _json(path, expected, sources, payloads, owner=None):
    return json.loads(_bound_payload(path, expected, sources, payloads, owner))


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def _bind(path, expected, sources, owner=None):
    path = Path(path)
    if not path.is_absolute() or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f'source_absolute_path_and_sha_required:{path}')
    key = str(path)
    if owner is not None and owner.get(key, {}).get('sha256') != expected:
        raise ValueError(f'terminal_source_mismatch:{path}')
    if key in sources:
        if sources[key] != expected:
            raise ValueError(f'source_identity_mismatch:{path}')
    else:
        if sha256(path) != expected:
            raise ValueError(f'source_hash_changed:{path}')
        sources[key] = expected
    return path


def _numerical():
    # Refuse an accidental local numerical stack, even when used as a library.
    import sys
    import stage022_run_c0_qualified_wait as runtime
    for name in ('numpy', 'pandas'):
        loaded = sys.modules.get(name)
        if loaded is not None and not Path(loaded.__file__).resolve().is_relative_to(runtime.FROZEN_SITE):
            raise RuntimeError(f'numerical_package_imported_before_frozen_runtime:{name}')
    if str(runtime.FROZEN_SITE) not in sys.path:
        raise RuntimeError('configure_stage022_frozen_runtime_first')
    import numpy as np
    import pandas as pd
    import stage021_blocking_data_gate as gate
    return np, pd, gate


def _key(symbol, stamp):
    # Public entry points already enforce the frozen runtime. Do not repeat
    # filesystem/runtime checks for every minute key in a large accepted layer.
    import pandas as pd
    stamp = pd.Timestamp(stamp)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert('Asia/Shanghai').tz_localize(None)
    return str(symbol), stamp


def _keys(frame):
    return {_key(row.vt_symbol, row.bar_datetime) for row in frame[['vt_symbol', 'bar_datetime']].itertuples(index=False)}


def _read_delivery_bytes(request, delivery, sources, payloads, owner):
    """Stage021 _read_delivery contract, changed only to consume pinned bytes.

    Based on the unchanged Stage021 source at DELIVERY_PARSER_SOURCE_SHA256.
    The original parser has no bytes interface and reopens its receipt path.
    Keep its qualification/scope/numeric checks here; never patch the old gate.
    """
    np, pd, gate = _numerical()
    if not isinstance(delivery, gate.QualifiedDelivery):
        raise ValueError('independent_qualified_delivery_required')
    receipt_path = Path(delivery.receipt_path)
    receipt = _json(receipt_path, delivery.receipt_sha256, sources, payloads, owner)
    if (receipt.get('schema') != gate.RECEIPT_SCHEMA or receipt.get('independent_review') is not True
            or not receipt.get('reviewer') or receipt.get('qualified_research_data') is not True
            or receipt.get('p0_findings', 0) or receipt.get('p1_findings', 0)):
        raise ValueError('independent_data_qualification_missing')
    if receipt.get('request_sha256') != request['request_sha256']:
        raise ValueError('delivery_request_hash_mismatch')
    wanted = {(item['vt_symbol'], item['execution_trade_date'], item['requirement_kind']): item
        for item in request['requirements']}
    accepted, allowed, full, anchors = {}, set(), set(), set()
    for item in receipt['accepted_requirements']:
        identity = (str(item['vt_symbol']), str(item['execution_trade_date']), item['requirement_kind'])
        if identity in accepted or identity not in wanted:
            raise ValueError('delivery_accepted_scope_mismatch')
        if item.get('accepted') is not True or item.get('completed_bars_and_daily_qualified') is not True:
            raise ValueError('delivery_completion_and_daily_qualification_missing')
        if item['accepted_timestamps'] != wanted[identity]['required_timestamps']:
            raise ValueError('delivery_accepted_timestamp_scope_mismatch')
        scoped = {(identity[0], pd.Timestamp(stamp)) for stamp in item['accepted_timestamps']}
        allowed.update(scoped)
        (full if identity[2] == 'full_session' else anchors).update(scoped)
        accepted[identity] = item
    if set(accepted) != set(wanted):
        raise ValueError('delivery_accepted_scope_incomplete')
    data_path, data_sha = Path(receipt['data_path']), receipt['data_sha256']
    if not data_path.is_absolute() or receipt.get('source_fingerprints', {}).get(str(data_path)) != data_sha:
        raise ValueError('delivery_data_source_not_bound')
    payload = _bound_payload(data_path, data_sha, sources, payloads, owner)
    data = gate.old.normal_times(pd.read_csv(io.BytesIO(payload)))
    if not set(FIELDS).issubset(data.columns) or gate.old.minute_keys(data).has_duplicates or gate._keys(data) != allowed:
        raise ValueError('delivery_raw_scope_or_uniqueness_mismatch')
    numeric = data[VALUES].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (data[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise ValueError('delivery_invalid_numeric_values')
    if ((data[['volume', 'open_oi', 'close_oi']] < 0).any().any()
            or (data.low > data[['open', 'close']].min(axis=1)).any()
            or (data.high < data[['open', 'close']].max(axis=1)).any()):
        raise ValueError('delivery_invalid_OHLCV_OI')
    return data[FIELDS].copy(), full, anchors, dict(receipt_path=str(receipt_path),
        receipt_sha256=delivery.receipt_sha256, data_path=str(data_path), data_sha256=data_sha,
        reviewer=receipt['reviewer'], accepted_keys=len(allowed))


def _terminal_failure(run_facts, facts_sha, terminal_path, terminal_sha, base_stack, base_sha, sources, payloads):
    facts_path, terminal_path = Path(run_facts), Path(terminal_path)
    facts = _json(facts_path, facts_sha, sources, payloads)
    terminal = _json(terminal_path, terminal_sha, sources, payloads)
    if terminal.get('schema') != 'stage063_B_TS_actual_tool_failure_terminal_v1':
        raise ValueError('unsupported_terminal_contract_success_or_journal')
    code = terminal.get('financial_exit_code')
    if (terminal.get('financial_terminal_observed') is not True or isinstance(code, bool)
            or not isinstance(code, int) or code == 0
            or not terminal.get('financial_tool_terminal_chunk_id')
            or not isinstance(terminal.get('financial_tool_session_id'), int)
            or terminal['financial_tool_session_id'] <= 0
            or not isinstance(terminal.get('engine_pid_at_start'), int)
            or terminal['engine_pid_at_start'] <= 0):
        raise ValueError('true_financial_failure_terminal_required')
    if (facts_path.name != 'run_failure.json' or terminal.get('run_failure_path') != str(facts_path)
            or terminal.get('run_failure_sha256') != facts_sha
            or facts.get('status') != 'failed_closed_no_accepted_performance'
            or facts.get('arm') != 'B_TS' or facts.get('attempt') != 1
            or not facts.get('run_id') or facts.get('production_qualified') is not False):
        raise ValueError('terminal_owner_failure_identity_mismatch')
    owner = facts['input_fingerprints']
    context_path = facts_path.parent / 'run_context.json'
    context_sha = hashlib.sha256(_payload(context_path, payloads)).hexdigest()
    context = _json(context_path, context_sha, sources, payloads)
    if (context.get('schema') != 'stage036_run_context_v1'
            or any(context.get(k) != facts.get(k) for k in ('run_id', 'arm', 'attempt', 'started_at'))
            or context.get('output_directory') != str(facts_path.parent)
            or any(terminal.get(k) != facts.get(k) for k in ('started_at', 'failed_at'))):
        raise ValueError('terminal_run_context_mismatch')
    runner_sha = terminal.get('runner_source_sha256')
    if (runner_sha != terminal.get('used_runner_sha256') or runner_sha != context.get('writer_source_sha256')
            or context.get('writer') != 'stage036_run_b_ts_checkpoint.py'):
        raise ValueError('terminal_runner_identity_mismatch')
    _bind(terminal['runner_source_path'], runner_sha, sources)
    _bind(facts_path.parent / 'runner_used.py', runner_sha, sources)
    stack = _json(base_stack, base_sha, sources, payloads, owner)
    if (facts.get('data_stack_sha256') != base_sha
            or stack.get('schema') != 'stage022_qualified_data_stack_v1'
            or stack.get('append_order') != ['002', '011', '015', '020']):
        raise ValueError('original_base_stack_identity_mismatch')
    # Identity-only inheritance: no old price aggregation or recertification.
    inherited = facts.get('reused_anchor', {})
    anchors = inherited.get('deliveries', [])
    if inherited.get('exact_anchor_keys') != 2 or inherited.get('full_session_keys') != 0 or len(anchors) != 2:
        raise ValueError('original_two_anchor_identity_required')
    for item in anchors:
        for kind in ('request', 'receipt', 'data'):
            path = item[kind + '_path']
            expected = owner.get(path, {}).get('sha256') if kind == 'request' else item[kind + '_sha256']
            _bind(path, expected, sources, owner)
    gates, resolvers = facts['qualified_wait_gate_audit'], facts['resolver_audit']
    if 'gate_event_counts' in terminal and dict(Counter(row['event'] for row in gates)) != terminal['gate_event_counts']:
        raise ValueError('terminal_gate_event_counts_mismatch')
    if 'resolver_wait_records' in terminal and len(resolvers) != terminal['resolver_wait_records']:
        raise ValueError('terminal_resolver_count_mismatch')
    snapshot = dict(schema='stage061_source_terminal_snapshot_v1', run_id=facts['run_id'],
        run_facts_path=str(facts_path), run_facts_sha256=facts_sha,
        terminal_evidence_path=str(terminal_path), terminal_sha256=terminal_sha,
        terminal=dict(financial_tool_session_id=terminal['financial_tool_session_id'],
            engine_pid_at_start=terminal['engine_pid_at_start'], financial_exit_code=code,
            financial_terminal_observed=True), run_context=context,
        run_context_path=str(context_path), run_context_sha256=sources[str(context_path)],
        runner_source_path=terminal['runner_source_path'], runner_source_sha256=runner_sha,
        base_stack_path=str(base_stack), base_stack_sha256=base_sha,
        inherited_anchor_inputs=anchors, accepted_audit=None,
        qualification_scope='committed_delivery_only_not_financial_qualification')
    return facts, snapshot


def freeze_accepted_delta(*, run_facts, run_facts_sha256, terminal_evidence, terminal_sha256,
                          base_stack, base_stack_sha256, output):
    """Create one new frozen candidate; reject drift, ambiguity, and overwrites."""
    np, pd, gate = _numerical()
    output = Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'existing_frozen_delta_refusing_overwrite:{output}')
    sources, payloads = {}, {}
    facts, snapshot = _terminal_failure(Path(run_facts), run_facts_sha256,
        Path(terminal_evidence), terminal_sha256, Path(base_stack), base_stack_sha256, sources, payloads)
    gates, resolvers = facts['qualified_wait_gate_audit'], facts['resolver_audit']
    by_request = {}
    for row in resolvers:
        digest = row['request_sha256']
        if digest in by_request:
            raise ValueError('ambiguous_duplicate_resolver_request')
        by_request[digest] = row
    failed = {row['request_sha256'] for row in gates if row['event'] == 'data_gate_failed'}
    commits = [(index, row) for index, row in enumerate(gates) if row['event'] == 'data_qualified_appended']
    if len({row['request_sha256'] for _, row in commits}) != len(commits):
        raise ValueError('ambiguous_duplicate_gate_commit')
    deliveries, seen, excluded, values, rights = [], set(), [], {}, {}
    for index, event in commits:
        digest = event['request_sha256']; pointer = by_request.get(digest)
        if digest in failed or pointer is None or pointer.get('status') != 'qualified_delivery_pointer_accepted':
            continue
        if event.get('old_keys_changed') != 0 or isinstance(event.get('old_keys_changed'), bool):
            raise ValueError('gate_old_key_mutation_not_reusable')
        for field in ('receipt_path', 'receipt_sha256', 'data_path', 'data_sha256'):
            if event.get(field) != pointer.get(field):
                raise ValueError(f'dual_record_identity_mismatch:{field}:{digest}')
        owner = facts['input_fingerprints']
        for path_field, sha_field in (('request_path', 'request_file_sha256'), ('response_path', 'response_sha256'),
                                     ('receipt_path', 'receipt_sha256'), ('data_path', 'data_sha256')):
            _bound_payload(pointer[path_field], pointer[sha_field], sources, payloads, owner)
        request_path = Path(pointer['request_path'])
        if request_path.parent != Path(run_facts).parent / 'data_wait' / ('request_' + digest):
            raise ValueError('delivery_not_owned_by_terminal_run')
        request = _json(request_path, pointer['request_file_sha256'], sources, payloads, owner)
        if request.get('schema') != gate.REQUEST_SCHEMA or request.get('request_sha256') != digest or gate.request_sha256(request) != digest:
            raise ValueError('canonical_request_hash_mismatch')
        requested = [row for row in gates[:index] if row['event'] == 'data_requested' and row['request_sha256'] == digest]
        if len(requested) != 1 or requested[0].get('request_sequence') != request.get('request_sequence'):
            raise ValueError('gate_request_sequence_mismatch')
        fingerprint_path = request_path.with_name('request_fingerprint.json')
        fingerprint = _json(fingerprint_path, owner.get(str(fingerprint_path), {}).get('sha256'), sources, payloads, owner)
        if fingerprint != dict(request_sha256=digest, request_file_sha256=pointer['request_file_sha256'], request_path=str(request_path)):
            raise ValueError('request_file_fingerprint_mismatch')
        response = _json(pointer['response_path'], pointer['response_sha256'], sources, payloads, owner)
        if (response.get('schema') != 'stage022_delivery_pointer_v1' or response.get('request_sha256') != digest
                or response.get('receipt_path') != pointer['receipt_path'] or response.get('receipt_sha256') != pointer['receipt_sha256']):
            raise ValueError('response_pointer_identity_mismatch')
        receipt = _json(pointer['receipt_path'], pointer['receipt_sha256'], sources, payloads, owner)
        closure = receipt.get('source_fingerprints', {})
        if closure != pointer.get('source_fingerprints'):
            raise ValueError('resolver_receipt_source_closure_mismatch')
        for path, expected in closure.items():
            _bind(path, expected, sources, owner)
        if any(item['requirement_kind'] not in ('anchor', 'full_session') for item in request['requirements']):
            raise ValueError('unsupported_delivery_requirement_kind')
        data, full, anchor, audit = _read_delivery_bytes(request,
            gate.QualifiedDelivery(Path(pointer['receipt_path']), pointer['receipt_sha256']), sources, payloads, owner)
        if audit['accepted_keys'] != event.get('accepted_keys') or not 0 <= event.get('appended_keys', -1) <= len(data):
            raise ValueError('gate_committed_key_count_mismatch')
        for row in data.to_dict('records'):
            key = _key(row['vt_symbol'], row['bar_datetime'])
            seven = tuple(float(row[name]) for name in VALUES)
            if key in values and not np.array_equal(values[key], seven):
                raise ValueError(f'cross_receipt_old_value_conflict:{key}')
            values[key] = seven
            entry = rights.setdefault(key, dict(full=False, anchor=False, proof=set()))
            entry['full'] |= key in full
            entry['anchor'] |= key in full or key in anchor
            entry['proof'].add(digest)
        deliveries.append(dict(original_gate_index=index, request_sha256=digest,
            request_path=str(request_path), request_file_sha256=pointer['request_file_sha256'],
            request_fingerprint_path=str(fingerprint_path), request_fingerprint_sha256=sources[str(fingerprint_path)],
            response_path=pointer['response_path'], response_sha256=pointer['response_sha256'],
            source_fingerprints=closure, accepted_requirements=receipt['accepted_requirements'],
            appended_keys=event['appended_keys'], old_keys_changed=0, **audit))
        seen.add(digest)
    commit_ids = {row['request_sha256'] for _, row in commits}
    # Do not read raw/receipts of excluded packages; the failure's signed prefix is sufficient.
    all_ids = list(dict.fromkeys([row['request_sha256'] for row in gates] + list(by_request)))
    for digest in all_ids:
        if digest in seen:
            continue
        pointer = by_request.get(digest, {})
        reason = ('data_gate_failed' if digest in failed else
            'pointer_only_no_gate_commit' if pointer.get('status') == 'qualified_delivery_pointer_accepted' and digest not in commit_ids
            else 'no_accepted_pointer' if pointer.get('status') != 'qualified_delivery_pointer_accepted'
            else 'no_matching_gate_commit')
        excluded.append(dict(request_sha256=digest, reason=reason))
    if not deliveries:
        raise ValueError('no_terminal_committed_deliveries')
    frame = pd.DataFrame([dict(vt_symbol=symbol, bar_datetime=stamp.isoformat(),
        **dict(zip(VALUES, seven))) for (symbol, stamp), seven in sorted(values.items())], columns=FIELDS)
    right_rows = [dict(vt_symbol=symbol, bar_datetime=stamp.isoformat(), qualified_full=int(item['full']),
        qualified_anchor=int(item['anchor']), proof_requests=json.dumps(sorted(item['proof']), separators=(',', ':')))
        for (symbol, stamp), item in sorted(rights.items())]
    # Every consumed identity is rechecked before publishing the directory.
    for path, expected in sources.items():
        if sha256(path) != expected:
            raise ValueError(f'source_hash_changed_during_freeze:{path}')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.' + output.name + '-', dir=output.parent))
    try:
        _write(temporary / 'source_run_snapshot.json', snapshot)
        _write(temporary / 'accepted_deliveries.json', dict(schema='stage061_accepted_wait_deliveries_v1',
            run_id=facts['run_id'], deliveries=deliveries, excluded=excluded))
        frame.to_csv(temporary / 'overlay.csv', index=False, float_format='%.17g')
        pd.DataFrame(right_rows).to_csv(temporary / 'rights.csv', index=False)
        artifacts = {name: sha256(temporary / name) for name in
            ('source_run_snapshot.json', 'accepted_deliveries.json', 'overlay.csv', 'rights.csv')}
        manifest = dict(schema=MANIFEST_SCHEMA, status='frozen_pending_independent_review',
            builder='stage061_accepted_wait_delta.py', run_id=facts['run_id'],
            base_stack_path=str(base_stack), base_stack_sha256=base_stack_sha256,
            inherited_anchor_inputs=snapshot['inherited_anchor_inputs'],
            terminal_evidence_path=str(terminal_evidence), terminal_sha256=terminal_sha256,
            source_fingerprints=sources, artifacts=artifacts, accepted_deliveries=len(deliveries),
            accepted_keys=len(values), qualified_full_keys=sum(row['qualified_full'] for row in right_rows),
            qualified_anchor_keys=sum(row['qualified_anchor'] for row in right_rows),
            old_key_value_policy='equal_only_no_replace', qualification_scope='accepted_exact_keys_only',
            financial_replays=0, model_fits=0, predictions=0, network_calls=0, production_qualified=False)
        _write(temporary / 'manifest.json', manifest)
        if output.exists():
            raise FileExistsError(f'existing_frozen_delta_refusing_overwrite:{output}')
        os.rename(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output / 'manifest.json'


@dataclass(frozen=True)
class FrozenDelta:
    overlay: object
    full_keys: frozenset
    anchor_keys: frozenset
    source_fingerprints: dict
    manifest: dict


def load_accepted_delta(manifest_path, manifest_sha256, review_path, review_sha256, *,
                        base_stack, base_stack_sha256, inherited_anchor_inputs, recorder=None):
    """Require a separately pinned independent review and exact upstream identity."""
    np, pd, gate = _numerical()
    sources, payloads = {}, {}
    manifest_path, review_path = Path(manifest_path), Path(review_path)
    manifest = _json(manifest_path, manifest_sha256, sources, payloads)
    review = _json(review_path, review_sha256, sources, payloads)
    if (manifest.get('schema') != MANIFEST_SCHEMA or manifest.get('status') != 'frozen_pending_independent_review'
            or manifest.get('old_key_value_policy') != 'equal_only_no_replace'
            or manifest.get('qualification_scope') != 'accepted_exact_keys_only'):
        raise ValueError('frozen_delta_manifest_contract_mismatch')
    if (review.get('schema') != REVIEW_SCHEMA or review.get('independent_review') is not True
            or not review.get('reviewer') or review['reviewer'] == manifest.get('builder')
            or review.get('manifest_path') != str(manifest_path) or review.get('manifest_sha256') != manifest_sha256
            or review.get('p0_findings') != 0 or review.get('p1_findings') != 0
            or any(review.get(k) is not True for k in ('qualified_research_data', 'exact_rights_confirmed', 'old_key_values_unchanged'))):
        raise ValueError('independent_wait_delta_review_required')
    if (manifest.get('base_stack_path') != str(base_stack) or manifest.get('base_stack_sha256') != base_stack_sha256
            or manifest.get('inherited_anchor_inputs') != inherited_anchor_inputs):
        raise ValueError('frozen_delta_upstream_identity_mismatch')
    for path, expected in manifest['source_fingerprints'].items():
        _bind(path, expected, sources)
    expected_artifacts = {'source_run_snapshot.json', 'accepted_deliveries.json', 'overlay.csv', 'rights.csv'}
    if set(manifest['artifacts']) != expected_artifacts:
        raise ValueError('frozen_delta_artifact_scope_mismatch')
    for name, expected in manifest['artifacts'].items():
        _bound_payload(manifest_path.parent / name, expected, sources, payloads)
    overlay = gate.old.normal_times(pd.read_csv(io.BytesIO(payloads[str(manifest_path.parent / 'overlay.csv')]), float_precision='round_trip'))
    rights = pd.read_csv(io.BytesIO(payloads[str(manifest_path.parent / 'rights.csv')]))
    rights = gate.old.normal_times(rights)
    if (list(overlay.columns) != FIELDS or gate.old.minute_keys(overlay).has_duplicates
            or gate.old.minute_keys(rights).has_duplicates or _keys(overlay) != _keys(rights)
            or not np.isfinite(overlay[VALUES].to_numpy(dtype=float)).all()
            or not rights.qualified_full.isin([0, 1]).all() or not rights.qualified_anchor.eq(1).all()):
        raise ValueError('frozen_delta_exact_keys_or_rights_mismatch')
    full = frozenset(_keys(rights.loc[rights.qualified_full.eq(1)]))
    anchor = frozenset(_keys(rights.loc[rights.qualified_anchor.eq(1)]))
    if (len(overlay) != manifest['accepted_keys'] or len(full) != manifest['qualified_full_keys']
            or len(anchor) != manifest['qualified_anchor_keys']):
        raise ValueError('frozen_delta_key_counts_mismatch')
    if recorder is not None:
        for path, expected in sources.items():
            recorder.extra.add(Path(path).resolve()); recorder.record(path)
            if recorder.files[str(Path(path).resolve())]['sha256'] != expected:
                raise ValueError(f'recorder_source_hash_mismatch:{path}')
    return FrozenDelta(overlay, full, anchor, sources, manifest)


def append_equal_only(base, delta):
    """Build a new frame only after every selected symbol's overlaps compare equal."""
    np, pd, gate = _numerical()
    base = gate.old.normal_times(base)
    if gate.old.minute_keys(base).has_duplicates:
        raise ValueError('duplicate_original_minute_key')
    if _keys(delta.overlay) != set(delta.anchor_keys) or not set(delta.full_keys).issubset(delta.anchor_keys):
        raise ValueError('frozen_delta_data_rights_scope_mismatch')
    prior = base.set_index(['vt_symbol', 'bar_datetime'])
    appended, added = [], set()
    for row in delta.overlay.to_dict('records'):
        key = _key(row['vt_symbol'], row['bar_datetime'])
        if key in prior.index:
            old = prior.loc[key, VALUES]
            if getattr(old, 'ndim', 1) != 1 or not np.array_equal(old.to_numpy(dtype=float),
                    np.asarray([row[name] for name in VALUES], dtype=float)):
                raise ValueError(f'accepted_wait_delta_old_value_conflict:{key}')
        else:
            row.update(bar_datetime=key[1], bar_date=key[1].normalize(), minute_source='stage061_independently_qualified_exact_rights')
            appended.append(row); added.add(key)
    if appended:
        base = pd.concat([base, pd.DataFrame(appended)], ignore_index=True, sort=False)
        base = base.sort_values(['vt_symbol', 'bar_datetime']).reset_index(drop=True)
    return base, added


@contextmanager
def temporary_accepted_wait_delta(s901, delta):
    """Outermost loader scope; restore loader and exact cache objects on exit/failure."""
    original = s901._load_stage861_full_minute_bars
    state = {name: getattr(s901, name) for name in CACHE_NAMES}
    newly_appended_keys = set()
    def load(symbols):
        before = {name: getattr(s901, name) for name in CACHE_NAMES}
        try:
            base = original(symbols)
            selected = delta.overlay.loc[delta.overlay.vt_symbol.astype(str).isin(symbols)]
            selected_keys = _keys(selected)
            local = FrozenDelta(selected, frozenset(delta.full_keys & selected_keys),
                frozenset(delta.anchor_keys & selected_keys), delta.source_fingerprints, delta.manifest)
            result, added = append_equal_only(base, local)
        except BaseException:
            for name, value in before.items():
                setattr(s901, name, value)
            raise
        newly_appended_keys.update(added)
        return result
    s901._load_stage861_full_minute_bars = load
    s901._FULL_MINUTE_BY_SYMBOL_CACHE = None
    s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = set()
    try:
        yield newly_appended_keys
    finally:
        s901._load_stage861_full_minute_bars = original
        for name, value in state.items():
            setattr(s901, name, value)


def compose_qualification(old_full, old_anchor, newly_appended_keys, delta):
    """Do not let the physical source label implicitly promote new anchor keys."""
    _, _, gate = _numerical()
    def full(symbol, stamp):
        key = _key(symbol, stamp)
        return bool((key not in newly_appended_keys and gate._source_contains(old_full, key)) or key in delta.full_keys)
    def anchor(symbol, stamp):
        key = _key(symbol, stamp)
        return bool(gate._source_contains(old_anchor, key) or full(*key) or key in delta.anchor_keys)
    return full, anchor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', required=True)
    for name in ('run-facts', 'run-facts-sha256', 'terminal-evidence', 'terminal-sha256',
                 'base-stack', 'base-stack-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    args = vars(parser.parse_args()); args.pop('freeze')
    import stage022_run_c0_qualified_wait as runtime
    with tempfile.TemporaryDirectory(prefix='stage061-runtime-') as shared:
        runtime.configure_runtime(Path(shared) / 'shared')
        print(freeze_accepted_delta(**args))


if __name__ == '__main__':
    main()
