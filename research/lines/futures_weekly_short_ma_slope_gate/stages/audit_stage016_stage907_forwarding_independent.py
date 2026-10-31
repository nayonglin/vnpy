"""Pure shell-command construction only; never invokes the constructed command."""
from pathlib import Path
import shlex,sys,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import run_qmt_roll_stage907_official_live_readonly_refresh_gate as wrapper
class WrapperForwardIndependent(unittest.TestCase):
 def test_optional_statement_day_is_one_exact_argument(self):
  argv,_=wrapper._production_live_command(30,'offline-fixture',weekly19_capture_options=('--weekly19-settlement-trading-day','2026-10-30'))
  tokens=shlex.split(argv[-1].splitlines()[-1]);i=tokens.index('--weekly19-settlement-trading-day');self.assertEqual(tokens[i+1],'2026-10-30')
 def test_forwarded_value_is_quoted_without_executing_it(self):
  value="2026-10-30'; literal-only #"
  argv,_=wrapper._production_live_command(30,'offline-fixture',weekly19_capture_options=('--weekly19-settlement-trading-day',value))
  tokens=shlex.split(argv[-1].splitlines()[-1]);self.assertEqual(tokens[-1],value)
 def test_odd_or_foreign_option_rejected_before_any_subprocess(self):
  for args in [('--weekly19-settlement-trading-day',),('--arbitrary-command','not-executed')]:
   with self.subTest(args=args):
    with self.assertRaisesRegex(ValueError,'capture_options_invalid'):wrapper._production_live_command(30,'offline-fixture',weekly19_capture_options=args)
if __name__=='__main__':unittest.main(defaultTest='WrapperForwardIndependent')
