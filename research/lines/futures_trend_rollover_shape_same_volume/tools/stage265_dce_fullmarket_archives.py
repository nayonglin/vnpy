"""Credential-free DCE annual archive recovery, discovery and normalization.

Only explicit public GETs; fetched code is never run. All output stays in this
research line. Native volume and closing OI remain unscaled because annual
archive units must be established independently of modern website units.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, datetime
import hashlib
from html import unescape
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from threading import local
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import requests

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUTPUT = LINE / 'outputs/stage265_deep_daily/dce'
SNAPSHOT = OUTPUT / 'raw/zjp_dce_historical_page.html'
COMMIT = 'cbef635dcc8f5f16384dc2eba1debfe05df1fdf0'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
NAMES = {'玉米':'c', '玉米淀粉':'cs', '豆一':'a', '黄大豆1号':'a', '豆二':'b', '黄大豆2号':'b',
         '豆粕':'m','豆油':'y','棕榈油':'p','纤维板':'fb','胶合板':'bb','鸡蛋':'jd','粳米':'rr',
         '聚乙烯':'l','线型低密度聚乙烯':'l','聚氯乙烯':'v','聚丙烯':'pp','焦炭':'j','焦煤':'jm',
         '铁矿石':'i','乙二醇':'eg','苯乙烯':'eb','液化石油气':'pg','生猪':'lh'}
HEADER = {'instrument':'合约','date':'日期','open':'开盘价','high':'最高价','low':'最低价',
          'close':'收盘价','settlement':'结算价','volume':'成交量','close_open_interest':'持仓量'}
NUMERIC = ('open','high','low','close','settlement','volume','close_open_interest')
FIELDS = ('contract_epoch_id','vt_symbol','product','contract_yyyymm','date',*NUMERIC,
          'source_year','source_key','raw_member','raw_row','volume_unit','oi_unit','oi_timing')

def stamp():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

def discover():
    html = SNAPSHOT.read_text()
    years = [int(x) for x in re.findall(r'<option[^>]*value="(\d{4})"', html)]
    blocks = re.findall(r'<ul class="cate_sel clearfix"[^>]*>(.*?)</ul>', html, re.S)
    if len(years) != len(blocks) or len(set(years)) != len(years):
        raise ValueError('ambiguous_year_block_binding')
    entries = []
    for year, block in zip(years, blocks):
        if not 2006 <= year <= 2022:
            continue
        for relative, name in re.findall(r'rel="([^"]+)">([^<>]+)</label>', block):
            name = unescape(name.strip())
            if '期权' in name:
                continue
            product = NAMES[name]
            if not relative.startswith('/dalianshangpin/resource/cms/'):
                raise ValueError('unexpected_archive_host_or_path')
            key = f'dce_{year}_{product}'
            legacy = OUTPUT / f'raw/official_{product}_{year}.response'
            dest = legacy if legacy.exists() else OUTPUT / f'official_raw/{year}/{product}.response'
            entries.append({'key':key,'year':year,'product':product+'.DCE','label':name,
                'url':'http://www.dce.com.cn'+relative,'relative_path':relative,
                'path':str(dest.relative_to(LINE)), 'source_snapshot_sha256':sha(SNAPSHOT),
                'source_repository':'https://github.com/zjp-CN/commodity-exchange-zh',
                'source_commit':COMMIT,'source_file':'tests/dce.html'})
    keys = [e['key'] for e in entries]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate_year_product')
    manifest = {'generated_at':stamp(),'scope':'all listed DCE futures, excludes options',
        'snapshot_years':years,'expected_years':list(range(2006,2023)),
        'year_product_counts':dict(sorted(Counter(str(e['year']) for e in entries).items())),
        'candidate_count':len(entries),'entries':entries,
        'limitation':'snapshot ends 2022; not evidence of 2023-2026 coverage',
        'license':'Repository code license is not a market-data redistribution license; raw is local research only.'}
    save(OUTPUT/'official_fullmarket_manifest.json', manifest)
    return manifest

def identify(path):
    data = path.read_bytes()
    if data[:2] == b'PK':
        with ZipFile(io.BytesIO(data)) as z:
            if '[Content_Types].xml' in z.namelist(): return 'xlsx'
            members=[n for n in z.namelist() if not n.endswith('/')]
            if members and all(z.read(n)[:2]==b'PK' for n in members):
                return 'zip_xlsx'
            return 'zip_csv'
    if data[:8] == bytes.fromhex('d0cf11e0a1b11ae1'):
        return 'xls'
    return 'unrecognized'

def fetch(entries, pause, limit, workers):
    logpath = OUTPUT/'official_fullmarket_downloads.json'
    log = json.loads(logpath.read_text()) if logpath.exists() else {'entries':{}}
    thread_state = local()
    def fetch_one(spec):
        path = LINE/spec['path']
        entry = {'key':spec['key'],'url':spec['url'],'method':'GET','authenticated':False,
                 'path':spec['path'],'checked_at':stamp()}
        if path.exists() and identify(path) in ('xlsx','zip_csv','zip_xlsx','xls'):
            entry.update(status='existing_valid_raw_reused_no_network',bytes=path.stat().st_size,
                         sha256=sha(path), actual_format=identify(path))
        else:
            time.sleep(pause)
            try:
                if not hasattr(thread_state,'session'): thread_state.session = requests.Session()
                with thread_state.session.get(spec['url'],stream=True,timeout=(10,35),allow_redirects=True) as response:
                    entry.update(http_status=response.status_code, response_url=response.url,
                                 content_type=response.headers.get('content-type',''), started_at=stamp())
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data)>limit:
                            raise ValueError('archive_above_size_cap')
                    if response.status_code != 200:
                        raise ValueError('http_status_'+str(response.status_code))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix('.part')
                    tmp.write_bytes(data)
                    fmt = identify(tmp)
                    if fmt == 'unrecognized':
                        tmp.replace(path.with_suffix('.unrecognized'))
                        raise ValueError('not_archive_quarantined')
                    tmp.replace(path)
                    entry.update(status='downloaded',bytes=len(data),sha256=sha(path),actual_format=fmt)
            except (requests.RequestException, ValueError) as error:
                entry.update(status='failed',error_type=type(error).__name__,error=str(error)[:250])
        entry['completed_at'] = stamp()
        return entry
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(fetch_one,spec) for spec in entries]
        for future in as_completed(futures):
            entry=future.result()
            log['entries'][entry['key']] = entry
            log['updated_at'] = stamp()
            save(logpath,log)
            print(json.dumps({k:entry.get(k) for k in ('key','status','bytes','actual_format','error')},ensure_ascii=False),flush=True)

def xml_rows(archive):
    strings = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
        strings = [''.join(n.text or '' for n in item.findall('.//s:t',NS)) for item in root.findall('s:si',NS)]
    sheets = sorted(n for n in archive.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+.xml',n))
    for sheet in sheets:
        root = ET.fromstring(archive.read(sheet))
        for number, row in enumerate(root.findall('.//s:sheetData/s:row',NS),1):
            number = int(row.attrib.get('r', number))
            vals = []
            for cell in row.findall('s:c',NS):
                address = re.match(r'([A-Z]+)',cell.attrib.get('r',''))
                if address is None:
                    raise ValueError('xlsx_cell_reference_missing')
                index = 0
                for c in address[1]: index = index*26+ord(c)-64
                while len(vals)<index: vals.append('')
                value = cell.find('s:v',NS)
                value = value.text if value is not None else ''
                if cell.attrib.get('t')=='s': value = strings[int(value)] if value else ''
                if cell.attrib.get('t')=='inlineStr': value = ''.join(n.text or '' for n in cell.findall('.//s:t',NS))
                vals[index-1] = value
            yield sheet, number, vals

def archive_rows(path):
    fmt = identify(path)
    if fmt == 'xls':
        import xlrd
        book = xlrd.open_workbook(path)
        for sheet in book.sheets():
            for i in range(sheet.nrows): yield sheet.name,i+1,sheet.row_values(i)
    else:
        with ZipFile(path) as archive:
            if fmt == 'xlsx':
                yield from xml_rows(archive)
            elif fmt == 'zip_xlsx':
                for name in archive.namelist():
                    if name.endswith('/'): continue
                    with ZipFile(io.BytesIO(archive.read(name))) as nested:
                        for member,number,vals in xml_rows(nested): yield name+'!'+member,number,vals
            elif fmt == 'zip_csv':
                for name in archive.namelist():
                    if name.endswith('/'):
                        continue
                    body = archive.read(name)
                    for encoding in ('utf-8-sig','gb18030'):
                        try: body = body.decode(encoding);break
                        except UnicodeDecodeError: pass
                    if isinstance(body,bytes): raise ValueError('undecodable_csv')
                    for number,row in enumerate(csv.reader(io.StringIO(body)),1): yield name,number,row
            else: raise ValueError('unrecognized_format')

def value(v):
    if isinstance(v,(float,int)) and v==int(v): return str(int(v))
    return str(v).strip()

def normalize_file(spec):
    path = LINE/spec['path']
    columns, member_prev = None,None
    rows, rejected = [],[]
    header_found = False
    for member,number,vals in archive_rows(path):
        labels = [value(v) for v in vals]
        if member != member_prev: columns=None;member_prev=member
        if all(n in labels for n in HEADER.values()):
            columns = {k:labels.index(n) for k,n in HEADER.items()};header_found=True;continue
        if not columns: continue
        if len(labels)<=max(columns.values()):
            labels += ['']*(max(columns.values())+1-len(labels))
        raw = {k:labels[i] for k,i in columns.items()}
        symbol = raw['instrument'].lower()
        if not symbol or '合计' in symbol or '注' in symbol: continue
        context = {'source_key':spec['key'],'raw_member':member,'raw_row':number,
                   'instrument':symbol,'date':raw['date']}
        try:
            match = re.fullmatch(r'([a-z]+)(\d{2})(\d{2})',symbol)
            if not match: raise ValueError('not_real_contract')
            product,yy,mm = match.groups()
            if product not in set(NAMES.values()): raise ValueError('unknown_dce_product')
            day = raw['date']
            if re.fullmatch(r'\d{8}',day): day = day[:4]+'-'+day[4:6]+'-'+day[6:]
            parsed_day = date.fromisoformat(day)
            if parsed_day.year != spec['year']: raise ValueError('source_year_mismatch')
            delivery = 2000+int(yy)
            if not 1<=int(mm)<=12: raise ValueError('invalid_delivery_month')
            if not 0<=delivery*12+int(mm)-(parsed_day.year*12+parsed_day.month)<=36:
                raise ValueError('delivery_epoch_mismatch')
            numbers = {k:float(raw[k].replace(',','')) for k in NUMERIC}
            if not all(math.isfinite(v) for v in numbers.values()): raise ValueError('nonfinite_numeric')
            if numbers['volume']<0 or numbers['close_open_interest']<0: raise ValueError('negative_volume_oi')
            if any(numbers[k]<=0 for k in ('open','high','low','close')):
                raise ValueError('no_trade_nonpositive_ohlc' if numbers['volume']==0 else 'nonpositive_ohlc')
            op,hi,lo,cl=(numbers[k] for k in ('open','high','low','close'))
            if not lo<=min(op,cl)<=max(op,cl)<=hi: raise ValueError('inconsistent_ohlc')
            vt = symbol+'.DCE';yyyymm=str(delivery)+mm
            rows.append({'contract_epoch_id':vt+'@'+yyyymm,'vt_symbol':vt,'product':product+'.DCE',
                'contract_yyyymm':yyyymm,'date':day,**numbers,'source_year':spec['year'],'source_key':spec['key'],
                'raw_member':member,'raw_row':number,'volume_unit':'native_archive_hands_unscaled',
                'oi_unit':'native_archive_hands_unscaled','oi_timing':'end_of_trading_day_close'})
        except (ValueError,TypeError) as error:
            rejected.append({**context,'reason':str(error)})
    if not header_found: raise ValueError('required_header_not_found')
    return rows,rejected

def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)

def normalize(entries):
    summary={'generated_at':stamp(),'archives':[],'missing_archives':[],'all_backtest_training_database_write_calls':0}
    allrows=[];allreject=[]
    for spec in entries:
        path=LINE/spec['path']
        if not path.exists(): summary['missing_archives'].append(spec['key']);continue
        try:
            rows,rejected=normalize_file(spec)
        except Exception as error:
            summary['archives'].append({'key':spec['key'],'status':'parse_failed','error':str(error)});continue
        allrows.extend(rows);allreject.extend(rejected)
        dest=OUTPUT/f'normalized/{spec["year"]}/{spec["product"].split(".")[0]}.csv'
        write_csv(dest,rows,FIELDS)
        summary['archives'].append({'key':spec['key'],'status':'normalized','source_sha256':sha(path),
            'actual_format':identify(path),'valid_rows':len(rows),'rejected_rows':len(rejected),
            'actual_product_counts':dict(Counter(r['product'] for r in rows)),
            'label_mismatch_valid_rows':sum(r['product']!=spec['product'] for r in rows),
            'reasons':dict(Counter(r['reason'] for r in rejected)),'contract_count':len({r['vt_symbol'] for r in rows}),
            'date_min':min((r['date'] for r in rows),default=None),'date_max':max((r['date'] for r in rows),default=None),
            'normalized_path':str(dest.relative_to(LINE)),'normalized_sha256':sha(dest)})
    groups=defaultdict(list)
    for row in allrows: groups[(row['contract_epoch_id'],row['date'])].append(row)
    conflict=[{'key':list(k),'rows':v} for k,v in groups.items() if len({tuple(r[n] for n in NUMERIC) for r in v})>1]
    unique=[v[0] for v in groups.values() if len({tuple(r[n] for n in NUMERIC) for r in v})==1]
    unique.sort(key=lambda r:(r['contract_epoch_id'],r['date']))
    deduplicated_path=OUTPUT/'official_fullmarket_daily.csv'
    write_csv(deduplicated_path,unique,FIELDS)
    summary.update(valid_raw_rows=len(allrows),unique_valid_rows=len(unique),
        contract_count=len({r['contract_epoch_id'] for r in unique}),rejected_rows=len(allreject),
        reasons=dict(Counter(r['reason'] for r in allreject)),duplicate_extra_rows=len(allrows)-len(groups),
        conflicting_keys=len(conflict),date_min=min((r['date'] for r in unique),default=None),
        date_max=max((r['date'] for r in unique),default=None),
        normalized_unique_path=str(deduplicated_path.relative_to(LINE)),
        normalized_unique_sha256=sha(deduplicated_path),
        row_identity_policy='Actual real-contract product takes precedence over archive label; identical duplicates collapse, conflicts fully quarantine.',
        volume_oi_policy='native archive values retained; side convention unresolved, do not automatically halve at 2020',
        oi_policy='closing OI; not interchangeable with TQ open_oi')
    by_contract=defaultdict(list)
    for row in unique: by_contract[row['contract_epoch_id']].append(row)
    contract_rows=[]
    for epoch,group in sorted(by_contract.items()):
        contract_rows.append({'contract_epoch_id':epoch,'vt_symbol':group[0]['vt_symbol'],
            'product':group[0]['product'],'contract_yyyymm':group[0]['contract_yyyymm'],
            'date_min':min(r['date'] for r in group),'date_max':max(r['date'] for r in group),
            'valid_days':len(group),'source_years':','.join(str(y) for y in sorted({r['source_year'] for r in group}))})
    write_csv(OUTPUT/'official_fullmarket_contracts.csv',contract_rows,
        ('contract_epoch_id','vt_symbol','product','contract_yyyymm','date_min','date_max','valid_days','source_years'))
    save(OUTPUT/'official_fullmarket_normalization.json',summary)
    save(OUTPUT/'official_fullmarket_rejected.json',allreject)
    save(OUTPUT/'official_fullmarket_conflicts.json',conflict)
    compare_database(unique)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('archives','missing_archives')},ensure_ascii=False),flush=True)

def compare_database(rows):
    database=ROOT/'.vntrader/database.db'
    before=database.stat()
    connection=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
    connection.row_factory=sqlite3.Row
    existing=defaultdict(list)
    for r in connection.execute("SELECT symbol,datetime,open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE exchange='DCE' AND interval='d' AND datetime>='2006-01-01' AND datetime<'2023-01-01'"):
        existing[(r['symbol'].lower()+'.DCE',r['datetime'][:10])].append(dict(r))
    connection.close()
    yearly=defaultdict(lambda:{'overlap_unique':0,'ohlc_equal':0,'ohlc_mismatch':0,'database_duplicate_keys':0,
                              'archive_volume_over_database':Counter(),'archive_close_oi_over_database':Counter(),'new_days':0})
    diffs=[]
    for row in rows:
        out=yearly[str(row['source_year'])];old=existing.get((row['vt_symbol'],row['date']),[])
        if not old:out['new_days']+=1;continue
        if len(old)!=1:out['database_duplicate_keys']+=1;continue
        out['overlap_unique']+=1;old=old[0]
        match=all(math.isclose(row[k],old[k+'_price'],abs_tol=1e-8,rel_tol=0) for k in ('open','high','low','close'))
        out['ohlc_equal' if match else 'ohlc_mismatch']+=1
        if not match and len(diffs)<100:diffs.append({'source':row,'database':old})
        for new,previous,field in [('volume','volume','archive_volume_over_database'),('close_open_interest','open_interest','archive_close_oi_over_database')]:
            if old[previous]>0:out[field][str(round(row[new]/old[previous],6))]+=1
    after=database.stat()
    save(OUTPUT/'official_fullmarket_database_overlap.json',{'generated_at':stamp(),'database_open_mode':'ro',
        'database_stat_unchanged':before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,
        'by_year':dict(yearly),'ohlc_difference_examples':diffs,
        'oi_limitation':'Database importer uses TQ open_oi; archive closing OI ratios do not establish side units.',
        'no_merge_performed':True})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['discover','fetch','normalize'])
    parser.add_argument('--years',nargs='*',type=int)
    parser.add_argument('--products',nargs='*')
    parser.add_argument('--pause',type=float,default=0.6)
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    parser.add_argument('--max-bytes',type=int,default=32*1024*1024)
    args=parser.parse_args()
    manifest=discover()
    entries=[e for e in manifest['entries'] if (not args.years or e['year'] in args.years) and (not args.products or e['product'].split('.')[0] in args.products)]
    if args.command=='fetch':fetch(entries,args.pause,args.max_bytes,args.workers)
    if args.command=='normalize':normalize(entries)
    if args.command=='discover':print(json.dumps({k:v for k,v in manifest.items() if k!='entries'},ensure_ascii=False))

if __name__=='__main__':main()
