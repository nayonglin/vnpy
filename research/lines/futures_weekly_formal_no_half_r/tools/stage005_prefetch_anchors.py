"""只处理数据only信号清单：批量下载真正已完成首分钟；无账户/订单/绩效路径。"""
from pathlib import Path
import sys,os,json,time,contextlib,io,hashlib
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs'
os.chdir(ROOT);sys.path[:0]=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools')]
os.environ['TZ']='Asia/Shanghai';time.tzset()
import pandas as pd
from stage249_download_minutes import download_snapshot
from stage249_prepare_replay import save_patch,verify_patch,sha256

def main():
 tasks=pd.read_csv(OUT/'stage005_anchor_plan/tasks.csv').to_dict('records')
 import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
 symbols={t['vt_symbol'] for t in tasks};base=s901._load_stage861_full_minute_bars(symbols);keys={(r.vt_symbol,pd.Timestamp(r.bar_datetime)) for r in base.itertuples()}
 for pattern in ['minute_probe/*_proof.json','minute_patches/*/*_proof.json','stage003_minute_patches/*/*_proof.json','stage005_minute_patches/*/*_proof.json']:
  for proof in (OUT).glob(pattern):
   p=proof.with_name(proof.name.replace('_proof.json','.parquet'));verify_patch(p,proof)
   for row in pd.read_parquet(p,columns=['vt_symbol','bar_datetime']).itertuples():keys.add((row.vt_symbol,pd.Timestamp(row.bar_datetime)))
 for row in pd.read_csv(OUT/'stage003_anchor_catalog/catalog.csv',usecols=['vt_symbol','bar_datetime']).itertuples():keys.add((row.vt_symbol,pd.Timestamp(row.bar_datetime)))
 missing=[t for t in tasks if (t['vt_symbol'],pd.Timestamp(t['natural_date']+' '+t['start'])) not in keys]
 creds=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text());groups={}
 for t in missing:groups.setdefault(t['natural_date'],[]).append(t)
 print(json.dumps(dict(data_only=True,planned_tasks=len(tasks),missing=len(missing),natural_dates=len(groups))),flush=True);progress=[]
 for day,t in sorted(groups.items()):
  identity=hashlib.sha256(json.dumps(t,sort_keys=True).encode()).hexdigest()[:12];folder=OUT/'stage005_minute_patches'/('prefetch_'+day+'_'+identity)
  if (folder/'result.json').exists():
   record=json.loads((folder/'result.json').read_text())
   if record['status']!='complete':raise ValueError('previous_failed_prefetch_requires_review:'+str(folder))
   progress.append(record);continue
  folder.mkdir(parents=True,exist_ok=False);(folder/'tasks.json').write_text(json.dumps(t,indent=2));record=dict(date=day,segments=len(t),data_only=True,order_api_calls=0)
  try:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):raw,source=download_snapshot(t,creds,60,data_length=1000)
   p=folder/'raw.parquet';raw.to_parquet(p,index=False);source.update(raw_path=str(p),source_sha256=sha256(p));patch=save_patch(folder,t,raw,source);verify_patch(Path(patch['parquet']),Path(patch['proof']));record.update(status='complete',patch=patch)
  except BaseException as e:record.update(status='failed',error_type=type(e).__name__)
  (folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));progress.append(record);(OUT/'stage005_prefetch_progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False),flush=True)
  if record['status']!='complete':return
if __name__=='__main__':main()
