"""Review only Stage008 qualification delta; reuse Stage007 345-row checks."""
from pathlib import Path
from datetime import datetime
import ast
import csv
import hashlib
import json

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage008_oi_requalification'
PRIOR = LINE / 'outputs/stage007_tqsdk_stream_probe/network_attempt1'
PRIOR_REVIEW = LINE / 'outputs/stage007_independent_review'
RAW_SHA = '0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac'
EVIDENCE_SHA = '3eecacbf83069daac6e0508b5ebdb79e6db50ba60b89b1486d76ce2979f8aff2'
QUALITY_SHA = '9bf02a770b12c7fe65d2efb105e3bfc4f29227d2961352eb0a614a6d5eb6625e'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def main():
    assert sha(PRIOR_REVIEW / 'review_receipt.json') == '3e2e7c1e89cd53b48c8d547119984db7cd482895a093b729eac1fbde61aa12c3'
    prior_receipt = json.loads((PRIOR_REVIEW / 'review_receipt.json').read_text())
    assert all(sha(PRIOR_REVIEW / name) == digest for name, digest in prior_receipt['review_artifact_sha256'].items())
    prior_checks = json.loads((PRIOR_REVIEW / 'probe_evidence_checks.json').read_text())
    summary = json.loads((SOURCE / 'requalification.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    assert all(sha(path) == digest for path, digest in inputs.items())
    assert all(sha(SOURCE / name) == digest for name, digest in summary['artifact_sha256'].items())
    old_preflight = json.loads((PRIOR.parent / 'preflight.json').read_text())
    for path, digest in inputs.items():
        if path in old_preflight['source_fingerprints']:
            assert digest == old_preflight['source_fingerprints'][path]
    assert sha(PRIOR / 'raw_completed_minutes.csv') == summary['raw_sha256'] == RAW_SHA
    assert sha(PRIOR / 'completion_evidence.csv') == summary['completion_evidence_sha256'] == EVIDENCE_SHA
    assert sha(PRIOR / 'quality.json') == summary['original_probe']['quality_sha256'] == QUALITY_SHA
    original = json.loads((PRIOR / 'quality.json').read_text())
    assert original['accepted'] is False and original['database_check']['daily_mismatch_fields'] == ['close_oi']
    assert summary['original_probe']['status'] == 'completed_quality_rejected'
    assert summary['original_probe']['exit_code'] == 1 and summary['original_probe']['original_accepted'] is False
    assert summary['original_probe']['unchanged']
    assert summary['accepted'] and summary['all_inputs_unchanged']
    assert summary['vt_symbol'] == 'rb2010.SHFE' and summary['target_trading_date'] == '2020-08-12'
    assert summary['database_close_oi'] == 'N/A_not_independently_available'
    assert summary['minute_check']['aggregate'] == prior_checks['independent_minute_aggregate']
    assert summary['minute_check']['accepted'] and summary['minute_check']['rows'] == 345
    assert summary['completion_check']['accepted'] and summary['completion_check']['evidence_rows'] == 345
    assert summary['completion_check']['final_target_time'] == prior_checks['last_target_bar']
    assert summary['completion_check']['final_successor_time'] == prior_checks['observed_successor_for_last_target']
    assert summary['importer_semantics']['sha256'] == prior_checks['importer_sha256']
    assert summary['importer_semantics']['line'] == prior_checks['importer_open_interest_keyword_line'] == 115

    # Verify exactly 7 CSV + 5 DB OHLCV + 1 DB openOI comparisons, using prior independent values.
    target_db = next(row for row in prior_checks['DB_vs_CSV_OI'] if row['date'] == '2020-08-12')
    aggregate = prior_checks['independent_minute_aggregate']
    expected_keys = {('csv', field, field) for field in aggregate}
    expected_keys |= {('database', field, field) for field in ['open', 'high', 'low', 'close', 'volume']}
    expected_keys.add(('database', 'open_interest', 'open_oi'))
    checks = summary['field_checks']
    assert len(checks) == 13
    assert {(r['source'], r['source_field'], r['aggregate_field']) for r in checks} == expected_keys
    for row in checks:
        value = aggregate[row['aggregate_field']]
        if row['source'] == 'database' and row['source_field'] == 'open_interest':
            value = target_db['database_open_interest']
        assert row['reference_value'] == row['aggregate_value'] == value
        assert row['absolute_difference'] == 0 and row['matches'] is True
    with (SOURCE / 'field_checks.csv').open(newline='') as f:
        table = list(csv.DictReader(f))
    assert len(table) == 13
    assert {(r['source'], r['source_field'], r['aggregate_field']) for r in table} == expected_keys
    assert all(r['matches'] == 'True' and float(r['absolute_difference']) == 0 for r in table)
    assert not any(r['source'] == 'database' and r['aggregate_field'] == 'close_oi' for r in checks)
    # Only inspect the last saved completion record; do not repeat the accepted full grid audit.
    with (PRIOR / 'completion_evidence.csv').open(newline='') as f:
        last = list(csv.DictReader(f))[-1]
    assert last['bar_datetime'] == '2020-08-12T14:59:00' and last['successor_time'] == '2020-08-12T21:00:00'

    tool = LINE / 'tools/stage008_oi_requalification.py'
    tree = ast.parse(tool.read_text())
    calls = [n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else ''
             for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not set(calls) & {'TqApi', 'TqSim', 'TqAuth', 'insert_order', 'cancel_order', 'run_backtesting', 'urlopen', 'get', 'post'}
    for field in ['network_calls', 'provider_replays', 'TqApi_instances', 'TqSim_instances',
                  'financial_strategy_replays', 'order_calls', 'cancel_calls', 'model_fits', 'source_writes']:
        assert summary[field] == 0
    assert not summary['cache_or_overlay_written'] and not summary['execution_fallback_enabled'] and not summary['production_qualified']

    report = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_qualification_delta_review_pass_accept_exact_345_minutes_for_research', p0_findings=0, p1_findings=0,
        qualified_research_data=True, scope=dict(vt_symbol='rb2010.SHFE', trading_date='2020-08-12', rows=345, raw_sha256=RAW_SHA),
        prior_345_grid_legal_completion_and_7_field_review_reused=True,
        prior_review_receipt_sha256=sha(PRIOR_REVIEW / 'review_receipt.json'),
        full_345_price_grid_or_aggregate_repeated=False, independent_new_SQL_queries=0,
        qualification_fields=13, CSV_fields=7, database_OHLCV_fields=5, database_openOI_fields=1,
        qualification_values_exact=True, database_closeOI='N/A_not_independently_available',
        observed_final_completed_bar=last, importer_semantics_source_same=True,
        original_Stage007_quality_rejected_unchanged=True, original_Stage007_quality_sha256=QUALITY_SHA,
        prior_Stage007_field_mapping_P1_handled_by_separate_source_aware_contract=True,
        old_Stage007_tool_or_quality_rewritten=False, strategy_OI_semantics_changed=False,
        checked_input_fingerprints_count=len(inputs), all_current_input_fingerprints_match=True,
        input_payload_validation_scope='SHA freshness only for all manifest files; no repeated old-data/account audit',
        source_requalification_sha256=sha(SOURCE / 'requalification.json'), source_input_manifest_sha256=sha(SOURCE / 'input_manifest.json'),
        source_data_or_strategy_modified=False, cache_or_overlay_merge_authorized=False,
        C0_attempt3_authorized=False, full_candidate_coverage_proven=False,
        execution_fallback_authorized=False, production_qualified=False,
        network_connections=0, provider_replays=0, financial_replays=0,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1, C0_alpha_verdict='not_evaluable',
        overfitting=False, continued_value=True,
        next_boundary='This exact data may enter a separately reviewed append-only research supplement; require complete causal order-demand coverage before any candidate account replay.')
    (DEST / 'qualification_delta_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'qualification_fields', 'database_closeOI',
        'checked_input_fingerprints_count', 'qualified_research_data', 'C0_attempt3_authorized']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
