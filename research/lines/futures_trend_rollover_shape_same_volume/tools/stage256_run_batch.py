"""Run pre-frozen accounts in separate Python processes, preserving every result."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', type=Path, required=True)
    p.add_argument('--accounts', nargs='+')
    p.add_argument('--workers', type=int, default=3, choices=[1, 2, 3])
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    out = args.experiment.resolve()
    manifest_path = out / 'experiment_manifest.json'
    payload = manifest_path.read_bytes()
    registry = json.loads(payload)
    ids = args.accounts or list(registry['accounts'])
    if len(ids) != len(set(ids)) or set(ids) - registry['accounts'].keys():
        raise SystemExit('unknown_or_duplicate_accounts')
    lock = threading.Lock()
    batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    logpath = out / 'logs' / f'batch_{batch_id}.jsonl'
    runner = Path(__file__).with_name('stage256_run_account.py')
    runtime = json.loads((Path(registry['root']) / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/data_preparation/runtime_overlay.json').read_text())
    environment = dict(os.environ, PYTHONPATH=runtime['PYTHONPATH'], PYTHONDONTWRITEBYTECODE='1',
                       MPLCONFIGDIR='/private/tmp/stage256_mpl', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    def emit(record):
        record['timestamp'] = datetime.now().astimezone().isoformat()
        with lock:
            with logpath.open('a') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            print(json.dumps(record, ensure_ascii=False), flush=True)
    def one(account_id):
        info = registry['accounts'][account_id]
        directory = out / 'accounts' / account_id
        marker = directory / 'batch_completion.json'
        command = [sys.executable, str(runner), '--account-id', account_id,
                   '--repo-root', registry['root'],
                   '--baseline-root', '/Users/mac/.codex/worktrees/formal-2020-replay/fian',
                   '--pool-file', info['pool_file'], '--output', str(directory),
                   '--registry', str(manifest_path)]
        if args.dry_run:
            return {'account_id': account_id, 'status': 'dry_run', 'command': command}
        if marker.exists():
            old = json.loads(marker.read_text())
            if (old.get('manifest_sha256') == hashlib.sha256(payload).hexdigest()
                    and old.get('returncode') == 0 and (directory / 'metrics.json').exists()):
                return {'account_id': account_id, 'status': 'already_completed'}
            raise RuntimeError(f'inconsistent_completion_marker:{account_id}')
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f'refuse_to_overwrite_partial_or_unregistered_run:{account_id}')
        if manifest_path.read_bytes() != payload:
            raise RuntimeError('manifest_changed')
        begin = time.monotonic()
        emit({'account_id': account_id, 'status': 'started'})
        with (out / 'logs' / f'{account_id}.log').open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=registry['root'], env=environment)
        record = {'account_id': account_id, 'returncode': result.returncode,
                  'elapsed_seconds': round(time.monotonic() - begin, 3),
                  'manifest_sha256': hashlib.sha256(payload).hexdigest(),
                  'status': 'completed' if result.returncode == 0 else 'failed_preserved',
                  'command': command}
        directory.mkdir(exist_ok=True)
        marker.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        return record
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(one, account): account for account in ids}
        for future in as_completed(futures):
            account = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                record = {'account_id': account, 'status': 'orchestration_error', 'error': repr(exc)}
            results.append(record)
            emit(record)
    summary = {'manifest_sha256': hashlib.sha256(payload).hexdigest(), 'workers': args.workers,
               'requested': len(ids), 'results': results,
               'all_success': all(r['status'] in {'completed', 'already_completed', 'dry_run'} for r in results)}
    (out / 'logs' / f'batch_{batch_id}_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    if not summary['all_success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
