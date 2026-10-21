"""Single-pass frozen274 World Corn source projection, with no financial join.

Source hashes are inherited from273, never integrity-rehashed here. Each
successful standalone CSV or ZIP CSV member is parsed once without extractall.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import date,datetime,time,timedelta,timezone
from decimal import Decimal,InvalidOperation,localcontext
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import time as timer
import zipfile
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage274_wasde_corn_projection_protocol/protocol.json'
PROTOCOL_SHA='023ffe7d172c93534adc80c718a7cd7c8b6cbfbc0992df9a4d0c68d4e2d7975d'
SOURCE_ROOT=LINE/'outputs/stage273_wasde_raw_source'
OUTPUT=LINE/'outputs/stage275_wasde_corn_projection/actual_run1'
FIELDS=['WasdeNumber','ReportDate','ReportTitle','Attribute','ReliabilityProjection','Commodity','Region','MarketYear',
    'ProjEstFlag','AnnualQuarterFlag','Value','Unit','ReleaseDate','ReleaseTime','ForecastYear','ForecastMonth']
TRACE=['source_filename','source_member','source_row','source_line_end','source_sha256','source_target_month',
    'visible_version_suffix','row_parse_state','extra_fields_json','source_stream_complete']
MONTHS={name:i+1 for i,name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}


def now():return datetime.now(timezone.utc).isoformat()


def binding(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def json_read(path):
    raw=Path(path).read_bytes();return json.loads(raw),binding(path,raw)


def save_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def release_date(value):
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return date.fromisoformat(value)
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}',value):
        month,day,year=map(int,value.split('/'));return date(year,month,day)
    raise ValueError('unsupported_explicit_ReleaseDate')


def candidate_boundary(day):
    return datetime.combine(day+timedelta(days=2),time(),ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()


def marketing_year(text):
    if not re.fullmatch(r'\d{4}/\d{2}',text):raise ValueError('unknown_marketing_year_format')
    first,last=map(int,text.split('/'))
    if last!=(first+1)%100:raise ValueError('unknown_marketing_year_sequence')
    return first


def project_report(rows):
    """One observed WasdeNumber; highest current year is chosen before Proj."""
    result=dict(WasdeNumber=rows[0].get('WasdeNumber','') if rows else '',release_date='',release_month='',marketing_year='',
        state='unknown',unknown_reason='',S_text='',U_text='',q_raw='',unit='',feature_eligible=False,
        candidate_available_at_utc='',known_at='',correction_known_at='',historical_first_seen_proven=False,
        ReleaseDate_literals=sorted({r.get('ReleaseDate','') for r in rows}),
        ReleaseTime_literals=sorted({r.get('ReleaseTime','') for r in rows}),corn_world_rows=len(rows),
        current_entity_rows=0,reprinted_entity_rows=0,S_source={},U_source={},
        sources=sorted({r.get('source_filename','')+'::'+r.get('source_member','') for r in rows}))
    def unknown(reason):result['unknown_reason']=reason;return result
    if not rows or not result['WasdeNumber'] or len({r['WasdeNumber'] for r in rows})!=1:return unknown('missing_or_conflicting_WasdeNumber')
    if any(r.get('row_parse_state')!='parsed' or r.get('source_stream_complete') is False for r in rows):
        return unknown('incomplete_source_row_or_stream')
    try:days={release_date(r['ReleaseDate']) for r in rows}
    except (ValueError,TypeError):return unknown('unknown_ReleaseDate_format')
    if len(days)!=1:return unknown('conflicting_ReleaseDate')
    day=next(iter(days));result.update(release_date=day.isoformat(),release_month=day.strftime('%Y-%m'),candidate_available_at_utc=candidate_boundary(day))
    if day>date(2026,10,19):return unknown('release_after_asof')
    for r in rows:
        match=re.fullmatch(r'([A-Za-z]+) (\d{4})',r['ReportDate'])
        if not match or match[1] not in MONTHS:return unknown('unknown_ReportDate_format')
        if (int(match[2]),MONTHS[match[1]])!=(day.year,day.month):return unknown('report_release_month_conflict')
        if r.get('source_target_month') and r['source_target_month']!=day.strftime('%Y-%m'):
            return unknown('source_target_release_month_conflict')
    entity=[r for r in rows if r['ReportTitle']=='World Corn Supply and Use' and r['Commodity']=='Corn' and r['Region']=='World'
        and r['AnnualQuarterFlag']=='Annual' and r['ReliabilityProjection']=='']
    current=[]
    for r in entity:
        if (not re.fullmatch(r'\d{4}',r['ForecastYear']) or not re.fullmatch(r'\d{1,2}',r['ForecastMonth'])
                or not 1<=int(r['ForecastMonth'])<=12):return unknown('unknown_forecast_year_month')
        if (int(r['ForecastYear']),int(r['ForecastMonth']))==(day.year,day.month):current.append(r)
    result.update(current_entity_rows=len(current),reprinted_entity_rows=len(entity)-len(current))
    if not current:return unknown('missing_current_exact_entity')
    try:latest=max(marketing_year(r['MarketYear']) for r in current)
    except (ValueError,TypeError):return unknown('unknown_current_marketing_year')
    chosen=[r for r in current if marketing_year(r['MarketYear'])==latest]
    result['marketing_year']=chosen[0]['MarketYear']
    if {r['ProjEstFlag'] for r in chosen}!={'Proj.'}:return unknown('latest_marketing_year_not_unique_Proj')
    stocks=[r for r in chosen if r['Attribute']=='Ending Stocks'];use=[r for r in chosen if r['Attribute']=='Domestic Total']
    if len(stocks)!=1 or len(use)!=1:return unknown('duplicate_or_missing_quantity_pair')
    s,u=stocks[0],use[0]
    if s['Unit']!=u['Unit'] or s['Unit']!='Million Metric Tons':return unknown('quantity_unit_mismatch')
    try:S=Decimal(s['Value']);U=Decimal(u['Value'])
    except InvalidOperation:return unknown('non_numeric_quantity')
    if not S.is_finite() or not U.is_finite() or S<0 or U<=0:return unknown('invalid_quantity_domain')
    def trace(r):return {k:r.get(k,'') for k in TRACE[:5]}
    with localcontext() as context:
        context.prec=50;q=str(S/U)
    result.update(state='quantity_observed',S_text=s['Value'],U_text=u['Value'],q_raw=q,unit=s['Unit'],
        feature_eligible=True,S_source=trace(s),U_source=trace(u))
    if any(r.get('visible_version_suffix')=='V2' or '-V2.' in r.get('source_filename','') for r in rows):
        result.update(state='unknown',unknown_reason='visible_V2_correction_time_unknown',feature_eligible=False,correction_known_at='unknown')
    return result


def consume_csv(binary,request,member,ledger):
    """Exactly one CSV stream; all16 Corn/World fields remain literal."""
    corn=[];reader=None
    item=dict(member=member,status='unknown',header=None,source_rows=0,corn_world_rows=0,malformed_rows=0)
    try:
        with io.TextIOWrapper(binary,encoding='utf-8-sig',newline='') as text:
            reader=csv.DictReader(text);item['header']=reader.fieldnames
            if reader.fieldnames!=FIELDS:raise ValueError('unsupported_header')
            for index,row in enumerate(reader,1):
                item['source_rows']+=1;ledger['all_source_rows']+=1
                bad=None in row or any(row.get(k) is None for k in FIELDS)
                item['malformed_rows']+=int(bad)
                for key in ('MarketYear','ForecastYear','Unit','ProjEstFlag','AnnualQuarterFlag','ReportDate'):
                    ledger[key][str(row.get(key))]+=1
                if row.get('Commodity')!='Corn' or row.get('Region')!='World':continue
                raw={k:row.get(k) for k in FIELDS}
                raw.update(source_filename=request['filename'],source_member=member,source_row=index,source_line_end=reader.line_num,
                    source_sha256=request['sha256'],source_target_month=request.get('month') or '',
                    visible_version_suffix=request.get('visible_version_suffix',''),row_parse_state='unknown_short_or_extra_fields' if bad else 'parsed',
                    extra_fields_json=json.dumps(row.get(None),ensure_ascii=False) if None in row else '',source_stream_complete=False)
                corn.append(raw);item['corn_world_rows']+=1
        item['status']='completed'
    except (OSError,UnicodeError,csv.Error,ValueError,zipfile.BadZipFile) as exc:
        item['error']=type(exc).__name__+': '+str(exc)
    for r in corn:r['source_stream_complete']=item['status']=='completed'
    return corn,item


def csv_value(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True) if isinstance(value,(dict,list)) else value


def write_csv(path,fields,rows):
    with gzip.open(path,'xt',compresslevel=1,encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:csv_value(row.get(k,'')) for k in fields})


def run_actual(protocol,pb):
    handle,hb=json_read(SOURCE_ROOT/'root_execution_handle.json')
    if handle.get('status')!='completed':raise RuntimeError('root273_real_terminal_not_confirmed')
    manifest,mb=json_read(LINE/'outputs'/protocol['source273'])
    if manifest['terminal']['status'] not in ('completed','stopped_early'):raise RuntimeError('273_not_terminal')
    catalog,cb=json_read(SOURCE_ROOT/'catalog_v2.json')
    if cb['sha256']!=manifest['catalog_sha256']:raise ValueError('accepted273_catalog_changed')
    if protocol['expected_header']!=FIELDS:raise ValueError('frozen274_header_changed')
    OUTPUT.mkdir(parents=True,exist_ok=False);began=timer.monotonic();status='failed';failure=None
    inventory=[];allcorn=[];projections=[];unknown_months=[];source_streams=0
    ledger={k:Counter() for k in ('MarketYear','ForecastYear','Unit','ProjEstFlag','AnnualQuarterFlag','ReportDate')};ledger['all_source_rows']=0
    requests={r['filename']:r for r in manifest['requests']}
    try:
        for target in catalog['targets']:
            request=requests.get(target['filename']);entry=dict(target,acquisition_status=request['status'] if request else 'unattempted',members=[])
            inventory.append(entry)
            if not request or request['status']!='body_retained_unparsed':
                entry['projection_source_state']='unknown_missing_payload'
                unknown_months.append(dict(month=target.get('month'),filename=target['filename'],reason=entry['acquisition_status'],
                    release_date=None,error=request.get('error') if request else None))
                continue
            entry['inherited_body_binding']={k:request[k] for k in ('path','bytes','sha256')}
            entry['integrity_rehash']=False;path=Path(request['path'])
            try:
                if path.stat().st_size!=request['bytes']:raise ValueError('source_size_changed')
                if request['kind']=='csv':
                    source_streams+=1
                    rows,info=consume_csv(path.open('rb'),request,'',ledger);allcorn.extend(rows);entry['members'].append(info)
                elif request['kind']=='zip':
                    with zipfile.ZipFile(path) as zipped:
                        infos=zipped.infolist();entry['zip_members']=[dict(name=i.filename,bytes=i.file_size,is_directory=i.is_dir()) for i in infos]
                        if not infos or any(i.is_dir() or not i.filename.lower().endswith('.csv') for i in infos):raise ValueError('ZIP_non_csv_member')
                        if sum(i.file_size for i in infos)>192*1024*1024:raise ValueError('ZIP_uncompressed_cap')
                        for info in infos:
                            source_streams+=1
                            rows,details=consume_csv(zipped.open(info),request,info.filename,ledger)
                            allcorn.extend(rows);entry['members'].append(details)
                else:raise ValueError('unsupported_source_kind')
                entry['projection_source_state']='parsed' if all(x['status']=='completed' for x in entry['members']) else 'unknown_source_stream'
                if entry['projection_source_state']=='parsed' and not sum(x['corn_world_rows'] for x in entry['members']):
                    entry['projection_source_state']='unknown_no_exact_Corn_World_rows'
            except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as exc:
                entry.update(projection_source_state='unknown_source_stream',error=type(exc).__name__+': '+str(exc))
            if entry['projection_source_state']!='parsed':
                unknown_months.append(dict(month=target.get('month'),filename=target['filename'],reason=entry['projection_source_state'],release_date=None,error=entry.get('error')))
        grouped=defaultdict(list)
        for row in allcorn:
            identity=row['WasdeNumber'] or 'unknown::'+row['source_filename']+'::'+row['source_member']
            grouped[identity].append(row)
        projections=[project_report(rows) for rows in grouped.values()]
        write_csv(OUTPUT/'corn_world_rows.csv.gz',FIELDS+TRACE,allcorn)
        write_csv(OUTPUT/'report_projection.csv.gz',list(projections[0]) if projections else ['WasdeNumber','state','unknown_reason'],projections)
        save_json(OUTPUT/'source_inventory.json',dict(schema='stage275_wasde_source_inventory_v1',sources=inventory,
            source_unknown_months=unknown_months,unlisted_calendar_months=catalog.get('unlisted_calendar_months',[]),
            missing_months_are_not_release_events=True,source_row_numbering='1-based CSV data record excluding header; source_line_end is physical ending line',
            ledger=ledger,observed_report_rows=len(projections),observed_corn_world_rows=len(allcorn)))
        status='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    receipt=dict(schema='stage275_wasde_corn_projection_receipt_v1',status=status,protocol=pb,source=binding(__file__),
        source_manifest=mb,source_handle=hb,source_catalog=cb,acquisition_status=manifest['terminal']['status'],
        source_targets=len(catalog['targets']),source_successful_bodies=sum(r['status']=='body_retained_unparsed' for r in requests.values()),
        source_CSV_member_streams=source_streams,observed_corn_world_rows=len(allcorn),observed_reports=len(projections),
        feature_eligible_reports=sum(r['feature_eligible'] for r in projections),report_states=dict(Counter(r['state'] for r in projections)),
        report_unknown_reasons=dict(Counter(r['unknown_reason'] for r in projections if r['unknown_reason'])),
        source_unknown_months=unknown_months,unlisted_calendar_months=catalog.get('unlisted_calendar_months',[]),
        root_prior_discovery_reads=dict(ZIPs='each directory plus first member first3 lines once',CSV_2021_01='first3 lines once and separate full schema/entity scan once',
            acquisition_SHA='once per body during273 download',extra_integrity_rehashes=0),
        author_source_reading='each successful CSV/member one new complete parse stream; inherited273 body SHA, no integrity reread',
        original_body_integrity_rehashes=0,ZIP_extractall=0,ratio_decimal_precision=50,
        candidate_clock='release+2 calendar days NewYork00 to UTC; assumed delay only, not historical first-seen proof',
        failure=failure,network=0,SQL=0,native_price_reads=0,labels=0,new_fit=0,new_cash=0,cumulative_fit=439,cumulative_cash=238,
        automatic_retry=False,goal_complete=False,completed_at=now(),elapsed_seconds=timer.monotonic()-began)
    save_json(OUTPUT/'receipt.json',receipt)
    save_json(OUTPUT/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
    roles={'corn_world_rows':'corn_world_rows.csv.gz','report_projection':'report_projection.csv.gz','source_inventory':'source_inventory.json',
        'receipt':'receipt.json','terminal':'terminal.json'}
    save_json(OUTPUT/'manifest.json',dict(schema='stage275_wasde_corn_projection_manifest_v1',status=status,protocol=pb,source=receipt['source'],
        artifacts={k:binding(OUTPUT/v) for k,v in roles.items() if (OUTPUT/v).is_file()},new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',required=True);parser.parse_args(argv)
    protocol,pb=json_read(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen274_changed')
    if protocol['schema']!='stage274_single_world_corn_quantity_extraction_protocol_v1':raise ValueError('frozen274_schema')
    receipt=run_actual(protocol,pb)
    print(json.dumps({k:receipt[k] for k in ('status','source_successful_bodies','source_CSV_member_streams','observed_corn_world_rows',
        'observed_reports','feature_eligible_reports','report_unknown_reasons','elapsed_seconds')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
