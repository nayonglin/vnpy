"""Frozen264 research-only cash wrapper. Import performs no data or kernel I/O.

Only root's exact authorization may launch four candidate books after 265/267.
No model, action table, score table, selector, SQL or historical CLI is invoked.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42'
IDENTITY=['event_id','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch']
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def bound_bytes(b):
    p=Path(b['path']);raw=p.read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
        raise ValueError('bound input changed '+str(p))
    return raw


def read_json(b):return json.loads(bound_bytes(b))


def write_json(path,value):
    with Path(path).open('w') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def source_bundle():
    return [binding(TOOLS/n) for n in ('stage266_spot_policy_cash.py','test_stage266_spot_policy_cash.py')]


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def check_research_gates(coverage,review,bundle):
    if coverage.get('total_signals')!=4365 or coverage.get('core_blockers')!=0 or coverage.get('cancel_count',0)<=0:
        raise ValueError('265 completed complete coverage and nonzero cancellation required; otherwise zero cash')
    if (review.get('schema')!='stage267_spot_policy_source_review_v1' or review.get('completed') is not True
            or review.get('core_blockers')!=0 or review.get('protocol_sha256')!=PROTOCOL_SHA):
        raise ValueError('267 independent new-source review required before data/cash')
    if any(not any(same(b,r) for r in review.get('source_bindings',[])) for b in bundle):
        raise ValueError('267 must bind exact266 source and fixture')


def apply_policy(signals,sidecar,expected_count=4365):
    if len(signals)!=expected_count or len(sidecar)!=expected_count or signals.event_id.duplicated().any():
        raise ValueError('complete original unique signal rows required')
    if pd.to_numeric(sidecar.signal_row,errors='raise').tolist()!=list(range(expected_count)):
        raise ValueError('sidecar original signal order differs')
    for name in IDENTITY:
        a,b=signals[name],sidecar[name]
        if name=='u_index':
            equal=pd.to_numeric(a,errors='raise').tolist()==pd.to_numeric(b,errors='raise').tolist()
        else:equal=a.astype(str).tolist()==b.astype(str).tolist()
        if not equal:raise ValueError('sidecar signal identity differs '+name)
    available=pd.to_numeric(sidecar.available,errors='raise')
    keep=pd.to_numeric(sidecar.keep_entry,errors='raise')
    if not available.isin([0,1]).all() or not keep.isin([0,1]).all():raise ValueError('binary policy flags required')
    if ((available==0)&(keep!=1)).any():raise ValueError('unavailable S must inherit original entry')
    if sidecar.action.tolist()!=['retain' if v else 'cancel' for v in keep]:raise ValueError('policy action contradicts mask')
    if sidecar.reason.astype(str).eq('').any():raise ValueError('every policy row needs reason')
    return signals.loc[keep.to_numpy()==1].copy().reset_index(drop=True)


def account_specs():
    return [dict(window=w,cost=c,account_id=f'NARROW_SPOT264_{w}_{c}') for w in WINDOWS for c in COSTS]


def run_four(output,run_account,export_account,*,before=None,finalize=None,metadata=None):
    """Persist real kernel starts/completions, including partial financial failures."""
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    started=completed=0;records=[];status='failed';error=None
    meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=266,started_at=began,**meta))
    def progress(account=None):
        write_json(out/'cash_progress.json',dict(cash_accounts_started=started,cash_accounts_completed=completed,
            max_new_candidate_cash=4,current_account=account,old_control_replays=0,new_fit=0))
    progress()
    try:
        if before is not None:before(out)
        for spec in account_specs():
            if started>=4:raise ValueError('fixed four-account budget exhausted')
            started+=1;progress(spec['account_id'])
            book=run_account(spec)
            completed+=1;progress(spec['account_id'])
            records.append(export_account(spec,book))
        if (started,completed)!=(4,4):raise ValueError('exact four candidates required')
        if finalize is not None:finalize(out,records)
        status='completed'
        return records
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,cash_accounts_started=started,cash_accounts_completed=completed,
            max_new_candidate_cash=4,new_fit=0,old_control_replays=0,SQL=0,auto_retry=False,
            goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts=[binding(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json']
        write_json(out/'manifest.json',dict(schema='stage266_spot_policy_cash_manifest_v1',status=status,
            accounts=records,terminal=binding(out/'actual_terminal.json'),artifacts=artifacts,**meta,**{
                'new_fit':0,'new_cash_accounts':completed,'cash_accounts_started':started,'old_control_replays':0,
                'max_new_candidate_cash':4,'goal_complete':False,'production_qualified':False}))


def load_runtime(refs):
    # Verify only the 16 small already accepted source bindings. Native restoration
    # below retains the existing132 exact cache reader; no new source SQL is used.
    for b in refs['source_bundle']:
        if not same(binding(b['path']),b):raise ValueError('accepted cash source changed '+b['path'])
    spec=importlib.util.spec_from_file_location('stage266_accepted148',TOOLS/'stage148_fx_cash.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def fixed_table(b,**kwargs):
    # Frozen large mother binding is inherited from158/263; no second big hash.
    if Path(b['path']).stat().st_size!=b['bytes']:raise ValueError('frozen table size changed')
    return pd.read_csv(b['path'],dtype=str,keep_default_na=False,float_precision='round_trip',**kwargs)


def authorize(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; previous attempt retained')
    if LINE/'outputs/stage266_spot_policy_cash' not in out.parents:raise ValueError('Stage266 output root required')
    pb=binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact264 required')
    protocol=read_json(pb)
    if protocol.get('schema')!='stage264_fixed_literal_spot_participation_protocol_v1':raise ValueError('264 schema differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root authorization hash differs')
    auth=read_json(ab);bundle=source_bundle()
    expected=dict(schema='stage266_exact_root_authorization_v1',authorized_by='root',protocol_sha256=PROTOCOL_SHA,
        output=str(out),max_new_candidate_cash=4,max_new_fit=0)
    if any(auth.get(k)!=v for k,v in expected.items()):raise ValueError('single exact root research authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(bundle,key=lambda b:b['path']):
        raise ValueError('authorized new source/fixture differs')
    return out,protocol,pb,auth,ab,bundle


def execute(args):
    out,p,pb,auth,ab,bundle=authorize(args);state={}
    metadata=dict(protocol=pb,authorization=ab,source_bundle=bundle,coverage_manifest=auth['coverage_manifest'],
        source_review_receipt=auth['source_review_receipt'],research_identity_gate_only=True,fixture=False)

    def prepare(folder):
        cm=read_json(auth['coverage_manifest']);review=read_json(auth['source_review_receipt'])
        if cm.get('schema')!='stage265_spot_policy_coverage_manifest_v1' or cm.get('status')!='completed' or cm.get('protocol_sha256')!=PROTOCOL_SHA:
            raise ValueError('completed265 exact264 coverage manifest required')
        coverage=read_json(cm['artifacts']['coverage_summary'])
        check_research_gates(coverage,review,bundle)
        for role in ('complete_signals','complete_choices'):
            if not same(cm['inputs'][role],p[role]):raise ValueError('265 original input differs '+role)
        refs=read_json(p['cash_interface_refs']);r=load_runtime(refs)
        signals=pd.read_csv(io.BytesIO(bound_bytes(p['complete_signals'])),compression='gzip',keep_default_na=False,float_precision='round_trip')
        side=pd.read_csv(io.BytesIO(bound_bytes(cm['artifacts']['signal_map'])),compression='gzip',dtype=str,keep_default_na=False)
        filtered=apply_policy(signals,side)
        if len(signals)-len(filtered)!=coverage['cancel_count']:raise ValueError('coverage cancellation count differs')
        mothers=fixed_table(p['complete_mothers'],usecols=r.IDENTITY)
        r.numeric(mothers,['sequence_index','u_index'])
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:
            raise ValueError('full immutable399252 mother/canonical domain required')
        parent=mothers.set_index('event_id')
        for row in signals.to_dict('records'):
            a=parent.loc[row['mother_event_id']]
            if (row['product_id']!=a.product_id or row['u_date']!=a.u_date or row['u_index']!=a.u_index
                    or row['anchor_epoch']!=a.reference_epoch):raise ValueError('original signal/mother identity differs')
        fixed=refs['input_bindings_inherited_from_accepted157']
        store,receipt,cache_meta=r.cache_source.restore_native_cache(fixed['native_cache_manifest'])
        if receipt['native_source_queries']!=0 or r.ref.NATIVE_QUERIES!=0:raise ValueError('zero SQL required')
        market,dates=r.CachedMarket(store),store.calendar
        economics=read_json(refs['market_dependencies']['economic_projection'])['instruments']
        if set(economics)!=set(store.series):raise ValueError('same cached epoch economics required')
        for row in signals.to_dict('records'):
            if dates[int(row['u_index'])]!=row['u_date'] or row['D_index']!=row['u_index']+1:
                raise ValueError('original u/D calendar differs')
        bounds_by_window={}
        for w in WINDOWS:
            start,end=(int(np.searchsorted(dates,v)) for v in p['windows'][w])
            if end>=len(dates) or dates[end]!=p['windows'][w][1]:raise ValueError('unchanged fixed window/source calendar required')
            bounds_by_window[w]=(start,end)
        state.update(r=r,signals=filtered,mothers=mothers,market=market,dates=dates,economics=economics,
            bounds_by_window=bounds_by_window,cache_meta=cache_meta,native_receipt=receipt,
            prepared=r.author.organize(filtered,mothers,dates),families=sorted(mothers.family_id.unique()),
            summaries={},reports={},families_tables=[])
        r.ref.write_table(folder/'signals_SPOT264.csv.gz',filtered,[])
        write_json(folder/'source_read_receipt.json',dict(receipt,original_signals=4365,
            retained_signals=len(filtered),cancelled_signals=coverage['cancel_count'],full_mother_rows=399252,
            original_signal_binding=p['complete_signals'],original_mother_binding=p['complete_mothers'],
            sidecar_binding=cm['artifacts']['signal_map'],new_fit=0,new_labels=0,old_control_replays=0,
            selectors_called=0,actions_scores_models_read=0,large_mother_hash_recomputed=False))
        write_json(folder/'control_references.json',p['control_accounts'])

    def run(spec):
        start,end=state['bounds_by_window'][spec['window']]
        return state['r'].kernel.run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],start,end,prepared=state['prepared'])

    def export(spec,book):
        r=state['r'];name=spec['account_id'];folder=out/name
        ledgers=r.write_ledgers(folder,book)
        summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_tick_fills=0
        for f in book['fills']:
            tick=state['economics'][f['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
            else:unknown_tick_fills+=1
        summary.update(spec,arm='SPOT264',source_arm='VOLUNTARY_RESELECT',role='candidate',
            any_historical_stale=report['stale_days']>0,execution_unknown=book['execution_unknown'],
            capacity_unknown_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_tick_fills,
            transaction_count_definition='closed_trades=closed roots; fills=all BUY/SELL fills; not interchangeable',
            slippage_already_in_fill_price=True)
        state['summaries'][(spec['window'],spec['cost'])]=summary;state['reports'][name]=report
        state['families_tables'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec,arm='SPOT264'))
        groups,tails=r.extra_reports(book)
        write_json(folder/'summary.json',r.kernel.original.safe(summary))
        write_json(folder/'diagnostics.json',r.kernel.original.safe(report))
        write_json(folder/'largest_wins_losses.json',r.kernel.original.safe(tails))
        r.ref.write_table(folder/'sector_variant_attribution.csv.gz',groups,[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers)

    def finalize(folder,records):
        r=state['r'];refs=read_json(p['cash_interface_refs'])
        original=read_json(refs['small_identity_bindings']['157'])
        control_reports=read_json(original['diagnostics'])
        points=[];all_summaries=list(state['summaries'].values());annual=[]
        for spec,control in zip(account_specs(),p['control_accounts']):
            key=(spec['window'],spec['cost'])
            if (control['window'],control['cost'])!=key:raise ValueError('exact four controls/window/cost order required')
            old=read_json(control['summary']);active=state['summaries'][key]
            all_summaries.append(dict(old,role='control_reused',source_only=True,replayed=False,
                account_id=control['account_id'],window=key[0],cost=key[1]))
            points.append(dict(spec,control_account_id=control['account_id'],
                ending_equity_difference=active['ending_equity']-old['ending_equity'],
                **r.helpers.compare_points(active,old)))
            for name,role,report in ((spec['account_id'],'candidate',state['reports'][spec['account_id']]),
                    (control['account_id'],'control_reused',control_reports[control['account_id']])):
                annual.extend(dict(account_id=name,role=role,window=key[0],cost=key[1],**a) for a in report['annual_slices'])
        stress=[x for x in points if x['cost']=='stress']
        effect=all(x['ending_equity_difference']>0 for x in stress)
        both=effect and all(x['drawdown_percentage_point_difference'] is not None and x['drawdown_percentage_point_difference']>0 for x in stress)
        r.ref.write_table(folder/'account_summaries.csv.gz',all_summaries,[])
        r.ref.write_table(folder/'comparisons.csv.gz',points,[])
        r.ref.write_table(folder/'annual_slices.csv.gz',annual,[])
        r.ref.write_table(folder/'family_year_including_zero.csv.gz',pd.concat(state['families_tables'],ignore_index=True),[])
        write_json(folder/'decision.json',dict(schema='stage266_fixed264_decision_v1',
            primary_falsification_pass=effect,both_stress_return_and_drawdown_improved=both,
            meaning='fixed conditional historical effect only; overlapping windows; not PIT/causal/future alpha',
            execution_unknown=any(x['execution_unknown'] for x in state['summaries'].values()),
            any_historical_stale=any(x['any_historical_stale'] for x in state['summaries'].values()),
            new_CI=0,new_fit=0,old_control_replays=0,goal_complete=False,production_qualified=False,increased_betting_qualified=False))
        if source_bundle()!=bundle or r.ref.NATIVE_QUERIES!=0:raise ValueError('source drift or SQL budget violation')
        if r.cache_source.database_state(state['cache_meta']['database']['path'])!=state['native_receipt']['database_after']:
            raise ValueError('cached native database stat changed during actual')

    return run_four(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())


if __name__=='__main__':main()
