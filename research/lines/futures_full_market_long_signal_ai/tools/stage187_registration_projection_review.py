"""Independent fixed183 registration-F and complete129 identity audit.

No author188 import, original report, price/label, model, cash or SQL. Large129
CSV SHA is inherited from the exact authorized source closure; only identity
columns stream once. All new projection outputs hash in the same audit stream.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from decimal import Decimal, localcontext
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import time
import traceback
import numpy as np
import pandas as pd
from stage187_warehouse_history_normalization_review import canon,equal,binding,load,write,stream,HashInput

LINE=Path(__file__).resolve().parents[1]
AUTHOR_SHA='bd3da6e25b4d4b445b4b3ecb7ca78eb03411d0cebe6a86c993b3c0de50593d71'
TEST_SHA='3fbebe9019cf6eba4feb60fcb15bd99f68d146ec1a2dd7d66ec061e8148d413e'
MOTHER=('sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch')
ACTION=('action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch')
FEATURE=('scalar_primary','scalar_missing','feature_state','decision_date','decision_index','prospective_entry_date','prospective_entry_index','report_v','report_w','report_v_index','report_w_index','scope_count','valid_scope_count')


def date(v):
    s=str(v)
    if re.fullmatch(r'\d{8}',s): return s[:4]+'-'+s[4:6]+'-'+s[6:]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s): raise AssertionError('explicit date required')
    return s


def integer(v):
    if not re.fullmatch(r'0|[1-9][0-9]*',str(v)): raise AssertionError('explicit nonnegative index required')
    return int(v)


def decimal(v):
    if v is None or isinstance(v,(bool,float)): raise ValueError('unknown quantity')
    q=Decimal(str(v))
    if not q.is_finite() or q<0: raise ValueError('invalid quantity')
    return q


def decimal_text(v):
    if v==0: return '0'
    text=format(v,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


class RegistrationEvidence:
    def __init__(self,scopes,statuses,calendar,not_applicable=()):
        self.calendar=[date(x) for x in calendar];equal(self.calendar,sorted(set(self.calendar)),'ordered unique calendar')
        self.indices={d:i for i,d in enumerate(self.calendar)};self.scopes={};self.statuses={};self.pairs={};self.na=set(not_applicable)
        for r in scopes:
            key=(date(r['request_date']),r['scope_id']);equal(key in self.scopes,False,'unique normalized scope')
            self.scopes[key]={k:r[k] for k in ('mapped_research_product_id','status','quantity_value','scope_identity','ordinary_total_count','leaf_coverage_fingerprint','coverage_state')}
        for r in statuses:
            key=(date(r['request_date']),r['mapped_research_product_id']);equal(key in self.statuses,False,'unique product status')
            self.statuses[key]={k:r[k] for k in ('status','required_scope_ids','bad_scope_ids','scope_membership_complete','unresolved_report_scope_ids')}

    def pair(self,p,v):
        key=(v,p)
        if key in self.pairs: return self.pairs[key]
        vi=self.indices[v];w=self.calendar[vi-1] if vi else ''
        r=dict(product_id=p,report_v=v,report_w=w,scalar_primary='',scalar_missing=1,feature_state='unknown_no_product_status',scope_count=0,valid_scope_count=0,
            required_scope_ids_v=[],required_scope_ids_w=[],components=[])
        self.pairs[key]=r
        if p in self.na: r['feature_state']='not_applicable';return r
        a=self.statuses.get(key);b=self.statuses.get((w,p))
        if a is None or b is None: return r
        if a['status']==b['status']=='not_applicable': r['feature_state']='not_applicable';return r
        av=sorted(a['required_scope_ids']);bv=sorted(b['required_scope_ids'])
        r.update(required_scope_ids_v=av,required_scope_ids_w=bv,scope_count=len(av))
        for x in (a,b):
            if x['unresolved_report_scope_ids'] or x['scope_membership_complete'] is not True:
                r['feature_state']='unknown_incomplete_scope_membership';return r
            if x['bad_scope_ids'] or x['status']!='conditional_all_required_scopes_qualified':
                r['feature_state']='unknown_bad_required_scope';return r
        if not av or av!=bv: r['feature_state']='unknown_required_scope_set_changed_or_empty';return r
        ratios=[]
        for sid in av:
            x=self.scopes.get((v,sid));y=self.scopes.get((w,sid))
            c=dict(scope_id=sid,status='unknown',reason='',scope_ratio='',quantity_v='',quantity_w='');r['components'].append(c)
            if x is None or y is None: c['reason']='missing_required_scope'
            elif x['mapped_research_product_id']!=p or y['mapped_research_product_id']!=p: c['reason']='scope_product_mapping_mismatch'
            elif x['scope_identity']!=y['scope_identity']: c['reason']='source_identity_or_schema_changed'
            elif any(s['coverage_state']!='complete_nonduplicated_source_rows' for s in (x,y)) or not x['leaf_coverage_fingerprint'] or x['leaf_coverage_fingerprint']!=y['leaf_coverage_fingerprint']:
                c['reason']='source_leaf_coverage_changed_or_unknown'
            elif any(s['status']!='conditional_source_qualified' or s['ordinary_total_count']!=1 for s in (x,y)): c['reason']='scope_not_qualified_or_nonunique_total'
            else:
                try:
                    qv,qw=decimal(x['quantity_value']),decimal(y['quantity_value'])
                    with localcontext() as ctx:
                        ctx.prec=50;ratio=Decimal(0) if qv+qw==0 else (qv-qw)/(qv+qw)
                except (ValueError,ArithmeticError): c['reason']='scope_quantity_unknown_or_invalid'
                else:
                    ratios.append(ratio);c.update(status='conditional_scope_pair_known',scope_ratio=decimal_text(ratio),quantity_v=x['quantity_value'],quantity_w=y['quantity_value'])
        r['valid_scope_count']=len(ratios)
        if len(ratios)!=len(av): r['feature_state']='unknown_required_scope_pair';return r
        with localcontext() as ctx:
            ctx.prec=50;value=sum(ratios,Decimal(0))/Decimal(len(ratios))
        r.update(scalar_primary=decimal_text(value),scalar_missing=0,feature_state='conditional_archive_scalar_known')
        return r

    def at(self,p,di,dd):
        i=integer(di);equal(self.calendar[i],date(dd),'original decision date/index')
        r=dict(scalar_primary='',scalar_missing=1,feature_state='unknown_calendar_history',decision_date=date(dd),decision_index=i,
            prospective_entry_date='',prospective_entry_index='',report_v='',report_w='',report_v_index='',report_w_index='',scope_count=0,valid_scope_count=0)
        if i+1>=len(self.calendar): return r
        r.update(prospective_entry_date=self.calendar[i+1],prospective_entry_index=i+1)
        if p in self.na: r['feature_state']='not_applicable';return r
        if i<2: return r
        pair=self.pair(p,self.calendar[i-1]);r.update(report_v_index=i-1,report_w_index=i-2)
        for k in ('scalar_primary','scalar_missing','feature_state','report_v','report_w','scope_count','valid_scope_count'): r[k]=pair[k]
        return r


def stat(ref):
    s=Path(ref['path']).stat();equal(s.st_size,ref['bytes'],'inherited source size')
    return dict(path=str(Path(ref['path']).resolve()),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,device=s.st_dev,inherited_sha256=ref['sha256'],sha256_check='inherited_acceptance_not_rehashed')


@contextmanager
def csv_stream(ref):
    with Path(ref['path']).open('rb') as raw:
        hashed=HashInput(raw)
        with gzip.GzipFile(fileobj=hashed,mode='rb') as z,io.TextIOWrapper(z,encoding='utf-8',newline='') as text:
            yield csv.DictReader(text)
        equal(hashed.n,ref['bytes'],'new CSV compressed bytes');equal(hashed.h.hexdigest(),ref['sha256'],'new CSV SHA')


def identities(ref,fields):
    # Accepted129 closure supplies complete SHA; do not hash the large old CSV.
    for chunk in pd.read_csv(ref['path'],usecols=list(fields),dtype=str,keep_default_na=False,chunksize=100000):
        yield from chunk[list(fields)].to_dict('records')


def string_row(x): return {k:str(v) for k,v in x.items()}


def update_digest(h,row,fields): h.update((canon([row[k] for k in fields])+'\n').encode())


def review(args):
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);clock=time.monotonic()
    mr=binding(args.manifest);equal(mr['sha256'],args.manifest_sha256,'exact projection manifest')
    source=[binding(__file__),binding(Path(__file__).with_name('test_stage187_registration_projection_review.py')),
            binding(Path(__file__).with_name('stage187_warehouse_history_normalization_review.py'))]
    receipt=dict(schema='stage187_registration_projection_review_v1',accepted=False,C=0,I=0,M=0,errors=[],projection_manifest=mr,source_bundle=source,
        new_fit=0,new_cash=0,SQL=0,network=0,raw_reports_read=0,old_large_source_generic_hashes=0,automatic_retry=False,
        strictPIT=False,physical_unit_type_certified=False,financial_authorization=False,cumulative_fit=409,cumulative_cash=218)
    write(out/'started.json',dict(projection_manifest=mr,source_bundle=source))
    try:
        m=load(mr);equal(m['schema'],'stage188_registration_projection_v1','projection schema');equal(m['status'],'completed','projection completed')
        terminal=load(m['terminal']);equal((terminal['status'],terminal['exit_code']),('completed',0),'188 terminal')
        for k in ('actual_model_fit_calls','new_cash_accounts','SQL','raw_reports_read','new_labels','new_prices','downloads','old_book_replays'):
            equal(terminal[k],0,'188 source-only '+k)
        equal(m['strictPIT'],False,'conditional archive PIT limit');equal(m['physical_unit_type_certification'],False,'unit/type limit')
        inputs=m['input_bindings'];nr=load(inputs['normalization_review']);nm=load(inputs['normalization_manifest'])
        equal(nr['schema'],'stage187_registration_normalization_review_v1','187 normalization schema');equal(nr['accepted'],True,'norm accepted')
        equal([nr[k] for k in ('C','I','M')],[0,0,0],'norm findings');equal(nr['normalization_manifest'],inputs['normalization_manifest'],'same normalization')
        equal(nm['status'],'completed','186 completed')
        receipt.update(normalization_manifest=inputs['normalization_manifest'],normalization_review=inputs['normalization_review'])
        for k in ('scope_observations','product_scope_status','product_overlay'): equal(inputs[k],nm[k],'exact norm artifact '+k)
        equal(inputs['calendar'],nm['calender'],'same full052 calendar')
        dataset=load(inputs['dataset_manifest']);equal(dataset['schema'],'stage129_contract_choice_dataset_v1','accepted dataset schema')
        for k in ('mothers','actions'): equal(inputs[k],dataset[k],'exact original129 '+k)
        equal((dataset['mother_rows'],dataset['action_rows']),(399252,1552456),'complete accepted dataset')
        for ref,pin in zip(m['source_bundle'],(AUTHOR_SHA,TEST_SHA)):
            equal(ref['sha256'],pin,'frozen188 source');equal(binding(ref['path']),ref,'current188 source')
        equal(len(m['source_bundle']),2,'188 source count')
        before={k:stat(inputs[k]) for k in ('scope_observations','product_scope_status','mothers','actions','calendar')}
        read_receipt=load(m['source_read_receipt']);equal(read_receipt['input_stats'],before,'188 read-only source stat closure')
        equal(binding(inputs['calendar']['path']),inputs['calendar'],'small full calendar SHA')
        calendar=[date(x) for x in np.load(inputs['calendar']['path'],allow_pickle=False)];equal(len(calendar),5587,'full052 calendar length')
        overlay=load(inputs['product_overlay']);equal(overlay.get('not_applicable_research_products',[]),[],'no inferred NA product list')
        with stream(inputs['scope_observations']) as scopes,stream(inputs['product_scope_status']) as statuses:
            evidence=RegistrationEvidence(scopes,statuses,calendar,overlay.get('not_applicable_research_products',[]))
        equal(len(evidence.scopes),nr['all_scopes'],'all independently accepted scopes');equal(len(evidence.statuses),nr['all_product_statuses'],'all independently accepted product statuses')
        for d,p in sorted(evidence.statuses): evidence.pair(p,d)
        write(out/'source_closure_checkpoint.json',dict(completed=True,projection_manifest=mr,normalization_manifest=inputs['normalization_manifest'],normalization_review=inputs['normalization_review'],input_stats=before))
        parents={};children=Counter();counts=Counter();state_counts=Counter();year_states=Counter();zero_counts=Counter();products=set();families=set();exchanges=set();years=set();forward=0
        mh=hashlib.sha256();ah=hashlib.sha256()
        with csv_stream(m['mothers_projection']) as saved:
            equal(tuple(saved.fieldnames),MOTHER+FEATURE,'mother output header')
            for i,old in enumerate(identities(inputs['mothers'],MOTHER)):
                equal(integer(old['sequence_index']),i,'original mother sequence');new=next(saved)
                expected=dict(old,**string_row(evidence.at(old['product_id'],old['u_index'],old['u_date'])))
                equal(new,expected,'mother identity/F '+str(i));parents[i]=tuple(old[k] for k in MOTHER)
                update_digest(mh,old,MOTHER);counts['mothers']+=1
                p=old['product_id'];y=old['u_date'][:4];s=new['feature_state'];products.add(p);families.add(old['family_id']);exchanges.add(p.split('.')[0]);years.add(y)
                forward+=int(date(old['u_date'])>='2020-01-01');state_counts[('mothers',s)]+=1;year_states[('mothers',p,y,s)]+=1
                zero_counts[('mothers',p,y)]+=int(new['scalar_missing']=='0' and new['scalar_primary']=='0')
            equal(next(saved,None),None,'no extra mother rows')
        equal((counts['mothers'],len(products),len(families),len(exchanges),forward),(399252,98,95,6,161014),'full mother domain')
        with csv_stream(m['actions_projection']) as saved:
            equal(tuple(saved.fieldnames),ACTION+FEATURE,'action output header')
            for i,old in enumerate(identities(inputs['actions'],ACTION)):
                equal(integer(old['action_sequence_index']),i,'original action sequence');new=next(saved)
                expected=dict(old,**string_row(evidence.at(old['product_id'],old['u_index'],old['u_date'])))
                equal(new,expected,'action identity/F '+str(i));update_digest(ah,old,ACTION);counts['actions']+=1
                mi=integer(old['mother_sequence_index']);parent=dict(zip(MOTHER,parents[mi]));children[mi]+=1
                equal(old['mother_event_id'],parent['event_id'],'parent event');equal(old['anchor_epoch'],parent['reference_epoch'],'immutable canonical anchor')
                for k in ('product_id','family_id','u_date','u_index'): equal(old[k],parent[k],'parent relation '+k)
                p=old['product_id'];y=old['u_date'][:4];s=new['feature_state'];state_counts[('actions',s)]+=1;year_states[('actions',p,y,s)]+=1
                zero_counts[('actions',p,y)]+=int(new['scalar_missing']=='0' and new['scalar_primary']=='0')
                if counts['actions']%250000==0: print(canon(dict(phase='complete_identity_F',actions=counts['actions'])),flush=True)
            equal(next(saved,None),None,'no extra actions')
        equal(counts['actions'],1552456,'full action domain')
        identity=load(m['identity_receipt']);equal(identity['mother_identity_sha256'],mh.hexdigest(),'mother identity SHA');equal(identity['action_identity_sha256'],ah.hexdigest(),'action identity SHA')
        equal(identity['status_counts'],[dict(domain=d,state=s,rows=n) for (d,s),n in sorted(state_counts.items())],'all identity statuses')
        equal(identity['mother_rows_with_no_actions'],sum(children[i]==0 for i in parents),'no-child parent preservation')
        write(out/'identity_F_checkpoint.json',dict(completed=True,mothers=counts['mothers'],actions=counts['actions'],mother_identity_sha256=mh.hexdigest(),action_identity_sha256=ah.hexdigest(),mother_rows_with_no_actions=sum(children[i]==0 for i in parents)))
        artifacts=m['artifacts'];closure=artifacts['mother_action_closure.csv.gz'];coverage=artifacts['coverage_by_product_year.csv.gz']
        with csv_stream(closure) as saved:
            for mi,values in parents.items():
                expected=dict(sequence_index=values[0],event_id=values[1],product_id=values[2],u_date=values[4],action_count=str(children[mi]))
                equal(next(saved),expected,'full mother/child count closure')
            equal(next(saved,None),None,'no extra closure rows')
        pair_count=component_count=0;pair_states=Counter()
        with csv_stream(m['product_scalar_pairs']) as ps,csv_stream(m['scope_pairs']) as cs:
            for key,r in sorted(evidence.pairs.items()):
                expected={k:r[k] for k in ('product_id','report_v','report_w','scalar_primary','scalar_missing','feature_state','scope_count','valid_scope_count','required_scope_ids_v','required_scope_ids_w')}
                for k in ('required_scope_ids_v','required_scope_ids_w'): expected[k]=canon(expected[k])
                equal(next(ps),string_row(expected),'all product pair F');pair_count+=1;pair_states[r['feature_state']]+=1
                for c in r['components']:
                    expected=dict(product_id=r['product_id'],report_v=r['report_v'],report_w=r['report_w'],**c)
                    equal(next(cs),string_row(expected),'all scope ratio components');component_count+=1
            equal(next(ps,None),None,'no extra product pairs');equal(next(cs,None),None,'no extra components')
        write(out/'pair_math_checkpoint.json',dict(completed=True,product_pair_rows=pair_count,scope_component_rows=component_count,pair_status_counts=dict(pair_states),projection_manifest=mr))
        with csv_stream(coverage) as saved:
            for domain in ('mothers','actions'):
                for p in sorted(products):
                    for y in sorted(years):
                        entries={s:n for (d,prod,year,s),n in year_states.items() if (d,prod,year)==(domain,p,y)}
                        known=entries.get('conditional_archive_scalar_known',0);na=entries.get('not_applicable',0);n=sum(entries.values())
                        equal(next(saved),string_row(dict(domain=domain,product_id=p,year=y,rows=n,known=known,known_zero=zero_counts[(domain,p,y)],unknown=n-known-na,not_applicable=na)),'complete zero-inclusive coverage')
            equal(next(saved,None),None,'no extra coverage rows')
        for k,v in before.items(): equal(stat(inputs[k]),v,'input unchanged '+k)
        equal(read_receipt['product_pair_rows'],pair_count,'pair source read count')
        byyear=Counter()
        for (domain,p,y,s),n in year_states.items(): byyear[(domain,y,s)]+=n
        receipt.update(accepted=True,mother_rows=counts['mothers'],action_rows=counts['actions'],full_forward_parent_rows=forward,products=len(products),families=len(families),exchanges=len(exchanges),
            mother_rows_with_no_actions=sum(children[i]==0 for i in parents),mother_identity_sha256=mh.hexdigest(),action_identity_sha256=ah.hexdigest(),
            product_pair_rows=pair_count,scope_component_rows=component_count,pair_status_counts=dict(pair_states),status_counts=identity['status_counts'],
            availability_by_year=[dict(domain=d,year=y,state=s,rows=n) for (d,y,s),n in sorted(byyear.items())],
            all_scope_ratios_and_whole_product_F_independently_recomputed=True,original_identity_fields_only=True,ordinary_F_aliases=0,
            source_unknown_is_not_zero=True,full052_calendar=True,calendar_sessions=5587,raw_body_rereads=0,
            source_assumptions='conditional declared source scopes only; accepted normalization does not certify physical unit/type/disjointness or first-release PIT')
    except BaseException as e:
        receipt.update(I=1,errors=[dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())]);raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-clock;write(out/'receipt.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',required=True)
    r=review(p.parse_args());print(canon(dict(accepted=r['accepted'],C=r['C'],I=r['I'],M=r['M'],mothers=r.get('mother_rows'),actions=r.get('action_rows'))),flush=True)


if __name__=='__main__': main()
