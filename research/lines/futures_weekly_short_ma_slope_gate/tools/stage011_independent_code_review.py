"""Independent AST admission witness for the Stage011 financial source."""
from pathlib import Path
import ast,copy,hashlib,json
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def financial_try(tree):
 main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
 return next(n for n in main.body if isinstance(n,ast.Try))
def normalized(nodes):
 nodes=copy.deepcopy(nodes)
 for root in nodes:
  for node in ast.walk(root):
   if isinstance(node,ast.Constant) and isinstance(node.value,str):node.value=node.value.replace('stage011','stage009')
 return ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
def main():
 out=STAGES/'stage011_independent_code_review.json'
 if out.exists():raise ValueError('immutable_code_review_exists')
 old=LINE/'tools/run_stage009.py';new=LINE/'tools/run_stage011.py'
 before=financial_try(ast.parse(old.read_text())).body;after=financial_try(ast.parse(new.read_text())).body
 kept=[];witness=[]
 for node in after:
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='dump' and any(isinstance(n,ast.Constant) and n.value in ['actual_strategy_settings.json','uniform_risk_acceptance.json'] for n in ast.walk(node)):
   witness.append(ast.unparse(node));continue
  kept.append(node)
 assert len(witness)==2 and normalized(before)==normalized(kept),'financial_try_AST_changed_outside_allowed_witnesses'
 names=['run_stage011.py','stage011_risk.py','stage011_contract.py','stage011_coordinator.py','test_stage011_runner.py','test_stage011_risk.py','test_stage011_contract.py','test_stage011_coordinator.py']
 sources={str((LINE/'tools'/name).resolve()):sha(LINE/'tools'/name) for name in names}
 testlog=STAGES/'stage011_independent_core_tests_attempt001.log';mutation=STAGES/'stage011_independent_tests_attempt002.log'
 assert testlog.read_text().rstrip().endswith('OK') and mutation.read_text().rstrip().endswith('OK'),'independent_tests_must_complete_green'
 result=dict(schema='stage011_independent_code_admission_v1',status='PASS_SOURCE_FOR_FROZEN_CANARY_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=0,source_files_sha256=sources,old_runner_sha256=sha(old),financial_try_AST_exact_preservation=True,financial_try_AST_sha256=hashlib.sha256(normalized(before).encode()).hexdigest(),allowed_added_witness_statements=witness,alpha_delta='Only risk_ratio_volume_open_interest_surge .06->.018; risk_ratio_open_interest_surge .06->.018; risk_ratio_open_interest_decline .025->.018',review_findings=['Full actual setting/actual/effective snapshots must match same-window Stage009 after restoring exactly three base ratios; normalization does not authorize other strategy changes.','All calls to reserve_strategy_class, historical/next-open classes, run_backtesting, source/export/settlement/PNL/positions/weekly aggregation in the complete financial try retain exact AST.','New freeze pins23starts,10/29cutoff,46new/46old,150k+150k,2workers and same four SHA. Old Stage009 checkpoints are read with their original freeze.','Admission verifies financial-source/data/freeze/old-control manifest coverage; checkpoint identity includes source/arm/start/end/freeze and actual snapshots.','Canary approval binds both actual checkpoints and source freeze before remaining44 fixed jobs; no criterion rescans financial parameters.'],tests={'core_log':str(testlog),'core_log_sha256':sha(testlog),'mutation_log':str(mutation),'mutation_log_sha256':sha(mutation)},data_review_sha256=sha(STAGES/'stage011_independent_data_review.json'),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',source_head_admission='Root must freeze these bytes at a commit and then bind source_head/SHA before finance; results not yet run',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'status':result['status'],'core_sources':sources},ensure_ascii=False))
if __name__=='__main__':main()
