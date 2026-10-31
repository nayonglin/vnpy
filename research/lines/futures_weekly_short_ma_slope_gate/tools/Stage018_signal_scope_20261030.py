"""Offline single-completed-day signal scope: no broker/production authority."""
from pathlib import Path
import csv,hashlib,json,math,sys,time
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import qmt_roll_weekly19_runtime as runtime
import qmt_roll_weekly19_data as data
import qmt_roll_weekly19_funding as funding
STAGE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages'
OLD=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate')
ASSETS=OLD/'outputs/data_stage014_20261030/data_approved'
CALENDAR=OLD/'outputs/data_stage014_20261030/raw/fresh_calendar.csv'
TARGET='2026-10-30';RELEASE='OFFLINE_STAGE018_150K_FLAT_SIGNAL_SCOPE_NOT_PRODUCTION'
ACCOUNT=hashlib.sha256(b'OFFLINE\0OFFLINE_STAGE018').hexdigest()
ASOF=datetime(2026,10,30,15,15,tzinfo=ZoneInfo('Asia/Shanghai'))
OUT=STAGE/'Stage018_signal_scope_20261030_result.json'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def clean(value):
 if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
 if isinstance(value,(list,tuple,set)):return [clean(v) for v in value]
 if isinstance(value,float) and not math.isfinite(value):return None
 if hasattr(value,'item'):return clean(value.item())
 if hasattr(value,'isoformat'):return value.isoformat()
 return value
def write(value):OUT.write_text(json.dumps(clean(value),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False,default=str)+'\n')
def envelope(raw):
 payload=json.dumps(raw,sort_keys=True,separators=(',',':'));return dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
def fixture_broker():
 common=dict(account_key=ACCOUNT,material_release_id=RELEASE,observed_at=ASOF.isoformat(),trading_day=TARGET,generation_uuid='OFFLINE_ONLY_NOT_A_REAL_QUERY',query_reqid=1,query_complete=True,offline_fixture=True,production_qualified=False)
 return dict(account=envelope(dict(common,schema='weekly19.ctp-account.v1',source_kind='ctp_account_callback',BrokerID='OFFLINE',AccountID='OFFLINE_STAGE018',CurrencyID='CNY',Balance='150000.00',Available='150000.00',Deposit='0.00',Withdraw='0.00')),positions=envelope(dict(common,schema='weekly19.ctp-positions.v1',source_kind='ctp_position_query',positions=[])))
def main():
 report=dict(schema='Stage018.signal-scope.v1',recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),target_date=TARGET,scope='OFFLINE_CONDITIONAL_150K_FLAT_COLD_START_NOT_PRODUCTION',assumptions=dict(balance=150000,available=150000,actual_positions='unknown',fixture_positions='flat',unconfirmed_external_reserve=150000,reserve_in_equity=False,asof_clock=ASOF.isoformat()),production_qualified=False,actual_broker_queried=False,formal_daily_receipt_issued=False,network_calls=0,ctp_connections=0,send_order_api_calls=0,cancel_order_api_calls=0,financial_full_history_replays=0,phases={})
 report['source_hashes_before']={name:sha(ASSETS/name) for name in data.FILES};report['calendar_sha256_before']=sha(CALENDAR)
 code=[Path(runtime.__file__),Path(data.__file__),Path(funding.__file__),runtime.DEFAULT_SETTINGS_ASSET,ROOT/'examples/portfolio_backtesting/weekly19_assets/source_manifest.json',Path(__file__)]
 report['code_hashes_before']={str(p.relative_to(ROOT)):sha(p) for p in code}
 pins=json.loads((STAGE/'20261031_stage016_runtime_real_sqlite_physical_parity.json').read_text())['source_hashes_before'];assert report['source_hashes_before']==pins
 def phase(name,call):
  start=time.monotonic();result=call();report['phases'][name]=dict(seconds=time.monotonic()-start);print('PHASE',name,report['phases'][name],flush=True);return result
 pins=dict(pins,forward_calendar=report['calendar_sha256_before'])
 inputs=phase('strict_read_inputs',lambda:data.load_weekly19_inputs(ASSETS,material_release_id=RELEASE,target_date=TARGET,forward_calendar=CALENDAR,expected_hashes=pins))
 report['conditional_data_receipt']=inputs['receipt'];report['source_data_shape']=dict(physical_rows=len(inputs['physical_epoch_daily']),positive_physical_contracts=inputs['physical_epoch_daily'].vt_symbol.nunique(),bar_days=len(inputs['bars_by_day']),target_positive_contract_bars=len(inputs['bars_by_day'][TARGET]),products=len(inputs['metadata']['product_symbols']))
 report['forward_calendar_known']= [day for day in inputs['calendar'] if day>TARGET]
 snapshot=fixture_broker();cash=funding.initial_state(ACCOUNT,RELEASE,TARGET)
 actor=phase('build_frozen_runtime',lambda:runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,inputs['metadata'],inputs['calendar'],inputs['physical_epoch_daily'],snapshot,None,cash,clock=lambda:ASOF))
 report['fixed_settings']=actor.fixed_settings;report['actual_strategy_mro']=[c.__name__ for c in type(actor.strategy).__mro__]
 batches=[inputs['bars_by_day'][d] for d in sorted(inputs['bars_by_day']) if d<TARGET]
 phase('pure_am_warmup_before_target',lambda:actor.warmup(batches))
 report['warmup_invariants']=dict(cursor=actor.warmup_cursor,intents=len(actor.engine.intents),positions=dict(actor.strategy.pos_data),layers=sum(len(s.layers) for s in actor.strategy.states.values()),funding_requests=len(actor.confirmed_cash_state['requests']))
 assert not actor.engine.intents and not any(actor.strategy.pos_data.values()) and report['warmup_invariants']['layers']==0
 decision=phase('single_completed_day',lambda:actor.process_completed_day(TARGET,inputs['bars_by_day'][TARGET],inputs['receipt'],snapshot,cash))
 report['on_bars_completed_day_calls']=1;report['decision']=decision
 print('PRELIMINARY_INTENTS',json.dumps(decision['intents'],ensure_ascii=False),flush=True)
 rows=[]
 for product,symbol in sorted(actor.metadata['daily_mapping'][TARGET].items()):
  am=actor.strategy.ams[symbol];bar=inputs['bars_by_day'][TARGET].get(symbol)
  row=dict(product=product,vt_symbol=symbol,has_actual_bar=bar is not None,weekly_count=am.count,weekly_inited=am.inited,fresh_completed_week=am.fresh,completed_week_end=actor._latest_week(symbol))
  if bar is not None:
   row.update(close=bar.close_price,close_oi=bar.open_interest,volume=bar.volume,physical_epoch_id=actor.epoch_lookup[(symbol,TARGET)])
   if am.inited:
    history=actor.strategy._build_history_df(am);signal=actor.strategy._generate_signal(am,history);row['signal_data']=signal
    native=signal.get('signal') in ('long_case1a','long_case2','short_case1a')
    row['native_entry_signal']=native
    if native:
     direction='short' if signal['signal'].startswith('short') else 'long'
     stop,valid,context=actor.strategy._weekly_initial_stop_qualification(symbol,direction,bar)
     row.update(direction=direction,weekly_initial_stop=stop,weekly_stop_valid=valid,weekly_stop_context=context)
     if direction=='short':row['short_bottom20']=actor.range_history.snapshot(symbol,TARGET,bar.close_price)
  rows.append(row)
 report['products']=rows
 for name in ('entry_candidate_snapshots','entry_risk_diagnostics','invalid_weekly_stop_rejections','short_price_range_decisions','weekly_readiness','trade_event_diagnostics','long_ma_slope_decisions','short_ma_slope_decisions'):
  if hasattr(actor.strategy,name):report[name]=getattr(actor.strategy,name)
 report['source_hashes_after']={name:sha(ASSETS/name) for name in data.FILES};report['calendar_sha256_after']=sha(CALENDAR);report['code_hashes_after']={str(p.relative_to(ROOT)):sha(p) for p in code}
 assert report['source_hashes_before']==report['source_hashes_after'] and report['calendar_sha256_before']==report['calendar_sha256_after'] and report['code_hashes_before']==report['code_hashes_after']
 report['sources_unchanged']=True;report['native_signal_products']=[r for r in rows if r.get('native_entry_signal')]
 write(report)
 print('SIGNAL_SCOPE_SUMMARY',json.dumps(clean(dict(native_signals=report['native_signal_products'],intents=decision['intents'],candidate_snapshots=report.get('entry_candidate_snapshots'),result_file=str(OUT))),ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':main()
