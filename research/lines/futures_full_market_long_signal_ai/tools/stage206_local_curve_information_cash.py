"""Four new CURVE53 cache-only books; accepted157 control is read-only.

Actual execution needs root's exact source/input authorization. All four raw
books and financial counts precede metadata. No automatic retry or old replay.
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
PROTOCOL_SHA='b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca'
ARM='CURVE53'
CONTROL='CONTROL157_REUSED'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
UPSTREAM_ROLES=('fit_manifest','choices_main','boundaries','held_diagnostic')


def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


reuse=load('stage148_fx_cash.py','stage206_pure148')
voluntary=load('stage157_voluntary_cash.py','stage206_pure157')
fit_source=load('stage205_local_curve_information_fit.py','stage206_lineage205')
author,cache_source=reuse.author,reuse.cache_source
kernel,ref,helpers,report_helpers=reuse.kernel,reuse.ref,reuse.helpers,reuse.report_helpers
read_json,numeric=reuse.read_json,reuse.numeric
CachedMarket,paired_statistics=reuse.CachedMarket,reuse.paired_statistics
write_ledgers,extra_reports=reuse.write_ledgers,reuse.extra_reports


def write_json(path,value):
    # Normalize numpy bool/int/float before strict JSON serialization.
    fit_source.write_json(path,kernel.original.safe(value))


def source_bundle():
    paths={b['path'] for b in reuse.source_bundle()}
    paths.update(b['path'] for b in fit_source.source_bundle())
    paths.update(str(TOOLS/n) for n in ('stage157_voluntary_cash.py','test_stage157_voluntary_cash.py',
        'stage206_local_curve_information_cash.py','test_stage206_local_curve_information_cash.py'))
    return sorted((ref.file_binding(p) for p in paths),key=lambda b:b['path'])


def account_specs():
    return [dict(arm=ARM,window=w,cost=c,account_id=f'NARROW_{ARM}_{w}_{c}')
        for w in WINDOWS for c in COSTS]


def control_account_specs(manifest):
    """Only Stage157's own four VOLUNTARY books; never its old131 references."""
    accounts=manifest.get('accounts',[])
    if len(accounts)!=4:raise ValueError('exact four own157 control accounts required')
    lookup={(a['window'],a['cost']):a for a in accounts}
    if set(lookup)!={(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('four unique157 windows/costs required')
    result=[]
    for spec in account_specs():
        w,c=spec['window'],spec['cost'];a=lookup[(w,c)]
        name=f'NARROW_VOLUNTARY_RESELECT_{w}_{c}'
        if a.get('arm')!='VOLUNTARY_RESELECT' or a.get('account_id')!=name:
            raise ValueError('own157 control identity differs')
        result.append(dict(window=w,cost=c,arm=CONTROL,source_arm='VOLUNTARY_RESELECT',
            source_account_id=name,summary=a['summary'],daily=a['ledgers']['daily'],
            source_only=True,replayed=False))
    return result


def baseline_references(manifest):
    specs=control_account_specs(manifest)
    diagnostic=manifest['diagnostics'];all_reports=read_json(diagnostic)
    summaries,daily,reports,references={},{},{},{}
    for spec in specs:
        w,c,name=spec['window'],spec['cost'],spec['source_account_id']
        summaries[(w,c)]=read_json(spec['summary'])
        if summaries[(w,c)].get('account')!=name or summaries[(w,c)].get('arm')!='VOLUNTARY_RESELECT':
            raise ValueError('bound own157 summary identity differs')
        daily[(w,c)]=pd.read_csv(io.BytesIO(ref.read_bound(spec['daily'])),compression='gzip')
        reports[name]=all_reports[name]
        if reports[name].get('account')!=name:raise ValueError('bound own157 diagnostic identity differs')
        references[w+'_'+c]=dict(spec,diagnostics=diagnostic,diagnostic_key=name)
    return references,summaries,daily,reports


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; all attempts retained '+str(out))
    if LINE/'outputs/stage206_local_curve_information_cash' not in out.parents:
        raise ValueError('fresh Stage206 output descendant required')
    pb=ref.file_binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen204 protocol required')
    protocol=read_json(pb)
    if protocol.get('schema')!='stage204_local_curve53_fixed_information_protocol_v1' or protocol.get('line_id')!=LINE.name:
        raise ValueError('204 identity differs')
    ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=read_json(ab)
    expected=dict(schema='stage204_exact_root_authorization_v1',authorized_by='root',stage='cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():
        raise ValueError('authorized206 source/tests differ')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!=set(protocol['input_bindings'])|set(UPSTREAM_ROLES):
        raise ValueError('exact204 plus completed205 roles required')
    for role,b in protocol['input_bindings'].items():author.same_binding(inputs[role],b,'204 '+role)
    c=protocol['execution_if_gate_pass'];b=protocol['budget']
    if (c['capital'],c['single_family_risk'],c['total_risk'],c['buffered_margin_cap'],c['margin_buffer'],c['participation'])!=(
            ref.INITIAL,ref.SINGLE_RISK,ref.TOTAL_RISK,ref.MARGIN_CAP,ref.MARGIN_BUFFER,.01):
        raise ValueError('accepted cash constants differ')
    if c['new_cash']!=4 or b['new_cash_max']!=4 or any(b[k]!=0 for k in ('old_fit','old_cash_replay','new_labels','SQL','downloads')):
        raise ValueError('four new books and zero replay/SQL/labels/download budget required')
    return protocol,pb,auth,ab


def validate_upstream(protocol,inputs,pb):
    execution=read_json(inputs['execution_protocol'])
    author.same_binding(inputs['market_protocol'],execution['inputs']['market_protocol'],'128 market protocol')
    c=execution['cash']
    if (c['initial_equity'],c['initial_stop_N'],c['single_family_risk'],c['total_planned_risk'],
        c['buffered_margin_cap'],c['margin_buffer'],c['capacity']['participation_rate'])!=(1e6,.25,.0025,.02,.25,1.1,.01):
        raise ValueError('unchanged128 constants required')
    fit=read_json(inputs['fit_manifest'])
    if (fit.get('schema')!='stage205_local_curve_information_fit_v1' or fit.get('status')!='completed'
            or fit.get('cash_eligible') is not True or fit.get('actual_model_fit_calls')!=6
            or fit.get('actual_fit_calls_attempted')!=6 or fit.get('actual_fit_calls_completed')!=6):
        raise ValueError('completed six-fit cash-eligible205 required')
    author.same_binding(fit['protocol'],pb,'205 protocol')
    if fit.get('protocol_sha256')!=PROTOCOL_SHA or fit.get('source_bundle')!=fit_source.source_bundle():
        raise ValueError('205 frozen protocol/source differs')
    if set(fit['input_bindings'])!=set(protocol['input_bindings']):raise ValueError('205 complete204 lineage required')
    for role,b in fit['input_bindings'].items():author.same_binding(b,inputs[role],'205 '+role)
    for role in UPSTREAM_ROLES[1:]:author.same_binding(fit[role],inputs[role],'205 artifact '+role)
    terminal=read_json(fit['terminal']);direction=read_json(fit['direction_gate'])
    if (terminal.get('status')!='completed' or terminal.get('exit_code')!=0
            or terminal.get('cash_eligible') is not True or terminal.get('actual_fit_calls_attempted')!=6
            or terminal.get('actual_fit_calls_completed')!=6 or direction.get('passed') is not True
            or direction.get('exact_six_unique_models') is not True):
        raise ValueError('205 complete terminal and six-direction gate required')
    outcomes=direction.get('outcomes',[])
    if (len(outcomes)!=6 or {(r['scope'],r['cutoff']) for r in outcomes}!=
            {(s,c) for s in fit_source.SCOPES for c in fit_source.CUTOFFS}
            or not all(r.get('strictly_negative') is True and r.get('q_coefficient') is not None
                and np.isfinite(r['q_coefficient']) and r['q_coefficient']<0 for r in outcomes)):
        raise ValueError('all six strict cheap coefficients required')
    baseline=read_json(inputs['control_cash_manifest']);review=read_json(inputs['control_cash_review'])
    if (baseline.get('schema')!='stage157_voluntary_cash_v1' or
            baseline.get('status') not in ('completed','completed_with_metadata_continuation')
            or baseline.get('new_cash_accounts')!=4 or review.get('completed') is not True
            or review.get('research_arithmetic_accepted') is not True or (review.get('C'),review.get('I'))!=(0,0)):
        raise ValueError('accepted completed157 four-book control required')
    control_account_specs(baseline)
    for role in ('actions','mothers','dataset_manifest','market_protocol','execution_protocol','native_cache','native_cache_manifest'):
        author.same_binding(baseline['input_bindings'][role],inputs[role],'157 '+role)
    author.same_binding(baseline['input_bindings']['choices_main'],inputs['control_choices_main_K'],'157 own choices')
    for w in WINDOWS:author.same_binding(baseline['bootstrap_indices'][w],execution['bootstrap_indices'][w],'same070 '+w)
    meta=read_json(inputs['native_cache_manifest']);author.same_binding(meta['file'],inputs['native_cache'],'132 cache')
    return execution,fit,baseline


def load_selected_inputs(inputs):
    evidence={role:dict(binding=inputs[role],stat_before=fit_source.inherited_stat(inputs[role]),
        verification='inherited_accepted129_or_completed205_SHA_single_data_read')
        for role in ('mothers','choices_main','actions')}
    mothers=pd.read_csv(inputs['mothers']['path'],dtype=str,keep_default_na=False,usecols=reuse.IDENTITY)
    numeric(mothers,['sequence_index','u_index'])
    if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
            or mothers.family_id.nunique()!=95 or not np.array_equal(mothers.sequence_index,np.arange(len(mothers)))):
        raise ValueError('unchanged complete129 mothers required')
    choices=pd.read_csv(inputs['choices_main']['path'],dtype=str,keep_default_na=False,float_precision='round_trip')
    numeric(choices,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    expected=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if (len(expected)!=161014 or len(choices)!=161014 or set(choices.arm)!={ARM}
            or set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'}
            or choices.event_id.duplicated().any() or choices.event_id.tolist()!=expected.event_id.tolist()):
        raise ValueError('one complete own205 main parent arm required')
    for col in reuse.IDENTITY:
        if choices[col].tolist()!=expected[col].tolist():raise ValueError('full own parent identity differs '+col)
    ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id']);frames=[];scanned=0
    for chunk in pd.read_csv(inputs['actions']['path'],dtype=str,keep_default_na=False,compression='gzip',
            usecols=reuse.ACTION_FIELDS,chunksize=100000,float_precision='round_trip'):
        if not np.array_equal(pd.to_numeric(chunk.action_sequence_index,errors='raise'),np.arange(scanned,scanned+len(chunk))):
            raise ValueError('full original action order differs')
        scanned+=len(chunk);part=chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(part):frames.append(part)
    actions=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=reuse.ACTION_FIELDS)
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    if scanned!=1552456 or actions.action_id.duplicated().any() or set(actions.action_id)!=ids:
        raise ValueError('full1552456 scan and selected original129 children required')
    boundary=read_json(inputs['boundaries'])
    if boundary.get('schema')!='stage205_fixed155_K_boundaries_v1' or boundary.get('account_deadline_certified') is not False:
        raise ValueError('205 unchanged155 voluntary noncertified boundaries required')
    author.same_binding(boundary['calendar'],inputs['calendar'],'205 boundary calendar')
    for role,state in evidence.items():
        state['stat_after']=fit_source.inherited_stat(inputs[role])
        if state['stat_before']!=state['stat_after']:raise ValueError('cash input changed during read '+role)
    return mothers,choices,actions,boundary['epochs'],evidence


def restore_accepted_cache(inputs):
    """191's accepted132 NPZ single-read path, without any old book driver."""
    meta=read_json(inputs['native_cache_manifest']);author.same_binding(meta['file'],inputs['native_cache'],'132 arrays')
    if (meta.get('schema')!='stage132_native_store_recovery_cache_v1'
            or meta.get('native_rows')!=1552456 or meta.get('native_epochs')!=9520):
        raise ValueError('accepted132 native identity differs')
    before=cache_source.database_state(meta['database']['path'])
    if any(meta['database'].get(k)!=v for k,v in before.items()):raise ValueError('native database stat differs')
    state=fit_source.inherited_stat(inputs['native_cache'])
    cal=np.load(io.BytesIO(ref.read_bound(inputs['calendar'])),allow_pickle=False)
    dates=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal]
        if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
    if len(dates)!=5587 or dates!=sorted(set(dates)):raise ValueError('exact052 calendar required')
    store=cache_source.NativeBars(dates)
    with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets']
        flat={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        if len(epochs)!=9520 or offsets[0]!=0 or offsets[-1]!=1552456:raise ValueError('native shape differs')
        for i,e in enumerate(epochs):store.series[e]={k:a[int(offsets[i]):int(offsets[i+1])] for k,a in flat.items()}
    after=cache_source.database_state(meta['database']['path'])
    if before!=after or state!=fit_source.inherited_stat(inputs['native_cache']):raise ValueError('cache/native stat changed')
    return store,dict(native_source_queries=0,native_contract_days=1552456,native_epochs=9520,
        database_before=before,database_after=after,database_rehashed=False,cache_rehashed=False,
        cache=inputs['native_cache_manifest'],cache_file=inputs['native_cache'],cache_stat=state,restored_from_exact_cache=True)


def make_signals(actions,mothers,choices,boundaries,market,dates,economics):
    picked=choices.copy()
    if set(picked.arm)!={ARM} or set(picked.scope)!={'main'}:raise ValueError('own CURVE53 main choices required')
    picked['arm']='B'
    source=author.make_signals(actions,mothers,picked,'B',market,dates,economics)
    source['arm']=ARM;source['control_id']=ARM
    result=voluntary.apply_boundaries(source,boundaries)
    for row in result.to_dict('records'):
        k=row['voluntary_boundary_index']
        if pd.notna(k) and int(k)<len(dates) and dates[int(k)]!=row['K_date']:
            raise ValueError('boundary and cache calendar differ')
    return result


def run_account_checkpoints(out,signals,mothers,market,dates,economics,windows,*,fixture=False):
    out=Path(out)
    if (out/'financial_started.json').exists() or (out/'financial_terminal.json').exists():
        raise FileExistsError('financial attempt retained; no completed book replay')
    if any((out/s['account_id']).exists() for s in account_specs()):
        raise FileExistsError('financial attempt retained; no completed book replay')
    if set(windows)!=set(WINDOWS):raise ValueError('exact204 windows required')
    prepared=author.organize(signals,mothers,dates);bounds={}
    for w in WINDOWS:
        start,end=(int(np.searchsorted(dates,v)) for v in windows[w])
        if end>=len(dates) or dates[end]!=windows[w][1] or start>end:raise ValueError('exact calendar window required')
        bounds[w]=(start,end)
    write_json(out/'financial_started.json',dict(cash_accounts_started=0,new_cash_accounts=0,fixture=fixture,
        started_at=datetime.now(timezone.utc).isoformat(),no_automatic_resume=True))
    books,accounts={},[];started=completed=checkpointed=0;status='failed';error=None
    try:
        for spec in account_specs():
            w,c,name=(spec[k] for k in ('window','cost','account_id'))
            started+=1;reuse.write_cash_progress(out,started,completed,name)
            book=kernel.run_cash_account(signals,market,dates,economics,c,name,*bounds[w],prepared=prepared)
            completed+=1
            write_json(out/f'cash_completed_{completed:02d}.json',dict(spec,cash_accounts_started=started,
                new_cash_accounts=completed,fixture=fixture,cumulative_fit=427,cumulative_cash=226+completed))
            books[(w,c)]=book;folder=out/name;ledgers=write_ledgers(folder,book)
            write_json(folder/'kernel_summary.json',book['summary'])
            write_json(folder/'checkpoint.json',dict(spec,status='raw_book_complete',fixture=fixture,
                ledgers=ledgers,kernel_summary=ref.file_binding(folder/'kernel_summary.json'),new_cash_accounts=completed,
                reports_pending=True,no_book_replay_allowed=True));checkpointed+=1
            accounts.append(dict(spec,directory=str(folder),ledgers=ledgers,checkpoint=ref.file_binding(folder/'checkpoint.json')))
        status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'financial_terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,
            cash_accounts_started=started,new_cash_accounts=completed,raw_ledgers_checkpointed=checkpointed,
            fixture=fixture,actual_model_fit_calls=0,new_labels=0,native_source_queries=ref.NATIVE_QUERIES,
            old_control_book_replays=0,metadata_pending=True,no_automatic_resume=True,cumulative_fit=427,cumulative_cash=226+completed))
    return books,accounts


def compare_accounts(summaries,daily,control_summaries,control_daily,indices):
    points,distributions=[],{}
    for spec in account_specs():
        w,c=spec['window'],spec['cost'];key=(w,c)
        aq,bq=summaries[key],control_summaries[key]
        stats,dist=paired_statistics(daily[key],control_daily[key],indices[w])
        known=all(q.get('max_drawdown_pct') is not None and np.isfinite(q['max_drawdown_pct']) for q in (aq,bq))
        point=helpers.compare_points(aq,bq) if known else dict(
            return_percentage_point_difference=aq['total_return_pct']-bq['total_return_pct'],
            drawdown_percentage_point_difference=None,dd_comparison_state='unknown_drawdown',
            identification='all_empty_unidentified' if aq['fills']==bq['fills']==0 else 'observed_cash_comparison')
        points.append(dict(window=w,cost=c,contrast=ARM+'_minus_'+CONTROL,active_arm=ARM,reference_arm=CONTROL,
            active_total_return_pct=aq['total_return_pct'],reference_total_return_pct=bq['total_return_pct'],**point,**stats))
        distributions[w+'_'+c+'_'+ARM+'_minus_'+CONTROL]=dist
    return points,distributions


def fixed_gate(points,held,any_stale,*,wealth_positive,execution_unknown):
    """Frozen204 is stricter than191: all four CIs and strict held increment."""
    lookup={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(lookup)!={(w,c) for w in WINDOWS for c in COSTS}:raise ValueError('four comparisons required')
    groups=held.get('groups',{})
    if not {'holdout_0','holdout_1'}.issubset(groups):raise ValueError('both held groups required')
    groups={g:groups[g] for g in ('holdout_0','holdout_1')};finite=lambda x:x is not None and np.isfinite(x)
    primary=lookup[('primary_2020','stress')]
    own=all(finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0 for p in points)
    ret=all(finite(p.get('return_percentage_point_difference')) and
        (p['return_percentage_point_difference']>0 if p is primary else p['return_percentage_point_difference']>=0) for p in points)
    dd_known=all(finite(p.get('drawdown_percentage_point_difference')) for p in points)
    dd=dd_known and all((p['drawdown_percentage_point_difference']>0 if p is primary else
        p['drawdown_percentage_point_difference']>=0) for p in points)
    ci=all(finite(p.get('ci95_low')) and p['ci95_low']>0 for p in points)
    hn=all(finite(g.get('known_u_equal_mean_increment_R')) and g['known_u_equal_mean_increment_R']>0 for g in groups.values())
    hu=any(g.get('unknown_differential_selected_events',0)>0 or g.get('status')=='unknown' for g in groups.values())
    held_pass=hn and not hu and all(g.get('nominal_pass') is True for g in groups.values())
    cash=bool(own and ret and dd and ci and wealth_positive);unknown=bool(not dd_known or any_stale or execution_unknown)
    status=('unknown_control_drawdown' if not dd_known else 'unsupported' if not (cash and hn) else
        'unknown_historical_stale' if any_stale else 'unknown_execution_capacity_or_entry' if execution_unknown else
        'unknown_differential_held_outcome' if hu else 'supported_limited_reconstruction_model_only' if held_pass else 'unsupported')
    return dict(status=status,cash_nominal_pass=cash,held_known_strictly_positive_all_two=bool(hn),held_known_nominal_pass=bool(held_pass),
        nominal_pass=bool(cash and held_pass and not unknown),own_returns_positive_all_four=bool(own),return_gate=bool(ret),
        drawdown_gate=bool(dd),all_four_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth_positive),
        financial_unknown=unknown,held_signal_unknown=bool(hu),execution_unknown=bool(execution_unknown),any_historical_stale=bool(any_stale),
        held_diagnostic_is_K_cash_target=False,strict_first_release_PIT_established=False,numeric_missing_causal_isolation=False,
        independent_actual_review_required=True,no_automatic_promotion=True,goal_complete=False,
        production_qualified=False,increased_betting_qualified=False)


def summarize_checkpoints(out,books,accounts,mothers,indices,held,baseline):
    references,control_summaries,control_daily,control_reports=baseline_references(baseline)
    summaries,daily,reports={}, {}, {};family_tables=[];capacities=[];groups=[];year_groups=[];tails={}
    for account in accounts:
        w,c,name=(account[k] for k in ('window','cost','account_id'));key=(w,c);book=books[key]
        summary,report,fy=helpers.cash_report(book,sorted(mothers.family_id.unique()),ref.INITIAL)
        capacity=dict(account=name,arm=ARM,control_id=ARM,window=w,cost=c,execution_unknown=book['execution_unknown'],
            unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
        summary.update(capacity,any_historical_stale=report['stale_days']>0);report.update(capacity)
        summaries[key],daily[key],reports[name]=summary,pd.DataFrame(book['daily']),report
        capacities.append(capacity);family_tables.append(report_helpers.add_family_costs(fy,book).assign(arm=ARM,window=w,cost=c))
        gr,tail=extra_reports(book);tails[name]=tail
        groups.extend(dict(account=name,arm=ARM,window=w,cost=c,**r) for r in gr)
        year_groups.extend(dict(account=name,arm=ARM,window=w,cost=c,**r) for r in voluntary.sector_year_attribution(book))
        path=Path(account['directory'])/'summary.json';write_json(path,summary);account['summary']=ref.file_binding(path)
    points,distributions=compare_accounts(summaries,daily,control_summaries,control_daily,indices)
    stale=any(r['stale_days']>0 for r in list(reports.values())+list(control_reports.values()))
    unknown=any(s['execution_unknown'] for s in list(summaries.values())+list(control_summaries.values()))
    wealth=all(reuse._log_path(f)[0] is not None for f in list(daily.values())+list(control_daily.values()))
    gate=fixed_gate(points,held,stale,wealth_positive=wealth,execution_unknown=unknown)
    old_fy=pd.read_csv(io.BytesIO(ref.read_bound(baseline['family_year_including_zero'])),compression='gzip',dtype={'year':str})
    old_fy=old_fy.loc[old_fy.arm.eq('VOLUNTARY_RESELECT')].copy();old_fy['arm']=CONTROL
    if not len(old_fy):raise ValueError('own157 family-year rows missing')
    fy=pd.concat([*family_tables,old_fy],ignore_index=True)
    metrics=list(summaries.values())+[dict(control_summaries[(s['window'],s['cost'])],arm=CONTROL,
        window=s['window'],cost=s['cost'],source_only=True,replayed=False) for s in account_specs()]
    tables=dict(comparisons=points,bootstrap_distributions=pd.DataFrame(distributions),family_year_including_zero=fy,
        family_total_including_zero=fy.groupby(['arm','window','cost','family_id'])[
            ['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index(),
        annual_slices=[dict(account=a,**r) for a,p in {**reports,**control_reports}.items() for r in p['annual_slices']],
        account_summaries=metrics,capacity_summary=capacities,sector_variant_attribution=groups,
        sector_variant_year_including_zero=year_groups)
    bindings={}
    for name,table in tables.items():
        path=out/(name+'.csv.gz');ref.write_table(path,table,[]);bindings[name]=ref.file_binding(path)
    for name,value in dict(largest_wins_losses=tails,diagnostics=reports,continuation_gate=gate,baseline_references=references).items():
        path=out/(name+'.json');write_json(path,value);bindings[name]=ref.file_binding(path)
    return bindings


def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    began,clock=datetime.now(timezone.utc).isoformat(),time.monotonic()
    before=source_bundle();status,error='failed_before_cash',None;accounts=[];artifacts={}
    write_json(out/'actual_started.json',dict(stage='cash',status='started',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        execution,fit,baseline=validate_upstream(protocol,inputs,pb)
        mothers,choices,actions,boundaries,evidence=load_selected_inputs(inputs)
        store,native=restore_accepted_cache(inputs)
        if native['native_source_queries']!=0 or ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=CachedMarket(store),store.calendar
        economics_binding=read_json(inputs['market_protocol'])['economic_projection'];economics=read_json(economics_binding)['instruments']
        if set(economics)!=set(store.series):raise ValueError('exact cached economics required')
        indices={w:np.load(io.BytesIO(ref.read_bound(execution['bootstrap_indices'][w])),allow_pickle=False) for w in WINDOWS}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,v)) for v in execution['cash']['windows'][w])
            if end>=len(dates) or dates[end]!='2026-10-16' or indices[w].shape!=(2000,end-start+1):
                raise ValueError('fixed070 calendar/index width differs')
        signals=make_signals(actions,mothers,choices,boundaries,market,dates,economics)
        ref.write_table(out/'signals_CURVE53.csv.gz',signals,[])
        trace=['arm','event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
        ref.write_table(out/'boundary_lineage.csv.gz',signals[trace],[])
        write_json(out/'source_read_receipt.json',dict(native,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,
            selected_source_children=len(actions),full_forward_parent_rows=161014,full_mother_rows=len(mothers),
            canonical_from_full_original_mothers=True,original_source_lifecycle_modified=False,input_evidence=evidence))
        books,accounts=run_account_checkpoints(out,signals,mothers,market,dates,economics,execution['cash']['windows'])
        status='failed_metadata_after_cash'
        artifacts=summarize_checkpoints(out,books,accounts,mothers,indices,read_json(inputs['held_diagnostic']),baseline)
        write_json(out/'budget_and_tick_disclosure.json',dict(policy='NARROW',kernel='unchanged accepted131 pure arithmetic',
            budget=protocol['execution_if_gate_pass'],capacity=execution['cash']['capacity'],anchor=execution['anchor_and_execution'],
            bootstrap_indices=execution['bootstrap_indices'],bootstrap_indices_regenerated=False,fees_already_in_cash=True,
            slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,no_actual_orderbook_execution_proof=True,
            old_cash_control_used=True,old_control_replayed=False,source_archive_is_final_reconstruction=True,
            held_diagnostic_is_K_cash_target=False,strict_first_release_PIT_established=False,goal_complete=False,
            production_qualified=False,increased_betting_qualified=False))
        write_json(out/'signal_identification.json',dict(full_mother_rows=399252,full_main_parent_rows=161014,
            selected_actions=len(signals),full_choices_binding=inputs['choices_main'],boundary_binding=inputs['boundaries'],
            fit_manifest=inputs['fit_manifest'],canonical_from_full_original_mothers=True,filter_full_domain_before_argmax=True,
            old_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,local_B_schema_alias_only=True,
            old_global_ARMS_changed=False,held_diagnostic_is_K_cash_target=False,numeric_missing_causal_isolation=False))
        if source_bundle()!=before:raise ValueError('authorized206 sources changed during actual')
        if cache_source.database_state(read_json(inputs['native_cache_manifest'])['database']['path'])!=native['database_after']:
            raise ValueError('cached database stat changed during actual')
        status='completed'
    except BaseException as exc:
        if (out/'financial_started.json').exists() and status=='failed_before_cash':status='failed_cash'
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        f=json.loads((out/'financial_terminal.json').read_text()) if (out/'financial_terminal.json').exists() else {}
        write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,cash_accounts_started=f.get('cash_accounts_started',0),
            new_cash_accounts=f.get('new_cash_accounts',0),raw_ledgers_checkpointed=f.get('raw_ledgers_checkpointed',0),
            native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,
            old_baseline_replays=0,old_control_cash_replays=0,fixture=False,python=sys.executable,no_completed_book_replay=True,
            cumulative_fit=427,cumulative_cash=226+f.get('new_cash_accounts',0)))
    all_artifacts=[dict(ref.file_binding(p),logical_name=str(p.relative_to(out)),role='decision_asset',
        feature_schema='stage206_local_curve_information_cash_v1',raw_ohlc=False,reproducibility_required=True)
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest=dict(schema='stage206_local_curve_information_cash_v1',status=status,mode='actual',protocol=pb,
        protocol_sha256=PROTOCOL_SHA,authorization=ab,source_bundle=before,input_bindings=inputs,
        terminal=ref.file_binding(out/'actual_terminal.json'),financial_terminal=ref.file_binding(out/'financial_terminal.json'),
        artifacts=all_artifacts,accounts=accounts,signals=ref.file_binding(out/'signals_CURVE53.csv.gz'),
        boundary_lineage=ref.file_binding(out/'boundary_lineage.csv.gz'),held_diagnostic=inputs['held_diagnostic'],
        economic_projection=economics_binding,bootstrap_indices=execution['bootstrap_indices'],new_cash_accounts=4,
        actual_model_fit_calls=0,native_source_queries=0,new_labels=0,old_control_book_replays=0,old_baseline_replays=0,
        cumulative_fit=427,cumulative_cash=230,goal_complete=False,production_qualified=False,increased_betting_qualified=False,**artifacts)
    for name in ('budget_and_tick_disclosure','signal_identification','source_read_receipt'):
        manifest[name]=ref.file_binding(out/(name+'.json'))
    write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),new_cash_accounts=4,native_source_queries=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
