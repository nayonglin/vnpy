import copy,hashlib,json,os,sqlite3,sys,time,resource,gc
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');D=R/'research/lines/futures_weekly_short_ma_slope_gate/stages';sys.path[:0]=[str(R/'examples/portfolio_backtesting'),str(R/'tests')]
import qmt_roll_weekly19_runtime as rt
import qmt_roll_weekly19_data as reader
import qmt_roll_weekly19_funding as funding
import test_weekly19_runtime as fixture
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=['qmt_roll_weekly19_runtime.py','qmt_roll_weekly19_data.py','qmt_roll_weekly19_funding.py','qmt_roll_weekly19_pipeline_state.py']
before={n:sha(R/'examples/portfolio_backtesting'/n)for n in paths}
assert before['qmt_roll_weekly19_runtime.py']=='5a7a911af89a1319fa9b7ed752e6f42aef67bb9fbb5d7faf3678b2c5a76e6d1c'
out=D/'stage016_actual_history_independent_attempt001.json';assert not out.exists()
report=dict(schema='stage016.actual-history-independent.v1',source_before=before,phases={},production_qualified=False,real_broker_source=False,actual_ctp=False,bank_or_smtp=False,financial_replays=0,on_bars_calls=0,order_api_calls=0,broker_account='synthetic_fixture_only',clock='fixed_aware_fixture_for_deterministic_state_comparison')
def phase(name,fn):
 start=time.perf_counter();value=fn();report['phases'][name]=dict(seconds=time.perf_counter()-start,maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);out.write_text(json.dumps(report,indent=2)+'\n');print(name,report['phases'][name],flush=True);return value
source=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved')
pins=json.loads((D/'20261031_stage016_runtime_real_sqlite_physical_parity.json').read_text())['source_hashes_before']
report['data_identity']=pins;report['data_root']=str(source)
data=phase('strict_reader',lambda:reader.load_weekly19_inputs(source,material_release_id=fixture.RELEASE,target_date='2026-10-30',forward_calendar=['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06'],expected_hashes=pins))
frame=data['physical_epoch_daily'];report['actual_admitted_daily_rows']=len(frame);assert len(frame)==392382;assert max(data['bars_by_day'])=='2026-10-30';assert data['receipt']['sqlite_physical_parity']['checked_rows']==392382
checks=0
with sqlite3.connect((source/'daily.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True)as db:
 indices=sorted(set([0,len(frame)-1,*range(0,len(frame),max(1,len(frame)//37))]))
 for index in indices:
  row=frame.iloc[index];symbol,exchange=row.vt_symbol.split('.')
  values=db.execute("select open_price,high_price,low_price,close_price,volume,open_interest from dbbardata where symbol=?and exchange=?and interval='d'and substr(datetime,1,10)=?",(symbol,exchange,row.date)).fetchall();assert len(values)==1
  assert all(abs(float(a)-float(row[k]))<=1e-9 for a,k in zip(values[0],['open','high','low','close','volume','close_oi']));checks+=6
report['independent_raw_sql_sample_value_checks']=checks
now=datetime.now(ZoneInfo('Asia/Shanghai'));broker=fixture.broker(now=now,day='2026-11-02');cash=funding.initial_state(fixture.ACCOUNT,fixture.RELEASE,'2026-11-02')
actor=phase('build',lambda:rt.build_weekly19_runtime(rt.DEFAULT_SETTINGS_ASSET,data['metadata'],data['calendar'],frame,broker,None,cash,clock=lambda:now))
with patch.object(type(actor.strategy),'on_bars',side_effect=AssertionError('no financial dayloop')),patch.object(type(actor.engine),'send_order',side_effect=AssertionError('no generated or real order')):
 phase('pure_warmup',lambda:actor.warmup(list(data['bars_by_day'].values())))
assert not actor.engine.intents and not any(actor.strategy.pos_data.values())and not any(s.layers for s in actor.strategy.states.values());assert actor.confirmed_cash_state==cash
report['warmup_cursor']=actor.warmup_cursor;report['am_count']=len(actor.strategy.ams);saved=phase('export',actor.export_state);report['durable_bytes']=len(json.dumps(saved,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());assert report['durable_bytes']<64_000_000
restore=phase('restore',lambda:rt.build_weekly19_runtime(rt.DEFAULT_SETTINGS_ASSET,data['metadata'],data['calendar'],frame,broker,saved,cash,clock=lambda:now))
restored=phase('restored_export',restore.export_state);assert saved['state_sha256']==restored['state_sha256'];assert saved==restored
assert restore.confirmed_cash_state==cash and not any(restore.strategy.pos_data.values())and not restore.engine.intents
report['exact_durable_restore_equal']=True;report['reserve_remaining_fen']=cash['reserve_remaining_fen'];report['confirmed_topup_fen']=cash['confirmed_topup_fen'];report['source_after']={n:sha(R/'examples/portfolio_backtesting'/n)for n in paths};assert report['source_after']==before
report['accepted']=True;report['status']='PASS_PURE_TECHNICAL_WITH_LIMITATIONS';out.write_text(json.dumps(report,indent=2)+'\n');print('complete',report['durable_bytes'],saved['state_sha256'],flush=True)
