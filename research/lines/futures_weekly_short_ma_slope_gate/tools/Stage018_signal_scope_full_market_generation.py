"""Inactive complete market generation with actual captured TQ calendar.

Copy-only frozen daily assets, no finance replay, active context or broker source.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,sqlite3,sys,uuid
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import qmt_roll_weekly19_data as reader
from qmt_roll_weekly19_context_update import resolve_completed_target
from qmt_roll_weekly19_local_backend import LocalEvidenceBackend
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved')
def sha(p):return reader._sha(p)
def write(path,value):
 raw=json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 return hashlib.sha256(raw).hexdigest()
def flush(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def main():
 capture=json.loads((STAGE/'Stage018_signal_scope_calendar_generation_receipt.json').read_text());assert capture['status']=='captured_actual_tq_calendar_conditional'
 assert sha(Path(capture['receipt_path']))==capture['receipt_sha256'];assert sha(Path(capture['calendar_path']))==capture['calendar_sha256']
 now=datetime.now(ZoneInfo('Asia/Shanghai'));parent=Path(capture['generation_path']);destination=parent/('Stage018_complete_market_'+now.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]);destination.mkdir(mode=0o700)
 pinned=json.loads((STAGE/'20261031_stage016_runtime_real_sqlite_physical_parity.json').read_text())['source_hashes_before'];before=reader._hashes(OLD,pinned)
 for name in reader.FILES:
  shutil.copy2(OLD/name,destination/name);os.chmod(destination/name,0o400);flush(destination/name);assert sha(destination/name)==pinned[name]
 calendar=destination/'forward_calendar.csv';shutil.copy2(capture['calendar_path'],calendar);os.chmod(calendar,0o400);flush(calendar)
 expected=dict(pinned,**{'forward_calendar.csv':sha(calendar)})
 assert expected['forward_calendar.csv']==capture['calendar_sha256']
 with sqlite3.connect('file:'+str(destination/'daily.sqlite')+'?mode=ro',uri=True) as connection:assert connection.execute('pragma integrity_check').fetchone()[0]=='ok'
 rawdir=destination/'raw_calendar';rawdir.mkdir(mode=0o700)
 original=json.loads(Path(capture['receipt_path']).read_text());responses=[]
 for response in original['source_responses']:
  target=rawdir/Path(response['raw_path']).name;shutil.copy2(response['raw_path'],target);os.chmod(target,0o400);flush(target);assert sha(target)==response['raw_sha256'];responses.append(dict(response,raw_path=str(target)))
 shutil.copy2(capture['receipt_path'],destination/'calendar_capture_receipt.json');os.chmod(destination/'calendar_capture_receipt.json',0o400);flush(destination/'calendar_capture_receipt.json')
 market=dict(asset_root=str(destination),forward_calendar=str(calendar),expected_hashes=expected)
 report=dict(schema='Stage018.inactive-complete-market-generation.v1',recorded_at=now.isoformat(),scope='inactive_install_preparation_no_broker_or_activation',production_qualified=False,asset_root=str(destination),market_data=market,source_receipt_identity='original_five_source_receipt_bytes_preserved; additional_actual_TQ_calendar_receipt_is_separate_and_unqualified',original_five_hashes_before=before,calendar_capture_receipt_sha256=capture['receipt_sha256'],actual_calendar_sources=responses,ctp_connections=0,order_api_calls=0,active_context_writes=0,financial_replays=0)
 release='STAGE018_MARKET_READER_CONDITIONAL_NOT_PRODUCTION_RELEASE'
 # Use the actual public backend market path. Preview prevents any production
 # promotion; missing real broker source must remain a real error, not a fixture
 # account or a fake successful full load_inputs result.
 config=dict(schema='weekly19.live-context.v1',execution_profile=PROFILE.profile_key,account_key='0'*64,material_release_id=release,market_data=market,broker=dict(summary_path=str(destination/'NO_REAL_BROKER_SUMMARY'),manifest_path=str(destination/'NO_REAL_BROKER_MANIFEST'),policy=dict(trusted_source_hashes={})))
 backend=LocalEvidenceBackend(config,repo_root=ROOT,release_manifest=destination/'NO_PRODUCTION_RELEASE',activation_receipt=destination/'NO_ACTIVATION',qualification_evidence=destination/'NO_QUALIFICATION',preview=True)
 stats=backend._market_stats(market);assert len(stats)==7
 monday=datetime(2026,11,2,9,0,tzinfo=ZoneInfo('Asia/Shanghai'));assert resolve_completed_target(backend,monday)=='2026-10-30'
 try:backend.load_inputs('2026-10-30',monday)
 except Exception as exc:
  report['full_load_inputs_broker_boundary']=dict(status='blocked_as_required_actual_broker_source_missing',error_type=type(exc).__name__,success_not_claimed=True)
 else:raise AssertionError('unexpected_broker_source_success')
 data=backend._market_cache
 assert data is not None,'actual_market_component_did_not_admit'
 assert len(data['metadata']['product_symbols'])==19 and data['receipt']['sqlite_physical_parity']['checked_rows']==392382
 assert len(data['bars_by_day']['2026-10-30'])==185 and max(data['bars_by_day'])=='2026-10-30' and not any(day>'2026-10-30' for day in data['bars_by_day'])
 assert len(data['metadata']['daily_mapping']['2026-10-30'])==19
 assert backend._market_stats(market)==stats
 report['market_validation']=dict(actual_local_backend_market_stats_entries=len(stats),actual_load_inputs_market_cache_admitted=True,sql_physical_parity=data['receipt']['sqlite_physical_parity'],fixed_products=19,target_main_coverage=19,target_contract_bars=185,max_bar_date=max(data['bars_by_day']),forward_calendar_max=max(data['calendar']),forward_calendar_next='2026-11-02',monday_0900_resolved_completed_target='2026-10-30',no_future_bar=True,conditional_read=True)
 report['original_five_hashes_after']=reader._hashes(OLD,pinned);assert before==report['original_five_hashes_after'];assert {name:sha(destination/name) for name in expected}==expected
 report['original_five_unchanged']=True;report['all_generation_pins_verified']=True
 report['source_code_hashes']={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),Path(reader.__file__),ROOT/'examples/portfolio_backtesting/qmt_roll_weekly19_local_backend.py',ROOT/'examples/portfolio_backtesting/qmt_roll_weekly19_context_update.py')}
 write(destination/'calendar_generation_source_receipt.json',report);os.chmod(destination/'calendar_generation_source_receipt.json',0o400)
 fragment=destination/'market_context_fragment.json';write(fragment,dict(market_data=market,scope='inactive_component_only_not_complete_live_context',production_qualified=False));os.chmod(fragment,0o400)
 flush(destination);report['calendar_generation_source_receipt_sha256']=sha(destination/'calendar_generation_source_receipt.json');report['market_context_fragment_path']=str(fragment);report['market_context_fragment_sha256']=sha(fragment)
 (STAGE/'Stage018_signal_scope_complete_market_generation_receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(asset_root=str(destination),calendar_sha256=expected['forward_calendar.csv'],market_validation=report['market_validation'],actual_broker_source='unknown_blocked',old_five_unchanged=True,production_qualified=False),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
