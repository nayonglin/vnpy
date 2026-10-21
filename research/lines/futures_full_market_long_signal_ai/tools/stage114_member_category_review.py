"""Independent110 raw scopes/models/cash audit; never imports author calculators."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,os,re,time,traceback
import csv as csvlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='80b9eb2f8e959fb61218b92c3c35049a3f5084817d784c211ece2fc5970a81bc'
CLARIFICATIONS_SHA='cf11f1d328ee7a0083668c7a364bf0f526c1c1612f55a26ce4880ed800f2e10e'
LABELS={'期货公司':('FC','legacy'),'非期货公司':('NFC','legacy'),'期货公司会员/境外特殊经纪参与者':('FC','expanded'),'非期货公司会员/境外特殊非经纪参与者':('NFC','expanded')}

def exact_integer(value,nonnegative=False):
    if isinstance(value,bool) or value is None:raise ValueError('invalid exact integer')
    try:q=Decimal(str(value).strip())
    except (InvalidOperation,ValueError,TypeError):raise ValueError('invalid exact integer')
    if not q.is_finite() or q!=q.to_integral_value() or (nonnegative and q<0):raise ValueError('invalid exact integer')
    return int(q)

def parse_instrument(row):
    raw=str(row.get('INSTRUMENTID','')).strip();match=re.fullmatch(r'([A-Za-z]+?)(all|[0-9]{4})',raw,re.I)
    return (match[1].lower(),raw.lower(),match[2].lower()=='all') if match else (raw.lower() if re.fullmatch('[A-Za-z]+',raw) else None,raw.lower(),False)

def pair_values(rows):
    roles={};versions=set()
    for row in rows:
        labels=[str(row.get('PARTICIPANTABBR'+str(i),'')).strip()for i in (1,2,3)]
        try:rank=exact_integer(row.get('RANK'))
        except ValueError:rank=None
        category=(rank in (-1,0) or any(x in LABELS for x in labels))
        if not category:continue
        if len(set(labels))!=1 or labels[0] not in LABELS:return None,'label_unknown_or_disagreement'
        role,version=LABELS[labels[0]]
        if rank!=(-1 if role=='FC' else 0) or role in roles:return None,'rank_or_duplicate_role'
        try:long=exact_integer(row.get('CJ2'),True);short=exact_integer(row.get('CJ3'),True)
        except ValueError:return None,'invalid_four_quantities'
        roles[role]=(long,short);versions.add(version)
    if set(roles)!={'FC','NFC'}:return None,'incomplete_pair'
    if len(versions)!=1:return None,'mixed_population_version'
    lf,sf=roles['FC'];ln,sn=roles['NFC']
    if lf+ln!=sf+sn:return None,'unbalanced_scope'
    return dict(L_N=ln,S_N=sn,L_F=lf,S_F=sf,versions=sorted(versions)),None

def product_scalar(rows,product):
    product=product.lower();inventory={};has_all=False;unknown=False
    for row in rows:
        code,instrument,is_all=parse_instrument(row)
        if code!=product:continue
        if not re.fullmatch(r'[a-z]+(?:all|[0-9]{4})',instrument):
            try:rank=exact_integer(row.get('RANK'))
            except ValueError:rank=None
            unknown|=rank in (-1,0) or any(str(row.get('PARTICIPANTABBR'+str(i),'')).strip() in LABELS for i in (1,2,3))
            continue
        inventory.setdefault(instrument,[]).append(row);has_all|=is_all
    scopes=sorted(k for k,v in inventory.items() if parse_instrument(v[0])[2]) if has_all else sorted(inventory)
    missing=lambda reason:dict(observed=False,s=None,reason=reason,scopes=scopes,versions=[],L_N=None,S_N=None,L_F=None,S_F=None,gross=None)
    if unknown:return missing('unknown_category_scope')
    if not scopes:return missing('no_disclosed_scope')
    if has_all and len(scopes)!=1:return missing('ambiguous_all_scope')
    quantities=dict(L_N=0,S_N=0,L_F=0,S_F=0);versions=set()
    for scope in scopes:
        pair,error=pair_values(inventory[scope])
        if error:return missing(error)
        for key in quantities:quantities[key]+=pair[key]
        versions.update(pair['versions'])
    if len(versions)!=1:return missing('mixed_population_version')
    gross=sum(quantities.values());numerator=quantities['L_N']-quantities['S_N']
    s=numerator/gross if gross else 0.
    assert -.5<=s<=.5 and quantities['L_N']+quantities['L_F']==quantities['S_N']+quantities['S_F']
    return dict(observed=True,s=s,reason=None,scopes=scopes,versions=sorted(versions),gross=gross,**quantities)

def lag_dates(dates):
    days=sorted(set(dates));return {day:days[i-1] if i else None for i,day in enumerate(days)}

AUDIT_HELPERS={'stage102_cash_adapter.py': '702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044', 'stage102_cash_core.py': '4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa', 'stage102_cash_diagnostics.py': '0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc', 'stage102_fit_checks.py': 'a7afe80d4a22f74857c1f48ca90b15467acb45385a019d4f00424c3429696e6a', 'stage102_native_checks.py': '5d869f86465e9e309b36baa9453644a004f1c0e2c4366e63e816164c57ec1ecd', 'stage102_target_math.py': '416ec9d4291e28e50e28e51de44c37a862e649d3de7ec9875bfddad90b279f6d'}

def bound(binding):
    raw=Path(binding['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==binding['sha256'],('binding SHA',binding['path'])
    size=binding.get('bytes',binding.get('size'))
    if size is not None:assert len(raw)==size,('binding bytes',binding['path'])
    return raw

def bind(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def audit_helpers():
    for name,sha in AUDIT_HELPERS.items():assert bind(LINE/'tools'/name)['sha256']==sha,('independent helper changed',name)
    import numpy as np
    import pandas as pd
    import stage102_cash_adapter as cash
    import stage102_cash_diagnostics as diagnostics
    from stage102_native_checks import review_native
    from stage102_fit_checks import load_labels,weights,stats,table,convert,compare_dict
    return np,pd,cash,diagnostics,review_native,load_labels,weights,stats,table,convert,compare_dict

def raw_report(record):
    """One saved body read, no network; compressed transport is not JSON repair."""
    if record.get('status') not in ('http_200','reused_stage104_106') or record.get('truncated') or record.get('error_type') or record.get('transport_error'):return None,'source_transport_or_status_unknown'
    if record.get('reused'):
        raw=bound(dict(path=record['source_path'],bytes=record['raw_body_bytes'],sha256=record['raw_body_sha256']))
    elif record.get('archive_path'):
        archive=bound(dict(path=record['archive_path'],bytes=record['archive_bytes'],sha256=record['archive_sha256']))
        raw=gzip.decompress(archive)
        assert len(raw)==record['raw_body_bytes'] and hashlib.sha256(raw).hexdigest()==record['raw_body_sha256']
    else:return None,'source_unavailable'
    if record.get('status') not in ('http_200','reused_stage104_106') or record.get('truncated') or record.get('error') or record.get('transport_error'):
        return None,'source_transport_or_status_unknown'
    encoding={str(k).lower():str(v).lower() for k,v in record.get('headers',{}).items()}.get('content-encoding','')
    try:
        payload=gzip.decompress(raw) if encoding=='gzip' else raw
        obj=json.loads(payload,parse_float=Decimal)
    except Exception:return None,'unrecognized_json'
    if not isinstance(obj,dict) or not isinstance(obj.get('o_cursor'),list) or any(not isinstance(row,dict)for row in obj['o_cursor']):return None,'unrecognized_cursor'
    report=obj.get('report_date')
    if report is not None and str(report).strip().replace('-','')!=record['date']:return obj['o_cursor'],'report_date_mismatch'
    return obj['o_cursor'],'report_date_absent' if report is None else 'report_date_matches'

ID=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ARMS=('CONTROL','NFC');SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
VERSION={'legacy':'domestic_members','expanded':'members_and_overseas_special_participants'}
def candidate(row):
    try:rank=exact_integer(row.get('RANK'))
    except ValueError:rank=None
    return rank in (-1,0) or any(str(row.get('PARTICIPANTABBR'+str(i),'')).strip() in LABELS for i in (1,2,3))

def raw_equal(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(raw_equal(a[k],b[k]) for k in a)
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(raw_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float,Decimal)) and not isinstance(a,bool) and isinstance(b,(int,float,Decimal)) and not isinstance(b,bool):
        x,y=Decimal(str(a)),Decimal(str(b));return (x.is_nan() and y.is_nan()) or x==y
    return type(a)is type(b) and a==b

def check_pair_audit(saved,rows):
    rows=[r for r in rows if candidate(r)]
    assert raw_equal(saved['raw_labels'],[[r.get('PARTICIPANTABBR'+str(i)) for i in (1,2,3)]for r in rows])
    assert saved['stripped_labels']==[[str(r.get('PARTICIPANTABBR'+str(i),'')).strip()for i in (1,2,3)]for r in rows]
    assert raw_equal(saved['raw_ranks'],[r.get('RANK')for r in rows]) and len(saved['raw_LS'])==len(rows)
    for actual,row in zip(saved['raw_LS'],rows):
        assert len(actual)==2
        for value,key in zip(actual,('CJ2','CJ3')):
            try:integer=exact_integer(row.get(key))
            except ValueError:integer=None
            typ='float' if isinstance(row.get(key),Decimal) else type(row.get(key)).__name__
            assert value['field']==key and value['present']==(key in row) and value['raw_type']==typ and raw_equal(value['raw'],row.get(key)) and value['parsed_integer']==integer
    # Optional parsed-role detail is present only after exact two-row label/rank structure.
    structural=False;by_rank={}
    if len(rows)==2:
        try:by_rank={exact_integer(r.get('RANK')):r for r in rows}
        except ValueError:pass
        if set(by_rank)=={-1,0}:
            texts=[[str(r.get('PARTICIPANTABBR'+str(i),'')).strip()for i in (1,2,3)]for r in [by_rank[-1],by_rank[0]]]
            structural=all(len(set(v))==1 for v in texts) and texts[0][0] in LABELS and texts[1][0] in LABELS and LABELS[texts[0][0]][0]=='FC' and LABELS[texts[1][0]][0]=='NFC' and LABELS[texts[0][0]][1]==LABELS[texts[1][0]][1]
    if structural:
        assert saved['population_version']==VERSION[LABELS[texts[0][0]][1]]
        for name,rank,key in [('LN',0,'CJ2'),('SN',0,'CJ3'),('LF',-1,'CJ2'),('SF',-1,'CJ3')]:
            try:value=exact_integer(by_rank[rank].get(key))
            except ValueError:value=None
            assert saved['four_quantities'][name]==value
    else:assert 'population_version'not in saved and 'four_quantities'not in saved

def check_product_audit(saved,group,own,clock):
    raw_scopes=defaultdict(list)
    for row in group:raw_scopes[str(row.get('INSTRUMENTID','')).strip()].append(row)
    allids=sorted(k for k in raw_scopes if re.fullmatch('[A-Za-z]+all',k,re.I))
    contracts=sorted(k for k in raw_scopes if re.fullmatch('[A-Za-z]+[0-9]{4}',k))
    unknown=[k for k in raw_scopes if not re.fullmatch('[A-Za-z]+(?:all|[0-9]{4})',k,re.I) and any(candidate(r)for r in raw_scopes[k])]
    chosen=allids if allids else contracts
    assert saved['disclosed_real_contract_ids']==contracts and saved['all_instrument_ids']==allids and saved['selected_instrument_ids']==chosen and saved['unknown_scope_ids']==unknown
    assert saved['scope']==('product_all'if allids else 'reported_actual_contract_set') and saved['report_date_state']==clock
    assert saved['observed']==int(own['observed'])
    if own['observed']:
        for a,b in [('LN','L_N'),('SN','S_N'),('LF','L_F'),('SF','S_F')]:assert saved[a]==own[b]
        assert abs(saved['scalar']-own['s'])<=1e-15 and saved['population_version']==VERSION[own['versions'][0]] and saved['missing_reason']==''
    else:assert saved['scalar']is None and all(saved[k]is None for k in ('LN','SN','LF','SF')) and saved['missing_reason']
    qa=[] if clock=='mismatch' or unknown or not chosen or (allids and len(allids)!=1) else chosen
    assert [q['instrument']for q in saved['scope_pair_audit']]==qa
    for q,k in zip(saved['scope_pair_audit'],qa):check_pair_audit(q,raw_scopes[k])
    nonselected=contracts if allids else []
    assert [q['instrument']for q in saved['nonselected_contract_pair_audit']]==nonselected
    for q,k in zip(saved['nonselected_contract_pair_audit'],nonselected):
        check_pair_audit(q,raw_scopes[k]);pair,error=pair_values(raw_scopes[k]);assert q['complete_pair']==(error is None)

def split_resume_request_segments(combined,prefix):
    assert combined.startswith(prefix) and prefix.endswith(b'\n'),'prior request prefix changed'
    parse=lambda raw:[json.loads(row)for row in raw.splitlines()if row]
    return [parse(prefix),parse(combined[len(prefix):])]

def audit_request_accounting(completion,records,recovery,original_requests,resumed_segments,dates,new_dates,reuse_dates,url_template):
    """Independently count actual requests; process loss is never an HTTP finish."""
    assert len(dates)==3588 and dates==sorted(set(dates)) and [r['date']for r in records]==dates
    reused=set(reuse_dates);new=set(new_dates)
    assert len(reused)==13 and len(new)==3575 and not reused&new and reused|new==set(dates)
    unknown=sorted(r['date']for r in records if r.get('status')=='interrupted_unknown')
    if recovery is None:
        assert not unknown and not original_requests and not resumed_segments and completion.get('recovery')is None
    else:
        assert recovery==completion.get('recovery') and recovery['schema']=='stage116_interrupted_source_recovery_v1'
        assert unknown==['20231213','20231214']==recovery['interrupted_dates'] and recovery['interrupted_request_count']==2
        assert recovery['complete_terminal_statuses']==3588 and completion['terminal_statuses_complete']is True
        assert recovery['interrupted_acquisition']is True and recovery['single_uninterrupted_execution_claim']is False and recovery['original_evidence_modified']is False
        assert all(recovery[k]==0 for k in('fit','cash','sql'))
    resumed=[r for segment in resumed_segments for r in segment]
    requested=original_requests+resumed
    request_by={r['date']:r for r in requested}
    if recovery is not None:
        assert len(original_requests)==2895 and recovery['prior_finished']==2893
        assert len(request_by)==len(requested) and set(request_by)<=new, 'duplicate or foreign request'
        assert set(unknown)<=set(r['date']for r in original_requests)
        assert recovery['resumed_started']==len(resumed)==recovery['resumed_finished']
        assert completion['new_get_started']==len(requested)
        for request in requested:
            assert request['url']==url_template.format(date=request['date']) and request['attempt']==1
            assert request['automatic_retry']is False and request['redirect_following']is False
    statuses=Counter();attempted=set();finished=0
    for record in records:
        day=record['date'];status=record['status'];statuses[status]+=1
        if record.get('reused'):
            assert day in reused and status=='reused_stage104_106';continue
        assert day in new
        if status=='not_requested':
            assert recovery is None or day not in request_by
            continue
        attempted.add(day)
        if status=='interrupted_unknown':
            assert recovery is not None and day in unknown
            assert record.get('request_started')==request_by[day] and record.get('automatic_retry')is False
            assert not any(record.get(k)is not None for k in('archive_path','source_path','raw_body_sha256','normalized_path','finished_utc','http_status'))
            continue
        assert status in('http_200','network_error','http_non200','truncated')
        assert record['url']==url_template.format(date=day) and record['attempt']==1
        assert record['automatic_retry']is False and record['redirect_following']is False
        if 'response_url'in record:assert record['response_url']==record['url']
        if recovery is not None:
            for key,value in request_by[day].items():assert record[key]==value,('request anchor changed',day,key)
        finished+=1
    assert statuses['reused_stage104_106']==13 and len(attempted)==completion['new_get_started'] and finished==completion['new_get_finished']
    assert len(attempted)-finished==len(unknown) and len(attempted)<=3575
    if recovery is not None:assert attempted==set(request_by)
    return dict(actual_requests=len(attempted),true_finished=finished,interrupted_unknown=len(unknown),not_requested=statuses['not_requested'],status_counts=dict(statuses),resumed_segment_sizes=[len(segment)for segment in resumed_segments],duplicate_requests=0,single_uninterrupted_execution_claim=recovery is None)

def review_source(manifest,labels,np,pd,compare,table):
    inputs=manifest['input_bindings'];records=[json.loads(row)for row in bound(inputs['date_manifest']).splitlines()if row]
    dates=json.loads(bound(inputs['source_dates']))['dates'];assert [r['date']for r in records]==dates and len(dates)==3588 and dates==sorted(set(dates))
    completion=json.loads(bound(inputs['completion_receipt']));acceptance=json.loads(bound(inputs['source_acceptance']))
    assert completion['stage']==109 and completion['date_count']==3588 and completion['reused_dates']==13 and all(completion[k]==0 for k in ('fit','cash','sql')) and completion['date_manifest_sha256']==inputs['date_manifest']['sha256']
    assert acceptance['schema']=='stage110_member_source_acceptance_v1' and acceptance['accepted_by']=='root' and acceptance['source_accepted']is True and acceptance['protocol_sha256']==PROTOCOL_SHA
    assert acceptance['date_manifest']==inputs['date_manifest'] and acceptance['completion_receipt']==inputs['completion_receipt']
    p110=json.loads(bound(manifest['protocol']));p108_binding=next(b for b in p110['bound_inputs']if b['path'].endswith('stage108_member_category_history_protocol/protocol.json'));p108=json.loads(bound(p108_binding));reuse={v['date']:v for v in p108['reuse']}
    assert completion['protocol_sha256']==p108_binding['sha256']and completion['implementation_sha256']==next(b['sha256']for b in p110['bound_inputs']if b['path'].endswith('/stage109_member_category_history.py'))and same(inputs['source_dates'],p108['source_dates'])
    recovery=None;original_requests=[];resumed_segments=[]
    if completion.get('recovery')is not None:
        recovery=json.loads(bound(acceptance['acquisition_recovery']))
        assert same(acceptance['acquisition_recovery'],completion['recovery_receipt'])
        original_requests=[json.loads(row)for row in bound(recovery['original_requests_started']).splitlines()if row]
        resumed_bytes=bound(recovery['resumed_requests_started']);resumed_segments=[[json.loads(row)for row in resumed_bytes.splitlines()if row]]
        original_started=json.loads(bound(recovery['original_started']));assert original_started['implementation_sha256']==completion['implementation_sha256']
        bound(recovery['wrapper']);recovery_protocol=json.loads(bound(recovery['recovery_protocol']))
        assert same(recovery_protocol['original_requests_started'],recovery['original_requests_started']) and same(recovery_protocol['original_started'],recovery['original_started'])
        assert recovery_protocol['interrupted_dates']==['20231213','20231214'] and recovery_protocol['prior_started']==2895 and recovery_protocol['prior_finished']==2893
        assert recovery_protocol['wall_origin_utc']==original_started['started_utc'] and recovery_protocol['wall_total_max_seconds']==p108['wall_time_max_seconds']
        elapsed=(datetime.fromisoformat(completion['finished_utc'])-datetime.fromisoformat(original_started['started_utc'])).total_seconds()
        assert 0<elapsed<=p108['wall_time_max_seconds'] and recovery['unknown_body_bytes_upper_bound']==2*p108['per_response_bytes_max']
        if completion.get('execution_stage')==119:
            prefix=bound(recovery['requests_started_prefix']);resumed_segments=split_resume_request_segments(resumed_bytes,prefix)
            assert len(resumed_segments[0])==6 and len(recovery['extra_execution_segments'])==1
            assert recovery_protocol['extra_execution_segments']==recovery['extra_execution_segments'] and same(recovery_protocol['requests_started_prefix'],recovery['requests_started_prefix'])
            extra=recovery['extra_execution_segments'][0];assert extra['stage']==116 and extra['retried']is False and extra['finished']==extra['network_errors']==6 and extra['body_bytes']==0
            assert same(extra['requests_started'],recovery['requests_started_prefix']) and extra['attempted_dates']==sorted(r['date']for r in resumed_segments[0])
            bound(extra['wrapper']);bound(extra['started']);prior_completion=json.loads(bound(extra['completion']));prior_receipt=json.loads(bound(extra['recovery_receipt']))
            assert prior_completion['recovery']==prior_receipt and same(prior_completion['recovery_receipt'],extra['recovery_receipt'])
            assert prior_completion['new_get_started']==2901 and prior_completion['new_get_finished']==2899 and prior_receipt['resumed_started']==prior_receipt['resumed_finished']==6
            assert same(prior_receipt['original_requests_started'],recovery['original_requests_started']) and same(prior_receipt['resumed_requests_started'],extra['requests_started'])
            assert all(next(r for r in records if r['date']==day)['status']=='network_error'for day in extra['attempted_dates'])
        remaining=set(p108['new_get_dates'])-set(r['date']for r in original_requests)-set(r['date']for r in resumed_segments[0]if len(resumed_segments)>1)
        assert recovery_protocol['remaining_never_started_dates']==sorted(remaining) and recovery_protocol['remaining_get_count']==len(remaining)
        provenance=[json.loads(row)for row in bound(recovery['source_provenance']).splitlines()if row]
        assert [row['date']for row in provenance]==dates
        by_day={r['date']:r for r in records}
        for row in provenance:
            if row.get('date_record'):
                assert json.loads(bound(row['date_record']))==by_day[row['date']],('original source record changed',row['date'])
    else:assert not acceptance.get('acquisition_recovery')
    accounting=audit_request_accounting(completion,records,recovery,original_requests,resumed_segments,dates,p108['new_get_dates'],reuse,p108['url_template'])
    for record in records:
        day=record['date']
        if record.get('reused'):
            assert day in reuse and record['source_path']==reuse[day]['path']and record['raw_body_sha256']==reuse[day]['sha256']and record['raw_body_bytes']==reuse[day]['size']
    assert sum(bool(r.get('reused'))for r in records)==13
    reader=iter(csvlib.DictReader(io.StringIO(gzip.decompress(bound(manifest['product_scope_audit'])).decode())))
    current=next(reader,None);products={};source_states=Counter();scope_count=Counter();pairs=0;raw_reads=0;source_audit=[]
    for record in records:
        day=record['date'];rows,state=raw_report(record);source_states[state]+=1
        eligible=record.get('status')in('http_200','reused_stage104_106')and not record.get('truncated')and not record.get('error_type');raw_reads+=int(eligible)
        audit=dict(date=day,status=record.get('status'),raw_read=eligible,parse_state='unavailable')
        if rows is None:
            if eligible:audit['parse_state']='not_json'if state=='unrecognized_json'else'unrecognized_schema'
            assert current is None or current['date']!=day
            source_audit.append(audit);continue
        groups=defaultdict(list)
        for row in rows:
            code=parse_instrument(row)[0]
            if code:groups[code].append(row)
        saved={}
        while current is not None and current['date']==day:
            assert current['product']not in saved;saved[current['product']]=json.loads(current['projection_json']);current=next(reader,None)
        assert set(saved)==set(groups),(day,'product inventory')
        clock={'report_date_matches':'matches','report_date_absent':'report_date_absent','report_date_mismatch':'mismatch'}[state]
        for code,group in groups.items():
            own=product_scalar(group,code)
            if clock=='mismatch':own.update(observed=False,s=None,L_N=None,S_N=None,L_F=None,S_F=None,gross=None)
            check_product_audit(saved[code],group,own,clock);pairs+=len(saved[code]['scope_pair_audit'])+len(saved[code]['nonselected_contract_pair_audit'])
            products[(day,code.upper())]=dict(own,saved={k:saved[code][k]for k in ('population_version','scope','report_date_state','selected_instrument_ids','disclosed_real_contract_ids')});scope_count[saved[code]['scope']]+=1
        audit.update(parse_state='json_cursor',products=len(groups),observed_products=sum(v['observed']for v in saved.values()));source_audit.append(audit)
    assert current is None
    saved_day=table(manifest['source_day_audit']);assert len(saved_day)==3588
    for actual,expected in zip(saved_day.to_dict('records'),source_audit):
        for key,value in expected.items():
            if isinstance(value,bool):assert actual[key]==str(value)
            elif isinstance(value,int):assert exact_integer(actual[key])==value
            else:assert actual[key]==value
    needed=ID+['v_date','v_calendar_rank','external_scalar_raw','external_observed','external_missing','projection_state','missing_reason','population_version','scope','report_date_state','source_status','source_locator','source_raw_sha256','selected_instrument_ids_json','disclosed_real_contract_ids_json','four_quantities_json','first_publication_qualified','contract_epoch_equivalence_claim']
    projected=table(manifest['projection'],needed);assert len(projected)==399252 and labels.u_date.nunique()==4074 and labels.product_id.nunique()==98 and labels.family_id.nunique()==95 and labels.exchange.nunique()==6
    for key in ID:
        if key in('sequence_index','u_index'):compare(pd.to_numeric(projected[key]),labels[key],'projection_identity_'+key,atol=0,rtol=0)
        else:assert projected[key].tolist()==labels[key].tolist()
    previous=lag_dates(labels.u_date);rank={u:i for i,u in enumerate(sorted(previous))};record_by={r['date']:r for r in records};values=[];observed=[];versions=Counter();zeros=0
    for row in projected.to_dict('records'):
        v=previous[row['u_date']];day=(v or'').replace('-','');match=re.fullmatch(r'SHFE\.([A-Z]+)',row['product_id']);item=products.get((day,match[1]))if match else None;known=bool(item and item['observed']);record=record_by.get(day,{})
        assert row['v_date']==(v or'')and exact_integer(row['v_calendar_rank'])==(rank[v]if v else-1)
        assert exact_integer(row['external_observed'])==int(known)and exact_integer(row['external_missing'])==int(not known)
        assert row['projection_state']==('observed_archive_member_categories_lag1'if known else'missing')and bool(row['missing_reason'])!=known
        assert row['source_status']==record.get('status','outside_source_acquisition')and row['source_locator']==record.get('archive_path',record.get('source_path',''))and row['source_raw_sha256']==record.get('raw_body_sha256','')
        assert row['first_publication_qualified']=='False'and row['contract_epoch_equivalence_claim']=='False'
        source=item['saved']if item else None
        assert row['population_version']==(source['population_version']if source else'unknown')and row['scope']==(source['scope']if source else'unknown')and row['report_date_state']==(source['report_date_state']if source else'unavailable')
        assert json.loads(row['selected_instrument_ids_json'])==(source['selected_instrument_ids']if source else[])and json.loads(row['disclosed_real_contract_ids_json'])==(source['disclosed_real_contract_ids']if source else[])
        if known:
            values.append(item['s']);versions[source['population_version']]+=1;zeros+=int(item['s']==0)
            assert json.loads(row['four_quantities_json'])=={a:item[b]for a,b in [('LN','L_N'),('SN','S_N'),('LF','L_F'),('SF','S_F')]}
        else:values.append(np.nan);assert row['external_scalar_raw']==''and json.loads(row['four_quantities_json'])is None
        observed.append(int(known))
    scalar=np.asarray(values);mask=np.asarray(observed)
    coverage=labels[['product_id','family_id','u_date']].assign(observed=mask,nonzero=np.isfinite(scalar)&(scalar!=0));coverage['year']=coverage.u_date.str[:4]
    annual=coverage.groupby('year').agg(rows=('observed','size'),observed=('observed','sum'),nonzero=('nonzero','sum')).reset_index().to_dict('records')
    families=coverage.groupby('family_id').agg(rows=('observed','size'),observed=('observed','sum'),nonzero=('nonzero','sum')).reset_index().to_dict('records')
    serialized_scalar=pd.to_numeric(projected.external_scalar_raw.replace('',np.nan)).to_numpy(float)
    compare(serialized_scalar,scalar,'all399252_independent_category_scalar',atol=1e-15,rtol=1e-14)
    assert manifest['observed_rows']==int(mask.sum()) and manifest['missing_rows']==int((1-mask).sum()) and manifest['missing_reasons']==projected.missing_reason.value_counts().to_dict()
    # Independent raw reconstruction is compared above. Exact accepted CSV
    # parsing is used for numerical model paths, separate from source derivation.
    return serialized_scalar,mask,dict(source_dates=3588,request_accounting=accounting,product_days=len(products),per_scope_audits=pairs,eligible_raw_files_read=raw_reads,source_states=dict(source_states),scope_counts=dict(scope_count),mother_rows=399252,catalog_products=98,family_count=95,exchanges=6,observed_rows=int(mask.sum()),missing_rows=int((1-mask).sum()),observed_zero_rows=zeros,population_versions=dict(versions),annual_support=annual,family_support_including_zero=families,unique_mother_dates=4074,source_reconstruction_passes=1,new_SQL=0,new_network_requests=0)

def family_group(value):return int.from_bytes(hashlib.sha256(value.encode()).digest(),'big')%2

def identity_check(actual,expected,compare,label):
    assert actual.event_id.tolist()==expected.event_id.tolist(),label
    for key in ID:
        if key in ('sequence_index','u_index'):compare(pd.to_numeric(actual[key]),expected[key],label+'_'+key,atol=0,rtol=0)
        else:assert actual[key].tolist()==expected[key].tolist(),(label,key)

def head54(raw,observed,scalar,scaler,arm):
    finite=np.isfinite(raw);m=np.asarray(scaler['common']['mean']);z=np.asarray(scaler['common']['scale'])
    base=np.column_stack([(np.where(finite,raw,m)-m)/z,(~finite).astype(float),1-np.asarray(observed,int)])
    q=np.asarray(scalar,float);qz=np.where(np.isfinite(q),(q-scaler['scalar']['mean'])/scaler['scalar']['scale'],0.)
    return np.column_stack([base,qz if arm=='NFC'else np.zeros(len(q))]),base,qz

def held_diagnostics(predictions,labels,end):
    linked=predictions.loc[predictions.scope.ne('main')].merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one',sort=False)
    known=linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)&linked.label_known_date.ne('')&linked.label_known_date.le(end)&linked.history_ready20.eq(1)
    linked['diagnostic_known_domain']=known;linked['diagnostic_outcome_R']=linked.net_R_stress.where(known,np.nan)
    groups={};daily=[]
    for scope,g in linked.groupby('scope',sort=True):
        a=g.loc[g.arm.eq('CONTROL')].set_index('event_id');b=g.loc[g.arm.eq('NFC')].set_index('event_id').reindex(a.index)
        assert len(a)==len(b)and a.u_date.eq(b.u_date).all()
        domain=a.diagnostic_known_domain&b.diagnostic_known_domain
        z=pd.DataFrame(dict(u_date=a.loc[domain,'u_date'],delta_R=((b.selected-a.selected)*a.net_R_stress).loc[domain],mse_difference=((b.score-a.net_R_stress)**2-(a.score-a.net_R_stress)**2).loc[domain]))
        d=z.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_events=('delta_R','size'),mse_difference=('mse_difference','mean')).reset_index();d['scope']=scope;daily.append(d)
        point=float(d.delta_R.mean())if len(d)else None;disagree=b.selected.ne(a.selected)
        unresolved=~domain&~a.participation_state.eq('known_nonparticipation');unknown=int((disagree&unresolved).sum())
        states=pd.DataFrame(dict(state=a.label_state,disagreement=disagree.astype(int))).groupby('state').agg(full_events=('disagreement','size'),action_disagreements=('disagreement','sum')).reset_index().to_dict('records')
        groups[scope]=dict(nominal_pass=point is not None and point>=0,status='unsupported'if point is not None and point<0 else'unknown'if point is None or unknown else'supported',known_u_equal_mean_increment_R=point,known_common_events=int(domain.sum()),known_source_days=len(d),prediction_u_equal_MSE_difference=float(d.mse_difference.mean())if len(d)else None,full_mother_events=len(a),unknown_differential_selected_events=unknown,all_state_action_counts=states,unknown_R_bounds=None,annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()),prediction_u_equal_MSE_difference=float(v.mse_difference.mean()),known_source_days=len(v),known_events=int(v.known_events.sum()))for y,v in d.groupby(d.u_date.str[:4],sort=True)],cold_2023_view_mean_delta_R=float(d.loc[d.u_date.ge('2023-01-01'),'delta_R'].mean())if d.u_date.ge('2023-01-01').any()else None,meaning='closed_complete_bar_model and ready20 only; within-u all known rows mean including equal-action zero, then equal u; not cash/full opportunity value')
    return dict(schema='stage112_held_closed_diagnostic_v1',groups=groups,unknown_not_zero=True,cancellation_not_zero=True,full_policy_value_qualified=False,cash_return_qualified=False,contrast='NFC_minus_CONTROL'),pd.concat(daily,ignore_index=True),linked

def main_signal_diagnostics(labels,predictions,end):
    p=predictions.loc[predictions.scope.eq('main')]
    f=labels[['event_id','family_id','u_date','label_state','label_known_date','net_R_stress']].merge(p.pivot(index='event_id',columns='arm',values='selected'),on='event_id',validate='one_to_one',how='inner')
    f['actions_differ']=f.NFC.ne(f.CONTROL);f['closed_known']=f.label_state.eq('closed_complete_bar_model')&np.isfinite(f.net_R_stress)&f.label_known_date.ne('')&f.label_known_date.le(end);f['known_nonparticipation']=f.label_state.eq('known_nonparticipation');f['year']=f.u_date.str[:4]
    s=f.groupby(['year','label_state'],dropna=False).agg(rows=('event_id','size'),action_disagreements=('actions_differ','sum'),CONTROL_selected=('CONTROL','sum'),NFC_selected=('NFC','sum'),closed_known=('closed_known','sum')).reset_index()
    r=dict(main_prediction_rows_per_arm=len(f),full_mother_rows=len(labels),full_mother_label_states={str(k):int(v)for k,v in labels.label_state.value_counts(dropna=False).items()},unknown_differential_selected_events=int((f.actions_differ&~f.closed_known&~f.known_nonparticipation).sum()),known_nonparticipation_differential_selected_events=int((f.actions_differ&f.known_nonparticipation).sum()),unfilled_signal_label_uncertainty_is_not_cash_exposure=True)
    return r,s


def review_models(manifest,labels,scalar,observed,compare,table,weights,stats,compare_dict):
    root=Path(manifest['support_report']['path']).parent;inputs=manifest['input_bindings']
    with np.load(io.BytesIO(bound(inputs['common_npz'])),allow_pickle=False)as z:common=z['common'].copy();columns=z['columns'].tolist()
    identity=json.loads(bound(inputs['common_identity']));assert common.shape==(399252,26)and columns==identity['columns']and identity['event_ids_sha256']==hashlib.sha256(('\n'.join(labels.event_id)+'\n').encode()).hexdigest()
    support=json.loads(bound(manifest['support_report']));cells=[];prepared=[]
    for scope in SCOPES:
        for cutoff,stop in [('2020-01-01','2023-01-01'),('2023-01-01',None)]:
            mature=labels.label_state.eq('closed_complete_bar_model')&labels.u_date.lt(cutoff)&labels.label_known_date.ne('')&labels.label_known_date.lt(cutoff)
            future=labels.u_date.ge(cutoff)&(labels.u_date.lt(stop)if stop else True)
            if scope!='main':
                group=labels.family_id.map(family_group);mature&=group.ne(int(scope[-1]));future&=group.eq(int(scope[-1]))
            train=labels.loc[mature].sort_values(['u_date','event_id']);test=labels.loc[future].sort_values(['u_date','event_id']);ti=train.sequence_index.to_numpy(int);pi=test.sequence_index.to_numpy(int)
            unique,day,w=weights(train);q=scalar[ti];finite=np.isfinite(q);st=stats(q,w)
            if finite.any()and np.equal(q[finite],q[finite][0]).all():st=(float(q[finite][0]),0.,1.,int(finite.sum()))
            weighted={k:v for k,v in zip(('mean','var','scale','finite_count'),st)}
            positive=bool(finite.any()and q[finite].min()<q[finite].max()and np.isfinite(st[1])and st[1]>0)
            d=train.loc[finite];cells.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),finite_rows=int(finite.sum()),nonzero_rows=int(np.count_nonzero(q[finite])),weighted_stats=weighted,positive_weighted_variation=positive,observed_families=d.family_id.value_counts().to_dict(),observed_months=d.u_date.str[:7].value_counts().sort_index().to_dict()))
            prepared.append((scope,cutoff,train,test,ti,pi,unique,day,w,weighted))
    eligible=all(c['positive_weighted_variation']for c in cells)
    compare_dict(support,dict(schema='stage112_scalar_support_v1',status='supported'if eligible else'unsupported_scalar_support',cash_eligible=eligible,cells=cells,checked_before_any_fit=True,availability_is_not_row_or_action_gate=True,finite_support_does_not_establish_sample_sufficiency=True),'six_cell_support')
    if not eligible:
        assert manifest['status']=='unsupported_scalar_support'and manifest['actual_fit_calls_completed']==manifest['actual_fit_calls_attempted']==0 and manifest['cash_eligible']is False and manifest['prediction_rows']==0
        for key in ('predictions','predictions_main','predictions_holdout','held_diagnostic'):assert manifest[key]is None
        assert not(root/'folds').exists()
        return None,None,None,None,dict(cash_eligible=False,models_checked=0,predictions_checked=0,scalar_support=support)
    assert manifest['status']=='completed'and manifest['cash_eligible']is True
    pred=table(manifest['predictions'])
    for key in ('sequence_index','u_index','score','selected','history_ready20','external_missing'):pred[key]=pd.to_numeric(pred[key])
    assert len(pred)==644056 and pred.scope.isin(SCOPES).all() and pred.arm.isin(ARMS).all() and pred.policy.eq('NARROW').all() and not pred.duplicated(['scope','event_id','arm']).any()
    records=json.loads((root/'fit_records.json').read_text());models=[];names=columns+[c+'_missing'for c in columns]+['external_missing','nonagency_net_gross_fraction']
    for scope,cutoff,train,test,ti,pi,unique,day,w,qstats in prepared:
        cell=root/'folds'/scope/cutoff;saved=pd.read_csv(cell/'training_identity_weights.csv.gz',dtype=str,keep_default_na=False);identity_check(saved,train,compare,'training_identity')
        assert saved.label_known_date.tolist()==train.label_known_date.tolist()and saved.label_state.eq('closed_complete_bar_model').all()
        for key,value in [('uniqueness',unique),('u_normalized_weight',day),('sample_weight',w)]:compare(pd.to_numeric(saved[key]),value,'training_'+key,atol=1e-10)
        pi_saved=pd.read_csv(cell/'prediction_identity.csv.gz',dtype=str,keep_default_na=False);identity_check(pi_saved,test,compare,'prediction_identity');assert np.array_equal(pd.to_numeric(pi_saved.label_history_ready20),test.label_history_ready20)
        scaler=json.loads((cell/'scaler.json').read_text());st=np.asarray([stats(common[ti,j],w)for j in range(26)])
        for i,key in enumerate(('mean','var','scale','finite_count')):compare(scaler['common'][key],st[:,i],'common_scaler_'+key,atol=1e-10)
        compare_dict(scaler['scalar'],qstats,'scalar_stats')
        assert scaler['common']['columns']==columns and scaler['feature_names']==names and scaler['scope']==scope and scaler['cutoff']==cutoff and scaler['common_units']=='accepted_original_2N'
        trainx,base,qz=head54(common[ti],observed[ti],scalar[ti],scaler,'NFC');testx,testbase,testqz=head54(common[pi],observed[pi],scalar[pi],scaler,'NFC')
        with np.load(cell/'normalized_inputs.npz',allow_pickle=False)as cache:
            for key,value in [('train_base',base),('prediction_base',testbase),('train_scalar',qz),('prediction_scalar',testqz),('y',train.net_R_stress),('sample_weight',w),('train_sequence_index',ti),('prediction_sequence_index',pi)]:compare(cache[key],value,'normalized_'+key,atol=1e-10)
        for arm in ARMS:
            model=json.loads((cell/arm/'portable_model.json').read_text());coef=np.asarray(model['coef']);intercept=model['intercept']
            assert model['schema']=='stage112_portable_ridge_v1'and model['scope']==scope and model['arm']==arm and model['policy']=='NARROW'and model['cutoff']==cutoff and model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky')and model['feature_names']==names and len(coef)==54
            x=trainx if arm=='NFC'else np.column_stack([base,np.zeros(len(base))]);xt=testx if arm=='NFC'else np.column_stack([testbase,np.zeros(len(testbase))])
            a=np.column_stack([x,np.ones(len(x))]);lhs=a.T@(w[:,None]*a);lhs[np.arange(54),np.arange(54)]+=1.;rhs=a.T@(w*train.net_R_stress.to_numpy(float));beta=np.r_[coef,intercept]
            with np.load(cell/arm/'normal_equations.npz',allow_pickle=False)as ne:
                compare(ne['lhs'],lhs,'normal_equation_lhs',atol=2e-7);compare(ne['rhs'],rhs,'normal_equation_rhs',atol=2e-7);compare(ne['coefficient_with_intercept'],beta,'portable_beta',atol=1e-12);compare(ne['weight_sum'],w.sum(),'normal_weights',atol=1e-10)
            residual=float(np.max(np.abs(lhs@beta-rhs)));assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8)
            actual=pred.loc[pred.scope.eq(scope)&pred.cutoff.eq(cutoff)&pred.arm.eq(arm)];identity_check(actual,test,compare,'all_prediction_IDs');scores=xt@coef+intercept;compare(actual.score,scores,'all644056_scores',atol=1e-9)
            assert np.array_equal(actual.external_missing,1-observed[pi])and np.array_equal(actual.history_ready20,test.label_history_ready20)and np.array_equal(actual.selected,(test.label_history_ready20.eq(1).to_numpy()&np.isfinite(scores)&(scores>0)).astype(int))
            rec=next(r for r in records if(r['scope'],r['cutoff'],r['arm'])==(scope,cutoff,arm))
            for key,value in dict(policy='NARROW',dimension=54,target='net_R_stress',training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),training_external_missing=int((1-observed[ti]).sum()),prediction_rows=len(test),prediction_external_missing=int((1-observed[pi]).sum()),selected=int(actual.selected.sum()),max_u_date=train.u_date.max(),max_label_known_date=train.label_known_date.max(),training_identity_sha256=hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()).items():assert rec[key]==value,(scope,cutoff,arm,key)
            assert rec['training_label_states']==train.label_state.value_counts().to_dict()
            models.append(dict(scope=scope,cutoff=cutoff,arm=arm,training_rows=len(train),prediction_rows=len(test),selected=int(actual.selected.sum()),normal_equation_max_residual=residual,scalar_coefficient=float(coef[-1])))
    assert len(models)==len(records)==manifest['actual_fit_calls_completed']==manifest['actual_fit_calls_attempted']==12 and manifest['prediction_rows']==644056
    order=[(scope,cutoff,arm)for scope in SCOPES for cutoff in CUTOFFS for arm in ARMS]
    for filename,counter in [('fit_attempts.jsonl','attempt'),('fit_completed.jsonl','completed')]:
        events=[json.loads(line)for line in(root/filename).read_text().splitlines()if line]
        assert [(v['scope'],v['cutoff'],v['arm'])for v in events]==order and [v[counter]for v in events]==list(range(1,13))
    for key,mask in [('predictions_main',pred.scope.eq('main')),('predictions_holdout',pred.scope.ne('main'))]:
        saved=table(manifest[key]);expected=pred.loc[mask];assert len(saved)==322028 and expected.groupby('arm').size().eq(161014).all()
        assert set(saved.columns)==set(expected.columns)
        for col in saved:
            if col in ('sequence_index','u_index','score','selected','history_ready20','external_missing'):compare(pd.to_numeric(saved[col]),expected[col],'split_'+col,atol=1e-12 if col=='score'else 0,rtol=0)
            else:assert saved[col].tolist()==expected[col].tolist(),(key,col)
    held,daily,linked=held_diagnostics(pred,labels,'2026-10-16');compare_dict(json.loads(bound(manifest['held_diagnostic'])),held,'held_report')
    saved=table(manifest['held_daily']);assert saved[['u_date','scope']].equals(daily[['u_date','scope']]);compare(pd.to_numeric(saved.delta_R),daily.delta_R,'held_daily_R');compare(pd.to_numeric(saved.mse_difference),daily.mse_difference,'held_daily_MSE');assert np.array_equal(pd.to_numeric(saved.known_events),daily.known_events)
    saved=table(manifest['held_linkage']);assert saved.event_id.tolist()==linked.event_id.tolist()and saved.arm.tolist()==linked.arm.tolist()and saved.scope.tolist()==linked.scope.tolist()
    assert saved.diagnostic_known_domain.eq('True').tolist()==linked.diagnostic_known_domain.tolist();compare(pd.to_numeric(saved.diagnostic_outcome_R.replace('',np.nan)),linked.diagnostic_outcome_R,'held_unknown_null')
    metrics=json.loads((root/'opportunity_metrics.json').read_text());g=pred.merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one');g['year']=g.u_date.str[:4]
    for role,keys in [('overall',['scope','arm']),('annual',['scope','arm','year']),('family_year',['scope','arm','family_id','year'])]:
        expected=[]
        for names_,v in g.groupby(keys,sort=True):
            if not isinstance(names_,tuple):names_=(names_,)
            known=v.label_state.eq('closed_complete_bar_model')&v.history_ready20.eq(1)&v.label_known_date.ne('')&v.label_known_date.le('2026-10-16')&np.isfinite(v.net_R_stress);selected=v.selected.eq(1)
            expected.append(dict(zip(keys,names_),rows=len(v),selected=int(selected.sum()),external_missing=int(v.external_missing.sum()),closed_action_ready_known=int(known.sum()),mse_closed_known=float(np.mean((v.loc[known,'score']-v.loc[known,'net_R_stress'])**2))if known.any()else None,selected_nonclosed=int((selected&~v.label_state.eq('closed_complete_bar_model')).sum()),label_states=v.label_state.value_counts().to_dict()))
        compare_dict(metrics[role],expected,'opportunity_'+role)
    signal,states=main_signal_diagnostics(labels,pred,'2026-10-16')
    return pred,held,signal,states,dict(cash_eligible=True,models_checked=12,predictions_checked=644056,models=models,six_cell_support=support,head_dimension=54,refits=0)

def cash_gate(points,held,any_stale,main_unknown,wealth_positive):
    assert set(held['groups'])=={'holdout_0','holdout_1'}
    vals=list(points.values());p=points[('primary_2020','stress')]
    returns=p['return_percentage_point_difference']>0 and all(v['return_percentage_point_difference']>=0 for k,v in points.items()if k!=('primary_2020','stress'))
    dds=[v['drawdown_percentage_point_difference']for v in vals];known=all(x is not None and np.isfinite(x)for x in dds);dd=all(x>=0 for x in dds if x is not None and np.isfinite(x))
    low=p['ci95_low'];ci=low is not None and np.isfinite(low)and low>0
    own=all(v['active_total_return_pct']is not None and np.isfinite(v['active_total_return_pct'])and v['active_total_return_pct']>0 for v in vals)
    hn=all(g['nominal_pass']is True for g in held['groups'].values());hu=any(g.get('unknown_differential_selected_events',0)>0 or g['status']=='unknown'for g in held['groups'].values())
    nominal=bool(returns and known and dd and ci and own and wealth_positive)
    if all(v['identification']=='all_empty_unidentified'for v in vals):status='all_empty_unidentified'
    elif not(returns and dd and ci and hn and own and wealth_positive):status='unsupported'
    elif not known:status='unknown_empty_reference_DD'
    elif any_stale:status='unknown_historical_stale'
    elif hu:status='unknown_differential_held_outcome'
    else:status='supported_research_model_only'
    return dict(status=status,cash_nominal_pass=nominal,held_known_nominal_pass=bool(hn),NFC_own_returns_positive_in_all_four=bool(own),actual_wealth_positive=bool(wealth_positive),nominal_pass=bool(nominal and hn),financial_unknown=bool(any_stale or not known),signal_unknown_main=bool(main_unknown),held_signal_unknown=bool(hu),signal_label_uncertainty_is_not_cash_exposure=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False,independent_actual_review_required=True,no_automatic_promotion=True)

def _signal(cash_dir, held, signal_report, signal_states):
    _require(signal_report is not None and signal_states is not None, "independently reviewed main signal report and states required")
    saved = json.loads((cash_dir / "signal_identification.json").read_text())
    _require(saved["main"] == signal_report, "independent main signal report differs")
    _nested(saved["held_groups"], held["groups"], "independent held groups")
    _nested(json.loads(_bound(saved["held_binding"])), held, "held bound independent input")
    _fields(saved, dict(label_unknown_not_a_cash_gate=True), "signal cash separation")
    _fields(signal_report, dict(main_prediction_rows_per_arm=161014, full_mother_rows=399252,
                               unfilled_signal_label_uncertainty_is_not_cash_exposure=True), "main signal scope")
    _require(sum(signal_report["full_mother_label_states"].values()) == 399252, "full mother label state count")
    _require(0 <= signal_report["unknown_differential_selected_events"] <= 161014, "unknown main count")
    actual = _read(cash_dir, "main_signal_states")
    expected = pd.DataFrame(signal_states).copy()
    _require(set(actual.columns) == set(expected.columns), "signal state columns")
    for frame in (actual, expected):
        frame["year"] = frame.year.astype(str)
        _require(not frame.duplicated(["year", "label_state"]).any(), "duplicate signal state identity")
    actual = actual.sort_values(["year", "label_state"]).reset_index(drop=True)
    expected = expected.sort_values(["year", "label_state"]).reset_index(drop=True)
    _require(actual[["year", "label_state"]].fillna("").values.tolist() == expected[["year", "label_state"]].fillna("").values.tolist(), "signal state identity")
    for col in set(actual.columns) - {"year", "label_state"}:
        compare(actual[col], expected[col], "independent main states " + col)
    compare(actual.rows.sum(), 161014, "main state total")
    return signal_report["unknown_differential_selected_events"] > 0


def check_account_summary_table(row,summary):
    for field,value in summary.items():
        if not isinstance(value,(dict,list)):_fields(row,{field:value},'account summary')

def review_cash_diagnostics(cash_dir, summaries, protocol, held, bootstrap_indices, *, signal_report=None, signal_states=None):
    """Read saved8 cash only; parent supplies independently reviewed held/main.

    summaries keys: NARROW_{CONTROL|NFC}_{primary_2020|cold_2023}_{base|stress}.
    signal_report and signal_states are required keyword inputs from the parent
    model checker. No author imports, labels/predictions, SQL, fit or cash replay.
    """
    cash_dir = Path(cash_dir)
    _require(protocol['stage']==110 and protocol['line_id']==LINE.name,'110 scope')
    c=protocol['cash'];_fields(c,dict(initial_equity=1000000,accounts_max=8,initial_stop_N=.25,single_family_risk=.0025,total_planned_risk=.02,buffered_margin_cap=.25,margin_buffer=1.1),'110 finance')
    finance=dict(initial=c['initial_equity'],arms=c['arms'],costs=c['costs'],windows=[dict(id=k,start=v[0],end=v[1])for k,v in c['windows'].items()],bootstrap=dict(repetitions=2000,block_length=252,seed=20261018))
    _fields(finance["bootstrap"], dict(repetitions=2000, block_length=252, seed=20261018), "110 bootstrap")
    _require(finance["arms"] == list(ARMS) and finance["costs"] == list(COSTS), "fixed two arms/costs")
    _require([w["id"] for w in finance["windows"]] == list(WINDOWS), "fixed two windows")
    keys = [(a, w, c) for a in ARMS for w in WINDOWS for c in COSTS]
    name = lambda a, w, c: f"NARROW_{a}_{w}_{c}"
    names = {name(*k) for k in keys}
    _require(set(summaries) == names, "exact8 independent summaries")
    reports = json.loads((cash_dir / "diagnostics.json").read_text())
    _require(set(reports) == names, "exact8 diagnostics")
    family = _read(cash_dir, "family_year_including_zero")
    families = sorted(family.family_id.unique())
    _require(len(families) == 95 and set(zip(family.arm, family.window, family.cost)) == set(keys), "8 x all95 family universe")
    annual = _read(cash_dir, "annual_slices")
    _require(set(annual.account) == names and not annual.duplicated(["account", "year"]).any(), "unique8 account annual tables")
    summary_table = _read(cash_dir, "account_summaries")
    _require(len(summary_table) == 8 and set(zip(summary_table.arm, summary_table.window, summary_table.cost)) == set(keys), "eight summary identities")
    daily, logs, counts, family_expected = {}, {}, {}, []
    for key in keys:
        account = name(*key)
        selected = family.loc[family.arm.eq(key[0]) & family.window.eq(key[1]) & family.cost.eq(key[2])]
        daily[key], logs[key], counts[account], fy = _account(cash_dir / account, summaries[account], reports[account], selected, families)
        family_expected.append(fy.assign(arm=key[0], window=key[1], cost=key[2]))
        _daily_summary(daily[key], summaries[account], finance["initial"])
        rows = annual.loc[annual.account.eq(account)].sort_values("year")
        _require(len(rows) == len(reports[account]["annual_slices"]), "annual row count")
        for actual, expected in zip(rows.to_dict("records"), reports[account]["annual_slices"]):
            _fields(actual, expected, "saved annual table")
        row = summary_table.loc[summary_table.arm.eq(key[0]) & summary_table.window.eq(key[1]) & summary_table.cost.eq(key[2])].iloc[0].to_dict()
        check_account_summary_table(row,summaries[account])
    totals = _read(cash_dir, "family_total_including_zero")
    group_cols = ["arm", "window", "cost", "family_id"]
    measures = ["net_equity_contribution", "fee", "slippage", "fill_count", "filled_qty"]
    expected = pd.concat(family_expected).groupby(group_cols)[measures].sum().sort_index()
    _require(not totals.duplicated(group_cols).any(), "duplicate family total")
    actual = totals.set_index(group_cols).sort_index()
    _require(actual.index.tolist() == expected.index.tolist(), "8 x all95 family total grid")
    for col in measures:
        compare(actual[col], expected[col], "independent family total " + col)
    comparisons = _read(cash_dir, "comparisons")
    distributions = _read(cash_dir, "bootstrap_distributions")
    expected_columns = {w + "_" + c + "_NFC_minus_CONTROL" for w in WINDOWS for c in COSTS}
    _require(len(comparisons) == 4 and not comparisons.duplicated(["window", "cost"]).any(), "four unique comparisons")
    _require(set(comparisons.contrast) == {"NFC_minus_CONTROL"}, "single frozen contrast")
    _require(len(distributions) == 2000 and set(distributions.columns) == expected_columns, "2000 x 4 distributions")
    _require(set(bootstrap_indices) == set(WINDOWS), "two prebound old indices")
    points = {}
    for window in WINDOWS:
        dates = daily[("NFC", window, "stress")].date.tolist()
        _require(all(daily[k].date.tolist() == dates for k in keys if k[1] == window), "common source calendar")
        schedule = next(w for w in finance["windows"] if w["id"] == window)
        _require(dates[0] >= schedule["start"] and dates[-1] == schedule["end"], "calendar window bounds")
        index = np.load(io.BytesIO(_bound(bootstrap_indices[window])), allow_pickle=False)
        _require(index.shape == (2000, len(dates)) and index.dtype.kind in "iu" and index.min() >= 0 and index.max() < len(dates), "bound index shape/type/range")
        for cost in COSTS:
            a, b = ("NFC", window, cost), ("CONTROL", window, cost)
            active, control = summaries[name(*a)], summaries[name(*b)]
            empty = control["fills"] == 0
            point = dict(active_total_return_pct=active["total_return_pct"], reference_total_return_pct=control["total_return_pct"],
                         return_percentage_point_difference=active["total_return_pct"] - control["total_return_pct"],
                         drawdown_percentage_point_difference=None if empty else active["max_drawdown_pct"] - control["max_drawdown_pct"],
                         dd_comparison_state="NA_empty_reference" if empty else "active_reference",
                         identification="all_empty_unidentified" if active["fills"] == control["fills"] == 0 else "observed_cash_comparison")
            if logs[a] is None or logs[b] is None:
                values = np.full(2000, np.nan)
                point.update(status="survival_failure_no_log_repair", ci95_low=None, ci95_high=None,
                             mean_daily_log_difference=None, cumulative_log_difference=None)
            else:
                difference = logs[a] - logs[b]
                values = difference[index].mean(axis=1)
                low, high = np.quantile(values, [.025, .975])
                point.update(status="valid", ci95_low=float(low), ci95_high=float(high),
                             mean_daily_log_difference=float(difference.mean()), cumulative_log_difference=float(difference.sum()))
            row = comparisons.loc[comparisons.window.eq(window) & comparisons.cost.eq(cost)]
            _require(len(row) == 1, "expected comparison")
            _fields(row.iloc[0].to_dict(), point, window + "." + cost)
            compare(distributions[window + "_" + cost + "_NFC_minus_CONTROL"], values, "paired bootstrap", atol=1e-12)
            points[(window, cost)] = point
    main_unknown = _signal(cash_dir, held, signal_report, signal_states)
    any_stale = any(r["stale_days"] > 0 for r in counts.values())
    gate = cash_gate(points, held, any_stale, main_unknown, all(v is not None for v in logs.values()))
    _fields(json.loads((cash_dir / "continuation_gate.json").read_text()), dict(gate, any_historical_stale=any_stale), "continuation gate")
    disclosure = json.loads((cash_dir / "budget_and_tick_disclosure.json").read_text())
    _fields(disclosure, dict(policy="NARROW", continuous_boundary_not_necessarily_tick_order=True, no_gap_loss_cap=True,
                            normal_open_close_mark_is_frozen_research_valuation=True, zero_price_scenarios_are_not_universal_loss_bounds=True,
                            bootstrap_indices_regenerated=False, normal_open_not_automatically_financial_unknown=True), "financial disclosures")
    _require(disclosure["bootstrap_indices"] == bootstrap_indices, "disclosed old indices identity")
    _require(0 <= disclosure["stop_distance_below_tick"] <= disclosure["known_tick_rows"] <= disclosure["ready_rows"], "tick counts range")
    return dict(accounts_checked=8, all_families=95, comparisons_checked=4, repetitions=2000, block_length=252,
                seed=20261018, bootstrap_indices_regenerated=False, account_diagnostics=counts, continuation_gate=gate,
                independently_supplied_main_signal_checked=True, independently_supplied_held_checked=True,
                unknown_payoff_bound_established=False, tick_counts_independently_rederived=False)

WINDOWS=("primary_2020","cold_2023");COSTS=("base","stress")

def extras(directory,signals):
    budgets=csv(directory/'reservations.csv.gz');reject=csv(directory/'rejections.csv.gz')
    if len(budgets):
        expected=budgets.loc[pd.to_numeric(budgets.D_qty).eq(0)].set_index('budget_id').sort_index();saved=reject.set_index('budget_id').sort_index().reindex(columns=expected.columns,fill_value='')
        assert expected.equals(saved),'rejections altered or omitted'
    else:assert len(reject)==0
    fills=csv(directory/'fills.csv.gz');numeric(fills,['reference_price','qty','fee','realized_gross'])
    closed=csv(directory/'closed.csv.gz');opened=csv(directory/'open.csv.gz');roots=pd.concat([closed,opened],ignore_index=True).set_index('root_id')
    if len(roots):
        compare(pd.to_numeric(roots.SL0),pd.to_numeric(roots.entry_reference)-.25*np.array([float(signals.loc[e,'N_u'])for e in roots.event_id]),'all_roots_initial_stop')
    diagnostics=json.loads((directory.parent/'diagnostics.json').read_text())[directory.name];expected=[]
    for r in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].itertuples():
        root=roots.loc[r.root_id];loss=(float(root.entry_reference)-r.reference_price)/(.25*float(signals.loc[r.event_id,'N_u']))
        expected.append(dict(event_id=r.event_id,date=r.date,gross_loss_R=loss,qty=r.qty,realized_gross=r.realized_gross,exit_fee=r.fee))
    assert len(diagnostics['gap_stop_fills'])==len(expected)
    for a,b in zip(diagnostics['gap_stop_fills'],expected):
        assert a['event_id']==b['event_id']and a['date']==b['date']
        for k in ('gross_loss_R','qty','realized_gross','exit_fee'):compare(a[k],b[k],'gap_'+k)
    assert diagnostics['gap_stop_exceeds_1R']==sum(x['gross_loss_R']>1 for x in expected)
    return dict(rejections_preserved=len(reject),all_root_initial_stops_checked=len(roots),gap_stops=len(expected),gap_stops_gross_over1R=sum(x['gross_loss_R']>1 for x in expected))


def same(a,b):return all(a.get(k)==b.get(k)for k in ('path','sha256'))and a.get('bytes',a.get('size'))==b.get('bytes',b.get('size'))

def closure(args):
    manifests={};bindings={}
    for role,schema,stage in [('projection','stage111_member_category_projection_v1','projection'),('fit','stage112_member_category_fit_v1','fit'),('cash','stage113_member_category_cash_v1','cash')]:
        path=getattr(args,role+'_manifest')
        if not path:
            assert role=='cash';continue
        mb=bind(path);assert mb['sha256']==getattr(args,role+'_sha256'),(role,'manifestSHA')
        m=json.loads(bound(mb));assert m['schema']==schema and m['mode']=='actual'and m['protocol']['sha256']==PROTOCOL_SHA
        if role=='fit':assert m['status']in('completed','unsupported_scalar_support')
        else:assert m['status']=='completed'
        assert m['terminal']['sha256']==getattr(args,role+'_terminal_sha256');terminal=json.loads(bound(m['terminal']))
        assert terminal['status']==m['status']and terminal['exit_code']==0
        expected={'projection':dict(completed_projection_rows=399252,native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,source_dates=3588),'fit':dict(actual_fit_calls_attempted=12 if m['status']=='completed'else 0,actual_fit_calls_completed=12 if m['status']=='completed'else 0,native_source_queries=0,cash_replays=0,new_labels=0),'cash':dict(cash_accounts_started=8,new_cash_accounts=8,native_source_queries=1,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,old_baseline_replays=0)}[role]
        for key,value in expected.items():assert terminal[key]==value,(role,'terminal',key)
        auth=json.loads(bound(m['authorization']));required=dict(schema='stage110_exact_root_authorization_v1',authorized_by='root',stage=stage,exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(Path(mb['path']).parent))
        for key,value in required.items():assert auth[key]==value,(role,'authorization',key)
        assert auth['input_bindings']==m['input_bindings']and sorted(auth['source_bundle'],key=lambda b:b['path'])==sorted(m['source_bundle'],key=lambda b:b['path'])
        for b in m['source_bundle']:bound(b)
        if role=='projection':artifacts=[m[key]for key in('projection','source_day_audit','product_scope_audit')]
        elif role=='fit'and m['status']=='unsupported_scalar_support':artifacts=[m['support_report']]
        else:artifacts=list(m['artifacts'].values())if isinstance(m['artifacts'],dict)else m['artifacts']
        seen=set()
        for b in artifacts:
            assert b['path']not in seen and str(Path(b['path']).resolve()).startswith(str(Path(mb['path']).parent)+'/');seen.add(b['path']);bound(b)
        manifests[role]=m;bindings[role]=dict(manifest=mb,terminal=m['terminal'],authorization=m['authorization'],source_bundle=m['source_bundle'],artifacts_verified=len(seen))
    source=manifests['projection'];fit=manifests['fit'];protocol=json.loads(bound(source['protocol']))
    assert protocol['stage']==110 and protocol['line_id']==LINE.name and source['protocol']==fit['protocol']
    assert same(fit['input_bindings']['projection_manifest'],bindings['projection']['manifest'])and same(fit['input_bindings']['projection_terminal'],source['terminal'])and same(fit['input_bindings']['projection'],source['projection'])
    for key in ('source_acceptance','narrow_labels','narrow_manifest','implementation_clarifications'):assert same(fit['input_bindings'][key],source['input_bindings'][key])
    assert source['input_bindings']['implementation_clarifications']['sha256']==CLARIFICATIONS_SHA;bound(source['input_bindings']['implementation_clarifications'])
    assert fit['input_bindings']['common_npz']['sha256']=='e3174cf1d2067611e6a2538d25aafee17772adcd1889a68408d727fdc4fc1fd3'and fit['input_bindings']['common_identity']['sha256']=='fa7954b8b3c5e7f0b61688e470f18c23b827490da22aa018dedc39c1b5be1f84'
    preflight=json.loads((LINE/'outputs/stage114_member_category_review/code_preflight.json').read_text());freeze=json.loads(bound(preflight['bindings']['113_freeze']))
    for key in ('narrow_labels','narrow_manifest'):assert same(source['input_bindings'][key],freeze['fixed_market_inputs'][key])
    if 'cash'in manifests:
        cash=manifests['cash'];assert fit['cash_eligible']is True and same(cash['input_bindings']['fit_manifest'],bindings['fit']['manifest'])
        for key in ('predictions_main','held_diagnostic'):assert same(cash['input_bindings'][key],fit[key])
        for key,b in freeze['fixed_market_inputs'].items():assert same(cash['input_bindings'][key],b)
        assert cash['bootstrap_indices']==freeze['bootstrap_indices']and cash['protocol']==source['protocol']
    else:
        assert fit['status']=='unsupported_scalar_support'and fit['cash_eligible']is False
        assert not (LINE/'outputs/stage113_member_category_cash/cash/manifest.json').exists()and not list((LINE/'outputs/stage113_member_category_cash/cash').glob('NARROW_*'))
    return manifests,bindings,protocol,freeze

def safe(value):
    if isinstance(value,dict):return{str(k):safe(v)for k,v in value.items()}
    if isinstance(value,(tuple,list)):return[safe(v)for v in value]
    if hasattr(value,'item'):return value.item()
    return value

def write(path,value):
    with path.open('x')as f:json.dump(safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def progress(out,name,value):
    write(out/(name+'.json'),value);print(json.dumps(dict(phase=name,completed=True)),flush=True)

def review(args):
    global np,pd,compare,csv,numeric,_require,_fields,_read,_log,_account,_daily_summary,_bound,_nested
    for key in('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);clock=time.monotonic();started=datetime.now(timezone.utc).isoformat();status='failed';error=None
    own=[bind(Path(__file__)),bind(Path(__file__).with_name('test_stage114_member_category_review.py'))]
    helpers=[bind(LINE/'tools'/name)for name in AUDIT_HELPERS];sources=own+helpers
    write(out/'actual_started.json',dict(started_at=started,process_id=os.getpid(),review_startups=1,not_strategy_run=True,sources=sources,expected_inputs=vars(args),new_SQL=0))
    snapshot=out/'checker_snapshot';snapshot.mkdir()
    for b in sources:(snapshot/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
    try:
        np,pd,cash,diag,review_native,load_labels,weights,stats,table,convert,compare_dict=audit_helpers()
        compare,csv,numeric=cash.compare,cash.csv,cash.numeric
        for key in('_require','_fields','_read','_log','_account','_daily_summary','_bound','_nested'):globals()[key]=getattr(diag,key)
        manifests,bindings,protocol,fixed=closure(args);progress(out,'final_input_closure',bindings)
        labels=load_labels(manifests['projection']['input_bindings']['narrow_labels'])
        scalar,observed,source_report=review_source(manifests['projection'],labels,np,pd,compare,table)
        terminal=json.loads(bound(manifests['projection']['terminal']));assert terminal['source_raw_files_read']==source_report['eligible_raw_files_read']
        progress(out,'all_source_scopes_and399252_projection',source_report)
        predictions,held,signal,states,models=review_models(manifests['fit'],labels,scalar,observed,compare,table,weights,stats,compare_dict)
        progress(out,'all12_models_and644056_predictions',models);accounts=[];diagnostics=None
        if not models['cash_eligible']:
            assert 'cash'not in manifests;progress(out,'whole_candidate_support_stop',dict(zero_fits=True,zero_cash=True,full_projection_preserved=True))
        else:
            assert 'cash'in manifests
            cashmanifest=manifests['cash'];directory=Path(bindings['cash']['manifest']['path']).parent
            bridge=json.loads(bound(fixed['fixed_market_inputs']['market_protocol']));dates=np.load(io.BytesIO(bound(bridge['calendar'])),allow_pickle=False)
            calendar=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8]for v in dates]if dates.dtype.kind in'iu'else dates.astype('datetime64[D]').astype(str).tolist()
            assert len(calendar)==5587 and calendar==sorted(set(calendar))and np.array_equal(labels.u_index,labels.u_date.map({d:i for i,d in enumerate(calendar)}))
            economics=json.loads(bound(bridge['economic_projection']))['instruments'];summaries={}
            labels['planned_execution_date']=[calendar[int(v)+1]if int(v)+1<len(calendar)else''for v in labels.u_index]
            for arm in ARMS:
                p=predictions.loc[predictions.scope.eq('main')&predictions.arm.eq(arm),['event_id','score']]
                signals=labels.merge(p,on='event_id',how='left',validate='one_to_one',sort=False)
                signals['potential']=(signals.label_history_ready20.eq(1)&np.isfinite(signals.score)&signals.score.gt(0)).astype(int);signals=signals.set_index('event_id',drop=False)
                for window,span in protocol['cash']['windows'].items():
                    schedule=dict(id=window,start=span[0],end=span[1])
                    for cost in COSTS:
                        name=f'NARROW_{arm}_{window}_{cost}';checked=cash.review_account(directory/name,cost,schedule,protocol,signals,economics,calendar,.25)
                        checked['additional_checks']=extras(directory/name,signals);accounts.append(checked);summaries[name]=checked['summary']
            assert len(accounts)==8;progress(out,'all8_cash_ledgers_budgets_fees_slippage',accounts)
            native=next(b for b in cashmanifest['artifacts']if Path(b['path']).name=='finite_native_cases.json.gz');progress(out,'finite_native_cash_cases',review_native(native,'cash'))
            diagnostics=review_cash_diagnostics(directory,summaries,protocol,held,fixed['bootstrap_indices'],signal_report=signal,signal_states=states)
            disclosure=json.loads((directory/'budget_and_tick_disclosure.json').read_text());ready=labels.label_history_ready20.eq(1)
            assert disclosure['ready_rows']==int(ready.sum())and disclosure['known_tick_rows']==int((ready&labels.tick_size.gt(0)).sum())and disclosure['stop_distance_below_tick']==int((ready&labels.R0_points.lt(labels.tick_size)).sum())and disclosure['reservation_records']==sum(a['budgets_checked']['rows']for a in accounts)
            progress(out,'all4_CI_held_gates_unknown_attribution',dict(diagnostics=diagnostics,signal=signal))
        assert sources==[bind(Path(b['path']))for b in sources]
        write(out/'review_receipt.json',dict(schema='stage114_member_category_independent_review_v1',completed=True,C=0,I=0,M=0,review_startups=1,full_review_completions=1,input_closure=bindings,checker_sources=sources,source_review=source_report,model_review=models,cash_accounts=accounts,diagnostics=diagnostics,main_signal_identification=signal,numeric_max_errors=cash.ERRORS,execution=dict(new_SQL=0,fit=0,research_cash=0,whole_native_strategy_replay=0,old_model_recheck=0,old_suite=0,whole_DB_H5_hash=0,new_network_requests=0),research_arithmetic_accepted=True,fixed_package_supported=diagnostics is not None and diagnostics['continuation_gate']['status']=='supported_research_model_only',first_publication_PIT_established=False,narrow_stop_universal_loss_bound=False,goal_complete=False,production_qualified=False))
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';write(out/'failure.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        write(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,error=error,exit_code=0 if status=='completed'else 1,review_startups=1,full_review_completions=int(status=='completed'),research_runs=0,new_SQL=0))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for role in('projection','fit','cash'):
        for key in('manifest','sha256','terminal-sha256'):p.add_argument('--'+role+'-'+key,required=role!='cash')
    p.add_argument('--output',required=True);review(p.parse_args())
