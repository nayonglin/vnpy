"""Consensus real prices isolated from disputed volume/OI; close/valuation only.

This source never changes accepted clean bars, signals, main selection, or
training eligibility. All source observations at a key must agree on OHLC.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import csv,gzip,hashlib,io,json,math,re,sqlite3,sys,zipfile
from pathlib import Path
import pandas as pd
from stage002_market_source import SOURCE_LINE,LINE,identity

OUT=LINE/'outputs/stage023_quantity_price_overlay'
PRICE_FIELDS=('open','high','low','close')
START,END='2014-01-01','2026-10-16'
QUOTE_CLASS='quantity_conflict_price_consensus_execution_only'


def qualify_quotes(contract,day,quotes,*,quantity_quarantine,price_quarantine=False):
    if not contract or not contract.get('contract_epoch_id'):
        return False,'unknown_epoch'
    if not quantity_quarantine or price_quarantine:
        return False,'not_quantity_only_quarantine'
    if not contract.get('maturity_date') or day>str(contract['maturity_date']):
        return False,'unknown_maturity_or_after_maturity'
    if sum(q.get('source_id')=='rqalpha' for q in quotes)!=1 or not any(str(q.get('source_id','')).startswith('official:') for q in quotes):
        return False,'missing_unique_RQ_or_official'
    prices=[]
    for q in quotes:
        if q.get('contract_epoch_id')!=contract['contract_epoch_id'] or q.get('date')!=day:
            return False,'quote_epoch_or_date_mismatch'
        try:p=tuple(float(q[k]) for k in PRICE_FIELDS);v=float(q['volume']);oi=float(q['close_oi'])
        except (KeyError,ValueError,TypeError):return False,'quote_numeric_missing'
        if not all(math.isfinite(x) and x>0 for x in p) or not p[2]<=min(p[0],p[3])<=max(p[0],p[3])<=p[1]:
            return False,'invalid_price_or_geometry'
        if not math.isfinite(v) or v<1 or not math.isfinite(oi) or oi<0:
            return False,'invalid_or_below_one_canonical_volume_or_oi'
        prices.append(p)
    if len(set(prices))!=1:return False,'any_present_source_price_disagreement'
    return True,'eligible_price_consensus_quantity_conflict'


def _day(value):
    text=str(int(value));return f'{text[:4]}-{text[4:6]}-{text[6:8]}'


def _number(v):
    try:return float(v)
    except (ValueError,TypeError):return None


def build_overlay():
    import h5py
    # Existing pure spreadsheet reader; importing this module runs no downloader.
    sys.path.insert(0,str(SOURCE_LINE.parent/'tools'))
    sys.dont_write_bytecode=True
    import stage265_exchanges_normalize as normalizer
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('output_exists_refusing_overwrite')
    clean=SOURCE_LINE/'stage266_clean_daily';db_path=clean/'clean_daily.sqlite'
    units=json.loads((clean/'unit_contract.json').read_text())
    metadata_path=LINE/'outputs/inputs/contract_metadata.csv'
    metadata=pd.read_csv(metadata_path,keep_default_na=False,dtype={'contract_yyyymm':str})
    known=metadata.set_index('contract_epoch_id').to_dict('index')
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
        contracts={r['contract_epoch_id']:dict(r) for r in db.execute('SELECT * FROM contracts')}
        sources={r['source_id']:dict(r) for r in db.execute('SELECT * FROM sources')}
    with (clean/'stage266_units_quarantine.csv').open(encoding='utf-8-sig') as stream:
        all_quantity={(r['contract_epoch_id'],r['trade_date']) for r in csv.DictReader(stream)}
    with (clean/'price_conflict_quarantine.csv').open(encoding='utf-8-sig') as stream:
        price_keys={(r['contract_epoch_id'],r['trade_date']) for r in csv.DictReader(stream)}
    expiry_path=LINE/'outputs/expiry_execution_overlay.csv'
    expiry=pd.read_csv(expiry_path);expiry_keys=set(zip(expiry.contract_epoch_id,expiry.date))
    candidate_keys={(e,d) for e,d in all_quantity if e in known and START<=d<=END}
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        accepted={key for key in candidate_keys if db.execute('SELECT 1 FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',key).fetchone()}
    observations=defaultdict(list)
    with gzip.open(clean/'excluded_observations.csv.gz','rt',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            key=(row['contract_epoch_id'],row['trade_date'])
            if key in candidate_keys and row['reason']=='cross_source_quantity_conflict':observations[key].append(row)
    required_norm_rows=defaultdict(set)
    for group in observations.values():
        for record in group:
            if record['source_id'].startswith('official:'):required_norm_rows[record['source_id']].add(int(json.loads(record['source_locator'])['row']))
    source_files={};norm_cache={};tq_cache={};raw_cache={};stats=Counter();rejections=[];output=[];evidence=[]
    frozen_inputs={str(p):identity(p) for p in [db_path,clean/'unit_contract.json',clean/'stage266_units_quarantine.csv',clean/'price_conflict_quarantine.csv',clean/'excluded_observations.csv.gz',metadata_path,expiry_path,Path(normalizer.__file__)]}
    def verify_source(sid):
        if sid not in source_files:
            src=sources[sid];observed=identity(src['path'])
            if observed['sha256']!=src['sha256']:raise RuntimeError('pinned_source_changed:'+sid)
            source_files[sid]=observed
        return source_files[sid]
    def normalized_row(sid,locator):
        if sid not in norm_cache:
            with gzip.open(sources[sid]['path'],'rt',encoding='utf-8-sig') as stream:
                norm_cache[sid]={i:r for i,r in enumerate(csv.DictReader(stream),2) if i in required_norm_rows[sid]}
        row=norm_cache[sid].get(int(locator['row']))
        if row is None:raise ValueError('official_normalized_row_missing')
        return row
    def official_raw(sid,normalized):
        src=sources[sid];raw_path=Path(src['raw_path']);member=normalized['source_member'];cache_key=(str(raw_path),member)
        if cache_key not in raw_cache:
            raw_id='raw:'+str(raw_path)
            if raw_id not in source_files:source_files[raw_id]=identity(raw_path)
            targets={(r['source_sheet'],int(r['source_row'])) for r in norm_cache[sid].values() if r['source_member']==member}
            records={};blob=None
            if zipfile.is_zipfile(raw_path):
                with zipfile.ZipFile(raw_path) as archive:blob=archive.read(member)
                if normalized['source_sheet']=='CSV':
                    try:text=blob.decode('utf-8-sig')
                    except UnicodeDecodeError:text=blob.decode('gb18030')
                    for rownum,row in enumerate(csv.DictReader(io.StringIO(text)),2):
                        if ('CSV',rownum) not in targets:continue
                        values={str(k).strip():str(v).strip() if v is not None else '' for k,v in row.items()}
                        quote={key:_number(next((values[a] for a in aliases if a in values),None)) for key,aliases in normalizer.HEADER.items() if key not in ['date','instrument']}
                        quote['close_oi']=quote.pop('open_interest')
                        records[('CSV',rownum)]=dict(instrument=values.get('合约代码',''),date=member[:8],quote=quote,raw_values=values)
                else:
                    for sheet,rows,_ in normalizer.sheets(blob):
                        columns=None;current=''
                        for rownum,values in rows:
                            labels=[normalizer.text(v) for v in values]
                            found={key:next((labels.index(alias) for alias in aliases if alias in labels),None) for key,aliases in normalizer.HEADER.items()}
                            if all(found[k] is not None for k in ['instrument','date','open','high','low','close','volume','open_interest']):columns=found;current='';continue
                            if columns is None:continue
                            raw={k:values[i] if i is not None and i<len(values) else '' for k,i in columns.items()}
                            instrument=normalizer.text(raw['instrument']);date=normalizer.text(raw['date'])
                            if instrument:current=instrument
                            if not current or not re.fullmatch(r'\d{8}',date):continue
                            if (sheet,rownum) not in targets:continue
                            quote={k:_number(raw[k]) for k in [*PRICE_FIELDS,'volume']};quote['close_oi']=_number(raw['open_interest'])
                            records[(sheet,rownum)]=dict(instrument=current,date=date,quote=quote,raw_values=raw)
            else:
                raw_json=json.loads(raw_path.read_text())
                for i,row in enumerate(raw_json.get('o_curinstrument',[]),1):
                    if ('o_curinstrument',i) not in targets:continue
                    quote={key:_number(row.get(k)) for key,k in {'open':'OPENPRICE','high':'HIGHESTPRICE','low':'LOWESTPRICE','close':'CLOSEPRICE','volume':'VOLUME','close_oi':'OPENINTEREST'}.items()}
                    records[('o_curinstrument',i)]=dict(instrument=str(row.get('PRODUCTGROUPID','')).strip()+str(row.get('DELIVERYMONTH','')).strip(),date=str(raw_json['report_date']),quote=quote,raw_values=row)
            raw_cache[cache_key]=(records,source_files[raw_id],hashlib.sha256(blob).hexdigest() if blob is not None else None)
        records,raw_file,member_sha=raw_cache[cache_key]
        result=records.get((normalized['source_sheet'],int(normalized['source_row'])))
        if result is None:raise ValueError('official_original_row_missing')
        if result['instrument'].strip().lower()!=normalized['source_symbol'].strip().lower() or result['date']!=normalized['date'].replace('-',''):
            raise ValueError('official_original_identity_or_date_mismatch')
        expected={k:float(normalized[k]) for k in [*PRICE_FIELDS,'volume']};expected['close_oi']=float(normalized['open_interest'])
        if any(result['quote'][k]!=v for k,v in expected.items()):raise ValueError('official_original_quote_mismatch')
        return dict(raw_archive=raw_file,member=member,member_sha256=member_sha,sheet=normalized['source_sheet'],row=int(normalized['source_row']),**result)
    verify_source('rqalpha')
    with h5py.File(sources['rqalpha']['path'],'r') as h5:
        for (epoch,day),items in sorted(observations.items()):
            def reject(reason):
                stats[reason]+=1;rejections.append(dict(contract_epoch_id=epoch,date=day,reason=reason))
            if (epoch,day) in accepted:reject('accepted_duplicate');continue
            if (epoch,day) in expiry_keys:reject('existing_expiry_duplicate');continue
            if (epoch,day) in price_keys:reject('price_quarantine');continue
            # Early no-price-consensus rejection avoids decoding irrelevant archives.
            raw_quotes=[json.loads(r['raw_values']) for r in items]
            try:price_set={tuple(float(r[k]) for k in PRICE_FIELDS) for r in raw_quotes}
            except (TypeError,ValueError,KeyError):reject('invalid_exclusion_price');continue
            if len(price_set)!=1:reject('any_present_source_price_disagreement');continue
            if sum(r['source_id']=='rqalpha' for r in items)!=1 or not any(r['source_id'].startswith('official:') for r in items):reject('missing_unique_RQ_or_official');continue
            quotes=[];proofs=[]
            try:
                for record in items:
                    sid=record['source_id'];locator=json.loads(record['source_locator']);file_id=verify_source(sid);native=json.loads(record['raw_values']);proof={}
                    ex,p,month=epoch.split('.')
                    if sid=='rqalpha':
                        expected_symbol=p.replace('_F','')+month[2:]+('F' if p.endswith('_F') else '')
                        if locator['key']!=expected_symbol:raise ValueError('rq_exact_epoch_mismatch')
                        r=h5[locator['key']][int(locator['row'])]
                        if _day(r['datetime'])!=day:raise ValueError('rq_exact_date_mismatch')
                        actual={k:float(r[k]) for k in [*PRICE_FIELDS,'volume']};actual['close_oi']=float(r['open_interest'])
                        matched=[r for r in units['rqalpha']['rules'] if ex in r['exchanges'] and r['start']<=day<=r['end']]
                        if len(matched)!=1:raise ValueError('rq_unit_unknown')
                        factors=(float(matched[0]['volume_factor']),float(matched[0]['close_oi_factor']))
                        proof=dict(rq_key=locator['key'],rq_row=int(locator['row']),rq_trade_date=day)
                    elif sid.startswith('official:'):
                        norm=normalized_row(sid,locator)
                        if (norm['exchange'],norm['product'].upper(),str(norm['contract_yyyymm']),norm['date'])!=(ex,p,month,day):raise ValueError('official_exact_epoch_date_mismatch')
                        factor=units['official']['accepted_regime_factors'].get(norm['unit_regime'])
                        if factor is None:raise ValueError('official_unit_unknown')
                        factors=(float(factor),float(factor));proof=dict(normalized_record=norm,original=official_raw(sid,norm))
                        actual={k:float(norm[k]) for k in [*PRICE_FIELDS,'volume']};actual['close_oi']=float(norm['open_interest'])
                    elif sid.startswith(('old_tq:','recent_tq:')):
                        if sid not in tq_cache:
                            with Path(sources[sid]['path']).open(encoding='utf-8-sig') as stream:tq_cache[sid]={i:r for i,r in enumerate(csv.DictReader(stream),2)}
                        row=tq_cache[sid].get(int(locator['row']))
                        if row is None or row.get('trade_date','')[:10]!=day:raise ValueError('tq_exact_row_date_mismatch')
                        if sid.split(':',1)[1].lower()!=known[epoch]['native_symbol'].rsplit('.',1)[1].lower()+'.'+known[epoch]['native_symbol'].rsplit('.',1)[0].lower():raise ValueError('tq_exact_native_epoch_mismatch')
                        actual={k:float(row[k]) for k in [*PRICE_FIELDS,'volume','close_oi']}
                        rule=units['recent_tq' if sid.startswith('recent_tq:') else 'old_tq'];factors=(float(rule['volume_factor']),float(rule['close_oi_factor']));proof=dict(csv_row=int(locator['row']),csv_values=row)
                    else:raise ValueError('unsupported_source_family')
                    if any(actual[k]!=float(native[k]) for k in [*PRICE_FIELDS,'volume','close_oi']):raise ValueError('source_quote_vs_exclusion_mismatch')
                    canonical={**actual,'volume':actual['volume']*factors[0],'close_oi':actual['close_oi']*factors[1], 'source_id':sid,'contract_epoch_id':epoch,'date':day}
                    quotes.append(canonical);proofs.append(dict(source_id=sid,source_file=file_id,locator=locator,raw_quote=actual,canonical_quote=canonical,quantity_factors=factors,source_proof=proof))
            except (ValueError,KeyError,IndexError) as exc:reject(str(exc));continue
            okay,reason=qualify_quotes(contracts.get(epoch),day,quotes,quantity_quarantine=(epoch,day) in all_quantity,price_quarantine=(epoch,day) in price_keys)
            if not okay:reject(reason);continue
            official=sorted((q for q in quotes if q['source_id'].startswith('official:')),key=lambda r:r['source_id'])[0]
            evidence_id=f'quantity_price_consensus:{epoch}:{day}'
            output.append(dict(contract_epoch_id=epoch,exchange=ex,product=p,contract_yyyymm=month,date=day,
                               **{k:official[k] for k in PRICE_FIELDS},volume=min(q['volume'] for q in quotes),close_oi=official['close_oi'],open_oi=None,
                               source_id=official['source_id'],vt_symbol=known[epoch]['vt_symbol'],execution_only=True,allow_new_open=False,
                               quantity_certified=False,quote_class=QUOTE_CLASS,evidence_id=evidence_id))
            evidence.append(dict(evidence_id=evidence_id,epoch=epoch,date=day,contract=contracts[epoch],quotes=proofs,
                                 minimum_positive_volume=min(q['volume'] for q in quotes),quantity_policy='minimum_only_for_one_lot_execution_qualification_not_true_volume_certification',open_signal_eligible=False))
    for _,spec in frozen_inputs.items():
        if identity(spec['path'])!=spec:raise RuntimeError('frozen_input_changed:'+spec['path'])
    for sid,spec in source_files.items():
        if identity(spec['path'])!=spec:raise RuntimeError('verified_source_changed:'+sid)
    frame=pd.DataFrame(output)
    if frame.empty:raise ValueError('no_qualified_quotes')
    if frame.duplicated(['vt_symbol','date']).any():raise ValueError('duplicate_output_key')
    OUT.mkdir(parents=True,exist_ok=True);csv_path=OUT/'execution_quotes.csv';frame.to_csv(csv_path,index=False)
    receipt=dict(status='execution_only_price_consensus_not_accepted_signals_or_training',rows=len(frame),output=identity(csv_path),source_files=source_files,
                 policy='exact_epoch_day_quantity_only_quarantine_all_present_real_OHLC_equal_and_canonical_V_ge_one_RQ_plus_official',
                 scope=dict(start=START,end=END,metadata_sha256=identity(metadata_path)['sha256'],expiry_overlay_sha256=identity(expiry_path)['sha256']),
                 candidate_keys=len(candidate_keys),rejected_counts=dict(stats),rejections=rejections,source_inputs=frozen_inputs,
                 quote_class=QUOTE_CLASS,code=identity(__file__),evidence=evidence,financial_backtests=0,model_fits=0,downloads=0,
                 boundaries=['Close existing positions or valuation only; no new open, signal, main selection, warmup or training eligibility.',
                             'Quantity/OI remain disputed; minimum positive canonical volume is only a conservative one-lot quote gate.',
                             'No price-disagreement record is recovered; no source is selected by PNL or cutoff success.',
                             'Daily OHLC agreement does not guarantee real counterfactual order liquidity.'])
    (OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['status','rows','output','candidate_keys','rejected_counts','financial_backtests']},ensure_ascii=False,indent=2))

if __name__=='__main__':build_overlay()
