"""Stage174 raw-callback capture/translation for the weekly19 candidate.

No network/CTP/SMTP imports or connection APIs exist here. Stage174's explicit
read-only runner may call publish_stage174_capture AFTER native callbacks are
frozen behind its mutation firewall. The provider independently re-reads the
manifest, raw artifact, callback/query metadata, normalized CSV hashes, source
hashes and account/release/profile binding.

Integrity is not authenticity: these APIs always return production_qualified=False.
Production mode is the default and requires a separately accepted real
production qualification, active release and signed capture authority. Offline fixtures never qualify a
runner, bank receipt, final cashflow statement or live trading account.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import fcntl
import copy
import threading
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

import qmt_roll_weekly19_funding as funding
from qmt_roll_official_live_broker_account_snapshot import _context
from qmt_roll_official_live_late_retry_fill import validate_readonly_query_bundle

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SOURCE_FILES = (
    'examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py',
    'examples/portfolio_backtesting/qmt_roll_weekly19_broker_evidence.py',
    'examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py',
    'examples/portfolio_backtesting/qmt_roll_weekly19_funding.py',
    'examples/portfolio_backtesting/qmt_roll_official_live_broker_account_snapshot.py',
    'examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py',
)
KINDS = ('account', 'positions', 'orders', 'trades')
RAW_NAMES = dict(account='raw_queried_accounts',positions='raw_queried_positions',
                 orders='raw_queried_orders',trades='raw_queried_trades')
CALLBACK_NAMES = dict(account='account_query_callbacks',positions='position_query_callbacks',
                      orders='order_query_callbacks',trades='trade_query_callbacks')
COUNTERS = ('send_order_api_called_count','cancel_order_api_called_count','native_mutation_api_called_count',
            'send_order_api_attempted_count','cancel_order_api_attempted_count','native_mutation_api_attempted_count',
            'order_api_called_count','order_api_attempted_count')


class BrokerEvidenceError(funding.FundingError):
    """A missing/mismatched/unsupported source leaves production fail-closed."""


def _fail(reason):
    raise BrokerEvidenceError(reason)


def _json(data):
    def unique(pairs):
        out = {}
        for key,value in pairs:
            if key in out: _fail('evidence_duplicate_json_key')
            out[key] = value
        return out
    try:
        obj = json.loads(data,object_pairs_hook=unique,parse_constant=lambda _: _fail('evidence_nonfinite_json'))
        if not isinstance(obj,dict): _fail('evidence_json_object_required')
        return obj
    except (ValueError,TypeError,UnicodeError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        _fail('evidence_json_invalid')


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _safe_read(path, *, private=False, shared_lock=False):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts: _fail('evidence_absolute_path_required')
    directory = None
    fd = None
    try:
        directory = os.open('/',os.O_RDONLY|os.O_DIRECTORY)
        for part in path.parent.parts[1:]:
            child = os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory); directory=child
        if private:
            parent = os.fstat(directory)
            if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700:
                _fail('capture_private_parent_required')
        fd = os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            _fail('evidence_regular_unlinked_file_required')
        if private and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
            _fail('capture_private_file_required')
        with os.fdopen(fd,'rb') as stream:
            fd=None
            if shared_lock: fcntl.flock(stream.fileno(),fcntl.LOCK_SH)
            data=stream.read(64_000_001)
        if len(data)>64_000_000: _fail('evidence_file_too_large')
        return data
    except OSError as exc:
        raise BrokerEvidenceError('evidence_path_or_io_invalid') from exc
    finally:
        if fd is not None: os.close(fd)
        if directory is not None: os.close(directory)


def _write_private(path, payload):
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts: _fail('capture_absolute_path_required')
    directory=None; fd=None; temp='.'+path.name+'.'+uuid.uuid4().hex
    try:
        directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
        for part in path.parent.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory); directory=child
        parent=os.fstat(directory)
        if parent.st_uid!=os.geteuid() or stat.S_IMODE(parent.st_mode)!=0o700:
            _fail('capture_private_parent_required')
        # A generation artifact is immutable, never overwrite/reuse one.
        try:
            os.stat(path.name,dir_fd=directory,follow_symlinks=False)
        except FileNotFoundError: pass
        else: _fail('capture_artifact_already_exists')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        with os.fdopen(fd,'wb') as stream:
            fd=None; stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        # link refuses an existing final name even under a competing publisher.
        os.link(temp,path.name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
        os.unlink(temp,dir_fd=directory); os.fsync(directory)
    except OSError as exc:
        raise BrokerEvidenceError('capture_private_write_failed') from exc
    finally:
        if fd is not None: os.close(fd)
        if directory is not None:
            try: os.unlink(temp,dir_fd=directory)
            except FileNotFoundError: pass
            os.close(directory)



_SOURCE_SUFFIXES=frozenset({'.py','.pyi','.c','.cc','.cpp','.h','.hpp','.sh','.rs','.m','.mm'})


def _source_digest(name):
    """Read only a canonical relative code path; never env/private artifacts.

    Extra caller pins are assertions, not comments: unsupported paths fail
    before any file read. _safe_read rejects every symlink component/hardlink.
    The immutable release owns the broader transitive closure.
    """
    if (not isinstance(name,str) or not name or len(name)>4096 or '\\' in name or '\x00' in name):
        _fail('trusted_source_path_invalid')
    relative=Path(name)
    if (relative.is_absolute() or relative.as_posix()!=name
            or '..' in relative.parts or any(part.startswith('.') for part in relative.parts)
            or relative.suffix.lower() not in _SOURCE_SUFFIXES):
        _fail('trusted_source_path_not_supported')
    return _digest(_safe_read(ROOT/relative))

def publish_stage174_capture(summary, rows, *, material_release_id, execution_profile,
                             private_capture_dir, invocation_id, capture_authority_registry=None):
    """Called only by Stage174 main after the generation has been frozen.

    This preserves original callback fields, including doubles, instead of
    reconstructing them from generic AccountData. It makes no success claim.
    """
    funding._text(material_release_id,'release'); funding._text(execution_profile,'profile')
    funding._text(invocation_id,'invocation_id')
    bundle=summary['broker_query_bundle']
    capture=dict(schema='weekly19.stage174-raw-capture.v1',production_qualified=False,
        material_release_id=material_release_id,execution_profile=execution_profile,
        generation_uuid=bundle['generation_uuid'],connection_generation=bundle['snapshot_connection_generation'],
        account_key=bundle['account']['account_fingerprint'],broker_trading_day=bundle['broker_trading_day'],
        generated_at=summary['generated_at'],queries=bundle['queries'],
        runner_provenance=dict(runner='run_ctp_stage174_readonly_probe.py',
            invocation_id=invocation_id,source_commit=summary['source_commit'],
            connect_requested=summary.get('connect_requested'),process_id=os.getpid(),
            source_hashes={name:_source_digest(name) for name in CAPTURE_SOURCE_FILES}),
        order_api_counters={name:summary.get(name) for name in COUNTERS},
        order_api_evidence_window=summary.get('order_api_evidence_window'),
        callbacks={name:rows.get(CALLBACK_NAMES[name],[]) for name in KINDS},
        **{RAW_NAMES[name]:rows.get(RAW_NAMES[name],[]) for name in KINDS})
    payload=funding._canonical(capture)
    path=Path(private_capture_dir)/('weekly19-raw-'+bundle['generation_uuid']+'-'+uuid.uuid4().hex+'.json')
    _write_private(path,payload)
    reference=dict(path=str(path),sha256=_digest(payload),schema=capture['schema'],
                production_qualified=False,generation_uuid=bundle['generation_uuid'])
    if capture_authority_registry is not None:
        _context(summary)
        if (summary.get('status')!='readonly_snapshots_received' or summary.get('connect_requested') is not True
                or bundle.get('complete') is not True
                or any(type(summary.get(name)) is not int or summary[name]!=0 for name in COUNTERS)
                or summary.get('order_api_evidence_window',{}).get('closed')!=1):
            _fail('authority_stage174_native_query_or_api_zero_required')
        authority=_authority_for(capture_authority_registry,capture,funding._time(capture['generated_at']))
        _assert_runner_production_source(capture,authority)
        reference['authority_receipt']=authority._write_receipt(Path(str(path)+'.authority.json'),
            'stage174_query',_query_authority_context(capture),reference['sha256'])
    return reference


def _day(raw):
    if not isinstance(raw,str) or not re.fullmatch(r'[0-9]{8}',raw): _fail('native_trading_day_missing')
    return funding._day(raw[:4]+'-'+raw[4:6]+'-'+raw[6:])


def _native_decimal(value, *, money=True, positive=False):
    if isinstance(value,bool) or not isinstance(value,(str,int,float,Decimal)): _fail('native_decimal_invalid')
    try:
        number=Decimal(str(value))
        if not number.is_finite() or (positive and number<=0): _fail('native_decimal_invalid')
        if money:
            if number!=number.quantize(Decimal('.01')): _fail('native_subcent_money_unsupported')
            out=format(number,'.2f'); funding._money(out)
        else:
            out=format(number,'f')
            if len(out)>40: _fail('native_decimal_invalid')
        return out
    except (InvalidOperation,ValueError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        _fail('native_decimal_invalid')


def _int(value, minimum=0):
    if type(value) is not int or value<minimum: _fail('native_integer_invalid')
    return value


def _fingerprint(raw, account_field):
    return _digest((funding._text(raw['BrokerID'],'broker')+'\0'+funding._text(raw[account_field],'account')).encode())


def _csv(raw):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames and len(reader.fieldnames)!=len(set(reader.fieldnames)): _fail('duplicate_csv_field')
    rows=list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows): _fail('csv_malformed')
    return rows


def _validate_callbacks(capture,bundle,now):
    for kind in KINDS:
        query=bundle['queries'][kind]
        callbacks=capture['callbacks'][kind]
        raw=capture[RAW_NAMES[kind]]
        matched=[row for row in callbacks if row.get('reqid_matched')==1]
        if (len(matched)!=query['callback_count'] or len(raw)!=query['data_callback_count']
                or sum(row.get('has_data') is True for row in matched)!=len(raw)
                or sum(row.get('last') is True for row in matched)!=1):
            _fail('native_callback_count_or_last_mismatch')
        if not matched or matched[-1].get('last') is not True: _fail('native_last_callback_missing')
        for row in matched:
            if (row.get('query_generation_uuid')!=capture['generation_uuid']
                    or row.get('connection_generation')!=capture['connection_generation']
                    or row.get('reqid')!=query['reqid'] or row.get('expected_reqid')!=query['reqid']
                    or type(row.get('error_id')) is not int or row['error_id']!=0):
                _fail('native_callback_identity_or_error_mismatch')
            observed=funding._time(row['received_at'])
            if not funding._time(query['request_sent_at'])<=observed<=funding._time(query['completed_at']):
                _fail('native_callback_timeline_invalid')
            if not 0<=(now-observed).total_seconds()<=300: _fail('native_callback_stale_or_future')


def _load(summary_path,manifest_path,*,expected_account_key,material_release_id,execution_profile,
          now,trusted_source_hashes,require_production_qualification=True,capture_authority_registry=None):
    now=funding._time(now); funding._sha(expected_account_key)
    summary_raw=_safe_read(summary_path); manifest_raw=_safe_read(manifest_path)
    summary=_json(summary_raw); manifest=_json(manifest_raw)
    bundle,account,connection=_context(summary)
    if account!=expected_account_key: _fail('expected_account_mismatch')
    if manifest.get('schema_version')!=2: _fail('complete_v2_manifest_required')
    if Path(manifest['summary_binding']['path'])!=Path(summary_path) or Path(bundle['manifest_path'])!=Path(manifest_path):
        _fail('capture_summary_manifest_path_mismatch')
    ref=manifest.get('weekly19_capture')
    if not isinstance(ref,dict) or ref!=bundle.get('weekly19_capture'): _fail('raw_capture_reference_missing_or_mismatch')
    raw=_safe_read(ref['path'],private=True)
    if _digest(raw)!=ref.get('sha256'): _fail('raw_capture_sha256_mismatch')
    capture=_json(raw)
    if capture.get('schema')!='weekly19.stage174-raw-capture.v1' or capture.get('production_qualified') is not False:
        _fail('raw_capture_schema_or_self_qualification_invalid')
    if any(capture.get(key)!=expected for key,expected in
           (('material_release_id',material_release_id),('execution_profile',execution_profile),
            ('account_key',account),('generation_uuid',bundle['generation_uuid']),
            ('connection_generation',connection),('broker_trading_day',bundle['broker_trading_day']),
            ('generated_at',summary['generated_at']),('queries',bundle['queries']))):
        _fail('raw_capture_identity_or_queries_mismatch')
    runner=capture['runner_provenance']
    if (runner.get('runner')!='run_ctp_stage174_readonly_probe.py'
            or runner.get('invocation_id')!=summary.get('invocation_id') or not runner.get('invocation_id')
            or runner.get('source_commit')!=summary.get('source_commit')
            or not re.fullmatch('[0-9a-f]{40}',runner.get('source_commit',''))
            or runner.get('connect_requested') is not True or summary.get('connect_requested') is not True):
        _fail('capture_runner_provenance_mismatch')
    if not isinstance(trusted_source_hashes,dict) or not set(CAPTURE_SOURCE_FILES).issubset(trusted_source_hashes):
        _fail('capture_mandatory_source_pin_missing')
    captured_sources=runner.get('source_hashes')
    if not isinstance(captured_sources,dict) or set(captured_sources)!=set(CAPTURE_SOURCE_FILES):
        _fail('capture_mandatory_source_identity_mismatch')
    actual_sources={}
    for name,expected_hash in trusted_source_hashes.items():
        funding._sha(expected_hash)
        actual_sources[name]=_source_digest(name)
        if actual_sources[name]!=expected_hash:
            _fail('capture_source_hash_mismatch_or_untrusted')
    for name in CAPTURE_SOURCE_FILES:
        if captured_sources[name]!=actual_sources[name]:
            _fail('capture_source_hash_mismatch_or_untrusted')
    if (summary.get('real_order_enabled') is not False
            or any(type(summary.get(name)) is not int or summary[name]!=0
                   or capture['order_api_counters'].get(name)!=0 for name in COUNTERS)
            or capture.get('order_api_evidence_window')!=summary.get('order_api_evidence_window')
            or summary.get('order_api_evidence_window',{}).get('closed')!=1):
        _fail('capture_order_firewall_or_counter_invalid')
    generated=funding._time(summary['generated_at'])
    if not 0<=(now-generated).total_seconds()<=300: _fail('capture_stale_or_future')
    for query in bundle['queries'].values():
        sent=funding._time(query['request_sent_at']); completed=funding._time(query['completed_at'])
        if not sent<=completed<=generated or not 0<=(now-sent).total_seconds()<=300:
            _fail('capture_query_stale_or_future')
    _validate_callbacks(capture,bundle,now)
    rows={}; artifacts={}; frozen={Path(summary_path):summary_raw,Path(manifest_path):manifest_raw,Path(ref['path']):raw}
    for name in ('orders','trades','positions'):
        reference=manifest['artifacts'][name]
        if reference!=bundle['artifacts'][name]: _fail('normalized_artifact_binding_mismatch')
        data=_safe_read(reference['path']); frozen[Path(reference['path'])]=data
        normalized=_csv(data); rows[name]=normalized
        if _digest(data)!=reference['sha256'] or len(normalized)!=reference['row_count']:
            _fail('normalized_artifact_count_or_hash_mismatch')
        artifacts[name]=dict(row_count=len(normalized),sha256=_digest(data),
            generation_uuids=sorted({r.get('query_generation_uuid','') for r in normalized}),
            account_fingerprints=sorted({_digest((r.get('broker_id','')+'\0'+r.get('account_id','')).encode()) for r in normalized}))
    artifacts['trades'].update(order_mapping_complete=all(r.get('order_mapping_complete')=='1' and bool(r.get('vt_orderid')) for r in rows['trades']),
        stable_trade_identity_complete=all(r.get('stable_trade_identity_complete')=='1' and bool(r.get('broker_trade_identity')) for r in rows['trades']))
    valid,reason,_,_=validate_readonly_query_bundle(readonly_summary=summary,bundle_manifest=manifest,bundle_evidence=dict(artifacts=artifacts))
    if not valid: _fail(reason)
    if any(_safe_read(path,private=path==Path(ref['path']))!=data for path,data in frozen.items()):
        _fail('capture_changed_during_read')
    if require_production_qualification or capture_authority_registry is not None:
        receipt=manifest.get('weekly19_capture_authority')
        if (capture_authority_registry is None or not isinstance(receipt,dict)
                or receipt!=bundle.get('weekly19_capture_authority') or receipt!=ref.get('authority_receipt')):
            _fail('production_capture_qualification_missing:registry_or_runner_receipt')
        authority=_authority_for(capture_authority_registry,capture,now)
        _assert_runner_production_source(capture,authority)
        capture['_verified_authority']=authority._verify_receipt(receipt,'stage174_query',_query_authority_context(capture),ref['sha256'])
    return summary,manifest,capture,rows


def _envelope(raw):
    payload=funding._canonical(raw).decode()
    return dict(raw_payload=payload,raw_sha256=_digest(payload.encode()))


def _common(capture,query):
    return dict(account_key=capture['account_key'],material_release_id=capture['material_release_id'],
        execution_profile=capture['execution_profile'],observed_at=query['completed_at'],
        trading_day=_day(capture['broker_trading_day']),generation_uuid=capture['generation_uuid'],
        query_reqid=query['reqid'],query_complete=True,query_error_rows=query['error_rows'],
        query_last_seen=query['last_seen'],production_qualified=False)


def _symbol(raw):
    symbol=funding._text(raw['InstrumentID'],'symbol'); exchange=raw['ExchangeID']
    if not re.fullmatch('[A-Za-z]+[0-9]{3,4}',symbol) or exchange not in ('SHFE','DCE','CZCE','INE','CFFEX','GFEX'):
        _fail('native_symbol_invalid')
    return symbol+'.'+exchange



def _native_offset(flag):
    value={'0':'open','1':'close','3':'closetoday','4':'closeyesterday'}.get(flag)
    if value is None: _fail('native_offset_enum_invalid')
    return value


def _business_offset(broker_offset):
    return 'open' if broker_offset=='open' else 'close'

def _public(summary,manifest,capture,rows):
    accounts=capture['raw_queried_accounts']
    if len(accounts)!=1: _fail('unique_native_cny_account_required')
    account=accounts[0]
    if _fingerprint(account,'AccountID')!=capture['account_key'] or account.get('CurrencyID')!='CNY':
        _fail('native_account_identity_or_currency_invalid')
    if _day(account['TradingDay'])!=_day(capture['broker_trading_day']): _fail('native_account_trading_day_mismatch')
    common=_common(capture,capture['queries']['account'])
    account_raw=dict(common,schema='weekly19.ctp-account.v1',source_kind='ctp_account_callback',
        BrokerID=account['BrokerID'],AccountID=account['AccountID'],CurrencyID='CNY',
        **{name:_native_decimal(account[name]) for name in ('Balance','Available','Deposit','Withdraw','CurrMargin')})
    if account.get('PositionProfit') is not None:
        account_raw['PositionProfit']=_native_decimal(account['PositionProfit'])
    if funding._money(account_raw['Deposit'])<0 or funding._money(account_raw['Withdraw'])<0:
        _fail('negative_native_cashflow')
    totals={}
    for row in capture['raw_queried_positions']:
        if _fingerprint(row,'InvestorID')!=capture['account_key'] or _day(row['TradingDay'])!=_day(capture['broker_trading_day']):
            _fail('native_position_account_or_day_mismatch')
        volume=_int(row['Position'])
        # Raw Position is authoritative; YdPosition is not added a second time.
        _int(row['TodayPosition']); _int(row['YdPosition'])
        if row['PosiDirection'] not in ('2','3'): _fail('native_position_direction_invalid')
        key=(_symbol(row),'long' if row['PosiDirection']=='2' else 'short')
        totals[key]=totals.get(key,0)+volume
    position_rows=[dict(vt_symbol=key[0],direction=key[1],volume=vol) for key,vol in sorted(totals.items()) if vol]
    order_rows=[]
    for row in capture['raw_queried_orders']:
        if _fingerprint(row,'InvestorID')!=capture['account_key'] or _day(row['TradingDay'])!=_day(capture['broker_trading_day']):
            _fail('native_order_account_or_day_mismatch')
        direction={'0':'long','1':'short'}.get(row['Direction'])
        broker_offset=_native_offset(row['CombOffsetFlag'])
        offset=_business_offset(broker_offset)
        status={'0':'all_traded','1':'part_traded','2':'cancelled','3':'not_traded','4':'cancelled','5':'cancelled','a':'submitting'}.get(row['OrderStatus'])
        if not direction or not offset or not status: _fail('native_order_enum_invalid')
        volume=_int(row['VolumeTotalOriginal'],1); traded=_int(row['VolumeTraded'])
        if traded>volume: _fail('native_order_traded_exceeds_volume')
        order_id='CTP.'+str(_int(row['FrontID'],1))+'_'+str(_int(row['SessionID'],1))+'_'+funding._text(row['OrderRef'],'orderref')
        order_rows.append(dict(broker_order_id=order_id,vt_symbol=_symbol(row),direction=direction,offset=offset,
                               business_offset=offset,broker_offset=broker_offset,native_offset_flag=row['CombOffsetFlag'],
                               volume=volume,traded=traded,status=status))
    return dict(account=_envelope(account_raw),
        positions=_envelope(dict(_common(capture,capture['queries']['positions']),schema='weekly19.ctp-positions.v1',source_kind='ctp_position_query',positions=position_rows)),
        orders=_envelope(dict(_common(capture,capture['queries']['orders']),schema='weekly19.ctp-orders.v1',source_kind='ctp_order_query',orders=order_rows)),
        production_qualified=False,source_qualified=bool(capture.get('_verified_authority')),provenance=dict(raw_capture=manifest['weekly19_capture'],
            capture_authority=copy.deepcopy(capture.get('_verified_authority')),
            generation_uuid=capture['generation_uuid'],source_hashes=capture['runner_provenance']['source_hashes'],
            qualification_status='source_authority_verified' if capture.get('_verified_authority') else 'not_qualified_no_accepted_capture_authority'))


def load_broker_snapshot(summary_path,manifest_path,**policy):
    """Load/translate only a complete same-generation capture, default fail-closed."""
    try:
        return _public(*_load(summary_path,manifest_path,**policy))
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,csv.Error) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_evidence_invalid:'+str(exc)) from exc


def load_broker_carry_in_positions(summary_path,manifest_path,**policy):
    """Retain native aggregate cost for an explicit first-start adoption only.

    Uses the very same admission as the real account snapshot. A normalized
    zero price is never substituted for native OpenCost; this private envelope
    does not attest a historical trade, its owner or its protection state.
    """
    try:
        admitted=_load(summary_path,manifest_path,**policy)
        summary,manifest,capture,rows=admitted
        snapshot=_public(*admitted)
        return _envelope(dict(_common(capture,capture['queries']['positions']),
            schema='weekly19.ctp-carry-in-positions.v1',source_kind='ctp_position_query',
            native_positions=copy.deepcopy(capture['raw_queried_positions']),
            normalized_positions_sha256=snapshot['positions']['raw_sha256'],
            raw_capture_sha256=manifest['weekly19_capture']['sha256']))
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,csv.Error) as exc:
        if isinstance(exc,BrokerEvidenceError):raise
        raise BrokerEvidenceError('broker_carry_in_evidence_invalid:'+str(exc)) from exc


def read_account_snapshot(account_envelope, *, expected_account_key, material_release_id,
                          now, max_age_seconds=300):
    """Conditionally parse one account; never confer broker/source qualification.

    PositionProfit may be absent; then unrealized_pnl_fen is explicitly None.
    Balance already includes MTM and must NOT have PositionProfit added again.
    """
    try:
        now=funding._time(now)
        if type(max_age_seconds) is not int or not 0<=max_age_seconds<=300:
            _fail('account_max_age_invalid')
        state=dict(account_key=funding._sha(expected_account_key),material_release_id=material_release_id)
        result=funding._broker(account_envelope,state,now)
        raw=funding._parse(account_envelope,'weekly19.ctp-account.v1','ctp_account_callback')
        if (type(raw.get('query_error_rows')) is not int or raw['query_error_rows']!=0
                or raw.get('query_last_seen') is not True):
            _fail('account_query_error_or_last_invalid')
        if (now-funding._time(raw['observed_at'])).total_seconds()>max_age_seconds:
            _fail('account_snapshot_stale')
        margin=funding._money(raw['CurrMargin'],nonnegative=True)
        pnl=funding._money(raw['PositionProfit']) if raw.get('PositionProfit') is not None else None
        result.update(equity_fen=result['balance_fen'],available_fen=funding._money(raw['Available']),
            unrealized_pnl_fen=pnl,margin_fen=margin,currency=raw['CurrencyID'],account_key=raw['account_key'],
            material_release_id=raw['material_release_id'],production_qualified=False,
            source_status='conditionally_parsed_origin_not_qualified')
        return result
    except (ValueError,KeyError,TypeError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_account_read_invalid:'+str(exc)) from exc


def load_broker_fills(summary_path,manifest_path,execution_ledger_rows,**policy):
    """Map raw queried trades to exactly one durable intent by native order ID.

    A query response is labelled onRspQryTrade, never misrepresented as an
    onRtnTrade push. The actual quantity/price/time come exclusively from CTP.
    Ledger fields only establish the stable order -> original intent mapping.
    Business offset is open|close; native close/closetoday/closeyesterday are
    retained separately and must match the unique original native order flag.
    """
    try:
        summary,manifest,capture,normalized=_load(summary_path,manifest_path,**policy)
        _public(summary,manifest,capture,normalized)
        _require_verified_execution_bindings(execution_ledger_rows,policy.get('require_production_qualification',True))
        fills=[]; seen=set()
        raw_trades=capture['raw_queried_trades']
        if len(raw_trades)!=len(normalized['trades']): _fail('native_trade_count_mismatch')
        for native,row in zip(raw_trades,normalized['trades']):
            if (_fingerprint(native,'InvestorID')!=capture['account_key']
                    or _day(native['TradingDay'])!=_day(capture['broker_trading_day'])):
                _fail('native_trade_account_or_day_mismatch')
            stable='ctp:'+native['BrokerID']+':'+native['InvestorID']+':'+native['ExchangeID']+':'+native['TradeDate']+':'+native['OrderSysID'].strip()+':'+native['TradeID'].strip()
            if stable!=row['broker_trade_identity'] or not native['TradeID'].strip() or stable in seen:
                _fail('native_trade_identity_invalid_or_duplicate')
            seen.add(stable)
            native_matches=[order for order in capture['raw_queried_orders']
                if order.get('ExchangeID')==native['ExchangeID']
                and str(order.get('OrderSysID','')).strip()==native['OrderSysID'].strip()]
            native_ids={'CTP.'+str(_int(order['FrontID'],1))+'_'+str(_int(order['SessionID'],1))+'_'+funding._text(order['OrderRef'],'orderref')
                        for order in native_matches}
            if len(native_matches)!=1 or len(native_ids)!=1 or row['vt_orderid'] not in native_ids:
                _fail('native_trade_order_mapping_mismatch')
            matches=[entry for entry in execution_ledger_rows if entry.get('broker_order_id')==row['vt_orderid']]
            if len(matches)!=1: _fail('trade_original_intent_mapping_not_unique')
            entry=matches[0]
            symbol=_symbol(native); direction={'0':'long','1':'short'}.get(native['Direction'])
            if direction is None: _fail('native_trade_direction_enum_invalid')
            broker_offset=_native_offset(native['OffsetFlag']); offset=_business_offset(broker_offset)
            native_order=native_matches[0]
            if (native_order['CombOffsetFlag']!=native['OffsetFlag'] or native_order['Direction']!=native['Direction']):
                _fail('native_trade_order_direction_or_offset_mismatch')
            if 'broker_offset' in entry and entry['broker_offset']!=broker_offset:
                _fail('ledger_broker_offset_mismatch')
            for key,value in (('account_key',capture['account_key']),('material_release_id',capture['material_release_id']),
                    ('execution_profile',capture['execution_profile']),('vt_symbol',symbol),('direction',direction),('offset',offset)):
                if entry.get(key)!=value: _fail('trade_original_intent_binding_mismatch')
            delivery=funding._text(entry['intent_id'],'delivery_intent_id')
            intent=funding._text(entry.get('planned_intent_id') or delivery,'intent_id'); signal=funding._text(entry['signal_order_id'],'signal_order_id')
            if entry['signal_identity'].get('intent_id')!=intent or entry['signal_identity'].get('signal_order_id')!=signal:
                _fail('trade_signal_identity_mismatch')
            executed=datetime.strptime(native['TradeDate']+' '+native['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
            if executed>funding._time(policy['now']): _fail('native_trade_future')
            if 'execution_batch_proof' in entry:
                _order_intent_binding(native_order,execution_ledger_rows,dict(account_key=capture['account_key'],material_release_id=capture['material_release_id'],execution_profile=capture['execution_profile'],trading_day=_day(capture['broker_trading_day'])))
            fills.append(_envelope(dict(_common(capture,capture['queries']['trades']),**_binding_batch_fields(entry,native_order),schema='weekly19.ctp-trade.v1',
                source_kind='ctp_trade_callback',source_callback='onRspQryTrade',intent_id=intent,delivery_intent_id=delivery,signal_order_id=signal,
                signal_identity=entry['signal_identity'],broker_order_id=row['vt_orderid'],trade_id=stable,vt_symbol=symbol,
                direction=direction,offset=offset,business_offset=offset,broker_offset=broker_offset,native_offset_flag=native['OffsetFlag'],
                volume=_int(native['Volume'],1),price=_native_decimal(native['Price'],money=False,positive=True),
                trade_datetime=executed.isoformat(),execution_datetime=executed.isoformat(),
                raw_capture_sha256=manifest['weekly19_capture']['sha256'])))
        return fills
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_fill_evidence_invalid:'+str(exc)) from exc

def _native_order_id(native):
    reference=funding._text(native['OrderRef'].strip(),'order_ref')
    if not re.fullmatch('[0-9]+',reference): _fail('native_order_ref_invalid')
    return 'CTP.'+str(_int(native['FrontID'],1))+'_'+str(_int(native['SessionID'],1))+'_'+reference


def _native_order_status(native):
    status=native['OrderStatus']; submit=native.get('OrderSubmitStatus')
    volume=_int(native['VolumeTotalOriginal'],1); traded=_int(native['VolumeTraded'])
    if traded>volume: _fail('native_order_traded_exceeds_volume')
    if submit=='4':
        if traded!=0: _fail('rejected_order_has_fills')
        return 'rejected'
    if status=='a' and submit in ('0','3'): return 'accepted'
    values={'0':'filled','1':'partially_filled','2':'cancelled','3':'working','4':'cancelled','5':'cancelled'}
    mapped=values.get(status)
    if mapped is None: _fail('native_order_status_unknown')
    if (mapped=='filled' and traded!=volume) or (mapped=='partially_filled' and not 0<traded<volume):
        _fail('native_order_status_volume_conflict')
    return mapped


# Logical quota plans never contain a future broker order ID.
_BATCH_FIELDS=('execution_batch_id','api_slot_batch_id','api_slot_batch_count','approved_parent_volume',
    'expected_children','expected_children_sha256','child_order_id','child_order_index',
    'execution_batch_proof','execution_batch_proof_sha256')
_BINDINGS_TOKEN=object()


class _VerifiedExecutionBindings(list):
    def __init__(self,token,rows,source):
        if token is not _BINDINGS_TOKEN: _fail('private_execution_ledger_loader_required')
        super().__init__(copy.deepcopy(rows));self._source=copy.deepcopy(source);self._binding_sha256=funding._hash(rows);self._source_sha256=funding._hash(source)
    def __deepcopy__(self,memo): return copy.deepcopy(list(self),memo)
    def _immutable(self,*args,**kwargs): _fail('verified_execution_bindings_immutable')
    append=extend=insert=pop=remove=clear=reverse=sort=__setitem__=__delitem__=__iadd__=__imul__=_immutable


def _require_verified_execution_bindings(rows,required):
    if not required: return
    if (not isinstance(rows,_VerifiedExecutionBindings) or rows._binding_sha256!=funding._hash(list(rows))
            or rows._source_sha256!=funding._hash(rows._source)
            or not all('execution_batch_proof' in row for row in rows)):
        _fail('production_execution_ledger_source_missing')


def load_execution_order_intent_bindings(path,*,expected_account_key,material_release_id,execution_profile):
    """Read the real private complete JSONL under SHLOCK; never accept a flag.

    Record checksums detect corruption, not an adversarial same-owner forgery;
    there is no ledger hash-chain. Runner/registry/release qualification remains
    a separate source authority. Returned process-local rows cannot be JSON-made.
    """
    raw=_safe_read(path,private=True,shared_lock=True)
    if raw and not raw.endswith(b'\n'): _fail('execution_ledger_incomplete_last_record')
    try:
        rows=[_json(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
        from qmt_roll_official_live_execution_ledger import _parse_ledger_lines
        parsed=_parse_ledger_lines(raw.decode('utf-8').splitlines())
        if rows!=parsed: _fail('execution_ledger_integrity_error')
        bindings=derive_order_intent_bindings(rows,expected_account_key=expected_account_key,
            material_release_id=material_release_id,execution_profile=execution_profile)
        source=dict(schema='weekly19.execution-ledger-source.v1',raw_sha256=_digest(raw),row_count=len(rows),binding_sha256=funding._hash(bindings))
        return _VerifiedExecutionBindings(_BINDINGS_TOKEN,bindings,source)
    except (UnicodeError,ValueError,KeyError,TypeError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('execution_ledger_read_invalid:'+type(exc).__name__) from exc


def _record_integrity(row):
    from qmt_roll_official_live_execution_ledger import _record_checksum
    if not row.get('record_checksum') or funding._sha(row['record_checksum'])!=_record_checksum(row):
        _fail('execution_batch_record_checksum_invalid')


def _batch_manifest(row,context):
    manifest=row.get('weekly19_batch_manifest')
    keys={'schema','intent_id','planned_intent_id','signal_identity','intent_payload_sha256','parent_intent_fingerprint',
        'spool_lease_token','service_generation','connection_generation','approved_parent_volume','expected_children','expected_children_sha256'}
    if type(manifest) is not dict or set(manifest)!=keys or manifest['schema']!='weekly19.physical-batch-manifest.v1':
        _fail('execution_batch_manifest_invalid')
    if not str(row.get('source','')).startswith('weekly19_'): _fail('execution_batch_source_invalid')
    for name in ('intent_id','planned_intent_id','spool_lease_token','service_generation','connection_generation'):
        funding._text(manifest[name],'batch_'+name)
    funding._sha(manifest['intent_payload_sha256'])
    for key,value in context.items():
        aliases=('account_key','account_fingerprint') if key=='account_key' else (key,)
        actual=[row[name] for name in aliases if row.get(name)]
        if not actual or any(item!=value for item in actual): _fail('execution_batch_scope_mismatch')
    for key in ('intent_id','planned_intent_id','signal_identity','intent_payload_sha256','parent_intent_fingerprint',
                'spool_lease_token','service_generation','connection_generation'):
        if row.get(key)!=manifest[key]: _fail('execution_batch_identity_mismatch')
    if manifest['signal_identity'].get('intent_id')!=manifest['planned_intent_id']: _fail('execution_batch_original_identity_mismatch')
    for key in ('approved_parent_volume','expected_children','expected_children_sha256'):
        if row.get(key)!=manifest[key]: _fail('execution_batch_repeated_manifest_mismatch')
    children=manifest['expected_children'];count=len(children) if isinstance(children,list) else 0
    if not 1<=count<=100 or funding._sha(manifest['expected_children_sha256'])!=funding._hash(children):
        _fail('execution_batch_children_digest_invalid')
    fingerprint=funding._sha(manifest['parent_intent_fingerprint']);total=0
    direction=row.get('planned_direction');offset=row.get('planned_offset')
    if direction not in ('long','short') or offset not in ('open','close'): _fail('execution_batch_planned_enum_invalid')
    for index,child in enumerate(children):
        if (type(child) is not dict or set(child)!={'child_order_id','child_order_index','volume','broker_offset','vt_symbol','direction','trading_date'}
                or child['child_order_id']!=fingerprint+':'+str(index+1)+'/'+str(count)
                or type(child['child_order_index']) is not int or child['child_order_index']!=index
                or child['vt_symbol']!=row['vt_symbol'] or child['direction']!=direction
                or child['trading_date']!=manifest['signal_identity']['trading_date']
                or child['broker_offset'] not in ('open','close','closetoday','closeyesterday')
                or _business_offset(child['broker_offset'])!=offset): _fail('execution_batch_child_descriptor_invalid')
        total+=_int(child['volume'],1)
    if _int(manifest['approved_parent_volume'],1)!=total: _fail('execution_batch_parent_volume_invalid')
    planned=Decimal(str(row['planned_volume']))
    if not planned.is_finite() or planned!=planned.to_integral_value() or total>planned: _fail('execution_batch_exceeds_parent_plan')
    if offset=='close' and total!=planned: _fail('execution_batch_close_parent_volume_mismatch')
    return manifest


def _batch_row_child(row,manifest):
    children=manifest['expected_children'];index=row['child_order_index']
    if type(index) is not int or not 0<=index<len(children): _fail('execution_batch_child_index_invalid')
    child=children[index]
    if row.get('child_order_id')!=child['child_order_id'] or row.get('child_order_count')!=len(children):
        _fail('execution_batch_child_identity_invalid')
    requested=row.get('child_order_volume',row.get('broker_order_volume'))
    if Decimal(str(requested))!=child['volume']: _fail('execution_batch_child_request_volume_mismatch')
    return child


def _derive_execution_batches(rows,context):
    from qmt_roll_official_live_execution_ledger import _api_slot_usage
    quotas={};proofs={};child_brokers={};native_indices={}
    for index,row in enumerate(rows):
        if type(row) is not dict: _fail('generic_ledger_row_invalid')
        if str(row.get('event_type','')).startswith('ledger_') and str(row.get('event_type','')).endswith('_error'):
            _fail('execution_ledger_integrity_error')
        if row.get('event_type')!='api_slot_reserved' or 'weekly19_batch_manifest' not in row: continue
        manifest=_batch_manifest(row,context);_record_integrity(row)
        batchid=row['api_slot_batch_id'];children=row['api_slot_batch_children'];count=len(manifest['expected_children'])
        if (not isinstance(batchid,str) or not re.fullmatch('[0-9a-f]{24}',batchid) or batchid in quotas
                or row.get('api_slot_type')!='send_order' or type(row.get('api_slot_reserved')) is not int or row['api_slot_reserved']!=1
                or type(row.get('api_slot_batch_count')) is not int or row['api_slot_batch_count']!=count
                or type(row.get('api_slot_reserved_count')) is not int or row['api_slot_reserved_count']!=count
                or not isinstance(children,list) or len(children)!=count): _fail('execution_batch_quota_transaction_invalid')
        for child_index,nested in enumerate(children):
            if (_batch_manifest(nested,context)!=manifest or nested.get('api_slot_batch_id') not in ('',batchid)
                    or nested.get('child_order_index')!=child_index): _fail('execution_batch_quota_child_mismatch')
            _batch_row_child(nested,manifest)
            for name in ('source','official_live_version','ruleset_version','physical_epoch_id','reservation_record_checksum'):
                if nested.get(name)!=row.get(name): _fail('execution_batch_quota_source_identity_conflict')
        expected=funding._hash(dict(target_date=row['target_date'],slot_type='send_order',
            usage_before=_api_slot_usage(rows[:index],row['target_date'],'send_order'),base_events=children))[:24]
        if batchid!=expected: _fail('execution_batch_quota_id_mismatch')
        quotas[batchid]=(index,row,manifest)
    for index,row in enumerate(rows):
        claims=any(key in row for key in ('weekly19_batch_manifest','expected_children','execution_batch_id')) or bool(row.get('api_slot_batch_id'))
        if not claims: continue
        if row.get('event_type')=='api_slot_reserved': continue
        if row.get('material_release_id')!=context['material_release_id'] or row.get('execution_profile')!=context['execution_profile']:
            continue
        batchid=row.get('api_slot_batch_id',row.get('execution_batch_id'))
        if batchid not in quotas: _fail('execution_batch_quota_missing')
        quota_index,quota,manifest=quotas[batchid]
        if index<=quota_index: _fail('execution_batch_native_precedes_quota')
        if _batch_manifest(row,context)!=manifest: _fail('execution_batch_event_manifest_conflict')
        for name in ('source','official_live_version','ruleset_version','physical_epoch_id','reservation_record_checksum'):
            if (name=='reservation_record_checksum' and name not in row
                    and row.get('event_type')!='native_order_identity_persisted_before_insert'): continue
            if row.get(name)!=quota.get(name): _fail('execution_batch_event_source_identity_conflict')
        child=_batch_row_child(row,manifest)
        broker=row.get('broker_order_id') or row.get('vt_orderid')
        if not broker: continue
        if row.get('event_type')!='native_order_identity_persisted_before_insert': continue
        _record_integrity(row)
        if type(row.get('native_api_called')) is not int or row['native_api_called']!=0: _fail('execution_batch_before_insert_proof_invalid')
        _int(row['req_order_insert_reqid'],1)
        if (Decimal(str(row['broker_order_volume']))!=child['volume'] or row.get('broker_offset')!=child['broker_offset']
                or _native_offset(row['native_offset_flag'])!=child['broker_offset']): _fail('execution_batch_native_child_mismatch')
        native_id='CTP.'+str(row['front_id'])+'_'+str(row['session_id'])+'_'+str(row['order_ref'])
        if native_id!=broker: _fail('execution_batch_native_broker_id_mismatch')
        child_key=(batchid,child['child_order_id'])
        if broker in proofs or child_key in child_brokers: _fail('execution_batch_native_binding_not_unique')
        child_brokers[child_key]=broker;native_indices[broker]=index
        proof=dict(schema='weekly19.execution-batch-proof.v1',quota_record_checksum=quota['record_checksum'],
            quota_record_sha256=funding._hash(quota),native_identity_record_checksum=row['record_checksum'],native_identity_record_sha256=funding._hash(row))
        proofs[broker]=dict(execution_batch_id=batchid,api_slot_batch_id=batchid,api_slot_batch_count=len(manifest['expected_children']),
            approved_parent_volume=manifest['approved_parent_volume'],expected_children=copy.deepcopy(manifest['expected_children']),
            expected_children_sha256=manifest['expected_children_sha256'],child_order_id=child['child_order_id'],child_order_index=child['child_order_index'],
            execution_batch_proof=proof,execution_batch_proof_sha256=funding._hash(proof))
    for index,row in enumerate(rows):
        if (row.get('event_type')=='api_slot_reserved' or row.get('material_release_id')!=context['material_release_id']
                or row.get('execution_profile')!=context['execution_profile']): continue
        if not (row.get('api_slot_batch_id') or any(key in row for key in ('weekly19_batch_manifest','expected_children','execution_batch_id'))): continue
        broker=row.get('broker_order_id') or row.get('vt_orderid')
        if not broker: continue
        if broker not in proofs: _fail('execution_batch_native_before_insert_missing')
        proof=proofs[broker]
        if index<native_indices[broker]: _fail('execution_batch_callback_precedes_native_identity')
        if (row.get('api_slot_batch_id')!=proof['api_slot_batch_id'] or row.get('child_order_id')!=proof['child_order_id']
                or row.get('child_order_index')!=proof['child_order_index']): _fail('execution_batch_callback_child_mapping_conflict')
    return proofs


def _binding_batch_fields(entry,native=None):
    present=[name for name in _BATCH_FIELDS if name in entry]
    if not present: return {}
    if len(present)!=len(_BATCH_FIELDS): _fail('execution_batch_binding_fields_missing')
    proof=entry['execution_batch_proof']
    if (proof.get('schema')!='weekly19.execution-batch-proof.v1' or funding._hash(proof)!=entry['execution_batch_proof_sha256']
            or entry['execution_batch_id']!=entry['api_slot_batch_id'] or funding._hash(entry['expected_children'])!=entry['expected_children_sha256']
            or len(entry['expected_children'])!=entry['api_slot_batch_count']): _fail('execution_batch_binding_proof_invalid')
    for name in ('quota_record_checksum','quota_record_sha256','native_identity_record_checksum','native_identity_record_sha256'): funding._sha(proof[name])
    children=entry['expected_children'];index=entry['child_order_index']
    if type(index) is not int or not 0<=index<len(children): _fail('execution_batch_binding_child_invalid')
    child=children[index]
    if child['child_order_id']!=entry['child_order_id']: _fail('execution_batch_binding_child_invalid')
    if native is not None and (child['volume']!=native['VolumeTotalOriginal'] or child['broker_offset']!=_native_offset(native['CombOffsetFlag'])
            or child['vt_symbol']!=_symbol(native) or child['direction']!={'0':'long','1':'short'}.get(native['Direction'])
            or child['trading_date']!=_day(native['TradingDay'])): _fail('execution_batch_native_descriptor_mismatch')
    return {name:copy.deepcopy(entry[name]) for name in _BATCH_FIELDS}


def derive_order_intent_bindings(execution_ledger_rows, *, expected_account_key,
                                 material_release_id, execution_profile):
    """Fold verified generic JSONL events into unique native-order bindings.

    This establishes identity only, never broker provenance or completion.
    Reserve/API-slot rows without a native ID cannot bind a broker callback.
    Same semantic events collapse; conflicting identity or original order caps
    fail closed. Trade callback ``volume`` is deliberately NOT an order cap.
    Pass this result to query/native loaders and collector.bind_execution_ledger_rows.
    """
    try:
        funding._sha(expected_account_key);funding._text(material_release_id,'release')
        funding._text(execution_profile,'profile')
        if not isinstance(execution_ledger_rows,list): _fail('generic_ledger_rows_invalid')
        context=dict(account_key=expected_account_key,material_release_id=material_release_id,execution_profile=execution_profile)
        batch_proofs=_derive_execution_batches(execution_ledger_rows,context)
        bindings={}
        for row in execution_ledger_rows:
            if type(row) is not dict: _fail('generic_ledger_row_invalid')
            broker_ids=[row[key] for key in ('broker_order_id','vt_orderid') if row.get(key)]
            if not broker_ids: continue
            if len(set(broker_ids))!=1: _fail('generic_ledger_broker_id_alias_conflict')
            account_values=[row[key] for key in ('account_key','account_fingerprint') if row.get(key)]
            if len(set(account_values))>1: _fail('generic_ledger_account_alias_conflict')
            if (row.get('material_release_id')!=material_release_id or row.get('execution_profile')!=execution_profile
                    or account_values!=[expected_account_key]*len(account_values) or not account_values):
                continue
            broker=funding._text(broker_ids[0],'broker_order_id')
            match=re.fullmatch(r'CTP\.([1-9][0-9]*)_([1-9][0-9]*)_([0-9]+)',broker)
            if not match: _fail('generic_ledger_native_order_id_invalid')
            for aliases,value in ((('front_id','FrontID'),match[1]),(('session_id','SessionID'),match[2]),(('order_ref','OrderRef'),match[3])):
                for key in aliases:
                    if key in row and str(row[key])!=value: _fail('generic_ledger_native_identity_conflict')
            identity=row.get('signal_identity')
            if 'signal_identity_json' in row and row['signal_identity_json'] not in (None,''):
                parsed=_json(row['signal_identity_json'])
                if identity is not None and parsed!=identity: _fail('generic_ledger_signal_alias_conflict')
                identity=parsed
            delivery=funding._text(row['intent_id'],'delivery_intent_id')
            original=funding._text(row.get('planned_intent_id') or delivery,'planned_intent_id')
            signal=funding._text(row['signal_order_id'],'signal_order_id')
            keys={'intent_id','signal_order_id','signal_datetime','trading_date'}
            if (type(identity) is not dict or set(identity)!=keys or identity['intent_id']!=original
                    or identity['signal_order_id']!=signal): _fail('generic_ledger_signal_identity_invalid')
            for key in keys: funding._text(identity[key],'signal_'+key)
            funding._day(identity['trading_date'])
            direction=row.get('planned_direction',row.get('direction'));offset=row.get('planned_offset',row.get('offset'))
            if direction not in ('long','short') or offset not in ('open','close'): _fail('generic_ledger_business_enum_invalid')
            binding=dict(account_key=expected_account_key,material_release_id=material_release_id,execution_profile=execution_profile,
                broker_order_id=broker,intent_id=delivery,planned_intent_id=original,signal_order_id=signal,
                signal_identity=copy.deepcopy(identity),vt_symbol=funding._text(row['vt_symbol'],'vt_symbol'),direction=direction,offset=offset)
            caps={}
            for key in ('planned_volume','broker_order_volume','order_request_volume'):
                if key in row and row[key] is not None:
                    value=row[key]
                    if isinstance(value,bool) or not isinstance(value,(int,float,str,Decimal)): _fail('generic_ledger_order_cap_invalid')
                    number=Decimal(str(value))
                    if not number.is_finite() or number<1 or number!=number.to_integral_value(): _fail('generic_ledger_order_cap_invalid')
                    caps[key]=int(number)
            binding.update(caps)
            native_offset=row.get('broker_offset')
            if row.get('native_offset_flag') is not None:
                native_value=_native_offset(row['native_offset_flag'])
                if native_offset is not None and native_offset!=native_value: _fail('generic_ledger_native_offset_conflict')
                native_offset=native_value
            if native_offset is not None:
                if native_offset not in ('open','close','closetoday','closeyesterday') or _business_offset(native_offset)!=offset:
                    _fail('generic_ledger_business_native_offset_conflict')
                binding['broker_offset']=native_offset
            if broker in batch_proofs: binding.update(batch_proofs[broker])
            elif any(key in row for key in ('weekly19_batch_manifest','expected_children','execution_batch_id')) or row.get('api_slot_batch_id'):
                _fail('execution_batch_native_before_insert_missing')
            prior=bindings.setdefault(broker,binding)
            for key,value in binding.items():
                if key in prior and prior[key]!=value: _fail('generic_ledger_order_binding_conflict')
                prior[key]=copy.deepcopy(value)
        return [bindings[key] for key in sorted(bindings)]
    except (ValueError,KeyError,TypeError,InvalidOperation,AttributeError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('generic_ledger_binding_invalid:'+str(exc)) from exc


def _order_intent_binding(native,ledger,context):
    if (_fingerprint(native,'InvestorID')!=context['account_key']
            or _day(native['TradingDay'])!=context['trading_day']):
        _fail('native_order_event_account_or_day_mismatch')
    broker_id=_native_order_id(native)
    matches=[row for row in ledger if isinstance(row,dict) and row.get('broker_order_id')==broker_id]
    if len(matches)!=1: _fail('order_original_intent_mapping_not_unique')
    entry=matches[0]; direction={'0':'long','1':'short'}.get(native['Direction'])
    if direction is None: _fail('native_order_direction_unknown')
    broker_offset=_native_offset(native['CombOffsetFlag']); offset=_business_offset(broker_offset)
    symbol=_symbol(native); volume=_int(native['VolumeTotalOriginal'],1)
    for key,value in (('account_key',context['account_key']),('material_release_id',context['material_release_id']),
        ('execution_profile',context['execution_profile']),('vt_symbol',symbol),('direction',direction),('offset',offset)):
        if entry.get(key)!=value: _fail('order_original_intent_binding_mismatch')
    if 'broker_offset' in entry and entry['broker_offset']!=broker_offset: _fail('ledger_broker_offset_mismatch')
    cap=next((entry[key] for key in ('broker_order_volume','order_request_volume','planned_volume') if key in entry),None)
    if cap is not None and _int(cap,1)!=volume: _fail('order_native_ledger_volume_mismatch')
    identity=entry['signal_identity']; original_id=entry.get('planned_intent_id') or entry['intent_id']
    expected_keys={'intent_id','signal_order_id','signal_datetime','trading_date'}
    if (not isinstance(identity,dict) or set(identity)!=expected_keys
            or identity.get('intent_id')!=original_id or identity.get('signal_order_id')!=entry['signal_order_id']
            or identity.get('trading_date')!=context['trading_day']):
        _fail('order_original_signal_identity_invalid')
    for key in expected_keys: funding._text(identity[key],'signal_'+key)
    return dict(account_key=context['account_key'],material_release_id=context['material_release_id'],
        intent_id=funding._text(original_id,'intent_id'),delivery_intent_id=funding._text(entry['intent_id'],'delivery_intent_id'),signal_order_id=funding._text(entry['signal_order_id'],'signal_order_id'),
        signal_identity=copy.deepcopy(identity),broker_order_id=broker_id,vt_symbol=symbol,direction=direction,
        offset=offset,broker_offset=broker_offset,volume=volume,**_binding_batch_fields(entry,native))


def _order_event(native,ledger,common,*,source_callback,capture_sha256):
    binding=_order_intent_binding(native,ledger,common)
    status=_native_order_status(native); system=str(native.get('OrderSysID','')).strip()
    if status not in ('accepted','rejected') and not system: _fail('native_order_sys_id_missing')
    keys=('account_key','material_release_id','intent_id','signal_order_id','signal_identity','broker_order_id','vt_symbol','direction','offset','broker_offset','volume')
    semantic=dict({key:binding[key] for key in keys},traded=_int(native['VolumeTraded']),status=status)
    digest=funding._hash(semantic)
    return _envelope(dict(common,**semantic,**_binding_batch_fields(binding),schema='weekly19.ctp-order.v1',source_kind='ctp_order_callback',
        source_callback=source_callback,event_id='ctp-order:'+digest,event_semantic_sha256=digest,
        delivery_intent_id=binding['delivery_intent_id'],
        order_sys_id=system,native_offset_flag=native['CombOffsetFlag'],business_offset=binding['offset'],
        raw_native_sha256=funding._hash(native),raw_capture_sha256=capture_sha256,production_qualified=False))


def load_broker_order_updates(summary_path,manifest_path,execution_ledger_rows,**policy):
    """Restore terminal/cumulative order state from onRspQryOrder evidence.

    Apply verified query fills BEFORE these cumulative updates. Event identity is
    based on stable native/business semantics, not collection generation/time.
    """
    try:
        summary,manifest,capture,normalized=_load(summary_path,manifest_path,**policy)
        _public(summary,manifest,capture,normalized)
        _require_verified_execution_bindings(execution_ledger_rows,policy.get('require_production_qualification',True))
        result=[]; seen=set()
        for native,row in zip(capture['raw_queried_orders'],normalized['orders']):
            if row['vt_orderid']!=_native_order_id(native): _fail('query_native_order_identity_mismatch')
            common=_common(capture,capture['queries']['orders'])
            common['capture_kind']='query_recovery'
            event=_order_event(native,execution_ledger_rows,common,source_callback='onRspQryOrder',
                               capture_sha256=manifest['weekly19_capture']['sha256'])
            key=json.loads(event['raw_payload'])['event_id']
            if key not in seen: result.append(event);seen.add(key)
        return result
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_order_evidence_invalid:'+str(exc)) from exc


class NativeBrokerCallbackCollector:
    """Capture actual native dictionaries BEFORE vn.py object normalization.

    Bind this to one warm service/connection lifecycle. It never connects,
    submits, qualifies itself, or treats EVENT_ORDER/TRADE Object rows as CTP.
    Ledger rows are immutable intent bindings, separately pinned by content;
    source authenticity still requires the trusted runner/authority registry.
    """
    def __init__(self,account_envelope,*,connection_generation,service_generation,execution_ledger_rows):
        raw=funding._parse(account_envelope,'weekly19.ctp-account.v1','ctp_account_callback')
        self.account_envelope=copy.deepcopy(account_envelope);self.account=copy.deepcopy(raw)
        self.connection_generation=funding._text(connection_generation,'connection_generation')
        self.service_generation=funding._text(service_generation,'service_generation')
        self.generation_uuid=str(uuid.uuid4());self.events=[];self.sequence=0
        self.known_orders={};self.lock=threading.RLock()
        self.source_hashes={name:_source_digest(name) for name in CAPTURE_SOURCE_FILES}
        self.bind_execution_ledger_rows(execution_ledger_rows)

    def bind_execution_ledger_rows(self,rows):
        if not isinstance(rows,list) or not all(isinstance(row,dict) for row in rows): _fail('native_ledger_rows_invalid')
        funding._canonical(rows)
        with self.lock:
            self.ledger_rows=copy.deepcopy(rows)
            self.ledger_source=copy.deepcopy(rows._source) if isinstance(rows,_VerifiedExecutionBindings) else None
            if self.ledger_source is not None: _require_verified_execution_bindings(rows,True)

    def record(self,method,native,*,connection_generation,observed_at):
        if method not in ('onRtnOrder','onRtnTrade'): _fail('native_callback_method_invalid')
        if type(native) is not dict: _fail('native_ctp_dictionary_required')
        required={'BrokerID','InvestorID','TradingDay','InstrumentID','ExchangeID','Direction','OrderSysID'}
        required|=({'FrontID','SessionID','OrderRef','CombOffsetFlag','VolumeTotalOriginal','VolumeTraded','OrderStatus'}
                   if method=='onRtnOrder' else {'TradeID','TradeDate','TradeTime','OffsetFlag','Volume','Price'})
        if not required.issubset(native): _fail('normalized_object_is_not_native_ctp_callback')
        if connection_generation!=self.connection_generation: _fail('native_callback_connection_revoked')
        observed=funding._time(observed_at)
        with self.lock:
            if self.events and observed<funding._time(self.events[-1]['observed_at']): _fail('native_callback_out_of_order')
            self.sequence+=1
            event=dict(sequence=self.sequence,source_callback=method,native=copy.deepcopy(native),
                native_sha256=funding._hash(native),observed_at=observed.isoformat(),
                connection_generation=self.connection_generation,service_generation=self.service_generation,
                execution_ledger_rows=copy.deepcopy(self.ledger_rows),execution_ledger_rows_sha256=funding._hash(self.ledger_rows),
                execution_ledger_source=copy.deepcopy(self.ledger_source))
            self.events.append(event)
            if method=='onRtnOrder': self.known_orders[_native_order_id(native)]=copy.deepcopy(event)
            return copy.deepcopy(event)

    def export_capture(self,*,now,after_sequence=0):
        _int(after_sequence);now=funding._time(now)
        with self.lock:
            if after_sequence>self.sequence: _fail('native_capture_cursor_future')
            return dict(schema='weekly19.native-broker-capture.v1',capture_kind='native_push',
                account=self.account_envelope,account_key=self.account['account_key'],material_release_id=self.account['material_release_id'],
                execution_profile=self.account['execution_profile'],trading_day=self.account['trading_day'],
                account_query_generation_uuid=self.account['generation_uuid'],generation_uuid=self.generation_uuid,
                connection_generation=self.connection_generation,service_generation=self.service_generation,
                generated_at=now.isoformat(),sequence_after=after_sequence,sequence_end=self.sequence,
                runner_provenance=dict(runner='weekly19_native_callback_collector',source_hashes=self.source_hashes),
                events=copy.deepcopy([row for row in self.events if row['sequence']>after_sequence]),
                known_orders=copy.deepcopy(list(self.known_orders.values())),production_qualified=False)


_NATIVE_BROKER_INSTRUMENT_LOCK=threading.Lock()


@contextmanager
def instrument_native_broker_callbacks(td_api,collector,*,connection_generation,clock,on_recorded=None):
    """Chain actual onRtnOrder/onRtnTrade before their normalized event emission."""
    if not _NATIVE_BROKER_INSTRUMENT_LOCK.acquire(blocking=False): _fail('native_callback_instrumentation_busy')
    owner=type(td_api); originals={}; had={}
    try:
        for name in ('onRtnOrder','onRtnTrade'):
            had[name]=name in owner.__dict__;originals[name]=getattr(owner,name,None)
            def callback(self,data,_name=name):
                if self is td_api:
                    event=collector.record(_name,data,connection_generation=connection_generation(),observed_at=clock())
                    if on_recorded is not None: on_recorded(event)
                original=originals[_name]
                return original(self,data) if original is not None else None
            setattr(owner,name,callback)
        yield collector
    finally:
        for name,original in originals.items():
            if had[name]: setattr(owner,name,original)
            elif name in owner.__dict__: delattr(owner,name)
        _NATIVE_BROKER_INSTRUMENT_LOCK.release()


def persist_native_broker_capture(path,collector,*,now,after_sequence=0,capture_authority_registry=None,capture_authority_capability=None):
    capture=collector.export_capture(now=now,after_sequence=after_sequence)
    payload=funding._canonical(capture)
    _write_private(path,payload)
    reference=dict(path=str(path),sha256=_digest(payload),schema='weekly19.native-broker-capture.v1',production_qualified=False)
    if capture_authority_registry is not None:
        if not all(row.get('execution_ledger_source') for row in capture['events']+capture['known_orders']):
            _fail('production_execution_ledger_source_missing')
        authority=_authority_for(capture_authority_registry,capture,now,capability=capture_authority_capability)
        reference['authority_receipt']=authority._write_receipt(Path(str(path)+'.authority.json'),'native_push',_native_authority_context(capture),reference['sha256'])
    return reference


def _verify_native_sources(capture,trusted):
    sources=capture['runner_provenance']['source_hashes']
    if (not isinstance(trusted,dict) or not set(CAPTURE_SOURCE_FILES).issubset(trusted)
            or not isinstance(sources,dict) or set(sources)!=set(CAPTURE_SOURCE_FILES)):
        _fail('native_capture_source_pins_missing')
    actual={name:_source_digest(name) for name in trusted}
    for name,digest in trusted.items():
        funding._sha(digest)
        if actual[name]!=digest: _fail('native_capture_source_pin_mismatch')
    if any(sources[name]!=actual[name] for name in CAPTURE_SOURCE_FILES): _fail('native_capture_source_pin_mismatch')


def load_native_broker_events(capture_reference,execution_ledger_rows,**policy):
    """Read private native push evidence; always consume fills before orders.

    Native callbacks/ledger content hashes are integrity evidence, not source
    qualification. The default still needs an accepted runner authority receipt.
    """
    try:
        now=funding._time(policy['now'])
        payload=_safe_read(capture_reference['path'],private=True)
        if _digest(payload)!=capture_reference['sha256']: _fail('native_capture_sha256_mismatch')
        capture=_json(payload)
        if (capture.get('schema')!='weekly19.native-broker-capture.v1' or capture.get('capture_kind')!='native_push'
                or capture.get('production_qualified') is not False): _fail('native_capture_schema_invalid')
        for key,expected in (('account_key',policy['expected_account_key']),('material_release_id',policy['material_release_id']),
                            ('execution_profile',policy['execution_profile'])):
            if capture.get(key)!=expected: _fail('native_capture_identity_mismatch')
        _verify_native_sources(capture,policy['trusted_source_hashes'])
        if capture['runner_provenance'].get('runner')!='weekly19_native_callback_collector': _fail('native_runner_invalid')
        funding._text(capture['connection_generation'],'connection_generation');funding._text(capture['service_generation'],'service_generation')
        account=funding._parse(capture['account'],'weekly19.ctp-account.v1','ctp_account_callback')
        if (_fingerprint(account,'AccountID')!=capture['account_key']
                or any(account.get(key)!=capture[key] for key in ('account_key','material_release_id','execution_profile','trading_day'))):
            _fail('native_capture_account_source_mismatch')
        generated=funding._time(capture['generated_at'])
        if not 0<=(now-generated).total_seconds()<=300: _fail('native_capture_stale_or_future')
        common={key:capture[key] for key in ('account_key','material_release_id','execution_profile','trading_day',
            'generation_uuid','connection_generation','service_generation')}
        common.update(capture_kind='native_push',production_qualified=False)
        events=capture['events'];known=capture['known_orders']
        last=_int(capture['sequence_after'])
        for event in events+known:
            if (event['native_sha256']!=funding._hash(event['native'])
                    or event['execution_ledger_rows_sha256']!=funding._hash(event['execution_ledger_rows'])
                    or event['connection_generation']!=capture['connection_generation']
                    or event['service_generation']!=capture['service_generation']
                    or funding._time(event['observed_at'])>generated): _fail('native_callback_record_invalid')
        for event in events:
            if _int(event['sequence'],1)<=last: _fail('native_callback_sequence_invalid')
            last=event['sequence']
            if not 0<=(now-funding._time(event['observed_at'])).total_seconds()<=300: _fail('native_callback_stale_or_future')
        if last!=capture['sequence_end']: _fail('native_capture_sequence_incomplete')
        source_authority=None
        if policy.get('require_production_qualification',True) or policy.get('capture_authority_registry') is not None:
            if policy.get('capture_authority_registry') is None or not capture_reference.get('authority_receipt'):
                _fail('production_capture_qualification_missing:registry_or_native_receipt')
            authority=_authority_for(policy['capture_authority_registry'],capture,now,capability=policy.get('capture_authority_capability'))
            source_authority=authority._verify_receipt(capture_reference['authority_receipt'],'native_push',_native_authority_context(capture),capture_reference['sha256'])
        _require_verified_execution_bindings(execution_ledger_rows,policy.get('require_production_qualification',True))
        if source_authority is not None and not all(row.get('execution_ledger_source') for row in events+known):
            _fail('production_execution_ledger_source_missing')
        orders=[];fills=[];seen_orders=set();seen_trades={}
        native_orders=[row['native'] for row in known if row['source_callback']=='onRtnOrder']
        for event in events:
            native=event['native'];event_common=dict(common,observed_at=event['observed_at'],native_callback_sequence=event['sequence'],
                execution_ledger_rows_sha256=event['execution_ledger_rows_sha256'])
            if event['source_callback']=='onRtnOrder':
                current=_order_intent_binding(native,execution_ledger_rows,event_common)
                captured=_order_intent_binding(native,event['execution_ledger_rows'],event_common)
                if current!=captured: _fail('native_callback_ledger_binding_drift')
                envelope=_order_event(native,execution_ledger_rows,event_common,source_callback='onRtnOrder',capture_sha256=capture_reference['sha256'])
                key=_json(envelope['raw_payload'])['event_id']
                if key not in seen_orders: orders.append(envelope);seen_orders.add(key)
            elif event['source_callback']=='onRtnTrade':
                if (_fingerprint(native,'InvestorID')!=capture['account_key'] or _day(native['TradingDay'])!=capture['trading_day']):
                    _fail('native_trade_account_or_day_mismatch')
                matches=[row for row in native_orders if row['ExchangeID']==native['ExchangeID']
                         and str(row['OrderSysID']).strip()==str(native['OrderSysID']).strip()]
                if len(matches)!=1: _fail('native_push_trade_order_proof_not_unique')
                order=matches[0]
                binding=_order_intent_binding(order,execution_ledger_rows,event_common)
                captured=_order_intent_binding(order,event['execution_ledger_rows'],event_common)
                if binding!=captured: _fail('native_callback_ledger_binding_drift')
                if order['Direction']!=native['Direction'] or order['CombOffsetFlag']!=native['OffsetFlag']:
                    _fail('native_push_trade_order_direction_or_offset_mismatch')
                executed=datetime.strptime(native['TradeDate']+' '+native['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
                if executed>funding._time(event['observed_at']): _fail('native_push_trade_after_callback')
                stable='ctp:'+native['BrokerID']+':'+native['InvestorID']+':'+native['ExchangeID']+':'+native['TradeDate']+':'+native['OrderSysID'].strip()+':'+funding._text(native['TradeID'].strip(),'trade_id')
                trade=dict(event_common,**{key:value for key,value in binding.items() if key!='volume'},schema='weekly19.ctp-trade.v1',
                    source_kind='ctp_trade_callback',source_callback='onRtnTrade',trade_id=stable,volume=_int(native['Volume'],1),
                    business_offset=binding['offset'],native_offset_flag=native['OffsetFlag'],price=_native_decimal(native['Price'],money=False,positive=True),
                    trade_datetime=executed.isoformat(),execution_datetime=executed.isoformat(),
                    raw_native_sha256=funding._hash(native),raw_capture_sha256=capture_reference['sha256'])
                semantic={key:trade[key] for key in ('account_key','material_release_id','intent_id','signal_order_id','signal_identity',
                    'broker_order_id','trade_id','vt_symbol','direction','offset','broker_offset','volume','price','execution_datetime','trading_day')}
                digest=funding._hash(semantic)
                if stable in seen_trades:
                    if seen_trades[stable]!=digest: _fail('native_trade_identity_content_conflict')
                else: fills.append(_envelope(trade));seen_trades[stable]=digest
            else: _fail('native_callback_method_invalid')
        return dict(fills=fills,orders=orders,apply_order=['fills','orders'],production_qualified=False,
            source_qualified=bool(source_authority),capture_authority=source_authority,
            capture_sha256=capture_reference['sha256'],sequence_end=capture['sequence_end'],
            generation_uuid=capture['generation_uuid'],connection_generation=capture['connection_generation'],service_generation=capture['service_generation'])
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('native_broker_evidence_invalid:'+str(exc)) from exc


CAPTURE_AUTHORITY_SOURCE_FILES=(*CAPTURE_SOURCE_FILES,
    'examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py',
    'examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py',
    'examples/portfolio_backtesting/build_qmt_roll_stage179_production_qualification_bundle.py',
    'examples/portfolio_backtesting/qmt_roll_weekly19_warm_evidence.py',
    'examples/portfolio_backtesting/qmt_roll_official_live_release_manifest.py',
    'examples/portfolio_backtesting/run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py',
    'examples/portfolio_backtesting/qmt_roll_official_baseline_identity.py')
_AUTHORITY_KINDS=frozenset({'stage174_query','native_push','warm_epoch_snapshot','transfer_serial_query'})
_AUTHORITY_TOKEN=object()


def _external_private(path):
    path=Path(path)
    if not path.is_absolute() or path.is_relative_to(ROOT): _fail('authority_private_external_path_required')
    return path


def _validate_authority_qualification(reference,identity,expected_account_key):
    path=_external_private(reference['path']);raw=_safe_read(path,private=True)
    if _digest(raw)!=reference['sha256']: _fail('authority_qualification_sha256_mismatch')
    critical=identity['critical_files']
    if not isinstance(critical,list) or not set(CAPTURE_AUTHORITY_SOURCE_FILES).issubset(critical):
        _fail('authority_qualification_source_closure_missing')
    # Check the validator's own pinned bytes BEFORE importing/executing it.
    declared=_json(raw).get('critical_files',[])
    hashes={row.get('path'):row.get('sha256') for row in declared if isinstance(row,dict)}
    for name in CAPTURE_AUTHORITY_SOURCE_FILES:
        if hashes.get(name)!=_source_digest(name): _fail('authority_qualification_source_hash_mismatch')
    try:
        from build_qmt_roll_stage179_release_manifest import load_and_validate_production_qualification_evidence
        payload=load_and_validate_production_qualification_evidence(path,repo_root=ROOT,
            source_commit=identity['source_commit'],execution_profile=identity['execution_profile'],
            official_version=identity['official_version'],capital=150000,capital_label='15w',
            critical_files=critical,manifest_created_at_utc=identity['manifest_created_at_utc'])
    except Exception as exc:
        raise BrokerEvidenceError('authority_real_qualification_rejected:'+type(exc).__name__) from exc
    pointer=payload['formal_ctp_readonly'];relative=Path(pointer['artifact_path'])
    if relative.is_absolute() or '..' in relative.parts: _fail('authority_readonly_artifact_path_invalid')
    readonly_raw=_safe_read(path.parent/relative,private=True)
    if _digest(readonly_raw)!=pointer['artifact_sha256']: _fail('authority_readonly_artifact_hash_mismatch')
    readonly=_json(readonly_raw)
    if (readonly.get('account_fingerprint')!=expected_account_key
            or readonly.get('status')!='qualified' or readonly.get('runtime_profile')!='production-readonly'
            or payload.get('trusted_runner',{}).get('runner_mode')!='trusted_subprocess_v1'
            or any(readonly.get(key)!=1 for key in ('query_bundle_complete','account_query_complete','position_query_complete','order_query_complete','trade_query_complete'))
            or any(type(readonly.get(key)) is not int or readonly[key]!=0 for key in ('send_order_api_called_count','cancel_order_api_called_count','order_api_called_count'))):
        _fail('authority_real_readonly_qualification_invalid')
    return payload


def _production_git(*args):
    result=subprocess.run(['git',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=10)
    if result.returncode: _fail('authority_production_git_failed')
    return result.stdout


def _validate_authority_production(release_reference,activation_reference,identity,material_release_id,qualification):
    """Require final stable production proof, never candidate/material proof."""
    try:
        for reference in (release_reference,activation_reference):
            if not isinstance(reference,dict) or not {'path','sha256'}.issubset(reference):
                _fail('authority_production_manifest_activation_required')
            funding._sha(reference['sha256'])
            if _digest(_safe_read(reference['path']))!=reference['sha256']: _fail('authority_production_artifact_hash_mismatch')
        stable=Path.home()/'Desktop/person/vnpy_production_live'
        if ROOT!=stable.resolve(strict=True): _fail('authority_stable_production_checkout_required')
        head=_production_git('rev-parse','--verify','HEAD^{commit}').decode().strip()
        if not re.fullmatch('[0-9a-f]{40}',head) or head!=identity['source_commit']:
            _fail('authority_final_production_qualification_head_mismatch')
        from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
        from qmt_roll_official_live_release_manifest import load_and_validate_release_manifest
        from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import validate_stage179_activation_receipt
        material=assert_official_checkout_matches_active_material(ROOT)
        if material.material_release_id!=material_release_id or material.strategy_version!=identity['official_version']:
            _fail('authority_active_material_identity_mismatch')
        manifest=load_and_validate_release_manifest(release_reference['path'],repo_root=ROOT,
            expected_official_version=identity['official_version'],expected_capital=150000,expected_capital_label='15w',
            expected_execution_profile=identity['execution_profile'],required_runtime_profile='production-live',current_commit=head)
        if (manifest['source_commit']!=head or manifest.get('strategy_semantics_qualification',{}).get('evidence_id')!=qualification['evidence_sha256']
                or manifest['created_at_utc']!=identity['manifest_created_at_utc']
                or {row['path'] for row in manifest['critical_files']}!=set(identity['critical_files'])):
            _fail('authority_production_qualification_manifest_mismatch')
        for row in manifest['critical_files']:
            relative=Path(row['path'])
            if relative.is_absolute() or '..' in relative.parts: _fail('authority_production_critical_path_invalid')
            if _digest(_production_git('show',head+':'+row['path']))!=row['sha256']:
                _fail('authority_production_head_critical_bytes_mismatch')
        if validate_stage179_activation_receipt(activation_reference['path'],manifest_sha256=manifest['manifest_sha256'],
                official_version=identity['official_version'],capital=150000,capital_label='15w'):
            _fail('authority_production_activation_invalid')
        # Detect replacement while the existing validators were reading files.
        for reference in (release_reference,activation_reference):
            if _digest(_safe_read(reference['path']))!=reference['sha256']: _fail('authority_production_artifact_changed')
        if _production_git('rev-parse','--verify','HEAD^{commit}').decode().strip()!=head: _fail('authority_production_head_changed')
        return dict(production_release_manifest=copy.deepcopy(release_reference),production_activation_receipt=copy.deepcopy(activation_reference),
            qualified_source_commit=identity['source_commit'],production_source_commit=head,
            material_source_commit=material.source_commit,material_manifest_sha256=material.manifest_sha256)
    except Exception as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('authority_production_proof_rejected:'+type(exc).__name__) from exc


def _assert_runner_production_source(capture,authority):
    registry=authority.registry
    if (registry['qualified_source_commit']!=registry['production_source_commit']
            or registry['qualification_identity']['source_commit']!=registry['production_source_commit']
            or capture['runner_provenance']['source_commit']!=registry['production_source_commit']):
        _fail('authority_stage174_source_commit_mismatch')


def create_capture_authority_registry(registry_path,*,qualification_path,qualification_sha256,
        expected_account_key,material_release_id,execution_profile,source_commit,official_version,
        critical_files,manifest_created_at_utc,now,capture_kinds=('stage174_query',),
        production_release_manifest=None,production_activation_receipt=None):
    """Create delegation ONLY after existing full Stage179 qualification passes.

    The active release must pin the returned registry digest. Key/registry live
    outside Git, private 0600 under an existing 0700 parent. HMAC detects edits by
    non-runners; it is NOT adversarial authentication against the same OS owner.
    production_release_manifest and production_activation_receipt are raw-SHA
    pinned real production artifacts; candidate/material qualification is not
    a substitute. Actual stable HEAD must equal production qualified source.
    No CTP connection, qualification run or bank action is initiated here.
    """
    try:
        registry_path=_external_private(registry_path);funding._time(now)
        funding._sha(expected_account_key);funding._sha(qualification_sha256)
        funding._text(material_release_id,'release');funding._text(execution_profile,'profile')
        kinds=sorted(set(capture_kinds))
        if not kinds or not set(kinds).issubset(_AUTHORITY_KINDS): _fail('authority_capture_kinds_invalid')
        identity=dict(source_commit=source_commit,execution_profile=execution_profile,official_version=official_version,
            critical_files=list(critical_files),manifest_created_at_utc=manifest_created_at_utc)
        qualification=dict(path=str(qualification_path),sha256=qualification_sha256)
        payload=_validate_authority_qualification(qualification,identity,expected_account_key)
        production=_validate_authority_production(production_release_manifest,production_activation_receipt,identity,material_release_id,payload)
        key=os.urandom(32);key_path=Path(str(registry_path)+'.key')
        registry=dict(schema='weekly19.capture-authority-registry.v1',authority_kind='stage179_trusted_qualification',
            account_key=expected_account_key,material_release_id=material_release_id,execution_profile=execution_profile,
            qualification=qualification,qualification_identity=identity,qualification_evidence_sha256=payload['evidence_sha256'],
            production_evidence=production,qualified_source_commit=production['qualified_source_commit'],
            production_source_commit=production['production_source_commit'],material_source_commit=production['material_source_commit'],
            authority_sources={name:_source_digest(name) for name in CAPTURE_AUTHORITY_SOURCE_FILES},
            allowed_capture_kinds=kinds,key_artifact=dict(path=str(key_path),sha256=_digest(key)),
            created_at=funding._time(now).isoformat())
        _write_private(key_path,key)
        raw=funding._canonical(registry);_write_private(registry_path,raw)
        return dict(path=str(registry_path),sha256=_digest(raw),schema=registry['schema'])
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('authority_registry_create_rejected:'+type(exc).__name__) from exc


class CaptureAuthority:
    def __init__(self,token,reference,registry,key):
        if token is not _AUTHORITY_TOKEN: _fail('authority_loader_required')
        self.reference=copy.deepcopy(reference);self.registry=copy.deepcopy(registry);self._key=key

    def _write_receipt(self,path,kind,context,raw_sha256):
        if kind not in self.registry['allowed_capture_kinds']: _fail('authority_capture_kind_not_qualified')
        body=dict(schema='weekly19.capture-authority-receipt.v1',capture_kind=kind,
            registry_sha256=self.reference['sha256'],raw_capture_sha256=funding._sha(raw_sha256),
            account_key=self.registry['account_key'],material_release_id=self.registry['material_release_id'],
            execution_profile=self.registry['execution_profile'],nonce=os.urandom(16).hex(),context=copy.deepcopy(context))
        receipt=dict(body,hmac_sha256=hmac.new(self._key,funding._canonical(body),hashlib.sha256).hexdigest())
        raw=funding._canonical(receipt);_write_private(path,raw)
        return dict(path=str(path),sha256=_digest(raw),registry_sha256=self.reference['sha256'])

    def _verify_receipt(self,reference,kind,context,raw_sha256):
        if kind not in self.registry['allowed_capture_kinds']: _fail('authority_capture_kind_not_qualified')
        raw=_safe_read(reference['path'],private=True)
        if _digest(raw)!=reference['sha256']: _fail('authority_receipt_sha256_mismatch')
        receipt=_json(raw)
        expected=dict(schema='weekly19.capture-authority-receipt.v1',capture_kind=kind,registry_sha256=self.reference['sha256'],
            raw_capture_sha256=raw_sha256,account_key=self.registry['account_key'],material_release_id=self.registry['material_release_id'],
            execution_profile=self.registry['execution_profile'],context=context)
        _verify_capture_receipt_mac(receipt,self._key,expected)
        return dict(registry_sha256=self.reference['sha256'],receipt_sha256=reference['sha256'],capture_kind=kind,
                    source_qualified=True,production_qualified=False)


def _verify_capture_receipt_mac(receipt,key,expected):
    body={name:value for name,value in receipt.items() if name!='hmac_sha256'}
    actual=hmac.new(key,funding._canonical(body),hashlib.sha256).hexdigest()
    if (not isinstance(receipt.get('hmac_sha256'),str) or not hmac.compare_digest(actual,receipt['hmac_sha256'])
            or not re.fullmatch('[0-9a-f]{32}',body.get('nonce',''))
            or any(body.get(name)!=value for name,value in expected.items())):
        _fail('capture_authority_receipt_mac_or_context_invalid')


def load_capture_authority_registry(reference,*,expected_account_key,material_release_id,execution_profile,
                                     trusted_source_hashes,now):
    """Load pinned private artifacts and FULL qualification; never a user flag."""
    try:
        funding._time(now);funding._sha(reference['sha256'])
        path=_external_private(reference['path']);raw=_safe_read(path,private=True)
        if _digest(raw)!=reference['sha256']: _fail('authority_registry_sha256_mismatch')
        registry=_json(raw)
        if registry.get('schema')!='weekly19.capture-authority-registry.v1' or registry.get('authority_kind')!='stage179_trusted_qualification':
            _fail('authority_registry_not_real_qualification')
        if any(registry.get(key)!=value for key,value in (('account_key',expected_account_key),
                ('material_release_id',material_release_id),('execution_profile',execution_profile))):
            _fail('authority_registry_identity_mismatch')
        sources=registry['authority_sources']
        if set(sources)!=set(CAPTURE_AUTHORITY_SOURCE_FILES): _fail('authority_source_closure_invalid')
        for name,digest in sources.items():
            if funding._sha(digest)!=_source_digest(name): _fail('authority_source_hash_mismatch')
        _verify_native_sources(dict(runner_provenance=dict(source_hashes={name:sources[name] for name in CAPTURE_SOURCE_FILES})),trusted_source_hashes)
        identity=registry['qualification_identity']
        if identity['execution_profile']!=execution_profile: _fail('authority_qualification_profile_mismatch')
        payload=_validate_authority_qualification(registry['qualification'],identity,expected_account_key)
        if payload['evidence_sha256']!=registry['qualification_evidence_sha256']: _fail('authority_qualification_digest_mismatch')
        production=registry['production_evidence']
        checked=_validate_authority_production(production['production_release_manifest'],production['production_activation_receipt'],identity,material_release_id,payload)
        if checked!=production or any(registry.get(key)!=checked[key] for key in ('qualified_source_commit','production_source_commit','material_source_commit')):
            _fail('authority_production_identity_drift')
        if not registry['allowed_capture_kinds'] or not set(registry['allowed_capture_kinds']).issubset(_AUTHORITY_KINDS):
            _fail('authority_capture_kinds_invalid')
        key=_safe_read(_external_private(registry['key_artifact']['path']),private=True)
        if len(key)!=32 or _digest(key)!=registry['key_artifact']['sha256']: _fail('authority_private_key_invalid')
        return CaptureAuthority(_AUTHORITY_TOKEN,reference,registry,key)
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('authority_registry_load_rejected:'+type(exc).__name__) from exc


def _authority_for(reference,context,now,capability=None):
    if reference is None: _fail('production_capture_qualification_missing:authority_registry')
    if capability is not None:
        if not isinstance(capability,CaptureAuthority): _fail('capture_authority_capability_invalid')
        if capability.reference!=reference: _fail('capture_authority_capability_registry_mismatch')
        if any(capability.registry.get(key)!=context[key] for key in ('account_key','material_release_id','execution_profile')):
            _fail('capture_authority_capability_identity_mismatch')
        # Reuse only a previously qualified process-local capability. Keep the
        # live private registry and every actual source pin current; no JSON
        # boolean, reconstructed object, or cached stat can grant this path.
        registry_raw=_safe_read(reference['path'],private=True)
        if _digest(registry_raw)!=reference['sha256']:
            _fail('capture_authority_capability_registry_drift')
        if _json(registry_raw)!=capability.registry:
            _fail('capture_authority_capability_registry_body_changed')
        key_artifact=capability.registry.get('key_artifact',{})
        actual_key=_safe_read(_external_private(key_artifact['path']),private=True)
        if (_digest(actual_key)!=key_artifact['sha256']or capability._key!=actual_key):
            _fail('capture_authority_capability_key_drift')
        sources=capability.registry.get('authority_sources',{})
        if set(sources)!=set(CAPTURE_AUTHORITY_SOURCE_FILES): _fail('capture_authority_capability_source_closure_invalid')
        if any(value!=_source_digest(name) for name,value in sources.items()): _fail('capture_authority_source_drift')
        return capability
    return load_capture_authority_registry(reference,expected_account_key=context['account_key'],
        material_release_id=context['material_release_id'],execution_profile=context['execution_profile'],
        trusted_source_hashes={name:_source_digest(name) for name in CAPTURE_SOURCE_FILES},now=now)


def _query_authority_context(capture):
    return {key:capture[key] for key in ('generation_uuid','connection_generation','generated_at','broker_trading_day','queries','order_api_counters')}|dict(
        invocation_id=capture['runner_provenance']['invocation_id'],source_commit=capture['runner_provenance']['source_commit'],
        source_hashes=capture['runner_provenance']['source_hashes'])


def _native_authority_context(capture):
    return {key:capture[key] for key in ('generation_uuid','connection_generation','service_generation','generated_at','sequence_after','sequence_end')}|dict(
        events_sha256=funding._hash(capture['events']),known_orders_sha256=funding._hash(capture['known_orders']))


def _bank_authority_context(raw):
    return {key:raw[key] for key in ('generation_uuid','connection_generation','observed_at','query_reqid','query_return_code','request_sent_at')}|dict(
        callbacks_sha256=funding._hash(raw['callbacks']),rows_sha256=funding._hash(raw['rows']))


class TransferSerialCollector:
    """Read-only native query adapter; it never connects or transfers funds.

    The owning trusted runner must install its onRspQryTransferSerial callback
    under the SAME Stage174 firewall and forward native data to on_callback with
    the current lifecycle generation. No last flag implies final daily closure.
    Exported data remains unqualified, even after all callbacks arrived.
    """
    def __init__(self, account_envelope, *, connection_generation):
        raw=funding._parse(account_envelope,'weekly19.ctp-account.v1','ctp_account_callback')
        self.account=copy.deepcopy(raw)
        self.connection_generation=funding._text(connection_generation,'connection_generation')
        self.request_id=None; self.request_sent_at=None; self.return_code=None
        self.callbacks=[]; self.rows=[]; self.invalid=False
        self.lock=threading.RLock()

    def begin(self,td_api,*,query_reqid,now,current_connection_generation):
        """Only reqQryTransferSerial is invoked; no bank-transfer method exists."""
        with self.lock:
            if self.request_id is not None: _fail('transfer_query_already_started')
            if current_connection_generation!=self.connection_generation: _fail('transfer_connection_mismatch')
            self.request_id=_int(query_reqid,1); self.request_sent_at=funding._time(now).isoformat()
            request=dict(BrokerID=self.account['BrokerID'],AccountID=self.account['AccountID'],BankID='',CurrencyID='CNY')
            self.return_code=int(td_api.reqQryTransferSerial(request,self.request_id))
            if self.return_code!=0: self.invalid=True
            return self.return_code

    def on_callback(self,data,error,reqid,last,*,connection_generation,observed_at):
        with self.lock:
            if self.request_id is None: _fail('transfer_query_not_started')
            matched=(type(reqid) is int and reqid==self.request_id and connection_generation==self.connection_generation)
            if not matched:
                # A callback in a revoked generation invalidates this capture;
                # a different reqid in the same generation is unrelated.
                if connection_generation!=self.connection_generation: self.invalid=True
                return
            if self.callbacks and self.callbacks[-1]['last']: self.invalid=True
            err=error.get('ErrorID') if isinstance(error,dict) else None
            if type(err) is not int or err!=0: self.invalid=True
            when=funding._time(observed_at)
            if when<funding._time(self.request_sent_at): self.invalid=True
            self.callbacks.append(dict(reqid=reqid,connection_generation=connection_generation,
                received_at=when.isoformat(),last=last is True,error_id=err,has_data=bool(data)))
            if data:
                if not isinstance(data,dict): self.invalid=True
                else: self.rows.append(copy.deepcopy(data))

    def export_capture(self,*,now):
        with self.lock:
            now=funding._time(now)
            if (self.invalid or self.return_code!=0 or not self.callbacks
                    or self.callbacks[-1]['last'] is not True
                    or not 0<=(now-funding._time(self.request_sent_at)).total_seconds()<=300
                    or any(not 0<=(now-funding._time(row['received_at'])).total_seconds()<=300 for row in self.callbacks)):
                _fail('transfer_query_incomplete_or_invalid')
            return _envelope(dict(schema='weekly19.ctp-transfer-serial-query.v1',source_kind='ctp_transfer_serial_query',
                account_key=self.account['account_key'],material_release_id=self.account['material_release_id'],
                execution_profile=self.account.get('execution_profile'),generation_uuid=self.account['generation_uuid'],
                connection_generation=self.connection_generation,trading_day=self.account['trading_day'],
                observed_at=now.isoformat(),query_reqid=self.request_id,query_complete=True,
                query_return_code=self.return_code,query_error_rows=0,request_sent_at=self.request_sent_at,
                account_source_sha256=_digest(funding._canonical(self.account)),callbacks=copy.deepcopy(self.callbacks),
                rows=copy.deepcopy(self.rows),production_qualified=False))



_TRANSFER_INSTRUMENT_LOCK = threading.Lock()


@contextmanager
def instrument_transfer_serial_callback(td_api,collector,*,connection_generation,clock):
    """Temporarily capture one native instance's transfer-query responses.

    The caller owns the already-connected generation and Stage174 mutation
    firewall. This helper installs no bank/order method and makes no connection.
    A nonblocking process lock forbids concurrent class monkeypatches.
    """
    if not _TRANSFER_INSTRUMENT_LOCK.acquire(blocking=False):
        _fail('transfer_callback_instrumentation_busy')
    owner=type(td_api); method='onRspQryTransferSerial'
    had=method in owner.__dict__; original=getattr(owner,method,None)
    def callback(self,data,error,reqid,last):
        if self is td_api:
            return collector.on_callback(data,error,reqid,last,
                connection_generation=connection_generation(),observed_at=clock())
        if original is not None:
            return original(self,data,error,reqid,last)
        return None
    try:
        setattr(owner,method,callback)
        yield collector
    finally:
        if had: setattr(owner,method,original)
        elif method in owner.__dict__: delattr(owner,method)
        _TRANSFER_INSTRUMENT_LOCK.release()


def persist_transfer_serial_capture(path,collector,*,now,capture_authority_registry=None,capture_authority_capability=None):
    """Keep full bank serial bytes private; publication remains unqualified."""
    envelope=collector.export_capture(now=now)
    payload=funding._canonical(envelope)
    _write_private(path,payload)
    reference=dict(path=str(path),sha256=_digest(payload),raw_sha256=envelope['raw_sha256'],production_qualified=False)
    if capture_authority_registry is not None:
        raw=_json(envelope['raw_payload']);authority=_authority_for(capture_authority_registry,raw,now,capability=capture_authority_capability)
        reference['authority_receipt']=authority._write_receipt(Path(str(path)+'.authority.json'),'transfer_serial_query',_bank_authority_context(raw),envelope['raw_sha256'])
    return reference

def load_bank_cashflow_receipt(raw_source,*,state=None,request_id=None,bank_serial=None,now=None,
                               require_production_qualification=True,capture_authority_registry=None,capture_authority_receipt=None,capture_authority_capability=None):
    """Conditionally parse native TransferSerial rows, still NOT source-qualified.

    CTP6.7.2.1 valid flag=1; bank->futures codes=102001 or 202001. Repealed,
    failed, withdrawal, fee-bearing, duplicate or unmatched serials are rejected.
    Caller selects an actual BankSerial; quantity always comes from TradeAmount.
    The real provider/runner qualification remains a separate missing gate.
    """
    if state is None or request_id is None or bank_serial is None or now is None:
        _fail('accepted_cashflow_source_missing:qualified_transfer_serial_capture')
    try:
        funding.validate_state(state); now=funding._time(now)
        raw=funding._parse(raw_source,'weekly19.ctp-transfer-serial-query.v1','ctp_transfer_serial_query')
        funding._binding(raw,state)
        if (raw.get('production_qualified') is not False or raw.get('query_complete') is not True
                or type(raw.get('query_return_code')) is not int or raw['query_return_code']!=0
                or type(raw.get('query_error_rows')) is not int or raw['query_error_rows']!=0):
            _fail('transfer_capture_query_invalid')
        _int(raw['query_reqid'],1); funding._text(raw['connection_generation'],'connection_generation')
        if not 0<=(now-funding._time(raw['observed_at'])).total_seconds()<=300:
            _fail('transfer_capture_stale_or_future')
        sent=funding._time(raw['request_sent_at'])
        if not 0<=(now-sent).total_seconds()<=300: _fail('transfer_query_stale_or_future')
        callbacks=raw['callbacks']
        if not callbacks or sum(row.get('last') is True for row in callbacks)!=1 or callbacks[-1]['last'] is not True:
            _fail('transfer_last_callback_missing')
        for callback in callbacks:
            if (callback.get('reqid')!=raw['query_reqid'] or callback.get('connection_generation')!=raw['connection_generation']
                    or type(callback.get('error_id')) is not int or callback['error_id']!=0
                    or not sent<=funding._time(callback['received_at'])<=funding._time(raw['observed_at'])<=now
                    or not 0<=(now-funding._time(callback['received_at'])).total_seconds()<=300):
                _fail('transfer_callback_invalid')
        if sum(row['has_data'] is True for row in callbacks)!=len(raw['rows']): _fail('transfer_row_count_mismatch')
        matches=[(index,row) for index,row in enumerate(raw['rows']) if row.get('BankSerial')==bank_serial]
        if len(matches)!=1: _fail('transfer_bank_serial_not_unique')
        index,row=matches[0]
        data_callbacks=[callback for callback in callbacks if callback['has_data'] is True]
        if (_fingerprint(row,'AccountID')!=state['account_key'] or row.get('CurrencyID')!='CNY'
                or type(row.get('ErrorID')) is not int or row['ErrorID']!=0
                or row.get('AvailabilityFlag')!='1' or row.get('TradeCode') not in ('102001','202001')
                or _native_decimal(row['CustFee'])!='0.00' or _native_decimal(row['BrokerFee'])!='0.00'):
            _fail('transfer_not_completed_fee_free_deposit')
        if _day(row['TradingDay'])!=raw['trading_day']: _fail('transfer_trading_day_mismatch')
        amount=_native_decimal(row['TradeAmount'],positive=True)
        occurred=datetime.strptime(row['TradeDate']+' '+row['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
        request=state['requests'][request_id]
        if not funding._time(request['created_at'])<=occurred<=funding._time(data_callbacks[index]['received_at']):
            _fail('transfer_request_or_native_callback_time_mismatch')
        serial_id='ctp-transfer:'+_digest(funding._canonical([row['BrokerID'],row['AccountID'],row['TradingDay'],
            _int(row['PlateSerial'],1),funding._text(row['BankID'],'bank_id'),bank_serial,_int(row['FutureSerial'],1)]))
        source_authority=None
        if require_production_qualification or capture_authority_registry is not None:
            if capture_authority_registry is None or capture_authority_receipt is None:
                _fail('accepted_cashflow_source_missing:qualified_transfer_serial_runner')
            authority=_authority_for(capture_authority_registry,raw,now,capability=capture_authority_capability)
            source_authority=authority._verify_receipt(capture_authority_receipt,'transfer_serial_query',_bank_authority_context(raw),raw_source['raw_sha256'])
        return _envelope(dict(schema='weekly19.bank-cashflow.v1',source_kind='broker_cashflow_receipt',
            source_callback='onRspQryTransferSerial',account_key=state['account_key'],material_release_id=state['material_release_id'],
            request_id=request_id,trading_day=raw['trading_day'],occurred_at=occurred.isoformat(),receipt_id=serial_id,
            Amount=amount,Direction='deposit',Status='completed',production_qualified=False,source_qualified=bool(source_authority),capture_authority=source_authority,
            raw_transfer_query_sha256=raw_source['raw_sha256']))
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('transfer_evidence_invalid:'+str(exc)) from exc


def load_cashflow_day_close(raw_source,**_policy):
    """Reserved boundary for a real final cashflow/settlement statement parser.

    Required evidence: immutable full statement bytes and vendor/schema version,
    authenticated account and covered TradingDay, FINAL Deposit/Withdraw (all
    banks/reversals/fees), statement finality semantics, cutoff/next TradingDay,
    and matching closing account callback/source hash. A query-last flag, an
    arbitrary cashflows_complete field or a wall-clock time cannot supply this.
    No broker statement sample/parser has yet been accepted for this release.
    """
    _fail('accepted_cashflow_source_missing:missing_statement:final_cashflow_statement_parser')
