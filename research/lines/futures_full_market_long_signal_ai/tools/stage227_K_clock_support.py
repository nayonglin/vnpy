"""Frozen226 full-action metadata clock probe, never a label/model/cash builder.

Only root's exact authorization starts the single original-data stream. Imports
and tiny fixture helpers have no data I/O. Original Y/X columns are never selected
or numerically parsed; accepted large SHA identities are inherited, not rehashed.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
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
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE/'outputs/stage226_K_clock_support_protocol/protocol.json'
PROTOCOL_SHA = 'ccaf36d3a5233cb826f86f012009ad4f5d30b45a210cb3eac09ff01b869a0a3f'
OUTPUT = LINE/'outputs/stage227_K_clock_support/actual_run1'
ACTIONS = ['sequence_index','action_sequence_index','action_id','mother_sequence_index','mother_event_id',
           'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
           'D_index','label_history_ready20','participation_state','label_state','filled','trade_label_known',
           'entry_index','entry_date','exit_index','exit_date','unknown_index','unknown_date','label_known_date',
           'label_known_phase','participation_known_date','participation_known_phase','last_path_index','cancel_reason']
MOTHERS = ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
CALENDAR_STATES = ('blocked_beforecalendar','unknown_D_sentinel','allowed_D_before_K',
                   'blocked_D_on_or_after_K','allowed_aftercalendar_D_before_target',
                   'blocked_aftercalendar_D_on_or_after_target')
TIMING_STATES = ('known_nonparticipation','not_history_ready','intent_right_censored','closed_before_K',
                 'closed_on_K_priority_reprice','closed_after_K','unknown_before_K','unknown_on_K',
                 'unknown_after_K','unknown_unclassified','open_K_reached','open_K_pending',
                 'K_before_calendar_unavailable')
LABEL_STATES = ('closed_complete_bar_model','entry_execution_unknown','intent_right_censored',
                'known_nonparticipation','not_history_ready','open_right_censored',
                'path_or_execution_unknown','input_or_economics_unresolved')
POTENTIAL = {'closed_on_K_priority_reprice','closed_after_K','unknown_after_K','open_K_reached'}
UNRESOLVED = {'unknown_before_K','unknown_on_K','unknown_unclassified','open_K_pending',
              'intent_right_censored','not_history_ready','K_before_calendar_unavailable'}
DERIVED = ['D_date','D_state','K_target_date','K_index','K_date','K_state','K_after_sample_end',
           'calendar_allowed','calendar_state','primary_domain','path_state','timing_state',
           'potential_clock_or_repricing_support','known_zero_exposure_before_K',
           'unresolved_clock_obscures_no_effect']
BASE_METRICS = ['action_count','u_eligible_count','calendar_allowed_count','calendar_unknown_count',
                'calendar_unknown_u_eligible_count','primary_domain_count','potential_support_count',
                'unresolved_primary_count','known_zero_exposure_primary_count','primary_resolved_before_K_count',
                'mother_count','nochild_mother_count','primary_domain_mother_count','potential_support_mother_count']
METRICS = BASE_METRICS + ['calendar_'+s+'_count' for s in CALENDAR_STATES] + [
    'timing_'+s+'_count' for s in TIMING_STATES] + ['primary_timing_'+s+'_count' for s in TIMING_STATES] + [
    'label_'+s+'_count' for s in LABEL_STATES]
MOTHER_COUNTS = ['child_count','u_eligible_child_count','calendar_allowed_child_count','calendar_unknown_child_count',
                 'primary_domain_child_count','potential_support_child_count','unresolved_primary_child_count',
                 'known_zero_exposure_primary_child_count','primary_resolved_before_K_child_count'] + [
    'timing_'+s+'_child_count' for s in TIMING_STATES] + ['primary_timing_'+s+'_child_count' for s in TIMING_STATES]
_GATE = None


def binding(path):
    p = Path(path).resolve(); digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):
            digest.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=digest.hexdigest())


def read_bound(bound):
    raw = Path(bound['path']).read_bytes()
    if len(raw)!=bound['bytes'] or hashlib.sha256(raw).hexdigest()!=bound['sha256']:
        raise ValueError('small_binding_changed '+bound['path'])
    return raw


def write_json(path, value):
    with Path(path).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n'); stream.flush()


def source_bundle():
    return sorted([binding(TOOLS/name) for name in ('stage227_K_clock_support.py',
        'test_stage227_K_clock_support.py','stage156_voluntary_choices.py')],key=lambda b:b['path'])


def source_stat(bound):
    p = Path(bound['path']); stat = p.stat()
    if not p.is_file() or stat.st_size!=bound['bytes']:
        raise ValueError('accepted_input_size_changed '+str(p))
    return dict(path=str(p.resolve()),bytes=stat.st_size,device=stat.st_dev,inode=stat.st_ino,
                mtime_ns=stat.st_mtime_ns,inherited_sha256=bound['sha256'],rehashed=False)


def integer(value):
    if isinstance(value,bool):
        raise ValueError('bool_not_integer_identity')
    number = float(value)
    if not math.isfinite(number) or not number.is_integer() or abs(number)>2**53:
        raise ValueError('invalid_integer_identity '+str(value))
    return int(number)


def gate_helper():
    global _GATE
    if _GATE is None:
        spec = importlib.util.spec_from_file_location('accepted156_for227',TOOLS/'stage156_voluntary_choices.py')
        _GATE = importlib.util.module_from_spec(spec); spec.loader.exec_module(_GATE)
    return _GATE


def action_gate(u, epoch, calendar, sample_end, boundary=None):
    """The pure156 calendar part in its original priority order; no score gate."""
    u = integer(u)
    if not 0<=u<len(calendar):
        raise ValueError('source_u_index_outside_calendar')
    b = gate_helper().calendar_boundary(epoch,calendar,sample_end) if boundary is None else boundary
    D = u+1; day = calendar[D] if D<len(calendar) else None
    if b['K_state']=='before_calendar_blocked':
        allowed,state = 0,'blocked_beforecalendar'
    elif day is None:
        allowed,state = None,'unknown_D_sentinel'
    elif b['K_index'] is None:
        allowed = int(day<b['K_target_date'])
        state = 'allowed_aftercalendar_D_before_target' if allowed else 'blocked_aftercalendar_D_on_or_after_target'
    else:
        allowed = int(D<b['K_index'])
        state = 'allowed_D_before_K' if allowed else 'blocked_D_on_or_after_K'
    return dict(D_date=day,D_state='unknown_D_sentinel' if day is None else
                'after_sample_end' if day>sample_end else 'in_sample_calendar',
                **b,calendar_allowed=allowed,calendar_state=state)


def clock(raw, name, calendar):
    """Missing stays missing; a one-sided or inconsistent date/index stops."""
    index,day = raw[name+'_index'],raw[name+'_date']
    if not index and not day:
        return None
    if not index or not day:
        raise ValueError('one_sided_clock '+name)
    index = integer(index)
    if not 0<=index<len(calendar) or day!=calendar[index]:
        raise ValueError('clock_date_index_mismatch '+name)
    return index


def classify_action(raw, calendar, sample_end, boundary=None, calendar_days=None):
    if set(raw)!=set(ACTIONS):
        raise ValueError('exact_metadata_allowlist_required')
    u = integer(raw['u_index']); D = integer(raw['D_index'])
    if not 0<=u<len(calendar) or calendar[u]!=raw['u_date'] or D!=u+1:
        raise ValueError('source_u_D_calendar_mismatch')
    if raw['reference_epoch'].rsplit('.',1)[0]!=raw['product_id'] or raw['family_id']!=raw['product_id'].removesuffix('_F'):
        raise ValueError('action_product_family_epoch_mismatch')
    flags = {k:integer(raw[k]) for k in ('u_action_eligible','label_history_ready20','filled','trade_label_known')}
    if any(v not in (0,1) for v in flags.values()):
        raise ValueError('nonbinary_source_flag')
    state = raw['label_state']
    if state not in LABEL_STATES or not raw['participation_state']:
        raise ValueError('unaccounted_original_state '+state)
    entry,exit_,unknown = (clock(raw,name,calendar) for name in ('entry','exit','unknown'))
    if entry is not None and entry!=D:
        raise ValueError('entry_clock_differs_from_D')
    if exit_ is not None and (entry is None or exit_<entry):
        raise ValueError('exit_precedes_entry_clock')
    if unknown is not None and unknown<D:
        raise ValueError('first_unknown_precedes_D')
    if raw['last_path_index']:
        last = integer(raw['last_path_index'])
        if not D<=last<len(calendar) or calendar[last]>sample_end:
            raise ValueError('last_path_clock_outside_observed_path')
    if bool(entry is not None)!=bool(flags['filled']):
        raise ValueError('filled_entry_clock_mismatch')
    if state=='closed_complete_bar_model':
        if exit_ is None or not flags['trade_label_known'] or unknown is not None:
            raise ValueError('closed_state_missing_or_conflicting_clock')
        if raw['label_known_date']!=raw['exit_date']:
            raise ValueError('closed_known_date_exit_mismatch')
    elif exit_ is not None or flags['trade_label_known']:
        raise ValueError('nonclosed_state_has_closed_clock')
    calendar_days = set(calendar) if calendar_days is None else calendar_days
    for field in ('label_known_date','participation_known_date'):
        if raw[field] and (raw[field] not in calendar_days or raw[field]>sample_end):
            raise ValueError('known_clock_outside_sample '+field)
    gate = action_gate(u,raw['reference_epoch'],calendar,sample_end,boundary)
    if state in ('known_nonparticipation','not_history_ready','intent_right_censored'):
        timing = state
    elif gate['K_state']=='before_calendar_blocked':
        timing = 'K_before_calendar_unavailable'
    elif state=='closed_complete_bar_model':
        K = gate['K_index']
        timing = ('closed_before_K' if K is None or exit_<K else
                  'closed_on_K_priority_reprice' if exit_==K else 'closed_after_K')
    elif state=='open_right_censored':
        timing = 'open_K_pending' if gate['K_index'] is None or gate['K_after_sample_end'] else 'open_K_reached'
    elif unknown is None:
        timing = 'unknown_unclassified'
    else:
        K = gate['K_index']
        timing = 'unknown_before_K' if K is None or unknown<K else 'unknown_on_K' if unknown==K else 'unknown_after_K'
    if exit_ is not None and raw['exit_date']>sample_end or unknown is not None and raw['unknown_date']>sample_end:
        raise ValueError('observed_exit_or_unknown_after_sample_end')
    primary = int(flags['u_action_eligible']==1 and gate['calendar_allowed']==1)
    gate['K_after_sample_end'] = int(gate['K_after_sample_end'])
    return dict(**gate,primary_domain=primary,path_state=state,timing_state=timing,
                potential_clock_or_repricing_support=int(primary and timing in POTENTIAL),
                known_zero_exposure_before_K=int(timing=='known_nonparticipation'),
                unresolved_clock_obscures_no_effect=int(timing in UNRESOLVED))


def probe_metadata(mothers, actions, calendar, sample_end, expected_actions, action_sink, mother_sink):
    """One streaming action pass; compact columnar mothers and int32 child counts."""
    if not calendar or calendar!=sorted(set(calendar)) or sample_end not in calendar:
        raise ValueError('unique_source_calendar_and_sample_end_required')
    frame = mothers.copy() if isinstance(mothers,pd.DataFrame) else pd.DataFrame(mothers,columns=MOTHERS)
    if set(frame.columns)!=set(MOTHERS) or frame.empty:
        raise ValueError('exact_complete_mother_metadata_required')
    frame = frame.loc[:,MOTHERS]
    for k in ('sequence_index','u_index'):
        frame[k] = frame[k].map(integer).astype('int32')
    if not np.array_equal(frame.sequence_index.to_numpy(),np.arange(len(frame))) or not frame.event_id.is_unique:
        raise ValueError('mother_sequence_or_identity_not_unique_contiguous')
    u = frame.u_index.to_numpy()
    if (u<0).any() or (u>=len(calendar)).any() or not np.array_equal(frame.u_date.to_numpy(),np.asarray(calendar)[u]):
        raise ValueError('mother_source_calendar_mismatch')
    nonempty_anchor = frame.reference_epoch.ne('')
    if (not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all() or
            not frame.loc[nonempty_anchor,'reference_epoch'].str.rsplit('.',n=1).str[0].eq(frame.loc[nonempty_anchor,'product_id']).all()):
        raise ValueError('mother_product_family_epoch_mismatch')
    # The high-cardinality event id remains one column; no million-row dict cache.
    for k in ('product_id','family_id','u_date','reference_epoch'):
        frame[k] = frame[k].astype('category')
    columns = {k:frame[k].to_numpy() for k in MOTHERS}
    fixed = dict(year=[str(y) for y in range(int(min(columns['u_date'])[:4]),int(sample_end[:4])+1)],
                 family=sorted(frame.family_id.unique().tolist()),product=sorted(frame.product_id.unique().tolist()))
    accum = defaultdict(Counter); parent_counts = np.zeros((len(frame),len(MOTHER_COUNTS)),dtype=np.int32)
    count_pos = {k:i for i,k in enumerate(MOTHER_COUNTS)}
    boundary_cache = {}; labels = Counter(); participations = Counter(); calendar_days = set(calendar)
    count = min(16,expected_actions)
    positions = [i*(expected_actions-1)//(count-1) for i in range(count)] if count>1 else [0] if count else []
    anchor_set = set(positions); anchors = []; rows = 0
    def keys(product,family,day):
        for scope in ('all','2020onward') if day>='2020-01-01' else ('all',):
            yield (scope,'global','all')
            yield (scope,'year',day[:4]); yield (scope,'family',family); yield (scope,'product',product)
    for raw in actions:
        seq = integer(raw['sequence_index']); parent = integer(raw['mother_sequence_index'])
        if seq!=rows or integer(raw['action_sequence_index'])!=seq or not raw['action_id'] or not 0<=parent<len(frame):
            raise ValueError('action_sequence_or_parent_mismatch '+str(rows))
        if (raw['mother_event_id']!=columns['event_id'][parent] or raw['anchor_epoch']!=columns['reference_epoch'][parent]
                or integer(raw['u_index'])!=int(columns['u_index'][parent]) or any(raw[k]!=columns[k][parent]
                  for k in ('product_id','family_id','u_date'))):
            raise ValueError('action_mother_identity_mismatch '+str(rows))
        epoch = raw['reference_epoch']
        if epoch not in boundary_cache:
            boundary_cache[epoch] = gate_helper().calendar_boundary(epoch,calendar,sample_end)
        derived = classify_action(raw,calendar,sample_end,boundary_cache[epoch],calendar_days); projected = dict(raw,**derived)
        action_sink(projected)
        if seq in anchor_set:
            anchors.append(projected)
        primary = derived['primary_domain']; timing = derived['timing_state']; allowed = derived['calendar_allowed']
        eligible = integer(raw['u_action_eligible']); potential = derived['potential_clock_or_repricing_support']
        unresolved = int(primary and derived['unresolved_clock_obscures_no_effect'])
        zero = int(primary and derived['known_zero_exposure_before_K'])
        resolved = int(primary and timing in ('closed_before_K','known_nonparticipation'))
        metrics = dict(action_count=1,u_eligible_count=eligible,calendar_allowed_count=int(allowed==1),
                       calendar_unknown_count=int(allowed is None),calendar_unknown_u_eligible_count=int(allowed is None and eligible),
                       primary_domain_count=primary,potential_support_count=potential,unresolved_primary_count=unresolved,
                       known_zero_exposure_primary_count=zero,primary_resolved_before_K_count=resolved)
        metrics.update({'calendar_'+derived['calendar_state']+'_count':1,'timing_'+timing+'_count':1,
                        'primary_timing_'+timing+'_count':primary,'label_'+raw['label_state']+'_count':1})
        for key in keys(raw['product_id'],raw['family_id'],raw['u_date']):
            accum[key].update(metrics)
        values = [1,eligible,int(allowed==1),int(allowed is None),primary,potential,unresolved,zero,resolved]
        parent_counts[parent,:9] += values
        parent_counts[parent,count_pos['timing_'+timing+'_child_count']] += 1
        parent_counts[parent,count_pos['primary_timing_'+timing+'_child_count']] += primary
        labels[raw['label_state']] += 1; participations[raw['participation_state']] += 1
        rows += 1
        if rows>expected_actions:
            raise ValueError('extra_action_rows')
        if rows%250000==0:
            print(json.dumps(dict(phase='metadata_actions_projected',rows=rows)),flush=True)
    if rows!=expected_actions:
        raise ValueError('incomplete_action_domain '+str(rows))
    for parent in range(len(frame)):
        counts = {k:int(v) for k,v in zip(MOTHER_COUNTS,parent_counts[parent])}
        if (sum(counts['timing_'+s+'_child_count'] for s in TIMING_STATES)!=counts['child_count'] or
                sum(counts['primary_timing_'+s+'_child_count'] for s in TIMING_STATES)!=counts['primary_domain_child_count']):
            raise ValueError('mother_timing_partition_failed')
        identity = {k:int(columns[k][parent]) if k in ('sequence_index','u_index') else columns[k][parent] for k in MOTHERS}
        nochild = int(counts['child_count']==0)
        mother_sink(dict(identity,**counts,nochild=nochild))
        mother_metrics = dict(mother_count=1,nochild_mother_count=nochild,
            primary_domain_mother_count=int(counts['primary_domain_child_count']>0),
            potential_support_mother_count=int(counts['potential_support_child_count']>0))
        for key in keys(identity['product_id'],identity['family_id'],identity['u_date']):
            accum[key].update(mother_metrics)
    scopes = {s:{m:int(accum[(s,'global','all')][m]) for m in METRICS} for s in ('all','2020onward')}
    partitions = {dim:[dict(scope=s,group=g,**{m:int(accum[(s,dim,g)][m]) for m in METRICS})
        for s in ('all','2020onward') for g in groups] for dim,groups in fixed.items()}
    for scope,overall in scopes.items():
        if (sum(overall['timing_'+s+'_count'] for s in TIMING_STATES)!=overall['action_count'] or
                sum(overall['calendar_'+s+'_count'] for s in CALENDAR_STATES)!=overall['action_count'] or
                sum(overall['label_'+s+'_count'] for s in LABEL_STATES)!=overall['action_count'] or
                sum(overall['primary_timing_'+s+'_count'] for s in TIMING_STATES)!=overall['primary_domain_count']):
            raise ValueError('global_action_partition_failed '+scope)
        for dimension,entries in partitions.items():
            if any(sum(r[m] for r in entries if r['scope']==scope)!=overall[m] for m in METRICS):
                raise ValueError('fixed_group_conservation_failed '+scope+'/'+dimension)
    return dict(scopes=scopes,fixed_partitions=fixed,partitions=partitions,metric_columns=METRICS,
                anchor_positions=positions,anchors=anchors,label_state_counts=dict(labels),
                participation_state_counts=dict(participations),all_action_ids_preserved=True,
                original_action_id_uniqueness_inherited_from_accepted129=True,action_id_recomputed=False,
                complete_contiguous_action_sequences=True,complete_contiguous_mother_sequences=True)


def authorization(args):
    output = Path(args.output).resolve()
    if output!=OUTPUT or output.exists():
        raise ValueError('fresh_exact_stage227_actual_run1_required')
    pb = binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:
        raise ValueError('frozen226_changed')
    protocol = json.loads(read_bound(pb)); ab = binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:
        raise ValueError('root_authorization_sha_changed')
    auth = json.loads(read_bound(ab))
    required = dict(schema='stage226_exact_root_clock_authorization_v1',authorized_by='root',
                    stage='K_clock_support_probe',exact_source_authorized=True,
                    protocol_sha256=PROTOCOL_SHA,output=str(output))
    if (any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle() or
            auth.get('input_bindings')!=protocol['input_bindings'] or auth.get('actions_usecols')!=ACTIONS or
            auth.get('mothers_usecols')!=MOTHERS or protocol['actions_usecols']!=ACTIONS or protocol['mothers_usecols']!=MOTHERS):
        raise ValueError('exact_root_authorization_differs')
    return output,protocol,ab,pb


def projected_rows(path, fields):
    """Decode the physical CSV once, retaining only the permitted metadata cells."""
    with gzip.open(path,'rt',encoding='utf8',newline='') as stream:
        reader = csv.reader(stream); header = next(reader)
        if len(header)!=len(set(header)) or any(k not in header for k in fields):
            raise ValueError('source_metadata_header_invalid')
        indexes = [header.index(k) for k in fields]
        for cells in reader:
            if len(cells)!=len(header):
                raise ValueError('malformed_physical_csv_row')
            yield {k:cells[i] for k,i in zip(fields,indexes)}


def run_actual(output, protocol, auth_binding, protocol_binding):
    output = Path(output); output.mkdir(parents=True,exist_ok=False); started = time.monotonic()
    source = source_bundle(); inputs = protocol['input_bindings']; artifacts = {}; before = {}; after = {}
    counters = dict(actions_single_stream_reads_attempted=0,actions_single_stream_reads_completed=0,
        mothers_reads_attempted=0,mothers_reads_completed=0,calendar_reads=0,Y_numeric_reads=0,X_reads=0,
        old_score_prediction_selection_reads=0,old_training_cache_reads=0,prices_or_native_cache_reads=0,
        SQL=0,download=0,large_input_hashes=0,new_label=0,fit=0,cash=0)
    def save(name,value):
        write_json(output/name,value); artifacts[name] = binding(output/name); return artifacts[name]
    save('started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),
         protocol=protocol_binding,authorization=auth_binding,source_bundle=source,automatic_retry=False))
    try:
        dataset = json.loads(read_bound(inputs['accepted_dataset_manifest']))
        if (dataset['status']!='completed' or dataset['action_rows']!=protocol['expected_actions'] or
                dataset['mother_rows']!=protocol['expected_mothers'] or
                any(dataset[k]!=inputs[k] for k in ('actions','mothers')) or
                dataset['input_bindings']['calendar']!=inputs['calendar']):
            raise ValueError('accepted129_domain_binding_changed')
        for key in ('calendar_gate_source','independent_design225','triage222'):
            read_bound(inputs[key])
        before = {k:source_stat(inputs[k]) for k in ('actions','mothers','calendar')}
        counters['calendar_reads'] += 1
        array = np.load(io.BytesIO(read_bound(inputs['calendar'])),allow_pickle=False)
        calendar = ([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in array]
            if array.dtype.kind in 'iu' else array.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=5587:
            raise ValueError('accepted_calendar_length_changed')
        counters['mothers_reads_attempted'] += 1
        mothers = pd.read_csv(inputs['mothers']['path'],usecols=MOTHERS,dtype=str,keep_default_na=False)
        counters['mothers_reads_completed'] += 1
        if len(mothers)!=protocol['expected_mothers']:
            raise ValueError('accepted_mother_count_changed')
        counters['actions_single_stream_reads_attempted'] += 1
        with gzip.open(output/'action_projection.csv.gz','xt',encoding='utf8',newline='') as astream, \
                gzip.open(output/'mother_projection.csv.gz','xt',encoding='utf8',newline='') as mstream:
            awriter = csv.DictWriter(astream,fieldnames=ACTIONS+DERIVED); awriter.writeheader()
            mwriter = csv.DictWriter(mstream,fieldnames=MOTHERS+MOTHER_COUNTS+['nochild']); mwriter.writeheader()
            result = probe_metadata(mothers,projected_rows(inputs['actions']['path'],ACTIONS),calendar,
                protocol['sample_end'],protocol['expected_actions'],awriter.writerow,mwriter.writerow)
        counters['actions_single_stream_reads_completed'] += 1
        if (result['label_state_counts']!=dataset['counts']['label_states'] or
                result['scopes']['all']['nochild_mother_count']!=dataset['counts']['mother_rows_without_children']):
            raise ValueError('accepted_raw_state_or_nochild_partition_changed')
        after = {k:source_stat(inputs[k]) for k in ('actions','mothers','calendar')}
        if before!=after or source!=source_bundle():
            raise ValueError('source_changed_during_actual')
        for name in ('action_projection.csv.gz','mother_projection.csv.gz'):
            artifacts[name] = binding(output/name)
        roles = dict(actions_projection=artifacts['action_projection.csv.gz'],mothers_projection=artifacts['mother_projection.csv.gz'])
        for dimension,rows in result.pop('partitions').items():
            name = 'by_'+dimension+'.csv'
            with (output/name).open('x',newline='',encoding='utf8') as stream:
                writer = csv.DictWriter(stream,fieldnames=['scope','group']+METRICS);writer.writeheader();writer.writerows(rows)
            roles['by_'+dimension] = artifacts[name] = binding(output/name)
        anchors = result.pop('anchors'); positions = result.pop('anchor_positions')
        roles['anchors'] = save('anchors.json',dict(policy='at most16 equally spaced complete original sequence positions',
            positions=positions,total_actions=protocol['expected_actions'],anchors=anchors,not_outcome_selected=True))
        overall = result['scopes']['all']; primary = overall['primary_domain_count']
        no_effect = bool(primary and overall['primary_resolved_before_K_count']==primary and
                         not overall['calendar_unknown_u_eligible_count'])
        roles['interpretation_gate'] = save('interpretation_gate.json',dict(
            status='stop_fixed_target_axis_no_clock_support' if no_effect else 'potential_or_unresolved_support_only',
            primary_domain_actions=primary,potential_support_actions=overall['potential_support_count'],
            unresolved_primary_actions=overall['unresolved_primary_count'],
            calendar_unknown_u_eligible_actions=overall['calendar_unknown_u_eligible_count'],
            all_primary_paths_resolved_before_K=bool(primary and overall['primary_resolved_before_K_count']==primary),
            no_effect_necessary_condition_met=no_effect,automatic_Y_K_authorized=False,fit_authorized=False,cash_authorized=False,
            interpretation='Only original clocks and repricing candidates; no price availability, Y difference, earlier maturity, predictability or alpha inferred.'))
        roles['source_read_receipt'] = save('source_read_receipt.json',dict(before=before,after=after,
            actions_usecols=ACTIONS,mothers_usecols=MOTHERS,counters=counters,accepted_large_SHA_inherited=True,
            numeric_Y_X_parsed=False,original_action_ids_not_rehashed=True,source_streams_reopened=False))
        roles['summary'] = save('summary.json',dict(schema='stage227_K_clock_support_summary_v1',status='completed',
            **result,counters=counters,cumulative_fit=433,cumulative_cash=234,goal_complete=False,
            automatic_training_authorized=False,production_qualified=False,increased_betting_qualified=False))
        terminal = save('terminal.json',dict(status='completed',exit_code=0,counters=counters,
            elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        manifest = dict(schema='stage227_K_clock_support_manifest_v1',status='completed',protocol=protocol_binding,
            protocol_sha256=PROTOCOL_SHA,authorization=auth_binding,source_bundle=source,input_bindings=inputs,
            artifacts=artifacts,terminal=terminal,counters=counters,**{k:v for k,v in roles.items() if k!='terminal'},
            cumulative_fit=433,cumulative_cash=234,goal_complete=False,financial_authorization=False,
            dependencies=dict(python=__import__('sys').version,numpy=np.__version__,pandas=pd.__version__))
        write_json(output/'manifest.json',manifest)
        return manifest
    except BaseException as error:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json',dict(status='failed',exit_code=1,counters=counters,before=before,after=after,
                error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual',action='store_true',required=True)
    parser.add_argument('--authorization',required=True);parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args = parser.parse_args(argv)
    out,protocol,ab,pb = authorization(args)
    result = run_actual(out,protocol,ab,pb)
    print(json.dumps(dict(status=result['status'],counters=result['counters'],output=str(out))),flush=True)


if __name__=='__main__':
    main()
