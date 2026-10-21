"""Fixed3018 source-only warehouse normalization. No network/scalar/model/cash.

The raw source scope and the retrospective exact research identity overlay are
separate. Unknown physical units/types and absent original fields stay unknown.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import traceback
import stage173_warehouse_normalize as base

LINE = Path(__file__).resolve().parents[1]
DECISION = LINE/'outputs/stage185_warehouse_history_decision/decision.json'
DECISION_SHA = '40787dfd0b4a8bfebe257fbcc9ea397ba982ea76ff9f60305caaab5ba7fbc017'
OVERLAY = LINE/'outputs/stage186_warehouse_history_normalize/product_overlay.json'
OVERLAY_SHA = '4728d646bd949bee21f5a4f8f48e9e898bc25070a0065c628b390304d31c4676'
HELPER_SHA = '350d74fb8373aaa9bd2b980db7c0051efedfd0754225194ff5671ac2972e1db2'
VERSION = 'stage186_declared_source_scopes_v1'
KEYS11 = {'REGNAME','REGSORT','ROWORDER','ROWSTATUS','VARNAME','VARSORT','WGHTUNIT','WHABBRNAME','WHROWS','WRTCHANGE','WRTWGHTS'}
KEYS13 = KEYS11 | {'VARID','WHTYPE'}
KEYS10 = KEYS13 - {'REGSORT','ROWORDER','VARSORT'}
ZERO = dict(new_fit=0, new_cash=0, SQL=0, network=0, new_labels=0, new_prices=0,
            scalar_computed=False, strict_PIT=False, financial_authorization=False)


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
                      default=decimal_encoding)


def decimal_encoding(value):
    if isinstance(value,Decimal):return format(value,'f')
    raise TypeError('unsupported source value '+type(value).__name__)


def decode_json(raw):
    return json.loads(raw,parse_float=Decimal)


def quantity_cell(value, missing=False):
    if isinstance(value,Decimal):
        result=base.decimal_cell(format(value,'f'),missing)
        result.update(raw_type='json_decimal_number',method='exact_JSON_decimal_number')
        return result
    return base.decimal_cell(value,missing)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def identity(value):
    return digest(canon(value).encode())


def field_state(raw, key):
    if key not in raw:
        return dict(state='absent', raw_type='NOT_DISCLOSED', value=None)
    value = raw[key]
    state = ('null' if value is None else 'empty' if value == '' else
             'blank' if isinstance(value, str) and not value.strip() else 'literal')
    return dict(state=state, raw_type=type(value).__name__, value=value)


def literal(token):
    return token.get('state') == 'literal' and isinstance(token.get('value'), (str,int)) and not isinstance(token.get('value'), bool)


def schema_version(keys):
    keyset = set(keys)
    name = ('legacy11' if keyset == KEYS11 else 'disclosed13' if keyset == KEYS13 else
            'compact10' if keyset == KEYS10 else 'unknown')
    return 'json_' + name + ':' + identity(sorted(keys))


def map_product(fmt, label, date, fields, overlay):
    matches = [e for e in overlay['entries'] if e['source_format'] == fmt and e['source_label'] == label
               and e['valid_from'] <= date <= e['valid_to']]
    state = 'unknown_no_exact_entry' if not matches else 'unknown_ambiguous_entry' if len(matches) != 1 else 'mapped'
    pid = matches[0]['mapped_research_product_id'] if state == 'mapped' else None
    code = fields.get('VARID', dict(state='absent', value=None))
    if state == 'mapped' and code['state'] != 'absent' and (
            code['state'] != 'literal' or code['value'] != matches[0]['expected_disclosed_VARID']):
        state, pid = 'unknown_code_conflict', None
    candidates = [pid] if pid else []
    if not candidates and code['state'] == 'literal':
        candidate = overlay.get('disclosed_code_blocking_identities', {}).get(code['value']) if isinstance(code['value'], str) else None
        if candidate and candidate['product_id'] in overlay['research_product_ids']:
            candidates = [candidate['product_id']]
    return dict(mapped_research_product_id=pid, mapping_state=state,
                overlay_entry_ids=[e['entry_id'] for e in matches], candidate_product_ids=candidates)


def source_role(label, status=None, fmt='html'):
    # Classification labels are separate from exact, unmodified product identities.
    name = base.display(label)
    roles = {'总计':'plain_total', '合计':'subtotal', '小计':'subtotal',
             '保税商品总计':'tax_total', '完税商品总计':'tax_total', '保税总计':'tax_total', '完税总计':'tax_total'}
    role = roles.get(name, 'leaf' if name else 'unknown')
    if fmt == 'json':
        expected = '0' if role == 'leaf' else '1' if role == 'subtotal' else '2'
        if role == 'unknown' or isinstance(status, bool) or str(status) != expected:
            return 'unknown'
    elif role == 'leaf' and any(word in name for word in ('总计','小计','合计')):
        return 'unknown'
    return role


def normalize_json(obj, date, overlay):
    if not isinstance(obj, dict) or not isinstance(obj.get('o_cursor'), list):
        raise ValueError('unexpected_bound_json_envelope')
    rows = []
    for index, raw in enumerate(obj['o_cursor']):
        if not isinstance(raw, dict):
            rows.append(dict(request_date=date, source_format='json', source_row=index,
                             row_level='unknown', raw_fields=raw, scope_identity=dict(source_format='json', representation_version='unknown_nonobject', raw_row_identity=index),
                             field_states={}, product_raw=None, quantity=base.decimal_cell(None, True),
                             official_delta=base.decimal_cell(None, True), quantity_origin=None, delta_origin=None,
                             context={}, layout_errors=['nonobject_source_row'], mapped_research_product_id=None,
                             mapping_state='unknown_nonobject', overlay_entry_ids=[], candidate_product_ids=[]))
            continue
        fields = {key:field_state(raw,key) for key in ('VARNAME','WGHTUNIT','VARID','WHTYPE','ROWSTATUS','REGNAME','WHABBRNAME')}
        version = schema_version(raw.keys())
        expected = 'legacy11' if date < '20231117' else 'disclosed13' if date < '20240321' else 'compact10'
        errors = [] if version.startswith('json_'+expected+':') else ['unknown_or_out_of_regime_keyset']
        label = raw.get('VARNAME')
        scope = dict(source_format='json', representation_version=version,
                     source_identity={k:fields[k] for k in ('VARNAME','WGHTUNIT','VARID','WHTYPE')})
        role = source_role(raw.get('WHABBRNAME'), raw.get('ROWSTATUS'), 'json')
        row = dict(request_date=date, source_format='json', source_row=index, table_index=None, table_row=index,
                   representation_version=version, scope_identity=scope, product_raw=label, field_states=fields,
                   unit_token=fields['WGHTUNIT'], physical_unit=None, physical_type=None,
                   unit_state='original_code_unmapped', type_state='original_code_unmapped' if 'WHTYPE' in raw else 'NOT_DISCLOSED',
                   row_level=role, aggregate_label=raw.get('WHABBRNAME'), region_raw=raw.get('REGNAME'), warehouse_raw=raw.get('WHABBRNAME'),
                   quantity=quantity_cell(raw.get('WRTWGHTS'), 'WRTWGHTS' not in raw),
                   official_delta=quantity_cell(raw.get('WRTCHANGE'), 'WRTCHANGE' not in raw),
                   quantity_field_name='WRTWGHTS', delta_field_name='WRTCHANGE', location_field_name='WHABBRNAME',
                   quantity_origin=f'json:{index}:WRTWGHTS', delta_origin=f'json:{index}:WRTCHANGE',
                   quantity_inherited=False, delta_inherited=False,
                   context={k:fields[k] for k in ('REGNAME','WHABBRNAME')}, raw_fields=raw,
                   raw_field_types={k:'json_decimal_number' if isinstance(v,Decimal) else type(v).__name__ for k,v in raw.items()},
                   layout_errors=errors)
        row.update(map_product('json', label, date, fields, overlay))
        rows.append(row)
    return rows, dict(request_date=date, source_format='json', physical_rows=len(rows),
                      raw_metadata={k:v for k,v in obj.items() if k!='o_cursor'},
                      representation_versions=sorted({r.get('representation_version','unknown_nonobject') for r in rows}),
                      tables=None)


def normalize_html(text, date, overlay):
    parser = base.TableParser();parser.feed(text);parser.close()
    tables = [base.expand_table(t,i) for i,t in enumerate(parser.tables)]
    rows, metadata = [], []
    for ti, table in enumerate(tables):
        cells_by_origin = {c['origin']:c for r in table['rows'] for c in r['cells']}
        header_rows = [r for r in table['rows'] if r['cells'] and all(c['tag']=='th' for c in r['cells'])]
        header_patterns = [[g['text'] if g else None for g in r['grid']] for r in header_rows]
        version = 'html_table_headers:' + identity(header_patterns)
        product = None;unit = {};names = [];header_occurrence = -1
        intro = 'content_intro' in table['attrs'].get('class','').split()
        for ri, physical in enumerate(table['rows']):
            cells, grid = physical['cells'], physical['grid']
            is_header = bool(cells) and all(c['tag']=='th' for c in cells)
            unit_cells = [c for c in cells if re.fullmatch(r'单位\s*[:：]\s*(.+)', c['text'])]
            section = bool(unit_cells)
            if is_header:
                names = [g['text'] if g else '' for g in grid];header_occurrence += 1
            if section:
                others = [c for c in cells if c not in unit_cells]
                product = others[0]['raw_text'] if len(others)==1 else None
                unit = {'unit':unit_cells[0]['raw_text']} if len(unit_cells)==1 else {}
            positions = defaultdict(list)
            for i,name in enumerate(names):
                positions[name].append(i)
            def at(name):
                inds = positions.get(name,[])
                return grid[inds[0]] if len(inds)==1 and inds[0]<len(grid) else None
            def original(cell):
                return cells_by_origin[cell['origin']]['raw_text'] if cell else None
            qname = next((n for n in ('期货','本日数量') if n in positions), None)
            lname = next((n for n in ('仓库','厂库','交割仓库') if n in positions), None)
            q, delta, location, region = at(qname), at('增减'), at(lname), at('地区')
            merged = bool(region and location and region['origin']==location['origin'])
            warehouse = original(location)
            region_raw = None if merged else original(region)
            physical_labels = [c['raw_text'] for c in cells if source_role(c['raw_text']) not in ('leaf','unknown')]
            label = physical_labels[0] if len(physical_labels)==1 else warehouse
            role = ('intro' if intro else 'column_header' if is_header else 'section_header' if section else source_role(label))
            if not product and role not in ('intro','column_header','section_header'):
                role = 'unknown'
            context = {}
            for name in positions:
                if name not in ('期货','本日数量','上日数量','昨日数量','增减'):
                    cell = at(name)
                    context[name] = field_state({'value':original(cell)},'value') if cell else field_state({},'value')
            fields = {k:field_state({},k) for k in ('VARID','WHTYPE')}
            fields['VARNAME'] = field_state({'VARNAME':product},'VARNAME') if product is not None else field_state({},'VARNAME')
            fields['WGHTUNIT'] = field_state(unit,'unit')
            scope = dict(source_format='html', representation_version=version, table_index=ti,
                         source_identity={k:fields[k] for k in ('VARNAME','WGHTUNIT','VARID','WHTYPE')})
            errors = list(table['errors'])
            if any(c['origin_row']+c['rowspan']>len(table['rows']) for c in grid if c):
                errors.append('span_outside_physical_rows')
            if len(physical_labels)>1:
                errors.append('ambiguous_aggregate_label')
            row = dict(request_date=date, source_format='html', source_row=len(rows), table_index=ti, table_row=ri,
                       representation_version=version, scope_identity=scope, product_raw=product, field_states=fields,
                       unit_token=fields['WGHTUNIT'], physical_unit=None, physical_type=None,
                       unit_state='explicit_declared_text' if unit else 'unknown', type_state='not_inferred',
                       row_level=role, aggregate_label=label, region_raw=region_raw, warehouse_raw=warehouse,
                       region_state='merged_with_location_unknown' if merged else 'original_or_explicit_span',
                       quantity=base.decimal_cell(original(q), q is None), official_delta=base.decimal_cell(original(delta), delta is None),
                       quantity_field_name=qname, delta_field_name='增减' if '增减' in positions else None, location_field_name=lname,
                       quantity_origin=q['origin'] if q else None, delta_origin=delta['origin'] if delta else None,
                       quantity_inherited=q['inherited_row'] if q else False, delta_inherited=delta['inherited_row'] if delta else False,
                       context=context, raw_cells=cells, logical_grid=grid, table_attrs=table['attrs'], row_attrs=physical['attrs'],
                       header_occurrence=header_occurrence, active_headers=list(names), layout_errors=errors)
            row.update(map_product('html', product, date, fields, overlay))
            rows.append(row)
        metadata.append(dict(table_index=ti, table_attrs=table['attrs'], physical_rows=len(table['rows']),
                             ordered_header_regimes=header_patterns, representation_version=version, layout_errors=table['errors']))
    return rows, dict(request_date=date, source_format='html', physical_rows=len(rows), tables=metadata,
                      representation_versions=sorted({r['representation_version'] for r in rows}))


def summarize_scopes(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['row_level'] not in ('intro','column_header','section_header'):
            row['scope_id'] = identity(row['scope_identity'])
            groups[row['scope_id']].append(row)
        else:
            row['scope_id'] = None
    observations = []
    for scope_id, group in sorted(groups.items()):
        first = group[0]
        totals = [r for r in group if r['row_level']=='plain_total']
        leaves = [r for r in group if r['row_level']=='leaf']
        reasons = []
        if len(totals)!=1:reasons.append('nonunique_plain_total')
        if not leaves:reasons.append('no_leaf_coverage')
        if any(r['row_level']=='unknown' for r in group):reasons.append('unknown_source_role')
        if any(r['layout_errors'] for r in group):reasons.append('layout_or_representation_unknown')
        if not literal(first.get('unit_token',{})):reasons.append('unknown_unit_token')
        if not literal(first.get('field_states',{}).get('VARNAME',{})):reasons.append('unknown_product_literal')
        measurements = defaultdict(list)
        identity_origins = defaultdict(set)
        for row in leaves:
            origin = row['quantity_origin']
            measurements[origin].append(row)
            context_id = canon(row['context'])
            identity_origins[context_id].add(origin)
            if origin is None or not row['context']:reasons.append('incomplete_leaf_identity_or_origin')
            if not base.numeric(row['quantity']):reasons.append('unknown_leaf_quantity')
            elif Decimal(row['quantity']['value'])<0:reasons.append('negative_quantity')
        if any(len(v)>1 for v in identity_origins.values()):reasons.append('duplicate_leaf_identity')
        leaf_measurements, coverage = [], []
        leaf_sum = Decimal(0)
        all_numeric = bool(leaves)
        for origin, members in measurements.items():
            values = {r['quantity']['value'] for r in members}
            if len(values)!=1:reasons.append('conflicting_shared_quantity_origin')
            contexts = sorted({canon(dict(context=r['context'],quantity_field_name=r['quantity_field_name'])) for r in members})
            cov = [json.loads(c) for c in contexts]
            coverage.append(cov)
            value = members[0]['quantity']['value']
            valid = origin is not None and len(values)==1 and all(base.numeric(r['quantity']) for r in members)
            all_numeric = all_numeric and valid
            if valid:leaf_sum += Decimal(value)
            leaf_measurements.append(dict(quantity_origin=origin, source_rows=[r['source_row'] for r in members],
                                          coverage_contexts=cov, quantity_value=value if valid else None,
                                          quantity_state=members[0]['quantity']['state']))
        coverage = sorted(coverage,key=canon)
        total = totals[0] if len(totals)==1 else None
        if total and total['quantity_origin'] in measurements:reasons.append('total_leaf_origin_overlap')
        if total and not base.numeric(total['quantity']):reasons.append('unknown_total_quantity')
        if total and base.numeric(total['quantity']) and Decimal(total['quantity']['value'])<0:reasons.append('negative_quantity')
        known_total = total is not None and base.numeric(total['quantity'])
        arithmetic = ('match' if leaf_sum==Decimal(total['quantity']['value']) else 'mismatch') if all_numeric and known_total else 'unknown'
        if arithmetic!='match':reasons.append('leaf_total_arithmetic_'+arithmetic)
        source_reasons = sorted(set(reasons))
        if first['mapping_state']!='mapped':reasons.append('research_mapping_unknown')
        observation = dict(schema='stage186_scope_observation_v1', request_date=first['request_date'],
            source_format=first['source_format'], scope_id=scope_id, scope_identity=first['scope_identity'],
            representation_version=first.get('representation_version','unknown'), product_raw=first['product_raw'],
            mapped_research_product_id=first['mapped_research_product_id'], mapping_state=first['mapping_state'],
            overlay_entry_ids=first['overlay_entry_ids'], candidate_product_ids=first['candidate_product_ids'], required=True,
            status='unknown' if reasons else 'conditional_source_qualified', reasons=sorted(set(reasons)),
            source_group_status='unknown' if source_reasons else 'conditionally_identified_source_rows', source_reasons=source_reasons,
            quantity_value=total['quantity']['value'] if total else None,
            official_delta_value=total['official_delta']['value'] if total else None,
            ordinary_total_count=len(totals), ordinary_total_source_rows=[r['source_row'] for r in totals],
            ordinary_total=({k:total[k] for k in ('source_row','quantity','official_delta','quantity_origin','delta_origin','aggregate_label')} if total else None),
            all_source_rows=[r['source_row'] for r in group], source_leaf_row_count=len(leaves), leaf_measurement_count=len(measurements),
            leaf_measurements=leaf_measurements, leaf_sum_quantity=str(leaf_sum) if all_numeric else None,
            quantity_arithmetic_status=arithmetic, leaf_coverage_fingerprint=identity(coverage),
            coverage_state='unknown' if source_reasons else 'complete_nonduplicated_source_rows',
            physical_unit_certified=False, physical_type_certified=False, physical_goods_disjointness_certified=False,
            conditional_same_object_same_positive_scale_assumption=True)
        observations.append(observation)
    return observations


def product_status(scopes, date, overlay):
    unresolved = [s['scope_id'] for s in scopes if not s['candidate_product_ids']]
    result = []
    for pid in overlay['research_product_ids']:
        required = [s for s in scopes if s['mapped_research_product_id']==pid or pid in s['candidate_product_ids']]
        bad = [s['scope_id'] for s in required if s['status']!='conditional_source_qualified']
        complete = bool(required) and not unresolved
        status = 'unknown_no_source_scope' if not required else 'unknown' if bad or not complete else 'conditional_all_required_scopes_qualified'
        result.append(dict(schema='stage186_product_scope_status_v1', request_date=date, mapped_research_product_id=pid,
            status=status, applicability_state='reported_source_groups' if required else 'unknown_not_certified',
            required_scope_ids=sorted(s['scope_id'] for s in required), required_scope_count=len(required), bad_scope_ids=sorted(bad),
            scope_membership_complete=complete, unresolved_report_scope_ids=sorted(unresolved),
            reasons=(['no_source_scope'] if not required else [])+(['bad_required_scope'] if bad else [])+
                    (['unresolved_report_scope_membership'] if unresolved else []),
            physical_goods_disjointness_certified=False, strict_PIT=False))
    return result


def process_report(obj, fmt, date, overlay):
    rows, schema = normalize_json(obj,date,overlay) if fmt=='json' else normalize_html(obj,date,overlay)
    scopes = summarize_scopes(rows)
    return dict(rows=rows, scopes=scopes, products=product_status(scopes,date,overlay), schema=schema)


def bound_bytes(ref):
    data = Path(ref['path']).read_bytes()
    if len(data)!=ref['bytes'] or digest(data)!=ref['sha256']:
        raise ValueError('bound_input_mismatch '+ref['path'])
    return data


def bind(path):
    data=Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()),bytes=len(data),sha256=digest(data))


def write_json(path,obj):
    with Path(path).open('x') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False,default=decimal_encoding);f.write('\n')


def actual(output, overlay_path=OVERLAY):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    source_bundle=[bind(__file__),bind(Path(__file__).with_name('test_stage186_warehouse_history_normalize.py')),bind(base.__file__)]
    write_json(output/'started.json',dict(schema='stage186_normalization_started_v1',started_at=datetime.now(timezone.utc).isoformat(),
               source_bundle=source_bundle,actual_authority='root one offline run; no automatic retry',**ZERO))
    try:
        decision_raw=DECISION.read_bytes()
        if digest(decision_raw)!=DECISION_SHA or source_bundle[-1]['sha256']!=HELPER_SHA:raise ValueError('frozen185_or173_mismatch')
        decision=json.loads(decision_raw);archive_ref=decision['bindings']['archive_manifest'];archive=json.loads(bound_bytes(archive_ref))
        if archive['status']!='completed':raise ValueError('archive_not_completed')
        protocol=json.loads(bound_bytes(archive['inputs']['protocol']));plan=json.loads(bound_bytes(archive['inputs']['plan']))
        if archive['inputs']['protocol']['sha256']!='a67cf844699c8b2d1b34cc3cd66ac88eaae0c6bedd5621796d886f129cfbb0c5' or archive['inputs']['plan']['sha256']!='06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8':raise ValueError('frozen179_178_mismatch')
        report_records=json.loads(bound_bytes(archive['date_manifest']))
        actions=[{k:r[k] for k in ('sequence_index','date','format','url','action')} for r in report_records]
        if len(actions)!=3018 or identity(actions)!=plan['frozen_candidate_domain']['full_action_records_sha256'] or [r['date'] for r in actions]!=plan['frozen_candidate_domain']['dates']:raise ValueError('full3018_source_identity_mismatch')
        overlay_raw=Path(overlay_path).read_bytes()
        if digest(overlay_raw)!=OVERLAY_SHA:raise ValueError('frozen186_overlay_mismatch')
        overlay=json.loads(overlay_raw)
        if len(overlay['research_product_ids'])!=98 or len(set(overlay['research_product_ids']))!=98:raise ValueError('research_catalog_identity_mismatch')
        names={'normalized_rows':'normalized_rows.jsonl.gz','scope_observations':'scope_observations.jsonl.gz',
               'product_scope_status':'product_scope_status.jsonl.gz','report_schema':'report_schema.jsonl.gz'}
        counts=Counter();numeric=defaultdict(Counter);scope_reasons=Counter();byyear=defaultdict(Counter);byproduct=defaultdict(Counter)
        streams={k:gzip.open(output/v,'xt',encoding='utf-8') for k,v in names.items()}
        try:
            for request in report_records:
                if request['state'] not in ('http200_expected_envelope','reused_binding_verified') or not request['body']['complete']:raise ValueError('incomplete_bound_report')
                raw=bound_bytes(request['body'])  # Exactly one body read/hash/parse per report this run.
                obj=decode_json(raw) if request['format']=='json' else raw.decode('utf-8-sig')
                normalized=process_report(obj,request['format'],request['date'],overlay)
                schema=normalized['schema'];schema.update(raw_binding=request['body'],source_url=request['url'],
                    original_response_binding=request.get('response'),archive_report_date_state=request.get('date_state'),definition_version=VERSION)
                for row in normalized['rows']:
                    row.update(definition_version=VERSION,source_url=request['url'])
                    streams['normalized_rows'].write(canon(row)+'\n');counts['physical_rows']+=1
                    counts['row_role:'+row['row_level']]+=1
                    for field in ('quantity','official_delta'):numeric[field][row[field]['state']]+=1
                for scope in normalized['scopes']:
                    streams['scope_observations'].write(canon(scope)+'\n');counts['scopes']+=1;counts['scope_status:'+scope['status']]+=1
                    scope_reasons.update(scope['reasons'])
                for product in normalized['products']:
                    streams['product_scope_status'].write(canon(product)+'\n');counts['product_day_rows']+=1
                    byyear[request['date'][:4]][product['status']]+=1;byproduct[product['mapped_research_product_id']][product['status']]+=1
                streams['report_schema'].write(canon(schema)+'\n');counts['reports']+=1;counts['format:'+request['format']]+=1
                if counts['reports']%250==0:print(json.dumps(dict(reports=counts['reports'],physical_rows=counts['physical_rows'])),flush=True)
        finally:
            for stream in streams.values():stream.close()
        if counts['reports']!=3018 or counts['product_day_rows']!=3018*98:raise ValueError('normalization_domain_not_complete')
        summary=dict(schema='stage186_warehouse_history_summary_v1',counts=dict(counts),numeric_states={k:dict(v) for k,v in numeric.items()},
                     scope_unknown_reasons=dict(scope_reasons),product_status_by_year={k:dict(v) for k,v in byyear.items()},
                     product_status_by_product={k:dict(v) for k,v in byproduct.items()},
                     scalar_or_projection_completed=False,physical_goods_disjointness_certified=False,cumulative_fit=409,cumulative_cash=218,**ZERO)
        write_json(output/'summary.json',summary)
        write_json(output/'terminal.json',dict(schema='stage186_normalization_terminal_v1',status='completed',exit_code=0,
                   elapsed_seconds=time.monotonic()-began,reports=counts['reports'],physical_rows=counts['physical_rows'],automatic_retry=False,**ZERO))
        artifacts={k:bind(output/v) for k,v in names.items()}
        artifacts.update({k:bind(output/(k+'.json')) for k in ('started','summary','terminal')})
        write_json(output/'manifest.json',dict(schema='stage186_warehouse_history_normalization_manifest_v1',status='completed',
            decision=dict(path=str(DECISION),bytes=len(decision_raw),sha256=DECISION_SHA),archive_manifest=archive_ref,
            date_manifest=archive['date_manifest'],protocol=archive['inputs']['protocol'],plan=archive['inputs']['plan'],
            product_overlay=dict(path=str(Path(overlay_path).resolve()),bytes=len(overlay_raw),sha256=OVERLAY_SHA),
            calender=plan['input_metadata']['calendar'],calendar_binding_inherited_not_read=True,
            source_bundle=source_bundle,**artifacts,counts=dict(counts),
            schema_definitions=dict(scope='stage186_scope_observation_v1',product='stage186_product_scope_status_v1',
                                    comparison_key='scope_id and representation_version plus full leaf_coverage_fingerprint; no cross-schema or format joins',
                                    quantities='original Decimal strings; never scalar; required scopes include every bad group',
                                    missing='unknown_no_source_scope / unknown are not zero or not_applicable'),**ZERO))
    except BaseException as error:
        if not (output/'terminal.json').exists():write_json(output/'terminal.json',dict(status='failed',exit_code=1,
            error=type(error).__name__+': '+str(error),traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-began,automatic_retry=False,**ZERO))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--overlay',type=Path,default=OVERLAY);args=parser.parse_args(argv)
    actual(args.output,args.overlay)


if __name__=='__main__':main()
