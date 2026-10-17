"""One cached next-day helper case on the real completed051 snapshot; no signing."""
from pathlib import Path
from copy import deepcopy
import json
import sys

LINE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(LINE/'tools'))
import stage052_generic_daily_source_resolver as resolver


def main():
    actual=resolver.frozen.read_json(LINE/'outputs/stage036_b_ts_account/B_TS/data_wait/request_2359178d438e2191ff3691ebb97a82f41be5c81f8fa3ecd279e5b0a631e9093a/request.json')
    probe=deepcopy(actual);probe['execution_trade_date']='2020-04-16'
    target=probe['requirements'][0];target['execution_trade_date']='2020-04-16'
    calendar=resolver.pd.DatetimeIndex(resolver.pd.to_datetime(sorted(resolver.pd.read_csv(resolver.old.MAPPING,usecols=['date']).date.unique())))
    grid=resolver.old.session_grid('SM009.CZCE','2020-04-16',calendar)
    target['required_timestamps']=[s.isoformat()for s in grid]
    target['missing_or_unqualified_timestamps']=target['required_timestamps'];target['existing_source_timestamps']=[]
    probe['request_sha256']=resolver.gate.request_sha256(probe)
    assert not(resolver.OUTPUT051/('request_'+probe['request_sha256'])).exists()
    review=resolver.frozen.Review()
    daily,q,a,c=resolver.read051_daily(review,'SM009.CZCE','2020-04-16',probe)
    assert c['source_origin_request_sha256']==actual['request_sha256']
    assert c['source_origin_qualified_targets'][0]['trade_date']=='2020-04-15'
    assert c['newly_qualified_trade_date']=='2020-04-16'and c['newly_qualified_request_sha256']==probe['request_sha256']
    assert q['trade_date']=='2020-04-16'and q['successor_id']>q['source_bar_id']
    assert c['reused_completed_snapshot']is True and c['exact_DB_queries']==1
    assert all(value==0 for value in c['six_fields_max_abs_difference'].values())
    assert c['raw_non_target_daily_rows_qualified']is False
    review.unchanged()
    result=dict(status='cached_real_snapshot_next_actual_day_helper_passed',fixture_only=True,actual_main_runs=0,
        current_SM009_request_qualified=False,new_daily_receipt_signed=False,engine_loaded=False,
        source_origin_request_sha256=c['source_origin_request_sha256'],source_origin_day='2020-04-15',
        newly_checked_day='2020-04-16',daily=daily,source_bar_id=q['source_bar_id'],successor_id=q['successor_id'],
        source_sha256=resolver.old.sha256(resolver.__file__),fixture_sha256=resolver.old.sha256(__file__),
        financial_replays=0,network_connections=0,model_fits=0,orders=0,response_written=False,root_terminal_written=False)
    resolver.frozen.write(Path(__file__).parent/'cached_next_day_result.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
