"""Stage517: four new continuation-exit cash books, frozen A157 reused.

Import is source-only. Explicit root514 protocol, completed515 portable heads and
independent516 acceptance are required before the one fresh actual operation.
All current decisions use actual cash positions; unit-path future fields never
enter the selected signal projection or the hook.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
ARM='C_CONTINUATION_EXIT'
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
BOUNDS={'primary_2020':('2020-01-01','2026-10-16'),'cold_2023':('2023-01-01','2026-10-16')}
MOTHER_FIELDS=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
# Explicit whitelist deliberately excludes terminal/participation/exit_date/R.
ACTION_FIELDS=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id',
 'family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
 'entry_capacity_qty','N_u','low20_u','u_close','source_lifecycle_target_date','K_target_date']

def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

base=load('stage497_member_identity_cash.py','stage517_pure497')
kernel=load('stage517_continuation_kernel.py','stage517_local_kernel')
binding,same,read_bytes,read_json,write_json=base.binding,base.same,base.read_bytes,base.read_json,base.write_json
numeric,read_table=base.numeric,base.read_table


def source_bundle():
    names=['stage517_continuation_cash.py','stage517_continuation_kernel.py','test_stage517_continuation_cash.py',
        'stage497_member_identity_cash.py','stage491_fomc_cash.py','stage515_continuation_fit.py']
    return sorted([binding(TOOLS/n) for n in names],key=lambda b:b['path'])


def account_specs():
    return [dict(arm=ARM,candidate=ARM,window=w,cost=c,account_id=f'NARROW_{ARM}_{w}_{c}')
            for w in WINDOWS for c in COSTS]


def prepare_choices(mothers,choices):
    """Original A is the selected VOLUNTARY_RESELECT entry policy, not131 A."""
    forward=mothers.loc[mothers.u_date.ge('2020-01-01'),MOTHER_FIELDS].reset_index(drop=True)
    if len(forward)!=161014 or len(choices)!=len(forward) or choices.event_id.duplicated().any():
        raise ValueError('complete original A forward choices required')
    for field in MOTHER_FIELDS:
        left,right=forward[field],choices[field]
        if field in ('sequence_index','u_index'):
            left,right=pd.to_numeric(left),pd.to_numeric(right)
        else:left,right=left.astype(str),right.astype(str)
        if left.tolist()!=right.tolist():raise ValueError('original choice identity differs '+field)
    if set(choices.arm)!={'VOLUNTARY_RESELECT'} or set(choices.scope)!={'main'} or set(choices.policy)!={'NARROW'}:
        raise ValueError('only frozen A VOLUNTARY_RESELECT main entries required')
    picked=choices.copy();numeric(picked,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
    if not picked.selected.isin([0,1]).all():raise ValueError('binary source selection required')
    ids=set(picked.loc[picked.selected.eq(1),'chosen_action_id'])
    if '' in ids or len(ids)!=int(picked.selected.sum()):raise ValueError('unique positive selected actions required')
    return picked,ids


def selected_action_projection(raw,ids,expected_rows=1552456):
    """One decompression/chunk stream; only causal fields are ever materialized."""
    frames=[];rows=0
    for chunk in pd.read_csv(io.BytesIO(raw),compression='gzip',dtype=str,keep_default_na=False,
            usecols=ACTION_FIELDS,chunksize=100000,float_precision='round_trip'):
        rows+=len(chunk);part=chunk.loc[chunk.action_id.isin(ids)].copy()
        if len(part):frames.append(part)
    if rows!=expected_rows:raise ValueError('complete accepted511 action summary required')
    actions=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=ACTION_FIELDS)
    if actions.action_id.duplicated().any() or set(actions.action_id)!=ids:
        raise ValueError('every selected original A action must be available')
    actions=actions.rename(columns={'sequence_index':'action_sequence_index'})
    actions['event_id']=actions['action_id']
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible',
        'entry_capacity_qty','N_u','low20_u','u_close'])
    return actions,dict(action_summary_streams=1,source_action_rows=rows,selected_actions=len(actions),
        source_fields=ACTION_FIELDS,outcome_field_reads=0,original129_reads=0)


class NativeStore:
    def __init__(self,calendar,series):self.calendar,self.series=calendar,series
    def locate(self,epoch,k):
        s=self.series.get(epoch)
        if s is None:return None
        j=int(np.searchsorted(s['days'],k))
        return j if j<len(s['days']) and s['days'][j]==k else None


def restore_arrays(raw,calendar):
    """One explicit cache read, no old132 implicit calendar/DB-protocol access."""
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets']
        flat={key:z[key] for key in ('days','values','accepted','valid','N','low20','run')}
    if len(epochs)!=9520 or int(offsets[-1])!=1552456 or offsets[0]!=0 or len(set(epochs))!=len(epochs):
        raise ValueError('accepted132 native array domain differs')
    return NativeStore(calendar,{epoch:{key:arr[int(offsets[j]):int(offsets[j+1])] for key,arr in flat.items()}
        for j,epoch in enumerate(epochs)})


def make_signals(v,actions,mothers,choices,market,dates,economics):
    picked=choices.copy();picked['arm']='B'
    signals=v.author.make_signals(actions,mothers,picked,'B',market,dates,economics)
    a=actions.set_index('action_id',verify_integrity=True)
    source_target=[];K_target=[];K_index=[];effective=[];origin=[]
    for row in signals.to_dict('records'):
        action=a.loc[row['event_id']]
        source,K=action.source_lifecycle_target_date,action.K_target_date
        if not source or not K:raise ValueError('selected causal lifecycle target dates required')
        source_i=int(np.searchsorted(dates,source));ki=int(np.searchsorted(dates,K))
        if source_i!=int(row['lifecycle_index']):raise ValueError('source511 lifecycle differs accepted cash')
        if row['D_index']>=ki:raise ValueError('original A selected action violates D<K')
        e=min(source_i,ki);which='same_source_and_voluntary' if source_i==ki else 'source_lifecycle' if source_i<ki else 'voluntary_calendar'
        source_target.append(source);K_target.append(K);K_index.append(ki if ki<len(dates) else None)
        effective.append(e);origin.append(which)
    signals['source_lifecycle_index']=signals.lifecycle_index
    signals['source_lifecycle_target_date']=source_target
    signals['K_target_date']=K_target;signals['voluntary_boundary_index']=K_index
    signals['effective_lifecycle_index']=effective;signals['effective_boundary_origin']=origin
    signals['lifecycle_index']=effective
    signals['arm']=ARM;signals['control_id']=ARM
    return signals


def run_four(output,run_account,export_account,*,before=None,finalize=None,metadata=None):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    clock=time.monotonic();began=datetime.now(timezone.utc).isoformat();started=completed=0
    records=[];books=[];status='failed';error=None;meta=dict(metadata or {})
    write_json(out/'actual_started.json',dict(stage=517,started_at=began,metadata=meta))
    def progress(phase,account=None):write_json(out/'cash_progress.json',dict(phase=phase,current_account=account,
        cash_accounts_started=started,cash_accounts_completed=completed,max_new_candidate_cash=4,new_fit=0,old_A_replays=0))
    try:
        progress('preparing')
        if before:before(out)
        for spec in account_specs():
            started+=1;progress('kernel_running',spec['account_id']);book=run_account(spec)
            path=out/'checkpoints'/(spec['account_id']+'.pickle.gz');path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(gzip.compress(pickle.dumps(book,protocol=5),mtime=0));completed+=1
            books.append(dict(spec=spec,book=binding(path)));del book
            write_json(out/'book_checkpoints.json',dict(cash_accounts_started=started,cash_accounts_completed=completed,books=books))
            progress('book_checkpoint_complete',spec['account_id'])
        for item in books:
            progress('reporting',item['spec']['account_id']);book=pickle.loads(gzip.decompress(read_bytes(item['book'])))
            records.append(export_account(item['spec'],book));del book
            write_json(out/'report_checkpoints.json',dict(accounts=records,raw_books_replayed=False))
        if finalize:finalize(out,records)
        status='completed';progress('completed');return records
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        terminal=dict(status=status,error=error,exit_code=0 if status=='completed' else 1,started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            cash_accounts_started=started,cash_accounts_completed=completed,new_cash_accounts=completed,new_fit=0,
            native_SQL=0,old_A_replays=0,automatic_retry=False,goal_complete=False,production_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        artifacts={str(p.relative_to(out)):binding(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
        write_json(out/'manifest.json',dict(schema='stage517_continuation_cash_manifest_v1',status=status,metadata=meta,
            accounts=records,artifacts=artifacts,terminal=binding(out/'actual_terminal.json'),new_fit=0,
            new_cash_accounts=completed,cash_accounts_started=started,old_A_replays=0,native_SQL=0,goal_complete=False))


def validate(args):
    out=Path(args.output).resolve()
    if LINE/'outputs/stage517_continuation_cash' not in out.parents or out.exists():
        raise ValueError('fresh Stage517 output required')
    pb=binding(args.protocol)
    if pb['sha256']!=args.protocol_sha256:raise ValueError('root514 protocol SHA differs')
    p=read_json(pb)
    if p.get('line_id')!=LINE.name or 'stage514' not in p.get('schema',''):
        raise ValueError('root514 continuation protocol required')
    hb=binding(args.handoff)
    if hb['sha256']!=args.handoff_sha256:raise ValueError('515 handoff SHA differs')
    h=read_json(hb)
    if h.get('protocol_sha256')!=pb['sha256']:raise ValueError('515 protocol closure differs')
    ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('exact root517 authorization differs')
    auth=read_json(ab)
    expected=dict(schema='stage517_exact_root_authorization_v1',authorized_by='root',stage='cash',
        protocol_sha256=pb['sha256'],output=str(out),max_new_cash=4,max_new_fit=0,actual_run_limit=1)
    if any(auth.get(k)!=v for k,v in expected.items()) or not same(auth['handoff_binding'],hb):
        raise ValueError('once-only exact root517 cash authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():
        raise ValueError('root517 exact source/test bundle differs')
    review=read_json(auth['model_review_binding'])
    if (review.get('schema')!='stage516_fixed_continuation_model_review_v1' or
            review.get('status')!='completed' or review.get('completed') is not True or
            review.get('material_disagreements')!=0 or review.get('material_issues')!=[] or
            review.get('coefficient_reconstructions')!=6 or review.get('cash')!=0 or review.get('new_fit')!=0):
        raise ValueError('completed independent516 actual review with zero material issues required')
    if not same(review['protocol_binding'],pb) or not same(review['portable_models_binding'],h['portable_models_binding']):
        raise ValueError('review/protocol/portable515 closure differs')
    fit=read_json(review['author_manifest_binding'])
    if (fit.get('schema')!='stage515_continuation_fit_manifest_v1' or fit.get('status')!='completed' or
            fit.get('fits_completed')!=6 or not same(fit['protocol_binding'],pb) or
            not same(fit['artifacts']['portable_models'],h['portable_models_binding']) or
            not same(fit['artifacts']['summary'],h['held_diagnostic_binding']) or
            not same(fit['artifacts']['handoff'],hb)):
        raise ValueError('completed reviewed six-head515 manifest closure required')
    c=p['cash_contract'];constants=tuple(c[k] for k in ('initial_capital','SINGLE_RISK','TOTAL_RISK',
        'MARGIN_CAP','MARGIN_BUFFER','entry_stop_N','daily_volume_cap'))
    if constants!=(1000000,.0025,.02,.25,1.1,.25,.01) or c['new_candidate_books']!=4:
        raise ValueError('frozen cash constants differ')
    if c['windows']!=list(WINDOWS) or c['costs']!=list(COSTS) or p['scope']['sample_end']!='2026-10-16':raise ValueError('cash windows differ')
    return out,p,pb,h,hb,auth,ab


def execute(args):
    out,p,pb,h,hb,auth,ab=validate(args);c=p['cash_contract'];inputs=c['input_bindings'];state={}
    metadata=dict(protocol=pb,handoff=hb,authorization=ab,source_bundle=source_bundle(),fixture=False)
    def prepare(folder):
        v=load('stage157_voluntary_cash.py','stage517_accepted157');r=v.reuse
        old=read_json(inputs['A157_manifest'])
        if v.source_bundle()!=old['source_bundle']:raise ValueError('accepted157 source dependencies changed')
        mothers=pd.read_csv(io.BytesIO(read_bytes(inputs['mother_domain'])),compression='gzip',usecols=MOTHER_FIELDS,
            dtype=str,keep_default_na=False,float_precision='round_trip')
        numeric(mothers,['sequence_index','u_index'])
        if len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98 or mothers.family_id.nunique()!=95:
            raise ValueError('complete511 mother/nochild domain required')
        choices,ids=prepare_choices(mothers,read_table(inputs['A_choices']))
        actions,action_receipt=selected_action_projection(read_bytes(inputs['action_path_summary']),ids)
        dates=base.decode_calendar(np.load(io.BytesIO(read_bytes(inputs['calendar'])),allow_pickle=False))
        meta=read_json(inputs['native_cache_manifest'])
        if not same(meta['file'],inputs['native_cache']):raise ValueError('accepted native cache manifest differs')
        store=restore_arrays(read_bytes(inputs['native_cache']),dates);market=r.CachedMarket(store)
        economics=read_json(inputs['economic_projection'])['instruments']
        if set(economics)!=set(store.series):raise ValueError('native/economics domain differs')
        signals=make_signals(v,actions,mothers,choices,market,dates,economics)
        prepared=v.author.organize(signals,mothers,dates)
        fitter=load('stage515_continuation_fit.py','stage517_frozen515')
        portable=read_json(h['portable_models_binding'])
        models=portable['models']
        expected_heads={scope+'|'+cutoff for scope in ('main','holdout_0','holdout_1') for cutoff in ('2020-01-01','2023-01-01')}
        if set(models)!=expected_heads:raise ValueError('all six reviewed portable heads required')
        controls={(x['window'],x['cost']):x for x in c['control_accounts_reused']}
        if len(controls)!=4:raise ValueError('four reused A157 OWN controls required')
        for (w,k),x in controls.items():
            if x['account_id']!='NARROW_VOLUNTARY_RESELECT_'+w+'_'+k or 'stage157_voluntary_cash' not in x['directory']:
                raise ValueError('A reference must be accepted157 OWN, never131B')
        bounds={w:tuple(int(np.searchsorted(dates,x)) for x in BOUNDS[w]) for w in WINDOWS}
        for w,(a,b) in bounds.items():
            if b>=len(dates) or dates[b]!=BOUNDS[w][1]:raise ValueError('fixed endpoint absent')
        state.update(v=v,r=r,mothers=mothers,market=market,dates=dates,economics=economics,signals=signals,
            prepared=prepared,models=models,fitter=fitter,controls=controls,bounds=bounds,families=sorted(mothers.family_id.unique()),
            summaries={},reports={},daily={},families_out=[],sectors=[],tails={})
        r.ref.write_table(folder/'signals_C_CONTINUATION_EXIT.csv.gz',signals,[])
        # Derived from the already-loaded complete mother RAM, including empty
        # references. Independent cash review need not re-read old511 mothers.
        r.ref.write_table(folder/'canonical_references.csv.gz',
            mothers[['product_id','u_index','reference_epoch']],[])
        write_json(folder/'source_read_receipt.json',dict(action_receipt,mother_domain_streams=1,mother_rows=len(mothers),
            canonical_products=98,canonical_families=95,canonical_reference_projection_rows=len(mothers),
            canonical_reference_projection_extra_source_reads=0,native_cache_reads=1,calendar_reads=1,economics_reads=1,
            original129_reads=0,COMMON_reads=0,fit=0,SQL=0,old_A_replays=0,unit_states_reads=0,
            unit_future_exit_observation_reads=0,choices_reselected=False,own_cash_state_scoring=True))
    def run(spec):
        start,end=state['bounds'][spec['window']]
        def scorer(day,current):return state['fitter'].predict_state(state['models'],day,current,scope='main')
        return kernel.run_cash_account(state['signals'],state['market'],state['dates'],state['economics'],
            spec['cost'],spec['account_id'],start,end,prepared=state['prepared'],continuation=scorer)
    def export(spec,book):
        r=state['r'];folder=out/spec['account_id'];ledgers=r.write_ledgers(folder,book)
        r.ref.write_table(folder/'continuation_audit.csv.gz',book['continuation_audit'],[])
        summary,report,fy=r.helpers.cash_report(book,state['families'],r.ref.INITIAL)
        tick_lots=0.;unknown_ticks=0
        for fill in book['fills']:
            tick=state['economics'][fill['epoch']].get('tick_size')
            if r.ref.positive(tick):tick_lots+=abs(fill['fill_price']-fill['reference_price'])/float(tick)*fill['qty']
            else:unknown_ticks+=1
        summary.update(spec,role='candidate',any_historical_stale=report['stale_days']>0,
            execution_unknown=book['execution_unknown'],unknown_capacity_fills=sum(x['capacity_state']=='execution_capacity_unknown' for x in book['capacity_audit']),
            capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']),
            slippage_tick_lots_known=tick_lots,unknown_tick_fills=unknown_ticks,slippage_already_in_fill_price=True,
            continuation_close_decisions=sum(x['discretionary'] for x in book['continuation_audit']),
            continuation_exit_requests=sum(x['requested'] for x in book['continuation_audit']),
            continuation_actual_exit_fills=sum(x['reason']=='ai_continuation_next_open_exit' for x in book['fills']))
        key=(ARM,spec['window'],spec['cost']);state['summaries'][key]=summary;state['reports'][spec['account_id']]=report
        state['daily'][key]=pd.DataFrame(book['daily']);state['families_out'].append(r.report_helpers.add_family_costs(fy,book).assign(**spec))
        groups,tails=r.extra_reports(book);state['tails'][spec['account_id']]=tails
        state['sectors'].extend(dict(account_id=spec['account_id'],arm=ARM,window=spec['window'],cost=spec['cost'],**x) for x in groups)
        for name,value in [('summary',summary),('diagnostics',report),('largest_wins_losses',tails)]:write_json(folder/(name+'.json'),r.kernel.original.safe(value))
        r.ref.write_table(folder/'sector_variant_year_including_zero.csv.gz',state['v'].sector_year_attribution(book),[])
        return dict(spec,directory=str(folder),summary=binding(folder/'summary.json'),ledgers=ledgers,
            continuation_audit=binding(folder/'continuation_audit.csv.gz'))
    def finalize(folder,records):
        r=state['r'];control_reports=read_json(inputs['A157_diagnostics']);indices={}
        for w,b in c['CI_indices'].items():indices[w]=np.load(io.BytesIO(read_bytes(b)),allow_pickle=False)
        for (w,k),x in state['controls'].items():
            key=('A',w,k);state['summaries'][key]=dict(read_json(x['summary']),arm='A',window=w,cost=k,account_id=x['account_id'],role='control_reused',replayed=False)
            state['daily'][key]=pd.read_csv(io.BytesIO(read_bytes(base.control_ledger_binding(x,'daily'))),compression='gzip',float_precision='round_trip')
            state['reports'][x['account_id']]=control_reports[x['account_id']]
        points=[];annual=[];paired=[];distributions={}
        for w in WINDOWS:
            for k in COSTS:
                a,b=state['summaries'][(ARM,w,k)],state['summaries'][('A',w,k)]
                start,end=state['bounds'][w]
                if indices[w].shape!=(2000,end-start+1):raise ValueError('original bootstrap shape differs')
                stats,dist=r.paired_statistics(state['daily'][(ARM,w,k)],state['daily'][('A',w,k)],indices[w])
                points.append(dict(contrast='C_minus_A',window=w,cost=k,active_account_id=a['account_id'],reference_account_id=b['account_id'],
                    active_total_return_pct=a['total_return_pct'],reference_total_return_pct=b['total_return_pct'],ending_equity_difference=a['ending_equity']-b['ending_equity'],
                    sharpe_difference=None if a.get('sharpe') is None or b.get('sharpe') is None else a['sharpe']-b['sharpe'],**r.helpers.compare_points(a,b),**stats))
                distributions[w+'_'+k]=dist
                paired.extend(dict(window=w,cost=k,**x) for x in base.pair_years(state['reports'][a['account_id']]['annual_slices'],state['reports'][b['account_id']]['annual_slices']))
        for key,summary in state['summaries'].items():
            annual.extend(dict(account_id=summary['account_id'],arm=key[0],window=key[1],cost=key[2],**x)
                for x in state['reports'][summary['account_id']]['annual_slices'])
        stale=any(x['stale_days']>0 for x in state['reports'].values())
        unknown=any(x['execution_unknown'] for x in state['summaries'].values())
        wealth=all(r._log_path(x)[0] is not None for x in state['daily'].values())
        gate=state['v'].fixed_gate(points,stale,wealth_positive=wealth,execution_unknown=unknown)
        gate.update(schema='stage517_continuation_cash_gate_v1',decision_scope='cash_only_held_model_gate_separate',held_model_diagnostics_binding=h['held_diagnostic_binding'],
            held_not_recomputed=True,model_held_gate_not_substituted_by_cash_gate=True,new_accounts=4,old_A_replays=0,
            full_products=98,full_families=95,alpha_proved=False,causal_identification=False)
        old_fy=read_table(inputs['A157_family_year']);old_fy=old_fy.loc[old_fy.arm.eq('VOLUNTARY_RESELECT')].copy();old_fy['arm']='A';old_fy['candidate']='A'
        numeric(old_fy,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
        fy=pd.concat(state['families_out']+[old_fy],ignore_index=True)
        for (arm,w,k),s in state['summaries'].items():
            f=fy.loc[fy.arm.eq(arm)&fy.window.eq(w)&fy.cost.eq(k)]
            if not np.isclose(f.net_equity_contribution.sum(),s['ending_equity']-r.ref.INITIAL,rtol=1e-12,atol=1e-6):raise ValueError('family cash identity differs')
        through2025=[dict(account_id=state['summaries'][key]['account_id'],arm=key[0],window=key[1],cost=key[2],
            **base.same_book_through_2025(frame,r.ref.INITIAL)) for key,frame in state['daily'].items()]
        for name,value in [('account_summaries',list(state['summaries'].values())),('comparisons',points),('annual_slices',annual),
            ('paired_annual',paired),('bootstrap_distributions',pd.DataFrame(distributions)),('family_year_including_zero',fy),
            ('family_total_including_zero',fy.groupby(['arm','window','cost','family_id'])[['net_equity_contribution','fee','slippage','fill_count','filled_qty']].sum().reset_index()),
            ('same_book_through_2025',through2025),('sector_variant_attribution',state['sectors'])]:r.ref.write_table(folder/(name+'.csv.gz'),value,[])
        for name,value in [('decision',gate),('diagnostics',state['reports']),('largest_wins_losses',state['tails'])]:write_json(folder/(name+'.json'),r.kernel.original.safe(value))
    return run_four(out,run,export,before=prepare,finalize=finalize,metadata=metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','handoff','handoff-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+name,required=True)
    execute(parser.parse_args())

if __name__=='__main__':main()
