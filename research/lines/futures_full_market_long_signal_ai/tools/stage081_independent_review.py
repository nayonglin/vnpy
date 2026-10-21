"""One saved-artifact review of fixed080; no author imports or strategy replay."""
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key]='1'
import argparse,hashlib,io,json,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from stage081_cash_adapter import bound,compare,csv,numeric,review_account,ERRORS
from stage081_native_checks import review_native
from stage081_cash_diagnostics import review_cash_diagnostics

LINE=Path(__file__).resolve().parents[1]
SOURCE_SHA='53234b3afa3e7e8c63aa676c8c183f13e6e384bed72a5208d40e602bd84755db'
PROTOCOL_SHA='421722dd73ba0b4c43656b9439766afcf80c723b095160ace4742114050afce3'
MODULES=['stage081_independent_review.py','stage081_cash_adapter.py','stage081_cash_core.py','stage081_native_checks.py','stage081_cash_diagnostics.py']

def bind(path):
    p=Path(path).resolve();b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def safe(v):
    if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [safe(x) for x in v]
    if isinstance(v,np.generic):return v.item()
    return v

def write(path,v):
    with path.open('x')as f:json.dump(safe(v),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def progress(out,name,v):
    write(out/(name+'.json'),v);print(json.dumps(dict(phase=name,completed=True)),flush=True)

def closure(args):
    mb=bind(args.manifest);assert mb['sha256']==args.manifest_sha256
    m=json.loads(bound(mb));assert m['schema']=='stage080_one_lot_prefilter_cash_v1' and m['status']=='completed' and m['mode']=='actual'
    assert m['new_cash_accounts']==4 and m['native_source_queries']==1 and m['actual_model_fit_calls']==m['new_labels']==m['baseline_cash_replays']==0
    assert m['protocol']['sha256']==PROTOCOL_SHA
    protocol=json.loads(bound(m['protocol']));assert m['input_bindings']==protocol['inputs'] and m['baselines']==protocol['baselines'] and m['bootstrap_indices']==protocol['bootstrap_indices']
    bound(protocol['plan']);bound(protocol['support_manifest']);bound(protocol['support_review'])
    terminal=json.loads(bound(m['terminal']));assert m['terminal']['sha256']==args.terminal_sha256
    for k,v in dict(status='completed',exit_code=0,fixture=False,native_source_queries=1,cash_accounts_started=4,new_cash_accounts=4,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,baseline_cash_replays=0).items():assert terminal[k]==v,(k,terminal.get(k))
    auth=json.loads(bound(m['authorization']))
    for k,v in dict(schema='stage079_exact_root_authorization_v1',authorized_by='root',stage='cash',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(Path(args.manifest).resolve().parent)).items():assert auth[k]==v,('authorization',k)
    assert auth['source_bundle']==m['source_bundle']
    for b in m['source_bundle']:bound(b)
    assert next(b for b in m['source_bundle']if Path(b['path']).name=='stage080_one_lot_prefilter.py')['sha256']==SOURCE_SHA
    for name in ('fit_manifest','narrow_manifest','baseline_cash_manifest'):bound(protocol['inputs'][name])
    paths=set()
    for a in m['artifacts']:
        assert a['path'] not in paths;paths.add(a['path']);bound(a)
    assert all(str(Path(x).resolve()).startswith(str(Path(args.manifest).resolve().parent)+'/') for x in paths)
    return m,protocol,dict(manifest=mb,terminal=m['terminal'],authorization=m['authorization'],artifacts_verified=len(paths),source_bundle=m['source_bundle'])

def load_signals(protocol,calendar):
    # Inherit the accepted scores; read only causal fields, never Y/known dates
    # or future exit state, and do not recompute the accepted models.
    fields=['event_id','product_id','family_id','u_date','u_index','reference_epoch','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index']
    raw=bound(protocol['inputs']['narrow_labels'])
    base=pd.read_csv(io.BytesIO(raw),compression='gzip',usecols=fields)
    raw=bound(protocol['inputs']['predictions'])
    chunks=pd.read_csv(io.BytesIO(raw),compression='gzip',usecols=['event_id','policy','arm','score'],chunksize=200000)
    chosen=pd.concat([g.loc[g.policy.eq('NARROW')&g.arm.eq('COMMON'),['event_id','score']]for g in chunks],ignore_index=True)
    assert len(base)==399252 and len(chosen)==161014 and base.event_id.is_unique and chosen.event_id.is_unique
    assert set(chosen.event_id)==set(base.loc[base.u_date.ge('2020-01-01'),'event_id'])
    base.reference_epoch=base.reference_epoch.fillna('')
    sig=base.merge(chosen,on='event_id',how='left',validate='one_to_one',sort=False)
    sig['potential']=(sig.label_history_ready20.eq(1)&sig.score.gt(0)).astype(int)
    sig['planned_execution_date']=[calendar[int(u)+1] if int(u)+1<len(calendar) else ''for u in sig.u_index]
    return sig.set_index('event_id',drop=False),dict(mother_rows=len(base),inherited_score_rows=len(chosen),selected=int(sig.potential.sum()),models_recomputed=0,predictions_reverified=0,fields_read=fields,labels_future_fields_read=False)

def extra_account(directory,signals):
    reservations=csv(directory/'reservations.csv.gz');rejections=csv(directory/'rejections.csv.gz')
    assert set(rejections.budget_id)==set(reservations.loc[pd.to_numeric(reservations.D_qty).eq(0),'budget_id'])
    left=reservations.loc[reservations.budget_id.isin(rejections.budget_id)].set_index('budget_id').sort_index()
    right=rejections.set_index('budget_id').sort_index().reindex(columns=left.columns,fill_value='');assert left.equals(right),'rejection rows changed'
    fills=csv(directory/'fills.csv.gz');numeric(fills,['reference_price','qty','realized_gross','fee'])
    positions=csv(directory/'positions.csv.gz');numeric(positions,['entry_reference','SL0','boundary_next','qty'])
    if len(positions):
        expected=[float(r.entry_reference)-.25*float(signals.loc[r.event_id,'N_u'])for r in positions.itertuples()]
        compare(positions.SL0,expected,'all_position_initial_stop')
        assert np.all(positions.boundary_next>=positions.SL0)
    diagnostics=json.loads((directory.parent/'diagnostics.json').read_text())[directory.name]
    closed=csv(directory/'closed.csv.gz');opened=csv(directory/'open.csv.gz');roots=pd.concat([closed,opened],ignore_index=True).set_index('root_id')
    expected=[]
    for r in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].itertuples():
        root=roots.loc[r.root_id];R0=.25*float(signals.loc[r.event_id,'N_u'])
        loss=(float(root.entry_reference)-r.reference_price)/R0
        expected.append(dict(event_id=r.event_id,date=r.date,gross_loss_R=loss,qty=r.qty,realized_gross=r.realized_gross,exit_fee=r.fee))
    actual=diagnostics['gap_stop_fills'];assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        assert a['event_id']==b['event_id'] and a['date']==b['date']
        for key in ('gross_loss_R','qty','realized_gross','exit_fee'):compare(a[key],b[key],'all_gap_'+key)
    assert diagnostics['gap_stop_exceeds_1R']==sum(x['gross_loss_R']>1 for x in expected)
    return dict(rejections_preserved=len(rejections),position_initial_stops_checked=len(positions),gap_stop_fills=len(expected),gap_stop_exceeds_1R=sum(x['gross_loss_R']>1 for x in expected))

def review(args):
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    sources=[bind(LINE/'tools'/n)for n in MODULES];started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();status='failed';error=None
    write(out/'actual_started.json',dict(started_at=started,review_startups=1,not_a_strategy_run=True,sources=sources,command=vars(args)))
    snapshots=out/'checker_snapshot';snapshots.mkdir()
    for b in sources:(snapshots/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
    try:
        m,protocol,bindings=closure(args);progress(out,'final_input_closure',bindings)
        bridge=json.loads(bound(protocol['inputs']['market_protocol']))
        dates=np.load(io.BytesIO(bound(bridge['calendar'])),allow_pickle=False)
        calendar=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8]for v in dates]if dates.dtype.kind in 'iu'else dates.astype('datetime64[D]').astype(str).tolist()
        economics=json.loads(bound(bridge['economic_projection']))['instruments']
        signals,signalreport=load_signals(protocol,calendar);progress(out,'accepted_signal_inputs',signalreport)
        cash=Path(args.manifest).resolve().parent;accounts=[];summaries={};urows=[]
        for window in protocol['finance']['windows']:
            for cost in protocol['finance']['costs']:
                name=f"NARROW_COMMON_{window['id']}_{cost}";directory=cash/name
                checked=review_account(directory,cost,window,protocol,signals,economics,calendar,.25)
                checked['additional_checks']=extra_account(directory,signals)
                for r in checked['budgets_checked'].pop('u_summary'):urows.append(dict(window=window['id'],cost=cost,**r))
                accounts.append(checked);summaries[name]=checked['summary']
        assert len(accounts)==4;progress(out,'all_four_ledgers_and_budgets',accounts)
        observed=pd.read_csv(cash/'prefilter_by_u.csv.gz').sort_values(['window','cost','u_date']).reset_index(drop=True)
        expected=pd.DataFrame(urows).sort_values(['window','cost','u_date']).reset_index(drop=True)
        assert len(observed)==len(expected) and observed[['window','cost','u_date']].equals(expected[['window','cost','u_date']])
        for col in expected.columns[3:]:compare(observed[col],expected[col],'prefilter_by_u_'+col)
        prefilter=json.loads((cash/'prefilter_summary.json').read_text())
        for key,value in dict(account_rows=len(expected),candidate_total=int(expected.candidates.sum()),prefiltered_candidate_total=int(expected.prefiltered_candidates.sum()),account_u_with_prefilter=int(expected.prefiltered_candidates.gt(0).sum()),same_u_qty_cap_gain=float(expected.same_u_qty_cap_gain.sum())).items():compare(prefilter[key],value,'prefilter_summary_'+key)
        assert prefilter['no_baseline_cash_replay'] is True and prefilter['no_reallocation_or_score_ordering'] is True
        progress(out,'prefilter_aggregates',dict(rows=len(expected),prefiltered_candidate_total=prefilter['prefiltered_candidate_total'],same_u_qty_cap_gain=prefilter['same_u_qty_cap_gain']))
        native=next(a for a in m['artifacts']if Path(a['path']).name=='finite_native_cases.json.gz')
        progress(out,'finite_native_cases',review_native(native,'cash'))
        diagnostics=review_cash_diagnostics(cash,summaries,protocol);progress(out,'paired_CI_and_diagnostics',diagnostics)
        assert sources==[bind(LINE/'tools'/n)for n in MODULES]
        receipt=dict(schema='stage081_independent_actual_review_v1',completed=True,C=0,I=0,M=0,review_startups=1,full_review_completions=1,input_closure=bindings,checker_sources=sources,signal_input_inheritance=signalreport,cash_accounts_reviewed=4,accounts=accounts,prefilter_summary=prefilter,diagnostics=diagnostics,numeric_max_errors=ERRORS,execution=dict(research_fit=0,research_cash=0,SQL=0,downloads=0,old_fills_or_reservations_reads=0,full_native_replay=0,whole_DB_hashes=0),interpretation='saved research arithmetic checked; benefit only as frozen gate states, no alpha or full goal claim',goal_complete=False)
        write(out/'review_receipt.json',receipt);status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';write(out/'failure.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        write(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed'else 1,error=error,review_startups=1,full_review_completions=int(status=='completed'),research_runs=0,SQL=0))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('manifest','manifest-sha256','terminal-sha256','output'):p.add_argument('--'+n,required=True)
    review(p.parse_args())
