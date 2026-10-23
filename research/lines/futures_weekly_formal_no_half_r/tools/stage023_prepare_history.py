"""Data-only immutable historical assembly; no strategy, market API, or financial replay."""
from pathlib import Path
import argparse, csv, hashlib, json, math, re, shutil, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

START='2014-01-01'; END='2026-10-23'
VALUE_FIELDS=['open','high','low','close','volume','close_oi']
BAR_FIELDS=['vt_symbol','date','contract_epoch_id','contract_yyyymm',*VALUE_FIELDS,'source_id','source_path','source_sha256','source_locator','lifecycle_status','admission_reason']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def _pin(path, files, expected=None):
    path=Path(path).resolve(); digest=sha(path)
    if expected is not None and digest!=expected:raise ValueError('source_sha_mismatch:'+str(path))
    if str(path) in files and files[str(path)]!=digest:raise ValueError('source_changed:'+str(path))
    files[str(path)]=digest;return digest

def _json(path, obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')

def _day(value):return str(value)[:10]

def _optional(value):
    return None if value is None or pd.isna(value) or str(value).strip()=='' else _day(value)

def epoch_index(contracts, products):
    canonical={p.upper():p for p in products}; by_id={}; by_native={}
    for source in contracts.to_dict('records'):
        key=(str(source['product'])+'.'+str(source['exchange'])).upper()
        if key not in canonical:continue
        row=dict(source); yyyymm=str(row['contract_yyyymm'])
        if not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])',yyyymm):raise ValueError('invalid_epoch_month:'+yyyymm)
        prod,exchange=canonical[key].split('.'); native=prod+yyyymm[-3 if exchange=='CZCE' else -4:]+'.'+exchange
        expected=exchange+'.'+prod.upper()+'.'+yyyymm
        if str(row['contract_epoch_id'])!=expected:raise ValueError('epoch_metadata_identity_mismatch')
        row.update(vt_symbol=native,product_vt_symbol=canonical[key],contract_yyyymm=yyyymm,
                   listed_date=_optional(row.get('listed_date')),delisted_date=_optional(row.get('delisted_date')))
        row['lifecycle_status']='known_vendor_listing_delisting' if row['listed_date'] and row['delisted_date'] else 'observed_bar_identity_known_full_lifecycle_unknown'
        if expected in by_id and row!=by_id[expected]:raise ValueError('duplicate_epoch_metadata')
        by_id[expected]=row;by_native.setdefault(native,[]).append(row)
    return {'by_id':by_id,'by_native':by_native}

def bind_epoch(vt_symbol, day, index, explicit=None):
    day=_day(day)
    def allowed(row):return (not row['listed_date'] or row['listed_date']<=day) and (not row['delisted_date'] or day<=row['delisted_date'])
    if explicit:
        row=index['by_id'].get(str(explicit))
        if row is None or row['vt_symbol']!=vt_symbol or not allowed(row):raise ValueError('epoch_out_of_lifecycle_or_identity:'+vt_symbol+':'+day)
        return row
    candidates=[row for row in index['by_native'].get(vt_symbol,[]) if allowed(row)]
    if len(candidates)!=1:raise ValueError(('ambiguous_epoch:' if len(candidates)>1 else 'epoch_not_found:')+vt_symbol+':'+day)
    return candidates[0]

def _valid(row):
    try:values=[float(row[k]) for k in VALUE_FIELDS]
    except (KeyError,TypeError,ValueError):raise ValueError('invalid_daily_fields')
    o,h,l,c,v,oi=values
    if not all(math.isfinite(x) for x in values) or min(o,h,l,c,v)<=0 or oi<0 or l>min(o,c) or h<max(o,c) or l>h:
        raise ValueError('invalid_daily:'+str(row.get('vt_symbol'))+':'+str(row.get('date')))
    return dict(zip(VALUE_FIELDS,values))

def clean_bars(frame,index,products,start=START,end=END):
    canonical={p.upper():p for p in products}; records=[];excluded=[]
    for row in frame.to_dict('records'):
        if row.get('quality_status')!='accepted':continue
        day=_day(row['trade_date']);key=(str(row['product'])+'.'+str(row['exchange'])).upper()
        if key not in canonical or not start<=day<=end:continue
        epoch=index['by_id'].get(str(row['contract_epoch_id']))
        if epoch is None:raise ValueError('epoch_metadata_absent:'+str(row['contract_epoch_id']))
        try:epoch=bind_epoch(epoch['vt_symbol'],day,index,explicit=epoch['contract_epoch_id'])
        except ValueError as exc:
            excluded.append(dict(vt_symbol=epoch['vt_symbol'],date=day,contract_epoch_id=epoch['contract_epoch_id'],reason=str(exc)));continue
        out={k:row[k] for k in VALUE_FIELDS};out.update(vt_symbol=epoch['vt_symbol'],date=day,contract_epoch_id=epoch['contract_epoch_id'],contract_yyyymm=epoch['contract_yyyymm'],lifecycle_status=epoch['lifecycle_status'],source_id=str(row.get('source_id','')),source_path=str(row.get('source_path','')),source_sha256=str(row.get('source_sha256','')),source_locator=str(row.get('source_locator','')),admission_reason='accepted_clean_primary')
        out.update(_valid(out));records.append(out)
    return pd.DataFrame(records,columns=BAR_FIELDS),pd.DataFrame(excluded,columns=['vt_symbol','date','contract_epoch_id','reason'])

def merge_bars(layers):
    rows={};duplicates=0
    for layer in layers:
        for row in layer.to_dict('records'):
            row.update(_valid(row));key=(row['vt_symbol'],row['date'])
            if key in rows:
                previous=rows[key]
                if previous['contract_epoch_id']!=row['contract_epoch_id'] or any(abs(float(previous[f])-float(row[f]))>1e-8 for f in VALUE_FIELDS):raise ValueError('daily_source_conflict:'+str(key))
                duplicates+=1
            else:rows[key]=row
    return pd.DataFrame(list(rows.values()),columns=BAR_FIELDS).sort_values(['date','vt_symbol']).reset_index(drop=True),duplicates

def merge_mapping(old,new):
    columns=list(old.columns)
    if any(k not in columns for k in ['date','continuous_symbol_vt','main_contract_vt']):raise ValueError('mapping_fields_missing')
    if set(new.columns)!=set(columns):raise ValueError('mapping_schema_changed')
    rows={}
    for source in [old.fillna(''),new.fillna('')]:
        for row in source[columns].to_dict('records'):
            key=(str(row['date']),str(row['continuous_symbol_vt']))
            if key in rows and rows[key]!=row:raise ValueError('mapping_conflict:'+str(key))
            rows[key]=row
    return pd.DataFrame(rows.values(),columns=columns).sort_values(['date','continuous_symbol_vt']).reset_index(drop=True)

def missing_main(mapping,bars,products,start,end):
    wanted=mapping.fillna('');wanted=wanted[wanted.continuous_symbol_vt.isin(products)&wanted.date.between(start,end)&wanted.main_contract_vt.ne('')].copy();keys=set(zip(bars.vt_symbol,bars.date))
    missing=wanted[[(r.main_contract_vt,r.date) not in keys for r in wanted.itertuples()]].copy();missing['reason']='no_positive_accepted_physical_daily';return missing

def native_epoch_gaps(bars):
    windows=bars.groupby(['vt_symbol','contract_epoch_id'],sort=True).date.agg(['min','max']).reset_index();rows=[]
    for symbol,group in windows.groupby('vt_symbol'):
        group=group.sort_values('min');previous=None
        for row in group.to_dict('records'):
            if previous is not None:
                gap=(pd.Timestamp(row['min'])-pd.Timestamp(previous['max'])).days
                if gap<=366:raise ValueError('native_epoch_overlap_or_gap_not_over366:'+symbol)
                rows.append(dict(vt_symbol=symbol,previous_epoch=previous['contract_epoch_id'],next_epoch=row['contract_epoch_id'],previous_last_observed=previous['max'],next_first_observed=row['min'],observed_gap_days=gap,bounds_are_expiry=False))
            previous=row
    return pd.DataFrame(rows,columns=['vt_symbol','previous_epoch','next_epoch','previous_last_observed','next_first_observed','observed_gap_days','bounds_are_expiry'])

def _raw_day(frame):
    if 'date' in frame: return frame['date'].astype(str).str[:10]
    return pd.to_datetime(pd.to_numeric(frame.datetime),unit='ns',utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d')

def _raw_check(row,raw):
    days=_raw_day(raw);q=raw.loc[days.eq(row['date'])]
    if len(q)!=1 or 'close_oi' not in q:raise ValueError('raw_mismatch_missing_date_or_close_oi')
    rr=q.iloc[0]
    if 'duration' not in q or float(rr.duration)!=86400:raise ValueError('raw_not_daily')
    if not all(math.isfinite(float(rr[f])) for f in VALUE_FIELDS):raise ValueError('raw_nonfinite_daily')
    if any(abs(float(rr[f])-float(row[f]))>1e-8 for f in VALUE_FIELDS):raise ValueError('raw_mismatch:'+row['vt_symbol']+':'+row['date'])
    # Native provider symbols may use CZCE three or four digit spellings; month/identity is resolved from metadata separately.
    provider=str(rr.get('symbol',''));code,exchange=row['vt_symbol'].split('.')
    if provider:
        if not provider.startswith(exchange+'.'):raise ValueError('raw_symbol_exchange_mismatch')
        rawcode=provider.split('.')[-1];match=re.fullmatch(r'([A-Za-z]+)(\d{3,4})',rawcode)
        if match is not None and exchange=='CZCE' and len(match[2])==4 and match[2]!=str(row['contract_yyyymm'])[-4:]:raise ValueError('raw_symbol_identity_mismatch')
        if match is None or match[1].lower()!=re.sub(r'\d+$','',code).lower() or match[2][-3 if exchange=='CZCE' else -4:]!=re.search(r'\d+$',code)[0]:raise ValueError('raw_symbol_identity_mismatch')

def probe_bars(directory,index,products,files):
    directory=Path(directory).resolve();receiptpath=directory/'probe_receipt.json';_pin(receiptpath,files);receipt=json.loads(receiptpath.read_text())
    if receipt.get('status') not in ['latest_daily_ready','offmain_daily_ready'] or receipt.get('raw_daily_interval_seconds')!=86400 or receipt.get('original_inputs_unchanged') is not True:raise ValueError('probe_not_accepted')
    for name,digest in receipt['output_files_sha256'].items():_pin(directory/name,files,digest)
    statuses={r['vt_symbol']:r for r in receipt['contract_statuses']};raws={}
    for symbol,status in statuses.items():
        if status['status']!='fetched':raise ValueError('probe_contract_not_fetched:'+symbol)
        _pin(status['raw_path'],files,status['raw_sha256']);raws[symbol]=pd.read_csv(status['raw_path'])
    selected=pd.read_csv(directory/'daily_probe.csv');records=[]
    for row in selected.to_dict('records'):
        symbol=str(row['vt_symbol']);day=_day(row['date'])
        if re.sub(r'\d+(?=\.)','',symbol) not in products:raise ValueError('probe_product_outside_fixed_pool')
        if not START<=day<=END:raise ValueError('future_or_prestart_daily_selected')
        epoch=bind_epoch(symbol,day,index);out={f:row[f] for f in VALUE_FIELDS};out.update(vt_symbol=symbol,date=day,contract_epoch_id=epoch['contract_epoch_id'],contract_yyyymm=epoch['contract_yyyymm'],lifecycle_status=epoch['lifecycle_status']);out.update(_valid(out));_raw_check(out,raws[symbol]);status=statuses[symbol]
        if _day(status['snapshot_at'])<day:raise ValueError('daily_snapshot_before_bar_day')
        out.update(source_id='TqSdk_daily_close_oi',source_path=status['raw_path'],source_sha256=status['raw_sha256'],source_locator=json.dumps({'date':day,'id':row.get('id')}),admission_reason='predeclared_latest_daily_probe');records.append(out)
    return pd.DataFrame(records,columns=BAR_FIELDS)

def approved_supplement(path,policy_path,index,products,files):
    if not policy_path:raise ValueError('approval_policy_required')
    policy=json.loads(Path(policy_path).read_text())
    if policy.get('approved') is not True or not policy.get('policy_id') or policy.get('units')!='single_sided_volume_close_oi':raise ValueError('approval_policy_invalid')
    _pin(policy_path,files);_pin(path,files,policy['supplement_sha256'])
    for name,digest in policy.get('files',{}).items():_pin(name,files,digest)
    field_map=policy.get('field_map',{})
    if set(field_map)!=set(VALUE_FIELDS) or field_map.get('volume') not in ('volume','tq_volume') or field_map.get('close_oi') not in ('close_oi','tq_close_oi'):raise ValueError('approval_field_map_invalid')
    source=pd.read_csv(path);records=[];raws={}
    for row in source.to_dict('records'):
        if not row.get('contract_epoch_id') or not row.get('source_path') or not row.get('source_sha256') or not str(row.get('admission_reason','')).strip():raise ValueError('approval_row_provenance_missing')
        symbol=str(row['vt_symbol']);day=_day(row['date'])
        if re.sub(r'\d+(?=\.)','',symbol) not in products or not START<=day<=END:raise ValueError('approval_row_scope_invalid')
        epoch=bind_epoch(symbol,day,index,explicit=str(row['contract_epoch_id']));out={f:row[field_map[f]] for f in VALUE_FIELDS};out.update(vt_symbol=symbol,date=day,contract_epoch_id=epoch['contract_epoch_id'],contract_yyyymm=epoch['contract_yyyymm'],lifecycle_status=epoch['lifecycle_status']);out.update(_valid(out));_pin(row['source_path'],files,row['source_sha256'])
        if row['source_path'] not in raws:raws[row['source_path']]=pd.read_csv(row['source_path'])
        _raw_check(out,raws[row['source_path']]);out.update(source_id=policy['policy_id'],source_path=row['source_path'],source_sha256=row['source_sha256'],source_locator=str(row.get('source_locator',day)),admission_reason=str(row['admission_reason']));records.append(out)
    return pd.DataFrame(records,columns=BAR_FIELDS)

def approved_no_trade(path,policy_path,index,products,files,missing):
    """Classify proved zero-volume missing main keys; never return a tradable bar."""
    if not policy_path:raise ValueError('no_trade_policy_required')
    policy=json.loads(Path(policy_path).read_text())
    if policy.get('approved') is not True or policy.get('purpose')!='classification_only_no_OHLC_OI_consumption' or not policy.get('policy_id'):raise ValueError('no_trade_policy_invalid')
    _pin(policy_path,files);_pin(path,files,policy['known_no_trade_sha256'])
    for name,digest in policy.get('files',{}).items():_pin(name,files,digest)
    volume_field=policy.get('volume_field')
    if not volume_field:raise ValueError('no_trade_volume_field_required')
    source=pd.read_csv(path);required=['vt_symbol','date','contract_epoch_id','source_contract_epoch_id','physical_identity_status','source_path','source_sha256','source_locator','admission_reason',volume_field]
    if any(field not in source for field in required):raise ValueError('no_trade_fields_missing')
    source['date']=source.date.astype(str).str[:10];keys=list(zip(source.vt_symbol,source.date));wanted=set(zip(missing.main_contract_vt,missing.date))
    if len(keys)!=len(set(keys)):raise ValueError('no_trade_duplicate_key')
    if not set(keys).issubset(wanted):raise ValueError('no_trade_missing_key_set')
    exceptions=policy.get('legacy_identity_exclusions',[]);exception_keys={};raws={};records=[]
    for ex in exceptions:
        key=(str(ex['vt_symbol']),_day(ex['date']))
        if key in exception_keys:raise ValueError('no_trade_duplicate_legacy_exception')
        exception_keys[key]=ex
    used_exceptions=set()
    for row in source.to_dict('records'):
        symbol=str(row['vt_symbol']);day=row['date'];key=(symbol,day)
        if re.sub(r'\d+(?=\.)','',symbol) not in products or not '2015-01-01'<=day<=END:raise ValueError('no_trade_scope_invalid')
        try:volume=float(row[volume_field])
        except (ValueError,TypeError):raise ValueError('no_trade_not_zero')
        if not math.isfinite(volume) or volume!=0:raise ValueError('no_trade_not_zero')
        if any(pd.isna(row[f]) or not str(row[f]).strip() for f in required):raise ValueError('no_trade_row_provenance_missing')
        if key in exception_keys:
            ex=exception_keys[key]
            if symbol!='fu1905.SHFE' or day>='2018-07-16' or row['contract_epoch_id']!='NONTRADABLE_LEGACY_FU180.201905' or row['physical_identity_status'] not in ('legacy_FU180_pre_relisting_not_new380','legacy_FU180_or_termination_buffer_not_new380_classification_only'):raise ValueError('no_trade_legacy_exception_invalid')
            for field in ['contract_epoch_id','source_contract_epoch_id']:
                if str(ex.get(field,''))!=str(row[field]):raise ValueError('no_trade_legacy_exception_mismatch')
            used_exceptions.add(key)
        else:
            bind_epoch(symbol,day,index,explicit=str(row['contract_epoch_id']))
            if str(row['source_contract_epoch_id'])!=str(row['contract_epoch_id']) or row['physical_identity_status'] not in ('known_vendor_inclusive_lifecycle','clean_metadata_inclusive_zero_observation_classification_only'):raise ValueError('no_trade_normal_identity_mismatch')
        _pin(row['source_path'],files,row['source_sha256'])
        if row['source_path'] not in raws:raws[row['source_path']]=pd.read_csv(row['source_path'])
        raw=raws[row['source_path']];epoch_field='source_contract_epoch_id' if 'source_contract_epoch_id' in raw else 'contract_epoch_id'
        if any(field not in raw for field in ['date','vt_symbol',epoch_field,'volume']):raise ValueError('no_trade_raw_fields_missing')
        q=raw.loc[raw.date.astype(str).str[:10].eq(day)&raw.vt_symbol.astype(str).eq(symbol)&raw[epoch_field].astype(str).eq(str(row['source_contract_epoch_id']))]
        if len(q)!=1:raise ValueError('no_trade_raw_identity_join_failed')
        try:raw_volume=float(q.iloc[0].volume)
        except (ValueError,TypeError):raise ValueError('no_trade_raw_not_zero')
        if not math.isfinite(raw_volume) or raw_volume!=0:raise ValueError('no_trade_raw_not_zero')
        # Deliberately copy no price/open-interest fields: classification has no OHLC/OI semantics.
        out={field:row[field] for field in required if field!=volume_field};out.update(zero_volume=0.,classification='known_no_trade_main_not_bar',policy_id=policy['policy_id']);records.append(out)
    if used_exceptions!=set(exception_keys):raise ValueError('no_trade_unused_legacy_exception')
    return pd.DataFrame(records),missing.loc[[(r.main_contract_vt,r.date) not in set(keys) for r in missing.itertuples()]].copy()

def approved_structural_unavailable(path,policy_path,index,products,files,missing):
    """Classify only the pre-approved18 invalid frozen mapping keys, with no quote inference."""
    if not policy_path:raise ValueError('structural_policy_required')
    policy=json.loads(Path(policy_path).read_text())
    if policy.get('approved') is not True or policy.get('purpose')!='classification_only_invalid_frozen_mapping' or not policy.get('policy_id'):raise ValueError('structural_policy_invalid')
    _pin(policy_path,files);_pin(path,files,policy['structural_unavailable_sha256'])
    for name,digest in policy.get('files',{}).items():_pin(name,files,digest)
    fields=['vt_symbol','date','source_contract_epoch_id','classification_reason'];provenance=['source_path','source_sha256','source_locator'];source=pd.read_csv(path)
    if any(field not in source for field in fields+provenance):raise ValueError('structural_fields_missing')
    source['date']=source.date.astype(str).str[:10];keys=list(zip(source.vt_symbol,source.date));wanted=set(zip(missing.main_contract_vt,missing.date))
    if len(keys)!=len(set(keys)):raise ValueError('structural_duplicate_key')
    if not set(keys).issubset(wanted):raise ValueError('structural_missing_key_set')
    approved=policy.get('approved_keys',[])
    if len(approved)!=18 or len(source)!=18 or {tuple(str(r[f]) for f in fields) for r in approved}!={tuple(str(r[f]) for f in fields) for r in source.to_dict('records')}:raise ValueError('structural_approved_keys')
    expected1805={'2018-05-02','2018-05-03','2018-05-04','2018-05-07','2018-05-08','2018-05-09','2018-05-10'}
    expected1905={'2018-06-29','2018-07-02','2018-07-03','2018-07-04','2018-07-05','2018-07-06','2018-07-09','2018-07-10','2018-07-11','2018-07-12','2018-07-13'}
    if set(keys)!={('fu1805.SHFE',d) for d in expected1805}|{('fu1905.SHFE',d) for d in expected1905}:raise ValueError('structural_fixed_scope_changed')
    raws={};records=[]
    for row in source.to_dict('records'):
        if any(pd.isna(row[f]) or not str(row[f]).strip() for f in fields+provenance):raise ValueError('structural_provenance_missing')
        symbol=row['vt_symbol'];day=row['date'];epoch=index['by_id'].get(row['source_contract_epoch_id'])
        if 'fu.SHFE' not in products or not epoch or epoch['vt_symbol']!=symbol:raise ValueError('structural_source_identity_invalid')
        if symbol=='fu1805.SHFE':
            if row['classification_reason']!='fu1805_after_delisting_frozen_mapping' or not epoch['delisted_date'] or epoch['delisted_date']>=day:raise ValueError('structural_expired_metadata_mismatch')
        elif row['classification_reason']!='fu1905_official_termination_relisting_gap' or not epoch['listed_date'] or not '2018-06-27'<day<epoch['listed_date'] or epoch['listed_date']!='2018-07-16':raise ValueError('structural_termination_gap_mismatch')
        _pin(row['source_path'],files,row['source_sha256'])
        if row['source_path'] not in raws:raws[row['source_path']]=pd.read_csv(row['source_path'])
        raw=raws[row['source_path']]
        if any(field not in raw for field in ['vt_symbol','date','source_contract_epoch_id','source_key_absent']):raise ValueError('structural_source_absence_fields')
        q=raw.loc[raw.vt_symbol.astype(str).eq(symbol)&raw.date.astype(str).str[:10].eq(day)&raw.source_contract_epoch_id.astype(str).eq(row['source_contract_epoch_id'])]
        if len(q)!=1 or str(q.iloc[0].source_key_absent).lower()!='true':raise ValueError('structural_source_absence_unproved')
        out={f:row[f] for f in fields+provenance};out.update(classification='structural_unavailable_frozen_mapping_not_bar',policy_id=policy['policy_id']);records.append(out)
    return pd.DataFrame(records),missing.loc[[(r.main_contract_vt,r.date) not in set(keys) for r in missing.itertuples()]].copy()

def snapshot_database(base_path,out_path,bars,products):
    base_path=Path(base_path).resolve();out_path=Path(out_path).resolve()
    if out_path.exists() or out_path==base_path:raise ValueError('output_database_exists')
    before=sha(base_path)
    with sqlite3.connect('file:'+str(base_path)+'?mode=ro',uri=True) as src,sqlite3.connect(out_path) as dst:src.backup(dst)
    with sqlite3.connect(out_path) as dst:
        old=pd.read_sql_query("select * from dbbardata where interval='d' and datetime>=?",dst,params=[START]);physical=old.symbol.astype(str).str.match(r'^[A-Za-z]+\d{3,4}$');old['product_vt']=old.symbol.astype(str).str.replace(r'\d+$','',regex=True)+'.'+old.exchange.astype(str);old=old.loc[physical&old.product_vt.isin(products)].copy();dst.executemany('delete from dbbardata where id=?',[(int(i),) for i in old.id]);rows=[]
        for r in bars.itertuples():
            symbol,exchange=r.vt_symbol.split('.');rows.append((symbol,exchange,r.date+' 00:00:00','d',r.volume,0.,r.close_oi,r.open,r.high,r.low,r.close))
        dst.executemany('insert into dbbardata(symbol,exchange,datetime,interval,volume,turnover,open_interest,open_price,high_price,low_price,close_price) values(?,?,?,?,?,?,?,?,?,?,?)',rows)
        if dst.execute("select count(*) from sqlite_master where type='table' and name='dbbaroverview'").fetchone()[0]:
            for symbol,exchange in old[['symbol','exchange']].drop_duplicates().itertuples(index=False,name=None):dst.execute("delete from dbbaroverview where symbol=? and exchange=? and interval='d'",(symbol,exchange))
            for symbol in bars.vt_symbol.unique():
                code,exchange=symbol.split('.');count,start,end=dst.execute("select count(*),min(datetime),max(datetime) from dbbardata where symbol=? and exchange=? and interval='d'",(code,exchange)).fetchone();dst.execute("delete from dbbaroverview where symbol=? and exchange=? and interval='d'",(code,exchange));dst.execute('insert into dbbaroverview(symbol,exchange,interval,count,start,end) values(?,?,?,?,?,?)',(code,exchange,'d',count,start,end))
        if dst.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('assembled_database_integrity_failed')
    if sha(base_path)!=before:raise ValueError('base_database_mutated')
    return old

def assemble_history(clean_db,clean_manifest,base_db,base_mapping,metadata,target_mapping,probe_dirs,out,products,approved=None,approval_policy=None,evidence_paths=(),known_no_trade=None,no_trade_policy=None,structural_unavailable=None,structural_policy=None):
    out=Path(out).resolve()
    if out.exists():raise ValueError('immutable_output_directory_exists:'+str(out))
    out.mkdir(parents=True);files={};_pin(__file__,files);base_db=Path(base_db).resolve();clean_db=Path(clean_db).resolve();before=sha(base_db)
    source_root=next((parent.parent for parent in clean_db.parents if parent.name=='research'),clean_db.parent)
    def source_ref(value):
        value=Path(value);return value if value.is_absolute() else source_root/value
    try:
        _pin(base_db,files,before);_pin(clean_manifest,files);manifest=json.loads(Path(clean_manifest).read_text());_pin(clean_db,files,manifest['database']['sha256'])
        for receipt in manifest.get('receipts',[]):_pin(receipt['path'],files,receipt['sha256'])
        for evidence in evidence_paths:_pin(evidence,files)
        _pin(base_mapping,files);_pin(metadata,files);_pin(target_mapping,files)
        with sqlite3.connect('file:'+str(clean_db)+'?mode=ro',uri=True) as db:
            contracts=pd.read_sql_query('select * from contracts',db);source_table=pd.read_sql_query('select * from sources',db);frame=pd.read_sql_query("select * from daily_bars where quality_status='accepted' and trade_date>=? and trade_date<=?",db,params=[START,END])
        index=epoch_index(contracts,products);allowed=set(index['by_id']);frame=frame.loc[frame.contract_epoch_id.isin(allowed)].copy();used=set(frame.source_id);source_paths={};source_shas={}
        for row in source_table.loc[source_table.source_id.isin(used)].to_dict('records'):
            digest=_pin(source_ref(row['path']),files,row['sha256']);source_paths[row['source_id']]=str(source_ref(row['path']).resolve());source_shas[row['source_id']]=digest
            if _optional(row.get('raw_path')):_pin(source_ref(row['raw_path']),files)
        if used-set(source_paths):raise ValueError('clean_source_identity_missing')
        frame['source_path']=frame.source_id.map(source_paths);frame['source_sha256']=frame.source_id.map(source_shas);print('clean accepted source rows',len(frame),flush=True);clean,excluded=clean_bars(frame,index,products);layers=[clean]
        for directory in probe_dirs:layers.append(probe_bars(directory,index,products,files))
        if approved:layers.append(approved_supplement(approved,approval_policy,index,products,files))
        elif approval_policy:raise ValueError('approval_without_supplement')
        bars,duplicates=merge_bars(layers);gaps=native_epoch_gaps(bars);mapping=merge_mapping(pd.read_csv(base_mapping),pd.read_csv(target_mapping));missing=missing_main(mapping,bars,products,'2015-01-01',END);warm_missing=missing_main(mapping,bars,products,START,'2014-12-31')
        missing.to_csv(out/'missing_main_all_before_classification.csv',index=False);missing_before_classification=len(missing);known=pd.DataFrame(columns=['vt_symbol','date','contract_epoch_id','classification','zero_volume'])
        if known_no_trade:known,missing=approved_no_trade(known_no_trade,no_trade_policy,index,products,files,missing)
        elif no_trade_policy:raise ValueError('no_trade_policy_without_csv')
        known.to_csv(out/'known_no_trade_main.csv',index=False)
        structural=pd.DataFrame(columns=['vt_symbol','date','classification'])
        if structural_unavailable:structural,missing=approved_structural_unavailable(structural_unavailable,structural_policy,index,products,files,missing)
        elif structural_policy:raise ValueError('structural_policy_without_csv')
        structural.to_csv(out/'structural_unavailable_main.csv',index=False)
        # Every consumed original19 physical daily row is rebuilt; old keys are quarantined, not reused as fallback.
        print('rebuilding database',len(bars),'accepted bars; main gaps',len(missing),flush=True);old=snapshot_database(base_db,out/'daily.sqlite',bars,products);old.to_csv(out/'old_original19_isolated.csv.gz',index=False,compression='gzip');old['vt_symbol']=old.symbol+'.'+old.exchange;old['date']=old.datetime.astype(str).str[:10]
        common=old.merge(bars,on=['vt_symbol','date'],how='inner',validate='one_to_one');common['old_new_price_diff']=False
        for legacy,new in [('open_price','open'),('high_price','high'),('low_price','low'),('close_price','close')]:common['old_new_price_diff']|=(common[legacy]-common[new]).abs().gt(1e-8)
        common['volume_delta']=common.volume_y-common.volume_x;common['close_oi_delta']=common.close_oi-common.open_interest;common.to_csv(out/'old_vs_new_common_fields.csv.gz',index=False,compression='gzip')
        keys=set(zip(bars.vt_symbol,bars.date));not_restored=old.loc[[(r.vt_symbol,r.date) not in keys for r in old.itertuples()]].copy();not_restored['reason']='not_in_accepted_positive_source_union';not_restored.to_csv(out/'old_unaccepted_not_restored.csv.gz',index=False,compression='gzip')
        mapping.to_csv(out/'mapping.csv',index=False);shutil.copyfile(metadata,out/'metadata.csv');bars.to_csv(out/'physical_epoch_daily.csv',index=False);pd.DataFrame(index['by_id'].values()).to_csv(out/'physical_epochs.csv',index=False);gaps.to_csv(out/'native_epoch_gaps.csv',index=False);excluded.to_csv(out/'known_lifecycle_excluded.csv',index=False);missing.to_csv(out/'missing_main.csv',index=False);warm_missing.to_csv(out/'warmup_missing_main_2014.csv',index=False)
        # Exact accepted DB/lookup parity, not just a row count.
        with sqlite3.connect(out/'daily.sqlite') as db:rebuilt=pd.read_sql_query("select symbol||'.'||exchange vt_symbol,substr(datetime,1,10) date,open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where interval='d' and datetime>=?",db,params=[START])
        rebuilt=rebuilt.loc[rebuilt.vt_symbol.astype(str).str.match(r'^[A-Za-z]+[0-9]{3,4}\.[A-Z]+$')&rebuilt.vt_symbol.str.replace(r'\d+(?=\.)','',regex=True).isin(products)]
        joined=bars.merge(rebuilt,on=['vt_symbol','date'],validate='one_to_one',suffixes=('_accepted','_db'))
        parity=len(joined)==len(bars)==len(rebuilt)
        for left,right in [('open','open_price'),('high','high_price'),('low','low_price'),('close','close_price'),('volume_accepted','volume_db'),('close_oi','open_interest')]:parity=parity and (joined[left]-joined[right]).abs().le(1e-8).all()
        if not parity:raise ValueError('canonical_database_lookup_parity_failed')
        after=sha(base_db)
        if after!=before:raise ValueError('old_M_database_changed')
        # Recheck every pinned source at finish; a concurrently written supplement/source is rejected.
        changed=[path for path,digest in files.items() if sha(path)!=digest]
        if changed:raise ValueError('source_drift:'+repr(changed))
        target=mapping.loc[mapping.date.eq(END)&mapping.continuous_symbol_vt.isin(products)&mapping.main_contract_vt.fillna('').ne('')]
        receipt={'schema':'stage023_history_data_receipt_v1','status':'prepared_accepted_base' if not approved else 'prepared_approved_supplement','data_ready':bool(missing.empty and len(target)==len(products)),'data_ready_for_bounded_replay':bool(missing.empty and len(target)==len(products)),'historical_main_reconstruction_complete':bool(not len(structural) and missing.empty),'date_start':START,'financial_start':'2015-01-01','date_end':END,'units':'single_sided_volume_close_oi','quantity_fields':{'volume':'accepted single-sided contracts','open_interest':'same completed day close_oi; never open_oi'},'products':list(products),'financial_replays':0,'source_layers_rows':[len(layer) for layer in layers],'accepted_rows':len(bars),'exact_duplicate_rows_not_overwritten':duplicates,'main_missing_before_no_trade_classification':missing_before_classification,'known_no_trade_main':len(known),'structural_unavailable_main':len(structural),'structural_unavailable_not_in_bars':True,'structural_policy':str(Path(structural_policy).resolve()) if structural_policy else None,'unknown_missing_main':len(missing),'known_no_trade_not_in_bars':True,'known_no_trade_policy':str(Path(no_trade_policy).resolve()) if no_trade_policy else None,'main_missing_2015_onward':len(missing),'warmup_missing_main_2014':len(warm_missing),'known_lifecycle_excluded_rows':len(excluded),'epochs_with_unknown_full_lifecycle':int(sum(row['lifecycle_status']=='observed_bar_identity_known_full_lifecycle_unknown' for row in index['by_id'].values())),'native_reused_epoch_pairs':len(gaps),'old_original19_rows_isolated':len(old),'old_keys_not_restored_no_fallback':len(not_restored),'common_old_new_rows':len(common),'common_OHLC_differences':int(common.old_new_price_diff.sum()),'common_volume_differences':int(common.volume_delta.abs().gt(1e-8).sum()),'common_close_OI_differences':int(common.close_oi_delta.abs().gt(1e-8).sum()),'old_M_sha256_before':before,'old_M_sha256_after':after,'old_M_unchanged':True,'canonical_DB_lookup_parity':True,'risk_metadata_unchanged':sha(out/'metadata.csv')==sha(metadata),'Stage278_patch259':'not layered:257 already accepted clean,2 zero-volume nontradable; existing oldM259 evidence only','readiness_limitations':['2014 MA aliases have228 missing mapped days; hc1505 first2015 target has only13 complete2014 weeks; actual21-ready state must be exported by replay.','Unknown full future lifecycle is labeled; never infer expiry from observed last row.','Frozen mapping has explicit18 structural defects, not a reconstructed historical main series; no substitute contracts inferred. data_ready requires unknown main gaps0; approved real zero-volume keys are classification-only, never bars/week inputs/fills. Every held/traded/week-source positive-data and execution/accounting gate remains mandatory.'],'stage022_lifecycle_label_correction':'Initial8 cohort is not8 lifecycle failures:7 are within clean vendor inclusive listing/delisting; only FU1905/2018-05-09 precedes2018-07-16 new contract listing. No metadata amendment performed.', 'approved_supplement_used':str(Path(approved).resolve()) if approved else None,'completed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
        _json(out/'receipt.json',receipt)
        for output in out.iterdir():
            if output.is_file():_pin(output,files)
        _pin(__file__,files);_json(out/'source_manifest.json',{'schema':'stage023_history_source_manifest_v1','files':files,'source_manifest_self_not_in_files':True,'financial_replays':0,'immutable_output':True});return receipt
    except BaseException as exc:
        _json(out/'receipt.json',{'schema':'stage023_history_data_receipt_v1','status':'failed_preparation','data_ready':False,'date_end':END,'units':'single_sided_volume_close_oi','error':repr(exc),'financial_replays':0});raise

def main():
    root=Path(__file__).resolve().parents[4];line=root/'research/lines/futures_weekly_formal_no_half_r';source=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs');clean=source/'stage266_clean_daily';old=line/'outputs/stage005_data'
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=line/'outputs/stage023_history_data');ap.add_argument('--approved-supplement',type=Path);ap.add_argument('--approval-policy',type=Path);ap.add_argument('--known-no-trade',type=Path);ap.add_argument('--no-trade-policy',type=Path);ap.add_argument('--structural-unavailable',type=Path);ap.add_argument('--structural-policy',type=Path);args=ap.parse_args();products=json.loads((line/'outputs/M_attempt001/preflight.json').read_text())['universe_products']
    evidence=[source/'stage278_daily_2015_20261022/data_review/historical_accepted_patch.csv',source/'stage278_daily_2015_20261022/data_review/historical_accepted_receipt.json',clean/'price_conflict_quarantine.csv',clean/'stage266_units_quarantine.csv',line/'stages/stage022_historical_inventory_review.json',line/'outputs/M_attempt001/input_manifest.json',old/'completed_manifest.json',Path(__file__).with_name('test_stage023_prepare_history.py'),line/'stages/stage022_lifecycle_rule_review.json']
    result=assemble_history(clean/'clean_daily.sqlite',clean/'dataset_manifest.json',old/'daily.sqlite',old/'mapping.csv',old/'metadata.csv',line/'outputs/stage022_latest_probe/target_mapping.csv',[line/'outputs/stage022_latest_probe',line/'outputs/stage022_offmain_probe'],args.out,products,args.approved_supplement,args.approval_policy,evidence,args.known_no_trade,args.no_trade_policy,args.structural_unavailable,args.structural_policy)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
