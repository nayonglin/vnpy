"""OFF exact-wait ownership, independent qualification and bounded orchestration.

Stdlib bootstrap. The financial runner never starts this tool. Root supplies a
real, immutable owner after observing its process. No fixture CLI bypass exists.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
TOOLS = LINE/'tools'
OUTPUT_ROOT = LINE/'outputs/stage087_off_data_scope'
ACCOUNT_ROOT = LINE/'outputs/stage065_pairwise_off_account'
PROTOCOL = LINE/'stages/20261018_0639_stage087_off_data_scope_contract.md'
PROVIDER = TOOLS/'stage087_off_data_provider.py'
SOURCE = Path(__file__).resolve()
PINS = {
 'stage045_exact_request_resolver.py':'597551c51a021f763318086e4e3084bd5a54aa03abb8d4b038f63d131f8d02df',
 'stage052_generic_daily_source_resolver.py':'5b2772c700f0ddabb5536df4be1bfe1f70e07d8fea43400abfa74c66ae727b78',
 'stage037_b_ts_request_provider.py':'19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1',
 'stage041_exact_daily_request_provider.py':'e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d',
 'stage051_generic_exact_daily_recovery.py':'89a2de7464f4b30eb3b3887ac265ca5433c7288fafcb117802072360c6a6228a',
 'stage021_blocking_data_gate.py':'150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b',
 'stage022_run_c0_qualified_wait.py':'aaa0cc50c7c817c885afd6eb3630b28f714da21486a1ec2dfb8fbeb39437582c',
}


def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def regular_bytes(path):
    path=Path(path).absolute()
    if any(p.is_symlink()for p in (path,*path.parents)):raise ValueError('scope_symlink_not_allowed')
    if not path.is_file():raise ValueError('scope_regular_file_required:'+str(path))
    return path.read_bytes()
def sha(path):return sha_bytes(regular_bytes(path))
def json_bytes(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def atomic(path,value,*,replace=False):
    path=Path(path)
    if path.exists()and not replace:raise FileExistsError('scope_refuses_overwrite:'+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
    with temp.open('xb')as handle:
        handle.write(json_bytes(value));handle.flush();os.fsync(handle.fileno())
    os.replace(temp,path)
    descriptor=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


class Bindings:
    """New scope JSON/CSV parsing consumes exactly the bytes that were hashed."""
    def __init__(self):self.inputs={};self.payloads={}
    def bind(self,path,expected=None):
        path=str(Path(path).absolute());raw=regular_bytes(path);digest=sha_bytes(raw)
        if expected is not None and digest!=expected:raise ValueError('bound_source_changed:'+path)
        if path in self.inputs and self.inputs[path]!=digest:raise ValueError('bound_source_conflict:'+path)
        self.inputs[path]=digest;self.payloads[path]=raw
        return digest
    def json(self,path,expected=None):
        self.bind(path,expected);return json.loads(self.payloads[str(Path(path).absolute())])
    def csv(self,path,expected=None):
        self.bind(path,expected);return deps().pd.read_csv(io.BytesIO(self.payloads[str(Path(path).absolute())]))
    def unchanged(self):
        for path,digest in self.inputs.items():
            if sha(path)!=digest:raise ValueError('used_source_changed:'+path)


def numeric_runtime_is_frozen():
    import stage022_run_c0_qualified_wait as runtime
    return all(name not in sys.modules or Path(sys.modules[name].__file__).resolve().is_relative_to(runtime.FROZEN_SITE)
        for name in ('numpy','pandas','scipy','sklearn','joblib')) and str(runtime.FROZEN_SITE)in sys.path


def deps():
    import stage022_run_c0_qualified_wait as runtime
    if not numeric_runtime_is_frozen():
        for name in ('numpy','pandas','scipy','sklearn','joblib'):
            if name in sys.modules:raise RuntimeError('configure_frozen_runtime_before_numeric_import:'+name)
        OUTPUT_ROOT.mkdir(parents=True,exist_ok=True)
        saved=runtime.OUTPUT
        try:
            runtime.OUTPUT=OUTPUT_ROOT/'runtime'
            runtime.configure_runtime(Path(tempfile.mkdtemp(prefix='shared_',dir=OUTPUT_ROOT)))
        finally:runtime.OUTPUT=saved
    for name,digest in PINS.items():
        if sha(TOOLS/name)!=digest:raise ValueError('frozen_helper_changed:'+name)
    from types import SimpleNamespace
    import numpy as np
    import pandas as pd
    import stage045_exact_request_resolver as frozen
    import stage052_generic_daily_source_resolver as generic
    import stage041_exact_daily_request_provider as minute
    import stage051_generic_exact_daily_recovery as daily
    return SimpleNamespace(np=np,pd=pd,frozen=frozen,generic=generic,minute=minute,daily=daily,
        old=frozen.old,local=frozen.local,gate=frozen.gate,runtime=runtime)


def process_identity(pid):
    result=subprocess.run(['ps','-ww','-p',str(pid),'-o','lstart=','-o','args='],capture_output=True,text=True,check=True)
    if not result.stdout.strip():raise ValueError('owner_process_not_live')
    return result.stdout.strip()


@dataclass
class Owner:
    path:Path
    sha256:str
    document:dict
    observer:object
    fixture_allowed:bool=False

    def verify(self):
        if sha(self.path)!=self.sha256:raise ValueError('owner_manifest_changed')
        b=Bindings();d=self.document
        for label in ('run_context','preflight','execution_readiness'):
            b.bind(d[label+'_path'],d[label+'_sha256'])
        if not self.fixture_allowed:b.bind(d['data_scope_review_path'],d['data_scope_review_sha256'])
        context=json.loads(b.payloads[str(Path(d['run_context_path']).absolute())])
        if any(context.get(k)!=d[k]for k in ('arm','attempt','run_id'))or context.get('output_directory')!=d['account_output']:
            raise ValueError('owner_context_identity_mismatch')
        if context.get('writer')!='stage065_account_checkpoint.py':raise ValueError('checkpoint_writer_is_not_financial_runner')
        binding=context.get('source_bindings',{}).get(d['runner_path'],{})
        if binding.get('sha256')!=d['runner_sha256']or sha(d['runner_path'])!=d['runner_sha256']:
            raise ValueError('owner_financial_runner_binding_mismatch')
        preflight=json.loads(b.payloads[str(Path(d['preflight_path']).absolute())])
        if preflight.get('source_bindings',{}).get(d['runner_path'])!=binding:
            raise ValueError('owner_runner_preflight_binding_mismatch')
        if not self.fixture_allowed:
            for path in (SOURCE,PROVIDER):
                expected=dict(sha256=d['source_fingerprints'][str(path)],bytes=len(regular_bytes(path)))
                if context.get('source_bindings',{}).get(str(path))!=expected or preflight.get('source_bindings',{}).get(str(path))!=expected:
                    raise ValueError('owner_scope_not_bound_by_financial_runner')
        for path,digest in d['source_fingerprints'].items():b.bind(path,digest)
        if self.observer(d['engine_pid'])!=d['process_identity']:raise ValueError('owner_PID_start_or_args_changed')
        return b


def load_owner(path,digest,*,_observer=None,_allow_fixture=False):
    b=Bindings();path=Path(path).absolute();d=b.json(path,digest)
    fixture=d.get('fixture_only')is True
    if fixture and not(_allow_fixture and _observer is not None):raise ValueError('fixture_owner_forbidden_on_real_CLI')
    if d.get('schema')!='stage087_off_owner_v1'or d.get('arm')not in{'A_OFF','B_OFF'}or d.get('attempt')!=1:
        raise ValueError('invalid_OFF_owner')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',str(d.get('run_id',''))):raise ValueError('invalid_owner_run_id')
    account=Path(d['account_output'])
    if not account.is_absolute()or Path(d['wait_root'])!=account/'data_wait':raise ValueError('owner_wait_root_mismatch')
    if not fixture and(account!=ACCOUNT_ROOT/d['arm']or Path(d['runner_path'])!=TOOLS/'stage065_run_pairwise_off.py'):
        raise ValueError('owner_not_fixed_OFF_account_or_runner')
    if type(d.get('engine_pid'))is not int or d['engine_pid']<=0:raise ValueError('real_positive_owner_PID_required')
    required={str(p)for p in (SOURCE,PROVIDER,TOOLS/'stage021_blocking_data_gate.py',TOOLS/'stage022_run_c0_qualified_wait.py')}
    if not required.issubset(d.get('source_fingerprints',{})):raise ValueError('owner_source_scope_bindings_missing')
    if not fixture:
        if str(PROTOCOL)not in d['source_fingerprints']:raise ValueError('owner_scope_contract_binding_missing')
        tokens=shlex.split(d['process_identity'])
        if '--run'not in tokens or '--arm'not in tokens or tokens[tokens.index('--arm')+1]!=d['arm']:
            raise ValueError('owner_command_arm_run_mismatch')
        if not any(Path(t).name==Path(d['runner_path']).name for t in tokens):raise ValueError('owner_runner_command_missing')
        review=b.json(d['data_scope_review_path'],d['data_scope_review_sha256'])
        expected={str(p):dict(sha256=sha(p),bytes=len(regular_bytes(p)))for p in (SOURCE,PROVIDER)}
        if review.get('independent_review')is not True or review.get('p0_findings')!=0 or review.get('p1_findings')!=0 or review.get('source_bindings')!=expected:
            raise ValueError('independent_OFF_scope_review_missing')
    owner=Owner(path,digest,d,_observer or process_identity,fixture)
    owner.verify();return owner


def read_actual_request(owner,request_path,request_file_sha256):
    owner.verify();path=Path(request_path).absolute();root=Path(owner.document['wait_root'])
    if path.name!='request.json'or path.parent.parent!=root:raise ValueError('request_outside_owner_wait_root')
    b=Bindings();request=b.json(path,request_file_sha256);digest=request.get('request_sha256')
    g=deps().gate
    if request.get('schema')!=g.REQUEST_SCHEMA or g.request_sha256(request)!=digest or path.parent.name!='request_'+str(digest):
        raise ValueError('actual_request_digest_or_schema_mismatch')
    fingerprint=path.with_name('request_fingerprint.json')
    if b.json(fingerprint)!=dict(request_path=str(path),request_file_sha256=request_file_sha256,request_sha256=digest):
        raise ValueError('actual_request_fingerprint_mismatch')
    audit=json.loads(regular_bytes(root/'audit.json'))
    expected=dict(status='waiting_for_independent_data',request_path=str(path),request_file_sha256=request_file_sha256,request_sha256=digest)
    if not audit or any(audit[-1].get(k)!=v for k,v in expected.items()):raise ValueError('request_not_current_owner_wait')
    return dict(request=request,path=path,file_sha=request_file_sha256,digest=digest,wait=audit[-1],inputs=b.inputs)


def current_request(owner):
    owner.verify();root=Path(owner.document['wait_root']);rows=json.loads(regular_bytes(root/'audit.json'))
    if not rows or rows[-1].get('status')!='waiting_for_independent_data':return None
    return read_actual_request(owner,rows[-1]['request_path'],rows[-1]['request_file_sha256'])


def request_directory(owner,current):
    d=owner.document
    return OUTPUT_ROOT/d['arm']/d['run_id']/('request_'+current['digest'])


def owner_bindings(owner,current,b):
    owner.verify();b.bind(owner.path,owner.sha256)
    for label in ('run_context','preflight','execution_readiness'):b.bind(owner.document[label+'_path'],owner.document[label+'_sha256'])
    for path,digest in owner.document['source_fingerprints'].items():b.bind(path,digest)
    for path,digest in current['inputs'].items():b.bind(path,digest)
    for name,digest in PINS.items():b.bind(TOOLS/name,digest)
    b.bind(PROTOCOL)


def gate_parser(current,receipt,digest):
    return deps().gate._read_delivery(current['request'],deps().gate.QualifiedDelivery(Path(receipt),digest))


def _proofs(frame,evidence,*,network):
    d=deps();pd=d.pd;proof=set()
    for row in evidence.to_dict('records'):
        stamp=pd.Timestamp(row['bar_datetime']);successor=pd.Timestamp(row['successor_time'])
        if successor.tzinfo:successor=successor.tz_convert('Asia/Shanghai').tz_localize(None)
        if successor<stamp+pd.Timedelta(minutes=1):raise ValueError('cached_forward_completion_missing')
        if network:
            if str(row.get('completed')).lower()!='true'or row.get('method')!='observed_later_serial_kline':raise ValueError('cached_observed_completion_missing')
        elif d.frozen.integer(row['source_bar_id'])<0 or d.frozen.integer(row['successor_id'])<=d.frozen.integer(row['source_bar_id']):
            raise ValueError('cached_local_successor_id_invalid')
        proof.add((str(row['vt_symbol']),stamp))
    if not d.gate._keys(frame).issubset(proof):raise ValueError('cached_scope_completion_incomplete')
    return proof


def read_cached_receipt(owner,current,row,b):
    path=Path(row['receipt_path']).absolute()
    allowed=[LINE/'outputs'/name for name in ('stage052_generic_daily_source_resolver','stage048_general_provider_delivery',
        'stage043_exact_request_delivery','stage046_original_provider_delivery')]
    if not any(path.is_relative_to(root)for root in allowed):raise ValueError('cache_source_not_root_whitelisted_or_fixture075')
    receipt=b.json(path,row['receipt_sha256'])
    if receipt.get('fixture_only')is True:raise ValueError('fixture_receipt_not_a_market_source')
    sources=receipt.get('source_fingerprints',{})
    trusted={TOOLS/'stage052_generic_daily_source_resolver.py':PINS['stage052_generic_daily_source_resolver.py'],
        TOOLS/'stage048_general_provider_delivery.py':'3b220aadeb1e8091a35d84624b643c3a0b276c6e3f4be9874293a9abaecd785a',
        TOOLS/'stage046_original_provider_delivery.py':'d0c1fb55b681ad3113a215cba1964e84eaff7c617875ef71ec27f9db018fe65b',
        LINE/'outputs/stage043_exact_request_delivery/review_provider_delivery.py':'373493d9eb50647063044e53c2c669584f237345cf2a8edf8f5d0d282c1b1d54'}
    if not any(sources.get(str(p))==h for p,h in trusted.items()):raise ValueError('cached_independent_reader_identity_missing')
    for source,digest in sources.items():b.bind(source,digest)
    candidates=[]
    for source in sources:
        if Path(source).name=='request.json':
            request=b.json(source,sources[source])
            if request.get('request_sha256')==receipt.get('request_sha256'):candidates.append(request)
    if len(candidates)!=1:raise ValueError('cached_origin_request_not_unique')
    if deps().gate.request_sha256(candidates[0])!=candidates[0].get('request_sha256'):raise ValueError('cached_origin_canonical_digest_mismatch')
    original=candidates[0];data,_,_,_=deps().gate._read_delivery(original,deps().gate.QualifiedDelivery(path,row['receipt_sha256']))
    proof_paths=[p for p in sources if Path(p).name=='completion_evidence.csv'and Path(p).parent==path.parent]
    if len(proof_paths)!=1:raise ValueError('cached_completion_source_missing')
    evidence=deps().old.normal_times(b.csv(proof_paths[0],sources[proof_paths[0]]))
    network_paths=[Path(p)for p in sources if Path(p).name=='raw_completed_minutes.csv']
    for raw_path in network_paths:
        packet=raw_path.parent.parent;terminal_path=packet/'terminal_observed.json';parent_path=raw_path.parent/'parent_receipt.json'
        if str(terminal_path)not in sources or str(parent_path)not in sources:raise ValueError('cached_provider_true_terminal_missing')
        terminal=b.json(terminal_path,sources[str(terminal_path)]);parent=b.json(parent_path,sources[str(parent_path)])
        if(terminal.get('terminal_observed')is not True or terminal.get('exit_code')!=0 or parent.get('exit_code')!=0 or
            parent.get('status')!='worker_terminal'or parent.get('hard_kill')or not parent.get('all_inputs_unchanged')or
            terminal.get('parent_receipt_sha256')!=sources[str(parent_path)]):raise ValueError('cached_provider_not_true_zero')
        if parent.get('artifact_sha256',{}).get(raw_path.name)!=sources[str(raw_path)]:raise ValueError('cached_raw_parent_binding_missing')
    proof=_proofs(data,evidence,network=bool(network_paths))
    return dict(data=data,proof=proof,origin_request_sha256=original['request_sha256'],origin_receipt_path=str(path),
        commit_inheritance=False,failed191_has_no_061_rights=True)


def _raw_local_proofs(sources,required):
    """Extract exactly the actual successor rule used by frozen045; no synthetic rows."""
    d=deps();pd=d.pd;frames=[];proof=set()
    for frame in sources:
        selected=frame.loc[frame.bar_datetime.isin(required)].copy()
        if selected.empty:continue
        # Frozen045 validates the source identity and actual next row. Supplying
        # the complete real source preserves its source_row_number offsets.
        if not{'bar_id','tq_symbol','source_row_number'}.issubset(frame):raise ValueError('local_source_actual_identity_missing')
        if selected.bar_datetime.duplicated().any()or not all(d.frozen.legal(r)for r in selected.to_dict('records')):
            raise ValueError('local_source_duplicate_or_illegal')
        frames.append(selected[d.gate.FIELDS])
        for row in selected.itertuples(index=False):
            position=d.frozen.integer(row.source_row_number)-2
            if position<0 or position+1>=len(frame):continue
            nxt=frame.iloc[position+1];native,exchange=str(row.vt_symbol).split('.')
            if str(nxt.vt_symbol)!=str(row.vt_symbol)or str(nxt.tq_symbol)!=str(row.tq_symbol)or str(row.tq_symbol)!=exchange+'.'+native:
                raise ValueError('local_actual_successor_symbol_conflict')
            ident,next_id=d.frozen.integer(row.bar_id),d.frozen.integer(nxt.bar_id)
            stamp,next_stamp=pd.Timestamp(row.bar_datetime),pd.Timestamp(nxt.bar_datetime)
            if ident<0 or next_id<=ident or next_stamp<stamp+pd.Timedelta(minutes=1)or not d.frozen.legal(nxt):continue
            if any(int(test.sum())!=1 for test in (frame.bar_id.eq(ident),frame.bar_id.eq(next_id),frame.bar_datetime.eq(stamp),frame.bar_datetime.eq(next_stamp))):
                raise ValueError('local_actual_successor_identity_conflict')
            proof.add((str(row.vt_symbol),stamp))
    return frames,proof


def qualify_local_sources(owner,current,contexts,sources,b,*,cached=()):
    d=deps();pd=d.pd;ready={};proofs=[];checks=[]
    for context in contexts:
        target=context['target'];symbol=target['vt_symbol'];kind=target['requirement_kind'];grid=context['grid']
        required=grid if kind=='full_session'else grid[:1]
        raw=sources.get(symbol,[]);raw=raw if isinstance(raw,list)else[raw]
        parts,completed=_raw_local_proofs(raw,required)
        for item in cached:
            selected=item['data'].loc[item['data'].vt_symbol.eq(symbol)&item['data'].bar_datetime.isin(required)]
            if len(selected):parts.append(selected[d.gate.FIELDS]);completed.update(item['proof'])
        if parts:
            data=pd.concat(parts,ignore_index=True)
            duplicated=data.loc[data.bar_datetime.duplicated(keep=False)]
            if len(duplicated):
                groups=duplicated.groupby('bar_datetime')[d.old.VALUES]
                if not d.np.isclose(groups.min().to_numpy(),groups.max().to_numpy(),rtol=1e-12,atol=1e-8).all():raise ValueError('completed_source_conflict')
            data=data.drop_duplicates('bar_datetime').sort_values('bar_datetime')
        else:data=pd.DataFrame(columns=d.gate.FIELDS);data['bar_datetime']=pd.Series(dtype='datetime64[ns]')
        wanted={(symbol,t)for t in required}
        if d.gate._keys(data)!=wanted or not wanted.issubset(completed):
            checks.append(dict(vt_symbol=symbol,accepted=False,reason='exact_required_grid_or_completion_missing'));continue
        check=d.minute.qualify_target(data,completed,dict(target,daily_reference=context['daily']))
        if not check['accepted']:raise ValueError('actual_target_qualification_conflict:'+str(check))
        identity=(symbol,target['execution_trade_date'],kind);ready[identity]=data[d.gate.FIELDS]
        checks.append(check)
        proofs.extend(dict(vt_symbol=s,bar_datetime=t.isoformat(),completed=True)for s,t in wanted)
    if len(ready)!=len(current['request']['requirements']):
        return dict(status='needs_provider',request_sha256=current['digest'],packet_count=1,local_ready_requirements=len(ready),checks=checks)
    data,accepted=d.generic.assemble_delivery(current['request'],ready)
    return _sign_delivery(owner,current,data,accepted,b,checks,proofs)


def _sign_delivery(owner,current,data,accepted,b,checks,proofs):
    d=deps();owner_bindings(owner,current,b)
    existing,new=d.generic.request_key_scope(current['request'])
    added=data.loc[[(str(r.vt_symbol),d.pd.Timestamp(r.bar_datetime))in new for r in data.itertuples(index=False)]]
    if len(added)!=len(new):raise ValueError('new_physical_key_filter_mismatch')
    if not owner.fixture_allowed:
        manifest=b.json(d.old.OLD/'input_manifest.json',d.frozen.OLD_MANIFEST_SHA)
        calendar=d.pd.DatetimeIndex(d.pd.to_datetime(sorted(b.csv(d.old.MAPPING,manifest[str(d.old.MAPPING.relative_to(ROOT))]).date.unique())))
        a=d.old.A0/'execution_anchor_requests.csv';s=d.old.A0/'minute_scan_requests.csv'
        disjoint=d.old.prove_read_disjointness(added,b.csv(a,'72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20'),
            b.csv(s,'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab'),calendar)
        if not disjoint['path_equivalent']or disjoint['intersection_count']:raise ValueError('actual_new_keys_intersect_A0_reads')
    else:disjoint=dict(fixture_only=True,market_disjointness_not_claimed=True)
    folder=request_directory(owner,current)/'review';folder.mkdir(parents=True,exist_ok=False)
    path=folder/'delivery_minutes.csv';data.to_csv(path,index=False);b.bind(path)
    proof_path=folder/'completion_evidence.json';atomic(proof_path,d.runtime.json_safe(proofs));b.bind(proof_path)
    checks_path=folder/'checks.json';atomic(checks_path,d.runtime.json_safe(dict(targets=checks,existing_keys=len(existing),new_keys=len(new),
        A0_disjointness=disjoint,old_value_comparison_delegated_to_actual021=True,commit_inheritance=False)));b.bind(checks_path)
    b.unchanged();receipt=folder/'delivery_receipt.json'
    value=dict(schema=d.gate.RECEIPT_SCHEMA,independent_review=True,reviewer='stage087_independent_exact_scope_reader',
        qualified_research_data=True,p0_findings=0,p1_findings=0,p2_findings=0,request_sha256=current['digest'],accepted_requirements=accepted,
        data_path=str(path),data_sha256=b.inputs[str(path)],source_fingerprints=b.inputs,owner_arm=owner.document['arm'],
        owner_run_id=owner.document['run_id'],owner_sha256=owner.sha256,fixture_only=owner.fixture_allowed,
        financial_replays=0,model_fits=0,orders=0,response_written=False,production_qualified=False)
    atomic(receipt,value);digest=sha(receipt);gate_parser(current,receipt,digest)
    result=dict(status='accepted',request_sha256=current['digest'],receipt_path=str(receipt),receipt_sha256=digest,
        actual_stage021_parser_passed=True,fixture_only=owner.fixture_allowed,response_written=False)
    atomic(folder/'parse_result.json',result);return result


def publish_reviewed(owner,current,receipt_path,receipt_sha256):
    fresh=read_actual_request(owner,current['path'],current['file_sha'])
    if fresh['digest']!=current['digest']:raise ValueError('current_wait_changed_before_publish')
    path=Path(receipt_path).absolute();expected=request_directory(owner,current)/'review/delivery_receipt.json'
    if path!=expected:raise ValueError('receipt_not_owned_independent_review')
    b=Bindings();receipt=b.json(path,receipt_sha256)
    if receipt.get('owner_sha256')!=owner.sha256 or receipt.get('owner_run_id')!=owner.document['run_id']or receipt.get('owner_arm')!=owner.document['arm']:
        raise ValueError('receipt_owner_mismatch')
    if receipt.get('fixture_only')and not owner.fixture_allowed:raise ValueError('fixture_receipt_not_actual_delivery')
    for source,digest in receipt['source_fingerprints'].items():b.bind(source,digest)
    gate_parser(current,path,receipt_sha256);read_actual_request(owner,current['path'],current['file_sha'])
    pointer=dict(schema='stage022_delivery_pointer_v1',request_sha256=current['digest'],receipt_path=str(path),receipt_sha256=receipt_sha256)
    target=current['path'].with_name('response.json')
    if target.exists():
        if json.loads(regular_bytes(target))!=pointer:raise ValueError('existing_response_conflict')
    else:atomic(target,pointer)
    return dict(response_path=str(target),response_sha256=sha(target))


def _daily_contexts(owner,current,b):
    d=deps();f=d.frozen
    manifest=b.json(d.old.OLD/'input_manifest.json',f.OLD_MANIFEST_SHA)
    mapping=b.csv(d.old.MAPPING,manifest[str(d.old.MAPPING.relative_to(ROOT))]);calendar=d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
    targets,info=d.minute.packet_targets(current['request'],calendar,0)
    if not info['covers_whole_request']or not 1<=len(targets)<=8:raise ValueError('one_to_eight_actual_requirements_only')
    review=b.json(f.R013,f.R013_SHA)
    approved=d.frozen.daily013.approved_references(b.csv(review['qualified_daily_path'],review['source_fingerprints'][review['qualified_daily_path']]),
        b.csv(review['target_qualification_path'],review['source_fingerprints'][review['target_qualification_path']]),review)
    rejected={(r['vt_symbol'],r['trade_date'])for r in review['rejected_targets']}
    contexts=[];missing=[];new_rows=[]
    for target in targets:
        symbol,day,kind=(target[k]for k in ('vt_symbol','execution_trade_date','requirement_kind'));native,exchange=symbol.split('.')
        path=d.old.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        original=b.csv(path,manifest.get(str(path.relative_to(ROOT))))if path.exists()else None
        try:daily,source=d.minute.choose_daily_reference(symbol,day,kind,original,approved,rejected)
        except ValueError as error:
            if str(error)!='qualified_daily_reference_missing':raise
            try:
                daily,q,a,c=d.generic.recover_daily(b,symbol,day,review,current['request'])
            except f.NeedRaw as error:
                if str(error)not in{'no_bound_daily_raw_for_actual_symbol','bound_daily_raw_has_no_actual_target_day',
                        'no_completed_bound_stage051_snapshot_for_actual_symbol'}:raise
                try:daily,q,a,c=recover_scoped_daily(owner,current,symbol,b)
                except f.NeedRaw:missing.append(symbol);continue
            new_rows.append((q,a,c));source='independently_reviewed_exact_request_daily'
        contexts.append(dict(target=target,daily=daily,daily_reference_source=source,grid=d.old.session_grid(symbol,day,calendar)))
    return contexts,missing,new_rows,info


def resolve_actual(owner,current):
    owner.verify();d=deps();b=Bindings();owner_bindings(owner,current,b)
    existing=request_directory(owner,current)/'review/parse_result.json'
    if existing.exists():
        result=b.json(existing)
        receipt=b.json(result['receipt_path'],result['receipt_sha256'])
        if receipt.get('owner_sha256')!=owner.sha256 or receipt.get('request_sha256')!=current['digest']:
            raise ValueError('existing_review_owner_mismatch')
        for path,digest in receipt['source_fingerprints'].items():b.bind(path,digest)
        gate_parser(current,result['receipt_path'],result['receipt_sha256']);return result
    contexts,missing,new_rows,info=_daily_contexts(owner,current,b)
    if missing:return dict(status='needs_daily',request_sha256=current['digest'],symbols=sorted(missing),family='daily')
    sources={};cache=[]
    for manifest_path,digest in d.frozen.SOURCE_MANIFESTS.items():
        inventory=b.json(manifest_path,digest)
        for row in inventory['sources']:
            for context in contexts:
                symbol=context['target']['vt_symbol'];native,exchange=symbol.split('.')
                path=Path(row['path'])
                if path.name!=native+'_completed_minute_backtest.csv'or path.parent.name!=exchange:continue
                if row.get('status')not in{None,'accepted_source_bytes'}:raise ValueError('local_source_not_accepted')
                frame,check=d.local.read_bound_minute_source(path,row['sha256'],symbol)
                if frame is None:raise ValueError('bound_local_source_unusable:'+str(check))
                b.bind(path,row['sha256']);sources.setdefault(symbol,[]).append(frame)
    for row in owner.document.get('cache_receipts',[]):
        # Inspect only root-whitelisted exact receipt scope before loading its raw closure.
        receipt=json.loads(regular_bytes(row['receipt_path']))
        wanted={(c['target']['vt_symbol'],c['target']['execution_trade_date'])for c in contexts}
        if not any((r['vt_symbol'],r['execution_trade_date'])in wanted for r in receipt.get('accepted_requirements',[])):continue
        cache.append(read_cached_receipt(owner,current,row,b))
    result=qualify_local_sources(owner,current,contexts,sources,b,cached=cache)
    if result['status']=='needs_provider':
        result.update(family='minute',provider_path=str(PROVIDER),provider_sha256=sha(PROVIDER),reviewer_path=str(SOURCE),reviewer_sha256=sha(SOURCE))
        folder=request_directory(owner,current);folder.mkdir(parents=True,exist_ok=True)
        references=folder/'daily_references.json'
        payload=dict(contexts=[dict(target=c['target'],daily=c['daily'],daily_reference_source=c['daily_reference_source'])for c in contexts],
            new_daily_rows=d.runtime.json_safe(new_rows),source_fingerprints=b.inputs,owner_sha256=owner.sha256,request_sha256=current['digest'])
        if references.exists():
            if json.loads(regular_bytes(references))!=payload:raise ValueError('daily_references_changed')
        else:atomic(references,payload)
        result.update(daily_references_path=str(references),daily_references_sha256=sha(references))
    return result


def invoke(argv,timeout):
    process=subprocess.Popen([sys.executable,*map(str,argv)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=process.communicate(timeout=timeout)
    except BaseException:
        if process.poll()is None:os.killpg(process.pid,signal.SIGKILL)
        process.wait();raise
    evidence=dict(subprocess_pid=process.pid,subprocess_returncode=process.returncode,terminal_observed=True)
    if process.returncode!=0:raise ValueError('scope_child_failed:'+str(process.returncode)+':'+stdout[-700:])
    lines=[s for s in stdout.splitlines()if s.strip()]
    return json.loads(lines[-1])if lines else{},evidence


def run_provider_connection(owner,current,packet,journal,*,remaining_seconds,_invoke=None):
    read_actual_request(owner,current['path'],current['file_sha'])
    remaining_seconds=min(remaining_seconds,remaining_engine_seconds(owner,current))
    if remaining_seconds<840:raise ValueError('full_provider_budget_unavailable')
    if not 0<=journal['provider_connections']<journal['max_provider_connections']<=4:raise ValueError('batch_four_connection_limit')
    packet=Path(packet);attempt=packet/'network_attempt1'
    if attempt.exists()or(packet/'terminal_observed.json').exists():raise ValueError('existing_attempt_no_retry')
    b=Bindings();manifest=b.json(packet/'packet_manifest.json');preflight=b.json(packet/'preflight.json')
    if manifest.get('owner_sha256')!=owner.sha256 or manifest.get('request_sha256')!=current['digest']:raise ValueError('packet_owner_or_request_mismatch')
    if owner.fixture_allowed and _invoke is None:raise ValueError('fixture_owner_no_real_provider')
    journal['provider_connections']+=1
    _,tool=(_invoke or invoke)([PROVIDER,'--role','run','--owner',owner.path,'--owner-sha256',owner.sha256,'--packet-dir',packet],min(660,remaining_seconds))
    if tool.get('terminal_observed')is not True or tool.get('subprocess_returncode')!=0:raise ValueError('provider_actual_tool_terminal_not_zero')
    parent_path=attempt/'parent_receipt.json';parent=b.json(parent_path)
    if(parent.get('status')!='worker_terminal'or parent.get('exit_code')!=0 or parent.get('hard_kill')or not parent.get('all_inputs_unchanged')or
        parent.get('request_sha256')!=current['digest']or parent.get('preflight_sha256')!=b.inputs[str(packet/'preflight.json')]):raise ValueError('provider_parent_not_true_zero')
    for name,digest in parent.get('artifact_sha256',{}).items():b.bind(attempt/name,digest)
    if sha(packet/'preflight.json')!=b.inputs[str(packet/'preflight.json')]:raise ValueError('provider_preflight_changed')
    terminal=dict(schema='stage087_provider_actual_tool_terminal_v1',**tool,exit_code=0,all_inputs_unchanged=True,
        owner_sha256=owner.sha256,request_sha256=current['digest'],provider_source_sha256=sha(PROVIDER),
        parent_receipt_sha256=b.inputs[str(parent_path)],preflight_sha256=b.inputs[str(packet/'preflight.json')],
        new_provider_connections=1,new_daily_provider_connections=int(manifest['family']=='daily'),
        new_minute_provider_connections=int(manifest['family']=='minute'),fixture_only=owner.fixture_allowed,
        driver_pid=os.getpid(),driver_source_sha256=sha(SOURCE),financial_replays=0,model_fits=0,orders=0)
    atomic(packet/'terminal_observed.json',terminal);return terminal


def read_provider_evidence(owner,current,packet,b):
    packet=Path(packet);manifest=b.json(packet/'packet_manifest.json');preflight=b.json(packet/'preflight.json')
    terminal=b.json(packet/'terminal_observed.json');parent=b.json(packet/'network_attempt1/parent_receipt.json',terminal['parent_receipt_sha256'])
    if(manifest.get('owner_sha256')!=owner.sha256 or manifest.get('request_sha256')!=current['digest']or
        terminal.get('schema')!='stage087_provider_actual_tool_terminal_v1'or terminal.get('terminal_observed')is not True or
        terminal.get('exit_code')!=0 or terminal.get('subprocess_returncode')!=0 or terminal.get('owner_sha256')!=owner.sha256 or
        terminal.get('request_sha256')!=current['digest']or terminal.get('provider_source_sha256')!=sha(PROVIDER)or
        terminal.get('preflight_sha256')!=b.inputs[str(packet/'preflight.json')]or
        parent.get('status')!='worker_terminal'or parent.get('exit_code')!=0 or parent.get('hard_kill')or not parent.get('all_inputs_unchanged')):
        raise ValueError('provider_origin_or_actual_terminal_not_accepted')
    if(terminal.get('all_inputs_unchanged')is not True or terminal.get('new_provider_connections')!=1 or
        terminal.get('new_daily_provider_connections')!=int(manifest['family']=='daily')or
        terminal.get('new_minute_provider_connections')!=int(manifest['family']=='minute')or
        terminal.get('driver_source_sha256')!=sha(SOURCE)or
        any(terminal.get(k)!=0 for k in ('financial_replays','model_fits','orders'))or
        parent.get('owner_sha256')!=owner.sha256 or parent.get('request_sha256')!=current['digest']or
        parent.get('preflight_sha256')!=b.inputs[str(packet/'preflight.json')]):
        raise ValueError('provider_terminal_parent_metadata_conflict')
    if parent.get('elapsed_seconds',601)>=600 or parent.get('automatic_retry')is not False:
        raise ValueError('provider_budget_or_retry_contract')
    if bool(manifest.get('fixture_only'))!=bool(owner.document.get('fixture_only'))or bool(terminal.get('fixture_only'))!=bool(owner.document.get('fixture_only')):
        raise ValueError('provider_fixture_or_actual_owner_conflict')
    for path,digest in preflight['source_fingerprints'].items():b.bind(path,digest)
    for name,digest in parent['artifact_sha256'].items():b.bind(packet/'network_attempt1'/name,digest)
    worker=b.json(packet/'network_attempt1/worker_receipt.json')
    expected_status='completed_all_targets_qualified'if manifest['family']=='daily'else'all_target_minutes_completed'
    if(worker.get('status')!=expected_status or worker.get('accepted')is not True or worker.get('provider_connections_attempted')!=1 or
        worker.get('TqSim_created')is not True or worker.get('owner_sha256')!=owner.sha256 or worker.get('request_sha256')!=current['digest']or
        worker.get('automatic_retry')is not False or any(worker.get(k)!=0 for k in ('financial_replays','model_fits','orders','cancels','broker_or_ctp_connections'))):
        raise ValueError('provider_worker_not_exact_success')
    return manifest,parent


def read_scoped_daily(owner,current,packet,symbol,b):
    d=deps();manifest,parent=read_provider_evidence(owner,current,packet,b)
    if manifest['family']!='daily':raise ValueError('daily_family_required')
    rows=d.pd.DataFrame(manifest['daily_targets']);hit=rows.loc[rows.vt_symbol.eq(symbol)]
    if len(hit)!=1:raise ValueError('exact_daily_target_missing')
    native,exchange=symbol.split('.');path=Path(packet)/'network_attempt1/raw'/exchange/(native+'.csv')
    frame=b.csv(path);raw=frame.to_dict('records');target=hit.iloc[0]
    six={name:float(target['open_interest'if name=='open_oi'else name])for name in ['open','high','low','close','volume','open_oi']}
    daily,q,a,c=d.generic.ordinary_raw_evidence(raw,symbol,str(target.trade_date),six)
    declared=b.csv(Path(packet)/'network_attempt1/qualified_daily.csv')
    audits=b.csv(Path(packet)/'network_attempt1/target_qualification.csv')
    qhit=declared.loc[declared.vt_symbol.eq(symbol)&declared.trade_date.eq(str(target.trade_date))]
    ahit=audits.loc[audits.vt_symbol.eq(symbol)&audits.trade_date.eq(str(target.trade_date))]
    if len(qhit)!=1 or len(ahit)!=1 or any(float(qhit.iloc[0][k])!=daily[k]for k in d.old.VALUES)or str(ahit.iloc[0].accepted).lower()!='true':
        raise ValueError('scoped_daily_origin_declared_values_or_audit_conflict')
    for key in ('source_bar_id','source_datetime_ns','successor_id','successor_datetime_ns'):
        if d.frozen.integer(qhit.iloc[0][key])!=q[key]or d.frozen.integer(ahit.iloc[0][key])!=q[key]:raise ValueError('scoped_daily_origin_proof_conflict')
    return daily,q,a,c


def query_daily_six(symbol,day):
    import sqlite3
    native,exchange=symbol.split('.')
    with sqlite3.connect((ROOT/'.vntrader/database.db').as_uri()+'?mode=ro',uri=True)as db:
        db.execute('PRAGMA query_only=ON')
        rows=db.execute('SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND substr(datetime,1,10)=?',(native,exchange,'d',day)).fetchall()
    if len(rows)!=1:raise ValueError('scoped_daily_current_DB_six_missing_or_duplicate')
    return dict(zip(('open','high','low','close','volume','open_oi'),rows[0]))


def recover_scoped_daily(owner,current,symbol,b):
    """Same-owner completed snapshots plus an explicit cross-owner root whitelist."""
    d=deps();exact=request_directory(owner,current)/'daily_packet'
    if exact.exists():candidates=[exact]
    else:
        candidates=sorted((OUTPUT_ROOT/owner.document['arm']/owner.document['run_id']).glob('request_*/daily_packet'))
        for row in owner.document.get('cache_daily_packets',[]):
            packet=Path(row['packet_dir']).absolute();b.bind(packet/'terminal_observed.json',row['terminal_sha256']);candidates.append(packet)
    qualified=[]
    for packet in candidates:
        if not(packet/'terminal_observed.json').exists():
            if packet==exact:raise ValueError('current_daily_attempt_without_true_terminal')
            continue
        manifest=b.json(packet/'packet_manifest.json')
        if not any(r['vt_symbol']==symbol for r in manifest.get('daily_targets',[])):
            if packet==exact:raise ValueError('current_daily_packet_missing_actual_symbol')
            continue
        origin_doc=b.json(manifest['owner_path'],manifest['owner_sha256'])
        if origin_doc.get('fixture_only')and not owner.document.get('fixture_only'):raise ValueError('fixture_daily_snapshot_not_actual_source')
        if packet!=OUTPUT_ROOT/origin_doc['arm']/origin_doc['run_id']/('request_'+manifest['request_sha256'])/'daily_packet':
            raise ValueError('cached_scope_daily_origin_path_mismatch')
        for label in ('run_context','preflight','execution_readiness'):b.bind(origin_doc[label+'_path'],origin_doc[label+'_sha256'])
        for path,digest in origin_doc['source_fingerprints'].items():b.bind(path,digest)
        if any(origin_doc['source_fingerprints'].get(str(p))!=sha(p)for p in (SOURCE,PROVIDER)):raise ValueError('unreviewed_scoped_daily_source_family')
        origin_request=b.json(manifest['request_path'],manifest['request_file_sha256'])
        if d.gate.request_sha256(origin_request)!=manifest['request_sha256']:raise ValueError('cached_scope_daily_origin_request_changed')
        from types import SimpleNamespace
        origin=SimpleNamespace(sha256=manifest['owner_sha256'],document=origin_doc)
        origin_current=dict(request=origin_request,digest=manifest['request_sha256'])
        read_scoped_daily(origin,origin_current,packet,symbol,b)
        native,exchange=symbol.split('.');path=packet/'network_attempt1/raw'/exchange/(native+'.csv');frame=b.csv(path)
        day=next(t['execution_trade_date']for t in current['request']['requirements']if t['vt_symbol']==symbol)
        try:result=d.generic.ordinary_raw_evidence(frame.to_dict('records'),symbol,day,query_daily_six(symbol,day))
        except ValueError as error:
            if str(error)=='stage051_unique_legal_actual_daily_target_required'and not any(d.frozen.local_ns(d.frozen.integer(r['datetime'])).date().isoformat()==day for r in frame.to_dict('records')if d.frozen.legal(r)):
                continue
            raise
        result[3].update(source_family='stage087_scoped_ordinary_daily',source_origin_request_sha256=manifest['request_sha256'],
            newly_qualified_request_sha256=current['digest'],raw_non_target_daily_rows_qualified=False,
            actual_DB_query=True,database_closeOI='N/A_not_independently_available')
        qualified.append((b.inputs[str(path)],result))
    if not qualified:raise d.frozen.NeedRaw('no_completed_scoped_daily_snapshot_for_actual_target')
    if len({h for h,r in qualified})!=1:raise ValueError('scoped_daily_snapshot_SHA_conflict')
    return qualified[0][1]


def review_packet(owner,current,packet_dirs,terminal_sha256s):
    if len(packet_dirs)!=1 or len(terminal_sha256s)!=1:raise ValueError('one_actual_packet_required')
    d=deps();packet=Path(packet_dirs[0]);b=Bindings();b.bind(packet/'terminal_observed.json',terminal_sha256s[0])
    manifest,parent=read_provider_evidence(owner,current,packet,b)
    if manifest['family']!='minute':raise ValueError('minute_packet_required_for_021_delivery')
    raw=d.old.normal_times(b.csv(packet/'network_attempt1/raw_completed_minutes.csv'))
    evidence=d.old.normal_times(b.csv(packet/'network_attempt1/completion_evidence.csv'))
    completed=_proofs(raw,evidence,network=True);ready={};checks=[]
    expected={(r['vt_symbol'],d.pd.Timestamp(t))for r in current['request']['requirements']for t in r['required_timestamps']}
    if d.gate._keys(raw)!=expected or d.old.minute_keys(raw).has_duplicates:raise ValueError('provider_raw_not_exact_actual_R')
    references=b.json(manifest['daily_references_path'],manifest['daily_references_sha256'])
    for path,digest in references['source_fingerprints'].items():b.bind(path,digest)
    wanted={(r['vt_symbol'],r['execution_trade_date'],r['requirement_kind']):r for r in current['request']['requirements']}
    if len(wanted)!=len(current['request']['requirements']):raise ValueError('duplicate_actual_requirement')
    for context in references['contexts']:
        target=context['target'];identity=tuple(target[k]for k in ('vt_symbol','execution_trade_date','requirement_kind'))
        if identity not in wanted or target!=wanted[identity]:raise ValueError('provider_reference_scope_conflict')
        check=d.minute.qualify_target(raw,completed,dict(target,daily_reference=context['daily']))
        if not check['accepted']:raise ValueError('provider_target_not_qualified')
        ready[identity]=raw.loc[raw.vt_symbol.eq(identity[0])&raw.bar_datetime.isin(d.pd.to_datetime(target['required_timestamps']))]
        checks.append(check)
    data,accepted=d.generic.assemble_delivery(current['request'],ready)
    return _sign_delivery(owner,current,data,accepted,b,checks,evidence.to_dict('records'))


def remaining_engine_seconds(owner,current):
    now=datetime.now(timezone.utc)
    elapsed=lambda value:(now-datetime.fromisoformat(value).astimezone(timezone.utc)).total_seconds()
    return min(1800-elapsed(current['wait']['started_at']),7200-elapsed(owner.document['run_started_at']))


def drive(owner,batch_id,*,max_connections=4,budget_seconds=3600):
    if not 1<=max_connections<=4 or not 840<=budget_seconds<=3600 or not re.fullmatch(r'[a-z0-9_-]+',batch_id):raise ValueError('bounded_batch_contract')
    owner.verify();folder=OUTPUT_ROOT/owner.document['arm']/owner.document['run_id']/'batches'/batch_id;folder.mkdir(parents=True,exist_ok=False)
    journal=dict(owner_sha256=owner.sha256,provider_connections=0,max_provider_connections=max_connections,status='running',events=[])
    began=time.monotonic()
    def save():atomic(folder/'journal.json',journal,replace=True)
    save()
    try:
        while time.monotonic()-began<budget_seconds:
            current=current_request(owner)
            if current is None:journal['status']='stopped_no_current_wait';break
            if current['path'].with_name('response.json').exists():time.sleep(.5);continue
            args=['--owner',owner.path,'--owner-sha256',owner.sha256,'--request',current['path'],'--request-file-sha256',current['file_sha']]
            result,_=invoke([SOURCE,'--role','resolve',*args],min(120,budget_seconds-(time.monotonic()-began)))
            if result.get('request_sha256')!=current['digest']:raise ValueError('resolver_returned_wrong_request')
            if result['status']=='accepted':publish_reviewed(owner,current,result['receipt_path'],result['receipt_sha256']);continue
            if result['status']not in{'needs_daily','needs_provider'}:raise ValueError('independent_resolver_blocked')
            family='daily'if result['status']=='needs_daily'else'minute';packet=request_directory(owner,current)/(family+'_packet')
            if packet.exists():
                if not(packet/'terminal_observed.json').exists():raise ValueError('existing_packet_without_true_terminal_no_retry')
            else:
                prepare=[PROVIDER,'--role','prepare',*args,'--family',family]
                if family=='daily':prepare+=['--symbols',*result['symbols']]
                else:prepare+=['--daily-references',result['daily_references_path'],'--daily-references-sha256',result['daily_references_sha256']]
                invoke(prepare,min(120,budget_seconds-(time.monotonic()-began)))
            if not(packet/'terminal_observed.json').exists():
                remaining=min(budget_seconds-(time.monotonic()-began),remaining_engine_seconds(owner,current))
                if remaining<840 or journal['provider_connections']>=max_connections:journal['status']='paused_budget_or_four_connections';break
                # Reserve durably before launch; a driver interruption cannot create free retries.
                journal['provider_connections']+=1;save();journal['provider_connections']-=1
                terminal=run_provider_connection(owner,current,packet,journal,remaining_seconds=remaining);save()
            if family=='daily':continue  # independent resolver checks actual raw/DB target next
            result,_=invoke([SOURCE,'--role','review',*args,'--packet-dir',packet,'--terminal-sha256',sha(packet/'terminal_observed.json')],120)
            publish_reviewed(owner,current,result['receipt_path'],result['receipt_sha256'])
            journal['events'].append(dict(request_sha256=current['digest'],published=True));save()
        else:journal['status']='paused_batch_budget'
    except BaseException as error:
        journal.update(status='blocked',error=type(error).__name__+':'+str(error));save();raise
    save();return journal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=['resolve','review','drive'],required=True)
    parser.add_argument('--owner',type=Path,required=True);parser.add_argument('--owner-sha256',required=True)
    parser.add_argument('--request',type=Path);parser.add_argument('--request-file-sha256')
    parser.add_argument('--packet-dir',type=Path,nargs='+');parser.add_argument('--terminal-sha256',nargs='+')
    parser.add_argument('--batch-id');parser.add_argument('--max-connections',type=int,default=4);parser.add_argument('--budget-seconds',type=int,default=3600)
    args=parser.parse_args();owner=load_owner(args.owner,args.owner_sha256)
    if args.role=='drive':result=drive(owner,args.batch_id,max_connections=args.max_connections,budget_seconds=args.budget_seconds)
    else:
        current=read_actual_request(owner,args.request,args.request_file_sha256)
        result=resolve_actual(owner,current)if args.role=='resolve'else review_packet(owner,current,args.packet_dir,args.terminal_sha256)
    print(json.dumps(deps().runtime.json_safe(result),ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='blocked',error_type=type(error).__name__,error=str(error),response_written=False),ensure_ascii=False));raise SystemExit(1)
