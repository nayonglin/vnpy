import importlib.util,unittest
from pathlib import Path
import pandas as pd
HERE=Path(__file__).parent

class QuarterWeeklyTest(unittest.TestCase):
 def setUp(self):
  p=HERE/'stage095_quarter_weekly_display.py';self.assertTrue(p.exists(),'pure-display weekly adapter missing');s=importlib.util.spec_from_file_location('quarter095',p);self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
 def test_off_display_rebuilds_exact_contract_without_finance_provider(self):
  calendar=pd.DataFrame({'date':pd.bdate_range('2020-01-06',periods=230)})
  market=pd.DataFrame([dict(vt_symbol=v,date=d,open=p,high=p+1,low=p-1,close=p,volume=2,execution_only=False,quote_class='accepted_clean',allow_new_open=float('nan')) for v in ('x1','x2') for n,d in enumerate(calendar.date) for p in [100+n if v=='x1' else 500-n] if not(v=='x1' and n==214)])
  contracts=pd.DataFrame([dict(vt_symbol=v,listed_date='2020-01-06') for v in ('x1','x2')]);tables=self.m.build_display_tables(market,contracts,calendar,{'x1','x2'})
  self.assertGreater(tables['x1'].close.iloc[-1],tables['x1'].close.iloc[0]);self.assertLess(tables['x2'].close.iloc[-1],tables['x2'].close.iloc[0]);self.assertTrue(pd.isna(tables['x1'].ma40.iloc[-1]));self.assertTrue(pd.notna(tables['x2'].ma40.iloc[-1]));self.assertIn('不构成',self.m.disclosure(False))
 def test_reused_replacement_protects_nonweekly_and_coordinates(self):
  import stage063_contract_weekly_recap as old
  self.assertIs(self.m.replace_weekly_records,old.replace_weekly_records);self.assertIs(self.m.non_weekly_payload_hash,old.non_weekly_payload_hash)

if __name__=='__main__':unittest.main()
