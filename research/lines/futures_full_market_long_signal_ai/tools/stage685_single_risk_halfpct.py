"""Frozen684: two cache-only 0.5% risk books, reusing exact675 signals.

Only root launches actual_run1. Three private function namespaces replace the
single-risk constant on the real070 reservation path; accepted sources and all
their module globals remain unchanged. Import performs no financial replay.
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
from types import FunctionType, SimpleNamespace
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage684_single_risk_halfpct_protocol/protocol.json'
PROTOCOL_SHA='51545297db2db5c729751acc23b2b045f2cc4808c0c463010e0a9b4b7b8d84d3'
OUTPUT=LINE/'outputs/stage685_single_risk_halfpct/actual_run1'
START='2015-01-01';END='2026-10-16';SINGLE_RISK=.005
INPUT_ROLES={'baseline_manifest','baseline_terminal','baseline_review','signals','mothers',
    'native_cache_manifest','native_cache','market_protocol','calendar','economic_projection',
    'baseline_annual','baseline_diagnostics','baseline_base_summary','baseline_base_daily',
    'baseline_stress_summary','baseline_stress_daily'}

def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

cash=load('stage157_voluntary_cash.py','halfpct685_pure_cash157')
ref=cash.ref

def clone_function(function,**replacements):
    namespace=dict(function.__globals__);namespace.update(replacements)
    result=FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
    result.__kwdefaults__=function.__kwdefaults__
    return result

def build_private_kernel():
    """Copy the three call-site namespaces, never modify accepted globals."""
    old=cash.kernel
    batch=clone_function(old.original.reserve_batch,SINGLE_RISK=SINGLE_RISK)
    capped=clone_function(old.reserve_capped,original=SimpleNamespace(reserve_batch=batch))
    run=clone_function(old.run_cash_account,reserve_capped=capped)
    return SimpleNamespace(reserve_batch=batch,reserve_capped=capped,run_cash_account=run)

private_kernel=build_private_kernel()

def snapshot_old_globals():
    return {label:{k:id(v) for k,v in module.__dict__.items()}
        for label,module in [('accepted131',cash.kernel),('accepted070',cash.kernel.original),('accepted042',ref)]}

def parameter_receipt(before):
    old=cash.kernel;new=private_kernel
    unchanged=before==snapshot_old_globals()
    graph=(new.reserve_batch.__code__ is old.original.reserve_batch.__code__
        and new.reserve_capped.__code__ is old.reserve_capped.__code__
        and new.run_cash_account.__code__ is old.run_cash_account.__code__
        and new.reserve_batch.__defaults__ is old.original.reserve_batch.__defaults__
        and new.reserve_capped.__defaults__ is old.reserve_capped.__defaults__
        and new.run_cash_account.__defaults__ is old.run_cash_account.__defaults__
        and new.reserve_capped.__globals__['original'].reserve_batch is new.reserve_batch
        and new.run_cash_account.__globals__['reserve_capped'] is new.reserve_capped)
    effective=dict(SINGLE_RISK=new.reserve_batch.__globals__['SINGLE_RISK'],TOTAL_RISK=old.TOTAL_RISK,
        MARGIN_CAP=old.MARGIN_CAP,MARGIN_BUFFER=old.MARGIN_BUFFER,initial_stop_N=old.policy_k('NARROW'))
    if not unchanged or not graph or tuple(effective.values())!=(.005,.02,.25,1.1,.25):
        raise ValueError('private risk call graph/constants or accepted globals changed')
    if (old.SINGLE_RISK,old.original.SINGLE_RISK,ref.SINGLE_RISK)!=(.0025,.0025,.0025):
        raise ValueError('accepted single risk changed')
    return dict(schema='stage685_parameter_effectiveness_v1',effective=effective,
        old_single_risk=dict(accepted131=old.SINGLE_RISK,accepted070=old.original.SINGLE_RISK,accepted042=ref.SINGLE_RISK),
        old_globals_unchanged=unchanged,three_private_call_sites_verified=graph,code_and_defaults_identical=True,
        changed_global_names=['private070.SINGLE_RISK','private131.reserve_capped.original','private131.run_cash_account.reserve_capped'],
        scale_before_capacity=True,D_only_reduces=True,existing_risk_frozen_at_entry=True,
        source_namespace_sizes={k:len(v) for k,v in before.items()})

def source_bundle():
    paths={b['path'] for b in cash.source_bundle()}
    paths.update(str(TOOLS/n) for n in ('stage685_single_risk_halfpct.py','test_stage685_single_risk_halfpct.py'))
    return sorted((ref.file_binding(p) for p in paths),key=lambda b:b['path'])

def describe_daily_pair(active,baseline,initial):
    if active.date.tolist()!=baseline.date.tolist():raise ValueError('paired source calendar differs')
    a=active.equity.to_numpy(float);b=baseline.equity.to_numpy(float)
    if not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('nonfinite paired equity')
    diff=a-b
    return dict(source_days=len(a),first_date=str(active.date.iloc[0]),last_date=str(active.date.iloc[-1]),
        final_equity_difference=float(diff[-1]),minimum_daily_equity_difference=float(diff.min()),
        maximum_daily_equity_difference=float(diff.max()),days_candidate_above=int((diff>0).sum()),
        days_candidate_below=int((diff<0).sum()),bootstrap_performed=False,CI_computed=False,
        descriptive_same_history_only=True,initial_equity=initial)

def point_dominance(comparisons):
    metrics=('total_return_pct','max_drawdown_pct','sharpe')
    def dominates(point):
        a,b=point['active_summary'],point['baseline_summary']
        return (not a.get('ever_insolvent',False) and not b.get('ever_insolvent',False)
            and all(ref.finite(a.get(k)) and ref.finite(b.get(k)) and a[k]>=b[k] for k in metrics))
    return bool(comparisons and all(dominates(point) for point in comparisons))

def authorize(args):
    out=Path(args.output).resolve()
    if out!=OUTPUT.resolve() or out.exists():raise ValueError('unique fresh685 actual_run1 output required')
    pb=ref.file_binding(args.protocol)
    if pb['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('frozen684 protocol mismatch')
    protocol=json.loads(ref.read_bound(pb))
    if (protocol.get('schema')!='stage684_single_risk_halfpct_protocol_v1' or protocol.get('line_id')!=LINE.name
        or protocol.get('stage')!=684):raise ValueError('frozen684 identity differs')
    ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization hash mismatch')
    auth=json.loads(ref.read_bound(ab))
    required=dict(schema='stage684_exact_root_authorization_v1',authorized_by='root',stage='risk_halfpct_cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle():
        raise ValueError('exact root source authorization required')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES or auth['input_bindings']!=protocol['inputs']:
        raise ValueError('exact16 frozen input bindings required')
    if protocol['change']!=dict(parameter='SINGLE_RISK',old=.0025,new=.005,other_parameters_changed=False):
        raise ValueError('single declared risk change required')
    limits=dict(new_fit=0,new_cash=2,old_refit=0,old_cash_replay=0,SQL=0,downloads=0,new_labels=0,new_scores=0,bootstrap=0,risk_grid_scan=False)
    if protocol['limits']!=limits:raise ValueError('exact0fit2cash finite budget required')
    return protocol,pb,auth,ab

def validate_upstream(inputs,baseline,terminal,review,market,meta):
    if (baseline.get('schema')!='stage675_common52_2015_extension_v1' or baseline.get('mode')!='actual'
        or baseline.get('status')!='completed' or baseline.get('actual_fit_calls_completed')!=1
        or baseline.get('new_cash_accounts')!=2):raise ValueError('completed675 exact1fit2cash baseline required')
    if (terminal.get('status')!='completed' or terminal.get('exit_code')!=0
        or terminal.get('new_cash_accounts')!=2 or terminal.get('actual_fit_calls_completed')!=1):
        raise ValueError('completed675 terminal required')
    if (review.get('completed') is not True or review.get('research_arithmetic_accepted') is not True
        or tuple(review.get(k) for k in ('C','I','M'))!=(0,0,0)):raise ValueError('accepted676 review required')
    for a,b,label in [(baseline['terminal'],inputs['baseline_terminal'],'675 terminal'),
        (baseline['signals'],inputs['signals'],'675 signals'),(baseline['annual_slices'],inputs['baseline_annual'],'675 annual'),
        (baseline['diagnostics'],inputs['baseline_diagnostics'],'675 diagnostics'),(meta['file'],inputs['native_cache'],'132 cache'),
        (market['calendar'],inputs['calendar'],'market calendar'),(market['economic_projection'],inputs['economic_projection'],'market economics')]:
        cash.author.same_binding(a,b,label)
    for role in ('mothers','native_cache_manifest','native_cache','market_protocol'):
        cash.author.same_binding(baseline['input_bindings'][role],inputs[role],'675 '+role)
    specs={a['cost']:a for a in baseline['accounts']}
    if set(specs)!={'base','stress'}:raise ValueError('exact two675 baseline books required')
    for cost,a in specs.items():
        cash.author.same_binding(a['summary'],inputs['baseline_'+cost+'_summary'],'675 '+cost+' summary')
        cash.author.same_binding(a['ledgers']['daily'],inputs['baseline_'+cost+'_daily'],'675 '+cost+' daily')

def restore_native_once(meta,raw,dates):
    """Restore already bound archive once; database is only stat-checked."""
    if (meta.get('schema')!='stage132_native_store_recovery_cache_v1' or meta.get('native_rows')!=1552456
        or meta.get('native_epochs')!=9520):raise ValueError('exact original132 native cache required')
    before=cash.cache_source.database_state(meta['database']['path'])
    if any(meta['database'].get(k)!=v for k,v in before.items()):raise ValueError('cached database stat differs')
    store=cash.cache_source.NativeBars(dates)
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets'];flat={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        if len(epochs)!=9520 or offsets[0]!=0 or offsets[-1]!=1552456:raise ValueError('full native cache dimensions differ')
        for i,e in enumerate(epochs):store.series[e]={k:a[int(offsets[i]):int(offsets[i+1])] for k,a in flat.items()}
    after=cash.cache_source.database_state(meta['database']['path'])
    if before!=after:raise ValueError('database stat changed during cache restore')
    return store,dict(native_source_queries=0,native_contract_days=1552456,native_epochs=9520,
        database_before=before,database_after=after,database_rehashed=False,restored_from_exact_cache=True,cache_restores=1)

def risk_budget_diagnostics(book,account,cost):
    frame=pd.DataFrame(book['budgets']);new=frame.loc[frame.budget_kind.eq('new_entry')].copy()
    groups=[];raw_error=scale_error=0.
    for day,g in new.groupby('u_date',sort=True):
        first=g.iloc[0];equity=float(first.u_equity)
        expected=.005*equity/g.unit_risk_u if equity>0 else pd.Series(0.,index=g.index)
        raw_error=max(raw_error,float(abs(g.target_qty_unscaled-expected).max()))
        rawrisk=float((g.target_qty_unscaled*g.unit_risk_u).sum());rawmargin=float((g.target_qty_unscaled*g.unit_margin_u).sum())
        ar=max(0.,.02*equity-float(first.existing_risk));am=max(0.,.25*equity-float(first.existing_buffered_margin))
        risk_scale=ar/rawrisk if rawrisk else 1.;margin_scale=am/rawmargin if rawmargin else 1.
        scale=min(1.,risk_scale,margin_scale) if equity>0 else 0.
        scale_error=max(scale_error,float(abs(g.joint_scale-scale).max()))
        if (g.D_qty>g.qty_cap).any():raise ValueError('D quantity increased above reserved cap')
        groups.append(dict(account=account,cost=cost,u_date=day,equity=equity,candidate_families=len(g),
            existing_frozen_initial_risk=float(first.existing_risk),existing_buffered_margin=float(first.existing_buffered_margin),
            unscaled_risk=rawrisk,available_risk=ar,unscaled_buffered_margin=rawmargin,available_buffered_margin=am,
            risk_only_scale=risk_scale,margin_only_scale=margin_scale,joint_scale=scale,
            binding_constraint='risk_and_margin' if scale<1 and abs(risk_scale-margin_scale)<1e-12 else 'risk' if scale<1 and risk_scale<margin_scale else 'margin' if scale<1 else 'single_family_budget',
            allocated_risk=float(g.allocated_risk.sum()),allocated_buffered_margin=float(g.allocated_buffered_margin.sum()),
            pre_capacity_integer_qty=int(g.original_qty_cap.sum()),post_capacity_qty=int(g.qty_cap.sum()),executed_entry_qty=int(g.D_qty.sum()),
            capacity_reduced_candidates=int((g.qty_cap<g.original_qty_cap).sum()),zero_entry_candidates=int(g.D_qty.eq(0).sum())))
    if raw_error>1e-7 or scale_error>1e-10:raise ValueError('actual half-percent proposal/joint scale identity differs')
    return groups,dict(account=account,cost=cost,new_entry_reservations=len(new),u_batches=len(groups),
        maximum_unscaled_qty_identity_error=raw_error,maximum_joint_scale_identity_error=scale_error,
        execution_unknown=book['execution_unknown'],entry_execution_unknown=len(book['entry_execution_unknown']),
        capacity_unknown_roots=len(book['capacity_unknown_roots']))

def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False);began=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    before=source_bundle();globals_before=snapshot_old_globals();status='failed';error=None;started=completed=0
    read_paths=set();reads=[];accounts=[];summaries=[];annual=[];families_out=[];reports={};sensitivity=[];budget_checks=[]
    comparisons=[];curve=None;utilization=[];native_receipt=None
    def read(role):
        binding=inputs[role]
        if binding['path'] in read_paths:raise ValueError('duplicate old payload read '+binding['path'])
        raw=ref.read_bound(binding);read_paths.add(binding['path']);reads.append(dict(role=role,**binding,passes=1));return raw
    def table(role,**kwargs):
        return pd.read_csv(io.BytesIO(read(role)),compression='gzip',float_precision='round_trip',**kwargs)
    ref.write_json(out/'actual_started.json',dict(status='started',stage='risk_halfpct_cash',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        baseline=json.loads(read('baseline_manifest'));terminal=json.loads(read('baseline_terminal'));review=json.loads(read('baseline_review'))
        market_protocol=json.loads(read('market_protocol'));meta=json.loads(read('native_cache_manifest'))
        validate_upstream(inputs,baseline,terminal,review,market_protocol,meta)
        old_annual=table('baseline_annual');old_reports=json.loads(read('baseline_diagnostics'))
        old_summaries={c:json.loads(read('baseline_'+c+'_summary')) for c in ('base','stress')}
        old_daily={c:table('baseline_'+c+'_daily') for c in ('base','stress')}
        rawcal=np.load(io.BytesIO(read('calendar')),allow_pickle=False)
        dates=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in rawcal] if rawcal.dtype.kind in 'iu' else rawcal.astype('datetime64[D]').astype(str).tolist())
        start=int(np.searchsorted(dates,START));end=int(np.searchsorted(dates,END))
        if end>=len(dates) or dates[end]!=END or dates[start]!='2015-01-05' or end-start+1!=2862:raise ValueError('frozen continuous source calendar differs')
        mothers=table('mothers',usecols=cash.reuse.IDENTITY,dtype=str,keep_default_na=False)
        cash.numeric(mothers,['sequence_index','u_index'])
        if (len(mothers)!=399252 or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95
            or mothers.event_id.duplicated().any() or not np.array_equal(mothers.sequence_index,np.arange(len(mothers)))):
            raise ValueError('complete399252 canonical mothers/98 products/95 families required')
        signals=table('signals',dtype=str,keep_default_na=False)
        numeric=['u_index','D_index','N_u','low20_u','u_close','history_run','lifecycle_index','entry_capacity_qty','potential',
            'source_lifecycle_index','effective_lifecycle_index','action_sequence_index','mother_sequence_index','sequence_index']
        cash.numeric(signals,numeric)
        if (len(signals)!=5246 or signals.event_id.duplicated().any() or not signals.u_date.between(START,END).all()
            or not signals.potential.eq(1).all() or not signals.lifecycle_index.eq(signals.effective_lifecycle_index).all()):
            raise ValueError('exact5246 original prebudget voluntary signals required')
        prepared=cash.author.organize(signals,mothers,dates);families=sorted(mothers.family_id.unique())
        store,native_receipt=restore_native_once(meta,read('native_cache'),dates)
        economics=json.loads(read('economic_projection'))['instruments']
        if set(economics)!=set(store.series) or ref.NATIVE_QUERIES!=0:raise ValueError('native economics domain or zeroSQL differs')
        market=cash.CachedMarket(store);curve=pd.DataFrame({'date':dates[start:end+1]})
        for cost in ('base','stress'):
            name='all_2015_halfpct_'+cost
            if started>=2:raise ValueError('two new cash account budget exhausted')
            started+=1;cash.reuse.write_cash_progress(out,started,completed,name)
            book=private_kernel.run_cash_account(signals,market,dates,economics,cost,name,start,end,prepared=prepared)
            completed+=1
            ref.write_json(out/f'cash_completed_{completed:02d}.json',dict(account=name,cash_accounts_started=started,new_cash_accounts=completed))
            folder=out/name;ledgers=cash.write_ledgers(folder,book)
            summary,report,fy=cash.helpers.cash_report(book,families,ref.INITIAL)
            summary.update(account=name,account_id=name,arm=cash.ARM,window='all_2015',cost=cost,single_family_risk=.005,
                execution_unknown=book['execution_unknown'],any_historical_stale=report['stale_days']>0,
                unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
                capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
            ref.write_json(folder/'summary.json',cash.kernel.original.safe(summary));summaries.append(summary);reports[name]=report
            accounts.append(dict(account_id=name,arm=cash.ARM,window='all_2015',cost=cost,directory=str(folder),
                summary=ref.file_binding(folder/'summary.json'),ledgers=ledgers))
            families_out.append(cash.report_helpers.add_family_costs(fy,book).assign(account=name,arm=cash.ARM,window='all_2015',cost=cost))
            annual.extend(dict(account=name,cost=cost,**r) for r in report['annual_slices'])
            daily=pd.DataFrame(book['daily']);old=old_daily[cost]
            point=describe_daily_pair(daily,old,ref.INITIAL)
            scalar={k:float(summary[k])-float(old_summaries[cost][k]) for k in summary if k in old_summaries[cost]
                and isinstance(summary[k],(float,int,np.number)) and not isinstance(summary[k],(bool,np.bool_))
                and isinstance(old_summaries[cost][k],(float,int)) and not isinstance(old_summaries[cost][k],bool)}
            comparisons.append(dict(cost=cost,active_account=name,baseline_account=old_summaries[cost]['account_id'],
                active_single_risk=.005,baseline_single_risk=.0025,active_summary=summary,baseline_summary=old_summaries[cost],
                metric_differences=scalar,**cash.helpers.compare_points(summary,old_summaries[cost]),**point))
            rows,check=risk_budget_diagnostics(book,name,cost);sensitivity.extend(rows);budget_checks.append(check)
            for risk,frame in [('risk025',old),('risk050',daily)]:
                eq=frame.equity.to_numpy(float)
                curve[risk+'_'+cost+'_equity']=eq
                curve[risk+'_'+cost+'_drawdown_pct']=(eq/np.maximum.accumulate(np.r_[ref.INITIAL,eq])[1:]-1)*100
                for row in frame.to_dict('records'):
                    equity=float(row['equity'])
                    utilization.append(dict(account=row['account_id'],cost=cost,single_risk=.0025 if risk=='risk025' else .005,
                        date=row['date'],equity=equity,initial_risk=row['initial_risk'],buffered_margin=row['buffered_margin'],
                        frozen_initial_risk_pct=100*row['initial_risk']/equity if equity>0 else None,
                        buffered_margin_pct=100*row['buffered_margin']/equity if equity>0 else None,
                        new_order_risk_reserve=row['new_order_risk_reserve'],new_order_margin_reserve=row['new_order_margin_reserve']))
            print(json.dumps(dict(phase='account_complete',account=name,new_fit=0,new_cash=completed)),flush=True)
        if (started,completed)!=(2,2):raise ValueError('exact zero fit two cash completion required')
        columns=['date']+[r+'_'+c+'_'+v for r in ('risk025','risk050') for c in ('base','stress') for v in ('equity','drawdown_pct')]
        curve[columns].to_csv(out/'equity_and_drawdown.csv',index=False,float_format='%.17g')
        ref.write_table(out/'account_summaries.csv.gz',pd.DataFrame(summaries),[])
        ref.write_table(out/'annual_slices.csv.gz',pd.concat([old_annual,pd.DataFrame(annual)],ignore_index=True),[])
        ref.write_table(out/'family_year_including_zero.csv.gz',pd.concat(families_out,ignore_index=True),[])
        ref.write_table(out/'risk_budget_sensitivity.csv.gz',sensitivity,[])
        ref.write_table(out/'risk_utilization_comparison.csv.gz',utilization,[])
        ref.write_json(out/'diagnostics.json',cash.kernel.original.safe(reports))
        dominance=point_dominance(comparisons)
        ref.write_json(out/'comparison.json',cash.kernel.original.safe(dict(per_cost=comparisons,
            same_history_point_dominance=dominance,descriptive_only=True,bootstrap_performed=False,CI_computed=False,
            no_automatic_promotion=True,strict_PIT=False,production_qualified=False,increased_betting_qualified=False)))
        effectiveness=parameter_receipt(globals_before);effectiveness['actual_budget_checks']=budget_checks
        ref.write_json(out/'parameter_effectiveness_receipt.json',effectiveness)
        ref.write_json(out/'source_read_receipt.json',dict(payloads=reads,native=native_receipt,
            complete_original_mothers_for_canonical=True,exact_original_prebudget_signals_reused=True,
            old_cash_replays=0,old_refits=0,new_models=0,new_scores=0,new_labels=0,downloads=0,bootstrap=0,
            old_reservations_read=False,old_family_payload_read=False,strict_PIT=False,production_qualified=False))
        ref.write_json(out/'budget_and_execution_disclosure.json',dict(change=protocol['change'],fixed=protocol['fixed'],
            source_archive_final_reconstruction=True,no_gap_loss_cap=True,account_deadline_certified=False,
            fees_already_in_cash=True,slippage_already_in_fill_price=True,no_automatic_promotion=True,
            historical_adaptive_selection_risk='high',production_qualified=False,increased_betting_qualified=False,goal_complete=False))
        if source_bundle()!=before:raise ValueError('685 authorized source changed during actual')
        if cash.cache_source.database_state(meta['database']['path'])!=native_receipt['database_after']:raise ValueError('native database stat changed')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='risk_halfpct_cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,actual_fit_calls_attempted=0,actual_fit_calls_completed=0,
            cash_accounts_started=started,new_cash_accounts=completed,native_source_queries=ref.NATIVE_QUERIES,
            old_refits=0,old_cash_replays=0,new_labels=0,new_scores=0,downloads=0,bootstrap=0,
            fixture=False,python=sys.executable,auto_retry=False))
    artifacts={k:ref.file_binding(out/name) for k,name in dict(account_summaries='account_summaries.csv.gz',
        annual_slices='annual_slices.csv.gz',family_year_including_zero='family_year_including_zero.csv.gz',
        curve_data='equity_and_drawdown.csv',diagnostics='diagnostics.json',comparison='comparison.json',
        risk_budget_sensitivity='risk_budget_sensitivity.csv.gz',risk_utilization_comparison='risk_utilization_comparison.csv.gz',
        parameter_effectiveness_receipt='parameter_effectiveness_receipt.json',source_read_receipt='source_read_receipt.json',
        budget_and_execution_disclosure='budget_and_execution_disclosure.json').items()}
    ref.write_json(out/'manifest.json',dict(schema='stage685_single_risk_halfpct_v1',status=status,mode='actual',protocol=pb,
        authorization=ab,source_bundle=before,input_bindings=inputs,signals=inputs['signals'],baseline_manifest=inputs['baseline_manifest'],
        baseline_accounts=baseline['accounts'],accounts=accounts,terminal=ref.file_binding(out/'actual_terminal.json'),
        actual_fit_calls_attempted=0,actual_fit_calls_completed=0,new_cash_accounts=completed,native_source_queries=0,
        old_refits=0,old_cash_replays=0,new_labels=0,new_scores=0,downloads=0,bootstrap=0,source_snapshot_end=END,
        strict_PIT=False,production_qualified=False,increased_betting_qualified=False,no_automatic_promotion=True,goal_complete=False,**artifacts))
    return dict(status=status,output=str(out),new_fit=0,new_cash=completed)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',required=True);p.add_argument('--protocol-sha256',required=True)
    p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',required=True)
    print(json.dumps(execute(p.parse_args())),flush=True)

if __name__=='__main__':main()
