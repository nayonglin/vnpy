"""固定信号清单真实分钟预取；仅数据，不模拟成交/资金，两个互斥分片。"""
from pathlib import Path
import sys,os,json,time,contextlib,io,hashlib,argparse
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs'
os.chdir(ROOT);sys.path[:0]=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'),str(Path(__file__).parent)]
os.environ['TZ']='Asia/Shanghai';time.tzset()
import pandas as pd
from stage005_download_open_window_21 import download_open_window_21
import stage249_prepare_replay as rules
from stage005_sessions import product_symbol
rules.product_of=lambda s:product_symbol(s).split('.')[0]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int,choices=[0,1],required=True);args=ap.parse_args()
 plan=pd.read_csv(OUT/'stage005_anchor_plan/tasks.csv').to_dict('records');allkeys=set()
 import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
 base=s901._load_stage861_full_minute_bars({t['vt_symbol'] for t in plan})
 for r in base.itertuples():allkeys.add((r.vt_symbol,pd.Timestamp(r.bar_datetime)))
 for r in pd.read_csv(OUT/'stage003_anchor_catalog/catalog.csv',usecols=['vt_symbol','bar_datetime']).itertuples():allkeys.add((r.vt_symbol,pd.Timestamp(r.bar_datetime)))
 for pattern in ['minute_probe/*_proof.json','minute_patches/*/*_proof.json','stage003_minute_patches/*/*_proof.json','stage005_minute_patches/*/*_proof.json']:
  for proof in OUT.glob(pattern):
   p=proof.with_name(proof.name.replace('_proof.json','.parquet'));rules.verify_patch(p,proof)
   for r in pd.read_parquet(p,columns=['vt_symbol','bar_datetime']).itertuples():allkeys.add((r.vt_symbol,pd.Timestamp(r.bar_datetime)))
 pending=[t for t in plan if (t['vt_symbol'],pd.Timestamp(t['natural_date']+' '+t['start'])) not in allkeys]
 pending=sorted(pending,key=lambda t:(t['natural_date'],t['vt_symbol']));groups=[]
 for t in pending:
  if not groups or (pd.Timestamp(t['natural_date'])-pd.Timestamp(groups[-1][0]['natural_date'])).days>=14:groups.append([])
  groups[-1].append(t)
 credentials=json.loads(Path('/Users/mac/Desktop/fian/.vntrader/vt_setting.json').read_text());progress=[];failed=0
 print(json.dumps(dict(worker=args.worker,data_only=True,total_pending=len(pending),total_groups=len(groups),groups_assigned=sum(i%2==args.worker for i in range(len(groups))))),flush=True)
 for i,tasks in enumerate(groups):
  if i%2!=args.worker:continue
  identity=hashlib.sha256(json.dumps(tasks,sort_keys=True).encode()).hexdigest()[:12];folder=OUT/'stage005_minute_patches'/f'planned_w{args.worker}_{i:03d}_{identity}'
  if folder.exists():raise ValueError('immutable_batch_exists:'+str(folder))
  folder.mkdir(parents=True);(folder/'tasks.json').write_text(json.dumps(tasks,indent=2));record=dict(worker=args.worker,batch=i,segments=len(tasks),first_date=tasks[0]['natural_date'],last_date=tasks[-1]['natural_date'],data_only=True,financial_replays=0,order_api_calls=0)
  try:
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):raw,source=download_open_window_21(tasks,credentials,120,data_length=10000)
   p=(folder/'raw.parquet').resolve();raw.to_parquet(p,index=False);source.update(raw_path=str(p),source_sha256=rules.sha256(p));patch=rules.save_patch(folder.resolve(),tasks,raw,source);rules.verify_patch(Path(patch['parquet']),Path(patch['proof']));record.update(status='complete',patch=patch);failed=0
  except BaseException as e:record.update(status='failed',error_type=type(e).__name__);failed+=1
  (folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));progress.append(record);(OUT/f'stage005_bulk_w{args.worker}_progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2));print(json.dumps(record,ensure_ascii=False),flush=True)
  if failed>=2:raise ValueError('consecutive_data_failures_require_review')
 print(json.dumps(dict(status='completed_data_prefetch',worker=args.worker,batches=len(progress),successful=sum(r['status']=='complete' for r in progress),failed=sum(r['status']=='failed' for r in progress),financial_replays=0)),flush=True)
if __name__=='__main__':main()
