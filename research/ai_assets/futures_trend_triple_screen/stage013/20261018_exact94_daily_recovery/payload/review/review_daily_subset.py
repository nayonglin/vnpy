"""All 4500 qualified targets against frozen refs; four raw snapshots only."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import csv
import hashlib
import json
import math

LINE = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage013_missing_daily_recovery'
ATTEMPT = SOURCE / 'network_attempt1'
VALUES = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def integer(text):
    number = Decimal(text)
    assert number.is_finite() and number == number.to_integral_value()
    return int(number)


def local_ns(number):
    seconds, rest = divmod(number, 1_000_000_000)
    return (datetime.fromtimestamp(seconds, timezone.utc) + timedelta(microseconds=rest // 1000)).astimezone(timezone(timedelta(hours=8)))


def legal(row):
    try:
        values = {name: float(row[name]) for name in VALUES}
        if not all(math.isfinite(v) for v in values.values()):
            return False
        if min(values[n] for n in ['open', 'high', 'low', 'close']) <= 0:
            return False
        if min(values[n] for n in ['volume', 'open_oi', 'close_oi']) < 0:
            return False
        if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
            return False
        return True
    except (KeyError, ValueError, TypeError):
        return False


def main():
    preflight = json.loads((SOURCE / 'preflight.json').read_text())
    parent = json.loads((ATTEMPT / 'parent_receipt.json').read_text())
    worker = json.loads((ATTEMPT / 'worker_receipt.json').read_text())
    symbols = json.loads((ATTEMPT / 'symbol_receipts.json').read_text())
    assert parent['status'] == 'worker_terminal' and parent['exit_code'] == 1
    assert parent['all_inputs_unchanged'] and not parent['hard_kill']
    assert worker['status'] == 'completed_with_target_rejections'
    assert worker['collected_contracts'] == worker['target_contracts'] == 94
    assert worker['accepted_target_days'] == 4500 and worker['target_days'] == 4502
    assert parent['elapsed_seconds'] < 600 and worker['peak_memory_bytes'] < 1_500_000_000
    for value in (parent, worker):
        assert not value['automatic_retry'] and not value['production_qualified']
        for key in ['TqBacktest_instances', 'financial_replays', 'orders', 'cancels', 'broker_or_ctp_connections']:
            assert value[key] == 0
        assert not value['credential_values_saved'] and not value['old_CSV_or_DB_written']
    assert worker['provider_connections_attempted'] == 1 and worker['TqSim_created']
    assert sha(SOURCE / 'preflight.json') == parent['preflight_sha256']
    assert sha(SOURCE / 'target_manifest.csv') == preflight['target_manifest_sha256']
    assert sha(SOURCE / 'excluded_constraints.csv') == preflight['excluded_constraints_sha256']
    assert all(sha(path) == digest for path, digest in preflight['source_fingerprints'].items())
    # Bind small result artifacts. Raw fingerprints are checked for four samples below.
    for name, digest in parent['artifact_sha256'].items():
        if not name.startswith('raw/'):
            assert sha(ATTEMPT / name) == digest
    targets = read(SOURCE / 'target_manifest.csv')
    excluded = read(SOURCE / 'excluded_constraints.csv')
    qualified = read(ATTEMPT / 'qualified_daily.csv')
    audits = read(ATTEMPT / 'target_qualification.csv')
    def key(row):
        return row['vt_symbol'], row['trade_date']
    refs = {key(r): r for r in targets}
    rows = {key(r): r for r in qualified}
    checks = {key(r): r for r in audits}
    assert len(refs) == len(targets) == len(checks) == len(audits) == 4502
    assert len(rows) == len(qualified) == 4500 and set(rows).issubset(refs)
    assert len(excluded) == 16 and all(r['real_daily_present'] == 'False' for r in excluded)
    assert all(r['real_daily_present'] == 'True' for r in targets)
    assert len({r['vt_symbol'] for r in targets}) == len({r['vt_symbol'] for r in qualified}) == 94
    rejects = [r for r in audits if r['accepted'] == 'False']
    expected_rejects = {('fu2605.SHFE', '2026-04-30'), ('fu2609.SHFE', '2026-08-31')}
    assert set(refs) - set(rows) == {key(r) for r in rejects} == expected_rejects
    assert all(r['reason'] == 'no_forward_successor' and r['mismatch_fields'] == '' for r in rejects)
    assert set(rows) == {key(r) for r in audits if r['accepted'] == 'True'}
    max_diff = {name: 0.0 for name in ['open', 'high', 'low', 'close', 'volume', 'open_oi']}
    for k, row in rows.items():
        assert legal(row)
        native, exchange = row['vt_symbol'].rsplit('.', 1)
        assert row['tq_symbol'] == exchange + '.' + native
        ns = integer(row['source_datetime_ns'])
        successor_ns = integer(row['successor_datetime_ns'])
        identifier, successor_id = integer(row['source_bar_id']), integer(row['successor_id'])
        assert 0 <= identifier < successor_id and 0 < ns < successor_ns
        assert local_ns(ns).strftime('%Y-%m-%d') == row['trade_date']
        assert datetime.fromisoformat(row['datetime']) == local_ns(ns)
        assert datetime.fromisoformat(row['successor_time']) == local_ns(successor_ns)
        audit = checks[k]
        assert audit['reason'] == 'completed_and_six_fields_matched' and audit['mismatch_fields'] == ''
        assert audit['database_closeOI'] == 'N/A_not_independently_available'
        for name in ['source_bar_id', 'source_datetime_ns', 'successor_id', 'successor_datetime_ns']:
            assert integer(audit[name]) == integer(row[name])
        for name in max_diff:
            db_field = 'open_interest' if name == 'open_oi' else name
            actual, expected = float(row[name]), float(refs[k][db_field])
            difference = abs(actual - expected)
            assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-8)
            max_diff[name] = max(max_diff[name], difference)
    assert all(r['database_closeOI'] == 'N/A_not_independently_available' for r in audits)
    assert sum(r['requirement_kind'] == 'full_session' for r in targets) == 159
    assert sum(r['requirement_kind'] == 'anchor' for r in targets) == 4343

    # Only four raw snapshots: one old expiry, one active, and both retained rejections.
    symbol_map = {r['vt_symbol']: r for r in symbols}
    assert len(symbol_map) == len(symbols) == 94
    for info in symbols:
        raw_path = Path(info['raw_path'])
        assert info['raw_sha256'] == parent['artifact_sha256'][str(raw_path.relative_to(ATTEMPT))]
        assert info['accepted_days'] == sum(r['vt_symbol'] == info['vt_symbol'] for r in qualified)
    sample_keys = [('AP005.CZCE', '2020-01-10'),
                   max((k for k in rows if k[0] == 'AP701.CZCE'), key=lambda k: k[1]),
                   ('fu2605.SHFE', '2026-04-30'), ('fu2609.SHFE', '2026-08-31')]
    raw_checks = []
    raw_sample_paths = []
    for k in sample_keys:
        info = symbol_map[k[0]]
        path = Path(info['raw_path'])
        assert sha(path) == info['raw_sha256']
        raw_sample_paths.append(path)
        raw = read(path)
        valid = []
        for item in raw:
            if not legal(item):
                continue
            try:
                identifier, ns = integer(item['id']), integer(item['datetime'])
            except (AssertionError, ValueError):
                continue
            if identifier >= 0 and ns > 0:
                valid.append((identifier, ns, item))
        selected = [item for item in valid if local_ns(item[1]).strftime('%Y-%m-%d') == k[1]]
        assert len(selected) == 1
        identifier, ns, item = selected[0]
        later = [r for r in valid if r[0] > identifier and r[1] > ns]
        if k in rows:
            row = rows[k]
            assert identifier == integer(row['source_bar_id']) and ns == integer(row['source_datetime_ns'])
            assert all(float(item[n]) == float(row[n]) for n in VALUES)
            successor = [r for r in later if r[0] == integer(row['successor_id']) and r[1] == integer(row['successor_datetime_ns'])]
            assert len(successor) == 1 and legal(successor[0][2])
        else:
            assert not later
        raw_checks.append(dict(symbol=k[0], target_date=k[1], raw_file_rows=len(raw), valid_daily_rows=len(valid),
            source_id=identifier, source_ns=ns, source_local_time=local_ns(ns).isoformat(),
            has_forward_valid_successor=bool(later), accepted=k in rows,
            latest_valid_local_date=max(local_ns(r[1]).strftime('%Y-%m-%d') for r in valid),
            raw_sha256=info['raw_sha256']))

    paths = [SOURCE / 'preflight.json', SOURCE / 'target_manifest.csv', SOURCE / 'excluded_constraints.csv',
             ATTEMPT / 'qualified_daily.csv', ATTEMPT / 'target_qualification.csv', ATTEMPT / 'parent_receipt.json',
             ATTEMPT / 'worker_receipt.json', ATTEMPT / 'symbol_receipts.json', *raw_sample_paths]
    fingerprints = {str(path): sha(path) for path in paths}
    fingerprints.update(preflight['source_fingerprints'])
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_independent_review_pass_accept_only_4500_target_daily_rows', p0_findings=0, p1_findings=0,
        qualified_research_daily=True, qualified_rows=4500, target_rows=4502, contracts=94,
        unique_legal_target_subset=True, all_4500_completion_id_time_and_CST_checked=True,
        all_4500_fixed_DB_ref_six_fields_checked=True, six_fields_max_abs_difference=max_diff,
        independent_DB_queries=0, references='frozen preflight exact real DB targets; no repeated full DB audit',
        database_closeOI='N/A_not_independently_available', rejected_targets=rejects, excluded_carry_rows=16,
        raw_snapshot_files_independently_read=4, raw_snapshot_samples=raw_checks,
        all_94_raw_files_reparsed=False, all_94_declared_raw_SHA_bindings_to_parent_checked=True,
        provider_parent_status=parent['status'], provider_parent_exit_code=1,
        provider_worker_status=worker['status'], provider_all_targets_success=False,
        original_rejected_targets_preserved=True, all_frozen_inputs_current_SHA_match=True,
        provider_elapsed_seconds=parent['elapsed_seconds'], provider_peak_memory_bytes=worker['peak_memory_bytes'],
        network_connections_in_review=0, financial_replays=0, TqBacktest_instances=0, orders=0, cancels=0,
        original_CSV_or_DB_modified=False, raw_non_target_history_qualified=False,
        next_scope='Only these accepted rows may be used as daily refs in a separately reviewed Stage015 delta; retain2 rejects,16 carry constraints and3 older minute conflicts',
        C0_attempt3_authorized=False, execution_fallback_authorized=False, production_qualified=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1, C0_alpha_verdict='not_evaluable',
        source_fingerprints=fingerprints, overfitting=False, continued_value=True)
    (DEST / 'daily_subset_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'qualified_rows', 'excluded_carry_rows',
        'raw_snapshot_files_independently_read', 'provider_all_targets_success', 'six_fields_max_abs_difference']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
