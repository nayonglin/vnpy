"""复用上一轮已验收Tq完成快照中真实首分钟，逐task保留原snapshot边界。"""
from pathlib import Path
import sys,json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs';sys.path.append(str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'))
from stage249_prepare_replay import save_patch,verify_patch,sha256

def main():
 calendar=sorted(pd.read_csv(OUT/'data/mapping.csv').date.unique());days=set(calendar);done=set();results=[]
 proofs=sorted((OUT/'minute_probe').glob('*_proof.json'))+sorted((OUT/'minute_patches').glob('*/*_proof.json'))
 for proof in proofs:
  p=json.loads(proof.read_text());source=p['source']
  if source.get('kind')!='tqsdk_completed_snapshot':continue
  raw=Path(source['raw_path']);digest=sha256(raw)
  if digest!=source['source_sha256']:raise ValueError('source_changed')
  if digest in done:continue
  done.add(digest);frame=pd.read_parquet(raw);frame['bar_datetime']=pd.to_datetime(frame.bar_datetime)
  selected=frame.loc[frame.bar_datetime.dt.strftime('%H:%M').isin(['09:00','21:00'])]
  tasks=[]
  for row in selected.itertuples():
   ts=row.bar_datetime;day=ts.strftime('%Y-%m-%d');clock=ts.strftime('%H:%M');bounds=source['serial_bounds'][row.vt_symbol]
   if not(pd.Timestamp(bounds['earliest'])<ts<=pd.Timestamp(bounds['latest'])<pd.Timestamp(source['snapshot_at'])):continue
   if clock=='09:00':trade=day if day in days else None
   else:trade=next((d for d in calendar if d>day),None)
   if not trade:continue
   tasks.append(dict(vt_symbol=row.vt_symbol,trading_day=trade,natural_date=day,start=clock,end_exclusive=(ts+pd.Timedelta(minutes=1)).strftime('%H:%M'),session='day' if clock=='09:00' else 'night'))
  if not tasks:continue
  folder=OUT/'stage003_minute_patches'/('snapshot_'+digest[:12]);folder.mkdir(parents=True,exist_ok=True)
  metadata={**source,'parent_proof_path':str(proof),'parent_proof_sha256':sha256(proof)}
  patch=save_patch(folder,tasks,frame,metadata);verified=verify_patch(Path(patch['parquet']),Path(patch['proof']))
  results.append(dict(patch=patch,rows=verified['rows'],raw_sha256=digest))
 (OUT/'stage003_snapshot_anchors_summary.json').write_text(json.dumps(dict(sources=len(results),rows=sum(r['rows'] for r in results),patches=results),indent=2)+'\n')
 print(json.dumps(dict(sources=len(results),rows=sum(r['rows'] for r in results))))
if __name__=='__main__':main()
