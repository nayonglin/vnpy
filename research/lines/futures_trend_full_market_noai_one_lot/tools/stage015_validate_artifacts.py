"""Validate completed recap against frozen ledger without strategy execution."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
from stage001_frozen_recap import sha256

def validate(out):
    s=json.loads((out/'summary.json').read_text());source=Path(s['source_directory'])
    for n,h in s['artifact_sha256'].items():assert sha256(out/n)==h,n
    assert sha256(source/'manifest.json')==s['source_manifest_sha256']
    metrics=json.loads((source/'summary.json').read_text());assert s['backtest_metrics']==metrics
    page=(out/'index.html').read_text();start=page.index('const records=')+len('const records=')
    records,end=json.JSONDecoder().raw_decode(page[start:])
    t=pd.read_csv(source/'trades.csv').set_index('trade_id');episodes=pd.read_csv(out/'all_trade_episodes.csv');manifest=pd.read_csv(out/'chart_manifest.csv')
    assert len(records)==len(episodes)==len(manifest)==metrics['completed_episodes']==670
    assert set(episodes.open_trade_id)==set(manifest.open_trade_id)=={r['meta']['open_trade_id'] for r in records}
    counts=episodes.result_type.value_counts().to_dict()
    for key in ('profit','loss','flat'):assert counts.get(key,0)==s['chart_'+key+'_episodes']
    checked_ma=0
    for record in records:
        m=record['meta'];a=t.loc[m['open_trade_id']];b=t.loc[m['close_trade_id']]
        assert m['entry_date']==a.date and m['exit_date']==b.date
        assert abs(m['entry_price']-a.price)<1e-8 and abs(m['exit_price']-b.price)<1e-8
        assert m['signal']==a.signal and m['direction']==a.direction
        assert len(record['intraday']['x'])==0 and m['draw_intraday']==0
        d=record['daily'];close=pd.Series(d['close'],dtype=float)
        for p in (5,10,20,40):
            expected=close.rolling(p).mean().iloc[p-1:].to_numpy()
            actual=np.asarray(d['ma'+str(p)][p-1:],dtype=float)
            assert np.isfinite(actual).all() and np.allclose(actual,expected,atol=1e-7,rtol=1e-10)
            checked_ma+=len(expected)
    assert manifest.draw_intraday.eq(0).all() and manifest.bars_15m.eq(0).all()
    for disclosure in ['执行与残仓受限','日线近似','2022-09-01','2023—2026','供需过滤','5日换月延迟','GFEX','最后报价2018-01-02','最后报价2018-12-21','最后报价2021-12-17','最后报价2022-09-01']:
        assert disclosure in page,disclosure
    result={'status':'PASS_diagnostic_artifact_only','episodes':len(records),'source_fills':len(t),
            'gross_result_counts':counts,'daily_ma_points_independently_checked':checked_ma,
            'all_entry_exit_dates_prices_signals_matched':True,'metrics_unchanged':True,'missing_minutes_qualified_unavailable':True,
            'html_sha256':sha256(out/'index.html'),'summary_sha256':sha256(out/'summary.json'),
            'source_manifest_sha256':sha256(source/'manifest.json'),'performance_certifiable':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result
if __name__=='__main__':
    result=validate(Path(sys.argv[1]).resolve())
    Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2))
