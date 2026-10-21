"""Continue only uncompleted cash/CI mathematics after the saved observer failure.

No model, prediction, selection, q or COMMON recomputation. No financial engine,
fit, SQL, download or new observer. The first failed receipt remains immutable.
Root must bind all completed checkpoints and this entry before actual use.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
spec=importlib.util.spec_from_file_location('stage192_frozen_recovery_math',TOOLS/'stage192_registration_review.py')
frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)


def bundle():
    return sorted(frozen.bundle()+[frozen.binding(Path(__file__))],key=lambda b:b['path'])


def required_roles():
    fixed={'protocol','fit_manifest','cash_manifest','prior_authorization','prior_started','prior_receipt','prior_terminal','prior_input_closure','prior_identity_q','prior_models_choices','observer_entry'}
    return fixed|{f'prior_model_{s}_{c}_{a}' for s in frozen.SCOPES for c in frozen.CUTOFFS for a in frozen.ARMS}


def authorize(args):
    ab=frozen.binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=frozen.read_json(ab);out=Path(args.output).resolve();assert not out.exists()
    assert LINE/'outputs/stage192_registration_review/actual_run1' in out.parents
    frozen.fields(auth,dict(schema='stage192_exact_root_recovery_authorization_v1',authorized_by='root',stage='cash_ci_only',exact_source_authorized=True,protocol_sha256=frozen.PROTOCOL_SHA,output=str(out),new_fit=0,new_cash=0,recompute_models=False,execute_cash_strategy=False),'exact root cash/CI recovery authorization')
    assert auth['source_bundle']==bundle() and set(auth['input_bindings'])==required_roles()
    for b in auth['source_bundle']:frozen.verify(b)
    return out,auth['input_bindings'],ab


def accept_completed_models(inputs,out):
    old=frozen.read_json(inputs['prior_receipt']);terminal=frozen.read_json(inputs['prior_terminal']);start=frozen.read_json(inputs['prior_started'])
    assert old['schema']=='stage192_registration_independent_review_v1' and old['completed'] is False
    assert old['C']==0 and old['I']==1 and old['M']==0 and len(old['errors'])==1
    error=old['errors'][0]
    assert error['type']=='TypeError' and "unsupported operand type(s) for /: 'module' and 'str'" in error['message']
    assert 'with_selection_observer' in error['traceback'] and 'main_choice_observation.json' in error['traceback']
    frozen.fields(terminal,dict(status='failed',exit_code=1,completed=False,new_fit=0,new_cash=0,SQL=0,completed_checkpoints_retained=True),'first failed observer attempt retained')
    frozen.nested(start['source_bundle'],frozen.bundle(),'original seven-file frozen math bundle')
    frozen.nested(old['source_bundle'],frozen.bundle(),'first failed receipt source bundle')
    original_auth=frozen.read_json(inputs['prior_authorization']);frozen.same(old['authorization'],inputs['prior_authorization']);frozen.same(start['inputs']['protocol'],inputs['protocol'])
    for role in ('protocol','fit_manifest','cash_manifest'):
        frozen.same(old['inputs'][role],inputs[role]);frozen.same(original_auth['input_bindings'][role],inputs[role])
    closure=frozen.read_json(inputs['prior_input_closure']);identity=frozen.read_json(inputs['prior_identity_q']);models=frozen.read_json(inputs['prior_models_choices'])
    for role in ('protocol','fit_manifest','cash_manifest'):frozen.same(closure[role],inputs[role])
    frozen.fields(identity,dict(actions=1552456,mothers=399252,q_finite=230490,all_2026_registration_q_missing=True,source_q_recalculations=0,child_parent_aliases_separate=True),'completed full source identity/q checkpoint')
    frozen.fields(models,dict(model_fits_reviewed=12,refits=0,all_forward_predictions_checked=3866960,main_parent_rows_per_arm=161014,held_union_parent_rows_per_arm=161014,all_full_parent_order_restored=True,filter_before_argmax=True,control_final_zero=True,accepted_q_measurement_inherited=True),'completed all model/selection checkpoint')
    assert len(models['models'])==12 and len(models['folds'])==6
    for scope in frozen.SCOPES:
        for cutoff in frozen.CUTOFFS:
            for arm in frozen.ARMS:
                checked=frozen.read_json(inputs[f'prior_model_{scope}_{cutoff}_{arm}'])
                frozen.fields(checked,dict(scope=scope,cutoff=cutoff,arm=arm,refits=0),'completed individual model checkpoint')
                assert checked in models['models']
    prior=Path(inputs['prior_started']['path']).parent
    assert not list(prior.glob('book_*.json')) and not (prior/'signals_review.json').exists() and not (prior/'confidence_and_gate_review.json').exists(),'only entirely unstarted cash/CI phases may continue'
    frozen.verify(inputs['observer_entry'])
    result=dict(first_failed_receipt=inputs['prior_receipt'],first_failed_terminal=inputs['prior_terminal'],original_math_bundle=frozen.bundle(),completed_model_checkpoint=inputs['prior_models_choices'],all12_model_checkpoints=[inputs[f'prior_model_{s}_{c}_{a}'] for s in frozen.SCOPES for c in frozen.CUTOFFS for a in frozen.ARMS],observer_source=inputs['observer_entry'],observer_failure_retained=True,observer_summary_abandoned=True,model_recomputations=0,prediction_recomputations=0,selection_recomputations=0)
    frozen.progress(out,'completed_model_checkpoint_acceptance',result)
    return identity,models,result


def restore_cash_identities(p,fm,out):
    """Restore lost process memory only; do not repeat model mathematics."""
    src=p['source_bindings'];before={r:frozen.stat_identity(src[r]) for r in ('actions','mothers')}
    mothers=frozen.numeric(frozen.table(src['mothers'],frozen.IDENTITY),['sequence_index','u_index'])
    assert len(mothers)==399252 and mothers.event_id.is_unique and np.array_equal(mothers.sequence_index,np.arange(399252))
    choices=frozen.numeric(frozen.table(fm['choices_main']),['sequence_index','u_index','selected','chosen_action_sequence_index','score','proposed_score'])
    expected=mothers.loc[mothers.u_date.ge('2020-01-01')]
    assert len(choices)==322028 and set(choices.arm)==set(frozen.ARMS) and set(choices.scope)=={'main'}
    for arm in frozen.ARMS:
        part=choices.loc[choices.arm.eq(arm)];assert part.event_id.tolist()==expected.event_id.tolist()
        for col in frozen.IDENTITY:assert part[col].tolist()==expected[col].tolist(),('restored accepted parent identity',arm,col)
    ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id'])
    cols=['action_id','action_sequence_index','mother_event_id','mother_sequence_index','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close']
    chunks=[];scanned=0
    with frozen.csv_stream(src['actions']) as stream:
        for chunk in pd.read_csv(stream,usecols=cols,dtype=str,keep_default_na=False,float_precision='round_trip',chunksize=100000):
            assert np.array_equal(pd.to_numeric(chunk.action_sequence_index),np.arange(scanned,scanned+len(chunk)))
            scanned+=len(chunk);part=chunk.loc[chunk.action_id.isin(ids)].copy()
            if len(part):chunks.append(part)
    actions=pd.concat(chunks,ignore_index=True) if chunks else pd.DataFrame(columns=cols)
    frozen.numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    assert scanned==1552456 and actions.action_id.is_unique and set(actions.action_id)==ids
    for role in before:assert before[role]==frozen.stat_identity(src[role])
    raw=np.load(frozen.verify(src['calendar']),allow_pickle=False)
    calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw] if raw.dtype.kind in 'iu' else raw.astype('datetime64[D]').astype(str).tolist())
    assert len(calendar)==5587 and calendar==sorted(set(calendar))
    bounds=frozen.read_json(fm['boundaries'])['epochs'];held=frozen.read_json(fm['held_diagnostic']);execution=frozen.read_json(src['execution_protocol'])
    frozen.progress(out,'cash_identity_memory_restore',dict(full_mothers=len(mothers),full_main_parent_rows=len(choices),selected_original_children=len(actions),source_rows_scanned=scanned,models_recomputed=0,scores_recomputed=0,choices_recomputed=0,q_or_COMMON_read_again=False,additional_old_actions_and_mothers_read_passes=1,reason='lost first process memory after auxiliary observer failed; pure identity restoration only'))
    return actions,mothers,choices,calendar,bounds,held,execution


def run(args):
    out,inputs,ab=authorize(args);out.mkdir(parents=True,exist_ok=False);before=bundle();began=time.monotonic()
    receipt=dict(schema='stage192_registration_independent_review_recovery_v1',completed=False,C=0,I=0,M=0,errors=[],authorization=ab,input_bindings=inputs,source_bundle=before,new_fit=0,new_cash=0,SQL=0,downloads=0,strategy_replays=0,model_recomputations=0,prediction_recomputations=0,selection_recomputations=0,source_q_recalculations=0,whole_database_hashes=0,author190_or191_imported=False,automatic_retry=False,observer_summary_abandoned=True,resolved_review_pipeline_incidents=1,python=sys.executable)
    frozen.write(out/'started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),authorization=ab,source_bundle=before,inputs=inputs))
    try:
        identity,models,accepted=accept_completed_models(inputs,out);receipt['completed_model_acceptance']=accepted;receipt['models']=models;receipt['source_identity_q']=identity
        minimal={r:inputs[r] for r in ('protocol','fit_manifest','cash_manifest')}
        p,fm,cm=frozen.input_closure(minimal,out);r,cash,diag=frozen.reuse().helpers()
        a,mothers,choices,calendar,bounds,held,execution=restore_cash_identities(p,fm,out)
        store,economics,econ_binding=frozen.cached_store(p,calendar,r);frozen.same(cm['economic_projection'],econ_binding)
        signals,signal_report=frozen.review_signals(p,cm,choices,a,bounds,store,economics,out,r);receipt['signals']=signal_report;del a,choices
        metrics,daily,logs,books,grids=frozen.review_books(p,cm,signals,mothers,store,economics,execution,out,r,cash,diag);receipt['books']=books;receipt['grids']=grids
        receipt['confidence']=frozen.review_comparisons(p,cm,metrics,daily,logs,books,held,execution,out)
        assert bundle()==before
        for b in inputs.values():frozen.verify(b)
        for role in ('actions','mothers','common','projection_actions'):assert frozen.stat_identity(p['source_bindings'][role])==fm['input_evidence'][role]['stat_after']
        assert all(frozen.DISK_READS[b['path']]==1 for account in cm['accounts'] for b in account['ledgers'].values()),'each cash ledger parsed/hash checked once during recovery'
        receipt['recovery_disk_data_reads']=dict(frozen.DISK_READS);receipt['maximum_cash_numeric_errors']=dict(frozen.ERRORS);receipt['accepted132_cash_numeric_errors']=dict(r.ERRORS);receipt['accepted158_cash_numeric_errors']=dict(frozen.reuse().ERRORS)
        receipt.update(completed=True,research_arithmetic_accepted=True,new_models_reviewed=12,new_financial_books_reviewed=8,cumulative_fit=421,cumulative_cash=226,conditional_reconstruction_only=True,strict_first_release_PIT_established=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-began;frozen.write(out/'receipt.json',receipt)
        frozen.write(out/'terminal.json',dict(status='completed' if receipt['completed'] else 'failed',exit_code=0 if receipt['completed'] else 1,completed=receipt['completed'],elapsed_seconds=receipt['elapsed_seconds'],new_fit=0,new_cash=0,SQL=0,automatic_retry=False,first_observer_failure_preserved=True,completed_model_recomputations=0))
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    run(parser.parse_args())


if __name__=='__main__':main()
