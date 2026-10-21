"""One public-API quote metadata batch; no date/session qualification or trading.

Root alone invokes run_batch after exact authorization.  Async get_quote_list
captures public references without awaiting the SDK's price-datetime readiness.
Only the explicitly selected metadata fields are copied, never Quote/vars().
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import logging
import math
from numbers import Integral, Real
from pathlib import Path
import re
import time

TOOLS=Path(__file__).resolve().parent
ROOT=TOOLS.parents[3]
TRANSPORT_SHA='4325fea74aa7718833637bd99dd4c8d0bb880a01a3d9fb0f0810a9512cee7992'
LIMITS=dict(critical_seconds=82.,connect_seconds=40.,metadata_seconds=35.,close_seconds=8.,
            network_total_seconds_max=90.,retries=0)
FIELDS=('instrument_id','exchange_id','ins_class','trading_time.day','trading_time.night',
        'delivery_year','delivery_month','expire_datetime','price_tick','volume_multiple')
_transport=None


def transport():
    global _transport
    if _transport is None:
        path=TOOLS/'stage336_recent_daily_receiver.py'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=TRANSPORT_SHA:
            raise ValueError('frozen336 transport helper changed')
        spec=importlib.util.spec_from_file_location('stage348_accepted336',path)
        _transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(_transport)
    return _transport


def connect_explicit(api_factory,auth_factory,sim_factory,username,password):
    """Explicit simulation account; never permit environment-selected accounts."""
    provider_auth=auth_factory(username,password)
    return api_factory(sim_factory(),auth=provider_auth,debug=False,disable_print=True,web_gui=False)


def new_report(symbols,source_version,identities):
    return dict(schema='stage348_quote_metadata_capture_v1',status='pending',source_version=source_version,
        T0=None,active=False,source_completed_at=None,D_open_at=None,forward_observations=0,
        periodic_template_only=True,canonical_rows_accepted=False,new_fit=0,new_cash=0,
        requests=dict(quote_list=0,catalog=0,price_serial=0,CTP=0,orders=0),items={s:dict(
            symbol=s,status='unknown',prior_contract_epoch_id=identities.get(s),
            prior_identity_state='known_explicit' if s in identities else 'unknown',
            model_input_eligible=False,source_completed_at=None,D_open_at=None,
            units_status='metadata_crosscheck_only',fields={k:dict(value=None,state='unknown',
                reason='not_received') for k in FIELDS}) for s in symbols})


def _get(value,key):
    return value[key] if isinstance(value,dict) else getattr(value,key)


def _field(quote,name):
    try:
        value=quote
        for part in name.split('.'):value=_get(value,part)
    except (KeyError,AttributeError,TypeError):
        return dict(value=None,state='unknown',reason='field_missing')
    valid=False;copied=None
    if name in ('instrument_id','exchange_id','ins_class'):
        valid=isinstance(value,str) and bool(value);copied=value if isinstance(value,str) else None
    elif name.startswith('trading_time.'):
        if isinstance(value,(list,tuple)):
            copied=[list(p) if isinstance(p,(list,tuple)) else None for p in value]
            valid=all(p is not None and len(p)==2 and all(isinstance(t,str) and
                re.fullmatch(r'\d{2,3}:[0-5]\d:[0-5]\d',t) for t in p) for p in copied)
            valid=valid and (bool(copied) or name.endswith('.night'))
    elif name in ('delivery_year','delivery_month','volume_multiple'):
        if isinstance(value,Integral) and not isinstance(value,bool):
            copied=int(value);valid=copied>0
            if name=='delivery_year':valid=1900<=copied<=2199
            if name=='delivery_month':valid=1<=copied<=12
    elif isinstance(value,Real) and not isinstance(value,bool):
        copied=float(value);valid=math.isfinite(copied) and copied>0
        if not math.isfinite(copied):copied=None
    return dict(value=copied,state='known' if valid else 'unknown',
                reason=None if valid else 'sdk_default_or_invalid')


def _snapshot(quote,row):
    """Update in place so an interruption retains all preceding field copies."""
    for name in FIELDS:row['fields'][name]=_field(quote,name)
    fields=row['fields']
    if fields['trading_time.night']['value']==[] and fields['trading_time.day']['state']!='known':
        fields['trading_time.night'].update(state='unknown',reason='empty_night_without_day_template')
    applies=(fields['instrument_id']['value']==row['symbol'] and
             fields['exchange_id']['value']==row['symbol'].split('.')[0] and
             fields['ins_class']['value']=='FUTURE')
    row['response_matches_requested_symbol']=applies
    known=sum(v['state']=='known' for v in fields.values())
    row['status']='metadata_ready' if known==len(FIELDS) and applies else ('partial' if known else 'unknown')
    if not applies:row['response_identity_reason']='missing_or_mismatched_response_identity'


def capture_metadata(api,symbols,report,*,secrets=()):
    """Exactly one get_quote_list, called inside a public scheduled coroutine.

    No await of QuoteList: its SDK task waits for quote.datetime and would lose
    retired contracts' otherwise usable metadata.  Price/timestamp never gates
    readiness here.  Any failure leaves every requested row and copied field.
    """
    holder={};task=None
    async def request():
        report['requests']['quote_list']+=1
        holder['refs']=api.get_quote_list(symbols)
    try:
        with transport()._alarm(LIMITS['metadata_seconds']):
            task=api.create_task(request())
            deadline=time.time()+LIMITS['metadata_seconds'];no_more_updates=False
            while True:
                if task.done():task.result()
                refs=holder.get('refs')
                if refs is not None:
                    report['quote_refs_received']=len(refs)
                    if len(refs)!=len(symbols):raise ValueError('public quote list length differs from request')
                    for symbol,quote in zip(symbols,refs):_snapshot(quote,report['items'][symbol])
                    if all(v['status']=='metadata_ready' for v in report['items'].values()):break
                if no_more_updates or time.time()>=deadline:
                    report['stop_reason']='metadata_deadline';break
                if not api.wait_update(deadline=deadline):no_more_updates=True
    except Exception as error:
        report.update(stop_reason='metadata_capture_error',**transport()._error(error,secrets))
    finally:
        for row in report['items'].values():
            for field in row['fields'].values():
                if field['reason']=='not_received':field['reason']=report.get('stop_reason','metadata_not_received')
        report['status']='completed' if all(v['status']=='metadata_ready' for v in report['items'].values()) else 'partial'
    return report


def run_batch(authorization,output):
    """Root-only actual path. Adapter creates fresh output before connection."""
    b=transport();auth=b.read_json(authorization) if isinstance(authorization,(str,Path)) else dict(authorization)
    if (auth.get('schema')!='stage348_quote_metadata_authorization_v1' or auth.get('authorized') is not True
            or auth.get('T0') is not None or auth.get('limits')!=LIMITS
            or auth.get('read_budget')!=dict(API_connections=1,quote_list=1,catalog=0,price_serial=0,
                CTP=0,orders=0,old_cache=0,economics=0,SQL=0,new_fit=0,new_cash=0)):
        raise ValueError('exact root metadata-only authorization required')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh metadata output required before credentials/API')
    bundle=json.loads(b._bound(auth['source_bundle']))
    for binding in bundle['sources']:b._bound(binding)
    inputs=auth['inputs'];scope=json.loads(b._bound(inputs['scope345']))
    catalog=json.loads(b._bound(inputs['catalog338']));identity=json.loads(b._bound(inputs['identity_map338']))
    if (scope.get('schema')!='stage345_minimum_session_metadata_scope_v1'
            or scope.get('status')!='authorized_next_minimum_metadata_task' or scope.get('T0') is not None):
        raise ValueError('accepted345 next_scope required')
    symbols=catalog['symbols'];identities=identity['identity_map']
    if (symbols!=sorted(set(symbols)) or len(symbols)!=874 or len(catalog['fresh_symbols'])!=870
            or len(catalog['added_symbols'])!=4 or len(catalog['just_retired_symbols'])!=4
            or catalog.get('ins_class')!='FUTURE' or catalog.get('expired') is not False
            or set(symbols)!=set(catalog['fresh_symbols'])|set(catalog['just_retired_symbols'])
            or len(identities)!=794 or not set(identities)<=set(symbols)
            or any(b.symbol_parts(s) is None for s in symbols)):
        raise ValueError('exact338 true-month874 union/root794 map required')
    if importlib.metadata.version('tqsdk')!=auth['tqsdk_version']:raise ValueError('root SDK version mismatch')
    out.mkdir(parents=True)
    journal=b.load_journal().ForwardJournal(auth['journal_path'],auth['journal_identity'])
    report=new_report(symbols,'tqsdk/'+auth['tqsdk_version'],identities)
    for symbol,row in report['items'].items():
        row.update(in_fresh_catalog=symbol in catalog['fresh_symbols'],
                   added_symbol=symbol in catalog['added_symbols'],just_retired=symbol in catalog['just_retired_symbols'])
    api=None;secrets=[];attempts=0;old_logging=logging.root.manager.disable;start=time.monotonic()
    try:
        cfg=b.read_json(auth['credential_path'])
        username,password=b._pure(b.CREDENTIAL_SOURCE,b.CREDENTIAL_SHA,'require_credentials',{'SETTINGS':cfg})();del cfg
        secrets=[username,password];logging.disable(logging.CRITICAL)
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(LIMITS['critical_seconds']):
            from tqsdk import TqApi,TqAuth,TqSim
            with b._alarm(LIMITS['connect_seconds']):
                attempts+=1;api=connect_explicit(TqApi,TqAuth,TqSim,username,password)
            capture_metadata(api,symbols,report,secrets=secrets)
    except Exception as error:
        report.update(status='partial',stop_reason='connection_or_global_error',**b._error(error,secrets))
        for row in report['items'].values():
            for field in row['fields'].values():
                if field['reason']=='not_received':field['reason']='connection_or_global_error'
    finally:
        if api is not None:
            try:
                with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(LIMITS['close_seconds']):api.close()
                report['close_status']='closed'
            except Exception as error:
                report.update(status='partial',close_status='close_error',close_error=b._error(error,secrets))
        logging.disable(old_logging)
    report.update(network_wall_seconds=time.monotonic()-start,api_instances_attempted=attempts,retries=0)
    receipt=journal.append('quote_metadata_batch',report,key=out.name+':metadata')
    for row in report['items'].values():
        row.update(received_at=receipt['recorded_at'],receipt_entry_hash=receipt['entry_hash'])
    metadata=b._write(out/'metadata.json',dict(schema='stage348_quote_metadata_rows_v1',
        source_version=report['source_version'],receipt=receipt,periodic_template_only=True,items=report['items']))
    manifest={k:v for k,v in report.items() if k!='items'}
    manifest.update(schema='stage348_quote_metadata_manifest_v1',inputs=inputs,source_bundle=auth['source_bundle'],
        limits=LIMITS,artifacts=dict(metadata=metadata),receipt=receipt,symbols=len(symbols),
        prior_identity_unknown=sum(v['prior_identity_state']=='unknown' for v in report['items'].values()),
        metadata_ready=sum(v['status']=='metadata_ready' for v in report['items'].values()),
        actual_UTC_receipt=receipt['recorded_at'],finished_at=datetime.now(timezone.utc).isoformat())
    b._write(out/'manifest.json',manifest)
    b._write(out/'terminal.json',dict(schema='stage348_quote_metadata_terminal_v1',status=manifest['status'],
        symbols=manifest['symbols'],metadata_ready=manifest['metadata_ready'],api_instances_attempted=attempts,
        quote_list_calls=report['requests']['quote_list'],retries=0,T0=None,new_fit=0,new_cash=0,
        manifest=dict(path=str(out/'manifest.json')),finished_at=manifest['finished_at']))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--authorization',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    if not args.execute:raise SystemExit('explicit --execute required')
    result=run_batch(args.authorization,args.output)
    print(json.dumps(dict(status=result['status'],metadata_ready=result['metadata_ready'],T0=None,new_fit=0,new_cash=0)))
    return 0 if result['status']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
