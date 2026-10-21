"""Fixed183/184 conditional registration scalar and identity-only projection.

Import has no source/financial work. Actual requires exact root188 authorization,
completed186 and accepted187 bound to the same manifest. Never opens raw reports,
prices, labels or SQL. Accepted large source bindings are inherited and checked
by size/stat plus a single identity/normalized stream, not a second hash scan.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
DECISION_SHA='40787dfd0b4a8bfebe257fbcc9ea397ba982ea76ff9f60305caaab5ba7fbc017'
DESIGN_SHA='309d81478b37678700c68e67962448dbb8d11b29f0b2a02892b545f7f5a7a5a2'
RULING_SHA='71af90ae41ac3ea74278e2029676d06b03defbc2407777e89e9463a3fbddd981'
INPUT_ROLES=('normalization_manifest','normalization_review','scope_observations','product_scope_status',
    'product_overlay','dataset_manifest','mothers','actions','calendar','feature_design','scope_ruling')
MOTHER_FIELDS=('sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch')
ACTION_FIELDS=('action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch')
FEATURE_FIELDS=('scalar_primary','scalar_missing','feature_state','decision_date','decision_index',
    'prospective_entry_date','prospective_entry_index','report_v','report_w','report_v_index','report_w_index','scope_count','valid_scope_count')
EXPECTED=dict(mothers=399252,actions=1552456,products=98,families=95,exchanges=6,forward_parents=161014)


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def file_binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same_binding(a,b,role):
    if any(a.get(k)!=b.get(k) for k in ('path','bytes','sha256')):raise ValueError('binding differs '+role)


def small_json(binding):
    if binding['bytes']>2*1024*1024:raise ValueError('small metadata limit exceeded')
    same_binding(file_binding(binding['path']),binding,'small metadata')
    return json.loads(Path(binding['path']).read_text())


def write_json(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def source_stat(binding):
    p=Path(binding['path']);s=p.stat()
    if not p.is_file() or s.st_size!=binding['bytes']:raise ValueError('inherited source size differs '+str(p))
    return dict(path=str(p.resolve()),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,device=s.st_dev,
        inherited_sha256=binding['sha256'],sha256_check='inherited_acceptance_not_rehashed')


def source_bundle():return [file_binding(TOOLS/n) for n in ('stage188_registration_projection.py','test_stage188_registration_projection.py')]


def day(value):
    text=str(value)
    if re.fullmatch(r'\d{8}',text):text=text[:4]+'-'+text[4:6]+'-'+text[6:]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):raise ValueError('explicit source date required')
    date.fromisoformat(text);return text


def index_value(value):
    text=str(value)
    if not re.fullmatch(r'0|[1-9]\d*',text):raise ValueError('nonnegative explicit index required')
    return int(text)


def decimal_value(value):
    if isinstance(value,(bool,float)) or value is None or str(value)=='':raise ValueError('known original Decimal quantity required')
    try:q=Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('invalid original Decimal quantity') from exc
    if not q.is_finite() or q<0:raise ValueError('finite nonnegative original quantity required')
    return q


def decimal_text(value):
    if value==0:return '0'
    return format(value,'f').rstrip('0').rstrip('.') if '.' in format(value,'f') else format(value,'f')


def scope_ratio(qv,qw):
    a,b=decimal_value(qv),decimal_value(qw)
    with localcontext() as context:
        context.prec=50
        return Decimal(0) if a+b==0 else (a-b)/(a+b)


def read_jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:
            if not line.strip():raise ValueError('empty normalized JSONL line')
            yield json.loads(line)


def read_csv_records(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


class RegistrationSource:
    """Normalized declared source scopes only. No unit/type interpretation."""
    def __init__(self,scopes,statuses,calendar,*,not_applicable_products=()):
        self.calendar=[day(x) for x in calendar]
        if not self.calendar or self.calendar!=sorted(set(self.calendar)):raise ValueError('complete ordered unique calendar required')
        self.date_index={d:i for i,d in enumerate(self.calendar)}
        self.scopes={};self.statuses={};self.pairs={};self.not_applicable=frozenset(not_applicable_products)
        self.scope_rows=self.status_rows=0
        for row in scopes:
            d=day(row['request_date']);sid=row['scope_id']
            if d not in self.date_index or not isinstance(sid,str) or not sid:raise ValueError('invalid normalized scope identity')
            key=(d,sid)
            if key in self.scopes:raise ValueError('duplicate date/scope')
            if row.get('required') is not True:raise ValueError('all normalized declared scopes must be required')
            # Do not retain normalized leaf quantities;187 independently accepted them.
            self.scopes[key]=dict(mapped_research_product_id=row['mapped_research_product_id'],
                status=row['status'],quantity_value=row.get('quantity_value'),
                scope_identity=canonical(row['scope_identity']),
                ordinary_total_count=row['ordinary_total_count'],
                leaf_coverage_fingerprint=row.get('leaf_coverage_fingerprint'),coverage_state=row['coverage_state'])
            self.scope_rows+=1
        for row in statuses:
            d=day(row['request_date']);p=row['mapped_research_product_id'];key=(d,p)
            if d not in self.date_index or not isinstance(p,str) or not p or key in self.statuses:
                raise ValueError('invalid/duplicate date/product status')
            required=row['required_scope_ids']
            if not isinstance(required,list) or len(required)!=len(set(required)):raise ValueError('unique full required scope ids required')
            self.statuses[key]=dict(status=row['status'],required_scope_ids=tuple(sorted(required)),
                bad_scope_ids=tuple(row['bad_scope_ids']),scope_membership_complete=row['scope_membership_complete'],
                unresolved_report_scope_ids=tuple(row['unresolved_report_scope_ids']))
            self.status_rows+=1

    def pair(self,product,report_v):
        key=(report_v,product)
        if key in self.pairs:return self.pairs[key]
        vi=self.date_index[report_v];report_w=self.calendar[vi-1] if vi>0 else ''
        result=dict(product_id=product,report_v=report_v,report_w=report_w,scalar_primary='',scalar_missing=1,
            feature_state='unknown_no_product_status',scope_count=0,valid_scope_count=0,
            required_scope_ids_v=[],required_scope_ids_w=[],components=[])
        self.pairs[key]=result
        if product in self.not_applicable:
            result['feature_state']='not_applicable';return result
        v=self.statuses.get(key);w=self.statuses.get((report_w,product))
        if v is None or w is None:return result
        if v['status']==w['status']=='not_applicable':
            result['feature_state']='not_applicable';return result
        result['required_scope_ids_v']=list(v['required_scope_ids']);result['required_scope_ids_w']=list(w['required_scope_ids'])
        result['scope_count']=len(v['required_scope_ids'])
        for s in (v,w):
            if s['unresolved_report_scope_ids'] or s['scope_membership_complete'] is not True:
                result['feature_state']='unknown_incomplete_scope_membership';return result
            if s['bad_scope_ids'] or s['status']!='conditional_all_required_scopes_qualified':
                result['feature_state']='unknown_bad_required_scope';return result
        if not v['required_scope_ids'] or v['required_scope_ids']!=w['required_scope_ids']:
            result['feature_state']='unknown_required_scope_set_changed_or_empty';return result
        values=[]
        for sid in v['required_scope_ids']:
            a=self.scopes.get((report_v,sid));b=self.scopes.get((report_w,sid))
            component=dict(scope_id=sid,status='unknown',reason='',scope_ratio='',quantity_v='',quantity_w='')
            result['components'].append(component)
            if a is None or b is None:component['reason']='missing_required_scope'
            elif a['mapped_research_product_id']!=product or b['mapped_research_product_id']!=product:
                component['reason']='scope_product_mapping_mismatch'
            elif a['scope_identity']!=b['scope_identity']:component['reason']='source_identity_or_schema_changed'
            elif any(s['coverage_state']!='complete_nonduplicated_source_rows' for s in (a,b)) or not a['leaf_coverage_fingerprint'] or a['leaf_coverage_fingerprint']!=b['leaf_coverage_fingerprint']:
                component['reason']='source_leaf_coverage_changed_or_unknown'
            elif any(s['status']!='conditional_source_qualified' or s['ordinary_total_count']!=1 for s in (a,b)):
                component['reason']='scope_not_qualified_or_nonunique_total'
            else:
                try:ratio=scope_ratio(a['quantity_value'],b['quantity_value'])
                except ValueError:component['reason']='scope_quantity_unknown_or_invalid'
                else:
                    values.append(ratio);component.update(status='conditional_scope_pair_known',
                        scope_ratio=decimal_text(ratio),quantity_v=a['quantity_value'],quantity_w=b['quantity_value'])
        result['valid_scope_count']=len(values)
        if len(values)!=len(v['required_scope_ids']):
            result['feature_state']='unknown_required_scope_pair';return result
        with localcontext() as context:
            context.prec=50
            value=sum(values,Decimal(0))/Decimal(len(values))
        result.update(scalar_primary=decimal_text(value),scalar_missing=0,feature_state='conditional_archive_scalar_known')
        return result

    def prepare_all_pairs(self):
        for d,p in sorted(self.statuses):self.pair(p,d)

    def at_decision(self,product,decision_index,decision_date):
        di=index_value(decision_index)
        if di>=len(self.calendar) or self.calendar[di]!=day(decision_date):raise ValueError('original decision date/index differ')
        result=dict(scalar_primary='',scalar_missing=1,feature_state='unknown_calendar_history',
            decision_date=day(decision_date),decision_index=di,prospective_entry_date='',prospective_entry_index='',
            report_v='',report_w='',report_v_index='',report_w_index='',scope_count=0,valid_scope_count=0)
        if di+1<len(self.calendar):result.update(prospective_entry_date=self.calendar[di+1],prospective_entry_index=di+1)
        else:return result
        if product in self.not_applicable:result['feature_state']='not_applicable';return result
        if di<2:return result
        pair=self.pair(product,self.calendar[di-1])
        result.update(report_v_index=di-1,report_w_index=di-2)
        result.update({k:pair[k] for k in ('scalar_primary','scalar_missing','feature_state','report_v','report_w','scope_count','valid_scope_count')})
        return result


def csv_writer(stack,path,fields):
    f=stack.enter_context(gzip.open(path,'xt',encoding='utf-8',newline=''))
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='raise');writer.writeheader();return writer


def identity_digest_update(h,row,fields):
    h.update((canonical([row[f] for f in fields])+'\n').encode('utf-8'))


def project_identity_records(out,mothers,actions,source,*,expected=EXPECTED,fixture=False):
    """Single pass over each identity stream; preserve order, including no-child parents."""
    out=Path(out);parent={};products=set();families=set();exchanges=set();counts=Counter();states=Counter();year_states=Counter();zero_counts=Counter()
    mh,ah=hashlib.sha256(),hashlib.sha256();action_ids=set();forward=0
    with ExitStack() as stack:
        mw=csv_writer(stack,out/'mothers_projection.csv.gz',MOTHER_FIELDS+FEATURE_FIELDS)
        aw=csv_writer(stack,out/'actions_projection.csv.gz',ACTION_FIELDS+FEATURE_FIELDS)
        for i,row in enumerate(mothers):
            row={f:str(row[f]) for f in MOTHER_FIELDS}
            if index_value(row['sequence_index'])!=i or not row['event_id']:
                raise ValueError('complete original ordered mother sequence required')
            p=row['product_id'];di=index_value(row['u_index']);feature=source.at_decision(p,di,row['u_date'])
            parent[i]=tuple(row[f] for f in MOTHER_FIELDS)
            products.add(p);families.add(row['family_id']);exchanges.add(p.split('.')[0])
            forward+=int(day(row['u_date'])>='2020-01-01')
            states[('mothers',feature['feature_state'])]+=1;year_states[('mothers',p,row['u_date'][:4],feature['feature_state'])]+=1
            zero_counts[('mothers',p,row['u_date'][:4])]+=int(feature['scalar_missing']==0 and feature['scalar_primary']=='0')
            identity_digest_update(mh,row,MOTHER_FIELDS);mw.writerow(dict(row,**feature));counts['mothers']+=1
            if counts['mothers']>expected['mothers']:raise ValueError('mother row budget exceeded')
        if (counts['mothers'],len(products),len(families),len(exchanges),forward)!=(expected['mothers'],expected['products'],expected['families'],expected['exchanges'],expected['forward_parents']):
            raise ValueError('full mother identity/domain counts differ')
        mother_events=[v[1] for v in parent.values()]
        if len(set(mother_events))!=len(mother_events):raise ValueError('duplicate original mother event')
        children=Counter()
        for i,row in enumerate(actions):
            row={f:str(row[f]) for f in ACTION_FIELDS}
            if index_value(row['action_sequence_index'])!=i or not row['action_id'] or row['action_id'] in action_ids:
                raise ValueError('complete original ordered unique action identity required')
            action_ids.add(row['action_id']);mi=index_value(row['mother_sequence_index'])
            if mi not in parent:raise ValueError('action parent missing')
            mother=dict(zip(MOTHER_FIELDS,parent[mi]))
            if row['mother_event_id']!=mother['event_id'] or any(row[f]!=mother[f] for f in ('product_id','family_id','u_date','u_index')) or row['anchor_epoch']!=mother['reference_epoch']:
                raise ValueError('action/parent identity or immutable anchor closure differs')
            feature=source.at_decision(row['product_id'],row['u_index'],row['u_date'])
            states[('actions',feature['feature_state'])]+=1;year_states[('actions',row['product_id'],row['u_date'][:4],feature['feature_state'])]+=1
            zero_counts[('actions',row['product_id'],row['u_date'][:4])]+=int(feature['scalar_missing']==0 and feature['scalar_primary']=='0')
            identity_digest_update(ah,row,ACTION_FIELDS);aw.writerow(dict(row,**feature));counts['actions']+=1;children[mi]+=1
            if counts['actions']>expected['actions']:raise ValueError('action row budget exceeded')
        if counts['actions']!=expected['actions']:raise ValueError('complete original action count differs')
        cw=csv_writer(stack,out/'mother_action_closure.csv.gz',('sequence_index','event_id','product_id','u_date','action_count'))
        for mi,values in parent.items():cw.writerow(dict(sequence_index=values[0],event_id=values[1],product_id=values[2],u_date=values[4],action_count=children[mi]))
        sw=csv_writer(stack,out/'coverage_by_product_year.csv.gz',('domain','product_id','year','rows','known','known_zero','unknown','not_applicable'))
        years=sorted({v[4][:4] for v in parent.values()})
        for domain in ('mothers','actions'):
            for p in sorted(products):
                for year in years:
                    entries={state:n for (d,prod,y,state),n in year_states.items() if (d,prod,y)==(domain,p,year)}
                    known=entries.get('conditional_archive_scalar_known',0);na=entries.get('not_applicable',0)
                    sw.writerow(dict(domain=domain,product_id=p,year=year,rows=sum(entries.values()),known=known,
                        known_zero=zero_counts[(domain,p,year)],unknown=sum(entries.values())-known-na,not_applicable=na))
    receipt=dict(**counts,products=len(products),families=len(families),exchanges=len(exchanges),forward_parents=forward,
        mother_identity_sha256=mh.hexdigest(),action_identity_sha256=ah.hexdigest(),
        mother_rows_with_no_actions=sum(children[i]==0 for i in parent),
        status_counts=[dict(domain=d,state=s,rows=n) for (d,s),n in sorted(states.items())],
        identity_only_source_single_pass=True,old_source_label_columns_read=[],actual_model_fit_calls=0,new_cash_accounts=0,SQL=0,
        raw_reports_read=0,ordinary_F_aliases=0,fixture=fixture)
    write_json(out/'identity_projection_checkpoint.json',receipt)
    return receipt


def identity_rows(path,fields):
    for chunk in pd.read_csv(path,usecols=list(fields),dtype=str,keep_default_na=False,chunksize=100000):
        if list(chunk.columns)!=list(fields):chunk=chunk[list(fields)]
        yield from chunk.to_dict('records')


def write_pair_ledgers(out,source):
    fields=('product_id','report_v','report_w','scalar_primary','scalar_missing','feature_state','scope_count',
        'valid_scope_count','required_scope_ids_v','required_scope_ids_w')
    component_fields=('product_id','report_v','report_w','scope_id','status','reason','scope_ratio','quantity_v','quantity_w')
    with ExitStack() as stack:
        pw=csv_writer(stack,out/'product_scalar_pairs.csv.gz',fields)
        sw=csv_writer(stack,out/'scope_pairs.csv.gz',component_fields)
        for key,r in sorted(source.pairs.items()):
            row={f:r[f] for f in fields}
            for f in ('required_scope_ids_v','required_scope_ids_w'):row[f]=canonical(row[f])
            pw.writerow(row)
            for c in r['components']:sw.writerow(dict(product_id=r['product_id'],report_v=r['report_v'],report_w=r['report_w'],**c))


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh projection output required; previous attempts retained')
    if LINE/'outputs/stage188_registration_projection' not in out.parents:raise ValueError('Stage188 fresh descendant required')
    db=file_binding(args.decision)
    if args.decision_sha256!=DECISION_SHA or db['sha256']!=DECISION_SHA:raise ValueError('exact root185 decision required')
    decision=small_json(db)
    if decision.get('schema')!='stage185_warehouse_archive_root_decision_v1' or decision.get('line_id')!=LINE.name:raise ValueError('185 identity differs')
    ab=file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization SHA differs')
    auth=small_json(ab)
    expected=dict(schema='stage188_exact_root_authorization_v1',authorized_by='root',stage='projection',
        exact_source_authorized=True,decision_sha256=DECISION_SHA,normalized_source_accepted=True,output=str(out))
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('exact root188 projection authorization required')
    if auth.get('source_bundle')!=source_bundle():raise ValueError('authorized source/tests differ')
    if set(auth.get('input_bindings',{}))!=set(INPUT_ROLES):raise ValueError('exact source/identity roles required')
    inputs=auth['input_bindings']
    for role,name,sha in (('feature_design','prospective_feature_design',DESIGN_SHA),('scope_ruling','legacy_scope_ruling',RULING_SHA)):
        same_binding(inputs[role],decision['bindings'][name],'185 '+role)
        if inputs[role]['sha256']!=sha:raise ValueError('fixed183/184 differs')
        small_json(inputs[role])
    return decision,db,auth,ab


def validate_metadata(inputs):
    norm=small_json(inputs['normalization_manifest']);review=small_json(inputs['normalization_review'])
    if norm.get('schema')!='stage186_warehouse_history_normalization_manifest_v1' or norm.get('status')!='completed':
        raise ValueError('completed186 required')
    terminal=small_json(norm['terminal'])
    if terminal.get('status')!='completed' or terminal.get('exit_code')!=0:raise ValueError('186 terminal incomplete')
    if review.get('schema')!='stage187_registration_normalization_review_v1' or review.get('accepted') is not True or any(review.get(k)!=0 for k in ('C','I','M')):
        raise ValueError('accepted187 C/I/M0 receipt required')
    same_binding(review['normalization_manifest'],inputs['normalization_manifest'],'187 same186')
    for role in ('scope_observations','product_scope_status','product_overlay'):
        same_binding(norm[role],inputs[role],'186 '+role)
    same_binding(norm['calender'],inputs['calendar'],'186 calender')
    dataset=small_json(inputs['dataset_manifest'])
    if dataset.get('schema')!='stage129_contract_choice_dataset_v1' or dataset.get('status')!='completed' or (dataset.get('mother_rows'),dataset.get('action_rows'))!=(EXPECTED['mothers'],EXPECTED['actions']):
        raise ValueError('accepted full129 dataset identity required')
    for role in ('mothers','actions'):same_binding(dataset[role],inputs[role],'129 '+role)
    overlay=small_json(inputs['product_overlay'])
    return norm,review,overlay


def execute(args):
    decision,db,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False);began=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    status,error='failed',None;before=source_bundle();receipt={};input_stats={};artifacts={}
    write_json(out/'started.json',dict(schema='stage188_projection_started_v1',status='started',started_at=began,
        decision=db,authorization=ab,source_bundle=before,fixture=False,projection_attempts=1,
        actual_model_fit_calls=0,new_cash_accounts=0,SQL=0,no_automatic_retry=True))
    try:
        norm,review,overlay=validate_metadata(inputs)
        for role in ('scope_observations','product_scope_status','mothers','actions','calendar'):
            input_stats[role]=source_stat(inputs[role])
        dates=[day(x) for x in np.load(inputs['calendar']['path'],allow_pickle=False)]
        source=RegistrationSource(read_jsonl(inputs['scope_observations']['path']),
            read_jsonl(inputs['product_scope_status']['path']),dates,
            not_applicable_products=overlay.get('not_applicable_research_products',[]))
        source.prepare_all_pairs()
        receipt=project_identity_records(out,identity_rows(inputs['mothers']['path'],MOTHER_FIELDS),
            identity_rows(inputs['actions']['path'],ACTION_FIELDS),source)
        write_pair_ledgers(out,source)
        for role,before_stat in input_stats.items():
            if source_stat(inputs[role])!=before_stat:raise ValueError('read-only input stat changed '+role)
        if source_bundle()!=before:raise ValueError('authorized source changed during projection')
        write_json(out/'source_read_receipt.json',dict(input_stats=input_stats,normalization_manifest=inputs['normalization_manifest'],
            normalization_review=inputs['normalization_review'],scope_rows_read=source.scope_rows,
            product_status_rows_read=source.status_rows,product_pair_rows=len(source.pairs),
            raw_reports_read=0,large_source_generic_hash_scans=0,label_or_price_fields_read=[],
            single_normalized_stream_each=True,single_identity_stream_each=True,SQL=0,new_labels=0,
            scalar_is_physical_inventory=False,first_release_PIT_proved=False))
        status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        checkpoint=out/'identity_projection_checkpoint.json'
        durable=json.loads(checkpoint.read_text()) if checkpoint.exists() else receipt
        write_json(out/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,
            started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            projection_attempts=1,identity_checkpointed=checkpoint.exists(),mother_rows=durable.get('mothers',0),
            action_rows=durable.get('actions',0),actual_model_fit_calls=0,new_cash_accounts=0,SQL=0,
            raw_reports_read=0,new_labels=0,new_prices=0,downloads=0,old_book_replays=0,
            fixture=False,python=sys.executable,no_automatic_retry=True))
    for path in sorted(out.iterdir()):
        if path.is_file():artifacts[path.name]=file_binding(path)
    manifest=dict(schema='stage188_registration_projection_v1',status=status,decision=db,authorization=ab,
        input_bindings=inputs,source_bundle=before,artifacts=artifacts,terminal=artifacts['terminal.json'],
        mothers_projection=artifacts['mothers_projection.csv.gz'],actions_projection=artifacts['actions_projection.csv.gz'],
        product_scalar_pairs=artifacts['product_scalar_pairs.csv.gz'],scope_pairs=artifacts['scope_pairs.csv.gz'],
        identity_receipt=artifacts['identity_projection_checkpoint.json'],source_read_receipt=artifacts['source_read_receipt.json'],
        full_domain_counts=receipt,scalar_definition='fixed183 equal mean of complete perdeclaredscope symmetric ratios',
        decision_clock='original129u_index=D,entry=D+1,v=D-1,w=D-2; never actual fill',
        strictPIT=False,physical_unit_type_certification=False,actual_model_fit_calls=0,new_cash_accounts=0,SQL=0,
        goal_complete=False,production_qualified=False,increased_betting_qualified=False)
    write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),mother_rows=receipt['mothers'],action_rows=receipt['actions'],actual_model_fit_calls=0,new_cash_accounts=0,SQL=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('decision','decision-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
