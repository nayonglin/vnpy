"""One independent terminal180 source/journal pass, without network or quantity normalization.

Only explicit root completion notice authorizes running this CLI. All new body
bytes are read once for hash/envelope/date and cheap structural diagnostics.
The nine reused originals inherit accepted174/104 evidence and are not opened.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import traceback

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='a67cf844699c8b2d1b34cc3cd66ac88eaae0c6bedd5621796d886f129cfbb0c5'
PLAN_SHA='06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8'
SOURCE_SHA='2915357de51e456cc38f485510ab3380886d1b81e58643c43fc2f7406a82a62a'
AUTHOR_TEST_SHA='0fe770724f3b467b3016291ac8627c51c7b2b4d882e6ef873cb93bff5ca1a2b7'
ACCEPTED174_SHA='520c9aea78dc30fe08c5fcf0b77dd3b35bbebececbf88e6914f4001f08fa7022'
SUCCESS={'reused_binding_verified','http200_expected_envelope'}
IDENTITY=('sequence_index','date','format','url','action')
LOCATION={'仓库','厂库','交割仓库','地区/仓库','地区/厂库','厂库/地区','仓库/地区'}
QUANTITY_HEADER={'期货','本日数量'}


def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def binding(path,body=None):
    p=Path(path).resolve();body=p.read_bytes() if body is None else body
    return dict(path=str(p),bytes=len(body),sha256=sha(body))
def same(a,b):assert all(a[k]==b[k] for k in ('path','bytes','sha256')),('binding',a,b)
def read_bound(b):
    data=Path(b['path']).read_bytes();same(binding(b['path'],data),b);return data
def write_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def normalized_date(raw):
    s=str(raw).strip();parts=re.fullmatch(r'(\d{4})-?(\d{2})-?(\d{2})',s)
    if not parts:return None
    day=''.join(parts.groups())
    try:datetime.strptime(day,'%Y%m%d')
    except ValueError:return None
    return day


class VisibleReport(HTMLParser):
    """Independent element stack and physical header inventory; no value parsing."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.tables=[];self.table_stack=[];self.intro=[];self.intro_present=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);intro='content_intro' in attrs.get('class','').split();self.intro_present|=intro
        in_intro=intro or any(v[1] for v in self.stack);hidden=tag in ('script','style') or any(v[2] for v in self.stack)
        if tag=='table':
            self.tables.append(dict(in_intro=in_intro,rows=[],row=None,cell=None));self.table_stack.append(len(self.tables)-1)
        elif self.table_stack and tag=='tr':self.tables[self.table_stack[-1]]['row']=[]
        elif self.table_stack and tag in ('td','th'):
            t=self.tables[self.table_stack[-1]]
            if t['row'] is not None:t['cell']=[]
        if tag not in ('br','hr','img','meta','link','input','source','wbr'):self.stack.append((tag,in_intro,hidden))
        if in_intro and not hidden:self.intro.append(' ')
    def handle_data(self,value):
        if any(v[1] for v in self.stack) and not any(v[2] for v in self.stack):self.intro.append(value)
        if self.table_stack and not any(v[2] for v in self.stack):
            t=self.tables[self.table_stack[-1]]
            if t['cell'] is not None:t['cell'].append(value)
    def handle_endtag(self,tag):
        if self.table_stack:
            t=self.tables[self.table_stack[-1]]
            if tag in ('td','th') and t['row'] is not None and t['cell'] is not None:t['row'].append(re.sub(r'\s+','',''.join(t['cell'])));t['cell']=None
            elif tag=='tr' and t['row'] is not None:t['rows'].append(t['row']);t['row']=None
            elif tag=='table':self.table_stack.pop()
        positions=[i for i,v in enumerate(self.stack) if v[0]==tag]
        if positions:del self.stack[positions[-1]:]


def inspect_source(body,fmt,date):
    env=dict(expected_envelope=False,report_date_fields={},report_dates={},date_state='absent',date_evidence_scope='JSON top fields only' if fmt=='json' else 'visible content_intro only')
    structure=dict(format=fmt,inventory_zero_inferred=False)
    try:
        text=body.decode('utf-8-sig')
        if fmt=='json':
            obj=json.loads(text);is_obj=isinstance(obj,dict);cursor=obj.get('o_cursor') if is_obj else None
            env['expected_envelope']=is_obj and isinstance(cursor,list)
            structure.update(top_type=type(obj).__name__,top_keys=sorted(obj) if is_obj else None,cursor_rows=len(cursor) if isinstance(cursor,list) else None,empty_cursor=isinstance(cursor,list) and not cursor,row_keysets=[],nonobject_row_types={},archive_update_date=obj.get('update_date') if is_obj else None,source_o_code=obj.get('o_code') if is_obj else None)
            if is_obj:
                env['report_date_fields']={k:obj[k] for k in ('report_date','o_tradingday') if k in obj}
                env['report_dates']={k:normalized_date(v) for k,v in env['report_date_fields'].items() if v is not None and str(v).strip()}
            if isinstance(cursor,list):
                keysets=Counter(tuple(sorted(row)) for row in cursor if isinstance(row,dict));structure['row_keysets']=[dict(keys=list(k),count=v) for k,v in sorted(keysets.items())]
                structure['nonobject_row_types']=dict(Counter(type(row).__name__ for row in cursor if not isinstance(row,dict)))
        else:
            parser=VisibleReport();parser.feed(text);parser.close();headers=[];table_headers=[]
            for i,t in enumerate(parser.tables):
                candidates=[row for row in t['rows'] if set(row)&QUANTITY_HEADER and set(row)&LOCATION]
                if not t['in_intro'] and candidates:headers.append(dict(table_index=i,header_rows=candidates));table_headers.extend(tuple(v) for v in candidates)
            count=len(headers);intro=''.join(parser.intro);env.update(expected_envelope=parser.intro_present and count>0,table_count=len(parser.tables),intro_present=parser.intro_present,report_header_table_count=count)
            env['report_date_fields']={'intro_text':intro}
            found=re.findall(r'(?<!\d)(\d{4})[-年](\d{2})[-月](\d{2})(?:日)?(?!\d)|(?<!\d)(\d{8})(?!\d)',intro)
            if found:env['report_dates']={'intro':sorted(set(normalized_date(''.join(v[:3]) if v[0] else v[3]) for v in found),key=lambda v:v or '')}
            structure.update(table_count=len(parser.tables),intro_present=parser.intro_present,report_header_table_count=count,header_patterns=[dict(cells=list(k),count=v) for k,v in sorted(Counter(table_headers).items())])
        dates=[d for value in env['report_dates'].values() for d in (value if isinstance(value,list) else [value])]
        env['date_state']='unparseable' if None in dates else 'conflict' if any(d!=date for d in dates) else 'matched' if dates else 'absent'
    except (ValueError,UnicodeError,TypeError) as exc:structure['parse_error']=dict(type=type(exc).__name__,message=str(exc))
    return dict(envelope=env,structure=structure)


def validate_stop_order(rows,status):
    new=[r for r in rows if r['action']=='new_get'];stop=False
    for r in new:
        if stop:assert r['state']=='not_attempted_after_stop' and r['attempt']==0,('request after stop',r['date'])
        elif r['state']!='http200_expected_envelope':stop=True
    if status=='completed':assert all(r['state'] in SUCCESS for r in rows)
    else:assert status=='stopped' and any(r['state'] not in SUCCESS for r in rows)


def actions_from(plan,protocol):
    d=plan['frozen_candidate_domain'];dates=d['dates'];assert dates==sorted(set(dates)) and len(dates)==3018 and dates[0]=='20140519' and dates[-1]=='20261016'
    actions=[]
    for i,day in enumerate(dates):
        assert normalized_date(day)==day
        fmt='json' if day<'20251118' else 'html'
        url=(f'https://www.shfe.com.cn/data/tradedata/future/dailydata/{day}dailystock.dat' if fmt=='json' else f'https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{day}/ZH/all.html')
        actions.append(dict(sequence_index=i,date=day,format=fmt,url=url,action='reuse' if day in plan['reuse_by_date'] else 'new_get'))
    hashes=dict(dates_sha256=sha(canon(dates)),full_action_records_sha256=sha(canon(actions)),new_get_records_sha256=sha(canon([a for a in actions if a['action']=='new_get'])))
    assert {k:v for k,v in d.items() if k!='dates'}==protocol['expected_domain']
    assert all(d[k]==v for k,v in hashes.items()) and dict(Counter(s[:4] for s in dates))==d['by_year']
    assert dict(Counter(a['format'] for a in actions))==d['by_format'] and len(plan['reuse_by_date'])==9
    assert sum(a['action']=='new_get' for a in actions)==3009
    return actions,hashes


def inherited_reuse_evidence(plan,protocol):
    """Small accepted metadata only. Never open any of the nine original bodies."""
    accepted_path=LINE/'outputs/stage174_warehouse_pilot_review/receipt.json';accepted_bytes=accepted_path.read_bytes()
    assert sha(accepted_bytes)==ACCEPTED174_SHA;accepted=json.loads(accepted_bytes)
    assert accepted['completed'] and accepted['source_arithmetic_accepted'] and accepted['errors']==[]
    parsed=json.loads(read_bound(accepted['parsed_manifest']));pilot_binding=plan['input_metadata']['pilot_manifest'];same(parsed['raw_manifest'],pilot_binding)
    pilot=json.loads(read_bound(pilot_binding));pilot_art={Path(b['path']).name:b for b in pilot['artifacts']}
    old_verify_b=plan['input_metadata']['old_source_verification'];old_probe_b=plan['input_metadata']['old_source_receipt']
    old_verify=json.loads(read_bound(old_verify_b));old_probe=json.loads(read_bound(old_probe_b))
    assert old_verify['all_7_raw_sha_bytes_status_valid'] is True
    verified={r['file']:r for r in old_verify['data']};evidence={}
    for date,source in plan['reuse_by_date'].items():
        if date in ('20200102','20230103'):
            same(source['evidence']['verification_receipt'],old_verify_b);same(source['evidence']['probe_receipt'],old_probe_b)
            prior=verified[Path(source['body']['path']).name];assert prior['status']==200 and all(prior[k]==source['body'][k] for k in ('bytes','sha256'))
            found=[v for v in old_probe['probes'] if v.get('kind')=='warehouse' and v.get('exchange')=='SHFE' and v.get('trade_date_requested')==date];assert len(found)==1
            v=found[0];assert v['url']==source['url'] and v['http_status']==200 and v['truncated'] is False
            assert all(v[k]==source['body'][k] for k in ('bytes','sha256'))
            assert v['headers']==source['original_fetch_metadata']['headers'] and v['report_metadata']==source['original_fetch_metadata']['report_metadata']
            evidence[date]='accepted104_probe_and_independent_verification_no_body_reread'
        else:
            name=date+('.dat' if source['format']=='json' else '.html');same(source['body'],pilot_art[name]);same(source['evidence']['source_manifest'],pilot_binding)
            evidence[date]='accepted174_all_seven_raw_and_parser_review_no_body_reread'
    prior_decision=protocol['prior_source_decision'];read_bound(prior_decision)
    return dict(accepted174=binding(accepted_path,accepted_bytes),accepted104_verification=old_verify_b,accepted104_probe=old_probe_b,prior175_decision=prior_decision,reused_dates=evidence,reused_original_body_reads=0)


def group_structures(observations):
    top={};rowgroups={};html={};empty=[];nonobjects=[];partial=[]
    for observation in observations:
        date=observation['date'];s=observation['structure']
        if not observation['body']['complete'] or observation['archive_state']!='http200_expected_envelope':
            partial.append(date);continue
        if observation['format']=='json':
            if s.get('empty_cursor'):empty.append(date)
            if s.get('nonobject_row_types'):nonobjects.append(dict(date=date,types=s['nonobject_row_types']))
            if s.get('top_keys') is not None:
                key=sha(canon(s['top_keys']));g=top.setdefault(key,dict(keys=s['top_keys'],dates=[],reports=0));g['dates'].append(date);g['reports']+=1
            for k in s.get('row_keysets',[]):
                key=sha(canon(k['keys']));g=rowgroups.setdefault(key,dict(keys=k['keys'],dates=[],rows=0,reports=0));g['dates'].append(date);g['rows']+=k['count'];g['reports']+=1
        elif 'header_patterns' in s:
            definition=dict(table_count=s['table_count'],intro_present=s['intro_present'],report_header_table_count=s['report_header_table_count'],header_patterns=s['header_patterns'])
            key=sha(canon(definition));g=html.setdefault(key,dict(definition=definition,dates=[],reports=0));g['dates'].append(date);g['reports']+=1
    return dict(schema='stage181_source_structure_groups_v1',new_bodies_only=True,groups_require_complete_successful_envelope=True,json_top_keyset_groups=top,json_row_keyset_groups=rowgroups,html_header_groups=html,empty_cursor_dates=empty,nonobject_cursor_dates=nonobjects,partial_or_failed_dates=partial,empty_cursor_not_inventory_zero=True,quantity_values_parsed=False,reused_source_structures_not_recomputed=True)


def iso(value):
    d=datetime.fromisoformat(value);assert d.tzinfo is not None;return d


def review(args):
    out=Path(args.output).resolve();assert LINE/'outputs/stage181_warehouse_archive_review' in out.parents and not out.exists()
    mp=Path(args.manifest).resolve();manifest_raw=mp.read_bytes();mb=binding(mp,manifest_raw);assert mb['sha256']==args.manifest_sha256
    manifest=json.loads(manifest_raw);assert manifest['schema']=='stage180_warehouse_archive_manifest_v1' and manifest['status'] in ('completed','stopped'),'root terminal notice required; partial archive is not reviewable'
    folder=mp.parent
    # Each bound metadata file is read once and reused in memory.
    blobs={};meta={}
    for name in ('started','date_manifest','journal','terminal'):
        b=manifest[name];assert Path(b['path']).parent==folder;data=read_bound(b);blobs[name]=data
        meta[name]=[json.loads(line) for line in data.decode().splitlines()] if name=='journal' else json.loads(data)
    terminal=meta['terminal'];assert terminal['status']==manifest['status'] and terminal['exit_code']==(0 if manifest['status']=='completed' else 1)
    inputs=manifest['inputs'];assert inputs['protocol']['sha256']==PROTOCOL_SHA and inputs['plan']['sha256']==PLAN_SHA and inputs['source']['sha256']==SOURCE_SHA
    protocol=json.loads(read_bound(inputs['protocol']));plan=json.loads(read_bound(inputs['plan']));read_bound(inputs['source'])
    assert binding(TOOLS/'test_stage180_warehouse_archive.py')['sha256']==AUTHOR_TEST_SHA
    same(protocol['plan'],inputs['plan']);assert protocol['http']==plan['proposed_network_budget']==manifest['budget']
    budget=protocol['http'];actions,hashes=actions_from(plan,protocol);reuse_evidence=inherited_reuse_evidence(plan,protocol)
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic();own_source=[binding(TOOLS/n) for n in ('stage181_warehouse_archive_review.py','test_stage181_warehouse_archive_review.py')]
    receipt=dict(schema='stage181_independent_warehouse_archive_review_v1',completed=False,C=0,I=0,M=0,errors=[],archive_manifest=mb,archive_status=manifest['status'],protocol=inputs['protocol'],plan=inputs['plan'],author_source=inputs['source'],review_source_bundle=own_source,new_fit=0,new_cash=0,SQL=0,network=0,normalization_calls=0,quantity_values_parsed=False,author180_imported=False,reused_body_reads=0,new_body_reads=0,cumulative_fit=409,cumulative_cash=218,automatic_retry=False)
    observations=[];observation_path=out/'new_body_observations.jsonl.gz'
    write_json(out/'started.json',dict(status='started_after_explicit_root_terminal_notice',archive_manifest=mb,review_source_bundle=own_source,new_fit=0,new_cash=0,SQL=0,network=0,raw_bodies_read_once=True,automatic_retry=False))
    observation_stream=gzip.open(observation_path,'xt',encoding='utf-8')
    try:
        rows=meta['date_manifest'];journal=meta['journal'];assert len(rows)==len(actions)==3018
        for a,r in zip(actions,rows):assert all(r[k]==a[k] for k in IDENTITY),('all frozen action identities',a)
        assert meta['started']['inputs']==inputs and meta['started']['frozen_domain']==plan['frozen_candidate_domain'] and meta['started']['http']==budget
        assert all(meta['started'][k]==0 and terminal[k]==0 and manifest[k]==0 for k in ('new_fit','new_cash','SQL','new_labels','new_prices'))
        assert all(m['financial_authorization'] is False and m['first_publication_PIT_proved'] is False for m in (manifest,terminal,meta['started']))
        assert manifest['automatic_retry'] is False and manifest['automatic_resume'] is False and manifest['strict_PIT'] is False
        validate_stop_order(rows,manifest['status'])
        assert journal[0]['event']=='batch_started' and journal[0]['date_count']==3018 and journal[0]['full_action_records_sha256']==hashes['full_action_records_sha256']
        date_events=defaultdict(list);dispatch=[];event_positions={}
        for i,event in enumerate(journal):
            iso(event['archived_at'])
            if event['event'] in ('date_terminal','archive_failure'):
                rec=event['record'];date_events[rec['sequence_index']].append(rec);event_positions[rec['sequence_index']]=i
            elif event['event']=='get_dispatch_pending':dispatch.append((i,event))
            else:assert i==0 and event['event']=='batch_started'
        responses={};response_bytes=0
        # Response metadata is not a report body; read all preserved records once.
        for path in sorted(folder.glob('*_response.json')):
            data=path.read_bytes();response_bytes+=len(data);responses[path.stem.removesuffix('_response')]=(data,json.loads(data),binding(path,data))
        body_bytes=0;new_paths=set();new_dates=[];status_counts=Counter();date_states=Counter();envelope_counts=Counter();metadata_truncated=[];failure_dates=[];get_starts=[]
        for a,r in zip(actions,rows):
            state=r['state'];status_counts[state]+=1;assert state!='not_attempted_pending'
            if state=='not_attempted_after_stop':assert r['attempt']==0 and set(r)==set(IDENTITY)|{'state','attempt'};assert a['sequence_index'] not in date_events;continue
            assert len(date_events[a['sequence_index']])==1 and date_events[a['sequence_index']][0]==r,('persistent terminal journal',a['date'])
            if r.get('metadata_capture_truncated'):metadata_truncated.append(a['date'])
            if 'response' in r:
                data,response,rb=responses[a['date']];same(rb,r['response']);assert dict(response,response=rb)==r,('exact response metadata',a['date'])
            else:assert r.get('metadata_capture_truncated') is True,('missing response binding',a['date'])
            if state not in SUCCESS:failure_dates.append(a['date'])
            if a['action']=='reuse':
                source=plan['reuse_by_date'][a['date']];assert r['attempt']==0
                assert r['original_body_binding']==source['body'] and r['original_fetch_metadata']==source['original_fetch_metadata'] and r['original_evidence']==source['evidence']
                if state=='reused_binding_verified':
                    same(r['body'],source['body']);assert r['body']['reused'] and r['body']['complete'] and not r['body']['truncated_prefix'];assert r['expected_envelope'] and r['date_state'] in ('matched','absent')
                    if a['date'] in ('20200102','20230103'):assert r['report_date_fields']=={k:source['original_fetch_metadata']['report_metadata'][k] for k in ('report_date','o_tradingday')}
                    else:assert r['date_state']=='matched'
                else:assert state=='failed_reuse_binding'
                assert not (folder/(a['date']+('.dat' if a['format']=='json' else '.html'))).exists(),'reused source copied into archive'
                continue
            assert r['attempt'] in (0,1)
            if r['attempt']==0:assert state=='failed_bound_or_budget' and 'body' not in r;continue
            if 'requested_timeout_seconds' in r:
                timeout=r['requested_timeout_seconds'];assert len(timeout)==2 and 0<timeout[0]<=8 and 0<timeout[1]<=20
                get_starts.append((a['date'],r['get_start_elapsed_seconds']))
            body=r['body'];path=Path(body['path']);assert path==folder/(a['date']+('.dat' if a['format']=='json' else '.html')) and body['reused'] is False
            data=path.read_bytes();receipt['new_body_reads']+=1;same(binding(path,data),body);assert body['truncated_prefix']==(not body['complete'])
            body_bytes+=len(data);assert len(data)<=budget['per_body_cap_bytes']+1 and body_bytes<=budget['global_new_response_body_cap_bytes']+1
            result=inspect_source(data,a['format'],a['date']);env=result['envelope'];structure=result['structure'];new_paths.add(str(path));new_dates.append(a['date'])
            for key,value in env.items():
                if key in r:assert r[key]==value,('independent envelope/date',a['date'],key,r[key],value)
            if state=='http200_expected_envelope':
                assert r['http_status']==200 and body['complete'] and env['expected_envelope'] and env['date_state'] in ('matched','absent')
                assert not r['report_elapsed_cap_exceeded']
            elif state=='failed_envelope_or_report_date':assert r.get('http_status')==200 and (not env['expected_envelope'] or env['date_state'] in ('conflict','unparseable'))
            elif state=='failed_http_or_network':assert r.get('http_status')!=200 or r.get('error_type')
            elif state=='failed_bound_or_budget':assert r.get('error') or r.get('metadata_capture_truncated')
            else:assert state=='failed_archive_io'
            if r.get('report_elapsed_cap_exceeded') or r.get('elapsed_seconds',0)>35.001:assert state=='failed_bound_or_budget'
            iso(r['started_at']);iso(r['finished_at']);iso(body['archived_at'])
            date_states[env['date_state']]+=1;envelope_counts[str(env['expected_envelope'])]+=1
            observation=dict(date=a['date'],format=a['format'],body={k:body[k] for k in ('path','bytes','sha256','complete','truncated_prefix')},archive_state=state,date_state=env['date_state'],report_dates=env['report_dates'],expected_envelope=env['expected_envelope'],structure=structure)
            observations.append(observation);observation_stream.write(canon(observation).decode()+'\n')
            if len(observations)%256==0:
                observation_stream.flush();print(json.dumps(dict(phase='new_body_hash_envelope_structure',checked=len(observations),bytes=body_bytes)),flush=True)
        observation_stream.close()
        write_json(out/'body_pass_checkpoint.json',dict(status='all_present_new_bodies_checked_once',new_body_reads=receipt['new_body_reads'],body_bytes_checked=body_bytes,observations=binding(observation_path),raw_rereads=0,quantity_values_parsed=False,archive_manifest=mb,pending='global journal/budget/summary accounting; no automatic retry'))
        # Exact saved body inventory and all irreversible request/source states.
        assert {str(p) for ext in ('*.dat','*.html') for p in folder.glob(ext)}==new_paths
        attempted=sum(r['attempt'] for r in rows if r['action']=='new_get');assert len(dispatch)==attempted<=3009
        for (position,event),r in zip(dispatch,[r for r in rows if r['action']=='new_get' and r['attempt']==1]):
            assert event['sequence_index']==r['sequence_index'] and event['date']==r['date'] and event['url']==r['url'] and event['attempt']==1
            assert event['prepared_elapsed_seconds']<=r['get_start_elapsed_seconds']
        if dispatch:
            assert all(event_positions[r['sequence_index']]<dispatch[0][0] for r in rows if r['action']=='reuse' and r['state']=='reused_binding_verified')
            assert sum(r['state']=='reused_binding_verified' for r in rows)==9
        for (_,previous),(_,current) in zip(get_starts,get_starts[1:]):assert current-previous>=1-1e-9,('actual GET start gap',previous,current)
        assert all(0<=elapsed<14400 for _,elapsed in get_starts)
        summary=manifest['summary'];assert terminal['summary']==summary
        expected_summary=dict(date_count=3018,state_counts=dict(status_counts),report_requests_attempted=attempted,reused_binding_verified=status_counts['reused_binding_verified'],new_expected_envelopes=status_counts['http200_expected_envelope'],completed_dates=sum(status_counts[k] for k in SUCCESS),not_attempted=status_counts['not_attempted_after_stop'],new_response_body_bytes=body_bytes,reused_body_bytes=sum(r.get('body',{}).get('bytes',0) for r in rows if r['state']=='reused_binding_verified'))
        assert all(summary[k]==v for k,v in expected_summary.items()),('all archive summary counts',expected_summary,summary)
        initial=canon([dict(a,state='not_attempted_pending',attempt=0) for a in actions])+b'\n'
        metadata_before=len(blobs['started'])+len(initial)+len(blobs['journal'])+response_bytes
        assert summary['metadata_bytes_before_terminal']==metadata_before
        metadata_final=len(manifest_raw)+sum(len(v) for v in blobs.values())+response_bytes
        assert metadata_final<=budget['metadata_archive_cap_bytes']
        assert bool(manifest['status']=='completed')==(summary['completed_dates']==3018 and terminal['stop_reason'] is None)
        assert terminal['cumulative_fit']==409 and terminal['cumulative_cash']==218 and terminal['goal_complete'] is False
        groups=group_structures(observations)
        with (out/'source_structure_groups.json').open('x') as f:json.dump(groups,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        assert [binding(TOOLS/n) for n in ('stage181_warehouse_archive_review.py','test_stage181_warehouse_archive_review.py')]==own_source
        same(binding(mp),mb)
        receipt.update(completed=True,source_archive_arithmetic_and_provenance_accepted=True,all_frozen_date_identities_checked=3018,new_response_body_bytes_checked=body_bytes,new_body_dates_checked=new_dates,reuse_evidence=reuse_evidence,all_journal_events_checked=len(journal),all_response_metadata_checked=len(responses),summary_checked=summary,actual_GET_start_records=len(get_starts),date_state_counts=dict(date_states),envelope_counts=dict(envelope_counts),metadata_final_bytes=metadata_final,metadata_truncated_dates=metadata_truncated,failed_dates=failure_dates,scope_hashes=hashes,json_new_bodies=sum(o['format']=='json' for o in observations),html_new_bodies=sum(o['format']=='html' for o in observations),empty_cursor_dates=groups['empty_cursor_dates'],json_top_keyset_groups=len(groups['json_top_keyset_groups']),json_row_keyset_groups=len(groups['json_row_keyset_groups']),html_header_groups=len(groups['html_header_groups']),archive_complete=manifest['status']=='completed',historical_physical_units_certified=False,unit_type_codebook_certified=False,first_publication_PIT_certified=False,normalization_or_feature_authorized=False,financial_authorization=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        receipt['output_bindings']={n:binding(out/n) for n in ('started.json','body_pass_checkpoint.json','new_body_observations.jsonl.gz','source_structure_groups.json')}
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        observation_stream.close()
        receipt['elapsed_seconds']=time.monotonic()-start
        with (out/'receipt.json').open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],new_body_reads=receipt['new_body_reads'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','manifest-sha256','output'):parser.add_argument('--'+key,required=True)
    review(parser.parse_args())


if __name__=='__main__':main()
