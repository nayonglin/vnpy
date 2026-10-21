"""Freeze only reviewed065/B_OFF committed minutes as a new pending data layer.

No provider, financial engine, model, old190-layer merge, or qualification signer.
The compatible061 DATA schema does not imply its legacy063 origin was accepted.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import stage061_accepted_wait_delta as data_container

ACTUAL_SNAPSHOT_SHA256 = 'f601f0f32eb258b6cde458754709d2451b433025dbe297619992c59beb42ea18'
ACTUAL_REVIEW_SHA256 = '2d6f19e8fbb6f94976380ae114c7ca6cde8c70ea4ad5df3d2f9628aeaa9edd7a'
BUILDER = 'stage135_accepted_off_wait_delta.py'


@dataclass(frozen=True)
class OriginContract:
    snapshot_schema: str
    review_schema: str
    terminal_schema: str
    owner_schema: str
    fixture_only: bool


ACTUAL_CONTRACT = OriginContract(
    'stage134_audit_only_projection_of_stage065_failed_capture_v1',
    'stage134_independent_actual_B_OFF_failure_and_committed_scope_review_v1',
    'stage133_B_OFF_actual_failure_terminal_v1', 'stage087_off_owner_v1', False)


def _origin(snapshot_path, snapshot_sha256, review_path, review_sha256, contract, sources, payloads):
    """Consume reviewed audit projection, without unpickling partial account data."""
    read = lambda p, h: data_container._json(p, h, sources, payloads)
    projection = read(snapshot_path, snapshot_sha256)
    review = read(review_path, review_sha256)
    if (projection.get('schema') != contract.snapshot_schema or projection.get('audit_only') is not True
            or projection.get('new_data_qualification') is not False or projection.get('financial_qualified') is not False
            or review.get('schema') != contract.review_schema or review.get('independent_review') is not True
            or not review.get('reviewer') or review.get('p0_findings') != 0 or review.get('p1_findings') != 0
            or any(review.get(k) is not False for k in ('financial_accepted', 'production_qualified',
                'new_frozen_dataset', 'new_data_qualification_receipt'))):
        raise ValueError('reviewed_audit_only_origin_required')
    if (review.get('audit_only_snapshot', {}).get('path') != str(snapshot_path)
            or review['audit_only_snapshot'].get('sha256') != snapshot_sha256
            or review.get('owner') != projection.get('owner')):
        raise ValueError('origin_review_projection_identity_mismatch')
    identity = projection['owner']; upstream = projection['upstream_bindings']
    if identity.get('arm') != 'B_OFF' or identity.get('attempt') != 1 or not identity.get('run_id'):
        raise ValueError('unsupported_off_owner_identity')
    if upstream.get('original_065_schema') != 'stage065_partial_failure_capture_v1':
        raise ValueError('original065_capture_schema_required')
    aliases = {'actual_terminal':'actual_terminal', 'run_context.json':'run_context',
        'preflight_used.json':'preflight', 'run_failure.json':'run_failure', 'failure_capture.pkl.gz':'failure_capture'}
    objects = {}
    for name, review_name in aliases.items():
        item = upstream[name]; reviewed = review.get(review_name, {})
        if any(item.get(k) != reviewed.get(k) for k in ('path', 'sha256')):
            raise ValueError('origin_review_upstream_identity_mismatch:' + name)
        raw = data_container._bound_payload(item['path'], item['sha256'], sources, payloads)
        # The compressed capture is only bound; its account/PnL payload is never parsed.
        if name != 'failure_capture.pkl.gz': objects[name] = json.loads(raw)
    terminal = objects['actual_terminal']; context = objects['run_context.json']
    preflight = objects['preflight_used.json']; failure = objects['run_failure.json']
    if (terminal.get('schema') != contract.terminal_schema or terminal.get('actual_terminal_observed') is not True
            or type(terminal.get('exit_code')) is not int or terminal['exit_code'] != 1
            or any(type(terminal.get(k)) is not int or terminal[k] <= 0 for k in ('tool_session_id', 'engine_pid_at_start'))
            or not terminal.get('tool_terminal_chunk_id') or terminal.get('owner_root') != identity['output_directory']
            or any(terminal.get(k) != identity[k] for k in ('arm', 'run_id', 'attempt'))
            or terminal.get('failure') != failure):
        raise ValueError('actual065_failed_tool_terminal_required')
    for name in ('run_context.json', 'preflight_used.json', 'run_failure.json', 'failure_capture.pkl.gz'):
        if terminal.get('objects', {}).get(name) != upstream[name]:
            raise ValueError('terminal_object_binding_mismatch:' + name)
    if (failure.get('status') != 'failed_partial_no_engine_seal' or failure.get('partial') is not True
            or failure.get('production_qualified') is not False
            or failure.get('failure_capture_sha256') != upstream['failure_capture.pkl.gz']['sha256']
            or any(failure.get(k) != identity[k] for k in ('arm', 'run_id'))):
        raise ValueError('actual065_partial_failure_identity_mismatch')
    if (context.get('schema') != 'stage065_run_context_v1'
            or any(context.get(k) != v for k, v in identity.items())
            or context.get('fixture_only') is not contract.fixture_only
            or context.get('preflight_sha256') != upstream['preflight_used.json']['sha256']
            or context.get('writer') != 'stage065_account_checkpoint.py'
            or preflight.get('fixture_only') is not contract.fixture_only
            or any(preflight.get(k) != identity[k] for k in ('arm', 'attempt'))):
        raise ValueError('actual065_context_preflight_identity_mismatch')
    item = upstream['owner']; owner = read(item['path'], item['sha256'])
    if (owner.get('schema') != contract.owner_schema or owner.get('fixture_only') is not contract.fixture_only
            or any(owner.get(k) != identity[k] for k in ('arm', 'run_id', 'attempt'))
            or owner.get('account_output') != identity['output_directory']
            or owner.get('wait_root') != str(Path(identity['output_directory']) / 'data_wait')
            or owner.get('run_context_path') != upstream['run_context.json']['path']
            or owner.get('run_context_sha256') != upstream['run_context.json']['sha256']
            or owner.get('preflight_path') != upstream['preflight_used.json']['path']
            or owner.get('preflight_sha256') != upstream['preflight_used.json']['sha256']):
        raise ValueError('original_off_owner_binding_mismatch')
    data_container._bind(owner['runner_path'], owner['runner_sha256'], sources)
    writers = [p for p, value in context['source_bindings'].items()
        if Path(p).name == context['writer'] and value['sha256'] == context['writer_source_sha256']]
    if len(writers) != 1: raise ValueError('original065_writer_source_identity_missing')
    data_container._bind(writers[0], context['writer_source_sha256'], sources)
    inputs = projection['input_fingerprints']
    stack_paths = [p for p, value in inputs.items()
        if Path(p).name == 'data_stack_manifest.json' and value['sha256'] == preflight['data_stack_sha256']]
    if len(stack_paths) != 1: raise ValueError('original_base_stack_identity_missing')
    stack_path = stack_paths[0]
    stack = data_container._json(stack_path, preflight['data_stack_sha256'], sources, payloads, inputs)
    if stack.get('schema') != 'stage022_qualified_data_stack_v1' or stack.get('append_order') != ['002','011','015','020']:
        raise ValueError('original_base_stack_contract_mismatch')
    inherited = preflight['reused_anchor']; anchors = inherited['deliveries']
    if inherited.get('exact_anchor_keys') != 2 or inherited.get('full_session_keys') != 0 or len(anchors) != 2:
        raise ValueError('original_two_anchor_identity_required')
    for anchor in anchors:
        for kind in ('request', 'receipt', 'data'):
            p = anchor[kind + '_path']
            expected = inputs.get(p, {}).get('sha256') if kind == 'request' else anchor[kind + '_sha256']
            data_container._bind(p, expected, sources, inputs)
    previous = dict(manifest_path=preflight['accepted_wait_delta_manifest'],
        manifest_sha256=preflight['accepted_wait_delta_sha256'], review_path=preflight['accepted_wait_delta_review'],
        review_sha256=preflight['accepted_wait_delta_review_sha256'])
    # Identity-only references: do not parse, merge, re-freeze or re-review old190 data.
    for kind in ('manifest', 'review'):
        data_container._bind(previous[kind + '_path'], previous[kind + '_sha256'], sources, inputs)
    snapshot = dict(schema='stage135_source065_failure_snapshot_v1', builder=BUILDER,
        compatible_data_schema_only=True, fixture_only=contract.fixture_only, **identity,
        origin_snapshot_path=str(snapshot_path), origin_snapshot_sha256=snapshot_sha256,
        origin_review_path=str(review_path), origin_review_sha256=review_sha256,
        terminal_evidence_path=upstream['actual_terminal']['path'], terminal_sha256=upstream['actual_terminal']['sha256'],
        upstream_bindings={k:v for k,v in upstream.items() if k != 'source_bindings'},
        base_stack_path=stack_path, base_stack_sha256=preflight['data_stack_sha256'],
        inherited_anchor_inputs=anchors, inherited_previous_delta=previous,
        qualification_scope='committed_delivery_only_not_financial_or_new_dataset_qualification')
    return projection, review, snapshot


def _freeze_off_delta(*, snapshot_path, snapshot_sha256, review_path, review_sha256, output, contract):
    """Common neutral origin reader; independent fixtures use distinct contracts."""
    np, pd, gate = data_container._numerical()
    snapshot_path, review_path, output = Path(snapshot_path), Path(review_path), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'existing_frozen_delta_refusing_overwrite:{output}')
    sources, payloads = {}, {}
    projection, review, snapshot = _origin(snapshot_path, snapshot_sha256, review_path, review_sha256,
        contract, sources, payloads)
    for module in (data_container, gate):
        path = Path(module.__file__).absolute()
        expected = (review.get('limited_static_source_bindings', {}).get(str(path), {}).get('sha256')
            if module is data_container else data_container.DELIVERY_PARSER_SOURCE_SHA256)
        data_container._bind(path, expected or data_container.sha256(path), sources)
    data_container._bind(Path(__file__).absolute(), data_container.sha256(__file__), sources)
    gates, resolvers, owner = projection['wait_audit'], projection['resolver_audit'], projection['input_fingerprints']
    pointers = {}
    for row in resolvers:
        digest = row['request_sha256']
        if digest in pointers: raise ValueError('ambiguous_duplicate_resolver_request')
        pointers[digest] = row
    commits = [(i, row) for i, row in enumerate(gates) if row['event'] == 'data_qualified_appended']
    if len({row['request_sha256'] for _, row in commits}) != len(commits):
        raise ValueError('ambiguous_duplicate_gate_commit')
    failed = {row['request_sha256'] for row in gates if row['event'] == 'data_gate_failed'}
    deliveries, seen, values, rights, sequences = [], set(), {}, {}, set()
    for index, event in commits:
        digest = event['request_sha256']; pointer = pointers.get(digest)
        if digest in failed or pointer is None or pointer.get('status') != 'qualified_delivery_pointer_accepted':
            raise ValueError('gate_commit_without_accepted_nonfailed_pointer')
        if type(event.get('old_keys_changed')) is not int or event['old_keys_changed'] != 0:
            raise ValueError('gate_old_key_mutation_not_reusable')
        for field in ('receipt_path','receipt_sha256','data_path','data_sha256'):
            if event.get(field) != pointer.get(field): raise ValueError('dual_record_identity_mismatch:' + field)
        for p, h in (('request_path','request_file_sha256'),('response_path','response_sha256'),
                     ('receipt_path','receipt_sha256'),('data_path','data_sha256')):
            data_container._bound_payload(pointer[p], pointer[h], sources, payloads, owner)
        request_path = Path(pointer['request_path'])
        if (request_path.parent != Path(projection['owner']['output_directory']) / 'data_wait' / ('request_' + digest)
                or Path(pointer['response_path']) != request_path.with_name('response.json')):
            raise ValueError('delivery_not_owned_by_original_off_run')
        request = data_container._json(request_path, pointer['request_file_sha256'], sources, payloads, owner)
        if (request.get('schema') != gate.REQUEST_SCHEMA or request.get('request_sha256') != digest
                or gate.request_sha256(request) != digest): raise ValueError('canonical_request_hash_mismatch')
        requested = [row for row in gates[:index] if row['event'] == 'data_requested' and row['request_sha256'] == digest]
        sequence = request.get('request_sequence')
        if (len(requested) != 1 or requested[0].get('request_sequence') != sequence
                or type(sequence) is not int or sequence <= 0 or sequence in sequences):
            raise ValueError('gate_request_sequence_mismatch')
        sequences.add(sequence)
        fingerprint_path = request_path.with_name('request_fingerprint.json')
        fingerprint = data_container._json(fingerprint_path, owner.get(str(fingerprint_path), {}).get('sha256'), sources, payloads, owner)
        if fingerprint != dict(request_sha256=digest,request_file_sha256=pointer['request_file_sha256'],request_path=str(request_path)):
            raise ValueError('request_file_fingerprint_mismatch')
        response = data_container._json(pointer['response_path'], pointer['response_sha256'], sources, payloads, owner)
        if (response.get('schema') != 'stage022_delivery_pointer_v1' or response.get('request_sha256') != digest
                or response.get('receipt_path') != pointer['receipt_path'] or response.get('receipt_sha256') != pointer['receipt_sha256']):
            raise ValueError('response_pointer_identity_mismatch')
        receipt = data_container._json(pointer['receipt_path'],pointer['receipt_sha256'],sources,payloads,owner)
        closure = receipt.get('source_fingerprints', {})
        if closure != pointer.get('source_fingerprints'):
            raise ValueError('resolver_receipt_source_closure_mismatch')
        if receipt.get('owner_run_id') != projection['owner']['run_id'] or receipt.get('owner_arm') != 'B_OFF':
            raise ValueError('receipt_off_owner_identity_mismatch')
        for path, expected in closure.items(): data_container._bind(path,expected,sources,owner)
        identities = [(item['vt_symbol'],item['execution_trade_date'],item['requirement_kind']) for item in request['requirements']]
        if len(set(identities)) != len(identities) or any(i[2] not in ('anchor','full_session') for i in identities):
            raise ValueError('unsupported_or_duplicate_delivery_requirement')
        data, full, anchor, audit = data_container._read_delivery_bytes(request,
            gate.QualifiedDelivery(Path(pointer['receipt_path']),pointer['receipt_sha256']),sources,payloads,owner)
        if (audit['accepted_keys'] != event.get('accepted_keys') or type(event.get('appended_keys')) is not int
                or not 0 <= event['appended_keys'] <= len(data)):
            raise ValueError('gate_committed_key_count_mismatch')
        for row in data.to_dict('records'):
            key = data_container._key(row['vt_symbol'],row['bar_datetime']); seven=tuple(float(row[name]) for name in data_container.VALUES)
            if key in values and not np.array_equal(values[key],seven):
                raise ValueError('cross_receipt_old_value_conflict:' + str(key))
            values[key] = seven
            entry = rights.setdefault(key,dict(full=False,anchor=False,proof=set()))
            entry['full'] |= key in full; entry['anchor'] |= key in full or key in anchor; entry['proof'].add(digest)
        deliveries.append(dict(original_gate_index=index,request_sha256=digest,
            request_path=str(request_path),request_file_sha256=pointer['request_file_sha256'],
            request_fingerprint_path=str(fingerprint_path),request_fingerprint_sha256=sources[str(fingerprint_path)],
            response_path=pointer['response_path'],response_sha256=pointer['response_sha256'],
            source_fingerprints=closure,accepted_requirements=receipt['accepted_requirements'],
            appended_keys=event['appended_keys'],old_keys_changed=0,**audit))
        seen.add(digest)
    counts = dict(actual_gate_committed=len(deliveries),unique_exact_keys=len(values),
        qualified_full_keys=sum(v['full'] for v in rights.values()),
        explicit_anchor_only_keys=sum(not v['full'] and v['anchor'] for v in rights.values()),
        qualified_anchor_keys=sum(v['anchor'] for v in rights.values()))
    if not deliveries or any(review['actual_capture_scope'].get(k) != v for k,v in counts.items()):
        raise ValueError('reviewed_committed_scope_count_mismatch')
    if ('actual_appended_keys_sum' in review['actual_capture_scope']
            and sum(x['appended_keys'] for x in deliveries) != review['actual_capture_scope']['actual_appended_keys_sum']):
        raise ValueError('reviewed_committed_appended_count_mismatch')
    excluded = []
    for digest in dict.fromkeys([row['request_sha256'] for row in gates] + list(pointers)):
        if digest not in seen:
            excluded.append(dict(request_sha256=digest,reason='data_gate_failed' if digest in failed else 'no_matching_gate_commit'))
    frame = pd.DataFrame([dict(vt_symbol=symbol,bar_datetime=stamp.isoformat(),**dict(zip(data_container.VALUES,seven)))
        for (symbol,stamp),seven in sorted(values.items())],columns=data_container.FIELDS)
    right_rows = [dict(vt_symbol=symbol,bar_datetime=stamp.isoformat(),qualified_full=int(v['full']),qualified_anchor=int(v['anchor']),
        proof_requests=json.dumps(sorted(v['proof']),separators=(',',':'))) for (symbol,stamp),v in sorted(rights.items())]
    for path, expected in sources.items():
        if data_container.sha256(path) != expected: raise ValueError('source_hash_changed_during_freeze:' + path)
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
    try:
        data_container._write(temporary/'source_run_snapshot.json',snapshot)
        data_container._write(temporary/'accepted_deliveries.json',dict(schema='stage061_accepted_wait_deliveries_v1',
            builder=BUILDER,compatible_data_schema_only=True,fixture_only=contract.fixture_only,
            run_id=projection['owner']['run_id'],deliveries=deliveries,excluded=excluded))
        frame.to_csv(temporary/'overlay.csv',index=False,float_format='%.17g')
        pd.DataFrame(right_rows).to_csv(temporary/'rights.csv',index=False)
        artifacts={name:data_container.sha256(temporary/name) for name in (
            'source_run_snapshot.json','accepted_deliveries.json','overlay.csv','rights.csv')}
        manifest=dict(schema=data_container.MANIFEST_SCHEMA,status='frozen_pending_independent_review',builder=BUILDER,
            compatible_data_schema_only=True,fixture_only=contract.fixture_only,origin_schema=contract.snapshot_schema,
            arm='B_OFF',run_id=projection['owner']['run_id'],base_stack_path=snapshot['base_stack_path'],
            base_stack_sha256=snapshot['base_stack_sha256'],inherited_anchor_inputs=snapshot['inherited_anchor_inputs'],
            inherited_previous_delta=snapshot['inherited_previous_delta'],
            terminal_evidence_path=snapshot['terminal_evidence_path'],terminal_sha256=snapshot['terminal_sha256'],
            origin_review_path=str(review_path),origin_review_sha256=review_sha256,
            source_fingerprints=sources,artifacts=artifacts,accepted_deliveries=len(deliveries),accepted_keys=len(values),
            qualified_full_keys=counts['qualified_full_keys'],qualified_anchor_keys=counts['qualified_anchor_keys'],
            explicit_anchor_only_keys=counts['explicit_anchor_only_keys'],old_key_value_policy='equal_only_no_replace',
            qualification_scope='accepted_exact_keys_only',new_layer_qualified_research_data=False,
            financial_replays=0,model_fits=0,predictions=0,network_calls=0,production_qualified=False)
        data_container._write(temporary/'manifest.json',manifest)
        if output.exists() or output.is_symlink(): raise FileExistsError('existing_frozen_delta_refusing_overwrite:' + str(output))
        os.rename(temporary,output)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return output/'manifest.json'


def freeze_off_delta(*, snapshot_path, snapshot_sha256, review_path, review_sha256, output):
    """One reviewed actual134 origin; author cannot sign new dataset acceptance."""
    if (snapshot_sha256,review_sha256) != (ACTUAL_SNAPSHOT_SHA256,ACTUAL_REVIEW_SHA256):
        raise ValueError('actual134_identity_required_fixture_not_actual')
    return _freeze_off_delta(snapshot_path=snapshot_path,snapshot_sha256=snapshot_sha256,
        review_path=review_path,review_sha256=review_sha256,output=output,contract=ACTUAL_CONTRACT)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot-path','snapshot-sha256','review-path','review-sha256','output'):
        parser.add_argument('--'+name,required=True)
    args=vars(parser.parse_args())
    import stage022_run_c0_qualified_wait as runtime
    with tempfile.TemporaryDirectory(prefix='stage135-runtime-') as temporary:
        previous=runtime.OUTPUT
        try:
            runtime.OUTPUT=Path(temporary)/'runtime'
            runtime.configure_runtime(Path(temporary)/'shared')
        finally:
            runtime.OUTPUT=previous
        print(freeze_off_delta(**args))


if __name__=='__main__':main()
