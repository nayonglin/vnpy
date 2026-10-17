"""Pinned Work CZCE full-market archive: resumable public GET and sparse normalization.

Never executes remote code, imputes prices, rewrites old product symbols, or
writes a market database. Vendor redistribution rights remain unestablished.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

import requests

from stage265_czce_metadata import normalize_metadata_code

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / 'outputs/stage265_deep_daily'
CZCE = OUT / 'czce'
OPEN = OUT / 'opensource'
COMMIT = 'e8dd9a55b9a30b1e3033fe838724c23fcdd87ad1'
PRODUCTS = 'AP CF CY FG JR LR MA OI PM RI RM RS SF SM SR TA WH ZC'.split()
FIELDS = {'open':'open', 'high':'high', 'low':'low', 'close':'cl', 'volume':'vol', 'open_interest':'oi'}
MIN_DATE, MAX_DATE = '2010-01-01', '2026-10-16'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def write_json(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def write_csv(path, rows, fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def specifications():
    tree=json.loads((OPEN/'ildhj_work_tree.raw').read_text())
    if tree['sha'] != COMMIT:
        raise RuntimeError('tree_commit_mismatch')
    blobs={x['path']:x for x in tree['tree'] if x['type']=='blob'}
    specs=[]
    for product in PRODUCTS:
        for kind,suffix in [('metadata',None),*[(f,s) for f,s in FIELDS.items()]]:
            remote=(f'Futures_Data/cnt_list/{product}.csv' if kind=='metadata' else f'Futures_Data/data_{suffix}/{product}.csv')
            info=blobs[remote]
            local=(CZCE/f'metadata_ildhj/{product}.csv' if kind=='metadata' else OPEN/f'work_{product}_data_{suffix}.raw')
            specs.append({'product_table':product,'field':kind,'repository_path':remote,'path':str(local.relative_to(LINE)),
                'url':f'https://raw.githubusercontent.com/ildhj0116/Work/{COMMIT}/{remote}',
                'commit':COMMIT,'git_blob_sha1':info['sha'],'expected_bytes':info['size']})
    return specs


def fetch():
    CZCE.mkdir(parents=True,exist_ok=True)
    (CZCE/'metadata_ildhj').mkdir(exist_ok=True)
    receipt=CZCE/'work_fullmarket_request_manifest.json'
    old=json.loads(receipt.read_text()) if receipt.exists() else []
    records={x['repository_path']:x for x in old}
    specs=specifications()
    write_json(CZCE/'work_fullmarket_download_spec.json',specs)
    for spec in specs:
        path=LINE/spec['path']
        entry={**spec,'accessed_at':now(),'auth':'none','method':'GET','automatic_retries':0}
        if path.exists():
            body=path.read_bytes()
            entry.update(status='existing_pinned_bytes_no_network',http_status=None)
        else:
            try:
                response=requests.get(spec['url'],timeout=(10,35))
                body=response.content
                entry.update(http_status=response.status_code,response_url=response.url,content_type=response.headers.get('content-type',''))
                if response.status_code != 200:
                    raise ValueError(f'http_{response.status_code}')
                if len(body)>8*1024*1024:
                    raise ValueError('above_size_cap')
                if len(body)!=spec['expected_bytes'] or blob(body)!=spec['git_blob_sha1']:
                    raise ValueError('pinned_blob_or_size_mismatch')
                path.write_bytes(body)
                entry['status']='downloaded_verified'
            except (requests.RequestException,ValueError) as exc:
                entry.update(status='failed_no_retry',error_type=type(exc).__name__,error=str(exc)[:250])
                records[spec['repository_path']]=entry
                write_json(receipt,list(records.values()))
                print(json.dumps({k:entry.get(k) for k in ('repository_path','status','http_status','error')}),flush=True)
                continue
            time.sleep(.8)
        if len(body)!=spec['expected_bytes'] or blob(body)!=spec['git_blob_sha1']:
            raise RuntimeError(f'existing_bytes_do_not_match_pin:{path}')
        entry.update(bytes=len(body),sha256=digest(body),git_blob_match=True,completed_at=now())
        records[spec['repository_path']]=entry
        write_json(receipt,list(records.values()))
        print(json.dumps({k:entry.get(k) for k in ('repository_path','status','bytes')}),flush=True)


def parse_identity(vendor, day, metadata):
    match=re.fullmatch(r'([A-Z]+)([0-9]{3,4})\.CZC',vendor)
    if not match:
        raise ValueError('not_explicit_czce_real_contract')
    product,digits=match.groups()
    if not 1<=int(digits[-2:])<=12:
        raise ValueError('invalid_delivery_month')
    # Metadata supplies the full expiry year. Require one explicit source
    # listing-to-expiry interval; never guess dates or rename old products
    # according to their containing filename.
    candidates=set()
    for identity,records in metadata.items():
        p,delivery=identity
        if p!=f'{product}.CZCE' or int(delivery[-2:])!=int(digits[-2:]):
            continue
        modulus=10 if len(digits)==3 else 100
        if int(delivery[:4])%modulus != int(digits[:-2]):
            continue
        for record in records:
            if record['contract_issue_date_candidate']<=day<=record['last_trade_date_candidate']:
                candidates.add(delivery)
    if len(candidates)!=1:
        raise ValueError('metadata_identity_missing_or_ambiguous')
    delivery=candidates.pop()
    canonical=f'{product}{int(delivery[:4])%10}{delivery[-2:]}.CZCE'
    return f'{canonical}@{delivery}',canonical,f'{product}.CZCE',delivery


def load_metadata():
    groups=defaultdict(list)
    file_report=[]
    for product in PRODUCTS:
        path=CZCE/f'metadata_ildhj/{product}.csv'
        if not path.exists():
            continue
        source=[]
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row_no,raw in enumerate(csv.DictReader(f),2):
                normalized=normalize_metadata_code(raw[''],raw['contract_issue_date'],raw['last_trade_date'])
                row={k:v for k,v in normalized.items() if k!='identity_key'}
                row.update(product=normalized['identity_key'][0],contract_yyyymm=normalized['identity_key'][1],source_table_product=product,source_row=row_no,
                    source_file=str(path.relative_to(LINE)),source_commit=COMMIT,metadata_status='third_party_unverified_candidate',
                    listing_date_officially_certified=False,full_lifetime_certified=False,source_sha256=digest(path.read_bytes()))
                groups[normalized['identity_key']].append(row)
                source.append(row)
        file_report.append({'product_table':product,'rows':len(source),'actual_product_codes':dict(Counter(r['product'] for r in source)),'sha256':digest(path.read_bytes())})
    conflicts={k for k,v in groups.items() if len({(r['contract_issue_date_candidate'],r['last_trade_date_candidate']) for r in v})>1}
    if conflicts:
        raise ValueError('conflicting_metadata_identity')
    return groups,file_report


def read_wide(path):
    cells={}
    columns=set()
    dates=[]
    identical_duplicates=0
    conflicts={}
    with path.open(encoding='utf-8-sig',newline='') as f:
        for row_no,row in enumerate(csv.DictReader(f),2):
            day=row['']
            date.fromisoformat(day)
            dates.append(day)
            for vendor,raw in row.items():
                if not vendor:
                    continue
                columns.add(vendor)
                if raw is None or not raw.strip() or raw.lower()=='nan':
                    continue
                value=float(raw)
                if not math.isfinite(value):
                    raise ValueError('non_finite')
                key=(day,vendor)
                if key in conflicts:
                    conflicts[key].append({'value':value,'row':row_no})
                    continue
                if key in cells:
                    if value==cells[key][0]:
                        identical_duplicates+=1
                    else:
                        conflicts[key]=[{'value':cells[key][0],'row':cells[key][1]},{'value':value,'row':row_no}]
                        del cells[key]
                    continue
                cells[key]=(value,row_no)
    return cells,{'file':str(path.relative_to(LINE)),'sha256':digest(path.read_bytes()),'rows':len(dates),'first_date':min(dates) if dates else None,
        'last_date':max(dates) if dates else None,'columns':len(columns),'nonmissing_cells':len(cells),
        'identical_duplicate_nonmissing_cells_deduplicated':identical_duplicates,
        'conflicting_duplicate_nonmissing_cells_rejected':[{'date':day,'vendor_contract':vendor,'observations':values} for (day,vendor),values in sorted(conflicts.items())]}


def normalize():
    specs=specifications()
    for spec in specs:
        path=LINE/spec['path']
        if not path.exists():
            raise RuntimeError('fetch_not_complete')
        body=path.read_bytes()
        if len(body)!=spec['expected_bytes'] or blob(body)!=spec['git_blob_sha1']:
            raise RuntimeError('source_hash_mismatch')
    metadata,metadata_files=load_metadata()
    metadata_by_product=defaultdict(dict)
    for key,values in metadata.items():
        metadata_by_product[key[0]][key]=values
    records=[r for values in metadata.values() for r in values]
    write_csv(CZCE/'work_fullmarket_metadata.csv',records,list(records[0]))
    all_bars=[]
    reports=[]
    rejections=[]
    missing_by_pattern=Counter()
    unresolved=Counter()
    for table in PRODUCTS:
        field_cells={}
        field_reports=[]
        field_conflicts={}
        for field,suffix in FIELDS.items():
            cells,info=read_wide(OPEN/f'work_{table}_data_{suffix}.raw')
            field_cells[field]=cells
            field_conflicts[field]={(r['date'],r['vendor_contract']) for r in info['conflicting_duplicate_nonmissing_cells_rejected']}
            field_reports.append({'field':field,**info})
        keys=set.union(*(set(x) for x in field_cells.values()),*field_conflicts.values())
        accepted=[]
        rejected=[]
        actual_products=Counter()
        for day,vendor in sorted(keys):
            if day<MIN_DATE or day>MAX_DATE:
                continue
            identity=None
            try:
                product_match=re.match(r'[A-Z]+',vendor)
                subset=metadata_by_product.get(product_match[0]+'.CZCE',{}) if product_match else {}
                identity=parse_identity(vendor,day,subset)
            except ValueError as exc:
                unresolved[str(exc)]+=1
            missing=[f for f,cells in field_cells.items() if (day,vendor) not in cells]
            values={f:cells[(day,vendor)][0] for f,cells in field_cells.items() if (day,vendor) in cells}
            conflicting_fields=[f for f,keys_with_conflicts in field_conflicts.items() if (day,vendor) in keys_with_conflicts]
            reason=None
            if conflicting_fields:
                reason='conflicting_duplicate_required_field'
            elif identity is None and values and all(v==0 for v in values.values()):
                reason='outside_candidate_lifetime_all_present_cells_zero'
            elif missing:
                reason='missing_required_fields'
                missing_by_pattern[','.join(missing)]+=1
            elif min(values[f] for f in ('open','high','low','close'))<=0:
                reason='nonpositive_price'
            elif not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:
                reason='invalid_ohlc_geometry'
            elif min(values['volume'],values['open_interest'])<0:
                reason='negative_volume_or_open_interest'
            elif identity is None:
                reason='unresolved_contract_identity'
            if reason:
                rejected.append({'source_table_product':table,'vendor_contract':vendor,'date':day,'reason':reason,
                    'missing_fields':','.join(missing),'volume_if_present':values.get('volume'),'open_interest_if_present':values.get('open_interest'),
                    'candidate_lifetime_contains_date':identity is not None,'conflicting_fields':','.join(conflicting_fields),
                    'no_trade_blank_prices':identity is not None and values.get('volume')==0 and all(f in missing for f in ('open','high','low','close'))})
                continue
            epoch,vt,product,delivery=identity
            actual_products[product]+=1
            accepted.append({'contract_epoch_id':epoch,'vt_symbol':vt,'product':product,'contract_yyyymm':delivery,'date':day,**values,
                'source_table_product':table,'vendor_contract':vendor,'source':'ildhj0116/Work','source_commit':COMMIT,
                'source_field_rows':json.dumps({f:cells[(day,vendor)][1] for f,cells in field_cells.items()},sort_keys=True),
                'volume_units':'raw_vendor_units_pending_product_specific_official_comparison','oi_clock':'raw_vendor_clock_pending_product_specific_official_comparison',
                'metadata_status':'third_party_unverified_candidate','full_lifetime_certified':False})
        if accepted:
            write_csv(CZCE/f'work_{table}_fullmarket_bars.csv',accepted,list(accepted[0]))
        all_bars.extend(accepted)
        rejections.extend(rejected)
        reports.append({'source_table_product':table,'fields':field_reports,'accepted_rows':len(accepted),'accepted_contract_epochs':len({r['contract_epoch_id'] for r in accepted}),
            'accepted_first_date':min((r['date'] for r in accepted),default=None),'accepted_last_date':max((r['date'] for r in accepted),default=None),
            'actual_product_codes':dict(actual_products),'rejected_rows':len(rejected),'rejected_reasons':dict(Counter(r['reason'] for r in rejected)),
            'no_trade_blank_price_rows':sum(r['no_trade_blank_prices'] for r in rejected)})
        print(json.dumps({k:v for k,v in reports[-1].items() if k!='fields'}),flush=True)
    seen={}
    duplicates=[]
    for row in all_bars:
        key=row['contract_epoch_id'],row['date']
        if key in seen:
            duplicates.append({'key':key,'tables':[seen[key]['source_table_product'],row['source_table_product']]})
        seen[key]=row
    if duplicates:
        raise RuntimeError('cross_table_identity_collision_requires_review')
    write_csv(CZCE/'work_fullmarket_rejected_rows.csv',rejections,['source_table_product','vendor_contract','date','reason','missing_fields','volume_if_present','open_interest_if_present','candidate_lifetime_contains_date','conflicting_fields','no_trade_blank_prices'])
    by_product=defaultdict(list)
    for row in all_bars:
        by_product[row['product']].append(row)
    summary={'generated_at':now(),'source_repository':'ildhj0116/Work','source_commit':COMMIT,'source_commit_date':'2018-04-26',
        'requested_scope':{'exchanges':['CZCE'],'min_date':MIN_DATE,'max_date':MAX_DATE,'all_listed_and_historical_products':True},
        'status':'isolated_full_source_snapshot_not_full_market_lifecycle_certification','downloaded_product_tables':PRODUCTS,'metadata_file_reports':metadata_files,
        'metadata_rows':len(records),'metadata_unique_identities':len(metadata),'actual_metadata_product_codes':dict(Counter(r['product'] for r in records)),
        'accepted_rows':len(all_bars),'accepted_contract_epochs':len({r['contract_epoch_id'] for r in all_bars}),
        'accepted_first_date':min((r['date'] for r in all_bars),default=None),'accepted_last_date':max((r['date'] for r in all_bars),default=None),
        'accepted_by_product':{p:{'rows':len(rows),'epochs':len({r['contract_epoch_id'] for r in rows}),'first_date':min(r['date'] for r in rows),'last_date':max(r['date'] for r in rows)} for p,rows in sorted(by_product.items())},
        'rejected_rows':len(rejections),'rejected_reasons':dict(Counter(r['reason'] for r in rejections)),'missing_field_patterns':dict(missing_by_pattern),
        'unresolved_identity_rows':dict(unresolved),'no_trade_blank_price_rows':sum(r['no_trade_blank_prices'] for r in rejections),'tables':reports,
        'limits':['Snapshot ending in 2018 cannot cover 2019 to 2026 or later listings; requested full market scope remains incomplete.',
            'Per-contract listing and last-trade dates are unverified third-party metadata; no exchange listing rule is guessed.',
            'Six fields have different starts and sparse cells. Missing fields and zero-volume blank-price rows are retained as rejected evidence, never fabricated. Identical duplicate source cells are deduplicated with counts, conflicting nonmissing cells are rejected without choosing a value. Out-of-candidate-lifetime all-zero grid cells are separately counted; they are not missing trading days.',
            'ME/MA, RO/OI, WS/WH, WT/PM, ER/RI, TC/ZC are preserved by actual column product code; source filenames do not authorize renaming.',
            'Repository GPLv3 text does not establish data vendor redistribution rights; raw data stays local ignored output.',
            'Raw V/OI are not globally divided by 2 or mixed with TQ open OI. Product-specific official comparison is pending.'],
        'database_writes':0,'training_runs':0,'backtest_runs':0,'minute_downloads':0}
    write_json(CZCE/'work_fullmarket_summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('tables','metadata_file_reports','limits')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['fetch','normalize'])
    args=parser.parse_args()
    (fetch if args.action=='fetch' else normalize)()
