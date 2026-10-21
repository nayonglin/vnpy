"""Fixed264 literal spot participation sidecars; no financial execution.

The accepted spot CSV is read once for this feature transform and hashed from
the same bytes. No raw pages, financial outcomes, prices, models or cash run.
"""
from __future__ import annotations
import argparse
import bisect
from collections import Counter,defaultdict
import csv
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import time

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage264_spot_participation_protocol/protocol.json'
PROTOCOL_SHA='d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42'
SOURCE_REVIEW_SHA='39ad63ad332603cf386968072d0b3d099817db9f557ce43f1f4a05290f7254fd'
OUTPUT=LINE/'outputs/stage265_spot_policy_map/actual_run1'
SIGNAL_ID=['event_id','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch']
CHOICE_ID=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch',
    'chosen_action_id','chosen_epoch','selected','selection_state']
POLICY=['available','policy_pass','keep_entry','action','reason','product_text','window_start','window_end',
    'spot_start_text','spot_end_text','unit_text_id','issue_date']
SPOT_FIELDS=['date','fdata_top_level_row','product_text','spot_price_text','numeric_text_state',
    'page_content_state','unit_text_id','source_raw_sha256']


def now():return datetime.now(timezone.utc).isoformat()


def binding(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bound_bytes(ref):
    raw=Path(ref['path']).read_bytes();got=binding(ref['path'],raw)
    if any(got[k]!=ref[k] for k in ('bytes','sha256')):raise ValueError('bound_input_changed '+ref['path'])
    return raw,got


def save_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def require_source_review(review):
    if review.get('status')!='completed' or review.get('core_blockers')!=0:
        raise ValueError('262_core_review_not_accepted')


def prepare_source(calendar,mapping,inventory,rows,groups):
    if len(calendar)!=len(set(calendar)):raise ValueError('duplicate_prescribed_source_date')
    if any(date.fromisoformat(d).isoformat()!=d for d in calendar):raise ValueError('source_date_format')
    calendar=sorted(calendar);domain=set(calendar);quotes=defaultdict(list);names=set(mapping.values())
    if set(inventory)!=domain:raise ValueError('source_inventory_date_identity')
    for row in rows:
        if row['date'] not in domain:raise ValueError('quote_outside_source_calendar')
        if row['product_text'] in names:quotes[(row['date'],row['product_text'])].append(row)
    return dict(calendar=calendar,mapping=dict(mapping),inventory=inventory,quotes=quotes,groups=groups,memo={})


def evaluate(u,product,source):
    key=(u,product)
    if key in source['memo']:return dict(source['memo'][key])
    text=source['mapping'].get(product,'');calendar=source['calendar'];end=bisect.bisect_left(calendar,u)
    window=calendar[max(0,end-21):end]
    result=dict(available=0,policy_pass='',keep_entry=1,action='retain',reason='unmapped_product',product_text=text,
        window_start=window[0] if window else '',window_end=window[-1] if window else '',
        spot_start_text='',spot_end_text='',unit_text_id='',issue_date='')
    if text:
        result['reason']='insufficient_prior_source_dates'
        if len(window)==21:
            values=[];units=[];result['reason']='available'
            for day in window:
                result['issue_date']=day
                if source['inventory'][day]['source_data_state']!='positive_spot_rows_observed':
                    result['reason']='page_unavailable';break
                quote=source['quotes'].get((day,text),[])
                if len(quote)>1:result['reason']='duplicate_literal';break
                if not quote:result['reason']='missing_quote';break
                row=quote[0];literal=row['spot_price_text'];uid=row['unit_text_id']
                if day==window[0]:result['spot_start_text']=literal
                if day==window[-1]:result['spot_end_text']=literal
                try:value=Decimal(literal)
                except InvalidOperation:value=Decimal('NaN')
                if (row['numeric_text_state']!='positive' or not value.is_finite() or value<=0):
                    result['reason']='nonpositive_or_non_numeric';break
                if row['page_content_state']!='positive_spot_rows_observed':
                    result['reason']='row_unavailable';break
                if uid not in source['groups'] or not source['groups'][uid]:
                    result['reason']='unknown_unit_text';break
                values.append(value);units.append(uid)
            else:
                result['issue_date']=''
                if len(set(units))!=1:result['reason']='unit_switch'
                else:
                    passed=values[-1]>values[0]
                    result.update(available=1,policy_pass=int(passed),keep_entry=int(passed),
                        action='retain' if passed else 'cancel',reason='spot_rising' if passed else 'spot_not_rising',unit_text_id=units[0])
    source['memo'][key]=result
    return dict(result)


def integer(value):
    v=Decimal(str(value))
    if not v.is_finite() or v!=v.to_integral_value():raise ValueError('noninteger_identity')
    return int(v)


def make_sidecars(choices,signals,source):
    cm=[];sm=[];parents={};selected=set();seen_actions=set()
    for index,c in enumerate(choices):
        if c['event_id'] in parents:raise ValueError('duplicate_choice_mother')
        picked=integer(c['selected'])
        if picked not in (0,1) or bool(c['chosen_action_id'])!=bool(picked):raise ValueError('choice_selected_identity')
        row=dict(choice_row=index,**{k:c[k] for k in CHOICE_ID},**evaluate(c['u_date'],c['product_id'],source))
        if not picked:
            row.update(keep_entry=1,action='retain',reason='no_original_entry:'+row['reason'])
        else:selected.add(c['event_id'])
        parents[c['event_id']]=row;cm.append(row)
    for index,s in enumerate(signals):
        c=parents.get(s['mother_event_id'])
        if c is None or integer(c['selected'])!=1 or s['event_id']!=c['chosen_action_id']:
            raise ValueError('signal_choice_action_identity')
        if (any(s[k]!=c[k] for k in ('product_id','family_id','u_date','anchor_epoch'))
                or integer(s['u_index'])!=integer(c['u_index']) or s['reference_epoch']!=c['chosen_epoch']):
            raise ValueError('signal_choice_source_identity')
        if s['event_id'] in seen_actions or s['mother_event_id'] not in selected:raise ValueError('duplicate_signal_identity')
        seen_actions.add(s['event_id']);selected.remove(s['mother_event_id'])
        sm.append(dict(signal_row=index,**{k:s[k] for k in SIGNAL_ID},**{k:c[k] for k in POLICY}))
    if selected:raise ValueError('selected_choice_missing_signal')
    return cm,sm


def aggregate(rows):
    return dict(total=len(rows),available=sum(r['available'] for r in rows),unavailable=sum(not r['available'] for r in rows),
        cancel=sum(r['action']=='cancel' for r in rows),retain=sum(r['action']=='retain' for r in rows),
        policy_pass=sum(r['policy_pass']==1 for r in rows),policy_fail=sum(r['policy_pass']==0 for r in rows))


def coverage_summary(cm,sm):
    result=dict(schema='stage265_spot_policy_coverage_v1',status='completed',core_blockers=0,total_choices=len(cm),
        total_signals=len(sm),product_domain=len({r['product_id'] for r in cm}),cancel_count=sum(r['action']=='cancel' for r in sm),
        choice_counts=aggregate(cm),signal_counts=aggregate(sm),by_year={},by_product={},by_reason={},new_fit=0,new_cash=0,
        cumulative_fit=439,cumulative_cash=234,financial_outcomes_read=False,goal_complete=False)
    for group,key in [('by_year',lambda r:r['u_date'][:4]),('by_product',lambda r:r['product_id'])]:
        cg=defaultdict(list);sg=defaultdict(list)
        for r in cm:cg[key(r)].append(r)
        for r in sm:sg[key(r)].append(r)
        result[group]={v:dict(choices=aggregate(cg[v]),signals=aggregate(sg[v])) for v in sorted(set(cg)|set(sg))}
    result['by_reason']=dict(choices=dict(Counter(r['reason'] for r in cm)),signals=dict(Counter(r['reason'] for r in sm)))
    return result


def read_gzip_projection(ref,fields):
    raw,got=bound_bytes(ref)
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as zipped,io.TextIOWrapper(zipped,encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream)
        if not set(fields)<=set(reader.fieldnames):raise ValueError('source_identity_columns_missing')
        rows=[{k:r[k] for k in fields} for r in reader]
    return rows,got


def write_map(path,rows,fields):
    with gzip.open(path,'xt',compresslevel=1,newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def run_actual(protocol,pb):
    # This gate precedes the single actual feature CSV read.
    review_raw=Path(protocol['source_review_receipt']).read_bytes();review_binding=binding(protocol['source_review_receipt'],review_raw)
    if review_binding['sha256']!=SOURCE_REVIEW_SHA:raise ValueError('accepted262_receipt_changed')
    require_source_review(json.loads(review_raw))
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic();inputs=dict(source_review=review_binding)
    status='failed';failure=None;summary=None
    try:
        for key in ('source_extraction_manifest','source_groups','source_calendar_protocol','source_inventory'):
            raw,got=bound_bytes(protocol[key]);inputs[key]=got
            value=json.loads(raw) if key!='source_inventory' else [json.loads(line) for line in raw.splitlines()]
            if key=='source_groups':groups=value
            elif key=='source_calendar_protocol':calendar=value['dates']
            elif key=='source_inventory':inventory={r['date']:r for r in value}
        if len(calendar)!=3833 or len(inventory)!=3833:raise ValueError('complete3833_source_domain')
        mappings=protocol['approved_operational_mapping'];mapping={r['product_code']:r['product_text'] for r in mappings}
        if len(mapping)!=55 or len(set(mapping.values()))!=55 or '聚乙烯' in mapping.values():raise ValueError('frozen55_exact_mapping')
        spot_raw,got=bound_bytes(protocol['source_csv']);inputs['source_csv']=got
        reader=csv.DictReader(io.StringIO(spot_raw.decode('utf-8')))
        if reader.fieldnames!=SPOT_FIELDS:raise ValueError('spot_CSV_schema')
        source=prepare_source(calendar,mapping,inventory,reader,groups)
        choices,got=read_gzip_projection(protocol['complete_choices'],CHOICE_ID);inputs['complete_choices']=got
        signals,got=read_gzip_projection(protocol['complete_signals'],SIGNAL_ID);inputs['complete_signals']=got
        if len(choices)!=161014 or len(signals)!=4365 or len({r['product_id'] for r in choices})!=98:
            raise ValueError('complete_forward_choice_signal_domain')
        cm,sm=make_sidecars(choices,signals,source);summary=coverage_summary(cm,sm)
        write_map(OUTPUT/'choice_map.csv.gz',cm,['choice_row']+CHOICE_ID+POLICY)
        write_map(OUTPUT/'signal_map.csv.gz',sm,['signal_row']+SIGNAL_ID+POLICY)
        save_json(OUTPUT/'coverage_summary.json',summary);status='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    receipt=dict(schema='stage265_spot_policy_receipt_v1',status=status,protocol=pb,inputs=inputs,
        source=binding(__file__),failure=failure,total_choices=summary['total_choices'] if summary else None,
        total_signals=summary['total_signals'] if summary else None,cancel_count=summary['cancel_count'] if summary else None,
        core_blockers=0 if status=='completed' else 1,spot_CSV_reads=1 if 'source_csv' in inputs else 0,
        spot_CSV_read_purpose='single actual fixed feature transform; hash from the same read',
        policy_contract=dict(source_calendar_dates=3833,calendar_order='sorted_unique_original249_dates_independent_of_CSV_order',
            exact_operational_mapping_count=55,excluded_literal='聚乙烯',strictly_prior_source_dates=21,
            all21_positive_required=True,all21_unit_ID_same_required=True,duplicate_literal='unavailable_even_if_equal',
            condition='Decimal(newest)>Decimal(oldest)',unavailable_action='inherit',cancel_scope='original_selected_opportunities_only'),
        raw_body_reads=0,network=0,SQL=0,native_price_reads=0,label_reads=0,new_fit=0,new_cash=0,cumulative_fit=439,cumulative_cash=234,
        financial_outcomes_read=False,automatic_retry=False,elapsed_seconds=time.monotonic()-began,completed_at=now())
    save_json(OUTPUT/'receipt.json',receipt)
    save_json(OUTPUT/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
    roles={'signal_map':'signal_map.csv.gz','choice_map':'choice_map.csv.gz','coverage_summary':'coverage_summary.json',
        'receipt':'receipt.json','terminal':'terminal.json'}
    save_json(OUTPUT/'manifest.json',dict(schema='stage265_spot_policy_coverage_manifest_v1',status=status,protocol_sha256=pb['sha256'],
        protocol=pb,source=receipt['source'],inputs=inputs,artifacts={k:binding(OUTPUT/v) for k,v in roles.items() if (OUTPUT/v).is_file()},
        new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',required=True);parser.parse_args(argv)
    raw=PROTOCOL.read_bytes();pb=binding(PROTOCOL,raw)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen264_changed')
    protocol=json.loads(raw)
    if protocol['schema']!='stage264_fixed_literal_spot_participation_protocol_v1':raise ValueError('frozen264_schema')
    print(json.dumps(run_actual(protocol,pb),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
