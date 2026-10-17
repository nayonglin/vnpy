"""Exact requested SM005 local delivery; no engine, provider, or response writer.

Reuse is limited to an existing one-symbol request and already bound snapshots.
Each invocation creates a new immutable request directory. No other raw dates
gain qualification. A nonempty existing-key scope requires a separate review.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys

LINE = Path(__file__).resolve().parents[2]
ROOT = LINE.parents[2]
sys.path.insert(0, str(LINE / 'tools'))
import numpy as np
import pandas as pd
import stage002_local_minute_overlay as old
import stage011_needed_local_completed as local
import stage021_blocking_data_gate as gate

PROVIDER = LINE / 'outputs/stage040_exact_request_daily_recovery'
ATTEMPT = PROVIDER / 'network_attempt1'
MINUTE = ROOT / 'examples/portfolio_backtesting/downloaded_futures/tqsdk_stage491_covered_key_full_session_backfill/CZCE/SM005_completed_minute_backtest.csv'
SOURCE_MANIFEST = LINE / 'outputs/stage002_local_minute_overlay/attempt2/source_manifest.json'
B_PREFLIGHT = LINE / 'outputs/stage036_b_ts_account/B_TS/preflight_used.json'
DB = ROOT / '.vntrader/database.db'
PROVIDER_SHA = '32ddecd055d7bb52b8d7f68ab8f1c5d3023ce0943f47045620b254d4e09cc820'
PREFLIGHT_SHA = 'ae032b5c8ad1ac1e9efa1a51c6af3f1ec0e537bcf47411853327547b1c824b9a'
TERMINAL_SHA = 'e13d4b523b507bc7267bbcac0d2cd7ccf7e08798c961c90405e372d1efbd55e0'
MANIFEST_SHA = '318da737a0a9e041919fbe6687669de3bf3aadacdbf191232b11ec43c6feb1ed'
MINUTE_SHA = '391899b58a6d58265fc02629e99622e16f6877dd84299800e1e0214373aa32b8'
FIELDS = old.VALUES
REVIEWER = 'ordered_execution_review_independent_exact_local_delivery'


def sha(path):
    return old.sha256(path)


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def read_json(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as f:
        f.write(json.dumps(old.safe(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def integer(value):
    number = Decimal(str(value))
    assert number.is_finite() and number == number.to_integral_value()
    return int(number)


def local_ns(value):
    seconds, nano = divmod(value, 1_000_000_000)
    return (datetime.fromtimestamp(seconds, timezone.utc) + timedelta(microseconds=nano // 1000)).astimezone(timezone(timedelta(hours=8)))


def legal(row):
    try:
        n = {k: float(row[k]) for k in FIELDS}
        return all(math.isfinite(v) for v in n.values()) and min(n[k] for k in ['open', 'high', 'low', 'close']) > 0 and min(n[k] for k in ['volume', 'open_oi', 'close_oi']) >= 0 and n['low'] <= min(n['open'], n['close']) <= max(n['open'], n['close']) <= n['high']
    except (ValueError, TypeError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    request_path = args.request.resolve()
    request = read_json(request_path)
    digest = gate.request_sha256(request)
    assert request['schema'] == gate.REQUEST_SCHEMA and request['request_sha256'] == digest
    assert request_path.parent.name == 'request_' + digest and len(request['requirements']) == 1
    wanted = request['requirements'][0]
    symbol, day, kind = (wanted[k] for k in ['vt_symbol', 'execution_trade_date', 'requirement_kind'])
    assert symbol == 'SM005.CZCE' and kind in {'full_session', 'anchor'}
    assert request['execution_trade_date'] == day
    assert not wanted['existing_source_timestamps'], 'nonempty old-key scope needs separately bound old values'
    assert wanted['missing_or_unqualified_timestamps'] == wanted['required_timestamps']
    fingerprints = {}

    def bind(path, expected=None):
        path = Path(path).resolve()
        actual = sha(path)
        assert expected is None or actual == expected, str(path)
        fingerprints[str(path)] = actual
        return actual

    bind(request_path)
    bind(Path(__file__))
    bind(PROVIDER / 'preflight.json', PREFLIGHT_SHA)
    bind(PROVIDER / 'terminal_observed.json', TERMINAL_SHA)
    bind(LINE / 'tools/stage040_exact_request_daily_recovery.py', PROVIDER_SHA)
    preflight = read_json(PROVIDER / 'preflight.json')
    terminal = read_json(PROVIDER / 'terminal_observed.json')
    parent = read_json(ATTEMPT / 'parent_receipt.json')
    worker = read_json(ATTEMPT / 'worker_receipt.json')
    bind(ATTEMPT / 'parent_receipt.json', terminal['parent_receipt_sha256'])
    assert terminal['terminal_observed'] is True and terminal['exit_code'] == 0
    assert terminal['source_sha256'] == PROVIDER_SHA and terminal['preflight_sha256'] == PREFLIGHT_SHA
    assert terminal['new_provider_connections'] == 1 and terminal['new_minute_provider_connections'] == 0
    assert parent['status'] == 'worker_terminal' and parent['exit_code'] == 0 and not parent['hard_kill'] and parent['all_inputs_unchanged']
    assert parent['preflight_sha256'] == PREFLIGHT_SHA and parent['request_sha256'] == preflight['request_sha256'] == terminal['request_sha256']
    assert worker['status'] == 'completed_all_targets_qualified' and worker['accepted_target_days'] == worker['target_days'] == 1
    assert worker['provider_connections_attempted'] == 1 and worker['TqSim_created']
    assert parent['elapsed_seconds'] < 600 and worker['peak_memory_bytes'] < 1_500_000_000
    for item in [parent, worker]:
        assert not item['automatic_retry'] and not item['production_qualified'] and not item['old_CSV_or_DB_written']
        assert not item['credential_values_saved']
        assert all(item[k] == 0 for k in ['TqBacktest_instances', 'financial_replays', 'orders', 'cancels', 'broker_or_ctp_connections'])
    for name, expected in parent['artifact_sha256'].items():
        bind(ATTEMPT / name, expected)
    for name in ['target_manifest.csv', 'excluded_constraints.csv']:
        bind(PROVIDER / name, preflight[name.replace('.csv', '_sha256')])
    assert not rows(PROVIDER / 'excluded_constraints.csv')
    raw_path = ATTEMPT / 'raw/CZCE/SM005.csv'
    raw = rows(raw_path)
    symbols = read_json(ATTEMPT / 'symbol_receipts.json')
    assert len(symbols) == 1 and symbols[0]['vt_symbol'] == symbol
    assert symbols[0]['raw_sha256'] == fingerprints[str(raw_path)] and len(raw) == symbols[0]['raw_rows']
    valid = []
    for index, row in enumerate(raw):
        if not legal(row):
            continue
        ident, ns = integer(row['id']), integer(row['datetime'])
        if ident >= 0 and ns > 0:
            valid.append((index, ident, ns, row))
    target = [v for v in valid if local_ns(v[2]).date().isoformat() == day]
    assert len(target) == 1, 'exact requested raw daily must be unique'
    source_index, source_id, source_ns, source_row = target[0]
    successors = [v for v in valid if v[1] > source_id and v[2] > source_ns]
    assert successors, 'daily completion requires a true later valid row'
    successor_index, successor_id, successor_ns, successor_row = min(successors, key=lambda v: (v[1], v[2]))
    native, exchange = symbol.rsplit('.', 1)
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db_rows = db.execute('SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND substr(datetime,1,10)=?', (native, exchange, 'd', day)).fetchall()
    assert len(db_rows) == 1
    six = ['open', 'high', 'low', 'close', 'volume', 'open_oi']
    db_six = dict(zip(six, db_rows[0]))
    assert all(math.isclose(float(source_row[k]), float(db_six[k]), rel_tol=1e-12, abs_tol=1e-8) for k in six)
    daily = {k: float(source_row[k]) for k in FIELDS}
    provider_qualified = [r for r in rows(ATTEMPT / 'qualified_daily.csv') if (r['vt_symbol'], r['trade_date']) == (symbol, day)]
    provider_audit = [r for r in rows(ATTEMPT / 'target_qualification.csv') if (r['vt_symbol'], r['trade_date']) == (symbol, day)]
    if provider_qualified:
        assert len(provider_qualified) == len(provider_audit) == 1
        q, a = provider_qualified[0], provider_audit[0]
        assert all(float(q[k]) == daily[k] for k in FIELDS)
        assert a['accepted'] == 'True' and a['reason'] == 'completed_and_six_fields_matched' and not a['mismatch_fields']
        assert a['database_closeOI'] == 'N/A_not_independently_available'
        for key, expected in [('source_bar_id', source_id), ('source_datetime_ns', source_ns), ('successor_id', successor_id), ('successor_datetime_ns', successor_ns)]:
            assert integer(q[key]) == integer(a[key]) == expected
        assert datetime.fromisoformat(q['datetime']) == local_ns(source_ns)
        assert datetime.fromisoformat(q['successor_time']) == local_ns(successor_ns)
    # Only the exact requested date is qualified, even though the raw snapshot contains other dates.
    dest = Path(__file__).parent / ('request_' + digest)
    dest.mkdir(exist_ok=False)
    daily_path = dest / 'reviewed_daily.csv'
    pd.DataFrame([dict(vt_symbol=symbol, trade_date=day, **daily)]).to_csv(daily_path, index=False)
    bind(daily_path)
    daily_checks = dict(vt_symbol=symbol, trade_date=day, daily=daily, exact_DB_six=db_six,
        six_fields_max_abs_difference={k: abs(daily[k] - float(db_six[k])) for k in six},
        DB_open_interest_maps_to='provider.open_oi', database_closeOI='N/A_not_independently_available',
        raw_snapshot_sha256=fingerprints[str(raw_path)], raw_rows=len(raw), source_csv_row=source_index + 2,
        source_id=source_id, source_ns=source_ns, source_local_time=local_ns(source_ns).isoformat(),
        successor_csv_row=successor_index + 2, successor_id=successor_id, successor_ns=successor_ns,
        successor_local_time=local_ns(successor_ns).isoformat(), successor_values={k: float(successor_row[k]) for k in FIELDS},
        exact_DB_queries=1, full_DB_rehashed_by_reviewer=False,
        inherited_DB_sha256=preflight['source_fingerprints'][str(DB)], provider_inputs_unchanged=parent['all_inputs_unchanged'],
        nonrequested_raw_daily_rows_qualified=False)
    write(dest / 'daily_checks.json', daily_checks)
    bind(dest / 'daily_checks.json')
    daily_receipt = dict(schema='stage039_independent_exact_daily_v1', reviewed_at=datetime.now().astimezone().isoformat(),
        independent_review=True, reviewer=REVIEWER, qualified_research_daily=True, p0_findings=0, p1_findings=0,
        request_sha256=digest, accepted_target_keys=[[symbol, day]], qualified_rows=1, target_rows=1,
        qualified_daily_path=str(daily_path), daily_checks_path=str(dest / 'daily_checks.json'),
        database_closeOI='N/A_not_independently_available', provider_request_sha256=preflight['request_sha256'],
        provider_actual_tool_terminal_exit_code=0, source_fingerprints=dict(fingerprints),
        network_connections_in_review=0, financial_replays=0, orders=0, production_qualified=False)
    write(dest / 'daily_review_receipt.json', daily_receipt)
    bind(dest / 'daily_review_receipt.json')
    bind(SOURCE_MANIFEST, MANIFEST_SHA)
    manifest = read_json(SOURCE_MANIFEST)
    source = [v for v in manifest['sources'] if v['path'] == str(MINUTE)]
    assert len(source) == 1 and source[0]['sha256'] == MINUTE_SHA
    bind(B_PREFLIGHT)
    b_preflight = read_json(B_PREFLIGHT)
    for path, expected in [(MINUTE, MINUTE_SHA), (SOURCE_MANIFEST, MANIFEST_SHA)]:
        assert b_preflight['input_fingerprints'][str(path)]['sha256'] == expected
    minute, source_audit = local.read_bound_minute_source(MINUTE, MINUTE_SHA, symbol)
    assert minute is not None and source_audit['status'] == 'accepted_source_bytes'
    assert len(minute) == 13050 and source_audit['bytes'] == source[0]['bytes']
    fingerprints[str(MINUTE)] = MINUTE_SHA
    bind(old.MAPPING, preflight['source_fingerprints'][str(old.MAPPING)])
    calendar = pd.DatetimeIndex(pd.to_datetime(sorted(pd.read_csv(old.MAPPING, usecols=['date']).date.unique())))
    grid = old.session_grid(symbol, day, calendar)
    assert len(grid) == 225
    required = grid if kind == 'full_session' else grid[:1]
    assert [t.isoformat() for t in required] == wanted['required_timestamps']
    selected = minute.loc[minute.bar_datetime.isin(grid)].sort_values('bar_datetime').copy()
    empty = selected.iloc[:0].copy()
    qualified, session_audit = local.qualify_needed_session({source[0]['source_id']: minute}, grid, daily, empty, kind)
    assert session_audit['status'] == 'accepted', session_audit
    assert len(selected) == 225 and not selected.bar_datetime.duplicated().any()
    assert list(selected.bar_datetime) == list(grid) and all(legal(r) for r in selected.to_dict('records'))
    completion = []
    for r in selected.itertuples():
        position = integer(r.source_row_number) - 2
        assert position + 1 < len(minute)
        nxt = minute.iloc[position + 1]
        ident, next_id = integer(r.bar_id), integer(nxt.bar_id)
        stamp, next_stamp = pd.Timestamp(r.bar_datetime), pd.Timestamp(nxt.bar_datetime)
        assert str(r.tq_symbol) == str(nxt.tq_symbol) == 'CZCE.SM005'
        assert ident >= 0 and next_id > ident and next_stamp >= stamp + pd.Timedelta(minutes=1) and legal(nxt)
        assert (minute.bar_id == r.bar_id).sum() == (minute.bar_id == nxt.bar_id).sum() == 1
        assert (minute.bar_datetime == stamp).sum() == (minute.bar_datetime == next_stamp).sum() == 1
        completion.append(dict(vt_symbol=symbol, bar_datetime=stamp.isoformat(), source_row_number=position + 2,
            source_bar_id=ident, successor_row_number=position + 3, successor_id=next_id, successor_datetime=next_stamp.isoformat()))
    pd.DataFrame(completion).to_csv(dest / 'completion_evidence.csv', index=False)
    bind(dest / 'completion_evidence.csv')
    delivered = selected.loc[selected.bar_datetime.isin(required), gate.FIELDS].copy()
    assert not old.minute_keys(delivered).has_duplicates and len(delivered) == len(required)
    a0_anchors = old.A0 / 'execution_anchor_requests.csv'
    a0_scans = old.A0 / 'minute_scan_requests.csv'
    bind(a0_anchors, '72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
    bind(a0_scans, 'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
    equivalence = old.prove_read_disjointness(delivered, pd.read_csv(a0_anchors), pd.read_csv(a0_scans), calendar)
    assert equivalence['path_equivalent'] and equivalence['intersection_count'] == 0
    for name, expected in [('stage002_local_minute_overlay.py', '33a30bc1e8f4f970532382da46c2bda790dfb6baac8beeca65abd759a6af50a3'), ('stage021_blocking_data_gate.py', '150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b')]:
        bind(LINE / 'tools' / name, expected)
    bind(LINE / 'tools/stage011_needed_local_completed.py')
    bind(old.PROJECT / 'qmt_roll_intraday_execution.py')
    data_path = dest / 'delivery_minutes.csv'
    delivered.to_csv(data_path, index=False)
    data_sha = bind(data_path)
    key_checks = dict(request_sha256=digest, expected_full_session_minutes=len(grid), delivered_minutes=len(delivered),
        source_audit=source_audit, session_audit=session_audit, all_225_actual_forward_successors_checked=True,
        first_completion=completion[0], last_completion=completion[-1], A0_actual_read_disjointness=equivalence,
        request_scope_existing_physical_keys=0, new_request_scope_physical_keys=len(delivered),
        global_existing_keys_claimed_empty=False, outside_request_mapping_untouched=True,
        old_key_protection='Actual stage021.ensure compares overlap seven values with np.array_equal; adds absent keys only and commits after all symbols pass.',
        no_engine_loaded=True, no_base_cache_reloaded=True, no_source_stack_requalification=True)
    write(dest / 'key_checks.json', key_checks)
    bind(dest / 'key_checks.json')
    receipt = dict(schema=gate.RECEIPT_SCHEMA, independent_review=True, reviewer=REVIEWER,
        reviewed_at=datetime.now().astimezone().isoformat(), qualified_research_data=True, p0_findings=0, p1_findings=0, p2_findings=0,
        request_sha256=digest, accepted_requirements=[dict(vt_symbol=symbol, execution_trade_date=day,
            requirement_kind=kind, accepted=True, completed_bars_and_daily_qualified=True,
            accepted_timestamps=wanted['required_timestamps'])], data_path=str(data_path), data_sha256=data_sha,
        daily_review_receipt_path=str(dest / 'daily_review_receipt.json'),
        daily_review_receipt_sha256=sha(dest / 'daily_review_receipt.json'), source_fingerprints=dict(fingerprints),
        scope='Only this actual request; full225 canonical grid, actual row completion, seven-field daily aggregate; no other day/anchor rights.',
        confidence='high_for_exact_requested_keys; no profitability or global minute quality claim',
        network_connections_in_review=0, new_minute_provider_connections=0, financial_replays=0, model_fits=0,
        orders=0, response_written=False, original_CSV_or_DB_modified=False, production_qualified=False,
        overfitting=False, continued_value=True)
    receipt_path = dest / 'delivery_receipt.json'
    write(receipt_path, receipt)
    # Exercise the genuine parser only. This does not construct or resume an engine.
    parsed, full, anchors, info = gate._read_delivery(request, gate.QualifiedDelivery(receipt_path, sha(receipt_path)))
    assert len(parsed) == len(required) and len(full) == (225 if kind == 'full_session' else 0)
    assert len(anchors) == (1 if kind == 'anchor' else 0) and info['accepted_keys'] == len(required)
    parse = dict(status='actual_stage021_read_delivery_pass', rows=len(parsed), full_keys=len(full), anchor_keys=len(anchors),
        receipt_path=str(receipt_path), receipt_sha256=sha(receipt_path), response_written=False,
        financial_replays=0, network_connections=0, all_bound_inputs_still_unchanged=True)
    assert all(sha(path) == expected for path, expected in fingerprints.items())
    write(dest / 'parse_result.json', parse)
    print(json.dumps(parse, ensure_ascii=False))


if __name__ == '__main__':
    main()
