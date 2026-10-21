"""External OFF-provider runtime selection; its sidecar is outside the account closure."""
from __future__ import annotations
import argparse
import ast
import importlib
from importlib import metadata,util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import uuid

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
LINE=HERE.parent;ROOT=LINE.parents[2]
SELF=Path(__file__).resolve();BOOT=HERE/'stage109_provider_runtime'
SITE=ROOT/'.py311/lib/python3.11/site-packages'
OUTPUT=LINE/'outputs/stage109_provider_runtime_selection'
PROTOCOL=LINE/'stages/20261018_0752_stage109_provider_runtime_selection_contract.md'
P018=LINE/'outputs/stage018_provider_wait_budget/preflight.json'
P018_SHA='c178b128b39f0a85999a2992f1730d9737d51cd5b5a0b170c649cc97caa738e9'
NUMERIC={'numpy':'numpy','pandas':'pandas','scipy':'scipy','sklearn':'scikit-learn','joblib':'joblib'}
ENDPOINTS=('TQ_AUTH_URL','TQ_MD_URL','TQ_INS_URL','TQ_TD_URL')


def _scope():
    if str(HERE)not in sys.path:sys.path.insert(0,str(HERE))
    import stage087_off_data_scope as scope
    return scope


def binding(path):
    raw=_scope().regular_bytes(path)
    return dict(sha256=_scope().sha_bytes(raw),bytes=len(raw))


def bound_json(path,digest):
    raw=_scope().regular_bytes(path)
    if _scope().sha_bytes(raw)!=digest:raise ValueError('stage109_bound_json_changed')
    return json.loads(raw)


def own_sources():return {str(path):binding(path)for path in (SELF,BOOT/'sitecustomize.py')}


def endpoints():
    if any(os.environ.get(name)for name in ENDPOINTS):raise ValueError('stage109_endpoint_override')


def owner_inputs(path,digest):
    path=Path(path).absolute();owner=bound_json(path,digest);scope=_scope()
    if(owner.get('schema')!='stage087_off_owner_v1'or owner.get('fixture_only')is not False
        or owner.get('arm')not in {'A_OFF','B_OFF'}or owner.get('attempt')!=1
        or path!=scope.OUTPUT_ROOT/owner['arm']/owner['run_id']/'owner.json'
        or Path(owner['account_output'])!=scope.ACCOUNT_ROOT/owner['arm']):
        raise ValueError('stage109_actual_owner_identity_required')
    rows={str(path):binding(path)}
    for label in ('run_context','preflight','execution_readiness','data_scope_review'):
        item=Path(owner[label+'_path']);bound_json(item,owner[label+'_sha256']);rows[str(item)]=binding(item)
    for source in (scope.SOURCE,scope.PROVIDER,HERE/'stage022_run_c0_qualified_wait.py'):
        row=binding(source)
        if row['sha256']!=owner['source_fingerprints'].get(str(source)):raise ValueError('stage109_owner_source_changed')
    return owner,rows


def sdk_identity():
    accepted=bound_json(P018,P018_SHA)['source_fingerprints'];distribution=metadata.distribution('tqsdk')
    sdk=Path(distribution.locate_file('tqsdk')).absolute();dist=Path(distribution._path).absolute()
    spec=util.find_spec('tqsdk')
    if(distribution.version!='3.10.2'or sdk!=SITE/'tqsdk'
        or dist!=SITE/'tqsdk-3.10.2.dist-info'or spec is None or Path(spec.origin)!=sdk/'__init__.py'):
        raise ValueError('stage109_real_sdk_selection_changed')
    rows={}
    for name in ('api.py','auth.py','tradeable/sim/tqsim.py','backtest/backtest.py','tools/downloader.py'):
        path=sdk/name;row=binding(path)
        if row['sha256']!=accepted.get(str(path)):raise ValueError('stage109_accepted_sdk_source_changed')
        rows[str(path)]=row
    return dict(sdk_version=distribution.version,sdk_package=str(sdk),sdk_dist_info=str(dist),
        sdk_metadata_binding=binding(dist/'METADATA'),sdk_init_binding=binding(sdk/'__init__.py'),
        sdk_accepted_source_bindings=rows,sdk_imported='tqsdk'in sys.modules)


def bootstrap_from_env():
    """Executed in every new interpreter before its unmodified CLI body."""
    endpoints();scope=_scope()
    path=Path(os.environ['STAGE109_MANIFEST']);document=bound_json(path,os.environ['STAGE109_MANIFEST_SHA256'])
    if(document.get('schema')!='stage109_external_provider_runtime_v1'
        or path.parent.parent!=OUTPUT/'sessions'):raise ValueError('stage109_sidecar_not_owned')
    for group in ('source_bindings','owner_bindings'):
        for name,row in document[group].items():
            if binding(Path(name))!=row:raise ValueError('stage109_sidecar_input_changed')
    owner_inputs(document['owner_path'],document['owner_sha256'])
    import stage022_run_c0_qualified_wait as runtime
    folder=path.parent/'runtime'/str(os.getpid());saved=runtime.OUTPUT
    try:
        runtime.OUTPUT=folder
        runtime.configure_runtime(folder/'shared_empty')
    finally:runtime.OUTPUT=saved
    numeric={}
    for name,distribution_name in NUMERIC.items():
        module=importlib.import_module(name);source=Path(module.__file__).resolve()
        frozen_distribution=next(item for item in metadata.distributions(path=[str(runtime.FROZEN_SITE)])
            if item.metadata['Name'].lower().replace('_','-')==distribution_name)
        if not source.is_relative_to(runtime.FROZEN_SITE)or module.__version__!=frozen_distribution.version:
            raise ValueError('stage109_numeric_runtime_changed:'+name)
        numeric[name]=dict(file=str(source),version=module.__version__)
    # Original helper imports add their project directory once. Finish that
    # definition-only initialization before selecting the SDK search order.
    scope.deps()
    if 'tqsdk'in sys.modules:raise ValueError('stage109_sdk_imported_before_selection')
    sys.path[:]=[str(SITE),*[item for item in sys.path if item!=str(SITE)]]
    if not scope.numeric_runtime_is_frozen():raise ValueError('stage109_numeric_guard_false')
    sdk=sdk_identity()
    if sdk!=document['sdk_identity']:raise ValueError('stage109_sdk_sidecar_changed')
    third_party={}
    for name in ('requests','aiohttp','websockets','certifi','jwt','psutil','packaging','threadpoolctl'):
        module=sys.modules.get(name);spec=util.find_spec(name)
        third_party[name]=dict(preloaded=module is not None,file=getattr(module,'__file__',None),
            selected_origin=None if spec is None else spec.origin)
    receipt=dict(schema='stage109_interpreter_identity_v1',pid=os.getpid(),ppid=os.getppid(),argv=sys.argv,
        python_executable=sys.executable,owner_path=document['owner_path'],owner_sha256=document['owner_sha256'],
        manifest_path=str(path),manifest_sha256=os.environ['STAGE109_MANIFEST_SHA256'],
        source_bindings=document['source_bindings'],runtime_review=document['runtime_review'],
        original_scope_review=document['original_scope_review'],numeric_modules=numeric,frozen_site=str(runtime.FROZEN_SITE),
        numeric_runtime_is_frozen=True,third_party_resolution=third_party,
        unpreloaded_third_party_not_covered_by_numeric_freeze=True,credentials_read=False,network_calls=0,**sdk)
    scope.atomic(path.parent/'interpreters'/('pid_'+str(os.getpid())+'.json'),receipt)


def probe_generation(generation):
    scope=_scope();path=Path(os.environ['STAGE109_MANIFEST'])
    receipt=json.loads(scope.regular_bytes(path.parent/'interpreters'/('pid_'+str(os.getpid())+'.json')))
    before=list(sys.path);scope.deps()
    if before!=sys.path:raise ValueError('stage109_deps_reordered_runtime')
    import stage087_off_data_provider as provider
    lines,first=inspect.getsourcelines(provider.sdk_preflight)
    tree=ast.parse(textwrap.dedent(''.join(lines)))
    stop_line=first+next(node.lineno for node in ast.walk(tree)if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Attribute)and node.func.attr=='load_credentials')-1
    class BeforeCredentials(Exception):pass
    def trace(frame,event,arg):
        if frame.f_code is provider.sdk_preflight.__code__ and event=='line'and frame.f_lineno==stop_line:
            raise BeforeCredentials
        return trace
    previous=sys.gettrace();passed=False
    try:
        sys.settrace(trace)
        try:provider.sdk_preflight(scope.Bindings())
        except BeforeCredentials:passed=True
    finally:sys.settrace(previous)
    if not passed:raise ValueError('stage109_original_version_guard_not_observed')
    receipt.update(generation=generation,deps_sys_path_unchanged=True,
        original_version_endpoint_guard_passed=True,full_sdk_preflight_completed=False)
    rows=[receipt]
    if generation<2:
        child,_=scope.invoke([SELF,'--probe-generation',str(generation+1)],40)
        rows.extend(child['generations'])
    return dict(generations=rows)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner',type=Path);parser.add_argument('--owner-sha256')
    parser.add_argument('--probe-only',action='store_true')
    parser.add_argument('--probe-generation',type=int,choices=range(3))
    parser.add_argument('--runtime-review',type=Path);parser.add_argument('--runtime-review-sha256')
    parser.add_argument('--target',choices=('scope','provider'),default='scope')
    parser.add_argument('arguments',nargs=argparse.REMAINDER);args=parser.parse_args(argv)
    if args.probe_generation is not None:
        print(json.dumps(probe_generation(args.probe_generation)));return 0
    endpoints();scope=_scope()
    if args.owner is None or not args.owner_sha256:raise ValueError('stage109_owner_required')
    owner,owner_bindings=owner_inputs(args.owner,args.owner_sha256)
    review=None
    if not args.probe_only:
        if args.runtime_review is None or not args.runtime_review_sha256:raise ValueError('stage109_independent_runtime_review_required')
        value=bound_json(args.runtime_review,args.runtime_review_sha256)
        if(value.get('independent_review')is not True or value.get('p0_findings')!=0 or value.get('p1_findings')!=0
            or value.get('source_bindings')!=own_sources()):raise ValueError('stage109_runtime_not_independently_accepted')
        review=dict(path=str(args.runtime_review.absolute()),sha256=args.runtime_review_sha256)
        owner_bindings[review['path']]=binding(args.runtime_review)
        scope.load_owner(args.owner,args.owner_sha256)  # Original live PID/owner gates, unchanged.
    source_bindings=own_sources()
    for path in (scope.SOURCE,scope.PROVIDER,HERE/'stage022_run_c0_qualified_wait.py',PROTOCOL):
        source_bindings[str(path)]=binding(path)
    folder=OUTPUT/'sessions'/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
    sdk=sdk_identity()
    arguments=args.arguments[1:]if args.arguments[:1]==['--']else args.arguments
    if args.probe_only:command=[sys.executable,str(SELF),'--probe-generation','0']
    else:
        def argument(name):
            found=[arguments[i+1]for i,item in enumerate(arguments[:-1])if item==name]
            if len(found)!=1:raise ValueError('stage109_target_owner_argument_required')
            return found[0]
        if(Path(argument('--owner')).absolute()!=args.owner.absolute()or argument('--owner-sha256')!=args.owner_sha256):
            raise ValueError('stage109_target_owner_mismatch')
        command=[sys.executable,str(scope.SOURCE if args.target=='scope'else scope.PROVIDER),*arguments]
    manifest=dict(schema='stage109_external_provider_runtime_v1',probe_only=args.probe_only,
        owner_path=str(args.owner.absolute()),owner_sha256=args.owner_sha256,owner_bindings=owner_bindings,
        source_bindings=source_bindings,sdk_identity=sdk,runtime_review=review,
        original_scope_review=dict(path=owner['data_scope_review_path'],sha256=owner['data_scope_review_sha256']),
        command=command,python_executable=sys.executable,old_financial_context_includes_this_sidecar=False,
        limits_unchanged=True,automatic_retry=False)
    scope.atomic(folder/'manifest.json',manifest);digest=scope.sha(folder/'manifest.json')
    env=os.environ.copy();env.update(PYTHONPATH=str(BOOT),PYTHONDONTWRITEBYTECODE='1',
        STAGE109_MANIFEST=str(folder/'manifest.json'),STAGE109_MANIFEST_SHA256=digest)
    if args.probe_only:
        completed=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        if completed.returncode:raise ValueError('stage109_probe_failed:'+completed.stderr[-300:])
        result=json.loads(completed.stdout.splitlines()[-1])
    else:
        process=subprocess.Popen(command,cwd=ROOT,env=env)
        code=process.wait()
        result=dict(exit_code=code)
    result.update(manifest_path=str(folder/'manifest.json'),manifest_sha256=digest)
    scope.atomic(folder/'launcher_terminal.json',result)
    print(json.dumps(result));return result.get('exit_code',0)


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print('stage109_launcher_failed:'+type(error).__name__+':'+str(error),file=sys.stderr);raise SystemExit(78)
