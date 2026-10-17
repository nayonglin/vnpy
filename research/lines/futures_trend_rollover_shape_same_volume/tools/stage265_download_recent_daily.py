"""Download only recent daily bars via existing ordinary TqSdk market rights.

Research output only. Complete sessions through 2026-10-16; never orders,
minute bars, professional range downloads, or writes to the main database.
"""
from __future__ import annotations
import contextlib
import io
import json
import logging
from pathlib import Path
import pickle
import signal
import time
from datetime import datetime

from stage264_diagnose_tqsdk import redact

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUT = LINE / 'outputs/stage265_deep_daily/tq_latest'
END, START = '2026-10-16', '2026-09-01'
EXCHANGES = {'DCE', 'CZCE', 'GFEX'}


class PrimitivesOnly(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError('archive metadata globals forbidden')

    def persistent_load(self, pid):
        raise pickle.UnpicklingError('archive metadata persistent ids forbidden')


def select_symbols(current, metadata):
    selected = {s for s in current if s.split('.')[0] in EXCHANGES}
    for item in metadata:
        if item.get('type') != 'Future' or item.get('exchange') not in EXCHANGES:
            continue
        listed, ended = item.get('listed_date', ''), item.get('de_listed_date', '')
        if '2000-01-01' <= listed <= END and '2026-10-01' <= ended:
            selected.add(item['exchange'] + '.' + item['trading_code'])
    return sorted(selected)


def deadline(signum, frame):
    raise TimeoutError('recent_daily_download_global_deadline')


def main():
    import pandas as pd
    from tqsdk import TqApi, TqAuth, TqSim
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / 'daily35'
    raw.mkdir(exist_ok=True)
    current = json.loads((OUT / 'current_futures_catalog.json').read_text())['symbols']
    with (OUT.parent / 'rqalpha/instruments.pk').open('rb') as stream:
        metadata = PrimitivesOnly(stream).load()
    symbols = select_symbols(current, metadata)
    status_path = OUT / 'recent_download_status.json'
    report = json.loads(status_path.read_text()) if status_path.exists() else {
        'started_at': datetime.now().astimezone().isoformat(), 'cutoff': END,
        'start': START, 'duration_seconds': 86400, 'data_length': 35,
        'broker_connections': 0, 'order_api_calls': 0, 'cancel_api_calls': 0,
        'items': {}}
    report.update(expected_symbols=symbols, expected_contracts=len(symbols), status='running')
    def save():
        report['updated_at'] = datetime.now().astimezone().isoformat()
        tmp = status_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        tmp.replace(status_path)
    pending = [s for s in symbols if report['items'].get(s, {}).get('status') != 'downloaded']
    if not pending:
        print('all expected recent symbols already downloaded; no network')
        return
    cfg = json.loads((ROOT / '.vntrader/vt_setting.json').read_text())
    secrets = [cfg.get('datafeed.username', ''), cfg.get('datafeed.password', '')]
    api = auth = None
    logging.disable(logging.CRITICAL)
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(360)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            auth = TqAuth(cfg['datafeed.username'], cfg['datafeed.password'])
            api = TqApi(TqSim(), auth=auth, debug=False, disable_print=True, web_gui=False)
            for offset in range(0, len(pending), 80):
                batch = pending[offset:offset + 80]
                frames = {}
                async def subscribe():
                    for symbol in batch:
                        frames[symbol] = api.get_kline_serial(symbol, 86400, data_length=35)
                task = api.create_task(subscribe())
                until = time.monotonic() + 40
                while time.monotonic() < until:
                    if task.done() and task.exception():
                        raise task.exception()
                    if len(frames) == len(batch) and all(api.is_serial_ready(f) for f in frames.values()):
                        break
                    api.wait_update(deadline=time.time() + 3)
                for symbol in batch:
                    frame = frames.get(symbol)
                    if frame is None or not api.is_serial_ready(frame):
                        report['items'][symbol] = {'status': 'not_ready'}
                        continue
                    data = frame.copy()
                    data = data[data.datetime.gt(0)].copy()
                    clock = pd.to_datetime(data.datetime, unit='ns', utc=True).dt.tz_convert('Asia/Shanghai')
                    data['timestamp_shanghai'] = clock.astype(str)
                    data['trade_date'] = clock.dt.strftime('%Y-%m-%d')
                    partial = int(data.trade_date.gt(END).sum())
                    data = data[data.trade_date.between(START, END)]
                    target = raw / (symbol.replace('.', '_') + '.csv')
                    data.to_csv(target, index=False)
                    report['items'][symbol] = {'status': 'downloaded', 'rows': len(data),
                        'first_date': data.trade_date.min() if len(data) else None,
                        'last_date': data.trade_date.max() if len(data) else None,
                        'future_or_incomplete_rows_excluded': partial,
                        'file': str(target.relative_to(OUT))}
                save()
        report['status'] = 'complete' if all(report['items'].get(s, {}).get('status') == 'downloaded' for s in symbols) else 'partial'
    except Exception as error:
        if auth:
            secrets.extend(str(getattr(auth, k, '') or '') for k in ['_access_token', '_refresh_token', '_auth_id'])
        report.update(status='partial_or_failed', error_type=type(error).__name__, error_redacted=redact(str(error), secrets))
    finally:
        signal.alarm(0)
        if api is not None:
            with contextlib.suppress(Exception), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                signal.alarm(8)
                api.close()
        signal.alarm(0)
        save()
    print(json.dumps({'status': report['status'], 'expected_contracts': len(symbols),
        'downloaded': sum(x['status'] == 'downloaded' for x in report['items'].values()),
        'error_redacted': report.get('error_redacted')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
