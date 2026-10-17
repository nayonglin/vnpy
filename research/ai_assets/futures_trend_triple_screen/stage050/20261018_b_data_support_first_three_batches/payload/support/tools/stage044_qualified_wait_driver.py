"""Bounded orchestration of one live B engine's actual qualified-data waits.

Never starts a financial engine or signs independent data qualification.
Resolver/qualifier/provider sources are explicit, hash-pinned CLI dependencies.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
LINE = Path(__file__).resolve().parents[1]
WAIT = LINE/'outputs/stage036_b_ts_account/B_TS/data_wait'
OUTPUT = LINE/'outputs/stage044_qualified_wait_driver'
PROTOCOL = LINE/'stages/20261018_0409_stage044_bounded_actual_wait_driver_contract.md'
RUNNER = LINE/'tools/stage036_run_b_ts_checkpoint.py'
RUNNER_SHA = '34563257e25e49b19c9631e06cd9107fc26cfd954713739e01a1bf67d574ff43'
PROVIDER = LINE/'tools/stage041_exact_daily_request_provider.py'
QUALIFIER = LINE/'outputs/stage043_exact_request_delivery/review_provider_delivery.py'
PROVIDER_OUTPUT = LINE/'outputs/stage041_exact_daily_request_provider'
ALLOWED_PROVIDERS = {str(PROVIDER): PROVIDER_OUTPUT,
    str(LINE/'tools/stage037_b_ts_request_provider.py'): LINE/'outputs/stage037_b_ts_request_provider'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.tmp.{os.getpid()}')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    os.replace(temp,path)


def engine_identity(pid):
    if pid!=21822:raise ValueError('only_original_B_attempt1_PID_21822_is_authorized')
    process=subprocess.run(['ps','-ww','-p',str(pid),'-o','lstart=','-o','args='],capture_output=True,text=True,check=True)
    identity=process.stdout.strip()
    if RUNNER.name not in identity or '--run' not in identity or not identity:
        raise ValueError('original_B_engine_command_not_live')
    if sha(RUNNER)!=RUNNER_SHA:raise ValueError('B_engine_source_changed')
    return identity


def current_request(wait_root=WAIT):
    wait_root=Path(wait_root).resolve();audit=wait_root/'audit.json'
    if not audit.is_file():raise ValueError('no_real_engine_wait_audit')
    rows=load(audit)
    if not rows or rows[-1].get('status')!='waiting_for_independent_data':
        return None
    row=rows[-1];path=Path(row['request_path'])
    if not path.is_absolute() or path.parent.parent!=wait_root or path.name!='request.json':
        raise ValueError('request_outside_real_engine_wait_root')
    digest=row['request_sha256'];actual=sha(path)
    request=load(path);payload={k:v for k,v in request.items()if k!='request_sha256'}
    canonical=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    expected=dict(request_sha256=digest,request_file_sha256=actual,request_path=str(path))
    if (canonical!=digest or request.get('request_sha256')!=digest or actual!=row['request_file_sha256'] or
        path.parent.name!='request_'+digest or load(path.parent/'request_fingerprint.json')!=expected or
        request.get('schema')!='stage021_exact_execution_minute_request_v1'):
        raise ValueError('actual_request_fingerprint_or_canonical_digest_changed')
    return dict(request=request,path=path,digest=digest,file_sha=actual)


def provider_action(packet):
    packet=Path(packet);attempt=packet/'network_attempt1'
    if not attempt.exists():return 'prepare' if not(packet/'packet_manifest.json').exists() else 'run'
    parent=attempt/'parent_receipt.json';terminal=packet/'terminal_observed.json'
    if not parent.is_file() or not terminal.is_file():
        raise ValueError('existing_provider_attempt_incomplete_no_retry')
    p,t=load(parent),load(terminal)
    if (p.get('exit_code')!=0 or p.get('all_inputs_unchanged')is not True or
        t.get('terminal_observed')is not True or t.get('exit_code')!=0 or
        t.get('parent_receipt_sha256')!=sha(parent)):
        raise ValueError('existing_provider_attempt_failed_or_unproven_no_retry')
    return 'consume'


def call(argv, timeout):
    process=subprocess.Popen([sys.executable,*map(str,argv)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,start_new_session=True)
    try:stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.wait()
        raise TimeoutError('bounded_child_command_timeout_no_retry')
    if process.returncode!=0:
        raise ValueError(f'child_exit_{process.returncode}:{Path(argv[0]).name}:{stdout[-1000:]}')
    lines=[line for line in stdout.splitlines()if line.strip()]
    result=json.loads(lines[-1])if lines else {}
    return result,dict(subprocess_pid=process.pid,subprocess_returncode=process.returncode,terminal_observed=True)


def publish(current, receipt_path, receipt_sha):
    import stage021_blocking_data_gate as gate
    receipt_path=Path(receipt_path)
    if not receipt_path.is_absolute():raise ValueError('receipt_must_be_absolute')
    gate._read_delivery(current['request'],gate.QualifiedDelivery(receipt_path,receipt_sha))
    receipt=load(receipt_path)
    for path,digest in receipt['source_fingerprints'].items():
        if sha(path)!=digest:raise ValueError('independent_receipt_source_drift')
    fresh=current_request()
    if fresh is None or fresh['digest']!=current['digest']:raise ValueError('engine_wait_changed_before_publish')
    pointer=dict(schema='stage022_delivery_pointer_v1',request_sha256=current['digest'],
                 receipt_path=str(receipt_path),receipt_sha256=receipt_sha)
    target=current['path'].parent/'response.json'
    if target.exists():
        if load(target)!=pointer:raise ValueError('existing_response_conflict')
    else:atomic(target,pointer)
    return dict(response_path=str(target),response_sha256=sha(target),receipt_path=str(receipt_path),receipt_sha256=receipt_sha,
                data_path=receipt['data_path'],data_sha256=receipt['data_sha256'])


def checked_binding(bindings, selection):
    fields=('provider_path','provider_sha256','reviewer_path','reviewer_sha256')
    found=[row for row in bindings if all(row.get(key)==selection.get(key)for key in fields)]
    if len(found)!=1:raise ValueError('resolver_provider_or_reader_not_in_root_frozen_allowlist')
    return found[0]


def existing_binding(bindings, digest):
    found=[]
    for row in bindings:
        packet=Path(row['output_root'])/('request_'+digest)/'packet_000'
        if packet.exists():found.append((row,packet))
    if len(found)>1:raise ValueError('multiple_provider_scopes_for_same_request')
    return found[0] if found else (None,None)


def prepare(args):
    if not 1<=args.max_providers<=4 or not 840<=args.budget_seconds<=3600:
        raise ValueError('first_batch_budget_outside_contract')
    if not args.batch_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in args.batch_id):
        raise ValueError('invalid_batch_id')
    folder=OUTPUT/args.batch_id
    if folder.exists():raise FileExistsError('existing_batch_refusing_overwrite')
    if args.provider_bindings:
        bindings=load(Path(args.provider_bindings).resolve())['providers']
    else:
        bindings=[dict(provider_path=str(PROVIDER),provider_sha256=args.provider_sha256,
            reviewer_path=str(QUALIFIER),reviewer_sha256=args.qualifier_sha256,reviewer_output_root=str(QUALIFIER.parent))]
    if not bindings or len(bindings)>2:raise ValueError('provider_allowlist_count_invalid')
    seen=set()
    for row in bindings:
        provider_path=row['provider_path'];reviewer=Path(row['reviewer_path'])
        if provider_path not in ALLOWED_PROVIDERS or provider_path in seen:
            raise ValueError('only_root_frozen_037_and_041_providers_allowed_once')
        seen.add(provider_path)
        if (not reviewer.is_absolute()or not reviewer.is_relative_to(LINE.resolve())or
            sha(provider_path)!=row['provider_sha256']or sha(reviewer)!=row['reviewer_sha256']):
            raise ValueError('frozen_provider_or_reader_SHA_mismatch')
        receipt_root=Path(row['reviewer_output_root'])
        if not receipt_root.is_absolute()or not receipt_root.resolve().is_relative_to((LINE/'outputs').resolve()):
            raise ValueError('root_bound_reviewer_output_must_be_inside_line_outputs')
        row['reviewer_output_root']=str(receipt_root.resolve())
        row['output_root']=str(ALLOWED_PROVIDERS[provider_path])
    resolver=Path(args.resolver).resolve()if args.resolver else None
    if resolver is not None and sha(resolver)!=args.resolver_sha256:raise ValueError('resolver_SHA_mismatch')
    current_request()  # No provider and no pointer during preparation.
    identity=engine_identity(args.engine_pid)
    paths=[Path(__file__),PROTOCOL,RUNNER,LINE/'tools/stage021_blocking_data_gate.py']
    for row in bindings:paths.extend([Path(row['provider_path']),Path(row['reviewer_path'])])
    if resolver is not None:paths.append(resolver)
    manifest=dict(schema='stage044_bounded_actual_wait_batch_v1',batch_id=args.batch_id,engine_pid=args.engine_pid,
        engine_identity=identity,wait_root=str(WAIT),max_provider_connections=args.max_providers,budget_seconds=args.budget_seconds,
        resolver_path=str(resolver)if resolver else None,resolver_sha256=args.resolver_sha256,
        provider_bindings=bindings,
        source_fingerprints={str(p.resolve()):sha(p)for p in paths},provider_connections=0,financial_replays=0,
        model_fits=0,orders=0,response_written=False,independent_review_signed=False,production_qualified=False)
    folder.mkdir(parents=True,exist_ok=False);atomic(folder/'manifest.json',manifest)
    print(json.dumps(dict(status='prepared_no_network',manifest_path=str((folder/'manifest.json').resolve()),manifest_sha256=sha(folder/'manifest.json'))))


def run(manifest_path, source_sha):
    manifest_path=Path(manifest_path).resolve();manifest=load(manifest_path);folder=manifest_path.parent
    if folder.parent!=OUTPUT.resolve() or manifest_path.name!='manifest.json':raise ValueError('batch_manifest_path_invalid')
    if sha(__file__)!=source_sha or manifest['source_fingerprints'].get(str(Path(__file__).resolve()))!=source_sha:
        raise ValueError('explicit_reviewed_driver_SHA_required')
    if(folder/'journal.json').exists():raise FileExistsError('batch_already_started_use_new_explicit_batch')
    began=time.monotonic();journal=dict(status='running',started_at=datetime.now().astimezone().isoformat(),
        driver_pid=os.getpid(),source_sha256=source_sha,manifest_sha256=sha(manifest_path),provider_connections=0,events=[])
    def save():
        journal['elapsed_seconds']=time.monotonic()-began;atomic(folder/'journal.json',journal)
    def invoke(argv, timeout):
        remaining=manifest['budget_seconds']-(time.monotonic()-began)
        if remaining<=0:raise TimeoutError('total_driver_budget_exhausted')
        return call(argv,min(timeout,remaining))
    def verify():
        for path,digest in manifest['source_fingerprints'].items():
            if sha(path)!=digest:raise ValueError('frozen_driver_dependency_drift')
        if engine_identity(manifest['engine_pid'])!=manifest['engine_identity']:raise ValueError('original_engine_PID_identity_changed')
    try:
        while True:
            verify();save()
            if time.monotonic()-began>=manifest['budget_seconds']:
                journal['status']='paused_batch_budget';break
            current=current_request()
            if current is None:time.sleep(.5);continue
            if(current['path'].parent/'response.json').exists():time.sleep(.5);continue
            event=dict(request_sha256=current['digest'],request_path=str(current['path']),request_file_sha256=current['file_sha'])
            journal['events'].append(event);save()
            binding,packet=existing_binding(manifest['provider_bindings'],current['digest'])
            action=provider_action(packet)if packet is not None else 'resolve'
            if action=='resolve':
                if not manifest.get('resolver_path'):raise ValueError('no_frozen_independent_local_daily_resolver')
                resolver_argv=[manifest['resolver_path'],'--request',current['path'],'--request-file-sha256',current['file_sha']]
                for allowed in manifest['provider_bindings']:
                    label='041'if allowed['provider_path']==str(PROVIDER)else'037'
                    resolver_argv += ['--reviewer'+label+'-path',allowed['reviewer_path'],
                                      '--reviewer'+label+'-sha256',allowed['reviewer_sha256']]
                resolved,evidence=invoke(resolver_argv,120)
                event.update(resolver_result=resolved,resolver_terminal=evidence);save()
                if resolved.get('request_sha256')!=current['digest']:raise ValueError('resolver_request_scope_mismatch')
                if resolved.get('status')=='accepted':
                    verify();event.update(publish(current,resolved['receipt_path'],resolved['receipt_sha256']),source='local');save();continue
                if resolved.get('status')!='needs_provider':raise ValueError('independent_resolver_blocked')
                if resolved.get('packet_count',1)!=1:raise ValueError('multi_packet_request_not_supported')
                binding=checked_binding(manifest['provider_bindings'],resolved)
                packet=Path(binding['output_root'])/('request_'+current['digest'])/'packet_000'
                action=provider_action(packet)
                if action!='prepare':raise ValueError('provider_scope_appeared_during_resolution')
            if action=='prepare':
                if binding is None or packet.exists():raise ValueError('existing_partial_packet_no_overwrite')
                argv=[binding['provider_path'],'--prepare','--request',current['path'],'--request-file-sha256',current['file_sha']]
                if binding['provider_path']==str(PROVIDER):
                    daily=Path(resolved['daily_review_path']);daily_sha=resolved['daily_review_sha256']
                    if not daily.is_absolute() or sha(daily)!=daily_sha:raise ValueError('signed_daily_reference_unbound')
                    argv+=['--daily-review-path',daily,'--daily-review-sha256',daily_sha]
                elif resolved.get('daily_review_path')or resolved.get('daily_review_sha256'):
                    raise ValueError('037_must_not_receive_new_daily_reference')
                _,evidence=invoke(argv,120)
                event['prepare_terminal']=evidence;save();action=provider_action(packet)
            event['provider_binding']=binding;save()
            if action=='run':
                if journal['provider_connections']>=manifest['max_provider_connections']:
                    journal['status']='paused_provider_batch_limit';break
                if manifest['budget_seconds']-(time.monotonic()-began)<840:
                    journal['status']='paused_insufficient_full_provider_budget';break
                saved=load(packet/'preflight.json');preflight_digest=sha(packet/'preflight.json')
                if saved.get('packet_count')!=1 or saved.get('covers_whole_request')is not True:raise ValueError('multi_packet_request_not_supported')
                verify();journal['provider_connections']+=1;event['provider_launch_reserved']=True;save()
                _,evidence=invoke([binding['provider_path'],'--run','--packet-dir',packet],660)
                parent=packet/'network_attempt1/parent_receipt.json';p=load(parent)
                if (p.get('exit_code')!=0 or p.get('all_inputs_unchanged')is not True or
                    sha(packet/'preflight.json')!=preflight_digest):raise ValueError('provider_parent_or_saved_preflight_not_accepted')
                terminal=dict(schema='stage041_provider_actual_tool_terminal_v1',observed_at=datetime.now().astimezone().isoformat(),
                    **evidence,exit_code=0,all_inputs_unchanged=True,request_sha256=current['digest'],source_sha256=sha(binding['provider_path']),provider_source_path=binding['provider_path'],
                    preflight_sha256=sha(packet/'preflight.json'),parent_receipt_sha256=sha(parent),driver_pid=os.getpid(),
                    driver_source_path=str(Path(__file__).resolve()),driver_source_sha256=source_sha,
                    parent_status=p['status'],worker_exit_code=p['exit_code'],new_provider_connections=1,new_minute_provider_connections=1,
                    financial_replays=0,model_fits=0,orders=0,production_qualified=False)
                atomic(packet/'terminal_observed.json',terminal);event['provider_terminal']=terminal;save()
            terminal=packet/'terminal_observed.json'
            signed_result=Path(binding['reviewer_output_root'])/('request_'+current['digest'])/'parse_result.json'
            if signed_result.exists():
                result=load(signed_result);evidence=dict(reused_signed_parse_result_path=str(signed_result),parse_result_sha256=sha(signed_result))
                receipt=load(result['receipt_path'])
                if receipt.get('source_fingerprints',{}).get(binding['reviewer_path'])!=binding['reviewer_sha256']:
                    raise ValueError('existing_signed_result_reader_source_not_bound')
            else:
                result,evidence=invoke([binding['reviewer_path'],'--packet-dir',packet,'--terminal-sha256',sha(terminal)],120)
            if result.get('status')!='accepted' or result.get('request_sha256')!=current['digest']:
                raise ValueError('independent_provider_qualification_not_accepted')
            verify();event.update(qualifier_terminal=evidence,source='provider',**publish(current,result['receipt_path'],result['receipt_sha256']));save()
    except BaseException as error:
        journal.update(status='blocked',blocked_reason=f'{type(error).__name__}:{error}');save()
        print(json.dumps(dict(status='blocked',reason=journal['blocked_reason'],journal_path=str(folder/'journal.json'))));return 1
    save();print(json.dumps(dict(status=journal['status'],provider_connections=journal['provider_connections'],journal_path=str(folder/'journal.json'))));return 0


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--run',action='store_true')
    p.add_argument('--batch-id');p.add_argument('--engine-pid',type=int,default=21822);p.add_argument('--provider-sha256')
    p.add_argument('--qualifier-sha256');p.add_argument('--provider-bindings');p.add_argument('--resolver');p.add_argument('--resolver-sha256')
    p.add_argument('--max-providers',type=int,default=4);p.add_argument('--budget-seconds',type=int,default=3600)
    p.add_argument('--manifest');p.add_argument('--source-sha256');args=p.parse_args()
    try:
        if args.prepare:prepare(args);return 0
        return run(args.manifest,args.source_sha256)
    except Exception as error:
        print(json.dumps(dict(status='blocked',reason=f'{type(error).__name__}:{error}')));return 1


if __name__=='__main__':raise SystemExit(main())
