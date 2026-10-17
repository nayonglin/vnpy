"""Create an isolated, source-traceable research daily store; never train/order.

All quantities are explicitly converted to single-sided contracts. Missing
opening OI stays NULL. Entire source rows compete by a frozen source priority.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

from stage265_rqalpha_inventory import contract_id

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
INPUT = LINE / 'outputs/stage265_deep_daily'
OUT = LINE / 'outputs/stage266_clean_daily'
START, END = '2010-01-01', '2026-10-16'
FIELDS = ['contract_epoch_id', 'exchange', 'product', 'source_symbol', 'contract_yyyymm',
    'trade_date', 'open', 'high', 'low', 'close', 'volume', 'close_oi', 'open_oi',
    'open_interest', 'source_id', 'source_locator', 'volume_factor', 'oi_factor',
    'native_volume', 'native_close_oi', 'native_open_oi', 'open_oi_status',
    'quality_status', 'legacy108_row_usable', 'train_eligible', 'priority']


def row_issue(row):
    if row['volume'] == 0:
        return 'no_trade'
    if not all(math.isfinite(row[k]) and row[k] > 0 for k in ['open', 'high', 'low', 'close']):
        return 'invalid_ohlc'
    if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
        return 'invalid_ohlc'
    if not all(math.isfinite(row[k]) and row[k] >= 0 for k in ['volume', 'close_oi']):
        return 'invalid_quantity'
    return None


def canonical_values(row, volume_factor, oi_factor):
    if volume_factor not in (1., .5) or oi_factor not in (1., .5):
        raise ValueError('unknown_unit')
    result = {k: row[k] for k in ['open', 'high', 'low', 'close']}
    for key, factor in [('volume', volume_factor), ('close_oi', oi_factor), ('open_oi', oi_factor)]:
        value = row.get(key)
        if value is None or (key == 'open_oi' and not math.isfinite(value)):
            result[key] = None
            continue
        value *= factor
        if value < 0 or not math.isfinite(value) or abs(value - round(value)) > 1e-6:
            raise ValueError('invalid_or_fractional_single_sided_quantity')
        result[key] = float(round(value))
    result['open_oi_status'] = 'missing_not_imputed' if result['open_oi'] is None else 'source_observed'
    result['legacy108_row_usable'] = int(result['open_oi'] is not None)
    return result


def resolve_alias(index, alias, trade_date):
    matches = [x['contract_epoch_id'] for x in index.get(alias, [])
        if x['listed_date'] <= trade_date <= x['delisted_date']]
    if len(set(matches)) != 1:
        raise ValueError('ambiguous_or_outside_metadata_identity')
    return matches[0]


def pick_source(previous, candidate):
    return candidate if candidate['priority'] > previous['priority'] else previous


def conflict_keys(rows, metadata):
    return {(metadata[r['rq_symbol']]['contract_epoch_id'], r['date']) for r in rows}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')


class Builder:
    def __init__(self, unit_contract):
        import numpy as np
        OUT.mkdir(parents=True, exist_ok=True)
        self.final = OUT / 'clean_daily.sqlite'
        self.temporary = OUT / 'clean_daily.building.sqlite'
        if self.final.exists() or self.temporary.exists():
            raise RuntimeError('existing_clean_store_do_not_silently_overwrite')
        self.units = unit_contract
        evidence=load_json(OUT/'stage266_units_evidence.json')
        self.pinned_old={str((ROOT/x['path']).resolve()):x['sha256'] for x in evidence['old_tq_files']}
        self.calendar = {str(int(x))[:4] + '-' + str(int(x))[4:6] + '-' + str(int(x))[6:8]
            for x in np.load(INPUT / 'rqalpha/trading_dates.npy', allow_pickle=False)}
        self.db = sqlite3.connect(self.temporary)
        self.db.executescript('''
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-100000;
            CREATE TABLE contracts(contract_epoch_id TEXT PRIMARY KEY,exchange TEXT,product TEXT,
                contract_yyyymm TEXT,listed_date TEXT,delisted_date TEXT,maturity_date TEXT,metadata_status TEXT);
            CREATE TABLE sources(source_id TEXT PRIMARY KEY,family TEXT,path TEXT,sha256 TEXT,bytes INTEGER,raw_path TEXT);
            CREATE TABLE daily_bars(contract_epoch_id TEXT,exchange TEXT,product TEXT,source_symbol TEXT,
                contract_yyyymm TEXT,trade_date TEXT,open REAL,high REAL,low REAL,close REAL,
                volume REAL,close_oi REAL,open_oi REAL,open_interest REAL,source_id TEXT,
                source_locator TEXT,volume_factor REAL,oi_factor REAL,native_volume REAL,native_close_oi REAL,
                native_open_oi REAL,open_oi_status TEXT,quality_status TEXT,legacy108_row_usable INTEGER,
                train_eligible INTEGER,priority INTEGER,PRIMARY KEY(contract_epoch_id,trade_date)) WITHOUT ROWID;
        ''')
        self.contracts, self.aliases, self.meta_by_rq = {}, defaultdict(list), {}
        for item in load_json(INPUT / 'rqalpha/futures_metadata.json'):
            try:
                identity = contract_id(item)
            except (KeyError, ValueError, TypeError):
                continue
            exchange, product, month = identity.split('.')
            row = dict(contract_epoch_id=identity, exchange=exchange, product=product,
                contract_yyyymm=month, listed_date=item['listed_date'], delisted_date=item['de_listed_date'],
                maturity_date=item['maturity_date'], metadata_status='rq_vendor_metadata')
            self.contracts[identity] = row
            self.meta_by_rq[item['order_book_id']] = row
            for code in set([item.get('trading_code', ''), item['order_book_id']]):
                if code:
                    self.aliases[exchange + '.' + code.upper()].append(row)
        self.db.executemany('INSERT INTO contracts VALUES(?,?,?,?,?,?,?,?)', [tuple(r.values()) for r in self.contracts.values()])
        self.conflicts = conflict_keys(load_json(OUT / 'stage266_units_exceptions.json')['quarantine_keys'], self.meta_by_rq)
        self.stats = defaultdict(Counter)
        self.excluded_file = gzip.open(OUT / 'excluded_observations.csv.gz', 'wt', encoding='utf-8', newline='')
        self.excluded = csv.DictWriter(self.excluded_file,
            fieldnames=['source_id', 'contract_epoch_id', 'trade_date', 'reason', 'source_locator', 'raw_values'], lineterminator='\n')
        self.excluded.writeheader()
        self.diff_file = gzip.open(OUT / 'source_disagreements.csv.gz', 'wt', encoding='utf-8', newline='')
        self.differences = csv.DictWriter(self.diff_file,
            fieldnames=['contract_epoch_id','trade_date','previous_source','candidate_source','selected_source','different_fields','previous_values','candidate_values'],lineterminator='\n')
        self.differences.writeheader()
        self.difference_count = 0
        self.source_ids = set()
        self.sql = 'INSERT INTO daily_bars VALUES(' + ','.join('?' for _ in FIELDS) + ') ON CONFLICT(contract_epoch_id,trade_date) DO UPDATE SET ' + ','.join(k+'=excluded.'+k for k in FIELDS[1:]) + ' WHERE excluded.priority>daily_bars.priority'

    def source(self, source_id, family, path, raw_path=None):
        path = Path(path)
        actual_hash=digest(path)
        expected=self.units['source_lock']['rq_h5_sha256'] if family=='rqalpha' else self.pinned_old.get(str(path.resolve()))
        if (expected and actual_hash!=expected) or (family=='old_tq' and expected is None):
            raise RuntimeError('source_changed_after_unit_calibration:'+source_id)
        self.db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?)',
            (source_id,family,str(path.resolve()),actual_hash,path.stat().st_size,raw_path))
        self.source_ids.add(source_id)

    def reject(self, source_id, identity, day, reason, locator, raw):
        self.stats[source_id][reason] += 1
        self.excluded.writerow(dict(source_id=source_id,contract_epoch_id=identity,trade_date=day,
            reason=reason,source_locator=json.dumps(locator,ensure_ascii=False),raw_values=json.dumps(raw,ensure_ascii=False)))

    def add(self, source_id, identity, symbol, day, raw, factors, priority, locator):
        self.stats[source_id]['raw_observations'] += 1
        reason = None
        if not START <= day <= END:
            reason = 'outside_target_dates'
        elif day not in self.calendar:
            reason = 'not_in_frozen_trading_calendar'
        elif (identity, day) in self.conflicts:
            reason = 'cross_source_quantity_conflict'
        elif identity not in self.contracts:
            reason = 'unresolved_contract_identity'
        else:
            meta = self.contracts[identity]
            if meta['listed_date'] and day < meta['listed_date']:
                reason = 'before_candidate_listing'
            elif meta['delisted_date'] and day > meta['delisted_date']:
                reason = 'after_candidate_delisting'
        reason = reason or row_issue(raw)
        if reason:
            self.reject(source_id,identity,day,reason,locator,raw)
            return
        try:
            values = canonical_values(raw,*factors)
        except ValueError as error:
            self.reject(source_id,identity,day,str(error),locator,raw)
            return
        exchange, product, month = identity.split('.')
        record = dict(contract_epoch_id=identity,exchange=exchange,product=product,source_symbol=symbol,
            contract_yyyymm=month,trade_date=day,**values,open_interest=values['close_oi'],source_id=source_id,
            source_locator=json.dumps(locator,ensure_ascii=False,separators=(',',':')),
            volume_factor=factors[0],oi_factor=factors[1],native_volume=raw['volume'],
            native_close_oi=raw['close_oi'],native_open_oi=raw.get('open_oi'),quality_status='accepted',
            train_eligible=values['legacy108_row_usable'],priority=priority)
        prior = self.db.execute('SELECT source_id,priority,open,high,low,close,volume,close_oi,open_oi FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',(identity,day)).fetchone()
        if prior:
            names=['open','high','low','close','volume','close_oi','open_oi']
            different=[k for k,a in zip(names,prior[2:]) if a is not None and record[k] is not None and abs(a-record[k])>1e-6]
            if different:
                self.difference_count += 1
                self.differences.writerow(dict(contract_epoch_id=identity,trade_date=day,previous_source=prior[0],
                    candidate_source=source_id,selected_source=source_id if priority>prior[1] else prior[0],
                    different_fields='|'.join(different),previous_values=json.dumps(dict(zip(names,prior[2:]))),
                    candidate_values=json.dumps({k:record[k] for k in names})))
        self.db.execute(self.sql, [record[k] for k in FIELDS])
        self.stats[source_id]['accepted_source_observations'] += 1

    def current_identity(self, exchange, symbol, day):
        alias = exchange + '.' + symbol.upper()
        try:
            return resolve_alias(self.aliases,alias,day)
        except ValueError:
            if self.aliases.get(alias):
                raise
        match = re.fullmatch(r'([A-Z]+)(\d{3,4})(F?)', symbol.upper())
        if not match:
            raise ValueError('unresolved_real_contract_code')
        product,digits,suffix=match.groups()
        month=int(digits[-2:])
        years=[year for year in range(int(day[:4])-1,int(day[:4])+4) if str(year)[-(len(digits)-2):]==digits[:-2]]
        if len(years)!=1 or not 1<=month<=12:
            raise ValueError('ambiguous_contract_year')
        product += '_F' if suffix else ''
        identity=f'{exchange}.{product}.{years[0]:04d}{month:02d}'
        if identity not in self.contracts:
            row=dict(contract_epoch_id=identity,exchange=exchange,product=product,contract_yyyymm=f'{years[0]:04d}{month:02d}',
                listed_date=None,delisted_date=None,maturity_date=None,metadata_status='current_or_official_symbol_only')
            self.contracts[identity]=row
            self.db.execute('INSERT INTO contracts VALUES(?,?,?,?,?,?,?,?)',tuple(row.values()))
        return identity

    def rqalpha(self):
        import h5py
        source='rqalpha'
        self.source(source,'rqalpha',INPUT/'rqalpha/futures.h5')
        with h5py.File(INPUT/'rqalpha/futures.h5','r') as h:
            for key, meta in sorted(self.meta_by_rq.items()):
                if key not in h:
                    continue
                for i,r in enumerate(h[key][:]):
                    ymd=str(int(r['datetime'])//1000000)
                    day=ymd[:4]+'-'+ymd[4:6]+'-'+ymd[6:8]
                    matched=[r for r in self.units['rqalpha']['rules'] if meta['exchange'] in r['exchanges'] and r['start']<=day<=r['end']]
                    factors=(matched[0]['volume_factor'],matched[0]['close_oi_factor']) if len(matched)==1 else (None,None)
                    self.add(source,meta['contract_epoch_id'],key,day,
                        {**{k:float(r[k]) for k in ['open','high','low','close','volume']},'close_oi':float(r['open_interest']),'open_oi':None},
                        factors,100,{'key':key,'row':i})
        self.db.commit()
        print('RQ bone loaded',flush=True)

    def official(self):
        manifest=load_json(INPUT/'other_exchanges/normalized/official_normalization_manifest.json')
        for item in manifest['sources']:
            source='official:'+item['source_id']; path=Path(item['normalized_path'])
            self.source(source,'official',path,item['raw_path'])
            with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
                for line,r in enumerate(csv.DictReader(f),2):
                    identity=r['exchange']+'.'+r['product'].upper()+'.'+r['contract_yyyymm']
                    if identity not in self.contracts:
                        try:
                            identity=self.current_identity(r['exchange'],r['source_symbol'],r['date'])
                        except ValueError:
                            identity=''
                    regime=r['unit_regime']
                    factor=self.units['official']['accepted_regime_factors'].get(regime)
                    self.add(source,identity,r['source_symbol'],r['date'],
                        {**{k:number(r[k]) for k in ['open','high','low','close','volume']},'close_oi':number(r['open_interest']),'open_oi':None},
                        (factor,factor),200,{'row':line,'source_member':r['source_member'],'raw_row':r['source_row']})
            self.db.commit()
        print('official reference rows loaded',flush=True)

    def tq(self, recent=False):
        paths=sorted((INPUT/'tq_latest/daily35').glob('*.csv')) if recent else sorted((ROOT/'examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04').glob('*/*.csv'))
        for path in paths:
            if recent:
                exchange,symbol=path.stem.split('_',1)
            else:
                exchange,symbol=path.parent.name,path.stem
            source=('recent_tq:' if recent else 'old_tq:')+exchange+'.'+symbol
            self.source(source,'recent_tq' if recent else 'old_tq',path)
            pending={}; conflicts=set()
            with path.open(encoding='utf-8-sig',newline='') as f:
                for line,r in enumerate(csv.DictReader(f),2):
                    day=r.get('trade_date','')[:10]
                    raw={k:number(r.get(k)) for k in ['open','high','low','close','volume','open_oi','close_oi']}
                    locator={'row':line}
                    try:
                        date.fromisoformat(day)
                        identity=self.current_identity(exchange,symbol,day)
                    except ValueError:
                        self.reject(source,'',day,'unresolved_contract_identity',locator,raw)
                        continue
                    key=(identity,day)
                    if key in pending:
                        if raw != pending[key][0]:
                            conflicts.add(key)
                        else:
                            self.reject(source,identity,day,'identical_source_duplicate',locator,raw)
                    else:
                        pending[key]=(raw,locator)
            for (identity,day),(raw,locator) in pending.items():
                if (identity,day) in conflicts:
                    self.reject(source,identity,day,'conflicting_source_duplicate',locator,raw)
                    continue
                # Verified ordinary TQ source rows are single-sided, including its historical CSV.
                rule=self.units['recent_tq' if recent else 'old_tq']
                self.add(source,identity,symbol,day,raw,(rule['volume_factor'],rule['close_oi_factor']),400 if recent else 300,locator)
        self.db.commit()
        print('recent' if recent else 'old','TQ loaded',flush=True)

    def finish(self):
        self.excluded_file.close(); self.diff_file.close()
        self.db.execute('CREATE INDEX daily_bars_date ON daily_bars(trade_date)')
        self.db.commit()
        groups=self.db.execute('SELECT exchange,COUNT(*),COUNT(DISTINCT contract_epoch_id),SUM(legacy108_row_usable),MIN(trade_date),MAX(trade_date) FROM daily_bars GROUP BY exchange').fetchall()
        selected_sources=self.db.execute('SELECT s.family,COUNT(*),SUM(d.legacy108_row_usable) FROM daily_bars d JOIN sources s USING(source_id) GROUP BY s.family').fetchall()
        csvroot=OUT/'csv'
        inventory=[]
        for (identity,) in self.db.execute('SELECT DISTINCT contract_epoch_id FROM daily_bars'):
            exchange,product,month=identity.split('.')
            target=csvroot/exchange/(product+month+'.csv');target.parent.mkdir(parents=True,exist_ok=True)
            header=['trade_date','datetime','open','high','low','close','volume','open_oi','close_oi',
                'contract_epoch_id','open_oi_status','legacy108_row_usable','source_id','volume_factor','oi_factor']
            count=complete=0
            with target.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=header,lineterminator='\n');writer.writeheader()
                for row in self.db.execute('SELECT trade_date,open,high,low,close,volume,open_oi,close_oi,open_oi_status,legacy108_row_usable,source_id,volume_factor,oi_factor FROM daily_bars WHERE contract_epoch_id=? ORDER BY trade_date',(identity,)):
                    record=dict(zip(['trade_date','open','high','low','close','volume','open_oi','close_oi','open_oi_status','legacy108_row_usable','source_id','volume_factor','oi_factor'],row))
                    record.update(datetime=record['trade_date']+' 00:00:00+08:00',contract_epoch_id=identity)
                    writer.writerow(record);count+=1;complete+=record['legacy108_row_usable']
            inventory.append({'contract_epoch_id':identity,'rows':count,'legacy108_rows':complete,'path':str(target.relative_to(OUT)),'sha256':digest(target)})
        self.db.close();self.temporary.replace(self.final)
        summary=dict(generated_at=datetime.now().astimezone().isoformat(),scope_start=START,scope_end=END,
            db_path=str(self.final),db_sha256=digest(self.final),
            by_exchange=[dict(zip(['exchange','selected_rows','contracts','legacy108_rows','first_date','last_date'],r)) for r in groups],
            by_selected_source=[dict(zip(['family','selected_rows','legacy108_rows'],r)) for r in selected_sources],
            selected_rows=sum(r[1] for r in groups),legacy108_row_usable=sum(r[3] for r in groups),
            csv_files=len(inventory),cross_source_disagreements=self.difference_count,source_stats=dict(self.stats),
            quantity_unit='single_sided_contracts',training_samples_generated=0,model_fits=0,
            main_database_writes=0,orders=0,unit_contract_sha256=digest(OUT/'unit_contract.json'))
        (OUT/'cleaning_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        (OUT/'csv_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:v for k,v in summary.items() if k!='source_stats'},ensure_ascii=False,indent=2),flush=True)


def main():
    units=load_json(OUT/'unit_contract.json')
    if not units.get('cleaner_rule_approved',False):
        raise RuntimeError('independent_units_contract_not_approved')
    for evidence in units['evidence_bindings']:
        if digest(evidence['path'])!=evidence['sha256']:
            raise RuntimeError('unit_evidence_drift:'+evidence['path'])
    protocol={
        'scope_start':START,'scope_end':END,'db_path':str(OUT/'clean_daily.sqlite'),
        'quantity_unit':'single_sided_contracts','unit_contract_path':str(OUT/'unit_contract.json'),
        'unit_contract_sha256':digest(OUT/'unit_contract.json'),
        'quantity_conflict_path':str(OUT/'stage266_units_exceptions.json'),
        'quantity_conflict_sha256':digest(OUT/'stage266_units_exceptions.json'),
        'source_priority':{'recent_tq':400,'old_tq':300,'official':200,'rqalpha':100},
        'whole_source_row_only':True,'zero_volume_excluded_from_traded_history':True,
        'open_oi':'source observed only; no fill, no shift',
        'train_eligible':'row field compatibility only; not a 120/60 mature training sample',
        'calendar_path':str(INPUT/'rqalpha/trading_dates.npy'),
        'calendar_sha256':digest(INPUT/'rqalpha/trading_dates.npy'),
        'metadata_path':str(INPUT/'rqalpha/futures_metadata.json'),
        'metadata_sha256':digest(INPUT/'rqalpha/futures_metadata.json'),
        'cleaner_source_sha256':digest(Path(__file__)),
        'before_integrity_path':str(INPUT/'primary_integrity.json'),
    }
    (OUT/'contract.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
    builder=Builder(units)
    builder.rqalpha();builder.official();builder.tq();builder.tq(recent=True);builder.finish()


if __name__=='__main__':
    main()
