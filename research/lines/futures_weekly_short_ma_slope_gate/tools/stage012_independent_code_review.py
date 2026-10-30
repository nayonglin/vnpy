"""Stage012 financial AST/source admission; no financial engine execution."""
from pathlib import Path
import ast,copy,hashlib,json
from stage012_independent_admission import reserve_AST
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def financial(tree):
 m=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');return next(n for n in m.body if isinstance(n,ast.Try)).body
def norm(nodes):
 nodes=copy.deepcopy(nodes)
 for root in nodes:
  for n in ast.walk(root):
   if isinstance(n,ast.Constant) and isinstance(n.value,str):n.value=n.value.replace('stage012','stage009')
 return ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
def main():
 out=STAGES/'stage012_independent_code_review.json'
 if out.exists():raise ValueError('immutable_stage012_code_review_exists')
 old=LINE/'tools/run_stage009.py';new=LINE/'tools/run_stage012.py';a=ast.parse(old.read_text());b=ast.parse(new.read_text());kept=[];witness=[]
 for n in financial(b):
  if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='dump' and any(isinstance(q,ast.Constant) and q.value in ['actual_strategy_settings.json','reserve_limit_acceptance.json'] for q in ast.walk(n)):witness.append(ast.unparse(n));continue
  kept.append(n)
 assert len(witness)==2 and norm(financial(a))==norm(kept),'financial_try_changed_beyond_witnesses'
 def selected(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
 assert norm([selected(a,'Engine')])==norm([selected(b,'Engine')]),'execution_engine_class_changed'
 assert norm([selected(a,'overrides')])==norm([selected(b,'overrides')]),'strategy_override_or_risk_tiers_changed'
 sources=['stage012_reserve','stage012_reuse','stage012_contract','run_stage012','stage012_coordinator']+['test_'+n for n in ['stage012_reserve','stage012_reuse','stage012_contract','stage012_runner','stage012_coordinator']]
 hashes={str((LINE/'tools'/(n+'.py')).resolve()):sha(LINE/'tools'/(n+'.py')) for n in sources};testlog=STAGES/'stage012_independent_core_tests_attempt002.log';assert testlog.read_text().rstrip().endswith('OK'),'independent_core_tests_not_finished_GREEN';proof=reserve_AST()
 result=dict(schema='stage012_independent_code_admission_v1',status='PASS_SOURCE_FOR_FROZEN_BINDING_CANARY_WITH_LIMITATIONS',accepted=True,P0=0,P1=0,P2=0,failures=0,source_files_sha256=hashes,reserve_wrapper_exact_one_constant_AST_delta=proof,complete_financial_try_AST_unchanged_except_stage_and_witnesses=True,financial_try_AST_sha256=hashlib.sha256(norm(financial(a)).encode()).hexdigest(),engine_AST_unchanged=True,strategy_overrides_AST_unchanged=True,allowed_added_witness_statements=witness,reuse_admission_sha256=sha(STAGES/'stage012_independent_reuse_admission.json'),independent_core_tests=str(testlog),independent_core_tests_sha256=sha(testlog),review_notes=['Original C risk tiers and every actual/effective setting must equal same-window Stage009; no Stage011 uniform-risk configuration is used.','Only reserve50k constant alters wallet trading state; unused R and auxiliary W have no trading consumers. Fourteen full-check coupling proofs are valid; nine binding histories require fresh engines.','Baseline control checkpoints are validated with their original Stage009 freeze; new fresh checkpoint metadata binds schema/method/head/freeze/arm/start/end.','New freeze fixes23candidate/9fresh/14reuse, C-only, same four dataSHA/cutoff,150k trading/50k reserve,2workers.','Canary gate requires earliest binding2016June fresh plus2015 full-period proven reuse checkpoints before remaining8 fresh jobs.','Former metadata-hardening and stale50k/200k diagnostic labels were corrected before freeze; no financial replay was performed.'],source_head_admission='Root must bind these exact source bytes at commit/source_head and new freeze before finance',financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',auditor_source_sha256=sha(__file__))
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(out),'sha256':sha(out),'status':result['status'],'sources':hashes},ensure_ascii=False))
if __name__=='__main__':main()
