"""Frozen230 K single-action payoff; root-only actual, no fit/cash/path replay.

Imports touch only small source modules. Tiny helpers accept arrays and rows;
only actual() opens accepted original data, once per declared source.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import InvalidOperation
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

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage230_K_payoff_measurement_protocol/protocol.json'
PROTOCOL_SHA='ba46ca70fd2bc6387f0cd89d9c7bb7313283b1de38cc9893442487e7ec754f85'
SCENARIOS=('base','stress')
PHASE='after_all_source_close'


def module(name):
    spec=importlib.util.spec_from_file_location('accepted233_'+name,TOOLS/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


clock=module('stage227_K_clock_support')
quote=module('stage042_cross_session_experiment')
META=list(clock.ACTIONS)
MOTHERS=list(clock.MOTHERS)
NUMERIC_INPUT=['N_u','R0_points','cash_risk_unit','multiplier','tick_size','entry_reference']
for _s in SCENARIOS:
    NUMERIC_INPUT += [_s+'_entry_fill',_s+'_entry_fee_per_lot',_s+'_entry_slippage_per_lot',
                     'net_pnl_'+_s+'_per_lot','net_R_'+_s,'net_R_common2N_'+_s]
ACTIONS=META+['exit_reason']+NUMERIC_INPUT
LABEL_ID=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id',
          'u_date','u_index','reference_epoch','anchor_epoch']
OLD=['u_action_eligible','label_state','participation_state','filled','trade_label_known','entry_index',
     'entry_date','exit_index','exit_date','unknown_index','unknown_date','label_known_date','label_known_phase',
     'participation_known_date','participation_known_phase','cancel_reason','exit_reason']
GATE=['primary_domain','calendar_allowed','calendar_state','D_date','K_target_date','K_index','K_date',
      'K_state','K_after_sample_end','timing_state','branch']
POLICY=['policy_reward_known','policy_reward','policy_known_date','policy_known_phase']
COST_FIELDS=['known','state','net_pnl_per_lot','net_R','net_R_common2N','known_date','known_phase',
             'exit_index','exit_date','exit_reason']
LABEL_COLUMNS=LABEL_ID+OLD+GATE+POLICY
for _s in SCENARIOS:
    LABEL_COLUMNS += ['net_pnl_'+_s+'_per_lot','net_R_'+_s,'net_R_common2N_'+_s]+['K_'+_s+'_'+k for k in COST_FIELDS]
NATIVE_EVIDENCE=['epoch_slot','offset_start','offset_end','local_row','flat_row','native_day','native_open','native_valid']
EVIDENCE_COLUMNS=LABEL_COLUMNS+[k for k in NUMERIC_INPUT if k not in LABEL_COLUMNS]+NATIVE_EVIDENCE
for _s in SCENARIOS:
    EVIDENCE_COLUMNS += ['K_'+_s+'_sell_fill','K_'+_s+'_sell_fee_per_lot','K_'+_s+'_sell_slippage_per_lot','K_'+_s+'_tickized']
MOTHER_COUNTS=['child_count','primary_count','K_quote_count']+[s+'_'+k+'_count' for s in SCENARIOS for k in ('known','unknown','noaction')]
NATIVE_MEMBERS=['epochs','offsets','days','values','valid']


def number(raw,key,positive=False):
    value=float(raw[key])
    if not math.isfinite(value) or (positive and value<=0):raise ValueError('invalid_original_numeric '+key)
    return value


def native_point(native,epoch,K):
    slots=native.get('_slots')
    slot=slots.get(epoch) if slots is not None else next((i for i,e in enumerate(native['epochs']) if e==epoch),None)
    if slot is None:raise ValueError('complete_prefix_missing_K_epoch '+epoch)
    a,b=map(int,native['offsets'][slot:slot+2]);days=native['days'][a:b]
    j=int(np.searchsorted(days,K));flat=a+j
    if j>=len(days) or int(days[j])!=K or not bool(native['valid'][flat]):
        raise ValueError('complete_prefix_missing_or_invalid_K_point '+epoch)
    O=float(native['values'][flat,0])
    if not math.isfinite(O) or O<=0:raise ValueError('complete_prefix_invalid_K_open')
    return dict(epoch_slot=slot,offset_start=a,offset_end=b,local_row=j,flat_row=flat,
                native_day=int(days[j]),native_open=O,native_valid=1)


def measure_action(raw,calendar,sample_end,native,*,boundary=None,calendar_days=None):
    """Accepted prefix reuse; only quote_K reaches native_point/adverse_quote."""
    derived=clock.classify_action({k:raw[k] for k in META},calendar,sample_end,boundary,calendar_days)
    out={k:raw[k] for k in LABEL_ID+OLD}
    out.update({k:('' if derived[k] is None else derived[k]) for k in GATE if k!='branch'})
    primary=bool(derived['primary_domain']);timing=derived['timing_state']
    if not primary:
        branch='nonprimary_calendar_unknown' if raw['u_action_eligible']=='1' and derived['calendar_allowed'] is None else 'nonprimary_noaction'
    elif timing=='closed_before_K':branch='copy_before_K'
    elif timing=='known_nonparticipation':branch='known_nonparticipation'
    elif timing in clock.POTENTIAL:branch='quote_K'
    else:branch='unresolved'
    out.update(branch=branch,policy_reward_known=0,policy_reward='',policy_known_date='',policy_known_phase='')
    if branch in ('nonprimary_noaction','known_nonparticipation'):
        out.update(policy_reward_known=1,policy_reward='0',
            policy_known_date=raw['u_date'] if branch=='nonprimary_noaction' else raw['participation_known_date'],
            policy_known_phase=PHASE if branch=='nonprimary_noaction' else raw['participation_known_phase'])
        if not out['policy_known_date'] or not out['policy_known_phase']:raise ValueError('missing_policy_zero_clock')
    for s in SCENARIOS:
        for k in ('net_pnl_'+s+'_per_lot','net_R_'+s,'net_R_common2N_'+s):out[k]=raw[k]
        out.update({'K_'+s+'_'+k:'' for k in COST_FIELDS})
        out['K_'+s+'_known']=0
        out['K_'+s+'_state']=branch if branch.startswith('nonprimary') else timing
    if branch=='copy_before_K':
        for s in SCENARIOS:
            for k in ('net_pnl_'+s+'_per_lot','net_R_'+s,'net_R_common2N_'+s):number(raw,k)
            out.update({'K_'+s+'_known':1,'K_'+s+'_state':'known_original_before_K',
                'K_'+s+'_net_pnl_per_lot':raw['net_pnl_'+s+'_per_lot'],'K_'+s+'_net_R':raw['net_R_'+s],
                'K_'+s+'_net_R_common2N':raw['net_R_common2N_'+s],
                'K_'+s+'_known_date':raw['label_known_date'],'K_'+s+'_known_phase':raw['label_known_phase'],
                'K_'+s+'_exit_index':raw['exit_index'],'K_'+s+'_exit_date':raw['exit_date'],
                'K_'+s+'_exit_reason':raw['exit_reason']})
        return out,None
    if branch!='quote_K':return out,None
    if raw['filled']!='1' or raw['entry_index']!=raw['D_index']:raise ValueError('K_prefix_without_original_entry')
    N=number(raw,'N_u',True);M=number(raw,'multiplier',True);R0=number(raw,'R0_points',True);risk=number(raw,'cash_risk_unit',True)
    if not math.isclose(R0,.25*N,rel_tol=1e-12,abs_tol=1e-12) or not math.isclose(risk,R0*M,rel_tol=1e-12,abs_tol=1e-12):
        raise ValueError('original_risk_unit_mismatch')
    number(raw,'entry_reference',True)
    tick=number(raw,'tick_size') if raw['tick_size'] else math.nan
    evidence={k:raw[k] for k in NUMERIC_INPUT if k not in LABEL_COLUMNS}
    evidence.update(native_point(native,raw['reference_epoch'],derived['K_index']))
    econ=dict(contract_multiplier=M,tick_size=tick)
    for s in SCENARIOS:
        p='K_'+s+'_';entry=number(raw,s+'_entry_fill',True);fee=number(raw,s+'_entry_fee_per_lot');slip=number(raw,s+'_entry_slippage_per_lot')
        if fee<0 or slip<0:raise ValueError('negative_original_fee_or_slippage')
        evidence.update({p+k:'' for k in ('sell_fill','sell_fee_per_lot','sell_slippage_per_lot','tickized')})
        try:
            sell=quote.adverse_quote(evidence['native_open'],'SELL',econ,s)
            net=M*(sell['fill_price']-entry)-fee-sell['fee_per_lot'];R=net/risk;aux=net/(2*N*M)
            if not all(math.isfinite(float(v)) for v in [sell['fill_price'],sell['fee_per_lot'],sell['slippage_per_lot'],net,R,aux]):
                raise ValueError('nonfinite_K_cost_result')
        except (ValueError,OverflowError,InvalidOperation,ZeroDivisionError):
            out[p+'state']='unknown_K_cost';continue
        out.update({p+'known':1,p+'state':'known_K_quote',p+'net_pnl_per_lot':net,p+'net_R':R,p+'net_R_common2N':aux,
            p+'known_date':derived['K_date'],p+'known_phase':PHASE,p+'exit_index':derived['K_index'],
            p+'exit_date':derived['K_date'],p+'exit_reason':'K_deadline_open'})
        evidence.update({p+'sell_fill':sell['fill_price'],p+'sell_fee_per_lot':sell['fee_per_lot'],
                         p+'sell_slippage_per_lot':sell['slippage_per_lot'],p+'tickized':int(sell['tickized'])})
    evidence.update(out)
    return out,evidence


def stats():
    return dict(action_count=0,primary_count=0,K_quote_count=0,noaction_count=0,mother_count=0,nochild_mother_count=0,
        timing_counts=Counter(),primary_timing_counts=Counter(),calendar_counts=Counter(),costs={s:dict(known_count=0,
        unknown_count=0,noaction_count=0,states=Counter(),oldclosed_primary_count=0,oldclosed_newknown_count=0,
        oldclosed_cost_unknown_count=0,oldclosed_clock_violation_count=0,paired_count=0,changed_count=0,
        oldunknown_newknown_count=0,sign_matrix=Counter(),absdelta_R_quantiles={},_deltas=[]) for s in SCENARIOS})


def accumulate(target,row,quantiles=False):
    target['action_count']+=1;target['primary_count']+=int(row['primary_domain']);target['K_quote_count']+=row['branch']=='quote_K'
    noaction=bool(row['policy_reward_known']);target['noaction_count']+=noaction
    target['timing_counts'][row['timing_state']]+=1;target['calendar_counts'][row['calendar_state']]+=1
    if row['primary_domain']:target['primary_timing_counts'][row['timing_state']]+=1
    for s in SCENARIOS:
        c=target['costs'][s];p='K_'+s+'_';known=bool(row[p+'known']);c['states'][row[p+'state']]+=1
        c['known_count']+=known;c['noaction_count']+=noaction;c['unknown_count']+=not (known or noaction)
        oldclosed=bool(row['primary_domain'] and row['trade_label_known']=='1')
        if oldclosed:
            c['oldclosed_primary_count']+=1
            if not known:c['oldclosed_cost_unknown_count']+=1
            else:
                c['oldclosed_newknown_count']+=1
                violation=(row[p+'known_date'],row[p+'known_phase'])>(row['label_known_date'],row['label_known_phase'])
                c['oldclosed_clock_violation_count']+=violation
                if violation:raise ValueError('new_known_clock_later_than_old_closed')
        if known and oldclosed:
            old=float(row['net_R_'+s]);new=float(row[p+'net_R']);delta=abs(new-old)
            c['paired_count']+=1;c['changed_count']+=delta>1e-12*(1+abs(old))
            sign=lambda v:'positive' if v>0 else 'negative' if v<0 else 'zero'
            c['sign_matrix'][sign(old)+'->'+sign(new)]+=1
            if quantiles:c['_deltas'].append(delta)
        elif known:c['oldunknown_newknown_count']+=1


def finalize(target,quantiles=False):
    for c in target['costs'].values():
        values=c.pop('_deltas')
        if quantiles and values:
            q=np.quantile(np.asarray(values,dtype=np.float64),[.5,.9,.99,1.])
            c['absdelta_R_quantiles']=dict(zip(('p50','p90','p99','max'),map(float,q)))
        if sum(c[k] for k in ('known_count','unknown_count','noaction_count'))!=target['action_count']:
            raise ValueError('cost_state_partition_mismatch')
    return target


def measure_rows(mothers,actions,calendar,sample_end,native,*,label_sink=None,evidence_sink=None):
    """One action stream; compact parent arrays, no original table reload."""
    frame=pd.DataFrame(mothers,columns=MOTHERS).copy()
    if frame.empty or frame.event_id.duplicated().any() or frame.duplicated(['product_id','u_date']).any():
        raise ValueError('mother_identity_not_unique')
    if [clock.integer(v) for v in frame.sequence_index]!=list(range(len(frame))):raise ValueError('mother_sequence_mismatch')
    lookup={d:i for i,d in enumerate(calendar)}
    if any(lookup.get(d)!=clock.integer(u) for d,u in zip(frame.u_date,frame.u_index)):raise ValueError('mother_calendar_mismatch')
    columns={k:frame[k].to_numpy() for k in MOTHERS};counts=np.zeros((len(frame),len(MOTHER_COUNTS)),dtype=np.int32)
    scopes={k:stats() for k in ('all','post2020')}
    partitions={k:{} for k in ('year','family','product')}
    boundaries={};days=set(calendar);labels=[];evidence_rows=[];anchors=[];quote_count=0
    anchor_positions=set(np.linspace(0,14254-1,16,dtype=int).tolist())
    for seq,raw in enumerate(actions):
        if clock.integer(raw['sequence_index'])!=seq or clock.integer(raw['action_sequence_index'])!=seq:
            raise ValueError('action_sequence_mismatch')
        parent=clock.integer(raw['mother_sequence_index'])
        if not 0<=parent<len(frame) or raw['mother_event_id']!=columns['event_id'][parent]:raise ValueError('action_parent_mismatch')
        for k in ('product_id','family_id','u_date','u_index'):
            if str(raw[k])!=str(columns[k][parent]):raise ValueError('action_parent_field_mismatch '+k)
        if raw['anchor_epoch']!=columns['reference_epoch'][parent]:raise ValueError('action_anchor_mismatch')
        epoch=raw['reference_epoch']
        if epoch not in boundaries:boundaries[epoch]=clock.gate_helper().calendar_boundary(epoch,calendar,sample_end)
        row,ev=measure_action(raw,calendar,sample_end,native,boundary=boundaries[epoch],calendar_days=days)
        (labels.append if label_sink is None else label_sink)(row)
        if ev is not None:
            (evidence_rows.append if evidence_sink is None else evidence_sink)(ev)
            if quote_count in anchor_positions:anchors.append(ev)
            quote_count+=1
        counts[parent,0]+=1;counts[parent,1]+=row['primary_domain'];counts[parent,2]+=ev is not None
        for z,s in enumerate(SCENARIOS):
            known=bool(row['K_'+s+'_known']);noaction=bool(row['policy_reward_known'])
            counts[parent,3+3*z:6+3*z]+=np.asarray([known,not(known or noaction),noaction],np.int32)
        accumulate(scopes['all'],row,True)
        if raw['u_date']>='2020-01-01':accumulate(scopes['post2020'],row,True)
        for kind,key in [('year',raw['u_date'][:4]),('family',raw['family_id']),('product',raw['product_id'])]:
            if key not in partitions[kind]:partitions[kind][key]=stats()
            accumulate(partitions[kind][key],row)
    for i in range(len(frame)):
        for group in [scopes['all']]+([scopes['post2020']] if str(columns['u_date'][i])>='2020-01-01' else []):
            group['mother_count']+=1;group['nochild_mother_count']+=int(counts[i,0]==0)
        for kind,key in [('year',str(columns['u_date'][i])[:4]),('family',columns['family_id'][i]),('product',columns['product_id'][i])]:
            if key not in partitions[kind]:partitions[kind][key]=stats()
            partitions[kind][key]['mother_count']+=1;partitions[kind][key]['nochild_mother_count']+=int(counts[i,0]==0)
    for j,k in enumerate(MOTHER_COUNTS):frame[k]=counts[:,j]
    summary=dict(scopes={k:finalize(v,True) for k,v in scopes.items()},
                 partitions={k:{n:finalize(v) for n,v in groups.items()} for k,groups in partitions.items()})
    return dict(labels=labels,evidence=evidence_rows,mothers=frame.to_dict('records') if label_sink is None else None,
                mother_frame=frame,summary=summary,anchors=anchors)


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def read_small(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('small_binding_changed '+b['path'])
    return raw


def write_json(path,data):
    with Path(path).open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def source_bundle():
    return sorted([binding(TOOLS/n) for n in ('stage233_K_payoff_measurement.py','test_stage233_K_payoff_measurement.py',
        'stage227_K_clock_support.py','stage156_voluntary_choices.py','stage042_cross_session_experiment.py')],key=lambda b:b['path'])


def inherited_stat(b):
    s=Path(b['path']).stat()
    if s.st_size!=b['bytes']:raise ValueError('accepted_source_size_changed '+b['path'])
    return dict(path=b['path'],bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
                inherited_sha256=b['sha256'],rehashed=False)


def projected_rows(path,fields):
    with gzip.open(path,'rt',newline='') as f:
        reader=csv.reader(f);header=next(reader)
        if len(header)!=len(set(header)) or not set(fields)<=set(header):raise ValueError('source_header_mismatch')
        positions=[header.index(k) for k in fields]
        for row in reader:
            if len(row)!=len(header):raise ValueError('source_row_width_mismatch')
            yield {k:row[j] for k,j in zip(fields,positions)}


def validate_counts(summary,accepted,protocol):
    for scope,oldname in [('all','all'),('post2020','2020onward')]:
        a=summary['scopes'][scope];old=accepted['scopes'][oldname]
        for new,previous in [('action_count','action_count'),('mother_count','mother_count'),
            ('nochild_mother_count','nochild_mother_count'),('primary_count','primary_domain_count'),('K_quote_count','potential_support_count')]:
            if a[new]!=old[previous]:raise ValueError('accepted_clock_count_changed '+scope+' '+new)
        for group,prefix,states in [('timing_counts','timing_',clock.TIMING_STATES),
            ('primary_timing_counts','primary_timing_',clock.TIMING_STATES),('calendar_counts','calendar_',clock.CALENDAR_STATES)]:
            for state in states:
                if a[group].get(state,0)!=old[prefix+state+'_count']:raise ValueError('accepted_clock_partition_changed '+state)
    a=summary['scopes']['all']
    if (a['action_count']!=protocol['expected_action_rows'] or a['mother_count']!=protocol['expected_mother_rows']
            or a['K_quote_count']!=protocol['expected_new_K_quote_actions']):raise ValueError('frozen_population_mismatch')


def actual(args):
    pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen230_protocol_changed')
    protocol=json.loads(read_small(pb));ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization_sha_mismatch')
    auth=json.loads(read_small(ab));bundle=source_bundle();output=Path(args.output).resolve()
    if (auth.get('schema')!='stage230_exact_root_authorization_v1' or auth.get('authorized_by')!='root'
        or auth.get('stage')!='measurement' or auth.get('exact_source_authorized') is not True
        or auth.get('protocol_sha256')!=PROTOCOL_SHA or auth.get('output')!=str(output) or auth.get('source_bundle')!=bundle):
        raise ValueError('exact_root_measurement_authorization_required')
    if protocol['actions_usecols']!=ACTIONS or protocol['mothers_usecols']!=MOTHERS or protocol['native_members']!=NATIVE_MEMBERS:
        raise ValueError('frozen_column_interface_changed')
    output.mkdir(parents=True,exist_ok=False);start=time.monotonic();began=datetime.now(timezone.utc).isoformat()
    write_json(output/'started.json',dict(started_at=began,protocol=pb,authorization=ab,source_bundle=bundle))
    status='failed';failure=None;source={};counters=dict(original_actions_streams=0,original_mothers_reads=0,calendar_reads=0,native_npz_opens=0,native_npz_members=0,
        old_clock_projection_reads=0,economic_projection_reads=0,old_training_cache_reads=0,COMMON_X_reads=0,model_score_selection_cash_reads=0,
        SQL=0,network_download=0,old_large_input_hashes=0,new_fit=0,new_cash=0)
    try:
        inputs=protocol['input_bindings'];small={}
        for role in ('dataset_manifest','native_cache_manifest','clock_summary227','clock_review228','clock_decision229'):
            small[role]=json.loads(read_small(inputs[role]))
        for role in ('classifier227','calendar_gate156','quote_kernel042'):read_small(inputs[role])
        meta=small['native_cache_manifest']
        if meta['file']!=inputs['native_cache'] or meta['native_rows']!=1552456 or meta['native_epochs']!=9520:
            raise ValueError('accepted132_cache_identity_mismatch')
        source={k:dict(before=inherited_stat(inputs[k])) for k in ('actions','mothers','native_cache')}
        counters['calendar_reads']+=1;cal=np.load(io.BytesIO(read_small(inputs['calendar'])),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal] if cal.dtype.kind in 'iu'
                  else cal.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)) or protocol['sample_end'] not in calendar:raise ValueError('original_calendar_mismatch')
        counters['native_npz_opens']+=1
        with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
            native={k:z[k] for k in NATIVE_MEMBERS};counters['native_npz_members']=5
        epochs=native['epochs'].tolist();offset=native['offsets']
        if (len(epochs)!=9520 or epochs!=sorted(set(epochs)) or len(offset)!=9521 or offset[0]!=0 or offset[-1]!=1552456
                or not np.all(np.diff(offset)>=0) or native['days'].shape!=(1552456,) or native['values'].shape!=(1552456,5)
                or native['valid'].shape!=(1552456,)):raise ValueError('accepted_native_array_shape_mismatch')
        native['_slots']={e:i for i,e in enumerate(epochs)}
        counters['original_mothers_reads']+=1
        mothers=pd.read_csv(inputs['mothers']['path'],usecols=MOTHERS,dtype=str,keep_default_na=False)[MOTHERS]
        if len(mothers)!=protocol['expected_mother_rows']:raise ValueError('mother_population_mismatch')
        counters['original_actions_streams']+=1
        with gzip.open(output/'labels_K.csv.gz','wt',newline='',compresslevel=1) as f,gzip.open(output/'K_quote_evidence.csv.gz','wt',newline='',compresslevel=1) as g:
            labels=csv.DictWriter(f,fieldnames=LABEL_COLUMNS);evidence=csv.DictWriter(g,fieldnames=EVIDENCE_COLUMNS)
            labels.writeheader();evidence.writeheader()
            result=measure_rows(mothers,projected_rows(inputs['actions']['path'],ACTIONS),calendar,protocol['sample_end'],native,
                                label_sink=labels.writerow,evidence_sink=evidence.writerow)
        validate_counts(result['summary'],small['clock_summary227'],protocol)
        frame=result.pop('mother_frame')
        for s in SCENARIOS:
            if not (frame[s+'_known_count']+frame[s+'_unknown_count']+frame[s+'_noaction_count']).equals(frame.child_count):
                raise ValueError('mother_cost_partition_mismatch')
        frame.to_csv(output/'mothers_K.csv.gz',index=False,compression=dict(method='gzip',compresslevel=1))
        for k,state in source.items():
            state['after']=inherited_stat(inputs[k])
            if state['before']!=state['after']:raise ValueError('source_stat_changed '+k)
        summary=dict(schema='stage233_K_payoff_summary_v1',**result['summary'],cumulative_fit=433,cumulative_cash=234,
                     purpose='object_measurement_only',goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        write_json(output/'summary.json',summary);write_json(output/'anchors.json',result['anchors'])
        write_json(output/'source_read_receipt.json',dict(inputs=inputs,source_stats=source,counters=counters,
            action_id_uniqueness_inherited_from_accepted129=True,new_K_path_replays=0,physical_NPZ_point_only_reads_claimed=False))
        status='completed'
    except Exception as exc:
        failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        write_json(output/'failure.json',failure)
    terminal=dict(schema='stage233_K_payoff_terminal_v1',status=status,started_at=began,completed_at=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=time.monotonic()-start,counters=counters,new_fit=0,new_cash=0,automatic_retry=False)
    write_json(output/'terminal.json',terminal)
    artifacts={p.name:binding(p) for p in sorted(output.iterdir()) if p.is_file()}
    manifest=dict(schema='stage233_K_payoff_measurement_v1',status=status,protocol=pb,protocol_sha256=PROTOCOL_SHA,authorization=ab,
        input_bindings=protocol['input_bindings'],source_bundle=bundle,artifacts=artifacts,counters=counters,
        label_columns=LABEL_COLUMNS,evidence_columns=EVIDENCE_COLUMNS,mother_columns=MOTHERS+MOTHER_COUNTS,
        cumulative_fit=433,cumulative_cash=234,goal_complete=False,production_qualified=False,increased_betting_qualified=False)
    write_json(output/'manifest.json',manifest)
    print(json.dumps(dict(status=status,output=str(output),elapsed_seconds=terminal['elapsed_seconds']),ensure_ascii=False),flush=True)
    if failure is not None:raise RuntimeError(failure['message'])
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--actual',action='store_true')
    parser.add_argument('--authorization',type=Path,required=True);parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(argv)
    if not args.actual:parser.error('only explicit --actual with frozen exact root authorization')
    actual(args)


if __name__=='__main__':main()
