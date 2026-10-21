"""Stage131: eight fresh main-scope contract-choice cash accounts.

Only main A/B choices enter the local anchor/capacity adapter. Import and new
synthetic fixtures consume no native source, models, actual cash or downloads.
Actual execution requires exact root source, protocol, input, fresh-output and
authorization-file hashes. Failure is retained and never automatically retried.
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
PROTOCOL_SHA='bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0'
DEPENDENCIES={
    'stage070_narrow_policy_cash.py':'5ed1461fb137854f5a6d7c20d1f3ea25306cd3fc9b8b1646fbc767e786387ecb',
    'stage070_policy_kernel.py':'ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe',
    'stage042_cross_session_experiment.py':'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d',
    'stage054_maturity_cash_compare.py':'f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd',
    'stage124_long_history_cash.py':'cd7d4da128a1995ae618c1a0232ff8ef0e8fb1b7f56f96d9c65134b762600023',
}
# 124 is used only for already accepted pure diagnostics/binding helpers.
def load(name,identity):
    path=TOOLS/name
    spec=importlib.util.spec_from_file_location(identity,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

for name,expected in DEPENDENCIES.items():
    if hashlib.sha256((TOOLS/name).read_bytes()).hexdigest()!=expected:
        raise ValueError('accepted pure dependency changed '+name)
report_helpers=load('stage124_long_history_cash.py','stage131_pure124')
kernel=load('stage131_contract_choice_kernel.py','stage131_local_adapter')
ref=kernel.ref
helpers=report_helpers.helpers
ARMS=('A','B');WINDOWS=('primary_2020','cold_2023');COSTS=('base','stress')
INPUT_ROLES=('market_protocol','dataset_manifest','fit_manifest','actions','mothers','choices_main','held_diagnostic')
# Exact minimal roles; no unused COMMON array or child score is loaded.
EMPTY_COLUMNS=dict(helpers.EMPTY_COLUMNS,
    capacity_audit=['account_id','root_id','fill_sequence','epoch','fill_date','capacity_reference_date',
        'capacity_reference_volume','capacity_cap_qty','prior_same_epoch_day_gross_qty','fill_qty',
        'cumulative_same_epoch_day_gross_qty','capacity_state','side','reason','lot'],
    entry_execution_unknown=['budget_id','event_id','mother_event_id','reference_epoch','anchor_epoch','date','state'])


def text(value):
    return '' if pd.isna(value) else str(value)


def same_binding(actual,expected,role):
    report_helpers.same_binding(actual,expected,role)


def source_bundle():
    names=list(DEPENDENCIES)+['stage131_contract_choice_cash.py','stage131_contract_choice_kernel.py',
                             'test_stage131_contract_choice_cash.py']
    return sorted([ref.file_binding(TOOLS/name) for name in names],key=lambda b:b['path'])


def make_signals(actions,mothers,choices,arm,market,dates,economics):
    if arm not in ARMS or set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'}:
        raise ValueError('only main fixed NARROW A/B choices may enter cash')
    picked=choices.loc[choices.arm.eq(arm)].copy()
    if picked.event_id.duplicated().any() or not picked.selected.isin([0,1]).all():
        raise ValueError('unique complete parent choices and binary selected required')
    parents=mothers.set_index('event_id',verify_integrity=True)
    child=actions.set_index('action_id',verify_integrity=True)
    lookup={d:k for k,d in enumerate(dates)}
    rows=[]
    for c in picked.to_dict('records'):
        parent_id=c['event_id']
        if parent_id not in parents.index:raise ValueError('choice parent absent')
        p=parents.loc[parent_id]
        for name in ('product_id','u_date','reference_epoch'):
            if text(c.get(name))!=text(p[name]):raise ValueError('original parent identity changed '+name)
        anchor=text(p.reference_epoch)
        if text(c.get('anchor_epoch'))!=anchor:raise ValueError('choice anchor differs from immutable u canonical')
        if not int(c['selected']):continue
        a_id=text(c['chosen_action_id'])
        if a_id not in child.index:raise ValueError('selected child absent')
        a=child.loc[a_id]
        epoch=text(a['reference_epoch'])
        if (text(a['mother_event_id'])!=parent_id or text(a['product_id'])!=text(p.product_id)
                or text(a['u_date'])!=text(p.u_date) or text(c['chosen_epoch'])!=epoch
                or not anchor or text(a['anchor_epoch'])!=anchor):
            raise ValueError('selected action identity/product/anchor differs')
        if arm=='A' and epoch!=anchor:raise ValueError('A may only choose canonical')
        if int(a['u_action_eligible'])!=1 or not ref.positive(c['score']):
            raise ValueError('cash choice must be prospective eligible and positive-scored')
        sequence_name='chosen_action_sequence_index' if 'chosen_action_sequence_index' in c else 'chosen_sequence_index'
        if int(c[sequence_name])!=int(a['action_sequence_index']):raise ValueError('selected child sequence differs')
        u=lookup[text(p.u_date)]
        if 'u_index' in a and int(a['u_index'])!=u:raise ValueError('child native index differs')
        bar=market.bar(epoch,u);ind=market.indicator(epoch,u);e=economics.get(epoch,{})
        limits=kernel.capacity_at(market,epoch,u,e.get('round_lot'))
        if (bar is None or ind['run_length']<20 or not ref.positive(ind['N'])
                or not ref.finite(ind['low20']) or not ref.qualified_economics(e)
                or limits is None or limits[1]<int(e['round_lot'])):
            raise ValueError('selected u action failed independently recomputed eligibility')
        if int(a['entry_capacity_qty'])!=limits[1]:raise ValueError('dataset u half-cap differs from native')
        for name,value in (('N_u',ind['N']),('low20_u',ind['low20']),('u_close',bar['close'])):
            if name in a and ref.finite(a[name]) and not np.isclose(float(a[name]),value,rtol=1e-12,atol=1e-12):
                raise ValueError('dataset own-epoch causal value differs '+name)
        rows.append(dict(event_id=a_id,mother_event_id=parent_id,action_sequence_index=int(a['action_sequence_index']),
            product_id=text(p.product_id),family_id=ref.family(text(p.product_id)),u_date=text(p.u_date),u_index=u,D_index=u+1,
            reference_epoch=epoch,anchor_epoch=anchor,label_history_ready20=1,N_u=ind['N'],low20_u=ind['low20'],
            u_close=bar['close'],history_run=ind['run_length'],lifecycle_index=ref.lifecycle_index(e,epoch,dates),
            entry_capacity_qty=limits[1],u_gross_capacity_qty=limits[0],potential=1,score=float(c['score']),
            arm=arm,policy='NARROW',cutoff=c['cutoff']))
    columns=['event_id','mother_event_id','action_sequence_index','product_id','family_id','u_date','u_index','D_index',
             'reference_epoch','anchor_epoch','label_history_ready20','N_u','low20_u','u_close','history_run',
             'lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score','arm','policy','cutoff']
    result=pd.DataFrame(rows,columns=columns)
    if result.duplicated(['family_id','u_date']).any():raise ValueError('more than one selected family-u winner')
    return result


def organize(signals,mothers,dates):
    lookup={d:k for k,d in enumerate(dates)}
    references={lookup[text(d)]:dict(zip(g.product_id,g.reference_epoch.fillna('')))
                for d,g in mothers.groupby('u_date',sort=True)}
    potential={int(k):g.to_dict('records') for k,g in signals.groupby('u_index',sort=True)}
    return potential,references


def continuation_gate(points,held,any_stale,*,wealth_positive,execution_unknown=False):
    groups=held.get('groups',{})
    if not {'holdout_0','holdout_1'}.issubset(groups):raise ValueError('both held diagnostics required')
    held_only=dict(held,groups={g:groups[g] for g in ('holdout_0','holdout_1')})
    result=report_helpers.continuation_gate(points,held_only,any_stale,wealth_positive=wealth_positive)
    result['B_own_returns_positive_in_all_four']=result.pop('LONG_HISTORY_own_returns_positive_in_all_four')
    result['execution_unknown']=bool(execution_unknown)
    if execution_unknown:
        result['financial_unknown']=True
        result['nominal_pass']=False
        if result['status']=='supported_research_model_only':result['status']='unknown_execution_capacity_or_entry'
    return result


def authorize(args):
    output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('fresh output required; no automatic retry '+str(output))
    pb=ref.file_binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or pb['sha256']!=PROTOCOL_SHA:raise ValueError('exact Stage128 protocol SHA required')
    protocol=json.loads(ref.read_bound(pb))
    if protocol.get('schema')!='stage128_contract_choice_protocol_v1' or protocol.get('stage')!=128 or protocol.get('line_id')!=LINE.name:
        raise ValueError('Stage128 protocol identity differs')
    ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(ref.read_bound(ab))
    required=dict(schema='stage128_exact_root_authorization_v1',authorized_by='root',stage='cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root cash authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('authorized source/tests bundle differs')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!=set(INPUT_ROLES):raise ValueError('exact seven market/dataset/fit/actions/mothers/main/held roles required')
    same_binding(inputs['market_protocol'],protocol['inputs']['market_protocol'],'market protocol')
    cash=protocol['cash']
    if (cash['initial_equity'],cash['single_family_risk'],cash['total_planned_risk'],cash['buffered_margin_cap'],cash['margin_buffer'])!=(ref.INITIAL,ref.SINGLE_RISK,ref.TOTAL_RISK,ref.MARGIN_CAP,ref.MARGIN_BUFFER):
        raise ValueError('accepted070 cash constants differ')
    if cash['accounts_max']!=8 or cash['native_SQL_max']!=1:raise ValueError('finite cash/native budget differs')
    return protocol,pb,auth,ab


def validate_manifests(dataset,fit,inputs):
    for m,schema in ((dataset,'stage129_contract_choice_dataset_v1'),(fit,'stage130_contract_choice_fit_v1')):
        if (m.get('schema')!=schema or m.get('status')!='completed' or m.get('mode')!='actual'
                or m.get('protocol',{}).get('sha256')!=PROTOCOL_SHA):raise ValueError('completed bound129/130 manifest required')
    for role in ('actions','mothers'):same_binding(dataset[role],inputs[role],'dataset '+role)
    for role in ('choices_main','held_diagnostic'):same_binding(fit[role],inputs[role],'fit '+role)
    same_binding(fit['input_bindings']['dataset_manifest'],inputs['dataset_manifest'],'fit dataset manifest')
    if fit.get('actual_fit_calls_completed')!=6 or fit.get('native_source_queries')!=0 or fit.get('cash_eligible') is not True:
        raise ValueError('130 must complete exactly6 shared fits/zero native and authorize cash')
    for m,expected_native,expected_fit in ((dataset,1,0),(fit,0,6)):
        terminal=json.loads(ref.read_bound(m['terminal']))
        if terminal.get('status')!='completed' or terminal.get('exit_code')!=0 or terminal.get('native_source_queries')!=expected_native:
            raise ValueError('dataset/fit actual terminal incomplete or native budget differs')
        if expected_fit and terminal.get('actual_fit_calls_completed')!=expected_fit:raise ValueError('fit terminal6 incomplete')
        if terminal.get('new_cash_accounts',terminal.get('cash_replays',0))!=0:raise ValueError('upstream phase unexpectedly ran cash')


def comparisons(summaries,daily,indices):
    points=[];distributions={}
    for window in WINDOWS:
        for cost in COSTS:
            a,b=('B',window,cost),('A',window,cost)
            point=helpers.compare_points(summaries[a],summaries[b])
            stats,dist=report_helpers.paired_statistics(daily[a],daily[b],indices[window])
            points.append(dict(window=window,cost=cost,contrast='B_minus_A',
                active_total_return_pct=summaries[a]['total_return_pct'],reference_total_return_pct=summaries[b]['total_return_pct'],**point,**stats))
            distributions[window+'_'+cost+'_B_minus_A']=dist
    return points,distributions


def source_cases(book,signals,market,dates,economics,arm,selections):
    roots={r['root_id']:r for r in book['closed_episodes']+book['open_episodes']}
    by_event=signals.set_index('event_id',verify_integrity=True)
    for fill in book['fills']:
        root=roots[fill['root_id']]
        kind=('capacity_unknown' if fill['capacity_state']=='execution_capacity_unknown' else
              'noncanonical_entry' if fill['side']=='BUY' and root['epoch']!=root['anchor_epoch'] else
              fill['reason'] if fill['side']=='SELL' else None)
        if kind is None or (arm,kind) in selections:continue
        signal=by_event.loc[fill['event_id']]
        k=int(np.searchsorted(dates,fill['date']));u=int(signal.u_index)
        begin=max(0,u-int(signal.history_run)+1);epoch=root['epoch'];bars=[]
        for j in range(begin,k+1):
            bar=market.bar(epoch,j)
            bars.append(dict(date=dates[j],native_index=j,bar=bar))
        selections[(arm,kind)]=dict(arm=arm,kind=kind,fill=fill,root=root,signal=signal.to_dict(),
            native_bars=bars,economics=economics[epoch],selection='first_case_in_frozen_account_order_not_PnL')


def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings']
    dataset=json.loads(ref.read_bound(inputs['dataset_manifest']));fit=json.loads(ref.read_bound(inputs['fit_manifest']))
    validate_manifests(dataset,fit,inputs)
    needed={'action_id','event_id','action_sequence_index','sequence_index','mother_event_id','mother_sequence_index',
        'product_id','family_id','u_date','u_index','actual_epoch','reference_epoch','anchor_epoch','u_action_eligible',
        'entry_capacity_qty','label_history_ready20','N_u','u_N20','low20_u','u_low20','u_close','history_run','lifecycle_index'}
    actions=pd.read_csv(io.BytesIO(ref.read_bound(inputs['actions'])),compression='gzip',usecols=lambda c:c in needed,low_memory=False)
    mothers=helpers.read_table(inputs['mothers']);choices=helpers.read_table(inputs['choices_main'])
    held=json.loads(ref.read_bound(inputs['held_diagnostic']))
    if len(mothers)!=399252 or mothers.product_id.nunique()!=98 or mothers.event_id.duplicated().any():raise ValueError('full unchanged399252 mother/98 products required')
    expected=set(mothers.loc[mothers.u_date.ge('2020-01-01'),'event_id'])
    if len(expected)!=161014 or len(choices)!=322028 or set(choices.arm)!=set(ARMS) or set(choices.scope)!={'main'}:
        raise ValueError('full161014 forward parent identities per main arm required')
    for arm in ARMS:
        sub=choices.loc[choices.arm.eq(arm)]
        if sub.event_id.duplicated().any() or set(sub.event_id)!=expected:raise ValueError('main arm lost parent identities')
    indices={w:np.load(io.BytesIO(ref.read_bound(protocol['bootstrap_indices'][w])),allow_pickle=False) for w in WINDOWS}
    if ref.NATIVE_QUERIES:raise ValueError('native already consumed')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();before=source_bundle()
    status,error,started,completed='failed',None,0,0
    ref.write_json(out/'actual_started.json',dict(status='started',stage='cash',started_at=began,source_bundle=before,protocol=pb,authorization=ab,fixture=False))
    try:
        panel,market,dates,economics,_,receipt,market_protocol=kernel.original.load_market_bridge(auth)
        ref.write_json(out/'source_read_receipt.json',receipt)
        if set(panel.event_id)!=set(mothers.event_id):raise ValueError('market bridge mother identities differ')
        signals={arm:make_signals(actions,mothers,choices,arm,market,dates,economics) for arm in ARMS}
        summaries={};daily={};reports={};family_tables=[];account_capacity=[];selections={};all_budgets=[]
        families=sorted(panel.product_id.map(ref.family).unique())
        for arm in ARMS:
            sig=signals[arm];prepared=organize(sig,mothers,dates)
            for window,bounds in protocol['cash']['windows'].items():
                start,end=(int(np.searchsorted(dates,v)) for v in bounds)
                if end>=len(dates) or dates[end]!=bounds[1] or indices[window].shape!=(2000,end-start+1):raise ValueError('fixed source calendar/bootstrap width differs')
                for cost in COSTS:
                    name=f'NARROW_{arm}_{window}_{cost}';started+=1
                    book=kernel.run_cash_account(sig,market,dates,economics,cost,name,start,end,prepared=prepared)
                    completed+=1;folder=out/name;folder.mkdir()
                    for file,key in [('fills','fills'),('reservations','budgets'),('daily','daily'),('positions','position_days'),
                                     ('closed','closed_episodes'),('open','open_episodes'),('capacity_audit','capacity_audit'),
                                     ('entry_execution_unknown','entry_execution_unknown')]:
                        ref.write_table(folder/(file+'.csv.gz'),book[key],EMPTY_COLUMNS.get(key,[]))
                    ref.write_table(folder/'rejections.csv.gz',[r for r in book['budgets'] if r.get('D_qty',0)==0],helpers.EMPTY_COLUMNS['budgets'])
                    summary,report,fy=helpers.cash_report(book,families,ref.INITIAL)
                    capacity=dict(account=name,arm=arm,window=window,cost=cost,execution_unknown=book['execution_unknown'],
                        unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
                        capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
                    summary.update(capacity);report.update(capacity);account_capacity.append(capacity)
                    key=(arm,window,cost);summaries[key]=summary;daily[key]=pd.DataFrame(book['daily']);reports[name]=report
                    fy=report_helpers.add_family_costs(fy,book);family_tables.append(fy.assign(arm=arm,window=window,cost=cost))
                    all_budgets.extend(book['budgets']);source_cases(book,sig,market,dates,economics,arm,selections)
                    ref.write_json(folder/'summary.json',kernel.original.safe(summary))
                    print(json.dumps(dict(phase='account_complete',account=name,completed=completed,elapsed_seconds=time.monotonic()-clock)),flush=True)
        if started!=8 or completed!=8 or ref.NATIVE_QUERIES!=1:raise AssertionError('8 fresh accounts/one shared source read required')
        points,distributions=comparisons(summaries,daily,indices)
        ref.write_table(out/'comparisons.csv.gz',points,[])
        ref.write_table(out/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        fy=pd.concat(family_tables,ignore_index=True);ref.write_table(out/'family_year_including_zero.csv.gz',fy,[])
        ref.write_table(out/'family_total_including_zero.csv.gz',fy.groupby(['arm','window','cost','family_id'])[
            ['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index(),[])
        ref.write_table(out/'annual_slices.csv.gz',[dict(account=a,**r) for a,report in reports.items() for r in report['annual_slices']],[])
        ref.write_table(out/'account_summaries.csv.gz',[dict(v,arm=k[0],window=k[1],cost=k[2]) for k,v in summaries.items()],[])
        ref.write_table(out/'capacity_summary.csv.gz',account_capacity,[])
        ref.write_json(out/'diagnostics.json',kernel.original.safe(reports))
        ref.write_json(out/'signal_identification.json',dict(main_parent_rows_per_arm=161014,full_mother_rows=399252,
            selected_actions={arm:len(signals[arm]) for arm in ARMS},held_binding=inputs['held_diagnostic'],held_groups=held['groups'],
            full_choices_binding=inputs['choices_main'],future_label_states_not_used_for_cash_eligibility=True))
        import gzip
        with gzip.GzipFile(filename=str(out/'finite_native_cases.json.gz'),mode='wb',mtime=0) as f:
            f.write(json.dumps(kernel.original.safe(list(selections.values())),ensure_ascii=False).encode())
        stale=any(r['stale_days']>0 for r in reports.values());execution_unknown=any(c['execution_unknown'] for c in account_capacity)
        wealth_positive=all(np.isfinite(f.equity).all() and f.equity.gt(0).all() and not f.ever_insolvent.any() for f in daily.values())
        gate=continuation_gate(points,held,stale,wealth_positive=wealth_positive,execution_unknown=execution_unknown)
        ref.write_json(out/'continuation_gate.json',kernel.original.safe(dict(gate,any_historical_stale=stale)))
        ref.write_json(out/'budget_and_tick_disclosure.json',dict(policy='NARROW',budget_rules='original070 u joint fractional reserve/D reduce only, then fixed u roundtrip half cap; no redistribution',
            risk_unit='0.25*N*M+roundtrip_fee+two_adverse_slippages',capacity='all BUY/SELL gross per account/epoch/day audited against exact native D-1 1% volume; ideal SELL retained',
            anchor='immutable entry canonical with persistent close request; own held lifecycle/stop/20low',reservation_records=len(all_budgets),
            A_curve_equals_old070_required=False,continuous_boundary_not_necessarily_tick_order=True,no_gap_loss_cap=True,
            no_actual_orderbook_execution_proof=True,bootstrap_indices=protocol['bootstrap_indices'],bootstrap_indices_regenerated=False,
            static_vendor_economic_snapshots_not_historical_broker_truth=True))
        ref.assert_db_binding(market_protocol['database'])
        if source_bundle()!=before:raise ValueError('source changed during131 actual')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,native_source_queries=ref.NATIVE_QUERIES,
            cash_accounts_started=started,new_cash_accounts=completed,actual_model_fit_calls=0,downloads=0,new_labels=0,whole_database_hashes=0,
            old_baseline_replays=0,fixture=False,python=sys.executable))
    artifacts=[dict(ref.file_binding(p),logical_name=str(p.relative_to(out)),role='qualification_evidence' if p.name=='finite_native_cases.json.gz' else 'decision_asset',
        feature_schema='stage131_contract_choice_cash_v1',raw_ohlc=p.name=='finite_native_cases.json.gz',reproducibility_required=p.name!='finite_native_cases.json.gz')
        for p in sorted(out.rglob('*')) if p.is_file()]
    ref.write_json(out/'manifest.json',dict(schema='stage131_contract_choice_cash_v1',status=status,mode='actual',protocol=pb,authorization=ab,
        input_bindings=inputs,source_bundle=before,bootstrap_indices=protocol['bootstrap_indices'],terminal=ref.file_binding(out/'actual_terminal.json'),
        artifacts=artifacts,new_cash_accounts=completed,native_source_queries=ref.NATIVE_QUERIES,actual_model_fit_calls=0,new_labels=0,
        old_baseline_replays=0,goal_complete=False,production_qualified=False))
    return dict(status=status,output=str(out),native_source_queries=ref.NATIVE_QUERIES,new_cash_accounts=completed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
