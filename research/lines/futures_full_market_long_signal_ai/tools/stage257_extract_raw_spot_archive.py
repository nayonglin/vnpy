"""Frozen257 one-pass literal extraction; no network or financial transforms.

Accepted253 CSV rows are copied, never reconstructed from their raw bodies.
Other retained bodies are read once; all dates, errors and ambiguity survive.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import html
import io
import json
from pathlib import Path
import re
import time

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage257_raw_spot_extraction_protocol/protocol.json'
PROTOCOL_SHA='2e0e56352ae8422a822ea8498af8d64481c66b642c135ebbfaf8f17aecd67242'
FIELDS=['date','fdata_top_level_row','product_text','spot_price_text','numeric_text_state','page_content_state','unit_text_id','source_raw_sha256']


def now():return datetime.now(timezone.utc).isoformat()


def raw_binding(path,raw):
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bound_bytes(ref):
    raw=Path(ref['path']).read_bytes();actual=raw_binding(ref['path'],raw)
    if any(actual[k]!=ref[k] for k in ('bytes','sha256')):raise ValueError('bound_input_changed '+ref['path'])
    return raw,actual


def save_json(path,value):
    with Path(path).open('x') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def clean(text):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',text))).strip()


def outer_rows(text):
    matches=list(re.finditer(r'<table\b[^>]*\bid\s*=\s*[\"\x27]fdata[\"\x27][^>]*>',text,re.I))
    if len(matches)!=1:raise ValueError('fdata table count not one')
    start=matches[0];depth=0;rows=[];row_start=None
    for tag in re.finditer(r'</?(?:table|tr)\b[^>]*>',text[start.start():],re.I):
        token=tag.group().lower();pos=start.start()+tag.start();end=start.start()+tag.end()
        if re.match(r'<table\b',token):depth+=1
        elif re.match(r'</table\b',token):
            depth-=1
            if depth==0:
                if row_start is not None:raise ValueError('unclosed top-level tr')
                return rows
        elif depth==1 and re.match(r'<tr\b',token):
            if row_start is not None:raise ValueError('unclosed top-level tr')
            row_start=end
        elif depth==1 and re.match(r'</tr\b',token):
            if row_start is None:raise ValueError('unmatched top-level tr')
            rows.append(text[row_start:pos]);row_start=None
    raise ValueError('unclosed fdata')


def cells(row):
    depth=0;result=[];start=None
    for tag in re.finditer(r'</?(?:td|th)\b[^>]*>',row,re.I):
        if not tag.group().startswith('</'):
            if depth==0:start=tag.end()
            depth+=1
        else:
            depth-=1
            if depth==0:result.append(clean(row[start:tag.start()]))
            if depth<0:raise ValueError('unmatched td')
    if depth:raise ValueError('unclosed td')
    return result


def number(value):return Decimal(value) if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',value) else None


def duplicates(records):
    names=defaultdict(list)
    for r in records:names[r['product_text']].append(int(r['fdata_top_level_row']))
    return [dict(product_text=k,top_level_rows=v) for k,v in names.items() if len(v)>1]


def unit_id(groups,lines):
    for key,value in groups.items():
        if value==lines:return key
    n=1
    while 'literal_unit_text_'+str(n) in groups:n+=1
    key='literal_unit_text_'+str(n);groups[key]=lines;return key


def parse_body(day,raw,expected,groups):
    """The accepted regex method; unsupported rows remain explicit unknowns."""
    observed=raw_binding(expected['path'] if expected else day+'.response',raw)
    matches=expected is not None and all(observed[k]==expected[k] for k in ('bytes','sha256'))
    inv=dict(date=day,body=observed,body_binding_matches=matches,format_state='unknown',source_data_state='unknown_format',
        title=None,publication_text=None,date_header_matches=None,fdata_top_level_rows=None,
        positive_numeric_spot_rows=None,no_data=None,unit_text_id=None,unsupported_rows=[],duplicate_product_groups=[],
        known_at=None,first_vintage_established=False)
    records=[]
    try:
        text=raw.decode('utf-8');expected_date=day.replace('-','年',1).replace('-','月',1)+'日'
        titles=re.findall(r'<title\b[^>]*>(.*?)</title>',text,re.I|re.S)
        if len(titles)!=1:raise ValueError('title count not one')
        inv['title']=clean(titles[0])
        pubs=[clean(x) for x in re.findall(r'<div\b[^>]*\bclass\s*=\s*[\"\x27]title2[\"\x27][^>]*>(.*?)</div>',text,re.I|re.S)]
        dated=[p for p in pubs if re.search(r'\d{4}年\d{2}月\d{2}日\s+\d{2}:\d{2}',p)]
        if len(dated)!=1:raise ValueError('publication date/time text count not one')
        inv['publication_text']=dated[0];inv['date_header_matches']=expected_date in inv['title'] and expected_date in dated[0]
        parsed=[cells(r) for r in outer_rows(text)];data=[];unsupported=[]
        headers=[['商品','现货','最近合约','主力合约'],['价格','代码','价格','现期差1','代码','价格','现期差2']]
        for index,row in enumerate(parsed,1):
            if len(row)==8 and row[0]:data.append((index,row))
            elif not row or row in headers or (len(row)==1 and ('交易所' in row[0] or row[0]=='暂无数据')):continue
            else:unsupported.append(dict(top_level_row=index,cells=row,state='unknown_unsupported_row'))
        positives=[r for _,r in data if number(r[1]) is not None and number(r[1])>0]
        no_data=any('暂无数据' in c for row in parsed for c in row);unitlines=[]
        for rawline in text.splitlines():
            t=clean(rawline)
            if any(k in t for k in ('单位:元/吨','黄金为元/克','铁矿石现货价格是','烧碱现货价格是','这里的期货价格为结算价')) and 'clip.setText' not in rawline:
                if t not in unitlines:unitlines.append(t)
        uid=unit_id(groups,unitlines)
        state=('unknown_binding_mismatch' if not matches else 'unknown_date_mismatch' if not inv['date_header_matches']
            else 'unknown_unsupported_rows' if unsupported else 'explicit_empty' if no_data and not positives
            else 'positive_spot_rows_observed' if positives and not no_data else 'unknown_empty_or_conflicting_content')
        for index,row in data:
            value=number(row[1]);numeric='non_numeric' if value is None else 'positive' if value>0 else 'zero' if value==0 else 'negative'
            records.append(dict(zip(FIELDS,[day,index,row[0],row[1],numeric,state,uid,observed['sha256']])))
        inv.update(format_state='parsed',source_data_state=state,fdata_top_level_rows=len(parsed),eight_cell_data_rows=len(data),
            positive_numeric_spot_rows=len(positives),zero_numeric_spot_rows=sum(number(r[1])==0 for _,r in data),
            negative_numeric_spot_rows=sum(number(r[1]) is not None and number(r[1])<0 for _,r in data),
            non_numeric_spot_rows=sum(number(r[1]) is None for _,r in data),no_data=no_data,unit_text_id=uid,
            unsupported_rows=unsupported,duplicate_product_groups=duplicates(records),
            unit_text_state='literal_text_observed' if unitlines else 'unknown_missing_unit_text')
    except (ValueError,UnicodeError,TypeError,KeyError) as exc:inv['unknown_reason']=type(exc).__name__+': '+str(exc)
    return inv,records


def acquisition_terminal(protocol):
    path=Path(protocol['acquisition255_terminal_required'])
    if not path.is_file():raise RuntimeError('255_terminal_missing_no_extraction')
    raw=path.read_bytes();value=json.loads(raw)
    if value.get('status') not in ('completed','failed','stopped','interrupted'):
        raise RuntimeError('255_terminal_not_terminal_no_extraction')
    return value,raw_binding(path,raw)


def run_extraction(protocol,protocol_binding=None):
    terminal255,terminal_binding=acquisition_terminal(protocol)  # Before any accepted CSV or raw read.
    out=Path(protocol['output_folder']).resolve();out.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();input_bindings=[terminal_binding];counts=Counter();inventory=[];body_reads=set();state='failed';failure=None
    groups={};records=[];bydate={};original=None
    try:
        if protocol['same_CSV_fields']!=FIELDS:raise ValueError('frozen_CSV_schema')
        ob,oref=bound_bytes(protocol['original249']);original=json.loads(ob);input_bindings.append(oref)
        if len(original['dates'])!=original['date_count'] or len(set(original['dates']))!=original['date_count']:raise ValueError('original_date_identity')
        rb,rref=bound_bytes(protocol['accepted253_receipt']);accepted=json.loads(rb);input_bindings.append(rref)
        groups={k:list(v) for k,v in accepted['literal_unit_text_groups'].items()}
        accepted_dates={r['date']:r for r in accepted['new_rows']}
        cb,cref=bound_bytes(protocol['accepted253_CSV']);counts['accepted253_csv_reads']+=1;input_bindings.append(cref)
        reader=csv.DictReader(io.StringIO(cb.decode('utf-8')))
        if reader.fieldnames!=FIELDS:raise ValueError('accepted253_CSV_header')
        csv_counts=Counter();accepted_records=defaultdict(list)
        for row in reader:
            prior=accepted_dates.get(row['date']);body=prior.get('source_body') if prior else None
            if (not body or row['source_raw_sha256']!=body['sha256'] or row['unit_text_id'] not in groups
                    or row['page_content_state']!=prior['source_data_state'] or None in row or any(v is None for v in row.values())):
                raise ValueError('accepted253_CSV_row_identity')
            records.append(row);accepted_records[row['date']].append(row);csv_counts[row['date']]+=1
        if len(records)!=protocol['accepted253_CSV']['data_rows']:raise ValueError('accepted253_CSV_count')
        for day,row in accepted_dates.items():
            if csv_counts[day]!=(row.get('spot_csv_rows') or 0):raise ValueError('accepted253_per_date_CSV_count '+day)
        inherited={r['date']:r for r in accepted['inherited_nine_rows']}
        forbidden={Path(r['source_body']['path']).resolve() for r in accepted_dates.values() if r.get('source_body')}
        forbidden.update(Path(original['reused'][d]['body']['path']).resolve() for d,r in inherited.items()
            if r.get('source_data_state')=='explicit_empty' and d in original['reused'])
        archive=Path(original['output_contract']['path']);rowsdir=archive/original['output_contract']['metadata_subdir'];rawdir=archive/original['output_contract']['body_subdir']
        for day in original['dates']:
            if day in accepted_dates:
                inv=dict(accepted_dates[day],origin='accepted253_CSV_and_inventory',raw_read_count=0,known_at=None,first_vintage_established=False)
                inv['duplicate_product_groups']=duplicates(accepted_records[day])
                inv.setdefault('unsupported_rows',None)
                inv['unsupported_rows_assessment']='not_in_accepted253_receipt_raw_not_reopened'
                counts['accepted253_dates']+=1
            elif day in original['reused'] and inherited.get(day,{}).get('source_data_state')=='explicit_empty':
                old=inherited[day];ref=original['reused'][day]['body']
                if old['body_sha256']!=ref['sha256']:raise ValueError('inherited_empty_identity '+day)
                inv=dict(old,origin='old9_inherited_empty',body=ref,raw_read_count=0,known_at=None,first_vintage_established=False,unsupported_rows=[],duplicate_product_groups=[])
                counts['old9_empty_inherited_dates']+=1
            else:
                rowpath=rowsdir/(day+'.json');started=rowsdir/(day+'.started.json');meta=None;expected=None;candidate=None
                if rowpath.is_file():
                    meta=json.loads(rowpath.read_bytes());counts['archive_date_metadata_reads']+=1
                    if meta.get('date')!=day:raise ValueError('archive_metadata_date '+day)
                    expected=meta.get('body');candidate=expected['path'] if expected else None
                elif started.is_file():
                    meta=json.loads(started.read_bytes());counts['archive_date_metadata_reads']+=1
                if day in original['reused']:
                    fixed=original['reused'][day]['body']
                    if expected is not None and expected!=fixed:raise ValueError('old9_metadata_body_changed '+day)
                    expected=fixed;candidate=fixed['path'];origin='old9_positive_full_S'
                else:
                    origin='remaining_archive_body'
                    if candidate is None and (rawdir/(day+'.response')).is_file():candidate=str(rawdir/(day+'.response'))
                if candidate is not None:
                    path=Path(candidate).resolve()
                    if path in forbidden:
                        inv=dict(date=day,source_data_state='unknown_ref_to_inherited_body_no_read',body=expected,raw_read_count=0)
                    elif path in body_reads:
                        inv=dict(date=day,source_data_state='unknown_shared_body_path',body=expected,raw_read_count=0)
                    else:
                        body_reads.add(path)
                        counter='old9_positive_body_reads' if day in original['reused'] else 'remaining_body_reads'
                        counts[counter]+=1
                        try:
                            raw=path.read_bytes();inv,new=parse_body(day,raw,expected,groups)
                            inv['body']['path']=str(path)
                            if expected is None:
                                inv['source_data_state']='unknown_missing_body_binding'
                            if meta and meta.get('http_success') is False:
                                inv['source_data_state']='unknown_HTTP_response'
                            for row in new:row['page_content_state']=inv['source_data_state']
                            records.extend(new);inv.update(origin=origin,raw_read_count=1)
                        except OSError as exc:
                            inv=dict(date=day,origin=origin,source_data_state='unknown_body_read_error',body=expected,raw_read_count=1,unknown_reason=str(exc))
                else:
                    inv=dict(date=day,origin='archive_metadata' if meta else 'not_acquired',source_data_state='unknown_no_body' if meta else 'unattempted',raw_read_count=0,
                        acquisition_state=meta.get('state') if meta else None,transport_error=meta.get('transport_error') if meta else None)
                inv.setdefault('known_at',None);inv.setdefault('first_vintage_established',False)
                if meta:
                    inv.update(acquisition_state=meta.get('state'),HTTP_status_inherited=meta.get('http_status'),transport_error=meta.get('transport_error'))
            inventory.append(inv);bydate[day]=inv
        counts.update(date_inventory_rows=len(inventory),output_spot_rows=len(records),unique_product_texts=len({r['product_text'] for r in records}),
            accepted253_body_reads=0,old9_empty_body_reads=0)
        with (out/'raw_spot_text.csv').open('x',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(records)
        with (out/'date_inventory.jsonl').open('x') as f:
            for row in inventory:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        save_json(out/'literal_unit_groups.json',groups);state='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    result=dict(schema='stage257_one_pass_raw_spot_extraction_receipt_v1',status=state,protocol=protocol_binding,
        source=raw_binding(__file__,Path(__file__).read_bytes()),inputs=input_bindings,counts=dict(counts),
        source_data_states=dict(Counter(r['source_data_state'] for r in inventory)),
        duplicate_literal_dates=[r['date'] for r in inventory if r.get('duplicate_product_groups')],
        unsupported_row_dates=[r['date'] for r in inventory if r.get('unsupported_rows')],failure=failure,
        terminal255_status=terminal255.get('status'),raw_body_read_count=len(body_reads),printed_clock_is_known_at=False,
        normalized_feature_rows=0,network_requests=0,new_fit=0,new_cash=0,SQL=0,automatic_retry=False,automatic_actual_execution=False,
        cumulative_fit=protocol.get('cumulative_fit'),cumulative_cash=protocol.get('cumulative_cash'),goal_complete=False,
        elapsed_seconds=time.monotonic()-began,completed_at=now())
    save_json(out/'receipt.json',result)
    save_json(out/'terminal.json',dict(schema='stage257_extraction_terminal_v1',status=state,exit_code=0 if state=='completed' else 1,
        new_fit=0,new_cash=0,network_requests=0,elapsed_seconds=result['elapsed_seconds']))
    artifacts={}
    for path in sorted(out.iterdir()):
        if path.is_file():artifacts[path.name]=raw_binding(path,path.read_bytes())
    save_json(out/'manifest.json',dict(schema='stage257_extraction_manifest_v1',status=state,protocol=protocol_binding,source=result['source'],artifacts=artifacts,new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',required=True);parser.parse_args(argv)
    raw=PROTOCOL.read_bytes();pb=raw_binding(PROTOCOL,raw)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen257_protocol_changed')
    protocol=json.loads(raw)
    if protocol['schema']!='stage257_one_pass_raw_spot_extraction_protocol_v1':raise ValueError('frozen257_schema')
    result=run_extraction(protocol,pb)
    print(json.dumps(dict(status=result['status'],counts=result['counts'],source_data_states=result['source_data_states']),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
