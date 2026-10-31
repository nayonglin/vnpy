"""Official publisher API; draft is readonly, prepare requires clean exact HEAD."""
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import argparse,ast,collections,json,sys,subprocess
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_strategy_material_discovery import discover_materials,MaterialDeclaration,assert_discovery_publishable
from qmt_roll_strategy_material_manifest import MaterialRole
from build_qmt_roll_official_strategy_material_release import ReleaseRequest,prepare_release
p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');args=p.parse_args()
tree=ast.parse((ROOT/'examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='DEFAULT_CRITICAL_FILES'for t in n.targets));paths=[Path(x)for x in ast.literal_eval(node.value)]
# Tests are frozen explicitly; their fixture-only dynamic module dispatch is
# not a production entrypoint. Prior read-only discovery enumerated every
# static test helper, so retain those bytes as explicit test declarations.
code=[x for x in paths if x.suffix in {'.py','.sh'}]
assets=[]
for x in paths:
 if x in code:continue
 role=MaterialRole.DECISION_ASSET if x.suffix=='.csv'else MaterialRole.OPERATIONAL_CONFIG
 if x.name=='actual_settings.json':role=MaterialRole.STRATEGY_CONFIG
 if x.name=='source_manifest.json':role=MaterialRole.FEATURE_CONTRACT
 assets.append(MaterialDeclaration(ROOT/x,str(x),role))
assets.append(MaterialDeclaration(ROOT/'.lfsconfig','.lfsconfig',MaterialRole.OPERATIONAL_CONFIG))
# Include every test module named by the fixed fault matrix, plus its local
# static helpers, via declarations. The known MODULE in the ownership test is
# the already-critical native ownership validator.
fault_tree=ast.parse((ROOT/'tests/test_stage179_fault_matrix.py').read_text())
fault_node=next(n for n in fault_tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='FAULT_CASES'for t in n.targets))
for case in fault_node.value.elts:
 assert isinstance(case,ast.Call)and isinstance(case.func,ast.Name)and case.func.id=='FaultCase'
 module=ast.literal_eval(case.args[1]);rel=Path(*module.split('.')).with_suffix('.py')
 if rel not in code:code.append(rel)
from qmt_roll_strategy_material_discovery import resolve_local_import_closure
static_tests,unresolved=resolve_local_import_closure(ROOT,[x for x in code if x.parts[0]=='tests'])
expected_unresolved={'unresolved_dynamic_import:tests/test_official_live_broker_position_ownership.py:467','unresolved_dynamic_import:tests/test_official_live_broker_position_ownership.py:53','unresolved_dynamic_import:tests/test_stage179_fault_matrix.py:113'}
assert set(unresolved)==expected_unresolved,unresolved
ownership_tree=ast.parse((ROOT/'tests/test_official_live_broker_position_ownership.py').read_text())
module_node=next(n for n in ownership_tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='MODULE'for t in n.targets))
ownership_module=ast.literal_eval(module_node.value);ownership_path=Path(*ownership_module.split('.')).with_suffix('.py')
assert Path('examples/portfolio_backtesting')/ownership_path in code
for rel in static_tests:
 if rel not in code:code.append(rel)
result=discover_materials(repo_root=ROOT,entrypoints=[x for x in code if x.suffix=='.py'and x.parts[0]!='tests'],declared_paths=code,config_assets=assets,ai_artifacts=[])
print(json.dumps(dict(mode='prepare'if args.prepare else'draft',declaration_count=len(result.declarations),blockers=list(result.blockers),prefix_counts=dict(collections.Counter(d.logical_path.split('/')[0]for d in result.declarations))),sort_keys=True))
if not args.prepare:raise SystemExit(0)
assert_discovery_publishable(result)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();now=datetime.now(timezone.utc)
request=ReleaseRequest(repo_root=ROOT,official_version='official_live_weekly19_base15w_reserve15w_stage014',capital=150000.,capital_label='15w',research_line='futures_weekly_short_ma_slope_gate',source_commit=head,
 created_at_utc=now.isoformat(),created_at_cst=now.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%dT%H:%M:%S%z'),discovery=result,
 provenance=dict(generator='research/lines/futures_weekly_short_ma_slope_gate/tools/stage016_prepare_weekly19_release.py',data_cutoff='2026-10-30',eval_date='2026-10-30',training_label_cutoff=None,ai_enabled=False,
  financial_source_commit='688754057ba1dc07caa9edc537ceec486f678372',research_verdict='NO_PROMOTION',operator_scope='replace_formal_after_real_qualification',
  test_dispatch_declarations='fixed FAULT_CASES test modules and existing critical ownership validator; no runtime dynamic import waived'),
 qualification=dict(status='candidate',evidence_ids=[],production_qualified=False,order_api_called_count=0,cancel_order_api_called_count=0))
prepared=prepare_release(request)
info=dict(release_id=prepared.release_id,material_version=prepared.material_version,release_dir=str(prepared.release_dir),manifest_path=str(prepared.manifest_path),staged_paths=list(prepared.staged_paths),
 commit_confirmation='I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:'+prepared.release_id,source_commit=head,production_qualified=False)
Path('/private/tmp/weekly19_prepared_candidate.json').write_text(json.dumps(info,indent=2));print(json.dumps(info,sort_keys=True))
