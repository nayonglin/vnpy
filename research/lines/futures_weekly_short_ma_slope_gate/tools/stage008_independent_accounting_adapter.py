"""Prove report AST preserves every financial statement outside two identity Ifs."""
from pathlib import Path
import ast,copy,hashlib,json,sys
L=Path(__file__).resolve().parents[1];ROOT=L.parents[2];sys.path.insert(0,str(L/'tools'))
import stage008_accounting as report

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 actual,receipt=report.loader_ast();source=L/'tools/stage001_report.py';before=sha(source);original=ast.parse(source.read_text());expected=copy.deepcopy(next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name=='load_ledger'));body=[];changes={'gate':0,'window':0}
 for n in expected.body:
  strings={x.value for x in ast.walk(n) if isinstance(x,ast.Constant) and isinstance(x.value,str)}
  if isinstance(n,ast.If) and 'slope_arm_flag_mismatch' in strings:body.extend(ast.parse("price_gate=read('short_price_range_acceptance.json')\n_stage008_gate_identity(pre,gate,price_gate,role)").body);changes['gate']+=1
  elif isinstance(n,ast.If) and 'full_requested_2020_calendar_required' in strings:body.extend(ast.parse('_stage008_window_identity(pre,daily)').body);changes['window']+=1
  else:body.append(n)
 expected.body=body;expected.name='_stage008_pure_accounting_loader';adapted=next(n for n in actual.body if isinstance(n,ast.FunctionDef));assert changes==dict(gate=1,window=1) and ast.dump(expected,include_attributes=False)==ast.dump(adapted,include_attributes=False)
 assert sha(source)==before and receipt['arm_check_changed'] is False
 frozen=json.loads((L/'stages/stage007_delivery_manifest.json').read_text())['files_sha256'];codes={str(p):sha(p) for p in [Path(report.__file__),L/'tools/test_stage008_accounting.py',source,L/'tools/stage006_report.py',ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage029_build_artifacts.py']}
 for p,h in codes.items():
  if p in frozen:assert frozen[p]==h
 out=L/'stages/stage008_independent_accounting_adapter.json'
 if out.exists():raise ValueError('immutable_adapter_review_exists')
 out.write_text(json.dumps(dict(status='PASS_EXACT_TWO_IDENTITY_IF_REPLACEMENTS',changes=changes,all_other_financial_AST_exactly_preserved=True,arm_check_changed=False,original_source_unchanged=True,adapted_ast_sha256=receipt['adapted_ast_sha256'],reviewed_code_sha256=codes,independent_script_sha256=sha(Path(__file__)),financial_replays=0),ensure_ascii=False,indent=2)+'\n');print(out,sha(out))
if __name__=='__main__':main()
