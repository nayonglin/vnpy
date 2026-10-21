"""Single root-authorized096 review: saved ID/181 arithmetic, zero new queries."""
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,io,json,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from stage096_cash_adapter import bound,compare,csv,numeric,review_account,ERRORS
from stage096_fit_checks import load_labels,check_fits
from stage096_alignment_checks import review_alignment
from stage096_native_checks import review_native
from stage096_cash_diagnostics import review_cash_diagnostics

LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='580c59d77964b27372570b2d48e197ce7a75f5edd77dac0a9aa5e42548d3a736'
EXPECTED={
 'prepare':('outputs/stage093_sequence_alignment/experiment/manifest.json','4824bb1c88e9eea6778a35f6a5b85fc5954486701b63dc9fef1bd446692612f4','0c111545d97a32595d791e7b0401795a00e43071b637ea56d2cd1e3f7d8918c1'),
 'fit':('outputs/stage094_crossday_order_fit/experiment/manifest.json','8d4d26d4c1e7b6a0c1aad2f25e11d9b63c4c8aeea02ded6a5b64f3dc82e96532','7f4770ef168578d7fc8c42f9e3a2b69cee24b2100677129e6d0c14d82fdc5d00'),
 'cash':('outputs/stage095_order_bag_cash/cash/manifest.json','8e6a43cd0b846a8653b615dbe66e291d3c6051471bc94ce2801e5231368334de','c3aec1194bf7b28f26d42753350037eebaaaf8805f7a9daf7ded7e94f0fa2cf2')}
MODULES=['stage096_independent_review.py','stage096_alignment_checks.py','stage096_feature_math.py','stage096_fit_checks.py','stage096_cash_adapter.py','stage096_cash_core.py','stage096_native_checks.py','stage096_cash_diagnostics.py']

def bind(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def safe(v):
    if isinstance(v,dict):return {str(k):safe(x)for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [safe(x)for x in v]
    if isinstance(v,np.generic):return v.item()
    return v

def write(path,v):
    with path.open('x')as stream:json.dump(safe(v),stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')

def progress(out,name,v):
    write(out/(name+'.json'),v);print(json.dumps(dict(phase=name,completed=True)),flush=True)

def same(a,b):return all(a[k]==b[k]for k in ('path','bytes','sha256'))

def closure():
    allm={};bindings={}
    for role,(path,sha,terminal_sha)in EXPECTED.items():
        mb=bind(LINE/path);assert mb['sha256']==sha,(role,'manifest')
        m=json.loads(bound(mb));assert m['status']=='completed'and m['mode']=='actual'
        assert m['schema']=={'prepare':'stage093_sequence_alignment_v1','fit':'stage094_crossday_order_fit_v1','cash':'stage095_order_bag_cash_v1'}[role]
        assert m['protocol']['sha256']==PROTOCOL_SHA;bound(m['protocol'])
        assert m['terminal']['sha256']==terminal_sha;terminal=json.loads(bound(m['terminal']))
        assert terminal['status']=='completed'and terminal['exit_code']==0
        requirements={
          'prepare':dict(completed_projection_rows=399252,native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,whole_database_hashes=0),
          'fit':dict(actual_fit_calls_attempted=12,actual_fit_calls_completed=12,native_source_queries=0,cash_replays=0,new_labels=0,downloads=0,whole_database_hashes=0),
          'cash':dict(cash_accounts_started=8,new_cash_accounts=8,native_source_queries=1,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,old_baseline_replays=0)}[role]
        for k,v in requirements.items():assert terminal[k]==v,(role,k)
        auth=json.loads(bound(m['authorization']))
        for k,v in dict(schema='stage092_exact_root_authorization_v1',authorized_by='root',stage=role,exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(Path(mb['path']).parent)).items():assert auth[k]==v,(role,'authorization',k)
        assert sorted(auth['source_bundle'],key=lambda x:x['path'])==sorted(m['source_bundle'],key=lambda x:x['path'])
        for b in m['source_bundle']:bound(b)
        if role!='prepare':assert auth['input_bindings']==m['input_bindings']
        artifacts=list(m['artifacts'].values())if isinstance(m['artifacts'],dict)else m['artifacts'];seen=set()
        for b in artifacts:
            assert b['path']not in seen and str(Path(b['path']).resolve()).startswith(str(Path(mb['path']).parent)+'/');seen.add(b['path']);bound(b)
        allm[role]=m;bindings[role]=dict(manifest=mb,terminal=m['terminal'],authorization=m['authorization'],artifacts_verified=len(seen),source_bundle=m['source_bundle'])
    s,f,c=[allm[k]for k in ('prepare','fit','cash')];p=json.loads(bound(s['protocol']))
    assert same(f['input_bindings']['prepare_manifest'],bindings['prepare']['manifest'])and same(f['input_bindings']['alignment'],s['alignment'])and same(f['input_bindings']['prepare_terminal'],s['terminal'])
    assert same(c['input_bindings']['fit_manifest'],bindings['fit']['manifest'])and same(c['input_bindings']['predictions_main'],f['predictions_main'])and same(c['input_bindings']['held_diagnostic'],f['held_diagnostic'])
    for role in ('narrow_labels','narrow_manifest'):
        assert same(f['input_bindings'][role],p['input_roles'][role])and same(c['input_bindings'][role],p['input_roles'][role])
    assert same(s['input_bindings']['narrow_labels'],p['input_roles']['narrow_labels'])and same(s['input_bindings']['old_event_ids'],p['old_event_ids'])
    assert same(f['input_bindings']['tensor'],p['tensor'])and same(c['input_bindings']['market_protocol'],p['market_protocol'])
    assert c['bootstrap_indices']==p['bootstrap_indices']
    for name in ('protocol_preflight.json','source_preflight.json','code_preflight.json'):bound(bind(LINE/'outputs/stage096_order_bag_review'/name))
    return allm,bindings,p

def extras(directory,signals):
    budgets=csv(directory/'reservations.csv.gz');reject=csv(directory/'rejections.csv.gz')
    if len(budgets):
        expected=budgets.loc[pd.to_numeric(budgets.D_qty).eq(0)].set_index('budget_id').sort_index();saved=reject.set_index('budget_id').sort_index().reindex(columns=expected.columns,fill_value='')
        assert expected.equals(saved),'rejections altered or omitted'
    else:assert len(reject)==0
    fills=csv(directory/'fills.csv.gz');numeric(fills,['reference_price','qty','fee','realized_gross'])
    closed=csv(directory/'closed.csv.gz');opened=csv(directory/'open.csv.gz');roots=pd.concat([closed,opened],ignore_index=True).set_index('root_id')
    if len(roots):
        compare(pd.to_numeric(roots.SL0),pd.to_numeric(roots.entry_reference)-.25*np.array([float(signals.loc[e,'N_u'])for e in roots.event_id]),'all_roots_initial_stop')
    diagnostics=json.loads((directory.parent/'diagnostics.json').read_text())[directory.name];expected=[]
    for r in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].itertuples():
        root=roots.loc[r.root_id];loss=(float(root.entry_reference)-r.reference_price)/(.25*float(signals.loc[r.event_id,'N_u']))
        expected.append(dict(event_id=r.event_id,date=r.date,gross_loss_R=loss,qty=r.qty,realized_gross=r.realized_gross,exit_fee=r.fee))
    assert len(diagnostics['gap_stop_fills'])==len(expected)
    for a,b in zip(diagnostics['gap_stop_fills'],expected):
        assert a['event_id']==b['event_id']and a['date']==b['date']
        for k in ('gross_loss_R','qty','realized_gross','exit_fee'):compare(a[k],b[k],'gap_'+k)
    assert diagnostics['gap_stop_exceeds_1R']==sum(x['gross_loss_R']>1 for x in expected)
    return dict(rejections_preserved=len(reject),all_root_initial_stops_checked=len(roots),gap_stops=len(expected),gap_stops_gross_over1R=sum(x['gross_loss_R']>1 for x in expected))

def attribution(predictions,cash):
    rows=[];signatures=[];main=predictions.loc[predictions.scope.eq('main')]
    for cutoff,g in main.groupby('cutoff',sort=True):
        a=g.loc[g.arm.eq('BAG')].set_index('event_id');b=g.loc[g.arm.eq('ORDER')].set_index('event_id').reindex(a.index);d=b.score-a.score
        rows.append(dict(cutoff=cutoff,events=len(a),bag_selected=int(a.selected.sum()),order_selected=int(b.selected.sum()),action_disagreements=int(b.selected.ne(a.selected).sum()),mean_score_difference=float(d.mean()),max_abs_score_difference=float(abs(d).max())))
    cols=['event_id','date','side','qty','reference_price','fill_price','fee','slippage','reason']
    for w in ('primary_2020','cold_2023'):
        for cost in ('base','stress'):
            a=csv(cash/f'NARROW_BAG_{w}_{cost}'/'fills.csv.gz')[cols].reset_index(drop=True);b=csv(cash/f'NARROW_ORDER_{w}_{cost}'/'fills.csv.gz')[cols].reset_index(drop=True)
            signatures.append(dict(window=w,cost=cost,bag_fills=len(a),order_fills=len(b),economic_fill_signatures_identical=a.equals(b)))
    return dict(main_information_actions=rows,cash_fill_signatures=signatures)

def review(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);clock=time.monotonic();started=datetime.now(timezone.utc).isoformat();sources=[bind(LINE/'tools'/n)for n in MODULES];status='failed';error=None
    write(out/'actual_started.json',dict(started_at=started,review_startups=1,not_strategy_run=True,sources=sources,expected_final_manifests=EXPECTED,new_SQL=0))
    snap=out/'checker_snapshot';snap.mkdir()
    for b in sources:(snap/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
    try:
        manifests,bindings,protocol=closure();progress(out,'final_input_closure',bindings)
        source,fit,cashmanifest=[manifests[k]for k in ('prepare','fit','cash')]
        bridge=json.loads(bound(protocol['market_protocol']));dates=np.load(io.BytesIO(bound(bridge['calendar'])),allow_pickle=False)
        calendar=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8]for v in dates]if dates.dtype.kind in'iu'else dates.astype('datetime64[D]').astype(str).tolist()
        assert len(calendar)==5587 and calendar==sorted(set(calendar));economics=json.loads(bound(bridge['economic_projection']))['instruments']
        labels=load_labels(protocol['input_roles']['narrow_labels']);assert np.array_equal(labels.u_index,labels.u_date.map({d:i for i,d in enumerate(calendar)}))
        index,tensor,alignment_report=review_alignment(source,labels,protocol);progress(out,'all399252_ID_alignment',alignment_report)
        predictions,held,signal_report,signal_states,models=check_fits(fit,labels,index,tensor);progress(out,'all12_models_644056_predictions',models)
        cash=Path(bindings['cash']['manifest']['path']).parent;accounts=[];summaries={}
        labels['planned_execution_date']=[calendar[int(u)+1]if int(u)+1<len(calendar)else''for u in labels.u_index]
        for arm in ('BAG','ORDER'):
            p=predictions.loc[predictions.scope.eq('main')&predictions.arm.eq(arm),['event_id','score']]
            signals=labels.merge(p,on='event_id',how='left',validate='one_to_one',sort=False);signals['potential']=(signals.label_history_ready20.eq(1)&np.isfinite(signals.score)&signals.score.gt(0)).astype(int);signals=signals.set_index('event_id',drop=False)
            for window in protocol['finance']['windows']:
                for cost in ('base','stress'):
                    name=f"NARROW_{arm}_{window['id']}_{cost}";directory=cash/name
                    checked=review_account(directory,cost,window,protocol,signals,economics,calendar,.25);checked['additional_checks']=extras(directory,signals);accounts.append(checked);summaries[name]=checked['summary']
        assert len(accounts)==8;progress(out,'all8_cash_ledgers_and_budgets',accounts)
        native=next(b for b in cashmanifest['artifacts']if Path(b['path']).name=='finite_native_cases.json.gz');progress(out,'finite_native_cash_cases',review_native(native,'cash'))
        diagnostics=review_cash_diagnostics(cash,summaries,protocol,held,signal_report=signal_report,signal_states=signal_states)
        disclosure=json.loads((cash/'budget_and_tick_disclosure.json').read_text());ready=labels.label_history_ready20.eq(1)
        assert disclosure['ready_rows']==int(ready.sum())and disclosure['known_tick_rows']==int((ready&labels.tick_size.gt(0)).sum())and disclosure['stop_distance_below_tick']==int((ready&labels.R0_points.lt(labels.tick_size)).sum())
        assert disclosure['reservation_records']==sum(a['budgets_checked']['rows']for a in accounts)
        progress(out,'all_CI_gate_unknown_and_attribution',dict(diagnostics=diagnostics,signal_report=signal_report,attribution=attribution(predictions,cash)))
        assert sources==[bind(LINE/'tools'/n)for n in MODULES]
        write(out/'review_receipt.json',dict(schema='stage096_independent_actual_review_v1',completed=True,C=0,I=0,M=0,review_startups=1,full_review_completions=1,input_closure=bindings,checker_sources=sources,alignment_review=alignment_report,model_review=models,cash_accounts=accounts,diagnostics=diagnostics,main_signal_identification=signal_report,numeric_max_errors=ERRORS,execution=dict(new_SQL=0,research_fits=0,research_cash=0,full_native_strategy_replay=0,old_model_rechecks=0,old_cleaner_rebuild=0,whole_DB_H5_hashes=0,downloads=0,old_suite=0),arithmetic_accepted=True,fixed_layout_supported=diagnostics['continuation_gate']['status']=='supported_research_model_only',alpha_or_COMMON_superiority_established=False,goal_complete=False))
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';write(out/'failure.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        write(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed'else 1,error=error,review_startups=1,full_review_completions=int(status=='completed'),research_runs=0,new_SQL=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);review(p.parse_args().output)
