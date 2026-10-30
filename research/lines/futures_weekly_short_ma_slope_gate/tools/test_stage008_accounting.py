import importlib.util,tempfile,unittest
from pathlib import Path
import pandas as pd
MODULE=Path(__file__).with_name('stage008_accounting.py')
def subject():
 s=importlib.util.spec_from_file_location('a',MODULE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class AccountingTests(unittest.TestCase):
 def test_exact_user_start_set_is_whitelisted(self):
  m=subject();self.assertEqual(len(m.STARTS),23);self.assertIn('2015-06-01',m.STARTS);self.assertNotIn('2015-07-01',m.STARTS);self.assertEqual(m.STARTS[-1],'2026-01-01')
  with self.assertRaises(ValueError):m.validate_key('2015-07-01','A')
 def test_actual_calendar_cannot_come_from_truncated_or_wrong_window(self):
  m=subject();first=m.window_meta('2016-01-01')['actual_first_day'];dates=pd.to_datetime(m.expected_days('2016-01-01'));pre={'start':'2016-01-01','end':m.END};m.validate_window(pre,pd.DataFrame({'date':dates}),'2016-01-01');bad=pd.DataFrame({'date':dates[1:]})
  with self.assertRaises(ValueError):m.validate_window(pre,bad,'2016-01-01')
 def test_ast_replaces_only_gate_and_window_identity_checks(self):
  m=subject();tree,r=m.loader_ast();self.assertEqual(r['gate_checks_replaced'],1);self.assertEqual(r['window_checks_replaced'],1);self.assertFalse(r['arm_check_changed']);self.assertTrue(r['old_source_unchanged']);self.assertIn('arm_role_mismatch',r['retained_string_literals']);self.assertIn('daily_equity_conservation',r['retained_string_literals'])
 def test_legacy_missing_range_certificate_requires_exact_registered_path(self):
  m=subject();self.assertTrue(m.is_legacy_2020_A(m.LEGACY_2020_A,'2020-01-01','A'));self.assertFalse(m.is_legacy_2020_A(m.LEGACY_2020_A,'2020-01-01','C'));self.assertFalse(m.is_legacy_2020_A(Path('/tmp/fake'),'2020-01-01','A'))
 def test_hash_substantive_drift_is_not_accepted(self):
  m=subject()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_text('source');expected={str(p):m.sha(p)};m.verify_sources(expected);p.write_text('changed')
   with self.assertRaises(ValueError):m.verify_sources(expected)
 def test_checkpoint_float_roundtrip_tolerance_rejects_material_drift(self):
  m=subject();a=dict(end_equity=1000000.,total_return_pct=566.6666666667,max_dd_pct=-30.,sharpe=1.1,total_slippage=100.,modeled_fill_count=20);b={**a,'total_trade_count':20};b['end_equity']+=1e-8;m.check_registered_metrics(a,b);b['end_equity']+=1.
  with self.assertRaises(ValueError):m.check_registered_metrics(a,b)
 def test_new_runs_cannot_hide_a_long_price_gate(self):
  m=subject();m.validate_disabled_long({'long_price_range_acceptance.json':dict(enabled=False,decision_count=0,applied_block_count=0)},True)
  with self.assertRaises(ValueError):m.validate_disabled_long({},True)
  with self.assertRaises(ValueError):m.validate_disabled_long({'long_price_range_acceptance.json':dict(enabled=True,decision_count=0,applied_block_count=0)},True)
 def test_only_declared_start_can_change_in_settings(self):
  m=subject();s=[{'setting':{'trade_start_date':'2016-06-01','risk':1},'actual':{'trade_start_date':'2016-06-01','risk':1}}];r=m.normalize_settings(s,'2016-06-01');self.assertEqual(r[0]['actual']['trade_start_date'],'<declared-independent-start>');self.assertEqual(r[0]['actual']['risk'],1)
  with self.assertRaises(ValueError):m.normalize_settings(s,'2016-01-01')
if __name__=='__main__':unittest.main()
