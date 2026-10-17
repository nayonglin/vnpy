"""Bounded market-data diagnostic: redacted errors, grant booleans, no orders."""
from __future__ import annotations

import argparse
import contextlib
from datetime import date, datetime, timedelta
import io
import json
import logging
from pathlib import Path
import re
import signal
import time
import traceback

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parents[1] / 'outputs/stage264_pre_main_daily/tqsdk_diagnosis'


def redact(message: str, secrets: list[str]) -> str:
    result = message
    for value in sorted(set(str(value) for value in secrets if value), key=len, reverse=True):
        result = result.replace(value, '<redacted>')
    result = re.sub(r'https?://[^\s\"\'<>]+', '<provider_url>', result)
    result = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '<email>', result)
    result = re.sub(r'[A-Za-z0-9_+/=.-]{32,}', '<token>', result)
    return result[:1000]


def deadline(signum, frame):
    raise TimeoutError('bounded_diagnostic_deadline')


def run(mode: str) -> dict:
    report = {'mode': mode, 'stage': 'read_local_config', 'broker_connections': 0,
              'order_api_calls': 0, 'generated_at': datetime.now().astimezone().isoformat()}
    cfg = json.loads((ROOT / '.vntrader/vt_setting.json').read_text())
    secrets = [str(cfg.get(key, '')) for key in ['datafeed.username', 'datafeed.password']]
    api, auth = None, None
    logging.disable(logging.CRITICAL)
    signal.signal(signal.SIGALRM, deadline)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from tqsdk import TqApi, TqAuth, TqSim, TqBacktest
            signal.alarm(45)
            auth = TqAuth(cfg['datafeed.username'], cfg['datafeed.password'])
            report['stage'] = 'construct_api'
            options = {}
            if mode == 'snapshot':
                start = datetime(2015, 4, 29, 8)
                options['backtest'] = TqBacktest(start_dt=start, end_dt=start+timedelta(days=21))
            api = TqApi(TqSim(), auth=auth, debug=False, disable_print=True, web_gui=False, **options)
            report['api_constructed'] = True
            report['stage'] = 'query_daily'
            if mode == 'range':
                frame = api.get_kline_data_series('SHFE.rb1505', 86400, date(2014, 1, 1), date(2015, 6, 1))
                report.update(status='returned', rows=len(frame))
            elif mode == 'serial':
                frame = api.get_kline_serial('SHFE.rb1505', 86400, data_length=1000)
                report.update(status='returned', rows=int(frame.datetime.gt(0).sum()))
            else:
                serials = {}
                async def subscribe():
                    serials['frame'] = api.get_kline_serial('SHFE.rb1505', 86400, data_length=1000)
                api.create_task(subscribe())
                report['stage'] = 'wait_snapshot'
                started = time.monotonic()
                while time.monotonic()-started < 25:
                    if 'frame' in serials and api.is_serial_ready(serials['frame']):
                        break
                    api.wait_update(deadline=time.time()+3)
                report.update(status='ready' if 'frame' in serials and api.is_serial_ready(serials['frame']) else 'not_ready')
                if report['status'] == 'ready':
                    report['rows'] = int(serials['frame'].datetime.gt(0).sum())
    except Exception as error:
        signal.alarm(0)
        if auth is not None:
            secrets.extend(str(getattr(auth, key, '') or '') for key in ['_access_token', '_refresh_token', '_auth_id'])
        report.update(status='failed', error_type=type(error).__name__,
                      error_redacted=redact(str(error), secrets),
                      traceback_locations=[{'file': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
                                           for frame in traceback.extract_tb(error.__traceback__)[-6:]])
    finally:
        signal.alarm(0)
        if auth is not None:
            features = auth._grants.get('features', [])
            report['login_grants'] = {key: key in features for key in ['futr', 'tq_dl']}
            report['auth_mode'] = auth._mode
            report['access_token_received'] = bool(auth._access_token)
        if api is not None:
            with contextlib.suppress(Exception), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                signal.alarm(6)
                api.close()
        signal.alarm(0)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['range', 'serial', 'snapshot'], required=True)
    args = parser.parse_args()
    destination = OUTPUT / f'{args.mode}.json'
    if destination.exists():
        raise SystemExit('diagnostic exists; inspect it instead of repeating requests')
    result = run(args.mode)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
