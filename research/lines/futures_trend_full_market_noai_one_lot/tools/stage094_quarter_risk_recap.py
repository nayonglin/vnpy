"""Strict 0.25% two-mode adapter reusing frozen071 allocation, episode and HTML.

Only declared .005 literals and public labels are adapted in an AST namespace;
matching/cost/R mathematics remain original functions, with full reuse evidence.
"""
import argparse,ast,copy,hashlib,json
from pathlib import Path
import stage071_fractional_recap as old
from stage062_contract_weekly_overview import WEEKLY_POLICY

PARENT_SHA='f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860'
PARENT_RUN='run_20261020_contract_weekly_risk05_v3'
PARENT_COMMIT='83e7669aca75811e50e009c3095c015311e646df'
DATA_SHA=old.BASELINE_SHA
FRACTIONAL_POLICY={**old.FRACTIONAL_POLICY,'risk_fraction':.0025,'signal_budget':'signal_equity * 0.0025','opening_budget':'min(original_signal_budget, opening_equity_after_prior_fills_costs * 0.0025)'}
NOTE=old.NOTE.replace('0.5%（0.005，100万对应5000元）','0.25%（0.0025，100万对应2500元）')
attribute_closed_lots=old.attribute_closed_lots
complete_entry_episodes=old.complete_entry_episodes
OFF_COUNTERS=('weekly_signal_candidates','weekly_budget_eligible_long_signal_rejections','weekly_execution_checks','weekly_execution_rejections')

def check(ok,reason):
 if not ok:raise ValueError(reason)

def mode_note(enabled):return ('周过滤启用：仅开多含移仓/重挂核合约自身完成周MA5>10>20>40，真实授权见冻结stage059两JSON及weekly审计。' if enabled else '周过滤关闭：未实例化/查询策略周线provider；策略周线检查数0，违规数不适用（N/A），不声称过滤通过。复盘周K仅显示行情，不构成策略周门证据。')

def validate_policy(identity,metrics):
 for obj in (identity,metrics):
  check(obj.get('fractional_risk_policy')==FRACTIONAL_POLICY,'quarter_policy_mismatch')
  for name,value in old.FRACTIONAL_FLAGS.items():check(obj.get(name) is value,'quarter_flag:'+name)
  check(obj.get('parent_execution_run_id')==PARENT_RUN and obj.get('parent_execution_manifest_sha256')==PARENT_SHA and obj.get('parent_execution_commit')==PARENT_COMMIT,'parent_execution_mismatch')
  check(obj.get('frozen_data_manifest_sha256')==DATA_SHA,'frozen_data_identity')
  enabled=obj.get('long_weekly_filter');check(isinstance(enabled,bool),'weekly_mode_missing');check(obj.get('weekly_policy')==(WEEKLY_POLICY if enabled else None),'weekly_mode_policy')
 check(identity['long_weekly_filter']==metrics['long_weekly_filter'],'weekly_mode_disagreement')
 p=identity['parameters'];check(p.get('stage068_risk_fraction')==.0025 and p.get('max_position_size')==2147483647 and p.get('min_position_size')==1 and p.get('fixed_size')==0 and p.get('max_concurrent_positions')==93,'quarter_sizing_parameters')
 if not identity['long_weekly_filter']:
  export=identity.get('weekly_feature_export');check(export==dict(scope='disabled_no_weekly_queries',queried_contracts=[],rows=0),'disabled_weekly_export')
  for obj in (identity,metrics):check(obj.get('weekly_feature_export_scope')=='disabled_no_weekly_queries','disabled_weekly_scope')
  for name in OFF_COUNTERS:check(metrics.get(name)==0,'disabled_weekly_counter:'+name)
  check(metrics.get('actual_long_weekly_violations') is None,'disabled_weekly_violations_must_be_NA')


def adapted_namespace(enabled):
 tree=ast.parse(Path(old.__file__).read_text());names=('budget','normalize_receipts','enrich');nodes=[copy.deepcopy(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];original=copy.deepcopy(nodes);changes=[]
 title='【日线近似】全市场无AI · 0.5%总权益风险预算 · 多手整数定仓逐笔复盘'
 label='合约自身完成周线N为基线；0.5%风险预算，多手、不加仓'
 literals={'.005':'.0025',title:title.replace('0.5%','0.25%'),label:'0.25%总权益风险，多手、不加仓；'+('启用' if enabled else '关闭')+'周过滤'}
 class Adapt(ast.NodeTransformer):
  def visit_Constant(self,n):
   if isinstance(n.value,float) and n.value==.005:changes.append([n.value,.0025]);n.value=.0025
   elif isinstance(n.value,str) and n.value in literals:before=n.value;n.value=literals[before];changes.append([before,n.value])
   return n
 for n in nodes:Adapt().visit(n)
 restored=copy.deepcopy(nodes);inverse={v:k for k,v in literals.items()}
 class Restore(ast.NodeTransformer):
  def visit_Constant(self,n):
   if isinstance(n.value,float) and n.value==.0025:n.value=.005
   elif isinstance(n.value,str) and n.value in inverse:n.value=inverse[n.value]
   return n
 for n in restored:Restore().visit(n)
 check(ast.dump(ast.Module(body=restored,type_ignores=[]))==ast.dump(ast.Module(body=original,type_ignores=[])),'quarter_nonliteral_AST_change')
 check(len(changes)==4,'quarter_literal_contract_changed')
 namespace={**old.__dict__,'__file__':__file__,'validate_policy':validate_policy,'FRACTIONAL_POLICY':FRACTIONAL_POLICY,'NOTE':NOTE+' '+mode_note(enabled)}
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(Path(__file__)),'exec'),namespace)
 proof=dict(source_sha256=old.sha256(Path(old.__file__)),reused_functions=list(names),constant_changes=changes,only_declared_constants_changed=True,original_AST_sha256=hashlib.sha256(ast.dump(ast.Module(body=original,type_ignores=[])).encode()).hexdigest(),adapted_AST_sha256=hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[])).encode()).hexdigest())
 return namespace,proof

def reuse_proof():return adapted_namespace(True)[1]
def budget(equity):return adapted_namespace(True)[0]['budget'](equity)

def enrich(source,parent,output):
 source,parent,output=map(lambda p:Path(p).resolve(),(source,parent,output));identity=json.loads((source/'manifest.json').read_text());metrics=json.loads((source/'summary.json').read_text());validate_policy(identity,metrics);ns,proof=adapted_namespace(identity['long_weekly_filter']);result=ns['enrich'](source,parent,output)
 evidence=dict(generator_sha256=old.sha256(Path(__file__)),algorithm=proof,parent_execution_manifest_sha256=PARENT_SHA,frozen_data_manifest_sha256=DATA_SHA,weekly_filter=identity['long_weekly_filter'],financial_replays=0)
 (output/'quarter_risk_adapter_manifest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n');result['quarter_risk_adapter']=evidence;result['artifact_sha256']['quarter_risk_adapter_manifest.json']=old.sha256(output/'quarter_risk_adapter_manifest.json');(output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source','parent','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=enrich(a.source,a.parent,a.output);print(json.dumps(r['quarter_risk_adapter'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
