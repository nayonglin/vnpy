"""Supplement fixed-universe minute history using completed TqBacktest snapshots.

No trading methods are called. Per-batch parquet and SHA checkpoints are reusable;
the formal Stage861 cache is not modified by this downloader.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import gc
import json
import os
from pathlib import Path
import sys
import time

from stage246_download_entry_minutes import validate_natural_day


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--bundle-root', type=Path, required=True)
    parser.add_argument('--credential-settings', type=Path, required=True)
    parser.add_argument('--start', default='2020-01-01')
    parser.add_argument('--end', default='2026-10-14')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    os.chdir(root)
    os.umask(0o077)
    os.environ['TZ'] = 'Asia/Shanghai'
    time.tzset()
    sys.path[:0] = [str(root), str(args.bundle_root / 'vendor'), str(root / 'examples/portfolio_backtesting')]
    import numpy as np
    import pandas as pd
    from tqsdk import TqApi, TqAuth, TqSim, TqBacktest

    data = root / 'examples/portfolio_backtesting/backtest_outputs'
    out = root / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage246_2020_20261014/minute_download'
    out.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(data / 'qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv').product_vt_symbol.tolist()
    mapping = pd.read_csv(data / 'tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv')
    mapping = mapping[mapping.continuous_symbol_vt.isin(universe) & mapping.main_contract_vt.notna()].copy()
    mapping['date'] = pd.to_datetime(mapping.date)
    mapping = mapping[mapping.main_contract_vt.astype(str).str.contains('.', regex=False)]
    cfg = json.loads(args.credential_settings.read_text())
    records = []
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    windows = [(d, min(d + pd.Timedelta(days=13), end)) for d in pd.date_range(start, end, freq='14D')]
    if args.limit:
        windows = windows[:args.limit]
    for batch_index, (begin, finish) in enumerate(windows, 1):
        batch_id = f'{begin:%Y%m%d}_{finish:%Y%m%d}'
        dest, proof_path = out / f'{batch_id}.parquet', out / f'{batch_id}.json'
        if dest.exists() and proof_path.exists():
            proof = json.loads(proof_path.read_text())
            if proof.get('status') == 'completed' and digest(dest) == proof.get('sha256'):
                records.append(proof)
                print(f'{batch_index}/{len(windows)} {batch_id} cached rows={proof["rows"]}', flush=True)
                continue
        nearby = mapping[mapping.date.between(begin - pd.Timedelta(days=14), finish + pd.Timedelta(days=14))]
        expected = mapping[mapping.date.between(begin, finish)].copy()
        symbols = sorted(nearby.main_contract_vt.unique())
        expected_by_symbol = expected.groupby('main_contract_vt').date.apply(lambda s: sorted(set(s.dt.strftime('%Y-%m-%d')))).to_dict()
        snapshot_at = (finish + pd.Timedelta(days=1, hours=8)).to_pydatetime()
        proof = {'batch_id': batch_id, 'start': str(begin.date()), 'end': str(finish.date()),
                 'snapshot_at': snapshot_at.isoformat(), 'symbols': symbols,
                 'expected_main_contract_days': len(expected), 'source': 'tqsdk_completed_history_snapshot',
                 'status': 'failed', 'rows': 0, 'send_order_api_calls': 0}
        api = None
        started = time.monotonic()
        print(f'{batch_index}/{len(windows)} {batch_id} starting symbols={len(symbols)}', flush=True)
        try:
            api = TqApi(TqSim(), backtest=TqBacktest(start_dt=snapshot_at, end_dt=snapshot_at + timedelta(days=4)),
                        auth=TqAuth(cfg['datafeed.username'], cfg['datafeed.password']), disable_print=True)
            serials = {}
            # Register subscriptions together in the SDK event loop. This avoids
            # advancing the historical clock once per synchronous subscription.
            # Disable repeated cyclic scans over the large transient SDK graph;
            # perform one collection after the API is closed instead.
            gc.disable()
            async def subscribe():
                for vt in symbols:
                    symbol, exchange = vt.split('.')
                    serials[vt] = api.get_kline_serial(f'{exchange}.{symbol}', 60, data_length=8964)
            subscription_task = api.create_task(subscribe())
            while (len(serials) != len(symbols) or not all(api.is_serial_ready(s) for s in serials.values())) and time.monotonic() - started < 150:
                api.wait_update(deadline=time.time() + 5)
            if len(serials) != len(symbols):
                raise RuntimeError('incomplete_subscription_registration')
            frames, day_counts, gaps = [], [], []
            for vt, serial in serials.items():
                if not api.is_serial_ready(serial):
                    gaps.append({'vt_symbol': vt, 'reason': 'serial_not_ready'})
                    continue
                frame = serial.copy()
                frame = frame[(frame.id >= 0) & (frame.datetime > 0)].copy()
                frame['bar_datetime'] = pd.to_datetime(frame.datetime, unit='ns', utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
                frame = frame[(frame.bar_datetime >= begin) & (frame.bar_datetime < finish + pd.Timedelta(days=1))].copy()
                frame['bar_date'] = frame.bar_datetime.dt.strftime('%Y-%m-%d')
                frame['vt_symbol'] = vt
                frame['minute_source'] = 'stage246_tqsdk_completed_history_snapshot'
                cols = ['vt_symbol', 'bar_datetime', 'bar_date', 'open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi', 'minute_source']
                frame = frame[cols]
                prices = frame[['open', 'high', 'low', 'close']]
                valid = np.isfinite(frame[['open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi']]).all(axis=1)
                valid &= (prices > 0).all(axis=1) & frame[['volume', 'open_oi', 'close_oi']].ge(0).all(axis=1)
                valid &= frame.high.ge(prices.max(axis=1)) & frame.low.le(prices.min(axis=1))
                if not valid.all() or frame.bar_datetime.duplicated().any():
                    raise ValueError(f'invalid_ohlcv_or_duplicate:{vt}')
                for day, group in frame.groupby('bar_date'):
                    validate_natural_day(group.sort_values('bar_datetime'), vt, day)
                    daytime = group[group.bar_datetime.dt.hour.between(9, 14)]
                    day_counts.append({'vt_symbol': vt, 'bar_date': day, 'rows': len(group), 'daytime_rows': len(daytime),
                                       'first': str(group.bar_datetime.min()), 'last': str(group.bar_datetime.max())})
                counts = frame.groupby('bar_date').size().to_dict()
                for day in expected_by_symbol.get(vt, []):
                    if day not in counts:
                        gaps.append({'vt_symbol': vt, 'bar_date': day, 'rows': 0, 'reason': 'mapped_main_day_missing'})
                frames.append(frame)
            joined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            joined = joined.sort_values(['vt_symbol', 'bar_datetime']) if len(joined) else joined
            proof.update(rows=len(joined), coverage_gaps=gaps, day_count=len(day_counts), status='completed' if not gaps else 'coverage_incomplete')
            joined.to_parquet(dest, index=False)
            pd.DataFrame(day_counts).to_csv(out / f'{batch_id}_coverage.csv', index=False)
            proof['sha256'] = digest(dest)
        except Exception as exc:
            proof['error_type'] = type(exc).__name__
            # Do not log exception text: third-party messages can contain credentials.
        finally:
            if api is not None:
                api.close()
                api = None
            if 'serials' in locals():
                serials.clear()
            gc.collect()
            gc.enable()
        proof['elapsed_seconds'] = round(time.monotonic() - started, 3)
        proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2))
        records.append(proof)
        (out / 'progress.json').write_text(json.dumps({'status': 'partial' if args.limit else 'mapped_scope_only', 'total_selected_batches': len(windows), 'finished': len(records), 'results': records, 'limitation': 'Nearby main mapping does not prove delayed-roll contracts or actual-open completeness; use entry-day fixed-point audit.'}, ensure_ascii=False, indent=2))
        print(f'{batch_index}/{len(windows)} {batch_id} {proof["status"]} rows={proof["rows"]} seconds={proof["elapsed_seconds"]}', flush=True)
        if proof['status'] != 'completed':
            raise SystemExit('batch failed; inspect sanitized checkpoint before resuming')
    if args.limit:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
