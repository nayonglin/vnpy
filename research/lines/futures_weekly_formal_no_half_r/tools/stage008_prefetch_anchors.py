"""G原19纯信号候选的真实缺key预取；固定全计划分组，两worker互斥。

默认仅计数；--worker 0/1 显式开始真实Tq历史数据下载。零量已有key不下载替换。
所有金融回放/账户持仓模拟次数为0；新proof目录完整验收后一次原子发布。
"""
from pathlib import Path
import argparse,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).parent))
from stage008_data_helpers import OUT,load_plan,available_keys,select_missing,group_tasks,download_batch,atomic_json
from stage008_signal_anchor_plan import sha


def inventory():
    plan,calendar=load_plan();keys=available_keys({t['vt_symbol'] for t in plan})
    groups=group_tasks(plan)
    pending=[(i,select_missing(tasks,keys)) for i,tasks in enumerate(groups)]
    pending=[(i,tasks) for i,tasks in pending if tasks]
    return calendar,pending,dict(data_only=True,total_candidates=len(plan),existing=len(plan)-sum(len(t) for _,t in pending),
        missing=sum(len(t) for _,t in pending),fixed_groups=len(groups),pending_groups=len(pending),
        worker0_groups=sum(i%2==0 for i,_ in pending),worker1_groups=sum(i%2==1 for i,_ in pending),
        financial_replays=0,order_api_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker',type=int,choices=[0,1]);args=parser.parse_args()
    calendar,pending,counts=inventory();print(json.dumps(counts,ensure_ascii=False),flush=True)
    if args.worker is None:return
    source_sha={str(p):sha(p) for p in Path(__file__).parent.glob('*.py')}
    plan_sha=sha(OUT/'stage008_anchor_plan/tasks.csv');records=[];failure_count=0
    for index,tasks in pending:
        if index%2!=args.worker:continue
        if sha(OUT/'stage008_anchor_plan/tasks.csv')!=plan_sha:raise ValueError('G_plan_changed_during_prefetch')
        for path,digest in source_sha.items():
            if sha(path)!=digest:raise ValueError('G_code_changed_during_prefetch:'+path)
        identity=hashlib.sha256(json.dumps(tasks,sort_keys=True).encode()).hexdigest()[:12]
        folder=OUT/'stage008_minute_patches'/f'planned_w{args.worker}_{index:03d}_{identity}'
        try:
            record=download_batch(tasks,folder,calendar);record.update(worker=args.worker,batch=index)
            failure_count=0
        except BaseException as error:
            record=dict(status='failed',worker=args.worker,batch=index,error_type=type(error).__name__,data_only=True,financial_replays=0,order_api_calls=0)
            failure_count+=1
        records.append(record)
        atomic_json(OUT/f'stage008_bulk_w{args.worker}_progress.json',dict(initial_inventory=counts,plan_sha256=plan_sha,source_files=source_sha,records=records))
        print(json.dumps({k:v for k,v in record.items() if k!='tasks'},ensure_ascii=False),flush=True)
        if failure_count>=2:raise ValueError('G_consecutive_data_failures_require_review')
    failures=sum(r['status']!='complete' for r in records)
    summary=dict(status='completed_data_prefetch' if failures==0 else 'incomplete_data_prefetch',worker=args.worker,batches=len(records),successful=len(records)-failures,failed=failures,data_only=True,financial_replays=0,order_api_calls=0)
    atomic_json(OUT/f'stage008_bulk_w{args.worker}_terminal.json',summary)
    print(json.dumps(summary),flush=True)
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
