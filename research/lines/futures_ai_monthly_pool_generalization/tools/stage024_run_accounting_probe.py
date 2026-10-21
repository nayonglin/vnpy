"""Fixed synthetic fill tapes for an accounting component; no market replay."""
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from stage024_fixed_r_accounting import Economics, Fill, FixedRiskLedger

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage024_fixed_r_accounting'


def fixtures():
    def m(**kw):
        values=dict(multiplier=10,tick=1,open_per_lot=2,open_rate=0,
                    close_per_lot=3,close_rate=0,close_today_per_lot=5,close_today_rate=0,
                    historical_validated=False)
        values.update(kw)
        return asdict(Economics(**values))
    def f(kind,day,price,qty=2,contract='A',economics=None,rollover=False,slippage=0):
        return dict(kind=kind,contract=contract,trading_day=day,price=price,qty=qty,
                    economics=economics or m(),extra_slippage_price=slippage,rollover=rollover)
    opening=f('open','2020-01-02',100)
    return [
      dict(case_id='partial_today_overnight',direction='long',initial_stop=90,
           fills=[opening,f('close','2020-01-02',110,1),f('close','2020-01-03',120,1)],marks={}),
      dict(case_id='short_explicit_slippage',direction='short',initial_stop=110,
           fills=[f('open','2020-01-02',100,slippage=1),f('close','2020-01-03',90,slippage=1)],marks={}),
      dict(case_id='roll_with_different_multiplier',direction='long',initial_stop=90,
           fills=[opening,f('close','2020-01-03',110,rollover=True),
                  f('open','2020-01-03',1000,1,'B',m(multiplier=20),True)],marks={'B':1010}),
      dict(case_id='holding_mark_no_exit_fee',direction='long',initial_stop=90,fills=[opening],marks={'A':110}),
      dict(case_id='missing_mark',direction='long',initial_stop=90,fills=[opening],marks={}),
      dict(case_id='missing_open_fee',direction='long',initial_stop=90,
           fills=[f('open','2020-01-02',100,economics=m(open_per_lot=None))],marks={'A':110}),
      dict(case_id='missing_extra_slippage',direction='long',initial_stop=90,
           fills=[f('open','2020-01-02',100,slippage=None)],marks={'A':110}),
      dict(case_id='explicit_zero_fee',direction='long',initial_stop=90,
           fills=[f('open','2020-01-02',100,economics=m(open_per_lot=0,historical_validated=True))],marks={'A':100}),
      dict(case_id='turnover_today_rate',direction='long',initial_stop=90,
           fills=[f('open','2020-01-02',100,economics=m(open_per_lot=0,open_rate=.001)),
                  f('close','2020-01-02',110,economics=m(close_today_per_lot=0,close_today_rate=.002))],marks={}),
    ]


def run():
    if OUT.exists() and any(OUT.iterdir()):raise ValueError('output_exists_no_overwrite')
    OUT.mkdir(parents=True,exist_ok=True)
    inputs=fixtures();results=[]
    for case in inputs:
        ledger=FixedRiskLedger(case['direction'],case['initial_stop'])
        for event in case['fills']:
            item=dict(event);item['economics']=Economics(**item['economics'])
            ledger.apply(Fill(**item))
        results.append(dict(case_id=case['case_id'],snapshot=ledger.mark(case['marks']),tape=ledger.tape))
    for name,value in [('fixtures.json',inputs),('results.json',results)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
    summary=dict(issued_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),synthetic_only=True,
                 cases=len(inputs),fill_events=sum(len(x['fills']) for x in inputs),
                 economic_unknown=sum(x['snapshot']['status']=='economic_unknown' for x in results),
                 conditional=sum(x['snapshot']['status']=='conditional_economics' for x in results),
                 declared_validated=sum(x['snapshot']['status']=='computed_with_declared_validated_economics' for x in results),
                 complete_strategy=False,actual_market_replays=0,model_fits=0,net_60d_labels=0,
                 production_changes=0,downloads=0,financial_performance_metrics=None,
                 bindings={str(p.relative_to(LINE)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [Path(__file__),LINE/'tools/stage024_fixed_r_accounting.py',OUT/'fixtures.json',OUT/'results.json']})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='bindings'}))


if __name__=='__main__':run()
