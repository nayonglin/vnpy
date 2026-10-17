"""Independent, single-test execution; only its evidence destination changes in memory."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

LINE = Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
OUT = LINE / 'outputs/stage079_pairwise_off_checkpoint_independent_review'
TEST = LINE / 'tools/test_stage065_pairwise_off_integration.py'
PINS = {
    LINE / 'tools/stage065_account_checkpoint.py': '7e5a265a23b8fce871c895292e0738831604eefb9a341f7a83bd0320a68cf15b',
    TEST: '2515326d771587c5ed49459c54286bd3f5c682c39455155082fd1daf982664c0',
    LINE / 'tools/stage065_pairwise_off_policy.py': 'edaa018cebe288245197dcb8b4bfba76e2a1c1691cf24c7de369a91bc62a639f',
}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for path, expected in PINS.items():
    assert sha(path) == expected, str(path)
protected = {path: sha(path) for path in
    (LINE / 'outputs/stage076_pairwise_off_checkpoint_implementation').glob('*') if path.is_file()}
raw = TEST.read_bytes()
start = raw.index(b'    def test_real_fill_identity_checkpoint_and_pure_export(')
end = raw.index(b'    def planner_cases(', start)
original_sha = hashlib.sha256(raw[:start] + raw[end:]).hexdigest()
assert original_sha == '51731fdd31bd9fe2d7ba7f04ed34fc99f3c19fddb70dd7abae839d35c5771539'
before = 'destination=LINE/"outputs/stage076_pairwise_off_checkpoint_implementation"'
after = 'destination=Path(' + repr(str(OUT)) + ')'
text = raw.decode()
assert text.count(before) == 1
text = text.replace(before, after)
sys.dont_write_bytecode = True
sys.path.insert(0, str(LINE / 'tools'))
namespace = {'__file__': str(TEST), '__name__': 'stage079_memory_redirected_test'}
exec(compile(text, str(TEST), 'exec'), namespace)
suite = unittest.TestSuite([namespace['PairwiseOffIntegrationTests'](
    'test_real_fill_identity_checkpoint_and_pure_export')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
changed = [str(path) for path, expected in {**PINS, **protected}.items() if sha(path) != expected]
assert not changed, changed
record = dict(schema='stage079_single_test_execution_v1',
    test_name='PairwiseOffIntegrationTests.test_real_fill_identity_checkpoint_and_pure_export',
    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
    successful=result.wasSuccessful(), task1_2_reconstructed_sha256=original_sha,
    memory_change='one evidence destination literal only; original test __file__ and all code identities retained',
    original_source_files_unchanged=True, author_stage076_output_files_unchanged=True,
    source_fingerprints={str(p): h for p, h in PINS.items()},
    protected_stage076_output_sha256={str(p): h for p, h in protected.items()},
    financial_replays=0, network_connections=0, orders=0)
(OUT / 'fresh_execution.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
sys.exit(0 if result.wasSuccessful() else 1)
