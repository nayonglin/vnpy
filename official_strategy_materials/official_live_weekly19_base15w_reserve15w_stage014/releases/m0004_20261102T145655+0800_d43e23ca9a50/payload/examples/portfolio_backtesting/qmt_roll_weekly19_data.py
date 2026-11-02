"""Explicit, read-only approved daily DTOs for weekly19.

No vnpy_sqlite driver, default database, market requests, zero-price fallback or
qualification inheritance. A correct conditional read is not production approval.
"""
from __future__ import annotations

from datetime import date, datetime, time
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from qmt_roll_weekly19_runtime import ASSETS, verify_frozen_sources

FILES=('daily.sqlite','mapping.csv','physical_epoch_daily.csv','metadata.csv','receipt.json')
SHANGHAI=ZoneInfo('Asia/Shanghai')
SHA=re.compile(r'[0-9a-f]{64}')
NATIVE=re.compile(r'([A-Za-z]+)[0-9]{3,4}\.([A-Z]+)')


class DataInputError(ValueError):
    """An explicit snapshot does not meet the declared read contract."""


def _fail(reason):
    raise DataInputError(reason)


def _now():
    return datetime.now(SHANGHAI)


def _day(value):
    if not isinstance(value,str):
        _fail('iso_trading_date_required')
    try:
        if date.fromisoformat(value).isoformat()!=value:
            _fail('iso_trading_date_required')
    except ValueError:
        _fail('iso_trading_date_required')
    return value


def _sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def _hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _fixed_products():
    verify_frozen_sources()
    asset=json.loads((ASSETS/'actual_settings.json').read_text())
    path=ASSETS/'static19.csv'
    if _sha(path)!=asset['assets']['static19.csv']['sha256']:
        _fail('fixed19_asset_hash_mismatch')
    frame=pd.read_csv(path)
    if 'eligible' in frame:
        frame=frame.loc[pd.to_numeric(frame.eligible,errors='raise')==1]
    result=sorted(set(frame.product_vt_symbol.astype(str)))
    if len(result)!=19:
        _fail('fixed19_asset_invalid')
    return result


def _product(symbol):
    match=NATIVE.fullmatch(str(symbol))
    return None if match is None else match.group(1)+'.'+match.group(2)


def _hashes(root,expected):
    result={}
    if not isinstance(expected,dict):
        _fail('explicit_source_hashes_required')
    for name in FILES:
        want=expected.get(name)
        if not isinstance(want,str) or not SHA.fullmatch(want):
            _fail('source_hash_required:'+name)
        path=root/name
        if not path.is_file():
            _fail('source_file_missing:'+name)
        result[name]=_sha(path)
        if result[name]!=want:
            _fail('source_hash_mismatch:'+name)
    for suffix in ('-wal','-journal'):
        sidecar=root/('daily.sqlite'+suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            _fail('sqlite_uncheckpointed_sidecar')
    return result


def _calendar(value,mapping_dates,target,expected):
    if isinstance(value,(str,Path)):
        path=Path(value).expanduser().resolve(strict=True)
        want=expected.get('forward_calendar') or expected.get(path.name)
        if not isinstance(want,str) or not SHA.fullmatch(want) or _sha(path)!=want:
            _fail('forward_calendar_hash_required_or_mismatch')
        frame=pd.read_csv(path,dtype=str)
        if 'date' not in frame:
            _fail('forward_calendar_date_column_missing')
        dates=frame.date.tolist();source=dict(kind='explicit_file',sha256=want)
    else:
        try:dates=list(value)
        except TypeError:_fail('forward_calendar_sequence_required')
        source=dict(kind='caller_declared_dates',sha256=_hash(dates))
    dates=[_day(d) for d in dates]
    if len(set(dates))!=len(dates):
        _fail('forward_calendar_duplicate_dates')
    calendar=sorted(set(mapping_dates)|set(dates))
    if target not in calendar or not any(date.fromisoformat(d).isocalendar()[:2]>date.fromisoformat(target).isocalendar()[:2] for d in dates):
        _fail('next_iso_week_calendar_required')
    return calendar,source


def _metadata(path,products,symbols,source_map,mapping):
    # Original frozen helpers with the metadata path explicitly supplied. No
    # default/private checkout metadata or vn.py database driver is consulted.
    from weekly19_frozen.contract_metadata import build_resolved_metadata
    from weekly19_frozen.main_contract_mapping import _product_defaults
    frame=pd.read_csv(path)
    if frame.empty or 'vt_symbol' not in frame:
        _fail('metadata_explicit_rows_required')
    product_frame=frame if 'symbol_kind' not in frame else frame.loc[frame.symbol_kind=='product_cont']
    product_rows={str(row.vt_symbol):row for _,row in product_frame.iterrows()}
    defaults={p:_product_defaults(p,product_rows) for p in products}
    resolved=build_resolved_metadata(symbols,
        {s:int(defaults[source_map[s]]['size']) for s in symbols},
        {s:float(defaults[source_map[s]]['pricetick']) for s in symbols},
        {s:float(defaults[source_map[s]]['margin_ratio']) for s in symbols},
        fallback_symbol_by_vt=source_map,metadata_path=path)
    for name in ('sizes','priceticks','margin_ratios'):
        if any(not math.isfinite(float(v)) or float(v)<=0 for v in resolved[name].values()):
            _fail('positive_contract_metadata_required:'+name)
    return dict(vt_symbols=symbols,product_symbols=products,source_symbol_by_contract=source_map,
        daily_mapping=mapping,**resolved,
        rates={s:float(defaults[source_map[s]]['rate']) for s in symbols},
        slippages={s:float(defaults[source_map[s]]['slippage']) for s in symbols})


def _read_sqlite(path,physical):
    wanted=[]
    for row in physical[['vt_symbol','date','open','high','low','close','volume','close_oi']].itertuples(index=False,name=None):
        symbol,day,*values=row;code,exchange=symbol.split('.')
        wanted.append((symbol,code,exchange,day,*map(float,values)))
    batches={};seen=set();checked=0
    with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.execute('pragma temp_store=MEMORY')
        columns={row[1] for row in db.execute('pragma table_info(dbbardata)')}
        if not {'id','symbol','exchange','datetime','interval','open_price','high_price','low_price','close_price','volume','turnover','open_interest'}<=columns:
            _fail('sqlite_daily_schema_missing')
        db.execute('create temp table wanted(vt text,symbol text,exchange text,day text,op real,hi real,lo real,cl real,vol real,oi real,primary key(symbol,exchange,day)) without rowid')
        db.executemany('insert into wanted values(?,?,?,?,?,?,?,?,?,?)',wanted)
        query='''select w.vt,w.day,w.op,w.hi,w.lo,w.cl,w.vol,w.oi,
            d.id,d.datetime,d.open_price,d.high_price,d.low_price,d.close_price,d.volume,d.open_interest,d.turnover
            from wanted w left join dbbardata d on d.symbol=w.symbol and d.exchange=w.exchange
            and d.interval='d' and substr(d.datetime,1,10)=w.day'''
        for row in db.execute(query):
            symbol,day,*tail=row
            expected=tail[:6];row_id,raw_time=tail[6:8];actual=tail[8:14];turnover=tail[14]
            key=(symbol,day)
            if key in seen:_fail('duplicate_sqlite_daily_key:'+symbol+':'+day)
            seen.add(key)
            if row_id is None:_fail('approved_sqlite_bar_missing:'+symbol+':'+day)
            try:
                actual=list(map(float,actual));turnover=float(turnover)
            except (TypeError,ValueError):_fail('sqlite_physical_nonfinite:'+symbol+':'+day)
            if any(not math.isfinite(a) or not math.isclose(a,e,rel_tol=0,abs_tol=1e-9) for a,e in zip(actual,expected)):
                _fail('sqlite_physical_value_mismatch:'+symbol+':'+day)
            if not math.isfinite(turnover) or turnover<0:_fail('sqlite_turnover_invalid')
            dt=datetime.fromisoformat(str(raw_time))
            if dt.date().isoformat()!=day:_fail('sqlite_daily_time_mismatch')
            code,exchange=symbol.split('.')
            op,hi,lo,cl,volume,oi=actual
            batches.setdefault(day,{})[symbol]=BarData(symbol=code,exchange=Exchange(exchange),datetime=dt,
                interval=Interval.DAILY,gateway_name='WEEKLY19_APPROVED_READ',open_price=op,high_price=hi,
                low_price=lo,close_price=cl,volume=volume,open_interest=oi,turnover=turnover)
            checked+=1
    return dict(sorted(batches.items())),dict(checked_rows=checked,positive_source_keys=len(physical),
        mismatches=0,duplicates=0,reader='python_sqlite3_readonly_explicit_DTO_v1',production_qualified=False)


def load_weekly19_inputs(asset_root,*,material_release_id,target_date,forward_calendar,expected_hashes):
    """Read an exact approved snapshot conditionally, never confer qualification.

    ``expected_hashes`` binds the five named files. A calendar file additionally
    needs its expected hash; a caller-supplied date list is labeled declared.
    All returned bars are actual SQL rows admitted in physical history. Only
    target main coverage is asserted, not unknown external holdings/readiness.
    """
    target=_day(target_date);today=_now().astimezone(SHANGHAI)
    if date.fromisoformat(target)>today.date() or (target==today.date().isoformat() and today.time()<time(15,0)):
        _fail('target_trading_day_not_completed')
    if not isinstance(material_release_id,str) or not material_release_id.strip():
        _fail('material_release_id_required')
    root=Path(asset_root).expanduser().resolve(strict=True)
    before=_hashes(root,expected_hashes)
    source=json.loads((root/'receipt.json').read_text())
    if source.get('units')!='single_sided_volume_close_oi':_fail('single_sided_close_oi_units_required')
    if source.get('data_ready') is not True or source.get('date_end')!=target:
        _fail('exact_completed_source_receipt_required')
    products=_fixed_products()
    if set(source.get('products',[]))!=set(products):_fail('receipt_fixed19_products_mismatch')
    mapping_frame=pd.read_csv(root/'mapping.csv',dtype=str).fillna('')
    if not {'date','continuous_symbol_vt','main_contract_vt'}<=set(mapping_frame):_fail('mapping_schema_missing')
    mapping_frame=mapping_frame.loc[mapping_frame.continuous_symbol_vt.isin(products)].copy()
    mapping_frame['date']=mapping_frame.date.map(_day)
    mapping_frame=mapping_frame.loc[mapping_frame.date<=target]
    if mapping_frame.duplicated(['date','continuous_symbol_vt']).any():_fail('mapping_duplicate_product_day')
    mapping={d:dict(zip(rows.continuous_symbol_vt,rows.main_contract_vt)) for d,rows in mapping_frame.groupby('date',sort=True)}
    if target not in mapping or set(mapping[target])!=set(products) or any(not s for s in mapping[target].values()):
        _fail('target_main_mapping_incomplete')
    calendar,calendar_source=_calendar(forward_calendar,sorted(mapping),target,expected_hashes)
    physical=pd.read_csv(root/'physical_epoch_daily.csv',dtype={'vt_symbol':str,'date':str,'contract_epoch_id':str})
    required={'vt_symbol','date','contract_epoch_id','open','high','low','close','volume','close_oi'}
    if not required<=set(physical):_fail('physical_epoch_daily_schema_missing')
    if physical[['vt_symbol','date','contract_epoch_id']].isna().any().any():_fail('physical_identity_missing')
    physical['date']=physical.date.map(_day)
    physical=physical.loc[physical.vt_symbol.map(_product).isin(products)&(physical.date<=target)].copy()
    if physical.empty or physical.duplicated(['vt_symbol','date']).any():_fail('physical_empty_or_duplicate_key')
    for column in ['open','high','low','close','volume','close_oi']:
        physical[column]=pd.to_numeric(physical[column],errors='raise').astype(float)
        if not np.isfinite(physical[column]).all() or (physical[column]<(0 if column=='close_oi' else np.nextafter(0.,1.))).any():
            _fail('physical_nonpositive_or_nonfinite:'+column)
    if ((physical.low>physical[['open','close']].min(axis=1))|(physical.high<physical[['open','close']].max(axis=1))).any():
        _fail('physical_ohlc_invalid')
    if any(d not in calendar for d in physical.date.unique()):_fail('physical_day_not_in_calendar')
    physical=physical.sort_values(['vt_symbol','date']).reset_index(drop=True)
    keys=set(zip(physical.vt_symbol,physical.date))
    for symbol in mapping[target].values():
        if (symbol,target) not in keys:_fail('target_main_admitted_bar_missing:'+symbol)
    source_map={s:_product(s) for s in sorted(physical.vt_symbol.unique())}
    for rows in mapping.values():
        for product,symbol in rows.items():
            if not symbol:continue
            if _product(symbol)!=product:_fail('mapping_native_product_identity_invalid')
            if symbol in source_map and source_map[symbol]!=product:_fail('contract_multiple_products')
            source_map[symbol]=product
    metadata=_metadata(root/'metadata.csv',products,sorted(source_map),source_map,mapping)
    bars,parity=_read_sqlite(root/'daily.sqlite',physical)
    admissions=source.get('new_contract_history_admissions',[])
    if not isinstance(admissions,list):_fail('new_contract_admission_list_required')
    metadata['new_contract_history_admissions']=admissions
    admitted_symbols={row.get('vt_symbol') for row in admissions}
    metadata['new_contract_history_bars']={symbol:[batch[symbol] for batch in bars.values() if symbol in batch]
        for symbol in sorted(admitted_symbols) if symbol in source_map}
    after=_hashes(root,expected_hashes)
    if before!=after:_fail('source_changed_during_read')
    if isinstance(forward_calendar,(str,Path)) and _sha(Path(forward_calendar))!=calendar_source['sha256']:
        _fail('forward_calendar_changed_during_read')
    identity=dict(files=before,calendar=calendar_source,source_reader_sha256=_sha(__file__))
    metadata['source_sha256']=_hash(identity)
    receipt=dict(schema='weekly19.data-receipt.v1',trading_date=target,complete=True,
        material_release_id=material_release_id,source_sha256=metadata['source_sha256'],
        source_hashes=before,calendar_provenance=calendar_source,sqlite_physical_parity=parity,
        target_main_positive_coverage_count=19,known_physical_contract_count=len(physical.vt_symbol.unique()),
        conditional_read=True,production_qualified=False,qualification_status='conditional_read_unqualified',
        source_receipt_schema=source.get('schema'),source_data_ready_declared=True,
        historical_main_reconstruction_complete=source.get('historical_main_reconstruction_complete',False),
        readiness_limitations=list(source.get('readiness_limitations',[])),
        all_external_held_contract_coverage_proven=False,strategy_weekly_readiness_asserted=False)
    return dict(metadata=metadata,calendar=calendar,physical_epoch_daily=physical,bars_by_day=bars,receipt=receipt,
                source_hashes_before=before,source_hashes_after=after)
