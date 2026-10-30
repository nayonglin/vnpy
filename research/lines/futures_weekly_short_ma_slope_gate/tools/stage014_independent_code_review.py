"""Independent Stage014 source and real-import admission. Does not construct an engine."""
from pathlib import Path
import ast,copy,hashlib,json,sys
from stage013_independent_code_review_v2 import resolve_without_execution
from stage014_independent_scope import canonical_starts,scope
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';TOOLS=LINE/'tools'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
def norm(nodes):
 nodes=copy.deepcopy(nodes)
 for root in nodes:
  for n in ast.walk(root):
   if isinstance(n,ast.Constant) and isinstance(n.value,str):n.value=n.value.replace('stage014','stage009')
 return ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
def selected(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def financial(tree):return next(n for n in selected(tree,'main').body if isinstance(n,ast.Try)).body
def main():
 out=STAGES/'stage014_independent_code_review.json'
 if out.exists():raise ValueError('immutable_code_admission_exists')
 old=ast.parse((TOOLS/'run_stage009.py').read_text());new=ast.parse((TOOLS/'run_stage014.py').read_text());assert norm(financial(old))==norm(financial(new)),'financial_try_changed'
 for name in ['Engine','overrides','_margin','normalize_settings','normalize_effective']:assert norm([selected(old,name)])==norm([selected(new,name)]),'economic_or_normalization_AST_changed:'+name
 assert (TOOLS/'stage014_reserve.py').read_bytes()==(TOOLS/'stage009_reserve.py').read_bytes(),'reserve_economic_class_changed'
 def imports(tree,current=False):
  rows=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Import):rows.append(('import',tuple((a.name,a.asname) for a in n.names)))
   elif isinstance(n,ast.ImportFrom):
    mod=n.module;names=[(a.name,a.asname) for a in n.names]
    if current and mod=='stage014_contract':mod='stage009_contract';assert [a for a,b in names if a not in [x.name for x in next(z for z in ast.walk(old) if isinstance(z,ast.ImportFrom) and z.module=='stage009_contract').names]]==['required_financial_sources','CUTOFF'];names=[(a,b) for a,b in names if a not in ['required_financial_sources','CUTOFF']]
    if current and mod=='stage014_reserve':mod='stage009_reserve'
    rows.append(('from',mod,n.level,tuple(names)))
  return sorted(rows,key=repr)
 assert imports(old)==imports(new,True),'whole_entry_import_binding_changed'
 def assets(t):return sorted(n.right.value for n in ast.walk(t) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div) and isinstance(n.left,ast.Name) and n.left.id=='FROZEN' and isinstance(n.right,ast.Constant) and isinstance(n.right.value,str))
 assert assets(old)==assets(new),'shared_frozen_asset_literal_changed'
 search=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_weekly_formal_no_half_r/tools'),str(TOOLS),*sys.path];modules=set()
 for n in ast.walk(new):
  if isinstance(n,ast.Import):modules.update(a.name for a in n.names)
  elif isinstance(n,ast.ImportFrom) and n.module:modules.add(n.module)
 resolved={}
 for name in sorted(modules):
  s=resolve_without_execution(name,search);resolved[name]=dict(origin=s.origin,sha256=sha(s.origin) if s.origin and Path(s.origin).is_file() else None,locations=list(s.submodule_search_locations or []))
 assetsmap={str(LINE/'outputs/frozen_baseline'/a):sha(LINE/'outputs/frozen_baseline'/a) for a in assets(new) if (LINE/'outputs/frozen_baseline'/a).is_file()}
 assert resolved['stage012_ai_selection_off']['origin']==str(ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage012_ai_selection_off.py')
 # New validators must own the expanded domain; original23 remains untouched.
 import stage014_contract as contract,stage009_contract as baseline
 assert list(contract.STARTS)==canonical_starts() and len(baseline.STARTS)==23 and len(contract.MATURE_STARTS)==54 and len(contract.OBSERVATION_STARTS)==5
 for start in canonical_starts():assert contract.validate_start(start)==start
 for start in ['2014-11-01','2026-11-01','2017-02-01']:
  try:contract.validate_start(start)
  except ValueError:pass
  else:raise AssertionError('invalid_start_accepted:'+start)
 admission=load(STAGES/'stage014_independent_data_admission.json');assert admission['accepted'] and admission['starts']==canonical_starts();testlog=STAGES/'stage014_independent_core_tests_attempt001.log';assert testlog.read_text().rstrip().endswith('OK')
 sources={str(TOOLS/n):sha(TOOLS/n) for n in ['run_stage014.py','stage014_contract.py','stage014_reserve.py','stage014_coordinator.py','test_stage014_reserve.py','test_stage014_contract.py','test_stage014_runner.py','test_stage014_coordinator.py']}
 # Reuse signed unchanged-byte hash evidence for the old source graph; rehash any changed fingerprint.
 merged={};drift={}
 for oldcache in [STAGES/'stage013_independent_hash_cache.json',Path(admission['source_hash_cache'])]:
  for p,row in load(oldcache)['files'].items():
   s=Path(p).stat();stat=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
   if stat!=row['stat']:assert sha(p)==row['sha256'],'admitted_old_source_changed:'+p;drift[p]=row['sha256']
   if p in merged:assert merged[p]['sha256']==row['sha256']
   merged[p]={'sha256':row['sha256'],'stat':stat}
 for p,h in {**sources,**assetsmap,**{r['origin']:r['sha256'] for r in resolved.values() if r['sha256']}}.items():
  s=Path(p).stat();merged[p]={'sha256':h,'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 cp=STAGES/'stage014_independent_run_hash_cache.json';assert not cp.exists();cp.write_text(json.dumps({'files':merged},indent=2)+'\n')
 result=dict(schema='stage014_independent_financial_source_admission_v1',status='PASS_SOURCE_FOR_59_FRESH_CANARY_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=[],source_files_sha256=sources,resolved_runtime_imports=resolved,shared_frozen_assets_sha256=assetsmap,complete_main_import_AST_unchanged_except_owned_contract_and_reserve=True,reserve_wrapper_byte_and_AST_identical_to_Stage009=True,financial_try_AST_unchanged_except_output_namespace=True,engine_AST_unchanged=True,original_overrides_AST_unchanged=True,normalization_AST_unchanged_only_validator_global_bound_to_59=True,local_59_validator_23_baseline_immutable=True,start_months=[1,3,6,9,11],starts=canonical_starts(),cutoff='2026-10-30',new_financial_runs_planned=59,data_admission_sha256=sha(STAGES/'stage014_independent_data_admission.json'),data_identity=admission['data_identity'],independent_target_tests_sha256=sha(testlog),source_hash_cache=str(cp),source_hash_cache_sha256=sha(cp),dedup_run_cache_files=len(merged),same_byte_stat_drift_rehashed=drift,allowed_financial_deltas=['independent_start_date_in_fixed59','data_path_to_append_only_20261030_snapshot','end_date20261030','management/output/freezing_IO_only'],economic_parameters_changed=[],financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'imports':len(resolved),'cache_files':len(merged)},ensure_ascii=False))
if __name__=='__main__':main()
