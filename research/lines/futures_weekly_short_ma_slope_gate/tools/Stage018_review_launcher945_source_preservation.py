"""Read-only C9 branch preservation plus actual new calendar/weekly cold proof."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,copy,hashlib,json,subprocess,sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import run_qmt_roll_stage945_official_live_production_session_launcher as launcher
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE
STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
REL='examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
 baseline_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
 baseline=subprocess.run(['git','show',baseline_commit+':'+REL],cwd=ROOT,capture_output=True,text=True,check=True).stdout
 current=(ROOT/REL).read_text();old={n.name:n for n in ast.parse(baseline).body if isinstance(n,ast.FunctionDef)};new={n.name:n for n in ast.parse(current).body if isinstance(n,ast.FunctionDef)}
 proof={}
 for name in ('_resolve_target_date','_target_is_before_live_shadow_start','_validate_target_date_calendar_window'):
  stripped=copy.deepcopy(new[name]);assert isinstance(stripped.body[0],ast.If);assert 'weekly19' in ast.unparse(stripped.body[0].test);stripped.body=stripped.body[1:]
  if name=='_resolve_target_date':
   idx=next(i for i,a in enumerate(stripped.args.kwonlyargs) if a.arg=='now');stripped.args.kwonlyargs.pop(idx);stripped.args.kw_defaults.pop(idx)
  expected=ast.dump(old[name],include_attributes=False);actual=ast.dump(stripped,include_attributes=False);assert actual==expected,name
  proof[name]=dict(c9_function_body_ast_preserved_after_removing_weekly_dispatch=True,ast_sha256=sha(actual.encode()))
 generation=json.loads((STAGE/'Stage018_signal_scope_complete_market_generation_receipt.json').read_text());market=generation['market_data']
 for name,want in market['expected_hashes'].items():assert sha((Path(market['asset_root'])/name).read_bytes())==want
 with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
  runtime=Path(tmp)/'runtime';ctx=runtime/'weekly19/context.json';ctx.parent.mkdir(mode=0o700,parents=True)
  cfg=dict(schema='weekly19.live-context.v1',execution_profile=WEEKLY19_15W_R150K_PROFILE.profile_key,material_release_id='STAGE018_ACTUAL_CALENDAR_PROOF_NOT_ACTUAL_ACCOUNT',cold_start_date='2026-10-31',market_data=market,cash_sources={});ctx.write_text(json.dumps(cfg));ctx.chmod(0o600)
  with patch.object(launcher,'PRODUCTION_RUNTIME_ROOT',runtime),patch.object(launcher,'resolve_configured_execution_profile',return_value=WEEKLY19_15W_R150K_PROFILE),patch.object(launcher.subprocess,'run',side_effect=AssertionError('weekly target must not call Stage922/subprocess')):
   target,payload=launcher._resolve_target_date({},now=datetime(2026,11,2,9,0,tzinfo=ZoneInfo('Asia/Shanghai')));skip=launcher._target_is_before_live_shadow_start(target_date=target,resolver_payload=payload)
  assert target=='2026-10-30' and skip and payload['cold_start_date']=='2026-10-31'
 report=dict(schema='Stage018.launcher945-weekly-source-proof.v1',source_sha256=sha(current.encode()),baseline_commit=baseline_commit,baseline_source_sha256=sha(baseline.encode()),c9_preservation=proof,actual_market_calendar=market,resolved_target=target,cold_start_skip=skip,resolver_payload=payload,scope='actual_calendar_plus_explicit_conditional_private_context_not_production_account',order_api_calls=0,ctp_connections=0,smtp_calls=0,production_qualified=False)
 (STAGE/'Stage018_review_launcher945_source_proof.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(dict(c9_branches_preserved=3,actual_calendar_target=target,context_cold_start='2026-10-31',cold_start_skip=skip,source_kind=payload['resolver_evidence']['trading_calendar_source'],source_sha256=report['source_sha256']),ensure_ascii=False))
if __name__=='__main__':main()
