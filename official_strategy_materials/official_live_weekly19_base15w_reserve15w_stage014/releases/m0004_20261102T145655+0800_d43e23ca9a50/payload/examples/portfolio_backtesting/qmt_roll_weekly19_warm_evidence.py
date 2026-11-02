"""Pure same-connection CTP epoch reader. Never calls a query or connects.

The 931 runner freezes exact onRsp* data BEFORE normalization/pending cleanup.
This module reads those receipts, not vn.py Object rows or a different Stage174
connection. A warm service may have real order API calls: only each query's
return/last/error/generation is relevant here. Source authority and strategy
production qualification remain separate.
"""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import qmt_roll_weekly19_broker_evidence as provider
import qmt_roll_weekly19_funding as funding

WARM_SOURCE='examples/portfolio_backtesting/qmt_roll_weekly19_warm_evidence.py'
KINDS=('account','positions','orders','trades')
EPOCH_KEYS=dict(account='_final_account_funds_epoch',positions='_position_query_epoch',orders='_order_query_epoch',trades='_trade_query_epoch')
CALLBACK_NAMES=dict(account='onRspQryTradingAccount',positions='onRspQryInvestorPosition',orders='onRspQryOrder',trades='onRspQryTrade')


class WarmEvidenceError(provider.BrokerEvidenceError):
    pass


def _fail(reason): raise WarmEvidenceError(reason)


def _integer(value,minimum=0):
    if type(value) is not int or value<minimum: _fail('warm_native_integer_invalid')
    return value


def _sources(trusted):
    required=(*provider.CAPTURE_SOURCE_FILES,WARM_SOURCE)
    if not isinstance(trusted,dict) or not set(required).issubset(trusted): _fail('warm_source_pin_missing')
    for name,digest in trusted.items():
        if funding._sha(digest)!=provider._source_digest(name): _fail('warm_source_pin_mismatch')


def _freeze(transport,policy):
    now=funding._time(policy['now']);_sources(policy['trusted_source_hashes'])
    rows=transport['rows'];original=rows.get('_weekly19_native_receipts')
    if not isinstance(original,dict) or set(original)!=set(KINDS): _fail('frozen_native_receipt_missing')
    before=funding._hash(original);receipts=copy.deepcopy(original)
    identity=copy.deepcopy(rows['_weekly19_capture_identity'])
    if before!=funding._hash(original): _fail('warm_native_receipt_changed_during_copy')
    for key,expected in (('account_key',policy['expected_account_key']),('material_release_id',policy['material_release_id']),
        ('execution_profile',policy['execution_profile']),('connection_generation',transport['connection_generation']),
        ('service_generation',transport['service_generation'])):
        if identity.get(key)!=expected: _fail('warm_transport_identity_mismatch')
        funding._text(expected,'warm_'+key)
    raw_rows={};queries={};reqids=set()
    for kind in KINDS:
        receipt=receipts[kind]
        if receipt.get('schema')!='weekly19.warm-native-query-epoch.v1' or receipt.get('kind')!=kind:
            _fail('warm_epoch_schema_invalid')
        if any(receipt.get(key)!=identity[key] for key in ('account_key','material_release_id','execution_profile','connection_generation','service_generation')): _fail('warm_epoch_identity_mismatch')
        reqid=_integer(receipt['query_reqid'],1)
        if reqid in reqids: _fail('warm_query_reqid_not_unique')
        reqids.add(reqid)
        ret=receipt.get('request_return_code',receipt.get('request_ret'))
        if (type(ret) is not int or ret!=0 or ('request_ret' in receipt and receipt['request_ret']!=ret)
                or receipt.get('last_seen') is not True or type(receipt.get('error_rows')) is not int
                or receipt['error_rows']!=0 or receipt.get('late_callback_blockers',[])!=[]):
            _fail('warm_query_return_last_error_or_late_invalid')
        sent=funding._time(receipt['request_sent_at']);done=funding._time(receipt['completed_at'])
        if not sent<=done<=now or not 0<=(now-sent).total_seconds()<=300: _fail('warm_query_stale_future_or_timeline_invalid')
        callbacks=receipt['native_callbacks']
        if (not isinstance(callbacks,list) or not callbacks or callbacks[-1].get('last') is not True
                or sum(row.get('last') is True for row in callbacks)!=1): _fail('warm_native_last_callback_missing')
        native=[];previous=sent
        for callback in callbacks:
            if (type(callback.get('reqid')) is not int or callback['reqid']!=reqid or type(callback.get('last')) is not bool
                    or callback.get('connection_generation')!=identity['connection_generation']):
                _fail('warm_native_callback_reqid_or_generation_invalid')
            observed=funding._time(callback['received_at']);error=callback['error'];data=callback['data']
            if not previous<=observed<=done or not 0<=(now-observed).total_seconds()<=300:
                _fail('warm_native_callback_stale_future_or_out_of_order')
            previous=observed
            if type(error) is not dict or (error and 'ErrorID' not in error): _fail('warm_native_error_info_invalid')
            error_id=error.get('ErrorID',0)
            if type(error_id) is not int or error_id!=0: _fail('warm_native_callback_error')
            if type(data) is not dict: _fail('warm_native_ctp_dictionary_required')
            if data: native.append(copy.deepcopy(data))
        epoch=rows.get(EPOCH_KEYS[kind])
        if epoch is not None:
            if (not isinstance(epoch,dict) or epoch.get('complete_reqid')!=reqid
                    or epoch.get('active_reqid') not in (None,reqid)
                    or epoch.get('weekly19_native_receipt')!=receipt):
                _fail('warm_epoch_frozen_mirror_mismatch')
        raw_rows[kind]=native
        queries[kind]=dict(reqid=reqid,completed_at=done.isoformat(),error_rows=0,last_seen=True,
            request_sent_at=sent.isoformat(),callback_count=len(callbacks),data_callback_count=len(native))
    bundle=dict(identity=identity,receipts=receipts)
    if funding._hash(original)!=before: _fail('warm_native_receipt_changed_during_read')
    if len(raw_rows['account'])!=1: _fail('warm_unique_native_cny_account_required')
    account=raw_rows['account'][0];day=provider._day(account['TradingDay'])
    for kind,native in raw_rows.items():
        for row in native:
            if provider._fingerprint(row,'AccountID' if kind=='account' else 'InvestorID')!=identity['account_key']:
                _fail('warm_native_row_account_mismatch')
            if provider._day(row['TradingDay'])!=day: _fail('warm_native_row_trading_day_mismatch')
    native_ids=set();system_ids=set()
    callbacks=[row for row in receipts['orders']['native_callbacks'] if row['data']]
    for order,callback in zip(raw_rows['orders'],callbacks):
        native_id=provider._native_order_id(order)
        if native_id in native_ids: _fail('warm_native_order_identity_duplicate')
        native_ids.add(native_id)
        status=provider._native_order_status(order)
        system=str(order.get('OrderSysID','')).strip()
        if not system and status not in ('accepted','rejected'): _fail('warm_native_order_system_id_missing')
        if system:
            key=(order['ExchangeID'],system)
            if key in system_ids: _fail('warm_native_order_system_identity_duplicate')
            system_ids.add(key)
        if order.get('InsertDate') or order.get('InsertTime'):
            inserted=datetime.strptime(order['InsertDate']+' '+order['InsertTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
            if inserted>funding._time(callback['received_at']): _fail('warm_native_order_after_query_callback')
    return bundle,raw_rows,queries,day


def _capability(policy,identity):
    reference=policy.get('capture_authority_registry');capability=policy.get('capture_authority_capability')
    if reference is None: _fail('warm_capture_authority_missing:active_registry')
    if capability is not None:
        return provider._authority_for(reference,identity,policy['now'],capability=capability)
    return provider.load_capture_authority_registry(reference,expected_account_key=identity['account_key'],
        material_release_id=identity['material_release_id'],execution_profile=identity['execution_profile'],
        trusted_source_hashes=policy['trusted_source_hashes'],now=policy['now'])


def _authority_context(body):
    identity=body['bundle']['identity']
    return dict(connection_generation=identity['connection_generation'],service_generation=identity['service_generation'],
        native_source_sha256=funding._hash(body['bundle']),generated_at=body['generated_at'],runner=body['runner'],source_hashes=body['source_hashes'])


def persist_warm_native_query_capture(path,transport_context,**policy):
    """Persist at completed query boundary, before the final API slot.

    A preloaded typed capability avoids full qualification validation inside the
    final order slot. Conditional fixture mode never creates an authority key.
    """
    try:
        bundle,_,_,_=_freeze(transport_context,policy)
        body=dict(schema='weekly19.warm-native-query-capture.v1',bundle=bundle,
            generated_at=funding._time(policy['now']).isoformat(),runner='run_qmt_roll_stage931_official_live_ctp_submit_adapter.py',
            source_hashes={name:provider._source_digest(name) for name in provider.CAPTURE_AUTHORITY_SOURCE_FILES},production_qualified=False)
        authority=None
        if policy.get('require_production_qualification',True) or policy.get('capture_authority_registry') is not None:
            authority=_capability(policy,bundle['identity'])
        payload=funding._canonical(body);provider._write_private(path,payload)
        reference=dict(path=str(path),sha256=provider._digest(payload),schema=body['schema'],source_qualified=False,production_qualified=False)
        if authority is not None:
            reference['authority_receipt']=authority._write_receipt(Path(str(path)+'.authority.json'),'warm_epoch_snapshot',_authority_context(body),reference['sha256'])
            reference['source_qualified']=True
        return reference
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        if isinstance(exc,WarmEvidenceError): raise
        raise WarmEvidenceError('warm_capture_persist_rejected:'+str(exc)) from exc


def _trade_rows(raw,day,receipt):
    result=[];seen=set()
    data_callbacks=[row for row in receipt['native_callbacks'] if row['data']]
    for index,trade in enumerate(raw['trades']):
        matches=[order for order in raw['orders'] if order['ExchangeID']==trade['ExchangeID']
                 and str(order.get('OrderSysID','')).strip()==str(trade.get('OrderSysID','')).strip()]
        if len(matches)!=1: _fail('warm_native_trade_order_proof_not_unique')
        order=matches[0]
        if order['CombOffsetFlag']!=trade['OffsetFlag'] or order['Direction']!=trade['Direction']:
            _fail('warm_native_trade_order_direction_or_offset_mismatch')
        direction={'0':'long','1':'short'}.get(trade['Direction'])
        if direction is None: _fail('warm_native_trade_direction_unknown')
        broker_offset=provider._native_offset(trade['OffsetFlag'])
        stable='ctp:'+trade['BrokerID']+':'+trade['InvestorID']+':'+trade['ExchangeID']+':'+trade['TradeDate']+':'+trade['OrderSysID'].strip()+':'+funding._text(trade['TradeID'].strip(),'trade_id')
        if stable in seen: _fail('warm_native_trade_identity_duplicate')
        seen.add(stable)
        executed=datetime.strptime(trade['TradeDate']+' '+trade['TradeTime'],'%Y%m%d %H:%M:%S').replace(tzinfo=funding.SHANGHAI)
        if executed>funding._time(data_callbacks[index]['received_at']): _fail('warm_native_trade_after_query_callback')
        result.append(dict(broker_trade_identity=stable,trade_id=stable,broker_order_id=provider._native_order_id(order),
            vt_symbol=provider._symbol(trade),direction=direction,offset=provider._business_offset(broker_offset),
            business_offset=provider._business_offset(broker_offset),broker_offset=broker_offset,native_offset_flag=trade['OffsetFlag'],
            volume=_integer(trade['Volume'],1),price=provider._native_decimal(trade['Price'],money=False,positive=True),
            trading_day=day,execution_datetime=executed.isoformat(),
            raw_native_sha256=funding._hash(trade)))
    return result


def load_warm_broker_snapshot(transport_context,**policy):
    """Read existing same-connection completed native epochs. NO new queries."""
    try:
        bundle,raw,queries,day=_freeze(transport_context,policy)
        identity=bundle['identity'];source=funding._hash(bundle);qualified=None
        reference=transport_context.get('weekly19_warm_capture_reference')
        if policy.get('require_production_qualification',True) or policy.get('capture_authority_registry') is not None:
            if not isinstance(reference,dict) or not reference.get('authority_receipt'):
                _fail('warm_capture_authority_missing:signed_frozen_epochs')
            authority=_capability(policy,identity)
            payload=provider._safe_read(reference['path'],private=True)
            if provider._digest(payload)!=reference['sha256']: _fail('warm_capture_sha256_mismatch')
            body=provider._json(payload)
            if (body.get('schema')!='weekly19.warm-native-query-capture.v1' or body.get('production_qualified') is not False
                    or body.get('bundle')!=bundle): _fail('warm_capture_current_epoch_mismatch')
            if not 0<=(funding._time(policy['now'])-funding._time(body['generated_at'])).total_seconds()<=300:
                _fail('warm_capture_stale_or_future')
            for name in provider.CAPTURE_AUTHORITY_SOURCE_FILES:
                if body['source_hashes'].get(name)!=provider._source_digest(name): _fail('warm_capture_source_hash_mismatch')
            qualified=authority._verify_receipt(reference['authority_receipt'],'warm_epoch_snapshot',_authority_context(body),reference['sha256'])
        capture=dict(account_key=identity['account_key'],material_release_id=identity['material_release_id'],execution_profile=identity['execution_profile'],
            broker_trading_day=raw['account'][0]['TradingDay'],generation_uuid=source,queries=queries,
            generated_at=max(row['completed_at'] for row in queries.values()),
            raw_queried_accounts=raw['account'],raw_queried_positions=raw['positions'],raw_queried_orders=raw['orders'],
            _verified_authority=qualified,runner_provenance=dict(source_hashes={name:policy['trusted_source_hashes'][name] for name in (*provider.CAPTURE_SOURCE_FILES,WARM_SOURCE)}))
        manifest=dict(weekly19_capture=dict(sha256=source,source_kind='same_connection_frozen_native_epochs'))
        snapshot=provider._public({},manifest,capture,{})
        for key in ('account','positions','orders'):
            body=provider._json(snapshot[key]['raw_payload'])
            body.update(capture_kind='warm_epoch_snapshot',connection_generation=identity['connection_generation'],
                service_generation=identity['service_generation'],native_source_sha256=source)
            snapshot[key]=provider._envelope(body)
        trades=provider._common(capture,queries['trades'])
        trades.update(schema='weekly19.ctp-trades.v1',source_kind='ctp_trade_query',capture_kind='warm_epoch_snapshot',
            connection_generation=identity['connection_generation'],service_generation=identity['service_generation'],
            native_source_sha256=source,trades=_trade_rows(raw,day,bundle['receipts']['trades']))
        snapshot['trades']=provider._envelope(trades)
        snapshot.update(native_source_sha256=source,connection_generation=identity['connection_generation'],
            service_generation=identity['service_generation'],production_qualified=False,source_qualified=bool(qualified))
        return snapshot
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,WarmEvidenceError): raise
        raise WarmEvidenceError('warm_broker_snapshot_rejected:'+str(exc)) from exc


def load_warm_broker_events(transport_context,execution_ledger_rows,**policy):
    """Bind same-connection native query recovery; consume fills before orders.

    Input ledger rows must be unique derived_order_intent_bindings. Query
    callbacks remain onRspQry*, never labelled native push onRtn*.
    """
    try:
        snapshot=load_warm_broker_snapshot(transport_context,**policy)
        provider._require_verified_execution_bindings(execution_ledger_rows,policy.get('require_production_qualification',True))
        bundle,raw,queries,day=_freeze(transport_context,policy)
        source=funding._hash(bundle)
        if snapshot['native_source_sha256']!=source: _fail('warm_recovery_source_changed')
        common=dict(bundle['identity'],trading_day=day,generation_uuid=source,capture_kind='warm_epoch_snapshot',
            native_source_sha256=source,production_qualified=False)
        orders=[];fills=[]
        for native in raw['orders']:
            context=dict(common,observed_at=queries['orders']['completed_at'],query_reqid=queries['orders']['reqid'],query_complete=True)
            orders.append(provider._order_event(native,execution_ledger_rows,context,source_callback='onRspQryOrder',capture_sha256=source))
        trade_rows=provider._json(snapshot['trades']['raw_payload'])['trades']
        for native,row in zip(raw['trades'],trade_rows):
            native_orders=[order for order in raw['orders'] if order['ExchangeID']==native['ExchangeID']
                           and str(order['OrderSysID']).strip()==str(native['OrderSysID']).strip()]
            if len(native_orders)!=1: _fail('warm_recovery_native_order_mapping_not_unique')
            binding=provider._order_intent_binding(native_orders[0],execution_ledger_rows,common)
            body=dict(common,**{key:value for key,value in binding.items() if key!='volume'},schema='weekly19.ctp-trade.v1',
                source_kind='ctp_trade_callback',source_callback='onRspQryTrade',observed_at=queries['trades']['completed_at'],
                query_reqid=queries['trades']['reqid'],query_complete=True,trade_id=row['trade_id'],volume=row['volume'],
                price=row['price'],business_offset=row['offset'],native_offset_flag=row['native_offset_flag'],
                trade_datetime=row['execution_datetime'],execution_datetime=row['execution_datetime'],
                raw_native_sha256=row['raw_native_sha256'],raw_capture_sha256=source)
            fills.append(provider._envelope(body))
        if funding._hash(transport_context['rows']['_weekly19_native_receipts'])!=funding._hash(bundle['receipts']):
            _fail('warm_recovery_source_changed')
        return dict(fills=fills,orders=orders,apply_order=['fills','orders'],native_source_sha256=source,
            source_qualified=snapshot['source_qualified'],production_qualified=False)
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,WarmEvidenceError): raise
        raise WarmEvidenceError('warm_broker_recovery_rejected:'+str(exc)) from exc
