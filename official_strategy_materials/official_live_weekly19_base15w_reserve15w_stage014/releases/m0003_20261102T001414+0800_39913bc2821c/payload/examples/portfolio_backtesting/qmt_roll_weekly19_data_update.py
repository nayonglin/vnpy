"""Fixed19 read-only market fetch -> new private immutable daily asset generation.

No default database, old checkout write, order API, strategy replay or source
qualification. The public updater accepts an explicit fetch backend; the TQ
backend reuses Stage173's fetch-only mapping primitive and raw close_oi serials.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import qmt_roll_weekly19_data as reader

SHANGHAI=ZoneInfo('Asia/Shanghai')
VALUES=('open','high','low','close','volume','close_oi')

class DataUpdateError(ValueError):pass

def _fail(reason):raise DataUpdateError(reason)

def _atomic_json(path,value):
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w') as out:
            json.dump(value,out,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def _private_root(path):
    path=Path(path).expanduser().absolute()
    if path.exists() and path.is_symlink():_fail('generation_root_symlink_forbidden')
    path=path.resolve(strict=False)
    # Reject checkout targets before creating even an empty directory.
    if any((p/'.git').exists() for p in (path,*path.parents)):_fail('raw_generation_must_be_outside_git_checkout')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.stat().st_mode&0o077:_fail('generation_root_must_be_private_0700')
    return path

def build_legacy_epoch_seed_from_approved(physical_daily_path,*,trusted_sha256):
    """Derive only approved observed bounds, never invent legal listing/expiry."""
    path=Path(physical_daily_path).expanduser().resolve(strict=True)
    if not isinstance(trusted_sha256,str) or not reader.SHA.fullmatch(trusted_sha256) or reader._sha(path)!=trusted_sha256:
        _fail('approved_physical_seed_hash_mismatch')
    frame=pd.read_csv(path,dtype=str)
    if not {'vt_symbol','date','contract_epoch_id','contract_yyyymm'}<=set(frame):_fail('approved_explicit_epoch_month_required')
    records=[]
    for (symbol,epoch),group in frame.groupby(['vt_symbol','contract_epoch_id'],sort=True):
        months=set(group.contract_yyyymm)
        if len(months)!=1:_fail('legacy_epoch_delivery_month_ambiguous:'+symbol)
        code,exchange=symbol.split('.');match=re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})',code);month=next(iter(months))
        if (match is None or not re.fullmatch(r'[0-9]{4}(0[1-9]|1[0-2])',month)
                or month[-(3 if exchange=='CZCE' else 4):]!=match[2] or epoch!=exchange+'.'+match[1].upper()+'.'+month):
            _fail('legacy_epoch_native_month_mismatch:'+symbol)
        days=[reader._day(d) for d in group.date]
        records.append(dict(vt_symbol=symbol,contract_epoch_id=epoch,contract_yyyymm=month,
            observed_available_min=min(days),observed_available_max=max(days),listed_date='',delisted_date='',
            listed_unknown=True,delisted_unknown=True,lifecycle_status='approved_observed_bounds_only',
            seed_kind='legacy_approved_observed',source_sha256=trusted_sha256))
    for symbol in sorted(set(frame.vt_symbol)):
        rows=sorted([r for r in records if r['vt_symbol']==symbol],key=lambda r:r['observed_available_min'])
        if any(a['observed_available_max']>=b['observed_available_min'] for a,b in zip(rows,rows[1:])):
            _fail('legacy_epoch_observed_ranges_overlap:'+symbol)
        for row in rows:row['forward_extension_allowed']=row is rows[-1]
    if reader._sha(path)!=trusted_sha256:_fail('approved_seed_changed_during_read')
    return pd.DataFrame(records)

def _epoch(symbol,day,epochs):
    choices=[]
    for row in epochs:
        if row['vt_symbol']!=symbol:continue
        if row.get('seed_kind')=='legacy_approved_observed':
            if (row['observed_available_min']<=day<=row['observed_available_max'] or
                    (row.get('forward_extension_allowed') in (True,'True') and day>row['observed_available_max'])):
                choices.append(row)
        elif ((not row.get('listed_date') or row['listed_date']<=day) and
              (not row.get('delisted_date') or day<=row['delisted_date'])):choices.append(row)
    if len(choices)!=1:_fail('physical_epoch_not_unique:'+symbol+':'+day)
    row=choices[0];code,exchange=symbol.split('.');match=re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})',code)
    month=str(row['contract_yyyymm'])
    if not match or not re.fullmatch(r'[0-9]{4}(0[1-9]|1[0-2])',month):_fail('physical_delivery_month_invalid:'+symbol)
    if month[-(3 if exchange=='CZCE' else 4):]!=match[2] or row['contract_epoch_id']!=exchange+'.'+match[1].upper()+'.'+month:
        _fail('physical_epoch_native_mismatch:'+symbol)
    return row

def _series(symbol,payload,target):
    frame=payload['daily'].copy()
    required={'id','datetime','duration',*VALUES}
    if 'close_oi' not in frame:_fail('daily_close_oi_required:'+symbol)
    if not required<=set(frame):_fail('raw_daily_schema_missing:'+symbol)
    # Placeholder ids/zero times are unavailable slots, never observed bars.
    ids=pd.to_numeric(frame.id,errors='raise');stamps=pd.to_numeric(frame.datetime,errors='raise')
    frame=frame.loc[(ids>=0)&(stamps>0)].copy()
    frame['date']=pd.to_datetime(pd.to_numeric(frame.datetime),unit='ns',utc=True).dt.tz_convert(SHANGHAI).dt.strftime('%Y-%m-%d')
    frame=frame.loc[frame.date<=target].copy()
    if frame.date.duplicated().any():_fail('duplicate_raw_daily:'+symbol)
    if not (pd.to_numeric(frame.duration,errors='raise')==86400).all():_fail('raw_not_daily:'+symbol)
    return frame.sort_values('date')

def _quote_delivery_month(symbol,quote):
    code,exchange=symbol.split('.')
    match=re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})',code)
    year=quote.get('delivery_year');month=quote.get('delivery_month')
    try:
        year_int=int(year);month_int=int(month)
        if year_int!=float(year) or month_int!=float(month) or not 2000<=year_int<=2199 or not 1<=month_int<=12:raise ValueError
    except (ValueError,TypeError,OverflowError):_fail('explicit_delivery_year_month_required:'+symbol)
    delivery=f'{year_int:04d}{month_int:02d}'
    if match is None or delivery[-(3 if exchange=='CZCE' else 4):]!=match[2]:_fail('quote_delivery_native_mismatch:'+symbol)
    return delivery

def _new_epoch(symbol,quote,frame):
    if frame.empty or not (pd.to_numeric(frame.id)==0).any():_fail('new_contract_available_history_start_missing:'+symbol)
    ids=pd.to_numeric(frame.id,errors='raise').tolist()
    if ids!=list(range(len(ids))):_fail('new_contract_available_history_id_gap:'+symbol)
    code,exchange=symbol.split('.');match=re.fullmatch(r'([A-Za-z]+)([0-9]{3,4})',code)
    delivery=_quote_delivery_month(symbol,quote)
    try:
        expiry=float(quote['expire_datetime'])
        if not math.isfinite(expiry) or expiry<=0:raise ValueError
        expiry_day=datetime.fromtimestamp(expiry,SHANGHAI).date().isoformat()
    except (KeyError,TypeError,ValueError,OverflowError):_fail('explicit_contract_expiry_required:'+symbol)
    if expiry_day<frame.date.max():_fail('series_after_expiry:'+symbol)
    # id0 and contiguous completed ids prove the available vendor series;
    # legal listing remains unknown. Do not relabel the first observation.
    listed=''
    if quote.get('listed_date'):
        listed=reader._day(quote['listed_date'])
        if listed>frame.date.min():_fail('available_history_before_explicit_listing:'+symbol)
    return dict(vt_symbol=symbol,contract_epoch_id=exchange+'.'+match[1].upper()+'.'+delivery,
        contract_yyyymm=delivery,listed_date=listed,listed_unknown=not bool(listed),delisted_date=expiry_day,observed_available_min=frame.date.min(),maturity_date=expiry_day,
        exchange=exchange,product=match[1],product_vt_symbol=reader._product(symbol),
        metadata_status='tqsdk_explicit_delivery_fields_and_available_series_id0',
        lifecycle_status='explicit_delivery_expiry_contiguous_available_series_id0_listing_unknown' if not listed else 'explicit_delivery_expiry_listing_contiguous_id0')

def _append_sqlite(base,target,rows):
    shutil.copyfile(base,target)
    with sqlite3.connect(target) as db:
        for row in rows:
            symbol,exchange=row['vt_symbol'].split('.')
            exists=db.execute("select 1 from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(symbol,exchange,row['date'])).fetchone()
            if exists:_fail('new_sqlite_key_already_exists:'+row['vt_symbol']+':'+row['date'])
            db.execute('insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,?,?,?,?,?,?,?,?)',
                (symbol,exchange,row['date']+' 00:00:00','d',row['volume'],row['turnover'],row['close_oi'],row['open'],row['high'],row['low'],row['close']))
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':_fail('new_sqlite_integrity_failed')
        # Keep optional vn.py daily overviews consistent without loading its driver.
        if db.execute("select 1 from sqlite_master where type='table' and name='dbbaroverview'").fetchone():
            for symbol in sorted({r['vt_symbol'] for r in rows}):
                code,exchange=symbol.split('.')
                count,start,end=db.execute("select count(*),min(datetime),max(datetime) from dbbardata where symbol=? and exchange=? and interval='d'",(code,exchange)).fetchone()
                existing=db.execute("select 1 from dbbaroverview where symbol=? and exchange=? and interval='d'",(code,exchange)).fetchone()
                if existing:db.execute("update dbbaroverview set count=?,start=?,end=? where symbol=? and exchange=? and interval='d'",(count,start,end,code,exchange))
                else:db.execute('insert into dbbaroverview(symbol,exchange,interval,count,start,end) values(?,?,?,?,?,?)',(code,exchange,'d',count,start,end))
        db.execute('attach database ? as frozen',(str(base),))
        columns=[r[1] for r in db.execute('pragma frozen.table_info(dbbardata)')]
        projection=','.join('"'+c.replace('"','""')+'"' for c in columns)
        if db.execute(f'select count(*) from (select {projection} from frozen.dbbardata except select {projection} from main.dbbardata)').fetchone()[0]:
            _fail('frozen_sqlite_rows_changed')
        if db.execute('select count(*) from main.dbbardata').fetchone()[0]!=db.execute('select count(*) from frozen.dbbardata').fetchone()[0]+len(rows):
            _fail('sqlite_append_count_not_conserved')

def update_weekly19_assets(base_asset_root,generation_root,*,material_release_id,target_date,held_contracts,
                            expected_hashes,backend,now=None):
    """Append completed real daily observations to a NEW private generation.

    Caller supplies the actual-held contract set; an empty set is an explicit
    flat declaration, not a broker query. New contract history is source-bound
    but needs runtime admission before it can alter a durable actor's input set.
    No receipt here confers production qualification or sends a financial order.
    """
    target=reader._day(target_date);now=now or datetime.now(SHANGHAI)
    if now.tzinfo is None or date.fromisoformat(target)>now.astimezone(SHANGHAI).date() or (target==now.astimezone(SHANGHAI).date().isoformat() and now.astimezone(SHANGHAI).hour<15):
        _fail('target_trading_day_not_completed')
    base=Path(base_asset_root).expanduser().resolve(strict=True);requested_destination=Path(generation_root).expanduser().absolute()
    if requested_destination.is_symlink():_fail('generation_root_symlink_forbidden')
    destination=requested_destination.resolve(strict=False)
    if destination==base or base in destination.parents or destination in base.parents:_fail('generation_destination_must_be_separate')
    if not isinstance(material_release_id,str) or not material_release_id.strip():_fail('material_release_id_required')
    before=reader._hashes(base,expected_hashes)
    registry_path=base/'physical_epochs.csv';registry_sha=expected_hashes.get('physical_epochs.csv')
    if registry_sha is not None:
        if not registry_path.is_file() or not isinstance(registry_sha,str) or not reader.SHA.fullmatch(registry_sha) or reader._sha(registry_path)!=registry_sha:
            _fail('physical_epoch_registry_hash_required')
        seed=None
    else:
        seed=build_legacy_epoch_seed_from_approved(base/'physical_epoch_daily.csv',trusted_sha256=before['physical_epoch_daily.csv'])
    source=json.loads((base/'receipt.json').read_text());end=reader._day(source['date_end'])
    if source.get('data_ready') is not True or source.get('units')!='single_sided_volume_close_oi' or target<=end:_fail('valid_prior_source_and_new_target_required')
    products=reader._fixed_products()
    if set(source.get('products',[]))!=set(products):_fail('base_fixed19_receipt_required')
    if not isinstance(held_contracts,(list,tuple,set)) or any(reader._product(s) not in products for s in held_contracts):_fail('explicit_fixed19_held_contracts_required')
    held=sorted(set(held_contracts))
    destination=_private_root(destination)
    lock_fd=os.open(destination/'.update.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:_fail('asset_update_already_running')
        generation='weekly19-'+target+'-'+now.astimezone(SHANGHAI).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex
        final=destination/generation;stage=destination/('.'+generation+'.pending');stage.mkdir(mode=0o700)
        try:
            mapping_old=pd.read_csv(base/'mapping.csv',dtype=str).fillna('')
            if not set(mapping_old.continuous_symbol_vt)<=set(products):_fail('base_mapping_not_fixed19')
            physical=pd.read_csv(base/'physical_epoch_daily.csv',dtype={'vt_symbol':str,'date':str,'contract_epoch_id':str})
            if not set(physical.vt_symbol.map(reader._product))<=set(products):_fail('base_physical_not_fixed19')
            epochs=(pd.read_csv(registry_path,dtype=str).fillna('') if seed is None else seed).to_dict('records')
            fetched=backend.fetch_mapping(products,end,target)
            if not {'date','continuous_symbol_vt','main_contract_vt'}<=set(fetched):_fail('fetched_mapping_schema_missing')
            if not set(fetched.continuous_symbol_vt)<=set(products):_fail('fetched_mapping_outside_fixed19')
            forward=dict(fetched.attrs.get('forward_calendar',{}));dates=forward.get('trading_dates',[])
            calendar=[reader._day(d) for d in dates]
            if len(set(calendar))!=len(calendar) or target not in calendar or not any(date.fromisoformat(d).isocalendar()[:2]>date.fromisoformat(target).isocalendar()[:2] for d in calendar):_fail('real_forward_calendar_next_week_required')
            calendar=sorted(set(calendar));append_days=[d for d in calendar if end<d<=target]
            extension=fetched.loc[(fetched.date>end)&(fetched.date<=target)].copy()
            if set(extension.date)!=set(append_days):_fail('fetched_mapping_day_calendar_mismatch')
            if extension.duplicated(['date','continuous_symbol_vt']).any():_fail('fetched_mapping_duplicate')
            for day in append_days:
                current=extension.loc[extension.date==day]
                if set(current.continuous_symbol_vt)!=set(products) or current.main_contract_vt.eq('').any():_fail('completed_mapping_19_missing:'+day)
                if any(reader._product(s)!=p for p,s in zip(current.continuous_symbol_vt,current.main_contract_vt)):_fail('mapping_product_mismatch')
            if not append_days:_fail('no_new_completed_trading_days')
            # Keep every known current physical AM updated, plus all actual held
            # and mapped contracts; expired instruments are excluded by registry.
            recent=set(physical.loc[physical.date==end,'vt_symbol'])
            active={s for s in recent if any(r['vt_symbol']==s and (not r.get('delisted_date') or r['delisted_date']>=target) for r in epochs)}
            wanted=sorted(active|set(extension.main_contract_vt)|set(held))
            known=set(physical.vt_symbol);new=sorted(set(wanted)-known)
            payloads=backend.fetch_contracts(wanted,new_symbols=new,target_date=target)
            if set(payloads)!=set(wanted):_fail('requested_contract_fetch_incomplete')
            raw_dir=stage/'raw_daily';raw_dir.mkdir(mode=0o700)
            accepted=[];rejected=[];overlap=[];new_admissions=[];metadata_rows=[];turnover_unknown=[];expired_offmain=[]
            existing={(str(r.vt_symbol),str(r.date)):r for r in physical.itertuples()}
            for symbol in wanted:
                payload=payloads[symbol];quote=dict(payload['quote']);raw_path=raw_dir/(symbol+'.csv')
                code,exchange=symbol.split('.')
                if quote.get('instrument_id')!=exchange+'.'+code or quote.get('ins_class')!='FUTURE':_fail('quote_native_instrument_identity_mismatch:'+symbol)
                payload['daily'].to_csv(raw_path,index=False);raw_sha=reader._sha(raw_path)
                quote_path=raw_dir/(symbol+'.quote.json');_atomic_json(quote_path,quote)
                try:
                    expiry=float(quote['expire_datetime'])
                    if not math.isfinite(expiry) or expiry<=0:raise ValueError
                    expiry_day=datetime.fromtimestamp(expiry,SHANGHAI).date().isoformat()
                except (KeyError,TypeError,ValueError,OverflowError):_fail('explicit_contract_expiry_required:'+symbol)
                if expiry_day<target and symbol not in held and symbol not in set(extension.main_contract_vt):
                    expired_offmain.append(dict(vt_symbol=symbol,expire_date=expiry_day,metadata_sha256=reader._sha(quote_path)))
                quote_delivery=_quote_delivery_month(symbol,quote)
                frame=_series(symbol,payload,target)
                if not frame.empty and frame.date.max()>expiry_day:_fail('daily_observation_after_actual_expiry:'+symbol)
                legacy=[ep for ep in epochs if ep['vt_symbol']==symbol and ep.get('seed_kind')=='legacy_approved_observed' and ep.get('forward_extension_allowed') in (True,'True')]
                if legacy:
                    if len(legacy)!=1 or quote_delivery!=legacy[0]['contract_yyyymm']:_fail('legacy_symbol_new_physical_epoch_requires_admission:'+symbol)
                if symbol in new:
                    epoch=_new_epoch(symbol,quote,frame);epochs.append(epoch)
                    new_admissions.append(dict(schema='weekly19.new-contract-history-admission.v1',vt_symbol=symbol,
                        contract_epoch_id=epoch['contract_epoch_id'],contract_yyyymm=epoch['contract_yyyymm'],
                        listed_date=epoch['listed_date'],listed_unknown=epoch['listed_unknown'],observed_available_min=epoch['observed_available_min'],
                        delisted_date=epoch['delisted_date'],available_history_complete=True,available_history_ids_contiguous=True,
                        available_series_id0=True,source_sha256=raw_sha,metadata_sha256=reader._sha(quote_path),
                        first_available_day=epoch['observed_available_min'],legal_listing_history_complete=False,
                        runtime_input_admission_required=True))
                    metadata_rows.append(dict(vt_symbol=symbol,source_symbol_vt=reader._product(symbol),symbol_kind='contract',
                        tq_symbol=quote.get('instrument_id'),instrument_id=quote.get('instrument_id'),price_tick=quote.get('price_tick'),
                        volume_multiple=quote.get('volume_multiple'),fetched_at=now.isoformat()))
                for index,row in frame.iterrows():
                    day=row['date'];key=(symbol,day)
                    try:
                        values={k:float(row[k]) for k in VALUES}
                        valid=all(math.isfinite(v) for v in values.values()) and min(values[k] for k in VALUES if k!='close_oi')>0 and values['close_oi']>=0 and values['low']<=min(values['open'],values['close']) and values['high']>=max(values['open'],values['close'])
                    except (TypeError,ValueError):valid=False
                    if key in existing:
                        if not valid or any(not math.isclose(values[k],float(getattr(existing[key],k)),rel_tol=0,abs_tol=1e-9) for k in VALUES):overlap.append(dict(vt_symbol=symbol,date=day,classification='observed_overlap_not_overwritten'))
                        continue
                    if symbol not in new and day<=end:continue
                    if not valid:
                        rejected.append(dict(vt_symbol=symbol,date=day,classification='raw_zero_or_invalid_not_bar'));continue
                    ep=_epoch(symbol,day,epochs)
                    if quote_delivery!=str(ep['contract_yyyymm']):_fail('known_contract_quote_epoch_mismatch:'+symbol)
                    try:turnover=float(row['turnover'])
                    except (KeyError,TypeError,ValueError):
                        turnover=0.0
                        turnover_unknown.append(dict(vt_symbol=symbol,date=day,classification='not_observed_transport_sentinel_zero',source_sha256=raw_sha))
                    if not math.isfinite(turnover) or turnover<0:_fail('daily_turnover_invalid:'+symbol)
                    accepted.append(dict(vt_symbol=symbol,date=day,contract_epoch_id=ep['contract_epoch_id'],contract_yyyymm=ep['contract_yyyymm'],**values,turnover=turnover,
                        source_id='explicit_fetch_backend_raw_daily',source_path=str(final/'raw_daily'/raw_path.name),source_sha256=raw_sha,
                        source_locator=json.dumps(dict(row=int(index),id=int(row['id'])),sort_keys=True),lifecycle_status=ep.get('lifecycle_status',''),
                        admission_reason='new_contract_available_history' if symbol in new else 'completed_daily_extension'))
            keys=set(existing)|{(r['vt_symbol'],r['date']) for r in accepted}
            for day in append_days:
                for symbol in set(extension.loc[extension.date==day,'main_contract_vt'])|set(held):
                    if (symbol,day) not in keys:_fail('required_completed_daily_missing:'+symbol+':'+day)
            # Never silently leave a tracked live physical AM behind.
            for symbol in active-{row['vt_symbol'] for row in expired_offmain}:
                if (symbol,target) not in keys:_fail('tracked_current_contract_daily_missing:'+symbol)
            merged_mapping=pd.concat([mapping_old,extension],ignore_index=True,sort=False)
            merged_mapping.to_csv(stage/'mapping.csv',index=False)
            new_physical=pd.DataFrame(accepted).drop(columns=['turnover'],errors='ignore')
            pd.concat([physical,new_physical],ignore_index=True,sort=False).to_csv(stage/'physical_epoch_daily.csv',index=False)
            pd.DataFrame(epochs).to_csv(stage/'physical_epochs.csv',index=False)
            meta=pd.read_csv(base/'metadata.csv')
            pd.concat([meta,pd.DataFrame(metadata_rows)],ignore_index=True,sort=False).to_csv(stage/'metadata.csv',index=False)
            _append_sqlite(base/'daily.sqlite',stage/'daily.sqlite',accepted)
            pd.DataFrame({'date':calendar}).to_csv(stage/'forward_calendar.csv',index=False)
            receipt=dict(schema='weekly19.private-daily-generation.v1',date_start=source.get('date_start'),date_end=target,
                units='single_sided_volume_close_oi',products=products,data_ready=True,completed_at=now.isoformat(),
                material_release_id=material_release_id,base_source_hashes=before,base_registry_sha256=registry_sha,
                requested_contracts=wanted,declared_actual_held_contracts=held,new_contract_history_admissions=new_admissions,
                appended_positive_rows=len(accepted),observed_overlap_not_overwritten=overlap,rejected_raw_observations=rejected,
                forward_calendar=forward,expired_unheld_offmain_contracts=expired_offmain,turnover_unknown=turnover_unknown,turnover_unknown_not_observed=bool(turnover_unknown),
                turnover_dependent_strategies_qualified=False,historical_main_reconstruction_complete=source.get('historical_main_reconstruction_complete',False),
                readiness_limitations=list(source.get('readiness_limitations',[]))+['Conditional market snapshot; live provider and runtime input admission are separate gates.'],
                conditional_read=True,production_qualified=False,market_order_calls=0,source_updater_sha256=reader._sha(__file__))
            _atomic_json(stage/'receipt.json',receipt)
            hashes={name:reader._sha(stage/name) for name in (*reader.FILES,'physical_epochs.csv','forward_calendar.csv')}
            # Completion check uses the same strict production-facing DTO reader.
            # Its clock is actual wall time; future fixture tests patch explicitly.
            checked=reader.load_weekly19_inputs(stage,material_release_id=material_release_id,target_date=target,
                forward_calendar=stage/'forward_calendar.csv',expected_hashes=hashes)
            if reader._hashes(base,expected_hashes)!=before or (registry_sha is not None and reader._sha(registry_path)!=registry_sha):_fail('base_source_changed_during_update')
            _atomic_json(stage/'generation_manifest.json',dict(schema='weekly19.private-generation-manifest.v1',files=hashes,
                source_receipt_sha256=hashes['receipt.json'],reader_parity=checked['receipt']['sqlite_physical_parity'],production_qualified=False))
            for path in stage.rglob('*'):
                if path.is_file():
                    fd=os.open(path,os.O_RDONLY)
                    try:os.fsync(fd)
                    finally:os.close(fd)
                    os.chmod(path,0o400)
            for folder in (raw_dir,stage):
                fd=os.open(folder,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
            os.replace(stage,final)
            result=dict(schema='weekly19.private-latest.v1',asset_root=str(final),target_date=target,source_hashes=hashes,
                source_manifest_sha256=reader._sha(final/'generation_manifest.json'),conditional_read=True,
                production_qualified=False,new_contract_history_admissions=new_admissions,market_order_calls=0)
            _atomic_json(destination/'latest.json',result)
            directory_fd=os.open(destination,os.O_RDONLY)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
            return result
        except BaseException:
            # A failed immutable attempt never advances latest. Retain private raw
            # observations for diagnosis without serializing arbitrary exceptions.
            if stage.exists():os.replace(stage,destination/('.failed-'+generation))
            raise
    finally:
        fcntl.flock(lock_fd,fcntl.LOCK_UN);os.close(lock_fd)

class TqReadOnlyBackend:
    """No strategy or broker. Credentials stay in local vn.py SETTINGS only."""
    def __init__(self,*,timeout_seconds=180):self.timeout_seconds=timeout_seconds
    def fetch_mapping(self,products,start,target):
        from build_qmt_roll_stage173_forward_main_contract_data_update import _fetch_mapping_rows
        return _fetch_mapping_rows(products,date.fromisoformat(start),date.fromisoformat(target))
    def fetch_contracts(self,symbols,*,new_symbols,target_date):
        from tqsdk import TqApi,TqAuth,TqSim
        from vnpy.trader.setting import SETTINGS
        username=str(SETTINGS.get('datafeed.username') or '');password=str(SETTINGS.get('datafeed.password') or '')
        if not username or not password:_fail('local_tqsdk_credentials_missing')
        api=TqApi(TqSim(),auth=TqAuth(username,password),disable_print=True,debug=False)
        def forbidden(*a,**kw):_fail('market_data_backend_order_api_forbidden')
        api.insert_order=forbidden;api.cancel_order=forbidden
        try:
            quotes={};serials={}
            for symbol in symbols:
                code,exchange=symbol.split('.');native=exchange+'.'+code
                quotes[symbol]=api.get_quote(native)
                serials[symbol]=api.get_kline_serial(native,86400,data_length=10000)
            deadline=time.monotonic()+self.timeout_seconds
            while not all(api.is_serial_ready(s) for s in serials.values()) or not all(q.get('instrument_id') for q in quotes.values()):
                if time.monotonic()>deadline:_fail('tqsdk_real_serial_timeout')
                api.wait_update(deadline=time.time()+1)
            fields=('instrument_id','ins_class','delivery_year','delivery_month','expire_datetime','price_tick','volume_multiple')
            result={}
            for symbol in symbols:
                daily=serials[symbol].copy()
                # This duration is the bound get_kline_serial request, not a
                # fabricated observation; raw close_oi remains mandatory.
                daily['duration']=86400
                result[symbol]=dict(quote={k:quotes[symbol].get(k) for k in fields},daily=daily)
            return result
        finally:api.close()

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-asset-root',required=True);parser.add_argument('--generation-root',required=True)
    parser.add_argument('--material-release-id',required=True);parser.add_argument('--target-date',required=True)
    parser.add_argument('--expected-hashes-json',required=True);parser.add_argument('--held-contracts-json',required=True)
    parser.add_argument('--execute',action='store_true',help='Perform explicitly requested read-only market fetch; default only prints plan')
    args=parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dict(status='plan_only_no_market_request',fixed_product_count=19,
            target_date=args.target_date,base_asset_root=str(Path(args.base_asset_root).expanduser().absolute()),
            generation_root=str(Path(args.generation_root).expanduser().absolute()),production_qualified=False),sort_keys=True));return 0
    result=update_weekly19_assets(args.base_asset_root,args.generation_root,material_release_id=args.material_release_id,
        target_date=args.target_date,held_contracts=json.loads(Path(args.held_contracts_json).read_text()),
        expected_hashes=json.loads(Path(args.expected_hashes_json).read_text()),backend=TqReadOnlyBackend())
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
