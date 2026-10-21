"""Stage070 fixed 24 accounts; native load shared once, reads only Stage071 scores.

Pure helpers operate on supplied arrays. No real execution without exact source,
protocol, input and fresh-output authorization. Old054 supplies only diagnostics.
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
_spec=importlib.util.spec_from_file_location('stage070_cash_kernel',TOOLS/'stage070_policy_kernel.py')
kernel=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(kernel)
ref=kernel.ref
_helper=TOOLS/'stage054_maturity_cash_compare.py'
if hashlib.sha256(_helper.read_bytes()).hexdigest()!='f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd':
    raise ValueError('accepted054 pure diagnostics changed')
_spec=importlib.util.spec_from_file_location('stage070_diagnostics054',_helper)
diagnostics=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(diagnostics)
ARMS=('COMMON','SETTLEMENT','OHLC_PROXY')
POLICIES=('WIDE','NARROW')
SIGNAL_FIELDS=['event_id','product_id','family_id','u_date','u_index','reference_epoch',
               'label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index']
EMPTY_COLUMNS={
    'fills':['account_id','scenario','root_id','event_id','family_id','product_id','epoch','date','side','qty',
             'reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','reason','risk_per_lot'],
    'budgets':['account_id','scenario','budget_id','event_id','family_id','u_date','execution_date','qty_cap','D_qty','D_state','budget_state'],
    'position_days':['account_id','scenario','date','root_id','event_id','family_id','product_id','epoch','qty','risk_per_lot','mark','mark_state','unrealized','notional'],
    'closed_episodes':['root_id','event_id','family_id','product_id','epoch','entry_date','exit_date','exit_reason','initial_qty','qty','net_pnl','label_evidence'],
    'open_episodes':['root_id','event_id','family_id','product_id','epoch','entry_date','initial_qty','qty','state','unrealized'],
}


def make_signals(labels,predictions,policy,arm):
    """Retain full mother. Future label/participation/exit states never gate orders."""
    base=labels[SIGNAL_FIELDS].copy()
    base['reference_epoch']=base.reference_epoch.fillna('')
    if base.event_id.duplicated().any() or base.duplicated(['product_id','u_date']).any():
        raise ValueError('duplicate full mother identity')
    chosen=predictions.loc[predictions.policy.eq(policy)&predictions.arm.eq(arm)].copy()
    expected=base.loc[base.u_date.ge('2020-01-01'),'event_id']
    if chosen.event_id.duplicated().any() or set(chosen.event_id)!=set(expected):
        raise ValueError('scores must preserve entire 2020+ mother per policy/arm')
    identity=chosen.merge(base[['event_id','product_id','family_id','u_date','u_index','reference_epoch','label_history_ready20']],
                          on='event_id',validate='one_to_one',suffixes=('','_label'))
    for col in ('product_id','family_id','u_date','u_index','reference_epoch'):
        if not identity[col].fillna('').eq(identity[col+'_label'].fillna('')).all():
            raise ValueError('score/u identity mismatch '+col)
    if not identity.history_ready20.eq(identity.label_history_ready20).all():
        raise ValueError('score causal ready20 changed')
    action=identity.label_history_ready20.eq(1)&np.isfinite(identity.score)&identity.score.gt(0)
    if not identity.selected.eq(action.astype(int)).all():
        raise ValueError('score action differs from ready20 and positive score')
    expected_cutoff=np.where(identity.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
    if not identity.cutoff.eq(expected_cutoff).all():
        raise ValueError('score cutoff violates disjoint forward blocks')
    if 'sequence_index' in labels:
        order=chosen.merge(labels[['event_id','sequence_index']],on='event_id',validate='one_to_one',suffixes=('','_label'))
        if not order.sequence_index.eq(order.sequence_index_label).all():
            raise ValueError('score sequence index changed')
    result=base.merge(chosen[['event_id','cutoff','score']],on='event_id',how='left',sort=False,validate='one_to_one')
    result['potential']=(result.label_history_ready20.eq(1)&np.isfinite(result.score)&result.score.gt(0)).astype(np.int8)
    result['D_index']=result.u_index+1
    return result


def compare_points(active,reference):
    active_empty=active['fills']==0
    reference_empty=reference['fills']==0
    return dict(return_percentage_point_difference=active['total_return_pct']-reference['total_return_pct'],
                drawdown_percentage_point_difference=None if reference_empty else active['max_drawdown_pct']-reference['max_drawdown_pct'],
                dd_comparison_state='NA_empty_reference' if reference_empty else 'active_reference',
                identification='all_empty_unidentified' if active_empty and reference_empty else 'observed_cash_comparison')


def paired_statistics(a,b,indices):
    if a.date.tolist()!=b.date.tolist():raise ValueError('paired source dates differ')
    al,ast=diagnostics.daily_log_growth(a,ref.INITIAL)
    bl,bst=diagnostics.daily_log_growth(b,ref.INITIAL)
    if ast!=bst or ast!='valid':
        return dict(status='survival_failure_no_log_repair',ci95_low=None,ci95_high=None),np.full(len(indices),np.nan)
    difference=al-bl
    values=difference[indices].mean(axis=1)
    lo,hi=np.quantile(values,[.025,.975])
    return dict(status='valid',mean_daily_log_difference=float(difference.mean()),
                cumulative_log_difference=float(difference.sum()),ci95_low=float(lo),ci95_high=float(hi)),values


def cash_report(book,families,initial):
    report,family_year=diagnostics.cash_diagnostics(book,initial)
    years=sorted({x['date'][:4] for x in book['daily']})
    complete=pd.MultiIndex.from_product([sorted(families),years],names=['family_id','year']).to_frame(index=False)
    family_year=complete.merge(family_year,on=['family_id','year'],how='left').fillna({'net_equity_contribution':0.,'fee':0.})
    fills=pd.DataFrame(book['fills'])
    closed=pd.DataFrame(book['closed_episodes'])
    summary=dict(book['summary'],fills=len(book['fills']))
    summary['max_open_notional']=max((d['open_notional'] for d in book['daily']),default=0.)
    summary['max_buffered_margin']=max((d['buffered_margin'] for d in book['daily']),default=0.)
    summary['max_frozen_initial_risk']=max((d['initial_risk'] for d in book['daily']),default=0.)
    summary['total_filled_qty']=int(fills.qty.sum()) if len(fills) else 0
    summary['turnover_notional']=float((fills.qty*fills.multiplier*fills.fill_price).sum()) if len(fills) else 0.
    summary['closed_net_CNY_right_tail']=[] if closed.empty else closed.sort_values('net_pnl',ascending=False).head(5)[['event_id','family_id','net_pnl']].to_dict('records')
    summary['closed_top5_positive_net_CNY']=float(closed.loc[closed.net_pnl.gt(0),'net_pnl'].nlargest(5).sum()) if len(closed) else 0.
    summary['closed_positive_net_CNY']=float(closed.loc[closed.net_pnl.gt(0),'net_pnl'].sum()) if len(closed) else 0.
    gaps=[]
    if len(fills):
        roots={r['root_id']:r for r in book['closed_episodes']+book['open_episodes']}
        for fill in book['fills']:
            if fill['side']=='SELL' and fill['reason']=='gap_stop':
                root=roots[fill['root_id']]
                loss=(root['entry_reference']-fill['reference_price'])/root['R0']
                gaps.append(dict(event_id=fill['event_id'],date=fill['date'],gross_loss_R=loss,
                                 qty=fill['qty'],realized_gross=fill['realized_gross'],exit_fee=fill['fee']))
    report.update(gap_stop_fills=gaps,gap_stop_exceeds_1R=sum(g['gross_loss_R']>1 for g in gaps),
                  limitations=['continuous barrier with adverse tick fill; intraday gaps/queue not identified',
                               'zero price scenarios are not finite universal loss bounds',
                               'year slices and 2023 window overlap; no independent replication claim'])
    return summary,report,family_year


def comparisons_and_gates(summaries,daily,protocol):
    pairs=[];bootstrap={};distributions={};indices={}
    for window in protocol['finance']['windows']:
        w=window['id']
        n=len(daily[('NARROW','SETTLEMENT',w,'stress')])
        index=diagnostics.circular_indices(n,**{k:protocol['finance']['bootstrap'][v] for k,v in
                   [('repetitions','repetitions'),('block_length','block_length'),('seed','seed')]})
        indices[w]=index
        for cost in ('base','stress'):
            contrasts=[((p,'SETTLEMENT',w,cost),(p,r,w,cost),f'{p}_SETTLEMENT_minus_{r}')
                       for p in POLICIES for r in ('COMMON','OHLC_PROXY')]
            contrasts.append((('NARROW','SETTLEMENT',w,cost),('WIDE','SETTLEMENT',w,cost),'NARROW_minus_WIDE_SETTLEMENT'))
            for a,b,name in contrasts:
                point=compare_points(summaries[a],summaries[b])
                stats,dist=paired_statistics(daily[a],daily[b],index)
                ident=f'{w}_{cost}_{name}'
                point.update(window=w,cost=cost,contrast=name,**stats)
                pairs.append(point);bootstrap[ident]=stats;distributions[ident]=dist
    def get(w,cost,contrast):return next(p for p in pairs if p['window']==w and p['cost']==cost and p['contrast']==contrast)
    information=[]
    for policy in POLICIES:
        main=summaries[(policy,'SETTLEMENT','primary_2020','stress')]
        primary=[get('primary_2020','stress',f'{policy}_SETTLEMENT_minus_{r}') for r in ('COMMON','OHLC_PROXY')]
        cold=[get('cold_2023',cost,f'{policy}_SETTLEMENT_minus_{r}') for cost in ('base','stress') for r in ('COMMON','OHLC_PROXY')]
        nominal=main['total_return_pct']>0 and all(p['ci95_low'] is not None and p['ci95_low']>0 for p in primary)
        nominal=nominal and all(summaries[(policy,'SETTLEMENT','cold_2023',c)]['total_return_pct']>0 for c in ('base','stress'))
        nominal=nominal and all(p['return_percentage_point_difference']>=0 for p in cold)
        empty=all(summaries[(policy,a,w,c)]['fills']==0 for a in ARMS for w in ('primary_2020','cold_2023') for c in ('base','stress'))
        information.append(dict(policy=policy,nominal_pass=nominal,status='all_empty_unidentified' if empty else 'supported_pending_unknown_audit' if nominal else 'unsupported',
                                kind='information',empty_reference_dd_not_a_gate=True))
    relevant=[get(w,c,'NARROW_minus_WIDE_SETTLEMENT') for w in ('primary_2020','cold_2023') for c in ('base','stress')]
    all_empty=all(p['identification']=='all_empty_unidentified' for p in relevant)
    policy_nominal=all(p['return_percentage_point_difference']>0 if p['window']=='primary_2020' else p['return_percentage_point_difference']>=0 for p in relevant)
    # Empty reference DD is unresolved, never mechanically failed or passed.
    dd_identified=all(p['drawdown_percentage_point_difference'] is not None for p in relevant)
    dd_no_worse=all(p['drawdown_percentage_point_difference']>=0 for p in relevant if p['drawdown_percentage_point_difference'] is not None)
    policy_state='all_empty_unidentified' if all_empty else 'unknown_empty_reference_DD' if policy_nominal and dd_no_worse and not dd_identified else 'supported_pending_unknown_audit' if policy_nominal and dd_no_worse else 'unsupported'
    gates=information+[dict(kind='policy_package',nominal_pass=bool(policy_nominal and dd_no_worse and dd_identified),status=policy_state,
                           pure_stop_causal_claim=False)]
    return pairs,gates,indices,distributions


def read_table(binding):
    return pd.read_csv(io.BytesIO(ref.read_bound(binding)),compression='gzip',low_memory=False)


def validate_cash_manifests(narrow,fit,inputs):
    for manifest,schema in ((narrow,'stage070_narrow_labels_v1'),(fit,'stage071_settlement_narrow_fit_v1')):
        if manifest.get('schema')!=schema or manifest.get('status')!='completed' or manifest.get('mode')!='actual':
            raise ValueError('complete actual label/fit manifest required')
        if manifest.get('protocol',{}).get('sha256')!=kernel.PROTOCOL_SHA:
            raise ValueError('label/fit Stage069 protocol differs')
    if fit.get('actual_fit_calls_completed')!=12 or narrow.get('mother_rows')!=399252:
        raise ValueError('finite full-mother label/12fit budget changed')
    def same(a,b,role):
        if any(a.get(k)!=b.get(k) for k in ('path','bytes','sha256')):
            raise ValueError('manifest/auth binding mismatch '+role)
    same(fit['predictions'],inputs['predictions'],'predictions')
    same(narrow['labels_narrow'],inputs['narrow_labels'],'narrow_labels')
    for role in ('narrow_labels','wide_labels'):
        same(fit['input_bindings'][role],inputs[role],role)
    same(narrow['input_bindings']['wide_labels'],inputs['wide_labels'],'accepted049 wide_labels')
    terminal=json.loads(ref.read_bound(fit['terminal']))
    if (terminal.get('status')!='completed' or terminal.get('exit_code')!=0 or
        terminal.get('actual_fit_calls_completed')!=12 or terminal.get('native_source_queries')!=0 or terminal.get('new_cash_accounts')!=0):
        raise ValueError('071 terminal must complete12 fits with zero native/cash')
    terminal=json.loads(ref.read_bound(narrow['terminal']))
    if (terminal.get('status')!='completed' or terminal.get('exit_code')!=0 or
        terminal.get('completed_label_rows')!=399252 or terminal.get('native_source_queries')!=1 or terminal.get('new_cash_accounts')!=0):
        raise ValueError('070 labels terminal must complete399252 rows with one native/zero cash')


def execute(args):
    protocol,protocol_binding,authorization,authorization_binding=kernel.authorize(args,'cash')
    inputs=authorization['input_bindings']
    if not {'market_protocol','wide_labels','narrow_labels','narrow_manifest','fit_manifest','predictions'}.issubset(inputs):
        raise ValueError('cash requires complete policy labels and071 prediction bindings')
    fit=json.loads(ref.read_bound(inputs['fit_manifest']))
    narrow=json.loads(ref.read_bound(inputs['narrow_manifest']))
    validate_cash_manifests(narrow,fit,inputs)
    labels={p:read_table(inputs['wide_labels' if p=='WIDE' else 'narrow_labels']) for p in POLICIES}
    for field in SIGNAL_FIELDS:
        if not labels['WIDE'][field].fillna('').equals(labels['NARROW'][field].fillna('')):
            raise ValueError('policies must share identical causal u inputs '+field)
    predictions=read_table(inputs['predictions'])
    if len(predictions)!=966084 or set(zip(predictions.policy,predictions.arm))!={(p,a) for p in POLICIES for a in ARMS}:
        raise ValueError('six groups of full forward scores required')
    signals={key:make_signals(labels[key[0]],predictions,*key) for key in ((p,a) for p in POLICIES for a in ARMS)}
    if any(len(l)!=399252 or l.product_id.nunique()!=98 for l in labels.values()):
        raise ValueError('complete399252 mother/98 products required')
    if ref.NATIVE_QUERIES:raise ValueError('process already consumed native input')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    began,clock=datetime.now(timezone.utc).isoformat(),time.monotonic()
    source_before=kernel.source_bundle('cash')
    status,error,accounts_started,accounts_completed='failed',None,0,0
    ref.write_json(out/'actual_started.json',dict(status='started',stage='cash',started_at=began,source_bundle=source_before,
                   authorization=authorization_binding,protocol=protocol_binding,fixture=False))
    try:
        panel,market,dates,economics,_,receipt,market_protocol=kernel.load_market_bridge(authorization)
        ref.write_json(out/'source_read_receipt.json',receipt)
        summaries={};daily={};reports={};family_tables=[];all_budgets=[];native_selections={}
        families=sorted(panel.product_id.map(ref.family).unique())
        for policy in POLICIES:
            for arm in ARMS:
                sig=signals[(policy,arm)]
                prepared=ref.organize(sig)
                for window in protocol['finance']['windows']:
                    start=int(np.searchsorted(dates,window['start']));end=int(np.searchsorted(dates,window['end']))
                    if dates[end]!=window['end']:raise ValueError('scope end absent from source calendar')
                    for cost in ('base','stress'):
                        name=f"{policy}_{arm}_{window['id']}_{cost}"
                        accounts_started+=1
                        book=kernel.run_cash_account(sig,market,dates,economics,cost,name,start,end,prepared=prepared,policy=policy)
                        accounts_completed+=1
                        account_dir=out/name;account_dir.mkdir()
                        for file,key in [('fills','fills'),('reservations','budgets'),('daily','daily'),('positions','position_days'),('closed','closed_episodes'),('open','open_episodes')]:
                            ref.write_table(account_dir/(file+'.csv.gz'),book[key],EMPTY_COLUMNS.get(key,[]))
                        rejections=[r for r in book['budgets'] if r.get('D_qty',0)==0]
                        ref.write_table(account_dir/'rejections.csv.gz',rejections,EMPTY_COLUMNS['budgets'])
                        summary,report,family_year=cash_report(book,families,ref.INITIAL)
                        key=(policy,arm,window['id'],cost)
                        summaries[key]=summary;daily[key]=pd.DataFrame(book['daily']);reports[name]=report
                        family_tables.append(family_year.assign(policy=policy,arm=arm,window=window['id'],cost=cost))
                        all_budgets.extend(book['budgets'])
                        audit_roots={r['root_id']:r for r in book['closed_episodes']+book['open_episodes']}
                        for fill in book['fills']:
                            if fill['side']!='SELL':continue
                            root=audit_roots.get(fill['root_id'])
                            if root is None:raise AssertionError('native audit fill root absent')
                            reason=fill['reason']
                            kind=('entry_day_stop' if reason in ('stop_boundary','gap_stop') and fill['date']==root['entry_date']
                                  else 'later_boundary' if reason=='stop_boundary' else 'gap_stop' if reason=='gap_stop'
                                  else 'old_epoch_exit' if reason=='liquidity_reference_changed' else 'lifecycle_exit' if reason=='lifecycle_exit'
                                  else 'deferred_exit' if reason=='research_deferred_liquidation' else None)
                            if kind is not None:
                                native_selections.setdefault((policy,kind),dict(kind=kind,policy=policy,event_id=fill['event_id'],date=fill['date'],account=name,fill=fill))
                        for position in book['position_days']:
                            if position['mark_state']=='stale':
                                native_selections.setdefault((policy,'missing'),dict(kind='missing',policy=policy,event_id=position['event_id'],date=position['date'],account=name,position=position))
                        ref.write_json(account_dir/'summary.json',kernel.safe(summary))
                        print(json.dumps(dict(phase='account_complete',account=name,completed=accounts_completed,elapsed_seconds=time.monotonic()-clock)),flush=True)
        if accounts_started!=24 or accounts_completed!=24 or ref.NATIVE_QUERIES!=1:
            raise AssertionError('finite cash/native budget changed')
        pairs,gates,indices,distributions=comparisons_and_gates(summaries,daily,protocol)
        for window,index in indices.items():np.save(out/(window+'_bootstrap_indices.npy'),index,allow_pickle=False)
        ref.write_table(out/'comparisons.csv.gz',pairs,[])
        ref.write_table(out/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        ref.write_table(out/'family_year_including_zero.csv.gz',pd.concat(family_tables,ignore_index=True),[])
        ref.write_table(out/'annual_slices.csv.gz',[dict(account=a,**r) for a,report in reports.items() for r in report['annual_slices']],[])
        ref.write_json(out/'diagnostics.json',kernel.safe(reports))
        kernel.export_native_cases(out/'finite_native_cases.json.gz',list(native_selections.values()),labels,panel,market,dates,economics)
        # Any historical unknown exposure needs an independent unbounded-risk review.
        any_stale=any(report['stale_days']>0 for report in reports.values())
        for gate in gates:
            if gate['status']=='supported_pending_unknown_audit':gate['status']='unknown_historical_stale' if any_stale else 'supported_research_model_only'
        ref.write_json(out/'continuation_gates.json',kernel.safe(dict(gates=gates,any_historical_stale=any_stale,goal_complete=False,
                       independent_actual_review_required=True,no_automatic_promotion=True)))
        tick=[]
        for policy,l in labels.items():
            ready=l.label_history_ready20.eq(1)
            tick.append(dict(policy=policy,ready_rows=int(ready.sum()),known_tick_rows=int((ready&l.tick_size.gt(0)).sum()),
                             stop_distance_below_tick=int((ready&l.R0_points.lt(l.tick_size)).sum())))
        ref.write_json(out/'budget_and_tick_disclosure.json',kernel.safe(dict(policy_tick=tick,
                       risk_unit='k*N*M+roundtrip_fee+two_adverse_slippages; frozen actual D risk while held',
                       budget_rules='u joint fractional reserve/floor; D own cap reduce only; no reallocation or same-day sale funding',
                       continuous_boundary_not_necessarily_tick_order=True,no_gap_loss_cap=True,
                       reservation_records=len(all_budgets))))
        ref.assert_db_binding(market_protocol['database'])
        if kernel.source_bundle('cash')!=source_before:raise ValueError('source changed during cash actual')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='cash',started_at=began,
                       finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
                       exit_code=0 if status=='completed' else 1,error=error,native_source_queries=ref.NATIVE_QUERIES,
                       cash_accounts_started=accounts_started,new_cash_accounts=accounts_completed,actual_model_fit_calls=0,
                       downloads=0,whole_database_hashes=0,fixture=False,python=sys.executable))
    artifacts=[dict(ref.file_binding(p),raw_ohlc=p.name=='finite_native_cases.json.gz',reproducibility_required=p.name!='finite_native_cases.json.gz') for p in sorted(out.rglob('*')) if p.is_file()]
    ref.write_json(out/'manifest.json',dict(schema='stage070_narrow_policy_cash_v1',status=status,mode='actual',
                   protocol=protocol_binding,authorization=authorization_binding,source_bundle=source_before,input_bindings=inputs,
                   terminal=ref.file_binding(out/'actual_terminal.json'),artifacts=artifacts,native_source_queries=ref.NATIVE_QUERIES,
                   new_cash_accounts=accounts_completed,actual_model_fit_calls=0,goal_complete=False,production_qualified=False))
    return dict(status=status,output=str(out),native_source_queries=ref.NATIVE_QUERIES,new_cash_accounts=accounts_completed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
