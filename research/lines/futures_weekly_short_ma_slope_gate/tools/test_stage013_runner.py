import importlib.util,unittest
class Reserve100RunnerTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('run_stage013'),'Stage013 runner missing')
  import run_stage013 as m
  return m
 def test_C_only_fresh_binding_windows_and_stage013_outputs(self):
  m=self.subject();self.assertEqual(m.output_path('2017-01-01','C','002').name,'stage013_C_20170101_attempt002')
  for start,arm in [('2015-01-01','C'),('2017-01-01','A')]:
   with self.subTest(start=start,arm=arm),self.assertRaises(ValueError):m.output_path(start,arm,'002')
 def test_runner_keeps_old_reference_normalization_and_original_risk(self):
  m=self.subject();import run_stage009
  self.assertIs(m.normalize_settings,run_stage009.normalize_settings);self.assertEqual(m.RESERVE_CAPITAL,100000.);self.assertEqual(m.TOTAL_CAPITAL,250000.)
 def test_all_static_runtime_import_modules_resolve_without_starting_engine(self):
  import ast
  from pathlib import Path
  m=self.subject();tree=ast.parse(Path(m.__file__).read_text());modules=set()
  for node in ast.walk(tree):
   if isinstance(node,ast.Import):modules.update(a.name for a in node.names)
   elif isinstance(node,ast.ImportFrom) and node.module:modules.add(node.module)
  for name in sorted(modules):
   with self.subTest(module=name):self.assertIsNotNone(importlib.util.find_spec(name),'unresolved main/runtime import: '+name)
 def test_shared_upstream_helpers_and_frozen_pointers_keep_original_identity(self):
  import ast
  from pathlib import Path
  m=self.subject();tree=ast.parse(Path(m.__file__).read_text())
  bindings={node.module:tuple(n.name for n in node.names) for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
  self.assertIn('stage012_ai_selection_off',bindings)
  self.assertEqual(bindings['stage012_ai_selection_off'],('disable_ai_selection','audit_ai_selection_off','AI_FLAGS'))
  self.assertIn('stage011_bar_open_execution',bindings);self.assertIn('stage011_bar_open_audit',bindings)
  pointers={node.right.value for node in ast.walk(tree) if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div) and isinstance(node.left,ast.Name) and node.left.id=='FROZEN' and isinstance(node.right,ast.Constant) and isinstance(node.right.value,str) and node.right.value.endswith('.json')}
  self.assertEqual(pointers,{'stage029_contract_pointer_v2.json','stage012_ai_off_contract_pointer.json','M_attempt001/preflight.json'})
  for name in pointers:self.assertTrue((m.FROZEN/name).is_file(),name)
  for name in ['stage012_ai_selection_off','stage011_bar_open_execution','stage011_bar_open_audit']:
   spec=importlib.util.find_spec(name);self.assertIsNotNone(spec)
   self.assertEqual(Path(spec.origin).resolve(),(m.BASETOOLS/(name+'.py')).resolve())
 def test_all_shared_import_and_frozen_asset_bindings_match_stage012_reference(self):
  import ast
  from pathlib import Path
  m=self.subject();current=ast.parse(Path(m.__file__).read_text());reference=ast.parse(Path(m.__file__).with_name('run_stage012.py').read_text())
  allowed={'stage013_contract':'stage012_contract','stage013_reserve':'stage012_reserve'}
  def imports(tree,renames):
   rows=[]
   for node in ast.walk(tree):
    if isinstance(node,ast.Import):rows.append(('import',tuple((n.name,n.asname) for n in node.names)))
    elif isinstance(node,ast.ImportFrom):rows.append(('from',renames.get(node.module,node.module),node.level,tuple((n.name,n.asname) for n in node.names)))
   return sorted(rows,key=repr)
  self.assertEqual(imports(current,allowed),imports(reference,{}))
  original=ast.parse(Path(m.__file__).with_name('run_stage009.py').read_text())
  current_main=next(node for node in current.body if isinstance(node,ast.FunctionDef) and node.name=='main')
  original_main=next(node for node in original.body if isinstance(node,ast.FunctionDef) and node.name=='main')
  self.assertEqual(imports(current_main,{'stage013_reserve':'stage009_reserve'}),imports(original_main,{}))
  def frozen_assets(tree):
   return sorted(node.right.value for node in ast.walk(tree) if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div) and isinstance(node.left,ast.Name) and node.left.id=='FROZEN' and isinstance(node.right,ast.Constant) and isinstance(node.right.value,str))
  self.assertEqual(frozen_assets(current),frozen_assets(reference))
  self.assertEqual(frozen_assets(current),frozen_assets(original))
  for name in frozen_assets(current):self.assertTrue((m.FROZEN/name).exists(),name)
if __name__=='__main__':unittest.main()
