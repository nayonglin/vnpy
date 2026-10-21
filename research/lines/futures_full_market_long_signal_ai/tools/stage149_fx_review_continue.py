"""Exact continuation of Stage149's single logical incremental audit.

Reuses the failed run's completed ZIP/model/score/choice checks; only held,
new four-book accounting and four paired comparisons remain. Never opens COMMON,
new child scores, normal equations or training tables and never fits/replays/SQLs.
The prior failed folder and checker snapshots are immutable evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review149_continuation_independent',TOOLS/'stage149_fx_review.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
ORIGINAL_CHECKER_SHA='d07df252bcc0776855dc29db0426e78017641075d5bf68a0462d5f10a431f846'
PRIOR_NAMES={
 'prior_started':'actual_started.json',
 'prior_terminal':'actual_terminal.json',
 'prior_failure_trace':'failure_trace.json',
 'prior_input_closure':'input_closure.json',
 'prior_projection_review':'projection_from_rawZIP.json',
 'prior_checker_snapshot':'checker_snapshot/stage149_fx_review.py',
}
MODEL_ROLES={f'prior_model_{scope}_{cutoff}':f'model_{scope}_{cutoff}.json' for scope in base.SCOPES for cutoff in base.CUTOFFS}
INPUT_ROLES={'projection_manifest','fit_manifest','cash_manifest',*PRIOR_NAMES,*MODEL_ROLES}


def bundle():
    return sorted(base.bundle()+[base.binding(TOOLS/n) for n in ('stage149_fx_review_continue.py','test_stage149_fx_review_continue.py')],key=lambda b:b['path'])


def alias_only_change(old,current):
    before="base=control.loc[control.scope.eq(scope)&control.arm.eq('B')]"
    after="base=control.loc[control.scope.eq(scope)&control.arm.eq('CONTROL_REUSED')]"
    assert old.count(before)==1 and old.replace(before,after)==current,'only held CONTROL alias fix may differ from failed checker'
    return True


def failed_held_stage(terminal,trace):
    base.fields(terminal,dict(status='failed',exit_code=1,error='AssertionError: complete held family-u',new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_replays=0,full_new_results_independent_review_completions=0),'original failed held stage')
    assert trace['error']==terminal['error'] and all(s in trace['traceback'] for s in ('review_models','held_result','AssertionError: complete held family-u'))
    return True


def model_evidence(reports):
    expected={(s,c) for s in base.SCOPES for c in base.CUTOFFS}
    assert len(reports)==6 and {(r['scope'],r['cutoff']) for r in reports}==expected,'all six completed model checkpoints'
    for row in reports:
        assert row['training_rows']>0 and row['forward_children']>0 and row['forward_mothers']>0
        base.fields(row,dict(common_scaler_refit=False,weights_reconstructed=False,model_refit=False),'prior completed model evidence')
        q=row['q_stats'];assert q['finite_count']==row['training_rows'] and all(base.finite(q[k]) for k in ('mean','var','scale')) and q['var']>0 and q['scale']>0
    return dict(models_checked=6,new_child_scores_checked=sum(r['forward_children'] for r in reports),new_parent_choices_checked=sum(r['forward_mothers'] for r in reports),folds=reports,checks_reexecuted=False,model_refits=0,normal_equations_or_new_scores_reopened=False,numeric_error_statement='All prior checks passed within the exact tolerances in the bound original snapshot; per-check/global maxima were not persisted and are unavailable.',numeric_max_errors=None)


def authorize(args):
    out=Path(args.output).resolve()
    assert not out.exists() and base.LINE/'outputs/stage149_fx_review' in out.parents,'fresh Stage149 continuation folder required'
    pb=base.binding(args.protocol);assert args.protocol_sha256==pb['sha256']==base.PROTOCOL_SHA
    protocol=base.read_json(pb)
    ab=base.binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=base.read_json(ab)
    base.fields(auth,dict(schema='stage145_exact_root_authorization_v1',authorized_by='root',stage='review_continue',exact_source_authorized=True,protocol_sha256=base.PROTOCOL_SHA,output=str(out)),'root exact continuation authorization')
    assert auth['source_bundle']==bundle() and set(auth['input_bindings'])==INPUT_ROLES,'exact continuation sources and evidence roles'
    return out,protocol,pb,auth,ab


def prior_evidence(protocol,auth):
    inputs=auth['input_bindings'];prior=Path(inputs['prior_terminal']['path']).parent
    assert prior==base.LINE/'outputs/stage149_fx_review/actual_run1','only original run1 may continue'
    for role,name in {**PRIOR_NAMES,**MODEL_ROLES}.items():assert Path(inputs[role]['path'])==prior/name,('prior exact path',role)
    terminal=base.read_json(inputs['prior_terminal']);trace=base.read_json(inputs['prior_failure_trace']);failed_held_stage(terminal,trace)
    assert not (prior/'review_receipt.json').exists() and not (prior/'models_and_full_held.json').exists(),'prior full review never completed'
    started=base.read_json(inputs['prior_started']);base.fields(started,dict(status='started',schema='stage149_incremental_review_start_v1',fixture=False,new_SQL=0,new_fits=0,new_cash=0),'prior review started')
    assert started['protocol']['sha256']==base.PROTOCOL_SHA
    old_authorization=base.read_json(started['authorization'])
    base.fields(old_authorization,dict(schema='stage145_exact_root_authorization_v1',authorized_by='root',stage='review',exact_source_authorized=True,protocol_sha256=base.PROTOCOL_SHA,output=str(prior)),'original exact root authorization')
    assert old_authorization['source_bundle']==started['source_bundle'] and old_authorization['input_bindings']==started['input_bindings']
    source=base.bound(inputs['prior_checker_snapshot']).decode();assert hashlib.sha256(source.encode()).hexdigest()==ORIGINAL_CHECKER_SHA
    alias_only_change(source,(TOOLS/'stage149_fx_review.py').read_text())
    original_source={Path(b['path']).name:b for b in started['source_bundle']}
    assert original_source['stage149_fx_review.py']['sha256']==ORIGINAL_CHECKER_SHA
    for name,b in original_source.items():
        snapshot=prior/'checker_snapshot'/name;raw=snapshot.read_bytes()
        assert len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],('prior source snapshot',name)
        if name in base.HELPERS:base.same_binding(base.binding(TOOLS/name),b)
    projection=base.read_json(inputs['prior_projection_review'])
    base.fields(projection,dict(all_08_assignment_u15_clocks_and_ages_checked=True,all_n_d_w_same_batch_ratios_and_q_checked=True,full_mother_projection_rows=399252,missing_or_future_rows_not_skipped=True,rawZIP_rows=7116,strict_first_release_PIT_established=False),'completed prior ZIP projection')
    reports=[base.read_json(inputs[role]) for role in MODEL_ROLES];models=model_evidence(reports)
    closure=base.read_json(inputs['prior_input_closure']);manifests={}
    for role,schema in [('projection','stage146_fx_projection_v1'),('fit','stage147_fx_fit_v1'),('cash','stage148_fx_cash_v1')]:
        item=inputs[role+'_manifest'];base.same_binding(item,started['input_bindings'][role+'_manifest']);base.same_binding(item,closure[role]['manifest'])
        m=base.read_json(item);base.fields(m,dict(status='completed',mode='actual',schema=schema,protocol_sha256=base.PROTOCOL_SHA),'unchanged phase manifest '+role)
        base.same_binding(m['terminal'],closure[role]['terminal']);base.fields(base.read_json(m['terminal']),dict(status='completed',exit_code=0,native_source_queries=0),'unchanged phase terminal')
        assert m['source_bundle']==closure[role]['source_bundle']
        for b in m['source_bundle']:base.verify(b)
        manifests[role]=m
    assert models['new_child_scores_checked']==manifests['fit']['prediction_children']==1933480 and models['new_parent_choices_checked']==322028
    # No COMMON/score/NE/training file is opened. The exact manifest closure and
    # original successful checkpoints carry those already completed checks.
    report=dict(schema='stage149_exact_checkpoint_continuation_v1',prior_directory=str(prior),prior_evidence_bindings={k:inputs[k] for k in (*PRIOR_NAMES,*MODEL_ROLES)},original_checker_sha256=ORIGINAL_CHECKER_SHA,current_checker_only_difference='held_result control.arm B -> CONTROL_REUSED',original_authorization=started['authorization'],original_failure_retained=True,source_projection_rechecks=0,model_or_normal_equation_rechecks=0,new_child_score_rechecks=0,full_choice_selection_rechecks=0,new_research_fits=0,new_cash_replays=0,new_SQL=0,new_downloads=0,skipped_matrices_reopened_or_rehashed=False,skipped_matrix_byte_identity='Inherited from exact run1 closure/checkpoints; not newly re-read or globally reasserted.',logical_full_new_review_completions_before=0,prior_numeric_max_errors_available=False)
    return manifests,closure,projection,models,report


def complete_held(protocol,fit,actions,out):
    controls=[];fx=[]
    for role,old_role in [('choices_main','accepted_choices_main'),('choices_holdout','accepted_choices_holdout')]:
        old=base.numeric(base.table(protocol['input_roles'][old_role]));old=old.loc[old.arm.eq('B')].copy();old['arm']='CONTROL_REUSED';controls.append(old)
        new=base.numeric(base.table(fit[role]));assert set(new.arm)=={'CONTROL_REUSED','FX'} and len(new)==322028
        fx.append(new.loc[new.arm.eq('FX')].copy())
    controls=pd.concat(controls,ignore_index=True);fx=pd.concat(fx,ignore_index=True)
    assert len(controls)==len(fx)==322028 and not controls.duplicated(['scope','event_id']).any() and not fx.duplicated(['scope','event_id']).any()
    groups,daily,family=base.held_result(fx,controls,actions,'2026-10-16')
    held=base.read_json(fit['held_diagnostic']);base.nested(held['groups'],groups,'continued complete held groups')
    base.fields(held,dict(schema='stage147_fx_held_v1',contrast='FX_minus_CONTROL_REUSED',full_policy_cash_qualified=False),'continued held limits')
    base.compare_frame(base.table(fit['held_daily']),daily,['scope','u_date'],'continued all held daily',['delta_R','known_family_u','unknown_family_u'])
    base.compare_frame(base.table(fit['held_family_u']),family,['scope','family_id','u_index'],'continued all held family-u',['delta_R','control_value_R','fx_value_R'],['same_action','known','unknown','common_unresolved_same_action'])
    report=dict(schema='stage149_continued_held_review_v1',new_parent_rows=len(fx),control_reference_rows=len(controls),complete_family_u_rows=len(family),complete_source_day_rows=len(daily),held_groups=groups,same_action_unknown_cancelled_only_in_increment=True,different_unknown_never_filled_zero=True,unknown_cash_equivalence_asserted=False)
    base.progress(out,'completed_held_and_unknown',report)
    return fx.loc[fx.scope.eq('main')],held,report


def review(args):
    out,protocol,pb,auth,ab=authorize(args);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();sources=bundle();status='failed';error=None
    base.write(out/'actual_started.json',dict(schema='stage149_continuation_started_v1',status='started',protocol=pb,authorization=ab,source_bundle=sources,input_bindings=auth['input_bindings'],fixture=False,new_SQL=0,new_fits=0,new_cash=0))
    snapshot=out/'checker_snapshot';snapshot.mkdir()
    for source in sources:(snapshot/Path(source['path']).name).write_bytes(base.bound(source))
    try:
        manifests,closure,projection,models,continuation=prior_evidence(protocol,auth);base.progress(out,'continuation_evidence',continuation)
        roles=protocol['input_roles'];mothers=base.numeric(base.table(roles['mothers'],base.IDENTITY));assert len(mothers)==399252 and mothers.event_id.is_unique
        # Only labels for held and observed identities for new signal checking.
        # No train/union/scaler/COMMON or score calculation is performed.
        columns=['action_id','action_sequence_index','actual_epoch','product_id','family_id','u_date','u_action_eligible','anchor_epoch','label_state','participation_state','net_R_stress','label_known_date']
        actions=base.numeric(base.table(roles['actions'],columns));assert len(actions)==1552456 and actions.action_id.is_unique
        choices,held,held_report=complete_held(protocol,manifests['fit'],actions,out)
        r,cash,diag=base.accepted_helpers();execution=base.read_json(roles['execution_protocol']);store,economics=base.cached_store(protocol,execution,r)
        signals=base.review_signals(manifests['cash'],choices,actions,store,economics,r)
        base.fields(base.read_json(manifests['cash']['signal_identification']),dict(selected_FX_actions=len(signals)),'continued selected FX actions')
        summaries,daily,logs,books=base.review_books(protocol,manifests['cash'],signals,mothers,store,economics,execution,out,r,cash,diag)
        comparisons=base.review_comparisons(protocol,manifests['cash'],summaries,daily,logs,books,held,diag);base.progress(out,'paired_CI_and_gates',comparisons)
        assert sources==bundle(),'continuation source changed during actual'
        receipt=dict(schema='stage149_fx_incremental_independent_review_continued_v1',completed=True,C=0,I=0,M=0,research_arithmetic_accepted=True,fixed_package_supported=comparisons['gate']['status']=='supported_limited_reconstruction_model_only',input_closure=closure,continuation=continuation,projection_review_reused=projection,model_review_reused=models,held_review=held_report,cash_accounts=books,comparisons=comparisons,prior_review_startups=1,this_continuation_startups=1,cumulative_review_startups=2,logical_full_new_results_review_completions=1,complete_review_reruns=0,prior_numeric_max_errors=None,prior_numeric_error_statement=models['numeric_error_statement'],continuation_numeric_max_errors=dict(base.ERRORS),continuation_cash_helper_numeric_errors=dict(cash.ERRORS),new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_fits=0,old_control_cash_replays=0,old_models_or_ledger_full_reaudits=0,checker_sources=sources,strict_first_release_PIT_established=False,orderbook_execution_established=False,narrow_stop_is_universal_loss_bound=False,goal_complete=False,production_qualified=False,increased_betting_qualified=False,limitations=['Original checker failed at an arm alias before held/cash review; failed terminal and original source snapshots are retained.','Prior numerical checks passed within snapshot tolerances, but their global maximum errors were not persisted; no maximum is fabricated.','Final ECB archive is not first-release vintage; assigned availability remains a historical assumption.','One global scalar does not identify month-specific FX or causal innovation; repeated as-of states are not independent releases.','Same historical search, overlapping starts and held families do not create unseen macro OOS; paired CI is conditional on fixed reconstructed paths.','Daily ideal native-bar execution, gap/stale/capacity and entry unknown limits survive nominal profit.','Old CONTROL remains a historical reference and cannot be promoted from this comparison.'])
        base.write(out/'review_receipt.json',receipt);status='completed';return receipt
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';base.write(out/'failure_trace.json',dict(error=error,traceback=traceback.format_exc()));raise
    finally:
        base.write(out/'actual_terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,elapsed_seconds=time.monotonic()-began,new_SQL=0,new_fits=0,new_cash=0,new_labels=0,new_downloads=0,whole_DB_hashes=0,old_control_replays=0,logical_full_new_results_review_completions=int(status=='completed'),complete_review_reruns=0,automatic_retry=False,fixture=False))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):p.add_argument('--'+name,required=True)
    receipt=review(p.parse_args(argv));print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],logical_review_completions=1,complete_review_reruns=0,new_SQL=0,new_fits=0,new_cash=0)),flush=True)


if __name__=='__main__':main()
