"""Exact pre-event field projection; a root-bound actual authorization is required.

One requested-key SQL, each necessary CSV once, at most two readonly H5 opens.
No clocks, candidate universe, labels, indicators, prediction fits or cash runs.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sqlite3
import time

import pandas as pd

RESOLVER_SHA = 'dacbb8d58e42f98c003d83c5a673a9bc651d645f092e17bd02e1dcdecb49f048'
REQUEST_FIELDS = ['raw_request_id', 'reference_epoch', 'pre_date', 'pre_observed_any_epoch',
                  'requestable', 'child_link_count', 'event_count', 'product_aliases']
NATIVE_FIELDS = ['contract_epoch_id', 'trade_date', 'open', 'high', 'low', 'close',
                 'volume', 'native_volume', 'volume_factor', 'quality_status', 'source_id',
                 'source_locator', 'source_symbol', 'source_family', 'source_path',
                 'source_sha256', 'source_bytes']
EXACT_SQL = '''WITH requests AS (
 SELECT CAST(key AS INTEGER) AS idx,
        json_extract(value,'$[0]') AS epoch,
        json_extract(value,'$[1]') AS day FROM json_each(?)
)
SELECT r.idx,r.epoch,r.day,d.contract_epoch_id,d.trade_date,d.open,d.high,d.low,d.close,
 d.volume,d.native_volume,d.volume_factor,d.quality_status,d.source_id,d.source_locator,
 d.source_symbol,s.family,s.path,s.sha256,s.bytes
 FROM requests r
 LEFT JOIN daily_bars d ON d.contract_epoch_id=r.epoch AND d.trade_date=r.day
 LEFT JOIN sources s ON s.source_id=d.source_id
 ORDER BY r.idx'''


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def number(value):
    return float(value) if finite(value) else None


def positive(value):
    return finite(value) and float(value) > 0


def nonnegative(value):
    return finite(value) and float(value) >= 0


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def load_resolver(binding=None):
    source = Path(__file__).with_name('stage067_settlement_source_projection.py')
    if binding and Path(binding['path']).resolve() != source.resolve():
        raise ValueError('unexpected resolver path')
    if sha256(source) != RESOLVER_SHA or (binding and binding['sha256'] != RESOLVER_SHA):
        raise ValueError('accepted067 resolver changed')
    spec = importlib.util.spec_from_file_location('stage488_inherited067', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_numeric_record(request, native, primary, fallback, metadata, resolver):
    """Separate numerical source checks from inherited rule and PIT qualification.

    Rule-unknown values remain explicitly conditional research proxies. They are
    never relabelled accepted067 observations, and all request rows survive.
    """
    metadata = metadata or {}
    multiplier = number(metadata.get('contract_multiplier'))
    exchange, product, _ = request['reference_epoch'].split('.')
    metadata_exact = (metadata.get('economics_status') == 'exact_epoch_metadata_snapshot'
                      and metadata.get('exchange') == exchange
                      and metadata.get('underlying_symbol') == product)
    multiplier_verified = metadata_exact and positive(multiplier)
    result = dict(request, native_found=int(native is not None), native_quality_status='', native_ohlc_valid=0,
                  pre_volume=None, native_volume=None, volume_factor=None, quantity_consistency='not_observed',
                  accepted_source_id='', accepted_source_locator='', accepted_source_family='', accepted_source_path='',
                  accepted_source_sha256='', accepted_source_bytes=None,
                  pre_open_native=None, pre_high_native=None, pre_low_native=None, pre_close_native=None,
                  pre_settlement_candidate=None, pre_settlement_source_verified=None, pre_close_candidate=None,
                  pre_open_candidate=None, pre_high_candidate=None, pre_low_candidate=None,
                  candidate_source_volume=None, candidate_source_epoch='', candidate_source_date='',
                  original_observation_state='not_observed', original_field_present=None,
                  original_source_epoch='', original_source_date='', original_ohlc_relation='not_compared',
                  original_settlement_candidate=None, original_settlement_text='', original_volume=None,
                  original_locator='', fallback_permitted_by067=0,
                  settlement_source_id='', settlement_source_locator='', settlement_source_family='',
                  settlement_text='', close_text='', print_state='', source_route='none', ohlc_relation='not_compared',
                  source_numeric_state='missing_native_pre', settlement_numerically_verified=0,
                  source_numerically_verified=False, inherited067_projection_state='missing_native_pre',
                  inherited067_value_observed=0, rule_state='unknown', rule_primary_bound=0, benchmark_family='unknown',
                  lifecycle_state='vendor_lifecycle_unknown', rule_evidence='', expected_print_decimals='',
                  final_delivery_definition='unknown', cash_multiplier=multiplier, multiplier_verified=int(multiplier_verified),
                  economics_status=metadata.get('economics_status', 'missing_exact_epoch_metadata'),
                  economics_order_book_id=metadata.get('order_book_id', ''), currency=metadata.get('currency', ''),
                  currency_source=metadata.get('currency_source', 'unknown'),
                  multiplier_scope='exact_epoch_static_snapshot_not_daily_historical_PIT',
                  turnover_interpretation='cash_quote_model_CNY_equivalent_research_proxy_not_legal_face_notional',
                  maturity_date=metadata.get('maturity_date', ''), de_listed_date=metadata.get('de_listed_date', ''),
                  raw_candidate_notional=None, numeric_notional=None, log_turnover_source_verified=None,
                  strict_pit_accepted=0, training_accepted=0, alpha_supported=0)
    result.update(available_at='', availability_basis='historical_same_pre_day_reconstruction_not_release_timestamp_verified')
    if native is None:
        return result
    if (native['contract_epoch_id'], native['trade_date']) != (request['reference_epoch'], request['pre_date']):
        raise ValueError('exact native request identity differs')
    volume, raw_volume, factor = [number(native.get(k)) for k in ('volume', 'native_volume', 'volume_factor')]
    quantity_state = ('consistent_native_times_inherited_factor' if nonnegative(volume) and nonnegative(raw_volume)
                      and factor in (.5, 1.) and abs(raw_volume * factor - volume) <= 1e-6
                      else 'inconsistent_or_unknown_native_quantity_binding')
    ohlc_valid = (all(positive(native.get(k)) for k in resolver.OHLC)
                  and native['low'] <= min(native['open'], native['close']) <= max(native['open'], native['close']) <= native['high'])
    native_valid = native.get('quality_status') == 'accepted' and ohlc_valid
    result.update(native_quality_status=native.get('quality_status', ''), native_ohlc_valid=int(ohlc_valid),
                  pre_volume=volume, native_volume=raw_volume, volume_factor=factor, quantity_consistency=quantity_state,
                  **{'pre_' + k + '_native': number(native.get(k)) for k in resolver.OHLC},
                  source_route='accepted_source_locator',
                  **{'accepted_' + k: native.get(k, '') for k in ['source_id', 'source_locator', 'source_family', 'source_path', 'source_sha256', 'source_bytes']})
    inherited_native = dict(native, N=math.nan, history_run=0)
    inherited = resolver.resolve_observation(inherited_native, primary, fallback, metadata)
    result.update(inherited067_projection_state=inherited['projection_state'],
                  inherited067_value_observed=inherited['value_observed'],
                  **{k: inherited.get(k, '') for k in ['rule_state', 'rule_primary_bound', 'benchmark_family',
                      'lifecycle_state', 'rule_evidence', 'expected_print_decimals', 'final_delivery_definition']})
    chosen = primary
    if primary:
        result.update(original_observation_state=primary.get('observation_state', ''),
                      original_field_present=primary.get('field_present'), original_source_epoch=primary.get('source_epoch', ''),
                      original_source_date=primary.get('trade_date', ''), original_ohlc_relation=resolver.ohlc_relation(inherited_native, primary),
                      original_settlement_candidate=number(primary.get('settlement')), original_settlement_text=primary.get('settlement_text', ''),
                      original_volume=number(primary.get('volume')), original_locator=primary.get('locator', ''))
    if resolver.needs_fallback(inherited_native, primary):
        result['fallback_permitted_by067'] = 1
        result['source_route'] = 'rq_fallback_after_absent_original_column'
        chosen = fallback
    if chosen:
        result.update(pre_settlement_candidate=number(chosen.get('settlement')), pre_close_candidate=number(chosen.get('close')),
                      **{'pre_' + k + '_candidate': number(chosen.get(k)) for k in ('open', 'high', 'low')},
                      candidate_source_volume=number(chosen.get('volume')), candidate_source_epoch=chosen.get('source_epoch', ''),
                      candidate_source_date=chosen.get('trade_date', ''), settlement_source_id=chosen.get('source_id', ''),
                      settlement_source_locator=chosen.get('locator', ''), settlement_source_family=chosen.get('source_family', ''),
                      settlement_text=chosen.get('settlement_text', ''), close_text=chosen.get('close_text', ''),
                      print_state=chosen.get('print_state', ''), ohlc_relation=resolver.ohlc_relation(inherited_native, chosen))
    state = 'source_verified_conditional_research_value'
    if not native_valid:
        state = 'invalid_accepted_native_pre'
    elif not chosen:
        state = ('settlement_column_absent_fallback_unavailable' if result['source_route'].startswith('rq_') else 'missing_original_source')
    elif chosen.get('observation_state') != 'row_found':
        state = chosen.get('observation_state', 'missing_original_source')
    elif (chosen.get('source_epoch'), chosen.get('trade_date')) != (request['reference_epoch'], request['pre_date']):
        state = 'source_identity_or_date_conflict'
    elif resolver.ohlc_relation(inherited_native, chosen) == 'conflict':
        state = 'source_ohlc_conflict'
    elif not nonnegative(chosen.get('volume')):
        state = 'source_quantity_nonfinite_or_negative'
    elif chosen.get('field_present') is not True:
        state = 'settlement_column_absent_or_schema_unknown'
    elif not positive(chosen.get('settlement')):
        state = 'settlement_nonfinite_or_nonpositive'
    elif not native['low'] - resolver.OHLC_ABS_TOL <= float(chosen['settlement']) <= native['high'] + resolver.OHLC_ABS_TOL:
        state = 'settlement_outside_native_range'
    else:
        result.update(pre_settlement_source_verified=float(chosen['settlement']), settlement_numerically_verified=1,
                      ohlc_relation=resolver.ohlc_relation(inherited_native, chosen))
    if state == 'source_verified_conditional_research_value':
        if not nonnegative(volume) or quantity_state != 'consistent_native_times_inherited_factor':
            state = 'clean_quantity_unknown_or_inconsistent'
        elif not multiplier_verified:
            state = 'cash_multiplier_unknown_or_not_exact_epoch'
        else:
            notional = volume * multiplier * result['pre_settlement_source_verified']
            if not finite(notional):
                state = 'numeric_notional_overflow'
            else:
                result.update(source_numerically_verified=True, numeric_notional=notional,
                              log_turnover_source_verified=math.log(notional) if notional > 0 else None)
                if volume == 0:
                    state = 'source_verified_zero_volume_log_unknown'
    if nonnegative(volume) and positive(multiplier) and positive(result['pre_settlement_candidate']):
        raw_notional = volume * multiplier * result['pre_settlement_candidate']
        result['raw_candidate_notional'] = number(raw_notional)
    result['source_numeric_state'] = state
    return result


def read_bound(binding):
    raw = Path(binding['path']).read_bytes()
    if len(raw) != binding['bytes'] or hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('frozen small input changed: ' + binding['path'])
    return raw


def read_exact_native(binding, requests, resolver):
    """Only one requested-key SELECT; no schema, count, source or range probe."""
    before = resolver.assert_stat(binding)
    path = Path(binding['path']).resolve()
    if Path(str(path) + '-wal').exists() or Path(str(path) + '-shm').exists():
        raise ValueError('accepted native WAL/SHM unexpectedly present')
    keys = [(r['reference_epoch'], r['pre_date']) for r in requests]
    payload = json.dumps(keys, separators=(',', ':'))
    projected = {}
    count = 0
    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        for seq, epoch, day, *values in db.execute(EXACT_SQL, (payload,)):
            if seq != count or (epoch, day) != keys[count]:
                raise ValueError('exact SQL request sequence or cardinality changed')
            count += 1
            if values[0] is None:
                continue
            row = dict(zip(NATIVE_FIELDS, values))
            if (row['contract_epoch_id'], row['trade_date']) != (epoch, day):
                raise ValueError('native join changed epoch/date')
            projected[(epoch, day)] = row
    after = resolver.assert_stat(binding)
    if count != len(keys) or before != after:
        raise ValueError('native source or LEFT JOIN request cardinality changed')
    return projected, dict(native_source_queries=1, native_rows_returned=count,
                          requested_native_observed=len(projected), requested_native_missing=count-len(projected),
                          native_full_stream_reads=0, database_before=before, database_after=after,
                          database_sha256_inherited=binding['sha256'], database_rehashed=False,
                          exact_sql_sha256=hashlib.sha256(EXACT_SQL.encode()).hexdigest())


def bounded_reader(resolver, metadata, h5_binding, budget):
    class BoundedSourceReader(resolver.SourceReader):
        def __init__(self):
            super().__init__(metadata, h5_binding['path'], h5_binding)
            self._csv_attempted = set()
            self._csv_attempt_bytes = 0
            self._h5_calls = 0

        def _csv(self, path, requests):
            physical = str(Path(path).resolve())
            if physical in self._csv_attempted:
                raise ValueError('CSV physical source requested twice')
            size = Path(path).stat().st_size if Path(path).is_file() else 0
            if len(self._csv_attempted) + 1 > budget['csv_files_max'] or self._csv_attempt_bytes + size > budget['csv_bytes_max']:
                raise ValueError('frozen CSV count/physical-byte budget exhausted')
            self._csv_attempted.add(physical)
            self._csv_attempt_bytes += size
            self.receipt.update(csv_physical_attempts=len(self._csv_attempted), csv_attempt_bytes=self._csv_attempt_bytes)
            return super()._csv(path, requests)

        def _h5(self, requests, *, original):
            if self._h5_calls + 1 > budget['h5_opens_max']:
                raise ValueError('frozen H5 readonly-open budget exhausted')
            self._h5_calls += 1
            self.receipt['h5_read_calls_attempted'] = self._h5_calls
            return super()._h5(requests, original=original)
    return BoundedSourceReader()


def verify_authorization(protocol, authorization):
    if authorization.get('actual_authorized') is not True:
        raise ValueError('root did not authorize actual field access')
    if authorization.get('source_sha256') != sha256(__file__):
        raise ValueError('root exact488 source binding differs')
    raw = Path(authorization['protocol_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != authorization.get('protocol_sha256') or json.loads(raw) != protocol:
        raise ValueError('root exact487 protocol binding differs')


def project_fields(protocol, output, *, authorization):
    """Return one full raw-request DataFrame and read receipt to the root runner.

    This function cannot authorize itself. It never opens Y/COMMON/old mother or
    action streams, nor dispatches financial fits, cash replay or downloads.
    """
    verify_authorization(protocol, authorization)
    if protocol.get('schema') != 'stage487_fomc_residual_protocol_v1':
        raise ValueError('unexpected frozen487 schema')
    cfg = protocol['source_fields']
    inputs = cfg['inputs']
    frozen_budget = cfg['budget']
    if (frozen_budget['starts_max'] != 1 or frozen_budget['retries'] != 0 or
        frozen_budget['requests_reads_max'] != 1 or frozen_budget['economic_projection_reads_max'] != 1 or
        frozen_budget['native_selects_max'] != 1 or frozen_budget['CSV_unique_physical_file_reads_max'] > cfg['contract']['requests_rows'] or
        frozen_budget['CSV_total_physical_bytes_max'] > 1024**3 or frozen_budget['CSV_each_physical_path_reads_max'] != 1 or
        frozen_budget['H5_readonly_opens_max'] > 2 or frozen_budget['whole_database_H5_rehashes'] != 0 or
        frozen_budget['downloads'] != 0 or frozen_budget['old_full_mother_action_streams'] != 0):
        raise ValueError('source budget differs from frozen upper envelope')
    budget = dict(csv_files_max=frozen_budget['CSV_unique_physical_file_reads_max'],
                  csv_bytes_max=frozen_budget['CSV_total_physical_bytes_max'],
                  h5_opens_max=frozen_budget['H5_readonly_opens_max'])
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('field output exists; no restart or overwrite')
    out.mkdir(parents=True)
    started = time.monotonic()
    receipt = dict(schema='stage488_exact_pre_fields_receipt_v1', completed=False,
                   started_at=datetime.now(timezone.utc).isoformat(), input_reads={}, input_reads_attempted={},
                   native_source_queries=0, native_source_queries_completed=0,
                   model_fits=0, cash_replays=0, downloads=0,
                   labels_read=0, COMMON_reads=0, old_mother_action_stream_reads=0,
                   strict_pit_accepted=False, training_accepted=False, alpha_supported=False)
    write_json(out / 'source_started.json', receipt)
    reader = None
    try:
        resolver = load_resolver(inputs['resolver'])
        receipt['input_reads_attempted']['requests'] = 1
        raw_requests = read_bound(inputs['requests'])
        receipt['input_reads']['requests'] = 1
        stream = csv.DictReader(io.StringIO(gzip.decompress(raw_requests).decode('utf-8'), newline=''))
        if stream.fieldnames != REQUEST_FIELDS:
            raise ValueError('accepted484 request schema differs')
        requests = list(stream)
        keys = [(r['reference_epoch'], r['pre_date']) for r in requests]
        if (len(requests) != cfg['contract']['requests_rows'] or len(set(keys)) != len(keys)
                or len({r['raw_request_id'] for r in requests}) != len(requests)):
            raise ValueError('full raw request count/uniqueness differs')
        if any(not r['reference_epoch'] or not r['pre_date'] or r['requestable'] != '1' for r in requests):
            raise ValueError('unexpected unrequestable key; do not silently drop')
        receipt['input_reads_attempted']['economics'] = 1
        raw_economics = read_bound(inputs['economics'])
        receipt['input_reads']['economics'] = 1
        economics = json.loads(raw_economics)
        if economics['schema'] != 'stage041_epoch_economics_projection_v1':
            raise ValueError('exact041 economic projection schema differs')
        instruments = economics['instruments']
        metadata = {k: v for k, v in instruments.items() if v.get('economics_status') == 'exact_epoch_metadata_snapshot'}
        receipt['input_reads_attempted']['unit_contract'] = 1
        units = json.loads(read_bound(inputs['unit_contract']))
        receipt['input_reads']['unit_contract'] = 1
        if units['canonical_quantity_unit'] != 'single_sided_contracts':
            raise ValueError('accepted clean quantity contract differs')
        receipt['native_source_queries'] = 1
        native, native_receipt = read_exact_native(inputs['database'], requests, resolver)
        receipt['native_source_queries_completed'] = 1
        receipt['native_read'] = native_receipt
        reader = bounded_reader(resolver, metadata, inputs['rq_h5'], budget)
        original = reader.read_originals(native)
        fallback_requests = {key: row for key, row in native.items() if resolver.needs_fallback(row, original.get(key))}
        fallback = reader.read_fallbacks(fallback_requests)
        rows = [resolve_numeric_record(r, native.get((r['reference_epoch'], r['pre_date'])),
                    original.get((r['reference_epoch'], r['pre_date'])), fallback.get((r['reference_epoch'], r['pre_date'])),
                    instruments.get(r['reference_epoch']), resolver) for r in requests]
        frame = pd.DataFrame(rows)
        if frame[REQUEST_FIELDS].to_dict('records') != requests:
            raise ValueError('request preservation failed')
        if not set(cfg['contract']['canonical_output_columns']) <= set(frame.columns):
            raise ValueError('frozen canonical field schema differs')
        frame.to_csv(out / 'exact_pre_fields.csv.gz', index=False, compression={'method':'gzip','mtime':0})
        receipt.update(completed=True, completed_at=datetime.now(timezone.utc).isoformat(),
                       elapsed_seconds=time.monotonic()-started, request_rows=len(frame),
                       native_found=int(frame.native_found.sum()), native_missing=int((frame.native_found == 0).sum()),
                       source_numerically_verified=int(frame.source_numerically_verified.sum()),
                       positive_log_observed=int(frame.log_turnover_source_verified.notna().sum()),
                       zero_volume_observed=int(frame.pre_volume.eq(0).sum()),
                       source_numeric_state_counts=dict(Counter(frame.source_numeric_state)),
                       inherited067_state_counts=dict(Counter(frame.inherited067_projection_state)),
                       inherited_rule_state_counts=dict(Counter(frame.rule_state)),
                       settlement_source_read=reader.receipt,
                       fallback_requested_rows=len(fallback_requests),
                       economic_metadata_content_sha256=inputs['economics']['sha256'],
                       source_code_sha256=sha256(__file__), inherited_resolver_sha256=RESOLVER_SHA)
        write_json(out / 'source_read_receipt.json', receipt)
        write_json(out / 'terminal.json', dict(completed=True, elapsed_seconds=receipt['elapsed_seconds'],
                   model_fits=0, cash_replays=0, native_source_queries=1, downloads=0,
                   source_projection_runs_completed=1, request_rows=len(frame)))
        artifact_names = {'exact_pre_fields.csv.gz':'exact_pre_fields', 'source_read_receipt.json':'source_read_receipt',
                          'terminal.json':'terminal', 'source_started.json':'source_started'}
        artifacts = {artifact_names.get(p.name, p.stem): dict(path=str(p), bytes=p.stat().st_size, sha256=sha256(p))
                     for p in sorted(out.iterdir()) if p.is_file()}
        write_json(out / 'manifest.json', dict(schema='stage488_pre_fields_manifest_v1', artifacts=artifacts,
                   source_code=dict(path=str(Path(__file__).resolve()), bytes=Path(__file__).stat().st_size, sha256=sha256(__file__)),
                   protocol_sha256=authorization['protocol_sha256'], model_fits=0, cash_replays=0,
                   historical_first_seen_PIT_verified=False, training_accepted=False, alpha_supported=False))
        return frame, receipt
    except Exception as error:
        receipt.update(completed=False, elapsed_seconds=time.monotonic()-started,
                       error_type=type(error).__name__, error=str(error))
        if reader is not None:
            receipt['settlement_source_read'] = reader.receipt
        write_json(out / 'source_read_receipt.json', receipt)
        write_json(out / 'terminal.json', dict(completed=False, elapsed_seconds=receipt['elapsed_seconds'],
                   error_type=type(error).__name__, error=str(error), model_fits=0, cash_replays=0, downloads=0))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--authorize-source-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    raw = Path(args.protocol).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.protocol_sha256:
        raise ValueError('root exact protocol bytes differ')
    auth = dict(actual_authorized=True, protocol_path=str(Path(args.protocol).resolve()),
                protocol_sha256=args.protocol_sha256, source_sha256=args.authorize_source_sha256)
    frame, receipt = project_fields(json.loads(raw), args.output, authorization=auth)
    print(json.dumps(dict(completed=True, request_rows=len(frame),
                     source_numerically_verified=receipt['source_numerically_verified'],
                     positive_log_observed=receipt['positive_log_observed'],
                     elapsed_seconds=receipt['elapsed_seconds']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
