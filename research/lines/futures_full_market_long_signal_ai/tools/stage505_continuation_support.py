"""Stage505 metadata-only continuation-clock support, not a trading policy.

No historical I/O at import. The root's exact Stage504 authorization is required
for one complete accepted466 metadata projection stream. No original129 actions,
price, numeric target, model, database or monetary replay is supported here.
"""
from __future__ import annotations
import argparse
import bisect
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import traceback
import numpy as np
from stage156_voluntary_choices import calendar_boundary

LINE=Path(__file__).resolve().parents[1]
CUTOFFS=('2020-01-01','2023-01-01')
SCOPES=('main','holdout_0','holdout_1')
END='2026-10-16'
PHASE='after_all_source_close'
FIELDS=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id',
 'reference_epoch','anchor_epoch','u_date','u_index','D_index','u_action_eligible','filled','participation_state',
 'label_state','entry_index','entry_date','exit_index','exit_date','label_known_date','label_known_phase',
 'family_hash_group','c2020_state','c2023_state']
INTERVAL_FIELDS=FIELDS+['K_target_date','K_index','K_date','K_state','K_after_sample_end','entry_before_K',
 'strict_start','strict_end','strict_start_date','strict_end_date','strict_count',
 'ambiguous_terminal_day_count','support_state','candidate_upper_not_execution_certified']


def integer(value,optional=False):
    if value=='' and optional:return None
    v=float(value)
    if not math.isfinite(v) or not v.is_integer() or abs(v)>2**53:raise ValueError('integer_metadata_required')
    return int(v)


def family_group(family):return int(hashlib.sha256(family.encode()).hexdigest(),16)%2


def parse_metadata(raw,calendar):
    """Validate necessary clocks, inheriting full state semantics from accepted467."""
    p=dict(raw)
    for name in ('sequence_index','mother_sequence_index','u_index','D_index','u_action_eligible','filled','family_hash_group'):
        p[name]=integer(raw[name])
    for name in ('entry_index','exit_index'):p[name]=integer(raw[name],optional=True)
    u=p['u_index'];D=p['D_index']
    if not 0<=u<len(calendar) or raw['u_date']!=calendar[u] or D!=u+1:raise ValueError('u_D_calendar')
    if p['u_action_eligible'] not in (0,1) or p['filled'] not in (0,1):raise ValueError('nonbinary_eligibility_filled')
    if raw['family_id']!=raw['product_id'].removesuffix('_F') or raw['reference_epoch'].rsplit('.',1)[0]!=raw['product_id']:
        raise ValueError('product_family_epoch')
    if p['family_hash_group']!=family_group(raw['family_id']):raise ValueError('family_hash_identity')
    for name in ('entry','exit'):
        index=p[name+'_index'];day=raw[name+'_date']
        if (index is None)!= (not bool(day)):raise ValueError('one_sided_'+name+'_clock')
        if index is not None and (not 0<=index<len(calendar) or calendar[index]!=day or day>END):raise ValueError(name+'_calendar')
    if bool(p['filled']) != (p['entry_index'] is not None):raise ValueError('filled_entry_clock')
    if p['filled'] and (p['entry_index']!=D or raw['participation_state']!='filled'):raise ValueError('filled_D_clock')
    known=raw['label_known_date'];phase=raw['label_known_phase']
    if bool(known)!=bool(phase) or known and (phase!=PHASE or known>END):raise ValueError('label_known_clock')
    if raw['label_state']=='closed_complete_bar_model':
        if not p['filled'] or p['exit_index'] is None or p['exit_index']<p['entry_index'] or known!=raw['exit_date']:
            raise ValueError('closed_terminal_clock')
    elif p['exit_index'] is not None or known:raise ValueError('nonclosed_terminal_clock')
    return p


def mature_for(p,cutoff):
    return bool(p['u_action_eligible']==1 and p['label_state']=='closed_complete_bar_model'
      and p['u_date']<cutoff and p['label_known_date'] and p['label_known_date']<cutoff)


def in_training_family(scope,group):
    if scope=='main':return True
    if scope not in SCOPES:raise ValueError('unknown_scope')
    return group!=int(scope[-1])


def path_interval(p,calendar):
    """Necessary before-terminal-day candidate opportunities, not actionable proof.

    A close t may request next-source-open t+1 only when t>=entry,
    t+1<original terminal x and t+1<K. Equality with x is separately ambiguous.
    K uses the unmodified Stage156 nominal calendar contract.
    """
    if p['label_state']!='closed_complete_bar_model':return None
    e,x=p['entry_index'],p['exit_index']
    b=calendar_boundary(p['reference_epoch'],calendar,END)
    if b['K_state']=='before_calendar_blocked':gate=False;k_limit=0
    elif b['K_index'] is None:
        gate=calendar[e]<b['K_target_date']
        # This is only a bound on observed indices, never an invented future K.
        k_limit=bisect.bisect_left(calendar,b['K_target_date'])
    else:gate=e<b['K_index'];k_limit=b['K_index']
    strict_end=min(x-2,k_limit-2) if gate else e-1
    count=max(0,strict_end-e+1)
    ambiguous=int(gate and x-1>=e and x<k_limit)
    state=('K_entry_blocked' if not gate else 'strict_before_terminal_day_candidates' if count else
           'same_terminal_day_only_not_certified' if ambiguous else 'no_preterminal_close_opportunity')
    return dict(**b,entry_before_K=gate,strict_start=e if count else None,strict_end=strict_end if count else None,
      strict_start_date=calendar[e] if count else None,strict_end_date=calendar[strict_end] if count else None,
      strict_count=count,ambiguous_terminal_day_count=ambiguous,support_state=state,
      candidate_upper_not_execution_certified=True)


class UnionAccumulator:
    """Interval difference arrays retain overlap rather than expand action-day rows."""
    def __init__(self,calendar):
        self.calendar=calendar;self.source_diff=np.zeros(len(calendar)+1,dtype=np.int64)
        self.family_diff={};self.age_diff=Counter();self.rows=0;self.paths=0
    def add(self,family,start,end):
        if start is None or end is None or end<start:return
        if not 0<=start<=end<len(self.calendar):raise ValueError('interval_outside_calendar')
        if family not in self.family_diff:self.family_diff[family]=np.zeros(len(self.calendar)+1,dtype=np.int64)
        for diff in (self.source_diff,self.family_diff[family]):diff[start]+=1;diff[end+1]-=1
        count=end-start+1;self.rows+=count;self.paths+=1
        self.age_diff[0]+=1;self.age_diff[count]-=1
    def result(self):
        counts=np.cumsum(self.source_diff[:-1]);age=[];running=0
        for i in range(max(self.age_diff,default=0)):
            running+=self.age_diff[i];age.append(running)
        families={f:np.cumsum(d[:-1]) for f,d in self.family_diff.items()}
        return dict(opportunity_rows_upper=self.rows,paths_with_strict_prefix=self.paths,
          source_day_union=int(np.count_nonzero(counts)),family_day_union=sum(int(np.count_nonzero(v)) for v in families.values()),
          families_with_strict_prefix=len(families),source_day_max_overlap=int(counts.max()) if len(counts) else 0,
          first_source_date=self.calendar[int(np.flatnonzero(counts)[0])] if np.any(counts) else None,
          last_source_date=self.calendar[int(np.flatnonzero(counts)[-1])] if np.any(counts) else None,age_counts=age)
    def family_year_rows(self):
        years=sorted(set(d[:4] for d in self.calendar))
        for family,diff in sorted(self.family_diff.items()):
            n=np.cumsum(diff[:-1])
            for year in years:
                lo=bisect.bisect_left(self.calendar,year+'-01-01');hi=bisect.bisect_left(self.calendar,str(int(year)+1)+'-01-01')
                part=n[lo:hi]
                if np.any(part):yield dict(family_id=family,decision_year=year,opportunity_rows_upper=int(part.sum()),
                  family_day_union=int(np.count_nonzero(part)),max_overlap=int(part.max()))


def bind(path):
    p=Path(path);return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def small_json(binding):
    if binding['bytes']>2_000_000:raise ValueError('small_json_cap')
    if bind(binding['path'])!={k:binding[k] for k in ('path','bytes','sha256')}:raise ValueError('small_binding_changed')
    return json.loads(Path(binding['path']).read_text())


def stat_only(binding):
    p=Path(binding['path']);st=p.stat()
    if st.st_size!=binding['bytes']:raise ValueError('accepted_input_size_changed')
    return dict(path=str(p.resolve()),bytes=st.st_size,mtime_ns=st.st_mtime_ns,sha256_inherited=binding['sha256'],full_rehash=False)


def json_write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def csv_write(path,rows,fields):
    with Path(path).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


class HashingReader:
    def __init__(self,stream):self.stream=stream;self.hash=hashlib.sha256();self.bytes=0
    def read(self,n=-1):
        data=self.stream.read(n);self.hash.update(data);self.bytes+=len(data);return data


def actual(protocol_path,protocol_sha,output):
    """One fresh run, no automatic retry. Stage504 schema finalized by root."""
    out=Path(output);out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    counters=dict(metadata_stream_attempted=0,metadata_stream_completed=0,metadata_rows=0,calendar_reads=0,
      original129_action_reads=0,old_mother_streams=0,numeric_Y_reads=0,price_reads=0,COMMON_reads=0,score_reads=0,
      cache_reads=0,SQL=0,API=0,download=0,fit=0,cash=0)
    status='failed';error=None;result={};artifacts={};current=None
    source_bundle=[bind(Path(__file__)),bind(Path(__file__).with_name('test_stage505_continuation_support.py')),
      bind(Path(__file__).with_name('stage156_voluntary_choices.py'))]
    pb=bind(protocol_path)
    json_write(out/'started.json',dict(status='started',time=datetime.now(timezone.utc).isoformat(),
      protocol=pb,source_bundle=source_bundle,automatic_restart=False,new_financial_budget=0))
    try:
        if pb['sha256']!=protocol_sha:raise ValueError('exact_root504_sha_required')
        protocol=json.loads(Path(protocol_path).read_text())
        if not protocol.get('root_authorized') or protocol.get('stage')!=504 or protocol.get('authorized_stage')!=505:
            raise ValueError('root504_authorization_required')
        budget=protocol['budget']
        if budget.get('metadata_streams')!=1 or budget.get('calendar_reads')!=1 or budget.get('fit')!=0 or budget.get('cash')!=0:
            raise ValueError('one_metadata_zero_financial_budget_required')
        if protocol['action_field_allowlist']!=FIELDS:raise ValueError('exact_metadata_allowlist_required')
        inputs=protocol['inputs'];before={k:stat_only(v) for k,v in inputs.items()}
        summary466=small_json(inputs['summary466']);manifest466=small_json(inputs['manifest466']);review467=small_json(inputs['review467'])
        if summary466['original_actions_preserved']!=1552456 or summary466['original_mothers_preserved']!=399252 or summary466['nochild_mothers']!=186400:
            raise ValueError('accepted_full_domain_anchors')
        if review467['status']!='completed' or review467['decision']!='PREFIX_STATE_CLOCK_SUPPORT_ACCEPTED_ONLY_MODEL_CASH_NOT_AUTHORIZED':
            raise ValueError('accepted467_required')
        if manifest466['artifacts']['action_metadata_state.csv.gz']!=inputs['metadata']:raise ValueError('accepted466_metadata_binding')
        cb=inputs['calendar'];raw=Path(cb['path']).read_bytes();counters['calendar_reads']+=1
        if len(raw)!=cb['bytes'] or hashlib.sha256(raw).hexdigest()!=cb['sha256']:raise ValueError('calendar_binding_changed')
        arr=np.load(io.BytesIO(raw),allow_pickle=False)
        calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in arr] if arr.dtype.kind in 'iu'
          else arr.astype('datetime64[D]').astype(str).tolist())
        if calendar!=sorted(set(calendar)) or END not in calendar:raise ValueError('complete_source_calendar_required')
        json_write(out/'source_acceptance_checkpoint.json',dict(inputs_before=before,calendar_rows=len(calendar),
          policy_domain_inherited=dict(mothers=399252,nochild_mothers=186400,products=98,families=95,exchanges=6),
          metadata_streams_started=0))
        accum={(c,s):UnionAccumulator(calendar) for c in CUTOFFS for s in SCOPES}
        mature_counts=Counter();entry_allowed=Counter();ambiguous=Counter();zero=Counter();states=defaultdict(Counter)
        raw_states=Counter();participation=Counter();products=set();families=set();epochs=set();seen_ids=set()
        last_mother=-1;child_products=Counter();table_rows=0
        counters['metadata_stream_attempted']=1
        with Path(inputs['metadata']['path']).open('rb') as base:
            hashed=HashingReader(base)
            with gzip.GzipFile(fileobj=hashed,mode='rb') as gz,io.TextIOWrapper(gz,newline='') as text, gzip.open(out/'mature_pre2023_intervals.csv.gz','xt',newline='',compresslevel=3) as target:
                reader=csv.reader(text);header=next(reader);indices=[header.index(k) for k in FIELDS]
                if len(set(header))!=len(header):raise ValueError('duplicate_physical_header')
                writer=csv.DictWriter(target,fieldnames=INTERVAL_FIELDS);writer.writeheader()
                for cells in reader:
                    current={k:cells[i] for k,i in zip(FIELDS,indices)}
                    p=parse_metadata(current,calendar);seq=p['sequence_index'];mi=p['mother_sequence_index']
                    if seq!=counters['metadata_rows'] or not 0<=mi<399252 or mi<last_mother:raise ValueError('full_action_sequence_mother_order')
                    if p['action_id'] in seen_ids:raise ValueError('duplicate_action_id')
                    seen_ids.add(p['action_id']);last_mother=mi
                    counters['metadata_rows']+=1;raw_states[p['label_state']]+=1;participation[p['participation_state']]+=1
                    products.add(p['product_id']);families.add(p['family_id']);epochs.add(p['reference_epoch']);child_products[p['product_id']]+=1
                    for cutoff in CUTOFFS:
                        state=p['c'+cutoff[:4]+'_state'];states[cutoff][state]+=1
                    if not mature_for(p,'2023-01-01'):continue
                    interval=path_interval(p,calendar);writer.writerow(dict(current,**interval));table_rows+=1
                    for cutoff in CUTOFFS:
                        if not mature_for(p,cutoff):continue
                        for scope in SCOPES:
                            if not in_training_family(scope,p['family_hash_group']):continue
                            key=(cutoff,scope);mature_counts[key]+=1;entry_allowed[key]+=interval['entry_before_K']
                            ambiguous[key]+=interval['ambiguous_terminal_day_count'];zero[(cutoff,scope,interval['support_state'])]+=1
                            accum[key].add(p['family_id'],interval['strict_start'],interval['strict_end'])
        counters['metadata_stream_completed']=1
        metadata_sha=hashed.hash.hexdigest()
        if hashed.bytes!=inputs['metadata']['bytes'] or metadata_sha!=inputs['metadata']['sha256']:raise ValueError('metadata_one_stream_sha_changed')
        if counters['metadata_rows']!=1552456 or len(products)!=97 or len(families)!=94:raise ValueError('full_child_domain_conservation')
        if dict(raw_states)!=summary466['raw_final_label_state_counts'] or dict(participation)!=summary466['raw_participation_state_counts']:
            raise ValueError('source_state_conservation')
        if {c:dict(states[c]) for c in CUTOFFS}!=summary466['full_action_asof_state_counts']:raise ValueError('cutoff_state_conservation')
        if table_rows!=445475 or mature_counts[('2020-01-01','main')]!=247795:raise ValueError('pre_K_mature_anchor')
        json_write(out/'metadata_phase_checkpoint.json',dict(counters=counters,metadata_compressed_bytes=hashed.bytes,
          metadata_compressed_sha256=metadata_sha,source_physical_header=header,selected_fields=FIELDS,
          raw_final_label_state_counts=dict(raw_states),raw_participation_state_counts=dict(participation),
          full_action_asof_state_counts={c:dict(states[c]) for c in CUTOFFS},mature_interval_rows=table_rows))
        folds=[];ages=[];coverage=[]
        for (cutoff,scope),a in accum.items():
            r=a.result();age_counts=r.pop('age_counts');key=(cutoff,scope)
            support=bool(r['opportunity_rows_upper']>0 and r['source_day_union']>0 and r['families_with_strict_prefix']>0)
            folds.append(dict(cutoff=cutoff,scope=scope,mature_original_eligible_pre_K=mature_counts[key],
              entry_before_K=entry_allowed[key],entry_K_blocked=mature_counts[key]-entry_allowed[key],
              ambiguous_terminal_day_upper_not_certified=ambiguous[key],**r,minimum_source_support=support,
              training_scope_note='family hash complement, not forward held subset'))
            ages.extend(dict(cutoff=cutoff,scope=scope,age_since_entry_zero_based=i,holding_source_day=i+1,
              candidate_close_count_upper=n) for i,n in enumerate(age_counts))
            coverage.extend(dict(cutoff=cutoff,scope=scope,**row) for row in a.family_year_rows())
        csv_write(out/'six_fold_support.csv',folds,list(folds[0]))
        csv_write(out/'exact_age_upper.csv',ages,['cutoff','scope','age_since_entry_zero_based','holding_source_day','candidate_close_count_upper'])
        csv_write(out/'family_year_support.csv',coverage,['cutoff','scope','family_id','decision_year','opportunity_rows_upper','family_day_union','max_overlap'])
        result=dict(status='completed',decision=('CLOCK_CANDIDATE_SUPPORT_EXISTS_NOT_EXECUTION_OR_PAYOFF_PROOF' if all(r['minimum_source_support'] for r in folds) else 'STOP_NO_ALL_FOLD_CLOCK_SUPPORT'),
          original_actions_preserved=1552456,original_mothers_preserved=399252,nochild_mothers_preserved=186400,
          policy_products=98,policy_families=95,policy_exchanges=6,observed_child_products=len(products),observed_child_families=len(families),
          source_calendar_rows=len(calendar),mature_pre2023_interval_rows=table_rows,six_fold_support=folds,
          support_state_counts=[dict(cutoff=c,scope=s,support_state=z,paths=n) for (c,s,z),n in sorted(zero.items())],
          scope_limits=['Intervals are necessary before-terminal-day candidates, not fully validated native executable opportunities.',
            'No terminal exit_reason is read; same-terminal-day next opens remain ambiguous and are excluded from strict support.',
            'Original known forced-open states and native price availability need a later separately authorized state reconstruction.',
            'Closed mature source support does not identify early-exit advantage, independent sample size, alpha, profitability or statistical adequacy.',
            '98/95 policy mother domain is inherited accepted466/467 provenance; action payload naturally has 97/94 children.'],
          new_labels=0,new_models_authorized=False,new_cash_authorized=False,production_qualified=False,goal_complete=False,
          before_after_stat_equal=before=={k:stat_only(v) for k,v in inputs.items()})
        if not result['before_after_stat_equal']:raise ValueError('source_stat_changed_during_run')
        json_write(out/'summary.json',result);status='completed'
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),last_sequence=current.get('sequence_index') if current else None)
        json_write(out/'failure.json',error)
    finally:
        terminal=dict(status=status,elapsed_seconds=time.monotonic()-started,counters=counters,error=error,
          automatic_restart=False,new_fit=0,new_cash=0)
        json_write(out/'terminal.json',terminal)
        for p in sorted(out.iterdir()):
            if p.is_file():artifacts[p.name]=bind(p)
        json_write(out/'manifest.json',dict(schema='stage505_continuation_support_manifest_v1',status=status,
          protocol=pb,source_bundle=source_bundle,artifacts=artifacts,counters=counters,automatic_restart=False,
          new_model_authorized=False,new_cash_authorized=False))
        print(json.dumps(terminal,ensure_ascii=False,allow_nan=False))
    return 0 if status=='completed' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['actual'])
    p.add_argument('--protocol',required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();return actual(a.protocol,a.protocol_sha256,a.output)

if __name__=='__main__':raise SystemExit(main())
