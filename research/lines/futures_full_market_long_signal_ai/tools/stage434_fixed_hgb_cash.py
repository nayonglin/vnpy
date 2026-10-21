"""Fixed432 model-only HGB candidate cash adapter; no I/O on import.

The Stage297 thin execution/report pattern is reused, not its research identity.
Only Stage433 main choices enter unchanged157 K cash; no fit or old cash replay.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='45c93399f2d6552a77805c9ca5bce9568b8e32522a5b6cdf5c289de11dbe847d'
CANDIDATE='COMMON52_FIXED_SHALLOW_HGB'
REFS=LINE/'stages/20261020_0018_stage263_cash_interface_inventory_refs.json'
FIXTURE=LINE/'outputs/stage434_fixed_hgb_cash/synthetic_fixture.py'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
ACTION_FIELDS=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
    'entry_capacity_qty','N_u','low20_u','u_close']


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def read_bytes(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('bound new/small input differs '+b['path'])
    return raw


def read_json(b):return json.loads(read_bytes(b))


def stat_bound(b):
    if Path(b['path']).stat().st_size!=b['bytes']:raise ValueError('inherited frozen file size changed '+b['path'])


def write_json(path,value):
    with Path(path).open('w') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def source_bundle():return [binding(Path(__file__)),binding(FIXTURE)]


def prepare_choices(mothers,choices,expected_parents=161014):
    forward=mothers.loc[mothers.u_date.ge('2020-01-01')]
    if len(forward)!=expected_parents or len(choices)!=expected_parents or choices.event_id.duplicated().any():
        raise ValueError('complete ordered forward parent choices required')
    for col in MOTHER_FIELDS:
        a,b=forward[col].reset_index(drop=True),choices[col].reset_index(drop=True)
        equal=(a.astype(float).tolist()==b.astype(float).tolist()) if col in ('sequence_index','u_index') else a.astype(str).tolist()==b.astype(str).tolist()
        if not equal:raise ValueError('original complete parent identity differs '+col)
    if set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'}:
        raise ValueError('main fixed NARROW choices required')
    if not set(choices.arm).issubset({'VOLUNTARY_RESELECT',CANDIDATE}):raise ValueError('candidate/internal arm differs')
    picked=choices.copy();selected=picked.selected.astype(float)
    if not selected.isin([0,1]).all():raise ValueError('binary selected required')
    picked['selected']=selected.astype(int)
    ids=set(picked.loc[picked.selected.eq(1),'chosen_action_id'])
    if '' in ids or len(ids)!=int(picked.selected.sum()):raise ValueError('unique nonempty selected action IDs required; zero selections allowed')
    picked['arm']='VOLUNTARY_RESELECT' # helper schema alias only; never overwrite external identity
    return picked,ids


def collect_selected_actions(chunks,ids):
    frames=[];rows=0
    for chunk in chunks:
        rows+=len(chunk)
        if not set(ACTION_FIELDS).issubset(chunk.columns):raise ValueError('all16 causal action fields required')
        part=chunk.loc[chunk.action_id.isin(ids),ACTION_FIELDS].copy()
        if len(part):frames.append(part)
    result=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=ACTION_FIELDS)
    if result.action_id.duplicated().any() or set(result.action_id)!=set(ids):raise ValueError('each new selected action required exactly once')
    result.attrs['source_rows_seen']=rows
    return result


def fixed_gate(points, annual, held):
    keyed={(p['window'],p['cost']):p for p in points}
    if len(points)!=4 or set(keyed)!={(w,c) for w in WINDOWS for c in COSTS}:
        raise ValueError('four paired fixed comparisons required')
    finite=lambda x:x is not None and math.isfinite(float(x))
    checks={}
    for key,p in keyed.items():
        checks['_'.join(key)]=dict(
            equity_strictly_higher=finite(p.get('ending_equity_difference')) and p['ending_equity_difference']>0,
            drawdown_nonharm=finite(p.get('drawdown_percentage_point_difference')) and p['drawdown_percentage_point_difference']>=0,
            sharpe_nonharm=finite(p.get('sharpe_difference')) and p['sharpe_difference']>=0,
            positive_return=finite(p.get('active_total_return_pct')) and p['active_total_return_pct']>0,
            paired_growth=(finite(p.get('ci95_low')) and p['ci95_low']>0) if key[0]=='primary_2020'
                else (finite(p.get('cumulative_log_difference')) and p['cumulative_log_difference']>0))
    groups=held.get('groups',{})
    if set(groups)!={'holdout_0','holdout_1'}:raise ValueError('both original held groups required')
    family={g:finite(x.get('known_u_equal_mean_increment_R')) and x['known_u_equal_mean_increment_R']>=0 for g,x in groups.items()}
    unknowns={g:x.get('unknown_differential_selected_events') for g,x in groups.items()}
    years=[r for r in annual if r['window']=='primary_2020' and r['cost']=='stress' and str(r['year']) in set(map(str,range(2020,2026)))]
    if len(years)!=6 or {str(r['year']) for r in years}!=set(map(str,range(2020,2026))):
        raise ValueError('all six complete primary-stress years required')
    nonnegative=sum(finite(r.get('candidate_growth_amount')) and r['candidate_growth_amount']>=0 for r in years)
    incremental=sum(finite(r.get('growth_amount_difference')) and r['growth_amount_difference']>0 for r in years)
    passed=all(all(v.values()) for v in checks.values()) and all(family.values()) and nonnegative>=4 and incremental>=4
    return dict(nominal_all_fixed_gates_pass=bool(passed),predicates=checks,held_known_mean_nonnegative=family,
        held_unknown_differential_selected_events=unknowns,complete_stress_years_nonnegative=nonnegative,
        complete_stress_years_positive_paired_growth=incremental,weak_year_gate=nonnegative>=4 and incremental>=4,
        full_family_generalization_certified=False,unknown_bounds_available=False,
        production_qualified=False,goal_complete=False,alpha_proved=False,
        interpretation='Fixed432 nominal gates only; adaptive historical learner choice and unknown execution/source states remain limitations')


def pair_years(candidate,control):
    a={r['year']:r for r in candidate};b={r['year']:r for r in control}
    if set(a)!=set(b):raise ValueError('paired yearly source coverage differs')
    rows=[]
    for year in sorted(a):
        x,y=a[year],b[year]
        diff=lambda k:None if x.get(k) is None or y.get(k) is None else x[k]-y[k]
        rows.append(dict(year=year,partial=year=='2026',candidate_return_pct=x['return_pct'],control_return_pct=y['return_pct'],
            candidate_growth_amount=x['cash_growth'],control_growth_amount=y['cash_growth'],
            candidate_max_drawdown_pct=x['max_drawdown_pct'],control_max_drawdown_pct=y['max_drawdown_pct'],
            return_percentage_point_difference=diff('return_pct'),growth_amount_difference=diff('cash_growth'),
            drawdown_percentage_point_difference=diff('max_drawdown_pct')))
    return rows


def control_ledger_binding(control,role):
    """263 records original157 ledger names relative to each account folder."""
    item=control['ledgers_relative_to_directory'][role]
    return dict(path=str(Path(control['directory'])/item['file']),bytes=item['bytes'],sha256=item['sha256'])


def account_specs():return [dict(candidate=CANDIDATE,window=w,cost=c,account_id=f'NARROW_{CANDIDATE}_{w}_{c}') for w in WINDOWS for c in COSTS]


def run_four(output,run_account,export_account,*,before=None,finalize=None,metadata=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();started=completed=0
    records=[];status='failed';error=None;meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=434,started_at=began,**meta))
    def progress(account=None):write_json(out/'cash_progress.json',dict(cash_accounts_started=started,cash_accounts_completed=completed,current_account=account,max_new_candidate_cash=4,new_fit=0,old_control_replays=0))
    progress()
    try:
        if before:before(out)
        for spec in account_specs():
            if started>=4:raise ValueError('fixed four cash budget exhausted')
            started+=1;progress(spec['account_id']);book=run_account(spec)
            completed+=1;progress(spec['account_id']);records.append(export_account(spec,book))
        if (started,completed)!=(4,4):raise ValueError('exact four new candidates required')
        if finalize:finalize(out,records)
        status='completed';return records
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,cash_accounts_started=started,cash_accounts_completed=completed,
            max_new_candidate_cash=4,new_fit=0,old_control_replays=0,SQL=0,auto_retry=False,goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts=[binding(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='manifest.json']
        write_json(out/'manifest.json',dict(schema='stage434_fixed_hgb_cash_manifest_v1',status=status,candidate=CANDIDATE,
            accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,**meta,
            new_fit=0,new_cash_accounts=completed,cash_accounts_started=started,old_control_replays=0,goal_complete=False,production_qualified=False))


def load_runtime(cash_refs):
    for b in cash_refs['source_bundle']:
        if not same(binding(b['path']),b):raise ValueError('accepted small cash source changed '+b['path'])
    spec=importlib.util.spec_from_file_location('stage434_accepted157',TOOLS/'stage157_voluntary_cash.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; previous attempt retained')
    if LINE/'outputs/stage434_fixed_hgb_cash' not in out.parents:raise ValueError('Stage434 output root required')
    pb=binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact432 protocol required')
    p=read_json(pb)
    if p.get('schema')!='stage432_fixed_common52_hgb_learner_protocol_v1' or p.get('candidate')!=CANDIDATE:raise ValueError('432 identity differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization hash differs')
    auth=read_json(ab);bundle=source_bundle()
    expected=dict(schema='stage434_exact_root_authorization_v1',authorized_by='root',protocol_sha256=PROTOCOL_SHA,
        output=str(out),max_new_candidate_cash=4,max_new_fit=0)
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('single exact root research authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(bundle,key=lambda b:b['path']):raise ValueError('authorized source/fixture differs')
    if auth['interface_refs']['path']!=str(REFS):raise ValueError('exact263 accepted157 cash interface refs required')
    return out,p,pb,auth,ab,bundle


def execute(args):
    out,p,pb,auth,ab,bundle=authorize(args);state={}
    metadata=dict(protocol=pb,authorization=ab,
        fit_select_manifest=auth['fit_select_manifest'],source_bundle=bundle,research_identity_gate_only=True,fixture=False)

    def prepare(folder):
        m=read_json(auth['fit_select_manifest'])
        if (m.get('schema')!='stage433_fixed_hgb_fit_select_manifest_v1' or m.get('status')!='completed'
                or m.get('protocol_sha256')!=PROTOCOL_SHA or m.get('candidate')!=CANDIDATE):raise ValueError('completed433 exact fixed HGB candidate required')
        if not m.get('cash_eligible') or m.get('changed_main_parent_choices',0)<=0:raise ValueError('changed main choices required; identical choices imply zero new cash')
        cash=read_json(auth['interface_refs']);fixed=cash['input_bindings_inherited_from_accepted157']
        for role in ('mothers','actions'):
            if not same(m['inputs'][role],fixed[role]):raise ValueError('433 frozen dataset binding differs '+role)
        v=load_runtime(cash);r=v.reuse
        stat_bound(m['inputs']['mothers'])
        mothers=pd.read_csv(m['inputs']['mothers']['path'],usecols=MOTHER_FIELDS,dtype=str,keep_default_na=False)
        for col in ('sequence_index','u_index'):mothers[col]=mothers[col].astype(int)
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('full399252 canonical mother domain required')
        choices=pd.read_csv(io.BytesIO(read_bytes(m['artifacts']['choices_main'])),compression='gzip',dtype=str,keep_default_na=False)
        picked,ids=prepare_choices(mothers,choices)
        for col in ('sequence_index','u_index','chosen_action_sequence_index'):picked[col]=picked[col].astype(int)
        picked['score']=picked.score.replace('',np.nan).astype(float)
        stat_bound(m['inputs']['actions'])
        chunks=pd.read_csv(m['inputs']['actions']['path'],compression='gzip',usecols=ACTION_FIELDS,dtype=str,
            keep_default_na=False,chunksize=100000,float_precision='round_trip')
        actions=collect_selected_actions(chunks,ids)
        source_rows=actions.attrs['source_rows_seen']
        if source_rows!=1552456:raise ValueError('complete once-only action stream row count differs')
        r.numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
        boundaries=read_json(m['artifacts']['boundaries'])
        if boundaries.get('schema')!='stage156_voluntary_K_only_v1' or boundaries.get('account_deadline_certified') is not False:raise ValueError('unchanged noncertified voluntary K required')
        store,receipt,cache_meta=r.cache_source.restore_native_cache(cash['market_dependencies']['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=r.CachedMarket(store),store.calendar
        econ_binding=cash['market_dependencies']['economic_projection'];stat_bound(econ_binding)
        economics=json.loads(Path(econ_binding['path']).read_text())['instruments']
        if set(economics)!=set(store.series):raise ValueError('frozen cache/economics epochs differ')
        signals=v.make_voluntary_signals(actions,mothers,picked,boundaries['epochs'],market,dates,economics)
        if len(signals)!=len(ids):raise ValueError('new selected action admission differs')
        bounds={}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,d)) for d in BOUNDS[w])
            if end>=len(dates) or dates[end]!=BOUNDS[w][1]:raise ValueError('fixed window/source calendar differs')
            bounds[w]=(start,end)
        state.update(v=v,r=r,cash=cash,signals=signals,mothers=mothers,dates=dates,market=market,economics=economics,
            prepared=v.author.organize(signals,mothers,dates),bounds=bounds,receipt=receipt,cache_meta=cache_meta,
            families=sorted(mothers.family_id.unique()),summaries={},reports={},daily={},family_tables=[],held=read_json(m['artifacts']['held_diagnostic']))
        r.ref.write_table(folder/'signals_candidate.csv.gz',signals,[])
        trace=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index',
            'source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
        r.ref.write_table(folder/'boundary_lineage.csv.gz',signals[trace],[])
        write_json(folder/'source_read_receipt.json',dict(receipt,candidate=CANDIDATE,new_selected_actions=len(ids),
            main_parent_rows=161014,full_mother_rows=399252,action_source_rows=source_rows,action_streams=1,action_fields=ACTION_FIELDS,
            old4365_admission_gate_used=False,choices_binding=m['artifacts']['choices_main'],actions_binding=m['inputs']['actions'],
            original_canonical_from_full_mothers=True,new_fit=0,models_scores_labels_read=0,selectors_called=0,separate_old_large_prehashes=0))
        write_json(folder/'control_references.json',cash['control_accounts'])

    def run(spec):
        a,b=state['bounds'][spec['window']]
        return state['v'].kernel.run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],a,b,prepared=state['prepared'])

    def export(spec,book):
        r=state['r'];name=spec['account_id'];folder=out/name
        ledgers=r.write_ledgers(folder,book);summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,arm=CANDIDATE,source_helper_arm='VOLUNTARY_RESELECT',role='candidate',
            any_historical_stale=report['stale_days']>0,execution_unknown=book['execution_unknown'],
            capacity_unknown_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_tick_fills,slippage_already_in_fill_price=True,
            transaction_count_definition='closed_trades=closed roots; fills=all BUY/SELL fills; total_filled_qty=quantity')
        key=(spec['window'],spec['cost']);state['summaries'][key]=summary;state['reports'][name]=report;state['daily'][key]=pd.DataFrame(book['daily'])
        state['family_tables'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec,arm=CANDIDATE))
        groups,tails=r.extra_reports(book)
        for file,value in [('summary',summary),('diagnostics',report),('largest_wins_losses',tails)]:write_json(folder/(file+'.json'),r.kernel.original.safe(value))
        r.ref.write_table(folder/'sector_variant_attribution.csv.gz',groups,[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers)

    def finalize(folder,records):
        r=state['r'];cash=state['cash'];old=read_json(cash['small_identity_bindings']['157'])
        control_reports=read_json(old['diagnostics']);points=[];annual=[];paired_year=[];distributions={};metrics=list(state['summaries'].values());indices={}
        for w,b in cash['market_dependencies']['bootstrap_indices_optional_if_paired_CI_retained'].items():
            stat_bound(b);indices[w]=np.load(b['path'],allow_pickle=False)
        controls={(c['window'],c['cost']):c for c in cash['control_accounts']}
        for spec in account_specs():
            key=(spec['window'],spec['cost']);control=controls[key];baseline=read_json(control['summary']);active=state['summaries'][key]
            cd=pd.read_csv(io.BytesIO(read_bytes(control_ledger_binding(control,'daily'))),compression='gzip',float_precision='round_trip')
            stats,dist=r.paired_statistics(state['daily'][key],cd,indices[key[0]])
            points.append(dict(spec,control_account_id=control['account_id'],ending_equity_difference=active['ending_equity']-baseline['ending_equity'],
                sharpe_difference=None if active.get('sharpe') is None or baseline.get('sharpe') is None else active['sharpe']-baseline['sharpe'],active_total_return_pct=active['total_return_pct'],
                control_total_return_pct=baseline['total_return_pct'],**r.helpers.compare_points(active,baseline),**stats))
            distributions[key[0]+'_'+key[1]]=dist
            metrics.append(dict(baseline,account_id=control['account_id'],window=key[0],cost=key[1],role='control_reused',replayed=False))
            ar=state['reports'][spec['account_id']]['annual_slices'];br=control_reports[control['account_id']]['annual_slices']
            paired_year.extend(dict(window=key[0],cost=key[1],**a) for a in pair_years(ar,br))
            for name,role,rows in ((spec['account_id'],'candidate',ar),(control['account_id'],'control_reused',br)):
                annual.extend(dict(account_id=name,role=role,window=key[0],cost=key[1],**a) for a in rows)
        for name,value in [('account_summaries',metrics),('comparisons',points),('annual_slices',annual),('paired_annual',paired_year),
                ('bootstrap_distributions',pd.DataFrame(distributions)),('family_year_including_zero',pd.concat(state['family_tables'],ignore_index=True))]:
            r.ref.write_table(folder/(name+'.csv.gz'),value,[])
        gate=fixed_gate(points,paired_year,state['held'])
        gate.update(any_candidate_historical_stale=any(s['any_historical_stale'] for s in state['summaries'].values()),
            any_candidate_execution_unknown=any(s['execution_unknown'] for s in state['summaries'].values()),
            CI_is_paired_daily_log_growth_diagnostic=True,overlapping_action_and_source_days_not_independent=True,
            bootstrap_indices_regenerated=False,mapped_product_scope='all original98 products',historical_first_seen_PIT_proved=False)
        write_json(folder/'decision.json',gate)
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('source drift or SQL budget violation')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['receipt']['database_after']:raise ValueError('native database stat drift')

    return run_four(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())


if __name__=='__main__':main()
