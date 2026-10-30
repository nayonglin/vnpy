"""Independent full-import/frozen-asset recovery review; no engine invocation."""
from pathlib import Path
import ast,copy,hashlib,importlib.machinery as machinery,json,subprocess,sys
from stage013_independent_admission import reserve_AST
from stage013_independent_code_review import financial,norm
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';TOOLS=LINE/'tools';HEAD1='0c9f18628303519247666ee09ba7e018cd1e8689'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def selected(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def imports(tree,rename=None):
 rename=rename or {};rows=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):rows.append(('import',tuple((a.name,a.asname) for a in n.names)))
  elif isinstance(n,ast.ImportFrom):rows.append(('from',rename.get(n.module,n.module),n.level,tuple((a.name,a.asname) for a in n.names)))
 return sorted(rows,key=repr)
def assets(tree):return sorted(n.right.value for n in ast.walk(tree) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div) and isinstance(n.left,ast.Name) and n.left.id=='FROZEN' and isinstance(n.right,ast.Constant) and isinstance(n.right.value,str))
def resolve_without_execution(module,search):
 path=search;spec=None
 for i,name in enumerate(module.split('.')):
  full='.'.join(module.split('.')[:i+1]);spec=machinery.BuiltinImporter.find_spec(full) or machinery.FrozenImporter.find_spec(full) or machinery.PathFinder.find_spec(full,path)
  if spec is None:raise AssertionError('unresolved_runtime_import:'+module)
  path=spec.submodule_search_locations
  if i<len(module.split('.'))-1 and path is None:raise AssertionError('nonpackage_parent:'+module)
 return spec

def main():
 out=STAGES/'stage013_independent_code_review_v2.json'
 if out.exists():raise ValueError('immutable_review_v2_exists')
 new=TOOLS/'run_stage013.py';tree=ast.parse(new.read_text());reference=ast.parse((TOOLS/'run_stage012.py').read_text());oldtree=ast.parse((TOOLS/'run_stage009.py').read_text());names={'stage013_contract':'stage012_contract','stage013_reserve':'stage012_reserve'}
 assert imports(tree,names)==imports(reference),'whole_runner_import_binding_changed_outside_owned_contract_and_reserve'
 assert assets(tree)==assets(reference),'shared_frozen_asset_literals_changed'
 search=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_weekly_formal_no_half_r/tools'),str(TOOLS),*sys.path]
 modules=set()
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):modules.update(a.name for a in n.names)
  elif isinstance(n,ast.ImportFrom) and n.module:modules.add(n.module)
 resolved={}
 for name in sorted(modules):
  s=resolve_without_execution(name,search);origin=s.origin;resolved[name]={'origin':origin,'sha256':sha(origin) if origin and Path(origin).is_file() else None,'locations':list(s.submodule_search_locations or [])}
 relocations={};oldjob=load(LINE/'outputs/stage009_multistart/registry.json')['jobs']['2017-01-01|C'];inputs=load(Path(oldjob['path'])/'input_manifest.json');assetpins={}
 for name in assets(tree):
  q=LINE/'outputs/frozen_baseline'/name;assert q.exists();assetpins[str(q)]=sha(q) if q.is_file() else None
  if q.is_file():
   original=str(q) if str(q) in inputs else '/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/'+name
   assert original in inputs and inputs[original]==sha(q),'old_asset_SHA_changed:'+str(q)
   relocations[str(q)]=original
 pointer=LINE/'outputs/frozen_baseline/stage012_ai_off_contract_pointer.json';contract=load(pointer);assert sha(contract['path'])==contract['sha256'];assetpins[contract['path']]=sha(contract['path'])
 assert resolved['stage012_ai_selection_off']['origin']==str(ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage012_ai_selection_off.py')
 oldhelper='/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/tools/stage012_ai_selection_off.py';assert inputs[oldhelper]==resolved['stage012_ai_selection_off']['sha256'];relocations[resolved['stage012_ai_selection_off']['origin']]=oldhelper
 kept=[];witness=[]
 for n in financial(tree):
  if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='dump' and any(isinstance(q,ast.Constant) and q.value in ['actual_strategy_settings.json','reserve_limit_acceptance.json'] for q in ast.walk(n)):witness.append(ast.unparse(n));continue
  kept.append(n)
 assert len(witness)==2 and norm(financial(oldtree))==norm(kept),'financial_body_changed'
 for name in ['Engine','overrides']:assert norm([selected(tree,name)])==norm([selected(oldtree,name)]),'financial_component_changed:'+name
 v1source=subprocess.check_output(['git','show',HEAD1+':'+str(new.relative_to(ROOT))],text=True);expected=v1source.replace("stage013_freeze.json","stage013_freeze_v2.json").replace('from stage013_ai_selection_off import','from stage012_ai_selection_off import').replace("'stage013_ai_off_contract_pointer.json'","'stage012_ai_off_contract_pointer.json'");assert ast.dump(ast.parse(expected),include_attributes=False)==ast.dump(tree,include_attributes=False),'runner_change_beyond_two_dependency_restores_and_v2_freeze';v1=ast.parse(v1source);v1imports=imports(v1);assert ('from','stage013_ai_selection_off',0,(('disable_ai_selection',None),('audit_ai_selection_off',None),('AI_FLAGS',None))) in v1imports
 failed=LINE/'outputs/stage013_C_20170101_attempt001';log=LINE/'outputs/stage013_multistart/logs/2017-01-01_C_attempt001.log';text=log.read_text();assert 'ModuleNotFoundError' in text and 'stage013_ai_selection_off' in text;assert sorted(q.name for q in failed.iterdir())==['actual_database_binding.json'];assert next(n.lineno for n in ast.walk(v1) if isinstance(n,ast.ImportFrom) and n.module=='stage013_ai_selection_off')<selected(v1,'Engine').lineno
 preengine={'attempt_registry_counter':load(LINE/'outputs/stage013_multistart/registry.json')['financial_replays_started'],'true_new_engine_constructions':0,'new_financial_results':0,'failure_phase':'main shared import before Engine definition and s901.run_single_case','failed_log_sha256':sha(log),'failed_output_files_sha256':{str(q):sha(q) for q in failed.iterdir()},'old_freeze_sha256':sha(STAGES/'stage013_freeze.json'),'old_source_head':HEAD1,'old_runner_sha256':hashlib.sha256(v1source.encode()).hexdigest()}
 source_names=['stage013_reserve','stage013_reuse','stage013_contract','run_stage013','stage013_coordinator','test_stage013_reserve','test_stage013_reuse','test_stage013_contract','test_stage013_runner','test_stage013_coordinator'];sources={str(TOOLS/(n+'.py')):sha(TOOLS/(n+'.py')) for n in source_names};testlog=STAGES/'stage013_independent_core_tests_attempt004.log';assert testlog.read_text().rstrip().endswith('OK')
 admission=load(STAGES/'stage013_independent_reuse_admission.json');assert admission['accepted'];cache=load(admission['source_hash_cache']);assert sha(admission['source_hash_cache'])==admission['source_hash_cache_sha256'];
 for q,row in cache['files'].items():
  st=Path(q).stat();assert [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==row['stat'],'unchanged_reuse_graph_stat:'+q
 assert reserve_AST()==admission['reserve_AST'],'reserve_source_and_induction_changed'
 result=dict(schema='stage013_independent_source_recovery_v2',accepted=True,status='PASS_SOURCE_V2_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=[],resolved_runtime_imports=resolved,complete_runner_import_AST_equal_to_frozen_Stage012_except_owned_modules=True,shared_frozen_assets_sha256=assetpins,explicit_same_byte_upstream_relocations=relocations,financial_try_AST_unchanged_except_stage_and_witnesses=True,engine_AST_unchanged=True,strategy_overrides_AST_unchanged=True,source_files_sha256=sources,preengine_failure=preengine,recovery_record_sha256=sha(STAGES/'20261030_stage013_pre_engine_import_recovery.md'),unchanged_admitted_graph_files=len(cache['files']),runner_v1_to_v2_only_dependency_restores_and_freeze_path=True,preexisting_review_miss='V1 reviewer compared financial try/Engine/overrides but omitted pre-try imports and shared frozen pointers; V2 adds complete import and asset identity checks.',reuse_admission_sha256=sha(STAGES/'stage013_independent_reuse_admission.json'),reuse_induction_still_valid=True,reuse_admission_rehash_needed=False,reuse_unchanged_reason='Reserve implementation byte/AST unchanged; old controls and dedup SHA/stat cache unchanged; corrected imports restore exact already-bound upstream helper and contract.',independent_core_tests_sha256=sha(testlog),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'imports':len(resolved),'status':result['status']},ensure_ascii=False))
if __name__=='__main__':main()
