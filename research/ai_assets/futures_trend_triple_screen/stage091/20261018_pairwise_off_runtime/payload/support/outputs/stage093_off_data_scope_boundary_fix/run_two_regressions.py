"""Only two090 regressions; preserve087 evidence by changing test destination in memory."""
from pathlib import Path
import sys
import unittest
LINE=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
path=LINE/'tools/test_stage087_off_data_scope.py'
before="OUT = TOOLS.parent / 'outputs/stage087_off_data_scope_implementation'"
after="OUT = TOOLS.parent / 'outputs/stage093_off_data_scope_boundary_fix'"
text=path.read_text();assert text.count(before)==1
sys.path.insert(0,str(path.parent));sys.dont_write_bytecode=True
namespace={'__file__':str(path),'__name__':'stage093_memory_redirected_regressions'}
exec(compile(text.replace(before,after),str(path),'exec'),namespace)
cls=namespace['ScopeBoundaryRegressionTests']
suite=unittest.TestSuite([cls('test_owner_readiness_and_context_clock_are_bound'),
    cls('test_public_provider_launch_reserve_cannot_be_bypassed')])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful()else 1)
