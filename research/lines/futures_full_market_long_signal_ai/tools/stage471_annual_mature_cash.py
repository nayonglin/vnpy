"""Stage471 fixed annual mature COMMON52 candidate: four continuous cache-only books.

Import has no source/data/cache/cash I/O. Only Stage470's bound derived handoff
enters the unchanged accepted157/131 cash kernel. The original129 actions and
COMMON matrix are never opened by this adapter. Annual signals are stitched
before cash, with no year-end liquidation or capital reset.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='f62281e099200e065785b61cc89a47a2111fe7d3dbf2ec60102b167b0708d4f6'
CANDIDATE='C_RESEARCH_COMMON52_FIXED_ANNUAL_MATURE_UPDATE'
FIXTURE=LINE/'outputs/stage471_annual_mature_cash/synthetic_fixture.py'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION_FIELDS=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
    'entry_capacity_qty','N_u','low20_u','u_close']
HANDOFF_ROLES=('protocol','fit_manifest','main_choices','held_diagnostic','full_mothers_projection',
    'selected_actions','calendar','boundaries')


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_bytes(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
        raise ValueError('bound input differs '+b['path'])
    return raw


def read_json(b):return json.loads(read_bytes(b))


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    tmp.replace(path)


def source_bundle():return [binding(Path(__file__)),binding(FIXTURE)]


def numeric(frame,columns):
    for col in columns:
        if col in frame:frame[col]=pd.to_numeric(frame[col].replace('',np.nan),errors='raise')
    return frame


def read_table(b,*,usecols=None):
    return pd.read_csv(io.BytesIO(read_bytes(b)),compression='gzip' if b['path'].endswith('.gz') else None,
        usecols=usecols,dtype=str,keep_default_na=False,float_precision='round_trip')


def decode_calendar(cal):
    """Match Stage470: integer source dates are YYYYMMDD, never epoch days."""
    return ([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:] for v in cal]
            if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())


def prepare_choices(mothers,choices,expected_parents=161014):
    forward=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if len(forward)!=expected_parents or len(choices)!=expected_parents or choices.event_id.duplicated().any():
        raise ValueError('complete ordered forward parent choices required')
    for col in MOTHER_FIELDS:
        a,b=forward[col].reset_index(drop=True),choices[col].reset_index(drop=True)
        equal=(a.astype(float).tolist()==b.astype(float).tolist()) if col in ('sequence_index','u_index') else a.astype(str).tolist()==b.astype(str).tolist()
        if not equal:raise ValueError('original complete parent identity differs '+col)
    if set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'} or set(choices.arm)!={'VOLUNTARY_RESELECT'}:
        raise ValueError('main unchanged NARROW/VOLUNTARY_RESELECT helper choices required')
    # Cash's cutoff remains the original deployment fold, never the annual fit cutoff.
    deployment=np.where(choices.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
    annual=choices.u_date.str.slice(0,4)+'-01-01'
    for col in ('cutoff','deployment_fold_cutoff'):
        if col not in choices or choices[col].tolist()!=deployment.tolist():
            raise ValueError('original deployment cutoff must not split yearly cash '+col)
    if 'training_cutoff' not in choices or choices.training_cutoff.tolist()!=annual.tolist():
        raise ValueError('same-year annual training cutoff required')
    picked=choices.copy();selected=picked.selected.astype(float)
    if not selected.isin([0,1]).all():raise ValueError('binary selected required')
    picked['selected']=selected.astype(int)
    ids=set(picked.loc[picked.selected.eq(1),'chosen_action_id'])
    if '' in ids or len(ids)!=int(picked.selected.sum()):raise ValueError('unique nonempty selected action IDs required')
    numeric(picked,['sequence_index','u_index','chosen_action_sequence_index','score'])
    if not np.isfinite(picked.loc[picked.selected.eq(1),'score']).all():raise ValueError('finite selected scores required')
    return picked,ids


def load_handoff_tables(handoff,*,expected_mothers=399252,expected_parents=161014,expected_products=98,expected_families=95):
    """Only bound new projections. No fallback to original mothers/actions/COMMON."""
    mothers=read_table(handoff['full_mothers_projection_binding'])
    if list(mothers.columns)!=MOTHER_FIELDS:raise ValueError('exact seven mother identity fields required')
    numeric(mothers,['sequence_index','u_index'])
    if (len(mothers)!=expected_mothers or mothers.event_id.duplicated().any() or
            mothers.product_id.nunique()!=expected_products or mothers.family_id.nunique()!=expected_families):
        raise ValueError('full canonical mother projection required')
    choices=read_table(handoff['main_choices_binding']);picked,ids=prepare_choices(mothers,choices,expected_parents)
    actions=read_table(handoff['selected_actions_binding'])
    if list(actions.columns)!=ACTION_FIELDS:raise ValueError('exact16 selected action fields required')
    if actions.action_id.duplicated().any() or set(actions.action_id)!=ids or len(actions)!=len(ids):
        raise ValueError('derived selected action projection must cover each candidate ID exactly once')
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    return mothers,picked,actions


def exact_cash_signals(candidate,control):
    """All assembled fields and row priorities, not just selected IDs, must agree.

    Native/calendar/economics/canonical mother identity and K bindings are checked
    separately before this function. Compare numeric values exactly, with matching
    missingness; no tolerance/epsilon can activate the zero-cash branch.
    """
    if list(candidate.columns)!=list(control.columns) or len(candidate)!=len(control):
        return dict(identical=False,reason='signal schema or row count differs',candidate_rows=len(candidate),control_rows=len(control))
    mismatches={}
    for col in candidate:
        a=candidate[col].reset_index(drop=True);b=control[col].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(a):
            b=pd.to_numeric(b.replace('',np.nan),errors='raise');equal=(a.eq(b)|(a.isna()&b.isna()))
        else:equal=a.fillna('').astype(str).eq(b.fillna('').astype(str))
        n=int((~equal).sum())
        if n:mismatches[col]=n
    return dict(identical=not mismatches,candidate_rows=len(candidate),control_rows=len(control),
        all_signal_fields=list(candidate.columns),mismatches=mismatches,selected_ID_equality_alone_never_used=True,
        ranking_score_and_row_priority_included=True,tolerance=0)


def accepted_controls(protocol):
    controls=protocol['cash_contract_inherited_exact']['control_accounts_reused']
    keyed={(c['window'],c['cost']):c for c in controls}
    if len(controls)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('all four accepted157 OWN controls required')
    for (w,c),item in keyed.items():
        expected='NARROW_VOLUNTARY_RESELECT_'+w+'_'+c
        if item['account_id']!=expected or Path(item['directory']).name!=expected or 'stage157_voluntary_cash' not in item['directory']:
            raise ValueError('accepted157 OWN account identity differs')
        read_json(item['summary'])
        for role in item['ledgers_relative_to_directory']:read_bytes(control_ledger_binding(item,role))
    return controls


def control_ledger_binding(control,role):
    item=control['ledgers_relative_to_directory'][role]
    return dict(path=str(Path(control['directory'])/item['file']),bytes=item['bytes'],sha256=item['sha256'])


def fixed_gate(points,annual,held,*,wealth_positive,any_stale=False,execution_unknown=False):
    keyed={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:raise ValueError('four fixed paired comparisons required')
    finite=lambda x:x is not None and math.isfinite(float(x))
    primary=keyed[('primary_2020','stress')];checks={}
    for key,p in keyed.items():
        strict=p is primary;ret=p.get('return_percentage_point_difference');dd=p.get('drawdown_percentage_point_difference')
        checks['_'.join(key)]=dict(positive_return=finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0,
            return_improvement=finite(ret) and (ret>0 if strict else ret>=0),drawdown_improvement=finite(dd) and (dd>0 if strict else dd>=0))
    ci=finite(primary.get('ci95_low')) and primary['ci95_low']>0
    nominal=bool(all(all(v.values()) for v in checks.values()) and ci and wealth_positive)
    groups=held.get('groups',{})
    if set(groups)!={'holdout_0','holdout_1'}:raise ValueError('both original held groups required')
    family={g:finite(x.get('known_u_equal_mean_increment_R')) and x['known_u_equal_mean_increment_R']>=0 for g,x in groups.items()}
    unknowns={g:x.get('unknown_differential_selected_events') for g,x in groups.items()}
    if any(isinstance(n,bool) or not isinstance(n,(int,np.integer)) or n<0 for n in unknowns.values()):
        raise ValueError('explicit nonnegative held unknown event counts required')
    held_unknown=any(n>0 for n in unknowns.values());held_known=all(family.values())
    financial_unknown=bool(any_stale or execution_unknown or not all(finite(p.get('drawdown_percentage_point_difference')) for p in points))
    status=('unsupported' if not (nominal and held_known) else 'unknown_historical_stale' if any_stale else
        'unknown_execution_capacity_or_entry' if execution_unknown else 'unknown_differential_held_outcome' if held_unknown else 'nominal_policy_pass_unqualified')
    return dict(status=status,cash_nominal_pass=nominal,held_known_nominal_pass=bool(held_known),
        nominal_all_fixed_gates_pass=bool(nominal and held_known),nominal_pass=bool(nominal and held_known and not financial_unknown and not held_unknown),
        predicates=checks,primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth_positive),
        held_known_mean_nonnegative=family,held_unknown_differential_selected_events=unknowns,held_signal_unknown=bool(held_unknown),
        unknown_bounds_available=False,financial_unknown=financial_unknown,any_historical_stale=bool(any_stale),execution_unknown=bool(execution_unknown),
        annual_disclosure_rows=len(annual),annual_or_sharpe_hard_gate_added=False,full_family_generalization_certified=False,
        independent_actual_review_required=True,no_automatic_promotion=True,production_qualified=False,increased_betting_qualified=False,
        goal_complete=False,alpha_proved=False,interpretation='Exact157 economics plus separate held disclosure; unbounded unknowns cannot certify; conditional historical evidence only')


def pair_years(candidate,control):
    a={r['year']:r for r in candidate};b={r['year']:r for r in control}
    if set(a)!=set(b):raise ValueError('paired yearly source coverage differs')
    rows=[]
    for year in sorted(a):
        x,y=a[year],b[year]
        diff=lambda k:None if x.get(k) is None or y.get(k) is None else x[k]-y[k]
        rows.append(dict(year=year,partial=str(year)=='2026',candidate_return_pct=x['return_pct'],control_return_pct=y['return_pct'],
            candidate_growth_amount=x['cash_growth'],control_growth_amount=y['cash_growth'],candidate_max_drawdown_pct=x['max_drawdown_pct'],
            control_max_drawdown_pct=y['max_drawdown_pct'],return_percentage_point_difference=diff('return_pct'),
            growth_amount_difference=diff('cash_growth'),drawdown_percentage_point_difference=diff('max_drawdown_pct')))
    return rows


def account_specs():return [dict(candidate=CANDIDATE,window=w,cost=c,account_id=f'NARROW_{CANDIDATE}_{w}_{c}') for w in WINDOWS for c in COSTS]


def run_account(state,spec):
    a,b=state['bounds'][spec['window']]
    return state['v'].kernel.run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
        spec['cost'],spec['account_id'],a,b,prepared=state['prepared'])


def validate_report_recovery(out,metadata,original,previous,checkpoint_binding,checkpoint,authorization):
    """Authorize only a report-source change; protocol, handoff and books stay exact."""
    if authorization is None:raise ValueError('exact root authorization required for changed report source')
    auth=read_json(authorization)
    expected=dict(schema='stage471_exact_report_recovery_authorization_v1',authorized_by='root',mode='reports_only',
        output=str(out),protocol_sha256=PROTOCOL_SHA,new_cash=0,native_cache_loads=0,SQL=0)
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('root report-only authorization identity/budget differs')
    old_meta=original['metadata'];unchanged={k:v for k,v in old_meta.items() if k!='source_bundle'}
    if {k:v for k,v in metadata.items() if k!='source_bundle'}!=unchanged or auth.get('unchanged_non_source_metadata')!=unchanged:
        raise ValueError('report recovery must preserve every non-source metadata field')
    if auth.get('old_book_source_bundle')!=old_meta.get('source_bundle') or auth.get('new_report_source_bundle')!=metadata.get('source_bundle'):
        raise ValueError('explicit old cash and new report source bindings differ')
    if checkpoint.get('metadata')!=old_meta or not same(auth['book_checkpoints'],checkpoint_binding) or auth.get('books')!=checkpoint['books']:
        raise ValueError('root recovery must bind the exact original four raw books')
    for role,file in [('failed_manifest','manifest.json'),('failed_terminal','actual_terminal.json')]:
        frozen=auth[role];read_bytes(frozen);live=binding(out/file)
        if any(frozen[k]!=live[k] for k in ('bytes','sha256')):raise ValueError('failed report evidence differs '+role)
    if read_json(auth['failed_manifest'])!=previous:raise ValueError('failed manifest snapshot differs')
    terminal=read_json(auth['failed_terminal'])
    if terminal.get('cash_accounts_started')!=4 or terminal.get('cash_accounts_completed')!=4:
        raise ValueError('four completed cash books must precede report-only source recovery')
    return auth


def run_four(output,run_account_fn,export_account,*,before=None,finalize=None,metadata=None,reports_only=False,report_authorization=None):
    """Checkpoint every complete raw book BEFORE any reporting; never retry cash.

    A report-only continuation requires all four bound checkpoints, and calls no
    kernel or source/native prepare callback. Failed kernel attempts are retained
    and cannot be resumed automatically or silently replaced by fresh books.
    """
    out=Path(output).resolve();meta=dict(metadata or {});began=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    records=[];checkpoints=[];started=completed=0;new_started=0;status='failed';error=None;attempt=1;skip=False
    old_book_source=meta.get('source_bundle',[])
    if reports_only:
        original=json.loads((out/'actual_started.json').read_text())
        previous=json.loads((out/'manifest.json').read_text())
        checkpoint_binding=next(b for b in previous['artifacts'] if Path(b['path'])==out/'book_checkpoints.json')
        cp=read_json(checkpoint_binding);checkpoints=cp['books']
        if original['metadata']!=meta or report_authorization is not None:
            validate_report_recovery(out,meta,original,previous,checkpoint_binding,cp,report_authorization)
        old_book_source=original['metadata'].get('source_bundle',[])
        if cp['cash_accounts_started']!=4 or cp['cash_accounts_completed']!=4 or len(checkpoints)!=4:
            raise ValueError('all four completed cash checkpoints required for report-only continuation')
        started=completed=4;attempt=1+len(list(out.glob('attempt_*_terminal.json')))
        write_json(out/f'attempt_{attempt}_report_started.json',dict(started_at=began,metadata=meta,new_cash_this_process=0,
            old_book_source=old_book_source,new_report_source=meta.get('source_bundle',[]),report_recovery_authorization=report_authorization,
            native_cache_loads_this_process=0))
    else:
        out.mkdir(parents=True,exist_ok=False)
        write_json(out/'actual_started.json',dict(stage=471,started_at=began,metadata=meta))
    def progress(phase,account=None):
        write_json(out/'cash_progress.json',dict(phase=phase,cash_accounts_started=started,cash_accounts_completed=completed,
            new_cash_this_process=new_started,current_account=account,max_new_candidate_cash=4,new_fit=0,old_control_replays=0))
    progress('reports_only' if reports_only else 'preparing')
    try:
        if not reports_only:
            prep=before(out) if before else None
            skip=bool(prep and prep.get('reuse_records') is not None)
            if skip:records=prep['reuse_records'];progress('identical_cash_inputs_zero_new_cash')
            else:
                for spec in account_specs():
                    started+=1;new_started+=1;progress('kernel_running',spec['account_id'])
                    book=run_account_fn(spec)
                    path=out/'checkpoints'/(spec['account_id']+'.pickle.gz');path.parent.mkdir(parents=True,exist_ok=True)
                    tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(gzip.compress(pickle.dumps(book,protocol=5),mtime=0));tmp.replace(path)
                    completed+=1;checkpoints.append(dict(spec=spec,book=binding(path)))
                    write_json(out/'book_checkpoints.json',dict(schema='stage471_completed_raw_books_v1',cash_accounts_started=started,
                        cash_accounts_completed=completed,books=checkpoints,metadata=meta))
                    progress('book_checkpoint_complete',spec['account_id']);del book
        if not skip:
            for item in checkpoints:
                spec=item['spec'];progress('reporting_checkpoint',spec['account_id'])
                book=pickle.loads(gzip.decompress(read_bytes(item['book'])))
                record=export_account(spec,book);records.append(record)
                write_json(out/'report_checkpoints.json',dict(attempt=attempt,accounts=records,raw_books_replayed=False))
                del book
        if finalize:finalize(out,records)
        status='completed';progress('completed');return records
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,attempt=attempt,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,cash_accounts_started=started,cash_accounts_completed=completed,
            new_cash_this_process=new_started,identical_inputs_reused=skip,max_new_candidate_cash=4,new_fit=0,old_control_replays=0,
            SQL=0,auto_retry=False,goal_complete=False,production_qualified=False)
        if reports_only:terminal.update(native_cache_loads_this_process=0,report_recovery_authorization=report_authorization)
        write_json(out/f'attempt_{attempt}_terminal.json',terminal);write_json(out/'actual_terminal.json',terminal)
        artifacts=[binding(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json' and not f.name.endswith('.tmp')]
        direct={name:binding(out/file) for name,file in dict(account_summaries='account_summaries.csv.gz',
            comparisons='comparisons.csv.gz',annual_slices='annual_slices.csv.gz',paired_annual='paired_annual.csv.gz',
            bootstrap_distributions='bootstrap_distributions.csv.gz',family_year_including_zero='family_year_including_zero.csv.gz',
            diagnostics='diagnostics.json',decision='decision.json',signals='signals_candidate.csv.gz',
            source_read_receipt='source_read_receipt.json',book_checkpoints='book_checkpoints.json',
            complete_cash_input_identity='complete_cash_input_identity.json').items() if (out/file).is_file()}
        write_json(out/'manifest.json',dict(schema='stage471_annual_mature_cash_manifest_v1',status=status,candidate=CANDIDATE,
            protocol_sha256=PROTOCOL_SHA,accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,
            metadata=meta,**direct,new_fit=0,new_cash_accounts=completed,cash_accounts_started=started,old_control_replays=0,native_source_queries=0,
            old_book_source=old_book_source,new_report_source=meta.get('source_bundle',[]),report_recovery_authorization=report_authorization,
            goal_complete=False,production_qualified=False))


def load_runtime(protocol,old_manifest):
    b=protocol['input_bindings']['original157_source']
    if not same(binding(b['path']),b):raise ValueError('frozen accepted157 adapter source differs')
    spec=importlib.util.spec_from_file_location('stage471_accepted157',TOOLS/'stage157_voluntary_cash.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    # This checks the reused execution code only, never a Con4 model/source gate.
    actual=v.source_bundle();frozen=old_manifest['source_bundle']
    if sorted(actual,key=lambda b:b['path'])!=sorted(frozen,key=lambda b:b['path']):raise ValueError('accepted157 execution helper bytes differ')
    r=v.reuse
    if (r.ref.INITIAL,r.ref.SINGLE_RISK,r.ref.TOTAL_RISK,r.ref.MARGIN_CAP,r.ref.MARGIN_BUFFER)!=(1000000,.0025,.02,.25,1.1):
        raise ValueError('unchanged accepted131 risk constants required')
    return v


def validate_protocol(args):
    out=Path(args.output).resolve();root=LINE/'outputs/stage471_annual_mature_cash'
    if root not in out.parents:raise ValueError('Stage471 output root required')
    pb=binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact frozen469 protocol required')
    p=read_json(pb)
    if p.get('schema')!='stage469_fixed_annual_mature_COMMON52_update_protocol_v1' or p['candidate']['name']!=CANDIDATE:
        raise ValueError('fixed annual COMMON52 identity differs')
    if not p['authorization']['implementation_and_one_actual_within_budgets']:raise ValueError('frozen research authorization missing')
    c=p['cash_contract_inherited_exact']
    if tuple(c[k] for k in ('initial_capital','single_family_risk','total_risk','buffered_margin_cap','margin_buffer','initial_stop_N','participation_rate'))!=(1000000,.0025,.02,.25,1.1,.25,.01):
        raise ValueError('unchanged execution constants required')
    if c['new_accounts_max']!=4 or c['new_SQL_or_native_downloads']!=0 or c['windows']!={k:list(v) for k,v in BOUNDS.items()}:
        raise ValueError('fixed four-window zero-SQL cash budget differs')
    ci=c['CI']
    if (ci['block_length'],ci['repetitions'],ci['reuse_exact_indices_no_regeneration'])!=(252,2000,True):
        raise ValueError('original CI252/2000 indices must be reused exactly')
    hb=binding(args.handoff)
    if hb['sha256']!=args.handoff_sha256:raise ValueError('470 handoff SHA differs')
    h=read_json(hb)
    if h.get('schema')!='stage470_annual_mature_cash_handoff_v1' or h.get('candidate')!=CANDIDATE or h.get('protocol_sha256')!=PROTOCOL_SHA:
        raise ValueError('completed470 annual handoff identity differs')
    if not same(h['protocol_binding'],pb):raise ValueError('470 protocol binding differs')
    fit_parent=Path(h['fit_manifest_binding']['path']).resolve().parent
    if LINE/'outputs/stage470_annual_mature_fit_select' not in fit_parent.parents:
        raise ValueError('new470 handoff source root required')
    for role in ('main_choices','held_diagnostic','full_mothers_projection','selected_actions'):
        if Path(h[role+'_binding']['path']).resolve().parent!=fit_parent:raise ValueError('derived470 input root differs '+role)
    # The protocol itself is the user-authorized research scope. No extra approval file.
    return out,p,pb,h,hb


def execute(args):
    out,p,pb,h,hb=validate_protocol(args);bundle=source_bundle();state={}
    old=read_json(p['control']['cash_manifest']);cash=p['cash_contract_inherited_exact'];market_deps=cash['market_dependencies_inherited']
    metadata=dict(protocol=pb,handoff=hb,fit_manifest=h['fit_manifest_binding'],source_bundle=bundle,
        research_authorization=p['authorization'],fixture=False,annual_liquidation=False,capital_reset=False)

    def report_context(context):
        v=load_runtime(p,old);r=v.reuse
        economics=json.loads(read_bytes(market_deps['economic_projection']))['instruments']
        state.update(v=v,r=r,controls=cash['control_accounts_reused'],economics=economics,
            families=context['families'],held=context['held'],receipt=context['receipt'],cache_meta=context['cache_meta'],
            summaries={},reports={},daily={},family_tables=[],identical=False)

    def prepare(folder):
        manifest=read_json(h['fit_manifest_binding'])
        if manifest.get('status')!='completed' or manifest.get('candidate')!=CANDIDATE or manifest.get('protocol_sha256')!=PROTOCOL_SHA:
            raise ValueError('completed470 fit/selection manifest required')
        for role,artifact in [('main_choices','choices_main'),('held_diagnostic','held_diagnostic'),
                ('full_mothers_projection','full_mothers_projection'),('selected_actions','selected_actions'),
                ('calendar','calendar'),('boundaries','boundaries')]:
            if not same(h[role+'_binding'],manifest['artifacts'][artifact]):
                raise ValueError('470 handoff/manifest artifact closure differs '+role)
        controls=accepted_controls(p);v=load_runtime(p,old);r=v.reuse
        mothers,picked,actions=load_handoff_tables(h)
        boundaries=read_json(h['boundaries_binding'])
        if boundaries.get('schema')!='stage156_voluntary_K_only_v1' or boundaries.get('account_deadline_certified') is not False:
            raise ValueError('unchanged noncertified voluntary common K required')
        original_choices=read_json(p['control']['choices_manifest'])
        frozen_boundary=original_choices['artifacts']['boundaries']
        old_boundaries=read_json(frozen_boundary)
        for key in ('schema','epochs','policy_version','sample_end','calendar','account_deadline_certified'):
            if boundaries.get(key)!=old_boundaries.get(key):
                raise ValueError('original common-K boundary values differ '+key)
        calendar=decode_calendar(np.load(io.BytesIO(read_bytes(h['calendar_binding'])),allow_pickle=False))
        cb=market_deps['calendar']
        if h['calendar_binding']['sha256']!=cb['sha256'] or h['calendar_binding']['bytes']!=cb['bytes']:
            raise ValueError('original exact calendar copy differs')
        store,receipt,cache_meta=r.cache_source.restore_native_cache(market_deps['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0 or not same(receipt['cache_file'],market_deps['native_cache']):
            raise ValueError('one frozen native cache load and zero SQL required')
        market,dates=r.CachedMarket(store),store.calendar
        if dates!=calendar:raise ValueError('handoff/source native calendar differs')
        economics=json.loads(read_bytes(market_deps['economic_projection']))['instruments']
        if set(economics)!=set(store.series):raise ValueError('frozen cache/economic epochs differ')
        signals=v.make_voluntary_signals(actions,mothers,picked,boundaries['epochs'],market,dates,economics)
        if len(signals)!=int(picked.selected.sum()):raise ValueError('new selected action admission differs')
        bounds={}
        for w in WINDOWS:
            a,b=(int(np.searchsorted(dates,d)) for d in BOUNDS[w])
            if b>=len(dates) or dates[b]!=BOUNDS[w][1]:raise ValueError('fixed endpoint absent from calendar')
            bounds[w]=(a,b)
        held=read_json(h['held_diagnostic_binding']);families=sorted(mothers.family_id.unique())
        state.update(v=v,r=r,signals=signals,dates=dates,market=market,economics=economics,prepared=v.author.organize(signals,mothers,dates),
            bounds=bounds,receipt=receipt,cache_meta=cache_meta,controls=controls,families=families,
            summaries={},reports={},daily={},family_tables=[],held=held,identical=False)
        context=dict(families=families,held=held,receipt=receipt,cache_meta=cache_meta)
        write_json(folder/'report_context.json',context)
        r.ref.write_table(folder/'signals_candidate.csv.gz',signals,[])
        trace=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
        r.ref.write_table(folder/'boundary_lineage.csv.gz',signals[trace],[])
        r.ref.write_table(folder/'annual_deployment_lineage.csv.gz',picked[MOTHER_FIELDS+['training_cutoff','deployment_fold_cutoff','cutoff','selected','chosen_action_id','score']],[])
        old_signals=read_table(old['signals']);identity=exact_cash_signals(signals,old_signals)
        identity.update(unchanged_calendar=cb,unchanged_economics=market_deps['economic_projection'],
            unchanged_native_cache=market_deps['native_cache'],unchanged_common_K=frozen_boundary,
            canonical_complete_mothers_source=p['input_bindings']['original_mothers'],projection=h['full_mothers_projection_binding'])
        write_json(folder/'complete_cash_input_identity.json',identity)
        write_json(folder/'source_read_receipt.json',dict(receipt,candidate=CANDIDATE,new_selected_actions=len(actions),
            main_parent_rows=len(picked),full_mother_rows=len(mothers),cash_native_cache_loads=1,
            original_actions_reads_this_cash_process=0,COMMON_reads_this_cash_process=0,original_mothers_reads_this_cash_process=0,
            derived_selected_action_reads=1,derived_action_fields=ACTION_FIELDS,derived_mother_reads=1,
            original_canonical_from_full_mother_projection=True,annual_scores_only_no_year_reset=True,
            new_fit=0,old_control_replays=0,models_scores_labels_read=0,selectors_called=0))
        write_json(folder/'control_references.json',controls)
        if identity['identical']:
            state['identical']=True;control_reports=read_json(old['diagnostics']);records=[]
            for spec in account_specs():
                c=next(x for x in controls if (x['window'],x['cost'])==(spec['window'],spec['cost']))
                summary=read_json(c['summary']);key=(spec['window'],spec['cost'])
                state['summaries'][key]=dict(summary,**spec,role='candidate_exact_control_reuse',arm=CANDIDATE,
                    any_historical_stale=control_reports[c['account_id']]['stale_days']>0,reused_from_account=c['account_id'])
                state['reports'][spec['account_id']]=control_reports[c['account_id']]
                state['daily'][key]=pd.read_csv(io.BytesIO(read_bytes(control_ledger_binding(c,'daily'))),compression='gzip',float_precision='round_trip')
                records.append(dict(spec,directory=c['directory'],summary=c['summary'],ledgers=c['ledgers_relative_to_directory'],
                    replayed=False,exact_identity_reuse=True,reused_from_account=c['account_id']))
            return dict(reuse_records=records)

    def export(spec,book):
        r=state['r'];folder=out/spec['account_id']
        ledgers=r.write_ledgers(folder,book);summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,arm=CANDIDATE,source_helper_arm='VOLUNTARY_RESELECT',role='candidate',
            any_historical_stale=report['stale_days']>0,execution_unknown=book['execution_unknown'],
            unknown_capacity_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_tick_fills,slippage_already_in_fill_price=True,
            transaction_count_definition='closed_trades=closed roots; fills=all BUY/SELL fills; total_filled_qty=quantity')
        key=(spec['window'],spec['cost']);state['summaries'][key]=summary;state['reports'][spec['account_id']]=report;state['daily'][key]=pd.DataFrame(book['daily'])
        state['family_tables'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec,arm=CANDIDATE))
        groups,tails=r.extra_reports(book)
        for name,value in [('summary',summary),('diagnostics',report),('largest_wins_losses',tails)]:write_json(folder/(name+'.json'),r.kernel.original.safe(value))
        r.ref.write_table(folder/'sector_variant_attribution.csv.gz',groups,[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers)

    def finalize(folder,records):
        r=state['r'];control_reports=read_json(old['diagnostics']);points=[];annual=[];paired_year=[];distributions={}
        metrics=list(state['summaries'].values());indices={};control_summaries=[];control_frames=[]
        for w,b in cash['CI']['indices'].items():
            indices[w]=np.load(io.BytesIO(read_bytes(b)),allow_pickle=False)
            if indices[w].shape[0]!=2000:raise ValueError('original2000 CI repetitions required')
        controls={(c['window'],c['cost']):c for c in state['controls']}
        for spec in account_specs():
            key=(spec['window'],spec['cost']);control=controls[key];baseline=read_json(control['summary']);active=state['summaries'][key]
            cd=pd.read_csv(io.BytesIO(read_bytes(control_ledger_binding(control,'daily'))),compression='gzip',float_precision='round_trip')
            stats,dist=r.paired_statistics(state['daily'][key],cd,indices[key[0]])
            control_summaries.append(baseline);control_frames.append(cd)
            points.append(dict(spec,control_account_id=control['account_id'],ending_equity_difference=active['ending_equity']-baseline['ending_equity'],
                sharpe_difference=None if active.get('sharpe') is None or baseline.get('sharpe') is None else active['sharpe']-baseline['sharpe'],
                active_total_return_pct=active['total_return_pct'],control_total_return_pct=baseline['total_return_pct'],
                **r.helpers.compare_points(active,baseline),**stats))
            distributions[key[0]+'_'+key[1]]=dist
            metrics.append(dict(baseline,account_id=control['account_id'],window=key[0],cost=key[1],role='control_reused',replayed=False))
            ar=state['reports'][spec['account_id']]['annual_slices'];br=control_reports[control['account_id']]['annual_slices']
            paired_year.extend(dict(window=key[0],cost=key[1],**a) for a in pair_years(ar,br))
            for name,role,rows in ((spec['account_id'],'candidate',ar),(control['account_id'],'control_reused',br)):
                annual.extend(dict(account_id=name,role=role,window=key[0],cost=key[1],**a) for a in rows)
        tables=[('account_summaries',metrics),('comparisons',points),('annual_slices',annual),('paired_annual',paired_year),
            ('bootstrap_distributions',pd.DataFrame(distributions))]
        if state['family_tables']:tables.append(('family_year_including_zero',pd.concat(state['family_tables'],ignore_index=True)))
        for name,value in tables:r.ref.write_table(folder/(name+'.csv.gz'),value,[])
        stale=any(s['any_historical_stale'] for s in state['summaries'].values()) or any(control_reports[c['account_id']]['stale_days']>0 for c in state['controls'])
        unknown=any(s['execution_unknown'] for s in list(state['summaries'].values())+control_summaries)
        wealth=all(r._log_path(f)[0] is not None for f in list(state['daily'].values())+control_frames)
        gate=fixed_gate(points,paired_year,state['held'],wealth_positive=wealth,any_stale=stale,execution_unknown=unknown)
        gate.update(any_candidate_historical_stale=any(s['any_historical_stale'] for s in state['summaries'].values()),
            any_candidate_execution_unknown=any(s['execution_unknown'] for s in state['summaries'].values()),
            identical_all_cash_inputs_reused=state['identical'],bootstrap_indices_regenerated=False,CI_is_paired_daily_log_growth_diagnostic=True,
            overlapping_action_and_source_days_not_independent=True,historical_first_seen_PIT_proved=False,
            annual_boundaries_only_update_new_signal_scores=True,year_end_liquidation=False,year_end_capital_reset=False,
            inherited_original157_own_control_accounts=True)
        write_json(folder/'decision.json',gate)
        write_json(folder/'diagnostics.json',r.kernel.original.safe(state['reports']))
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('source drift or SQL budget violation')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['receipt']['database_after']:
            raise ValueError('native database stat drift')

    report_authorization=None
    if bool(args.report_recovery_authorization)!=bool(args.report_recovery_authorization_sha256):
        raise ValueError('report recovery authorization path and SHA are required together')
    if args.report_recovery_authorization:
        if not args.reports_only:raise ValueError('source recovery authorization is report-only')
        report_authorization=binding(args.report_recovery_authorization)
        if report_authorization['sha256']!=args.report_recovery_authorization_sha256:
            raise ValueError('report recovery authorization SHA differs')
    if args.reports_only:
        previous=json.loads((out/'manifest.json').read_text())
        context_binding=next(b for b in previous['artifacts'] if Path(b['path'])==out/'report_context.json')
        report_context(read_json(context_binding))
    return run_four(out,lambda spec:run_account(state,spec),export,before=prepare,finalize=finalize,
        metadata=metadata,reports_only=args.reports_only,report_authorization=report_authorization)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','handoff','handoff-sha256','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--reports-only',action='store_true',help='Use all four bound raw-book checkpoints; never re-open the native cache or run cash.')
    parser.add_argument('--report-recovery-authorization')
    parser.add_argument('--report-recovery-authorization-sha256')
    execute(parser.parse_args())


if __name__=='__main__':main()
