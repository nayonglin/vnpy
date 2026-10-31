"""Verify the public resolver with actual pinned sources; no production context write."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
import qmt_roll_weekly19_context_update as update
STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 capture=json.loads((STAGE/'Stage018_signal_scope_calendar_generation_receipt.json').read_text())
 assert capture['status']=='captured_actual_tq_calendar_conditional'
 p=Path(capture['calendar_path']);assert sha(p)==capture['calendar_sha256'];assert sha(Path(capture['receipt_path']))==capture['receipt_sha256']
 pins=json.loads((STAGE/'20261031_stage016_runtime_real_sqlite_physical_parity.json').read_text())['source_hashes_before']
 cases=[]
 for name,calendar,want in [('original_short_calendar',OLD/'raw/fresh_calendar.csv','weekly19_target_forward_calendar_coverage_expired'),('actual_new_calendar',p,'2026-10-30')]:
  backend=SimpleNamespace(config=dict(market_data=dict(asset_root=str(OLD/'data_approved'),expected_hashes=dict(pins,forward_calendar=sha(calendar)),forward_calendar=str(calendar))))
  try:result=update.resolve_completed_target(backend,datetime(2026,11,2,9,0,tzinfo=ZoneInfo('Asia/Shanghai')));status='resolved'
  except update.ContextUpdateError as exc:result=str(exc);status='blocked'
  assert result==want,(name,result,want);cases.append(dict(name=name,clock='2026-11-02T09:00:00+08:00',status=status,result=result,calendar_sha256=sha(calendar)))
 result=dict(schema='Stage018.actual-calendar-resolution-proof.v1',source='actual_TQ_calendar_capture_not_weekday_guess',source_qualification='conditional_calendar_not_production_activation',production_qualified=False,ctp_connections=0,order_api_calls=0,production_context_writes=0,cases=cases,calendar_path=str(p),calendar_sha256=sha(p),private_capture_receipt_path=capture['receipt_path'],private_capture_receipt_sha256=capture['receipt_sha256'],resolver_source_sha256=sha(Path(update.__file__)))
 (STAGE/'Stage018_signal_scope_calendar_resolution_proof.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 print(json.dumps(cases,ensure_ascii=False))
if __name__=='__main__':main()
