"""Run exactly the three new integration methods, preserving older evidence."""
from pathlib import Path
import sys
import types
import unittest
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[5]
source=root/'research/lines/futures_trend_triple_screen/tools/test_stage065_pairwise_off_integration.py'
out=Path(__file__).resolve().parent
sys.path.insert(0,str(source.parent))
text=source.read_text()
old='destination=LINE/"outputs/stage076_pairwise_off_checkpoint_implementation"'
assert text.count(old)==1
text=text.replace(old,'destination=LINE/"outputs/stage084_pairwise_off_runner_implementation"')
module=types.ModuleType('stage084_finite_tests');module.__file__=str(source)
sys.modules[module.__name__]=module
exec(compile(text,str(source),'exec'),module.__dict__)
module.EVIDENCE=out
names=['test_disabled_profiles_native_and_b_no_model',
       'test_real_planner_fallback_slot_margin_and_b_final_budget',
       'test_real_fill_identity_checkpoint_and_pure_export']
suite=unittest.TestSuite(module.PairwiseOffIntegrationTests(name) for name in names)
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
