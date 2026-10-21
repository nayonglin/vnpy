"""Frozen673 historical extension: one new main model and two continuous books.

Accepted130/156/157 sources remain unchanged. Import and synthetic fixtures do
no fit, SQL or cash work. Only root may launch the exact authorized actual once.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage673_common52_2015_extension_protocol/protocol.json'
PROTOCOL_SHA='4d27ee6c708de39d029e6eee87f9b6d0db81aefa66ee271802f486e7fb97aa13'
START='2015-01-01';END='2026-10-16';OLD_START='2020-01-01'
OUTPUT=LINE/'outputs/stage675_common52_2015_extension/actual_run1'
INPUT_ROLES={'dataset_manifest','dataset_terminal','actions','common','mothers','fit_manifest','child_scores',
    'market_protocol','native_cache_manifest','native_cache','execution_protocol','accepted_cash_manifest',
    'choice_manifest','accepted_stage156_choices'}

def load(name,identity):
    s=importlib.util.spec_from_file_location(identity,TOOLS/name)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

fit=load('stage130_contract_choice_fit.py','extension675_fit130')
selector=load('stage156_voluntary_choices.py','extension675_selector156')
cash=load('stage157_voluntary_cash.py','extension675_cash157')
ref=cash.ref

def source_bundle():
    paths={b['path'] for b in fit.source_bundle()+cash.source_bundle()}
    paths.update(str(TOOLS/n) for n in ('stage156_voluntary_choices.py','test_stage156_voluntary_choices.py',
        'stage675_common52_2015_extension.py','test_stage675_common52_2015_extension.py'))
    return sorted((ref.file_binding(p) for p in paths),key=lambda b:b['path'])

def cutoff_for(day):
    if not START<=day<=END:raise ValueError('date outside fixed2015 extension')
    return START if day<OLD_START else OLD_START if day<'2023-01-01' else '2023-01-01'

def validate_score_schedule(scores):
    if set(scores.scope)!={'main'}:raise ValueError('main only score schedule required')
    if scores.action_id.duplicated().any() or scores.sequence_index.duplicated().any():raise ValueError('duplicate score identity')
    expected=scores.u_date.map(cutoff_for)
    if not scores.cutoff.eq(expected).all():raise ValueError('score cutoff violates fixed three era schedule')
    if not np.isfinite(scores.score.to_numpy(float)).all():raise ValueError('nonfinite prospective score')

def training_support(actions,mothers):
    train,pred,parent=fit.fold_slices(actions,mothers,START,OLD_START,'main')
    if not train.u_date.lt(START).all() or not train.label_known_date.lt(START).all():raise ValueError('two-clock mature training violated')
    return train,pred,parent

def validate_dataset_arrays(a,m,common,full=True):
    if full and (len(a)!=1552456 or len(m)!=399252 or m.product_id.nunique()!=98 or m.family_id.nunique()!=95):raise ValueError('full129 source domain required')
    if m.event_id.duplicated().any() or not np.array_equal(m.sequence_index,np.arange(len(m))):raise ValueError('full mother identity mismatch')
    if (a.action_id.duplicated().any() or not np.array_equal(a.sequence_index,np.arange(len(a)))
        or not a.sequence_index.eq(a.action_sequence_index).all() or not a.event_id.eq(a.action_id).all()
        or not a.reference_epoch.eq(a.actual_epoch).all()):raise ValueError('action alias identity mismatch')
    if not a.u_action_eligible.isin([0,1]).all():raise ValueError('binary action eligibility required')
    idx=a.mother_sequence_index.to_numpy(np.int64)
    if (idx<0).any() or (idx>=len(m)).any() or not np.array_equal(a.mother_event_id.to_numpy(),m.event_id.to_numpy()[idx]):raise ValueError('parent action identity mismatch')
    for c in ('product_id','family_id','u_date','u_index'):
        if not np.array_equal(a[c].to_numpy(),m[c].to_numpy()[idx]):raise ValueError('parent action '+c+' mismatch')
    if common.shape!=(len(a),26):raise ValueError('COMMON shape mismatch')

def rows(frame,columns):
    return (dict(zip(columns,r)) for r in frame[columns].itertuples(index=False,name=None))

def select_choices(mothers,scores,calendar,sample_end,audit_sink=None):
    validate_score_schedule(scores)
    result=selector.select_full_pool(mothers.to_dict('records'),rows(scores,selector.SCORE_FIELDS),calendar,sample_end,audit_sink,strict_cutoff=False)
    # Original156 writes its old2020/2023 metadata even with strict=False.
    # Only the already validated fixed schedule is adapted; scores/selection stay unchanged.
    for c in result['choices']:c['cutoff']=cutoff_for(c['u_date'])
    choices=result['choices'];summary=result['summary']
    summary['parents_per_cutoff']=dict(Counter(c['cutoff'] for c in choices))
    summary['selected_per_cutoff']=dict(Counter(c['cutoff'] for c in choices if c['selected']))
    summary['old_selected_per_cutoff']=dict(Counter(c['cutoff'] for c in choices if c['old_chosen_action_id']))
    differences=Counter()
    for c in choices:
        old,new=c['old_chosen_action_id'],c['chosen_action_id']
        differences[(c['cutoff'],'unchanged' if old==new else 'newly_selected' if not old else 'removed' if not new else 'different_action')]+=1
    summary['selection_differences']=[dict(cutoff=k[0],state=k[1],parents=v) for k,v in sorted(differences.items())]
    return result

def check_overlap(choices,accepted):
    new=choices.loc[choices.u_date.ge(OLD_START)].reset_index(drop=True)
    old=accepted.reset_index(drop=True)
    fields=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch',
        'selected','chosen_action_id','chosen_action_sequence_index','chosen_epoch','anchor_epoch','cutoff','selection_state']
    if len(new)!=len(old):raise ValueError('old2020+ overlap parent count differs')
    for c in fields:
        if new[c].fillna('').astype(str).tolist()!=old[c].fillna('').astype(str).tolist():raise ValueError('old2020+ overlap differs '+c)
    if not np.allclose(pd.to_numeric(new.score).to_numpy(float),pd.to_numeric(old.score).to_numpy(float),rtol=0,atol=0,equal_nan=True):raise ValueError('old2020+ overlap differs score')
    return dict(status='identical',parent_rows=len(old),selected_rows=int(new.selected.sum()),
        before_account_state_effects=True,old_cash_replayed=False)

def authorize(args):
    out=Path(args.output).resolve()
    if out!=OUTPUT.resolve() or out.exists():raise ValueError('unique fresh675 actual_run1 output required')
    pb=ref.file_binding(args.protocol)
    if pb['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('frozen673 protocol mismatch')
    protocol=json.loads(ref.read_bound(pb));ab=ref.file_binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization hash mismatch')
    auth=json.loads(ref.read_bound(ab))
    required=dict(schema='stage673_exact_root_authorization_v1',authorized_by='root',stage='extension_fit_cash',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle():raise ValueError('exact root source authorization required')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES or auth['input_bindings']!=protocol['inputs']:raise ValueError('exact14 frozen input bindings required')
    if protocol['limits']!=dict(new_fit=1,new_cash=2,old_refit=0,old_cash_replay=0):raise ValueError('fixed1fit2cash budget required')
    return protocol,pb,auth,ab

def execute(args):
    protocol,pb,auth,ab=authorize(args);inputs=auth['input_bindings'];out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False);began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();before=source_bundle()
    attempts=completed=started_cash=completed_cash=0;status='failed';error=None;read_paths=set();read_receipt=[]
    accounts=[];summaries=[];annual=[];family=[];reports={};curve=None;record=None
    def read(role,binding=None):
        b=inputs[role] if binding is None else binding
        if b['path'] in read_paths:raise ValueError('duplicate original payload read '+b['path'])
        raw=ref.read_bound(b);read_paths.add(b['path']);read_receipt.append(dict(role=role,**b,passes=1));return raw
    def table(role,columns=None):
        return pd.read_csv(io.BytesIO(read(role)),compression='gzip',dtype=str,keep_default_na=False,
            float_precision='round_trip',usecols=columns)
    def attempt(scope,cutoff):
        nonlocal attempts
        if attempts>=1 or (scope,cutoff)!=('main',START):raise ValueError('new fit budget exhausted')
        attempts+=1
        with (out/'fit_attempts.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,attempt=attempts))+'\n');f.flush()
    def complete(scope,cutoff):
        nonlocal completed
        completed+=1
        with (out/'fit_completed.jsonl').open('a') as f:f.write(json.dumps(dict(scope=scope,cutoff=cutoff,completed=completed))+'\n');f.flush()
    ref.write_json(out/'actual_started.json',dict(status='started',stage='extension_fit_cash',started_at=began,
        protocol=pb,authorization=ab,source_bundle=before,fixture=False))
    try:
        dataset=json.loads(read('dataset_manifest'));terminal=json.loads(read('dataset_terminal'))
        oldfit=json.loads(read('fit_manifest'));oldchoice=json.loads(read('choice_manifest'));oldcash=json.loads(read('accepted_cash_manifest'))
        execution=json.loads(read('execution_protocol'));market_protocol=json.loads(read('market_protocol'))
        meta=json.loads(read('native_cache_manifest'))
        if dataset.get('schema')!='stage129_contract_choice_dataset_v1' or dataset.get('status')!='completed' or terminal.get('status')!='completed':raise ValueError('completed129 dataset required')
        for role in ('actions','common','mothers'):cash.author.same_binding(dataset[role],inputs[role],'dataset '+role)
        cash.author.same_binding(dataset['terminal'],inputs['dataset_terminal'],'dataset terminal')
        if oldfit.get('actual_fit_calls_completed')!=6 or oldfit.get('status')!='completed':raise ValueError('accepted130 six-fit source required')
        cash.author.same_binding(oldfit['child_scores'],inputs['child_scores'],'130 child scores')
        cash.author.same_binding(oldchoice['artifacts']['choices_main'],inputs['accepted_stage156_choices'],'156 choices')
        cash.author.same_binding(meta['file'],inputs['native_cache'],'132 cache')
        if oldcash.get('schema')!='stage157_voluntary_cash_v1' or oldcash.get('new_cash_accounts')!=4:raise ValueError('accepted157 four books identity required')
        fields=list(dict.fromkeys(fit.ACTION_COLUMNS+cash.reuse.ACTION_FIELDS))
        a=table('actions',fields);fit_numeric=list(dict.fromkeys(fit.NUMERIC+['N_u','low20_u','u_close']))
        for c in fit_numeric:
            if c in a:a[c]=pd.to_numeric(a[c],errors='coerce')
        m=table('mothers',fit.IDENTITY)
        for c in ('sequence_index','u_index'):m[c]=pd.to_numeric(m[c],errors='raise')
        with np.load(io.BytesIO(read('common')),allow_pickle=False) as z:
            if z['columns'].tolist()!=fit.COMMON:raise ValueError('COMMON names differ')
            common=z['common'].astype(float)
        validate_dataset_arrays(a,m,common)
        train,pred,_=training_support(a,m)
        ref.write_json(out/'training_support.json',dict(training_rows=len(train),training_dates=int(train.u_date.nunique()),
            training_families=int(train.family_id.nunique()),max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
            prediction_children=len(pred),prediction_unknown_labels=int(pred.label_state.ne('closed_complete_bar_model').sum()),new_cutoff=START))
        del train,pred
        new,unused_choices,record=fit.fit_cell(a,m,common,'main',START,OLD_START,out/'folds/main'/START,attempt,complete)
        del common,unused_choices
        record['new_scores']=fit.write_csv(out/'new2015_child_scores.csv.gz',new)
        old=[];raw=read('child_scores')
        for chunk in pd.read_csv(io.BytesIO(raw),compression='gzip',dtype=str,keep_default_na=False,usecols=selector.SCORE_FIELDS,
                float_precision='round_trip',chunksize=100000):
            part=chunk.loc[chunk.scope.eq('main')].copy()
            if len(part):old.append(part)
        del raw
        old=pd.concat(old,ignore_index=True);cash.numeric(old,['sequence_index','mother_sequence_index','u_index','u_action_eligible']);old['score']=old.score.map(float)
        scores=pd.concat([new,old],ignore_index=True).sort_values('sequence_index',kind='stable').reset_index(drop=True)
        del new,old
        validate_score_schedule(scores)
        expected=a.loc[a.u_date.between(START,END)]
        identity=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']
        if len(scores)!=len(expected):raise ValueError('full forward child score domain differs')
        for c in identity:
            if scores[c].tolist()!=expected[c].tolist():raise ValueError('forward score identity differs '+c)
        fit.write_csv(out/'combined_child_scores.csv.gz',scores)
        forward=m.loc[m.u_date.between(START,END)].copy()
        fit.write_csv(out/'mothers_2015.csv.gz',forward)
        cal=np.load(io.BytesIO(read('calendar',market_protocol['calendar'])),allow_pickle=False)
        dates=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal] if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        with gzip.open(out/'action_eligibility.csv.gz','xt',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=selector.AUDIT_FIELDS);writer.writeheader()
            result=select_choices(forward,scores,dates,END,writer.writerow)
        choices=pd.DataFrame(result['choices']);fit.write_csv(out/'choices_main.csv.gz',choices)
        accepted=table('accepted_stage156_choices')
        cash.numeric(accepted,['sequence_index','u_index','selected','chosen_action_sequence_index']);accepted['score']=accepted.score.map(lambda v:float(v) if v else np.nan)
        overlap=check_overlap(choices,accepted);ref.write_json(out/'overlap_receipt.json',overlap)
        ref.write_json(out/'selection_summary.json',cash.kernel.original.safe(result['summary']))
        boundaries=result['boundaries'];ref.write_json(out/'boundaries.json',dict(schema='stage156_voluntary_K_only_v1',
            sample_end=END,account_deadline_certified=False,calendar=market_protocol['calendar'],epochs=boundaries))
        del scores,accepted,result,expected
        selected=set(choices.loc[choices.selected.eq(1),'chosen_action_id'])
        selected_actions=a.loc[a.action_id.isin(selected),cash.reuse.ACTION_FIELDS].copy();del a
        store,native_receipt,_=cash.cache_source.restore_native_cache(inputs['native_cache_manifest'])
        if native_receipt['native_source_queries']!=0 or ref.NATIVE_QUERIES!=0:raise ValueError('cache-only zero SQL required')
        if store.calendar!=dates:raise ValueError('full native source calendar differs')
        economics=json.loads(read('economic_projection',market_protocol['economic_projection']))['instruments']
        if set(economics)!=set(store.series):raise ValueError('native economics epoch domain differs')
        market=cash.CachedMarket(store)
        signals=cash.make_voluntary_signals(selected_actions,m,choices,boundaries,market,dates,economics)
        fit.write_csv(out/'signals_VOLUNTARY_RESELECT.csv.gz',signals)
        trace=['event_id','mother_event_id','reference_epoch','anchor_epoch','u_date','u_index','D_index','source_lifecycle_index',
            'voluntary_boundary_index','effective_lifecycle_index','effective_boundary_origin','K_target_date','K_date','K_state']
        fit.write_csv(out/'boundary_lineage.csv.gz',signals[trace])
        prepared=cash.author.organize(signals,m,dates);start=int(np.searchsorted(dates,START));end=int(np.searchsorted(dates,END))
        if end>=len(dates) or dates[end]!=END:raise ValueError('fixed last financial source day required')
        families=sorted(m.family_id.unique());curve=pd.DataFrame({'date':dates[start:end+1]})
        for cost in ('base','stress'):
            name='all_2015_'+cost
            if started_cash>=2:raise ValueError('two new cash budget exhausted')
            started_cash+=1;cash.reuse.write_cash_progress(out,started_cash,completed_cash,name)
            book=cash.kernel.run_cash_account(signals,market,dates,economics,cost,name,start,end,prepared=prepared)
            completed_cash+=1
            folder=out/name;ledgers=cash.write_ledgers(folder,book)
            summary,report,fy=cash.helpers.cash_report(book,families,ref.INITIAL)
            summary.update(account=name,account_id=name,arm=cash.ARM,window='all_2015',cost=cost,
                execution_unknown=book['execution_unknown'],any_historical_stale=report['stale_days']>0,
                unknown_capacity_fills=sum(r['capacity_state']=='execution_capacity_unknown' for r in book['capacity_audit']),
                capacity_unknown_roots=len(book['capacity_unknown_roots']),entry_execution_unknown=len(book['entry_execution_unknown']))
            ref.write_json(folder/'summary.json',cash.kernel.original.safe(summary));summaries.append(summary);reports[name]=report
            accounts.append(dict(account_id=name,arm=cash.ARM,window='all_2015',cost=cost,directory=str(folder),
                summary=ref.file_binding(folder/'summary.json'),ledgers=ledgers))
            family.append(cash.report_helpers.add_family_costs(fy,book).assign(account=name,arm=cash.ARM,window='all_2015',cost=cost))
            annual.extend(dict(account=name,cost=cost,**r) for r in report['annual_slices'])
            eq=np.asarray([r['equity'] for r in book['daily']],float)
            curve[cost+'_equity']=eq;curve[cost+'_drawdown_pct']=(eq/np.maximum.accumulate(np.r_[ref.INITIAL,eq])[1:]-1)*100
            print(json.dumps(dict(phase='account_complete',account=name,new_fit=completed,new_cash=completed_cash)),flush=True)
        if (attempts,completed,started_cash,completed_cash)!=(1,1,2,2):raise ValueError('exact one fit two cash completion required')
        fit.write_csv(out/'account_summaries.csv.gz',pd.DataFrame(summaries));fit.write_csv(out/'annual_slices.csv.gz',pd.DataFrame(annual))
        fit.write_csv(out/'family_year_including_zero.csv.gz',pd.concat(family,ignore_index=True))
        curve.to_csv(out/'equity_and_drawdown.csv',index=False,float_format='%.17g')
        ref.write_json(out/'diagnostics.json',cash.kernel.original.safe(reports));ref.write_json(out/'fit_records.json',[record])
        ref.write_json(out/'source_read_receipt.json',dict(payloads=read_receipt,native=native_receipt,
            complete_original_mothers_for_canonical=True,old_main_scores_reused=True,old_choices_overlap=overlap,
            new_held_models=0,old_refits=0,old_cash_replays=0,new_labels=0,downloads=0,
            source_snapshot_end=END,strict_PIT=False,production_qualified=False))
        ref.write_json(out/'budget_and_execution_disclosure.json',dict(protocol_cash=protocol['cash'],
            execution_cash=execution['cash'],anchor_and_execution=execution['anchor_and_execution'],
            no_bootstrap=True,no_new_held=True,fees_already_in_cash=True,slippage_already_in_fill_price=True,
            no_gap_loss_cap=True,account_deadline_certified=False,source_archive_final_reconstruction=True,
            production_qualified=False,increased_betting_qualified=False,goal_complete=False))
        if source_bundle()!=before:raise ValueError('675 authorized source changed during actual')
        if cash.cache_source.database_state(meta['database']['path'])!=native_receipt['database_after']:raise ValueError('native cached database stat changed')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,stage='extension_fit_cash',started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=='completed' else 1,error=error,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,
            cash_accounts_started=started_cash,new_cash_accounts=completed_cash,native_source_queries=ref.NATIVE_QUERIES,
            new_held_models=0,old_refits=0,old_cash_replays=0,new_labels=0,downloads=0,fixture=False,python=sys.executable,auto_retry=False))
    bindings={k:ref.file_binding(out/name) for k,name in dict(new_scores='new2015_child_scores.csv.gz',combined_scores='combined_child_scores.csv.gz',
        mothers_2015='mothers_2015.csv.gz',choices_main='choices_main.csv.gz',boundaries='boundaries.json',signals='signals_VOLUNTARY_RESELECT.csv.gz',
        boundary_lineage='boundary_lineage.csv.gz',overlap_receipt='overlap_receipt.json',selection_summary='selection_summary.json',
        account_summaries='account_summaries.csv.gz',annual_slices='annual_slices.csv.gz',family_year_including_zero='family_year_including_zero.csv.gz',
        curve_data='equity_and_drawdown.csv',diagnostics='diagnostics.json',source_read_receipt='source_read_receipt.json',
        budget_and_execution_disclosure='budget_and_execution_disclosure.json',training_support='training_support.json').items()}
    ref.write_json(out/'manifest.json',dict(schema='stage675_common52_2015_extension_v1',status=status,mode='actual',protocol=pb,
        authorization=ab,source_bundle=before,input_bindings=inputs,fold2015=record,fit_records=ref.file_binding(out/'fit_records.json'),
        accounts=accounts,terminal=ref.file_binding(out/'actual_terminal.json'),actual_fit_calls_completed=completed,new_cash_accounts=completed_cash,
        native_source_queries=0,new_held_models=0,old_refits=0,old_cash_replays=0,source_snapshot_end=END,strict_PIT=False,
        production_qualified=False,increased_betting_qualified=False,goal_complete=False,**bindings))
    return dict(status=status,output=str(out),new_fit=completed,new_cash=completed_cash)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',required=True);p.add_argument('--protocol-sha256',required=True)
    p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',required=True);args=p.parse_args()
    print(json.dumps(execute(args)),flush=True)

if __name__=='__main__':main()
