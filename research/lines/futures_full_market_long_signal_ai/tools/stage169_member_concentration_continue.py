"""Root-authorized continuation after169 interval-JSON checker failure.

Inherit only the two completed immutable review phases. Restore arrays needed
by pending model/choice/book/CI checks. Never call review(), input_closure(),
load_data(), refit, a cash kernel, SQL or original member-source measurements.
No automatic retry and no completed book replay.
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
spec=importlib.util.spec_from_file_location('review169_fixed_for_explicit_continuation',TOOLS/'stage169_member_concentration_review.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
OLD_SOURCE='501e0ae60292732756adc793af98996714de8de84575bb5d7790fa6bc6d9cd1e'
OLD_TEST='45201a09c7bccf371cd30a7a01f15f3be2bf7f1a1997c36600d34bd738ac6a64'


def source_bundle():
    return sorted(r.bundle()+[r.binding(__file__)],key=lambda b:b['path'])


def inputs_for(failed_run):
    folder=Path(failed_run).resolve();receipt=json.loads((folder/'receipt.json').read_text())
    inputs=dict(receipt['inputs'])
    for role,name in [('failed_receipt','receipt.json'),('failed_terminal','terminal.json'),('failed_started','started.json'),('accepted_input_closure','input_closure.json'),('accepted_identity_q','identity_and_accepted_q.json'),('failure_snapshot_manifest','failure_source/manifest.json')]:inputs[role]=r.binding(folder/name)
    return inputs


def inherited_bindings(inputs):
    """Small manifests only; no table, NPZ, raw-data or large hash here."""
    p=json.loads(Path(inputs['protocol']['path']).read_text());fm=json.loads(Path(inputs['fit_manifest']['path']).read_text());cm=json.loads(Path(inputs['cash_manifest']['path']).read_text())
    found={}
    def add(b):
        if b['path'] in found:r.same(found[b['path']],b)
        else:found[b['path']]={k:b[k] for k in ('path','bytes','sha256')}
    for b in p['source_bindings'].values():add(b)
    for m in (fm,cm):
        for b in m['source_bundle']:add(b)
        for name in ('authorization','terminal'):add(m[name])
        if 'financial_terminal' in m:add(m['financial_terminal'])
        assets=m['artifacts'];assets=assets.values() if isinstance(assets,dict) else assets
        for b in assets:add(b)
    return [found[k] for k in sorted(found)]


def stat_evidence(failed_run):
    """Root may call to construct exact authorization; stats only, no actual."""
    return [dict(binding=b,stat=r.stat_identity(b)) for b in inherited_bindings(inputs_for(failed_run))]


def authorize(args):
    folder=Path(args.failed_run).resolve();out=Path(args.output).resolve();assert not out.exists()
    assert r.LINE/'outputs/stage169_member_concentration_review' in out.parents and folder!=out
    inputs=inputs_for(folder);ab=r.binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=json.loads(Path(ab['path']).read_text())
    r.fields(auth,dict(schema='stage169_exact_root_continuation_authorization_v1',authorized_by='root',exact_source_authorized=True,protocol_sha256=r.PROTOCOL_SHA,failed_run=str(folder),output=str(out),root_attests_artifacts_unchanged_since_completed_input_closure=True,do_not_repeat_completed_identity_or_source_audit=True),'explicit root continuation')
    r.nested(auth['input_bindings'],inputs,'exact failed/current review inputs');assert auth['source_bundle']==source_bundle()
    for b in inputs.values():r.same(r.binding(b['path']),b)
    old=json.loads(Path(inputs['failed_receipt']['path']).read_text());terminal=json.loads(Path(inputs['failed_terminal']['path']).read_text())
    assert old['completed'] is False and terminal['status']=='failed' and terminal['exit_code']==1
    assert len(old['errors'])==1 and old['errors'][0]['type']=='TypeError' and old['errors'][0]['message']=='Object of type int64 is not JSON serializable'
    assert all(not p.exists() for p in (folder/'models_and_choices_review.json',folder/'books_review.json',folder/'confidence_and_gate_review.json'))
    assert not list(folder.glob('model_*.json')) and not list(folder.glob('book_*.json')),'completed pending-phase checkpoint must never be replayed'
    started=json.loads(Path(inputs['failed_started']['path']).read_text());assert started['inputs']==old['inputs']
    snapshot=json.loads(Path(inputs['failure_snapshot_manifest']['path']).read_text());assert snapshot['status']=='failed_review_source_snapshot'
    saved={Path(b['path']).name:b for b in snapshot['source_bundle']};assert set(saved)=={'stage169_member_concentration_review.py','test_stage169_member_concentration_review.py'}
    for name,sha in [('stage169_member_concentration_review.py',OLD_SOURCE),('test_stage169_member_concentration_review.py',OLD_TEST)]:
        b=saved[name];assert b['sha256']==sha;r.same(r.binding(b['path']),b)
        original=next(v for v in old['source_bundle'] if Path(v['path']).name==name);assert original['bytes']==b['bytes'] and original['sha256']==sha
    closure=json.loads(Path(inputs['accepted_input_closure']['path']).read_text());identity=json.loads(Path(inputs['accepted_identity_q']['path']).read_text())
    for role in ('protocol','fit_manifest','cash_manifest'):r.same(closure[role],inputs[role])
    assert closure['upstream_fit_calls']==12 and closure['upstream_cash_books']==8 and closure['accepted_measurement_not_recomputed'] is True
    r.fields(identity,dict(actions=1552456,mothers=399252,calendar_sessions=5587,source_q_recalculations=0,child_parent_aliases_separate=True),'inherited complete identity/q checkpoint');assert identity['common_shape']==[1552456,26]
    expected=inherited_bindings(inputs);evidence=auth['verified_artifact_stats'];assert len(expected)==len(evidence)
    for b,e in zip(expected,evidence):
        r.same(b,e['binding']);assert e['stat']==r.stat_identity(b),('changed original accepted artifact',b['path'])
        r.INHERITED.add(b['path'])
    # The original input closure itself recorded these large data stats.
    for role,state in closure['source_inputs_unchanged'].items():
        b=next(v for v in expected if v['path']==state['path']);assert r.stat_identity(b)==state,(role,'changed since completed first closure')
    return out,inputs,auth,ab,closure,identity


def restore_arrays(p):
    """Data restoration only; inherited row/alias/q/PIT review is not repeated."""
    src=p['source_bindings'];num=['sequence_index','action_sequence_index','mother_sequence_index','u_index','entry_index','exit_index','net_R_stress','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close','label_history_ready20']
    cols=list(dict.fromkeys(r.IDENTITY+['action_sequence_index','action_id','actual_epoch','mother_sequence_index','mother_event_id','anchor_epoch','u_action_eligible','entry_index','exit_index','entry_date','exit_date','net_R_stress','label_state','label_known_date','participation_state','entry_capacity_qty','label_history_ready20','N_u','low20_u','u_close']))
    a=r.numeric(pd.read_csv(src['actions']['path'],usecols=cols,dtype=str,keep_default_na=False,float_precision='round_trip'),num)
    m=r.numeric(pd.read_csv(src['mothers']['path'],usecols=r.IDENTITY,dtype=str,keep_default_na=False),['sequence_index','u_index'])
    projection=pd.read_csv(src['member_projection']['path'],usecols=['scalar_primary'],dtype=str,keep_default_na=False,float_precision='round_trip');q=pd.to_numeric(projection.scalar_primary.replace('',np.nan),errors='raise').to_numpy(float);del projection
    with np.load(src['common']['path'],allow_pickle=False) as z:common=z['common'].astype(float);columns=z['columns'].tolist()
    raw=np.load(src['calendar']['path'],allow_pickle=False)
    calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw] if raw.dtype.kind in 'iu' else raw.astype('datetime64[D]').astype(str).tolist())
    execution=r.read_json(src['execution_protocol'])
    return a,m,common,q,calendar,columns,execution


def continue_review(args):
    out,inputs,auth,ab,closure,identity=authorize(args);out.mkdir(parents=True,exist_ok=False);before=source_bundle();began=time.monotonic()
    receipt=dict(schema='stage169_member_concentration_continued_independent_review_v1',completed=False,C=0,I=0,M=0,errors=[],inputs=inputs,authorization=ab,source_bundle=before,original_failed_receipt=inputs['failed_receipt'],inherited_completed_phases={'input_closure':inputs['accepted_input_closure'],'identity_and_accepted_q':inputs['accepted_identity_q']},original_failed_processes=1,continuation_processes=1,new_fit=0,new_cash=0,SQL=0,downloads=0,whole_database_hashes=0,strategy_replays=0,source_q_recalculations=0,author167_or168_imported=False,automatic_retry=False,completed_identity_or_source_audits_repeated=0,large_input_hashes_repeated=0,python=sys.executable)
    r.write(out/'started.json',dict(status='started_explicit_continuation',started_at=datetime.now(timezone.utc).isoformat(),authorization=ab,inputs=inputs,source_bundle=before,inherited_completed_phases=receipt['inherited_completed_phases'],verified_artifact_stats=auth['verified_artifact_stats'],automatic_retry=False))
    try:
        # Small manifest restoration. This does not enter the old closure routine.
        p=json.loads(Path(inputs['protocol']['path']).read_text());fm=json.loads(Path(inputs['fit_manifest']['path']).read_text());cm=json.loads(Path(inputs['cash_manifest']['path']).read_text())
        accepted,cash,diag=r.reuse().helpers();a,m,common,q,calendar,columns,execution=restore_arrays(p)
        choices,held,bounds,models=r.review_models(p,fm,a,m,common,q,calendar,columns,out,accepted);receipt['models']=models;del common,q
        store,economics,econ_binding=r.cached_store(p,calendar,accepted);r.same(cm['economic_projection'],econ_binding)
        signals,signal_report=r.review_signals(p,cm,choices,a,bounds,store,economics,out,accepted);receipt['signals']=signal_report;del a
        metrics,daily,logs,books,grids=r.review_books(p,cm,signals,m,store,economics,execution,out,accepted,cash,diag);receipt['books']=books;receipt['grids']=grids
        receipt['confidence']=r.review_comparisons(p,cm,metrics,daily,logs,books,held,execution,out)
        assert source_bundle()==before
        for e in auth['verified_artifact_stats']:assert e['stat']==r.stat_identity(e['binding']),('artifact changed during pending-phase review',e['binding']['path'])
        for b in inputs.values():r.same(r.binding(b['path']),b)
        receipt['maximum_numeric_errors']=dict(r.ERRORS);receipt['accepted132_numeric_errors']=dict(accepted.ERRORS);receipt['accepted158_numeric_errors']=dict(r.reuse().ERRORS)
        receipt.update(completed=True,research_arithmetic_accepted=True,new_models_reviewed=12,new_financial_books_reviewed=8,cumulative_fit=409,cumulative_cash=218,conditional_reconstruction_only=True,strict_first_release_PIT_established=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-began;r.write(out/'receipt.json',receipt)
        r.write(out/'terminal.json',dict(status='completed' if receipt['completed'] else 'failed',exit_code=0 if receipt['completed'] else 1,completed=receipt['completed'],elapsed_seconds=receipt['elapsed_seconds'],original_failed_receipt=inputs['failed_receipt'],inherited_completed_phases=receipt['inherited_completed_phases'],automatic_retry=False,new_fit=0,new_cash=0,SQL=0,completed_checkpoints_retained=True))
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('failed-run','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    continue_review(parser.parse_args())


if __name__=='__main__':main()
