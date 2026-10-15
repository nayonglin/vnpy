"""Supply validated actual execution days to the existing formal raw-data root."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from stage246_download_entry_minutes import cached_groups, read_coverage


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--required', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    import numpy as np
    import pandas as pd
    root = args.repo_root.resolve()
    out = root / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage246_2020_20261014'
    rawroot = root / 'examples/portfolio_backtesting/downloaded_futures/tqsdk_stage506_next_real_forward_risk_signal_frontier'
    keys = read_coverage([args.required])
    by_symbol = {}
    for vt, day in sorted(keys):
        groups, _ = cached_groups(out / 'entry_minute_download', day)
        if vt not in groups:
            raise SystemExit(f'required_execution_day_not_validated:{vt}:{day}')
        by_symbol.setdefault(vt, []).append(groups[vt])
    audit = []
    for vt, frames in sorted(by_symbol.items()):
        contract, exchange = vt.split('.')
        path = rawroot / exchange / f'{contract}_minute_backtest.csv'
        backup = out / 'execution_raw_original' / exchange / path.name
        new = pd.concat(frames, ignore_index=True).sort_values('bar_datetime')
        new['tq_symbol'] = f'{exchange}.{contract}'
        before_sha = None
        changes = {}
        if path.exists():
            before_sha = digest(path)
            if not backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
            old = pd.read_csv(path)
            old['bar_datetime'] = pd.to_datetime(old.bar_datetime)
            old['vt_symbol'] = vt
        else:
            old = pd.DataFrame(columns=new.columns)
        fields = ['open','high','low','close','volume','open_oi','close_oi']
        if len(old):
            common = old.merge(new, on=['vt_symbol','bar_datetime'], suffixes=('_old','_new'))
            for col in fields:
                if col+'_old' in common:
                    changes[col] = int((~np.isclose(common[col+'_old'], common[col+'_new'], rtol=0, atol=1e-8, equal_nan=True)).sum())
        joined = pd.concat([old, new], ignore_index=True).drop_duplicates(['vt_symbol','bar_datetime'], keep='last').sort_values('bar_datetime')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.stage246.tmp.csv')
        joined.to_csv(temporary, index=False, encoding='utf-8-sig')
        os.replace(temporary, path)
        audit.append({'vt_symbol':vt,'dates':sorted(set(new.bar_date)), 'path':str(path),
                      'before_sha256':before_sha,'after_sha256':digest(path), 'old_rows':len(old),
                      'new_snapshot_rows':len(new),'final_rows':len(joined),'changed_overlap_values':changes})
    (out / f'execution_minute_patch_{args.label}.json').write_text(json.dumps({'status':'completed','requirements':str(args.required.resolve()),'required_keys':len(keys),'files':audit}, ensure_ascii=False, indent=2))
    print(json.dumps({'required_keys':len(keys),'contracts':len(audit),'status':'completed'}))


if __name__ == '__main__':
    main()
