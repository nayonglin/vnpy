"""Frozen596 four C cash books; unchanged157 OWN A reuse, import is data-pure."""
import argparse
import hashlib
import io
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='3985c8fa70fdcb31f3712dc1fff58ea8d449579a0b31eff17ca2110b18fa894f'
ARM='WINNER_ADDITION'
NEW_FILES=['stage597_winner_addition_cash.py','test_stage597_winner_addition_cash.py',
           'stage597_winner_addition_kernel.py','test_stage597_winner_addition_kernel.py']


def binding(path,data=None):
    p=Path(path).resolve();data=p.read_bytes() if data is None else data
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def read_bytes(bound):
    raw=Path(bound['path']).read_bytes()
    if binding(bound['path'],raw)!=bound:raise ValueError('bound input changed '+bound['path'])
    return raw

def read_json(bound):return json.loads(read_bytes(bound))
def read_table(bound,**kwargs):return pd.read_csv(io.BytesIO(read_bytes(bound)),compression='gzip',keep_default_na=False,float_precision='round_trip',**kwargs)
def write_json(path,obj):
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def source_bundle():return [binding(TOOLS/n) for n in NEW_FILES]


def metadata_frame(signals):
    if signals.event_id.duplicated().any() or set(signals.policy)!={'NARROW'} or set(signals.arm)!={'VOLUNTARY_RESELECT'}:raise ValueError('original157 signal identity differs')
    if not np.isfinite(signals[['u_close','N_u','low20_u']].to_numpy(float)).all():raise ValueError('fixed causal signal invalid')
    if not all(signals.D_index==signals.u_index+1):raise ValueError('original D index differs')
    expected=np.where(signals.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
    if not np.array_equal(signals.cutoff.to_numpy(),expected):raise ValueError('original per-u cutoff differs; no account constant-cutoff filter')


def fresh_overlap(old_buys,book):
    columns=['root_id','event_id','epoch','date','side','qty']
    fills=pd.DataFrame(book['fills'],columns=columns)
    new=fills.loc[fills.side.eq('BUY')&~fills.root_id.isin(book['add_root_ids']),['event_id','epoch','date','qty']]
    overlap=old_buys.merge(new,on=['event_id','epoch'],how='outer',suffixes=('_A','_C'),indicator=True,validate='one_to_one')
    overlap['participation']=overlap.pop('_merge').map({'left_only':'A_only','both':'common','right_only':'C_only'}).astype(str)
    add_events=set(fills.loc[fills.side.eq('BUY')&fills.root_id.isin(book['add_root_ids']),'event_id'])
    overlap['C_add_same_event']=overlap.event_id.isin(add_events)
    overlap['quantity_difference_C_minus_A']=overlap.qty_C.fillna(0)-overlap.qty_A.fillna(0)
    return overlap


def addition_summary(book):
    ids=set(book['add_root_ids']);audit=book['add_audit']
    if len(ids)!=len(book['add_root_ids']):raise ValueError('duplicate actual add root identity')
    fills=[r for r in book['fills'] if r['root_id'] in ids]
    buy=[r for r in fills if r['side']=='BUY']
    if {r['root_id'] for r in buy}!=ids:raise ValueError('actual add-root BUY identity differs')
    reasons=pd.Series([str(r.get('reason','')) for r in audit],dtype=str).value_counts().to_dict()
    return dict(actual_add_roots=len(ids),add_buy_qty=sum(r['qty'] for r in buy),
        add_fill_count=len(fills),add_fees=sum(r['fee'] for r in fills),add_slippage=sum(r['slippage'] for r in fills),
        add_candidate_audit_rows=len(audit),material_add_unknown=any(bool(r.get('unknown',False)) for r in audit),
        add_reason_counts={str(k):int(v) for k,v in reasons.items()},add_roots_not_independent_samples=True)


def run(protocol_path,output,check,ready_path,runner_test=None,kernel_test=None):
    raw=protocol_path.read_bytes();pb=binding(protocol_path,raw)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen596 protocol changed')
    protocol=json.loads(raw)
    if protocol['schema']!='stage596_frozen_winner_addition_cash_v1':raise ValueError('protocol schema differs')
    sources=source_bundle();output.mkdir(parents=True,exist_ok=False)
    if check:
        if runner_test is None or kernel_test is None:raise ValueError('truthful two fixture receipts required')
        receipts={}
        for role,path in [('runner',runner_test),('kernel',kernel_test)]:
            rb=binding(path);receipt=read_json(rb)
            if receipt.get('exit_code')!=0:raise ValueError('fixture receipt is not passed '+role)
            source_name='stage597_winner_addition_cash.py' if role=='runner' else 'stage597_winner_addition_kernel.py'
            fixture_name='test_'+source_name
            if receipt.get('source')!=binding(TOOLS/source_name) or receipt.get('fixture')!=binding(TOOLS/fixture_name):raise ValueError('fixture tested source changed '+role)
            receipts[role]=dict(binding=rb,result=receipt)
        ready=dict(source_ready=True,actual_started=False,protocol=pb,source_bundle=sources,
            fixture_receipts=receipts,fit=0,cash=0,SQL=0,GET=0,A_replay=0)
        write_json(output/'source_ready.json',ready);print(json.dumps(ready));return
    if ready_path is None:raise ValueError('exact source-ready required')
    ready=json.loads(ready_path.read_text())
    if ready['source_bundle']!=sources or ready['protocol']!=pb or not ready['source_ready']:raise ValueError('source-ready binding differs')
    for row in ready['fixture_receipts'].values():
        if read_json(row['binding'])!=row['result'] or row['result']['exit_code']!=0:raise ValueError('passed fixture receipt changed')
    import stage597_winner_addition_kernel as kernel
    import stage157_voluntary_cash as reuse
    began=time.monotonic();started=completed=0;accounts=[];status='failed';error=None
    write_json(output/'actual_started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),protocol=pb,source_bundle=sources,source_ready=binding(ready_path),max_new_cash=4))
    write_json(output/'actual_attempt.json',dict(attempt=1,fit=0,A_replay=0,max_new_cash=4))
    try:
        inputs=protocol['input_bindings'];manifest157=read_json(inputs['accepted157_manifest'])
        if manifest157['schema']!='stage157_voluntary_cash_v1' or manifest157['status'] not in ('completed','completed_with_metadata_continuation') or manifest157['new_cash_accounts']!=4:raise ValueError('accepted157 four OWN books required')
        if manifest157['signals']!=inputs['signals']:raise ValueError('unchanged157 signals required')
        signals=read_table(inputs['signals']);metadata_frame(signals)
        cols=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
        mothers=read_table(inputs['mothers'],dtype=str,usecols=cols)
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('full98/95 mother domain differs')
        if len(mothers.loc[mothers.u_date.between('2020-01-01','2026-10-16')])!=161014:raise ValueError('full forward parent domain differs')
        meta=read_json(inputs['native_cache_manifest'])
        if meta['file']!=inputs['native_cache']:raise ValueError('exact native cache binding required')
        store,native_receipt,_=reuse.cache_source.restore_native_cache(inputs['native_cache_manifest'])
        market,dates=reuse.CachedMarket(store),store.calendar
        market_protocol=read_json(inputs['market_protocol']);economics=read_json(market_protocol['economic_projection'])['instruments']
        read_json(inputs['execution_protocol'])
        if set(economics)!=set(store.series) or reuse.ref.NATIVE_QUERIES or native_receipt['native_source_queries']:raise ValueError('cached economics or zeroSQL differs')
        prepared=reuse.author.organize(signals,mothers,dates);families=sorted(mothers.family_id.unique())
        indices={w:np.load(io.BytesIO(read_bytes(b)),allow_pickle=False) for w,b in protocol['bootstrap_indices'].items()}
        diagnosticsA=read_json(inputs['A_diagnostics']);summary_table=read_table(inputs['A_summaries'])
        control={};dailyA={};metricsA=[];buysA={}
        old_accounts=protocol['old_A_own_accounts']
        if len(old_accounts)!=4 or {(a['window'],a['cost']) for a in old_accounts}!={(w,c) for w in ['primary_2020','cold_2023'] for c in ['base','stress']}:raise ValueError('exact four OWN sources required')
        for a in old_accounts:
            key=a['window'],a['cost'];own=next(x for x in manifest157['accounts'] if x['account_id']==a['account_id'])
            if a['summary']!=own['summary'] or a['daily']!=own['ledgers']['daily'] or a['fills']!=own['ledgers']['fills']:raise ValueError('A OWN ledger identity differs')
            control[key]=read_json(a['summary']);dailyA[key]=read_table(a['daily'])
            if a['account_id'] not in set(summary_table.account):raise ValueError('A OWN summary identity missing')
            fills=read_table(a['fills'],usecols=['event_id','epoch','date','side','qty'])
            buysA[key]=fills.loc[fills.side.eq('BUY')].drop(columns='side')
            metricsA.append(dict(control[key],arm='A_REUSED',window=a['window'],cost=a['cost'],source_only=True,replayed=False))
        write_json(output/'source_read_receipt.json',dict(native_receipt,signals=inputs['signals'],mothers=inputs['mothers'],economic_projection=market_protocol['economic_projection'],full_mothers=399252,forward_mothers=161014,selected_signal_rows=len(signals),full_original_signal_choices_unchanged=True,A_BUY_identity_fills={a['account_id']:a['fills'] for a in old_accounts},actions_read=0,COMMON_read=0,fit=0,downloads=0,A_replay=0))
        dailyC={};summariesC={};reports={};metrics=[];family=[];audits=[];tails={};groups=[];overlaps=[];add_fills=[]
        signal_family=signals.set_index('event_id').family_id
        for a in old_accounts:
            w,c=a['window'],a['cost'];name=f'NARROW_{ARM}_{w}_{c}';bounds=protocol['cash']['starts'][w]
            start,end=[int(np.searchsorted(dates,d)) for d in bounds]
            if end>=len(dates) or dates[end]!=bounds[1] or indices[w].shape!=(2000,end-start+1):raise ValueError('fixed calendar/window/index width differs')
            started+=1
            if started>4:raise ValueError('four C budget exhausted')
            write_json(output/f'cash_progress_{started:02d}.json',dict(started=started,completed=completed,account=name))
            book=kernel.run_cash_account(signals,market,dates,economics,c,name,start,end,prepared=prepared)
            completed+=1;folder=output/name;ledgers=reuse.write_ledgers(folder,book)
            add=addition_summary(book)
            summary,report,fy=reuse.helpers.cash_report(book,families,1000000.)
            summary.update(account=name,arm='C',window=w,cost=c,execution_unknown=bool(book['execution_unknown'] or add['material_add_unknown']),entry_execution_unknown=len(book['entry_execution_unknown']),capacity_unknown_roots=len(book['capacity_unknown_roots']),any_historical_stale=report['stale_days']>0,**add)
            report.update(account=name,window=w,cost=c,execution_unknown=summary['execution_unknown'],**add)
            summariesC[w,c]=summary;dailyC[w,c]=pd.DataFrame(book['daily']);reports[name]=report;metrics.append(summary)
            family.append(reuse.report_helpers.add_family_costs(fy,book).assign(arm='C',account=name,window=w,cost=c))
            audits.extend(dict(r,account=name,window=w,cost=c) for r in book['add_audit'])
            new_fills=[dict(r,account=name,window=w,cost=c,entry_kind='add') for r in book['fills'] if r['root_id'] in set(book['add_root_ids'])]
            add_fills.extend(new_fills)
            reuse.ref.write_table(folder/'add_audit.csv.gz',book['add_audit'],['event_id','reason','unknown'])
            reuse.ref.write_table(folder/'add_root_fills.csv.gz',new_fills,['account','root_id','event_id','date','side','qty','fee','slippage'])
            ledgers['add_audit']=binding(folder/'add_audit.csv.gz');ledgers['add_root_fills']=binding(folder/'add_root_fills.csv.gz')
            grouping,tail=reuse.extra_reports(book);groups.extend(dict(account=name,window=w,cost=c,**r) for r in grouping);tails[name]=tail
            overlap=fresh_overlap(buysA[w,c],book);overlap['family_id']=overlap.event_id.map(signal_family)
            overlaps.append(overlap.assign(window=w,cost=c))
            write_json(folder/'summary.json',kernel.original.safe(summary))
            accounts.append(dict(account_id=name,window=w,cost=c,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers,add_root_ids=book['add_root_ids']))
            print(json.dumps(dict(phase='account_complete',account=name,completed=completed,actual_add_roots=add['actual_add_roots'],material_add_unknown=add['material_add_unknown'])),flush=True)
        points=[];distributions={}
        for a in old_accounts:
            w,c=a['window'],a['cost'];key=w,c;stat,dist=reuse.paired_statistics(dailyC[key],dailyA[key],indices[w]);distributions[w+'_'+c]=dist
            points.append(dict(window=w,cost=c,contrast='C_minus_A157_OWN',active_total_return_pct=summariesC[key]['total_return_pct'],reference_total_return_pct=control[key]['total_return_pct'],**reuse.helpers.compare_points(summariesC[key],control[key]),**stat,C_add_roots=summariesC[key]['actual_add_roots'],participation_fill_count_difference=summariesC[key].get('fills',0)-control[key].get('fills',0)))
        stale=any(r['stale_days']>0 for r in list(reports.values())+list(diagnosticsA.values()))
        unknown=any(s.get('execution_unknown',False) for s in list(summariesC.values())+list(control.values()))
        wealth=all(reuse.reuse._log_path(d)[0] is not None for d in list(dailyC.values())+list(dailyA.values()))
        gate=reuse.fixed_gate(points,stale,wealth_positive=wealth,execution_unknown=unknown)
        gate.update(goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        reuse.ref.write_table(output/'account_summaries.csv.gz',metrics+metricsA,[])
        reuse.ref.write_table(output/'comparisons.csv.gz',points,[]);reuse.ref.write_table(output/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        reuse.ref.write_table(output/'add_audit.csv.gz',audits,['account','event_id','reason','unknown'])
        reuse.ref.write_table(output/'new_add_root_fills.csv.gz',add_fills,['account','root_id','event_id','date','side','qty','fee','slippage'])
        overlap=pd.concat(overlaps,ignore_index=True);reuse.ref.write_table(output/'fresh_BUY_identity_overlap.csv.gz',overlap,[])
        fresh_counts=overlap.groupby(['window','cost','participation'],observed=True).agg(events=('event_id','size'),A_quantity=('qty_A','sum'),C_quantity=('qty_C','sum'),C_add_same_event=('C_add_same_event','sum')).reset_index()
        reuse.ref.write_table(output/'fresh_participation_summary.csv.gz',fresh_counts,[])
        fy=pd.concat(family,ignore_index=True);reuse.ref.write_table(output/'family_year_including_zero.csv.gz',fy,[])
        total=fy.groupby(['account','arm','window','cost','family_id'],as_index=False)[['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum()
        reuse.ref.write_table(output/'family_total_including_zero.csv.gz',total,[])
        new_frame=pd.DataFrame(add_fills)
        if len(new_frame):
            new_frame['year']=new_frame.date.str[:4]
            stats=new_frame.groupby(['account','window','cost','year','family_id','side']).agg(root_count=('root_id','nunique'),fill_count=('qty','size'),filled_qty=('qty','sum'),fee=('fee','sum'),slippage=('slippage','sum')).reset_index()
        else:stats=pd.DataFrame(columns=['account','window','cost','year','family_id','side','root_count','fill_count','filled_qty','fee','slippage'])
        reuse.ref.write_table(output/'add_root_year_family_fill_groups.csv.gz',stats,[])
        annual=[dict(r,account=a,arm='C') for a,p in reports.items() for r in p['annual_slices']]+[dict(r,account=a,arm='A_REUSED') for a,p in diagnosticsA.items() for r in p['annual_slices']]
        reuse.ref.write_table(output/'annual_slices.csv.gz',annual,[])
        reuse.ref.write_table(output/'sector_variant_attribution.csv.gz',groups,[])
        write_json(output/'largest_wins_losses.json',kernel.original.safe(tails));write_json(output/'diagnostics.json',kernel.original.safe(reports));write_json(output/'continuation_gate.json',kernel.original.safe(gate))
        write_json(output/'budget_and_tick_disclosure.json',dict(mechanism='frozen596 independent winning-family new batch',old_F0_not_released=True,risk_rates_and_old_stops_unchanged=True,all_root_family_caps=True,full_scope=protocol['full_scope'],original_u_choices_unchanged=True,no_constant_account_cutoff_filter=True,no_D_reserve_reallocation=True,no_open_retroactive_Dlow_gate=True,old_A_replayed=False,fees_once_and_slip_in_fill=True,bar_execution_conditional=True,strict_first_print_fill_certified=False,add_roots_not_independent_samples=True,attribution_not_causal_PnL_decomposition=True,fresh_A_only_may_substitute_C_add_see_same_event_column=True,original_A_and_material_add_unknown_retained=True))
        if completed!=4 or reuse.ref.NATIVE_QUERIES:raise ValueError('exact four C/zeroSQL required')
        if reuse.cache_source.database_state(meta['database']['path'])!=native_receipt['database_after']:raise ValueError('database stat changed')
        status='completed'
    except Exception:
        error=traceback.format_exc();write_json(output/'failure.json',dict(error=error,started=started,completed=completed))
    terminal=dict(status=status,exit_code=0 if status=='completed' else 1,elapsed_seconds=time.monotonic()-began,cash_accounts_started=started,new_cash_accounts=completed,actual_model_fit_calls=0,SQL=0,GET=0,A_replayed=0,goal_complete=False)
    write_json(output/'actual_terminal.json',terminal)
    artifacts={p.name:binding(p) for p in output.iterdir() if p.is_file() and p.name!='manifest.json'}
    write_json(output/'manifest.json',dict(schema='stage597_winner_addition_cash_v1',status=status,protocol=pb,source_bundle=sources,inputs=protocol['input_bindings'],A_own_accounts=protocol['old_A_own_accounts'],accounts=accounts,artifacts=artifacts,terminal=binding(output/'actual_terminal.json'),new_cash_accounts=completed,actual_model_fit_calls=0,SQL=0,GET=0,A_replay=0,full_scope=protocol['full_scope'],goal_complete=False,production_qualified=False,increased_betting_qualified=False))
    print(json.dumps(terminal),flush=True)
    if status!='completed':raise RuntimeError(error)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--check-source',action='store_true');p.add_argument('--source-ready',type=Path)
    p.add_argument('--runner-test-receipt',type=Path);p.add_argument('--kernel-test-receipt',type=Path)
    a=p.parse_args();run(a.protocol,a.output,a.check_source,a.source_ready,a.runner_test_receipt,a.kernel_test_receipt)
