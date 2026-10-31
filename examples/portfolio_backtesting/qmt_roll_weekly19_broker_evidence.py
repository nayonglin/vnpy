"""Stage174 raw-callback capture/translation for the weekly19 candidate.

No network/CTP/SMTP imports or connection APIs exist here. Stage174's explicit
read-only runner may call publish_stage174_capture AFTER native callbacks are
frozen behind its mutation firewall. The provider independently re-reads the
manifest, raw artifact, callback/query metadata, normalized CSV hashes, source
hashes and account/release/profile binding.

Integrity is not authenticity: these APIs always return production_qualified=False.
Production mode is the default and remains blocked until a separately accepted
capture/qualification authority is implemented. Offline fixtures never qualify a
runner, bank receipt, final cashflow statement or live trading account.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import copy
import threading
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import uuid

import qmt_roll_weekly19_funding as funding
from qmt_roll_official_live_broker_account_snapshot import _context
from qmt_roll_official_live_late_retry_fill import validate_readonly_query_bundle

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SOURCE_FILES = (
    'examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py',
    'examples/portfolio_backtesting/qmt_roll_weekly19_broker_evidence.py',
    'examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py',
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


def _safe_read(path, *, private=False):
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


def publish_stage174_capture(summary, rows, *, material_release_id, execution_profile,
                             private_capture_dir, invocation_id):
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
            source_hashes={name:_digest(_safe_read(ROOT/name)) for name in CAPTURE_SOURCE_FILES}),
        order_api_counters={name:summary.get(name) for name in COUNTERS},
        order_api_evidence_window=summary.get('order_api_evidence_window'),
        callbacks={name:rows.get(CALLBACK_NAMES[name],[]) for name in KINDS},
        **{RAW_NAMES[name]:rows.get(RAW_NAMES[name],[]) for name in KINDS})
    payload=funding._canonical(capture)
    path=Path(private_capture_dir)/('weekly19-raw-'+bundle['generation_uuid']+'-'+uuid.uuid4().hex+'.json')
    _write_private(path,payload)
    return dict(path=str(path),sha256=_digest(payload),schema=capture['schema'],
                production_qualified=False,generation_uuid=bundle['generation_uuid'])


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
          now,trusted_source_hashes,require_production_qualification=True):
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
    for name in CAPTURE_SOURCE_FILES:
        actual=_digest(_safe_read(ROOT/name))
        if (not isinstance(trusted_source_hashes,dict) or trusted_source_hashes.get(name)!=actual
                or runner.get('source_hashes',{}).get(name)!=actual):
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
    if require_production_qualification:
        _fail('production_capture_qualification_missing')
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
        offset={'0':'open','1':'close','3':'closetoday','4':'closeyesterday'}.get(row['CombOffsetFlag'])
        status={'0':'all_traded','1':'part_traded','2':'cancelled','3':'not_traded','4':'cancelled','5':'cancelled','a':'submitting'}.get(row['OrderStatus'])
        if not direction or not offset or not status: _fail('native_order_enum_invalid')
        volume=_int(row['VolumeTotalOriginal'],1); traded=_int(row['VolumeTraded'])
        if traded>volume: _fail('native_order_traded_exceeds_volume')
        order_id='CTP.'+str(_int(row['FrontID'],1))+'_'+str(_int(row['SessionID'],1))+'_'+funding._text(row['OrderRef'],'orderref')
        order_rows.append(dict(broker_order_id=order_id,vt_symbol=_symbol(row),direction=direction,offset=offset,
                               volume=volume,traded=traded,status=status))
    return dict(account=_envelope(account_raw),
        positions=_envelope(dict(_common(capture,capture['queries']['positions']),schema='weekly19.ctp-positions.v1',source_kind='ctp_position_query',positions=position_rows)),
        orders=_envelope(dict(_common(capture,capture['queries']['orders']),schema='weekly19.ctp-orders.v1',source_kind='ctp_order_query',orders=order_rows)),
        production_qualified=False,provenance=dict(raw_capture=manifest['weekly19_capture'],
            generation_uuid=capture['generation_uuid'],source_hashes=capture['runner_provenance']['source_hashes'],
            qualification_status='not_qualified_no_accepted_capture_authority'))


def load_broker_snapshot(summary_path,manifest_path,**policy):
    """Load/translate only a complete same-generation capture, default fail-closed."""
    try:
        return _public(*_load(summary_path,manifest_path,**policy))
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,csv.Error) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_evidence_invalid:'+str(exc)) from exc


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
    """
    try:
        summary,manifest,capture,normalized=_load(summary_path,manifest_path,**policy)
        _public(summary,manifest,capture,normalized)
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
            if len(native_ids)!=1 or row['vt_orderid'] not in native_ids:
                _fail('native_trade_order_mapping_mismatch')
            matches=[entry for entry in execution_ledger_rows if entry.get('broker_order_id')==row['vt_orderid']]
            if len(matches)!=1: _fail('trade_original_intent_mapping_not_unique')
            entry=matches[0]
            symbol=_symbol(native); direction={'0':'long','1':'short'}.get(native['Direction'])
            offset={'0':'open','1':'close','3':'closetoday','4':'closeyesterday'}.get(native['OffsetFlag'])
            for key,value in (('account_key',capture['account_key']),('material_release_id',capture['material_release_id']),
                    ('execution_profile',capture['execution_profile']),('vt_symbol',symbol),('direction',direction),('offset',offset)):
                if entry.get(key)!=value: _fail('trade_original_intent_binding_mismatch')
            intent=funding._text(entry['intent_id'],'intent_id'); signal=funding._text(entry['signal_order_id'],'signal_order_id')
            if entry['signal_identity'].get('intent_id')!=intent or entry['signal_identity'].get('signal_order_id')!=signal:
                _fail('trade_signal_identity_mismatch')
            executed=datetime.strptime(native['TradeDate']+' '+native['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
            if executed>funding._time(policy['now']): _fail('native_trade_future')
            fills.append(_envelope(dict(_common(capture,capture['queries']['trades']),schema='weekly19.ctp-trade.v1',
                source_kind='ctp_trade_callback',source_callback='onRspQryTrade',intent_id=intent,signal_order_id=signal,
                signal_identity=entry['signal_identity'],broker_order_id=row['vt_orderid'],trade_id=stable,vt_symbol=symbol,
                direction=direction,offset=offset,volume=_int(native['Volume'],1),price=_native_decimal(native['Price'],money=False,positive=True),
                trade_datetime=executed.isoformat(),execution_datetime=executed.isoformat(),
                raw_capture_sha256=manifest['weekly19_capture']['sha256'])))
        return fills
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,BrokerEvidenceError): raise
        raise BrokerEvidenceError('broker_fill_evidence_invalid:'+str(exc)) from exc


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


def persist_transfer_serial_capture(path,collector,*,now):
    """Keep full bank serial bytes private; publication remains unqualified."""
    envelope=collector.export_capture(now=now)
    payload=funding._canonical(envelope)
    _write_private(path,payload)
    return dict(path=str(path),sha256=_digest(payload),raw_sha256=envelope['raw_sha256'],production_qualified=False)

def load_bank_cashflow_receipt(raw_source,*,state=None,request_id=None,bank_serial=None,now=None,
                               require_production_qualification=True):
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
        callbacks=raw['callbacks']
        if not callbacks or sum(row.get('last') is True for row in callbacks)!=1 or callbacks[-1]['last'] is not True:
            _fail('transfer_last_callback_missing')
        for callback in callbacks:
            if (callback.get('reqid')!=raw['query_reqid'] or callback.get('connection_generation')!=raw['connection_generation']
                    or type(callback.get('error_id')) is not int or callback['error_id']!=0
                    or not funding._time(raw['request_sent_at'])<=funding._time(callback['received_at'])<=now):
                _fail('transfer_callback_invalid')
        if sum(row['has_data'] is True for row in callbacks)!=len(raw['rows']): _fail('transfer_row_count_mismatch')
        matches=[row for row in raw['rows'] if row.get('BankSerial')==bank_serial]
        if len(matches)!=1: _fail('transfer_bank_serial_not_unique')
        row=matches[0]
        if (_fingerprint(row,'AccountID')!=state['account_key'] or row.get('CurrencyID')!='CNY'
                or type(row.get('ErrorID')) is not int or row['ErrorID']!=0
                or row.get('AvailabilityFlag')!='1' or row.get('TradeCode') not in ('102001','202001')
                or _native_decimal(row['CustFee'])!='0.00' or _native_decimal(row['BrokerFee'])!='0.00'):
            _fail('transfer_not_completed_fee_free_deposit')
        if _day(row['TradingDay'])!=raw['trading_day']: _fail('transfer_trading_day_mismatch')
        amount=_native_decimal(row['TradeAmount'],positive=True)
        occurred=datetime.strptime(row['TradeDate']+' '+row['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
        request=state['requests'][request_id]
        if not funding._time(request['created_at'])<=occurred<=now: _fail('transfer_request_time_mismatch')
        serial_id='ctp-transfer:'+_digest(funding._canonical([row['BrokerID'],row['AccountID'],row['TradingDay'],
            _int(row['PlateSerial'],1),funding._text(row['BankID'],'bank_id'),bank_serial,_int(row['FutureSerial'],1)]))
        if require_production_qualification:
            _fail('accepted_cashflow_source_missing:qualified_transfer_serial_runner')
        return _envelope(dict(schema='weekly19.bank-cashflow.v1',source_kind='broker_cashflow_receipt',
            source_callback='onRspQryTransferSerial',account_key=state['account_key'],material_release_id=state['material_release_id'],
            request_id=request_id,trading_day=raw['trading_day'],occurred_at=occurred.isoformat(),receipt_id=serial_id,
            Amount=amount,Direction='deposit',Status='completed',production_qualified=False,
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
    _fail('accepted_cashflow_source_missing:final_cashflow_statement_parser')
