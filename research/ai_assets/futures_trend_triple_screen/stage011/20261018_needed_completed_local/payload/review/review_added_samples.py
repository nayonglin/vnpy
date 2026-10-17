"""Eight session samples plus streaming new-key/A0 intersection; no engine."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import sys

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
DEST = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage011_needed_local_completed'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'
sys.path.insert(0, str(LINE / 'tools'))
import stage002_local_minute_overlay as accepted_helper

VALUES = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']
SAMPLES = [('AP101.CZCE', '2020-09-25'), ('SM403.CZCE', '2024-01-09'),
           ('rb2010.SHFE', '2020-08-12'), ('FG209.CZCE', '2022-05-27'),
           ('cu2010.SHFE', '2020-08-27'), ('cu2507.SHFE', '2025-06-11'),
           ('AP005.CZCE', '2020-01-10'), ('AP105.CZCE', '2021-03-25')]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def stamp(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo:
        dt = dt.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def close(a, b):
    return all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-8) for x, y in zip(a, b))


def main():
    summary = json.loads((SOURCE / 'summary.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    manifests = json.loads((SOURCE / 'source_manifest.json').read_text())
    sessions = read(SOURCE / 'session_manifest.csv')
    session_map = {(r['vt_symbol'], r['execution_trade_date']): r for r in sessions}
    assert len(session_map) == len(sessions) == 23309
    assert sum(r['status'] == 'accepted' for r in sessions) == 13752
    assert sum(r['reason'] == 'base_overlap_conflict' for r in sessions) == 3
    for name, digest in summary['artifact_sha256'].items():
        if name != 'overlay.csv':
            assert sha(SOURCE / name) == digest
    # Freeze the reviewed Stage010 demand, existing bytes and accepted Stage008 receipt.
    review010 = LINE / 'outputs/stage010_independent_review/review_receipt.json'
    assert sha(review010) == '58eef7e21536b372d3704eb012d0d7dba0118beccca4d0d920553ef9b73ebd32'
    review010_data = json.loads(review010.read_text())
    assert inputs[str(LINE / 'outputs/stage010_reachable_demand/summary.json')] == review010_data['source_summary_sha256']
    assert sha(accepted_helper.CACHE) == inputs[str(accepted_helper.CACHE)] == summary['base_sha256']
    overlay002 = LINE / 'outputs/stage002_local_minute_overlay/attempt2/overlay.csv'
    assert sha(overlay002) == inputs[str(overlay002)] == summary['stage002_overlay_sha256']
    for path in [LINE / 'tools/stage011_needed_local_completed.py', LINE / 'stages/20261018_0005_stage011_needed_local_completed_protocol.md',
                 LINE / 'outputs/stage008_independent_review/review_receipt.json']:
        assert sha(path) == inputs[str(path)]
    declared_path = next(Path(path) for path in inputs if path.endswith('/stage251_half_r_ab/A_final3/input_manifest.json'))
    declared = json.loads(declared_path.read_text())
    assert sha(declared_path) == inputs[str(declared_path)]
    source_map = {r['source_id']: r for r in manifests['sources']}
    assert len(source_map) == 906
    for source in source_map.values():
        assert source['status'] == 'accepted_source_bytes' and source['sha256'] == source['expected_sha256']
        assert inputs[source['path']] == source['sha256']
        if source['source_id'] != 'stage008_accepted_345':
            assert declared[str(Path(source['path']).relative_to(ROOT))] == source['sha256']
    mapping = read(accepted_helper.MAPPING)
    calendar = accepted_helper.pd.DatetimeIndex(sorted({r['date'] for r in mapping}))
    grids = {key: [stamp(x) for x in accepted_helper.session_grid(*key, calendar)] for key in SAMPLES}
    by_symbol_times = {}
    for (symbol, _), grid in grids.items():
        by_symbol_times.setdefault(symbol, set()).update(grid)

    # Only re-create the accepted A0 identity read-set, never its economics/account.
    anchors = read(A0 / 'execution_anchor_requests.csv')
    scans = read(A0 / 'minute_scan_requests.csv')
    used = {(r['vt_symbol'], stamp(r['expected_start'])) for r in anchors}
    for r in scans:
        grid = accepted_helper.session_grid(r['vt_symbol'], r['trading_date'], calendar)
        requested = [stamp(x) for x in grid if stamp(x) >= stamp(r['requested_start'])]
        assert len(requested) == int(r['expected_bar_count'])
        used.update((r['vt_symbol'], x) for x in requested)
    assert len(used) == 106731 and len(anchors) == 535 and len(scans) == 501
    new_samples = {}
    digest = hashlib.sha256()
    previous = None
    count = 0
    intersections = []
    with (SOURCE / 'overlay.csv').open('rb') as f:
        def lines():
            for block in f:
                digest.update(block)
                yield block.decode('utf-8-sig')
        reader = csv.reader(lines())
        header = next(reader)
        assert header == ['vt_symbol', 'bar_datetime', *VALUES, 'source_ids', 'trading_date']
        for row in reader:
            key = row[0], row[1]
            assert previous is None or key > previous
            previous = key
            count += 1
            if key in used:
                intersections.append(key)
            if key[1] in by_symbol_times.get(key[0], set()):
                new_samples[key] = dict(values=[float(x) for x in row[2:9]], source_ids=row[9], trading_date=row[10])
    assert count == 4646214 and not intersections
    assert digest.hexdigest() == summary['artifact_sha256']['overlay.csv']

    # Extract a few old-symbol rows, then restrict to eight target grids.
    existing = {}
    pattern = '^(' + '|'.join(re.escape(s) for s in by_symbol_times) + '),'
    for path in [accepted_helper.CACHE, overlay002]:
        header = next(csv.reader(Path(path).open(encoding='utf-8-sig')))
        result = subprocess.run(['rg', '-e', pattern, str(path)], capture_output=True, text=True)
        assert result.returncode in (0, 1)
        for row in csv.DictReader(io.StringIO(result.stdout), fieldnames=header):
            key = row['vt_symbol'], stamp(row['bar_datetime'])
            if key[1] in by_symbol_times.get(key[0], set()):
                assert key not in existing
                existing[key] = [float(row[field]) for field in VALUES]
    assert not set(new_samples).intersection(existing)

    sample_checks = []
    actual_source_bytes_checked = set()
    for symbol, day in SAMPLES:
        audit = session_map[symbol, day]
        grid = grids[symbol, day]
        source_ids = json.loads(audit['source_ids'])
        merged = {}
        cross_source_duplicate_keys = 0
        for source_id in source_ids:
            source = source_map[source_id]
            path = Path(source['path'])
            if str(path) not in actual_source_bytes_checked:
                assert sha(path) == source['sha256']
                actual_source_bytes_checked.add(str(path))
            for row in read(path):
                moment = stamp(row['bar_datetime'])
                if moment not in grid:
                    continue
                values = [float(row[field]) for field in VALUES]
                if moment in merged:
                    assert close(values, merged[moment])
                    cross_source_duplicate_keys += 1
                else:
                    merged[moment] = values
        old = {t: existing[symbol, t] for t in grid if (symbol, t) in existing}
        additions = {t: new_samples[symbol, t] for t in grid if (symbol, t) in new_samples}
        conflicts = [t for t in set(merged).intersection(old) if not close(merged[t], old[t])]
        if audit['reason'] == 'base_overlap_conflict':
            assert conflicts and not additions
            sample_checks.append(dict(symbol=symbol, date=day, result='base_conflict_preserved_whole_session_rejected',
                mismatched_existing_keys=len(conflicts), new_minutes=0))
            continue
        if audit['reason'] == 'required_daily_csv_seven_fields_missing':
            assert not Path(audit['daily_source_path']).exists() and not additions
            sample_checks.append(dict(symbol=symbol, date=day, result='missing_daily_CSV_rejected', new_minutes=0))
            continue
        assert not conflicts
        combined = {**merged, **old}
        if audit['reason'] == 'incomplete_session':
            assert len(set(grid) - set(combined)) == 1 and not additions
            sample_checks.append(dict(symbol=symbol, date=day, result='anchor_request_still_rejects_incomplete_session',
                candidate_anchor_present=grid[0] in combined, observed=len(combined), expected=len(grid), new_minutes=0))
            continue
        assert audit['status'] == 'accepted' and set(combined) == set(grid)
        assert set(additions) == set(grid) - set(old)
        for t, row in additions.items():
            assert close(row['values'], merged[t]) and row['trading_date'] == day
        ordered = [combined[t] for t in grid]
        aggregate = dict(zip(VALUES, [ordered[0][0], max(v[1] for v in ordered), min(v[2] for v in ordered),
            ordered[-1][3], math.fsum(v[4] for v in ordered), ordered[0][5], ordered[-1][6]]))
        assert aggregate == json.loads(audit['aggregate'])
        daily_path = Path(audit['daily_source_path'])
        assert sha(daily_path) == inputs[str(daily_path)]
        daily = [r for r in read(daily_path) if r['trade_date'] == day]
        assert len(daily) == 1 and all(math.isclose(aggregate[k], float(daily[0][k]), rel_tol=1e-12, abs_tol=1e-8) for k in VALUES)
        sample_checks.append(dict(symbol=symbol, date=day, result='complete_session_and_seven_CSV_fields_match',
            old_minutes=len(old), new_minutes=len(additions), expected=len(grid), source_ids=source_ids,
            consistent_cross_source_duplicate_keys=cross_source_duplicate_keys))

    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_new_data_sample_and_full_new_key_A0_disjointness_review_pass', p0_findings=0, p1_findings=0,
        financial_replays=0, network_calls=0, old_account_or_indicator_streams_repeated=False,
        full_added_price_qualification_repeated=False, full_new_key_stream_rows=count,
        new_overlay_SHA256=digest.hexdigest(), new_keys_strictly_sorted_unique=True,
        A0_actual_read_keys=106731, added_intersection_A0_reads=0,
        base_and_Stage002_bytes_current_SHA_unchanged=True, sampled_new_old_key_overlap=0,
        source_manifest_binding_rows=906, independently_rehashed_sample_source_files=len(actual_source_bytes_checked),
        independent_session_samples=sample_checks, completion_basis='inherited frozen completed-source declarations; Stage008 keeps independent provider successor qualification',
        qualified_added_rows=4646214, qualified_added_contracts=349,
        accepted_sessions=13752, quarantined_sessions=9557, remaining_full_sessions=215,
        remaining_anchors=9342, unresolved_no_real_fill_constraints=16,
        source_summary_sha256=sha(SOURCE / 'summary.json'), source_input_manifest_sha256=sha(SOURCE / 'input_manifest.json'),
        qualification_confidence='static append-only gate plus eight real source/session samples; not independent aggregate recomputation of all13752 accepted sessions',
        A0_replay_reuse_valid_for_this_append_only_data_change=True, old_source_values_overwrite_authorized=False,
        execution_fallback_authorized=False, C0_attempt3_authorized=False, full_candidate_feasibility_proven=False,
        production_qualified=False, financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict='not_evaluable', overfitting=False, continued_value=True)
    (DEST / 'added_sample_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'full_new_key_stream_rows', 'added_intersection_A0_reads',
        'independently_rehashed_sample_source_files', 'unresolved_no_real_fill_constraints']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
