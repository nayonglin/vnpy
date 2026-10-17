"""Two bounded new-source structural tests; no actual main/terminal signing."""
from pathlib import Path
import csv
import json
import sys

LINE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(LINE/'tools'))
import stage052_generic_daily_source_resolver as resolver


def main():
    raw_path=LINE/'outputs/stage040_exact_request_daily_recovery/network_attempt1/raw/CZCE/SM005.csv'
    assert resolver.old.sha256(raw_path)=='c4cc24d64e3eee78f2af690c375c46682a4b9dee2f067110978ec4efbd6014dd'
    with raw_path.open(newline='')as f:raw=list(csv.DictReader(f))
    assert set(raw[0])=={'id','datetime',*resolver.old.VALUES}
    db_six=dict(open=6378.,high=6380.,low=6262.,close=6280.,volume=76307.,open_oi=68372.)
    daily,q,a,c=resolver.ordinary_raw_evidence(raw,'SM005.CZCE','2020-01-06',db_six)
    assert q['source_bar_id']==157 and q['successor_id']==158 and daily['close_oi']==61153.
    assert a['database_closeOI']=='N/A_not_independently_available'and c['actual_raw_forward_successor_checked']is True
    assert c['raw_non_target_daily_rows_qualified']is False
    empty=Path(__file__).parent/'missing_root_terminal_fixture';empty.mkdir(exist_ok=False)
    request=resolver.frozen.read_json(LINE/'outputs/stage036_b_ts_account/B_TS/data_wait/request_2359178d438e2191ff3691ebb97a82f41be5c81f8fa3ecd279e5b0a631e9093a/request.json')
    try:resolver.root051_terminal(resolver.frozen.Review(),empty,request)
    except ValueError as error:assert str(error)=='stage051_root_actual_terminal_required'
    else:raise AssertionError('missing_actual_root_terminal_was_not_rejected')
    result=dict(status='two_new_source_structural_cases_passed',cases=['ordinary_raw_schema_exact_six_and_real_forward_daily_row','missing_root_observed_terminal_rejected'],
        source_sha256=resolver.old.sha256(resolver.__file__),fixture_sha256=resolver.old.sha256(__file__),
        fixture_only=True,actual_main_runs=0,actual_SM009_qualified=False,root_terminal_written=False,
        coverage_limit='Pure raw structure and absent-root-terminal guard; successful051 envelope/main awaits root actual terminal.',
        financial_replays=0,network_connections=0,model_fits=0,orders=0,response_written=False)
    resolver.frozen.write(Path(__file__).parent/'targeted_result.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
