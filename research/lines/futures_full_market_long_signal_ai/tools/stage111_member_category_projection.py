"""Frozen110 category scalar, local109 raw only; no network/SQL/fit/cash.

One exact root-authorized projection. All missing dates/scopes stay missing;
the full070 mother order and identities remain untouched.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
spec=importlib.util.spec_from_file_location('stage111_pure071',TOOLS/'stage071_settlement_narrow_fit.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
PROTOCOL=LINE/'outputs/stage110_member_category_protocol/protocol.json'
PROTOCOL_SHA='80b9eb2f8e959fb61218b92c3c35049a3f5084817d784c211ece2fc5970a81bc'
CLARIFICATIONS=LINE/'outputs/stage110_member_category_protocol/implementation_clarifications.json'
CLARIFICATIONS_SHA='cf11f1d328ee7a0083668c7a364bf0f526c1c1612f55a26ce4880ed800f2e10e'
STAGE_ROOT=LINE/'outputs/stage111_member_category_projection'
IDENTITY=legacy.IDENTITY
PAIRS={('期货公司','非期货公司'):'domestic_members',
    ('期货公司会员/境外特殊经纪参与者','非期货公司会员/境外特殊非经纪参与者'):'members_and_overseas_special_participants'}
INPUT_ROLES={'narrow_labels','narrow_manifest','date_manifest','completion_receipt','source_acceptance','source_dates','implementation_clarifications'}
file_binding=legacy.file_binding;read_bound=legacy.read_bound;same_binding=legacy.same_binding
write_json=legacy.write_json;write_csv=legacy.write_csv

def source_bundle():
    return sorted([file_binding(TOOLS/n) for n in ('stage111_member_category_projection.py',
        'test_stage111_member_category_projection.py','stage071_settlement_narrow_fit.py')],key=lambda b:b['path'])

def integer(value):
    if value is None or isinstance(value,bool):return None
    try:
        q=Decimal(str(value).strip())
        return int(q) if q.is_finite() and q==q.to_integral_value() else None
    except (InvalidOperation,ValueError,TypeError):return None

def _instrument(value):
    value=str(value).strip()
    if re.fullmatch(r'[A-Za-z]+all',value,re.IGNORECASE):return value[:-3].lower(),'product_all',value
    if re.fullmatch(r'[A-Za-z]+[0-9]{4}',value):return re.sub(r'[0-9]+$','',value).lower(),'actual_contract',value
    return (value.lower() if re.fullmatch(r'[A-Za-z]+',value) else ''),'unknown',value

def _category(row):
    labels=[str(row.get('PARTICIPANTABBR'+str(i), '')).strip() for i in (1,2,3)]
    rank=integer(row.get('RANK'))
    known={s for pair in PAIRS for s in pair}
    return rank in (-1,0) or any(s in known for s in labels)

def _pair(rows):
    labels=[[str(r.get('PARTICIPANTABBR'+str(i),'')).strip() for i in (1,2,3)] for r in rows]
    audit=dict(raw_labels=[[r.get('PARTICIPANTABBR'+str(i)) for i in (1,2,3)] for r in rows],
        stripped_labels=labels,raw_ranks=[r.get('RANK') for r in rows],
        raw_LS=[[dict(field=k,raw=r.get(k),present=k in r,raw_type=type(r.get(k)).__name__,parsed_integer=integer(r.get(k)))
            for k in ('CJ2','CJ3')] for r in rows])
    if len(rows)!=2 or any(len(set(v))!=1 for v in labels):return None,audit
    by_rank={integer(r.get('RANK')):r for r in rows}
    if set(by_rank)!={-1,0}:return None,audit
    pair=(str(by_rank[-1].get('PARTICIPANTABBR1','')).strip(),str(by_rank[0].get('PARTICIPANTABBR1','')).strip())
    if pair not in PAIRS:return None,audit
    q={name:integer(by_rank[rank].get(key)) for name,rank,key in [('LN',0,'CJ2'),('SN',0,'CJ3'),('LF',-1,'CJ2'),('SF',-1,'CJ3')]}
    audit.update(population_version=PAIRS[pair],four_quantities=q)
    if any(v is None or v<0 for v in q.values()) or q['LN']+q['LF']!=q['SN']+q['SF']:return None,audit
    return dict(q,population_version=PAIRS[pair]),audit

def project_report(day,obj):
    """Use the entire cursor for contract inventory, not only category rows."""
    if not isinstance(obj,dict) or not isinstance(obj.get('o_cursor'),list) or any(not isinstance(r,dict) for r in obj['o_cursor']):return {}
    inventory=defaultdict(lambda:defaultdict(list));kinds={}
    for row in obj['o_cursor']:
        product,scope,instrument=_instrument(row.get('INSTRUMENTID',''))
        if not product:continue
        inventory[product][instrument].append(row);kinds[instrument]=scope
    report_date=obj.get('report_date')
    clock='report_date_absent' if report_date is None else ('matches' if str(report_date).strip().replace('-','')==day else 'mismatch')
    result={}
    for product,scopes in inventory.items():
        all_ids=sorted(k for k in scopes if kinds[k]=='product_all')
        contracts=sorted(k for k in scopes if kinds[k]=='actual_contract')
        unknown=[k for k in scopes if kinds[k]=='unknown' and any(_category(r) for r in scopes[k])]
        chosen=all_ids if all_ids else contracts
        scope='product_all' if all_ids else 'reported_actual_contract_set'
        item=dict(observed=0,scalar=None,LN=None,SN=None,LF=None,SF=None,scope=scope,
            population_version='unknown',report_date_state=clock,source_date=day,
            disclosed_real_contract_ids=contracts,selected_instrument_ids=chosen,
            all_instrument_ids=all_ids,unknown_scope_ids=unknown,scope_pair_audit=[],nonselected_contract_pair_audit=[],missing_reason='')
        if all_ids:
            for instrument in contracts:
                pair,audit=_pair([r for r in scopes[instrument] if _category(r)])
                item['nonselected_contract_pair_audit'].append(dict(instrument=instrument,complete_pair=pair is not None,**audit))
        if clock=='mismatch':item['missing_reason']='report_date_mismatch'
        elif unknown:item['missing_reason']='unknown_category_scope'
        elif not chosen:item['missing_reason']='no_disclosed_real_contract_or_all_scope'
        elif all_ids and len(all_ids)!=1:item['missing_reason']='incomplete_or_conflicting_all_scope'
        else:
            values=[]
            for instrument in chosen:
                pair,audit=_pair([r for r in scopes[instrument] if _category(r)])
                item['scope_pair_audit'].append(dict(instrument=instrument,**audit))
                if pair is not None:values.append(pair)
            versions={q['population_version'] for q in values}
            if len(values)!=len(chosen) or len(versions)!=1:
                item['missing_reason']='incomplete_or_conflicting_all_scope' if all_ids else 'incomplete_or_conflicting_contract_scope'
            else:
                totals={name:sum(v[name] for v in values) for name in ('LN','SN','LF','SF')}
                gross=sum(totals.values())
                scalar=(totals['LN']-totals['SN'])/gross if gross else 0.
                if not np.isfinite(scalar):item['missing_reason']='nonfinite_scalar'
                else:item.update(totals,observed=1,scalar=scalar,population_version=versions.pop())
        result[product]=item
    return result

def project_mother(mother,source_days,day_records):
    calendar=sorted(mother.u_date.unique());ranks={u:i for i,u in enumerate(calendar)}
    previous={u:(calendar[i-1] if i else '') for i,u in enumerate(calendar)}
    rows=[]
    for r in mother[IDENTITY].itertuples(index=False,name=None):
        row=dict(zip(IDENTITY,r));v=previous[row['u_date']];day=v.replace('-','')
        product=row['product_id'];match=re.fullmatch(r'SHFE\.([A-Z]+)',product)
        item=source_days.get(day,{}).get(match.group(1).lower()) if match else None
        record=day_records.get(day,{})
        reason=('no_previous_mother_source_date' if not v else 'product_outside_exact_SHFE_mapping' if not match
            else 'source_date_unavailable' if day not in source_days else 'no_product_category_scope' if item is None else item['missing_reason'])
        observed=bool(item and item['observed'])
        row.update(v_date=v,v_calendar_rank=ranks[v] if v else -1,
            external_scalar_raw=item['scalar'] if observed else np.nan,external_observed=int(observed),external_missing=int(not observed),
            projection_state='observed_archive_member_categories_lag1' if observed else 'missing',missing_reason='' if observed else reason,
            population_version=item['population_version'] if item else 'unknown',scope=item['scope'] if item else 'unknown',
            report_date_state=item['report_date_state'] if item else 'unavailable',source_status=record.get('status','outside_source_acquisition'),
            source_locator=record.get('archive_path',record.get('source_path','')),source_raw_sha256=record.get('raw_body_sha256',''),
            selected_instrument_ids_json=json.dumps(item['selected_instrument_ids'] if item else [],ensure_ascii=False),
            disclosed_real_contract_ids_json=json.dumps(item['disclosed_real_contract_ids'] if item else [],ensure_ascii=False),
            four_quantities_json=json.dumps({k:item[k] for k in ('LN','SN','LF','SF')} if observed else None,ensure_ascii=False),
            scope_pair_audit_json=json.dumps(item['scope_pair_audit'] if item else [],ensure_ascii=False),
            first_publication_qualified=False,contract_epoch_equivalence_claim=False)
        rows.append(row)
    return pd.DataFrame(rows)

def _bound_size(b):return dict(path=b['path'],bytes=b.get('bytes',b.get('size')),sha256=b['sha256'])

def source_request_accounting_valid(completion,records,recovery_receipt):
    """Keep the two killed in-flight requests unknown, never fake HTTP finishes."""
    recovery=completion.get('recovery')
    unknown=sorted(r['date'] for r in records if r.get('status')=='interrupted_unknown')
    if recovery is None:
        return (recovery_receipt is None and not unknown
            and completion.get('new_get_started')==completion.get('new_get_finished'))
    expected=dict(schema='stage116_interrupted_source_recovery_v1',
        interrupted_dates=['20231213','20231214'],interrupted_request_count=2,
        complete_terminal_statuses=3588,prior_finished=2893,resumed_started=680,resumed_finished=680)
    return (isinstance(recovery_receipt,dict)
        and all(recovery.get(k)==v and recovery_receipt.get(k)==v for k,v in expected.items())
        and unknown==expected['interrupted_dates']
        and completion.get('new_get_started')==3575
        and completion.get('new_get_finished')==3573)

def authorize(args):
    out=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in out.parents or out.exists():raise ValueError('fresh Stage111 output required')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen110 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes());binding=file_binding(args.authorization)
    if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(binding));required=dict(schema='stage110_exact_root_authorization_v1',authorized_by='root',stage='projection',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact111 root authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('projection source bundle differs')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('projection input roles differ')
    if (file_binding(CLARIFICATIONS)['sha256']!=CLARIFICATIONS_SHA
            or not same_binding(auth['input_bindings']['implementation_clarifications'],file_binding(CLARIFICATIONS))):
        raise ValueError('frozen110 implementation clarification differs')
    return out,protocol,auth,binding

def run_actual(out,protocol,auth,authorization):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();inputs=auth['input_bindings']
    write_json(out/'actual_started.json',dict(status='started',started_utc=datetime.now(timezone.utc).isoformat(),protocol=file_binding(PROTOCOL),
        source_bundle=bundle,authorization=authorization,fixture=False))
    try:
        acceptance=json.loads(read_bound(inputs['source_acceptance']));completion=json.loads(read_bound(inputs['completion_receipt']))
        if (acceptance.get('schema')!='stage110_member_source_acceptance_v1' or acceptance.get('accepted_by')!='root'
                or acceptance.get('source_accepted') is not True or acceptance.get('protocol_sha256')!=PROTOCOL_SHA
                or not same_binding(acceptance.get('completion_receipt',{}),inputs['completion_receipt'])
                or not same_binding(acceptance.get('date_manifest',{}),inputs['date_manifest'])):raise ValueError('explicit root109 source acceptance required')
        fixed108=next(b for b in protocol['bound_inputs'] if b['path'].endswith('stage108_member_category_history_protocol/protocol.json'))
        fixed_dates=next(b for b in protocol['bound_inputs'] if b['path'].endswith('/source_dates.json'))
        fixed109=next(b for b in protocol['bound_inputs'] if b['path'].endswith('/stage109_member_category_history.py'))
        if (completion.get('stage')!=109 or completion.get('protocol_sha256')!=fixed108['sha256'] or not completion.get('finished_utc')
                or completion.get('date_count')!=3588
                or any(completion.get(k)!=0 for k in ('fit','cash','sql'))
                or completion.get('implementation_sha256')!=fixed109['sha256']
                or completion.get('date_manifest_sha256')!=inputs['date_manifest']['sha256']):raise ValueError('109 terminal binding differs')
        read_bound(inputs['implementation_clarifications'])
        if not same_binding(inputs['source_dates'],_bound_size(fixed_dates)):raise ValueError('fixed source calendar binding differs')
        dates=json.loads(read_bound(inputs['source_dates']))['dates']
        records=[json.loads(s) for s in read_bound(inputs['date_manifest']).splitlines() if s]
        if [r['date'] for r in records]!=dates or len(set(dates))!=3588:raise ValueError('complete source date statuses differ')
        recovery_receipt=(json.loads(read_bound(acceptance['acquisition_recovery']))
            if acceptance.get('acquisition_recovery') else None)
        if not source_request_accounting_valid(completion,records,recovery_receipt):
            raise ValueError('source request terminal accounting differs')
        narrow=json.loads(read_bound(inputs['narrow_manifest']))
        if narrow.get('schema')!='stage070_narrow_labels_v1' or narrow.get('status')!='completed' or not same_binding(narrow.get('labels_narrow',{}),inputs['narrow_labels']):raise ValueError('accepted mother manifest differs')
        mother=pd.read_csv(io.BytesIO(read_bound(inputs['narrow_labels'])),compression='gzip',usecols=IDENTITY,dtype=str,keep_default_na=False)
        legacy._numeric(mother,['sequence_index','u_index'])
        if len(mother)!=399252 or mother.event_id.duplicated().any() or not np.array_equal(mother.sequence_index,np.arange(399252)) or mother.u_date.nunique()!=4074:raise ValueError('complete mother identity/calendar differs')
        days={};audits=[];products=[]
        for record in records:
            day=record['date'];state=record.get('status');audit=dict(date=day,status=state,raw_read=False,parse_state='unavailable')
            if state not in ('http_200','reused_stage104_106') or record.get('truncated') or record.get('error_type'):
                audits.append(audit);continue
            if state=='reused_stage104_106':raw=Path(record['source_path']).read_bytes()
            else:
                archive=Path(record['archive_path']).read_bytes()
                if len(archive)!=record['archive_bytes'] or hashlib.sha256(archive).hexdigest()!=record['archive_sha256']:raise ValueError('109 raw archive differs')
                raw=gzip.decompress(archive)
            if len(raw)!=record['raw_body_bytes'] or hashlib.sha256(raw).hexdigest()!=record['raw_body_sha256']:raise ValueError('109 original response differs')
            audit['raw_read']=True
            try:
                body=gzip.decompress(raw) if record.get('headers',{}).get('Content-Encoding','').lower()=='gzip' else raw
                obj=json.loads(body)
            except (ValueError,OSError,EOFError):audit['parse_state']='not_json';audits.append(audit);continue
            if not isinstance(obj,dict) or not isinstance(obj.get('o_cursor'),list) or any(not isinstance(r,dict) for r in obj['o_cursor']):
                audit['parse_state']='unrecognized_schema';audits.append(audit);continue
            days[day]=project_report(day,obj);audit.update(parse_state='json_cursor',products=len(days[day]),observed_products=sum(p['observed'] for p in days[day].values()))
            audits.append(audit)
            for product,item in days[day].items():products.append(dict(date=day,product=product,projection_json=json.dumps(item,ensure_ascii=False)))
        projection=project_mother(mother,days,{r['date']:r for r in records})
        legacy._identity(mother,projection)
        p=write_csv(out/'member_category_projection.csv.gz',projection)
        d=write_csv(out/'source_day_audit.csv.gz',pd.DataFrame(audits))
        s=write_csv(out/'product_scope_audit.csv.gz',pd.DataFrame(products))
        if source_bundle()!=bundle:raise ValueError('source changed during projection')
        write_json(out/'actual_terminal.json',dict(status='completed',exit_code=0,completed_projection_rows=len(projection),
            native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,
            source_dates=len(records),source_raw_files_read=sum(a['raw_read'] for a in audits),elapsed_seconds=time.monotonic()-started,fixture=False))
        manifest=dict(schema='stage111_member_category_projection_v1',status='completed',mode='actual',protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,
            authorization=authorization,source_bundle=bundle,input_bindings=inputs,projection=p,terminal=file_binding(out/'actual_terminal.json'),
            source_day_audit=d,product_scope_audit=s,mother_rows=len(projection),source_dates=len(records),
            observed_rows=int(projection.external_observed.sum()),missing_rows=int(projection.external_missing.sum()),
            missing_reasons=projection.missing_reason.value_counts().to_dict(),native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,
            first_publication_qualified=False,all_listed_months_scope_qualified=False,
            scalar='(LN-SN)/(LN+SN+LF+SF); true gross0=>0',calendar='4074_mother_u_dates_exact_predecessor_not_native_index_minus1')
        write_json(out/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (out/'actual_terminal.json').exists():write_json(out/'actual_terminal.json',dict(status='failed',exit_code=1,native_source_queries=0,
            actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,error_type=type(error).__name__,error=str(error),automatic_retry=False))
        raise

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-sha256','authorization','authorization-sha256'):p.add_argument('--'+name,required=True)
    out,protocol,auth,binding=authorize(p.parse_args(argv));m=run_actual(out,protocol,auth,binding)
    print(json.dumps(dict(status=m['status'],mother_rows=m['mother_rows'],observed_rows=m['observed_rows'])),flush=True)

if __name__=='__main__':main()
