from pathlib import Path
import importlib,os,tempfile,json,unittest
from unittest.mock import patch
import pandas as pd
mod=importlib.import_module(os.environ.get('STAGE026_REPORT_MODULE','stage026_build_artifacts_v2'))
class RiskReportTest(unittest.TestCase):
 def fixture(self,p):
  (p/'execution_clock.csv').write_text('trade_id\n1\n')
  pd.DataFrame([dict(candidate_status='opened',skip_reason='')]).to_csv(p/'entry_candidates.csv',index=False)
  (p/'historical_target_cleanup.csv').write_text('date,vt_symbol\n')
  (p/'historical_epoch_transitions.json').write_text('[]')
  days=pd.to_datetime(['2026-01-05','2026-01-06'])
  d=pd.DataFrame(dict(date=days,total_margin_exact=[100.,200.],broker10_total_margin_exact=[110.,220.],account_equity=[1000.,1000.]))
  pos=pd.DataFrame(dict(date=days,vt_symbol=['cu2602.SHFE','rb2605.SHFE'],end_pos=[1,1]))
  fills=pd.DataFrame([dict(vt_symbol='cu2602.SHFE',direction='多',volume=1,trade_id='1',execution_datetime='2026-01-05T09:00:00'),dict(vt_symbol='rb2605.SHFE',direction='多',volume=1,trade_id='2',execution_datetime='2026-01-06T09:00:00'),dict(vt_symbol='cu2602.SHFE',direction='空',volume=1,trade_id='3',execution_datetime='2026-01-06T09:01:00')])
  return dict(path=str(p),daily=d,positions=pos,trades=fills,settings=[dict(actual=dict(stage830_broker_margin_multiplier=1.65,forced_margin_deleverage_broker_multiplier=1.65))])
 def test_actual_multiplier_and_after_fill_inventory(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=self.fixture(Path(tmp))
   with patch.object(mod.base,'ordered_fills',return_value=r['trades']):s=mod.risk_summary(r)
   self.assertAlmostEqual(s['actual_margin_to_equity_max_pct'],33.)
   self.assertEqual(s['legacy_broker10_multiplier'],1.1)
   self.assertEqual(s['max_after_fill_products'],2)
   self.assertEqual(s['max_daily_close_products'],1)
   self.assertEqual(s['actual_margin_over100_days'],0)
 def test_disagreeing_actual_multiplier_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=self.fixture(Path(tmp));r['settings'][0]['actual']['forced_margin_deleverage_broker_multiplier']=1.1
   with self.assertRaisesRegex(ValueError,'margin_multiplier_disagreement'):mod.risk_summary(r)
if __name__=='__main__':unittest.main()
