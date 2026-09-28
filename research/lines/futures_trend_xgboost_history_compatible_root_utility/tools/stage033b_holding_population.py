from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/stage033_holding_observer'
OUTPUT = ROOT / 'artifacts/stage033b_holding_population'
CONTRACT = ROOT / 'stages/20260906_0819_stage033b_holding_population_contract.md'
MIN_ROOTS = 60


def group_roots(rows, events):
    roots = events.copy().fillna('')
    if roots.event_id.eq('').any() or roots.event_id.duplicated().any():
        raise RuntimeError('holding_root_identity_invalid')
    allowed = {'mature', 'mature_cancelled_unfilled', 'right_censored_open', 'right_censored_pending_entry'}
    if not roots.status.isin(allowed).all() or not roots.direction.isin(['long', 'short']).all():
        raise RuntimeError('holding_root_status_invalid')
    for root in roots.itertuples():
        if root.status in {'mature', 'right_censored_open'}:
            if not root.first_fill_date or root.first_fill_date <= root.decision_date:
                raise RuntimeError('holding_root_fill_time_invalid')
        if root.status == 'mature' and (not root.end_date or root.end_date < root.first_fill_date):
            raise RuntimeError('holding_root_end_time_invalid')
    linked, seen = [], set()
    records = roots.to_dict('records')
    for row in rows:
        if row['product_vt_symbol'] == 'fu.SHFE' or not row['actual_positions']:
            continue
        day, product = row['date'], row['product_vt_symbol']
        if (day, product) in seen:
            raise RuntimeError('holding_duplicate_product_day')
        seen.add((day, product))
        matches = [root for root in records if root['product_vt_symbol'] == product
            and root['first_fill_date'] and root['first_fill_date'] <= day
            and (root['status'] == 'right_censored_open'
                 or (root['status'] == 'mature' and day < root['end_date']))]
        if len(matches) != 1:
            raise RuntimeError(f'holding_root_assignment_invalid:{day}:{product}:{len(matches)}')
        root = matches[0]
        if row['state_status'] == 'stable_holding':
            sign = 1 if root['direction'] == 'long' else -1
            if any(value * sign <= 0 for value in row['actual_positions'].values()):
                raise RuntimeError('holding_root_direction_changed')
        linked.append({'date': day, 'product_vt_symbol': product, 'event_id': root['event_id'],
            'state_status': row['state_status'], 'actual_contract_count': len(row['actual_positions'])})
    linked = pd.DataFrame(linked, columns=['date','product_vt_symbol','event_id','state_status','actual_contract_count'])
    stable = linked[linked.state_status.eq('stable_holding')]
    roots['actual_holding_days'] = roots.event_id.map(linked.groupby('event_id').size()).fillna(0).astype(int)
    roots['stable_observation_days'] = roots.event_id.map(stable.groupby('event_id').size()).fillna(0).astype(int)
    roots['first_stable_date'] = roots.event_id.map(stable.groupby('event_id').date.min()).fillna('')
    roots['last_stable_date'] = roots.event_id.map(stable.groupby('event_id').date.max()).fillna('')
    return linked, roots


def monthly_population(roots, cutoffs):
    rows = []
    for cutoff in cutoffs:
        selected = roots[roots.status.eq('mature') & roots.stable_observation_days.gt(0)
            & roots.end_date.lt(cutoff) & roots.decision_date.lt(cutoff)]
        rows.append({'cutoff': cutoff, 'eligible_independent_roots': len(selected),
            'eligible_observation_days': int(selected.stable_observation_days.sum()),
            'minimum_roots_met': len(selected) >= MIN_ROOTS})
    return pd.DataFrame(rows)


def load_observer():
    spec = importlib.util.spec_from_file_location('population_observer033', ROOT / 'tools/stage033_holding_observer.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    if OUTPUT.exists():
        raise RuntimeError('holding_population_already_exists')
    observer = load_observer()
    base, runner = observer.configured()
    batch = observer.load('stage004_label_batch')
    manifest = json.loads((SOURCE / 'input_manifest.json').read_text())
    runner.validate_current_input_manifest(manifest)
    runner.validate_frozen_input_contract(observer.FREEZE, manifest)
    summary = json.loads((SOURCE / 'summary.json').read_text())
    root = SOURCE / 'workers/A'
    receipt = json.loads((root / 'observer_receipt.json').read_text())
    if (summary['status'] != 'observation_qualified_not_model' or not summary['all_seven_frames_exact']
            or summary['file_contract_sha256'] != manifest['file_contract_sha256']
            or batch.digest(root / 'receipt.json') != summary['worker_receipt_sha256']
            or runner._file_identity(root / 'observer_receipt.json') != summary['observer_receipt_identity']):
        raise RuntimeError('holding_observer_receipt_changed')
    trace = root / 'holding_states.json.gz'
    if runner._file_identity(trace) != receipt['trace_identity'] or receipt['trace_identity'] != summary['trace_identity']:
        raise RuntimeError('holding_trace_identity_changed')
    raw = gzip.decompress(trace.read_bytes())
    if hashlib.sha256(raw).hexdigest() != receipt['raw_sha256']:
        raise RuntimeError('holding_raw_trace_changed')
    rows = json.loads(raw)
    collector = observer.load('stage005_label_collection')
    archives = json.loads((root / 'archive_receipt.json').read_text())
    for name, item in archives.items():
        collector.verify_archive(root / f'{name}.csv.gz', item)
    daily = pd.read_csv(root / 'daily.csv.gz', float_precision='round_trip')
    positions = pd.read_csv(root / 'positions.csv.gz', float_precision='round_trip')
    if observer.qualify_trace(rows, daily, positions) != summary['qualification']:
        raise RuntimeError('holding_observation_qualification_changed')
    lifecycle = ROOT / 'artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv'
    paths = [Path(__file__).resolve(), ROOT / 'tests/test_stage033b_holding_population.py', CONTRACT,
        SOURCE / 'summary.json', SOURCE / 'input_manifest.json', observer.FREEZE, lifecycle,
        root / 'observer_receipt.json', root / 'receipt.json', root / 'archive_receipt.json', trace]
    identities = {str(path): runner._file_identity(path) for path in paths}
    events = pd.read_csv(lifecycle, dtype=str, keep_default_na=False)
    linked, roots = group_roots(rows, events)
    cutoffs = [str(month.date()) for month in pd.date_range(daily.date.iloc[0][:7] + '-01', daily.date.iloc[-1], freq='MS')]
    months = monthly_population(roots, cutoffs)
    headroom = batch.load('holding_headroom', batch.V4 / 'tools/stage007_objective_headroom_audit.py')
    eligible = roots[roots.stable_observation_days.gt(0)]
    geometry = headroom.objective_headroom(daily, eligible, MIN_ROOTS)
    runner.validate_current_input_manifest(manifest)
    if any(runner._file_identity(Path(path)) != identity for path, identity in identities.items()):
        raise RuntimeError('holding_population_source_drift')
    OUTPUT.mkdir(mode=0o700)
    outputs = {}
    for name, frame in [('linked_holding_days', linked), ('root_population', roots), ('monthly_population', months)]:
        path = OUTPUT / f'{name}.csv'
        runner._write_bytes_exclusive(path, frame.to_csv(index=False).encode())
        outputs[name] = runner._file_identity(path)
    result = {'stage': 'stage033b_holding_population', 'status': 'population_qualified_not_execution_or_model',
        'root_count': len(roots), 'actual_holding_days': len(linked),
        'stable_holding_days': int(roots.stable_observation_days.sum()),
        'roots_with_stable_observations': int(roots.stable_observation_days.gt(0).sum()),
        'mature_roots_with_stable_observations': int((roots.status.eq('mature') & roots.stable_observation_days.gt(0)).sum()),
        'root_status_counts': roots.status.value_counts().to_dict(), **geometry,
        'source_identities': identities, 'outputs': outputs, 'new_replay_count': 0, 'new_label_count': 0,
        'historical_fit_predict_count': 0, 'reviewer_started': False}
    batch.write_json(OUTPUT / 'summary.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in {'source_identities', 'outputs'}}), flush=True)


if __name__ == '__main__':
    main()
