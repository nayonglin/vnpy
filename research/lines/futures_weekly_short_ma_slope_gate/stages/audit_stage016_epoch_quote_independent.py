"""Synthetic explicit-epoch updater counterexample; no downloads or finance."""
import sys,unittest,pandas as pd
from pathlib import Path
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path[:0]=[str(R/'examples/portfolio_backtesting'),str(R/'tests')]
from test_weekly19_data_update import UpdateTests
import qmt_roll_weekly19_data_update as updater
class ExplicitEpochQuoteIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=UpdateTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_explicit_registry_rejects_new_decade_quote_for_existing_native_symbol(self):
  original=self.fx.backend.fetch_contracts
  def changed(*args,**kwargs):
   result=original(*args,**kwargs);symbol='AP612.CZCE'
   result[symbol]['quote']['delivery_year']=2036
   result[symbol]['quote']['expire_datetime']=pd.Timestamp('2036-12-20',tz='Asia/Shanghai').timestamp();return result
  self.fx.backend.fetch_contracts=changed
  with self.assertRaises(updater.DataUpdateError):self.fx.run_update()
  self.assertFalse((self.fx.generations/'latest.json').exists())
 def test_matching_explicit_quote_preserves_real_known_epoch_and_close_oi(self):
  out=self.fx.run_update();frame=pd.read_csv(Path(out['asset_root'])/'physical_epoch_daily.csv')
  row=frame[(frame.vt_symbol=='AP612.CZCE')&(frame.date=='2026-11-02')].iloc[0]
  self.assertEqual(row.contract_epoch_id,'CZCE.AP.202612');self.assertEqual(row.close_oi,2200.)
  self.assertFalse(out['production_qualified'])
if __name__=='__main__':unittest.main(verbosity=2)
