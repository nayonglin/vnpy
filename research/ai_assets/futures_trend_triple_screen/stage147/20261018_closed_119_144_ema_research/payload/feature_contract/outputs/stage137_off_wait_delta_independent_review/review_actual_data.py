"""One bounded independent audit of the accepted OFF delta; no financial work."""
from collections import Counter
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path('/Users/mac/Desktop/fian')
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
OUT = LINE / 'outputs/stage137_off_wait_delta_independent_review'
TOOLS = LINE / 'tools'
CANDIDATE = LINE / 'outputs/stage135_accepted_off_wait_delta/81ffc8f704ce4c5eb701e97e0397b12a'
ORIGIN = LINE / 'outputs/stage134_B_OFF_failure_independent_review'
PINS = {
    TOOLS / 'stage135_accepted_off_wait_delta.py': 'e128a199deddf728b24a58ee4511bdb781121fe668945249351a1ed573cc5977',
    TOOLS / 'test_stage135_accepted_off_wait_delta.py': '4c990835b19ea6852d05e637d37fa3bfa4a854f0ca17130549045e02e4bca735',
    CANDIDATE / 'manifest.json': '563556d9a70a4f841f606e6b668c6422ae11c7f28f0dcc9203451c20ab2e694a',
    ORIGIN / 'audit_only_snapshot.json': 'f601f0f32eb258b6cde458754709d2451b433025dbe297619992c59beb42ea18',
    ORIGIN / 'review_receipt.json': '2d6f19e8fbb6f94976380ae114c7ca6cde8c70ea4ad5df3d2f9628aeaa9edd7a',
    ORIGIN / 'committed_scope_audit.json': '1d8578b14c9adaf16fbdb5b3d5aa519cfa2e1d6690c82e58bb59539324a978cd',
}
VALUES = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']
FIELDS = ['vt_symbol', 'bar_datetime', *VALUES]
FAILED = '7422216c316b1eeea381af05e31318dfbea8903ffe77c31c6c9b6c7cf2c087eb'


def check(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def write(name, value):
    p = OUT / name
    check(not p.exists(), 'review evidence refuses overwrite: ' + name)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def configure():
    sys.path.insert(0, str(TOOLS))
    import stage022_run_c0_qualified_wait as runtime
    temporary = tempfile.TemporaryDirectory(prefix='stage137-', dir=OUT)
    previous = runtime.OUTPUT
    try:
        runtime.OUTPUT = Path(temporary.name) / 'runtime'
        runtime.configure_runtime(Path(temporary.name) / 'shared')
    finally:
        runtime.OUTPUT = previous
    return temporary


def audit():
    temporary = configure()
    import numpy as np
    import pandas as pd
    payloads, observed, expected_sources = {}, {}, {}

    def read(path, expected):
        p = Path(path)
        check(p.is_absolute() and not p.is_symlink(), 'absolute non-symlink required: ' + str(p))
        raw = p.read_bytes()
        check(hashlib.sha256(raw).hexdigest() == expected, 'SHA mismatch: ' + str(p))
        check(str(p) not in observed or observed[str(p)] == expected, 'source identity collision')
        observed[str(p)] = expected
        payloads[str(p)] = raw
        return raw

    def obj(path, expected):
        return json.loads(read(path, expected))

    def claim(path, expected, owner=None):
        p = str(path)
        check(Path(p).is_absolute() and isinstance(expected, str) and len(expected) == 64, 'invalid source binding')
        check(p not in expected_sources or expected_sources[p] == expected, 'conflicting source binding: ' + p)
        if owner is not None:
            check(owner.get(p, {}).get('sha256') == expected, 'not in original owner fingerprints: ' + p)
        expected_sources[p] = expected

    def bound_obj(path, expected, owner=None):
        claim(path, expected, owner)
        return obj(path, expected)

    def key(symbol, stamp):
        t = pd.Timestamp(stamp)
        if t.tzinfo is not None:
            t = t.tz_convert('Asia/Shanghai').tz_localize(None)
        return str(symbol), t

    def rows(raw, round_trip=False):
        frame = pd.read_csv(io.BytesIO(raw), **({'float_precision': 'round_trip'} if round_trip else {}))
        check(set(FIELDS) <= set(frame.columns), 'data fields missing')
        result = {}
        for row in frame[FIELDS].itertuples(index=False, name=None):
            k = key(row[0], row[1]); seven = tuple(float(v) for v in row[2:])
            check(k not in result, 'duplicate minute key')
            check(np.isfinite(seven).all(), 'nonfinite minute value')
            check(min(seven[:4]) > 0 and min(seven[4:]) >= 0, 'invalid price/volume/OI')
            check(seven[2] <= min(seven[0], seven[3]) and seven[1] >= max(seven[0], seven[3]), 'invalid OHLC')
            result[k] = seven
        return result

    for p, digest in PINS.items():
        check(sha(p) == digest, 'initial pinned identity changed: ' + str(p))
    manifest = obj(CANDIDATE / 'manifest.json', PINS[CANDIDATE / 'manifest.json'])
    projection = bound_obj(ORIGIN / 'audit_only_snapshot.json', PINS[ORIGIN / 'audit_only_snapshot.json'])
    review = bound_obj(ORIGIN / 'review_receipt.json', PINS[ORIGIN / 'review_receipt.json'])
    scope = obj(ORIGIN / 'committed_scope_audit.json', PINS[ORIGIN / 'committed_scope_audit.json'])
    owner = projection['input_fingerprints']; identity = projection['owner']; upstream = projection['upstream_bindings']
    check(identity == review['owner'], 'origin owner mismatch')
    check(identity['arm'] == 'B_OFF' and identity['attempt'] == 1 and identity['run_id'] == CANDIDATE.name, 'wrong actual owner')
    check(projection['schema'] == 'stage134_audit_only_projection_of_stage065_failed_capture_v1'
          and projection['audit_only'] is True and projection['new_data_qualification'] is False
          and projection['financial_qualified'] is False, 'projection qualification overclaim')
    check(review['independent_review'] is True and review['p0_findings'] == review['p1_findings'] == 0
          and review['new_data_qualification_receipt'] is False and review['financial_accepted'] is False, 'invalid inherited review')
    artifacts = {}
    for name, digest in manifest['artifacts'].items():
        raw = read(CANDIDATE / name, digest)
        artifacts[name] = {'sha256': digest, 'bytes': len(raw)}
    check(set(artifacts) == {'source_run_snapshot.json', 'accepted_deliveries.json', 'overlay.csv', 'rights.csv'}, 'artifact scope')
    snapshot = json.loads(payloads[str(CANDIDATE / 'source_run_snapshot.json')])
    accepted = json.loads(payloads[str(CANDIDATE / 'accepted_deliveries.json')])
    check(manifest['status'] == 'frozen_pending_independent_review' and manifest['new_layer_qualified_research_data'] is False, 'author self qualification')
    check(manifest['schema'] == 'stage061_accepted_wait_delta_manifest_v1' and manifest['builder'] == 'stage135_accepted_off_wait_delta.py'
          and manifest['compatible_data_schema_only'] is True and manifest['fixture_only'] is False, 'manifest identity')
    check(snapshot['schema'] == 'stage135_source065_failure_snapshot_v1'
          and snapshot['upstream_bindings'] == {k: v for k, v in upstream.items() if k != 'source_bindings'}
          and all(snapshot[k] == v for k, v in identity.items()), 'new origin schema/source identity')
    check(snapshot['origin_snapshot_path'] == str(ORIGIN / 'audit_only_snapshot.json')
          and snapshot['origin_snapshot_sha256'] == PINS[ORIGIN / 'audit_only_snapshot.json']
          and snapshot['origin_review_path'] == str(ORIGIN / 'review_receipt.json')
          and snapshot['origin_review_sha256'] == PINS[ORIGIN / 'review_receipt.json'], 'origin pins not carried')
    upstream_objects = {}
    for name, item in upstream.items():
        if name != 'source_bindings' and isinstance(item, dict):
            claim(item['path'], item['sha256'])
            raw = read(item['path'], item['sha256'])
            if name != 'failure_capture.pkl.gz':
                upstream_objects[name] = json.loads(raw)
    terminal = upstream_objects['actual_terminal']; context = upstream_objects['run_context.json']
    preflight = upstream_objects['preflight_used.json']; run_owner = upstream_objects['owner']
    check(terminal['schema'] == 'stage133_B_OFF_actual_failure_terminal_v1' and terminal['exit_code'] == 1
          and terminal['actual_terminal_observed'] is True and terminal['failure'] == upstream_objects['run_failure.json'], 'actual failure identity')
    check(context['schema'] == 'stage065_run_context_v1' and context['fixture_only'] is False
          and all(context[k] == v for k, v in identity.items()) and run_owner['schema'] == 'stage087_off_owner_v1', '065 context/owner identity')
    claim(run_owner['runner_path'], run_owner['runner_sha256'])
    writers = [p for p, v in context['source_bindings'].items()
               if Path(p).name == context['writer'] and v['sha256'] == context['writer_source_sha256']]
    check(len(writers) == 1, 'unique original writer missing')
    claim(writers[0], context['writer_source_sha256'])
    check(manifest['base_stack_sha256'] == preflight['data_stack_sha256']
          and manifest['inherited_anchor_inputs'] == preflight['reused_anchor']['deliveries']
          and snapshot['inherited_previous_delta'] == manifest['inherited_previous_delta'], 'inherited upstream identity')
    claim(manifest['base_stack_path'], manifest['base_stack_sha256'], owner)
    for anchor in manifest['inherited_anchor_inputs']:
        for kind in ('request', 'receipt', 'data'):
            p = anchor[kind + '_path']
            claim(p, owner[p]['sha256'] if kind == 'request' else anchor[kind + '_sha256'], owner)
    previous = manifest['inherited_previous_delta']
    for kind in ('manifest', 'review'):
        claim(previous[kind + '_path'], previous[kind + '_sha256'], owner)
    for name in ('stage061_accepted_wait_delta.py', 'stage021_blocking_data_gate.py', 'stage135_accepted_off_wait_delta.py'):
        p = TOOLS / name
        digest = PINS[p] if p in PINS else ('150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'
            if name.startswith('stage021') else review['limited_static_source_bindings'][str(p)]['sha256'])
        claim(p, digest)

    pointers = {r['request_sha256']: r for r in projection['resolver_audit'] if r.get('status') == 'qualified_delivery_pointer_accepted'}
    commits = [(i, r) for i, r in enumerate(projection['wait_audit']) if r['event'] == 'data_qualified_appended']
    check(len(pointers) == len(commits) == 159 and len({r['request_sha256'] for _, r in commits}) == 159, 'actual selected count')
    check(set(pointers) == {r['request_sha256'] for _, r in commits}, 'dual-record set mismatch')
    check(len(accepted['deliveries']) == 159 and accepted['excluded'] == [{'request_sha256': FAILED, 'reason': 'data_gate_failed'}], 'exclusion changed')
    check(accepted['schema'] == 'stage061_accepted_wait_deliveries_v1' and accepted['builder'] == manifest['builder']
          and accepted['compatible_data_schema_only'] is True and accepted['fixture_only'] is False
          and accepted['run_id'] == identity['run_id'], 'accepted delivery identity')
    expected_values, rights, proofs, details, sequences = {}, {}, {}, [], set()
    captured_scope = {d['request_sha256']: d for d in scope['committed_deliveries']}
    existing_sum = appended_sum = overlap_count = 0
    for (index, event), item in zip(commits, accepted['deliveries']):
        digest = event['request_sha256']; pointer = pointers[digest]
        check(item['request_sha256'] == digest and item['original_gate_index'] == index, 'frozen order differs from real gate')
        check(type(event['old_keys_changed']) is int and event['old_keys_changed'] == item['old_keys_changed'] == 0, 'actual old-key mutation')
        for field in ('receipt_path', 'receipt_sha256', 'data_path', 'data_sha256'):
            check(event[field] == pointer[field] == item[field], 'dual-record field mismatch: ' + field)
        for path_field, sha_field in (('request_path', 'request_file_sha256'), ('response_path', 'response_sha256'),
                                    ('receipt_path', 'receipt_sha256'), ('data_path', 'data_sha256')):
            check(item[path_field] == pointer[path_field] and item[sha_field] == pointer[sha_field], 'artifact pointer mismatch')
            claim(pointer[path_field], pointer[sha_field], owner)
        request = obj(pointer['request_path'], pointer['request_file_sha256'])
        request_path = Path(pointer['request_path'])
        check(request_path.parent == Path(identity['output_directory']) / 'data_wait' / ('request_' + digest)
              and Path(pointer['response_path']) == request_path.with_name('response.json'), 'wrong run data ownership')
        check(request['schema'] == 'stage021_exact_execution_minute_request_v1' and request['request_sha256'] == digest
              and hashlib.sha256(canonical({k: v for k, v in request.items() if k != 'request_sha256'})).hexdigest() == digest, 'canonical request mismatch')
        seq = request['request_sequence']
        requested = [r for r in projection['wait_audit'][:index] if r['event'] == 'data_requested' and r['request_sha256'] == digest]
        check(type(seq) is int and seq > 0 and seq not in sequences and len(requested) == 1 and requested[0]['request_sequence'] == seq, 'request sequence')
        sequences.add(seq)
        fp_path = request_path.with_name('request_fingerprint.json')
        fp_sha = owner[str(fp_path)]['sha256']; claim(fp_path, fp_sha, owner)
        check(item['request_fingerprint_path'] == str(fp_path) and item['request_fingerprint_sha256'] == fp_sha, 'artifact fingerprint identity')
        check(obj(fp_path, fp_sha) == {'request_sha256': digest, 'request_file_sha256': pointer['request_file_sha256'], 'request_path': str(request_path)}, 'file fingerprint')
        response = obj(pointer['response_path'], pointer['response_sha256'])
        check(response['schema'] == 'stage022_delivery_pointer_v1' and response['request_sha256'] == digest
              and response['receipt_path'] == pointer['receipt_path'] and response['receipt_sha256'] == pointer['receipt_sha256'], 'response linkage')
        receipt = obj(pointer['receipt_path'], pointer['receipt_sha256'])
        check(receipt['schema'] == 'stage021_independent_minute_delivery_v1' and receipt['independent_review'] is True
              and receipt['qualified_research_data'] is True and receipt['reviewer']
              and receipt['p0_findings'] == receipt['p1_findings'] == 0 and receipt['fixture_only'] is False
              and receipt['request_sha256'] == digest and receipt['owner_run_id'] == identity['run_id']
              and receipt['owner_arm'] == 'B_OFF' and receipt['owner_sha256'] == upstream['owner']['sha256'], 'original021 qualification/owner')
        check(receipt['data_path'] == pointer['data_path'] and receipt['data_sha256'] == pointer['data_sha256'], 'receipt data linkage')
        closure = receipt['source_fingerprints']
        check(closure == pointer['source_fingerprints'] == item['source_fingerprints'], 'full source closure mismatch')
        for path, expected in closure.items():
            claim(path, expected, owner)
        check(closure[pointer['data_path']] == pointer['data_sha256'], 'data absent from source closure')
        wanted = {(r['vt_symbol'], r['execution_trade_date'], r['requirement_kind']): r for r in request['requirements']}
        check(len(wanted) == len(request['requirements']), 'duplicate requirement')
        full, anchor, found = set(), set(), set()
        for requirement in receipt['accepted_requirements']:
            ident = (requirement['vt_symbol'], requirement['execution_trade_date'], requirement['requirement_kind'])
            check(ident in wanted and ident not in found and ident[2] in ('anchor', 'full_session'), 'scope identity mismatch')
            check(requirement['accepted'] is True and requirement['completed_bars_and_daily_qualified'] is True
                  and requirement['accepted_timestamps'] == wanted[ident]['required_timestamps'], 'exact timestamp rights mismatch')
            keys = {key(ident[0], t) for t in requirement['accepted_timestamps']}
            check(len(keys) == len(requirement['accepted_timestamps']), 'duplicate required timestamp')
            (full if ident[2] == 'full_session' else anchor).update(keys); found.add(ident)
            existing_sum += len(wanted[ident]['existing_source_timestamps'])
        check(found == set(wanted) and item['accepted_requirements'] == receipt['accepted_requirements'], 'scope incomplete')
        data = rows(read(pointer['data_path'], pointer['data_sha256']))
        check(set(data) == full | anchor and len(data) == event['accepted_keys'] == item['accepted_keys'], 'exact data key scope')
        check(item['appended_keys'] == event['appended_keys'] == captured_scope[digest]['appended_keys'], 'actual append count')
        check(item['reviewer'] == receipt['reviewer'], 'reviewer not inherited')
        appended_sum += event['appended_keys']
        for k, seven in data.items():
            if k in expected_values:
                overlap_count += 1
                check(expected_values[k] == seven, 'seven-value cross-receipt conflict: ' + str(k))
            expected_values[k] = seven
            rights[k] = rights.get(k, False) or k in full
            proofs.setdefault(k, set()).add(digest)
        details.append({'request_sha256': digest, 'gate_index': index, 'receipt_sha256': pointer['receipt_sha256'],
                        'data_sha256': pointer['data_sha256'], 'accepted_keys': len(data),
                        'full_keys': len(full), 'anchor_only_keys': len(anchor - full), 'appended_keys': event['appended_keys']})

    check(manifest['source_fingerprints'] == expected_sources and len(expected_sources) == 2783, 'necessary source closure not exact')
    for path, expected in expected_sources.items():
        if path not in observed:
            check(not Path(path).is_symlink() and sha(path) == expected, 'necessary source SHA changed: ' + path)
            observed[path] = expected
        check(observed[path] == expected, 'necessary source differs from parsed bytes')
    check(not any('/request_' + FAILED + '/' in p for p in expected_sources), 'failed raw/source was included')
    overlay = rows(payloads[str(CANDIDATE / 'overlay.csv')], round_trip=True)
    check(overlay == expected_values, 'candidate overlay differs from159 signed delivery bytes')
    rf = pd.read_csv(io.BytesIO(payloads[str(CANDIDATE / 'rights.csv')]))
    actual_rights = {}
    for row in rf.itertuples(index=False):
        k = key(row.vt_symbol, row.bar_datetime)
        check(k not in actual_rights and row.qualified_full in (0, 1) and row.qualified_anchor == 1, 'rights duplicate/invalid')
        actual_proofs = json.loads(row.proof_requests)
        check(actual_proofs == sorted(set(actual_proofs)), 'proof list is not exact unique sorted')
        actual_rights[k] = bool(row.qualified_full)
        check(set(actual_proofs) == proofs[k], 'proof request mapping differs')
    check(actual_rights == rights, 'full/anchor promotion or key mismatch')
    counts = {'accepted_deliveries': len(details), 'accepted_keys': len(expected_values), 'qualified_full_keys': sum(rights.values()),
              'qualified_anchor_keys': len(rights), 'explicit_anchor_only_keys': sum(not v for v in rights.values())}
    check(all(manifest[k] == v for k, v in counts.items()), 'manifest counts')
    check(counts == {'accepted_deliveries': 159, 'accepted_keys': 36391, 'qualified_full_keys': 36345,
                     'qualified_anchor_keys': 36391, 'explicit_anchor_only_keys': 46}, 'independent counts mismatch')
    check(appended_sum == 31703 == review['actual_capture_scope']['actual_appended_keys_sum']
          and existing_sum == 4688 == review['actual_capture_scope']['existing_request_keys_sum'], 'actual R/E/M facts mismatch')
    comparison = [[k[0], k[1].isoformat(), [x.hex() for x in expected_values[k]], rights[k], sorted(proofs[k])]
                  for k in sorted(expected_values)]
    result = {'schema': 'stage137_independent_actual_off_delta_audit_v1', 'reviewer': 'off_wait_delta_review',
              'completed_at': datetime.now().astimezone().isoformat(), 'all_checks_passed': True,
              'manifest_path': str(CANDIDATE / 'manifest.json'), 'manifest_sha256': PINS[CANDIDATE / 'manifest.json'],
              'counts': counts, 'appended_keys_sum': appended_sum, 'existing_request_keys_sum': existing_sum,
              'cross_receipt_duplicate_occurrences': overlap_count, 'seven_value_or_rights_conflicts': 0,
              'source_fingerprints_verified': len(expected_sources), 'capture_fingerprints_not_globally_rehashed': len(owner),
              'independent_expected_source_map_sha256': hashlib.sha256(canonical(expected_sources)).hexdigest(),
              'rebuilt_seven_values_rights_proofs_sha256': hashlib.sha256(canonical(comparison)).hexdigest(),
              'source_map_exactly_matches_manifest': True, 'all_overlay_values_equal_signed_delivery_bytes': True,
              'full_anchor_and_proofs_exact': True, 'failed_request_excluded': FAILED, 'artifacts': artifacts,
              'old_key_values_unchanged_basis': '159 actual original021 strict equal-only commit events old_keys_changed=0, bound by original065 capture and134 independent audit; not a new global RAM/base-market reconstruction.',
              'original021_qualification_inherited': True, 'old190_layer_remerged_or_requalified': False,
              'partial_capture_unpickled': False, 'old_suite_or_author_two_tests_rerun': False,
              'financial_model_provider_network_guard_readiness_runs': 0, 'details': details,
              'pinned_code_and_manifest': {str(p): digest for p, digest in PINS.items()}}
    write('actual_data_audit.json', result)
    temporary.cleanup()
    print(json.dumps({k: v for k, v in result.items() if k not in ('details', 'pinned_code_and_manifest')}, ensure_ascii=False))


def load_once():
    temporary = configure()
    import stage061_accepted_wait_delta as container
    receipt_path = OUT / 'review_receipt.json'
    receipt_sha = sha(receipt_path)
    audit_path = OUT / 'actual_data_audit.json'
    audit_result = json.loads(audit_path.read_bytes())
    check(audit_result['all_checks_passed'] is True, 'actual audit missing')
    manifest_path = CANDIDATE / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    delta = container.load_accepted_delta(manifest_path, PINS[manifest_path], receipt_path, receipt_sha,
        base_stack=Path(manifest['base_stack_path']), base_stack_sha256=manifest['base_stack_sha256'],
        inherited_anchor_inputs=manifest['inherited_anchor_inputs'])
    check((len(delta.overlay), len(delta.full_keys), len(delta.anchor_keys)) == (36391, 36345, 36391), 'loader counts')
    check(delta.manifest == manifest, 'loader manifest altered')
    result = {'schema': 'stage137_real_unchanged061_loader_acceptance_v1', 'completed_at': datetime.now().astimezone().isoformat(),
              'loader_calls': 1, 'passed': True, 'manifest_path': str(manifest_path), 'manifest_sha256': PINS[manifest_path],
              'review_path': str(receipt_path), 'review_sha256': receipt_sha, 'rows': len(delta.overlay),
              'full_keys': len(delta.full_keys), 'anchor_keys': len(delta.anchor_keys),
              'source_bindings_checked_by_unchanged_loader': len(delta.source_fingerprints),
              'financial_model_provider_network_guard_readiness_runs': 0, 'append_or_market_loader_called': False,
              'frozen_numerical_runtime': True, 'runtime_OUTPUT_redirected_to_reviewer_temporary': True}
    write('loader_acceptance.json', result)
    temporary.cleanup()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    check(len(sys.argv) == 2 and sys.argv[1] in ('audit', 'load-once'), 'choose audit or load-once')
    (audit if sys.argv[1] == 'audit' else load_once)()
