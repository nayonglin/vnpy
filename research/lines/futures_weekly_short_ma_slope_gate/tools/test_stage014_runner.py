import ast,importlib.util,json,unittest
from pathlib import Path
from copy import deepcopy

class FiveStartRunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage014'),'Stage014 runner missing')
  import run_stage014 as m
  return m
 def test_new_month_normalization_keeps_original_risk_and_capital(self):
  m=self.subject();old=json.loads((m.FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]['actual'];current=deepcopy(old);mapping=m.LINE/'outputs/data_stage014_20261030/data_approved/mapping.csv';current.update(mapping_csv_path=str(mapping),trade_start_date='2015-09-01')
  for key,value in list(current.items()):
   if isinstance(value,str):current[key]=value.replace('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/',str(m.ROOT)+'/')
  self.assertEqual(m.normalize_settings(current,old,mapping,{},'2015-09-01'),old)
  current['risk_ratio_open_interest_surge']=.018
  with self.assertRaises(ValueError):m.normalize_settings(current,old,mapping,{},'2015-09-01')
 def test_runtime_imports_and_all_frozen_assets_preserve_shared_identity(self):
  m=self.subject();tree=ast.parse(Path(m.__file__).read_text());old=ast.parse(Path(m.__file__).with_name('run_stage009.py').read_text());modules=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Import):modules.extend(x.name for x in n.names)
   elif isinstance(n,ast.ImportFrom) and n.module:modules.append(n.module)
  for module in set(modules):
   with self.subTest(module=module):self.assertIsNotNone(importlib.util.find_spec(module))
  imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)};self.assertIn('stage012_ai_selection_off',imports);self.assertNotIn('stage014_ai_selection_off',imports)
  for module in ['stage012_ai_selection_off','stage011_bar_open_execution','stage011_bar_open_audit']:self.assertEqual(Path(importlib.util.find_spec(module).origin).resolve(),(m.BASETOOLS/(module+'.py')).resolve())
  def assets(t):return sorted(n.right.value for n in ast.walk(t) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div) and isinstance(n.left,ast.Name) and n.left.id=='FROZEN' and isinstance(n.right,ast.Constant) and isinstance(n.right.value,str))
  self.assertEqual(assets(tree),assets(old))
  for name in assets(tree):self.assertTrue((m.FROZEN/name).exists())
  def shared_imports(t):
   rows=[]
   main=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='main')
   for n in ast.walk(main):
    if isinstance(n,ast.Import):rows.append(('import',tuple((a.name,a.asname) for a in n.names)))
    elif isinstance(n,ast.ImportFrom):rows.append(('from','stage009_reserve' if n.module=='stage014_reserve' else n.module,tuple((a.name,a.asname) for a in n.names)))
   return sorted(rows,key=repr)
  self.assertEqual(shared_imports(tree),shared_imports(old))
 def test_C_only_all59_outputs_and_true_completed_cutoff(self):
  m=self.subject();self.assertEqual(m.output_path('2026-09-01','C','001').name,'stage014_C_20260901_attempt001')
  with self.assertRaises(ValueError):m.output_path('2015-03-01','A','001')
  receipt=dict(date_start='2014-01-01',date_end='2026-10-30',data_ready=True,data_ready_for_bounded_replay=True,main_missing_2015_onward=0)
  self.assertEqual(m.validate_window('2015-11-01','2026-10-30',receipt),('2015-11-01','2026-10-30'))
  with self.assertRaises(ValueError):m.validate_window('2015-11-01','2026-11-02',receipt)
if __name__=='__main__':unittest.main()
