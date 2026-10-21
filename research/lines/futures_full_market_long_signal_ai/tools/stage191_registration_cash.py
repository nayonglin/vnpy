"""Eight independent new54 cash books under frozen189; import is nonfinancial.

Only an exact root authorization may invoke execute. The accepted131 pure
arithmetic is reused, not its old results. All raw books and financial counts
are durable before any report or metadata computation. No automatic resume.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='7d2209746ec71740d7869d8a993ed877d609a1bade71c748378d3519fa3a5451'
ARMS=('CONTROL54','REGISTRATION54')
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
UPSTREAM_ROLES=('fit_manifest','choices_main','boundaries','held_diagnostic')


def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


reuse=load('stage148_fx_cash.py','stage191_pure148')
voluntary=load('stage157_voluntary_cash.py','stage191_pure157')
registration=load('stage190_registration_fit.py','stage191_registration_lineage')
author,cache_source=reuse.author,reuse.cache_source
kernel,ref,helpers,report_helpers=reuse.kernel,reuse.ref,reuse.helpers,reuse.report_helpers
read_json,verify_file,numeric=reuse.read_json,reuse.verify_file,reuse.numeric
CachedMarket,paired_statistics=reuse.CachedMarket,reuse.paired_statistics
write_ledgers,extra_reports=reuse.write_ledgers,reuse.extra_reports
apply_boundaries,sector_year_attribution=voluntary.apply_boundaries,voluntary.sector_year_attribution


def source_bundle():
    paths={b['path'] for b in reuse.source_bundle()}
    paths.update(b['path'] for b in registration.source_bundle())
    paths.update(str(TOOLS/n) for n in ('stage157_voluntary_cash.py','test_stage157_voluntary_cash.py',
        'stage191_registration_cash.py','test_stage190_191_registration.py'))
    return sorted((ref.file_binding(p) for p in paths),key=lambda b:b['path'])


def account_specs():
    return [dict(arm=a,window=w,cost=c,account_id=f'NARROW_{a}_{w}_{c}')
        for a in ARMS for w in WINDOWS for c in COSTS]


def make_arm_signals(actions,mothers,choices,boundaries,market,dates,economics,arm):
    if arm not in ARMS:raise ValueError('unknown189 arm')
    picked=choices.loc[choices.arm.eq(arm)].copy()
    if not len(picked) or set(picked.scope)!={'main'} or set(picked.policy)!={'NARROW'}:
        raise ValueError('complete own main NARROW parents required')
    # Schema adapter only. Never mutate131 ARMS or borrow the other arm choice.
    picked['arm']='B'
    source=author.make_signals(actions,mothers,picked,'B',market,dates,economics)
    source['arm']=arm;source['control_id']=arm
    result=apply_boundaries(source,boundaries)
    for row in result.to_dict('records'):
        k=row['voluntary_boundary_index']
        if pd.notna(k) and int(k)<len(dates) and dates[int(k)]!=row['K_date']:
            raise ValueError('boundary and cached source calendar differ')
    return result


def run_account_checkpoints(out,signals,mothers,market,dates,economics,windows,*,fixture=False):
    """Run exactly8 separate recursive books; no report dependency in this step."""
    out=Path(out)
    if (out/'financial_started.json').exists() or (out/'financial_terminal.json').exists() or any(
            (out/s['account_id']).exists() for s in account_specs()):
        raise FileExistsError('financial attempt retained; completed books must never replay')
    if set(signals)!=set(ARMS) or set(windows)!=set(WINDOWS):raise ValueError('exact189 arms/windows required')
    prepared={a:author.organize(signals[a],mothers,dates) for a in ARMS}
    bounds={}
    for w in WINDOWS:
        start,end=(int(np.searchsorted(dates,v)) for v in windows[w])
        if end>=len(dates) or dates[end]!=windows[w][1] or start>end:
            raise ValueError('exact source end/calendar window required')
        bounds[w]=(start,end)
    ref.write_json(out/'financial_started.json',dict(cash_accounts_started=0,new_cash_accounts=0,
        fixture=fixture,started_at=datetime.now(timezone.utc).isoformat(),no_automatic_resume=True))
    books,accounts={},[];started=completed=checkpointed=0;status='failed';error=None
    try:
        for spec in account_specs():
            a,w,c,name=(spec[k] for k in ('arm','window','cost','account_id'))
            started+=1;reuse.write_cash_progress(out,started,completed,name)
            book=kernel.run_cash_account(signals[a],market,dates,economics,c,name,*bounds[w],prepared=prepared[a])
            # Count completion before any serialization/report can fail.
            completed+=1
            ref.write_json(out/f'cash_completed_{completed:02d}.json',dict(spec,
                cash_accounts_started=started,new_cash_accounts=completed,fixture=fixture,
                cumulative_fit=409 if fixture else 421,cumulative_cash=218 if fixture else 218+completed))
            books[(a,w,c)]=book
            folder=out/name;ledgers=write_ledgers(folder,book)
            ref.write_json(folder/'kernel_summary.json',kernel.original.safe(book['summary']))
            checkpoint=dict(spec,status='raw_book_complete',fixture=fixture,ledgers=ledgers,
                kernel_summary=ref.file_binding(folder/'kernel_summary.json'),new_cash_accounts=completed,
                reports_pending=True,no_book_replay_allowed=True)
            ref.write_json(folder/'checkpoint.json',checkpoint);checkpointed+=1
            accounts.append(dict(spec,directory=str(folder),ledgers=ledgers,
                checkpoint=ref.file_binding(folder/'checkpoint.json')))
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'financial_terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,
            error=error,cash_accounts_started=started,new_cash_accounts=completed,raw_ledgers_checkpointed=checkpointed,
            fixture=fixture,actual_model_fit_calls=0,new_labels=0,native_source_queries=ref.NATIVE_QUERIES,
            old_control_book_replays=0,metadata_pending=True,no_automatic_resume=True,
            cumulative_fit=409 if fixture else 421,cumulative_cash=218 if fixture else 218+completed))
    return books,accounts


def compare_accounts(summaries,daily,indices):
    points,distributions=[],{}
    for w in WINDOWS:
        for c in COSTS:
            active,control=('REGISTRATION54',w,c),('CONTROL54',w,c)
            stats,dist=paired_statistics(daily[active],daily[control],indices[w])
            name=f'{w}_{c}_REGISTRATION54_minus_CONTROL54'
            aq,bq=summaries[active],summaries[control]
            dd_known=all(q.get('max_drawdown_pct') is not None and np.isfinite(q['max_drawdown_pct']) for q in (aq,bq))
            if dd_known:
                point=helpers.compare_points(aq,bq)
            else:
                point=dict(return_percentage_point_difference=aq['total_return_pct']-bq['total_return_pct'],
                    drawdown_percentage_point_difference=None,dd_comparison_state='unknown_drawdown',
                    identification='all_empty_unidentified' if aq['fills']==bq['fills']==0 else 'observed_cash_comparison')
            points.append(dict(window=w,cost=c,contrast='REGISTRATION54_minus_CONTROL54',
                active_arm=ARMS[1],reference_arm=ARMS[0],
                active_total_return_pct=summaries[active]['total_return_pct'],
                reference_total_return_pct=summaries[control]['total_return_pct'],
                **point,**stats))
            distributions[name]=dist
    return points,distributions


def fixed_gate(points,held,any_stale,*,wealth_positive,execution_unknown):
    lookup={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(lookup)!={(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('four fixed new54 comparisons required')
    groups=held.get('groups',{})
    if not {'holdout_0','holdout_1'}.issubset(groups):raise ValueError('both held old-target groups required')
    groups={g:groups[g] for g in ('holdout_0','holdout_1')}
    finite=lambda x:x is not None and np.isfinite(x)
    primary=lookup[('primary_2020','stress')]
    own=all(finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0 for p in points)
    ret=all(finite(p.get('return_percentage_point_difference')) and
        (p['return_percentage_point_difference']>0 if p is primary else p['return_percentage_point_difference']>=0) for p in points)
    dd_known=all(finite(p.get('drawdown_percentage_point_difference')) for p in points)
    dd=all((p['drawdown_percentage_point_difference']>0 if p is primary else p['drawdown_percentage_point_difference']>=0)
        for p in points if finite(p.get('drawdown_percentage_point_difference')))
    ci=finite(primary.get('ci95_low')) and primary['ci95_low']>0
    hn=all(finite(g.get('known_u_equal_mean_increment_R')) and g['known_u_equal_mean_increment_R']>=0
        and g.get('nominal_pass') is True for g in groups.values())
    hu=any(g.get('unknown_differential_selected_events',0)>0 or g.get('status')=='unknown' for g in groups.values())
    cash=bool(own and ret and dd_known and dd and ci and wealth_positive)
    unknown=bool(not dd_known or any_stale or execution_unknown)
    if not dd_known:status='unknown_control_drawdown'
    elif not (cash and hn):status='unsupported'
    elif any_stale:status='unknown_historical_stale'
    elif execution_unknown:status='unknown_execution_capacity_or_entry'
    elif hu:status='unknown_differential_held_outcome'
    else:status='supported_limited_reconstruction_model_only'
    return dict(status=status,cash_nominal_pass=cash,held_known_nominal_pass=bool(hn),
        nominal_pass=bool(cash and hn and not hu and not unknown),own_returns_positive_all_four=bool(own),
        return_gate=bool(ret),drawdown_gate=bool(dd and dd_known),primary_daily_log_CI_lower_positive=bool(ci),
        actual_wealth_positive=bool(wealth_positive),financial_unknown=unknown,held_signal_unknown=bool(hu),
        execution_unknown=bool(execution_unknown),any_historical_stale=bool(any_stale),
        held_diagnostic_is_K_cash_target=False,unchanged_training_target=True,
        fixed_algorithm_information_increment_under_shared_K_only=True,strict_first_release_PIT_established=False,
        independent_actual_review_required=True,no_automatic_promotion=True,goal_complete=False,
        production_qualified=False,increased_betting_qualified=False)


def build_disclosure(protocol,execution):
    return dict(policy='NARROW',kernel='unchanged accepted131 pure cash arithmetic',
        budget=protocol['cash'],capacity=execution['cash']['capacity'],anchor=execution['anchor_and_execution'],
        bootstrap_indices=protocol['statistics']['indices'],bootstrap_indices_regenerated=False,
        fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,
        no_gap_loss_cap=True,no_actual_orderbook_execution_proof=True,legal_clearance_proved=False,
        source_archive_is_final_reconstruction=True,held_diagnostic_is_K_cash_target=False,
        old_cash_control_used=False,ordinary_F_and_financial_commodity_retained=True,
        voluntary_generic_kernel_reason='lifecycle_exit; see source/voluntary/effective sidecar',
        goal_complete=False,production_qualified=False,increased_betting_qualified=False)


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; previous attempt retained '+str(out))
    if LINE/'outputs/stage191_registration_cash' not in out.parents:
        raise ValueError('fresh Stage191 output descendant required')
    pb=ref.file_binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact frozen189 required')
    protocol=read_json(pb)
    if protocol.get('schema')!='stage189_registration_information_financial_protocol_v1' or protocol.get('line_id')!=LINE.name:
        raise ValueError('189 identity differs')
    ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=read_json(ab)
    expected=dict(schema='stage189_exact_root_authorization_v1',authorized_by='root',stage='cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('authorized source/tests differ')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!=set(protocol['source_bindings'])|set(registration.NEW_INPUT_ROLES)|set(UPSTREAM_ROLES):
        raise ValueError('exact189 plus accepted186/188 and190 roles required')
    for role,binding in protocol['source_bindings'].items():author.same_binding(inputs[role],binding,'189 '+role)
    c=protocol['cash']
    if (c['initial_capital'],c['single_family_risk'],c['total_risk'],c['buffered_margin_cap'],c['margin_buffer'])!=(ref.INITIAL,ref.SINGLE_RISK,ref.TOTAL_RISK,ref.MARGIN_CAP,ref.MARGIN_BUFFER):
        raise ValueError('accepted cash constants differ')
    if (c['initial_stop_N'],c['new_accounts_max'],c['native_SQL'],c['new_labels'],c['old_control_book_replays'])!=(.25,8,0,0,0) or c['arms']!=list(ARMS) or not c['cache_only']:
        raise ValueError('exact eight cache-only books required')
    return protocol,pb,auth,ab


def validate_upstream(protocol,inputs):
    execution=read_json(inputs['execution_protocol'])
    author.same_binding(inputs['market_protocol'],execution['inputs']['market_protocol'],'128 market protocol')
    fit=read_json(inputs['fit_manifest'])
    if fit.get('schema')!='stage190_registration_fit_v1' or fit.get('status')!='completed' or fit.get('actual_model_fit_calls')!=12:
        raise ValueError('completed twelve-fit190 required')
    if fit.get('protocol_sha256')!=PROTOCOL_SHA:raise ValueError('190 protocol differs')
    author.same_binding(fit['protocol'],ref.file_binding(LINE/'outputs/stage189_registration_information_protocol/protocol.json'),'190 protocol')
    required_fit_roles=set(protocol['source_bindings'])|set(registration.NEW_INPUT_ROLES)
    if set(fit['input_bindings'])!=required_fit_roles:raise ValueError('190 complete exact source lineage required')
    for role,b in fit['input_bindings'].items():
        author.same_binding(b,inputs[role],'190 '+role)
    small={role:read_json(inputs[role]) for role in registration.NEW_INPUT_ROLES if role!='projection_actions'}
    registration.check_new_lineage(small,inputs,protocol)
    for role in UPSTREAM_ROLES[1:]:author.same_binding(fit[role],inputs[role],'190 artifact '+role)
    terminal=read_json(fit['terminal'])
    if (terminal.get('status')!='completed' or terminal.get('exit_code')!=0
            or terminal.get('actual_fit_calls_attempted')!=12 or terminal.get('actual_fit_calls_completed')!=12):
        raise ValueError('190 incomplete twelve-fit terminal')
    meta=read_json(inputs['native_cache_manifest'])
    author.same_binding(meta['file'],inputs['native_cache'],'132 native arrays')
    return execution,fit


def load_selected_inputs(inputs):
    evidence={role:dict(binding=inputs[role],stat_before=registration.stat_identity(inputs[role]['path']),
        verification='accepted129_or_new190_binding_inherited_single_data_read')
        for role in ('mothers','choices_main','actions')}
    if any(s['stat_before']['bytes']!=s['binding']['bytes'] for s in evidence.values()):
        raise ValueError('accepted cash input size differs')
    mothers=pd.read_csv(inputs['mothers']['path'],dtype=str,keep_default_na=False,usecols=reuse.IDENTITY)
    numeric(mothers,['sequence_index','u_index'])
    if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
            or mothers.family_id.nunique()!=95 or mothers.product_id.str.split('.').str[0].nunique()!=6
            or not np.array_equal(mothers.sequence_index,np.arange(len(mothers)))):
        raise ValueError('unchanged complete129 mothers required')
    choices=pd.read_csv(inputs['choices_main']['path'],dtype=str,keep_default_na=False,float_precision='round_trip')
    numeric(choices,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    expected=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if len(expected)!=161014 or len(choices)!=322028 or set(choices.arm)!=set(ARMS) or set(choices.scope)!={'main'}:
        raise ValueError('two complete161014 main parent arms required')
    for arm in ARMS:
        part=choices.loc[choices.arm.eq(arm)]
        if len(part)!=161014 or part.event_id.duplicated().any() or part.event_id.tolist()!=expected.event_id.tolist():
            raise ValueError('full own parent order differs '+arm)
        for col in reuse.IDENTITY:
            if part[col].tolist()!=expected[col].tolist():raise ValueError('full own parent identity differs '+arm+' '+col)
    ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id'])
    frames=[];scanned=0
    for chunk in pd.read_csv(inputs['actions']['path'],dtype=str,keep_default_na=False,compression='gzip',
            usecols=reuse.ACTION_FIELDS,chunksize=100000,float_precision='round_trip'):
        if not np.array_equal(pd.to_numeric(chunk.action_sequence_index,errors='raise'),np.arange(scanned,scanned+len(chunk))):
            raise ValueError('full original action order differs while scanning')
        scanned+=len(chunk)
        part=chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(part):frames.append(part)
    actions=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=reuse.ACTION_FIELDS)
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    if scanned!=1552456 or actions.action_id.duplicated().any() or set(actions.action_id)!=ids:
        raise ValueError('full1552456 scan and all selected exact129 actions required')
    document=read_json(inputs['boundaries'])
    if document.get('schema')!='stage190_voluntary_epoch_boundaries_v1' or document.get('not_certified') is not True or document.get('protocol_sha256')!=PROTOCOL_SHA:
        raise ValueError('190 same-policy noncertified boundary document required')
    author.same_binding(document['calendar'],inputs['calendar'],'190 boundary calendar')
    for role,state in evidence.items():
        state['stat_after']=registration.stat_identity(inputs[role]['path'])
        if state['stat_before']!=state['stat_after']:raise ValueError('cash input changed during read '+role)
    return mothers,choices,actions,document['epochs'],evidence


def restore_accepted_cache(inputs):
    """Inherit accepted132 digest; read NPZ once, with small metadata/stat guards."""
    meta=read_json(inputs['native_cache_manifest'])
    author.same_binding(meta['file'],inputs['native_cache'],'accepted132 cache')
    if (meta.get('schema')!='stage132_native_store_recovery_cache_v1'
            or meta.get('native_rows')!=1552456 or meta.get('native_epochs')!=9520):
        raise ValueError('accepted native cache identity differs')
    before=cache_source.database_state(meta['database']['path'])
    if any(meta['database'].get(k)!=v for k,v in before.items()):raise ValueError('accepted native database stat differs')
    state=registration.stat_identity(inputs['native_cache']['path'])
    if state['bytes']!=inputs['native_cache']['bytes']:raise ValueError('native cache size differs')
    cal_array=np.load(io.BytesIO(ref.read_bound(inputs['calendar'])),allow_pickle=False)
    dates=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal_array]
        if cal_array.dtype.kind in 'iu' else cal_array.astype('datetime64[D]').astype(str).tolist())
    if len(dates)!=5587 or dates!=sorted(set(dates)):raise ValueError('exact full052 calendar required')
    store=cache_source.NativeBars(dates)
    with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets']
        flat={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        if len(epochs)!=9520 or offsets[0]!=0 or offsets[-1]!=1552456:
            raise ValueError('full accepted native cache shape differs')
        for i,epoch in enumerate(epochs):
            store.series[epoch]={k:a[int(offsets[i]):int(offsets[i+1])] for k,a in flat.items()}
    after=cache_source.database_state(meta['database']['path'])
    if before!=after or state!=registration.stat_identity(inputs['native_cache']['path']):
        raise ValueError('native metadata or cache stat changed while reading')
    return store,dict(native_source_queries=0,native_contract_days=1552456,native_epochs=9520,
        database_before=before,database_after=after,database_rehashed=False,cache_rehashed=False,
        cache=inputs['native_cache_manifest'],cache_file=inputs['native_cache'],
        cache_stat=state,restored_from_exact_cache=True)


def summarize_checkpoints(out,books,accounts,mothers,indices,held):
    summaries,daily,reports={}, {}, {};family_tables=[];capacities=[];groups=[];year_groups=[];tails={}
    for account in accounts:
        a,w,c,name=(account[k] for k in ('arm','window','cost','account_id'));key=(a,w,c);book=books[key]
        summary,report,fy=helpers.cash_report(book,sorted(mothers.family_id.unique()),ref.INITIAL)
        capacity=dict(account=name,arm=a,window=w,cost=c,execution_unknown=book['execution_unknown'],
            unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
        summary.update(capacity,any_historical_stale=report['stale_days']>0);report.update(capacity)
        summaries[key],daily[key],reports[name]=summary,pd.DataFrame(book['daily']),report
        capacities.append(capacity);family_tables.append(report_helpers.add_family_costs(fy,book).assign(arm=a,window=w,cost=c))
        gr,tail=extra_reports(book);tails[name]=tail
        groups.extend(dict(account=name,arm=a,window=w,cost=c,**r) for r in gr)
        year_groups.extend(dict(account=name,arm=a,window=w,cost=c,**r) for r in sector_year_attribution(book))
        path=Path(account['directory'])/'summary.json';ref.write_json(path,kernel.original.safe(summary));account['summary']=ref.file_binding(path)
    points,distributions=compare_accounts(summaries,daily,indices)
    stale=any(r['stale_days']>0 for r in reports.values())
    unknown=any(s['execution_unknown'] for s in summaries.values())
    wealth=all(reuse._log_path(f)[0] is not None for f in daily.values())
    gate=fixed_gate(points,held,stale,wealth_positive=wealth,execution_unknown=unknown)
    fy=pd.concat(family_tables,ignore_index=True)
    tables=dict(comparisons=points,bootstrap_distributions=pd.DataFrame(distributions),family_year_including_zero=fy,
        family_total_including_zero=fy.groupby(['arm','window','cost','family_id'])[
            ['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index(),
        annual_slices=[dict(account=a,**r) for a,p in reports.items() for r in p['annual_slices']],
        account_summaries=list(summaries.values()),capacity_summary=capacities,
        sector_variant_attribution=groups,sector_variant_year_including_zero=year_groups)
    bindings={}
    for name,table in tables.items():
        path=out/(name+'.csv.gz');ref.write_table(path,table,[]);bindings[name]=ref.file_binding(path)
    for name,value in dict(largest_wins_losses=tails,diagnostics=reports,continuation_gate=gate).items():
        path=out/(name+'.json');ref.write_json(path,kernel.original.safe(value));bindings[name]=ref.file_binding(path)
    return bindings


def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    began,clock=datetime.now(timezone.utc).isoformat(),time.monotonic()
    before=source_bundle();status,error='failed_before_cash',None;accounts=[];signals_binding={};artifacts={}
    ref.write_json(out/'actual_started.json',dict(stage='cash',status='started',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        execution,fit=validate_upstream(protocol,inputs)
        mothers,choices,actions,boundaries,input_evidence=load_selected_inputs(inputs)
        store,native_receipt=restore_accepted_cache(inputs)
        if native_receipt['native_source_queries']!=0 or ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=CachedMarket(store),store.calendar
        market_protocol=read_json(inputs['market_protocol'])
        economics_binding=market_protocol['economic_projection'];economics=read_json(economics_binding)['instruments']
        if set(economics)!=set(store.series):raise ValueError('exact cached economics required')
        indices={w:np.load(io.BytesIO(ref.read_bound(protocol['statistics']['indices'][w])),allow_pickle=False) for w in WINDOWS}
        for w in WINDOWS:
            bounds=protocol['cash']['windows'][w]
            if execution['cash']['windows'][w]!=bounds:raise ValueError('unchanged128 windows required')
            start,end=(int(np.searchsorted(dates,v)) for v in bounds)
            if end>=len(dates) or dates[end]!=bounds[1] or indices[w].shape!=(2000,end-start+1):
                raise ValueError('fixed070 calendar/index width differs')
        signals={a:make_arm_signals(actions,mothers,choices,boundaries,market,dates,economics,a) for a in ARMS}
        trace_cols=['arm','event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin',
            'K_target_date','K_date','K_state']
        for a in ARMS:
            path=out/f'signals_{a}.csv.gz';ref.write_table(path,signals[a],[]);signals_binding[a]=ref.file_binding(path)
        ref.write_table(out/'boundary_lineage.csv.gz',pd.concat([signals[a][trace_cols] for a in ARMS],ignore_index=True),[])
        ref.write_json(out/'source_read_receipt.json',dict(native_receipt,actual_model_fit_calls=0,new_labels=0,
            old_baseline_replays=0,selected_source_children=len(actions),full_forward_parent_rows_per_arm=161014,
            full_mother_rows=len(mothers),canonical_from_full_original_mothers=True,original_source_lifecycle_modified=False,
            input_evidence=input_evidence))
        # Every completed book is checkpointed and financial_terminal written by
        # this call before any cash_report, held gate, disclosure, or manifest.
        books,accounts=run_account_checkpoints(out,signals,mothers,market,dates,economics,protocol['cash']['windows'])
        status='failed_metadata_after_cash'
        held=read_json(inputs['held_diagnostic'])
        artifacts=summarize_checkpoints(out,books,accounts,mothers,indices,held)
        ref.write_json(out/'budget_and_tick_disclosure.json',build_disclosure(protocol,execution))
        ref.write_json(out/'signal_identification.json',dict(full_mother_rows=399252,full_main_parent_rows_per_arm=161014,
            selected_actions={a:len(signals[a]) for a in ARMS},full_choices_binding=inputs['choices_main'],
            boundary_binding=inputs['boundaries'],fit_manifest=inputs['fit_manifest'],
            canonical_from_full_original_mothers=True,filter_full_domain_before_argmax=True,
            old_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,
            local_B_schema_alias_only=True,old_global_ARMS_changed=False,held_diagnostic_is_K_cash_target=False))
        if source_bundle()!=before:raise ValueError('authorized191 sources changed during actual')
        if cache_source.database_state(read_json(inputs['native_cache_manifest'])['database']['path'])!=native_receipt['database_after']:
            raise ValueError('cached database stat changed during actual')
        status='completed'
    except BaseException as exc:
        if (out/'financial_started.json').exists() and status=='failed_before_cash':status='failed_cash'
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        financial=json.loads((out/'financial_terminal.json').read_text()) if (out/'financial_terminal.json').exists() else {}
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,cash_accounts_started=financial.get('cash_accounts_started',0),
            new_cash_accounts=financial.get('new_cash_accounts',0),raw_ledgers_checkpointed=financial.get('raw_ledgers_checkpointed',0),
            native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_labels=0,downloads=0,
            whole_database_hashes=0,old_baseline_replays=0,old_control_cash_replays=0,fixture=False,python=sys.executable,
            no_completed_book_replay=True,cumulative_fit=421,cumulative_cash=218+financial.get('new_cash_accounts',0)))
    all_artifacts=[dict(ref.file_binding(p),logical_name=str(p.relative_to(out)),role='decision_asset',
        feature_schema='stage191_registration_cash_v1',raw_ohlc=False,reproducibility_required=True)
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest=dict(schema='stage191_registration_cash_v1',status=status,mode='actual',protocol=pb,
        protocol_sha256=PROTOCOL_SHA,authorization=ab,source_bundle=before,input_bindings=inputs,
        terminal=ref.file_binding(out/'actual_terminal.json'),financial_terminal=ref.file_binding(out/'financial_terminal.json'),
        artifacts=all_artifacts,accounts=accounts,signals=signals_binding,boundary_lineage=ref.file_binding(out/'boundary_lineage.csv.gz'),
        held_diagnostic=inputs['held_diagnostic'],economic_projection=economics_binding,
        bootstrap_indices=protocol['statistics']['indices'],new_cash_accounts=8,actual_model_fit_calls=0,
        native_source_queries=0,new_labels=0,old_control_book_replays=0,old_baseline_replays=0,
        cumulative_fit=421,cumulative_cash=226,
        goal_complete=False,production_qualified=False,increased_betting_qualified=False,**artifacts)
    for name in ('budget_and_tick_disclosure','signal_identification','source_read_receipt'):
        manifest[name]=ref.file_binding(out/(name+'.json'))
    ref.write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),new_cash_accounts=8,native_source_queries=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
