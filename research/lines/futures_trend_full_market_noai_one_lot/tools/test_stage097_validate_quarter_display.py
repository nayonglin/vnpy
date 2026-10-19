import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).parent

class QuarterAuditTest(unittest.TestCase):
 def test_complete_two_arm_frozen_pipeline_and_independent_2862_point_audit(self):
  import json
  from unittest.mock import patch
  from test_stage094_quarter_risk_recap import frozen_arm
  import stage083_final_multilot_labels as labels
  import stage067_current_trade_reset as reset
  import stage096_quarter_pair_overview as pair
  import stage097_validate_quarter_display as audit
  a,b=frozen_arm(self,True),frozen_arm(self,False)
  for arm in (a,b):
   lab=arm['root']/'labels';labels.generate(arm['weekly'],lab);arm['final']=arm['root']/'final';reset.generate(lab,arm['final'])
  out=a['root']/'pair';r=pair.generate(a['source'],b['source'],a['final'],b['final'],out);self.assertEqual(r['points_per_arm'],2862);self.assertIsNone(r['disabled']['weekly_violations'])
  with patch.object(audit.independent,'BASELINE_SHA',a['data_hash']):
   report=audit.validate_pair(a['source'],b['source'],a['data'],out,a['raw'],b['raw'],a['fractional'],b['fractional'],a['weekly'],b['weekly'],a['final'],b['final'])
  self.assertEqual(report['overview']['curve_values_checked'],2862*6);self.assertEqual(report['disabled']['weekly_strategy_violations'],'N/A');self.assertEqual(report['enabled']['complete_entries'],1)
  for name,digest in r['artifact_sha256'].items():self.assertEqual(pair.base.sha(out/name),digest)
  self.assertGreater(report['overview']['javascript_blocks'],0)
  with self.assertRaises(FileExistsError):pair.generate(a['source'],b['source'],a['final'],b['final'],out)
  (out/'equity_pair.csv').write_text('tampered')
  with patch.object(audit.independent,'BASELINE_SHA',a['data_hash']):
   with self.assertRaisesRegex(ValueError,'artifact_hash'):audit.validate_pair(a['source'],b['source'],a['data'],out)
  import pandas as pd
  trades=pd.read_csv(b['source']/'trades.csv',keep_default_na=False);trades.loc[trades.offset.eq('open'),'stage059_weekly_signal_snapshot']='{}';trades.to_csv(b['source']/'trades.csv',index=False)
  with self.assertRaisesRegex(ValueError,'off_trade_claims_weekly_authorization_expected_null'):audit.source_mode(b['source'],False)

 def test_quarter_audit_reuses_independent_math_with_only_declared_literals(self):
  p=HERE/'stage097_validate_quarter_display.py';self.assertTrue(p.exists(),'quarter display audit missing');s=importlib.util.spec_from_file_location('audit097',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  proof=m.audit_namespace()[1];self.assertTrue(proof['only_declared_constants_changed']);self.assertEqual(m.check_mode_metrics(False,dict(weekly_signal_candidates=0,weekly_budget_eligible_long_signal_rejections=0,weekly_execution_checks=0,weekly_execution_rejections=0,actual_long_weekly_violations=None)),'N/A')
  with self.assertRaisesRegex(ValueError,'off_not_NA'):m.check_mode_metrics(False,dict(weekly_signal_candidates=0,weekly_budget_eligible_long_signal_rejections=0,weekly_execution_checks=0,weekly_execution_rejections=0,actual_long_weekly_violations=0))

if __name__=='__main__':unittest.main()
