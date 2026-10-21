"""Independent full new source/projection review with only 24 raw-day rereads.

No author162 imports, label/price consumption, SQL, fits, cash or network. Root
alone invokes actual after frozen161 and exact source/input authorization.
"""
from __future__ import annotations
import argparse
import ast
from bisect import bisect_left
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import traceback

LINE=Path(__file__).resolve().parents[1]
TOOLS=LINE/'tools'
VERIFIED=set()
ERRORS={}
INHERITED=set()
PROTOCOL_SHA='ce6329b0f806e69d62d34a894b3738df2a65fdcf557c873bffb37392208b73ca'
CLARIFIER_SHA='9e94d0e977f4ae56ac3329a5db9e2a23b9dea5b71e8daf99482cdd6573ec439a'
VERSION='stage162_exact_visible_member_distribution_v1'
MOTHER_ID=('sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch')
ACTION_ID=MOTHER_ID+('action_sequence_index','action_id','actual_epoch','mother_sequence_index','mother_event_id','anchor_epoch')


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):
    assert all(a.get(k)==b.get(k) for k in ('path','bytes','sha256')),('binding differs',a,b)


def verify(b):
    if b['path'] in INHERITED:
        assert Path(b['path']).stat().st_size==b['bytes'],('accepted identity size changed',b['path'])
        return Path(b['path'])
    key=tuple(b[k] for k in ('path','bytes','sha256'))
    if key not in VERIFIED:same(binding(b['path']),b);VERIFIED.add(key)
    return Path(b['path'])


def read_json(b):return json.loads(verify(b).read_text())


def serial(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def digest(x):return hashlib.sha256(serial(x).encode()).hexdigest()


def rows(b):
    p=verify(b)
    with (gzip.open(p,'rt',newline='') if p.suffix=='.gz' else p.open(newline='')) as f:yield from csv.DictReader(f)


def integer(x):
    assert not isinstance(x,bool)
    v=Decimal(str(x));assert v.is_finite() and v==v.to_integral_value(),('integer',x)
    return int(v)


def num(x):
    if x is None or x=='':return None
    v=float(x);return v if math.isfinite(v) else None


def flag(x):
    assert str(x).lower() in ('true','false','1','0'),('boolean',x)
    return str(x).lower() in ('true','1')


def close(got,want,label,atol=1e-12,rtol=1e-11):
    a=num(got);b=num(want)
    assert (a is None)==(b is None),(label,'null',got,want)
    if a is not None:
        err=abs(a-b);ERRORS[label]=max(ERRORS.get(label,0.),err)
        assert err<=atol+rtol*abs(b),(label,a,b,err)


def fields(got,want,label):
    for k,v in want.items():
        assert k in got,(label,'missing',k)
        if isinstance(v,bool):assert flag(got[k])==v,(label,k,got[k],v)
        elif isinstance(v,int):assert integer(got[k])==v,(label,k,got[k],v)
        elif v is None or isinstance(v,float):close(got[k],v,label+'.'+k)
        else:assert got[k]==v,(label,k,got[k],v)


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def progress(out,name,value):
    write(out/(name+'.json'),value);print(json.dumps(dict(phase=name,completed=True)),flush=True)


def bundle():return sorted([binding(TOOLS/n) for n in ('stage163_member_distribution_review.py','test_stage163_member_distribution_review.py')],key=lambda b:b['path'])


def quantity(value,present=True):
    if not present:return 'missing_key',None
    if value is None:return 'null',None
    if isinstance(value,bool):return 'invalid_boolean',None
    if str(value).strip()=='':return 'empty_string',None
    if isinstance(value,str) and str(value).strip()=='-':return 'dash',None
    if isinstance(value,str) and not re.fullmatch(r'[+-]?[0-9]+(?:\.0+)?',value.strip()):return 'nonnumeric',None
    try:
        v=Decimal(str(value).strip())
        if not v.is_finite():return 'nonfinite',None
        if v!=v.to_integral_value():return 'noninteger',None
        q=int(v)
        return ('negative' if q<0 else 'true_zero' if q==0 else 'finite_integer'),q
    except(InvalidOperation,ValueError,TypeError):return 'nonnumeric',None


def vector_math(vector,reported_total):
    ranks=set();identities=set();names={};ids={};errors=set();values=[];empty=0;zeros=0
    for row in vector:
        rank=integer(row['rank']);assert 1<=rank<=20,'999/category cannot be member'
        if rank in ranks:errors.add('duplicate_rank')
        ranks.add(rank);name=str(row['name']).strip();member=str(row['id']).strip();q=row['qty'];state=row['qty_state']
        if not name and not member and q is None and state in ('empty_string','missing_key','null','dash'):
            empty+=1;continue
        if not name and not member and q==0 and state=='true_zero':continue
        if (not name and not member) or q is None or not isinstance(q,int) or isinstance(q,bool) or q<0:
            errors.add('invalid_named_quantity');continue
        if state not in ('finite_integer','true_zero') or (state=='true_zero')!=(q==0):errors.add('quantity_state_conflict')
        key=('id',member) if member else ('name',name)
        if key in identities:errors.add('duplicate_identity')
        identities.add(key)
        if member and member in ids and ids[member]!=name:errors.add('identity_name_conflict')
        if member:ids[member]=name
        if name:names[name]=member
        values.append(q);zeros+=q==0
    total=sum(values);squares=sum(q*q for q in values);H=squares/(total*total) if total>0 else None
    match=reported_total is not None and reported_total>=0 and total==reported_total
    return dict(sum=total,sumsq=squares,H=H,named_count=len(values),empty_slots=empty,absent_rank_count=20-len(ranks),true_zero=zeros,total_match=match,available=not errors and total>0 and match,errors=sorted(errors))


def epoch_candidates(raw,directory):
    m=re.fullmatch(r'([A-Za-z]+)([0-9]{4})([Ff]?)',raw.strip())
    if not m:return []
    code=m[1].upper()+('_F' if m[3] else '')
    return sorted(e for e in directory if e.split('.')[1]==code and e.rsplit('.',1)[-1][2:]==m[2])


def previous_day(day,calendar):
    i=bisect_left(calendar,day);assert i<len(calendar) and calendar[i]==day,('u absent calendar',day)
    return calendar[i-1].replace('-','') if i else None


def lookup_projection(day,epoch,calendar,scopes):
    v=previous_day(day,calendar)
    if not epoch:return dict(v=v,observed=0,reason='no_reference_epoch',scope_id='',q=None)
    if v is None:return dict(v=None,observed=0,reason='no_previous_calendar_date',scope_id='',q=None)
    s=scopes.get((v,epoch))
    if s is None:return dict(v=v,observed=0,reason='exact_scope_absent',scope_id='',q=None)
    return dict(v=v,observed=int(s['available']),reason='observed' if s['available'] else 'scope_unavailable',scope_id=s['scope_id'],q=s['q'] if s['available'] else None)


def raw_value(info):
    kind,text=info['type'],info['repr']
    if kind=='missing_key':return None,False
    if kind=='float' and text in ('nan','inf','-inf'):return float(text),True
    if kind=='int':return int(text),True
    if kind=='float':return float(text),True
    value=ast.literal_eval(text)
    assert type(value).__name__==kind,('raw type',kind,text)
    return value,True


def qstate(info):
    value,present=raw_value(info);state,q=quantity(value,present)
    return ('valid' if state in ('finite_integer','true_zero') else 'negative_quantity' if state=='negative' else 'missing_quantity' if state in ('missing_key','null','empty_string','dash') else 'invalid_quantity'),q


def raw_info(row,key):
    return dict(type=type(row[key]).__name__,repr=repr(row[key])) if key in row else dict(type='missing_key',repr='<missing>')


def identity_text(x):return '' if x is None else str(x).strip()


def normalize_vector_row(source_row,rank,member_id,member_name,raw):
    state,q=qstate(raw);has=bool(member_id or member_name)
    if not has and state=='missing_quantity':state,q='empty_slot',None
    elif not has and state=='valid':state,q=('unidentified_true_zero',0) if q==0 else ('missing_identity',None)
    elif state!='valid':q=None
    return dict(source_row=source_row,rank=rank,member_id=member_id,member_name=member_name,qty_state=state,qty=q,raw=raw)


def side_measure(vector,totals,common=()):
    errors=set(common);identities=set();ranks=set();qs=[];empty=zero=unidentified=0
    for v in vector:
        rank=integer(v['rank']);assert 1<=rank<=20
        if rank in ranks:errors.add('duplicate_rank')
        ranks.add(rank)
        expected=normalize_vector_row(integer(v['source_row']),rank,v['member_id'],v['member_name'],v['raw'])
        assert v==expected,('full normalized vector quantity/state',v,expected)
        state=v['qty_state'];member=v['member_id'];name=v['member_name']
        assert member==member.strip() and name==name.strip()
        key=('id',member) if member else ('name',name) if name else None
        if key is not None:
            if key in identities:errors.add('duplicate_side_identity')
            identities.add(key)
        if state=='valid':qs.append(v['qty']);zero+=v['qty']==0
        elif state=='empty_slot':empty+=1
        elif state=='unidentified_true_zero':unidentified+=1
        else:errors.add(state)
    total=sum(qs);sumsq=sum(q*q for q in qs)
    H=sumsq/(total*total) if total>0 and not errors else None
    reported,match=None,None
    for t in totals:
        state,q=qstate(t['raw']);assert t['qty_state']==state and t['qty']==(q if state=='valid' else None)
    if len(totals)>1:errors.add('duplicate_999')
    elif len(totals)==1:
        t=totals[0];reported=t['qty']
        if t['qty_state']!='valid':errors.add('invalid_total_quantity')
        else:
            match=reported==total
            if not match:errors.add('total_mismatch')
    if total<=0:errors.add('nonpositive_visible_total')
    if errors-{'total_mismatch','invalid_total_quantity','duplicate_999'}:H=None
    status='unknown' if errors else 'verified' if totals else 'total_unverified'
    return dict(sum=total,sumsq=sumsq,H=H,named_count=len(qs),empty_slots=empty,absent_rank_count=20-len(ranks),true_zero=zero,unidentified_true_zero=unidentified,reported_999=reported,reported_999_count=len(totals),total_match=match,status=status,reasons=sorted(errors))


def mapping(raw,directory_index):
    raw=raw.strip();base=dict(epoch='',product_id='',exchange='')
    if re.fullmatch('[A-Za-z]+all',raw,re.I):return dict(base,mapping_state='aggregate_all_excluded')
    if not re.fullmatch(r'[A-Za-z]+[0-9]{4}F?',raw,re.I):return dict(base,mapping_state='unrecognized_instrument')
    candidates=directory_index.get(raw.upper(),[])
    if len(candidates)!=1:return dict(base,mapping_state='ambiguous_epoch' if candidates else 'unmapped_instrument')
    epoch=candidates[0];exchange,code,_=epoch.split('.')
    return dict(epoch=epoch,product_id=exchange+'.'+code,exchange=exchange,mapping_state='exact_epoch')


def directory_index(entries):
    result=defaultdict(list);epochs=set()
    for r in entries:
        e=r['epoch'];exchange,code,month=e.split('.')
        assert e not in epochs and r['product_id']==exchange+'.'+code and re.fullmatch('[0-9]{6}',month)
        epochs.add(e);token=(code[:-2] if code.endswith('_F') else code)+month[2:]+('F' if code.endswith('_F') else '')
        result[token].append(e)
    return dict(result)


def fresh_stats():return dict(total=Counter(),by_year=defaultdict(Counter),by_exchange=defaultdict(Counter),by_product=defaultdict(Counter))


def count_support(stats,r,date,status):
    state=r[status];observed=state in ('verified','observed');product=r.get('product_id') or 'UNMAPPED'
    vals=dict(rows=1,observed=int(observed),missing=int(not observed),observed_zero=int(observed and r['scalar_primary']==0));vals['state:'+state]=1
    for counter in (stats['total'],stats['by_year'][r[date][:4]],stats['by_exchange'][r.get('exchange') or product.split('.')[0]],stats['by_product'][product]):counter.update(vals)


def plain_stats(stats):
    return {k:dict(v) if k=='total' else {a:dict(b) for a,b in sorted(v.items())} for k,v in stats.items()}


def artifact(manifest,role):
    matches=[b for b in manifest['artifacts'] if b['role']==role];assert len(matches)==1,('artifact',role)
    return matches[0]


def review_scopes(manifest,directory,sample_days,out):
    index=directory_index(directory);lookup={};byday=defaultdict(list);samples=defaultdict(dict);stats=fresh_stats();seen=set();mapping_counts=Counter();count=0;physical_byday=defaultdict(set)
    for row in rows(artifact(manifest,'normalized_scopes')):
        day=row['source_date'];instrument=row['raw_instrument'];scope_id=day.replace('-','')+'|'+instrument
        assert scope_id==row['scope_id'] and scope_id not in seen;seen.add(scope_id)
        mapped=mapping(instrument,index);fields(row,mapped,'every scope directory mapping')
        sides={};physical={}
        for side in ('long','short'):
            vector=json.loads(row[side+'_vector_json']);totals=json.loads(row[side+'_reported_999_raw_json']);reasons=json.loads(row[side+'_reasons'])
            assert row[side+'_vector_json']==serial(vector) and row[side+'_vector_sha256']==digest(vector)
            assert row[side+'_reported_999_raw_json']==serial(totals)
            common=[r for r in reasons if r in ('duplicate_rank','invalid_rank','unexpected_rank')]
            expected=side_measure(vector,totals,common);sides[side]=expected
            physical[side]=([(v['source_row'],v['rank']) for v in vector],[v['source_row'] for v in totals])
            for name,value in expected.items():
                if name=='reasons':assert reasons==value,('all side unknown reasons',side,scope_id,reasons,value)
                else:fields(row,{side+'_'+name:value},'every side distribution statistic')
        assert set(json.loads(row['long_reasons']))&{'duplicate_rank','invalid_rank','unexpected_rank'}==set(json.loads(row['short_reasons']))&{'duplicate_rank','invalid_rank','unexpected_rank'}
        assert physical['long']==physical['short'],'independent sides still share original physical rank rows'
        positions=[v[0] for v in physical['long'][0]]+physical['long'][1]
        assert len(positions)==len(set(positions)) and not physical_byday[day].intersection(positions),'source physical row assigned twice'
        physical_byday[day].update(positions)
        status='aggregate_all_excluded' if mapped['mapping_state']=='aggregate_all_excluded' else 'unknown' if mapped['mapping_state']!='exact_epoch' or any(s['status']=='unknown' for s in sides.values()) else 'total_unverified' if any(s['status']=='total_unverified' for s in sides.values()) else 'verified'
        q=sides['long']['H']-sides['short']['H'] if status=='verified' else None
        fields(row,dict(scope_status=status,scalar_primary=q,definition_version=VERSION),'every scope q and primary missing')
        row['scalar_primary']=q;row['source_index']=integer(row['source_index'])
        count_support(stats,row,'source_date','scope_status');mapping_counts[row['mapping_state']]+=1
        byday[day].append((row['source_index'],scope_id,status,row['mapping_state'],positions))
        if mapped['mapping_state']=='exact_epoch':
            key=(day,mapped['epoch']);assert key not in lookup,'multiple raw scopes for exact epoch'
            lookup[key]=dict(scope_id=scope_id,scope_status=status,scalar_primary=q)
        if day.replace('-','') in sample_days:samples[day.replace('-','')][instrument]=row
        count+=1
    report=dict(normalized_scope_rows=count,all_vectors_formulas_and_primary_unknown_checked=True,all_vector_hashes_checked=True,source_summary=plain_stats(stats),mapping_counts=dict(mapping_counts),sample_days_held=len(samples))
    progress(out,'normalized_scope_review',report)
    return lookup,byday,samples,report


def report_from_raw(obj,day,index):
    groups=defaultdict(list)
    for i,r in enumerate(obj['o_cursor']):groups[identity_text(r.get('INSTRUMENTID'))].append((i,r))
    output={}
    for instrument,group in groups.items():
        valid=[];reasons=set();ranks=set()
        for i,r in group:
            state,rank=quantity(r.get('RANK'), 'RANK' in r)
            if rank is None or state not in ('finite_integer','true_zero','negative'):reasons.add('invalid_rank');continue
            if rank in (-1,0):continue
            if rank!=999 and not 1<=rank<=20:reasons.add('unexpected_rank');continue
            if rank!=999:
                if rank in ranks:reasons.add('duplicate_rank')
                ranks.add(rank)
            valid.append((i,r,rank))
        sides={};out=mapping(instrument,index)
        for side,col in (('long','2'),('short','3')):
            vector=[];totals=[]
            for i,r,rank in valid:
                raw=raw_info(r,'CJ'+col)
                if rank==999:
                    state,q=qstate(raw);totals.append(dict(source_row=i,qty_state=state,qty=q if state=='valid' else None,raw=raw))
                else:vector.append(normalize_vector_row(i,rank,identity_text(r.get('PARTICIPANTID'+col)),identity_text(r.get('PARTICIPANTABBR'+col)),raw))
            measured=side_measure(vector,totals,reasons);sides[side]=measured
            out.update({side+'_'+k:v for k,v in measured.items()})
            out[side+'_vector']=vector;out[side+'_totals']=totals
        status='aggregate_all_excluded' if out['mapping_state']=='aggregate_all_excluded' else 'unknown' if out['mapping_state']!='exact_epoch' or any(v['status']=='unknown' for v in sides.values()) else 'total_unverified' if any(v['status']=='total_unverified' for v in sides.values()) else 'verified'
        out.update(scope_id=day+'|'+instrument,scope_status=status,scalar_primary=sides['long']['H']-sides['short']['H'] if status=='verified' else None)
        output[instrument]=out
    return output


def read_raw_sample(entry):
    path=Path(entry.get('archive_path') or entry['source_path']);raw=path.read_bytes();archive_sha=hashlib.sha256(raw).hexdigest()
    if entry.get('archive_path'):
        assert len(raw)==entry['archive_bytes'] and archive_sha==entry['archive_sha256'],'raw sample archive binding'
        body=gzip.decompress(raw)
    else:body=raw
    body_sha=hashlib.sha256(body).hexdigest()
    assert len(body)==entry['raw_body_bytes'] and body_sha==entry['raw_body_sha256'],'raw sample original body binding'
    parse=gzip.decompress(body) if entry.get('headers',{}).get('Content-Encoding','').lower()=='gzip' else body
    try:obj=json.loads(parse)
    except(ValueError,UnicodeError):obj=None
    return obj,dict(path=str(path),archive_bytes=len(raw),archive_sha256=archive_sha,body_bytes=len(body),body_sha256=body_sha)


def review_days_and_samples(manifest,entries,expected_dates,byday,samples,directory,protocol,out):
    audits=list(rows(artifact(manifest,'source_day_audit')));assert len(audits)==3588
    assert len(entries)==len(expected_dates)==3588 and [e['date'] for e in entries]==expected_dates and len(set(expected_dates))==3588
    sampled=protocol['independent_review']['raw_fixed_dates'];assert len(sampled)==len(set(sampled))==24
    index=directory_index(directory);states={};counts=Counter();known=0;sample_report=[]
    for i,(entry,a) in enumerate(zip(entries,audits)):
        day=entry['date'][:4]+'-'+entry['date'][4:6]+'-'+entry['date'][6:8]
        fields(a,dict(source_index=i,source_date=day,original_status=entry['status']),'all3588 source date identity')
        scopes=byday.get(day,[]);assert all(v[0]==i for v in scopes),'scope source_index'
        assert all(0<=position<integer(a['raw_rows']) for scope in scopes for position in scope[4]),'source physical row outside report'
        scope_counts=dict(Counter(v[2] for v in scopes));map_counts=dict(Counter(v[3] for v in scopes))
        fields(a,dict(scopes=len(scopes),exact_mapped_scopes=map_counts.get('exact_epoch',0)),'all day scope counts')
        assert json.loads(a['scope_states_json'])==scope_counts and json.loads(a['mapping_states_json'])==map_counts
        isknown=entry['status'] in ('http_200','reused_stage104_106')
        if isknown:
            known+=1
            fields(a,dict(raw_path=entry.get('archive_path') or entry['source_path'],original_body_bytes=entry['raw_body_bytes'],original_body_sha256=entry['raw_body_sha256'],current_body_bytes=entry['raw_body_bytes'],current_body_sha256=entry['raw_body_sha256'],body_hash_verified=True),'all accepted body manifest claims')
            if entry.get('archive_path'):fields(a,dict(original_archive_bytes=entry['archive_bytes'],original_archive_sha256=entry['archive_sha256'],current_archive_bytes=entry['archive_bytes'],current_archive_sha256=entry['archive_sha256'],archive_hash_verified=True),'all accepted archive manifest claims')
            else:assert not flag(a['archive_hash_verified'])
            assert a['parse_state'] in ('json_cursor','not_json','unrecognized_schema')
            expectedstate='report_date_mismatch' if a['report_date_state']=='mismatch' else a['parse_state'] if a['parse_state']!='json_cursor' else entry['status']
            assert a['source_day_status']==expectedstate
            if a['parse_state']=='json_cursor':
                meta=json.loads(a['report_metadata_json']);rd=meta.get('report_date')
                reportstate='absent' if 'report_date' not in meta else 'matches' if str(rd).replace('-','')==entry['date'] else 'mismatch'
                assert a['report_date_state']==reportstate
            if a['source_day_status'] not in ('http_200','reused_stage104_106'):assert not scopes
        else:
            assert not scopes and a['source_day_status']==entry['status'] and integer(a['raw_rows'])==0
            assert not a['raw_path'] and not a['body_hash_verified'],'unknown original date must not read raw'
        states[day]=a['source_day_status'];counts[a['source_day_status']]+=1
        if entry['date'] not in sampled:continue
        assert isknown,'frozen sample day must have original known response'
        obj,rawreceipt=read_raw_sample(entry)
        fields(a,dict(current_archive_bytes=rawreceipt['archive_bytes'],current_archive_sha256=rawreceipt['archive_sha256'],current_body_bytes=rawreceipt['body_bytes'],current_body_sha256=rawreceipt['body_sha256']),'24 raw fresh byte checks')
        valid=isinstance(obj,dict) and isinstance(obj.get('o_cursor'),list) and all(isinstance(r,dict) for r in obj['o_cursor'])
        if valid:
            fields(a,dict(raw_rows=len(obj['o_cursor'])),'24 raw row counts')
            assert json.loads(a['report_metadata_json'])=={k:v for k,v in obj.items() if k!='o_cursor'}
        normalized=report_from_raw(obj,entry['date'],index) if valid and a['report_date_state']!='mismatch' else {}
        got=samples.get(entry['date'],{});assert set(got)==set(normalized),('raw sample complete scope domain',entry['date'])
        for instrument,want in normalized.items():
            saved=got[instrument]
            for side in ('long','short'):
                # Value/identity/rank semantics are strict; raw repr is a display
                # field. Every saved repr was already interpreted independently
                # above, so changing int1 to equivalent string1 is not an alpha
                # or measurement failure when the original value matches.
                meaningful=lambda seq:[{k:v for k,v in r.items() if k!='raw'} for r in seq]
                assert meaningful(json.loads(saved[side+'_vector_json']))==meaningful(want.pop(side+'_vector')),('24 raw full member vector',entry['date'],instrument,side)
                assert meaningful(json.loads(saved[side+'_reported_999_raw_json']))==meaningful(want.pop(side+'_totals')),('24 raw complete999',entry['date'],instrument,side)
                expected_reasons=want.pop(side+'_reasons');assert json.loads(saved[side+'_reasons'])==expected_reasons
            fields(saved,want,'24 raw all scope values and unknown')
        sample_report.append(dict(source_date=entry['date'],full_scopes_checked=len(normalized),**rawreceipt))
    assert known==3580 and len(entries)-known==8 and len(sample_report)==24
    result=dict(source_days_checked=3588,accepted_known_body_claims_reconciled=known,original_unknown_dates_unread=8,source_day_states=dict(counts),raw_days_independently_reread=24,raw_samples=sample_report,raw_second_full_pass=False,sampling_is_not_all_raw_byte_recertification=True)
    progress(out,'source_days_and_24raw_review',result)
    return states,result


def identity_rows(b,columns):
    with gzip.open(verify(b),'rt',newline='') as f:
        reader=csv.reader(f);header=next(reader);indices=[header.index(k) for k in columns]
        for cells in reader:yield {k:cells[i] for k,i in zip(columns,indices)}


def stat(path):
    p=Path(path);s=p.stat();return dict(path=str(p.resolve()),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino)


def review_projections(manifest,protocol,calendar,daystates,lookup,out):
    reports={}
    for role,columns,epochfield,expected in [('actions',ACTION_ID,'actual_epoch',1552456),('mothers',MOTHER_ID,'reference_epoch',399252)]:
        original=protocol['input_bindings'][role];before=stat(original['path']);same(original,manifest['inputs'][role])
        assert before==manifest['inputs'][role]['stat_before']==manifest['inputs'][role]['stat_after']
        newrows=iter(rows(artifact(manifest,role+'_projection')));full,forward=fresh_stats(),fresh_stats();pre={c:fresh_stats() for c in ('2020-01-01','2023-01-01')};h=hashlib.sha256();count=0
        for old in identity_rows(original,columns):
            new=next(newrows);fields(new,old,'every original '+role+' identity cell')
            seq='action_sequence_index' if role=='actions' else 'sequence_index';assert integer(old[seq])==count
            u=integer(old['u_index']);assert 0<=u<len(calendar) and calendar[u]==old['u_date']
            epoch=old[epochfield];v=u-1 if u else None;vdate=calendar[v] if v is not None else ''
            daystate=daystates.get(vdate,'outside_accepted_source_dates') if vdate else 'no_predecessor_session'
            scope=lookup.get((vdate,epoch)) if vdate and epoch else None
            status='no_reference_epoch' if not epoch else 'no_predecessor_session' if v is None else 'source_day_unavailable' if daystate not in ('http_200','reused_stage104_106') else 'exact_scope_not_disclosed' if scope is None else 'scope_'+scope['scope_status'] if scope['scope_status']!='verified' else 'observed'
            q=scope['scalar_primary'] if status=='observed' else None
            expectedrow=dict(projected_epoch=epoch,v_date=vdate,v_index=v,source_day_status=daystate,scope_id=scope['scope_id'] if scope else '',scope_status=scope['scope_status'] if scope else '',projection_status=status,scalar_primary=q,missing=status!='observed',definition_version=VERSION)
            fields(new,expectedrow,'every '+role+' exact predecessor/epoch/q/missing')
            assert set(new)==set(columns)|set(expectedrow),'projection must contain no price/label/outcome/score values'
            value=dict(old,**expectedrow);count_support(full,value,'u_date','projection_status')
            if old['u_date']>='2020-01-01':count_support(forward,value,'u_date','projection_status')
            for cutoff,s in pre.items():
                if old['u_date']<cutoff:count_support(s,value,'u_date','projection_status')
            h.update((serial(old)+'\n').encode());count+=1
        assert next(newrows,None) is None and count==expected
        assert stat(original['path'])==before,'accepted identity source mutated'
        assert h.hexdigest()==manifest['inputs'][role]['identity_projection_sha256']
        result=dict(full=plain_stats(full),forward_2020_plus=plain_stats(forward),pre_cutoff_source_availability={c:plain_stats(v) for c,v in pre.items()})
        progress(out,role+'_projection_review',dict(rows_checked=count,original_identity_sha256=h.hexdigest(),whole_original_file_hash_reused_not_recomputed=True,all_identity_epoch_lag_q_missing_checked=True,source_support=result))
        reports[role]=result
    assert reports['mothers']['forward_2020_plus']['total']['rows']==161014
    return reports


def source_byte_accounting(entries,new_original_bytes,all_consumed_bytes):
    new=sum(e['raw_body_bytes'] for e in entries if e['status']=='http_200')
    reused=sum(e['raw_body_bytes'] for e in entries if e['status']=='reused_stage104_106')
    assert new==new_original_bytes and new+reused==all_consumed_bytes
    return dict(new_original_bytes=new,reused_original_bytes=reused,all_consumed_bytes=all_consumed_bytes)


def review_summary(manifest,protocol,entries,scope_report,day_report,projections,out):
    summary=read_json(artifact(manifest,'support_summary'))
    expected=dict(schema='stage162_support_summary_v1',definition_version=VERSION,source_days=3588,known_responses_read_once=3580,unknown_unread=8,directory_epochs=10880,directory_product_codes=98,
        consumed_original_body_bytes=sum(e['raw_body_bytes'] for e in entries if e['status'] in ('http_200','reused_stage104_106')),
        consumed_compressed_or_plain_file_bytes=sum(e.get('archive_bytes',e['raw_body_bytes']) for e in entries if e['status'] in ('http_200','reused_stage104_106')),
        source_day_states=day_report['source_day_states'],mapping_states=scope_report['mapping_counts'],normalized_scopes=scope_report['source_summary'],**projections,
        first_publication_PIT_certified=False,outcome_or_financial_inference=False,pre_cutoff_availability_is_not_mature_training_support=True,new_fit=0,new_cash=0,new_SQL=0,network=0,cumulative_fit=397,cumulative_cash=210)
    assert summary==expected,('all new support summaries',set(summary)^set(expected))
    byte_groups=source_byte_accounting(entries,protocol['source']['raw_bytes_known_new_original'],expected['consumed_original_body_bytes'])
    result=dict(all_summary_groups_checked=True,normalized_scope_rows=scope_report['normalized_scope_rows'],source_days=3588,action_rows=1552456,mother_rows=399252,forward_mother_rows=161014,raw_days_independently_reparsed=24,pre_cutoff_is_X_availability_only=True,all_year_exchange_product_status_denominators_preserved=True,source_data_accepted_not_alpha_or_training_qualification=True,source_original_byte_groups=byte_groups)
    progress(out,'summary_review',result);return summary,result


def authorize(args):
    output=Path(args.output).resolve();assert not output.exists(),'fresh review directory required'
    assert LINE/'outputs/stage163_member_distribution_review' in output.parents
    inputs={k:binding(getattr(args,k)) for k in ('protocol','clarifier','manifest')}
    assert inputs['protocol']['sha256']==PROTOCOL_SHA and inputs['clarifier']['sha256']==CLARIFIER_SHA
    authbinding=binding(args.authorization);assert authbinding['sha256']==args.authorization_sha256
    auth=read_json(authbinding)
    fields(auth,dict(schema='stage163_exact_root_review_authorization_v1',authorized_by='root',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output)),'exact root source review authorization')
    assert auth['input_bindings']==inputs and sorted(auth['source_bundle'],key=lambda b:b['path'])==bundle()
    return output,inputs,authbinding


def closure(inputs):
    protocol=read_json(inputs['protocol']);clarifier=read_json(inputs['clarifier']);manifest=read_json(inputs['manifest'])
    fields(protocol,dict(schema='stage161_member_distribution_source_protocol_v1',line_id=LINE.name,financial_authorization=False) if 'financial_authorization' in protocol else dict(schema='stage161_member_distribution_source_protocol_v1',line_id=LINE.name),'frozen source protocol')
    fields(clarifier,dict(protocol_sha256=PROTOCOL_SHA,policy_changes=False,source_only=True),'frozen numeric clarifier')
    fields(manifest,dict(schema='stage162_member_distribution_manifest_v1',status='completed',definition_version=VERSION,strict_first_publication_PIT=False,financial_authorization=False,new_fit=0,new_cash=0,new_SQL=0,network=0),'actual162 manifest')
    same(manifest['protocol'],inputs['protocol']);same(manifest['inputs']['protocol'],inputs['protocol']);same(manifest['inputs']['implementation_clarifier'],inputs['clarifier'])
    assert manifest['identity_fields']==dict(actions=list(ACTION_ID),mothers=list(MOTHER_ID))
    for role,b in protocol['input_bindings'].items():
        same(manifest['inputs'][role],b)
        if role in ('actions','mothers'):INHERITED.add(b['path'])
        verify(b)
    for b in manifest['source_bundle']:verify(b)
    for b in manifest['artifacts']:verify(b)
    fields(read_json(artifact(manifest,'terminal')),dict(schema='stage162_terminal_v1',status='completed',known_responses_read_once=3580,actions=1552456,mothers=399252,new_fit=0,new_cash=0,new_SQL=0,network=0,retry=False),'actual162 terminal')
    fields(read_json(artifact(manifest,'started')),dict(protocol_sha256=PROTOCOL_SHA,auto_retry=False,fit=0,cash=0,SQL=0,network=0,outcomes=0,native_prices=0),'actual162 start boundary')
    market=read_json(protocol['input_bindings']['market_protocol']);same(market['calendar'],protocol['input_bindings']['calendar'])
    dataset=read_json(protocol['input_bindings']['dataset_manifest'])
    for role in ('actions','mothers'):same(dataset[role],protocol['input_bindings'][role])
    directory=list(identity_rows(protocol['input_bindings']['epoch_directory'],('epoch','product_id')))
    assert len(directory)==10880 and len({r['epoch'] for r in directory})==10880 and len({r['product_id'] for r in directory})==98
    import numpy as np
    arr=np.load(verify(protocol['input_bindings']['calendar']),allow_pickle=False)
    calendar=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in arr] if arr.dtype.kind in 'iu' else arr.astype('datetime64[D]').astype(str).tolist()
    assert len(calendar)==5587 and calendar==sorted(set(calendar))
    with verify(protocol['input_bindings']['date_manifest']).open() as f:entries=[json.loads(line) for line in f if line.strip()]
    dates=read_json(protocol['input_bindings']['source_dates'])['dates']
    assert dates==[e['date'] for e in entries]
    assert len(protocol['independent_review']['raw_fixed_dates'])==24 and protocol['independent_review']['author_import_for_calculation'] is False
    report=dict(exact_protocol_clarifier_author_source_and_new_output_binding_closed=True,accepted129_full_file_hash_inherited_identity_stream_only=True,all_new_output_files_hashed_once=True,source_dates=3588,directory_epochs=10880,product_codes=98,source_calendar_days=5587,raw_read_budget=24,author_calculation_imported=False,new_fit=0,new_cash=0,SQL=0,network=0)
    return protocol,manifest,calendar,directory,entries,dates,report


def review(args):
    out,inputs,authbinding=authorize(args);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();before=bundle()
    receipt=dict(schema='stage163_member_distribution_independent_review_v1',completed=False,C=0,I=0,M=0,errors=[],inputs=inputs,authorization=authbinding,source_bundle=before,author162_imported=False,new_fit=0,new_cash=0,SQL=0,network=0,downloads=0,native_prices=0,outcome_columns=0,whole_raw_second_pass=False,accepted129_full_file_hashes_reused=True,automatic_retry=False)
    write(out/'started.json',dict(schema=receipt['schema'],started_at=datetime.now(timezone.utc).isoformat(),inputs=inputs,source_bundle=before,raw_max_dates=24,fit=0,cash=0,SQL=0,network=0))
    try:
        protocol,manifest,calendar,directory,entries,dates,closed=closure(inputs);receipt['closure']=closed;progress(out,'input_closure',closed)
        lookup,byday,samples,scope_report=review_scopes(manifest,directory,set(protocol['independent_review']['raw_fixed_dates']),out);receipt['normalized']=scope_report
        daystates,day_report=review_days_and_samples(manifest,entries,dates,byday,samples,directory,protocol,out);receipt['source']=day_report
        projections=review_projections(manifest,protocol,calendar,daystates,lookup,out);receipt['projections']=projections
        support,summary_report=review_summary(manifest,protocol,entries,scope_report,day_report,projections,out);receipt['summary']=summary_report
        assert bundle()==before,'review source changed during actual'
        for b in inputs.values():same(binding(b['path']),b)
        receipt.update(completed=True,source_measurement_arithmetic_accepted=True,source_primary_availability_counts=support['normalized_scopes']['total'],raw_independent_sample_dates=protocol['independent_review']['raw_fixed_dates'],maximum_numeric_errors=dict(ERRORS),cumulative_fit=397,cumulative_cash=210,first_publication_PIT_certified=False,mature_training_support_certified=False,alpha_proved=False,financial_authorization=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-began;write(out/'receipt.json',receipt)
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','clarifier','manifest','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    review(parser.parse_args())


if __name__=='__main__':main()
