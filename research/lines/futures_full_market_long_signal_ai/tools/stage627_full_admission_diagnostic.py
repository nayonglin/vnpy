"""Frozen625: unchanged52+K full admission diagnostic, no fit or cash replay.

Historical END=2026-10-16. A separate u=20 -> D=21 forward calculation is
not an input or dependency. Actual execution belongs only to root after628.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='a9f4363c6069fc95ad7e845e45fb925619ae69b73e256bd12010f67b4c484651'
SCOPES=('main','holdout_0','holdout_1')
END='2026-10-16'
SCORE=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id',
       'family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','score','scope','cutoff']
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
K_ID=SCORE[:10]
K_FIELDS=K_ID+['u_action_eligible','primary_domain','calendar_allowed','calendar_state','D_date',
    'K_target_date','K_index','K_date','K_state','K_after_sample_end','timing_state','branch',
    'label_state','participation_state','policy_reward_known','policy_reward','policy_known_date',
    'policy_known_phase','K_stress_known','K_stress_net_R','K_stress_known_date','K_stress_known_phase',
    'K_stress_state','K_stress_exit_index','K_stress_exit_date','K_stress_exit_reason',
    'unknown_index','unknown_date','label_known_date','label_known_phase','participation_known_date',
    'participation_known_phase','cancel_reason','exit_reason','filled','trade_label_known','entry_date','exit_date']
PURE=['pure_K_gate','pure_K_state','D_index','D_date','K_target_date','K_index','K_date','K_state','K_after_sample_end']
ACCEPT=IDENTITY+['selected','chosen_action_id','chosen_action_sequence_index','chosen_epoch',
                 'anchor_epoch','score','cutoff']
METRICS=('A_E','U_E','Delta_E','R_known_contribution','A_I','U_I','Delta_I','Z_lower','Z_upper')
spec=importlib.util.spec_from_file_location('accepted156_pure',LINE/'tools/stage156_voluntary_choices.py')
fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)


def integer(v):
    return fixed.integer(v)


def family_group(v):
    return int(hashlib.sha256(str(v).encode()).hexdigest(),16)%2


def binding(path):
    p=Path(path);data=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def read_bound(b):
    data=Path(b['path']).read_bytes()
    if len(data)!=b['bytes'] or hashlib.sha256(data).hexdigest()!=b['sha256']:
        raise ValueError('binding mismatch '+b['path'])
    return data


def json_write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


class HashStream:
    def __init__(self,stream):self.stream=stream;self.sha=hashlib.sha256();self.n=0
    def read(self,size=-1):
        data=self.stream.read(size);self.sha.update(data);self.n+=len(data);return data
    def write(self,data):
        n=self.stream.write(data);self.sha.update(data[:n]);self.n+=n;return n
    def flush(self):self.stream.flush()
    def tell(self):return self.n


def csv_rows(b,fields,receipts,role):
    """Hash compressed bytes during the sole original CSV parse, never prehash."""
    with Path(b['path']).open('rb') as stream:
        hashed=HashStream(stream)
        with gzip.GzipFile(fileobj=hashed,mode='rb') as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as text:
                reader=csv.reader(text);header=next(reader);positions=[header.index(k) for k in fields]
                count=0
                for cells in reader:
                    if len(cells)!=len(header):raise ValueError('CSV width '+role)
                    count+=1;yield {k:cells[i] for k,i in zip(fields,positions)}
        if hashed.n!=b['bytes'] or hashed.sha.hexdigest()!=b['sha256']:
            raise ValueError('combined stream binding mismatch '+role)
        receipts[role]=dict(b,rows=count,source_opens=1,hash_and_parse_same_stream=True,columns=fields)


@contextmanager
def csv_sink(path,fields,artifacts):
    with Path(path).open('wb') as raw:
        hashed=HashStream(raw)
        with gzip.GzipFile(filename='',fileobj=hashed,mode='wb',mtime=0) as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as text:
                writer=csv.DictWriter(text,fieldnames=fields,extrasaction='ignore');writer.writeheader()
                yield writer
        artifacts[Path(path).name]=dict(path=str(Path(path).resolve()),bytes=hashed.n,sha256=hashed.sha.hexdigest())


def pure_calendar(row,calendar,boundaries,end):
    epoch=row['reference_epoch'];u=integer(row['u_index'])
    if epoch not in boundaries:boundaries[epoch]=fixed.calendar_boundary(epoch,calendar,end)
    b=boundaries[epoch];D=u+1 if u+1<len(calendar) else None
    day=calendar[D] if D is not None else None
    if b['K_state']=='before_calendar_blocked':gate,state=False,'K_before_calendar_blocked'
    elif D is None:gate,state=None,'next_source_session_unknown'
    elif b['K_index'] is None:gate,state=day<b['K_target_date'],'K_after_calendar_D_before_target'
    else:gate,state=D<b['K_index'],'D_before_K' if D<b['K_index'] else 'D_on_or_after_K'
    return dict(pure_K_gate=None if gate is None else int(gate),pure_K_state=state,D_index=D,D_date=day,**b)


def select_domain(mothers,scores,calendar,end,score_sink=None):
    """Construct all-sign E/m before outcomes; all literals survive in score cache."""
    parents={integer(p['sequence_index']):p for p in mothers}
    if len(parents)!=len(mothers) or len({p['event_id'] for p in mothers})!=len(mothers):
        raise ValueError('duplicate original mother')
    if not calendar or calendar!=sorted(set(calendar)):raise ValueError('unique ordered calendar required')
    all_best={s:{} for s in SCOPES};positive_best={s:{} for s in SCOPES}
    seen={};seen_seq={};boundaries={};unknown=set();observed=set();counts=Counter()
    fingerprint_fields=[k for k in SCORE if k not in ('score','scope','cutoff')]
    for raw in scores:
        row={k:raw[k] for k in SCORE};scope=row['scope']
        if scope not in SCOPES:raise ValueError('unexpected score scope')
        seq,ps,u=map(integer,[row['sequence_index'],row['mother_sequence_index'],row['u_index']])
        p=parents.get(ps)
        if p is None:raise ValueError('score outside complete forward mothers')
        if any(row[k]!=p[k] for k in ('product_id','family_id','u_date','u_index')):
            raise ValueError('score mother identity mismatch')
        if row['mother_event_id']!=p['event_id'] or row['anchor_epoch']!=p['reference_epoch']:
            raise ValueError('score mother event/anchor mismatch')
        if not 0<=u<len(calendar) or calendar[u]!=row['u_date']:raise ValueError('source u calendar mismatch')
        if row['cutoff']!=fixed.cutoff_for(row['u_date']):raise ValueError('future/mismatched cutoff')
        if row['reference_epoch'].rsplit('.',1)[0]!=row['product_id']:raise ValueError('exact product/epoch mismatch')
        group=family_group(row['family_id'])
        if scope!='main' and int(scope[-1])!=group:raise ValueError('held family group mismatch')
        bit=1<<SCOPES.index(scope);aid=row['action_id']
        fingerprint=hashlib.sha256(json.dumps([row[k] for k in fingerprint_fields],separators=(',',':')).encode()).digest()
        if aid in seen:
            old_seq,old_print,mask,old_group=seen[aid]
            if seq!=old_seq or fingerprint!=old_print or mask&bit or group!=old_group:
                raise ValueError('duplicate/cross-scope child identity mismatch')
            seen[aid]=(seq,fingerprint,mask|bit,group)
        else:
            if seq in seen_seq:raise ValueError('action sequence reused by another action')
            seen_seq[seq]=aid;seen[aid]=(seq,fingerprint,bit,group)
        original=integer(row['u_action_eligible'])
        if original not in (0,1):raise ValueError('binary u eligibility required')
        value=float(row['score']);gate=pure_calendar(row,calendar,boundaries,end);row.update(gate)
        observed.add((scope,ps));counts[scope]+=1;counts[scope+'/'+row['cutoff']]+=1
        if score_sink is not None:score_sink.writerow(row)
        if original==1 and math.isfinite(value):
            if gate['pure_K_gate'] is None:unknown.add((scope,row['u_date'],row['family_id']))
            elif gate['pure_K_gate']==1:
                if ps not in all_best[scope] or fixed.rank_action(row)<fixed.rank_action(all_best[scope][ps]):all_best[scope][ps]=row
                if value>0 and (ps not in positive_best[scope] or fixed.rank_action(row)<fixed.rank_action(positive_best[scope][ps])):
                    positive_best[scope][ps]=row
        elif not math.isfinite(value):counts['nonfinite_score_rows']+=1
    for _,_,mask,group in seen.values():
        if mask!=(1|(1<<(group+1))):raise ValueError('main plus matching held projection required')
    choices=[];positive={}
    for scope in SCOPES:
        winners=fixed.family_winners(positive_best[scope]);positive[scope]=winners
        by_family={(r['family_id'],r['u_index']):r for r in fixed.family_winners(all_best[scope]).values()}
        for row in winners.values():by_family[(row['family_id'],row['u_index'])]=row
        for row in by_family.values():
            marked=int(integer(row['mother_sequence_index']) in winners)
            choices.append(dict(row,m=marked))
    return dict(choices=sorted(choices,key=lambda r:(r['scope'],integer(r['u_index']),r['family_id'])),
                positive=positive,membership_unknown=unknown,observed=observed,counts=dict(counts),
                unique_actions=len(seen),boundaries=boundaries)


def check_main(positive,accepted,mothers):
    parents={integer(p['sequence_index']):p for p in mothers};seen=set();n=0
    for row in accepted:
        ps=integer(row['sequence_index']);p=parents.get(ps)
        if p is None or ps in seen:raise ValueError('accepted156 mother population mismatch')
        seen.add(ps)
        if any(row[k]!=p[k] for k in IDENTITY):raise ValueError('accepted156 original mother identity mismatch')
        win=positive['main'].get(ps);flag=integer(row['selected'])
        if flag!=int(win is not None):raise ValueError('original156 positive winner changed')
        if win is not None:
            expected=dict(chosen_action_id=win['action_id'],chosen_action_sequence_index=win['sequence_index'],
                          chosen_epoch=win['reference_epoch'],anchor_epoch=win['anchor_epoch'],cutoff=win['cutoff'])
            if any(row[k]!=v for k,v in expected.items()) or float(row['score'])!=float(win['score']):
                raise ValueError('original156 chosen literal identity/score changed')
            n+=1
        elif row['chosen_action_id']!='':raise ValueError('unselected156 has action')
    if seen!=set(parents):raise ValueError('complete accepted156 main mothers required')
    return n


def label_outcome(row,end):
    def observed(date,phase):return bool(date and phase and date<=end)
    if integer(row['primary_domain'])!=1:return dict(known=False,Y=None,outcome_reason='nonprimary_zero_not_outcome')
    if row['K_stress_known']=='1':
        value=float(row['K_stress_net_R'])
        if math.isfinite(value) and observed(row['K_stress_known_date'],row['K_stress_known_phase']):
            return dict(known=True,Y=value,outcome_reason='known_K_stress_trade')
    if (row['branch']=='known_nonparticipation' and row['policy_reward_known']=='1'
            and float(row['policy_reward'])==0 and observed(row['policy_known_date'],row['policy_known_phase'])):
        return dict(known=True,Y=0.,outcome_reason='primary_known_cancel_zero')
    return dict(known=False,Y=None,outcome_reason='unknown_or_not_mature_at_END')


def day_statistics(rows,membership_unknown=0):
    n=len(rows);k=sum(r['m'] for r in rows);p=k/n if n else 0.
    known=[r for r in rows if r['known']];missing=[r for r in rows if not r['known']]
    nI=len(known);kI=sum(r['m'] for r in known);pI=kI/nI if nI else 0.
    selected=sum(r['m']*r['Y'] for r in known);total=sum(r['Y'] for r in known)
    component=sum((r['m']-p)*r['Y']/n for r in known) if n else 0.
    coeff=[(r['m']-p)/n for r in missing] if n else []
    material=sum(a!=0 for a in coeff);lower=sum((r['m']-p)/n*(r['Y']>0) for r in known) if n else 0.
    upper=lower;lower+=sum(min(a,0) for a in coeff);upper+=sum(max(a,0) for a in coeff)
    missing_selected=sum(r['m'] for r in missing)
    A=selected/n if n else 0.;U=p*total/n if n else 0.
    if missing_selected or membership_unknown:A=None
    if (p!=0 and missing) or membership_unknown:U=None
    delta=None if material or membership_unknown else component
    return dict(n=n,k=k,p=p,nI=nI,kI=kI,pI=pI,A_E=A,U_E=U,Delta_E=delta,
        R_known_contribution=component,A_I=selected/nI if nI else 0.,U_I=pI*total/nI if nI else 0.,
        Delta_I=(selected-pI*total)/nI if nI else 0.,Z_lower=None if membership_unknown else lower,
        Z_upper=None if membership_unknown else upper,unknown=len(missing),unknown_selected=missing_selected,
        unknown_nonselected=len(missing)-missing_selected,unknown_material_terms=material,
        unknown_coefficient_positive_mass=sum(max(a,0) for a in coeff),
        unknown_coefficient_negative_mass=sum(min(a,0) for a in coeff),membership_unknown_families=membership_unknown,
        n0=int(n==0),k0=int(k==0),kn=int(k==n),nI0=int(nI==0),kI0=int(kI==0),kInI=int(kI==nI),
        informative=int(0<kI<nI),selected_known_families=sorted({r['family_id'] for r in known if r['m']}),
        unknown_families=sorted({r['family_id'] for r in missing}),
        selected_known_count=kI,known_positive=sum(r['Y']>0 for r in known),
        selected_known_positive=sum(r['Y']>0 for r in known if r['m']))


def mean_ci(values,indices=None):
    if not values or any(v is None or not math.isfinite(v) for v in values):
        return dict(mean=None,ci95=None,identified=False)
    data=np.asarray(values,float);out=dict(mean=float(data.mean()),ci95=None,identified=True)
    if indices is not None:
        if indices.ndim!=2 or indices.shape[1]!=len(data) or indices.dtype.kind not in 'iu' or np.any(indices<0) or np.any(indices>=len(data)):
            raise ValueError('existing index array differs from full source-date grid')
        means=data[indices].mean(axis=1);out['ci95']=[float(v) for v in np.percentile(means,[2.5,97.5])]
    return out


def summarize(days,indices=None):
    result={name:mean_ci([d[name] for d in days],indices) for name in METRICS}
    sums=['n','k','nI','kI','unknown','unknown_selected','unknown_nonselected','unknown_material_terms',
          'n0','k0','kn','nI0','kI0','kInI','selected_known_count','known_positive','selected_known_positive']
    support={name:int(sum(d[name] for d in days)) for name in sums}
    support.update(source_dates=len(days),informative_dates=sum(d['informative'] for d in days),
        unknown_dates=sum(d['unknown']>0 for d in days),membership_unknown_dates=sum(d['membership_unknown_families']>0 for d in days),
        unknown_family_count=len({f for d in days for f in d['unknown_families']}),
        selected_known_family_count=len({f for d in days for f in d['selected_known_families']}))
    result['support']=support;return result


def diagnostic_gates(windows,eras):
    positive=lambda r,a,b:r[a]['mean'] is not None and r[a]['mean']>0 and r[b]['mean'] is not None and r[b]['mean']>0
    conditions={};full_conditions={};full_identified=True
    for w in ('primary_2020','cold_2023'):
        r=windows['main/'+w];ci=r['Delta_I']['ci95']
        conditions['main/'+w]=r['A_I']['mean']>0 and ci is not None and ci[0]>0
        ci_full=r['Delta_E']['ci95']
        full_conditions['main/'+w]=positive(r,'A_E','Delta_E') and ci_full is not None and ci_full[0]>0
    for scope in SCOPES:
        for era in ('early_2020_2022','late_2023_plus'):
            r=eras[scope+'/'+era];support=r['support'];enough=support['informative_dates']>=60 and support['selected_known_family_count']>=8
            conditions[scope+'/'+era+'/support']=enough
            full_conditions[scope+'/'+era+'/support']=enough
            if scope!='main' or era=='early_2020_2022':
                conditions[scope+'/'+era]=positive(r,'A_I','Delta_I')
                full_conditions[scope+'/'+era]=positive(r,'A_E','Delta_E')
    for r in list(windows.values())+list(eras.values()):
        if r['A_E']['mean'] is None or r['Delta_E']['mean'] is None or r['support']['membership_unknown_dates']:
            full_identified=False
    return dict(identity=True,conditional_support=all(conditions.values()),conditional_checks=conditions,
        full_E_support=('inconclusive' if not full_identified else 'supported' if all(full_conditions.values()) else 'unsupported'),
        full_E_checks=full_conditions,full_E_pointidentified=full_identified,binary_descriptive_only=True,
        goal_complete=False,production_qualified=False,increased_betting_qualified=False,
        interpretation='Conditional I is not full E or causal cash wealth. No automatic continuation/promotion.')


def progress(out,event,**kwargs):
    with (out/'progress.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),event=event,**kwargs))+'\n')


def actual(protocol_path,ready_path,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);start=time.monotonic();receipts={};artifacts={}
    json_write(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),new_fit=0,new_cash=0,
        automatic_retry=False,historical_END=END,current_day_close_dependency=False))
    try:
        pb=binding(protocol_path)
        if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen625 protocol changed')
        protocol=json.loads(Path(protocol_path).read_text());ready=json.loads(Path(ready_path).read_text())
        if ready['protocol']!=pb or ready['fixture_receipt']['exit_code']!=0:raise ValueError('source-ready protocol/fixture mismatch')
        for b in ready['sources']:read_bound(b)
        receipt=json.loads(read_bound(ready['fixture_receipt']['binding']))
        if receipt['exit_code']!=0 or receipt['source']!=ready['sources'][0] or receipt['fixture']!=ready['sources'][1]:
            raise ValueError('tested source/fixture bindings differ')
        for b in protocol['input_metadata_bindings']:read_bound(b)
        for b in protocol['immutable_sources'].values():read_bound(b)
        inputs=protocol['input_bindings'];expected=protocol['scope'];forward=[];families=set();products=set();mother_seen=set();events=set()
        with csv_sink(out/'mother_identity.csv.gz',IDENTITY,artifacts) as sink:
            for row in csv_rows(inputs['mothers'],IDENTITY,receipts,'mothers'):
                seq=integer(row['sequence_index'])
                if seq!=len(mother_seen) or row['event_id'] in events:raise ValueError('original mother sequence/event not unique')
                mother_seen.add(seq);events.add(row['event_id']);families.add(row['family_id']);products.add(row['product_id']);sink.writerow(row)
                if '2020-01-01'<=row['u_date']<=END:forward.append(row)
        if (len(mother_seen),len(forward),len(families),len(products))!=(expected['all_mothers'],expected['forward_mothers'],95,98):
            raise ValueError('whole original mother coverage differs')
        del mother_seen,events
        data=np.load(io.BytesIO(read_bound(inputs['calendar'])),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in data] if data.dtype.kind in 'iu'
                  else data.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=expected['calendar_rows'] or calendar!=sorted(set(calendar)):raise ValueError('original calendar differs')
        json_write(out/'calendar.json',dict(calendar=calendar,source=inputs['calendar']))
        progress(out,'mothers_calendar_complete',forward_mothers=len(forward))
        with csv_sink(out/'forward_scores_slim.csv.gz',SCORE+PURE,artifacts) as sink:
            def score_rows():
                for i,r in enumerate(csv_rows(inputs['child_scores'],SCORE,receipts,'child_scores'),1):
                    if i%250000==0:progress(out,'score_stream_progress',rows=i)
                    yield r
            selected=select_domain(forward,score_rows(),calendar,END,sink)
        counts=selected['counts']
        if sum(counts[s] for s in SCOPES)!=expected['all_scores'] or counts['main']!=expected['main_scores'] or selected['unique_actions']!=expected['main_scores']:
            raise ValueError('complete score count differs')
        with csv_sink(out/'accepted156_main_projection.csv.gz',ACCEPT,artifacts) as sink:
            def accepted_rows():
                for r in csv_rows(inputs['accepted156_main_choices'],ACCEPT,receipts,'accepted156_main_choices'):
                    sink.writerow(r);yield r
            main_preserved=check_main(selected['positive'],accepted_rows(),forward)
        choices=selected['choices'];union={r['action_id']:r for r in choices}
        with csv_sink(out/'E_before_Y.csv.gz',SCORE+PURE+['m'],artifacts) as sink:
            sink.writerows(choices)
        progress(out,'E_frozen_before_K_outcomes',E_scope_rows=len(choices),union_actions=len(union),main_positive_preserved=main_preserved)
        by_action={};seen_labels=set();label_count=0
        with csv_sink(out/'selected_K_literals.csv.gz',K_FIELDS,artifacts) as sink:
            for row in csv_rows(inputs['labels_K'],K_FIELDS,receipts,'labels_K'):
                if integer(row['sequence_index'])!=label_count or row['action_id'] in seen_labels:
                    raise ValueError('full K label sequence/action domain differs')
                label_count+=1;seen_labels.add(row['action_id']);choice=union.get(row['action_id'])
                if choice is not None:
                    if any(row[k]!=choice[k] for k in K_ID) or row['u_action_eligible']!='1':raise ValueError('selected K original identity mismatch')
                    if row['primary_domain']!='1' or row['calendar_allowed']!='1':raise ValueError('K primary/calendar disagrees with independently frozen E')
                    for k in ('D_date','K_target_date','K_date','K_state'):
                        if row[k]!=(str(choice[k]) if choice[k] is not None else ''):raise ValueError('K clock mismatch '+k)
                    if row['K_index']!=(str(choice['K_index']) if choice['K_index'] is not None else ''):raise ValueError('K index mismatch')
                    sink.writerow(row);by_action[row['action_id']]=label_outcome(row,END)
                if label_count%250000==0:progress(out,'K_stream_progress',rows=label_count)
        if label_count!=expected['K_action_rows'] or set(by_action)!=set(union):raise ValueError('complete K/selected union count differs')
        del seen_labels,union
        for r in choices:r.update(by_action[r['action_id']])
        with csv_sink(out/'E_linked.csv.gz',SCORE+PURE+['m','known','Y','outcome_reason'],artifacts) as sink:sink.writerows(choices)
        json_write(out/'selection_summary.json',dict(score_counts=counts,unique_forward_actions=selected['unique_actions'],
            E_scope_rows=len(choices),E_union_actions=len(by_action),main_positive_preserved=main_preserved,
            membership_unknown_family_u=len(selected['membership_unknown']),historical_END=END,
            current_day_close_dependency=False,held_control='reconstructed original156 positive+K rule; no accepted held file'))
        progress(out,'K_join_complete',selected_unknown=sum(not r['known'] for r in choices))
        grids=[d for d in calendar if '2020-01-01'<=d<=END];groups=defaultdict(list);unknown=Counter()
        for r in choices:groups[(r['scope'],r['u_date'])].append(r)
        for s,d,f in selected['membership_unknown']:unknown[(s,d)]+=1
        daily={s:[] for s in SCOPES}
        for s in SCOPES:
            for day in grids:daily[s].append(dict(scope=s,u_date=day,**day_statistics(groups[(s,day)],unknown[(s,day)])))
        fields=['scope','u_date']+[k for k in daily['main'][0] if k not in ('scope','u_date')]
        with csv_sink(out/'daily.csv.gz',fields,artifacts) as sink:
            for s in SCOPES:
                for row in daily[s]:sink.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,list) else v for k,v in row.items()})
        windows={};eras={};annual={};indices_meta={}
        for window,bounds in protocol['windows'].items():
            b=inputs[window+'_indices'];indices=np.load(io.BytesIO(read_bound(b)),allow_pickle=False)
            indices_meta[window]=dict(b,shape=list(indices.shape),dtype=str(indices.dtype),regenerated=False)
            if indices.shape[0]!=2000:raise ValueError('existing2000 block repetitions required')
            for s in SCOPES:
                part=[r for r in daily[s] if bounds[0]<=r['u_date']<=bounds[1]]
                windows[s+'/'+window]=summarize(part,indices)
        for s in SCOPES:
            for era,bounds in dict(protocol['secondary_eras'],late_2023_plus=protocol['windows']['cold_2023']).items():
                eras[s+'/'+era]=summarize([r for r in daily[s] if bounds[0]<=r['u_date']<=bounds[1]])
            for year in range(2020,2027):annual[s+'/'+str(year)]=summarize([r for r in daily[s] if r['u_date'][:4]==str(year)])
        json_write(out/'windows.json',windows);json_write(out/'eras.json',eras);json_write(out/'annual.json',annual)
        json_write(out/'indices_metadata.json',indices_meta)
        # A full family grid preserves products with no opportunity and all original mother coverage.
        mother_family=Counter((p['family_id'],p['u_date'][:4]) for p in forward)
        family_rows=[];family_groups=defaultdict(list)
        for row in choices:family_groups[(row['scope'],row['family_id'],row['u_date'][:4])].append(row)
        for s in SCOPES:
            scoped=[f for f in sorted(families) if s=='main' or family_group(f)==int(s[-1])]
            for f in scoped:
                for year in range(2020,2027):
                    rs=family_groups[(s,f,str(year))]
                    family_rows.append(dict(scope=s,family_id=f,year=year,forward_mothers=mother_family[(f,str(year))],
                        E=len(rs),selected=sum(r['m'] for r in rs),known=sum(r['known'] for r in rs),
                        unknown=sum(not r['known'] for r in rs),selected_known=sum(r['m'] for r in rs if r['known']),
                        unknown_selected=sum(r['m'] for r in rs if not r['known'])))
        with csv_sink(out/'family_year_including_zero.csv.gz',list(family_rows[0]),artifacts) as sink:sink.writerows(family_rows)
        # Per-mother coverage retains no-child and no-eligible statuses across all appropriate scopes.
        Ekeys={(r['scope'],integer(r['mother_sequence_index'])):r for r in choices}
        with csv_sink(out/'mother_forward_coverage.csv.gz',IDENTITY+['scope','observed_children','positive_selected','E_selected','m'],artifacts) as sink:
            for p in forward:
                ps=integer(p['sequence_index'])
                for s in ('main','holdout_'+str(family_group(p['family_id']))):
                    e=Ekeys.get((s,ps));sink.writerow(dict(p,scope=s,observed_children=int((s,ps) in selected['observed']),
                        positive_selected=int(ps in selected['positive'][s]),E_selected=int(e is not None),m=e['m'] if e else ''))
        gates=diagnostic_gates(windows,eras);json_write(out/'gates.json',gates)
        summary=dict(status='completed',historical_END=END,current_day_close_dependency=False,full_products=98,full_families=95,
            all_mothers=expected['all_mothers'],forward_mothers=len(forward),all_score_rows=expected['all_scores'],
            K_label_rows=label_count,E_scope_rows=len(choices),main_positive_preserved=main_preserved,
            conditional_support=gates['conditional_support'],full_E_support=gates['full_E_support'],
            new_fit=0,new_cash=0,new_K_labels=0,random_policy_draws=0,SQL=0,market_GET=0,
            cumulative_fit=551,cumulative_completed_cash=290,old_partial_cash=1,
            financial_metrics='N/A: potential one-lot R diagnostic, not equity/fill count/ROI/DD/Sharpe/cash winrate',
            continuation='Interpretation only, no automatic promotion or next experiment',adaptive_history_risk='high')
        json_write(out/'summary.json',summary);json_write(out/'input_read_receipts.json',receipts)
        terminal=dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-start,new_fit=0,new_cash=0,
            ended_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False)
        json_write(out/'terminal.json',terminal)
        for p in sorted(out.iterdir()):
            if p.is_file() and p.name not in artifacts:artifacts[p.name]=binding(p)
        manifest=dict(schema='stage627_full_admission_diagnostic_v1',status='completed',protocol=pb,
            source_ready=binding(ready_path),inputs=inputs,input_reads=receipts,source_bundle=ready['sources'],artifacts=artifacts,
            historical_END=END,current_day_close_dependency=False,new_fit=0,new_cash=0,new_labels=0,
            gates=gates,counters=protocol['counters_before'],production_qualified=False)
        json_write(out/'manifest.json',manifest);return terminal
    except BaseException as exc:
        terminal=dict(status='failed',exit_code=1,elapsed_seconds=time.monotonic()-start,new_fit=0,new_cash=0,
            ended_at=datetime.now(timezone.utc).isoformat(),automatic_retry=False,error=repr(exc),traceback=traceback.format_exc())
        json_write(out/'terminal.json',terminal);json_write(out/'input_read_receipts.json',receipts)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True);parser.add_argument('--source-ready',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(actual(args.protocol,args.source_ready,args.output),ensure_ascii=False))
