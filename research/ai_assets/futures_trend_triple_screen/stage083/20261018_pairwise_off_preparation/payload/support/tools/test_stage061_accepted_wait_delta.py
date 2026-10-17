"""Three bounded contracts; no financial replay, provider, or model invocation."""
from __future__ import annotations
from contextlib import contextmanager
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

# Configure the accepted numerical stack before importing pandas/numpy/021.
_runtime_tmp = tempfile.TemporaryDirectory(prefix='stage061-runtime-')
runtime.configure_runtime(Path(_runtime_tmp.name) / 'shared')
import pandas as pd
import stage021_blocking_data_gate as gate

SOURCE = TOOLS / 'stage061_accepted_wait_delta.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return digest(path)


def bars(symbol, stamps, source='stage061_non859'):
    return pd.DataFrame([dict(vt_symbol=symbol, bar_datetime=pd.Timestamp(stamp),
        open=10., high=12., low=9., close=11., volume=5., open_oi=8., close_oi=9.,
        minute_source=source) for stamp in stamps])


@contextmanager
def replace_after_first_read(path, replacement, *, symlink=False):
    """Switch after the hash read and restore after the next read, including final hashes."""
    path=Path(path);original=path.read_bytes();original_open=Path.open;events=[]
    good=path.with_name(path.name+'.good');evil=path.with_name(path.name+'.evil')
    if symlink:
        path.rename(good);evil.write_bytes(replacement);path.symlink_to(good)
    def put(payload):
        with original_open(path,'wb') as handle:handle.write(payload)
    @contextmanager
    def raced_open(current,*args,**kwargs):
        mode=args[0] if args else kwargs.get('mode','r')
        with original_open(current,*args,**kwargs) as handle:
            yield handle
        if Path(current)==path and not any(flag in mode for flag in 'wa+'):
            events.append('read')
            if len(events)<=2:
                if symlink:
                    path.unlink();path.symlink_to(evil if len(events)==1 else good)
                else:put(replacement if len(events)==1 else original)
    try:
        with patch.object(Path,'open',raced_open):yield events
    finally:
        if symlink:
            path.unlink();good.rename(path);evil.unlink()
        else:put(original)


class Fixture:
    """Hand-sized mirror of actual Stage036 failure + Stage063 tool evidence."""
    def __init__(self, root):
        self.root = root
        self.owner = root / 'B_TS'; self.owner.mkdir()
        self.facts = self.owner / 'run_failure.json'
        self.terminal = root / 'actual_tool_terminal.json'
        self.stack = root / 'data_stack_manifest.json'
        self.runner = root / 'stage036_run_b_ts_checkpoint.py'
        self.runner.write_text('# fixture runner identity\n')
        (self.owner / 'runner_used.py').write_bytes(self.runner.read_bytes())
        write(self.stack, dict(schema='stage022_qualified_data_stack_v1',
            append_order=['002', '011', '015', '020'], source_fingerprints={}))
        self.context = dict(schema='stage036_run_context_v1', run_id='fixture-run',
            arm='B_TS', attempt=1, output_directory=str(self.owner), started_at='start',
            writer=self.runner.name, writer_source_sha256=digest(self.runner),
            production_qualified=False)
        write(self.owner / 'run_context.json', self.context)
        self.inputs = {str(self.stack): dict(sha256=digest(self.stack))}
        inherited = []
        for number in range(2):
            paths = [root / f'old_anchor_{number}_{kind}.json' for kind in ('request', 'receipt', 'data')]
            for path in paths:
                path.write_text('{}\n'); self.inputs[str(path)] = dict(sha256=digest(path))
            inherited.append(dict(request_path=str(paths[0]), request_sha256=str(number)*64,
                receipt_path=str(paths[1]), receipt_sha256=digest(paths[1]),
                data_path=str(paths[2]), data_sha256=digest(paths[2])))
        self.payload = dict(status='failed_closed_no_accepted_performance', arm='B_TS',
            attempt=1, run_id='fixture-run', started_at='start', failed_at='end',
            raw_checkpoint=None, validation_seal_exists=False, production_qualified=False,
            data_stack_sha256=digest(self.stack), input_fingerprints=self.inputs,
            qualified_wait_gate_audit=[], resolver_audit=[],
            reused_anchor=dict(deliveries=inherited, exact_anchor_keys=2, full_session_keys=0))

    def add(self, symbol, stamps, kind='anchor', commit=True, status='qualified_delivery_pointer_accepted', failed=False):
        sequence=len(self.payload['resolver_audit'])+1
        request=dict(schema=gate.REQUEST_SCHEMA, request_sequence=sequence,
            execution_trade_date='2020-01-02', active_orders=[], requirements=[dict(
            vt_symbol=symbol, execution_trade_date='2020-01-02', requirement_kind=kind,
            required_timestamps=stamps, missing_or_unqualified_timestamps=stamps,
            existing_source_timestamps=[])])
        request['request_sha256']=gate.request_sha256(request)
        folder=self.owner/'data_wait'/('request_'+request['request_sha256']); folder.mkdir(parents=True)
        request_path=folder/'request.json'; write(request_path,request)
        fingerprint=folder/'request_fingerprint.json'
        write(fingerprint,dict(request_sha256=request['request_sha256'],
            request_file_sha256=digest(request_path),request_path=str(request_path)))
        data=folder/'data.csv'; bars(symbol,stamps).drop(columns='minute_source').to_csv(data,index=False)
        sources={str(path):digest(path) for path in (request_path,fingerprint,data)}
        receipt=folder/'receipt.json'
        accepted=dict(request['requirements'][0],accepted=True,completed_bars_and_daily_qualified=True,
            accepted_timestamps=stamps)
        write(receipt,dict(schema=gate.RECEIPT_SCHEMA, independent_review=True, reviewer='fixture-independent',
            qualified_research_data=True,p0_findings=0,p1_findings=0,
            request_sha256=request['request_sha256'],accepted_requirements=[accepted],
            data_path=str(data),data_sha256=digest(data),source_fingerprints=sources))
        response=folder/'response.json'
        write(response,dict(schema='stage022_delivery_pointer_v1',request_sha256=request['request_sha256'],
            receipt_path=str(receipt),receipt_sha256=digest(receipt)))
        row=dict(status=status,request_sha256=request['request_sha256'],request_path=str(request_path),
            request_file_sha256=digest(request_path),response_path=str(response),response_sha256=digest(response),
            receipt_path=str(receipt),receipt_sha256=digest(receipt),data_path=str(data),data_sha256=digest(data),
            source_fingerprints=sources)
        self.payload['resolver_audit'].append(row)
        self.payload['qualified_wait_gate_audit'].append(dict(event='data_requested',
            request_sha256=request['request_sha256'],request_sequence=sequence))
        if commit:
            self.payload['qualified_wait_gate_audit'].append(dict(event='data_qualified_appended',
                request_sha256=request['request_sha256'],appended_keys=len(stamps),old_keys_changed=0,
                accepted_keys=len(stamps),reviewer='fixture-independent',
                **{k:row[k] for k in ('receipt_path','receipt_sha256','data_path','data_sha256')}))
        if failed:self.payload['qualified_wait_gate_audit'].append(dict(event='data_gate_failed',
            request_sha256=request['request_sha256'],error_type='ValueError'))
        for path in (*sources, str(receipt),str(response)):
            self.inputs[path]=dict(sha256=digest(path))
        return row

    def seal(self, active=False):
        write(self.facts,self.payload)
        write(self.terminal,dict(schema='stage063_B_TS_actual_tool_failure_terminal_v1',
            financial_tool_session_id=70433,financial_tool_terminal_chunk_id='fixture-terminal',
            financial_terminal_observed=not active,financial_exit_code=1,engine_pid_at_start=21822,
            runner_source_path=str(self.runner),runner_source_sha256=digest(self.runner),
            used_runner_sha256=digest(self.runner),run_failure_path=str(self.facts),
            run_failure_sha256=digest(self.facts),started_at='start',failed_at='end'))

    def freeze(self, module, output=None):
        return module.freeze_accepted_delta(run_facts=self.facts,run_facts_sha256=digest(self.facts),
            terminal_evidence=self.terminal,terminal_sha256=digest(self.terminal),
            base_stack=self.stack,base_stack_sha256=digest(self.stack),output=output or self.root/'frozen')

    def reviewed(self, module, manifest):
        review=self.root/'review.json'
        write(review,dict(schema='stage061_independent_wait_delta_review_v1',independent_review=True,
            reviewer='other-agent',manifest_path=str(manifest),manifest_sha256=digest(manifest),
            p0_findings=0,p1_findings=0,qualified_research_data=True,
            exact_rights_confirmed=True,old_key_values_unchanged=True))
        return module.load_accepted_delta(manifest,digest(manifest),review,digest(review),
            base_stack=self.stack,base_stack_sha256=digest(self.stack),
            inherited_anchor_inputs=self.payload['reused_anchor']['deliveries'])


class AcceptedDeltaTests(unittest.TestCase):
    def api(self):
        self.assertTrue(SOURCE.is_file(), 'Stage061 freeze/loader API is not implemented')
        spec=importlib.util.spec_from_file_location('stage061_accepted_wait_delta',SOURCE)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        return module

    def test_anchor_receipt_never_becomes_full_from_physical_coverage_or_source_label(self):
        # Mutation caught: inferring full from the enriched non859 physical cache.
        module=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Fixture(Path(tmp)); fixture.add('AA.CZCE',['2020-01-01T21:00:00'])
            fixture.add('BB.SHFE',['2020-01-01T21:00:00','2020-01-01T21:01:00'],'full_session')
            fixture.seal(); delta=fixture.reviewed(module,fixture.freeze(module))
            old=bars('AA.CZCE',['2020-01-01T21:01:00'])
            merged,added=module.append_equal_only(old,delta)
            self.assertEqual(len(merged),4)
            old_full=lambda symbol,stamp: (symbol,stamp) in gate._keys(merged)
            full,anchor=module.compose_qualification(old_full,lambda *_:False,added,delta)
            self.assertFalse(full('AA.CZCE',pd.Timestamp('2020-01-01T21:00:00')))
            self.assertTrue(anchor('AA.CZCE',pd.Timestamp('2020-01-01T21:00:00')))
            self.assertTrue(full('AA.CZCE',pd.Timestamp('2020-01-01T21:01:00')))
            self.assertTrue(full('BB.SHFE',pd.Timestamp('2020-01-01T21:01:00')))
            self.assertFalse(full('BB.SHFE',pd.Timestamp('2020-01-02T21:01:00')))
            self.assertFalse(anchor('CC.SHFE',pd.Timestamp('2020-01-01T21:00:00')))

    def test_any_old_seven_value_conflict_is_atomic_and_same_value_keeps_old_source(self):
        # Mutation caught: replacing old correction/source, or publishing symbol 1 before symbol 2 fails.
        module=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Fixture(Path(tmp));fixture.add('AA.CZCE',['2020-01-01T21:00:00'])
            fixture.add('BB.SHFE',['2020-01-01T21:00:00']);fixture.seal()
            delta=fixture.reviewed(module,fixture.freeze(module))
            base=bars('BB.SHFE',['2020-01-01T21:00:00'],'stage016_corrected_source')
            merged,added=module.append_equal_only(base,delta)
            self.assertEqual(merged.loc[merged.vt_symbol.eq('BB.SHFE'),'minute_source'].item(),'stage016_corrected_source')
            self.assertEqual(added,{('AA.CZCE',pd.Timestamp('2020-01-01T21:00:00'))})
            cache_object=object(); cache_symbols={'sentinel'};audit_object={'sentinel':1}
            engine=SimpleNamespace(_FULL_MINUTE_BY_SYMBOL_CACHE=cache_object,
                _FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS=cache_symbols,_LAST_MINUTE_AUDIT=audit_object)
            for field in ['open','high','low','close','volume','open_oi','close_oi']:
                conflict=base.copy();conflict.loc[0,field]+=1
                def load(_):
                    engine._FULL_MINUTE_BY_SYMBOL_CACHE={'partial':'must rollback'}
                    return conflict
                engine._load_stage861_full_minute_bars=load
                with self.subTest(field=field):
                    with module.temporary_accepted_wait_delta(engine,delta) as appended:
                        before=engine._FULL_MINUTE_BY_SYMBOL_CACHE
                        with self.assertRaisesRegex(ValueError,'old_value_conflict'):
                            engine._load_stage861_full_minute_bars(['AA.CZCE','BB.SHFE'])
                        self.assertIs(engine._FULL_MINUTE_BY_SYMBOL_CACHE,before)
                        self.assertEqual(appended,set())
                    self.assertIs(engine._FULL_MINUTE_BY_SYMBOL_CACHE,cache_object)
                    self.assertIs(engine._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS,cache_symbols)
                    self.assertIs(engine._LAST_MINUTE_AUDIT,audit_object)
                pd.testing.assert_frame_equal(base,bars('BB.SHFE',['2020-01-01T21:00:00'],'stage016_corrected_source'))

    def test_only_terminal_double_commit_and_unchanged_signed_source_can_freeze(self):
        # Mutation caught: inheriting pointers/provider success/failed last package or accepting SHA drift.
        module=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Fixture(Path(tmp));good=fixture.add('AA.CZCE',['2020-01-01T21:00:00'])
            pointer=fixture.add('BB.SHFE',['2020-01-01T21:00:00'],commit=False)
            provider=fixture.add('CC.SHFE',['2020-01-01T21:00:00'],commit=False,status='provider_success_unsigned')
            failed=fixture.add('DD.SHFE',['2020-01-01T21:00:00'],commit=False,failed=True)
            unaccepted=fixture.add('EE.SHFE',['2020-01-01T21:00:00'],commit=False,status='pending')
            fixture.seal(active=True)
            with self.assertRaisesRegex(ValueError,'terminal'):fixture.freeze(module)
            self.assertFalse((fixture.root/'frozen').exists())
            fixture.seal();manifest=fixture.freeze(module)
            accepted=json.loads((manifest.parent/'accepted_deliveries.json').read_text())
            self.assertEqual([x['request_sha256'] for x in accepted['deliveries']],[good['request_sha256']])
            self.assertEqual({x['request_sha256'] for x in accepted['excluded']},
                {pointer['request_sha256'],provider['request_sha256'],failed['request_sha256'],unaccepted['request_sha256']})
            with self.assertRaises(FileExistsError):fixture.freeze(module)
            self.assertEqual(len(fixture.reviewed(module,manifest).overlay),1)
            # P1-001: the checked bytes, rather than a later path read, must be consumed.
            manifest_sha=digest(manifest);review=fixture.root/'review.json';review_sha=digest(review)
            base_sha=digest(fixture.stack)
            def pinned_load(review_digest=review_sha):
                return module.load_accepted_delta(manifest,manifest_sha,review,review_digest,
                    base_stack=fixture.stack,base_stack_sha256=base_sha,
                    inherited_anchor_inputs=fixture.payload['reused_anchor']['deliveries'])
            rights=manifest.parent/'rights.csv';saved=rights.read_bytes()
            rights.write_bytes(saved.replace(b',0,1,',b',1,1,'))
            with self.assertRaises(ValueError):pinned_load()
            rights.write_bytes(saved)
            overlay=manifest.parent/'overlay.csv';altered=pd.read_csv(overlay).astype({'open':float})
            altered.loc[0,'open']=10.25;evil_csv=altered.to_csv(index=False).encode()
            evil_manifest=json.loads(manifest.read_bytes());evil_manifest['builder']='unsigned-swapped-builder'
            for name,target,payload,link in [
                ('ordinary_csv',overlay,evil_csv,False),
                ('symlink_csv',overlay,evil_csv,True),
                ('ordinary_manifest',manifest,json.dumps(evil_manifest).encode(),False)]:
                with self.subTest(byte_binding=name):
                    with replace_after_first_read(target,payload,symlink=link) as events:
                        try:loaded=pinned_load()
                        except ValueError:pass  # A changed or rejected leaf is fail-closed.
                        else:
                            self.assertEqual(float(loaded.overlay.open.iloc[0]),10.)
                            self.assertEqual(loaded.manifest['builder'],'stage061_accepted_wait_delta.py')
                    if not link:self.assertTrue(events)
            good_review=review.read_bytes();bad_review=json.loads(good_review);bad_review['p1_findings']=1
            review.write_bytes(json.dumps(bad_review).encode());bad_review_sha=digest(review)
            with self.subTest(byte_binding='ordinary_review'):
                with replace_after_first_read(review,good_review):
                    with self.assertRaises(ValueError):pinned_load(bad_review_sha)
            review.write_bytes(good_review)
            receipt=Path(good['receipt_path']);evil_receipt=json.loads(receipt.read_bytes())
            evil_receipt['accepted_requirements'][0]['unsigned_note']='must_not_be_consumed'
            with self.subTest(byte_binding='freeze_receipt'):
                with replace_after_first_read(receipt,json.dumps(evil_receipt).encode()):
                    try:second=fixture.freeze(module,fixture.root/'receipt-race')
                    except ValueError:pass
                    else:
                        frozen=json.loads((second.parent/'accepted_deliveries.json').read_bytes())
                        self.assertNotIn('unsigned_note',frozen['deliveries'][0]['accepted_requirements'][0])
            source=Path(good['data_path']);original=source.read_bytes();source.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'source.*changed|hash.*mismatch'):
                fixture.freeze(module,fixture.root/'drift')
            self.assertFalse((fixture.root/'drift').exists());source.write_bytes(original)
            fixture.inputs[str(source)]['sha256']='0'*64;fixture.seal()
            with self.assertRaisesRegex(ValueError,'source.*mismatch'):
                fixture.freeze(module,fixture.root/'owner-drift')
            self.assertFalse((fixture.root/'owner-drift').exists())


if __name__=='__main__':unittest.main()
