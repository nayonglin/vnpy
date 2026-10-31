"""Pure runtime DTO/source boundary tests; never constructs a strategy engine."""
import copy,sys,types,unittest
from pathlib import Path
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path[:0]=[str(R/'examples/portfolio_backtesting'),str(R/'tests')]
import qmt_roll_weekly19_runtime as runtime
import test_weekly19_runtime as fixture
class BarBindingIndependent(unittest.TestCase):
 def setUp(self):
  calendar,frame,bars,meta=fixture.fixture();frame['close_oi']=2000.0
  self.actor=object.__new__(runtime.Runtime);self.actor.metadata=meta;self.actor.calendar=calendar
  self.actor.epoch_lookup={(r.vt_symbol,r.date):r.contract_epoch_id for r in frame.itertuples()}
  self.actor.range_history=types.SimpleNamespace(table=frame.set_index(['vt_symbol','date']));self.actor.physical_frame=frame
  self.bar=copy.deepcopy(bars['2026-10-29'][fixture.SYMBOL])
 def reject(self,field,value):
  bar=copy.deepcopy(self.bar);setattr(bar,field,value)
  with self.assertRaises(runtime.RuntimeContractError):self.actor._validate_bars({fixture.SYMBOL:bar},expected_day='2026-10-29')
 def test_nonfinite_volume_never_reaches_an_array_manager(self):
  for value in [float('nan'),float('inf'),-float('inf')]:
   with self.subTest(value=value):self.reject('volume',value)
 def test_close_oi_must_be_finite_and_equal_to_approved_source(self):
  for value in [float('nan'),float('inf'),-1.0,987654321.0]:
   with self.subTest(value=value):self.reject('open_interest',value)
 def test_high_and_low_cannot_differ_from_source_even_when_bar_is_valid(self):
  for field,value in [('high_price',999.0),('low_price',1.0)]:
   with self.subTest(field=field):self.reject(field,value)
 def test_open_and_volume_cannot_differ_from_source_even_when_positive(self):
  for field,value in [('open_price',99.75),('volume',1001.0)]:
   with self.subTest(field=field):self.reject(field,value)
 def test_exact_real_source_and_zero_close_oi_remain_legal(self):
  self.assertEqual(self.actor._validate_bars({fixture.SYMBOL:self.bar},expected_day='2026-10-29'),'2026-10-29')
  self.actor.range_history.table.loc[(fixture.SYMBOL,'2026-10-29'),'close_oi']=0.0
  self.actor.physical_frame.loc[self.actor.physical_frame.date=='2026-10-29','close_oi']=0.0
  self.bar.open_interest=0.0
  self.assertEqual(self.actor._validate_bars({fixture.SYMBOL:self.bar},expected_day='2026-10-29'),'2026-10-29')
if __name__=='__main__':unittest.main(verbosity=2)
