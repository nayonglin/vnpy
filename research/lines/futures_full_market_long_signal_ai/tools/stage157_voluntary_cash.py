"""Stage157: four cache-only VOLUNTARY_RESELECT cash books under frozen155.

Import performs no financial work. Root must supply an exact source/input
authorization and a fresh output. Accepted131 arithmetic is unchanged; only a
local signal copy receives min(source lifecycle, voluntary calendar K).
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
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
PROTOCOL_SHA='7ec4f92b31b46b04e0a17812878acb7f6305c9c476f9350d84bb7d873fe11e47'
ARM='VOLUNTARY_RESELECT'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
INPUT_ROLES=('execution_protocol','dataset_manifest','fit_manifest','actions','mothers',
    'native_cache_manifest','native_cache','market_protocol','accepted_cash_manifest',
    'accepted_review_receipt','choice_manifest','choices_main','boundaries')
FIXED_SOURCE_MAP=dict(execution_protocol='base_execution_protocol',dataset_manifest='dataset_manifest',
    fit_manifest='fit_manifest',actions='actions',mothers='mothers',
    native_cache_manifest='native_cache_json',native_cache='native_cache_file')


def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


reuse=load('stage148_fx_cash.py','stage157_pure148_helpers')
author,cache_source=reuse.author,reuse.cache_source
kernel,ref,helpers,report_helpers=reuse.kernel,reuse.ref,reuse.helpers,reuse.report_helpers
read_json,verify_file,numeric=reuse.read_json,reuse.verify_file,reuse.numeric
CachedMarket,paired_statistics=reuse.CachedMarket,reuse.paired_statistics
write_ledgers,extra_reports=reuse.write_ledgers,reuse.extra_reports


def source_bundle():
    paths={b['path'] for b in reuse.source_bundle()}
    paths.update(str(TOOLS/n) for n in ('stage157_voluntary_cash.py','test_stage157_voluntary_cash.py'))
    return sorted((ref.file_binding(p) for p in paths),key=lambda b:b['path'])


def account_specs():
    return [dict(arm=ARM,window=w,cost=c,account_id=f'NARROW_{ARM}_{w}_{c}')
        for w in WINDOWS for c in COSTS]


def apply_boundaries(signals,boundaries):
    """Adapt only a private signal frame; missing beyond-calendar K is not end."""
    result=signals.copy()
    source,voluntary,effective,origin,states,targets,dates=[],[],[],[],[],[],[]
    for row in result.to_dict('records'):
        epoch=row['reference_epoch']
        if epoch not in boundaries:
            raise ValueError('selected epoch has no voluntary boundary '+epoch)
        b=boundaries[epoch];old=int(row['lifecycle_index']);k=b['K_index'];state=b['K_state']
        if k is None:
            if state!='after_calendar_pending':
                raise ValueError('selected K missing without after-calendar pending')
            eff,which=old,'source_lifecycle'
        else:
            if isinstance(k,bool) or int(k)!=k or k<0:
                raise ValueError('invalid voluntary native calendar index')
            k=int(k)
            if int(row['D_index'])>=k:
                raise ValueError('selected prospective entry violates D<K')
            eff=min(old,k)
            which='same_source_and_voluntary' if old==k else 'source_lifecycle' if old<k else 'voluntary_calendar'
        source.append(old);voluntary.append(k);effective.append(eff);origin.append(which)
        states.append(state);targets.append(b['K_target_date']);dates.append(b['K_date'])
    result['source_lifecycle_index']=source
    result['voluntary_boundary_index']=voluntary
    result['effective_lifecycle_index']=effective
    result['effective_boundary_origin']=origin
    result['K_state']=states;result['K_target_date']=targets;result['K_date']=dates
    result['lifecycle_index']=effective
    return result


def make_voluntary_signals(actions,mothers,choices,boundaries,market,dates,economics):
    picked=choices.copy()
    if set(picked.arm)!={ARM} or set(picked.scope)!={'main'}:
        raise ValueError('complete single voluntary main arm required')
    picked['arm']='B'
    source=author.make_signals(actions,mothers,picked,'B',market,dates,economics)
    source['arm']=ARM;source['control_id']=ARM
    result=apply_boundaries(source,boundaries)
    for row in result.to_dict('records'):
        k=row['voluntary_boundary_index']
        if pd.notna(k) and int(k)<len(dates) and dates[int(k)]!=row['K_date']:
            raise ValueError('boundary and cached source calendar differ')
    return result


def fixed_gate(points,any_stale,*,wealth_positive,execution_unknown):
    lookup={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(lookup)!={(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('four fixed comparisons required')
    finite=lambda x:x is not None and np.isfinite(x)
    primary=lookup[('primary_2020','stress')]
    own=all(finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0 for p in points)
    ret=all(finite(p.get('return_percentage_point_difference')) and
        (p['return_percentage_point_difference']>0 if p is primary else p['return_percentage_point_difference']>=0)
        for p in points)
    dd=all(finite(p.get('drawdown_percentage_point_difference')) and
        (p['drawdown_percentage_point_difference']>0 if p is primary else p['drawdown_percentage_point_difference']>=0)
        for p in points)
    ci=finite(primary.get('ci95_low')) and primary['ci95_low']>0
    nominal=bool(own and ret and dd and ci and wealth_positive)
    unknown=bool(any_stale or execution_unknown or not all(finite(p.get('drawdown_percentage_point_difference')) for p in points))
    return dict(status='unsupported' if not nominal else 'unknown_historical_stale' if any_stale else
        'unknown_execution_capacity_or_entry' if execution_unknown else 'nominal_policy_pass_unqualified',
        cash_nominal_pass=nominal,nominal_pass=bool(nominal and not unknown),financial_unknown=unknown,
        own_returns_positive_all_four=bool(own),return_gate=bool(ret),drawdown_gate=bool(dd),
        primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth_positive),
        any_historical_stale=bool(any_stale),execution_unknown=bool(execution_unknown),
        held_recomputed=False,new_model_generalization_claim=False,legal_clearance_proved=False,
        independent_actual_review_required=True,no_automatic_promotion=True,goal_complete=False,
        production_qualified=False,increased_betting_qualified=False)


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; failed attempts retained '+str(out))
    if LINE/'outputs/stage157_voluntary_cash' not in out.parents:
        raise ValueError('fresh Stage157 output directory required')
    pb=ref.file_binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen155 protocol required')
    protocol=read_json(pb)
    if protocol.get('schema')!='stage155_voluntary_calendar_full_domain_protocol_v1' or protocol.get('line_id')!=LINE.name:
        raise ValueError('frozen155 identity differs')
    ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=read_json(ab)
    expected=dict(schema='stage155_exact_root_authorization_v1',authorized_by='root',stage='cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():
        raise ValueError('authorized source/tests bundle differs')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!=set(INPUT_ROLES):raise ValueError('exact fixed source and new156 roles required')
    for role,frozen in FIXED_SOURCE_MAP.items():
        author.same_binding(inputs[role],protocol['source_bindings'][frozen],'155 '+role)
    c=protocol['cash']
    if (c['initial_capital'],c['single_family_risk'],c['total_risk'],c['buffered_margin_cap'],c['margin_buffer'])!=(ref.INITIAL,ref.SINGLE_RISK,ref.TOTAL_RISK,ref.MARGIN_CAP,ref.MARGIN_BUFFER):
        raise ValueError('unchanged accepted cash constants required')
    if c['initial_stop_N']!=.25 or c['new_accounts_max']!=4 or not c['cache_only'] or c['native_SQL']!=0:
        raise ValueError('fixed four cash/zero SQL/.25N policy required')
    return protocol,pb,auth,ab


def validate_upstream(protocol,inputs):
    execution=read_json(inputs['execution_protocol'])
    author.same_binding(inputs['market_protocol'],execution['inputs']['market_protocol'],'128 market protocol')
    baseline=read_json(inputs['accepted_cash_manifest'])
    if baseline.get('schema')!='stage131_contract_choice_cash_v1' or baseline.get('status')!='completed' or baseline.get('new_cash_accounts')!=8:
        raise ValueError('completed accepted131 old books required')
    author.same_binding(baseline['protocol'],inputs['execution_protocol'],'131 protocol')
    if author.source_bundle()!=baseline['source_bundle']:
        raise ValueError('accepted131 source must stay byte-identical')
    for role in ('actions','mothers','dataset_manifest','fit_manifest','market_protocol'):
        author.same_binding(baseline['input_bindings'][role],inputs[role],'131 '+role)
    accepted=read_json(inputs['accepted_review_receipt'])
    if accepted.get('completed') is not True or accepted.get('research_arithmetic_accepted') is not True or (accepted.get('C'),accepted.get('I'))!=(0,0):
        raise ValueError('accepted132 receipt required; no re-review')
    choice=read_json(inputs['choice_manifest'])
    if choice.get('schema')!='stage156_voluntary_choices_manifest_v1' or choice.get('parent_rows')!=161014 or choice.get('main_action_rows')!=966740:
        raise ValueError('completed156 selector required')
    author.same_binding(choice['inputs']['protocol'],ref.file_binding(LINE/'outputs/stage155_voluntary_calendar_protocol/protocol.json'),'156 protocol')
    if choice['inputs']['protocol']['sha256']!=PROTOCOL_SHA:raise ValueError('156 protocol differs')
    for role in ('fit_manifest','mothers'):
        author.same_binding(choice['inputs'][role],inputs[role],'156 '+role)
    for role in ('choices_main','boundaries'):
        author.same_binding(choice['artifacts'][role],inputs[role],'156 '+role)
    terminal=read_json(choice['artifacts']['terminal'])
    if terminal.get('status')!='completed' or terminal.get('exit_code')!=0:
        raise ValueError('156 actual terminal incomplete')
    meta=read_json(inputs['native_cache_manifest'])
    author.same_binding(meta['file'],inputs['native_cache'],'132 arrays')
    return execution,choice,baseline


def load_selected_inputs(inputs):
    verify_file(inputs['mothers'])
    mothers=pd.read_csv(inputs['mothers']['path'],dtype=str,keep_default_na=False,usecols=reuse.IDENTITY)
    numeric(mothers,['sequence_index','u_index'])
    if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:
        raise ValueError('complete unchanged129 mothers required')
    verify_file(inputs['choices_main'])
    choices=pd.read_csv(inputs['choices_main']['path'],dtype=str,keep_default_na=False,float_precision='round_trip')
    numeric(choices,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    expected=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if len(expected)!=161014 or len(choices)!=161014 or set(choices.arm)!={ARM} or set(choices.scope)!={'main'}:
        raise ValueError('complete161014 main parents required')
    if choices.event_id.duplicated().any() or choices.event_id.tolist()!=expected.event_id.tolist():
        raise ValueError('full parent order/identity changed')
    for col in ('product_id','family_id','u_date','u_index','reference_epoch','sequence_index'):
        if choices[col].tolist()!=expected[col].tolist():raise ValueError('full parent identity differs '+col)
    ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id'])
    if not ids:raise ValueError('exact zero selected opportunities; stop0cash')
    verify_file(inputs['actions']);frames=[]
    for chunk in pd.read_csv(inputs['actions']['path'],dtype=str,keep_default_na=False,compression='gzip',
            usecols=reuse.ACTION_FIELDS,chunksize=100000,float_precision='round_trip'):
        part=chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(part):frames.append(part)
    actions=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=reuse.ACTION_FIELDS)
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    if actions.action_id.duplicated().any() or set(actions.action_id)!=ids:
        raise ValueError('all selected exact129 child actions required')
    boundary_document=read_json(inputs['boundaries'])
    if boundary_document.get('schema')!='stage156_voluntary_K_only_v1' or boundary_document.get('account_deadline_certified') is not False:
        raise ValueError('156 non-certified voluntary-only boundary document required')
    return mothers,choices,actions,boundary_document['epochs']


def baseline_references(protocol):
    references=protocol['cash']['read_only_control_books'];summaries={};daily={};reports={}
    diagnostic_cache={}
    for spec in account_specs():
        w,c=spec['window'],spec['cost'];b=references[w+'_'+c]
        summaries[(w,c)]=read_json(b['summary'])
        daily[(w,c)]=pd.read_csv(io.BytesIO(ref.read_bound(b['daily'])),compression='gzip')
        key=b['diagnostics']['path']
        if key not in diagnostic_cache:diagnostic_cache[key]=read_json(b['diagnostics'])
        reports[b['source_account_id']]=diagnostic_cache[key][b['diagnostic_key']]
    return references,summaries,daily,reports


def sector_year_attribution(book):
    """Calendar-year equity contributions, including every zero sector/variant."""
    daily=pd.DataFrame(book['daily']);date_index=daily.date.tolist();years=daily.date.str[:4].to_numpy()
    roots=book['closed_episodes']+book['open_episodes'];root_product={r['root_id']:r['product_id'] for r in roots}
    fills=pd.DataFrame(book['fills']);positions=pd.DataFrame(book['position_days']);rows=[]
    for dimension,names in (('market_sector',('financial','commodity')),('product_variant',('ordinary','F'))):
        for name in names:
            ids={root_id for root_id,p in root_product.items() if
                (('financial' if p.startswith('CFFEX.') else 'commodity') if dimension=='market_sector'
                 else ('F' if p.endswith('_F') else 'ordinary'))==name}
            f=fills.loc[fills.root_id.isin(ids)] if len(fills) else fills
            p=positions.loc[positions.root_id.isin(ids)] if len(positions) else positions
            realized=f.groupby('date').realized_gross.sum().reindex(date_index,fill_value=0.).to_numpy() if len(f) else np.zeros(len(daily))
            fees=f.groupby('date').fee.sum().reindex(date_index,fill_value=0.).to_numpy() if len(f) else np.zeros(len(daily))
            slip=f.groupby('date').slippage.sum().reindex(date_index,fill_value=0.).to_numpy() if len(f) else np.zeros(len(daily))
            unrealized=p.groupby('date').unrealized.sum().reindex(date_index,fill_value=0.).to_numpy() if len(p) else np.zeros(len(daily))
            contribution=realized-fees+np.diff(np.r_[0.,unrealized])
            for year in sorted(set(years)):
                mask=years==year
                part=f.loc[f.date.str.startswith(year)] if len(f) else f
                rows.append(dict(dimension=dimension,group=name,year=year,net_equity_contribution=float(contribution[mask].sum()),
                    fee=float(fees[mask].sum()),slippage=float(slip[mask].sum()),fill_count=len(part),
                    filled_qty=int(part.qty.sum()) if len(part) else 0,slippage_already_in_fill_price=True))
    for dimension in ('market_sector','product_variant'):
        total=sum(r['net_equity_contribution'] for r in rows if r['dimension']==dimension)
        if not np.isclose(total,float(daily.equity.iloc[-1])-ref.INITIAL,rtol=1e-12,atol=1e-6):
            raise ValueError('sector/variant annual attribution identity differs')
    return rows


def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    began,clock=datetime.now(timezone.utc).isoformat(),time.monotonic()
    before=source_bundle();status,error,started,completed='failed',None,0,0
    accounts,summaries,daily,reports,family_tables,capacities=[],{},{},{},[],[]
    ref.write_json(out/'actual_started.json',dict(stage='cash',status='started',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        execution,choice_manifest,baseline_manifest=validate_upstream(protocol,inputs)
        mothers,choices,actions,boundaries=load_selected_inputs(inputs)
        store,native_receipt,_=cache_source.restore_native_cache(inputs['native_cache_manifest'])
        if native_receipt['native_source_queries']!=0 or ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=CachedMarket(store),store.calendar
        market_protocol=read_json(inputs['market_protocol'])
        economics=read_json(market_protocol['economic_projection'])['instruments']
        if set(economics)!=set(store.series):raise ValueError('exact cached economics required')
        indices={w:np.load(io.BytesIO(ref.read_bound(protocol['statistics']['indices'][w])),allow_pickle=False) for w in WINDOWS}
        baseline_books,control_summaries,control_daily,control_reports=baseline_references(protocol)
        signals=make_voluntary_signals(actions,mothers,choices,boundaries,market,dates,economics)
        ref.write_table(out/'signals_VOLUNTARY_RESELECT.csv.gz',signals,[])
        trace_cols=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin',
            'K_target_date','K_date','K_state']
        ref.write_table(out/'boundary_lineage.csv.gz',signals[trace_cols],[])
        prepared=author.organize(signals,mothers,dates)
        ref.write_json(out/'source_read_receipt.json',dict(native_receipt,actual_model_fit_calls=0,new_labels=0,
            old_baseline_replays=0,selected_source_children=len(actions),full_forward_parent_rows=161014,
            full_mother_rows=len(mothers),canonical_from_full_original_mothers=True,original_source_lifecycle_modified=False))
        all_groups,all_tails,all_sector_year=[],{},[]
        families=sorted(mothers.family_id.unique())
        for spec in account_specs():
            w,c,name=spec['window'],spec['cost'],spec['account_id'];bounds=protocol['cash']['windows'][w]
            if execution['cash']['windows'][w]!=bounds:raise ValueError('unchanged execution window required')
            start,end=(int(np.searchsorted(dates,v)) for v in bounds)
            if end>=len(dates) or dates[end]!=bounds[1] or indices[w].shape!=(2000,end-start+1):
                raise ValueError('fixed source calendar/window/index width differs')
            if started>=4:raise ValueError('four new cash budget exhausted')
            started+=1;reuse.write_cash_progress(out,started,completed,name)
            book=kernel.run_cash_account(signals,market,dates,economics,c,name,start,end,prepared=prepared)
            completed+=1;folder=out/name;ledgers=write_ledgers(folder,book)
            summary,report,fy=helpers.cash_report(book,families,ref.INITIAL)
            capacity=dict(account=name,arm=ARM,control_id=ARM,window=w,cost=c,execution_unknown=book['execution_unknown'],
                unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
                capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
            summary.update(capacity,any_historical_stale=report['stale_days']>0);report.update(capacity)
            summaries[(w,c)],daily[(w,c)],reports[name]=summary,pd.DataFrame(book['daily']),report
            capacities.append(capacity);family_tables.append(report_helpers.add_family_costs(fy,book).assign(arm=ARM,window=w,cost=c))
            groups,tails=extra_reports(book)
            all_groups.extend(dict(account=name,window=w,cost=c,**r) for r in groups);all_tails[name]=tails
            all_sector_year.extend(dict(account=name,window=w,cost=c,**r) for r in sector_year_attribution(book))
            ref.write_json(folder/'summary.json',kernel.original.safe(summary))
            accounts.append(dict(spec,directory=str(folder),summary=ref.file_binding(folder/'summary.json'),ledgers=ledgers))
            print(json.dumps(dict(phase='account_complete',account=name,cash_accounts_started=started,new_cash_accounts=completed)),flush=True)
        if started!=4 or completed!=4 or ref.NATIVE_QUERIES!=0:raise ValueError('exact4 accounts/zero SQL required')
        points,distributions=[],{}
        for spec in account_specs():
            w,c=spec['window'],spec['cost'];key=(w,c)
            stats,dist=paired_statistics(daily[key],control_daily[key],indices[w])
            points.append(dict(window=w,cost=c,contrast=ARM+'_minus_CONTROL_REUSED',
                active_total_return_pct=summaries[key]['total_return_pct'],reference_total_return_pct=control_summaries[key]['total_return_pct'],
                **helpers.compare_points(summaries[key],control_summaries[key]),**stats))
            distributions[w+'_'+c+'_'+ARM+'_minus_CONTROL_REUSED']=dist
        stale=any(r['stale_days']>0 for r in list(reports.values())+list(control_reports.values()))
        unknown=any(s['execution_unknown'] for s in list(summaries.values())+list(control_summaries.values()))
        wealth=all(reuse._log_path(f)[0] is not None for f in list(daily.values())+list(control_daily.values()))
        gate=fixed_gate(points,stale,wealth_positive=wealth,execution_unknown=unknown)
        fy=pd.concat(family_tables,ignore_index=True)
        # Preserve all old control family-year rows read-only; never replay them.
        old_fy_binding=reuse.artifact(baseline_manifest,'family_year_including_zero.csv.gz')
        old_fy=pd.read_csv(io.BytesIO(ref.read_bound(old_fy_binding)),compression='gzip',dtype={'year':str})
        old_fy=old_fy.loc[old_fy.arm.eq('B')].copy();old_fy['arm']='CONTROL_REUSED'
        fy=pd.concat([fy,old_fy],ignore_index=True)
        ref.write_table(out/'comparisons.csv.gz',points,[])
        ref.write_table(out/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        ref.write_table(out/'family_year_including_zero.csv.gz',fy,[])
        ref.write_table(out/'family_total_including_zero.csv.gz',fy.groupby(['arm','window','cost','family_id'])[
            ['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index(),[])
        ref.write_table(out/'annual_slices.csv.gz',[dict(account=a,**r) for a,p in {**reports,**control_reports}.items() for r in p['annual_slices']],[])
        metrics=[dict(summaries[(s['window'],s['cost'])]) for s in account_specs()]
        metrics.extend(dict(control_summaries[(s['window'],s['cost'])],arm='CONTROL_REUSED',window=s['window'],cost=s['cost'],
            source_only=True,replayed=False) for s in account_specs())
        ref.write_table(out/'account_summaries.csv.gz',metrics,[])
        ref.write_table(out/'capacity_summary.csv.gz',capacities,[])
        ref.write_table(out/'sector_variant_attribution.csv.gz',all_groups,[])
        ref.write_table(out/'sector_variant_year_including_zero.csv.gz',all_sector_year,[])
        ref.write_json(out/'largest_wins_losses.json',kernel.original.safe(all_tails))
        ref.write_json(out/'diagnostics.json',kernel.original.safe(reports))
        ref.write_json(out/'baseline_references.json',baseline_books)
        ref.write_json(out/'continuation_gate.json',kernel.original.safe(gate))
        ref.write_json(out/'signal_identification.json',dict(full_mother_rows=399252,full_main_parent_rows=161014,
            selected_actions=len(signals),full_choices_binding=inputs['choices_main'],boundary_binding=inputs['boundaries'],
            choice_manifest=inputs['choice_manifest'],canonical_from_full_original_mothers=True,
            filter_full_domain_before_argmax=True,old_B_selection_used_as_admission_gate=False,
            future_label_state_used_as_admission_gate=False,local_B_schema_alias_only=True,old_global_ARMS_changed=False,
            held_recomputed=False,new_model_generalization_claim=False))
        ref.write_json(out/'budget_and_tick_disclosure.json',dict(policy='NARROW',kernel='unchanged accepted131',
            budget=protocol['cash'],capacity=execution['cash']['capacity'],anchor=execution['cash']['anchor_and_execution'],
            bootstrap_indices=protocol['statistics']['indices'],bootstrap_indices_regenerated=False,
            fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,
            no_actual_orderbook_execution_proof=True,legal_clearance_proved=False,source_archive_is_final_reconstruction=True,
            voluntary_generic_kernel_reason='lifecycle_exit; see source/voluntary/effective sidecar',
            goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        if source_bundle()!=before:raise ValueError('authorized157 source changed during actual')
        if cache_source.database_state(read_json(inputs['native_cache_manifest'])['database']['path'])!=native_receipt['database_after']:
            raise ValueError('cached database stat changed during actual')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,cash_accounts_started=started,new_cash_accounts=completed,
            native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_labels=0,downloads=0,
            whole_database_hashes=0,old_baseline_replays=0,old_control_cash_replays=0,fixture=False,python=sys.executable))
    artifacts=[dict(ref.file_binding(p),logical_name=str(p.relative_to(out)),role='decision_asset',
        feature_schema='stage157_voluntary_cash_v1',raw_ohlc=False,reproducibility_required=True)
        for p in sorted(out.rglob('*')) if p.is_file()]
    manifest=dict(schema='stage157_voluntary_cash_v1',status=status,mode='actual',protocol=pb,protocol_sha256=PROTOCOL_SHA,
        authorization=ab,source_bundle=before,input_bindings=inputs,terminal=ref.file_binding(out/'actual_terminal.json'),
        artifacts=artifacts,accounts=accounts,signals=ref.file_binding(out/'signals_VOLUNTARY_RESELECT.csv.gz'),
        boundary_lineage=ref.file_binding(out/'boundary_lineage.csv.gz'),baseline_books=baseline_books,
        control_family_year_source=old_fy_binding,bootstrap_indices=protocol['statistics']['indices'],new_cash_accounts=completed,
        native_source_queries=0,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,old_control_cash_replays=0,
        goal_complete=False,production_qualified=False,increased_betting_qualified=False)
    json_names={'largest_wins_losses','diagnostics','continuation_gate','signal_identification','budget_and_tick_disclosure','source_read_receipt'}
    for name in ('comparisons','bootstrap_distributions','account_summaries','family_year_including_zero',
        'family_total_including_zero','annual_slices','capacity_summary','sector_variant_attribution',
        'sector_variant_year_including_zero',*sorted(json_names)):
        manifest[name]=ref.file_binding(out/(name+('.json' if name in json_names else '.csv.gz')))
    ref.write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),new_cash_accounts=completed,native_source_queries=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
