"""Frozen PMI source-to-completed-u join, using only accepted small source metadata."""
import argparse, bisect, csv, gzip, hashlib, json, math, time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
SH = timezone(timedelta(hours=8))
PROTOCOL_SHA = '38ccfa3add609a40c969eeb4e16d625fcf91d09b853417a1a3b7fe2f2c650cb6'
FIELDS = ['u_index','u_date','macro_available','report_month','NO','FG','reason','pair_source_id','publication_upper','eligible_u_index']

def binding(path, data=None):
    p=Path(path).resolve(); data=p.read_bytes() if data is None else data
    return {'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def dump(path,obj):
    with path.open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False); f.write('\n')
def read_bound(bound):
    p=Path(bound['path']); data=p.read_bytes()
    assert binding(p,data)==bound, 'bound input changed: '+str(p)
    return json.loads(data)
def next_month(month):
    y,m=map(int,month.split('-')); return f'{y+(m==12):04d}-{1 if m==12 else m+1:02d}'
def public_upper(clock):
    kind=clock.get('kind'); value=clock.get('claimed_at')
    if not value or kind not in ('publication_minute','publication_date'): return None
    t=datetime.fromisoformat(value)
    if kind=='publication_minute':
        if t.utcoffset() is None: return None
        return t.replace(second=0,microsecond=0)+timedelta(minutes=1)
    return datetime(t.year,t.month,t.day,tzinfo=SH)+timedelta(days=1)
def closes(calendar):
    return [datetime.fromisoformat(day+'T15:15:00+08:00') for day in calendar]
def make_event(article, times, calendar):
    month=article.get('report_month'); upper=public_upper(article.get('clock',{}))
    fields=article.get('fields',{}); no=fields.get('new_orders',{}).get('value'); fg=fields.get('finished_goods',{}).get('value')
    finite=lambda v: isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<=v<=100
    pair=bool(article.get('pair_complete')) and finite(no) and finite(fg)
    event={'source_id':article['id'],'url':article['url'],'report_month':month,'NO':no,'FG':fg,'pair_complete':pair,
        'field_conflict':any(fields.get(k,{}).get('state')=='conflict' for k in ['new_orders','finished_goods']),
        'clock_kind':article.get('clock',{}).get('kind','unknown'),'publication_upper':upper.isoformat() if upper else None,
        'eligible_u_index':None,'eligible_u_date':None,'D_index':None,'D_date':None,'activation_state':'unknown_identity_or_clock'}
    if not month or not ('2010-01'<=month<='2026-09'): event['activation_state']='identity_unknown_or_outside_month_domain'; return event
    if upper is None: return event
    if upper.astimezone(SH).date()<times[0].date(): event['activation_state']='before_source_calendar'; return event
    index=bisect.bisect_right(times,upper)
    if index==len(times): event['activation_state']='after_source_calendar'; return event
    event.update(eligible_u_index=index,eligible_u_date=calendar[index],activation_state='activated_at_completed_u')
    if index+1<len(calendar): event.update(D_index=index+1,D_date=calendar[index+1])
    return event

def build_join(articles,calendar):
    assert calendar==sorted(set(calendar)) and calendar
    times=closes(calendar); events=[make_event(a,times,calendar) for a in articles]; schedule=defaultdict(list)
    for e in events:
        if e['eligible_u_index'] is not None: schedule[e['eligible_u_index']].append(e)
    active=defaultdict(list); rows=[]
    for index,day in enumerate(calendar):
        for e in schedule[index]: active[e['report_month']].append(e)
        row=dict.fromkeys(FIELDS,''); row.update(u_index=index,u_date=day,macro_available=0,reason='no_activated_report')
        if active:
            month=max(active); versions=active[month]
            pairs=[e for e in versions if e['pair_complete']]
            values={k:{e[k] for e in versions if e[k] is not None} for k in ['NO','FG']}
            conflict=any(e['field_conflict'] for e in versions) or any(len(v)>1 for v in values.values())
            chosen=max(pairs or versions,key=lambda e:(e['publication_upper'],e['source_id']))
            row.update(report_month=month,publication_upper=chosen['publication_upper'],eligible_u_index=chosen['eligible_u_index'])
            if day[:7] not in (month,next_month(month)): row['reason']='reference_month_expired_or_future'
            elif conflict: row['reason']='known_source_value_conflict'
            elif not pairs: row['reason']='latest_reference_month_incomplete_pair'
            else: row.update(macro_available=1,NO=chosen['NO'],FG=chosen['FG'],reason='available_same_original_pair',pair_source_id=chosen['source_id'])
        rows.append(row)
    months=[]
    for y in range(2010,2027):
        for m in range(1,13):
            if (y,m)>(2026,9): continue
            month=f'{y:04d}-{m:02d}'; source=[e for e in events if e['report_month']==month]
            used=[r for r in rows if r['report_month']==month and r['macro_available']]
            months.append({'report_month':month,'versions':source,'available_u_count':len(used),
                'first_available_u':used[0]['u_date'] if used else None,'last_available_u':used[-1]['u_date'] if used else None})
    return rows,{'months':months,'unresolved_or_outside_domain':[e for e in events if not e['report_month'] or not ('2010-01'<=e['report_month']<='2026-09')]}

def fixture(id,month,clock,no,fg):
    return {'id':id,'url':'fixture:'+id,'report_month':month,'pair_complete':no is not None and fg is not None,
        'clock':{'kind':'publication_minute','claimed_at':clock},'fields':{'new_orders':{'value':no,'state':'agrees' if no is not None else 'unparsed_or_not_reported'},
        'finished_goods':{'value':fg,'state':'agrees' if fg is not None else 'unparsed_or_not_reported'}}}
def boundary_checks():
    c=['2020-01-02','2020-01-03','2020-01-06'];t=closes(c)
    assert make_event(fixture('a','2020-01','2020-01-02T15:14:00+08:00',51,47),t,c)['eligible_u_index']==1
    assert make_event(fixture('b','2020-01','2020-01-02T09:30:00+08:00',51,47),t,c)['D_date']=='2020-01-03'
    assert make_event(fixture('c','2020-01','2020-01-04T09:30:00+08:00',51,47),t,c)['eligible_u_index']==2
    c=['2020-01-31','2020-02-03','2020-03-02'];a=fixture('a','2020-01','2020-01-31T09:30:00+08:00',51,47)
    rows,_=build_join([a],c);assert [r['macro_available'] for r in rows]==[1,1,0]
    b=fixture('b','2020-02','2020-02-03T09:30:00+08:00',52,None)
    old=fixture('old','2020-01','2020-02-03T10:30:00+08:00',51,47)
    rows,_=build_join([a,b,old],c);assert rows[1]['report_month']=='2020-02' and rows[1]['macro_available']==0
    a1=fixture('x','2020-01','2020-01-31T09:30:00+08:00',51,None);a2=fixture('y','2020-01','2020-01-31T09:30:00+08:00',None,47)
    rows,_=build_join([a1,a2],c);assert not any(r['macro_available'] for r in rows)
    return {'boundary_assertions':7,'strict_equal_upper_next_u':True,'weekend_next_existing_u':True,'expiry_and_incomplete_clears':True,'no_cross_URL_pair':True}

def main(protocol_path,output,check):
    pdata=protocol_path.read_bytes();assert hashlib.sha256(pdata).hexdigest()==PROTOCOL_SHA
    protocol=json.loads(pdata);assert protocol['schema']=='stage564_frozen_pmi_incremental_v1'
    output.mkdir(parents=True,exist_ok=False); checks=boundary_checks()
    if check:
        ready={'source_ready':True,'actual_started':False,'source':binding(Path(__file__)),'protocol':binding(protocol_path,pdata),'checks':checks,'GET':0,'fit':0,'cash':0,'SQL':0}
        dump(output/'source_ready.json',ready);print(json.dumps(ready));return
    start=time.monotonic();dump(output/'started.json',{'started_at':datetime.now(timezone.utc).isoformat(),'protocol':binding(protocol_path,pdata),'source':binding(Path(__file__))})
    inputs=protocol['source_inputs'];articles=read_bound(inputs['articles']);review=read_bound(inputs['source_review']);calendar=read_bound(inputs['calendar'])
    assert len(articles)==230 and len(calendar)==5587 and review['failed_checks']==0 and review['scope_findings']['critical']==review['scope_findings']['important']==0
    rows,events=build_join(articles,calendar)
    with gzip.open(output/'calendar_u_macro.csv.gz','xt',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    dump(output/'source_months.json',events)
    available=[r for r in rows if r['macro_available']]
    summary={'calendar_rows':len(rows),'article_versions':len(articles),'available_u_rows':len(available),'reason_counts':dict(Counter(r['reason'] for r in rows)),
        'available_unique_report_months':len({r['report_month'] for r in available}),'source_cutoff_support_not_training':{
            cutoff:{'unique_report_months':len({r['report_month'] for r in available if r['u_date']<cutoff}),'u_rows':sum(r['u_date']<cutoff for r in available)}
            for cutoff in protocol['scope']['cutoffs']},'source_calendar_close':'15:15:00+08:00 conditional research convention',
        'source_rows_independent_macro_samples':False,'training_rows_read':0,'mature_label_join_performed':False,'full_market_scope':protocol['scope'],
        'missing_macro_policy':'preserve all mother/child rows; downstream exact A fallback','first_vintage_qualified':False,'goal_complete':False}
    dump(output/'summary.json',summary)
    terminal={'status':'completed','exit_code':0,'calendar_rows':len(rows),'available_u_rows':len(available),'fit':0,'cash':0,'SQL':0,'GET':0,'elapsed_seconds':time.monotonic()-start,'goal_complete':False}
    dump(output/'terminal.json',terminal)
    manifest={'schema':'stage565_pmi_causal_join_v1','inputs':inputs,'source':binding(Path(__file__)),'protocol':binding(protocol_path,pdata),
        **{name:binding(output/file) for name,file in [('calendar_u_macro','calendar_u_macro.csv.gz'),('source_months','source_months.json'),('summary','summary.json'),('terminal','terminal.json')]}}
    dump(output/'manifest.json',manifest);print(json.dumps(terminal),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--check-boundaries',action='store_true')
    a=p.parse_args();main(a.protocol,a.output,a.check_boundaries)
