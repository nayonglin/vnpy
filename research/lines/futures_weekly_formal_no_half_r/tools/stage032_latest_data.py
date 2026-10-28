"""Stage032 immutable daily-only extension of Stage029; never a strategy replay.

10/27 authority: existing hash-bound local Stage283 Tq daily close_oi snapshot.
10/28 authority: a new completed-day Tq snapshot, original raw serial retained.
No old key is replaced, no CTP/order API is permitted, no minute data is used.
"""
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo
import argparse
import contextlib
import hashlib
import io
import json
import logging
import math
import os
import re
import shutil
import signal
import sqlite3
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_weekly_formal_no_half_r'
BASE = LINE / 'outputs/stage029_latest_data/data_approved'
OUT = LINE / 'outputs/stage032_latest_data'
LOCAL = Path('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage283_no_ai_long_15m_addon/data')
LOCAL_TOOL = LOCAL.parents[2] / 'tools/stage283_prepare_data.py'
TZ = ZoneInfo('Asia/Shanghai')
APPEND_DAYS = ['2026-10-27', '2026-10-28']
TARGET = APPEND_DAYS[-1]
FIELDS = ['open', 'high', 'low', 'close', 'volume', 'close_oi']
AUTHORITY = 'stage032_predeclared_Tq_daily_only_close_oi'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path = Path(path)
    tmp = Path(str(path) + '.pending')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n')
    os.replace(tmp, path)


def epoch_for(symbol, day, epochs):
    choices = [r for r in epochs if str(r['vt_symbol']) == symbol
               and (not r.get('listed_date') or r['listed_date'] <= day)
               and (not r.get('delisted_date') or day <= r['delisted_date'])]
    if len(choices) != 1:
        raise ValueError('physical_identity_not_unique:' + symbol + ':' + day)
    row = choices[0]
    code, exchange = symbol.split('.')
    match = re.fullmatch(r'([A-Za-z]+)(\d{3,4})', code)
    month = str(row['contract_yyyymm'])
    if not match or not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])', month):
        raise ValueError('physical_month_invalid:' + symbol)
    if month[-(3 if exchange == 'CZCE' else 4):] != match[2]:
        raise ValueError('physical_month_mismatch:' + symbol)
    if row['contract_epoch_id'] != exchange + '.' + match[1].upper() + '.' + month:
        raise ValueError('physical_epoch_id_mismatch:' + symbol)
    return row


def admit_rows(rows, epochs, append_days):
    accepted, rejected, seen = [], [], set()
    for source in rows:
        row = dict(source)
        key = (row['vt_symbol'], row['date'])
        if key in seen:
            raise ValueError('duplicate_new_daily:' + repr(key))
        seen.add(key)
        if row['date'] not in append_days:
            raise ValueError('outside_predeclared_append_days:' + repr(key))
        if int(row.get('duration', 0)) != 86400:
            raise ValueError('not_real_daily:' + repr(key))
        if any(not row.get(k) for k in ['source_id', 'source_path', 'source_sha256', 'source_locator']):
            raise ValueError('daily_provenance_missing:' + repr(key))
        if 'close_oi' not in row:
            raise ValueError('same_day_close_oi_missing:' + repr(key))
        ep = epoch_for(*key, epochs)
        try:
            values = {k: float(row[k]) for k in FIELDS}
            o, h, low, close, volume, oi = (values[k] for k in FIELDS)
            valid = (all(math.isfinite(x) for x in values.values())
                     and min(o, h, low, close, volume) > 0 and oi >= 0
                     and low <= min(o, close) and h >= max(o, close) and low <= h)
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            rejected.append(dict(vt_symbol=key[0], date=key[1], classification='raw_zero_or_invalid_not_bar',
                                 source_path=row['source_path'], source_sha256=row['source_sha256'],
                                 source_locator=row['source_locator']))
            continue
        accepted.append(dict(vt_symbol=key[0], date=key[1], contract_epoch_id=ep['contract_epoch_id'],
                             contract_yyyymm=ep['contract_yyyymm'], **values,
                             source_id=row['source_id'], source_path=row['source_path'],
                             source_sha256=row['source_sha256'], source_locator=row['source_locator'],
                             lifecycle_status=ep['lifecycle_status'],
                             admission_reason='predeclared_completed_daily_extension_only'))
    return accepted, rejected


def validate_mapping(mapping, products, days):
    keys = set(zip(mapping.date.astype(str), mapping.continuous_symbol_vt.astype(str)))
    wanted = {(d, p) for d in days for p in products}
    if len(mapping) != len(wanted) or mapping.duplicated(['date', 'continuous_symbol_vt']).any() or keys != wanted:
        raise ValueError('new_main_mapping_incomplete_duplicate_or_outside_universe')
    if mapping.main_contract_vt.fillna('').eq('').any():
        raise ValueError('empty_new_main_contract')
    for r in mapping.itertuples():
        product = re.sub(r'\d+(?=\.)', '', r.main_contract_vt)
        if product != r.continuous_symbol_vt:
            raise ValueError('main_contract_product_identity_mismatch')


def require_daily_keys(rows, required):
    keys = {(r['vt_symbol'], r['date']) for r in rows}
    missing = sorted(required - keys)
    if missing:
        raise ValueError('required_physical_daily_missing:' + repr(missing))


def append_sqlite(base, target, rows):
    base, target = Path(base), Path(target)
    if target.exists():
        raise ValueError('immutable_snapshot_exists:' + str(target))
    before = sha(base)
    shutil.copyfile(base, target)
    with sqlite3.connect(target) as db:
        for row in rows:
            code, exchange = row['vt_symbol'].split('.')
            old = db.execute("select count(*) from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",
                             (code, exchange, row['date'])).fetchone()[0]
            if old:
                raise ValueError('new_key_already_in_database:' + row['vt_symbol'] + ':' + row['date'])
            db.execute("insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,'d',?,0,?,?,?,?,?)",
                       (code, exchange, row['date'] + ' 00:00:00', row['volume'], row['close_oi'],
                        row['open'], row['high'], row['low'], row['close']))
        for symbol in sorted({r['vt_symbol'] for r in rows}):
            code, exchange = symbol.split('.')
            count, begin, end = db.execute("select count(*),min(datetime),max(datetime) from dbbardata where symbol=? and exchange=? and interval='d'", (code, exchange)).fetchone()
            db.execute("delete from dbbaroverview where symbol=? and exchange=? and interval='d'", (code, exchange))
            db.execute("insert into dbbaroverview(symbol,exchange,interval,count,start,end) values(?,?,'d',?,?,?)", (code, exchange, count, begin, end))
        db.commit()
        if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError('snapshot_integrity_failed')
        db.execute('attach database ? as frozen', (str(base),))
        old_count = db.execute('select count(*) from frozen.dbbardata').fetchone()[0]
        new_count = db.execute('select count(*) from main.dbbardata').fetchone()[0]
        missing = db.execute('select count(*) from (select * from frozen.dbbardata except select * from main.dbbardata)').fetchone()[0]
        if missing or new_count != old_count + len(rows):
            raise ValueError('old_database_rows_changed')
        for row in rows:
            code, exchange = row['vt_symbol'].split('.')
            actual = db.execute("select open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?", (code, exchange, row['date'])).fetchall()
            if actual != [tuple(row[k] for k in FIELDS)]:
                raise ValueError('new_database_field_parity_failed')
    if sha(base) != before:
        raise ValueError('base_database_changed')
    return dict(old_database_all_rows_preserved=True, old_database_rows=old_count,
                new_database_rows=new_count, new_database_field_parity=True,
                snapshot_integrity='ok', base_database_sha256=before)


def frozen_inputs():
    receipt = json.loads((BASE / 'receipt.json').read_text())
    if not receipt['data_ready_for_bounded_replay'] or receipt['date_end'] != '2026-10-26' or len(receipt['products']) != 19:
        raise ValueError('base_approved_snapshot_not_ready')
    prior = json.loads((BASE / 'source_manifest.json').read_text())['files']
    selected = [BASE / n for n in ['daily.sqlite', 'physical_epoch_daily.csv', 'physical_epochs.csv', 'metadata.csv', 'mapping.csv', 'receipt.json']]
    for path in selected:
        if prior.get(str(path)) != sha(path):
            raise ValueError('base_snapshot_hash_changed:' + str(path))
    local_manifest = json.loads((LOCAL / 'data_manifest.json').read_text())
    if local_manifest['status'] != 'latest_daily_mapping_ready' or local_manifest['target_end'] != '2026-10-27':
        raise ValueError('local_27_source_not_ready')
    for name in ['latest_daily', 'latest_mapping']:
        path = LOCAL / (name + '.csv')
        if sha(path) != local_manifest[name + '_sha256']:
            raise ValueError('local_27_source_hash_changed:' + name)
    # The local source writer explicitly maps close_oi to open_interest; bind it.
    if sha(LOCAL_TOOL) != local_manifest['adapter_sha256']:
        raise ValueError('local_27_adapter_changed')
    selected += [BASE / 'source_manifest.json', LOCAL / 'data_manifest.json', LOCAL / 'latest_daily.csv', LOCAL / 'latest_mapping.csv', LOCAL_TOOL, Path(__file__), Path(__file__).with_name('test_stage032_latest_data.py')]
    selected += [LINE / 'outputs/R_attempt003' / n for n in ['preflight.json', 'positions.csv', 'pending_orders.csv', 'effective_parameters.json']]
    return {str(p): sha(p) for p in selected}


def local_rows():
    data = pd.read_csv(LOCAL / 'latest_daily.csv')
    rows = []
    for index, row in data.loc[data.date.eq(APPEND_DAYS[0])].iterrows():
        rows.append(dict(vt_symbol=row.vt_symbol, date=row.date, open=row.open_price,
                         high=row.high_price, low=row.low_price, close=row.close_price,
                         volume=row.volume, close_oi=row.open_interest, duration=86400,
                         source_id=AUTHORITY + '_local_stage283_20261027',
                         source_path=str(LOCAL / 'latest_daily.csv'), source_sha256=sha(LOCAL / 'latest_daily.csv'),
                         source_locator=json.dumps({'data_row_index': int(index), 'date': row.date, 'vt_symbol': row.vt_symbol, 'field_origin': 'Tq daily close_oi renamed open_interest by bound adapter'})))
    return rows


def probe(probe_dir, inputs):
    probe_dir.mkdir(parents=True, exist_ok=False)
    (probe_dir / 'raw_daily').mkdir()
    receipt = dict(schema='stage032_daily_probe_v1', status='started', started_at=datetime.now(TZ).isoformat(),
                   target_date=TARGET, append_days=APPEND_DAYS, financial_replays=0, minute_reads=0,
                   ctp_connected=False, guards=dict(insert_order_calls=0, cancel_order_calls=0),
                   source_authority=AUTHORITY, source_consensus_claim=False, inputs_before=inputs)
    dump(probe_dir / 'progress.json', receipt)
    api = None
    stage = 'preflight'
    old_logging = logging.root.manager.disable
    old_signal = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('stage032_vendor_budget_120_seconds')))
    try:
        if datetime.now(TZ) < datetime(2026, 10, 28, 15, 30, tzinfo=TZ):
            raise ValueError('target_day_not_completed')
        os.environ.update(TZ='Asia/Shanghai', OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0', OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0')
        time.tzset()
        logging.disable(logging.CRITICAL)
        signal.alarm(120)
        products = json.loads((BASE / 'receipt.json').read_text())['products']
        epochs = pd.read_csv(BASE / 'physical_epochs.csv', dtype=str).fillna('').to_dict('records')
        stage = 'authentication_fresh_main_calendar'
        # Local credentials stay in memory and are never placed in receipts/logs.
        credentials = json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from tqsdk import TqApi, TqAuth, TqSim
            from tqsdk.calendar import TqContCalendar
            import requests
            auth = TqAuth(credentials['datafeed.username'], credentials['datafeed.password'])
            auth.login()
            response = requests.get('https://files.shinnytech.com/continuous_table.json', headers=auth._base_headers, timeout=25)
            response.raise_for_status()
            raw_path = probe_dir / 'fresh_main_continuous_table.raw.json'
            raw_path.write_bytes(response.content)
            TqContCalendar.continuous = {'KQ.m@' + key: value for key, value in response.json().items()}
            symbols = ['KQ.m@' + p.split('.')[1] + '.' + p.split('.')[0] for p in products]
            calendar = TqContCalendar(start_dt=date(2026, 10, 26), end_dt=date(2026, 10, 30), symbols=symbols, headers=auth._base_headers)
        calendar.df.to_csv(probe_dir / 'fresh_calendar_raw.csv', index=False)
        dump(probe_dir / 'fresh_mapping_source_receipt.json', dict(source_url='https://files.shinnytech.com/continuous_table.json', response_body_path=str(raw_path), response_body_sha256=sha(raw_path), captured_at=datetime.now(TZ).isoformat(), not_a_PIT_claim=True))
        mapping_rows = []
        for row in calendar.df.to_dict('records'):
            day = str(row['date'])[:10]
            for product, key in zip(products, symbols):
                value = '' if pd.isna(row.get(key)) else str(row[key])
                if not value or '.' not in value:
                    raise ValueError('fresh_mapping_missing:' + product + ':' + day)
                exchange, code = value.split('.', 1)
                mapping_rows.append(dict(date=day, product=product.split('.')[0], exchange=product.split('.')[1], continuous_symbol_tq=key, continuous_symbol_vt=product, main_contract_tq=value, main_contract_vt=code + '.' + exchange))
        fresh = pd.DataFrame(mapping_rows)
        fresh.to_csv(probe_dir / 'fresh_mapping_probe.csv', index=False)
        new_mapping = fresh.loc[fresh.date.isin(APPEND_DAYS)].copy()
        validate_mapping(new_mapping, products, APPEND_DAYS)
        base_map = pd.read_csv(BASE / 'mapping.csv').fillna('')
        old_latest = base_map.loc[base_map.date.eq('2026-10-26')]
        local_map = pd.read_csv(LOCAL / 'latest_mapping.csv').fillna('')
        before_map = pd.concat([old_latest, local_map.loc[local_map.date.eq('2026-10-27')]])
        overlap = before_map.merge(fresh, on=['date', 'continuous_symbol_vt'], suffixes=('_frozen', '_fresh'))
        overlap['same_main_contract'] = overlap.main_contract_vt_frozen.eq(overlap.main_contract_vt_fresh)
        overlap.to_csv(probe_dir / 'mapping_overlap_20261026_27.csv', index=False)
        if len(overlap) != 38 or not overlap.same_main_contract.all():
            raise ValueError('frozen_mapping_response_changed')
        old_daily = pd.read_csv(BASE / 'physical_epoch_daily.csv')
        recent_symbols = set(old_daily.loc[old_daily.date.eq('2026-10-26'), 'vt_symbol'])
        held = pd.read_csv(LINE / 'outputs/R_attempt003/positions.csv')
        held_symbols = set(held.loc[held.date.eq(held.date.max()) & held.end_pos.ne(0), 'vt_symbol'])
        pending = set(pd.read_csv(LINE / 'outputs/R_attempt003/pending_orders.csv').vt_symbol)
        wanted = sorted(recent_symbols | set(new_mapping.main_contract_vt) | held_symbols | pending)
        if len(wanted) > 48:
            raise ValueError('declared_contract_budget_exceeded')
        old_mapped = set(base_map.main_contract_vt)
        new_symbols = sorted(set(new_mapping.main_contract_vt) - old_mapped)
        if new_symbols:
            raise ValueError('new_contract_metadata_requires_explicit_admission:' + repr(new_symbols))
        for symbol in wanted:
            if re.sub(r'\d+(?=\.)', '', symbol) not in products:
                raise ValueError('contract_outside_original19')
            for day in APPEND_DAYS:
                epoch_for(symbol, day, epochs)
        selection = dict(recent_accepted_tail=sorted(recent_symbols), frozen_terminal_positions=sorted(held_symbols), frozen_pending_contracts=sorted(pending), requested_contracts=wanted, contract_count=len(wanted), selection_uses_strategy_profit=False, new_metadata_symbols=new_symbols, new_physical_epochs=[])
        dump(probe_dir / 'selection.json', selection)
        new_mapping.to_csv(probe_dir / 'new_mapping.csv', index=False)
        stage = 'daily_serials'
        def forbidden(key):
            def blocked(*args, **kwargs):
                receipt['guards'][key] += 1
                raise RuntimeError('order_api_forbidden')
            return blocked
        TqApi.insert_order = forbidden('insert_order_calls')
        TqApi.cancel_order = forbidden('cancel_order_calls')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            api = TqApi(TqSim(), auth=auth, disable_print=True, debug=False)
            serials = {}
            async def subscribe():
                for symbol in wanted:
                    code, exchange = symbol.split('.')
                    serials[symbol] = api.get_kline_serial(exchange + '.' + code, 86400, data_length=30)
            api.create_task(subscribe())
            while len(serials) != len(wanted) or not all(api.is_serial_ready(s) for s in serials.values()):
                api.wait_update(deadline=time.time() + 1)
        records, statuses, observed_overlap = [], [], []
        local = local_rows()
        local_lookup = {(r['vt_symbol'], r['date']): r for r in local}
        for symbol, serial in sorted(serials.items()):
            raw = serial.copy()
            path = probe_dir / 'raw_daily' / (symbol + '.csv')
            raw.to_csv(path, index=False)
            digest = sha(path)
            filtered = raw.loc[pd.to_numeric(raw.datetime).gt(0) & pd.to_numeric(raw.id).ge(0)].copy()
            filtered['date'] = pd.to_datetime(pd.to_numeric(filtered.datetime), unit='ns', utc=True).dt.tz_convert(TZ).dt.strftime('%Y-%m-%d')
            if filtered.date.duplicated().any():
                raise ValueError('duplicate_raw_daily:' + symbol)
            if 'duration' not in filtered:
                raise ValueError('raw_daily_duration_missing:' + symbol)
            for row in filtered.loc[filtered.date.eq(TARGET)].to_dict('records'):
                records.append(dict(vt_symbol=symbol, date=row['date'], **{f: row[f] for f in FIELDS}, duration=row['duration'], source_id=AUTHORITY + '_fresh_20261028', source_path=str(path), source_sha256=digest, source_locator=json.dumps({'date': row['date'], 'id': row['id'], 'datetime_ns': row['datetime']})))
            for row in filtered.loc[filtered.date.eq(APPEND_DAYS[0])].to_dict('records'):
                frozen = local_lookup.get((symbol, row['date']))
                if frozen:
                    differences = {f: dict(frozen=float(frozen[f]), fresh=float(row[f])) for f in FIELDS if float(frozen[f]) != float(row[f])}
                    observed_overlap.append(dict(vt_symbol=symbol, date=row['date'], frozen_authority_preserved=True, differences=differences))
            statuses.append(dict(vt_symbol=symbol, raw_path=str(path), raw_sha256=digest, raw_rows=len(raw), target_rows=int(filtered.date.eq(TARGET).sum()), excluded_future_forming_rows=int(filtered.date.gt(TARGET).sum())))
        dump(probe_dir / 'frozen_27_overlap_observations.json', observed_overlap)
        dump(probe_dir / 'new_rows.json', local + records)
        signal.alarm(0)
        future = sorted(fresh.loc[fresh.date.gt(TARGET), 'date'].unique())
        if not future:
            raise ValueError('future_calendar_missing')
        receipt.update(status='raw_daily_probe_ready', next_trading_date=future[0], contract_statuses=statuses,
                       source_cutoffs={'local_stage283': APPEND_DAYS[0], 'fresh_probe': TARGET},
                       target_is_completed_week=False, weekly_boundary_reason='10/28 Wednesday; 10/29 exists in fresh trading calendar',
                       metadata_admission=selection, contract_count=len(wanted))
    except Exception as exc:
        # Never persist exception text from authentication/network libraries.
        error = str(exc) if isinstance(exc, ValueError) else None
        receipt.update(status='failed_probe', failure_stage=stage, error_type=type(exc).__name__, data_gate_detail=error)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_signal)
        if api is not None:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                api.close()
        logging.disable(old_logging)
        changed = [p for p, digest in inputs.items() if not Path(p).is_file() or sha(p) != digest]
        receipt.update(original_inputs_unchanged=not changed, changed_inputs=changed, completed_at=datetime.now(TZ).isoformat())
        if changed:
            receipt['status'] = 'REJECT_FROZEN_INPUT_CHANGED'
        dump(probe_dir / 'probe_receipt.json', receipt)
    return receipt


def assemble(probe_dir, inputs):
    probe_receipt = json.loads((probe_dir / 'probe_receipt.json').read_text())
    if probe_receipt['status'] != 'raw_daily_probe_ready' or not probe_receipt['original_inputs_unchanged']:
        raise ValueError('probe_not_ready')
    if any(sha(p) != digest for p, digest in inputs.items()):
        raise ValueError('frozen_inputs_changed_before_assembly')
    target = OUT / 'data_approved'
    if target.exists():
        raise ValueError('immutable_snapshot_exists')
    base_receipt = json.loads((BASE / 'receipt.json').read_text())
    epochs = pd.read_csv(BASE / 'physical_epochs.csv', dtype=str).fillna('').to_dict('records')
    raw_rows = json.loads((probe_dir / 'new_rows.json').read_text())
    for row in raw_rows:
        if sha(row['source_path']) != row['source_sha256']:
            raise ValueError('new_row_source_changed')
    accepted, rejected = admit_rows(raw_rows, epochs, set(APPEND_DAYS))
    mapping = pd.read_csv(probe_dir / 'new_mapping.csv', dtype=str).fillna('')
    validate_mapping(mapping, base_receipt['products'], APPEND_DAYS)
    required = set(zip(mapping.main_contract_vt, mapping.date))
    selection = probe_receipt['metadata_admission']
    required |= {(symbol, day) for symbol in selection['frozen_terminal_positions'] + selection['frozen_pending_contracts'] for day in APPEND_DAYS}
    require_daily_keys(accepted, required)
    old = pd.read_csv(BASE / 'physical_epoch_daily.csv', dtype=str).fillna('')
    old_keys = set(zip(old.vt_symbol, old.date))
    if any((r['vt_symbol'], r['date']) in old_keys for r in accepted):
        raise ValueError('attempt_to_replace_approved_daily')
    new = pd.DataFrame(accepted, columns=old.columns).sort_values(['date', 'vt_symbol'])
    target.mkdir()
    for name in ['metadata.csv', 'physical_epochs.csv', 'known_lifecycle_excluded.csv', 'known_no_trade_main.csv', 'structural_unavailable_main.csv', 'warmup_missing_main_2014.csv']:
        shutil.copyfile(BASE / name, target / name)
    old_daily_bytes = (BASE / 'physical_epoch_daily.csv').read_bytes()
    old_mapping_bytes = (BASE / 'mapping.csv').read_bytes()
    if not old_daily_bytes.endswith(b'\n') or not old_mapping_bytes.endswith(b'\n'):
        raise ValueError('base_csv_no_terminal_newline')
    (target / 'physical_epoch_daily.csv').write_bytes(old_daily_bytes + new.to_csv(index=False, header=False).encode())
    mapping = mapping[list(pd.read_csv(BASE / 'mapping.csv', nrows=0).columns)].sort_values(['date', 'continuous_symbol_vt'])
    (target / 'mapping.csv').write_bytes(old_mapping_bytes + mapping.to_csv(index=False, header=False).encode())
    new.to_csv(target / 'admitted_new_daily.csv', index=False)
    mapping.to_csv(target / 'admitted_new_mapping.csv', index=False)
    pd.DataFrame(rejected, columns=['vt_symbol', 'date', 'classification', 'source_path', 'source_sha256', 'source_locator']).to_csv(target / 'new_missing_or_zero_not_bar.csv', index=False)
    pd.DataFrame(columns=['date', 'main_contract_vt', 'reason']).to_csv(target / 'missing_main.csv', index=False)
    db_proof = append_sqlite(BASE / 'daily.sqlite', target / 'daily.sqlite', accepted)
    merged = pd.read_csv(target / 'physical_epoch_daily.csv', dtype=str).fillna('')
    prefix = merged.iloc[:len(old)].reset_index(drop=True).equals(old.reset_index(drop=True))
    if not prefix or merged.duplicated(['vt_symbol', 'date']).any():
        raise ValueError('old_daily_fields_or_new_keys_changed')
    proof = dict(**db_proof, old_accepted_rows=len(old), new_accepted_rows=len(new), accepted_rows=len(merged),
                 old_physical_rows_all_fields_exact=prefix, old_physical_csv_bytes_prefix_exact=True,
                 old_mapping_bytes_prefix_exact=True, old_mapping_rows_all_fields_exact=True,
                 metadata_bytes_unchanged=sha(BASE / 'metadata.csv') == sha(target / 'metadata.csv'),
                 physical_epochs_bytes_unchanged=sha(BASE / 'physical_epochs.csv') == sha(target / 'physical_epochs.csv'),
                 required_main_and_frozen_held_pending_key_count=len(required), required_keys_missing=0,
                 new_daily_rows_by_day=new.groupby('date').size().to_dict(),
                 source_authority=AUTHORITY, no_price_or_date_fallback=True)
    dump(target / 'additive_preservation_proof.json', proof)
    metadata = dict(accepted=True, basis='R003 existing mapped contract schema and physical_epochs; no new symbol required',
                    new_metadata_symbols=selection['new_metadata_symbols'], new_physical_epochs=selection['new_physical_epochs'],
                    metadata_bytes_unchanged=proof['metadata_bytes_unchanged'], physical_epochs_bytes_unchanged=proof['physical_epochs_bytes_unchanged'],
                    admitted_contracts=sorted(set(new.vt_symbol)), old_metadata_path=str(BASE / 'metadata.csv'), old_metadata_sha256=sha(BASE / 'metadata.csv'))
    dump(target / 'metadata_admission.json', metadata)
    changed = [p for p, digest in inputs.items() if sha(p) != digest]
    if changed:
        raise ValueError('frozen_inputs_changed_after_assembly')
    receipt = {**base_receipt, 'schema': 'stage032_additive_history_data_receipt_v1', 'status': 'prepared_additive_Tq_daily_20261028',
               'date_end': TARGET, 'financial_start': '2020-01-01', 'requested_financial_end': TARGET,
               'data_ready': True, 'data_ready_for_bounded_replay': True, 'accepted_rows': len(merged),
               'base_data_directory': str(BASE), 'base_receipt_sha256': sha(BASE / 'receipt.json'),
               'base_source_manifest_sha256': sha(BASE / 'source_manifest.json'), 'latest_probe_directory': str(probe_dir),
               'latest_probe_receipt_sha256': sha(probe_dir / 'probe_receipt.json'), 'source_authority': AUTHORITY,
               'source_consensus_claim': False, 'latest_day_is_completed_week': False,
               'next_trading_date': probe_receipt['next_trading_date'], 'new_data': proof,
               'new_metadata_symbols': metadata['new_metadata_symbols'], 'new_physical_epochs': metadata['new_physical_epochs'],
               'metadata_admission_path': str(target / 'metadata_admission.json'), 'metadata_admission_sha256': sha(target / 'metadata_admission.json'),
               'completed_at': datetime.now(TZ).isoformat(), 'original_inputs_unchanged': True,
               'financial_replays': 0, 'production_accesses': 0, 'ctp_connected': False, 'order_api_calls': 0,
               'promotion_decision': 'NO_PROMOTION',
               'inherited_base_limitations': base_receipt['readiness_limitations'],
               'inherited_limitations_policy': 'Historical Stage029 scope retained above; its 10/26-only addition restriction is superseded by the explicit Stage032 10/27-28 append contract.',
               'readiness_limitations': [text for text in base_receipt['readiness_limitations']
                                        if not text.startswith('Only 10/26') and not text.startswith('10/26 is an incomplete')] + [
                   '10/27 local Stage283 daily closeOI snapshot is the predeclared authority; later same-vendor observations do not overwrite it.',
                   '10/28 Tq daily is observed after 15:30 local, not independently arbitrated exchange final truth.',
                   '10/28 is incomplete week; ordinary weekly indicators use completed weeks only.',
                   'Data readiness covers original19 main plus frozen R003 held/pending and accepted recent tails; each new replay must still verify every actual held/traded day and 2020 warmup readiness.'
               ]}
    dump(target / 'receipt.json', receipt)
    files = dict(json.loads((BASE / 'source_manifest.json').read_text())['files'])
    files.update(inputs)
    for path in [*probe_dir.rglob('*'), *target.rglob('*')]:
        if path.is_file():
            files[str(path)] = sha(path)
    dump(target / 'source_manifest.json', dict(schema='stage032_history_source_manifest_v1', files=files,
         source_manifest_self_not_in_files=True, immutable_output=True, financial_replays=0,
         new_source_input_count=len(inputs), generated_at=datetime.now(TZ).isoformat()))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--assemble-only', action='store_true')
    parser.add_argument('--attempt', default='001')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = frozen_inputs()
    attempt = OUT / ('probe_attempt' + args.attempt)
    if not args.download and not args.assemble_only:
        print(json.dumps(dict(status='plan_only', base=str(BASE), target=str(OUT / 'data_approved'), append_days=APPEND_DAYS, target_end=TARGET, financial_start='2020-01-01', frozen_inputs=len(inputs), new_market_downloads=0)))
        return 0
    if args.download:
        result = probe(attempt, inputs)
        if result['status'] != 'raw_daily_probe_ready':
            print(json.dumps({k: result.get(k) for k in ['status', 'failure_stage', 'error_type', 'data_gate_detail', 'original_inputs_unchanged']}, ensure_ascii=False))
            return 1
    try:
        result = assemble(attempt, inputs)
    except Exception as exc:
        detail = str(exc) if isinstance(exc, ValueError) else None
        dump(attempt / 'assembly_failure.json', dict(status='failed_assembly', error_type=type(exc).__name__, data_gate_detail=detail, financial_replays=0, completed_at=datetime.now(TZ).isoformat()))
        print(json.dumps(dict(status='failed_assembly', error_type=type(exc).__name__, data_gate_detail=detail), ensure_ascii=False))
        return 1
    print(json.dumps(dict(status=result['status'], data_ready=result['data_ready'], date_end=result['date_end'], accepted_rows=result['accepted_rows'], new_data=result['new_data'], data_directory=str(OUT / 'data_approved')), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
