"""仅补固定策略实际访问的缺失分钟；不调参、不替换已有分钟、不接受失败绩效。"""
from pathlib import Path
import os,sys,json,subprocess,re,contextlib,io,hashlib,time
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
os.chdir(ROOT);sys.path[:0]=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),'/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools']
os.environ['TZ']='Asia/Shanghai';time.tzset()
import pandas as pd
from stage249_download_minutes import download_snapshot
from stage249_prepare_replay import tasks_for_trade_day,save_patch,sha256
credentials=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text())
calendar=pd.read_csv(LINE/'outputs/data/mapping.csv').date.tolist()
status=[]
from stage249_prepare_replay import extract_fragments
symbol='MA101.CZCE';day='2020-11-09';tasks=tasks_for_trade_day(symbol,day,calendar)
folder=LINE/'outputs/minute_patches/local_MA101';folder.mkdir(parents=True,exist_ok=True)
cached=ROOT/'examples/portfolio_backtesting/downloaded_futures/tqsdk_stage491_covered_key_full_session_backfill/CZCE/MA101_completed_minute_backtest.csv'
frame=pd.read_csv(cached);frame['bar_datetime']=pd.to_datetime(frame.bar_datetime)
raw=extract_fragments(frame,tasks);p=folder/'raw.parquet';raw.to_parquet(p,index=False)
source=dict(kind='existing_completed_minute_cache',original_path=str(cached.resolve()),original_sha256=sha256(cached),raw_path=str(p),source_sha256=sha256(p),order_api_calls=0,cancel_api_calls=0)
save_patch(folder,tasks,raw,source)
(folder/'source_receipt.json').write_text(json.dumps(source,indent=2))
for attempt in range(3,1000):
    label=f'{attempt:03d}';out=LINE/'outputs'/('C_attempt'+label)
    if (out/'terminal.json').exists():continue
    log=LINE/'outputs'/('C_attempt'+label+'.log')
    with log.open('w') as f:
        code=subprocess.call([str(ROOT/'.py311/bin/python'),str(LINE/'tools/run_weekly_with_minutes.py'),'--arm','C','--attempt',label],stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONPATH':str(ROOT)})
    terminal=json.loads((out/'terminal.json').read_text()) if (out/'terminal.json').exists() else {'status':'preflight_failed','error':log.read_text()[-1500:]}
    row={'attempt':attempt,'code':code,'terminal':terminal};status.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    (LINE/'outputs/completion_progress.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
    if code==0:
        (LINE/'outputs/C_accepted_attempt.json').write_text(json.dumps({'attempt':attempt,'path':str(out),'review_status':'pending'},indent=2));break
    error=str(terminal.get('error',''))
    match=re.search(r'intraday_(?:open_anchor_missing|minute_coverage):([^:]+):(\d{4}-\d{2}-\d{2})',error)
    if not match:break
    symbol,day=match.groups();folder=LINE/'outputs/minute_patches'/label;folder.mkdir(parents=True,exist_ok=True)
    tasks=tasks_for_trade_day(symbol,day,calendar);(folder/'tasks.json').write_text(json.dumps(tasks,indent=2))
    result={'symbol':symbol,'trading_date':day,'order_api_count':0}
    try:
        from stage249_prepare_replay import extract_fragments
        contract,exchange=symbol.split('.')
        raw=None;source=None
        for cached in sorted((ROOT/'examples/portfolio_backtesting/downloaded_futures').glob(f'*/{exchange}/{contract}_completed_minute_backtest.csv')):
            frame=pd.read_csv(cached)
            if 'bar_datetime' not in frame:continue
            frame['bar_datetime']=pd.to_datetime(frame.bar_datetime)
            try:
                fragment=extract_fragments(frame,tasks)
            except ValueError:continue
            raw=fragment;source=dict(kind='existing_completed_minute_cache',original_path=str(cached.resolve()),original_sha256=sha256(cached),order_api_calls=0,cancel_api_calls=0)
            break
        if raw is None:
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):raw,source=download_snapshot(tasks,credentials,45,data_length=10000)
        p=folder/'raw.parquet';raw.to_parquet(p,index=False);source.update(raw_path=str(p),source_sha256=sha256(p))
        result.update(status='complete',patch=save_patch(folder,tasks,raw,source))
    except BaseException as e:
        msg=str(e)
        for v in credentials.values():
            if isinstance(v,str) and v:msg=msg.replace(v,'[redacted]')
        result.update(status='failed',error_type=type(e).__name__,error=msg[:1500])
    (folder/'download_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
    if result['status']!='complete':break
