"""仅严格真实成交：缺canonical锚即停，补已完成真实分钟后整窗重跑。"""
from pathlib import Path
import sys,os,json,time,re,subprocess,contextlib,io,argparse
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs'
os.chdir(ROOT);sys.path[:0]=[str(ROOT),str(ROOT/'examples/portfolio_backtesting'),str(Path(__file__).parent),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools')]
os.environ['TZ']='Asia/Shanghai';time.tzset()
import pandas as pd
from stage249_download_minutes import download_snapshot
from stage249_prepare_replay import save_patch,verify_patch,sha256
from stage005_sessions import canonical_open_timestamp

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['E','F'],required=True);ap.add_argument('--start',type=int,default=1);args=ap.parse_args()
 creds=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text());calendar=sorted(pd.read_csv(OUT/'stage005_data/mapping.csv').date.unique());progress=[]
 for number in range(args.start,1000):
  label=f'{number:03d}';out=OUT/(args.arm+'_attempt'+label);log=OUT/(out.name+'.log')
  if (out/'terminal.json').exists():raise ValueError('attempt_exists:'+str(out))
  with log.open('w') as f:code=subprocess.call([str(ROOT/'.py311/bin/python'),str(LINE/'tools/run_stage005_full_market.py'),'--arm',args.arm,'--attempt',label],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':str(ROOT)})
  terminal=json.loads((out/'terminal.json').read_text()) if (out/'terminal.json').exists() else dict(status='preflight_failed',error_type='see_log')
  progress.append(dict(path=str(out),code=code,terminal=terminal));(OUT/('stage005_'+args.arm+'_progress.json')).write_text(json.dumps(progress,ensure_ascii=False,indent=2));print(json.dumps(progress[-1],ensure_ascii=False),flush=True)
  if terminal['status'].startswith('completed'):
   (OUT/(args.arm+'_completed_attempt.json')).write_text(json.dumps(dict(path=str(out),review_status='pending'),indent=2));return
  error=str(terminal.get('error',''));match=re.search(r'intraday_open_anchor_missing:([^:]+):(\d{4}-\d{2}-\d{2})',error)
  if not match:raise ValueError('non_anchor_failure_requires_investigation:'+error)
  symbol,day=match.groups();ts=canonical_open_timestamp(symbol,day,calendar)
  tasks=[dict(vt_symbol=symbol,trading_day=day,natural_date=ts.strftime('%Y-%m-%d'),start=ts.strftime('%H:%M'),end_exclusive=(ts+pd.Timedelta(minutes=1)).strftime('%H:%M'),session='night' if ts.hour==21 else 'day')]
  folder=OUT/'stage005_minute_patches'/('from_'+out.name);folder.mkdir(parents=True,exist_ok=False);(folder/'tasks.json').write_text(json.dumps(tasks,indent=2));receipt=dict(symbol=symbol,trading_day=day,expected_start=str(ts),order_api_calls=0,cancel_api_calls=0)
  try:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):raw,source=download_snapshot(tasks,creds,60,data_length=1000)
   p=folder/'raw.parquet';raw.to_parquet(p,index=False);source.update(raw_path=str(p),source_sha256=sha256(p));patch=save_patch(folder,tasks,raw,source);verify_patch(Path(patch['parquet']),Path(patch['proof']));receipt.update(status='complete',patch=patch)
  except BaseException as e:
   receipt.update(status='failed',error_type=type(e).__name__)
  (folder/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False),flush=True)
  if receipt['status']!='complete':return
if __name__=='__main__':main()
