"""One offline interpretation of immutable338 raw daily timestamps.

This does not broaden arbitrary float nanosecond precision. A float64 timestamp
is admitted only with exact roundtrips, an equal Decimal literal, whole seconds,
Beijing midnight and the already received calendar's explicit trading=True.
No API, old cache, economics, database, model, or cash is imported or used.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

CHINA=ZoneInfo('Asia/Shanghai')
NANO=10**9
CUTOFF='2026-10-16'


def _local(ns):
    d=datetime.fromtimestamp(ns//NANO,timezone.utc).astimezone(CHINA)
    fraction='.'+f'{ns%NANO:09d}' if ns%NANO else ''
    offset=d.strftime('%z')
    return d,d.strftime('%Y-%m-%dT%H:%M:%S')+fraction+offset[:3]+':'+offset[3:]


def recover_timestamp(raw,*,source_dtype,calendar):
    """Never mutate the raw row; successful float recovery is narrowly named."""
    result=dict(recovered_ns=None,trade_date=None,raw_local_iso_recovered=None,
        timestamp_recovery_state='unknown',date_mapping_state='unknown',rejection_reason=None)
    ns=raw.get('raw_ns');integer_path=(isinstance(ns,int) and not isinstance(ns,bool)
        and ns>0 and raw.get('timestamp_state')=='strict_integer_ns')
    if not integer_path:
        value=raw.get('values',{}).get('datetime')
        if source_dtype!='float64' or raw.get('raw_datetime_type')!='float64' or not isinstance(value,float):
            result['rejection_reason']='source_not_float64';return result
        if not math.isfinite(value) or value<=0:
            result['rejection_reason']='nonfinite_or_nonpositive';return result
        if not value.is_integer():
            result['rejection_reason']='noninteger_float';return result
        ns=int(value)
        if float(ns)!=value:
            result['rejection_reason']='float_integer_roundtrip_failed';return result
        if ns%NANO:
            result['rejection_reason']='not_exact_whole_second';return result
        try:
            literal=Decimal(raw['raw_datetime_literal'])
            if not literal.is_finite() or literal!=ns:
                result['rejection_reason']='decimal_literal_disagrees';return result
        except (InvalidOperation,ValueError,KeyError,TypeError):
            result['rejection_reason']='decimal_literal_unreadable';return result
    try:d,local=_local(ns)
    except (ValueError,OverflowError,OSError):
        result['rejection_reason']='timestamp_out_of_datetime_range';return result
    if integer_path:
        result.update(recovered_ns=ns,raw_local_iso_recovered=local,
                      timestamp_recovery_state='original_strict_integer_ns')
    if d.hour!=0 or d.minute!=0 or d.second!=0 or ns%NANO!=0:
        result['rejection_reason']='not_exact_beijing_midnight';return result
    day=d.date().isoformat()
    if calendar.get(day) is not True:
        result['rejection_reason']='stored_calendar_not_confirmed_trading_day';return result
    result.update(recovered_ns=ns,trade_date=day,raw_local_iso_recovered=local,
        timestamp_recovery_state='original_strict_integer_ns' if integer_path else 'recovered_exact_whole_second_float_ns',
        date_mapping_state='operational_midnight_label',date_mapping_rule='tq_daily_midnight_label_calendar_v1')
    return result


def decode_row(raw,*,symbol,source_dtype,calendar,identity_map,received_at,raw_sha256,end_inclusive):
    result=recover_timestamp(raw,source_dtype=source_dtype,calendar=calendar)
    day=result['trade_date'];epoch=identity_map.get(symbol)
    result.update(schema='stage342_date_normalized_row_v1',symbol=symbol,raw_sha256=raw_sha256,
        raw_row_index=raw['row_index'],raw_datetime_literal=raw.get('raw_datetime_literal'),
        raw_datetime_type=raw.get('raw_datetime_type'),raw_ns_original=raw.get('raw_ns'),
        raw_local_iso_original=raw.get('raw_local_iso'),contract_epoch_id=epoch,
        identity_state='known_explicit' if epoch is not None else 'unknown',
        native_values=dict(raw.get('values',{})),
        native_missing_fields=raw.get('raw_missing_fields',[]),
        received_at=received_at,source_completed_at=None,completion_observed_at=None,
        completion_state='no_new_session_completion_proof',vendor_finality='unknown',source_first_published_at=None,
        units_status='provider_raw_units_unverified',canonical_quality_status='unknown',
        model_input_eligible=False,active=False,T0=None,
        window_state='date_unknown' if day is None else 'before_or_at_cutoff' if day<=CUTOFF
            else 'in_window' if day<=end_inclusive else 'after_window')
    return result


def _bound(binding):
    p=Path(binding['path']);raw=p.read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('frozen artifact changed: '+p.name)
    return raw


def _write(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:f.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _binding(path):
    p=Path(path);h=hashlib.sha256()
    with p.open('rb') as f:
        for raw in iter(lambda:f.read(1024*1024),b''):h.update(raw)
    return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=h.hexdigest())


def _line(stream,value):
    stream.write((json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())


def run_offline(authorization,output):
    """Root-authorized one pass of338 raw files. Adapter creates fresh output."""
    auth=(json.loads(Path(authorization).read_text()) if isinstance(authorization,(str,Path)) else dict(authorization))
    if (auth.get('schema')!='stage342_offline_date_authorization_v1' or auth.get('authorized') is not True
            or auth.get('T0') is not None or auth.get('read_budget')!=dict(raw_passes=1,raw_files_max=874,API=0,SQL=0,old_cache=0,economics=0)):
        raise ValueError('exact root offline date authorization required')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh offline decode output required')
    bundle=json.loads(_bound(auth['source_bundle']))
    for b in bundle['sources']:_bound(b)
    inputs=auth['inputs']
    source=json.loads(_bound(inputs['receiver_manifest']))
    calendar=json.loads(_bound(inputs['calendar']))['days']
    identity=json.loads(_bound(inputs['identity_map']))['identity_map']
    receiver_auth=json.loads(_bound(inputs['receiver_authorization']))
    if (source.get('schema')!='stage336_recent_daily_receiver_manifest_v1' or source.get('T0') is not None
            or source.get('duration_seconds')!=86400 or source.get('data_length')!=35
            or len(source['items'])!=874 or len(identity)!=794
            or receiver_auth['normalization_contract']['identity_map']!=identity
            or receiver_auth['normalization_contract']['timestamp_semantics']!='tq_daily_midnight_label_calendar_v1'):
        raise ValueError('fixed338 batch/calendar/explicit794 identity contract mismatch')
    if any(not isinstance(v,bool) for v in calendar.values()):raise ValueError('stored calendar boolean required')
    end=receiver_auth['normalization_contract']['end_inclusive']
    out.mkdir(parents=True)
    reads=0;rows_count=0;by_state=Counter();by_date=Counter();by_reason=Counter();by_dtype=Counter();coverage=[]
    _write(out/'started.json',dict(schema='stage342_offline_decode_started_v1',inputs=inputs,
        source_bundle=auth['source_bundle'],T0=None,new_fit=0,new_cash=0,API=0,SQL=0,raw_passes=1))
    try:
        with gzip.open(out/'date_rows.jsonl.gz','xb',compresslevel=1) as rows_out, \
             gzip.open(out/'raw_artifact_index.jsonl.gz','xb',compresslevel=1) as raw_out, \
             gzip.open(out/'overlap_index.jsonl.gz','xb',compresslevel=1) as overlap_out:
            for symbol,item in sorted(source['items'].items()):
                if 'raw' not in item:raise ValueError('expected archived raw missing for '+symbol)
                raw_binding=item['raw'];reads+=1
                raw=json.loads(_bound(raw_binding))
                if raw.get('schema')!='stage336_raw_daily_symbol_v1' or raw['symbol']!=symbol or raw['duration_seconds']!=86400:
                    raise ValueError('archived symbol/schema mismatch')
                receipt=item.get('receipt',{});received=receipt.get('recorded_at')
                if item.get('received_at')!=received:raise ValueError('original321 receipt timestamp mismatch')
                dtype=raw['dtypes'].get('datetime');by_dtype[str(dtype)]+=1
                _line(raw_out,dict(symbol=symbol,raw=raw_binding,receipt=receipt,
                    source_version=raw.get('source_version'),original_transport_status=item['status'],
                    fresh_ready=item.get('fresh_ready'),source_dtype=dtype))
                stats=Counter();dates=Counter();known_identity=0
                for row in raw['rows']:
                    decoded=decode_row(row,symbol=symbol,source_dtype=dtype,calendar=calendar,
                        identity_map=identity,received_at=received,raw_sha256=raw_binding['sha256'],end_inclusive=end)
                    decoded['fresh_ready']=item.get('fresh_ready',False)
                    decoded['original_transport_status']=item['status']
                    _line(rows_out,decoded);rows_count+=1
                    state=decoded['timestamp_recovery_state'];stats[state]+=1;by_state[state]+=1
                    if decoded['rejection_reason']:by_reason[decoded['rejection_reason']]+=1
                    if decoded['trade_date'] is not None:
                        day=decoded['trade_date'];dates[day]+=1;by_date[day]+=1
                        if decoded['contract_epoch_id'] is not None:known_identity+=1
                        if day<=CUTOFF:
                            _line(overlap_out,dict(symbol=symbol,contract_epoch_id=decoded['contract_epoch_id'],
                                trade_date=day,raw_sha256=raw_binding['sha256'],raw_row_index=row['row_index']))
                coverage.append(dict(symbol=symbol,original_transport_status=item['status'],raw_rows=len(raw['rows']),
                    source_dtype=dtype,recovery_states=dict(stats),dates=dict(sorted(dates.items())),
                    date_known_and_explicit_identity_rows=known_identity,
                    units_status='provider_raw_units_unverified',model_input_eligible=False))
        cov=dict(schema='stage342_date_coverage_v1',raw_files_read=reads,raw_rows=rows_count,source_dtype_files=dict(by_dtype),
            timestamp_recovery_states=dict(by_state),rejection_reasons=dict(by_reason),dates=dict(sorted(by_date.items())),
            symbols=coverage,units_status='provider_raw_units_unverified',canonical_rows_accepted=False,
            new_first_seen_claimed=False,received_at_rule='unchanged338 actual321receipt; decoded_at is not firstseen',
            arbitrary_float_nanosecond_recovery_claimed=False)
        artifacts=dict(date_rows=_binding(out/'date_rows.jsonl.gz'),raw_artifact_index=_binding(out/'raw_artifact_index.jsonl.gz'),
                       overlap_index=_binding(out/'overlap_index.jsonl.gz'),coverage=_write(out/'coverage.json',cov))
        manifest=dict(schema='stage342_offline_date_recovery_manifest_v1',status='completed',inputs=inputs,
            source_bundle=auth['source_bundle'],artifacts=artifacts,raw_files_read=reads,raw_rows=rows_count,
            raw_passes=1,API=0,SQL=0,old_cache=0,economics=0,new_fit=0,new_cash=0,
            T0=None,forward_observations=0,canonical_rows_accepted=False,
            decoded_at=datetime.now(timezone.utc).isoformat(),source338_status_preserved=source['status'])
        _write(out/'manifest.json',manifest)
        return manifest
    except Exception as exc:
        failure=dict(schema='stage342_offline_date_recovery_terminal_v1',status='failed_no_retry',raw_files_read=reads,
            raw_rows=rows_count,error_type=type(exc).__name__,error=str(exc),API=0,SQL=0,old_cache=0,economics=0,
            new_fit=0,new_cash=0,T0=None,forward_observations=0)
        _write(out/'terminal.json',failure);exc.offline_date_receipt=failure;raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--authorization',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    if not args.execute:raise SystemExit('explicit --execute required')
    result=run_offline(args.authorization,args.output)
    print(json.dumps(dict(status=result['status'],raw_files_read=result['raw_files_read'],API=0,new_fit=0,new_cash=0)))
    return 0


if __name__=='__main__':raise SystemExit(main())
