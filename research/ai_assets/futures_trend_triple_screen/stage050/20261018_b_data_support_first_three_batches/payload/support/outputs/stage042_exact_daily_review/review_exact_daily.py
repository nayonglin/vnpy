"""Independently qualify one actual request's daily row in bound 013/040 raw.

No network, engine, source writes, or response writer. Each request is immutable.
Only one exact requested symbol/day is qualified, including for anchor requests.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import argparse
import csv
import json
import math
import sqlite3
import sys

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
sys.path.insert(0, str(LINE / 'tools'))
import pandas as pd
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate

R013 = LINE / 'outputs/stage013_independent_review/review_receipt.json'
R013_SHA = '194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
TERMINAL040 = LINE / 'outputs/stage040_exact_request_daily_recovery/terminal_observed.json'
TERMINAL040_SHA = 'e13d4b523b507bc7267bbcac0d2cd7ccf7e08798c961c90405e372d1efbd55e0'
VALUES = old.VALUES


def read_json(path): return json.loads(Path(path).read_text())
def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def write(path, value):
    with Path(path).open('x') as f: f.write(json.dumps(old.safe(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def integer(value):
    v = Decimal(str(value))
    assert v.is_finite() and v == v.to_integral_value()
    return int(v)
def local_ns(value):
    seconds, nano = divmod(value, 1_000_000_000)
    return (datetime.fromtimestamp(seconds, timezone.utc) + timedelta(microseconds=nano // 1000)).astimezone(timezone(timedelta(hours=8)))
def legal(row):
    try:
        n = {k: float(row[k]) for k in VALUES}
        return all(math.isfinite(v) for v in n.values()) and min(n[k] for k in ['open','high','low','close']) > 0 and min(n[k] for k in ['volume','open_oi','close_oi']) >= 0 and n['low'] <= min(n['open'],n['close']) <= max(n['open'],n['close']) <= n['high']
    except (ValueError, TypeError, KeyError): return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-file-sha256', required=True)
    args = parser.parse_args()
    inputs = {}
    def bind(path, expected=None):
        path = Path(path).resolve(); actual = old.sha256(path)
        assert expected is None or actual == expected, str(path)
        inputs[str(path)] = actual
        return actual
    path = args.request.resolve()
    assert path.parent.parent == (LINE / 'outputs/stage036_b_ts_account/B_TS/data_wait').resolve()
    bind(path, args.request_file_sha256)
    request = read_json(path); digest = gate.request_sha256(request)
    assert request['schema'] == gate.REQUEST_SCHEMA and digest == request['request_sha256']
    assert path.parent.name == 'request_' + digest and path.name == 'request.json'
    fp = path.parent / 'request_fingerprint.json'; bind(fp)
    assert read_json(fp) == dict(request_sha256=digest, request_file_sha256=args.request_file_sha256, request_path=str(path))
    assert len(request['requirements']) == 1
    target = request['requirements'][0]
    symbol, day, kind = (target[k] for k in ['vt_symbol','execution_trade_date','requirement_kind'])
    assert kind in {'full_session','anchor'} and day == request['execution_trade_date']
    native, exchange = symbol.rsplit('.',1)
    bind(R013, R013_SHA); old_review = read_json(R013)
    assert old_review['qualified_research_daily'] and not old_review['p0_findings'] and not old_review['p1_findings']
    assert (symbol,day) not in {(r['vt_symbol'],r['trade_date']) for r in old_review['rejected_targets']}
    provider = LINE / 'outputs/stage013_missing_daily_recovery'
    symbols_path = provider / 'network_attempt1/symbol_receipts.json'
    symbols = read_json(symbols_path)
    info = [v for v in symbols if v['vt_symbol'] == symbol]
    if not info:
        provider = LINE / 'outputs/stage040_exact_request_daily_recovery'
        bind(TERMINAL040, TERMINAL040_SHA)
        terminal = read_json(TERMINAL040)
        assert terminal['terminal_observed'] and terminal['exit_code'] == 0
        symbols_path = provider / 'network_attempt1/symbol_receipts.json'
        info = [v for v in read_json(symbols_path) if v['vt_symbol'] == symbol]
    assert len(info) == 1, 'no already-bound raw snapshot for actual symbol'
    attempt = provider / 'network_attempt1'
    parent_path = attempt / 'parent_receipt.json'
    expected_parent = old_review['source_fingerprints'][str(parent_path)] if provider.name == 'stage013_missing_daily_recovery' else terminal['parent_receipt_sha256']
    bind(parent_path, expected_parent); parent = read_json(parent_path)
    assert parent['status'] == 'worker_terminal' and parent['all_inputs_unchanged'] and not parent['hard_kill']
    assert parent['exit_code'] == (1 if provider.name == 'stage013_missing_daily_recovery' else 0)
    for k in ['TqBacktest_instances','financial_replays','orders','cancels','broker_or_ctp_connections']: assert parent[k] == 0
    preflight_path = provider / 'preflight.json'; bind(preflight_path,parent['preflight_sha256']); preflight=read_json(preflight_path)
    bind(symbols_path,parent['artifact_sha256']['symbol_receipts.json'])
    raw_path=Path(info[0]['raw_path']); assert raw_path==attempt/'raw'/exchange/(native+'.csv')
    bind(raw_path,info[0]['raw_sha256']); assert info[0]['raw_sha256']==parent['artifact_sha256'][str(raw_path.relative_to(attempt))]
    raw=rows(raw_path); assert len(raw)==info[0]['raw_rows']
    valid=[]
    for index,row in enumerate(raw):
        if not legal(row): continue
        ident,ns=integer(row['id']),integer(row['datetime'])
        if ident>=0 and ns>0: valid.append((index,ident,ns,row))
    selected=[v for v in valid if local_ns(v[2]).date().isoformat()==day]
    assert len(selected)==1,'unique exact raw daily required'
    source_index,source_id,source_ns,row=selected[0]
    later=[v for v in valid if v[1]>source_id and v[2]>source_ns]
    assert later,'true valid forward daily successor required'
    next_index,next_id,next_ns,next_row=min(later,key=lambda v:(v[1],v[2]))
    dbpath=ROOT/'.vntrader/database.db'
    with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        exact=db.execute('SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND substr(datetime,1,10)=?',(native,exchange,'d',day)).fetchall()
    assert len(exact)==1
    six=['open','high','low','close','volume','open_oi']; db_six=dict(zip(six,exact[0])); daily={k:float(row[k]) for k in VALUES}
    difference={k:abs(daily[k]-float(db_six[k])) for k in six}
    assert all(math.isclose(daily[k],float(db_six[k]),rel_tol=1e-12,abs_tol=1e-8) for k in six)
    bind(old.MAPPING,preflight['source_fingerprints'][str(old.MAPPING)])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(old.MAPPING,usecols=['date']).date.unique())))
    grid=old.session_grid(symbol,day,calendar); required=grid if kind=='full_session' else grid[:1]
    assert target['required_timestamps']==[s.isoformat() for s in required]
    dest=Path(__file__).parent/('request_'+digest);dest.mkdir(exist_ok=False)
    proof=dict(source_bar_id=source_id,source_datetime_ns=source_ns,successor_id=next_id,successor_datetime_ns=next_ns)
    qualified=dest/'qualified_daily.csv';audit=dest/'target_qualification.csv'
    pd.DataFrame([dict(vt_symbol=symbol,tq_symbol=exchange+'.'+native,trade_date=day,datetime=local_ns(source_ns).isoformat(),**daily,**proof,successor_time=local_ns(next_ns).isoformat())]).to_csv(qualified,index=False)
    pd.DataFrame([dict(vt_symbol=symbol,trade_date=day,accepted=True,reason='completed_and_six_fields_matched',mismatch_fields='',database_closeOI='N/A_not_independently_available',**proof)]).to_csv(audit,index=False)
    bind(qualified);bind(audit);bind(Path(__file__))
    checks=dict(request_sha256=digest,vt_symbol=symbol,trade_date=day,requirement_kind=kind,daily=daily,exact_DB_six=db_six,
        six_fields_checked=True,six_fields_max_abs_difference=difference,DB_open_interest_maps_to='provider.open_oi',database_closeOI='N/A_not_independently_available',
        actual_raw_forward_successor_checked=True,source_csv_row=source_index+2,successor_csv_row=next_index+2,**proof,
        source_local_time=local_ns(source_ns).isoformat(),successor_local_time=local_ns(next_ns).isoformat(),
        successor_values={k:float(next_row[k]) for k in VALUES},raw_rows=len(raw),raw_non_target_daily_rows_qualified=False,
        exact_DB_queries=1,full_DB_rehashed_by_reviewer=False,inherited_DB_sha256=preflight['source_fingerprints'][str(dbpath)],
        provider_original_exit_code=parent['exit_code'],provider_original_rejections_preserved=True)
    checkpath=dest/'daily_checks.json';write(checkpath,checks);bind(checkpath)
    receipt=dict(schema='stage042_independent_exact_daily_v1',reviewed_at=datetime.now().astimezone().isoformat(),independent_review=True,
        reviewer='ordered_execution_review_exact_daily',qualified_research_daily=True,p0_findings=0,p1_findings=0,p2_findings=0,
        request_sha256=digest,accepted_target_keys=[[symbol,day]],qualified_rows=1,target_rows=1,
        qualified_daily_path=str(qualified),target_qualification_path=str(audit),daily_checks_path=str(checkpath),
        six_fields_checked=True,actual_raw_forward_successor_checked=True,database_closeOI='N/A_not_independently_available',
        source_fingerprints=inputs,network_connections_in_review=0,financial_replays=0,model_fits=0,orders=0,response_written=False,production_qualified=False)
    assert all(old.sha256(p)==h for p,h in inputs.items())
    receipt_path=dest/'daily_review_receipt.json';write(receipt_path,receipt)
    print(json.dumps(dict(status='exact_actual_request_daily_accepted',receipt_path=str(receipt_path),receipt_sha256=old.sha256(receipt_path),daily=daily),ensure_ascii=False))


if __name__=='__main__':main()
