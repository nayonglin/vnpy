"""Thin362 reuse for the explicitly amended second acquisition; no network.

Only the review-output directory literal is adapted in memory. The frozen
acquisition inputs, original reviewer file and its first receipt are untouched.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

LINE=Path(__file__).resolve().parents[1]
OLD=LINE/'tools/stage362_actual_forward_source_review.py'
OLD_SHA='22132de7e5aa2a504961eeef808bd0df87ee831f6f90e55aa791e908a2ffce99'
BASE=LINE/'outputs/stage362_u20_forward_source_review'
PREP=BASE/'prepare2_network_corrected'
FINAL=BASE/'actual_run2_network_corrected'
CORRECTION=LINE/'outputs/stage411_capture_network_correction'


def bind(path, raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(path):return json.loads(Path(path).read_bytes())


def write(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:f.write(raw)
    return bind(path,raw)


def guard():
    raw=OLD.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=OLD_SHA:raise ValueError('original362 reviewer changed')
    return raw.decode()


def prepare():
    guard();original=read(LINE/'outputs/stage360_frozen_reference_decision/execution_plan.json')
    plan=read(CORRECTION/'execution_plan.json');new=read(plan['authorization']['path'])
    old=read(original['authorization']['path']);amendment=read(plan['amendment']['path'])
    added={'operational_amendment','original_authorization','source_attempt_number',
           'source_attempt_output','strict_original_single_acquisition_adherence'}
    if ({k:v for k,v in new.items() if k not in added}!=old or new['source_attempt_number']!=2
            or new['strict_original_single_acquisition_adherence'] is not False
            or new['operational_amendment']!=plan['amendment'] or plan['attempt3_authorized'] is not False
            or plan['entrypoint']!=original['entrypoint'] or plan['output']!=amendment['new_attempt']['output']):
        raise ValueError('only explicit411 operational correction is permitted')
    for key in ('authorization','amendment'):
        if bind(plan[key]['path'])!=plan[key]:raise ValueError('411 binding changed: '+key)
    PREP.mkdir(parents=True,exist_ok=False)
    view=dict(original,authorization=plan['authorization'],output=plan['output'],
        schema='stage414_original360_review_view_with_explicit411_correction_v1',
        original_plan=bind(LINE/'outputs/stage360_frozen_reference_decision/execution_plan.json'),
        correction_plan=bind(CORRECTION/'execution_plan.json'),operational_amendment=plan['amendment'],
        source_attempt_number=2,strict_original_single_acquisition_adherence=False,attempt3_authorized=False)
    view_binding=write(PREP/'review_plan.json',view)
    return write(PREP/'readiness.json',dict(schema='stage414_corrected_source_review_readiness_v1',
        reviewer=bind(__file__),reused362=bind(OLD),review_plan=view_binding,actual_output=str(FINAL),
        corrected_capture_output=plan['output'],operational_amendment=plan['amendment'],
        acquisition_authorization=plan['authorization'],source_attempt_number=2,
        strict_original_single_acquisition_adherence=False,attempt3_authorized=False,
        same_frozen_inputs_model_scaler_clock_risk=True,original_raw_or_review_reparsed=False,
        new_raw_read=False,actual_review_started=False,
        adaptation='in-memory unique output directory literal only; PLAN points at explicit amended view',
        actual_gate='root9175 actual terminal first; one offline new-batch review only',
        new_fit=0,new_cash=0,API=0,SQL=0,model_inference=0))


def actual(session):
    if session!='9175':raise ValueError('root original corrected-batch handle9175 required')
    source=guard();ready=read(PREP/'readiness.json')
    if bind(ready['review_plan']['path'])!=ready['review_plan']:raise ValueError('prepared review view changed')
    for key in ('operational_amendment','acquisition_authorization'):
        if bind(ready[key]['path'])!=ready[key]:raise ValueError('prepared411 binding changed')
    old_literal="out=OUT/'actual_run1'"
    if source.count(old_literal)!=1:raise ValueError('unique mechanical review-output adaptation required')
    source=source.replace(old_literal,"out=OUT/'actual_run2_network_corrected'")
    env=dict(__name__='stage414_original362_reuse',__file__=str(Path(__file__).resolve()))
    exec(compile(source,str(OLD)+'[output-directory-only-adaptation]','exec'),env)
    env['PLAN']=PREP/'review_plan.json'
    code=env['review'](session)
    receipt=write(FINAL/'network_correction_binding.json',dict(schema='stage414_actual_network_corrected_review_binding_v1',
        review_receipt=bind(FINAL/'actual_receipt.json'),reviewer=bind(__file__),reused362=bind(OLD),
        readiness=bind(PREP/'readiness.json'),review_plan=ready['review_plan'],
        acquisition_authorization=ready['acquisition_authorization'],operational_amendment=ready['operational_amendment'],
        original_failed_attempt_preserved=True,original_review_reparsed=False,source_attempt_number=2,
        strict_original_single_acquisition_adherence=False,attempt3_authorized=False,
        source_session=session,review_exit_code=code,recorded_at=datetime.now(timezone.utc).isoformat(),
        boundary='Attempt2 under explicit411 permission correction; never claim attempt1 or strict original one-acquisition success.'))
    print(json.dumps(receipt));return code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--review',action='store_true')
    p.add_argument('--source-session');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare()))
    else:raise SystemExit(actual(a.source_session))
