"""Read-only A0 anchor versus exact real daily-open evidence; no fallback."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
PROJECT = ROOT / 'examples/portfolio_backtesting'
A0 = LINE / 'outputs/stage001_first_screen/A0_attempt2'
OLD = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3'
DATABASE = ROOT / '.vntrader/database.db'
MAPPING = PROJECT / 'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
HELPER = PROJECT / 'qmt_roll_intraday_execution.py'
PROTOCOL = LINE / 'stages/20261017_2323_stage006_daily_open_equivalence_protocol.md'
OUTPUT = LINE / 'outputs/stage006_daily_open_equivalence'
ABSOLUTE_TOLERANCE = 1e-8
RELATIVE_TOLERANCE = 1e-12
sys.path.insert(0, str(PROJECT))
from qmt_roll_intraday_execution import local_timestamp, session_minutes


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def lookup_real_daily_open(database, vt_symbol, trading_date):
    """An absent exact daily row stays absent: no carry or continuous contract."""
    symbol, exchange = vt_symbol.rsplit('.', 1)
    day = local_timestamp(trading_date).normalize()
    end = day + pd.Timedelta(days=1)
    rows = database.execute(
        "SELECT datetime,open_price FROM dbbardata "
        "WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<? "
        "ORDER BY datetime",
        (symbol, exchange, day.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')),
    ).fetchall()
    return [dict(datetime=row[0], open_price=row[1]) for row in rows]


def normalized_offset(value):
    return {'开':'Open', '平':'Close', '平今':'CloseToday', '平昨':'CloseYesterday'}.get(str(value), str(value))


def event_direction(event, orders):
    exact = orders.loc[
        orders.order_id.eq(str(event['order_id']))
        & orders.vt_symbol.eq(str(event['vt_symbol']))
        & orders.trading_date.eq(str(event['trading_date']))
        & orders.offset.map(normalized_offset).eq(normalized_offset(event['offset']))
    ]
    if exact.empty:
        return 'unknown', 'no_exact_order_fields'
    directions = {
        {'多':'Long', '空':'Short', 'Direction.LONG':'Long', 'Direction.SHORT':'Short'}.get(str(value), str(value))
        for value in exact.direction
    }
    if len(directions) != 1 or not directions.issubset({'Long','Short'}):
        return 'unknown', 'conflicting_or_unrecognized_order_fields'
    return directions.pop(), 'exact_order_fields'


def valid_price(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def check_event(event, daily_rows, calendar, direction):
    row = {key:str(event.get(key,'')) for key in [
        'vt_symbol','trading_date','order_id','offset','expected_start','actual_time','source'
    ]}
    row['direction'] = direction
    row['anchor_present'] = str(event.get('anchor_present','')).lower() in {'true','1'}
    row['anchor_price_valid'] = valid_price(event.get('price'))
    row['anchor_price'] = float(event['price']) if row['anchor_price_valid'] else None
    row['daily_row_count'] = len(daily_rows)
    row['daily_datetimes'] = ';'.join(str(item['datetime']) for item in daily_rows)
    row['daily_open_price'] = None
    if not daily_rows:
        row['daily_status'] = 'missing_real_daily_bar'
    elif len(daily_rows) != 1:
        row['daily_status'] = 'duplicate_real_daily_bars'
    elif not valid_price(daily_rows[0]['open_price']):
        row['daily_status'] = 'invalid_real_daily_open'
    else:
        row['daily_status'] = 'unique_valid_real_daily_bar'
        row['daily_open_price'] = float(daily_rows[0]['open_price'])
    row['absolute_price_difference'] = None
    row['price_exact_match'] = False
    row['price_tolerance_match'] = False
    if row['anchor_price_valid'] and row['daily_status'] == 'unique_valid_real_daily_bar':
        row['absolute_price_difference'] = abs(row['anchor_price'] - row['daily_open_price'])
        row['price_exact_match'] = row['anchor_price'] == row['daily_open_price']
        row['price_tolerance_match'] = math.isclose(row['anchor_price'], row['daily_open_price'],
            rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE)
    row['helper_session_start'] = ''
    row['expected_start_match'] = False
    row['physical_time_match'] = False
    row['session_error'] = ''
    try:
        start = session_minutes(row['vt_symbol'], row['trading_date'], calendar)[0]
        row['helper_session_start'] = start.isoformat()
        row['expected_start_match'] = local_timestamp(row['expected_start']) == start
        row['physical_time_match'] = local_timestamp(row['actual_time']) == start
    except (ValueError, TypeError, IndexError) as error:
        row['session_error'] = f'{type(error).__name__}:{error}'
    row['canonical_anchor_source'] = row['source'] == 'canonical_session_first_minute_open'
    row['equivalent'] = bool(row['daily_status'] == 'unique_valid_real_daily_bar'
        and row['price_tolerance_match'] and row['anchor_present'] and row['canonical_anchor_source']
        and row['expected_start_match'] and row['physical_time_match'] and not row['session_error'])
    issues = []
    if row['daily_status'] != 'unique_valid_real_daily_bar': issues.append(row['daily_status'])
    if not row['anchor_price_valid']: issues.append('invalid_anchor_price')
    if row['absolute_price_difference'] is not None and not row['price_tolerance_match']: issues.append('price_difference')
    for key in ['anchor_present','canonical_anchor_source','expected_start_match','physical_time_match']:
        if not row[key]: issues.append(key + '_false')
    if row['session_error']: issues.append('session_error')
    row['anomaly_reason'] = ';'.join(issues)
    return row


def aggregate(frame):
    comparable = frame.daily_status.eq('unique_valid_real_daily_bar') & frame.anchor_price_valid
    differences = frame.loc[comparable,'absolute_price_difference']
    return dict(events=len(frame), unique_real_daily_bars=int(frame.daily_status.eq('unique_valid_real_daily_bar').sum()),
        missing_real_daily_bars=int(frame.daily_status.eq('missing_real_daily_bar').sum()),
        duplicate_real_daily_bars=int(frame.daily_status.eq('duplicate_real_daily_bars').sum()),
        invalid_real_daily_opens=int(frame.daily_status.eq('invalid_real_daily_open').sum()),
        invalid_anchor_prices=int((~frame.anchor_price_valid).sum()),
        price_exact_matches=int(frame.price_exact_match.sum()),
        price_tolerance_matches=int(frame.price_tolerance_match.sum()),
        price_differences_outside_tolerance=int((comparable & ~frame.price_tolerance_match).sum()),
        physical_time_matches=int(frame.physical_time_match.sum()),
        expected_start_matches=int(frame.expected_start_match.sum()),
        direction_unknown=int(frame.direction.eq('unknown').sum()),
        equivalent_events=int(frame.equivalent.sum()),
        max_absolute_price_difference=float(differences.max()) if len(differences) else None)


def audit():
    if OUTPUT.exists():
        raise FileExistsError('existing_daily_open_audit_refusing_repeat')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write_json(OUTPUT/'attempt_started.json', dict(started_at=datetime.now().astimezone().isoformat(),
        financial_replays=0, downloads=0, execution_fallback_enabled=False))
    try:
        wal = Path(str(DATABASE) + '-wal')
        if wal.exists() and wal.stat().st_size:
            raise ValueError('nonempty_database_WAL_refusing_audit')
        paths = [DATABASE,MAPPING,HELPER,PROTOCOL,Path(__file__),A0/'execution_anchor_requests.csv',
            A0/'trades.csv',A0/'input_manifest.json',OLD/'input_manifest.json']
        inputs = {str(path):sha256(path) for path in paths}
        a0_manifest = json.loads((A0/'input_manifest.json').read_text())
        old_manifest = json.loads((OLD/'input_manifest.json').read_text())
        for path in [DATABASE,MAPPING]:
            if inputs[str(path)] != old_manifest.get(str(path.relative_to(ROOT))):
                raise ValueError(f'accepted_original_input_changed:{path.name}')
        for path in [DATABASE,MAPPING,HELPER]:
            if inputs[str(path)] != a0_manifest[str(path)]['sha256']:
                raise ValueError(f'accepted_A0_input_changed:{path.name}')
        anchors = pd.read_csv(A0/'execution_anchor_requests.csv', dtype=str, keep_default_na=False)
        if len(anchors) != 535:
            raise ValueError(f'accepted_anchor_count_changed:{len(anchors)}')
        # These five order fields contain no equity, return, realized PnL or outcome columns.
        orders = pd.read_csv(A0/'trades.csv', usecols=['order_id','vt_symbol','direction','offset','trading_date'],
            dtype=str, keep_default_na=False)
        calendar = pd.DatetimeIndex(sorted(pd.to_datetime(pd.read_csv(MAPPING,usecols=['date']).date).unique()))
        cache = {}; checks = []
        # immutable prevents even journal side effects; a nonempty WAL was explicitly rejected.
        with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro&immutable=1', uri=True) as database:
            for number,event in enumerate(anchors.to_dict('records'), start=1):
                key = event['vt_symbol'], event['trading_date']
                if key not in cache:
                    cache[key] = lookup_real_daily_open(database, *key)
                direction, direction_source = event_direction(event, orders)
                row = check_event(event, cache[key], calendar, direction)
                row['event_number'] = number
                row['direction_source'] = direction_source
                if direction_source != 'exact_order_fields':
                    row['anomaly_reason'] = ';'.join(filter(None,[row['anomaly_reason'],direction_source]))
                checks.append(row)
        frame = pd.DataFrame(checks)
        frame.to_csv(OUTPUT/'event_checks.csv', index=False)
        frame.loc[frame.anomaly_reason.ne('')].to_csv(OUTPUT/'anomalies.csv', index=False)
        unchanged = all(sha256(path) == value for path,value in inputs.items())
        if not unchanged:
            raise ValueError('input_changed_during_readonly_audit')
        if wal.exists() and wal.stat().st_size:
            raise ValueError('nonempty_database_WAL_after_audit')
        write_json(OUTPUT/'input_manifest.json', inputs)
        result = dict(status='completed_data_equivalence_audit_pending_independent_review',
            elapsed_seconds=time.monotonic()-started, source_code_sha256=inputs[str(Path(__file__))],
            protocol_sha256=inputs[str(PROTOCOL)], all_inputs_unchanged=unchanged,
            financial_replays=0, downloads=0, model_fits=0, source_writes=0,
            pnl_columns_read=0, execution_fallback_enabled=False, production_qualified=False,
            unique_daily_keys_queried=len(cache), real_daily_records_read=sum(len(value)for value in cache.values()),
            daily_fields_selected=['datetime','open_price'],
            order_fields_selected=['order_id','vt_symbol','direction','offset','trading_date'],
            tolerance=dict(absolute=ABSOLUTE_TOLERANCE,relative=RELATIVE_TOLERANCE), overall=aggregate(frame),
            by_offset=[dict(offset=key,**aggregate(group)) for key,group in frame.groupby('offset',sort=True)],
            by_direction=[dict(direction=key,**aggregate(group)) for key,group in frame.groupby('direction',sort=True)],
            by_offset_direction=[dict(offset=offset,direction=direction,**aggregate(group))
                for (offset,direction),group in frame.groupby(['offset','direction'],sort=True)],
            limitations=[
                'Only the fixed 535 accepted A0 events, not all possible candidate paths.',
                'Real daily open equivalence cannot replace intraday stop/limit order sequence or generate synthetic minute OHLCVOI.',
                'Missing or duplicate exact real bars fail equivalence; no carry or other contract substituted.',
                'No execution contract or source fallback has been authorized or implemented.',
                'This does not prove gap sizing, time visibility, liquidity or real fill feasibility.',
            ])
        result['artifact_sha256']={path.name:sha256(path)for path in OUTPUT.iterdir()if path.is_file()}
        write_json(OUTPUT/'data_open_equivalence.json', result)
        print(json.dumps(dict(status=result['status'],**result['overall']),ensure_ascii=False))
    except BaseException as error:
        write_json(OUTPUT/'audit_failure.json',dict(error_type=type(error).__name__,error=str(error),
            financial_replays=0, downloads=0, execution_fallback_enabled=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', action='store_true', required=True)
    parser.parse_args()
    audit()
