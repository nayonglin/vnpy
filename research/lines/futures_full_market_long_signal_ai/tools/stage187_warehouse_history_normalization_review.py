"""Independent Stage186 output audit; six fixed raw anchors, no network/finance.

All new normalized streams are read once with compressed-byte hashing. Source
extraction is checked against six mechanically fixed original reports; the
remaining original-body integrity is inherited from accepted181, not rescanned.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import io
import itertools
import json
from pathlib import Path
import re
import time
import traceback

LINE = Path(__file__).resolve().parents[1]
ANCHORS = ('20140519','20231117','20240321','20251124','20251205','20260724')
AUTHOR_SHA = '45525e8500449f2b087dd94d227760bf94b344ab47303257a9adf2fe87cbfa02'
TEST_SHA = 'ae38d66cd3dabd4b00d84f2bade47e8926cf27ca3fe04219048ba645442cf5f6'
OVERLAY_SHA = '4728d646bd949bee21f5a4f8f48e9e898bc25070a0065c628b390304d31c4676'
HELPER_SHA = '350d74fb8373aaa9bd2b980db7c0051efedfd0754225194ff5671ac2972e1db2'
DECISION_SHA = '40787dfd0b4a8bfebe257fbcc9ea397ba982ea76ff9f60305caaab5ba7fbc017'
VERSION = 'stage186_declared_source_scopes_v1'
KEY11 = set('REGNAME REGSORT ROWORDER ROWSTATUS VARNAME VARSORT WGHTUNIT WHABBRNAME WHROWS WRTCHANGE WRTWGHTS'.split())
KEY13 = KEY11 | {'VARID','WHTYPE'}
KEY10 = KEY13 - {'REGSORT','ROWORDER','VARSORT'}


def encoded(value):
    if isinstance(value, Decimal): return format(value, 'f')
    raise TypeError(type(value).__name__)


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=encoded)


def sha(x): return hashlib.sha256(x).hexdigest()
def token_hash(x): return sha(canon(x).encode())


def equal(actual, expected, where):
    if actual != expected:
        raise AssertionError(where + ': differs; actual=' + repr(actual)[:500] + ' expected=' + repr(expected)[:500])


def binding(path):
    p = Path(path).resolve(); b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=sha(b))


def load(ref):
    p = Path(ref['path']); b = p.read_bytes()
    equal(len(b), ref['bytes'], 'bound size ' + str(p)); equal(sha(b), ref['sha256'], 'bound SHA ' + str(p))
    return json.loads(b)


def write(path, x):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(x, f, ensure_ascii=False, indent=2, allow_nan=False, default=encoded); f.write('\n')


def presence(raw, key):
    if key not in raw: return dict(state='absent', raw_type='NOT_DISCLOSED', value=None)
    v = raw[key]
    state = 'null' if v is None else 'empty' if v == '' else 'blank' if isinstance(v,str) and not v.strip() else 'literal'
    return dict(state=state, raw_type=type(v).__name__, value=encoded(v) if isinstance(v,Decimal) else v)


def quantity(v, missing=False):
    decimal_number = isinstance(v,Decimal)
    v = encoded(v) if decimal_number else v
    r = dict(raw=v,raw_type='missing_field' if missing else type(v).__name__,state=None,value=None,method=None)
    if missing: r['state']='missing_field'
    elif v is None: r['state']='null'
    elif isinstance(v,bool): r['state']='parse_failure'
    else:
        t = str(v).strip()
        if not t: r['state']='blank'
        elif t in ('--','-','—','–'): r['state']='placeholder'
        else:
            if re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)',t): method='strict_decimal'
            elif re.fullmatch(r'[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?',t): method='strict_grouped_decimal'
            else: method=None
            if method is None: r['state']='parse_failure'
            else:
                try: d=Decimal(t.replace(',',''))
                except InvalidOperation: d=Decimal('NaN')
                if not d.is_finite(): r['state']='parse_failure'
                else: r.update(state='numeric_zero' if d==0 else 'numeric',value=format(d,'f'),method=method)
    if decimal_number: r.update(raw_type='json_decimal_number',method='exact_JSON_decimal_number')
    return r


def known(cell): return cell['state'] in ('numeric','numeric_zero') and cell['value'] is not None
def literal(t): return t.get('state')=='literal' and isinstance(t.get('value'),(str,int)) and not isinstance(t.get('value'),bool)


def role(label, status=None, fmt='html'):
    s = str(label or '').split('$$',1)[0].strip()
    r = {'总计':'plain_total','合计':'subtotal','小计':'subtotal','保税商品总计':'tax_total',
         '完税商品总计':'tax_total','保税总计':'tax_total','完税总计':'tax_total'}.get(s,'leaf' if s else 'unknown')
    if fmt=='json':
        expected={'leaf':'0','subtotal':'1'}.get(r,'2')
        if r=='unknown' or isinstance(status,bool) or str(status)!=expected: return 'unknown'
    elif r=='leaf' and any(w in s for w in ('总计','小计','合计')): return 'unknown'
    return r


def mapping(fmt, label, date, fields, overlay):
    es=[e for e in overlay['entries'] if e['source_format']==fmt and e['source_label']==label and e['valid_from']<=date<=e['valid_to']]
    state='mapped' if len(es)==1 else 'unknown_ambiguous_entry' if es else 'unknown_no_exact_entry'
    pid=es[0]['mapped_research_product_id'] if state=='mapped' else None
    code=fields['VARID']
    if pid and code['state']!='absent' and (code['state']!='literal' or code['value']!=es[0]['expected_disclosed_VARID']):
        state,pid='unknown_code_conflict',None
    candidates=[pid] if pid else []
    if not candidates and code['state']=='literal' and isinstance(code['value'],str):
        q=overlay.get('disclosed_code_blocking_identities',{}).get(code['value'])
        if q and q['product_id'] in overlay['research_product_ids']: candidates=[q['product_id']]
    return dict(mapped_research_product_id=pid,mapping_state=state,overlay_entry_ids=[e['entry_id'] for e in es],candidate_product_ids=candidates)


def json_rows(raw_rows, date, overlay, raw_types=None):
    result=[]
    for i, raw in enumerate(raw_rows):
        raw=dict(raw)
        if raw_types:
            for k,t in raw_types[i].items():
                if t=='json_decimal_number': raw[k]=Decimal(raw[k])
        fields={k:presence(raw,k) for k in ('VARNAME','WGHTUNIT','VARID','WHTYPE','ROWSTATUS','REGNAME','WHABBRNAME')}
        keys=set(raw);name='legacy11' if keys==KEY11 else 'disclosed13' if keys==KEY13 else 'compact10' if keys==KEY10 else 'unknown'
        version='json_'+name+':'+token_hash(sorted(raw))
        wanted='legacy11' if date<'20231117' else 'disclosed13' if date<'20240321' else 'compact10'
        scope=dict(source_format='json',representation_version=version,source_identity={k:fields[k] for k in ('VARNAME','WGHTUNIT','VARID','WHTYPE')})
        r=dict(request_date=date,source_format='json',source_row=i,table_index=None,table_row=i,
            representation_version=version,scope_identity=scope,product_raw=raw.get('VARNAME'),field_states=fields,
            unit_token=fields['WGHTUNIT'],physical_unit=None,physical_type=None,unit_state='original_code_unmapped',
            type_state='original_code_unmapped' if 'WHTYPE' in raw else 'NOT_DISCLOSED',row_level=role(raw.get('WHABBRNAME'),raw.get('ROWSTATUS'),'json'),
            aggregate_label=raw.get('WHABBRNAME'),region_raw=raw.get('REGNAME'),warehouse_raw=raw.get('WHABBRNAME'),
            quantity=quantity(raw.get('WRTWGHTS'),'WRTWGHTS' not in raw),official_delta=quantity(raw.get('WRTCHANGE'),'WRTCHANGE' not in raw),
            quantity_field_name='WRTWGHTS',delta_field_name='WRTCHANGE',location_field_name='WHABBRNAME',
            quantity_origin=f'json:{i}:WRTWGHTS',delta_origin=f'json:{i}:WRTCHANGE',quantity_inherited=False,delta_inherited=False,
            context={k:fields[k] for k in ('REGNAME','WHABBRNAME')},raw_fields=json.loads(canon(raw)),
            raw_field_types={k:'json_decimal_number' if isinstance(v,Decimal) else type(v).__name__ for k,v in raw.items()},
            layout_errors=[] if name==wanted else ['unknown_or_out_of_regime_keyset'])
        r.update(mapping('json',r['product_raw'],date,fields,overlay)); result.append(r)
    return result


class PhysicalHTML(HTMLParser):
    """Independent anchor-only physical table extraction; never executes HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.tables=[];self.table=self.row=self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            if self.table is not None: raise AssertionError('nested anchor table')
            self.table=dict(attrs=dict(attrs),rows=[]);self.tables.append(self.table)
        elif tag=='tr' and self.table is not None:
            self.row=dict(attrs=dict(attrs),cells=[]);self.table['rows'].append(self.row)
        elif tag in ('td','th') and self.row is not None:
            self.cell=dict(tag=tag,attrs=dict(attrs),raw_text='',line=self.getpos()[0],start_tag=self.get_starttag_text());self.row['cells'].append(self.cell)
        elif tag=='br' and self.cell is not None: self.cell['raw_text']+='\n'
    def handle_data(self,data):
        if self.cell is not None: self.cell['raw_text']+=data
    def handle_endtag(self,tag):
        if tag in ('td','th'): self.cell=None
        elif tag=='tr': self.row=None
        elif tag=='table': self.table=self.row=self.cell=None


def expand(physical, ti):
    occupied={};errors=[];rows=[]
    for ri, row in enumerate(physical['rows']):
        cells=[];col=0
        for ci, old in enumerate(row['cells']):
            c={k:old[k] for k in ('tag','attrs','raw_text','line','start_tag')}
            c['text']=re.sub(r'\s+',' ',c['raw_text']).strip()
            while (ri,col) in occupied: col+=1
            spans=[]
            for name in ('rowspan','colspan'):
                text=c['attrs'].get(name,'1')
                if not re.fullmatch(r'[0-9]+',text) or not 1<=int(text)<=2048: errors.append('invalid_'+name);spans.append(1)
                else: spans.append(int(text))
            rs,cs=spans;c.update(rowspan=rs,colspan=cs,logical_column=col,origin=f'html:{ti}:{ri}:{ci}')
            for rr in range(rs):
                for cc in range(cs):
                    key=(ri+rr,col+cc)
                    if key in occupied: errors.append('overlapping_span')
                    else: occupied[key]=dict(text=c['text'],origin=c['origin'],origin_row=ri,origin_cell=ci,inherited_row=rr>0,colspan=cs,rowspan=rs)
            col+=cs;cells.append(c)
        rows.append(dict(attrs=row['attrs'],cells=cells))
    for ri,row in enumerate(rows):
        cols=[c for rr,c in occupied if rr==ri]
        row['grid']=[occupied.get((ri,c)) for c in range(max(cols)+1)] if cols else []
    return dict(attrs=physical['attrs'],rows=rows,errors=errors)


def html_rows(tables, date, overlay):
    output=[];meta=[]
    for ti,physical in enumerate(tables):
        t=expand(physical,ti);lookup={c['origin']:c for r in t['rows'] for c in r['cells']}
        headers=[[g['text'] if g else None for g in r['grid']] for r in t['rows'] if r['cells'] and all(c['tag']=='th' for c in r['cells'])]
        version='html_table_headers:'+token_hash(headers)
        names=[];product=None;unit={};occ=-1;intro='content_intro' in t['attrs'].get('class','').split()
        for ri,row in enumerate(t['rows']):
            cells,grid=row['cells'],row['grid'];header=bool(cells) and all(c['tag']=='th' for c in cells)
            uc=[c for c in cells if re.fullmatch(r'单位\s*[:：]\s*(.+)',c['text'])]
            if header: names=[g['text'] if g else '' for g in grid];occ+=1
            if uc:
                other=[c for c in cells if c not in uc];product=other[0]['raw_text'] if len(other)==1 else None
                unit={'unit':uc[0]['raw_text']} if len(uc)==1 else {}
            def at(name):
                ix=[j for j,n in enumerate(names) if n==name]
                return grid[ix[0]] if len(ix)==1 and ix[0]<len(grid) else None
            def raw(c): return lookup[c['origin']]['raw_text'] if c else None
            qn=next((n for n in ('期货','本日数量') if n in names),None);ln=next((n for n in ('仓库','厂库','交割仓库') if n in names),None)
            q,d,l,reg=at(qn),at('增减'),at(ln),at('地区');merged=bool(reg and l and reg['origin']==l['origin'])
            agg=[c['raw_text'] for c in cells if role(c['raw_text']) not in ('leaf','unknown')]
            label=agg[0] if len(agg)==1 else raw(l)
            lev='intro' if intro else 'column_header' if header else 'section_header' if uc else role(label)
            if not product and lev not in ('intro','column_header','section_header'): lev='unknown'
            context={}
            for n in dict.fromkeys(names):
                if n not in ('期货','本日数量','上日数量','昨日数量','增减'):
                    c=at(n);context[n]=presence({'value':raw(c)},'value') if c else presence({},'value')
            fields={k:presence({},k) for k in ('VARID','WHTYPE')}
            fields.update(VARNAME=presence({'VARNAME':product},'VARNAME') if product is not None else presence({},'VARNAME'),WGHTUNIT=presence(unit,'unit'))
            scope=dict(source_format='html',representation_version=version,table_index=ti,source_identity={k:fields[k] for k in ('VARNAME','WGHTUNIT','VARID','WHTYPE')})
            errs=list(t['errors'])
            if any(c['origin_row']+c['rowspan']>len(t['rows']) for c in grid if c): errs.append('span_outside_physical_rows')
            if len(agg)>1: errs.append('ambiguous_aggregate_label')
            x=dict(request_date=date,source_format='html',source_row=len(output),table_index=ti,table_row=ri,representation_version=version,
                scope_identity=scope,product_raw=product,field_states=fields,unit_token=fields['WGHTUNIT'],physical_unit=None,physical_type=None,
                unit_state='explicit_declared_text' if unit else 'unknown',type_state='not_inferred',row_level=lev,aggregate_label=label,
                region_raw=None if merged else raw(reg),warehouse_raw=raw(l),region_state='merged_with_location_unknown' if merged else 'original_or_explicit_span',
                quantity=quantity(raw(q),q is None),official_delta=quantity(raw(d),d is None),quantity_field_name=qn,
                delta_field_name='增减' if '增减' in names else None,location_field_name=ln,quantity_origin=q['origin'] if q else None,
                delta_origin=d['origin'] if d else None,quantity_inherited=q['inherited_row'] if q else False,delta_inherited=d['inherited_row'] if d else False,
                context=context,raw_cells=cells,logical_grid=grid,table_attrs=t['attrs'],row_attrs=row['attrs'],header_occurrence=occ,active_headers=list(names),layout_errors=errs)
            x.update(mapping('html',product,date,fields,overlay));output.append(x)
        meta.append(dict(table_index=ti,table_attrs=t['attrs'],physical_rows=len(t['rows']),ordered_header_regimes=headers,representation_version=version,layout_errors=t['errors']))
    return output,meta


def scope_rows(rows):
    groups=defaultdict(list)
    for r in rows:
        sid=None if r['row_level'] in ('intro','column_header','section_header') else token_hash(r['scope_identity'])
        r['scope_id']=sid
        if sid is not None: groups[sid].append(r)
    result=[]
    for sid,rs in sorted(groups.items()):
        first=rs[0];totals=[r for r in rs if r['row_level']=='plain_total'];leaves=[r for r in rs if r['row_level']=='leaf'];reasons=[]
        if len(totals)!=1: reasons.append('nonunique_plain_total')
        if not leaves: reasons.append('no_leaf_coverage')
        if any(r['row_level']=='unknown' for r in rs): reasons.append('unknown_source_role')
        if any(r['layout_errors'] for r in rs): reasons.append('layout_or_representation_unknown')
        if not literal(first['unit_token']): reasons.append('unknown_unit_token')
        if not literal(first['field_states']['VARNAME']): reasons.append('unknown_product_literal')
        origins=defaultdict(list);identities=defaultdict(set)
        for r in leaves:
            o=r['quantity_origin'];origins[o].append(r);identities[canon(r['context'])].add(o)
            if o is None or not r['context']: reasons.append('incomplete_leaf_identity_or_origin')
            if not known(r['quantity']): reasons.append('unknown_leaf_quantity')
            elif Decimal(r['quantity']['value'])<0: reasons.append('negative_quantity')
        if any(len(v)>1 for v in identities.values()): reasons.append('duplicate_leaf_identity')
        ms=[];coverage=[];total_leaf=Decimal(0);all_known=bool(leaves)
        for origin,members in origins.items():
            vals={r['quantity']['value'] for r in members};ok=origin is not None and len(vals)==1 and all(known(r['quantity']) for r in members)
            if len(vals)!=1: reasons.append('conflicting_shared_quantity_origin')
            cov=[json.loads(c) for c in sorted({canon(dict(context=r['context'],quantity_field_name=r['quantity_field_name'])) for r in members})]
            coverage.append(cov);value=members[0]['quantity']['value'];all_known=all_known and ok
            if ok: total_leaf+=Decimal(value)
            ms.append(dict(quantity_origin=origin,source_rows=[r['source_row'] for r in members],coverage_contexts=cov,quantity_value=value if ok else None,quantity_state=members[0]['quantity']['state']))
        total=totals[0] if len(totals)==1 else None
        if total and total['quantity_origin'] in origins: reasons.append('total_leaf_origin_overlap')
        if total and not known(total['quantity']): reasons.append('unknown_total_quantity')
        if total and known(total['quantity']) and Decimal(total['quantity']['value'])<0: reasons.append('negative_quantity')
        ar=('match' if total_leaf==Decimal(total['quantity']['value']) else 'mismatch') if all_known and total and known(total['quantity']) else 'unknown'
        if ar!='match': reasons.append('leaf_total_arithmetic_'+ar)
        sr=sorted(set(reasons))
        if first['mapping_state']!='mapped': reasons.append('research_mapping_unknown')
        x=dict(schema='stage186_scope_observation_v1',request_date=first['request_date'],source_format=first['source_format'],scope_id=sid,
            scope_identity=first['scope_identity'],representation_version=first['representation_version'],product_raw=first['product_raw'],
            mapped_research_product_id=first['mapped_research_product_id'],mapping_state=first['mapping_state'],overlay_entry_ids=first['overlay_entry_ids'],
            candidate_product_ids=first['candidate_product_ids'],required=True,status='unknown' if reasons else 'conditional_source_qualified',reasons=sorted(set(reasons)),
            source_group_status='unknown' if sr else 'conditionally_identified_source_rows',source_reasons=sr,
            quantity_value=total['quantity']['value'] if total else None,official_delta_value=total['official_delta']['value'] if total else None,
            ordinary_total_count=len(totals),ordinary_total_source_rows=[r['source_row'] for r in totals],
            ordinary_total={k:total[k] for k in ('source_row','quantity','official_delta','quantity_origin','delta_origin','aggregate_label')} if total else None,
            all_source_rows=[r['source_row'] for r in rs],source_leaf_row_count=len(leaves),leaf_measurement_count=len(origins),leaf_measurements=ms,
            leaf_sum_quantity=str(total_leaf) if all_known else None,quantity_arithmetic_status=ar,leaf_coverage_fingerprint=token_hash(sorted(coverage,key=canon)),
            coverage_state='unknown' if sr else 'complete_nonduplicated_source_rows',physical_unit_certified=False,physical_type_certified=False,
            physical_goods_disjointness_certified=False,conditional_same_object_same_positive_scale_assumption=True)
        result.append(x)
    return result


def product_rows(scopes,date,overlay):
    unresolved=sorted(s['scope_id'] for s in scopes if not s['candidate_product_ids']);result=[]
    for pid in overlay['research_product_ids']:
        req=[s for s in scopes if s['mapped_research_product_id']==pid or pid in s['candidate_product_ids']]
        bad=sorted(s['scope_id'] for s in req if s['status']!='conditional_source_qualified');complete=bool(req) and not unresolved
        result.append(dict(schema='stage186_product_scope_status_v1',request_date=date,mapped_research_product_id=pid,
            status='unknown_no_source_scope' if not req else 'unknown' if bad or not complete else 'conditional_all_required_scopes_qualified',
            applicability_state='reported_source_groups' if req else 'unknown_not_certified',required_scope_ids=sorted(s['scope_id'] for s in req),required_scope_count=len(req),
            bad_scope_ids=bad,scope_membership_complete=complete,unresolved_report_scope_ids=unresolved,
            reasons=(['no_source_scope'] if not req else [])+(['bad_required_scope'] if bad else [])+(['unresolved_report_scope_membership'] if unresolved else []),
            physical_goods_disjointness_certified=False,strict_PIT=False))
    return result


class HashInput:
    def __init__(self,f): self.f=f;self.h=hashlib.sha256();self.n=0
    def read(self,size=-1):
        b=self.f.read(size);self.h.update(b);self.n+=len(b);return b


@contextmanager
def stream(ref):
    with Path(ref['path']).open('rb') as raw:
        hashed=HashInput(raw)
        with gzip.GzipFile(fileobj=hashed,mode='rb') as z, io.TextIOWrapper(z,encoding='utf-8') as text:
            yield (json.loads(line) for line in text)
        equal(hashed.n,ref['bytes'],'compressed stream bytes');equal(hashed.h.hexdigest(),ref['sha256'],'compressed stream SHA')


class DateGroups:
    def __init__(self,it): self.it=iter(it);self.next=next(self.it,None)
    def take(self,date):
        result=[]
        while self.next is not None and self.next['request_date']==date:
            result.append(self.next);self.next=next(self.it,None)
        return result
    def end(self): equal(self.next,None,'unexpected trailing report records')


def embedded_tables(rows):
    tables=[]
    for ti, group in itertools.groupby(rows,key=lambda r:r['table_index']):
        equal(ti,len(tables),'physical table order');rs=list(group)
        for j,r in enumerate(rs): equal(r['table_row'],j,'physical table row order')
        tables.append(dict(attrs=rs[0]['table_attrs'],rows=[dict(attrs=r['row_attrs'],cells=r['raw_cells']) for r in rs]))
    return tables


def review(args):
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False);clock=time.monotonic()
    mr=binding(args.manifest);equal(mr['sha256'],args.manifest_sha256,'exact root subject manifest')
    source=[binding(__file__),binding(Path(__file__).with_name('test_stage187_warehouse_history_normalization_review.py'))]
    receipt=dict(schema='stage187_registration_normalization_review_v1',accepted=False,C=0,I=0,M=0,errors=[],normalization_manifest=mr,
        source_bundle=source,new_fit=0,new_cash=0,SQL=0,network=0,scalar_computed=False,raw_full_rescan=False,
        strict_PIT=False,physical_unit_type_certified=False,physical_goods_disjointness_certified=False,normalization_is_feature_authorization=False,
        cumulative_fit=409,cumulative_cash=218,automatic_retry=False,raw_anchor_dates=list(ANCHORS),raw_anchor_reads=0)
    write(output/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),normalization_manifest=mr,source_bundle=source,raw_anchor_dates=list(ANCHORS)))
    try:
        norm=load(mr);equal(norm['schema'],'stage186_warehouse_history_normalization_manifest_v1','norm schema');equal(norm['status'],'completed','norm status')
        terminal=load(norm['terminal']);equal((terminal['status'],terminal['exit_code']),('completed',0),'186 terminal')
        for k in ('new_fit','new_cash','SQL','network','new_labels','new_prices'): equal(norm[k],0,'norm zero '+k)
        equal(norm['strict_PIT'],False,'PIT');equal(norm['scalar_computed'],False,'no scalar')
        decision=load(norm['decision']);equal(norm['decision']['sha256'],DECISION_SHA,'185 frozen')
        equal(norm['archive_manifest'],decision['bindings']['archive_manifest'],'185 same archive')
        accepted=load(decision['bindings']['independent_receipt']);equal(accepted['completed'],True,'accepted181');equal([accepted[k] for k in ('C','I','M')],[0,0,0],'181 findings')
        ar=load(norm['archive_manifest']);equal(norm['date_manifest'],ar['date_manifest'],'same date manifest')
        requests=load(norm['date_manifest']);equal(len(requests),3018,'report domain')
        plan=load(norm['plan']);equal(norm['calender'],plan['input_metadata']['calendar'],'calendar binding')
        equal([r['date'] for r in requests],plan['frozen_candidate_domain']['dates'],'ordered full dates')
        equal(norm['product_overlay']['sha256'],OVERLAY_SHA,'overlay frozen');overlay=load(norm['product_overlay'])
        equal(len(overlay['research_product_ids']),98,'all products');equal(len(set(overlay['research_product_ids'])),98,'unique products')
        for r,s in zip(norm['source_bundle'],(AUTHOR_SHA,TEST_SHA,HELPER_SHA)):
            equal(r['sha256'],s,'author dependency frozen');load_bytes=Path(r['path']).read_bytes();equal(sha(load_bytes),s,'author current SHA')
        equal(len(norm['source_bundle']),3,'author dependency count')
        write(output/'input_closure_checkpoint.json',dict(completed=True,normalization_manifest=mr,accepted181=decision['bindings']['independent_receipt'],archive_manifest=norm['archive_manifest'],raw_anchors=list(ANCHORS)))
        counts=Counter();numbers=defaultdict(Counter);reasons=Counter();years=defaultdict(Counter);products=defaultdict(Counter);anchor_bindings=[]
        with stream(norm['normalized_rows']) as rowit,stream(norm['scope_observations']) as scopeit,stream(norm['product_scope_status']) as productit,stream(norm['report_schema']) as schemait:
            rowgroups=DateGroups(rowit);scopegroups=DateGroups(scopeit);productgroups=DateGroups(productit)
            for request in requests:
                date=request['date'];actual=rowgroups.take(date);saved_scopes=scopegroups.take(date);saved_products=productgroups.take(date);saved_schema=next(schemait)
                equal(saved_schema['request_date'],date,'schema date');equal(saved_schema['source_format'],request['format'],'schema format')
                equal(saved_schema['raw_binding'],request['body'],'raw bound identity');equal(saved_schema['source_url'],request['url'],'schema URL')
                equal(saved_schema['original_response_binding'],request.get('response'),'response binding');equal(saved_schema['archive_report_date_state'],request.get('date_state'),'archive body date state')
                equal(saved_schema['definition_version'],VERSION,'definition')
                anchor=None
                if date in ANCHORS:
                    b=Path(request['body']['path']).read_bytes();equal(len(b),request['body']['bytes'],'anchor bytes');equal(sha(b),request['body']['sha256'],'anchor SHA')
                    anchor=json.loads(b,parse_float=Decimal) if request['format']=='json' else b.decode('utf-8-sig')
                    anchor_bindings.append(dict(date=date,body=request['body']));receipt['raw_anchor_reads']+=1
                if request['format']=='json':
                    raw=anchor['o_cursor'] if anchor is not None else [r['raw_fields'] for r in actual]
                    types=None if anchor is not None else [r['raw_field_types'] for r in actual]
                    derived=json_rows(raw,date,overlay,types)
                    expected_schema=dict(tables=None,representation_versions=sorted({r['representation_version'] for r in derived}))
                    if anchor is not None: equal(saved_schema['raw_metadata'],json.loads(canon({k:v for k,v in anchor.items() if k!='o_cursor'})),'anchor JSON metadata')
                else:
                    if anchor is not None:
                        p=PhysicalHTML();p.feed(anchor);p.close();tables=p.tables
                    else: tables=embedded_tables(actual)
                    derived,tables_meta=html_rows(tables,date,overlay)
                    expected_schema=dict(tables=tables_meta,representation_versions=sorted({r['representation_version'] for r in derived}))
                equal(saved_schema['physical_rows'],len(derived),'complete physical row count')
                for k,v in expected_schema.items(): equal(saved_schema[k],v,'report schema '+k)
                expected_scopes=scope_rows(derived);expected_products=product_rows(expected_scopes,date,overlay)
                equal(len(actual),len(derived),'all physical rows')
                for i,(a,e) in enumerate(zip(actual,derived)):
                    e.update(definition_version=VERSION,source_url=request['url']);equal(a,e,f'{date} row {i}')
                    counts['physical_rows']+=1;counts['row_role:'+e['row_level']]+=1
                    for k in ('quantity','official_delta'): numbers[k][e[k]['state']]+=1
                equal(saved_scopes,expected_scopes,date+' all scope fields')
                for s in expected_scopes:
                    counts['scopes']+=1;counts['scope_status:'+s['status']]+=1;reasons.update(s['reasons'])
                equal(saved_products,expected_products,date+' full98 product statuses')
                for p in expected_products:
                    counts['product_day_rows']+=1;years[date[:4]][p['status']]+=1;products[p['mapped_research_product_id']][p['status']]+=1
                counts['reports']+=1;counts['format:'+request['format']]+=1
                if counts['reports']%250==0: print(canon(dict(phase='all_normalized_outputs',reports=counts['reports'],rows=counts['physical_rows'])),flush=True)
            rowgroups.end();scopegroups.end();productgroups.end();equal(next(schemait,None),None,'no trailing schemas')
        receipt.update(all_reports=counts['reports'],all_physical_rows=counts['physical_rows'],numeric_fields_checked=sum(sum(v.values()) for v in numbers.values()),
            all_scopes=counts['scopes'],all_product_statuses=counts['product_day_rows'],anchor_bindings=anchor_bindings,
            normalized_streams_each_read_once=True,output_hashes_verified_in_same_stream=True,raw_nonsampled_bodies_reread=0)
        write(output/'output_rows_checkpoint.json',dict(completed=True,normalization_manifest=mr,counts=dict(counts),raw_anchors=anchor_bindings,numeric_fields_checked=receipt['numeric_fields_checked']))
        summary=load(norm['summary']);equal(summary['counts'],dict(counts),'summary counts');equal(norm['counts'],dict(counts),'manifest counts')
        equal(summary['numeric_states'],{k:dict(v) for k,v in numbers.items()},'numeric summary');equal(summary['scope_unknown_reasons'],dict(reasons),'unknown reasons')
        equal(summary['product_status_by_year'],{k:dict(v) for k,v in years.items()},'year summary');equal(summary['product_status_by_product'],{k:dict(v) for k,v in products.items()},'product summary')
        equal(counts['product_day_rows'],3018*98,'complete product-day domain');equal(receipt['raw_anchor_reads'],6,'only mechanical six raw anchors')
        receipt.update(accepted=True,counts=dict(counts),numeric_states={k:dict(v) for k,v in numbers.items()},scope_unknown_reasons=dict(reasons),
            original_body_extraction_verified='six fixed anchors only; remaining raw integrity inherited accepted181',
            normalized_all_rows_semantics_recomputed=True,financial_authorization=False,feature_projection_authorization=False)
    except BaseException as e:
        receipt.update(I=1,errors=[dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())]);raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-clock;write(output/'receipt.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',required=True)
    r=review(p.parse_args());print(canon(dict(accepted=r['accepted'],C=r['C'],I=r['I'],M=r['M'],reports=r.get('all_reports'),rows=r.get('all_physical_rows'))),flush=True)


if __name__=='__main__': main()
