"""Merge validated research minute days; retain the original cache and evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from stage246_download_entry_minutes import validate_natural_day


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--session-audit', type=Path, required=True)
    args = p.parse_args()
    import numpy as np
    import pandas as pd
    root = args.repo_root.resolve()
    session_audit = json.loads(args.session_audit.read_text())
    if session_audit.get('status') != 'complete' or any(row.get('status') != 'complete' for row in session_audit.get('rows', [])) or not session_audit.get('rows'):
        raise SystemExit('actual_required_session_audit_not_complete')
    out = root / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage246_2020_20261014'
    cache = root / 'examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv'
    original = out / 'original_stage861_minute_cache.csv'
    if not original.exists():
        shutil.copy2(cache, original)
    sources = []
    frames = []
    # Broad pilot batches also contain Saturday early-night fragments and are
    # acquisition experiments, not final per-entry-day inputs.
    for folder, suffix in [('entry_minute_download', '_proof.json')]:
        for path in sorted((out / folder).glob('*.parquet')):
            proof_path = path.with_name(path.stem + suffix)
            proof = json.loads(proof_path.read_text())
            if proof.get('sha256') != digest(path):
                raise SystemExit(f'invalid_download_digest:{path.name}')
            frame = pd.read_parquet(path)
            frame['_source_rank'] = 1 if folder == 'entry_minute_download' else 0
            frame['bar_datetime'] = pd.to_datetime(frame.bar_datetime)
            frame['bar_date'] = frame.bar_datetime.dt.strftime('%Y-%m-%d')
            for (vt, day), group in frame.groupby(['vt_symbol', 'bar_date']):
                validate_natural_day(group.sort_values('bar_datetime'), str(vt), str(day))
            frames.append(frame)
            sources.append({'path': str(path), 'sha256': proof['sha256'], 'rows': len(frame)})
    if not frames:
        raise SystemExit('no_validated_minute_sources')
    new = pd.concat(frames, ignore_index=True).sort_values(['vt_symbol', 'bar_datetime', '_source_rank'], kind='stable')
    keys = ['vt_symbol', 'bar_datetime']
    values = ['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']
    duplicates = new[new.duplicated(keys, keep=False)]
    if len(duplicates) and duplicates.groupby(keys)[values].nunique().gt(1).any().any():
        raise SystemExit('conflicting_completed_snapshot_values')
    new = new.drop_duplicates(keys, keep='last')
    new = new.drop(columns='_source_rank')
    new['tq_symbol'] = new.vt_symbol.str.split('.').str[1] + '.' + new.vt_symbol.str.split('.').str[0]
    base = pd.read_csv(original)
    base['bar_datetime'] = pd.to_datetime(base.bar_datetime)
    base['bar_date'] = base.bar_datetime.dt.strftime('%Y-%m-%d')
    daykeys = ['vt_symbol', 'bar_date']
    replace_keys = pd.MultiIndex.from_frame(new[daykeys].drop_duplicates())
    replaced = base[pd.MultiIndex.from_frame(base[daykeys]).isin(replace_keys)]
    retained = base[~pd.MultiIndex.from_frame(base[daykeys]).isin(replace_keys)]
    old_times = pd.MultiIndex.from_frame(replaced[keys])
    new_times = pd.MultiIndex.from_frame(new[keys])
    removed_times = old_times.difference(new_times)
    if len(removed_times):
        pd.DataFrame(removed_times.tolist(), columns=keys).to_csv(out / f'minute_removed_times_{args.label}.csv', index=False)
        raise SystemExit(f'old_minute_timestamps_would_be_removed:{len(removed_times)}')
    compare = replaced.merge(new, on=keys, suffixes=('_old', '_new'))
    differences = {}
    for col in values:
        differences[col] = int((~np.isclose(compare[col+'_old'], compare[col+'_new'], rtol=0, atol=1e-8, equal_nan=True)).sum())
    merged = pd.concat([retained, new], ignore_index=True).sort_values(keys).reset_index(drop=True)
    if merged.duplicated(keys).any():
        raise SystemExit('duplicate_merged_minutes')
    temp = cache.with_suffix('.stage246.tmp.csv')
    merged.to_csv(temp, index=False, encoding='utf-8-sig')
    cache_before = digest(cache)
    os.replace(temp, cache)
    summary = {
        'status': 'completed', 'label': args.label, 'base_cache': str(original), 'base_sha256': digest(original),
        'cache_before_sha256': cache_before, 'cache_after_sha256': digest(cache),
        'base_rows': len(base), 'new_snapshot_rows': len(new), 'refreshed_contract_days': len(replace_keys),
        'old_rows_replaced': len(replaced), 'merged_rows': len(merged), 'matched_rows_compared': len(compare),
        'old_timestamps_removed': len(removed_times), 'new_timestamps_added': len(new_times.difference(old_times)),
        'changed_values_by_field': differences, 'source_files': sources,
        'policy': 'Replace entire validated natural-day keys; retain all other original rows. Official natural-day semantics unchanged.',
        'required_session_audit': str(args.session_audit.resolve()), 'required_session_audit_sha256': digest(args.session_audit),
    }
    (out / f'minute_merge_{args.label}.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
