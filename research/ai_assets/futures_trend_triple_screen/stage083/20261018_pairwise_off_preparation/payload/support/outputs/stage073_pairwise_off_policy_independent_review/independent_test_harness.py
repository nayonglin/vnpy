from pathlib import Path
import hashlib, json, sys, tempfile, unittest
from contextlib import ExitStack
from unittest.mock import patch
sys.dont_write_bytecode = True
root = Path('/Users/mac/Desktop/fian')
line = root/'research/lines/futures_trend_triple_screen'
out = line/'outputs/stage073_pairwise_off_policy_independent_review'
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0,str(line/'tools'))
import stage022_run_c0_qualified_wait as runtime
with tempfile.TemporaryDirectory(prefix='stage073_runtime_') as temp:
    runtime.OUTPUT = Path(temp)/'runtime'
    runtime.configure_runtime(Path(temp)/'shared')
    import joblib
    from sklearn.pipeline import Pipeline
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    calls = dict(load=0,runtime=0,score=0,predict=0,fit=0,old_smoke=0)
    def forbidden(name):
        def fail(*args,**kwargs):
            calls[name] += 1
            raise AssertionError('stage073_forbidden_model_path:'+name)
        return fail
    with ExitStack() as stack:
        stack.enter_context(patch.object(joblib,'load',forbidden('load')))
        stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel,'__init__',forbidden('runtime')))
        stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel,'score_candidate_pool',forbidden('score')))
        for name in ('predict','predict_proba'):
            stack.enter_context(patch.object(Pipeline,name,forbidden('predict')))
        stack.enter_context(patch.object(Pipeline,'fit',forbidden('fit')))
        stack.enter_context(patch.object(runtime,'model_runtime_smoke',forbidden('old_smoke')))
        import test_stage065_pairwise_off_integration as module
        module.EVIDENCE = out
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.PairwiseOffIntegrationTests)
        with (out/'independent_tests.txt').open('w') as stream:
            result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        receipt = dict(schema='stage073_independent_test_receipt_v1',
            source_sha256=hashlib.sha256((line/'tools/stage065_pairwise_off_policy.py').read_bytes()).hexdigest(),
            test_sha256=hashlib.sha256((line/'tools/test_stage065_pairwise_off_integration.py').read_bytes()).hexdigest(),
            tests_run=result.testsRun, failures=len(result.failures),errors=len(result.errors),
            successful=result.wasSuccessful(),outer_model_spies=calls,
            frozen_numerical_stack={name:sys.modules[name].__version__ for name in ('numpy','pandas','sklearn','joblib')},
            evidence_redirected_to=str(out),financial_replays=0,production_qualified=False)
        (out/'independent_test_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        print((out/'independent_tests.txt').read_text())
        print(json.dumps(receipt,ensure_ascii=False,indent=2))
        raise SystemExit(0 if result.wasSuccessful() and not any(calls.values()) else 1)
