"""Bounded read-only source/preflight review; never calls a provider/run CLI."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import sqlite3
import sys

LINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LINE/'tools'))
import pandas as pd
import stage051_generic_exact_daily_recovery as candidate
import stage021_blocking_data_gate as gate

OUT = Path(__file__).resolve().parent
SHA = '89a2de7464f4b30eb3b3887ac265ca5433c7288fafcb117802072360c6a6228a'
PREFLIGHT_SHA = '692f0c45529fc2984c86d3a814ba09b07f85064d399412aeb97afac0029301d1'
DIGEST = '2359178d438e2191ff3691ebb97a82f41be5c81f8fa3ecd279e5b0a631e9093a'
FOLDER = candidate.OUTPUT_ROOT/('request_'+DIGEST)
inputs = {}

def bind(path, expected=None):
    path = Path(path).resolve(); value = hashlib.sha256(path.read_bytes()).hexdigest()
    assert expected is None or value == expected, str(path)
    inputs[str(path)] = value
    return value

def function(path, name):
    return next(n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)

def main():
    bind(__file__); bind(candidate.__file__, SHA); bind(FOLDER/'preflight.json', PREFLIGHT_SHA)
    frozen = json.loads((FOLDER/'preflight.json').read_text())
    request, _ = candidate.request_provider.read_request(frozen['request_path'], frozen['request_file_sha256'])
    assert gate.request_sha256(request) == frozen['request_sha256'] == DIGEST
    assert frozen['selected_symbols'] == ['SM009.CZCE'] and frozen['contracts'] == frozen['target_real_days'] == 1
    assert frozen['target_full_session_days'] == 1 and frozen['target_anchor_days'] == 0
    assert frozen['duration_seconds'] == 86400 and frozen['data_length'] == 10000
    assert frozen['planned_TqApi_max'] == frozen['planned_TqSim_max'] == 1
    assert frozen['soft_seconds'] == 570 and frozen['hard_seconds'] == 600 and frozen['memory_budget_bytes'] == 1500000000
    assert not frozen['automatic_retry'] and frozen['provider_connections'] == frozen['TqBacktest_instances'] == 0
    # Rehash only this finite preflight dependency set; accepted DB identity is
    # inherited rather than a second full database scan. Query its exact row below.
    for path, expected in frozen['source_fingerprints'].items():
        if Path(path).resolve() != candidate.DATABASE.resolve():
            bind(path, expected)
    assert frozen['source_fingerprints'][str(candidate.DATABASE)] == candidate.DB_SHA
    bind(FOLDER/'target_manifest.csv', frozen['target_manifest_sha256'])
    bind(FOLDER/'excluded_constraints.csv', frozen['excluded_constraints_sha256'])
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(candidate.MAPPING, usecols=['date']).date.unique())).sort_values()
    selected = candidate.select_requirements(request, frozen['selected_symbols'], calendar)
    assert len(selected) == 1 and selected[0]['vt_symbol'] == 'SM009.CZCE'
    target = selected[0]
    assert target['execution_trade_date'] == '2020-04-15' and target['requirement_kind'] == 'full_session'
    assert len(target['required_timestamps']) == len(target['missing_or_unqualified_timestamps']) == 225
    assert not target['existing_source_timestamps']
    original = candidate.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04/CZCE/SM009.csv'
    review = json.loads(candidate.R013.read_text())
    q = pd.read_csv(review['qualified_daily_path']); a = pd.read_csv(review['target_qualification_path'])
    approved = candidate.daily_refs.approved_references(q, a, review)
    rejected = {(str(x['vt_symbol']), str(x['trade_date'])) for x in review['rejected_targets']}
    candidate.require_missing_reference(('SM009.CZCE', '2020-04-15'), original.is_file(), approved, rejected)
    with sqlite3.connect(candidate.DATABASE.resolve().as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute("SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata "
            "WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=?",
            ('SM009', 'CZCE', '2020-04-15')).fetchall()
    assert rows == [(6910., 6998., 6910., 6982., 104359., 68585.)]
    manifest = pd.read_csv(FOLDER/'target_manifest.csv')
    assert len(manifest) == 1 and manifest.iloc[0].vt_symbol == 'SM009.CZCE'
    assert tuple(float(manifest.iloc[0][x]) for x in candidate.DB_FIELDS) == rows[0]
    # Execute only the local path binder, never preflight/run/worker/provider.
    candidate.bind_preflight(FOLDER/'preflight.json')
    assert candidate.OUTPUT == FOLDER and candidate.ATTEMPT == FOLDER/'network_attempt1' and candidate.REQUEST_DIGEST == DIGEST
    old_source = LINE/'tools/stage040_exact_request_daily_recovery.py'
    bind(old_source, '32ddecd055d7bb52b8d7f68ab8f1c5d3023ce0943f47045620b254d4e09cc820')
    old_worker, new_worker = function(old_source, 'worker'), function(candidate.__file__, 'worker')
    assert ast.unparse(new_worker.body[0]) == 'bind_preflight(preflight_path)'
    assert [ast.dump(x, include_attributes=False) for x in new_worker.body[1:]] == [ast.dump(x, include_attributes=False) for x in old_worker.body]
    for name in ['atomic_csv', 'peak_memory', 'budget_guard']:
        assert ast.dump(function(old_source, name), include_attributes=False) == ast.dump(function(candidate.__file__, name), include_attributes=False)
    run_source, main_source = ast.unparse(function(candidate.__file__, 'run_once')), ast.unparse(function(candidate.__file__, 'main'))
    assert 'worker(args._worker, args.preflight)' in main_source
    assert 'run_once(args.preflight, args.source_sha256)' in main_source
    assert "'--preflight', str(Path(preflight_path).resolve())" in run_source
    assert 'str(Path(__file__).resolve())' in run_source and 'bind_preflight(preflight_path)' in run_source
    assert candidate.qualify_daily_snapshot is candidate.daily013.qualify_daily_snapshot
    result = dict(schema='stage053_daily_provider_source_preflight_independent_review_v1',
        reviewed_at=datetime.now().astimezone().isoformat(), independent_review=True, reviewer='delivery_guard_readonly',
        p0_findings=0, p1_findings=0, approved_for_one_actual_provider_run=True,
        qualification_signed=False, conclusion='current_SM009_actual_request_source_and_preflight_accepted',
        reviewed_source_sha256=SHA, preflight_path=str(FOLDER/'preflight.json'), preflight_sha256=PREFLIGHT_SHA,
        request_sha256=DIGEST, selected_symbols=['SM009.CZCE'], target_day='2020-04-15', target_kind='full_session', target_minutes=225,
        exact_database_six=list(rows[0]), database_closeOI='N/A_not_independently_available',
        database_identity_inherited=candidate.DB_SHA, database_full_hash_recomputed_in_review=False,
        normal_API_worker_body_AST_equal_to_040_after_explicit_path_binding=True,
        generic_CLI_parent_worker_path_and_digest_binding_checked=True,
        original_CSV_or_013_approved_or_rejected_override_forbidden=True,
        source_fingerprints=inputs,
        boundaries=['Source/preflight approval only; raw output and actual terminal do not yet have independent qualification.',
            'Root must observe real provider terminal before Stage052 can qualify the exact raw/six-fields/successor.',
            'No generic multi-symbol actual provider run or future unsupported demand was exercised.',
            'Normal SDK source identity inherited from Stage013 and matched to this finite preflight, without network/auth changes.'],
        network_connections=0, financial_replays=0, model_fits=0, orders=0, engine_loaded=False,
        original_inputs_modified=False, production_qualified=False)
    path = OUT/'review_receipt.json'
    with path.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps(dict(status='accepted', approved_for_one_actual_provider_run=True, receipt_path=str(path), receipt_sha256=bind(path))))

if __name__ == '__main__':
    main()
