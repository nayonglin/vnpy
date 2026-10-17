"""Bounded independent read-only audit of two consumed Stage048 deliveries.

Writes only this new review directory. Never runs providers, financial engines,
the driver, or the Stage048 signing CLI; inherited source qualifications remain
inherited rather than being repeated here.
"""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import sys

LINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LINE / 'tools'))
import numpy as np
import pandas as pd
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate

OUT = Path(__file__).resolve().parent
SHA048 = '3b220aadeb1e8091a35d84624b643c3a0b276c6e3f4be9874293a9abaecd785a'
SHA044 = '1a27fa40efab481330bed6d3ac8714ddbd414a785d84200578001a8fcc7c5445'
SHA021 = '150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'
FAMILIES = {'037': '19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1',
            '041': 'e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d'}
bound = {}

def read(p):
    return json.loads(Path(p).read_text())

def bind(p, expected=None):
    p = Path(p).resolve()
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert expected is None or digest == expected, str(p)
    assert str(p) not in bound or bound[str(p)] == digest
    bound[str(p)] = digest
    return digest

def keys(frame):
    return {(str(r.vt_symbol), pd.Timestamp(r.bar_datetime)) for r in frame.itertuples(index=False)}

def fn_ast(path, name):
    tree = ast.parse(Path(path).read_text())
    return ast.dump(next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name), include_attributes=False)

def main():
    bind(__file__)
    bind(LINE / 'tools/stage048_general_provider_delivery.py', SHA048)
    bind(LINE / 'tools/stage044_qualified_wait_driver.py', SHA044)
    bind(gate.__file__, SHA021)
    for number, digest in FAMILIES.items():
        name = 'stage037_b_ts_request_provider.py' if number == '037' else 'stage041_exact_daily_request_provider.py'
        bind(LINE / 'tools' / name, digest)
    # The original legality/key helpers are inherited unchanged; no broad suite.
    old_reader = LINE / 'outputs/stage043_exact_request_delivery/review_provider_delivery.py'
    for name in ['read', 'write', 'keys', 'legal']:
        assert fn_ast(old_reader, name) == fn_ast(LINE / 'tools/stage048_general_provider_delivery.py', name)
    bind(old_reader, '373493d9eb50647063044e53c2c669584f237345cf2a8edf8f5d0d282c1b1d54')
    batch = LINE / 'outputs/stage044_qualified_wait_driver/batch002'
    manifest, journal = read(batch / 'manifest.json'), read(batch / 'journal.json')
    bind(batch / 'manifest.json', journal['manifest_sha256']); bind(batch / 'journal.json')
    assert journal['source_sha256'] == SHA044
    assert journal['status'] == 'paused_provider_batch_limit' and journal['provider_connections'] == 4
    assert sum(e.get('source') == 'local' for e in journal['events']) == 15
    assert sum(e.get('source') == 'provider' for e in journal['events']) == 4
    anchors, scans = old.A0 / 'execution_anchor_requests.csv', old.A0 / 'minute_scan_requests.csv'
    bind(anchors, '72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
    bind(scans, 'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
    bind(old.MAPPING, '55e95a468f4ebd989e5db4da282d69a319ebc75ea08a068e1be8ff87ef1ff325')
    calendar = pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(old.MAPPING, usecols=['date']).date.unique())))
    sample_results = []
    for index, family in [(3, '041'), (17, '037')]:
        event = journal['events'][index]
        receipt_path = Path(event['receipt_path']); bind(receipt_path, event['receipt_sha256'])
        receipt = read(receipt_path); checks_path = receipt_path.with_name('checks.json')
        bind(checks_path, receipt['source_fingerprints'][str(checks_path)]); checks = read(checks_path)
        bind(event['request_path'], event['request_file_sha256']); request = read(event['request_path'])
        assert gate.request_sha256(request) == event['request_sha256'] == receipt['request_sha256']
        folder = Path(checks['packets'][0]['packet_dir']); packet = read(folder / 'packet_manifest.json')
        terminal_path = folder / 'terminal_observed.json'
        bind(terminal_path, checks['packets'][0]['root_terminal_sha256']); terminal = read(terminal_path)
        assert terminal == event['provider_terminal'] and terminal['source_sha256'] == FAMILIES[family]
        assert terminal['driver_source_sha256'] == SHA044
        assert terminal['schema'] == 'stage041_provider_actual_tool_terminal_v1'
        assert terminal['terminal_observed'] is True and terminal['subprocess_returncode'] == 0
        assert terminal['exit_code'] == terminal['worker_exit_code'] == 0 and terminal['all_inputs_unchanged'] is True
        assert terminal['request_sha256'] == request['request_sha256']
        assert terminal['new_provider_connections'] == terminal['new_minute_provider_connections'] == 1
        bind(folder / 'preflight.json', terminal['preflight_sha256']); preflight = read(folder / 'preflight.json')
        bind(folder / 'packet_manifest.json', preflight['source_fingerprints'][str(folder / 'packet_manifest.json')])
        assert preflight['source_fingerprints'][terminal['provider_source_path']] == FAMILIES[family]
        attempt = folder / 'network_attempt1'
        bind(attempt / 'parent_receipt.json', terminal['parent_receipt_sha256']); parent = read(attempt / 'parent_receipt.json')
        assert parent['status'] == 'worker_terminal' and parent['exit_code'] == 0 and not parent['hard_kill']
        assert parent['all_inputs_unchanged'] is True and parent['provider_attempts_max'] == 1 and not parent['automatic_retry']
        assert parent['elapsed_seconds'] < 600 and not parent['response_written'] and not parent['production_qualified']
        for name, digest in parent['artifact_sha256'].items():
            bind(attempt / name, digest)
        worker, quality = read(attempt / 'worker_receipt.json'), read(attempt / 'quality.json')
        assert worker['status'] == 'all_target_minutes_completed' and quality['packet_all_targets_accepted'] is True
        assert worker['completed_minutes'] == worker['target_minutes'] == packet['packet_required_minutes'] == 225
        assert worker['provider_attempts'] == 1 and worker['local_TqSim_created'] is True
        assert worker['request_sha256'] == quality['request_sha256'] == parent['request_sha256'] == request['request_sha256']
        for obj in [worker, parent]:
            assert all(obj[k] == 0 for k in ['financial_replays', 'orders', 'cancels', 'broker_or_ctp_connections'])
            assert not obj['credential_values_saved'] and not obj['raw_sdk_output_saved'] and not obj['cache_or_overlay_written']
        data, full, anchor, info = gate._read_delivery(request, gate.QualifiedDelivery(receipt_path, event['receipt_sha256']))
        raw = old.normal_times(pd.read_csv(attempt / 'raw_completed_minutes.csv'))
        proof = old.normal_times(pd.read_csv(attempt / 'completion_evidence.csv'))
        assert len(data) == len(raw) == len(proof) == len(full) == 225 and not anchor
        assert keys(data) == keys(raw) == keys(proof) and not old.minute_keys(proof).has_duplicates
        data = data.sort_values(['vt_symbol', 'bar_datetime']).reset_index(drop=True)
        raw = raw.sort_values(['vt_symbol', 'bar_datetime']).reset_index(drop=True)
        assert np.array_equal(data[old.VALUES].to_numpy(float), raw[old.VALUES].to_numpy(float))
        successors = pd.to_datetime(proof.successor_time)
        assert proof.completed.astype(str).str.lower().eq('true').all()
        assert proof.method.eq('observed_later_serial_kline').all()
        assert (successors >= proof.bar_datetime + pd.Timedelta(minutes=1)).all()
        required, existing, missing = set(), set(), set()
        for target in request['requirements']:
            symbol = target['vt_symbol']
            sets = [{(symbol, pd.Timestamp(t)) for t in target[k]} for k in ['required_timestamps', 'existing_source_timestamps', 'missing_or_unqualified_timestamps']]
            R, E, M = sets
            assert E <= R and M <= R and (R-E) <= M and M
            required |= R; existing |= E; missing |= M
        assert keys(data) == required and len(existing) == 0
        target = packet['targets'][0]; daily_path = Path(target['daily_reference_path'])
        bind(daily_path, preflight['source_fingerprints'][str(daily_path)])
        daily = pd.read_csv(daily_path); hit = daily.loc[pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d').eq(target['execution_trade_date'])]
        if 'vt_symbol' in daily:
            hit = hit.loc[hit.vt_symbol.eq(target['vt_symbol'])]
        assert len(hit) == 1 and all(float(hit.iloc[0][k]) == float(v) for k, v in target['daily_reference'].items())
        aggregate = dict(open=float(raw.open.iloc[0]), high=float(raw.high.max()), low=float(raw.low.min()), close=float(raw.close.iloc[-1]),
                         volume=float(raw.volume.sum()), open_oi=float(raw.open_oi.iloc[0]), close_oi=float(raw.close_oi.iloc[-1]))
        assert all(np.isclose(v, target['daily_reference'][k], rtol=1e-12, atol=1e-8) for k, v in aggregate.items())
        if family == '041':
            bind(packet['daily_review_path'], packet['daily_review_sha256']); daily_review = read(packet['daily_review_path'])
            assert daily_review['independent_review'] is True and daily_review['qualified_research_daily'] is True
            assert daily_review['request_sha256'] == request['request_sha256'] and not daily_review['p0_findings'] and not daily_review['p1_findings']
            assert [target['vt_symbol'], target['execution_trade_date']] in daily_review['accepted_target_keys']
            assert daily_review['six_fields_checked'] and daily_review['actual_raw_forward_successor_checked']
        new_data = data.loc[[(str(r.vt_symbol), pd.Timestamp(r.bar_datetime)) not in existing for r in data.itertuples(index=False)]]
        disjoint = old.prove_read_disjointness(new_data, pd.read_csv(anchors), pd.read_csv(scans), calendar)
        assert disjoint['intersection_count'] == 0 and disjoint['added_keys'] == 225
        pointer_path = Path(event['response_path']); bind(pointer_path, event['response_sha256']); pointer = read(pointer_path)
        assert pointer['receipt_path'] == str(receipt_path) and pointer['receipt_sha256'] == event['receipt_sha256']
        sample_results.append(dict(family=family, request_sha256=request['request_sha256'], receipt_path=str(receipt_path),
            receipt_sha256=event['receipt_sha256'], vt_symbol=target['vt_symbol'], day=target['execution_trade_date'],
            required=len(required), existing=len(existing), missing=len(missing), new_physical=len(new_data),
            raw_proof_key_identity=True, forward_completion_proofs=len(proof), daily_seven=aggregate,
            daily_reference_source=target['daily_reference_source'], terminal_parent_artifact_hashes_verified=True,
            A0_new_physical_intersection=disjoint['intersection_count'], actual_stage021_parser_passed=True))
    result = dict(schema='stage049_bounded_general_provider_review_v1', reviewed_at=datetime.now().astimezone().isoformat(),
        independent_review=True, reviewer='delivery_guard_readonly', p0_findings=0, p1_findings=0,
        conclusion='accepted_for_reviewed_semantics_and_two_exact_samples', samples=sample_results,
        batch=dict(deliveries=19, local=15, provider=4, provider_connections=4, status=journal['status']),
        semantic_review=dict(R='required unique complete keys', E='physical existing unique subset of R',
            M='missing or unqualified unique nonempty subset of R', mandatory_relation='R minus E is a subset of M',
            delivery_scope='exactly R; no outside keys', A0_scope='R minus E only',
            old_values='runtime frozen Stage021 exact seven-value overlap comparison before commit; reader does not reload base cache',
            family_selection='fixed 037 or 041 source hash and root; mixed families rejected'),
        inherited_boundaries=['No E>0 provider sample in batch002; that branch is source-reviewed only.',
            'Provider connection terminal observation is inherited from root-observed driver and pinned terminal; no new provider execution.',
            'Original Stage013 and Stage047 daily qualification retained, not independently requalified.',
            'Completion outside delivery is frozen collector observed successor metadata, without independently exported successor OHLC.',
            'Full financial backtest result, all local deliveries, source stack, runtime E>0 value equality and profitability not reviewed.'],
        source_fingerprints=bound, source_stack_requalified=False, engine_loaded=False, network_connections=0,
        financial_replays=0, model_fits=0, orders=0, original_inputs_modified=False, production_qualified=False)
    for path, digest in bound.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    destination = OUT / 'review_receipt.json'
    with destination.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps(dict(status='accepted', samples=len(sample_results), receipt_path=str(destination), receipt_sha256=bind(destination))))

if __name__ == '__main__':
    main()
