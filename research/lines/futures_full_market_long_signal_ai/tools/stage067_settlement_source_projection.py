"""Project existing settlement observations onto all Stage049 identities.

No fitting, cash replay, label construction, download, production or new pool.
Actual use needs root's exact code/protocol SHA authorization and a fresh output.
One accepted native SELECT supplies pure, causal Stage042 ATR and source locators.
Only an absent original settlement column permits the fixed RQ H5 alternative.
Values remain historical reconstructions; fixed lag never certifies release PIT.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import importlib.util
import io
from itertools import groupby
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
KERNEL = Path(__file__).with_name('stage042_cross_session_experiment.py')
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'reference_epoch']
OHLC = ('open', 'high', 'low', 'close')
OHLC_ABS_TOL = 1e-8
EXPECTED_KERNEL_SHA = 'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d'
NATIVE_SQL = '''SELECT d.contract_epoch_id,d.trade_date,d.open,d.high,d.low,d.close,d.volume,
 d.quality_status,d.source_id,d.source_locator,d.source_symbol,d.volume_factor,
 s.family,s.path,s.sha256,s.bytes
 FROM daily_bars d JOIN sources s ON s.source_id=d.source_id
 WHERE d.trade_date>=? AND d.trade_date<=? ORDER BY d.contract_epoch_id,d.trade_date'''
NATIVE_COLUMNS = ['contract_epoch_id', 'trade_date', 'open', 'high', 'low', 'close', 'volume',
                  'quality_status', 'source_id', 'source_locator', 'source_symbol', 'volume_factor',
                  'source_family', 'source_path', 'source_sha256', 'source_bytes']


def finite(value):
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def positive(value):
    return finite(value) and float(value) > 0


def number(value):
    return float(value) if finite(value) else math.nan


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stat_binding(path):
    path = Path(path).resolve()
    s = path.stat()
    return dict(path=str(path), bytes=s.st_size, mtime_ns=s.st_mtime_ns, inode=s.st_ino)


def assert_stat(binding):
    current = stat_binding(binding['path'])
    if any(current[k] != binding[k] for k in ('bytes', 'mtime_ns', 'inode') if k in binding):
        raise ValueError('frozen source stat changed: ' + binding['path'])
    return current


def read_bound(binding):
    raw = Path(binding['path']).read_bytes()
    if len(raw) != binding['bytes'] or hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('bound small/input file changed: ' + binding['path'])
    return raw


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def load_pure_kernel():
    if file_sha(KERNEL) != EXPECTED_KERNEL_SHA:
        raise ValueError('accepted pure ATR kernel changed')
    spec = importlib.util.spec_from_file_location('stage067_pure042', KERNEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_mother(frame, dates, *, expected_rows=399252):
    """Select only identities; future label columns cannot influence this step."""
    result = frame[IDENTITY].copy()
    if expected_rows is not None and len(result) != expected_rows:
        raise ValueError('full mother row count changed')
    if list(dates) != sorted(set(dates)):
        raise ValueError('source calendar not unique ordered')
    if result.event_id.duplicated().any() or result.duplicated(['product_id', 'u_date']).any():
        raise ValueError('duplicate mother identity')
    if not np.array_equal(result.sequence_index.to_numpy(dtype=np.int64), np.arange(len(result))):
        raise ValueError('original mother sequence changed')
    expected_family = result.product_id.astype(str).str.removesuffix('_F')
    if not result.family_id.eq(expected_family).all():
        raise ValueError('ordinary/F family identity changed')
    lookup = {day: i for i, day in enumerate(dates)}
    indices = result.u_date.map(lookup)
    if indices.isna().any():
        raise ValueError('mother outside source calendar')
    result['u_index'] = indices.astype(np.int32)
    result['v_index'] = result.u_index - 1
    result['v_date'] = [dates[int(k)] if k >= 0 else '' for k in result.v_index]
    return result


def build_native_projection(records, dates, wanted):
    """Consume ordered accepted native rows once; persist only requested v rows."""
    ref = load_pure_kernel()
    calendar = {day: i for i, day in enumerate(dates)}
    result, source_catalog = {}, {}
    count, epochs = 0, 0
    for epoch, group in groupby(records, key=lambda r: r['contract_epoch_id']):
        rows = list(group)
        epochs += 1
        count += len(rows)
        days, values, valid = [], [], []
        for row in rows:
            if row['trade_date'] not in calendar:
                raise ValueError('native date outside frozen source calendar')
            days.append(calendar[row['trade_date']])
            v = [number(row[k]) for k in (*OHLC, 'volume')]
            values.append(v)
            valid.append(row['quality_status'] == 'accepted' and all(positive(x) for x in v)
                         and v[2] <= min(v[0], v[3]) <= max(v[0], v[3]) <= v[1])
        if days != sorted(set(days)):
            raise ValueError('duplicate or unordered native epoch/day')
        series = ref.EpochSeries(days, values, valid)
        for j, row in enumerate(rows):
            key = (epoch, row['trade_date'])
            if key not in wanted:
                continue
            if key in result:
                raise ValueError('native epoch is not a contiguous unique group')
            record = dict(row, N=float(series.N[j]), history_run=int(series.run[j]),
                          accepted_native_valid=bool(series.valid[j]))
            result[key] = record
            sid = row['source_id']
            binding = {k: row.get(k) for k in ('source_family', 'source_path', 'source_sha256', 'source_bytes')}
            if sid in source_catalog and source_catalog[sid] != binding:
                raise ValueError('source id has inconsistent physical binding')
            source_catalog[sid] = binding
    return result, dict(native_contract_days=count, native_epochs=epochs,
                        requested_native_rows=len(result), requested_unique_epoch_days=len(wanted),
                        source_catalog=source_catalog, pure_indicator='unchanged042_Wilder20_N_at_v')


def read_native_once(binding, dates, wanted, start, end):
    before = assert_stat(binding)
    path = Path(binding['path']).resolve()
    if Path(str(path) + '-wal').exists() or Path(str(path) + '-shm').exists():
        raise ValueError('accepted native WAL/SHM unexpectedly present')
    uri = path.as_uri() + '?mode=ro&immutable=1'
    with sqlite3.connect(uri, uri=True) as db:
        # This is the only native SELECT; no schema/count/source follow-up SQL.
        cursor = db.execute(NATIVE_SQL, (start, end))
        records = (dict(zip(NATIVE_COLUMNS, row)) for row in cursor)
        projected, receipt = build_native_projection(records, dates, wanted)
    after = assert_stat(binding)
    if before != after:
        raise ValueError('native source changed during projection')
    receipt.update(native_source_queries=1, database_before=before, database_after=after,
                   database_sha256_inherited=binding['sha256'], database_rehashed=False)
    return projected, receipt


def metadata_index(entries):
    """Resolve full delivery year/month from existing vendor metadata; never short aliases."""
    result = {}
    for item in entries:
        try:
            maturity = date.fromisoformat(item['maturity_date'][:10])
            match = re.fullmatch(r'([A-Z]+)(\d{4})(F?)', item['order_book_id'])
            if not match:
                continue
            prefix, digits, suffix = match.groups()
            product = prefix + ('_F' if suffix else '')
            if item['underlying_symbol'] != product or item['exchange'] not in {'SHFE', 'INE', 'DCE', 'CZCE', 'CFFEX', 'GFEX'}:
                continue
            month = int(digits[-2:])
            years = [y for y in range(maturity.year - 1, maturity.year + 2) if y % 100 == int(digits[:2])]
            if len(years) != 1 or not 1 <= month <= 12:
                continue
            identity = f"{item['exchange']}.{product}.{years[0]:04d}{month:02d}"
            record = dict(item, contract_epoch_id=identity)
            if identity in result and result[identity] != record:
                raise ValueError('duplicate full metadata identity')
            result[identity] = record
        except (KeyError, TypeError, ValueError) as error:
            if str(error) == 'duplicate full metadata identity':
                raise
            continue
    return result


def rule_annotation(epoch, day, metadata):
    exchange, product, _ = epoch.split('.')
    result = dict(benchmark_family='unknown', rule_state='unknown', rule_primary_bound=0, expected_print_decimals='',
                  final_delivery_definition='product_specific_not_substituted_for_daily_settlement',
                  lifecycle_state='vendor_lifecycle_unknown', rule_evidence='')
    if exchange == 'CFFEX' and product in {'IF', 'IH', 'IC', 'IM'}:
        result.update(benchmark_family='cffex_index_last_hour_daily', expected_print_decimals='1',
                      final_delivery_definition='underlying_index_last_two_hours_arithmetic_mean',
                      rule_evidence='https://www.cffex.com.cn/u/cms/www/202003/27165505w3j5.pdf')
    elif exchange == 'CFFEX' and product in {'T', 'TF', 'TS', 'TL'}:
        result.update(benchmark_family='cffex_bond_last_hour_daily', expected_print_decimals='3',
                      final_delivery_definition='final_trade_day_futures_whole_day_volume_weighted',
                      rule_evidence='https://www.e-cffex.com.cn/u/cms/www/202007/08152235b2ys.pdf')
    elif exchange in {'SHFE', 'INE', 'DCE', 'CZCE', 'GFEX'} and not product.endswith('_F'):
        result.update(benchmark_family=exchange.lower() + '_commodity_daily_default',
                      expected_print_decimals='product_and_period_specific_not_inferred',
                      rule_evidence={'SHFE': 'https://www.shfe.com.cn/upload/20200930/1601455533699.pdf',
                                     'INE': 'https://www.shfe.com.cn/regulation/ineregulation/businessmethods/settlement/202606/t20260622_832188.html',
                                     'CZCE': 'https://www.czce.com.cn/cn/uploadfile/2022/06/20/20220620144457117.pdf'}.get(exchange, 'not_bound_in_stage067'))
    # _F contracts and unsupported rule families remain values-only unknown.
    if result['benchmark_family'] != 'unknown':
        result['rule_primary_bound'] = int(result['rule_evidence'] not in {'', 'not_bound_in_stage067'})
        result['rule_state'] = ('historical_family_reconstruction_not_full_vintage' if result['rule_evidence'] != 'not_bound_in_stage067'
                                else 'family_default_assumption_no_primary_rule_bound')
    final_days = [str(metadata.get(k, ''))[:10] for k in ('maturity_date', 'de_listed_date')
                  if isinstance(metadata.get(k), str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', metadata[k][:10])]
    if final_days:
        result['lifecycle_state'] = 'at_or_after_vendor_final_boundary' if day >= min(final_days) else 'before_vendor_final_boundary'
    return result


def empty_candidate(state, *, field_present=None, source_id='', source_family='', locator=''):
    return dict(observation_state=state, field_present=field_present, source_id=source_id,
                source_family=source_family, locator=locator)


def locator_index(value, minimum):
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError('locator row must be an exact integer')
    result = int(value)
    if result < minimum:
        raise ValueError('locator row below format origin')
    return result


def ohlc_relation(native, candidate):
    if not all(positive(candidate.get(k)) for k in OHLC):
        return 'conflict'
    if any(abs(float(native[k]) - float(candidate[k])) > OHLC_ABS_TOL for k in OHLC):
        return 'conflict'
    return 'equal_with_fixed_absolute_tolerance_1e-8'


def needs_fallback(native, primary):
    return bool(primary and primary.get('observation_state') == 'row_found'
                and primary.get('field_present') is False
                and primary.get('source_epoch') == native['contract_epoch_id']
                and primary.get('trade_date') == native['trade_date']
                and ohlc_relation(native, primary) != 'conflict' and positive(primary.get('volume')))


def resolve_observation(native, primary, fallback, metadata):
    """Select once by provenance; bad values/rows never cause another-source rescue."""
    result = dict(projection_state='missing_original_source', value_observed=0,
                  source_route='accepted_source_locator', ohlc_relation='not_compared',
                  accepted_source_id=native['source_id'], accepted_source_locator=native['source_locator'],
                  accepted_C_v=number(native.get('close')), C_v=math.nan, S_v=math.nan, prev_S_v=math.nan,
                  N_v=number(native.get('N')), N_history_run=int(native.get('history_run', 0)),
                  close_minus_settlement_v=math.nan, settlement_source_id='', settlement_source_locator='',
                  source_price_unit='native_unadjusted_quote_same_epoch_not_currency_notional',
                  close_text='', settlement_text='', print_state='', strict_pit_accepted=0,
                  available_at='', availability_basis='historical_reconstruction_one_source_day_lag_not_release_verified',
                  training_accepted=0, feature_available=0, feature_state='source_projection_only_not_training_accepted',
                  N_state='N_v_ready20' if positive(native.get('N')) and native.get('history_run', 0) >= 20 else 'N_v_not_ready20',
                  accepted_quantity_factor=number(native.get('volume_factor')),
                  **rule_annotation(native['contract_epoch_id'], native['trade_date'], metadata))
    if result['N_state'] != 'N_v_ready20':
        result['feature_state'] = result['N_state']
    elif not result['rule_primary_bound']:
        result['feature_state'] = 'primary_rule_evidence_not_bound'
    chosen = primary
    if not chosen:
        return result
    for route in range(2):
        # Preserve candidate numbers and their own identity even when the
        # comparison below rejects them. They are evidence, never a mask.
        result.update(candidate_quote_epoch=chosen.get('source_epoch', ''), candidate_quote_date=chosen.get('trade_date', ''),
                      settlement_source_id=chosen.get('source_id', ''), settlement_source_locator=chosen.get('locator', ''),
                      C_v=number(chosen.get('close')), S_v=number(chosen.get('settlement')),
                      prev_S_v=number(chosen.get('prev_settlement')), close_text=chosen.get('close_text', ''),
                      settlement_text=chosen.get('settlement_text', ''), print_state=chosen.get('print_state', ''))
        if chosen.get('observation_state') != 'row_found':
            result['projection_state'] = chosen.get('observation_state', 'missing_original_source')
            return result
        if chosen.get('source_epoch') != native['contract_epoch_id'] or chosen.get('trade_date') != native['trade_date']:
            result['projection_state'] = 'source_identity_or_date_conflict'
            return result
        result['ohlc_relation'] = ohlc_relation(native, chosen)
        if result['ohlc_relation'] == 'conflict':
            result['projection_state'] = 'source_ohlc_conflict'
            return result
        if not positive(chosen.get('volume')):
            result['projection_state'] = 'source_no_trade'
            return result
        if chosen.get('field_present') is not False:
            break
        if route == 1 or fallback is None:
            result['projection_state'] = 'settlement_column_absent_fallback_unavailable'
            return result
        result['source_route'] = 'rq_fallback_after_absent_original_column'
        chosen = fallback
    if not positive(chosen.get('settlement')):
        result['projection_state'] = 'settlement_nonfinite_or_nonpositive'
    elif result['lifecycle_state'] != 'before_vendor_final_boundary':
        result['projection_state'] = 'final_delivery_or_definition_unknown'
    elif result['benchmark_family'] == 'unknown':
        result['projection_state'] = 'rule_family_unknown'
    elif not float(native['low']) - OHLC_ABS_TOL <= result['S_v'] <= float(native['high']) + OHLC_ABS_TOL:
        result['projection_state'] = 'settlement_outside_native_range'
    else:
        result.update(projection_state='observed_historical_reconstruction', value_observed=1,
                      close_minus_settlement_v=result['C_v'] - result['S_v'])
    return result


class SourceReader:
    """Read only wanted exact rows. CSV files are hashed during their one read.

    The H5 is stat-bound before/after and inherits its prior SHA; never rehash it.
    No normalized source directory scan and no network calls are used.
    """
    def __init__(self, metadata, h5_path, h5_binding):
        self.metadata = metadata
        self.h5_path = Path(h5_path).resolve() if h5_path else None
        self.h5_binding = h5_binding
        self._h5_dates_cache = {}
        self._h5_keys_seen = set()
        self._h5_read_rows_digest = hashlib.sha256()
        self.receipt = dict(csv_files=0, csv_compressed_or_plain_bytes=0, csv_rows_scanned=0,
                            h5_opens=0, h5_key_visits=0, h5_timestamp_rows=0, h5_value_rows=0,
                            source_files=[], h5_rehashed=False)

    def read_originals(self, wanted):
        groups = defaultdict(dict)
        result, h5_requests = {}, {}
        for key, row in wanted.items():
            if row.get('source_family') == 'rqalpha':
                h5_requests[key] = row
            else:
                groups[str(Path(row.get('source_path', '')).resolve())][key] = row
        for path, requests in sorted(groups.items()):
            bindings = {(r.get('source_family'), r.get('source_sha256'), r.get('source_bytes')) for r in requests.values()}
            if len(bindings) != 1:
                result.update({key: empty_candidate('same_physical_source_binding_conflict') for key in requests})
                continue
            result.update(self._csv(Path(path), requests))
        if h5_requests:
            result.update(self._h5(h5_requests, original=True))
        return result

    def read_fallbacks(self, wanted):
        return self._h5(wanted, original=False) if wanted else {}

    def _csv(self, path, requests):
        result = {}
        example = next(iter(requests.values()))
        sid, family = example.get('source_id', ''), example.get('source_family', '')
        if family not in {'official', 'old_tq', 'recent_tq'}:
            return {k: empty_candidate('unsupported_original_source_family', source_id=sid) for k in requests}
        if not path.is_file():
            return {k: empty_candidate('original_source_file_missing', source_id=sid) for k in requests}
        before = stat_binding(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected = example.get('source_sha256')
        if expected and digest != expected:
            raise ValueError('original source content differs from accepted source: ' + str(path))
        self.receipt['csv_files'] += 1
        self.receipt['csv_compressed_or_plain_bytes'] += len(raw)
        self.receipt['source_files'].append(dict(path=str(path.resolve()), bytes=len(raw), sha256=digest,
                                                 read_role='accepted_locator_source_not_copied'))
        text = gzip.decompress(raw).decode('utf-8-sig') if path.name.endswith('.gz') else raw.decode('utf-8-sig')
        stream = csv.DictReader(io.StringIO(text, newline=''))
        fields = stream.fieldnames or []
        settlement_field = 'settle' if 'settle' in fields else 'settlement' if 'settlement' in fields else None
        requested_rows = defaultdict(list)
        matches = Counter()
        target_keys = set(requests)
        target_days = defaultdict(list)
        for key in target_keys:
            target_days[key[1]].append(key)
        for key, record in requests.items():
            try:
                loc = json.loads(record['source_locator'])
                requested_rows[locator_index(loc['row'], 2)].append((key, record, loc))
            except (ValueError, TypeError, KeyError):
                result[key] = empty_candidate('accepted_locator_unparseable', source_id=sid)
        for line, record in enumerate(stream, 2):
            self.receipt['csv_rows_scanned'] += 1
            day = record.get('date', record.get('trade_date', ''))[:10]
            if family == 'official':
                actual_epoch = '.'.join([record.get('exchange', ''), record.get('product', '').upper(), record.get('contract_yyyymm', '')])
                physical_key = (actual_epoch, day)
                if physical_key in target_keys:
                    matches[physical_key] += 1
            else:
                # This accepted TQ file is one exchange/symbol; date is still
                # checked rather than inferred from the requested locator.
                for key in target_days.get(day, []):
                    matches[key] += 1
            for key, native, locator in requested_rows.get(line, []):
                actual_epoch = ('.'.join([record.get('exchange', ''), record.get('product', '').upper(), record.get('contract_yyyymm', '')])
                                if family == 'official' else native['contract_epoch_id'])
                locator_ok = (('source_member' not in locator or str(locator['source_member']) == str(record.get('source_member', '')))
                              and ('raw_row' not in locator or str(locator['raw_row']) == str(record.get('source_row', ''))))
                native_sid = native.get('source_id', sid)
                source_symbol_ok = (family == 'official' or native_sid.split(':', 1)[-1] == native['contract_epoch_id'].split('.')[0] + '.' + str(native['source_symbol']))
                if not locator_ok or not source_symbol_ok:
                    result[key] = empty_candidate('accepted_locator_binding_conflict', source_id=sid)
                    continue
                result[key] = dict(source_epoch=actual_epoch, trade_date=day,
                    **{name: number(record.get(name)) for name in (*OHLC, 'volume')},
                    settlement=number(record.get(settlement_field)) if settlement_field else None,
                    prev_settlement=number(record.get('pre_settle', record.get('prev_settlement'))),
                    field_present=settlement_field is not None, observation_state='row_found',
                    source_id=native_sid, source_family=family,
                    locator=json.dumps(dict(path=str(path.resolve()), **locator), ensure_ascii=False, sort_keys=True),
                    close_text=str(record.get('close', '')), settlement_text=str(record.get(settlement_field, '')) if settlement_field else '',
                    print_state='source_csv_field_text_preserved')
        for key in requests:
            if key not in result:
                result[key] = empty_candidate('locator_row_missing', field_present=settlement_field is not None, source_id=sid)
            elif matches[key] > 1:
                result[key]['observation_state'] = 'duplicate_source_epoch_day'
        if stat_binding(path) != before:
            raise ValueError('CSV source changed during projection')
        return result

    def _h5(self, requests, *, original):
        result, groups = {}, defaultdict(dict)
        if self.h5_path is None or not self.h5_path.is_file():
            return {key: empty_candidate('rq_h5_unavailable', source_id='rqalpha') for key in requests}
        before = assert_stat(self.h5_binding)
        for key, record in requests.items():
            metadata = self.metadata.get(key[0])
            if not metadata:
                result[key] = empty_candidate('full_epoch_metadata_missing', source_id='rqalpha')
                continue
            rq_key = metadata['order_book_id']
            if original:
                inherited_sha = self.h5_binding.get('sha256')
                if not record.get('source_sha256') or not inherited_sha:
                    result[key] = empty_candidate('accepted_h5_content_identity_missing', source_id='rqalpha')
                    continue
                if (record['source_sha256'] != inherited_sha
                        or (record.get('source_bytes') and record['source_bytes'] != self.h5_binding['bytes'])):
                    result[key] = empty_candidate('accepted_h5_content_identity_conflict', source_id='rqalpha')
                    continue
                try:
                    locator = json.loads(record['source_locator'])
                    locator_index(locator['row'], 0)
                    source_key = locator['key']
                except (ValueError, TypeError, KeyError):
                    result[key] = empty_candidate('accepted_locator_unparseable', source_id='rqalpha')
                    continue
                if source_key != rq_key or Path(record['source_path']).resolve() != self.h5_path:
                    result[key] = empty_candidate('accepted_locator_binding_conflict', source_id='rqalpha')
                    continue
            groups[rq_key][key] = record
        import h5py
        with h5py.File(self.h5_path, 'r') as store:
            self.receipt['h5_opens'] += 1
            for rq_key, wanted in sorted(groups.items()):
                self.receipt['h5_key_visits'] += 1
                self._h5_keys_seen.add(rq_key)
                self.receipt['h5_unique_keys'] = len(self._h5_keys_seen)
                if rq_key not in store:
                    result.update({key: empty_candidate('rq_exact_key_missing', source_id='rqalpha') for key in wanted})
                    continue
                dataset = store[rq_key]
                names = set(dataset.dtype.names or [])
                if not {'datetime', *OHLC, 'volume'} <= names:
                    result.update({key: empty_candidate('rq_required_schema_missing', source_id='rqalpha') for key in wanted})
                    continue
                if rq_key not in self._h5_dates_cache:
                    times = dataset['datetime'][:]
                    self.receipt['h5_timestamp_rows'] += len(times)
                    day_positions = defaultdict(list)
                    for j, timestamp in enumerate(times):
                        value = int(timestamp)
                        if value % 1000000:
                            continue
                        text = str(value // 1000000)
                        if len(text) == 8:
                            day_positions[text[:4] + '-' + text[4:6] + '-' + text[6:]].append(j)
                    self._h5_dates_cache[rq_key] = day_positions
                day_positions = self._h5_dates_cache[rq_key]
                for key, native in wanted.items():
                    positions = day_positions.get(key[1], [])
                    if len(positions) != 1:
                        result[key] = empty_candidate('duplicate_source_epoch_day' if positions else 'source_date_missing', source_id='rqalpha')
                        continue
                    j = positions[0]
                    if original and locator_index(json.loads(native['source_locator'])['row'], 0) != j:
                        result[key] = empty_candidate('accepted_locator_binding_conflict', source_id='rqalpha')
                        continue
                    record = dataset[j]
                    self.receipt['h5_value_rows'] += 1
                    self._h5_read_rows_digest.update((rq_key + '|' + str(j) + '|').encode())
                    self._h5_read_rows_digest.update(record.tobytes())
                    result[key] = dict(source_epoch=key[0], trade_date=key[1],
                        **{name: float(record[name]) for name in (*OHLC, 'volume')},
                        settlement=float(record['settlement']) if 'settlement' in names else None,
                        prev_settlement=float(record['prev_settlement']) if 'prev_settlement' in names else None,
                        field_present='settlement' in names, observation_state='row_found', source_id='rqalpha', source_family='rqalpha',
                        locator=json.dumps(dict(path=str(self.h5_path), key=rq_key, row=j), sort_keys=True),
                        close_text=format(float(record['close']), '.17g'),
                        settlement_text=format(float(record['settlement']), '.17g') if 'settlement' in names else '',
                        print_state='float64_not_original_print_precision')
        if assert_stat(self.h5_binding) != before:
            raise ValueError('RQ H5 changed during projection')
        self.receipt['h5_requested_rows_fingerprint_sha256'] = self._h5_read_rows_digest.hexdigest()
        self.receipt['h5_fingerprint_scope'] = 'only_actually_read_rows_not_full_blob_reverification'
        self.receipt['h5_inherited_content_identity'] = self.h5_binding.get('sha256')
        return result


def project_mother(mother, native, original, fallback, metadata):
    values = []
    for identity in mother.to_dict('records'):
        key = (identity['reference_epoch'], identity['v_date'])
        missing = ('no_reference_epoch' if not identity['reference_epoch'] else
                   'no_previous_source_day' if identity['v_index'] < 0 else
                   'missing_native_v' if key not in native else
                   'invalid_accepted_native_v' if not native[key].get('accepted_native_valid', True) else None)
        if missing:
            record = dict(projection_state=missing, value_observed=0, source_route='none', ohlc_relation='not_compared',
                          strict_pit_accepted=0, training_accepted=0, feature_available=0, feature_state=missing,
                          N_state='N_v_not_ready20', rule_state='unknown', rule_primary_bound=0, benchmark_family='unknown',
                          available_at='', availability_basis='historical_reconstruction_one_source_day_lag_not_release_verified')
        else:
            record = resolve_observation(native[key], original.get(key), fallback.get(key), metadata.get(key[0], {}))
        values.append(dict(identity, **record))
    result = pd.DataFrame(values)
    if len(result) != len(mother) or not result[IDENTITY].equals(mother[IDENTITY]):
        raise ValueError('mother preservation failed')
    return result


def coverage_table(frame):
    data = frame.assign(year=frame.u_date.astype(str).str[:4])
    rows = []
    for (family, year), group in data.groupby(['family_id', 'year'], sort=True, dropna=False):
        record = dict(family_id=family, year=year, mother_rows=len(group), value_observed=int(group.value_observed.sum()),
                      strict_pit_accepted_rows=0, training_accepted_rows=0)
        for field in ('projection_state', 'source_route', 'ohlc_relation', 'rule_state'):
            record[field + '_counts'] = json.dumps(dict(sorted(Counter(group[field].fillna('unknown')).items())), sort_keys=True)
        record['value_observed_pct'] = 100. * record['value_observed'] / len(group)
        rows.append(record)
    result = pd.DataFrame(rows)
    if int(result.mother_rows.sum()) != len(frame):
        raise ValueError('coverage denominator lost mother rows')
    return result


def summary(frame, native_receipt, source_receipt):
    return dict(mother_rows=len(frame), unique_event_ids=int(frame.event_id.nunique()),
                value_observed_rows=int(frame.value_observed.sum()), strict_pit_accepted_rows=0, training_accepted_rows=0,
                feature_available_rows=0, field_observation_is_not_feature_mask=True,
                source_day_lag=1, quote_description='close_relative_to_applicable_settlement_benchmark_not_buy_pressure_or_universal_vwap',
                ohlc_absolute_tolerance=OHLC_ABS_TOL,
                state_counts=dict(Counter(frame.projection_state)), route_counts=dict(Counter(frame.source_route)),
                relation_counts=dict(Counter(frame.ohlc_relation)), rule_counts=dict(Counter(frame.rule_state)),
                native_read=native_receipt, settlement_source_read=source_receipt,
                model_fits=0, cash_replays=0, labels_built=0, downloads=0, production_qualified=False,
                actual_source_projection_runs=1, downstream_experiment_frozen=False)


def run_actual(protocol_bytes, output, *, source_sha256=None, protocol_sha256=None):
    # The importable real-reader entry cannot bypass the CLI's authorization.
    if source_sha256 != file_sha(__file__):
        raise ValueError('root exact source SHA authorization differs')
    if not isinstance(protocol_bytes, bytes) or hashlib.sha256(protocol_bytes).hexdigest() != protocol_sha256:
        raise ValueError('root exact protocol SHA authorization differs')
    protocol = json.loads(protocol_bytes)
    if protocol['source_sha256'] != source_sha256:
        raise ValueError('protocol code authorization binding differs')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('actual output exists; no silent restart or overwrite')
    if protocol['scope'] != dict(expected_mother_rows=399252, expected_products=98, expected_exchanges=6,
                                 expected_native_rows=1552456, expected_native_epochs=9520,
                                 start='2010-01-01', end='2026-10-16'):
        raise ValueError('fixed scope differs')
    output.mkdir(parents=True)
    started = time.monotonic()
    write_json(output / 'actual_started.json', dict(started_at=datetime.now(timezone.utc).isoformat(), source_projection_runs_started=1))
    try:
        calendar = load_pure_kernel().parse_calendar(read_bound(protocol['calendar']))
        source = protocol['mother']
        raw = read_bound(source)
        mother = pd.read_csv(io.BytesIO(raw), compression='gzip' if source['path'].endswith('.gz') else None,
                             usecols=IDENTITY, dtype={k: str for k in IDENTITY if k != 'sequence_index'}, keep_default_na=False)
        mother = prepare_mother(mother, calendar)
        if mother.product_id.nunique() != 98 or mother.product_id.str.split('.').str[0].nunique() != 6:
            raise ValueError('full product/exchange scope changed')
        wanted = {(r.reference_epoch, r.v_date) for r in mother.itertuples(index=False) if r.reference_epoch and r.v_index >= 0}
        native, native_receipt = read_native_once(protocol['database'], calendar, wanted,
                                                 protocol['scope']['start'], protocol['scope']['end'])
        if native_receipt['native_contract_days'] != 1552456 or native_receipt['native_epochs'] != 9520:
            raise ValueError('accepted native full scope changed')
        metadata = metadata_index(json.loads(read_bound(protocol['rq_metadata'])))
        reader = SourceReader(metadata, protocol['rq_h5']['path'], protocol['rq_h5'])
        original = reader.read_originals(native)
        requests = {key: row for key, row in native.items() if needs_fallback(row, original.get(key))}
        fallback = reader.read_fallbacks(requests)
        projected = project_mother(mother, native, original, fallback, metadata)
        coverage = coverage_table(projected)
        report = summary(projected, native_receipt, reader.receipt)
        projected.to_csv(output / 'settlement_projection.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
        coverage.to_csv(output / 'family_year_coverage.csv', index=False)
        write_json(output / 'summary.json', report)
        write_json(output / 'protocol.json', protocol)
        write_json(output / 'actual_terminal.json', dict(completed=True, elapsed_seconds=time.monotonic()-started,
                   source_projection_runs_completed=1, native_source_queries=1, model_fits=0, cash_replays=0,
                   downloads=0, labels_built=0))
        artifacts = []
        for path in sorted(output.iterdir()):
            if path.is_file():
                artifacts.append(dict(path=str(path), bytes=path.stat().st_size, sha256=file_sha(path),
                                      raw_ohlc=False, role='minimal_projection_or_receipt'))
        write_json(output / 'manifest.json', dict(artifacts=artifacts, script_sha256=file_sha(__file__),
                   kernel_sha256=EXPECTED_KERNEL_SHA, model_fits=0, cash_replays=0, production_qualified=False))
        print(json.dumps(json_safe(dict(mother_rows=len(projected), state_counts=report['state_counts'],
                                       elapsed_seconds=time.monotonic()-started)), ensure_ascii=False), flush=True)
        return report
    except Exception as error:
        write_json(output / 'actual_terminal.json', dict(completed=False, elapsed_seconds=time.monotonic()-started,
                   error_type=type(error).__name__, error=str(error), model_fits=0, cash_replays=0, downloads=0))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--authorize-source-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.authorize_source_sha256 != file_sha(__file__):
        raise ValueError('root exact source SHA authorization differs')
    path = Path(args.protocol)
    if file_sha(path) != args.protocol_sha256:
        raise ValueError('root exact protocol SHA authorization differs')
    return run_actual(path.read_bytes(), args.output, source_sha256=args.authorize_source_sha256,
                      protocol_sha256=args.protocol_sha256)


if __name__ == '__main__':
    main()
