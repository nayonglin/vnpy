"""Stage015 bounded scope/readiness, four session samples, new-key stream."""
from pathlib import Path
from datetime import datetime
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import sys

LINE = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
ROOT = LINE.parents[2]
SOURCE = LINE / 'outputs/stage015_daily_recovered_minute_delta'
S011 = LINE / 'outputs/stage011_needed_local_completed'
S012 = LINE / 'outputs/stage012_provider_batch'
S013 = LINE / 'outputs/stage013_missing_daily_recovery'
sys.path.insert(0, str(LINE / 'tools'))
import stage002_local_minute_overlay as h
VALUES = h.VALUES
SAMPLES = [('AP005.CZCE', '2020-01-10'), ('AP005.CZCE', '2020-01-23'),
           ('SH605.CZCE', '2026-03-05'), ('rb2010.SHFE', '2020-04-01')]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(b)
    return digest.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def stamp(value):
    return h.local_timestamp(value).strftime('%Y-%m-%d %H:%M:%S')


def equal(a, b):
    return all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-8) for x, y in zip(a, b))


def main():
    summary = json.loads((SOURCE / 'summary.json').read_text())
    inputs = json.loads((SOURCE / 'input_manifest.json').read_text())
    assert all(sha(path) == digest for path, digest in inputs.items())
    for name, digest in summary['artifact_sha256'].items():
        if name != 'overlay.csv':
            assert sha(SOURCE / name) == digest
    daily_review = LINE / 'outputs/stage013_independent_review/review_receipt.json'
    assert sha(daily_review) == '194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
    accepted_daily = {(r['vt_symbol'], r['trade_date']): r for r in read(S013 / 'network_attempt1/qualified_daily.csv')}
    assert len(accepted_daily) == 4500
    refs = dict(accepted_daily)
    batch012 = json.loads((S012 / 'batch_manifest.json').read_text())
    for target in batch012['targets']:
        day = target['execution_trade_date']
        rows = [r for r in read(target['daily_csv_path']) if r['trade_date'] == day]
        assert len(rows) == 1
        refs[target['vt_symbol'], day] = rows[0]
    sessions = read(SOURCE / 'session_manifest.csv')
    bykey = {(r['vt_symbol'], r['execution_trade_date']): r for r in sessions}
    assert len(refs) == len(sessions) == len(bykey) == 4511 and set(bykey) == set(refs)
    rejected013 = {('fu2605.SHFE', '2026-04-30'), ('fu2609.SHFE', '2026-08-31')}
    assert not set(bykey).intersection(rejected013)
    forbidden = {(r['vt_symbol'], r['execution_trade_date']) for r in read(S011 / 'quarantine.csv') if r['reason'] == 'base_overlap_conflict'}
    assert len(forbidden) == 3 and not set(bykey).intersection(forbidden)
    assert sum(r['status'] == 'accepted' for r in sessions) == 1480
    assert sum(r['reason'] == 'incomplete_session' for r in sessions) == 3031

    pd = h.pd
    previous = pd.read_csv(S011 / 'demand_readiness.csv').set_index(['vt_symbol', 'execution_trade_date'])
    final = pd.read_csv(SOURCE / 'demand_readiness.csv').set_index(['vt_symbol', 'execution_trade_date'])
    assert previous.index.is_unique and final.index.is_unique and set(previous.index) == set(final.index)
    assert set(final.loc[final.stage015_checked].index) == set(bykey)
    outside = sorted(set(previous.index) - set(bykey))
    assert len(outside) == 23757
    pd.testing.assert_frame_equal(previous.loc[outside], final.loc[outside, previous.columns], check_dtype=False)
    assert not previous.loc[list(bykey), 'ready_after'].any()
    assert previous.ready_after.sum() == 18711 and final.ready_after.sum() == 20191
    assert (~final.ready_after).sum() == 8077
    assert sum(~final.ready_after & final.requirement_kind.eq('full_session')) == 135
    assert sum(~final.ready_after & final.requirement_kind.eq('anchor')) == 7942
    carry = final.index[~final.real_daily_present]
    assert len(carry) == 16 and not set(carry).intersection(bykey) and not final.loc[carry, 'ready_after'].any()
    assert not final.loc[list(forbidden | rejected013), 'stage015_checked'].any()

    calendar = pd.DatetimeIndex(sorted({r['date'] for r in read(h.MAPPING)}))
    grids = {key: [stamp(x) for x in h.session_grid(*key, calendar)] for key in SAMPLES}
    wanted = {}
    for (symbol, _), grid in grids.items():
        wanted.setdefault(symbol, set()).update(grid)
    anchors = read(h.A0 / 'execution_anchor_requests.csv')
    scans = read(h.A0 / 'minute_scan_requests.csv')
    used = {(r['vt_symbol'], stamp(r['expected_start'])) for r in anchors}
    for r in scans:
        grid = h.session_grid(r['vt_symbol'], r['trading_date'], calendar)
        keys = [(r['vt_symbol'], stamp(t)) for t in grid if h.local_timestamp(t) >= h.local_timestamp(r['requested_start'])]
        assert len(keys) == int(r['expected_bar_count'])
        used.update(keys)
    assert len(used) == 106731
    new_sample = {}
    digest = hashlib.sha256()
    count = 0
    last = None
    with (SOURCE / 'overlay.csv').open('rb') as f:
        def lines():
            for b in f:
                digest.update(b)
                yield b.decode('utf-8-sig')
        reader = csv.reader(lines())
        assert next(reader) == ['vt_symbol', 'bar_datetime', *VALUES, 'source_ids', 'trading_date']
        for row in reader:
            key = row[0], row[1]
            assert key not in used and (last is None or key > last)
            last = key
            count += 1
            if key[1] in wanted.get(key[0], set()):
                new_sample[key] = [float(x) for x in row[2:9]]
    assert count == 452401 and digest.hexdigest() == summary['artifact_sha256']['overlay.csv']

    # Old values for the four exact grids only; no old prices are recomputed globally.
    existing = {}
    pattern = '^(' + '|'.join(re.escape(s) for s in wanted) + '),'
    existing_paths = [h.CACHE, LINE / 'outputs/stage002_local_minute_overlay/attempt2/overlay.csv', S011 / 'overlay.csv']
    for path in existing_paths:
        header = next(csv.reader(path.open(encoding='utf-8-sig')))
        output = subprocess.run(['rg', '-e', pattern, str(path)], capture_output=True, text=True)
        assert output.returncode in (0, 1)
        for row in csv.DictReader(io.StringIO(output.stdout), fieldnames=header):
            key = row['vt_symbol'], stamp(row['bar_datetime'])
            if key[1] in wanted.get(key[0], set()):
                assert key not in existing
                existing[key] = [float(row[n]) for n in VALUES]
    assert not set(existing).intersection(new_sample)
    source_info = json.loads((SOURCE / 'source_manifest.json').read_text())
    source_map = {r['source_id']: r for r in source_info['completed_sources']}
    source_files = set()
    sample_results = []
    for symbol, day in SAMPLES:
        row = bykey[symbol, day]
        grid = grids[symbol, day]
        merged = {}
        duplicates = 0
        ids = json.loads(row['source_ids'])
        for source_id in ids:
            if source_id == 'stage012_reviewed_provider':
                path = S012 / 'network_attempt1/raw_completed_minutes.csv'
                assert sha(path) == inputs[str(path)]
            else:
                info = source_map[source_id]
                path = Path(info['path'])
                assert sha(path) == info['sha256'] == inputs[str(path)]
            source_files.add(str(path))
            for source in read(path):
                moment = stamp(source['bar_datetime'])
                if source['vt_symbol'] != symbol or moment not in grid:
                    continue
                values = [float(source[n]) for n in VALUES]
                if moment in merged:
                    assert equal(values, merged[moment])
                    duplicates += 1
                else:
                    merged[moment] = values
        old = {t: existing[symbol, t] for t in grid if (symbol, t) in existing}
        added = {t: new_sample[symbol, t] for t in grid if (symbol, t) in new_sample}
        assert all(equal(old[t], merged[t]) for t in set(old).intersection(merged))
        combined = {**merged, **old}
        if row['status'] != 'accepted':
            assert row['reason'] == 'incomplete_session' and len(combined) == 224 and len(grid) == 225 and not added
            sample_results.append(dict(symbol=symbol, day=day, accepted=False, complete_rows=224, expected=225, new_rows=0))
            continue
        assert set(combined) == set(grid) and set(added) == set(grid) - set(old)
        assert all(equal(values, merged[t]) for t, values in added.items())
        ordered = [combined[t] for t in grid]
        aggregate = dict(zip(VALUES, [ordered[0][0], max(v[1] for v in ordered), min(v[2] for v in ordered),
            ordered[-1][3], math.fsum(v[4] for v in ordered), ordered[0][5], ordered[-1][6]]))
        assert aggregate == json.loads(row['aggregate'])
        assert all(math.isclose(value, float(refs[symbol, day][field]), rel_tol=1e-12, abs_tol=1e-8) for field, value in aggregate.items())
        sample_results.append(dict(symbol=symbol, day=day, accepted=True, old_rows=len(old), new_rows=len(added),
            expected=len(grid), matched_seven_daily_fields=True, consistent_duplicate_source_keys=duplicates,
            daily_reference='reviewed_Stage013_target' if (symbol, day) in accepted_daily else 'reviewed_Stage012_original_CSV'))
    result = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_incremental_scope_samples_readiness_and_A0_key_review_pass', p0_findings=0, p1_findings=0,
        qualified_research_overlay=True, delta_scope_exact_4500_daily_plus_11_provider=True,
        rejected_013_targets_waived=False, no_real_16_constraints_waived=False, original_3_conflicts_waived=False,
        current_input_fingerprints_checked=len(inputs), untouched_readiness_common_rows_same=23757,
        original_13752_sessions_requalified=0, added_keys_unique_sorted=count,
        new_overlay_sha256=digest.hexdigest(), A0_actual_read_keys=106731, added_intersection_A0_reads=0,
        sampled_existing_key_overlap=0, four_session_samples=sample_results, sampled_source_files=len(source_files),
        all_delta_session_prices_independently_reaggregated=False,
        ready_before=18711, inherited_ready_after=20191, remaining_requirements=8077, remaining_full=135, remaining_anchor=7942,
        inherited_859_ready_truth_requalified=False,
        old_readiness_scope='unchanged timestamp coverage inherited; separately identified source859 ready issues remain outside this delta verdict',
        source_summary_sha256=sha(SOURCE / 'summary.json'), source_input_manifest_sha256=sha(SOURCE / 'input_manifest.json'),
        financial_replays=0, network_calls=0, full_candidate_feasibility_proven=False,
        C0_attempt3_authorized=False, execution_fallback_authorized=False, production_qualified=False,
        financial_attempts_cumulative_unchanged=4, financial_completed_cumulative_unchanged=1, C0_alpha_verdict='not_evaluable',
        overfitting=False, continued_value=True)
    (DEST / 'delta_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'added_keys_unique_sorted', 'added_intersection_A0_reads',
        'untouched_readiness_common_rows_same', 'current_input_fingerprints_checked']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
