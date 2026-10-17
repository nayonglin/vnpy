"""Small independent Stage004 semantic/count sentinels; no account or bulk QA."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
SOURCE = LINE / 'outputs/stage004_minute_coverage'
DEST = Path(__file__).resolve().parent
CODE = LINE / 'tools/stage004_minute_coverage.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    summary = json.loads((SOURCE / 'summary.json').read_text())
    assert summary['financial_attempts'] == 0 and summary['potential_signal_set_is_exact'] is False
    assert summary['production_qualified'] is False
    assert sha(CODE) == summary['source_code_sha256']
    selected_artifacts = ['known_failure_session_coverage.csv', 'gap_examples.csv',
        'local_source_candidates.csv', 'requirement_set_summary.csv', 'input_manifest.json']
    for name in selected_artifacts:
        assert sha(SOURCE / name) == summary['artifact_sha256'][name]
    known = pd.read_csv(SOURCE / 'known_failure_session_coverage.csv')
    examples = pd.read_csv(SOURCE / 'gap_examples.csv')
    chosen = [known]
    for role, real in [('current_main', True), ('adjacent_previous_main', True),
        ('adjacent_previous_main', False), ('earlier_prior_main', False),
        ('metadata_real_only', True), ('earlier_prior_main', True)]:
        row = examples.loc[examples.mapping_role.eq(role) & examples.real_daily_present.eq(real)].head(1)
        assert len(row) == 1
        chosen.append(row)
    sample = pd.concat(chosen, ignore_index=True).drop_duplicates(['vt_symbol', 'date'])
    mapping_path = ROOT / 'examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
    mapping = pd.read_csv(mapping_path, usecols=['date', 'continuous_symbol_vt', 'main_contract_vt']).fillna('')
    mapping['date'] = pd.to_datetime(mapping.date)
    calendar = pd.DatetimeIndex(sorted(mapping.date.unique()))
    def independent_grid(product, day):
        date = pd.Timestamp(day)
        code = product.split('.')[0]
        parts = [pd.date_range(date + pd.Timedelta(minutes=start), periods=count, freq='min')
            for start, count in [(540, 75), (630, 60), (810, 90)]]
        if code not in {'AP', 'SM', 'si', 'lc', 'lh'}:
            pos = calendar.get_indexer([date])[0]
            before = calendar[pos - 1]
            gap = (date - before).days
            active = gap == 1 or (before.weekday() == 4 and date.weekday() == 0 and gap == 3)
            active = active and not (pd.Timestamp('2020-02-03') <= before < pd.Timestamp('2020-05-06'))
            if active:
                count = 330 if code == 'au' else 240 if code == 'cu' else 120
                parts.insert(0, pd.date_range(before + pd.Timedelta(hours=21), periods=count, freq='min'))
        return list(pd.DatetimeIndex(np.concatenate([p.values for p in parts])).sort_values())
    expected = {(r.vt_symbol, r.date): independent_grid(r.product_vt_symbol, r.date) for r in sample.itertuples()}
    natural_dates = sorted({stamp.strftime('%Y-%m-%d') for grid in expected.values() for stamp in grid})
    symbols = sorted(sample.vt_symbol.unique())
    pattern = '^(' + '|'.join(re.escape(s) for s in symbols) + '),[^,]+,(' + '|'.join(natural_dates) + ')'
    actual = set()
    exact_matched_lines = {}
    for name, path in [('base', ROOT / 'examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'),
        ('overlay', LINE / 'outputs/stage002_local_minute_overlay/attempt2/overlay.csv')]:
        result = subprocess.run(['rg', pattern, str(path)], capture_output=True, text=True, check=False)
        assert result.returncode in (0, 1)
        rows = list(csv.reader(io.StringIO(result.stdout)))
        exact_matched_lines[name] = len(rows)
        for row in rows:
            key = (row[0], pd.Timestamp(row[2]))
            assert key not in actual
            actual.add(key)
    records = []
    database = ROOT / '.vntrader/database.db'
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        for row in sample.itertuples(index=False):
            grid = expected[(row.vt_symbol, row.date)]
            present = [stamp for stamp in grid if (row.vt_symbol, stamp) in actual]
            observed = len(present)
            assert row.expected_minutes == len(grid)
            assert row.available_minutes == observed
            assert row.missing_minutes == len(grid) - observed
            assert bool(row.anchor_present) == ((row.vt_symbol, grid[0]) in actual)
            assert bool(row.complete) == (observed == len(grid))
            native, exchange = row.vt_symbol.rsplit('.', 1)
            n = db.execute("SELECT COUNT(*) FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=?", [native, exchange, row.date]).fetchone()[0]
            assert n in (0, 1)
            real = n == 1
            assert bool(row.real_daily_present) == real
            assert bool(row.real_data_gap) == (real and observed < len(grid))
            history = mapping.loc[mapping.continuous_symbol_vt.eq(row.product_vt_symbol) &
                mapping.date.between('2020-01-01', row.date) & mapping.main_contract_vt.ne('')].sort_values('date')
            current, prior = '', ''
            main_today = False
            previous_today = False
            ever = False
            for item in history.itertuples(index=False):
                if item.main_contract_vt != current:
                    prior, current = current, item.main_contract_vt
                ever |= item.main_contract_vt == row.vt_symbol
                if item.date == pd.Timestamp(row.date):
                    main_today = current == row.vt_symbol
                    previous_today = prior == row.vt_symbol
            role = 'current_main' if main_today else 'adjacent_previous_main' if previous_today else 'earlier_prior_main' if ever else 'metadata_real_only'
            assert bool(row.main_only) == main_today
            assert bool(row.main_plus_previous) == (main_today or previous_today)
            assert bool(row.ever_main_upper) == ever
            assert row.mapping_role == role
            assert bool(row.carry_risk) == (ever and not real)
            records.append(dict(symbol=row.vt_symbol, date=row.date, role=role, real_daily_present=real,
                carry_risk=bool(row.carry_risk), expected=len(grid), brute_available=observed,
                missing=len(grid)-observed, anchor_present=bool(row.anchor_present),
                real_data_gap=bool(row.real_data_gap), classification_and_count_match=True))
    # One independently assembled gapped night/day grid, without repeating the
    # implementation agent's test suite or full coverage batch.
    spec = importlib.util.spec_from_file_location('coverage_review_target', CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    day_grid = independent_grid('rb.SHFE', '2020-05-18')
    values = np.array(day_grid, dtype='datetime64[ns]').astype('int64')
    removed = {0, 37, len(values)-1}
    available = np.sort(np.r_[values[[i for i in range(len(values)) if i not in removed]], values[0]-60_000_000_000, values[-1]+60_000_000_000])
    brute = sum(int(value) in set(map(int, available)) for value in values)
    vector = module.coverage_counts(available, values)
    assert brute == vector['available_minutes'] == 342
    assert vector['missing_minutes'] == 3 and vector['anchor_present'] is False and vector['complete'] is False
    inventory = pd.read_csv(SOURCE / 'local_source_candidates.csv').fillna('')
    assert inventory.measured_sha256.eq('').all()
    assert inventory.auto_accepted.eq(False).all() and inventory.covered_dates_verified.eq(False).all()
    assert inventory.sha_status.isin(['manifest_declaration_only_not_rehashed', 'not_declared_not_rehashed']).all()
    totals = pd.read_csv(SOURCE / 'requirement_set_summary.csv')
    assert (totals.expected_minutes - totals.available_minutes).eq(totals.missing_minutes).all()
    assert (totals.sessions - totals.anchor_present).eq(totals.missing_anchor_sessions).all()
    report = dict(reviewed_at=datetime.now().astimezone().isoformat(timespec='seconds'),
        status='limited_semantic_and_small_enumeration_checks_pass', production_qualified=False,
        financial_replays=0, old_account_recalculations=0, weekly_recalculations=0,
        full_coverage_batch_repeated=False, full_session_gzip_reenumerated=False,
        summary_sha256=sha(SOURCE/'summary.json'), implementation_sha256=sha(CODE),
        selected_artifact_fingerprints_checked=selected_artifacts,
        sampled_sessions=records, targeted_minute_lines_examined=exact_matched_lines,
        vectorized_sparse_night_day_probe=vector, local_source_inventory_rows=len(inventory),
        inventory_measured_checksums_empty=True, inventory_never_auto_accepted=True,
        assertions='current/prior/main-derived bounds conditional; no-real carry rows are diagnostic only; requirement sets overlap and cannot be summed as disjoint demands',
        confidence_limit='8 session sentinels plus one sparse-grid probe and static/source semantics; not an independent enumeration of all 452069 coverage rows or price requalification')
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST/'sample_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
