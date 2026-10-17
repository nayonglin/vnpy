"""Bounded independent failure review; never exports or inspects partial PnL."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import ast
import hashlib
import json

LINE = Path(__file__).resolve().parents[2]
B = LINE/'outputs/stage036_b_ts_account/B_TS'
OUT = Path(__file__).resolve().parent
LAST = '6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730'
sources = {}

def read(path):
    return json.loads(Path(path).read_text())

def bind(path, expected=None):
    path = Path(path).resolve(); digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert expected is None or digest == expected, str(path)
    sources[str(path)] = digest
    return digest

def write(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write('\n')

def main():
    bind(__file__)
    terminal_path = LINE/'outputs/stage063_b_ts_actual_failure/actual_tool_terminal.json'
    bind(terminal_path, '8f556fb6b76c27f28db7ff7799643bda5c7e934c844a29546545efe10d21981b')
    terminal = read(terminal_path)
    assert terminal['financial_terminal_observed'] and terminal['financial_exit_code'] == 1
    assert terminal['data_terminal_observed'] and terminal['data_exit_code'] == 1
    assert terminal['actual_failure_cause'] == 'qualified_delivery_old_value_conflict'
    assert terminal['whole_run_timeout_was_failure_cause'] is False
    bind(B/'run_failure.json', terminal['run_failure_sha256']); failure = read(B/'run_failure.json')
    bind(terminal['data_driver_journal_path'], terminal['data_driver_journal_sha256']); journal = read(terminal['data_driver_journal_path'])
    bind(terminal['data_chain_journal_path'], terminal['data_chain_journal_sha256'])
    bind(B/'data_wait/audit.json'); resolver = read(B/'data_wait/audit.json')
    bind(B/'qualified_wait_audit.json'); persisted = read(B/'qualified_wait_audit.json')
    assert failure['status'] == 'failed_closed_no_accepted_performance' and failure['arm'] == 'B_TS' and failure['attempt'] == 1
    assert failure['raw_checkpoint'] is None and failure['validation_seal_exists'] is False
    assert failure['captured_bar_failures'] == [dict(datetime='2022-05-31 00:00:00+08:00', error="ValueError('qualified_delivery_old_value_conflict')")]
    assert failure['resolver_audit'] == resolver == persisted['resolver']
    gate = failure['qualified_wait_gate_audit']; assert gate == persisted['gate']
    counts = dict(Counter(row['event'] for row in gate))
    assert counts == dict(data_requested=191, data_qualified_appended=190, data_gate_failed=1)
    requested = [r for r in gate if r['event'] == 'data_requested']
    assert [r['request_sequence'] for r in requested] == list(range(1,192))
    assert len({r['request_sha256'] for r in requested}) == 191
    accepted = {r['request_sha256']: r for r in resolver if r['status'] == 'qualified_delivery_pointer_accepted'}
    appended = [r for r in gate if r['event'] == 'data_qualified_appended']
    assert len(accepted) == len(resolver) == 191
    assert len({r['request_sha256'] for r in appended}) == 190
    assert set(accepted) - {r['request_sha256'] for r in appended} == {LAST}
    assert {r['request_sha256'] for r in appended} <= set(accepted)
    for row in appended:
        assert row['old_keys_changed'] == 0
        assert all(row[key] == accepted[row['request_sha256']][key] for key in ['receipt_path','receipt_sha256','data_path','data_sha256'])
    assert gate[-1] == dict(event='data_gate_failed', request_sha256=LAST, error_type='ValueError')
    last = resolver[-1]; assert last['request_sha256'] == LAST
    bind(last['request_path'], last['request_file_sha256']); request = read(last['request_path'])
    canonical = {k:v for k,v in request.items() if k != 'request_sha256'}
    assert hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode()).hexdigest() == LAST
    assert request['request_sequence'] == 191 and request['execution_trade_date'] == '2022-05-31'
    target = request['requirements'][0]
    assert len(request['requirements']) == 1 and target['vt_symbol'] == 'fu2209.SHFE' and target['requirement_kind'] == 'full_session'
    R,E,M = [set(target[k]) for k in ['required_timestamps','existing_source_timestamps','missing_or_unqualified_timestamps']]
    assert len(R) == 345 and len(E) == 226 and len(M) == 344 and E <= R and M <= R and R-E <= M
    bind(last['response_path'], last['response_sha256']); pointer = read(last['response_path'])
    bind(last['receipt_path'], last['receipt_sha256']); receipt = read(last['receipt_path'])
    bind(receipt['data_path'], receipt['data_sha256'])
    assert pointer['receipt_sha256'] == last['receipt_sha256'] and receipt['request_sha256'] == LAST
    accepted_requirement = receipt['accepted_requirements'][0]
    assert accepted_requirement['accepted_timestamps'] == target['required_timestamps']
    dest = Path(last['receipt_path']).parent
    for name in ['key_checks.json','local_checks.json','completion_evidence.csv']:
        bind(dest/name, receipt['source_fingerprints'][str(dest/name)])
    bind(dest/'parse_result.json'); parsed = read(dest/'parse_result.json')
    key_checks = read(dest/'key_checks.json')
    assert parsed['actual_stage021_parser_passed'] is True and parsed['receipt_sha256'] == last['receipt_sha256']
    assert key_checks['old_physical_values_independently_compared'] is False
    assert key_checks['old_value_comparison_delegated_to_actual_stage021'] is True
    assert key_checks['A0_actual_read_disjointness']['intersection_count'] == 0
    assert key_checks['request_scope_existing_physical_keys'] == 226 and key_checks['new_request_scope_physical_keys'] == 119
    assert journal['status'] == 'blocked' and journal['provider_connections'] == 2
    assert 'ps' in journal['blocked_reason'] and journal['events'][-1]['request_sha256'] == LAST
    assert journal['events'][-1]['receipt_sha256'] == last['receipt_sha256']
    presence = {name:(B/name).exists() for name in ['checkpoint','checkpoint/raw_account.pkl.gz','checkpoint/raw_manifest.json','checkpoint/validation_seal.json','summary.json','export_success.json','daily.csv','execution_clock.csv']}
    assert not any(presence.values())
    bind(B/'engine.log'); assert (B/'engine.log').stat().st_size == 0
    source = LINE/'tools/stage036_run_b_ts_checkpoint.py'
    bind(source, terminal['runner_source_sha256']); bind(B/'runner_used.py', terminal['used_runner_sha256'])
    bind(LINE/'tools/stage021_blocking_data_gate.py', '150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b')
    bind(LINE/'tools/stage052_generic_daily_source_resolver.py', receipt['source_fingerprints'][str(LINE/'tools/stage052_generic_daily_source_resolver.py')])
    tree = ast.parse(source.read_text())
    expected_a0 = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id == 'A0_SHA' for t in n.targets)))
    unchanged = {}
    for name,digest in expected_a0.items():
        path = LINE/'outputs/stage001_first_screen/A0_attempt2'/name
        unchanged[str(path)] = bind(path,digest)
    for path,digest in receipt['source_fingerprints'].items():
        if 'source_manifest.json' in path or 'downloaded_futures/' in path:
            unchanged[path] = bind(path,digest)
    reconciliation = [{k:r[k] for k in ['request_sha256','receipt_path','receipt_sha256','data_path','data_sha256','old_keys_changed']} for r in appended]
    excluded = dict(schema='stage064_runtime_rejected_delivery_exclusion_v1',request_sha256=LAST,
        receipt_path=last['receipt_path'],receipt_sha256=last['receipt_sha256'],data_path=receipt['data_path'],data_sha256=receipt['data_sha256'],
        independent_data_receipt_accepted=True,pointer_parser_accepted=True,runtime_gate_accepted=False,
        data_qualified_appended=False,new_keys_committed_by_this_delivery=0,full_or_anchor_rights_granted_by_this_delivery=0,
        inheritance_eligible=False,reason='Runtime Stage021 old-value comparison rejected before atomic mapping/qualification update.',
        prior_independently_accepted_rights_not_revoked=True,original_receipt_or_data_modified=False)
    write(OUT/'excluded_delivery.json',excluded); bind(OUT/'excluded_delivery.json')
    evidence = dict(schema='stage064_B_TS_failure_independent_evidence_v1',reviewed_at=datetime.now().astimezone().isoformat(),
        reviewer='delivery_guard_readonly',actual_terminal_source=str(terminal_path),failure_trade_date='2022-05-31',
        failure_cause='qualified_delivery_old_value_conflict',timeout_cause=False,
        financial_tool_session=70433,financial_exit_code=1,data_tool_session=43111,data_exit_code=1,
        actual_tool_observation_inherited_from_root=True,elapsed_wall_seconds=terminal['elapsed_wall_seconds'],
        observed_data_wait_seconds=terminal['observed_data_wait_seconds'],gate_event_counts=counts,
        pointer_acceptances=191,runtime_appended_receipts=190,unique_appended_receipts=190,
        matching_receipt_and_data_bindings=190,all_appended_old_keys_changed_zero=True,
        accepted_without_runtime_append=[LAST],runtime_append_without_acceptance=[],
        canonical_reconciliation_sha256=hashlib.sha256(json.dumps(reconciliation,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        final_request=dict(sequence=191,symbol='fu2209.SHFE',day='2022-05-31',kind='full_session',required=345,existing=226,missing_or_unqualified=344,new_physical=119),
        last_receipt_claim=dict(old_values_independently_compared=False,comparison_delegated_to_frozen_actual_stage021=True,
            claimed_engine_old_values_all_equal=False,standalone_completion_daily_qualification_is_not_atomic_merge_acceptance=True),
        exclusion_path=str(OUT/'excluded_delivery.json'),full_account_artifact_presence=presence,engine_log_bytes=0,
        raw_checkpoint=None,validation_seal=False,complete_performance='N/A',export_only_recovery_available=False,
        batch038=dict(status='blocked',provider_connections=2,reason='B process already exited; later ps identity check failed.',journal_reason=journal['blocked_reason']),
        finite_old_assets_unchanged=unchanged,full_minute_baseline_or_all_market_bytes_rehashed=False,
        finite_hash_scope='A0 four accepted files; two accepted source manifests; bound fu2209 daily plus three local minute CSVs; frozen runner and gate.',
        concrete_conflicting_fields_and_base_origin='Separately investigated by root; not duplicated or inferred here.',
        unrelated_pairwise_PIT_findings='Stage057/058 P1 remain; not the exception or failure cause of this run.',
        accounting=dict(B_TS_attempt=1,B_TS_result='failed',global_attempts_inherited_from_root=8,complete_account_reviews_inherited_from_root=3,additional_financial_replays_in_this_review=0),
        source_fingerprints=sources,model_fits=0,predictions=0,network_connections=0,financial_replays=0,orders=0,
        partial_PnL_reported=False,original_inputs_or_receipts_modified=False,production_qualified=False)
    for path,digest in sources.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest,path
    write(OUT/'evidence.json',evidence); evidence_sha = bind(OUT/'evidence.json')
    review = dict(schema='stage064_B_TS_failure_independent_review_receipt_v1',independent_review=True,reviewer='delivery_guard_readonly',
        reviewed_at=datetime.now().astimezone().isoformat(),status='failed_closed_confirmed_no_complete_performance',
        evidence_path=str(OUT/'evidence.json'),evidence_sha256=evidence_sha,source_fingerprints=sources,
        p0_findings=0,p1_findings=1,p2_findings=1,
        p1_scope='Runtime old-value incompatibility prevents complete financial result; concrete cause separately investigated, not attributed to alpha or model.',
        p2_scope='Pointer/data acceptance alone cannot seed inheritance; require corresponding runtime-appended evidence and pinned identities.',
        result_qualified=False,last_delivery_inheritance_qualified=False,complete_metrics='N/A',
        financial_replays=0,model_fits=0,predictions=0,network_connections=0,orders=0,partial_PnL_reported=False,production_qualified=False)
    write(OUT/'review_receipt.json',review)
    print(json.dumps(dict(status=review['status'],receipt_path=str(OUT/'review_receipt.json'),
        receipt_sha256=hashlib.sha256((OUT/'review_receipt.json').read_bytes()).hexdigest(),evidence_sha256=evidence_sha)))

if __name__ == '__main__':
    main()
