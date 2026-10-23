"""G专用严格缺canonical补齐控制器；完成或整窗执行否决均停止。

调用run_stage008_three_ma_missing_only.py --attempt NNN；只有实际missing错误触发真实snapshot
补数。零量及其它错误绝不当missing，不跳信号、不换分钟、不改价、不删品种。
金融runner与此控制器只能在明确冻结代码后由操作者启动。
"""
from pathlib import Path
import argparse,json,os,subprocess,sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from stage008_data_helpers import ROOT,LINE,OUT,load_plan,available_keys,select_missing,error_task,task_key,download_batch,atomic_json


def completion_pointer(path,terminal):
    status=str(terminal.get('status',''))
    if status=='completed_pending_independent_review':
        return dict(path=str(path),review_status='pending_independent_review',diagnostic_completed=False,qualified_execution=False,
            qualification_note='execution acceptance and independent review required; not a promotion')
    if status in {'rejected_reject_execution_zero_volume','rejected_reject_execution_anchor_mismatch'}:
        return dict(path=str(path),review_status='pending_independent_review',diagnostic_completed=True,qualified_execution=False,
            execution_status=status,qualification_note='diagnostic ledger retained; rejected execution is not qualified performance')
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--start',type=int,default=1);parser.add_argument('--stop',type=int,default=999);args=parser.parse_args()
    if not 1<=args.start<=args.stop<=999:raise ValueError('invalid_attempt_range')
    plan,calendar=load_plan();progress=[]
    for number in range(args.start,args.stop+1):
        label=f'{number:03d}';out=OUT/('G_attempt'+label);log=OUT/(out.name+'.log')
        if out.exists() or log.exists():raise ValueError('G_immutable_attempt_exists:'+str(out))
        with log.open('x') as handle:
            code=subprocess.call([str(ROOT/'.py311/bin/python'),str(LINE/'tools/run_stage008_three_ma_missing_only.py'),'--attempt',label],
                stdout=handle,stderr=subprocess.STDOUT,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)})
        terminal=json.loads((out/'terminal.json').read_text()) if (out/'terminal.json').exists() else dict(status='preflight_failed',error='terminal_missing_see_log')
        record=dict(path=str(out),code=code,terminal=terminal);progress.append(record)
        atomic_json(OUT/'stage008_G_progress.json',progress);print(json.dumps(record,ensure_ascii=False),flush=True)
        pointer=completion_pointer(out,terminal)
        if pointer is not None:
            atomic_json(OUT/'G_completed_attempt.json',pointer);return
        if code==0:raise ValueError('G_unrecognized_terminal_even_with_zero_exit_code')
        actual=error_task(terminal,calendar);ts=task_key(actual)[1]
        keys=available_keys({t['vt_symbol'] for t in plan}|{actual['vt_symbol']})
        if task_key(actual) in keys:raise ValueError('G_runner_missing_key_already_in_verified_data_requires_investigation')
        candidates=[actual]+[t for t in plan if ts.normalize()<=pd.Timestamp(t['natural_date'])<=ts.normalize()+pd.Timedelta(days=13)]
        tasks=select_missing(candidates,keys)
        destination=OUT/'stage008_minute_patches'/('from_'+out.name)
        try:receipt=download_batch(tasks,destination,calendar)
        except BaseException as error:
            atomic_json(OUT/(out.name+'_download_failure.json'),dict(status='failed',error_type=type(error).__name__,data_only=True,financial_replays=0,order_api_calls=0));raise RuntimeError('G_download_failed_requires_review') from None
        print(json.dumps({k:v for k,v in receipt.items() if k!='tasks'},ensure_ascii=False),flush=True)
        subprocess.check_call([str(ROOT/'.py311/bin/python'),str(LINE/'tools/stage008_harvest_new_sources.py')],cwd=ROOT)
    raise ValueError('G_attempt_range_exhausted_without_completion')

if __name__=='__main__':main()
