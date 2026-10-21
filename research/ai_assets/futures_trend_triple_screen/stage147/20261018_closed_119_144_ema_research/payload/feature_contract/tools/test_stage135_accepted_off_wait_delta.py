"""Two tiny provenance/data compositions; all owners and reviews are fixtures."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import stage022_run_c0_qualified_wait as runtime

_runtime_tmp = tempfile.TemporaryDirectory(prefix='stage135-test-runtime-')
_runtime_output = runtime.OUTPUT
try:
    runtime.OUTPUT = Path(_runtime_tmp.name) / 'runtime'
    runtime.configure_runtime(Path(_runtime_tmp.name) / 'shared')
finally:
    runtime.OUTPUT = _runtime_output
import pandas as pd
import stage021_blocking_data_gate as gate
import stage061_accepted_wait_delta as container

SOURCE = TOOLS / 'stage135_accepted_off_wait_delta.py'
STAMPS = ['2020-01-02T09:00:00', '2020-01-02T09:01:00', '2020-01-02T09:02:00']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return digest(path)


class Fixture:
    """Independent synthetic schemas, never a forged actual134/087 signature."""
    def __init__(self, root):
        self.root = root
        self.owner = dict(arm='B_OFF', run_id='fixture-off-only', attempt=1,
            output_directory=str(root / 'B_OFF'))
        self.directory = Path(self.owner['output_directory']); self.directory.mkdir()
        self.inputs = {}
        self.gates, self.resolvers = [], []
        self.stack = root / 'data_stack_manifest.json'
        write(self.stack, dict(schema='stage022_qualified_data_stack_v1', append_order=['002', '011', '015', '020']))
        self.bind(self.stack)
        self.writer = root / 'stage065_account_checkpoint.py'; self.writer.write_bytes(b'# fixture writer\n')
        self.runner = root / 'stage065_run_pairwise_off.py'; self.runner.write_bytes(b'# fixture runner\n')
        self.anchors = []
        for number in range(2):
            paths = {}
            for kind in ('request', 'receipt', 'data'):
                p = root / f'inherited_{number}_{kind}.json'; p.write_bytes(b'{}\n'); self.bind(p)
                paths[kind + '_path'] = str(p)
                paths[kind + '_sha256'] = digest(p)
            self.anchors.append(paths)
        self.old_delta = root / 'old190_manifest.json'; self.old_delta.write_bytes(b'{"inherited_only":true}\n'); self.bind(self.old_delta)
        self.old_review = root / 'old190_review.json'; self.old_review.write_bytes(b'{"inherited_only":true}\n'); self.bind(self.old_review)
        self.context = dict(schema='stage065_run_context_v1', **self.owner,
            fixture_only=True, started_at='2026-01-01T00:00:00+08:00',
            writer=self.writer.name, writer_source_sha256=digest(self.writer),
            source_bindings={str(self.writer):dict(sha256=digest(self.writer))})
        self.preflight = dict(arm='B_OFF', attempt=1, fixture_only=True,
            data_stack_sha256=digest(self.stack), accepted_wait_delta_manifest=str(self.old_delta),
            accepted_wait_delta_sha256=digest(self.old_delta), accepted_wait_delta_review=str(self.old_review),
            accepted_wait_delta_review_sha256=digest(self.old_review),
            reused_anchor=dict(deliveries=self.anchors, exact_anchor_keys=2, full_session_keys=0))
        self.capture = self.directory / 'failure_capture.pkl.gz'; self.capture.write_bytes(b'opaque fixture capture; do not unpickle')
        self.failure = dict(arm='B_OFF', run_id=self.owner['run_id'], partial=True,
            status='failed_partial_no_engine_seal', production_qualified=False,
            failure_capture_sha256=digest(self.capture))
        self.add(STAMPS[:2], 'anchor')
        self.add(STAMPS[1:], 'full_session')
        failed = 'f' * 64
        self.gates.extend([dict(event='data_requested', request_sha256=failed, request_sequence=3),
            dict(event='data_gate_failed', request_sha256=failed)])
        self.resolvers.append(dict(status='failed', request_sha256=failed,
            data_path=str(root / 'NEVER_READ_FAILED_RAW.csv')))
        self.failed = failed

    def bind(self, path):
        self.inputs[str(path)] = dict(sha256=digest(path))

    def add(self, stamps, kind):
        sequence = len(self.resolvers) + 1
        request = dict(schema=gate.REQUEST_SCHEMA, request_sequence=sequence, requirements=[dict(
            vt_symbol='x2001.TEST', execution_trade_date='2020-01-02', requirement_kind=kind,
            required_timestamps=stamps, existing_source_timestamps=[], missing_or_unqualified_timestamps=stamps)])
        request['request_sha256'] = gate.request_sha256(request); identity=request['request_sha256']
        folder = self.directory / 'data_wait' / ('request_' + identity); folder.mkdir(parents=True)
        request_path=folder/'request.json'; write(request_path,request)
        fingerprint=folder/'request_fingerprint.json'; write(fingerprint,dict(request_sha256=identity,
            request_file_sha256=digest(request_path),request_path=str(request_path)))
        data=folder/'minutes.csv'
        pd.DataFrame([dict(vt_symbol='x2001.TEST',bar_datetime=stamp,open=10.,high=12.,low=9.,
            close=11.,volume=5.,open_oi=8.,close_oi=9.)for stamp in stamps]).to_csv(data,index=False)
        proof=folder/'proof.json'; write(proof,dict(fixture_only=True))
        closure={str(data):digest(data),str(proof):digest(proof)}
        receipt=folder/'receipt.json'; write(receipt,dict(schema=gate.RECEIPT_SCHEMA,independent_review=True,
            reviewer='fixture_only_data_reader',qualified_research_data=True,fixture_only=True,p0_findings=0,p1_findings=0,
            owner_run_id=self.owner['run_id'],owner_arm='B_OFF',
            request_sha256=identity,data_path=str(data),data_sha256=digest(data),source_fingerprints=closure,
            accepted_requirements=[dict(vt_symbol='x2001.TEST',execution_trade_date='2020-01-02',requirement_kind=kind,
                accepted=True,completed_bars_and_daily_qualified=True,accepted_timestamps=stamps)]))
        response=folder/'response.json'; write(response,dict(schema='stage022_delivery_pointer_v1',
            request_sha256=identity,receipt_path=str(receipt),receipt_sha256=digest(receipt)))
        for p in (request_path,fingerprint,data,proof,receipt,response):self.bind(p)
        pointer=dict(status='qualified_delivery_pointer_accepted',request_sha256=identity,
            request_path=str(request_path),request_file_sha256=digest(request_path),response_path=str(response),
            response_sha256=digest(response),receipt_path=str(receipt),receipt_sha256=digest(receipt),
            data_path=str(data),data_sha256=digest(data),source_fingerprints=closure)
        self.resolvers.append(pointer)
        self.gates.extend([dict(event='data_requested',request_sha256=identity,request_sequence=sequence),
            dict(event='data_qualified_appended',request_sha256=identity,accepted_keys=len(stamps),appended_keys=len(stamps),
                old_keys_changed=0,**{k:pointer[k]for k in ('receipt_path','receipt_sha256','data_path','data_sha256')})])

    def save(self):
        preflight=self.directory/'preflight_used.json'; write(preflight,self.preflight)
        self.context['preflight_sha256']=digest(preflight)
        context=self.directory/'run_context.json';write(context,self.context)
        failure=self.directory/'run_failure.json';write(failure,self.failure)
        owner=self.root/'owner.json';write(owner,dict(schema='stage135_fixture_owner_v1',fixture_only=True,
            arm='B_OFF',attempt=1,run_id=self.owner['run_id'],account_output=str(self.directory),
            wait_root=str(self.directory/'data_wait'),run_context_path=str(context),run_context_sha256=digest(context),
            preflight_path=str(preflight),preflight_sha256=digest(preflight),
            runner_path=str(self.runner),runner_sha256=digest(self.runner)))
        objects={name:dict(path=str(p),sha256=digest(p))for name,p in (
            ('run_context.json',context),('preflight_used.json',preflight),('run_failure.json',failure),('failure_capture.pkl.gz',self.capture))}
        terminal=self.root/'terminal.json';write(terminal,dict(schema='stage135_fixture_terminal_v1',actual_terminal_observed=True,
            tool_session_id=123,tool_terminal_chunk_id='fixture-terminal',engine_pid_at_start=123,exit_code=1,
            **{k:self.owner[k]for k in ('arm','run_id','attempt')},owner_root=str(self.directory),
            failure=self.failure,objects=objects))
        self.snapshot=self.root/'snapshot.json'
        self.projection=dict(schema='stage135_fixture_projection_v1',audit_only=True,new_data_qualification=False,
            financial_qualified=False,owner=self.owner,input_fingerprints=self.inputs,wait_audit=self.gates,
            resolver_audit=self.resolvers,upstream_bindings=dict(objects,actual_terminal=dict(path=str(terminal),sha256=digest(terminal)),
                owner=dict(path=str(owner),sha256=digest(owner)),original_065_schema='stage065_partial_failure_capture_v1'))
        write(self.snapshot,self.projection)
        self.review=self.root/'review.json'
        self.review_value=dict(schema='stage135_fixture_origin_review_v1',independent_review=True,reviewer='fixture_origin_reviewer',
            p0_findings=0,p1_findings=0,owner=self.owner,financial_accepted=False,production_qualified=False,
            new_frozen_dataset=False,new_data_qualification_receipt=False,
            audit_only_snapshot=dict(path=str(self.snapshot),sha256=digest(self.snapshot)),
            actual_terminal=dict(path=str(terminal),sha256=digest(terminal)),run_context=objects['run_context.json'],
            preflight=objects['preflight_used.json'],run_failure=objects['run_failure.json'],failure_capture=objects['failure_capture.pkl.gz'],
            actual_capture_scope=dict(actual_gate_committed=2,unique_exact_keys=3,qualified_full_keys=2,
                explicit_anchor_only_keys=1,qualified_anchor_keys=3))
        write(self.review,self.review_value)

    def freeze(self,builder,name='delta',snapshot_sha256=None):
        return builder._freeze_off_delta(snapshot_path=self.snapshot,snapshot_sha256=snapshot_sha256 or digest(self.snapshot),
            review_path=self.review,review_sha256=digest(self.review),output=self.root/name,
            contract=builder.OriginContract('stage135_fixture_projection_v1','stage135_fixture_origin_review_v1',
                'stage135_fixture_terminal_v1','stage135_fixture_owner_v1',True))


@contextmanager
def poison_after_hash_read(path):
    """A path re-open would parse poison; pinned-byte parsing must reach drift guard."""
    path=Path(path);original=path.read_bytes();original_open=Path.open;reads=[]
    @contextmanager
    def opened(current,*args,**kwargs):
        with original_open(current,*args,**kwargs) as handle:yield handle
        if Path(current)==path and 'r' in (args[0] if args else kwargs.get('mode','r')):
            reads.append(1)
            with original_open(path,'wb')as handle:handle.write(b'{poison' if len(reads)==1 else original)
    try:
        with patch.object(Path,'open',opened):yield reads
    finally:
        with original_open(path,'wb')as handle:handle.write(original)


class OffDeltaTest(unittest.TestCase):
    def builder(self):
        self.assertTrue(SOURCE.exists(),'Stage135 neutral builder is not implemented')
        spec=importlib.util.spec_from_file_location('stage135_under_test',SOURCE)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        return module

    def test_origin_provenance_and_same_bytes_cannot_be_upgraded_or_reopened(self):
        builder=self.builder()
        for mutation in ('schema','terminal','pointer','old_keys','sequence','closure'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory()as tmp:
                f=Fixture(Path(tmp));f.save()
                if mutation=='schema':f.projection['schema']='stage134_audit_only_projection_of_stage065_failed_capture_v1'
                if mutation=='terminal':
                    p=Path(f.projection['upstream_bindings']['actual_terminal']['path']);v=json.loads(p.read_bytes());v['exit_code']=0
                    write(p,v);f.projection['upstream_bindings']['actual_terminal']['sha256']=digest(p)
                    f.review_value['actual_terminal']['sha256']=digest(p)
                if mutation=='pointer':f.projection['resolver_audit'][0]['data_sha256']='0'*64
                if mutation=='old_keys':f.projection['wait_audit'][1]['old_keys_changed']=1
                if mutation=='sequence':f.projection['wait_audit'][0]['request_sequence']=99
                if mutation=='closure':f.projection['resolver_audit'][0]['source_fingerprints']={}
                write(f.snapshot,f.projection);f.review_value['audit_only_snapshot']['sha256']=digest(f.snapshot);write(f.review,f.review_value)
                with self.assertRaises(ValueError):f.freeze(builder)
                self.assertFalse((f.root/'delta').exists())
        with tempfile.TemporaryDirectory()as tmp:
            f=Fixture(Path(tmp));f.save()
            with self.assertRaisesRegex(ValueError,'actual134_identity'):
                builder.freeze_off_delta(snapshot_path=f.snapshot,snapshot_sha256=digest(f.snapshot),
                    review_path=f.review,review_sha256=digest(f.review),output=f.root/'not_actual')
            snapshot_pin=digest(f.snapshot)
            with poison_after_hash_read(f.snapshot):
                with self.assertRaisesRegex(ValueError,'source_hash_changed_during_freeze'):
                    f.freeze(builder,snapshot_sha256=snapshot_pin)
            data=Path(f.resolvers[0]['data_path'])
            with poison_after_hash_read(data):
                with self.assertRaisesRegex(ValueError,'source_hash_changed_during_freeze'):f.freeze(builder)

    def test_overlapping_rights_conflicts_and_readonly_original_container_compose(self):
        builder=self.builder()
        with tempfile.TemporaryDirectory()as tmp:
            f=Fixture(Path(tmp));f.save();manifest=f.freeze(builder)
            m=json.loads(manifest.read_bytes())
            self.assertEqual((m['accepted_deliveries'],m['accepted_keys'],m['qualified_full_keys'],m['qualified_anchor_keys']),(2,3,2,3))
            self.assertEqual(m['builder'],'stage135_accepted_off_wait_delta.py')
            self.assertTrue(m['compatible_data_schema_only']);self.assertTrue(m['fixture_only'])
            self.assertEqual(m['status'],'frozen_pending_independent_review')
            accepted=json.loads((manifest.parent/'accepted_deliveries.json').read_bytes())
            self.assertEqual(accepted['excluded'],[dict(request_sha256=f.failed,reason='data_gate_failed')])
            self.assertNotIn(str(f.root/'NEVER_READ_FAILED_RAW.csv'),m['source_fingerprints'])
            with self.assertRaises(FileExistsError):f.freeze(builder)
            review=f.root/'fixture_dataset_review.json'
            write(review,dict(schema=container.REVIEW_SCHEMA,independent_review=True,reviewer='fixture_independent_dataset_reader',
                fixture_only=True,manifest_path=str(manifest),manifest_sha256=digest(manifest),p0_findings=0,p1_findings=0,
                qualified_research_data=True,exact_rights_confirmed=True,old_key_values_unchanged=True))
            delta=container.load_accepted_delta(manifest,digest(manifest),review,digest(review),
                base_stack=f.stack,base_stack_sha256=digest(f.stack),inherited_anchor_inputs=f.anchors)
            base=delta.overlay.iloc[[2]].copy();before=base.copy(deep=True)
            result,added=container.append_equal_only(base,delta);pd.testing.assert_frame_equal(base,before)
            self.assertEqual(len(result),3);self.assertEqual(len(added),2)
            full,anchor=container.compose_qualification(lambda *_:True,set(),added,delta)
            self.assertFalse(full('x2001.TEST',STAMPS[0]));self.assertTrue(anchor('x2001.TEST',STAMPS[0]))
            self.assertTrue(full('x2001.TEST',STAMPS[1]));self.assertTrue(full('x2001.TEST',STAMPS[2]))
            caches=[object(),set(['original']),object()]
            original=lambda _:base
            engine=SimpleNamespace(_load_stage861_full_minute_bars=original,
                **dict(zip(container.CACHE_NAMES,caches)))
            with container.temporary_accepted_wait_delta(engine,delta):
                self.assertEqual(len(engine._load_stage861_full_minute_bars(['x2001.TEST'])),3)
            self.assertIs(engine._load_stage861_full_minute_bars,original)
            for name,value in zip(container.CACHE_NAMES,caches):self.assertIs(getattr(engine,name),value)
            for name in container.VALUES:
                changed=delta.overlay.copy();changed.loc[2,name]+=1
                bad=container.FrozenDelta(changed,delta.full_keys,delta.anchor_keys,delta.source_fingerprints,delta.manifest)
                with self.subTest(value=name),self.assertRaisesRegex(ValueError,'old_value_conflict'):
                    container.append_equal_only(base,bad)
            # A second accepted receipt disagreeing on even one overlapping value is rejected before publication.
            data=Path(f.resolvers[1]['data_path']);frame=pd.read_csv(data);frame.loc[0,'volume']+=1;frame.to_csv(data,index=False)
            pointer=f.resolvers[1];pointer['data_sha256']=digest(data);pointer['source_fingerprints'][str(data)]=digest(data)
            receipt=Path(pointer['receipt_path']);rv=json.loads(receipt.read_bytes());rv['data_sha256']=digest(data);rv['source_fingerprints']=pointer['source_fingerprints'];write(receipt,rv)
            pointer['receipt_sha256']=digest(receipt);response=Path(pointer['response_path']);rr=json.loads(response.read_bytes());rr['receipt_sha256']=digest(receipt);write(response,rr);pointer['response_sha256']=digest(response)
            f.gates[3].update({k:pointer[k]for k in ('data_sha256','receipt_sha256')})
            for p in (data,receipt,response):f.bind(p)
            f.save()
            with self.assertRaisesRegex(ValueError,'cross_receipt_old_value_conflict'):f.freeze(builder,'conflicting')
            self.assertFalse((f.root/'conflicting').exists())


if __name__=='__main__':unittest.main()
