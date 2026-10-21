"""Write fixed synthetic fixtures and every finite path ledger; no market inputs."""
from dataclasses import asdict
from datetime import datetime
import csv
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from stage018_finite_path_ledger import Bar, Session, Position, enumerate_paths, KERNEL_SHA256

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage018_finite_path_probe'


def fixtures():
    def b(o,h,l,c):return Bar(o,h,l,c)
    def day(d,*paths):return Session(d,tuple(tuple(x) for x in paths))
    def mirror(path):return [b(200-x.open,200-x.low,200-x.high,200-x.close) for x in path]
    p=Position('long',100,90,1,1)
    stop=[b(100,101,89,95),b(95,111,94,100)]
    confirm=[b(100,111,99,105),b(105,106,89,100)]
    a=[b(100,101,99,100),b(100,101,99,100)]
    z=[b(100,100,99,100),b(100,101,99,100)]
    cases=[
      ('same_daily_two_actions',p,[day('2020-01-02',stop,confirm),day('2020-01-03',[b(100,101,79,80)])]),
      ('short_mirror',Position('short',100,110,1,1),[day('2020-01-02',mirror(stop),mirror(confirm)),day('2020-01-03',mirror([b(100,101,79,80)]))]),
      ('same_minute_policy',p,[day('2020-01-02',[b(100,111,89,100)])]),
      ('open_before_intrabar',p,[day('2020-01-02',[b(100,109,99,105),b(111,111,89,100)])]),
      ('expired_not_rearmed',p,[day('2020-01-02',[b(100,109,91,100)]),day('2020-01-03',[b(100,111,80,85)])]),
      ('gap_beyond_one_r',p,[day('2020-01-02',[b(100,101,95,96),b(85,89,84,88)]),day('2020-01-03',[b(100,151,99,150)])]),
      ('fill_tick_is_separate',Position('long',100,99.5,.1,1),[day('2020-01-02',[b(100,100.1,99,99.2)])]),
      ('subtick_inactive',Position('long',100,99.5,1,1),[day('2020-01-02',[b(100,101,99,99)])]),
      ('unreachable_fill',Position('long',100,90.3,.1,1),[day('2020-01-02',[b(100,101,95,96),b(91,91,90.2,90.5)])]),
      ('missing_flat_vs_holding',p,[day('2020-01-02',stop,confirm),Session('2020-01-03',None),day('2020-01-06',[b(100,121,99,120)])]),
      ('five_day_no_pruning',p,[day(f'2020-01-0{n}',a,z) for n in range(2,7)]),
      ('entry_path_missing',p,[Session('2020-01-02',None),day('2020-01-03',[b(100,121,99,120)])]),
    ]
    return cases


def run():
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('output_exists_no_overwrite')
    OUT.mkdir(parents=True,exist_ok=True)
    cases=fixtures()
    fixture_rows=[dict(case_id=name,position=asdict(p),sessions=[asdict(s) for s in sessions])
                  for name,p,sessions in cases]
    fixture_path=OUT/'fixtures.json'
    fixture_path.write_text(json.dumps(fixture_rows,indent=2)+'\n')
    results=[];flat=[]
    for name,p,sessions in cases:
        rows=enumerate_paths(p,sessions)
        results.append(dict(case_id=name,paths=rows))
        for r in rows:
            for t in r['trace']:flat.append(dict(case_id=name,path_id=r['path_id'],**t))
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    with (OUT/'trace.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    rows=[r for case in results for r in case['paths']]
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),synthetic_only=True,
                 cases=len(cases),supplied_scenarios=len(rows),daily_trace_rows=len(flat),
                 known_scenarios=sum(x['status']=='known' for x in rows),
                 execution_unknown=sum(x['status']=='execution_unknown' for x in rows),
                 path_unknown=sum(x['status']=='path_unknown' for x in rows),
                 complete_strategy=False,model_fits=0,market_replays=0,net_60d_labels=0,
                 financial_performance_metrics=None,production_changes=0,downloads=0,
                 kernel_sha256=KERNEL_SHA256,
                 bindings={str(p.relative_to(LINE)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [fixture_path,OUT/'results.json',OUT/'trace.csv',Path(__file__),
                                     LINE/'tools/stage018_finite_path_ledger.py']},
                 limits=['explicit finite synthetic paths only; not all OHLC-compatible paths',
                         'entry-session C2 only, later gross horizon MTM; ordinary strategy exits absent',
                         'no real session, historical tick, fees or trade certification',
                         'known flat survives missing future data; holding missing stays unknown',
                         'no fitting, pruning, re-entry, roll, position aggregation or formal changes'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('bindings','limits')},ensure_ascii=False))


if __name__=='__main__':run()
