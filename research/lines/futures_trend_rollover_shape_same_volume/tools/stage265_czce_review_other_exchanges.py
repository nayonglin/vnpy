"""Independent offline audit of official archives and all normalized reference rows.

No network, full XLS reparse, data repair, source-unit conversion or database writes.
"""
from collections import Counter,defaultdict
import csv,gzip,hashlib,io,json,math,re
from datetime import date,datetime
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo
import xlrd

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
BASE=LINE/'outputs/stage265_deep_daily/other_exchanges'
OUT=LINE/'outputs/stage265_deep_daily/czce'
FIELDS=('open','high','low','close','volume','open_interest')
INE={'sc','nr','lu','bc','ec'}
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
ALIASES={'instrument':['合约','合约代码'],'date':['日期','交易日期'],'open':['开盘价','今开盘'],'high':['最高价'],'low':['最低价'],'close':['收盘价','今收盘'],'volume':['成交量'],'open_interest':['持仓量']}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def resolve(value):
    path=Path(value)
    return path if path.is_absolute() else ROOT/path


def readrows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as stream:
        yield from csv.DictReader(stream)


def text(value):
    if isinstance(value,(int,float)) and math.isfinite(value) and value==int(value):return str(int(value))
    return str(value).strip()


def number(value):
    s=text(value).replace(',','')
    if s.lower() in {'','--','-','none','nan','null'}:return None
    return float(s)


def sample_annual(rec,row):
    with zipfile.ZipFile(resolve(rec['path'])) as z:body=z.read(row['source_member'])
    wanted=int(row['source_row']);rawrows={}
    if body[:8]==bytes.fromhex('d0cf11e0a1b11ae1'):
        book=xlrd.open_workbook(file_contents=body,on_demand=True)
        sheet=book.sheet_by_name(row['source_sheet'])
        for n in range(min(sheet.nrows,max(wanted,25))):rawrows[n+1]=sheet.row_values(n)
        book.release_resources()
    else:
        with zipfile.ZipFile(io.BytesIO(body)) as inner:
            strings=[]
            if 'xl/sharedStrings.xml' in inner.namelist():
                root=ET.fromstring(inner.read('xl/sharedStrings.xml'))
                strings=[''.join(t.text or '' for t in item.iter(NS+'t')) for item in root]
            wb=ET.fromstring(inner.read('xl/workbook.xml'))
            sheet=next(s for s in wb.iter(NS+'sheet') if s.attrib['name']==row['source_sheet'])
            rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            rel=ET.fromstring(inner.read('xl/_rels/workbook.xml.rels'))
            target=next(x.attrib['Target'] for x in rel if x.attrib['Id']==rid)
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            with inner.open(target) as stream:
                for _,elem in ET.iterparse(stream,events=('end',)):
                    if elem.tag!=NS+'row':continue
                    n=int(elem.attrib['r']);values=[]
                    for cell in elem.findall(NS+'c'):
                        letters=re.match('[A-Z]+',cell.attrib['r'])[0];col=0
                        for letter in letters:col=col*26+ord(letter)-64
                        while len(values)<col:values.append('')
                        v=cell.find(NS+'v');value=v.text if v is not None and v.text is not None else ''
                        if cell.attrib.get('t')=='s':value=strings[int(value)] if value else ''
                        elif cell.attrib.get('t')=='inlineStr':value=''.join(t.text or '' for t in cell.iter(NS+'t'))
                        values[col-1]=value
                    rawrows[n]=values;elem.clear()
                    if n>=max(wanted,25):break
    columns=None
    for n,values in sorted(rawrows.items()):
        labels=[text(v) for v in values]
        found={key:next((labels.index(a) for a in names if a in labels),None) for key,names in ALIASES.items()}
        if all(found[k] is not None for k in ALIASES):columns=found;break
    if columns is None:raise AssertionError('sample_header_unresolved:'+rec['source_id'])
    values=rawrows[wanted]
    raw={k:values[v] if v<len(values) else '' for k,v in columns.items()}
    # The first accepted source row in each sampled sheet has an explicit symbol.
    assert text(raw['instrument']).lower()==row['source_symbol'].lower(),(rec['source_id'],'symbol',raw['instrument'],row['source_symbol'])
    d=text(raw['date']);assert d==row['date'].replace('-','')
    for field in FIELDS:assert number(raw[field])==float(row[field]),(rec['source_id'],field,raw[field],row[field])
    return {'source_id':rec['source_id'],'kind':'original_spreadsheet_cell_sample','source_member':row['source_member'],'source_sheet':row['source_sheet'],'source_row':wanted,'date':row['date'],'symbol':row['source_symbol'],'field_cells_verified':6}


def sample_other(rec,row):
    if rec['exchange']=='CFFEX':
        with zipfile.ZipFile(resolve(rec['path'])) as z:body=z.read(row['source_member']).decode('gb18030')
        rows=list(csv.DictReader(io.StringIO(body)));raw={str(k).strip():v for k,v in rows[int(row['source_row'])-2].items()}
        for field in FIELDS:
            value=next(raw[a] for a in ALIASES[field] if a in raw)
            assert number(value)==float(row[field]),(rec['source_id'],field)
        assert text(next(raw[a] for a in ALIASES['instrument'] if a in raw)).upper()==row['source_symbol'].upper()
        assert row['source_member'][:8]==row['date'].replace('-','')
    else:
        raw=json.loads(resolve(rec['path']).read_text())
        assert str(raw['report_date'])==row['date'].replace('-','')
        item=raw['o_curinstrument'][int(row['source_row'])-1]
        assert str(item['PRODUCTGROUPID']).strip()+str(item['DELIVERYMONTH']).strip()==row['source_symbol']
        for field,key in zip(FIELDS,['OPENPRICE','HIGHESTPRICE','LOWESTPRICE','CLOSEPRICE','VOLUME','OPENINTEREST']):
            assert number(item[key])==float(row[field]),(rec['source_id'],field)
    return {'source_id':rec['source_id'],'kind':'original_csv_or_json_row_sample','date':row['date'],'symbol':row['source_symbol'],'source_row':int(row['source_row']),'field_cells_verified':6}


def main():
    manifests=['official_archive_sources_manifest.json','cffex_month_sources_manifest.json','official_tail_sources_manifest.json']
    records=[];manifest_hash={}
    for name in manifests:
        path=BASE/name;manifest_hash[name]=sha(path);records.extend(json.loads(path.read_text())['sources'])
    byid={r['source_id']:r for r in records};assert len(byid)==len(records)==247
    norm_path=BASE/'normalized/official_normalization_manifest.json';norm=json.loads(norm_path.read_text())
    catalog=json.loads((BASE/'official_reference_catalog.json').read_text())
    assert catalog['source_manifests']==manifest_hash
    assert catalog['normalization_manifest_sha256']==sha(norm_path)
    assert set(byid)=={r['source_id'] for r in norm['sources']}
    raw_verified=[];zipcount=0;jsoncount=0;reused=[]
    for rec in records:
        path=resolve(rec['path']);assert path.exists()
        assert path.stat().st_size==rec['bytes'] and sha(path)==rec['sha256'],('raw_hash',rec['source_id'])
        if rec.get('status')=='reused_stage264':reused.append(rec['source_id']);assert 'stage264_pre_main_daily/shfe_official/raw_years' in str(path)
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                assert z.testzip() is None
                info=z.infolist();assert len(info)==len({x.filename for x in info})
                stated={x['name']:(x['bytes'],x['crc32'].lower()) for x in rec['members']}
                actual={x.filename:(x.file_size,f'{x.CRC:08x}') for x in info if not x.is_dir()}
                assert stated==actual,('zip_member_manifest',rec['source_id'])
            zipcount+=1
        else:
            data=json.loads(path.read_text());assert str(data['report_date'])==rec['date'];assert len(data['o_curinstrument'])==rec['record_count'];jsoncount+=1
        raw_verified.append({'source_id':rec['source_id'],'sha256':rec['sha256'],'bytes':rec['bytes']})
    assert zipcount==233 and jsoncount==14 and len(reused)==6
    keys=set();no_trade=set();rejects=set();product=defaultdict(lambda:{'rows':0,'first':'9999','last':'0000','months':set()});units=Counter();latest=defaultdict(lambda:{'accepted':set(),'no_trade':set(),'rejected':set()});exchange=Counter();contract=defaultdict(set)
    zero_good=0;no_trade_rows=0;rejected_rows=0;samples=[];sampleids={'SHFE_futures_2002','SHFE_futures_2014','SHFE_futures_2019','SHFE_futures_2024','SHFE_futures_2026','INE_futures_2018','INE_futures_2024','INE_futures_2026','CFFEX_futures_options_201004','CFFEX_futures_options_202610','SHFE_daily_20261016','INE_daily_20261016'}
    for source in norm['sources']:
        rec=byid[source['source_id']]
        assert source['raw_sha256']==rec['sha256']
        local_count=0
        for prefix in ['normalized','no_trade','rejected']:
            path=resolve(source[prefix+'_path']);assert sha(path)==source[prefix+'_sha256'],('normalized_hash',source['source_id'],prefix)
            for row in readrows(path):
                assert row['source_id']==source['source_id'] and row['exchange']==source['exchange']
                d=date.fromisoformat(row['date']);assert d<=date(2026,10,16)
                match=re.fullmatch('([A-Za-z]{1,3})([0-9]{4})',row['source_symbol']);assert match
                assert match[1].lower()==row['product'].lower()
                month=row['contract_yyyymm'];assert month[2:]==match[2]
                assert 1<=int(month[-2:])<=12
                assert row['oi_timing']=='close_end_of_day'
                assert not(row['exchange']=='SHFE' and row['product'].lower() in INE)
                assert not(row['exchange']=='INE' and row['product'].lower() not in INE)
                key=(row['exchange'],row['product'].lower(),month,row['date'])
                group=(row['exchange'],row['product'])
                if row['date']=='2026-10-16':latest[group][{'normalized':'accepted','no_trade':'no_trade','rejected':'rejected'}[prefix]].add(row['source_symbol'])
                if prefix=='no_trade':
                    assert float(row['volume'])==0;no_trade.add(key);no_trade_rows+=1;continue
                if prefix=='rejected':rejects.add(key);rejected_rows+=1;assert row['row_quality'] not in {'valid_ohlc','no_trade_with_valid_ohlc'};continue
                assert key not in keys,('duplicate',key);keys.add(key)
                values=[float(row[f]) for f in FIELDS];assert all(math.isfinite(x) for x in values)
                op,hi,lo,cl,v,oi=values
                assert min(op,hi,lo,cl)>0 and lo<=min(op,cl)<=max(op,cl)<=hi and min(v,oi)>=0
                assert row['row_quality']==('no_trade_with_valid_ohlc' if v==0 else 'valid_ohlc')
                zero_good+=int(v==0);local_count+=1;exchange[row['exchange']]+=1;units[row['unit_regime']]+=1
                contract[row['exchange']].add((row['product'],month))
                g=product[group];g['rows']+=1;g['first']=min(g['first'],row['date']);g['last']=max(g['last'],row['date']);g['months'].add(month)
                if local_count==1 and source['source_id'] in sampleids:
                    samples.append(sample_other(rec,row) if rec['exchange']=='CFFEX' or '_daily_' in rec['source_id'] else sample_annual(rec,row))
        assert local_count==source['counts']['accepted_rows']
    assert not (keys & rejects)
    assert len(keys)==catalog['ordinary_accepted_rows'] and dict(exchange)==catalog['by_exchange_rows']
    for row in catalog['product_coverage']:
        g=product[row['exchange'],row['product']]
        assert g['rows']==row['rows'] and g['first']==row['min_date'] and g['last']==row['max_date'] and len(g['months'])==row['contract_count']
    census=json.loads((BASE/'latest_trade_date_census.json').read_text())
    for stated in census['products']:
        g=latest[stated['exchange'],stated['product']];union=set.union(*g.values())
        assert union==set(stated['contracts']) and len(union)==stated['ordinary_contract_count']
        assert len(g['accepted'])==stated['accepted_ohlc_contract_count'] and len(g['no_trade'])==stated['zero_trade_contract_count'] and len(g['rejected'])==stated['rejected_ohlc_contract_count']
    latest_exchange={}
    for ex in ['CFFEX','INE','SHFE']:
        groups=[g for (e,p),g in latest.items() if e==ex]
        latest_exchange[ex]={k:sum(len(g[k]) for g in groups) for k in ['accepted','no_trade','rejected']}
        latest_exchange[ex]['ordinary_union']=sum(len(set.union(*g.values())) for g in groups)
    db=ROOT/'.vntrader/database.db';dbsha=sha(db);baseline=json.loads((LINE/'outputs/stage264_pre_main_daily/stage264_summary.json').read_text())['verification']['main_database_sha256'];assert dbsha==baseline
    report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'PASS_isolated_official_download_and_normalization_REFERENCE_ONLY',
        'reviewer':'independent_czce_agent_no_implementer_functions_imported','raw_sources_verified':len(raw_verified),'zip_sha_and_full_crc_verified':zipcount,'json_sha_schema_reportdate_verified':jsoncount,
        'raw_bytes_including_reuse':sum(x['bytes'] for x in raw_verified),'stage264_reused_source_ids':reused,
        'normalized_hash_files_verified':len(norm['sources'])*3,'accepted_rows_read_independently':len(keys),'accepted_zero_volume_rows_flagged':zero_good,
        'no_trade_rows_read':no_trade_rows,'rejected_rows_read':rejected_rows,'no_trade_rejected_key_overlap':len(no_trade&rejects),'accepted_rejected_key_overlap':0,'duplicate_accepted_keys':0,
        'by_exchange_rows':dict(exchange),'contract_epoch_counts':{e:len(s) for e,s in contract.items()},'products':len(product),
        'product_date_ranges':[{'exchange':e,'product':p,'rows':g['rows'],'min_date':g['first'],'max_date':g['last'],'epochs':len(g['months'])} for (e,p),g in sorted(product.items())],
        'latest_20261016_independent_census':latest_exchange,'unit_regime_rows':dict(units),'cross_exchange_mirror_in_accepted_rows':0,
        'raw_coordinate_samples':samples,'sample_cells_verified':sum(s['field_cells_verified'] for s in samples),
        'main_database_sha256':dbsha,'main_database_matches_stage264_baseline':True,'source_manifest_sha256':manifest_hash,'normalization_manifest_sha256':sha(norm_path),
        'download_review':{'P0':0,'P1':0,'verdict':'PASS_requested_SHFE_INE_CFFEX_artifacts_and_latest_date_census'},
        'training_qualification_review':{'P0':0,'P1':2,'verdict':'NOT_QUALIFIED','P1_reasons':['188965 accepted reference rows retain explicitly unknown side units; no conversion/clock/PIT acceptance contract yet','Observed bounds and downloaded official sources do not certify all-market per-contract lifetime metadata or training readiness; GFEX official route remains missing in this source set']},
        'limits':['No full XLS reparse: every saved raw SHA/ZIP CRC and every normalized row was checked; 12 stratified original raw coordinate samples verify 72 numeric cells.',
            'No-trade and rejected datasets overlap by design, so latest/overall coverage uses set unions, not naive counts.',
            'This official reference set covers SHFE/INE/CFFEX; it is not a six-exchange training dataset. Unknown units do not invalidate download success but prevent automatic training acceptance.'],
        'network_requests':0,'raw_or_normalized_mutations':0,'main_database_writes':0,'training_runs':0,'backtest_runs':0}
    path=OUT/'other_exchanges_independent_review.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'raw_coordinate_samples','product_date_ranges','limits'}},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
