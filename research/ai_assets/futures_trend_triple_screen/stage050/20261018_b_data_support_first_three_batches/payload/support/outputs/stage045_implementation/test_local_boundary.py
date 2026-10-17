"""Focused resolver scope fixtures on an already bound actual source; no main."""
from pathlib import Path
import json
import sys

LINE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(LINE/'tools'))
import stage045_exact_request_resolver as resolver


def main():
    request_path=LINE/'outputs/stage036_b_ts_account/B_TS/data_wait/request_53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae/request.json'
    request=resolver.read_json(request_path);grid=resolver.pd.DatetimeIndex(request['requirements'][0]['required_timestamps'])
    daily=resolver.read_json(LINE/'outputs/stage039_independent_delivery/request_53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae/daily_checks.json')['daily']
    path=resolver.ROOT/'examples/portfolio_backtesting/downloaded_futures/tqsdk_stage491_covered_key_full_session_backfill/CZCE/SM005_completed_minute_backtest.csv'
    frame,check=resolver.local.read_bound_minute_source(path,'391899b58a6d58265fc02629e99622e16f6877dd84299800e1e0214373aa32b8','SM005.CZCE')
    assert frame is not None
    delivered,audit,proof=resolver.qualify_local({'source':frame},grid,daily,'anchor')
    assert len(delivered)==1 and len(proof)==1 and audit['session_qualification']['status']=='accepted'
    assert audit['full_session_qualified']is False and audit['required_minutes']==1
    assert proof[0]['successor_time']=='2020-01-06T09:01:00'
    bad=frame.copy();index=bad.index[bad.bar_datetime.eq(grid[0])][0];bad.loc[index,'high']+=2
    try:resolver.qualify_local({'source':frame,'conflict':bad},grid,daily,'anchor')
    except ValueError as error:assert str(error)=='completed_source_conflict'
    else:raise AssertionError('conflict_not_rejected')
    partial=frame.loc[frame.bar_datetime.isin(grid[:2])].copy().reset_index(drop=True)
    partial['source_row_number']=[2,3]
    anchor_only={'open':daily['open'],'open_oi':daily['open_oi']}
    one,one_audit,one_proof=resolver.qualify_local({'two_actual_rows':partial},grid,anchor_only,'anchor')
    assert len(one)==len(one_proof)==1 and one_audit['full_session_qualified']is False
    full,full_audit,_=resolver.qualify_local({'two_actual_rows':partial},grid,daily,'full_session')
    assert full is None and full_audit['missing_minutes']==223 and full_audit['full_session_qualified']is False
    result=dict(status='three_focused_local_boundary_cases_passed',cases=['complete225_source_delivers_anchor1_proof1_only','cross_source_anchor_price_conflict_blocks','two_actual_rows_anchor_pass_full_session_fail'],
        source_sha256=resolver.old.sha256(resolver.__file__),fixture_sha256=resolver.old.sha256(__file__),financial_replays=0,network_connections=0,actual_request_qualified_by_this_test=False)
    with(Path(__file__).parent/'targeted_anchor_revision_result.json').open('x')as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
