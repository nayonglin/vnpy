"""固定D组；仅补真实首分钟，不改参数和既有数据，失败证据不可覆盖。"""
from pathlib import Path
import os,sys,time,json,re,subprocess,contextlib,io
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs'
os.chdir(ROOT);sys.path[:0]=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools')]
os.environ['TZ']='Asia/Shanghai';time.tzset()
import pandas as pd
from stage249_download_minutes import download_snapshot
from stage249_prepare_replay import save_patch,verify_patch,sha256
from qmt_roll_intraday_execution import session_minutes

def main():
 credentials=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text());calendar=pd.read_csv(OUT/'data/mapping.csv').date.tolist();previous=OUT/'D_attempt003';progress=[]
 for number in range(4,1000):
  terminal=json.loads((previous/'terminal.json').read_text());error=str(terminal.get('error',''))
  if terminal['status'].startswith('completed'):
   (OUT/'D_completed_attempt.json').write_text(json.dumps(dict(path=str(previous),review_status='pending'),indent=2));return
  match=re.search(r'intraday_open_anchor_missing:([^:]+):(\d{4}-\d{2}-\d{2})',error)
  if not match:raise ValueError('non_anchor_failure_requires_investigation:'+error)
  symbol,day=match.groups();ts=session_minutes(symbol,day,calendar)[0]
  tasks=[dict(vt_symbol=symbol,trading_day=day,natural_date=ts.strftime('%Y-%m-%d'),start=ts.strftime('%H:%M'),end_exclusive=(ts+pd.Timedelta(minutes=1)).strftime('%H:%M'),session='day' if ts.hour==9 else 'night')]
  folder=OUT/'stage003_minute_patches'/('from_'+previous.name);folder.mkdir(parents=True,exist_ok=True)
  if (folder/'result.json').exists():raise ValueError('download_attempt_exists')
  (folder/'tasks.json').write_text(json.dumps(tasks,indent=2));receipt=dict(symbol=symbol,trading_day=day,expected_start=str(ts),order_api_calls=0,cancel_api_calls=0)
  try:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):raw,source=download_snapshot(tasks,credentials,45,data_length=1000)
   p=folder/'raw.parquet';raw.to_parquet(p,index=False);source.update(raw_path=str(p),source_sha256=sha256(p));patch=save_patch(folder,tasks,raw,source);verify_patch(Path(patch['parquet']),Path(patch['proof']));receipt.update(status='complete',patch=patch)
  except BaseException as e:
   message=str(e)
   for val in credentials.values():
    if isinstance(val,str) and val:message=message.replace(val,'[redacted]')
   receipt.update(status='failed',error_type=type(e).__name__,error=message[:1500])
  (folder/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False),flush=True)
  if receipt['status']!='complete':return
  label=f'{number:03d}';previous=OUT/('D_attempt'+label)
  if (previous/'terminal.json').exists():raise ValueError('replay_attempt_exists')
  with (OUT/(previous.name+'.log')).open('w') as f:code=subprocess.call([str(ROOT/'.py311/bin/python'),str(LINE/'tools/run_stage003_with_anchors.py'),'--arm','D','--attempt',label],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':str(ROOT)})
  terminal=json.loads((previous/'terminal.json').read_text()) if (previous/'terminal.json').exists() else dict(status='preflight_failed',error=(OUT/(previous.name+'.log')).read_text()[-1200:])
  progress.append(dict(attempt=label,code=code,terminal=terminal));(OUT/'stage003_progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2));print(json.dumps(progress[-1],ensure_ascii=False),flush=True)
  if not (previous/'terminal.json').exists():return
if __name__=='__main__':main()
