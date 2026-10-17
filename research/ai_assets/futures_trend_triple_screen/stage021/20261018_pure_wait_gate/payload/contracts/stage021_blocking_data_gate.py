"""Pure synchronous data-qualification gate before the original order context.

No provider, financial replay, price fallback or order mutation is implemented.
The external resolver receives only a JSON request and returns pinned review
and CSV paths. It must never advance or mutate the waiting engine.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old

FIELDS=['vt_symbol','bar_datetime',*old.VALUES]
METHOD='_stage827_order_context'
REQUEST_SCHEMA='stage021_exact_execution_minute_request_v1'
RECEIPT_SCHEMA='stage021_independent_minute_delivery_v1'
sha256=old.sha256
write_json=old.write_json


def request_sha256(request):
    """Canonical UTF-8 JSON, sorted keys, excluding the embedded digest only."""
    payload={key:value for key,value in request.items()if key!='request_sha256'}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class QualifiedDelivery:
    receipt_path: Path
    receipt_sha256: str


def _keys(frame):
    return {(str(row.vt_symbol),pd.Timestamp(row.bar_datetime))for row in frame[['vt_symbol','bar_datetime']].itertuples(index=False)}


def _frame(frame,symbol):
    if frame is None or frame.empty:
        empty=pd.DataFrame(columns=FIELDS);empty['bar_datetime']=pd.Series(dtype='datetime64[ns]')
        return empty
    normalized=old.normal_times(frame)
    if set(normalized.vt_symbol.astype(str))!={symbol}or old.minute_keys(normalized).has_duplicates:
        raise ValueError('minute_frame_symbol_identity_or_duplicate')
    return normalized


def _offset_kind(order):
    offset=getattr(order.offset,'name',str(order.offset)).upper()
    if offset in {'OPEN','开'}:return 'full_session'
    if offset in {'CLOSE','CLOSETODAY','CLOSEYESTERDAY','平','平今','平昨'}:return 'anchor'
    raise ValueError('unsupported_execution_order_offset')


def _source_contains(source,key):
    if source is None:return False
    return bool(source(*key))if callable(source)else key in source


def _state_snapshot(engine,current):
    # Execution identity only: deliberately never inspect PnL/account fields.
    def order_identity(order):
        return(id(order),str(order.vt_orderid),str(order.vt_symbol),str(order.offset),
            str(getattr(order,'direction','')),getattr(order,'price',None),getattr(order,'volume',None),
            getattr(order,'traded',None),str(getattr(order,'status','')))
    return(str(engine.datetime),tuple((str(key),order_identity(value))for key,value in engine.active_limit_orders.items()),
        order_identity(current),tuple((str(key),id(value))for key,value in engine.bars.items()))


def _read_delivery(request,delivery):
    if not isinstance(delivery,QualifiedDelivery):raise ValueError('independent_qualified_delivery_required')
    receipt_path=Path(delivery.receipt_path)
    if not receipt_path.is_absolute()or sha256(receipt_path)!=delivery.receipt_sha256:
        raise ValueError('independent_receipt_hash_or_absolute_path_required')
    receipt=json.loads(receipt_path.read_text())
    if(receipt.get('schema')!=RECEIPT_SCHEMA or receipt.get('independent_review')is not True
        or not receipt.get('reviewer')or receipt.get('qualified_research_data')is not True
        or receipt.get('p0_findings',0)or receipt.get('p1_findings',0)):
        raise ValueError('independent_data_qualification_missing')
    if receipt.get('request_sha256')!=request['request_sha256']:raise ValueError('delivery_request_hash_mismatch')
    wanted={(item['vt_symbol'],item['execution_trade_date'],item['requirement_kind']):item
        for item in request['requirements']}
    accepted={};allowed=set();full=set();anchors=set()
    for item in receipt['accepted_requirements']:
        identity=(str(item['vt_symbol']),str(item['execution_trade_date']),item['requirement_kind'])
        if identity in accepted or identity not in wanted:raise ValueError('delivery_accepted_scope_mismatch')
        if item.get('accepted')is not True or item.get('completed_bars_and_daily_qualified')is not True:
            raise ValueError('delivery_completion_and_daily_qualification_missing')
        if item['accepted_timestamps']!=wanted[identity]['required_timestamps']:
            raise ValueError('delivery_accepted_timestamp_scope_mismatch')
        scoped={(identity[0],pd.Timestamp(stamp))for stamp in item['accepted_timestamps']}
        allowed.update(scoped);(full if identity[2]=='full_session'else anchors).update(scoped)
        accepted[identity]=item
    if set(accepted)!=set(wanted):raise ValueError('delivery_accepted_scope_incomplete')
    data_path=Path(receipt['data_path']);data_sha=receipt['data_sha256']
    if not data_path.is_absolute()or receipt.get('source_fingerprints',{}).get(str(data_path))!=data_sha:
        raise ValueError('delivery_data_source_not_bound')
    payload=data_path.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=data_sha:raise ValueError('delivery_data_sha_mismatch')
    data=old.normal_times(pd.read_csv(io.BytesIO(payload)))
    if not set(FIELDS).issubset(data.columns)or old.minute_keys(data).has_duplicates or _keys(data)!=allowed:
        raise ValueError('delivery_raw_scope_or_uniqueness_mismatch')
    numeric=data[old.VALUES].to_numpy(dtype=float)
    if not np.isfinite(numeric).all()or(data[['open','high','low','close']]<=0).any().any():
        raise ValueError('delivery_invalid_numeric_values')
    if(data[['volume','open_oi','close_oi']]<0).any().any()or(data.low>data[['open','close']].min(axis=1)).any()or(
        data.high<data[['open','close']].max(axis=1)).any():raise ValueError('delivery_invalid_OHLCV_OI')
    return data[FIELDS].copy(),full,anchors,dict(receipt_path=str(receipt_path),receipt_sha256=delivery.receipt_sha256,
        data_path=str(data_path),data_sha256=data_sha,reviewer=receipt['reviewer'],accepted_keys=len(allowed))


class _Gate:
    def __init__(self,resolver,audit,common,anchor):
        self.resolver=resolver;self.audit=audit;self.common=common;self.anchor=anchor
        self.dynamic_full=set();self.dynamic_anchor=set();self.engine=None;self.original_mapping=None
        self.sequence=0;self.waiting=False

    def bind(self,engine):
        if self.engine is None:
            self.engine=engine;self.original_mapping=engine.strategy.stage827_minute_by_symbol
            if not isinstance(self.original_mapping,dict):raise ValueError('minute_container_must_be_dictionary')
            # Isolate this engine's additions from shared s901/global caches.
            engine.strategy.stage827_minute_by_symbol=dict(self.original_mapping)
        elif self.engine is not engine:raise ValueError('one_engine_per_qualified_wait_scope')

    def qualified(self,key,kind):
        if key in self.dynamic_full or _source_contains(self.common,key):return True
        return kind=='anchor'and(key in self.dynamic_anchor or _source_contains(self.anchor,key))

    def requirements(self,engine,current,current_bar):
        self.bind(engine);day=old.local_timestamp(engine.datetime).normalize();combined={};orders=[]
        active=list(engine.active_limit_orders.values())
        if not any(order is current for order in active):active.append(current)
        for order in active:
            bar=current_bar if order is current else engine.bars.get(order.vt_symbol)
            if bar is None:continue  # Exactly the original cross_delayed_orders guard.
            symbol=str(order.vt_symbol);kind=_offset_kind(order);identity=(symbol,day.date().isoformat())
            orders.append(dict(order_id=str(order.vt_orderid),vt_symbol=symbol,requirement_kind=kind))
            if identity not in combined or kind=='full_session':combined[identity]=kind
        missing=[]
        for(symbol,trading_date),kind in sorted(combined.items()):
            grid=old.session_grid(symbol,trading_date,engine.strategy.available_trade_dates)
            required=grid if kind=='full_session'else grid[:1]
            frame=_frame(engine.strategy.stage827_minute_by_symbol.get(symbol),symbol)
            present=set(frame.bar_datetime)
            needed=[stamp for stamp in required if stamp not in present or not self.qualified((symbol,stamp),kind)]
            if not needed:continue
            missing.append(dict(vt_symbol=symbol,execution_trade_date=trading_date,requirement_kind=kind,
                required_timestamps=[stamp.isoformat()for stamp in required],
                missing_or_unqualified_timestamps=[stamp.isoformat()for stamp in needed],
                existing_source_timestamps=[stamp.isoformat()for stamp in required if stamp in present]))
        return missing,orders

    def ensure(self,engine,current,current_bar):
        if self.waiting:raise ValueError('qualified_data_resolver_reentered_engine')
        missing,orders=self.requirements(engine,current,current_bar)
        if not missing:return
        self.sequence+=1
        request=dict(schema=REQUEST_SCHEMA,request_sequence=self.sequence,
            execution_trade_date=old.local_timestamp(engine.datetime).date().isoformat(),
            active_orders=orders,requirements=missing)
        request['request_sha256']=request_sha256(request)
        before=_state_snapshot(engine,current);self.waiting=True
        self.audit.append(dict(event='data_requested',request_sha256=request['request_sha256'],
            request_sequence=self.sequence,requirements=len(missing),requested_keys=sum(len(row['required_timestamps'])for row in missing)))
        try:
            delivery=self.resolver(deepcopy(request))  # The resolver never receives engine/account references.
            if _state_snapshot(engine,current)!=before:raise ValueError('resolver_changed_waiting_engine_or_orders')
            data,full,anchors,receipt=_read_delivery(request,delivery)
            updates={};added=0
            for symbol,rows in data.groupby('vt_symbol',sort=False):
                existing=_frame(engine.strategy.stage827_minute_by_symbol.get(str(symbol)),str(symbol))
                overlap=rows.loc[rows.bar_datetime.isin(existing.bar_datetime)].sort_values('bar_datetime')
                if len(overlap):
                    prior=existing.set_index('bar_datetime').loc[overlap.bar_datetime,old.VALUES].to_numpy(dtype=float)
                    if not np.array_equal(overlap[old.VALUES].to_numpy(dtype=float),prior):raise ValueError('qualified_delivery_old_value_conflict')
                new=rows.loc[~rows.bar_datetime.isin(existing.bar_datetime)].copy();added+=len(new)
                if new.empty:continue
                new['bar_date']=new.bar_datetime.dt.normalize();new['minute_source']='stage021_independently_qualified'
                if 'bar_date'not in existing:existing['bar_date']=existing.bar_datetime.dt.normalize()
                updates[str(symbol)]=(pd.concat([existing,new],ignore_index=True,sort=False)if len(existing)else new).sort_values('bar_datetime').reset_index(drop=True)
            # Commit only after all symbols, old-key comparisons and receipt gates pass.
            engine.strategy.stage827_minute_by_symbol.update(updates)
            self.dynamic_full.update(full);self.dynamic_anchor.update(anchors)
            remaining,_=self.requirements(engine,current,current_bar)
            if remaining:raise ValueError('qualified_delivery_did_not_satisfy_current_batch')
            self.audit.append(dict(event='data_qualified_appended',request_sha256=request['request_sha256'],
                appended_keys=added,old_keys_changed=0,**receipt))
        except BaseException as error:
            self.audit.append(dict(event='data_gate_failed',request_sha256=request['request_sha256'],error_type=type(error).__name__))
            raise
        finally:self.waiting=False

    def restore(self):
        if self.engine is not None and self.original_mapping is not None:
            self.engine.strategy.stage827_minute_by_symbol=self.original_mapping


@contextmanager
def qualified_wait_scope(engine_class,resolver,audit,*,qualified_existing_keys=None,qualified_anchor_existing_keys=None):
    """Patch one class temporarily, preserving whether its method was inherited.

    Existing qualification arguments are exact key sets or (symbol, Timestamp)
    predicates. Common qualification may serve OPEN/CLOSE; anchor-only may serve
    CLOSE only. None grants no implicit physical-data qualification.
    """
    local=METHOD in engine_class.__dict__;original=getattr(engine_class,METHOD)
    gate=_Gate(resolver,audit,qualified_existing_keys,qualified_anchor_existing_keys)
    def context(engine,order,bar):
        gate.ensure(engine,order,bar)
        return original(engine,order,bar)
    setattr(engine_class,METHOD,context)
    try:yield gate
    finally:
        if local:setattr(engine_class,METHOD,original)
        else:delattr(engine_class,METHOD)
        gate.restore()
