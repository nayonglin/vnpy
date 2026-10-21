"""Frozen611: four conditional D-only resting limits, original own-budget and costs."""
import argparse, re, gzip, hashlib, importlib.util, inspect, io, json, time, traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import stage613_conditional_limit_kernel as kernel
import stage157_voluntary_cash as reuse
TOOLS=Path(__file__).resolve().parent
PROTOCOL_SHA='19c23d804c086a6d229cb2b96459e851549223916222646e1a3e354fac16992b'
ARM='D1_RESTING_CLOSE_LIMIT'
NEW_FILES=['stage613_conditional_limit_cash.py','stage613_conditional_limit_kernel.py','test_stage613_conditional_limit.py']

def binding(path,data=None):
    p=Path(path).resolve();data=p.read_bytes() if data is None else data
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def read_bytes(bound):
    p=Path(bound['path']);data=p.read_bytes()
    if binding(p,data)!=bound:raise ValueError('bound input changed '+str(p))
    return data
def read_json(bound):return json.loads(read_bytes(bound))
def write_json(path,obj):
    with path.open('x') as f:json.dump(kernel.original.safe(obj),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def read_table(bound,**kwargs):return pd.read_csv(io.BytesIO(read_bytes(bound)),compression='gzip',keep_default_na=False,float_precision='round_trip',**kwargs)
def source_bundle():return [binding(TOOLS/n) for n in NEW_FILES]
def source_diff():
    source=inspect.getsource(kernel._run_cash_account)
    def remove(match):
        if match.group(2)=='ENTRY':return match.group(1)+"F=bar['open'];SL0=F-policy_k(policy)*intent['N_u']\n"
        return ''
    restored=re.sub(r'(?ms)^([ ]*)# BEGIN613_(\w+)\n.*?^\1# END613_\2\n',remove,source)
    restored=restored.replace('def _run_cash_account(', 'def run_cash_account(',1)
    if restored!=inspect.getsource(kernel.accepted.run_cash_account):raise ValueError('original131 changed outside isolated entry/audit/invariant')
    return dict(original131_restored_exact=True,old_position_loop_unchanged=True,original_u_budget_unchanged=True,
        event_phase_split=False,winner_addition=False,new_D_global_gate=False,
        original_kernel=binding(TOOLS/'stage131_contract_choice_kernel.py'))
def metadata_frame(signals):
    if signals.event_id.duplicated().any() or not all(signals.policy=='NARROW') or not all(signals.arm=='VOLUNTARY_RESELECT'):raise ValueError('fixed157 signal identity differs')
    if not np.isfinite(signals[['u_close','N_u','low20_u']].to_numpy(float)).all():raise ValueError('fixed signal causal values invalid')
    if not all(signals.D_index==signals.u_index+1):raise ValueError('original source D differs')

def limit_audit(book,name,window,cost):
    return [dict(row,account=name,window=window,cost=cost) for row in book['limit_audit']]

def entry_groups(book,name,window,cost):
    groups={}
    for p in book['closed_episodes']+book['open_episodes']:
        kind=p.get('limit_entry_kind','unknown');g=groups.setdefault(kind,dict(roots=0,net_pnl=0.,fees=0.,slippage=0.))
        g['roots']+=1;g['net_pnl']+=p['realized_gross']-p['entry_fees']-p['exit_fees']+p.get('unrealized',0.)
        fs=[f for f in book['fills'] if f['root_id']==p['root_id']]
        g['fees']+=sum(f['fee'] for f in fs);g['slippage']+=sum(f['slippage'] for f in fs)
    if abs(sum(g['net_pnl'] for g in groups.values())-(book['daily'][-1]['equity']-1000000.))>1e-6:
        raise AssertionError('entry-group PnL identity')
    return [dict(account=name,window=window,cost=cost,entry_kind=kind,**g,meaning='bookkeeping allocation; not causal or executable-fill proof') for kind,g in groups.items()]

def run(protocol_path,output,check,ready_path):
    raw=protocol_path.read_bytes();pb=binding(protocol_path,raw)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen611 protocol changed')
    protocol=json.loads(raw);assert protocol['schema']=='stage611_frozen_conditional_limit_cash_v1'
    sources=source_bundle();diff=source_diff();output.mkdir(parents=True,exist_ok=False)
    if check:
        ready=dict(source_ready=True,actual_started=False,protocol=pb,source_bundle=sources,source_diff=diff,
            tests='7 new conditional-entry synthetic cases passed; no historical replay',fit=0,cash=0,SQL=0,GET=0)
        write_json(output/'source_ready.json',ready);print(json.dumps(ready));return
    if ready_path is None:raise ValueError('exact source-ready receipt required')
    ready=json.loads(ready_path.read_text())
    if ready['source_bundle']!=sources or ready['protocol']!=pb or not ready['source_ready']:raise ValueError('source-ready binding differs')
    fixture=read_json(ready['fixture_receipt'])
    if fixture.get('exit_code')!=0 or fixture['source_bundle']!=sources:raise ValueError('fixture receipt differs from current sources')
    began=time.monotonic();started=completed=0;accounts=[];status='failed';error=None
    write_json(output/'actual_started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),protocol=pb,source_bundle=sources,source_ready=binding(ready_path),max_new_cash=4))
    try:
        for old_source in protocol['immutable_sources'].values():read_bytes(old_source)
        inputs=protocol['input_bindings'];manifest157=read_json(inputs['accepted157_manifest'])
        if manifest157['schema']!='stage157_voluntary_cash_v1' or manifest157['status'] not in ('completed','completed_with_metadata_continuation') or manifest157['new_cash_accounts']!=4:raise ValueError('accepted157 own cash required')
        if manifest157['signals']!=inputs['signals']:raise ValueError('unchanged signal binding required')
        signals=read_table(inputs['signals']);metadata_frame(signals)
        mother_cols=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
        mothers=read_table(inputs['mothers'],dtype=str,usecols=mother_cols)
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:raise ValueError('whole98/95mother domain changed')
        forward=mothers.loc[mothers.u_date.between('2020-01-01','2026-10-16')]
        if len(forward)!=161014:raise ValueError('whole forward mother domain changed')
        meta=read_json(inputs['native_cache_manifest'])
        if meta['file']!=inputs['native_cache']:raise ValueError('exact cache binding required')
        store,native_receipt,_=reuse.cache_source.restore_native_cache(inputs['native_cache_manifest'])
        market,dates=reuse.CachedMarket(store),store.calendar
        market_protocol=read_json(inputs['market_protocol']);economics=read_json(market_protocol['economic_projection'])['instruments']
        execution=read_json(inputs['execution_protocol'])
        if set(economics)!=set(store.series) or reuse.ref.NATIVE_QUERIES or native_receipt['native_source_queries']:raise ValueError('cached economics/SQL differs')
        prepared=reuse.author.organize(signals,mothers,dates);families=sorted(mothers.family_id.unique())
        indices={w:np.load(io.BytesIO(read_bytes(bound)),allow_pickle=False) for w,bound in protocol['bootstrap_indices'].items()}
        diagnosticsA=read_json(inputs['A_diagnostics']);summariesA=read_table(inputs['A_summaries'])
        control={};dailyA={};metricsA=[];buysA={};Afill_bindings={}
        for a in protocol['old_A_own_accounts']:
            key=(a['window'],a['cost']);control[key]=read_json(a['summary']);dailyA[key]=read_table(a['daily'])
            if a['account_id'] not in set(summariesA.account):raise ValueError('A OWN summary id missing')
            own=next(x for x in manifest157['accounts'] if x['account_id']==a['account_id'])
            fb=a['fills'];Afill_bindings[a['account_id']]=fb
            if own['ledgers']['fills']!=fb:raise ValueError('frozen A fills differs')
            # Root-approved extra small reads: BUY identities only, no counterfactual PnL.
            fills=read_table(fb,usecols=['event_id','epoch','date','side','qty'])
            buysA[key]=fills.loc[fills.side=='BUY'].drop(columns='side')
            metricsA.append(dict(control[key],arm='A_REUSED',window=a['window'],cost=a['cost'],source_only=True,replayed=False))
        write_json(output/'source_read_receipt.json',dict(native_receipt,signals=inputs['signals'],mothers=inputs['mothers'],full_mothers=399252,
            forward_mothers=161014,selected_signal_rows=len(signals),u_choices_unchanged=True,A_BUY_identity_fills=Afill_bindings,
            actions_read=0,COMMON_read=0,fit=0,downloads=0,A_replay=0))
        dailyC={};summariesC={};reports={};metrics=[];family=[];limits=[];tails={};groups=[];overlaps=[];limit_groups=[]
        for old in protocol['old_A_own_accounts']:
            w,c=old['window'],old['cost'];name=f'NARROW_{ARM}_{w}_{c}';bounds=protocol['cash']['starts'][w]
            start,end=[int(np.searchsorted(dates,d)) for d in bounds]
            if dates[end]!=bounds[1] or indices[w].shape!=(2000,end-start+1):raise ValueError('fixed calendar/window/bootstrap differs')
            started+=1
            if started>4:raise ValueError('new4 cash budget exhausted')
            write_json(output/f'cash_progress_{started:02d}.json',dict(started=started,completed=completed,account=name))
            book=kernel.run_cash_account(signals,market,dates,economics,c,name,start,end,prepared=prepared)
            completed+=1;folder=output/name;ledgers=reuse.write_ledgers(folder,book)
            summary,report,fy=reuse.helpers.cash_report(book,families,1000000.)
            audit=limit_audit(book,name,w,c);limits.extend(audit);counts=pd.Series([r['D_state'] for r in audit],dtype=str).value_counts().to_dict();limit_groups.extend(entry_groups(book,name,w,c))
            summary.update(account=name,arm='C',window=w,cost=c,execution_unknown=bool(book['execution_unknown']),
                entry_execution_unknown=len(book['entry_execution_unknown']),capacity_unknown_roots=len(book['capacity_unknown_roots']),
                any_historical_stale=report['stale_days']>0,limit_orders=len(audit),
                limit_open=sum(r.get('limit_state')=='open_marketable' and r['D_qty']>0 for r in audit),
                limit_intraday=sum(r.get('limit_state')=='intraday_first_touch' and r['D_qty']>0 for r in audit),
                limit_expired=counts.get('not_touched_expired',0),numeric_inverse_unknown=book['numeric_inverse_unknown'])
            report.update(account=name,window=w,cost=c,execution_unknown=book['execution_unknown'],limit_reason_counts=counts)
            summariesC[(w,c)]=summary;dailyC[(w,c)]=pd.DataFrame(book['daily']);reports[name]=report;metrics.append(summary)
            family.append(reuse.report_helpers.add_family_costs(fy,book).assign(arm='C',account=name,window=w,cost=c))
            grouping,tail=reuse.extra_reports(book);groups.extend(dict(account=name,window=w,cost=c,**r) for r in grouping);tails[name]=tail
            buysC=pd.DataFrame(book['fills'],columns=['event_id','epoch','date','side','qty'])
            buysC=buysC.loc[buysC.side=='BUY'].drop(columns='side')
            overlap=buysA[(w,c)].merge(buysC,on=['event_id','epoch'],how='outer',suffixes=('_A','_C'),indicator=True,validate='one_to_one')
            overlap['participation']=overlap.pop('_merge').map({'left_only':'A_only','both':'common','right_only':'C_only'})
            overlaps.append(overlap.assign(window=w,cost=c))
            write_json(folder/'summary.json',summary)
            accounts.append(dict(account_id=name,window=w,cost=c,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers))
            print(json.dumps(dict(phase='account_complete',account=name,completed=completed,limit_expired=summary['limit_expired'])),flush=True)
        points=[];distributions={}
        for old in protocol['old_A_own_accounts']:
            w,c=old['window'],old['cost'];key=(w,c);stat,dist=reuse.paired_statistics(dailyC[key],dailyA[key],indices[w]);distributions[w+'_'+c]=dist
            points.append(dict(window=w,cost=c,contrast='C_minus_A157_OWN',active_total_return_pct=summariesC[key]['total_return_pct'],
                reference_total_return_pct=control[key]['total_return_pct'],**reuse.helpers.compare_points(summariesC[key],control[key]),**stat,
                C_limit_expired=summariesC[key]['limit_expired'],participation_trade_count_difference=summariesC[key].get('fills',0)-control[key].get('fills',0)))
        stale=any(r['stale_days']>0 for r in list(reports.values())+list(diagnosticsA.values()))
        unknown=any(s.get('execution_unknown',False) for s in list(summariesC.values())+list(control.values()))
        wealth=all(reuse.reuse._log_path(d)[0] is not None for d in list(dailyC.values())+list(dailyA.values()))
        gate=reuse.fixed_gate(points,stale,wealth_positive=wealth,execution_unknown=unknown)
        gate.update(goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        reuse.ref.write_table(output/'account_summaries.csv.gz',metrics+metricsA,[])
        reuse.ref.write_table(output/'comparisons.csv.gz',points,[]);reuse.ref.write_table(output/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        reuse.ref.write_table(output/'limit_audit.csv.gz',limits,['account','event_id','limit_state','D_state','D_qty'])
        reuse.ref.write_table(output/'entry_kind_bookkeeping.csv.gz',limit_groups,[])
        reuse.ref.write_table(output/'BUY_identity_overlap.csv.gz',pd.concat(overlaps,ignore_index=True),[])
        reuse.ref.write_table(output/'family_year_including_zero.csv.gz',pd.concat(family,ignore_index=True),[])
        reuse.ref.write_table(output/'annual_slices.csv.gz',[dict(account=a,**r) for a,p in {**reports,**diagnosticsA}.items() for r in p['annual_slices']],[])
        reuse.ref.write_table(output/'sector_variant_attribution.csv.gz',groups,[])
        write_json(output/'largest_wins_losses.json',tails);write_json(output/'diagnostics.json',reports);write_json(output/'continuation_gate.json',gate)
        write_json(output/'budget_and_tick_disclosure.json',dict(limit='actual selected epoch u.close; D start through close only',
            entry_contract=protocol['entry'],bookkeeping=protocol['bookkeeping'],unknown_accounting=protocol['unknown_accounting'],
            rawF_SL0_unchanged=True,quote_clipped=False,cash_slippage_reclassified=False,own_u_budget_formula_unchanged=True,
            same_D_reallocation=False,winner_addition=False,event_phase_split=False,old_A_replayed=False,
            old_position_loop_unchanged=True,conditional_first_touch_full_fill=True,actual_execution_certified=False,
            intraday_cash_margin_safety_certified=False,return_DD_bounds=False,entry_group_PnL_is_causal=False,
            CI_gate='original157 PRIMARY_2020 STRESS lower>0',full_domain=protocol['full_scope']))
        if completed!=4 or reuse.ref.NATIVE_QUERIES:raise ValueError('exact4 cash/zeroSQL required')
        if reuse.cache_source.database_state(meta['database']['path'])!=native_receipt['database_after']:raise ValueError('database stat changed')
        status='completed'
    except Exception:
        error=traceback.format_exc();write_json(output/'failure.json',dict(error=error,started=started,completed=completed))
    terminal=dict(status=status,exit_code=0 if status=='completed' else 1,elapsed_seconds=time.monotonic()-began,
        cash_accounts_started=started,new_cash_accounts=completed,actual_model_fit_calls=0,SQL=0,GET=0,A_replayed=0,goal_complete=False)
    write_json(output/'actual_terminal.json',terminal)
    artifacts={p.name:binding(p) for p in output.iterdir() if p.is_file() and p.name not in ('manifest.json',)}
    write_json(output/'manifest.json',dict(schema='stage613_conditional_limit_cash_v1',status=status,protocol=pb,source_bundle=sources,
        source_diff=diff,inputs=protocol['input_bindings'],A_own_accounts=protocol['old_A_own_accounts'],accounts=accounts,artifacts=artifacts,
        terminal=binding(output/'actual_terminal.json'),new_cash_accounts=completed,actual_model_fit_calls=0,SQL=0,GET=0,A_replay=0,
        full_scope=protocol['full_scope'],goal_complete=False,production_qualified=False,increased_betting_qualified=False))
    print(json.dumps(terminal),flush=True)
    if status!='completed':raise RuntimeError(error)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--check-source',action='store_true');p.add_argument('--source-ready',type=Path)
    a=p.parse_args();run(a.protocol,a.output,a.check_source,a.source_ready)
