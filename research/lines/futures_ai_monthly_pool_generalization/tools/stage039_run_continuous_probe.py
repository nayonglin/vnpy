"""Predeclared synthetic continuous-source probes; no external data or fitting."""
from copy import deepcopy
from datetime import datetime
import hashlib,json
from pathlib import Path
from zoneinfo import ZoneInfo
from stage039_continuous_source import run_continuous_source
from test_stage039_continuous_source import source_case,fresh,replace_record
from stage034_run_episode_probe import fixtures as episode_fixtures
LINE=Path(__file__).resolve().parents[1]


def fixtures():
    rows=[]
    def add(name,c):rows.append(dict(case_id=name,case=c))
    c,ds=source_case(5);c['sessions'][ds[0]]['fresh_signal']=fresh(qty=3)
    replace_record(c,ds[1],rsi=96);replace_record(c,ds[2],ma=110)
    c['sessions'][ds[3]]['fresh_signal']=fresh('short',110,qty=3)
    add('ordinary_exit_then_new_short_and_RSI_reset',c)
    c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
    replace_record(c,ds[1],ma=110);replace_record(c,ds[2],opening=105,close=105)
    c['sessions'][ds[2]]['fresh_signal']={**fresh('long',95),'signal_high':106,'signal_low':104}
    replace_record(c,ds[3],opening=110,close=110);replace_record(c,ds[4],opening=110,close=110)
    add('new_fresh_new_initial_R_and_no_MTM_double_count',c)
    c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
    a=c['sessions'][ds[1]]['contracts']['A'];a['bar'].update(high=111,low=89);a['history'][-1]=a['bar']
    for d in ds[2:]:c['sessions'][d]['fresh_signal']=fresh()
    add('unknown_never_recovers_on_future_fresh',c)
    c,ds=source_case(4);c['sessions'][ds[0]]['fresh_signal']=fresh()
    a=c['sessions'][ds[1]]['contracts']['A'];a['economics']['open_per_lot']=None;a['ma_long_prev_value']=110
    c['sessions'][ds[2]]['fresh_signal']=fresh();add('old_missing_cost_survives_new_episode',c)
    c,ds=source_case(3);c['sessions'][ds[0]]['fresh_signal']=fresh();c['sessions'][ds[1]]['fresh_signal']={**fresh('short',120),'signal_high':111,'signal_low':89}
    a=c['sessions'][ds[1]]['contracts']['A'];a['bar'].update(high=111,low=89);a['history'][-1]=a['bar']
    a['minute_paths']=[[dict(open=100,high=101,low=89,close=95),dict(open=95,high=111,low=94,close=100)],
                       [dict(open=100,high=111,low=99,close=105),dict(open=105,high=106,low=89,close=100)]]
    a['minute_evidence_id']='synthetic-finite-paths';add('C2_two_paths_different_reentry_opportunity',c)
    c,ds=source_case(3);del c['sessions'][ds[1]];c['sessions'][ds[2]]['fresh_signal']=fresh()
    add('flat_missing_session_is_unknown_opportunity',c)
    c=next(row['case'] for row in episode_fixtures() if row['case_id']=='roll_new_c2_and_original_denominator')
    initial=c.pop('initial');start=c.pop('signal_day');c.update(start_day=start,monthly_eval_days=[])
    c['sessions'][start]=dict(target_contract='A',contracts={'A':__import__('test_stage034_episode_driver').record(start)},fresh_signal=initial)
    for session in c['sessions'].values():session.setdefault('fresh_signal',None)
    add('roll_remains_same_episode_denominator',c)
    return rows


def run():
    now=datetime.now(ZoneInfo('Asia/Shanghai'));out=LINE/'outputs/stage039_continuous_source'/now.strftime('run_%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True,exist_ok=False);inputs=fixtures();results=[]
    for row in inputs:
        before=deepcopy(row['case']);value=run_continuous_source(row['case'])
        if before!=row['case']:raise ValueError('continuous_source_mutated_input')
        results.append(dict(case_id=row['case_id'],result=value))
    for name,value in [('inputs.json',inputs),('outputs.json',results)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    paths=[p for r in results for p in r['result']['paths']]
    dependencies=[Path(__file__),LINE/'tools/stage039_continuous_source.py',LINE/'tools/test_stage039_continuous_source.py',
                  LINE/'tools/stage034_episode_driver.py',LINE/'tools/stage024_fixed_r_accounting.py',LINE/'tools/stage026_daily_exit_adapter.py',
                  LINE/'tools/stage031_roll_admissibility.py',LINE/'tools/stage012_c2_reference_frontier.py',out/'inputs.json',out/'outputs.json']
    summary=dict(issued_at=now.isoformat(),synthetic_only=True,cases=len(inputs),paths=len(paths),trace_rows=sum(len(p['trace']) for p in paths),
                 known_paths=sum(p['status']=='known' for p in paths),unknown_paths=sum(p['status']!='known' for p in paths),
                 episode_descriptors=sum(len(p['episodes']) for p in paths),monthly_evaluation_rows=sum(len(p['monthly_evaluations']) for p in paths),
                 market_replays=0,model_fits=0,training_labels=0,downloads=0,orders=0,production_changes=0,
                 financial_performance_metrics=None,bindings={str(p.relative_to(LINE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies})
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),**{k:v for k,v in summary.items() if k!='bindings'}),ensure_ascii=False))

if __name__=='__main__':run()
