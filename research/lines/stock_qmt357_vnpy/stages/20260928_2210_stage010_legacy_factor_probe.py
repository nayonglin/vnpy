"""Bounded public BaoStock query for the announcement-verified 300114 identity."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from examples.stock_backtesting.qmt357.baostock_download import collect_response
from examples.stock_backtesting.qmt357.history_download import _deadline
import baostock as bs

target = ROOT / 'examples/stock_backtesting/qmt357_commit4ac255e/data/factor_crosscheck/legacy_300114'
target.mkdir(exist_ok=False, parents=True)
socket.setdefaulttimeout(20)
params = dict(code='sz.300114', start_date='1990-01-01', end_date='2026-09-28')
receipt = dict(endpoint='query_adjust_factor', params=params,
    time_utc=datetime.now(timezone.utc).isoformat(), source='baostock public SDK')
try:
    with _deadline(30):
        login = bs.login()
        if login.error_code != '0':
            raise RuntimeError(login.error_msg)
        frame = collect_response(bs.query_adjust_factor(**params))
        if len(frame) and not frame.code.eq(params['code']).all():
            raise ValueError('Wrong security in provider response')
        raw = frame.to_parquet(index=False)
        (target / 'factors.parquet').write_bytes(raw)
        receipt.update(rows=len(frame), sha256=hashlib.sha256(raw).hexdigest(), status='OK')
        print(frame.to_string(index=False))
except Exception as exc:
    receipt.update(status='FAILED', error_type=type(exc).__name__, error=str(exc))
finally:
    try:
        with _deadline(5):
            bs.logout()
    except Exception:
        pass
    (target / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))
