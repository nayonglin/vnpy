"""Fixed synthetic integration fixtures; no market inputs or fitting."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from stage034_episode_driver import run_episode
from test_stage034_episode_driver import case,record

LINE=Path(__file__).resolve().parents[1]


def fixtures():
    rows=[]
    def add(name,c):rows.append(dict(case_id=name,case=c))
    c=case(horizon=3,qty=3);days=sorted(c['sessions'])
    c['sessions'][days[0]]['contracts']['A']['rsi_value']=96
    c['sessions'][days[1]]['contracts']['A']=record(days[1],100,110,ma=101)
    c['sessions'][days[2]]['contracts']['A']=record(days[2],100,90)
    for session in c['sessions'].values():
        for r in session['contracts'].values():
            r['economics'].update(open_per_lot=2,close_per_lot=3,close_today_per_lot=5)
    add('odd_rsi_actual_next_open',c)
    for mode in ('mtm','exit_next_open'):
        add('horizon_'+mode,case(horizon=2,mode=mode))
    c=case();days=sorted(c['sessions']);c['sessions'][days[0]]['contracts']['A']['rsi_value']=96
    c['sessions'][days[1]]['contracts']['A']['anchor']=None;add('pending_missing_anchor',c)
    c=case();days=sorted(c['sessions']);r=c['sessions'][days[0]]['contracts']['A']
    r['bar']=dict(open=100,high=111,low=89,close=100,volume=100);r['history'][-1]=r['bar']
    r['minute_paths']=[[dict(open=100,high=101,low=89,close=95),dict(open=95,high=111,low=94,close=100)],
                       [dict(open=100,high=111,low=99,close=105),dict(open=105,high=106,low=89,close=100)]]
    r['minute_evidence_id']='synthetic-two-paths';del c['sessions'][days[1]]
    add('two_paths_missing_holding_day',c)
    c=case();c['sessions'][sorted(c['sessions'])[0]]['contracts']['A']['economics']['open_rate']=None
    add('missing_cost',c)
    for n in (59,60,61):
        c=case(horizon=60);days=sorted(c['sessions']);c['observed_through']=days[n-1]
        c['sessions']={day:s for day,s in c['sessions'].items() if day<=c['observed_through']}
        add('fixed_clock_'+str(n),c)
    for missing in (False,True):
        c=case(horizon=8);days=sorted(c['sessions'])
        for i,day in enumerate(days):
            s=c['sessions'][day];s['target_contract']='B';s['roll_qty']=2
            r=record(day,140,140,ma=100)
            r['history']=[dict(open=100+j,high=101+j,low=99+j,close=100+j,volume=100) for j in range(41)]
            r['bar']=r['history'][-1]
            r['anchor']['price']=140
            r['economics'].update(multiplier=20,tick=.5);r['c2_guard_tick']=.5
            if i>=6:
                r['bar']=dict(open=140,high=141.5,low=139.5,close=140,volume=100);r['history'][-1]=r['bar']
            s['contracts']['B']=r
        c['sessions'][days[6]]['contracts']['A']=record(days[6],100,110)
        if missing:c['sessions'][days[6]]['contracts']['B']['anchor']=None
        add('roll_new_anchor_missing' if missing else 'roll_new_c2_and_original_denominator',c)
    return rows


def run():
    parent=LINE/'outputs/stage034_episode_driver'
    out=parent/datetime.now(ZoneInfo('Asia/Shanghai')).strftime('run_%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True,exist_ok=False)
    inputs=fixtures();results=[]
    for row in inputs:
        before=deepcopy(row['case']);value=run_episode(row['case'])
        if before!=row['case']:raise ValueError('driver_mutated_input')
        results.append(dict(case_id=row['case_id'],result=value))
    for name,value in [('inputs.json',inputs),('outputs.json',results)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    paths=[p for row in results for p in row['result']['paths']]
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),synthetic_only=True,
                 cases=len(inputs),paths=len(paths),known_paths=sum(p['status']=='known' for p in paths),
                 trajectory_unknown=sum(p['status']=='trajectory_unknown' for p in paths),
                 trace_rows=sum(len(p['trace']) for p in paths),input_mutations=0,
                 actual_market_replays=0,model_fits=0,training_labels=0,production_changes=0,
                 financial_performance_metrics=None,
                 bindings={str(p.relative_to(LINE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           [Path(__file__),LINE/'tools/stage034_episode_driver.py',LINE/'tools/test_stage034_episode_driver.py',
                            LINE/'tools/stage031_roll_admissibility.py',LINE/'tools/stage024_fixed_r_accounting.py',
                            LINE/'tools/stage026_daily_exit_adapter.py',out/'inputs.json',out/'outputs.json']})
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),**{k:v for k,v in summary.items() if k!='bindings'}),ensure_ascii=False))


if __name__=='__main__':run()
