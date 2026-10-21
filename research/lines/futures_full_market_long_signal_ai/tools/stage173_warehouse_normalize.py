"""Fixed172 seven-report offline normalization. No network or financial imports.

Every JSON row and HTML physical tr survives. Unknown units/codes are not inferred
from contract multipliers, later reports, or apparent numerical agreement.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
import traceback

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage172_warehouse_pilot_protocol/protocol.json'
PROTOCOL_SHA='7359cd6fbd9d1bbf65d30dd89b8b4b2d7da4d49463de2018d737814a39b17b00'
RAW_MANIFEST=LINE/'outputs/stage172_warehouse_pilot_raw/actual_run1/manifest.json'
RAW_MANIFEST_SHA='1460d64762d6e90822aeb7bca3a96299574df3e149721c6548debc08b8c7f545'
VERSION='stage173_warehouse_physical_rows_v1'


def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bind(path):
    p=Path(path);data=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(data),sha256=digest(data))


def bound_bytes(binding):
    data=Path(binding['path']).read_bytes()
    if len(data)!=binding['bytes'] or digest(data)!=binding['sha256']:
        raise ValueError('bound_input_mismatch '+binding['path'])
    return data


def decimal_cell(raw,missing=False):
    result=dict(raw=raw,raw_type='missing_field' if missing else type(raw).__name__,state=None,value=None,method=None)
    if missing:result['state']='missing_field';return result
    if raw is None:result['state']='null';return result
    if isinstance(raw,bool):result['state']='parse_failure';return result
    text=str(raw).strip()
    if not text:result['state']='blank';return result
    if text in ('--','-','—','–'):result['state']='placeholder';return result
    if isinstance(raw,float) and not math.isfinite(raw):result['state']='parse_failure';return result
    plain=r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)'
    grouped=r'[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?'
    if re.fullmatch(plain,text):result['method']='strict_decimal'
    elif re.fullmatch(grouped,text):text=text.replace(',','');result['method']='strict_grouped_decimal'
    else:result['state']='parse_failure';return result
    try:value=Decimal(text)
    except InvalidOperation:result['state']='parse_failure';return result
    if not value.is_finite():result['state']='parse_failure';return result
    result.update(state='numeric_zero' if value==0 else 'numeric',value=format(value,'f'))
    return result


def numeric(cell):
    return cell['state'] in ('numeric','numeric_zero') and cell['value'] is not None


def display(text):
    return str(text or '').split('$$',1)[0].strip()


def level(label,region=''):
    text=display(label)
    if '保税' in text and ('总计' in text or '合计' in text):return 'bonded_total'
    if '完税' in text and ('总计' in text or '合计' in text):return 'duty_paid_total'
    if text=='总计':return 'grand_total'
    if text in ('合计','小计'):return 'region_subtotal' if region else 'scope_subtotal'
    return 'leaf' if text else 'unknown'


def make_scope(row):
    return canon([row['source_format'],row['product_raw'],row['product_code_raw'],row['storage_type_raw'],row['unit_raw']])


def normalize_json(obj,request_date):
    if not isinstance(obj,dict) or not isinstance(obj.get('o_cursor'),list):raise ValueError('unknown_json_envelope')
    meta={k:v for k,v in obj.items() if k!='o_cursor'}
    dates={k:str(obj[k]).replace('-','') for k in ('report_date','o_tradingday') if k in obj}
    date_state='absent' if not dates else 'matches' if all(v==request_date for v in dates.values()) else 'mismatch'
    rows=[]
    for index,raw in enumerate(obj['o_cursor']):
        if not isinstance(raw,dict):raise ValueError('nonobject_json_row')
        product=raw.get('VARNAME','');warehouse=raw.get('WHABBRNAME','');region=raw.get('REGNAME','')
        row=dict(request_date=request_date,source_format='json',source_row=index,table_index=None,table_row=index,
                 product_raw=product,product_display=display(product),product_code_raw=raw.get('VARID'),
                 storage_type_raw=raw.get('WHTYPE'),type_code_state='code_unmapped' if 'WHTYPE' in raw else 'absent',
                 storage_kind='factory_explicit_product_name' if '厂库' in display(product) else 'UNKNOWN',
                 unit_raw=raw.get('WGHTUNIT'),unit_value=None,unit_state='code_unmapped' if 'WGHTUNIT' in raw else 'absent',
                 region_raw=region,warehouse_raw=warehouse,rowstatus_raw=raw.get('ROWSTATUS'),
                 row_level=level(warehouse,region),aggregate_label=display(warehouse),
                 quantity=decimal_cell(raw.get('WRTWGHTS'),missing='WRTWGHTS' not in raw),
                 official_delta=decimal_cell(raw.get('WRTCHANGE'),missing='WRTCHANGE' not in raw),
                 quantity_field_name='WRTWGHTS',location_field_name='WHABBRNAME',delta_field_name='WRTCHANGE',
                 quantity_origin=f'json:{index}:WRTWGHTS',delta_origin=f'json:{index}:WRTCHANGE',
                 quantity_inherited=False,delta_inherited=False,
                 context={'REGNAME':region,'WHABBRNAME':warehouse},raw_fields=raw,
                 bonded_context='explicit_name_only' if '保税' in display(warehouse) or '保税' in display(product) else 'UNKNOWN',
                 layout_errors=[])
        row['scope_key']=make_scope(row);rows.append(row)
    return rows,dict(source_format='json',request_date=request_date,body_dates=dates,date_state=date_state,
                     raw_metadata=meta,physical_rows=len(rows),field_names=sorted({k for r in obj['o_cursor'] for k in r}),
                     table_count=None,unit_codebook_bound=False,type_codebook_bound=False,first_publication_PIT=False)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            if self.table is not None:raise ValueError('nested_table_unsupported')
            self.table=dict(attrs=dict(attrs),rows=[],errors=[]);self.tables.append(self.table)
        elif tag=='tr' and self.table is not None:
            self.row=dict(attrs=dict(attrs),cells=[],line=self.getpos()[0]);self.table['rows'].append(self.row)
        elif tag in ('td','th') and self.row is not None:
            self.cell=dict(tag=tag,attrs=dict(attrs),parts=[],line=self.getpos()[0],start_tag=self.get_starttag_text())
            self.row['cells'].append(self.cell)
        elif tag=='br' and self.cell is not None:self.cell['parts'].append('\n')
    def handle_data(self,data):
        if self.cell is not None:self.cell['parts'].append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th'):self.cell=None
        elif tag=='tr':self.row=None
        elif tag=='table':self.table=None;self.row=None;self.cell=None


def expand_table(table,index):
    grid={}
    for r,row in enumerate(table['rows']):
        c=0
        for ci,cell in enumerate(row['cells']):
            raw=''.join(cell.pop('parts'));cell['raw_text']=raw;cell['text']=re.sub(r'\s+',' ',raw).strip()
            while (r,c) in grid:c+=1
            spans=[]
            for name in ('rowspan','colspan'):
                value=cell['attrs'].get(name,'1')
                if not re.fullmatch(r'[0-9]+',value) or not 1<=int(value)<=2048:
                    table['errors'].append('invalid_'+name);spans.append(1)
                else:spans.append(int(value))
            rs,cs=spans;cell.update(rowspan=rs,colspan=cs,logical_column=c,origin=f'html:{index}:{r}:{ci}')
            for dr in range(rs):
                for dc in range(cs):
                    key=(r+dr,c+dc)
                    if key in grid:table['errors'].append('overlapping_span')
                    else:grid[key]=dict(text=cell['text'],origin=cell['origin'],origin_row=r,origin_cell=ci,
                                        inherited_row=dr>0,colspan=cs,rowspan=rs)
            c+=cs
    for r,row in enumerate(table['rows']):
        cols=[c for rr,c in grid if rr==r]
        row['grid']=[grid.get((r,c)) for c in range(max(cols)+1)] if cols else []
    return table


def normalize_html(text,request_date):
    parser=TableParser();parser.feed(text);parser.close()
    tables=[expand_table(t,i) for i,t in enumerate(parser.tables)]
    intro=[cell['text'] for t in tables if 'content_intro' in t['attrs'].get('class','') for r in t['rows'] for cell in r['cells']]
    dates=sorted(set(re.findall(r'\b20[0-9]{2}-[0-9]{2}-[0-9]{2}\b',' '.join(intro))))
    date_state='absent' if not dates else 'matches' if all(d.replace('-','')==request_date for d in dates) else 'mismatch'
    rows=[];headers=[]
    for ti,table in enumerate(tables):
        product='';unit_raw=None;unit_value=None;names=[]
        for ri,physical in enumerate(table['rows']):
            cells=physical['cells'];grid=physical['grid'];texts=[c['text'] for c in cells]
            is_intro='content_intro' in table['attrs'].get('class','')
            is_header=bool(cells) and all(c['tag']=='th' for c in cells)
            units=[re.fullmatch(r'单位\s*[:：]\s*(.+)',c['text']) for c in cells]
            unit_matches=[m for m in units if m]
            section=bool(unit_matches)
            if is_header:names=[g['text'] if g else '' for g in grid]
            if section:
                unit_raw=next(c['text'] for c in cells if re.fullmatch(r'单位\s*[:：]\s*(.+)',c['text']))
                unit_value=unit_matches[0].group(1).strip() if len(unit_matches)==1 else None
                candidates=[c['text'] for c in cells if not re.fullmatch(r'单位\s*[:：]\s*(.+)',c['text'])]
                product=candidates[0] if len(candidates)==1 else ''
            kind='factory_explicit_header_or_name' if any('厂库' in n for n in names) or '厂库' in product else ('warehouse_explicit_header' if any(n in names for n in ('仓库','交割仓库')) else 'UNKNOWN')
            context={};positions={n:i for i,n in enumerate(names)}
            def at(name):
                i=positions.get(name)
                return grid[i] if i is not None and i<len(grid) and grid[i] else None
            for name,i in positions.items():
                if name not in ('期货','本日数量','上日数量','昨日数量','增减') and i<len(grid) and grid[i]:context[name]=grid[i]['text']
            loc_name=next((name for name in ('厂库','仓库','交割仓库') if name in positions),None)
            q_name=next((name for name in ('期货','本日数量') if name in positions),None)
            location=at(loc_name);region=at('地区');q=at(q_name);delta=at('增减')
            warehouse=location['text'] if location else ''
            region_text=region['text'] if region else ''
            merged=bool(region and location and region['origin']==location['origin'])
            if merged:region_text=''
            label=warehouse
            for value in texts:
                if display(value) in ('总计','合计','小计') or (('保税' in value or '完税' in value) and ('总计' in value or '合计' in value)):
                    label=value;break
            row_level='intro' if is_intro else 'column_header' if is_header else 'section_header' if section else level(label,region_text)
            if not product and row_level=='leaf':row_level='unknown'
            row=dict(request_date=request_date,source_format='html',source_row=len(rows),table_index=ti,table_row=ri,
                product_raw=product,product_display=product,product_code_raw=None,storage_type_raw='厂库' if kind.startswith('factory') else ('仓库' if kind.startswith('warehouse') else None),
                type_code_state='not_applicable',storage_kind=kind,unit_raw=unit_raw,unit_value=unit_value,
                unit_state='explicit' if unit_value else 'unknown',region_raw=region_text,warehouse_raw=warehouse,
                region_state='merged_with_location_unknown' if merged else 'explicit_or_rowspan_context',rowstatus_raw=None,
                row_level=row_level,aggregate_label=display(label),
                quantity=decimal_cell(q['text'] if q else None,missing=q is None),
                official_delta=decimal_cell(delta['text'] if delta else None,missing=delta is None),
                quantity_field_name=q_name,location_field_name=loc_name,delta_field_name='增减' if '增减' in positions else None,
                quantity_origin=q['origin'] if q else None,delta_origin=delta['origin'] if delta else None,
                quantity_inherited=q['inherited_row'] if q else False,delta_inherited=delta['inherited_row'] if delta else False,
                context=context,raw_cells=cells,logical_grid=grid,table_attrs=table['attrs'],row_attrs=physical['attrs'],
                bonded_context='explicit_name_only' if '保税' in warehouse or '保税' in product else 'UNKNOWN',
                layout_errors=list(table['errors']))
            row['scope_key']=make_scope(row);rows.append(row)
        headers.append(dict(table_index=ti,headers=names,product_raw=product,unit_raw=unit_raw,unit_value=unit_value,errors=table['errors']))
    return rows,dict(source_format='html',request_date=request_date,body_dates=dates,date_state=date_state,
        intro_text=intro,table_count=len(tables),physical_rows=len(rows),tables=headers,first_publication_PIT=False)


def scopes(rows):
    result=defaultdict(list)
    for row in rows:
        if row['product_raw'] and row['row_level'] not in ('intro','column_header','section_header'):
            result[row['scope_key']].append(row)
    return dict(result)


def coverage(group):
    return sorted(canon(r['context']) for r in group if r['row_level']=='leaf')


def arithmetic_basis(group):
    if all(r['unit_state']=='explicit' and r['unit_value'] for r in group):return 'explicit_declared_unit'
    if all(r['source_format']=='json' and r['unit_raw'] is not None and r['storage_type_raw'] is not None for r in group):
        return 'raw_code_only_not_physical_unit_certification'
    return 'unknown_unit'


def measurements(rows,field):
    origin_field='quantity_origin' if field=='quantity' else 'delta_origin'
    origins={};identity_origins=defaultdict(set);reasons=[]
    for row in rows:
        cell=row[field];origin=row[origin_field]
        identity_origins[canon(row['context'])].add(origin)
        if not numeric(cell):reasons.append('unknown_numeric')
        elif field=='quantity' and Decimal(cell['value'])<0:reasons.append('negative_quantity')
        if origin in origins and origins[origin][field]['value']!=cell['value']:reasons.append('conflicting_span_value')
        origins.setdefault(origin,row)
    if any(len(v)>1 for v in identity_origins.values()):reasons.append('duplicate_leaf')
    values=[Decimal(r[field]['value']) for r in origins.values() if numeric(r[field])]
    return sum(values,Decimal(0)),len(origins),sorted(set(reasons))


def intra_checks(rows):
    checks=[]
    for key,group in scopes(rows).items():
        leaves=[r for r in group if r['row_level']=='leaf']
        aggregates=[r for r in group if r['row_level'] in ('grand_total','region_subtotal','scope_subtotal','bonded_total','duty_paid_total')]
        for aggregate in aggregates:
            selected=[r for r in leaves if aggregate['row_level']!='region_subtotal' or r['region_raw']==aggregate['region_raw']]
            for field in ('quantity','official_delta'):
                total,count,reasons=measurements(selected,field)
                if aggregate['layout_errors']:reasons.append('layout')
                if not selected:reasons.append('no_leaf_coverage')
                if aggregate['row_level'] in ('bonded_total','duty_paid_total'):reasons.append('tax_leaf_coverage')
                if not numeric(aggregate[field]):reasons.append('aggregate_numeric')
                basis=arithmetic_basis(group)
                arithmetic='unknown' if reasons else ('match' if total==Decimal(aggregate[field]['value']) else 'mismatch')
                status='unknown_'+reasons[0] if reasons else (arithmetic if basis=='explicit_declared_unit' else 'unknown_unit')
                checks.append(dict(request_date=aggregate['request_date'],scope_key=key,check_kind='leaf_sum',
                    aggregate_source_row=aggregate['source_row'],aggregate_label=aggregate['aggregate_label'],field=field,
                    basis=basis,status=status,arithmetic_status=arithmetic,computed_sum=str(total),
                    official_value=aggregate[field]['value'],measurement_count=count,physical_leaf_rows=len(selected),reasons=sorted(set(reasons)),
                    physical_unit_certified=basis=='explicit_declared_unit'))
        # Explicit partitions may be summed against a plain total, never as leaves.
        grand=[r for r in aggregates if r['row_level']=='grand_total']
        bonded=[r for r in aggregates if r['row_level']=='bonded_total']
        paid=[r for r in aggregates if r['row_level']=='duty_paid_total']
        if len(grand)==len(bonded)==len(paid)==1:
            for field in ('quantity','official_delta'):
                valid=all(numeric(r[field]) for r in grand+bonded+paid)
                value=Decimal(bonded[0][field]['value'])+Decimal(paid[0][field]['value']) if valid else None
                arith=('match' if value==Decimal(grand[0][field]['value']) else 'mismatch') if valid else 'unknown'
                basis=arithmetic_basis(group)
                checks.append(dict(request_date=grand[0]['request_date'],scope_key=key,check_kind='explicit_partition_sum',aggregate_label='保税+完税→总计',
                    field=field,basis=basis,status=arith if basis=='explicit_declared_unit' else 'unknown_unit',arithmetic_status=arith,
                    computed_sum=str(value) if valid else None,official_value=grand[0][field]['value'],measurement_count=2,
                    tax_leaf_classification_certified=False))
    return checks


def adjacent_checks(previous,current):
    prev,curr=scopes(previous),scopes(current);checks=[]
    for key in sorted(set(prev)|set(curr)):
        pg,cg=prev.get(key,[]),curr.get(key,[])
        template=(cg or pg)[0]
        base=dict(previous_date=previous[0]['request_date'] if previous else None,current_date=current[0]['request_date'] if current else None,
                  scope_key=key,product_raw=template['product_raw'],unit_raw=template['unit_raw'],basis=arithmetic_basis(pg+cg))
        if not pg or not cg or coverage(pg)!=coverage(cg):
            checks.append(dict(base,aggregate_label=None,status='unknown_coverage',arithmetic_status='unknown',
                               reason='format_scope_or_complete_leaf_context_coverage_changed'));continue
        aggregates=lambda g:[r for r in g if r['row_level'] in ('grand_total','region_subtotal','scope_subtotal','bonded_total','duty_paid_total')]
        old=defaultdict(list)
        for row in aggregates(pg):old[(row['row_level'],row['aggregate_label'],row['region_raw'])].append(row)
        for row in aggregates(cg):
            matched=old.get((row['row_level'],row['aggregate_label'],row['region_raw']),[])
            valid=len(matched)==1 and numeric(row['quantity']) and numeric(row['official_delta']) and numeric(matched[0]['quantity'])
            diff=Decimal(row['quantity']['value'])-Decimal(matched[0]['quantity']['value']) if valid else None
            arith=('match' if diff==Decimal(row['official_delta']['value']) else 'mismatch') if valid else 'unknown'
            status=arith if base['basis']=='explicit_declared_unit' else 'unknown_unit'
            checks.append(dict(base,aggregate_label=row['aggregate_label'],aggregate_source_row=row['source_row'],
                status=status,arithmetic_status=arith,previous_quantity=matched[0]['quantity']['value'] if len(matched)==1 else None,
                current_quantity=row['quantity']['value'],computed_difference=str(diff) if valid else None,
                official_delta=row['official_delta']['value'],original_official_delta_replaced=False))
    return checks


def write_json(path,obj):
    with Path(path).open('x') as stream:json.dump(obj,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def write_jsonl(path,records):
    with gzip.open(path,'wt') as stream:
        for record in records:stream.write(canon(record)+'\n')


def actual(output,raw_manifest=RAW_MANIFEST):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write_json(output/'started.json',dict(schema='stage173_started_v1',started_at=datetime.now(timezone.utc).isoformat(),
               implementation=bind(__file__),new_fit=0,new_cash=0,SQL=0,network=0,automatic_retry=False))
    try:
        protocol_bytes=PROTOCOL.read_bytes();manifest_bytes=Path(raw_manifest).read_bytes()
        if digest(protocol_bytes)!=PROTOCOL_SHA or digest(manifest_bytes)!=RAW_MANIFEST_SHA:raise ValueError('frozen172_binding_mismatch')
        protocol=json.loads(protocol_bytes);manifest=json.loads(manifest_bytes)
        artifacts={Path(b['path']).name:b for b in manifest['artifacts']}
        reports=[];schemas=[];bindings=[]
        for request in protocol['requests']:
            date=request['date'];name=date+('.dat' if request['format']=='json' else '.html')
            raw_b=artifacts[name];data=bound_bytes(raw_b);response_b=artifacts[date+'_response.json']
            response=json.loads(bound_bytes(response_b))
            if request['format']=='json':rows,meta=normalize_json(json.loads(data),date)
            else:rows,meta=normalize_html(data.decode('utf-8'),date)
            for row in rows:
                row.update(definition_version=VERSION,report_date_state=meta['date_state'],source_url=request['url'])
            meta.update(raw_binding=raw_b,response_binding=response_b,response_metadata=response)
            schemas.append(meta);reports.append(rows);bindings.extend([raw_b,response_b])
        normalized=[r for rows in reports for r in rows]
        intra=[c for rows in reports for c in intra_checks(rows)]
        adjacent=[c for previous,current in zip(reports,reports[1:]) for c in adjacent_checks(previous,current)]
        write_jsonl(output/'normalized_rows.jsonl.gz',normalized)
        write_jsonl(output/'intra_checks.jsonl.gz',intra)
        write_jsonl(output/'adjacent_checks.jsonl.gz',adjacent)
        write_json(output/'report_schema.json',schemas)
        summary=dict(schema='stage173_warehouse_normalization_summary_v1',reports=len(reports),physical_rows=len(normalized),
            reports_by_date=[dict(date=m['request_date'],format=m['source_format'],rows=m['physical_rows'],tables=m['table_count'],date_state=m['date_state']) for m in schemas],
            products_by_date={m['request_date']:sorted({r['product_raw'] for r in rows if r['product_raw']}) for m,rows in zip(schemas,reports)},
            numeric_states={field:dict(Counter(r[field]['state'] for r in normalized)) for field in ('quantity','official_delta')},
            row_levels=dict(Counter(r['row_level'] for r in normalized)),unit_states=dict(Counter(r['unit_state'] for r in normalized)),
            unit_values=dict(Counter(r['unit_value'] or 'UNKNOWN' for r in normalized)),
            intra_status=dict(Counter(c['status'] for c in intra)),intra_arithmetic=dict(Counter(c['arithmetic_status'] for c in intra)),
            adjacent_status=dict(Counter(c['status'] for c in adjacent)),adjacent_arithmetic=dict(Counter(c['arithmetic_status'] for c in adjacent)),
            strict_first_publication_PIT=False,unit_codebook_bound=False,cross_format_physical_join_certified=False,
            new_fit=0,new_cash=0,SQL=0,network=0,cumulative_fit=409,cumulative_cash=218,financial_authorization=False)
        write_json(output/'summary.json',summary)
        write_json(output/'terminal.json',dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-start,
            reports=len(reports),physical_rows=len(normalized),new_fit=0,new_cash=0,SQL=0,network=0,automatic_retry=False))
        names=('started.json','normalized_rows.jsonl.gz','intra_checks.jsonl.gz','adjacent_checks.jsonl.gz','report_schema.json','summary.json','terminal.json')
        write_json(output/'manifest.json',dict(schema='stage173_warehouse_normalization_manifest_v1',status='completed',
            protocol=dict(path=str(PROTOCOL),bytes=len(protocol_bytes),sha256=PROTOCOL_SHA),
            raw_manifest=dict(path=str(Path(raw_manifest).resolve()),bytes=len(manifest_bytes),sha256=RAW_MANIFEST_SHA),
            inputs=bindings,source_bundle=[bind(__file__),bind(Path(__file__).with_name('test_stage173_warehouse_normalize.py'))],
            artifacts={n:bind(output/n) for n in names},new_fit=0,new_cash=0,SQL=0,network=0,financial_authorization=False))
    except BaseException as exc:
        if not (output/'terminal.json').exists():write_json(output/'terminal.json',dict(status='failed',exit_code=1,error=type(exc).__name__+': '+str(exc),
            traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start,automatic_retry=False))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--raw-manifest',type=Path,default=RAW_MANIFEST);args=parser.parse_args()
    actual(args.output,args.raw_manifest)


if __name__=='__main__':main()
