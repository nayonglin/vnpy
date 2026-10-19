"""Independent quarter-risk paired-display validation, no finance/provider imports.

Reuse frozen081 independent quantity/cost/calendar calculations with a declared
risk-literal adaptation, separate from094/095/096 generation algorithms.
"""
import argparse,ast,copy,hashlib,json,csv as csv_module
from pathlib import Path
import numpy as np
import pandas as pd
import stage081_validate_fractional_display as independent

PARENT_SHA='f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860'
DATA_SHA='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25'
COMMON_CODE=('stage090_quarter_risk.py','stage091_quarter_weekly.py','stage092_quarter_pending_open.py','stage093_run_quarter_pair.py')
OFF_COUNTERS=('weekly_signal_candidates','weekly_budget_eligible_long_signal_rejections','weekly_execution_checks','weekly_execution_rejections')


def check_mode_metrics(enabled,metrics):
 if enabled:
  independent.check(metrics.get('actual_long_weekly_violations')==0,'on_weekly_violation');return 0
 independent.check(all(metrics.get(n)==0 for n in OFF_COUNTERS) and metrics.get('actual_long_weekly_violations') is None,'off_not_NA_or_not_zero_checks');return 'N/A'

def audit_namespace():
 original=next(n for n in ast.parse(Path(independent.__file__).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='validate');node=copy.deepcopy(original);changes=[]
 class Adapt(ast.NodeTransformer):
  def visit_Constant(self,n):
   if isinstance(n.value,float) and n.value==.005:changes.append([n.value,.0025]);n.value=.0025
   elif n.value in ('0.5%','5000') if isinstance(n.value,str) else False:before=n.value;n.value={'0.5%':'0.25%','5000':'2500'}[before];changes.append([before,n.value])
   return n
 Adapt().visit(node);restored=copy.deepcopy(node)
 class Restore(ast.NodeTransformer):
  def visit_Constant(self,n):
   if isinstance(n.value,float) and n.value==.0025:n.value=.005
   elif isinstance(n.value,str) and n.value in ('0.25%','2500'):n.value={'0.25%':'0.5%','2500':'5000'}[n.value]
   return n
 Restore().visit(restored);independent.check(ast.dump(restored)==ast.dump(original),'audit_nondeclared_AST_change');independent.check(len(changes)==8,'audit_literal_contract_changed')
 namespace={**independent.__dict__,'__file__':__file__};exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),__file__,'exec'),namespace)
 return namespace,dict(independent_source_sha256=independent.sha(Path(independent.__file__)),only_declared_constants_changed=True,literal_changes=changes,original_AST_sha256=hashlib.sha256(ast.dump(original).encode()).hexdigest(),adapted_AST_sha256=hashlib.sha256(ast.dump(node).encode()).hexdigest())

def source_mode(source,enabled):
 m=independent.read(source/'manifest.json');stats=independent.read(source/'summary.json');independent.check(m['long_weekly_filter'] is enabled and stats['long_weekly_filter'] is enabled,'arm_mode');independent.check(m['parent_execution_manifest_sha256']==stats['parent_execution_manifest_sha256']==PARENT_SHA and m['frozen_data_manifest_sha256']==stats['frozen_data_manifest_sha256']==DATA_SHA,'reference_identity')
 independent.check(m['fractional_risk_policy']['risk_fraction']==stats['fractional_risk_policy']['risk_fraction']==.0025,'quarter_policy');check_mode_metrics(enabled,stats)
 daily=independent.csv(source/'daily.csv');trades=independent.csv(source/'trades.csv');dates=pd.to_datetime(daily.date);capital=stats['initial_capital'];equity=capital+daily.net_pnl.cumsum();peak=equity.cummax().clip(lower=capital);dd=(equity/peak-1)*100
 independent.check(len(daily)==stats['total_days']==2862 and dates.is_monotonic_increasing and not dates.duplicated().any() and daily.date.iloc[-1]==stats['analysis_end'],'source_daily_interval')
 independent.check(np.isfinite(equity).all() and np.allclose(daily.equity,equity,atol=1e-5,rtol=0) and np.allclose(daily.balance,equity,atol=1e-5,rtol=0),'source_daily_equity')
 for key,want in (('highlevel',peak),('drawdown',equity-peak),('ddpercent',dd)):independent.check(np.allclose(daily[key],want,atol=1e-7,rtol=0),'source_daily_'+key)
 for key,want in (('end_balance',equity.iloc[-1]),('total_return',(equity.iloc[-1]/capital-1)*100),('max_ddpercent',dd.min())):independent.close(stats[key],want,'source_summary_'+key)
 independent.check(len(trades)==stats['total_trade_count'],'source_fill_count')
 for key in ('commission','slippage'):independent.close(trades[key].sum(),daily[key].sum(),'all_fill_daily_'+key);independent.close(stats['total_'+key],daily[key].sum(),'summary_total_'+key)
 if not enabled:
  independent.check(m['weekly_policy'] is None and stats['weekly_policy'] is None,'off_policy_not_NA');independent.check(m['weekly_feature_export']==dict(scope='disabled_no_weekly_queries',queried_contracts=[],rows=0),'off_export_not_empty')
  for obj in (m,stats):independent.check(obj['weekly_feature_export_scope']=='disabled_no_weekly_queries','off_export_scope')
  for name in ('weekly_contract_features.csv','weekly_signal_audit.csv','weekly_execution_audit.csv'):
   try:table=independent.csv(source/name)
   except pd.errors.EmptyDataError:
    independent.check(name in ('weekly_signal_audit.csv','weekly_execution_audit.csv') and not (source/name).read_text().strip(),'off_malformed_empty_csv');table=pd.DataFrame()
   independent.check(table.empty,'off_financial_weekly_evidence_not_empty:'+name)
  with (source/'trades.csv').open(newline='') as handle:open_rows=[r for r in csv_module.DictReader(handle) if r['offset']=='open']
  for row in open_rows:independent.check(json.loads(row['stage059_weekly_signal_snapshot']) is None and json.loads(row['stage059_weekly_open_snapshot']) is None,'off_trade_claims_weekly_authorization_expected_null')
 else:independent.check(m['weekly_policy'] is not None and m['weekly_policy']==stats['weekly_policy'],'on_policy_missing')
 return m,stats

def validate_pair(enabled_source,disabled_source,data_source,overview=None,enabled_raw=None,disabled_raw=None,enabled_fractional=None,disabled_fractional=None,enabled_weekly=None,disabled_weekly=None,enabled_final=None,disabled_final=None,node=independent.NODE):
 enabled_source,disabled_source,data_source=map(lambda p:Path(p).resolve(),(enabled_source,disabled_source,data_source));ns,proof=audit_namespace();a,am=source_mode(enabled_source,True);b,bm=source_mode(disabled_source,False)
 independent.check(a['parameters']==b['parameters'],'pair_parameters');independent.check(a['parameters']['stage068_risk_fraction']==.0025,'pair_risk_fraction')
 for name in ('market_daily.csv','mapping.csv','contract_metadata.csv','trading_calendar.csv','lifecycle_deadlines.csv'):independent.check(a['hashes'][name]==b['hashes'][name],'pair_data_changed:'+name)
 for name in COMMON_CODE:independent.check(name in a['code_snapshot_hashes'] and a['code_snapshot_hashes'][name]==b['code_snapshot_hashes'].get(name),'pair_common_code:'+name)
 reports={}
 for label,source,raw,fractional,weekly,final in (('enabled',enabled_source,enabled_raw,enabled_fractional,enabled_weekly,enabled_final),('disabled',disabled_source,disabled_raw,disabled_fractional,disabled_weekly,disabled_final)):
  reports[label]=ns['validate'](source,data_source,raw,fractional,weekly,final,None,node);reports[label]['weekly_strategy_violations']=0 if label=='enabled' else 'N/A'
 result=dict(status='PASS_DISPLAY_ONLY',pair='risk025_weekly_enabled_vs_disabled',risk_fraction=.0025,initial_example_budget=2500,independent_algorithm=proof,enabled=reports['enabled'],disabled=reports['disabled'],financial_replays=0,browser_status='root_separate_UI_check_required')
 if overview:
  overview=Path(overview).resolve();s=independent.read(overview/'summary.json');hashes=independent.bound_files(overview);independent.check(s['enabled']['source_manifest_sha256']==independent.sha(enabled_source/'manifest.json') and s['disabled']['source_manifest_sha256']==independent.sha(disabled_source/'manifest.json'),'overview_arms_identity')
  frame=independent.csv(overview/'equity_pair.csv');figure=independent.read(overview/'figure.json');independent.check(len(figure['data'])==8,'paired_trace_count');independent.check(s['points_per_arm']==len(frame)==2862,'pair_2862_points');metrics={'enabled':am,'disabled':bm}
  for label,source,offset in (('enabled',enabled_source,0),('disabled',disabled_source,4)):
   d=independent.csv(source/'daily.csv');e=metrics[label]['initial_capital']+d.net_pnl.cumsum();peak=e.cummax().clip(lower=metrics[label]['initial_capital']);dd=(e/peak-1)*100;independent.check(d.date.tolist()==frame.date.tolist() and len(d)==2862,'pair_dates')
   for name,wanted in ((label+'_equity',e),(label+'_peak',peak),(label+'_drawdown_pct',dd)):independent.check(np.allclose(frame[name],wanted,atol=1e-7,rtol=0),'pair_csv:'+name)
   for i,wanted in enumerate((e/10000,peak/10000,dd)):
    trace=figure['data'][offset+i];independent.check(len(trace['x'])==2862 and [str(v)[:10] for v in trace['x']]==d.date.tolist() and np.allclose(trace['y'],wanted,atol=1e-9,rtol=0),'pair_plot_all_points:'+label)
   png=(overview/label/'equity_drawdown.png').read_bytes();independent.check(png.startswith(b'\x89PNG\r\n\x1a\n') and len(png)>1000,'pair_png:'+label)
  for row in s['comparison']:
   av,bv=am.get(row['key']),bm.get(row['key']);independent.check(row['enabled']==av and row['disabled']==bv,'pair_comparison_value')
   if av is not None and bv is not None:independent.close(row['delta'],av-bv,'pair_comparison_delta')
   else:independent.check(row['delta'] is None,'missing_metric_delta_not_NA')
  text=(overview/'index.html').read_text()
  for value in ('0.25%','2500','周过滤启用','周过滤关闭','N/A','不声称通过','不是本表比较臂'):independent.check(value in text,'pair_text:'+value)
  for parent in (s['enabled']['parent_directory'],s['disabled']['parent_directory']):independent.check(__import__('os').path.relpath(Path(parent)/'index.html',overview) in text,'paired_recap_link')
  result['overview']=dict(directory=str(overview),hashes=hashes,javascript_blocks=independent.scripts(overview,node),points_per_arm=2862,curve_values_checked=2862*6,comparison_rows=len(s['comparison']),weekly_off_violations='N/A')
 result['validator_sha256']=independent.sha(Path(__file__));return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('enabled-source','disabled-source','data-source','output'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('overview','enabled-raw','disabled-raw','enabled-fractional','disabled-fractional','enabled-weekly','disabled-weekly','enabled-final','disabled-final'):p.add_argument('--'+n,type=Path)
 p.add_argument('--node',type=Path,default=independent.NODE);a=p.parse_args();independent.check(not a.output.exists(),'report_already_exists')
 for root in (a.enabled_source,a.disabled_source,a.data_source,a.overview,a.enabled_raw,a.disabled_raw,a.enabled_fractional,a.disabled_fractional,a.enabled_weekly,a.disabled_weekly,a.enabled_final,a.disabled_final):
  if root:independent.check(not a.output.resolve().is_relative_to(root.resolve()),'report_inside_input')
 r=validate_pair(a.enabled_source,a.disabled_source,a.data_source,a.overview,a.enabled_raw,a.disabled_raw,a.enabled_fractional,a.disabled_fractional,a.enabled_weekly,a.disabled_weekly,a.enabled_final,a.disabled_final,a.node);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=r['status'],risk=r['risk_fraction'],overview=r.get('overview')),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
