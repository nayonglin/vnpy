"""Two bounded checkpoint/family regressions; no market load or account run."""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict,make_dataclass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
import stage022_run_c0_qualified_wait as runtime

LINE=Path(__file__).resolve().parents[1]
_TEMP=tempfile.TemporaryDirectory(prefix='stage098_checkpoint_fix_')
runtime.OUTPUT=Path(_TEMP.name)/'runtime'
runtime.configure_runtime(Path(_TEMP.name)/'shared')
import pandas as pd
import stage065_account_checkpoint as checkpoint
import stage065_run_pairwise_off as runner

OLD_OWNER=LINE/'outputs/stage065_pairwise_off_account/A_OFF'
FAMILY=LINE/'outputs/stage099_pairwise_off_account'
PARENT=LINE/'outputs/stage096_A_OFF_actual_failure/actual_tool_terminal.json'
PARENT_SHA='8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085'
ID='ai_top10_plus_fu_official_live_v1'


def bound_json(path,digest):
    raw=checkpoint._read_regular(path)
    if hashlib.sha256(raw).hexdigest()!=digest:raise AssertionError('test_input_sha_changed:'+str(path))
    return json.loads(raw)


def actual_metadata():
    preflight=bound_json(OLD_OWNER/'preflight_used.json',
        '4612f307b30e6917d227d624cdbf35c9ff74238a73cd1d0bd7a8267a53d92bf5')
    parameters_path=runtime.OLD/'effective_parameters.json'
    binding=preflight['data_bindings'][str(parameters_path)]
    parameters=bound_json(parameters_path,binding['sha256'])
    # Accepted formal metadata, projected by the same eight already frozen OFF keys.
    from stage065_pairwise_off_policy import OFF_SETTINGS
    parameters['spec']['overrides'].update(OFF_SETTINGS)
    return preflight,parameters


def actual_function(name):
    tree=ast.parse(checkpoint._read_regular(Path(runner.__file__)))
    return next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)


class CheckpointMetadataFixTests(unittest.TestCase):
    def test_real_096_metadata_and_prepare_prevalidation(self):
        """Catch the exact real AI-pool string collision and a missing prepare guard."""
        preflight,parameters=actual_metadata()
        envelope=dict(preflight=preflight,spec=deepcopy(parameters['spec']),parameters=parameters)
        self.assertEqual(preflight['ai_pool_audit']['strategy'],ID)
        try:checkpoint._account_only(envelope)
        except ValueError as error:self.fail('real_096_metadata_was_rejected:'+str(error))

        # Execute the guard call from the real prepare body, without executing
        # its database/data/model preparation. This is a statement boundary,
        # not a replacement prepare implementation or an account fixture.
        prepare=actual_function('prepare_account')
        calls=[node for node in ast.walk(prepare) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Attribute) and node.func.attr=='_account_only'
            and isinstance(node.func.value,ast.Name) and node.func.value.id=='checkpoint']
        self.assertEqual(len(calls),1,'real_prepare_must_prevalidate_with_checkpoint_guard')
        Spec=make_dataclass('FormalSpec',[(name,object) for name in parameters['spec']])
        spec=Spec(**deepcopy(parameters['spec']))
        metadata={name:parameters[source] for name,source in (
            ('sizes','contract_sizes'),('rates','rates'),('slippages','slippages'),('priceticks','priceticks'))}
        expression=compile(ast.fix_missing_locations(ast.Expression(body=calls[0])),str(runner.__file__),'eval')
        seen=[]
        def observe(value):
            seen.append(value)
            return checkpoint._account_only(value)
        namespace=dict(checkpoint=SimpleNamespace(_account_only=observe),preflight=preflight,
            profile={'spec':spec},metadata=metadata,asdict=asdict,_parameters=runner._parameters)
        eval(expression,namespace)
        self.assertEqual(seen,[envelope])
        bad=deepcopy(preflight);bad['ai_pool_audit']['strategy']='wrong_strategy'
        namespace['preflight']=bad
        with self.assertRaisesRegex(ValueError,'checkpoint_forbidden_engine_or_history'):eval(expression,namespace)
        self.assertEqual(runner.FROZEN['stage065_account_checkpoint.py'],
            hashlib.sha256(checkpoint._read_regular(Path(checkpoint.__file__))).hexdigest())

    def test_dangerous_objects_family_readiness_and_return_phase(self):
        """Catch broadened object exceptions, old owner reuse and missing parent pins."""
        preflight,parameters=actual_metadata()
        valid=dict(preflight=preflight,spec=parameters['spec'],parameters=parameters)
        bad_cases=[{'engine':object()},{'history':[]},{'history_data':{}},{'minute_cache':{}},
            {'stage827_minute_by_symbol':{}},{'strategy':ID},{'other':{'strategy':ID}},
            {'object':object()},[deepcopy(valid)],
            {'frame':pd.DataFrame({'cell':[{'engine':object()}]})},
            {'frame':pd.DataFrame({'cell':[deepcopy(valid)]})}]
        attr_frame=pd.DataFrame({'x':[1]});attr_frame.attrs['history']=[];bad_cases.append({'frame':attr_frame})
        for value in ('wrong_strategy',object(),{'name':ID},None):
            bad=deepcopy(valid);bad['preflight']['ai_pool_audit']['strategy']=value;bad_cases.append(bad)
        bad=deepcopy(valid);bad['preflight']['active_parameter_identity']['strategy_version']='other';bad_cases.append(bad)
        for index,bad in enumerate(bad_cases):
            with self.subTest(dangerous=index):
                with self.assertRaisesRegex(ValueError,'checkpoint_(forbidden_engine_or_history|non_account_object)'):
                    checkpoint._account_only(bad)

        with self.subTest(family_dispatch=True):
            self.assertTrue(OLD_OWNER.is_dir())
            self.assertFalse((FAMILY/'A_OFF').exists())
            class BeforePrepare(Exception):pass
            with patch.object(runner,'_readiness',side_effect=BeforePrepare),patch.object(
                    runner,'_configure_runtime',side_effect=AssertionError('runtime_must_not_start')):
                try:runner.main(['--arm','A_OFF','--run'])
                except BeforePrepare:pass
                except FileExistsError:self.fail('new_family_reused_old_A_OFF_owner')
                else:self.fail('readiness_dispatch_missing')
            self.assertEqual(runner.OUTPUT,FAMILY)
            import stage087_off_data_scope as scope
            self.assertEqual(scope.ACCOUNT_ROOT,FAMILY)
            self.assertEqual(scope.PROTOCOL,LINE/'stages/20261018_0723_stage099_checkpoint_repair_run_family_contract.md')

        with tempfile.TemporaryDirectory(prefix='stage098_readiness_') as folder:
            root=Path(folder).resolve()
            sources={}
            for path in runner.DATA_SCOPE_SOURCES:
                raw=checkpoint._read_regular(path);sources[str(path)]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            # Explicit finite receipt: no external reviewer or financial run is
            # impersonated; this temporary document only exercises parsing.
            review=root/'finite_data_scope_review.json'
            review.write_text(json.dumps(dict(fixture_only=True,independent_review=True,p0_findings=0,p1_findings=0,
                source_bindings=sources)))
            review_sha=hashlib.sha256(review.read_bytes()).hexdigest()
            readiness=bound_json(preflight['execution_readiness']['path'],preflight['execution_readiness']['sha256'])
            readiness.update(repaired_checkpoint_family='stage099_checkpoint_metadata_fix_v1',
                global_financial_attempts_before_family=9,global_arm_attempt=2,
                prior_A_OFF_checkpoint_failure=dict(path=str(PARENT),sha256=PARENT_SHA),
                data_scope_review=dict(path=str(review),sha256=review_sha))
            document=root/'finite_readiness.json'
            args=SimpleNamespace(arm='A_OFF',execution_readiness=document,data_scope_review=None,data_scope_review_sha256=None)
            def check(value):
                document.write_text(json.dumps(value));args.execution_readiness_sha256=hashlib.sha256(document.read_bytes()).hexdigest()
                return runner._readiness(args)
            self.assertEqual(check(readiness)['document']['global_arm_attempt'],2)
            for key,value in (('prior_A_OFF_checkpoint_failure',None),('repaired_checkpoint_family','old'),
                    ('global_financial_attempts_before_family',0),('global_arm_attempt',1),('global_arm_attempt',True)):
                with self.subTest(readiness_field=key,value=value):
                    bad=deepcopy(readiness)
                    if value is None:bad.pop(key)
                    else:bad[key]=value
                    with self.assertRaisesRegex(ValueError,'root_(readiness_original_terminal_binding_missing|execution_readiness_contract_not_met)'):
                        check(bad)
            b=deepcopy(readiness);b.update(arm='B_OFF',global_arm_attempt=1);args.arm='B_OFF'
            self.assertEqual(check(b)['document']['global_arm_attempt'],1)

        with self.subTest(engine_return_phase=True):
            execute=actual_function('execute_account')
            inner=next(node for node in ast.walk(execute) if isinstance(node,ast.Try)
                and any(isinstance(x,ast.Assign) and isinstance(x.value,ast.Call)
                    and isinstance(x.value.func,ast.Name) and x.value.func.id=='run_profile_once' for x in node.body))
            cut=next(index for index,node in enumerate(inner.body) if isinstance(node,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='raw_manifest' for t in node.targets))
            code=compile(ast.fix_missing_locations(ast.Module(body=inner.body[:cut+1],type_ignores=[])),str(runner.__file__),'exec')
            class RawFailure(Exception):pass
            class RawCheckpoint:
                @staticmethod
                def save_raw_checkpoint(*args,**kwargs):raise RawFailure
            spec=make_dataclass('Spec',[('profile',str)])('finite')
            ns=dict(phase='engine_not_returned',run_profile_once=lambda *a,**k:(pd.DataFrame(),{},spec),
                s901=None,prepared=dict(profile={},metadata={},start=None,end=None),engine=None,minute_audit={},
                arm='A_OFF',ordered_capture={'actual_trade_identities':[]},_parameters=lambda *a:{},
                checkpoint=RawCheckpoint,output=Path(_TEMP.name),capture={},actual=[],asdict=asdict,
                recorder=SimpleNamespace(files={}),context={},time=SimpleNamespace(monotonic=lambda:1),began=0,
                wait_audit=[],resolver_audit=[],qualification_audit={},effective=[])
            ns['prepared']['preflight']={}
            with self.assertRaises(RawFailure):exec(code,ns)
            self.assertEqual(ns['phase'],'returned_before_checkpoint')


if __name__=='__main__':unittest.main(verbosity=2)
