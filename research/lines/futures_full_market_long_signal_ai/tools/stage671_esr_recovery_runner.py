"""Frozen669 ESR MY-literal recovery experiment, root-only single actual pass.

Imports never read historical payloads. Every accepted train/forward/mother/source
is consumed once; inherited SHA identities plus before/after stat bind old files. Recovery reads only parent668 literal caches; no second538 payload pass.
Only new outputs are hashed. No old model/scaler/A choices, SQL or network reads.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage669_esr_marketing_year_schema_recovery_protocol/protocol.json'
PROTOCOL_SHA='9562629fe8d190e092ef042b51aa1d3027d2b3ea69382ca19891224bcc1f7725'
OUTPUT_ROOT=LINE/'outputs/stage671_esr_quantity_recovery'
PARENT_CACHE_ROOT=LINE/'outputs/stage668_esr_quantity_increment/actual_run1'
ARMS=('A','B','C')
SCOPES=('main','holdout_0','holdout_1')
ECONOMIC_GROUPS=('corn','soy_complex','upland_cotton')
CASES=SCOPES+tuple('transfer_'+g for g in ECONOMIC_GROUPS)
CONTRASTS={'C_minus_B':('C','B'),'C_minus_A':('C','A'),'B_minus_A':('B','A')}
TRAIN=['sequence_index','action_id','product_id','family_id','u_date','u_index','u_action_eligible','label_state','participation_state','label_known_date','net_R_stress','sample_weight','Ahat']
SCORE_FIELDS=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','score','scope','cutoff']
LABELS=['label_state','participation_state','net_R_stress','label_known_date']
FORWARD=SCORE_FIELDS+LABELS
MOTHER=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
SOURCE_COLUMNS=['source_row','period_end_date','unit','commodityId','commodityName','weekNumber','myDefinition','weekEndingDate','weeklyExport','netSales','outstandingSales','accumulatedExport','nextYearOutstandingSales','nextYearNetSales','mycoTypeName','numeric_state','publication_clock_state']
STAT_FIELDS=('bytes','device','inode','mtime_ns')

def load_local_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simple(binding):
    return {key: binding[key] for key in ('path', 'bytes', 'sha256')}


def file_stat(path):
    stat = Path(path).stat()
    return dict(bytes=stat.st_size, device=stat.st_dev, inode=stat.st_ino,
                mtime_ns=stat.st_mtime_ns)


def check_stat(path, expected):
    actual = file_stat(path)
    if actual != {key: expected[key] for key in STAT_FIELDS}:
        raise ValueError('accepted source stat differs: ' + str(path))
    return actual


def small_binding(path, limit=2_000_000):
    path = Path(path).resolve()
    if path.stat().st_size > limit:
        raise ValueError('small binding limit exceeded: ' + str(path))
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()), data


def read_bound_json(binding):
    actual, data = small_binding(binding['path'])
    if actual != simple(binding):
        raise ValueError('small JSON binding differs: ' + binding['path'])
    return json.loads(data)


def jsonable(value):
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def output_binding(path):
    """New files only; old payloads must never be passed here."""
    path = Path(path).resolve()
    if OUTPUT_ROOT.resolve() not in path.parents:
        raise ValueError('only new671 artifacts may be hashed here')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(jsonable(value), stream, ensure_ascii=False, sort_keys=True,
                  indent=2, allow_nan=False)
        stream.write('\n')
    return output_binding(path)


def write_frame(path, frame):
    frame.to_csv(path, index=False, mode='x', float_format='%.17g',
                 compression={'method': 'gzip', 'mtime': 0})
    return output_binding(path)


def family_group(family):
    return int(hashlib.sha256(str(family).encode('utf-8')).hexdigest(), 16) % 2



class SinglePassInputs:
    def __init__(self, roles):
        self.roles = roles
        self.records = {}

    def read_table(self, role, columns, numeric=()):
        if role in self.records:
            raise ValueError('old source read attempted twice: ' + role)
        binding, expected = self.roles[role]
        before = check_stat(binding['path'], expected)
        record = dict(role=role, accepted_binding=simple(binding), stat_before=before,
                      read_passes_attempted=1, read_passes_completed=0,
                      separate_payload_hash_passes=0, columns=list(columns))
        self.records[role] = record
        chunks = []
        with pd.read_csv(binding['path'], compression='gzip', dtype=str,
                         keep_default_na=False, usecols=list(columns),
                         chunksize=100_000) as reader:
            for chunk in reader:
                chunk = chunk.loc[:, columns]
                for name in numeric:
                    chunk[name] = pd.to_numeric(chunk[name], errors='raise')
                chunks.append(chunk)
        frame = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
        record.update(stat_after=check_stat(binding['path'], expected),
                      read_passes_completed=1, rows=len(frame))
        return frame

    def read_calendar(self):
        role = 'calendar'
        if role in self.records:
            raise ValueError('calendar read twice')
        binding, expected = self.roles[role]
        before = check_stat(binding['path'], expected)
        self.records[role] = dict(role=role, accepted_binding=simple(binding),
                                  stat_before=before, read_passes_attempted=1,
                                  read_passes_completed=0, separate_payload_hash_passes=0)
        data = Path(binding['path']).read_bytes()
        if len(data) != binding['bytes'] or hashlib.sha256(data).hexdigest() != binding['sha256']:
            raise ValueError('calendar bytes differ')
        calendar = json.loads(data)
        if len(calendar) != 5587 or calendar != sorted(set(calendar)):
            raise ValueError('immutable full source calendar differs')
        self.records[role].update(stat_after=check_stat(binding['path'], expected),
                                  read_passes_completed=1, rows=len(calendar),
                                  sha256_checked_in_same_read=True)
        return calendar

    def verify_final_stats(self):
        for role, (binding, expected) in self.roles.items():
            final = check_stat(binding['path'], expected)
            if role in self.records:
                self.records[role]['stat_at_terminal'] = final



def validate_train(train, fold):
    cutoff, scope = fold['cutoff'], fold['scope']
    if (len(train) != fold['training_check']['training_rows']
            or train.action_id.duplicated().any() or train.sequence_index.duplicated().any()):
        raise ValueError('accepted own training row identity differs')
    if not (train.u_action_eligible.eq(1)
            & train.label_state.eq('closed_complete_bar_model')
            & train.u_date.lt(cutoff) & train.label_known_date.ne('')
            & train.label_known_date.lt(cutoff)).all():
        raise ValueError('accepted original mature training domain differs')
    values = train[['sample_weight', 'net_R_stress', 'Ahat']].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 0] <= 0).any():
        raise ValueError('finite training inputs/positive inherited weight required')
    if (train.u_date.max() != fold['training_check']['max_u_date']
            or train.label_known_date.max() != fold['training_check']['max_label_known_date']
            or train.u_date.nunique() != fold['training_check']['training_dates']
            or train.family_id.nunique() != fold['training_check']['training_families']):
        raise ValueError('inherited training coverage/maturity differs')
    if scope != 'main' and train.family_id.map(family_group).eq(int(scope[-1])).any():
        raise ValueError('held-family label leakage')


def validate_forward(forward, mothers, protocol):
    if (len(forward) != 1_933_480
            or forward.duplicated(['scope', 'cutoff', 'action_id']).any()
            or not np.isfinite(forward.score).all()
            or not forward.u_action_eligible.isin((0, 1)).all()):
        raise ValueError('complete frozen forward child domain differs')
    if (len(mothers) != 161_014
            or mothers.sequence_index.duplicated().any() or mothers.event_id.duplicated().any()
            or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95):
        raise ValueError('full98/95 mother identity differs')
    expected_cutoff = np.where(forward.u_date.lt('2023-01-01'), '2020-01-01', '2023-01-01')
    if (set(forward.scope) != set(SCOPES)
            or not np.array_equal(forward.cutoff.to_numpy(), expected_cutoff)
            or not forward.u_date.between('2020-01-01', protocol['scope']['forward_end']).all()):
        raise ValueError('scope/cutoff deployment differs')
    for fold in protocol['folds']:
        selected = forward.scope.eq(fold['scope']) & forward.cutoff.eq(fold['cutoff'])
        if int(selected.sum()) != fold['prediction_children']:
            raise ValueError('own-fold forward count differs')
        if fold['scope'] != 'main' and not forward.loc[selected, 'family_id'].map(family_group).eq(int(fold['scope'][-1])).all():
            raise ValueError('forward own-held family scope differs')
    main = forward.loc[forward.scope.eq('main')]
    held = forward.loc[forward.scope.ne('main')]
    if (main.action_id.duplicated().any() or held.action_id.duplicated().any()
            or set(main.action_id) != set(held.action_id)):
        raise ValueError('main/held complete child coverage differs')
    linked = main.merge(held[['action_id', *LABELS]], on='action_id',
                        validate='one_to_one', suffixes=('', '_held'))
    for name in LABELS:
        left, right = linked[name], linked[name + '_held']
        if not (left.eq(right) | (left.isna() & right.isna())).all():
            raise ValueError('scope target literals differ: ' + name)



def source_roles(protocol):
    roles={}
    for fold in protocol['folds']:
        role='train_'+fold['scope']+'_'+fold['cutoff']
        if Path(fold['train_compact']['path']).resolve()!=(PARENT_CACHE_ROOT/(role+'.csv.gz')).resolve():raise ValueError('recovery must reuse exact parent668 training literal cache')
        roles[role]=(fold['train_compact'],fold['stat_snapshot'])
    for name in ('forward_base_compact','mothers_forward','calendar'):
        if name!='calendar':
            filename='forward_thin.csv.gz' if name=='forward_base_compact' else 'mothers_thin.csv.gz'
            if Path(protocol['inputs'][name]['path']).resolve()!=(PARENT_CACHE_ROOT/filename).resolve():raise ValueError('recovery must reuse exact parent668 original literal projection')
        roles[name]=(protocol['inputs'][name],protocol['core_stat_snapshots'][name])
    for source in protocol['sources']:
        roles['esr_source_'+str(source['commodity_id'])]=(source['normalized'],source['stat_snapshot'])
    if len(roles)!=14 or len({b['path'] for b,_ in roles.values()})!=14:
        raise ValueError('exact14 accepted input roles required')
    return roles


def validate_source_ready(protocol_path,protocol_sha256,ready_path):
    pb,data=small_binding(protocol_path)
    if Path(pb['path'])!=PROTOCOL.resolve() or protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen669 protocol required')
    protocol=json.loads(data)
    if protocol['schema']!='stage669_esr_quantity_recovery_protocol_v1':raise ValueError('wrong669schema')
    rb,raw=small_binding(ready_path);ready=json.loads(raw)
    if ready.get('schema')!='stage670_esr_quantity_source_ready_v1' or simple(ready['protocol'])!=pb:
        raise ValueError('wrong670source ready')
    for key,pkey in [('mapping','mapping'),('method_notes','method_advisory_notes')]:
        if simple(ready[key])!=simple(protocol[pkey]):raise ValueError('ready small binding differs '+key)
        read_bound_json(ready[key])
    review=read_bound_json(ready['method_review'])
    if review.get('schema')!='stage665_frozen669_recovery_protocol_review_v1' or review.get('method_GO') is not True or simple(review['protocol'])!=pb or review.get('financial_payload_reads')!=0 or review.get('full_protocol_read') is not True:
        raise ValueError('665 protocol review not GO')
    required={str((TOOLS/f).resolve()) for f in ['stage671_esr_recovery_runner.py','stage670_esr_schema_kernel.py','test_stage670_esr_schema_kernel.py','stage156_voluntary_choices.py']}
    if not required.issubset({b['path'] for b in ready['sources']}):raise ValueError('source ready code missing')
    if len({b['path'] for b in ready['sources']})!=len(ready['sources']):raise ValueError('duplicate code binding')
    for b in ready['sources']:
        if small_binding(b['path'])[0]!=simple(b):raise ValueError('source code changed '+b['path'])
    fixture=read_bound_json(ready['fixture_receipt'])
    if fixture.get('status') not in ('completed','passed') or fixture.get('exit_code')!=0:raise ValueError('fixtures not passing')
    recovery=protocol['schema_recovery']
    parent_manifest=read_bound_json(recovery['parent_manifest'])
    parent_terminal=read_bound_json(recovery['parent_terminal'])
    read_bound_json(recovery['independent_confirmation'])
    if any(parent_terminal.get(k)!=0 for k in ['actual_fit_calls_attempted','actual_fit_calls_completed','cash']):raise ValueError('parent668 must remain0fit0cash')
    roles=source_roles(protocol)
    for role,(binding,_) in roles.items():
        if role.startswith('train_'):parent_role=role
        elif role=='forward_base_compact':parent_role='forward_thin'
        elif role=='mothers_forward':parent_role='mothers_thin'
        else:continue
        if simple(binding)!=simple(parent_manifest['artifacts'][parent_role]):raise ValueError('669financial cache must match parent668manifest')
    stats={role:check_stat(b['path'],st) for role,(b,st) in roles.items()}
    return dict(protocol=protocol,protocol_binding=pb,ready=ready,ready_binding=rb,source_roles=roles,checked_stats=stats)


def validate_source_go(path,state):
    b,raw=small_binding(path);go=json.loads(raw)
    if go.get('schema')!='stage665_esr_recovery_source_go_v1' or go.get('source_GO') is not True or simple(go['protocol'])!=state['protocol_binding'] or simple(go['source_ready'])!=state['ready_binding'] or any(go.get(k)!=0 for k in ['preactual_payload_reads','fit','cash']):
        raise ValueError('exact665 source GO required')
    read_bound_json(go['reviewer_ready'])
    return b,go


def validate_calendar_identity(frame,calendar):
    ix=frame.u_index.to_numpy(float)
    if not np.isfinite(ix).all() or not np.equal(ix,np.floor(ix)).all() or (ix<0).any() or (ix>=len(calendar)).any():raise ValueError('invalid calendarindex')
    if frame.u_date.tolist()!=[calendar[i] for i in ix.astype(int)]:raise ValueError('original calendar date identity differs')


def choose_all(forward,mothers,calendar,end):
    """Exact538.select_scope ->156 selector; new scores are sole policy change."""
    selector=load_local_module('esr671_original538','stage538_sector_residual_fit.py')
    choices=[];records=[]
    for case in CASES:
        original_scope=case if case in SCOPES else 'main'
        children=forward.loc[forward.scope.eq(original_scope)]
        parents=mothers if original_scope=='main' else mothers.loc[mothers.family_id.map(family_group).eq(int(original_scope[-1]))]
        if case.startswith('transfer_'):
            group=case.removeprefix('transfer_')
            children=children.loc[children.economic_group.eq(group)]
            parents=parents.loc[parents.economic_group.eq(group)]
        parent_records=parents[MOTHER].to_dict('records')
        for arm in ARMS:
            col='score' if arm=='A' else ('transfer_'+arm+'_score' if case.startswith('transfer_') else arm+'_score')
            fields=children[SCORE_FIELDS].copy();fields['score']=children[col].to_numpy();fields['scope']=case
            columns=fields.columns.tolist()
            rows=(dict(zip(columns,values)) for values in fields.itertuples(index=False,name=None))
            result=selector.select_scope(parent_records,rows,calendar,end,case,arm)
            frame=pd.DataFrame(result['choices']);frame['case']=case;frame['label_scope']=original_scope
            if len(frame)!=len(parents) or set(frame.event_id)!=set(parents.event_id):raise ValueError('complete case mother domain shrunk')
            choices.append(frame);records.append(dict(case=case,arm=arm,summary=result['summary']))
            print(json.dumps(dict(phase='selection_complete',case=case,arm=arm,mothers=len(frame),selected=int(frame.selected.sum()))),flush=True)
    result=pd.concat(choices,ignore_index=True)
    for arm in ARMS:
        for subset in [result.loc[result.case.eq('main')&result.arm.eq(arm)],result.loc[result.case.isin(SCOPES[1:])&result.arm.eq(arm)]]:
            if len(subset)!=len(mothers) or set(subset.event_id)!=set(mothers.event_id):raise ValueError('full main/held mother domain lost')
    return result,records


def _bool(series):
    if pd.api.types.is_bool_dtype(series):return series.to_numpy(bool)
    return series.astype(str).str.lower().isin(['1','true','1.0']).to_numpy(bool)


def _mean(values):
    values=np.asarray(values,float);values=values[np.isfinite(values)]
    return float(values.mean()) if len(values) else None


def policy_statistics(choices,forward,mothers,calendar_map,kernel,heads,end):
    """Direct mother-week policy averages, conditional unknown masks, shared CIs."""
    cs=choices.copy()
    labels=forward[['scope','cutoff','action_id']+LABELS].rename(columns={'scope':'label_scope','action_id':'chosen_action_id'})
    if labels.duplicated(['label_scope','cutoff','chosen_action_id']).any():raise ValueError('duplicate original label key')
    cs=cs.merge(labels,on=['label_scope','cutoff','chosen_action_id'],how='left',validate='many_to_one')
    meta=['event_id','weekly_group','commodity_id','economic_group','sourcevalid','source_reason','source_id','report_period']
    cs=cs.merge(mothers[meta],on='event_id',how='left',validate='many_to_one')
    if cs.weekly_group.isna().any():raise ValueError('mother outside complete source calendar')
    cs['era']=np.where(cs.u_date.lt('2023-01-01'),'early','late');cs['year']=cs.u_date.str[:4]
    selected=_bool(cs.selected);kd=cs.label_known_date.fillna('').astype(str);y=pd.to_numeric(cs.net_R_stress,errors='coerce').to_numpy(float)
    mature=kd.str.fullmatch(r'\d{4}-\d{2}-\d{2}').to_numpy()&kd.le(end).to_numpy()
    valid=cs.label_state.eq('closed_complete_bar_model').to_numpy()&mature&np.isfinite(y)
    cs['own_known']=(~selected)|valid;cs['own_unknown']=~cs.own_known
    cs['contribution']=np.where(~selected,0.,np.where(valid,y,np.nan))
    cs['selected_nonparticipation']=selected&cs.participation_state.eq('known_nonparticipation').to_numpy()
    cs['selected_unmature']=selected&~mature
    cs['selected_ineligible_label']=selected&~cs.label_state.eq('closed_complete_bar_model').to_numpy()
    if cs.duplicated(['case','arm','event_id']).any():raise ValueError('duplicate case/arm/mother')
    one=cs.loc[cs.arm.eq('A'),['case','event_id','u_date','u_index','family_id','product_id','era','year','weekly_group','commodity_id','economic_group','sourcevalid','source_reason','source_id','report_period']].copy()
    pair=one.copy()
    for arm in ARMS:
        columns=['chosen_action_id','contribution','own_known','selected']
        part=cs.loc[cs.arm.eq(arm),['case','event_id']+columns].rename(columns={c:arm+'_'+c for c in columns})
        pair=pair.merge(part,on=['case','event_id'],how='left',validate='one_to_one')
    for name,(hi,lo) in CONTRASTS.items():
        same=pair[hi+'_chosen_action_id'].fillna('').eq(pair[lo+'_chosen_action_id'].fillna('')).to_numpy()
        both=np.isfinite(pair[hi+'_contribution'])&np.isfinite(pair[lo+'_contribution'])
        diff=(pair[hi+'_contribution']-pair[lo+'_contribution']).to_numpy(float);diff[same]=0.
        pair[name]=np.where(same|both,diff,np.nan);pair[name+'_same_action_unknown']=same&~both
    used=calendar_map[['u_index','u_date','weekly_group']].drop_duplicates('u_index')
    used=used.loc[used.u_date.between('2020-01-01',end)].copy();used['era']=np.where(used.u_date.lt('2023-01-01'),'early','late')
    grids={era:used.loc[used.era.eq(era),'weekly_group'].drop_duplicates().tolist() for era in ['early','late']}
    indices={era:kernel.shared_bootstrap_indices(len(grid)) for era,grid in grids.items()}
    group_rows=[];summary=dict(conditional_only=True,fullE_identified=False,scope_era={},bootstrap=dict(repetitions=2000,block_length=52,seed=20261021,each_era_seed_reset=True,grid_shared=True))
    for case in CASES:
        summary['scope_era'][case]={}
        for view in ['mapped','fullmarket']:
            csdom=cs.loc[cs.case.eq(case)];pdom=pair.loc[pair.case.eq(case)]
            if view=='mapped':csdom=csdom.loc[csdom.commodity_id.ge(0)];pdom=pdom.loc[pdom.commodity_id.ge(0)]
            summary['scope_era'][case][view]={}
            for era,grid in grids.items():
                own=csdom.loc[csdom.era.eq(era)];pr=pdom.loc[pdom.era.eq(era)]
                byown={key:g for key,g in own.groupby(['arm','weekly_group'],sort=False)};bypr={key:g for key,g in pr.groupby('weekly_group',sort=False)}
                current=[]
                for sid in grid:
                    row=dict(case=case,view=view,era=era,weekly_group=sid)
                    for arm in ARMS:
                        part=byown.get((arm,sid));n=0 if part is None else len(part);nk=0 if part is None else int(part.own_known.sum())
                        row.update({arm+'_mothers':n,arm+'_selected':0 if part is None else int(_bool(part.selected).sum()),arm+'_mean':np.nan if not nk else float(part.contribution.mean()),arm+'_known':nk,arm+'_unknown':n-nk,arm+'_sourcevalid_mothers':0 if part is None else int(_bool(part.sourcevalid).sum()),arm+'_selected_nonparticipation':0 if part is None else int(part.selected_nonparticipation.sum()),arm+'_selected_unmature':0 if part is None else int(part.selected_unmature.sum()),arm+'_selected_ineligible_label':0 if part is None else int(part.selected_ineligible_label.sum())})
                    part=bypr.get(sid)
                    for name in CONTRASTS:
                        n=0 if part is None else len(part);nk=0 if part is None else int(np.isfinite(part[name]).sum())
                        row.update({name+'_mean':np.nan if not nk else float(part[name].mean()),name+'_identified':nk,name+'_unknown':n-nk,name+'_same_action_unknown':0 if part is None else int(part[name+'_same_action_unknown'].sum())})
                    group_rows.append(row);current.append(row)
                current=pd.DataFrame(current)
                metrics={name:kernel.conditional_ci(current[name].to_numpy(float),indices[era]) for name in ['A_mean','B_mean','C_mean']+[c+'_mean' for c in CONTRASTS]}
                summary['scope_era'][case][view][era]=dict(weekly_groups=len(grid),metrics=metrics,mothers=len(pr),sourcevalid_mothers=int(_bool(pr.sourcevalid).sum()))
    def test(case,view,era,name,stat,strict=True):
        val=summary['scope_era'][case][view][era]['metrics'][name][stat]
        return val is not None and (val>0 if strict else val>=0)
    eras=['early','late']
    head_support=all(h.get('supported') is True for h in heads.values()) and len(heads)==24
    forward_support={};forward_support_counts={}
    for case in CASES:
        domain=forward.loc[forward.scope.eq(case if case in SCOPES else 'main')]
        if case.startswith('transfer_'):domain=domain.loc[domain.economic_group.eq(case.removeprefix('transfer_'))]
        forward_support[case]={};forward_support_counts[case]={}
        for era in eras:
            part=domain.loc[domain.u_date.lt('2023-01-01') if era=='early' else domain.u_date.ge('2023-01-01')]
            valideligible=_bool(part.sourcevalid)&_bool(part.u_action_eligible)
            forward_support[case][era]=bool(valideligible.any())
            forward_support_counts[case][era]=dict(children=len(part),sourcevalid_children=int(_bool(part.sourcevalid).sum()),sourcevalid_eligible_children=int(valideligible.sum()))
    gates=dict(main_mapped_CminusB_CIlow_positive_both_eras=all(test('main','mapped',e,'C_minus_B_mean','low') for e in eras),main_mapped_CminusA_CIlow_positive_both_eras=all(test('main','mapped',e,'C_minus_A_mean','low') for e in eras),original_held_mapped_CminusB_positive_and_CminusA_nonnegative_all4=all(test(s,'mapped',e,'C_minus_B_mean','point') and test(s,'mapped',e,'C_minus_A_mean','point',False) for s in SCOPES[1:] for e in eras),economic_transfer_CminusB_positive_and_CminusA_nonnegative_all6=all(test(s,'mapped',e,'C_minus_B_mean','point') and test(s,'mapped',e,'C_minus_A_mean','point',False) for s in CASES[3:] for e in eras),C_mapped_own_mean_positive_all12_and_main_own_CIlow_positive_both=all(test(s,'mapped',e,'C_mean','point') for s in CASES for e in eras) and all(test('main','mapped',e,'C_mean','low') for e in eras),main_fullmarket_CminusA_point_nonnegative_both=all(test('main','fullmarket',e,'C_minus_A_mean','point',False) for e in eras),all_required_heads_and_forward_domains_have_actual_support=head_support and all(all(v.values()) for v in forward_support.values()))
    gate=dict(gates,passed=all(gates.values()),head_support=head_support,forward_support=forward_support,new_cash_authorized=False,fullE_qualified=False,interpretation='conditional_signal_candidate_only' if all(gates.values()) else 'close_exact_frozen_ESR_package')
    # MSE uses common source-valid eligible, matured action mask. Source means,
    # equal sources inside economic group, equal groups inside report week.
    mse_source=[];mse_weekly=[]
    for case in CASES:
        ff=forward.loc[forward.scope.eq(case if case in SCOPES else 'main')].copy()
        if case.startswith('transfer_'):ff=ff.loc[ff.economic_group.eq(case.removeprefix('transfer_'))]
        kd=ff.label_known_date.fillna('').astype(str);target=pd.to_numeric(ff.net_R_stress,errors='coerce')
        mask=_bool(ff.sourcevalid)&_bool(ff.u_action_eligible)&ff.label_state.eq('closed_complete_bar_model').to_numpy()&kd.str.fullmatch(r'\d{4}-\d{2}-\d{2}').to_numpy()&kd.le(end).to_numpy()&np.isfinite(target)
        ff=ff.loc[mask].copy();ff['era']=np.where(ff.u_date.lt('2023-01-01'),'early','late')
        for arm in ARMS:
            col='score' if arm=='A' else ('transfer_'+arm+'_score' if case.startswith('transfer_') else arm+'_score')
            ff[arm+'_MSE']=(pd.to_numeric(ff[col])-pd.to_numeric(ff.net_R_stress))**2
        for key,g in ff.groupby(['era','weekly_group','economic_group','commodity_id'],sort=True):
            mse_source.append(dict(case=case,era=key[0],weekly_group=key[1],economic_group=key[2],commodity_id=key[3],known_action_rows=len(g),**{a+'_MSE':float(g[a+'_MSE'].mean()) for a in ARMS}))
    ms=pd.DataFrame(mse_source)
    if not ms.empty:
        ec=ms.groupby(['case','era','weekly_group','economic_group'],as_index=False)[[a+'_MSE' for a in ARMS]].mean()
        mse_weekly=ec.groupby(['case','era','weekly_group'],as_index=False)[[a+'_MSE' for a in ARMS]].mean()
    else:mse_weekly=pd.DataFrame(columns=['case','era','weekly_group']+[a+'_MSE' for a in ARMS])
    annual=[];coverage=[];ecocoverage=[]
    families=sorted(mothers.family_id.unique())
    def coverage_record(part,case,arm,year,**extra):
        means=part.groupby('weekly_group',sort=False).contribution.mean()
        return dict(case=case,arm=arm,year=year,**extra,mothers=len(part),selected=int(_bool(part.selected).sum()),known=int(part.own_known.sum()),unknown=int(part.own_unknown.sum()),sourcevalid_mothers=int(_bool(part.sourcevalid).sum()),source_groups=int(part.weekly_group.nunique()),knownconditional_week_equal_mean=_mean(means),selected_nonparticipation=int(part.selected_nonparticipation.sum()),selected_unmature=int(part.selected_unmature.sum()),selected_ineligible_label=int(part.selected_ineligible_label.sum()))
    for case in CASES:
        for arm in ARMS:
            own=cs.loc[cs.case.eq(case)&cs.arm.eq(arm)]
            for year in map(str,range(2020,2027)):
                part=own.loc[own.year.eq(year)]
                for view in ['mapped','fullmarket']:
                    pp=part.loc[part.commodity_id.ge(0)] if view=='mapped' else part
                    annual.append(coverage_record(pp,case,arm,year,view=view))
                for fid in families:coverage.append(coverage_record(part.loc[part.family_id.eq(fid)],case,arm,year,family_id=fid))
                for group in ECONOMIC_GROUPS:ecocoverage.append(coverage_record(part.loc[part.economic_group.eq(group)],case,arm,year,economic_group=group))
    summary.update(head_support=head_support,forward_support=forward_support,forward_support_counts=forward_support_counts,fullmother_choice_rows=len(cs),mapped_families=5,unmapped_families=90)
    return dict(choices=cs,paired_mothers=pair,group_stats=pd.DataFrame(group_rows),action_MSE_source=ms,action_MSE_weekly=mse_weekly,annual=pd.DataFrame(annual),family_coverage=pd.DataFrame(coverage),economic_coverage=pd.DataFrame(ecocoverage),indices=indices,grids=grids,summary=summary,gate=gate)

def run_actual(args,state):
    if not args.source_go:raise ValueError('--source-go required for root actual')
    go_binding,go=validate_source_go(args.source_go,state)
    output=Path(args.output).resolve()
    if OUTPUT_ROOT.resolve() not in output.parents or output.exists():raise ValueError('fresh stage671 output directory required')
    output.mkdir(parents=True)
    started=time.monotonic();artifacts={};heads={};fit_counts=dict(attempted=0,completed=0)
    protocol=state['protocol'];inputs=SinglePassInputs(state['source_roles'])
    kernel=load_local_module('esr671_kernel','stage670_esr_schema_kernel.py')
    mapping=read_bound_json(protocol['mapping']);family_mapping=mapping['source_to_family']
    scales_by_cutoff={}
    (output/'fit_journal.jsonl').touch(exist_ok=False)
    def event(value):
        with (output/'fit_journal.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(jsonable(value),ensure_ascii=False,allow_nan=False)+'\n');stream.flush()
    artifacts['started']=write_json(output/'started.json',dict(schema='stage671_esr_started_v1',status='started',started_utc=datetime.now(timezone.utc).isoformat(),parent668_fit=0,parent668_cash=0,parent538_original_physical_passes_already_occurred=1,recovery_reads_only_parent668_financial_literals=True,recovery_old538_financial_payload_reads=0,protocol=state['protocol_binding'],source_ready=state['ready_binding'],source_go=go_binding,automatic_retry=False,original_payload_rehashes=0,base_refits=0,cash=0,SQL=0,network=0))
    try:
        calendar=inputs.read_calendar()
        source_frames={}
        for source in protocol['sources']:
            cid=source['commodity_id'];frame=inputs.read_table('esr_source_'+str(cid),SOURCE_COLUMNS)
            if len(frame)!=1951:raise ValueError('all1951 original source rows required per commodity')
            source_frames[cid]=frame
        sources=kernel.prepare_sources(source_frames,protocol['sources'],protocol['clock'])
        if len(sources)!=9755:raise ValueError('all5x1951 source literals required')
        calendar_map=kernel.build_calendar_map(calendar,sources)
        if len(calendar_map)!=5*len(calendar):raise ValueError('complete5source calendar required')
        artifacts['source_literals']=write_frame(output/'source_literals.csv.gz',sources)
        artifacts['source_calendar']=write_frame(output/'source_calendar.csv.gz',calendar_map)
        for cutoff in ['2020-01-01','2023-01-01']:
            scales_by_cutoff[cutoff]=kernel.prefix_scales(sources,cutoff)
        artifacts['prefix_scales']=write_json(output/'prefix_scales.json',scales_by_cutoff)
        del sources,source_frames
        for fold in protocol['folds']:
            scope,cutoff=fold['scope'],fold['cutoff'];role='train_'+scope+'_'+cutoff
            train=inputs.read_table(role,TRAIN,['sequence_index','u_index','u_action_eligible','net_R_stress','sample_weight','Ahat'])
            validate_train(train,fold);validate_calendar_identity(train,calendar)
            train=kernel.feature_rows(train,calendar_map,scales_by_cutoff[cutoff],family_mapping)
            artifacts[role]=write_frame(output/(role+'.csv.gz'),train)
            cases=[(scope,None)]
            if scope=='main':cases += [('transfer_'+g,g) for g in ECONOMIC_GROUPS]
            for case,excluded in cases:
                def on_fit(arm):
                    if arm not in ['B','C'] or fit_counts['attempted']>=24:raise ValueError('24actualfit budget exceeded')
                    fit_counts['attempted']+=1
                    event(dict(event='attempted',case=case,cutoff=cutoff,arm=arm,attempt=fit_counts['attempted']))
                fitted=kernel.fit_heads(train,case,cutoff,excluded_group=excluded,on_fit=on_fit)
                if set(fitted)!=set(['B','C']):raise ValueError('exactB/C heads required')
                for arm in ['B','C']:
                    head=fitted[arm];heads[(case,cutoff,arm)]=head
                    name='head_'+case+'_'+cutoff+'_'+arm
                    artifacts[name]=write_json(output/(name+'.json'),head)
                    if head.get('supported') is True:
                        fit_counts['completed']+=1
                        event(dict(event='completed',case=case,cutoff=cutoff,arm=arm,completed=fit_counts['completed']))
                    else:event(dict(event='unsupported_no_solve',case=case,cutoff=cutoff,arm=arm))
                print(json.dumps(dict(phase='head_pair_complete',case=case,cutoff=cutoff,completed_fit_calls=fit_counts['completed'])),flush=True)
            del train
        if len(heads)!=24 or fit_counts['attempted']!=fit_counts['completed']:raise ValueError('24headdomain/fit journal mismatch')
        forward=inputs.read_table('forward_base_compact',FORWARD,['sequence_index','mother_sequence_index','u_index','u_action_eligible','score','net_R_stress'])
        mothers=inputs.read_table('mothers_forward',MOTHER,['sequence_index','u_index'])
        validate_forward(forward,mothers,protocol);validate_calendar_identity(forward,calendar);validate_calendar_identity(mothers,calendar)
        def enrich_by_cutoff(frame,base_column):
            frame=frame.copy();frame['_original_position']=np.arange(len(frame));pieces=[]
            for cutoff,mask in [('2020-01-01',frame.u_date.lt('2023-01-01')),('2023-01-01',frame.u_date.ge('2023-01-01'))]:
                part=frame.loc[mask].copy()
                if base_column not in part:part[base_column]=0.
                pieces.append(kernel.feature_rows(part,calendar_map,scales_by_cutoff[cutoff],family_mapping))
            return pd.concat(pieces,ignore_index=True).sort_values('_original_position',kind='stable').drop(columns='_original_position').reset_index(drop=True)
        forward=enrich_by_cutoff(forward,'score');mothers=enrich_by_cutoff(mothers,'score').drop(columns='score')
        forward['B_score']=np.nan;forward['C_score']=np.nan
        forward['transfer_B_score']=np.nan;forward['transfer_C_score']=np.nan
        for fold in protocol['folds']:
            scope,cutoff=fold['scope'],fold['cutoff'];mask=forward.scope.eq(scope)&forward.cutoff.eq(cutoff);part=forward.loc[mask]
            for arm in ['B','C']:
                pred=kernel.predict(part,heads[(scope,cutoff,arm)])
                if len(pred)!=len(part) or not np.isfinite(pred).all():raise ValueError('complete finite originalfold score required')
                forward.loc[mask,arm+'_score']=pred
            if scope=='main':
                for group in ECONOMIC_GROUPS:
                    gm=mask&forward.economic_group.eq(group);gp=forward.loc[gm]
                    for arm in ['B','C']:
                        pred=kernel.predict(gp,heads[('transfer_'+group,cutoff,arm)])
                        if len(pred)!=len(gp) or not np.isfinite(pred).all():raise ValueError('complete finite transfer score required')
                        forward.loc[gm,'transfer_'+arm+'_score']=pred
        unavailable=~_bool(forward.sourcevalid)
        for arm in ['B','C']:
            if not np.array_equal(forward.loc[unavailable,arm+'_score'].to_numpy(float).view(np.uint64),forward.loc[unavailable,'score'].to_numpy(float).view(np.uint64)):raise ValueError('invalid source notbitwiseA fallback')
        mainmapped=forward.scope.eq('main')&forward.commodity_id.ge(0)
        for arm in ['B','C']:
            if not np.isfinite(forward.loc[mainmapped,'transfer_'+arm+'_score']).all() or forward.loc[~mainmapped,'transfer_'+arm+'_score'].notna().any():raise ValueError('transfer score domain must be mappedmain only')
            invalid=mainmapped&unavailable
            if not np.array_equal(forward.loc[invalid,'transfer_'+arm+'_score'].to_numpy(float).view(np.uint64),forward.loc[invalid,'score'].to_numpy(float).view(np.uint64)):raise ValueError('transfer invalid notexactA')
        artifacts['forward_thin']=write_frame(output/'forward_thin.csv.gz',forward)
        artifacts['mothers_thin']=write_frame(output/'mothers_thin.csv.gz',mothers)
        choices,records=choose_all(forward,mothers,calendar,protocol['scope']['forward_end'])
        stats=policy_statistics(choices,forward,mothers,calendar_map,kernel,heads,protocol['scope']['forward_end'])
        for name,key in [('choices','choices'),('paired_mothers','paired_mothers'),('weekly_statistics','group_stats'),('action_MSE_source','action_MSE_source'),('action_MSE_weekly','action_MSE_weekly'),('annual','annual'),('family_coverage','family_coverage'),('economic_coverage','economic_coverage')]:artifacts[name]=write_frame(output/(name+'.csv.gz'),stats[key])
        for era in ['early','late']:
            path=output/('bootstrap_indices_'+era+'.npy')
            with path.open('xb') as stream:np.save(stream,np.asarray(stats['indices'][era]),allow_pickle=False)
            artifacts['bootstrap_indices_'+era]=output_binding(path)
        artifacts['bootstrap_grids']=write_json(output/'bootstrap_grids.json',stats['grids'])
        artifacts['selection_records']=write_json(output/'selection_records.json',records)
        artifacts['gate']=write_json(output/'gate.json',stats['gate'])
        if set(inputs.records)!=set(state['source_roles']):raise ValueError('exact14inputs each once required')
        inputs.verify_final_stats()
        financial_bytes=sum(r['accepted_binding']['bytes'] for name,r in inputs.records.items() if name!='calendar' and not name.startswith('esr_source_'))
        if financial_bytes!=protocol['implementation']['financial_compressed_read_budget']:raise ValueError('financial bytebudget differs')
        small_inputs=[*map(protocol['schema_recovery'].__getitem__,['parent_manifest','parent_terminal','independent_confirmation']),state['protocol_binding'],protocol['mapping'],protocol['method_advisory_notes'],state['ready']['method_review'],state['ready']['fixture_receipt'],state['ready_binding'],go_binding,go['reviewer_ready']]
        for b in state['ready']['sources']+small_inputs:
            if small_binding(b['path'])[0]!=simple(b):raise ValueError('frozen small source changed '+b['path'])
        artifacts['source_io_receipt']=write_json(output/'source_io_receipt.json',dict(schema='stage671_single_pass_io_v1',records=inputs.records,compressed_financial_bytes=financial_bytes,separate_old_payload_hash_passes=0,model_reads=0,scaler_reads=0,COMMON_reads=0,native_reads=0,old_choice_reads=0,SQL=0,network=0,original_source_mutations=False,parent668_fit=0,parent668_cash=0,parent538_original_physical_passes_already_occurred=1,recovery_reads_only_parent668_financial_literals=True,recovery_old538_financial_payload_reads=0,small_source_csv_second_attempt_passes=5))
        summary=dict(stats['summary']);summary.update(status='completed',actual_fit_calls_attempted=fit_counts['attempted'],actual_fit_calls_completed=fit_counts['completed'],head_objects=len(heads),supported_heads=sum(h.get('supported') is True for h in heads.values()),base_refits=0,new_cash=0,SQL=0,network=0,full_forward_rows=len(forward),main_mothers=len(mothers),registered_products=98,registered_families=95,old_choices_read=False,old_offsets_consumed=False,parent668_fit=0,parent668_cash=0,parent538_original_physical_passes_already_occurred=1,recovery_old538_financial_payload_reads=0,goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        artifacts['summary']=write_json(output/'summary.json',summary);artifacts['fit_journal']=output_binding(output/'fit_journal.jsonl')
        terminal=dict(schema='stage671_esr_terminal_v1',status='completed',exit_code=0,actual_fit_calls_attempted=fit_counts['attempted'],actual_fit_calls_completed=fit_counts['completed'],base_refits=0,cash=0,SQL=0,network=0,automatic_retry=False,elapsed_seconds=time.monotonic()-started,goal_complete=False)
        artifacts['terminal']=write_json(output/'terminal.json',terminal)
        write_json(output/'manifest.json',dict(schema='stage671_esr_quantity_actual_v1',status='completed',protocol=state['protocol_binding'],source_ready=state['ready_binding'],source_go=go_binding,sources=state['ready']['sources'],artifacts=artifacts,actual_fit_calls_attempted=fit_counts['attempted'],actual_fit_calls_completed=fit_counts['completed'],base_refits=0,cash=0,SQL=0,network=0,goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        return terminal
    except BaseException as error:
        if not (output/'terminal.json').exists():
            artifacts['terminal']=write_json(output/'terminal.json',dict(schema='stage671_esr_terminal_v1',status='failed',exit_code=1,actual_fit_calls_attempted=fit_counts['attempted'],actual_fit_calls_completed=fit_counts['completed'],base_refits=0,cash=0,SQL=0,network=0,automatic_retry=False,error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-started,source_io_records=inputs.records))
        if not (output/'manifest.json').exists():write_json(output/'manifest.json',dict(schema='stage671_esr_quantity_actual_v1',status='failed',protocol=state['protocol_binding'],source_ready=state['ready_binding'],source_go=go_binding,sources=state['ready']['sources'],artifacts=artifacts,actual_fit_calls_attempted=fit_counts['attempted'],actual_fit_calls_completed=fit_counts['completed'],base_refits=0,cash=0,SQL=0,network=0,automatic_retry=False,goal_complete=False))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=PROTOCOL)
    parser.add_argument('--protocol-sha256',default=PROTOCOL_SHA)
    parser.add_argument('--source-ready',type=Path,required=True)
    parser.add_argument('--source-go',type=Path)
    parser.add_argument('--output',type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-source',action='store_true');mode.add_argument('--actual',action='store_true')
    args=parser.parse_args(argv)
    state=validate_source_ready(args.protocol,args.protocol_sha256,args.source_ready)
    if args.check_source:
        print(json.dumps(dict(status='source_checked',financial_payload_reads=0,model_reads=0,scaler_reads=0,actual_fit=0,cash=0,protocol=state['protocol_binding'],source_ready=state['ready_binding'],source_roles=len(state['source_roles'])),ensure_ascii=False),flush=True)
        return
    if args.output is None:parser.error('--actual requires --output')
    print(json.dumps(jsonable(run_actual(args,state)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
